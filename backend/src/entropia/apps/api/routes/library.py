"""Package Library catalog API (doc 08 §3, §4, §9.2). Thin GET-only handlers:
parse + validate filters -> resolve actor -> call one read query. No SQL, policy
or business logic here.

The page is authentication-gated (doc 08 §2 "Guest ... katalog döndürülmez"): the
query layer rejects Guests with 401 and applies per-role visibility server-side.
Detail carries an ETag from the root ``row_version`` for optimistic-concurrency
staleness detection on later mutating actions (doc 08 §4.4).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel

from entropia.application.commands import package_lifecycle as pkg_cmd
from entropia.application.queries import library as library_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.package.catalog import parse_catalog_filters
from entropia.shared.concurrency import etag_for_row_version, row_version_from_if_match
from entropia.shared.pagination import PageParams

router = APIRouter(tags=["package-library"])


class DeprecatePackageRequest(BaseModel):
    note: str | None = None


class DeletePackageRequest(BaseModel):
    reason: str | None = None


@router.get("/library")
async def list_library(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    package_type: str | None = Query(default=None, alias="type"),
    lifecycle_state: str | None = Query(default=None),
    validation_state: str | None = Query(default=None),
    approval_state: str | None = Query(default=None),
    visibility_scope: str | None = Query(default=None),
    rationale_family_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    filters = parse_catalog_filters(
        package_type=package_type,
        lifecycle_state=lifecycle_state,
        validation_state=validation_state,
        approval_state=approval_state,
        visibility_scope=visibility_scope,
        rationale_family_id=rationale_family_id,
        query=q,
    )
    return await library_query.list_packages(
        ctx.session,
        ctx.actor,
        PageParams(cursor=cursor, limit=limit),
        filters=filters,
    )


@router.get("/library/{entity_id}")
async def get_library_package(
    entity_id: str,
    response: Response,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    detail = await library_query.get_package_detail(ctx.session, ctx.actor, entity_id=entity_id)
    response.headers["ETag"] = etag_for_row_version(int(detail["row_version"]))
    return detail


@router.post("/library/{entity_id}/deprecate")
async def deprecate_package(
    entity_id: str,
    body: DeprecatePackageRequest | None = None,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    """Owner-or-Admin: ``active -> deprecated`` (doc 08 §7 "Deprecate"). No OCC — a
    deprecate appends no revision, so it cannot race the head (mirrors the sibling
    ``market_data`` deprecate); a non-active/soft-deleted root -> 409 LIFECYCLE_BLOCKED."""
    return await pkg_cmd.deprecate_package(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        note=body.note if body else None,
    )


@router.delete("/library/{entity_id}", status_code=204)
async def soft_delete_package(
    entity_id: str,
    body: DeletePackageRequest | None = None,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> Response:
    """Owner-or-Admin Move to Trash (doc 08 §7, §8.4). OCC token is the root
    ``row_version`` carried as the ``If-Match "rv-N"`` ETag (the detail GET returns
    it); a stale head -> 409, a repeat delete is an idempotent no-op. Restore stays
    the Admin-only Trash surface."""
    await pkg_cmd.soft_delete_package(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        reason=body.reason if body else None,
        expected_row_version=row_version_from_if_match(if_match),
    )
    return Response(status_code=204)
