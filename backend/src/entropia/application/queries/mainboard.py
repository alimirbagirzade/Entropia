"""Mainboard read-side query: the default workspace projection (doc 01 §4, §9).

The Mainboard is authentication-gated: a Guest gets no workspace at all — the
query raises UNAUTHENTICATED before resolving or auto-creating anything (AT#1, no
leak). For an authenticated actor the default workspace is resolved owner-scoped;
if none exists yet it is auto-created (FK-safe registry Root -> flush -> detail)
with a kind derived from the actor (``agent_research`` for an Agent, else
``human_default``). "One active default per human owner" is APP-ENFORCED here
(query-before-create) — there is no cross-table DB uniqueness constraint
(follow-up).

The item list is the ACTIVE projection: items whose work object root is
soft-deleted are filtered out server-side (they remain rows, but never appear),
ordered by ``position_index``.

Readiness and latest-result are REAL projections (GAP-05, doc 01 §5.1/§9.5, doc 15
§9.4): ``ready_summary`` reflects the composition's current readiness (the
recomputed-currentness Ready Check projection — ``not_checked`` when never run,
``stale``/``superseded`` when the composition moved past the report), and
``latest_result_summary`` carries the most recent active succeeded Result for this
composition, flagged ``snapshot_differs`` when the live composition fingerprint has
moved past the result's pinned fingerprint. A result is never fabricated (null when
none exists) and never silently overwritten (doc 15 §9.4); the badge currentness is
recomputed here, never stored.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.queries.readiness_check import get_current_readiness
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.mainboard.composition import CompositionMember, composition_hash
from entropia.domain.mainboard.enums import WorkspaceKind
from entropia.infrastructure.postgres.models import (
    MainboardWorkingItem,
    MainboardWorkspace,
    ResultSummary,
)
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo


async def get_default_mainboard(session: AsyncSession, actor: Actor) -> dict[str, Any]:
    """Resolve (or auto-create) the actor's default Mainboard workspace projection.

    Guests are rejected with 401 before any read/create. The returned shape is the
    workspace header + the active item projection + the real readiness and
    latest-result projections (doc 01 §9.5, doc 15 §9.4).
    """
    require_authenticated(actor)
    detail = await mb_repo.find_default_workspace(
        session, owner_principal_id=actor.principal_id or ""
    )
    if detail is None:
        detail = await _auto_create_default(session, actor)

    items = await mb_repo.list_active_items(session, detail.entity_id)
    current_fingerprint = _composition_fingerprint(items)
    ready = await get_current_readiness(session, actor, composition_id=detail.entity_id)
    latest_result = await _latest_result_projection(session, detail.entity_id, current_fingerprint)
    return {
        "workspace_id": detail.entity_id,
        "workspace_kind": str(detail.workspace_kind),
        "composition_hash": detail.composition_hash,
        "row_version": detail.row_version,
        "items": [_item_projection(item) for item in items],
        "ready_summary": {
            "state": ready["state"],
            "report_id": ready.get("report_id"),
        },
        "latest_result_summary": latest_result,
    }


async def _auto_create_default(session: AsyncSession, actor: Actor) -> MainboardWorkspace:
    """Create the actor's default workspace (FK-safe Root -> flush -> detail)."""
    workspace_kind = WorkspaceKind.AGENT_RESEARCH if actor.is_agent else WorkspaceKind.HUMAN_DEFAULT
    _root, detail = await mb_repo.create_workspace(
        session,
        owner_principal_id=actor.principal_id,
        created_by_principal_id=actor.principal_id,
        workspace_kind=workspace_kind,
        title=None,
        is_default=True,
    )
    return detail


def _composition_fingerprint(items: Sequence[MainboardWorkingItem]) -> str:
    """Hash of the ENABLED item composition — the live fingerprint used to flag a
    stale latest-result snapshot. Mirrors the Ready Check currentness recompute
    (``readiness_check._current_fingerprint``) so the badge and the ready state
    agree on what "current composition" means.
    """
    members = [
        CompositionMember(
            kind=item.item_kind,
            root_id=item.work_object_root_id,
            revision_id=item.pinned_revision_id,
        )
        for item in items
        if item.is_enabled
    ]
    return composition_hash(members)


async def _latest_result_projection(
    session: AsyncSession, workspace_entity_id: str, current_fingerprint: str
) -> dict[str, Any] | None:
    """The most recent active succeeded Result for this composition, or None.

    ``snapshot_differs`` is recomputed here (never stored): true when the live
    composition fingerprint has moved past the result's pinned fingerprint (doc 15
    §9.4 — the row stays readable, is never treated as a current test of the
    modified composition, and is clearly labelled).
    """
    result = await bt_repo.latest_result_for_workspace(session, workspace_entity_id)
    if result is None:
        return None
    summary = await bt_repo.get_summary(session, result.result_id)
    return {
        "result_id": result.result_id,
        "manifest_hash": result.manifest_hash,
        "composition_fingerprint": result.composition_fingerprint,
        "engine_version": result.engine_version,
        "created_at": _iso(result.created_at),
        "snapshot_differs": result.composition_fingerprint != current_fingerprint,
        "summary": _result_summary_projection(summary),
    }


def _result_summary_projection(summary: ResultSummary | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    return {
        "symbol": summary.symbol,
        "timeframe": summary.timeframe,
        "period_start": summary.period_start,
        "period_end": summary.period_end,
        "total_trades": summary.total_trades,
        "headline": summary.headline,
    }


def _iso(value: datetime) -> str:
    return value.isoformat()


def _item_projection(item: MainboardWorkingItem) -> dict[str, Any]:
    return {
        "item_id": item.item_id,
        "item_kind": str(item.item_kind),
        "work_object_root_id": item.work_object_root_id,
        "pinned_revision_id": item.pinned_revision_id,
        "position_index": item.position_index,
        "is_enabled": item.is_enabled,
        "display_label_override": item.display_label_override,
        "row_version": item.row_version,
    }


__all__ = ["get_default_mainboard"]
