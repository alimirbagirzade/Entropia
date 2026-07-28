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
from typing import Any, NamedTuple

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
from entropia.domain.trash.restore import (
    RestoreConflictKind,
    conflict_summary,
    resolution_options,
)
from entropia.infrastructure.postgres.models import TrashEntry
from entropia.infrastructure.postgres.repositories import entities as entity_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import CursorInvalidError, TrashEntryNotFoundError

_RESULT_ENTITY_TYPE = "backtest_result"
_ARTIFACT_ENTITY_TYPE = "hypothesis_artifact"
_MANUAL_ENTITY_TYPE = "manual_document"

_HEAD_POINTER_MOVED = RestoreConflictKind.HEAD_POINTER_MOVED
_TARGET_MISSING = RestoreConflictKind.TARGET_MISSING

# Statuses where restore is closed by the deletion lifecycle itself — there is no
# resolution to offer, only the error code the command would raise (doc 20 §4).
_BLOCKED_REASON_BY_STATUS: dict[TrashEntryStatus, str] = {
    TrashEntryStatus.PURGE_PENDING: "PURGE_IN_PROGRESS",
    TrashEntryStatus.PURGED: "OBJECT_ALREADY_PURGED",
    TrashEntryStatus.RESTORED: "ENTITY_NOT_SOFT_DELETED",
}

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
    if entry.entity_type == _ARTIFACT_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import agent_lab as al_repo

        artifact = await al_repo.get_hypothesis(session, entry.entity_id)
        return str(artifact.deletion_state) if artifact is not None else None
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


# --------------------------------------------------------------------------- #
# Restore preflight (O-17, doc 20 §5 "Restore conflict choice", §8.2)          #
# --------------------------------------------------------------------------- #


class _TargetProbe(NamedTuple):
    """Read-only view of what the restore command would find.

    ``adjudicates_head`` is what separates "this type pins a head pointer" from
    "its head happens to be NULL" — collapsing the two would silently skip the
    historical-integrity check for a root whose pointer really is unset.
    """

    resolved: bool
    adjudicates_head: bool = False
    current_head: Any = None


async def _probe_restore_target(session: AsyncSession, entry: TrashEntry) -> _TargetProbe:
    """Mirror of the command's per-type target lookup — WITHOUT any mutation.

    Only ``EntityRegistry`` roots and manual documents adjudicate a head pointer
    on restore; a Result / Lab artifact carries its deletion flag on its own row
    and has no snapshot head to disagree with (commands/deletion.py).
    """
    if entry.entity_type == _RESULT_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import backtest as bt_repo

        result = await bt_repo.get_result(session, entry.entity_id)
        return _TargetProbe(resolved=result is not None)
    if entry.entity_type == _ARTIFACT_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import agent_lab as al_repo

        artifact = await al_repo.get_hypothesis(session, entry.entity_id)
        return _TargetProbe(resolved=artifact is not None)
    if entry.entity_type == _MANUAL_ENTITY_TYPE:
        from entropia.infrastructure.postgres.repositories import manual as manual_repo

        document = await manual_repo.get_document(session, entry.entity_id)
        if document is None:
            return _TargetProbe(resolved=False)
        return _TargetProbe(True, adjudicates_head=True, current_head=document.current_revision_id)
    root = await entity_repo.get_root(session, entry.entity_id)
    if root is None:
        return _TargetProbe(resolved=False)
    return _TargetProbe(True, adjudicates_head=True, current_head=root.current_revision_id)


def _conflict_report(
    kind: RestoreConflictKind, *, expected_head: Any = None, current_head: Any = None
) -> dict[str, Any]:
    """The typed conflict + its option set, from the ONE domain catalog."""
    return {
        "conflict_kind": str(kind),
        "conflict_summary": conflict_summary(
            kind, expected_head=expected_head, current_head=current_head
        ),
        "resolutions": resolution_options(kind),
    }


async def get_restore_preflight(
    session: AsyncSession, actor: Actor, *, trash_entry_id: str
) -> dict[str, Any]:
    """Admin-only READ answering "would Restore succeed, and if not, what may I
    choose?" (O-17; doc 20 §5 "Typed ``resolution`` enum from preflight", §8.2).

    Read-only by construction: no lock, no mutation, no partial projection. The
    Admin drives the doc 20 §6 "Restore needs attention" panel from this, then
    resubmits the restore with the chosen typed ``resolution`` and the SAME
    ``expected_head_revision_id`` this response echoes.

    ``outcome`` is one of:

    * ``allow``    — preflight passes; Restore may be submitted as-is.
    * ``conflict`` — a typed conflict, with the resolutions its domain adapter
      supports. An EMPTY ``resolutions`` list is a real answer, not an omission:
      nothing can unblock it and the object stays in Trash (doc 20 §8.2).
    * ``blocked``  — the deletion lifecycle forbids restore outright (purge in
      flight, already purged, already restored). ``blocked_reason`` carries the
      error code the command would raise; there is nothing to choose.

    Preflight is advisory, never authorization: the command re-runs every check
    inside its own transaction, so a race between this read and the submit is
    caught there (and by OCC), not trusted from here.
    """
    require_trash_admin(actor)
    entry = await trash_repo.get_entry(session, trash_entry_id)
    if entry is None:
        raise TrashEntryNotFoundError()

    preflight: dict[str, Any] = {
        "trash_entry_id": entry.id,
        "entity_id": entry.entity_id,
        "object_type": entry.entity_type,
        "display_name": entry.display_name or entry.entity_id,
        # Echoed so the retry carries the SAME expected deletion version the
        # Admin reviewed; a moved entry then fails OCC instead of restoring blind.
        "expected_head_revision_id": entry.row_version,
        "outcome": "allow",
        "blocked_reason": None,
        "conflict_kind": None,
        "conflict_summary": None,
        "resolutions": [],
    }

    blocked_reason = _BLOCKED_REASON_BY_STATUS.get(entry.status)
    if blocked_reason is not None:
        preflight.update({"outcome": "blocked", "blocked_reason": blocked_reason})
        return preflight

    probe = await _probe_restore_target(session, entry)
    if not probe.resolved:
        preflight.update({"outcome": "conflict", **_conflict_report(_TARGET_MISSING)})
        return preflight

    expected_head = (entry.dependency_snapshot or {}).get("current_revision_id")
    if probe.adjudicates_head and expected_head is not None and expected_head != probe.current_head:
        preflight.update(
            {
                "outcome": "conflict",
                **_conflict_report(
                    _HEAD_POINTER_MOVED,
                    expected_head=expected_head,
                    current_head=probe.current_head,
                ),
            }
        )
    return preflight


__all__ = ["get_restore_preflight", "get_trash_entry_detail", "list_trash_entries"]
