"""Create Package + Pre-Check API (docs 06 §7, 07 §8). Thin handlers: parse ->
resolve actor -> call one application command/query. No SQL, queue, object-storage
or policy here.

Page access is role-aware: any authenticated actor may create and operate on their
OWN request and run Pre-Check; approve/publish is Admin-only (CR-02) and is rejected
in the command/policy layer before any mutation. Guests are rejected.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from pydantic import BaseModel, Field

from entropia.application.commands import create_package as cp_cmd
from entropia.application.queries import create_package as cp_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.apps.api.upload import validate_multipart_upload
from entropia.domain.create_package.enums import CreationMode, SourceLanguage
from entropia.domain.esp.enums import RuntimeAdapter
from entropia.shared.errors import ValidationError
from entropia.shared.pagination import PageParams

router = APIRouter(tags=["create-package"])

_REQUEST_VERSION_HEADER = "X-Request-Version"


def _request_version(value: str | None) -> int | None:
    """Parse the optimistic-concurrency request-version header."""
    if not value:
        return None
    try:
        return int(value.strip().strip('"'))
    except ValueError:
        return None


class CreateRequestBody(BaseModel):
    package_type: str
    creation_mode: CreationMode
    target_runtime: RuntimeAdapter = RuntimeAdapter.PYTHON
    request_body: str
    output_contract: dict[str, Any]
    source_language: SourceLanguage | None = None
    other_language_label: str | None = None
    rationale_family_id: str | None = None
    compatible_rationale_family_ids: list[str] = Field(default_factory=list)
    linked_indicator: dict[str, Any] | None = None
    declared_dependencies: list[dict[str, Any]] = Field(default_factory=list)
    # Optional explicit equivalence claim (doc 06 §4.4); when null the server derives
    # it from the creation mode. Never a role field — it only drives the baseline gate.
    equivalence_claim: bool | None = None


class DraftBody(BaseModel):
    expected_candidate_hash: str | None = None


class ApproveBody(BaseModel):
    expected_head_revision_id: str | None = None
    note: str | None = None


def _parse_baseline_metadata(raw: str | None) -> dict[str, Any]:
    """Decode the ``baseline_metadata`` multipart form field (a JSON object string
    carrying provider/symbol/timeframe/range/timezone/settings context). Absent or
    blank -> ``{}``; malformed JSON or a non-object -> 422 (never a silent drop)."""
    if raw is None or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("baseline_metadata is not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValidationError("baseline_metadata must be a JSON object.")
    return parsed


@router.post("/create-package/requests", status_code=201)
async def create_request(
    body: CreateRequestBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await cp_cmd.create_package_request(
        ctx.session,
        ctx.actor,
        package_type=body.package_type,
        creation_mode=body.creation_mode,
        source_language=body.source_language,
        other_language_label=body.other_language_label,
        target_runtime=body.target_runtime,
        request_body=body.request_body,
        output_contract=body.output_contract,
        rationale_family_id=body.rationale_family_id,
        compatible_rationale_family_ids=body.compatible_rationale_family_ids,
        linked_indicator=body.linked_indicator,
        declared_dependencies=body.declared_dependencies,
        equivalence_claim=body.equivalence_claim,
        idempotency_key=idempotency_key,
    )


@router.get("/create-package/requests")
async def list_requests(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await cp_query.list_package_requests(
        ctx.session, ctx.actor, PageParams(cursor=cursor, limit=limit)
    )


@router.get("/create-package/requests/{request_id}")
async def get_request(
    request_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await cp_query.get_package_request(ctx.session, ctx.actor, request_id=request_id)


@router.post("/create-package/requests/{request_id}/pre-check")
async def run_pre_check(
    request_id: str,
    ctx: RequestContext = Depends(request_context),
    request_version: str | None = Header(default=None, alias=_REQUEST_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await cp_cmd.run_precheck(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        expected_request_version=_request_version(request_version),
        idempotency_key=idempotency_key,
    )


@router.post("/create-package/requests/{request_id}/generate-candidate")
async def generate_candidate(
    request_id: str,
    ctx: RequestContext = Depends(request_context),
    request_version: str | None = Header(default=None, alias=_REQUEST_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await cp_cmd.submit_candidate_generation(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        expected_request_version=_request_version(request_version),
        idempotency_key=idempotency_key,
    )


@router.post("/create-package/requests/{request_id}/draft")
async def create_draft(
    request_id: str,
    body: DraftBody | None = None,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    payload = body or DraftBody()
    return await cp_cmd.create_draft_from_candidate(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        expected_candidate_hash=payload.expected_candidate_hash,
        idempotency_key=idempotency_key,
    )


@router.post("/create-package/requests/{request_id}/validate")
async def run_validation(
    request_id: str,
    ctx: RequestContext = Depends(request_context),
    request_version: str | None = Header(default=None, alias=_REQUEST_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await cp_cmd.start_package_validation_run(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        expected_request_version=_request_version(request_version),
        idempotency_key=idempotency_key,
    )


@router.post("/create-package/requests/{request_id}/request-revision")
async def request_revision(
    request_id: str,
    ctx: RequestContext = Depends(request_context),
    request_version: str | None = Header(default=None, alias=_REQUEST_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await cp_cmd.request_package_revision(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        expected_request_version=_request_version(request_version),
        idempotency_key=idempotency_key,
    )


@router.post("/create-package/requests/{request_id}/baseline", status_code=201)
async def upload_baseline(
    request_id: str,
    file: UploadFile = File(...),
    baseline_metadata: str | None = Form(default=None),
    ctx: RequestContext = Depends(request_context),
    request_version: str | None = Header(default=None, alias=_REQUEST_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Real native baseline upload (F-03): the browser transfers the selected
    TradingView baseline CSV as ``multipart/form-data``; the provider/symbol/
    timeframe context rides the ``baseline_metadata`` JSON form field. Size,
    UTF-8 encoding, and CSV schema are validated server-side; the CSV extension
    gate lives in the command (``FILE_TYPE_NOT_ALLOWED``)."""
    upload = await validate_multipart_upload(file, require_csv_schema=True)
    return await cp_cmd.upload_baseline_asset(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        content=upload.content,
        baseline_metadata=_parse_baseline_metadata(baseline_metadata),
        content_type=upload.content_type,
        original_filename=upload.filename,
        expected_request_version=_request_version(request_version),
        idempotency_key=idempotency_key,
    )


@router.post("/create-package/requests/{request_id}/baseline-parse")
async def parse_baseline(
    request_id: str,
    ctx: RequestContext = Depends(request_context),
    request_version: str | None = Header(default=None, alias=_REQUEST_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await cp_cmd.start_baseline_parse(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        expected_request_version=_request_version(request_version),
        idempotency_key=idempotency_key,
    )


@router.post("/create-package/requests/{request_id}/approve")
async def approve_request(
    request_id: str,
    body: ApproveBody | None = None,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    payload = body or ApproveBody()
    return await cp_cmd.approve_and_publish(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        expected_head_revision_id=payload.expected_head_revision_id,
        note=payload.note,
        idempotency_key=idempotency_key,
    )


@router.get("/dependency-scans/{scan_id}")
async def get_scan(
    scan_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await cp_query.get_dependency_scan(ctx.session, ctx.actor, scan_id=scan_id)


@router.get("/validation-runs/{validation_run_id}")
async def get_validation_run(
    validation_run_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await cp_query.get_validation_run(
        ctx.session, ctx.actor, validation_run_id=validation_run_id
    )


@router.get("/baseline-assets/{baseline_asset_id}")
async def get_baseline_asset(
    baseline_asset_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await cp_query.get_baseline_asset(
        ctx.session, ctx.actor, baseline_asset_id=baseline_asset_id
    )
