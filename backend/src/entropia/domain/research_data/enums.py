"""Research Data per-domain enums (doc 12, CR-04).

All values are lowercase snake_case and are returned over REST/SSE verbatim.
The research revision lifecycle (``ResearchRevisionState``) is a SEPARATE facet
from the shared deletion/validation/approval/visibility enums and never collapses
into a single status column. ``UsageScope`` governs *consumption* (doc 12 §9.3),
not merely visibility.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchRevisionState(StrEnum):
    """Research dataset revision lifecycle (doc 12 §8.2, DOMAIN_MODEL §3.2).

    ``verified`` is distinct from ``approved``: only an Admin moves verified ->
    approved, and only an ACTIVE+APPROVED revision feeds backtest evidence
    bundles. ``approval_revoked`` stops new use without mutating pinned manifests.
    """

    DRAFT = "draft"
    ANALYZING = "analyzing"
    NEEDS_REVIEW = "needs_review"
    VERIFIED = "verified"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    APPROVAL_REVOKED = "approval_revoked"


class ResearchCategory(StrEnum):
    """Built-in research data categories (doc 12 §5.1). The set is *extensible*:
    ``OTHER_CUSTOM`` carries a free-text ``custom_category`` and the persisted
    ``category_key`` is never a closed enum at the column level (stored as text)."""

    OPEN_INTEREST = "open_interest"
    FUNDING_RATE = "funding_rate"
    LIQUIDATIONS = "liquidations"
    ORDER_BOOK = "order_book"
    LIQUIDITY_HEATMAP = "liquidity_heatmap"
    ONCHAIN_FLOWS = "onchain_flows"
    MACRO_CALENDAR = "macro_calendar"
    OTHER_CUSTOM = "other_custom"


class UsageScope(StrEnum):
    """What system behavior a revision may feed (doc 12 §5.3, §9.3 matrix).

    * ``research_backtest`` — eligible for Evidence Bundles after approval.
    * ``agent_research_only`` — investigation/context only; forbidden in backtest
      evidence bundles, feature input and trade triggers.
    * ``feature_input_only`` — requires an approved versioned feature definition
      before Strategy consumption; raw direct binding is forbidden.
    """

    RESEARCH_BACKTEST = "research_backtest"
    AGENT_RESEARCH_ONLY = "agent_research_only"
    FEATURE_INPUT_ONLY = "feature_input_only"


class EventTimeSemantics(StrEnum):
    """How a record's event timestamp is interpreted (doc 12 §5.2)."""

    PROVIDER_EVENT_TIMESTAMP = "provider_event_timestamp"
    PROVIDER_SNAPSHOT_TIMESTAMP = "provider_snapshot_timestamp"
    BAR_CLOSE_END_TIME = "bar_close_end_time"
    CUSTOM_DOCUMENTED_EVENT_TIME = "custom_documented_event_time"


class AvailableTimePolicy(StrEnum):
    """How the first real availability time of a record is derived (doc 12 §5.2).

    ``fixed_delay`` requires a positive bounded delay; all other rules must send
    ``delay=null`` so a stale prior delay never affects the engine.
    """

    SAME_AS_EVENT_TIME = "same_as_event_time"
    FIXED_DELAY = "fixed_delay"
    PROVIDER_PUBLISH_TIMESTAMP = "provider_publish_timestamp"
    CUSTOM_DOCUMENTED_RULE = "custom_documented_rule"


class FrequencyPolicy(StrEnum):
    """Declared cadence of the research records (doc 12 §5.2). Frequency is not a
    guarantee that coverage has no gaps."""

    EVENT_BASED = "event_based"
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H8 = "8h"
    D1 = "1d"
    PROVIDER_NATIVE = "provider_native"


class ResearchTimezoneMode(StrEnum):
    """Declared source timezone semantics (doc 12 §5.2). ``custom`` requires a
    valid IANA identifier."""

    UTC = "utc"
    EXCHANGE = "exchange"
    CUSTOM = "custom"
