"""Trash page domain contract (Stage 6c, doc 20)."""

from entropia.domain.trash.page import (
    DEFAULT_LIST_STATUSES,
    MAX_SEARCH_TEXT,
    TRASH_CURSOR_NAMESPACE,
    TRASH_OBJECT_LOCATIONS,
    TrashEntryStatus,
    decode_trash_cursor,
    encode_trash_cursor,
    normalize_object_type,
    original_location_for,
)
from entropia.domain.trash.redaction import (
    REDACTED,
    SNAPSHOT_ALLOWED_KEYS,
    TRUNCATED_KEY,
    redact_snapshot,
)

__all__ = [
    "DEFAULT_LIST_STATUSES",
    "MAX_SEARCH_TEXT",
    "REDACTED",
    "SNAPSHOT_ALLOWED_KEYS",
    "TRASH_CURSOR_NAMESPACE",
    "TRASH_OBJECT_LOCATIONS",
    "TRUNCATED_KEY",
    "TrashEntryStatus",
    "decode_trash_cursor",
    "encode_trash_cursor",
    "normalize_object_type",
    "original_location_for",
    "redact_snapshot",
]
