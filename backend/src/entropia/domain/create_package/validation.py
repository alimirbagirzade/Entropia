"""Deterministic Create-Package validation evidence (doc 06 §4.4/§5/§7).

The V1 validation *compute* — like ``candidate.py`` — is pure and reproducible. It
produces genuine evidence (never a cosmetic pass label): the checks that can be
evaluated deterministically at V1 (output-structure conformance + dependency-
snapshot health) run for real; the execution-dependent checks (syntax, runtime,
real market data, repaint/future-leak, baseline comparison) are recorded as
``not_executed`` with an honest note, deferred to the Future-Dev execution worker.

Overall ``passed`` is true iff every EXECUTED check passed. A drifted dependency
snapshot therefore fails validation and blocks approval — the gate is real. The
application command feeds already-resolved facts in (output kind + per-dependency
re-resolution booleans); this module has no I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Bumping this shifts the evidence namespace (mirrors GENERATOR_VERSION / ENGINE_VERSION):
# evidence produced by an older validator is never silently reused by a newer one.
VALIDATOR_VERSION = "cp-validation-v1"

# Canonical check categories (doc 06 §4.4 "Validation Tests"). The first two are
# executed deterministically at V1; the rest are execution-dependent and deferred.
CHECK_OUTPUT_STRUCTURE = "output_structure"
CHECK_DEPENDENCY_HEALTH = "dependency_health"
_DEFERRED_CHECKS: tuple[str, ...] = (
    "syntax",
    "runtime",
    "real_market_data",
    "repaint_future_leak",
    "baseline_comparison",
)

_STATUS_PASSED = "passed"
_STATUS_FAILED = "failed"
_STATUS_NOT_EXECUTED = "not_executed"

_DEFERRED_NOTE = "Execution-based check deferred to the validation worker (Future-Dev)."


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    """One validation check outcome inside the immutable evidence row."""

    check: str
    status: str  # passed | failed | not_executed
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """The deterministic evidence produced for one draft revision."""

    validator_version: str
    checks: list[ValidationCheck]
    passed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "validator_version": self.validator_version,
            "checks": [check.as_dict() for check in self.checks],
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class DependencyResolution:
    """A single re-resolution outcome the command computed against the live registry."""

    canonical_key: str
    resolved: bool
    detail: str


def build_validation_report(
    *,
    output_kind: str | None,
    dependency_resolutions: list[DependencyResolution],
) -> ValidationReport:
    """Compose deterministic validation evidence for a draft revision (doc 06 §4.4).

    ``output_structure`` passes iff the draft carries a non-empty output-contract
    kind. ``dependency_health`` passes iff every pinned dependency still resolves to
    its trusted revision; a dep-less request marks it ``not_executed`` (nothing to
    check). The execution-based checks are recorded ``not_executed``. ``passed`` is
    true iff every executed check passed.
    """
    checks: list[ValidationCheck] = [_output_structure_check(output_kind)]
    checks.append(_dependency_health_check(dependency_resolutions))
    checks.extend(
        ValidationCheck(check=name, status=_STATUS_NOT_EXECUTED, detail=_DEFERRED_NOTE)
        for name in _DEFERRED_CHECKS
    )
    passed = all(check.status != _STATUS_FAILED for check in checks)
    return ValidationReport(validator_version=VALIDATOR_VERSION, checks=checks, passed=passed)


def _output_structure_check(output_kind: str | None) -> ValidationCheck:
    if output_kind:
        return ValidationCheck(
            check=CHECK_OUTPUT_STRUCTURE,
            status=_STATUS_PASSED,
            detail=f"Output contract declares kind '{output_kind}'.",
        )
    return ValidationCheck(
        check=CHECK_OUTPUT_STRUCTURE,
        status=_STATUS_FAILED,
        detail="The draft revision has no output-contract kind.",
    )


def _dependency_health_check(resolutions: list[DependencyResolution]) -> ValidationCheck:
    if not resolutions:
        return ValidationCheck(
            check=CHECK_DEPENDENCY_HEALTH,
            status=_STATUS_NOT_EXECUTED,
            detail="No pinned dependencies to re-resolve.",
        )
    drifted = [res.canonical_key for res in resolutions if not res.resolved]
    if drifted:
        return ValidationCheck(
            check=CHECK_DEPENDENCY_HEALTH,
            status=_STATUS_FAILED,
            detail=f"Pinned dependencies no longer resolve: {', '.join(sorted(drifted))}.",
        )
    return ValidationCheck(
        check=CHECK_DEPENDENCY_HEALTH,
        status=_STATUS_PASSED,
        detail=f"All {len(resolutions)} pinned dependencies still resolve to their revision.",
    )


__all__ = [
    "VALIDATOR_VERSION",
    "DependencyResolution",
    "ValidationCheck",
    "ValidationReport",
    "build_validation_report",
]
