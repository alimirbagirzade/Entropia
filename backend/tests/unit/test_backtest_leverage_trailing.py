"""F-07f — leverage mode + trailing-stop profit-lock engine tests (Master Ref §9.2/§10.2).

Two independent behaviours land together:

* Leverage (§10.2): a strategy's ``position_sizing.leverage`` multiplier scales computed
  position size (and therefore notional/exposure) — 'No Leverage' normalizes to 1x,
  'Isolated' applies the saved positive multiplier, 'Cross' needs a portfolio-level risk
  model the engine does not implement and FAILS CLOSED (opens no position).
* Trailing-stop profit lock (§9.2 "Activate After Profit %", ``TrailingStop.
  lock_in_percentage``): the trailing rule contributes NO stop level until the position's
  profit reaches the activation threshold; once reached, ``trail_anchor`` — already a
  monotonic favourable-extreme ratchet — derives a trailing level that can only tighten,
  never loosen ("locks in", never retreats).

This slice also closes the F-07c boundary left by ``test_backtest_partial_close.py``:
``lock_in_profit`` (always modelled — no extra config) and ``trailing_stop`` (modelled
WHEN protection-level trailing is configured/enabled) partial-close aftermaths.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    EngineOutput,
    _Position,
    _trailing_activated,
    _trailing_level,
    leverage_is_modelled,
    run_engine,
)
from entropia.domain.strategy.config import StrategyConfig

_ZERO_COST = {"slippage_mode": "percentage_slippage", "slippage_value": "0"}


def _config(
    *,
    base_position_size: str = "10",
    leverage_mode: str = "isolated",
    leverage: str = "1",
    trail_percentage: str | None = None,
    lock_in_percentage: str | None = None,
    close_percentage: str = "100",
    partial_aftermath: str = "move_stop_to_entry",
) -> StrategyConfig:
    """A minimal VALID StrategyConfig; only the fields the engine reads matter.

    Zero costs so a fill lands exactly on the resolved price. ``trail_percentage`` /
    ``lock_in_percentage`` set (both required together) enable protection-level trailing;
    otherwise protection is empty (no percentage/absolute/trailing stop at all)."""
    protection: dict[str, Any] = {}
    if trail_percentage is not None:
        protection["trailing_stop"] = {
            "enabled": True,
            "trail_percentage": trail_percentage,
            "lock_in_percentage": lock_in_percentage,
        }
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Leverage/Trailing Fixture",
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
            "position_sizing": {
                "method": "base_position_size",
                "base_position_size": base_position_size,
                "leverage_mode": leverage_mode,
                "leverage": leverage,
            },
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


def _run(config: StrategyConfig, bars: list[dict[str, Any]], *, batch: int = 8) -> EngineOutput:
    def batched() -> Iterator[list[dict[str, Any]]]:
        for start in range(0, len(bars), batch):
            yield bars[start : start + batch]

    return run_engine(strategy_config=config, bar_batches=batched(), execution_key="exec_key_test")


# --------------------------------------------------------------------------- #
# Leverage — predicate                                                        #
# --------------------------------------------------------------------------- #


def test_leverage_predicate_no_leverage_and_isolated_positive_are_modelled() -> None:
    assert leverage_is_modelled(_config(leverage_mode="no_leverage", leverage="1"))
    assert leverage_is_modelled(_config(leverage_mode="isolated", leverage="3"))


def test_leverage_predicate_cross_is_not_modelled() -> None:
    assert not leverage_is_modelled(_config(leverage_mode="cross", leverage="2"))


# --------------------------------------------------------------------------- #
# Leverage — positive: 2x leverage doubles size / notional exposure           #
# --------------------------------------------------------------------------- #


def test_leverage_2x_doubles_position_size_and_notional() -> None:
    baseline = _run(
        _config(leverage_mode="isolated", leverage="1"),
        _long_then([_fu(22, "102", "102", "102", "102")]),
    )
    leveraged = _run(
        _config(leverage_mode="isolated", leverage="2"),
        _long_then([_fu(22, "102", "102", "102", "102")]),
    )
    assert leveraged.diagnostics["leverage_modelled"] is True
    assert leveraged.diagnostics["leverage_multiplier"] == "2"
    # base_position_size=10 units @ entry 102: 1x -> 1020 notional, 2x -> 2040 notional.
    base_notional = Decimal(baseline.summary["initial_capital"]) - baseline.summary["final_equity"]
    lev_notional = Decimal(leveraged.summary["initial_capital"]) - leveraged.summary["final_equity"]
    # Both bars are flat @102 after entry so neither position has moved -> 0 pnl either way;
    # assert directly on the decision-trace fill size instead of inferring from equity.
    assert base_notional == Decimal("0.00")
    assert lev_notional == Decimal("0.00")
    base_fill = next(e for e in baseline.signal_events if e.event_type == "entry_fill")
    lev_fill = next(e for e in leveraged.signal_events if e.event_type == "entry_fill")
    assert Decimal(lev_fill.detail["size"]) == Decimal(base_fill.detail["size"]) * 2
    assert Decimal(lev_fill.detail["size"]) == Decimal("20")


def test_leverage_no_leverage_mode_normalizes_to_1x_regardless_of_saved_value() -> None:
    # A saved leverage=5 is ignored under 'no_leverage' -> normalized to 1x.
    out = _run(
        _config(leverage_mode="no_leverage", leverage="5"),
        _long_then([_fu(22, "102", "102", "102", "102")]),
    )
    assert out.diagnostics["leverage_multiplier"] == "1"
    fill = next(e for e in out.signal_events if e.event_type == "entry_fill")
    assert Decimal(fill.detail["size"]) == Decimal("10")


# --------------------------------------------------------------------------- #
# Leverage — negative: 'cross' fails closed                                   #
# --------------------------------------------------------------------------- #


def test_leverage_cross_mode_opens_no_position() -> None:
    out = _run(
        _config(leverage_mode="cross", leverage="2"),
        _long_then([_fu(22, "102", "102", "102", "102")]),
    )
    assert out.diagnostics["leverage_modelled"] is False
    assert out.summary["total_trades"] == 0
    assert "leverage_unsupported:cross" in out.diagnostics["warnings"]


# --------------------------------------------------------------------------- #
# Trailing profit-lock — pure predicate (Master Ref §9.2 worked example)      #
# --------------------------------------------------------------------------- #


def _position(*, entry: str, anchor: str, trail_pct: str, lock_in_pct: str) -> _Position:
    return _Position(
        position_seq=1,
        entry_bar_seq=0,
        direction="long",
        entry_time="t",
        entry_price=Decimal(entry),
        size=Decimal("1"),
        pct_stop=None,
        abs_stop=None,
        trail_pct=Decimal(trail_pct) / 100,
        trail_anchor=Decimal(anchor),
        entry_notional=Decimal("0"),
        trail_lock_in_pct=Decimal(lock_in_pct) / 100,
    )


def test_trailing_not_activated_below_lock_in_threshold() -> None:
    # Entry 100, lock-in 2% -> activates at 102. Anchor only reached 101 (1% profit).
    pos = _position(entry="100", anchor="101", trail_pct="0.8", lock_in_pct="2.0")
    assert not _trailing_activated(pos)
    assert _trailing_level(pos) is None


def test_trailing_activates_and_matches_master_ref_worked_example() -> None:
    # Master Ref §9.2 example: entry 100, activate after 2% profit (102), trail 0.8%; once
    # price reaches 105 the stop sits at ~104.16.
    pos = _position(entry="100", anchor="105", trail_pct="0.8", lock_in_pct="2.0")
    assert _trailing_activated(pos)
    assert _trailing_level(pos) == Decimal("104.16000")


def test_trailing_level_never_retreats_as_anchor_advances() -> None:
    # A ratchet: the anchor only moves toward one direction (see the bar loop's max()), so
    # a later, LOWER anchor value is not a state this position can reach -- but a level
    # computed from a higher anchor is always >= one computed from any earlier anchor.
    early_pos = _position(entry="100", anchor="103", trail_pct="0.8", lock_in_pct="2.0")
    later_pos = _position(entry="100", anchor="105", trail_pct="0.8", lock_in_pct="2.0")
    early = _trailing_level(early_pos)
    later = _trailing_level(later_pos)
    assert early is not None
    assert later is not None
    assert later > early


# --------------------------------------------------------------------------- #
# Trailing profit-lock — full engine run, positive                            #
# --------------------------------------------------------------------------- #


def test_trailing_lock_in_activates_then_locks_a_profitable_stop() -> None:
    # Entry @102 (breakout). Bar 22 rises to 103 but stays below the 2% activation
    # threshold (104.04) -> trailing contributes NOTHING yet (no stop rule at all is
    # configured besides trailing), so a dip would NOT have stopped it out this bar.
    # Bar 23 pushes to a high of 105 (>= 104.04) -> ACTIVATES; level = 105 * 0.992 =
    # 104.16, and bar 23's own low (104.5) stays above it (survives the same bar).
    # Bar 24's high (104) is LOWER than the anchor (105) -> the anchor does not retreat;
    # its low (103) touches the still-104.16 level -> stops out there, locking in profit.
    out = _run(
        _config(trail_percentage="0.8", lock_in_percentage="2.0"),
        _long_then(
            [
                _fu(22, "102", "103", "101", "102"),
                _fu(23, "102", "105", "104.5", "104"),
                _fu(24, "104", "104", "103", "103"),
            ]
        ),
    )
    assert out.summary["total_trades"] == 1
    trade = out.trades[0]
    assert trade.exit_reason == "stop_loss"
    assert trade.exit_price == Decimal("104.16")
    assert trade.pnl == Decimal("21.60")  # (104.16 - 102) * 10


def test_trailing_lock_in_never_engages_below_activation_threshold() -> None:
    # A very high lock-in threshold (50%) is never reached by this price path -> the
    # trailing rule never contributes a stop level, so the position rides to end-of-data
    # rather than trail-stopping on the way up.
    out = _run(
        _config(trail_percentage="0.8", lock_in_percentage="50.0"),
        _long_then(
            [
                _fu(22, "102", "105", "101", "104"),
                _fu(23, "104", "108", "103", "106"),
                _fu(24, "106", "106", "106", "106"),
            ]
        ),
    )
    assert out.summary["total_trades"] == 1
    assert out.trades[0].exit_reason == "end_of_data"
    assert out.diagnostics["trailing_lock_in_active"] is True
    assert out.diagnostics["lock_in_locks"] == 0


# --------------------------------------------------------------------------- #
# F-07c boundary closure — partial-close aftermaths (was fail-closed)         #
# --------------------------------------------------------------------------- #


def test_lock_in_profit_aftermath_is_now_modelled_and_locks_the_exit_price() -> None:
    # Exit signal at bar 22 closes 50% at 99 (a losing exit vs entry 102); lock_in_profit
    # moves the remainder's stop to that SAME price (99) rather than failing closed.
    out = _run(
        _config(close_percentage="50", partial_aftermath="lock_in_profit"),
        _long_then(
            [
                _fu(22, "100", "100", "99", "99"),  # exit signal (close < window low)
                _fu(23, "99", "99", "98", "98"),  # dips to the locked level -> stops there
            ]
        ),
    )
    assert out.diagnostics["partial_close_modelled"] is True
    assert out.diagnostics["lock_in_locks"] == 1
    assert out.summary["total_trades"] == 2
    assert out.trades[0].exit_reason == "partial_exit"
    assert out.trades[1].exit_reason == "stop_loss"
    assert out.trades[1].exit_price == Decimal("99.00")
    assert out.trades[1].pnl == Decimal("-15.00")  # (99-102)*5


def test_trailing_stop_aftermath_requires_protection_trailing_configured() -> None:
    # Negative: 'trailing_stop' aftermath with NO protection-level trailing_stop rule has
    # no trailing parameters to reuse -> still fails closed (F-07c/f boundary).
    out = _run(
        _config(close_percentage="50", partial_aftermath="trailing_stop"),
        _long_then([_fu(22, "100", "100", "99", "99")]),
    )
    assert out.diagnostics["partial_close_modelled"] is False
    assert out.summary["total_trades"] == 0
    assert "partial_close_unsupported:trailing_stop" in out.diagnostics["warnings"]


def test_trailing_stop_aftermath_force_activates_when_trailing_configured() -> None:
    # Positive: protection-level trailing IS configured (lock-in 2%, not yet reached at
    # the 99 exit price) -> the aftermath force-activates it immediately on the
    # remainder rather than waiting for the (never-to-be-reached, price is falling)
    # protection-level threshold.
    out = _run(
        _config(
            close_percentage="50",
            partial_aftermath="trailing_stop",
            trail_percentage="0.5",
            lock_in_percentage="2.0",
        ),
        _long_then(
            [
                _fu(22, "100", "100", "99", "99"),  # partial exit @99, force-activates trailing
                _fu(23, "99", "99", "99", "99"),  # flat: anchor stays >= entry*(1+2%) via force
            ]
        ),
    )
    assert out.diagnostics["partial_close_modelled"] is True
    assert out.diagnostics["lock_in_locks"] == 1
    assert out.summary["total_trades"] == 2
    assert out.trades[0].exit_reason == "partial_exit"
    # Force-activation sets trail_anchor to entry*(1+2%) = 104.04; trail level =
    # 104.04 * (1 - 0.5%) = 103.5198, quantized to money (2dp) = 103.52 -> bar 23's flat
    # close (99) is BELOW it, so the remainder should already be stopped out intrabar at
    # that forced level.
    assert out.trades[1].exit_reason == "stop_loss"
    assert out.trades[1].exit_price == Decimal("103.52")
