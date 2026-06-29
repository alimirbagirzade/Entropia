"""Deterministic content hashing for immutable revisions (DOMAIN_MODEL §1).

`content_hash = sha256(canonical_json(payload))`. Canonical JSON uses sorted
keys, compact separators, and UTF-8 so the same logical payload always hashes
identically across processes and languages.
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
