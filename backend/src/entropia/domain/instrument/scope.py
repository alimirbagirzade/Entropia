"""Canonical instrument scope value object + normalization (GAP-16; Master §8.1).

An instrument "scope" shown in the UI (e.g. "BTCUSDT Perpetual") is NEVER matched
by free-text equality; it must resolve to a canonical registry row. The identity
of an instrument is the ``resolution_key`` — the normalized ``venue:symbol:
contract_type`` triple — so spot vs perpetual and one venue vs another are
distinct rows. All normalization is pure and deterministic (no clock/IO).
"""

from __future__ import annotations

from dataclasses import dataclass

from entropia.domain.instrument.enums import ContractType
from entropia.shared.errors import InstrumentScopeInvalidError


def normalize_token(value: str | None) -> str:
    """Trim, lowercase and collapse internal whitespace to a single space."""
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def normalize_alias(value: str | None) -> str:
    """Normalized alias identity used for display-text -> instrument resolution."""
    return normalize_token(value)


def coerce_contract_type(value: str | ContractType | None) -> ContractType:
    """Coerce a wire string to a ContractType, or reject it (never a silent 'other')."""
    if isinstance(value, ContractType):
        return value
    token = normalize_token(value)
    if not token:
        raise InstrumentScopeInvalidError("A contract type is required for an instrument scope.")
    try:
        return ContractType(token)
    except ValueError as exc:
        raise InstrumentScopeInvalidError(f"'{value}' is not a recognized contract type.") from exc


@dataclass(frozen=True, slots=True)
class InstrumentScope:
    """The identity + metadata of a tradable instrument (Master §8.1 fields)."""

    venue_id: str
    symbol: str
    contract_type: ContractType
    display_name: str
    base_asset: str | None = None
    quote_asset: str | None = None
    settlement_asset: str | None = None
    multiplier: str | None = None
    market_class: str | None = None

    @property
    def resolution_key(self) -> str:
        """Canonical identity: ``venue:symbol:contract_type`` (normalized)."""
        return resolution_key(self.venue_id, self.symbol, self.contract_type)


def resolution_key(
    venue_id: str | None, symbol: str | None, contract_type: str | ContractType | None
) -> str:
    """Build the canonical, case-insensitive identity for an instrument scope."""
    ct = coerce_contract_type(contract_type)
    return f"{normalize_token(venue_id)}:{normalize_token(symbol)}:{ct.value}"


def require_registerable(scope: InstrumentScope) -> None:
    """The three identity fields (venue, symbol, contract_type) must be present.

    Metadata (base/quote/settlement/multiplier/market_class) is optional; a blank
    identity field is rejected so no ambiguous, unresolvable row is ever created.
    """
    if not normalize_token(scope.venue_id):
        raise InstrumentScopeInvalidError("An instrument scope requires a venue.")
    if not normalize_token(scope.symbol):
        raise InstrumentScopeInvalidError("An instrument scope requires a symbol.")
    if not scope.display_name.strip():
        raise InstrumentScopeInvalidError("An instrument scope requires a display name.")
