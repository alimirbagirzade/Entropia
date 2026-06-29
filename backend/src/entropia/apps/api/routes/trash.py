"""Soft-delete, Trash, restore and purge endpoints (M3, §7).

Trash view, restore and purge are Admin-only. Soft delete is allowed for the
owner (or Admin). Policy is enforced server-side regardless of UI gating.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel

from entropia.application.commands.deletion import (
    purge_entity,
    restore_entity,
    soft_delete_entity,
)
from entropia.application.queries.trash import list_trash
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity.policy import require_admin
from entropia.shared.pagination import PageParams

router = APIRouter(tags=["trash"])


class DeleteRequest(BaseModel):
    reason: str | None = None


@router.delete("/entities/{entity_id}", status_code=204)
async def soft_delete(
    entity_id: str,
    body: DeleteRequest | None = None,
    ctx: RequestContext = Depends(request_context),
) -> Response:
    await soft_delete_entity(
        ctx.session, ctx.actor, entity_id=entity_id, reason=body.reason if body else None
    )
    return Response(status_code=204)


@router.get("/trash")
async def get_trash(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, object]:
    require_admin(ctx.actor)
    items = await list_trash(ctx.session, PageParams(cursor=cursor, limit=limit))
    return {"data": items, "meta": {"has_more": len(items) == limit}}


@router.post("/trash/{entity_id}/restore", status_code=204)
async def restore(entity_id: str, ctx: RequestContext = Depends(request_context)) -> Response:
    await restore_entity(ctx.session, ctx.actor, entity_id=entity_id)
    return Response(status_code=204)


@router.delete("/trash/{entity_id}/purge", status_code=204)
async def purge(entity_id: str, ctx: RequestContext = Depends(request_context)) -> Response:
    await purge_entity(ctx.session, ctx.actor, entity_id=entity_id)
    return Response(status_code=204)
