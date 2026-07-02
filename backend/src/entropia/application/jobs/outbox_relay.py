"""Transactional-outbox relay + read models (Module 20 §10, Stage 8b).

The outbox row is written in the SAME transaction as its domain mutation (M3);
this module is the consumer side. Two independent consumers exist by design:

- ``relay_unpublished`` — the durable checkpoint run by the scheduler: marks
  events published in batches. Consumer failure never rolls back the producer.
- ``fetch_events_after`` — the LOSS-TOLERANT projection feed the API's SSE hub
  polls (INF-11: SSE is a refresh signal, never a source of truth), keyed by the
  lexically-sortable ULID event id so a per-process cursor needs no extra state.

``outbox_lag_seconds`` feeds the per-process metrics (oldest unpublished age).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.infrastructure.postgres.models.audit import OutboxEvent


def _projection(event: OutboxEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "correlation_id": event.correlation_id,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


async def relay_unpublished(
    session: AsyncSession, *, batch_size: int = 200, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Mark the oldest unpublished batch as published; return their projections.

    ``skip_locked`` keeps concurrent relays (e.g. a second scheduler during a
    deploy overlap) from double-claiming a batch. Does not commit."""
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    events = list((await session.execute(stmt)).scalars().all())
    stamp = now or datetime.now(UTC)
    for event in events:
        event.published_at = stamp
        event.attempts += 1
    return [_projection(event) for event in events]


async def fetch_events_after(
    session: AsyncSession, *, cursor_id: str | None, limit: int = 200
) -> list[dict[str, Any]]:
    """Read-only feed of events newer than ``cursor_id`` (ULID-ordered).

    Independent of ``published_at`` so the SSE hub never races the scheduler's
    checkpoint; a ``None`` cursor means 'from the beginning'."""
    stmt = select(OutboxEvent).order_by(OutboxEvent.id).limit(limit)
    if cursor_id is not None:
        stmt = stmt.where(OutboxEvent.id > cursor_id)
    events = (await session.execute(stmt)).scalars().all()
    return [_projection(event) for event in events]


async def latest_event_id(session: AsyncSession) -> str | None:
    """The current tail of the stream — a boot-time SSE cursor (only NEW events
    stream to a fresh subscriber; history is served by query endpoints)."""
    stmt = select(func.max(OutboxEvent.id))
    return (await session.execute(stmt)).scalar_one_or_none()


async def outbox_lag_seconds(session: AsyncSession, *, now: datetime | None = None) -> float | None:
    """Age of the OLDEST unpublished event (None when fully relayed)."""
    stmt = select(func.min(OutboxEvent.created_at)).where(OutboxEvent.published_at.is_(None))
    oldest = (await session.execute(stmt)).scalar_one_or_none()
    if oldest is None:
        return None
    reference = now or datetime.now(UTC)
    return max(0.0, (reference - oldest).total_seconds())


__all__ = [
    "fetch_events_after",
    "latest_event_id",
    "outbox_lag_seconds",
    "relay_unpublished",
]
