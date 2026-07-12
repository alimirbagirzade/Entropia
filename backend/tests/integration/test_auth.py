"""post-V1 — local auth (M1 §4 / Master §20): commands + session-mode transport.

Auto-skips without PostgreSQL (session fixture). Proves:
- sign_up inserts principal -> human_user -> credential in FK order (L1 proof),
  always role=user, audit + outbox rows in the SAME transaction;
- duplicate-username and password-policy contracts;
- login returns a raw token exactly once and stores only its SHA-256 digest;
  unknown user / wrong password / disabled account are one indistinguishable
  INVALID_CREDENTIALS;
- logout revokes and is retry-safe (no-op second call, no audit noise);
- the session-mode actor line: fresh role every request (M1 §4.2), expired /
  revoked rejection, bare X-Actor-Id ignored, service line is non-human only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.requests import Request

from entropia.application.commands import auth as auth_cmd
from entropia.application.commands.auth import _username_hint, hash_token
from entropia.apps.api.deps import request_context
from entropia.config import get_settings
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    Agent,
    AuditEvent,
    AuthSession,
    HumanCredential,
    OutboxEvent,
    Principal,
)
from entropia.shared.errors import (
    InvalidCredentialsError,
    PasswordPolicyError,
    ServiceLineForbiddenError,
    SessionInvalidError,
    UsernameTakenError,
)

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


def _audit_factory(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """A committed-transaction factory bound to the SAME test engine, so the
    LOGIN_FAILED audit that ``login`` writes in its OWN transaction (surviving
    the request rollback) lands in this test's database — the production default
    is the app's ``lru_cache`` factory, which is not safe across test loops."""
    bind = session.bind
    assert isinstance(bind, AsyncEngine)
    return async_sessionmaker(bind=bind, expire_on_commit=False)


async def _login_failed_events(session: AsyncSession) -> list[AuditEvent]:
    """Read the committed ``auth.login_failed`` rows via a fresh session — proof
    the audit persisted independently of the raising login path."""
    async with _audit_factory(session)() as read:
        result = await read.execute(
            select(AuditEvent).where(AuditEvent.event_kind == "auth.login_failed")
        )
        return list(result.scalars().all())


@pytest.fixture
def session_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_MODE", "session")
    monkeypatch.setenv("ENTROPIA_SERVICE_TOKEN", "svc-secret-token")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_sign_up_creates_user_credential_audit_and_outbox(session: AsyncSession) -> None:
    result = await auth_cmd.sign_up(session, username="alice", password=PASSWORD)

    assert result["username"] == "alice"
    assert result["role"] == str(Role.USER)  # default role, never client-chosen

    user_id = result["user_id"]
    principal = await session.get(Principal, user_id)
    assert principal is not None and principal.principal_type == PrincipalType.HUMAN

    credential = await session.get(HumanCredential, user_id)
    assert credential is not None
    assert credential.algorithm == "argon2id"
    assert PASSWORD not in credential.password_hash  # hashed, never plaintext

    audit = (
        (await session.execute(select(AuditEvent).where(AuditEvent.event_kind == "user.signed_up")))
        .scalars()
        .all()
    )
    assert len(audit) == 1 and audit[0].target_entity_id == user_id
    outbox = (
        (await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "user_created")))
        .scalars()
        .all()
    )
    assert len(outbox) == 1 and outbox[0].resource_id == user_id


async def test_sign_up_rejects_duplicate_username_and_short_password(
    session: AsyncSession,
) -> None:
    await auth_cmd.sign_up(session, username="bob", password=PASSWORD)
    with pytest.raises(UsernameTakenError):
        await auth_cmd.sign_up(session, username="bob", password=PASSWORD)
    with pytest.raises(PasswordPolicyError):
        await auth_cmd.sign_up(session, username="carol", password="short")


async def test_login_issues_token_and_stores_only_digest(session: AsyncSession) -> None:
    await auth_cmd.sign_up(session, username="alice", password=PASSWORD)
    result = await auth_cmd.login(session, username="alice", password=PASSWORD, ttl_minutes=60)

    token = result["token"]
    record = await session.get(AuthSession, result["session_id"])
    assert record is not None
    assert record.token_hash == hash_token(token)
    assert token not in (record.token_hash,)  # raw token never persisted
    assert record.revoked_at is None and record.expires_at > datetime.now(UTC)
    assert result["user"]["username"] == "alice"


async def test_login_failure_paths_are_one_error(session: AsyncSession) -> None:
    signup = await auth_cmd.sign_up(session, username="alice", password=PASSWORD)
    factory = _audit_factory(session)

    with pytest.raises(InvalidCredentialsError):
        await auth_cmd.login(
            session,
            username="alice",
            password="wrong-password!",
            ttl_minutes=60,
            audit_session_factory=factory,
        )
    with pytest.raises(InvalidCredentialsError):
        await auth_cmd.login(
            session,
            username="nobody",
            password=PASSWORD,
            ttl_minutes=60,
            audit_session_factory=factory,
        )

    from entropia.infrastructure.postgres.models import HumanUser

    user = await session.get(HumanUser, signup["user_id"])
    assert user is not None
    user.status = "locked"
    with pytest.raises(InvalidCredentialsError):
        await auth_cmd.login(
            session,
            username="alice",
            password=PASSWORD,
            ttl_minutes=60,
            audit_session_factory=factory,
        )


async def test_login_failure_writes_login_failed_audit(session: AsyncSession) -> None:
    # GAP-20 / Master M1 §11.2: a failed login MUST leave a LOGIN_FAILED audit —
    # and it must survive the request rollback the 401 triggers (the row is read
    # back here through a SEPARATE committed session).
    await auth_cmd.sign_up(session, username="alice", password=PASSWORD)

    with pytest.raises(InvalidCredentialsError):
        await auth_cmd.login(
            session,
            username="alice",
            password="wrong-password!",
            ttl_minutes=60,
            audit_session_factory=_audit_factory(session),
        )

    events = await _login_failed_events(session)
    assert len(events) == 1
    event = events[0]
    assert event.severity == "warning"  # security-relevant, surfaces in triage
    assert event.actor_principal_id is None  # never leaks the resolved user id
    assert event.reason == "invalid_credentials"
    assert event.target_entity_id is None  # no session was opened
    # The only stored reference to the attempt is a truncated hash — never the
    # plaintext username/email, and no credential detail at all (M1 §11.2).
    hint = _username_hint("alice")
    assert event.event_metadata == {"username_hint": hint}
    assert len(hint) == 16 and hint != "alice"
    assert "wrong-password!" not in str(event.event_metadata)


async def test_login_failure_audit_is_uniform_across_reasons(session: AsyncSession) -> None:
    # The audit row must be IDENTICAL across every rejection reason (unknown user
    # / bad password / inactive account) so the trail never reveals whether the
    # account exists — the audit-side mirror of the single-401 login contract.
    signup = await auth_cmd.sign_up(session, username="alice", password=PASSWORD)
    factory = _audit_factory(session)

    async def _attempt(username: str, password: str) -> None:
        with pytest.raises(InvalidCredentialsError):
            await auth_cmd.login(
                session,
                username=username,
                password=password,
                ttl_minutes=60,
                audit_session_factory=factory,
            )

    await _attempt("ghost", PASSWORD)  # unknown user
    await _attempt("alice", "nope-nope-nope")  # known user, wrong password

    from entropia.infrastructure.postgres.models import HumanUser

    user = await session.get(HumanUser, signup["user_id"])
    assert user is not None
    user.status = "locked"  # verify succeeds, status check rejects
    await session.flush()
    await _attempt("alice", PASSWORD)

    events = await _login_failed_events(session)
    assert len(events) == 3
    assert {e.event_kind for e in events} == {"auth.login_failed"}
    assert {e.severity for e in events} == {"warning"}
    assert {e.actor_principal_id for e in events} == {None}
    assert {e.reason for e in events} == {"invalid_credentials"}
    # The ONLY field that varies is the attempted-identifier reference.
    hints = {(e.event_metadata or {})["username_hint"] for e in events}
    assert hints == {_username_hint("ghost"), _username_hint("alice")}


async def test_logout_revokes_and_is_retry_safe(session: AsyncSession) -> None:
    await auth_cmd.sign_up(session, username="alice", password=PASSWORD)
    login = await auth_cmd.login(session, username="alice", password=PASSWORD, ttl_minutes=60)

    first = await auth_cmd.logout(session, token=login["token"])
    assert first == {"session_id": login["session_id"], "revoked": True, "changed": True}
    second = await auth_cmd.logout(session, token=login["token"])
    assert second["changed"] is False  # retry-safe no-op

    audits = (
        (
            await session.execute(
                select(AuditEvent).where(AuditEvent.event_kind == "auth.session_closed")
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1  # the no-op wrote no audit noise

    with pytest.raises(SessionInvalidError):
        await auth_cmd.logout(session, token="never-issued-token")


async def test_session_mode_resolves_actor_with_fresh_role(
    session: AsyncSession, session_mode: None
) -> None:
    signup = await auth_cmd.sign_up(session, username="alice", password=PASSWORD)
    login = await auth_cmd.login(session, username="alice", password=PASSWORD, ttl_minutes=60)

    ctx = await request_context(
        _request({"Authorization": f"Bearer {login['token']}"}), session=session
    )
    assert ctx.actor.principal_id == signup["user_id"]
    assert ctx.actor.role == Role.USER

    # An Admin role change applies to the NEXT request (M1 §4.2) — no relogin.
    from entropia.infrastructure.postgres.models import HumanUser

    user = await session.get(HumanUser, signup["user_id"])
    assert user is not None
    user.current_role = Role.SUPERVISOR
    await session.flush()
    ctx2 = await request_context(
        _request({"Authorization": f"Bearer {login['token']}"}), session=session
    )
    assert ctx2.actor.role == Role.SUPERVISOR


async def test_session_mode_rejects_expired_revoked_and_ignores_actor_header(
    session: AsyncSession, session_mode: None
) -> None:
    signup = await auth_cmd.sign_up(session, username="alice", password=PASSWORD)
    login = await auth_cmd.login(session, username="alice", password=PASSWORD, ttl_minutes=60)

    # Bare X-Actor-Id is NOT a credential in session mode -> anonymous.
    ctx = await request_context(_request({"X-Actor-Id": signup["user_id"]}), session=session)
    assert not ctx.actor.is_authenticated

    # Expired session -> 401 SESSION_INVALID.
    record = await session.get(AuthSession, login["session_id"])
    assert record is not None
    record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.flush()
    with pytest.raises(SessionInvalidError):
        await request_context(
            _request({"Authorization": f"Bearer {login['token']}"}), session=session
        )

    # Revoked session -> 401 as well.
    record.expires_at = datetime.now(UTC) + timedelta(minutes=60)
    record.revoked_at = datetime.now(UTC)
    await session.flush()
    with pytest.raises(SessionInvalidError):
        await request_context(
            _request({"Authorization": f"Bearer {login['token']}"}), session=session
        )


async def test_service_line_is_non_human_only(session: AsyncSession, session_mode: None) -> None:
    signup = await auth_cmd.sign_up(session, username="alice", password=PASSWORD)
    session.add(Principal(principal_id="agent-research-01", principal_type=PrincipalType.AGENT))
    await session.flush()  # principal row must exist before the FK-dependent agent row
    session.add(Agent(agent_id="agent-research-01", name="Alpha Agent", enabled=True))
    await session.flush()

    ctx = await request_context(
        _request({"Authorization": "Bearer svc-secret-token", "X-Actor-Id": "agent-research-01"}),
        session=session,
    )
    assert ctx.actor.is_agent

    # The service line can never act as a human account (M1 §3.3).
    with pytest.raises(ServiceLineForbiddenError):
        await request_context(
            _request({"Authorization": "Bearer svc-secret-token", "X-Actor-Id": signup["user_id"]}),
            session=session,
        )
    # ...and an unknown principal on the service line is rejected too.
    with pytest.raises(ServiceLineForbiddenError):
        await request_context(
            _request({"Authorization": "Bearer svc-secret-token"}), session=session
        )
