"""Admin Panel API — Management + Logs (doc 19 §8). Thin handlers: parse
body/query/headers -> require_admin_panel (fast 403) -> one command/query which
ALSO re-checks the Admin guard. A hidden menu item is never authorization; every
endpoint here is server-guarded for authenticated human Admins only (doc 19 §2, §13).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from entropia.application.commands import role_assignment as role_assignment_cmd
from entropia.application.queries import log_projection as log_query
from entropia.application.queries import user_registry as user_registry_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity.policy import require_admin_panel
from entropia.domain.lifecycle.enums import Role
from entropia.shared.errors import ValidationError

router = APIRouter(tags=["admin-panel"])

_USERS_PATH = "/admin/users"
_USER_ROLE_PATH = "/admin/users/{user_id}/role"
_SYSTEM_ACTORS_PATH = "/admin/system-actors"
_ROLE_MATRIX_PATH = "/admin/role-matrix"
_LOGS_PATH = "/admin/logs"
_LOG_DETAIL_PATH = "/admin/logs/{event_id}"


class AssignRoleBody(BaseModel):
    target_role: Role
    expected_head_revision_id: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=512)


def _parse_if_match(if_match: str | None) -> int | None:
    """Parse an ``If-Match`` ETag into an expected user version (``None`` if absent).
    A present-but-non-integer header is a client error (422)."""
    if if_match is None:
        return None
    token = if_match.strip().strip('"')
    if not token:
        return None
    try:
        return int(token)
    except ValueError as exc:
        raise ValidationError("If-Match must be an integer user version.") from exc


def _parse_dt(value: str | None, *, field: str) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"'{field}' must be an ISO-8601 UTC timestamp.") from exc


# ---------- Management ----------


@router.get(_USERS_PATH)
async def list_users(
    ctx: RequestContext = Depends(request_context),
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None),
) -> dict[str, Any]:
    require_admin_panel(ctx.actor)
    return await user_registry_query.list_registered_users(
        ctx.session, ctx.actor, cursor=cursor, limit=limit
    )


@router.patch(_USER_ROLE_PATH)
async def assign_role(
    user_id: str,
    body: AssignRoleBody,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    require_admin_panel(ctx.actor)
    if_match_version = _parse_if_match(if_match)
    if if_match_version is not None and if_match_version != body.expected_head_revision_id:
        raise ValidationError("If-Match must equal expected_head_revision_id.")
    return await role_assignment_cmd.assign_user_role(
        ctx.session,
        ctx.actor,
        target_user_id=user_id,
        target_role=body.target_role,
        expected_head_revision_id=body.expected_head_revision_id,
        reason=body.reason,
        idempotency_key=idempotency_key,
    )


@router.get(_SYSTEM_ACTORS_PATH)
async def list_system_actors(ctx: RequestContext = Depends(request_context)) -> dict[str, Any]:
    require_admin_panel(ctx.actor)
    return await user_registry_query.list_system_actors(ctx.session, ctx.actor)


@router.get(_ROLE_MATRIX_PATH)
async def role_matrix(ctx: RequestContext = Depends(request_context)) -> dict[str, Any]:
    require_admin_panel(ctx.actor)
    return await user_registry_query.get_role_matrix(ctx.session, ctx.actor)


# ---------- Logs ----------


@router.get(_LOGS_PATH)
async def list_logs(
    ctx: RequestContext = Depends(request_context),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    family: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    actor_type: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None),
) -> dict[str, Any]:
    require_admin_panel(ctx.actor)
    from_at = _parse_dt(from_, field="from")
    to_at = _parse_dt(to, field="to")
    if from_at is not None and to_at is not None and from_at > to_at:
        raise ValidationError("'from' must be earlier than or equal to 'to'.")
    return await log_query.list_log_events(
        ctx.session,
        ctx.actor,
        from_at=from_at,
        to_at=to_at,
        family=family,
        severity=severity,
        actor_type=actor_type,
        actor_id=actor_id,
        resource_type=resource_type,
        correlation_id=correlation_id,
        query_text=q,
        cursor=cursor,
        limit=limit,
    )


@router.get(_LOG_DETAIL_PATH)
async def get_log(event_id: str, ctx: RequestContext = Depends(request_context)) -> dict[str, Any]:
    require_admin_panel(ctx.actor)
    return await log_query.get_log_event(ctx.session, ctx.actor, event_id=event_id)


__all__ = ["router"]
