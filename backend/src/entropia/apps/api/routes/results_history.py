"""Results History API (doc 16 §7, §9.3). Thin handlers: parse query/body ->
resolve actor context -> call one read query (or the reused 5a soft-delete command).
No SQL, sort or cursor logic lives here.

``GET /backtest-results`` is the server-side history index (sort + opaque cursor);
``POST /backtest-results/compare`` reads exactly two immutable results side by side;
``POST /backtest-results/{id}/delete`` is the doc-16 soft-delete affordance that
REUSES the 5a ``soft_delete_backtest_result`` command (no new delete logic). The
collapsed-row read + the existing ``GET``/``DELETE /backtest-results/{id}`` stay in
the Stage 5a ``backtest`` router.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.queries import results_history as history_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.shared.concurrency import row_version_from_if_match
from entropia.shared.pagination import MAX_LIMIT

router = APIRouter(tags=["results-history"])

_LIST_PATH = "/backtest-results"
_COMPARE_PATH = "/backtest-results/compare"
_DELETE_PATH = "/backtest-results/{result_id}/delete"

_DEFAULT_HISTORY_LIMIT = 25


class CompareBody(BaseModel):
    result_ids: list[str] = Field(min_length=2, max_length=2)


class DeleteResultBody(BaseModel):
    expected_row_version: int | None = None


@router.get(_LIST_PATH)
async def list_backtest_results(
    ctx: RequestContext = Depends(request_context),
    sort: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_LIMIT),
) -> dict[str, Any]:
    return await history_query.list_backtest_results(
        ctx.session, ctx.actor, sort=sort, cursor=cursor, limit=limit
    )


@router.post(_COMPARE_PATH)
async def compare_backtest_results(
    body: CompareBody,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await history_query.compare_backtest_results(
        ctx.session, ctx.actor, result_ids=body.result_ids
    )


@router.post(_DELETE_PATH)
async def soft_delete_backtest_result(
    result_id: str,
    body: DeleteResultBody | None = None,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    payload = body or DeleteResultBody()
    expected = payload.expected_row_version
    if expected is None and if_match is not None:
        expected = row_version_from_if_match(if_match)
    return await backtest_cmd.soft_delete_backtest_result(
        ctx.session,
        ctx.actor,
        result_id=result_id,
        expected_row_version=expected,
        idempotency_key=idempotency_key,
    )


__all__ = ["router"]
