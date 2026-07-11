"""Future Dev endpoints (Stage 7b, doc 22 §8).

Thin handlers: parse body/headers -> one application command/query. The
capability list/detail and the Graphic View overview are read-only registry
projections for any authenticated principal. The Admin lifecycle transition
re-checks Admin at the ROUTE and the command re-checks it at the SERVICE
(``require_capability_admin`` — UI visibility is never authorization, doc 22
§3). The operational POSTs exist as registered generic capability routes: the
server re-checks the registry state on every dispatch, so while a capability
is below Limited/Active they return CAPABILITY_NOT_ACTIVE and create nothing
(CR-09, FD-02). There is NO Live Trade order endpoint in V1 (FD-12).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from entropia.application.commands.capability import (
    create_analysis_artifact,
    query_view_dataset,
    transition_capability,
)
from entropia.application.queries.capability import (
    get_analysis_artifact,
    get_capability,
    get_graphic_view_overview,
    get_view_dataset,
    list_analysis_artifacts,
    list_capabilities,
    list_view_datasets,
)
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity.policy import require_capability_admin

router = APIRouter(tags=["future-dev"])

_CAPABILITIES_PATH = "/capabilities"
_CAPABILITY_PATH = "/capabilities/{capability_key}"
_TRANSITIONS_PATH = "/capabilities/{capability_key}/lifecycle-transitions"
_GRAPHIC_VIEW_OVERVIEW_PATH = "/future-dev/graphic_view/overview"
_VIEW_DATASET_QUERY_PATH = "/view-datasets/query"
_VIEW_DATASETS_PATH = "/view-datasets"
_VIEW_DATASET_PATH = "/view-datasets/{view_dataset_id}"
_ANALYSIS_ARTIFACTS_PATH = "/analysis-artifacts"
_ANALYSIS_ARTIFACT_PATH = "/analysis-artifacts/{artifact_id}"


class LifecycleTransitionRequest(BaseModel):
    to_state: str
    reason: str
    expected_registry_version: int
    dependency_snapshot: dict[str, Any] | None = None


class ViewDatasetQueryRequest(BaseModel):
    source_manifest_refs: list[str]
    schema_version: str
    series_refs: list[str] | None = None
    marker_refs: list[str] | None = None
    range_spec: dict[str, Any] | None = None


class AnalysisArtifactRequest(BaseModel):
    artifact_type: str
    input_manifest_refs: list[str]
    method_version: str
    output_ref: str | None = None


@router.get(_CAPABILITIES_PATH)
async def capabilities_index(
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await list_capabilities(ctx.session, ctx.actor)


@router.get(_CAPABILITY_PATH)
async def capability_detail(
    capability_key: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await get_capability(ctx.session, ctx.actor, capability_key=capability_key)


@router.post(_TRANSITIONS_PATH)
async def lifecycle_transition(
    capability_key: str,
    body: LifecycleTransitionRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    require_capability_admin(ctx.actor)
    return await transition_capability(
        ctx.session,
        ctx.actor,
        capability_key=capability_key,
        to_state=body.to_state,
        reason=body.reason,
        expected_registry_version=body.expected_registry_version,
        dependency_snapshot=body.dependency_snapshot,
        idempotency_key=idempotency_key,
    )


@router.get(_GRAPHIC_VIEW_OVERVIEW_PATH)
async def graphic_view_overview(
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await get_graphic_view_overview(ctx.session, ctx.actor)


@router.post(_VIEW_DATASET_QUERY_PATH, status_code=201)
async def view_dataset_query(
    body: ViewDatasetQueryRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await query_view_dataset(
        ctx.session,
        ctx.actor,
        source_manifest_refs=body.source_manifest_refs,
        schema_version=body.schema_version,
        series_refs=body.series_refs,
        marker_refs=body.marker_refs,
        range_spec=body.range_spec,
        idempotency_key=idempotency_key,
    )


@router.post(_ANALYSIS_ARTIFACTS_PATH, status_code=201)
async def analysis_artifact_create(
    body: AnalysisArtifactRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await create_analysis_artifact(
        ctx.session,
        ctx.actor,
        artifact_type=body.artifact_type,
        input_manifest_refs=body.input_manifest_refs,
        method_version=body.method_version,
        output_ref=body.output_ref,
        idempotency_key=idempotency_key,
    )


# --------------------------------------------------------------------------- #
# Operational output history (owner-scoped read, doc 22 §7) — the read surface  #
# for the outputs the operational POSTs above create.                          #
# --------------------------------------------------------------------------- #


@router.get(_VIEW_DATASETS_PATH)
async def view_datasets_index(
    cursor: str | None = None,
    limit: int | None = None,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await list_view_datasets(ctx.session, ctx.actor, cursor=cursor, limit=limit)


@router.get(_VIEW_DATASET_PATH)
async def view_dataset_detail(
    view_dataset_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await get_view_dataset(ctx.session, ctx.actor, view_dataset_id=view_dataset_id)


@router.get(_ANALYSIS_ARTIFACTS_PATH)
async def analysis_artifacts_index(
    artifact_type: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await list_analysis_artifacts(
        ctx.session,
        ctx.actor,
        artifact_type=artifact_type,
        cursor=cursor,
        limit=limit,
    )


@router.get(_ANALYSIS_ARTIFACT_PATH)
async def analysis_artifact_detail(
    artifact_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await get_analysis_artifact(ctx.session, ctx.actor, artifact_id=artifact_id)


__all__ = ["router"]
