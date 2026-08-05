"""The bar loop, driven one bar at a time, must replay exactly like ``run_engine``.

ADIM 16 lifted ``run_engine``'s bar-loop body into ``_build_stepper``'s ``step`` so a
caller that owns a MERGED clock (ADR-0002 §8) can advance ONE item to a given ``t``
instead of replaying it whole. ``run_engine`` kept its signature and became a driver
over that stepper.

The refactor's acceptance proof is the 46 recorded golden digests
(``test_backtest_engine_golden.py``, ADR-0002 §15 R-4) — they prove ``run_engine`` did
not move. This module proves the OTHER half, which no digest can see: that the stepper
is genuinely **resumable**, i.e. that suspending the replay between bars carries the
same state the loop used to carry in ``run_engine``'s frame.

That is not a restatement of the golden test. ``run_engine`` feeds the stepper from one
generator in one uninterrupted pass, so a carried name that had silently become a
per-bar local would still produce the recorded digest as long as it happened to be
written before it was read on every bar. Driving the SAME scenarios one bar per call —
and, for the tick-cursor case, interleaved with reads — is what makes the ten carried
names observable. The cases below are chosen to hold each of them across a bar
boundary: an unfilled limit order (``working_limit`` / ``pending``), an untriggered stop
(``working_stop``), a laddering position (``position`` / ``scale_signal`` /
``prev_scale_signal``), a held position paying funding (``funding_idx``), a signal held
across a blackout window (``prev_entry_signal`` / ``current_day``) and a resting touch
exit (``exit_touch``).
"""

from __future__ import annotations

from typing import Any

import pytest

import tests.unit.test_backtest_engine as base
import tests.unit.test_backtest_funding as fund
import tests.unit.test_backtest_limit_orders as lim
import tests.unit.test_backtest_restrictions as restr
import tests.unit.test_backtest_scaling as scal
import tests.unit.test_backtest_stop_orders as stops
from entropia.domain.backtest.engine import EngineOutput, _build_stepper, run_engine
from entropia.domain.backtest.execution.state import _normalize
from tests.unit.engine_signal_plan import sma_entry_plan
from tests.unit.test_backtest_engine_golden import _digest


def _case(bars: list[dict[str, Any]], **kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One scenario: the bar list plus the arguments BOTH entry points receive."""
    kwargs.setdefault("execution_key", "exec_key_stepper")
    kwargs.setdefault("indicator_plan", sma_entry_plan())
    return bars, kwargs


def _cases() -> list[tuple[str, list[dict[str, Any]], dict[str, Any]]]:
    """One entry per name the bar loop carries across a bar boundary."""
    out: list[tuple[str, list[dict[str, Any]], dict[str, Any]]] = []

    def add(name: str, case: tuple[list[dict[str, Any]], dict[str, Any]]) -> None:
        out.append((name, case[0], case[1]))

    # position / prev_entry_signal — a plain entry held to a stop-out.
    add("baseline_stop_out", _case(base._long_breakout_then_stop(), strategy_config=base._config()))
    # working_limit / pending — a limit ENTRY resting across bars, then touched.
    add(
        "limit_touch",
        _case(
            lim._long_breakout_then(
                [
                    lim._fu(22, "102", "102", "98", "101"),
                    lim._fu(23, "101", "103", "100", "102"),
                ]
            ),
            strategy_config=lim._config(order_config=lim._limit_order()),
        ),
    )
    # working_limit — a limit that NEVER touches, so it is still resting at end-of-data
    # and only ``_finalize`` cancels it.
    add(
        "limit_never_touches",
        _case(
            lim._long_breakout_then([lim._fu(22, "102", "104", "103", "104")]),
            strategy_config=lim._config(order_config=lim._limit_order()),
        ),
    )
    # working_stop — a stop ENTRY trigger resting across bars.
    add(
        "stop_order",
        _case(
            stops._long_breakout_then(
                [
                    stops._fu(22, "102", "106", "101", "105"),
                    stops._fu(23, "105", "105", "99", "100"),
                ]
            ),
            strategy_config=stops._config(order_config=stops._stop_order()),
        ),
    )
    # scale_signal / prev_scale_signal / position — the ladder adds layers on later bars.
    add(
        "price_ladder",
        _case(
            scal._long_then(
                [
                    scal._fu(22, "102", "108", "102", "107"),
                    scal._fu(23, "107", "115", "106", "114"),
                ]
            ),
            strategy_config=scal._config(scaling=scal._price_scaling()),
        ),
    )
    # funding_idx — the as-of cursor advances over two records on two different bars.
    add(
        "funding_two_records",
        _case(
            fund._long_held(),
            strategy_config=base._config(),
            funding=fund._schedule((22, "0.001"), (23, "0.002")),
            execution_key="exec_key_funding",
        ),
    )
    # current_day / prev_entry_signal — a HELD signal vetoed inside a blackout day and
    # admitted on the next day, which is exactly a decision that spans a bar boundary.
    add(
        "date_blackout_then_entry",
        _case(
            [*restr._flat(20), restr._BREAKOUT, restr._REBREAK],
            strategy_config=restr._config(
                restrictions={
                    "rule": "any",
                    "filters": [restr._blackout(("2024-01-21", "2024-01-21"))],
                }
            ),
            execution_key="exec_key_restrictions",
            indicator_plan=sma_entry_plan(validity="until_opposite_signal"),
        ),
    )
    return out


def _batched(bars: list[dict[str, Any]], size: int) -> Any:
    for start in range(0, len(bars), size):
        yield bars[start : start + size]


def _step_one_bar_at_a_time(bars: list[dict[str, Any]], kwargs: dict[str, Any]) -> EngineOutput:
    """Drive the stepper the way a merged-clock caller would: one bar per call."""
    stepper = _build_stepper(**kwargs)
    for raw in bars:
        bar = _normalize(raw)
        if bar is not None:
            stepper.step(bar)
    stepper.finalize()
    return stepper.output()


@pytest.mark.parametrize(("name", "bars", "kwargs"), _cases(), ids=[c[0] for c in _cases()])
def test_stepping_one_bar_at_a_time_replays_identically_to_run_engine(
    name: str, bars: list[dict[str, Any]], kwargs: dict[str, Any]
) -> None:
    """The FULL output digest is identical whether the loop runs to completion or is
    suspended between every pair of bars."""
    whole = run_engine(bar_batches=_batched(bars, 8), **kwargs)
    suspended = _step_one_bar_at_a_time(bars, kwargs)
    assert _digest(suspended) == _digest(whole), (
        f"{name}: suspending the replay between bars changed the output. A name the bar "
        "loop carries across bars is missing from _step's `nonlocal` block."
    )


def test_the_batching_of_the_bar_stream_is_not_observable() -> None:
    """A driver's batch size is an I/O detail, never a modelling input — the stepper
    contract only holds if the two are independent."""
    bars = base._long_breakout_then_stop()
    kwargs: dict[str, Any] = {
        "strategy_config": base._config(),
        "execution_key": "exec_key_stepper",
        "indicator_plan": sma_entry_plan(),
    }
    digests = {_digest(run_engine(bar_batches=_batched(bars, n), **kwargs)) for n in (1, 3, 8, 999)}
    assert len(digests) == 1
    assert digests == {_digest(_step_one_bar_at_a_time(bars, kwargs))}


def test_the_stepper_holds_an_open_position_between_steps() -> None:
    """The resumability claim, stated directly: a position opened on one step is still
    open when the NEXT step is called, and end-of-data settlement closes it."""
    # These bars enter and are STILL HELD at the last one, so the position has to survive
    # several step boundaries and the close can only come from end-of-data settlement.
    bars = fund._long_held()
    stepper = _build_stepper(
        strategy_config=base._config(),
        execution_key="exec_key_stepper",
        indicator_plan=sma_entry_plan(),
    )
    held_between_steps = 0
    for index, raw in enumerate(bars, start=1):
        bar = _normalize(raw)
        assert bar is not None
        stepper.step(bar)
        # The read happens BETWEEN steps — the state must survive the return.
        assert stepper.ledger.bars_seen == index
        if stepper.open_position() is not None:
            held_between_steps += 1

    assert held_between_steps > 1, "the position never survived a step boundary"
    assert stepper.open_position() is not None, "the run should end with a position still open"
    stepper.finalize()
    assert stepper.open_position() is None, "end-of-data must close the open position"
    assert [t.exit_reason for t in stepper.output().trades] == ["end_of_data"]


def test_the_stepper_refuses_an_unresolved_strategy_before_any_bar() -> None:
    """The F-04 fail-closed gate lives in the factory, not in the loop: a run with no
    resolved plan must raise before a single bar can be stepped."""
    from entropia.domain.backtest.engine import UnresolvedStrategyError

    with pytest.raises(UnresolvedStrategyError):
        _build_stepper(strategy_config=base._config(), execution_key="exec_key_stepper")
