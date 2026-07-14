"""StrategyConfig Pydantic model (Stage 3b, §2; spec §9.2).

Frozen immutable model with deterministic JSON serialization (for content_hash).
Sections 1-9 map to spec doc 02. Disabled sections omitted on save (Binding Decision #2).

Field validators enforce:
- Name is non-blank (§1)
- Dates: end ≥ start (§2)
- Order config: limit details present iff type is limit/stop-limit (§2)
- Signal block: min_supporting_count required for min_supporting rule (§3)
- Sizing: base_position_size required iff method='base_position_size' (§6)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

# ============================================================================
# SECTION 1: Strategy Context
# ============================================================================


class StrategyConfig(BaseModel):
    """Immutable strategy contract pinned by revision (spec §9.2)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        use_enum_values=True,  # Store enum values, not names
    )

    # ========== Identity & Metadata ==========
    strategy_root_id: str = Field(..., description="ULID, links to entity_registry")
    display_name: str = Field(..., min_length=1, max_length=160, description="Human-readable name")
    rationale_family_id: str = Field(..., description="Active/accessible rationale family ULID")

    # ========== Data Context (Section 2) ==========
    data: DataContext = Field(...)

    # ========== Decision Logic (Sections 3-4) ==========
    position_entry_logic: PositionEntryLogic = Field(...)
    position_exit_logic: PositionExitLogic = Field(...)

    # ========== Risk Management (Sections 5-9) ==========
    # protection_stop_logic / scaling_logic are Optional: when every stop is
    # disabled (or scaling.enabled=false) the disabled-section filter collapses the
    # whole subtree to None before parsing (Binding Decision #2), so None must be a
    # legal value for the saved revision.
    protection_stop_logic: ProtectionStopLogic | None = Field(default=None)
    position_sizing: PositionSizing = Field(...)
    scaling_logic: ScalingLogic | None = Field(default=None)
    restrictions_filters: RestrictionsFilters = Field(...)
    conflict_position_handling: ConflictPositionHandling = Field(...)

    # ========== Validation & Provenance ==========
    validated_at: datetime | None = Field(None, description="Last validation pass")
    validation_errors: list[str] = Field(
        default_factory=list, description="Validation error messages"
    )

    @field_validator("display_name")
    @classmethod
    def validate_name_not_control(cls, v: str) -> str:
        """Ensure name is non-blank."""
        v = v.strip()
        if not v or v.isspace():
            raise ValueError("Name cannot be blank or control-only")
        return v


# ============================================================================
# SECTION 2: Data & Execution Context
# ============================================================================


class DataContextInstrumentScope(BaseModel):
    """Free-text instrument scope resolved to a canonical instrument (GAP-16; Master §8.1).

    When present, ``save_strategy_revision`` resolves this scope through the registry
    and rewrites ``DataContext.instrument_id`` to the canonical ``instrument_id`` — an
    unresolvable scope fails closed (422) so a strategy can no longer conflate
    BTCUSDT spot with BTCUSDT perpetual. A caller provides either an ``alias`` (display
    text) or a ``venue_id``/``symbol``/``contract_type`` triple.
    """

    venue_id: str | None = Field(default=None)
    symbol: str | None = Field(default=None)
    contract_type: str | None = Field(default=None)
    alias: str | None = Field(default=None)


class DataContext(BaseModel):
    """Data source, execution assumptions, capital base (§2)."""

    instrument_id: str = Field(..., description="e.g., 'BTCUSDT'")
    # GAP-16 (Master §8.1): optional free-text scope resolved server-side at save to
    # the canonical instrument_id above; unresolvable -> 422 (never a silent free-text).
    instrument_scope: DataContextInstrumentScope | None = Field(default=None)
    market_dataset_root_id: str = Field(..., description="Market data ULID")
    market_dataset_revision_id: str = Field(..., description="Pinned revision")
    market_dataset_content_hash: str = Field(..., description="SHA-256 hash")

    backtest_range: DateRange = Field(...)
    initial_capital: Decimal = Field(
        ..., gt=Decimal("0"), decimal_places=2, description="Starting capital"
    )

    execution: ExecutionModel = Field(...)
    order_config: OrderConfig = Field(...)
    costs: CostsModel = Field(...)
    intrabar_policy: IntrabarPolicy = Field(...)
    funding: FundingPolicy = Field(...)

    @field_validator("initial_capital")
    @classmethod
    def validate_finite_capital(cls, v: Decimal) -> Decimal:
        """Ensure capital is finite."""
        if not v.is_finite():
            raise ValueError("Initial capital must be finite")
        return v


class DateRange(BaseModel):
    """Backtest date window."""

    start: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}T", description="ISO 8601 timestamp")
    end: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}T", description="ISO 8601 timestamp")

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: str, info: ValidationInfo) -> str:
        """Enforce end >= start."""
        if info.data.get("start") and v < info.data["start"]:
            raise ValueError("End date must be >= start date")
        return v


class ExecutionModel(BaseModel):
    """Execution timing determinism (§2)."""

    entry_timing: Literal[
        "next_candle_open",
        "current_candle_close",
        "next_candle_close",
        "intrabar_touch",
        "limit_fill_simulation",
        "market_fill_simulation",
    ] = Field(..., description="When entry orders fill")

    exit_timing: Literal[
        "next_candle_open",
        "current_candle_close",
        "next_candle_close",
        "intrabar_touch",
        "stop_limit_priority_simulation",
        "market_fill_simulation",
    ] = Field(..., description="When exit orders fill")


class OrderConfig(BaseModel):
    """Order type enum + conditional limit details (§2)."""

    type: Literal[
        "market_order",
        "limit_order",
        "stop_order",
        "stop_limit_order",
        "simulation_only",
    ] = Field(default="market_order", description="Order execution mode")

    limit: LimitOrderDetails | None = Field(
        default=None, description="Limit details (required iff type is limit/stop-limit)"
    )

    @field_validator("limit", mode="before")
    @classmethod
    def limit_required_if_limit_type(cls, v: Any, info: ValidationInfo) -> Any:
        """Validate limit details presence."""
        order_type = info.data.get("type")
        if order_type in ("limit_order", "stop_limit_order"):
            if v is None:
                raise ValueError("Limit details required for limit/stop-limit orders")
        elif v is not None:
            return None
        return v


class LimitOrderDetails(BaseModel):
    """Limit order parameters (visible only if order_config.type in limit/stop-limit)."""

    price_rule: Literal[
        "entry_signal_price",
        "best_bid_ask",
        "signal_price_minus_offset",
        "signal_price_plus_offset",
    ] = Field(..., description="Price determination rule")

    price_offset: Decimal | None = Field(default=None, description="Offset from rule price")

    validity: Literal[
        "current_candle_only",
        "1_candle",
        "2_candles",
        "3_candles",
        "4_candles",
        "until_cancelled",
    ] = Field(default="3_candles", description="Time-in-force")

    unfilled_policy: Literal[
        "cancel_order",
        "keep_until_validity_ends",
        "re_price_next_candle",
        "convert_to_market_order",
    ] = Field(..., description="Unfilled order handling")

    partial_fill_policy: Literal[
        "not_allowed",
        "allowed",
        "minimum_50_percent",
        "fill_remaining_as_market",
        "cancel_remaining",
    ] = Field(default="not_allowed", description="Partial fill behavior")


class CostsModel(BaseModel):
    """Commission, spread, slippage (§2)."""

    commission: Decimal | None = Field(default=None, description="Per-trade fee")
    spread: Decimal | None = Field(default=None, description="Bid-ask spread")

    slippage_mode: Literal["percentage_slippage", "historical_slippage_if_available"] = Field(
        default="percentage_slippage", description="Slippage model"
    )

    slippage_value: Decimal | None = Field(
        default=None, description="Slippage % (required iff mode=percentage)"
    )

    @field_validator("slippage_value", mode="before")
    @classmethod
    def slippage_required_for_percentage(cls, v: Any, info: ValidationInfo) -> Any:
        """Validate slippage value."""
        if info.data.get("slippage_mode") == "percentage_slippage" and v is None:
            raise ValueError("Slippage value required for percentage mode")
        return v


class IntrabarPolicy(BaseModel):
    """Tick data usage (§2)."""

    tick_policy: Literal["inherit", "require", "disable"] = Field(
        default="inherit", description="Tick data policy"
    )


class FundingPolicy(BaseModel):
    """Perpetual/funding fee (optional, market-dependent) (§2)."""

    enabled: bool = Field(default=False, description="Enable funding fees")
    source_root_id: str | None = Field(default=None, description="Funding data source ULID")
    source_revision_id: str | None = Field(default=None, description="Source revision")
    source_content_hash: str | None = Field(default=None, description="Source hash")


# ============================================================================
# SECTIONS 3-4: Entry & Exit Logic
# ============================================================================


class PositionEntryLogic(BaseModel):
    """Entry signal + indicator/condition blocks (§3)."""

    direction_mode: Literal["long", "short", "long_and_short"] = Field(
        default="long_and_short", description="Trade direction bias"
    )

    signal_block: SignalBlock = Field(..., description="Entry signal aggregation rule")
    indicator_blocks: list[IndicatorBlock] = Field(
        ..., min_length=1, description="Entry indicator blocks (≥1)"
    )


class PositionExitLogic(BaseModel):
    """Exit signal + optional exit logic (§4)."""

    applies_to_direction: Literal["long", "short", "long_and_short"] = Field(
        default="long_and_short", description="Which direction this applies to"
    )

    close_percentage: Decimal = Field(
        default=Decimal("100"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="% position to close",
    )

    partial_aftermath: Literal[
        "move_stop_to_entry",
        "trailing_stop",
        "lock_in_profit",
        "close_all",
    ] = Field(default="move_stop_to_entry", description="Post-partial strategy")

    signal_block: SignalBlock | None = Field(
        default=None, description="Exit signal rule (optional)"
    )
    indicator_blocks: list[IndicatorBlock] | None = Field(
        default=None, description="Exit indicator blocks"
    )


class SignalBlock(BaseModel):
    """Entry/exit signal graph aggregation rule (§3, §4)."""

    rule: Literal[
        "required_indicator_blocks_only",
        "required_plus_any_supporting",
        "required_plus_min_supporting",
        "required_plus_all_confirmations",
    ] = Field(..., description="Signal aggregation mode")

    min_supporting_count: int | None = Field(
        default=None,
        ge=1,
        description="Min supporting indicators (required for min_supporting rule)",
    )

    @field_validator("min_supporting_count", mode="before")
    @classmethod
    def min_supporting_required_if_rule(cls, v: Any, info: ValidationInfo) -> Any:
        """Validate min_supporting_count presence."""
        rule = info.data.get("rule")
        if rule == "required_plus_min_supporting" and v is None:
            raise ValueError("Min supporting count required for min_supporting rule")
        elif rule != "required_plus_min_supporting":
            return None
        return v


class IndicatorBlock(BaseModel):
    """Dynamic indicator block with nested condition blocks (§3)."""

    block_id: str = Field(..., description="ULID, stable within draft")
    display_order: int = Field(..., ge=0, description="Display position")
    enabled: bool = Field(default=True, description="Block active")

    package_ref: PackageReference = Field(..., description="Pinned indicator package")

    trigger_source: Literal[
        "indicator_native_trigger",
        "indicator_native_trigger_plus_condition",
        "indicator_output_plus_condition",
    ] = Field(..., description="Signal source type")

    direction: Literal["long", "short", "long_and_short"] = Field(
        default="long_and_short", description="Which directions to signal"
    )

    timeframe: Literal[
        "same_as_base_tf",
        "use_package_default_tf",
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "1D",
    ] = Field(default="same_as_base_tf", description="Timeframe override")

    validity: Literal[
        "current_candle_only",
        "1_candle",
        "2_candles",
        "3_candles",
        "4_candles",
        "until_opposite_signal",
    ] = Field(default="3_candles", description="Signal validity window")

    requirement: Literal["required", "supporting"] = Field(..., description="Aggregation role")

    condition_block_rule: (
        Literal[
            "required_condition_blocks_only",
            "required_plus_any_supporting",
            "required_plus_min_supporting",
            "required_plus_all_supporting",
        ]
        | None
    ) = Field(default=None, description="Nested condition aggregation rule")

    min_supporting_condition_count: int | None = Field(
        default=None, ge=1, description="Min supporting conditions"
    )

    condition_blocks: list[ConditionBlock] | None = Field(
        default=None, description="Nested condition blocks"
    )

    parameter_overrides: dict[str, Any] | None = Field(
        default=None, description="Package parameter overrides"
    )


class ReferenceLeg(BaseModel):
    """One additional reference leg of an N-ary indicator comparison chain (post-V1 (ii)).

    Extends the two-package ``reference_package_ref`` into an ordered chain: the
    condition's source is compared against ``reference_package_ref`` -> ``additional[0]``
    -> ``additional[1]`` ... (e.g. a fast-MA vs slow-MA vs slowest-MA fan). Each leg pins
    its own indicator package, may compute on its own (coarser) timeframe, and carries its
    own parameter overrides (its look-back)."""

    package_ref: PackageReference = Field(..., description="Pinned reference indicator package")

    timeframe: Literal[
        "same_as_base_tf",
        "use_package_default_tf",
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "1D",
    ] = Field(default="same_as_base_tf", description="Reference leg timeframe override")

    parameter_overrides: dict[str, Any] | None = Field(
        default=None, description="Reference leg parameter overrides (e.g. reference_length)"
    )


class ConditionBlock(BaseModel):
    """Condition package block, nested under indicator block (§3)."""

    condition_block_id: str = Field(..., description="ULID")
    display_order: int = Field(..., ge=0, description="Display position")
    enabled: bool = Field(default=True, description="Block active")

    package_ref: PackageReference = Field(..., description="Pinned condition package")

    requirement: Literal["required", "supporting"] = Field(..., description="Aggregation role")

    validity: Literal[
        "current_candle_only",
        "1_candle",
        "2_candles",
        "3_candles",
        "until_opposite_signal",
    ] = Field(default="3_candles", description="Condition validity window")

    reference_package_ref: PackageReference | None = Field(
        default=None,
        description=(
            "Optional 2nd pinned INDICATOR package whose output series is the condition's "
            "right-hand side (two-package indicator-vs-indicator, e.g. fast-MA vs slow-MA). "
            "When set it takes precedence over a constant threshold / bounded reference series."
        ),
    )

    reference_timeframe: Literal[
        "same_as_base_tf",
        "use_package_default_tf",
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "1D",
    ] = Field(
        default="same_as_base_tf",
        description=(
            "Timeframe on which the reference_package_ref RHS series is computed "
            "(per-condition multi-timeframe reference). Only meaningful with a "
            "reference_package_ref; a value strictly COARSER than the parent block's "
            "effective timeframe resamples the RHS (the fast source is compared against "
            "the slower reference, which only advances on a completed reference candle — "
            "no look-ahead). same_as_base_tf keeps the RHS on the block's timeframe."
        ),
    )

    additional_reference_package_refs: list[ReferenceLeg] | None = Field(
        default=None,
        description=(
            "Optional additional reference legs extending reference_package_ref into an "
            "N-ary comparison chain (post-V1 (ii)): the source is compared against the "
            "ordered chain reference_package_ref -> additional[0] -> additional[1] ... "
            "(e.g. fast-MA > slow-MA > slowest-MA). Only meaningful with reference_package_ref."
        ),
    )

    parameter_overrides: dict[str, Any] | None = Field(
        default=None, description="Package parameter overrides"
    )


class PackageReference(BaseModel):
    """Pinned package dependency (never 'latest'; Binding Decision #3) (§3)."""

    package_root_id: str = Field(..., description="Package root ULID")
    package_revision_id: str = Field(..., description="Exact revision ULID")
    package_content_hash: str = Field(..., description="SHA-256 hash (deterministic)")


# ============================================================================
# SECTION 5: Protection / Stop Logic
# ============================================================================


class ProtectionStopLogic(BaseModel):
    """Stop loss rules (all toggleable independently; at least one enables risk control) (§5)."""

    percentage_stop: PercentageStop | None = Field(default=None)
    trailing_stop: TrailingStop | None = Field(default=None)
    absolute_stop: AbsoluteStop | None = Field(default=None)


class PercentageStop(BaseModel):
    """Fixed % stop loss."""

    enabled: bool = Field(default=True)
    loss_percentage: Decimal = Field(
        default=Decimal("1.0"), gt=Decimal("0"), description="Loss % trigger"
    )


class TrailingStop(BaseModel):
    """Dynamic trailing stop."""

    enabled: bool = Field(default=True)
    trail_percentage: Decimal = Field(
        default=Decimal("2.0"), gt=Decimal("0"), description="Trail distance %"
    )
    lock_in_percentage: Decimal = Field(
        default=Decimal("0.8"), ge=Decimal("0"), description="Profit lock % trigger"
    )


class AbsoluteStop(BaseModel):
    """Fixed price stop loss."""

    enabled: bool = Field(default=False)
    absolute_price: Decimal | None = Field(default=None, description="Stop price")


# ============================================================================
# SECTION 6: Position Sizing
# ============================================================================


class PositionSizing(BaseModel):
    """Exactly one sizing method active (§6)."""

    method: Literal[
        "base_position_size",
        "risk_based_sizing",
        "formula_based_sizing",
    ] = Field(default="base_position_size", description="Sizing strategy")

    base_position_size: Decimal | None = Field(
        default=None,
        description="Position size when method=base_position_size (required iff method=base)",
    )
    risk_based: RiskBasedSizing | None = Field(default=None, description="Risk-based sizing")
    formula_based: FormulaBasedSizing | None = Field(
        default=None, description="Formula-based sizing"
    )

    signal_strength_adjustment: Literal[
        "no_adjustment",
        "volatility_adjusted",
        "trend_adjusted",
        "divergence_adjusted",
    ] = Field(default="no_adjustment", description="Size modulation mode")

    leverage_mode: Literal["isolated", "cross"] = Field(
        default="isolated", description="Margin mode"
    )

    position_size_limits: PositionSizeLimits | None = Field(default=None)

    @field_validator("base_position_size", mode="before")
    @classmethod
    def base_size_required_if_base_method(cls, v: Any, info: ValidationInfo) -> Any:
        """Validate base_position_size presence."""
        if info.data.get("method") == "base_position_size" and v is None:
            raise ValueError("Base position size required for base_position_size method")
        return v


class RiskBasedSizing(BaseModel):
    """Risk per trade as % of capital."""

    risk_percentage_per_trade: Decimal = Field(
        ..., gt=Decimal("0"), le=Decimal("100"), description="Risk %"
    )
    stop_loss_point: Decimal = Field(..., gt=Decimal("0"), description="Stop distance")


class FormulaBasedSizing(BaseModel):
    """Formula-based position sizing (e.g., Kelly criterion)."""

    formula_type: Literal["kelly_criterion", "custom_formula"] = Field(...)
    formula_params: dict[str, Any] = Field(default_factory=dict)


class PositionSizeLimits(BaseModel):
    """Global position size caps."""

    min_position_size: Decimal | None = Field(default=None)
    max_position_size: Decimal | None = Field(default=None)


# ============================================================================
# SECTION 7: Scaling Logic
# ============================================================================


class ScalingLogic(BaseModel):
    """Layered entry scaling (optional; entire subtree ignored if enabled=false) (§7)."""

    enabled: bool = Field(default=False, description="Enable scaling")

    timeframe: Literal[
        "same_as_base_tf",
        "use_package_default_tf",
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "1D",
    ] = Field(default="same_as_base_tf", description="Scaling timeframe")

    method: Literal["price_distance_scaling", "logic_based_scaling"] | None = Field(
        default=None, description="Scaling activation method"
    )

    price_scaling: PriceDistanceScaling | None = Field(default=None)
    logic_scaling: LogicBasedScaling | None = Field(default=None)

    add_size: Literal[
        "percent_of_initial",
        "percent_of_current",
        "fixed_amount",
    ] = Field(default="percent_of_initial", description="Add-size reference basis")

    add_size_value: Decimal | None = Field(default=None, description="Add-size value")

    scaling_limits: ScalingLimits | None = Field(default=None)


class PriceDistanceScaling(BaseModel):
    """Scale by price retracement."""

    retracement_distance: Decimal = Field(..., gt=Decimal("0"))
    layers: int = Field(..., ge=1)


class LogicBasedScaling(BaseModel):
    """Scale on additional signal confirmations."""

    indicator_blocks: list[IndicatorBlock] = Field(...)


class ScalingLimits(BaseModel):
    """Scaling caps."""

    max_scaling_layers: int | None = Field(default=None)
    max_total_position_size: Decimal | None = Field(default=None)


# ============================================================================
# SECTION 8: Restrictions / Filters
# ============================================================================


class RestrictionsFilters(BaseModel):
    """Entry eligibility filters (§8)."""

    rule: Literal["any", "all"] = Field(default="any", description="Filter aggregation")
    filters: list[RestrictionFilter] = Field(
        default_factory=list, description="Individual filters (toggleable)"
    )


class RestrictionFilter(BaseModel):
    """Individual filter (each toggleable independently)."""

    filter_type: Literal[
        "volatility_filter",
        "spread_filter",
        "volume_filter",
        "date_blackout_filter",
        "max_daily_loss_filter",
        "consecutive_loss_filter",
        "correlation_filter",
    ] = Field(..., description="Filter category")

    enabled: bool = Field(default=True, description="Filter active")
    filter_id: str = Field(..., description="ULID for track/remove")

    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific config (volatility_threshold, spread_max, etc.)",
    )


# ============================================================================
# SECTION 9: Conflict / Position Handling
# ============================================================================


class ConflictPositionHandling(BaseModel):
    """Multi-signal conflict resolution (§9)."""

    overlapping_signal_policy: Literal[
        "queue_sequential",
        "cancel_pending",
        "merge_signals",
        "ignore_if_active",
    ] = Field(default="queue_sequential", description="Concurrent signal handling")

    same_direction_stacking: Literal[
        "allow_stacking",
        "replace_existing",
        "scale_existing",
        "ignore",
    ] = Field(default="allow_stacking", description="Same-direction multi-position policy")

    opposite_direction_hedge: Literal[
        "allow_hedge",
        "close_existing",
        "ignore",
    ] = Field(default="allow_hedge", description="Hedge/reverse position policy")

    exit_on_opposite_signal: bool = Field(default=True, description="Close on opposite signal")

    # §5.9 "Stop + Exit" — same-bar collision resolution when BOTH a protection stop
    # touches AND an exit signal fires on one bar. V18 default is "Stop Has Priority".
    # Only "exit_has_priority" changes the trade OUTCOME (close at bar.close as an exit
    # rather than at the stop level); "record_both_reasons" executes the stop but emits
    # a collision signal event carrying both reason codes; "first_trigger_wins" resolves
    # to the stop deterministically because the stop is an intrabar high/low touch while
    # the exit signal is close-based (no intrabar ordering data exists to separate them —
    # an honest V1 boundary, so it shares the stop-wins execution and records the reason).
    stop_exit_conflict: Literal[
        "stop_has_priority",
        "exit_has_priority",
        "record_both_reasons",
        "first_trigger_wins",
    ] = Field(
        default="stop_has_priority",
        description="Stop vs exit-signal same-bar collision resolution (§5.9)",
    )
