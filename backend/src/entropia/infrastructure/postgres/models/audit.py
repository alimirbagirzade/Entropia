"""Append-only audit events + transactional outbox (M3, DOMAIN_MODEL §8)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.lifecycle.enums import ActorKind
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.types import enum_column


class AuditEvent(Base):
    """Immutable. Never updated or deleted; survives delete and purge.
    Corrections are added as new events via ``causation_event_id``."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_log_order", "occurred_at", "event_id"),
        Index("ix_audit_events_target", "target_entity_id"),
    )

    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    event_kind: Mapped[str] = mapped_column(String(96), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    actor_principal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    actor_kind: Mapped[ActorKind] = mapped_column(
        enum_column(ActorKind, "actor_kind"), nullable=False
    )
    target_entity_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    previous_state: Mapped[str | None] = mapped_column(String(48), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(48), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    causation_event_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_task_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload_hash_before: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_hash_after: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)


class OutboxEvent(Base):
    """Transactional outbox. Written in the same tx as the domain mutation;
    relayed by the scheduler. Consumer failure never rolls back the root."""

    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_unpublished", "published_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(96), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
