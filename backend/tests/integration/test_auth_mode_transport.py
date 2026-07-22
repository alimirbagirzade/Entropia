"""Mode strictness in both directions, plus the session-mode provisioning shape.

``deps.py`` trusts exactly ONE mechanism per AUTH_MODE. The session-mode half
(bare X-Actor-Id ignored, expired/revoked rejected, service line non-human only)
is covered in ``test_auth.py``; this file pins the DEV half — a Bearer session
token must NOT authenticate under AUTH_MODE=dev — and the seeding rule that
keeps a real session-mode installation bootstrappable.

Both halves matter for the reported failure: the fix must make the frontend
follow the server's mode, NOT make the server accept both credentials.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from entropia.application.commands import auth as auth_cmd
from entropia.apps.api.deps import request_context
from entropia.apps.seed import DEFAULT_ADMIN_ID, seed_identities, should_seed_dev_admin
from entropia.config import get_settings
from entropia.domain.lifecycle.enums import Role
from entropia.infrastructure.postgres.models import HumanUser, Principal
from entropia.infrastructure.postgres.repositories import identity as identity_repo

pytestmark = pytest.mark.integration

PASSWORD = "correct-horse-battery"


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/me",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


@pytest.fixture
def dev_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENTROPIA_ENV", "local")
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def session_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENTROPIA_ENV", "local")
    monkeypatch.setenv("AUTH_MODE", "session")
    monkeypatch.delenv("SEED_DEV_ADMIN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Dev mode: a Bearer session token is NOT a credential.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dev_mode_ignores_a_valid_bearer_session(
    session: AsyncSession, dev_mode: None
) -> None:
    """A real, live session token authenticates NOTHING under AUTH_MODE=dev.

    This is the server-side half of the reported bug and it must stay this way:
    the fix belongs in the frontend (follow /meta.auth_mode), never in a backend
    fallback that trusts both mechanisms at once.
    """
    signup = await auth_cmd.sign_up(session, username="alice", password=PASSWORD)
    login = await auth_cmd.login(session, username="alice", password=PASSWORD, ttl_minutes=60)

    ctx = await request_context(
        _request({"Authorization": f"Bearer {login['token']}"}), session=session
    )
    assert not ctx.actor.is_authenticated

    # The dev actor header IS the credential here, and the role still comes from
    # the registry — the client never asserts one.
    ctx = await request_context(_request({"X-Actor-Id": signup["user_id"]}), session=session)
    assert ctx.actor.is_authenticated
    assert ctx.actor.principal_id == signup["user_id"]

    # A token present alongside the header does not upgrade or override it.
    ctx = await request_context(
        _request(
            {
                "Authorization": f"Bearer {login['token']}",
                "X-Actor-Id": signup["user_id"],
            }
        ),
        session=session,
    )
    assert ctx.actor.principal_id == signup["user_id"]


# ---------------------------------------------------------------------------
# Session-mode provisioning: a fresh database must be bootstrappable.
# ---------------------------------------------------------------------------


def test_seed_follows_the_auth_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTROPIA_ENV", "local")
    monkeypatch.delenv("SEED_DEV_ADMIN", raising=False)

    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    assert should_seed_dev_admin() is True

    monkeypatch.setenv("AUTH_MODE", "session")
    get_settings.cache_clear()
    assert should_seed_dev_admin() is False

    # Explicit operator override wins over the mode in both directions.
    monkeypatch.setenv("SEED_DEV_ADMIN", "1")
    assert should_seed_dev_admin() is True
    monkeypatch.setenv("SEED_DEV_ADMIN", "0")
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    assert should_seed_dev_admin() is False
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_session_mode_seed_leaves_bootstrap_open(
    session: AsyncSession, session_mode: None
) -> None:
    """The seed must not plant a credentialless ACTIVE Admin in session mode.

    Bootstrap is fail-closed ("only while no active Admin exists"), so such a row
    permanently blocks a real installation from provisioning its first Admin —
    while itself being unreachable, since nobody can log in as it.
    """
    await seed_identities(session)
    await session.flush()

    assert await session.get(HumanUser, DEFAULT_ADMIN_ID) is None
    # ...but the Principal row survives: other seeds FK-reference it as an owner,
    # and a bare principal never counts toward the active-Admin total.
    assert await session.get(Principal, DEFAULT_ADMIN_ID) is not None
    assert await identity_repo.count_active_admins(session) == 0


@pytest.mark.asyncio
async def test_fresh_session_mode_database_bootstraps_a_real_admin(
    session: AsyncSession, session_mode: None
) -> None:
    """End to end: seed a fresh session-mode database, then the bootstrap signup
    lands as a real Admin — no database edit required."""
    await seed_identities(session)
    await session.flush()

    created = await auth_cmd.sign_up(
        session,
        username="root",
        password=PASSWORD,
        email="root@entropia.test",
        bootstrap_admin_email="root@entropia.test",
    )
    assert created["role"] == str(Role.ADMIN)
    assert await identity_repo.count_active_admins(session) == 1

    # ...and the window closes behind it (fail-closed): the next signup is a
    # plain User, so the seed change opens bootstrap exactly once.
    second = await auth_cmd.sign_up(
        session,
        username="root2",
        password=PASSWORD,
        email="second@entropia.test",
        bootstrap_admin_email="root@entropia.test",
    )
    assert second["role"] == str(Role.USER)
    assert await identity_repo.count_active_admins(session) == 1
