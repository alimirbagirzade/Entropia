"""GAP-07b — pure baseline domain: equivalence-claim derivation, metadata
completeness and CSV parse evidence (doc 06 §4.4/§8.3). No I/O, no DB."""

from __future__ import annotations

from entropia.domain.create_package.baseline import (
    BASELINE_PARSER_VERSION,
    REQUIRED_BASELINE_METADATA_FIELDS,
    is_allowed_baseline_file,
    missing_baseline_metadata_fields,
    parse_baseline_csv,
    resolve_equivalence_claim,
)
from entropia.domain.create_package.enums import CreationMode

_FULL_METADATA = {
    "provider": "tradingview",
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "range": {"start": "2024-01-01", "end": "2024-06-01"},
    "timezone": "UTC",
    "settings": {"rsi_length": 14},
    "source_revision_context": "pine v5 @ abcdef",
}
_GOOD_CSV = b"time,rsi\n2024-01-01T00:00:00Z,55.2\n2024-01-01T01:00:00Z,48.7\n"


def test_equivalence_claim_derived_from_mode() -> None:
    # translate / repair / review claim equivalence; generate does not.
    assert resolve_equivalence_claim(CreationMode.TRANSLATE_EXISTING_CODE, None) is True
    assert resolve_equivalence_claim(CreationMode.REPAIR_EXISTING_CODE, None) is True
    assert resolve_equivalence_claim(CreationMode.REVIEW_EXISTING_CODE, None) is True
    assert resolve_equivalence_claim(CreationMode.GENERATE_FROM_DESCRIPTION, None) is False


def test_explicit_equivalence_claim_overrides_mode() -> None:
    # A Generate request may opt IN; a Translate request may opt OUT.
    assert resolve_equivalence_claim(CreationMode.GENERATE_FROM_DESCRIPTION, True) is True
    assert resolve_equivalence_claim(CreationMode.TRANSLATE_EXISTING_CODE, False) is False


def test_missing_metadata_fields_reports_gaps_in_order() -> None:
    assert missing_baseline_metadata_fields(_FULL_METADATA) == []
    partial = {"provider": "tradingview", "symbol": "", "settings": {}}
    missing = missing_baseline_metadata_fields(partial)
    # symbol is empty, settings is empty-dict, the rest are absent — all reported.
    assert "symbol" in missing
    assert "settings" in missing
    assert "provider" not in missing
    # Canonical order preserved.
    assert missing == [f for f in REQUIRED_BASELINE_METADATA_FIELDS if f in missing]


def test_missing_metadata_on_empty_dict_lists_all() -> None:
    assert missing_baseline_metadata_fields({}) == list(REQUIRED_BASELINE_METADATA_FIELDS)


def test_parse_good_csv_is_parseable() -> None:
    report = parse_baseline_csv(_GOOD_CSV)
    assert report.is_parseable is True
    assert report.parser_version == BASELINE_PARSER_VERSION
    assert report.row_count == 2
    assert report.column_count == 2
    assert report.columns == ["time", "rsi"]


def test_parse_header_only_is_not_parseable() -> None:
    report = parse_baseline_csv(b"time,rsi\n")
    assert report.is_parseable is False
    assert report.row_count == 0


def test_parse_empty_bytes_is_not_parseable() -> None:
    report = parse_baseline_csv(b"")
    assert report.is_parseable is False


def test_parse_non_utf8_is_not_parseable() -> None:
    report = parse_baseline_csv(b"\xff\xfe\x00\x01binary")
    assert report.is_parseable is False
    assert "UTF-8" in report.detail


def test_allowed_baseline_file_is_csv_only() -> None:
    assert is_allowed_baseline_file("baseline.csv") is True
    assert is_allowed_baseline_file("BASELINE.CSV") is True
    assert is_allowed_baseline_file("baseline.txt") is False
    assert is_allowed_baseline_file(None) is False
    assert is_allowed_baseline_file("") is False
