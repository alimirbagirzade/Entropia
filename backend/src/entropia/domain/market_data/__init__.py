"""Market Data domain surface (doc 11). Re-exports only; no logic here."""

from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    RecordTimeBasis,
    ResolutionKind,
    TimezoneMode,
    TradeSide,
)
from entropia.domain.market_data.policy import (
    ensure_can_approve,
    ensure_can_edit_draft,
    ensure_can_view,
)
from entropia.domain.market_data.schema_mapping import (
    SchemaMappingProposal,
    confirmed_mapping_is_complete,
    propose_schema_mapping,
)
from entropia.domain.market_data.state_machine import (
    IllegalMarketRevisionTransition,
    can_approve,
    can_deprecate,
    can_reject,
    can_verify,
    next_market_revision_state,
)
from entropia.domain.market_data.validation_rules import (
    OhlcvRow,
    SpreadRow,
    TickRow,
    validate_ohlcv_row,
    validate_spread_row,
    validate_tick_row,
)
from entropia.domain.market_data.value_objects import (
    CoverageSlice,
    Resolution,
    TimezoneSpec,
)

__all__ = [
    "CoverageSlice",
    "IllegalMarketRevisionTransition",
    "MarketDataType",
    "MarketRevisionState",
    "OhlcvRow",
    "RecordTimeBasis",
    "Resolution",
    "ResolutionKind",
    "SchemaMappingProposal",
    "SpreadRow",
    "TickRow",
    "TimezoneMode",
    "TimezoneSpec",
    "TradeSide",
    "can_approve",
    "can_deprecate",
    "can_reject",
    "can_verify",
    "confirmed_mapping_is_complete",
    "ensure_can_approve",
    "ensure_can_edit_draft",
    "ensure_can_view",
    "next_market_revision_state",
    "propose_schema_mapping",
    "validate_ohlcv_row",
    "validate_spread_row",
    "validate_tick_row",
]
