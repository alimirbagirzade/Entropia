"""Usage-scope consumption matrix (doc 12 §9.3, §10).

Pure predicates over a revision's ``UsageScope`` describing which downstream
behavior may consume it. Usage scope governs *consumption*, not just visibility:
the command/bundle layer calls these and raises ``UsageScopeForbidden`` (or
``FieldMeaningInsufficient`` for the missing-feature case) on a forbidden use.

Matrix (doc 12 §9.3):

    scope               agent_research  feature_def     evidence_bundle  direct_strategy
    research_backtest   allowed         allowed         allowed*         never raw
    agent_research_only allowed         proposal only   forbidden        forbidden
    feature_input_only  allowed         required path   via feature only never raw

``*`` after approval + Ready-Check validation. "never raw" / "via feature only"
mean a versioned feature definition is the only legal path to a strategy.
"""

from __future__ import annotations

from entropia.domain.research_data.enums import UsageScope
from entropia.shared.errors import FieldMeaningInsufficient, UsageScopeForbidden


def allows_agent_research(scope: UsageScope) -> bool:
    """Every scope may be used for Agent research/context/quality notes."""
    return scope in {
        UsageScope.RESEARCH_BACKTEST,
        UsageScope.AGENT_RESEARCH_ONLY,
        UsageScope.FEATURE_INPUT_ONLY,
    }


def allows_evidence_bundle(scope: UsageScope) -> bool:
    """Backtest Evidence Bundle membership: only Research+Backtest revisions, and
    Feature-Input-Only *via an approved feature definition* (checked separately)."""
    return scope == UsageScope.RESEARCH_BACKTEST


def requires_feature_definition(scope: UsageScope) -> bool:
    """Feature-Input-Only needs a versioned feature definition before strategy use."""
    return scope == UsageScope.FEATURE_INPUT_ONLY


def allows_direct_strategy_binding(scope: UsageScope) -> bool:
    """Raw direct binding to a strategy condition is never allowed for any scope
    (doc 12 §9.3, M15 raw-data prohibition)."""
    return False


def ensure_allows_evidence_bundle(
    scope: UsageScope, *, has_approved_feature_definition: bool
) -> None:
    """Gate a revision entering a Backtest Evidence Bundle.

    * Agent-Research-Only -> ``UsageScopeForbidden``.
    * Feature-Input-Only without an approved feature definition ->
      ``FieldMeaningInsufficient`` (the versioned feature path is required).
    """
    if scope == UsageScope.RESEARCH_BACKTEST:
        return
    if scope == UsageScope.AGENT_RESEARCH_ONLY:
        raise UsageScopeForbidden(
            "Agent-Research-Only datasets cannot enter a Backtest Evidence Bundle."
        )
    if scope == UsageScope.FEATURE_INPUT_ONLY:
        if not has_approved_feature_definition:
            raise FieldMeaningInsufficient(
                "Feature-Input-Only requires an approved versioned feature definition."
            )
        return
    raise UsageScopeForbidden("This usage scope cannot enter a Backtest Evidence Bundle.")
