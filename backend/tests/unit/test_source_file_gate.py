"""Fail-closed TXT/CSV source-file gate (K-07, doc 05 §5.2/§12.1, doc 04 §7/§11).

Pure unit coverage of the shared gate: the filename axis (absent/blank/extension)
and the content sniff (binary signatures, NUL bytes, undecodable UTF-8), plus the
boundary case that a multi-byte character straddling the sniff cut is NOT a
decode failure.
"""

from __future__ import annotations

import pytest

from entropia.domain.importing.source_file import (
    REASON_BINARY_CONTENT,
    REASON_MISSING_FILENAME,
    REASON_UNDECODABLE_CONTENT,
    REASON_UNSUPPORTED_EXTENSION,
    SNIFF_PREFIX_BYTES,
    assert_supported_source_file,
    sniff_text_content,
)
from entropia.shared.errors import FileTypeNotAllowedError

_TEXT = b"direction,entry_time\nLong,2024-01-01 10:00\n"


def _reason(filename: str | None, content: bytes = _TEXT) -> str:
    with pytest.raises(FileTypeNotAllowedError) as excinfo:
        assert_supported_source_file(filename, content, error=FileTypeNotAllowedError)
    detail = excinfo.value.details[0]
    assert detail["field"] == "original_filename"
    assert detail["actual"] == filename
    return str(detail["reason"])


@pytest.mark.parametrize("filename", [None, "", "   ", "\t"])
def test_absent_filename_fails_closed(filename: str | None) -> None:
    """The pre-K-07 gate SKIPPED entirely here; a missing name is now a rejection."""
    assert _reason(filename) == REASON_MISSING_FILENAME


@pytest.mark.parametrize("filename", ["trades.pdf", "trades", "trades.csv.exe", ".csvx"])
def test_unsupported_extension_is_rejected(filename: str) -> None:
    assert _reason(filename) == REASON_UNSUPPORTED_EXTENSION


@pytest.mark.parametrize("filename", ["trades.csv", "trades.txt", "TRADES.CSV", " trades.txt "])
def test_supported_extension_with_text_content_passes(filename: str) -> None:
    assert_supported_source_file(filename, _TEXT, error=FileTypeNotAllowedError)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"PK\x03\x04\x14\x00", f"{REASON_BINARY_CONTENT}:zip"),
        (b"%PDF-1.7 trailing", f"{REASON_BINARY_CONTENT}:pdf"),
        (b"\x1f\x8b\x08\x00", f"{REASON_BINARY_CONTENT}:gzip"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", f"{REASON_BINARY_CONTENT}:ole2"),
        (b"side,price\n\x00\x00", REASON_BINARY_CONTENT),
        (b"side,price\n\xff\xfe\xfa", REASON_UNDECODABLE_CONTENT),
    ],
)
def test_content_sniff_rejects_non_text(content: bytes, expected: str) -> None:
    """A .csv extension is not evidence of type — the bytes must sniff as text."""
    assert sniff_text_content(content) == expected
    assert _reason("trades.csv", content) == expected


def test_multibyte_character_across_the_sniff_cut_is_not_a_failure() -> None:
    """The incremental decoder must not read a truncated prefix as undecodable."""
    payload = ("a" * (SNIFF_PREFIX_BYTES - 1) + "ğ" + "b" * 64).encode("utf-8")
    assert len(payload) > SNIFF_PREFIX_BYTES
    assert sniff_text_content(payload) is None


def test_plain_text_content_passes_the_sniff() -> None:
    assert sniff_text_content(_TEXT) is None
    assert sniff_text_content("café,über\n1,2\n".encode()) is None
