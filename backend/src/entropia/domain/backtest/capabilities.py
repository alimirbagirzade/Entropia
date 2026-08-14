"""The machine-readable engine capability matrix (F-05 / M-05).

ONE canonical source of truth for the question "does this saved strategy option
actually EXECUTE in this build?" — consumed by three surfaces that previously
each carried their own private answer and could therefore disagree:

* the **engine** (:mod:`entropia.domain.backtest.engine`) imports
  :func:`capabilities_are_modelled` as a matrix-driven fail-closed entry gate, so
  a ``future_dev`` option opens NO position instead of silently degrading to some
  neighbouring behaviour;
* **Ready Check** (:mod:`entropia.domain.readiness.validators`) imports
  :func:`future_dev_selections` to raise the ``STRATEGY_CAPABILITY_NOT_IN_BUILD``
  blocker ("Not available in this build") BEFORE a run is ever admitted;
* the **Strategy editor** consumes the generated TS mirror
  (``frontend/src/lib/engineCapabilityMatrix.generated.ts``) to render
  ``future_dev`` options visibly disabled with their dependency note, so a user
  never builds a strategy on top of an option that cannot run.

The mirror is regenerated from :data:`CAPABILITY_MATRIX` by
``scripts/export_capability_matrix.py`` and pinned by a parity test, so drift
between the Python canon and the TS surface fails CI rather than shipping.

Why the matrix exists on top of the nine per-domain ``*_is_modelled`` predicates
already in the engine: those predicates answer a whole-CONFIG question ("is this
strategy's sizing modelled?") and fold value choices together with
misconfiguration (a missing ``trigger_offset``, a non-positive cap). They are
correct but they are not enumerable — nothing could ask them "which VALUES of
``leverage_mode`` are executable?", which is exactly what a UI and a parity test
need. The matrix answers per option VALUE; the predicates keep answering per
config. Both are kept: the matrix is the enumerable contract, the predicates
remain the precise misconfiguration gates.

Statuses (deliberately only two — a third "partial" state is what produced the
F-05 finding in the first place):

``active_v1``
    The option EXECUTES in this build. It may carry a :attr:`~CapabilityOption.dependency`
    — a condition the strategy must also satisfy for the option to run (e.g. the
    tick-dependent execution timings need 'Use Tick Data' = Yes). The dependency is
    enforced by the listed blocker code; it is NOT a reason to hide the option,
    because with the dependency met the option genuinely runs.

``future_dev``
    The option NEVER executes in this build. It is fail-closed in the engine and
    blocked by Ready Check. The UI disables it (keeping an already-saved value
    selectable so an existing strategy still round-trips without the form silently
    rewriting saved config).

Every ``future_dev`` row records WHY in :attr:`~CapabilityOption.dependency` — the
missing data series or model that would be needed — so the honest boundary is
documented at the single place the three surfaces read.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from entropia.domain.strategy.config import StrategyConfig

CapabilityStatus = Literal["active_v1", "future_dev"]

# Order-config types that carry the Limit Order Details subtree (mirrors the engine's
# ``_LIMIT_BACKED_ORDER_TYPES`` — a limit price rule / partial-fill policy is only a
# SELECTED option when the order type actually reveals that subtree).
_LIMIT_BACKED_ORDER_TYPES = frozenset({"limit_order", "stop_limit_order"})


@dataclass(frozen=True, slots=True)
class CapabilityOption:
    """One saved-config option VALUE and whether this build executes it."""

    field_path: str
    """Canonical dotted path of the option in the saved strategy payload."""

    value: str
    """The saved enum literal (never the human label — labels are presentation)."""

    status: CapabilityStatus
    """``active_v1`` = executes; ``future_dev`` = never executes in this build."""

    label: str
    """The V18 surface label, mirrored so the generated TS keeps one wording."""

    dependency: str = ""
    """For ``active_v1``: the extra condition the option needs to run (empty = none).
    For ``future_dev``: WHY it cannot run — the missing data series or model."""

    blocker_code: str = "STRATEGY_CAPABILITY_NOT_IN_BUILD"
    """The Ready Check code that enforces this row. ``future_dev`` rows ALSO always
    trip ``STRATEGY_CAPABILITY_NOT_IN_BUILD``; where a pre-existing per-domain
    blocker already covers the value it is recorded here instead, because that code
    carries the more specific remediation text."""


# ---------------------------------------------------------------------------
# The canonical matrix. Every row is empirically grounded in the engine predicate
# named in its comment — this table is a restatement of executable truth, never an
# aspiration. Only fields whose values differ in executability are enumerated;
# fields where every value executes identically (order validity windows, unfilled
# policies, slippage VALUE, stop-exit collision resolution, overlapping-signal and
# same-direction-stacking policies) are intentionally absent: an exhaustive listing
# of uniformly-active values would add drift surface without adding a single
# decision either the UI or Ready Check can act on.
# ---------------------------------------------------------------------------

CAPABILITY_MATRIX: tuple[CapabilityOption, ...] = (
    # -- Costs / slippage (_cost_params) -----------------------------------
    # ``_cost_params`` reads ONLY ``slippage_value`` as a percentage; it never
    # branches on ``slippage_mode``. A 'historical slippage' request therefore used
    # to run as percentage slippage — and, because ``slippage_value`` is optional
    # under that mode, in practice as ZERO slippage: a silently over-optimistic
    # fill model the user never asked for. That is the F-05 flagship finding; it is
    # now fail-closed here rather than quietly mismodelled.
    CapabilityOption(
        field_path="data.costs.slippage_mode",
        value="percentage_slippage",
        status="active_v1",
        label="Percentage Slippage",
    ),
    CapabilityOption(
        field_path="data.costs.slippage_mode",
        value="historical_slippage_if_available",
        status="future_dev",
        label="Historical Slippage If Available",
        dependency=(
            "Needs an observed per-fill historical slippage series (Master Ref §2.3 "
            "Spread/Execution dataset); the OHLCV and tick/trade print paths do not "
            "carry realized slippage, and deriving it from last price alone would "
            "fabricate an execution cost."
        ),
    ),
    # -- Limit price rule (order_execution_is_modelled) --------------------
    CapabilityOption(
        field_path="data.order_config.limit.price_rule",
        value="entry_signal_price",
        status="active_v1",
        label="Entry signal price",
    ),
    CapabilityOption(
        field_path="data.order_config.limit.price_rule",
        value="signal_price_minus_offset",
        status="active_v1",
        label="Signal price minus offset",
    ),
    CapabilityOption(
        field_path="data.order_config.limit.price_rule",
        value="signal_price_plus_offset",
        status="active_v1",
        label="Signal price plus offset",
    ),
    CapabilityOption(
        field_path="data.order_config.limit.price_rule",
        value="best_bid_ask",
        status="future_dev",
        label="Best bid / ask",
        dependency=(
            "Needs an observed bid/ask QUOTE series (Master Ref §2.3 Spread/Execution "
            "dataset). The tick/trade print path carries executions, not quotes, so a "
            "best-bid/ask fill cannot be reconstructed even with 'Use Tick Data' = Yes."
        ),
        blocker_code="STRATEGY_ORDER_TYPE_UNSUPPORTED",
    ),
    # -- Partial-fill policy (order_execution_is_modelled, F-07i C) --------
    # Every non-``not_allowed`` policy IS executed — the filled fraction comes from
    # the print path's trade sizes — but only when the strategy demands tick data.
    CapabilityOption(
        field_path="data.order_config.limit.partial_fill_policy",
        value="not_allowed",
        status="active_v1",
        label="Not Allowed",
    ),
    *(
        CapabilityOption(
            field_path="data.order_config.limit.partial_fill_policy",
            value=value,
            status="active_v1",
            label=label,
            dependency=(
                "Requires 'Use Tick Data' = Yes — the filled fraction is computed from "
                "the print path's trade sizes and is never fabricated from bars alone."
            ),
            blocker_code="STRATEGY_ORDER_TYPE_UNSUPPORTED",
        )
        for value, label in (
            ("allowed", "Allowed"),
            ("minimum_50_percent", "Minimum 50% Fill"),
            ("fill_remaining_as_market", "Fill Remaining as Market"),
            ("cancel_remaining", "Cancel Remaining"),
        )
    ),
    # -- Entry execution timing (execution_timing_is_modelled) -------------
    *(
        CapabilityOption(
            field_path="data.execution.entry_timing",
            value=value,
            status="active_v1",
            label=label,
        )
        for value, label in (
            ("current_candle_close", "Current Candle Close"),
            ("next_candle_open", "Next Candle Open"),
            ("next_candle_close", "Next Candle Close"),
            ("market_fill_simulation", "Market Fill Simulation"),
        )
    ),
    CapabilityOption(
        field_path="data.execution.entry_timing",
        value="intrabar_touch",
        status="active_v1",
        label="Intrabar Touch",
        dependency=(
            "Requires 'Use Tick Data' = Yes — the touch is resolved over the real "
            "intrabar print path, never imitated over plain OHLCV."
        ),
        blocker_code="STRATEGY_EXECUTION_TIMING_UNSUPPORTED",
    ),
    CapabilityOption(
        field_path="data.execution.entry_timing",
        value="limit_fill_simulation",
        status="active_v1",
        label="Limit Fill Simulation",
        dependency=(
            "Requires 'Use Tick Data' = Yes AND a Limit or Stop-Limit order type — it "
            "simulates the CONFIGURED limit order's fill over the print path, so with a "
            "market-like order type there is no limit order to simulate."
        ),
        blocker_code="STRATEGY_EXECUTION_TIMING_UNSUPPORTED",
    ),
    # -- Exit execution timing (execution_timing_is_modelled) --------------
    *(
        CapabilityOption(
            field_path="data.execution.exit_timing",
            value=value,
            status="active_v1",
            label=label,
        )
        for value, label in (
            ("current_candle_close", "Current Candle Close"),
            ("next_candle_open", "Next Candle Open"),
            ("next_candle_close", "Next Candle Close"),
            ("market_fill_simulation", "Market Fill Simulation"),
        )
    ),
    CapabilityOption(
        field_path="data.execution.exit_timing",
        value="intrabar_touch",
        status="active_v1",
        label="Intrabar Touch",
        dependency=(
            "Requires 'Use Tick Data' = Yes — the touch is resolved over the real "
            "intrabar print path, never imitated over plain OHLCV."
        ),
        blocker_code="STRATEGY_EXECUTION_TIMING_UNSUPPORTED",
    ),
    CapabilityOption(
        field_path="data.execution.exit_timing",
        value="stop_limit_priority_simulation",
        status="active_v1",
        label="Stop / Limit Priority Simulation",
        dependency=(
            "Requires 'Use Tick Data' = Yes — the same-bar stop-then-limit ordering is "
            "resolved from the observed print sequence, which bars cannot supply."
        ),
        blocker_code="STRATEGY_EXECUTION_TIMING_UNSUPPORTED",
    ),
    # -- Sizing formula type (sizing_is_modelled / _kelly_capital_fraction) -
    CapabilityOption(
        field_path="position_sizing.formula_based.formula_type",
        value="kelly_criterion",
        status="active_v1",
        label="Kelly Criterion",
        dependency=(
            "Needs formula_params with win_probability in (0,1) and a positive "
            "payoff_ratio (an optional kelly_fraction in (0,1])."
        ),
        blocker_code="STRATEGY_SIZING_UNSUPPORTED",
    ),
    CapabilityOption(
        field_path="position_sizing.formula_based.formula_type",
        value="custom_formula",
        status="future_dev",
        label="Custom Formula",
        dependency=(
            "Needs a sandboxed expression evaluator with a pinned function/operator "
            "grammar; the engine performs no arbitrary-expression evaluation, so a "
            "custom formula has no defined deterministic meaning."
        ),
        blocker_code="STRATEGY_SIZING_UNSUPPORTED",
    ),
    # -- Leverage mode (leverage_is_modelled) ------------------------------
    CapabilityOption(
        field_path="position_sizing.leverage_mode",
        value="no_leverage",
        status="active_v1",
        label="No Leverage",
    ),
    CapabilityOption(
        field_path="position_sizing.leverage_mode",
        value="isolated",
        status="active_v1",
        label="Isolated",
        dependency="Needs a positive saved leverage multiplier.",
        blocker_code="STRATEGY_LEVERAGE_UNSUPPORTED",
    ),
    CapabilityOption(
        field_path="position_sizing.leverage_mode",
        value="cross",
        status="future_dev",
        label="Cross",
        dependency=(
            "Needs a portfolio-level margin/risk model that shares margin across "
            "concurrently open positions (Master Ref §10.2 — cross-margin logic depends "
            "on the Equity Allocation model); the single-position bar-replay has no such "
            "shared margin pool."
        ),
        blocker_code="STRATEGY_LEVERAGE_UNSUPPORTED",
    ),
    # -- Signal-strength adjustment (signal_strength_is_modelled) ----------
    CapabilityOption(
        field_path="position_sizing.signal_strength_adjustment",
        value="no_adjustment",
        status="active_v1",
        label="No Signal Strength Adjustment",
    ),
    CapabilityOption(
        field_path="position_sizing.signal_strength_adjustment",
        value="volatility_adjusted",
        status="active_v1",
        label="Volatility Adjusted",
    ),
    *(
        CapabilityOption(
            field_path="position_sizing.signal_strength_adjustment",
            value=value,
            status="future_dev",
            label=label,
            dependency=(
                "Needs the signal-source configuration Master Ref §10.3 requires — "
                "condition-package refs, an adjustment formula and upper/lower band caps "
                "— none of which the saved schema carries; there is no canonical "
                f"{noun} formula derivable from OHLCV alone."
            ),
            blocker_code="STRATEGY_SIGNAL_STRENGTH_UNSUPPORTED",
        )
        for value, label, noun in (
            ("trend_adjusted", "Trend Adjusted", "trend"),
            ("divergence_adjusted", "Divergence Adjusted", "divergence"),
        )
    ),
    # -- Partial-close aftermath (partial_close_is_modelled) ---------------
    *(
        CapabilityOption(
            field_path="position_exit_logic.partial_aftermath",
            value=value,
            status="active_v1",
            label=label,
        )
        for value, label in (
            ("move_stop_to_entry", "Move Stop To Entry"),
            ("close_all", "Close All"),
            ("lock_in_profit", "Lock In Profit"),
        )
    ),
    CapabilityOption(
        field_path="position_exit_logic.partial_aftermath",
        value="trailing_stop",
        status="active_v1",
        label="Trailing Stop",
        dependency=(
            "Needs protection_stop_logic.trailing_stop configured AND enabled — the "
            "aftermath carries no trailing distance of its own, so it reuses that rule's "
            "parameters."
        ),
        blocker_code="STRATEGY_PARTIAL_CLOSE_UNSUPPORTED",
    ),
    # -- Scaling method (scaling_is_modelled) ------------------------------
    CapabilityOption(
        field_path="scaling_logic.method",
        value="price_distance_scaling",
        status="active_v1",
        label="Price-Distance Based",
        dependency=(
            "Needs a price_scaling subtree, a positive add_size_value and sane caps "
            "(max_scaling_layers >= 0, max_total_position_size > 0)."
        ),
        blocker_code="STRATEGY_SCALING_UNSUPPORTED",
    ),
    CapabilityOption(
        field_path="scaling_logic.method",
        value="logic_based_scaling",
        status="active_v1",
        label="Logic Based",
        dependency=(
            "Needs at least one resolvable indicator block, a positive add_size_value and "
            "a DECLARED depth — max_scaling_layers or a custom timeframe sequence — "
            "because logic-based scaling has no layer count of its own (S5c)."
        ),
        blocker_code="STRATEGY_SCALING_UNSUPPORTED",
    ),
    # -- Scaling timeframe (scaling_is_modelled) ---------------------------
    #
    # GH #541, corrected at ADIM 65. The `dependency` strings on the two scaling-timeframe
    # groups below used to state blockers that do not survive a canon read. Both were
    # re-measured against the tree before rewriting; the reasoning is kept HERE rather than
    # in `dependency` because the UI joins every future_dev option's dependency into one
    # paragraph (`CapabilityNote.tsx:24`), and this field group has ten of them — a long
    # string ships as ten repeats of itself to the user.
    #
    # 1. `scaling_logic.timeframe` (the ten overrides). The old text said a per-layer
    #    override "would require a second resampled series the replay does not build". The
    #    replay DOES build one: `indicators._ReferenceSeries` aggregates base candles
    #    (high=max, low=min, close=last, volume=sum) and advances only when a reference
    #    candle CLOSES, so it carries no look-ahead. What is actually absent is wiring that
    #    series to the scaling ladder's price comparison — and, further up, a canonical row
    #    to wire it to: doc 02 §5.7 carries Scaling Timeframe Structure, Timeframe Mode and
    #    Custom Timeframe Sequence, and no flat per-layer override. The identical option set
    #    is canonical only for an Indicator Block. So the blocker is a canonical gap, not a
    #    missing primitive, and building it would ship a field canon never asked for.
    #
    # 2. `scaling_logic.timeframe_mode="increasing_by_layer"` (below). The old text said the
    #    rung size is undeclared and offered "next canonical timeframe vs. doubling" as live
    #    alternatives. Doubling is not an alternative: doc 02 §6.1 states the mode steps
    #    "bir üst timeframe'e" and works it through as 15m -> 30m -> 1h, which is exactly
    #    `CANONICAL_TIMEFRAMES` index + 1. The genuine remainder is the TOP of the ladder —
    #    canon says nothing about a layer past `1D`, and clamping there, stopping the ladder
    #    and refusing the config are three different products.
    #
    # Neither row's `status`, `value`, `field_path`, `label` or `blocker_code` was touched;
    # only the reason text moved. Regenerate the TS mirror after any edit here
    # (`uv run python tools/export_capability_matrix.py`) — `dependency` is mirrored and
    # `test_capability_matrix.py::test_generated_typescript_mirror_is_up_to_date` pins it.
    CapabilityOption(
        field_path="scaling_logic.timeframe",
        value="same_as_base_tf",
        status="active_v1",
        label="Same as base timeframe",
    ),
    *(
        CapabilityOption(
            field_path="scaling_logic.timeframe",
            value=value,
            status="future_dev",
            label=label,
            dependency=(
                "Doc 02 §5.7 declares no per-layer timeframe override, so there is no "
                "canonical behaviour to implement — the option set is canonical only for an "
                "Indicator Block."
            ),
            blocker_code="STRATEGY_SCALING_UNSUPPORTED",
        )
        for value, label in (
            ("use_package_default_tf", "Use package default timeframe"),
            ("1m", "1m"),
            ("3m", "3m"),
            ("5m", "5m"),
            ("15m", "15m"),
            ("30m", "30m"),
            ("1h", "1h"),
            ("2h", "2h"),
            ("4h", "4h"),
            ("1D", "1D"),
        )
    ),
    # -- Scaling timeframe MODE / structure (scaling_is_modelled, S5c) ------
    # Distinct from ``scaling_logic.timeframe`` above: that field picks ONE evaluation
    # timeframe for the whole ladder (an override there still needs a resampled series),
    # while the mode says how the per-layer structure is shaped. S5c made the custom
    # sequence active because it needs no resampling — it only gates which base bars are
    # decision points.
    CapabilityOption(
        field_path="scaling_logic.timeframe_mode",
        value="same_strategy",
        status="active_v1",
        label="Same as Strategy Timeframe",
    ),
    CapabilityOption(
        field_path="scaling_logic.timeframe_mode",
        value="custom_sequence",
        status="active_v1",
        label="Custom Timeframe Sequence",
        dependency=(
            "Needs a non-empty, strictly increasing custom_timeframe_sequence of canonical "
            "timeframes. Layer N is gated on the closed candle of entry N, and the "
            "sequence length also bounds the ladder."
        ),
        blocker_code="STRATEGY_SCALING_UNSUPPORTED",
    ),
    CapabilityOption(
        field_path="scaling_logic.timeframe_mode",
        value="increasing_by_layer",
        status="future_dev",
        label="Increasing Timeframe by Layer",
        dependency=(
            "Needs a declared top-of-ladder rule. Doc 02 §6.1 fixes the rung — each layer "
            "steps one canonical timeframe up — but not what a layer past the last rung (1D) "
            "evaluates on, and clamping, stopping and refusing are different ladders."
        ),
        blocker_code="STRATEGY_SCALING_UNSUPPORTED",
    ),
    # -- Restriction filter types (restrictions_are_modelled) --------------
    *(
        CapabilityOption(
            field_path="restrictions_filters.filters.filter_type",
            value=value,
            status="active_v1",
            label=label,
            dependency=(
                f"Needs a parseable {cfg} config and the block-entries action; other "
                "actions (reduce / close / disable / warn) are not modelled."
            ),
            blocker_code="STRATEGY_RESTRICTIONS_UNSUPPORTED",
        )
        for value, label, cfg in (
            ("date_blackout_filter", "Date Blackout Windows", "date_ranges"),
            ("max_daily_loss_filter", "Max Daily Loss", "limit_percent"),
            ("consecutive_loss_filter", "Consecutive Loss Filter", "max_losses"),
        )
    ),
    *(
        CapabilityOption(
            field_path="restrictions_filters.filters.filter_type",
            value=value,
            status="future_dev",
            label=label,
            dependency=dependency,
            blocker_code="STRATEGY_RESTRICTIONS_UNSUPPORTED",
        )
        for value, label, dependency in (
            (
                "volatility_filter",
                "Volatility Filter",
                "Needs a volatility series (an ATR-style dependency) with a pinned "
                "definition; OHLCV alone gives no canonical volatility regime.",
            ),
            (
                "spread_filter",
                "Spread Filter",
                "Needs an observed bid/ask quote series — Master Ref §12.2 forbids "
                "deriving a fake spread from last price alone.",
            ),
            (
                "volume_filter",
                "Volume Filter",
                "Needs a pinned volume-regime definition (baseline window + threshold "
                "semantics) the saved schema does not carry.",
            ),
            (
                "correlation_filter",
                "Correlation Filter",
                "Needs a SECOND instrument's aligned series plus a pinned correlation "
                "window; the replay streams one instrument.",
            ),
        )
    ),
    # -- Opposite-direction hedge (conflict_handling_is_modelled) ----------
    *(
        CapabilityOption(
            field_path="conflict_position_handling.opposite_direction_hedge",
            value=value,
            status="active_v1",
            label=label,
        )
        for value, label in (("close_existing", "Close Existing"), ("ignore", "Ignore"))
    ),
    CapabilityOption(
        field_path="conflict_position_handling.opposite_direction_hedge",
        value="allow_hedge",
        status="future_dev",
        label="Allow Hedge",
        dependency=(
            "Needs two concurrent opposite positions with independent margin and PnL; "
            "the single-position bar-replay cannot hold both. Accepted only as an INERT "
            "value when 'exit on opposite signal' is ON — that setting closes the "
            "position before the hedge branch is ever reached, so no hedge is executed."
        ),
        blocker_code="STRATEGY_CONFLICT_HANDLING_UNSUPPORTED",
    ),
)


# ---------------------------------------------------------------------------
# Field readers — which value(s) of each matrix field does a saved config SELECT?
#
# Kept separate from the matrix so :data:`CAPABILITY_MATRIX` stays pure,
# serializable data (exportable verbatim to the TS mirror). A reader returns an
# empty tuple when the field is not reachable in this config — an inert value on a
# collapsed conditional subtree is NOT a selection and must not block a run.
# ---------------------------------------------------------------------------


def _read_slippage_mode(config: StrategyConfig) -> tuple[str, ...]:
    return (config.data.costs.slippage_mode,)


def _read_limit_price_rule(config: StrategyConfig) -> tuple[str, ...]:
    order = config.data.order_config
    if order.type not in _LIMIT_BACKED_ORDER_TYPES or order.limit is None:
        return ()
    return (order.limit.price_rule,)


def _read_limit_partial_fill(config: StrategyConfig) -> tuple[str, ...]:
    order = config.data.order_config
    if order.type not in _LIMIT_BACKED_ORDER_TYPES or order.limit is None:
        return ()
    return (order.limit.partial_fill_policy,)


def _read_entry_timing(config: StrategyConfig) -> tuple[str, ...]:
    return (config.data.execution.entry_timing,)


def _read_exit_timing(config: StrategyConfig) -> tuple[str, ...]:
    return (config.data.execution.exit_timing,)


def _read_formula_type(config: StrategyConfig) -> tuple[str, ...]:
    sizing = config.position_sizing
    if sizing.method != "formula_based_sizing" or sizing.formula_based is None:
        return ()
    return (sizing.formula_based.formula_type,)


def _read_leverage_mode(config: StrategyConfig) -> tuple[str, ...]:
    return (config.position_sizing.leverage_mode,)


def _read_signal_strength(config: StrategyConfig) -> tuple[str, ...]:
    return (config.position_sizing.signal_strength_adjustment,)


def _read_partial_aftermath(config: StrategyConfig) -> tuple[str, ...]:
    """A full close leaves no remainder, so the aftermath is unreachable — mirrors
    ``partial_close_is_modelled``'s ``close_percentage >= 100`` short circuit."""
    exit_logic = config.position_exit_logic
    if exit_logic.close_percentage >= 100:
        return ()
    return (exit_logic.partial_aftermath,)


def _read_scaling_method(config: StrategyConfig) -> tuple[str, ...]:
    scaling = config.scaling_logic
    if scaling is None or not scaling.enabled or scaling.method is None:
        return ()
    return (scaling.method,)


def _read_scaling_timeframe_mode(config: StrategyConfig) -> tuple[str, ...]:
    scaling = config.scaling_logic
    if scaling is None or not scaling.enabled:
        return ()
    return (scaling.timeframe_mode,)


def _read_scaling_timeframe(config: StrategyConfig) -> tuple[str, ...]:
    scaling = config.scaling_logic
    if scaling is None or not scaling.enabled:
        return ()
    return (scaling.timeframe,)


def _read_filter_types(config: StrategyConfig) -> tuple[str, ...]:
    """Only ENABLED filters are engine rules (the disabled-child convention)."""
    return tuple(rf.filter_type for rf in config.restrictions_filters.filters if rf.enabled)


def _read_opposite_hedge(config: StrategyConfig) -> tuple[str, ...]:
    """``exit_on_opposite_signal`` ON closes the position before the hedge branch is
    reached, so the saved hedge value is inert and NOT a selection — exactly the rule
    ``conflict_handling_is_modelled`` applies, kept identical on purpose."""
    conflict = config.conflict_position_handling
    if conflict.exit_on_opposite_signal:
        return ()
    return (str(conflict.opposite_direction_hedge),)


_FIELD_READERS: dict[str, Callable[[StrategyConfig], tuple[str, ...]]] = {
    "data.costs.slippage_mode": _read_slippage_mode,
    "data.order_config.limit.price_rule": _read_limit_price_rule,
    "data.order_config.limit.partial_fill_policy": _read_limit_partial_fill,
    "data.execution.entry_timing": _read_entry_timing,
    "data.execution.exit_timing": _read_exit_timing,
    "position_sizing.formula_based.formula_type": _read_formula_type,
    "position_sizing.leverage_mode": _read_leverage_mode,
    "position_sizing.signal_strength_adjustment": _read_signal_strength,
    "position_exit_logic.partial_aftermath": _read_partial_aftermath,
    "scaling_logic.method": _read_scaling_method,
    "scaling_logic.timeframe": _read_scaling_timeframe,
    "scaling_logic.timeframe_mode": _read_scaling_timeframe_mode,
    "restrictions_filters.filters.filter_type": _read_filter_types,
    "conflict_position_handling.opposite_direction_hedge": _read_opposite_hedge,
}

_BY_FIELD_VALUE: dict[tuple[str, str], CapabilityOption] = {
    (option.field_path, option.value): option for option in CAPABILITY_MATRIX
}

FUTURE_DEV_OPTIONS: tuple[CapabilityOption, ...] = tuple(
    option for option in CAPABILITY_MATRIX if option.status == "future_dev"
)

MATRIX_FIELD_PATHS: tuple[str, ...] = tuple(dict.fromkeys(o.field_path for o in CAPABILITY_MATRIX))


def option_status(field_path: str, value: str) -> CapabilityStatus | None:
    """The matrix status of one option value, or ``None`` when unenumerated.

    ``None`` means "this value is not a capability decision" — either the field is
    absent from the matrix (every value executes identically) or the value is not a
    known literal. Callers must treat ``None`` as NOT ``future_dev``: the matrix
    enumerates what is gated, never what is permitted."""
    option = _BY_FIELD_VALUE.get((field_path, value))
    return option.status if option is not None else None


def future_dev_selections(config: StrategyConfig) -> tuple[CapabilityOption, ...]:
    """Every ``future_dev`` option this saved strategy actually selects.

    Deterministic and stable in :data:`CAPABILITY_MATRIX` order so the Ready Check
    message and the engine diagnostics warning are reproducible. Empty tuple = the
    strategy selects only options this build executes."""
    selected: list[CapabilityOption] = []
    for field_path, reader in _FIELD_READERS.items():
        for value in reader(config):
            option = _BY_FIELD_VALUE.get((field_path, value))
            if option is not None and option.status == "future_dev":
                selected.append(option)
    order = {(o.field_path, o.value): i for i, o in enumerate(CAPABILITY_MATRIX)}
    return tuple(sorted(selected, key=lambda o: order[(o.field_path, o.value)]))


def capabilities_are_modelled(config: StrategyConfig) -> bool:
    """Public predicate: does this strategy select ONLY options this build executes?

    The matrix-driven fail-closed gate shared by the engine and Ready Check (F-05).
    It sits ALONGSIDE the nine per-domain ``*_is_modelled`` predicates rather than
    replacing them: this one enumerates per option VALUE (so a UI and a parity test
    can read it), while those keep catching the misconfiguration cases a value-level
    table cannot express (a missing ``trigger_offset``, a non-positive cap, an
    unparseable filter config)."""
    return not future_dev_selections(config)


__all__ = [
    "CAPABILITY_MATRIX",
    "FUTURE_DEV_OPTIONS",
    "MATRIX_FIELD_PATHS",
    "CapabilityOption",
    "CapabilityStatus",
    "capabilities_are_modelled",
    "future_dev_selections",
    "option_status",
]
