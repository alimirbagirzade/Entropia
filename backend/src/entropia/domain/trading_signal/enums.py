"""Trading Signal domain enums (Stage 3c, doc 04 §5, §5.1, §9).

Lowercase snake_case ``StrEnum`` values, stored as canonical strings inside the
work object revision payload (JSONB) and the normalized-event revision. Trading
Signal is an EXTERNAL work object (``object_kind=trading_signal``) — never a
``PackageKind`` (CR-01).
"""

from __future__ import annotations

from enum import StrEnum


class SourceKind(StrEnum):
    """Where the raw signal events came from (doc 04 §5, §9.2)."""

    FILE = "file"
    INTEGRATION = "integration"


class SignalDirection(StrEnum):
    """Canonical directional bias of a signal event (doc 04 §5.1).

    Case/alias mapping is applied during import normalization; anything that does
    not resolve to exactly one of these is rejected (``INVALID_SIGNAL_DIRECTION``).
    """

    LONG = "long"
    SHORT = "short"


class SignalType(StrEnum):
    """Canonical signal-event type (doc 04 §5.1).

    ``entry`` semantics are NEVER assumed by default; an unmapped upstream value
    requires explicit mapping to one of these (``SIGNAL_EVENT_MAPPING_REQUIRED``).
    """

    ENTRY = "entry"
    EXIT_HINT = "exit_hint"
    SCALE_HINT = "scale_hint"
    CLOSE = "close"
    PROVIDER_CUSTOM = "provider_custom"


class DataQualityMode(StrEnum):
    """Permissible source columns / policy scope (doc 04 §3.1, §5).

    Canonical signal-event terminology — the legacy V18 ``Entry / Exit Records
    Only`` is NOT a valid mode here (that is Trade Log ledger semantics).
    """

    SIGNAL_EVENTS_ONLY = "signal_events_only"
    SIGNAL_EVENTS_WITH_SOURCE_OHLCV = "signal_events_with_source_ohlcv"
    SIGNAL_EVENTS_WITH_MARKET_CONTEXT = "signal_events_with_market_context"


class ResolutionKind(StrEnum):
    """How signal times align to bars (doc 04 §5, §5.2, ID-04-02).

    ``event_based`` sources carry no base timeframe; a bar-aligned source selects a
    supported timeframe.
    """

    EVENT_BASED = "event_based"
    SAME_AS_MARKET_DATASET = "same_as_market_dataset"
    BAR_TIMEFRAME = "bar_timeframe"


class PriceSourceMode(StrEnum):
    """Which price a backtest reads for a signal event (doc 04 §5, §5.2)."""

    SUGGESTED_SIGNAL_PRICE = "suggested_signal_price"
    OHLCV_CLOSE_IF_NEEDED = "ohlcv_close_if_needed"
    OHLCV_INTRABAR_IF_AVAILABLE = "ohlcv_intrabar_if_available"


class OhlcvUseMode(StrEnum):
    """How source-file OHLCV context is used (doc 04 §5, §5.2).

    Source-file OHLCV is contextual evidence only; it never substitutes for an
    Approved Market Data revision at execution time.
    """

    USE_IF_SUPPLIED_AND_NEEDED = "use_if_supplied_and_needed"
    IGNORE = "ignore"
    USE_FOR_PRICE_CONTEXT_AND_VALIDATION = "use_for_price_context_and_validation"


class NormalizedRevisionStatus(StrEnum):
    """Lifecycle of a normalized signal-event revision produced by import.

    The durable ``jobs`` row carries the transport-level ``JobStatus``; this enum
    is the domain-level outcome of the parse/map/validate pass.
    """

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
