"""User Manual endpoints (Stage 7a, doc 21 §7).

Thin handlers: parse body/headers -> one application command/query. Published
stream + search are all-role (Admin/Supervisor/User; the Agent uses the Tool
Gateway, not these routes). Every write route re-checks Admin at the ROUTE and
the command re-checks it at the SERVICE (``require_manual_admin`` — UI
hide/disable is never authorization, doc 21 §2). Concurrency: stream mutations
take ``expected_stream_version``; revision replacement takes
``expected_head_revision_id`` (transport: ``If-Match``); every mutation carries
an ``Idempotency-Key`` (doc 21 §7).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from pydantic import BaseModel

from entropia.application.commands.manual import (
    create_manual_document,
    replace_manual_revision,
    restore_manual_document,
    soft_delete_manual_document,
    upload_manual_document,
)
from entropia.application.queries.manual import get_manual_stream, search_manual
from entropia.apps.api.deps import RequestContext, request_context
from entropia.apps.api.upload import validate_multipart_upload
from entropia.domain.identity.policy import require_manual_admin, require_trash_admin

router = APIRouter(tags=["manual"])

_STREAM_PATH = "/manual/stream"
_SEARCH_PATH = "/manual/search"
_DOCUMENTS_PATH = "/admin/manual/documents"
_UPLOAD_PATH = "/admin/manual/documents:upload"
_DOCUMENT_PATH = "/admin/manual/documents/{document_id}"
_REVISIONS_PATH = "/admin/manual/documents/{document_id}/revisions"
_RESTORE_PATH = "/admin/manual/documents/{document_id}:restore"


class CreateDocumentRequest(BaseModel):
    title: str
    content: str
    allow_duplicate: bool = False
    expected_stream_version: int | None = None


class ReplaceRevisionRequest(BaseModel):
    content: str
    title: str | None = None
    expected_head_revision_id: str | None = None


class DeleteDocumentRequest(BaseModel):
    reason: str | None = None
    expected_stream_version: int | None = None


def _expected_revision(body_value: str | None, if_match: str | None) -> str | None:
    """Body token wins; ``If-Match`` transports the same head revision id."""
    if body_value is not None:
        return body_value
    if if_match is None:
        return None
    return if_match.strip().strip('"') or None


@router.get(_STREAM_PATH)
async def stream(
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await get_manual_stream(ctx.session, ctx.actor, cursor=cursor, limit=limit)


@router.get(_SEARCH_PATH)
async def search(
    q: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await search_manual(ctx.session, ctx.actor, q=q, cursor=cursor, limit=limit)


@router.post(_DOCUMENTS_PATH, status_code=201)
async def create_document(
    body: CreateDocumentRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    require_manual_admin(ctx.actor)
    return await create_manual_document(
        ctx.session,
        ctx.actor,
        title=body.title,
        content=body.content,
        allow_duplicate=body.allow_duplicate,
        expected_stream_version=body.expected_stream_version,
        idempotency_key=idempotency_key,
    )


@router.post(_UPLOAD_PATH, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    allow_duplicate: bool = Form(default=False),
    expected_stream_version: int | None = Form(default=None),
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Real native document upload (F-03): the browser transfers the selected
    UTF-8 TXT/MD/HTML file as ``multipart/form-data``. Size and UTF-8 encoding
    are validated server-side; the TXT/MD/HTML extension gate lives in the
    command (``MANUAL_FILE_TYPE_UNSUPPORTED``). The reader-visible title is
    filename-derived unless an explicit override is supplied."""
    require_manual_admin(ctx.actor)
    upload = await validate_multipart_upload(file)
    return await upload_manual_document(
        ctx.session,
        ctx.actor,
        source_filename=upload.filename or "",
        content=upload.text,
        title=title,
        allow_duplicate=allow_duplicate,
        expected_stream_version=expected_stream_version,
        idempotency_key=idempotency_key,
    )


@router.post(_REVISIONS_PATH, status_code=201)
async def replace_revision(
    document_id: str,
    body: ReplaceRevisionRequest,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    require_manual_admin(ctx.actor)
    return await replace_manual_revision(
        ctx.session,
        ctx.actor,
        document_id=document_id,
        content=body.content,
        title=body.title,
        expected_head_revision_id=_expected_revision(body.expected_head_revision_id, if_match),
        idempotency_key=idempotency_key,
    )


@router.delete(_DOCUMENT_PATH)
async def soft_delete_document(
    document_id: str,
    body: DeleteDocumentRequest | None = None,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    require_manual_admin(ctx.actor)
    payload = body or DeleteDocumentRequest()
    return await soft_delete_manual_document(
        ctx.session,
        ctx.actor,
        document_id=document_id,
        reason=payload.reason,
        expected_stream_version=payload.expected_stream_version,
        idempotency_key=idempotency_key,
    )


@router.post(_RESTORE_PATH)
async def restore_document(
    document_id: str,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    require_trash_admin(ctx.actor)
    return await restore_manual_document(
        ctx.session, ctx.actor, document_id=document_id, idempotency_key=idempotency_key
    )


__all__ = ["router"]
