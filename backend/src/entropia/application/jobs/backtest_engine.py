"""Backtest engine worker body (Stage 5a → post-V1 Slice B, doc 15 §8.3, §9.3, §15).

Runs on the ``backtest`` queue. The durable ``jobs`` row + the ``backtest_run`` row
are the source of truth — the request that admitted the run has long since returned
(CR-09); browser close / logout never cancels it (doc 15 §8.2). Steps:

    load job + run + immutable manifest -> mark RUNNING ->
    RE-RESOLVE every pinned revision from the manifest (NO 'latest' fallback;
        any unresolved pin => terminal FAILED, doc 15 §11, §15) ->
    resolve EVERY enabled Strategy's pinned config + its pinned market revision's
        processed bar source (INF-12); a missing asset => terminal FAILED (F-04) ->
    for each enabled Strategy: physically filter its bar stream to its backtest_range
        + verify its pinned revision's instrument (F-05); resolve its pinned indicator
        plan (F-06: NEVER the breakout proxy); an invalid/empty-after-filter range,
        instrument mismatch, or unresolved required dependency on ANY enabled Strategy
        => terminal FAILED (a selected object is never silently dropped) ->
    bar-replay the deterministic engine (``domain.backtest.engine``) once per enabled
        Strategy over its streamed OHLCV batches (bounded memory), then COMPOSE every
        contribution into one portfolio result in deterministic manifest pin order
        (F-04); a lone Strategy stays byte-identical (no compose step) ->
    ONLY on success: materialize the immutable Result + summary + metrics +
        artifacts (CR-03), back-fill run.result_id, run -> SUCCEEDED ->
    audit + outbox.

A FAILED run is a normal recorded terminal outcome (diagnostics only, no Result,
no history row), NOT a job exception — so the worker does not retry a permanent
manifest/asset/engine failure. Only an unexpected/missing-row condition raises.

Bars are injected via ``stream_bars`` (default: the real S3-backed
``iter_bar_batches``) so integration tests exercise the full resolve → replay →
materialize chain without object storage.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.queries.funding import FundingRowLoader, resolve_funding_schedule
from entropia.application.queries.indicator_plan import resolve_indicator_plan
from entropia.application.queries.market_bars import (
    BarSourceRef,
    filter_bars_by_range,
    iter_bar_batches,
    parse_range_bound,
    resolve_bar_source,
)
from entropia.application.queries.market_ticks import (
    TickSourceRef,
    iter_tick_batches,
    resolve_tick_source,
)
from entropia.domain.backtest.engine import (
    EngineOutput,
    ItemRun,
    combine_item_runs,
    resolve_allocation_execution,
    run_engine,
    tick_data_required,
)
from entropia.domain.backtest.enums import (
    RUN_TERMINAL_STATES,
    BacktestRunState,
    RunFailureCode,
)
from entropia.domain.backtest.metrics import derive_metric_values
from entropia.domain.lifecycle.enums import ActorKind, JobStatus
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.strategy.config import StrategyConfig
from entropia.infrastructure.postgres.models import Job
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import strategy as strat_repo
from entropia.shared.errors import FundingSourceInvalid, NotFoundError

_RUN_TARGET = "backtest_run"
_RESULT_TARGET = "backtest_result"

# The worker owns the bar-source I/O boundary; the engine itself never touches S3.
BarBatchStreamer = Callable[[BarSourceRef], Iterator[list[dict[str, Any]]]]
# F-07i (B): same boundary for the pinned tick/trade print stream — injectable so
# integration tests exercise the resolve -> replay chain without object storage.
TickBatchStreamer = Callable[[TickSourceRef], Iterator[list[dict[str, Any]]]]


async def run_backtest(
    session: AsyncSession,
    job_id: str,
    *,
    stream_bars: BarBatchStreamer = iter_bar_batches,
    stream_ticks: TickBatchStreamer = iter_tick_batches,
    load_funding_rows: FundingRowLoader | None = None,
) -> dict[str, Any]:
    """Execute the durable backtest job. Does not commit (the worker scope commits)."""
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found.")
    run_id = str((job.payload or {}).get("run_id"))
    run = await bt_repo.get_run(session, run_id)
    if run is None:
        raise ValueError(f"Backtest run '{run_id}' not found for job '{job_id}'.")
    manifest = await bt_repo.get_manifest_by_run(session, run_id)
    if manifest is None:
        raise ValueError(f"Backtest manifest for run '{run_id}' not found.")

    # At-least-once delivery guard: a redelivered message for an already-terminal
    # run must NOT re-run the engine (a second create_result would violate
    # UNIQUE(backtest_result.run_id)). Return the durable outcome unchanged.
    if run.state in RUN_TERMINAL_STATES:
        return _terminal_ref(run)

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    run.state = BacktestRunState.PROVISIONING
    run.started_at = datetime.now(UTC)

    # Re-resolve pins while still PROVISIONING; advance to RUNNING only when the
    # manifest fully resolves AND the bar source is available, so the fail path
    # never transits through RUNNING.
    missing = await _unresolved_pins(session, manifest.manifest)
    if missing:
        return _fail_run(
            session,
            job,
            run,
            code=RunFailureCode.MANIFEST_RESOLUTION,
            message=f"Pinned revisions could not be resolved (no 'latest' fallback): {missing}",
        )

    # F-04: resolve EVERY enabled Strategy item, not just the first. The user selected
    # all of them; a composition with two enabled strategies must run both and fold
    # their contributions into one portfolio result.
    strategies = await _resolve_enabled_strategies(session, manifest.manifest)
    if not strategies:
        return _fail_run(
            session,
            job,
            run,
            code=RunFailureCode.ASSET_UNAVAILABLE,
            message="No enabled Strategy item with a resolvable pinned config in the composition.",
        )

    capital_execution = manifest.manifest.get("capital_execution")
    item_count = len(manifest.manifest.get("mainboard_items", []))
    # Prepare + bar-replay each enabled Strategy while still PROVISIONING, so the fail
    # path (a missing asset / bad range / instrument mismatch / unresolved dependency /
    # engine error on ANY enabled Strategy) never transits through RUNNING. A single
    # enabled Strategy that fails is not silently dropped — the whole run FAILS (F-04:
    # every selected object participates or the result is honestly not produced).
    item_runs: list[ItemRun] = []
    for config, meta in strategies:
        prepared = await _prepare_and_run_strategy(
            session,
            config=config,
            meta=meta,
            stream_bars=stream_bars,
            stream_ticks=stream_ticks,
            tick_data=manifest.manifest.get("tick_data"),
            load_funding_rows=load_funding_rows,
            capital_execution=capital_execution,
            execution_key=manifest.execution_key,
            item_count=item_count,
        )
        if isinstance(prepared, _PrepFailure):
            return _fail_run(session, job, run, code=prepared.code, message=prepared.message)
        item_runs.append(prepared)

    run.state = BacktestRunState.RUNNING

    # Enabled non-Strategy items (Trading Signal / Trade Log) are pinned + recorded for
    # traceability but run no standalone V1 bar-replay (F-04 honest boundary): their
    # execution effect is defined only as a Strategy data input. Disabled items were
    # already excluded from the snapshot (doc 01 §5.2) and never reach here.
    non_executing = _enabled_non_strategy_items(manifest.manifest)

    if len(item_runs) == 1 and not non_executing:
        # Byte-identical single-Strategy path: a lone enabled Strategy with nothing else
        # in the composition produces exactly the pre-F-04 engine output (no compose).
        output: EngineOutput = item_runs[0].output  # type: ignore[assignment]
    else:
        # Portfolio starting capital: the shared pool P0 under shared allocation (taken
        # ONCE — each sleeve reports the same pool), else the sum of the strategies' own
        # initial capitals (independent mode). Realized PnL is additive either way.
        alloc_probe = resolve_allocation_execution(capital_execution, item_id=item_runs[0].item_id)
        if alloc_probe is not None:
            portfolio_initial = alloc_probe.initial_capital
        else:
            portfolio_initial = sum(
                (Decimal(str(r.output.summary["initial_capital"])) for r in item_runs if r.output),
                Decimal("0"),
            )
        output = combine_item_runs(
            [*item_runs, *non_executing],
            portfolio_initial_capital=portfolio_initial,
            execution_key=manifest.execution_key,
            item_count=item_count,
        )
    metric_values = derive_metric_values(output.summary)

    result = await bt_repo.create_result(
        session,
        run=run,
        manifest=manifest,
        engine_output=output,
        metric_values=metric_values,
    )
    run.result_id = result.result_id
    run.state = BacktestRunState.SUCCEEDED
    run.finished_at = datetime.now(UTC)

    _emit_success_audit(session, run=run, result_id=result.result_id)
    job.status = JobStatus.SUCCEEDED
    job.finished_at = datetime.now(UTC)
    result_ref = {
        "run_id": run_id,
        "state": BacktestRunState.SUCCEEDED.value,
        "result_id": result.result_id,
        "manifest_hash": run.manifest_hash,
    }
    job.result_ref = result_ref
    return result_ref


async def _unresolved_pins(session: AsyncSession, manifest: dict[str, Any]) -> list[str]:
    """Every pinned revision that no longer resolves (soft-deleted / missing).

    The worker reads ONLY the manifest; it never falls back to the current
    Mainboard or a 'latest' revision (doc 15 §15)."""
    missing: list[str] = []
    for item in manifest.get("mainboard_items", []):
        revision_id = item.get("selected_revision_id")
        if revision_id is None:
            missing.append(str(item.get("item_id")))
            continue
        revision = await mb_repo.get_work_object_revision(session, str(revision_id))
        if revision is None:
            missing.append(str(revision_id))
    return missing


@dataclass(frozen=True, slots=True)
class _PrepFailure:
    """A per-Strategy preparation/replay failure (F-04): fails the WHOLE run.

    A selected Strategy that cannot resolve its asset / range / instrument / indicator
    plan, or that errors during replay, is never silently dropped — the run fails so a
    result is never materialized missing an object the user chose (spec F-04/F-06)."""

    code: RunFailureCode
    message: str


async def _resolve_enabled_strategies(
    session: AsyncSession, manifest: dict[str, Any]
) -> list[tuple[StrategyConfig, dict[str, Any]]]:
    """Every enabled Strategy item's pinned config + its composition item metadata (F-04).

    Items are consumed in the manifest's deterministic pin order (sorted by
    ``(root_id, selected_revision_id)`` at manifest-build time — doc 01 §5.2 presentation
    ``position`` is explicitly NOT engine event priority), so the composed portfolio
    result is reproducible. The ``item_id`` (== the allocation entry's
    ``composition_item_id``, doc 13 §8.2) joins each item to its sleeve share. Reads ONLY
    pinned revisions; a pin that no longer parses to a valid config is skipped here and
    caught upstream as a hard MANIFEST_RESOLUTION / ASSET failure."""
    resolved: list[tuple[StrategyConfig, dict[str, Any]]] = []
    for item in manifest.get("mainboard_items", []):
        if item.get("item_kind") != MainboardItemKind.STRATEGY:
            continue
        if item.get("enabled") is False:
            continue
        revision_id = item.get("selected_revision_id")
        if revision_id is None:
            continue
        revision = await mb_repo.get_work_object_revision(session, str(revision_id))
        if revision is None:
            continue
        payload = await _resolve_strategy_payload(session, dict(revision.payload))
        try:
            config = StrategyConfig.model_validate(payload)
        except ValidationError:
            continue
        resolved.append(
            (
                config,
                {
                    "item_id": str(item.get("item_id")),
                    "item_kind": str(item.get("item_kind")),
                    "root_id": item.get("root_id"),
                    "revision_id": str(revision_id),
                },
            )
        )
    return resolved


def _enabled_non_strategy_items(manifest: dict[str, Any]) -> list[ItemRun]:
    """Enabled Trading Signal / Trade Log items — pinned + recorded, no standalone run.

    F-04 honest boundary: these EXTERNAL work objects affect execution only as a
    Strategy data input, so the V1 bar-replay engine runs no standalone simulation for
    them. They are still surfaced (``output=None``) in the composite diagnostics so
    every participating object is traceable; disabled items were already excluded from
    the snapshot and never reach here."""
    items: list[ItemRun] = []
    for item in manifest.get("mainboard_items", []):
        if item.get("item_kind") == MainboardItemKind.STRATEGY:
            continue
        if item.get("enabled") is False:
            continue
        revision_id = item.get("selected_revision_id")
        items.append(
            ItemRun(
                item_id=str(item.get("item_id")),
                item_kind=str(item.get("item_kind")),
                root_id=item.get("root_id"),
                revision_id=str(revision_id) if revision_id is not None else None,
                output=None,
            )
        )
    return items


async def _prepare_and_run_strategy(
    session: AsyncSession,
    *,
    config: StrategyConfig,
    meta: dict[str, Any],
    stream_bars: BarBatchStreamer,
    stream_ticks: TickBatchStreamer,
    tick_data: dict[str, Any] | None,
    load_funding_rows: FundingRowLoader | None,
    capital_execution: dict[str, Any] | None,
    execution_key: str,
    item_count: int,
) -> ItemRun | _PrepFailure:
    """Resolve + bar-replay ONE enabled Strategy (F-04/F-05/F-06), or a ``_PrepFailure``.

    Mirrors the pre-F-04 single-strategy chain exactly (asset -> F-05 range/instrument
    filter -> F-06 indicator plan -> allocation sleeve -> ``run_engine``), so a lone
    Strategy replays byte-identically. Every failure is attributed to its ``item_id``
    for traceability, and fails the whole run upstream — a selected Strategy is never
    silently skipped."""
    item_id = meta["item_id"]
    market_revision_id = config.data.market_dataset_revision_id
    try:
        source = await resolve_bar_source(session, market_revision_id=market_revision_id)
    except NotFoundError:
        return _PrepFailure(
            RunFailureCode.ASSET_UNAVAILABLE,
            f"Strategy item '{item_id}': pinned market revision '{market_revision_id}' "
            "has no processed bar asset.",
        )

    # F-05: physically filter the bar stream to this strategy's selected date range +
    # cross-check its pinned market revision's instrument.
    range_cfg = config.data.backtest_range
    range_start = parse_range_bound(range_cfg.start)
    range_end = parse_range_bound(range_cfg.end)
    if range_start is None or range_end is None or range_start > range_end:
        return _PrepFailure(
            RunFailureCode.INVALID_BACKTEST_RANGE,
            f"Strategy item '{item_id}': backtest_range '{range_cfg.start}'.."
            f"'{range_cfg.end}' is not a valid start<=end ISO-8601 window.",
        )
    # The pinned revision's dataset-level instrument (GAP-16) must match the strategy's
    # selected instrument when it is known. A legacy/unset revision instrument_id cannot
    # be disproven and is honestly passed through unfiltered; an actual mismatch is a
    # hard fail-closed reject, never a silent cross-instrument run (F-05 acceptance).
    market_revision = await md_repo.get_revision(session, market_revision_id)
    if (
        market_revision is not None
        and market_revision.instrument_id is not None
        and market_revision.instrument_id != config.data.instrument_id
    ):
        return _PrepFailure(
            RunFailureCode.INSTRUMENT_MISMATCH,
            f"Strategy item '{item_id}': pinned market revision '{market_revision_id}' is "
            f"scoped to instrument '{market_revision.instrument_id}', not the strategy's "
            f"selected '{config.data.instrument_id}'.",
        )
    filtered_bars = filter_bars_by_range(
        stream_bars(source), start=range_cfg.start, end=range_cfg.end
    )
    try:
        first_batch = next(filtered_bars)
    except StopIteration:
        return _PrepFailure(
            RunFailureCode.EMPTY_FILTERED_RANGE,
            f"Strategy item '{item_id}': no bars fall within the selected backtest_range "
            f"'{range_cfg.start}'..'{range_cfg.end}' for market revision "
            f"'{market_revision_id}'.",
        )
    bar_batches = itertools.chain([first_batch], filtered_bars)

    # F-06: an unresolved required indicator dependency is a HARD terminal failure —
    # NEVER silently substituted with the deterministic breakout proxy.
    indicator_plan = await resolve_indicator_plan(session, config)
    if not indicator_plan.has_entry or indicator_plan.unresolved:
        return _PrepFailure(
            RunFailureCode.UNRESOLVED_DEPENDENCY,
            f"Strategy item '{item_id}': required indicator dependency could not be "
            "resolved (no breakout-proxy fallback): "
            f"{list(indicator_plan.unresolved) or 'no computable entry signal'}.",
        )

    # F-11: resolve the pinned funding source (a ``funding_rate`` Research revision) into an
    # available-time-safe schedule the engine applies as a real position cost. Funding OFF
    # resolves to None (byte-identical to pre-F-11). A funding source the engine cannot
    # interpret (not Approved / wrong scope-category / hash mismatch / unreadable native
    # schema) is a hard terminal failure — never a silent zero-cost run (doc 12 §8.4).
    funding_kwargs = {"load_rows": load_funding_rows} if load_funding_rows is not None else {}
    try:
        funding_schedule = await resolve_funding_schedule(
            session, config.data.funding, **funding_kwargs
        )
    except FundingSourceInvalid as exc:
        return _PrepFailure(
            RunFailureCode.FUNDING_SOURCE_INVALID,
            f"Strategy item '{item_id}': {exc.args[0] if exc.args else exc}",
        )

    # F-07i (B): a tick-demanding strategy replays over its PINNED tick/trade revision's
    # processed print stream. The pin comes from the MANIFEST (admission-time resolution
    # — the worker never falls back to 'newest approved', doc 15 §15); a missing pin (a
    # stale pre-v15 manifest) or a missing processed asset is a hard terminal failure,
    # never a silently tickless run. Resolved OUTSIDE the engine try (F-11/INF-12
    # precedent) so a DB error stays a retryable job exception.
    tick_batches: Iterator[list[dict[str, Any]]] | None = None
    if tick_data_required(config):
        pin = (tick_data or {}).get(item_id) or {}
        tick_revision_id = pin.get("tick_revision_id")
        if not tick_revision_id:
            return _PrepFailure(
                RunFailureCode.ASSET_UNAVAILABLE,
                f"Strategy item '{item_id}' requires tick data but the run manifest pins "
                "no tick/trade revision for it.",
            )
        try:
            tick_source = await resolve_tick_source(session, tick_revision_id=str(tick_revision_id))
        except NotFoundError:
            return _PrepFailure(
                RunFailureCode.ASSET_UNAVAILABLE,
                f"Strategy item '{item_id}': pinned tick revision '{tick_revision_id}' "
                "has no processed tick asset.",
            )
        tick_batches = stream_ticks(tick_source)

    base_timeframe = await md_repo.get_base_timeframe_for_revision(session, market_revision_id)
    # GAP-02: apply the pinned shared-pool capital model from the manifest snapshot
    # (doc 13 §8.3/§8.4). Independent / absent allocation resolves to None, so the engine
    # sizes from the strategy's own initial_capital. The item id joins the allocation
    # entries to this item's sleeve share.
    allocation = resolve_allocation_execution(capital_execution, item_id=item_id)
    try:
        output = run_engine(
            strategy_config=config,
            bar_batches=bar_batches,
            execution_key=execution_key,
            item_count=item_count,
            indicator_plan=indicator_plan,
            timeframe=base_timeframe,
            allocation=allocation,
            funding=funding_schedule,
            tick_batches=tick_batches,
        )
    except Exception as exc:
        return _PrepFailure(
            RunFailureCode.ENGINE_ERROR,
            f"Strategy item '{item_id}': engine error during bar-replay: {exc}",
        )
    return ItemRun(
        item_id=item_id,
        item_kind=meta["item_kind"],
        root_id=meta["root_id"],
        revision_id=meta["revision_id"],
        output=output,
    )


async def _resolve_strategy_payload(
    session: AsyncSession, payload: dict[str, Any]
) -> dict[str, Any]:
    """Dereference a Strategy-editor MIRROR pin to its typed canonical config.

    Twin of ``readiness_check._resolve_strategy_payload`` (doc 02 §7.1): a strategy
    Mainboard item pins either a direct StrategyConfig or the mirror work-object
    revision (``{"strategy_revision_id", ...}``). The engine must replay the REAL
    immutable configuration, so the mirror is dereferenced here; an unresolvable
    mirror falls through unchanged and fails config parse visibly."""
    mirror_ref = payload.get("strategy_revision_id")
    if not mirror_ref:
        return payload
    revision = await strat_repo.get_strategy_revision(session, str(mirror_ref))
    if revision is None:
        return payload
    return dict(revision.payload)


def _fail_run(
    session: AsyncSession,
    job: Job,
    run: Any,
    *,
    code: RunFailureCode,
    message: str,
) -> dict[str, Any]:
    run.state = BacktestRunState.FAILED
    run.failure_code = code.value
    run.failure_message = message
    run.finished_at = datetime.now(UTC)
    _emit_failure_audit(session, run=run, code=code)
    # The job itself completed (it produced a terminal run); a permanent manifest
    # failure is not retried by re-running the same job (doc 15 §11 — retry is a
    # new run via RetryBacktestRun).
    job.status = JobStatus.SUCCEEDED
    job.finished_at = datetime.now(UTC)
    result_ref = {
        "run_id": run.run_id,
        "state": BacktestRunState.FAILED.value,
        "failure_code": code.value,
        "result_id": None,
    }
    job.result_ref = result_ref
    return result_ref


def _terminal_ref(run: Any) -> dict[str, Any]:
    """Durable outcome for an already-terminal run (redelivery-safe; no re-run)."""
    return {
        "run_id": run.run_id,
        "state": str(run.state),
        "result_id": run.result_id,
        "failure_code": run.failure_code,
    }


def _emit_success_audit(session: AsyncSession, *, run: Any, result_id: str) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind="backtest.run_succeeded",
        actor_principal_id=run.requested_by_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=run.run_id,
        target_entity_type=_RUN_TARGET,
        new_state=str(run.state),
        correlation_id=run.correlation_id,
        metadata={"manifest_hash": run.manifest_hash, "result_id": result_id},
    )
    audit_repo.add_audit_event(
        session,
        event_kind="backtest.result_materialized",
        actor_principal_id=run.requested_by_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=result_id,
        target_entity_type=_RESULT_TARGET,
        new_state=result_id,
        correlation_id=run.correlation_id,
        metadata={"manifest_hash": run.manifest_hash, "run_id": run.run_id},
    )
    audit_repo.add_outbox_event(
        session,
        event_type="backtest.result_materialized",
        resource_type=_RESULT_TARGET,
        resource_id=result_id,
        payload={
            "result_id": result_id,
            "run_id": run.run_id,
            "manifest_hash": run.manifest_hash,
            "composition_fingerprint": run.composition_fingerprint,
        },
        correlation_id=run.correlation_id,
    )


def _emit_failure_audit(session: AsyncSession, *, run: Any, code: RunFailureCode) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind="backtest.run_failed",
        actor_principal_id=run.requested_by_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=run.run_id,
        target_entity_type=_RUN_TARGET,
        new_state=run.state,
        correlation_id=run.correlation_id,
        metadata={"failure_code": code.value},
    )
    audit_repo.add_outbox_event(
        session,
        event_type="backtest.run_failed",
        resource_type=_RUN_TARGET,
        resource_id=run.run_id,
        payload={"run_id": run.run_id, "state": run.state, "failure_code": code.value},
        correlation_id=run.correlation_id,
    )


__all__ = ["BarBatchStreamer", "TickBatchStreamer", "run_backtest"]
