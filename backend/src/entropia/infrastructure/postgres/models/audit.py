"""Append-only audit events + transactional outbox (M3, DOMAIN_MODEL §8)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DDL, DateTime, Index, Integer, String, event, func, text
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
        # Log-projection filter indexes (doc 19 §6.2): each mirrors one equality
        # filter of ``list_log_events`` plus the newest-first
        # ``(occurred_at, event_id)`` keyset, so a filtered page is a single
        # ordered index scan. Partial WHERE matches the filter semantics (a NULL
        # row can never match) and keeps the insert-hot append path cheap.
        # ``severity`` indexes only non-info rows — the warning/error triage
        # case; ``severity = 'info'`` matches the table bulk and deliberately
        # rides the log-order index instead.
        Index(
            "ix_audit_events_severity_order",
            "severity",
            "occurred_at",
            "event_id",
            postgresql_where=text("severity != 'info'"),
        ),
        Index(
            "ix_audit_events_actor_order",
            "actor_principal_id",
            "occurred_at",
            "event_id",
            postgresql_where=text("actor_principal_id IS NOT NULL"),
        ),
        Index(
            "ix_audit_events_target_type_order",
            "target_entity_type",
            "occurred_at",
            "event_id",
            postgresql_where=text("target_entity_type IS NOT NULL"),
        ),
        # Correlation chain (doc 19 §5): equality + the same composite order —
        # serves the detail view's ASC chain (and a DESC keyset via backward
        # scan) without touching the heap for ordering.
        Index(
            "ix_audit_events_correlation_order",
            "correlation_id",
            "occurred_at",
            "event_id",
            postgresql_where=text("correlation_id IS NOT NULL"),
        ),
        # §6.2 exact-or-prefix filter runs ``lower(correlation_id) LIKE 'p%'``
        # while ids store UPPERCASE Crockford base32 — only this expression
        # index (pattern ops, locale-independent) can serve that predicate.
        Index(
            "ix_audit_events_correlation_prefix",
            text("lower(correlation_id) varchar_pattern_ops"),
            postgresql_where=text("correlation_id IS NOT NULL"),
        ),
        # Substring (pg_trgm) indexes (doc 19 §6.2): the family token filter and
        # the ``q`` search run ``lower(col) LIKE '%needle%'`` — a leading-wildcard
        # LIKE that no B-tree (not even ``varchar_pattern_ops``) can serve; only a
        # ``gin_trgm_ops`` trigram index does. Each is an expression index over
        # ``lower(col)`` to match the predicate. ``event_kind`` is NOT NULL so it
        # covers every row; the nullable columns carry a partial ``IS NOT NULL``
        # predicate (a NULL row never matches a ``contains``) to keep the
        # insert-hot append path cheap. The extension is provisioned by the
        # ``before_create`` listener below (create_all) and migration 0023
        # (alembic).
        Index(
            "ix_audit_events_event_kind_trgm",
            text("lower(event_kind) gin_trgm_ops"),
            postgresql_using="gin",
        ),
        Index(
            "ix_audit_events_target_id_trgm",
            text("lower(target_entity_id) gin_trgm_ops"),
            postgresql_using="gin",
            postgresql_where=text("target_entity_id IS NOT NULL"),
        ),
        Index(
            "ix_audit_events_reason_trgm",
            text("lower(reason) gin_trgm_ops"),
            postgresql_using="gin",
            postgresql_where=text("reason IS NOT NULL"),
        ),
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


# The ``audit_events`` trigram indexes above need the ``pg_trgm`` extension.
# Declare that dependency on the metadata so any ``create_all`` path (tests)
# provisions the extension BEFORE ``CREATE INDEX``; the paired migration 0023
# does the same via ``op.execute`` for the alembic path. Postgres-only — a no-op
# on any other dialect.
_pg_trgm_ddl = DDL("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # type: ignore[no-untyped-call]
event.listen(
    Base.metadata,
    "before_create",
    _pg_trgm_ddl.execute_if(dialect="postgresql"),
)
