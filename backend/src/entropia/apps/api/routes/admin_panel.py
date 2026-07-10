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

from entropia.application.commands import data_queue as data_queue_cmd
from entropia.application.commands import role_assignment as role_assignment_cmd
from entropia.application.queries import log_projection as log_query
from entropia.application.queries import user_registry as user_registry_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.config import get_settings
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
_DATA_QUEUE_REDELIVER_PATH = "/admin/data-queue/redeliver"


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


# ---------- Operator recovery ----------


@router.post(_DATA_QUEUE_REDELIVER_PATH)
async def redeliver_data_queue(
    ctx: RequestContext = Depends(request_context),
    grace_seconds: int | None = Query(default=None, ge=0),
) -> dict[str, Any]:
    """Operator recovery (INF-03, doc 20 §6): re-dispatch durable ``data``-queue
    jobs still QUEUED past the redeliver grace window. The multi-actor ``data``
    queue is not auto-redelivered by the scheduler — this explicit Admin action
    routes each stuck job back to its actor via the payload ``job_kind``.
    ``grace_seconds`` defaults to the configured window; ``0`` sweeps every QUEUED
    data job."""
    require_admin_panel(ctx.actor)
    window = get_settings().job_redeliver_grace_seconds if grace_seconds is None else grace_seconds
    result = await data_queue_cmd.redeliver_data_queue_jobs(
        ctx.session, ctx.actor, grace_seconds=window
    )
    _dispatch_data_jobs(result["redeliverable"])
    return result


def _dispatch_data_jobs(items: list[dict[str, Any]]) -> None:
    """Send the resolved data actors after the request tx (the durable rows are
    already QUEUED; mirrors the other worker routes). Redelivery is idempotent."""
    from entropia.apps.worker.actors import DATA_ACTOR_BY_KIND
    from entropia.infrastructure.queues import enqueue as job_enqueue

    for item in items:
        actor = DATA_ACTOR_BY_KIND.get(item["job_kind"])
        if actor is not None:
            job_enqueue.send_job(actor, item["job_id"])


__all__ = ["router"]
