"""Analysis Lab read models (Stage 6a, doc 18 §3, §7, §9, §9.2).

Read-only projections for the Agent Workspace. Admin/Supervisor server policy is
re-checked on every call; UI hide/disable is never authority (doc 18 §2, §14).
Runtime status/queue/output are the Coordinator's durable truth, never a browser
array; SSE is only a refresh signal.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.agent_lab.cursor import clamp_limit, decode_cursor, encode_cursor
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskStatus,
    HypothesisStatus,
)
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_role
from entropia.domain.lifecycle.enums import Role
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.shared.errors import (
    AgentRuntimeNotFoundError,
    AgentTaskNotFoundError,
    ValidationError,
)

_LAB_ROLES = (Role.ADMIN, Role.SUPERVISOR)
_TASK_NAMESPACE = "agent_task"
_HYPOTHESIS_NAMESPACE = "hypothesis"
_QUEUE_CARD_LIMIT = 20


def _parse_task_status(raw: str | None) -> AgentTaskStatus | None:
    if raw is None:
        return None
    try:
        return AgentTaskStatus(raw)
    except ValueError as exc:
        raise ValidationError("Unknown Agent task status filter.") from exc


def _parse_hypothesis_status(raw: str | None) -> HypothesisStatus | None:
    if raw is None:
        return None
    try:
        return HypothesisStatus(raw)
    except ValueError as exc:
        raise ValidationError("Unknown hypothesis status filter.") from exc


def _task_card(task: Any) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "task_type": task.task_type,
        "source": task.source,
        "priority": str(task.priority),
        "status": str(task.status),
        "stage": task.stage,
        "progress": task.progress,
    }


def _hypothesis_card(artifact: Any) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "status": str(artifact.status),
        "title": artifact.title,
        "mechanism": artifact.mechanism,
        "data_context": artifact.data_context,
        "next_action": artifact.next_action,
        "evidence_refs": list(artifact.evidence_refs),
        "source_task_id": artifact.source_task_id,
    }


async def get_overview(
    session: AsyncSession, actor: Actor, *, agent_id: str = ALPHA_AGENT_ID
) -> dict[str, Any]:
    """Runtime + active task + context bundle + queue + output summary (doc 18 §7)."""
    require_role(actor, _LAB_ROLES)
    runtime = await al_repo.get_runtime(session, agent_id)
    if runtime is None:
        raise AgentRuntimeNotFoundError()

    active_task = (
        await al_repo.get_task(session, runtime.active_task_id)
        if runtime.active_task_id is not None
        else None
    )
    context_bundle: dict[str, Any] | None = None
    if active_task is not None and active_task.context_manifest_id is not None:
        context_bundle = {
            "context_manifest_id": active_task.context_manifest_id,
            "note": "Derived read-only from the active task's pinned context manifest.",
        }

    counts = await al_repo.queue_counts(session, agent_id)
    cards = await al_repo.recent_tasks(session, agent_id, _QUEUE_CARD_LIMIT)
    hypotheses = await al_repo.page_hypotheses(session, limit=_QUEUE_CARD_LIMIT)

    return {
        "runtime": {
            "agent_id": runtime.agent_id,
            "mode": str(runtime.mode),
            "status": str(runtime.status),
            "pending_control": str(runtime.pending_control)
            if runtime.pending_control is not None
            else None,
            "active_task_id": runtime.active_task_id,
            "last_checkpoint_id": runtime.last_checkpoint_id,
            "row_version": runtime.row_version,
        },
        "active_task": _task_card(active_task) if active_task is not None else None,
        "context_bundle": context_bundle,
        "queue": {"counts": counts, "cards": [_task_card(t) for t in cards]},
        "output_board": {
            "hypotheses": [_hypothesis_card(h) for h in hypotheses[:_QUEUE_CARD_LIMIT]]
        },
    }


async def list_tasks(
    session: AsyncSession,
    actor: Actor,
    *,
    status: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
    agent_id: str = ALPHA_AGENT_ID,
) -> dict[str, Any]:
    """One keyset page of the task queue/history (doc 18 §7)."""
    require_role(actor, _LAB_ROLES)
    status_filter = _parse_task_status(status)
    page_size = clamp_limit(limit)
    last_key = (
        decode_cursor(cursor, namespace=_TASK_NAMESPACE).last_key if cursor is not None else None
    )
    rows = await al_repo.page_tasks(
        session, agent_id=agent_id, status=status_filter, last_key=last_key, limit=page_size
    )
    has_more = len(rows) > page_size
    page = rows[:page_size]
    next_cursor = (
        encode_cursor(_TASK_NAMESPACE, last_key=page[-1].task_id) if has_more and page else None
    )
    return {
        "tasks": [_task_card(t) for t in page],
        "next_cursor": next_cursor,
    }


async def get_task(session: AsyncSession, actor: Actor, *, task_id: str) -> dict[str, Any]:
    """Task detail with checkpoints + related directives (doc 18 §7, §9)."""
    require_role(actor, _LAB_ROLES)
    task = await al_repo.get_task(session, task_id)
    if task is None:
        raise AgentTaskNotFoundError()
    checkpoints = await al_repo.list_checkpoints(session, task_id)
    directives = await al_repo.list_directives_for_task(session, task_id)
    return {
        **_task_card(task),
        "context_manifest_id": task.context_manifest_id,
        "parent_task_id": task.parent_task_id,
        "waiting_reason": task.waiting_reason,
        "failure_reason": task.failure_reason,
        "checkpoints": [
            {
                "checkpoint_id": c.checkpoint_id,
                "checkpoint_no": c.checkpoint_no,
                "stage": c.stage,
                "directive_cursor": c.directive_cursor,
            }
            for c in checkpoints
        ],
        "directives": [
            {
                "directive_id": d.directive_id,
                "priority": str(d.priority),
                "status": str(d.status),
                "text": d.text,
                "consumed_checkpoint_id": d.consumed_checkpoint_id,
            }
            for d in directives
        ],
    }


async def list_hypotheses(
    session: AsyncSession,
    actor: Actor,
    *,
    status: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """One keyset page of the Hypothesis & Output Board (active artifacts, doc 18 §7)."""
    require_role(actor, _LAB_ROLES)
    status_filter = _parse_hypothesis_status(status)
    page_size = clamp_limit(limit)
    last_key = (
        decode_cursor(cursor, namespace=_HYPOTHESIS_NAMESPACE).last_key
        if cursor is not None
        else None
    )
    rows = await al_repo.page_hypotheses(
        session, status=status_filter, last_key=last_key, limit=page_size
    )
    has_more = len(rows) > page_size
    page = rows[:page_size]
    next_cursor = (
        encode_cursor(_HYPOTHESIS_NAMESPACE, last_key=page[-1].artifact_id)
        if has_more and page
        else None
    )
    return {
        "hypotheses": [_hypothesis_card(h) for h in page],
        "next_cursor": next_cursor,
    }


__all__ = ["get_overview", "get_task", "list_hypotheses", "list_tasks"]
