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
    COMPOSITION_CURVE_WARNING,
    EngineOutput,
    ItemRun,
    _clamp_to_limits,
    _position_size,
    combine_item_runs,
    run_engine,
)
from entropia.domain.backtest.enums import (
    RUN_ACTIVE_STATES,
    RUN_RETRYABLE_STATES,
    RUN_TERMINAL_STATES,
    BacktestRunState,
    MetricAvailability,
)
from entropia.domain.backtest.indicators import BUILTIN_ENTRY_MODEL
from entropia.domain.backtest.manifest import build_run_manifest
from entropia.domain.backtest.metrics import DEFAULT_METRICS, derive_metric_values
from entropia.domain.strategy.config import PositionSizeLimits, StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan


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
    formula_type: str | None = None,
    win_prob: str | None = None,
    payoff: str | None = None,
    kelly_fraction: str | None = None,
    min_size: str | None = None,
    max_size: str | None = None,
    stop_exit_conflict: str | None = None,
    entry_timing: str = "current_candle_close",
    exit_timing: str = "current_candle_close",
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
    if method == "formula_based_sizing" and formula_type is not None:
        formula_params: dict[str, Any] = {}
        if win_prob is not None:
            formula_params["win_probability"] = win_prob
        if payoff is not None:
            formula_params["payoff_ratio"] = payoff
        if kelly_fraction is not None:
            formula_params["kelly_fraction"] = kelly_fraction
        sizing["formula_based"] = {
            "formula_type": formula_type,
            "formula_params": formula_params,
        }
    if min_size is not None or max_size is not None:
        limits: dict[str, Any] = {}
        if min_size is not None:
            limits["min_position_size"] = min_size
        if max_size is not None:
            limits["max_position_size"] = max_size
        sizing["position_size_limits"] = limits
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
                    "entry_timing": entry_timing,
                    "exit_timing": exit_timing,
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
            "conflict_position_handling": (
                {"stop_exit_conflict": stop_exit_conflict} if stop_exit_conflict is not None else {}
            ),
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
        indicator_plan=sma_entry_plan(),
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
    # The signal came from the resolved indicator plan — the model a real RUN reports (F-06:
    # an unresolved plan is a Ready Check blocker, so the breakout proxy never labels a
    # production result).
    assert out.diagnostics["entry_model"] == BUILTIN_ENTRY_MODEL
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
        strategy_config=_config(),
        bar_batches=iter([]),
        execution_key="exec_key_empty",
        indicator_plan=sma_entry_plan(),
    )
    assert out.summary["total_trades"] == 0
    assert out.summary["net_profit"] == Decimal("0.00")
    assert out.diagnostics["warnings"] == ["no_bars_in_source"]


def test_engine_warns_on_unsupported_sizing_method() -> None:
    # formula_based sizing is not modelled — the engine FAILS CLOSED (opens no position,
    # F-09) and surfaces the divergence in diagnostics (never silently, L4).
    # (risk_based_sizing WITH a sub-config is now honored — see the tests below.)
    out = _run(_config(method="formula_based_sizing"), _long_breakout_then_stop())
    assert any(
        w.startswith("position_sizing_method_unsupported") for w in out.diagnostics["warnings"]
    )
    assert out.summary["total_trades"] == 0  # fail closed: no position opened


def test_engine_warns_when_risk_based_sizing_lacks_its_sub_config() -> None:
    # A risk_based_sizing request that carries no ``risk_based`` sub-config cannot be
    # honored; the engine FAILS CLOSED (no position) and surfaces the divergence (L4).
    out = _run(_config(method="risk_based_sizing"), _long_breakout_then_stop())
    assert any(
        w.startswith("position_sizing_method_unsupported") for w in out.diagnostics["warnings"]
    )
    assert out.summary["total_trades"] == 0  # fail closed: no position opened


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


def _kelly(win_prob: str, payoff: str, kelly_fraction: str | None = None) -> StrategyConfig:
    return _config(
        method="formula_based_sizing",
        formula_type="kelly_criterion",
        win_prob=win_prob,
        payoff=payoff,
        kelly_fraction=kelly_fraction,
    )


def test_position_size_kelly_applies_the_fractional_kelly_formula() -> None:
    # f* = W - (1 - W) / R = 0.6 - 0.4 / 2 = 0.4; size = equity * f* / entry_price.
    cfg = _kelly("0.6", "2")
    assert _position_size(cfg, Decimal("100"), Decimal("10000")) == Decimal("40")


def test_position_size_kelly_scales_with_the_fractional_multiplier() -> None:
    # Half-Kelly halves the capital fraction: f* = 0.5 * 0.4 = 0.2 → 10000 * 0.2 / 100.
    cfg = _kelly("0.6", "2", kelly_fraction="0.5")
    assert _position_size(cfg, Decimal("100"), Decimal("10000")) == Decimal("20")


def test_position_size_kelly_non_positive_edge_clamps_to_zero() -> None:
    # W - (1 - W) / R = 0.4 - 0.6 / 1 = -0.2 → clamped to 0 (no edge, do not trade),
    # never a negative (bet-against-the-edge) size. Still an honored config (size 0).
    cfg = _kelly("0.4", "1")
    assert _position_size(cfg, Decimal("100"), Decimal("10000")) == Decimal("0")


def test_position_size_kelly_clamps_negative_equity_to_zero() -> None:
    # A bust account never yields a negative size (would invert PnL signs — CRITICAL).
    cfg = _kelly("0.6", "2")
    assert _position_size(cfg, Decimal("100"), Decimal("-500")) == Decimal("0")


def test_position_size_kelly_is_entry_price_dependent() -> None:
    # Unlike risk-based, Kelly sizes a fraction of CAPITAL, so the unit count scales
    # inversely with the entry price (f* = 0.4; 10000 * 0.4 / price).
    cfg = _kelly("0.6", "2")
    cheap = _position_size(cfg, Decimal("100"), Decimal("10000"))
    dear = _position_size(cfg, Decimal("200"), Decimal("10000"))
    assert cheap == Decimal("40")
    assert dear == Decimal("20")
    assert cheap != dear


def test_engine_does_not_warn_when_kelly_sizing_is_honored() -> None:
    # A valid kelly_criterion config is modelled: no unsupported-method warning.
    out = _run(_kelly("0.6", "2"), _long_breakout_then_stop())
    assert not any(
        w.startswith("position_sizing_method_unsupported") for w in out.diagnostics["warnings"]
    )
    assert out.summary["total_trades"] == 1  # produces a real result


def test_engine_warns_on_custom_formula_sizing() -> None:
    # custom_formula has no safe deterministic evaluation → fail closed (no position) + L4 warn.
    out = _run(
        _config(method="formula_based_sizing", formula_type="custom_formula"),
        _long_breakout_then_stop(),
    )
    assert any(
        w.startswith("position_sizing_method_unsupported") for w in out.diagnostics["warnings"]
    )


def test_engine_warns_when_kelly_params_are_missing() -> None:
    # kelly_criterion without win_probability / payoff_ratio cannot be modelled →
    # fail closed (no position) + surface the divergence (never silently, L4).
    out = _run(
        _config(method="formula_based_sizing", formula_type="kelly_criterion"),
        _long_breakout_then_stop(),
    )
    assert any(
        w.startswith("position_sizing_method_unsupported") for w in out.diagnostics["warnings"]
    )


def test_engine_warns_when_kelly_params_are_out_of_range() -> None:
    # An impossible win probability (>= 1) is rejected → fail closed (no position) + L4 warn.
    out = _run(_kelly("1.5", "2"), _long_breakout_then_stop())
    assert any(
        w.startswith("position_sizing_method_unsupported") for w in out.diagnostics["warnings"]
    )


def test_position_size_kelly_non_finite_params_fail_closed() -> None:
    # formula_params is an unvalidated dict[str, Any]: a user-supplied "nan" / "Infinity"
    # constructs a quiet non-finite Decimal that would RAISE InvalidOperation on the
    # caller's ordered comparisons (crashing the run) or silently honour a nonsensical
    # infinite payoff. Both must FAIL CLOSED to size 0 (F-09) — never raise, never an
    # all-in notional, never a modelled Kelly size (40).
    for win, payoff in [("nan", "2"), ("Infinity", "2"), ("0.6", "nan"), ("0.6", "Infinity")]:
        cfg = _kelly(win, payoff)
        assert _position_size(cfg, Decimal("100"), Decimal("10000")) == Decimal("0")


def test_position_size_kelly_garbage_fraction_is_not_upgraded_to_full_kelly() -> None:
    # A PRESENT but non-finite kelly_fraction must FAIL CLOSED to size 0 (F-09) — never
    # silently treated as absent and upgraded to the most aggressive full-Kelly sizing,
    # and never an all-in notional.
    cfg = _kelly("0.6", "2", kelly_fraction="nan")
    assert _position_size(cfg, Decimal("100"), Decimal("10000")) == Decimal("0")  # fail closed
    assert _position_size(cfg, Decimal("100"), Decimal("10000")) != Decimal("40")  # not full Kelly


def test_engine_does_not_crash_on_nan_kelly_params() -> None:
    # Regression: a non-finite formula param must not propagate an InvalidOperation out
    # of the engine. The run completes, opens NO position (fail closed, F-09) and
    # surfaces the L4 unsupported-sizing warning instead of a phantom notional trade.
    out = _run(_kelly("nan", "2"), _long_breakout_then_stop())
    assert out.summary["total_trades"] == 0
    assert any(
        w.startswith("position_sizing_method_unsupported") for w in out.diagnostics["warnings"]
    )


def test_engine_unsupported_sizing_opens_no_position() -> None:
    # F-09 (was: notional-fallback no-phantom-profit regression). An unmodelled sizing
    # method (formula_based without a valid Kelly config) must FAIL CLOSED — the engine
    # opens NO position for it, so no phantom notional trade (and therefore no phantom
    # profit) can ever be booked, whatever the price path. The negative-size clamp for
    # SUPPORTED methods stays covered by test_position_size_{risk_based,kelly}_clamps_
    # negative_equity_to_zero.
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "100", "95", "95"))  # would-be short entry
    bars.append(_bar("2024-01-22T00:00:00Z", "100", "300", "95", "300"))  # would-be exit
    bars.append(_bar("2024-01-23T00:00:00Z", "95", "95", "90", "90"))  # would-be re-entry
    bars.append(_bar("2024-01-24T00:00:00Z", "300", "400", "300", "400"))  # would-be exit
    out = _run(_config(direction="short", method="formula_based_sizing", with_stop=False), bars)
    assert out.summary["total_trades"] == 0
    assert not out.trades
    assert any(
        w.startswith("position_sizing_method_unsupported") for w in out.diagnostics["warnings"]
    )


# --- position_size_limits (min/max cap) wiring -------------------------------


def test_clamp_to_limits_is_a_noop_without_limits() -> None:
    # No configured window → the raw size passes through byte-identically (this is what
    # keeps every pre-wiring test's expected size unchanged).
    assert _clamp_to_limits(Decimal("50"), None) == Decimal("50")


def test_clamp_to_limits_caps_down_to_max() -> None:
    limits = PositionSizeLimits(max_position_size=Decimal("30"))
    assert _clamp_to_limits(Decimal("50"), limits) == Decimal("30")


def test_clamp_to_limits_lifts_up_to_min() -> None:
    limits = PositionSizeLimits(min_position_size=Decimal("80"))
    assert _clamp_to_limits(Decimal("50"), limits) == Decimal("80")


def test_clamp_to_limits_leaves_a_size_within_the_window() -> None:
    limits = PositionSizeLimits(min_position_size=Decimal("10"), max_position_size=Decimal("100"))
    assert _clamp_to_limits(Decimal("50"), limits) == Decimal("50")


def test_clamp_to_limits_preserves_the_zero_fail_closed_sentinel() -> None:
    # 0 = "do not open" (bust equity / non-positive entry price). A min cap must NOT
    # resurrect it into a live position.
    limits = PositionSizeLimits(min_position_size=Decimal("80"))
    assert _clamp_to_limits(Decimal("0"), limits) == Decimal("0")


def test_clamp_to_limits_min_greater_than_max_fails_closed() -> None:
    # A misconfigured window that no size can satisfy fails closed to 0 rather than
    # silently honouring one bound and violating the other.
    limits = PositionSizeLimits(min_position_size=Decimal("100"), max_position_size=Decimal("30"))
    assert _clamp_to_limits(Decimal("50"), limits) == Decimal("0")


def test_clamp_to_limits_neutralises_a_negative_cap() -> None:
    # A nonsensical negative max cannot pull a size negative — the final guard floors at 0.
    limits = PositionSizeLimits(max_position_size=Decimal("-5"))
    assert _clamp_to_limits(Decimal("50"), limits) == Decimal("0")


def test_position_size_base_is_capped_to_max() -> None:
    cfg = _config(base_size="50", max_size="30")
    assert _position_size(cfg, Decimal("100"), Decimal("10000")) == Decimal("30")


def test_position_size_base_is_lifted_to_min() -> None:
    cfg = _config(base_size="50", min_size="80")
    assert _position_size(cfg, Decimal("100"), Decimal("10000")) == Decimal("80")


def test_position_size_risk_based_is_capped_to_max() -> None:
    # risk_based raw size = 10000 * 2% / 50 = 4; capped to 1.
    cfg = _config(method="risk_based_sizing", risk_pct="2.0", stop_point="50", max_size="1")
    assert _position_size(cfg, Decimal("123.45"), Decimal("10000")) == Decimal("1")


def test_position_size_kelly_is_capped_to_max() -> None:
    # Kelly raw size = 10000 * f* / 100, f* = 0.6 - 0.4/2 = 0.4 → 40; capped to 5.
    cfg = _config(
        method="formula_based_sizing",
        formula_type="kelly_criterion",
        win_prob="0.6",
        payoff="2",
        max_size="5",
    )
    assert _position_size(cfg, Decimal("100"), Decimal("10000")) == Decimal("5")


def test_position_size_unsupported_sizing_fails_closed_regardless_of_cap() -> None:
    # custom_formula is unmodelled → FAIL CLOSED to size 0 (F-09). There is no all-in
    # notional to cap; a configured max cap is irrelevant because the raw size is 0.
    cfg = _config(method="formula_based_sizing", formula_type="custom_formula", max_size="7")
    assert _position_size(cfg, Decimal("100"), Decimal("10000")) == Decimal("0")


def test_position_size_bust_equity_stays_zero_despite_min_cap() -> None:
    # A min cap must not manufacture a position when the raw size is 0 — here because the
    # sizing method is unmodelled and fails closed (F-09). The clamp leaves 0 as 0.
    cfg = _config(method="formula_based_sizing", formula_type="custom_formula", min_size="10")
    assert _position_size(cfg, Decimal("100"), Decimal("-500")) == Decimal("0")


def test_engine_applies_the_position_size_cap_to_a_real_trade() -> None:
    # End-to-end: a base size of 50 capped to 5 shrinks the booked position, so the
    # stop-out loss is strictly smaller in magnitude than the uncapped run (same prices,
    # same stop). Both are losses, so uncapped_net < capped_net < 0.
    uncapped = _run(_config(base_size="50"), _long_breakout_then_stop())
    capped = _run(_config(base_size="50", max_size="5"), _long_breakout_then_stop())
    assert capped.diagnostics["position_size_limits_active"] is True
    assert uncapped.diagnostics["position_size_limits_active"] is False
    assert capped.summary["total_trades"] == uncapped.summary["total_trades"] == 1
    assert uncapped.summary["net_profit"] < capped.summary["net_profit"] < Decimal("0")


def test_engine_execution_key_namespace_shifts_with_the_engine_version() -> None:
    # The ENGINE_VERSION bump must flow into the manifest so a stale pre-conflict
    # result cannot be reused under the new engine (INF-04 idempotent reuse / INF-05).
    built = _manifest("btrun_A", "snap_A", "2024-01-01T00:00:00Z")
    assert built.manifest["identity"]["engine_version"] == "backtest-engine-v15-intrabar-execution"


def test_stop_exit_default_is_stop_has_priority() -> None:
    # §5.9: with no override the same-bar Stop+Exit collision resolves to the stop —
    # the V18 default. The bar-22 low (90) both trips the 1% stop AND makes a new
    # window low (proxy exit), so the collision path is exercised; the trade closes at
    # the stop level, NOT at the bar close.
    out = _run(_config(), _long_breakout_then_stop())
    trade = out.trades[0]
    assert trade.exit_reason == "stop_loss"
    assert out.diagnostics["stop_exit_conflict"] == "stop_has_priority"
    assert out.diagnostics["stop_exit_collisions"] == 1
    # Stop = entry(102) * (1 - 1%) = 100.98 (slippage/commission are 0 here).
    assert trade.exit_price == Decimal("100.98")


def test_stop_exit_exit_has_priority_closes_at_the_bar_close() -> None:
    # "exit_has_priority" is the only option that changes the OUTCOME: the same
    # collision bar closes as an exit at the bar CLOSE (95), well below the stop
    # (100.98), so the long loses strictly more than under stop priority.
    stop_first = _run(_config(), _long_breakout_then_stop())
    exit_first = _run(_config(stop_exit_conflict="exit_has_priority"), _long_breakout_then_stop())
    trade = exit_first.trades[0]
    assert trade.exit_reason == "exit_signal"
    assert trade.exit_price == Decimal("95")
    assert exit_first.diagnostics["stop_exit_conflict"] == "exit_has_priority"
    assert exit_first.diagnostics["stop_exit_collisions"] == 1
    # Closing lower (95 < 100.98) is strictly worse for the long position.
    assert exit_first.summary["net_profit"] < stop_first.summary["net_profit"]


def test_stop_exit_record_both_reasons_executes_stop_but_logs_the_collision() -> None:
    # "record_both_reasons" executes the stop (identical trade to the default) but
    # emits a stop_exit_collision signal event carrying BOTH reason codes (§5.9).
    default = _run(_config(), _long_breakout_then_stop())
    both = _run(_config(stop_exit_conflict="record_both_reasons"), _long_breakout_then_stop())
    assert both.trades[0].exit_reason == "stop_loss"
    assert both.trades[0].exit_price == default.trades[0].exit_price
    assert both.summary["net_profit"] == default.summary["net_profit"]
    collision = [e for e in both.signal_events if e.event_type == "stop_exit_collision"]
    assert len(collision) == 1
    assert collision[0].detail["executed"] == "stop_loss"
    assert collision[0].detail["also_triggered"] == "exit_signal"


def test_stop_exit_first_trigger_wins_resolves_to_the_intrabar_stop() -> None:
    # "first_trigger_wins": the stop is an intrabar high/low touch and precedes the
    # close-based exit signal, so it wins deterministically — same trade as the
    # default, but the collision is still counted (honest V1 boundary).
    default = _run(_config(), _long_breakout_then_stop())
    first = _run(_config(stop_exit_conflict="first_trigger_wins"), _long_breakout_then_stop())
    assert first.trades[0].exit_reason == "stop_loss"
    assert first.trades[0].exit_price == default.trades[0].exit_price
    assert first.diagnostics["stop_exit_collisions"] == 1
    # F-10: the conflict decision is ALWAYS traced (not only under record_both_reasons),
    # carrying which rule executed, which also fired, and the governing policy.
    collision = [e for e in first.signal_events if e.event_type == "stop_exit_collision"]
    assert len(collision) == 1
    assert collision[0].detail["executed"] == "stop_loss"
    assert collision[0].detail["also_triggered"] == "exit_signal"
    assert collision[0].detail["policy"] == "first_trigger_wins"


def test_summary_carries_the_caller_resolved_timeframe() -> None:
    # The job resolves the pinned market revision's base bar timeframe and passes it
    # through; the engine surfaces it verbatim in the summary (pure — no I/O here).
    out = run_engine(
        strategy_config=_config(),
        bar_batches=_batched(_long_breakout_then_stop(), 8),
        execution_key="exec_key_test",
        timeframe="1m",
        indicator_plan=sma_entry_plan(),
    )
    assert out.summary["timeframe"] == "1m"


def test_summary_timeframe_defaults_to_none_when_unresolved() -> None:
    # No caller-resolved timeframe (event-based / unknown revision) stays an honest
    # None — never guessed from the bars (L4).
    out = _run(_config(), _long_breakout_then_stop())
    assert out.summary["timeframe"] is None


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


# ---------------------------------------------------------------------------
# F-04: full-composition aggregation (combine_item_runs)
# ---------------------------------------------------------------------------


def _strategy_run(item_id: str, *, base_size: str = "50") -> ItemRun:
    """One executing Strategy ItemRun over the shared long-breakout-then-stop bars."""
    out = _run(_config(base_size=base_size), _long_breakout_then_stop())
    return ItemRun(
        item_id=item_id,
        item_kind="strategy",
        root_id=f"root_{item_id}",
        revision_id=f"rev_{item_id}",
        output=out,
    )


def test_combine_two_strategies_sums_net_profit_and_unions_trades() -> None:
    a = _strategy_run("item_a", base_size="50")
    b = _strategy_run("item_b", base_size="30")
    combined = combine_item_runs(
        [a, b],
        portfolio_initial_capital=Decimal("20000.00"),
        execution_key="exec_multi",
        item_count=2,
    )
    # Both strategies contribute: net_profit is additive, trades are the union.
    assert a.output is not None and b.output is not None
    assert combined.summary["net_profit"] == (
        a.output.summary["net_profit"] + b.output.summary["net_profit"]
    )
    assert combined.summary["total_trades"] == len(a.output.trades) + len(b.output.trades)
    assert combined.summary["initial_capital"] == Decimal("20000.00")
    assert combined.summary["final_equity"] == Decimal("20000.00") + combined.summary["net_profit"]
    # Trades are re-sequenced 1..N with no gaps or dupes.
    assert [t.seq for t in combined.trades] == list(range(1, len(combined.trades) + 1))
    # Every decision event is attributed to its originating item (traceability).
    tagged = {ev.detail.get("item_id") for ev in combined.signal_events}
    assert tagged == {"item_a", "item_b"}
    # Per-item breakdown is recorded for both, with the ledger seq range.
    comp = combined.diagnostics["composition"]
    assert comp["strategy_count"] == 2
    ids = {row["item_id"]: row for row in comp["items"]}
    assert ids["item_a"]["executed"] is True and ids["item_b"]["executed"] is True
    assert ids["item_a"]["net_profit"] == a.output.summary["net_profit"]
    assert ids["item_a"]["trade_seq_range"] == [1, len(a.output.trades)]
    assert COMPOSITION_CURVE_WARNING in combined.diagnostics["warnings"]


def test_combine_net_profit_is_order_invariant() -> None:
    a = _strategy_run("item_a", base_size="50")
    b = _strategy_run("item_b", base_size="30")
    forward = combine_item_runs(
        [a, b], portfolio_initial_capital=Decimal("20000"), execution_key="k", item_count=2
    )
    reverse = combine_item_runs(
        [b, a], portfolio_initial_capital=Decimal("20000"), execution_key="k", item_count=2
    )
    # Realized PnL is additive → the portfolio total does not depend on compose order.
    assert forward.summary["net_profit"] == reverse.summary["net_profit"]
    assert forward.summary["total_trades"] == reverse.summary["total_trades"]


def test_combine_records_non_executing_trading_signal_without_contribution() -> None:
    strat = _strategy_run("item_a")
    ts = ItemRun(
        item_id="item_ts",
        item_kind="trading_signal",
        root_id="root_ts",
        revision_id="rev_ts",
        output=None,
    )
    combined = combine_item_runs(
        [strat, ts],
        portfolio_initial_capital=Decimal("10000.00"),
        execution_key="exec_ts",
        item_count=2,
    )
    assert strat.output is not None
    # The Trading Signal is pinned + recorded but contributes no trades (V1 boundary).
    assert combined.summary["net_profit"] == strat.output.summary["net_profit"]
    assert combined.summary["total_trades"] == len(strat.output.trades)
    comp = combined.diagnostics["composition"]
    assert comp["strategy_count"] == 1
    assert comp["participating_item_count"] == 2
    ts_row = next(row for row in comp["items"] if row["item_id"] == "item_ts")
    assert ts_row["executed"] is False
    assert ts_row["net_profit"] is None
    assert ts_row["total_trades"] == 0
    # A lone executing strategy (with a participating TS) does NOT get the multi-curve
    # sequential warning — only 2+ executing strategies concatenate curves.
    assert COMPOSITION_CURVE_WARNING not in combined.diagnostics["warnings"]


# ============================================================================
# F-07a: entry/exit execution timing (ExecutionModel.entry_timing / exit_timing)
# ============================================================================


def _entry_timing_bars() -> list[dict[str, Any]]:
    """20 flat bars fill the breakout window at 100; bar 21 breaks out up (close 102 →
    long signal); bar 22 is the deferred-fill bar with a distinct open (105) and close
    (108). Trailing flat bars at 108 stay above the window low so nothing exits before
    end-of-data. With zero costs the raw fill price equals the recorded entry price:
    immediate → 102, next_candle_open → 105, next_candle_close → 108."""
    bars = _flat(20, "100")
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "102", "100", "102"))
    bars.append(_bar("2024-01-22T00:00:00Z", "105", "110", "104", "108"))
    bars += [_bar(f"2024-02-{i + 1:02d}T00:00:00Z", "108", "108", "108", "108") for i in range(3)]
    return bars


def _exit_timing_bars() -> list[dict[str, Any]]:
    """20 flat bars at 100 establish the MA; bar 21 crosses it (immediate long entry at 102);
    19 bars hold AT the entry price (above the MA — the trend is intact, so no exit signal);
    the next bar closes back under the MA (96 → exit signal); the final bar is the
    deferred-exit fill with a distinct open (90) and close (85). immediate exit → 96,
    next_candle_open → 90, next_candle_close → 85.

    The hold bars sit at 102, not 100: under a real MA cross (F-24) a fall back to the 100
    baseline IS a down-cross, i.e. a genuine exit signal, which would end the position before
    the bar this fixture designates as the exit. The retired breakout proxy exited only on a
    new window LOW, so flat-at-100 hold bars happened not to trip it."""
    bars = _flat(20, "100")
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "102", "100", "102"))
    bars += [_bar(f"2024-02-{i + 1:02d}T00:00:00Z", "102", "102", "102", "102") for i in range(19)]
    bars.append(_bar("2024-03-01T00:00:00Z", "100", "100", "95", "96"))
    bars.append(_bar("2024-03-02T00:00:00Z", "90", "91", "84", "85"))
    return bars


def test_entry_timing_current_candle_close_fills_at_signal_bar_close() -> None:
    # Baseline (unchanged behaviour): the entry fills at the SIGNAL bar's close.
    out = _run(_config(with_stop=False, direction="long"), _entry_timing_bars())
    assert out.summary["total_trades"] == 1
    assert out.trades[0].entry_price == Decimal("102.00")
    assert out.diagnostics["deferred_entry_fills"] == 0
    assert out.diagnostics["entry_timing"] == "current_candle_close"
    assert out.diagnostics["execution_timing_modelled"] is True


def test_entry_timing_next_candle_open_fills_at_next_bar_open() -> None:
    out = _run(
        _config(with_stop=False, direction="long", entry_timing="next_candle_open"),
        _entry_timing_bars(),
    )
    assert out.summary["total_trades"] == 1
    # POSITIVE: fills at the NEXT bar's open (105). NEGATIVE: NOT the old hardcoded
    # current-candle-close (102) — the timing is honored, not ignored.
    assert out.trades[0].entry_price == Decimal("105.00")
    assert out.trades[0].entry_price != Decimal("102.00")
    assert out.diagnostics["deferred_entry_fills"] == 1


def test_entry_timing_next_candle_close_fills_at_next_bar_close() -> None:
    out = _run(
        _config(with_stop=False, direction="long", entry_timing="next_candle_close"),
        _entry_timing_bars(),
    )
    assert out.summary["total_trades"] == 1
    assert out.trades[0].entry_price == Decimal("108.00")  # POSITIVE: next bar close
    assert out.trades[0].entry_price != Decimal("102.00")  # NEGATIVE: not signal close
    assert out.diagnostics["deferred_entry_fills"] == 1


def test_entry_timing_market_fill_simulation_is_immediate() -> None:
    # market_fill_simulation == a market fill at the decision bar's close (immediate).
    out = _run(
        _config(with_stop=False, direction="long", entry_timing="market_fill_simulation"),
        _entry_timing_bars(),
    )
    assert out.trades[0].entry_price == Decimal("102.00")
    assert out.diagnostics["deferred_entry_fills"] == 0
    assert out.diagnostics["execution_timing_modelled"] is True


def test_unsupported_entry_timing_fails_closed_opens_no_position() -> None:
    # F-07a: intrabar_touch needs a tick path — not silently imitated over OHLCV. The
    # engine opens NO position (fail closed, backstop to the Ready Check blocker).
    out = _run(
        _config(with_stop=False, direction="long", entry_timing="intrabar_touch"),
        _entry_timing_bars(),
    )
    assert out.summary["total_trades"] == 0
    assert out.diagnostics["execution_timing_modelled"] is False
    assert (
        "execution_timing_unsupported:intrabar_touch/current_candle_close"
        in out.diagnostics["warnings"]
    )


def test_unsupported_exit_timing_fails_closed_opens_no_position() -> None:
    # BOTH sides must be modelled: an unsupported EXIT timing (a stop-limit simulation)
    # also fails the run closed — no position at all.
    out = _run(
        _config(with_stop=False, direction="long", exit_timing="stop_limit_priority_simulation"),
        _entry_timing_bars(),
    )
    assert out.summary["total_trades"] == 0
    assert out.diagnostics["execution_timing_modelled"] is False


def test_exit_timing_current_candle_close_exits_at_signal_bar_close() -> None:
    out = _run(_config(with_stop=False, direction="long"), _exit_timing_bars())
    assert out.summary["total_trades"] == 1
    trade = out.trades[0]
    assert trade.exit_reason == "exit_signal"
    assert trade.exit_price == Decimal("96.00")
    assert out.diagnostics["deferred_exit_fills"] == 0


def test_exit_timing_next_candle_open_exits_at_next_bar_open() -> None:
    out = _run(
        _config(with_stop=False, direction="long", exit_timing="next_candle_open"),
        _exit_timing_bars(),
    )
    assert out.summary["total_trades"] == 1
    trade = out.trades[0]
    assert trade.exit_price == Decimal("90.00")  # POSITIVE: next bar open
    assert trade.exit_price != Decimal("96.00")  # NEGATIVE: not the signal close
    assert out.diagnostics["deferred_exit_fills"] == 1


def test_exit_timing_next_candle_close_exits_at_next_bar_close() -> None:
    out = _run(
        _config(with_stop=False, direction="long", exit_timing="next_candle_close"),
        _exit_timing_bars(),
    )
    assert out.summary["total_trades"] == 1
    trade = out.trades[0]
    assert trade.exit_price == Decimal("85.00")  # POSITIVE: next bar close
    assert trade.exit_price != Decimal("96.00")  # NEGATIVE: not the signal close
    assert out.diagnostics["deferred_exit_fills"] == 1


def test_intrabar_stop_pre_empts_a_deferred_close_exit() -> None:
    # A stop is ALWAYS an intrabar touch (immediate) and pre-empts a signal exit that
    # was deferred to the same bar's close: the stop wins, no deferred exit fill occurs.
    bars = _flat(20, "100")
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "102", "100", "102"))  # long entry @102
    bars += [_bar(f"2024-02-{i + 1:02d}T00:00:00Z", "100", "100", "100", "100") for i in range(19)]
    bars.append(_bar("2024-03-01T00:00:00Z", "100", "100", "95", "96"))  # exit signal (close 96)
    # A deferred (next_close) exit would fill here, but the bar's low 90 trips the 1% stop
    # (100.98 → below entry) intrabar first, so the STOP closes the trade.
    bars.append(_bar("2024-03-02T00:00:00Z", "97", "97", "90", "97"))
    out = _run(
        _config(with_stop=True, loss_pct="1.0", direction="long", exit_timing="next_candle_close"),
        bars,
    )
    assert out.summary["total_trades"] == 1
    assert out.trades[0].exit_reason == "stop_loss"
    assert out.diagnostics["deferred_exit_fills"] == 0
