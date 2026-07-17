"""F-07h — stop / stop-limit order engine tests (doc 02 §5.2, Master Ref §6.2/§6.3).

The saved schema previously carried NO stop trigger, so stop / stop-limit orders failed
closed (STRATEGY_ORDER_TYPE_UNSUPPORTED). These tests pin the new behaviour: the schema
stores a stop activation rule + trigger offset; a plain stop order rests a trigger that
fires when a later bar reaches the level and fills market-like at max(trigger, open)
(long; short mirror — a gap through the trigger fills at the open); a stop-limit order
arms the F-07b limit machine only AFTER the trigger fires, with the limit resting from
the NEXT bar (same-bar stop-then-limit ordering needs tick data — never modelled) and
validity/unfilled policy applied verbatim. A missing/invalid trigger stays fail-closed.
Each setting has a positive and a negative case (spec F-07 acceptance). Entries are
driven by the breakout proxy: 20 flat bars fill the look-back window, a breakout bar
produces the signal, and the following bars resolve the resting trigger. Follow-up
closes stay at/under the running window high (103) so no fresh breakout re-fires while
a resting order is being resolved (the F-07b test-design trap).
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from entropia.domain.backtest.engine import (
    DECISION_TRACE_EVENT_TYPES,
    EngineOutput,
    order_execution_is_modelled,
    run_engine,
)
from entropia.domain.strategy.config import (
    LimitOrderDetails,
    OrderConfig,
    StopOrderDetails,
    StrategyConfig,
)

_ZERO_COST = {"slippage_mode": "percentage_slippage", "slippage_value": "0"}


def _config(
    *,
    order_config: dict[str, Any] | None = None,
    direction: str = "long_and_short",
) -> StrategyConfig:
    """A minimal VALID StrategyConfig; only the fields the engine reads matter.

    Costs are zero so a fill lands exactly on the resolved price; no protective stop is
    configured so a triggered entry holds to end-of-data (no stop interference)."""
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Stop Order Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {
                    "start": "2024-01-01T00:00:00Z",
                    "end": "2024-12-31T23:59:59Z",
                },
                "initial_capital": "10000.00",
                "execution": {
                    "entry_timing": "current_candle_close",
                    "exit_timing": "current_candle_close",
                },
                "order_config": order_config or {"type": "market_order"},
                "costs": _ZERO_COST,
                "intrabar_policy": {"tick_policy": "inherit"},
                "funding": {"enabled": False},
            },
            "position_entry_logic": {
                "direction_mode": direction,
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
            "protection_stop_logic": {},
            "position_sizing": {"method": "base_position_size", "base_position_size": "50"},
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


def _stop_order(
    *, activation_rule: str = "signal_price_plus_offset", offset: str | None = "2"
) -> dict[str, Any]:
    stop: dict[str, Any] = {"activation_rule": activation_rule}
    if offset is not None:
        stop["trigger_offset"] = offset
    return {"type": "stop_order", "stop": stop}


def _stop_limit_order(
    *,
    activation_rule: str = "signal_price_plus_offset",
    offset: str | None = "2",
    price_rule: str = "entry_signal_price",
    validity: str = "3_candles",
    unfilled_policy: str = "cancel_order",
    partial_fill_policy: str = "not_allowed",
) -> dict[str, Any]:
    stop: dict[str, Any] = {"activation_rule": activation_rule}
    if offset is not None:
        stop["trigger_offset"] = offset
    return {
        "type": "stop_limit_order",
        "stop": stop,
        "limit": {
            "price_rule": price_rule,
            "validity": validity,
            "unfilled_policy": unfilled_policy,
            "partial_fill_policy": partial_fill_policy,
        },
    }


def _bar(ts: str, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c, "volume": "10"}


def _flat(n: int, price: str = "100") -> list[dict[str, Any]]:
    return [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", price, price, price, price) for i in range(n)]


def _long_breakout_then(followups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """20 flat bars, an upside breakout (long signal, close 102), then the follow-up bars."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "103", "100", "102"))  # breakout -> long @102
    return bars + followups


def _short_breakout_then(followups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """20 flat bars, a downside breakout (short signal, close 98), then the follow-up bars."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "100", "97", "98"))  # breakdown -> short @98
    return bars + followups


def _fu(day: int, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return _bar(f"2024-01-{day:02d}T00:00:00Z", o, h, low, c)


# A bar that neither reaches a long trigger above 103 nor re-breaks out (close 103 is not
# strictly above the running window high 103) — holds a resting trigger/limit open.
def _no_touch(day: int) -> dict[str, Any]:
    return _fu(day, "103", "103", "103", "103")


def _run(config: StrategyConfig, bars: list[dict[str, Any]], *, batch: int = 8) -> EngineOutput:
    def batched() -> Iterator[list[dict[str, Any]]]:
        for start in range(0, len(bars), batch):
            yield bars[start : start + batch]

    return run_engine(strategy_config=config, bar_batches=batched(), execution_key="exec_key_test")


def _events(out: EngineOutput, kind: str) -> list[dict[str, Any]]:
    return [e.detail for e in out.signal_events if e.event_type == kind]


def _event_times(out: EngineOutput, kind: str) -> list[str]:
    return [e.event_time for e in out.signal_events if e.event_type == kind]


# --------------------------------------------------------------------------- #
# Predicate — the single shared source of truth (readiness + engine)          #
# --------------------------------------------------------------------------- #


def test_predicate_stop_order_with_trigger_is_modelled() -> None:
    assert order_execution_is_modelled(_config(order_config=_stop_order()))
    assert order_execution_is_modelled(
        _config(order_config=_stop_order(activation_rule="entry_signal_price", offset=None))
    )


def test_predicate_stop_offset_rule_without_offset_fails_closed() -> None:
    # An offset activation rule with no trigger_offset key is an invalid trigger —
    # the acceptance "trigger missing -> blocker" case (shared with Ready Check).
    assert not order_execution_is_modelled(_config(order_config=_stop_order(offset=None)))


def test_predicate_stop_limit_variants() -> None:
    assert order_execution_is_modelled(_config(order_config=_stop_limit_order()))
    # The limit leg keeps the F-07b constraints: best_bid_ask / partial fills fail closed.
    assert not order_execution_is_modelled(
        _config(order_config=_stop_limit_order(price_rule="best_bid_ask"))
    )
    assert not order_execution_is_modelled(
        _config(order_config=_stop_limit_order(partial_fill_policy="allowed"))
    )


# --------------------------------------------------------------------------- #
# Schema — conditional requiredness (doc 02 §5.2, Master Ref §6.3)            #
# --------------------------------------------------------------------------- #


def test_schema_stop_trigger_required_for_stop_types() -> None:
    with pytest.raises(ValidationError) as exc:
        OrderConfig(type="stop_order", stop=None)
    assert "Stop trigger details required" in str(exc.value)
    with pytest.raises(ValidationError) as exc:
        OrderConfig(type="stop_limit_order", stop=None)
    assert "Stop trigger details required" in str(exc.value)


def test_schema_trigger_offset_required_for_offset_rules() -> None:
    with pytest.raises(ValidationError) as exc:
        StopOrderDetails(activation_rule="signal_price_plus_offset", trigger_offset=None)
    assert "Trigger offset required" in str(exc.value)
    # entry_signal_price needs no offset.
    details = StopOrderDetails(activation_rule="entry_signal_price", trigger_offset=None)
    assert details.trigger_offset is None


def test_schema_unused_subtrees_are_cleared() -> None:
    # A non-stop type clears a stray stop subtree; a stop_order clears limit fields
    # (Master Ref §6.3: "Stop Orderda limit-specific alanlar kullanilmaz").
    market = OrderConfig(
        type="market_order",
        stop=StopOrderDetails(activation_rule="entry_signal_price"),
    )
    assert market.stop is None
    stop = OrderConfig(
        type="stop_order",
        stop=StopOrderDetails(activation_rule="entry_signal_price"),
        limit=LimitOrderDetails(price_rule="entry_signal_price", unfilled_policy="cancel_order"),
    )
    assert stop.limit is None
    assert stop.stop is not None


def test_stop_trace_event_types_registered() -> None:
    for name in ("stop_order_placed", "stop_order_triggered", "stop_order_cancelled"):
        assert name in DECISION_TRACE_EVENT_TYPES
        assert len(name) <= 32


# --------------------------------------------------------------------------- #
# Stop order — resting trigger, market-like fill                              #
# --------------------------------------------------------------------------- #


def test_stop_order_long_triggers_and_fills_at_trigger() -> None:
    # Long buy-stop at 102 + 2 = 104; bar 22 reaches high 105 >= 104 -> fills at 104
    # (open 103 below the trigger -> no gap, the trigger price is the fill).
    followups = [_fu(22, "103", "105", "103", "103"), _no_touch(23)]
    out = _run(_config(order_config=_stop_order()), _long_breakout_then(followups))
    assert out.diagnostics["order_type"] == "stop_order"
    assert out.diagnostics["order_execution_modelled"] is True
    assert out.diagnostics["stop_orders_placed"] == 1
    assert out.diagnostics["stop_orders_triggered"] == 1
    assert out.diagnostics["stop_orders_cancelled"] == 0
    assert out.summary["total_trades"] == 1
    assert out.trades[0].direction == "long"
    assert out.trades[0].entry_price == Decimal("104.00")
    placed = _events(out, "stop_order_placed")
    assert placed and placed[0]["trigger_price"] == "104"
    assert placed[0]["activation_rule"] == "signal_price_plus_offset"
    triggered = _events(out, "stop_order_triggered")
    assert triggered and triggered[0]["fill_price"] == "104"
    fills = _events(out, "entry_fill")
    assert fills and fills[0]["order_type"] == "stop_order"


def test_stop_order_not_triggered_opens_nothing() -> None:
    # Trigger 104 never reached (follow-up highs stay at 103) -> no position, and the
    # unfired trigger is an auditable end-of-data cancellation, never a silent gap.
    followups = [_no_touch(22), _no_touch(23), _no_touch(24)]
    out = _run(_config(order_config=_stop_order()), _long_breakout_then(followups))
    assert out.summary["total_trades"] == 0
    assert out.diagnostics["stop_orders_placed"] == 1
    assert out.diagnostics["stop_orders_triggered"] == 0
    assert out.diagnostics["stop_orders_cancelled"] == 1
    cancelled = _events(out, "stop_order_cancelled")
    assert cancelled and cancelled[0]["reason"] == "end_of_data"


def test_stop_order_gap_through_trigger_fills_at_open() -> None:
    # Bar 22 opens at 106, already beyond the 104 trigger -> the trigger price no longer
    # exists; the fill is the open (106), never a phantom fill at 104.
    followups = [_fu(22, "106", "107", "105", "105"), _no_touch(23)]
    out = _run(_config(order_config=_stop_order()), _long_breakout_then(followups))
    assert out.summary["total_trades"] == 1
    assert out.trades[0].entry_price == Decimal("106.00")


def test_stop_order_short_mirror_fills_at_trigger() -> None:
    # Short sell-stop at 98 - 2 = 96; bar 22 low 95 <= 96 -> fills at 96 (open 97 above
    # the trigger -> min(96, 97) = 96).
    followups = [
        _fu(22, "97", "97", "95", "97"),
        _fu(23, "97", "97", "97", "97"),
    ]
    out = _run(
        _config(order_config=_stop_order(activation_rule="signal_price_minus_offset")),
        _short_breakout_then(followups),
    )
    assert out.summary["total_trades"] == 1
    assert out.trades[0].direction == "short"
    assert out.trades[0].entry_price == Decimal("96.00")


def test_stop_order_never_triggers_on_signal_bar() -> None:
    # entry_signal_price rule -> trigger 102; the SIGNAL bar's own high (103) already
    # exceeds it, but the trigger rests from the NEXT bar (a same-bar trigger would look
    # ahead) -> the fire is on bar 22, at max(102, open 103) = 103.
    followups = [_no_touch(22), _no_touch(23)]
    out = _run(
        _config(order_config=_stop_order(activation_rule="entry_signal_price", offset=None)),
        _long_breakout_then(followups),
    )
    assert out.summary["total_trades"] == 1
    assert out.trades[0].entry_price == Decimal("103.00")
    assert _event_times(out, "stop_order_triggered") == ["2024-01-22T00:00:00Z"]


# --------------------------------------------------------------------------- #
# Stop-limit order — trigger arms the F-07b limit machine                     #
# --------------------------------------------------------------------------- #


def test_stop_limit_triggers_then_limit_fills() -> None:
    # Trigger 104 fires on bar 22; the limit (entry signal price, 102) rests from bar 23
    # and fills there on low 101 <= 102 -> entry AT the limit, not the trigger.
    followups = [
        _fu(22, "103", "105", "103", "103"),
        _fu(23, "103", "103", "101", "103"),
        _no_touch(24),
    ]
    out = _run(_config(order_config=_stop_limit_order()), _long_breakout_then(followups))
    assert out.diagnostics["order_type"] == "stop_limit_order"
    assert out.diagnostics["stop_orders_placed"] == 1
    assert out.diagnostics["stop_orders_triggered"] == 1
    assert out.diagnostics["limit_orders_placed"] == 1
    assert out.diagnostics["limit_orders_filled"] == 1
    assert out.summary["total_trades"] == 1
    assert out.trades[0].entry_price == Decimal("102.00")
    triggered = _events(out, "stop_order_triggered")
    assert triggered and triggered[0]["limit_price"] == "102"
    armed = _events(out, "limit_order_placed")
    assert armed and armed[0]["armed_by"] == "stop_order_triggered"
    fills = _events(out, "entry_fill")
    assert fills and fills[0]["order_type"] == "stop_limit_order"


def test_stop_limit_same_bar_limit_touch_does_not_fill() -> None:
    # Bar 22 BOTH fires the trigger (high 105) and touches the limit (low 101 <= 102),
    # but same-bar stop-then-limit ordering needs tick data -> the limit rests only from
    # bar 23. With current-candle validity and no later touch, the order expires
    # unfilled: the trigger fired yet the position never opened (doc 02 §5.2).
    followups = [
        _fu(22, "103", "105", "101", "103"),
        _no_touch(23),
        _no_touch(24),
    ]
    out = _run(
        _config(order_config=_stop_limit_order(validity="current_candle_only")),
        _long_breakout_then(followups),
    )
    assert out.summary["total_trades"] == 0
    assert out.diagnostics["stop_orders_triggered"] == 1
    assert out.diagnostics["limit_orders_placed"] == 1
    assert out.diagnostics["limit_orders_filled"] == 0
    assert out.diagnostics["limit_orders_cancelled"] == 1
    cancelled = _events(out, "limit_order_cancelled")
    assert cancelled and cancelled[0]["reason"] == "validity_expired"


def test_stop_limit_convert_to_market_at_expiry() -> None:
    # Trigger fires on bar 22; the limit never touches within validity (1 candle) and
    # the unfilled policy converts to market at the expiry bar's close (103) — the
    # F-07b machine applied verbatim to the armed leg.
    followups = [
        _fu(22, "103", "105", "103", "103"),
        _no_touch(23),
        _no_touch(24),
    ]
    out = _run(
        _config(
            order_config=_stop_limit_order(
                validity="1_candle", unfilled_policy="convert_to_market_order"
            )
        ),
        _long_breakout_then(followups),
    )
    assert out.summary["total_trades"] == 1
    assert out.trades[0].entry_price == Decimal("103.00")
    assert out.diagnostics["limit_orders_filled"] == 1


def test_stop_limit_never_triggered_arms_no_limit() -> None:
    # The trigger never fires -> the limit leg is never armed (no limit_order_placed),
    # and the resting trigger is cancelled at end-of-data.
    followups = [_no_touch(22), _no_touch(23), _no_touch(24)]
    out = _run(_config(order_config=_stop_limit_order()), _long_breakout_then(followups))
    assert out.summary["total_trades"] == 0
    assert out.diagnostics["stop_orders_triggered"] == 0
    assert out.diagnostics["stop_orders_cancelled"] == 1
    assert out.diagnostics["limit_orders_placed"] == 0
    assert _events(out, "limit_order_placed") == []
