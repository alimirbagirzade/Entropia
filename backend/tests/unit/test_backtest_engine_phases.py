"""The bar's phases, driven separately, must replay exactly like one whole ``step``.

ADIM 16 lifted ``run_engine``'s bar loop into a resumable stepper. That made the replay
suspendable BETWEEN bars, which is what a merged-clock caller needs to advance one item to
a given ``t`` — but it left the bar itself atomic, and ADR-0002 §8 needs it split. The phase
loop asks an item three separate questions at three different points of ONE shared tick:
what is it charged (P1), what must it close (P3), and what does it want (P4) — the last of
them sized against a portfolio ``E(t)`` that only exists after P3 has run for every sibling.
A whole-bar ``step`` cannot answer those in that order.

So this slice split the step body into the numbered sections of doc 15 §9.3 it already was,
and exposed them on ``_ItemStepper``. ``run_engine`` still drives them in the original order
and the 46 golden digests are the proof that it did not move (ADR-0002 §15 R-4).

This module proves the half no digest can see: that the phases are genuinely SEPARATE — that
driving them by hand reproduces the whole bar, that the former ``if``/``elif`` exclusivity
survived being pulled into two callables, and that the supplied sizing equity reaches the
sizing chain and does not outlive the phase it was given to.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

import tests.unit.test_backtest_engine as base
import tests.unit.test_backtest_engine_stepper as stepper_tests
from entropia.domain.backtest.engine import EngineOutput, _build_stepper, run_engine
from entropia.domain.backtest.execution.state import AllocationExecution, _normalize
from tests.unit.engine_signal_plan import sma_entry_plan
from tests.unit.test_backtest_engine_golden import _digest

# A bar that CLOSES a position through the held arm must not also open a fresh one — the
# ``elif`` used to guarantee that for free. These two scenarios are the ones where ignoring
# the returned flag actually changes the output, i.e. where the guard carries its weight.
_EXCLUSIVITY_CASES = ("baseline_stop_out", "stop_order")


def _drive_phases(
    bars: list[dict[str, Any]],
    kwargs: dict[str, Any],
    *,
    ignore_held_flag: bool = False,
) -> EngineOutput:
    """Drive the bar the way the phase loop does: one phase per call, in ADR-0002 §8 order."""
    stepper = _build_stepper(**kwargs)
    for raw in bars:
        bar = _normalize(raw)
        if bar is None:
            continue
        stepper.admit(bar)
        stepper.carry(bar)
        stepper.open_fills(bar)
        held = stepper.held(bar)
        if ignore_held_flag or not held:
            stepper.entry(bar)
        stepper.tail(bar)
    stepper.finalize()
    return stepper.output()


@pytest.mark.parametrize(
    ("name", "bars", "kwargs"),
    stepper_tests._cases(),
    ids=[c[0] for c in stepper_tests._cases()],
)
def test_driving_the_phases_by_hand_replays_identically_to_run_engine(
    name: str, bars: list[dict[str, Any]], kwargs: dict[str, Any]
) -> None:
    """The FULL output digest is identical whether the bar runs as one step or as its phases.

    This is the claim the split has to earn: the phases are the same statements over the same
    state in the same order, so a caller that interleaves them with a sibling's phases is
    replaying the item the engine would have replayed."""
    whole = _digest(run_engine(bar_batches=stepper_tests._batched(bars, 8), **kwargs))
    by_phase = _digest(_drive_phases(bars, kwargs))
    assert by_phase == whole, (
        f"{name}: driving the phases separately changed the output. A phase either reads "
        "state a later one writes, or the split moved a statement across a boundary."
    )


@pytest.mark.parametrize(
    ("name", "bars", "kwargs"),
    [c for c in stepper_tests._cases() if c[0] in _EXCLUSIVITY_CASES],
    ids=_EXCLUSIVITY_CASES,
)
def test_the_held_arm_still_excludes_a_fresh_entry_on_the_same_bar(
    name: str, bars: list[dict[str, Any]], kwargs: dict[str, Any]
) -> None:
    """``_phase_held``'s return value is load-bearing, not decoration.

    The former ``if position is not None: ... elif <entry>: ...`` made exclusivity free. Once
    the two arms are separate callables, a caller that ignores the flag would offer a fresh
    entry to a bar that just stopped out — so the guard must be observable. Driving these two
    scenarios WITHOUT it produces a different run, which is what makes that assertion real
    rather than a restatement of the test above."""
    whole = _digest(run_engine(bar_batches=stepper_tests._batched(bars, 8), **kwargs))
    ignored = _digest(_drive_phases(bars, kwargs, ignore_held_flag=True))
    assert ignored != whole, (
        f"{name}: ignoring the held flag did not change the output, so this scenario cannot "
        "prove the exclusivity guard. Pick one where a stop closes a position on a bar that "
        "also carries an entry signal."
    )


def _alloc(pool: str) -> AllocationExecution:
    """A COMPOUNDING sleeve, so the cap tracks live equity and a supplied one is observable."""
    return AllocationExecution(
        initial_capital=Decimal(pool),
        reserve_percent=Decimal("0"),
        compound=True,
        item_share_percent=Decimal("100"),
        currency="USDT",
    )


def _first_open_size(*, equity: Decimal | None, pool: str = "1000.00") -> Decimal:
    """The size of the first position opened, with ``equity`` supplied to every P4.

    The pool is deliberately SMALL relative to the fixture's price, so the sleeve cap is the
    binding constraint. ``base._config`` sizes by a flat ``base_position_size``, which no
    equity can move on its own — it is ``_cap_to_sleeve`` that reads the valuation, and that
    is exactly the ADR-0002 §7 path a participant needs to redirect at the shared ``E(t)``."""
    stepper = _build_stepper(
        strategy_config=base._config(),
        execution_key="exec_key_phases",
        indicator_plan=sma_entry_plan(),
        allocation=_alloc(pool),
    )
    for raw in base._long_breakout_then_stop():
        bar = _normalize(raw)
        if bar is None:
            continue
        stepper.admit(bar)
        stepper.carry(bar)
        stepper.open_fills(bar)
        if not stepper.held(bar):
            stepper.entry(bar, equity=equity)
        stepper.tail(bar)
        position = stepper.open_position()
        if position is not None:
            return position.size
    raise AssertionError("the fixture never opened a position")


def test_the_entry_phase_sizes_against_the_supplied_equity() -> None:
    """P4's ``equity`` reaches the sizing chain — the whole point of the parameter.

    Under a shared pool the sleeve is a slice of the PORTFOLIO's equity, not of a private
    ledger that no longer holds the capital (ADR-0002 §7). A participant therefore hands the
    published ``E(t)`` to this phase, and it has to be what the size is measured from."""
    own_ledger = _first_open_size(equity=None)
    doubled = _first_open_size(equity=Decimal("20000.00"))
    assert doubled > own_ledger, (
        "supplying a larger E(t) did not open a larger position, so the parameter never "
        "reached sleeve_capital / _position_size."
    )


def test_omitting_the_equity_is_identical_to_the_ledgers_own() -> None:
    """The default is not a new policy: ``None`` means what the engine already meant."""
    assert _first_open_size(equity=None) == _first_open_size(equity=Decimal("1000.00"))


def _digest_with_override(*, on_bars: set[int] | None) -> str:
    """Replay the fixture, supplying a huge ``E(t)`` to P4 on the named bar indices only."""
    stepper = _build_stepper(
        strategy_config=base._config(),
        execution_key="exec_key_phases",
        indicator_plan=sma_entry_plan(),
        allocation=_alloc("1000.00"),
    )
    for index, raw in enumerate(base._long_breakout_then_stop()):
        bar = _normalize(raw)
        if bar is None:
            continue
        stepper.admit(bar)
        stepper.carry(bar)
        stepper.open_fills(bar)
        if not stepper.held(bar):
            supplied = Decimal("999999.00") if on_bars is not None and index in on_bars else None
            stepper.entry(bar, equity=supplied)
        stepper.tail(bar)
    stepper.finalize()
    return _digest(stepper.output())


def test_the_supplied_equity_does_not_outlive_the_phase_it_was_given_to() -> None:
    """Scoped to the call, so a stale valuation can never size a later bar.

    A snapshot is published per tick and superseded by the next one. If the override leaked
    past its phase, an entry on a LATER bar would be sized against an ``E(t)`` the portfolio
    had already moved on from — silently, and in the direction of the last override. So
    supplying one on the first (warm-up) bar alone must land exactly where supplying none
    lands, while supplying it on every bar must NOT — otherwise the first assertion would
    pass for the trivial reason that the parameter does nothing at all."""
    none_supplied = _digest_with_override(on_bars=None)
    first_bar_only = _digest_with_override(on_bars={0})
    every_bar = _digest_with_override(on_bars=set(range(len(base._long_breakout_then_stop()))))

    assert first_bar_only == none_supplied, (
        "an override given to ONE phase changed a later bar's sizing, so it outlived the "
        "call it was scoped to."
    )
    assert every_bar != none_supplied, (
        "supplying the override on every bar changed nothing, so the assertion above is "
        "vacuous — it would hold even if `equity` were ignored entirely."
    )
