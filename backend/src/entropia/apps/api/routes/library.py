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

from fastapi import APIRouter, Depends, Query, Response

from entropia.application.queries import library as library_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.package.catalog import parse_catalog_filters
from entropia.shared.concurrency import etag_for_row_version
from entropia.shared.pagination import PageParams

router = APIRouter(tags=["package-library"])


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
