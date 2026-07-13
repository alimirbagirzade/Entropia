"""Unit tests for the shared column-mapping resolver + its use in the TL/TS
importers (GAP-22, doc 04 §5.1, doc 05 §5.2/§5.4).

Covers: explicit-mapping precedence, case normalization, single-alias resolution,
ambiguity fail-closed (never inferred), invalid explicit mapping, and the end-to-end
effect through ``normalize_trade_rows`` / ``normalize_signal_rows`` — including the
spec rule that a legacy Trade Log ledger becomes a Trading Signal ONLY with an
explicit mapping.
"""

from __future__ import annotations

from entropia.domain.importing.column_mapping import (
    BLOCKER_AMBIGUOUS_COLUMN_MAPPING,
    BLOCKER_INVALID_COLUMN_MAPPING,
    mapping_hash,
    resolve_column_mapping,
)
from entropia.domain.trade_log.enums import RecordBatchStatus
from entropia.domain.trade_log.records import (
    BLOCKER_REQUIRED_COLUMN_MISSING,
    normalize_trade_rows,
    parse_delimited,
)
from entropia.domain.trading_signal.enums import NormalizedRevisionStatus
from entropia.domain.trading_signal.events import (
    BLOCKER_LEGACY_TRADE_LOG_SCHEMA,
)
from entropia.domain.trading_signal.events import (
    normalize_signal_rows as normalize_signal,
)
from entropia.domain.trading_signal.events import (
    parse_delimited as parse_signal,
)

_FIELDS = ("direction", "entry_time", "entry_price", "exit_time", "exit_price")
_ALIASES = {"side": "direction", "open_time": "entry_time", "close_time": "exit_time"}


# --------------------------------------------------------------------------- #
# Pure resolver                                                                #
# --------------------------------------------------------------------------- #


def test_exact_headers_need_no_rename() -> None:
    res = resolve_column_mapping(
        list(_FIELDS), canonical_fields=_FIELDS, alias_table=_ALIASES, explicit_mapping=None
    )
    assert res.blocker_code is None
    assert res.rename == {}
    assert res.applied is False
    assert res.resolved == {f: f for f in _FIELDS}


def test_case_normalized_headers_rename_to_canonical() -> None:
    res = resolve_column_mapping(
        ["Direction", "Entry_Time"],
        canonical_fields=("direction", "entry_time"),
        alias_table={},
        explicit_mapping=None,
    )
    assert res.blocker_code is None
    assert res.rename == {"Direction": "direction", "Entry_Time": "entry_time"}
    assert res.applied is True


def test_single_alias_resolves() -> None:
    res = resolve_column_mapping(
        ["side", "entry_time"],
        canonical_fields=("direction", "entry_time"),
        alias_table={"side": "direction"},
        explicit_mapping=None,
    )
    assert res.rename == {"side": "direction"}
    assert res.resolved == {"direction": "side", "entry_time": "entry_time"}


def test_two_aliases_for_one_absent_field_is_ambiguous_not_inferred() -> None:
    res = resolve_column_mapping(
        ["open_time", "started_at"],
        canonical_fields=("entry_time",),
        alias_table={"open_time": "entry_time", "started_at": "entry_time"},
        explicit_mapping=None,
    )
    assert res.blocker_code == BLOCKER_AMBIGUOUS_COLUMN_MAPPING
    assert res.rename == {}


def test_exact_header_wins_over_alias_no_ambiguity() -> None:
    # entry_time present exactly => open_time (an alias) is never consulted.
    res = resolve_column_mapping(
        ["entry_time", "open_time"],
        canonical_fields=("entry_time",),
        alias_table={"open_time": "entry_time"},
        explicit_mapping=None,
    )
    assert res.blocker_code is None
    assert res.rename == {}
    assert res.resolved == {"entry_time": "entry_time"}


def test_explicit_mapping_wins_over_alias_and_ambiguity() -> None:
    res = resolve_column_mapping(
        ["open_time", "started_at"],
        canonical_fields=("entry_time",),
        alias_table={"open_time": "entry_time", "started_at": "entry_time"},
        explicit_mapping={"entry_time": "started_at"},
    )
    assert res.blocker_code is None
    assert res.rename == {"started_at": "entry_time"}


def test_explicit_target_not_stolen_by_alias_for_other_field() -> None:
    # "profit" aliases to pnl, but the user explicitly maps it to size — the alias
    # resolver must NOT also claim it for pnl.
    res = resolve_column_mapping(
        ["profit", "entry_time"],
        canonical_fields=("size", "pnl", "entry_time"),
        alias_table={"profit": "pnl"},
        explicit_mapping={"size": "profit"},
    )
    assert res.blocker_code is None
    assert res.resolved["size"] == "profit"
    assert "pnl" not in res.resolved  # not stolen
    assert res.rename == {"profit": "size"}


def test_explicit_unknown_canonical_is_invalid() -> None:
    res = resolve_column_mapping(
        ["a"], canonical_fields=("direction",), alias_table={}, explicit_mapping={"bogus": "a"}
    )
    assert res.blocker_code == BLOCKER_INVALID_COLUMN_MAPPING


def test_explicit_missing_source_column_is_invalid() -> None:
    res = resolve_column_mapping(
        ["a"],
        canonical_fields=("direction",),
        alias_table={},
        explicit_mapping={"direction": "not_in_file"},
    )
    assert res.blocker_code == BLOCKER_INVALID_COLUMN_MAPPING


def test_mapping_hash_is_deterministic_and_order_independent() -> None:
    a = mapping_hash({"direction": "side", "entry_time": "open_time"})
    b = mapping_hash({"entry_time": "open_time", "direction": "side"})
    assert a == b and a.startswith("sha256:")


# --------------------------------------------------------------------------- #
# Trade Log normalize (doc 05 §5.4)                                            #
# --------------------------------------------------------------------------- #


def _tl(csv: str, **kw):
    columns, rows = parse_delimited(csv.encode("utf-8"))
    return normalize_trade_rows(columns, rows, source_timezone="UTC", instrument_id="BTCUSDT", **kw)


def test_tl_fully_aliased_headers_import() -> None:
    csv = (
        "side,open_time,open_price,close_time,close_price,qty,fee,profit,ticker\n"
        "Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850,1.0,2.1,750,BTCUSDT"
    )
    outcome = _tl(csv)
    assert outcome.status == RecordBatchStatus.SUCCEEDED
    assert outcome.accepted_count == 1
    assert outcome.mapping_hash is not None
    assert outcome.resolved_mapping is not None
    assert outcome.resolved_mapping["direction"] == "side"


def test_tl_ambiguous_headers_fail_closed() -> None:
    # open_time + entry_date BOTH alias entry_time and there is no exact entry_time
    # column, so the server must NOT guess — it fails closed (nothing inferred).
    csv = (
        "direction,open_time,entry_date,entry_price,exit_time,exit_price\n"
        "Long,2024-01-01 10:00,2024-01-01 09:00,42100,2024-01-01 15:30,42850"
    )
    outcome = _tl(csv)
    assert outcome.status == RecordBatchStatus.FAILED
    assert outcome.blocker_code == BLOCKER_AMBIGUOUS_COLUMN_MAPPING


def test_tl_explicit_mapping_disambiguates() -> None:
    csv = (
        "direction,t_open,t_close,entry_price,exit_price\n"
        "Long,2024-01-01 10:00,2024-01-01 15:30,42100,42850"
    )
    outcome = _tl(csv, import_mapping={"entry_time": "t_open", "exit_time": "t_close"})
    assert outcome.status == RecordBatchStatus.SUCCEEDED
    assert outcome.accepted_count == 1


def test_tl_invalid_explicit_mapping_blocks() -> None:
    csv = (
        "direction,entry_time,entry_price,exit_time,exit_price\n"
        "Long,2024-01-01 10:00,1,2024-01-01 11:00,2"
    )
    outcome = _tl(csv, import_mapping={"entry_time": "does_not_exist"})
    assert outcome.status == RecordBatchStatus.FAILED
    assert outcome.blocker_code == BLOCKER_INVALID_COLUMN_MAPPING


def test_tl_unmappable_headers_still_required_column_missing() -> None:
    csv = "a,b,c\n1,2,3"
    outcome = _tl(csv)
    assert outcome.status == RecordBatchStatus.FAILED
    assert outcome.blocker_code == BLOCKER_REQUIRED_COLUMN_MISSING


def test_tl_exact_canonical_unchanged_no_mapping_evidence() -> None:
    csv = (
        "direction,entry_time,entry_price,exit_time,exit_price\n"
        "Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850"
    )
    outcome = _tl(csv)
    assert outcome.status == RecordBatchStatus.SUCCEEDED
    assert outcome.mapping_hash is None
    assert outcome.resolved_mapping is None


# --------------------------------------------------------------------------- #
# Trading Signal normalize (doc 04 §5.1)                                       #
# --------------------------------------------------------------------------- #


def _ts(csv: str, **kw):
    columns, rows = parse_signal(csv.encode("utf-8"))
    return normalize_signal(columns, rows, source_timezone="UTC", instrument_id="BTCUSDT", **kw)


def test_ts_capitalized_headers_case_normalized() -> None:
    csv = (
        "Source_Record_ID,Event_Time,Available_Time,Direction,Signal_Type\n"
        "r1,2024-01-01 10:00,2024-01-01 11:00,long,entry"
    )
    outcome = _ts(csv)
    assert outcome.status == NormalizedRevisionStatus.SUCCEEDED
    assert outcome.accepted_count == 1
    assert outcome.mapping_hash is not None


def test_ts_legacy_ledger_without_mapping_still_blocked() -> None:
    csv = (
        "direction,entry_time,entry_price,exit_time,exit_price\n"
        "Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850"
    )
    outcome = _ts(csv)
    assert outcome.status == NormalizedRevisionStatus.FAILED
    assert outcome.blocker_code == BLOCKER_LEGACY_TRADE_LOG_SCHEMA


def test_ts_legacy_ledger_accepted_only_with_explicit_mapping() -> None:
    csv = (
        "entry_time,exit_time,entry_price,exit_price,direction,rid,seen,kind\n"
        "2024-01-01 10:00,2024-01-01 15:30,42100,42850,long,r1,2024-01-01 11:00,entry"
    )
    mapping = {
        "source_record_id": "rid",
        "event_time": "entry_time",
        "available_time": "seen",
        "signal_type": "kind",
    }
    outcome = _ts(csv, import_mapping=mapping)
    assert outcome.status == NormalizedRevisionStatus.SUCCEEDED
    assert outcome.accepted_count == 1
    assert outcome.resolved_mapping is not None
    assert outcome.resolved_mapping["event_time"] == "entry_time"
