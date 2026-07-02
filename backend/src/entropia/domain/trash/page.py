"""Trash page domain contract (Stage 6c, doc 20 §4, §5, §9.1, §13).

Server-owned pieces of the Admin Trash surface: the Trash-Entry status overlay
(separate from the root ``DeletionState`` — an entry outlives restore/purge as
evidence), the canonical object-type catalog + original-location map used by the
list filter and projection, and the opaque composite keyset cursor
(``deleted_at DESC, trash_entry_id DESC`` — doc 20 §13 gap resolution). An
unknown filter value is rejected (422 ``INVALID_TRASH_OBJECT_TYPE``), never
silently coerced to ``All types``.
"""

from __future__ import annotations

from enum import StrEnum

from entropia.domain.agent_lab.cursor import decode_cursor, encode_cursor
from entropia.shared.errors import CursorInvalidError, InvalidTrashObjectTypeError

TRASH_CURSOR_NAMESPACE = "trash_entries"
_CURSOR_SEP = "|"

MAX_SEARCH_TEXT = 128


class TrashEntryStatus(StrEnum):
    """Trash Entry status pill (doc 20 §3.2, §4). Orthogonal to the root's
    ``DeletionState``: a restored/purged entry stays as append-only evidence and
    simply leaves the default recoverable listing."""

    SOFT_DELETED = "soft_deleted"
    RESTORED = "restored"
    PURGE_PENDING = "purge_pending"
    PURGE_FAILED = "purge_failed"
    PURGED = "purged"


# Statuses shown in the default Admin listing (doc 20 §4: completed purges may be
# hidden; restored entries left the recoverable set).
DEFAULT_LIST_STATUSES: tuple[TrashEntryStatus, ...] = (
    TrashEntryStatus.SOFT_DELETED,
    TrashEntryStatus.PURGE_PENDING,
    TrashEntryStatus.PURGE_FAILED,
)

# Canonical object types that can appear in Trash -> original location label
# (doc 20 §3.3). Keys are the persisted ``entity_type`` values of the registry /
# result rows; the filter accepts exactly these (+ no free text).
TRASH_OBJECT_LOCATIONS: dict[str, str] = {
    "work_object": "Mainboard / Work Objects",
    "workspace": "Mainboard / Workspaces",
    "package": "Package Library",
    "package_request": "Create Package / Requests",
    "market_dataset": "Market Data",
    "research_dataset": "Research Data",
    "rationale_family": "Edit / Rationale Families",
    "backtest_result": "Mainboard / Backtest Results",
    "hypothesis_artifact": "Analysis Lab / Outputs",
}


def normalize_object_type(value: str | None) -> str | None:
    """Validate an ``object_type`` filter; ``None``/'all' means All types."""
    if value is None or value == "" or value == "all":
        return None
    if value not in TRASH_OBJECT_LOCATIONS:
        raise InvalidTrashObjectTypeError()
    return value


def original_location_for(entity_type: str) -> str | None:
    """Canonical original-location label for a deleted root (doc 20 §3.3)."""
    return TRASH_OBJECT_LOCATIONS.get(entity_type)


def encode_trash_cursor(*, deleted_at_iso: str, entry_id: str) -> str:
    """Opaque forward cursor for the ``deleted_at DESC, id DESC`` keyset."""
    return encode_cursor(
        TRASH_CURSOR_NAMESPACE, last_key=f"{deleted_at_iso}{_CURSOR_SEP}{entry_id}"
    )


def decode_trash_cursor(cursor: str) -> tuple[str, str]:
    """Decode into ``(deleted_at_iso, entry_id)``; malformed -> CURSOR_INVALID."""
    decoded = decode_cursor(cursor, namespace=TRASH_CURSOR_NAMESPACE)
    deleted_at_iso, sep, entry_id = decoded.last_key.partition(_CURSOR_SEP)
    if not sep or not deleted_at_iso or not entry_id:
        raise CursorInvalidError()
    return deleted_at_iso, entry_id


__all__ = [
    "DEFAULT_LIST_STATUSES",
    "MAX_SEARCH_TEXT",
    "TRASH_CURSOR_NAMESPACE",
    "TRASH_OBJECT_LOCATIONS",
    "TrashEntryStatus",
    "decode_trash_cursor",
    "encode_trash_cursor",
    "normalize_object_type",
    "original_location_for",
]
