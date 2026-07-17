"""Pure, deterministic Ready Check validators + state derivation (Stage 4b,
doc 14 §9.2 "Validator architecture and fixed check order").

These are separate pure domain services (doc 14 §9.2 "not one large frontend
handler"). Nothing here touches the DB, the clock or the request. The command
orchestrator resolves inputs (snapshot items, pinned payloads, external import
batch state, allocation config) and calls :func:`evaluate_readiness`; it owns
aggregation, report persistence and audit.

Fixed check order (doc 14 §9.2): composition -> lifecycle -> strategy ->
market data -> external working objects -> portfolio allocation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from entropia.domain.allocation.enums import AllocationIssueCode as AllocCode
from entropia.domain.allocation.enums import AllocationIssueSeverity as AllocSev
from entropia.domain.allocation.rules import AllocationIssue
from entropia.domain.backtest.engine import (
    conflict_handling_is_modelled,
    execution_timing_is_modelled,
    leverage_is_modelled,
    order_execution_is_modelled,
    partial_close_is_modelled,
    restrictions_are_modelled,
    scaling_is_modelled,
    signal_strength_is_modelled,
    sizing_is_modelled,
)
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
from entropia.domain.readiness.issues import ReadinessIssue, ReadinessItemInput
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
_OHLCV_FALLBACK_SOURCES = frozenset(
    {
        TradeLogPriceSource.OHLCV_CLOSE_IF_NEEDED,
        TradeLogPriceSource.OHLCV_INTRABAR_IF_AVAILABLE,
    }
)

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
    strategy_indicator_issues: Sequence[ReadinessIssue] = (),
) -> ReadinessEvaluation:
    """Aggregate all validator layers into an immutable evaluation (doc 14 §9.2).

    ``items`` are the ENABLED composition members (a disabled item never enters a
    snapshot). ``allocation_issues`` is the 4a ``validate_allocation`` output for
    the shared pool (empty in independent mode); it is mapped 1:1 here.
    ``strategy_indicator_issues`` are the F-06 upfront-RUN-gate blockers the command
    resolved from each strategy's pinned indicator plan (a DB read, like
    ``market_data_issues``) — an unresolved required dependency blocks RUN so the
    worker can never silently substitute the breakout proxy.
    """
    issues: list[ReadinessIssue] = []
    issues.extend(_composition_issues(items))
    issues.extend(_instrument_consistency_issues(items))
    for item in items:
        issues.extend(_item_issues(item, allocation_enabled=allocation_enabled))
    issues.extend(market_data_issues)
    issues.extend(strategy_indicator_issues)
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

    # F-07a: an unsupported entry/exit EXECUTION TIMING must BLOCK RUN — the engine
    # fails closed (opens no position) for it, so a run would silently produce nothing.
    # Over plain OHLCV the intrabar-touch and limit/stop-limit simulation modes cannot
    # be faithfully reproduced (doc 02: "cannot silently imitate unavailable detail") and
    # are deferred to later F-07 slices. Shares the single ``execution_timing_is_modelled``
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
                "and Limit/Stop-Limit simulation are not yet supported over OHLCV data.",
                field_path="data.execution",
                scope_id=item.item_id,
            )
        )

    # F-07b: an unsupported ORDER TYPE must BLOCK RUN — the engine fails closed (opens no
    # position) for it. A Stop / Stop-Limit order carries no trigger/activation price in the
    # saved schema (and stop-limit needs intrabar stop-vs-limit ordering); a Limit order
    # with a best-bid/ask price rule needs a quote series absent over OHLCV; and a partial-
    # fill policy other than "not allowed" is deferred to a later slice. Shares the single
    # ``order_execution_is_modelled`` predicate with the engine so the two never diverge.
    if not order_execution_is_modelled(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_ORDER_TYPE_UNSUPPORTED,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy's order type is not supported by the backtest engine and "
                "would open no position.",
                remediation="Use a Market Order or Simulation Only, or a Limit Order with an "
                "entry-signal / signal±offset price rule and 'partial fill not allowed'. Stop "
                "and Stop-Limit orders (no trigger price is stored), a best-bid/ask limit "
                "price, and partial fills are not yet supported.",
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

    # F-07d: an unsupported SCALING configuration must BLOCK RUN — the engine fails closed
    # (opens no position) for it. Price-Distance scaling on the strategy's own timeframe with
    # a positive add size is modelled; Logic-Based scaling, a per-layer timeframe override
    # (increasing-by-layer / custom TF sequence), a missing/non-positive add size and a
    # negative/non-positive cap are deferred or misconfigured. Shares the single
    # ``scaling_is_modelled`` predicate with the engine so the two never diverge. Disabled
    # (or absent) scaling raises nothing.
    if not scaling_is_modelled(config):
        issues.append(
            ReadinessIssue(
                Code.STRATEGY_SCALING_UNSUPPORTED,
                Sev.BLOCKER,
                Scope.STRATEGY,
                "The strategy's scaling (additional layer) configuration is not supported "
                "by the backtest engine and would open no position.",
                remediation="Use Price-Distance Based scaling on the strategy timeframe "
                "with a positive add size, or disable scaling. Logic-Based scaling and "
                "per-layer timeframe overrides are not yet supported.",
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

    # OHLCV fallback (Trade Log): an OHLCV price fallback needs an approved Market
    # Data revision reference at execution time (doc 05 §5.3, Impl. Rule 8).
    if (
        is_trade_log
        and isinstance(config, TradeLogConfig)
        and config.price_policy.source in _OHLCV_FALLBACK_SOURCES
        and config.price_policy.approved_market_data_revision_ref is None
    ):
        issues.append(
            ReadinessIssue(
                Code.OHLCV_FALLBACK_MARKET_DATA_MISSING,
                Sev.BLOCKER,
                Scope.EXTERNAL_OBJECT,
                "An OHLCV price fallback requires an approved Market Data revision reference.",
                remediation="Bind an Approved Market Data revision to price_policy, or use "
                "the trade-log entry/exit price source.",
                field_path="price_policy.approved_market_data_revision_ref",
                scope_id=item.item_id,
            )
        )

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
]
