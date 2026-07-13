"""Canonical instrument registry persistence (GAP-16; Master §8.1).

Sync mutators INSERT rows / bump the registry version (no commit, mirroring
``repositories/esp.py``); async readers return ORM rows for the queries layer.
The application command layer validates authorization (policy), legality (state
machine) and optimistic concurrency (registry_version) first.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.instrument.enums import ContractType, InstrumentState
from entropia.infrastructure.postgres.models import InstrumentAlias, InstrumentRegistry
from entropia.shared.ids import new_id


def create_instrument(
    session: AsyncSession,
    *,
    resolution_key: str,
    venue_id: str,
    symbol: str,
    contract_type: ContractType,
    display_name: str,
    base_asset: str | None = None,
    quote_asset: str | None = None,
    settlement_asset: str | None = None,
    multiplier: Decimal | None = None,
    market_class: str | None = None,
    created_by_principal_id: str | None = None,
) -> InstrumentRegistry:
    """Insert a new canonical instrument row (state ACTIVE, registry_version 1)."""
    instrument = InstrumentRegistry(
        instrument_id=new_id("instr"),
        resolution_key=resolution_key,
        venue_id=venue_id,
        symbol=symbol,
        contract_type=contract_type,
        display_name=display_name,
        base_asset=base_asset,
        quote_asset=quote_asset,
        settlement_asset=settlement_asset,
        multiplier=multiplier,
        market_class=market_class,
        state=InstrumentState.ACTIVE,
        registry_version=1,
        created_by_principal_id=created_by_principal_id,
        updated_by_principal_id=created_by_principal_id,
    )
    session.add(instrument)
    return instrument


def add_alias(
    session: AsyncSession,
    *,
    instrument_id: str,
    alias_norm: str,
    alias_text: str,
    created_by_principal_id: str | None = None,
) -> InstrumentAlias:
    """Insert a display-alias -> instrument resolution row."""
    alias = InstrumentAlias(
        alias_id=new_id("insa"),
        instrument_id=instrument_id,
        alias_norm=alias_norm,
        alias_text=alias_text,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(alias)
    return alias


def set_state(
    instrument: InstrumentRegistry,
    *,
    state: InstrumentState,
    deprecation_reason: str | None = None,
    updated_by_principal_id: str | None = None,
) -> InstrumentRegistry:
    """Apply a validated state transition and bump the registry version.

    The caller must validate the transition (state machine) and authorization
    (policy) first. ``registry_version`` is incremented so a stale deprecation is
    detected on the next optimistic-concurrency check.
    """
    instrument.state = state
    if deprecation_reason is not None:
        instrument.deprecation_reason = deprecation_reason
    instrument.registry_version += 1
    if updated_by_principal_id is not None:
        instrument.updated_by_principal_id = updated_by_principal_id
    return instrument


async def get_instrument(session: AsyncSession, instrument_id: str) -> InstrumentRegistry | None:
    stmt = select(InstrumentRegistry).where(InstrumentRegistry.instrument_id == instrument_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_by_resolution_key(
    session: AsyncSession, resolution_key: str
) -> InstrumentRegistry | None:
    stmt = select(InstrumentRegistry).where(InstrumentRegistry.resolution_key == resolution_key)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_alias(session: AsyncSession, alias_norm: str) -> InstrumentAlias | None:
    stmt = select(InstrumentAlias).where(InstrumentAlias.alias_norm == alias_norm)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_aliases_for(session: AsyncSession, instrument_id: str) -> Sequence[InstrumentAlias]:
    stmt = (
        select(InstrumentAlias)
        .where(InstrumentAlias.instrument_id == instrument_id)
        .order_by(InstrumentAlias.alias_norm.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_instruments(
    session: AsyncSession,
    *,
    state: InstrumentState | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> Sequence[InstrumentRegistry]:
    """Registry rows ordered by resolution_key (keyset cursor)."""
    stmt = select(InstrumentRegistry).order_by(InstrumentRegistry.resolution_key.asc())
    if state is not None:
        stmt = stmt.where(InstrumentRegistry.state == state)
    if cursor is not None:
        stmt = stmt.where(InstrumentRegistry.resolution_key > cursor)
    stmt = stmt.limit(limit + 1)
    return list((await session.execute(stmt)).scalars().all())


__all__ = [
    "add_alias",
    "create_instrument",
    "get_alias",
    "get_by_resolution_key",
    "get_instrument",
    "list_aliases_for",
    "list_instruments",
    "set_state",
]
