"""K-09 (a) — order matching primitives, tested as their own unit.

``limit_touch_evidence`` and ``decide_partial_fill`` were nested closures inside
``run_engine``. Neither actually needed the loop's mutable state — they only read it —
so the extraction lifts them out unchanged and makes the F-07i partial-fill policy
table directly testable. That table is the subtlest branch in the engine: whether a
touched resting order fills whole, fills partially, or is rejected below its minimum
decides how much size a run ever holds.

The rules under test are the never-fabricate ones:

* a print-less bar keeps the coarse bar-touch — data sparsity is never proof of no fill;
* under a tick-backed entry timing the print path is AUTHORITATIVE, so a bar extreme the
  prints never confirm does not fill;
* size-less print evidence degrades to the full-fill model and raises the L4 flag — a
  fraction is never invented.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.execution.fills import (
    _limit_price,
    _Tick,
    decide_partial_fill,
    limit_touch_evidence,
)
from entropia.domain.backtest.execution.state import _Bar

_LEVEL = Decimal("100")


def _bar(*, low: str, high: str) -> _Bar:
    return _Bar(
        timestamp="2024-01-21T00:00:00Z",
        open=Decimal("100"),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal("100"),
        volume=Decimal("10"),
    )


def _tick(price: str, size: str | None = None) -> _Tick:
    return _Tick(epoch_ms=0, price=Decimal(price), size=Decimal(size) if size is not None else None)


def _decide(
    planned: str, prints: tuple[_Tick, ...], *, active: bool = True, policy: str = "allowed"
):
    return decide_partial_fill(
        planned=Decimal(planned), prints=prints, partial_active=active, partial_policy=policy
    )


# --------------------------------------------------------------------------- #
# _limit_price                                                                 #
# --------------------------------------------------------------------------- #
def test_limit_price_rests_at_the_reference_by_default() -> None:
    assert _limit_price("entry_signal_price", _LEVEL, Decimal("5")) == _LEVEL


def test_limit_price_shifts_by_the_configured_offset() -> None:
    assert _limit_price("signal_price_minus_offset", _LEVEL, Decimal("5")) == Decimal("95")
    assert _limit_price("signal_price_plus_offset", _LEVEL, Decimal("5")) == Decimal("105")


# --------------------------------------------------------------------------- #
# limit_touch_evidence                                                         #
# --------------------------------------------------------------------------- #
def test_a_buy_limit_is_touched_when_the_bar_low_reaches_it() -> None:
    touched, prints = limit_touch_evidence(
        _LEVEL, "long", _bar(low="99", high="103"), (), tick_entry_authority=False
    )
    assert touched
    assert prints == ()


def test_a_buy_limit_is_not_touched_when_the_bar_stays_above() -> None:
    touched, _ = limit_touch_evidence(
        _LEVEL, "long", _bar(low="101", high="105"), (), tick_entry_authority=False
    )
    assert not touched


def test_a_sell_limit_is_touched_when_the_bar_high_reaches_it() -> None:
    touched, _ = limit_touch_evidence(
        _LEVEL, "short", _bar(low="96", high="101"), (), tick_entry_authority=False
    )
    assert touched


def test_a_print_less_bar_keeps_the_coarse_bar_touch() -> None:
    """Data sparsity is never treated as proof of no fill — even under tick authority."""
    touched, prints = limit_touch_evidence(
        _LEVEL, "long", _bar(low="99", high="103"), (), tick_entry_authority=True
    )
    assert touched
    assert prints == ()


def test_tick_authority_refuses_a_bar_extreme_the_prints_never_confirm() -> None:
    """The bar's low reaches the level but no print does; a simulation mode promises the
    print path decides."""
    bar = _bar(low="99", high="103")
    ticks = (_tick("102"), _tick("101"))
    touched, prints = limit_touch_evidence(_LEVEL, "long", bar, ticks, tick_entry_authority=True)
    assert not touched
    assert prints == ()


def test_without_tick_authority_the_bar_touch_still_wins_over_unconfirming_prints() -> None:
    bar = _bar(low="99", high="103")
    ticks = (_tick("102"), _tick("101"))
    touched, _ = limit_touch_evidence(_LEVEL, "long", bar, ticks, tick_entry_authority=False)
    assert touched


def test_a_confirming_print_fills_under_tick_authority_and_is_returned_as_evidence() -> None:
    bar = _bar(low="99", high="103")
    ticks = (_tick("102"), _tick("99.5", "3"))
    touched, prints = limit_touch_evidence(_LEVEL, "long", bar, ticks, tick_entry_authority=True)
    assert touched
    assert prints == (ticks[1],)


# --------------------------------------------------------------------------- #
# decide_partial_fill                                                          #
# --------------------------------------------------------------------------- #
def test_partial_fills_off_always_books_the_whole_plan() -> None:
    d = _decide("10", (_tick("100", "1"),), active=False)
    assert d.outcome == "full"
    assert d.filled_size == Decimal("10")
    assert d.remainder == Decimal("0")


def test_evidence_covering_the_plan_books_a_full_fill() -> None:
    d = _decide("10", (_tick("100", "6"), _tick("100", "4")))
    assert d.outcome == "full"
    assert d.filled_size == Decimal("10")


def test_evidence_short_of_the_plan_books_a_partial_with_the_remainder() -> None:
    d = _decide("10", (_tick("100", "4"),))
    assert d.outcome == "partial"
    assert d.filled_size == Decimal("4")
    assert d.remainder == Decimal("6")


def test_minimum_50_percent_rejects_a_sub_half_bar() -> None:
    """Nothing books; the order keeps resting whole."""
    d = _decide("10", (_tick("100", "4"),), policy="minimum_50_percent")
    assert d.outcome == "rejected_below_minimum"


def test_minimum_50_percent_accepts_exactly_half() -> None:
    d = _decide("10", (_tick("100", "5"),), policy="minimum_50_percent")
    assert d.outcome == "partial"
    assert d.filled_size == Decimal("5")


def test_size_less_prints_degrade_to_a_full_fill_and_raise_the_l4_flag() -> None:
    """A fraction is NEVER fabricated from evidence that carries no size."""
    d = _decide("10", (_tick("100"), _tick("100")))
    assert d.outcome == "full"
    assert d.filled_size == Decimal("10")
    assert d.evidence_missing


def test_sized_evidence_does_not_raise_the_missing_flag() -> None:
    assert not _decide("10", (_tick("100", "4"),)).evidence_missing


def test_a_bar_without_prints_is_a_full_fill_without_the_flag() -> None:
    """No prints at all is the coarse OHLCV model, not degraded tick evidence."""
    d = _decide("10", ())
    assert d.outcome == "full"
    assert not d.evidence_missing


def test_a_non_positive_plan_books_full_and_never_flags() -> None:
    d = _decide("0", (_tick("100"),))
    assert d.outcome == "full"
    assert not d.evidence_missing


def test_unsized_prints_are_ignored_when_others_carry_sizes() -> None:
    d = _decide("10", (_tick("100"), _tick("100", "3")))
    assert d.outcome == "partial"
    assert d.filled_size == Decimal("3")
