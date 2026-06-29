"""Durable job table + idempotency keys (Module 20 §6).

The Redis message is only transport; the authoritative job record lives here so a
Redis restart never loses history, and stale-RUNNING recovery is possible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.lifecycle.enums import JobStatus
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_queue_status", "queue", "status"),
        Index("ix_jobs_stale_running", "status", "claimed_at"),
    )

    job_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    queue: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        enum_column(JobStatus, "job_status"), nullable=False, default=JobStatus.QUEUED
    )
    actor_principal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    actor_principal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
