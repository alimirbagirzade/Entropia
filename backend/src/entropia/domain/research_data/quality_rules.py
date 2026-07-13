"""Semantic quality checks for parsed research data (doc 12 §10, backlog R9).

The analysis job (``jobs/research_data.py::evaluate_research``) historically only
proved two things: a structurally valid time policy (DR4) and ``>=1`` native field
(schema integrity). Doc 12 §10 asks for a deeper quality report — the "Schema /
content" row names ``DUPLICATE_EXCESSIVE``, ``COVERAGE_INSUFFICIENT`` and
``INSTRUMENT_MAPPING_INVALID`` alongside null / type / range families — so a
per-row-clean payload that is still empty, mostly duplicated, heavily null, mixed
type or non-finite cannot silently reach ``VERIFIED`` (and, via Admin approval, an
Agent/Backtest evidence bundle) without a recorded finding.

These are PURE helpers over the schema-agnostic native rows (research payload is
never coerced to Market Data's canonical OHLCV schema — M5), mirroring
``domain/market_data/validation_rules.py::evaluate_cross_row``. The job persists the
returned findings as ``research_validation_issue`` rows (severity, check_id, message,
occurrences, evidence, remediation) and maps the worst severity to a lifecycle state.

Severity contract (doc 12 §10.1 decision tree — research-specific): only a
``BLOCKING_FAIL`` forces ``NEEDS_REVIEW`` (no auto-verify); a ``WARNING`` is recorded
in the quality report but the revision still verifies. This differs deliberately from
the Market Data job (where a warning also blocks) because the money-sizing engine is
fed by Market Data, whereas a research warning is contextual quality that a human may
knowingly approve. Approval requires the ``VERIFIED`` state, not ``PASS`` validation
status, so a warned-but-verified revision remains approvable.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from entropia.domain.lifecycle.enums import ValidationStatus

# Severity ordering for aggregation; the worst finding decides the outcome.
SEVERITY_RANK: dict[ValidationStatus, int] = {
    ValidationStatus.PASS: 0,
    ValidationStatus.WARNING: 1,
    ValidationStatus.BLOCKING_FAIL: 2,
}

# --- Thresholds (named constants; no magic numbers) ------------------------------
# Fully-identical rows across ALL native columns are an ingestion artifact, not
# signal. A modest fraction warns; a majority is a corrupt payload that blocks.
_DUPLICATE_WARN_FRACTION = Decimal("0.10")
_DUPLICATE_BLOCK_FRACTION = Decimal("0.50")
# A column that is at least half null is unreliable to consume as a feature input.
_NULL_WARN_FRACTION = Decimal("0.50")
# A column mixing numeric and non-numeric non-null values is flagged only when the
# minority class is non-trivial, so a single stray typo does not create noise.
_TYPE_MINORITY_MIN_FRACTION = Decimal("0.05")
# A column is treated as numeric-dominant (subject to the range check) when at least
# half of its non-null values parse as numbers.
_NUMERIC_DOMINANT_FRACTION = Decimal("0.50")
# Evidence lists are capped so a wide dataset cannot bloat a single issue row.
_EVIDENCE_COLUMN_CAP = 12


@dataclass(frozen=True, slots=True)
class QualityIssue:
    """A single quality finding, ready to persist as a ``research_validation_issue``."""

    severity: ValidationStatus
    check_id: str
    message: str
    occurrences: int = 1
    remediation: str | None = None
    evidence: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class QualityReport:
    """Aggregate quality outcome: the worst severity + the ordered findings."""

    worst: ValidationStatus
    issues: tuple[QualityIssue, ...]


def _is_null(value: Any) -> bool:
    """A native cell is null iff it is absent (``None``). A float ``NaN`` is a
    present-but-non-finite value (caught by the range check), not a null — Polars
    distinguishes the two and so do we."""
    return value is None


def _numeric_value(value: Any) -> float | None:
    """Return the value as a float if it is numeric or a numeric-parseable string,
    else ``None``. ``bool`` is rejected (an ``int`` subclass, but not a measurement)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        try:
            return float(value)
        except (ValueError, OverflowError, InvalidOperation):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _fraction(numerator: int, denominator: int) -> Decimal:
    return Decimal(numerator) / Decimal(denominator) if denominator else Decimal(0)


def _round4(fraction: Decimal) -> float:
    """JSON-safe fraction for evidence (Decimal is not JSON-serialisable)."""
    return float(round(fraction, 4))


def _check_coverage(rows: list[dict[str, Any]]) -> list[QualityIssue]:
    """``COVERAGE_INSUFFICIENT`` — a schema with no data rows cannot be consumed."""
    if rows:
        return []
    return [
        QualityIssue(
            severity=ValidationStatus.BLOCKING_FAIL,
            check_id="COVERAGE_INSUFFICIENT",
            message="The parsed native payload has no data rows.",
            occurrences=0,
            remediation="Upload a source that contains at least one data row, then re-analyze.",
            evidence={"row_count": 0},
        )
    ]


def _check_duplicates(columns: list[str], rows: list[dict[str, Any]]) -> list[QualityIssue]:
    """``DUPLICATE_EXCESSIVE`` — fully-identical native rows above a threshold."""
    total = len(rows)
    if total == 0:
        return []
    keys = Counter(tuple(repr(row.get(col)) for col in columns) for row in rows)
    duplicate_rows = sum(count - 1 for count in keys.values() if count > 1)
    if duplicate_rows == 0:
        return []
    fraction = _fraction(duplicate_rows, total)
    evidence = {
        "duplicate_rows": duplicate_rows,
        "total_rows": total,
        "duplicate_fraction": _round4(fraction),
    }
    if fraction >= _DUPLICATE_BLOCK_FRACTION:
        return [
            QualityIssue(
                severity=ValidationStatus.BLOCKING_FAIL,
                check_id="DUPLICATE_EXCESSIVE",
                message="A majority of native rows are exact duplicates.",
                occurrences=duplicate_rows,
                remediation="De-duplicate the source; a new revision is required.",
                evidence=evidence,
            )
        ]
    if fraction >= _DUPLICATE_WARN_FRACTION:
        return [
            QualityIssue(
                severity=ValidationStatus.WARNING,
                check_id="DUPLICATE_EXCESSIVE",
                message="Repeated exact-duplicate native rows detected.",
                occurrences=duplicate_rows,
                remediation="Review whether duplicate rows are intended for this dataset.",
                evidence=evidence,
            )
        ]
    return []


def _check_null_density(columns: list[str], rows: list[dict[str, Any]]) -> list[QualityIssue]:
    """``NULL_DENSITY_HIGH`` — columns whose null fraction crosses the threshold."""
    total = len(rows)
    if total == 0:
        return []
    offenders: list[dict[str, Any]] = []
    for col in columns:
        null_count = sum(1 for row in rows if _is_null(row.get(col)))
        fraction = _fraction(null_count, total)
        if fraction >= _NULL_WARN_FRACTION:
            offenders.append(
                {"column": col, "null_count": null_count, "null_fraction": _round4(fraction)}
            )
    if not offenders:
        return []
    return [
        QualityIssue(
            severity=ValidationStatus.WARNING,
            check_id="NULL_DENSITY_HIGH",
            message="One or more native columns are predominantly null.",
            occurrences=len(offenders),
            remediation="Document null semantics per field, or supply a more complete source.",
            evidence={"columns": offenders[:_EVIDENCE_COLUMN_CAP]},
        )
    ]


def _check_type_consistency(columns: list[str], rows: list[dict[str, Any]]) -> list[QualityIssue]:
    """``TYPE_INCONSISTENT`` — columns mixing numeric and non-numeric non-null values."""
    offenders: list[dict[str, Any]] = []
    for col in columns:
        non_null = [row.get(col) for row in rows if not _is_null(row.get(col))]
        if not non_null:
            continue
        numeric = sum(1 for value in non_null if _numeric_value(value) is not None)
        non_numeric = len(non_null) - numeric
        if numeric == 0 or non_numeric == 0:
            continue
        minority = _fraction(min(numeric, non_numeric), len(non_null))
        if minority >= _TYPE_MINORITY_MIN_FRACTION:
            offenders.append(
                {
                    "column": col,
                    "numeric_fraction": _round4(_fraction(numeric, len(non_null))),
                }
            )
    if not offenders:
        return []
    return [
        QualityIssue(
            severity=ValidationStatus.WARNING,
            check_id="TYPE_INCONSISTENT",
            message="One or more native columns mix numeric and non-numeric values.",
            occurrences=len(offenders),
            remediation="Normalize the column to a single type, or declare its semantic type.",
            evidence={"columns": offenders[:_EVIDENCE_COLUMN_CAP]},
        )
    ]


def _check_numeric_ranges(columns: list[str], rows: list[dict[str, Any]]) -> list[QualityIssue]:
    """``NUMERIC_NON_FINITE`` — non-finite (NaN/Inf) values in numeric columns.

    A declared-bound outlier check needs a per-field range from an approved field
    definition (future work); non-finite is the schema-agnostic, deterministic range
    violation, and it corrupts any downstream compute (Kelly non-finite precedent)."""
    offenders: list[dict[str, Any]] = []
    total_non_finite = 0
    for col in columns:
        non_null = [row.get(col) for row in rows if not _is_null(row.get(col))]
        if not non_null:
            continue
        numerics = [_numeric_value(value) for value in non_null]
        numeric_count = sum(1 for value in numerics if value is not None)
        if _fraction(numeric_count, len(non_null)) < _NUMERIC_DOMINANT_FRACTION:
            continue
        non_finite = sum(1 for value in numerics if value is not None and not math.isfinite(value))
        if non_finite:
            total_non_finite += non_finite
            offenders.append({"column": col, "non_finite_count": non_finite})
    if not offenders:
        return []
    return [
        QualityIssue(
            severity=ValidationStatus.WARNING,
            check_id="NUMERIC_NON_FINITE",
            message="Numeric native columns contain non-finite (NaN/Inf) values.",
            occurrences=total_non_finite,
            remediation="Replace or drop non-finite values; document the fill policy per field.",
            evidence={"columns": offenders[:_EVIDENCE_COLUMN_CAP]},
        )
    ]


def _check_instrument_mapping(
    linked_market_dataset_revision_id: str | None, instrument_mapping_ref: str | None
) -> list[QualityIssue]:
    """``INSTRUMENT_MAPPING_INVALID`` — an incoherent research<->instrument mapping.

    A revision linked to a market dataset should carry an instrument mapping
    reference, and a mapping reference should not dangle without a link. Surfaces the
    gap as a WARNING without pre-empting the canonical instrument-resolution wiring
    (backlog R1), so previously-linked revisions are not retroactively blocked."""
    has_link = bool(linked_market_dataset_revision_id)
    has_ref = bool((instrument_mapping_ref or "").strip())
    if has_link == has_ref:
        return []
    if has_link:
        message = "A linked market revision has no instrument mapping reference."
        remediation = "Declare the instrument mapping for the linked market dataset."
    else:
        message = "An instrument mapping reference has no linked market revision."
        remediation = "Link an ACTIVE+APPROVED market revision, or clear the mapping reference."
    return [
        QualityIssue(
            severity=ValidationStatus.WARNING,
            check_id="INSTRUMENT_MAPPING_INVALID",
            message=message,
            remediation=remediation,
            evidence={"has_link": has_link, "has_mapping_ref": has_ref},
        )
    ]


def evaluate_quality(
    columns: list[str],
    rows: list[dict[str, Any]],
    *,
    linked_market_dataset_revision_id: str | None = None,
    instrument_mapping_ref: str | None = None,
) -> QualityReport:
    """Run every semantic check family over parsed native data (doc 12 §10, R9).

    Families: coverage, duplicates, null density, type consistency, numeric ranges
    and instrument mapping. Returns the ordered findings plus the worst severity, so
    the caller can record the quality report and gate the lifecycle transition."""
    issues: list[QualityIssue] = []
    issues.extend(_check_coverage(rows))
    issues.extend(_check_duplicates(columns, rows))
    issues.extend(_check_null_density(columns, rows))
    issues.extend(_check_type_consistency(columns, rows))
    issues.extend(_check_numeric_ranges(columns, rows))
    issues.extend(
        _check_instrument_mapping(linked_market_dataset_revision_id, instrument_mapping_ref)
    )

    worst = ValidationStatus.PASS
    for issue in issues:
        if SEVERITY_RANK[issue.severity] > SEVERITY_RANK[worst]:
            worst = issue.severity
    return QualityReport(worst=worst, issues=tuple(issues))
