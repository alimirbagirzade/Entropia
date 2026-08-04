"""Oracle — partial close, its aftermath, and the same-direction scaling ladder (ADIM 12).

Canonical rules under test (doc 02 §5.3/§5.7, Master Ref §8 / §11.1-§11.4):

* a partial close realizes ``close_percentage`` of the CURRENT quantity as its own lot and
  leaves the rest open; the aftermath then governs the remainder (move stop to entry /
  lock in profit / close all);
* the price-distance ladder proposes ONE layer per threshold crossing, sized off the
  configured basis, and an over-cap layer is REJECTED outright — never trimmed to fit
  (Master Ref §11.4: a layer over the exposure limit is never auto-trimmed open);
* the position's entry basis after a layer is the size-weighted average of its fills
  (Master Ref §7.1 ``entry_vwap``).

Geometry: long in at 102 on bar 21; ``exit_first`` admits the entry on the same bar the
exit rule also fires, so the partial-close fixtures have a real exit signal to work with.
Zero costs unless a test says otherwise.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.engine import EngineOutput
from tests.unit.oracles.harness import (
    bar,
    entry_and_exit_plan,
    flat_run,
    oracle_config,
    run_oracle,
)

_UP_CROSS = bar(21, "100", "102", "100", "102")

# bar 22 crosses back below the MA (exit signal at close 99); bar 23 recovers to 104.
_PARTIAL_BARS = [
    *flat_run(),
    _UP_CROSS,
    bar(22, "102", "102", "99", "99"),
    # Bar 23 OPENS at 103, above every stop level these fixtures install, and dips to 99.
    # That is deliberate: it keeps these tests about the AFTERMATH rules. An open BELOW the
    # remainder's stop would let the gap rule (#549) decide the exit instead — a different
    # property, tested on its own in ``test_a_remainder_stop_obeys_the_gap_rule_too``.
    bar(23, "103", "104", "99", "104"),
]
# bar 22 retraces 1% below the 102 entry without crossing the MA (no exit signal);
# bar 23 recovers to 104.
_SCALE_BARS = [
    *flat_run(),
    _UP_CROSS,
    bar(22, "102", "102", "100.90", "100.90"),
    bar(23, "101", "104", "101", "104"),
]
_HOLD_THROUGH_OPPOSITE = {"exit_on_opposite_signal": False, "opposite_direction_hedge": "ignore"}


def _partial(
    aftermath: str, *, costs: dict[str, str] | None = None, close_pct: str = "40"
) -> EngineOutput:
    return run_oracle(
        oracle_config(
            direction="long",
            protection={},
            costs=costs,
            conflict={"same_candle_entry_exit": "exit_first"},
            exit_logic={
                "applies_to_direction": "long_and_short",
                "close_percentage": close_pct,
                "partial_aftermath": aftermath,
            },
        ),
        _PARTIAL_BARS,
        plan=entry_and_exit_plan(),
    )


def _scaled(scaling: dict[str, object]) -> EngineOutput:
    return run_oracle(
        oracle_config(
            direction="long", protection={}, conflict=_HOLD_THROUGH_OPPOSITE, scaling=scaling
        ),
        _SCALE_BARS,
    )


_LADDER = {
    "enabled": True,
    "method": "price_distance_scaling",
    "price_scaling": {"retracement_distance": "1", "layers": 2},
    "add_size": "percent_of_initial",
    "add_size_value": "50",
}


# --------------------------------------------------------------------------- #
# Partial close                                                                #
# --------------------------------------------------------------------------- #
def test_a_partial_close_realizes_its_fraction_and_holds_the_rest() -> None:
    """40% of 50 units = 20 units realized at bar 22's close of 99:
    lot pnl = (99 - 102) * 20 = -60.00, reason ``partial_exit``, 30 units left open.
    The aftermath moves the remainder's stop to the entry basis 102, so bar 23's low of 99
    stops it out AT 102 for exactly 0.00. Run total = -60.00."""
    out = _partial("move_stop_to_entry")

    first, second = out.trades
    assert (first.exit_reason, first.exit_price, first.pnl) == (
        "partial_exit",
        Decimal("99.00"),
        Decimal("-60.00"),
    )
    assert (second.exit_reason, second.exit_price, second.pnl) == (
        "stop_loss",
        Decimal("102.00"),
        Decimal("0.00"),
    )
    assert out.summary["final_equity"] == Decimal("9940.00")


def test_lock_in_profit_ratchets_the_remainder_stop_to_the_achieved_price() -> None:
    """Same 20-unit lot at -60.00, but the aftermath pins the remainder's stop to the price
    just achieved (99). Bar 23's low of 99 touches it: (99 - 102) * 30 = -90.00.
    Run total = -150.00 — the same money as closing 100% at 99, reached down a different
    path, which is what makes the two aftermaths distinguishable."""
    out = _partial("lock_in_profit")

    assert [t.pnl for t in out.trades] == [Decimal("-60.00"), Decimal("-90.00")]
    assert out.summary["final_equity"] == Decimal("9850.00")


def test_close_all_collapses_the_partial_into_a_full_exit() -> None:
    """``close_all`` ignores the 40% and closes 100% on the signal:
    one lot, (99 - 102) * 50 = -150.00, reason ``exit_signal`` (not ``partial_exit``).
    Bar 23 then crosses back up and opens a fresh long at 104 that ends flat at 104."""
    out = _partial("close_all")

    assert out.trades[0].exit_reason == "exit_signal"
    assert out.trades[0].pnl == Decimal("-150.00")
    assert out.trades[1].entry_price == Decimal("104.00")


def test_a_partial_lot_pays_commission_in_proportion_but_the_final_close_pays_a_full_one() -> None:
    """Commission 7 per fill, so a round trip is 14.00.

    The 40% lot is charged 14.00 * 0.4 = 5.60 -> pnl = -60.00 - 5.60 = -65.60.
    The remainder's close is a FULL close and is charged a whole 14.00 -> pnl = -14.00
    (it exits at the breakeven stop, so the fee is the entire result).
    Run total = -79.60.

    DIVERGENCE, pinned deliberately: this position had ONE entry fill and TWO exit fills,
    yet is charged 1.4 round trips (19.60) — neither three per-fill commissions (21.00) nor
    the single round trip the booking layer documents as its invariant. Filed as issue #552."""
    out = _partial(
        "move_stop_to_entry",
        costs={"slippage_mode": "percentage_slippage", "slippage_value": "0", "commission": "7"},
    )

    assert [t.pnl for t in out.trades] == [Decimal("-65.60"), Decimal("-14.00")]
    assert out.summary["final_equity"] == Decimal("9920.40")


def test_a_remainder_stop_obeys_the_gap_rule_too() -> None:
    """#549 reaches the aftermath, not only the originally-installed stops.

    Same 40% partial at 99 (-60.00), same ``move_stop_to_entry`` breakeven stop at 102 —
    but bar 23 now OPENS at 95, already below it. The remainder cannot wait for a rally
    back to 102: it exits at min(102, 95) = 95.
    (95 - 102) * 30 = -210.00, run total -270.00.

    This is the widest reading of the defect and the reason it is worth more than the word
    "gap" suggests: the level does not need to be outside the bar's RANGE (bar 23 trades up
    to 104, through 102). It only needs to be beyond the bar's OPEN."""
    out = run_oracle(
        oracle_config(
            direction="long",
            protection={},
            conflict={"same_candle_entry_exit": "exit_first"},
            exit_logic={
                "applies_to_direction": "long_and_short",
                "close_percentage": "40",
                "partial_aftermath": "move_stop_to_entry",
            },
        ),
        [
            *flat_run(),
            _UP_CROSS,
            bar(22, "102", "102", "99", "99"),
            bar(23, "95", "104", "95", "104"),
        ],
        plan=entry_and_exit_plan(),
    )

    assert [t.pnl for t in out.trades] == [Decimal("-60.00"), Decimal("-210.00")]
    assert out.trades[1].exit_price == Decimal("95.00")
    assert out.summary["final_equity"] == Decimal("9730.00")
    assert out.diagnostics["gap_adjusted_stops"] == 1


# --------------------------------------------------------------------------- #
# Same-direction scaling ladder                                                #
# --------------------------------------------------------------------------- #
def test_a_layer_is_added_at_the_threshold_and_rebases_the_average_entry() -> None:
    """Threshold = 1% adverse from the 102 reference = 102 * 0.99 = 100.98. Bar 22 closes
    at 100.90, below it, so ONE layer fires at that close.

    layer size = 50% of the initial 50 units = 25 units at 100.90
    new size   = 50 + 25 = 75
    new basis  = (102 * 50 + 100.90 * 25) / 75 = 7622.50 / 75 = 101.63333... -> 101.63
    pnl        = (104 - 101.63) * 75 = 177.75"""
    out = _scaled(_LADDER)

    trade = out.trades[0]
    assert trade.entry_price == Decimal("101.63")
    assert trade.pnl == Decimal("177.75")
    layer = next(e for e in out.signal_events if e.event_type == "scale_layer_added")
    assert layer.detail["fill_price"] == "100.90"
    assert Decimal(str(layer.detail["new_size"])) == Decimal("75")


def test_a_fixed_amount_layer_uses_the_configured_quantity_verbatim() -> None:
    """10 units at 100.90 -> size 60, basis = (5100 + 1009) / 60 = 6109 / 60
    = 101.81666... -> 101.82. pnl = (104 - 101.82) * 60 = 130.80."""
    out = _scaled({**_LADDER, "add_size": "fixed_amount", "add_size_value": "10"})

    assert out.trades[0].entry_price == Decimal("101.82")
    assert out.trades[0].pnl == Decimal("130.80")


def test_an_over_cap_layer_is_rejected_whole_and_never_trimmed_to_fit() -> None:
    """The candidate would take the position to 75 units against a 60-unit total cap.
    Master Ref §11.4 forbids trimming, so NOTHING is added: the position stays 50 units at
    102 and pnl is the unscaled (104 - 102) * 50 = 100.00. A trim-to-fit engine would have
    booked 10 extra units here."""
    out = _scaled({**_LADDER, "scaling_limits": {"max_total_position_size": "60"}})

    assert out.trades[0].entry_price == Decimal("102.00")
    assert out.trades[0].pnl == Decimal("100.00")
    rejection = next(e for e in out.signal_events if e.event_type == "scale_layer_rejected")
    assert rejection.detail["reason"] == "max_total_exposure"
    assert rejection.detail["cap"] == "60"


def test_a_disabled_ladder_changes_nothing() -> None:
    """``enabled: false`` with the whole subtree still populated must be inert — the
    unscaled 100.00, identical to having no scaling config at all."""
    disabled = _scaled({**_LADDER, "enabled": False})
    absent = run_oracle(
        oracle_config(direction="long", protection={}, conflict=_HOLD_THROUGH_OPPOSITE),
        _SCALE_BARS,
    )

    assert disabled.trades[0].pnl == Decimal("100.00")
    assert disabled.summary == absent.summary
