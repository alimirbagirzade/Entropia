"""Engine plan-path unit tests (post-V1 Slice C) — DB-free.

Proves the engine drives entry/exit from a real ``IndicatorPlan`` (built-in TA native
triggers) — the only entry path a production RUN can take. An UNRESOLVED plan is refused
upstream (F-06: a Ready Check blocker + a worker fail-closed re-check), never silently
substituted with a proxy; this module pins the contract those gates read rather than the
substitution itself (F-24). The plan is constructed directly (the DB-backed resolution is
covered separately in tests/integration/test_indicator_plan_resolution.py)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from entropia.domain.backtest.engine import EngineOutput, run_engine
from entropia.domain.backtest.indicators import (
    BUILTIN_ENTRY_MODEL,
    IndicatorPlan,
    IndicatorSpec,
    SignalRule,
)
from entropia.domain.strategy.config import StrategyConfig


def _config(*, direction: str = "long_and_short", with_stop: bool = False) -> StrategyConfig:
    protection: dict[str, Any] = (
        {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}} if with_stop else {}
    )
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Plan Fixture",
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


def _bar(ts: str, close: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": close, "high": close, "low": close, "close": close}


def _bars(closes: list[str]) -> list[dict[str, Any]]:
    return [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", c) for i, c in enumerate(closes)]


def _batched(bars: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(bars), size):
        yield bars[start : start + size]


def _sma_plan(
    *, validity: str = "until_opposite_signal", unresolved: tuple[str, ...] = ()
) -> IndicatorPlan:
    spec = IndicatorSpec(
        block_id="blk_1",
        canonical_key="ta.sma",
        length=3,
        direction="long_and_short",
        requirement="required",
        validity=validity,
    )
    return IndicatorPlan(
        entry_rule=SignalRule(rule="required_indicator_blocks_only"),
        entry_specs=(spec,),
        unresolved=unresolved,
    )


def _run(
    config: StrategyConfig, bars: list[dict[str, Any]], plan: IndicatorPlan | None, batch: int = 8
) -> EngineOutput:
    return run_engine(
        strategy_config=config,
        bar_batches=_batched(bars, batch),
        execution_key="k",
        indicator_plan=plan,
    )


# A clean SMA(3) upward cross: flat at 10 (no signal) then a step to 12 crosses the MA.
_LONG_CROSS = ["10", "10", "10", "10", "10", "10", "12", "12", "12"]


def test_plan_drives_a_real_indicator_entry() -> None:
    out = _run(_config(), _bars(_LONG_CROSS), _sma_plan())
    assert out.diagnostics["entry_model"] == BUILTIN_ENTRY_MODEL
    assert out.diagnostics["indicator_blocks"] == 1
    assert out.summary["total_trades"] == 1
    trade = out.trades[0]
    assert trade.direction == "long"
    assert trade.exit_reason == "end_of_data"  # no opposite/stop -> closed at end
    assert trade.entry_time == "2024-01-07T00:00:00Z"  # cross bar (7th)


def test_an_unresolved_plan_is_refused_before_the_engine_is_reached() -> None:
    """An unresolved plan carries the two facts the upstream gates fail closed on (F-06).

    This REPLACES a test that asserted the engine substitutes a labelled breakout proxy for an
    unresolved plan — F-24: that is precisely the behaviour the product ruled out, so the suite
    must not lock it in. Production can no longer reach the proxy: Ready Check raises
    STRATEGY_INDICATOR_UNRESOLVED so admission refuses to queue the run, and the worker
    re-checks ``not plan.has_entry or plan.unresolved`` and fails closed with
    RUN_FAILED_UNRESOLVED_DEPENDENCY before the engine is ever called. Both gates are covered
    end-to-end in tests/integration/test_backtest_persistence.py (admission-blocked + worker
    defence-in-depth); what is pinned HERE is the plan-shaped contract they read."""
    empty = IndicatorPlan(
        entry_rule=SignalRule(rule="required_indicator_blocks_only"),
        entry_specs=(),
        unresolved=("entry:blk_1:no_directional_dependency",),
    )
    assert not empty.has_entry
    assert empty.unresolved == ("entry:blk_1:no_directional_dependency",)


def test_plan_run_is_deterministic_across_batch_sizes() -> None:
    a = _run(_config(), _bars(_LONG_CROSS), _sma_plan(), batch=8)
    b = _run(_config(), _bars(_LONG_CROSS), _sma_plan(), batch=3)
    assert a.summary == b.summary
    assert [t.pnl for t in a.trades] == [t.pnl for t in b.trades]


def test_plan_exit_on_opposite_signal_closes_and_reverses() -> None:
    # up-cross (long) then a down-cross (short) while long -> close on opposite, reverse.
    closes = ["10", "10", "10", "10", "10", "10", "12", "12", "12", "8", "8", "8"]
    out = _run(_config(), _bars(closes), _sma_plan())
    assert out.summary["total_trades"] == 2
    assert out.trades[0].direction == "long"
    assert out.trades[0].exit_reason == "exit_signal"
    assert out.trades[1].direction == "short"


def test_plan_direction_restriction_suppresses_disallowed_side() -> None:
    # A down-cross under a LONG-ONLY strategy: suppressed, traced, no trade.
    closes = ["10", "10", "10", "10", "10", "10", "8", "8", "8"]
    out = _run(_config(direction="long"), _bars(closes), _sma_plan())
    assert out.summary["total_trades"] == 0
    assert "filtered_no_entry" in {e.event_type for e in out.signal_events}


def test_active_plan_still_surfaces_unresolved_warnings() -> None:
    out = _run(
        _config(),
        _bars(_LONG_CROSS),
        _sma_plan(unresolved=("entry:blk_2:timeframe_override_deferred:1h",)),
    )
    assert out.diagnostics["entry_model"] == BUILTIN_ENTRY_MODEL  # still real
    assert "entry:blk_2:timeframe_override_deferred:1h" in out.diagnostics["warnings"]
    assert "indicator_plan_empty_fallback_proxy" not in out.diagnostics["warnings"]


def test_plan_reproducibility_note_reflects_real_compute() -> None:
    out = _run(_config(), _bars(_LONG_CROSS), _sma_plan())
    assert "native trigger" in out.diagnostics["reproducibility_note"]
