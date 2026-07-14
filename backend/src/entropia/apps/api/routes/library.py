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


class DerivePackageRequest(BaseModel):
    source_revision_id: str
    name: str
    change_note: str | None = None


class CreateRevisionRequest(BaseModel):
    expected_head_revision_id: str | None = None
    change_note: str | None = None
    input_contract: dict[str, Any] | None = None
    output_contract: dict[str, Any] | None = None
    dependency_snapshot: dict[str, Any] | None = None


class RequestApprovalRequest(BaseModel):
    revision_id: str
    expected_head_revision_id: str | None = None
    note: str | None = None


class ApprovePackageRequest(BaseModel):
    revision_id: str
    expected_head_revision_id: str | None = None
    note: str | None = None


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


@router.post("/library/{entity_id}/derive", status_code=201)
async def derive_package(
    entity_id: str,
    body: DerivePackageRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Any viewer: copy the selected immutable source revision into a NEW root owned
    by the caller (doc 08 §7 "Derive", §8.2). The source is chosen in the body, not
    the path; a fresh ``Idempotency-Key`` guards double-creation. No OCC token — a
    derive creates a new root and cannot race the source head. The source package is
    never mutated; a blank name -> 422 PACKAGE_DERIVE_INVALID."""
    return await pkg_cmd.derive_package(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        source_revision_id=body.source_revision_id,
        name=body.name,
        change_note=body.change_note,
        idempotency_key=idempotency_key,
    )


@router.post("/library/{entity_id}/revisions", status_code=201)
async def create_package_revision(
    entity_id: str,
    body: CreateRevisionRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Owner-or-Admin: append an immutable revision N+1 to an active owned root (doc
    08 §7 "Create Revision", §8.5). OCC is the BODY-form ``expected_head_revision_id``
    (the detail GET returns ``current_revision_id``); a concurrent head move -> 409
    PACKAGE_REVISION_CONFLICT + a fresh ``Idempotency-Key`` guards double-append. A
    non-active / soft-deleted root -> 409 LIFECYCLE_BLOCKED."""
    return await pkg_cmd.create_package_revision(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        expected_head_revision_id=body.expected_head_revision_id,
        change_note=body.change_note,
        input_contract=body.input_contract,
        output_contract=body.output_contract,
        dependency_snapshot=body.dependency_snapshot,
        idempotency_key=idempotency_key,
    )


@router.post("/library/{entity_id}/request-approval")
async def request_package_approval(
    entity_id: str,
    body: RequestApprovalRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Owner-or-Admin: move the validation-PASSED head revision ``DRAFT ->
    APPROVAL_REQUESTED`` (doc 08 §7 "Request approval"). OCC is the BODY-form
    ``expected_head_revision_id`` + a fresh ``Idempotency-Key``; a stale head -> 409
    PACKAGE_REVISION_CONFLICT, a not-passed head -> 409 VALIDATION_REQUIRED."""
    return await pkg_cmd.request_package_approval(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        revision_id=body.revision_id,
        expected_head_revision_id=body.expected_head_revision_id,
        note=body.note,
        idempotency_key=idempotency_key,
    )


@router.post("/library/{entity_id}/approve")
async def approve_package(
    entity_id: str,
    body: ApprovePackageRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Admin-only: approve + publish the requested + PASSED head revision in one
    transaction (CR-02, doc 08 §7 "Approve & Publish"). OCC is the BODY-form
    ``expected_head_revision_id`` + a fresh ``Idempotency-Key``; a non-Admin -> 403
    APPROVAL_REQUIRES_ADMIN, a non-requested / non-passed head -> 409. The UI never
    pre-gates (it never renders 403 as a hidden button); the server re-validates."""
    return await pkg_cmd.approve_and_publish_package(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        revision_id=body.revision_id,
        expected_head_revision_id=body.expected_head_revision_id,
        note=body.note,
        idempotency_key=idempotency_key,
    )
