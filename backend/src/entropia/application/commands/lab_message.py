"""Lab Assistant discussion command (Stage 6a, doc 18 §8.2, §7, §11).

A normal discussion message is persisted and answered by the Lab Assistant from
SAVED context (runtime + active task + latest checkpoint). It NEVER interrupts,
re-prioritizes or mutates the active research task (doc 18 §14). The V1 assistant
response is a deterministic, honest summary of saved state — not fabricated
progress and not a hidden reasoning trace (CR-09).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.domain.agent_lab.enums import ALPHA_AGENT_ID, LabMessageType
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_role
from entropia.domain.lifecycle.enums import ActorKind, Role
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.shared.errors import AgentTaskNotFoundError, MessageTextRequiredError

_LAB_ROLES = (Role.ADMIN, Role.SUPERVISOR)
_MESSAGE_TARGET = "lab_message"


async def _compose_assistant_response(session: AsyncSession, agent_id: str) -> str:
    """A human-readable summary derived only from saved Agent state."""
    runtime = await al_repo.get_runtime(session, agent_id)
    if runtime is None:
        return (
            "Alpha Agent runtime state is unavailable. Reload the latest Agent "
            "state before relying on this answer."
        )
    if runtime.active_task_id is None:
        return (
            f"Alpha Agent is {runtime.status}. There is no active task right now; "
            "the Coordinator will schedule an eligible task. This message was "
            "recorded and did not change the active work."
        )
    task = await al_repo.get_task(session, runtime.active_task_id)
    if task is None:
        return (
            f"Alpha Agent is {runtime.status}. This message was recorded from the "
            "latest saved Agent state and did not change the active work."
        )
    checkpoint = await al_repo.get_latest_checkpoint(session, task.task_id)
    stage = checkpoint.stage if checkpoint is not None else (task.stage or "n/a")
    return (
        f"Alpha Agent is {runtime.status}. Active task '{task.title}' is "
        f"{task.status} at stage '{stage}' ({task.progress}% saved). This message "
        "was recorded and did not interrupt or re-prioritize the active task."
    )


async def record_discussion_message(
    session: AsyncSession,
    actor: Actor,
    *,
    text: str,
    related_task_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Persist a discussion message + a saved-context Lab Assistant response."""
    require_role(actor, _LAB_ROLES)
    clean_text = text.strip()
    if not clean_text:
        raise MessageTextRequiredError()
    if related_task_id is not None:
        task = await al_repo.get_task(session, related_task_id)
        if task is None:
            raise AgentTaskNotFoundError()

    async def _op() -> dict[str, Any]:
        message = await al_repo.create_message(
            session,
            message_type=LabMessageType.MESSAGE,
            author_principal_id=actor.principal_id,
            text=clean_text,
            task_id=related_task_id,
            correlation_id=actor.correlation_id,
        )
        response_text = await _compose_assistant_response(session, ALPHA_AGENT_ID)
        response = await al_repo.create_message(
            session,
            message_type=LabMessageType.ASSISTANT,
            author_principal_id=None,
            text=response_text,
            task_id=related_task_id,
            correlation_id=actor.correlation_id,
        )
        await al_repo.append_event(
            session,
            event_type="discussion_recorded",
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            task_id=related_task_id,
            payload={"message_id": message.message_id},
            correlation_id=actor.correlation_id,
        )
        await al_repo.append_event(
            session,
            event_type="lab_assistant_response_created",
            actor_principal_id=None,
            actor_kind=ActorKind.SYSTEM_SERVICE,
            task_id=related_task_id,
            payload={"message_id": response.message_id},
            correlation_id=actor.correlation_id,
        )
        audit_repo.add_audit_event(
            session,
            event_kind="agent.discussion.recorded",
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            target_entity_id=message.message_id,
            target_entity_type=_MESSAGE_TARGET,
            correlation_id=actor.correlation_id,
        )
        audit_repo.add_outbox_event(
            session,
            event_type="agent.discussion.recorded",
            resource_type=_MESSAGE_TARGET,
            resource_id=message.message_id,
            payload={"message_id": message.message_id, "response_id": response.message_id},
            correlation_id=actor.correlation_id,
        )
        return {
            "message": {
                "message_id": message.message_id,
                "type": str(message.type),
                "text": message.text,
                "task_id": message.task_id,
            },
            "assistant_response": {
                "message_id": response.message_id,
                "type": str(response.type),
                "text": response.text,
            },
            "active_task_interrupted": False,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "record_discussion_message",
            "text": clean_text,
            "related_task_id": related_task_id,
        },
        operation=_op,
    )


__all__ = ["record_discussion_message"]
