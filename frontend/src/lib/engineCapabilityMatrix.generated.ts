// GENERATED FILE — DO NOT EDIT BY HAND.
//
// Rendered from backend/src/entropia/domain/backtest/capabilities.py (the canonical
// machine-readable engine capability matrix, F-05) by:
//
//     cd backend && uv run python tools/export_capability_matrix.py
//
// backend/tests/unit/test_capability_matrix.py re-renders this file and asserts byte
// equality, so editing it here (or changing the Python matrix without regenerating)
// fails CI. The engine fail-closes on every `future_dev` option and Ready Check blocks
// it with STRATEGY_CAPABILITY_NOT_IN_BUILD; this mirror exists so the Strategy editor
// can disable those options BEFORE a user builds a strategy on one.

/** Whether this build actually executes an option value. */
export type CapabilityStatus = "active_v1" | "future_dev";

export interface CapabilityOption {
  /** Canonical dotted path of the option in the saved strategy payload. */
  fieldPath: string;
  /** The saved enum literal (never the human label). */
  value: string;
  /** `active_v1` = executes; `future_dev` = never executes in this build. */
  status: CapabilityStatus;
  /** The V18 surface label, mirrored from the backend matrix. */
  label: string;
  /**
   * For `active_v1`: the extra condition the option needs to run (empty = none).
   * For `future_dev`: WHY it cannot run — the missing data series or model.
   */
  dependency: string;
  /** The Ready Check code that enforces this row. */
  blockerCode: string;
}

export const ENGINE_CAPABILITY_MATRIX: readonly CapabilityOption[] = [
  {
    "fieldPath": "data.costs.slippage_mode",
    "value": "percentage_slippage",
    "status": "active_v1",
    "label": "Percentage Slippage",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.costs.slippage_mode",
    "value": "historical_slippage_if_available",
    "status": "future_dev",
    "label": "Historical Slippage If Available",
    "dependency": "Needs an observed per-fill historical slippage series (Master Ref §2.3 Spread/Execution dataset); the OHLCV and tick/trade print paths do not carry realized slippage, and deriving it from last price alone would fabricate an execution cost.",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.order_config.limit.price_rule",
    "value": "entry_signal_price",
    "status": "active_v1",
    "label": "Entry signal price",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.order_config.limit.price_rule",
    "value": "signal_price_minus_offset",
    "status": "active_v1",
    "label": "Signal price minus offset",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.order_config.limit.price_rule",
    "value": "signal_price_plus_offset",
    "status": "active_v1",
    "label": "Signal price plus offset",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.order_config.limit.price_rule",
    "value": "best_bid_ask",
    "status": "future_dev",
    "label": "Best bid / ask",
    "dependency": "Needs an observed bid/ask QUOTE series (Master Ref §2.3 Spread/Execution dataset). The tick/trade print path carries executions, not quotes, so a best-bid/ask fill cannot be reconstructed even with 'Use Tick Data' = Yes.",
    "blockerCode": "STRATEGY_ORDER_TYPE_UNSUPPORTED"
  },
  {
    "fieldPath": "data.order_config.limit.partial_fill_policy",
    "value": "not_allowed",
    "status": "active_v1",
    "label": "Not Allowed",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.order_config.limit.partial_fill_policy",
    "value": "allowed",
    "status": "active_v1",
    "label": "Allowed",
    "dependency": "Requires 'Use Tick Data' = Yes — the filled fraction is computed from the print path's trade sizes and is never fabricated from bars alone.",
    "blockerCode": "STRATEGY_ORDER_TYPE_UNSUPPORTED"
  },
  {
    "fieldPath": "data.order_config.limit.partial_fill_policy",
    "value": "minimum_50_percent",
    "status": "active_v1",
    "label": "Minimum 50% Fill",
    "dependency": "Requires 'Use Tick Data' = Yes — the filled fraction is computed from the print path's trade sizes and is never fabricated from bars alone.",
    "blockerCode": "STRATEGY_ORDER_TYPE_UNSUPPORTED"
  },
  {
    "fieldPath": "data.order_config.limit.partial_fill_policy",
    "value": "fill_remaining_as_market",
    "status": "active_v1",
    "label": "Fill Remaining as Market",
    "dependency": "Requires 'Use Tick Data' = Yes — the filled fraction is computed from the print path's trade sizes and is never fabricated from bars alone.",
    "blockerCode": "STRATEGY_ORDER_TYPE_UNSUPPORTED"
  },
  {
    "fieldPath": "data.order_config.limit.partial_fill_policy",
    "value": "cancel_remaining",
    "status": "active_v1",
    "label": "Cancel Remaining",
    "dependency": "Requires 'Use Tick Data' = Yes — the filled fraction is computed from the print path's trade sizes and is never fabricated from bars alone.",
    "blockerCode": "STRATEGY_ORDER_TYPE_UNSUPPORTED"
  },
  {
    "fieldPath": "data.execution.entry_timing",
    "value": "current_candle_close",
    "status": "active_v1",
    "label": "Current Candle Close",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.execution.entry_timing",
    "value": "next_candle_open",
    "status": "active_v1",
    "label": "Next Candle Open",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.execution.entry_timing",
    "value": "next_candle_close",
    "status": "active_v1",
    "label": "Next Candle Close",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.execution.entry_timing",
    "value": "market_fill_simulation",
    "status": "active_v1",
    "label": "Market Fill Simulation",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.execution.entry_timing",
    "value": "intrabar_touch",
    "status": "active_v1",
    "label": "Intrabar Touch",
    "dependency": "Requires 'Use Tick Data' = Yes — the touch is resolved over the real intrabar print path, never imitated over plain OHLCV.",
    "blockerCode": "STRATEGY_EXECUTION_TIMING_UNSUPPORTED"
  },
  {
    "fieldPath": "data.execution.entry_timing",
    "value": "limit_fill_simulation",
    "status": "active_v1",
    "label": "Limit Fill Simulation",
    "dependency": "Requires 'Use Tick Data' = Yes AND a Limit or Stop-Limit order type — it simulates the CONFIGURED limit order's fill over the print path, so with a market-like order type there is no limit order to simulate.",
    "blockerCode": "STRATEGY_EXECUTION_TIMING_UNSUPPORTED"
  },
  {
    "fieldPath": "data.execution.exit_timing",
    "value": "current_candle_close",
    "status": "active_v1",
    "label": "Current Candle Close",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.execution.exit_timing",
    "value": "next_candle_open",
    "status": "active_v1",
    "label": "Next Candle Open",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.execution.exit_timing",
    "value": "next_candle_close",
    "status": "active_v1",
    "label": "Next Candle Close",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.execution.exit_timing",
    "value": "market_fill_simulation",
    "status": "active_v1",
    "label": "Market Fill Simulation",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "data.execution.exit_timing",
    "value": "intrabar_touch",
    "status": "active_v1",
    "label": "Intrabar Touch",
    "dependency": "Requires 'Use Tick Data' = Yes — the touch is resolved over the real intrabar print path, never imitated over plain OHLCV.",
    "blockerCode": "STRATEGY_EXECUTION_TIMING_UNSUPPORTED"
  },
  {
    "fieldPath": "data.execution.exit_timing",
    "value": "stop_limit_priority_simulation",
    "status": "active_v1",
    "label": "Stop / Limit Priority Simulation",
    "dependency": "Requires 'Use Tick Data' = Yes — the same-bar stop-then-limit ordering is resolved from the observed print sequence, which bars cannot supply.",
    "blockerCode": "STRATEGY_EXECUTION_TIMING_UNSUPPORTED"
  },
  {
    "fieldPath": "position_sizing.formula_based.formula_type",
    "value": "kelly_criterion",
    "status": "active_v1",
    "label": "Kelly Criterion",
    "dependency": "Needs formula_params with win_probability in (0,1) and a positive payoff_ratio (an optional kelly_fraction in (0,1]).",
    "blockerCode": "STRATEGY_SIZING_UNSUPPORTED"
  },
  {
    "fieldPath": "position_sizing.formula_based.formula_type",
    "value": "custom_formula",
    "status": "future_dev",
    "label": "Custom Formula",
    "dependency": "Needs a sandboxed expression evaluator with a pinned function/operator grammar; the engine performs no arbitrary-expression evaluation, so a custom formula has no defined deterministic meaning.",
    "blockerCode": "STRATEGY_SIZING_UNSUPPORTED"
  },
  {
    "fieldPath": "position_sizing.leverage_mode",
    "value": "no_leverage",
    "status": "active_v1",
    "label": "No Leverage",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "position_sizing.leverage_mode",
    "value": "isolated",
    "status": "active_v1",
    "label": "Isolated",
    "dependency": "Needs a positive saved leverage multiplier.",
    "blockerCode": "STRATEGY_LEVERAGE_UNSUPPORTED"
  },
  {
    "fieldPath": "position_sizing.leverage_mode",
    "value": "cross",
    "status": "future_dev",
    "label": "Cross",
    "dependency": "Needs a portfolio-level margin/risk model that shares margin across concurrently open positions (Master Ref §10.2 — cross-margin logic depends on the Equity Allocation model); the single-position bar-replay has no such shared margin pool.",
    "blockerCode": "STRATEGY_LEVERAGE_UNSUPPORTED"
  },
  {
    "fieldPath": "position_sizing.signal_strength_adjustment",
    "value": "no_adjustment",
    "status": "active_v1",
    "label": "No Signal Strength Adjustment",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "position_sizing.signal_strength_adjustment",
    "value": "volatility_adjusted",
    "status": "active_v1",
    "label": "Volatility Adjusted",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "position_sizing.signal_strength_adjustment",
    "value": "trend_adjusted",
    "status": "future_dev",
    "label": "Trend Adjusted",
    "dependency": "Needs the signal-source configuration Master Ref §10.3 requires — condition-package refs, an adjustment formula and upper/lower band caps — none of which the saved schema carries; there is no canonical trend formula derivable from OHLCV alone.",
    "blockerCode": "STRATEGY_SIGNAL_STRENGTH_UNSUPPORTED"
  },
  {
    "fieldPath": "position_sizing.signal_strength_adjustment",
    "value": "divergence_adjusted",
    "status": "future_dev",
    "label": "Divergence Adjusted",
    "dependency": "Needs the signal-source configuration Master Ref §10.3 requires — condition-package refs, an adjustment formula and upper/lower band caps — none of which the saved schema carries; there is no canonical divergence formula derivable from OHLCV alone.",
    "blockerCode": "STRATEGY_SIGNAL_STRENGTH_UNSUPPORTED"
  },
  {
    "fieldPath": "position_exit_logic.partial_aftermath",
    "value": "move_stop_to_entry",
    "status": "active_v1",
    "label": "Move Stop To Entry",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "position_exit_logic.partial_aftermath",
    "value": "close_all",
    "status": "active_v1",
    "label": "Close All",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "position_exit_logic.partial_aftermath",
    "value": "lock_in_profit",
    "status": "active_v1",
    "label": "Lock In Profit",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "position_exit_logic.partial_aftermath",
    "value": "trailing_stop",
    "status": "active_v1",
    "label": "Trailing Stop",
    "dependency": "Needs protection_stop_logic.trailing_stop configured AND enabled — the aftermath carries no trailing distance of its own, so it reuses that rule's parameters.",
    "blockerCode": "STRATEGY_PARTIAL_CLOSE_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.method",
    "value": "price_distance_scaling",
    "status": "active_v1",
    "label": "Price-Distance Based",
    "dependency": "Needs a price_scaling subtree, a positive add_size_value and sane caps (max_scaling_layers >= 0, max_total_position_size > 0).",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.method",
    "value": "logic_based_scaling",
    "status": "active_v1",
    "label": "Logic Based",
    "dependency": "Needs at least one resolvable indicator block, a positive add_size_value and a DECLARED depth — max_scaling_layers or a custom timeframe sequence — because logic-based scaling has no layer count of its own (S5c).",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe",
    "value": "same_as_base_tf",
    "status": "active_v1",
    "label": "Same as base timeframe",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "scaling_logic.timeframe",
    "value": "use_package_default_tf",
    "status": "future_dev",
    "label": "Use package default timeframe",
    "dependency": "Doc 02 §5.7 declares no per-layer timeframe override, so there is no canonical behaviour to implement — the option set is canonical only for an Indicator Block.",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe",
    "value": "1m",
    "status": "future_dev",
    "label": "1m",
    "dependency": "Doc 02 §5.7 declares no per-layer timeframe override, so there is no canonical behaviour to implement — the option set is canonical only for an Indicator Block.",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe",
    "value": "3m",
    "status": "future_dev",
    "label": "3m",
    "dependency": "Doc 02 §5.7 declares no per-layer timeframe override, so there is no canonical behaviour to implement — the option set is canonical only for an Indicator Block.",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe",
    "value": "5m",
    "status": "future_dev",
    "label": "5m",
    "dependency": "Doc 02 §5.7 declares no per-layer timeframe override, so there is no canonical behaviour to implement — the option set is canonical only for an Indicator Block.",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe",
    "value": "15m",
    "status": "future_dev",
    "label": "15m",
    "dependency": "Doc 02 §5.7 declares no per-layer timeframe override, so there is no canonical behaviour to implement — the option set is canonical only for an Indicator Block.",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe",
    "value": "30m",
    "status": "future_dev",
    "label": "30m",
    "dependency": "Doc 02 §5.7 declares no per-layer timeframe override, so there is no canonical behaviour to implement — the option set is canonical only for an Indicator Block.",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe",
    "value": "1h",
    "status": "future_dev",
    "label": "1h",
    "dependency": "Doc 02 §5.7 declares no per-layer timeframe override, so there is no canonical behaviour to implement — the option set is canonical only for an Indicator Block.",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe",
    "value": "2h",
    "status": "future_dev",
    "label": "2h",
    "dependency": "Doc 02 §5.7 declares no per-layer timeframe override, so there is no canonical behaviour to implement — the option set is canonical only for an Indicator Block.",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe",
    "value": "4h",
    "status": "future_dev",
    "label": "4h",
    "dependency": "Doc 02 §5.7 declares no per-layer timeframe override, so there is no canonical behaviour to implement — the option set is canonical only for an Indicator Block.",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe",
    "value": "1D",
    "status": "future_dev",
    "label": "1D",
    "dependency": "Doc 02 §5.7 declares no per-layer timeframe override, so there is no canonical behaviour to implement — the option set is canonical only for an Indicator Block.",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe_mode",
    "value": "same_strategy",
    "status": "active_v1",
    "label": "Same as Strategy Timeframe",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "scaling_logic.timeframe_mode",
    "value": "custom_sequence",
    "status": "active_v1",
    "label": "Custom Timeframe Sequence",
    "dependency": "Needs a non-empty, strictly increasing custom_timeframe_sequence of canonical timeframes. Layer N is gated on the closed candle of entry N, and the sequence length also bounds the ladder.",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "scaling_logic.timeframe_mode",
    "value": "increasing_by_layer",
    "status": "active_v1",
    "label": "Increasing Timeframe by Layer",
    "dependency": "Each layer is gated on the closed candle one canonical timeframe further up from the run's base (doc 02 §6.1: 15m -> 30m -> 1h). The ladder ends at the top rung (1D) — a layer past it is never a candidate, exactly as a custom sequence runs out at its last entry (GH #547).",
    "blockerCode": "STRATEGY_SCALING_UNSUPPORTED"
  },
  {
    "fieldPath": "restrictions_filters.filters.filter_type",
    "value": "date_blackout_filter",
    "status": "active_v1",
    "label": "Date Blackout Windows",
    "dependency": "Needs a parseable date_ranges config and the block-entries action; other actions (reduce / close / disable / warn) are not modelled.",
    "blockerCode": "STRATEGY_RESTRICTIONS_UNSUPPORTED"
  },
  {
    "fieldPath": "restrictions_filters.filters.filter_type",
    "value": "max_daily_loss_filter",
    "status": "active_v1",
    "label": "Max Daily Loss",
    "dependency": "Needs a parseable limit_percent config and the block-entries action; other actions (reduce / close / disable / warn) are not modelled.",
    "blockerCode": "STRATEGY_RESTRICTIONS_UNSUPPORTED"
  },
  {
    "fieldPath": "restrictions_filters.filters.filter_type",
    "value": "consecutive_loss_filter",
    "status": "active_v1",
    "label": "Consecutive Loss Filter",
    "dependency": "Needs a parseable max_losses config and the block-entries action; other actions (reduce / close / disable / warn) are not modelled.",
    "blockerCode": "STRATEGY_RESTRICTIONS_UNSUPPORTED"
  },
  {
    "fieldPath": "restrictions_filters.filters.filter_type",
    "value": "volatility_filter",
    "status": "future_dev",
    "label": "Volatility Filter",
    "dependency": "Needs a volatility series (an ATR-style dependency) with a pinned definition; OHLCV alone gives no canonical volatility regime.",
    "blockerCode": "STRATEGY_RESTRICTIONS_UNSUPPORTED"
  },
  {
    "fieldPath": "restrictions_filters.filters.filter_type",
    "value": "spread_filter",
    "status": "future_dev",
    "label": "Spread Filter",
    "dependency": "Needs an observed bid/ask quote series — Master Ref §12.2 forbids deriving a fake spread from last price alone.",
    "blockerCode": "STRATEGY_RESTRICTIONS_UNSUPPORTED"
  },
  {
    "fieldPath": "restrictions_filters.filters.filter_type",
    "value": "volume_filter",
    "status": "future_dev",
    "label": "Volume Filter",
    "dependency": "Needs a pinned volume-regime definition (baseline window + threshold semantics) the saved schema does not carry.",
    "blockerCode": "STRATEGY_RESTRICTIONS_UNSUPPORTED"
  },
  {
    "fieldPath": "restrictions_filters.filters.filter_type",
    "value": "correlation_filter",
    "status": "future_dev",
    "label": "Correlation Filter",
    "dependency": "Needs a SECOND instrument's aligned series plus a pinned correlation window; the replay streams one instrument.",
    "blockerCode": "STRATEGY_RESTRICTIONS_UNSUPPORTED"
  },
  {
    "fieldPath": "restrictions_filters.filters.action",
    "value": "block",
    "status": "active_v1",
    "label": "Block",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "restrictions_filters.filters.action",
    "value": "block_entries",
    "status": "active_v1",
    "label": "Block New Entries",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "restrictions_filters.filters.action",
    "value": "reduce",
    "status": "future_dev",
    "label": "Reduce New Position Size",
    "dependency": "Needs a canonical size-reduction rule (factor and basis) doc 02 does not define; the modelled restriction surface is a binary entry-eligibility veto, not a sizing input.",
    "blockerCode": "STRATEGY_RESTRICTIONS_UNSUPPORTED"
  },
  {
    "fieldPath": "restrictions_filters.filters.action",
    "value": "close",
    "status": "future_dev",
    "label": "Close All Open Positions",
    "dependency": "Needs a forced-close path at filter-activation time; the modelled restriction surface only vetoes NEW entries and never touches an open position.",
    "blockerCode": "STRATEGY_RESTRICTIONS_UNSUPPORTED"
  },
  {
    "fieldPath": "restrictions_filters.filters.action",
    "value": "disable",
    "status": "future_dev",
    "label": "Disable Strategy for the Day",
    "dependency": "Needs day-scoped strategy state (disable-until-boundary) the replay does not carry; the modelled restriction surface decides per-bar entry eligibility only.",
    "blockerCode": "STRATEGY_RESTRICTIONS_UNSUPPORTED"
  },
  {
    "fieldPath": "restrictions_filters.filters.action",
    "value": "warn",
    "status": "future_dev",
    "label": "Warning Only",
    "dependency": "Needs a non-blocking advisory surface: a warn-only filter must admit the entry while reporting, and silently treating it as block would invert the saved intent.",
    "blockerCode": "STRATEGY_RESTRICTIONS_UNSUPPORTED"
  },
  {
    "fieldPath": "conflict_position_handling.opposite_direction_hedge",
    "value": "close_existing",
    "status": "active_v1",
    "label": "Close Existing",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "conflict_position_handling.opposite_direction_hedge",
    "value": "ignore",
    "status": "active_v1",
    "label": "Ignore",
    "dependency": "",
    "blockerCode": "STRATEGY_CAPABILITY_NOT_IN_BUILD"
  },
  {
    "fieldPath": "conflict_position_handling.opposite_direction_hedge",
    "value": "allow_hedge",
    "status": "future_dev",
    "label": "Allow Hedge",
    "dependency": "Needs two concurrent opposite positions with independent margin and PnL; the single-position bar-replay cannot hold both. Accepted only as an INERT value when 'exit on opposite signal' is ON — that setting closes the position before the hedge branch is ever reached, so no hedge is executed.",
    "blockerCode": "STRATEGY_CONFLICT_HANDLING_UNSUPPORTED"
  }
];

/** Index for O(1) lookup by `${fieldPath}\u0000${value}`. */
const BY_FIELD_VALUE = new Map<string, CapabilityOption>(
  ENGINE_CAPABILITY_MATRIX.map((option) => [`${option.fieldPath}\u0000${option.value}`, option]),
);

/**
 * The matrix row for one option value, or `undefined` when unenumerated.
 *
 * `undefined` means the value is not a capability decision (the field is absent from
 * the matrix because every value executes identically). Callers must treat it as NOT
 * `future_dev`: the matrix enumerates what is gated, never what is permitted.
 */
export function capabilityOption(fieldPath: string, value: string): CapabilityOption | undefined {
  return BY_FIELD_VALUE.get(`${fieldPath}\u0000${value}`);
}

/** Does this build refuse to execute the given option value? */
export function isFutureDev(fieldPath: string, value: string): boolean {
  return capabilityOption(fieldPath, value)?.status === "future_dev";
}
