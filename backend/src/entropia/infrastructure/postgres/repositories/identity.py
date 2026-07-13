"""Identity data access (M1)."""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import DeletionState, Role
from entropia.infrastructure.postgres.models import Agent, HumanUser

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
