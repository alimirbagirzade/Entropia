"""Stage 6c — Trash page contract (doc 20 §4, §5, §7, §9, §10, §15) against a real DB.

Covers: soft-delete page-contract entry + idempotent repeat; Admin-only list/
detail/restore/purge (User AND Agent -> TRASH_ACCESS_FORBIDDEN); keyset
pagination stability on deleted_at ties; object_type filter validation; restore
same-identity + OCC + audit/outbox; two-phase purge (confirmation + re-auth +
job) with worker completion, worker failure return path and duplicate-request
idempotency; RATIONALE_FAMILY_IN_USE delete preflight; Backtest Result trash
row + restore/purge via the Result-local deletion flag.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import auth as auth_cmd
from entropia.application.commands.backtest_run import soft_delete_backtest_result
from entropia.application.commands.deletion import (
    request_purge,
    restore_entity,
    restore_trash_entry,
    soft_delete_entity,
)
from entropia.application.commands.entities import create_entity
from entropia.application.commands.rationale import create_family, soft_delete_family
from entropia.application.jobs import purge as purge_job
from entropia.application.queries.trash import get_trash_entry_detail, list_trash_entries
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.domain.rationale.enums import AssignmentTargetKind, RationaleAssignmentState
from entropia.domain.trash.page import TrashEntryStatus
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    BacktestResult,
    EntityRegistry,
    HumanCredential,
    HumanUser,
    Job,
    Principal,
    TrashEntry,
)
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import (
    EntityNotSoftDeletedError,
    InvalidTrashObjectTypeError,
    ObjectAlreadyPurgedError,
    PurgeConfirmationInvalidError,
    PurgeInProgressError,
    PurgeNotEligibleError,
    RationaleFamilyInUseError,
    ReauthProofInvalidError,
    ReauthRequiredError,
    StaleRevisionError,
    TrashAccessForbiddenError,
)
from entropia.shared.passwords import PASSWORD_ALGORITHM, hash_password

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
AGENT = Actor(principal_id="agent_alpha", principal_type=PrincipalType.AGENT, role=None)

ADMIN_PASSWORD = "correct-horse-battery-admin"


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _mint_reauth_proof(session, *, purpose: str = "trash_purge") -> str:
    """F-21: the ADMIN test actor is a plain ``Actor`` dataclass, not a real
    signed-up account — ``reauth_proofs.user_id`` FKs to ``human_users``, so
    give it a real row once, then mint a REAL proof through the same
    ``reauthenticate`` command the HTTP route uses (no test-only shortcut)."""
    if await session.get(Principal, ADMIN.principal_id) is None:
        session.add(Principal(principal_id=ADMIN.principal_id, principal_type=PrincipalType.HUMAN))
        await session.flush()
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


async def _delete_one(session, *, entity_type: str = "demo_entity") -> str:
    root = await create_entity(session, USER, entity_type=entity_type, payload={"v": 1})
    await session.commit()
    await soft_delete_entity(session, USER, entity_id=root.entity_id, reason="cleanup")
    await session.commit()
    return root.entity_id


async def _entry_for(session, entity_id: str) -> TrashEntry:
    entry = await trash_repo.get_recoverable_entry_for_entity(session, entity_id)
    assert entry is not None
    return entry


# --------------------------------------------------------------------------- #
# Soft delete -> page-contract entry                                           #
# --------------------------------------------------------------------------- #


async def test_soft_delete_writes_page_contract_entry(session) -> None:
    entity_id = await _delete_one(session)
    entry = await _entry_for(session, entity_id)

    assert entry.status == TrashEntryStatus.SOFT_DELETED
    assert entry.row_version == 1
    assert entry.owner_at_deletion == USER.principal_id
    assert entry.deleted_by == USER.principal_id
    assert entry.reason == "cleanup"
    assert (entry.deletion_snapshot or {}).get("current_revision_id") is not None
    assert entry.purge_job_id is None


async def test_repeat_soft_delete_is_idempotent_no_duplicate_entry(session) -> None:
    entity_id = await _delete_one(session)
    entries_before = await _count(session, TrashEntry)
    audit_before = await _count(session, AuditEvent)

    root = await soft_delete_entity(session, USER, entity_id=entity_id)
    await session.commit()

    assert root.deletion_state == DeletionState.SOFT_DELETED
    assert await _count(session, TrashEntry) == entries_before  # no duplicate
    assert await _count(session, AuditEvent) == audit_before  # no audit noise


# --------------------------------------------------------------------------- #
# Admin-only access (doc 20 §2, §15)                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("actor", [USER, AGENT], ids=["user", "agent"])
async def test_trash_surfaces_reject_non_admin(session, actor: Actor) -> None:
    entity_id = await _delete_one(session)
    entry = await _entry_for(session, entity_id)

    with pytest.raises(TrashAccessForbiddenError):
        await list_trash_entries(session, actor)
    with pytest.raises(TrashAccessForbiddenError):
        await get_trash_entry_detail(session, actor, trash_entry_id=entry.id)
    with pytest.raises(TrashAccessForbiddenError):
        await restore_trash_entry(session, actor, trash_entry_id=entry.id)
    with pytest.raises(TrashAccessForbiddenError):
        await request_purge(
            session,
            actor,
            trash_entry_id=entry.id,
            confirmation_phrase=entity_id,
            reauth_proof="irrelevant",  # role check runs before any proof lookup
        )


# --------------------------------------------------------------------------- #
# List projection: filters, eligibility, keyset stability (doc 20 §4, §5, §13) #
# --------------------------------------------------------------------------- #


async def test_list_projection_fields_and_type_filter(session) -> None:
    await _delete_one(session, entity_type="package")
    await _delete_one(session, entity_type="demo_entity")

    page = await list_trash_entries(session, ADMIN)
    assert page["meta"]["recoverable_total"] == 2
    row = page["data"][0]
    assert row["restore_eligible"] is True
    assert row["status"] == "soft_deleted"
    assert row["purge_status"] is None
    assert row["row_version"] == 1

    only_packages = await list_trash_entries(session, ADMIN, object_type="package")
    assert [r["object_type"] for r in only_packages["data"]] == ["package"]
    assert only_packages["data"][0]["original_location"] == "Package Library"

    with pytest.raises(InvalidTrashObjectTypeError):
        await list_trash_entries(session, ADMIN, object_type="bogus_type")


async def test_list_search_pushdown(session) -> None:
    target = await _delete_one(session, entity_type="package")
    await _delete_one(session)

    hit = await list_trash_entries(session, ADMIN, q=target)
    assert [r["entity_id"] for r in hit["data"]] == [target]

    miss = await list_trash_entries(session, ADMIN, q="no-such-object")
    assert miss["data"] == []


async def test_keyset_pagination_stable_on_deleted_at_ties(session) -> None:
    ids = []
    for _ in range(5):
        root = await create_entity(session, USER, entity_type="demo_entity", payload={"v": 1})
        ids.append(root.entity_id)
    await session.commit()
    # One transaction -> identical server-side deleted_at for all five entries
    # (transaction timestamp), exercising the id tie-break.
    for entity_id in ids:
        await soft_delete_entity(session, USER, entity_id=entity_id)
    await session.commit()

    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        page = await list_trash_entries(session, ADMIN, cursor=cursor, limit=2)
        seen.extend(r["trash_entry_id"] for r in page["data"])
        pages += 1
        cursor = page["meta"]["cursor"]
        if not page["meta"]["has_more"]:
            break
    assert len(seen) == 5
    assert len(set(seen)) == 5  # no duplicates, no gaps across pages
    assert pages == 3


async def test_detail_returns_redacted_snapshot_and_current_state(session) -> None:
    entity_id = await _delete_one(session)
    entry = await _entry_for(session, entity_id)

    detail = await get_trash_entry_detail(session, ADMIN, trash_entry_id=entry.id)
    assert detail["deletion_snapshot"]["current_revision_id"] is not None
    assert detail["current_deletion_state"] == "soft_deleted"
    assert detail["tombstone"] is None


# --------------------------------------------------------------------------- #
# Restore (doc 20 §8.1, §8.2, §9.3)                                            #
# --------------------------------------------------------------------------- #


async def test_restore_keeps_identity_marks_entry_and_audits(session) -> None:
    root = await create_entity(session, USER, entity_type="demo_entity", payload={"v": 1})
    await session.commit()
    head = root.current_revision_id
    await soft_delete_entity(session, USER, entity_id=root.entity_id)
    await session.commit()
    entry = await _entry_for(session, root.entity_id)

    result = await restore_trash_entry(
        session, ADMIN, trash_entry_id=entry.id, expected_head_revision_id=1
    )
    await session.commit()

    assert result["deletion_state"] == "active"
    assert root.deletion_state == DeletionState.ACTIVE
    assert root.current_revision_id == head  # same identity + head pointer
    assert root.owner_principal_id == USER.principal_id  # no owner transfer
    assert entry.status == TrashEntryStatus.RESTORED
    assert entry.restored_by == ADMIN.principal_id

    kinds = [
        k
        for (k,) in (
            await session.execute(
                select(AuditEvent.event_kind).where(AuditEvent.target_entity_id == root.entity_id)
            )
        ).all()
    ]
    assert "trash.restored" in kinds

    # A restored entry leaves the default recoverable listing.
    page = await list_trash_entries(session, ADMIN)
    assert entry.id not in [r["trash_entry_id"] for r in page["data"]]

    # A second fresh restore attempt is a lifecycle conflict, not a repeat.
    with pytest.raises(EntityNotSoftDeletedError):
        await restore_trash_entry(session, ADMIN, trash_entry_id=entry.id)


async def test_restore_stale_version_conflict(session) -> None:
    entity_id = await _delete_one(session)
    entry = await _entry_for(session, entity_id)

    with pytest.raises(StaleRevisionError):
        await restore_trash_entry(
            session, ADMIN, trash_entry_id=entry.id, expected_head_revision_id=99
        )
    await session.rollback()
    assert (await _entry_for(session, entity_id)).status == TrashEntryStatus.SOFT_DELETED


async def test_restore_entity_compat_surface(session) -> None:
    entity_id = await _delete_one(session)
    root = await restore_entity(session, ADMIN, entity_id=entity_id)
    await session.commit()
    assert root.deletion_state == DeletionState.ACTIVE


# --------------------------------------------------------------------------- #
# Purge: request + worker (doc 20 §8.3, §9.2, §9.3)                            #
# --------------------------------------------------------------------------- #


async def test_purge_request_validations(session) -> None:
    entity_id = await _delete_one(session)
    entry = await _entry_for(session, entity_id)

    with pytest.raises(ReauthRequiredError):
        await request_purge(
            session,
            ADMIN,
            trash_entry_id=entry.id,
            confirmation_phrase=entity_id,
            reauth_proof="  ",
        )
    # F-21: an arbitrary non-empty string is NOT a valid proof — the core
    # acceptance criterion this slice fixes (it used to be accepted).
    with pytest.raises(ReauthProofInvalidError):
        await request_purge(
            session,
            ADMIN,
            trash_entry_id=entry.id,
            confirmation_phrase=entity_id,
            reauth_proof="just some arbitrary text, not a real proof",
        )
    with pytest.raises(PurgeConfirmationInvalidError):
        await request_purge(
            session,
            ADMIN,
            trash_entry_id=entry.id,
            confirmation_phrase="wrong-name",
            reauth_proof=await _mint_reauth_proof(session),
        )
    await session.rollback()
    assert (await _entry_for(session, entity_id)).status == TrashEntryStatus.SOFT_DELETED


async def test_purge_two_phase_flow_completes_with_tombstone(session) -> None:
    entity_id = await _delete_one(session)
    entry = await _entry_for(session, entity_id)
    # Plain-str copy: ORM attribute access after a rollback would lazy-load.
    trash_id = entry.id

    accepted = await request_purge(
        session,
        ADMIN,
        trash_entry_id=trash_id,
        confirmation_phrase=entity_id,
        reauth_proof=await _mint_reauth_proof(session),
        expected_head_revision_id=1,
    )
    await session.commit()

    assert accepted["purge_status"] == "pending"
    job_id = accepted["purge_job_id"]
    assert entry.status == TrashEntryStatus.PURGE_PENDING
    job = await session.get(Job, job_id)
    assert job is not None and job.queue == "maintenance"

    # Restore is disabled while the purge job is pending (doc 20 §4).
    with pytest.raises(PurgeInProgressError):
        await restore_trash_entry(session, ADMIN, trash_entry_id=trash_id)
    await session.rollback()

    # A duplicate request WITHOUT the original idempotency key is a conflict.
    with pytest.raises(PurgeInProgressError):
        await request_purge(
            session,
            ADMIN,
            trash_entry_id=trash_id,
            confirmation_phrase=entity_id,
            reauth_proof=await _mint_reauth_proof(session),
        )
    await session.rollback()

    outcome = await purge_job.run_purge(session, job_id)
    await session.commit()

    assert outcome["purge_status"] == "completed"
    assert entry.status == TrashEntryStatus.PURGED
    root = await session.get(EntityRegistry, entity_id)
    assert root is not None and root.deletion_state == DeletionState.PURGED
    tombstone = await trash_repo.get_tombstone(session, entity_id)
    assert tombstone is not None and tombstone.purged_by == ADMIN.principal_id

    # Purged entries leave the default list; restore is permanently closed.
    page = await list_trash_entries(session, ADMIN)
    assert trash_id not in [r["trash_entry_id"] for r in page["data"]]
    with pytest.raises(ObjectAlreadyPurgedError):
        await restore_trash_entry(session, ADMIN, trash_entry_id=trash_id)
    await session.rollback()

    # Redelivered job message is a no-op (at-least-once guard).
    replay = await purge_job.run_purge(session, job_id)
    assert replay.get("skipped") is True


async def test_purge_request_idempotency_key_replays_same_job(session) -> None:
    entity_id = await _delete_one(session)
    entry = await _entry_for(session, entity_id)

    first = await request_purge(
        session,
        ADMIN,
        trash_entry_id=entry.id,
        confirmation_phrase=entity_id,
        reauth_proof=await _mint_reauth_proof(session),
        idempotency_key="purge-key-1",
    )
    await session.commit()
    jobs_before = await _count(session, Job)

    # The idempotency-key REPLAY never re-checks the proof (run_idempotent
    # short-circuits before `_op` runs) — an arbitrary string here proves the
    # replay path genuinely never re-consumes or re-verifies a proof.
    replay = await request_purge(
        session,
        ADMIN,
        trash_entry_id=entry.id,
        confirmation_phrase=entity_id,
        reauth_proof="not-a-real-proof-and-that-is-fine-on-replay",
        idempotency_key="purge-key-1",
    )
    await session.commit()

    assert replay["purge_job_id"] == first["purge_job_id"]
    assert await _count(session, Job) == jobs_before  # no second job


async def test_purge_worker_failure_returns_root_to_soft_deleted(session, monkeypatch) -> None:
    entity_id = await _delete_one(session)
    entry = await _entry_for(session, entity_id)
    accepted = await request_purge(
        session,
        ADMIN,
        trash_entry_id=entry.id,
        confirmation_phrase=entity_id,
        reauth_proof=await _mint_reauth_proof(session),
    )
    await session.commit()

    async def _blocked(session_, entry_):
        raise PurgeNotEligibleError("Retention policy blocks this cleanup.")

    monkeypatch.setattr(purge_job, "_purge_preflight", _blocked)
    outcome = await purge_job.run_purge(session, accepted["purge_job_id"])
    await session.commit()

    assert outcome["purge_status"] == "failed"
    assert entry.status == TrashEntryStatus.PURGE_FAILED
    assert entry.purge_error == "PURGE_NOT_ELIGIBLE"

    # The root is recoverable again (doc 20 §9.2 worker-failure path): a fresh
    # confirmed+re-authed request or a restore both work.
    result = await restore_trash_entry(session, ADMIN, trash_entry_id=entry.id)
    await session.commit()
    assert result["deletion_state"] == "active"


# --------------------------------------------------------------------------- #
# Type-specific rules (doc 20 §10)                                             #
# --------------------------------------------------------------------------- #


async def test_family_with_active_assignment_blocks_delete(session) -> None:
    # rationale_family_revision.created_by / assignment.updated_by FK principals.
    for pid in (USER.principal_id, ADMIN.principal_id):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()
    created = await create_family(session, USER, display_name="Momentum Rationale")
    await session.commit()
    family_id = created["entity_id"]
    await rationale_repo.upsert_assignment(
        session,
        target_kind=AssignmentTargetKind.PACKAGE_REVISION,
        target_root_id="pkg_x",
        target_revision_id="rev_x",
        rationale_family_id=family_id,
        rationale_family_revision_id=created["revision_id"],
        rationale_display_snapshot=None,
        assignment_state=RationaleAssignmentState.ASSIGNED,
        updated_by_principal_id=USER.principal_id,
    )
    await session.commit()
    entries_before = await _count(session, TrashEntry)

    with pytest.raises(RationaleFamilyInUseError):
        await soft_delete_family(session, USER, entity_id=family_id)
    await session.rollback()
    with pytest.raises(RationaleFamilyInUseError):
        await soft_delete_entity(session, ADMIN, entity_id=family_id)
    await session.rollback()

    # No dangling state: root stays active, no Trash Entry was written.
    assert await _count(session, TrashEntry) == entries_before
    page = await list_trash_entries(session, ADMIN)
    assert family_id not in [r["entity_id"] for r in page["data"]]


async def test_backtest_result_trash_roundtrip(session) -> None:
    result = BacktestResult(
        result_id="res_trash_1",
        run_id="run_trash_1",
        manifest_id="man_trash_1",
        manifest_hash="h" * 64,
        workspace_entity_id="ws_1",
        composition_fingerprint="f" * 64,
        engine_version="engine-1",
        created_by_principal_id=USER.principal_id,
    )
    session.add(result)
    await session.commit()

    await soft_delete_backtest_result(session, USER, result_id="res_trash_1")
    await session.commit()
    entry = await _entry_for(session, "res_trash_1")
    assert entry.entity_type == "backtest_result"
    assert entry.original_location == "Mainboard / Backtest Results"
    assert (entry.dependency_snapshot or {}).get("run_id") == "run_trash_1"

    restored = await restore_trash_entry(session, ADMIN, trash_entry_id=entry.id)
    await session.commit()
    assert restored["deletion_state"] == "active"
    assert result.deletion_state == "active"

    # Delete again and run the full purge: the Result row keeps its identity as
    # a purged tombstoned record; the Run manifest reference is untouched.
    await soft_delete_backtest_result(session, USER, result_id="res_trash_1")
    await session.commit()
    entry2 = await _entry_for(session, "res_trash_1")
    accepted = await request_purge(
        session,
        ADMIN,
        trash_entry_id=entry2.id,
        confirmation_phrase="res_trash_1",
        reauth_proof=await _mint_reauth_proof(session),
    )
    await session.commit()
    await purge_job.run_purge(session, accepted["purge_job_id"])
    await session.commit()

    assert result.deletion_state == "purged"
    assert entry2.status == TrashEntryStatus.PURGED
    assert await trash_repo.get_tombstone(session, "res_trash_1") is not None
