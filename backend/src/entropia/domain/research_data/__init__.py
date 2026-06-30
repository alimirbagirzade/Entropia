"""Research Data domain surface (doc 12). Re-exports only; no logic here."""

from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    EventTimeSemantics,
    FrequencyPolicy,
    ResearchCategory,
    ResearchRevisionState,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.domain.research_data.policy import (
    ensure_can_approve,
    ensure_can_edit_draft,
    ensure_can_revoke,
    ensure_can_view,
)
from entropia.domain.research_data.state_machine import (
    IllegalResearchRevisionTransition,
    can_approve,
    can_deprecate,
    can_revoke,
    can_verify,
    next_research_revision_state,
)
from entropia.domain.research_data.time_policy import (
    MAX_AVAILABLE_DELAY,
    available_time_is_consistent,
    delay_is_valid,
    is_eligible_for_decision,
    resolve_available_at,
    time_policy_is_valid,
)
from entropia.domain.research_data.usage_scope import (
    allows_agent_research,
    allows_direct_strategy_binding,
    allows_evidence_bundle,
    ensure_allows_evidence_bundle,
    requires_feature_definition,
)
from entropia.domain.research_data.value_objects import (
    AvailableTimeSpec,
    CategorySpec,
    FieldDefinition,
    ResearchTimezoneSpec,
)

__all__ = [
    "MAX_AVAILABLE_DELAY",
    "AvailableTimePolicy",
    "AvailableTimeSpec",
    "CategorySpec",
    "EventTimeSemantics",
    "FieldDefinition",
    "FrequencyPolicy",
    "IllegalResearchRevisionTransition",
    "ResearchCategory",
    "ResearchRevisionState",
    "ResearchTimezoneMode",
    "ResearchTimezoneSpec",
    "UsageScope",
    "allows_agent_research",
    "allows_direct_strategy_binding",
    "allows_evidence_bundle",
    "available_time_is_consistent",
    "can_approve",
    "can_deprecate",
    "can_revoke",
    "can_verify",
    "delay_is_valid",
    "ensure_allows_evidence_bundle",
    "ensure_can_approve",
    "ensure_can_edit_draft",
    "ensure_can_revoke",
    "ensure_can_view",
    "is_eligible_for_decision",
    "next_research_revision_state",
    "requires_feature_definition",
    "resolve_available_at",
    "time_policy_is_valid",
]
