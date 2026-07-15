"""F-08 — Logic-Based Stop combination engine (unit, pure, no DB).

Covers ``_resolve_stop`` — the Any/All trigger requirement + the four conflict /
priority resolutions (Master Ref §9.1/§9.3) — with +/- (fires / does not fire)
cases for every combination, plus an engine-level proof that ``all_active`` changes
the actual stop-out behaviour through ``run_engine``. Logic-block firing is exercised
by feeding ``_resolve_stop`` the resolved trigger set (the same list the engine builds
from the stop evaluators); a real pinned-package end-to-end run lives in the
integration suite.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    _Bar,
    _Position,
    _resolve_stop,
    _StopOutcome,
    run_engine,
)
from entropia.domain.strategy.config import StrategyConfig

_ENTRY = Decimal("100")


def _protection(**kwargs: Any) -> dict[str, Any]:
    return kwargs


def _cfg(protection: dict[str, Any] | None) -> StrategyConfig:
    """A minimal VALID StrategyConfig; ``_resolve_stop`` only reads protection_stop_logic."""
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Logic Stop Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
                "initial_capital": "10000.00",
                "execution": {
                    "entry_timing": "current_candle_close",
                    "exit_timing": "current_candle_close",
                },
                "order_config": {"type": "market_order"},
                "costs": {"slippage_mode": "percentage_slippage", "slippage_value": "0"},
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
                "close_percentage": "100",
            },
            "protection_stop_logic": protection,
            "position_sizing": {"method": "base_position_size", "base_position_size": "50"},
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


def _pos(
    *,
    direction: str = "long",
    pct: str | None = None,
    absolute: str | None = None,
) -> _Position:
    return _Position(
        direction=direction,
        entry_time="2024-01-01T00:00:00Z",
        entry_price=_ENTRY,
        size=Decimal("1"),
        pct_stop=Decimal(pct) if pct is not None else None,
        abs_stop=Decimal(absolute) if absolute is not None else None,
        trail_pct=None,
        trail_anchor=_ENTRY,
        entry_notional=_ENTRY,
    )


def _bar(low: str, close: str = "98") -> _Bar:
    return _Bar(
        timestamp="2024-01-22T00:00:00Z",
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("10"),
    )


def _resolve(protection: dict[str, Any], pos: _Position, bar: _Bar, *, triggered=(), enabled=()):
    return _resolve_stop(
        _cfg(protection),
        pos,
        bar,
        logic_enabled=list(enabled),
        logic_triggered=list(triggered),
    )


# --------------------------------------------------------------------------- #
# any_active + most_conservative (the DEFAULT — must equal pre-F-08 behaviour) #
# --------------------------------------------------------------------------- #


def test_any_active_conservative_fires_on_a_single_touched_price_stop() -> None:
    protection = _protection(percentage_stop={"enabled": True, "loss_percentage": "1.0"})
    out = _resolve(protection, _pos(pct="99", absolute="98"), _bar(low="98.5"))
    assert isinstance(out, _StopOutcome)
    assert out.executed_key == "percentage"
    assert out.price == Decimal("99")
    assert out.triggered == ("percentage",)


def test_any_active_conservative_picks_the_tightest_of_two_touched_stops() -> None:
    protection = _protection(percentage_stop={"enabled": True, "loss_percentage": "1.0"})
    out = _resolve(protection, _pos(pct="99", absolute="98"), _bar(low="97"))
    assert out is not None
    # Tightest (closest to entry) wins — the percentage level 99, not the absolute 98.
    assert out.executed_key == "percentage"
    assert out.price == Decimal("99")
    assert set(out.triggered) == {"percentage", "absolute"}


def test_no_rule_touched_does_not_fire() -> None:
    protection = _protection(percentage_stop={"enabled": True, "loss_percentage": "1.0"})
    assert _resolve(protection, _pos(pct="99", absolute="98"), _bar(low="99.5")) is None


# --------------------------------------------------------------------------- #
# all_active (AND): fires ONLY when EVERY enabled rule triggers this bar        #
# --------------------------------------------------------------------------- #


def test_all_active_does_not_fire_when_only_one_of_two_stops_triggers() -> None:
    protection = _protection(stop_trigger_requirement="all_active")
    out = _resolve(protection, _pos(pct="99", absolute="98"), _bar(low="98.5"))
    assert out is None  # absolute (98) not touched -> AND unsatisfied


def test_all_active_fires_when_every_stop_triggers() -> None:
    protection = _protection(stop_trigger_requirement="all_active")
    out = _resolve(protection, _pos(pct="99", absolute="98"), _bar(low="97"))
    assert out is not None
    assert set(out.triggered) == {"percentage", "absolute"}


# --------------------------------------------------------------------------- #
# priority_order / record_all_execute_highest                                  #
# --------------------------------------------------------------------------- #


def test_priority_order_custom_executes_the_highest_priority_triggered_rule() -> None:
    protection = _protection(
        stop_conflict_resolution="priority_order",
        stop_priority_order=["absolute", "percentage"],
    )
    out = _resolve(protection, _pos(pct="99", absolute="98"), _bar(low="97"))
    assert out is not None
    assert out.executed_key == "absolute"  # first in the explicit priority list
    assert out.price == Decimal("98")


def test_priority_order_default_prefers_percentage_over_absolute() -> None:
    protection = _protection(stop_conflict_resolution="priority_order")
    out = _resolve(protection, _pos(pct="99", absolute="98"), _bar(low="97"))
    assert out is not None
    assert out.executed_key == "percentage"  # canonical §9.2: percentage before absolute


def test_record_all_execute_highest_records_every_triggered_rule() -> None:
    protection = _protection(stop_conflict_resolution="record_all_execute_highest")
    out = _resolve(protection, _pos(pct="99", absolute="98"), _bar(low="97"))
    assert out is not None
    assert out.executed_key == "percentage"
    assert set(out.triggered) == {"percentage", "absolute"}


# --------------------------------------------------------------------------- #
# first_trigger_wins over OHLCV resolves to conservative + flags it            #
# --------------------------------------------------------------------------- #


def test_first_trigger_wins_falls_back_to_conservative_and_flags_it() -> None:
    protection = _protection(stop_conflict_resolution="first_trigger_wins")
    out = _resolve(protection, _pos(pct="99", absolute="98"), _bar(low="97"))
    assert out is not None
    assert out.approximated_first is True
    assert out.executed_key == "percentage"  # conservative model


# --------------------------------------------------------------------------- #
# Logic-Based Stop blocks (signal against the open position -> stop at close)   #
# --------------------------------------------------------------------------- #


def test_logic_block_fires_at_bar_close_when_signalled_against_position() -> None:
    out = _resolve(
        _protection(),
        _pos(),
        _bar(low="100", close="97.5"),
        enabled=["logic:s1"],
        triggered=["logic:s1"],
    )
    assert out is not None
    assert out.executed_key == "logic:s1"
    assert out.price == Decimal("97.5")  # signal-confirmed bar close


def test_logic_block_enabled_but_not_triggered_does_not_fire() -> None:
    out = _resolve(_protection(), _pos(), _bar(low="100", close="99"), enabled=["logic:s1"])
    assert out is None


def test_logic_stop_can_be_more_conservative_than_a_touched_price_stop() -> None:
    # premise broke early: the logic stop closes at 99.8 (0.2 from entry) BEFORE the price
    # falls to the 99 percentage level (1.0 from entry) — conservative model prefers it.
    protection = _protection(percentage_stop={"enabled": True, "loss_percentage": "1.0"})
    out = _resolve(
        protection,
        _pos(pct="99"),
        _bar(low="97", close="99.8"),
        enabled=["logic:s1"],
        triggered=["logic:s1"],
    )
    assert out is not None
    assert out.executed_key == "logic:s1"
    assert out.price == Decimal("99.8")


def test_all_active_with_price_and_logic_requires_both() -> None:
    protection = _protection(stop_trigger_requirement="all_active")
    pos = _pos(pct="99")
    # price stop touched but logic NOT triggered -> AND unsatisfied.
    assert _resolve(protection, pos, _bar(low="97", close="99"), enabled=["logic:s1"]) is None
    # both -> fires.
    out = _resolve(
        protection, pos, _bar(low="97", close="99"), enabled=["logic:s1"], triggered=["logic:s1"]
    )
    assert out is not None
    assert set(out.triggered) == {"percentage", "logic:s1"}


def test_short_position_price_stop_triggers_on_the_high() -> None:
    protection = _protection(percentage_stop={"enabled": True, "loss_percentage": "1.0"})
    pos = _Position(
        direction="short",
        entry_time="2024-01-01T00:00:00Z",
        entry_price=_ENTRY,
        size=Decimal("1"),
        pct_stop=Decimal("101"),
        abs_stop=None,
        trail_pct=None,
        trail_anchor=_ENTRY,
        entry_notional=_ENTRY,
    )
    bar = _Bar(
        timestamp="2024-01-22T00:00:00Z",
        open=Decimal("100"),
        high=Decimal("102"),  # >= 101 stop
        low=Decimal("100"),
        close=Decimal("101.5"),
        volume=Decimal("10"),
    )
    out = _resolve_stop(_cfg(protection), pos, bar, logic_enabled=[], logic_triggered=[])
    assert out is not None
    assert out.executed_key == "percentage"
    assert out.price == Decimal("101")


# --------------------------------------------------------------------------- #
# Engine-level: all_active changes the actual stop-out through run_engine       #
# --------------------------------------------------------------------------- #


def _engine_cfg(*, requirement: str) -> StrategyConfig:
    return _cfg(
        _protection(
            percentage_stop={"enabled": True, "loss_percentage": "1.0"},
            absolute_stop={"enabled": True, "absolute_price": "80"},
            stop_trigger_requirement=requirement,
        )
    )


def _breakout_then_partial_drop() -> list[dict[str, Any]]:
    bars = [
        {
            "timestamp": f"2024-01-{i + 1:02d}T00:00:00Z",
            "open": "100",
            "high": "100",
            "low": "100",
            "close": "100",
            "volume": "10",
        }
        for i in range(20)
    ]
    bars.append(
        {
            "timestamp": "2024-01-21T00:00:00Z",
            "open": "100",
            "high": "102",
            "low": "100",
            "close": "102",
            "volume": "10",
        }
    )  # breakout -> long
    # low 90 trips the 1% percentage stop (99) but NOT the absolute stop (80).
    bars.append(
        {
            "timestamp": "2024-01-22T00:00:00Z",
            "open": "102",
            "high": "102",
            "low": "90",
            "close": "95",
            "volume": "10",
        }
    )
    return bars


def _run(cfg: StrategyConfig, bars: list[dict[str, Any]]):
    def _batched():
        for start in range(0, len(bars), 8):
            yield bars[start : start + 8]

    return run_engine(strategy_config=cfg, bar_batches=_batched(), execution_key="ek")


def test_engine_any_active_stops_out_on_the_single_touched_stop() -> None:
    out = _run(_engine_cfg(requirement="any_active"), _breakout_then_partial_drop())
    assert out.summary["total_trades"] == 1
    assert out.summary["total_stops"] == 1
    assert out.diagnostics["stop_trigger_requirement"] == "any_active"
    assert out.diagnostics["logic_stop_blocks"] == 0


def test_engine_all_active_does_not_stop_until_every_stop_triggers() -> None:
    # Same bars: only the percentage stop is touched (low 90 > absolute 80), so all_active
    # does NOT close the position — the run ends holding it (no stop-out trade).
    out = _run(_engine_cfg(requirement="all_active"), _breakout_then_partial_drop())
    assert out.summary["total_stops"] == 0
    assert out.diagnostics["stop_trigger_requirement"] == "all_active"
