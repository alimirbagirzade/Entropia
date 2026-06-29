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


def new_correlation_id() -> str:
    return new_id("corr")


def new_request_id() -> str:
    return new_id("req")
