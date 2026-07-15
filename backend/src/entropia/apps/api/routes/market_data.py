"""Market Data API (doc 11). Thin handlers: parse -> resolve actor -> call one
application command/query. No SQL, queue, object-storage, or policy here.

Async analysis returns 202 with the durable job id (the job row is the source of
truth; browser close never cancels it). Approval is Admin-only and rejects
non-Admins with 403 before touching the domain.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Header, Query, Response, UploadFile
from pydantic import BaseModel, Field

from entropia.application.commands import market_data as md_cmd
from entropia.application.queries import market_data as md_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.market_data.enums import MarketDataType, TimezoneMode
from entropia.domain.market_data.value_objects import TimezoneSpec
from entropia.infrastructure.queues import enqueue as job_enqueue
from entropia.shared.concurrency import etag_for_row_version, row_version_from_if_match
from entropia.shared.pagination import PageParams

router = APIRouter(tags=["market-data"])


class CreateDatasetRequest(BaseModel):
    market_data_type: MarketDataType
    payload: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None
    instrument_id: str | None = None
    # GAP-16 (Master §8.1): a free-text scope resolved server-side to a canonical
    # instrument_id. Keys: {venue_id, symbol, contract_type} or {alias}. An
    # unresolvable scope -> 422 INSTRUMENT_SCOPE_UNRESOLVABLE (never a silent free-text).
    instrument_scope: dict[str, Any] | None = None


class FinalizeUploadRequest(BaseModel):
    asset_id: str


class ConfirmMappingRequest(BaseModel):
    market_data_type: MarketDataType
    source_columns: list[str]
    confirmed_mapping: dict[str, str | None] | None = None


class CreateRevisionRequest(BaseModel):
    market_data_type: MarketDataType
    payload: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None
    instrument_id: str | None = None
    timezone_mode: TimezoneMode
    timezone_iana: str | None = None


class ApproveRequest(BaseModel):
    revision_id: str
    note: str | None = None


class DeprecateRequest(BaseModel):
    revision_id: str
    note: str | None = None


class DeleteDatasetRequest(BaseModel):
    reason: str | None = None


@router.post("/market-datasets", status_code=201)
async def create_dataset(
    body: CreateDatasetRequest,
    response: Response,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    root, revision = await md_cmd.create_market_dataset(
        ctx.session,
        ctx.actor,
        market_data_type=body.market_data_type,
        payload=body.payload,
        title=body.title,
        instrument_id=body.instrument_id,
        instrument_scope=body.instrument_scope,
    )
    response.headers["ETag"] = etag_for_row_version(root.row_version)
    return {
        "entity_id": root.entity_id,
        "revision_id": revision.revision_id,
        "revision_state": str(revision.revision_state),
    }


@router.post("/market-datasets/{entity_id}/raw-uploads", status_code=201)
async def start_upload(
    entity_id: str,
    file: UploadFile = File(...),
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Real multipart byte transfer (F-01): the object key, SHA-256 digest,
    byte size, and content type are all derived server-side from the bytes —
    the client never supplies storage metadata. The read is bounded by
    ``MAX_UPLOAD_BYTES + 1`` so an oversized upload is rejected without
    buffering an unbounded payload into memory.
    """
    content = await file.read(md_cmd.MAX_UPLOAD_BYTES + 1)
    return await md_cmd.start_market_raw_upload(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        content=content,
        content_type=file.content_type,
        original_filename=file.filename,
        idempotency_key=idempotency_key,
    )


@router.post("/market-datasets/{entity_id}/raw-uploads/finalize")
async def finalize_upload(
    entity_id: str,
    body: FinalizeUploadRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await md_cmd.finalize_market_raw_upload(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        asset_id=body.asset_id,
        idempotency_key=idempotency_key,
    )


@router.post("/market-datasets/{entity_id}/analysis", status_code=202)
async def request_analysis(
    entity_id: str,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    result = await md_cmd.request_market_dataset_analysis(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        idempotency_key=idempotency_key,
    )
    # Dispatch the actor after the request transaction commits (the job row is
    # already durable). Imported lazily to keep route import broker-free.
    from entropia.apps.worker.actors import run_market_data_analysis

    job_enqueue.send_job(run_market_data_analysis, result["job_id"])
    return result


@router.post("/market-datasets/{entity_id}/schema-mapping")
async def confirm_mapping(
    entity_id: str,
    body: ConfirmMappingRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    mapping = await md_cmd.confirm_market_schema_mapping(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        market_data_type=body.market_data_type,
        source_columns=body.source_columns,
        confirmed_mapping=body.confirmed_mapping,
    )
    return {
        "mapping_id": mapping.mapping_id,
        "review_required": mapping.review_required,
        "confirmed_mapping": mapping.confirmed_mapping,
    }


@router.post("/market-datasets/{entity_id}/revisions")
async def create_revision(
    entity_id: str,
    body: CreateRevisionRequest,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    timezone_spec = TimezoneSpec(mode=body.timezone_mode, iana=body.timezone_iana)
    return await md_cmd.create_market_dataset_revision(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        payload=body.payload,
        market_data_type=body.market_data_type,
        title=body.title,
        instrument_id=body.instrument_id,
        timezone_spec=timezone_spec,
        expected_row_version=row_version_from_if_match(if_match),
        idempotency_key=idempotency_key,
    )


@router.post("/market-datasets/{entity_id}/approve")
async def approve(
    entity_id: str,
    body: ApproveRequest,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await md_cmd.approve_market_dataset_revision(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        revision_id=body.revision_id,
        note=body.note,
        expected_row_version=row_version_from_if_match(if_match),
        idempotency_key=idempotency_key,
    )


@router.post("/market-datasets/{entity_id}/successor")
async def create_successor(
    entity_id: str,
    body: CreateRevisionRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    revision = await md_cmd.create_successor_revision(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        payload=body.payload,
        market_data_type=body.market_data_type,
        title=body.title,
        instrument_id=body.instrument_id,
    )
    return {
        "entity_id": entity_id,
        "revision_id": revision.revision_id,
        "revision_no": revision.revision_no,
        "revision_state": str(revision.revision_state),
    }


@router.post("/market-datasets/{entity_id}/deprecate")
async def deprecate(
    entity_id: str,
    body: DeprecateRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await md_cmd.deprecate_market_dataset_revision(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        revision_id=body.revision_id,
        note=body.note,
    )


@router.delete("/market-datasets/{entity_id}", status_code=204)
async def soft_delete(
    entity_id: str,
    body: DeleteDatasetRequest | None = None,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> Response:
    """Owner-or-Admin soft delete (doc 11 §10.1, Flow F). The Market Data page has
    no delete control (doc 11 §2.1); this is the domain/Agent-Gateway surface."""
    await md_cmd.soft_delete_market_dataset(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        reason=body.reason if body else None,
        expected_row_version=row_version_from_if_match(if_match),
    )
    return Response(status_code=204)


@router.get("/market-datasets")
async def list_datasets(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await md_query.list_market_dataset_revisions(
        ctx.session, ctx.actor, PageParams(cursor=cursor, limit=limit)
    )


@router.get("/market-datasets/{entity_id}")
async def get_detail(
    entity_id: str,
    response: Response,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    detail = await md_query.get_market_dataset_detail(ctx.session, ctx.actor, entity_id=entity_id)
    response.headers["ETag"] = etag_for_row_version(int(detail["row_version"]))
    return detail


@router.get("/market-datasets/{entity_id}/approved-bundle")
async def resolve_bundle(
    entity_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await md_query.resolve_approved_market_data_bundle(ctx.session, entity_id=entity_id)
