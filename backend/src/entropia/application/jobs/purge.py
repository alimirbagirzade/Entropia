"""Trash purge worker body (Stage 6c, doc 20 §8.3, §9.3, §12).

Runs on the ``maintenance`` queue. The durable ``jobs`` row + the Trash Entry
are the source of truth — the Admin request that accepted the purge returned
202 long ago; browser close / logout never cancels it. Steps:

    load job + entry -> re-check eligibility (retention/dependency preflight,
    doc 20 §9.3 "purge worker") ->
    ELIGIBLE: target purged (root row kept as identity evidence; revisions and
        completed run manifests are retained per V1 retention) + tombstone +
        entry ``purged`` -> audit ``trash.purge_completed`` ->
    NOT ELIGIBLE: target returns to soft_deleted + entry ``purge_failed`` with a
        safe diagnostic code -> audit ``trash.purge_failed``.

A failed purge is a NORMAL recorded outcome (root stays recoverable), not a job
exception — the worker never retries it silently; a new confirmed+re-authed
Admin request is required (doc 20 §8.4). Only unexpected/missing-row conditions
raise. At-least-once redelivery of an already-terminal entry is a no-op.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.deletion import next_deletion_state
from entropia.domain.lifecycle.enums import ActorKind, DeletionState, JobStatus
from entropia.domain.trash.page import TrashEntryStatus
from entropia.infrastructure.postgres.models import Job, TrashEntry
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import entities as entity_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import PurgeNotEligibleError

_RESULT_ENTITY_TYPE = "backtest_result"
_MANUAL_ENTITY_TYPE = "manual_document"
_RESULT_PURGE_PENDING = "purge_pending"
_RESULT_PURGED = "purged"
_RESULT_SOFT_DELETED = "soft_deleted"


async def _purge_preflight(session: AsyncSession, entry: TrashEntry) -> None:
    """Re-check retention/dependency AT JOB START (doc 20 §9.3) — the request-time
    check never substitutes for this one."""
    if entry.entity_type == _RESULT_ENTITY_TYPE:
        return  # parent Run manifest is immutable and always retained (doc 20 §10)
    if entry.entity_type == _MANUAL_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import manual as manual_repo

        document = await manual_repo.get_document(session, entry.entity_id)
        # Built-in/system content purge policy blocks the baseline (doc 20 §10).
        if document is not None and document.is_baseline:
            raise PurgeNotEligibleError("The built-in baseline manual cannot be purged.")
        return
    if entry.entity_type == "work_object":
        from entropia.infrastructure.postgres.repositories import backtest as bt_repo

        if await bt_repo.has_active_run_for_root(session, entry.entity_id):
            raise PurgeNotEligibleError("An active run still pins this work object.")


async def _finalize_purge(session: AsyncSession, entry: TrashEntry) -> None:
    """Move the target to its terminal purged state + tombstone. The root row and
    immutable revisions are RETAINED as identity/audit evidence (V1 retention);
    ``purged`` roots can never re-enter active projections (state machine)."""
    if entry.entity_type == _RESULT_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import backtest as bt_repo

        result = await bt_repo.get_result(session, entry.entity_id)
        if result is None:
            raise ValueError(f"Backtest result '{entry.entity_id}' not found for purge.")
        result.deletion_state = _RESULT_PURGED
        result.row_version += 1
    elif entry.entity_type == _MANUAL_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import manual as manual_repo

        document = await manual_repo.get_document(session, entry.entity_id)
        if document is None:
            raise ValueError(f"Manual document '{entry.entity_id}' not found for purge.")
        document.deletion_state = DeletionState.PURGED
        document.row_version += 1
        # Content redaction: the search projection goes away; the root row,
        # immutable revisions and blocks are retained for citation/audit
        # resolution under V1 retention (doc 21 §11, UM-12).
        await manual_repo.delete_search_chunks_for_document(session, entry.entity_id)
    else:
        root = await entity_repo.get_root(session, entry.entity_id)
        if root is None:
            raise ValueError(f"Entity '{entry.entity_id}' not found for purge.")
        root.deletion_state = next_deletion_state(root.deletion_state, DeletionState.PURGED)
    trash_repo.add_tombstone(
        session,
        entity_id=entry.entity_id,
        entity_type=entry.entity_type,
        purged_by=entry.purge_requested_by,
    )


async def _return_target_soft_deleted(session: AsyncSession, entry: TrashEntry) -> None:
    """Worker-failure return path (doc 20 §9.2): purge_pending -> soft_deleted."""
    if entry.entity_type == _RESULT_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import backtest as bt_repo

        result = await bt_repo.get_result(session, entry.entity_id)
        if result is not None and result.deletion_state == _RESULT_PURGE_PENDING:
            result.deletion_state = _RESULT_SOFT_DELETED
            result.row_version += 1
        return
    if entry.entity_type == _MANUAL_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import manual as manual_repo

        document = await manual_repo.get_document(session, entry.entity_id)
        if document is not None and document.deletion_state == DeletionState.PURGE_PENDING:
            document.deletion_state = DeletionState.SOFT_DELETED
            document.row_version += 1
        return
    root = await entity_repo.get_root(session, entry.entity_id)
    if root is not None and root.deletion_state == DeletionState.PURGE_PENDING:
        root.deletion_state = next_deletion_state(
            DeletionState.PURGE_PENDING, DeletionState.SOFT_DELETED
        )


def _audit(session: AsyncSession, entry: TrashEntry, *, kind: str, reason: str | None) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=kind,
        actor_principal_id=entry.purge_requested_by,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=entry.entity_id,
        target_entity_type=entry.entity_type,
        previous_state=str(DeletionState.PURGE_PENDING),
        new_state=str(entry.status),
        reason=reason,
        correlation_id=entry.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type=kind,
        resource_type=entry.entity_type,
        resource_id=entry.entity_id,
        payload={"trash_entry_id": entry.id, "purge_job_id": entry.purge_job_id},
        correlation_id=entry.correlation_id,
    )


async def run_purge(session: AsyncSession, job_id: str) -> dict[str, Any]:
    """Execute the durable purge job. Does not commit (the worker scope commits)."""
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found.")
    entry_id = str((job.payload or {}).get("trash_entry_id"))
    entry = await trash_repo.get_entry(session, entry_id)
    if entry is None:
        raise ValueError(f"Trash entry '{entry_id}' not found for job '{job_id}'.")

    # At-least-once delivery guard: a redelivered message for an already-terminal
    # entry must not purge twice or overwrite a recorded failure.
    if entry.status != TrashEntryStatus.PURGE_PENDING:
        return {"trash_entry_id": entry.id, "purge_status": str(entry.status), "skipped": True}

    job.status = JobStatus.RUNNING
    try:
        await _purge_preflight(session, entry)
        await _finalize_purge(session, entry)
    except PurgeNotEligibleError as exc:
        await _return_target_soft_deleted(session, entry)
        entry.status = TrashEntryStatus.PURGE_FAILED
        entry.purge_error = exc.code
        entry.row_version += 1
        _audit(session, entry, kind="trash.purge_failed", reason=exc.message)
        job.status = JobStatus.SUCCEEDED  # the failed purge is a recorded outcome
        return {
            "trash_entry_id": entry.id,
            "purge_status": "failed",
            "purge_error": exc.code,
        }

    entry.status = TrashEntryStatus.PURGED
    entry.purge_error = None
    entry.row_version += 1
    _audit(session, entry, kind="trash.purge_completed", reason=None)
    job.status = JobStatus.SUCCEEDED
    return {"trash_entry_id": entry.id, "purge_status": "completed"}
