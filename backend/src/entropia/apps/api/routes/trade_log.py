"""Trade Log API (doc 05 §8, §9, §10). Thin handlers: parse the body/headers ->
resolve actor context -> call one application command/query. No SQL, policy, hashing
or object-storage logic lives here.

Page access is authentication-gated (commands/queries reject Guests with 401).
Import is a durable async job returning 202 with a stable job id; the actor is
dispatched after the request transaction commits. Pin (``Use This Revision``) and
delete REUSE the Mainboard router's ``PATCH /mainboard-items/{id}`` (pin_revision)
and ``DELETE /work-objects/{root_id}`` — no duplicate endpoints here (CR-01, TL-01:
a Trade Log is a work object, not a package).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from entropia.application.commands import trade_log as tl_cmd
from entropia.application.queries import trade_log as tl_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.infrastructure.queues import enqueue as job_enqueue

router = APIRouter(tags=["trade-log"])


class UploadSourceAssetBody(BaseModel):
    content: str
    content_type: str | None = "text/csv"
    original_filename: str | None = None
    draft_id: str | None = None


class RequestImportBody(BaseModel):
    source_asset_id: str
    instrument_id: str
    # GAP-16 (Master §8.1): an optional free-text scope resolved server-side to a
    # canonical instrument_id BEFORE the durable import is enqueued. Keys:
    # {venue_id, symbol, contract_type} or {alias}. Unresolvable -> 422
    # INSTRUMENT_SCOPE_UNRESOLVABLE (never a silent free-text instrument).
    instrument_scope: dict[str, Any] | None = None
    source_timezone: str = "UTC"
    # Optional {canonical_field: source_header} column mapping (doc 05 §5.2). Absent
    # for exact/aliased canonical headers; required when a header is unmappable
    # otherwise. The server never infers an ambiguous mapping.
    import_mapping: dict[str, str] | None = None


class CreateTradeLogBody(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    workspace_id: str | None = None
    attach: bool = True
    position_index: int | None = None


class CreateRevisionBody(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_head_revision_id: str | None = None


@router.post("/trade-logs/source-assets", status_code=201)
async def upload_source_asset(
    body: UploadSourceAssetBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await tl_cmd.upload_source_asset(
        ctx.session,
        ctx.actor,
        content=body.content.encode("utf-8"),
        content_type=body.content_type,
        original_filename=body.original_filename,
        draft_id=body.draft_id,
        idempotency_key=idempotency_key,
    )


@router.post("/trade-logs/imports", status_code=202)
async def request_import(
    body: RequestImportBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    result = await tl_cmd.request_trade_log_import(
        ctx.session,
        ctx.actor,
        source_asset_id=body.source_asset_id,
        instrument_id=body.instrument_id,
        instrument_scope=body.instrument_scope,
        source_timezone=body.source_timezone,
        import_mapping=body.import_mapping,
        idempotency_key=idempotency_key,
    )
    # Dispatch the durable actor after the request tx commits (job row already durable).
    from entropia.apps.worker.actors import run_trade_log_import

    job_enqueue.send_job(run_trade_log_import, result["job_id"])
    return result


@router.get("/trade-logs/imports/{job_id}")
async def get_import_report(
    job_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await tl_query.get_import_report(ctx.session, ctx.actor, job_id=job_id)


@router.post("/trade-logs", status_code=201)
async def create_trade_log(
    body: CreateTradeLogBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await tl_cmd.create_trade_log_and_attach(
        ctx.session,
        ctx.actor,
        payload=body.payload,
        workspace_id=body.workspace_id,
        attach=body.attach,
        position_index=body.position_index,
        idempotency_key=idempotency_key,
    )


@router.post("/trade-logs/{root_id}/revisions", status_code=201)
async def create_trade_log_revision(
    root_id: str,
    body: CreateRevisionBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await tl_cmd.create_trade_log_revision(
        ctx.session,
        ctx.actor,
        root_id=root_id,
        payload=body.payload,
        expected_head_revision_id=body.expected_head_revision_id,
        idempotency_key=idempotency_key,
    )


@router.get("/trade-logs/{root_id}")
async def get_trade_log(
    root_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await tl_query.get_trade_log(ctx.session, ctx.actor, root_id=root_id)
