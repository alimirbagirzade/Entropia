"""Unit tests for the honest Create-Package validation gate (GAP-07, F-13).

The gate is strict: ``not_executed`` and ``blocked`` are NOT passes, and a report is
``passed`` iff every mandatory check is ``passed`` (or genuinely ``not_applicable``).
A check that should run but cannot (no resolvable native plan, an equivalence claim
with no baseline) is ``blocked`` and prevents approval.
"""

from __future__ import annotations

from entropia.domain.create_package.validation import (
    CHECK_BASELINE_COMPARISON,
    CHECK_DEPENDENCY_HEALTH,
    CHECK_OUTPUT_STRUCTURE,
    CHECK_REAL_MARKET_DATA,
    CHECK_REPAINT_FUTURE_LEAK,
    CHECK_RUNTIME,
    CHECK_SYNTAX,
    EXEC_ABSENT,
    EXEC_EMPTY,
    EXEC_ERROR,
    EXEC_EXECUTED,
    PLAN_COMPUTABLE,
    PLAN_UNRESOLVABLE,
    VALIDATOR_VERSION,
    DependencyResolution,
    ValidationInputs,
    build_validation_report,
)


def _status_of(report, check_name: str) -> str:
    return next(c.status for c in report.checks if c.check == check_name)


def _computable_indicator_inputs(**overrides) -> ValidationInputs:
    """A well-formed translated indicator: every mandatory check can pass."""
    base = {
        "package_kind": "indicator",
        "output_kind": "directional_signal",
        "dependency_resolutions": [
            DependencyResolution(canonical_key="ta.rsi", resolved=True, detail="rev_1")
        ],
        "syntax_ok": True,
        "syntax_detail": "Python source parses without syntax errors.",
        "plan_status": PLAN_COMPUTABLE,
        "plan_detail": "Resolves to a computable 'directional_signal' from ['ta.rsi'].",
        "plan_keys": ["ta.rsi"],
        "claims_equivalence": False,
        "baseline_passed": False,
        "baseline_report": None,
        # F-14: a well-formed candidate has a generated implementation that loaded and
        # executed to a non-empty plan in the sandbox.
        "execution_status": EXEC_EXECUTED,
        "execution_detail": "The generated implementation executed to a plan over ['ta.rsi'].",
        "execution_plan": {
            "output_kind": "directional_signal",
            "package_kind": "indicator",
            "primitives": ["ta.rsi"],
        },
    }
    base.update(overrides)
    return ValidationInputs(**base)


def test_hash_without_implementation_blocks_runtime() -> None:
    # F-14: a candidate hash with no stored/loadable implementation cannot be approved.
    report = build_validation_report(_computable_indicator_inputs(execution_status=EXEC_ABSENT))
    assert _status_of(report, CHECK_RUNTIME) == "blocked"
    assert report.passed is False


def test_empty_skeleton_execution_blocks_runtime() -> None:
    # F-14: an implementation that loads but yields an empty plan is an empty skeleton.
    report = build_validation_report(
        _computable_indicator_inputs(
            execution_status=EXEC_EMPTY,
            execution_detail="loaded but the plan has no primitives (empty skeleton).",
            plan_status=PLAN_UNRESOLVABLE,
            plan_keys=[],
        )
    )
    assert _status_of(report, CHECK_RUNTIME) == "blocked"
    assert report.passed is False


def test_non_executable_implementation_fails_runtime() -> None:
    # F-14: a generated implementation that fails to load/execute is a real failure.
    report = build_validation_report(
        _computable_indicator_inputs(
            execution_status=EXEC_ERROR,
            execution_detail="The generated implementation failed to load: boom.",
        )
    )
    assert _status_of(report, CHECK_RUNTIME) == "failed"
    assert report.passed is False


def test_well_formed_candidate_passes_all_mandatory_checks() -> None:
    report = build_validation_report(_computable_indicator_inputs())
    assert report.passed is True
    assert report.validator_version == VALIDATOR_VERSION
    assert _status_of(report, CHECK_OUTPUT_STRUCTURE) == "passed"
    assert _status_of(report, CHECK_DEPENDENCY_HEALTH) == "passed"
    assert _status_of(report, CHECK_SYNTAX) == "passed"
    assert _status_of(report, CHECK_RUNTIME) == "passed"
    assert _status_of(report, CHECK_REPAINT_FUTURE_LEAK) == "passed"
    # No equivalence claim -> the two market-data checks genuinely do not apply.
    assert _status_of(report, CHECK_REAL_MARKET_DATA) == "not_applicable"
    assert _status_of(report, CHECK_BASELINE_COMPARISON) == "not_applicable"


def test_missing_output_kind_fails() -> None:
    report = build_validation_report(_computable_indicator_inputs(output_kind=None))
    assert report.passed is False
    assert _status_of(report, CHECK_OUTPUT_STRUCTURE) == "failed"


def test_dependency_drift_fails() -> None:
    report = build_validation_report(
        _computable_indicator_inputs(
            dependency_resolutions=[
                DependencyResolution(canonical_key="ta.rsi", resolved=True, detail="rev_1"),
                DependencyResolution(
                    canonical_key="ta.gone", resolved=False, detail="RESOLVER_NOT_RESOLVED"
                ),
            ]
        )
    )
    assert report.passed is False
    assert _status_of(report, CHECK_DEPENDENCY_HEALTH) == "failed"


def test_unresolvable_plan_blocks_runtime_and_repaint_and_prevents_pass() -> None:
    # An empty skeleton (no resolvable native plan) blocks approval — a blocked
    # mandatory check is not a pass (F-13 acceptance).
    report = build_validation_report(
        _computable_indicator_inputs(
            plan_status=PLAN_UNRESOLVABLE,
            plan_detail="No 'ta.*' dependency resolved.",
            plan_keys=[],
            dependency_resolutions=[],
        )
    )
    assert report.passed is False
    assert _status_of(report, CHECK_RUNTIME) == "blocked"
    assert _status_of(report, CHECK_REPAINT_FUTURE_LEAK) == "blocked"


def test_failed_syntax_prevents_pass() -> None:
    report = build_validation_report(
        _computable_indicator_inputs(syntax_ok=False, syntax_detail="Python syntax error.")
    )
    assert report.passed is False
    assert _status_of(report, CHECK_SYNTAX) == "failed"


def test_description_request_syntax_is_not_applicable_not_a_pass_label() -> None:
    # A description request has no source to syntax-check; that alone must not gate,
    # but its plan must still resolve for runtime to pass.
    report = build_validation_report(_computable_indicator_inputs(syntax_ok=None, syntax_detail=""))
    assert _status_of(report, CHECK_SYNTAX) == "not_applicable"
    assert report.passed is True


def test_equivalence_claim_without_baseline_blocks_market_and_baseline_checks() -> None:
    report = build_validation_report(
        _computable_indicator_inputs(claims_equivalence=True, baseline_passed=False)
    )
    assert report.passed is False
    assert _status_of(report, CHECK_REAL_MARKET_DATA) == "blocked"
    assert _status_of(report, CHECK_BASELINE_COMPARISON) == "blocked"


def test_equivalence_claim_with_passed_baseline_passes() -> None:
    report = build_validation_report(
        _computable_indicator_inputs(
            claims_equivalence=True,
            baseline_passed=True,
            baseline_report={"content_digest": "sha256:abc", "attempt_no": 1},
        )
    )
    assert report.passed is True
    assert _status_of(report, CHECK_REAL_MARKET_DATA) == "passed"
    assert _status_of(report, CHECK_BASELINE_COMPARISON) == "passed"
    # The baseline evidence is surfaced as real per-check output, never a bare label.
    baseline_check = next(c for c in report.checks if c.check == CHECK_BASELINE_COMPARISON)
    assert baseline_check.artifacts["content_digest"] == "sha256:abc"
