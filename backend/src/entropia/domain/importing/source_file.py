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
from typing import Any

from entropia.shared.errors import ValidationError

ALLOWED_SOURCE_EXTENSIONS: tuple[str, ...] = (".txt", ".csv")

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


def _detail(original_filename: str | None, reason: str) -> dict[str, Any]:
    return {"field": "original_filename", "actual": original_filename, "reason": reason}


def _extension_label(allowed_extensions: tuple[str, ...]) -> str:
    return "/".join(extension.lstrip(".").upper() for extension in allowed_extensions)
