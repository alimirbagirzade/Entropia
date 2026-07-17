"""Deterministic source-column -> canonical-field mapping (decision D7, doc 11).

Per market-data type we keep a synonym table for the *essential* canonical
fields. Auto-confirmation is allowed ONLY when every essential field maps to
exactly one source column (by exact name or synonym, case-insensitive). If any
essential field has zero or more than one candidate, the mapping is ambiguous and
``review_required`` is set so the command surfaces ``MAPPING_REVIEW_REQUIRED``.

Pure: no I/O. Optional fields (e.g. OHLCV volume, tick side) never block.
"""

from __future__ import annotations

from dataclasses import dataclass

from entropia.domain.market_data.enums import MarketDataType

# Canonical essential field -> accepted source-column synonyms (lowercased).
_ESSENTIAL_SYNONYMS: dict[MarketDataType, dict[str, frozenset[str]]] = {
    MarketDataType.OHLCV: {
        "timestamp": frozenset({"timestamp", "time", "date", "datetime", "ts"}),
        "open": frozenset({"open", "o", "open_price"}),
        "high": frozenset({"high", "h", "high_price"}),
        "low": frozenset({"low", "l", "low_price"}),
        "close": frozenset({"close", "c", "close_price", "last"}),
    },
    MarketDataType.TICK_TRADES: {
        "timestamp": frozenset({"timestamp", "time", "date", "datetime", "ts"}),
        "price": frozenset({"price", "p", "trade_price", "last"}),
    },
    MarketDataType.SPREAD_EXECUTION: {
        "timestamp": frozenset({"timestamp", "time", "date", "datetime", "ts"}),
        "bid": frozenset({"bid", "bid_price", "best_bid"}),
        "ask": frozenset({"ask", "ask_price", "best_ask", "offer"}),
    },
}

_OPTIONAL_SYNONYMS: dict[MarketDataType, dict[str, frozenset[str]]] = {
    MarketDataType.OHLCV: {"volume": frozenset({"volume", "v", "vol", "qty", "quantity"})},
    MarketDataType.TICK_TRADES: {
        "side": frozenset({"side", "direction", "aggressor"}),
        # F-07i (C): the print's traded quantity — the partial-fill fraction evidence
        # (Master Ref §6.3 Partial Fill). Optional: a size-less tick revision still
        # replays; only the partial-fill computation degrades to the coarse full-fill
        # model (flagged, never fabricated).
        "size": frozenset({"size", "qty", "quantity", "amount", "volume", "v", "vol"}),
    },
    MarketDataType.SPREAD_EXECUTION: {},
}


@dataclass(frozen=True, slots=True)
class SchemaMappingProposal:
    """Result of proposing a canonical mapping for a set of source columns."""

    proposed: dict[str, str | None]
    review_required: bool
    ambiguous_fields: tuple[str, ...]
    unmapped_fields: tuple[str, ...]


def _candidates(synonyms: frozenset[str], columns: list[str]) -> list[str]:
    lowered = {col: col.strip().lower() for col in columns}
    return [col for col, low in lowered.items() if low in synonyms]


def propose_schema_mapping(
    market_data_type: MarketDataType, source_columns: list[str]
) -> SchemaMappingProposal:
    """Map essential (and known optional) fields to source columns deterministically.

    Auto-confirm iff every essential field has exactly one candidate column.
    """
    essentials = _ESSENTIAL_SYNONYMS[market_data_type]
    optionals = _OPTIONAL_SYNONYMS[market_data_type]

    proposed: dict[str, str | None] = {}
    ambiguous: list[str] = []
    unmapped: list[str] = []

    for field, synonyms in essentials.items():
        matches = _candidates(synonyms, source_columns)
        if len(matches) == 1:
            proposed[field] = matches[0]
        else:
            proposed[field] = None
            if len(matches) == 0:
                unmapped.append(field)
            else:
                ambiguous.append(field)

    for field, synonyms in optionals.items():
        matches = _candidates(synonyms, source_columns)
        proposed[field] = matches[0] if len(matches) == 1 else None

    review_required = bool(ambiguous or unmapped)
    return SchemaMappingProposal(
        proposed=proposed,
        review_required=review_required,
        ambiguous_fields=tuple(ambiguous),
        unmapped_fields=tuple(unmapped),
    )


def confirmed_mapping_is_complete(
    market_data_type: MarketDataType, confirmed: dict[str, str | None]
) -> bool:
    """A confirmed mapping is complete iff every essential field is mapped."""
    essentials = _ESSENTIAL_SYNONYMS[market_data_type]
    return all(confirmed.get(field) for field in essentials)
