"""Research Data API (doc 12). Thin handlers: parse -> resolve actor -> call one
application command/query. No SQL, queue, object-storage, or policy here.

Async analysis returns 202 with the durable job id (the job row is the source of
truth; browser close never cancels it). Approval and revocation are Admin-only
and reject non-Admins with 403 before touching the domain.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, Field

from entropia.application.commands import research_data as rd_cmd
from entropia.application.jobs import research_data as rd_jobs
from entropia.application.queries import research_data as rd_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.research_data import policy as rd_policy
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    EventTimeSemantics,
    ResearchCategory,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.domain.research_data.value_objects import (
    AvailableTimeSpec,
    CategorySpec,
    FieldDefinition,
    ResearchTimezoneSpec,
)
from entropia.infrastructure.queues import enqueue as job_enqueue
from entropia.shared.concurrency import etag_for_row_version, row_version_from_if_match
from entropia.shared.pagination import PageParams


async def _require_page_access(ctx: RequestContext = Depends(request_context)) -> None:
    """Gate EVERY Research Data endpoint on Admin/Supervisor/Agent page access
    (doc 12 §2/§4). Users and Guests are blocked here, before any handler runs."""
    rd_policy.ensure_can_access_page(ctx.actor)


router = APIRouter(tags=["research-data"], dependencies=[Depends(_require_page_access)])


class CreateDatasetRequest(BaseModel):
    market_entity_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    category: ResearchCategory
    usage_scope: UsageScope
    custom_category: str | None = None
    display_name: str | None = None
    provider_name: str | None = None


class StartUploadRequest(BaseModel):
    object_key: str
    content_digest: str
    size_bytes: int = Field(ge=0)
    content_type: str | None = None
    original_filename: str | None = None


class FinalizeUploadRequest(BaseModel):
    asset_id: str


class CreateRevisionRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    category: ResearchCategory
    usage_scope: UsageScope
    timezone_mode: ResearchTimezoneMode
    custom_category: str | None = None
    timezone_iana: str | None = None
    market_entity_id: str | None = None
    display_name: str | None = None
    provider_name: str | None = None
    base_revision_id: str | None = None


class SetTimePolicyRequest(BaseModel):
    event_time_semantics: EventTimeSemantics
    available_time_policy: AvailableTimePolicy
    timezone_mode: ResearchTimezoneMode
    delay_seconds: int | None = None
    timezone_iana: str | None = None


class FieldDefinitionRequest(BaseModel):
    field_name: str
    semantic_type: str
    measurement_method: str
    null_semantics: str
    event_time_source: str
    availability_rule: str
    allowed_usage: str
    unit_or_scale: str | None = None


class FeatureDefinitionRequest(BaseModel):
    feature_name: str
    definition: dict[str, Any]
    feature_version: int = 1
    approval_state: str | None = None


class ApproveRequest(BaseModel):
    revision_id: str
    note: str | None = None


class RevokeRequest(BaseModel):
    revision_id: str
    note: str | None = None


class CompileBundleRequest(BaseModel):
    research_revision_ids: list[str]
    task_id: str | None = None
    run_request_id: str | None = None


@router.post("/research-datasets", status_code=201)
async def create_dataset(
    body: CreateDatasetRequest,
    response: Response,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    category = CategorySpec(category=body.category, custom_category=body.custom_category)
    root, revision = await rd_cmd.create_research_dataset(
        ctx.session,
        ctx.actor,
        market_entity_id=body.market_entity_id,
        payload=body.payload,
        category=category,
        usage_scope=body.usage_scope,
        display_name=body.display_name,
        provider_name=body.provider_name,
    )
    response.headers["ETag"] = etag_for_row_version(root.row_version)
    return {
        "entity_id": root.entity_id,
        "revision_id": revision.revision_id,
        "revision_state": str(revision.revision_state),
    }


@router.post("/research-datasets/{entity_id}/upload-session", status_code=201)
async def create_upload_session(
    entity_id: str,
    body: StartUploadRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    asset = await rd_cmd.create_upload_session(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        object_key=body.object_key,
        content_digest=body.content_digest,
        size_bytes=body.size_bytes,
        content_type=body.content_type,
        original_filename=body.original_filename,
    )
    return {"asset_id": asset.asset_id, "entity_id": entity_id}


@router.post("/research-datasets/{entity_id}/upload-session/finalize")
async def finalize_upload(
    entity_id: str,
    body: FinalizeUploadRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await rd_cmd.finalize_upload(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        asset_id=body.asset_id,
        idempotency_key=idempotency_key,
    )


@router.post("/research-datasets/{entity_id}/analysis", status_code=202)
async def request_analysis(
    entity_id: str,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    result = await rd_cmd.request_research_dataset_analysis(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        idempotency_key=idempotency_key,
    )
    # Dispatch the actor after the request transaction commits (the job row is
    # already durable). Imported lazily to keep route import broker-free.
    from entropia.apps.worker.actors import run_research_data_analysis

    job_enqueue.send_job(run_research_data_analysis, result["job_id"])
    return result


@router.post("/research-datasets/{entity_id}/revisions")
async def create_revision(
    entity_id: str,
    body: CreateRevisionRequest,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    category = CategorySpec(category=body.category, custom_category=body.custom_category)
    timezone_spec = ResearchTimezoneSpec(mode=body.timezone_mode, iana=body.timezone_iana)
    return await rd_cmd.create_research_dataset_revision(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        payload=body.payload,
        category=category,
        usage_scope=body.usage_scope,
        timezone_spec=timezone_spec,
        market_entity_id=body.market_entity_id,
        display_name=body.display_name,
        provider_name=body.provider_name,
        base_revision_id=body.base_revision_id,
        expected_row_version=row_version_from_if_match(if_match),
        idempotency_key=idempotency_key,
    )


@router.post("/research-datasets/{entity_id}/time-policy")
async def set_time_policy(
    entity_id: str,
    body: SetTimePolicyRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    available_time = AvailableTimeSpec(
        policy=body.available_time_policy, delay_seconds=body.delay_seconds
    )
    timezone_spec = ResearchTimezoneSpec(mode=body.timezone_mode, iana=body.timezone_iana)
    policy = await rd_cmd.set_time_policy(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        event_time_semantics=body.event_time_semantics,
        available_time=available_time,
        timezone_spec=timezone_spec,
    )
    return {
        "time_policy_id": policy.time_policy_id,
        "entity_id": entity_id,
        "available_time_policy": str(policy.available_time_policy),
    }


@router.post("/research-datasets/{entity_id}/field-definitions", status_code=201)
async def define_field(
    entity_id: str,
    body: FieldDefinitionRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    field = FieldDefinition(
        field_name=body.field_name,
        semantic_type=body.semantic_type,
        measurement_method=body.measurement_method,
        null_semantics=body.null_semantics,
        event_time_source=body.event_time_source,
        availability_rule=body.availability_rule,
        allowed_usage=body.allowed_usage,
        unit_or_scale=body.unit_or_scale,
    )
    row = await rd_cmd.define_field(ctx.session, ctx.actor, entity_id=entity_id, field=field)
    return {"field_definition_id": row.field_definition_id, "field_name": row.field_name}


@router.post("/research-datasets/{entity_id}/feature-definitions", status_code=201)
async def define_feature(
    entity_id: str,
    body: FeatureDefinitionRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    row = await rd_cmd.define_feature(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        feature_name=body.feature_name,
        definition=body.definition,
        feature_version=body.feature_version,
        approval_state=body.approval_state,
    )
    return {
        "feature_definition_id": row.feature_definition_id,
        "feature_name": row.feature_name,
    }


@router.post("/research-datasets/{entity_id}/approve")
async def approve(
    entity_id: str,
    body: ApproveRequest,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await rd_cmd.approve_research_dataset_revision(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        revision_id=body.revision_id,
        note=body.note,
        expected_row_version=row_version_from_if_match(if_match),
        idempotency_key=idempotency_key,
    )


@router.post("/research-datasets/{entity_id}/revoke")
async def revoke(
    entity_id: str,
    body: RevokeRequest,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await rd_cmd.revoke_research_dataset_approval(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        revision_id=body.revision_id,
        note=body.note,
        expected_row_version=row_version_from_if_match(if_match),
        idempotency_key=idempotency_key,
    )


@router.get("/research-datasets")
async def list_datasets(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await rd_query.list_research_dataset_revisions(
        ctx.session, ctx.actor, PageParams(cursor=cursor, limit=limit)
    )


@router.get("/research-datasets/{entity_id}")
async def get_detail(
    entity_id: str,
    response: Response,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    detail = await rd_query.get_research_dataset_detail(ctx.session, ctx.actor, entity_id=entity_id)
    response.headers["ETag"] = etag_for_row_version(int(detail["row_version"]))
    return detail


@router.post("/research-datasets/bundles/agent")
async def compile_agent_bundle(
    body: CompileBundleRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await rd_jobs.compile_agent_data_bundle(
        ctx.session,
        ctx.actor,
        research_revision_ids=body.research_revision_ids,
        task_id=body.task_id,
    )


@router.post("/research-datasets/bundles/backtest-evidence")
async def compile_evidence_bundle(
    body: CompileBundleRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await rd_jobs.compile_backtest_evidence_bundle(
        ctx.session,
        ctx.actor,
        research_revision_ids=body.research_revision_ids,
        run_request_id=body.run_request_id,
    )
