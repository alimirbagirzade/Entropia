"""Oracle — resting order types: limit, stop and stop-limit (ADIM 12).

Canonical rules under test (doc 02 §5.2.1 / §6.1, Master Ref §6.2-§6.3):

* a LIMIT entry does not fill at the decision bar (the signal is only known at that bar's
  close — a same-bar fill would look ahead). It rests from the NEXT bar and fills at its
  level only if a bar reaches it inside the validity window; otherwise the unfilled policy
  applies (cancel / keep / convert-to-market / re-price);
* a STOP entry rests a trigger and fills market-like once price reaches it;
* a STOP-LIMIT fires the trigger and only then arms the limit leg.

SPEC BOUNDARY, stated honestly: the master reference names these options but never fixes
the fill PRICE for any of them, and it is silent on what happens when a bar gaps THROUGH a
level (see docs/audit/backtest_oracle_fixtures.md §"Spec-open conventions"). These oracles
pin the SHIPPED convention — a touched limit fills at its own level, and a gapped stop
entry fills at ``max(trigger, open)`` for a long (the level no longer exists, so the open
is the first attainable price). They are a baseline, not a claim that the spec mandates it.

Zero costs throughout; size 50; the SMA cross fires on bar 21 at close 102.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import EngineOutput
from tests.unit.oracles.harness import bar, bar_time, flat_run, oracle_config, run_oracle

_UP_CROSS = bar(21, "100", "102", "100", "102")
_DOWN_CROSS = bar(21, "100", "100", "98", "98")


def _limit(**overrides: object) -> dict[str, object]:
    return {
        "type": "limit_order",
        "limit": {
            "price_rule": "entry_signal_price",
            "validity": "3_candles",
            "unfilled_policy": "cancel_order",
            "partial_fill_policy": "not_allowed",
            **overrides,
        },
    }


def _stop(**overrides: object) -> dict[str, object]:
    return {"type": "stop_order", "stop": {"activation_rule": "entry_signal_price", **overrides}}


def _run(
    order_config: dict[str, object],
    bars: list[dict[str, Any]],
    *,
    direction: str = "long",
) -> EngineOutput:
    return run_oracle(
        oracle_config(direction=direction, protection={}, order_config=order_config), bars
    )


# --------------------------------------------------------------------------- #
# Limit entries                                                                #
# --------------------------------------------------------------------------- #
def test_a_limit_rests_from_the_next_bar_and_fills_at_its_own_level() -> None:
    """Limit = signal price = 102, resting from bar 22. Bar 22's low of 101 reaches it, so
    the fill is 102.00 ON BAR 22 — not bar 21, where the order did not yet exist.
    Exit = end of data at 106. pnl = (106 - 102) * 50 = 200.00."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "103", "104", "101", "104"),
        bar(23, "104", "106", "104", "106"),
    ]
    out = _run(_limit(), bars)

    trade = out.trades[0]
    assert trade.entry_price == Decimal("102.00")
    assert trade.entry_time == bar_time(22)
    assert trade.pnl == Decimal("200.00")


def test_an_untouched_limit_never_becomes_a_position() -> None:
    """Bar 22's low is 103 and bar 23's is 104 — the 102 limit is never reached, so the
    order is cancelled and the ledger stays empty. A no-fill is traced, never silent."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "103", "104", "103", "104"),
        bar(23, "104", "106", "104", "106"),
    ]
    out = _run(_limit(), bars)

    assert out.trades == []
    assert out.summary["final_equity"] == Decimal("10000.00")
    assert "limit_order_cancelled" in {e.event_type for e in out.signal_events}


def test_convert_to_market_fills_at_the_expiry_bar_close() -> None:
    """Same untouched geometry, but the order expires after 1 candle and converts:
    it fills at bar 22's CLOSE of 104 — the worse price, which is the point of the policy.
    pnl = (106 - 104) * 50 = 100.00."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "103", "104", "103", "104"),
        bar(23, "104", "106", "104", "106"),
    ]
    out = _run(_limit(unfilled_policy="convert_to_market_order", validity="1_candle"), bars)

    trade = out.trades[0]
    assert (trade.entry_price, trade.entry_time) == (Decimal("104.00"), bar_time(22))
    assert trade.pnl == Decimal("100.00")


def test_a_minus_offset_moves_the_limit_below_the_signal_price() -> None:
    """102 - 2 = 100. Bar 22's low of 101 and bar 23's of 104 never reach it, so the
    stricter level is what keeps the run flat — the offset is real, not decorative."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "103", "104", "101", "104"),
        bar(23, "104", "106", "104", "106"),
    ]
    out = _run(_limit(price_rule="signal_price_minus_offset", price_offset="2"), bars)

    assert out.trades == []


def test_a_plus_offset_moves_the_limit_above_the_signal_price() -> None:
    """102 + 2 = 104 — an aggressive buy limit. Bar 22 trades down to 101, so the level is
    reached and the fill is the LIMIT price 104.00, not the bar's low.
    pnl = (106 - 104) * 50 = 100.00."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "103", "104", "101", "104"),
        bar(23, "104", "106", "104", "106"),
    ]
    out = _run(_limit(price_rule="signal_price_plus_offset", price_offset="2"), bars)

    assert out.trades[0].entry_price == Decimal("104.00")
    assert out.trades[0].pnl == Decimal("100.00")


# --------------------------------------------------------------------------- #
# Stop entries                                                                 #
# --------------------------------------------------------------------------- #
def test_a_stop_entry_fills_at_its_trigger_when_the_bar_opens_below_it() -> None:
    """Trigger = signal price = 102. Bar 22 opens at 101 and trades up to 103, so the
    trigger is reached inside the bar and the fill is max(102, open 101) = 102.00.
    pnl = (104 - 102) * 50 = 100.00."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "101", "103", "101", "103"),
        bar(23, "103", "104", "103", "104"),
    ]
    out = _run(_stop(), bars)

    trade = out.trades[0]
    assert (trade.entry_price, trade.entry_time) == (Decimal("102.00"), bar_time(22))
    assert trade.pnl == Decimal("100.00")


def test_a_stop_entry_gapped_through_pays_the_open_not_the_trigger() -> None:
    """Bar 22 GAPS to an open of 105, past the 102 trigger. 102 never existed on that bar,
    so the fill is max(102, 105) = 105.00 — the first attainable price.
    pnl = (107 - 105) * 50 = 100.00. Booking 102 here would fabricate 150.00 of profit
    out of a price the market never printed."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "105", "106", "105", "106"),
        bar(23, "106", "107", "106", "107"),
    ]
    out = _run(_stop(), bars)

    assert out.trades[0].entry_price == Decimal("105.00")
    assert out.trades[0].pnl == Decimal("100.00")


def test_a_short_stop_entry_mirrors_the_gap_rule() -> None:
    """Short trigger = 98; bar 22 gaps DOWN to an open of 95. Fill = min(98, 95) = 95.00.
    pnl = (93 - 95) * 50 * (-1) = 100.00."""
    bars = [
        *flat_run(),
        _DOWN_CROSS,
        bar(22, "95", "95", "94", "94"),
        bar(23, "94", "94", "93", "93"),
    ]
    out = _run(_stop(), bars, direction="short")

    assert out.trades[0].entry_price == Decimal("95.00")
    assert out.trades[0].pnl == Decimal("100.00")


def test_an_unfired_stop_trigger_opens_nothing() -> None:
    """Price never reaches 102 again after the signal bar: no trade, and the resting
    trigger is disposed of in the trace rather than quietly forgotten."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "101", "101.50", "100", "101"),
        bar(23, "101", "101.90", "100", "101"),
    ]
    out = _run(_stop(), bars)

    assert out.trades == []
    assert "stop_order_placed" in {e.event_type for e in out.signal_events}


def test_a_stop_trigger_offset_shifts_the_activation_level() -> None:
    """``signal_price_plus_offset`` with offset 3 puts the trigger at 105. Bar 22 tops out
    at 104 — below it — so nothing fires; bar 23 reaches 106 and fills at max(105, open
    104) = 105.00. pnl = (106 - 105) * 50 = 50.00."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "102", "104", "102", "104"),
        bar(23, "104", "106", "104", "106"),
    ]
    out = _run(_stop(activation_rule="signal_price_plus_offset", trigger_offset="3"), bars)

    trade = out.trades[0]
    assert (trade.entry_price, trade.entry_time) == (Decimal("105.00"), bar_time(23))
    assert trade.pnl == Decimal("50.00")
