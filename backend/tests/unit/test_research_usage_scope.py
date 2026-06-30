"""Usage-scope consumption matrix unit tests (doc 12 §9.3, §10, DR5)."""

from __future__ import annotations

import pytest

from entropia.domain.research_data.enums import UsageScope
from entropia.domain.research_data.usage_scope import (
    allows_agent_research,
    allows_direct_strategy_binding,
    allows_evidence_bundle,
    ensure_allows_evidence_bundle,
    requires_feature_definition,
)
from entropia.shared.errors import FieldMeaningInsufficient, UsageScopeForbidden


def test_every_scope_allows_agent_research() -> None:
    for scope in UsageScope:
        assert allows_agent_research(scope)


def test_evidence_bundle_membership() -> None:
    assert allows_evidence_bundle(UsageScope.RESEARCH_BACKTEST)
    assert not allows_evidence_bundle(UsageScope.AGENT_RESEARCH_ONLY)
    assert not allows_evidence_bundle(UsageScope.FEATURE_INPUT_ONLY)


def test_direct_strategy_binding_never_allowed() -> None:
    for scope in UsageScope:
        assert not allows_direct_strategy_binding(scope)


def test_feature_input_only_requires_feature_definition() -> None:
    assert requires_feature_definition(UsageScope.FEATURE_INPUT_ONLY)
    assert not requires_feature_definition(UsageScope.RESEARCH_BACKTEST)


def test_ensure_research_backtest_passes() -> None:
    ensure_allows_evidence_bundle(
        UsageScope.RESEARCH_BACKTEST, has_approved_feature_definition=False
    )


def test_ensure_agent_research_only_forbidden() -> None:
    with pytest.raises(UsageScopeForbidden):
        ensure_allows_evidence_bundle(
            UsageScope.AGENT_RESEARCH_ONLY, has_approved_feature_definition=True
        )


def test_ensure_feature_input_only_needs_feature() -> None:
    with pytest.raises(FieldMeaningInsufficient):
        ensure_allows_evidence_bundle(
            UsageScope.FEATURE_INPUT_ONLY, has_approved_feature_definition=False
        )
    # With an approved feature definition it is allowed.
    ensure_allows_evidence_bundle(
        UsageScope.FEATURE_INPUT_ONLY, has_approved_feature_definition=True
    )
