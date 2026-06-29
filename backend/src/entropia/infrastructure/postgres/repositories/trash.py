"""Trash entries + tombstones data access (M3, §7)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.infrastructure.postgres.models import Tombstone, TrashEntry
from entropia.shared.ids import new_id


def add_trash_entry(
    session: AsyncSession,
    *,
    entity_id: str,
    entity_type: str,
    deleted_by: str | None,
    reason: str | None,
    owner_at_deletion: str | None,
    dependency_snapshot: dict[str, Any] | None,
) -> TrashEntry:
    entry = TrashEntry(
        id=new_id("trash"),
        entity_id=entity_id,
        entity_type=entity_type,
        deleted_by=deleted_by,
        reason=reason,
        owner_at_deletion=owner_at_deletion,
        dependency_snapshot=dependency_snapshot,
    )
    session.add(entry)
    return entry


def add_tombstone(
    session: AsyncSession, *, entity_id: str, entity_type: str, purged_by: str | None
) -> Tombstone:
    tomb = Tombstone(entity_id=entity_id, entity_type=entity_type, purged_by=purged_by)
    session.add(tomb)
    return tomb
