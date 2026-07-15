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


def test_csv_and_txt_filenames_accepted() -> None:
    rd_cmd._validate_upload_file_type("open-interest.csv")  # no raise
    rd_cmd._validate_upload_file_type("FUNDING.TXT")  # case-insensitive
    rd_cmd._validate_upload_file_type(None)  # missing filename never blocks


def test_unsupported_extension_rejected() -> None:
    with pytest.raises(ResearchDataFileTypeNotAllowedError):
        rd_cmd._validate_upload_file_type("dataset.xlsx")


def test_empty_file_rejected() -> None:
    with pytest.raises(ValidationError):
        rd_cmd._validate_upload_file_size(0)


def test_oversized_file_rejected() -> None:
    with pytest.raises(ResearchDataFileTooLargeError):
        rd_cmd._validate_upload_file_size(rd_cmd.MAX_UPLOAD_BYTES + 1)


def test_file_at_the_limit_is_accepted() -> None:
    rd_cmd._validate_upload_file_size(rd_cmd.MAX_UPLOAD_BYTES)  # no raise
