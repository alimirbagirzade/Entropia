"""Backtest Ready Check domain (Stage 4b, doc 14).

Pure, deterministic readiness validators + value objects. The immutable Readiness
Report/Issue persistence and the snapshot fingerprint contract live in the
application/infrastructure layers; this package holds only engine-agnostic domain
logic (doc 14 §9.2).
"""

from __future__ import annotations

from entropia.domain.readiness.enums import (
    ReadinessIssueCode,
    ReadinessScope,
    ReadinessSeverity,
    ReadinessState,
)
from entropia.domain.readiness.issues import (
    ExternalImportState,
    ReadinessIssue,
    ReadinessItemInput,
)
from entropia.domain.readiness.validators import (
    ReadinessEvaluation,
    evaluate_readiness,
    is_stale,
)

__all__ = [
    "ExternalImportState",
    "ReadinessEvaluation",
    "ReadinessIssue",
    "ReadinessIssueCode",
    "ReadinessItemInput",
    "ReadinessScope",
    "ReadinessSeverity",
    "ReadinessState",
    "evaluate_readiness",
    "is_stale",
]
