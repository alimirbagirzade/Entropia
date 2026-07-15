"""Continuous Coordinator cycle (Stage 6a-2, doc 18 §8.3, §8.4, §8.5, §14, AL-01).

Promotes the Stage-6a deterministic scaffold (``agent_coordinator``) into the real
loop body ``apps/agent_coordinator`` drives every tick, independent of the UI /
browser / Lab Assistant chat (doc 18 §14, AL-01). One cycle, one transaction (the
process commits per tick):

    apply any pending pause/stop at a safe checkpoint (never a worker kill) ->
    if paused, stop here (a paused runtime consumes nothing) ->
    consume the next eligible directive at a safe checkpoint (HIGH orders, never
        preempts) -> materialize an AUTONOMOUS follow-up task (doc 18 §8.3, §10).

Re-entrancy / crash recovery (AL-14): a directive already CONSUMED is never
re-selected, so a redelivered/retried cycle produces no duplicate follow-up; a
cycle that fails mid-way rolls back whole and the next tick re-reads canonical
state.

Stage 6b (spec F-20): materializing a follow-up task also enqueues a durable
``agent-executor`` Job in the SAME transaction (no commit here either) — the
Coordinator process (``apps/agent_coordinator/__main__.py``) dispatches the
matching actor after it commits, exactly like an API route dispatches
``send_job`` after its own commit. A crash between commit and dispatch is not a
lost task: the job row stays QUEUED and the scheduler's redelivery sweep
(INF-03) re-sends it on the next tick.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import agent_coordinator as coordinator
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    RuntimeStatus,
)
from entropia.domain.agent_lab.tool_gateway import exposed_tool_names
from entropia.domain.lifecycle.enums import ActorKind
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import capability as capability_repo
from entropia.infrastructure.queues.enqueue import enqueue_job
from entropia.shared.errors import AgentRuntimeNotFoundError

_EXECUTOR_QUEUE = "agent-executor"

_SYSTEM_KIND = ActorKind.SYSTEM_SERVICE
_FOLLOWUP_TITLE_LIMIT = 120


async def run_coordinator_cycle(
    session: AsyncSession, *, agent_id: str = ALPHA_AGENT_ID, correlation_id: str | None = None
) -> dict[str, Any]:
    """Run one Coordinator cycle for the agent runtime (doc 18 §8.3-§8.5)."""
    runtime = await al_repo.get_runtime(session, agent_id)
    if runtime is None:
        raise AgentRuntimeNotFoundError()
    # Lock the runtime row for the whole cycle. The loop is now concurrent with the
    # Admin control commands (pause/resume/stop), which also lock the row; serializing
    # here prevents any lost update on the runtime's operational pointers.
    await session.refresh(runtime, with_for_update=True)

    control = await coordinator.apply_pending_control(
        session, agent_id=agent_id, correlation_id=correlation_id
    )

    # A paused runtime does no work and consumes no directive this cycle
    # (queue/directives/artifacts are preserved, doc 18 §8.4) — and plans nothing,
    # so no tool registry is resolved either.
    await session.refresh(runtime)
    if runtime.status is RuntimeStatus.PAUSED:
        return {
            "runtime_status": str(runtime.status),
            "control": control,
            "consumed": None,
            "followup_task_id": None,
            "exposed_tools": None,
        }

    # Plan step (doc 22 §11, CR-08/FD-10): the tool menu the Agent may plan around
    # this cycle is the CR-08 exposure — ungated tools plus capability tools whose
    # gating capability is currently Limited/Active. Placeholder capabilities never
    # enter the plan.
    operational_keys = await capability_repo.operational_capability_keys(session)
    plan_tools = exposed_tool_names(operational_keys)

    consumed = await coordinator.consume_next_directive(
        session, agent_id=agent_id, correlation_id=correlation_id
    )
    followup_task_id: str | None = None
    executor_job_id: str | None = None
    if consumed.get("consumed"):
        spawned = await _spawn_followup_task(
            session,
            agent_id=agent_id,
            directive_id=str(consumed["consumed"]),
            correlation_id=correlation_id,
            exposed_tools=plan_tools,
        )
        if spawned is not None:
            followup_task_id, executor_job_id = spawned

    return {
        "runtime_status": str(runtime.status),
        "control": control,
        "consumed": consumed,
        "followup_task_id": followup_task_id,
        "executor_job_id": executor_job_id,
        "exposed_tools": list(plan_tools),
    }


async def _spawn_followup_task(
    session: AsyncSession,
    *,
    agent_id: str,
    directive_id: str,
    correlation_id: str | None,
    exposed_tools: tuple[str, ...] = (),
) -> tuple[str, str] | None:
    """Materialize an AUTONOMOUS follow-up task from a consumed directive.

    The task is QUEUED — real execution is the durable executor's job (spec
    F-20, ``application/jobs/agent_executor.py``); the Coordinator never
    fabricates progress itself (CR-09, doc 18 §14). The plan-time CR-08 tool
    exposure is recorded on the creation event so the task's plan provenance
    shows exactly which tools were offerable at materialization, and the
    executor re-reads it before dispatching any governed tool call (safe tool
    selection). Returns ``(task_id, executor_job_id)``."""
    directive = await al_repo.get_directive(session, directive_id)
    if directive is None:
        return None
    title = f"Directive follow-up: {directive.text[:_FOLLOWUP_TITLE_LIMIT]}"
    task = await al_repo.create_task(
        session,
        agent_id=agent_id,
        task_type="research",
        title=title,
        source="directive",
        priority=AgentTaskPriority.AUTONOMOUS,
        status=AgentTaskStatus.QUEUED,
        parent_task_id=directive.related_task_id,
    )
    await al_repo.append_event(
        session,
        event_type="agent_task_created",
        actor_principal_id=None,
        actor_kind=_SYSTEM_KIND,
        task_id=task.task_id,
        directive_id=directive_id,
        payload={
            "source": "directive",
            "priority": str(AgentTaskPriority.AUTONOMOUS),
            "exposed_tools": list(exposed_tools),
        },
        correlation_id=correlation_id,
    )
    job = enqueue_job(
        session,
        queue=_EXECUTOR_QUEUE,
        payload={"task_id": task.task_id},
        idempotency_key=f"agent-task-exec:{task.task_id}",
        correlation_id=correlation_id,
    )
    return task.task_id, job.job_id


__all__ = ["run_coordinator_cycle"]
