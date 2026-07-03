"""Engine condition-gating unit tests (post-V1 (b)) — DB-free.

Proves the engine drives entry only when an indicator block's native trigger fires
AND its nested threshold conditions are satisfied. The plan is built directly (the
DB-backed resolution is covered in tests/integration/test_condition_plan_resolution.py)."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import EngineOutput, run_engine
from entropia.domain.backtest.indicators import (
    BUILTIN_ENTRY_MODEL,
    ConditionSpec,
    IndicatorPlan,
    IndicatorSpec,
    SignalRule,
)
from entropia.domain.strategy.config import StrategyConfig


def _config() -> StrategyConfig:
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Condition Gating Fixture",
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
                        "trigger_source": "indicator_native_trigger_plus_condition",
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


def _bar(ts: str, close: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": close, "high": close, "low": close, "close": close}


def _bars(closes: list[str]) -> list[dict[str, Any]]:
    return [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", c) for i, c in enumerate(closes)]


def _batched(bars: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(bars), size):
        yield bars[start : start + size]


def _gated_plan(threshold: str, *, source: str = "close", key: str = "cond.above") -> IndicatorPlan:
    cond = ConditionSpec(
        condition_block_id="c1",
        canonical_key=key,
        source=source,
        threshold=Decimal(threshold),
        requirement="required",
        validity="until_opposite_signal",
    )
    spec = IndicatorSpec(
        block_id="blk_1",
        canonical_key="ta.sma",
        length=3,
        direction="long_and_short",
        requirement="required",
        validity="until_opposite_signal",
        conditions=(cond,),
    )
    return IndicatorPlan(
        entry_rule=SignalRule(rule="required_indicator_blocks_only"), entry_specs=(spec,)
    )


def _run(plan: IndicatorPlan, closes: list[str], batch: int = 8) -> EngineOutput:
    return run_engine(
        strategy_config=_config(),
        bar_batches=_batched(_bars(closes), batch),
        execution_key="k",
        indicator_plan=plan,
    )


# A clean SMA(3) upward cross: flat at 10 then a step to 12 crosses the MA (bar index 6).
_LONG_CROSS = ["10", "10", "10", "10", "10", "10", "12", "12", "12"]


def test_condition_gate_allows_entry_when_satisfied() -> None:
    out = _run(_gated_plan("10"), _LONG_CROSS)  # close 12 > 10 at the cross bar
    assert out.diagnostics["entry_model"] == BUILTIN_ENTRY_MODEL
    assert out.diagnostics["condition_blocks"] == 1
    assert out.summary["total_trades"] == 1
    assert out.trades[0].direction == "long"


def test_condition_gate_blocks_entry_when_unsatisfied() -> None:
    out = _run(_gated_plan("15"), _LONG_CROSS)  # close 12 is NOT above 15 -> gated
    assert out.diagnostics["entry_model"] == BUILTIN_ENTRY_MODEL  # still real compute
    assert out.diagnostics["condition_blocks"] == 1
    assert out.summary["total_trades"] == 0


def test_indicator_output_source_gate() -> None:
    # SMA(3) at/after the cross bar is 10.67 -> 11.33 -> 12 (max 12). A threshold of 10
    # opens the gate at the cross; a threshold of 13 is never reached so it stays shut.
    allowed = _run(_gated_plan("10", source="indicator_output"), _LONG_CROSS)
    blocked = _run(_gated_plan("13", source="indicator_output"), _LONG_CROSS)
    assert allowed.summary["total_trades"] == 1
    assert blocked.summary["total_trades"] == 0


def test_gated_run_is_deterministic_across_batch_sizes() -> None:
    a = _run(_gated_plan("10"), _LONG_CROSS, batch=8)
    b = _run(_gated_plan("10"), _LONG_CROSS, batch=3)
    assert a.summary == b.summary
    assert [t.pnl for t in a.trades] == [t.pnl for t in b.trades]
