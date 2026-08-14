"""T-02 — the trade-booking core, tested as its own unit.

``execution/booking.py`` arrived with K-10b (PR #437) carrying the three routines that
WRITE to a run's accumulating state: appending a decision event, closing (or
part-closing) a position, and topping an open position up with a partial-fill
remainder. It shipped with no test module of its own — the only consumer was
``engine.py``, so every one of its branches was reachable only through a full bar
replay, and the golden digest guard proves *that nothing moved* without saying what
any single branch is supposed to do.

This module locks the money arithmetic directly. It is a CHARACTERIZATION suite: every
expectation below is a literal transcribed from a hand-computed table, never re-derived
from the module under test, so a change in the arithmetic breaks a test instead of
quietly moving the expectation with it.

What is deliberately pinned, because it is where a booking bug hides silently:

* the long/short sign and the ADVERSE fill side on the exit leg;
* commission as ONE charge per exit FILL (GH #552 / PD-2), so a partial lot and a full
  close cost the same and four 0.25 lots cost four times a single close — the entry fill
  pays its own at ``engine._do_open`` and never appears in a trade row;
* the classification boundaries at exactly zero PnL — a 0-PnL lot is not a winner and
  does not extend the loss streak, and it books a 0 into ``gross_loss``;
* ``exposure`` measured against the equity BEFORE the lot is booked, and its
  divide-by-zero guard;
* ``peak``/``drawdown`` ratcheting, which is what ``max_drawdown_pct`` is built from;
* the two seq counters, which disagree on base by design: a trade row is 1-based, a
  decision event is 0-based;
* that one call appends exactly ONE trade row, ONE equity point and ONE event — the
  double-booking failure mode.

Two behaviours recorded here are ODD but are the shipped behaviour and are locked as
found, NOT corrected (see ``test_close_position_treats_a_fraction_above_one_as_a_full_close``
and ``test_close_position_books_a_zero_fraction_as_an_empty_partial_lot``). Changing
either is a modelling decision that shifts engine output and therefore needs an
``ENGINE_VERSION`` bump; it is out of scope for a test-only slice.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.execution.booking import (
    absorb_remainder,
    close_position,
    emit_event,
)
from entropia.domain.backtest.execution.costs import FillCosts
from entropia.domain.backtest.execution.state import _Bar, _Ledger, _Position

_ENTRY_TIME = "2024-01-01T00:00:00Z"
_EXIT_TIME = "2024-01-01T05:00:00Z"
_ENTRY_BAR_SEQ = 3
_EXIT_BAR_SEQ = 8
_START_EQUITY = Decimal("10000.00")


def _ledger(*, equity: str = "10000.00", peak: str | None = None) -> _Ledger:
    """A ledger seeded the way ``run_engine`` seeds it: equity and peak at capital."""
    led = _Ledger()
    led.equity = Decimal(equity)
    led.peak = Decimal(peak if peak is not None else equity)
    return led


def _position(
    *,
    direction: str = "long",
    entry_price: str = "100",
    size: str = "10",
    peak_notional: str = "1000.00",
) -> _Position:
    price = Decimal(entry_price)
    qty = Decimal(size)
    return _Position(
        position_seq=1,
        entry_bar_seq=_ENTRY_BAR_SEQ,
        direction=direction,
        entry_time=_ENTRY_TIME,
        entry_price=price,
        size=qty,
        pct_stop=Decimal("95"),
        abs_stop=Decimal("94"),
        trail_pct=Decimal("2"),
        trail_anchor=price,
        entry_notional=(price * qty).quantize(Decimal("0.01")),
        peak_notional=Decimal(peak_notional),
    )


def _costs(*, half_spread: str = "0", slippage: str = "0", commission: str = "0") -> FillCosts:
    return FillCosts(
        half_spread=Decimal(half_spread),
        slippage=Decimal(slippage),
        commission=Decimal(commission),
    )


def _bar(timestamp: str = "2024-01-01T04:00:00Z", close: str = "130") -> _Bar:
    price = Decimal(close)
    return _Bar(
        timestamp=timestamp,
        open=price,
        high=price,
        low=price,
        close=price,
        volume=Decimal("1000"),
    )


def _close(
    led: _Ledger,
    pos: _Position,
    costs: FillCosts,
    *,
    exit_price_raw: str,
    reason: str = "signal_exit",
    fraction: str = "1",
) -> bool:
    return close_position(
        led,
        pos,
        costs,
        exit_time=_EXIT_TIME,
        exit_price_raw=Decimal(exit_price_raw),
        reason=reason,
        bar_seq=_EXIT_BAR_SEQ,
        fraction=Decimal(fraction),
    )


# --------------------------------------------------------------------------- #
# emit_event                                                                   #
# --------------------------------------------------------------------------- #
def test_emit_event_numbers_decision_events_from_zero() -> None:
    """The decision journal is 0-based, unlike the 1-based trade ledger."""
    led = _ledger()

    emit_event(led, "entry_signal", event_time=_ENTRY_TIME, direction="long", bar_seq=1, detail={})
    emit_event(led, "entry_fill", event_time=_ENTRY_TIME, direction="long", bar_seq=1, detail={})

    assert [event.seq for event in led.signal_events] == [0, 1]
    assert [event.event_type for event in led.signal_events] == ["entry_signal", "entry_fill"]


def test_emit_event_binds_every_event_to_its_replayed_bar_index() -> None:
    led = _ledger()

    emit_event(
        led,
        "entry_signal",
        event_time=_ENTRY_TIME,
        direction="short",
        bar_seq=7,
        detail={"rule": "breakout"},
    )

    event = led.signal_events[0]
    assert event.detail == {"bar_seq": 7, "rule": "breakout"}
    assert event.event_time == _ENTRY_TIME
    assert event.direction == "short"


def test_emit_event_accepts_a_directionless_event() -> None:
    """Run-level events (a funding charge, a blocked entry) carry no direction."""
    led = _ledger()

    emit_event(led, "funding_charge", event_time=_ENTRY_TIME, direction=None, bar_seq=2, detail={})

    assert led.signal_events[0].direction is None


# --------------------------------------------------------------------------- #
# close_position — the canonical arithmetic table                              #
#                                                                              #
# Every figure below is hand-computed and transcribed as a literal. Recomputing #
# any of them from the module under test would make the test agree with a bug.  #
# --------------------------------------------------------------------------- #
def test_close_position_books_a_winning_long_at_the_adverse_exit_side() -> None:
    """long 10 @100 -> 110, zero costs: gross 100.00, pnl 100.00, equity 10100.00."""
    led = _ledger()
    pos = _position(peak_notional="1200.00")

    is_full = _close(led, pos, _costs(), exit_price_raw="110", reason="take_profit")

    assert is_full is True
    assert led.equity == Decimal("10100.00")
    assert led.peak == Decimal("10100.00")
    assert led.winners == 1
    assert led.gross_profit == Decimal("100.00")
    assert led.gross_loss == Decimal("0")
    assert led.day_realized == Decimal("100.00")
    assert led.loss_streak == 0

    trade = led.trades[0]
    assert trade.seq == 1
    assert trade.direction == "long"
    assert trade.entry_price == Decimal("100")
    assert trade.exit_price == Decimal("110.00")
    assert trade.pnl == Decimal("100.00")
    assert trade.exit_reason == "take_profit"


def test_close_position_inverts_the_sign_and_the_fill_side_for_a_short() -> None:
    """short 10 @100 -> 90 with spread 0.5 + 2% slip + 2.00 commission.

    The exit of a short is a BUY, so it pays up: (90 + 0.5) * 1.02 = 92.31. The sign
    flips, so the move down is a profit: (92.31 - 100) * 10 * -1 = 76.90, less this exit
    fill's own 2.00 commission = 74.90. (Per-FILL, GH #552: the entry leg's 2.00 was
    charged at entry and is not in this row; the old model billed 4.00 here.)
    """
    led = _ledger()
    pos = _position(direction="short")

    _close(
        led,
        pos,
        _costs(half_spread="0.5", slippage="0.02", commission="2"),
        exit_price_raw="90",
    )

    assert led.trades[0].exit_price == Decimal("92.31")
    assert led.trades[0].pnl == Decimal("74.90")
    assert led.equity == Decimal("10074.90")
    assert led.winners == 1


def test_close_position_charges_one_commission_for_the_exit_fill() -> None:
    """Flat exit, 2.00 per fill: this close is ONE fill and pays 2.00.

    GH #552 / PD-2. The old model charged 4.00 here — the entry leg billed at the exit —
    which is why this was called ``..._as_a_round_trip_on_a_full_close``. The entry leg is
    now charged at ``engine._do_open``, so ``close_position`` never sees it. This function
    is called directly here, with no entry, which is exactly why the equity below moves by
    the exit fill alone."""
    led = _ledger()
    pos = _position()

    _close(led, pos, _costs(commission="2"), exit_price_raw="100")

    assert led.trades[0].pnl == Decimal("-2.00")
    assert led.equity == Decimal("9998.00")


def test_partial_lots_each_pay_their_own_fill_commission() -> None:
    """Four 0.25 lots are four exit FILLS and pay four commissions — 8.00, not 2.00.

    This inverts the invariant this test used to pin. Under the old model commission was
    pro-rated on the fraction so that N partials summing to 1 cost exactly one full close;
    the cost of exiting was independent of how many fills it took. Per-FILL says the
    opposite and says it deliberately: each fill is a trade the venue charges for, which is
    what ``costs.commission``'s own "Per-trade fee" description means. Scaling out is
    genuinely more expensive than closing at once."""
    led = _ledger()
    pos = _position()
    for _ in range(4):
        _close(led, pos, _costs(commission="2"), exit_price_raw="100", fraction="0.25")

    assert [trade.pnl for trade in led.trades] == [Decimal("-2.00")] * 4
    assert led.equity == Decimal("9992.00")


def test_close_position_extends_the_loss_streak_and_the_stop_streak_on_a_stop() -> None:
    """long 10 @100 -> 95: pnl -50.00, and gross_loss carries the ABSOLUTE value."""
    led = _ledger()
    pos = _position()

    _close(led, pos, _costs(), exit_price_raw="95", reason="stop_loss")

    assert led.trades[0].pnl == Decimal("-50.00")
    assert led.gross_loss == Decimal("50.00")
    assert led.gross_profit == Decimal("0")
    assert led.winners == 0
    assert led.day_realized == Decimal("-50.00")
    assert led.loss_streak == 1
    assert led.stops_hit == 1
    assert led.stop_streak == 1
    assert led.max_stop_streak == 1


def test_close_position_remembers_the_longest_stop_run_after_it_is_broken() -> None:
    """A non-stop exit resets the live streak; the high-water mark survives."""
    led = _ledger()
    for _ in range(3):
        _close(led, _position(), _costs(), exit_price_raw="95", reason="stop_loss")
    _close(led, _position(), _costs(), exit_price_raw="110", reason="take_profit")

    assert led.stops_hit == 3
    assert led.stop_streak == 0
    assert led.max_stop_streak == 3


def test_close_position_treats_a_zero_pnl_lot_as_neither_a_win_nor_a_loss() -> None:
    """Exactly-zero PnL is the classification boundary: not a winner, and it RESETS
    the consecutive-loss run rather than extending it (booking.py:97-109)."""
    led = _ledger()
    led.loss_streak = 2
    pos = _position()

    _close(led, pos, _costs(), exit_price_raw="100")

    assert led.trades[0].pnl == Decimal("0.00")
    assert led.winners == 0
    assert led.gross_profit == Decimal("0")
    assert led.gross_loss == Decimal("0")
    assert led.loss_streak == 0


def test_close_position_ratchets_the_peak_and_reports_drawdown_beneath_it() -> None:
    """Equity falling from a peak of 10000.00 to 9950.00 is a 50.00 drawdown."""
    led = _ledger()

    _close(led, _position(), _costs(), exit_price_raw="95", reason="stop_loss")

    assert led.equity == Decimal("9950.00")
    assert led.peak == Decimal("10000.00")
    assert led.equity_points[0].drawdown == Decimal("50.00")


def test_close_position_measures_exposure_against_equity_before_the_lot() -> None:
    """1000.00 of notional against the 10000.00 equity held BEFORE booking = 10.0000%.

    Using the post-trade equity would understate exposure on every winning lot.
    """
    led = _ledger()

    _close(led, _position(), _costs(), exit_price_raw="110")

    assert led.equity_points[0].exposure == Decimal("10.0000")


def test_close_position_reports_zero_exposure_when_equity_is_wiped_out() -> None:
    """The divide-by-zero guard: a busted account reports 0.0000, not an error."""
    led = _ledger(equity="0.00")

    _close(led, _position(), _costs(), exit_price_raw="110")

    assert led.equity_points[0].exposure == Decimal("0.0000")


def test_close_position_appends_exactly_one_row_to_each_journal() -> None:
    """The double-booking guard: one close is one trade, one equity point, one event."""
    led = _ledger()

    _close(led, _position(), _costs(), exit_price_raw="110")

    assert len(led.trades) == 1
    assert len(led.equity_points) == 1
    assert len(led.signal_events) == 1
    assert len(led.position_intervals) == 1


def test_close_position_numbers_the_trade_and_its_equity_point_alike_from_one() -> None:
    """The trade ledger is 1-based and the equity curve shares its seq."""
    led = _ledger()
    for _ in range(3):
        _close(led, _position(), _costs(), exit_price_raw="110")

    assert [trade.seq for trade in led.trades] == [1, 2, 3]
    assert [point.seq for point in led.equity_points] == [1, 2, 3]


def test_close_position_records_the_held_window_at_its_peak_notional() -> None:
    """The interval carries the PEAK notional over the position's life, not the entry
    notional — the conservative figure a portfolio cap replays against."""
    led = _ledger()
    pos = _position(peak_notional="1750.00")

    _close(led, pos, _costs(), exit_price_raw="110")

    assert led.position_intervals == [
        {
            "entry_time": _ENTRY_TIME,
            "exit_time": _EXIT_TIME,
            "direction": "long",
            "peak_notional": Decimal("1750.00"),
        }
    ]


def test_close_position_falls_back_to_entry_notional_when_no_peak_was_ratcheted() -> None:
    """A position that never scaled has a peak_notional of 0 from the dataclass default;
    the interval must still report the notional actually held."""
    led = _ledger()
    pos = _position(peak_notional="0")

    _close(led, pos, _costs(), exit_price_raw="110")

    assert led.position_intervals[0]["peak_notional"] == Decimal("1000.00")


def test_close_position_emits_a_close_event_linking_the_trade_and_the_holding_span() -> None:
    led = _ledger()
    pos = _position()

    _close(led, pos, _costs(), exit_price_raw="95", reason="stop_loss")

    event = led.signal_events[0]
    assert event.event_type == "position_close"
    assert event.direction == "long"
    assert event.detail == {
        "bar_seq": _EXIT_BAR_SEQ,
        "position_seq": 1,
        "trade_seq": 1,
        "exit_reason": "stop_loss",
        "exit_price": "95.00",
        "pnl": "-50.00",
        "entry_bar_seq": _ENTRY_BAR_SEQ,
        "holding_bars": 5,
    }


# --------------------------------------------------------------------------- #
# close_position — the partial-close branch                                    #
# --------------------------------------------------------------------------- #
def test_close_position_realizes_a_partial_lot_and_leaves_the_position_open() -> None:
    """0.25 of long 8 @100 -> 120 with 2.00 commission.

    close_size 2.00, gross 40.00, commission 2.00 (this exit fill's own, GH #552 — it used
    to be pro-rated to 2*2*0.25 = 1.00), pnl 38.00; the position survives at size 6.00 with
    its notional refreshed to 600.00.
    """
    led = _ledger()
    pos = _position(size="8", peak_notional="800.00")

    is_full = _close(led, pos, _costs(commission="2"), exit_price_raw="120", fraction="0.25")

    assert is_full is False
    assert led.trades[0].pnl == Decimal("38.00")
    assert led.equity == Decimal("10038.00")
    assert led.partial_closes == 1
    assert pos.size == Decimal("6.00")
    assert pos.entry_notional == Decimal("600.00")


def test_close_position_labels_a_partial_lot_as_a_partial_exit() -> None:
    """The trade row's reason is normalized; the ORIGINAL reason survives in the event."""
    led = _ledger()
    pos = _position(size="8")

    _close(led, pos, _costs(), exit_price_raw="120", reason="take_profit", fraction="0.25")

    assert led.trades[0].exit_reason == "partial_exit"
    assert led.signal_events[0].detail["exit_reason"] == "take_profit"


def test_close_position_omits_the_held_window_until_the_position_fully_closes() -> None:
    """An interval is the record of a CLOSED position; a part-closed one is still open."""
    led = _ledger()
    pos = _position(size="8")

    _close(led, pos, _costs(), exit_price_raw="120", fraction="0.25")

    assert led.position_intervals == []


def test_close_position_emits_a_partial_event_carrying_the_fraction_and_remainder() -> None:
    led = _ledger()
    pos = _position(size="8")

    _close(led, pos, _costs(), exit_price_raw="120", fraction="0.25")

    event = led.signal_events[0]
    assert event.event_type == "position_partial_close"
    assert event.detail["closed_fraction"] == "0.25"
    assert event.detail["remaining_size"] == "6.00"


def test_close_position_treats_a_fraction_above_one_as_a_full_close() -> None:
    """LOCKED AS FOUND: ``fraction >= 1`` takes the full-close branch, so an
    over-unity fraction closes the position's size and no more — it can never realize
    PnL on quantity the position does not hold. Recorded because the guard is a `>=`
    comparison rather than a clamp, and that is easy to weaken by accident."""
    led = _ledger()
    pos = _position()

    is_full = _close(led, pos, _costs(), exit_price_raw="110", fraction="1.5")

    assert is_full is True
    assert led.trades[0].pnl == Decimal("100.00")  # on size 10, not 15
    assert led.trades[0].exit_reason == "signal_exit"


def test_close_position_books_a_zero_fraction_as_an_empty_partial_lot() -> None:
    """LOCKED AS FOUND, NOT ENDORSED: a zero fraction still books a 0.00 trade row, an
    equity point and an event, and still bumps ``partial_closes`` — while leaving the
    position untouched. The engine never calls it this way (a close percentage of 0 is
    rejected upstream), so this pins the boundary rather than blessing it. Changing it
    would move engine output and needs an ENGINE_VERSION bump."""
    led = _ledger()
    pos = _position()

    is_full = _close(led, pos, _costs(commission="2"), exit_price_raw="110", fraction="0")

    assert is_full is False
    # Per-FILL (GH #552): the empty lot is still a fill and still pays its commission,
    # where the pro-rated model charged 2*2*0 = 0.00. The boundary is unchanged in shape —
    # a 0-size lot still books a row, an equity point and an event — only its fee moved.
    assert led.trades[0].pnl == Decimal("-2.00")
    assert led.partial_closes == 1
    assert pos.size == Decimal("10")


# --------------------------------------------------------------------------- #
# absorb_remainder                                                             #
# --------------------------------------------------------------------------- #
def test_absorb_remainder_averages_the_basis_by_size() -> None:
    """10 @100 topped up with 5 @130 -> 15 @110.00, notional 1650.00.

    A simple mean of the two prices would give 115.00; the weighting is what keeps the
    basis honest when the lots differ in size.
    """
    led = _ledger()
    pos = _position()

    absorb_remainder(
        led,
        pos,
        _costs(),
        bar=_bar(),
        price_raw=Decimal("130"),
        add_size=Decimal("5"),
        action="market_remainder",
        bar_seq=_EXIT_BAR_SEQ,
        partial_policy="fill_remainder_next_bar",
    )

    assert pos.entry_price == Decimal("110.00")
    assert pos.size == Decimal("15")
    assert pos.entry_notional == Decimal("1650.00")
    assert led.partial_fills == 1


def test_absorb_remainder_fills_a_short_top_up_on_the_adverse_side() -> None:
    """A short's top-up is a SELL: (130 - 1) * 0.99 = 127.71, basis 109.24."""
    led = _ledger()
    pos = _position(direction="short")

    absorb_remainder(
        led,
        pos,
        _costs(half_spread="1", slippage="0.01"),
        bar=_bar(),
        price_raw=Decimal("130"),
        add_size=Decimal("5"),
        action="market_remainder",
        bar_seq=_EXIT_BAR_SEQ,
        partial_policy="fill_remainder_next_bar",
    )

    assert led.signal_events[0].detail["fill_price"] == "127.71"
    assert pos.entry_price == Decimal("109.24")
    assert pos.entry_notional == Decimal("1638.60")


def test_absorb_remainder_charges_one_commission_for_the_extra_fill() -> None:
    """An added lot is ONE fill, so it pays one commission — never a round trip."""
    led = _ledger()

    absorb_remainder(
        led,
        _position(),
        _costs(commission="3"),
        bar=_bar(),
        price_raw=Decimal("130"),
        add_size=Decimal("5"),
        action="market_remainder",
        bar_seq=_EXIT_BAR_SEQ,
        partial_policy="fill_remainder_next_bar",
    )

    assert led.equity == Decimal("9997.00")


def test_absorb_remainder_leaves_equity_untouched_when_there_is_no_commission() -> None:
    led = _ledger()

    absorb_remainder(
        led,
        _position(),
        _costs(),
        bar=_bar(),
        price_raw=Decimal("130"),
        add_size=Decimal("5"),
        action="market_remainder",
        bar_seq=_EXIT_BAR_SEQ,
        partial_policy="fill_remainder_next_bar",
    )

    assert led.equity == _START_EQUITY


def test_absorb_remainder_keeps_the_stop_levels_installed_at_the_initial_entry() -> None:
    """The documented fixed-for-life invariant: adding size never re-anchors a stop."""
    led = _ledger()
    pos = _position()

    absorb_remainder(
        led,
        pos,
        _costs(),
        bar=_bar(),
        price_raw=Decimal("130"),
        add_size=Decimal("5"),
        action="market_remainder",
        bar_seq=_EXIT_BAR_SEQ,
        partial_policy="fill_remainder_next_bar",
    )

    assert pos.pct_stop == Decimal("95")
    assert pos.abs_stop == Decimal("94")
    assert pos.trail_pct == Decimal("2")
    assert pos.trail_anchor == Decimal("100")


def test_absorb_remainder_ratchets_the_peak_notional_and_never_lowers_it() -> None:
    """The peak is a high-water mark: a top-up landing below it must not erase it."""
    led = _ledger()
    pos = _position(peak_notional="2000.00")

    absorb_remainder(
        led,
        pos,
        _costs(),
        bar=_bar(),
        price_raw=Decimal("130"),
        add_size=Decimal("5"),
        action="market_remainder",
        bar_seq=_EXIT_BAR_SEQ,
        partial_policy="fill_remainder_next_bar",
    )

    assert pos.entry_notional == Decimal("1650.00")
    assert pos.peak_notional == Decimal("2000.00")


def test_absorb_remainder_emits_a_partial_fill_event_timed_to_the_filling_bar() -> None:
    """The event is stamped with the BAR's timestamp, not the original order's."""
    led = _ledger()
    pos = _position()

    absorb_remainder(
        led,
        pos,
        _costs(),
        bar=_bar(timestamp="2024-01-01T04:00:00Z"),
        price_raw=Decimal("130"),
        add_size=Decimal("5"),
        action="market_remainder",
        bar_seq=_EXIT_BAR_SEQ,
        partial_policy="fill_remainder_next_bar",
    )

    event = led.signal_events[0]
    assert event.event_type == "partial_fill"
    assert event.event_time == "2024-01-01T04:00:00Z"
    assert event.direction == "long"
    assert event.detail == {
        "bar_seq": _EXIT_BAR_SEQ,
        "position_seq": 1,
        "policy": "fill_remainder_next_bar",
        "action": "market_remainder",
        "fill_price": "130.00",
        "fill_size": "5",
        "new_size": "15",
        "entry_basis": "110.00",
    }
