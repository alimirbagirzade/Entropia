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
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import ActorKind, DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuthSession,
    HumanCredential,
    HumanUser,
    Principal,
)
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import auth as auth_repo
from entropia.infrastructure.postgres.repositories import identity as identity_repo
from entropia.shared.errors import (
    InvalidCredentialsError,
    PasswordPolicyError,
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
) -> dict[str, Any]:
    """Create a human account. The role is ALWAYS User (M1 §4.1): any
    client-sent role never reaches this command — the route schema has no
    role field, so escalation via Sign Up is structurally impossible.

    First-Admin bootstrap (explicit operator opt-in): when the deployment sets
    ``ENTROPIA_BOOTSTRAP_ADMIN_EMAIL`` and the signup email matches it
    (case-normalized), the account is provisioned as Admin — ONLY while no
    active Admin exists (fail-closed otherwise). The role is still decided
    server-side; no client field can reach this branch."""
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
    if bootstrap_admin_matches(email, bootstrap_admin_email):
        # Same-tx race guard, mirroring the last-admin demote path: the shared
        # advisory lock serializes this count+decide section against concurrent
        # demotions AND concurrent bootstraps; a second concurrent qualifying
        # signup is additionally impossible via unique(human_users.email).
        await identity_repo.lock_admin_count(session)
        if await identity_repo.count_active_admins(session) == 0:
            role = Role.ADMIN
            bootstrapped = True

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


async def login(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    ttl_minutes: int,
    correlation_id: str = "",
) -> dict[str, Any]:
    """Verify the credential and open a revocable server-side session.

    Every rejection path is the same 401 INVALID_CREDENTIALS and every path
    runs exactly one argon2 verification (user-enumeration hardening). The
    raw token is returned once here and persisted only as a SHA-256 digest.
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


__all__ = ["bootstrap_admin_matches", "hash_token", "login", "logout", "sign_up"]
