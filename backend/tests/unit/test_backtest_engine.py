"""Stage 5a → post-V1 Slice B — pure backtest domain unit tests (doc 15).

DB-free. Covers: execution_key reproducibility vs run-unique manifest_hash (§17,
§7), pinned-item ordering (§9.2), the deterministic bar-replay engine (§9.3 order,
§17 reproducibility, real protection stops, direction restriction, bounded batch
streaming), and the canonical metric registry incl. never-0 missing metrics (§5, L4).
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    ENTRY_MODEL,
    EngineOutput,
    _position_size,
    run_engine,
)
from entropia.domain.backtest.enums import (
    RUN_ACTIVE_STATES,
    RUN_RETRYABLE_STATES,
    RUN_TERMINAL_STATES,
    BacktestRunState,
    MetricAvailability,
)
from entropia.domain.backtest.manifest import build_run_manifest
from entropia.domain.backtest.metrics import DEFAULT_METRICS, derive_metric_values
from entropia.domain.strategy.config import StrategyConfig


# ---------------------------------------------------------------------------
# Manifest (unchanged Stage 5a contract)
# ---------------------------------------------------------------------------
def _manifest(run_id: str, snapshot_id: str, created_at: str, *, fingerprint: str = "fp_1"):
    item_manifest = {
        "items": [
            {
                "item_id": "mbi_2",
                "kind": "strategy",
                "root_id": "wo_b",
                "revision_id": "rev_b",
                "position": 20,
                "enabled": True,
            },
            {
                "item_id": "mbi_1",
                "kind": "strategy",
                "root_id": "wo_a",
                "revision_id": "rev_a",
                "position": 10,
                "enabled": True,
            },
        ]
    }
    return build_run_manifest(
        run_id=run_id,
        composition_id="mbws_1",
        composition_snapshot_id=snapshot_id,
        composition_fingerprint=fingerprint,
        item_manifest=item_manifest,
        capital_mode={"enabled": False},
        requested_by_principal_id="user_1",
        preflight={"ready_report_id": "rcrpt_1", "state": "ready", "warning_count": 0},
        correlation_id="corr_1",
        created_at_iso=created_at,
    )


def test_execution_key_is_reproducible_but_manifest_hash_is_run_unique() -> None:
    a = _manifest("btrun_A", "snap_A", "2024-01-01T00:00:00Z")
    b = _manifest("btrun_B", "snap_B", "2024-02-02T00:00:00Z")
    # Same pinned composition -> identical execution key (reproducibility, §17)...
    assert a.execution_key == b.execution_key
    # ...but every run gets a unique manifest hash (retry -> new hash, §7/§8.4).
    assert a.manifest_hash != b.manifest_hash
    assert len(a.manifest_hash) == 64 and len(a.execution_key) == 64


def test_manifest_pins_items_sorted_by_root_revision() -> None:
    built = _manifest("btrun_A", "snap_A", "2024-01-01T00:00:00Z")
    roots = [item["root_id"] for item in built.manifest["mainboard_items"]]
    assert roots == ["wo_a", "wo_b"]  # sorted, independent of input/position order
    assert built.manifest["mainboard_items"][0]["selected_revision_id"] == "rev_a"


def test_execution_key_changes_with_fingerprint() -> None:
    a = _manifest("btrun_A", "snap_A", "2024-01-01T00:00:00Z", fingerprint="fp_1")
    b = _manifest("btrun_A", "snap_A", "2024-01-01T00:00:00Z", fingerprint="fp_2")
    assert a.execution_key != b.execution_key


# ---------------------------------------------------------------------------
# Bar-replay engine (post-V1 Slice B)
# ---------------------------------------------------------------------------
def _config(
    *,
    direction: str = "long_and_short",
    loss_pct: str = "1.0",
    base_size: str = "50",
    instrument: str = "BTCUSDT",
    method: str = "base_position_size",
    with_stop: bool = True,
    risk_pct: str | None = None,
    stop_point: str | None = None,
) -> StrategyConfig:
    """A minimal VALID StrategyConfig; only the fields the engine reads matter."""
    sizing: dict[str, Any] = {"method": method}
    if method == "base_position_size":
        sizing["base_position_size"] = base_size
    if method == "risk_based_sizing" and risk_pct is not None and stop_point is not None:
        sizing["risk_based"] = {
            "risk_percentage_per_trade": risk_pct,
            "stop_loss_point": stop_point,
        }
    protection: dict[str, Any] = (
        {"percentage_stop": {"enabled": True, "loss_percentage": loss_pct}} if with_stop else {}
    )
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Bar Replay Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": instrument,
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
            "position_sizing": sizing,
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


def _bar(ts: str, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c, "volume": "10"}


def _flat(n: int, price: str = "100") -> list[dict[str, Any]]:
    return [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", price, price, price, price) for i in range(n)]


def _long_breakout_then_stop() -> list[dict[str, Any]]:
    """20 flat bars (fills the window) → an upside breakout entry → a stop-out."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "102", "100", "102"))  # breakout -> long
    bars.append(_bar("2024-01-22T00:00:00Z", "102", "102", "90", "95"))  # low 90 trips 1% stop
    return bars


def _batched(bars: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(bars), size):
        yield bars[start : start + size]


def _run(config: StrategyConfig, bars: list[dict[str, Any]], *, batch: int = 8) -> EngineOutput:
    return run_engine(
        strategy_config=config,
        bar_batches=_batched(bars, batch),
        execution_key="exec_key_test",
    )


def test_engine_bar_replay_produces_a_real_stop_out_trade() -> None:
    out = _run(_config(), _long_breakout_then_stop())
    assert out.summary["total_trades"] == 1
    trade = out.trades[0]
    assert trade.direction == "long"
    assert trade.exit_reason == "stop_loss"
    assert out.summary["total_stops"] == 1
    assert out.summary["symbol"] == "BTCUSDT"  # real symbol, never fabricated as None now
    # Stop at entry(102) * (1 - 1%) = 100.98 -> a loss on a 50-unit position.
    assert trade.pnl < Decimal("0")
    assert out.summary["net_profit"] == trade.pnl
    assert out.diagnostics["engine_kind"] == "v1_bar_replay"
    assert out.diagnostics["entry_model"] == ENTRY_MODEL
    assert out.diagnostics["bars_processed"] == 22


def test_engine_is_deterministic_for_identical_inputs() -> None:
    cfg = _config()
    first = _run(cfg, _long_breakout_then_stop())
    # Re-run with a DIFFERENT batch size: the streamed result must be identical
    # (reproducibility is a function of bars+config, not batching, §17).
    second = _run(cfg, _long_breakout_then_stop(), batch=3)
    assert first.summary == second.summary
    assert [t.pnl for t in first.trades] == [t.pnl for t in second.trades]
    assert len(first.equity_points) == len(first.trades) + 1  # includes the seed point


def test_engine_direction_restriction_suppresses_and_traces_no_entry() -> None:
    # A downside breakout under a LONG-ONLY strategy: no trade, but the decision
    # trace records the suppressed entry (a non-fill event != a fill, §14).
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "100", "98", "98"))  # down breakout
    out = _run(_config(direction="long"), bars)
    assert out.summary["total_trades"] == 0
    kinds = {event.event_type for event in out.signal_events}
    assert "filtered_no_entry" in kinds


def test_engine_yields_no_trades_and_empty_warning_on_no_bars() -> None:
    out = run_engine(
        strategy_config=_config(), bar_batches=iter([]), execution_key="exec_key_empty"
    )
    assert out.summary["total_trades"] == 0
    assert out.summary["net_profit"] == Decimal("0.00")
    assert out.diagnostics["warnings"] == ["no_bars_in_source"]


def test_engine_warns_on_unsupported_sizing_method() -> None:
    # formula_based sizing is still not modelled — the engine falls back to notional
    # sizing and surfaces the divergence in diagnostics (never silently, L4).
    # (risk_based_sizing WITH a sub-config is now honored — see the tests below.)
    out = _run(_config(method="formula_based_sizing"), _long_breakout_then_stop())
    assert any(
        w.startswith("position_sizing_method_unsupported") for w in out.diagnostics["warnings"]
    )
    assert out.summary["total_trades"] == 1  # still produces a real result


def test_engine_warns_when_risk_based_sizing_lacks_its_sub_config() -> None:
    # A risk_based_sizing request that carries no ``risk_based`` sub-config cannot be
    # honored; the engine falls back to notional and surfaces the divergence (L4).
    out = _run(_config(method="risk_based_sizing"), _long_breakout_then_stop())
    assert any(
        w.startswith("position_sizing_method_unsupported") for w in out.diagnostics["warnings"]
    )


def test_engine_does_not_warn_when_risk_based_sizing_is_honored() -> None:
    # risk_based_sizing WITH its sub-config is modelled: no unsupported warning.
    out = _run(
        _config(method="risk_based_sizing", risk_pct="2.0", stop_point="50"),
        _long_breakout_then_stop(),
    )
    assert not any(
        w.startswith("position_sizing_method_unsupported") for w in out.diagnostics["warnings"]
    )
    assert out.summary["total_trades"] == 1  # produces a real result


def test_position_size_risk_based_applies_the_risk_formula() -> None:
    # size = equity * risk% / 100 / stop_loss_point = 10000 * 2 / 100 / 50 = 4.
    cfg = _config(method="risk_based_sizing", risk_pct="2.0", stop_point="50")
    assert _position_size(cfg, Decimal("123.45"), Decimal("10000")) == Decimal("4")


def test_position_size_risk_based_is_independent_of_entry_price() -> None:
    # Risk-based sizing is a function of equity + stop distance, never the price.
    cfg = _config(method="risk_based_sizing", risk_pct="2.0", stop_point="50")
    low = _position_size(cfg, Decimal("100"), Decimal("10000"))
    high = _position_size(cfg, Decimal("999999"), Decimal("10000"))
    assert low == high == Decimal("4")


def test_position_size_risk_based_clamps_negative_equity_to_zero() -> None:
    # A bust account never yields a negative size (would invert PnL signs — CRITICAL).
    cfg = _config(method="risk_based_sizing", risk_pct="2.0", stop_point="50")
    assert _position_size(cfg, Decimal("100"), Decimal("-500")) == Decimal("0")


def test_engine_notional_sizing_never_inverts_pnl_after_bust() -> None:
    # Regression (review CRITICAL): with notional (non-base) sizing and no stop, a
    # catastrophic short drives equity negative; the next entry must clamp to size 0
    # rather than a NEGATIVE size, which would invert PnL signs. Assert no
    # adverse-direction trade ever books a phantom profit.
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "100", "95", "95"))  # short entry
    bars.append(_bar("2024-01-22T00:00:00Z", "100", "300", "95", "300"))  # exit -> equity < 0
    bars.append(_bar("2024-01-23T00:00:00Z", "95", "95", "90", "90"))  # re-entry after bust
    bars.append(_bar("2024-01-24T00:00:00Z", "300", "400", "300", "400"))  # exit
    out = _run(_config(direction="short", method="formula_based_sizing", with_stop=False), bars)
    assert out.summary["total_trades"] >= 2
    for trade in out.trades:
        adverse = (
            trade.exit_price > trade.entry_price
            if trade.direction == "short"
            else trade.exit_price < trade.entry_price
        )
        if adverse:
            assert trade.pnl <= Decimal("0"), f"phantom profit on adverse trade: {trade}"


def test_metrics_registry_maps_all_nine_defaults() -> None:
    out = _run(_config(), _long_breakout_then_stop())
    values = derive_metric_values(out.summary)
    assert len(values) == len(DEFAULT_METRICS) == 9
    assert [v.key for v in values][:2] == ["net_profit", "max_drawdown"]
    computed = [v for v in values if v.availability == MetricAvailability.COMPUTED]
    assert all(v.value is not None for v in computed)


def test_missing_ratio_metric_is_non_computed_never_zero() -> None:
    # A no-qualifying-trades summary: ratio/percent metrics that CANNOT be computed
    # surface as None + NO_QUALIFYING_TRADES (never a fabricated 0), while count
    # metrics that legitimately ARE 0 show the real computed 0 (L4, §5).
    summary = {
        "net_profit_pct": None,
        "max_drawdown_pct": None,
        "romad": None,
        "win_rate": None,
        "profit_factor": None,
        "total_trades": 0,
        "total_stops": 0,
        "max_stop_streak": 0,
        "total_winning_trades": 0,
    }
    values = {v.key: v for v in derive_metric_values(summary)}
    for key in ("net_profit", "max_drawdown", "romad", "win_rate", "profit_factor"):
        assert values[key].value is None
        assert values[key].availability == MetricAvailability.NO_QUALIFYING_TRADES
    for key in ("total_trades", "total_stops", "max_stop_streak", "total_winning_trades"):
        assert values[key].value == Decimal("0")
        assert values[key].availability == MetricAvailability.COMPUTED


def test_run_state_partitions() -> None:
    assert BacktestRunState.QUEUED in RUN_ACTIVE_STATES
    assert BacktestRunState.SUCCEEDED in RUN_TERMINAL_STATES
    assert {BacktestRunState.FAILED, BacktestRunState.CANCELLED} == RUN_RETRYABLE_STATES
    assert RUN_ACTIVE_STATES.isdisjoint(RUN_TERMINAL_STATES)
