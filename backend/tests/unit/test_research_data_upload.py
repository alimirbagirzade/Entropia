"""Research Data raw-asset upload validators (F-02, doc 12 §7).

Pure unit coverage for the file-type/size gates that run before any DB access
in ``create_upload_session`` (mirrors ``test_market_data_upload.py`` style).
"""

from __future__ import annotations

import pytest

from entropia.application.commands import research_data as rd_cmd
from entropia.shared.errors import (
    ResearchDataFileTooLargeError,
    ResearchDataFileTypeNotAllowedError,
    ValidationError,
)

_GOOD_CSV = b"timestamp,open_interest\n2024-01-01T00:00:00Z,123456\n"


def test_csv_and_txt_filenames_accepted() -> None:
    rd_cmd._validate_upload_file_type("open-interest.csv", _GOOD_CSV)  # no raise
    rd_cmd._validate_upload_file_type("FUNDING.TXT", _GOOD_CSV)  # case-insensitive


@pytest.mark.parametrize("filename", [None, "", "   "])
def test_missing_filename_fails_closed(filename: str | None) -> None:
    """Regression: the gate used to SKIP entirely when no filename was declared
    (``if name and not name.endswith(...)``), so any payload was accepted."""
    with pytest.raises(ResearchDataFileTypeNotAllowedError):
        rd_cmd._validate_upload_file_type(filename, _GOOD_CSV)


def test_unsupported_extension_rejected() -> None:
    with pytest.raises(ResearchDataFileTypeNotAllowedError):
        rd_cmd._validate_upload_file_type("dataset.xlsx", _GOOD_CSV)


def test_binary_content_behind_a_csv_name_rejected() -> None:
    """The extension claim is backed by a content sniff, so a renamed archive
    cannot pass the command-level gate."""
    with pytest.raises(ResearchDataFileTypeNotAllowedError):
        rd_cmd._validate_upload_file_type("dataset.csv", b"PK\x03\x04\x14\x00binary")


def test_empty_file_rejected() -> None:
    with pytest.raises(ValidationError):
        rd_cmd._validate_upload_file_size(0)


def test_oversized_file_rejected() -> None:
    with pytest.raises(ResearchDataFileTooLargeError):
        rd_cmd._validate_upload_file_size(rd_cmd.MAX_UPLOAD_BYTES + 1)


def test_file_at_the_limit_is_accepted() -> None:
    rd_cmd._validate_upload_file_size(rd_cmd.MAX_UPLOAD_BYTES)  # no raise
