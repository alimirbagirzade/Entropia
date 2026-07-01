"""Backtest Ready Check API (doc 14 §7, §9). Thin handlers: parse body/headers ->
resolve actor context -> call one application command/query. No SQL, policy,
hashing or validation logic lives here.

``POST .../readiness-checks`` always produces a NEW immutable report (rerun = new
id, doc 14 §9.1); an optional ``expected_fingerprint`` (body or ``If-Match``) makes
the check conditional on the composition being unchanged (mismatch => 409, RC-09).
The RUN-admission endpoint (``POST /backtest-runs``) is a later stage and is not
exposed here (doc 14 §9.3 scope boundary).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.queries import readiness_check as readiness_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.shared.concurrency import row_version_from_if_match

router = APIRouter(tags=["backtest-ready-check"])

_CHECKS_PATH = "/mainboard-compositions/{composition_id}/readiness-checks"
_CURRENT_PATH = "/mainboard-compositions/{composition_id}/readiness"
_REPORT_PATH = "/readiness-reports/{report_id}"


class ReadinessCheckBody(BaseModel):
    expected_fingerprint: str | None = None


def _resolve_expected(body_value: str | None, if_match: str | None) -> str | None:
    if body_value is not None:
        return body_value
    if if_match is None:
        return None
    # If-Match may carry a quoted fingerprint; reuse the shared unwrap where numeric,
    # else strip surrounding quotes so a fingerprint token round-trips.
    numeric = row_version_from_if_match(if_match)
    if numeric is not None:
        return str(numeric)
    return if_match.strip().strip('"')


@router.post(_CHECKS_PATH, status_code=201)
async def run_readiness_check(
    composition_id: str,
    body: ReadinessCheckBody | None = None,
    ctx: RequestContext = Depends(request_context),
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    payload = body or ReadinessCheckBody()
    return await readiness_cmd.run_readiness_check(
        ctx.session,
        ctx.actor,
        composition_id=composition_id,
        expected_fingerprint=_resolve_expected(payload.expected_fingerprint, if_match),
        idempotency_key=idempotency_key,
    )


@router.get(_CURRENT_PATH)
async def get_current_readiness(
    composition_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await readiness_query.get_current_readiness(
        ctx.session, ctx.actor, composition_id=composition_id
    )


@router.get(_REPORT_PATH)
async def get_readiness_report(
    report_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await readiness_query.get_readiness_report(ctx.session, ctx.actor, report_id=report_id)
