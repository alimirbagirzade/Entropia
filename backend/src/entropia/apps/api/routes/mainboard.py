"""Mainboard composition-plane API (doc 01 §5, §7, §9). Thin handlers: parse the
body/headers -> resolve actor context -> call one application command/query. No
SQL, policy, hashing, or business logic lives here.

Page access is authentication-gated (the query/commands reject Guests with 401).
Mutating routes read the ``Idempotency-Key`` header; ``patch_mainboard_item``
additionally accepts ``If-Match`` as an alternative carrier of the item's expected
row version. The default-Mainboard GET sets an ``ETag`` from the workspace row
version for later optimistic-concurrency checks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.shared.concurrency import etag_for_row_version, row_version_from_if_match
from entropia.shared.errors import ValidationError

router = APIRouter(tags=["mainboard"])


class CreateWorkObjectBody(BaseModel):
    object_kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    source_provenance: dict[str, Any] | None = None
    available_time: str | None = None


class CreateWorkObjectRevisionBody(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    source_provenance: dict[str, Any] | None = None
    available_time: str | None = None
    expected_head_revision_id: str | None = None


class AttachItemBody(BaseModel):
    root_id: str
    revision_id: str
    item_kind: str | None = None
    position_index: int | None = None


class PatchItemBody(BaseModel):
    intent: str
    expected_row_version: int | None = None
    revision_id: str | None = None
    is_enabled: bool | None = None
    position_index: int | None = None
    display_label_override: str | None = None


def _parse_available_time(value: str | None) -> Any:
    """Parse an ISO-8601 ``available_time`` to a datetime; ``None`` passes through.

    The command layer enforces tz-awareness and the anti-lookahead rule; here we
    only decode the wire value.
    """
    if value is None:
        return None
    return datetime.fromisoformat(value)


@router.get("/mainboards/default")
async def get_default_mainboard(
    response: Response,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    result = await mb_query.get_default_mainboard(ctx.session, ctx.actor)
    response.headers["ETag"] = etag_for_row_version(int(result["row_version"]))
    return result


# NOTE: ``POST /strategy-drafts`` moved to the Strategy Details router (Stage 3b)
# where it creates a PERSISTED draft + root instead of a transient opener. The 3a
# transient ``mb_cmd.start_strategy_draft`` remains available as a command but is
# no longer routed here (superseded by real persistence, doc 02 §7).


@router.post("/external-work-object-drafts/{kind}")
async def start_external_work_object_draft(
    kind: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return mb_cmd.start_external_work_object_draft(ctx.actor, kind)


@router.post("/work-objects", status_code=201)
async def create_work_object(
    body: CreateWorkObjectBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await mb_cmd.create_work_object(
        ctx.session,
        ctx.actor,
        object_kind=body.object_kind,
        payload=body.payload,
        source_provenance=body.source_provenance,
        available_time=_parse_available_time(body.available_time),
        idempotency_key=idempotency_key,
    )


@router.post("/work-objects/{root_id}/revisions", status_code=201)
async def create_work_object_revision(
    root_id: str,
    body: CreateWorkObjectRevisionBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await mb_cmd.create_work_object_revision(
        ctx.session,
        ctx.actor,
        root_id=root_id,
        payload=body.payload,
        source_provenance=body.source_provenance,
        available_time=_parse_available_time(body.available_time),
        expected_head_revision_id=body.expected_head_revision_id,
        idempotency_key=idempotency_key,
    )


@router.post("/mainboards/{workspace_id}/items", status_code=201)
async def attach_mainboard_item(
    workspace_id: str,
    body: AttachItemBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await mb_cmd.attach_mainboard_item(
        ctx.session,
        ctx.actor,
        workspace_id=workspace_id,
        root_id=body.root_id,
        revision_id=body.revision_id,
        item_kind=body.item_kind,
        position_index=body.position_index,
        idempotency_key=idempotency_key,
    )


@router.patch("/mainboard-items/{item_id}")
async def patch_mainboard_item(
    item_id: str,
    body: PatchItemBody,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    expected_row_version = body.expected_row_version
    if expected_row_version is None:
        expected_row_version = row_version_from_if_match(if_match)
    if expected_row_version is None:
        raise ValidationError(
            "expected_row_version (body) or If-Match header is required.",
            details=[{"field": "expected_row_version"}],
        )
    return await mb_cmd.patch_mainboard_item(
        ctx.session,
        ctx.actor,
        item_id=item_id,
        intent=body.intent,
        expected_row_version=expected_row_version,
        revision_id=body.revision_id,
        is_enabled=body.is_enabled,
        position_index=body.position_index,
        display_label_override=body.display_label_override,
        idempotency_key=idempotency_key,
    )


@router.post("/mainboards/{workspace_id}/snapshots", status_code=201)
async def create_composition_snapshot(
    workspace_id: str,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await mb_cmd.create_composition_snapshot(
        ctx.session,
        ctx.actor,
        workspace_id=workspace_id,
        idempotency_key=idempotency_key,
    )


@router.delete("/work-objects/{root_id}")
async def soft_delete_work_object(
    root_id: str,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await mb_cmd.soft_delete_work_object(
        ctx.session,
        ctx.actor,
        root_id=root_id,
        idempotency_key=idempotency_key,
    )
