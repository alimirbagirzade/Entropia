"""Backtest RUN + Result persistence (Stage 5a, doc 15 §9.1).

No commits — the command/job layer owns the transaction. L1 (parent-before-child):
``create_result`` flushes the ``backtest_result`` root BEFORE any summary / metric
/ artifact child is inserted, so every child ``result_id`` FK is satisfiable in the
same transaction (SQLAlchemy does not order INSERTs from a bare ForeignKey).
``has_active_run_for_root`` powers the 3a ``_assert_not_in_active_run`` guard by
scanning ACTIVE runs' manifests for a pinned root (doc 15 wiring of
OBJECT_IN_ACTIVE_RUN).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.engine import EngineOutput
from entropia.domain.backtest.enums import RUN_ACTIVE_STATES
from entropia.domain.backtest.metrics import MetricValue
from entropia.infrastructure.postgres.models.backtest import (
    BacktestResult,
    BacktestRun,
    BacktestRunManifest,
    DiagnosticArtifact,
    MetricValueRow,
    ResultEquityPoint,
    ResultManifestSnapshot,
    ResultSummary,
    SignalEventRow,
    TradeLedgerRow,
)
from entropia.shared.ids import new_id

_SUMMARY_JSON_KEYS = (
    "symbol",
    "timeframe",
    "initial_capital",
    "final_equity",
    "net_profit",
    "net_profit_pct",
    "max_drawdown",
    "max_drawdown_pct",
    "romad",
    "win_rate",
    "profit_factor",
    "total_trades",
    "total_stops",
    "max_stop_streak",
    "total_winning_trades",
)


def _jsonable(value: Any) -> Any:
    """Recursively render Decimals as strings so a dict is JSONB-serializable."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


# --------------------------------------------------------------------------- #
# RUN + manifest                                                              #
# --------------------------------------------------------------------------- #


async def create_run(
    session: AsyncSession,
    *,
    run_id: str,
    workspace_entity_id: str,
    composition_snapshot_id: str,
    composition_fingerprint: str,
    manifest_id: str,
    manifest_hash: str,
    state: str,
    requested_by_principal_id: str | None,
    ready_report_id: str | None,
    retry_of_run_id: str | None,
    correlation_id: str | None,
) -> BacktestRun:
    """Insert a BacktestRun (QUEUED). Flushes so the run_id is available."""
    run = BacktestRun(
        run_id=run_id,
        workspace_entity_id=workspace_entity_id,
        composition_snapshot_id=composition_snapshot_id,
        composition_fingerprint=composition_fingerprint,
        manifest_id=manifest_id,
        manifest_hash=manifest_hash,
        state=state,
        requested_by_principal_id=requested_by_principal_id,
        ready_report_id=ready_report_id,
        retry_of_run_id=retry_of_run_id,
        correlation_id=correlation_id,
        row_version=1,
    )
    session.add(run)
    await session.flush()
    return run


async def create_manifest(
    session: AsyncSession,
    *,
    manifest_id: str,
    run_id: str,
    manifest_hash: str,
    execution_key: str,
    composition_snapshot_id: str,
    composition_fingerprint: str,
    engine_version: str,
    manifest: dict[str, Any],
) -> BacktestRunManifest:
    """Insert the immutable run manifest. Flushes so the manifest_id is available."""
    row = BacktestRunManifest(
        manifest_id=manifest_id,
        run_id=run_id,
        manifest_hash=manifest_hash,
        execution_key=execution_key,
        composition_snapshot_id=composition_snapshot_id,
        composition_fingerprint=composition_fingerprint,
        engine_version=engine_version,
        manifest=manifest,
    )
    session.add(row)
    await session.flush()
    return row


async def get_run(session: AsyncSession, run_id: str) -> BacktestRun | None:
    return await session.get(BacktestRun, run_id)


async def get_manifest_by_run(session: AsyncSession, run_id: str) -> BacktestRunManifest | None:
    stmt = select(BacktestRunManifest).where(BacktestRunManifest.run_id == run_id)
    return (await session.execute(stmt)).scalars().first()


async def has_active_run_for_root(session: AsyncSession, root_id: str) -> bool:
    """True iff any QUEUED/PROVISIONING/RUNNING run pins ``root_id`` in its manifest.

    Active runs are few; iterating their manifests in Python keeps this portable
    (no JSONB-operator dependency) and correct for the OBJECT_IN_ACTIVE_RUN guard.
    """
    stmt = (
        select(BacktestRunManifest.manifest)
        .join(BacktestRun, BacktestRun.run_id == BacktestRunManifest.run_id)
        .where(BacktestRun.state.in_([s.value for s in RUN_ACTIVE_STATES]))
    )
    for (manifest,) in (await session.execute(stmt)).all():
        items = manifest.get("mainboard_items", []) if isinstance(manifest, dict) else []
        if any(str(item.get("root_id")) == root_id for item in items):
            return True
    return False


# --------------------------------------------------------------------------- #
# Result materialization (L1 FK-safe)                                         #
# --------------------------------------------------------------------------- #


async def create_result(
    session: AsyncSession,
    *,
    run: BacktestRun,
    manifest: BacktestRunManifest,
    engine_output: EngineOutput,
    metric_values: list[MetricValue],
) -> BacktestResult:
    """Materialize the immutable Result + summary + metrics + artifacts (CR-03).

    The ``backtest_result`` root is flushed BEFORE any child so every FK is
    satisfiable in-transaction (L1).
    """
    result_id = new_id("btres")
    result = BacktestResult(
        result_id=result_id,
        run_id=run.run_id,
        manifest_id=manifest.manifest_id,
        manifest_hash=manifest.manifest_hash,
        workspace_entity_id=run.workspace_entity_id,
        composition_fingerprint=run.composition_fingerprint,
        engine_version=manifest.engine_version,
        deletion_state="active",
        row_version=1,
        created_by_principal_id=run.requested_by_principal_id,
    )
    session.add(result)
    await session.flush()

    summary = engine_output.summary
    session.add(
        ResultSummary(
            summary_id=new_id("btsum"),
            result_id=result_id,
            symbol=summary.get("symbol"),
            timeframe=summary.get("timeframe"),
            period_start=None,
            period_end=None,
            total_trades=int(summary.get("total_trades") or 0),
            headline={k: _jsonable(summary.get(k)) for k in _SUMMARY_JSON_KEYS},
        )
    )
    for metric in metric_values:
        session.add(
            MetricValueRow(
                metric_value_id=new_id("btmv"),
                result_id=result_id,
                metric_key=metric.key,
                label=metric.label,
                unit=metric.unit,
                value_format=metric.value_format,
                value=metric.value,
                availability=metric.availability,
                formula_version=metric.formula_version,
                position_index=metric.position_index,
            )
        )
    for point in engine_output.equity_points:
        session.add(
            ResultEquityPoint(
                point_id=new_id("bteq"),
                result_id=result_id,
                seq=point.seq,
                timestamp=point.timestamp,
                equity=point.equity,
                drawdown=point.drawdown,
                exposure=point.exposure,
            )
        )
    for trade in engine_output.trades:
        session.add(
            TradeLedgerRow(
                trade_row_id=new_id("bttr"),
                result_id=result_id,
                seq=trade.seq,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                direction=trade.direction,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                pnl=trade.pnl,
                exit_reason=trade.exit_reason,
            )
        )
    for event in engine_output.signal_events:
        session.add(
            SignalEventRow(
                signal_event_id=new_id("btse"),
                result_id=result_id,
                seq=event.seq,
                event_time=event.event_time,
                event_type=event.event_type,
                direction=event.direction,
                detail=_jsonable(event.detail),
            )
        )
    session.add(
        DiagnosticArtifact(
            diagnostic_id=new_id("btdiag"),
            result_id=result_id,
            kind="run_diagnostics",
            content=_jsonable(engine_output.diagnostics),
        )
    )
    session.add(
        ResultManifestSnapshot(
            snapshot_id=new_id("btms"),
            result_id=result_id,
            manifest_hash=manifest.manifest_hash,
            execution_key=manifest.execution_key,
            engine_version=manifest.engine_version,
            manifest=manifest.manifest,
        )
    )
    await session.flush()
    return result


# --------------------------------------------------------------------------- #
# Result read helpers                                                         #
# --------------------------------------------------------------------------- #


async def get_result(session: AsyncSession, result_id: str) -> BacktestResult | None:
    return await session.get(BacktestResult, result_id)


async def get_summary(session: AsyncSession, result_id: str) -> ResultSummary | None:
    stmt = select(ResultSummary).where(ResultSummary.result_id == result_id)
    return (await session.execute(stmt)).scalars().first()


async def list_metric_values(session: AsyncSession, result_id: str) -> list[MetricValueRow]:
    stmt = (
        select(MetricValueRow)
        .where(MetricValueRow.result_id == result_id)
        .order_by(MetricValueRow.position_index, MetricValueRow.metric_key)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_manifest_snapshot(
    session: AsyncSession, result_id: str
) -> ResultManifestSnapshot | None:
    stmt = select(ResultManifestSnapshot).where(ResultManifestSnapshot.result_id == result_id)
    return (await session.execute(stmt)).scalars().first()


async def count_artifacts(session: AsyncSession, result_id: str) -> dict[str, int]:
    """Cheap projection counts for the collapsed Result row (heavy pagination is a
    later slice)."""
    from sqlalchemy import func

    counts: dict[str, int] = {}
    for label, model in (
        ("equity_points", ResultEquityPoint),
        ("trades", TradeLedgerRow),
        ("signal_events", SignalEventRow),
    ):
        stmt = select(func.count()).select_from(model).where(model.result_id == result_id)
        counts[label] = int((await session.execute(stmt)).scalar_one())
    return counts


__all__ = [
    "count_artifacts",
    "create_manifest",
    "create_result",
    "create_run",
    "get_manifest_by_run",
    "get_manifest_snapshot",
    "get_result",
    "get_run",
    "get_summary",
    "has_active_run_for_root",
    "list_metric_values",
]
