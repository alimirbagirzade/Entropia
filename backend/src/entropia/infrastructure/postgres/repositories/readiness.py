"""Backtest Ready Check repository (Stage 4b, doc 14 §9.1).

No commits — the command layer owns the transaction. L1 (parent-before-child):
``create_report`` flushes the report root before any issue child is inserted so
the ``report_id`` FK is satisfiable within the same transaction. Read helpers
resolve the external import-batch evidence (Trade Log / Trading Signal) and the
enabled working items joined to their registry lifecycle state (for RC-16).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.readiness.issues import ReadinessIssue
from entropia.infrastructure.postgres.models import (
    CanonicalTradeRecordBatch,
    EntityRegistry,
    MainboardWorkingItem,
    NormalizedSignalEventRevision,
)
from entropia.infrastructure.postgres.models.readiness import (
    ReadinessIssueRow,
    ReadyCheckReport,
)
from entropia.shared.ids import new_id


async def create_report(
    session: AsyncSession,
    *,
    workspace_entity_id: str,
    composition_snapshot_id: str,
    composition_fingerprint: str,
    state: str,
    blocker_count: int,
    warning_count: int,
    pass_count: int,
    allocation_enabled: bool,
    checked_by_principal_id: str | None,
) -> ReadyCheckReport:
    """Insert the immutable report root. Flushes before issue children (L1)."""
    report = ReadyCheckReport(
        report_id=new_id("rcrpt"),
        workspace_entity_id=workspace_entity_id,
        composition_snapshot_id=composition_snapshot_id,
        composition_fingerprint=composition_fingerprint,
        state=state,
        blocker_count=blocker_count,
        warning_count=warning_count,
        pass_count=pass_count,
        allocation_enabled=1 if allocation_enabled else 0,
        checked_by_principal_id=checked_by_principal_id,
    )
    session.add(report)
    await session.flush()
    return report


async def add_issues(
    session: AsyncSession,
    *,
    report_id: str,
    issues: Sequence[ReadinessIssue],
) -> list[ReadinessIssueRow]:
    """Insert immutable issue children in order. Flushes so ids are available."""
    rows: list[ReadinessIssueRow] = []
    for position, issue in enumerate(issues):
        row = ReadinessIssueRow(
            issue_id=new_id("rcissue"),
            report_id=report_id,
            code=str(issue.code),
            severity=str(issue.severity),
            scope=str(issue.scope),
            field_path=issue.field_path,
            scope_id=issue.scope_id,
            message=issue.message,
            remediation=issue.remediation,
            position_index=position,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def get_report(session: AsyncSession, report_id: str) -> ReadyCheckReport | None:
    return await session.get(ReadyCheckReport, report_id)


async def list_issues(session: AsyncSession, report_id: str) -> list[ReadinessIssueRow]:
    stmt = (
        select(ReadinessIssueRow)
        .where(ReadinessIssueRow.report_id == report_id)
        .order_by(ReadinessIssueRow.position_index, ReadinessIssueRow.issue_id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def latest_report_for_workspace(
    session: AsyncSession, workspace_entity_id: str
) -> ReadyCheckReport | None:
    """The most recent report for a composition (currentness is recomputed by the
    caller against the current fingerprint; this is only "newest by time")."""
    stmt = (
        select(ReadyCheckReport)
        .where(ReadyCheckReport.workspace_entity_id == workspace_entity_id)
        .order_by(ReadyCheckReport.created_at.desc(), ReadyCheckReport.report_id.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def list_enabled_items_with_root_state(
    session: AsyncSession, workspace_entity_id: str
) -> list[tuple[MainboardWorkingItem, bool]]:
    """Every ENABLED working item of a workspace + whether its work-object root is
    ACTIVE (soft-deleted roots yield ``available=False`` → RC-16 blocker)."""
    stmt = (
        select(MainboardWorkingItem, EntityRegistry.deletion_state)
        .join(
            EntityRegistry,
            EntityRegistry.entity_id == MainboardWorkingItem.work_object_root_id,
            isouter=True,
        )
        .where(
            MainboardWorkingItem.workspace_entity_id == workspace_entity_id,
            MainboardWorkingItem.is_enabled.is_(True),
        )
        .order_by(MainboardWorkingItem.position_index, MainboardWorkingItem.item_id)
    )
    rows = (await session.execute(stmt)).all()
    return [(item, state == DeletionState.ACTIVE) for item, state in rows]


async def resolve_trade_log_batch(
    session: AsyncSession, revision_id: str
) -> CanonicalTradeRecordBatch | None:
    """The canonical trade-record batch pinned to a Trade Log revision, if any."""
    stmt = select(CanonicalTradeRecordBatch).where(
        CanonicalTradeRecordBatch.work_object_revision_id == revision_id
    )
    return (await session.execute(stmt)).scalars().first()


async def resolve_signal_revision(
    session: AsyncSession, revision_id: str
) -> NormalizedSignalEventRevision | None:
    """The normalized signal-event revision pinned to a Trading Signal revision."""
    stmt = select(NormalizedSignalEventRevision).where(
        NormalizedSignalEventRevision.work_object_revision_id == revision_id
    )
    return (await session.execute(stmt)).scalars().first()


__all__ = [
    "add_issues",
    "create_report",
    "get_report",
    "latest_report_for_workspace",
    "list_enabled_items_with_root_state",
    "list_issues",
    "resolve_signal_revision",
    "resolve_trade_log_batch",
]
