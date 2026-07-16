"""F-11 — the pure funding-schedule builder + available-time resolution (doc 12 §8.4).

DB-free. Covers ``build_funding_schedule`` (event→available time resolution, native column
resolution, drop-vs-fail-closed policy, ascending sort) and ``parse_utc``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from entropia.domain.backtest.funding import (
    build_funding_schedule,
    parse_utc,
    resolve_funding_columns,
)
from entropia.domain.research_data.enums import AvailableTimePolicy
from entropia.shared.errors import FundingSourceInvalid


def _rows() -> list[dict[str, object]]:
    return [
        {"event_time": "2024-01-02T00:00:00Z", "funding_rate": "0.0002"},
        {"event_time": "2024-01-01T00:00:00Z", "funding_rate": "0.0001"},
    ]


def test_same_as_event_time_sets_available_at_to_event_time_and_sorts_ascending() -> None:
    sched = build_funding_schedule(
        _rows(),
        source_revision_id="rd_1",
        columns=["event_time", "funding_rate"],
        policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
        delay_seconds=None,
    )
    assert sched.source_revision_id == "rd_1"
    assert [r.available_at for r in sched.records] == [
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 2, tzinfo=UTC),  # sorted ascending regardless of input order
    ]
    assert sched.records[0].available_at == sched.records[0].event_at
    assert sched.records[0].rate == Decimal("0.0001")


def test_fixed_delay_shifts_available_at_by_the_delay() -> None:
    sched = build_funding_schedule(
        [{"event_time": "2024-01-01T00:00:00Z", "funding_rate": "0.0001"}],
        source_revision_id="rd_1",
        columns=["event_time", "funding_rate"],
        policy=AvailableTimePolicy.FIXED_DELAY,
        delay_seconds=3600,
    )
    rec = sched.records[0]
    assert rec.event_at == datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    assert rec.available_at == datetime(2024, 1, 1, 1, 0, tzinfo=UTC)  # +3600s


def test_column_resolution_is_case_insensitive_over_the_candidates() -> None:
    assert resolve_funding_columns(["Event_At", "RATE"]) == ("Event_At", "RATE")
    assert resolve_funding_columns(["ts", "funding", "note"]) == ("ts", "funding")


def test_missing_time_or_rate_column_fails_closed() -> None:
    with pytest.raises(FundingSourceInvalid):
        resolve_funding_columns(["open", "high", "low"])  # no time/rate column
    with pytest.raises(FundingSourceInvalid):
        build_funding_schedule(
            [{"foo": "1", "bar": "2"}],
            source_revision_id="rd_1",
            columns=["foo", "bar"],
            policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
            delay_seconds=None,
        )


def test_unparseable_rows_are_dropped_but_valid_rows_kept() -> None:
    rows = [
        {"event_time": "not-a-date", "funding_rate": "0.001"},  # bad ts -> dropped
        {"event_time": "2024-01-01T00:00:00Z", "funding_rate": "nan"},  # non-finite -> dropped
        {"event_time": "2024-01-02T00:00:00Z", "funding_rate": "0.002"},  # kept
    ]
    sched = build_funding_schedule(
        rows,
        source_revision_id="rd_1",
        columns=["event_time", "funding_rate"],
        policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
        delay_seconds=None,
    )
    assert len(sched.records) == 1
    assert sched.records[0].rate == Decimal("0.002")


def test_all_rows_dropped_fails_closed_never_silent_zero_cost() -> None:
    with pytest.raises(FundingSourceInvalid):
        build_funding_schedule(
            [{"event_time": "bad", "funding_rate": "bad"}],
            source_revision_id="rd_1",
            columns=["event_time", "funding_rate"],
            policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
            delay_seconds=None,
        )


def test_empty_source_is_an_empty_schedule_not_an_error() -> None:
    # No rows at all is a legitimately empty (inert) schedule — distinct from an all-dropped
    # non-empty source, which is a fail-closed configuration error.
    sched = build_funding_schedule(
        [],
        source_revision_id="rd_1",
        columns=["event_time", "funding_rate"],
        policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
        delay_seconds=None,
    )
    assert sched.records == ()
    assert not sched


@pytest.mark.parametrize(
    "policy",
    [AvailableTimePolicy.PROVIDER_PUBLISH_TIMESTAMP, AvailableTimePolicy.CUSTOM_DOCUMENTED_RULE],
)
def test_unresolvable_policies_fail_closed(policy: AvailableTimePolicy) -> None:
    # provider/custom rules need per-record inputs this generic reader does not carry — they
    # must fail closed rather than silently degrade to event time (the exact leakage forbidden).
    with pytest.raises(FundingSourceInvalid):
        build_funding_schedule(
            _rows(),
            source_revision_id="rd_1",
            columns=["event_time", "funding_rate"],
            policy=policy,
            delay_seconds=None,
        )


def test_rate_accepts_int_float_decimal_and_string() -> None:
    rows = [
        {"event_time": "2024-01-01T00:00:00Z", "funding_rate": 1},
        {"event_time": "2024-01-02T00:00:00Z", "funding_rate": 0.0002},
        {"event_time": "2024-01-03T00:00:00Z", "funding_rate": Decimal("0.0003")},
        {"event_time": "2024-01-04T00:00:00Z", "funding_rate": "0.0004"},
    ]
    sched = build_funding_schedule(
        rows,
        source_revision_id="rd_1",
        columns=["event_time", "funding_rate"],
        policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
        delay_seconds=None,
    )
    assert len(sched.records) == 4


def test_parse_utc_handles_z_suffix_naive_datetime_and_none() -> None:
    assert parse_utc("2024-01-01T00:00:00Z") == datetime(2024, 1, 1, tzinfo=UTC)
    assert parse_utc(datetime(2024, 1, 1)) == datetime(2024, 1, 1, tzinfo=UTC)  # naive -> UTC
    assert parse_utc(None) is None
    assert parse_utc("") is None
    assert parse_utc("garbage") is None
