"""Shared package per-domain enums (doc 09 §11.2, CR-04).

All values are lowercase snake_case and are returned over REST/SSE verbatim.
``PackageValidationState`` is a SEPARATE facet from the shared deletion/
approval/visibility enums and from ``PackageKind``; none of them collapse into a
single status column (doc 09 §14, "V18 Status label persistence enumuna
dönüştürme").
"""

from __future__ import annotations

from enum import StrEnum


class PackageValidationState(StrEnum):
    """Per-revision validation lifecycle (doc 09 §11.2).

    ``revision.validation_state: pending | passed | warning | failed | stale``.
    A package revision can be valid enough for review yet still not be an active
    resolver — trust activation is a separate facet handled by the ESP registry.
    """

    PENDING = "pending"
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    STALE = "stale"
