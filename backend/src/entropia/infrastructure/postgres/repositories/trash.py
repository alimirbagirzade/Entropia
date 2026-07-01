"""Trash entries + tombstones data access (M3, §7; Stage 6c doc 20 §4, §5, §9.1).

Pure data access: policy (Admin-only Trash) and lifecycle validation live in the
application commands/queries. The list query pushes filters + the stable
``deleted_at DESC, id DESC`` keyset down to SQL — the client never receives the
whole Trash to filter locally (doc 20 §13).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.trash.page import TrashEntryStatus
from entropia.infrastructure.postgres.models import Tombstone, TrashEntry
from entropia.shared.ids import new_id

RECOVERABLE_STATUSES: tuple[TrashEntryStatus, ...] = (
    TrashEntryStatus.SOFT_DELETED,
    TrashEntryStatus.PURGE_PENDING,
    TrashEntryStatus.PURGE_FAILED,
)


def add_trash_entry(
    session: AsyncSession,
    *,
    entity_id: str,
    entity_type: str,
    deleted_by: str | None,
    reason: str | None,
    owner_at_deletion: str | None,
    dependency_snapshot: dict[str, Any] | None,
    display_name: str | None = None,
    original_location: str | None = None,
    deletion_snapshot: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> TrashEntry:
    entry = TrashEntry(
        id=new_id("trash"),
        entity_id=entity_id,
        entity_type=entity_type,
        deleted_by=deleted_by,
        reason=reason,
        owner_at_deletion=owner_at_deletion,
        dependency_snapshot=dependency_snapshot,
        display_name=display_name,
        original_location=original_location,
        deletion_snapshot=deletion_snapshot,
        status=TrashEntryStatus.SOFT_DELETED,
        correlation_id=correlation_id,
    )
    session.add(entry)
    return entry


async def get_entry(session: AsyncSession, trash_entry_id: str) -> TrashEntry | None:
    return await session.get(TrashEntry, trash_entry_id)


async def get_recoverable_entry_for_entity(
    session: AsyncSession, entity_id: str
) -> TrashEntry | None:
    """The single non-terminal entry for a root (a repeated delete never creates a
    duplicate — doc 20 §14). Newest-first guards against legacy duplicates."""
    stmt = (
        select(TrashEntry)
        .where(
            TrashEntry.entity_id == entity_id,
            TrashEntry.status.in_(RECOVERABLE_STATUSES),
        )
        .order_by(TrashEntry.deleted_at.desc(), TrashEntry.id.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


def _apply_search(stmt: Select[Any], q: str) -> Select[Any]:
    """Doc 20 §5 haystack: display name, type, original location, owner, deleted by
    (+ the entity id, the fallback display identity)."""
    needle = q.lower()
    return stmt.where(
        or_(
            func.lower(func.coalesce(TrashEntry.display_name, "")).contains(needle),
            func.lower(TrashEntry.entity_type).contains(needle),
            func.lower(func.coalesce(TrashEntry.original_location, "")).contains(needle),
            func.lower(func.coalesce(TrashEntry.owner_at_deletion, "")).contains(needle),
            func.lower(func.coalesce(TrashEntry.deleted_by, "")).contains(needle),
            func.lower(TrashEntry.entity_id).contains(needle),
        )
    )


async def list_entries(
    session: AsyncSession,
    *,
    statuses: Sequence[TrashEntryStatus],
    object_type: str | None,
    q: str | None,
    last: tuple[datetime, str] | None,
    limit: int,
) -> Sequence[TrashEntry]:
    """One keyset page, newest deletion first (``deleted_at DESC, id DESC``)."""
    stmt = select(TrashEntry).where(TrashEntry.status.in_(list(statuses)))
    if object_type is not None:
        stmt = stmt.where(TrashEntry.entity_type == object_type)
    if q:
        stmt = _apply_search(stmt, q)
    stmt = stmt.order_by(TrashEntry.deleted_at.desc(), TrashEntry.id.desc())
    if last is not None:
        last_at, last_id = last
        stmt = stmt.where(
            or_(
                TrashEntry.deleted_at < last_at,
                and_(TrashEntry.deleted_at == last_at, TrashEntry.id < last_id),
            )
        )
    return list((await session.execute(stmt.limit(limit))).scalars().all())


async def count_recoverable(session: AsyncSession) -> int:
    stmt = select(func.count()).where(TrashEntry.status.in_(RECOVERABLE_STATUSES))
    return int((await session.execute(stmt)).scalar_one())


def add_tombstone(
    session: AsyncSession, *, entity_id: str, entity_type: str, purged_by: str | None
) -> Tombstone:
    tomb = Tombstone(entity_id=entity_id, entity_type=entity_type, purged_by=purged_by)
    session.add(tomb)
    return tomb


async def get_tombstone(session: AsyncSession, entity_id: str) -> Tombstone | None:
    return await session.get(Tombstone, entity_id)
