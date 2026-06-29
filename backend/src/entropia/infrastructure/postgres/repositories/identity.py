"""Identity data access (M1)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import DeletionState, Role
from entropia.infrastructure.postgres.models import Agent, HumanUser


async def get_human_user(session: AsyncSession, user_id: str) -> HumanUser | None:
    return await session.get(HumanUser, user_id)


async def get_agent(session: AsyncSession, agent_id: str) -> Agent | None:
    return await session.get(Agent, agent_id)


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
