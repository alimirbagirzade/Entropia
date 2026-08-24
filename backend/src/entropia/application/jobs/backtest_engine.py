"""Backtest engine worker body (Stage 5a → post-V1 Slice B, doc 15 §8.3, §9.3, §15).

Runs on the ``backtest`` queue. The durable ``jobs`` row + the ``backtest_run`` row
are the source of truth — the request that admitted the run has long since returned
(CR-09); browser close / logout never cancels it (doc 15 §8.2). Steps:

    load job + run + immutable manifest -> mark PROVISIONING (durable, committed) ->
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

O-05 — stage observability. Each stage transition writes a durable
``backtest_run_event`` (per-run monotonic ``sequence_no``) + audit + outbox row and
is COMMITTED before the next stage begins, so PROVISIONING and RUNNING are visible
to any other reader while the engine is still working (doc 15 §8.3, §12) and a
disconnected client replays from its ``last_sequence`` (doc 15 §7, §11). The
at-least-once guard is untouched: a TERMINAL run is still never re-run. A
non-terminal run left behind by a killed worker is genuinely incomplete, so a
redelivery re-attempts it and simply appends further events to the same sequence.

O-06 — controlled cancellation. The worker is never killed mid-flight. An
authorized ``cancel_backtest_run`` records an INTENT on the run row; the worker
reads it at four SAFE CHECKPOINTS (after the PROVISIONING commit, between two
strategies' asset resolution, between two items' bar-replays, and last of all
immediately before the Result is materialized) and only then writes terminal
CANCELLED. Checkpoint four is what makes doc 15 §16 true: past it the immutable
Result exists and the run can only end SUCCEEDED, so a later cancel is honestly
not honored — which is exactly what the command's ``cancellation_safe_boundary``
delivery policy promises. The claim/cancel race at the very start is closed by a
row lock both sides take (see ``run_backtest``).

A FAILED run is a normal recorded terminal outcome (diagnostics only, no Result,
no history row), NOT a job exception — so the worker does not retry a permanent
manifest/asset/engine failure. A CANCELLED run is the same shape. Only an
unexpected/missing-row condition raises.

Bars are injected via ``stream_bars`` (default: the real S3-backed
``iter_bar_batches``) so integration tests exercise the full resolve → replay →
materialize chain without object storage.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands.readiness_check import _resolve_strategy_payload
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
from entropia.domain.allocation.capability import (
    shared_allocation_is_executable,
    shared_allocation_requested,
)
from entropia.domain.backtest.engine import (
    EngineOutput,
    ItemRun,
    PortfolioRules,
    PriorItemInterval,
    _build_stepper,
    build_prior_intervals,
    resolve_allocation_execution,
    resolve_portfolio_rules,
    run_engine,
)
from entropia.domain.backtest.enums import (
    RUN_TERMINAL_STATES,
    BacktestRunState,
    RunEventType,
    RunFailureCode,
)
from entropia.domain.backtest.execution.constants import _HUNDRED, _MONEY, _ZERO
from entropia.domain.backtest.execution.fills import (
    tick_data_required,
)
from entropia.domain.backtest.execution.portfolio import combine_item_runs
from entropia.domain.backtest.execution.portfolio_projection import (
    PinnedItem,
    project_portfolio_run,
)
from entropia.domain.backtest.metrics import derive_metric_values
from entropia.domain.backtest.participant import build_engine_participant
from entropia.domain.backtest.portfolio_engine import ItemParticipant, iter_portfolio
from entropia.domain.lifecycle.enums import ActorKind, DeletionState, JobStatus
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.strategy.config import StrategyConfig
from entropia.infrastructure.postgres.models import Job
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import readiness as readiness_repo
from entropia.infrastructure.postgres.repositories import research_data as research_repo
from entropia.infrastructure.postgres.repositories import strategy as strat_repo
from entropia.shared.errors import FundingSourceInvalid, NotFoundError

_RUN_TARGET = "backtest_run"
_RESULT_TARGET = "backtest_result"

# The spec's run event token (doc 15 §12) -> the shipped dotted audit/outbox kind.
# Both names are kept on purpose: the token identifies the durable stream row a
# client replays, the dotted kind matches the audit plane's existing
# ``backtest.run_succeeded`` / ``backtest.run_failed`` convention.
_STAGE_AUDIT_KIND: dict[RunEventType, str] = {
    RunEventType.RUN_STARTED: "backtest.run_started",
    RunEventType.RUN_STAGE_CHANGED: "backtest.run_stage_changed",
}

# The worker owns the bar-source I/O boundary; the engine itself never touches S3.
BarBatchStreamer = Callable[[BarSourceRef], Iterator[list[dict[str, Any]]]]
# F-07i (B): same boundary for the pinned tick/trade print stream — injectable so
# integration tests exercise the resolve -> replay chain without object storage.
TickBatchStreamer = Callable[[TickSourceRef], Iterator[list[dict[str, Any]]]]

#: How many committed ticks the unified-clock loop advances between two cancellation
#: checks. ADR-0002 §11: the merged axis DELETES the between-items boundary that O-06
#: checkpoint #3 sits on, so cancel/pause needs a per-K-ticks granularity or a long shared
#: run becomes uncancellable. The number is a latency / round-trip trade and NOT a
#: correctness knob: each check is one ``session.refresh``, a stride of 1 would put a
#: database round trip between every pair of bars, and a stride wide enough to matter would
#: leave a cancel unobserved for the rest of the run. Whatever it is set to, checkpoint #4
#: still runs unconditionally before any Result exists (doc 15 §16), so the WORST a wrong
#: stride can cost is how long a user waits — never a Result for a cancelled run.
_TICK_CHECKPOINT_STRIDE = 500


def _use_unified_clock(capital_execution: Any) -> bool:
    """The ONE place that decides shared-clock vs independent replay (P-C2 §C.5).

    **Both conjuncts are load-bearing**, and either one alone silently re-prices every
    INDEPENDENT composite Result — with no flag, no ``ENGINE_VERSION`` bump and nothing a
    reader could see. ``shared_allocation_requested`` alone would route an independent
    multi-item run through the shared loop the moment someone mis-reads the snapshot;
    ``shared_allocation_is_executable`` alone would route EVERY multi-item run through it.
    Independent multi-item runs are a complete, first-class mode (doc 13 §1.1), so that is
    not a hypothetical: it is most of what production runs today.

    ``shared_allocation_is_executable()`` is read HERE, at the branch, and never cached —
    the containment gate's reachability assertion is that this module names it, and a cached
    copy would make the branch answer a question that was asked at import time.

    It deliberately does NOT test how many items execute. That is ADR §3.2's separate
    invariant, tested at the call site where the reason for it is visible."""
    return shared_allocation_is_executable() and shared_allocation_requested(capital_execution)


async def run_backtest(
    session: AsyncSession,
    job_id: str,
    *,
    stream_bars: BarBatchStreamer = iter_bar_batches,
    stream_ticks: TickBatchStreamer = iter_tick_batches,
    load_funding_rows: FundingRowLoader | None = None,
) -> dict[str, Any]:
    """Execute the durable backtest job.

    Commits at each stage boundary (O-05) so PROVISIONING/RUNNING are observable
    while the engine works; the FINAL segment (terminal state + Result + audit) is
    left uncommitted for the worker scope to commit, exactly as before."""
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found.")
    run_id = str((job.payload or {}).get("run_id"))
    # O-06: claim the run under its row lock, held across the QUEUED -> PROVISIONING
    # transition below. ``cancel_backtest_run`` takes the SAME lock, so the two can
    # never interleave: either the cancel lands first (and the terminal guard below
    # turns this delivery into a no-op), or this worker claims the run and the cancel
    # then observes PROVISIONING and downgrades itself to a checkpoint request.
    # Without the lock a cancel could write ``cancelled`` between this read and the
    # write below, and the worker would silently overwrite it and materialize a
    # Result for a run the user cancelled.
    run = await bt_repo.get_run(session, run_id, for_update=True)
    if run is None:
        raise ValueError(f"Backtest run '{run_id}' not found for job '{job_id}'.")
    manifest = await bt_repo.get_manifest_by_run(session, run_id)
    if manifest is None:
        raise ValueError(f"Backtest manifest for run '{run_id}' not found.")

    # At-least-once delivery guard: a redelivered message for an already-terminal
    # run must NOT re-run the engine (a second create_result would violate
    # UNIQUE(backtest_result.run_id)). Return the durable outcome unchanged. This
    # is also what makes a QUEUED-stage cancel final: the run is already
    # ``cancelled``, so the engine never starts.
    if run.state in RUN_TERMINAL_STATES:
        return _terminal_ref(run)

    entry_state = run.state
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    run.state = BacktestRunState.PROVISIONING
    run.started_at = datetime.now(UTC)
    await _record_stage(
        session,
        run,
        event_type=RunEventType.RUN_STARTED,
        previous_state=entry_state,
        state=BacktestRunState.PROVISIONING,
        detail={"job_id": job_id, "manifest_hash": run.manifest_hash},
    )
    # O-05 stage checkpoint. Without this commit the whole body lands in ONE
    # transaction (the actor's), so PROVISIONING/RUNNING never exist for any other
    # reader and the run looks like QUEUED -> terminal from outside — while doc 15
    # §8.3 requires the worker to WRITE these events. Committing here also means a
    # worker killed mid-replay leaves a truthful durable stage instead of silently
    # reverting to QUEUED.
    await session.commit()

    # O-06 safe checkpoint #1 — the run is durably PROVISIONING and the lock is
    # released, so an authorized cancel can now be observed. Checked BEFORE the pin
    # re-resolution because that pass is many round trips wide.
    if await _cancellation_requested(session, run):
        return await _cancel_run(session, job, run, stage=BacktestRunState.PROVISIONING)

    # Re-resolve pins while still PROVISIONING; advance to RUNNING only when the
    # manifest fully resolves AND every enabled Strategy's assets / range /
    # instrument / indicator plan are in hand, so the resolution fail path never
    # transits through RUNNING.
    missing = await _unresolved_pins(session, manifest.manifest)
    if missing:
        return await _fail_run(
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
        return await _fail_run(
            session,
            job,
            run,
            code=RunFailureCode.ASSET_UNAVAILABLE,
            message="No enabled Strategy item with a resolvable pinned config in the composition.",
        )

    capital_execution = manifest.manifest.get("capital_execution")
    item_count = len(manifest.manifest.get("mainboard_items", []))

    # PROVISIONING = resolve every enabled Strategy's assets (bar/tick source, range,
    # instrument, indicator plan, funding schedule, allocation sleeve). A resolution
    # failure on ANY enabled Strategy fails the whole run here, so the resolution fail
    # path still never transits through RUNNING (F-04: a selected Strategy is never
    # silently dropped). O-05 splits this from the replay — previously both happened
    # under PROVISIONING and RUNNING was a zero-duration state set AFTER the engine had
    # already finished, which is exactly why RUNNING was never observable.
    prepared_items: list[_PreparedStrategy] = []
    for config, meta in strategies:
        # O-06 safe checkpoint #2 — between two strategies' asset resolution. Each
        # item opens its own bar/tick stream, so this is a real boundary, not a
        # cosmetic one.
        if await _cancellation_requested(session, run):
            return await _cancel_run(
                session,
                job,
                run,
                stage=BacktestRunState.PROVISIONING,
                progress={
                    "prepared_item_count": len(prepared_items),
                    "strategy_item_count": len(strategies),
                },
            )
        prepared = await _prepare_strategy(
            session,
            config=config,
            meta=meta,
            stream_bars=stream_bars,
            stream_ticks=stream_ticks,
            tick_data=manifest.manifest.get("tick_data"),
            load_funding_rows=load_funding_rows,
            capital_execution=capital_execution,
        )
        if isinstance(prepared, _PrepFailure):
            return await _fail_run(session, job, run, code=prepared.code, message=prepared.message)
        prepared_items.append(prepared)

    # Everything the engine needs is resolved -> the simulation itself starts NOW. This
    # is the stage a watching client actually cares about, and the checkpoint commit is
    # what makes it visible while the replay is still running.
    await _record_stage(
        session,
        run,
        event_type=RunEventType.RUN_STAGE_CHANGED,
        previous_state=BacktestRunState.PROVISIONING,
        state=BacktestRunState.RUNNING,
        detail={"strategy_item_count": len(prepared_items), "item_count": item_count},
    )
    run.state = BacktestRunState.RUNNING
    await session.commit()

    # RUNNING = bar-replay each prepared Strategy. Portfolio-level rules (cross-item,
    # doc 13 §8.4): resolved ONCE from the manifest snapshot; None (no rule set) keeps
    # every item's replay byte-identical to the pre-rules engine. Enforcement is
    # sequential in the manifest's deterministic pin order — each completed item's
    # closed-position windows become the NEXT items' constraints (an earlier item is
    # never re-simulated because of a later one; the engine surfaces this precedence as
    # an L4 warning). An engine error on ANY item fails the whole run.
    base_rules = resolve_portfolio_rules(capital_execution)
    # F-07 §4.4: the PINNED display labels, read once from the immutable manifest. They
    # are not part of ``execution_key``, so they cannot influence the replay — they only
    # travel with each item so the finished Result can name its rows without the reader
    # ever joining the live composition.
    item_labels = _manifest_item_labels(manifest.manifest)

    # Both of these are declared ahead of the branch because BOTH arms produce them and
    # neither owns them: the tail below (metrics, checkpoint #4, Result) must be reached by
    # exactly one path whichever arm ran.
    #
    # ``replay_progress`` is what checkpoint #4 reports about how far the replay got, and it
    # is bound HERE rather than read off a branch-local name. It used to read ``item_runs``,
    # which only the independent arm binds — so a cancel observed at checkpoint #4 on the
    # shared path raised ``UnboundLocalError`` instead of cancelling the run. Nothing caught
    # that until a negative control removed the in-loop checkpoint: the passing tests all
    # cancelled EARLIER, at #3b, and never reached the line.
    output: EngineOutput
    replay_progress: dict[str, Any] = {"strategy_item_count": len(prepared_items)}

    # ADR-0002 §3.2 / §11 + P-C2 §C.5 — the SHARED-clock branch, a SIBLING above the item
    # loop rather than a replacement for it. Wired and structurally unreachable: run
    # admission already refuses every shared run while the capability is ``future_dev``, and
    # ``_use_unified_clock`` reads that same flag, so no request, retry or Agent path can
    # construct a run that enters here. Lifting the flag is C9 / ADIM 20, not this slice.
    #
    # ``len(prepared_items) > 1`` is ADR §3.2's own wording — the phase loop is entered
    # "only when more than one item executes". With exactly one executing item the merged
    # axis IS that item's bar axis and the shared ledger IS its ledger, so A14 requires the
    # composition to keep replaying through ``run_engine`` byte-identically. The condition
    # lives HERE rather than inside ``_use_unified_clock`` because it is a different
    # invariant with a different source, and folding two reasons into one predicate would
    # leave neither of them stated.
    if len(prepared_items) > 1 and _use_unified_clock(capital_execution):
        unified = await _replay_shared_clock(
            session,
            job,
            run,
            prepared_items=prepared_items,
            manifest=manifest,
            item_count=item_count,
            item_labels=item_labels,
            base_rules=base_rules,
        )
        if not isinstance(unified, EngineOutput):
            # Already durable: the shared replay cancelled or failed the run and this is its
            # terminal reference, the same shape every other early return here carries.
            return unified
        output = unified
        # Every participant was driven to exhaustion on ONE clock — there is no per-item
        # replay count on this path, and reporting ticks under an item key would be a lie in
        # a durable event. ``unified_clock`` names the path the run actually took.
        replay_progress["replayed_item_count"] = len(prepared_items)
        replay_progress["unified_clock"] = True
    else:
        # INDEPENDENT PATH — unchanged (P-C2 §C.5 property 2). ``for prepared in
        # prepared_items:``, ``_replay_strategy``, ``PriorItemInterval`` and
        # ``combine_item_runs`` all stay exactly where they were; re-routing any of them
        # would silently re-price every independent composite Result.
        prior_intervals: list[PriorItemInterval] = []
        item_runs: list[ItemRun] = []
        for prepared in prepared_items:
            # O-06 safe checkpoint #3 — between two items' bar-replays, and (on the
            # first pass) immediately after the RUNNING commit. This is the checkpoint
            # a user watching a long simulation actually hits.
            if await _cancellation_requested(session, run):
                return await _cancel_run(
                    session,
                    job,
                    run,
                    stage=BacktestRunState.RUNNING,
                    progress={
                        "replayed_item_count": len(item_runs),
                        "strategy_item_count": len(prepared_items),
                    },
                )
            item_rules = (
                replace(
                    base_rules,
                    own_symbol=prepared.config.data.instrument_id,
                    prior_intervals=tuple(prior_intervals),
                )
                if base_rules is not None
                else None
            )
            replayed = _replay_strategy(
                prepared,
                execution_key=manifest.execution_key,
                item_count=item_count,
                portfolio_rules=item_rules,
                item_label=item_labels.get(prepared.item_id),
            )
            if isinstance(replayed, _PrepFailure):
                return await _fail_run(
                    session, job, run, code=replayed.code, message=replayed.message
                )
            if base_rules is not None and replayed.output is not None:
                prior_intervals.extend(
                    build_prior_intervals(
                        item_id=replayed.item_id,
                        symbol=prepared.config.data.instrument_id,
                        position_intervals=replayed.output.position_intervals,
                    )
                )
            item_runs.append(replayed)
        replay_progress["replayed_item_count"] = len(item_runs)

        # Enabled non-Strategy items (Trading Signal / Trade Log) are pinned + recorded for
        # traceability but run no standalone V1 bar-replay (F-04 honest boundary): their
        # execution effect is defined only as a Strategy data input. Disabled items were
        # already excluded from the snapshot (doc 01 §5.2) and never reach here.
        non_executing = _enabled_non_strategy_items(manifest.manifest)

        if len(item_runs) == 1 and not non_executing:
            # Byte-identical single-Strategy path: a lone enabled Strategy with nothing else
            # in the composition produces exactly the pre-F-04 engine output (no compose).
            output = item_runs[0].output  # type: ignore[assignment]
        else:
            # Portfolio starting capital: the shared pool P0 under shared allocation (taken
            # ONCE — each sleeve reports the same pool), else the sum of the strategies' own
            # initial capitals (independent mode). Realized PnL is additive either way.
            alloc_probe = resolve_allocation_execution(
                capital_execution, item_id=item_runs[0].item_id
            )
            if alloc_probe is not None:
                portfolio_initial = alloc_probe.initial_capital
            else:
                portfolio_initial = sum(
                    (
                        Decimal(str(r.output.summary["initial_capital"]))
                        for r in item_runs
                        if r.output
                    ),
                    Decimal("0"),
                )
            output = combine_item_runs(
                [*item_runs, *non_executing],
                portfolio_initial_capital=portfolio_initial,
                execution_key=manifest.execution_key,
                item_count=item_count,
                # Contribution's without-item fold follows the SAME capital rule as this
                # run: shared pool keeps P0, independent subtracts the item's own capital.
                shared_pool=alloc_probe is not None,
            )
    metric_values = derive_metric_values(output.summary)

    # O-06 safe checkpoint #4 — the LAST point at which no Result exists yet. This
    # is the checkpoint that actually enforces doc 15 §16 ("CANCELLED run no
    # BacktestResult üretir"): past this line the immutable Result root is written
    # and the run can only end SUCCEEDED. A cancel that arrives after this point is
    # honestly not honored — the response the caller got said ``requested`` under
    # the ``cancellation_safe_boundary`` policy, never ``cancelled``.
    if await _cancellation_requested(session, run):
        return await _cancel_run(
            session,
            job,
            run,
            stage=BacktestRunState.RUNNING,
            progress={**replay_progress, "engine_replay_complete": True},
        )

    result = await bt_repo.create_result(
        session,
        run=run,
        manifest=manifest,
        engine_output=output,
        metric_values=metric_values,
    )
    terminal_from = run.state
    run.result_id = result.result_id
    run.state = BacktestRunState.SUCCEEDED
    run.finished_at = datetime.now(UTC)

    # The terminal event closes the stream a reconnecting client is replaying — without
    # it a client that resumes from ``last_sequence`` would never learn the run ended.
    await bt_repo.record_run_event(
        session,
        run_id=run.run_id,
        event_type=RunEventType.RUN_SUCCEEDED,
        previous_state=terminal_from,
        state=BacktestRunState.SUCCEEDED,
        correlation_id=run.correlation_id,
        detail={"result_id": result.result_id, "manifest_hash": run.manifest_hash},
    )
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

    The worker reads ONLY the manifest; it never falls back to the current Mainboard,
    Package Library or a 'latest' dataset row (doc 15 §15). K-04 widens the gate from
    the Mainboard work-object pins to EVERY dependency the manifest now records: the
    strategy mirror revision, each transitive indicator/condition/reference package
    revision and its resolver (ESP) revisions, the pinned market dataset revision (and
    its dataset root's ACTIVE state — a soft-deleted dataset is unresolved, never
    silently re-resolved to the newest revision), every research feed revision, and the
    external Trading Signal / Trade Log import revision. A pre-K-04 manifest carries
    none of those groups and is checked exactly as before."""
    missing: list[str] = []
    items = manifest.get("mainboard_items", [])
    # O-24b: one IN() read for the whole pin set. An id with no row is absent from the
    # map, so it lands in ``missing`` exactly as the per-id ``session.get`` miss did —
    # same ids, same order, same RUN_FAILED_MANIFEST_RESOLUTION message.
    revisions = await mb_repo.get_work_object_revisions(
        session,
        [
            str(item["selected_revision_id"])
            for item in items
            if item.get("selected_revision_id") is not None
        ],
    )
    for item in items:
        revision_id = item.get("selected_revision_id")
        if revision_id is None:
            missing.append(str(item.get("item_id")))
            continue
        if revisions.get(str(revision_id)) is None:
            missing.append(str(revision_id))
    missing.extend(await _unresolved_package_pins(session, manifest))
    missing.extend(await _unresolved_data_pins(session, manifest))
    missing.extend(await _unresolved_external_pins(session, manifest))
    return missing


async def _unresolved_package_pins(session: AsyncSession, manifest: dict[str, Any]) -> list[str]:
    """Strategy revision + transitive package/resolver revisions that no longer resolve."""
    missing: list[str] = []
    entries = manifest.get("strategy_package_context") or []
    pinned_by_entry = [_pinned_package_ids(entry) for entry in entries]
    # O-24b: one IN() read for EVERY strategy's transitive package + resolver revisions,
    # instead of one per block/condition/leg. An id with no row is absent from the map, so
    # the ``is None`` branch below still appends it — same ids, same order.
    revisions = await pkg_repo.get_revisions(
        session, [revision_id for pinned in pinned_by_entry for revision_id in pinned]
    )
    for entry, pinned_ids in zip(entries, pinned_by_entry, strict=True):
        strategy_revision_id = entry.get("strategy_revision_id")
        if strategy_revision_id is not None:
            mirror = await strat_repo.get_strategy_revision(session, str(strategy_revision_id))
            if mirror is None:
                missing.append(str(strategy_revision_id))
        for revision_id in pinned_ids:
            if revisions.get(revision_id) is None:
                missing.append(revision_id)
    return missing


def _pinned_package_ids(entry: dict[str, Any]) -> list[str]:
    """A manifest strategy entry's package revision ids, then its resolver (ESP) ids."""
    pinned_ids = [
        str(pkg["package_revision_id"])
        for pkg in entry.get("package_revisions") or []
        if pkg.get("package_revision_id")
    ]
    pinned_ids.extend(
        str(ref["embedded_revision_id"])
        for ref in entry.get("resolver_revisions") or []
        if ref.get("embedded_revision_id")
    )
    return pinned_ids


async def _unresolved_data_pins(session: AsyncSession, manifest: dict[str, Any]) -> list[str]:
    """Market/research dataset pins that no longer resolve to an ACTIVE root revision."""
    missing: list[str] = []
    entries = manifest.get("data_time_context") or []
    # O-24b: two IN() reads (market + research) for every item's data pins, instead of one
    # per pin. A pin with no row is absent from the map, so its root stays ``None`` and it
    # lands in ``missing`` exactly as before — a soft-deleted dataset is still unresolved.
    market_revisions = await md_repo.get_revisions(
        session,
        [
            str(entry["market_dataset_revision_id"])
            for entry in entries
            if entry.get("market_dataset_revision_id") is not None
        ],
    )
    research_revisions = await research_repo.get_revisions(
        session,
        [
            str(research_revision_id)
            for entry in entries
            for research_revision_id in entry.get("research_dataset_revision_ids") or []
        ],
    )
    for entry in entries:
        market_revision_id = entry.get("market_dataset_revision_id")
        if market_revision_id is not None:
            revision = market_revisions.get(str(market_revision_id))
            root = (
                await md_repo.get_dataset_root(session, revision.entity_id)
                if revision is not None
                else None
            )
            if root is None or root.deletion_state != DeletionState.ACTIVE:
                missing.append(str(market_revision_id))
        for research_revision_id in entry.get("research_dataset_revision_ids") or []:
            research = research_revisions.get(str(research_revision_id))
            research_root = (
                await research_repo.get_dataset_root(session, research.entity_id)
                if research is not None
                else None
            )
            if research_root is None or research_root.deletion_state != DeletionState.ACTIVE:
                missing.append(str(research_revision_id))
    return missing


async def _unresolved_external_pins(session: AsyncSession, manifest: dict[str, Any]) -> list[str]:
    """Trading Signal / Trade Log import revisions that no longer resolve.

    Uses the SAME probe Ready Check and the manifest builder used, so a normalized
    event revision / canonical record batch that has disappeared fails the run closed
    instead of replaying an external object with no import evidence."""
    missing: list[str] = []
    for entry in manifest.get("external_object_context") or []:
        revision_id = entry.get("work_object_revision_id")
        if revision_id is None:
            continue
        if entry.get("item_kind") == MainboardItemKind.TRADE_LOG:
            resolved: Any = await readiness_repo.resolve_trade_log_batch(session, str(revision_id))
        else:
            resolved = await readiness_repo.resolve_signal_revision(session, str(revision_id))
        if resolved is None:
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
    selected = [
        item
        for item in manifest.get("mainboard_items", [])
        if item.get("item_kind") == MainboardItemKind.STRATEGY
        and item.get("enabled") is not False
        and item.get("selected_revision_id") is not None
    ]
    # O-24b: one IN() read for every enabled Strategy's pinned revision. A pin with no row
    # is absent from the map, so it is still skipped here and still fails the run closed
    # upstream in ``_unresolved_pins`` — never silently re-resolved.
    revisions = await mb_repo.get_work_object_revisions(
        session, [str(item["selected_revision_id"]) for item in selected]
    )
    for item in selected:
        revision_id = item["selected_revision_id"]
        revision = revisions.get(str(revision_id))
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


def _manifest_item_labels(manifest: dict[str, Any]) -> dict[str, str]:
    """Read the run manifest's pinned display labels (F-07 §4.4).

    ``build_run_manifest`` already projected these out of the composition snapshot into
    ``mainboard_item_labels`` — a key deliberately OUTSIDE the hashed execution content,
    so reading it can never perturb ``execution_key``. A manifest written before the key
    existed yields an empty map and every row falls back to its raw id.
    """
    raw = manifest.get("mainboard_item_labels")
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str) and v}


def _enabled_non_strategy_items(manifest: dict[str, Any]) -> list[ItemRun]:
    """Enabled Trading Signal / Trade Log items — pinned + recorded, no standalone run.

    F-04 honest boundary: these EXTERNAL work objects affect execution only as a
    Strategy data input, so the V1 bar-replay engine runs no standalone simulation for
    them. They are still surfaced (``output=None``) in the composite diagnostics so
    every participating object is traceable; disabled items were already excluded from
    the snapshot and never reach here."""
    items: list[ItemRun] = []
    labels = _manifest_item_labels(manifest)
    for item in manifest.get("mainboard_items", []):
        if item.get("item_kind") == MainboardItemKind.STRATEGY:
            continue
        if item.get("enabled") is False:
            continue
        revision_id = item.get("selected_revision_id")
        item_id = str(item.get("item_id"))
        items.append(
            ItemRun(
                item_id=item_id,
                item_kind=str(item.get("item_kind")),
                root_id=item.get("root_id"),
                revision_id=str(revision_id) if revision_id is not None else None,
                output=None,
                # F-07 §4.4 — a non-executing item still appears in the per-item
                # breakdown, so it needs its pinned name just as much.
                item_label=labels.get(item_id),
            )
        )
    return items


@dataclass(frozen=True, slots=True)
class _PreparedStrategy:
    """One enabled Strategy with every engine input resolved, ready to replay.

    Everything here is settled while the run is PROVISIONING; nothing in it touches
    the database, so the replay stage is pure compute over already-resolved pins."""

    item_id: str
    item_kind: str
    root_id: Any
    revision_id: str
    config: StrategyConfig
    bar_batches: Iterator[list[dict[str, Any]]]
    tick_batches: Iterator[list[dict[str, Any]]] | None
    indicator_plan: Any
    funding_schedule: Any
    timeframe: str | None
    allocation: Any


async def _prepare_strategy(
    session: AsyncSession,
    *,
    config: StrategyConfig,
    meta: dict[str, Any],
    stream_bars: BarBatchStreamer,
    stream_ticks: TickBatchStreamer,
    tick_data: dict[str, Any] | None,
    load_funding_rows: FundingRowLoader | None,
    capital_execution: dict[str, Any] | None,
) -> _PreparedStrategy | _PrepFailure:
    """Resolve every engine input for ONE enabled Strategy (F-04/F-05/F-06/F-11).

    Mirrors the pre-F-04 single-strategy resolution chain exactly (asset -> F-05
    range/instrument filter -> F-06 indicator plan -> funding source -> tick pin ->
    allocation sleeve), so a lone Strategy replays byte-identically. Every failure is
    attributed to its ``item_id`` for traceability and fails the whole run upstream —
    a selected Strategy is never silently skipped. Nothing here runs the engine: the
    split is what lets the run sit in PROVISIONING for exactly the resolution work and
    enter RUNNING for exactly the simulation (O-05)."""
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
    return _PreparedStrategy(
        item_id=item_id,
        item_kind=meta["item_kind"],
        root_id=meta["root_id"],
        revision_id=meta["revision_id"],
        config=config,
        bar_batches=bar_batches,
        tick_batches=tick_batches,
        indicator_plan=indicator_plan,
        funding_schedule=funding_schedule,
        timeframe=base_timeframe,
        allocation=allocation,
    )


def _replay_strategy(
    prepared: _PreparedStrategy,
    *,
    execution_key: str,
    item_count: int,
    portfolio_rules: PortfolioRules | None = None,
    item_label: str | None = None,
) -> ItemRun | _PrepFailure:
    """Bar-replay ONE prepared Strategy. Pure compute — no database access.

    Runs while the durable run state is RUNNING. An engine error is attributed to
    the item and fails the whole run upstream (F-04)."""
    try:
        output = run_engine(
            strategy_config=prepared.config,
            bar_batches=prepared.bar_batches,
            execution_key=execution_key,
            item_count=item_count,
            indicator_plan=prepared.indicator_plan,
            timeframe=prepared.timeframe,
            allocation=prepared.allocation,
            funding=prepared.funding_schedule,
            tick_batches=prepared.tick_batches,
            portfolio_rules=portfolio_rules,
        )
    except Exception as exc:
        return _PrepFailure(
            RunFailureCode.ENGINE_ERROR,
            f"Strategy item '{prepared.item_id}': engine error during bar-replay: {exc}",
        )
    return ItemRun(
        item_id=prepared.item_id,
        item_kind=prepared.item_kind,
        root_id=prepared.root_id,
        revision_id=prepared.revision_id,
        output=output,
        item_label=item_label,
    )


@dataclass(frozen=True, slots=True)
class _SharedClockInputs:
    """Everything ``iter_portfolio`` needs for ONE shared-pool run, resolved once.

    Assembled from the SAME pins the independent path replays from, so the two branches can
    never disagree about what the manifest said — the participants wrap steppers built by
    ``engine._build_stepper`` with ``_replay_strategy``'s own argument list, and the pool
    figures come from the ``AllocationExecution`` each item already carries."""

    participants: list[ItemParticipant]
    items: list[PinnedItem]
    pool_initial: Decimal
    shares: dict[str, Decimal]
    reserve_percent: Decimal
    compound: bool
    conflict_policy: str | None
    max_total_exposure_notional: Decimal | None


def _shared_clock_inputs(
    prepared_items: list[_PreparedStrategy],
    *,
    manifest: dict[str, Any],
    execution_key: str,
    item_count: int,
    item_labels: dict[str, str],
    base_rules: PortfolioRules | None,
) -> _SharedClockInputs | _PrepFailure:
    """Turn the resolved pins into participants and pool parameters. Pure — no I/O.

    ``pin_ordinal`` comes from the MANIFEST's deterministic pin order and never from a list
    position: ``prepared_items`` is that order FILTERED to the executing Strategy items, so
    the two coincide only when nothing else is pinned (``ItemBarStream``'s own docstring
    makes the same point, and ``portfolio_engine._ordered`` enforces the agreement between
    an identity's ordinal and its stream's).

    ``max_position_notional`` is deliberately NOT supplied. The §6 per-item cap is stored as
    a PERCENT and only resolves to money at an entry price, and the sizing chain already
    binds it inside ``desired_size`` (``sizing.planned_size`` -> ``_position_size`` ->
    ``_clamp_to_limits``). ``arbitrate``'s parameter is the ledger-layer form of the same
    limit and its docstring says it is "passed through to the ledger as given and never
    inferred" — inventing a notional here would be a second reading of one config field.

    The participant is built through ``participant.build_engine_participant`` rather than by
    naming ``ItemIdentity`` / ``ItemBarStream`` here. Those two live in contained
    unified-clock modules whose production importers are an allowlist a human signed with
    exactly ONE module in it; constructing them in this file would widen that list by a
    second, UNSIGNED module. The worker is a CALLER of the phase loop, never an IMPORTER of
    its vocabulary — which is why the signed allowlist is untouched by this slice."""
    pin_ordinals = {
        str(entry.get("item_id")): ordinal
        for ordinal, entry in enumerate(manifest.get("mainboard_items", []))
    }
    participants: list[ItemParticipant] = []
    shares: dict[str, Decimal] = {}
    # The loop variable is ``pinned``, NOT the name the independent item loop uses. That
    # loop's header is a LITERAL the containment gate greps for to prove it survived the
    # wiring, and a second copy of that exact line anywhere in this module — code OR
    # comment, the scan cannot tell them apart — lets the gate stay green with the real
    # loop deleted, which is the silent re-price of every independent composite Result.
    # Measured with a negative control: removing the real loop left the gate GREEN until
    # this name was changed.
    for pinned in prepared_items:
        allocation = pinned.allocation
        if allocation is None:
            # The run ASKS for shared capital (``_use_unified_clock`` said so) but this
            # item's snapshot resolves to no sleeve — a missing/non-positive pool P0 or an
            # unreadable plan config. Failing closed is the only honest answer: sizing the
            # item from its own ``initial_capital`` instead would run a shared composition
            # on independent capital under a shared Result's label.
            return _PrepFailure(
                RunFailureCode.MANIFEST_RESOLUTION,
                f"Strategy item '{pinned.item_id}': the run requests SHARED capital but "
                "its pinned capital_execution snapshot resolves to no allocation sleeve.",
            )
        item_id = pinned.item_id
        stepper = _build_stepper(
            strategy_config=pinned.config,
            execution_key=execution_key,
            item_count=item_count,
            indicator_plan=pinned.indicator_plan,
            timeframe=pinned.timeframe,
            allocation=allocation,
            funding=pinned.funding_schedule,
            tick_batches=pinned.tick_batches,
            # Cross-item precedence is RETIRED on this path (ADR §12 row 19, P-C2 §C.5
            # seam #5): the loop arbitrates conflict and exposure globally at P5/P6b, so
            # also handing the item the sequential ``PortfolioRules`` would enforce one
            # rule twice under two different order-dependences. ``prior_intervals`` is
            # built inside the independent branch and never reaches a participant.
            portfolio_rules=None,
        )
        participants.append(
            build_engine_participant(
                item_id=item_id,
                item_kind=pinned.item_kind,
                pin_ordinal=pin_ordinals[item_id],
                root_id=str(pinned.root_id) if pinned.root_id is not None else None,
                selected_revision_id=pinned.revision_id,
                item_label=item_labels.get(item_id),
                instrument_id=pinned.config.data.instrument_id,
                stepper=stepper,
                bar_batches=pinned.bar_batches,
            )
        )
        shares[item_id] = allocation.item_share_percent

    # P0, R0 and the compounding mode are properties of the PLAN, not of an item: every
    # ``AllocationExecution`` projects them from the same ``capital_execution`` snapshot and
    # only ``item_share_percent`` differs. Reading them off the first item is therefore a
    # read of the plan, not a choice between candidates.
    plan = prepared_items[0].allocation
    max_total_exposure_notional: Decimal | None = None
    if base_rules is not None:
        if base_rules.exposure_percent_invalid:
            # A SET-but-unreadable / non-positive cap admits NOTHING, which is verbatim how
            # the shipped single-item engine reads it — never silently uncapped.
            max_total_exposure_notional = _ZERO.quantize(_MONEY)
        elif base_rules.max_total_exposure_percent is not None:
            # The same conversion the engine prologue applies, against the same base (the
            # pool under allocation) and with the same quantization, so one configured
            # percent cannot mean two amounts depending on which branch replayed it.
            max_total_exposure_notional = (
                plan.initial_capital * base_rules.max_total_exposure_percent / _HUNDRED
            ).quantize(_MONEY)

    symbols = {p.item_id: p.config.data.instrument_id for p in prepared_items}
    timeframes = {p.item_id: p.timeframe for p in prepared_items}
    items: list[PinnedItem] = []
    for entry in manifest.get("mainboard_items", []):
        if entry.get("enabled") is False:
            continue
        entry_id = str(entry.get("item_id"))
        revision_id = entry.get("selected_revision_id")
        items.append(
            PinnedItem(
                item_id=entry_id,
                item_kind=str(entry.get("item_kind")),
                root_id=entry.get("root_id"),
                revision_id=str(revision_id) if revision_id is not None else None,
                # F-07 §4.4 — the PINNED label, exactly as the sequential fold reads it. A
                # non-executing Trading Signal / Trade Log needs one just as much: the
                # projection gives it a row, and a row that cannot be named cannot be
                # attributed either.
                item_label=item_labels.get(entry_id),
                symbol=symbols.get(entry_id),
                timeframe=timeframes.get(entry_id),
            )
        )
    return _SharedClockInputs(
        participants=participants,
        items=items,
        pool_initial=plan.initial_capital,
        shares=shares,
        reserve_percent=plan.reserve_percent,
        compound=plan.compound,
        conflict_policy=base_rules.conflict_policy if base_rules is not None else None,
        max_total_exposure_notional=max_total_exposure_notional,
    )


async def _replay_shared_clock(
    session: AsyncSession,
    job: Job,
    run: Any,
    *,
    prepared_items: list[_PreparedStrategy],
    manifest: Any,
    item_count: int,
    item_labels: dict[str, str],
    base_rules: PortfolioRules | None,
) -> EngineOutput | dict[str, Any]:
    """Co-simulate every pinned Strategy on ONE merged clock over ONE shared pool.

    Returns the composite ``EngineOutput`` on success, or the DURABLE terminal reference of
    a run this function already cancelled or failed — the same two shapes ``run_backtest``'s
    independent branch produces, so the caller's tail (metrics, checkpoint #4, Result) is
    reached by exactly one path.

    **Unreachable from any production request as shipped.** Run admission
    (``commands/backtest_run.py``) refuses every shared run while the capability is
    ``future_dev``, and ``_use_unified_clock`` reads the same flag, so no HTTP call, no
    retry and no Agent path can construct a run that arrives here (P-C2 §C.5)."""
    try:
        inputs = _shared_clock_inputs(
            prepared_items,
            manifest=manifest.manifest,
            execution_key=manifest.execution_key,
            item_count=item_count,
            item_labels=item_labels,
            base_rules=base_rules,
        )
    except Exception as exc:
        # The adapter refuses ELEVEN strategy shapes at construction, before a single bar is
        # admitted (``participant._unsupported_shapes``), and ``_build_stepper`` has its own
        # fail-closed prologue. Mirrors ``_replay_strategy``'s handling of an engine error on
        # the independent path: a shape this build cannot drive fails the RUN, terminally,
        # rather than escaping as a job exception that redelivery would replay forever.
        return await _fail_run(
            session,
            job,
            run,
            code=RunFailureCode.ENGINE_ERROR,
            message=f"Shared-clock run could not be pinned: {exc}",
        )
    if isinstance(inputs, _PrepFailure):
        return await _fail_run(session, job, run, code=inputs.code, message=inputs.message)

    ticks = iter_portfolio(
        inputs.participants,
        pool_initial=inputs.pool_initial,
        shares=inputs.shares,
        reserve_percent=inputs.reserve_percent,
        compound=inputs.compound,
        conflict_policy=inputs.conflict_policy,
        max_total_exposure_notional=inputs.max_total_exposure_notional,
    )
    tick_index = 0
    portfolio_run: Any
    while True:
        # Drained by hand rather than with ``for``: a plain loop DISCARDS a generator's
        # return value, and the assembled ``PortfolioRun`` is exactly that value. The
        # ``next`` call sits inside the try and the cancellation ``await`` OUTSIDE it, so a
        # database error on the checkpoint stays a retryable job exception instead of being
        # relabelled as an engine failure and burying the run.
        try:
            next(ticks)
        except StopIteration as exhausted:
            portfolio_run = exhausted.value
            break
        except Exception as exc:
            return await _fail_run(
                session,
                job,
                run,
                code=RunFailureCode.ENGINE_ERROR,
                message=f"Shared-clock co-simulation failed at tick {tick_index}: {exc}",
            )
        # O-06 safe checkpoint #3b — the merged axis deletes the between-items boundary
        # checkpoint #3 sits on, so without this a long shared run would be uncancellable
        # (ADR §14 A21). It lands between two COMMITTED ticks, which is the P9 boundary
        # ADR §11 names as the only safe one, and the ``PortfolioRun`` is assembled only
        # after the generator is exhausted — so a cancel here still precedes every Result.
        if tick_index % _TICK_CHECKPOINT_STRIDE == 0 and await _cancellation_requested(
            session, run
        ):
            return await _cancel_run(
                session,
                job,
                run,
                stage=BacktestRunState.RUNNING,
                progress={
                    "replayed_tick_count": tick_index,
                    "strategy_item_count": len(prepared_items),
                },
            )
        tick_index += 1

    try:
        return project_portfolio_run(
            portfolio_run,
            items=inputs.items,
            execution_key=manifest.execution_key,
            item_count=item_count,
        )
    except Exception as exc:
        # The projection fails closed on a traded item with no pinned record, a booked close
        # with no open before it and a position priced at nothing. Each would otherwise
        # reach an IMMUTABLE Result as a plausible-looking row.
        return await _fail_run(
            session,
            job,
            run,
            code=RunFailureCode.ENGINE_ERROR,
            message=f"Shared-clock run could not be projected into a Result: {exc}",
        )


async def _record_stage(
    session: AsyncSession,
    run: Any,
    *,
    event_type: RunEventType,
    previous_state: Any,
    state: BacktestRunState,
    detail: dict[str, Any] | None = None,
) -> None:
    """Write ONE durable stage event + its audit/outbox twins (doc 15 §12).

    Three planes, one transaction: the ``backtest_run_event`` row is what a client
    replays by ``sequence_no``; the ``audit_events`` row keeps the shipped dotted
    ``backtest.*`` kind convention; the outbox row fans the change out over SSE
    (``resource_type`` starting with ``backtest`` maps to ``backtest.run.updated``).
    """
    await bt_repo.record_run_event(
        session,
        run_id=run.run_id,
        event_type=event_type,
        previous_state=previous_state,
        state=state,
        correlation_id=run.correlation_id,
        detail=detail,
    )
    audit_repo.add_audit_event(
        session,
        event_kind=_STAGE_AUDIT_KIND[event_type],
        actor_principal_id=run.requested_by_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=run.run_id,
        target_entity_type=_RUN_TARGET,
        previous_state=str(previous_state) if previous_state is not None else None,
        new_state=str(state),
        correlation_id=run.correlation_id,
        metadata=detail,
    )
    audit_repo.add_outbox_event(
        session,
        event_type=_STAGE_AUDIT_KIND[event_type],
        resource_type=_RUN_TARGET,
        resource_id=run.run_id,
        payload={"run_id": run.run_id, "state": str(state), "event_type": str(event_type)},
        correlation_id=run.correlation_id,
    )


async def _cancellation_requested(session: AsyncSession, run: Any) -> bool:
    """Is an authorized cancellation pending for this run? (O-06, doc 15 §8.4)

    Called ONLY at stage boundaries, where the session holds no pending changes to
    ``run`` — so this refresh cannot discard work. Refreshing the whole row rather
    than selecting one column is deliberate: it also pulls in the requester and the
    ``row_version`` the cancel command bumped on another connection, so the terminal
    write below neither clobbers that bump nor attributes the cancellation to nobody.
    """
    await session.refresh(run)
    return run.cancel_requested_at is not None


async def _cancel_run(
    session: AsyncSession,
    job: Job,
    run: Any,
    *,
    stage: BacktestRunState,
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Honor a pending cancellation at a safe checkpoint (doc 15 §8.4, §16).

    Writes the terminal state, the ``RUN_CANCELLED`` stream event that closes the
    replay a reconnecting client is following, the cancellation audit, and the
    finalized job row — and NO Backtest Result (CR-03), so the run never produces a
    current-result card or a Results History entry either.

    Partial diagnostics survive in the event ``detail``: which checkpoint stopped
    the run and how far it got. HONEST BOUNDARY: they do NOT survive as
    ``diagnostic_artifact`` rows, because that table is FK-bound to a
    ``backtest_result`` and only a SUCCEEDED run may create one — writing a Result
    to host cancellation diagnostics would break the very rule this path enforces.
    """
    reason = (
        f"Cancellation honored at the {stage.value} safe checkpoint; "
        "no Backtest Result was materialized."
    )
    terminal_from = run.state
    run.state = BacktestRunState.CANCELLED
    run.cancellation_reason = reason
    run.finished_at = datetime.now(UTC)
    detail: dict[str, Any] = {
        "cancellation_reason": reason,
        "cancelled_at_stage": stage.value,
        "requested_by_principal_id": run.cancel_requested_by_principal_id,
        "result_id": None,
        **(progress or {}),
    }
    await bt_repo.record_run_event(
        session,
        run_id=run.run_id,
        event_type=RunEventType.RUN_CANCELLED,
        previous_state=terminal_from,
        state=BacktestRunState.CANCELLED,
        correlation_id=run.correlation_id,
        detail=detail,
    )
    _emit_cancellation_audit(session, run=run, detail=detail)
    # The job did complete — it produced a terminal run — but it did not succeed;
    # ``cancelled`` is the honest generic job outcome (Module 20 §6) and is terminal,
    # so no redelivery re-attempts it.
    job.status = JobStatus.CANCELLED
    job.finished_at = datetime.now(UTC)
    result_ref = {
        "run_id": run.run_id,
        "state": BacktestRunState.CANCELLED.value,
        "result_id": None,
        "cancellation_reason": reason,
    }
    job.result_ref = result_ref
    return result_ref


def _emit_cancellation_audit(session: AsyncSession, *, run: Any, detail: dict[str, Any]) -> None:
    """Terminal cancellation audit + SSE outbox twin (doc 15 §16).

    Attributed to the SYSTEM SERVICE acting on the requester's principal: the human
    intent was already audited by ``cancel_backtest_run`` as
    ``backtest.run_cancellation_requested``; THIS row records the worker actually
    carrying it out at a checkpoint."""
    audit_repo.add_audit_event(
        session,
        event_kind="backtest.run_cancelled",
        actor_principal_id=run.cancel_requested_by_principal_id or run.requested_by_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=run.run_id,
        target_entity_type=_RUN_TARGET,
        new_state=str(run.state),
        correlation_id=run.correlation_id,
        metadata={"manifest_hash": run.manifest_hash, **detail},
    )
    audit_repo.add_outbox_event(
        session,
        event_type="backtest.run_cancelled",
        resource_type=_RUN_TARGET,
        resource_id=run.run_id,
        payload={"run_id": run.run_id, "state": str(run.state), **detail},
        correlation_id=run.correlation_id,
    )


async def _fail_run(
    session: AsyncSession,
    job: Job,
    run: Any,
    *,
    code: RunFailureCode,
    message: str,
) -> dict[str, Any]:
    terminal_from = run.state
    run.state = BacktestRunState.FAILED
    run.failure_code = code.value
    run.failure_message = message
    run.finished_at = datetime.now(UTC)
    # Terminal event: closes the replay stream for a client watching by sequence.
    await bt_repo.record_run_event(
        session,
        run_id=run.run_id,
        event_type=RunEventType.RUN_FAILED,
        previous_state=terminal_from,
        state=BacktestRunState.FAILED,
        correlation_id=run.correlation_id,
        detail={"failure_code": code.value, "failure_message": message},
    )
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
