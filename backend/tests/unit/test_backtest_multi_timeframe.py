"""Multi-timeframe resampling unit tests (post-V1 Slice C follow-up (c)) — DB-free.

A higher-timeframe indicator block aggregates the base bars into its own coarser
candle and advances the inner compute only when a candle CLOSES — never on a
still-forming one (no look-ahead / no repaint). These tests pin: the timeframe→span
map, the timestamp bucketing, the causal timing of a higher-TF signal, that a trailing
incomplete candle never fires, equivalence to computing on hand-aggregated candles, and
batch-invariant determinism through ``run_engine``.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import run_engine
from entropia.domain.backtest.indicators import (
    BlockEvaluator,
    IndicatorPlan,
    IndicatorSpec,
    SignalRule,
    _epoch_seconds,
    _htf_bucket,
    timeframe_seconds,
)
from entropia.domain.strategy.config import StrategyConfig

_2H = 7200  # two 1-hour base bars per higher-TF candle at wall-clock 2h boundaries


def _htf_spec(*, length: int = 2, span: int | None = _2H) -> IndicatorSpec:
    return IndicatorSpec(
        block_id="blk_htf",
        canonical_key="ta.sma",
        length=length,
        direction="long_and_short",
        requirement="required",
        validity="until_opposite_signal",
        resample_seconds=span,
    )


def _htf_eval() -> BlockEvaluator:
    return BlockEvaluator(_htf_spec())


def _hourly(closes: list[str]) -> list[tuple[str, Decimal]]:
    """(ISO hourly timestamp, close) pairs, one per hour from 2024-01-01T00:00Z."""
    return [(f"2024-01-01T{h:02d}:00:00Z", Decimal(c)) for h, c in enumerate(closes)]


# 12 hourly bars -> six 2h candles. Candle closes (2nd bar of each bucket) are
# [10, 10, 10, 10, 12, 12]; an SMA(2) price/MA cross fires LONG on candle 4, which
# only CLOSES when the first bar of the next bucket (bar index 10) arrives.
_CROSS_CLOSES = ["10", "10", "10", "10", "10", "10", "10", "10", "11", "12", "12", "12"]
_HTF_CANDLE_CLOSES = ["10", "10", "10", "10", "12", "12"]


def test_timeframe_seconds_maps_the_fixed_vocabulary() -> None:
    assert timeframe_seconds("1m") == 60
    assert timeframe_seconds("1h") == 3600
    assert timeframe_seconds("4h") == 14400
    assert timeframe_seconds("1D") == 86400
    # Base-timeframe sentinels and anything unknown are not concrete spans.
    assert timeframe_seconds("same_as_base_tf") is None
    assert timeframe_seconds("1w") is None


def test_epoch_bucket_parses_iso_naive_and_epoch_forms() -> None:
    z = _epoch_seconds("2024-01-01T00:00:00Z")
    naive = _epoch_seconds("2024-01-01T00:00:00")  # assumed UTC
    epoch_s = _epoch_seconds("1704067200")
    epoch_ms = _epoch_seconds("1704067200000")
    assert z == naive == epoch_s == epoch_ms == 1704067200
    assert _epoch_seconds("not-a-time") is None
    # Two hourly bars share a 2h bucket; the third opens the next one.
    b0 = _htf_bucket("2024-01-01T00:00:00Z", _2H)
    b1 = _htf_bucket("2024-01-01T01:00:00Z", _2H)
    b2 = _htf_bucket("2024-01-01T02:00:00Z", _2H)
    assert b0 == b1 == b2 - 1


def _feed(ev: BlockEvaluator, bars: list[tuple[str, Decimal]]) -> list[str | None]:
    signals: list[str | None] = []
    for ts, close in bars:
        ev.update(close, timestamp=ts)
        signals.append(ev.current_signal)
    return signals


def test_higher_tf_cross_is_only_readable_after_the_candle_closes() -> None:
    ev = _htf_eval()
    signals = _feed(ev, _hourly(_CROSS_CLOSES))
    # No look-ahead: candle 4 spans bars 8 & 9; its LONG cross is NOT visible on the
    # forming candle (bar 9) — only once bar 10 opens the next bucket and closes it.
    assert signals[9] is None
    assert signals[10] == "long"
    assert ev.current_signal == "long"


def test_trailing_incomplete_candle_never_fires() -> None:
    # The cross lands on the LAST 2h candle (bucket {10,11}), which never closes
    # (no bar 12), so no signal repaints from a still-forming candle.
    closes = ["10", "10", "10", "10", "10", "10", "10", "10", "10", "10", "10", "12"]
    ev = _htf_eval()
    _feed(ev, _hourly(closes))
    assert ev.current_signal is None


def test_resample_equals_computing_on_hand_aggregated_candles() -> None:
    # A higher-TF evaluator over 12 hourly bars must reproduce a base-TF evaluator fed
    # the six hand-aggregated candle closes (same cross, same direction).
    htf = _htf_eval()
    _feed(htf, _hourly(_CROSS_CLOSES))
    base = BlockEvaluator(_htf_spec(span=None))
    base_signals: list[str | None] = []
    for c in _HTF_CANDLE_CLOSES:
        base.update(Decimal(c))
        base_signals.append(base.current_signal)
    assert base_signals[4] == "long"  # base evaluator fires on aggregated candle 4
    assert htf.current_signal == base.current_signal == "long"


def _config() -> StrategyConfig:
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "MTF Fixture",
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
                        "block_id": "blk_htf",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_1",
                            "package_revision_id": "pkgrev_1",
                            "package_content_hash": "pkghash_1",
                        },
                        "trigger_source": "indicator_native_trigger",
                        "timeframe": "2h",
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


def _plan() -> IndicatorPlan:
    return IndicatorPlan(
        entry_rule=SignalRule(rule="required_indicator_blocks_only"),
        entry_specs=(_htf_spec(),),
    )


def _bars(closes: list[str]) -> list[dict[str, Any]]:
    return [
        {"timestamp": ts, "open": str(c), "high": str(c), "low": str(c), "close": str(c)}
        for ts, c in _hourly(closes)
    ]


def _batched(bars: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(bars), size):
        yield bars[start : start + size]


def test_engine_multi_timeframe_entry_is_batch_invariant() -> None:
    bars = _bars(_CROSS_CLOSES)
    out_a = run_engine(
        strategy_config=_config(),
        bar_batches=_batched(bars, 8),
        execution_key="k",
        indicator_plan=_plan(),
    )
    out_b = run_engine(
        strategy_config=_config(),
        bar_batches=_batched(bars, 3),
        execution_key="k",
        indicator_plan=_plan(),
    )
    # One resolved higher-TF block drove the run; the result is batch-independent.
    assert out_a.diagnostics["multi_timeframe_blocks"] == 1
    assert out_a.summary["total_trades"] == 1
    assert [t.direction for t in out_a.trades] == ["long"]
    assert out_a.trades == out_b.trades
    assert out_a.summary == out_b.summary
