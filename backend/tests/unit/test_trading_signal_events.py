"""Unit tests for the pure signal-event parser + normalizer (doc 04 §5.1).

Infra-free: exercises ``domain.trading_signal.events`` directly (no DB/MinIO). The
clock is seamed via ``now`` so event/available times are deterministic.
"""

from __future__ import annotations

from datetime import UTC, datetime

from entropia.domain.trading_signal.enums import NormalizedRevisionStatus
from entropia.domain.trading_signal.events import (
    BLOCKER_AVAILABLE_TIME_REQUIRED,
    BLOCKER_LEGACY_TRADE_LOG_SCHEMA,
    REASON_AVAILABLE_TIME_INVALID,
    REASON_DUPLICATE_SOURCE_RECORD_ID,
    REASON_EVENT_TIME_FUTURE,
    REASON_INSTRUMENT_MISMATCH,
    REASON_INVALID_SIGNAL_DIRECTION,
    REASON_SIGNAL_TYPE_UNMAPPED,
    events_content_hash,
    normalize_signal_rows,
    parse_delimited,
)

_NOW = datetime(2024, 6, 1, tzinfo=UTC)
_HEADER = "source_record_id,event_time,available_time,direction,signal_type"


def _csv(*rows: str, header: str = _HEADER) -> bytes:
    return ("\n".join([header, *rows])).encode("utf-8")


def _normalize(data: bytes, *, instrument_id: str = "BTCUSDT"):
    columns, rows = parse_delimited(data)
    return normalize_signal_rows(
        columns, rows, source_timezone="UTC", instrument_id=instrument_id, now=_NOW
    )


def test_parse_detects_semicolon_delimiter() -> None:
    columns, rows = parse_delimited(b"a;b;c\n1;2;3")
    assert columns == ["a", "b", "c"]
    assert rows == [{"a": "1", "b": "2", "c": "3"}]


def test_parse_detects_pipe_delimiter() -> None:
    columns, _rows = parse_delimited(b"a|b|c\n1|2|3")
    assert columns == ["a", "b", "c"]


def test_happy_path_accepts_and_records_earliest_available_time() -> None:
    outcome = _normalize(
        _csv(
            "r1,2024-05-01T10:00:00Z,2024-05-01T10:03:00Z,long,entry",
            "r2,2024-05-02T10:00:00Z,2024-05-02T10:01:00Z,sell,exit",
        )
    )
    assert outcome.status == NormalizedRevisionStatus.SUCCEEDED
    assert outcome.accepted_count == 2
    assert outcome.skipped_count == 0
    assert [e.direction for e in outcome.accepted] == ["long", "short"]
    assert [e.signal_type for e in outcome.accepted] == ["entry", "exit_hint"]
    # earliest available_time is the min across accepted events.
    assert outcome.earliest_available_time == datetime(2024, 5, 1, 10, 3, tzinfo=UTC)


def test_available_time_required_blocks_when_nothing_accepted() -> None:
    outcome = _normalize(_csv("r1,2024-05-01T10:00:00Z,,long,entry"))
    assert outcome.status == NormalizedRevisionStatus.FAILED
    assert outcome.accepted_count == 0
    assert outcome.blocker_code == BLOCKER_AVAILABLE_TIME_REQUIRED


def test_available_time_before_event_time_is_skipped() -> None:
    outcome = _normalize(_csv("r1,2024-05-01T10:00:00Z,2024-05-01T09:59:00Z,long,entry"))
    assert outcome.accepted_count == 0
    assert outcome.skipped[0].reason_code == REASON_AVAILABLE_TIME_INVALID


def test_future_event_time_is_skipped() -> None:
    outcome = _normalize(_csv("r1,2999-01-01T00:00:00Z,2999-01-01T00:00:00Z,long,entry"))
    assert outcome.accepted_count == 0
    assert outcome.skipped[0].reason_code == REASON_EVENT_TIME_FUTURE


def test_invalid_direction_is_skipped() -> None:
    outcome = _normalize(_csv("r1,2024-05-01T10:00:00Z,2024-05-01T10:00:00Z,sideways,entry"))
    assert outcome.accepted_count == 0
    assert outcome.skipped[0].reason_code == REASON_INVALID_SIGNAL_DIRECTION


def test_unmapped_signal_type_is_skipped() -> None:
    outcome = _normalize(_csv("r1,2024-05-01T10:00:00Z,2024-05-01T10:00:00Z,long,mystery"))
    assert outcome.accepted_count == 0
    assert outcome.skipped[0].reason_code == REASON_SIGNAL_TYPE_UNMAPPED


def test_instrument_mismatch_is_skipped() -> None:
    data = _csv(
        "r1,2024-05-01T10:00:00Z,2024-05-01T10:00:00Z,long,entry,ETHUSDT",
        header=_HEADER + ",symbol",
    )
    outcome = _normalize(data, instrument_id="BTCUSDT")
    assert outcome.accepted_count == 0
    assert outcome.skipped[0].reason_code == REASON_INSTRUMENT_MISMATCH


def test_duplicate_source_record_id_is_skipped() -> None:
    outcome = _normalize(
        _csv(
            "r1,2024-05-01T10:00:00Z,2024-05-01T10:00:00Z,long,entry",
            "r1,2024-05-02T10:00:00Z,2024-05-02T10:00:00Z,short,entry",
        )
    )
    assert outcome.accepted_count == 1
    assert outcome.skipped[0].reason_code == REASON_DUPLICATE_SOURCE_RECORD_ID


def test_legacy_trade_log_schema_is_a_whole_file_blocker() -> None:
    data = _csv(
        "2024-05-01T10:00:00Z,100,2024-05-01T12:00:00Z,110",
        header="entry_time,entry_price,exit_time,exit_price",
    )
    outcome = _normalize(data)
    assert outcome.status == NormalizedRevisionStatus.FAILED
    assert outcome.blocker_code == BLOCKER_LEGACY_TRADE_LOG_SCHEMA


def test_event_id_and_content_hash_are_deterministic() -> None:
    data = _csv("r1,2024-05-01T10:00:00Z,2024-05-01T10:03:00Z,long,entry")
    a = _normalize(data)
    b = _normalize(data)
    assert a.accepted[0].event_id == b.accepted[0].event_id
    assert a.accepted[0].event_id.startswith("sigevt_")
    assert events_content_hash(a.accepted) == events_content_hash(b.accepted)
    assert len(events_content_hash(a.accepted)) == 64


def test_naive_timestamp_localized_to_source_timezone() -> None:
    # A tz-naive event_time is localized via the source timezone (UTC here).
    columns, rows = parse_delimited(_csv("r1,2024-05-01T10:00:00,2024-05-01T10:00:00,long,entry"))
    outcome = normalize_signal_rows(
        columns, rows, source_timezone="UTC", instrument_id="BTCUSDT", now=_NOW
    )
    assert outcome.accepted_count == 1
    assert outcome.accepted[0].event_time == "2024-05-01T10:00:00+00:00"
