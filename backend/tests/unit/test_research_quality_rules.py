"""R9 — semantic quality checks for research data (doc 12 §10). Pure, no DB.

Covers each check family (coverage / duplicates / null density / type consistency /
numeric ranges / instrument mapping) and the severity contract wired into
``evaluate_research``: only a blocker forces NEEDS_REVIEW; a warning still verifies.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from entropia.application.jobs.research_data import (
    ParsedResearch,
    evaluate_research,
    normalize_event_timestamps,
    revision_source_zone,
)
from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    ResearchRevisionState,
    ResearchTimezoneMode,
)
from entropia.domain.research_data.quality_rules import evaluate_quality

_UTC = ZoneInfo("UTC")

INF = float("inf")
NAN = float("nan")


def _codes(report: Any) -> set[str]:
    return {issue.check_id for issue in report.issues}


def _by_code(report: Any, check_id: str) -> Any:
    return next(issue for issue in report.issues if issue.check_id == check_id)


# --- evaluate_quality: individual families ---------------------------------------


def test_clean_data_has_no_issues() -> None:
    rows = [{"x": i, "label": f"row-{i}"} for i in range(5)]
    report = evaluate_quality(["x", "label"], rows, source_zone=_UTC)
    assert report.worst == ValidationStatus.PASS
    assert report.issues == ()


def test_empty_rows_block_coverage() -> None:
    report = evaluate_quality(["x"], [], source_zone=_UTC)
    assert report.worst == ValidationStatus.BLOCKING_FAIL
    issue = _by_code(report, "COVERAGE_INSUFFICIENT")
    assert issue.severity == ValidationStatus.BLOCKING_FAIL
    assert issue.evidence == {"row_count": 0}


def test_excessive_duplicates_block() -> None:
    rows = [{"x": 1, "y": "a"} for _ in range(4)]  # 3/4 duplicate -> majority
    report = evaluate_quality(["x", "y"], rows, source_zone=_UTC)
    issue = _by_code(report, "DUPLICATE_EXCESSIVE")
    assert issue.severity == ValidationStatus.BLOCKING_FAIL
    assert issue.occurrences == 3
    assert issue.evidence["duplicate_fraction"] == 0.75


def test_moderate_duplicates_warn() -> None:
    rows = [{"x": i} for i in range(8)] + [{"x": 0}, {"x": 1}]  # 2/10 duplicate
    report = evaluate_quality(["x"], rows, source_zone=_UTC)
    issue = _by_code(report, "DUPLICATE_EXCESSIVE")
    assert issue.severity == ValidationStatus.WARNING
    assert issue.occurrences == 2


def test_high_null_density_warns_and_names_column() -> None:
    rows = [{"x": 1, "oi": None}, {"x": 2, "oi": None}, {"x": 3, "oi": 9}, {"x": 4, "oi": None}]
    report = evaluate_quality(["x", "oi"], rows, source_zone=_UTC)
    issue = _by_code(report, "NULL_DENSITY_HIGH")
    assert issue.severity == ValidationStatus.WARNING
    names = {col["column"] for col in issue.evidence["columns"]}
    assert names == {"oi"}
    assert issue.evidence["columns"][0]["null_fraction"] == 0.75


def test_type_inconsistency_warns() -> None:
    rows = [{"z": "1"}, {"z": "2"}, {"z": "hello"}, {"z": "world"}]
    report = evaluate_quality(["z"], rows, source_zone=_UTC)
    issue = _by_code(report, "TYPE_INCONSISTENT")
    assert issue.severity == ValidationStatus.WARNING
    assert issue.evidence["columns"][0]["column"] == "z"


def test_pure_string_column_is_not_type_inconsistent() -> None:
    rows = [{"sym": s} for s in ("BTC", "ETH", "SOL")]
    report = evaluate_quality(["sym"], rows, source_zone=_UTC)
    assert "TYPE_INCONSISTENT" not in _codes(report)


def test_non_finite_numeric_warns() -> None:
    rows = [{"p": 1.0}, {"p": 2.0}, {"p": NAN}, {"p": INF}]
    report = evaluate_quality(["p"], rows, source_zone=_UTC)
    issue = _by_code(report, "NUMERIC_NON_FINITE")
    assert issue.severity == ValidationStatus.WARNING
    assert issue.occurrences == 2


def test_nan_is_not_counted_as_null() -> None:
    # A present-but-NaN value is a range violation, never a null-density one.
    rows = [{"p": 1.0}, {"p": NAN}]
    report = evaluate_quality(["p"], rows, source_zone=_UTC)
    assert "NULL_DENSITY_HIGH" not in _codes(report)
    assert "NUMERIC_NON_FINITE" in _codes(report)


def test_instrument_link_without_ref_warns() -> None:
    rows = [{"x": 1}]
    report = evaluate_quality(
        ["x"],
        rows,
        source_zone=_UTC,
        linked_market_dataset_revision_id="mdr_1",
        instrument_mapping_ref=None,
    )
    issue = _by_code(report, "INSTRUMENT_MAPPING_INVALID")
    assert issue.evidence == {"has_link": True, "has_mapping_ref": False}


def test_instrument_ref_without_link_warns() -> None:
    rows = [{"x": 1}]
    report = evaluate_quality(
        ["x"],
        rows,
        source_zone=_UTC,
        linked_market_dataset_revision_id=None,
        instrument_mapping_ref="BTCUSD",
    )
    issue = _by_code(report, "INSTRUMENT_MAPPING_INVALID")
    assert issue.evidence == {"has_link": False, "has_mapping_ref": True}


def test_instrument_mapping_coherent_has_no_issue() -> None:
    rows = [{"x": 1}]
    both = evaluate_quality(
        ["x"],
        rows,
        source_zone=_UTC,
        linked_market_dataset_revision_id="mdr_1",
        instrument_mapping_ref="BTCUSD",
    )
    neither = evaluate_quality(["x"], rows, source_zone=_UTC)
    assert "INSTRUMENT_MAPPING_INVALID" not in _codes(both)
    assert "INSTRUMENT_MAPPING_INVALID" not in _codes(neither)


def test_worst_is_blocking_when_any_blocker_present() -> None:
    # Empty rows (blocking coverage) alongside a dangling instrument ref (warning).
    report = evaluate_quality([], [], source_zone=_UTC, instrument_mapping_ref="BTCUSD")
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
        # K-01: the declared source timezone the ingest normalizer localizes with.
        source_timezone_mode=ResearchTimezoneMode.UTC,
        source_timezone_iana=None,
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


# --------------------------------------------------------------------------- #
# K-01 — the declared source timezone is applied at research ingest
# (doc 12 §8.4 rule 1: read in the source zone, normalize to UTC, keep metadata)
# --------------------------------------------------------------------------- #

_NEW_YORK = ZoneInfo("America/New_York")
_ISTANBUL = ZoneInfo("Asia/Istanbul")


def test_naive_event_times_without_a_resolvable_zone_block_with_the_canonical_code() -> None:
    rows = [{"event_time": "2024-07-15T09:30:00", "oi": 1} for _ in range(3)]
    report = evaluate_quality(["event_time", "oi"], rows, source_zone=None)
    issue = _by_code(report, "RESEARCH_DATA_TIMEZONE_UNRESOLVED")
    assert issue.severity == ValidationStatus.BLOCKING_FAIL
    assert issue.occurrences == 3
    assert issue.evidence == {"column": "event_time", "unresolved_rows": 3}


def test_naive_event_times_with_a_resolvable_zone_produce_no_finding() -> None:
    rows = [{"event_time": "2024-07-15T09:30:00", "oi": 1}]
    report = evaluate_quality(["event_time", "oi"], rows, source_zone=_NEW_YORK)
    assert "RESEARCH_DATA_TIMEZONE_UNRESOLVED" not in _codes(report)


def test_offset_carrying_event_times_never_need_a_zone() -> None:
    rows = [{"event_time": "2024-07-15T13:30:00+00:00", "oi": 1}]
    report = evaluate_quality(["event_time", "oi"], rows, source_zone=None)
    assert "RESEARCH_DATA_TIMEZONE_UNRESOLVED" not in _codes(report)


def test_schema_without_a_recognizable_event_time_column_is_not_flagged() -> None:
    """Research keeps its native schema (M5); an unrecognized shape is left alone."""
    rows = [{"some_metric": 1, "label": "a"}]
    report = evaluate_quality(["some_metric", "label"], rows, source_zone=None)
    assert "RESEARCH_DATA_TIMEZONE_UNRESOLVED" not in _codes(report)


def test_normalize_event_timestamps_localizes_in_istanbul() -> None:
    parsed = ParsedResearch(
        columns=["event_time", "oi"], rows=[{"event_time": "2024-07-15T09:30:00", "oi": 1}]
    )
    out = normalize_event_timestamps(parsed, source_zone=_ISTANBUL)
    # Istanbul is UTC+3 -> 09:30 local is 06:30 UTC.
    assert out.rows[0]["event_time"] == "2024-07-15T06:30:00+00:00"
    assert out.rows[0]["oi"] == 1  # every other column is untouched


def test_normalize_event_timestamps_leaves_unresolvable_cells_verbatim() -> None:
    parsed = ParsedResearch(columns=["event_time"], rows=[{"event_time": "2024-07-15T09:30:00"}])
    out = normalize_event_timestamps(parsed, source_zone=None)
    assert out.rows[0]["event_time"] == "2024-07-15T09:30:00"  # never guessed into UTC


def test_revision_source_zone_maps_each_declared_mode() -> None:
    assert revision_source_zone(_revision_tz(ResearchTimezoneMode.UTC)) == ZoneInfo("UTC")
    assert (
        revision_source_zone(_revision_tz(ResearchTimezoneMode.CUSTOM, "America/New_York"))
        == _NEW_YORK
    )
    # Exchange mode carries no IANA identifier -> unresolvable, fail-closed.
    assert revision_source_zone(_revision_tz(ResearchTimezoneMode.EXCHANGE)) is None
    # A stored identifier that no longer exists degrades instead of crashing the job.
    assert revision_source_zone(_revision_tz(ResearchTimezoneMode.CUSTOM, "Mars/Olympus")) is None


def _revision_tz(mode: Any, iana: str | None = None) -> Any:
    return SimpleNamespace(source_timezone_mode=mode, source_timezone_iana=iana)


def test_evaluate_research_blocks_a_naive_source_under_an_unresolvable_zone() -> None:
    """End of the chain: a wrong-instant payload can never auto-verify."""
    revision = _revision()
    revision.source_timezone_mode = ResearchTimezoneMode.EXCHANGE
    revision.source_timezone_iana = None
    parsed = ParsedResearch(
        columns=["event_time", "oi"],
        rows=[{"event_time": f"2024-07-1{i}T09:30:00", "oi": i} for i in range(1, 4)],
    )
    outcome = evaluate_research(parsed, revision)
    assert outcome.status == ValidationStatus.BLOCKING_FAIL
    assert outcome.next_state == ResearchRevisionState.NEEDS_REVIEW
    assert any(i["check_id"] == "RESEARCH_DATA_TIMEZONE_UNRESOLVED" for i in outcome.issues)
