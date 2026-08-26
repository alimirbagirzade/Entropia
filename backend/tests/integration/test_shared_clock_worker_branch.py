"""`C4` (E5) — the worker's shared-clock branch, proved behaviourally (P-C2 §C.6 part 2).

The containment gate used to buy one thing for free: ``run_portfolio`` had NO production
caller, so a text scan settled the whole question. `C4` wires the branch, so that scan is
narrowed to an authorised-caller allowlist and the property it can no longer prove —
*reachability* — has to be proved by running the worker. This module is that proof.

The four facts, and why each is separate:

* an INDEPENDENT multi-item run never reaches the unified loop, with the flag exactly as
  shipped. This is the one that matters commercially: independent multi-item runs are a
  first-class mode (doc 13 §1.1) and re-routing them would silently re-price every composite
  Result ever produced — no flag, no ``ENGINE_VERSION`` bump, nothing a reader could see;
* a LIFTED flag alone does not route it either, which pins the second conjunct of
  ``_use_unified_clock`` through the real worker rather than through the predicate;
* with the flag lifted AND shared capital requested, the branch really does run, really does
  produce a Result from ``project_portfolio_run``, and the composite curve is time-ordered —
  otherwise `C4` would have wired a branch that merely type-checks;
* the tick-strided cancellation checkpoint (ADR §14 A21) is genuinely reachable, and a cancel
  observed there produces NO Result (doc 15 §16).

**The lift fixture is test-owned and production cannot reach it.** It patches
``capability.SHARED_ALLOCATION_STATUS`` for the duration of a block;
``tests/unit/test_shared_allocation_two_world_gate.py`` asserts structurally that there is no
env var, no setter and no second assignment in ``backend/src`` that could do the same. Not one
``future_dev`` pin is weakened here — those pins ARE the containment, and `C9` / ADIM 20 moves
them deliberately, behind the ADR §16 human gate.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.jobs import backtest_engine as worker
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.domain.allocation import capability
from entropia.domain.backtest.enums import BacktestRunState, RunEventType, RunFailureCode
from entropia.domain.backtest.execution.portfolio import COMPOSITION_CURVE_WARNING
from entropia.domain.backtest.execution.portfolio_projection import ENGINE_KIND as UNIFIED_KIND
from entropia.domain.identity import Actor
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    ResolutionKind,
)
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    BacktestRunEvent,
    ResultArtifactChecksum,
    ResultEquityPoint,
    ResultSummary,
    SignalEventRow,
)
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from tests.integration.test_backtest_persistence import (
    USER1,
    _count,
    _e2e_bars,
    _empty_composition,
    _run_diagnostics,
    _seed_indicator_package,
    _seed_principals,
    _strategy_payload,
    _two_strategy_composition,
)

pytestmark = pytest.mark.integration

#: What ``combine_item_runs`` stamps on a sequentially folded composite. The unified loop's
#: projection stamps :data:`UNIFIED_KIND` instead, so the two paths are distinguishable from
#: the persisted artifact alone — which is the only place a reader could ever tell.
_SEQUENTIAL_KIND = "v1_bar_replay_composition"

#: The artifacts whose stored checksum is a function of the RUN and of nothing else. The
#: fifth stored checksum, ``diagnostics``, is deliberately absent — see
#: :func:`_artifact_checksums` for the measurement that put it there.
_CONTENT_ARTIFACTS = ("equity_curve", "trade_ledger", "signal_events", "filtered_events")

#: ``(declared timeframe, bar step, bar count, offset from midnight)`` for the two items of
#: :func:`_heterogeneous_composition`. The six-hour offset is load-bearing and is explained
#: where the bars are built.
_HETEROGENEOUS_CADENCES = (
    ("1D", timedelta(days=1), 22, timedelta(hours=6)),
    ("12h", timedelta(hours=12), 43, timedelta(0)),
)


@contextmanager
def _lifted(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Force the ``active_v1`` world for the duration of the block.

    Patching the module GLOBAL, not a re-imported copy: ``_use_unified_clock`` and the
    admission guard both hold a reference to the *function*
    ``shared_allocation_is_executable``, whose ``__globals__`` IS this module's dict, so they
    observe the patch without importing anything from here. Same fixture, same reasoning as
    ``tests/unit/test_shared_allocation_two_world_gate.py``."""
    with monkeypatch.context() as patch:
        patch.setattr(capability, "SHARED_ALLOCATION_STATUS", "active_v1")
        yield


def _shared_safe_payload(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """``_strategy_payload`` with the two shapes the shared clock cannot drive removed.

    Both removals are refusals ``participant._unsupported_shapes`` states, and neither is a
    fixture convenience:

    * ``next_candle_open`` DEFERS the fill to ``_phase_open_fills``, a phase the shared path
      never runs — the pool would arbitrate an entry the item never opens at that tick;
    * ``same_direction_stacking`` defaults to ``allow_stacking`` in the SCHEMA, and a stack
      opens a second entry inside ``_phase_tail`` with no ``PortfolioSnapshot`` behind it.

    That second one is `C3`'s recorded finding: the schema default is a shape the adapter
    refuses, so most saved strategies would fall out of a shared run. Turning it into a
    user-visible admission blocker is `C6` and is a PRODUCT decision, not this slice's."""
    payload = _strategy_payload(*args, **kwargs)
    payload["data"]["execution"] = {
        "entry_timing": "current_candle_close",
        "exit_timing": "current_candle_close",
    }
    payload["conflict_position_handling"] = {"same_direction_stacking": "ignore"}
    return payload


async def _attach_strategy(
    session: Any,
    actor: Actor,
    workspace_id: str,
    *,
    pkg_rev_id: str,
    shared_safe: bool,
) -> str:
    """Seed one Strategy (its own market revision + processed asset) onto a workspace.

    A local copy of ``test_backtest_persistence._attach_strategy`` for exactly one reason:
    that one hard-codes the payload, and half of this module needs the shared-safe variant.
    Everything else about the seeding is identical, deliberately."""
    market_root, market_rev = await md_repo.create_market_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        market_data_type=MarketDataType.OHLCV,
        payload={"note": "seed bars"},
        instrument_id=None,
    )
    market_rev.revision_state = MarketRevisionState.APPROVED
    await session.flush()
    md_repo.add_processed_asset(
        session,
        entity_id=market_root.entity_id,
        object_key=f"market/processed/{market_root.entity_id}/seed.parquet",
        content_digest="seed-bars",
        size_bytes=4096,
        revision_id=market_rev.revision_id,
        row_count=22,
    )
    await session.flush()
    build = _shared_safe_payload if shared_safe else _strategy_payload
    work_object = await mb_cmd.create_work_object(
        session,
        actor,
        object_kind="strategy",
        payload=build(
            market_root.entity_id,
            market_rev.revision_id,
            market_rev.content_hash,
            indicator_revision_id=pkg_rev_id,
        ),
    )
    await mb_cmd.attach_mainboard_item(
        session,
        actor,
        workspace_id=workspace_id,
        root_id=work_object["root_id"],
        revision_id=work_object["revision_id"],
        item_kind="strategy",
    )
    return str(work_object["revision_id"])


async def _composition(session: Any, actor: Actor, *, count: int, shared_safe: bool) -> str:
    """A composition with ``count`` enabled Strategies (shared indicator, own market rev)."""
    workspace_id = await _empty_composition(session, actor)
    pkg_rev_id = await _seed_indicator_package(session)
    for _ in range(count):
        await _attach_strategy(
            session, actor, workspace_id, pkg_rev_id=pkg_rev_id, shared_safe=shared_safe
        )
    await session.commit()
    return str(workspace_id)


async def _enable_shared_pool(session: Any, actor: Actor, composition_id: str) -> None:
    """Enable a shared-pool plan splitting P0 EVENLY across every strategy item.

    Evenly rather than 100/0: a 0% share is a legal plan but the item it belongs to can never
    open a position, so a "two-item" run would in fact drive one participant and prove less
    than it looks like it proves. ``Decimal`` rather than float division so the shares sum to
    exactly 100 for the counts this module uses."""
    items = [
        it
        for it in await mb_repo.list_active_items(session, composition_id)
        if str(it.item_kind) == "strategy"
    ]
    share = str(Decimal(100) / Decimal(len(items)))
    await alloc_cmd.upsert_allocation_draft(
        session,
        actor,
        composition_id=composition_id,
        expected_row_version=None,
        enabled=True,
        initial_capital={"amount": "50000.00", "currency": "USDT"},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent="0",
        entries=[
            {
                "composition_item_id": item.item_id,
                "active": True,
                "equity_share_percent": share,
            }
            for item in items
        ],
        idempotency_key="c4-shared-pool",
    )
    await session.commit()


async def _persisted_equity_timestamps(session: Any, result_id: str) -> list[str]:
    """The Result's own equity curve, read back in ``seq`` order.

    Read from the persisted rows rather than from the in-memory ``EngineOutput``: the claim
    is about what a reader of a finished Result sees, and the JSONB/round-trip boundary is
    where a time-ordering claim could quietly stop being true."""
    rows = (
        await session.execute(
            select(ResultEquityPoint)
            .where(ResultEquityPoint.result_id == result_id)
            .order_by(ResultEquityPoint.seq)
        )
    ).scalars()
    return [str(row.timestamp) for row in rows]


async def _artifact_checksums(session: Any, result_id: str) -> dict[str, str]:
    """The Result's stored per-artifact CONTENT checksums, minus ``diagnostics``.

    This is the identity instrument every "unchanged" claim below is stated over, and the
    omission is the reason it can be: ``result_artifacts.project_row`` hashes a diagnostics
    row together with its ``diagnostic_id``, a fresh ULID minted at every materialization, so
    that one checksum differs between two byte-identical runs BY CONSTRUCTION (measured, not
    assumed). It says nothing about the engine, so including it would make every identity
    assertion here permanently unsatisfiable. The diagnostics CONTENT is compared directly
    instead, by :func:`_run_diagnostics`, and it carries ``execution_key``, the per-item
    attribution and the policy versions — so nothing is dropped, only re-read where it is
    stable.

    The four that remain cover every row a reader of a finished Result can page: the equity
    curve, the trade ledger and both decision journals."""
    rows = (
        await session.execute(
            select(ResultArtifactChecksum).where(ResultArtifactChecksum.result_id == result_id)
        )
    ).scalars()
    stored = {row.artifact_type: row.checksum for row in rows}
    return {kind: stored[kind] for kind in _CONTENT_ARTIFACTS}


async def _signal_events(session: Any, result_id: str) -> list[SignalEventRow]:
    """The Result's decision trace in ``seq`` order — the merged axis, as persisted.

    Every arbitration assertion below reads THIS rather than the in-memory ``PortfolioRun``:
    the trace is the only surface on which a reader can see that two items were decided at
    one instant, and a claim about arbitration that never survives to the artifact is a claim
    about a value nobody can check."""
    return list(
        (
            await session.execute(
                select(SignalEventRow)
                .where(SignalEventRow.result_id == result_id)
                .order_by(SignalEventRow.seq)
            )
        )
        .scalars()
        .all()
    )


async def _admit_and_run(
    session: Any,
    composition_id: str,
    *,
    idempotency_key: str,
    stream_bars: Any = _e2e_bars,
) -> dict[str, Any]:
    """Admit one run on ``composition_id`` and drive the real worker to its terminal state.

    ``idempotency_key`` is REQUIRED rather than defaulted: the identity tests admit two runs
    on the SAME composition, and two admissions that share a key replay one another instead
    of producing a second run — which would turn "identical twice" into "compared a Result
    with itself"."""
    admit = await backtest_cmd.request_backtest_run(
        session, USER1, composition_id=composition_id, idempotency_key=idempotency_key
    )
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=stream_bars)
    await session.commit()
    return dict(out)


def _stepped_bars(step: timedelta, count: int, *, offset: timedelta) -> list[dict[str, Any]]:
    """``_e2e_bars``' shape at an arbitrary cadence: flat, then a breakout, then a stop-out.

    ``offset`` shifts the whole series off midnight so two cadences can be built whose
    timestamp sets are DISJOINT. That matters: with a daily series at 00:00 and a 12-hourly
    one also at 00:00 the daily points are a SUBSET of the 12-hourly ones, the union equals
    the finer axis, and "the merged axis is the union" is satisfied by an implementation that
    simply picked the longer stream. Measured, both ways: aligned, the merged run walks 43
    ticks (= the 12h axis alone); offset by six hours it walks 65 (= 22 + 43)."""
    start = datetime(2024, 2, 1, tzinfo=UTC) + offset
    bars: list[dict[str, Any]] = []
    for index in range(count):
        timestamp = (start + step * index).strftime("%Y-%m-%dT%H:%M:%SZ")
        if index < count - 2:
            prices = ("100", "100", "100", "100")
        elif index == count - 2:
            prices = ("100", "103", "100", "103")
        else:
            prices = ("103", "103", "98", "98")
        bars.append(
            {
                "timestamp": timestamp,
                "open": prices[0],
                "high": prices[1],
                "low": prices[2],
                "close": prices[3],
                "volume": "5",
            }
        )
    return bars


async def _heterogeneous_composition(
    session: Any, actor: Actor
) -> tuple[str, dict[str, list[dict[str, Any]]]]:
    """Two shared-safe Strategies on DIFFERENT bar cadences, each with its own bar stream.

    Returns the composition and a ``BarSourceRef.entity_id -> bars`` map, because the worker
    resolves one source per pinned market revision and the whole point here is that the two
    items do not share an axis. The revisions declare their cadence
    (``resolution_kind``/``resolution_value``) so ``get_base_timeframe_for_revision`` gives
    each prepared item a real, DIFFERENT ``timeframe`` — without that the two items would
    disagree only in their timestamps and the composite summary could still name one."""
    workspace_id = await _empty_composition(session, actor)
    pkg_rev_id = await _seed_indicator_package(session)
    streams: dict[str, list[dict[str, Any]]] = {}
    for timeframe, step, count, offset in _HETEROGENEOUS_CADENCES:
        market_root, market_rev = await md_repo.create_market_dataset(
            session,
            owner_principal_id=None,
            created_by_principal_id=None,
            market_data_type=MarketDataType.OHLCV,
            payload={"note": f"seed bars {timeframe}"},
            instrument_id=None,
        )
        market_rev.resolution_kind = ResolutionKind.BAR
        market_rev.resolution_value = timeframe
        market_rev.revision_state = MarketRevisionState.APPROVED
        await session.flush()
        md_repo.add_processed_asset(
            session,
            entity_id=market_root.entity_id,
            object_key=f"market/processed/{market_root.entity_id}/seed.parquet",
            content_digest=f"seed-bars-{timeframe}",
            size_bytes=4096,
            revision_id=market_rev.revision_id,
            row_count=count,
        )
        await session.flush()
        streams[market_root.entity_id] = _stepped_bars(step, count, offset=offset)
        work_object = await mb_cmd.create_work_object(
            session,
            actor,
            object_kind="strategy",
            payload=_shared_safe_payload(
                market_root.entity_id,
                market_rev.revision_id,
                market_rev.content_hash,
                indicator_revision_id=pkg_rev_id,
            ),
        )
        await mb_cmd.attach_mainboard_item(
            session,
            actor,
            workspace_id=workspace_id,
            root_id=work_object["root_id"],
            revision_id=work_object["revision_id"],
            item_kind="strategy",
        )
    await session.commit()
    return str(workspace_id), streams


# --------------------------------------------------------------------------- #
# (1) The branch is NOT taken by any independent run                           #
# --------------------------------------------------------------------------- #


async def test_an_independent_multi_item_run_never_reaches_the_unified_loop(session) -> None:
    """The flag exactly as SHIPPED, a real two-Strategy run, and the sequential marker.

    This is the assertion that replaces the containment gate's old ``callers == []``. It is
    stated over the PERSISTED diagnostics rather than over a spy, because the persisted
    artifact is the only thing a reader of a finished Result ever sees: if the wiring ever
    re-routed this run, ``engine_kind`` is where it would show, and nowhere else."""
    await _seed_principals(session)
    composition_id, _revisions = await _two_strategy_composition(session, USER1)

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "succeeded"
    diagnostics = await _run_diagnostics(session, out["result_id"])
    assert diagnostics["engine_kind"] == _SEQUENTIAL_KIND
    assert diagnostics["engine_kind"] != UNIFIED_KIND
    # Independent mode sums the strategies' OWN capitals; a pool would have replaced them.
    assert diagnostics["composition"]["strategy_count"] == 2
    # MEASURED, against an expectation this test got wrong on its first run: the fold
    # discloses itself on EVERY composite it produces, not only on a shared pool. So the
    # warning marks "the sequential fold ran", not "shared capital was requested", and it is
    # asserted in that reading — present here, absent on the unified path below.
    assert COMPOSITION_CURVE_WARNING in diagnostics["warnings"]


async def test_a_lifted_flag_alone_does_not_route_an_independent_multi_item_run(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The SECOND conjunct of ``_use_unified_clock``, driven through the real worker.

    ``shared_allocation_is_executable`` alone would route EVERY multi-item run through the
    shared loop. Testing the predicate's compound answer would not catch that — a short
    circuit hides its own second term — so the world is moved and the run is left
    independent, which is the only combination that isolates the conjunct."""
    await _seed_principals(session)
    composition_id, _revisions = await _two_strategy_composition(session, USER1)

    with _lifted(monkeypatch):
        assert capability.shared_allocation_is_executable() is True
        admit = await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id
        )
        await session.commit()
        out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
        await session.commit()

    assert out["state"] == "succeeded"
    assert (await _run_diagnostics(session, out["result_id"]))["engine_kind"] == _SEQUENTIAL_KIND


async def test_a_single_strategy_shared_composition_stays_on_run_engine(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §3.2 / §14 A14 — with ONE executing item the merged axis IS that item's bar axis.

    Both ``_use_unified_clock`` conjuncts hold here, and the branch is still not taken: the
    third condition is the executing-item count, and it lives at the call site because it is
    a different invariant with a different source. A composition that replays byte-identically
    today must keep doing so when the flag lifts, or A14 becomes unprovable."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=1, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)

    with _lifted(monkeypatch):
        admit = await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id
        )
        await session.commit()
        out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
        await session.commit()

    assert out["state"] == "succeeded"
    # A lone Strategy with nothing else pinned takes the byte-identical single-item path, so
    # there is no composite artifact at all — which is itself the assertion.
    assert (await _run_diagnostics(session, out["result_id"]))["engine_kind"] != UNIFIED_KIND


# --------------------------------------------------------------------------- #
# (2) The branch IS taken, and it works                                        #
# --------------------------------------------------------------------------- #


async def test_a_shared_two_strategy_run_reaches_the_unified_loop_when_lifted(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wiring proof: both conjuncts true, two executing items, a real Result.

    Without this the slice would have wired a branch that merely type-checks. What it pins is
    the whole chain `C1`-`C3` built — ``_build_stepper`` -> ``_EngineParticipant`` ->
    ``iter_portfolio`` -> ``project_portfolio_run`` — reached from the worker for the first
    time, over the ONE shared pool rather than the sum of the items' own capitals.

    The equity curve being time-ordered is not decoration: it is ADR §14 **A5**, and it is
    the exact defect the sequential fold has (the containment gate reads 5000 sequentially
    where one clock reads 3000 on the same trades)."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)

    with _lifted(monkeypatch):
        admit = await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id
        )
        await session.commit()
        out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
        await session.commit()

    assert out["state"] == "succeeded", out
    diagnostics = await _run_diagnostics(session, out["result_id"])
    assert diagnostics["engine_kind"] == UNIFIED_KIND
    assert diagnostics["engine_kind"] != _SEQUENTIAL_KIND
    # The merged axis really was walked: a projection over ZERO ticks would satisfy every
    # assertion above while proving only that the loop was constructed and never entered.
    assert diagnostics["tick_count"] >= 1
    assert diagnostics["policy_versions"]["portfolio_loop_version"]
    # The sequential fold's self-disclosure does NOT travel here, and the asymmetry is the
    # point: the two markers are mutually exclusive, so a persisted Result names its own path.
    assert COMPOSITION_CURVE_WARNING not in diagnostics["warnings"]
    # ADR §14 **A5** — the composite curve is the ledger's own and is time-ordered BY
    # CONSTRUCTION. That is exactly what the sequential fold cannot say (the containment gate
    # reads 5000 on trades one clock reads 3000 on), so it is asserted on the PERSISTED
    # points rather than assumed from the projection's own docstring.
    stamps = await _persisted_equity_timestamps(session, out["result_id"])
    assert stamps == sorted(stamps)
    assert len(stamps) >= 2


async def test_a_cancel_inside_the_tick_loop_is_honoured_and_writes_no_result(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 **A21** — checkpoint #3b, the one the merged axis made necessary.

    O-06 checkpoint #3 sits BETWEEN items, and the shared branch has no between-items
    boundary; without a tick-strided check a long shared run would be uncancellable. Proving
    it is reachable needs the cancel to arrive DURING the loop, so the user's press is
    simulated at the first checkpoint the run reaches while RUNNING — which, on this path, is
    checkpoint #3b and nothing else. The real ``_cancellation_requested`` still decides and
    the real ``_cancel_run`` still writes; only the moment of the press is scripted.

    ``replayed_tick_count`` in the durable event is what distinguishes #3b from checkpoint
    #4: only #3b reports it, so a cancel that had actually been caught after the replay would
    fail this test rather than pass it."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)

    real = worker._cancellation_requested
    pressed: list[str] = []

    async def _press_once_running(sess: Any, run: Any) -> bool:
        if run.state == BacktestRunState.RUNNING and not pressed:
            pressed.append(str(run.run_id))
            await backtest_cmd.cancel_backtest_run(sess, USER1, run_id=str(run.run_id))
            # In production the press arrives on ANOTHER connection and is committed before
            # the worker's next refresh can see it. Here both live in one session, and
            # ``_cancellation_requested`` refreshes the row — which DISCARDS an unflushed
            # attribute. The flush reproduces the production ordering; it does not stand in
            # for the assertion, which the real predicate still makes on the next line.
            await sess.flush()
        return bool(await real(sess, run))

    with _lifted(monkeypatch):
        admit = await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id
        )
        await session.commit()
        monkeypatch.setattr(worker, "_cancellation_requested", _press_once_running)
        out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
        await session.commit()

    assert pressed, "the run never reached a RUNNING checkpoint, so nothing was proved"
    assert out["state"] == "cancelled"
    assert out["result_id"] is None
    # doc 15 §16 — a CANCELLED run materialises no Result, on this path as on every other.
    assert await _count(session, BacktestResult) == 0
    event = (
        await session.execute(
            select(BacktestRunEvent).where(
                BacktestRunEvent.run_id == admit["run_id"],
                BacktestRunEvent.event_type == RunEventType.RUN_CANCELLED,
            )
        )
    ).scalar_one()
    assert event.detail["cancelled_at_stage"] == BacktestRunState.RUNNING.value
    assert "replayed_tick_count" in event.detail, event.detail


async def test_checkpoint_four_also_cancels_a_shared_run_and_writes_no_result(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Checkpoint #4 on the SHARED path — a regression a negative control found, not a review.

    Checkpoint #4 is the last line at which no Result exists (doc 15 §16), and its progress
    detail used to read ``item_runs`` — a name only the INDEPENDENT arm binds. A cancel
    observed there on a shared run therefore raised ``UnboundLocalError`` instead of
    cancelling. Every test in this module passed anyway, because they all cancel EARLIER, at
    #3b, and the line was never reached.

    So the press is scripted at the SECOND checkpoint the run reaches while RUNNING: with the
    stride as shipped a short run checks once inside the loop and once after it, and the
    second one is #4. Its absent ``replayed_tick_count`` is what proves which of the two ran.
    """
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)

    real = worker._cancellation_requested
    running_checks: list[int] = []

    async def _press_on_the_second_running_check(sess: Any, run: Any) -> bool:
        if run.state == BacktestRunState.RUNNING:
            running_checks.append(1)
            if len(running_checks) == 2:
                await backtest_cmd.cancel_backtest_run(sess, USER1, run_id=str(run.run_id))
                await sess.flush()
        return bool(await real(sess, run))

    with _lifted(monkeypatch):
        admit = await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id
        )
        await session.commit()
        monkeypatch.setattr(worker, "_cancellation_requested", _press_on_the_second_running_check)
        out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
        await session.commit()

    assert len(running_checks) >= 2, "the run never reached checkpoint #4, so nothing was proved"
    assert out["state"] == "cancelled"
    assert await _count(session, BacktestResult) == 0
    event = (
        await session.execute(
            select(BacktestRunEvent).where(
                BacktestRunEvent.run_id == admit["run_id"],
                BacktestRunEvent.event_type == RunEventType.RUN_CANCELLED,
            )
        )
    ).scalar_one()
    assert event.detail["engine_replay_complete"] is True
    assert "replayed_tick_count" not in event.detail
    # The durable event names the path the run took, so a reader of a cancelled shared run
    # can tell it apart from a cancelled independent one without re-deriving anything.
    assert event.detail["unified_clock"] is True
    assert event.detail["replayed_item_count"] == 2


async def test_a_strategy_shape_the_shared_clock_cannot_drive_fails_the_run_closed(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`C3`'s eleven refusals reach the worker as a FAILED run, never a degraded one.

    The stock fixture defers its entry fill (``next_candle_open``) and leaves
    ``same_direction_stacking`` at its schema default, so the adapter refuses it at
    construction — before a single bar is admitted. What this pins is the worker's half: the
    refusal becomes a terminal ``RUN_FAILED_ENGINE_ERROR`` with no Result, rather than an
    unhandled exception that a retry would replay forever.

    It is also the honest statement of `C6`'s size: with the schema default as it stands,
    this is what MOST saved strategies would do on a shared clock."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=False)
    await _enable_shared_pool(session, USER1, composition_id)

    with _lifted(monkeypatch):
        admit = await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id
        )
        await session.commit()
        out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
        await session.commit()

    assert out["state"] == "failed", out
    assert out["failure_code"] == RunFailureCode.ENGINE_ERROR.value
    assert await _count(session, BacktestResult) == 0


# --------------------------------------------------------------------------- #
# (3) The merged axis, arbitrated — what only a worker-level run can show       #
# --------------------------------------------------------------------------- #


async def test_two_items_entering_at_the_same_tick_are_priced_against_one_frozen_pool(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 **A3** + §8.1, at the worker: simultaneous intents see ONE ``PortfolioSnapshot``.

    The wiring proof above establishes that the branch runs and produces a time-ordered
    curve. It says nothing about the property the merged axis exists FOR — that two items
    deciding at the same instant are decided against the same frozen valuation, with neither
    privileged by its pin ordinal. The two shipped fixtures already breakout on the same bar,
    so the situation was reached on every shared run in this module; nothing read it.

    Four axes, each a different way the property could fail and none of which implies another:

    * the two entries carry the SAME ``t_ms`` — otherwise there is no simultaneity to arbitrate
      and every assertion below is about two unrelated ticks;
    * they carry DISTINCT ``pin_ordinal``s — otherwise it is one item observed twice;
    * they were priced off the SAME ``reference_price`` — this is the frozen snapshot itself.
      A per-item valuation would still produce two admitted entries and still produce a
      time-ordered curve, so nothing else here would notice;
    * they were granted the SAME ``granted_notional`` — the *no prior-item precedence* half.
      Equal shares of one pool must buy equal capacity; a running tally that leaked into the
      later item's pricing, or a first-come-first-served pool, would show up here and nowhere
      else in this module.

    And the pool itself: each item's sleeve is exactly its share of the allocatable capital
    and the two sleeves sum to it. That is *no hidden share transfer* stated over the
    persisted artifact — a sleeve that had absorbed a sibling's capacity would still be a
    number, and only this comparison calls it wrong."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)

    with _lifted(monkeypatch):
        out = await _admit_and_run(session, composition_id, idempotency_key="c4-arbitration")

    assert out["state"] == "succeeded", out
    events = await _signal_events(session, out["result_id"])
    entries = [row for row in events if row.event_type == "entry"]
    first_instant = min(int(row.detail["t_ms"]) for row in entries)
    simultaneous = [row for row in entries if int(row.detail["t_ms"]) == first_instant]
    assert len(simultaneous) == 2, (
        "the two items did not decide at the same instant, so this run arbitrates nothing: "
        f"{[(row.detail['item_id'], row.detail['t_ms']) for row in entries]}"
    )

    ordinals = {int(row.detail["diagnostics"]["pin_ordinal"]) for row in simultaneous}
    assert ordinals == {0, 1}, ordinals
    assert len({row.detail["item_id"] for row in simultaneous}) == 2

    # The frozen snapshot. One published valuation per tick (ADR §8.1) means one reference
    # price, whatever each item then does with it.
    assert len({str(row.detail["reference_price"]) for row in simultaneous}) == 1

    # Equal shares, one pool, one instant -> equal capacity. Both admitted, and neither
    # blocked by the other.
    arbitration = [row.detail["arbitration"] for row in simultaneous]
    assert {str(block["outcome"]) for block in arbitration} == {"admitted"}
    assert len({str(block["granted_notional"]) for block in arbitration}) == 1
    assert {block["counterparty_item_id"] for block in arbitration} == {None}

    # No hidden share transfer, read off the immutable diagnostics rather than the ledger.
    composition = (await _run_diagnostics(session, out["result_id"]))["composition"]
    allocatable = Decimal(str(composition["allocatable_initial"]))
    sleeves = [Decimal(str(item["initial_sleeve"])) for item in composition["items"]]
    for item in composition["items"]:
        share = Decimal(str(item["equity_share_percent"])) / Decimal(100)
        assert Decimal(str(item["initial_sleeve"])) == allocatable * share
    assert sum(sleeves) == allocatable


async def test_a_mandatory_exit_and_a_competing_entry_land_on_one_tick_in_phase_order(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §8's phase ORDER, observed at the worker rather than in a phase-loop unit test.

    On the stop-out bar both items' protective stops fire (P3, mandatory) and both items then
    form a fresh opposite entry (P4, competing) — four decisions, one instant. The shipped
    fixture produced exactly that on every run in this module and nothing read it.

    The claim is not merely that all four survive to the trace. It is that at ONE instant
    every mandatory exit precedes every competing entry, because a shared pool cannot price
    an entry against capital a sibling's mandatory close has not yet released. Stated as a
    comparison of ``seq`` ranges rather than as a spot check on one pair: with two items there
    are four orderings that keep each item's own P3 before its own P4 while interleaving the
    items, and only one of them is the phase order."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)

    with _lifted(monkeypatch):
        out = await _admit_and_run(session, composition_id, idempotency_key="c4-phase-order")

    assert out["state"] == "succeeded", out
    events = await _signal_events(session, out["result_id"])
    by_instant: dict[int, list[SignalEventRow]] = {}
    for row in events:
        by_instant.setdefault(int(row.detail["t_ms"]), []).append(row)

    contested = [
        rows
        for rows in by_instant.values()
        if {row.event_type for row in rows} == {"exit", "entry"}
    ]
    traced = {
        instant: [(row.event_type, row.detail["phase"]) for row in rows]
        for instant, rows in by_instant.items()
    }
    assert contested, (
        "no instant carried a mandatory exit AND a competing entry, so the phase order was "
        f"never exercised: {traced}"
    )
    for rows in contested:
        exits = [row for row in rows if row.event_type == "exit"]
        entries = [row for row in rows if row.event_type == "entry"]
        # Both items, on both sides — otherwise one item's exit and the OTHER's entry could
        # satisfy the ordering while the contested pair never met.
        assert len({row.detail["item_id"] for row in exits}) == 2
        assert len({row.detail["item_id"] for row in entries}) == 2
        # The exits are mandatory (a protective stop), not discretionary closes.
        assert {str(row.detail["reason"]) for row in exits} == {"stop_loss"}
        assert {str(row.detail["phase"]) for row in exits} == {"P3"}
        assert {str(row.detail["phase"]) for row in entries} == {"P4"}
        assert max(row.seq for row in exits) < min(row.seq for row in entries), (
            "an entry was traced before a mandatory exit at the same instant"
        )


async def test_the_shared_run_is_identical_when_the_prepared_items_arrive_reversed(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*No prior-item precedence*, stated as the strongest form: the ORDER cannot be read.

    ``iter_portfolio``'s contract says participants "may arrive in any order" because it
    re-orders them to ``(pin_ordinal, item_id)`` first, and ``_shared_clock_inputs``' own
    docstring says ``pin_ordinal`` comes from the MANIFEST and never from a list position.
    Both are claims about the worker's inputs and neither was exercised through the worker.

    The reversal is applied at the seam those two claims meet — the real
    ``_shared_clock_inputs`` still builds the participants, the real loop still runs, the real
    projection still writes — so what is measured is the production path fed a permuted list,
    not a re-implementation of it. The SAME composition is run both ways, which is what makes
    the artifacts comparable at all: two separately seeded compositions carry different ULIDs
    and their decision traces could never match whatever the engine did."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)
    real = worker._shared_clock_inputs
    seen: list[list[str]] = []

    def _reverse_the_prepared_list(prepared_items: list[Any], **kwargs: Any) -> Any:
        seen.append([item.item_id for item in prepared_items])
        return real(list(reversed(prepared_items)), **kwargs)

    with _lifted(monkeypatch):
        control = await _admit_and_run(session, composition_id, idempotency_key="c4-order-a")
        monkeypatch.setattr(worker, "_shared_clock_inputs", _reverse_the_prepared_list)
        permuted = await _admit_and_run(session, composition_id, idempotency_key="c4-order-b")

    assert control["state"] == "succeeded" and permuted["state"] == "succeeded"
    # The permutation really happened and really was non-trivial. Without this a patch that
    # silently failed to apply would make the whole test a comparison of two identical runs.
    assert seen and len(seen[-1]) == 2 and seen[-1] != list(reversed(seen[-1]))

    assert await _artifact_checksums(session, permuted["result_id"]) == await _artifact_checksums(
        session, control["result_id"]
    )
    assert await _run_diagnostics(session, permuted["result_id"]) == await _run_diagnostics(
        session, control["result_id"]
    )


async def test_replaying_the_same_shared_composition_twice_produces_identical_artifacts(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 **A18** — the co-simulation is a function of its pins and of nothing else.

    Two admissions, two runs, two Results, one set of content checksums. What this excludes
    is a whole class of defect the order test cannot see: a wall clock, a ``run_id``, an
    iteration over a set, or any other run-scoped value leaking into an IMMUTABLE artifact.
    The diagnostics are compared as CONTENT because their stored checksum is taken over a
    freshly minted ``diagnostic_id`` — measured, and the reason ``_artifact_checksums``
    omits it."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)

    with _lifted(monkeypatch):
        first = await _admit_and_run(session, composition_id, idempotency_key="c4-replay-1")
        second = await _admit_and_run(session, composition_id, idempotency_key="c4-replay-2")

    # Two distinct runs, not one replayed admission — the idempotency keys differ, and this
    # is what proves the keys did their job rather than merely being passed.
    assert first["result_id"] != second["result_id"]
    assert (await _run_diagnostics(session, first["result_id"]))["engine_kind"] == UNIFIED_KIND
    assert await _artifact_checksums(session, second["result_id"]) == await _artifact_checksums(
        session, first["result_id"]
    )
    assert await _run_diagnostics(session, second["result_id"]) == await _run_diagnostics(
        session, first["result_id"]
    )


async def test_a_heterogeneous_timeframe_composition_walks_the_union_of_both_axes(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 **A1** — the outer loop is the merged valuation axis, never one item's.

    Every shared run in this module until here gave both items the SAME bars, so the merged
    axis and each item's own axis coincided and an implementation that simply drove the first
    participant's stream would have passed all of them. Two disjoint cadences separate those
    readings for the first time at the worker: 22 daily bars offset to 06:00 and 43 twelve-
    hourly bars at 00:00/12:00, so neither timestamp set contains the other and the union is
    strictly larger than both.

    Three consequences are asserted, because the union could be walked and still be
    misreported: the tick count IS the union's size; the replayed period spans the earliest
    and latest points across BOTH items; and the composite summary refuses to name a single
    timeframe when the items disagree (a composite that claimed "1D" would be a provenance
    lie about half its own rows). Both items must also have executed — a run where one item
    never traded would satisfy the tick count while proving only that its bars were read."""
    await _seed_principals(session)
    composition_id, streams = await _heterogeneous_composition(session, USER1)
    await _enable_shared_pool(session, USER1, composition_id)

    def _stream_per_source(source: Any) -> Iterator[list[dict[str, Any]]]:
        yield streams[source.entity_id]

    with _lifted(monkeypatch):
        out = await _admit_and_run(
            session,
            composition_id,
            idempotency_key="c4-heterogeneous",
            stream_bars=_stream_per_source,
        )

    assert out["state"] == "succeeded", out
    per_item = [{bar["timestamp"] for bar in bars} for bars in streams.values()]
    union = sorted(set().union(*per_item))
    assert all(len(union) > len(axis) for axis in per_item), (
        "the two cadences are not disjoint, so the union equals one of them and this test "
        "cannot tell a merged axis from a single item's"
    )

    diagnostics = await _run_diagnostics(session, out["result_id"])
    assert diagnostics["engine_kind"] == UNIFIED_KIND
    assert diagnostics["tick_count"] == len(union)
    assert {str(item["timeframe"]) for item in diagnostics["composition"]["items"]} == {
        "1D",
        "12h",
    }
    assert all(item["executed"] for item in diagnostics["composition"]["items"])
    assert all(int(item["total_trades"]) >= 1 for item in diagnostics["composition"]["items"])

    summary = (
        await session.execute(
            select(ResultSummary).where(ResultSummary.result_id == out["result_id"])
        )
    ).scalar_one()
    assert summary.period_start == union[0]
    assert summary.period_end == union[-1]
    # ``_single_value`` over two disagreeing timeframes: the composite states none rather
    # than one item's.
    assert summary.timeframe is None


# --------------------------------------------------------------------------- #
# (4) Independent mode, byte for byte                                          #
# --------------------------------------------------------------------------- #


async def test_a_single_item_shared_run_stays_on_the_byte_identical_lone_strategy_path(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §3.2 / §14 **A14**, tightened: WHICH non-unified path, not merely "not unified".

    ``test_a_single_strategy_shared_composition_stays_on_run_engine`` asserts the engine kind
    is not the unified one. There are TWO other kinds, and only one of them is A14: a build
    that sent the lone item through ``combine_item_runs`` would stamp the COMPOSITE kind,
    re-price it as a one-row portfolio fold, and pass that assertion unchanged. ``run_backtest``
    calls the path it must take "byte-identical" in its own comment; this names it.

    The pool is asserted to have been RESOLVED, not ignored — the persisted summary's initial
    capital is the plan's P0 and not the strategy's own ``initial_capital``. Without that the
    test would be satisfied by a run that dropped the allocation on the floor, which is a
    different bug wearing the same green.

    **Honest boundary, measured rather than assumed.** The strongest reading of A14 — *the
    same composition produces the same BYTES with and without the lift* — is not constructible
    from the worker in this tree, and the reason is the containment itself: a shared-capital
    composition is refused at admission in the shipped world (``ReadinessBlockedError``), so
    there is no second world to compare against. Tried, and it is what this test was before
    the attempt failed. The comparison C9 will owe is the merged axis reduced to one item; it
    needs the count guard removed, which is a source-level literal and a `C9` decision."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=1, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)

    with _lifted(monkeypatch):
        out = await _admit_and_run(session, composition_id, idempotency_key="c4-lone-item")

    assert out["state"] == "succeeded", out
    diagnostics = await _run_diagnostics(session, out["result_id"])
    # The lone-Strategy path: neither the unified loop NOR the sequential composite fold.
    assert diagnostics["engine_kind"] == "v1_bar_replay"
    assert diagnostics["engine_kind"] != UNIFIED_KIND
    assert diagnostics["engine_kind"] != _SEQUENTIAL_KIND

    summary = (
        await session.execute(
            select(ResultSummary).where(ResultSummary.result_id == out["result_id"])
        )
    ).scalar_one()
    # The sleeve WAS resolved — 100% of a 50,000 pool, not the strategy's own 10,000.
    assert Decimal(str(summary.headline["initial_capital"])) == Decimal("50000.00")


async def test_an_independent_multi_item_run_is_byte_identical_when_the_flag_is_lifted(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The commercially load-bearing one: composite Results must not move when C9 lands.

    ``test_a_lifted_flag_alone_does_not_route_an_independent_multi_item_run`` reads the
    engine kind, which is one field. Independent multi-item runs are a first-class mode
    (doc 13 §1.1) and every composite Result ever produced was folded sequentially, so what
    has to hold across the lift is not the label but the ROWS — the equity curve, the trade
    ledger and both decision journals, unchanged.

    Stated here rather than left to the containment gate on purpose: the gate proves the
    independent loop and ``combine_item_runs`` still EXIST in the source. Existing and
    producing the same bytes are different claims, and only the second one is what a reader
    of an old Result is entitled to."""
    await _seed_principals(session)
    composition_id, _revisions = await _two_strategy_composition(session, USER1)

    shipped = await _admit_and_run(session, composition_id, idempotency_key="c4-multi-shipped")
    with _lifted(monkeypatch):
        assert capability.shared_allocation_is_executable() is True
        lifted = await _admit_and_run(session, composition_id, idempotency_key="c4-multi-lifted")

    assert shipped["state"] == "succeeded" and lifted["state"] == "succeeded"
    for finished in (shipped, lifted):
        diagnostics = await _run_diagnostics(session, finished["result_id"])
        assert diagnostics["engine_kind"] == _SEQUENTIAL_KIND
    assert await _artifact_checksums(session, lifted["result_id"]) == await _artifact_checksums(
        session, shipped["result_id"]
    )
    assert await _run_diagnostics(session, lifted["result_id"]) == await _run_diagnostics(
        session, shipped["result_id"]
    )
