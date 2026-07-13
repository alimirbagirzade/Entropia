"""Canonical instrument registry commands (GAP-16; Master Reference §8.1).

Each command runs in one transaction supplied by the request dependency and
NEVER commits (mirrors Stage 1/2). The shape per mutation is:

    policy check -> domain check -> repo mutation
    -> add_audit_event ("instrument.*") + add_outbox_event

Registration is open to any authenticated actor (reference data the whole
workspace shares); deprecation is Admin-only. Optimistic concurrency uses the
registry version token: a stale ``expected_registry_version`` ->
INSTRUMENT_REGISTRY_CONFLICT (409). Idempotent commands route through
``application.idempotency.run_idempotent`` with the concurrency + legality checks
INSIDE the operation body (L2/D3), so a completed-key replay returns the cached
result instead of a spurious conflict.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.domain.identity import Actor
from entropia.domain.instrument import policy as instrument_policy
from entropia.domain.instrument.enums import InstrumentState
from entropia.domain.instrument.scope import (
    InstrumentScope,
    coerce_contract_type,
    normalize_alias,
    require_registerable,
)
from entropia.domain.instrument.state_machine import next_instrument_state
from entropia.infrastructure.postgres.models import InstrumentRegistry
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import instrument as instrument_repo
from entropia.shared.errors import (
    InstrumentAlreadyRegisteredError,
    InstrumentNotFoundError,
    InstrumentRegistryConflictError,
    InstrumentScopeInvalidError,
)

_TARGET_KIND = "instrument"


def _audit_and_outbox(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    instrument_id: str,
    previous_state: str | None = None,
    new_state: str | None = None,
    action: str,
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=instrument_id,
        target_entity_type=_TARGET_KIND,
        target_revision_id=None,
        previous_state=previous_state,
        new_state=new_state,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=_TARGET_KIND,
        resource_id=instrument_id,
        payload={"action": action},
        correlation_id=actor.correlation_id,
    )


def _parse_multiplier(value: str | float | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise InstrumentScopeInvalidError(f"'{value}' is not a valid multiplier.") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise InstrumentScopeInvalidError("An instrument multiplier must be a positive number.")
    return parsed


async def register_instrument(
    session: AsyncSession,
    actor: Actor,
    *,
    venue_id: str,
    symbol: str,
    contract_type: str,
    display_name: str,
    base_asset: str | None = None,
    quote_asset: str | None = None,
    settlement_asset: str | None = None,
    multiplier: str | float | None = None,
    market_class: str | None = None,
    aliases: list[str] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Register a new canonical instrument (+ optional resolution aliases).

    The identity triple (venue/symbol/contract_type) must be present and unique;
    a duplicate ``resolution_key`` -> INSTRUMENT_ALREADY_REGISTERED. An alias that
    already resolves to another instrument -> INSTRUMENT_ALREADY_REGISTERED (an
    alias can never be ambiguous). Emits ``instrument.registered`` audit + outbox.
    """
    instrument_policy.ensure_can_register(actor)
    ct = coerce_contract_type(contract_type)
    multiplier_value = _parse_multiplier(multiplier)
    scope = InstrumentScope(
        venue_id=venue_id,
        symbol=symbol,
        contract_type=ct,
        display_name=display_name,
        base_asset=base_asset,
        quote_asset=quote_asset,
        settlement_asset=settlement_asset,
        multiplier=str(multiplier_value) if multiplier_value is not None else None,
        market_class=market_class,
    )
    require_registerable(scope)
    key = scope.resolution_key
    normalized_aliases = _dedupe_aliases(aliases)

    async def _op() -> dict[str, Any]:
        if await instrument_repo.get_by_resolution_key(session, key) is not None:
            raise InstrumentAlreadyRegisteredError(
                f"An instrument with scope '{key}' is already registered."
            )
        instrument = instrument_repo.create_instrument(
            session,
            resolution_key=key,
            venue_id=venue_id.strip(),
            symbol=symbol.strip(),
            contract_type=ct,
            display_name=display_name.strip(),
            base_asset=base_asset,
            quote_asset=quote_asset,
            settlement_asset=settlement_asset,
            multiplier=multiplier_value,
            market_class=market_class,
            created_by_principal_id=actor.principal_id,
        )
        # Flush the parent before the alias children: SQLAlchemy's unit-of-work
        # does not derive parent-before-child INSERT order from a bare ForeignKey
        # (no relationship() on the registry), so the order is made explicit.
        await session.flush()
        for alias_norm, alias_text in normalized_aliases:
            await _ensure_alias_free(session, alias_norm)
            instrument_repo.add_alias(
                session,
                instrument_id=instrument.instrument_id,
                alias_norm=alias_norm,
                alias_text=alias_text,
                created_by_principal_id=actor.principal_id,
            )
        _audit_and_outbox(
            session,
            actor,
            event_kind="instrument.registered",
            instrument_id=instrument.instrument_id,
            new_state=str(instrument.state),
            action="registered",
        )
        return {
            "instrument_id": instrument.instrument_id,
            "resolution_key": key,
            "display_name": instrument.display_name,
            "state": str(instrument.state),
            "registry_version": instrument.registry_version,
            "alias_count": len(normalized_aliases),
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "register_instrument", "resolution_key": key},
        operation=_op,
    )


async def add_instrument_alias(
    session: AsyncSession,
    actor: Actor,
    *,
    instrument_id: str,
    alias: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Attach a display alias to an existing instrument for scope resolution."""
    instrument_policy.ensure_can_register(actor)
    alias_norm = normalize_alias(alias)
    if not alias_norm:
        raise InstrumentScopeInvalidError("An alias cannot be blank.")

    async def _op() -> dict[str, Any]:
        instrument = await _require_instrument(session, instrument_id)
        await _ensure_alias_free(session, alias_norm, owner_instrument_id=instrument_id)
        instrument_repo.add_alias(
            session,
            instrument_id=instrument.instrument_id,
            alias_norm=alias_norm,
            alias_text=alias.strip(),
            created_by_principal_id=actor.principal_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="instrument.alias_added",
            instrument_id=instrument.instrument_id,
            action="alias_added",
        )
        return {
            "instrument_id": instrument.instrument_id,
            "alias_norm": alias_norm,
            "alias_text": alias.strip(),
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "add_instrument_alias",
            "instrument_id": instrument_id,
            "alias": alias_norm,
        },
        operation=_op,
    )


async def deprecate_instrument(
    session: AsyncSession,
    actor: Actor,
    *,
    instrument_id: str,
    reason: str,
    expected_registry_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin-only: deprecate an ACTIVE instrument -> DEPRECATED (Master §8.1).

    A reason is required. Historical ``instrument_id`` references keep resolving;
    only new-work selection is closed. A stale ``expected_registry_version`` ->
    INSTRUMENT_REGISTRY_CONFLICT (409).
    """
    instrument_policy.ensure_can_deprecate(actor)
    if not reason.strip():
        raise InstrumentScopeInvalidError("A deprecation reason is required.")

    async def _op() -> dict[str, Any]:
        instrument = await _require_instrument(session, instrument_id)
        _check_registry_version(instrument, expected_registry_version)
        previous = instrument.state
        next_instrument_state(previous, InstrumentState.DEPRECATED)
        instrument_repo.set_state(
            instrument,
            state=InstrumentState.DEPRECATED,
            deprecation_reason=reason.strip(),
            updated_by_principal_id=actor.principal_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="instrument.deprecated",
            instrument_id=instrument.instrument_id,
            previous_state=str(previous),
            new_state=str(instrument.state),
            action="deprecated",
        )
        return {
            "instrument_id": instrument.instrument_id,
            "state": str(instrument.state),
            "registry_version": instrument.registry_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "deprecate_instrument", "instrument_id": instrument_id},
        operation=_op,
    )


def _dedupe_aliases(aliases: list[str] | None) -> list[tuple[str, str]]:
    """Normalize + dedupe the alias batch, dropping blanks (order preserved)."""
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for raw in aliases or []:
        norm = normalize_alias(raw)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append((norm, raw.strip()))
    return result


async def _ensure_alias_free(
    session: AsyncSession, alias_norm: str, *, owner_instrument_id: str | None = None
) -> None:
    existing = await instrument_repo.get_alias(session, alias_norm)
    if existing is not None and existing.instrument_id != owner_instrument_id:
        raise InstrumentAlreadyRegisteredError(
            f"The alias '{alias_norm}' already resolves to another instrument."
        )


async def _require_instrument(session: AsyncSession, instrument_id: str) -> InstrumentRegistry:
    instrument = await instrument_repo.get_instrument(session, instrument_id)
    if instrument is None:
        raise InstrumentNotFoundError(f"Instrument '{instrument_id}' not found.")
    return instrument


def _check_registry_version(
    instrument: InstrumentRegistry, expected_registry_version: int | None
) -> None:
    if (
        expected_registry_version is not None
        and instrument.registry_version != expected_registry_version
    ):
        raise InstrumentRegistryConflictError(
            f"Expected registry version {expected_registry_version} "
            f"but current is {instrument.registry_version}."
        )


__all__ = ["add_instrument_alias", "deprecate_instrument", "register_instrument"]
