"""Trash entries and tombstones (M3, DOMAIN_MODEL §7; Stage 6c page contract
doc 20 §9.1).

The entry is append-only evidence of one deletion: the snapshot columns are
immutable after insert, while ``status``/purge columns advance with the
restore/purge lifecycle and ``row_version`` carries the Trash OCC token
(``expected_head_revision_id``)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.trash.page import TrashEntryStatus
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.types import enum_column


class TrashEntry(Base):
    """One soft delete: redacted snapshots + recovery/purge control (doc 20 §9.1)."""

    __tablename__ = "trash_entries"
    __table_args__ = (
        # Stable keyset ordering `deleted_at DESC, id DESC` (doc 20 §13).
        Index("ix_trash_entries_deleted_at_id", text("deleted_at DESC"), text("id DESC")),
        Index("ix_trash_entries_status", "status"),
        Index("ix_trash_entries_entity_type", "entity_type"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    deleted_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    owner_at_deletion: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dependency_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # --- Stage 6c page-contract columns (doc 20 §4, §5, §9.1) ---
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    original_location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    deletion_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[TrashEntryStatus] = mapped_column(
        enum_column(TrashEntryStatus, "trash_entry_status"),
        nullable=False,
        default=TrashEntryStatus.SOFT_DELETED,
        server_default=TrashEntryStatus.SOFT_DELETED.value,
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    purge_job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    purge_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    purge_requested_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    restored_by: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Tombstone(Base):
    """Post-purge marker. The entity_id is never reused."""

    __tablename__ = "tombstones"

    entity_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    purged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    purged_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
