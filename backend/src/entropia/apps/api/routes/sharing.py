"""Explicit package-sharing API (GAP-17; Master Reference §6, §6.4).

Thin handlers over the sharing command/query layer — no SQL, policy or business
logic here. The grant/revoke mutations carry the package root ``row_version`` as
the ``If-Match "rv-N"`` ETag (the ``GET /library/{entity_id}`` detail returns it)
plus a fresh ``Idempotency-Key``, matching the sibling package Move-to-Trash
route. ``GET /library/{entity_id}/shares`` lists the active grantees and is
owner/Admin-only (a grantee never learns who else a resource is shared with).
``GET /library-shared-with-me`` is the grantee's inbox of shared packages (a
distinct literal path so it never shadows ``GET /library/{entity_id}``).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel

from entropia.application.commands import sharing as sharing_cmd
from entropia.application.queries import library as library_query
from entropia.application.queries import sharing as sharing_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.shared.concurrency import etag_for_row_version, row_version_from_if_match
from entropia.shared.pagination import PageParams

router = APIRouter(tags=["package-sharing"])


class SharePackageRequest(BaseModel):
    grantee_email: str


@router.post("/library/{entity_id}/shares", status_code=201)
async def share_package(
    entity_id: str,
    body: SharePackageRequest,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await sharing_cmd.share_package(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        grantee_email=body.grantee_email,
        expected_row_version=row_version_from_if_match(if_match),
        idempotency_key=idempotency_key,
    )


@router.get("/library/{entity_id}/shares")
async def list_package_shares(
    entity_id: str,
    response: Response,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    result = await sharing_query.list_package_shares(ctx.session, ctx.actor, entity_id=entity_id)
    response.headers["ETag"] = etag_for_row_version(int(result["row_version"]))
    return result


@router.delete("/library/{entity_id}/shares/{share_id}")
async def revoke_package_share(
    entity_id: str,
    share_id: str,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await sharing_cmd.revoke_package_share(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        share_id=share_id,
        expected_row_version=row_version_from_if_match(if_match),
        idempotency_key=idempotency_key,
    )


@router.get("/library-shared-with-me")
async def list_shared_with_me(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await library_query.list_shared_with_me(
        ctx.session, ctx.actor, PageParams(cursor=cursor, limit=limit)
    )
