"""Analysis Lab API (doc 18 §7, §9.2). Thin handlers: parse body/query/headers ->
resolve actor context -> call one command/query. Server policy is enforced inside
the command/query; the SSE stream re-checks role before streaming (never a UI hint).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from entropia.application.commands import agent_control as agent_control_cmd
from entropia.application.commands import lab_message as lab_message_cmd
from entropia.application.queries import agent_tool_gateway as tool_gateway_query
from entropia.application.queries import agent_workspace as agent_workspace_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.agent_lab.enums import ALPHA_AGENT_ID
from entropia.domain.identity.policy import require_role
from entropia.domain.lifecycle.enums import Role
from entropia.shared.errors import ValidationError

router = APIRouter(tags=["analysis-lab"])

_LAB_ROLES = (Role.ADMIN, Role.SUPERVISOR)
_SSE_HEARTBEAT_SECONDS = 15

_OVERVIEW_PATH = "/agent-workspace/overview"
_TASKS_PATH = "/agent-tasks"
_TASK_DETAIL_PATH = "/agent-tasks/{task_id}"
_MESSAGES_PATH = "/lab/messages"
_DIRECTIVES_PATH = "/agent-directives"
_PAUSE_PATH = "/agent-runtime/pause"
_RESUME_PATH = "/agent-runtime/resume"
_STOP_PATH = "/agent-runs/{run_id}/stop"
_HYPOTHESES_PATH = "/hypotheses"
_STREAM_PATH = "/agent-events/stream"
_TASK_TOOL_CALLS_PATH = "/agent-tasks/{task_id}/tool-calls"
_TOOL_CALL_DETAIL_PATH = "/agent-tool-calls/{tool_call_id}"


class LabMessageBody(BaseModel):
    text: str = Field(min_length=1)
    related_task_id: str | None = None


class DirectiveBody(BaseModel):
    text: str = Field(min_length=1)
    priority: str = "normal"
    target_agent_id: str = ALPHA_AGENT_ID
    related_task_id: str | None = None


def _parse_if_match(if_match: str | None) -> int | None:
    """Parse an ``If-Match`` ETag into an expected ``row_version``.

    A missing/empty header means "no OCC token supplied" (``None``). A present
    but non-integer header is a client error: reject it (422) rather than
    silently dropping the concurrency guard.
    """
    if if_match is None:
        return None
    token = if_match.strip().strip('"')
    if not token:
        return None
    try:
        return int(token)
    except ValueError as exc:
        raise ValidationError("If-Match must be an integer row version.") from exc


# ---------- Read models ----------


@router.get(_OVERVIEW_PATH)
async def get_overview(ctx: RequestContext = Depends(request_context)) -> dict[str, Any]:
    return await agent_workspace_query.get_overview(ctx.session, ctx.actor)


@router.get(_TASKS_PATH)
async def list_tasks(
    ctx: RequestContext = Depends(request_context),
    status: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None),
) -> dict[str, Any]:
    return await agent_workspace_query.list_tasks(
        ctx.session, ctx.actor, status=status, cursor=cursor, limit=limit
    )


@router.get(_TASK_DETAIL_PATH)
async def get_task(task_id: str, ctx: RequestContext = Depends(request_context)) -> dict[str, Any]:
    return await agent_workspace_query.get_task(ctx.session, ctx.actor, task_id=task_id)


@router.get(_TASK_TOOL_CALLS_PATH)
async def list_task_tool_calls(
    task_id: str,
    ctx: RequestContext = Depends(request_context),
    limit: int | None = Query(default=None),
) -> dict[str, Any]:
    return await tool_gateway_query.list_task_tool_calls(
        ctx.session, ctx.actor, task_id=task_id, limit=limit
    )


@router.get(_TOOL_CALL_DETAIL_PATH)
async def get_tool_call(
    tool_call_id: str, ctx: RequestContext = Depends(request_context)
) -> dict[str, Any]:
    return await tool_gateway_query.get_tool_call(ctx.session, ctx.actor, tool_call_id=tool_call_id)


@router.get(_HYPOTHESES_PATH)
async def list_hypotheses(
    ctx: RequestContext = Depends(request_context),
    status: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None),
) -> dict[str, Any]:
    return await agent_workspace_query.list_hypotheses(
        ctx.session, ctx.actor, status=status, cursor=cursor, limit=limit
    )


# ---------- Commands ----------


@router.post(_MESSAGES_PATH)
async def send_lab_message(
    body: LabMessageBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await lab_message_cmd.record_discussion_message(
        ctx.session,
        ctx.actor,
        text=body.text,
        related_task_id=body.related_task_id,
        idempotency_key=idempotency_key,
    )


@router.post(_DIRECTIVES_PATH, status_code=202)
async def queue_directive(
    body: DirectiveBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await agent_control_cmd.create_directive(
        ctx.session,
        ctx.actor,
        text=body.text,
        priority=body.priority,
        target_agent_id=body.target_agent_id,
        related_task_id=body.related_task_id,
        idempotency_key=idempotency_key,
    )


@router.post(_PAUSE_PATH, status_code=202)
async def pause_runtime(
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await agent_control_cmd.pause_runtime(
        ctx.session,
        ctx.actor,
        agent_id=ALPHA_AGENT_ID,
        expected_row_version=_parse_if_match(if_match),
        idempotency_key=idempotency_key,
    )


@router.post(_RESUME_PATH, status_code=202)
async def resume_runtime(
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await agent_control_cmd.resume_runtime(
        ctx.session,
        ctx.actor,
        agent_id=ALPHA_AGENT_ID,
        expected_row_version=_parse_if_match(if_match),
        idempotency_key=idempotency_key,
    )


@router.post(_STOP_PATH, status_code=202)
async def stop_run(
    run_id: str,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await agent_control_cmd.stop_run(
        ctx.session,
        ctx.actor,
        run_id=run_id,
        expected_row_version=_parse_if_match(if_match),
        idempotency_key=idempotency_key,
    )


# ---------- SSE (refresh signal only, doc 18 §7, §14) ----------


async def _event_stream(request: Request) -> AsyncIterator[dict[str, str]]:
    yield {"event": "ready", "data": json.dumps({"agent_id": ALPHA_AGENT_ID})}
    while True:
        if await request.is_disconnected():
            break
        yield {"event": "heartbeat", "data": "{}"}
        await asyncio.sleep(_SSE_HEARTBEAT_SECONDS)


@router.get(_STREAM_PATH)
async def agent_events_stream(
    request: Request, ctx: RequestContext = Depends(request_context)
) -> EventSourceResponse:
    # Authorize BEFORE streaming — a denied caller gets 403, never a stream.
    require_role(ctx.actor, _LAB_ROLES)
    return EventSourceResponse(_event_stream(request))


__all__ = ["router"]
