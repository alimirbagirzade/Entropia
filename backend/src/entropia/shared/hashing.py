"""Deterministic content hashing — the lowest-layer canonicalizer (DOMAIN_MODEL §1).

``content_hash = sha256(canonical_json(payload))``. Canonical JSON uses sorted
keys, compact separators, and UTF-8 so the same logical payload always hashes
identically across processes and languages.

This lives in ``shared`` because ``shared`` is the bottom layer and may not
import from ``domain``. ``domain.revision.hashing`` re-exports these names so
the revision domain keeps its published surface (see that module).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def content_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
