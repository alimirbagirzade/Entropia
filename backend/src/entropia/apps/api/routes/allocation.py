"""Portfolio / Equity Allocation API (doc 13 §7, §9). Thin handlers: parse the
body/headers -> resolve actor context -> call one application command/query. No
SQL, policy, hashing, or business logic lives here.

All routes are authentication-gated (the query/commands reject Guests with 401).
The draft PUT and the revision POST accept ``If-Match`` as an alternative carrier
of ``expected_row_version`` and read the ``Idempotency-Key`` header; the draft GET
sets an ``ETag`` from the plan row version for later optimistic-concurrency checks.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.queries import allocation_plan as alloc_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.shared.concurrency import etag_for_row_version, row_version_from_if_match

router = APIRouter(tags=["portfolio-allocation"])

_DRAFT_PATH = "/mainboard-compositions/{composition_id}/portfolio-allocation-draft"
_VALIDATE_PATH = "/mainboard-compositions/{composition_id}/portfolio-allocation/validate"
_SYNC_PATH = "/mainboard-compositions/{composition_id}/portfolio-allocation/sync"
_REVISIONS_PATH = "/mainboard-compositions/{composition_id}/portfolio-allocation/revisions"


class MoneyBody(BaseModel):
    amount: str
    currency: str


class AllocationEntryBody(BaseModel):
    composition_item_id: str
    # ``item_type`` is accepted but IGNORED — the server derives it (doc 13 §8.2).
    item_type: str | None = None
    active: bool = True
    equity_share_percent: str | None = None


class PutDraftBody(BaseModel):
    expected_row_version: int | None = None
    enabled: bool = False
    initial_capital: MoneyBody | None = None
    compounding_mode: str | None = None
    reserve_cash_percent: str | None = None
    # Portfolio-level rules (doc 13 §8.4): composition-wide exposure ceiling (% of
    # P0, None = no cap) + cross-item opposing-signal policy (None = KEEP_SEPARATE).
    max_total_exposure_percent: str | None = None
    conflict_policy: str | None = None
    entries: list[AllocationEntryBody] = Field(default_factory=list)


class CreateRevisionBody(BaseModel):
    expected_row_version: int | None = None


def _resolve_expected(body_value: int | None, if_match: str | None) -> int | None:
    if body_value is not None:
        return body_value
    return row_version_from_if_match(if_match)


@router.get(_DRAFT_PATH)
async def get_allocation_draft(
    composition_id: str,
    response: Response,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    result = await alloc_query.get_allocation_draft(
        ctx.session, ctx.actor, composition_id=composition_id
    )
    response.headers["ETag"] = etag_for_row_version(int(result["row_version"]))
    return result


@router.put(_DRAFT_PATH)
async def put_allocation_draft(
    composition_id: str,
    body: PutDraftBody,
    response: Response,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    result = await alloc_cmd.upsert_allocation_draft(
        ctx.session,
        ctx.actor,
        composition_id=composition_id,
        expected_row_version=_resolve_expected(body.expected_row_version, if_match),
        enabled=body.enabled,
        initial_capital=body.initial_capital.model_dump() if body.initial_capital else None,
        compounding_mode=body.compounding_mode,
        reserve_cash_percent=body.reserve_cash_percent,
        max_total_exposure_percent=body.max_total_exposure_percent,
        conflict_policy=body.conflict_policy,
        entries=[entry.model_dump() for entry in body.entries],
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = etag_for_row_version(int(result["row_version"]))
    return result


@router.post(_VALIDATE_PATH)
async def validate_allocation_draft(
    composition_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await alloc_cmd.validate_allocation_draft(
        ctx.session, ctx.actor, composition_id=composition_id
    )


@router.post(_SYNC_PATH)
async def sync_from_mainboard(
    composition_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await alloc_query.sync_preview(ctx.session, ctx.actor, composition_id=composition_id)


@router.post(_REVISIONS_PATH, status_code=201)
async def create_allocation_revision(
    composition_id: str,
    body: CreateRevisionBody,
    response: Response,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    result = await alloc_cmd.create_allocation_revision(
        ctx.session,
        ctx.actor,
        composition_id=composition_id,
        expected_row_version=_resolve_expected(body.expected_row_version, if_match),
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = etag_for_row_version(int(result["row_version"]))
    return result
