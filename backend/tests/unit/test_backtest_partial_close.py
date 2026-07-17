"""F-07c/f — partial-close (close_percentage) + partial-aftermath engine tests (doc 02 §4).

The bar-replay engine held at most ONE full-size position and always fully closed; it ignored
``close_percentage`` entirely. These tests pin the new behaviour: an EXIT SIGNAL closes only
``close_percentage`` of the position as its own trade lot and holds the remainder under the
aftermath (move-stop-to-entry breakevens it, close-all collapses to a full close,
lock-in-profit moves the stop to the current price — F-07f closes this boundary). A
``trailing_stop`` aftermath is modelled ONLY when the strategy's own protection-level
trailing_stop is configured/enabled (it has no trailing parameters of its own to reuse); with
none configured it still FAILS CLOSED (see ``test_backtest_leverage_trailing.py`` for the
positive trailing-stop-aftermath case, which needs a protection trailing config this file's
minimal fixture does not set up). Partial FILLS stay unmodellable over OHLCV (no liquidity
data) and remain fail-closed from slice b. Entries + exit signals are the breakout proxy: 20
flat bars, an upside breakout (long @102), then a downside close (< the window low) is the
exit signal. Each setting has a positive and a negative case (spec F-07 acceptance).
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    EngineOutput,
    partial_close_is_modelled,
    run_engine,
)
from entropia.domain.strategy.config import StrategyConfig

_ZERO_COST = {"slippage_mode": "percentage_slippage", "slippage_value": "0"}


def _config(
    *,
    close_percentage: str = "100",
    partial_aftermath: str = "move_stop_to_entry",
    with_stop: bool = False,
) -> StrategyConfig:
    """A minimal VALID StrategyConfig; only the fields the engine reads matter.

    Zero costs so a fill lands exactly on the resolved price. ``with_stop`` OFF by default so
    the ONLY protective stop on a remainder is the one move-stop-to-entry installs."""
    protection: dict[str, Any] = (
        {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}} if with_stop else {}
    )
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Partial Close Fixture",
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
                "order_config": {"type": "market_order"},
                "costs": _ZERO_COST,
                "intrabar_policy": {"tick_policy": "inherit"},
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
                "close_percentage": close_percentage,
                "partial_aftermath": partial_aftermath,
            },
            "protection_stop_logic": protection,
            "position_sizing": {"method": "base_position_size", "base_position_size": "50"},
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


def _bar(ts: str, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c, "volume": "10"}


def _flat(n: int, price: str = "100") -> list[dict[str, Any]]:
    return [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", price, price, price, price) for i in range(n)]


def _fu(day: int, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return _bar(f"2024-01-{day:02d}T00:00:00Z", o, h, low, c)


def _long_then(followups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """20 flat bars, an upside breakout (long signal @102), then the follow-up bars."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "103", "100", "102"))  # breakout -> long @102
    return bars + followups


# The exit-signal bar: close 99 < the window low (100) -> the long exits on this bar.
_EXIT_SIGNAL = _fu(22, "100", "100", "99", "99")


def _run(config: StrategyConfig, bars: list[dict[str, Any]], *, batch: int = 8) -> EngineOutput:
    def batched() -> Iterator[list[dict[str, Any]]]:
        for start in range(0, len(bars), batch):
            yield bars[start : start + batch]

    return run_engine(strategy_config=config, bar_batches=batched(), execution_key="exec_key_test")


def _events(out: EngineOutput, kind: str) -> list[dict[str, Any]]:
    return [e.detail for e in out.signal_events if e.event_type == kind]


# --------------------------------------------------------------------------- #
# Predicate — shared source of truth (readiness + engine)                     #
# --------------------------------------------------------------------------- #


def test_predicate_full_close_always_modelled_regardless_of_aftermath() -> None:
    # close_percentage == 100 never leaves a remainder, so any aftermath is modelled.
    assert partial_close_is_modelled(
        _config(close_percentage="100", partial_aftermath="trailing_stop")
    )
    assert partial_close_is_modelled(
        _config(close_percentage="100", partial_aftermath="lock_in_profit")
    )


def test_predicate_partial_modelled_only_for_supported_aftermaths() -> None:
    assert partial_close_is_modelled(
        _config(close_percentage="50", partial_aftermath="move_stop_to_entry")
    )
    assert partial_close_is_modelled(_config(close_percentage="50", partial_aftermath="close_all"))
    # F-07f: lock_in_profit is self-contained (no extra config needed) -> always modelled.
    assert partial_close_is_modelled(
        _config(close_percentage="50", partial_aftermath="lock_in_profit")
    )
    # trailing_stop has no trailing parameters of its own -> modelled only when the
    # strategy's protection_stop_logic.trailing_stop rule is configured/enabled. This
    # fixture's minimal config carries no protection stops at all, so it stays unsupported.
    assert not partial_close_is_modelled(
        _config(close_percentage="50", partial_aftermath="trailing_stop")
    )


# --------------------------------------------------------------------------- #
# Full close — the byte-identical baseline                                    #
# --------------------------------------------------------------------------- #


def test_full_close_100_percent_is_a_single_trade() -> None:
    out = _run(
        _config(close_percentage="100"),
        _long_then([_EXIT_SIGNAL, _fu(23, "100", "100", "100", "100")]),
    )
    assert out.diagnostics["partial_closes"] == 0
    assert out.diagnostics["partial_close_modelled"] is True
    assert out.diagnostics["close_percentage"] == "100"
    assert out.summary["total_trades"] == 1
    assert out.trades[0].exit_reason == "exit_signal"
    assert out.trades[0].pnl == Decimal("-150.00")  # (99-102)*50


# --------------------------------------------------------------------------- #
# Partial close — positive                                                    #
# --------------------------------------------------------------------------- #


def test_partial_close_50_percent_realizes_a_lot_and_holds_remainder() -> None:
    # Exit signal at 99 closes 50% (25 units) as a partial lot; the remainder (25) holds to
    # end-of-data at bar 23's close (103, above the moved breakeven stop so it does not stop).
    followups = [_EXIT_SIGNAL, _fu(23, "103", "104", "103", "103")]
    out = _run(
        _config(close_percentage="50", partial_aftermath="move_stop_to_entry"),
        _long_then(followups),
    )
    assert out.diagnostics["partial_closes"] == 1
    assert out.summary["total_trades"] == 2
    assert out.trades[0].exit_reason == "partial_exit"
    assert out.trades[0].pnl == Decimal("-75.00")  # (99-102)*25
    assert out.trades[1].exit_reason == "end_of_data"
    assert out.trades[1].pnl == Decimal("25.00")  # remainder (103-102)*25
    partials = _events(out, "position_partial_close")
    assert partials and partials[0]["closed_fraction"] == "0.5"
    assert partials[0]["remaining_size"] == "25.0"


def test_move_stop_to_entry_breakevens_the_remainder() -> None:
    # After the 50% partial the remainder's stop is moved to the entry (102); bar 23 dips to
    # low 100 <= 102 -> the remainder stops out at breakeven (102, pnl 0). Without the moved
    # stop (with_stop OFF) the remainder would have no stop at all.
    followups = [_EXIT_SIGNAL, _fu(23, "101", "101", "100", "101")]
    out = _run(
        _config(close_percentage="50", partial_aftermath="move_stop_to_entry"),
        _long_then(followups),
    )
    assert out.summary["total_trades"] == 2
    assert out.trades[1].exit_reason == "stop_loss"
    assert out.trades[1].exit_price == Decimal("102.00")  # breakeven
    assert out.trades[1].pnl == Decimal("0.00")


def test_close_all_aftermath_collapses_to_a_full_close() -> None:
    # close_all: the exit signal closes 100% even though close_percentage is 50 -> ONE trade.
    followups = [_EXIT_SIGNAL, _fu(23, "100", "100", "100", "100")]
    close_all = _run(
        _config(close_percentage="50", partial_aftermath="close_all"), _long_then(followups)
    )
    assert close_all.diagnostics["partial_closes"] == 0
    assert close_all.summary["total_trades"] == 1
    assert close_all.trades[0].exit_reason == "exit_signal"

    # The SAME bars with move_stop_to_entry partial-close instead -> TWO trades (distinguishes).
    move_stop = _run(
        _config(close_percentage="50", partial_aftermath="move_stop_to_entry"),
        _long_then(followups),
    )
    assert move_stop.diagnostics["partial_closes"] == 1
    assert move_stop.summary["total_trades"] == 2


# --------------------------------------------------------------------------- #
# trailing_stop aftermath without a protection trailing config — still         #
# fails closed (F-07f positive/effect cases live in                            #
# test_backtest_leverage_trailing.py, which sets up a real trailing config)    #
# --------------------------------------------------------------------------- #


def test_partial_trailing_stop_aftermath_without_protection_config_fails_closed() -> None:
    # This fixture's protection_stop_logic carries no trailing_stop rule at all -> the
    # aftermath has no trailing distance/activation parameters to reuse -> unsupported.
    out = _run(
        _config(close_percentage="50", partial_aftermath="trailing_stop"),
        _long_then([_EXIT_SIGNAL, _fu(23, "100", "100", "100", "100")]),
    )
    assert out.diagnostics["partial_close_modelled"] is False
    assert out.summary["total_trades"] == 0
    assert "partial_close_unsupported:trailing_stop" in out.diagnostics["warnings"]


# --------------------------------------------------------------------------- #
# lock_in_profit aftermath — now modelled (F-07f closes the F-07c boundary)    #
# --------------------------------------------------------------------------- #


def test_partial_lock_in_profit_aftermath_locks_the_exit_price() -> None:
    # F-07f: lock_in_profit moves the remainder's stop to the price at partial-close time
    # (99, the EXIT_SIGNAL close) instead of failing closed. Bar 23 stays flat at 100
    # (above the locked 99 level) so the remainder rides to end-of-data unstopped.
    out = _run(
        _config(close_percentage="50", partial_aftermath="lock_in_profit"),
        _long_then([_EXIT_SIGNAL, _fu(23, "100", "100", "100", "100")]),
    )
    assert out.diagnostics["partial_close_modelled"] is True
    assert out.diagnostics["lock_in_locks"] == 1
    assert out.summary["total_trades"] == 2
    assert out.trades[0].exit_reason == "partial_exit"
    assert out.trades[1].exit_reason == "end_of_data"
    assert out.trades[1].pnl == Decimal("-50.00")  # remainder (100-102)*25


def test_full_close_with_trailing_aftermath_still_runs() -> None:
    # close_percentage == 100: no remainder ever, so the trailing aftermath is irrelevant and
    # the run is NOT blocked (a full close executes normally).
    out = _run(
        _config(close_percentage="100", partial_aftermath="trailing_stop"),
        _long_then([_EXIT_SIGNAL, _fu(23, "100", "100", "100", "100")]),
    )
    assert out.diagnostics["partial_close_modelled"] is True
    assert out.summary["total_trades"] == 1
    assert out.diagnostics["partial_closes"] == 0
