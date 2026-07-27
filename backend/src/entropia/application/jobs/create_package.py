"""Create-Package worker bodies — Pre-Check dependency scan (docs 06 §7, 07 §8; F-01a).

Runs on the ``default`` queue. The durable ``jobs`` row is the source of truth (CR-09):
the request that admitted the Pre-Check has long since returned ``queued``, so a browser
close / logout never cancels the scan (Finding F-01). The single ``run_create_package_job``
body reads the durable payload ``kind`` and routes to the matching worker; only
``precheck`` is real in F-01a — candidate-generation / validation / baseline-parse stay
in-transaction stubs in ``commands.create_package`` until F-01b/c convert them.

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

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.queries import esp as esp_query
from entropia.domain.create_package import (
    CreatePackageState,
    PrecheckScanStatus,
    SourceKind,
    next_request_state,
    scan_source_calls,
)
from entropia.domain.create_package.source_scan import SOURCE_SCANNER_VERSION, is_scannable_key
from entropia.domain.esp.enums import RuntimeAdapter
from entropia.domain.lifecycle.enums import ActorKind, JobStatus
from entropia.domain.revision.hashing import content_hash
from entropia.infrastructure.postgres.models import EntityRegistry, Job, PackageRequest
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.shared.errors import (
    ResolverAdapterIncompatible,
    ResolverNotResolved,
    ResolverSignatureMismatch,
)

_REQUEST_TARGET_KIND = "package_request"
_PRECHECK_KIND = "precheck"
# The scanner semantics are the comment/string-aware source lexer (doc 07 §6.2); the
# version tracks the domain scanner contract (mirrors the former sync command).
_SCANNER_VERSION = SOURCE_SCANNER_VERSION
_UNDECLARED_SOURCE_CODE = "UNDECLARED_SOURCE_DEPENDENCY"
_DECLARED_NOT_IN_SOURCE_CODE = "DECLARED_NOT_IN_SOURCE"
_RESOLVE_ERRORS = (ResolverNotResolved, ResolverSignatureMismatch, ResolverAdapterIncompatible)
_PRECHECK_WORKER_FAILED = "PRECHECK_WORKER_FAILED"

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

    detected = list(scan_source_calls(detail.request_body).calls)
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
    """Audit + ``resource.changed`` outbox for the request (identical to the sync path).

    The worker acts as a SYSTEM_SERVICE on behalf of the requesting principal. The outbox
    stays ``resource.changed`` on ``package_request`` so the Pre-Check overlay refetches
    server-authoritative state through the existing SSE catch-all (never ``job.updated``).
    """
    audit_repo.add_audit_event(
        session,
        event_kind="package_precheck_completed",
        actor_principal_id=job.actor_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=root.entity_id,
        target_entity_type=_REQUEST_TARGET_KIND,
        target_revision_id=scan_id,
        previous_state=previous_state,
        new_state=new_state,
        reason=None,
        correlation_id=job.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=_REQUEST_TARGET_KIND,
        resource_id=root.entity_id,
        payload={"action": action, "revision_id": scan_id},
        correlation_id=job.correlation_id,
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
        unsupported_calls=[],
        source_warnings=computation.source_warnings,
        status=computation.status,
        job_id=job.job_id,
        error_detail=None,
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
        action="precheck_completed",
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


async def run_create_package_job(session: AsyncSession, job_id: str) -> dict[str, Any]:
    """Durable Create-Package job dispatcher (the ``default``-queue actor body).

    Reads the durable ``kind`` discriminator and routes to the matching worker. F-01a
    only wires ``precheck``; F-01b/c add branches here (candidate-generation, validation,
    baseline-parse) without a new actor or a scheduler change.
    """
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Create-Package job '{job_id}' not found.")
    kind = str((job.payload or {}).get("kind"))
    if kind == _PRECHECK_KIND:
        return await run_precheck_job(session, job)
    raise ValueError(f"Unsupported create-package job kind '{kind}' for job '{job_id}'.")


__all__ = [
    "PrecheckComputation",
    "compute_precheck",
    "registry_fingerprint",
    "run_create_package_job",
    "run_precheck_job",
]
