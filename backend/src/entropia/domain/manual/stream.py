"""Continuous Manual Stream contract pieces (doc 21 §7, §9, §13).

The reader/sidebar renders ONE ``stream_version`` snapshot; appended documents
order by their atomic unique ``stream_position`` — never ``created_at``
(doc 21 §14). Cursors reuse the opaque keyset scheme from
``domain/agent_lab/cursor``; a malformed or foreign-namespace token is a
``CURSOR_INVALID`` recovery signal, never a silent reset. The search cursor
carries the previous page's exact (rank, chunk_id) pair as opaque strings —
rank is a fixed-precision NUMERIC so keyset comparison is exact across pages.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from entropia.domain.agent_lab.cursor import decode_cursor, encode_cursor
from entropia.shared.errors import CursorInvalidError

STREAM_CURSOR_NAMESPACE = "manual_stream"
SEARCH_CURSOR_NAMESPACE = "manual_search"
_SEP = "|"

MAX_SEARCH_QUERY = 200

# ts_rank is rounded to this scale in SQL so the cursor keyset is exact.
SEARCH_RANK_SCALE = 6


def section_anchor(document_id: str) -> str:
    """Stable reader section anchor (doc 21 §3.2 ``manual-section-{id}``)."""
    return f"manual-section-{document_id}"


def encode_stream_cursor(position: int) -> str:
    return encode_cursor(STREAM_CURSOR_NAMESPACE, last_key=f"{position:012d}")


def decode_stream_cursor(cursor: str) -> int:
    decoded = decode_cursor(cursor, namespace=STREAM_CURSOR_NAMESPACE)
    try:
        return int(decoded.last_key)
    except ValueError as exc:
        raise CursorInvalidError() from exc


def encode_search_cursor(*, rank: Decimal, chunk_id: str) -> str:
    return encode_cursor(SEARCH_CURSOR_NAMESPACE, last_key=f"{rank}{_SEP}{chunk_id}")


def decode_search_cursor(cursor: str) -> tuple[Decimal, str]:
    decoded = decode_cursor(cursor, namespace=SEARCH_CURSOR_NAMESPACE)
    rank_raw, sep, chunk_id = decoded.last_key.partition(_SEP)
    if not sep or not rank_raw or not chunk_id:
        raise CursorInvalidError()
    try:
        return Decimal(rank_raw), chunk_id
    except InvalidOperation as exc:
        raise CursorInvalidError() from exc


__all__ = [
    "MAX_SEARCH_QUERY",
    "SEARCH_CURSOR_NAMESPACE",
    "SEARCH_RANK_SCALE",
    "STREAM_CURSOR_NAMESPACE",
    "decode_search_cursor",
    "decode_stream_cursor",
    "encode_search_cursor",
    "encode_stream_cursor",
    "section_anchor",
]
