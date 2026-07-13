"""Canonical Instrument Registry API (GAP-16; Master Reference §8.1, §9.1).

Thin handlers: parse -> resolve actor -> call one application command/query. No
SQL, queue, object-storage or policy here. Registration + read are open to any
authenticated actor (reference data the workspace shares); deprecation is
Admin-only and carries the registry_version as the X-Registry-Version OCC header
(a plain int, NOT the If-Match "rv-N" ETag) + a fresh Idempotency-Key. The
resolve endpoint turns a free-text instrument scope into a canonical instrument
(Master §8.1 "instrument scope must resolve").
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, Field

from entropia.application.commands import instrument as instrument_cmd
from entropia.application.queries import instrument as instrument_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.instrument.enums import InstrumentState
from entropia.shared.concurrency import etag_for_row_version
from entropia.shared.pagination import PageParams

router = APIRouter(tags=["instrument-registry"])

_REGISTRY_VERSION_HEADER = "X-Registry-Version"


def _registry_version(value: str | None) -> int | None:
    """Parse the optimistic-concurrency registry-version token header."""
    if not value:
        return None
    try:
        return int(value.strip().strip('"'))
    except ValueError:
        return None


class RegisterInstrumentRequest(BaseModel):
    venue_id: str
    symbol: str
    contract_type: str
    display_name: str
    base_asset: str | None = None
    quote_asset: str | None = None
    settlement_asset: str | None = None
    multiplier: str | None = None
    market_class: str | None = None
    aliases: list[str] = Field(default_factory=list)


class AddAliasRequest(BaseModel):
    alias: str


class DeprecateInstrumentRequest(BaseModel):
    reason: str


class ResolveScopeRequest(BaseModel):
    venue_id: str | None = None
    symbol: str | None = None
    contract_type: str | None = None
    alias: str | None = None


@router.post("/instruments", status_code=201)
async def register_instrument(
    body: RegisterInstrumentRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await instrument_cmd.register_instrument(
        ctx.session,
        ctx.actor,
        venue_id=body.venue_id,
        symbol=body.symbol,
        contract_type=body.contract_type,
        display_name=body.display_name,
        base_asset=body.base_asset,
        quote_asset=body.quote_asset,
        settlement_asset=body.settlement_asset,
        multiplier=body.multiplier,
        market_class=body.market_class,
        aliases=body.aliases,
        idempotency_key=idempotency_key,
    )


@router.get("/instruments")
async def list_instruments(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    state: InstrumentState | None = Query(default=None),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await instrument_query.list_instruments(
        ctx.session,
        ctx.actor,
        PageParams(cursor=cursor, limit=limit),
        state=state,
    )


@router.get("/instruments/{instrument_id}")
async def get_instrument(
    instrument_id: str,
    response: Response,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    detail = await instrument_query.get_instrument_detail(
        ctx.session, ctx.actor, instrument_id=instrument_id
    )
    response.headers["ETag"] = etag_for_row_version(int(detail["row_version"]))
    return detail


@router.post("/instruments/{instrument_id}/aliases", status_code=201)
async def add_alias(
    instrument_id: str,
    body: AddAliasRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await instrument_cmd.add_instrument_alias(
        ctx.session,
        ctx.actor,
        instrument_id=instrument_id,
        alias=body.alias,
        idempotency_key=idempotency_key,
    )


@router.post("/instruments/{instrument_id}/deprecate")
async def deprecate_instrument(
    instrument_id: str,
    body: DeprecateInstrumentRequest,
    ctx: RequestContext = Depends(request_context),
    registry_version: str | None = Header(default=None, alias=_REGISTRY_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await instrument_cmd.deprecate_instrument(
        ctx.session,
        ctx.actor,
        instrument_id=instrument_id,
        reason=body.reason,
        expected_registry_version=_registry_version(registry_version),
        idempotency_key=idempotency_key,
    )


@router.post("/instruments/resolve")
async def resolve_scope(
    body: ResolveScopeRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    # A pure read over the registry; any authenticated actor may resolve a scope.
    require_authenticated(ctx.actor)
    return await instrument_query.resolve_scope(
        ctx.session,
        venue_id=body.venue_id,
        symbol=body.symbol,
        contract_type=body.contract_type,
        alias=body.alias,
    )
