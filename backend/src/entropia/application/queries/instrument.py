"""Canonical instrument registry read-side queries (GAP-16; Master §8.1, §9.1).

The registry is shared reference data: any authenticated actor may list/read it.
``resolve_scope`` is the resolution the ingest paths + the UI call to turn a
free-text instrument scope ("BTCUSDT Perpetual", or a venue/symbol/contract
triple) into a canonical ``instrument_id`` — the "instrument scope must resolve"
rule (Master §8.1). An unresolvable scope raises INSTRUMENT_SCOPE_UNRESOLVABLE so
the caller cannot silently fall back to a free-text assumption.

All return values are JSON-safe dicts (``str(enum)``, ``.isoformat()``).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.instrument.enums import InstrumentState
from entropia.domain.instrument.scope import (
    coerce_contract_type,
    normalize_alias,
    resolution_key,
)
from entropia.infrastructure.postgres.models import InstrumentAlias, InstrumentRegistry
from entropia.infrastructure.postgres.repositories import instrument as instrument_repo
from entropia.shared.errors import (
    InstrumentNotFoundError,
    InstrumentScopeInvalidError,
    InstrumentScopeUnresolvableError,
)
from entropia.shared.pagination import PageParams


def _instrument_dict(instrument: InstrumentRegistry) -> dict[str, Any]:
    return {
        "instrument_id": instrument.instrument_id,
        "resolution_key": instrument.resolution_key,
        "venue_id": instrument.venue_id,
        "symbol": instrument.symbol,
        "contract_type": str(instrument.contract_type),
        "display_name": instrument.display_name,
        "base_asset": instrument.base_asset,
        "quote_asset": instrument.quote_asset,
        "settlement_asset": instrument.settlement_asset,
        "multiplier": str(instrument.multiplier) if instrument.multiplier is not None else None,
        "market_class": instrument.market_class,
        "state": str(instrument.state),
        "registry_version": instrument.registry_version,
        "deprecation_reason": instrument.deprecation_reason,
    }


def _alias_dict(alias: InstrumentAlias) -> dict[str, Any]:
    return {
        "alias_id": alias.alias_id,
        "alias_norm": alias.alias_norm,
        "alias_text": alias.alias_text,
    }


async def list_instruments(
    session: AsyncSession,
    actor: Actor,
    params: PageParams,
    *,
    state: InstrumentState | None = None,
) -> dict[str, Any]:
    """List canonical instruments, cursor-paginated by resolution_key."""
    require_authenticated(actor)
    rows = await instrument_repo.list_instruments(
        session, state=state, cursor=params.cursor, limit=params.limit
    )
    has_more = len(rows) > params.limit
    page = list(rows[: params.limit])
    next_cursor = page[-1].resolution_key if has_more and page else None
    return {
        "data": [_instrument_dict(row) for row in page],
        "meta": {"cursor": next_cursor, "has_more": has_more},
    }


async def get_instrument_detail(
    session: AsyncSession, actor: Actor, *, instrument_id: str
) -> dict[str, Any]:
    """Return the instrument detail + its resolution aliases."""
    require_authenticated(actor)
    instrument = await instrument_repo.get_instrument(session, instrument_id)
    if instrument is None:
        raise InstrumentNotFoundError(f"Instrument '{instrument_id}' not found.")
    aliases = await instrument_repo.list_aliases_for(session, instrument_id)
    return {
        **_instrument_dict(instrument),
        "row_version": instrument.registry_version,
        "aliases": [_alias_dict(alias) for alias in aliases],
    }


async def resolve_scope(
    session: AsyncSession,
    *,
    venue_id: str | None = None,
    symbol: str | None = None,
    contract_type: str | None = None,
    alias: str | None = None,
) -> dict[str, Any]:
    """Resolve a free-text instrument scope to a canonical instrument (Master §8.1).

    Resolution order:
      * an ``alias`` (display text) -> the instrument it uniquely resolves to;
      * else a ``venue/symbol/contract_type`` triple -> its resolution_key.
    A scope that resolves to no registered instrument -> INSTRUMENT_SCOPE_UNRESOLVABLE
    (422): the caller must register the instrument first rather than silently
    assume a free-text identity. A deprecated instrument still resolves (historical
    pins keep reading), with its ``state`` surfaced so the caller can warn.
    """
    instrument = await _resolve_instrument(
        session, venue_id=venue_id, symbol=symbol, contract_type=contract_type, alias=alias
    )
    return {"resolved": True, **_instrument_dict(instrument)}


async def _resolve_instrument(
    session: AsyncSession,
    *,
    venue_id: str | None,
    symbol: str | None,
    contract_type: str | None,
    alias: str | None,
) -> InstrumentRegistry:
    if alias is not None and alias.strip():
        alias_row = await instrument_repo.get_alias(session, normalize_alias(alias))
        if alias_row is None:
            raise InstrumentScopeUnresolvableError(
                f"No canonical instrument resolves the scope '{alias.strip()}'."
            )
        instrument = await instrument_repo.get_instrument(session, alias_row.instrument_id)
        if instrument is None:
            raise InstrumentScopeUnresolvableError(
                f"No canonical instrument resolves the scope '{alias.strip()}'."
            )
        return instrument

    if not (venue_id and symbol and contract_type):
        raise InstrumentScopeInvalidError(
            "Provide either an alias or a venue/symbol/contract_type triple to resolve."
        )
    # coerce_contract_type raises INSTRUMENT_SCOPE_INVALID on an unknown type.
    coerce_contract_type(contract_type)
    key = resolution_key(venue_id, symbol, contract_type)
    instrument = await instrument_repo.get_by_resolution_key(session, key)
    if instrument is None:
        raise InstrumentScopeUnresolvableError(
            f"No canonical instrument resolves the scope '{key}'."
        )
    return instrument


__all__ = [
    "get_instrument_detail",
    "list_instruments",
    "resolve_scope",
]
