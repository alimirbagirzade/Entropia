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
    # O-01: doc 14 §9.2 lists Research Data as its own validator layer, between
    # Market Data and External working objects. Stored as a plain string (the
    # ``readiness_issue.scope`` column is a CHECK-free varchar), so a new member
    # needs no migration.
    RESEARCH_DATA = "research_data"
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
    STRATEGY_SIZING_SEMANTICS_UNCONFIRMED = "STRATEGY_SIZING_SEMANTICS_UNCONFIRMED"
    STRATEGY_EXECUTION_TIMING_UNSUPPORTED = "STRATEGY_EXECUTION_TIMING_UNSUPPORTED"
    STRATEGY_ORDER_TYPE_UNSUPPORTED = "STRATEGY_ORDER_TYPE_UNSUPPORTED"
    STRATEGY_PARTIAL_CLOSE_UNSUPPORTED = "STRATEGY_PARTIAL_CLOSE_UNSUPPORTED"
    STRATEGY_SCALING_UNSUPPORTED = "STRATEGY_SCALING_UNSUPPORTED"
    STRATEGY_RESTRICTIONS_UNSUPPORTED = "STRATEGY_RESTRICTIONS_UNSUPPORTED"
    STRATEGY_CONFLICT_HANDLING_UNSUPPORTED = "STRATEGY_CONFLICT_HANDLING_UNSUPPORTED"
    # F-07f: an unsupported leverage configuration (cross-margin, or a non-positive saved
    # multiplier) — blocks RUN (the engine also fails closed and opens no position).
    STRATEGY_LEVERAGE_UNSUPPORTED = "STRATEGY_LEVERAGE_UNSUPPORTED"
    # F-07g: an unsupported signal-strength adjustment mode (trend-/divergence-adjusted —
    # the saved schema carries no condition refs / multiplier / band config to execute
    # them) — blocks RUN (the engine also fails closed and opens no position).
    STRATEGY_SIGNAL_STRENGTH_UNSUPPORTED = "STRATEGY_SIGNAL_STRENGTH_UNSUPPORTED"
    # F-05: the strategy selects an option the machine-readable capability matrix
    # (domain/backtest/capabilities.py) marks ``future_dev`` — it does not execute in this
    # build at all. Blocks RUN with a "Not available in this build" message naming every
    # offending option and its dependency (the engine also fails closed and opens no
    # position). This is the MATRIX-driven blocker: it enumerates per option VALUE, so it
    # catches options no per-domain predicate was gating — notably
    # ``data.costs.slippage_mode = 'historical_slippage_if_available'``, which previously ran
    # as a silent zero-slippage backtest.
    STRATEGY_CAPABILITY_NOT_IN_BUILD = "STRATEGY_CAPABILITY_NOT_IN_BUILD"
    STRATEGY_INDICATOR_UNRESOLVED = "STRATEGY_INDICATOR_UNRESOLVED"
    # F-08: a pinned Logic-Based Stop Block dependency does not resolve to a computable
    # stop signal — blocks RUN (the worker also fails closed on plan.unresolved).
    STRATEGY_LOGIC_STOP_UNRESOLVED = "STRATEGY_LOGIC_STOP_UNRESOLVED"
    EXECUTION_ASSUMPTIONS_DEFAULT = "EXECUTION_ASSUMPTIONS_DEFAULT"

    # Market data (§9.2, §11 approved-only gate)
    MARKET_DATASET_NOT_APPROVED = "MARKET_DATASET_NOT_APPROVED"
    # F-07i: 'Use Tick Data = Yes' (intrabar_policy.tick_policy == 'require') needs an
    # approved tick/trade dataset for the strategy's instrument (Master Ref §6.4). When
    # none is available, Ready Check blocks RUN rather than silently resolving the
    # intrabar-sensitive execution over OHLCV (Master Ref §11.2 / line ~3558).
    TICK_DATA_UNAVAILABLE = "TICK_DATA_UNAVAILABLE"

    # Research Data (§9.2 "Research Data" validator row) — O-01.
    # These five codes are taken VERBATIM from the doc 12 §10 taxonomy so the Ready
    # Check finding and the Research Data page speak the same vocabulary about the
    # same defect; they are only ever emitted under ``ReadinessScope.RESEARCH_DATA``.
    # ``RESEARCH_COVERAGE_LIMITED`` is readiness-only: doc 12 §10 has no code for the
    # doc 14 §9.2 Research *warning* row ("Limited coverage or low fill rate"), so it
    # is named in this catalog's own namespace.
    USAGE_SCOPE_FORBIDDEN = "USAGE_SCOPE_FORBIDDEN"
    TIME_POLICY_INVALID = "TIME_POLICY_INVALID"
    DEPENDENCY_BLOCKED = "DEPENDENCY_BLOCKED"
    INSTRUMENT_MAPPING_INVALID = "INSTRUMENT_MAPPING_INVALID"
    LIFECYCLE_BLOCKED = "LIFECYCLE_BLOCKED"
    RESEARCH_COVERAGE_LIMITED = "RESEARCH_COVERAGE_LIMITED"

    # External working objects — Trading Signal / Trade Log (§5.1, §9.2, RC-07/RC-08)
    EXTERNAL_IMPORT_UNRESOLVED = "EXTERNAL_IMPORT_UNRESOLVED"
    EXTERNAL_IMPORT_INVALID = "EXTERNAL_IMPORT_INVALID"
    TRADE_LOG_CHRONOLOGY_INVALID = "TRADE_LOG_CHRONOLOGY_INVALID"
    MIXED_SYMBOL_SCOPE = "MIXED_SYMBOL_SCOPE"
    # GAP-16 (Master §8.1): an external import's canonical instrument must match the
    # strategy's — a spot import under a perpetual strategy is a Ready blocker.
    INSTRUMENT_SCOPE_MISMATCH = "INSTRUMENT_SCOPE_MISMATCH"
    # Trade Log's OHLCV price fallback with no approved Market Data pin (doc 05 §5.3).
    OHLCV_FALLBACK_MARKET_DATA_MISSING = "OHLCV_FALLBACK_MARKET_DATA_MISSING"
    # K-08: the Trading Signal TWIN of the code above. Doc 04 §5 Price Source row —
    # "Fallback options require compatible approved Market Data at Ready Check" —
    # applies to a Trading Signal exactly as doc 05 §5.3 applies to a Trade Log, but
    # each page's own §-taxonomy names the defect (the K-07 adjudication): doc 04 §11
    # Dependency row says ``MARKET_DATA_DEPENDENCY_BLOCKED``, so a Trading Signal emits
    # THAT while a Trade Log keeps ``OHLCV_FALLBACK_MARKET_DATA_MISSING``. Same defect,
    # two page vocabularies; renaming either would break the page already speaking it.
    MARKET_DATA_DEPENDENCY_BLOCKED = "MARKET_DATA_DEPENDENCY_BLOCKED"
    # Doc 04 §5.2 "Price Source = OHLCV Intrabar If Available": the pinned approved
    # market dataset must actually CARRY sub-bar detail. A bar-only (``ohlcv``) or
    # spread dataset cannot, and resolving intrabar execution over it would silently
    # imitate unavailable detail — so it blocks RUN. Distinct from
    # ``TICK_DATA_UNAVAILABLE``, which is the STRATEGY-side 'Use Tick Data = Yes'
    # requirement (Master Ref §6.4) resolved by instrument rather than by pinned ref.
    INTRABAR_DATA_UNAVAILABLE = "INTRABAR_DATA_UNAVAILABLE"
    # Doc 04 §5.2 "OHLCV Use = Use for price context and validation": the declared
    # context must come from somewhere. ``signal_events_with_source_ohlcv`` supplies it
    # from the source file; ``signal_events_with_market_context`` supplies NO source
    # OHLCV, so an approved Market Data pin is the only remaining provider — without
    # one the validation the user explicitly asked for cannot run at all.
    OHLCV_CONTEXT_REQUIRED = "OHLCV_CONTEXT_REQUIRED"

    # Capital / allocation (§5.1, §9.2, RC-03/RC-04)
    INDEPENDENT_CAPITAL_REQUIRED = "INDEPENDENT_CAPITAL_REQUIRED"
    ALLOCATION_CAPITAL_INVALID = "ALLOCATION_CAPITAL_INVALID"
    ALLOCATION_TOTAL_EXCEEDS_100 = "ALLOCATION_TOTAL_EXCEEDS_100"
    ALLOCATION_ITEM_UNAVAILABLE = "ALLOCATION_ITEM_UNAVAILABLE"
    ALLOCATION_UNALLOCATED_CASH = "ALLOCATION_UNALLOCATED_CASH"
    # An item settles in a currency other than the Base Currency with no approved
    # pinned FX conversion dataset (doc 13 §5.1/§6.2 surfaced through Ready Check).
    ALLOCATION_FX_DEPENDENCY = "ALLOCATION_FX_DEPENDENCY"
    # Containment (ADIM 3): the composition asks for SHARED capital allocation, which
    # does not execute in this build — the engine replays each item independently and
    # folds the finished runs in pin order, so there is no per-timestamp portfolio
    # valuation snapshot and the composite equity curve is not time-ordered (doc 13
    # §8.3, §8.4, §13, §14 test 11). Blocks RUN with the doc 14 §9.1 remediation, the
    # twin of the strategy-side ``STRATEGY_CAPABILITY_NOT_IN_BUILD``. Independent
    # capital (doc 13 §1.1) is unaffected. Status, texts and the removal condition
    # live in ``domain/allocation/capability.py``.
    ALLOCATION_SHARED_MODE_NOT_IN_BUILD = "ALLOCATION_SHARED_MODE_NOT_IN_BUILD"
    # ADR 0002 §13.1 OD-6(a): a SHARED plan whose active entries include a kind the
    # engine runs no simulation for (Trading Signal / Trade Log — F-04 hands them
    # ``output=None``). Their share would be withheld from the items that CAN trade
    # while doing nothing itself. Blocks RUN at admission; independent mode is
    # unaffected, and the item may still feed a Strategy as a data input. Texts and
    # the predicate live in ``domain/allocation/shared_mode_admission.py``.
    ALLOCATION_SHARED_MODE_NON_EXECUTING_ITEM = "ALLOCATION_SHARED_MODE_NON_EXECUTING_ITEM"
    # ADR 0002 §13.1 OD-1(a): a SHARED run whose pinned market datasets declare
    # DIFFERENT ``record_time_basis`` values. The engine keeps one decision-time
    # convention and never branches on that field (A-1), so a shared clock would fold
    # two differently-based axes together as if identical. Blocks RUN at admission;
    # independent mode replays each item on its own axis and is unaffected.
    ALLOCATION_SHARED_MODE_MIXED_RECORD_TIME_BASIS = (
        "ALLOCATION_SHARED_MODE_MIXED_RECORD_TIME_BASIS"
    )
    ALLOCATION_ISSUE = "ALLOCATION_ISSUE"


__all__ = [
    "ReadinessIssueCode",
    "ReadinessScope",
    "ReadinessSeverity",
    "ReadinessState",
]
