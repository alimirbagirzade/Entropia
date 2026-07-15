"""Shared multipart upload validation for real native file choosers (F-03).

Trading Signal, Trade Log, Create Package baseline, and User Manual all accept a
real file transferred as ``multipart/form-data`` (mirroring the F-01 Market Data
raw-upload route). This module centralizes the server-side gate that runs at the
route boundary, BEFORE any application command touches the database or object
storage:

* **size** — the read is bounded by ``max_bytes + 1`` so an oversized upload is
  rejected without buffering an unbounded payload into memory; an empty file is
  rejected too.
* **encoding** — the bytes must decode as UTF-8 and carry no NUL bytes (these are
  text assets — the UI copy has always promised "UTF-8 TXT/CSV text").
* **schema** — for CSV/TXT surfaces the decoded text must present at least one
  non-empty header row (a binary blob renamed ``.csv`` is rejected here even if it
  happened to decode).

Extension checks stay in the per-surface application commands so the documented
error taxonomy (``FILE_TYPE_NOT_ALLOWED`` / ``MANUAL_FILE_TYPE_UNSUPPORTED`` /
``MARKET_DATA_FILE_TYPE_NOT_ALLOWED``) is preserved; the command's early
extension gate still runs regardless of how it is invoked.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from fastapi import UploadFile

from entropia.shared.errors import (
    UploadEncodingInvalidError,
    UploadSchemaInvalidError,
    UploadTooLargeError,
    ValidationError,
)

# 50 MB default ceiling for the text-asset surfaces (signal-event ledgers, trade
# logs, baseline CSVs, manual documents). Market Data keeps its own larger raw
# ingestion ceiling (F-01); these surfaces are hand-authored ledgers/documents.
DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class ValidatedUpload:
    """A validated multipart upload: the raw bytes (content-addressed by the
    command layer), the decoded UTF-8 text, the original filename, and the
    client-declared content type."""

    content: bytes
    text: str
    filename: str | None
    content_type: str | None


def _decode_utf8(content: bytes) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadEncodingInvalidError() from exc
    if "\x00" in text:
        raise UploadEncodingInvalidError(
            "The file contains NUL bytes and is not a valid text document."
        )
    return text


def validate_csv_schema(text: str) -> None:
    """Reject text that has no usable CSV header row (F-03 schema gate). A
    leading UTF-8 BOM is tolerated; the first non-blank line must contain at
    least one non-empty column."""
    stripped = text.lstrip("\ufeff")
    if not stripped.strip():
        raise UploadSchemaInvalidError("The file has no rows.")
    try:
        rows = csv.reader(io.StringIO(stripped))
        header = next((row for row in rows if any(cell.strip() for cell in row)), None)
    except csv.Error as exc:
        raise UploadSchemaInvalidError() from exc
    if header is None:
        raise UploadSchemaInvalidError("The file has no header columns.")


async def validate_multipart_upload(
    file: UploadFile,
    *,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    require_csv_schema: bool = False,
) -> ValidatedUpload:
    """Read a bounded multipart file and validate size + UTF-8 encoding (+ CSV
    schema when requested). Raises a ``ValidationError`` subclass on any failure
    before the caller reaches the database. The extension check remains the
    caller's (command's) responsibility."""
    content = await file.read(max_bytes + 1)
    if not content:
        raise ValidationError("The uploaded file is empty.")
    if len(content) > max_bytes:
        raise UploadTooLargeError(
            f"The file exceeds the {max_bytes // (1024 * 1024)} MB upload limit.",
            details=[{"field": "file", "actual_bytes": len(content), "limit": max_bytes}],
        )
    text = _decode_utf8(content)
    if require_csv_schema:
        validate_csv_schema(text)
    return ValidatedUpload(
        content=content,
        text=text,
        filename=file.filename,
        content_type=file.content_type,
    )
