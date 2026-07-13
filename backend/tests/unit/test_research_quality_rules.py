"""R9 — semantic quality checks for research data (doc 12 §10). Pure, no DB.

Covers each check family (coverage / duplicates / null density / type consistency /
numeric ranges / instrument mapping) and the severity contract wired into
``evaluate_research``: only a blocker forces NEEDS_REVIEW; a warning still verifies.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from entropia.application.jobs.research_data import ParsedResearch, evaluate_research
from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.research_data.enums import AvailableTimePolicy, ResearchRevisionState
from entropia.domain.research_data.quality_rules import evaluate_quality

INF = float("inf")
NAN = float("nan")


def _codes(report: Any) -> set[str]:
    return {issue.check_id for issue in report.issues}


def _by_code(report: Any, check_id: str) -> Any:
    return next(issue for issue in report.issues if issue.check_id == check_id)


# --- evaluate_quality: individual families ---------------------------------------


def test_clean_data_has_no_issues() -> None:
    rows = [{"x": i, "label": f"row-{i}"} for i in range(5)]
    report = evaluate_quality(["x", "label"], rows)
    assert report.worst == ValidationStatus.PASS
    assert report.issues == ()


def test_empty_rows_block_coverage() -> None:
    report = evaluate_quality(["x"], [])
    assert report.worst == ValidationStatus.BLOCKING_FAIL
    issue = _by_code(report, "COVERAGE_INSUFFICIENT")
    assert issue.severity == ValidationStatus.BLOCKING_FAIL
    assert issue.evidence == {"row_count": 0}


def test_excessive_duplicates_block() -> None:
    rows = [{"x": 1, "y": "a"} for _ in range(4)]  # 3/4 duplicate -> majority
    report = evaluate_quality(["x", "y"], rows)
    issue = _by_code(report, "DUPLICATE_EXCESSIVE")
    assert issue.severity == ValidationStatus.BLOCKING_FAIL
    assert issue.occurrences == 3
    assert issue.evidence["duplicate_fraction"] == 0.75


def test_moderate_duplicates_warn() -> None:
    rows = [{"x": i} for i in range(8)] + [{"x": 0}, {"x": 1}]  # 2/10 duplicate
    report = evaluate_quality(["x"], rows)
    issue = _by_code(report, "DUPLICATE_EXCESSIVE")
    assert issue.severity == ValidationStatus.WARNING
    assert issue.occurrences == 2


def test_high_null_density_warns_and_names_column() -> None:
    rows = [{"x": 1, "oi": None}, {"x": 2, "oi": None}, {"x": 3, "oi": 9}, {"x": 4, "oi": None}]
    report = evaluate_quality(["x", "oi"], rows)
    issue = _by_code(report, "NULL_DENSITY_HIGH")
    assert issue.severity == ValidationStatus.WARNING
    names = {col["column"] for col in issue.evidence["columns"]}
    assert names == {"oi"}
    assert issue.evidence["columns"][0]["null_fraction"] == 0.75


def test_type_inconsistency_warns() -> None:
    rows = [{"z": "1"}, {"z": "2"}, {"z": "hello"}, {"z": "world"}]
    report = evaluate_quality(["z"], rows)
    issue = _by_code(report, "TYPE_INCONSISTENT")
    assert issue.severity == ValidationStatus.WARNING
    assert issue.evidence["columns"][0]["column"] == "z"


def test_pure_string_column_is_not_type_inconsistent() -> None:
    rows = [{"sym": s} for s in ("BTC", "ETH", "SOL")]
    report = evaluate_quality(["sym"], rows)
    assert "TYPE_INCONSISTENT" not in _codes(report)


def test_non_finite_numeric_warns() -> None:
    rows = [{"p": 1.0}, {"p": 2.0}, {"p": NAN}, {"p": INF}]
    report = evaluate_quality(["p"], rows)
    issue = _by_code(report, "NUMERIC_NON_FINITE")
    assert issue.severity == ValidationStatus.WARNING
    assert issue.occurrences == 2


def test_nan_is_not_counted_as_null() -> None:
    # A present-but-NaN value is a range violation, never a null-density one.
    rows = [{"p": 1.0}, {"p": NAN}]
    report = evaluate_quality(["p"], rows)
    assert "NULL_DENSITY_HIGH" not in _codes(report)
    assert "NUMERIC_NON_FINITE" in _codes(report)


def test_instrument_link_without_ref_warns() -> None:
    rows = [{"x": 1}]
    report = evaluate_quality(
        ["x"], rows, linked_market_dataset_revision_id="mdr_1", instrument_mapping_ref=None
    )
    issue = _by_code(report, "INSTRUMENT_MAPPING_INVALID")
    assert issue.evidence == {"has_link": True, "has_mapping_ref": False}


def test_instrument_ref_without_link_warns() -> None:
    rows = [{"x": 1}]
    report = evaluate_quality(
        ["x"], rows, linked_market_dataset_revision_id=None, instrument_mapping_ref="BTCUSD"
    )
    issue = _by_code(report, "INSTRUMENT_MAPPING_INVALID")
    assert issue.evidence == {"has_link": False, "has_mapping_ref": True}


def test_instrument_mapping_coherent_has_no_issue() -> None:
    rows = [{"x": 1}]
    both = evaluate_quality(
        ["x"], rows, linked_market_dataset_revision_id="mdr_1", instrument_mapping_ref="BTCUSD"
    )
    neither = evaluate_quality(["x"], rows)
    assert "INSTRUMENT_MAPPING_INVALID" not in _codes(both)
    assert "INSTRUMENT_MAPPING_INVALID" not in _codes(neither)


def test_worst_is_blocking_when_any_blocker_present() -> None:
    # Empty rows (blocking coverage) alongside a dangling instrument ref (warning).
    report = evaluate_quality([], [], instrument_mapping_ref="BTCUSD")
    assert report.worst == ValidationStatus.BLOCKING_FAIL


# --- evaluate_research: merge + severity contract --------------------------------


def _revision(
    *,
    policy: AvailableTimePolicy | None = AvailableTimePolicy.SAME_AS_EVENT_TIME,
    delay: int | None = None,
    link: str | None = None,
    ref: str | None = None,
) -> Any:
    return SimpleNamespace(
        available_time_policy=policy,
        available_delay_seconds=delay,
        linked_market_dataset_revision_id=link,
        instrument_mapping_ref=ref,
    )


def test_evaluate_research_verifies_clean_data() -> None:
    parsed = ParsedResearch(columns=["x"], rows=[{"x": i} for i in range(3)])
    outcome = evaluate_research(parsed, _revision())
    assert outcome.status == ValidationStatus.PASS
    assert outcome.next_state == ResearchRevisionState.VERIFIED
    assert outcome.issues == []


def test_evaluate_research_warns_but_still_verifies() -> None:
    # A null-heavy column is a WARNING; the revision still auto-verifies (§10.1).
    rows = [{"x": None}, {"x": None}, {"x": 3}]
    parsed = ParsedResearch(columns=["x"], rows=rows)
    outcome = evaluate_research(parsed, _revision())
    assert outcome.status == ValidationStatus.WARNING
    assert outcome.next_state == ResearchRevisionState.VERIFIED
    assert any(i["check_id"] == "NULL_DENSITY_HIGH" for i in outcome.issues)


def test_evaluate_research_blocks_on_empty_coverage() -> None:
    parsed = ParsedResearch(columns=["x"], rows=[])
    outcome = evaluate_research(parsed, _revision())
    assert outcome.status == ValidationStatus.BLOCKING_FAIL
    assert outcome.next_state == ResearchRevisionState.NEEDS_REVIEW
    assert any(i["check_id"] == "COVERAGE_INSUFFICIENT" for i in outcome.issues)


def test_evaluate_research_blocks_on_invalid_time_policy() -> None:
    parsed = ParsedResearch(columns=["x"], rows=[{"x": 1}])
    outcome = evaluate_research(parsed, _revision(policy=None))
    assert outcome.status == ValidationStatus.BLOCKING_FAIL
    assert outcome.next_state == ResearchRevisionState.NEEDS_REVIEW
    assert any(i["check_id"] == "TIME_POLICY" for i in outcome.issues)
