"""Oracle — protection stops and same-bar stop conflicts (ADIM 12).

Canonical rules under test (doc 02 §5.5/§5.6/§5.9, Master Ref §9.1-§9.3):

* PERCENTAGE stop level = ``entry * (1 - d/100)`` long, mirrored short (Master Ref §9.2;
  doc 02's worked example: long from 100 with 1.00% stops at 99);
* ABSOLUTE stop is the configured price verbatim;
* TRAILING stop activates once profit reaches "Activate After Profit %" and then rests at
  ``favourable_extreme * (1 - t/100)`` — off the running extreme, never off entry (doc 02's
  worked example: 100 in, activate 2%, trail 0.8%, extreme 105 -> 104.16);
* ``stop_trigger_requirement`` decides WHETHER protection fires (any / all enabled rules);
* ``stop_conflict_resolution`` decides WHICH triggered rule executes.

SPEC BOUNDARY: the master reference is SILENT on the EXECUTION price of a triggered stop —
it fixes the trigger level and says the ledger stores a ``trigger_price``, but never that
the fill equals it. The shipped engine executes at the level when the level was reachable,
and at the bar's OPEN when the bar opened already past it (#549): the level did not exist
during that bar, so booking it would credit a price the market never printed. That is the
same ``max(trigger, open)`` rule the engine applies to a gapped stop ENTRY — one rule, two
signs — rather than a reading invented where canon is silent.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import EngineOutput
from tests.unit.oracles.harness import (
    bar,
    entry_and_exit_plan,
    flat_run,
    oracle_config,
    run_oracle,
)

_UP_CROSS = bar(21, "100", "102", "100", "102")
_DOWN_CROSS = bar(21, "100", "100", "98", "98")
_PCT_1 = {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}}


def _run(
    protection: dict[str, Any],
    bars: list[dict[str, Any]],
    *,
    direction: str = "long",
    **kwargs: Any,
) -> EngineOutput:
    return run_oracle(oracle_config(direction=direction, protection=protection, **kwargs), bars)


# --------------------------------------------------------------------------- #
# Level arithmetic                                                             #
# --------------------------------------------------------------------------- #
def test_a_percentage_stop_executes_at_its_level_not_at_the_bar_low() -> None:
    """Entry 102, 1% -> level 102 * 0.99 = 100.98. Bar 22 trades down to 90, but the fill
    is the LEVEL: pnl = (100.98 - 102) * 50 = -51.00. Filling at the bar's low would
    report -600.00 for a stop that was reachable at 100.98 on the way down."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "102", "102", "90", "95")]
    trade = _run(_PCT_1, bars).trades[0]

    assert trade.exit_reason == "stop_loss"
    assert trade.exit_price == Decimal("100.98")
    assert trade.pnl == Decimal("-51.00")


def test_a_short_percentage_stop_mirrors_the_sign() -> None:
    """Entry 98, 1% -> level 98 * 1.01 = 98.98. Bar 22's high of 102 reaches it.
    pnl = (98.98 - 98) * 50 * (-1) = -49.00."""
    bars = [*flat_run(), _DOWN_CROSS, bar(22, "98", "102", "98", "101")]
    trade = _run(_PCT_1, bars, direction="short").trades[0]

    assert trade.exit_price == Decimal("98.98")
    assert trade.pnl == Decimal("-49.00")


def test_an_absolute_stop_is_the_configured_price_verbatim() -> None:
    """Level 101 regardless of entry. pnl = (101 - 102) * 50 = -50.00."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "102", "102", "100", "100.50")]
    protection = {"absolute_stop": {"enabled": True, "absolute_price": "101"}}
    trade = _run(protection, bars).trades[0]

    assert trade.exit_price == Decimal("101.00")
    assert trade.pnl == Decimal("-50.00")


def test_a_trailing_stop_rests_below_the_running_extreme_once_activated() -> None:
    """Entry 102, activate after 0.8% -> 102 * 1.008 = 102.816; bar 22's high of 106 clears
    it, so the trail is live at 106 * 0.98 = 103.88. Bar 22's low of 104 is above it (no
    exit); bar 23 dips to 103 and the stop fills at 103.88.
    pnl = (103.88 - 102) * 50 = 94.00 — a PROFITABLE stop, which is what a trail is for."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "102", "106", "104", "105"),
        bar(23, "105", "105", "103", "103"),
    ]
    protection = {
        "trailing_stop": {"enabled": True, "trail_percentage": "2.0", "lock_in_percentage": "0.8"}
    }
    trade = _run(protection, bars).trades[0]

    assert trade.exit_price == Decimal("103.88")
    assert trade.pnl == Decimal("94.00")


def test_an_unactivated_trailing_stop_contributes_no_level_at_all() -> None:
    """Activation needs 102 * 1.05 = 107.10; the high is only 102.50. With no other rule
    enabled the position is unprotected and runs to the end of data at 100.50.
    pnl = (100.50 - 102) * 50 = -75.00 — the trail must not protect before it activates."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "102", "102.50", "100", "100.50")]
    protection = {
        "trailing_stop": {"enabled": True, "trail_percentage": "2.0", "lock_in_percentage": "5"}
    }
    trade = _run(protection, bars).trades[0]

    assert trade.exit_reason == "end_of_data"
    assert trade.pnl == Decimal("-75.00")


# --------------------------------------------------------------------------- #
# Multi-stop combination                                                       #
# --------------------------------------------------------------------------- #
_TWO_STOPS = {
    "percentage_stop": {"enabled": True, "loss_percentage": "1.0"},  # level 100.98
    "absolute_stop": {"enabled": True, "absolute_price": "101.50"},
}
_BOTH_TRIGGER = [*flat_run(), _UP_CROSS, bar(22, "102", "102", "100", "100.50")]


def test_most_conservative_picks_the_level_closest_to_entry() -> None:
    """Both fire on bar 22 (low 100 <= 100.98 and <= 101.50). "Leaves least risk" = the
    tightest adverse distance: |102 - 101.50| = 0.50 beats |102 - 100.98| = 1.02, so the
    ABSOLUTE stop executes. pnl = (101.50 - 102) * 50 = -25.00."""
    trade = _run({**_TWO_STOPS, "stop_conflict_resolution": "most_conservative"}, _BOTH_TRIGGER)

    assert trade.trades[0].exit_price == Decimal("101.50")
    assert trade.trades[0].pnl == Decimal("-25.00")


def test_priority_order_picks_by_rank_and_ignores_the_distance() -> None:
    """Same bar, same two levels, different resolver: with no explicit order the shipped
    ranking is percentage -> trailing -> absolute, so the PERCENTAGE stop executes at
    100.98 even though it is the looser level. pnl = -51.00.

    SPEC BOUNDARY: no canonical stop precedence exists in the master reference —
    ``priority_order`` is defined there as a USER-supplied ordered list of rule ids. The
    default ranking asserted here is a shipped convention."""
    trade = _run({**_TWO_STOPS, "stop_conflict_resolution": "priority_order"}, _BOTH_TRIGGER)

    assert trade.trades[0].exit_price == Decimal("100.98")
    assert trade.trades[0].pnl == Decimal("-51.00")


def test_an_explicit_priority_order_overrides_the_default_ranking() -> None:
    """Listing ``absolute`` first flips the winner back to 101.50 / -25.00 — proof the
    configured order is read, not merely accepted."""
    protection = {
        **_TWO_STOPS,
        "stop_conflict_resolution": "priority_order",
        "stop_priority_order": ["absolute", "percentage"],
    }
    trade = _run(protection, _BOTH_TRIGGER).trades[0]

    assert trade.exit_price == Decimal("101.50")


def test_all_active_refuses_to_fire_when_only_one_rule_triggers() -> None:
    """Bar 22's low is 101.20: the absolute stop at 101.50 is touched, the percentage stop
    at 100.98 is not. ``all_active`` requires EVERY enabled rule, so protection does not
    fire and the position rides to the end of data at 101.30.
    pnl = (101.30 - 102) * 50 = -35.00, reason ``end_of_data`` — not a stop."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "102", "102", "101.20", "101.30")]
    trade = _run({**_TWO_STOPS, "stop_trigger_requirement": "all_active"}, bars).trades[0]

    assert trade.exit_reason == "end_of_data"
    assert trade.pnl == Decimal("-35.00")


# --------------------------------------------------------------------------- #
# Stop + exit-signal collision (§5.9)                                          #
# --------------------------------------------------------------------------- #
_COLLISION_BARS = [
    *flat_run(),
    _UP_CROSS,
    bar(22, "102", "102", "99", "99"),  # low 99 trips the stop AND closes below the MA
    bar(23, "98", "98", "98", "98"),
]


def _collision(policy: str) -> EngineOutput:
    return run_oracle(
        oracle_config(
            direction="long",
            protection=_PCT_1,
            conflict={"same_candle_entry_exit": "exit_first", "stop_exit_conflict": policy},
        ),
        _COLLISION_BARS,
        plan=entry_and_exit_plan(),
    )


def test_stop_has_priority_closes_at_the_stop_level() -> None:
    """The V18 default. Both fire on bar 22; the close is booked as the stop:
    exit 100.98, pnl = -51.00, reason ``stop_loss``."""
    trade = _collision("stop_has_priority").trades[0]

    assert (trade.exit_reason, trade.exit_price, trade.pnl) == (
        "stop_loss",
        Decimal("100.98"),
        Decimal("-51.00"),
    )


def test_exit_has_priority_closes_at_the_bar_close_instead() -> None:
    """The one policy that changes the OUTCOME rather than the label: the exit signal wins
    and fills at bar 22's close of 99. pnl = (99 - 102) * 50 = -150.00 — a 99.00 worse
    result than the stop-priority reading of the same bar."""
    trade = _collision("exit_has_priority").trades[0]

    assert (trade.exit_reason, trade.exit_price, trade.pnl) == (
        "exit_signal",
        Decimal("99.00"),
        Decimal("-150.00"),
    )


def test_record_both_reasons_still_executes_exactly_one_close() -> None:
    """Doc 02 §5.9: ONE close is executed, but the report keeps both reason codes. One trade at
    the stop level, and the collision is journalled."""
    out = _collision("record_both_reasons")

    assert len(out.trades) == 1
    assert out.trades[0].exit_price == Decimal("100.98")
    assert "stop_exit_collision" in {e.event_type for e in out.signal_events}


def test_first_trigger_wins_resolves_to_the_stop_over_plain_ohlcv() -> None:
    """The stop is an intrabar touch and the exit signal is close-confirmed, so OHLCV
    carries no ordering that could put the exit first. It resolves to the stop: -51.00."""
    trade = _collision("first_trigger_wins").trades[0]

    assert trade.exit_price == Decimal("100.98")


# --------------------------------------------------------------------------- #
# Gapped stops (#549)                                                          #
# --------------------------------------------------------------------------- #
def test_a_stop_gapped_through_at_the_open_fills_at_the_open() -> None:
    """Long from 102 with a 1% stop at 100.98. Bar 22 GAPS: it opens at 90 and its entire
    range is 88-92, so 100.98 does not exist anywhere on that bar.

    The first attainable price is the OPEN, 90 — the same rule the engine applies to a
    gapped stop ENTRY (``max(trigger, open)``; see
    ``test_a_stop_entry_gapped_through_pays_the_open_not_the_trigger``).

        pnl = (90 - 102) * 50 = -600.00

    Booking the untouchable 100.98 would report -51.00 — 549.00 of loss the market never
    gave back, on this bar and on every other gapped stop-out."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "90", "92", "88", "91")]
    trade = _run(_PCT_1, bars).trades[0]

    assert trade.exit_price == Decimal("90.00")
    assert trade.pnl == Decimal("-600.00")


def test_a_short_stop_gapped_through_mirrors_the_rule() -> None:
    """Short from 98, 1% stop at 98.98. Bar 22 opens at 110 (range 108-112), so 98.98 was
    never available: the buy-back fills at max(98.98, 110) = 110.00.
    pnl = (110 - 98) * 50 * (-1) = -600.00."""
    bars = [*flat_run(), _DOWN_CROSS, bar(22, "110", "112", "108", "111")]
    trade = _run(_PCT_1, bars, direction="short").trades[0]

    assert trade.exit_price == Decimal("110.00")
    assert trade.pnl == Decimal("-600.00")


def test_an_absolute_stop_gapped_through_fills_at_the_open_too() -> None:
    """The rule is a property of the BAR, not of which stop rule won: absolute stop at 101,
    bar 22 opens at 80 (range 78-82) -> fill 80.00, pnl = (80 - 102) * 50 = -1100.00."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "80", "82", "78", "81")]
    protection = {"absolute_stop": {"enabled": True, "absolute_price": "101"}}
    trade = _run(protection, bars).trades[0]

    assert trade.exit_price == Decimal("80.00")
    assert trade.pnl == Decimal("-1100.00")


def test_a_stop_touched_inside_the_bar_is_untouched_by_the_gap_rule() -> None:
    """The control that keeps the fix narrow. Bar 22 OPENS at 102, above the 100.98 level,
    and trades down to 90: the level existed on the way down, so the fill is still the
    level. min(100.98, 102) = 100.98, pnl = -51.00 — unchanged from before #549."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "102", "102", "90", "95")]
    trade = _run(_PCT_1, bars).trades[0]

    assert trade.exit_price == Decimal("100.98")
    assert trade.pnl == Decimal("-51.00")


def test_the_gap_clamp_does_not_change_which_rule_is_reported_as_executed() -> None:
    """Both stops (percentage 100.98, absolute 101.50) are gapped through by a bar opening
    at 90. The clamp is applied AFTER the winner is chosen, so ``most_conservative`` still
    picks the tightest LEVEL — absolute — and reports it, even though both would execute at
    the same 90.00. Clamping before the comparison would collapse the two distances to zero
    and hand the win to whichever key sorted first."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "90", "92", "88", "91")]
    out = _run({**_TWO_STOPS, "stop_conflict_resolution": "most_conservative"}, bars)

    resolution = next(e for e in out.signal_events if e.event_type == "stop_resolution")
    assert resolution.detail["executed"] == "absolute"
    assert out.trades[0].exit_price == Decimal("90.00")


def test_a_gapped_stop_publishes_both_the_trigger_and_the_executed_price() -> None:
    """The divergence must be readable, not inferred: the trace carries the level that
    fired the rule (101.50) beside the price it could actually fill at (90.00), and the
    run's diagnostics count the occurrence."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "90", "92", "88", "91")]
    protection = {"absolute_stop": {"enabled": True, "absolute_price": "101.50"}}
    out = _run(protection, bars)

    resolution = next(e for e in out.signal_events if e.event_type == "stop_resolution")
    assert resolution.detail["gap_adjusted"] is True
    assert resolution.detail["trigger_price"] == "101.50"
    assert resolution.detail["executed_price"] == "90.00"
    assert out.diagnostics["gap_adjusted_stops"] == 1


def test_an_ungapped_run_reports_no_gap_adjusted_stops() -> None:
    """The counter is evidence, so it must stay at 0 when nothing gapped — otherwise it
    would read as noise rather than as a signal about the data."""
    bars = [*flat_run(), _UP_CROSS, bar(22, "102", "102", "90", "95")]
    out = _run(_PCT_1, bars)

    assert out.diagnostics["gap_adjusted_stops"] == 0
    assert not [e for e in out.signal_events if e.event_type == "stop_resolution"]
