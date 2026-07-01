"""Stage 5a — pure backtest domain (manifest, engine, metrics) unit tests (doc 15).

DB-free. Covers: execution_key reproducibility vs run-unique manifest_hash (§17,
§7), deterministic engine output (§17), pinned-item ordering (§9.2), and the
canonical metric registry incl. the never-0 missing-metric behaviour (§5, L4).
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.engine import run_engine
from entropia.domain.backtest.enums import (
    RUN_ACTIVE_STATES,
    RUN_RETRYABLE_STATES,
    RUN_TERMINAL_STATES,
    BacktestRunState,
    MetricAvailability,
)
from entropia.domain.backtest.manifest import build_run_manifest
from entropia.domain.backtest.metrics import DEFAULT_METRICS, derive_metric_values


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


def test_engine_is_deterministic_for_the_same_execution_key() -> None:
    key = "exec_key_deadbeef"
    first = run_engine(key, initial_capital=Decimal("10000"), item_count=1)
    second = run_engine(key, initial_capital=Decimal("10000"), item_count=1)
    assert first.summary == second.summary
    assert [t.pnl for t in first.trades] == [t.pnl for t in second.trades]
    assert len(first.equity_points) == len(first.trades) + 1  # includes the seed point


def test_engine_signal_events_include_a_non_fill_decision() -> None:
    output = run_engine("exec_key_1", initial_capital=Decimal("10000"), item_count=1)
    kinds = {event.event_type for event in output.signal_events}
    assert "entry_signal" in kinds
    assert "filtered_no_entry" in kinds  # decision trace != fill (§14)


def test_metrics_registry_maps_all_nine_defaults() -> None:
    output = run_engine("exec_key_2", initial_capital=Decimal("10000"), item_count=1)
    values = derive_metric_values(output.summary)
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
