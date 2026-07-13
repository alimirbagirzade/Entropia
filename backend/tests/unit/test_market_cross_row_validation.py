"""Pure cross-row market-data validation (doc 11 §7.4).

The per-row rules cannot see relationships between rows. These cover the aggregate
findings: timestamp monotonicity + duplicate (BLOCKING_FAIL, keep corrupt series
out of the money engine), declared cadence gaps (WARNING + coverage segments) and
undeclared spread units (WARNING).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.market_data.enums import MarketDataType, ResolutionKind
from entropia.domain.market_data.validation_rules import (
    cadence_seconds,
    evaluate_cross_row,
    parse_timestamp,
)


def _ohlcv(ts: Any) -> dict[str, Any]:
    return {"timestamp": ts, "open": "1", "high": "2", "low": "1", "close": "2", "volume": "10"}


def test_clean_monotonic_ohlcv_passes_with_one_coverage_segment() -> None:
    rows = [_ohlcv(f"2026-01-01T00:0{i}:00Z") for i in range(3)]  # 00:00,01,02 at 1m
    report = evaluate_cross_row(
        MarketDataType.OHLCV,
        rows,
        resolution_kind=ResolutionKind.BAR,
        resolution_value="1m",
    )
    assert report.worst == ValidationStatus.PASS
    assert report.issues == ()
    assert len(report.coverage) == 1
    segment = report.coverage[0]
    assert segment.row_count == 3
    assert segment.gap_seconds is None


def test_non_monotonic_timestamps_block() -> None:
    rows = [_ohlcv("2026-01-01T00:02:00Z"), _ohlcv("2026-01-01T00:01:00Z")]
    report = evaluate_cross_row(MarketDataType.OHLCV, rows)
    assert report.worst == ValidationStatus.BLOCKING_FAIL
    assert {i.rule_code for i in report.issues} == {"TIMESTAMP_NON_MONOTONIC"}


def test_duplicate_timestamps_block() -> None:
    rows = [_ohlcv("2026-01-01T00:00:00Z"), _ohlcv("2026-01-01T00:00:00Z")]
    report = evaluate_cross_row(MarketDataType.OHLCV, rows)
    assert report.worst == ValidationStatus.BLOCKING_FAIL
    issue = next(i for i in report.issues if i.rule_code == "DUPLICATE_TIMESTAMP")
    assert issue.occurrences == 1
    assert issue.sample == {"duplicate_groups": 1}


def test_unresolvable_timestamp_blocks() -> None:
    rows = [_ohlcv("not-a-time"), _ohlcv("2026-01-01T00:00:00Z")]
    report = evaluate_cross_row(MarketDataType.OHLCV, rows)
    assert report.worst == ValidationStatus.BLOCKING_FAIL
    assert any(i.rule_code == "TIMESTAMP_UNRESOLVABLE" for i in report.issues)


def test_cadence_gap_warns_and_splits_coverage() -> None:
    rows = [
        _ohlcv("2026-01-01T00:00:00Z"),
        _ohlcv("2026-01-01T00:01:00Z"),
        _ohlcv("2026-01-01T00:10:00Z"),  # 9-minute gap at 1m cadence
    ]
    report = evaluate_cross_row(
        MarketDataType.OHLCV,
        rows,
        resolution_kind=ResolutionKind.BAR,
        resolution_value="1m",
    )
    assert report.worst == ValidationStatus.WARNING
    assert any(i.rule_code == "CADENCE_GAP" for i in report.issues)
    assert len(report.coverage) == 2
    first, second = report.coverage
    assert first.row_count == 2
    assert first.gap_seconds == Decimal("540.0")  # 00:10 - 00:01 = 540s
    assert second.row_count == 1
    assert second.gap_seconds is None


def test_cadence_gap_ignored_without_bar_resolution() -> None:
    rows = [_ohlcv("2026-01-01T00:00:00Z"), _ohlcv("2026-01-01T01:00:00Z")]
    report = evaluate_cross_row(MarketDataType.OHLCV, rows)  # no declared cadence
    assert report.worst == ValidationStatus.PASS
    assert report.coverage == ()


def test_spread_unit_undeclared_warns() -> None:
    rows = [{"timestamp": "2026-01-01T00:00:00Z", "bid": "1", "ask": "2"}]
    report = evaluate_cross_row(MarketDataType.SPREAD_EXECUTION, rows)
    assert report.worst == ValidationStatus.WARNING
    assert any(i.rule_code == "SPREAD_UNIT_UNDECLARED" for i in report.issues)


def test_spread_unit_declared_passes() -> None:
    rows = [{"timestamp": "2026-01-01T00:00:00Z", "bid": "1", "ask": "2"}]
    report = evaluate_cross_row(MarketDataType.SPREAD_EXECUTION, rows, spread_unit="bps")
    assert report.worst == ValidationStatus.PASS
    assert report.issues == ()


def test_tick_type_has_no_cadence_or_spread_findings() -> None:
    rows = [{"timestamp": "2026-01-01T00:00:00Z", "price": "1"}]
    report = evaluate_cross_row(
        MarketDataType.TICK_TRADES,
        rows,
        resolution_kind=ResolutionKind.BAR,
        resolution_value="1m",
    )
    assert report.worst == ValidationStatus.PASS
    assert report.coverage == ()  # coverage segments are OHLCV-only


def test_empty_dataset_is_clean() -> None:
    report = evaluate_cross_row(MarketDataType.OHLCV, [])
    assert report.worst == ValidationStatus.PASS
    assert report.issues == ()
    assert report.coverage == ()


@pytest.mark.parametrize(
    "value",
    [
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00",  # naive -> read as UTC
        1767225600,  # epoch seconds
        1767225600000,  # epoch milliseconds
        "1767225600",  # epoch seconds as string
    ],
)
def test_parse_timestamp_forms(value: Any) -> None:
    assert parse_timestamp(value) == datetime(2026, 1, 1, tzinfo=UTC)


def test_parse_timestamp_rejects_garbage_and_bool() -> None:
    assert parse_timestamp("nope") is None
    assert parse_timestamp(None) is None
    assert parse_timestamp(True) is None  # bool is an int subclass, must be rejected


def test_cadence_seconds_forms() -> None:
    assert cadence_seconds("1m") == 60
    assert cadence_seconds("15m") == 900
    assert cadence_seconds("1h") == 3600
    assert cadence_seconds("1D") == 86400  # doc uses uppercase D
    assert cadence_seconds("60") == 3600  # bare integer -> minutes
    assert cadence_seconds(None) is None
    assert cadence_seconds("garbage") is None
    assert cadence_seconds("0m") is None
