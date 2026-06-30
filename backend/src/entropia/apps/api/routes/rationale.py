"""Rationale Families API (doc 10 §7, §8). Thin handlers: parse -> resolve actor
-> call one application command/query. No SQL, policy or business logic here.

Authorization is the shared-editing exception enforced in the application layer
(``ensure_can_manage_families`` / ``ensure_can_edit_assignments``): any
authenticated actor may manage families + edit assignments; Guests are rejected
with AUTHENTICATION_REQUIRED before any data is returned. Restore/purge are NOT
exposed here — they stay on the Admin-only Trash surface.

Optimistic concurrency is carried by ``If-Match``/``ETag`` (family row_version /
head revision) and the assignment ``expected_table_version`` body field, mirrored
back so the UI can recover from a stale-conflict (409).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, Field

from entropia.application.commands import rationale as rationale_cmd
from entropia.application.queries import rationale as rationale_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.shared.concurrency import etag_for_row_version, row_version_from_if_match
from entropia.shared.pagination import PageParams

router = APIRouter(tags=["rationale-families"])


class CreateFamilyRequest(BaseModel):
    display_name: str
    subfamilies: list[str] = Field(default_factory=list)
    compatible_output_types: list[str] = Field(default_factory=list)
    change_note: str | None = None


class ReviseFamilyRequest(BaseModel):
    display_name: str
    subfamilies: list[str] = Field(default_factory=list)
    compatible_output_types: list[str] = Field(default_factory=list)
    change_note: str | None = None
    expected_head_revision_id: str | None = None


class AssignmentChangeRequest(BaseModel):
    package_root_id: str
    expected_head_revision_id: str | None = None
    rationale_family_id: str | None = None
    expected_family_current_revision_id: str | None = None


class BatchAssignmentRequest(BaseModel):
    changes: list[AssignmentChangeRequest]
    expected_table_version: str | None = None


@router.get("/rationale-families")
async def list_families(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    state: str = Query(default="active"),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await rationale_query.list_families(
        ctx.session, ctx.actor, PageParams(cursor=cursor, limit=limit), state=state
    )


@router.post("/rationale-families", status_code=201)
async def create_family(
    body: CreateFamilyRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await rationale_cmd.create_family(
        ctx.session,
        ctx.actor,
        display_name=body.display_name,
        subfamilies=body.subfamilies,
        compatible_output_types=body.compatible_output_types,
        change_note=body.change_note,
        idempotency_key=idempotency_key,
    )


@router.get("/rationale-families/{entity_id}")
async def get_family(
    entity_id: str,
    response: Response,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    detail = await rationale_query.get_family(ctx.session, ctx.actor, entity_id=entity_id)
    response.headers["ETag"] = etag_for_row_version(int(detail["row_version"]))
    return detail


@router.post("/rationale-families/{entity_id}/revisions")
async def revise_family(
    entity_id: str,
    body: ReviseFamilyRequest,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    # If-Match carries the row_version ETag; the body may also pin the head
    # revision. The command treats a non-null expected_head_revision_id as the
    # concurrency token (doc 10 §5 Save row).
    return await rationale_cmd.revise_family(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        display_name=body.display_name,
        subfamilies=body.subfamilies,
        compatible_output_types=body.compatible_output_types,
        change_note=body.change_note,
        expected_head_revision_id=body.expected_head_revision_id,
        idempotency_key=idempotency_key,
    )


@router.delete("/rationale-families/{entity_id}")
async def soft_delete_family(
    entity_id: str,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict[str, Any]:
    return await rationale_cmd.soft_delete_family(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        expected_row_version=row_version_from_if_match(if_match),
    )


@router.get("/package-rationale-assignments")
async def list_assignments(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await rationale_query.list_package_assignments(
        ctx.session, ctx.actor, PageParams(cursor=cursor, limit=limit)
    )


@router.post("/package-rationale-assignments:batch")
async def batch_assign(
    body: BatchAssignmentRequest,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    changes: Sequence[rationale_cmd.AssignmentChange] = [
        rationale_cmd.AssignmentChange(
            package_root_id=c.package_root_id,
            expected_head_revision_id=c.expected_head_revision_id,
            rationale_family_id=c.rationale_family_id,
            expected_family_current_revision_id=c.expected_family_current_revision_id,
        )
        for c in body.changes
    ]
    return await rationale_cmd.batch_assign_rationale(
        ctx.session,
        ctx.actor,
        changes=changes,
        expected_table_version=body.expected_table_version,
        idempotency_key=idempotency_key,
    )
