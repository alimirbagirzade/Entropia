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
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    BacktestRunEvent,
    ResultEquityPoint,
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
