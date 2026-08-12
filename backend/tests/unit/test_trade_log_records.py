"""Unit tests for the pure Trade Log ledger parser/normalizer (doc 05 §5.4, §10.3).

Covers TL-05 (required column), TL-06 (delimiters), TL-07 (timezone + exit<entry),
TL-08 (price integrity + non-destructive pnl warning), TL-09 (instrument scope),
plus deterministic record ids / content hash.
"""

from __future__ import annotations

from entropia.domain.trade_log.enums import RecordBatchStatus
from entropia.domain.trade_log.records import (
    BLOCKER_NO_ACCEPTED_TRADE_RECORDS,
    BLOCKER_REQUIRED_COLUMN_MISSING,
    BLOCKER_TIMEZONE_INVALID,
    REASON_ENTRY_PRICE_INVALID,
    REASON_EXIT_BEFORE_ENTRY,
    REASON_EXIT_PRICE_INVALID,
    REASON_INSTRUMENT_MISMATCH,
    WARN_PNL_MISMATCH,
    normalize_trade_rows,
    parse_delimited,
    records_content_hash,
)

_HEADER = "direction,entry_time,entry_price,exit_time,exit_price,size,fees,pnl,symbol"
_GOOD = "\n".join(
    [
        _HEADER,
        "Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850,1.0,2.1,750,BTCUSDT",
        "Short,2024-01-02 09:15,43000,2024-01-02 18:00,41950,1.0,2.4,1050,BTCUSDT",
    ]
).encode("utf-8")


def _run(data: bytes, *, tz: str = "UTC", instrument_id: str = "BTCUSDT"):
    columns, rows = parse_delimited(data)
    return normalize_trade_rows(columns, rows, source_timezone=tz, instrument_id=instrument_id)


def test_good_ledger_all_accepted() -> None:
    outcome = _run(_GOOD)
    assert outcome.status == RecordBatchStatus.SUCCEEDED
    assert outcome.accepted_count == 2
    assert outcome.skipped_count == 0
    assert outcome.warning_count == 0
    assert outcome.earliest_entry_time is not None
    assert outcome.latest_exit_time is not None
    # canonical UTC ISO timestamps
    assert outcome.accepted[0].entry_time.endswith("+00:00")
    assert outcome.accepted[0].direction == "long"
    assert outcome.accepted[1].direction == "short"


def test_delimiters_produce_equivalent_records() -> None:
    row = "Long,2024-01-01 10:00,100,2024-01-01 12:00,110"
    base = _run(("direction,entry_time,entry_price,exit_time,exit_price\n" + row).encode())
    for sep in (";", "\t", "|"):
        header = sep.join(["direction", "entry_time", "entry_price", "exit_time", "exit_price"])
        body = sep.join(["Long", "2024-01-01 10:00", "100", "2024-01-01 12:00", "110"])
        outcome = _run((header + "\n" + body).encode())
        assert outcome.status == RecordBatchStatus.SUCCEEDED
        assert outcome.accepted_count == 1
        assert outcome.accepted[0].record_id == base.accepted[0].record_id


def test_missing_required_column_is_whole_file_blocker() -> None:
    data = "direction,entry_time,entry_price,exit_time\nLong,2024-01-01 10:00,100,2024-01-01 12:00"
    outcome = _run(data.encode())
    assert outcome.status == RecordBatchStatus.FAILED
    assert outcome.blocker_code == BLOCKER_REQUIRED_COLUMN_MISSING
    assert outcome.accepted_count == 0


def test_invalid_timezone_is_whole_file_blocker() -> None:
    outcome = _run(_GOOD, tz="Not/AZone")
    assert outcome.status == RecordBatchStatus.FAILED
    assert outcome.blocker_code == BLOCKER_TIMEZONE_INVALID


def test_exit_before_entry_skips_row() -> None:
    data = "\n".join(
        [
            "direction,entry_time,entry_price,exit_time,exit_price",
            "Long,2024-01-01 15:00,100,2024-01-01 10:00,110",
        ]
    )
    outcome = _run(data.encode())
    assert outcome.status == RecordBatchStatus.FAILED
    assert outcome.blocker_code == BLOCKER_NO_ACCEPTED_TRADE_RECORDS
    assert outcome.skipped[0].reason_code == REASON_EXIT_BEFORE_ENTRY


def test_non_positive_prices_skip_rows() -> None:
    data = "\n".join(
        [
            "direction,entry_time,entry_price,exit_time,exit_price",
            "Long,2024-01-01 10:00,0,2024-01-01 12:00,110",
            "Short,2024-01-02 10:00,100,2024-01-02 12:00,-5",
        ]
    )
    outcome = _run(data.encode())
    reasons = {r.reason_code for r in outcome.skipped}
    assert REASON_ENTRY_PRICE_INVALID in reasons
    assert REASON_EXIT_PRICE_INVALID in reasons


def test_pnl_mismatch_is_a_non_destructive_warning() -> None:
    data = "\n".join(
        [
            "direction,entry_time,entry_price,exit_time,exit_price,size,pnl",
            "Long,2024-01-01 10:00,100,2024-01-01 12:00,110,1.0,999",
        ]
    )
    outcome = _run(data.encode())
    assert outcome.status == RecordBatchStatus.SUCCEEDED
    assert outcome.accepted_count == 1
    # reported pnl is preserved, never overwritten; only flagged.
    assert outcome.accepted[0].pnl == "999"
    assert WARN_PNL_MISMATCH in outcome.accepted[0].warnings


def test_out_of_scope_symbol_is_skipped() -> None:
    data = "\n".join(
        [
            "direction,entry_time,entry_price,exit_time,exit_price,symbol",
            "Long,2024-01-01 10:00,100,2024-01-01 12:00,110,ETHUSDT",
        ]
    )
    outcome = _run(data.encode(), instrument_id="BTCUSDT")
    assert outcome.status == RecordBatchStatus.FAILED
    assert outcome.skipped[0].reason_code == REASON_INSTRUMENT_MISMATCH


def test_direction_aliases_normalize() -> None:
    data = "\n".join(
        [
            "direction,entry_time,entry_price,exit_time,exit_price",
            "buy,2024-01-01 10:00,100,2024-01-01 12:00,110",
            "-1,2024-01-02 10:00,100,2024-01-02 12:00,90",
        ]
    )
    outcome = _run(data.encode())
    assert [r.direction for r in outcome.accepted] == ["long", "short"]


def test_content_hash_is_deterministic() -> None:
    a = _run(_GOOD)
    b = _run(_GOOD)
    h = records_content_hash(a.accepted)
    assert h == records_content_hash(b.accepted)
    assert len(h) == 64
    assert [r.record_id for r in a.accepted] == [r.record_id for r in b.accepted]


def test_capitalized_headers_are_accepted() -> None:
    # Real broker/MT4/MT5 exports emit capitalized headers — they must parse, not
    # silently skip every row (code-review HIGH regression guard).
    data = "\n".join(
        [
            "Direction,Entry_Time,Entry_Price,Exit_Time,Exit_Price,Symbol",
            "Long,2024-01-01 10:00,100,2024-01-01 12:00,110,BTCUSDT",
        ]
    )
    outcome = _run(data.encode(), instrument_id="BTCUSDT")
    assert outcome.status == RecordBatchStatus.SUCCEEDED
    assert outcome.accepted_count == 1
    assert outcome.accepted[0].direction == "long"


def test_quoted_field_may_contain_the_active_delimiter() -> None:
    # TL-06: the parser is quoting-aware, so a comma living INSIDE a quoted field
    # must not shift the columns to its right. A naive `line.split(",")` would read
    # exit_price out of the note column and skip the row; asserting the accepted
    # prices is what distinguishes the two implementations.
    data = "\n".join(
        [
            "direction,entry_time,entry_price,exit_time,exit_price,note",
            'Long,2024-01-01 10:00,100,2024-01-01 12:00,110,"scaled in, then out"',
        ]
    )
    outcome = _run(data.encode())
    assert outcome.status == RecordBatchStatus.SUCCEEDED
    assert outcome.skipped_count == 0
    assert outcome.accepted[0].entry_price == "100"
    assert outcome.accepted[0].exit_price == "110"


def test_skipped_row_names_its_source_row_number() -> None:
    # TL-07: the import report must name WHICH row was rejected, not merely that a
    # rejection happened. Two good rows precede the bad one so the index is
    # discriminating — a hard-coded 0 would pass a single-row fixture.
    data = "\n".join(
        [
            "direction,entry_time,entry_price,exit_time,exit_price",
            "Long,2024-01-01 10:00,100,2024-01-01 12:00,110",
            "Long,2024-01-02 10:00,100,2024-01-02 12:00,110",
            "Short,2024-01-03 15:00,100,2024-01-03 10:00,110",
        ]
    )
    outcome = _run(data.encode())
    assert outcome.status == RecordBatchStatus.SUCCEEDED
    assert outcome.accepted_count == 2
    assert outcome.skipped_count == 1
    skipped = outcome.skipped[0]
    assert skipped.reason_code == REASON_EXIT_BEFORE_ENTRY
    # zero-based index into the DATA rows (the header is not a row) -> the third one
    assert skipped.row_index == 2


def test_non_finite_prices_skip_rows() -> None:
    # TL-08: `Decimal("NaN")` and `Decimal("inf")` PARSE — only the explicit
    # is_finite() guard rejects them, so a fixture of 0/-5 alone cannot prove this.
    for literal in ("NaN", "inf", "-inf", "Infinity"):
        data = "\n".join(
            [
                "direction,entry_time,entry_price,exit_time,exit_price",
                f"Long,2024-01-01 10:00,{literal},2024-01-01 12:00,110",
                f"Short,2024-01-02 10:00,100,2024-01-02 12:00,{literal}",
            ]
        )
        outcome = _run(data.encode())
        assert outcome.status == RecordBatchStatus.FAILED, literal
        assert outcome.blocker_code == BLOCKER_NO_ACCEPTED_TRADE_RECORDS, literal
        assert [(r.row_index, r.reason_code) for r in outcome.skipped] == [
            (0, REASON_ENTRY_PRICE_INVALID),
            (1, REASON_EXIT_PRICE_INVALID),
        ], literal
