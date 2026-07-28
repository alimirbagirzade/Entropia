"""Market Data per-domain enums (doc 11, CR-04).

All values are lowercase snake_case and are returned over REST/SSE verbatim.
The market revision lifecycle (``MarketRevisionState``) is a SEPARATE facet from
the shared deletion/validation/approval/visibility enums and never collapses
into a single status column.
"""

from __future__ import annotations

from enum import StrEnum


class MarketDataType(StrEnum):
    """The three accepted market-data shapes. Choice selects the target schema
    and the type-specific validators (doc 11 §)."""

    OHLCV = "ohlcv"
    TICK_TRADES = "tick_trades"
    SPREAD_EXECUTION = "spread_execution"


def supports_intrabar_execution(market_data_type: MarketDataType | str) -> bool:
    """Can a dataset of this shape resolve a price BETWEEN two bar boundaries (K-08)?

    Only ``tick_trades`` carries the sub-bar print sequence an intrabar resolution
    needs. ``ohlcv`` is bar-aggregated by construction — its open/high/low/close say
    nothing about the ORDER in which those extremes were reached inside the bar — and
    ``spread_execution`` is a cost series, not a price path. Answering "yes" for either
    would let the engine silently imitate detail the dataset does not contain (doc 04
    §5.2 "Price Source = OHLCV Intrabar If Available" -> ``INTRABAR_DATA_UNAVAILABLE``).

    Single source of truth, the same discipline as
    ``domain/backtest/execution/fills.py::tick_data_required``: the readiness blocker
    and any later engine-side intrabar gate must never disagree about what "supports
    intrabar" means. An unknown/unparseable string answers ``False`` (fail closed).
    """
    return market_data_type == MarketDataType.TICK_TRADES


class MarketRevisionState(StrEnum):
    """Market dataset revision lifecycle. ``verified`` is distinct from
    ``approved``: only an Admin moves verified -> approved, and only an
    ACTIVE+APPROVED revision feeds research/backtests."""

    DRAFT = "draft"
    UPLOADING = "uploading"
    ANALYZING = "analyzing"
    NEEDS_REVIEW = "needs_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


class ResolutionKind(StrEnum):
    """How a dataset's cadence is expressed."""

    BAR = "bar"
    EVENT_BASED = "event_based"


class TimezoneMode(StrEnum):
    """Declared source timezone semantics. ``custom`` requires an IANA id."""

    EXCHANGE = "exchange"
    UTC = "utc"
    CUSTOM = "custom"


class RecordTimeBasis(StrEnum):
    """What a row's timestamp means relative to the event it records."""

    BAR_CLOSE = "bar_close"
    BAR_OPEN = "bar_open"
    EVENT_TIME = "event_time"


class TradeSide(StrEnum):
    """Tick/trade side. ``unknown`` is preserved, never guessed (doc 11 §)."""

    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"
