"""Deterministic Coordinator scaffold (Stage 6a, doc 18 §8.3, §8.4, §8.5).

Stage 6a ships the *safe-checkpoint* machinery the observation/control plane
needs, callable and testable, without the continuous ``apps/agent_coordinator``
runtime loop or the Tool Gateway (deferred to Stage 6a-2). These functions run
under the system service identity, take one transaction, and never commit.

Guarantees enforced here:
  - Pause/Stop are applied ONLY at a safe checkpoint (never a worker kill).
  - A queued directive is consumed ONLY after a safe checkpoint; HIGH ordering
    influences selection but never preempts a running task.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.agent_lab.enums import (
    AgentTaskStatus,
    DirectiveStatus,
    RuntimeControl,
    RuntimeStatus,
)
from entropia.domain.lifecycle.enums import ActorKind
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.shared.errors import AgentRuntimeNotFoundError

_SYSTEM_KIND = ActorKind.SYSTEM_SERVICE


async def advance_to_safe_checkpoint(
    session: AsyncSession,
    *,
    agent_id: str,
    stage: str = "safe_checkpoint",
    directive_cursor: str | None = None,
    correlation_id: str | None = None,
) -> Any:
    """Write a durable checkpoint for the runtime's active task, if any.

    Returns the new checkpoint, or ``None`` when there is no active task to
    checkpoint. Updates ``runtime.last_checkpoint_id``.
    """
    runtime = await al_repo.get_runtime(session, agent_id)
    if runtime is None:
        raise AgentRuntimeNotFoundError()
    if runtime.active_task_id is None:
        return None
    task = await al_repo.get_task(session, runtime.active_task_id)
    if task is None:
        return None
    checkpoint_no = await al_repo.max_checkpoint_no(session, task.task_id) + 1
    checkpoint = await al_repo.create_checkpoint(
        session,
        task_id=task.task_id,
        checkpoint_no=checkpoint_no,
        stage=stage,
        state_ref=f"state::{task.task_id}::{checkpoint_no}",
        context_manifest_id=task.context_manifest_id,
        plan_revision=checkpoint_no,
        directive_cursor=directive_cursor,
    )
    runtime.last_checkpoint_id = checkpoint.checkpoint_id
    await al_repo.append_event(
        session,
        event_type="checkpoint_saved",
        actor_principal_id=None,
        actor_kind=_SYSTEM_KIND,
        task_id=task.task_id,
        payload={"checkpoint_id": checkpoint.checkpoint_id, "stage": stage},
        correlation_id=correlation_id,
    )
    return checkpoint


async def apply_pending_control(
    session: AsyncSession, *, agent_id: str, correlation_id: str | None = None
) -> dict[str, Any]:
    """Apply a pending pause/stop at a safe checkpoint (doc 18 §8.4)."""
    runtime = await al_repo.get_runtime(session, agent_id)
    if runtime is None:
        raise AgentRuntimeNotFoundError()
    control = runtime.pending_control
    if control is None:
        return {"applied": None, "runtime_status": str(runtime.status)}

    checkpoint = await advance_to_safe_checkpoint(
        session, agent_id=agent_id, correlation_id=correlation_id
    )
    active_task = (
        await al_repo.get_task(session, runtime.active_task_id)
        if runtime.active_task_id is not None
        else None
    )

    if control is RuntimeControl.PAUSE:
        runtime.status = RuntimeStatus.PAUSED
        if active_task is not None:
            active_task.status = AgentTaskStatus.PAUSED
        event_type = "task_paused"
    else:  # RuntimeControl.STOP — controlled cancellation of the current sub-run
        if active_task is not None:
            active_task.status = AgentTaskStatus.CANCELLED
        runtime.status = RuntimeStatus.ACTIVE
        runtime.active_task_id = None
        event_type = "task_cancelled"

    runtime.pending_control = None
    runtime.control_correlation_id = None
    runtime.row_version += 1
    await al_repo.append_event(
        session,
        event_type=event_type,
        actor_principal_id=None,
        actor_kind=_SYSTEM_KIND,
        task_id=active_task.task_id if active_task is not None else None,
        payload={
            "control": str(control),
            "checkpoint_id": checkpoint.checkpoint_id if checkpoint is not None else None,
        },
        correlation_id=correlation_id,
    )
    return {
        "applied": str(control),
        "runtime_status": str(runtime.status),
        "checkpoint_id": checkpoint.checkpoint_id if checkpoint is not None else None,
        "cancelled_task_id": active_task.task_id
        if (control is RuntimeControl.STOP and active_task is not None)
        else None,
    }


async def consume_next_directive(
    session: AsyncSession, *, agent_id: str, correlation_id: str | None = None
) -> dict[str, Any]:
    """Consume the next eligible directive at a safe checkpoint (doc 18 §8.3)."""
    runtime = await al_repo.get_runtime(session, agent_id)
    if runtime is None:
        raise AgentRuntimeNotFoundError()

    # A pending pause/stop takes precedence: never consume (and thereby burn) a
    # directive at a boundary where the sub-run is about to pause or cancel — the
    # directive would become CONSUMED for a cancelled task with no way back to
    # QUEUED. Defer until the control has been applied (doc 18 §8.3, §8.4).
    if runtime.pending_control is not None:
        return {"consumed": None, "deferred_reason": str(runtime.pending_control)}

    directive = await al_repo.next_queued_directive(session, agent_id)
    if directive is None:
        return {"consumed": None}

    checkpoint = await advance_to_safe_checkpoint(
        session,
        agent_id=agent_id,
        directive_cursor=directive.directive_id,
        correlation_id=correlation_id,
    )
    checkpoint_id = checkpoint.checkpoint_id if checkpoint is not None else None
    directive.status = DirectiveStatus.CONSUMED
    directive.consumed_checkpoint_id = checkpoint_id
    await al_repo.append_event(
        session,
        event_type="directive_consumed",
        actor_principal_id=None,
        actor_kind=_SYSTEM_KIND,
        task_id=runtime.active_task_id,
        directive_id=directive.directive_id,
        payload={"checkpoint_id": checkpoint_id, "priority": str(directive.priority)},
        correlation_id=correlation_id,
    )
    return {
        "consumed": directive.directive_id,
        "checkpoint_id": checkpoint_id,
        "priority": str(directive.priority),
    }


__all__ = ["advance_to_safe_checkpoint", "apply_pending_control", "consume_next_directive"]
