"""Trading Signal API (doc 04 §7, §8, §9). Thin handlers: parse the body/headers ->
resolve actor context -> call one application command/query. No SQL, policy, hashing
or object-storage logic lives here.

Page access is authentication-gated (commands/queries reject Guests with 401).
Import is a durable async job returning 202 with a stable job id; the actor is
dispatched after the request transaction commits. Pin (``Use This Revision``) and
delete REUSE the Mainboard router's ``PATCH /mainboard-items/{id}`` (pin_revision)
and ``DELETE /work-objects/{root_id}`` — no duplicate endpoints here (CR-01: a
Trading Signal is a work object, not a package).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from entropia.application.commands import trading_signal as ts_cmd
from entropia.application.queries import trading_signal as ts_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.infrastructure.queues import enqueue as job_enqueue

router = APIRouter(tags=["trading-signal"])


class UploadSourceAssetBody(BaseModel):
    content: str
    content_type: str | None = "text/csv"
    original_filename: str | None = None
    draft_id: str | None = None


class RequestImportBody(BaseModel):
    source_asset_id: str
    instrument_id: str
    source_timezone: str = "UTC"
    # Optional {canonical_field: source_header} column mapping (doc 04 §5.1). Absent
    # for exact/aliased canonical headers; an explicit mapping is what lets a legacy
    # ledger be accepted as a Trading Signal. The server never infers an ambiguous one.
    import_mapping: dict[str, str] | None = None


class CreateTradingSignalBody(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    workspace_id: str | None = None
    attach: bool = True
    position_index: int | None = None


class CreateRevisionBody(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_head_revision_id: str | None = None


@router.post("/trading-signals/source-assets", status_code=201)
async def upload_source_asset(
    body: UploadSourceAssetBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await ts_cmd.upload_source_asset(
        ctx.session,
        ctx.actor,
        content=body.content.encode("utf-8"),
        content_type=body.content_type,
        original_filename=body.original_filename,
        draft_id=body.draft_id,
        idempotency_key=idempotency_key,
    )


@router.post("/trading-signals/imports", status_code=202)
async def request_import(
    body: RequestImportBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    result = await ts_cmd.request_trading_signal_import(
        ctx.session,
        ctx.actor,
        source_asset_id=body.source_asset_id,
        instrument_id=body.instrument_id,
        source_timezone=body.source_timezone,
        import_mapping=body.import_mapping,
        idempotency_key=idempotency_key,
    )
    # Dispatch the durable actor after the request tx commits (job row already durable).
    from entropia.apps.worker.actors import run_trading_signal_import

    job_enqueue.send_job(run_trading_signal_import, result["job_id"])
    return result


@router.get("/trading-signals/imports/{job_id}")
async def get_import_report(
    job_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await ts_query.get_import_report(ctx.session, ctx.actor, job_id=job_id)


@router.post("/trading-signals", status_code=201)
async def create_trading_signal(
    body: CreateTradingSignalBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await ts_cmd.create_trading_signal_and_attach(
        ctx.session,
        ctx.actor,
        payload=body.payload,
        workspace_id=body.workspace_id,
        attach=body.attach,
        position_index=body.position_index,
        idempotency_key=idempotency_key,
    )


@router.post("/trading-signals/{root_id}/revisions", status_code=201)
async def create_trading_signal_revision(
    root_id: str,
    body: CreateRevisionBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await ts_cmd.create_trading_signal_revision(
        ctx.session,
        ctx.actor,
        root_id=root_id,
        payload=body.payload,
        expected_head_revision_id=body.expected_head_revision_id,
        idempotency_key=idempotency_key,
    )


@router.get("/trading-signals/{root_id}")
async def get_trading_signal(
    root_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await ts_query.get_trading_signal(ctx.session, ctx.actor, root_id=root_id)
