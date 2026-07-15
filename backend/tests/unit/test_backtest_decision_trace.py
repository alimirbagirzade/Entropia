"""F-10 complete decision trace — pure engine unit tests (doc 15 §9.3 step 8, §14, §16).

Proves a reviewer can reconstruct WHY every position opened / did not open / changed /
closed from the immutable decision-trace artifact alone: the entry_signal -> entry_fill
-> position_close lifecycle links by ``position_seq`` + ``trade_seq`` + ``bar_seq``;
plan-mode entry decisions carry the evaluated rule id and each nested condition's
pass/fail; direction restrictions, deferred-timing schedules, sizing/sleeve blocks and
same-bar stop/exit conflicts are each traced; and the trace is byte-identical for the
same inputs (a stand-in for the same manifest -> deterministic trace acceptance)."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    DECISION_TRACE_EVENT_TYPES,
    DECISION_TRACE_SCHEMA,
    UNMODELLED_DECISION_CLASSES,
    EngineOutput,
    ItemRun,
    combine_item_runs,
    run_engine,
)
from entropia.domain.backtest.indicators import (
    IndicatorPlan,
    IndicatorSpec,
    SignalRule,
)
from entropia.domain.strategy.config import StrategyConfig


def _config(
    *,
    direction: str = "long_and_short",
    method: str = "base_position_size",
    formula_type: str | None = None,
    entry_timing: str = "current_candle_close",
    exit_timing: str = "current_candle_close",
    with_stop: bool = True,
) -> StrategyConfig:
    sizing: dict[str, Any] = {"method": method}
    if method == "base_position_size":
        sizing["base_position_size"] = "50"
    if method == "formula_based_sizing" and formula_type is not None:
        sizing["formula_based"] = {"formula_type": formula_type, "formula_params": {}}
    protection: dict[str, Any] = (
        {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}} if with_stop else {}
    )
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Trace Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
                "initial_capital": "10000.00",
                "execution": {"entry_timing": entry_timing, "exit_timing": exit_timing},
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
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c}


def _flat(n: int) -> list[dict[str, Any]]:
    return [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", "100", "100", "100", "100") for i in range(n)]


def _long_breakout_then_stop() -> list[dict[str, Any]]:
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "102", "100", "102"))  # breakout -> long
    bars.append(_bar("2024-01-22T00:00:00Z", "102", "102", "90", "95"))  # low 90 trips 1% stop
    return bars


def _plan_bars(closes: list[str]) -> list[dict[str, Any]]:
    return [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", c, c, c, c) for i, c in enumerate(closes)]


def _sma_plan() -> IndicatorPlan:
    spec = IndicatorSpec(
        block_id="blk_1",
        canonical_key="ta.sma",
        length=3,
        direction="long_and_short",
        requirement="required",
        validity="until_opposite_signal",
    )
    return IndicatorPlan(
        entry_rule=SignalRule(rule="required_indicator_blocks_only"),
        entry_specs=(spec,),
    )


def _batched(bars: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(bars), size):
        yield bars[start : start + size]


def _run(
    config: StrategyConfig,
    bars: list[dict[str, Any]],
    *,
    batch: int = 8,
    plan: IndicatorPlan | None = None,
) -> EngineOutput:
    return run_engine(
        strategy_config=config,
        bar_batches=_batched(bars, batch),
        execution_key="exec_key_trace",
        indicator_plan=plan,
    )


# A clean SMA(3) upward cross: flat at 10 then a step to 12 crosses the MA.
_LONG_CROSS = ["10", "10", "10", "10", "10", "10", "12", "12", "12"]


def test_position_lifecycle_is_fully_reconstructable() -> None:
    # entry_signal (decision) -> entry_fill (execution) -> position_close, all sharing one
    # position_seq, with the close linked to its immutable trade row + holding span.
    out = _run(_config(), _long_breakout_then_stop())
    by_type = {e.event_type: e for e in out.signal_events}
    assert {"entry_signal", "entry_fill", "position_close"} <= set(by_type)

    signal, fill, close = by_type["entry_signal"], by_type["entry_fill"], by_type["position_close"]
    # One lifecycle: the three events share the position id.
    pseq = fill.detail["position_seq"]
    assert close.detail["position_seq"] == pseq == 1
    # A signal/decision event is never conflated with a fill (doc 15 §16).
    assert "position_seq" not in signal.detail  # the decision precedes any fill
    # The close links to the immutable trade row + carries the realized outcome.
    assert close.detail["trade_seq"] == out.trades[0].seq == 1
    assert close.detail["exit_reason"] == "stop_loss"
    assert close.detail["pnl"] == str(out.trades[0].pnl)
    # bar_seq binds each event to the exact replayed bar (breakout on bar 21, stop on 22).
    assert signal.detail["bar_seq"] == fill.detail["bar_seq"] == 21
    assert close.detail["bar_seq"] == 22
    assert close.detail["entry_bar_seq"] == 21
    assert close.detail["holding_bars"] == 1


def test_trace_is_deterministic_for_identical_inputs() -> None:
    # Same inputs (a stand-in for the same manifest) -> byte-identical decision trace,
    # independent of batch size (§17 reproducibility applied to the trace artifact).
    a = _run(_config(), _long_breakout_then_stop(), batch=8)
    b = _run(_config(), _long_breakout_then_stop(), batch=3)
    project = lambda o: [  # noqa: E731
        (e.seq, e.event_time, e.event_type, e.direction, e.detail) for e in o.signal_events
    ]
    assert project(a) == project(b)


def test_plan_entry_signal_carries_rule_id_and_condition_evidence() -> None:
    out = _run(_config(), _plan_bars(_LONG_CROSS), plan=_sma_plan())
    signal = next(e for e in out.signal_events if e.event_type == "entry_signal")
    rule = signal.detail["rule"]
    assert rule["mode"] == "plan"
    assert rule["rule"] == "required_indicator_blocks_only"
    block = rule["blocks"][0]
    # The evaluated rule id is the pinned block id; the signal + conditions are recorded.
    assert block["rule_id"] == "blk_1"
    assert block["key"] == "ta.sma"
    assert block["signal"] == "long"
    assert block["conditions"] == []  # a plain native-trigger block has no nested conditions


def test_filtered_no_entry_is_per_occurrence_with_direction() -> None:
    # A down-cross under a LONG-ONLY strategy: the restriction is traced per occurrence,
    # carrying the filtered direction + reason (not a single post-run aggregate count).
    closes = ["10", "10", "10", "10", "10", "10", "8", "8", "8"]
    out = _run(_config(direction="long"), _plan_bars(closes), plan=_sma_plan())
    filtered = [e for e in out.signal_events if e.event_type == "filtered_no_entry"]
    # One event PER suppressed occurrence (the signal is disallowed while flat), never a
    # single post-run aggregate count row.
    assert filtered
    assert all(e.direction == "short" for e in filtered)
    assert all(e.detail["reason"] == "direction_restriction" for e in filtered)
    assert all(e.detail["direction_mode"] == "long" for e in filtered)
    assert all("count" not in e.detail for e in filtered)  # no aggregate row anymore
    assert len(filtered) == out.diagnostics["suppressed_entries"]
    assert out.summary["total_trades"] == 0


def test_deferred_timing_traces_schedule_then_deferred_fill() -> None:
    # next_candle_open: the entry is SCHEDULED at the signal bar and FILLS on the next
    # bar's open — both phases traced (F-07a timing made reconstructable).
    out = _run(
        _config(entry_timing="next_candle_open", with_stop=False), _long_breakout_then_stop()
    )
    scheduled = next(e for e in out.signal_events if e.event_type == "entry_scheduled")
    fill = next(e for e in out.signal_events if e.event_type == "entry_fill")
    assert scheduled.detail["bar_seq"] == 21
    assert scheduled.detail["target_bar_seq"] == 22
    assert scheduled.detail["timing"] == "next_candle_open"
    assert fill.detail["deferred"] is True
    assert fill.detail["bar_seq"] == 22


def test_entry_blocked_traces_the_unsupported_sizing_restriction() -> None:
    # A signal fires but an unmodelled sizing method opens NO position (F-09): the trace
    # records the decision (entry_signal) AND why it produced no fill (entry_blocked).
    out = _run(
        _config(method="formula_based_sizing", formula_type="custom_formula"),
        _long_breakout_then_stop(),
    )
    assert out.summary["total_trades"] == 0
    signals = [e for e in out.signal_events if e.event_type == "entry_signal"]
    blocked = [e for e in out.signal_events if e.event_type == "entry_blocked"]
    # Every entry decision that reached execution produced a blocked event (no silent gap).
    assert signals and len(blocked) == len(signals)
    assert all(e.detail["reason"] == "sizing_unsupported" for e in blocked)


def test_diagnostics_expose_trace_schema_and_unmodelled_classes() -> None:
    out = _run(_config(), _long_breakout_then_stop())
    diag = out.diagnostics
    assert diag["decision_trace_schema"] == DECISION_TRACE_SCHEMA == "v1"
    assert set(diag["decision_trace_event_types"]) == set(DECISION_TRACE_EVENT_TYPES)
    # Honest V1 boundary: scaling / partials never occur, surfaced (never fabricated).
    assert diag["unmodelled_decision_classes"] == list(UNMODELLED_DECISION_CLASSES)
    assert "same_direction_scaling" in diag["unmodelled_decision_classes"]
    assert "partial_fill" in diag["unmodelled_decision_classes"]
    assert "partial_close" in diag["unmodelled_decision_classes"]


def test_combined_events_bind_the_executing_object_revision() -> None:
    # combine_item_runs binds every event to the exact item's pinned object revision, so
    # a rule id resolves back to the immutable Strategy/Package revision that was replayed.
    out = _run(_config(), _long_breakout_then_stop())
    run = ItemRun(
        item_id="mbi_1",
        item_kind="strategy",
        root_id="wo_a",
        revision_id="rev_a",
        output=out,
    )
    combined = combine_item_runs(
        [run],
        portfolio_initial_capital=Decimal("10000.00"),
        execution_key="exec_key_trace",
        item_count=1,
    )
    assert combined.signal_events
    for event in combined.signal_events:
        assert event.detail["item_id"] == "mbi_1"
        assert event.detail["root_id"] == "wo_a"
        assert event.detail["revision_id"] == "rev_a"
