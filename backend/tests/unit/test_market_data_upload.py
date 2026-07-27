"""Market Data raw-asset upload validators (F-01, doc 11 §3.1, §7).

Pure unit coverage for the file-type/size gates that run before any DB access
in ``start_market_raw_upload`` (mirrors ``test_market_policy.py`` style).
"""

from __future__ import annotations

import pytest

from entropia.application.commands import market_data as md_cmd
from entropia.shared.errors import (
    MarketDataFileTooLargeError,
    MarketDataFileTypeNotAllowedError,
    ValidationError,
)

_GOOD_CSV = b"timestamp,open,high,low,close,volume\n2024-01-01T00:00:00Z,1,2,0.5,1.5,100\n"


def test_csv_and_txt_filenames_accepted() -> None:
    md_cmd._validate_upload_file_type("ohlcv.csv", _GOOD_CSV)  # no raise
    md_cmd._validate_upload_file_type("OHLCV.TXT", _GOOD_CSV)  # case-insensitive


@pytest.mark.parametrize("filename", [None, "", "   "])
def test_missing_filename_fails_closed(filename: str | None) -> None:
    """Regression: the gate used to SKIP entirely when no filename was declared
    (``if name and not name.endswith(...)``), so any payload was accepted."""
    with pytest.raises(MarketDataFileTypeNotAllowedError):
        md_cmd._validate_upload_file_type(filename, _GOOD_CSV)


def test_unsupported_extension_rejected() -> None:
    with pytest.raises(MarketDataFileTypeNotAllowedError):
        md_cmd._validate_upload_file_type("dataset.xlsx", _GOOD_CSV)


def test_binary_content_behind_a_csv_name_rejected() -> None:
    """The extension claim is backed by a content sniff, so a renamed archive
    cannot pass the command-level gate."""
    with pytest.raises(MarketDataFileTypeNotAllowedError):
        md_cmd._validate_upload_file_type("dataset.csv", b"PK\x03\x04\x14\x00binary")


def test_empty_file_rejected() -> None:
    with pytest.raises(ValidationError):
        md_cmd._validate_upload_file_size(0)


def test_oversized_file_rejected() -> None:
    with pytest.raises(MarketDataFileTooLargeError):
        md_cmd._validate_upload_file_size(md_cmd.MAX_UPLOAD_BYTES + 1)


def test_file_at_the_limit_is_accepted() -> None:
    md_cmd._validate_upload_file_size(md_cmd.MAX_UPLOAD_BYTES)  # no raise
