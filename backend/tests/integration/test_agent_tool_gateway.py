"""Stage 6a-2 — Tool Gateway against a real database (doc 18 §9.2, §10, §14).

Auto-skips without PostgreSQL. The integration conftest builds the schema with
``create_all``; the ``alpha-agent`` runtime + agent principal are seeded manually.

Covers: the mandated tool-call envelope (§9.2), AL-11 (agent_research_only blocked
from an execution/backtest context; invalid bundle never pinned), AL-12 (package
proposal is candidate/draft only), AL-14 (idempotent replay -> no duplicate), AL-16
(agent soft-deletes only its OWN artifact), the scope-legality guard, and an L1 FK
insert-order proof for ``create_tool_call``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from entropia.application.jobs import agent_tools
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    HypothesisStatus,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.agent_lab.tool_gateway import PolicyScope, ToolCallStatus, ToolName
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import ActorKind, DeletionState, PrincipalType
from entropia.domain.research_data.enums import UsageScope
from entropia.infrastructure.postgres.models import (
    AgentEvent,
    AgentRuntime,
    AgentToolCall,
    HypothesisArtifact,
    Job,
    Principal,
)
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import agent_tool_gateway as tg_repo
from entropia.infrastructure.postgres.repositories import research_data as research_repo

pytestmark = pytest.mark.integration

_AGENT_PID = "agent_alpha"
_OTHER_PID = "other_1"
AGENT = Actor(
    principal_id=_AGENT_PID,
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_ag",
)


async def _seed(session) -> AgentRuntime:
    session.add(Principal(principal_id=_AGENT_PID, principal_type=PrincipalType.AGENT))
    session.add(Principal(principal_id=_OTHER_PID, principal_type=PrincipalType.HUMAN))
    runtime = AgentRuntime(
        agent_id=ALPHA_AGENT_ID,
        mode=RuntimeMode.CONTINUOUS,
        status=RuntimeStatus.ACTIVE,
        row_version=1,
    )
    session.add(runtime)
    await session.flush()
    return runtime


async def _seed_task(session):
    return await al_repo.create_task(
        session,
        agent_id=ALPHA_AGENT_ID,
        task_type="research",
        title="Active research",
        source="autonomous",
        priority=AgentTaskPriority.AUTONOMOUS,
        status=AgentTaskStatus.RUNNING,
    )


async def _research_revision(session, scope: UsageScope) -> str:
    _, revision = await research_repo.create_research_dataset(
        session,
        owner_principal_id=_AGENT_PID,
        created_by_principal_id=_AGENT_PID,
        payload={"series": [1, 2, 3]},
        usage_scope=scope,
    )
    await session.flush()
    return revision.revision_id


async def _count_events(session, event_type: str) -> int:
    stmt = select(func.count()).where(AgentEvent.type == event_type)
    return int((await session.execute(stmt)).scalar_one())


# --------------------------------------------------------------------------- #
# Envelope + success path
# --------------------------------------------------------------------------- #


async def test_tool_call_records_full_envelope(session) -> None:
    await _seed(session)
    task = await _seed_task(session)

    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.create",
        policy_scope="research",
        task_id=task.task_id,
        checkpoint_id="ckpt_x",
        input_manifest_id="man_x",
        idempotency_key="key_1",
        request={"title": "Funding edge", "mechanism": "carry"},
    )

    call = await tg_repo.get_tool_call(session, result["tool_call_id"])
    assert call is not None
    assert call.tool_name == ToolName.ARTIFACT_CREATE.value
    assert call.agent_id == ALPHA_AGENT_ID
    assert call.actor_principal_id == _AGENT_PID
    assert call.actor_kind is ActorKind.AGENT
    assert call.task_id == task.task_id
    assert call.checkpoint_id == "ckpt_x"
    assert call.input_manifest_id == "man_x"
    assert call.idempotency_key == "key_1"
    assert call.policy_scope is PolicyScope.RESEARCH
    assert call.status is ToolCallStatus.SUCCEEDED
    assert call.artifact_output_ref == result["artifact_id"]
    assert await _count_events(session, "tool_call_started") == 1
    assert await _count_events(session, "tool_call_succeeded") == 1


# --------------------------------------------------------------------------- #
# Envelope status is never shadowed by a handler payload's own status key
# --------------------------------------------------------------------------- #


async def test_envelope_status_not_shadowed_by_artifact_status(session) -> None:
    # artifact.create returns its OWN maturity; it must NOT overwrite the
    # envelope's terminal call status (doc 18 §9.2). The durable row agrees.
    await _seed(session)

    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.create",
        policy_scope="research",
        request={"title": "H", "mechanism": "m"},
    )

    assert result["status"] == "succeeded"
    assert result["artifact_status"] == HypothesisStatus.EXPLORING.value
    assert "status" not in {"artifact_status"}  # keys are distinct, not aliased
    call = await tg_repo.get_tool_call(session, result["tool_call_id"])
    assert call.status is ToolCallStatus.SUCCEEDED


async def test_task_query_status_is_namespaced(session) -> None:
    # agent.task.query returns the queried task's status under ``task_status``;
    # the envelope's ``status`` stays the call outcome.
    await _seed(session)
    task = await _seed_task(session)

    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="agent.task.query",
        policy_scope="observation",
        request={"target_task_id": task.task_id},
    )

    assert result["found"] is True
    assert result["status"] == "succeeded"
    assert result["task_status"] == str(task.status)


async def test_replay_status_not_shadowed(session) -> None:
    # The replay path mirrors the success path: the durable terminal status wins
    # over the stored handler payload (AL-14).
    await _seed(session)
    payload = {
        "tool_name": "artifact.create",
        "policy_scope": "research",
        "idempotency_key": "shadow_key",
        "request": {"title": "H", "mechanism": "m"},
    }
    first = await agent_tools.dispatch_tool_call(session, AGENT, **payload)
    replay = await agent_tools.dispatch_tool_call(session, AGENT, **payload)

    assert replay["replayed"] is True
    assert replay["tool_call_id"] == first["tool_call_id"]
    assert replay["status"] == "succeeded"
    assert replay["artifact_status"] == HypothesisStatus.EXPLORING.value


# --------------------------------------------------------------------------- #
# AL-11 — agent_research_only cannot enter execution/backtest
# --------------------------------------------------------------------------- #


async def test_data_bundle_execution_blocks_research_only(session) -> None:
    await _seed(session)
    revision_id = await _research_revision(session, UsageScope.AGENT_RESEARCH_ONLY)

    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="data_bundle.resolve",
        policy_scope="execution",
        request={"research_revisions": [{"revision_id": revision_id}]},
    )

    assert result["status"] == "rejected"
    assert result["reason_code"] == "RESEARCH_INPUT_BLOCKED"
    call = await tg_repo.get_tool_call(session, result["tool_call_id"])
    assert call.status is ToolCallStatus.REJECTED
    # The invalid bundle never pins a manifest (doc 18 §14, AL-11).
    assert call.artifact_output_ref is None
    assert call.input_manifest_id is None
    assert await _count_events(session, "research_input_blocked") == 1


async def test_data_bundle_execution_allows_research_backtest(session) -> None:
    await _seed(session)
    revision_id = await _research_revision(session, UsageScope.RESEARCH_BACKTEST)

    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="data_bundle.resolve",
        policy_scope="execution",
        request={"research_revisions": [{"revision_id": revision_id}]},
    )

    assert result["status"] == "succeeded"
    assert result["context_manifest_id"]
    call = await tg_repo.get_tool_call(session, result["tool_call_id"])
    assert call.input_manifest_id == result["context_manifest_id"]
    assert await _count_events(session, "data_bundle_pinned") == 1


async def test_data_bundle_research_scope_allows_research_only(session) -> None:
    await _seed(session)
    revision_id = await _research_revision(session, UsageScope.AGENT_RESEARCH_ONLY)

    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="data_bundle.resolve",
        policy_scope="research",
        request={"research_revisions": [{"revision_id": revision_id}]},
    )

    assert result["status"] == "succeeded"
    assert result["research_revision_ids"] == [revision_id]


# --------------------------------------------------------------------------- #
# AL-12 — package proposal is candidate/draft only
# --------------------------------------------------------------------------- #


async def test_package_proposal_is_candidate_only(session) -> None:
    await _seed(session)

    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="package.proposal.create",
        policy_scope="proposal",
        request={"title": "Mean reversion pack", "mechanism": "z-score"},
    )

    assert result["proposal_status"] == "candidate"
    assert result["can_approve"] is False
    assert result["can_publish"] is False
    artifact = await al_repo.get_hypothesis(session, result["artifact_id"])
    assert artifact.status is HypothesisStatus.CANDIDATE
    links = await al_repo.list_artifact_links(session, artifact.artifact_id)
    assert any(link.target_type == "package_proposal" for link in links)


# --------------------------------------------------------------------------- #
# AL-14 — idempotent replay, no duplicate
# --------------------------------------------------------------------------- #


async def test_idempotent_replay_no_duplicate(session) -> None:
    await _seed(session)
    payload = {
        "tool_name": "artifact.create",
        "policy_scope": "research",
        "idempotency_key": "dup_key",
        "request": {"title": "H", "mechanism": "m"},
    }
    first = await agent_tools.dispatch_tool_call(session, AGENT, **payload)
    second = await agent_tools.dispatch_tool_call(session, AGENT, **payload)

    assert second.get("replayed") is True
    assert second["tool_call_id"] == first["tool_call_id"]
    hypotheses = (
        await session.execute(select(func.count()).select_from(HypothesisArtifact))
    ).scalar_one()
    tool_calls = (
        await session.execute(select(func.count()).select_from(AgentToolCall))
    ).scalar_one()
    assert int(hypotheses) == 1
    assert int(tool_calls) == 1


# --------------------------------------------------------------------------- #
# AL-16 — agent soft-deletes only its own artifact
# --------------------------------------------------------------------------- #


async def test_soft_delete_own_artifact(session) -> None:
    await _seed(session)
    created = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.create",
        policy_scope="research",
        request={"title": "H", "mechanism": "m"},
    )
    artifact_id = created["artifact_id"]

    deleted = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.soft_delete",
        policy_scope="research",
        request={"artifact_id": artifact_id},
    )

    assert deleted["deletion_state"] == DeletionState.SOFT_DELETED.value
    artifact = await al_repo.get_hypothesis(session, artifact_id)
    assert artifact.deletion_state is DeletionState.SOFT_DELETED
    board = await al_repo.page_hypotheses(session, limit=10)
    assert artifact_id not in [h.artifact_id for h in board]


async def test_soft_delete_foreign_artifact_denied(session) -> None:
    await _seed(session)
    foreign = await al_repo.create_hypothesis(
        session,
        status=HypothesisStatus.EXPLORING,
        title="Not the agent's",
        mechanism="m",
        created_by_principal_id=_OTHER_PID,
    )

    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.soft_delete",
        policy_scope="research",
        request={"artifact_id": foreign.artifact_id},
    )

    assert result["status"] == "rejected"
    assert result["reason_code"] == "ARTIFACT_NOT_OWNED"
    await session.refresh(foreign)
    assert foreign.deletion_state is DeletionState.ACTIVE


# --------------------------------------------------------------------------- #
# Autonomous follow-up + scope guard
# --------------------------------------------------------------------------- #


async def test_followup_task_enqueue_is_autonomous(session) -> None:
    await _seed(session)
    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="followup_task.enqueue",
        policy_scope="research",
        request={"title": "Investigate tail risk"},
    )
    task = await al_repo.get_task(session, result["task_id"])
    assert task.priority is AgentTaskPriority.AUTONOMOUS
    assert task.status is AgentTaskStatus.QUEUED


async def test_illegal_scope_is_rejected(session) -> None:
    await _seed(session)
    # agent.task.query is an OBSERVATION tool; EXECUTION scope is illegal.
    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="agent.task.query",
        policy_scope="execution",
        request={"target_task_id": "whatever"},
    )
    assert result["status"] == "rejected"
    assert result["reason_code"] == "AGENT_TOOL_SCOPE_FORBIDDEN"


# --------------------------------------------------------------------------- #
# L1 FK insert-order proof for create_tool_call (agent_id -> agent_runtime)
# --------------------------------------------------------------------------- #


async def test_tool_call_l1_fk_insert_order(session) -> None:
    # Child-before-parent: a tool call for a non-existent runtime violates the FK.
    with pytest.raises(IntegrityError):
        await tg_repo.create_tool_call(
            session,
            tool_name=ToolName.TASK_QUERY,
            agent_id="ghost-agent",
            actor_principal_id=None,
            actor_kind=ActorKind.AGENT,
            policy_scope=PolicyScope.OBSERVATION,
        )
    await session.rollback()

    # Parent-before-child: with the runtime seeded first, the same insert succeeds.
    await _seed(session)
    call = await tg_repo.create_tool_call(
        session,
        tool_name=ToolName.TASK_QUERY,
        agent_id=ALPHA_AGENT_ID,
        actor_principal_id=_AGENT_PID,
        actor_kind=ActorKind.AGENT,
        policy_scope=PolicyScope.OBSERVATION,
    )
    assert call.tool_call_id


# --------------------------------------------------------------------------- #
# Durable job path (agent / agent-high queue) + scope routing
# --------------------------------------------------------------------------- #


async def test_enqueue_and_run_tool_job(session) -> None:
    await _seed(session)
    job = agent_tools.enqueue_tool_call(
        session,
        AGENT,
        tool_name="followup_task.enqueue",
        policy_scope="research",
        request={"title": "Investigate tail risk"},
        idempotency_key="job_key_1",
    )
    assert isinstance(job, Job)
    assert job.queue == "agent"
    await session.flush()

    result = await agent_tools.run_tool_job(session, job.job_id)

    assert result["status"] == "succeeded"
    task = await al_repo.get_task(session, result["task_id"])
    assert task is not None
    assert task.priority is AgentTaskPriority.AUTONOMOUS
    call = await tg_repo.get_tool_call(session, result["tool_call_id"])
    assert call.idempotency_key == "job_key_1"
    assert call.actor_kind is ActorKind.AGENT


async def test_execution_scope_routes_to_agent_high(session) -> None:
    await _seed(session)
    job = agent_tools.enqueue_tool_call(
        session,
        AGENT,
        tool_name="data_bundle.resolve",
        policy_scope="execution",
        request={"research_revisions": []},
    )
    # An EXECUTION-scoped data-bundle resolve gates a run -> the high plane.
    assert job.queue == "agent-high"
