"""Pure, deterministic Ready Check validators + state derivation (Stage 4b,
doc 14 §9.2 "Validator architecture and fixed check order").

These are separate pure domain services (doc 14 §9.2 "not one large frontend
handler"). Nothing here touches the DB, the clock or the request. The command
orchestrator resolves inputs (snapshot items, pinned payloads, external import
batch state, allocation config) and calls :func:`evaluate_readiness`; it owns
aggregation, report persistence and audit.

Fixed check order (doc 14 §9.2): composition -> lifecycle -> strategy ->
market data -> research data -> external working objects -> portfolio allocation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from entropia.domain.allocation.enums import AllocationIssueCode as AllocCode
from entropia.domain.allocation.enums import AllocationIssueSeverity as AllocSev
from entropia.domain.allocation.rules import AllocationIssue
from entropia.domain.backtest.capabilities import future_dev_selections
from entropia.domain.backtest.engine import (
    conflict_handling_is_modelled,
    partial_close_is_modelled,
    restrictions_are_modelled,
    scaling_is_modelled,
    signal_strength_is_modelled,
)
from entropia.domain.backtest.execution.fills import (
    execution_timing_is_modelled,
    order_execution_is_modelled,
)
from entropia.domain.backtest.execution.sizing import (
    leverage_is_modelled,
    sizing_is_modelled,
)
from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.readiness.enums import (
    ReadinessIssueCode as Code,
)
from entropia.domain.readiness.enums import (
    ReadinessScope as Scope,
)
from entropia.domain.readiness.enums import (
    ReadinessSeverity as Sev,
)
from entropia.domain.readiness.enums import (
    ReadinessState,
)
from entropia.domain.readiness.issues import (
    ReadinessIssue,
    ReadinessItemInput,
    ResearchSourceState,
)
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    ResearchRevisionState,
    UsageScope,
)
from entropia.domain.research_data.time_policy import instrument_mapping_is_valid
from entropia.domain.strategy.config import StrategyConfig
from entropia.domain.trade_log.compiler import validate_semantics as validate_trade_log_semantics
from entropia.domain.trade_log.config import TradeLogConfig
from entropia.domain.trade_log.enums import PriceSourceMode as TradeLogPriceSource
from entropia.domain.trade_log.records import (
    REASON_EXIT_BEFORE_ENTRY,
    REASON_INSTRUMENT_MISMATCH,
)
from entropia.domain.trading_signal.compiler import (
    validate_semantics as validate_signal_semantics,
)
from entropia.domain.trading_signal.config import TradingSignalConfig
from entropia.domain.trading_signal.enums import DataQualityMode as SignalDataQualityMode
from entropia.domain.trading_signal.enums import OhlcvUseMode as SignalOhlcvUseMode

_CANONICAL_KINDS = frozenset(
    {
        MainboardItemKind.STRATEGY,
        MainboardItemKind.TRADING_SIGNAL,
        MainboardItemKind.TRADE_LOG,
    }
)
_TRIGGERS_REQUIRING_CONDITION = frozenset(
    {"indicator_native_trigger_plus_condition", "indicator_output_plus_condition"}
)
# The price sources that cannot be served by the import alone and therefore need an
# approved Market Data revision behind them. Held as plain STRINGS because both
# external twins declare the identical two values under their own enum
# (``trade_log.enums.PriceSourceMode`` / ``trading_signal.enums.PriceSourceMode``) —
# one membership test then judges either config without depending on cross-enum
# identity (K-08).
_OHLCV_FALLBACK_SOURCES = frozenset(
    {
        str(TradeLogPriceSource.OHLCV_CLOSE_IF_NEEDED),
        str(TradeLogPriceSource.OHLCV_INTRABAR_IF_AVAILABLE),
    }
)

# O-01: the ONLY usage scope doc 12 §9.3 lets into a Backtest Evidence Bundle.
# ``agent_research_only`` and ``feature_input_only`` are both "Forbidden" / "only via
# an approved feature definition" in that matrix — neither is raw backtest input.
_BACKTEST_ELIGIBLE_USAGE_SCOPE = str(UsageScope.RESEARCH_BACKTEST)
# Only an APPROVED revision feeds a bundle (doc 12 §8.2; ``verified`` is NOT enough).
_BACKTEST_ELIGIBLE_REVISION_STATE = str(ResearchRevisionState.APPROVED)
# ``fixed_delay`` is the one policy that additionally needs a positive bounded delay
# (doc 12 §5.2); every other policy derives availability without one.
_FIXED_DELAY_POLICY = str(AvailableTimePolicy.FIXED_DELAY)
# The persisted ``validation_status`` value that means "analysis recorded a
# non-blocking quality finding" (limited coverage / low fill rate / duplicate density).
_VALIDATION_WARNING = str(ValidationStatus.WARNING)

# Allocation blocker codes that resolve to a specific readiness code; anything
# else maps to the generic ALLOCATION_ISSUE (still carrying the original message).
_ALLOC_CODE_MAP: dict[str, Code] = {
    str(AllocCode.INITIAL_CAPITAL_INVALID): Code.ALLOCATION_CAPITAL_INVALID,
    str(AllocCode.BASE_CURRENCY_INVALID): Code.ALLOCATION_CAPITAL_INVALID,
    str(AllocCode.TOTAL_ALLOCATION_EXCEEDS_100): Code.ALLOCATION_TOTAL_EXCEEDS_100,
    str(AllocCode.TOTAL_ALLOCATION_UNDER_100): Code.ALLOCATION_UNALLOCATED_CASH,
    str(AllocCode.ITEM_UNAVAILABLE): Code.ALLOCATION_ITEM_UNAVAILABLE,
    str(AllocCode.FX_DEPENDENCY_MISSING): Code.ALLOCATION_FX_DEPENDENCY,
}


@dataclass(frozen=True, slots=True)
class ReadinessEvaluation:
    """Aggregate result of a Ready Check pass (doc 14 §9.1 report summary)."""

    issues: tuple[ReadinessIssue, ...]
    state: ReadinessState
    blocker_count: int
    warning_count: int

    def as_summary(self) -> dict[str, int | str]:
        return {
            "state": str(self.state),
            "blocker_count": self.blocker_count,
            "warning_count": self.warning_count,
        }


def evaluate_readiness(
    items: Sequence[ReadinessItemInput],
    *,
    allocation_enabled: bool,
    allocation_issues: Sequence[AllocationIssue],
    market_data_issues: Sequence[ReadinessIssue] = (),
    tick_data_issues: Sequence[ReadinessIssue] = (),
    signal_market_data_issues: Sequence[ReadinessIssue] = (),
    strategy_indicator_issues: Sequence[ReadinessIssue] = (),
    research_sources: Sequence[ResearchSourceState] = (),
) -> ReadinessEvaluation:
    """Aggregate all validator layers into an immutable evaluation (doc 14 §9.2).

    ``items`` are the ENABLED composition members (a disabled item never enters a
    snapshot). ``allocation_issues`` is the 4a ``validate_allocation`` output for
    the shared pool (empty in independent mode); it is mapped 1:1 here.
    ``strategy_indicator_issues`` are the F-06 upfront-RUN-gate blockers the command
    resolved from each strategy's pinned indicator plan (a DB read, like
    ``market_data_issues``) — an unresolved required dependency blocks RUN so the
    worker can never silently substitute the breakout proxy. ``tick_data_issues`` are
    the F-07i blockers the command resolved for strategies that demand tick data
    ('Use Tick Data' = Yes) but have no approved tick/trade dataset — also a DB read.
    ``signal_market_data_issues`` are the K-08 blockers the command resolved for a
    Trading Signal whose price policy DOES name an approved Market Data revision:
    whether that pin is still ACTIVE + APPROVED, and whether it can carry intrabar
    detail, are DB facts. The pure layer above only proves a reference was declared.
    ``research_sources`` are the O-01 resolved Research Data pins (one per research
    revision a strategy consumes); they are judged HERE by the pure
    ``validate_research_sources`` rather than arriving pre-judged, because the whole
    Research decision is expressible over the resolved row (doc 14 §9.2 Research row).
    """
    issues: list[ReadinessIssue] = []
    issues.extend(_composition_issues(items))
    issues.extend(_instrument_consistency_issues(items))
    for item in items:
        issues.extend(_item_issues(item, allocation_enabled=allocation_enabled))
    issues.extend(market_data_issues)
    issues.extend(tick_data_issues)
    issues.extend(signal_market_data_issues)
    issues.extend(strategy_indicator_issues)
    issues.extend(validate_research_sources(research_sources))
    issues.extend(_map_allocation_issues(allocation_issues))

    blockers = sum(1 for i in issues if i.severity == Sev.BLOCKER)
    warnings = sum(1 for i in issues if i.severity == Sev.WARNING)
    state = _derive_state(blockers, warnings)
    return ReadinessEvaluation(
        issues=tuple(issues),
        state=state,
        blocker_count=blockers,
        warning_count=warnings,
    )


def _derive_state(blocker_count: int, warning_count: int) -> ReadinessState:
    if blocker_count > 0:
        return ReadinessState.NOT_READY
    if warning_count > 0:
        return ReadinessState.READY_WITH_WARNINGS
    return ReadinessState.READY


def is_stale(report_fingerprint: str, current_fingerprint: str) -> bool:
    """A report is stale once the composition it was pinned to changed (doc 14 §4).

    A newer catalog revision that the draft does NOT pin never stales a report —
    the fingerprint is over the pinned revision ids only (RC-10, doc 14 §13).
    """
    return report_fingerprint != current_fingerprint


# --------------------------------------------------------------------------- #
# Composition / items (doc 14 §9.2, RC-01)                                     #
# --------------------------------------------------------------------------- #


def _composition_issues(items: Sequence[ReadinessItemInput]) -> list[ReadinessIssue]:
    issues: list[ReadinessIssue] = []
    available = [i for i in items if i.available]
    if not available:
        issues.append(
            ReadinessIssue(
                Code.COMPOSITION_EMPTY,
                Sev.BLOCKER,
                Scope.COMPOSITION,
                "No enabled Strategy, Trading Signal or Trade Log exists on the composition.",
                remediation="Add at least one enabled item, then re-run the check.",
                field_path="composition.items",
            )
        )

    seen: set[str] = set()
    duplicated: set[str] = set()
    for item in available:
        if item.root_id in seen and item.root_id not in duplicated:
            duplicated.add(item.root_id)
            issues.append(
                ReadinessIssue(
                    Code.DUPLICATE_ENABLED_ITEM,
                    Sev.BLOCKER,
                    Scope.COMPOSITION,
                    "The same working object is enabled more than once in this composition.",
                    remediation="Disable or remove the duplicate item; V1 allows one enabled "
                    "instance per working object.",
                    scope_id=item.item_id,
                )
            )
        seen.add(item.root_id)
    return issues


def _strategy_instrument_id(item: ReadinessItemInput) -> str:
    data = item.payload.get("data")
    raw = data.get("instrument_id") if isinstance(data, dict) else None
    return (raw or "").strip()


def _instrument_consistency_issues(
    items: Sequence[ReadinessItemInput],
) -> list[ReadinessIssue]:
    """Every external import's canonical instrument must match the strategy's (GAP-16).

    V1 compositions are single-instrument scope (doc 05 §5.1). Once ingest resolves
    the free-text scope to a canonical ``instrument_id`` (Master §8.1), a divergence
    between a strategy and its Trading Signal / Trade Log is a real mismatch, not a
    formatting difference: a spot import under a perpetual strategy is a Ready
    blocker. The check anchors on a single declared strategy instrument; with none
    (external-only) or more than one, it yields to the other validator layers.
    """
    issues: list[ReadinessIssue] = []
    references = {
        _strategy_instrument_id(item)
        for item in items
        if item.available and item.kind == MainboardItemKind.STRATEGY
    }
    references.discard("")
    if len(references) != 1:
        return issues
    reference = next(iter(references))
    for item in items:
        if not item.available or item.external is None:
            continue
        declared = (item.external.instrument_id or "").strip()
        if declared and declared != reference:
            issues.append(
                ReadinessIssue(
                    Code.INSTRUMENT_SCOPE_MISMATCH,
                    Sev.BLOCKER,
                    Scope.EXTERNAL_OBJECT,
                    "This external import's instrument does not match the strategy's instrument.",
                    remediation="Re-import the external object under the strategy's instrument, or "
                    "pin a strategy for the same instrument.",
                    scope_id=item.item_id,
                )
            )
    return issues


# --------------------------------------------------------------------------- #
# Per-item dispatch (lifecycle -> strategy / external)                         #
# --------------------------------------------------------------------------- #


def _item_issues(item: ReadinessItemInput, *, allocation_enabled: bool) -> list[ReadinessIssue]:
    if not item.available:
        return [
            ReadinessIssue(
                Code.ITEM_UNAVAILABLE,
                Sev.BLOCKER,
                Scope.LIFECYCLE,
                "A selected Mainboard item is soft-deleted, inaccessible, or no longer usable.",
                remediation="Restore or replace the item's work object, then re-run the check.",
                scope_id=item.item_id,
            )
        ]
    if item.kind not in _CANONICAL_KINDS:
        return [
            ReadinessIssue(
                Code.NON_CANONICAL_ITEM_KIND,
                Sev.BLOCKER,
                Scope.COMPOSITION,
                f"Item kind {item.kind!s} is not a canonical composition kind.",
                scope_id=item.item_id,
            )
        ]
    if item.kind == MainboardItemKind.STRATEGY:
        return _strategy_issues(item, allocation_enabled=allocation_enabled)
    return _external_issues(item, allocation_enabled=allocation_enabled)


# --------------------------------------------------------------------------- #
# Strategy configuration (doc 14 §5.1, §9.2, RC-05/RC-06)                      #
# --------------------------------------------------------------------------- #


def _strategy_issues(item: ReadinessItemInput, *, allocation_enabled: bool) -> list[ReadinessIssue]:
    try:
        config = StrategyConfig(**item.payload)
    except PydanticValidationError as exc:
        return [
            ReadinessIssue(
                Code.STRATEGY_CONFIG_INVALID,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The pinned strategy revision does not resolve to a valid configuration.",
                remediation="Open the strategy and fix the reported fields, save a revision, "
                "then re-run the check.",
                field_path=_first_error_path(exc),
                scope_id=item.item_id,
            )
        ]

    issues: list[ReadinessIssue] = []
    entry = config.position_entry_logic
    enabled_entry_blocks = [b for b in entry.indicator_blocks if b.enabled]
    if not enabled_entry_blocks:
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_NO_ENTRY_LOGIC,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy has no enabled entry indicator block.",
                remediation="Enable at least one entry indicator block.",
                field_path="position_entry_logic.indicator_blocks",
                scope_id=item.item_id,
            )
        )

    # RC-05/RC-06: a Condition Package is required ONLY when the Trigger Source
    # demands it; a Native Trigger alone never requires one (doc 14 §5.1, §13).
    for block in enabled_entry_blocks:
        if block.trigger_source in _TRIGGERS_REQUIRING_CONDITION:
            enabled_conditions = [c for c in (block.condition_blocks or []) if c.enabled]
            if not enabled_conditions:
                issues.append(
                    ReadinessIssue(
                        Code.CONDITION_PACKAGE_REQUIRED,
                        Sev.BLOCKER,
                        Scope.STRATEGY,
                        f"Trigger source {block.trigger_source!r} requires at least one enabled "
                        "condition package.",
                        remediation="Add an enabled condition block to the indicator, or switch "
                        "to a native trigger.",
                        field_path=f"position_entry_logic.indicator_blocks.{block.block_id}."
                        "condition_blocks",
                        scope_id=item.item_id,
                    )
                )

    if not _has_exit_or_stop(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_NO_EXIT_OR_STOP,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy has neither exit logic nor an active stop.",
                remediation="Define exit logic or enable at least one protection stop.",
                field_path="position_exit_logic",
                scope_id=item.item_id,
            )
        )

    # F-05: the MATRIX-driven capability blocker. Every option the capability matrix
    # (domain/backtest/capabilities.py) marks ``future_dev`` does not execute in this build at
    # all, so selecting one must BLOCK RUN — the engine also fails closed and opens no
    # position. Its value is covering option values NO per-domain predicate gates: it is what
    # caught ``data.costs.slippage_mode = 'historical_slippage_if_available'``, which passed
    # all nine and then ran as a silent ZERO-slippage backtest. One issue per offending option
    # so the user sees every one at once instead of fixing them one run at a time.
    #
    # Placed ahead of the nine per-domain checks for READING order only — Ready Check collects
    # every issue, so an option covered by both (cross leverage, trend-adjusted strength, ...)
    # legitimately raises this blocker AND its specific one, and the user gets both remediations.
    # This is NOT the engine's precedence rule: ``_blocked_reason`` returns exactly ONE trace
    # value, so there the matrix reason is checked LAST and never overwrites the more specific
    # per-domain reason.
    for capability in future_dev_selections(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_CAPABILITY_NOT_IN_BUILD,
                Sev.BLOCKER,
                Scope.STRATEGY,
                f"Not available in this build: {capability.label!r} "
                f"({capability.field_path}) is not executed by the backtest engine and "
                "would open no position.",
                remediation=f"Choose a supported option. {capability.dependency}",
                field_path=capability.field_path,
                scope_id=item.item_id,
            )
        )

    # F-09: an unsupported / misconfigured position-sizing method must BLOCK RUN — the
    # engine fails closed (opens no position) for it, so a run would silently produce
    # nothing. Surface it as a blocker with a concrete remediation instead. Shares the
    # single ``sizing_is_modelled`` predicate with the engine so the two never diverge.
    if not sizing_is_modelled(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_SIZING_UNSUPPORTED,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy's position sizing method is not supported by the backtest "
                "engine and would open no position.",
                remediation="Use an explicit base position size, risk-based sizing with a "
                "stop distance, or a valid Kelly-criterion formula (win_probability in "
                "(0,1) and a positive payoff_ratio).",
                field_path="position_sizing",
                scope_id=item.item_id,
            )
        )

    # F-07f: an unsupported leverage configuration must BLOCK RUN — the engine fails
    # closed (opens no position) for it. 'No Leverage' and 'Isolated' with a positive
    # saved multiplier are modelled; 'Cross' needs a portfolio-level risk model the
    # single-position bar-replay engine does not implement. Shares the single
    # ``leverage_is_modelled`` predicate with the engine so the two never diverge.
    if not leverage_is_modelled(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_LEVERAGE_UNSUPPORTED,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy's leverage configuration is not supported by the backtest "
                "engine and would open no position.",
                remediation="Use 'No Leverage' or 'Isolated' margin mode with a positive "
                "leverage multiplier. 'Cross' margin mode is not yet supported.",
                field_path="position_sizing",
                scope_id=item.item_id,
            )
        )

    # F-07g: an unsupported signal-strength adjustment must BLOCK RUN — the engine fails
    # closed (opens no position) for it. 'no_adjustment' is inert (1x) and
    # 'volatility_adjusted' is executed as a deterministic look-back volatility multiplier;
    # 'trend_adjusted' / 'divergence_adjusted' need signal-source config (condition-package
    # refs, an adjustment formula and band caps, Master Ref §10.3) the saved schema does
    # not carry. Shares the single ``signal_strength_is_modelled`` predicate with the
    # engine so the two never diverge.
    if not signal_strength_is_modelled(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_SIGNAL_STRENGTH_UNSUPPORTED,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy's signal-strength adjustment mode is not supported by the "
                "backtest engine and would open no position.",
                remediation="Use 'No Adjustment' or 'Volatility Adjusted' signal-strength "
                "sizing. Trend- and divergence-adjusted modes are not yet supported.",
                field_path="position_sizing",
                scope_id=item.item_id,
            )
        )

    # F-07a/F-07i (C): an unsupported entry/exit EXECUTION TIMING must BLOCK RUN — the
    # engine fails closed (opens no position) for it, so a run would silently produce
    # nothing. The intrabar-touch and limit/stop-limit simulation modes are executed
    # over the REAL intrabar print path and therefore require 'Use Tick Data' = Yes
    # (which chains the (i)a tick-availability blocker + the manifest tick pin); over
    # plain OHLCV they cannot be faithfully reproduced (doc 02: "cannot silently
    # imitate unavailable detail"). Shares the single ``execution_timing_is_modelled``
    # predicate with the engine so Ready Check and the worker never diverge.
    if not execution_timing_is_modelled(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_EXECUTION_TIMING_UNSUPPORTED,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy's entry or exit execution timing is not supported by the "
                "backtest engine and would open no position.",
                remediation="Use Current Candle Close, Next Candle Open, Next Candle Close, "
                "or Market Fill Simulation for both entry and exit execution. Intrabar Touch "
                "and Limit/Stop-Limit simulation run over tick data only: set 'Use Tick "
                "Data' to Yes (an approved tick/trade dataset is then required); Limit Fill "
                "Simulation also needs a Limit or Stop-Limit order type.",
                field_path="data.execution",
                scope_id=item.item_id,
            )
        )

    # F-07b/F-07h/F-07i (C): an unsupported ORDER VARIANT must BLOCK RUN — the engine
    # fails closed (opens no position) for it. Stop / Stop-Limit orders ARE modelled
    # (F-07h) when the saved schema carries a valid stop trigger (activation rule +
    # offset where required). Partial-fill policies other than "not allowed" ARE
    # modelled (F-07i C) when the strategy demands tick data — the filled fraction is
    # computed from the print path's trade sizes; without that demand they remain
    # blocked. A best-bid/ask price rule remains blocked regardless: it needs an
    # observed bid/ask QUOTE series (Master Ref §2.3 Spread/Execution dataset), which
    # the tick/trade print path does not carry. Shares the single
    # ``order_execution_is_modelled`` predicate with the engine so the two never diverge.
    if not order_execution_is_modelled(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_ORDER_TYPE_UNSUPPORTED,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy's order type is not supported by the backtest engine and "
                "would open no position.",
                remediation="Use a Market Order or Simulation Only; a Limit Order with an "
                "entry-signal / signal±offset price rule; or a Stop / Stop-Limit Order "
                "with an entry-signal / signal±offset trigger (a Stop-Limit also needs a "
                "supported limit rule). A partial-fill policy other than 'not allowed' "
                "requires 'Use Tick Data' = Yes. A missing stop trigger and the "
                "best-bid/ask price rule (needs a bid/ask quote series) are not supported.",
                field_path="data.order_config",
                scope_id=item.item_id,
            )
        )

    # F-07c: a partial close (close_percentage < 100) with an unmodelled aftermath (trailing /
    # lock-in, deferred to slice f) must BLOCK RUN — the engine fails closed (opens no position)
    # for it. Shares the single ``partial_close_is_modelled`` predicate with the engine so the
    # two never diverge. A full close (close_percentage == 100) or a move-stop / close-all
    # aftermath is modelled and raises nothing.
    if not partial_close_is_modelled(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_PARTIAL_CLOSE_UNSUPPORTED,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy's partial-close aftermath is not supported by the backtest "
                "engine and would open no position.",
                remediation="For a partial close (close percentage under 100), use the "
                "'move stop to entry' or 'close all' aftermath. Trailing-stop and lock-in-"
                "profit aftermaths are not yet supported.",
                field_path="position_exit_logic",
                scope_id=item.item_id,
            )
        )

    # F-07d / S5c: an unsupported SCALING configuration must BLOCK RUN — the engine fails
    # closed (opens no position) for it. Both methods are now modelled: Price-Distance with
    # a positive add size, and Logic-Based with resolvable blocks plus a DECLARED depth
    # (S5c) — each on the strategy's own timeframe, under either the same_strategy or the
    # custom_sequence per-layer timeframe structure. The increasing_by_layer mode (doc 02
    # §5.7 specifies no step increment), a flat ``timeframe`` override, an unbounded logic
    # ladder, a missing/non-positive add size and a negative/non-positive cap are deferred
    # or misconfigured. Shares the single ``scaling_is_modelled`` predicate with the engine
    # so the two never diverge. Disabled (or absent) scaling raises nothing.
    if not scaling_is_modelled(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_SCALING_UNSUPPORTED,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy's scaling (additional layer) configuration is not supported "
                "by the backtest engine and would open no position.",
                remediation="Use Price-Distance Based or Logic-Based scaling on the "
                "strategy timeframe with a positive add size, or disable scaling. "
                "Logic-Based scaling also needs a declared depth — set Max Additional "
                "Layers or a Custom Timeframe Sequence. The scaling timeframe structure "
                "may be 'Same as Strategy Timeframe' or a Custom Timeframe Sequence; "
                "'Increasing Timeframe by Layer' is not yet supported.",
                field_path="scaling_logic",
                scope_id=item.item_id,
            )
        )

    # F-07e: an unsupported Restrictions/Filters section must BLOCK RUN — the engine fails
    # closed (opens no position) for it. Date-blackout / max-daily-loss / consecutive-loss
    # filters with a parseable config and a block-entries action are modelled; volatility /
    # spread / volume / correlation filters (each needs a data series OHLCV cannot honestly
    # supply), another action (reduce / close / disable / warn) and a malformed config are
    # not. Shares the single ``restrictions_are_modelled`` predicate with the engine so the
    # two never diverge. Disabled filters (or an empty list) raise nothing.
    if not restrictions_are_modelled(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_RESTRICTIONS_UNSUPPORTED,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy's restrictions / filters are not supported by the backtest "
                "engine and would open no position.",
                remediation="Use Date Blackout Windows (date_ranges), Max Daily Loss "
                "(limit_percent) or a Consecutive Loss Filter (max_losses) with the "
                "block-entries action, or disable the filter. Volatility, spread, volume "
                "and correlation filters are not yet supported.",
                field_path="restrictions_filters",
                scope_id=item.item_id,
            )
        )

    # F-07e: an unsupported conflict/position-handling combination must BLOCK RUN — the
    # engine fails closed (opens no position) for it. A true hedge (allow_hedge with
    # exit-on-opposite off) needs two concurrent opposite positions the single-position
    # bar-replay cannot honestly simulate. Shares the single
    # ``conflict_handling_is_modelled`` predicate with the engine so the two never diverge.
    if not conflict_handling_is_modelled(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_CONFLICT_HANDLING_UNSUPPORTED,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy's opposite-direction hedge policy is not supported by the "
                "backtest engine and would open no position.",
                remediation="Enable 'exit on opposite signal', or set the opposite-"
                "direction policy to 'close existing' or 'ignore'. Holding simultaneous "
                "long and short positions (hedge mode) is not yet supported.",
                field_path="conflict_position_handling",
                scope_id=item.item_id,
            )
        )

    costs = config.data.costs
    if costs.commission is None and costs.spread is None:
        issues.append(
            ReadinessIssue(
                Code.EXECUTION_ASSUMPTIONS_DEFAULT,
                Sev.WARNING,
                Scope.STRATEGY,
                "Commission and spread assumptions are unset; review execution realism "
                "before running.",
                field_path="data.costs",
                scope_id=item.item_id,
            )
        )
    return issues


def _has_exit_or_stop(config: StrategyConfig) -> bool:
    exit_logic = config.position_exit_logic
    # Exit logic exists when at least one ENABLED exit indicator block is present;
    # the signal_block is only the aggregation rule and disabled blocks are not
    # active engine rules (doc 14 §5.1 exit/protection).
    has_exit = any(block.enabled for block in (exit_logic.indicator_blocks or []))
    stops = config.protection_stop_logic
    has_price_stop = stops is not None and any(
        s is not None and getattr(s, "enabled", False)
        for s in (stops.percentage_stop, stops.trailing_stop, stops.absolute_stop)
    )
    # F-08: an enabled Logic-Based Stop Block is a real protection rule too.
    has_logic_stop = stops is not None and any(
        block.enabled for block in (stops.logic_blocks or [])
    )
    return has_exit or has_price_stop or has_logic_stop


# --------------------------------------------------------------------------- #
# Research Data (doc 14 §9.2 "Research Data" row; doc 12 §9.2/§9.3/§10) — O-01   #
# --------------------------------------------------------------------------- #


def validate_research_sources(
    sources: Sequence[ResearchSourceState],
) -> list[ReadinessIssue]:
    """Judge every Research Data revision the composition pins (doc 14 §9.2).

    Doc 12 §9.2 requires BOTH Ready Check and the Backtest worker to validate the
    evidence bundle server-side. The worker gate (``queries/funding.py`` ->
    ``FundingSourceInvalid``) is deliberately left in place: it is the last line of
    defence for a revision whose eligibility changed between admission and execution.
    This layer is the UPFRONT gate, so an ineligible pin surfaces as a Ready Check
    BLOCKER (and a 422 ``READINESS_BLOCKED`` on RUN) instead of a mid-run crash.

    Blockers (doc 14 §9.2 Research row, in evaluation order):

    * ``LIFECYCLE_BLOCKED`` — the pinned revision does not resolve, its root is not
      ACTIVE, or the revision is not APPROVED. Reported ALONE: nothing further can be
      trusted about a revision we could not resolve or that is not eligible at all,
      and three findings for one broken pin would be noise, not detail.
    * ``USAGE_SCOPE_FORBIDDEN`` — the usage scope excludes backtest consumption
      (doc 12 §9.3: ``agent_research_only`` is Forbidden in a Backtest Evidence
      Bundle; ``feature_input_only`` only reaches a strategy through an approved
      versioned feature definition, never as a raw pin).
    * ``TIME_POLICY_INVALID`` — available time is undefined: no available-time policy,
      or ``fixed_delay`` without a positive bounded delay (doc 12 §5.2, §8.4). Without
      it the engine cannot prove ``available_at <= t`` and would leak future values.
    * ``DEPENDENCY_BLOCKED`` — the revision declares a link to a market dataset
      revision OTHER than the one the strategy pins ("exact Market Data compatibility
      missing"). A revision declaring NO link is compatible: it is consumed by pinned
      revision id, not resolved through a market link.
    * ``INSTRUMENT_MAPPING_INVALID`` — the link/mapping pair is incoherent (reusing
      ``instrument_mapping_is_valid``, the same predicate the engine's availability
      gate depends on, so the two can never disagree).

    Warning:

    * ``RESEARCH_COVERAGE_LIMITED`` — the revision's recorded analysis outcome is
      WARNING (doc 14 §9.2 "Limited coverage or low fill rate"). Honest boundary: the
      analysis records per-dataset quality (null density, duplicate density, coverage),
      NOT per-requested-interval fill rate — no such metric is computed today — so this
      warns that the pinned dataset carries a non-blocking quality finding and points
      at its quality report, rather than claiming an interval-scoped measurement.
    """
    issues: list[ReadinessIssue] = []
    for source in sources:
        lifecycle = _research_lifecycle_issue(source)
        if lifecycle is not None:
            issues.append(lifecycle)
            continue
        issues.extend(_research_eligibility_issues(source))
    return issues


def _research_lifecycle_issue(source: ResearchSourceState) -> ReadinessIssue | None:
    """The one blocker that stops all further judgement of a pinned revision."""
    if not source.found:
        reason = "does not resolve to a research dataset revision"
    elif not source.root_active:
        reason = "belongs to a deleted or inaccessible research dataset"
    elif source.revision_state != _BACKTEST_ELIGIBLE_REVISION_STATE:
        reason = f"is not Approved (state={source.revision_state})"
    else:
        return None
    return ReadinessIssue(
        Code.LIFECYCLE_BLOCKED,
        Sev.BLOCKER,
        Scope.RESEARCH_DATA,
        f"The pinned research dataset revision '{source.revision_id}' {reason}.",
        remediation=(
            "Pin an Approved revision of an active research dataset (or ask an Admin to "
            "approve/restore it), then re-run the check."
        ),
        field_path=source.field_path,
        scope_id=source.item_id,
    )


def _research_eligibility_issues(source: ResearchSourceState) -> list[ReadinessIssue]:
    """Scope / available-time / market-compatibility / coverage over a RESOLVED,
    Approved revision."""
    issues: list[ReadinessIssue] = []
    if source.usage_scope != _BACKTEST_ELIGIBLE_USAGE_SCOPE:
        issues.append(
            ReadinessIssue(
                Code.USAGE_SCOPE_FORBIDDEN,
                Sev.BLOCKER,
                Scope.RESEARCH_DATA,
                (
                    f"Research revision '{source.revision_id}' has usage scope "
                    f"'{source.usage_scope}', which forbids backtest consumption."
                ),
                remediation=(
                    "Use the dataset for research artifacts only, or pin a revision whose "
                    "usage scope is 'research_backtest' (a Feature Input Only dataset must "
                    "reach the strategy through an approved versioned feature definition)."
                ),
                field_path=source.field_path,
                scope_id=source.item_id,
            )
        )
    if _available_time_is_undefined(source):
        issues.append(
            ReadinessIssue(
                Code.TIME_POLICY_INVALID,
                Sev.BLOCKER,
                Scope.RESEARCH_DATA,
                (
                    f"Research revision '{source.revision_id}' has no usable available-time "
                    "policy, so the engine cannot prove when a value first became known."
                ),
                remediation=(
                    "Set a documented available-time policy on the dataset revision (a fixed "
                    "delay needs a positive delay), re-analyze, then re-run the check."
                ),
                field_path=source.field_path,
                scope_id=source.item_id,
            )
        )
    issues.extend(_research_market_compatibility_issues(source))
    if source.validation_status == _VALIDATION_WARNING:
        issues.append(
            ReadinessIssue(
                Code.RESEARCH_COVERAGE_LIMITED,
                Sev.WARNING,
                Scope.RESEARCH_DATA,
                (
                    f"Research revision '{source.revision_id}' carries a non-blocking quality "
                    "finding (limited coverage or low fill rate) from its analysis."
                ),
                remediation=(
                    "Review the dataset's quality report and decide whether the recorded gaps "
                    "are acceptable for this run, or pin a fuller revision."
                ),
                field_path=source.field_path,
                scope_id=source.item_id,
            )
        )
    return issues


def _available_time_is_undefined(source: ResearchSourceState) -> bool:
    """Available time is undefined when no policy is declared, or a fixed delay is
    declared without a positive bounded delay (doc 12 §5.2)."""
    policy = source.available_time_policy
    if not policy:
        return True
    if policy != _FIXED_DELAY_POLICY:
        return False
    delay = source.available_delay_seconds
    return delay is None or delay <= 0


def _research_market_compatibility_issues(source: ResearchSourceState) -> list[ReadinessIssue]:
    """ "Exact Market Data compatibility" — the link must point at the SAME market
    revision the strategy pins, and the link/mapping pair must be coherent."""
    issues: list[ReadinessIssue] = []
    linked = (source.linked_market_dataset_revision_id or "").strip()
    strategy_pin = (source.strategy_market_dataset_revision_id or "").strip()
    if linked and strategy_pin and linked != strategy_pin:
        issues.append(
            ReadinessIssue(
                Code.DEPENDENCY_BLOCKED,
                Sev.BLOCKER,
                Scope.RESEARCH_DATA,
                (
                    f"Research revision '{source.revision_id}' is linked to market dataset "
                    f"revision '{linked}', but the strategy runs on '{strategy_pin}'."
                ),
                remediation=(
                    "Pin a research revision linked to the strategy's market dataset revision, "
                    "or align the strategy's market pin, then re-run the check."
                ),
                field_path=source.field_path,
                scope_id=source.item_id,
            )
        )
    if not instrument_mapping_is_valid(
        linked_market_dataset_revision_id=source.linked_market_dataset_revision_id,
        instrument_mapping_ref=source.instrument_mapping_ref,
    ):
        issues.append(
            ReadinessIssue(
                Code.INSTRUMENT_MAPPING_INVALID,
                Sev.BLOCKER,
                Scope.RESEARCH_DATA,
                (
                    f"Research revision '{source.revision_id}' declares a market link without "
                    "an instrument mapping (or a mapping without a link)."
                ),
                remediation=(
                    "Declare both the linked market dataset revision and its instrument "
                    "mapping on the research revision, or neither, then re-run the check."
                ),
                field_path=source.field_path,
                scope_id=source.item_id,
            )
        )
    return issues


# --------------------------------------------------------------------------- #
# External working objects — Trading Signal / Trade Log (§5.1, §9.2, RC-07/08) #
# --------------------------------------------------------------------------- #


def _external_issues(item: ReadinessItemInput, *, allocation_enabled: bool) -> list[ReadinessIssue]:
    is_trade_log = item.kind == MainboardItemKind.TRADE_LOG
    issues: list[ReadinessIssue] = []

    config: TradeLogConfig | TradingSignalConfig | None
    semantic: str | None
    if is_trade_log:
        config, semantic = _parse_trade_log(item.payload)
    else:
        config, semantic = _parse_trading_signal(item.payload)

    if config is None:
        return [
            ReadinessIssue(
                Code.EXTERNAL_IMPORT_INVALID,
                Sev.BLOCKER,
                Scope.EXTERNAL_OBJECT,
                "The pinned import revision does not resolve to a valid configuration.",
                remediation="Re-import the source and bind an accepted normalized revision.",
                field_path=semantic,
                scope_id=item.item_id,
            )
        ]
    if semantic is not None:
        issues.append(
            ReadinessIssue(
                Code.EXTERNAL_IMPORT_INVALID,
                Sev.BLOCKER,
                Scope.EXTERNAL_OBJECT,
                "The import configuration has a policy conflict.",
                remediation="Correct the price/OHLCV/event-model policy and re-import.",
                field_path=semantic,
                scope_id=item.item_id,
            )
        )

    # RC-07: a browser file selection is never proof — a normalized, accepted
    # import revision must back the pinned config (doc 14 §5.1, Impl. Rules).
    ext = item.external
    if ext is None or not ext.found or not ext.succeeded or ext.accepted_count <= 0:
        issues.append(
            ReadinessIssue(
                Code.EXTERNAL_IMPORT_UNRESOLVED,
                Sev.BLOCKER,
                Scope.EXTERNAL_OBJECT,
                "No accepted normalized import revision backs this external object.",
                remediation="Complete ingestion/parse/mapping and bind the accepted import "
                "revision.",
                scope_id=item.item_id,
            )
        )
    else:
        # TL-09: V1 is single-instrument scope; any out-of-scope (mixed) symbol
        # row makes the import a Ready blocker (doc 05 §5.1, spec line 1099).
        if REASON_INSTRUMENT_MISMATCH in ext.skipped_reason_codes:
            issues.append(
                ReadinessIssue(
                    Code.MIXED_SYMBOL_SCOPE,
                    Sev.BLOCKER,
                    Scope.EXTERNAL_OBJECT,
                    "The import contains rows outside the declared single-instrument scope.",
                    remediation="Correct the instrument scope/mapping or split the mixed-symbol "
                    "source into separate imports.",
                    scope_id=item.item_id,
                )
            )
        # RC-08: chronology-invalid rows are rejected under explicit policy (skipped,
        # never silently passed) — surfaced as a non-blocking quality warning.
        if REASON_EXIT_BEFORE_ENTRY in ext.skipped_reason_codes:
            issues.append(
                ReadinessIssue(
                    Code.TRADE_LOG_CHRONOLOGY_INVALID,
                    Sev.WARNING,
                    Scope.EXTERNAL_OBJECT,
                    "Some rows were skipped because exit_time precedes entry_time.",
                    remediation="Review the skipped-row report; correct the source chronology "
                    "if these rows are needed.",
                    scope_id=item.item_id,
                )
            )

    # OHLCV price/context dependency — applied to BOTH external twins (K-08). This
    # check used to be conditioned on ``is_trade_log``, which let a Trading Signal
    # selecting ``ohlcv_close_if_needed`` / ``ohlcv_intrabar_if_available`` reach Ready
    # PASS with no market data behind the fallback. Doc 04 §5 states the requirement for
    # a Trading Signal in the same words doc 05 §5.3 states it for a Trade Log
    # ("Fallback options require compatible approved Market Data at Ready Check"), so
    # the RULE is shared and only the emitted CODE differs per page taxonomy.
    if isinstance(config, TradeLogConfig):
        issues.extend(_trade_log_market_data_issues(config, item_id=item.item_id))
    else:
        issues.extend(_signal_market_data_issues(config, item_id=item.item_id))

    # TL-11: in independent-capital mode each enabled external item needs its own
    # Initial Capital > 0 (doc 14 §5.1 Independent capital mode).
    if not allocation_enabled and _independent_capital(config) is None:
        issues.append(
            ReadinessIssue(
                Code.INDEPENDENT_CAPITAL_REQUIRED,
                Sev.BLOCKER,
                Scope.EXTERNAL_OBJECT,
                "Independent capital mode requires this item's own Initial Capital > 0.",
                remediation="Enable Portfolio Allocation or set an independent Initial Capital "
                "on this item.",
                field_path="capital.independent_initial_capital",
                scope_id=item.item_id,
            )
        )
    return issues


def _trade_log_market_data_issues(config: TradeLogConfig, *, item_id: str) -> list[ReadinessIssue]:
    """Trade Log side of the shared OHLCV-fallback rule (doc 05 §5.3, Impl. Rule 8).

    Unchanged behaviour and unchanged code — ``OHLCV_FALLBACK_MARKET_DATA_MISSING`` is
    what the Trade Log page, its taxonomy and its shipped tests already speak.
    """
    price = config.price_policy
    if (
        price.source not in _OHLCV_FALLBACK_SOURCES
        or price.approved_market_data_revision_ref is not None
    ):
        return []
    return [
        ReadinessIssue(
            Code.OHLCV_FALLBACK_MARKET_DATA_MISSING,
            Sev.BLOCKER,
            Scope.EXTERNAL_OBJECT,
            "An OHLCV price fallback requires an approved Market Data revision reference.",
            remediation="Bind an Approved Market Data revision to price_policy, or use "
            "the trade-log entry/exit price source.",
            field_path="price_policy.approved_market_data_revision_ref",
            scope_id=item_id,
        )
    ]


def _signal_market_data_issues(
    config: TradingSignalConfig, *, item_id: str
) -> list[ReadinessIssue]:
    """Trading Signal side of the same rule, plus its OHLCV-context twin (doc 04 §5/§5.2).

    Two DISTINCT defects, deliberately reported independently because they have
    different remediations and either can hold alone:

    * ``MARKET_DATA_DEPENDENCY_BLOCKED`` — an OHLCV price fallback with nothing approved
      behind it (doc 04 §5 Price Source row; doc 04 §11 Dependency row names the code).
      The user can either bind a revision or drop back to ``suggested_signal_price``.
    * ``OHLCV_CONTEXT_REQUIRED`` — "OHLCV Use = Use for price context and validation"
      was chosen while Data Quality is ``signal_events_with_market_context``, i.e. the
      source file supplies NO OHLCV, so the only possible provider of that context is an
      approved Market Data pin (doc 04 §5.2 OHLCV-Use row). The sibling combinations are
      already gated elsewhere and are NOT re-reported here: with
      ``signal_events_with_source_ohlcv`` the file itself is the context, and
      ``signal_events_only`` + this use mode is a save-time ``OHLCV_POLICY_CONFLICT``
      in ``trading_signal/compiler.py`` (surfaced above as ``EXTERNAL_IMPORT_INVALID``).

    Honest boundary: this layer only proves a reference was DECLARED. Whether it
    resolves to an ACTIVE + APPROVED revision, and whether that revision can actually
    carry intrabar detail, is a DB read and lives in
    ``commands/readiness_check.py::_resolve_signal_market_data_issues`` — the same
    split as ``_resolve_market_data_issues`` / ``_resolve_tick_data_issues``.
    """
    issues: list[ReadinessIssue] = []
    price = config.price_policy
    if price.source in _OHLCV_FALLBACK_SOURCES and price.approved_market_data_revision_ref is None:
        issues.append(
            ReadinessIssue(
                Code.MARKET_DATA_DEPENDENCY_BLOCKED,
                Sev.BLOCKER,
                Scope.EXTERNAL_OBJECT,
                "An OHLCV price fallback requires a compatible approved Market Data revision.",
                remediation="Bind an Approved Market Data revision to price_policy, or use "
                "the suggested signal entry/exit price source.",
                field_path="price_policy.approved_market_data_revision_ref",
                scope_id=item_id,
            )
        )
    if (
        config.ohlcv_policy.use_mode == SignalOhlcvUseMode.USE_FOR_PRICE_CONTEXT_AND_VALIDATION
        and config.data_quality.mode == SignalDataQualityMode.SIGNAL_EVENTS_WITH_MARKET_CONTEXT
        and price.approved_market_data_revision_ref is None
    ):
        issues.append(
            ReadinessIssue(
                Code.OHLCV_CONTEXT_REQUIRED,
                Sev.BLOCKER,
                Scope.EXTERNAL_OBJECT,
                "Using OHLCV for price context and validation requires an approved Market "
                "Data revision, because this signal supplies no source OHLCV of its own.",
                remediation="Bind an Approved Market Data revision to price_policy, switch "
                "OHLCV Use to 'ignore', or re-import with source OHLCV columns.",
                field_path="ohlcv_policy.use_mode",
                scope_id=item_id,
            )
        )
    return issues


def _parse_trade_log(payload: dict[str, Any]) -> tuple[TradeLogConfig | None, str | None]:
    try:
        config = TradeLogConfig(**payload)
    except PydanticValidationError as exc:
        return None, _first_error_path(exc)
    semantic = validate_trade_log_semantics(config)
    return config, (semantic[0]["field"] if semantic else None)


def _parse_trading_signal(payload: dict[str, Any]) -> tuple[TradingSignalConfig | None, str | None]:
    try:
        config = TradingSignalConfig(**payload)
    except PydanticValidationError as exc:
        return None, _first_error_path(exc)
    semantic = validate_signal_semantics(config)
    return config, (semantic[0]["field"] if semantic else None)


def _independent_capital(
    config: TradeLogConfig | TradingSignalConfig,
) -> object | None:
    return config.capital.independent_initial_capital


# --------------------------------------------------------------------------- #
# Portfolio allocation (doc 14 §9.2, RC-03/RC-04) — 4a issues mapped 1:1        #
# --------------------------------------------------------------------------- #


def _map_allocation_issues(
    allocation_issues: Sequence[AllocationIssue],
) -> list[ReadinessIssue]:
    mapped: list[ReadinessIssue] = []
    for issue in allocation_issues:
        severity = Sev.BLOCKER if str(issue.severity) == str(AllocSev.BLOCKER) else Sev.WARNING
        code = _ALLOC_CODE_MAP.get(str(issue.code), Code.ALLOCATION_ISSUE)
        mapped.append(
            ReadinessIssue(
                code,
                severity,
                Scope.PORTFOLIO_ALLOCATION,
                issue.message,
                field_path=issue.field,
                scope_id=issue.composition_item_id,
            )
        )
    return mapped


def _first_error_path(exc: PydanticValidationError) -> str | None:
    errors = exc.errors()
    if not errors:
        return None
    return ".".join(str(p) for p in errors[0].get("loc", ()))


__all__ = [
    "ReadinessEvaluation",
    "evaluate_readiness",
    "is_stale",
    "validate_research_sources",
]
