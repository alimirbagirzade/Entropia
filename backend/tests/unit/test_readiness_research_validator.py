"""O-01 — the pure Research Data readiness validator (doc 14 §9.2 Research row).

Before O-01 the Research layer was absent from Ready Check entirely: a composition
pinning an ineligible research revision reported READY and then died inside the
worker's ``FundingSourceInvalid`` gate. These cases pin the pure decision table
(``validate_research_sources``); the DB-backed wiring lives in
``tests/integration/test_readiness_research_data.py``.
"""

from __future__ import annotations

from entropia.domain.readiness.enums import ReadinessScope, ReadinessSeverity
from entropia.domain.readiness.issues import ResearchSourceState
from entropia.domain.readiness.validators import validate_research_sources

_FIELD = "data.funding.source_revision_id"


def _source(**overrides: object) -> ResearchSourceState:
    """An otherwise fully eligible pinned research revision."""
    base: dict[str, object] = {
        "item_id": "item_1",
        "revision_id": "rdrev_1",
        "field_path": _FIELD,
        "found": True,
        "root_active": True,
        "revision_state": "approved",
        "usage_scope": "research_backtest",
        "available_time_policy": "same_as_event_time",
        "available_delay_seconds": None,
        "linked_market_dataset_revision_id": None,
        "instrument_mapping_ref": None,
        "validation_status": "pass",
        "strategy_market_dataset_revision_id": "md_rev_1",
    }
    base.update(overrides)
    return ResearchSourceState(**base)  # type: ignore[arg-type]


def _codes(source: ResearchSourceState) -> list[str]:
    return [str(issue.code) for issue in validate_research_sources([source])]


def test_no_sources_yields_no_issues() -> None:
    assert validate_research_sources([]) == []


def test_fully_eligible_revision_yields_no_issues() -> None:
    assert _codes(_source()) == []


def test_agent_research_only_scope_blocks_backtest_consumption() -> None:
    issues = validate_research_sources([_source(usage_scope="agent_research_only")])
    assert [str(i.code) for i in issues] == ["USAGE_SCOPE_FORBIDDEN"]
    assert issues[0].severity == ReadinessSeverity.BLOCKER
    assert issues[0].scope == ReadinessScope.RESEARCH_DATA
    assert issues[0].field_path == _FIELD
    assert issues[0].scope_id == "item_1"


def test_feature_input_only_scope_is_not_a_raw_backtest_pin() -> None:
    assert _codes(_source(usage_scope="feature_input_only")) == ["USAGE_SCOPE_FORBIDDEN"]


def test_missing_available_time_policy_blocks() -> None:
    assert _codes(_source(available_time_policy=None)) == ["TIME_POLICY_INVALID"]


def test_fixed_delay_without_a_positive_delay_blocks() -> None:
    assert _codes(_source(available_time_policy="fixed_delay")) == ["TIME_POLICY_INVALID"]
    assert _codes(_source(available_time_policy="fixed_delay", available_delay_seconds=0)) == [
        "TIME_POLICY_INVALID"
    ]


def test_fixed_delay_with_a_positive_delay_passes() -> None:
    assert _codes(_source(available_time_policy="fixed_delay", available_delay_seconds=60)) == []


def test_link_to_another_market_revision_blocks() -> None:
    codes = _codes(
        _source(
            linked_market_dataset_revision_id="md_rev_other",
            instrument_mapping_ref="BTCUSDT",
        )
    )
    assert codes == ["DEPENDENCY_BLOCKED"]


def test_link_to_the_strategys_own_market_revision_passes() -> None:
    assert (
        _codes(
            _source(
                linked_market_dataset_revision_id="md_rev_1",
                instrument_mapping_ref="BTCUSDT",
            )
        )
        == []
    )


def test_incoherent_link_mapping_pair_blocks() -> None:
    # A link without a mapping...
    assert _codes(_source(linked_market_dataset_revision_id="md_rev_1")) == [
        "INSTRUMENT_MAPPING_INVALID"
    ]
    # ...and a mapping without a link.
    assert _codes(_source(instrument_mapping_ref="BTCUSDT")) == ["INSTRUMENT_MAPPING_INVALID"]


def test_warning_validation_status_is_a_warning_not_a_blocker() -> None:
    issues = validate_research_sources([_source(validation_status="warning")])
    assert [str(i.code) for i in issues] == ["RESEARCH_COVERAGE_LIMITED"]
    assert issues[0].severity == ReadinessSeverity.WARNING


def test_unresolvable_revision_blocks_alone() -> None:
    issues = validate_research_sources(
        [
            ResearchSourceState(
                item_id="item_1",
                revision_id="rdrev_missing",
                field_path=_FIELD,
                found=False,
                strategy_market_dataset_revision_id="md_rev_1",
            )
        ]
    )
    assert [str(i.code) for i in issues] == ["LIFECYCLE_BLOCKED"]


def test_unapproved_or_deleted_revision_blocks_alone() -> None:
    # An unapproved revision reports ONE lifecycle blocker, never a pile of findings
    # derived from a revision that is not eligible to be judged further.
    assert _codes(_source(revision_state="verified", usage_scope="agent_research_only")) == [
        "LIFECYCLE_BLOCKED"
    ]
    assert _codes(_source(root_active=False)) == ["LIFECYCLE_BLOCKED"]


def test_multiple_defects_on_one_revision_all_surface() -> None:
    codes = _codes(
        _source(
            usage_scope="agent_research_only",
            available_time_policy=None,
            linked_market_dataset_revision_id="md_rev_other",
            instrument_mapping_ref="BTCUSDT",
            validation_status="warning",
        )
    )
    assert codes == [
        "USAGE_SCOPE_FORBIDDEN",
        "TIME_POLICY_INVALID",
        "DEPENDENCY_BLOCKED",
        "RESEARCH_COVERAGE_LIMITED",
    ]
