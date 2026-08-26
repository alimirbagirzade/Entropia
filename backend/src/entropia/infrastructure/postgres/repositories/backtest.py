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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.artifacts import (
    ARTIFACT_CHECKSUM_SCHEMA_VERSION,
    ArtifactType,
    compute_artifact_checksum,
)
from entropia.domain.backtest.engine import EngineOutput
from entropia.domain.backtest.enums import RUN_ACTIVE_STATES, BacktestRunState, RunEventType
from entropia.domain.backtest.metrics import MetricValue
from entropia.domain.backtest.portfolio_mode import (
    UNIFIED_MANIFEST_KEY as PORTFOLIO_SIMULATION_KEY,
)
from entropia.domain.backtest.portfolio_mode import (
    UNIFIED_MANIFEST_VERSION_FIELD,
)
from entropia.infrastructure.postgres.models.backtest import (
    BacktestResult,
    BacktestRun,
    BacktestRunEvent,
    BacktestRunManifest,
    DiagnosticArtifact,
    FilteredEventRow,
    MetricValueRow,
    ResultArtifactChecksum,
    ResultEquityPoint,
    ResultManifestSnapshot,
    ResultSummary,
    SignalEventRow,
    TradeLedgerRow,
)
from entropia.infrastructure.postgres.repositories.result_artifacts import checksum_rows
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


async def get_run(
    session: AsyncSession, run_id: str, *, for_update: bool = False
) -> BacktestRun | None:
    """Load a run; ``for_update`` takes the row lock in the SAME query (O-06).

    The worker and ``cancel_backtest_run`` both serialize on this lock, which is
    what stops a cancel from being silently overwritten by a worker claiming the
    run (and vice versa). Locking in the initial read rather than re-selecting
    afterwards keeps the worker at its original single round trip."""
    if for_update:
        return await session.get(BacktestRun, run_id, with_for_update=True)
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
# Run stage events (O-05, doc 15 §7, §8.3, §11, §12)                          #
# --------------------------------------------------------------------------- #


async def latest_run_sequence(session: AsyncSession, run_id: str) -> int:
    """Highest ``sequence_no`` written for the run so far (0 when it has none)."""
    stmt = select(func.coalesce(func.max(BacktestRunEvent.sequence_no), 0)).where(
        BacktestRunEvent.run_id == run_id
    )
    return int((await session.execute(stmt)).scalar_one())


async def record_run_event(
    session: AsyncSession,
    *,
    run_id: str,
    event_type: RunEventType,
    state: BacktestRunState,
    previous_state: BacktestRunState | None = None,
    correlation_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> BacktestRunEvent:
    """Append ONE stage event, taking the next per-run ``sequence_no``.

    L1 (parent-before-child): the caller always holds a persisted ``backtest_run``
    row — the worker loaded it and admission flushed it — so the FK is satisfiable
    when this INSERT flushes. The sequence is allocated from the run's own MAX; a
    concurrent second writer for the SAME run does not silently interleave, it
    violates ``UNIQUE(run_id, sequence_no)`` and raises. That constraint is also
    what makes doc 15 §7 de-duplication real: one logical event keeps one sequence
    forever, so a reconnecting reader keyed on ``sequence_no`` never double-counts
    a redelivered event.
    """
    event = BacktestRunEvent(
        event_id=new_id("brev"),
        run_id=run_id,
        sequence_no=await latest_run_sequence(session, run_id) + 1,
        event_type=event_type,
        previous_state=previous_state,
        state=state,
        correlation_id=correlation_id,
        detail=_jsonable(detail) if detail is not None else None,
    )
    session.add(event)
    await session.flush()
    return event


async def list_run_events(
    session: AsyncSession,
    run_id: str,
    *,
    after_sequence: int = 0,
    limit: int,
) -> list[BacktestRunEvent]:
    """Events strictly after ``after_sequence``, ascending — the reconnect replay.

    Ascending + strictly-greater is the whole contract (doc 15 §11 "Reconnect by
    event sequence"): a client that resumes from the last sequence it saw gets
    every later event exactly once and nothing it already holds.
    """
    stmt = (
        select(BacktestRunEvent)
        .where(BacktestRunEvent.run_id == run_id, BacktestRunEvent.sequence_no > after_sequence)
        .order_by(BacktestRunEvent.sequence_no.asc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


# --------------------------------------------------------------------------- #
# Result materialization (L1 FK-safe)                                         #
# --------------------------------------------------------------------------- #


def _snapshot_manifest(
    manifest: dict[str, Any], portfolio_provenance: dict[str, Any] | None
) -> dict[str, Any]:
    """The run manifest as the RESULT pins it, plus the unified-clock section when there is
    one (doc 13 §13 / ADR 0002 §10.4).

    The section is OUTCOME provenance — a merged timeline identity, a tick count, the
    ledger's own equity digest — so it cannot exist at admission, when the run manifest is
    built and hashed. It is therefore appended here, at the one moment both the admission
    pins and the finished run are in hand, and it is appended to the Result's SNAPSHOT
    rather than to the run's manifest row: doc 15 §12 makes this copy the thing historical
    reads resolve against precisely so a Result never depends on a mutable neighbour.

    A copy, never a mutation: ``manifest.manifest`` belongs to the run and is read by the
    independent branch and by every replay of it. Writing the key in place would edit a
    live JSONB row's Python object under a caller that did not ask for a portfolio.

    Returns the input unchanged when there is no section, so an independent Result's
    snapshot stays byte-identical to what it was before this parameter existed.
    """
    if portfolio_provenance is None:
        return manifest
    return {**manifest, PORTFOLIO_SIMULATION_KEY: portfolio_provenance}


async def create_result(
    session: AsyncSession,
    *,
    run: BacktestRun,
    manifest: BacktestRunManifest,
    engine_output: EngineOutput,
    metric_values: list[MetricValue],
    portfolio_provenance: dict[str, Any] | None = None,
) -> BacktestResult:
    """Materialize the immutable Result + summary + metrics + artifacts (CR-03).

    The ``backtest_result`` root is flushed BEFORE any child so every FK is
    satisfiable in-transaction (L1).

    ``portfolio_provenance`` is the ``portfolio_simulation`` section, supplied ONLY by the
    unified-clock branch of the worker. It is pinned into the Result's manifest SNAPSHOT
    (see below); ``None`` — every independent and every sequentially folded run — stores the
    run manifest byte-for-byte as before.
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
            # F-05: the actual first/last bar timestamps replayed (post-filter),
            # never the requested config range — proves the manifest matches the
            # data actually processed.
            period_start=summary.get("period_start"),
            period_end=summary.get("period_end"),
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
    equity_rows = [
        ResultEquityPoint(
            point_id=new_id("bteq"),
            result_id=result_id,
            seq=point.seq,
            timestamp=point.timestamp,
            equity=point.equity,
            drawdown=point.drawdown,
            exposure=point.exposure,
        )
        for point in engine_output.equity_points
    ]
    trade_rows = [
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
        for trade in engine_output.trades
    ]
    signal_rows = [
        SignalEventRow(
            signal_event_id=new_id("btse"),
            result_id=result_id,
            seq=event.seq,
            event_time=event.event_time,
            event_type=event.event_type,
            direction=event.direction,
            detail=_jsonable(event.detail),
        )
        for event in engine_output.signal_events
    ]
    # I-02: the filter vetoes are their OWN artifact rows with their own ``seq`` — never
    # folded into ``signal_event`` (doc 15 §3.2 two drill-downs, §16).
    filtered_rows = [
        FilteredEventRow(
            filtered_event_id=new_id("btfe"),
            result_id=result_id,
            seq=event.seq,
            event_time=event.event_time,
            event_type=event.event_type,
            direction=event.direction,
            detail=_jsonable(event.detail),
        )
        for event in engine_output.filtered_events
    ]
    diagnostic_rows = [
        DiagnosticArtifact(
            diagnostic_id=new_id("btdiag"),
            result_id=result_id,
            kind="run_diagnostics",
            content=_jsonable(engine_output.diagnostics),
        )
    ]
    for artifact_rows in (equity_rows, trade_rows, signal_rows, filtered_rows, diagnostic_rows):
        session.add_all(artifact_rows)
    # doc 15 §8.3: the worker persists the artifacts WITH their checksums, and §7 makes
    # "artifact checksum verification" part of the drill-down contract. Computed from
    # the same projection the drill-down and the export both serve, so a caller that
    # paged the whole artifact can re-derive the value it is verifying against.
    for artifact_type, artifact_rows in (
        (ArtifactType.EQUITY_CURVE, equity_rows),
        (ArtifactType.TRADE_LEDGER, trade_rows),
        (ArtifactType.SIGNAL_EVENTS, signal_rows),
        (ArtifactType.FILTERED_EVENTS, filtered_rows),
        (ArtifactType.DIAGNOSTICS, diagnostic_rows),
    ):
        projected = checksum_rows(artifact_type, list(artifact_rows))
        session.add(
            ResultArtifactChecksum(
                checksum_id=new_id("btack"),
                result_id=result_id,
                artifact_type=str(artifact_type),
                row_count=len(projected),
                checksum=compute_artifact_checksum(artifact_type, projected),
                schema_version=ARTIFACT_CHECKSUM_SCHEMA_VERSION,
            )
        )
    session.add(
        ResultManifestSnapshot(
            snapshot_id=new_id("btms"),
            result_id=result_id,
            # The RUN's admission hash, unchanged. It is the run's IDENTITY (doc 15 §7,
            # §8.4 "retry -> new manifest hash") and it is what ties this Result back to
            # its run and forwards to every export's ``source_manifest_hash``. Rehashing
            # the extended dict below would fork that identity: ``result.manifest_hash``
            # would stop equalling ``run.manifest_hash`` and the provenance chain would
            # break at the join. The section carries its OWN content hash instead — the
            # same two-hashes-over-overlapping-content shape ``execution_key`` and
            # ``manifest_hash`` already have in ``domain/backtest/manifest.py``.
            manifest_hash=manifest.manifest_hash,
            execution_key=manifest.execution_key,
            engine_version=manifest.engine_version,
            manifest=_snapshot_manifest(manifest.manifest, portfolio_provenance),
        )
    )
    await session.flush()
    return result


# --------------------------------------------------------------------------- #
# Result read helpers                                                         #
# --------------------------------------------------------------------------- #


async def get_result(session: AsyncSession, result_id: str) -> BacktestResult | None:
    return await session.get(BacktestResult, result_id)


async def latest_result_for_workspace(
    session: AsyncSession, workspace_entity_id: str
) -> BacktestResult | None:
    """The most recent active succeeded Result for a composition (doc 15 §9.4).

    A ``BacktestResult`` exists only for a succeeded run (CR-03); soft-deleted
    results are excluded. Ordered newest-first by ``created_at`` with the ULID
    ``result_id`` as a deterministic same-instant tiebreak. Currentness of the
    result against the live composition is recomputed by the caller (the
    "snapshot differs" badge is never stored, doc 15 §9.4).
    """
    stmt = (
        select(BacktestResult)
        .where(
            BacktestResult.workspace_entity_id == workspace_entity_id,
            BacktestResult.deletion_state == "active",
        )
        .order_by(BacktestResult.created_at.desc(), BacktestResult.result_id.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


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


async def get_run_diagnostics_markers(
    session: AsyncSession, result_id: str
) -> dict[str, Any] | None:
    """The two diagnostics fields the portfolio-mode label needs, and nothing else.

    Deliberately NOT a full ``diagnostics`` read: for a multi-item Result that blob carries
    every item's whole equity curve, and the Result detail endpoint must not pay for it just
    to answer "which co-simulation produced this". Two JSONB path extracts on one indexed
    row instead. ``None`` when the Result retains no diagnostics artifact — the caller
    reports that as ``unknown`` rather than assuming an era."""
    stmt = (
        select(
            DiagnosticArtifact.content["engine_kind"].label("engine_kind"),
            DiagnosticArtifact.content["warnings"].label("warnings"),
            DiagnosticArtifact.content["composition"]["strategy_count"].label("strategy_count"),
        )
        .where(
            DiagnosticArtifact.result_id == result_id,
            DiagnosticArtifact.kind == "run_diagnostics",
        )
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    composition = {"strategy_count": row.strategy_count} if row.strategy_count is not None else {}
    return {
        "engine_kind": row.engine_kind,
        "warnings": row.warnings,
        "composition": composition,
    }


async def get_portfolio_mode_markers(
    session: AsyncSession, result_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """The portfolio-mode inputs for a whole history page, in TWO batched reads.

    Mirrors the ``_load_digests`` / ``_load_summaries`` pattern already used by the
    history index: one ``IN (...)`` per table, never one read per row. Only the JSONB
    paths that matter are extracted — a per-row full-manifest or full-diagnostics read
    would be an N+1 over two of the largest columns in the schema.

    A result absent from either map simply contributes nothing; the caller resolves that
    to ``unknown`` rather than assuming an era."""
    if not result_ids:
        return {}
    markers: dict[str, dict[str, Any]] = {}

    diag = select(
        DiagnosticArtifact.result_id.label("result_id"),
        DiagnosticArtifact.content["engine_kind"].label("engine_kind"),
        DiagnosticArtifact.content["warnings"].label("warnings"),
        DiagnosticArtifact.content["composition"]["strategy_count"].label("strategy_count"),
    ).where(
        DiagnosticArtifact.result_id.in_(result_ids),
        DiagnosticArtifact.kind == "run_diagnostics",
    )
    for row in (await session.execute(diag)).all():
        composition = (
            {"strategy_count": row.strategy_count} if row.strategy_count is not None else {}
        )
        markers[row.result_id] = {
            "diagnostics": {
                "engine_kind": row.engine_kind,
                "warnings": row.warnings,
                "composition": composition,
            },
            "unified_manifest_version": None,
        }

    pinned = select(
        ResultManifestSnapshot.result_id.label("result_id"),
        # The SAME constants the writer pins with (``_snapshot_manifest``). Two literals
        # here would let a rename move the writer and leave the reader silently blind —
        # and a reader that finds no section reports ``unknown``, not an error.
        ResultManifestSnapshot.manifest[PORTFOLIO_SIMULATION_KEY]["policy_versions"][
            UNIFIED_MANIFEST_VERSION_FIELD
        ]
        .as_string()
        .label("version"),
    ).where(ResultManifestSnapshot.result_id.in_(result_ids))
    for row in (await session.execute(pinned)).all():
        entry = markers.setdefault(
            row.result_id, {"diagnostics": None, "unified_manifest_version": None}
        )
        entry["unified_manifest_version"] = row.version

    return markers


async def count_artifacts(session: AsyncSession, result_id: str) -> dict[str, int]:
    """Cheap projection counts for the collapsed Result row (heavy pagination is a
    later slice)."""
    from sqlalchemy import func

    counts: dict[str, int] = {}
    for label, model in (
        ("equity_points", ResultEquityPoint),
        ("trades", TradeLedgerRow),
        ("signal_events", SignalEventRow),
        ("filtered_events", FilteredEventRow),
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
    "latest_result_for_workspace",
    "list_metric_values",
]
