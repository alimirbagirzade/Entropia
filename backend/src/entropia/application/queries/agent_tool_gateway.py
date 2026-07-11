"""Agent Tool Gateway call-history read models (doc 18 §7, §9.2, §14).

Read-only projections over the durable, governed ``agent_tool_call`` records the
Coordinator writes on every gateway dispatch. Analysis Lab is the human "safe
observation and control surface" (doc 18 §1356/teslim): Admin/Supervisor policy
is re-checked on every call, UI hide/disable is never authority (doc 18 §2, §14).

The write path (``dispatch_tool_call``) stays fully gated; these queries only
surface the already-persisted record. Summary rows omit the ``request`` /
``response_ref`` payloads — the per-call detail carries them verbatim.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.agent_lab.cursor import clamp_limit
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_role
from entropia.domain.lifecycle.enums import Role
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import agent_tool_gateway as tg_repo
from entropia.shared.errors import AgentTaskNotFoundError, AgentToolCallNotFoundError

_LAB_ROLES = (Role.ADMIN, Role.SUPERVISOR)


def _tool_call_card(call: Any) -> dict[str, Any]:
    """Summary row: operational pointer + provenance, no payload bodies."""
    return {
        "tool_call_id": call.tool_call_id,
        "tool_name": call.tool_name,
        "task_id": call.task_id,
        "checkpoint_id": call.checkpoint_id,
        "actor_kind": str(call.actor_kind),
        "policy_scope": str(call.policy_scope),
        "status": str(call.status),
        "artifact_output_ref": call.artifact_output_ref,
        "failure_code": call.failure_code,
        "failure_message": call.failure_message,
        "correlation_id": call.correlation_id,
        "created_at": call.created_at.isoformat() if call.created_at else None,
        "updated_at": call.updated_at.isoformat() if call.updated_at else None,
    }


def _tool_call_detail(call: Any) -> dict[str, Any]:
    """Full record: the summary plus the verbatim request/terminal outcome."""
    return {
        **_tool_call_card(call),
        "agent_id": call.agent_id,
        "actor_principal_id": call.actor_principal_id,
        "input_manifest_id": call.input_manifest_id,
        "idempotency_key": call.idempotency_key,
        "request": call.request,
        "response_ref": call.response_ref,
    }


async def list_task_tool_calls(
    session: AsyncSession,
    actor: Actor,
    *,
    task_id: str,
    limit: int | None = None,
) -> dict[str, Any]:
    """Recent tool calls for one Agent task (doc 18 §9.2), newest-first and
    bounded — the same shape as the task's checkpoints/directives. A missing task
    is reported as not-found so the listing never silently returns an empty page
    for a bad id."""
    require_role(actor, _LAB_ROLES)
    task = await al_repo.get_task(session, task_id)
    if task is None:
        raise AgentTaskNotFoundError()
    page_limit = clamp_limit(limit)
    calls = await tg_repo.list_tool_calls(session, task_id=task_id, limit=page_limit)
    return {"tool_calls": [_tool_call_card(call) for call in calls]}


async def get_tool_call(
    session: AsyncSession, actor: Actor, *, tool_call_id: str
) -> dict[str, Any]:
    """One tool-call record in full (doc 18 §9.2). A missing id is not-found."""
    require_role(actor, _LAB_ROLES)
    call = await tg_repo.get_tool_call(session, tool_call_id)
    if call is None:
        raise AgentToolCallNotFoundError()
    return _tool_call_detail(call)


__all__ = ["get_tool_call", "list_task_tool_calls"]
