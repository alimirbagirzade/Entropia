"""Backtest Ready Check domain enums (Stage 4b, doc 14 §4, §9.1-§9.2).

Lowercase snake_case ``StrEnum`` values, stored as canonical strings in
``ready_check_report`` / ``readiness_issue``. Severity is deliberately only
BLOCKER or WARNING — a PASS lives in the report summary, never as an issue row
(doc 14 §9.1 "Readiness Issue ... Severity only BLOCKER or WARNING").
"""

from __future__ import annotations

from enum import StrEnum


class ReadinessSeverity(StrEnum):
    """A readiness finding severity (doc 14 §9.1). PASS is summary-only."""

    BLOCKER = "blocker"
    WARNING = "warning"


class ReadinessState(StrEnum):
    """Server-derived readiness state (doc 14 §4).

    Only the three terminal report states are PERSISTED on a report row:
    ``not_ready`` / ``ready_with_warnings`` / ``ready``. ``stale`` and
    ``superseded`` are COMPUTED at read time by comparing the report's pinned
    fingerprint against the composition's current fingerprint — they are never
    stored (currentness is always recomputed, doc 14 §12.2 Trash rule).
    ``not_checked`` / ``checking`` are transient UI-only states with no report.
    """

    NOT_CHECKED = "not_checked"
    CHECKING = "checking"
    NOT_READY = "not_ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    READY = "ready"
    STALE = "stale"
    SUPERSEDED = "superseded"


class ReadinessScope(StrEnum):
    """Which validator layer produced an issue (doc 14 §9.2 fixed check order)."""

    COMPOSITION = "composition"
    LIFECYCLE = "lifecycle"
    STRATEGY = "strategy"
    MARKET_DATA = "market_data"
    EXTERNAL_OBJECT = "external_object"
    PORTFOLIO_ALLOCATION = "portfolio_allocation"


class ReadinessIssueCode(StrEnum):
    """Stable machine-readable issue codes (doc 14 §6.1, §9.2, §11, §15).

    A code is part of the immutable report contract — never renamed once emitted.
    """

    # Composition / items (§9.2, RC-01)
    COMPOSITION_EMPTY = "COMPOSITION_EMPTY"
    DUPLICATE_ENABLED_ITEM = "DUPLICATE_ENABLED_ITEM"
    NON_CANONICAL_ITEM_KIND = "NON_CANONICAL_ITEM_KIND"

    # Authorization / lifecycle (§9.2, RC-16)
    ITEM_UNAVAILABLE = "ITEM_UNAVAILABLE"

    # Strategy configuration (§5.1, §9.2, RC-05/RC-06)
    STRATEGY_CONFIG_INVALID = "STRATEGY_CONFIG_INVALID"
    STRATEGY_NO_ENTRY_LOGIC = "STRATEGY_NO_ENTRY_LOGIC"
    CONDITION_PACKAGE_REQUIRED = "CONDITION_PACKAGE_REQUIRED"
    STRATEGY_NO_EXIT_OR_STOP = "STRATEGY_NO_EXIT_OR_STOP"
    STRATEGY_SIZING_UNSUPPORTED = "STRATEGY_SIZING_UNSUPPORTED"
    STRATEGY_EXECUTION_TIMING_UNSUPPORTED = "STRATEGY_EXECUTION_TIMING_UNSUPPORTED"
    STRATEGY_ORDER_TYPE_UNSUPPORTED = "STRATEGY_ORDER_TYPE_UNSUPPORTED"
    STRATEGY_PARTIAL_CLOSE_UNSUPPORTED = "STRATEGY_PARTIAL_CLOSE_UNSUPPORTED"
    STRATEGY_SCALING_UNSUPPORTED = "STRATEGY_SCALING_UNSUPPORTED"
    STRATEGY_RESTRICTIONS_UNSUPPORTED = "STRATEGY_RESTRICTIONS_UNSUPPORTED"
    STRATEGY_CONFLICT_HANDLING_UNSUPPORTED = "STRATEGY_CONFLICT_HANDLING_UNSUPPORTED"
    STRATEGY_INDICATOR_UNRESOLVED = "STRATEGY_INDICATOR_UNRESOLVED"
    # F-08: a pinned Logic-Based Stop Block dependency does not resolve to a computable
    # stop signal — blocks RUN (the worker also fails closed on plan.unresolved).
    STRATEGY_LOGIC_STOP_UNRESOLVED = "STRATEGY_LOGIC_STOP_UNRESOLVED"
    EXECUTION_ASSUMPTIONS_DEFAULT = "EXECUTION_ASSUMPTIONS_DEFAULT"

    # Market data (§9.2, §11 approved-only gate)
    MARKET_DATASET_NOT_APPROVED = "MARKET_DATASET_NOT_APPROVED"

    # External working objects — Trading Signal / Trade Log (§5.1, §9.2, RC-07/RC-08)
    EXTERNAL_IMPORT_UNRESOLVED = "EXTERNAL_IMPORT_UNRESOLVED"
    EXTERNAL_IMPORT_INVALID = "EXTERNAL_IMPORT_INVALID"
    TRADE_LOG_CHRONOLOGY_INVALID = "TRADE_LOG_CHRONOLOGY_INVALID"
    MIXED_SYMBOL_SCOPE = "MIXED_SYMBOL_SCOPE"
    # GAP-16 (Master §8.1): an external import's canonical instrument must match the
    # strategy's — a spot import under a perpetual strategy is a Ready blocker.
    INSTRUMENT_SCOPE_MISMATCH = "INSTRUMENT_SCOPE_MISMATCH"
    OHLCV_FALLBACK_MARKET_DATA_MISSING = "OHLCV_FALLBACK_MARKET_DATA_MISSING"

    # Capital / allocation (§5.1, §9.2, RC-03/RC-04)
    INDEPENDENT_CAPITAL_REQUIRED = "INDEPENDENT_CAPITAL_REQUIRED"
    ALLOCATION_CAPITAL_INVALID = "ALLOCATION_CAPITAL_INVALID"
    ALLOCATION_TOTAL_EXCEEDS_100 = "ALLOCATION_TOTAL_EXCEEDS_100"
    ALLOCATION_ITEM_UNAVAILABLE = "ALLOCATION_ITEM_UNAVAILABLE"
    ALLOCATION_UNALLOCATED_CASH = "ALLOCATION_UNALLOCATED_CASH"
    # An item settles in a currency other than the Base Currency with no approved
    # pinned FX conversion dataset (doc 13 §5.1/§6.2 surfaced through Ready Check).
    ALLOCATION_FX_DEPENDENCY = "ALLOCATION_FX_DEPENDENCY"
    ALLOCATION_ISSUE = "ALLOCATION_ISSUE"


__all__ = [
    "ReadinessIssueCode",
    "ReadinessScope",
    "ReadinessSeverity",
    "ReadinessState",
]
