"""Backtest RUN status + Result read models (Stage 5a, doc 15 §4, §7, §9.4).

Read-only projections. A Result detail is hydrated ONLY from ``result_id`` +
immutable artifacts — never from the current Mainboard form (doc 15 §8.5, §15).
Metric values come from the persisted ``metric_value`` rows; a missing metric is
surfaced with its non-computed availability, never 0 (L4). A soft-deleted Result
is treated as not found for the active projection (doc 15 §12).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.shared.errors import (
    BacktestResultNotFoundError,
    BacktestRunNotFoundError,
    CompositionNotFoundError,
)

_ACTIVE = "active"


async def get_backtest_run(
    session: AsyncSession,
    actor: Actor,
    *,
    run_id: str,
) -> dict[str, Any]:
    """Durable run status projection (doc 15 §4, §7). Reconnect-safe: state comes
    from the durable row, not any in-memory worker progress."""
    require_authenticated(actor)
    run = await bt_repo.get_run(session, run_id)
    if run is None:
        raise BacktestRunNotFoundError()
    await _ensure_can_view_workspace(session, actor, run.workspace_entity_id)
    return {
        "run_id": run.run_id,
        "composition_id": run.workspace_entity_id,
        "state": str(run.state),
        "manifest_hash": run.manifest_hash,
        "composition_fingerprint": run.composition_fingerprint,
        "composition_snapshot_id": run.composition_snapshot_id,
        "ready_report_id": run.ready_report_id,
        "retry_of_run_id": run.retry_of_run_id,
        "result_id": run.result_id,
        "failure_code": run.failure_code,
        "failure_message": run.failure_message,
        "job_id": run.job_id,
        "created_at": _iso(run.created_at),
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
    }


async def get_backtest_result(
    session: AsyncSession,
    actor: Actor,
    *,
    result_id: str,
) -> dict[str, Any]:
    """Immutable Result detail: summary + metrics + manifest projection (doc 15 §9.4)."""
    require_authenticated(actor)
    result = await bt_repo.get_result(session, result_id)
    if result is None or result.deletion_state != _ACTIVE:
        raise BacktestResultNotFoundError()
    await _ensure_can_view_workspace(session, actor, result.workspace_entity_id)

    summary = await bt_repo.get_summary(session, result_id)
    metrics = await bt_repo.list_metric_values(session, result_id)
    manifest_snapshot = await bt_repo.get_manifest_snapshot(session, result_id)
    counts = await bt_repo.count_artifacts(session, result_id)

    return {
        "result_id": result.result_id,
        "run_id": result.run_id,
        "composition_id": result.workspace_entity_id,
        "composition_fingerprint": result.composition_fingerprint,
        "manifest_hash": result.manifest_hash,
        "engine_version": result.engine_version,
        "summary": _summary_projection(summary),
        "metrics": [_metric_projection(metric) for metric in metrics],
        "manifest": _manifest_projection(manifest_snapshot),
        "artifact_counts": counts,
    }


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


async def _ensure_can_view_workspace(
    session: AsyncSession, actor: Actor, workspace_entity_id: str
) -> None:
    workspace = await mb_repo.get_workspace(session, workspace_entity_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    ensure_can_view(actor, owner_principal_id=workspace.owner_principal_id, visibility="private")


def _summary_projection(summary: Any) -> dict[str, Any] | None:
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


def _metric_projection(metric: Any) -> dict[str, Any]:
    return {
        "key": metric.metric_key,
        "label": metric.label,
        "unit": metric.unit,
        "value_format": metric.value_format,
        "value": _decimal_str(metric.value),
        "availability": str(metric.availability),
        "formula_version": metric.formula_version,
    }


def _manifest_projection(snapshot: Any) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    manifest = snapshot.manifest if isinstance(snapshot.manifest, dict) else {}
    return {
        "manifest_hash": snapshot.manifest_hash,
        "execution_key": snapshot.execution_key,
        "engine_version": snapshot.engine_version,
        "pinned_item_count": len(manifest.get("mainboard_items", [])),
    }


def _decimal_str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


__all__ = ["get_backtest_result", "get_backtest_run"]
