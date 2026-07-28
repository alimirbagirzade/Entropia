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
from entropia.shared.concurrency import reconcile_occ_tokens, row_version_from_if_match

router = APIRouter(tags=["trash"])

_ENTRIES_PATH = "/trash-entries"
_ENTRY_PATH = "/trash-entries/{trash_entry_id}"
_RESTORE_PATH = "/trash-entries/{trash_entry_id}/restore"
_PURGE_PATH = "/trash-entries/{trash_entry_id}/purge"


class DeleteRequest(BaseModel):
    # O-18: the generic soft-delete entry point had NO concurrency token at all, so a
    # racing edit could be deleted out from under its author. Optional to keep the
    # existing (already state-idempotent) callers working; enforced when supplied.
    expected_row_version: int | None = None
    reason: str | None = None


class RestoreRequest(BaseModel):
    expected_head_revision_id: int | None = None


class PurgeRequest(BaseModel):
    confirmation_phrase: str
    reauth_proof: str
    expected_head_revision_id: int | None = None


def _expected_version(
    body_value: int | None, if_match: str | None, *, field: str = "expected_head_revision_id"
) -> int | None:
    """Body token wins; ``If-Match`` is transport support only (doc 20 §14).

    Dual-token rule (O-12): the two spellings must agree — a disagreement is 409
    OCC_TOKEN_CONFLICT, never a silent pick.
    """
    return reconcile_occ_tokens(body_value, row_version_from_if_match(if_match), field=field)


@router.delete("/entities/{entity_id}", status_code=204)
async def soft_delete(
    entity_id: str,
    body: DeleteRequest | None = None,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Response:
    """Generic soft-delete entry point (doc 20 §9.3 ``entity.soft_delete``).

    O-18: this surface previously carried NO concurrency token, so it was the one
    delete path that could silently discard a concurrent edit. It now takes the root
    ``expected_row_version`` in the body or as an ``If-Match`` ``rv-N`` ETag, under
    the same dual-token rule as every other mutation, plus an ``Idempotency-Key`` so
    a retried submit cannot write a second audit trail (doc 20 §14).
    """
    payload = body or DeleteRequest()
    await soft_delete_entity(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        reason=payload.reason,
        expected_row_version=_expected_version(
            payload.expected_row_version, if_match, field="expected_row_version"
        ),
        idempotency_key=idempotency_key,
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
