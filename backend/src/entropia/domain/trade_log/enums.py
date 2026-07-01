"""Trade Log domain enums (Stage 3d, doc 05 §5, §5.1-§5.4, §10).

Lowercase snake_case ``StrEnum`` values, stored as canonical strings inside the
work object revision payload (JSONB) and the canonical trade-record batch. Trade
Log is an EXTERNAL work object (``object_kind=trade_log``) — never a ``PackageKind``
(CR-01, TL-01).
"""

from __future__ import annotations

from enum import StrEnum


class SourceKind(StrEnum):
    """Where the raw trade records came from (doc 05 §5.1, §10.2)."""

    FILE = "file"
    INTEGRATION = "integration"


class TradeDirection(StrEnum):
    """Canonical direction of a historical trade record (doc 05 §5.4).

    Case/alias mapping is applied during import normalization; anything that does
    not resolve to exactly one of these skips the row (``INVALID_TRADE_DIRECTION``).
    """

    LONG = "long"
    SHORT = "short"


class ContentProfile(StrEnum):
    """Which columns the source file is declared to carry (doc 05 §5.1, §5.3).

    Ledger semantics — this is the Trade Log ``Data Quality`` selector.
    ``TRADE_LOG_WITH_SIGNAL_EVENTS`` never promotes the object into a Trading Signal
    (doc 05 §5.3).
    """

    ENTRY_EXIT_RECORDS_ONLY = "entry_exit_records_only"
    TRADE_LOG_WITH_OHLCV = "trade_log_with_ohlcv"
    TRADE_LOG_WITH_SIGNAL_EVENTS = "trade_log_with_signal_events"


class ResolutionKind(StrEnum):
    """How trade records align to bars (doc 05 §5.1 Base TF / Event Model).

    ``event_based`` records carry no base timeframe; a bar-aligned source selects a
    supported timeframe.
    """

    EVENT_BASED = "event_based"
    SAME_AS_MARKET_DATASET = "same_as_market_dataset"
    BAR_TIMEFRAME = "bar_timeframe"


class PriceSourceMode(StrEnum):
    """Which price a backtest reads for a record (doc 05 §5.2 Price Source)."""

    TRADE_LOG_ENTRY_EXIT_PRICE = "trade_log_entry_exit_price"
    OHLCV_CLOSE_IF_NEEDED = "ohlcv_close_if_needed"
    OHLCV_INTRABAR_IF_AVAILABLE = "ohlcv_intrabar_if_available"


class OhlcvUseMode(StrEnum):
    """How source-file OHLCV context is used (doc 05 §5.2 OHLCV Use).

    Source-file OHLCV is contextual evidence only; it never substitutes for an
    Approved Market Data revision at execution time (doc 05 §5.3, Implementation
    Rule 8).
    """

    USE_IF_SUPPLIED_AND_NEEDED = "use_if_supplied_and_needed"
    IGNORE = "ignore"
    USE_FOR_PRICE_CONTEXT_AND_VALIDATION = "use_for_price_context_and_validation"


class RecordBatchStatus(StrEnum):
    """Lifecycle of a canonical trade-record batch produced by import.

    The durable ``jobs`` row carries the transport-level ``JobStatus``; this enum is
    the domain-level outcome of the parse/map/validate pass.
    """

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
