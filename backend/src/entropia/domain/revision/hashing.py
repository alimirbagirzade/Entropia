"""Deterministic content hashing for immutable revisions (DOMAIN_MODEL §1).

`content_hash = sha256(canonical_json(payload))`. Canonical JSON uses sorted
keys, compact separators, and UTF-8 so the same logical payload always hashes
identically across processes and languages.

The implementation lives in :mod:`entropia.shared.hashing` — ``shared`` is the
bottom layer and must not import from ``domain``, and ``shared.idempotency`` /
``shared.manifest`` need the same canonicalizer. This module re-exports it so
the revision domain keeps its published surface and every caller keeps hashing
identically. Do not fork a second canonicalizer here.
"""

from __future__ import annotations

from entropia.shared.hashing import canonical_json, content_hash

__all__ = ["canonical_json", "content_hash"]
