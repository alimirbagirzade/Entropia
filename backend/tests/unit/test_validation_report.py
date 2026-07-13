"""Unit tests for the deterministic Create-Package validation evidence (GAP-07)."""

from __future__ import annotations

from entropia.domain.create_package.validation import (
    CHECK_DEPENDENCY_HEALTH,
    CHECK_OUTPUT_STRUCTURE,
    VALIDATOR_VERSION,
    DependencyResolution,
    build_validation_report,
)

_DEFERRED = {"syntax", "runtime", "real_market_data", "repaint_future_leak", "baseline_comparison"}


def _status_of(report, check_name: str) -> str:
    return next(c.status for c in report.checks if c.check == check_name)


def test_output_structure_and_dep_health_pass() -> None:
    report = build_validation_report(
        output_kind="directional_signal",
        dependency_resolutions=[
            DependencyResolution(canonical_key="ta.rsi", resolved=True, detail="rev_1")
        ],
    )
    assert report.passed is True
    assert report.validator_version == VALIDATOR_VERSION
    assert _status_of(report, CHECK_OUTPUT_STRUCTURE) == "passed"
    assert _status_of(report, CHECK_DEPENDENCY_HEALTH) == "passed"


def test_missing_output_kind_fails() -> None:
    report = build_validation_report(output_kind=None, dependency_resolutions=[])
    assert report.passed is False
    assert _status_of(report, CHECK_OUTPUT_STRUCTURE) == "failed"


def test_dependency_drift_fails() -> None:
    report = build_validation_report(
        output_kind="directional_signal",
        dependency_resolutions=[
            DependencyResolution(canonical_key="ta.rsi", resolved=True, detail="rev_1"),
            DependencyResolution(
                canonical_key="ta.gone", resolved=False, detail="RESOLVER_NOT_RESOLVED"
            ),
        ],
    )
    assert report.passed is False
    assert _status_of(report, CHECK_DEPENDENCY_HEALTH) == "failed"


def test_no_dependencies_marks_health_not_executed_but_still_passes() -> None:
    report = build_validation_report(output_kind="boolean_condition", dependency_resolutions=[])
    assert report.passed is True
    assert _status_of(report, CHECK_DEPENDENCY_HEALTH) == "not_executed"


def test_execution_based_checks_are_recorded_not_executed() -> None:
    report = build_validation_report(output_kind="directional_signal", dependency_resolutions=[])
    deferred = {c.check for c in report.checks if c.status == "not_executed"}
    # The five execution-based checks are honestly recorded as deferred (Future-Dev).
    assert deferred >= _DEFERRED
