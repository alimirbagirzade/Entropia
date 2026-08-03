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

from dataclasses import dataclass

from fastapi import UploadFile

from entropia.domain.importing.source_file import (
    MAX_SOURCE_UPLOAD_BYTES,
    assert_csv_schema,
    assert_source_bytes_admissible,
)

# 50 MB default ceiling for the text-asset surfaces (signal-event ledgers, trade
# logs, baseline CSVs, manual documents). Market Data keeps its own larger raw
# ingestion ceiling (F-01); these surfaces are hand-authored ledgers/documents.
#
# The value now lives in the domain (``MAX_SOURCE_UPLOAD_BYTES``) because the route
# is no longer the only caller — the Alpha Agent reaches the same upload command
# through the Tool Gateway (doc 04 §10, TS-20). Aliasing rather than re-declaring
# is what keeps the browser plane and the UI-less plane on ONE ceiling; two
# literals would drift the first time one of them was tuned.
DEFAULT_MAX_UPLOAD_BYTES = MAX_SOURCE_UPLOAD_BYTES


@dataclass(frozen=True)
class ValidatedUpload:
    """A validated multipart upload: the raw bytes (content-addressed by the
    command layer), the decoded UTF-8 text, the original filename, and the
    client-declared content type."""

    content: bytes
    text: str
    filename: str | None
    content_type: str | None


# The F-03 byte gate itself lives in ``domain/importing/source_file`` so the
# UI-less Tool Gateway runs the SAME code (doc 04 §10, TS-20). These names stay
# exported here because the routes and the F-03 unit tests import them from this
# module; they are aliases, not a second implementation.
validate_csv_schema = assert_csv_schema


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
    # The bounded read (``max_bytes + 1``) stays HERE — it is the streaming
    # protection that keeps an oversized upload from being buffered whole. The
    # shared gate then rules on the bytes that were actually read.
    content = await file.read(max_bytes + 1)
    text = assert_source_bytes_admissible(
        content, max_bytes=max_bytes, require_csv_schema=require_csv_schema
    )
    return ValidatedUpload(
        content=content,
        text=text,
        filename=file.filename,
        content_type=file.content_type,
    )
