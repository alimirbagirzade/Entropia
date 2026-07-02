"""User Manual tables (Stage 7a, doc 21 §9, §9.1).

Root/revision/stream-entry separation — never one append-only TEXT blob
(doc 21 §14). ``manual_documents`` is a page-local root (like
``backtest_results``): its ``deletion_state`` overlay integrates the landed
Trash core via type dispatch, not EntityRegistry. Revisions and their blocks
are immutable after publication; the stream entry pins the document's unique
``stream_position`` (positions are never reassigned, so restore is
deterministic). Search chunks are the Postgres-FTS projection over
title/heading/content; publication events are the append-only audit trail
with a monotonic ``resulting_stream_version``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.manual.enums import BlockType, ManualSourceType, PublicationState
from entropia.domain.manual.enums import StreamEntryState as EntryState
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_PRINCIPAL_FK = "principals.principal_id"
_DOCUMENT_FK = "manual_documents.document_id"
_REVISION_FK = "manual_document_revisions.revision_id"


class ManualDocument(TimestampMixin, Base):
    """Permanent manual root: identity, provenance, baseline flag (doc 21 §9.1)."""

    __tablename__ = "manual_documents"
    __table_args__ = (Index("ix_manual_documents_deletion", "deletion_state"),)

    document_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    is_baseline: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    deletion_state: Mapped[DeletionState] = mapped_column(
        enum_column(DeletionState, "manual_document_deletion_state"),
        nullable=False,
        default=DeletionState.ACTIVE,
        server_default=DeletionState.ACTIVE.value,
    )
    owner_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    current_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


class ManualDocumentRevision(Base):
    """Immutable content/source/parse version of one document (doc 21 §9)."""

    __tablename__ = "manual_document_revisions"
    __table_args__ = (
        UniqueConstraint("document_id", "revision_no", name="uq_manual_revision_no"),
        Index("ix_manual_revisions_document", "document_id"),
        Index("ix_manual_revisions_checksum", "content_checksum"),
    )

    revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(40), ForeignKey(_DOCUMENT_FK), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    publication_state: Mapped[PublicationState] = mapped_column(
        enum_column(PublicationState, "manual_publication_state"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[ManualSourceType] = mapped_column(
        enum_column(ManualSourceType, "manual_source_type"), nullable=False
    )
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ManualStreamEntry(TimestampMixin, Base):
    """One document's fixed slot in the continuous stream (doc 21 §9). The
    unique ``stream_position`` is assigned once under the stream lock and never
    reassigned — a removed entry keeps its slot for deterministic restore."""

    __tablename__ = "manual_stream_entries"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_manual_stream_entry_document"),
        UniqueConstraint("stream_position", name="uq_manual_stream_position"),
        Index("ix_manual_stream_entries_state_position", "state", "stream_position"),
    )

    stream_entry_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(40), ForeignKey(_DOCUMENT_FK), nullable=False)
    stream_position: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[EntryState] = mapped_column(
        enum_column(EntryState, "manual_stream_entry_state"),
        nullable=False,
        default=EntryState.ACTIVE,
        server_default=EntryState.ACTIVE.value,
    )
    visible_revision_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_REVISION_FK), nullable=False
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ManualContentBlock(Base):
    """Canonical safe-render block of one revision (doc 21 §9.2). ``block_id``
    is stable per revision; ``payload`` carries the per-type required fields."""

    __tablename__ = "manual_content_blocks"
    __table_args__ = (
        UniqueConstraint("revision_id", "block_index", name="uq_manual_block_index"),
        Index("ix_manual_blocks_revision", "revision_id"),
    )

    block_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_REVISION_FK, ondelete="CASCADE"), nullable=False
    )
    block_index: Mapped[int] = mapped_column(Integer, nullable=False)
    block_type: Mapped[BlockType] = mapped_column(
        enum_column(BlockType, "manual_block_type"), nullable=False
    )
    anchor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")


class ManualSearchChunk(Base):
    """Title/heading/content search projection row (doc 21 §9). Queried with
    Postgres FTS (``to_tsvector('simple', content_text)``, GIN-indexed)."""

    __tablename__ = "manual_search_chunks"
    __table_args__ = (
        Index("ix_manual_chunks_revision", "revision_id"),
        Index("ix_manual_chunks_document", "document_id"),
        Index(
            "ix_manual_chunks_fts",
            text("to_tsvector('simple', content_text)"),
            postgresql_using="gin",
        ),
    )

    chunk_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(40), ForeignKey(_DOCUMENT_FK), nullable=False)
    revision_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_REVISION_FK, ondelete="CASCADE"), nullable=False
    )
    heading_path: Mapped[str] = mapped_column(String(512), nullable=False)
    anchor: Mapped[str] = mapped_column(String(160), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    block_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ManualPublicationEvent(Base):
    """Append-only publication/audit trail (doc 21 §9, §11). The UNIQUE
    monotonic ``resulting_stream_version`` doubles as the reader snapshot
    version source (``manual_stream_projection.stream_version``)."""

    __tablename__ = "manual_publication_events"
    __table_args__ = (
        UniqueConstraint("resulting_stream_version", name="uq_manual_event_stream_version"),
        Index("ix_manual_events_document", "document_id"),
        Index("ix_manual_events_type", "event_type"),
    )

    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    document_id: Mapped[str] = mapped_column(String(40), ForeignKey(_DOCUMENT_FK), nullable=False)
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    stream_entry_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    actor_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    prior_stream_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_stream_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
