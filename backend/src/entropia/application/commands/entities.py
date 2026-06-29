"""Generic create/save commands exercising the root/revision spine (M2).

These prove the universal pattern (insert revision N+1, advance head, audit,
optimistic concurrency) without any product-specific domain. Later stages build
concrete entities on the same mechanics.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_edit, require_authenticated
from entropia.infrastructure.postgres.models import EntityRegistry
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import entities as entity_repo
from entropia.shared.concurrency import check_row_version
from entropia.shared.errors import NotFoundError


async def create_entity(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_type: str,
    payload: dict[str, Any],
) -> EntityRegistry:
    require_authenticated(actor)
    root, revision = entity_repo.create_root_with_revision(
        session,
        entity_type=entity_type,
        owner_principal_id=actor.principal_id,
        created_by_principal_id=actor.principal_id,
        payload=payload,
    )
    audit_repo.add_audit_event(
        session,
        event_kind="entity.created",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=root.entity_id,
        target_entity_type=entity_type,
        target_revision_id=revision.revision_id,
        new_state="active",
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=entity_type,
        resource_id=root.entity_id,
        payload={"action": "created"},
        correlation_id=actor.correlation_id,
    )
    return root


async def save_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    payload: dict[str, Any],
    expected_row_version: int | None,
) -> EntityRegistry:
    root = await entity_repo.get_root(session, entity_id)
    if root is None:
        raise NotFoundError(f"Entity '{entity_id}' not found.")
    ensure_can_edit(actor, owner_principal_id=root.owner_principal_id)
    check_row_version(root.row_version, expected_row_version)

    revision = entity_repo.append_revision(
        session, root, payload=payload, created_by_principal_id=actor.principal_id
    )
    audit_repo.add_audit_event(
        session,
        event_kind="entity.revised",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=root.entity_id,
        target_entity_type=root.entity_type,
        target_revision_id=revision.revision_id,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=root.entity_type,
        resource_id=root.entity_id,
        payload={"action": "revised", "revision_id": revision.revision_id},
        correlation_id=actor.correlation_id,
    )
    return root
