"""Strategy domain enums (Stage 3b, §3.1).

Lowercase snake_case StrEnum values, stored via enum_column (portable
VARCHAR + CHECK). Reflects sections 1-9 of StrategyConfig structure.
"""

from __future__ import annotations

from enum import StrEnum


class TriggerSourceEnum(StrEnum):
    """Indicator signal graph configuration option (section 3, CR-02)."""

    INDICATOR_NATIVE_TRIGGER = "indicator_native_trigger"
    INDICATOR_NATIVE_TRIGGER_PLUS_CONDITION = "indicator_native_trigger_plus_condition"
    INDICATOR_OUTPUT_PLUS_CONDITION = "indicator_output_plus_condition"


class DirectionModeEnum(StrEnum):
    """Trade direction bias (sections 1, 3, 4; signal_block inheritance)."""

    LONG = "long"
    SHORT = "short"
    LONG_AND_SHORT = "long_and_short"


class ExecutionTimingEnum(StrEnum):
    """Deterministic order entry/exit timing (section 2)."""

    NEXT_CANDLE_OPEN = "next_candle_open"
    CURRENT_CANDLE_CLOSE = "current_candle_close"
    NEXT_CANDLE_CLOSE = "next_candle_close"
    INTRABAR_TOUCH = "intrabar_touch"
    LIMIT_FILL_SIMULATION = "limit_fill_simulation"
    MARKET_FILL_SIMULATION = "market_fill_simulation"
    STOP_LIMIT_PRIORITY_SIMULATION = "stop_limit_priority_simulation"


class OrderTypeEnum(StrEnum):
    """Order execution model (section 2)."""

    MARKET_ORDER = "market_order"
    LIMIT_ORDER = "limit_order"
    STOP_ORDER = "stop_order"
    STOP_LIMIT_ORDER = "stop_limit_order"
    SIMULATION_ONLY = "simulation_only"


class LimitPriceRuleEnum(StrEnum):
    """Conditional limit order pricing rule (section 2)."""

    ENTRY_SIGNAL_PRICE = "entry_signal_price"
    BEST_BID_ASK = "best_bid_ask"
    SIGNAL_PRICE_MINUS_OFFSET = "signal_price_minus_offset"
    SIGNAL_PRICE_PLUS_OFFSET = "signal_price_plus_offset"


class LimitValidityEnum(StrEnum):
    """Limit order time-in-force (section 2)."""

    CURRENT_CANDLE_ONLY = "current_candle_only"
    ONE_CANDLE = "1_candle"
    TWO_CANDLES = "2_candles"
    THREE_CANDLES = "3_candles"
    FOUR_CANDLES = "4_candles"
    UNTIL_CANCELLED = "until_cancelled"


class UnfilledPolicyEnum(StrEnum):
    """Limit order unfilled behavior (section 2)."""

    CANCEL_ORDER = "cancel_order"
    KEEP_UNTIL_VALIDITY_ENDS = "keep_until_validity_ends"
    RE_PRICE_NEXT_CANDLE = "re_price_next_candle"
    CONVERT_TO_MARKET_ORDER = "convert_to_market_order"


class PartialFillPolicyEnum(StrEnum):
    """Partial fill handling (section 2)."""

    NOT_ALLOWED = "not_allowed"
    ALLOWED = "allowed"
    MINIMUM_50_PERCENT = "minimum_50_percent"
    FILL_REMAINING_AS_MARKET = "fill_remaining_as_market"
    CANCEL_REMAINING = "cancel_remaining"


class SlippageModeEnum(StrEnum):
    """Slippage simulation mode (section 2)."""

    PERCENTAGE_SLIPPAGE = "percentage_slippage"
    HISTORICAL_SLIPPAGE_IF_AVAILABLE = "historical_slippage_if_available"


class IntrabarPolicyEnum(StrEnum):
    """Tick data policy (section 2)."""

    INHERIT = "inherit"
    REQUIRE = "require"
    DISABLE = "disable"


class SignalBlockRuleEnum(StrEnum):
    """Signal aggregation rule (sections 3, 4)."""

    REQUIRED_INDICATOR_BLOCKS_ONLY = "required_indicator_blocks_only"
    REQUIRED_PLUS_ANY_SUPPORTING = "required_plus_any_supporting"
    REQUIRED_PLUS_MIN_SUPPORTING = "required_plus_min_supporting"
    REQUIRED_PLUS_ALL_CONFIRMATIONS = "required_plus_all_confirmations"


class ConditionBlockRuleEnum(StrEnum):
    """Nested condition aggregation rule (section 3)."""

    REQUIRED_CONDITION_BLOCKS_ONLY = "required_condition_blocks_only"
    REQUIRED_PLUS_ANY_SUPPORTING = "required_plus_any_supporting"
    REQUIRED_PLUS_MIN_SUPPORTING = "required_plus_min_supporting"
    REQUIRED_PLUS_ALL_SUPPORTING = "required_plus_all_supporting"


class RequirementEnum(StrEnum):
    """Indicator/condition block role (sections 3, 4, 8)."""

    REQUIRED = "required"
    SUPPORTING = "supporting"


class TimeframeEnum(StrEnum):
    """Timeframe override options (sections 3, 4, 7)."""

    SAME_AS_BASE_TF = "same_as_base_tf"
    USE_PACKAGE_DEFAULT_TF = "use_package_default_tf"
    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1D"


class ValidityEnum(StrEnum):
    """Signal validity window (sections 3, 4, 8)."""

    CURRENT_CANDLE_ONLY = "current_candle_only"
    ONE_CANDLE = "1_candle"
    TWO_CANDLES = "2_candles"
    THREE_CANDLES = "3_candles"
    FOUR_CANDLES = "4_candles"
    UNTIL_OPPOSITE_SIGNAL = "until_opposite_signal"


class PartialAftermathEnum(StrEnum):
    """Post-partial-close strategy (section 4)."""

    MOVE_STOP_TO_ENTRY = "move_stop_to_entry"
    TRAILING_STOP = "trailing_stop"
    LOCK_IN_PROFIT = "lock_in_profit"
    CLOSE_ALL = "close_all"


class PositionSizingMethodEnum(StrEnum):
    """Mutually exclusive sizing method (section 6)."""

    BASE_POSITION_SIZE = "base_position_size"
    RISK_BASED_SIZING = "risk_based_sizing"
    FORMULA_BASED_SIZING = "formula_based_sizing"


class SignalStrengthAdjustmentEnum(StrEnum):
    """Signal confidence modulation (section 6)."""

    NO_ADJUSTMENT = "no_adjustment"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    TREND_ADJUSTED = "trend_adjusted"
    DIVERGENCE_ADJUSTED = "divergence_adjusted"


class LeverageModeEnum(StrEnum):
    """Margin mode (section 6)."""

    ISOLATED = "isolated"
    CROSS = "cross"


class FormulaTypeEnum(StrEnum):
    """Position sizing formula type (section 6)."""

    KELLY_CRITERION = "kelly_criterion"
    CUSTOM_FORMULA = "custom_formula"


class ScalingMethodEnum(StrEnum):
    """Position scaling activation logic (section 7)."""

    PRICE_DISTANCE_SCALING = "price_distance_scaling"
    LOGIC_BASED_SCALING = "logic_based_scaling"


class AddSizeTypeEnum(StrEnum):
    """Scaling add-size reference basis (section 7)."""

    PERCENT_OF_INITIAL = "percent_of_initial"
    PERCENT_OF_CURRENT = "percent_of_current"
    FIXED_AMOUNT = "fixed_amount"


class FilterTypeEnum(StrEnum):
    """Entry restriction filter type (section 8)."""

    VOLATILITY_FILTER = "volatility_filter"
    SPREAD_FILTER = "spread_filter"
    VOLUME_FILTER = "volume_filter"
    DATE_BLACKOUT_FILTER = "date_blackout_filter"
    MAX_DAILY_LOSS_FILTER = "max_daily_loss_filter"
    CONSECUTIVE_LOSS_FILTER = "consecutive_loss_filter"
    CORRELATION_FILTER = "correlation_filter"


class FilterRuleEnum(StrEnum):
    """Filter aggregation rule (section 8)."""

    ANY = "any"
    ALL = "all"


class OverlappingSignalPolicyEnum(StrEnum):
    """Concurrent signal handling (section 9)."""

    QUEUE_SEQUENTIAL = "queue_sequential"
    CANCEL_PENDING = "cancel_pending"
    MERGE_SIGNALS = "merge_signals"
    IGNORE_IF_ACTIVE = "ignore_if_active"


class SameDirectionStackingEnum(StrEnum):
    """Same-direction multi-position policy (section 9)."""

    ALLOW_STACKING = "allow_stacking"
    REPLACE_EXISTING = "replace_existing"
    SCALE_EXISTING = "scale_existing"
    IGNORE = "ignore"


class OppositeDirectionHedgeEnum(StrEnum):
    """Hedge/reverse position policy (section 9)."""

    ALLOW_HEDGE = "allow_hedge"
    CLOSE_EXISTING = "close_existing"
    IGNORE = "ignore"


class ValidationStatusEnum(StrEnum):
    """Strategy revision validation state (schema §3.2)."""

    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    STALE = "stale"


class StrategyLifecycleStateEnum(StrEnum):
    """Strategy root lifecycle (schema §3.1)."""

    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE_CANDIDATE = "active_candidate"
    LOCKED_FOR_TEST = "locked_for_test"
    DEPRECATED = "deprecated"
    SOFT_DELETED = "soft_deleted"


class DependencyRoleEnum(StrEnum):
    """Semantic role in strategy dependency graph (schema §3.3)."""

    ENTRY_INDICATOR = "entry_indicator"
    ENTRY_CONDITION = "entry_condition"
    EXIT_INDICATOR = "exit_indicator"
    EXIT_CONDITION = "exit_condition"
    SCALING_LOGIC = "scaling_logic"
    RESTRICTION_FILTER = "restriction_filter"
    DATA_SOURCE = "data_source"
    FUNDING_SOURCE = "funding_source"
    # F-08 Logic-Based Stop: pinned packages of a protection logic-stop block.
    PROTECTION_STOP_INDICATOR = "protection_stop_indicator"
    PROTECTION_STOP_CONDITION = "protection_stop_condition"


class ReferencedEntityTypeEnum(StrEnum):
    """Type of pinned dependency entity (schema §3.3)."""

    INDICATOR_PACKAGE = "indicator_package"
    CONDITION_PACKAGE = "condition_package"
    EMBEDDED_SYSTEM_PACKAGE = "embedded_system_package"
    MARKET_DATASET = "market_dataset"
    RESEARCH_DATASET = "research_dataset"
