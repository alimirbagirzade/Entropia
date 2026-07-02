"""User Manual read models (Stage 7a, doc 21 §7, §8.1, §12).

All-role read: Admin, Supervisor, User AND the internal Agent principal read
the same Published projection — menu visibility is never authorization
(doc 21 §2). The reader/sidebar renders ONE ``stream_version`` snapshot per
page; search runs server-side over title/heading/content chunks (never a
document-level substring filter) and returns anchor + block_ids + the
stream_version the anchors resolve against (doc 21 §14).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.agent_lab.cursor import clamp_limit
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.manual.enums import BlockType, ManualSourceType, source_label
from entropia.domain.manual.enums import StreamEntryState as EntryState
from entropia.domain.manual.stream import (
    MAX_SEARCH_QUERY,
    decode_search_cursor,
    decode_stream_cursor,
    encode_search_cursor,
    encode_stream_cursor,
    section_anchor,
)
from entropia.infrastructure.postgres.models import ManualContentBlock
from entropia.infrastructure.postgres.repositories import manual as manual_repo
from entropia.shared.errors import ManualDocumentNotFoundError, ManualSectionNotFoundError

_HEADING = BlockType.HEADING


def _block_row(block: ManualContentBlock) -> dict[str, Any]:
    return {
        "block_id": block.block_id,
        "block_type": block.block_type.value,
        "anchor": block.anchor,
        "payload": block.payload,
    }


async def get_manual_stream(
    session: AsyncSession,
    actor: Actor,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Continuous stream page: baseline first, appended sections by their
    unique ``stream_position`` (doc 21 §8.1, UM-01)."""
    require_authenticated(actor)
    page_limit = clamp_limit(limit)
    after_position = decode_stream_cursor(cursor) if cursor is not None else None

    rows = await manual_repo.list_stream_sections(
        session, after_position=after_position, limit=page_limit + 1
    )
    has_more = len(rows) > page_limit
    page = rows[:page_limit]
    blocks_by_revision = await manual_repo.load_blocks(
        session, [revision.revision_id for _, _, revision in page]
    )

    sections: list[dict[str, Any]] = []
    for entry, document, revision in page:
        sections.append(
            {
                "document_id": document.document_id,
                "is_baseline": document.is_baseline,
                "title": revision.title,
                "revision_id": revision.revision_id,
                "revision_no": revision.revision_no,
                "source_type": revision.source_type.value,
                "source_label": source_label(revision.source_type, revision.source_filename),
                "stream_position": entry.stream_position,
                "anchor": section_anchor(document.document_id),
                "blocks": [
                    _block_row(block) for block in blocks_by_revision.get(revision.revision_id, [])
                ],
            }
        )

    next_cursor: str | None = None
    if has_more and page:
        next_cursor = encode_stream_cursor(page[-1][0].stream_position)
    return {
        "data": sections,
        "meta": {
            "stream_version": await manual_repo.current_stream_version(session),
            "cursor": next_cursor,
            "has_more": has_more,
            "limit": page_limit,
        },
    }


async def search_manual(
    session: AsyncSession,
    actor: Actor,
    *,
    q: str | None,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Published-corpus FTS page (doc 21 §8.1, UM-02): results carry
    document_id, revision_no, heading_path, excerpt, anchor, block_ids and the
    stream_version the anchors resolve against. A blank query searches nothing."""
    require_authenticated(actor)
    page_limit = clamp_limit(limit)
    stream_version = await manual_repo.current_stream_version(session)
    needle = " ".join((q or "").split())[:MAX_SEARCH_QUERY]
    if not needle:
        return {
            "data": [],
            "meta": {
                "stream_version": stream_version,
                "cursor": None,
                "has_more": False,
                "limit": page_limit,
                "query": "",
            },
        }

    after = decode_search_cursor(cursor) if cursor is not None else None
    rows = await manual_repo.search_chunks(session, query=needle, after=after, limit=page_limit + 1)
    has_more = len(rows) > page_limit
    page = rows[:page_limit]

    results: list[dict[str, Any]] = []
    for chunk, _rank, excerpt, document, revision in page:
        results.append(
            {
                "chunk_id": chunk.chunk_id,
                "document_id": document.document_id,
                "revision_id": revision.revision_id,
                "revision_no": revision.revision_no,
                "title": revision.title,
                "heading_path": chunk.heading_path,
                "excerpt": excerpt,
                "anchor": chunk.anchor,
                "block_ids": chunk.block_ids,
                "source_label": source_label(revision.source_type, revision.source_filename),
            }
        )

    next_cursor: str | None = None
    if has_more and page:
        tail = page[-1]
        next_cursor = encode_search_cursor(rank=tail[1], chunk_id=tail[0].chunk_id)
    return {
        "data": results,
        "meta": {
            "stream_version": stream_version,
            "cursor": next_cursor,
            "has_more": has_more,
            "limit": page_limit,
            "query": needle,
        },
    }


def _slice_from_anchor(blocks: list[ManualContentBlock], anchor: str) -> list[ManualContentBlock]:
    """Blocks from the anchored heading to the next same-or-higher heading."""
    start: int | None = None
    level = 0
    for index, block in enumerate(blocks):
        if block.block_type == _HEADING and block.anchor == anchor:
            start = index
            level = int(block.payload.get("level", 1))
            break
    if start is None:
        raise ManualSectionNotFoundError()
    section = [blocks[start]]
    for block in blocks[start + 1 :]:
        if block.block_type == _HEADING and int(block.payload.get("level", 1)) <= level:
            break
        section.append(block)
    return section


async def get_manual_section(
    session: AsyncSession,
    actor: Actor,
    *,
    document_id: str,
    anchor: str | None = None,
    revision_no: int | None = None,
) -> dict[str, Any]:
    """One published section with canonical blocks + citation metadata
    (doc 21 §12 `documentation.get_section`, UM-03). Draft or soft-deleted
    content never enters normal retrieval; a stale revision/anchor is a
    MANUAL_SECTION_NOT_FOUND recovery signal (UM-18)."""
    require_authenticated(actor)
    document = await manual_repo.get_document(session, document_id)
    if document is None or document.deletion_state != DeletionState.ACTIVE:
        raise ManualDocumentNotFoundError()
    entry = await manual_repo.get_stream_entry(session, document_id)
    if entry is None or entry.state != EntryState.ACTIVE:
        raise ManualDocumentNotFoundError()
    revision = await manual_repo.get_revision(session, entry.visible_revision_id)
    if revision is None:
        raise ManualDocumentNotFoundError()
    if revision_no is not None and revision_no != revision.revision_no:
        raise ManualSectionNotFoundError()

    blocks = (await manual_repo.load_blocks(session, [revision.revision_id])).get(
        revision.revision_id, []
    )
    doc_anchor = section_anchor(document_id)
    resolved_anchor = anchor or doc_anchor
    if resolved_anchor != doc_anchor:
        blocks = _slice_from_anchor(blocks, resolved_anchor)

    return {
        "document_id": document_id,
        "is_baseline": document.is_baseline,
        "revision_id": revision.revision_id,
        "revision_no": revision.revision_no,
        "title": revision.title,
        "source_label": source_label(
            ManualSourceType(revision.source_type), revision.source_filename
        ),
        "anchor": resolved_anchor,
        "stream_version": await manual_repo.current_stream_version(session),
        "blocks": [_block_row(block) for block in blocks],
        "citation": {
            "document_id": document_id,
            "revision_no": revision.revision_no,
            "anchor": resolved_anchor,
            "block_ids": [block.block_id for block in blocks],
        },
    }


__all__ = ["get_manual_section", "get_manual_stream", "search_manual"]
