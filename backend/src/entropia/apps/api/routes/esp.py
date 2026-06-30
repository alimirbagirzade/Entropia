"""Embedded System Packages API (doc 09 §8, §10.1). Thin handlers: parse ->
resolve actor -> call one application command/query. No SQL, queue, object-storage
or policy here.

Page access is role-aware rather than fully gated: any authenticated actor may
view/use trusted system resolvers (doc 09 §2 "User"/"Supervisor" rows), so view
permission is enforced in the query layer. Registry mutation (activate/deprecate)
is Admin-only and rejects non-Admins with 403 before touching the domain (CR-02).
The resolve endpoint provides Agent-Gateway parity for Pre-Check (doc 09 §10.3).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, Field

from entropia.application.commands import esp as esp_cmd
from entropia.application.queries import esp as esp_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.lifecycle.enums import VisibilityScope
from entropia.shared.concurrency import etag_for_row_version
from entropia.shared.pagination import PageParams

router = APIRouter(tags=["embedded-system-packages"])

_REGISTRY_VERSION_HEADER = "X-Registry-Version"


def _registry_version(value: str | None) -> int | None:
    """Parse the optimistic-concurrency registry-version token header."""
    if not value:
        return None
    try:
        return int(value.strip().strip('"'))
    except ValueError:
        return None


class CreateEspRequest(BaseModel):
    canonical_key: str
    signature: dict[str, Any]
    runtime_adapter: RuntimeAdapter
    input_contract: dict[str, Any] = Field(default_factory=dict)
    output_contract: dict[str, Any] = Field(default_factory=dict)
    dependency_snapshot: dict[str, Any] | None = None
    warm_up_period: int | None = None
    timing_semantics: str | None = None
    repaint: bool = False
    evidence: dict[str, Any] | None = None
    visibility_scope: VisibilityScope = VisibilityScope.PRIVATE
    change_note: str | None = None


class ActivateRequest(BaseModel):
    revision_id: str
    canonical_key: str
    note: str | None = None


class DeprecateRequest(BaseModel):
    canonical_key: str
    reason: str
    replacement_revision_id: str | None = None


class ResolveRequest(BaseModel):
    parsed_call: dict[str, Any]
    target_runtime: RuntimeAdapter


@router.post("/embedded-system-packages", status_code=201)
async def create_esp(
    body: CreateEspRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await esp_cmd.create_esp_package(
        ctx.session,
        ctx.actor,
        canonical_key=body.canonical_key,
        signature=body.signature,
        runtime_adapter=body.runtime_adapter,
        input_contract=body.input_contract,
        output_contract=body.output_contract,
        dependency_snapshot=body.dependency_snapshot,
        warm_up_period=body.warm_up_period,
        timing_semantics=body.timing_semantics,
        repaint=body.repaint,
        evidence=body.evidence,
        visibility_scope=body.visibility_scope,
        change_note=body.change_note,
    )


@router.get("/embedded-system-packages")
async def list_esp(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    trust_state: ResolverTrustState | None = Query(default=None),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await esp_query.list_embedded_system_packages(
        ctx.session,
        ctx.actor,
        PageParams(cursor=cursor, limit=limit),
        trust_state=trust_state,
    )


@router.get("/embedded-system-packages/{entity_id}")
async def get_esp(
    entity_id: str,
    response: Response,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    detail = await esp_query.get_esp_detail(ctx.session, ctx.actor, entity_id=entity_id)
    response.headers["ETag"] = etag_for_row_version(int(detail["row_version"]))
    return detail


@router.post("/embedded-system-packages/{entity_id}/activate")
async def activate_esp(
    entity_id: str,
    body: ActivateRequest,
    ctx: RequestContext = Depends(request_context),
    registry_version: str | None = Header(default=None, alias=_REGISTRY_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await esp_cmd.activate_resolver(
        ctx.session,
        ctx.actor,
        entity_id=entity_id,
        revision_id=body.revision_id,
        canonical_key=body.canonical_key,
        expected_registry_version=_registry_version(registry_version),
        note=body.note,
        idempotency_key=idempotency_key,
    )


@router.post("/embedded-system-packages/{entity_id}/deprecate")
async def deprecate_esp(
    entity_id: str,
    body: DeprecateRequest,
    ctx: RequestContext = Depends(request_context),
    registry_version: str | None = Header(default=None, alias=_REGISTRY_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await esp_cmd.deprecate_resolver(
        ctx.session,
        ctx.actor,
        canonical_key=body.canonical_key,
        reason=body.reason,
        replacement_revision_id=body.replacement_revision_id,
        expected_registry_version=_registry_version(registry_version),
        idempotency_key=idempotency_key,
    )


@router.post("/embedded-system-packages/resolve")
async def resolve_dependency(
    body: ResolveRequest,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    # Guests are blocked; any authenticated actor (User/Supervisor/Agent) may use
    # trusted system resolvers (doc 09 §2). Pre-Check (2e) calls the query with an
    # already-authenticated actor context.
    require_authenticated(ctx.actor)
    return await esp_query.resolve_embedded_dependency(
        ctx.session,
        parsed_call=body.parsed_call,
        target_runtime=body.target_runtime,
    )
