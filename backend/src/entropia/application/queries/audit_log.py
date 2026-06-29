"""Audit log read model — cursor-paginated, Admin-only at the route (M3, §8)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.shared.pagination import PageParams


async def list_audit_events(
    session: AsyncSession, params: PageParams
) -> tuple[list[dict[str, Any]], str | None]:
    rows = await audit_repo.query_audit_events(
        session, limit=params.limit + 1, before_event_id=params.cursor
    )
    has_more = len(rows) > params.limit
    page = rows[: params.limit]
    next_cursor = page[-1].event_id if has_more and page else None
    data = [
        {
            "event_id": r.event_id,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "event_kind": r.event_kind,
            "severity": r.severity,
            "actor_principal_id": r.actor_principal_id,
            "actor_kind": str(r.actor_kind),
            "target_entity_id": r.target_entity_id,
            "target_entity_type": r.target_entity_type,
            "previous_state": r.previous_state,
            "new_state": r.new_state,
            "correlation_id": r.correlation_id,
        }
        for r in page
    ]
    return data, next_cursor
