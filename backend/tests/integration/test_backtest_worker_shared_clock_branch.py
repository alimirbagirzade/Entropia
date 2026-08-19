"""`C4` / E5 — the worker's shared-clock branch: wired, guarded, and unreachable.

Three properties, in the order they matter.

1. **The independent path never reaches the unified loop** — proved by making the loop and
   the projection EXPLODE if they are entered, then running a real two-Strategy composition
   through the real worker with the flag exactly as shipped. A marker check alone would only
   say the fold ran; a booby-trapped loop says the other branch did not.
2. **A shared composition is still refused at admission** — at the MULTI-ITEM shape this
   slice wires, which ``test_shared_allocation_containment.py`` (single Strategy) does not
   cover. That refusal is what makes property 1 hold for every request that can exist, and
   it is why narrowing the containment gate's caller scan is safe.
3. **The wired branch is real, and cancellable** — driven only under a test-owned forced
   flag. Without this the slice would ship a branch nobody had ever executed, and the
   narrowed tripwire would be guarding a claim rather than a behaviour. ADR §14 **A21**: the
   merged clock deletes the per-item checkpoint boundary, so the cancel moves INTO the tick
   loop on a stride, and a cancelled run still produces NO Result (doc 15 §16).

The forced flag lives here and only here. ``SHARED_ALLOCATION_STATUS`` stays ``future_dev``
in ``backend/src``; lifting it is `C9` / ADIM 20, behind the ADR §16 human gate.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.jobs import backtest_engine as worker
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.domain.allocation import rules as alloc_rules
from entropia.domain.backtest.enums import RunEventType
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    BacktestRun,
    BacktestRunEvent,
)
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.shared.errors import ReadinessBlockedError
from tests.integration import test_backtest_persistence as persistence
from tests.integration.test_backtest_persistence import (
    USER1,
    _count,
    _e2e_bars,
    _run_diagnostics,
    _seed_principals,
    _two_strategy_composition,
)

pytestmark = pytest.mark.integration

_BLOCKER = "ALLOCATION_SHARED_MODE_NOT_IN_BUILD"
_CURVE_WARNING = "portfolio_curve_sequential_not_unified_clock"


async def _enable_shared_pool(session, composition_id: str, *, amount: str) -> list[str]:
    """A shared plan capitalising EVERY strategy item at an equal share (doc 13 §7).

    ``_enable_allocation`` in the persistence suite funds a single item at 100%; the shared
    clock's whole subject is more than one sleeve drawing on one pool, so the shares are
    split here instead of the helper being widened for one caller."""
    items = await mb_repo.list_active_items(session, composition_id)
    strategies = [it for it in items if str(it.item_kind) == "strategy"]
    share = Decimal(100) / Decimal(len(strategies))
    await alloc_cmd.upsert_allocation_draft(
        session,
        USER1,
        composition_id=composition_id,
        expected_row_version=None,
        enabled=True,
        initial_capital={"amount": amount, "currency": "USDT"},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent="0",
        entries=[
            {
                "composition_item_id": item.item_id,
                "active": True,
                "equity_share_percent": str(share),
            }
            for item in strategies
        ],
        idempotency_key="c4-shared-pool",
    )
    await session.commit()
    return [str(item.item_id) for item in strategies]


def _force_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make this build answer "shared allocation is executable" — everywhere it is asked.

    Patched at each BINDING site, not only at the definition: admission, the allocation
    rules and the worker each did ``from ... import shared_allocation_is_executable``, so
    patching only ``capability`` would leave three live references to the real one and the
    run would be refused before the branch under test could run."""
    for module in (backtest_cmd, alloc_rules, worker):
        monkeypatch.setattr(module, "shared_allocation_is_executable", lambda: True)


def _co_simulable_strategies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reshape the seeded Strategy into a shape ``_unsupported_shapes`` admits.

    MEASURED, not assumed: with the shipped schema defaults the adapter refuses the
    standard fixture on THREE of its eleven counts at once — ``entry_timing`` and
    ``exit_timing`` default to ``next_candle_open`` (a deferred fill the pool would
    arbitrate but the item would not open), and ``same_direction_stacking`` defaults to
    ``allow_stacking`` (a second entry opened inside ``_phase_tail``, outside arbitration).
    The stacking one is the finding `C3` handed forward: it is the SCHEMA DEFAULT, so most
    existing strategies cannot co-simulate at all, and turning that list into admission
    blockers (`C6`) is a product decision rather than a test slice's.

    Two fields are changed and nothing else, so the run this drives is the same seeded
    strategy on the same bars — only its fill schedule and its stacking policy differ."""
    real_payload = persistence._strategy_payload

    def _shaped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = real_payload(*args, **kwargs)
        payload["data"]["execution"] = {
            "entry_timing": "current_candle_close",
            "exit_timing": "current_candle_close",
        }
        payload["conflict_position_handling"] = {"same_direction_stacking": "ignore"}
        return payload

    monkeypatch.setattr(persistence, "_strategy_payload", _shaped)


# --------------------------------------------------------------------------- #
# 1. The independent path never reaches the unified loop                       #
# --------------------------------------------------------------------------- #


async def test_an_independent_multi_item_run_never_reaches_the_unified_loop(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P-C2 §C.6 part 2 — the behavioural half of the narrowed containment gate.

    The caller scan can only say the worker NAMES ``iter_portfolio``; it cannot say the
    branch is not taken. This can: both unified-clock entry points are replaced with traps,
    so entering either fails the run loudly instead of quietly producing a different number.
    The run then has to succeed through the sequential fold — and the fold's self-disclosing
    warning has to be on the Result, because that warning is what tells a reader which of
    the two engines priced their portfolio."""

    def _trap(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError(
            "an INDEPENDENT multi-item run entered the unified-clock path; every composite "
            "Result would be silently re-priced with no flag and no ENGINE_VERSION bump"
        )

    monkeypatch.setattr(worker, "iter_portfolio", _trap)
    monkeypatch.setattr(worker, "project_portfolio_run", _trap)

    await _seed_principals(session)
    composition_id, revisions = await _two_strategy_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "succeeded"
    diagnostics = await _run_diagnostics(session, out["result_id"])
    assert diagnostics["engine_kind"] == "v1_bar_replay_composition"
    assert diagnostics["composition"]["strategy_count"] == len(revisions) == 2
    # The sequential fold's own marker: this Result was priced item-by-item, not on one
    # clock. Its absence would mean the composite came from somewhere else.
    assert _CURVE_WARNING in diagnostics["warnings"]


# --------------------------------------------------------------------------- #
# 2. A shared composition is still refused at admission                        #
# --------------------------------------------------------------------------- #


async def test_a_shared_multi_item_run_is_still_refused_at_admission(session) -> None:
    """The refusal, at the shape `C4` wires: TWO Strategies drawing on ONE pool.

    ``test_shared_allocation_containment.py`` covers the single-Strategy case. A worker
    branch that only more-than-one-item runs can reach deserves the multi-item refusal
    asserted directly, rather than assumed to generalise — and doc 15 §9.3 still means no
    run and no Result are left behind."""
    await _seed_principals(session)
    composition_id, _revisions = await _two_strategy_composition(session, USER1)
    item_ids = await _enable_shared_pool(session, composition_id, amount="50000.00")
    assert len(item_ids) == 2

    with pytest.raises(ReadinessBlockedError) as exc_info:
        await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.rollback()

    assert _BLOCKER in {detail["code"] for detail in exc_info.value.details}
    assert await _count(session, BacktestRun) == 0
    assert await _count(session, BacktestResult) == 0


# --------------------------------------------------------------------------- #
# 3. The wired branch is real, and it is cancellable (ADR §14 A21)             #
# --------------------------------------------------------------------------- #


async def test_the_default_strategy_shape_fails_closed_instead_of_co_simulating(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`C3`'s handed-forward finding, confirmed at the worker: the DEFAULTS are refused.

    A lifted build would not quietly co-simulate today's strategies. The adapter refuses
    the seeded fixture on three counts — two deferred fill timings and, the one that
    matters, ``same_direction_stacking`` at its SCHEMA DEFAULT of ``allow_stacking``. The
    run fails with a typed ``RUN_FAILED_ENGINE_ERROR`` naming the shapes, which is the
    honest outcome; the alternative — arbitrating an entry the item never opens — is a
    wrong NUMBER rather than a failure. `C6` turns this list into admission blockers, and
    that most existing strategies then fall out of shared runs is a product decision.

    Asserted here rather than left to `C6` because it is what a reader of this branch most
    needs to know: it is wired, and it currently admits almost nothing."""
    _force_flag(monkeypatch)
    await _seed_principals(session)
    composition_id, _revisions = await _two_strategy_composition(session, USER1)
    await _enable_shared_pool(session, composition_id, amount="50000.00")

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "failed"
    assert await _count(session, BacktestResult) == 0
    run_row = (
        await session.execute(select(BacktestRun).where(BacktestRun.run_id == admit["run_id"]))
    ).scalar_one()
    assert str(run_row.failure_code) == "RUN_FAILED_ENGINE_ERROR"
    message = str(run_row.failure_message)
    assert "cannot participate in a shared-clock run" in message
    assert "same_direction_stacking" in message


async def test_the_shared_branch_co_simulates_every_item_into_one_result(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under a forced flag, and on an admissible shape, the branch runs end to end.

    Not a formality: without it `C4` would ship a branch nobody had executed, and the
    narrowed tripwire would be protecting a claim rather than a behaviour. What is asserted
    is what distinguishes the two engines — the composite came from the merged clock, so it
    carries NO sequential-fold warning, which is the one thing the independent path cannot
    also satisfy."""
    _force_flag(monkeypatch)
    _co_simulable_strategies(monkeypatch)
    await _seed_principals(session)
    composition_id, _revisions = await _two_strategy_composition(session, USER1)
    await _enable_shared_pool(session, composition_id, amount="50000.00")

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "succeeded", await _failure_of(session, admit["run_id"])
    diagnostics = await _run_diagnostics(session, out["result_id"])
    assert _CURVE_WARNING not in diagnostics["warnings"]


async def _failure_of(session, run_id: str) -> str:
    """The run's typed failure, so a red assertion above names the cause instead of 'failed'."""
    row = (
        await session.execute(select(BacktestRun).where(BacktestRun.run_id == run_id))
    ).scalar_one()
    return f"{row.failure_code}: {row.failure_message}"


async def test_the_tick_strided_checkpoint_cancels_before_any_result_exists(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 **A21** — the cancel still lands on a safe checkpoint.

    Checkpoint #3 sits BETWEEN items on the independent path; the merged clock has no
    between-items left, so a shared run would be uncancellable if the check did not move
    into the tick loop. The cancel is armed only AFTER the loop has been entered, so an
    earlier checkpoint catching it would fail this test rather than fake a pass — and the
    ``replayed_tick_count`` key in the recorded progress is emitted by the tick checkpoint
    and by nothing else, which is what names WHICH checkpoint answered.

    The stride is forced to 1 because the fixture's replay is far shorter than the shipped
    stride; the property under test is that a check happens inside the loop at all, not the
    value of ``_TICK_CHECKPOINT_STRIDE``."""
    _force_flag(monkeypatch)
    monkeypatch.setattr(worker, "_TICK_CHECKPOINT_STRIDE", 1)
    _co_simulable_strategies(monkeypatch)

    entered: list[bool] = []
    real_iter = worker.iter_portfolio

    def _watched(*args: Any, **kwargs: Any) -> Any:
        entered.append(True)
        return (yield from real_iter(*args, **kwargs))

    real_check = worker._cancellation_requested

    async def _arm_then_check(db: Any, run: Any) -> bool:
        # Arm on the first check that happens after the loop was entered, so the pre-replay
        # checkpoints see an un-cancelled row and cannot claim this cancel.
        if entered and run.cancel_requested_at is None:
            run.cancel_requested_at = datetime.now(UTC)
            run.cancel_requested_by_principal_id = USER1.principal_id
            await db.flush()
        return await real_check(db, run)

    monkeypatch.setattr(worker, "iter_portfolio", _watched)
    monkeypatch.setattr(worker, "_cancellation_requested", _arm_then_check)

    await _seed_principals(session)
    composition_id, _revisions = await _two_strategy_composition(session, USER1)
    await _enable_shared_pool(session, composition_id, amount="50000.00")

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert entered, "the shared branch was never entered; this test proved nothing"
    assert out["state"] == "cancelled"
    # doc 15 §16: a CANCELLED run materializes no BacktestResult.
    assert await _count(session, BacktestResult) == 0
    run_row = (
        await session.execute(select(BacktestRun).where(BacktestRun.run_id == admit["run_id"]))
    ).scalar_one()
    assert str(run_row.state) == "cancelled"
    # The progress payload rides on the durable RUN_CANCELLED event, which is what a
    # watching client actually replays — so the checkpoint is identified from the record
    # the product publishes rather than from an internal.
    cancelled = (
        await session.execute(
            select(BacktestRunEvent).where(
                BacktestRunEvent.run_id == admit["run_id"],
                BacktestRunEvent.event_type == RunEventType.RUN_CANCELLED.value,
            )
        )
    ).scalar_one()
    detail = dict(cancelled.detail or {})
    assert detail["cancelled_at_stage"] == "running"
    assert detail["result_id"] is None
    assert "replayed_tick_count" in detail, (
        "the run was cancelled somewhere other than the tick-strided checkpoint; the shared "
        f"clock's in-loop cancel was not what answered. detail={detail}"
    )
    assert detail["replayed_tick_count"] >= 1
    # The independent path's key must NOT be there: it would mean checkpoint #3 or #4
    # answered, i.e. this test passed without the loop's own check existing.
    assert "replayed_item_count" not in detail
