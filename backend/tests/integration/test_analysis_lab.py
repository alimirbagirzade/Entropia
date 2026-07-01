"""Stage 6a — Analysis Lab observation/control plane against a real database (doc 18).

Auto-skips without PostgreSQL. The integration conftest builds the schema with
``create_all`` (not the migration), so the singleton ``alpha-agent`` runtime that
the migration seeds is created here manually. Principals are seeded because
directives/messages FK to ``principals``.

Covers acceptance IDs: AL-02 (admin overview projection), AL-03 (user denied),
AL-04 (discussion never mutates the active task), AL-05 (High directive queued then
consumed only at a safe checkpoint), AL-06 (empty text rejected), AL-07 (autonomous
priority rejected), AL-08 (pause applied at checkpoint), AL-09 (supervisor lifecycle
denied), AL-10 (stop cancels the sub-run, no Result), AL-17 (concurrent control
conflict), AL-18 (context manifest pinned into the checkpoint). Plus an L1 FK
insert-order proof (task -> checkpoint -> hypothesis -> artifact_link), keyset
pagination and soft-delete hiding.
"""

from __future__ import annotations

import pytest

from entropia.application.commands import agent_control as ctrl
from entropia.application.commands import agent_coordinator as coord
from entropia.application.commands import lab_message as msg
from entropia.application.queries import agent_workspace as ws
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    DirectiveStatus,
    HypothesisStatus,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.models import AgentRuntime, Principal
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.shared.errors import (
    AccessDeniedError,
    AgentRunNotStoppableError,
    AgentRuntimeStateConflictError,
    InvalidDirectivePriorityError,
    MessageTextRequiredError,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
SUPERVISOR = Actor(principal_id="sup_1", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_MANIFEST_ID = "mkt_manifest_1"


async def _seed_principals(session) -> None:
    for pid in ("admin_1", "sup_1", "user_1"):
        session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_runtime(session) -> AgentRuntime:
    runtime = AgentRuntime(
        agent_id=ALPHA_AGENT_ID,
        mode=RuntimeMode.CONTINUOUS,
        status=RuntimeStatus.ACTIVE,
        row_version=1,
    )
    session.add(runtime)
    await session.flush()
    return runtime


async def _activate_task(session, runtime: AgentRuntime):
    task = await al_repo.create_task(
        session,
        agent_id=ALPHA_AGENT_ID,
        task_type="research",
        title="High-funding BTCUSDT reversal",
        source="autonomous",
        priority=AgentTaskPriority.AUTONOMOUS,
        status=AgentTaskStatus.RUNNING,
        stage="robustness",
        context_manifest_id=_MANIFEST_ID,
    )
    runtime.active_task_id = task.task_id
    await session.flush()
    return task


# --- AL-02 / AL-03 : overview + policy -------------------------------------


async def test_overview_admin_projection(session) -> None:
    await _seed_principals(session)
    runtime = await _seed_runtime(session)
    await _activate_task(session, runtime)

    overview = await ws.get_overview(session, ADMIN)

    assert overview["runtime"]["agent_id"] == ALPHA_AGENT_ID
    assert overview["runtime"]["status"] == "active"
    assert overview["runtime"]["mode"] == "continuous"
    assert overview["active_task"]["title"] == "High-funding BTCUSDT reversal"
    assert overview["context_bundle"]["context_manifest_id"] == _MANIFEST_ID
    assert overview["queue"]["counts"].get("running") == 1
    assert overview["output_board"]["hypotheses"] == []


async def test_overview_user_denied(session) -> None:
    await _seed_principals(session)
    await _seed_runtime(session)
    with pytest.raises(AccessDeniedError):
        await ws.get_overview(session, USER)


async def test_directive_user_denied(session) -> None:
    await _seed_principals(session)
    await _seed_runtime(session)
    with pytest.raises(AccessDeniedError):
        await ctrl.create_directive(session, USER, text="do x", target_agent_id=ALPHA_AGENT_ID)


# --- AL-04 : discussion never mutates the active task ----------------------


async def test_discussion_message_does_not_change_active_task(session) -> None:
    await _seed_principals(session)
    runtime = await _seed_runtime(session)
    task = await _activate_task(session, runtime)

    result = await msg.record_discussion_message(
        session, ADMIN, text="Which dataset revisions are pinned?"
    )

    assert result["active_task_interrupted"] is False
    assert result["message"]["type"] == "message"
    assert result["assistant_response"]["type"] == "assistant"
    assert "did not interrupt" in result["assistant_response"]["text"]
    refreshed = await al_repo.get_task(session, task.task_id)
    assert refreshed is not None
    assert refreshed.status is AgentTaskStatus.RUNNING
    assert refreshed.progress == 0


# --- AL-05 : High directive queued, consumed only at a safe checkpoint ------


async def test_high_directive_queued_then_consumed_at_checkpoint(session) -> None:
    await _seed_principals(session)
    runtime = await _seed_runtime(session)
    task = await _activate_task(session, runtime)

    queued = await ctrl.create_directive(
        session,
        SUPERVISOR,
        text="Add a low-volatility regime split.",
        priority="high",
        target_agent_id=ALPHA_AGENT_ID,
    )
    assert queued["status"] == "queued"
    assert queued["priority"] == "high"
    assert queued["active_task_interrupted"] is False
    # Active task untouched by queuing.
    still = await al_repo.get_task(session, task.task_id)
    assert still is not None and still.status is AgentTaskStatus.RUNNING

    consumed = await coord.consume_next_directive(session, agent_id=ALPHA_AGENT_ID)
    assert consumed["consumed"] == queued["directive_id"]
    assert consumed["checkpoint_id"] is not None
    directive = await al_repo.get_directive(session, queued["directive_id"])
    assert directive is not None
    assert directive.status is DirectiveStatus.CONSUMED
    assert directive.consumed_checkpoint_id == consumed["checkpoint_id"]


async def test_directive_high_consumed_before_normal(session) -> None:
    await _seed_principals(session)
    runtime = await _seed_runtime(session)
    await _activate_task(session, runtime)

    normal = await ctrl.create_directive(
        session, ADMIN, text="normal one", priority="normal", target_agent_id=ALPHA_AGENT_ID
    )
    high = await ctrl.create_directive(
        session, ADMIN, text="high one", priority="high", target_agent_id=ALPHA_AGENT_ID
    )
    consumed = await coord.consume_next_directive(session, agent_id=ALPHA_AGENT_ID)
    assert consumed["consumed"] == high["directive_id"]
    assert consumed["consumed"] != normal["directive_id"]


# --- AL-06 / AL-07 : validation --------------------------------------------


async def test_empty_directive_rejected(session) -> None:
    await _seed_principals(session)
    await _seed_runtime(session)
    with pytest.raises(MessageTextRequiredError):
        await ctrl.create_directive(session, ADMIN, text="   ", target_agent_id=ALPHA_AGENT_ID)


async def test_autonomous_and_unknown_priority_rejected(session) -> None:
    await _seed_principals(session)
    await _seed_runtime(session)
    with pytest.raises(InvalidDirectivePriorityError):
        await ctrl.create_directive(
            session, ADMIN, text="x", priority="autonomous", target_agent_id=ALPHA_AGENT_ID
        )
    with pytest.raises(InvalidDirectivePriorityError):
        await ctrl.create_directive(
            session, ADMIN, text="x", priority="bogus", target_agent_id=ALPHA_AGENT_ID
        )


# --- AL-08 / AL-18 : pause applied at a safe checkpoint that pins manifest ---


async def test_admin_pause_applies_at_safe_checkpoint(session) -> None:
    await _seed_principals(session)
    runtime = await _seed_runtime(session)
    task = await _activate_task(session, runtime)

    accepted = await ctrl.pause_runtime(session, ADMIN, agent_id=ALPHA_AGENT_ID)
    assert accepted["control"] == "pause"
    assert accepted["delivery_policy"] == "next_safe_checkpoint"
    runtime_after_request = await al_repo.get_runtime(session, ALPHA_AGENT_ID)
    assert runtime_after_request is not None
    assert runtime_after_request.pending_control is not None
    # Not yet paused — only requested.
    assert runtime_after_request.status is RuntimeStatus.ACTIVE

    applied = await coord.apply_pending_control(session, agent_id=ALPHA_AGENT_ID)
    assert applied["applied"] == "pause"
    assert applied["runtime_status"] == "paused"
    runtime_paused = await al_repo.get_runtime(session, ALPHA_AGENT_ID)
    assert runtime_paused is not None and runtime_paused.status is RuntimeStatus.PAUSED
    assert runtime_paused.pending_control is None
    paused_task = await al_repo.get_task(session, task.task_id)
    assert paused_task is not None and paused_task.status is AgentTaskStatus.PAUSED
    # AL-18: the checkpoint pins the task's context manifest (no 'latest' switch).
    checkpoint = await al_repo.get_latest_checkpoint(session, task.task_id)
    assert checkpoint is not None and checkpoint.context_manifest_id == _MANIFEST_ID


# --- AL-09 : supervisor lifecycle denied -----------------------------------


async def test_supervisor_lifecycle_denied(session) -> None:
    await _seed_principals(session)
    runtime = await _seed_runtime(session)
    task = await _activate_task(session, runtime)
    with pytest.raises(AccessDeniedError):
        await ctrl.pause_runtime(session, SUPERVISOR, agent_id=ALPHA_AGENT_ID)
    with pytest.raises(AccessDeniedError):
        await ctrl.stop_run(session, SUPERVISOR, run_id=task.task_id)


# --- AL-10 : stop cancels the sub-run, no Result ---------------------------


async def test_admin_stop_cancels_run(session) -> None:
    await _seed_principals(session)
    runtime = await _seed_runtime(session)
    task = await _activate_task(session, runtime)

    accepted = await ctrl.stop_run(session, ADMIN, run_id=task.task_id)
    assert accepted["control"] == "stop"
    assert accepted["run_id"] == task.task_id

    applied = await coord.apply_pending_control(session, agent_id=ALPHA_AGENT_ID)
    assert applied["applied"] == "stop"
    assert applied["cancelled_task_id"] == task.task_id
    cancelled = await al_repo.get_task(session, task.task_id)
    assert cancelled is not None and cancelled.status is AgentTaskStatus.CANCELLED
    runtime_after = await al_repo.get_runtime(session, ALPHA_AGENT_ID)
    assert runtime_after is not None and runtime_after.active_task_id is None


async def test_stop_without_active_run_rejected(session) -> None:
    await _seed_principals(session)
    await _seed_runtime(session)
    with pytest.raises(AgentRunNotStoppableError):
        await ctrl.stop_run(session, ADMIN, run_id="agttask_missing")


# --- AL-17 : concurrent control conflict -----------------------------------


async def test_concurrent_control_stale_version_conflict(session) -> None:
    await _seed_principals(session)
    runtime = await _seed_runtime(session)
    await _activate_task(session, runtime)

    first = await ctrl.pause_runtime(
        session, ADMIN, agent_id=ALPHA_AGENT_ID, expected_row_version=1
    )
    assert first["row_version"] == 2
    # A second control with the now-stale expected version is rejected.
    with pytest.raises(AgentRuntimeStateConflictError):
        await ctrl.pause_runtime(session, ADMIN, agent_id=ALPHA_AGENT_ID, expected_row_version=1)


# --- L1 FK insert-order proof ----------------------------------------------


async def test_fk_insert_order_task_checkpoint_hypothesis_link(session) -> None:
    await _seed_principals(session)
    runtime = await _seed_runtime(session)
    task = await _activate_task(session, runtime)

    checkpoint = await al_repo.create_checkpoint(
        session, task_id=task.task_id, checkpoint_no=1, stage="analysis"
    )
    artifact = await al_repo.create_hypothesis(
        session,
        status=HypothesisStatus.EXPLORING,
        title="Funding-skew reversal",
        mechanism="Extreme funding precedes mean reversion.",
        source_task_id=task.task_id,
        checkpoint_id=checkpoint.checkpoint_id,
        created_by_principal_id="admin_1",
    )
    link = await al_repo.create_artifact_link(
        session,
        source_artifact_id=artifact.artifact_id,
        target_type="backtest_result",
        target_id="res_1",
        relation_type="evidence",
    )
    assert task.task_id and checkpoint.checkpoint_id
    assert artifact.artifact_id and link.link_id
    links = await al_repo.list_artifact_links(session, artifact.artifact_id)
    assert [row.link_id for row in links] == [link.link_id]


# --- Board hides soft-deleted; keyset pagination ---------------------------


async def test_hypotheses_hides_soft_deleted(session) -> None:
    from entropia.domain.agent_lab.enums import HypothesisStatus

    await _seed_principals(session)
    await _seed_runtime(session)
    keep = await al_repo.create_hypothesis(
        session, status=HypothesisStatus.TESTING, title="keep", mechanism="m1"
    )
    gone = await al_repo.create_hypothesis(
        session, status=HypothesisStatus.EXPLORING, title="gone", mechanism="m2"
    )
    gone.deletion_state = DeletionState.SOFT_DELETED
    await session.flush()

    listed = await ws.list_hypotheses(session, ADMIN)
    ids = {h["artifact_id"] for h in listed["hypotheses"]}
    assert keep.artifact_id in ids
    assert gone.artifact_id not in ids


async def test_task_list_keyset_pagination(session) -> None:
    await _seed_principals(session)
    await _seed_runtime(session)
    for i in range(3):
        await al_repo.create_task(
            session,
            agent_id=ALPHA_AGENT_ID,
            task_type="research",
            title=f"t{i}",
            source="autonomous",
            priority=AgentTaskPriority.AUTONOMOUS,
            status=AgentTaskStatus.QUEUED,
        )

    page1 = await ws.list_tasks(session, ADMIN, limit=2)
    assert len(page1["tasks"]) == 2
    assert page1["next_cursor"] is not None
    page2 = await ws.list_tasks(session, ADMIN, limit=2, cursor=page1["next_cursor"])
    assert len(page2["tasks"]) == 1
    assert page2["next_cursor"] is None
    seen = {t["task_id"] for t in page1["tasks"]} | {t["task_id"] for t in page2["tasks"]}
    assert len(seen) == 3


# --- Review remediation regressions ----------------------------------------


def test_parse_if_match_rejects_malformed() -> None:
    """A malformed If-Match must be a 422, never a silent OCC opt-out."""
    from entropia.apps.api.routes.agent_lab import _parse_if_match
    from entropia.shared.errors import ValidationError

    assert _parse_if_match(None) is None
    assert _parse_if_match("   ") is None
    assert _parse_if_match('"5"') == 5
    with pytest.raises(ValidationError):
        _parse_if_match("abc")
    with pytest.raises(ValidationError):
        _parse_if_match("v5")


async def test_consume_defers_while_control_pending(session) -> None:
    """A queued directive is deferred (not burned) while a pause/stop is pending."""
    await _seed_principals(session)
    runtime = await _seed_runtime(session)
    await _activate_task(session, runtime)
    queued = await ctrl.create_directive(
        session, ADMIN, text="later", priority="high", target_agent_id=ALPHA_AGENT_ID
    )
    await ctrl.pause_runtime(session, ADMIN, agent_id=ALPHA_AGENT_ID)

    deferred = await coord.consume_next_directive(session, agent_id=ALPHA_AGENT_ID)
    assert deferred["consumed"] is None
    assert deferred["deferred_reason"] == "pause"
    directive = await al_repo.get_directive(session, queued["directive_id"])
    assert directive is not None and directive.status is DirectiveStatus.QUEUED
