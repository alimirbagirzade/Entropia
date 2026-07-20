"""Strategy Details API (doc 02 §7, §8, §9). Thin handlers: parse the
body/headers -> resolve actor context -> call one application command/query. No
SQL, policy, hashing, or business logic lives here.

Page access is authentication-gated (create + queries reject Guests with 401;
edit/save on another owner's strategy is 403 EDIT_FORBIDDEN). Mutating routes read
``Idempotency-Key``; draft-mutating routes accept the draft's expected row version
in the body or via ``If-Match``. Typed ``AppError``s raised by the command/query
layer are rendered by the global exception handler as the canonical error envelope.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from entropia.application.commands import strategy_draft as strat_cmd
from entropia.application.queries import strategy as strat_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.shared.concurrency import row_version_from_if_match
from entropia.shared.errors import ValidationError

router = APIRouter(tags=["strategy"])


class CreateStrategyDraftBody(BaseModel):
    display_name: str | None = None
    rationale_family_id: str | None = None
    initial_payload: dict[str, Any] | None = None
    # GAP-03 (doc 01 §8.2, §9.5): when present, the draft is DERIVED from a usable
    # Strategy Package instead of created blank — the source is pinned and provenance
    # is recorded. source_package_revision_id is optional (defaults to the head).
    source_package_root_id: str | None = None
    source_package_revision_id: str | None = None


class SetRationaleFamilyBody(BaseModel):
    rationale_family_id: str


class PatchStrategyDraftBody(BaseModel):
    payload: dict[str, Any] | None = None
    patch: dict[str, Any] | None = None
    expected_draft_row_version: int | None = None


class SaveStrategyDraftBody(BaseModel):
    expected_draft_row_version: int | None = None


class ClearStrategyDraftBody(BaseModel):
    expected_draft_row_version: int | None = None


def _resolve_expected_version(explicit: int | None, if_match: str | None) -> int:
    expected = explicit if explicit is not None else row_version_from_if_match(if_match)
    if expected is None:
        raise ValidationError(
            "expected_draft_row_version (body) or If-Match header is required.",
            details=[{"field": "expected_draft_row_version"}],
        )
    return expected


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #


@router.post("/strategy-drafts", status_code=201)
async def create_strategy_draft(
    body: CreateStrategyDraftBody | None = None,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    payload = body or CreateStrategyDraftBody()
    if payload.source_package_root_id is not None:
        return await strat_cmd.derive_strategy_draft_from_package(
            ctx.session,
            ctx.actor,
            source_package_root_id=payload.source_package_root_id,
            source_package_revision_id=payload.source_package_revision_id,
            display_name=payload.display_name,
            rationale_family_id=payload.rationale_family_id,
            idempotency_key=idempotency_key,
        )
    return await strat_cmd.create_strategy_draft(
        ctx.session,
        ctx.actor,
        display_name=payload.display_name or "",
        rationale_family_id=payload.rationale_family_id,
        initial_payload=payload.initial_payload,
        idempotency_key=idempotency_key,
    )


@router.post("/strategies/{root_id}/rationale-family")
async def set_strategy_rationale_family(
    root_id: str,
    body: SetRationaleFamilyBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """One-time set of a NULL rationale family (R2-07 gap). No OCC token — the
    NULL→set transition is itself the guard (already-set → 409)."""
    return await strat_cmd.set_strategy_rationale_family(
        ctx.session,
        ctx.actor,
        strategy_root_id=root_id,
        rationale_family_id=body.rationale_family_id,
        idempotency_key=idempotency_key,
    )


@router.patch("/strategy-drafts/{draft_id}")
async def patch_strategy_draft(
    draft_id: str,
    body: PatchStrategyDraftBody,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    expected = _resolve_expected_version(body.expected_draft_row_version, if_match)
    return await strat_cmd.patch_strategy_draft(
        ctx.session,
        ctx.actor,
        draft_id=draft_id,
        expected_draft_row_version=expected,
        payload=body.payload,
        patch=body.patch,
        idempotency_key=idempotency_key,
    )


@router.post("/strategy-drafts/{draft_id}/validate")
async def validate_strategy_draft(
    draft_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await strat_cmd.validate_strategy_draft(ctx.session, ctx.actor, draft_id=draft_id)


@router.post("/strategy-drafts/{draft_id}/save", status_code=201)
async def save_strategy_revision(
    draft_id: str,
    body: SaveStrategyDraftBody,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    expected = _resolve_expected_version(body.expected_draft_row_version, if_match)
    return await strat_cmd.save_strategy_revision(
        ctx.session,
        ctx.actor,
        draft_id=draft_id,
        expected_draft_row_version=expected,
        idempotency_key=idempotency_key,
    )


@router.post("/strategy-drafts/{draft_id}/clear")
async def clear_strategy_draft(
    draft_id: str,
    body: ClearStrategyDraftBody,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    expected = _resolve_expected_version(body.expected_draft_row_version, if_match)
    return await strat_cmd.clear_strategy_draft(
        ctx.session,
        ctx.actor,
        draft_id=draft_id,
        expected_draft_row_version=expected,
        idempotency_key=idempotency_key,
    )


# --------------------------------------------------------------------------- #
# Queries                                                                     #
# --------------------------------------------------------------------------- #


@router.get("/strategy-drafts")
async def list_strategy_drafts(
    ctx: RequestContext = Depends(request_context),
) -> list[dict[str, Any]]:
    return await strat_query.list_strategy_drafts(ctx.session, ctx.actor)


@router.get("/strategy-drafts/{draft_id}")
async def get_strategy_draft(
    draft_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await strat_query.get_strategy_draft(ctx.session, ctx.actor, draft_id)


@router.get("/strategies/{root_id}")
async def get_strategy(
    root_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await strat_query.get_strategy(ctx.session, ctx.actor, root_id)


@router.get("/strategies/{root_id}/revisions")
async def list_strategy_revisions(
    root_id: str,
    ctx: RequestContext = Depends(request_context),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return await strat_query.list_strategy_revisions(ctx.session, ctx.actor, root_id, limit=limit)


@router.get("/strategy-revisions/{revision_id}")
async def get_strategy_revision(
    revision_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await strat_query.get_strategy_revision(ctx.session, ctx.actor, revision_id)
