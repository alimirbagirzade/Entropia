"""Arrange Metrics API (doc 17 §7). Thin handlers: parse query/body/headers ->
resolve actor context -> call one command/query. No registry, selection, hashing
or policy logic lives here.

``GET /metric-definitions`` is the registry (availability-filtered); ``GET
/metric-profiles/resolved`` returns the caller's effective profile (personal or
System Default); ``POST /metric-profiles/{profile_id}/revisions`` is the single
Apply/Lock/Unlock append (``is_locked`` + selection drive the transition);
``GET /backtest-results/{id}/metrics`` hydrates a Result's immutable metrics through
the resolved profile (presentation-only, no recompute).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from entropia.application.commands import metric_profile as metric_profile_cmd
from entropia.application.queries import metric_profile as metric_profile_query
from entropia.apps.api.deps import RequestContext, request_context

router = APIRouter(tags=["arrange-metrics"])

_DEFINITIONS_PATH = "/metric-definitions"
_RESOLVED_PATH = "/metric-profiles/resolved"
_REVISIONS_PATH = "/metric-profiles/{profile_id}/revisions"
_RESULT_METRICS_PATH = "/backtest-results/{result_id}/metrics"


class ApplyMetricProfileBody(BaseModel):
    selected_metric_codes: list[str] = Field(min_length=1)
    is_locked: bool = False
    expected_profile_revision_id: str | None = None


@router.get(_DEFINITIONS_PATH)
async def list_metric_definitions(
    ctx: RequestContext = Depends(request_context),
    availability: str | None = Query(default=None),
) -> dict[str, Any]:
    return await metric_profile_query.list_metric_definitions(
        ctx.session, ctx.actor, availability=availability
    )


@router.get(_RESOLVED_PATH)
async def get_resolved_metric_profile(
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await metric_profile_query.get_resolved_metric_profile(ctx.session, ctx.actor)


@router.post(_REVISIONS_PATH)
async def create_metric_profile_revision(
    profile_id: str,
    body: ApplyMetricProfileBody,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    expected = body.expected_profile_revision_id
    if expected is None and if_match is not None:
        expected = if_match.strip().strip('"')
    return await metric_profile_cmd.create_metric_profile_revision(
        ctx.session,
        ctx.actor,
        profile_id=profile_id,
        expected_profile_revision_id=expected,
        selected_metric_codes=body.selected_metric_codes,
        is_locked=body.is_locked,
        idempotency_key=idempotency_key,
    )


@router.get(_RESULT_METRICS_PATH)
async def get_result_metrics(
    result_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await metric_profile_query.get_result_metrics(
        ctx.session, ctx.actor, result_id=result_id
    )


__all__ = ["router"]
