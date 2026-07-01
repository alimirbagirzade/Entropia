"""Backtest RUN + Results API (doc 15 §7, §9). Thin handlers: parse body/headers ->
resolve actor context -> call one application command/query. No SQL, policy,
hashing or manifest logic lives here.

RUN admission returns 202 (durable async job); the client never waits on the
engine (doc 15 §8.2). The durable ``jobs`` row is written in the command tx; the
actor is dispatched AFTER the handler returns (mirrors the other worker routes).
``expected_fingerprint`` (body or ``If-Match``) guards the RUN; a Result soft
delete carries ``expected_row_version`` (body or numeric ``If-Match``).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.queries import backtest_run as backtest_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.infrastructure.queues import enqueue as job_enqueue
from entropia.shared.concurrency import row_version_from_if_match

router = APIRouter(tags=["backtest"])

_RUNS_PATH = "/mainboard-compositions/{composition_id}/backtest-runs"
_RUN_PATH = "/backtest-runs/{run_id}"
_RETRY_PATH = "/backtest-runs/{run_id}/retries"
_RESULT_PATH = "/backtest-results/{result_id}"


class RequestRunBody(BaseModel):
    expected_fingerprint: str | None = None
    ready_report_id: str | None = None


class DeleteResultBody(BaseModel):
    expected_row_version: int | None = None


def _resolve_fingerprint(body_value: str | None, if_match: str | None) -> str | None:
    if body_value is not None:
        return body_value
    if if_match is None:
        return None
    numeric = row_version_from_if_match(if_match)
    if numeric is not None:
        return str(numeric)
    return if_match.strip().strip('"')


@router.post(_RUNS_PATH, status_code=202)
async def request_backtest_run(
    composition_id: str,
    body: RequestRunBody | None = None,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    payload = body or RequestRunBody()
    result = await backtest_cmd.request_backtest_run(
        ctx.session,
        ctx.actor,
        composition_id=composition_id,
        expected_fingerprint=_resolve_fingerprint(payload.expected_fingerprint, if_match),
        ready_report_id=payload.ready_report_id,
        idempotency_key=idempotency_key,
    )
    _dispatch(result)
    return result


@router.get(_RUN_PATH)
async def get_backtest_run(
    run_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await backtest_query.get_backtest_run(ctx.session, ctx.actor, run_id=run_id)


@router.post(_RETRY_PATH, status_code=202)
async def retry_backtest_run(
    run_id: str,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    result = await backtest_cmd.retry_backtest_run(
        ctx.session, ctx.actor, run_id=run_id, idempotency_key=idempotency_key
    )
    _dispatch(result)
    return result


@router.get(_RESULT_PATH)
async def get_backtest_result(
    result_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await backtest_query.get_backtest_result(ctx.session, ctx.actor, result_id=result_id)


@router.delete(_RESULT_PATH)
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


def _dispatch(result: dict[str, Any]) -> None:
    """Dispatch the durable backtest actor after the admission tx commits (the
    ``jobs`` row is already durable; mirrors the other worker routes)."""
    from entropia.apps.worker.actors import run_backtest_engine

    job_id = result.get("job_id")
    if job_id:
        job_enqueue.send_job(run_backtest_engine, job_id)


__all__ = ["router"]
