"""Alpha Agent task executor — durable worker body (spec F-20; doc 18 §8.3-§8.5,
§9, §9.2, §10, §14).

Runs on the ``agent-executor`` queue. The durable ``jobs`` row is transport plus
the retry/redelivery backstop (INF-03/INF-09) — because this queue hosts exactly
one actor (``run_agent_executor``), the SAME generic scheduler sweeps that already
recover a crashed ``backtest``/``agent`` job (``application/jobs/maintenance.py``,
``apps/scheduler/__main__.py::ACTOR_BY_QUEUE``) cover this queue for free: no new
maintenance code, no new columns, no bespoke claim/lease table. The ``agent_task``/
``agent_runtime`` rows stay the business source of truth (doc 18 §9).

One executor pass drives exactly the QUEUED task named in the job payload
(materialized by the Coordinator, ``agent_loop.py::_spawn_followup_task``) end to
end through the SAME governed Tool Gateway a human-equivalent flow would use
(doc 18 §10 parity):

    lock runtime + task -> apply any already-pending pause/stop (never overrun a
    control request with a false RUNNING start) -> RUNNING (this is the FIRST code
    path that ever sets ``runtime.active_task_id`` — Pause/Resume/Stop, already
    implemented in ``agent_control.py``/``agent_coordinator.py``, become live for
    the first time) -> at each step boundary, re-check pending control before
    proceeding (checkpoint-safe cancellation, doc 18 §8.4) -> resolve the Agent's
    own Mainboard composition -> Ready Check -> backtest admission -> run the REAL
    engine (``jobs/backtest_engine.py::run_backtest``, untouched) -> query the
    immutable result -> record a hypothesis artifact evidenced by it -> SUCCEEDED.

Safe tool selection: every governed step is only attempted when its tool name was
present in the task's plan-time CR-08 exposure (recorded on the ``agent_task_created``
event) — an unexposed tool fails the task closed rather than being silently skipped
or forced. A governed denial (REJECTED tool call, non-ready composition, engine
failure) is a normal recorded terminal outcome — the task goes FAILED with a
structured reason, never a raised job exception, mirroring ``run_backtest``'s own
philosophy that an expected business failure is not a retriable job error. Only a
genuinely unexpected exception propagates, so it gets the worker's own retry plus
the scheduler's stale-job recovery (timeout/retry, INF-09).

Idempotency: every Tool Gateway call carries a step-deterministic idempotency key
(``f"{task_id}:<step>"``); ``run_backtest`` is itself redelivery-idempotent
(terminal-state early return). A redelivered executor job for an already-terminal
task is a no-op (mirrors ``run_backtest``'s at-least-once guard). Every transition
is both an ``AgentEvent`` (doc 18 §9.2 observability) and an audit + outbox record
(doc 18 §12).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import agent_coordinator as coordinator
from entropia.application.jobs import agent_tools
from entropia.application.jobs.backtest_engine import BarBatchStreamer, run_backtest
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries.market_bars import iter_bar_batches
from entropia.domain.agent_lab.enums import TASK_TERMINAL_STATES, AgentTaskStatus
from entropia.domain.agent_lab.state_machine import task_transition_allowed
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import ActorKind, JobStatus, PrincipalType
from entropia.domain.readiness.enums import ReadinessState
from entropia.infrastructure.postgres.models import Job
from entropia.infrastructure.postgres.models.agent_lab import AgentEvent
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.shared.errors import AppError

_SYSTEM_KIND = ActorKind.SYSTEM_SERVICE
_TASK_TARGET = "agent_task"
_FAILURE_REASON_LIMIT = 256

# Mirrors ``apps/seed.py::DEFAULT_AGENT_ID`` — the Principal the Agent's own tool
# calls / Mainboard composition are attributed to (not the runtime's ``agent_id``,
# which is the ``agent_runtime`` singleton PK, e.g. "alpha-agent").
_AGENT_PRINCIPAL_ID = "agent_alpha"


def _agent_actor(*, correlation_id: str | None) -> Actor:
    return Actor(
        principal_id=_AGENT_PRINCIPAL_ID,
        principal_type=PrincipalType.AGENT,
        role=None,
        correlation_id=correlation_id or "",
    )


async def run_agent_task(
    session: AsyncSession, job_id: str, *, stream_bars: BarBatchStreamer = iter_bar_batches
) -> dict[str, Any]:
    """Execute the durable Agent task-execution job. Does not commit (the worker
    scope commits). ``stream_bars`` is the SAME S3-backed default ``run_backtest``
    itself uses in production; the override exists only so integration tests can
    inject deterministic bars without a real object store (mirrors
    ``run_backtest``'s own test seam — the engine boundary is untouched)."""
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found.")
    task_id = str((job.payload or {}).get("task_id") or "")
    task = await al_repo.get_task(session, task_id)
    if task is None:
        raise ValueError(f"Agent task '{task_id}' not found for job '{job_id}'.")

    # At-least-once delivery guard (mirrors run_backtest): a redelivered message
    # for an already-terminal task must never re-run the pipeline.
    if task.status in TASK_TERMINAL_STATES:
        return _task_ref(task)

    runtime = await al_repo.get_runtime(session, task.agent_id)
    if runtime is None:
        raise ValueError(f"Agent runtime '{task.agent_id}' not found for task '{task_id}'.")
    # Lock the runtime BEFORE the task, then re-read the task under that lock —
    # the same TOCTOU-closing order ``agent_control.py::stop_run`` uses, since
    # Pause/Resume/Stop and the Coordinator loop are now concurrent with this
    # executor.
    await session.refresh(runtime, with_for_update=True)
    await session.refresh(task, with_for_update=True)
    if task.status in TASK_TERMINAL_STATES:
        return _task_ref(task)
    if task.status is not AgentTaskStatus.QUEUED:
        # A concurrent delivery already claimed it, or it is PAUSED awaiting a
        # human Resume — never double-run it.
        return _task_ref(task)

    correlation_id = job.correlation_id
    actor = _agent_actor(correlation_id=correlation_id)

    # A control was already pending before this delivery even reached a safe
    # boundary. The task is still QUEUED — QUEUED -> PAUSED is not a legal
    # transition (``state_machine.py``), and a QUEUED task is never in
    # TASK_STOPPABLE_STATES, so ``stop_run`` itself already rejects a STOP
    # against it (only PAUSE can be pending here). Applying the control with NO
    # active task set is a deliberate no-op on the task: the runtime goes PAUSED,
    # the task is left QUEUED untouched, and the Job row is left QUEUED too — the
    # generic redelivery sweep (INF-03) retries this SAME job after a human
    # Resume, with zero bespoke wake-up plumbing.
    if runtime.pending_control is not None:
        await coordinator.apply_pending_control(
            session, agent_id=runtime.agent_id, correlation_id=correlation_id
        )
        return _task_ref(task)

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    _transition(task, AgentTaskStatus.RUNNING)
    runtime.active_task_id = task.task_id
    await _checkpoint(
        session, task=task, runtime=runtime, stage="task_started", correlation_id=correlation_id
    )
    await al_repo.append_event(
        session,
        event_type="task_started",
        actor_principal_id=None,
        actor_kind=_SYSTEM_KIND,
        task_id=task.task_id,
        payload={"task_type": task.task_type},
        correlation_id=correlation_id,
    )

    exposed_tools = await _exposed_tools(session, task.task_id)
    outcome = await _run_research_pipeline(
        session,
        actor=actor,
        task=task,
        runtime=runtime,
        exposed_tools=exposed_tools,
        correlation_id=correlation_id,
        stream_bars=stream_bars,
    )

    # The job's own completion is distinct from the task's business outcome: a
    # FAILED task is still a job that did its job (mirrors run_backtest, where a
    # terminal FAILED run is not a job exception either).
    job.status = JobStatus.SUCCEEDED
    job.finished_at = datetime.now(UTC)
    job.result_ref = outcome
    return outcome


def _transition(task: Any, to: AgentTaskStatus) -> None:
    if not task_transition_allowed(task.status, to):
        raise RuntimeError(f"Illegal agent task transition {task.status} -> {to} ({task.task_id}).")
    task.status = to


def _task_ref(task: Any) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "status": str(task.status),
        "stage": task.stage,
        "failure_reason": task.failure_reason,
    }


async def _checkpoint(
    session: AsyncSession, *, task: Any, runtime: Any, stage: str, correlation_id: str | None
) -> Any:
    checkpoint_no = await al_repo.max_checkpoint_no(session, task.task_id) + 1
    checkpoint = await al_repo.create_checkpoint(
        session,
        task_id=task.task_id,
        checkpoint_no=checkpoint_no,
        stage=stage,
        state_ref=f"state::{task.task_id}::{checkpoint_no}",
        context_manifest_id=task.context_manifest_id,
        plan_revision=checkpoint_no,
    )
    task.stage = stage
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


async def _exposed_tools(session: AsyncSession, task_id: str) -> frozenset[str]:
    """Recover the CR-08 plan-time tool menu recorded on ``agent_task_created``
    (the exposure is an event payload, not a task column — doc 22 §11)."""
    stmt = (
        select(AgentEvent)
        .where(AgentEvent.task_id == task_id, AgentEvent.type == "agent_task_created")
        .order_by(AgentEvent.seq.asc())
        .limit(1)
    )
    event = (await session.execute(stmt)).scalars().first()
    if event is None:
        return frozenset()
    return frozenset(str(t) for t in (event.payload or {}).get("exposed_tools", []))


async def _pending_control_interrupt(
    session: AsyncSession, *, runtime: Any, task: Any, correlation_id: str | None
) -> dict[str, Any] | None:
    """Re-check for a pause/stop requested mid-run at this safe boundary
    (doc 18 §8.4) and apply it. Returns the interrupted task ref, or ``None`` when
    the pipeline may continue."""
    await session.refresh(runtime, with_for_update=True)
    if runtime.pending_control is None:
        return None
    await coordinator.apply_pending_control(
        session, agent_id=runtime.agent_id, correlation_id=correlation_id
    )
    await session.refresh(task)
    return _task_ref(task)


async def _fail_task(
    session: AsyncSession,
    *,
    task: Any,
    runtime: Any,
    code: str,
    message: str,
    correlation_id: str | None,
) -> dict[str, Any]:
    _transition(task, AgentTaskStatus.FAILED)
    task.failure_reason = f"{code}: {message}"[:_FAILURE_REASON_LIMIT]
    runtime.active_task_id = None
    await _checkpoint(
        session, task=task, runtime=runtime, stage="task_failed", correlation_id=correlation_id
    )
    await al_repo.append_event(
        session,
        event_type="task_failed",
        actor_principal_id=None,
        actor_kind=_SYSTEM_KIND,
        task_id=task.task_id,
        payload={"code": code, "message": message},
        correlation_id=correlation_id,
    )
    audit_repo.add_audit_event(
        session,
        event_kind="agent.task.failed",
        actor_principal_id=None,
        actor_kind=_SYSTEM_KIND,
        target_entity_id=task.task_id,
        target_entity_type=_TASK_TARGET,
        previous_state=str(AgentTaskStatus.RUNNING),
        new_state=str(AgentTaskStatus.FAILED),
        reason=code,
        correlation_id=correlation_id,
        metadata={"message": message},
    )
    audit_repo.add_outbox_event(
        session,
        event_type="agent.task.failed",
        resource_type=_TASK_TARGET,
        resource_id=task.task_id,
        payload={"task_id": task.task_id, "code": code, "message": message},
        correlation_id=correlation_id,
    )
    return _task_ref(task)


async def _succeed_task(
    session: AsyncSession,
    *,
    task: Any,
    runtime: Any,
    result_id: str | None,
    artifact_id: str | None,
    correlation_id: str | None,
) -> dict[str, Any]:
    _transition(task, AgentTaskStatus.SUCCEEDED)
    task.progress = 100
    runtime.active_task_id = None
    await _checkpoint(
        session, task=task, runtime=runtime, stage="task_succeeded", correlation_id=correlation_id
    )
    await al_repo.append_event(
        session,
        event_type="task_succeeded",
        actor_principal_id=None,
        actor_kind=_SYSTEM_KIND,
        task_id=task.task_id,
        payload={"result_id": result_id, "artifact_id": artifact_id},
        correlation_id=correlation_id,
    )
    audit_repo.add_audit_event(
        session,
        event_kind="agent.task.succeeded",
        actor_principal_id=None,
        actor_kind=_SYSTEM_KIND,
        target_entity_id=task.task_id,
        target_entity_type=_TASK_TARGET,
        previous_state=str(AgentTaskStatus.RUNNING),
        new_state=str(AgentTaskStatus.SUCCEEDED),
        correlation_id=correlation_id,
        metadata={"result_id": result_id, "artifact_id": artifact_id},
    )
    audit_repo.add_outbox_event(
        session,
        event_type="agent.task.succeeded",
        resource_type=_TASK_TARGET,
        resource_id=task.task_id,
        payload={"task_id": task.task_id, "result_id": result_id, "artifact_id": artifact_id},
        correlation_id=correlation_id,
    )
    ref = _task_ref(task)
    ref["result_id"] = result_id
    ref["artifact_id"] = artifact_id
    return ref


async def _run_research_pipeline(
    session: AsyncSession,
    *,
    actor: Actor,
    task: Any,
    runtime: Any,
    exposed_tools: frozenset[str],
    correlation_id: str | None,
    stream_bars: BarBatchStreamer,
) -> dict[str, Any]:
    """The deterministic plan for ``task_type == "research"`` (the only type the
    Coordinator materializes today, ``agent_loop.py::_spawn_followup_task``):
    resolve the Agent's own composition -> Ready Check -> backtest admission ->
    real engine run -> result read -> hypothesis artifact evidenced by the result
    (doc 18 §10 parity with the human RUN flow). An unrecognized task_type, an
    unexposed tool, a governed rejection, a non-ready composition, or an engine
    failure are all honest FAILED outcomes — never a fabricated step."""
    if task.task_type != "research":
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code="UNSUPPORTED_TASK_TYPE",
            message=f"No executor pipeline is defined for task_type '{task.task_type}'.",
            correlation_id=correlation_id,
        )

    interrupted = await _pending_control_interrupt(
        session, runtime=runtime, task=task, correlation_id=correlation_id
    )
    if interrupted is not None:
        return interrupted

    mainboard = await mb_query.get_default_mainboard(session, actor)
    composition_id = str(mainboard["workspace_id"])
    await _checkpoint(
        session,
        task=task,
        runtime=runtime,
        stage="composition_resolved",
        correlation_id=correlation_id,
    )

    interrupted = await _pending_control_interrupt(
        session, runtime=runtime, task=task, correlation_id=correlation_id
    )
    if interrupted is not None:
        return interrupted

    if "backtest.ready_check" not in exposed_tools:
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code="TOOL_NOT_EXPOSED",
            message="'backtest.ready_check' was not offerable in this task's plan-time tool menu.",
            correlation_id=correlation_id,
        )
    try:
        report = await agent_tools.dispatch_tool_call(
            session,
            actor,
            tool_name="backtest.ready_check",
            policy_scope="execution",
            request={"composition_id": composition_id},
            task_id=task.task_id,
            idempotency_key=f"{task.task_id}:ready_check",
            agent_id=runtime.agent_id,
        )
    except AppError as exc:
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code=getattr(exc, "code", type(exc).__name__),
            message=str(exc),
            correlation_id=correlation_id,
        )
    if report.get("status") != "succeeded":
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code=str(report.get("reason_code") or "READY_CHECK_REJECTED"),
            message=str(report.get("reason") or "Ready Check was rejected."),
            correlation_id=correlation_id,
        )
    if report.get("state") == str(ReadinessState.NOT_READY):
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code="NOT_READY",
            message=f"Composition '{composition_id}' is not ready to run: {report.get('summary')}",
            correlation_id=correlation_id,
        )
    await _checkpoint(
        session, task=task, runtime=runtime, stage="ready_checked", correlation_id=correlation_id
    )

    interrupted = await _pending_control_interrupt(
        session, runtime=runtime, task=task, correlation_id=correlation_id
    )
    if interrupted is not None:
        return interrupted

    if "backtest.request" not in exposed_tools:
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code="TOOL_NOT_EXPOSED",
            message="'backtest.request' was not offerable in this task's plan-time tool menu.",
            correlation_id=correlation_id,
        )
    try:
        run_req = await agent_tools.dispatch_tool_call(
            session,
            actor,
            tool_name="backtest.request",
            policy_scope="execution",
            request={
                "composition_id": composition_id,
                "ready_report_id": report.get("report_id"),
                "expected_fingerprint": report.get("composition_fingerprint"),
            },
            task_id=task.task_id,
            idempotency_key=f"{task.task_id}:backtest_request",
            agent_id=runtime.agent_id,
        )
    except AppError as exc:
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code=getattr(exc, "code", type(exc).__name__),
            message=str(exc),
            correlation_id=correlation_id,
        )
    if run_req.get("status") != "succeeded":
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code=str(run_req.get("reason_code") or "BACKTEST_REQUEST_REJECTED"),
            message=str(run_req.get("reason") or "Backtest admission was rejected."),
            correlation_id=correlation_id,
        )
    await _checkpoint(
        session,
        task=task,
        runtime=runtime,
        stage="backtest_requested",
        correlation_id=correlation_id,
    )

    interrupted = await _pending_control_interrupt(
        session, runtime=runtime, task=task, correlation_id=correlation_id
    )
    if interrupted is not None:
        return interrupted

    # The REAL engine, called exactly as the ``backtest`` queue actor would call
    # it — untouched (spec F-20 scope boundary). Any genuinely unexpected
    # exception here propagates (worker retry + stale-job recovery); an expected
    # engine failure is a normal terminal ``state``, handled below.
    engine_out = await run_backtest(session, str(run_req.get("job_id")), stream_bars=stream_bars)
    if engine_out.get("state") != "succeeded":
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code=str(engine_out.get("failure_code") or "RUN_FAILED"),
            message=f"Backtest run did not succeed: {engine_out.get('state')}",
            correlation_id=correlation_id,
        )
    result_id = str(engine_out.get("result_id"))
    await _checkpoint(
        session, task=task, runtime=runtime, stage="engine_completed", correlation_id=correlation_id
    )

    interrupted = await _pending_control_interrupt(
        session, runtime=runtime, task=task, correlation_id=correlation_id
    )
    if interrupted is not None:
        return interrupted

    if "result.query" not in exposed_tools:
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code="TOOL_NOT_EXPOSED",
            message="'result.query' was not offerable in this task's plan-time tool menu.",
            correlation_id=correlation_id,
        )
    queried = await agent_tools.dispatch_tool_call(
        session,
        actor,
        tool_name="result.query",
        policy_scope="observation",
        request={"result_id": result_id},
        task_id=task.task_id,
        agent_id=runtime.agent_id,
    )
    if not queried.get("found"):
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code="RESULT_NOT_FOUND",
            message=f"Backtest result '{result_id}' could not be read back through the gateway.",
            correlation_id=correlation_id,
        )

    interrupted = await _pending_control_interrupt(
        session, runtime=runtime, task=task, correlation_id=correlation_id
    )
    if interrupted is not None:
        return interrupted

    if "artifact.create" not in exposed_tools:
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code="TOOL_NOT_EXPOSED",
            message="'artifact.create' was not offerable in this task's plan-time tool menu.",
            correlation_id=correlation_id,
        )
    hypothesis = await agent_tools.dispatch_tool_call(
        session,
        actor,
        tool_name="artifact.create",
        policy_scope="research",
        request={
            "title": f"Autonomous research outcome: {task.title[:80]}",
            "mechanism": (
                f"Backtest run '{run_req.get('run_id')}' on the Agent's own composition "
                f"'{composition_id}' completed with a real, deterministic Result."
            ),
            "evidence_refs": [result_id],
            "links": [
                {
                    "target_type": "backtest_result",
                    "target_id": result_id,
                    "relation_type": "evidenced_by",
                }
            ],
        },
        task_id=task.task_id,
        idempotency_key=f"{task.task_id}:artifact_create",
        agent_id=runtime.agent_id,
    )
    if hypothesis.get("status") != "succeeded":
        return await _fail_task(
            session,
            task=task,
            runtime=runtime,
            code=str(hypothesis.get("reason_code") or "ARTIFACT_CREATE_REJECTED"),
            message=str(hypothesis.get("reason") or "Hypothesis artifact creation was rejected."),
            correlation_id=correlation_id,
        )

    return await _succeed_task(
        session,
        task=task,
        runtime=runtime,
        result_id=result_id,
        artifact_id=hypothesis.get("artifact_id"),
        correlation_id=correlation_id,
    )


__all__ = ["run_agent_task"]
