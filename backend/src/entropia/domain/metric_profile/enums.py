"""Arrange Metrics domain enums (Stage 5c, doc 17 §1, §9.2).

Presentation-plane enums for the Result View Metric Profile. These are DISTINCT
from the Stage 5a ``MetricAvailability`` (whether a metric was *computed* for a
result): here ``MetricAvailabilityStatus`` describes whether a metric is
*offerable* in the registry (selectable now vs future/experimental reference).
Stored as lowercase snake_case ``StrEnum`` values via ``enum_column`` (CR-04).
"""

from __future__ import annotations

from enum import StrEnum


class MetricAvailabilityStatus(StrEnum):
    """Registry offer state of a MetricDefinition (doc 17 §1, §3.2, §13).

    Only ``SELECTABLE`` codes may enter an Apply payload; ``FUTURE`` /
    ``EXPERIMENTAL`` are reference-only and never produce a fake value (doc 17
    §14, CR-07).
    """

    SELECTABLE = "selectable"
    FUTURE = "future"
    EXPERIMENTAL = "experimental"


class ProfileScope(StrEnum):
    """Ownership scope of a Result View Metric Profile root (doc 17 §2, §5.1)."""

    USER = "user"
    WORKSPACE_DEFAULT = "workspace_default"
    SYSTEM_DEFAULT = "system_default"


__all__ = ["MetricAvailabilityStatus", "ProfileScope"]
