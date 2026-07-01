"""Backtest Ready Check read model (Stage 4b, doc 14 §4, §9.1).

Reports/issues are immutable; currentness is NEVER stored — it is recomputed here
by comparing the report's pinned ``composition_fingerprint`` against the current
composition fingerprint (doc 14 §12.2 Trash rule, §13 latest-revisions note).
A report is STALE when the composition changed, SUPERSEDED when a newer report
exists for the same still-current composition, else its stored terminal state.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.mainboard.composition import CompositionMember, composition_hash
from entropia.domain.readiness.enums import ReadinessState
from entropia.domain.readiness.validators import is_stale
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import readiness as readiness_repo
from entropia.shared.errors import (
    CompositionNotFoundError,
    ReadinessReportNotFoundError,
)


async def get_readiness_report(
    session: AsyncSession,
    actor: Actor,
    *,
    report_id: str,
) -> dict[str, Any]:
    """Return an immutable report + issues + the RECOMPUTED effective state."""
    require_authenticated(actor)
    report = await readiness_repo.get_report(session, report_id)
    if report is None:
        raise ReadinessReportNotFoundError()

    workspace = await mb_repo.get_workspace(session, report.workspace_entity_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    ensure_can_view(actor, owner_principal_id=workspace.owner_principal_id, visibility="private")

    current_fingerprint = await _current_fingerprint(session, report.workspace_entity_id)
    latest = await readiness_repo.latest_report_for_workspace(session, report.workspace_entity_id)
    stale = is_stale(report.composition_fingerprint, current_fingerprint)
    superseded = latest is not None and latest.report_id != report.report_id
    effective_state = _effective_state(str(report.state), stale=stale, superseded=superseded)

    issues = await readiness_repo.list_issues(session, report_id)
    return {
        "report_id": report.report_id,
        "composition_id": report.workspace_entity_id,
        "snapshot_id": report.composition_snapshot_id,
        "composition_fingerprint": report.composition_fingerprint,
        "current_fingerprint": current_fingerprint,
        "stored_state": str(report.state),
        "state": effective_state,
        "is_current": not stale and not superseded,
        "summary": {
            "blocker_count": report.blocker_count,
            "warning_count": report.warning_count,
            "pass_count": report.pass_count,
            "allocation_enabled": bool(report.allocation_enabled),
        },
        "issues": [
            {
                "code": row.code,
                "severity": str(row.severity),
                "scope": str(row.scope),
                "field_path": row.field_path,
                "scope_id": row.scope_id,
                "message": row.message,
                "remediation": row.remediation,
            }
            for row in issues
        ],
    }


async def get_current_readiness(
    session: AsyncSession,
    actor: Actor,
    *,
    composition_id: str,
) -> dict[str, Any]:
    """Return the composition's latest report projection, or NOT_CHECKED state."""
    require_authenticated(actor)
    workspace = await mb_repo.get_workspace(session, composition_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    ensure_can_view(actor, owner_principal_id=workspace.owner_principal_id, visibility="private")

    latest = await readiness_repo.latest_report_for_workspace(session, composition_id)
    if latest is None:
        return {
            "composition_id": composition_id,
            "state": str(ReadinessState.NOT_CHECKED),
            "report_id": None,
        }
    return await get_readiness_report(session, actor, report_id=latest.report_id)


async def _current_fingerprint(session: AsyncSession, workspace_entity_id: str) -> str:
    items = await mb_repo.list_active_items(session, workspace_entity_id)
    enabled = [item for item in items if item.is_enabled]
    members = [
        CompositionMember(
            kind=item.item_kind,
            root_id=item.work_object_root_id,
            revision_id=item.pinned_revision_id,
        )
        for item in enabled
    ]
    return composition_hash(members)


def _effective_state(stored: str, *, stale: bool, superseded: bool) -> str:
    if stale:
        return str(ReadinessState.STALE)
    if superseded:
        return str(ReadinessState.SUPERSEDED)
    return stored


__all__ = ["get_current_readiness", "get_readiness_report"]
