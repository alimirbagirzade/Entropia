"""Identity data access (M1)."""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import DeletionState, Role
from entropia.infrastructure.postgres.models import Agent, HumanUser
from entropia.infrastructure.postgres.models.auth import HumanCredential

# Fixed key for the transaction-scoped advisory lock that serializes the
# last-active-Admin critical section (count + check + demote). Any stable app-wide
# integer works; released automatically at commit/rollback.
_ADMIN_COUNT_LOCK_KEY = 6_2000_1


async def get_human_user(session: AsyncSession, user_id: str) -> HumanUser | None:
    return await session.get(HumanUser, user_id)


async def get_active_user_by_email(session: AsyncSession, email: str) -> HumanUser | None:
    """Resolve an ACTIVE human user by exact (case-normalized) email.

    The email is stored verbatim but matched case-insensitively so a share
    recipient is found regardless of the casing the owner typed. A disabled or
    soft-deleted account never resolves (it must not become a share target)."""
    normalized = email.strip().lower()
    if not normalized:
        return None
    stmt = select(HumanUser).where(
        func.lower(HumanUser.email) == normalized,
        HumanUser.status == "active",
        HumanUser.deletion_state == DeletionState.ACTIVE,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_agent(session: AsyncSession, agent_id: str) -> Agent | None:
    return await session.get(Agent, agent_id)


async def lock_admin_count(session: AsyncSession) -> None:
    """Serialize the last-admin critical section against concurrent demotions.

    Without this, two transactions each locking a *different* Admin row can both read
    ``count_active_admins() == 2`` and both demote, leaving zero Admins (TOCTOU). A
    transaction-scoped advisory lock is deadlock-free (single shared key) and released
    at commit/rollback. Call this BEFORE ``count_active_admins`` on the demote path."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADMIN_COUNT_LOCK_KEY})


async def count_active_admins(session: AsyncSession) -> int:
    """Count active Admin ROLE ROWS — regardless of whether they can log in.

    This is the dev-mode operational count: under ``AUTH_MODE=dev`` an Admin is
    reachable through ``X-Actor-Id`` with no password, so a credentialless Admin
    role row IS an operator. Session mode must NOT use this count (PROV-02/03):
    a role row without a credential is nobody who can log in — see
    :func:`count_login_capable_admins`."""
    stmt = (
        select(func.count())
        .select_from(HumanUser)
        .where(
            HumanUser.current_role == Role.ADMIN,
            HumanUser.status == "active",
            HumanUser.deletion_state == DeletionState.ACTIVE,
        )
    )
    return int((await session.execute(stmt)).scalar_one())


async def count_login_capable_admins(session: AsyncSession) -> int:
    """Count active Admins who can actually LOG IN — the session-mode operational
    Admin count (audit PROV-02/03).

    An administrator who can recover or operate a session-mode installation is an
    active/non-deleted :class:`HumanUser` with role Admin AND a stored
    :class:`HumanCredential` (one per user — its PK is ``user_id``, so the inner
    join yields at most one row per Admin and never inflates the count). The
    legacy credentialless ``user_admin`` seed has a role row but no credential, so
    it is correctly excluded: it can neither log in nor unblock a real install."""
    stmt = (
        select(func.count())
        .select_from(HumanUser)
        .join(HumanCredential, HumanCredential.user_id == HumanUser.user_id)
        .where(
            HumanUser.current_role == Role.ADMIN,
            HumanUser.status == "active",
            HumanUser.deletion_state == DeletionState.ACTIVE,
        )
    )
    return int((await session.execute(stmt)).scalar_one())


async def count_operational_admins(session: AsyncSession, *, auth_mode: str) -> int:
    """The operational Admin count for the active authentication mode — the ONE
    rule both first-Admin bootstrap and last-Admin protection must share (audit
    PROV-02/03, §6.5).

    * ``session`` mode → :func:`count_login_capable_admins` (credentialed Admins);
      a credentialless legacy role row is not an operator here.
    * ``dev`` (or any non-session) mode → :func:`count_active_admins` (role rows);
      an ``X-Actor-Id`` Admin needs no credential to operate.

    The auth mode is passed in (never read from settings here) so this layer stays
    free of configuration and the rule is explicit and unit-testable at each call
    site. Call under :func:`lock_admin_count` on any count-and-decide path."""
    if auth_mode == "session":
        return await count_login_capable_admins(session)
    return await count_active_admins(session)
