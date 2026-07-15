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


def test_csv_and_txt_filenames_accepted() -> None:
    md_cmd._validate_upload_file_type("ohlcv.csv")  # no raise
    md_cmd._validate_upload_file_type("OHLCV.TXT")  # case-insensitive
    md_cmd._validate_upload_file_type(None)  # missing filename never blocks


def test_unsupported_extension_rejected() -> None:
    with pytest.raises(MarketDataFileTypeNotAllowedError):
        md_cmd._validate_upload_file_type("dataset.xlsx")


def test_empty_file_rejected() -> None:
    with pytest.raises(ValidationError):
        md_cmd._validate_upload_file_size(0)


def test_oversized_file_rejected() -> None:
    with pytest.raises(MarketDataFileTooLargeError):
        md_cmd._validate_upload_file_size(md_cmd.MAX_UPLOAD_BYTES + 1)


def test_file_at_the_limit_is_accepted() -> None:
    md_cmd._validate_upload_file_size(md_cmd.MAX_UPLOAD_BYTES)  # no raise
