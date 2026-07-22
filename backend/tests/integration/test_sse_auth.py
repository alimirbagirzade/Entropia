"""AUTH-11 (integration): the SSE handshake authenticates a real principal in both
modes and rejects a dead Bearer session as SESSION_INVALID.

The handshake body is ``resolve_request_actor`` followed by ``require_authenticated``
(``sse.py::_authenticated_subscriber``); the session it uses is short-lived and
closed before the stream starts. Here we pin the trust-model OUTCOME against a
seeded registry via that same direct-resolve path — mirroring the dev/session
split proven for the request pipeline in ``test_auth_mode_transport``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from entropia.application.commands import auth as auth_cmd
from entropia.apps.api.deps import resolve_request_actor
from entropia.config import get_settings
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.shared.errors import SessionInvalidError, UnauthenticatedError

pytestmark = pytest.mark.integration

PASSWORD = "correct-horse-battery"


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/events",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


async def _handshake(request: Request, session: AsyncSession) -> Actor:
    """Exactly the handshake's decision: resolve under AUTH_MODE, then require auth."""
    actor = await resolve_request_actor(request, session)
    require_authenticated(actor)
    return actor


@pytest.fixture
def dev_mode(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ENTROPIA_ENV", "local")
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def session_mode(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ENTROPIA_ENV", "local")
    monkeypatch.setenv("AUTH_MODE", "session")
    monkeypatch.delenv("SEED_DEV_ADMIN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_dev_mode_authenticated_subscriber_connects(
    session: AsyncSession, dev_mode: None
) -> None:
    signup = await auth_cmd.sign_up(session, username="alice", password=PASSWORD)

    actor = await _handshake(_request({"X-Actor-Id": signup["user_id"]}), session)

    assert actor.is_authenticated
    assert actor.principal_id == signup["user_id"]


@pytest.mark.asyncio
async def test_dev_mode_anonymous_subscriber_is_rejected(
    session: AsyncSession, dev_mode: None
) -> None:
    with pytest.raises(UnauthenticatedError):
        await _handshake(_request({}), session)


@pytest.mark.asyncio
async def test_session_mode_authenticated_subscriber_connects(
    session: AsyncSession, session_mode: None
) -> None:
    await auth_cmd.sign_up(session, username="bob", password=PASSWORD)
    login = await auth_cmd.login(session, username="bob", password=PASSWORD, ttl_minutes=60)

    actor = await _handshake(_request({"Authorization": f"Bearer {login['token']}"}), session)

    assert actor.is_authenticated


@pytest.mark.asyncio
async def test_session_mode_anonymous_subscriber_is_rejected(
    session: AsyncSession, session_mode: None
) -> None:
    with pytest.raises(UnauthenticatedError):
        await _handshake(_request({}), session)


@pytest.mark.asyncio
async def test_session_mode_dead_bearer_is_session_invalid(
    session: AsyncSession, session_mode: None
) -> None:
    # A well-formed but unknown Bearer token: the resolver must reject it with the
    # canonical SESSION_INVALID code so the client runs its one-shot invalid-session
    # flow rather than silently sitting SSE-blind.
    with pytest.raises(SessionInvalidError):
        await _handshake(_request({"Authorization": "Bearer not-a-real-session-token"}), session)
