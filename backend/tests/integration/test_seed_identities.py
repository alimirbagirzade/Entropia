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

from entropia.apps.seed import (
    DEFAULT_ADMIN_ID,
    DEFAULT_AGENT_ID,
    seed_capabilities,
    seed_identities,
)
from entropia.domain.capability.enums import BASELINE_CAPABILITY_KEYS, CapabilityState
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import Agent, HumanUser, Principal
from entropia.infrastructure.postgres.repositories import capability as capability_repo

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


async def test_seed_capabilities_on_fresh_database(session: AsyncSession) -> None:
    """The seed entrypoint provisions every baseline Future Dev key as PLACEHOLDER.

    Without this wiring the Capability Registry is empty on a fresh database, so
    each Future Dev subpage reports its key as "Not registered" (doc 22 §4/§9).
    """
    await seed_capabilities(session)
    await session.commit()

    rows = await capability_repo.list_capabilities(session)
    assert {row.capability_key for row in rows} == set(BASELINE_CAPABILITY_KEYS)
    assert all(row.lifecycle_state == CapabilityState.PLACEHOLDER for row in rows)


async def test_seed_capabilities_is_idempotent(session: AsyncSession) -> None:
    """A second run neither errors nor duplicates the baseline registry rows."""
    await seed_capabilities(session)
    await session.commit()
    await seed_capabilities(session)
    await session.commit()

    rows = await capability_repo.list_capabilities(session)
    assert len(rows) == len(BASELINE_CAPABILITY_KEYS)
