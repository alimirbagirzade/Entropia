"""F-07i sub-slice A — the tick-data requirement predicate (Master Ref §6.4/§11.2).

'Use Tick Data' saves ``intrabar_policy.tick_policy`` (None/Yes/No ->
inherit/require/disable). ``tick_data_required`` is the single engine-owned source
of truth for "this strategy DEMANDS an intrabar tick path"; the readiness command
imports it so Ready Check's ``TICK_DATA_UNAVAILABLE`` blocker and the engine's later
intrabar gate (sub-slice B) never diverge. Only ``require`` demands tick data —
``inherit`` (None) falls back to the conservative OHLCV resolution and ``disable``
(No) forces OHLCV even when tick data exists.
"""

from __future__ import annotations

from typing import Any

from entropia.domain.backtest.engine import tick_data_required
from entropia.domain.strategy.config import StrategyConfig


def _config(*, tick_policy: str = "inherit") -> StrategyConfig:
    """A minimal VALID StrategyConfig; only ``intrabar_policy.tick_policy`` matters here."""
    payload: dict[str, Any] = {
        "strategy_root_id": "strat_root_1",
        "display_name": "Tick Data Fixture",
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
            "intrabar_policy": {"tick_policy": tick_policy},
            "funding": {"enabled": False},
        },
        "position_entry_logic": {
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
        "position_exit_logic": {},
        "protection_stop_logic": {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}},
        "position_sizing": {"method": "base_position_size", "base_position_size": "1.0"},
        "restrictions_filters": {},
        "conflict_position_handling": {},
    }
    return StrategyConfig.model_validate(payload)


def test_require_demands_tick_data() -> None:
    # 'Use Tick Data = Yes' -> tick_policy 'require' -> the strategy demands tick data.
    assert tick_data_required(_config(tick_policy="require")) is True


def test_inherit_and_disable_never_demand_tick_data() -> None:
    # 'None' (inherit) falls back to conservative OHLCV; 'No' (disable) forces OHLCV.
    assert tick_data_required(_config(tick_policy="inherit")) is False
    assert tick_data_required(_config(tick_policy="disable")) is False
