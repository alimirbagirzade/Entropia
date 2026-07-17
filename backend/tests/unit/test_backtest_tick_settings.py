"""F-07i (C) — tick-dependent execution SETTINGS over the intrabar print path (unit).

Per opened setting: a POSITIVE test (tick demand + print path -> the real intrabar
behaviour) and a NEGATIVE test (no tick demand -> the shared predicate stays False ->
Ready Check BLOCKER + an inert engine run). Covers: the ``execution_timing_is_modelled``
/ ``order_execution_is_modelled`` tick gates (incl. ``best_bid_ask`` staying blocked),
``intrabar_touch`` entry/exit touch orders (print-authoritative), print-authoritative
``limit_fill_simulation``, the ``stop_limit_priority_simulation`` same-bar
stop-then-limit print sequence, every partial-fill policy (fraction from print SIZES;
size-less evidence degrades to the flagged coarse full fill), and the emptied
``UNMODELLED_DECISION_CLASSES``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    UNMODELLED_DECISION_CLASSES,
    EngineOutput,
    execution_timing_is_modelled,
    order_execution_is_modelled,
    run_engine,
)
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.readiness.enums import ReadinessIssueCode as Code
from entropia.domain.readiness.issues import ReadinessItemInput
from entropia.domain.readiness.validators import evaluate_readiness
from entropia.domain.strategy.config import StrategyConfig

# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


def _cfg(
    *,
    entry_timing: str = "current_candle_close",
    exit_timing: str = "current_candle_close",
    tick_policy: str = "require",
    order_config: dict[str, Any] | None = None,
    protection: dict[str, Any] | None = None,
) -> StrategyConfig:
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Tick Settings Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
                "initial_capital": "10000.00",
                "execution": {"entry_timing": entry_timing, "exit_timing": exit_timing},
                "order_config": order_config or {"type": "market_order"},
                "costs": {"slippage_mode": "percentage_slippage", "slippage_value": "0"},
                "intrabar_policy": {"tick_policy": tick_policy},
                "funding": {"enabled": False},
            },
            "position_entry_logic": {
                "direction_mode": "long_and_short",
                "signal_block": {"rule": "required_indicator_blocks_only"},
                "indicator_blocks": [
                    {
                        "block_id": "blk_1",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_1",
                            "package_revision_id": "pkgrev_1",
                            "package_content_hash": "pkghash_1",
                        },
                        "trigger_source": "indicator_native_trigger",
                        "requirement": "required",
                    }
                ],
            },
            "position_exit_logic": {
                "applies_to_direction": "long_and_short",
                "close_percentage": "100",
            },
            "protection_stop_logic": protection or {},
            "position_sizing": {"method": "base_position_size", "base_position_size": "50"},
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


def _limit_order(
    *,
    price_rule: str = "entry_signal_price",
    partial: str = "not_allowed",
    validity: str = "until_cancelled",
    unfilled: str = "keep_until_validity_ends",
) -> dict[str, Any]:
    return {
        "type": "limit_order",
        "limit": {
            "price_rule": price_rule,
            "validity": validity,
            "unfilled_policy": unfilled,
            "partial_fill_policy": partial,
        },
    }


def _stop_limit_order(*, partial: str = "not_allowed") -> dict[str, Any]:
    return {
        "type": "stop_limit_order",
        "stop": {"activation_rule": "entry_signal_price"},
        "limit": {
            "price_rule": "entry_signal_price",
            "validity": "until_cancelled",
            "unfilled_policy": "keep_until_validity_ends",
            "partial_fill_policy": partial,
        },
    }


_DAY = "2024-01-{0:02d}T00:00:00Z"


def _bar(day: int, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return {
        "timestamp": _DAY.format(day),
        "open": o,
        "high": h,
        "low": low,
        "close": c,
        "volume": "10",
    }


def _breakout_bars() -> list[dict[str, Any]]:
    """20 flat bars -> an upside breakout at close 102 (the proxy entry SIGNAL bar)."""
    bars = [_bar(i + 1, "100", "100", "100", "100") for i in range(20)]
    bars.append(_bar(21, "100", "102", "100", "102"))
    return bars


def _tick(day: int, hhmm: str, price: str, size: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"timestamp": f"2024-01-{day:02d}T{hhmm}:00Z", "price": price}
    if size is not None:
        row["size"] = size
    return row


def _run(
    config: StrategyConfig,
    bars: list[dict[str, Any]],
    ticks: list[dict[str, Any]] | None,
) -> EngineOutput:
    return run_engine(
        strategy_config=config,
        bar_batches=iter([bars]),
        execution_key="exec_key_test",
        timeframe="1D",
        tick_batches=iter([ticks]) if ticks is not None else None,
    )


def _events(out: EngineOutput, event_type: str) -> list[Any]:
    return [e for e in out.signal_events if e.event_type == event_type]


def _strategy_item(config_payload: StrategyConfig) -> ReadinessItemInput:
    return ReadinessItemInput(
        item_id="item_s1",
        kind=MainboardItemKind.STRATEGY,
        root_id="root_s1",
        revision_id="rev_s1",
        available=True,
        payload=config_payload.model_dump(mode="json"),
    )


def _codes(config: StrategyConfig) -> set[str]:
    result = evaluate_readiness(
        [_strategy_item(config)], allocation_enabled=False, allocation_issues=[]
    )
    return {issue.code.value for issue in result.issues}


# --------------------------------------------------------------------------- #
# Predicates: tick modes open ONLY with the tick demand                        #
# --------------------------------------------------------------------------- #


def test_timing_predicate_opens_tick_modes_only_with_tick_demand() -> None:
    assert execution_timing_is_modelled(_cfg(entry_timing="intrabar_touch")) is True
    assert (
        execution_timing_is_modelled(_cfg(entry_timing="intrabar_touch", tick_policy="inherit"))
        is False
    )
    assert execution_timing_is_modelled(_cfg(exit_timing="stop_limit_priority_simulation")) is True
    assert (
        execution_timing_is_modelled(
            _cfg(exit_timing="stop_limit_priority_simulation", tick_policy="disable")
        )
        is False
    )


def test_limit_fill_simulation_needs_a_limit_backed_order_type() -> None:
    with_limit = _cfg(entry_timing="limit_fill_simulation", order_config=_limit_order())
    without_limit = _cfg(entry_timing="limit_fill_simulation")  # market order: nothing to simulate
    assert execution_timing_is_modelled(with_limit) is True
    assert execution_timing_is_modelled(without_limit) is False


def test_order_predicate_opens_partial_fill_only_with_tick_demand() -> None:
    assert order_execution_is_modelled(_cfg(order_config=_limit_order(partial="allowed"))) is True
    assert (
        order_execution_is_modelled(
            _cfg(order_config=_limit_order(partial="allowed"), tick_policy="inherit")
        )
        is False
    )
    # not_allowed stays modelled without any tick demand (the F-07b baseline).
    assert (
        order_execution_is_modelled(
            _cfg(order_config=_limit_order(partial="not_allowed"), tick_policy="inherit")
        )
        is True
    )
    assert (
        order_execution_is_modelled(
            _cfg(order_config=_stop_limit_order(partial="minimum_50_percent"))
        )
        is True
    )


def test_best_bid_ask_stays_blocked_even_with_tick_demand() -> None:
    # A bid/ask QUOTE series (Spread/Execution dataset, Master Ref §2.3) is a different
    # data plane than tick/trade prints — the rule stays fail-closed.
    config = _cfg(order_config=_limit_order(price_rule="best_bid_ask"))
    assert order_execution_is_modelled(config) is False
    assert Code.STRATEGY_ORDER_TYPE_UNSUPPORTED.value in _codes(config)


def test_ready_check_blocks_tick_timing_without_tick_demand() -> None:
    blocked = _cfg(entry_timing="intrabar_touch", tick_policy="inherit")
    assert Code.STRATEGY_EXECUTION_TIMING_UNSUPPORTED.value in _codes(blocked)
    opened = _cfg(entry_timing="intrabar_touch")
    assert Code.STRATEGY_EXECUTION_TIMING_UNSUPPORTED.value not in _codes(opened)


def test_ready_check_blocks_partial_fill_without_tick_demand() -> None:
    blocked = _cfg(order_config=_limit_order(partial="allowed"), tick_policy="inherit")
    assert Code.STRATEGY_ORDER_TYPE_UNSUPPORTED.value in _codes(blocked)
    opened = _cfg(order_config=_limit_order(partial="allowed"))
    assert Code.STRATEGY_ORDER_TYPE_UNSUPPORTED.value not in _codes(opened)


def test_engine_stays_inert_for_tick_timing_without_tick_demand() -> None:
    # Fail-closed backstop to Ready Check: a stale readiness state reaching the worker
    # with an un-backed tick timing opens NO position at all.
    bars = [*_breakout_bars(), _bar(22, "102", "103", "101", "102")]
    out = _run(_cfg(entry_timing="intrabar_touch", tick_policy="inherit"), bars, None)
    assert out.summary["total_trades"] == 0
    assert not _events(out, "entry_fill")


def test_unmodelled_decision_classes_is_empty() -> None:
    assert UNMODELLED_DECISION_CLASSES == ()


# --------------------------------------------------------------------------- #
# intrabar_touch ENTRY: a touch order at the signal price                      #
# --------------------------------------------------------------------------- #


def test_touch_entry_fills_when_prints_return_to_the_signal_price() -> None:
    # Signal at close 102 (bar 21). Bar 22 gaps UP (low 103, prints never at 102) ->
    # no fill. Bar 23 prints come back to 102 -> the touch order fills AT the level.
    bars = [
        *_breakout_bars(),
        _bar(22, "103", "105", "103", "104"),
        _bar(23, "104", "104", "101", "103"),
    ]
    ticks = [
        _tick(22, "01:00", "104.5"),
        _tick(23, "01:00", "102.5"),
        _tick(23, "02:00", "101.8"),  # first touch: 101.8 <= 102
    ]
    out = _run(_cfg(entry_timing="intrabar_touch"), bars, ticks)
    assert out.summary["total_trades"] == 1
    assert out.trades[0].entry_price == Decimal("102")
    assert out.diagnostics["touch_orders_placed"] == 1
    assert out.diagnostics["tick_resolved_entry_fills"] == 1
    fill = _events(out, "entry_fill")[0]
    assert fill.detail["tick_resolved"] is True
    placed = _events(out, "limit_order_placed")[0]
    assert placed.detail["mode"] == "intrabar_touch"


def test_touch_entry_is_print_authoritative_over_the_bar_extreme() -> None:
    # Bar 22's LOW touches the 102 level but its prints never do -> under the touch
    # timing the print path is authoritative: NO fill, the order rests to end-of-data.
    bars = [*_breakout_bars(), _bar(22, "103", "105", "101.5", "104")]
    ticks = [_tick(22, "01:00", "104.5"), _tick(22, "02:00", "103.2")]
    out = _run(_cfg(entry_timing="intrabar_touch"), bars, ticks)
    assert out.summary["total_trades"] == 0
    cancelled = _events(out, "limit_order_cancelled")
    assert cancelled and cancelled[0].detail["reason"] == "end_of_data"
    # The SAME data without the touch timing (baseline limit order, bar-touch model)
    # DOES fill — the print authority is what the tick timing adds.
    baseline = _run(
        _cfg(order_config=_limit_order()),
        bars,
        None,
    )
    assert baseline.summary["total_trades"] == 1


# --------------------------------------------------------------------------- #
# limit_fill_simulation: the configured limit order over the print path        #
# --------------------------------------------------------------------------- #


def test_limit_fill_simulation_fills_only_on_a_real_print_touch() -> None:
    bars = [
        *_breakout_bars(),
        _bar(22, "103", "105", "101.5", "104"),  # bar extreme touches, prints do NOT
        _bar(23, "104", "104", "101", "103"),  # prints DO touch
    ]
    ticks = [
        _tick(22, "01:00", "103.5"),
        _tick(23, "01:00", "101.9", "60"),  # 101.9 <= 102, size covers the planned 50
    ]
    config = _cfg(entry_timing="limit_fill_simulation", order_config=_limit_order())
    out = _run(config, bars, ticks)
    assert out.summary["total_trades"] == 1
    fill = _events(out, "entry_fill")[0]
    assert fill.detail["tick_resolved"] is True
    assert fill.detail["fill_price"] == "102.00"
    # The fill landed on bar 23 (the print touch), NOT bar 22 (the bar-extreme touch).
    assert fill.detail["bar_seq"] == 23


# --------------------------------------------------------------------------- #
# Partial-fill policies: fraction from print SIZES                             #
# --------------------------------------------------------------------------- #


def _partial_config(policy: str) -> StrategyConfig:
    return _cfg(
        entry_timing="limit_fill_simulation",
        order_config=_limit_order(partial=policy),
    )


def test_partial_allowed_books_the_evidenced_fraction_and_tops_up_later() -> None:
    bars = [
        *_breakout_bars(),
        _bar(22, "102", "103", "101", "102.5"),
        _bar(23, "102", "103", "101", "102.5"),
        _bar(24, "102", "103", "102", "102.5"),
    ]
    ticks = [
        _tick(22, "01:00", "101.5", "20"),  # 20 of the planned 50
        _tick(23, "01:00", "101.7", "40"),  # tops the remaining 30 up
    ]
    out = _run(_partial_config("allowed"), bars, ticks)
    fill = _events(out, "entry_fill")[0]
    assert fill.detail["partial_fill"] is True
    assert fill.detail["size"] == "20"
    partials = _events(out, "partial_fill")
    actions = [e.detail["action"] for e in partials]
    assert actions == ["remainder_resting", "remainder_touch"]
    assert partials[1].detail["fill_size"] == "30"
    assert partials[1].detail["new_size"] == "50"
    assert out.diagnostics["partial_fills"] == 2
    assert "partial_fill_evidence_unavailable" not in out.diagnostics["warnings"]


def test_partial_minimum_50_rejects_a_sub_half_bar_and_fills_a_half_plus_bar() -> None:
    bars = [
        *_breakout_bars(),
        _bar(22, "102", "103", "101", "102.5"),
        _bar(23, "102", "103", "101", "102.5"),
    ]
    ticks = [
        _tick(22, "01:00", "101.5", "20"),  # 20 < 50% of 50 -> rejected, order rests
        _tick(23, "01:00", "101.7", "30"),  # 30 >= 50% -> fills 30, 20 keeps resting
    ]
    out = _run(_partial_config("minimum_50_percent"), bars, ticks)
    partials = _events(out, "partial_fill")
    assert partials[0].detail["action"] == "rejected_below_minimum"
    assert partials[0].detail["bar_seq"] == 22
    fill = _events(out, "entry_fill")[0]
    assert fill.detail["bar_seq"] == 23
    assert fill.detail["size"] == "30"
    assert partials[1].detail["action"] == "remainder_resting"
    assert partials[1].detail["remaining_size"] == "20"


def test_partial_fill_remaining_as_market_completes_at_the_bar_close() -> None:
    bars = [*_breakout_bars(), _bar(22, "102", "103", "101", "102.5")]
    ticks = [_tick(22, "01:00", "101.5", "20")]
    out = _run(_partial_config("fill_remaining_as_market"), bars, ticks)
    fill = _events(out, "entry_fill")[0]
    assert fill.detail["size"] == "20"
    partials = _events(out, "partial_fill")
    actions = [e.detail["action"] for e in partials]
    assert actions == ["remainder_market_filled", "market_remainder"]
    # 20 @ limit 102 + 30 @ close 102.5 -> weighted basis 102.30, total size 50.
    assert partials[1].detail["fill_size"] == "30"
    assert partials[1].detail["new_size"] == "50"
    assert partials[1].detail["entry_basis"] == "102.30"


def test_partial_cancel_remaining_books_the_fraction_and_drops_the_rest() -> None:
    bars = [
        *_breakout_bars(),
        _bar(22, "102", "103", "101", "102.5"),
        _bar(23, "102", "103", "101", "102.5"),  # prints touch again — must NOT top up
    ]
    ticks = [
        _tick(22, "01:00", "101.5", "20"),
        _tick(23, "01:00", "101.7", "40"),
    ]
    out = _run(_partial_config("cancel_remaining"), bars, ticks)
    partials = _events(out, "partial_fill")
    assert [e.detail["action"] for e in partials] == ["remainder_cancelled"]
    fill = _events(out, "entry_fill")[0]
    assert fill.detail["size"] == "20"
    assert out.diagnostics["partial_fills"] == 1


def test_partial_without_print_sizes_degrades_to_the_flagged_full_fill() -> None:
    bars = [*_breakout_bars(), _bar(22, "102", "103", "101", "102.5")]
    ticks = [_tick(22, "01:00", "101.5")]  # touching print WITHOUT a size column
    out = _run(_partial_config("allowed"), bars, ticks)
    fill = _events(out, "entry_fill")[0]
    assert fill.detail["size"] == "50"  # the coarse full-fill model
    assert "partial_fill" not in fill.detail
    assert "partial_fill_evidence_unavailable" in out.diagnostics["warnings"]


# --------------------------------------------------------------------------- #
# stop_limit_priority_simulation: same-bar stop-then-limit print sequence      #
# --------------------------------------------------------------------------- #


def test_stop_limit_priority_simulation_fills_same_bar_from_the_print_sequence() -> None:
    bars = [*_breakout_bars(), _bar(22, "101", "103", "100.5", "102.5")]
    ticks = [
        _tick(22, "01:00", "102.5"),  # fires the 102 trigger (first touch)
        _tick(22, "02:00", "101.8"),  # AFTER the trigger: reaches the 102 limit
    ]
    config = _cfg(exit_timing="stop_limit_priority_simulation", order_config=_stop_limit_order())
    out = _run(config, bars, ticks)
    fill = _events(out, "entry_fill")[0]
    assert fill.detail["bar_seq"] == 22  # SAME bar as the trigger — the observed print sequence
    assert fill.detail["same_bar_stop_limit"] is True
    assert out.diagnostics["same_bar_stop_limit_fills"] == 1
    triggered = _events(out, "stop_order_triggered")[0]
    assert triggered.detail["bar_seq"] == 22


def test_stop_limit_without_the_simulation_timing_keeps_the_next_bar_model() -> None:
    # Identical data, baseline exit timing: the armed limit is first examined on the
    # NEXT bar (the F-07h conservative model) — the same-bar sequence is (C)'s delta.
    bars = [
        *_breakout_bars(),
        _bar(22, "101", "103", "100.5", "102.5"),
        _bar(23, "102", "103", "101", "102.5"),
    ]
    ticks = [
        _tick(22, "01:00", "102.5"),
        _tick(22, "02:00", "101.8"),
        _tick(23, "01:00", "101.9"),
    ]
    out = _run(_cfg(order_config=_stop_limit_order()), bars, ticks)
    fill = _events(out, "entry_fill")[0]
    assert fill.detail["bar_seq"] == 23
    assert out.diagnostics["same_bar_stop_limit_fills"] == 0


def test_stop_limit_simulation_without_a_limit_print_never_opens_same_bar() -> None:
    # The trigger fires but no later print comes back to the limit: doc 02 §5.2 — the
    # position does not open this bar (and here never, prints stay above the limit).
    bars = [*_breakout_bars(), _bar(22, "101", "103", "100.5", "102.5")]
    ticks = [_tick(22, "01:00", "102.5"), _tick(22, "02:00", "102.6")]
    config = _cfg(exit_timing="stop_limit_priority_simulation", order_config=_stop_limit_order())
    out = _run(config, bars, ticks)
    assert not _events(out, "entry_fill")
    assert out.diagnostics["same_bar_stop_limit_fills"] == 0


# --------------------------------------------------------------------------- #
# intrabar_touch EXIT: a resting touch exit at the exit-signal level           #
# --------------------------------------------------------------------------- #


def test_touch_exit_fills_when_prints_return_to_the_exit_level() -> None:
    # Long from the breakout (102). Bar 23 closes at 99 (below the 100 window low ->
    # proxy exit signal); the exit rests at 99 and fills on bar 24's print at/above it.
    bars = [
        *_breakout_bars(),
        _bar(22, "102", "102.5", "100.5", "101"),
        _bar(23, "101", "101", "98.5", "99"),
        _bar(24, "98.8", "100", "98.5", "98.9"),
    ]
    ticks = [_tick(24, "01:00", "98.7"), _tick(24, "02:00", "99.4")]  # 99.4 >= 99
    out = _run(_cfg(exit_timing="intrabar_touch"), bars, ticks)
    assert out.summary["total_trades"] == 1
    trade = out.trades[0]
    assert trade.exit_reason == "exit_signal"
    assert trade.exit_price == Decimal("99")
    assert out.diagnostics["touch_exit_fills"] == 1
    scheduled = _events(out, "exit_scheduled")[0]
    assert scheduled.detail["timing"] == "intrabar_touch"
    assert scheduled.detail["touch_level"] == "99"


def test_touch_exit_rests_while_prints_stay_away_from_the_level() -> None:
    # Prints on bar 24 never rise back to 99 -> the position stays open to end-of-data
    # (the honest touch semantics: opportunity exits fill only on a real return).
    bars = [
        *_breakout_bars(),
        _bar(22, "102", "102.5", "100.5", "101"),
        _bar(23, "101", "101", "98.5", "99"),
        _bar(24, "98.8", "100", "98.5", "98.9"),
    ]
    ticks = [_tick(24, "01:00", "98.7"), _tick(24, "02:00", "98.9")]
    out = _run(_cfg(exit_timing="intrabar_touch"), bars, ticks)
    assert out.summary["total_trades"] == 1
    assert out.trades[0].exit_reason == "end_of_data"
    assert out.diagnostics["touch_exit_fills"] == 0


def test_partial_remainder_dies_with_its_position_and_never_reopens() -> None:
    # Partial fill (20 of 50) on bar 22 -> the 1% protection stop closes the position
    # on bar 23 -> bar 24's prints touch the limit again. The REMAINDER must be
    # cancelled (traced), never re-armed as a fresh full-size entry.
    bars = [
        *_breakout_bars(),
        _bar(22, "102", "103", "101", "102.5"),
        _bar(23, "102", "102", "90", "95"),  # low 90 trips the stop on the open position
        _bar(24, "95", "102.5", "95", "96"),  # prints touch 102 again — must NOT refill
    ]
    ticks = [
        _tick(22, "01:00", "101.5", "20"),
        _tick(23, "01:00", "103"),  # no touch (authority: prints never reach 102)
        _tick(24, "01:00", "101.9", "40"),
    ]
    config = _cfg(
        entry_timing="limit_fill_simulation",
        order_config=_limit_order(partial="allowed"),
        protection={"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}},
    )
    out = _run(config, bars, ticks)
    assert out.summary["total_trades"] == 1
    assert out.trades[0].exit_reason == "stop_loss"
    assert len(_events(out, "entry_fill")) == 1
    cancelled = _events(out, "limit_order_cancelled")
    assert cancelled and cancelled[0].detail["reason"] == "position_closed"
    assert cancelled[0].detail["remaining_size"] == "30"
