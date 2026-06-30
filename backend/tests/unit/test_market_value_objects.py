"""Market value-object + analysis-decision unit tests (doc 11, AT #5)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from entropia.application.jobs.market_data import (
    AnalysisOutcome,
    ParsedDataset,
    decide_outcome,
    evaluate_rows,
)
from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    ResolutionKind,
    TimezoneMode,
)
from entropia.domain.market_data.value_objects import (
    CoverageSlice,
    Resolution,
    TimezoneSpec,
)
from entropia.shared.errors import TimezoneRequired, ValidationError


def test_custom_timezone_requires_iana() -> None:
    with pytest.raises(TimezoneRequired):
        TimezoneSpec(mode=TimezoneMode.CUSTOM, iana=None)


def test_custom_timezone_invalid_iana_rejected() -> None:
    with pytest.raises(ValidationError):
        TimezoneSpec(mode=TimezoneMode.CUSTOM, iana="Not/AZone")


def test_custom_timezone_valid_resolves() -> None:
    spec = TimezoneSpec(mode=TimezoneMode.CUSTOM, iana="America/New_York")
    assert spec.zone.key == "America/New_York"


def test_utc_mode_resolves_without_iana() -> None:
    assert TimezoneSpec(mode=TimezoneMode.UTC).zone.key == "UTC"


def test_exchange_mode_rejects_iana() -> None:
    with pytest.raises(ValidationError):
        TimezoneSpec(mode=TimezoneMode.EXCHANGE, iana="UTC")


def test_bar_resolution_requires_value() -> None:
    with pytest.raises(ValidationError):
        Resolution(kind=ResolutionKind.BAR, value=None)
    assert Resolution(kind=ResolutionKind.BAR, value="15m").value == "15m"


def test_coverage_slice_rejects_inverted_interval() -> None:
    start = datetime(2026, 1, 2, tzinfo=UTC)
    end = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        CoverageSlice(start=start, end=end)


def test_decide_outcome_clean_data_verifies() -> None:
    assert decide_outcome(ValidationStatus.PASS) == MarketRevisionState.VERIFIED


def test_decide_outcome_warning_needs_review() -> None:
    assert decide_outcome(ValidationStatus.WARNING) == MarketRevisionState.NEEDS_REVIEW


def test_decide_outcome_blocking_needs_review() -> None:
    assert decide_outcome(ValidationStatus.BLOCKING_FAIL) == MarketRevisionState.NEEDS_REVIEW


def test_evaluate_rows_aggregates_worst_severity() -> None:
    parsed = ParsedDataset(
        market_data_type=MarketDataType.OHLCV,
        columns=["timestamp", "open", "high", "low", "close"],
        rows=[
            {"open": "10", "high": "12", "low": "9", "close": "11"},
            {"open": "10", "high": "8", "low": "9", "close": "11"},  # high<close -> block
        ],
    )
    outcome = evaluate_rows(parsed)
    assert isinstance(outcome, AnalysisOutcome)
    assert outcome.status == ValidationStatus.BLOCKING_FAIL
    assert outcome.rows_checked == 2
    assert outcome.next_state == MarketRevisionState.NEEDS_REVIEW


def test_evaluate_rows_all_clean_verifies() -> None:
    parsed = ParsedDataset(
        market_data_type=MarketDataType.SPREAD_EXECUTION,
        columns=["timestamp", "bid", "ask"],
        rows=[{"bid": "9", "ask": "10"}, {"bid": "9.5", "ask": "10.5"}],
    )
    outcome = evaluate_rows(parsed)
    assert outcome.status == ValidationStatus.PASS
    assert outcome.next_state == MarketRevisionState.VERIFIED
