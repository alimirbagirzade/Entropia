"""Trash read model (Stage 6c, doc 20 §4, §5, §13).

Admin-only cursor projection over ``trash_entries`` — NOT the V18 local
``deletedItems`` array. Every entry point re-applies ``require_trash_admin``
(the route guard is never the only check). Filters (``q``, ``object_type``) and
the stable ``deleted_at DESC, id DESC`` keyset are pushed down to SQL; an
unknown object type or malformed cursor is rejected, never coerced. The detail
query returns the redacted, size-bounded deletion/dependency snapshots only —
no secrets, no raw artifact payloads (doc 20 §12).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.agent_lab.cursor import clamp_limit
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_trash_admin
from entropia.domain.trash.page import (
    DEFAULT_LIST_STATUSES,
    MAX_SEARCH_TEXT,
    TRASH_OBJECT_LOCATIONS,
    TrashEntryStatus,
    decode_trash_cursor,
    encode_trash_cursor,
    normalize_object_type,
)
from entropia.infrastructure.postgres.models import TrashEntry
from entropia.infrastructure.postgres.repositories import entities as entity_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import CursorInvalidError, TrashEntryNotFoundError

_RESULT_ENTITY_TYPE = "backtest_result"

# An entry is restore-eligible when its object is recoverable-soft-deleted:
# purge_failed returned the root to soft_deleted; purge_pending disables Restore
# (doc 20 §4 interaction matrix).
_RESTORE_ELIGIBLE_STATUSES = (TrashEntryStatus.SOFT_DELETED, TrashEntryStatus.PURGE_FAILED)

_PURGE_STATUS_BY_ENTRY_STATUS: dict[TrashEntryStatus, str | None] = {
    TrashEntryStatus.SOFT_DELETED: None,
    TrashEntryStatus.RESTORED: None,
    TrashEntryStatus.PURGE_PENDING: "pending",
    TrashEntryStatus.PURGE_FAILED: "failed",
    TrashEntryStatus.PURGED: "completed",
}


def _row(entry: TrashEntry) -> dict[str, Any]:
    return {
        "trash_entry_id": entry.id,
        "entity_id": entry.entity_id,
        "object_type": entry.entity_type,
        "display_name": entry.display_name or entry.entity_id,
        "original_location": entry.original_location,
        "original_owner": entry.owner_at_deletion,
        "deleted_by": entry.deleted_by,
        "deleted_at": entry.deleted_at.isoformat() if entry.deleted_at else None,
        "delete_reason": entry.reason,
        "status": str(entry.status),
        "purge_status": _PURGE_STATUS_BY_ENTRY_STATUS.get(entry.status),
        "purge_job_id": entry.purge_job_id,
        "restore_eligible": entry.status in _RESTORE_ELIGIBLE_STATUSES,
        "row_version": entry.row_version,
        "correlation_id": entry.correlation_id,
    }


async def list_trash_entries(
    session: AsyncSession,
    actor: Actor,
    *,
    q: str | None = None,
    object_type: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Admin-only, filtered, newest-deletion-first cursor page (doc 20 §4, §13)."""
    require_trash_admin(actor)
    page_limit = clamp_limit(limit)
    otype = normalize_object_type(object_type)
    needle = (q or "").strip()[:MAX_SEARCH_TEXT] or None

    last: tuple[datetime, str] | None = None
    if cursor is not None:
        deleted_at_iso, entry_id = decode_trash_cursor(cursor)
        try:
            last = (datetime.fromisoformat(deleted_at_iso), entry_id)
        except ValueError as exc:
            raise CursorInvalidError() from exc

    rows = await trash_repo.list_entries(
        session,
        statuses=DEFAULT_LIST_STATUSES,
        object_type=otype,
        q=needle,
        last=last,
        limit=page_limit + 1,
    )
    has_more = len(rows) > page_limit
    page = list(rows[:page_limit])
    next_cursor: str | None = None
    if has_more and page:
        tail = page[-1]
        next_cursor = encode_trash_cursor(
            deleted_at_iso=tail.deleted_at.isoformat(), entry_id=tail.id
        )

    recoverable_total = await trash_repo.count_recoverable(session)
    return {
        "data": [_row(r) for r in page],
        "meta": {
            "cursor": next_cursor,
            "has_more": has_more,
            "limit": page_limit,
            "recoverable_total": recoverable_total,
            "object_types": sorted(TRASH_OBJECT_LOCATIONS),
        },
    }


async def _target_deletion_state(session: AsyncSession, entry: TrashEntry) -> str | None:
    """Best-effort CURRENT deletion state of the target, for refresh semantics
    (doc 20 §7 Refresh status). ``None`` when the target row is unresolvable."""
    if entry.entity_type == _RESULT_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import backtest as bt_repo

        result = await bt_repo.get_result(session, entry.entity_id)
        return result.deletion_state if result is not None else None
    root = await entity_repo.get_root(session, entry.entity_id)
    return str(root.deletion_state) if root is not None else None


async def get_trash_entry_detail(
    session: AsyncSession, actor: Actor, *, trash_entry_id: str
) -> dict[str, Any]:
    """Admin-only snapshot reader (doc 20 §3.2, §7 Open Snapshot).

    Returns the immutable redacted deletion/dependency snapshots recorded at
    delete time plus the live purge/restore control state. Read-only: no root
    reactivation, no snapshot edit.
    """
    require_trash_admin(actor)
    entry = await trash_repo.get_entry(session, trash_entry_id)
    if entry is None:
        raise TrashEntryNotFoundError()

    detail = _row(entry)
    tombstone = await trash_repo.get_tombstone(session, entry.entity_id)
    detail.update(
        {
            "deletion_snapshot": entry.deletion_snapshot or {},
            "dependency_snapshot": entry.dependency_snapshot or {},
            "purge_error": entry.purge_error,
            "purge_requested_by": entry.purge_requested_by,
            "restored_at": entry.restored_at.isoformat() if entry.restored_at else None,
            "restored_by": entry.restored_by,
            "current_deletion_state": await _target_deletion_state(session, entry),
            "tombstone": (
                {
                    "purged_at": tombstone.purged_at.isoformat() if tombstone.purged_at else None,
                    "purged_by": tombstone.purged_by,
                }
                if tombstone is not None
                else None
            ),
        }
    )
    return detail


__all__ = ["get_trash_entry_detail", "list_trash_entries"]
