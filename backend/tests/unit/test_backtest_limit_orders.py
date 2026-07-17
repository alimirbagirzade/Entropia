"""F-07b — limit-order / order-validity / unfilled-policy engine tests (doc 02 §6.3, §2).

The bar-replay engine previously IGNORED ``order_config`` and always market-filled. These
tests pin the new behaviour: market / simulation orders keep the market fill; a limit order
rests a working order that fills only on a limit touch within the validity window, applies
its unfilled policy at expiry, and re-prices when configured; a TRIGGERLESS stop / stop-
limit (F-07h models the triggered variants — see test_backtest_stop_orders.py) and best-
bid-ask / partial-fill orders FAIL CLOSED (open no position). Each setting has a positive and a
negative case (spec F-07 acceptance).

Entries are driven by a real, production-reachable ``ta.sma`` cross plan (see
tests/unit/engine_signal_plan.py — F-24: the engine's breakout proxy is unreachable in a real
RUN, so no fixture is allowed to depend on it): 20 flat bars establish the MA, a breakout bar
crosses it and produces the signal, and the following bars resolve the resting order. Follow-up
closes stay at/under 103 so the MA is never re-crossed while a resting order is being resolved.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    EngineOutput,
    order_execution_is_modelled,
    run_engine,
)
from entropia.domain.strategy.config import StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan

_ZERO_COST = {"slippage_mode": "percentage_slippage", "slippage_value": "0"}


def _config(
    *,
    order_config: dict[str, Any] | None = None,
    direction: str = "long_and_short",
    with_stop: bool = False,
) -> StrategyConfig:
    """A minimal VALID StrategyConfig; only the fields the engine reads matter.

    Costs are zero so a fill lands exactly on the resolved price. ``with_stop`` defaults
    OFF so a resting-limit fill holds to end-of-data (no protective-stop interference)."""
    protection: dict[str, Any] = (
        {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}} if with_stop else {}
    )
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Limit Order Fixture",
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
            "protection_stop_logic": protection,
            "position_sizing": {"method": "base_position_size", "base_position_size": "50"},
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


def _limit_order(
    *,
    price_rule: str = "entry_signal_price",
    offset: str | None = None,
    validity: str = "3_candles",
    unfilled_policy: str = "cancel_order",
    partial_fill_policy: str = "not_allowed",
) -> dict[str, Any]:
    limit: dict[str, Any] = {
        "price_rule": price_rule,
        "validity": validity,
        "unfilled_policy": unfilled_policy,
        "partial_fill_policy": partial_fill_policy,
    }
    if offset is not None:
        limit["price_offset"] = offset
    return {"type": "limit_order", "limit": limit}


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


# A bar that neither touches a long limit at 102 (low 103 > 102) nor re-breaks out (close
# 103 is not strictly above the window high 103) — used to hold a resting order open.
def _no_touch(day: int) -> dict[str, Any]:
    return _fu(day, "103", "103", "103", "103")


def _run(config: StrategyConfig, bars: list[dict[str, Any]], *, batch: int = 8) -> EngineOutput:
    def batched() -> Iterator[list[dict[str, Any]]]:
        for start in range(0, len(bars), batch):
            yield bars[start : start + batch]

    return run_engine(
        strategy_config=config,
        bar_batches=batched(),
        execution_key="exec_key_test",
        indicator_plan=sma_entry_plan(),
    )


def _events(out: EngineOutput, kind: str) -> list[dict[str, Any]]:
    return [e.detail for e in out.signal_events if e.event_type == kind]


# --------------------------------------------------------------------------- #
# Predicate — the single shared source of truth (readiness + engine)          #
# --------------------------------------------------------------------------- #


def test_predicate_market_and_simulation_are_modelled() -> None:
    assert order_execution_is_modelled(_config(order_config={"type": "market_order"}))
    assert order_execution_is_modelled(_config(order_config={"type": "simulation_only"}))


def test_predicate_limit_modelled_only_for_supported_variants() -> None:
    assert order_execution_is_modelled(_config(order_config=_limit_order()))
    assert not order_execution_is_modelled(
        _config(order_config=_limit_order(price_rule="best_bid_ask"))
    )
    assert not order_execution_is_modelled(
        _config(order_config=_limit_order(partial_fill_policy="allowed"))
    )


def test_predicate_triggerless_stop_orders_fail_closed() -> None:
    # F-07h models stop/stop-limit WITH a trigger (test_backtest_stop_orders.py); a
    # missing ``stop`` subtree stays unexecutable → fail closed.
    assert not order_execution_is_modelled(_config(order_config={"type": "stop_order"}))
    assert not order_execution_is_modelled(
        _config(
            order_config={
                "type": "stop_limit_order",
                "limit": {
                    "price_rule": "entry_signal_price",
                    "validity": "3_candles",
                    "unfilled_policy": "cancel_order",
                    "partial_fill_policy": "not_allowed",
                },
            }
        )
    )


# --------------------------------------------------------------------------- #
# Market / simulation orders — the byte-identical market-fill baseline         #
# --------------------------------------------------------------------------- #


def test_market_order_fills_at_signal_close() -> None:
    out = _run(
        _config(order_config={"type": "market_order"}),
        _long_breakout_then([_no_touch(22), _no_touch(23)]),
    )
    assert out.diagnostics["order_type"] == "market_order"
    assert out.diagnostics["order_execution_modelled"] is True
    assert out.diagnostics["limit_orders_placed"] == 0
    assert out.summary["total_trades"] == 1
    # Immediate current_candle_close fill at the breakout bar's close (102), zero costs.
    assert out.trades[0].entry_price == Decimal("102.00")


def test_simulation_only_is_byte_identical_to_market_order() -> None:
    bars = _long_breakout_then([_no_touch(22), _no_touch(23)])
    market = _run(_config(order_config={"type": "market_order"}), bars)
    simulation = _run(_config(order_config={"type": "simulation_only"}), bars)
    assert market.summary == simulation.summary
    assert [t.entry_price for t in market.trades] == [t.entry_price for t in simulation.trades]
    assert simulation.diagnostics["order_type"] == "simulation_only"


# --------------------------------------------------------------------------- #
# Limit orders — positive fills                                                #
# --------------------------------------------------------------------------- #


def test_limit_order_long_fills_when_price_touches_limit() -> None:
    # Long limit rests at 102 (signal close); bar 22 dips to low 101 <= 102 -> fills at 102.
    followups = [_fu(22, "103", "103", "101", "103"), _no_touch(23)]
    out = _run(_config(order_config=_limit_order()), _long_breakout_then(followups))
    assert out.diagnostics["limit_orders_placed"] == 1
    assert out.diagnostics["limit_orders_filled"] == 1
    assert out.diagnostics["limit_orders_cancelled"] == 0
    assert out.summary["total_trades"] == 1
    assert out.trades[0].direction == "long"
    assert out.trades[0].entry_price == Decimal("102.00")  # filled AT the limit, not market
    fills = _events(out, "entry_fill")
    assert fills and fills[0]["order_type"] == "limit_order"


def test_limit_order_short_fills_when_high_reaches_limit() -> None:
    # Short limit rests at 98 (signal close); bar 22 spikes to high 99 >= 98 -> fills at 98.
    followups = [_fu(22, "97", "99", "96", "97"), _fu(23, "97", "98", "96", "97")]
    out = _run(_config(order_config=_limit_order()), _short_breakout_then(followups))
    assert out.diagnostics["limit_orders_filled"] == 1
    assert out.summary["total_trades"] == 1
    assert out.trades[0].direction == "short"
    assert out.trades[0].entry_price == Decimal("98.00")


def test_limit_order_signal_price_minus_offset_rule() -> None:
    # minus-offset 2: limit = 102 - 2 = 100; bar 22 must dip to <= 100 to fill.
    followups = [_fu(22, "101", "102", "100", "101"), _no_touch(23)]
    out = _run(
        _config(order_config=_limit_order(price_rule="signal_price_minus_offset", offset="2")),
        _long_breakout_then(followups),
    )
    assert out.diagnostics["limit_orders_filled"] == 1
    assert out.trades[0].entry_price == Decimal("100.00")
    placed = _events(out, "limit_order_placed")
    assert placed and placed[0]["limit_price"] == "100"


# --------------------------------------------------------------------------- #
# Limit orders — negative (no touch -> cancel) + validity window              #
# --------------------------------------------------------------------------- #


def test_limit_order_cancels_when_price_never_touches() -> None:
    # Limit at 102, validity 1 candle; bar 22 low 103 never reaches it -> cancelled, no trade.
    out = _run(
        _config(order_config=_limit_order(validity="1_candle")),
        _long_breakout_then([_no_touch(22), _no_touch(23)]),
    )
    assert out.diagnostics["limit_orders_placed"] == 1
    assert out.diagnostics["limit_orders_filled"] == 0
    assert out.diagnostics["limit_orders_cancelled"] == 1
    assert out.summary["total_trades"] == 0
    cancels = _events(out, "limit_order_cancelled")
    assert cancels and cancels[0]["reason"] == "validity_expired"


def test_limit_order_validity_window_bounds_the_fill() -> None:
    # validity 3 candles (expires bar 24): a touch on bar 24 (the last live bar) still fills;
    # the SAME bars with a 1-candle validity expire (bar 22) before the touch and cancel.
    followups = [
        _no_touch(22),
        _no_touch(23),
        _fu(24, "103", "103", "101", "102"),  # low 101 <= 102 (touch on the last live bar)
    ]
    filled = _run(
        _config(order_config=_limit_order(validity="3_candles")),
        _long_breakout_then(followups),
    )
    assert filled.diagnostics["limit_orders_filled"] == 1
    assert filled.summary["total_trades"] == 1

    expired = _run(
        _config(order_config=_limit_order(validity="1_candle")),
        _long_breakout_then(followups),
    )
    assert expired.diagnostics["limit_orders_filled"] == 0
    assert expired.diagnostics["limit_orders_cancelled"] == 1


# --------------------------------------------------------------------------- #
# Unfilled policies                                                            #
# --------------------------------------------------------------------------- #


def test_unfilled_policy_convert_to_market_fills_at_expiry_close() -> None:
    # Limit at 102 untouched on the (1-candle) expiry bar -> convert-to-market fills at close.
    followups = [_no_touch(22), _no_touch(23)]
    convert = _run(
        _config(
            order_config=_limit_order(
                validity="1_candle", unfilled_policy="convert_to_market_order"
            )
        ),
        _long_breakout_then(followups),
    )
    assert convert.diagnostics["limit_orders_filled"] == 1
    assert convert.summary["total_trades"] == 1
    assert convert.trades[0].entry_price == Decimal("103.00")  # market fill at bar-22 close

    # The SAME bars with cancel_order produce NO fill — proves convert is distinguishable.
    cancel = _run(
        _config(order_config=_limit_order(validity="1_candle", unfilled_policy="cancel_order")),
        _long_breakout_then(followups),
    )
    assert cancel.diagnostics["limit_orders_filled"] == 0
    assert cancel.summary["total_trades"] == 0


def test_unfilled_policy_re_price_next_candle_chases_price() -> None:
    # minus-offset 1: initial limit 101. bar22 low 102 misses; re-price from bar22 close 103
    # -> new limit 102; bar23 low 102 <= 102 -> fills at 102. A FIXED limit (cancel_order)
    # stays at 101 and never fills on these bars (both lows are 102 > 101).
    followups = [_fu(22, "103", "103", "102", "103"), _fu(23, "103", "103", "102", "102")]
    reprice = _run(
        _config(
            order_config=_limit_order(
                price_rule="signal_price_minus_offset",
                offset="1",
                validity="3_candles",
                unfilled_policy="re_price_next_candle",
            )
        ),
        _long_breakout_then(followups),
    )
    assert reprice.diagnostics["limit_orders_filled"] == 1
    assert reprice.trades[0].entry_price == Decimal("102.00")

    fixed = _run(
        _config(
            order_config=_limit_order(
                price_rule="signal_price_minus_offset",
                offset="1",
                validity="3_candles",
                unfilled_policy="cancel_order",
            )
        ),
        _long_breakout_then(followups),
    )
    assert fixed.diagnostics["limit_orders_filled"] == 0
    assert fixed.diagnostics["limit_orders_cancelled"] == 1


def test_until_cancelled_limit_rests_to_end_of_data_then_cancels() -> None:
    # until_cancelled never expires on a window bar; an untouched order cancels at end-of-data.
    out = _run(
        _config(order_config=_limit_order(validity="until_cancelled")),
        _long_breakout_then([_no_touch(22), _no_touch(23)]),
    )
    assert out.diagnostics["limit_orders_filled"] == 0
    assert out.diagnostics["limit_orders_cancelled"] == 1
    cancels = _events(out, "limit_order_cancelled")
    assert cancels and cancels[0]["reason"] == "end_of_data"


# --------------------------------------------------------------------------- #
# Fail-closed order types                                                      #
# --------------------------------------------------------------------------- #


def test_stop_order_fails_closed() -> None:
    out = _run(
        _config(order_config={"type": "stop_order"}),
        _long_breakout_then([_no_touch(22), _no_touch(23)]),
    )
    assert out.diagnostics["order_execution_modelled"] is False
    assert out.diagnostics["order_type"] == "stop_order"
    assert out.summary["total_trades"] == 0
    assert out.diagnostics["limit_orders_placed"] == 0
    assert "order_type_unsupported:stop_order" in out.diagnostics["warnings"]


def test_stop_limit_order_fails_closed() -> None:
    order_config = {
        "type": "stop_limit_order",
        "limit": {
            "price_rule": "entry_signal_price",
            "validity": "3_candles",
            "unfilled_policy": "cancel_order",
            "partial_fill_policy": "not_allowed",
        },
    }
    out = _run(_config(order_config=order_config), _long_breakout_then([_no_touch(22)]))
    assert out.diagnostics["order_execution_modelled"] is False
    assert out.summary["total_trades"] == 0


def test_best_bid_ask_price_rule_fails_closed() -> None:
    out = _run(
        _config(order_config=_limit_order(price_rule="best_bid_ask")),
        _long_breakout_then([_no_touch(22)]),
    )
    assert out.diagnostics["order_execution_modelled"] is False
    assert out.summary["total_trades"] == 0
    assert out.diagnostics["limit_orders_placed"] == 0


def test_partial_fill_policy_other_than_not_allowed_fails_closed() -> None:
    out = _run(
        _config(order_config=_limit_order(partial_fill_policy="allowed")),
        _long_breakout_then([_no_touch(22)]),
    )
    assert out.diagnostics["order_execution_modelled"] is False
    assert out.summary["total_trades"] == 0
    assert "order_type_unsupported:limit_order" in out.diagnostics["warnings"]
