"""User Manual data access (Stage 7a, doc 21 §9, §13).

Every stream mutation first takes the transaction-scoped advisory stream lock
(one global order — mirrors the identity admin-count lock), so unique
``stream_position`` assignment and the monotonic ``stream_version`` are race
free (UM-13). Search runs server-side over the FTS chunk projection joined to
ACTIVE stream entries + ACTIVE documents — soft-deleted content leaves the
search projection without touching historical rows (doc 21 §10, §11).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Numeric, Row, and_, cast, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.manual.baseline import build_baseline_seed
from entropia.domain.manual.blocks import ContentBlock, SearchChunkDraft
from entropia.domain.manual.enums import ManualSourceType, PublicationState, StreamEntryState
from entropia.domain.manual.stream import SEARCH_RANK_SCALE
from entropia.infrastructure.postgres.models import (
    ManualContentBlock,
    ManualDocument,
    ManualDocumentRevision,
    ManualPublicationEvent,
    ManualSearchChunk,
    ManualStreamEntry,
)
from entropia.shared.ids import new_id

# Fixed advisory-lock key serializing manual stream mutations (doc 21 §7 UM-13).
MANUAL_STREAM_LOCK_KEY = 210_721


async def lock_stream(session: AsyncSession) -> None:
    """Take the xact-scoped global stream lock BEFORE any stream mutation."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": MANUAL_STREAM_LOCK_KEY}
    )


# --------------------------------------------------------------------------- #
# Lookups                                                                      #
# --------------------------------------------------------------------------- #


async def get_document(session: AsyncSession, document_id: str) -> ManualDocument | None:
    return await session.get(ManualDocument, document_id)


async def get_revision(session: AsyncSession, revision_id: str) -> ManualDocumentRevision | None:
    return await session.get(ManualDocumentRevision, revision_id)


async def get_revision_by_no(
    session: AsyncSession, document_id: str, revision_no: int
) -> ManualDocumentRevision | None:
    stmt = select(ManualDocumentRevision).where(
        ManualDocumentRevision.document_id == document_id,
        ManualDocumentRevision.revision_no == revision_no,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_stream_entry(session: AsyncSession, document_id: str) -> ManualStreamEntry | None:
    stmt = select(ManualStreamEntry).where(ManualStreamEntry.document_id == document_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def current_stream_version(session: AsyncSession) -> int:
    stmt = select(func.coalesce(func.max(ManualPublicationEvent.resulting_stream_version), 0))
    return int((await session.execute(stmt)).scalar_one())


async def next_stream_position(session: AsyncSession) -> int:
    """Positions are assigned once (under the stream lock) and NEVER reused —
    a removed entry keeps its slot so restore is deterministic (doc 21 §8.4)."""
    stmt = select(func.coalesce(func.max(ManualStreamEntry.stream_position), 0))
    return int((await session.execute(stmt)).scalar_one()) + 1


async def find_active_duplicate(
    session: AsyncSession, *, checksum: str, exclude_document_id: str | None = None
) -> str | None:
    """document_id of an ACTIVE stream section with the same normalized
    checksum on its visible revision (MANUAL_DUPLICATE_CONTENT, doc 21 §10)."""
    stmt = (
        select(ManualDocument.document_id)
        .join(ManualStreamEntry, ManualStreamEntry.document_id == ManualDocument.document_id)
        .join(
            ManualDocumentRevision,
            ManualDocumentRevision.revision_id == ManualStreamEntry.visible_revision_id,
        )
        .where(
            ManualStreamEntry.state == StreamEntryState.ACTIVE,
            ManualDocument.deletion_state == DeletionState.ACTIVE,
            ManualDocumentRevision.content_checksum == checksum,
        )
        .limit(1)
    )
    if exclude_document_id is not None:
        stmt = stmt.where(ManualDocument.document_id != exclude_document_id)
    return (await session.execute(stmt)).scalar_one_or_none()


# --------------------------------------------------------------------------- #
# Inserts (no commit — the caller's transaction owns atomicity)                #
# --------------------------------------------------------------------------- #


def block_id_for(revision_id: str, index: int) -> str:
    """Stable per-revision block id (doc 21 §9.2 'block_id stable')."""
    return f"{revision_id}-b{index:04d}"


async def create_document(
    session: AsyncSession,
    *,
    document_id: str | None = None,
    is_baseline: bool = False,
    owner_principal_id: str | None,
    created_by_principal_id: str | None,
) -> ManualDocument:
    document = ManualDocument(
        document_id=document_id or new_id("mdoc"),
        is_baseline=is_baseline,
        deletion_state=DeletionState.ACTIVE,
        owner_principal_id=owner_principal_id,
        created_by_principal_id=created_by_principal_id,
        row_version=1,
    )
    session.add(document)
    await session.flush()  # L1: root row exists before revisions reference it
    return document


async def create_revision(
    session: AsyncSession,
    *,
    revision_id: str | None = None,
    document_id: str,
    revision_no: int,
    title: str,
    source_type: ManualSourceType,
    source_filename: str | None,
    content_checksum: str,
    created_by_principal_id: str | None,
    blocks: list[ContentBlock],
) -> ManualDocumentRevision:
    """Insert one immutable Published revision together with its blocks
    (L1: the revision row flushes BEFORE its child blocks)."""
    revision = ManualDocumentRevision(
        revision_id=revision_id or new_id("mrev"),
        document_id=document_id,
        revision_no=revision_no,
        publication_state=PublicationState.PUBLISHED,
        title=title,
        source_type=source_type,
        source_filename=source_filename,
        content_checksum=content_checksum,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    await session.flush()
    for index, block in enumerate(blocks):
        session.add(
            ManualContentBlock(
                block_id=block_id_for(revision.revision_id, index),
                revision_id=revision.revision_id,
                block_index=index,
                block_type=block.block_type,
                anchor=block.anchor,
                payload=block.payload,
            )
        )
    await session.flush()
    return revision


async def create_stream_entry(
    session: AsyncSession,
    *,
    stream_entry_id: str | None = None,
    document_id: str,
    stream_position: int,
    visible_revision_id: str,
) -> ManualStreamEntry:
    entry = ManualStreamEntry(
        stream_entry_id=stream_entry_id or new_id("mstr"),
        document_id=document_id,
        stream_position=stream_position,
        state=StreamEntryState.ACTIVE,
        visible_revision_id=visible_revision_id,
        row_version=1,
    )
    session.add(entry)
    await session.flush()
    return entry


def add_search_chunks(
    session: AsyncSession,
    *,
    document_id: str,
    revision_id: str,
    chunks: list[SearchChunkDraft],
) -> list[ManualSearchChunk]:
    rows: list[ManualSearchChunk] = []
    for chunk in chunks:
        row = ManualSearchChunk(
            chunk_id=new_id("mchk"),
            document_id=document_id,
            revision_id=revision_id,
            heading_path=chunk.heading_path[:512],
            anchor=chunk.anchor[:160],
            content_text=chunk.content_text,
            block_ids=[block_id_for(revision_id, i) for i in chunk.block_indexes],
        )
        session.add(row)
        rows.append(row)
    return rows


def add_publication_event(
    session: AsyncSession,
    *,
    event_type: str,
    document_id: str,
    revision_id: str | None,
    stream_entry_id: str | None,
    actor_principal_id: str | None,
    prior_stream_version: int,
    resulting_stream_version: int,
    source_type: str | None = None,
    source_filename: str | None = None,
    checksum: str | None = None,
    correlation_id: str | None = None,
) -> ManualPublicationEvent:
    event = ManualPublicationEvent(
        event_id=new_id("mevt"),
        event_type=event_type,
        document_id=document_id,
        revision_id=revision_id,
        stream_entry_id=stream_entry_id,
        actor_principal_id=actor_principal_id,
        prior_stream_version=prior_stream_version,
        resulting_stream_version=resulting_stream_version,
        source_type=source_type,
        source_filename=source_filename,
        checksum=checksum,
        correlation_id=correlation_id,
    )
    session.add(event)
    return event


async def delete_search_chunks_for_document(session: AsyncSession, document_id: str) -> None:
    """Purge-time content redaction of the search projection (doc 21 §11)."""
    await session.execute(
        delete(ManualSearchChunk).where(ManualSearchChunk.document_id == document_id)
    )


# --------------------------------------------------------------------------- #
# Reader / search projections                                                  #
# --------------------------------------------------------------------------- #


async def list_stream_sections(
    session: AsyncSession, *, after_position: int | None, limit: int
) -> list[Row[tuple[ManualStreamEntry, ManualDocument, ManualDocumentRevision]]]:
    """ACTIVE sections ordered by the unique ``stream_position`` (doc 21 §14)."""
    stmt = (
        select(ManualStreamEntry, ManualDocument, ManualDocumentRevision)
        .join(ManualDocument, ManualDocument.document_id == ManualStreamEntry.document_id)
        .join(
            ManualDocumentRevision,
            ManualDocumentRevision.revision_id == ManualStreamEntry.visible_revision_id,
        )
        .where(
            ManualStreamEntry.state == StreamEntryState.ACTIVE,
            ManualDocument.deletion_state == DeletionState.ACTIVE,
        )
        .order_by(ManualStreamEntry.stream_position.asc())
        .limit(limit)
    )
    if after_position is not None:
        stmt = stmt.where(ManualStreamEntry.stream_position > after_position)
    return list((await session.execute(stmt)).all())


async def load_blocks(
    session: AsyncSession, revision_ids: list[str]
) -> dict[str, list[ManualContentBlock]]:
    if not revision_ids:
        return {}
    stmt = (
        select(ManualContentBlock)
        .where(ManualContentBlock.revision_id.in_(revision_ids))
        .order_by(ManualContentBlock.revision_id, ManualContentBlock.block_index)
    )
    grouped: dict[str, list[ManualContentBlock]] = {}
    for block in (await session.execute(stmt)).scalars():
        grouped.setdefault(block.revision_id, []).append(block)
    return grouped


async def search_chunks(
    session: AsyncSession,
    *,
    query: str,
    after: tuple[Decimal, str] | None,
    limit: int,
) -> list[Row[Any]]:
    """Published-only FTS page: (chunk, rank, excerpt, document, revision).

    Rank is rounded to a fixed NUMERIC scale so the (rank DESC, chunk_id DESC)
    keyset comparison is exact when the cursor round-trips (doc 21 §13).
    """
    tsq = func.plainto_tsquery("simple", query)
    tsv = func.to_tsvector("simple", ManualSearchChunk.content_text)
    rank = func.round(cast(func.ts_rank(tsv, tsq), Numeric(20, 10)), SEARCH_RANK_SCALE).label(
        "rank"
    )
    excerpt = func.ts_headline(
        "simple",
        ManualSearchChunk.content_text,
        tsq,
        "StartSel=[, StopSel=], MaxWords=30, MinWords=8",
    ).label("excerpt")

    stmt = (
        select(ManualSearchChunk, rank, excerpt, ManualDocument, ManualDocumentRevision)
        .join(
            ManualStreamEntry,
            ManualStreamEntry.visible_revision_id == ManualSearchChunk.revision_id,
        )
        .join(ManualDocument, ManualDocument.document_id == ManualSearchChunk.document_id)
        .join(
            ManualDocumentRevision,
            ManualDocumentRevision.revision_id == ManualSearchChunk.revision_id,
        )
        .where(
            ManualStreamEntry.state == StreamEntryState.ACTIVE,
            ManualDocument.deletion_state == DeletionState.ACTIVE,
            tsv.op("@@")(tsq),
        )
        .order_by(rank.desc(), ManualSearchChunk.chunk_id.desc())
        .limit(limit)
    )
    if after is not None:
        after_rank, after_chunk_id = after
        rank_expr = func.round(cast(func.ts_rank(tsv, tsq), Numeric(20, 10)), SEARCH_RANK_SCALE)
        stmt = stmt.where(
            or_(
                rank_expr < after_rank,
                and_(rank_expr == after_rank, ManualSearchChunk.chunk_id < after_chunk_id),
            )
        )
    return list((await session.execute(stmt)).all())


# --------------------------------------------------------------------------- #
# Baseline seed (shared by migration 0019 and tests)                           #
# --------------------------------------------------------------------------- #


async def seed_baseline(session: AsyncSession) -> ManualDocument:
    """Idempotently insert the built-in baseline guide (doc 21 §1, §3.3)."""
    seed = build_baseline_seed()
    existing = await get_document(session, seed.document_id)
    if existing is not None:
        return existing
    await lock_stream(session)
    document = await create_document(
        session,
        document_id=seed.document_id,
        is_baseline=True,
        owner_principal_id=None,
        created_by_principal_id=None,
    )
    revision = await create_revision(
        session,
        revision_id=seed.revision_id,
        document_id=seed.document_id,
        revision_no=1,
        title=seed.title,
        source_type=ManualSourceType.BUILT_IN,
        source_filename=None,
        content_checksum=seed.checksum,
        created_by_principal_id=None,
        blocks=seed.blocks,
    )
    document.current_revision_id = revision.revision_id
    await create_stream_entry(
        session,
        stream_entry_id=seed.stream_entry_id,
        document_id=seed.document_id,
        stream_position=seed.stream_position,
        visible_revision_id=revision.revision_id,
    )
    add_search_chunks(
        session, document_id=seed.document_id, revision_id=revision.revision_id, chunks=seed.chunks
    )
    prior = await current_stream_version(session)
    add_publication_event(
        session,
        event_type="manual_document_published",
        document_id=seed.document_id,
        revision_id=revision.revision_id,
        stream_entry_id=seed.stream_entry_id,
        actor_principal_id=None,
        prior_stream_version=prior,
        resulting_stream_version=prior + 1,
        source_type=ManualSourceType.BUILT_IN.value,
        checksum=seed.checksum,
    )
    return document
