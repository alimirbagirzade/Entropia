"""Content-addressed manifest hashing for datasets, packages, and bundles.

Delegates to the canonical-JSON serializer in ``domain.revision.hashing`` so a
manifest always hashes identically to the equivalent revision payload. Never
hand-roll ``json.dumps`` here — reuse the one canonicalizer.
"""

from __future__ import annotations

from typing import Any

from entropia.domain.revision.hashing import content_hash


def manifest_hash(payload: Any) -> str:
    """Return ``sha256(canonical_json(payload))`` as a 64-char hex digest."""
    return content_hash(payload)
