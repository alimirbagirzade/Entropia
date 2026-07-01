"""Stage 6a-2 — continuous Coordinator loop against a real database (doc 18 §8, §14).

Auto-skips without PostgreSQL. The integration conftest builds the schema with
``create_all`` (not the migration), so the singleton ``alpha-agent`` runtime that
the migration seeds is created here manually.

Covers: AL-01 (loop runs independent of any UI; browser state irrelevant), the
directive -> safe-checkpoint -> AUTONOMOUS follow-up task materialization (doc 18
§8.3, §10), AL-08 (pause halts consumption at a checkpoint), AL-10 (stop cancels
the active sub-run), and AL-14 (a re-run consumes no directive twice -> no
duplicate follow-up).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands.agent_loop import run_coordinator_cycle
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    DirectiveStatus,
    RuntimeControl,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.lifecycle.enums import PrincipalType
from entropia.infrastructure.postgres.models import AgentEvent, AgentRuntime, AgentTask, Principal
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo

pytestmark = pytest.mark.integration

_ADMIN = "admin_1"


async def _seed(session) -> AgentRuntime:
    session.add(Principal(principal_id=_ADMIN, principal_type=PrincipalType.HUMAN))
    runtime = AgentRuntime(
        agent_id=ALPHA_AGENT_ID,
        mode=RuntimeMode.CONTINUOUS,
        status=RuntimeStatus.ACTIVE,
        row_version=1,
    )
    session.add(runtime)
    await session.flush()
    return runtime


async def _activate_task(session, runtime: AgentRuntime) -> AgentTask:
    task = await al_repo.create_task(
        session,
        agent_id=ALPHA_AGENT_ID,
        task_type="research",
        title="BTCUSDT funding reversal",
        source="autonomous",
        priority=AgentTaskPriority.AUTONOMOUS,
        status=AgentTaskStatus.RUNNING,
        stage="robustness",
        context_manifest_id="mkt_manifest_1",
    )
    runtime.active_task_id = task.task_id
    await session.flush()
    return task


async def _queue_directive(session, text: str, *, related_task_id: str | None = None):
    return await al_repo.create_directive(
        session,
        author_principal_id=_ADMIN,
        target_agent_id=ALPHA_AGENT_ID,
        related_task_id=related_task_id,
        text=text,
        priority=AgentTaskPriority.HIGH,
        correlation_id="corr_1",
    )


async def _count_autonomous_tasks(session) -> int:
    stmt = select(func.count()).where(
        AgentTask.source == "directive",
        AgentTask.priority == AgentTaskPriority.AUTONOMOUS,
    )
    return int((await session.execute(stmt)).scalar_one())


async def test_loop_consumes_directive_and_spawns_autonomous_followup(session) -> None:
    # AL-01 / §8.3: the loop runs with no UI, consumes a queued directive at a
    # safe checkpoint, and materializes an AUTONOMOUS follow-up task.
    runtime = await _seed(session)
    active = await _activate_task(session, runtime)
    directive = await _queue_directive(
        session, "Probe regime shift", related_task_id=active.task_id
    )

    summary = await run_coordinator_cycle(session, agent_id=ALPHA_AGENT_ID, correlation_id="corr_1")

    assert summary["consumed"]["consumed"] == directive.directive_id
    assert summary["followup_task_id"] is not None

    await session.refresh(directive)
    assert directive.status is DirectiveStatus.CONSUMED
    assert directive.consumed_checkpoint_id is not None

    followup = await al_repo.get_task(session, summary["followup_task_id"])
    assert followup is not None
    assert followup.priority is AgentTaskPriority.AUTONOMOUS
    assert followup.status is AgentTaskStatus.QUEUED
    assert followup.source == "directive"
    assert followup.parent_task_id == active.task_id

    # A safe checkpoint was written for the active task before consumption.
    latest = await al_repo.get_latest_checkpoint(session, active.task_id)
    assert latest is not None
    # Follow-up materialization is observable on the event stream.
    created = (
        await session.execute(select(func.count()).where(AgentEvent.type == "agent_task_created"))
    ).scalar_one()
    assert int(created) == 1


async def test_loop_is_idempotent_no_duplicate_followup(session) -> None:
    # AL-14: a second cycle finds no queued directive -> no duplicate follow-up.
    runtime = await _seed(session)
    await _activate_task(session, runtime)
    await _queue_directive(session, "Probe regime shift")

    first = await run_coordinator_cycle(session, agent_id=ALPHA_AGENT_ID)
    second = await run_coordinator_cycle(session, agent_id=ALPHA_AGENT_ID)

    assert first["consumed"]["consumed"] is not None
    assert second["consumed"]["consumed"] is None
    assert second["followup_task_id"] is None
    assert await _count_autonomous_tasks(session) == 1


async def test_pause_halts_consumption_at_checkpoint(session) -> None:
    # AL-08: a pending pause is applied at a safe checkpoint; a queued directive is
    # NOT consumed while paused (queue/directives preserved).
    runtime = await _seed(session)
    active = await _activate_task(session, runtime)
    runtime.pending_control = RuntimeControl.PAUSE
    directive = await _queue_directive(session, "Deferred while paused")
    await session.flush()

    summary = await run_coordinator_cycle(session, agent_id=ALPHA_AGENT_ID)

    assert summary["runtime_status"] == str(RuntimeStatus.PAUSED)
    assert summary["consumed"] is None
    await session.refresh(runtime)
    assert runtime.status is RuntimeStatus.PAUSED
    await session.refresh(directive)
    assert directive.status is DirectiveStatus.QUEUED
    # Pause is checkpoint-safe: the active task's checkpoint was written.
    assert await al_repo.get_latest_checkpoint(session, active.task_id) is not None


async def test_stop_cancels_active_run_no_result(session) -> None:
    # AL-10: stop is a controlled cancellation of the active sub-run.
    runtime = await _seed(session)
    active = await _activate_task(session, runtime)
    runtime.pending_control = RuntimeControl.STOP
    await session.flush()

    summary = await run_coordinator_cycle(session, agent_id=ALPHA_AGENT_ID)

    assert summary["control"]["applied"] == str(RuntimeControl.STOP)
    await session.refresh(active)
    assert active.status is AgentTaskStatus.CANCELLED
    await session.refresh(runtime)
    assert runtime.status is RuntimeStatus.ACTIVE
    assert runtime.active_task_id is None
