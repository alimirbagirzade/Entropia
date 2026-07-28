"""Deterministic, collision-resistant, human-readable identifiers.

Canonical id shape: ``<prefix>_<26-char-base32>`` (ULID-like, lexicographically
sortable by creation time). Example: ``run_01J9Z3K8Q2...``.
"""

from __future__ import annotations

import os
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        value, rem = divmod(value, 32)
        chars.append(_CROCKFORD[rem])
    return "".join(reversed(chars))


def new_id(prefix: str) -> str:
    """Generate a sortable, prefixed identifier."""
    ts = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")
    return f"{prefix}_{_encode(ts, 10)}{_encode(rand, 16)}"


_ID_BODY_LENGTH = 26


def looks_like_id(value: str, *, prefix: str) -> bool:
    """Whether ``value`` has the exact shape ``new_id(prefix)`` mints.

    The shape check lives beside the minter so a caller that must decide whether an
    id came from us — a client-supplied SSE ``Last-Event-ID`` cursor, say — never
    re-derives (and drifts from) the alphabet. Shape only: an id of the right form
    may still name no row."""
    head, separator, body = value.partition("_")
    return (
        head == prefix
        and separator == "_"
        and len(body) == _ID_BODY_LENGTH
        and all(char in _CROCKFORD for char in body)
    )


def new_correlation_id() -> str:
    return new_id("corr")


def new_request_id() -> str:
    return new_id("req")
