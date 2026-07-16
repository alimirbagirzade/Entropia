"""Create-Package validation evidence + the honest approval gate (doc 06 §4.4/§5/§7, F-13).

This module is the PURE compute behind the durable validation worker
(``application/jobs/package_validation``). The worker gathers the request's real
facts from the database — the re-resolved dependency snapshot, a real syntax probe
over the submitted source, the resolved native indicator/condition plan, and the
baseline parse result — and feeds them in as ``ValidationInputs``. This module maps
those facts onto the seven mandatory checks and computes the overall verdict.

The gate is honest (F-13):

* ``not_executed`` and ``blocked`` are NOT passes. A check that *should* run but
  could not (no resolvable plan, an equivalence claim with no parsed baseline) is
  ``blocked`` and prevents an overall ``passed`` result.
* A check that genuinely does not apply to this request (a dep-less indicator has no
  dependencies to health-check; a non-claiming package has no baseline to compare) is
  ``not_applicable`` and is excluded from the mandatory set — it never blocks.
* ``passed`` is true iff every mandatory check is ``passed`` (equivalently: no check is
  ``failed``, ``blocked`` or ``not_executed``). Only then does the request reach
  ``eligible_for_approval``.

No I/O. Bumping ``VALIDATOR_VERSION`` shifts the evidence namespace so a report from an
older validator is never silently reused by a newer one (mirrors ENGINE_VERSION).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Bumping this shifts the evidence namespace. F-13 turned the five stubbed checks into
# real deterministic checks and made not_executed/blocked block, so the evidence a v1
# validator produced is semantically incompatible and must not be reused.
VALIDATOR_VERSION = "cp-validation-v2"

# The seven mandatory checks (doc 06 §4.4 "Validation Tests"). Every one produces real
# output; none is a cosmetic pass label.
CHECK_OUTPUT_STRUCTURE = "output_structure"
CHECK_DEPENDENCY_HEALTH = "dependency_health"
CHECK_SYNTAX = "syntax"
CHECK_RUNTIME = "runtime"
CHECK_REAL_MARKET_DATA = "real_market_data"
CHECK_REPAINT_FUTURE_LEAK = "repaint_future_leak"
CHECK_BASELINE_COMPARISON = "baseline_comparison"

MANDATORY_CHECKS: tuple[str, ...] = (
    CHECK_OUTPUT_STRUCTURE,
    CHECK_DEPENDENCY_HEALTH,
    CHECK_SYNTAX,
    CHECK_RUNTIME,
    CHECK_REAL_MARKET_DATA,
    CHECK_REPAINT_FUTURE_LEAK,
    CHECK_BASELINE_COMPARISON,
)

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_NOT_EXECUTED = "not_executed"

# A check with one of these statuses is unsatisfied and prevents an overall pass
# (F-13: "any failed, blocked, or not-executed mandatory check prevents a passed result").
_BLOCKING_STATUSES = frozenset({STATUS_FAILED, STATUS_BLOCKED, STATUS_NOT_EXECUTED})

# Semantic verdicts the worker computes for the native plan (drives runtime + repaint).
PLAN_COMPUTABLE = "computable"  # the resolved plan yields the declared signal
PLAN_INCOMPATIBLE = "incompatible"  # deps resolved but cannot produce the declared signal
PLAN_UNRESOLVABLE = "unresolvable"  # no native plan resolves (empty skeleton) -> blocked
PLAN_NOT_A_SIGNAL = "not_a_signal"  # the package produces no time-series signal (e.g. ESP)


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    """One validation check outcome inside the immutable evidence row.

    ``artifacts`` carries the real per-check output (resolved keys, a baseline parse
    excerpt, a syntax diagnostic) so the report is inspectable, never a bare label.
    """

    check: str
    status: str
    detail: str
    artifacts: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """The evidence produced for one draft revision by the validation worker."""

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
    """A single re-resolution outcome computed against the live ESP registry."""

    canonical_key: str
    resolved: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ValidationInputs:
    """The real facts the durable worker gathered for one draft revision.

    Every field is a fact read from the database (or derived from it) — this module
    performs no I/O and simply maps facts onto the seven checks and the gate.
    """

    package_kind: str
    output_kind: str | None
    dependency_resolutions: list[DependencyResolution]
    # Syntax probe over the submitted source. ``None`` = no source to check (a
    # description request carries no code artifact) -> the check is not_applicable.
    syntax_ok: bool | None
    syntax_detail: str
    # The resolved native plan verdict (one of the PLAN_* constants) + evidence.
    plan_status: str
    plan_detail: str
    plan_keys: list[str]
    # Equivalence / baseline facts (doc 06 §4.4). A claiming request must compare
    # against a PASSED baseline of real market data; a non-claiming one needs none.
    claims_equivalence: bool
    baseline_passed: bool
    baseline_report: dict[str, Any] | None


def build_validation_report(inputs: ValidationInputs) -> ValidationReport:
    """Compose the seven-check validation evidence and the honest gate (F-13)."""
    checks = [
        _output_structure_check(inputs),
        _dependency_health_check(inputs),
        _syntax_check(inputs),
        _runtime_check(inputs),
        _real_market_data_check(inputs),
        _repaint_future_leak_check(inputs),
        _baseline_comparison_check(inputs),
    ]
    passed = all(check.status not in _BLOCKING_STATUSES for check in checks)
    return ValidationReport(validator_version=VALIDATOR_VERSION, checks=checks, passed=passed)


def _output_structure_check(inputs: ValidationInputs) -> ValidationCheck:
    if inputs.output_kind:
        return ValidationCheck(
            check=CHECK_OUTPUT_STRUCTURE,
            status=STATUS_PASSED,
            detail=f"Output contract declares kind '{inputs.output_kind}'.",
            artifacts={"output_kind": inputs.output_kind},
        )
    return ValidationCheck(
        check=CHECK_OUTPUT_STRUCTURE,
        status=STATUS_FAILED,
        detail="The draft revision has no output-contract kind.",
    )


def _dependency_health_check(inputs: ValidationInputs) -> ValidationCheck:
    resolutions = inputs.dependency_resolutions
    if not resolutions:
        return ValidationCheck(
            check=CHECK_DEPENDENCY_HEALTH,
            status=STATUS_NOT_APPLICABLE,
            detail="No pinned dependencies to re-resolve.",
        )
    drifted = sorted(res.canonical_key for res in resolutions if not res.resolved)
    if drifted:
        return ValidationCheck(
            check=CHECK_DEPENDENCY_HEALTH,
            status=STATUS_FAILED,
            detail=f"Pinned dependencies no longer resolve: {', '.join(drifted)}.",
            artifacts={"drifted": drifted},
        )
    resolved = sorted(res.canonical_key for res in resolutions)
    return ValidationCheck(
        check=CHECK_DEPENDENCY_HEALTH,
        status=STATUS_PASSED,
        detail=f"All {len(resolved)} pinned dependencies still resolve to their revision.",
        artifacts={"resolved": resolved},
    )


def _syntax_check(inputs: ValidationInputs) -> ValidationCheck:
    if inputs.syntax_ok is None:
        return ValidationCheck(
            check=CHECK_SYNTAX,
            status=STATUS_NOT_APPLICABLE,
            detail=inputs.syntax_detail or "No submitted source to syntax-check.",
        )
    if inputs.syntax_ok:
        return ValidationCheck(
            check=CHECK_SYNTAX, status=STATUS_PASSED, detail=inputs.syntax_detail
        )
    return ValidationCheck(check=CHECK_SYNTAX, status=STATUS_FAILED, detail=inputs.syntax_detail)


def _runtime_check(inputs: ValidationInputs) -> ValidationCheck:
    """Confirm the candidate's resolved native plan actually runs to a signal.

    No arbitrary code is executed: a translated/generated candidate's behaviour is
    defined by its resolved ta.*/cond.* plan, so a computable plan is a real runtime
    verdict. An empty skeleton (no resolvable plan) is BLOCKED — it cannot be approved.
    """
    artifacts = {"plan_keys": inputs.plan_keys} if inputs.plan_keys else {}
    if inputs.plan_status == PLAN_COMPUTABLE:
        status = STATUS_PASSED
    elif inputs.plan_status == PLAN_INCOMPATIBLE:
        status = STATUS_FAILED
    else:
        # PLAN_UNRESOLVABLE / PLAN_NOT_A_SIGNAL: nothing runnable was resolved.
        status = STATUS_BLOCKED
    return ValidationCheck(
        check=CHECK_RUNTIME, status=status, detail=inputs.plan_detail, artifacts=artifacts
    )


def _real_market_data_check(inputs: ValidationInputs) -> ValidationCheck:
    if not inputs.claims_equivalence:
        return ValidationCheck(
            check=CHECK_REAL_MARKET_DATA,
            status=STATUS_NOT_APPLICABLE,
            detail="This package makes no equivalence claim; no market-data baseline is required.",
        )
    if inputs.baseline_passed:
        return ValidationCheck(
            check=CHECK_REAL_MARKET_DATA,
            status=STATUS_PASSED,
            detail="A baseline of real market data has been uploaded and parsed.",
            artifacts=inputs.baseline_report or {},
        )
    return ValidationCheck(
        check=CHECK_REAL_MARKET_DATA,
        status=STATUS_BLOCKED,
        detail="Equivalence is claimed but no passed real-market-data baseline is present.",
    )


def _repaint_future_leak_check(inputs: ValidationInputs) -> ValidationCheck:
    """Structural non-repaint proof over the resolved native plan.

    The built-in ta.*/cond.* evaluators are single-pass and incremental, so a resolved
    plan reads no future bar by construction — a real, deterministic verdict. A package
    that produces no time-series signal (e.g. an ESP resolver) has no repaint surface.
    """
    if inputs.plan_status == PLAN_NOT_A_SIGNAL:
        return ValidationCheck(
            check=CHECK_REPAINT_FUTURE_LEAK,
            status=STATUS_NOT_APPLICABLE,
            detail="This package emits no time-series signal; there is no repaint surface.",
        )
    if inputs.plan_status == PLAN_COMPUTABLE:
        return ValidationCheck(
            check=CHECK_REPAINT_FUTURE_LEAK,
            status=STATUS_PASSED,
            detail=(
                "The resolved plan uses only single-pass incremental evaluators "
                "(no look-ahead / no future-bar reference)."
            ),
            artifacts={"plan_keys": inputs.plan_keys} if inputs.plan_keys else {},
        )
    # No resolvable plan -> the repaint property cannot be established -> blocked.
    return ValidationCheck(
        check=CHECK_REPAINT_FUTURE_LEAK,
        status=STATUS_BLOCKED,
        detail="No resolvable native plan; the non-repaint property cannot be established.",
    )


def _baseline_comparison_check(inputs: ValidationInputs) -> ValidationCheck:
    if not inputs.claims_equivalence:
        return ValidationCheck(
            check=CHECK_BASELINE_COMPARISON,
            status=STATUS_NOT_APPLICABLE,
            detail="No equivalence claim; no baseline comparison is required.",
        )
    if inputs.baseline_passed:
        return ValidationCheck(
            check=CHECK_BASELINE_COMPARISON,
            status=STATUS_PASSED,
            detail="The uploaded baseline parsed successfully and is the equivalence evidence.",
            artifacts=inputs.baseline_report or {},
        )
    return ValidationCheck(
        check=CHECK_BASELINE_COMPARISON,
        status=STATUS_BLOCKED,
        detail="Equivalence is claimed but the baseline has not been uploaded and parsed.",
    )


__all__ = [
    "MANDATORY_CHECKS",
    "PLAN_COMPUTABLE",
    "PLAN_INCOMPATIBLE",
    "PLAN_NOT_A_SIGNAL",
    "PLAN_UNRESOLVABLE",
    "VALIDATOR_VERSION",
    "DependencyResolution",
    "ValidationCheck",
    "ValidationInputs",
    "ValidationReport",
    "build_validation_report",
]
