"""Soft-delete / restore / purge commands (M3 §7; Stage 6c doc 20 §9.3, §10).

Each command is ONE transaction: domain mutation + trash/tombstone + audit +
outbox, no commit here. Soft delete stays owner-or-Admin; Trash restore/purge
are Admin-only behind ``require_trash_admin`` (route AND service). Purge is
TWO-PHASE (doc 20 §8.3): the Admin request only moves the target to
``purge_pending`` and enqueues a durable ``maintenance`` job; the worker
(``application/jobs/purge.py``) re-checks eligibility and either tombstones the
root or returns it to ``soft_deleted``. Forbidden deletion-state jumps are
rejected by the state machine before any write.

Type dispatch (doc 20 §10): registry-backed roots mutate ``EntityRegistry``;
``backtest_result`` entries mutate the Result row's local ``deletion_state``
(a Result is not a registry root — CR-03). Historical revisions, run manifests
and audit evidence are never rewritten by restore or purge.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands.auth import consume_reauth_proof
from entropia.application.idempotency import run_idempotent
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_edit, require_trash_admin
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.trash.page import TrashEntryStatus, original_location_for
from entropia.infrastructure.postgres.models import EntityRegistry, TrashEntry
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import entities as entity_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.infrastructure.queues.enqueue import enqueue_job
from entropia.shared.concurrency import check_row_version
from entropia.shared.errors import (
    EntityNotSoftDeletedError,
    NotFoundError,
    ObjectAlreadyPurgedError,
    PurgeConfirmationInvalidError,
    PurgeInProgressError,
    RestoreConflictError,
    StaleRevisionError,
    TrashEntryNotFoundError,
)

_TRASH_PURGE_REAUTH_PURPOSE = "trash_purge"

PURGE_QUEUE = "maintenance"
RESULT_ENTITY_TYPE = "backtest_result"
MANUAL_ENTITY_TYPE = "manual_document"
_RESULT_ACTIVE = "active"
_RESULT_SOFT_DELETED = "soft_deleted"
_RESULT_PURGE_PENDING = "purge_pending"


async def _require_root(session: AsyncSession, entity_id: str) -> EntityRegistry:
    root = await entity_repo.get_root(session, entity_id)
    if root is None:
        raise NotFoundError(f"Entity '{entity_id}' not found.")
    return root


# --------------------------------------------------------------------------- #
# Type-specific delete preflight (doc 20 §10)                                  #
# --------------------------------------------------------------------------- #


async def _soft_delete_preflight(session: AsyncSession, root: EntityRegistry) -> None:
    """Blockers that must veto the delete BEFORE any Trash Entry exists.

    Lazy imports keep this module free of backtest/rationale imports at module
    load (mirrors ``mainboard._assert_not_in_active_run``).
    """
    if root.entity_type == "work_object":
        from entropia.infrastructure.postgres.repositories import backtest as bt_repo
        from entropia.shared.errors import ObjectInActiveRunError

        # Canonical running-job blocker (doc 01/15 OBJECT_IN_ACTIVE_RUN; doc 20
        # §12 names the same semantic DELETE_BLOCKED_BY_RUNNING_JOB).
        if await bt_repo.has_active_run_for_root(session, root.entity_id):
            raise ObjectInActiveRunError()
    elif root.entity_type == "rationale_family":
        from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
        from entropia.shared.errors import RationaleFamilyInUseError

        if await rationale_repo.count_active_family_assignments(session, root.entity_id) > 0:
            raise RationaleFamilyInUseError()


# --------------------------------------------------------------------------- #
# Soft delete                                                                  #
# --------------------------------------------------------------------------- #


async def soft_delete_entity(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    reason: str | None = None,
    display_name: str | None = None,
    original_location: str | None = None,
    deletion_snapshot: dict[str, Any] | None = None,
) -> EntityRegistry:
    """Owner-or-Admin soft delete of a registry root (doc 20 §9.3 entity.soft_delete).

    Row-locks the root, short-circuits an already-soft-deleted root as an
    idempotent no-op (same entry, no duplicate audit), runs the type-specific
    preflight, then writes root state + Trash Entry + audit + outbox atomically.
    """
    root = await _require_root(session, entity_id)
    ensure_can_edit(actor, owner_principal_id=root.owner_principal_id)
    await session.refresh(root, with_for_update=True)

    previous = root.deletion_state
    if previous == DeletionState.SOFT_DELETED:
        return root  # idempotent repeat: the existing entry stands (doc 20 §14)
    if previous == DeletionState.PURGE_PENDING:
        raise PurgeInProgressError()
    if previous == DeletionState.PURGED:
        raise ObjectAlreadyPurgedError()

    await _soft_delete_preflight(session, root)

    from entropia.domain.deletion import next_deletion_state

    root.deletion_state = next_deletion_state(previous, DeletionState.SOFT_DELETED)
    root.deleted_by = actor.principal_id
    root.delete_reason = reason
    root.deleted_at = datetime.now(UTC)

    snapshot = dict(deletion_snapshot or {})
    snapshot.setdefault("current_revision_id", root.current_revision_id)
    snapshot.setdefault("domain_lifecycle_state", root.lifecycle_state)
    trash_repo.add_trash_entry(
        session,
        entity_id=root.entity_id,
        entity_type=root.entity_type,
        deleted_by=actor.principal_id,
        reason=reason,
        owner_at_deletion=root.owner_principal_id,
        dependency_snapshot={"current_revision_id": root.current_revision_id},
        display_name=display_name,
        original_location=original_location or original_location_for(root.entity_type),
        deletion_snapshot=snapshot,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_audit_event(
        session,
        event_kind="entity.soft_deleted",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=root.entity_id,
        target_entity_type=root.entity_type,
        previous_state=str(previous),
        new_state=str(root.deletion_state),
        reason=reason,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="entity.soft_deleted",
        resource_type=root.entity_type,
        resource_id=root.entity_id,
        payload={"reason": reason},
        correlation_id=actor.correlation_id,
    )
    return root


async def soft_delete_registry_root(
    session: AsyncSession,
    actor: Actor,
    root: EntityRegistry,
    *,
    reason: str | None,
    display_name: str | None,
    expected_row_version: int | None = None,
) -> tuple[str, str] | None:
    """Shared soft-delete core for a DOMAIN registry root (doc 20 §9.3/§10).

    Row-locks the root, enforces optional OCC, and — on a real ACTIVE ->
    SOFT_DELETED transition — flips the deletion pointers and writes the Trash
    Entry. Returns ``(previous_state, new_state)`` when a transition happened, or
    ``None`` when the root was already soft-deleted (idempotent no-op — the caller
    MUST NOT emit a duplicate audit; doc 20 §14).

    Unlike ``soft_delete_entity`` this emits NO audit/outbox: the caller keeps its
    own domain event family (``market.dataset.*`` / ``research.dataset.*``) so the
    delete lands in the Logs family filter alongside that resource's other events
    (doc 11 §10, doc 12 §11). Authorization is the caller's responsibility.
    """
    await session.refresh(root, with_for_update=True)
    check_row_version(root.row_version, expected_row_version)

    previous = root.deletion_state
    if previous == DeletionState.SOFT_DELETED:
        return None  # idempotent repeat: the existing entry stands (doc 20 §14)
    if previous == DeletionState.PURGE_PENDING:
        raise PurgeInProgressError()
    if previous == DeletionState.PURGED:
        raise ObjectAlreadyPurgedError()

    from entropia.domain.deletion import next_deletion_state

    root.deletion_state = next_deletion_state(previous, DeletionState.SOFT_DELETED)
    root.deleted_by = actor.principal_id
    root.delete_reason = reason
    root.deleted_at = datetime.now(UTC)

    trash_repo.add_trash_entry(
        session,
        entity_id=root.entity_id,
        entity_type=root.entity_type,
        deleted_by=actor.principal_id,
        reason=reason,
        owner_at_deletion=root.owner_principal_id,
        dependency_snapshot={"current_revision_id": root.current_revision_id},
        display_name=display_name,
        original_location=original_location_for(root.entity_type),
        deletion_snapshot={
            "current_revision_id": root.current_revision_id,
            "domain_lifecycle_state": root.lifecycle_state,
            "display_name": display_name,
        },
        correlation_id=actor.correlation_id,
    )
    return str(previous), str(root.deletion_state)


# --------------------------------------------------------------------------- #
# Restore (Admin-only, doc 20 §9.3 trash.restore)                              #
# --------------------------------------------------------------------------- #


def _display_identity(entry: TrashEntry) -> str:
    return entry.display_name or entry.entity_id


def _assert_entry_recoverable(entry: TrashEntry) -> None:
    if entry.status == TrashEntryStatus.PURGE_PENDING:
        raise PurgeInProgressError()
    if entry.status == TrashEntryStatus.PURGED:
        raise ObjectAlreadyPurgedError()
    if entry.status == TrashEntryStatus.RESTORED:
        raise EntityNotSoftDeletedError()


async def _restore_registry_target(
    session: AsyncSession, entry: TrashEntry
) -> tuple[str | None, str, str]:
    """Return (revision_id, previous_state, new_state) after reactivating a root."""
    root = await entity_repo.get_root(session, entry.entity_id)
    if root is None:
        # The root vanished outside the state machine — never guess a repair.
        raise RestoreConflictError()
    await session.refresh(root, with_for_update=True)
    previous = root.deletion_state
    if previous == DeletionState.PURGE_PENDING:
        raise PurgeInProgressError()
    if previous == DeletionState.PURGED:
        raise ObjectAlreadyPurgedError()
    if previous != DeletionState.SOFT_DELETED:
        raise EntityNotSoftDeletedError()

    # Historical-integrity preflight (doc 20 §10): restore returns the SAME
    # head pointer the snapshot recorded; a moved head is a conflict, not a
    # silent adoption of newer content.
    snap = entry.dependency_snapshot or {}
    expected_head = snap.get("current_revision_id")
    if expected_head is not None and expected_head != root.current_revision_id:
        raise RestoreConflictError()

    from entropia.domain.deletion import next_deletion_state

    root.deletion_state = next_deletion_state(previous, DeletionState.ACTIVE)
    root.deleted_at = None
    root.deleted_by = None
    root.delete_reason = None
    return root.current_revision_id, str(previous), str(root.deletion_state)


async def _restore_result_target(
    session: AsyncSession, entry: TrashEntry
) -> tuple[str | None, str, str]:
    from entropia.infrastructure.postgres.repositories import backtest as bt_repo

    result = await bt_repo.get_result(session, entry.entity_id)
    if result is None:
        raise RestoreConflictError()
    await session.refresh(result, with_for_update=True)
    previous = result.deletion_state
    if previous == _RESULT_PURGE_PENDING:
        raise PurgeInProgressError()
    if previous != _RESULT_SOFT_DELETED:
        if previous == "purged":
            raise ObjectAlreadyPurgedError()
        raise EntityNotSoftDeletedError()
    result.deletion_state = _RESULT_ACTIVE
    result.row_version += 1
    return None, previous, _RESULT_ACTIVE


async def _restore_manual_target(
    session: AsyncSession, actor: Actor, entry: TrashEntry
) -> tuple[str | None, str, str]:
    """Manual documents are page-local roots (doc 21 §8.4, UM-09): restore
    reactivates the SAME root/revision chain and the stream entry returns at
    its original (never-reassigned) stream_position, bumping stream_version."""
    from entropia.domain.manual.enums import StreamEntryState
    from entropia.infrastructure.postgres.repositories import manual as manual_repo

    document = await manual_repo.get_document(session, entry.entity_id)
    if document is None:
        raise RestoreConflictError()
    await manual_repo.lock_stream(session)
    await session.refresh(document, with_for_update=True)
    previous = document.deletion_state
    if previous == DeletionState.PURGE_PENDING:
        raise PurgeInProgressError()
    if previous == DeletionState.PURGED:
        raise ObjectAlreadyPurgedError()
    if previous != DeletionState.SOFT_DELETED:
        raise EntityNotSoftDeletedError()

    # Head-pointer integrity (doc 20 §10): restore returns the SAME revision
    # the snapshot recorded; a moved head is a conflict, never silent adoption.
    snap = entry.dependency_snapshot or {}
    expected_head = snap.get("current_revision_id")
    if expected_head is not None and expected_head != document.current_revision_id:
        raise RestoreConflictError()

    document.deletion_state = DeletionState.ACTIVE
    document.deleted_at = None
    document.deleted_by = None
    document.delete_reason = None
    document.row_version += 1
    stream_entry = await manual_repo.get_stream_entry(session, entry.entity_id)
    if stream_entry is not None and stream_entry.state != StreamEntryState.ACTIVE:
        stream_entry.state = StreamEntryState.ACTIVE
        stream_entry.row_version += 1
    prior_version = await manual_repo.current_stream_version(session)
    manual_repo.add_publication_event(
        session,
        event_type="manual_document_restored",
        document_id=entry.entity_id,
        revision_id=document.current_revision_id,
        stream_entry_id=stream_entry.stream_entry_id if stream_entry is not None else None,
        actor_principal_id=actor.principal_id,
        prior_stream_version=prior_version,
        resulting_stream_version=prior_version + 1,
        correlation_id=actor.correlation_id,
    )
    return document.current_revision_id, str(previous), str(DeletionState.ACTIVE)


async def _restore_entry_core(
    session: AsyncSession, actor: Actor, entry: TrashEntry
) -> dict[str, Any]:
    """Shared restore body: entry + target mutation + audit/outbox, one tx."""
    _assert_entry_recoverable(entry)
    if entry.entity_type == RESULT_ENTITY_TYPE:
        revision_id, previous, new_state = await _restore_result_target(session, entry)
    elif entry.entity_type == MANUAL_ENTITY_TYPE:
        revision_id, previous, new_state = await _restore_manual_target(session, actor, entry)
    else:
        revision_id, previous, new_state = await _restore_registry_target(session, entry)

    entry.status = TrashEntryStatus.RESTORED
    entry.restored_at = datetime.now(UTC)
    entry.restored_by = actor.principal_id
    entry.purge_error = None
    entry.row_version += 1

    audit_repo.add_audit_event(
        session,
        event_kind="trash.restored",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=entry.entity_id,
        target_entity_type=entry.entity_type,
        target_revision_id=revision_id,
        previous_state=previous,
        new_state=new_state,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="entity.restored",
        resource_type=entry.entity_type,
        resource_id=entry.entity_id,
        payload={"trash_entry_id": entry.id},
        correlation_id=actor.correlation_id,
    )
    return {
        "trash_entry_id": entry.id,
        "entity_id": entry.entity_id,
        "entity_type": entry.entity_type,
        "display_name": _display_identity(entry),
        "status": str(entry.status),
        "deletion_state": new_state,
        "current_revision_id": revision_id,
        "row_version": entry.row_version,
        "correlation_id": actor.correlation_id,
    }


async def restore_trash_entry(
    session: AsyncSession,
    actor: Actor,
    *,
    trash_entry_id: str,
    expected_head_revision_id: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin restore by Trash Entry id (doc 20 §7): OCC + idempotency + atomic
    root reactivation with the SAME entity_id/current_revision_id (no new revision)."""
    require_trash_admin(actor)

    async def _op() -> dict[str, Any]:
        entry = await trash_repo.get_entry(session, trash_entry_id)
        if entry is None:
            raise TrashEntryNotFoundError()
        await session.refresh(entry, with_for_update=True)
        if expected_head_revision_id is not None and entry.row_version != expected_head_revision_id:
            raise StaleRevisionError()
        return await _restore_entry_core(session, actor, entry)

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "trash.restore",
            "trash_entry_id": trash_entry_id,
            "expected_head_revision_id": expected_head_revision_id,
        },
        operation=_op,
    )


async def restore_entity(session: AsyncSession, actor: Actor, *, entity_id: str) -> EntityRegistry:
    """Admin restore addressed by entity id (Stage-1 compat surface).

    Resolves the single recoverable entry for the root and delegates to the
    shared restore body; returns the reactivated registry root.
    """
    require_trash_admin(actor)
    entry = await trash_repo.get_recoverable_entry_for_entity(session, entity_id)
    if entry is None:
        raise EntityNotSoftDeletedError()
    await session.refresh(entry, with_for_update=True)
    await _restore_entry_core(session, actor, entry)
    return await _require_root(session, entity_id)


# --------------------------------------------------------------------------- #
# Purge request (Admin-only, doc 20 §8.3, §9.3 trash.purge.request)            #
# --------------------------------------------------------------------------- #


async def _mark_target_purge_pending(session: AsyncSession, entry: TrashEntry) -> str:
    """Move the target to purge_pending; return the previous state string."""
    if entry.entity_type == MANUAL_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import manual as manual_repo

        document = await manual_repo.get_document(session, entry.entity_id)
        if document is None:
            raise ObjectAlreadyPurgedError()
        await session.refresh(document, with_for_update=True)
        manual_previous = document.deletion_state
        if manual_previous == DeletionState.PURGE_PENDING:
            raise PurgeInProgressError()
        if manual_previous == DeletionState.PURGED:
            raise ObjectAlreadyPurgedError()
        if manual_previous != DeletionState.SOFT_DELETED:
            raise EntityNotSoftDeletedError()
        document.deletion_state = DeletionState.PURGE_PENDING
        document.row_version += 1
        return str(manual_previous)

    if entry.entity_type == RESULT_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import backtest as bt_repo

        result = await bt_repo.get_result(session, entry.entity_id)
        if result is None:
            raise ObjectAlreadyPurgedError()
        await session.refresh(result, with_for_update=True)
        previous = result.deletion_state
        if previous != _RESULT_SOFT_DELETED:
            raise EntityNotSoftDeletedError()
        result.deletion_state = _RESULT_PURGE_PENDING
        result.row_version += 1
        return previous

    root = await _require_root(session, entry.entity_id)
    await session.refresh(root, with_for_update=True)
    previous = root.deletion_state
    if previous == DeletionState.PURGE_PENDING:
        raise PurgeInProgressError()
    if previous == DeletionState.PURGED:
        raise ObjectAlreadyPurgedError()
    if previous != DeletionState.SOFT_DELETED:
        raise EntityNotSoftDeletedError()

    from entropia.domain.deletion import next_deletion_state

    root.deletion_state = next_deletion_state(previous, DeletionState.PURGE_PENDING)
    return str(previous)


async def request_purge(
    session: AsyncSession,
    actor: Actor,
    *,
    trash_entry_id: str,
    confirmation_phrase: str,
    reauth_proof: str,
    expected_head_revision_id: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin Permanent Delete request (doc 20 §8.3): second confirmation + re-auth
    + OCC + idempotency -> target ``purge_pending`` + durable purge job (202).

    The re-auth proof (F-21) must be a real, unexpired, single-use token minted
    by ``POST /auth/reauth`` for the ``trash_purge`` purpose and bound to THIS
    actor — no arbitrary non-empty string can authorize a purge (doc 20 §0/§8.3;
    full MFA verification stays out of scope). The confirmation phrase must
    match the object's display identity.
    """
    require_trash_admin(actor)

    async def _op() -> dict[str, Any]:
        # Consumed INSIDE the idempotent operation: run_idempotent skips this
        # closure entirely on a cache-hit replay, so a legitimate retry of an
        # already-succeeded request never re-checks (and never re-rejects) the
        # proof it already spent on the first, successful attempt.
        await consume_reauth_proof(
            session,
            user_id=actor.principal_id or "",
            purpose=_TRASH_PURGE_REAUTH_PURPOSE,
            proof=reauth_proof,
        )
        entry = await trash_repo.get_entry(session, trash_entry_id)
        if entry is None:
            raise TrashEntryNotFoundError()
        await session.refresh(entry, with_for_update=True)
        if expected_head_revision_id is not None and entry.row_version != expected_head_revision_id:
            raise StaleRevisionError()
        _assert_entry_recoverable(entry)
        if confirmation_phrase.strip() != _display_identity(entry):
            raise PurgeConfirmationInvalidError()

        previous = await _mark_target_purge_pending(session, entry)
        job = enqueue_job(
            session,
            queue=PURGE_QUEUE,
            payload={"trash_entry_id": entry.id},
            actor_principal_id=actor.principal_id,
            correlation_id=actor.correlation_id,
        )
        entry.status = TrashEntryStatus.PURGE_PENDING
        entry.purge_job_id = job.job_id
        entry.purge_requested_by = actor.principal_id
        entry.purge_error = None
        entry.row_version += 1

        audit_repo.add_audit_event(
            session,
            event_kind="trash.purge_requested",
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            target_entity_id=entry.entity_id,
            target_entity_type=entry.entity_type,
            previous_state=previous,
            new_state=str(DeletionState.PURGE_PENDING),
            correlation_id=actor.correlation_id,
        )
        audit_repo.add_outbox_event(
            session,
            event_type="trash.purge_requested",
            resource_type=entry.entity_type,
            resource_id=entry.entity_id,
            payload={"trash_entry_id": entry.id, "purge_job_id": job.job_id},
            correlation_id=actor.correlation_id,
        )
        return {
            "purge_job_id": job.job_id,
            "trash_entry_id": entry.id,
            "entity_id": entry.entity_id,
            "entity_type": entry.entity_type,
            "deletion_state": str(DeletionState.PURGE_PENDING),
            "purge_status": "pending",
            "row_version": entry.row_version,
            "correlation_id": actor.correlation_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "trash.purge.request",
            "trash_entry_id": trash_entry_id,
            "expected_head_revision_id": expected_head_revision_id,
            "confirmation_phrase": confirmation_phrase,
        },
        operation=_op,
    )
