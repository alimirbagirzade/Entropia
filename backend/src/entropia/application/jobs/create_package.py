"""Create-Package worker bodies — Pre-Check, candidate generation, validation, baseline
parse (docs 06 §5/§7/§8.3, 07 §8; F-01a + F-01b + F-01c).

Runs on the ``default`` queue. The durable ``jobs`` row is the source of truth (CR-09):
the request that admitted the work has long since returned its ``queued`` admission, so a
browser close / logout never cancels it (Finding F-01). The single
``run_create_package_job`` body reads the durable payload ``kind`` and routes to the
matching worker: ``precheck`` (F-01a), ``candidate_generation`` and ``validation``
(F-01b), ``baseline_parse`` (F-01c). With the baseline parse moved here, every
advertised-async Create-Package operation runs on a real worker — no admission path
completes its own compute in-transaction.

All four workers share one lifecycle shape:

    load job (redelivery guard: a terminal job replays its durable ``result_ref``) ->
    lock the request root -> superseded guard (the request advanced past the state this
        delivery was admitted for => SUPERSEDED, nothing recorded) -> RUNNING ->
    compute -> record durable evidence + advance the request state + audit/outbox ->
    SUCCEEDED, or a DURABLE terminal failure (never a silent success, never an
    infinite retry).

The Pre-Check lifecycle mirrors ``jobs.backtest_engine`` / ``jobs.trade_log``:

    load job (redelivery guard: a terminal job replays its durable ``result_ref`` and
        never re-scans — the immutable scan is append-only) -> lock the request row ->
    superseded guard: a request that already advanced past a Pre-Check state (a
        concurrent Send / candidate-generation won the race) records nothing and the
        delivery ends SUPERSEDED (mirrors ``run_backtest``'s terminal-run guard) ->
    RUNNING -> compute the scan (description => NOT_APPLICABLE; else scan the SOURCE for
        TA/condition calls, reconcile against declared deps, resolve each declared call
        against the trusted ESP registry, pin a registry fingerprint) ->
    record the immutable scan + advance the request state + audit/outbox -> SUCCEEDED.

A compute failure is recorded as a DURABLE terminal outcome (an immutable FAILED scan +
request -> PRECHECK_FAILED + job FAILED_FINAL), never a silent success and never an
infinite retry — mirrors ``run_backtest``'s terminal-fail path. Only an unexpected
missing-row condition raises (retryable). The completion outbox is ``resource.changed``
on the ``package_request`` (the exact event the sync path emitted), so the Pre-Check
overlay refetches server-authoritative state via the existing SSE catch-all. Does not
commit (the actor session scope commits).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.jobs.package_validation import run_package_validation
from entropia.application.queries import esp as esp_query
from entropia.domain.create_package import (
    BaselineParseStatus,
    CreatePackageState,
    PrecheckScanStatus,
    SourceKind,
    SourceLanguage,
    ValidationRunStatus,
    next_request_state,
    parse_baseline_csv,
    scan_source_calls,
)
from entropia.domain.create_package.baseline import BASELINE_PARSER_VERSION
from entropia.domain.create_package.generator import GeneratedCandidate, generate_candidate
from entropia.domain.create_package.language_detect import (
    LANGUAGE_DETECTOR_VERSION,
    detect_source_language,
)
from entropia.domain.create_package.source_scan import SOURCE_SCANNER_VERSION, is_scannable_key
from entropia.domain.create_package.validation import (
    STATUS_BLOCKED,
    VALIDATOR_VERSION,
    ValidationCheck,
)
from entropia.domain.esp.enums import RuntimeAdapter
from entropia.domain.lifecycle.enums import ActorKind, JobStatus
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.revision.hashing import content_hash
from entropia.infrastructure.postgres.models import (
    BaselineAsset,
    EntityRegistry,
    Job,
    PackageRequest,
    PackageRevision,
    PackageValidationRun,
)
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import (
    BaselineParseFailed,
    ParseUnsupported,
    RequiresClarification,
    ResolverAdapterIncompatible,
    ResolverNotActive,
    ResolverNotResolved,
    ResolverSignatureMismatch,
    SourceLanguageMismatch,
)

_REQUEST_TARGET_KIND = "package_request"
_PACKAGE_TARGET_KIND = "package"
_PRECHECK_KIND = "precheck"
_CANDIDATE_KIND = "candidate_generation"
_VALIDATION_KIND = "validation"
_BASELINE_PARSE_KIND = "baseline_parse"
# The scanner semantics are the comment/string-aware source lexer (doc 07 §6.2); the
# version tracks the domain scanner contract (mirrors the former sync command).
_SCANNER_VERSION = SOURCE_SCANNER_VERSION
_UNDECLARED_SOURCE_CODE = "UNDECLARED_SOURCE_DEPENDENCY"
_DECLARED_NOT_IN_SOURCE_CODE = "DECLARED_NOT_IN_SOURCE"
_RESOLVE_ERRORS = (
    ResolverNotResolved,
    ResolverSignatureMismatch,
    ResolverAdapterIncompatible,
    # A deprecated / soft-deleted registry entry blocks exactly like a missing one
    # (doc 07 §12 RESOLVER_NOT_ACTIVE) — it must never fall through to Passed.
    ResolverNotActive,
)
_PRECHECK_WORKER_FAILED = "PRECHECK_WORKER_FAILED"
# The registry was never consulted on a fail-closed scan, so there is no fingerprint
# to pin. A FAILED scan can never satisfy the Send gate, which requires PASSED.
_UNEVALUATED_FINGERPRINT = "sha256:not_evaluated"
_CANDIDATE_WORKER_FAILED = "CANDIDATE_GENERATION_WORKER_FAILED"
_VALIDATION_WORKER_FAILED = "VALIDATION_WORKER_FAILED"
_BASELINE_WORKER_FAILED = "BASELINE_PARSE_WORKER_FAILED"

# A redelivered job in a terminal status has already produced its durable outcome;
# re-running would append a duplicate immutable scan attempt.
_JOB_TERMINAL = frozenset(
    {
        JobStatus.SUCCEEDED,
        JobStatus.FAILED_FINAL,
        JobStatus.CANCELLED,
        JobStatus.SUPERSEDED,
    }
)
# The request states from which recording a Pre-Check scan is a legal transition (the
# states where Pre-Check is offered). A request that advanced past these between enqueue
# and worker was superseded — recording now would be an illegal state jump.
_PRECHECK_RECORDABLE = frozenset(
    {
        CreatePackageState.REQUESTED,
        CreatePackageState.PRECHECK_PASSED,
        CreatePackageState.PRECHECK_BLOCKED,
        CreatePackageState.PRECHECK_NOT_APPLICABLE,
        CreatePackageState.PRECHECK_STALE,
        CreatePackageState.PRECHECK_FAILED,
    }
)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class PrecheckComputation:
    """The pure result of a Pre-Check scan, ready to persist as immutable evidence."""

    detected_calls: list[str]
    resolved_refs: list[dict[str, Any]]
    missing_calls: list[dict[str, Any]]
    source_warnings: list[dict[str, Any]]
    status: PrecheckScanStatus
    registry_fingerprint: str
    next_state: CreatePackageState
    # Calls/inputs the production parser could not handle at all (doc 07 §12
    # PARSE_UNSUPPORTED / SOURCE_LANGUAGE_MISMATCH / REQUIRES_CLARIFICATION). A
    # non-empty list always accompanies a FAILED status — never a verdict.
    unsupported_calls: list[dict[str, Any]] = field(default_factory=list)
    error_detail: dict[str, Any] | None = None


def _fail_closed(*, code: str, message: str, evidence: dict[str, Any]) -> PrecheckComputation:
    """A determinate Pre-Check *refusal*: the scanner ran and knows it cannot judge.

    Distinct from ``_fail_precheck`` (an unexpected worker crash). The scan is
    recorded FAILED with the canonical error code, the request advances to
    PRECHECK_FAILED, and — because the Send gate requires a PASSED scan — the
    request can never reach candidate generation on this evidence (doc 07 §9.5,
    §12.1: a positive result is never produced for an unparsed/mismatched source).
    """
    return PrecheckComputation(
        detected_calls=[],
        resolved_refs=[],
        missing_calls=[],
        source_warnings=[],
        status=PrecheckScanStatus.FAILED,
        registry_fingerprint=_UNEVALUATED_FINGERPRINT,
        next_state=CreatePackageState.PRECHECK_FAILED,
        unsupported_calls=[{"code": code, "message": message, "evidence": evidence}],
        error_detail={"code": code, "message": message},
    )


def _language_verdict(
    source_language: SourceLanguage | None, source: str
) -> PrecheckComputation | None:
    """Adjudicate the DECLARED language against the language the CONTENT shows (PC-10).

    Returns a fail-closed computation on disagreement, otherwise ``None`` (proceed).
    Two honest boundaries, both deliberate:

    * ``other`` carries a free-text label the detector cannot adjudicate against, so
      no verdict is issued for it (the label is a human contract, not a grammar);
    * absence of markers is NOT treated as mismatch — a snippet too small to carry
      evidence proceeds to the lexer, which applies its own PARSE_UNSUPPORTED rule.
    """
    if source_language is None or source_language == SourceLanguage.OTHER:
        return None
    signal = detect_source_language(source)
    evidence = {
        "selected_language": str(source_language),
        "detected_language": str(signal.language) if signal.language else None,
        "scores": signal.scores,
        "detector_version": LANGUAGE_DETECTOR_VERSION,
    }
    if signal.is_ambiguous:
        return _fail_closed(
            code=RequiresClarification.code,
            message=(
                "The source content matches more than one language. "
                "Confirm the source language before continuing."
            ),
            evidence=evidence,
        )
    if signal.language is not None and signal.language != source_language:
        return _fail_closed(
            code=SourceLanguageMismatch.code,
            message=(
                f"Source language '{source_language}' was selected but the content "
                f"matches '{signal.language}'."
            ),
            evidence=evidence,
        )
    return None


async def registry_fingerprint(
    session: AsyncSession, declared_dependencies: list[dict[str, Any]]
) -> str:
    """Fingerprint the consulted registry pointers so an Admin activate/deprecate of any
    declared resolver after a scan makes that scan stale (doc 07 §8.1, IR-4).

    Public because the candidate-generation gate (``_enforce_precheck_gate`` in
    ``commands.create_package``) re-computes it to detect drift — the two MUST agree, so
    they share this one implementation.
    """
    parts: list[dict[str, Any]] = []
    for dep in declared_dependencies:
        key = str(dep.get("key", ""))
        entry = await esp_repo.get_registry_by_key(session, key)
        parts.append(
            {
                "key": key,
                "active_revision_id": entry.trusted_active_revision_id if entry else None,
                "registry_version": entry.registry_version if entry else None,
                "trust_state": str(entry.trust_state) if entry else None,
            }
        )
    parts.sort(key=lambda p: p["key"])
    return f"sha256:{content_hash(parts)}"


async def _resolve_declared(
    session: AsyncSession,
    declared_dependencies: list[dict[str, Any]],
    target_runtime: RuntimeAdapter,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve each declared canonical TA call against the trusted ESP registry.

    Returns ``(resolved_refs, missing_calls)``. Each resolved ref pins the exact revision
    id + content hash + registry version (never name-only/latest, P4/L5). A typed resolver
    error becomes a missing_call with its precise code.
    """
    resolved_refs: list[dict[str, Any]] = []
    missing_calls: list[dict[str, Any]] = []
    for dep in declared_dependencies:
        key = str(dep.get("key", ""))
        signature = dep.get("signature") if isinstance(dep.get("signature"), dict) else {}
        try:
            res = await esp_query.resolve_embedded_dependency(
                session,
                parsed_call={"key": key, "signature": signature},
                target_runtime=target_runtime,
            )
            resolved_refs.append(
                {
                    "call": key,
                    "canonical_key": res["canonical_key"],
                    "embedded_entity_id": res["entity_id"],
                    "embedded_revision_id": res["revision_id"],
                    "content_hash": res["content_hash"],
                    "runtime_adapter": res["runtime_adapter"],
                    "registry_version": res["registry_version"],
                }
            )
        except _RESOLVE_ERRORS as exc:
            missing_calls.append({"call": key, "code": exc.code, "message": exc.message})
    return resolved_refs, missing_calls


async def compute_precheck(session: AsyncSession, detail: PackageRequest) -> PrecheckComputation:
    """Run the Pre-Check dependency scan for a request (doc 07 §8, §10).

    Description requests resolve to NOT_APPLICABLE (no resolver gate). Code requests
    detect the real TA/condition call nodes from the SOURCE (comment/string aware), then
    reconcile against the declared dependency list (doc 07 §6.2): a source call the request
    never declared blocks (PC-06 undeclared), and a declared call the source never invokes
    is a non-fatal over-declaration warning. Declared deps drive registry resolution + the
    pins; any unresolved declared call or undeclared source call makes the scan BLOCKED.

    Two fail-closed gates run BEFORE any of that, because a scanner that did not
    understand the file would otherwise reconcile an empty call set into ``Passed``
    (doc 07 §9.5, §12):

      1. the declared language vs. the language the content actually shows —
         SOURCE_LANGUAGE_MISMATCH, or REQUIRES_CLARIFICATION when the evidence
         competes (PC-10). Checked first because it is the more actionable
         diagnostic: "you picked the wrong language" beats "I could not parse it".
      2. the lexer's own accounting — PARSE_UNSUPPORTED when an unterminated
         string/comment swallowed the tail or too much of the body falls outside
         the grammar it parses.

    Either gate yields a FAILED scan + PRECHECK_FAILED, which the Send gate
    (``_enforce_precheck_gate``, PASSED-only) can never satisfy.
    """
    if detail.source_kind == SourceKind.DESCRIPTION:
        return PrecheckComputation(
            detected_calls=[],
            resolved_refs=[],
            missing_calls=[],
            source_warnings=[],
            status=PrecheckScanStatus.NOT_APPLICABLE,
            registry_fingerprint="sha256:not_applicable",
            next_state=CreatePackageState.PRECHECK_NOT_APPLICABLE,
        )

    language_failure = _language_verdict(detail.source_language, detail.request_body)
    if language_failure is not None:
        return language_failure

    scan = scan_source_calls(detail.request_body)
    if scan.is_parse_unsupported:
        return _fail_closed(
            code=ParseUnsupported.code,
            message=(
                "The source could not be parsed safely "
                f"({scan.unsupported_reason}). Manual review is required."
            ),
            evidence=scan.as_evidence(),
        )

    detected = list(scan.calls)
    declared_keys = [str(dep["key"]) for dep in detail.declared_dependencies]
    declared_set = set(declared_keys)
    source_set = set(detected)
    undeclared = [
        {
            "call": call,
            "code": _UNDECLARED_SOURCE_CODE,
            "message": f"Source calls '{call}' but it is not declared as a dependency.",
        }
        for call in detected
        if call not in declared_set
    ]
    source_warnings = [
        {
            "call": key,
            "code": _DECLARED_NOT_IN_SOURCE_CODE,
            "message": f"Declared dependency '{key}' is not called in the source.",
        }
        for key in declared_keys
        if is_scannable_key(key) and key not in source_set
    ]

    resolved_refs, missing_calls = await _resolve_declared(
        session, detail.declared_dependencies, detail.target_runtime
    )
    # Registry-missing declared calls first, then undeclared source calls: both block,
    # and the existing missing[0] contract stays the resolver miss.
    missing_calls = missing_calls + undeclared
    fingerprint = await registry_fingerprint(session, detail.declared_dependencies)
    passed = not missing_calls
    status = PrecheckScanStatus.PASSED if passed else PrecheckScanStatus.BLOCKED
    next_state = (
        CreatePackageState.PRECHECK_PASSED if passed else CreatePackageState.PRECHECK_BLOCKED
    )
    return PrecheckComputation(
        detected_calls=detected,
        resolved_refs=resolved_refs,
        missing_calls=missing_calls,
        source_warnings=source_warnings,
        status=status,
        registry_fingerprint=fingerprint,
        next_state=next_state,
    )


def _emit_worker_event(
    session: AsyncSession,
    job: Job,
    *,
    event_kind: str,
    target_kind: str,
    entity_id: str,
    revision_id: str | None,
    previous_state: str,
    new_state: str,
    action: str,
) -> None:
    """Audit + ``resource.changed`` outbox for a completed worker step (identical to the
    sync path each worker replaced).

    The worker acts as a SYSTEM_SERVICE on behalf of the requesting principal. The outbox
    event_type stays ``resource.changed`` so the Create-Package surfaces refetch
    server-authoritative state through the existing SSE catch-all (never ``job.updated``);
    the taxonomy is untouched — ``action`` carries the same verbs the sync path emitted.
    """
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=job.actor_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=entity_id,
        target_entity_type=target_kind,
        target_revision_id=revision_id,
        previous_state=previous_state,
        new_state=new_state,
        reason=None,
        correlation_id=job.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=target_kind,
        resource_id=entity_id,
        payload={"action": action, "revision_id": revision_id},
        correlation_id=job.correlation_id,
    )


def _emit_precheck_completed(
    session: AsyncSession,
    job: Job,
    root: EntityRegistry,
    scan_id: str,
    previous_state: str,
    new_state: str,
    *,
    action: str,
) -> None:
    """The Pre-Check completion event: request-scoped, carrying the immutable scan id."""
    _emit_worker_event(
        session,
        job,
        event_kind="package_precheck_completed",
        target_kind=_REQUEST_TARGET_KIND,
        entity_id=root.entity_id,
        revision_id=scan_id,
        previous_state=previous_state,
        new_state=new_state,
        action=action,
    )


async def _record_scan(
    session: AsyncSession,
    job: Job,
    root: EntityRegistry,
    detail: PackageRequest,
    computation: PrecheckComputation,
) -> dict[str, Any]:
    """Insert the immutable scan, point the request head at it, advance the flow state.

    Preserves the sync path's OCC/version guard: ``root.row_version`` is bumped so the
    ``expected_request_version`` token the client held at enqueue detects the advance.
    """
    scan = await cp_repo.append_dependency_scan(
        session,
        request_entity_id=root.entity_id,
        source_hash=detail.source_hash,
        context_hash=detail.context_hash,
        language=str(detail.source_language) if detail.source_language else None,
        scanner_version=_SCANNER_VERSION,
        registry_fingerprint=computation.registry_fingerprint,
        detected_calls=computation.detected_calls,
        resolved_refs=computation.resolved_refs,
        missing_calls=computation.missing_calls,
        unsupported_calls=computation.unsupported_calls,
        source_warnings=computation.source_warnings,
        status=computation.status,
        job_id=job.job_id,
        error_detail=computation.error_detail,
        correlation_id=job.correlation_id or None,
        created_by_principal_id=job.actor_principal_id,
    )
    scan.completed_at = _now()
    await session.flush()
    detail.current_scan_id = scan.scan_id
    previous = detail.state
    detail.state = next_request_state(detail.state, computation.next_state)
    root.row_version += 1
    _emit_precheck_completed(
        session,
        job,
        root,
        scan.scan_id,
        str(previous),
        str(detail.state),
        # A fail-closed refusal is a completed scan with a negative verdict, so it
        # carries the same failure verb the crash path emits — the UI must not read
        # "completed" and infer a usable result.
        action=(
            "precheck_failed"
            if computation.status == PrecheckScanStatus.FAILED
            else "precheck_completed"
        ),
    )
    return {
        "request_id": root.entity_id,
        "scan_id": scan.scan_id,
        "attempt_no": scan.attempt_no,
        "status": str(scan.status),
        "state": str(detail.state),
        "resolved": len(computation.resolved_refs),
        "missing": computation.missing_calls,
        "warnings": computation.source_warnings,
        "unsupported": computation.unsupported_calls,
        "error": computation.error_detail,
        "registry_fingerprint": computation.registry_fingerprint,
        "job_id": job.job_id,
    }


async def _fail_precheck(
    session: AsyncSession,
    job: Job,
    root: EntityRegistry,
    detail: PackageRequest,
    exc: Exception,
) -> dict[str, Any]:
    """Record a durable terminal Pre-Check failure (Finding F-01: worker failure is a
    durable failed state, never a silent success and never an infinite retry).

    An immutable FAILED scan carries the error; the request advances to PRECHECK_FAILED
    (legal from every Pre-Check state, state_machine widened for F-01a) and the job is
    FAILED_FINAL. Returning normally lets the actor commit the failure.
    """
    error_detail = {"code": _PRECHECK_WORKER_FAILED, "message": str(exc)}
    scan = await cp_repo.append_dependency_scan(
        session,
        request_entity_id=root.entity_id,
        source_hash=detail.source_hash,
        context_hash=detail.context_hash,
        language=str(detail.source_language) if detail.source_language else None,
        scanner_version=_SCANNER_VERSION,
        registry_fingerprint="sha256:precheck_failed",
        detected_calls=[],
        resolved_refs=[],
        missing_calls=[],
        unsupported_calls=[],
        source_warnings=[],
        status=PrecheckScanStatus.FAILED,
        job_id=job.job_id,
        error_detail=error_detail,
        correlation_id=job.correlation_id or None,
        created_by_principal_id=job.actor_principal_id,
    )
    scan.completed_at = _now()
    await session.flush()
    detail.current_scan_id = scan.scan_id
    previous = detail.state
    detail.state = next_request_state(detail.state, CreatePackageState.PRECHECK_FAILED)
    root.row_version += 1
    _emit_precheck_completed(
        session,
        job,
        root,
        scan.scan_id,
        str(previous),
        str(detail.state),
        action="precheck_failed",
    )
    job.status = JobStatus.FAILED_FINAL
    job.finished_at = _now()
    job.error = error_detail
    result = {
        "request_id": root.entity_id,
        "scan_id": scan.scan_id,
        "attempt_no": scan.attempt_no,
        "status": str(scan.status),
        "state": str(detail.state),
        "resolved": 0,
        "missing": [],
        "warnings": [],
        "unsupported": [],
        "error": error_detail,
        "registry_fingerprint": scan.registry_fingerprint,
        "job_id": job.job_id,
    }
    job.result_ref = result
    return result


def _superseded_ref(job: Job, root: EntityRegistry, detail: PackageRequest) -> dict[str, Any]:
    return {
        "request_id": root.entity_id,
        "state": str(detail.state),
        "status": str(job.status),
        "job_id": job.job_id,
        "superseded": True,
    }


async def run_precheck_job(session: AsyncSession, job: Job) -> dict[str, Any]:
    """Execute the durable Pre-Check job. Does not commit (the actor scope commits)."""
    request_id = str((job.payload or {}).get("request_id"))

    # At-least-once delivery guard: a redelivered message for a job that already reached a
    # terminal status replays its durable outcome and never re-scans (the scan is an
    # append-only immutable attempt, so a second run would forge a duplicate).
    if job.status in _JOB_TERMINAL:
        return job.result_ref or {
            "request_id": request_id,
            "status": str(job.status),
            "job_id": job.job_id,
        }

    root = await cp_repo.get_request_root(session, request_id)
    detail = await cp_repo.get_request_detail(session, request_id)
    if root is None or detail is None:
        raise ValueError(
            f"Package request '{request_id}' not found for Pre-Check job '{job.job_id}'."
        )

    await session.refresh(root, with_for_update=True)
    await session.refresh(detail)

    # Superseded guard: a concurrent Send / candidate-generation advanced the request past
    # a Pre-Check state; recording a scan now would be an illegal transition, so this
    # delivery is a durable no-op (mirrors run_backtest's already-terminal-run guard).
    if detail.state not in _PRECHECK_RECORDABLE:
        job.status = JobStatus.SUPERSEDED
        job.finished_at = _now()
        result = _superseded_ref(job, root, detail)
        job.result_ref = result
        return result

    job.status = JobStatus.RUNNING
    job.started_at = _now()
    try:
        computation = await compute_precheck(session, detail)
    except Exception as exc:  # a compute failure becomes a durable terminal state
        return await _fail_precheck(session, job, root, detail, exc)

    result = await _record_scan(session, job, root, detail, computation)
    job.status = JobStatus.SUCCEEDED
    job.finished_at = _now()
    job.result_ref = result
    return result


# ---------------------------------------------------------------------------
# Candidate generation (F-01b)
# ---------------------------------------------------------------------------


async def _candidate_resolved_refs(
    session: AsyncSession, detail: PackageRequest
) -> list[dict[str, Any]]:
    """The resolved ESP refs the candidate compute pins (doc 06 §5).

    Description requests resolve nothing; a code request reuses the current PASSED
    scan's resolved refs (the PC-13 gate ran at admission, so the scan is fresh).
    """
    if detail.source_kind == SourceKind.DESCRIPTION:
        return []
    scan = await cp_repo.get_current_scan(session, detail)
    if scan is None:
        return []
    return list(scan.resolved_refs or [])


async def generate_and_store_candidate(
    session: AsyncSession, detail: PackageRequest
) -> GeneratedCandidate:
    """Generate the loadable candidate (F-14) and pin it onto the request.

    Deterministic: the same request inputs always produce the same implementation and
    the same candidate hash. Shared by the candidate-generation worker (Send) and the
    in-transaction revision loop (``commands.request_package_revision``) so both produce
    an identical implementation. Stores the candidate hash, the validated output
    contract and the loadable implementation (source + test draft + plan) — later copied
    verbatim onto the immutable draft revision at C.D.P. A real LLM / arbitrary-code
    generator + its isolated sandbox stays Future-Dev.
    """
    resolved_refs = await _candidate_resolved_refs(session, detail)
    generated = generate_candidate(
        request_id=detail.entity_id,
        package_kind=str(detail.package_kind),
        source_kind=detail.source_kind,
        output_contract=detail.output_contract,
        resolved_refs=resolved_refs,
        source_language=detail.source_language,
    )
    detail.candidate_hash = generated.candidate_hash
    detail.candidate_output_contract = generated.output_contract
    detail.candidate_implementation = generated.implementation.as_dict()
    return generated


def _candidate_result(
    root: EntityRegistry, detail: PackageRequest, job: Job, *, candidate_hash: str
) -> dict[str, Any]:
    return {
        "request_id": root.entity_id,
        "state": str(detail.state),
        "candidate_hash": candidate_hash,
        "job_id": job.job_id,
    }


async def _fail_candidate(
    session: AsyncSession,
    job: Job,
    root: EntityRegistry,
    detail: PackageRequest,
    exc: Exception,
) -> dict[str, Any]:
    """Record a durable terminal candidate-generation failure (Finding F-01).

    The request advances to CANDIDATE_FAILED (a real state with a retry edge back to
    CANDIDATE_GENERATING) and the job is FAILED_FINAL — never a silent success, never an
    infinite retry. The audit kind is the spec's ``candidate_generation_failed``.
    """
    error_detail = {"code": _CANDIDATE_WORKER_FAILED, "message": str(exc)}
    previous = detail.state
    detail.state = next_request_state(detail.state, CreatePackageState.CANDIDATE_FAILED)
    root.row_version += 1
    _emit_worker_event(
        session,
        job,
        event_kind="candidate_generation_failed",
        target_kind=_REQUEST_TARGET_KIND,
        entity_id=root.entity_id,
        revision_id=None,
        previous_state=str(previous),
        new_state=str(detail.state),
        action="candidate_generation_failed",
    )
    job.status = JobStatus.FAILED_FINAL
    job.finished_at = _now()
    job.error = error_detail
    result = _candidate_result(root, detail, job, candidate_hash="")
    result["error"] = error_detail
    job.result_ref = result
    return result


async def run_candidate_generation_job(session: AsyncSession, job: Job) -> dict[str, Any]:
    """Execute the durable candidate-generation job (doc 06 §5; F-01b).

    The Pre-Check gate (PC-13) already ran at admission — re-running it here would race a
    concurrent registry change into a worker-side error instead of the typed 409 the
    client received synchronously. What the worker owns is the compute + the durable
    outcome. Does not commit (the actor scope commits).
    """
    request_id = str((job.payload or {}).get("request_id"))
    if job.status in _JOB_TERMINAL:
        return job.result_ref or {
            "request_id": request_id,
            "state": str(job.status),
            "job_id": job.job_id,
        }

    root = await cp_repo.get_request_root(session, request_id)
    detail = await cp_repo.get_request_detail(session, request_id)
    if root is None or detail is None:
        raise ValueError(
            f"Package request '{request_id}' not found for candidate job '{job.job_id}'."
        )

    await session.refresh(root, with_for_update=True)
    await session.refresh(detail)

    # Superseded guard: only the state this delivery was admitted for may complete. A
    # request that already advanced (a concurrent re-generate won, or a revision reset
    # the flow) records nothing — mirrors run_precheck_job's guard.
    if detail.state != CreatePackageState.CANDIDATE_GENERATING:
        job.status = JobStatus.SUPERSEDED
        job.finished_at = _now()
        result = _superseded_ref(job, root, detail)
        job.result_ref = result
        return result

    job.status = JobStatus.RUNNING
    job.started_at = _now()
    try:
        generated = await generate_and_store_candidate(session, detail)
    except Exception as exc:  # a compute failure becomes a durable terminal state
        return await _fail_candidate(session, job, root, detail, exc)

    previous = detail.state
    detail.state = next_request_state(detail.state, CreatePackageState.CANDIDATE_READY)
    root.row_version += 1
    _emit_worker_event(
        session,
        job,
        event_kind="candidate_generation_completed",
        target_kind=_REQUEST_TARGET_KIND,
        entity_id=root.entity_id,
        revision_id=None,
        previous_state=str(previous),
        new_state=str(detail.state),
        action="candidate_generation_completed",
    )
    result = _candidate_result(root, detail, job, candidate_hash=generated.candidate_hash)
    job.status = JobStatus.SUCCEEDED
    job.finished_at = _now()
    job.result_ref = result
    return result


# ---------------------------------------------------------------------------
# Validation run (F-01b)
# ---------------------------------------------------------------------------


def _validation_result(
    root: EntityRegistry, detail: PackageRequest, run: PackageValidationRun, job: Job
) -> dict[str, Any]:
    return {
        "request_id": root.entity_id,
        "validation_run_id": run.validation_run_id,
        "attempt_no": run.attempt_no,
        "status": str(run.status),
        "state": str(detail.state),
        "checks": run.checks,
        "job_id": job.job_id,
    }


def _certify_draft_revision(revision: PackageRevision | None, *, passed: bool) -> None:
    """Stamp the run's verdict onto the draft revision.

    ``can_use`` requires the head revision's validation_state == PASSED
    (domain/package/permissions), so without this the draft stays PENDING and an
    approved+published package could never be pinned in the Strategy editor. A FAILED
    run marks it FAILED; a regenerated candidate makes a fresh PENDING draft, so
    evidence never goes stale.
    """
    if revision is None:
        return
    revision.validation_state = (
        PackageValidationState.PASSED if passed else PackageValidationState.FAILED
    )


async def _fail_validation(
    session: AsyncSession,
    job: Job,
    root: EntityRegistry,
    detail: PackageRequest,
    run: PackageValidationRun,
    exc: Exception,
) -> dict[str, Any]:
    """Record a durable terminal validation failure (Finding F-01).

    A worker crash is NOT a pass: the immutable run lands FAILED carrying a BLOCKED
    check with the error, the draft revision is certified FAILED, and the request moves
    to REVISION_REQUIRED so the user's next legal step (Request Revision) is real. The
    job is FAILED_FINAL — never an infinite retry.
    """
    error_detail = {"code": _VALIDATION_WORKER_FAILED, "message": str(exc)}
    run.status = ValidationRunStatus.FAILED
    run.validator_version = VALIDATOR_VERSION
    run.checks = [
        ValidationCheck(
            check="validator",
            status=STATUS_BLOCKED,
            detail="The validation worker failed before it could produce a verdict.",
            artifacts=error_detail,
        ).as_dict()
    ]
    run.completed_at = _now()
    _certify_draft_revision(
        await pkg_repo.get_revision(session, run.draft_revision_id), passed=False
    )
    previous = detail.state
    detail.state = next_request_state(detail.state, CreatePackageState.REVISION_REQUIRED)
    root.row_version += 1
    _emit_worker_event(
        session,
        job,
        event_kind="validation_run_completed",
        target_kind=_PACKAGE_TARGET_KIND,
        entity_id=run.package_root_id,
        revision_id=run.draft_revision_id,
        previous_state=str(previous),
        new_state=str(detail.state),
        action="validation_run_failed",
    )
    job.status = JobStatus.FAILED_FINAL
    job.finished_at = _now()
    job.error = error_detail
    result = _validation_result(root, detail, run, job)
    result["error"] = error_detail
    job.result_ref = result
    return result


async def run_validation_job(session: AsyncSession, job: Job) -> dict[str, Any]:
    """Execute the durable Validation Tests job (doc 06 §4.4/§5/§7; F-13 + F-01b).

    The QUEUED immutable run row was appended at admission (the spec's queued/running
    row states), so the UI has a real evidence row to poll from the first render. This
    body flips it RUNNING, gathers the draft's real facts through
    ``jobs.package_validation.run_package_validation`` and lands the honest verdict: a
    not_executed / blocked mandatory check is NOT a pass, so only a fully-passing run
    reaches ELIGIBLE_FOR_APPROVAL. Does not commit (the actor scope commits).
    """
    payload = job.payload or {}
    request_id = str(payload.get("request_id"))
    validation_run_id = str(payload.get("validation_run_id"))
    if job.status in _JOB_TERMINAL:
        return job.result_ref or {
            "request_id": request_id,
            "validation_run_id": validation_run_id,
            "status": str(job.status),
            "job_id": job.job_id,
        }

    root = await cp_repo.get_request_root(session, request_id)
    detail = await cp_repo.get_request_detail(session, request_id)
    run = await cp_repo.get_validation_run(session, validation_run_id)
    if root is None or detail is None or run is None:
        raise ValueError(f"Validation run '{validation_run_id}' not found for job '{job.job_id}'.")

    await session.refresh(root, with_for_update=True)
    await session.refresh(detail)
    await session.refresh(run)

    # Superseded guard: the request must still be running THIS run. A newer run (or a
    # revision that reset the flow) makes this delivery a durable no-op.
    if (
        detail.state != CreatePackageState.VALIDATION_RUNNING
        or detail.current_validation_run_id != run.validation_run_id
    ):
        job.status = JobStatus.SUPERSEDED
        job.finished_at = _now()
        result = _superseded_ref(job, root, detail)
        result["validation_run_id"] = run.validation_run_id
        job.result_ref = result
        return result

    job.status = JobStatus.RUNNING
    job.started_at = _now()
    run.status = ValidationRunStatus.RUNNING
    await session.flush()
    try:
        report = await run_package_validation(session, detail)
    except Exception as exc:  # a compute failure becomes a durable terminal state
        return await _fail_validation(session, job, root, detail, run, exc)

    run.validator_version = report.validator_version
    run.checks = [check.as_dict() for check in report.checks]
    run.status = ValidationRunStatus.PASSED if report.passed else ValidationRunStatus.FAILED
    run.completed_at = _now()
    _certify_draft_revision(
        await pkg_repo.get_revision(session, run.draft_revision_id), passed=report.passed
    )
    previous = detail.state
    terminal = (
        CreatePackageState.ELIGIBLE_FOR_APPROVAL
        if report.passed
        else CreatePackageState.REVISION_REQUIRED
    )
    detail.state = next_request_state(detail.state, terminal)
    root.row_version += 1
    _emit_worker_event(
        session,
        job,
        event_kind="validation_run_completed",
        target_kind=_PACKAGE_TARGET_KIND,
        entity_id=run.package_root_id,
        revision_id=run.draft_revision_id,
        previous_state=str(previous),
        new_state=str(detail.state),
        action="validation_run_completed",
    )
    result = _validation_result(root, detail, run, job)
    job.status = JobStatus.SUCCEEDED
    job.finished_at = _now()
    job.result_ref = result
    return result


# ---------------------------------------------------------------------------
# Baseline parse (F-01c)
# ---------------------------------------------------------------------------


def _baseline_result(
    root: EntityRegistry, asset: BaselineAsset, job: Job, *, request_version: int
) -> dict[str, Any]:
    return {
        "request_id": root.entity_id,
        "baseline_asset_id": asset.baseline_asset_id,
        "attempt_no": asset.attempt_no,
        "parse_status": str(asset.parse_status),
        "parser_version": asset.parser_version or "",
        "parse_report": asset.parse_report or {},
        "job_id": job.job_id,
        "request_version": request_version,
    }


def _emit_baseline_parsed(
    session: AsyncSession,
    job: Job,
    root: EntityRegistry,
    asset: BaselineAsset,
    *,
    action: str,
) -> None:
    """The baseline-parse completion event.

    Keeps the audit ``event_kind`` the synchronous path emitted (``baseline_validated``)
    and distinguishes the outcome through ``action`` — the same shape ``_fail_precheck``
    uses. The taxonomy is untouched: the outbox event stays ``resource.changed`` on the
    ``package_request``, so the baseline panel refetches server-authoritative state.
    """
    _emit_worker_event(
        session,
        job,
        event_kind="baseline_validated",
        target_kind=_REQUEST_TARGET_KIND,
        entity_id=root.entity_id,
        revision_id=asset.baseline_asset_id,
        previous_state=str(BaselineParseStatus.PARSING),
        new_state=str(asset.parse_status),
        action=action,
    )


def _fail_baseline_parse(
    session: AsyncSession,
    job: Job,
    root: EntityRegistry,
    asset: BaselineAsset,
    *,
    code: str,
    message: str,
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    """Record a durable terminal baseline-parse failure (Finding F-01).

    Both failure modes land here: an unparseable CSV (the domain's PARSE_FAILED verdict,
    which the synchronous command used to raise and record nothing) and a worker crash
    before a verdict existed. The head asset becomes ``failed`` carrying the error, so
    ``baseline_ready`` stays false and the equivalence gate still blocks approval; the
    stored upload is untouched evidence and the user's next step is a corrected upload
    (doc 06 §9). The job is FAILED_FINAL — never a silent success, never an infinite retry.
    """
    error_detail = {"code": code, "message": message}
    asset.parse_status = BaselineParseStatus.FAILED
    asset.parse_report = {**(report or {}), **error_detail}
    asset.parser_version = BASELINE_PARSER_VERSION
    asset.parsed_at = _now()
    root.row_version += 1
    _emit_baseline_parsed(session, job, root, asset, action="baseline_parse_failed")
    job.status = JobStatus.FAILED_FINAL
    job.finished_at = _now()
    job.error = error_detail
    result = _baseline_result(root, asset, job, request_version=root.row_version)
    result["error"] = error_detail
    job.result_ref = result
    return result


async def run_baseline_parse_job(session: AsyncSession, job: Job) -> dict[str, Any]:
    """Execute the durable baseline-parse job (doc 06 §4.4/§8.3; F-01c).

    The metadata-complete + head-baseline gates already ran at admission and returned
    their typed errors. What the worker owns is the object-storage read, the deterministic
    parse report and the terminal ``passed`` / ``failed`` status. Does not commit (the
    actor scope commits).
    """
    payload = job.payload or {}
    request_id = str(payload.get("request_id"))
    baseline_asset_id = str(payload.get("baseline_asset_id"))
    if job.status in _JOB_TERMINAL:
        return job.result_ref or {
            "request_id": request_id,
            "baseline_asset_id": baseline_asset_id,
            "status": str(job.status),
            "job_id": job.job_id,
        }

    root = await cp_repo.get_request_root(session, request_id)
    detail = await cp_repo.get_request_detail(session, request_id)
    asset = await cp_repo.get_baseline_asset(session, baseline_asset_id)
    if root is None or detail is None or asset is None:
        raise ValueError(f"Baseline asset '{baseline_asset_id}' not found for job '{job.job_id}'.")

    await session.refresh(root, with_for_update=True)
    await session.refresh(detail)
    await session.refresh(asset)

    # Superseded guard: only the asset this delivery was admitted for, still the request's
    # head and still in flight, may be written. A fresh upload appended a NEW attempt (the
    # head moved) or a prior delivery already landed a terminal status => durable no-op.
    if (
        detail.baseline_asset_id != asset.baseline_asset_id
        or asset.parse_status != BaselineParseStatus.PARSING
    ):
        job.status = JobStatus.SUPERSEDED
        job.finished_at = _now()
        result = _superseded_ref(job, root, detail)
        result["baseline_asset_id"] = asset.baseline_asset_id
        result["parse_status"] = str(asset.parse_status)
        job.result_ref = result
        return result

    job.status = JobStatus.RUNNING
    job.started_at = _now()
    try:
        report = parse_baseline_csv(datasets.get_raw_bytes(asset.object_key))
    except Exception as exc:  # a read/compute failure becomes a durable terminal state
        return _fail_baseline_parse(
            session,
            job,
            root,
            asset,
            code=_BASELINE_WORKER_FAILED,
            message=str(exc),
            report=None,
        )

    if not report.is_parseable:
        return _fail_baseline_parse(
            session,
            job,
            root,
            asset,
            code=BaselineParseFailed.code,
            message=report.detail,
            report=report.as_dict(),
        )

    asset.parse_status = BaselineParseStatus.PASSED
    asset.parse_report = report.as_dict()
    asset.parser_version = report.parser_version
    asset.parsed_at = _now()
    root.row_version += 1
    _emit_baseline_parsed(session, job, root, asset, action="baseline_validated")
    result = _baseline_result(root, asset, job, request_version=root.row_version)
    job.status = JobStatus.SUCCEEDED
    job.finished_at = _now()
    job.result_ref = result
    return result


async def run_create_package_job(session: AsyncSession, job_id: str) -> dict[str, Any]:
    """Durable Create-Package job dispatcher (the ``default``-queue actor body).

    Reads the durable ``kind`` discriminator and routes to the matching worker:
    ``precheck`` (F-01a), ``candidate_generation`` / ``validation`` (F-01b),
    ``baseline_parse`` (F-01c). New kinds add a branch here — never a new actor or a
    scheduler change.
    """
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Create-Package job '{job_id}' not found.")
    kind = str((job.payload or {}).get("kind"))
    if kind == _PRECHECK_KIND:
        return await run_precheck_job(session, job)
    if kind == _CANDIDATE_KIND:
        return await run_candidate_generation_job(session, job)
    if kind == _VALIDATION_KIND:
        return await run_validation_job(session, job)
    if kind == _BASELINE_PARSE_KIND:
        return await run_baseline_parse_job(session, job)
    raise ValueError(f"Unsupported create-package job kind '{kind}' for job '{job_id}'.")


__all__ = [
    "PrecheckComputation",
    "compute_precheck",
    "generate_and_store_candidate",
    "registry_fingerprint",
    "run_baseline_parse_job",
    "run_candidate_generation_job",
    "run_create_package_job",
    "run_precheck_job",
    "run_validation_job",
]
