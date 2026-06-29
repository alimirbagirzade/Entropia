"""Generic root/revision registry — the reusable spine for soft-delete,
optimistic concurrency, and the immutable revision chain (M2, DOMAIN_MODEL §1).

Concrete domain entities (strategy, package, dataset, ...) arrive in later
stages; they register here by `entity_type` and store their immutable payloads
as revisions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.lifecycle.enums import DeletionState, ValidationStatus
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column


class EntityRegistry(TimestampMixin, Base):
    """Stable identity + lifecycle/deletion pointers + head + row_version."""

    __tablename__ = "entity_registry"

    entity_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_principal_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lifecycle_state: Mapped[str | None] = mapped_column(String(48), nullable=True)
    deletion_state: Mapped[DeletionState] = mapped_column(
        enum_column(DeletionState, "deletion_state"),
        nullable=False,
        default=DeletionState.ACTIVE,
        index=True,
    )
    current_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


class EntityRevision(Base):
    """Immutable content snapshot. Never UPDATEd; each save inserts N+1."""

    __tablename__ = "entity_revisions"
    __table_args__ = (UniqueConstraint("entity_id", "revision_no", name="uq_entity_revision_no"),)

    revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("entity_registry.entity_id"), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_principal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    validation_status: Mapped[ValidationStatus | None] = mapped_column(
        enum_column(ValidationStatus, "validation_status"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
