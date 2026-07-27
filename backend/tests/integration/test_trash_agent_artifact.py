"""K-06 — Analysis Lab output (Agent artifact) Trash lifecycle (doc 20 §10, §11).

Before this slice ``hypothesis_artifact`` was a registered Trash object type
whose soft delete never wrote a Trash Entry: the artifact left the Analysis Lab
board and became unreachable — the Admin type filter returned nothing and
Restore/Purge had no entry to act on.

Covers, against a real database: the Agent's own ``artifact.soft_delete`` tool
writing the canonical entry; the entry's page-contract projection + type filter;
Admin restore returning the SAME artifact_id to the board; the two-phase purge
ending in ``purged`` + tombstone; and the type-specific dependency preflight —
a LIVE source task blocks the purge (doc 20 §10 "Running task/checkpoint is not
deleted via generic Trash route") and returns the artifact to ``soft_deleted``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import auth as auth_cmd
from entropia.application.commands.agent_artifact import soft_delete_hypothesis_artifact
from entropia.application.commands.deletion import request_purge, restore_trash_entry
from entropia.application.jobs import agent_tools
from entropia.application.jobs import purge as purge_job
from entropia.application.queries.trash import get_trash_entry_detail, list_trash_entries
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    HypothesisStatus,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.domain.trash.page import TrashEntryStatus
from entropia.infrastructure.postgres.models import (
    AgentRuntime,
    HumanCredential,
    HumanUser,
    Principal,
    TrashEntry,
)
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import ArtifactOwnershipError, TrashAccessForbiddenError
from entropia.shared.passwords import PASSWORD_ALGORITHM, hash_password

pytestmark = pytest.mark.integration

ARTIFACT_TYPE = "hypothesis_artifact"
ADMIN_PASSWORD = "correct-horse-battery-admin"

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OTHER = Actor(principal_id="user_other", principal_type=PrincipalType.HUMAN, role=Role.USER)
AGENT = Actor(
    principal_id="agent_alpha",
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_k06",
)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _mint_reauth_proof(session, *, purpose: str = "trash_purge") -> str:
    """F-21: mirrors ``test_trash_page._mint_reauth_proof`` — the ADMIN test actor
    needs a real ``human_users`` row for the ``reauth_proofs`` FK."""
    if await session.get(HumanUser, ADMIN.principal_id) is None:
        session.add(
            HumanUser(
                user_id=ADMIN.principal_id,
                username="admin_test",
                display_name="Admin",
                current_role=Role.ADMIN,
                status="active",
                version=1,
            )
        )
        await session.flush()
    if await session.get(HumanCredential, ADMIN.principal_id) is None:
        session.add(
            HumanCredential(
                user_id=ADMIN.principal_id,
                password_hash=hash_password(ADMIN_PASSWORD),
                algorithm=PASSWORD_ALGORITHM,
            )
        )
        await session.flush()
    result = await auth_cmd.reauthenticate(
        session,
        user_id=ADMIN.principal_id,
        password=ADMIN_PASSWORD,
        purpose=purpose,
        ttl_minutes=5,
    )
    return str(result["reauth_proof"])


async def _seed(session) -> None:
    session.add(Principal(principal_id=AGENT.principal_id, principal_type=PrincipalType.AGENT))
    session.add(Principal(principal_id=ADMIN.principal_id, principal_type=PrincipalType.HUMAN))
    session.add(Principal(principal_id=OTHER.principal_id, principal_type=PrincipalType.HUMAN))
    session.add(
        AgentRuntime(
            agent_id=ALPHA_AGENT_ID,
            mode=RuntimeMode.CONTINUOUS,
            status=RuntimeStatus.ACTIVE,
            row_version=1,
        )
    )
    await session.flush()


async def _seed_task(session, *, status: AgentTaskStatus):
    return await al_repo.create_task(
        session,
        agent_id=ALPHA_AGENT_ID,
        task_type="research",
        title="Momentum decay study",
        source="autonomous",
        priority=AgentTaskPriority.AUTONOMOUS,
        status=status,
    )


async def _entry_for(session, entity_id: str) -> TrashEntry:
    entry = await trash_repo.get_recoverable_entry_for_entity(session, entity_id)
    assert entry is not None
    return entry


# --------------------------------------------------------------------------- #
# Agent tool path -> canonical Trash Entry (doc 20 §11)                        #
# --------------------------------------------------------------------------- #


async def test_agent_tool_soft_delete_writes_trash_entry(session) -> None:
    await _seed(session)
    task = await _seed_task(session, status=AgentTaskStatus.RUNNING)
    created = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.create",
        policy_scope="research",
        request={"title": "Vol clustering holds out-of-sample", "mechanism": "m"},
        task_id=task.task_id,
        checkpoint_id="chk_k06_1",
    )
    artifact_id = created["artifact_id"]

    deleted = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.soft_delete",
        policy_scope="research",
        request={"artifact_id": artifact_id},
    )
    await session.commit()

    assert deleted["deletion_state"] == DeletionState.SOFT_DELETED.value
    # The artifact left the active board AND is now visible to the Admin.
    board = await al_repo.page_hypotheses(session, limit=10)
    assert artifact_id not in [h.artifact_id for h in board]
    entry = await _entry_for(session, artifact_id)
    assert entry.entity_type == ARTIFACT_TYPE
    assert entry.status == TrashEntryStatus.SOFT_DELETED
    assert entry.original_location == "Analysis Lab / Outputs"
    assert entry.display_name == "Vol clustering holds out-of-sample"
    assert entry.owner_at_deletion == AGENT.principal_id
    # Provenance is snapshot evidence, never a cascade delete (doc 20 §10).
    assert (entry.dependency_snapshot or {}).get("source_task_id") == task.task_id
    assert (entry.dependency_snapshot or {}).get("checkpoint_id") == "chk_k06_1"
    assert await al_repo.get_task(session, task.task_id) is not None


async def test_repeat_agent_soft_delete_writes_no_second_entry(session) -> None:
    await _seed(session)
    artifact = await al_repo.create_hypothesis(
        session,
        status=HypothesisStatus.EXPLORING,
        title="Repeat delete",
        mechanism="m",
        created_by_principal_id=AGENT.principal_id,
    )
    await soft_delete_hypothesis_artifact(session, AGENT, artifact_id=artifact.artifact_id)
    await session.commit()
    entries_after_first = await _count(session, TrashEntry)

    repeat = await soft_delete_hypothesis_artifact(session, AGENT, artifact_id=artifact.artifact_id)
    await session.commit()

    assert repeat["deletion_state"] == DeletionState.SOFT_DELETED.value
    assert await _count(session, TrashEntry) == entries_after_first


async def test_foreign_artifact_soft_delete_denied_and_untrashed(session) -> None:
    await _seed(session)
    foreign = await al_repo.create_hypothesis(
        session,
        status=HypothesisStatus.EXPLORING,
        title="Not the agent's",
        mechanism="m",
        created_by_principal_id=OTHER.principal_id,
    )
    await session.commit()
    entries_before = await _count(session, TrashEntry)

    with pytest.raises(ArtifactOwnershipError):
        await soft_delete_hypothesis_artifact(session, AGENT, artifact_id=foreign.artifact_id)
    await session.rollback()

    assert await _count(session, TrashEntry) == entries_before
    await session.refresh(foreign)
    assert foreign.deletion_state is DeletionState.ACTIVE


# --------------------------------------------------------------------------- #
# Admin surface: list filter, restore, purge (doc 20 §4, §7, §10)              #
# --------------------------------------------------------------------------- #


async def test_artifact_trash_roundtrip_restore_then_purge(session) -> None:
    await _seed(session)
    task = await _seed_task(session, status=AgentTaskStatus.SUCCEEDED)
    artifact = await al_repo.create_hypothesis(
        session,
        status=HypothesisStatus.CANDIDATE,
        title="Carry premium in EM rates",
        mechanism="m",
        source_task_id=task.task_id,
        created_by_principal_id=AGENT.principal_id,
    )
    artifact_id = artifact.artifact_id
    await soft_delete_hypothesis_artifact(session, AGENT, artifact_id=artifact_id, reason="noisy")
    await session.commit()

    # The Admin can actually FIND it under its own object type (doc 20 §4).
    page = await list_trash_entries(session, ADMIN, object_type=ARTIFACT_TYPE)
    row = next(r for r in page["data"] if r["entity_id"] == artifact_id)
    assert row["object_type"] == ARTIFACT_TYPE
    assert row["original_location"] == "Analysis Lab / Outputs"
    assert row["restore_eligible"] is True
    entry = await _entry_for(session, artifact_id)
    detail = await get_trash_entry_detail(session, ADMIN, trash_entry_id=entry.id)
    assert detail["current_deletion_state"] == str(DeletionState.SOFT_DELETED)
    assert detail["deletion_snapshot"]["artifact_status"] == str(HypothesisStatus.CANDIDATE)

    # Restore: SAME artifact_id back on the Analysis Lab board.
    restored = await restore_trash_entry(session, ADMIN, trash_entry_id=entry.id)
    await session.commit()
    assert restored["entity_id"] == artifact_id
    assert restored["deletion_state"] == str(DeletionState.ACTIVE)
    assert entry.status == TrashEntryStatus.RESTORED
    await session.refresh(artifact)
    assert artifact.deletion_state is DeletionState.ACTIVE
    board = await al_repo.page_hypotheses(session, limit=10)
    assert artifact_id in [h.artifact_id for h in board]

    # Delete again and run the full two-phase purge -> tombstone.
    await soft_delete_hypothesis_artifact(session, AGENT, artifact_id=artifact_id)
    await session.commit()
    entry2 = await _entry_for(session, artifact_id)
    accepted = await request_purge(
        session,
        ADMIN,
        trash_entry_id=entry2.id,
        confirmation_phrase="Carry premium in EM rates",
        reauth_proof=await _mint_reauth_proof(session),
    )
    await session.commit()
    await session.refresh(artifact)
    assert artifact.deletion_state is DeletionState.PURGE_PENDING

    outcome = await purge_job.run_purge(session, accepted["purge_job_id"])
    await session.commit()

    assert outcome["purge_status"] == "completed"
    assert entry2.status == TrashEntryStatus.PURGED
    await session.refresh(artifact)
    assert artifact.deletion_state is DeletionState.PURGED
    tombstone = await trash_repo.get_tombstone(session, artifact_id)
    assert tombstone is not None and tombstone.entity_type == ARTIFACT_TYPE
    # Provenance survives the purge: the source task row is untouched.
    assert await al_repo.get_task(session, task.task_id) is not None


async def test_live_source_task_blocks_artifact_purge(session) -> None:
    """doc 20 §10: a running task/checkpoint is never removed through Trash — the
    purge is a RECORDED failure and the output stays recoverable."""
    await _seed(session)
    task = await _seed_task(session, status=AgentTaskStatus.RUNNING)
    artifact = await al_repo.create_hypothesis(
        session,
        status=HypothesisStatus.EXPLORING,
        title="Live loop output",
        mechanism="m",
        source_task_id=task.task_id,
        created_by_principal_id=AGENT.principal_id,
    )
    artifact_id = artifact.artifact_id
    await soft_delete_hypothesis_artifact(session, AGENT, artifact_id=artifact_id)
    await session.commit()
    entry = await _entry_for(session, artifact_id)

    accepted = await request_purge(
        session,
        ADMIN,
        trash_entry_id=entry.id,
        confirmation_phrase="Live loop output",
        reauth_proof=await _mint_reauth_proof(session),
    )
    await session.commit()
    outcome = await purge_job.run_purge(session, accepted["purge_job_id"])
    await session.commit()

    assert outcome["purge_status"] == "failed"
    assert outcome["purge_error"] == "PURGE_NOT_ELIGIBLE"
    assert entry.status == TrashEntryStatus.PURGE_FAILED
    await session.refresh(artifact)
    assert artifact.deletion_state is DeletionState.SOFT_DELETED
    assert await trash_repo.get_tombstone(session, artifact_id) is None

    # Once the task reaches a terminal state the purge is eligible again.
    task.status = AgentTaskStatus.SUCCEEDED
    await session.commit()
    retry = await request_purge(
        session,
        ADMIN,
        trash_entry_id=entry.id,
        confirmation_phrase="Live loop output",
        reauth_proof=await _mint_reauth_proof(session),
    )
    await session.commit()
    retry_outcome = await purge_job.run_purge(session, retry["purge_job_id"])
    assert retry_outcome["purge_status"] == "completed"
    await session.commit()
    await session.refresh(artifact)
    assert artifact.deletion_state is DeletionState.PURGED


async def test_agent_has_no_trash_capability_for_its_own_output(session) -> None:
    """doc 20 §11: the Agent soft-deletes, but list/restore/purge stay Admin-only."""
    await _seed(session)
    artifact = await al_repo.create_hypothesis(
        session,
        status=HypothesisStatus.EXPLORING,
        title="Agent cannot restore this",
        mechanism="m",
        created_by_principal_id=AGENT.principal_id,
    )
    await soft_delete_hypothesis_artifact(session, AGENT, artifact_id=artifact.artifact_id)
    await session.commit()
    entry = await _entry_for(session, artifact.artifact_id)

    with pytest.raises(TrashAccessForbiddenError):
        await list_trash_entries(session, AGENT, object_type=ARTIFACT_TYPE)
    with pytest.raises(TrashAccessForbiddenError):
        await restore_trash_entry(session, AGENT, trash_entry_id=entry.id)
    await session.rollback()
