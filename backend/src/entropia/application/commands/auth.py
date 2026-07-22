"""Local authentication commands (M1 §4 / Master §20): sign_up, login, logout.

Same conventions as every other slice: module-level async commands, one
transaction, no commit here (the caller's unit of work commits), audit written
in the SAME transaction. Sessions are infrastructure — not domain resources —
so login/logout write audit events but no outbox fan-out; sign_up creates a
domain resource (a human user) and emits both.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from entropia.domain.lifecycle.enums import ActorKind, DeletionState, PrincipalType, Role
from entropia.infrastructure.observability import get_logger
from entropia.infrastructure.postgres.engine import get_session_factory
from entropia.infrastructure.postgres.models import (
    AuthSession,
    HumanCredential,
    HumanUser,
    Principal,
    ReauthProof,
)
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import auth as auth_repo
from entropia.infrastructure.postgres.repositories import identity as identity_repo
from entropia.shared.errors import (
    InvalidCredentialsError,
    PasswordPolicyError,
    ReauthProofInvalidError,
    ReauthRequiredError,
    SessionInvalidError,
    UsernameTakenError,
    ValidationError,
)
from entropia.shared.ids import new_id
from entropia.shared.passwords import (
    DUMMY_HASH,
    MIN_PASSWORD_LENGTH,
    PASSWORD_ALGORITHM,
    hash_password,
    needs_rehash,
    verify_password,
)

_TARGET_TYPE = "human_user"
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 128
# Truncated-hash length for the failed-login "attempted identifier reference"
# (Master M1 §11.2): enough to correlate repeated attempts against one account,
# never the plaintext username/email.
_USERNAME_HINT_LENGTH = 16

log = get_logger("auth")


def hash_token(token: str) -> str:
    """SHA-256 digest of the opaque Bearer token — the only stored form."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bootstrap_admin_matches(email: str | None, bootstrap_email: str | None) -> bool:
    """Case- and whitespace-normalized bootstrap email comparison.

    An unset/empty ``bootstrap_email`` (the default) or a signup without an
    email disables the mechanism entirely — zero behavior change.
    """
    if not bootstrap_email or not email:
        return False
    return email.strip().lower() == bootstrap_email.strip().lower()


def bootstrap_is_configured(bootstrap_email: str | None) -> bool:
    """True when the operator has opted into first-Admin bootstrap by setting a
    non-empty ``ENTROPIA_BOOTSTRAP_ADMIN_EMAIL``. Pure (no infra) so it can be
    unit-tested and reused by the read-only status query."""
    return bool(bootstrap_email and bootstrap_email.strip())


def _user_projection(user: HumanUser) -> dict[str, Any]:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "role": str(user.current_role),
    }


async def sign_up(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    email: str | None = None,
    display_name: str | None = None,
    correlation_id: str = "",
    bootstrap_admin_email: str | None = None,
    auth_mode: str = "dev",
) -> dict[str, Any]:
    """Create a human account. The role is ALWAYS User (M1 §4.1): any
    client-sent role never reaches this command — the route schema has no
    role field, so escalation via Sign Up is structurally impossible.

    First-Admin bootstrap (explicit operator opt-in): when the deployment sets
    ``ENTROPIA_BOOTSTRAP_ADMIN_EMAIL`` and the signup email matches it
    (case-normalized), the account is provisioned as Admin — ONLY while no
    OPERATIONAL Admin exists (fail-closed otherwise). The role is still decided
    server-side; no client field can reach this branch.

    ``auth_mode`` selects what "operational Admin" means (audit PROV-02, §6.5):
    in ``session`` mode only a login-capable (credentialed) Admin closes the
    window, so a legacy credentialless ``user_admin`` role row does NOT block a
    real first-Admin signup; in ``dev`` mode any active Admin role row counts
    (the historical behavior). The legacy row is never deleted, demoted, renamed
    or given a credential — a session-mode bootstrap over it is a pure add
    (audit §12); it is only recorded as a PII-free legacy-upgrade audit note."""
    username = username.strip()
    if not (USERNAME_MIN_LENGTH <= len(username) <= USERNAME_MAX_LENGTH):
        raise ValidationError(
            f"Username must be {USERNAME_MIN_LENGTH}-{USERNAME_MAX_LENGTH} characters."
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    if await auth_repo.get_user_by_username(session, username) is not None:
        raise UsernameTakenError()

    role = Role.USER
    bootstrapped = False
    legacy_upgrade = False
    if bootstrap_admin_matches(email, bootstrap_admin_email):
        # Same-tx race guard, mirroring the last-admin demote path: the shared
        # advisory lock serializes this count+decide section against concurrent
        # demotions AND concurrent bootstraps; a second concurrent qualifying
        # signup is additionally impossible via unique(human_users.email).
        await identity_repo.lock_admin_count(session)
        if await identity_repo.count_operational_admins(session, auth_mode=auth_mode) == 0:
            role = Role.ADMIN
            bootstrapped = True
            # Session-mode legacy upgrade (audit §6.5.3): zero login-capable
            # Admins but an active credentialless Admin ROLE ROW already exists —
            # this signup mints the first real Admin OVER the legacy row without
            # touching it. Recorded as a PII-free audit note.
            legacy_upgrade = (
                auth_mode == "session" and await identity_repo.count_active_admins(session) > 0
            )

    user_id = new_id("usr")
    session.add(Principal(principal_id=user_id, principal_type=PrincipalType.HUMAN))
    await session.flush()  # principal must exist before the FK-dependent user row
    user = HumanUser(
        user_id=user_id,
        username=username,
        email=email,
        display_name=display_name or username,
        current_role=role,
        status="active",
        version=1,
    )
    session.add(user)
    try:
        await session.flush()  # unique(username) is enforced here
    except IntegrityError as exc:
        # Lost the unique race after the pre-check — same contract either way.
        raise UsernameTakenError() from exc
    session.add(
        HumanCredential(
            user_id=user_id,
            password_hash=hash_password(password),
            algorithm=PASSWORD_ALGORITHM,
        )
    )
    await session.flush()

    event = audit_repo.add_audit_event(
        session,
        event_kind="user.signed_up",
        actor_principal_id=user_id,  # self-registration: the new user is the actor
        actor_kind=ActorKind.HUMAN,
        target_entity_id=user_id,
        target_entity_type=_TARGET_TYPE,
        new_state="active",
        correlation_id=correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="user_created",
        resource_type=_TARGET_TYPE,
        resource_id=user_id,
        payload={
            "action": "user_created",
            "username": user.username,
            "role": str(user.current_role),
            "audit_event_id": event.event_id,
        },
        correlation_id=correlation_id,
    )
    if bootstrapped:
        # The provisioning itself is a distinct auditable action (M1 §4.1:
        # Sign Up never assigns elevated roles — this is operator provisioning).
        bootstrap_event = audit_repo.add_audit_event(
            session,
            event_kind="user.admin_bootstrapped",
            actor_principal_id=user_id,
            actor_kind=ActorKind.HUMAN,
            target_entity_id=user_id,
            target_entity_type=_TARGET_TYPE,
            new_state=str(Role.ADMIN),
            correlation_id=correlation_id,
            reason="bootstrap_admin_email_match",
            # PII-free provenance: when true, this bootstrap ran over a legacy
            # credentialless Admin that could not log in (audit §6.5.4). No email,
            # username or credential material is recorded — only the fact.
            metadata=(
                {"legacy_credentialless_admin_not_login_capable": True} if legacy_upgrade else None
            ),
        )
        audit_repo.add_outbox_event(
            session,
            event_type="admin_bootstrapped",
            resource_type=_TARGET_TYPE,
            resource_id=user_id,
            payload={
                "action": "admin_bootstrapped",
                "username": user.username,
                "role": str(Role.ADMIN),
                "audit_event_id": bootstrap_event.event_id,
            },
            correlation_id=correlation_id,
        )
    return _user_projection(user)


async def bootstrap_status(
    session: AsyncSession,
    *,
    bootstrap_admin_email: str | None = None,
) -> dict[str, Any]:
    """Read-only onboarding signal for the first-Admin flow.

    Returns booleans ONLY — no email echo, no PII — so it is safe on the
    anonymous entry surface alongside sign up / login (the first Admin is, by
    definition, not yet authenticated).

    Two distinct operational truths (audit PROV-05):

    * ``active_admin_exists`` — an Admin ROLE ROW exists (may be the legacy
      credentialless ``user_admin`` that nobody can log in as).
    * ``login_capable_admin_exists`` — a credentialed Admin who can actually log
      in and operate/recover a session-mode installation exists.

    Exposing both lets the Provisioning page report the real state: a role row
    that exists but cannot log in must still show the bootstrap window as OPEN
    (the exact defect PROV-05 flags). This is a hint, not a decision: the actual
    provisioning choice in :func:`sign_up` stays guarded by the same-tx advisory
    lock, so a stale read here can never mint a second Admin."""
    return {
        "bootstrap_configured": bootstrap_is_configured(bootstrap_admin_email),
        "active_admin_exists": await identity_repo.count_active_admins(session) > 0,
        "login_capable_admin_exists": (await identity_repo.count_login_capable_admins(session) > 0),
    }


def _username_hint(username: str) -> str:
    """A non-plaintext reference to the attempted identifier (Master M1 §11.2:
    "attempted identifier reference ... hassas credential detail saklanmaz").

    A truncated SHA-256 of the normalized username — never the plaintext — lets
    an operator correlate repeated failures against one account (brute-force /
    credential-stuffing) without persisting the username or email into the log.
    """
    return hashlib.sha256(username.strip().encode("utf-8")).hexdigest()[:_USERNAME_HINT_LENGTH]


async def _record_login_failure(
    username: str,
    correlation_id: str,
    audit_session_factory: async_sessionmaker[AsyncSession] | None,
) -> None:
    """Persist a LOGIN_FAILED audit (Master M1 §11.2) that SURVIVES the request
    unit-of-work rollback that follows the 401.

    A failed login rolls back the request session (``deps.db_session`` rolls back
    on any exception), so this row is written in its OWN committed transaction.
    It is UNIFORM across every failure reason (unknown user / bad password /
    inactive account) — no ``actor_principal_id`` and no reason beyond the shared
    error code — so the audit trail itself never reveals whether the account
    exists (user-enumeration hardening, mirroring the single-401 login contract).

    Best-effort: an audit-infra hiccup must not turn a failed login into a 500,
    so a write failure is logged (never silently swallowed) and the original 401
    still propagates.
    """
    factory = audit_session_factory or get_session_factory()
    try:
        async with factory() as audit_session:
            audit_repo.add_audit_event(
                audit_session,
                event_kind="auth.login_failed",
                actor_principal_id=None,
                actor_kind=ActorKind.HUMAN,
                severity="warning",
                reason="invalid_credentials",
                correlation_id=correlation_id,
                metadata={"username_hint": _username_hint(username)},
            )
            await audit_session.commit()
    except Exception:
        log.exception("auth.login_failed_audit_write_failed", correlation_id=correlation_id)


async def _authenticate_or_raise(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    ttl_minutes: int,
    correlation_id: str = "",
) -> dict[str, Any]:
    """Verify the credential and open a revocable server-side session, or raise.

    Every rejection path is the same 401 INVALID_CREDENTIALS and every path
    runs exactly one argon2 verification (user-enumeration hardening). The
    raw token is returned once here and persisted only as a SHA-256 digest.
    The success audit ``auth.session_opened`` is the LOGIN_SUCCEEDED record
    (Master M1 §11.2); the LOGIN_FAILED record is emitted by :func:`login`.
    """
    user = await auth_repo.get_user_by_username(session, username.strip())
    if user is None:
        verify_password(DUMMY_HASH, password)  # timing pad
        raise InvalidCredentialsError()
    credential = await auth_repo.get_credential(session, user.user_id)
    if credential is None:
        verify_password(DUMMY_HASH, password)  # timing pad
        raise InvalidCredentialsError()
    if not verify_password(credential.password_hash, password):
        raise InvalidCredentialsError()
    if user.status != "active" or user.deletion_state != DeletionState.ACTIVE:
        raise InvalidCredentialsError()

    if needs_rehash(credential.password_hash):
        credential.password_hash = hash_password(password)

    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    record = AuthSession(
        session_id=new_id("ses"),
        user_id=user.user_id,
        token_hash=hash_token(token),
        issued_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )
    session.add(record)

    audit_repo.add_audit_event(
        session,
        event_kind="auth.session_opened",
        actor_principal_id=user.user_id,
        actor_kind=ActorKind.HUMAN,
        target_entity_id=record.session_id,
        target_entity_type="auth_session",
        new_state="active",
        correlation_id=correlation_id,
    )
    return {
        "token": token,
        "session_id": record.session_id,
        "expires_at": record.expires_at.isoformat(),
        "user": _user_projection(user),
    }


async def login(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    ttl_minutes: int,
    correlation_id: str = "",
    audit_session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> dict[str, Any]:
    """Authenticate and open a session; on ANY failure persist a durable
    LOGIN_FAILED audit (Master M1 §11.2) before re-raising the same 401.

    The failure audit is written in an INDEPENDENT transaction because the 401
    rolls back the request unit of work (``deps.db_session``) — see
    :func:`_record_login_failure`. ``audit_session_factory`` is a test seam
    (default: the app session factory); the route never passes it.
    """
    try:
        return await _authenticate_or_raise(
            session,
            username=username,
            password=password,
            ttl_minutes=ttl_minutes,
            correlation_id=correlation_id,
        )
    except InvalidCredentialsError:
        await _record_login_failure(username, correlation_id, audit_session_factory)
        raise


async def logout(session: AsyncSession, *, token: str, correlation_id: str = "") -> dict[str, Any]:
    """Revoke the presented session. Re-revoking an already-closed session is
    a quiet no-op (changed=false, no audit noise) — logout must be safe to
    retry from a flaky client."""
    record = await auth_repo.get_session_by_token_hash(session, hash_token(token))
    if record is None:
        raise SessionInvalidError()
    if record.revoked_at is not None:
        return {"session_id": record.session_id, "revoked": True, "changed": False}

    record.revoked_at = datetime.now(UTC)
    audit_repo.add_audit_event(
        session,
        event_kind="auth.session_closed",
        actor_principal_id=record.user_id,
        actor_kind=ActorKind.HUMAN,
        target_entity_id=record.session_id,
        target_entity_type="auth_session",
        previous_state="active",
        new_state="revoked",
        correlation_id=correlation_id,
    )
    return {"session_id": record.session_id, "revoked": True, "changed": True}


async def _record_reauth_failure(
    user_id: str,
    purpose: str,
    correlation_id: str,
    audit_session_factory: async_sessionmaker[AsyncSession] | None,
) -> None:
    """Persist a durable ``auth.reauth_failed`` audit (F-21) that SURVIVES the
    request rollback that follows the 401 — mirrors :func:`_record_login_failure`.
    Unlike login, the actor is already authenticated (this is a re-auth STEP,
    not first authentication), so the target user id is not sensitive here."""
    factory = audit_session_factory or get_session_factory()
    try:
        async with factory() as audit_session:
            audit_repo.add_audit_event(
                audit_session,
                event_kind="auth.reauth_failed",
                actor_principal_id=user_id,
                actor_kind=ActorKind.HUMAN,
                target_entity_id=user_id,
                target_entity_type=_TARGET_TYPE,
                severity="warning",
                reason="invalid_credentials",
                correlation_id=correlation_id,
                metadata={"purpose": purpose},
            )
            await audit_session.commit()
    except Exception:
        log.exception("auth.reauth_failed_audit_write_failed", correlation_id=correlation_id)


async def reauthenticate(
    session: AsyncSession,
    *,
    user_id: str,
    password: str,
    purpose: str,
    ttl_minutes: int,
    correlation_id: str = "",
    audit_session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> dict[str, Any]:
    """Verify the ALREADY-authenticated human's password again and mint a
    short-lived, single-use, purpose-scoped proof token (F-21, doc 20 §8.3).

    Every rejection is the same 401 INVALID_CREDENTIALS (mirrors login's
    user-enumeration hardening — a timing pad on the "no credential" path) and
    a durable ``auth.reauth_failed`` audit survives the request rollback. The
    raw proof token is returned once here and persisted only as a SHA-256
    digest — the same shape as a session token (:func:`hash_token`).
    """
    user = await session.get(HumanUser, user_id)
    credential = await auth_repo.get_credential(session, user_id) if user is not None else None
    verified = (
        credential is not None
        and user is not None
        and user.status == "active"
        and user.deletion_state == DeletionState.ACTIVE
        and verify_password(credential.password_hash, password)
    )
    if not verified:
        if credential is None:
            verify_password(DUMMY_HASH, password)  # timing pad
        await _record_reauth_failure(user_id, purpose, correlation_id, audit_session_factory)
        raise InvalidCredentialsError()
    assert credential is not None  # narrows for mypy; implied by `verified`
    if needs_rehash(credential.password_hash):
        credential.password_hash = hash_password(password)

    proof = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    record = ReauthProof(
        proof_id=new_id("rap"),
        user_id=user_id,
        purpose=purpose,
        proof_hash=hash_token(proof),
        issued_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )
    session.add(record)

    audit_repo.add_audit_event(
        session,
        event_kind="auth.reauth_verified",
        actor_principal_id=user_id,
        actor_kind=ActorKind.HUMAN,
        target_entity_id=record.proof_id,
        target_entity_type="reauth_proof",
        new_state="issued",
        correlation_id=correlation_id,
        metadata={"purpose": purpose},
    )
    return {"reauth_proof": proof, "expires_at": record.expires_at.isoformat()}


async def consume_reauth_proof(
    session: AsyncSession, *, user_id: str, purpose: str, proof: str | None
) -> None:
    """Verify and CONSUME a re-authentication proof for a sensitive action
    (F-21). Raises :class:`ReauthRequiredError` for a missing/empty proof and
    :class:`ReauthProofInvalidError` for anything that fails verification
    (unknown, wrong purpose, wrong principal, expired, already used) — no
    arbitrary non-empty string can substitute for a real proof minted by
    :func:`reauthenticate`.

    Marks the proof used IN THE CALLER'S transaction so it is consumed
    atomically with the action it authorizes — a concurrent replay of the same
    token either loses the row lock race or observes ``used_at`` already set,
    never both callers succeeding.
    """
    if not proof or not proof.strip():
        raise ReauthRequiredError()
    record = await auth_repo.get_reauth_proof_by_hash(session, hash_token(proof.strip()))
    now = datetime.now(UTC)
    if (
        record is None
        or record.user_id != user_id
        or record.purpose != purpose
        or record.used_at is not None
        or record.expires_at <= now
    ):
        raise ReauthProofInvalidError()
    await session.refresh(record, with_for_update=True)
    if record.used_at is not None:  # re-check under the row lock (replay race)
        raise ReauthProofInvalidError()
    record.used_at = now


__all__ = [
    "bootstrap_admin_matches",
    "bootstrap_is_configured",
    "bootstrap_status",
    "consume_reauth_proof",
    "hash_token",
    "login",
    "logout",
    "reauthenticate",
    "sign_up",
]
