"""Soft-delete / restore / purge commands (M3, §7).

Each runs one transaction: domain mutation + trash/tombstone + audit + outbox.
Trash view, restore and purge are Admin-only; normal soft-delete is allowed for
the owner (or Admin). Forbidden deletion-state jumps are rejected by the state
machine before any write.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.deletion import next_deletion_state
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_edit, require_admin
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import EntityRegistry
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import entities as entity_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import NotFoundError


async def _require_root(session: AsyncSession, entity_id: str) -> EntityRegistry:
    root = await entity_repo.get_root(session, entity_id)
    if root is None:
        raise NotFoundError(f"Entity '{entity_id}' not found.")
    return root


async def soft_delete_entity(
    session: AsyncSession, actor: Actor, *, entity_id: str, reason: str | None = None
) -> EntityRegistry:
    root = await _require_root(session, entity_id)
    ensure_can_edit(actor, owner_principal_id=root.owner_principal_id)

    previous = root.deletion_state
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


async def restore_entity(session: AsyncSession, actor: Actor, *, entity_id: str) -> EntityRegistry:
    require_admin(actor)
    root = await _require_root(session, entity_id)

    previous = root.deletion_state
    # Restore keeps the same entity_id and current_revision_id (no new revision).
    root.deletion_state = next_deletion_state(previous, DeletionState.ACTIVE)
    root.deleted_at = None
    root.deleted_by = None
    root.delete_reason = None

    audit_repo.add_audit_event(
        session,
        event_kind="entity.restored",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=root.entity_id,
        target_entity_type=root.entity_type,
        target_revision_id=root.current_revision_id,
        previous_state=str(previous),
        new_state=str(root.deletion_state),
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="entity.restored",
        resource_type=root.entity_type,
        resource_id=root.entity_id,
        payload={},
        correlation_id=actor.correlation_id,
    )
    return root


async def purge_entity(session: AsyncSession, actor: Actor, *, entity_id: str) -> None:
    """Admin-only irreversible purge. Stage 1 preflight is trivial (no domain
    dependencies yet); later stages add running-run / active-assignment checks
    before allowing the transition. Leaves a tombstone; the id is never reused."""
    require_admin(actor)
    root = await _require_root(session, entity_id)

    entity_type = root.entity_type
    previous = root.deletion_state
    # active -> purged is forbidden; must pass through purge_pending.
    pending = next_deletion_state(previous, DeletionState.PURGE_PENDING)
    next_deletion_state(pending, DeletionState.PURGED)  # validate final hop

    trash_repo.add_tombstone(
        session, entity_id=root.entity_id, entity_type=entity_type, purged_by=actor.principal_id
    )
    audit_repo.add_audit_event(
        session,
        event_kind="entity.purged",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=root.entity_id,
        target_entity_type=entity_type,
        previous_state=str(previous),
        new_state=str(DeletionState.PURGED),
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="entity.purged",
        resource_type=entity_type,
        resource_id=root.entity_id,
        payload={},
        correlation_id=actor.correlation_id,
    )
    await session.delete(root)
