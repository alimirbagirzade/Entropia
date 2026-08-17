"""The describe/book split of P1, P3 and P4 (ADR-0002 §15 R-4, closure C1 / E4a).

``_ItemStepper``'s three decision phases used to do two things in one call: work out what
this bar means for the item, and immediately book it. A merged-clock caller (ADR-0002 §8)
cannot use that shape — the pool has to hear what every item WANTS, arbitrate across them,
and only then let the winners book. So each of the three phases is now a pair: a describe
half that answers, and a booking half that acts on the answer.

The golden digests (``test_backtest_engine_golden.py``) prove the composition did not move
a number. They cannot prove the property that makes the split worth having, because
``run_engine`` calls describe and book back to back on every bar: that the describe half is
genuinely READ-ONLY, so a pool may ask, refuse what it hears, and leave the item exactly as
it was. That is what this module pins, from both sides — nothing moves when only describing,
and the same things still move when booking.

The distinction matters because the pre-split code failed it silently: evaluating an entry
bumped ``suppressed_entries`` / ``entries_blocked_by_restriction`` / ``strength_adjustments``
and emitted ``filtered_no_entry`` while it was still only deciding. Those writes now travel
in ``_EntryDecision.effects`` and land only in ``apply_entry``.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

import tests.unit.test_backtest_decision_trace as trace
import tests.unit.test_backtest_engine as base
import tests.unit.test_backtest_funding as fund
import tests.unit.test_backtest_restrictions as restr
import tests.unit.test_backtest_signal_strength as strength
from entropia.domain.backtest.engine import EngineOutput, _build_stepper, run_engine
from entropia.domain.backtest.execution.state import _Ledger, _normalize
from tests.unit.engine_signal_plan import sma_entry_plan
from tests.unit.test_backtest_engine_golden import _digest
from tests.unit.test_backtest_engine_stepper import _batched


def _kwargs(**over: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "strategy_config": base._config(),
        "execution_key": "exec_key_describe_book",
        "indicator_plan": sma_entry_plan(),
    }
    out.update(over)
    return out


def _funding_case() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """A held position paying two funding records — the stepper suite's own scenario."""
    return fund._long_held(), _kwargs(
        funding=fund._schedule((22, "0.001"), (23, "0.002")),
        execution_key="exec_key_funding",
    )


def _blackout_case() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """A signal vetoed inside a blackout day — the one path that suppresses an entry."""
    bars = [*restr._flat(20), restr._BREAKOUT, restr._REBREAK]
    kwargs = _kwargs(
        strategy_config=restr._config(
            restrictions={
                "rule": "any",
                "filters": [restr._blackout(("2024-01-21", "2024-01-21"))],
            }
        ),
        execution_key="exec_key_restrictions",
        indicator_plan=sma_entry_plan(validity="until_opposite_signal"),
    )
    return bars, kwargs


def _strength_case() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """A volatility-adjusted entry — the only path that defers ``strength_adjustments``.

    Without this case that third deferral is unobserved: a negative control that put the
    counter back inline left every other scenario green, because none of them activates
    ``volatility_adjusted`` mode at all."""
    return strength._calm_recent(), _kwargs(
        strategy_config=strength._config(signal_strength_adjustment="volatility_adjusted"),
        execution_key="exec_key_strength",
    )


def _direction_veto_case() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """A short signal under a LONG-ONLY strategy — the direction-bias suppression path.

    Distinct from ``_blackout_case``: that one vetoes at the RESTRICTION gate and defers
    ``entries_blocked_by_restriction``; this one vetoes at the direction bias and defers
    ``suppressed_entries``. A negative control confirmed neither case catches the other's
    inline write, so both are required to cover the two counters."""
    closes = ["10", "10", "10", "10", "10", "10", "8", "8", "8"]
    return trace._plan_bars(closes), _kwargs(
        strategy_config=trace._config(direction="long"),
        execution_key="exec_key_trace",
        indicator_plan=trace._sma_plan(),
    )


def _ledger_fingerprint(led: _Ledger) -> tuple[Any, ...]:
    """Every ledger field a describe half could plausibly move, as one comparable value.

    Read off ``dataclasses.fields`` rather than an enumerated list on purpose: a counter
    added later is covered without anyone remembering to add it here, which is the failure
    mode this whole module exists to catch."""
    parts: list[Any] = []
    for f in dataclasses.fields(led):
        value = getattr(led, f.name)
        parts.append((f.name, len(value) if isinstance(value, list) else value))
    return tuple(parts)


def _lifecycle_fingerprint(stepper: Any) -> tuple[Any, ...]:
    """The position lifecycle state a describe half must not touch."""
    pos = stepper.open_position()
    return (
        None if pos is None else (pos.direction, pos.entry_price, pos.layers_filled, pos.size),
        len(stepper.ledger.trades),
        len(stepper.ledger.signal_events),
        len(stepper.ledger.filtered_events),
    )


def _drive_split(bars: list[dict[str, Any]], kwargs: dict[str, Any]) -> EngineOutput:
    """Replay through the SIX halves instead of the three phases, in ``_step``'s order."""
    stepper = _build_stepper(**kwargs)
    for raw in bars:
        bar = _normalize(raw)
        if bar is None:
            continue
        stepper.admit(bar)
        plan = stepper.compute_carry(bar)
        if plan is not None:
            stepper.book_carry(bar, plan)
        stepper.open_fills(bar)
        decision = stepper.evaluate_held(bar)
        if decision is not None:
            stepper.apply_held(bar, decision)
        else:
            entry = stepper.evaluate_entry(bar)
            if entry is not None:
                stepper.apply_entry(bar, entry)
        stepper.tail(bar)
    stepper.finalize()
    return stepper.output()


def _all_cases() -> list[tuple[str, list[dict[str, Any]], dict[str, Any]]]:
    """Every scenario the split is driven over. Each reaches a different describe branch."""
    return [
        ("baseline_stop_out", base._long_breakout_then_stop(), _kwargs()),
        ("funding_held", *_funding_case()),
        ("date_blackout", *_blackout_case()),
        ("volatility_strength", *_strength_case()),
        ("direction_veto", *_direction_veto_case()),
    ]


def test_the_six_halves_compose_into_the_three_phases() -> None:
    """Driving describe+book pairs is byte-identical to driving the phases.

    This is the split's correctness statement. ``_step`` still calls the phases, so every
    other test in the suite exercises the composed path; only this one proves the halves
    are separately drivable in the order a merged clock would use them."""
    for name, bars, kwargs in _all_cases():
        whole = run_engine(bar_batches=_batched(bars, 8), **kwargs)
        split = _drive_split(bars, kwargs)
        assert _digest(split) == _digest(whole), (
            f"{name}: driving the describe/book halves diverged from the composed phases"
        )


@pytest.mark.parametrize(("name", "bars", "kwargs"), _all_cases(), ids=[c[0] for c in _all_cases()])
def test_describing_an_entry_writes_nothing(
    name: str, bars: list[dict[str, Any]], kwargs: dict[str, Any]
) -> None:
    """``evaluate_entry`` moves no ledger field, emits no event and opens no position.

    Called repeatedly at every bar, BEFORE the booking path runs — so if any counter or
    event the old inline code wrote were still written during evaluation, the fingerprint
    moves here and the assertion names the bar.

    Parametrized over every scenario deliberately: the baseline never reaches a suppression
    branch, so running only that case would leave the three deferred counters — the exact
    writes this split exists to remove — unobserved. The blackout case is what reaches the
    restriction gate, and a negative control confirmed it fails when the write is put back."""
    stepper = _build_stepper(**kwargs)
    described = 0
    for raw in bars:
        bar = _normalize(raw)
        if bar is None:
            continue
        stepper.admit(bar)
        plan = stepper.compute_carry(bar)
        if plan is not None:
            stepper.book_carry(bar, plan)
        stepper.open_fills(bar)
        held = stepper.evaluate_held(bar)
        if held is not None:
            stepper.apply_held(bar, held)
            stepper.tail(bar)
            continue

        before_led = _ledger_fingerprint(stepper.ledger)
        before_life = _lifecycle_fingerprint(stepper)
        first = stepper.evaluate_entry(bar)
        for _ in range(3):
            again = stepper.evaluate_entry(bar)
            assert again == first, "describing the same bar twice gave two different answers"
        assert _ledger_fingerprint(stepper.ledger) == before_led, (
            f"evaluate_entry wrote to the ledger at {bar.timestamp}"
        )
        assert _lifecycle_fingerprint(stepper) == before_life, (
            f"evaluate_entry moved lifecycle state at {bar.timestamp}"
        )
        described += 1
        if first is not None:
            stepper.apply_entry(bar, first)
        stepper.tail(bar)

    assert described > 0, f"{name}: never reached P4, so nothing was actually described"


def test_a_described_entry_is_only_booked_when_it_is_applied() -> None:
    """The negative control for the test above: booking DOES move what describing did not.

    Without this, ``evaluate_entry`` returning a decision nobody books would satisfy the
    read-only assertion trivially — a phase that does nothing writes nothing."""
    bars = base._long_breakout_then_stop()
    stepper = _build_stepper(**_kwargs())
    booked_an_entry = False
    for raw in bars:
        bar = _normalize(raw)
        if bar is None:
            continue
        stepper.admit(bar)
        plan = stepper.compute_carry(bar)
        if plan is not None:
            stepper.book_carry(bar, plan)
        stepper.open_fills(bar)
        held = stepper.evaluate_held(bar)
        if held is not None:
            stepper.apply_held(bar, held)
            stepper.tail(bar)
            continue
        decision = stepper.evaluate_entry(bar)
        if decision is not None and decision.want is not None:
            before = _lifecycle_fingerprint(stepper)
            stepper.apply_entry(bar, decision)
            assert _lifecycle_fingerprint(stepper) != before, (
                "apply_entry booked nothing for a decision that wanted an entry"
            )
            booked_an_entry = True
        elif decision is not None:
            stepper.apply_entry(bar, decision)
        stepper.tail(bar)

    assert booked_an_entry, "the scenario never wanted an entry, so booking was never proven"


def test_a_suppressed_entry_defers_its_counter_and_its_event_to_the_booking_half() -> None:
    """The specific regression the split exists to prevent.

    A direction/restriction veto is the one path where evaluation used to write: it bumped a
    counter and emitted ``filtered_no_entry`` mid-decision. Those must now be carried on the
    decision and applied only by ``apply_entry`` — and still applied, not dropped."""
    bars, kwargs = _blackout_case()
    stepper = _build_stepper(**kwargs)
    suppressions_seen = 0
    for raw in bars:
        bar = _normalize(raw)
        if bar is None:
            continue
        stepper.admit(bar)
        plan = stepper.compute_carry(bar)
        if plan is not None:
            stepper.book_carry(bar, plan)
        stepper.open_fills(bar)
        held = stepper.evaluate_held(bar)
        if held is not None:
            stepper.apply_held(bar, held)
            stepper.tail(bar)
            continue
        decision = stepper.evaluate_entry(bar)
        if decision is None:
            stepper.tail(bar)
            continue
        if decision.effects:
            suppressions_seen += 1
            before = _ledger_fingerprint(stepper.ledger)
            events_before = len(stepper.ledger.filtered_events)
            stepper.apply_entry(bar, decision)
            assert _ledger_fingerprint(stepper.ledger) != before, (
                "the deferred suppression effects were never booked"
            )
            assert len(stepper.ledger.filtered_events) > events_before, (
                "the deferred filtered_no_entry event was never emitted"
            )
        else:
            stepper.apply_entry(bar, decision)
        stepper.tail(bar)

    assert suppressions_seen > 0, (
        "the blackout scenario suppressed no entry, so the deferral was never exercised"
    )


def test_describing_carry_does_not_advance_the_funding_cursor() -> None:
    """``compute_carry`` is re-askable: the cursor moves in ``book_carry``, not before.

    A describe half that advanced the cursor would charge each record once per ASK rather
    than once per bar, so a pool that polled twice would silently double-charge funding."""
    bars, kwargs = _funding_case()
    stepper = _build_stepper(**kwargs)
    charged_bars = 0
    for raw in bars:
        bar = _normalize(raw)
        if bar is None:
            continue
        stepper.admit(bar)
        before = _ledger_fingerprint(stepper.ledger)
        first = stepper.compute_carry(bar)
        for _ in range(3):
            assert stepper.compute_carry(bar) == first, (
                "asking for carry twice gave two different plans — the cursor moved"
            )
        assert _ledger_fingerprint(stepper.ledger) == before, (
            f"compute_carry wrote to the ledger at {bar.timestamp}"
        )
        if first is not None:
            if first.charges:
                charged_bars += 1
            stepper.book_carry(bar, first)
        stepper.open_fills(bar)
        held = stepper.evaluate_held(bar)
        if held is not None:
            stepper.apply_held(bar, held)
        else:
            entry = stepper.evaluate_entry(bar)
            if entry is not None:
                stepper.apply_entry(bar, entry)
        stepper.tail(bar)

    assert charged_bars > 0, "no funding was ever charged, so the cursor was never at risk"


def test_describing_a_held_position_names_the_exit_without_closing_it() -> None:
    """``evaluate_held`` reports the arm; only ``apply_held`` closes.

    P3 is where the pool learns what an item MUST do before ``E(t)`` is published
    (ADR-0002 §6 rule 4), so naming the exit has to be separable from taking it."""
    bars = base._long_breakout_then_stop()
    stepper = _build_stepper(**_kwargs())
    named_a_close = False
    for raw in bars:
        bar = _normalize(raw)
        if bar is None:
            continue
        stepper.admit(bar)
        plan = stepper.compute_carry(bar)
        if plan is not None:
            stepper.book_carry(bar, plan)
        stepper.open_fills(bar)

        before_led = _ledger_fingerprint(stepper.ledger)
        before_life = _lifecycle_fingerprint(stepper)
        decision = stepper.evaluate_held(bar)
        for _ in range(3):
            assert stepper.evaluate_held(bar) == decision, (
                "describing the held position twice gave two different arms"
            )
        assert _ledger_fingerprint(stepper.ledger) == before_led, (
            f"evaluate_held wrote to the ledger at {bar.timestamp}"
        )
        assert _lifecycle_fingerprint(stepper) == before_life, (
            f"evaluate_held closed or altered the position at {bar.timestamp}"
        )

        if decision is not None:
            if decision.branch in ("stop", "stop_exit_collision"):
                named_a_close = True
                stepper.apply_held(bar, decision)
                assert stepper.open_position() is None, (
                    "apply_held did not close a position its decision named a stop for"
                )
            else:
                stepper.apply_held(bar, decision)
        else:
            entry = stepper.evaluate_entry(bar)
            if entry is not None:
                stepper.apply_entry(bar, entry)
        stepper.tail(bar)

    assert named_a_close, "the scenario never stopped out, so the naming was never proven"
