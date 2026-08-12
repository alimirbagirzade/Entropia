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
from entropia.infrastructure.queues import enqueue as job_enqueue
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


class PrecheckAcceptedResponse(BaseModel):
    """Pre-Check admission body — doc 07 §10.3 names this response ``202 accepted``.

    Nothing here is a Pre-Check RESULT: the scan does not exist yet. ``scan_id`` /
    ``attempt_no`` / ``resolved`` / ``missing`` / ``warnings`` / ``registry_fingerprint``
    are the command's deliberate placeholders (see ``cp_cmd.run_precheck``) that keep the
    body assignable to the client's ``PrecheckActionResult`` while the worker is still
    running — never a synthesized PASSED/BLOCKED. Declaring the model is what puts the
    shape into ``docs/openapi.json``; a bare ``dict`` kept the drift guard green while
    the contract stayed invisible (O-30).
    """

    request_id: str
    job_id: str
    status: str
    state: str
    scan_id: str
    attempt_no: int
    resolved: int
    missing: list[Any]
    warnings: list[Any]
    registry_fingerprint: str
    request_version: int


class CandidateAcceptedResponse(BaseModel):
    """Candidate-generation admission body — Master Technical Reference §7.1 spells this
    wire contract out literally (``-> 202 Accepted`` carrying the job id and the
    ``CANDIDATE_GENERATING`` state) and doc 07 §10.3 repeats the status.

    ``candidate_hash`` is empty ON PURPOSE: no candidate exists at admission, and an
    empty hash makes it impossible to chain a draft against one the worker has not
    produced yet (see ``cp_cmd.submit_candidate_generation``).
    """

    request_id: str
    state: str
    candidate_hash: str
    job_id: str
    request_version: int


class ValidationRunAcceptedResponse(BaseModel):
    """Validation-run admission body — ``202`` by PRODUCT-OWNER DECISION (2026-08-12).

    ADJUDICATION (RC P8-B2 / readiness §6.7.9). The conflict: this endpoint is a durable
    admission exactly like pre-check / generate-candidate — it appends the ``queued`` run
    row, enqueues a job and returns before any verdict exists — but canonical never names
    a status for it. doc 06 §7 describes only the behaviour ("returns validation_run_id;
    rows show queued/running"), doc 08 §7 lists the endpoint without a code, and MTR §13
    mandates only that long validate work leaves the request. Two readings were open:
    (a) keep the shipped ``200``, because inventing a wire contract in a canonical gap is
    what this project refuses to do; (b) align to the shipped durable-admission pattern,
    because ``200`` advertises a completed result this response does not carry. The PO
    chose (b) on 2026-08-12. Canonical does NOT say 202 here — the decision does, and the
    reason it is recorded rather than absorbed is that a later reader must not "fix" it
    back by pattern-matching. Pinned by ``test_p8b2_admission_status.py``.

    Nothing here is a validation RESULT: ``checks`` is empty at admission (the seven
    mandatory checks land when ``jobs.create_package.run_validation_job`` completes) and
    ``status`` is the run row's own ``queued``. Declaring the model is what puts the shape
    into ``docs/openapi.json``; a bare ``dict`` kept the drift guard green while the
    contract stayed invisible (O-30).
    """

    request_id: str
    validation_run_id: str
    attempt_no: int
    status: str
    state: str
    checks: list[Any]
    job_id: str
    request_version: int


class BaselineParseAcceptedResponse(BaseModel):
    """Baseline-parse admission body — ``202`` by PRODUCT-OWNER DECISION (2026-08-12).

    ADJUDICATION (RC P8-B2 / readiness §6.7.9), the same decision as
    ``ValidationRunAcceptedResponse`` and with one gap MORE: canonical does not merely
    omit a status here, it does not name the ENDPOINT. doc 06 §7 has a single baseline
    surface ("asset upload and parse are async") and MTR §10.2 lists only
    ``POST /package-revisions/{id}/baseline-assets``, so splitting upload (201) from parse
    is a shipped decomposition with nothing to align TO. The PO chose the durable-admission
    ``202`` on 2026-08-12 for both endpoints together. Pinned by
    ``test_p8b2_admission_status.py``.

    ``parser_version`` and ``parse_report`` are the command's deliberate placeholders (see
    ``cp_cmd.start_baseline_parse``): no parse evidence exists at admission, and empty
    values keep the body assignable to the client's ``BaselineParseResult`` while making
    it impossible to render a parser version or a row count the worker has not produced.
    """

    request_id: str
    baseline_asset_id: str
    attempt_no: int
    parse_status: str
    parser_version: str
    parse_report: dict[str, Any]
    job_id: str
    request_version: int


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


def dispatch_create_package_job(job_id: str) -> None:
    """Dispatch the durable ``default``-queue Create-Package worker (F-01a/F-01b).

    The QUEUED ``jobs`` row written by the admission is already the source of truth, so a
    lost broker message costs latency, not work: the scheduler sweep re-sends it
    (INF-03). Called AFTER the admission returns, so the actor only ever sees a committed
    job row.
    """
    from entropia.apps.worker.actors import run_create_package_job

    job_enqueue.send_job(run_create_package_job, job_id)


@router.post(
    "/create-package/requests/{request_id}/pre-check",
    response_model=PrecheckAcceptedResponse,
    status_code=202,
)
async def run_pre_check(
    request_id: str,
    ctx: RequestContext = Depends(request_context),
    request_version: str | None = Header(default=None, alias=_REQUEST_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    result = await cp_cmd.run_precheck(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        expected_request_version=_request_version(request_version),
        idempotency_key=idempotency_key,
    )
    dispatch_create_package_job(result["job_id"])
    return result


@router.post(
    "/create-package/requests/{request_id}/generate-candidate",
    response_model=CandidateAcceptedResponse,
    status_code=202,
)
async def generate_candidate(
    request_id: str,
    ctx: RequestContext = Depends(request_context),
    request_version: str | None = Header(default=None, alias=_REQUEST_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    result = await cp_cmd.submit_candidate_generation(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        expected_request_version=_request_version(request_version),
        idempotency_key=idempotency_key,
    )
    dispatch_create_package_job(result["job_id"])
    return result


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


@router.post(
    "/create-package/requests/{request_id}/validate",
    response_model=ValidationRunAcceptedResponse,
    status_code=202,
)
async def run_validation(
    request_id: str,
    ctx: RequestContext = Depends(request_context),
    request_version: str | None = Header(default=None, alias=_REQUEST_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Admit a Validation Tests run: writes a durable QUEUED job and returns before the
    verdict exists, so the four Create-Package admissions now agree on ``202``.

    The status is a PO DECISION of 2026-08-12, not a canonical alignment — canonical
    names no status for this endpoint. The full adjudication (what conflicted, the two
    readings, who chose and why) lives on ``ValidationRunAcceptedResponse``; do not
    re-derive it from the sibling routes. ``test_p8b2_admission_status.py`` pins it.
    """
    result = await cp_cmd.start_package_validation_run(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        expected_request_version=_request_version(request_version),
        idempotency_key=idempotency_key,
    )
    dispatch_create_package_job(result["job_id"])
    return result


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


@router.post(
    "/create-package/requests/{request_id}/baseline-parse",
    response_model=BaselineParseAcceptedResponse,
    status_code=202,
)
async def parse_baseline(
    request_id: str,
    ctx: RequestContext = Depends(request_context),
    request_version: str | None = Header(default=None, alias=_REQUEST_VERSION_HEADER),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Admit the head baseline's parse (F-01c). Returns ``parsing`` immediately; the
    stored CSV is read and the terminal passed/failed status written by the durable
    ``default``-queue worker, so closing the tab never cancels it.

    ``202`` is a PO DECISION of 2026-08-12, not a canonical alignment — canonical does
    not even name this endpoint. The full adjudication lives on
    ``BaselineParseAcceptedResponse``. ``test_p8b2_admission_status.py`` pins it.
    """
    result = await cp_cmd.start_baseline_parse(
        ctx.session,
        ctx.actor,
        request_id=request_id,
        expected_request_version=_request_version(request_version),
        idempotency_key=idempotency_key,
    )
    dispatch_create_package_job(result["job_id"])
    return result


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
