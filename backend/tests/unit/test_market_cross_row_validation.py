"""Pure cross-row market-data validation (doc 11 §7.4).

The per-row rules cannot see relationships between rows. These cover the aggregate
findings: timestamp monotonicity + duplicate (BLOCKING_FAIL, keep corrupt series
out of the money engine), declared cadence gaps (WARNING + coverage segments) and
undeclared spread units (WARNING).

Coverage segmentation is exercised on BOTH paths (O-29): the cadence path for declared
OHLCV bars, and the consecutive-UTC-day path for cadence-less tick/trades, spread/
execution and unreadable-cadence bars.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.market_data.enums import MarketDataType, ResolutionKind
from entropia.domain.market_data.validation_rules import (
    cadence_seconds,
    evaluate_cross_row,
    parse_timestamp,
    resolve_timestamp,
)

_UTC = ZoneInfo("UTC")
_NEW_YORK = ZoneInfo("America/New_York")


def _ohlcv(ts: Any) -> dict[str, Any]:
    return {"timestamp": ts, "open": "1", "high": "2", "low": "1", "close": "2", "volume": "10"}


def test_clean_monotonic_ohlcv_passes_with_one_coverage_segment() -> None:
    rows = [_ohlcv(f"2026-01-01T00:0{i}:00Z") for i in range(3)]  # 00:00,01,02 at 1m
    report = evaluate_cross_row(
        MarketDataType.OHLCV,
        rows,
        source_zone=_UTC,
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
    report = evaluate_cross_row(MarketDataType.OHLCV, rows, source_zone=_UTC)
    assert report.worst == ValidationStatus.BLOCKING_FAIL
    assert {i.rule_code for i in report.issues} == {"TIMESTAMP_NON_MONOTONIC"}


def test_duplicate_timestamps_block() -> None:
    rows = [_ohlcv("2026-01-01T00:00:00Z"), _ohlcv("2026-01-01T00:00:00Z")]
    report = evaluate_cross_row(MarketDataType.OHLCV, rows, source_zone=_UTC)
    assert report.worst == ValidationStatus.BLOCKING_FAIL
    issue = next(i for i in report.issues if i.rule_code == "DUPLICATE_TIMESTAMP")
    assert issue.occurrences == 1
    assert issue.sample == {"duplicate_groups": 1}


def test_unresolvable_timestamp_blocks() -> None:
    rows = [_ohlcv("not-a-time"), _ohlcv("2026-01-01T00:00:00Z")]
    report = evaluate_cross_row(MarketDataType.OHLCV, rows, source_zone=_UTC)
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
        source_zone=_UTC,
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
    """No declared cadence -> no CADENCE_GAP verdict, but coverage is still recorded.

    O-29: an unreadable/absent cadence used to drop the revision's coverage entirely,
    so an analyzed dataset was indistinguishable from an un-analyzed one."""
    rows = [_ohlcv("2026-01-01T00:00:00Z"), _ohlcv("2026-01-01T01:00:00Z")]
    report = evaluate_cross_row(MarketDataType.OHLCV, rows, source_zone=_UTC)  # no declared cadence
    assert report.worst == ValidationStatus.PASS
    assert not any(i.rule_code == "CADENCE_GAP" for i in report.issues)
    assert len(report.coverage) == 1  # same UTC day -> one contiguous segment
    segment = report.coverage[0]
    assert segment.start_at == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert segment.end_at == datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
    assert segment.row_count == 2
    assert segment.gap_seconds is None


def test_spread_unit_undeclared_warns() -> None:
    rows = [{"timestamp": "2026-01-01T00:00:00Z", "bid": "1", "ask": "2"}]
    report = evaluate_cross_row(MarketDataType.SPREAD_EXECUTION, rows, source_zone=_UTC)
    assert report.worst == ValidationStatus.WARNING
    assert any(i.rule_code == "SPREAD_UNIT_UNDECLARED" for i in report.issues)


def test_spread_unit_declared_passes() -> None:
    rows = [{"timestamp": "2026-01-01T00:00:00Z", "bid": "1", "ask": "2"}]
    report = evaluate_cross_row(
        MarketDataType.SPREAD_EXECUTION, rows, source_zone=_UTC, spread_unit="bps"
    )
    assert report.worst == ValidationStatus.PASS
    assert report.issues == ()


def test_tick_type_has_no_cadence_or_spread_findings_but_records_coverage() -> None:
    """A tick revision never inherits a bar cadence, yet it still records coverage.

    O-29: the cadence is ignored for the tick type (no CADENCE_GAP verdict can be
    fair against a step the data never declared), but the covered span is real and
    must reach ``dataset_coverage_slice`` — doc 11 §3.3 shows a Coverage value on
    the Tick / Trades registry row."""
    rows = [{"timestamp": "2026-01-01T00:00:00Z", "price": "1"}]
    report = evaluate_cross_row(
        MarketDataType.TICK_TRADES,
        rows,
        source_zone=_UTC,
        resolution_kind=ResolutionKind.BAR,
        resolution_value="1m",
    )
    assert report.worst == ValidationStatus.PASS
    assert not any(i.rule_code == "CADENCE_GAP" for i in report.issues)
    assert len(report.coverage) == 1
    assert report.coverage[0].row_count == 1
    assert report.coverage[0].gap_seconds is None


def test_tick_selected_sessions_split_into_one_segment_per_session() -> None:
    """Doc 11 §3.3's "Selected 2025 sessions" tick row: disjoint days, disjoint slices.

    A single min->max span would read as continuous coverage over a range the dataset
    only samples. Consecutive covered UTC days stay in one segment; a skipped day
    closes it and records the real distance to the next observed instant."""
    rows = [
        {"timestamp": "2025-03-03T09:00:00Z", "price": "1"},
        {"timestamp": "2025-03-03T17:00:00Z", "price": "1"},
        {"timestamp": "2025-03-04T09:00:00Z", "price": "1"},  # next day -> same segment
        {"timestamp": "2025-06-10T09:00:00Z", "price": "1"},  # months later -> new segment
    ]
    report = evaluate_cross_row(MarketDataType.TICK_TRADES, rows, source_zone=_UTC)
    assert report.worst == ValidationStatus.PASS
    assert len(report.coverage) == 2
    first, second = report.coverage
    assert first.start_at == datetime(2025, 3, 3, 9, 0, tzinfo=UTC)
    assert first.end_at == datetime(2025, 3, 4, 9, 0, tzinfo=UTC)
    assert first.row_count == 3
    # The real distance to the next observed instant, not an inferred cadence.
    assert first.gap_seconds == Decimal(
        str((datetime(2025, 6, 10, 9, 0) - datetime(2025, 3, 4, 9, 0)).total_seconds())
    )
    assert second.start_at == second.end_at == datetime(2025, 6, 10, 9, 0, tzinfo=UTC)
    assert second.row_count == 1
    assert second.gap_seconds is None


def test_spread_execution_records_coverage_alongside_its_unit_finding() -> None:
    """Spread/execution is event-based too: coverage is recorded on the day boundary.

    The undeclared-unit WARNING (§7.4) is orthogonal — a WARNING revision still has a
    real covered span to pin in the run manifest."""
    rows = [
        {"timestamp": "2026-02-01T00:00:00Z", "bid": "1", "ask": "2"},
        {"timestamp": "2026-02-09T00:00:00Z", "bid": "1", "ask": "2"},
    ]
    report = evaluate_cross_row(MarketDataType.SPREAD_EXECUTION, rows, source_zone=_UTC)
    assert report.worst == ValidationStatus.WARNING
    assert any(i.rule_code == "SPREAD_UNIT_UNDECLARED" for i in report.issues)
    assert len(report.coverage) == 2
    assert report.coverage[0].gap_seconds == Decimal("691200.0")  # 8 days
    assert report.coverage[1].gap_seconds is None


def test_empty_dataset_is_clean() -> None:
    report = evaluate_cross_row(MarketDataType.OHLCV, [], source_zone=_UTC)
    assert report.worst == ValidationStatus.PASS
    assert report.issues == ()
    assert report.coverage == ()


@pytest.mark.parametrize(
    "value",
    [
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00",  # naive -> localized in the declared source zone
        1767225600,  # epoch seconds
        1767225600000,  # epoch milliseconds
        "1767225600",  # epoch seconds as string
    ],
)
def test_parse_timestamp_forms(value: Any) -> None:
    assert parse_timestamp(value, source_zone=_UTC) == datetime(2026, 1, 1, tzinfo=UTC)


def test_parse_timestamp_rejects_garbage_and_bool() -> None:
    assert parse_timestamp("nope", source_zone=_UTC) is None
    assert parse_timestamp(None, source_zone=_UTC) is None
    assert (
        parse_timestamp(True, source_zone=_UTC) is None
    )  # bool is an int subclass, must be rejected


def test_cadence_seconds_forms() -> None:
    assert cadence_seconds("1m") == 60
    assert cadence_seconds("15m") == 900
    assert cadence_seconds("1h") == 3600
    assert cadence_seconds("1D") == 86400  # doc uses uppercase D
    assert cadence_seconds("60") == 3600  # bare integer -> minutes
    assert cadence_seconds(None) is None
    assert cadence_seconds("garbage") is None
    assert cadence_seconds("0m") is None


# --------------------------------------------------------------------------- #
# K-01 — the declared timezone is actually applied (doc 11 §7.3 step 5, §9.1)
# --------------------------------------------------------------------------- #


def test_naive_timestamp_is_localized_in_new_york_not_read_as_utc() -> None:
    # 09:30 New York on a summer date is EDT (UTC-4) -> 13:30 UTC, NOT 09:30 UTC.
    parsed = resolve_timestamp("2024-07-15T09:30:00", source_zone=_NEW_YORK)
    assert parsed.moment == datetime(2024, 7, 15, 13, 30, tzinfo=UTC)
    assert parsed.timezone_unresolved is False


def test_naive_timestamp_is_localized_in_new_york_across_the_dst_boundary() -> None:
    # The same wall clock in January is EST (UTC-5) -> 14:30 UTC. A fixed offset
    # would get one of the two wrong; ZoneInfo gets both right.
    assert parse_timestamp("2024-01-15T09:30:00", source_zone=_NEW_YORK) == datetime(
        2024, 1, 15, 14, 30, tzinfo=UTC
    )


def test_naive_timestamp_is_localized_in_istanbul() -> None:
    # Istanbul is a fixed UTC+3 year-round -> 09:30 local is 06:30 UTC.
    assert parse_timestamp(
        "2024-07-15T09:30:00", source_zone=ZoneInfo("Asia/Istanbul")
    ) == datetime(2024, 7, 15, 6, 30, tzinfo=UTC)


def test_naive_timestamp_under_utc_zone_is_unchanged() -> None:
    parsed = resolve_timestamp("2024-07-15T09:30:00", source_zone=_UTC)
    assert parsed.moment == datetime(2024, 7, 15, 9, 30, tzinfo=UTC)
    assert parsed.timezone_unresolved is False


def test_naive_timestamp_without_a_resolvable_zone_is_unresolved_never_utc() -> None:
    """K-01's core: no silent UTC fallback when the declaration resolves to nothing."""
    parsed = resolve_timestamp("2024-07-15T09:30:00", source_zone=None)
    assert parsed.moment is None
    assert parsed.timezone_unresolved is True


def test_offset_carrying_timestamp_ignores_the_source_zone() -> None:
    # An explicit offset is already an instant; the declared zone must not re-shift it.
    assert parse_timestamp("2024-07-15T09:30:00-04:00", source_zone=ZoneInfo("Asia/Tokyo")) == (
        datetime(2024, 7, 15, 13, 30, tzinfo=UTC)
    )


def test_epoch_is_absolute_and_needs_no_source_zone() -> None:
    parsed = resolve_timestamp(1720000000, source_zone=None)
    assert parsed.moment == datetime.fromtimestamp(1720000000, UTC)
    assert parsed.timezone_unresolved is False


def test_bare_date_is_localized_in_the_source_zone() -> None:
    from datetime import date

    # An ambiguous date (doc 11 §9.1) — midnight in New York, not midnight UTC.
    assert parse_timestamp(date(2024, 7, 15), source_zone=_NEW_YORK) == datetime(
        2024, 7, 15, 4, 0, tzinfo=UTC
    )


def test_bare_date_without_a_resolvable_zone_is_unresolved() -> None:
    from datetime import date

    assert resolve_timestamp(date(2024, 7, 15), source_zone=None).timezone_unresolved is True


def test_garbage_is_unparseable_not_timezone_unresolved() -> None:
    """The two blocking findings must stay distinguishable in the validation report."""
    parsed = resolve_timestamp("not-a-time", source_zone=None)
    assert parsed.moment is None
    assert parsed.timezone_unresolved is False


def test_cross_row_blocks_naive_rows_with_the_canonical_timezone_code() -> None:
    rows = [_ohlcv("2026-01-01T00:00:00"), _ohlcv("2026-01-01T00:01:00")]
    report = evaluate_cross_row(MarketDataType.OHLCV, rows, source_zone=None)
    assert report.worst == ValidationStatus.BLOCKING_FAIL
    issue = next(i for i in report.issues if i.rule_code == "MARKET_DATA_TIMEZONE_UNRESOLVED")
    assert issue.occurrences == 2
    # Distinct from the garbage-cell finding, so remediation guidance can differ.
    assert not any(i.rule_code == "TIMESTAMP_UNRESOLVABLE" for i in report.issues)


def test_cross_row_orders_rows_by_the_localized_instant_not_the_wall_clock() -> None:
    """Two rows monotonic as wall-clock digits, but out of order as real instants."""
    rows = [
        {**_ohlcv("2024-07-15T09:00:00-04:00"), "timestamp": "2024-07-15T09:00:00-04:00"},
        {**_ohlcv("2024-07-15T10:00:00-07:00"), "timestamp": "2024-07-15T10:00:00-07:00"},
    ]
    # 13:00Z then 17:00Z -> monotonic. Same digits read naively would also look fine,
    # but the coverage segment must carry the true instants.
    report = evaluate_cross_row(MarketDataType.OHLCV, rows, source_zone=_UTC)
    assert report.worst == ValidationStatus.PASS
