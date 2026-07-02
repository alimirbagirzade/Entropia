"""User Manual enums + fixed identities (Stage 7a, doc 21 §9, §9.1).

``MANUAL_ENTITY_TYPE`` is the Trash/type-dispatch key for manual documents —
they are page-local roots (like ``backtest_result``), not EntityRegistry rows.
The baseline guide ships with the product under fixed ids so the migration
seed and tests address the same row (doc 21 §1, §3.3).
"""

from __future__ import annotations

from enum import StrEnum

MANUAL_ENTITY_TYPE = "manual_document"

BASELINE_DOCUMENT_ID = "mdoc_baseline_entropia_guide"
BASELINE_REVISION_ID = "mrev_baseline_entropia_guide_1"
BASELINE_STREAM_ENTRY_ID = "mstr_baseline_entropia_guide"
BASELINE_STREAM_POSITION = 1


class ManualSourceType(StrEnum):
    """``manual_document_revision.source_type`` (doc 21 §9.1)."""

    BUILT_IN = "built_in"
    ADDED_TEXT = "added_text"
    UPLOADED_TXT = "uploaded_txt"
    UPLOADED_MARKDOWN = "uploaded_markdown"
    UPLOADED_HTML = "uploaded_html"


class PublicationState(StrEnum):
    """Immutable revision publication overlay (doc 21 §9): a Published revision
    becomes Superseded when replaced; Removed marks purge-time redaction."""

    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    REMOVED = "removed"


class StreamEntryState(StrEnum):
    """``manual_stream_entry.state`` (doc 21 §9). A removed entry keeps its
    unique ``stream_position`` forever — positions are never reassigned — so a
    Trash restore returns the SAME deterministic slot (doc 21 §8.4, UM-09)."""

    ACTIVE = "active"
    REMOVED = "removed"


class BlockType(StrEnum):
    """Canonical safe-render block types (doc 21 §9.2)."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    BULLET_LIST = "bullet_list"
    ORDERED_LIST = "ordered_list"
    CODE = "code"
    CALLOUT = "callout"
    DIVIDER = "divider"


# Upload acceptance is extension/MIME-allowlisted (doc 21 §5, UM-06).
SOURCE_TYPE_BY_EXTENSION: dict[str, ManualSourceType] = {
    ".txt": ManualSourceType.UPLOADED_TXT,
    ".md": ManualSourceType.UPLOADED_MARKDOWN,
    ".markdown": ManualSourceType.UPLOADED_MARKDOWN,
    ".html": ManualSourceType.UPLOADED_HTML,
    ".htm": ManualSourceType.UPLOADED_HTML,
}

# Reader-facing source label (doc 21 §3.2 source meta).
SOURCE_LABELS: dict[ManualSourceType, str] = {
    ManualSourceType.BUILT_IN: "Built-in Manual",
    ManualSourceType.ADDED_TEXT: "Added text document",
    ManualSourceType.UPLOADED_TXT: "Uploaded TXT document",
    ManualSourceType.UPLOADED_MARKDOWN: "Uploaded Markdown document",
    ManualSourceType.UPLOADED_HTML: "Uploaded HTML document",
}


def source_label(source_type: ManualSourceType, source_filename: str | None) -> str:
    """Reader source meta: uploads show the original filename as descriptive
    provenance (never executed/rendered as markup, doc 21 §9.1)."""
    base = SOURCE_LABELS[source_type]
    if source_filename and source_type is not ManualSourceType.BUILT_IN:
        return f"{base} — {source_filename}"
    return base


__all__ = [
    "BASELINE_DOCUMENT_ID",
    "BASELINE_REVISION_ID",
    "BASELINE_STREAM_ENTRY_ID",
    "BASELINE_STREAM_POSITION",
    "MANUAL_ENTITY_TYPE",
    "SOURCE_LABELS",
    "SOURCE_TYPE_BY_EXTENSION",
    "BlockType",
    "ManualSourceType",
    "PublicationState",
    "StreamEntryState",
    "source_label",
]
