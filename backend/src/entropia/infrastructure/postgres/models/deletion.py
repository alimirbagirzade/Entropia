"""Trash entries and tombstones (M3, DOMAIN_MODEL §7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.infrastructure.postgres.base import Base


class TrashEntry(Base):
    """Immutable record of a soft delete + a redacted dependency snapshot."""

    __tablename__ = "trash_entries"

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


class Tombstone(Base):
    """Post-purge marker. The entity_id is never reused."""

    __tablename__ = "tombstones"

    entity_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    purged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    purged_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
