"""Oracle — WHEN a fill happens and at WHICH price (ADIM 12).

Canonical rule under test (doc 02 "Entry/Exit Execution", Master Ref §6.1): an indicator
signal is confirmed at a bar's CLOSE. ``current_candle_close`` / ``market_fill_simulation``
therefore fill at that same close; ``next_candle_open`` / ``next_candle_close`` defer the
fill to the following bar's open / close. Nothing may fill EARLIER in the signal bar than
the close that produced the signal — that would be look-ahead.

Shared geometry: 20 flat bars at 100 (so the 20-bar SMA sits at 100), then bar 21 crosses.
Costs are zero throughout this module, so ``effective fill == raw price`` and the arithmetic
is visible: pnl = (exit - entry) * size, size = 50.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from entropia.domain.strategy.config import StrategyConfig
from tests.unit.oracles.harness import (
    SIGNAL_BAR_SEQ,
    bar,
    bar_time,
    entry_and_exit_plan,
    flat_run,
    oracle_config,
    run_oracle,
)

SIZE = Decimal("50")

# bar 21 closes at 102 > SMA(20 x 100) = 100 -> a LONG cross at that bar's close.
_UP_CROSS = bar(21, "100", "102", "100", "102")
# bar 21 closes at 98 < 100 -> a SHORT cross.
_DOWN_CROSS = bar(21, "100", "100", "98", "98")


def _long_cfg(**kwargs: Any) -> StrategyConfig:
    return oracle_config(direction="long", protection={}, **kwargs)


# --------------------------------------------------------------------------- #
# Immediate (signal-bar close) fills                                           #
# --------------------------------------------------------------------------- #
def test_current_candle_close_fills_a_long_at_the_signal_bar_close() -> None:
    """Entry = bar 21 close = 102. Exit = end of data at bar 22 close = 104.
    pnl = (104 - 102) * 50 = 100.00; equity = 10000 + 100 = 10100.00."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "102", "104", "102", "104")]
    out = run_oracle(_long_cfg(), bars)

    trade = out.trades[0]
    assert (trade.direction, trade.entry_price, trade.exit_price) == (
        "long",
        Decimal("102.00"),
        Decimal("104.00"),
    )
    assert trade.entry_time == bar_time(21) and trade.exit_time == bar_time(22)
    assert trade.pnl == Decimal("100.00")
    assert out.summary["final_equity"] == Decimal("10100.00")


def test_market_fill_simulation_is_the_same_fill_as_current_candle_close() -> None:
    """Doc 02 calls it a "simplified virtual fill"; a backtest fill IS that virtual fill,
    so the price must be identical — 102 in and 104 out, pnl 100.00."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "102", "104", "102", "104")]
    out = run_oracle(_long_cfg(entry_timing="market_fill_simulation"), bars)

    assert out.trades[0].entry_price == Decimal("102.00")
    assert out.trades[0].pnl == Decimal("100.00")


def test_current_candle_close_fills_a_short_at_the_signal_bar_close() -> None:
    """Short entry = 98, exit = 96. A short earns when price falls:
    pnl = (96 - 98) * 50 * (-1) = +100.00."""
    bars = [*flat_run(), _DOWN_CROSS, bar(22, "98", "98", "96", "96")]
    out = run_oracle(oracle_config(direction="short", protection={}), bars)

    trade = out.trades[0]
    assert trade.direction == "short"
    assert (trade.entry_price, trade.exit_price) == (Decimal("98.00"), Decimal("96.00"))
    assert trade.pnl == Decimal("100.00")


# --------------------------------------------------------------------------- #
# Deferred fills                                                               #
# --------------------------------------------------------------------------- #
def test_next_candle_open_fills_at_the_following_bar_open() -> None:
    """Signal at bar 21's close, fill at bar 22's OPEN = 103 (not bar 21's 102).
    Exit = end of data at bar 23 close = 106. pnl = (106 - 103) * 50 = 150.00."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "103", "104", "103", "104"),
        bar(23, "104", "106", "104", "106"),
    ]
    out = run_oracle(_long_cfg(entry_timing="next_candle_open"), bars)

    trade = out.trades[0]
    assert trade.entry_price == Decimal("103.00")
    assert trade.entry_time == bar_time(22)  # the FILL bar, not the signal bar
    assert trade.pnl == Decimal("150.00")


def test_next_candle_close_fills_at_the_following_bar_close() -> None:
    """Same signal, fill at bar 22's CLOSE = 104. pnl = (106 - 104) * 50 = 100.00."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "103", "104", "103", "104"),
        bar(23, "104", "106", "104", "106"),
    ]
    out = run_oracle(_long_cfg(entry_timing="next_candle_close"), bars)

    assert out.trades[0].entry_price == Decimal("104.00")
    assert out.trades[0].entry_time == bar_time(22)
    assert out.trades[0].pnl == Decimal("100.00")


def test_a_deferred_entry_takes_the_gapped_open_it_cannot_have_foreseen() -> None:
    """NO-LOOKAHEAD. Bar 22 gaps UP to 108 — a fill that had peeked at bar 22 would have
    preferred bar 21's 102. The engine pays the gap: entry = 108.00, and the round trip
    to bar 23's close of 109 earns only (109 - 108) * 50 = 50.00."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "108", "109", "108", "109"),
        bar(23, "109", "109", "109", "109"),
    ]
    out = run_oracle(_long_cfg(entry_timing="next_candle_open"), bars)

    assert out.trades[0].entry_price == Decimal("108.00")
    assert out.trades[0].pnl == Decimal("50.00")


# --------------------------------------------------------------------------- #
# Exit timing                                                                  #
# --------------------------------------------------------------------------- #
def test_an_exit_signal_closes_at_the_signal_bar_close_under_immediate_timing() -> None:
    """``exit_first`` admits the flat-position entry on bar 21; bar 22 crosses back down
    and closes the long at that bar's close = 99. pnl = (99 - 102) * 50 = -150.00."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "102", "102", "99", "99"),
        bar(23, "98", "98", "98", "98"),
    ]
    out = run_oracle(
        _long_cfg(conflict={"same_candle_entry_exit": "exit_first"}),
        bars,
        plan=entry_and_exit_plan(),
    )

    trade = out.trades[0]
    assert trade.exit_reason == "exit_signal"
    assert trade.exit_price == Decimal("99.00")
    assert trade.exit_time == bar_time(22)
    assert trade.pnl == Decimal("-150.00")


def test_a_flat_position_entry_and_exit_on_one_bar_resolves_to_no_entry() -> None:
    """§5.9 Same Candle Entry/Exit. Both decisions are close-confirmed, so OHLCV carries no
    ordering to separate them; the default ``use_intrabar_data_if_available`` refuses to
    invent one and opens NOTHING — the collision is traced, the ledger stays empty."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "102", "102", "99", "99"),
        bar(23, "98", "98", "98", "98"),
    ]
    out = run_oracle(_long_cfg(), bars, plan=entry_and_exit_plan())

    assert out.trades == []
    assert out.summary["final_equity"] == Decimal("10000.00")
    assert "entry_exit_collision" in {event.event_type for event in out.signal_events}


def test_an_open_position_is_closed_at_the_last_bar_close_when_data_runs_out() -> None:
    """No stop, no exit signal: the position is marked out at the final bar's close = 107.
    pnl = (107 - 102) * 50 = 250.00, reason ``end_of_data`` — never left silently open."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "102", "105", "102", "105"),
        bar(23, "105", "107", "105", "107"),
    ]
    out = run_oracle(_long_cfg(), bars)

    trade = out.trades[0]
    assert trade.exit_reason == "end_of_data"
    assert trade.exit_price == Decimal("107.00")
    assert trade.pnl == Decimal("250.00")


def test_the_signal_is_dated_to_the_cross_bar() -> None:
    """The 20-bar SMA over 20 identical closes IS the flat price, so the cross can only be
    bar 21 — the fixture geometry every other oracle in this package depends on."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "102", "104", "102", "104")]
    out = run_oracle(_long_cfg(), bars)

    signal = next(e for e in out.signal_events if e.event_type == "entry_signal")
    assert signal.detail["bar_seq"] == SIGNAL_BAR_SEQ == 21
