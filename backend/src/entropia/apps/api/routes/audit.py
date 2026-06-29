"""Audit event log endpoint — Admin-only (M3, §8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from entropia.application.queries.audit_log import list_audit_events
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity.policy import require_admin
from entropia.shared.pagination import PageParams

router = APIRouter(tags=["audit"])


@router.get("/audit-events")
async def audit_events(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, object]:
    require_admin(ctx.actor)
    data, next_cursor = await list_audit_events(ctx.session, PageParams(cursor=cursor, limit=limit))
    return {"data": data, "meta": {"cursor": next_cursor, "has_more": next_cursor is not None}}
