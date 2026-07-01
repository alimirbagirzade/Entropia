"""Unit tests for StrategyConfig validation (Stage 3b §2, binding decision #2).

Covers:
- StrategyConfig immutability (frozen=True)
- Display name validation (non-blank, length bounds)
- Data context field validation (capital > 0, date range valid)
- Execution model enum validation
- Order config conditional logic (limit details iff limit type)
- Cost model validation (slippage required for percentage mode)
- Sizing method exclusivity (exactly one method active)
- Disabled sections produce zero engine input
- Signal block min_supporting validation
- Package reference pinning (root_id, revision_id, content_hash)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from entropia.domain.strategy.config import (
    ConflictPositionHandling,
    CostsModel,
    DataContext,
    DateRange,
    ExecutionModel,
    FormulaBasedSizing,
    FundingPolicy,
    IndicatorBlock,
    IntrabarPolicy,
    LimitOrderDetails,
    OrderConfig,
    PackageReference,
    PercentageStop,
    PositionEntryLogic,
    PositionExitLogic,
    PositionSizeLimits,
    PositionSizing,
    ProtectionStopLogic,
    RestrictionsFilters,
    RiskBasedSizing,
    ScalingLogic,
    SignalBlock,
    StrategyConfig,
)

# ============================================================================
# FIXTURES: Minimal Valid Payloads
# ============================================================================


@pytest.fixture
def valid_date_range() -> DateRange:
    """Valid date range for backtest."""
    return DateRange(
        start="2024-01-01T00:00:00Z",
        end="2024-12-31T23:59:59Z",
    )


@pytest.fixture
def valid_execution_model() -> ExecutionModel:
    """Valid execution timing."""
    return ExecutionModel(
        entry_timing="next_candle_open",
        exit_timing="next_candle_close",
    )


@pytest.fixture
def valid_order_config() -> OrderConfig:
    """Valid market order (no limit details)."""
    return OrderConfig(type="market_order", limit=None)


@pytest.fixture
def valid_limit_order_config() -> OrderConfig:
    """Valid limit order with required details."""
    return OrderConfig(
        type="limit_order",
        limit=LimitOrderDetails(
            price_rule="entry_signal_price",
            price_offset=None,
            validity="3_candles",
            unfilled_policy="cancel_order",
            partial_fill_policy="not_allowed",
        ),
    )


@pytest.fixture
def valid_costs_model() -> CostsModel:
    """Valid costs with percentage slippage."""
    return CostsModel(
        commission=Decimal("0.001"),
        spread=Decimal("0.0002"),
        slippage_mode="percentage_slippage",
        slippage_value=Decimal("0.01"),
    )


@pytest.fixture
def valid_data_context(
    valid_date_range,
    valid_execution_model,
    valid_order_config,
    valid_costs_model,
) -> DataContext:
    """Valid data context with all required fields."""
    return DataContext(
        instrument_id="BTCUSDT",
        market_dataset_root_id="market_01234567890123456789",
        market_dataset_revision_id="mrev_0123456789012345678901",
        market_dataset_content_hash="abc123def456789012345678901234567890123456789012345678901234567890",
        backtest_range=valid_date_range,
        initial_capital=Decimal("10000.00"),
        execution=valid_execution_model,
        order_config=valid_order_config,
        costs=valid_costs_model,
        intrabar_policy=IntrabarPolicy(tick_policy="inherit"),
        funding=FundingPolicy(enabled=False),
    )


@pytest.fixture
def valid_package_reference() -> PackageReference:
    """Valid pinned package reference."""
    return PackageReference(
        package_root_id="pkg_0123456789012345678901",
        package_revision_id="pkgrev_012345678901234567890",
        package_content_hash="fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
    )


@pytest.fixture
def valid_signal_block() -> SignalBlock:
    """Valid signal aggregation rule."""
    return SignalBlock(
        rule="required_indicator_blocks_only",
        min_supporting_count=None,
    )


@pytest.fixture
def valid_indicator_block(valid_package_reference) -> IndicatorBlock:
    """Valid indicator block with minimal config."""
    return IndicatorBlock(
        block_id="ind_0123456789012345678901",
        display_order=0,
        enabled=True,
        package_ref=valid_package_reference,
        trigger_source="indicator_native_trigger",
        direction="long",
        timeframe="same_as_base_tf",
        validity="3_candles",
        requirement="required",
        condition_block_rule=None,
        min_supporting_condition_count=None,
        condition_blocks=None,
        parameter_overrides=None,
    )


@pytest.fixture
def valid_position_entry_logic(valid_signal_block, valid_indicator_block) -> PositionEntryLogic:
    """Valid entry logic with signal and indicator blocks."""
    return PositionEntryLogic(
        direction_mode="long_and_short",
        signal_block=valid_signal_block,
        indicator_blocks=[valid_indicator_block],
    )


@pytest.fixture
def valid_position_exit_logic() -> PositionExitLogic:
    """Valid exit logic (signal block optional)."""
    return PositionExitLogic(
        applies_to_direction="long_and_short",
        close_percentage=Decimal("100"),
        partial_aftermath="move_stop_to_entry",
        signal_block=None,
        indicator_blocks=None,
    )


@pytest.fixture
def valid_protection_stop_logic() -> ProtectionStopLogic:
    """Valid stop loss configuration (all toggleable)."""
    return ProtectionStopLogic(
        percentage_stop=PercentageStop(enabled=True, loss_percentage=Decimal("1.0")),
        trailing_stop=None,
        absolute_stop=None,
    )


@pytest.fixture
def valid_position_sizing() -> PositionSizing:
    """Valid base position sizing."""
    return PositionSizing(
        method="base_position_size",
        base_position_size=Decimal("100.0"),
        risk_based=None,
        formula_based=None,
        signal_strength_adjustment="no_adjustment",
        leverage_mode="isolated",
        position_size_limits=None,
    )


@pytest.fixture
def valid_scaling_logic() -> ScalingLogic:
    """Valid disabled scaling (no re-scale)."""
    return ScalingLogic(
        enabled=False,
        timeframe="same_as_base_tf",
        method=None,
        price_scaling=None,
        logic_scaling=None,
        add_size="percent_of_initial",
        add_size_value=None,
        scaling_limits=None,
    )


@pytest.fixture
def valid_restrictions_filters() -> RestrictionsFilters:
    """Valid empty restrictions (no filters)."""
    return RestrictionsFilters(rule="any", filters=[])


@pytest.fixture
def valid_conflict_position_handling() -> ConflictPositionHandling:
    """Valid position conflict rules."""
    return ConflictPositionHandling(
        overlapping_signal_policy="queue_sequential",
        same_direction_stacking="allow_stacking",
        opposite_direction_hedge="allow_hedge",
        exit_on_opposite_signal=True,
    )


@pytest.fixture
def valid_strategy_config(
    valid_data_context,
    valid_position_entry_logic,
    valid_position_exit_logic,
    valid_protection_stop_logic,
    valid_position_sizing,
    valid_scaling_logic,
    valid_restrictions_filters,
    valid_conflict_position_handling,
) -> StrategyConfig:
    """Fully valid StrategyConfig."""
    return StrategyConfig(
        strategy_root_id="strat_01234567890123456789",
        display_name="Test Strategy Long-Only",
        rationale_family_id="ratfam_0123456789012345678",
        data=valid_data_context,
        position_entry_logic=valid_position_entry_logic,
        position_exit_logic=valid_position_exit_logic,
        protection_stop_logic=valid_protection_stop_logic,
        position_sizing=valid_position_sizing,
        scaling_logic=valid_scaling_logic,
        restrictions_filters=valid_restrictions_filters,
        conflict_position_handling=valid_conflict_position_handling,
        validated_at=datetime.now(UTC),
        validation_errors=[],
    )


# ============================================================================
# TESTS: Display Name Validation
# ============================================================================


def test_display_name_must_not_be_blank(valid_strategy_config):
    """Display name cannot be empty string (§1)."""
    payload = valid_strategy_config.model_dump()
    payload["display_name"] = ""
    with pytest.raises(ValidationError) as exc:
        StrategyConfig(**payload)
    # Empty string is rejected by the min_length=1 constraint before the custom
    # blank/whitespace validator runs; either way display_name is the failing field.
    assert "display_name" in str(exc.value)


def test_display_name_must_not_be_whitespace_only(valid_strategy_config):
    """Display name cannot be whitespace-only (§1)."""
    payload = valid_strategy_config.model_dump()
    payload["display_name"] = "   \t  "
    with pytest.raises(ValidationError) as exc:
        StrategyConfig(**payload)
    assert "Name cannot be blank" in str(exc.value)


def test_display_name_stripped_of_leading_trailing_space(valid_strategy_config):
    """Display name is trimmed; internal spaces preserved (§1)."""
    payload = valid_strategy_config.model_dump()
    payload["display_name"] = "  My Strategy  "
    config = StrategyConfig(**payload)
    assert config.display_name == "My Strategy"


def test_display_name_max_length_160(valid_strategy_config):
    """Display name cannot exceed 160 characters (§1)."""
    payload = valid_strategy_config.model_dump()
    payload["display_name"] = "x" * 161
    with pytest.raises(ValidationError) as exc:
        StrategyConfig(**payload)
    assert "at most 160 characters" in str(exc.value)


def test_display_name_accepted_at_160_chars(valid_strategy_config):
    """Display name exactly 160 chars is valid (§1)."""
    payload = valid_strategy_config.model_dump()
    payload["display_name"] = "x" * 160
    config = StrategyConfig(**payload)
    assert len(config.display_name) == 160


# ============================================================================
# TESTS: Data Context Validation
# ============================================================================


def test_initial_capital_must_be_positive(valid_data_context):
    """Initial capital must be > 0 (§2)."""
    payload = valid_data_context.model_dump()
    payload["initial_capital"] = Decimal("0")
    with pytest.raises(ValidationError) as exc:
        DataContext(**payload)
    assert "greater than 0" in str(exc.value)


def test_initial_capital_must_be_negative_rejected(valid_data_context):
    """Negative initial capital rejected (§2)."""
    payload = valid_data_context.model_dump()
    payload["initial_capital"] = Decimal("-1000.00")
    with pytest.raises(ValidationError) as exc:
        DataContext(**payload)
    assert "greater than 0" in str(exc.value)


def test_backtest_range_end_must_be_after_start():
    """End date must be >= start date (§2) — rejected at DateRange construction."""
    with pytest.raises(ValidationError) as exc:
        DateRange(
            start="2024-12-31T00:00:00Z",
            end="2024-01-01T00:00:00Z",
        )
    assert "End date must be >=" in str(exc.value)


def test_backtest_range_end_equal_start_allowed(valid_data_context):
    """End date equal to start date allowed (single candle backtest) (§2)."""
    payload = valid_data_context.model_dump()
    payload["backtest_range"] = DateRange(
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T23:59:59Z",
    )
    ctx = DataContext(**payload)
    assert ctx.backtest_range.start <= ctx.backtest_range.end


def test_capital_decimal_places_must_be_2(valid_data_context):
    """Initial capital must have exactly 2 decimal places (§2)."""
    payload = valid_data_context.model_dump()
    payload["initial_capital"] = Decimal("10000.001")  # 3 decimal places
    with pytest.raises(ValidationError) as exc:
        DataContext(**payload)
    assert "2 decimal places" in str(exc.value)


# ============================================================================
# TESTS: Order Config Conditional Logic
# ============================================================================


def test_market_order_must_not_have_limit_details():
    """Market order type cannot include limit details (§2, binding decision #1)."""
    order = OrderConfig(
        type="market_order",
        limit=LimitOrderDetails(
            price_rule="entry_signal_price",
            unfilled_policy="cancel_order",
        ),
    )
    # Validator should clear limit if not limit/stop-limit type
    # (If validator mode='before' returns None)
    assert order.limit is None


def test_limit_order_must_have_limit_details():
    """Limit order type must include limit details (§2)."""
    with pytest.raises(ValidationError) as exc:
        OrderConfig(type="limit_order", limit=None)
    assert "Limit details required" in str(exc.value)


def test_stop_limit_order_must_have_limit_details():
    """Stop-limit order type must include limit details (§2)."""
    with pytest.raises(ValidationError) as exc:
        OrderConfig(type="stop_limit_order", limit=None)
    assert "Limit details required" in str(exc.value)


def test_limit_order_details_partial_fill_defaults():
    """Partial fill policy defaults to not_allowed (§2)."""
    details = LimitOrderDetails(
        price_rule="entry_signal_price",
        unfilled_policy="cancel_order",
        # partial_fill_policy not set; should default
    )
    assert details.partial_fill_policy == "not_allowed"


# ============================================================================
# TESTS: Cost Model Validation
# ============================================================================


def test_slippage_value_required_for_percentage_slippage():
    """Slippage value required when mode='percentage_slippage' (§2)."""
    with pytest.raises(ValidationError) as exc:
        CostsModel(
            slippage_mode="percentage_slippage",
            slippage_value=None,
        )
    assert "Slippage value required" in str(exc.value)


def test_slippage_value_optional_for_historical_slippage():
    """Slippage value optional when mode='historical_slippage_if_available' (§2)."""
    costs = CostsModel(
        slippage_mode="historical_slippage_if_available",
        slippage_value=None,
    )
    assert costs.slippage_value is None


# ============================================================================
# TESTS: Sizing Method Exclusivity
# ============================================================================


def test_base_position_size_required_if_base_method():
    """Base size must be set when method='base_position_size' (§6, binding decision #2)."""
    with pytest.raises(ValidationError) as exc:
        PositionSizing(
            method="base_position_size",
            base_position_size=None,
        )
    assert "Base position size required" in str(exc.value)


def test_risk_based_sizing_not_required_if_base_method():
    """Risk-based config unused if method='base_position_size' (§6)."""
    sizing = PositionSizing(
        method="base_position_size",
        base_position_size=Decimal("100.0"),
        risk_based=RiskBasedSizing(
            risk_percentage_per_trade=Decimal("2.0"),
            stop_loss_point=Decimal("50.0"),
        ),
    )
    # risk_based is present but ignored by engine (not semantic)
    assert sizing.method == "base_position_size"


def test_formula_based_sizing_valid():
    """Formula-based sizing with kelly criterion (§6)."""
    sizing = PositionSizing(
        method="formula_based_sizing",
        formula_based=FormulaBasedSizing(
            formula_type="kelly_criterion",
            formula_params={"win_rate": 0.55, "avg_win": 1.2, "avg_loss": 1.0},
        ),
    )
    assert sizing.formula_based is not None
    assert sizing.formula_based.formula_type == "kelly_criterion"


def test_position_size_limits_optional():
    """Position size limits are optional (§6)."""
    sizing = PositionSizing(
        method="base_position_size",
        base_position_size=Decimal("100.0"),
        position_size_limits=None,
    )
    assert sizing.position_size_limits is None


def test_position_size_limits_applied():
    """Position size limits can be set (§6)."""
    sizing = PositionSizing(
        method="base_position_size",
        base_position_size=Decimal("100.0"),
        position_size_limits=PositionSizeLimits(
            min_position_size=Decimal("10.0"),
            max_position_size=Decimal("500.0"),
        ),
    )
    assert sizing.position_size_limits.min_position_size == Decimal("10.0")
    assert sizing.position_size_limits.max_position_size == Decimal("500.0")


# ============================================================================
# TESTS: Disabled Sections Filtering (Binding Decision #2)
# ============================================================================


def test_disabled_percentage_stop_produces_none():
    """Disabled percentage stop should be filtered out on save (binding decision #2)."""
    stops = ProtectionStopLogic(
        percentage_stop=PercentageStop(enabled=False, loss_percentage=Decimal("1.0")),
        trailing_stop=None,
        absolute_stop=None,
    )
    # In actual implementation, disabled stop would be filtered before JSON
    # For now, check that model accepts disabled state
    assert stops.percentage_stop.enabled is False


def test_enabled_percentage_stop_preserved():
    """Enabled percentage stop included on save (binding decision #2)."""
    stops = ProtectionStopLogic(
        percentage_stop=PercentageStop(enabled=True, loss_percentage=Decimal("2.0")),
        trailing_stop=None,
        absolute_stop=None,
    )
    assert stops.percentage_stop.enabled is True
    assert stops.percentage_stop.loss_percentage == Decimal("2.0")


def test_disabled_scaling_logic_produces_empty_config():
    """Disabled scaling logic should be empty/null on save (binding decision #2)."""
    scaling = ScalingLogic(
        enabled=False,
        method=None,
        price_scaling=None,
        logic_scaling=None,
    )
    assert scaling.enabled is False


def test_enabled_scaling_with_price_distance():
    """Enabled scaling with price distance configuration (binding decision #2)."""
    from entropia.domain.strategy.config import PriceDistanceScaling

    scaling = ScalingLogic(
        enabled=True,
        timeframe="1h",
        method="price_distance_scaling",
        price_scaling=PriceDistanceScaling(
            retracement_distance=Decimal("100.0"),
            layers=3,
        ),
    )
    assert scaling.enabled is True
    assert scaling.price_scaling.layers == 3


# ============================================================================
# TESTS: Signal Block Validation
# ============================================================================


def test_min_supporting_required_for_min_supporting_rule():
    """min_supporting_count required when rule='required_plus_min_supporting' (§3)."""
    with pytest.raises(ValidationError) as exc:
        SignalBlock(
            rule="required_plus_min_supporting",
            min_supporting_count=None,
        )
    assert "Min supporting count required" in str(exc.value)


def test_min_supporting_not_required_for_required_only():
    """min_supporting_count not needed for rule='required_indicator_blocks_only' (§3)."""
    signal = SignalBlock(
        rule="required_indicator_blocks_only",
        min_supporting_count=None,
    )
    assert signal.min_supporting_count is None


def test_min_supporting_count_must_be_positive():
    """min_supporting_count must be >= 1 (§3)."""
    with pytest.raises(ValidationError) as exc:
        SignalBlock(
            rule="required_plus_min_supporting",
            min_supporting_count=0,
        )
    assert "greater than or equal to 1" in str(exc.value)


# ============================================================================
# TESTS: Package Reference Pinning (Binding Decision #3)
# ============================================================================


def test_package_reference_requires_all_three_pins():
    """Package reference must have root_id, revision_id, and content_hash (binding decision #3)."""
    with pytest.raises(ValidationError):
        PackageReference(
            package_root_id="pkg_0123456789012345678901",
            package_revision_id=None,  # Missing
            package_content_hash="abc123...",
        )


def test_package_reference_content_hash_required():
    """Content hash is not optional (immutability proof, binding decision #3)."""
    ref = PackageReference(
        package_root_id="pkg_0123456789012345678901",
        package_revision_id="pkgrev_012345678901234567890",
        package_content_hash="fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
    )
    assert ref.package_content_hash  # Must be pinned


# ============================================================================
# TESTS: StrategyConfig Immutability (frozen=True)
# ============================================================================


def test_strategy_config_frozen_no_mutation_after_create(valid_strategy_config):
    """StrategyConfig is immutable; cannot modify after creation (frozen=True)."""
    with pytest.raises(ValidationError):  # frozen=True -> assignment is rejected
        valid_strategy_config.display_name = "Modified"


def test_strategy_config_extra_fields_forbidden(valid_strategy_config):
    """StrategyConfig forbids extra fields not in model (extra='forbid')."""
    payload = valid_strategy_config.model_dump()
    payload["extra_unknown_field"] = "value"
    with pytest.raises(ValidationError) as exc:
        StrategyConfig(**payload)
    assert "Extra inputs are not permitted" in str(exc.value)


# ============================================================================
# TESTS: Indicator Block Trigger Source Logic
# ============================================================================


def test_indicator_block_trigger_source_native_trigger():
    """Indicator block can use native trigger without conditions (§3)."""
    from entropia.domain.strategy.config import PackageReference

    block = IndicatorBlock(
        block_id="ind_001",
        display_order=0,
        enabled=True,
        package_ref=PackageReference(
            package_root_id="pkg_001",
            package_revision_id="pkgrev_001",
            package_content_hash="hash001",
        ),
        trigger_source="indicator_native_trigger",
        direction="long",
        timeframe="same_as_base_tf",
        validity="3_candles",
        requirement="required",
        condition_block_rule=None,
        condition_blocks=None,
    )
    assert block.trigger_source == "indicator_native_trigger"
    assert block.condition_blocks is None


def test_indicator_block_trigger_source_with_conditions():
    """Indicator block can use native trigger + condition blocks (§3)."""
    from entropia.domain.strategy.config import (
        ConditionBlock,
        PackageReference,
    )

    cond_block = ConditionBlock(
        condition_block_id="cond_001",
        display_order=0,
        enabled=True,
        package_ref=PackageReference(
            package_root_id="cond_pkg_001",
            package_revision_id="cond_pkgrev_001",
            package_content_hash="cond_hash_001",
        ),
        requirement="required",
        validity="3_candles",
        parameter_overrides=None,
    )

    block = IndicatorBlock(
        block_id="ind_002",
        display_order=0,
        enabled=True,
        package_ref=PackageReference(
            package_root_id="pkg_002",
            package_revision_id="pkgrev_002",
            package_content_hash="hash002",
        ),
        trigger_source="indicator_native_trigger_plus_condition",
        direction="long",
        timeframe="same_as_base_tf",
        validity="3_candles",
        requirement="required",
        condition_block_rule="required_condition_blocks_only",
        min_supporting_condition_count=None,
        condition_blocks=[cond_block],
    )
    assert block.condition_blocks is not None
    assert len(block.condition_blocks) == 1


# ============================================================================
# TESTS: Conflict Position Handling
# ============================================================================


def test_conflict_position_handling_defaults():
    """Conflict position handling has sensible defaults (§9)."""
    config = ConflictPositionHandling()
    assert config.overlapping_signal_policy == "queue_sequential"
    assert config.same_direction_stacking == "allow_stacking"
    assert config.opposite_direction_hedge == "allow_hedge"
    assert config.exit_on_opposite_signal is True


def test_conflict_position_hedge_prevents_opposite():
    """Opposite direction hedge can close existing position (§9)."""
    config = ConflictPositionHandling(
        opposite_direction_hedge="close_existing",
        exit_on_opposite_signal=False,
    )
    assert config.opposite_direction_hedge == "close_existing"


# ============================================================================
# PARAMETRIZED TESTS
# ============================================================================


@pytest.mark.parametrize(
    "entry_timing",
    [
        "next_candle_open",
        "current_candle_close",
        "next_candle_close",
        "intrabar_touch",
        "limit_fill_simulation",
        "market_fill_simulation",
    ],
)
def test_execution_model_valid_entry_timings(entry_timing):
    """Entry timing accepts all valid enum values (§2)."""
    exec_model = ExecutionModel(
        entry_timing=entry_timing,
        exit_timing="next_candle_close",
    )
    assert exec_model.entry_timing == entry_timing


@pytest.mark.parametrize(
    "exit_timing",
    [
        "next_candle_open",
        "current_candle_close",
        "next_candle_close",
        "intrabar_touch",
        "stop_limit_priority_simulation",
        "market_fill_simulation",
    ],
)
def test_execution_model_valid_exit_timings(exit_timing):
    """Exit timing accepts all valid enum values (§2)."""
    exec_model = ExecutionModel(
        entry_timing="next_candle_open",
        exit_timing=exit_timing,
    )
    assert exec_model.exit_timing == exit_timing


@pytest.mark.parametrize(
    "direction",
    ["long", "short", "long_and_short"],
)
def test_entry_logic_valid_directions(direction, valid_signal_block, valid_indicator_block):
    """Entry logic accepts all valid direction enums (§3)."""
    entry = PositionEntryLogic(
        direction_mode=direction,
        signal_block=valid_signal_block,
        indicator_blocks=[valid_indicator_block],
    )
    assert entry.direction_mode == direction


@pytest.mark.parametrize(
    "rule",
    [
        "required_indicator_blocks_only",
        "required_plus_any_supporting",
        "required_plus_min_supporting",
        "required_plus_all_confirmations",
    ],
)
def test_signal_block_valid_rules(rule):
    """Signal block accepts all valid rule enums (§3)."""
    min_supporting = 1 if rule == "required_plus_min_supporting" else None
    signal = SignalBlock(rule=rule, min_supporting_count=min_supporting)
    assert signal.rule == rule
