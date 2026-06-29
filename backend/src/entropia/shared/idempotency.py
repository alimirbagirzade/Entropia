"""Idempotency-key support for mutation commands (Module 20 §6.2).

The same key + same payload returns the prior result and never creates a second
revision/run/job. The same key + a *different* payload is a conflict.
"""

from __future__ import annotations

import hashlib

from entropia.domain.revision.hashing import canonical_json


def request_fingerprint(payload: object) -> str:
    """Stable hash of a command payload for idempotency comparison."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
