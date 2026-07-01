"""Opaque keyset cursor for Analysis Lab list projections (Stage 6a, doc 18 §9.2).

Mirrors ``domain/backtest/artifacts.py``: a forward cursor pinned to a namespace
carrying the previous page's last ordering key (a sortable id). A malformed
token, or one built for a different namespace, is a ``CURSOR_INVALID`` recovery
signal — never a silent reset to page 1.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass

from entropia.shared.errors import CursorInvalidError

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100


@dataclass(frozen=True, slots=True)
class KeysetCursor:
    """Decoded keyset position: the previous page's last (sortable) id."""

    last_key: str


def encode_cursor(namespace: str, *, last_key: str) -> str:
    """Build an opaque forward cursor pinned to ``namespace``."""
    payload = {"n": namespace, "k": last_key}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, *, namespace: str) -> KeysetCursor:
    """Decode + validate a cursor for ``namespace``."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode())
        payload = json.loads(raw)
    except (ValueError, binascii.Error) as exc:
        raise CursorInvalidError() from exc
    if not isinstance(payload, dict) or payload.get("n") != namespace:
        raise CursorInvalidError()
    key = payload.get("k")
    if not isinstance(key, str) or not key:
        raise CursorInvalidError()
    return KeysetCursor(last_key=key)


def clamp_limit(limit: int | None) -> int:
    """Bound a client page size into ``[1, MAX_PAGE_LIMIT]`` (default 20)."""
    if limit is None:
        return DEFAULT_PAGE_LIMIT
    if limit < 1:
        return 1
    return min(limit, MAX_PAGE_LIMIT)


__all__ = [
    "DEFAULT_PAGE_LIMIT",
    "MAX_PAGE_LIMIT",
    "KeysetCursor",
    "clamp_limit",
    "decode_cursor",
    "encode_cursor",
]
