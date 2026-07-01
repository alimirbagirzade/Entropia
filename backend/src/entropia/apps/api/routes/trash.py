"""Soft-delete + Admin Trash endpoints (M3 §7; Stage 6c doc 20 §7).

Thin handlers: parse body/headers -> one application command/query. Soft delete
stays owner-or-Admin; every Trash surface (list/detail/restore/purge) requires
an authenticated human Admin at the ROUTE and again inside the service
(``require_trash_admin`` — UI hide/disable is never authorization, doc 20 §2).

Purge is a 202: the durable ``jobs`` row is written in the command tx and the
``maintenance`` actor is dispatched after the handler returns (mirrors the
other worker routes).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel

from entropia.application.commands.deletion import (
    request_purge,
    restore_trash_entry,
    soft_delete_entity,
)
from entropia.application.queries.trash import get_trash_entry_detail, list_trash_entries
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity.policy import require_trash_admin
from entropia.infrastructure.queues import enqueue as job_enqueue
from entropia.shared.concurrency import row_version_from_if_match

router = APIRouter(tags=["trash"])

_ENTRIES_PATH = "/trash-entries"
_ENTRY_PATH = "/trash-entries/{trash_entry_id}"
_RESTORE_PATH = "/trash-entries/{trash_entry_id}/restore"
_PURGE_PATH = "/trash-entries/{trash_entry_id}/purge"


class DeleteRequest(BaseModel):
    reason: str | None = None


class RestoreRequest(BaseModel):
    expected_head_revision_id: int | None = None


class PurgeRequest(BaseModel):
    confirmation_phrase: str
    reauth_proof: str
    expected_head_revision_id: int | None = None


def _expected_version(body_value: int | None, if_match: str | None) -> int | None:
    """Body token wins; ``If-Match`` is transport support only (doc 20 §14)."""
    return body_value if body_value is not None else row_version_from_if_match(if_match)


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


@router.get(_ENTRIES_PATH)
async def get_trash_entries(
    q: str | None = Query(default=None),
    object_type: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    require_trash_admin(ctx.actor)
    return await list_trash_entries(
        ctx.session, ctx.actor, q=q, object_type=object_type, cursor=cursor, limit=limit
    )


@router.get(_ENTRY_PATH)
async def get_trash_entry(
    trash_entry_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    require_trash_admin(ctx.actor)
    return await get_trash_entry_detail(ctx.session, ctx.actor, trash_entry_id=trash_entry_id)


@router.post(_RESTORE_PATH)
async def restore(
    trash_entry_id: str,
    body: RestoreRequest | None = None,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    require_trash_admin(ctx.actor)
    payload = body or RestoreRequest()
    return await restore_trash_entry(
        ctx.session,
        ctx.actor,
        trash_entry_id=trash_entry_id,
        expected_head_revision_id=_expected_version(payload.expected_head_revision_id, if_match),
        idempotency_key=idempotency_key,
    )


@router.post(_PURGE_PATH, status_code=202)
async def purge(
    trash_entry_id: str,
    body: PurgeRequest,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    require_trash_admin(ctx.actor)
    result = await request_purge(
        ctx.session,
        ctx.actor,
        trash_entry_id=trash_entry_id,
        confirmation_phrase=body.confirmation_phrase,
        reauth_proof=body.reauth_proof,
        expected_head_revision_id=_expected_version(body.expected_head_revision_id, if_match),
        idempotency_key=idempotency_key,
    )
    _dispatch(result)
    return result


def _dispatch(result: dict[str, Any]) -> None:
    """Dispatch the durable purge actor after the request tx commits (the ``jobs``
    row is already durable; mirrors the other worker routes)."""
    from entropia.apps.worker.actors import run_trash_purge

    job_id = result.get("purge_job_id")
    if job_id:
        job_enqueue.send_job(run_trash_purge, job_id)


__all__ = ["router"]
