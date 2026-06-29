"""Generic root/revision registry data access (M2, §1)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.revision.hashing import content_hash
from entropia.domain.revision.head import next_revision_no
from entropia.infrastructure.postgres.models import EntityRegistry, EntityRevision
from entropia.shared.ids import new_id


async def get_root(session: AsyncSession, entity_id: str) -> EntityRegistry | None:
    return await session.get(EntityRegistry, entity_id)


def create_root_with_revision(
    session: AsyncSession,
    *,
    entity_type: str,
    owner_principal_id: str | None,
    created_by_principal_id: str | None,
    payload: dict[str, Any],
    lifecycle_state: str | None = None,
) -> tuple[EntityRegistry, EntityRevision]:
    entity_id = new_id("ent")
    revision = EntityRevision(
        revision_id=new_id("rev"),
        entity_id=entity_id,
        revision_no=next_revision_no(None),
        parent_revision_id=None,
        payload=payload,
        content_hash=content_hash(payload),
        created_by_principal_id=created_by_principal_id,
    )
    root = EntityRegistry(
        entity_id=entity_id,
        entity_type=entity_type,
        owner_principal_id=owner_principal_id,
        created_by_principal_id=created_by_principal_id,
        lifecycle_state=lifecycle_state,
        deletion_state=DeletionState.ACTIVE,
        current_revision_id=revision.revision_id,
        row_version=1,
    )
    session.add(root)
    session.add(revision)
    return root, revision


def append_revision(
    session: AsyncSession,
    root: EntityRegistry,
    *,
    payload: dict[str, Any],
    created_by_principal_id: str | None,
) -> EntityRevision:
    """Insert revision N+1 and advance the head pointer + row_version."""
    revision = EntityRevision(
        revision_id=new_id("rev"),
        entity_id=root.entity_id,
        revision_no=next_revision_no(_current_revision_no(root)),
        parent_revision_id=root.current_revision_id,
        payload=payload,
        content_hash=content_hash(payload),
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    root.row_version += 1
    return revision


def _current_revision_no(root: EntityRegistry) -> int | None:
    # The head pointer is enough for next_revision_no; callers that need the
    # exact prior number can load it, but row_version mirrors revision count
    # for the generic registry.
    return root.row_version


async def list_soft_deleted(session: AsyncSession, *, limit: int) -> Sequence[EntityRegistry]:
    stmt = (
        select(EntityRegistry)
        .where(EntityRegistry.deletion_state == DeletionState.SOFT_DELETED)
        .order_by(EntityRegistry.deleted_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
