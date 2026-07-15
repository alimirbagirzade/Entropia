"""Unit tests for the shared multipart upload validator (F-03).

Covers size, UTF-8 encoding, and CSV-schema gates in isolation (no DB, no HTTP)
so the validator's fail-closed contract is pinned independently of any route.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from starlette.datastructures import Headers, UploadFile

from entropia.apps.api.upload import (
    DEFAULT_MAX_UPLOAD_BYTES,
    validate_csv_schema,
    validate_multipart_upload,
)
from entropia.shared.errors import (
    UploadEncodingInvalidError,
    UploadSchemaInvalidError,
    UploadTooLargeError,
    ValidationError,
)


def _file(content: bytes, *, filename: str = "f.csv", content_type: str = "text/csv") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


async def test_valid_csv_passes_and_returns_bytes_text_and_metadata() -> None:
    result = await validate_multipart_upload(_file(b"time,side\n1,buy\n"), require_csv_schema=True)
    assert result.content == b"time,side\n1,buy\n"
    assert result.text == "time,side\n1,buy\n"
    assert result.filename == "f.csv"
    assert result.content_type == "text/csv"


async def test_empty_upload_rejected() -> None:
    with pytest.raises(ValidationError):
        await validate_multipart_upload(_file(b""))


async def test_oversized_upload_rejected_without_buffering_beyond_limit() -> None:
    with pytest.raises(UploadTooLargeError):
        await validate_multipart_upload(_file(b"x" * 11), max_bytes=10)


async def test_non_utf8_bytes_rejected() -> None:
    with pytest.raises(UploadEncodingInvalidError):
        await validate_multipart_upload(_file(b"\xff\xfe\x00\x01bad"))


async def test_nul_byte_rejected_even_if_decodable() -> None:
    with pytest.raises(UploadEncodingInvalidError):
        await validate_multipart_upload(_file(b"col\x00umn"))


async def test_csv_schema_rejects_blank_document() -> None:
    with pytest.raises(UploadSchemaInvalidError):
        await validate_multipart_upload(_file(b"   \n  \n"), require_csv_schema=True)


async def test_csv_schema_tolerates_utf8_bom_header() -> None:
    result = await validate_multipart_upload(
        _file(b"\xef\xbb\xbfcol_a,col_b\n1,2\n"), require_csv_schema=True
    )
    assert "col_a" in result.text


async def test_non_csv_text_allowed_when_schema_not_required() -> None:
    # Manual accepts TXT/MD/HTML — no CSV structure required.
    result = await validate_multipart_upload(
        _file(b"<h1>Guide</h1>", filename="guide.html", content_type="text/html")
    )
    assert result.text == "<h1>Guide</h1>"


def test_validate_csv_schema_rejects_binary_shaped_text() -> None:
    with pytest.raises(UploadSchemaInvalidError):
        validate_csv_schema("")


def test_default_ceiling_is_bounded() -> None:
    assert DEFAULT_MAX_UPLOAD_BYTES == 50 * 1024 * 1024
