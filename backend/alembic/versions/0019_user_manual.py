"""stage 7a — User Manual (doc 21 §9, §9.1)

Six tables: manual_documents (page-local root + baseline flag),
manual_document_revisions (immutable content versions),
manual_stream_entries (unique never-reassigned stream_position),
manual_content_blocks (canonical safe-render blocks),
manual_search_chunks (Postgres-FTS projection, GIN 'simple' index),
manual_publication_events (append-only trail; UNIQUE monotonic
resulting_stream_version doubles as the reader stream_version source).

Seeds the built-in baseline guide (is_baseline=true, stream_position=1) from
the same ``build_baseline_seed`` content source tests use, so every
environment addresses the same fixed ids (doc 21 §1, §3.3).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.manual.baseline import build_baseline_seed
from entropia.domain.manual.enums import (
    BlockType,
    ManualSourceType,
    PublicationState,
    StreamEntryState,
)
from entropia.infrastructure.postgres.repositories.manual import block_id_for
from entropia.infrastructure.postgres.types import enum_column
from entropia.shared.ids import new_id

revision: str = "0019_user_manual"
down_revision: str | None = "0018_trash_page"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"
_DOCUMENT_FK = "manual_documents.document_id"
_REVISION_FK = "manual_document_revisions.revision_id"


def upgrade() -> None:
    # === manual_documents (root; FK -> principals) ===
    op.create_table(
        "manual_documents",
        sa.Column("document_id", sa.String(40), primary_key=True),
        sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "deletion_state",
            enum_column(DeletionState, "manual_document_deletion_state"),
            nullable=False,
            server_default=DeletionState.ACTIVE.value,
        ),
        sa.Column("owner_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("current_revision_id", sa.String(40), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(40), nullable=True),
        sa.Column("delete_reason", sa.String(512), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_manual_documents_deletion", "manual_documents", ["deletion_state"])

    # === manual_document_revisions (FK -> documents, principals) ===
    op.create_table(
        "manual_document_revisions",
        sa.Column("revision_id", sa.String(40), primary_key=True),
        sa.Column("document_id", sa.String(40), sa.ForeignKey(_DOCUMENT_FK), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column(
            "publication_state",
            enum_column(PublicationState, "manual_publication_state"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column(
            "source_type", enum_column(ManualSourceType, "manual_source_type"), nullable=False
        ),
        sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("content_checksum", sa.String(64), nullable=False),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("document_id", "revision_no", name="uq_manual_revision_no"),
    )
    op.create_index("ix_manual_revisions_document", "manual_document_revisions", ["document_id"])
    op.create_index(
        "ix_manual_revisions_checksum", "manual_document_revisions", ["content_checksum"]
    )

    # === manual_stream_entries (FK -> documents, revisions) ===
    op.create_table(
        "manual_stream_entries",
        sa.Column("stream_entry_id", sa.String(40), primary_key=True),
        sa.Column("document_id", sa.String(40), sa.ForeignKey(_DOCUMENT_FK), nullable=False),
        sa.Column("stream_position", sa.Integer(), nullable=False),
        sa.Column(
            "state",
            enum_column(StreamEntryState, "manual_stream_entry_state"),
            nullable=False,
            server_default=StreamEntryState.ACTIVE.value,
        ),
        sa.Column(
            "visible_revision_id", sa.String(40), sa.ForeignKey(_REVISION_FK), nullable=False
        ),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("document_id", name="uq_manual_stream_entry_document"),
        sa.UniqueConstraint("stream_position", name="uq_manual_stream_position"),
    )
    op.create_index(
        "ix_manual_stream_entries_state_position",
        "manual_stream_entries",
        ["state", "stream_position"],
    )

    # === manual_content_blocks (FK -> revisions, CASCADE) ===
    op.create_table(
        "manual_content_blocks",
        sa.Column("block_id", sa.String(64), primary_key=True),
        sa.Column(
            "revision_id",
            sa.String(40),
            sa.ForeignKey(_REVISION_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("block_index", sa.Integer(), nullable=False),
        sa.Column("block_type", enum_column(BlockType, "manual_block_type"), nullable=False),
        sa.Column("anchor", sa.String(120), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("revision_id", "block_index", name="uq_manual_block_index"),
    )
    op.create_index("ix_manual_blocks_revision", "manual_content_blocks", ["revision_id"])

    # === manual_search_chunks (FK -> documents, revisions; GIN FTS) ===
    op.create_table(
        "manual_search_chunks",
        sa.Column("chunk_id", sa.String(40), primary_key=True),
        sa.Column("document_id", sa.String(40), sa.ForeignKey(_DOCUMENT_FK), nullable=False),
        sa.Column(
            "revision_id",
            sa.String(40),
            sa.ForeignKey(_REVISION_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("heading_path", sa.String(512), nullable=False),
        sa.Column("anchor", sa.String(160), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("block_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_manual_chunks_revision", "manual_search_chunks", ["revision_id"])
    op.create_index("ix_manual_chunks_document", "manual_search_chunks", ["document_id"])
    op.create_index(
        "ix_manual_chunks_fts",
        "manual_search_chunks",
        [sa.text("to_tsvector('simple', content_text)")],
        postgresql_using="gin",
    )

    # === manual_publication_events (FK -> documents, principals) ===
    op.create_table(
        "manual_publication_events",
        sa.Column("event_id", sa.String(40), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("document_id", sa.String(40), sa.ForeignKey(_DOCUMENT_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=True),
        sa.Column("stream_entry_id", sa.String(40), nullable=True),
        sa.Column("actor_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True),
        sa.Column("prior_stream_version", sa.Integer(), nullable=False),
        sa.Column("resulting_stream_version", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=True),
        sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("resulting_stream_version", name="uq_manual_event_stream_version"),
    )
    op.create_index("ix_manual_events_document", "manual_publication_events", ["document_id"])
    op.create_index("ix_manual_events_type", "manual_publication_events", ["event_type"])

    _seed_baseline()


def _seed_baseline() -> None:
    seed = build_baseline_seed()
    documents = sa.table(
        "manual_documents",
        sa.column("document_id", sa.String),
        sa.column("is_baseline", sa.Boolean),
        sa.column("deletion_state", sa.String),
        sa.column("current_revision_id", sa.String),
        sa.column("row_version", sa.Integer),
    )
    revisions = sa.table(
        "manual_document_revisions",
        sa.column("revision_id", sa.String),
        sa.column("document_id", sa.String),
        sa.column("revision_no", sa.Integer),
        sa.column("publication_state", sa.String),
        sa.column("title", sa.String),
        sa.column("source_type", sa.String),
        sa.column("content_checksum", sa.String),
    )
    entries = sa.table(
        "manual_stream_entries",
        sa.column("stream_entry_id", sa.String),
        sa.column("document_id", sa.String),
        sa.column("stream_position", sa.Integer),
        sa.column("state", sa.String),
        sa.column("visible_revision_id", sa.String),
        sa.column("row_version", sa.Integer),
    )
    blocks = sa.table(
        "manual_content_blocks",
        sa.column("block_id", sa.String),
        sa.column("revision_id", sa.String),
        sa.column("block_index", sa.Integer),
        sa.column("block_type", sa.String),
        sa.column("anchor", sa.String),
        sa.column("payload", postgresql.JSONB),
    )
    chunks = sa.table(
        "manual_search_chunks",
        sa.column("chunk_id", sa.String),
        sa.column("document_id", sa.String),
        sa.column("revision_id", sa.String),
        sa.column("heading_path", sa.String),
        sa.column("anchor", sa.String),
        sa.column("content_text", sa.Text),
        sa.column("block_ids", postgresql.JSONB),
    )
    events = sa.table(
        "manual_publication_events",
        sa.column("event_id", sa.String),
        sa.column("event_type", sa.String),
        sa.column("document_id", sa.String),
        sa.column("revision_id", sa.String),
        sa.column("stream_entry_id", sa.String),
        sa.column("prior_stream_version", sa.Integer),
        sa.column("resulting_stream_version", sa.Integer),
        sa.column("source_type", sa.String),
        sa.column("checksum", sa.String),
    )

    op.bulk_insert(
        documents,
        [
            {
                "document_id": seed.document_id,
                "is_baseline": True,
                "deletion_state": DeletionState.ACTIVE.value,
                "current_revision_id": seed.revision_id,
                "row_version": 1,
            }
        ],
    )
    op.bulk_insert(
        revisions,
        [
            {
                "revision_id": seed.revision_id,
                "document_id": seed.document_id,
                "revision_no": 1,
                "publication_state": PublicationState.PUBLISHED.value,
                "title": seed.title,
                "source_type": ManualSourceType.BUILT_IN.value,
                "content_checksum": seed.checksum,
            }
        ],
    )
    op.bulk_insert(
        entries,
        [
            {
                "stream_entry_id": seed.stream_entry_id,
                "document_id": seed.document_id,
                "stream_position": seed.stream_position,
                "state": StreamEntryState.ACTIVE.value,
                "visible_revision_id": seed.revision_id,
                "row_version": 1,
            }
        ],
    )
    op.bulk_insert(
        blocks,
        [
            {
                "block_id": block_id_for(seed.revision_id, index),
                "revision_id": seed.revision_id,
                "block_index": index,
                "block_type": block.block_type.value,
                "anchor": block.anchor,
                "payload": block.payload,
            }
            for index, block in enumerate(seed.blocks)
        ],
    )
    op.bulk_insert(
        chunks,
        [
            {
                "chunk_id": new_id("mchk"),
                "document_id": seed.document_id,
                "revision_id": seed.revision_id,
                "heading_path": chunk.heading_path[:512],
                "anchor": chunk.anchor[:160],
                "content_text": chunk.content_text,
                "block_ids": [block_id_for(seed.revision_id, i) for i in chunk.block_indexes],
            }
            for chunk in seed.chunks
        ],
    )
    op.bulk_insert(
        events,
        [
            {
                "event_id": new_id("mevt"),
                "event_type": "manual_document_published",
                "document_id": seed.document_id,
                "revision_id": seed.revision_id,
                "stream_entry_id": seed.stream_entry_id,
                "prior_stream_version": 0,
                "resulting_stream_version": 1,
                "source_type": ManualSourceType.BUILT_IN.value,
                "checksum": seed.checksum,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("manual_publication_events")
    op.drop_table("manual_search_chunks")
    op.drop_table("manual_content_blocks")
    op.drop_table("manual_stream_entries")
    op.drop_table("manual_document_revisions")
    op.drop_table("manual_documents")
