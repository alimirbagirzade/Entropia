"""Fail-closed server-side source-file type gate for the TXT/CSV import surfaces.

Doc 05 §5.2 requires "Extension/parseability/type validated server-side" for the
Trade Log source asset; doc 04 §7 states the same for the Trading Signal twin.

The gate is FAIL-CLOSED on every axis:

* **filename** — an absent or blank ``original_filename`` is a REJECTION, not a
  skip. Without a filename the server cannot establish the declared type at all,
  so accepting the upload would silently drop the documented control. (A raw
  multipart part carrying ``filename=""`` reaches the command with an empty
  string; a direct command caller can pass ``None``.)
* **extension** — the declared name must end in an allowed extension.
* **content** — the extension claim is BACKED by a bounded content sniff: known
  binary container signatures, embedded NUL bytes, and undecodable UTF-8 all
  reject, so a binary blob renamed ``trades.csv`` cannot pass the gate even when
  the command is invoked directly (bypassing the route-level F-03 gate in
  ``entropia.apps.api.upload``).

Each surface passes its OWN documented error class so the page-level error
taxonomy stays intact: doc 05 §12.1 names ``UNSUPPORTED_SOURCE_FILE_TYPE`` for
Trade Log, doc 04 §11 names ``FILE_TYPE_NOT_ALLOWED`` for Trading Signal.
"""

from __future__ import annotations

import codecs
import csv
import io
from typing import Any

from entropia.shared.errors import (
    UploadEncodingInvalidError,
    UploadSchemaInvalidError,
    UploadTooLargeError,
    ValidationError,
)

ALLOWED_SOURCE_EXTENSIONS: tuple[str, ...] = (".txt", ".csv")

# 50 MB ceiling for the text-asset surfaces (signal-event ledgers, trade logs,
# baseline CSVs, manual documents). Market Data keeps its own larger raw ingestion
# ceiling (F-01); these surfaces are hand-authored ledgers/documents.
#
# The constant lives in the DOMAIN, not at the route boundary, because the human
# page is no longer the only caller: the Alpha Agent reaches the same upload
# command UI-lessly through the Tool Gateway (doc 04 §10, TS-20), so a ceiling that
# existed only in ``apps.api.upload`` would have bounded the browser and left the
# Agent unbounded. ``apps.api.upload.DEFAULT_MAX_UPLOAD_BYTES`` IS this constant —
# the two planes must never drift into two different ceilings.
MAX_SOURCE_UPLOAD_BYTES = 50 * 1024 * 1024

# The NUL scan covers the whole payload (a cheap memchr); the UTF-8 validation
# runs over a bounded prefix so the command-layer gate stays O(1) on a 50 MB
# upload. The route-level F-03 gate still decodes the full document.
SNIFF_PREFIX_BYTES = 8192

# Leading magic bytes of container/binary formats users actually mis-upload.
_BINARY_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"PK\x03\x04", "zip"),
    (b"PK\x05\x06", "zip"),
    (b"PK\x07\x08", "zip"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole2"),
    (b"%PDF-", "pdf"),
    (b"\x1f\x8b", "gzip"),
    (b"Rar!\x1a\x07", "rar"),
    (b"7z\xbc\xaf\x27\x1c", "7z"),
    (b"SQLite format 3\x00", "sqlite"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF8", "gif"),
    (b"\x7fELF", "elf"),
)

REASON_MISSING_FILENAME = "missing_filename"
REASON_UNSUPPORTED_EXTENSION = "unsupported_extension"
REASON_BINARY_CONTENT = "binary_content"
REASON_UNDECODABLE_CONTENT = "undecodable_content"


def sniff_text_content(content: bytes) -> str | None:
    """Return a rejection reason when ``content`` is not plain UTF-8 text, else None."""
    for signature, label in _BINARY_SIGNATURES:
        if content.startswith(signature):
            return f"{REASON_BINARY_CONTENT}:{label}"
    if b"\x00" in content:
        return REASON_BINARY_CONTENT
    prefix = content[:SNIFF_PREFIX_BYTES]
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        # ``final`` only when the prefix IS the whole payload, so a multi-byte
        # character straddling the cut is not misread as a decode failure.
        decoder.decode(prefix, final=len(content) <= SNIFF_PREFIX_BYTES)
    except UnicodeDecodeError:
        return REASON_UNDECODABLE_CONTENT
    return None


def assert_supported_source_file(
    original_filename: str | None,
    content: bytes,
    *,
    error: type[ValidationError],
    allowed_extensions: tuple[str, ...] = ALLOWED_SOURCE_EXTENSIONS,
) -> None:
    """Raise ``error`` unless the upload declares an allowed extension AND sniffs
    as UTF-8 text. A missing/blank filename fails closed (doc 05 §5.2)."""
    label = _extension_label(allowed_extensions)
    name = (original_filename or "").strip()
    if not name:
        raise error(
            f"A source file name is required to establish the file type; only "
            f"{label} source files are supported.",
            details=[_detail(original_filename, REASON_MISSING_FILENAME)],
        )
    if not name.lower().endswith(allowed_extensions):
        raise error(
            f"File {original_filename!r} is not a {label} file.",
            details=[_detail(original_filename, REASON_UNSUPPORTED_EXTENSION)],
        )
    reason = sniff_text_content(content)
    if reason is not None:
        raise error(
            f"File {original_filename!r} does not contain {label} text.",
            details=[_detail(original_filename, reason)],
        )


def decode_source_text(content: bytes) -> str:
    """Decode the WHOLE document as UTF-8 (F-03 encoding gate).

    Stricter than ``sniff_text_content``, which only decodes a bounded prefix so the
    type gate stays O(1): a file whose first 8 KB are clean but whose tail is not
    UTF-8 passes the sniff and fails here. Both run — the sniff names the *type*
    defect, this names the *encoding* defect.
    """
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadEncodingInvalidError() from exc
    if "\x00" in text:
        raise UploadEncodingInvalidError(
            "The file contains NUL bytes and is not a valid text document."
        )
    return text


def assert_csv_schema(text: str) -> None:
    """Reject text that has no usable CSV header row (F-03 schema gate). A leading
    UTF-8 BOM is tolerated; the first non-blank line must contain at least one
    non-empty column."""
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


def assert_source_bytes_admissible(
    content: bytes,
    *,
    max_bytes: int = MAX_SOURCE_UPLOAD_BYTES,
    require_csv_schema: bool = False,
) -> str:
    """The byte-level F-03 gate — empty / size / UTF-8 / CSV schema — returning the
    decoded text.

    ``apps.api.upload.validate_multipart_upload`` calls this after its bounded
    stream read, and the UI-less Tool Gateway calls it on the bytes an agent tool
    carried, so BOTH planes reject the same document with the same machine code
    (``UPLOAD_TOO_LARGE`` / ``UPLOAD_ENCODING_INVALID`` / ``UPLOAD_SCHEMA_INVALID``).
    Keeping one implementation is the point: a gate that only the route ran is
    exactly how a browser-bound control silently stops applying to the Agent.
    """
    if not content:
        raise ValidationError("The uploaded file is empty.")
    if len(content) > max_bytes:
        raise UploadTooLargeError(
            f"The file exceeds the {max_bytes // (1024 * 1024)} MB upload limit.",
            details=[{"field": "file", "actual_bytes": len(content), "limit": max_bytes}],
        )
    text = decode_source_text(content)
    if require_csv_schema:
        assert_csv_schema(text)
    return text


def _detail(original_filename: str | None, reason: str) -> dict[str, Any]:
    return {"field": "original_filename", "actual": original_filename, "reason": reason}


def _extension_label(allowed_extensions: tuple[str, ...]) -> str:
    return "/".join(extension.lstrip(".").upper() for extension in allowed_extensions)
