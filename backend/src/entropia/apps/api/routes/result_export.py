"""Result export + artifact drill-down API (doc 15 §7). Thin handlers: parse
body/query/headers -> resolve actor context -> call one command/query. No export
serialization, checksum, cursor or policy logic lives here.

``POST /backtest-results/{id}/exports`` requests a schema-versioned export (V1
synchronous); ``GET /backtest-results/{id}/artifacts/{type}`` is the cursor-paginated
drill-down over the immutable equity / ledger / signal / diagnostics artifacts.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from entropia.application.commands import result_export as export_cmd
from entropia.application.queries import result_artifacts as artifact_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.shared.pagination import MAX_LIMIT

router = APIRouter(tags=["result-export"])

_EXPORTS_PATH = "/backtest-results/{result_id}/exports"
_ARTIFACTS_PATH = "/backtest-results/{result_id}/artifacts/{artifact_type}"

_DEFAULT_ARTIFACT_LIMIT = 50


class RequestExportBody(BaseModel):
    export_type: str
    export_format: str
    filter_spec: dict[str, Any] | None = None


@router.post(_EXPORTS_PATH, status_code=201)
async def request_result_export(
    result_id: str,
    body: RequestExportBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await export_cmd.request_result_export(
        ctx.session,
        ctx.actor,
        result_id=result_id,
        export_type=body.export_type,
        export_format=body.export_format,
        filter_spec=body.filter_spec,
        idempotency_key=idempotency_key,
    )


@router.get(_ARTIFACTS_PATH)
async def query_result_artifact(
    result_id: str,
    artifact_type: str,
    ctx: RequestContext = Depends(request_context),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_ARTIFACT_LIMIT, ge=1, le=MAX_LIMIT),
) -> dict[str, Any]:
    return await artifact_query.query_result_artifact(
        ctx.session,
        ctx.actor,
        result_id=result_id,
        artifact_type=artifact_type,
        cursor=cursor,
        limit=limit,
    )


__all__ = ["router"]
