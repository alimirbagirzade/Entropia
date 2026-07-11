"""Seed identity bootstrap — fresh-database FK ordering + idempotency.

Regression for the local-setup flow (README step: ``python -m entropia.apps.seed``):
on a fresh schema the unit of work has no relationship()-derived dependency
between Principal and HumanUser/Agent, so a single batched flush could emit the
FK-dependent child INSERT before the principals row and abort the whole seed.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.apps.seed import DEFAULT_ADMIN_ID, DEFAULT_AGENT_ID, seed_identities
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import Agent, HumanUser, Principal

pytestmark = pytest.mark.asyncio


async def test_seed_identities_on_fresh_database(session: AsyncSession) -> None:
    """Both identities land on an empty schema (principal precedes FK child)."""
    await seed_identities(session)
    await session.commit()

    admin_principal = await session.get(Principal, DEFAULT_ADMIN_ID)
    assert admin_principal is not None
    assert admin_principal.principal_type == PrincipalType.HUMAN

    admin = await session.get(HumanUser, DEFAULT_ADMIN_ID)
    assert admin is not None
    assert admin.current_role == Role.ADMIN

    agent_principal = await session.get(Principal, DEFAULT_AGENT_ID)
    assert agent_principal is not None
    assert agent_principal.principal_type == PrincipalType.AGENT

    agent = await session.get(Agent, DEFAULT_AGENT_ID)
    assert agent is not None
    assert agent.enabled is True


async def test_seed_identities_is_idempotent(session: AsyncSession) -> None:
    """A second run neither errors nor duplicates rows."""
    await seed_identities(session)
    await session.commit()
    await seed_identities(session)
    await session.commit()

    principal_count = await session.scalar(select(func.count()).select_from(Principal))
    assert principal_count == 2
    human_count = await session.scalar(select(func.count()).select_from(HumanUser))
    assert human_count == 1
    agent_count = await session.scalar(select(func.count()).select_from(Agent))
    assert agent_count == 1
