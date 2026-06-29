"""Audit + transactional outbox data access (M3, §8)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import ActorKind
from entropia.infrastructure.postgres.models import AuditEvent, OutboxEvent
from entropia.shared.ids import new_id


def add_audit_event(
    session: AsyncSession,
    *,
    event_kind: str,
    actor_principal_id: str | None,
    actor_kind: ActorKind,
    target_entity_id: str | None = None,
    target_entity_type: str | None = None,
    target_revision_id: str | None = None,
    previous_state: str | None = None,
    new_state: str | None = None,
    correlation_id: str | None = None,
    reason: str | None = None,
    severity: str = "info",
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_id=new_id("evt"),
        event_kind=event_kind,
        severity=severity,
        actor_principal_id=actor_principal_id,
        actor_kind=actor_kind,
        target_entity_id=target_entity_id,
        target_entity_type=target_entity_type,
        target_revision_id=target_revision_id,
        previous_state=previous_state,
        new_state=new_state,
        correlation_id=correlation_id,
        reason=reason,
        event_metadata=metadata,
    )
    session.add(event)
    return event


def add_outbox_event(
    session: AsyncSession,
    *,
    event_type: str,
    resource_type: str | None,
    resource_id: str | None,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> OutboxEvent:
    event = OutboxEvent(
        id=new_id("obx"),
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
        correlation_id=correlation_id,
    )
    session.add(event)
    return event


async def query_audit_events(
    session: AsyncSession, *, limit: int, before_event_id: str | None = None
) -> Sequence[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.occurred_at.desc(), AuditEvent.event_id.desc())
    if before_event_id is not None:
        stmt = stmt.where(AuditEvent.event_id < before_event_id)
    stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars().all())
