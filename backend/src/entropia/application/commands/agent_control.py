"""Analysis Lab control commands (Stage 6a, doc 18 §7, §8.3, §8.4, §11).

Directive queue + Admin lifecycle (pause / resume / stop). One transaction
(owned by the request dependency, never committed here). Lifecycle commands are
*requests*: they never kill a worker — pause/stop set a pending control that the
Coordinator applies at the next safe checkpoint (``application/commands/
agent_coordinator``). All mutations are audited + outboxed.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.domain.agent_lab.enums import (
    TASK_STOPPABLE_STATES,
    RuntimeControl,
    RuntimeStatus,
)
from entropia.domain.agent_lab.state_machine import (
    parse_human_directive_priority,
    runtime_can_pause,
    runtime_can_request_stop,
    runtime_can_resume,
)
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_admin, require_role
from entropia.domain.lifecycle.enums import Role
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.shared.errors import (
    AgentRunNotStoppableError,
    AgentRuntimeNotFoundError,
    AgentRuntimeStateConflictError,
    DirectiveTargetInvalidError,
    MessageTextRequiredError,
)

_LAB_ROLES = (Role.ADMIN, Role.SUPERVISOR)
_RUNTIME_TARGET = "agent_runtime"
_DIRECTIVE_TARGET = "task_directive"


async def create_directive(
    session: AsyncSession,
    actor: Actor,
    *,
    text: str,
    priority: str = "normal",
    target_agent_id: str,
    related_task_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Queue a durable research directive (doc 18 §8.3). 202-shaped result; the
    active task is never interrupted."""
    require_role(actor, _LAB_ROLES)
    clean_text = text.strip()
    if not clean_text:
        raise MessageTextRequiredError()
    canonical_priority = parse_human_directive_priority(priority)

    runtime = await al_repo.get_runtime(session, target_agent_id)
    if runtime is None:
        raise DirectiveTargetInvalidError()

    async def _op() -> dict[str, Any]:
        directive = await al_repo.create_directive(
            session,
            author_principal_id=actor.principal_id or "",
            target_agent_id=target_agent_id,
            related_task_id=related_task_id,
            text=clean_text,
            priority=canonical_priority,
            correlation_id=actor.correlation_id,
        )
        await al_repo.append_event(
            session,
            event_type="directive_queued",
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            task_id=related_task_id,
            directive_id=directive.directive_id,
            payload={"priority": str(canonical_priority)},
            correlation_id=actor.correlation_id,
        )
        audit_repo.add_audit_event(
            session,
            event_kind="agent.directive.queued",
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            target_entity_id=directive.directive_id,
            target_entity_type=_DIRECTIVE_TARGET,
            new_state="queued",
            correlation_id=actor.correlation_id,
            metadata={"priority": str(canonical_priority), "target_agent_id": target_agent_id},
        )
        audit_repo.add_outbox_event(
            session,
            event_type="agent.directive.queued",
            resource_type=_DIRECTIVE_TARGET,
            resource_id=directive.directive_id,
            payload={
                "directive_id": directive.directive_id,
                "priority": str(canonical_priority),
                "target_agent_id": target_agent_id,
            },
            correlation_id=actor.correlation_id,
        )
        return {
            "directive_id": directive.directive_id,
            "status": str(directive.status),
            "priority": str(canonical_priority),
            "target_agent_id": target_agent_id,
            "related_task_id": related_task_id,
            "delivery_policy": "next_safe_checkpoint",
            "active_task_interrupted": False,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "create_directive",
            "text": clean_text,
            "priority": str(canonical_priority),
            "target_agent_id": target_agent_id,
            "related_task_id": related_task_id,
        },
        operation=_op,
    )


async def _load_runtime_for_control(
    session: AsyncSession, agent_id: str, expected_row_version: int | None
) -> Any:
    """Resolve + row-lock the runtime, enforcing optimistic concurrency."""
    runtime = await al_repo.get_runtime(session, agent_id)
    if runtime is None:
        raise AgentRuntimeNotFoundError()
    await session.refresh(runtime, with_for_update=True)
    if expected_row_version is not None and expected_row_version != runtime.row_version:
        raise AgentRuntimeStateConflictError()
    return runtime


def _emit_control(
    session: AsyncSession,
    actor: Actor,
    *,
    runtime: Any,
    control: str,
    new_status: str,
    task_id: str | None = None,
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=f"agent.runtime.{control}",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=runtime.agent_id,
        target_entity_type=_RUNTIME_TARGET,
        new_state=new_status,
        correlation_id=actor.correlation_id,
        metadata={"control": control},
    )
    audit_repo.add_outbox_event(
        session,
        event_type=f"agent.runtime.{control}",
        resource_type=_RUNTIME_TARGET,
        resource_id=runtime.agent_id,
        payload={"agent_id": runtime.agent_id, "control": control, "status": new_status},
        correlation_id=actor.correlation_id,
    )


async def pause_runtime(
    session: AsyncSession,
    actor: Actor,
    *,
    agent_id: str,
    expected_row_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Request a controlled pause at the next safe checkpoint (Admin only)."""
    require_admin(actor)

    async def _op() -> dict[str, Any]:
        runtime = await _load_runtime_for_control(session, agent_id, expected_row_version)
        if not runtime_can_pause(runtime.status, runtime.pending_control):
            raise AgentRuntimeStateConflictError()
        runtime.pending_control = RuntimeControl.PAUSE
        runtime.control_correlation_id = actor.correlation_id
        runtime.row_version += 1
        await al_repo.append_event(
            session,
            event_type="agent_run_control_requested",
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            task_id=runtime.active_task_id,
            payload={"control": "pause"},
            correlation_id=actor.correlation_id,
        )
        _emit_control(
            session,
            actor,
            runtime=runtime,
            control="pause_requested",
            new_status=str(runtime.status),
        )
        return {
            "agent_id": runtime.agent_id,
            "control": "pause",
            "status": "accepted",
            "runtime_status": str(runtime.status),
            "delivery_policy": "next_safe_checkpoint",
            "row_version": runtime.row_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "pause_runtime", "agent_id": agent_id},
        operation=_op,
    )


async def resume_runtime(
    session: AsyncSession,
    actor: Actor,
    *,
    agent_id: str,
    expected_row_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Resume a paused runtime from its saved checkpoint (Admin only)."""
    require_admin(actor)

    async def _op() -> dict[str, Any]:
        runtime = await _load_runtime_for_control(session, agent_id, expected_row_version)
        if not runtime_can_resume(runtime.status):
            raise AgentRuntimeStateConflictError()
        runtime.status = RuntimeStatus.ACTIVE
        runtime.pending_control = None
        runtime.control_correlation_id = None
        runtime.row_version += 1
        await al_repo.append_event(
            session,
            event_type="task_resumed",
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            task_id=runtime.active_task_id,
            payload={"from": "paused"},
            correlation_id=actor.correlation_id,
        )
        _emit_control(
            session, actor, runtime=runtime, control="resumed", new_status=str(runtime.status)
        )
        return {
            "agent_id": runtime.agent_id,
            "control": "resume",
            "status": "accepted",
            "runtime_status": str(runtime.status),
            "row_version": runtime.row_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "resume_runtime", "agent_id": agent_id},
        operation=_op,
    )


async def stop_run(
    session: AsyncSession,
    actor: Actor,
    *,
    run_id: str,
    expected_row_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Request a controlled cancellation of the active Agent sub-run (Admin only).
    A cancelled run never publishes a normal Backtest Result (doc 18 §8.4)."""
    require_admin(actor)

    async def _op() -> dict[str, Any]:
        task = await al_repo.get_task(session, run_id)
        if task is None:
            raise AgentRunNotStoppableError()
        # Lock the runtime BEFORE validating the task's stoppable state, then
        # re-read the task under that lock — this closes the TOCTOU where a
        # concurrent Coordinator control moves the task out of a stoppable state
        # between the unlocked read and the runtime lock.
        runtime = await _load_runtime_for_control(session, task.agent_id, expected_row_version)
        await session.refresh(task)
        if task.status not in TASK_STOPPABLE_STATES:
            raise AgentRunNotStoppableError()
        if not runtime_can_request_stop(runtime.status, runtime.pending_control):
            raise AgentRuntimeStateConflictError()
        runtime.pending_control = RuntimeControl.STOP
        runtime.control_correlation_id = actor.correlation_id
        runtime.row_version += 1
        await al_repo.append_event(
            session,
            event_type="agent_run_control_requested",
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            task_id=task.task_id,
            payload={"control": "stop"},
            correlation_id=actor.correlation_id,
        )
        _emit_control(
            session,
            actor,
            runtime=runtime,
            control="stop_requested",
            new_status=str(runtime.status),
            task_id=task.task_id,
        )
        return {
            "agent_id": runtime.agent_id,
            "run_id": task.task_id,
            "control": "stop",
            "status": "accepted",
            "delivery_policy": "cancellation_safe_boundary",
            "row_version": runtime.row_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "stop_run", "run_id": run_id},
        operation=_op,
    )


__all__ = ["create_directive", "pause_runtime", "resume_runtime", "stop_run"]
