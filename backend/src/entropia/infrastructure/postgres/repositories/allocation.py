"""Portfolio / Equity Allocation repository (Stage 4a, doc 13 §8).

No commits — the command layer owns the transaction. L1 (parent-before-child):
``create_plan`` flushes the plan root before any entry/revision child is inserted,
and ``replace_entries`` / ``create_revision`` flush after adding children so ids
are available within the same transaction.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.allocation.enums import AllocationCurrency, CompoundingMode
from entropia.infrastructure.postgres.models import (
    PortfolioAllocationEntry,
    PortfolioAllocationPlan,
    PortfolioAllocationPlanRevision,
)
from entropia.shared.ids import new_id


async def get_plan_for_workspace(
    session: AsyncSession, workspace_entity_id: str
) -> PortfolioAllocationPlan | None:
    stmt = select(PortfolioAllocationPlan).where(
        PortfolioAllocationPlan.workspace_entity_id == workspace_entity_id
    )
    return (await session.execute(stmt)).scalars().first()


async def get_plan(session: AsyncSession, plan_id: str) -> PortfolioAllocationPlan | None:
    return await session.get(PortfolioAllocationPlan, plan_id)


async def create_plan(
    session: AsyncSession,
    *,
    workspace_entity_id: str,
    created_by_principal_id: str | None,
    enabled: bool,
    initial_capital_amount: Decimal | None,
    initial_capital_currency: AllocationCurrency | None,
    compounding_mode: CompoundingMode | None,
    reserve_cash_percent: Decimal | None,
    draft_fingerprint: str,
) -> PortfolioAllocationPlan:
    """Insert the plan root (row_version=1). Flushes before children (L1)."""
    plan = PortfolioAllocationPlan(
        plan_id=new_id("paplan"),
        workspace_entity_id=workspace_entity_id,
        enabled=enabled,
        initial_capital_amount=initial_capital_amount,
        initial_capital_currency=initial_capital_currency,
        compounding_mode=compounding_mode,
        reserve_cash_percent=reserve_cash_percent,
        draft_fingerprint=draft_fingerprint,
        row_version=1,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(plan)
    await session.flush()
    return plan


async def list_entries(session: AsyncSession, plan_id: str) -> list[PortfolioAllocationEntry]:
    stmt = (
        select(PortfolioAllocationEntry)
        .where(PortfolioAllocationEntry.plan_id == plan_id)
        .order_by(PortfolioAllocationEntry.position_index, PortfolioAllocationEntry.entry_id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def replace_entries(
    session: AsyncSession,
    *,
    plan_id: str,
    entries: list[dict[str, Any]],
) -> list[PortfolioAllocationEntry]:
    """Full-replace the plan's draft entries (the PUT draft is a wholesale upsert).

    ``entries`` items carry ``composition_item_id``, ``item_type`` (server-derived
    ``MainboardItemKind``), ``active`` and ``equity_share_percent`` (Decimal|None).
    """
    await session.execute(
        delete(PortfolioAllocationEntry).where(PortfolioAllocationEntry.plan_id == plan_id)
    )
    rows: list[PortfolioAllocationEntry] = []
    for position, entry in enumerate(entries):
        row = PortfolioAllocationEntry(
            entry_id=new_id("paentry"),
            plan_id=plan_id,
            composition_item_id=entry["composition_item_id"],
            item_type=entry["item_type"],
            active=entry["active"],
            equity_share_percent=entry["equity_share_percent"],
            position_index=position,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def create_revision(
    session: AsyncSession,
    *,
    plan_id: str,
    revision_no: int,
    config: dict[str, Any],
    config_hash: str,
    derived_amounts: dict[str, Any] | None,
    source_draft_row_version: int,
    created_by_principal_id: str | None,
) -> PortfolioAllocationPlanRevision:
    revision = PortfolioAllocationPlanRevision(
        plan_revision_id=new_id("parev"),
        plan_id=plan_id,
        revision_no=revision_no,
        config=config,
        config_hash=config_hash,
        derived_amounts=derived_amounts,
        source_draft_row_version=source_draft_row_version,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    await session.flush()
    return revision


async def max_revision_no(session: AsyncSession, plan_id: str) -> int:
    stmt = select(func.max(PortfolioAllocationPlanRevision.revision_no)).where(
        PortfolioAllocationPlanRevision.plan_id == plan_id
    )
    current = (await session.execute(stmt)).scalar_one_or_none()
    return int(current) if current is not None else 0
