"""Spec F-20 — the durable Alpha Agent task executor, end to end.

Auto-skips without PostgreSQL. Unlike ``test_e2e_agent_loop.py`` (which proves the
Tool Gateway primitives work by calling ``dispatch_tool_call`` manually, step by
step), this file proves the DURABLE EXECUTOR drives a directive to a completed
hypothesis with ZERO manual tool-call orchestration from the test: one
``run_coordinator_cycle`` plus exactly one ``run_agent_task`` call.

Covers the F-20 acceptance criteria:
- a directive completes end to end without test code manually calling
  ``dispatch_tool_call`` for each step;
- every step/tool call/result/failure/state transition is visible via
  ``AgentTask``/``AgentCheckpoint``/``AgentEvent``/``AuditEvent``;
- cancellation (Stop) is a live, checkpoint-safe control — proven by wiring
  ``runtime.active_task_id`` for the first time;
- idempotency — a redelivered job for an already-terminal task is a no-op.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import agent_control as agent_control_cmd
from entropia.application.commands.agent_loop import run_coordinator_cycle
from entropia.application.jobs.agent_executor import run_agent_task
from entropia.domain.agent_lab.enums import AgentTaskPriority, AgentTaskStatus, RuntimeStatus
from entropia.infrastructure.postgres.models import (
    AgentEvent,
    AgentRuntime,
    AgentTask,
    AgentToolCall,
    BacktestResult,
    HypothesisArtifact,
    Job,
)
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from tests.integration.test_e2e_agent_loop import (
    _AGENT_PID,
    ADMIN,
    _agent_composition,
    _approved_market,
    _e2e_bars,
    _real_package,
    _seed_runtime_and_principals,
)

pytestmark = pytest.mark.integration


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _queue_directive_and_spawn_job(session) -> tuple[str, str]:
    """The Coordinator half: consume a directive, materialize the QUEUED task
    AND its durable executor Job (spec F-20) — mirrors what
    ``apps/agent_coordinator/__main__.py`` does every tick."""
    market = await _approved_market(session)
    package = await _real_package(session)
    await session.commit()
    await _agent_composition(session, market, package)

    directive = await al_repo.create_directive(
        session,
        author_principal_id="admin_1",
        target_agent_id="alpha-agent",
        related_task_id=None,
        text="Probe BTCUSDT robustness on the Agent's own pinned composition",
        priority=AgentTaskPriority.HIGH,
        correlation_id="corr_f20",
    )
    await session.commit()

    cycle = await run_coordinator_cycle(session)
    await session.commit()
    assert cycle["consumed"]["consumed"] == directive.directive_id
    task_id = cycle["followup_task_id"]
    job_id = cycle["executor_job_id"]
    assert task_id is not None and job_id is not None
    job = await session.get(Job, job_id)
    assert job is not None and job.queue == "agent-executor" and job.status.value == "queued"
    return task_id, job_id


async def test_executor_drives_directive_to_hypothesis_without_manual_dispatch(session) -> None:
    await _seed_runtime_and_principals(session)
    task_id, job_id = await _queue_directive_and_spawn_job(session)

    # ONE call. No manual dispatch_tool_call anywhere in this test — the
    # executor plans + selects tools + executes the real engine + evaluates the
    # result + creates the hypothesis on its own (spec F-20 acceptance).
    outcome = await run_agent_task(session, job_id, stream_bars=_e2e_bars)
    await session.commit()

    assert outcome["status"] == str(AgentTaskStatus.SUCCEEDED)
    task = await session.get(AgentTask, task_id)
    assert task is not None
    assert task.status is AgentTaskStatus.SUCCEEDED
    assert task.stage == "task_succeeded"
    assert task.progress == 100

    # runtime.active_task_id was set while RUNNING and cleared on completion —
    # the first code path that ever writes it (Pause/Resume/Stop become live).
    runtime = await session.get(AgentRuntime, "alpha-agent")
    assert runtime is not None and runtime.active_task_id is None

    # A real, deterministic Result was produced by the untouched engine.
    assert await _count(session, BacktestResult) == 1
    assert outcome["result_id"] is not None

    # The hypothesis artifact carries provenance to that result.
    artifact = await session.get(HypothesisArtifact, outcome["artifact_id"])
    assert artifact is not None
    assert artifact.created_by_principal_id == _AGENT_PID
    assert artifact.source_task_id == task_id

    # Every governed step is a durable tool-call row: ready_check, backtest
    # request, result query, artifact create.
    assert await _count(session, AgentToolCall) == 4

    # Every step/transition is visible: checkpoints + AgentEvents + audit trail.
    checkpoints = await al_repo.list_checkpoints(session, task_id)
    stages = [c.stage for c in checkpoints]
    assert stages == [
        "task_started",
        "composition_resolved",
        "ready_checked",
        "backtest_requested",
        "engine_completed",
        "task_succeeded",
    ]
    event_types = {
        e.type
        for e in (await session.execute(select(AgentEvent).where(AgentEvent.task_id == task_id)))
        .scalars()
        .all()
    }
    assert {"task_started", "task_succeeded"} <= event_types
    audit_kinds = {
        e.event_kind for e in (await session.execute(select(audit_repo.AuditEvent))).scalars().all()
    }
    assert "agent.task.succeeded" in audit_kinds

    job = await session.get(Job, job_id)
    assert job is not None and job.status.value == "succeeded"

    # Redelivery of the SAME job for an already-terminal task is a no-op
    # (idempotency, AL-14) — no duplicate tool calls / results / checkpoints.
    replay = await run_agent_task(session, job_id)
    await session.commit()
    assert replay["status"] == str(AgentTaskStatus.SUCCEEDED)
    assert await _count(session, AgentToolCall) == 4
    assert await _count(session, BacktestResult) == 1
    assert len(await al_repo.list_checkpoints(session, task_id)) == 6


async def test_executor_defers_a_queued_task_under_a_pending_pause(session) -> None:
    """Pause is a checkpoint-safe control request (doc 18 §8.4) — legal any time
    the runtime is ACTIVE, even before an executor delivery has started. A QUEUED
    task has no safe checkpoint of its own yet (QUEUED -> PAUSED is not a legal
    transition, ``state_machine.py``), so the correct behavior is: the RUNTIME
    goes PAUSED, the task is left QUEUED untouched (never a false RUNNING start,
    never a Result), and the Job row is left QUEUED for the generic redelivery
    sweep (INF-03) to retry after a human Resume."""
    await _seed_runtime_and_principals(session)
    task_id, job_id = await _queue_directive_and_spawn_job(session)

    await agent_control_cmd.pause_runtime(session, ADMIN, agent_id="alpha-agent")
    await session.commit()

    outcome = await run_agent_task(session, job_id, stream_bars=_e2e_bars)
    await session.commit()

    assert outcome["status"] == str(AgentTaskStatus.QUEUED)
    task = await session.get(AgentTask, task_id)
    assert task is not None and task.status is AgentTaskStatus.QUEUED

    runtime = await session.get(AgentRuntime, "alpha-agent")
    assert runtime is not None
    assert runtime.active_task_id is None
    assert runtime.status is RuntimeStatus.PAUSED
    assert runtime.pending_control is None

    # No false start: no Result, no governed tool call.
    assert await _count(session, BacktestResult) == 0
    assert await _count(session, AgentToolCall) == 0

    # The Job row is untouched (still QUEUED) — a redelivery of this SAME job
    # after Resume will re-attempt the task from scratch.
    job = await session.get(Job, job_id)
    assert job is not None and job.status.value == "queued"

    await agent_control_cmd.resume_runtime(session, ADMIN, agent_id="alpha-agent")
    await session.commit()
    runtime = await session.get(AgentRuntime, "alpha-agent")
    assert runtime is not None and runtime.status is RuntimeStatus.ACTIVE

    # Redelivering the SAME job now (no pending control, task still QUEUED)
    # drives the full pipeline to completion — proves the deferral was a true
    # no-op, not a lost task.
    resumed_outcome = await run_agent_task(session, job_id, stream_bars=_e2e_bars)
    await session.commit()
    assert resumed_outcome["status"] == str(AgentTaskStatus.SUCCEEDED)
    assert await _count(session, BacktestResult) == 1
