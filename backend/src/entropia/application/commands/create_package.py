"""Create Package + Pre-Check commands (docs 06 §7, 07 §8; CR-02; Stage 2e).

Each command runs in one transaction supplied by the request dependency and NEVER
commits (mirrors Stage 1/2a/2b/2c/2d). The shape per mutation is: authorization +
pure validation (OUTSIDE) -> idempotent body { optimistic-concurrency + state-
machine legality checks INSIDE (L2) -> repo mutation } -> audit + outbox.

Reuse: the shared Package model from 2c (``pkg_repo.create_package``, async/FK-safe)
for Create Draft Package and the publish head; the ESP resolver registry from 2c
(``esp_query.resolve_embedded_dependency``) for Pre-Check dependency resolution;
the durable job row (``enqueue_job``) as the source of truth (CR-09).

V1 boundaries (Future-Dev): the candidate-generation, scan-parsing and validation
*compute* are stubs — the durable rows, lifecycle, resolver wiring, idempotency,
concurrency, role gates and audit are real. The Pre-Check "parser" reads the
request's explicitly declared canonical TA keys (a real PineScript parser replaces
this later) and resolves each against the trusted ESP registry.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.application.jobs.package_validation import run_package_validation
from entropia.application.queries import esp as esp_query
from entropia.domain.create_package import (
    BaselineParseStatus,
    CreatePackageState,
    CreationMode,
    PrecheckScanStatus,
    SourceKind,
    SourceLanguage,
    ValidationRunStatus,
    clean_declared_dependencies,
    context_hash,
    ensure_can_approve_publish,
    ensure_can_create_request,
    ensure_can_operate_request,
    is_allowed_baseline_file,
    missing_baseline_metadata_fields,
    next_request_state,
    normalize_request,
    parse_baseline_csv,
    resolve_equivalence_claim,
    scan_source_calls,
    source_hash,
)
from entropia.domain.create_package.generator import (
    GeneratedCandidate,
    generate_candidate,
)
from entropia.domain.create_package.source_scan import (
    SOURCE_SCANNER_VERSION,
    is_scannable_key,
)
from entropia.domain.esp.enums import RuntimeAdapter
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    DeletionState,
    JobStatus,
    PackageKind,
    VisibilityScope,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.revision.hashing import content_hash
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    Job,
    PackageRequest,
    PackageRevision,
    PackageRoot,
)
from entropia.infrastructure.postgres.repositories import approvals as approval_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.concurrency import check_head_revision
from entropia.shared.errors import (
    BaselineAssetNotFound,
    BaselineMetadataInvalid,
    BaselineParseFailed,
    BaselineRequired,
    CandidateNotReady,
    CandidateStale,
    DependencyUnresolved,
    FileTypeNotAllowedError,
    PackageRequestNotFound,
    PrecheckBlocked,
    PrecheckStale,
    RationaleFamilyNotActive,
    RequestVersionConflict,
    ResolverAdapterIncompatible,
    ResolverNotResolved,
    ResolverSignatureMismatch,
    ValidationError,
    ValidationRequired,
    ValidationStale,
)

_REQUEST_TARGET_KIND = "package_request"
_PACKAGE_TARGET_KIND = "package"
# The scanner semantics changed from a declared-list echo to a comment/string-aware
# source lexer (doc 07 §6.2). A prior stub scan is not equivalent, so the version
# tracks the domain scanner contract.
_SCANNER_VERSION = SOURCE_SCANNER_VERSION
_UNDECLARED_SOURCE_CODE = "UNDECLARED_SOURCE_DEPENDENCY"
_DECLARED_NOT_IN_SOURCE_CODE = "DECLARED_NOT_IN_SOURCE"
_RESOLVE_ERRORS = (ResolverNotResolved, ResolverSignatureMismatch, ResolverAdapterIncompatible)
# Upload cap for a baseline CSV export (doc 06 §8.3 file type/size gate).
_MAX_BASELINE_BYTES = 25 * 1024 * 1024


def _audit_and_outbox(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    target_kind: str,
    entity_id: str,
    revision_id: str | None,
    previous_state: str | None,
    new_state: str | None,
    action: str,
    reason: str | None = None,
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=entity_id,
        target_entity_type=target_kind,
        target_revision_id=revision_id,
        previous_state=previous_state,
        new_state=new_state,
        reason=reason,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=target_kind,
        resource_id=entity_id,
        payload={"action": action, "revision_id": revision_id},
        correlation_id=actor.correlation_id,
    )


async def _require_request(
    session: AsyncSession, actor: Actor, entity_id: str
) -> tuple[EntityRegistry, PackageRequest]:
    """Resolve a request the actor may operate on (owner or Admin), or raise."""
    root = await cp_repo.get_request_root(session, entity_id)
    detail = await cp_repo.get_request_detail(session, entity_id)
    if root is None or detail is None or root.deletion_state != DeletionState.ACTIVE:
        raise PackageRequestNotFound(f"Package request '{entity_id}' not found.")
    ensure_can_operate_request(actor, owner_principal_id=root.owner_principal_id)
    return root, detail


def _check_request_version(root: EntityRegistry, expected: int | None) -> None:
    if expected is not None and root.row_version != expected:
        raise RequestVersionConflict(
            f"Expected request version {expected} but current is {root.row_version}."
        )


async def _registry_fingerprint(
    session: AsyncSession, declared_dependencies: list[dict[str, Any]]
) -> str:
    """Fingerprint the consulted registry pointers so an Admin activate/deprecate
    of any declared resolver after a scan makes that scan stale (doc 07 §8.1, IR-4)."""
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

    Returns ``(resolved_refs, missing_calls)``. Each resolved ref pins the exact
    revision id + content hash + registry version (never name-only/latest, P4/L5).
    A typed resolver error becomes a missing_call with its precise code.
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


async def create_package_request(
    session: AsyncSession,
    actor: Actor,
    *,
    package_type: str | PackageKind,
    creation_mode: CreationMode,
    source_language: SourceLanguage | None,
    other_language_label: str | None,
    target_runtime: RuntimeAdapter,
    request_body: str,
    output_contract: dict[str, Any],
    rationale_family_id: str | None = None,
    compatible_rationale_family_ids: list[str] | None = None,
    linked_indicator: dict[str, Any] | None = None,
    declared_dependencies: list[dict[str, Any]] | None = None,
    equivalence_claim: bool | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create an immutable Create-Package request (Send step 1, doc 06 §5, §7).

    Validates field requiredness (type/mode/language/runtime/output contract) and,
    for Indicator/Condition, a resolvable ACTIVE Rationale Family; ESP requests
    take the system classification (personal family ignored). Description requests
    start ``precheck_not_applicable``; code requests start ``requested`` and must
    pass Pre-Check before candidate generation.

    ``equivalence_claim`` captures whether the package claims to reproduce/repair/be
    equivalent to an external reference (doc 06 §4.4): it is resolved from the
    creation mode (translate/repair/review claim; generate does not) unless supplied
    explicitly, and drives the mode-aware baseline gate at approval.
    """
    ensure_can_create_request(actor)
    normalized = normalize_request(
        package_type=package_type,
        creation_mode=creation_mode,
        source_language=source_language,
        other_language_label=other_language_label,
        target_runtime=target_runtime,
        request_body=request_body,
        output_contract=output_contract,
    )
    declared = clean_declared_dependencies(declared_dependencies)
    family_id = await _validate_family(session, normalized.package_kind, rationale_family_id)
    claims_equivalence = resolve_equivalence_claim(normalized.creation_mode, equivalence_claim)
    src_hash = source_hash(request_body)
    ctx_hash = context_hash(
        source_hash_value=src_hash,
        source_language=normalized.source_language,
        target_runtime=normalized.target_runtime,
        output_contract=normalized.output_contract,
        declared_dependencies=declared,
    )
    initial_state = (
        CreatePackageState.PRECHECK_NOT_APPLICABLE
        if normalized.source_kind == SourceKind.DESCRIPTION
        else CreatePackageState.REQUESTED
    )

    async def _op() -> dict[str, Any]:
        root, _detail = await cp_repo.create_request(
            session,
            owner_principal_id=actor.principal_id,
            created_by_principal_id=actor.principal_id,
            package_kind=normalized.package_kind,
            creation_mode=normalized.creation_mode,
            source_kind=normalized.source_kind,
            source_language=normalized.source_language,
            other_language_label=normalized.other_language_label,
            target_runtime=normalized.target_runtime,
            request_body=request_body,
            source_hash=src_hash,
            context_hash=ctx_hash,
            output_contract=normalized.output_contract,
            rationale_family_id=family_id,
            compatible_rationale_family_ids=compatible_rationale_family_ids or [],
            linked_indicator=linked_indicator,
            declared_dependencies=declared,
            claims_equivalence=claims_equivalence,
            state=initial_state,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="package_request_created",
            target_kind=_REQUEST_TARGET_KIND,
            entity_id=root.entity_id,
            revision_id=None,
            previous_state=None,
            new_state=str(initial_state),
            action="created",
        )
        return {
            "request_id": root.entity_id,
            "package_type": str(normalized.package_kind),
            "source_kind": str(normalized.source_kind),
            "state": str(initial_state),
            "context_hash": ctx_hash,
            "request_version": root.row_version,
            "claims_equivalence": claims_equivalence,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "create_package_request", "context_hash": ctx_hash},
        operation=_op,
    )


async def _validate_family(
    session: AsyncSession, kind: PackageKind, rationale_family_id: str | None
) -> str | None:
    """Indicator/Condition need an ACTIVE family; ESP uses the system classification."""
    if kind == PackageKind.EMBEDDED_SYSTEM:
        return None
    if rationale_family_id is None:
        raise ValidationError("A Rationale Family is required for this package type.")
    family_root = await rationale_repo.get_family_root(session, rationale_family_id)
    if family_root is None or family_root.deletion_state != DeletionState.ACTIVE:
        raise RationaleFamilyNotActive()
    return rationale_family_id


async def run_precheck(
    session: AsyncSession,
    actor: Actor,
    *,
    request_id: str,
    expected_request_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Run a Pre-Check dependency scan for a request (doc 07 §8, §10).

    Description requests resolve to NOT_APPLICABLE (no resolver gate). Code requests
    resolve each declared canonical TA call against the trusted ESP registry; if any
    is unresolved the scan is BLOCKED, else PASSED. Each scan is immutable evidence
    (new ``attempt_no``) pinning the exact resolved revisions + a registry
    fingerprint. A durable job row records the work (CR-09); the V1 stub completes
    it in-transaction. The concurrency + scan write live INSIDE the idempotent body.
    """
    root, detail = await _require_request(session, actor, request_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        _check_request_version(root, expected_request_version)

        if detail.source_kind == SourceKind.DESCRIPTION:
            return await _record_scan(
                session,
                actor,
                root,
                detail,
                detected_calls=[],
                resolved_refs=[],
                missing_calls=[],
                source_warnings=[],
                status=PrecheckScanStatus.NOT_APPLICABLE,
                registry_fingerprint="sha256:not_applicable",
                next_state=CreatePackageState.PRECHECK_NOT_APPLICABLE,
            )

        # Detect the real TA/condition call nodes from the SOURCE (comment/string
        # aware), then reconcile against the declared dependency list (doc 07 §6.2):
        # a source call the request never declared blocks (PC-06 undeclared), and a
        # declared call the source never invokes is a non-fatal over-declaration
        # warning. Declared deps still drive registry resolution + the pins.
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
        # Registry-missing declared calls first, then undeclared source calls:
        # both block, and the existing missing[0] contract stays the resolver miss.
        missing_calls = missing_calls + undeclared
        fingerprint = await _registry_fingerprint(session, detail.declared_dependencies)
        passed = not missing_calls
        status = PrecheckScanStatus.PASSED if passed else PrecheckScanStatus.BLOCKED
        next_state = (
            CreatePackageState.PRECHECK_PASSED if passed else CreatePackageState.PRECHECK_BLOCKED
        )
        return await _record_scan(
            session,
            actor,
            root,
            detail,
            detected_calls=detected,
            resolved_refs=resolved_refs,
            missing_calls=missing_calls,
            source_warnings=source_warnings,
            status=status,
            registry_fingerprint=fingerprint,
            next_state=next_state,
        )

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "run_precheck",
            "request_id": request_id,
            "context_hash": detail.context_hash,
        },
        operation=_op,
    )


async def _record_scan(
    session: AsyncSession,
    actor: Actor,
    root: EntityRegistry,
    detail: PackageRequest,
    *,
    detected_calls: list[str],
    resolved_refs: list[dict[str, Any]],
    missing_calls: list[dict[str, Any]],
    source_warnings: list[dict[str, Any]],
    status: PrecheckScanStatus,
    registry_fingerprint: str,
    next_state: CreatePackageState,
) -> dict[str, Any]:
    """Insert the immutable scan + durable job row, then advance the request."""
    job: Job = await _enqueue_stub_job(
        session, actor, queue="default", kind="precheck", request_id=root.entity_id
    )
    scan = await cp_repo.append_dependency_scan(
        session,
        request_entity_id=root.entity_id,
        source_hash=detail.source_hash,
        context_hash=detail.context_hash,
        language=str(detail.source_language) if detail.source_language else None,
        scanner_version=_SCANNER_VERSION,
        registry_fingerprint=registry_fingerprint,
        detected_calls=detected_calls,
        resolved_refs=resolved_refs,
        missing_calls=missing_calls,
        unsupported_calls=[],
        source_warnings=source_warnings,
        status=status,
        job_id=job.job_id,
        error_detail=None,
        correlation_id=actor.correlation_id or None,
        created_by_principal_id=actor.principal_id,
    )
    scan.completed_at = datetime.now(UTC)
    await session.flush()
    detail.current_scan_id = scan.scan_id
    previous = detail.state
    detail.state = next_request_state(detail.state, next_state)
    # Advance the request_version so expected_request_version can detect a
    # concurrent state advance (the token is otherwise inert).
    root.row_version += 1
    _audit_and_outbox(
        session,
        actor,
        event_kind="package_precheck_completed",
        target_kind=_REQUEST_TARGET_KIND,
        entity_id=root.entity_id,
        revision_id=scan.scan_id,
        previous_state=str(previous),
        new_state=str(detail.state),
        action="precheck_completed",
    )
    return {
        "request_id": root.entity_id,
        "scan_id": scan.scan_id,
        "attempt_no": scan.attempt_no,
        "status": str(scan.status),
        "state": str(detail.state),
        "resolved": len(resolved_refs),
        "missing": missing_calls,
        "warnings": source_warnings,
        "registry_fingerprint": registry_fingerprint,
        "job_id": job.job_id,
    }


async def submit_candidate_generation(
    session: AsyncSession,
    actor: Actor,
    *,
    request_id: str,
    expected_request_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Send: gate Pre-Check, then enqueue candidate generation (doc 06 §5, doc 07 §9.3).

    The candidate-generation GATE (PC-13) is enforced server-side: a code request
    needs a current PASSED scan that is not stale against the live registry; a
    description request needs no scan. The candidate compute itself is a V1 stub —
    the durable job + candidate summary are produced in-transaction (real LLM
    generation is Future-Dev) so the draft step has a ready candidate to consume.
    """
    root, detail = await _require_request(session, actor, request_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        _check_request_version(root, expected_request_version)
        await _enforce_precheck_gate(session, detail)

        job = await _enqueue_stub_job(
            session, actor, queue="default", kind="candidate_generation", request_id=root.entity_id
        )
        previous = detail.state
        detail.state = next_request_state(detail.state, CreatePackageState.CANDIDATE_GENERATING)
        _audit_and_outbox(
            session,
            actor,
            event_kind="candidate_generation_started",
            target_kind=_REQUEST_TARGET_KIND,
            entity_id=root.entity_id,
            revision_id=None,
            previous_state=str(previous),
            new_state=str(detail.state),
            action="candidate_generation_started",
        )
        # Deterministic candidate generation (doc 06 §5, F-14): generate a real loadable
        # implementation (source + test draft + plan) from the resolved ESP dependencies +
        # validated output contract; its content hash is the candidate hash. A real
        # LLM/arbitrary-code generator + isolated sandbox stays Future-Dev.
        generated = await _generate_and_store_candidate(session, detail)
        new_candidate_hash = generated.candidate_hash
        detail.state = next_request_state(detail.state, CreatePackageState.CANDIDATE_READY)
        root.row_version += 1
        _audit_and_outbox(
            session,
            actor,
            event_kind="candidate_generation_completed",
            target_kind=_REQUEST_TARGET_KIND,
            entity_id=root.entity_id,
            revision_id=None,
            previous_state=str(CreatePackageState.CANDIDATE_GENERATING),
            new_state=str(detail.state),
            action="candidate_generation_completed",
        )
        return {
            "request_id": root.entity_id,
            "state": str(detail.state),
            "candidate_hash": new_candidate_hash,
            "job_id": job.job_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "submit_candidate_generation", "request_id": request_id},
        operation=_op,
    )


async def _enforce_precheck_gate(session: AsyncSession, detail: PackageRequest) -> None:
    """Re-validate the Pre-Check gate at Send time (doc 07 §9.3 PC-13).

    Description requests skip the dependency gate. A code request must have a
    current PASSED scan whose context_hash + registry fingerprint still match the
    live state, else PRECHECK_BLOCKED / PRECHECK_STALE — never bypassable by a
    stale client flag.
    """
    if detail.source_kind == SourceKind.DESCRIPTION:
        return
    scan = await cp_repo.get_current_scan(session, detail)
    if scan is None or scan.status != PrecheckScanStatus.PASSED:
        raise PrecheckBlocked()
    if scan.context_hash != detail.context_hash:
        raise PrecheckStale()
    current_fingerprint = await _registry_fingerprint(session, detail.declared_dependencies)
    if scan.registry_fingerprint != current_fingerprint:
        raise PrecheckStale()


async def _candidate_resolved_refs(
    session: AsyncSession, detail: PackageRequest
) -> list[dict[str, Any]]:
    """The resolved ESP refs the candidate compute pins (doc 06 §5).

    Description requests resolve nothing; a code request reuses the current PASSED
    scan's resolved refs (the PC-13 gate already ran, so the scan is fresh).
    """
    if detail.source_kind == SourceKind.DESCRIPTION:
        return []
    scan = await cp_repo.get_current_scan(session, detail)
    if scan is None:
        return []
    return list(scan.resolved_refs or [])


async def _generate_and_store_candidate(
    session: AsyncSession, detail: PackageRequest
) -> GeneratedCandidate:
    """Generate the loadable candidate (F-14) and pin it onto the request.

    Shared by Send (``submit_candidate_generation``) and the revision loop
    (``request_revision``) so both produce an identical, deterministic implementation
    from the same inputs. Stores the candidate hash, validated output contract, and the
    loadable implementation (source + test draft + plan) — later copied verbatim onto
    the immutable draft revision at C.D.P.
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


async def create_draft_from_candidate(
    session: AsyncSession,
    actor: Actor,
    *,
    request_id: str,
    expected_candidate_hash: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """C.D.P: create the Package Root + immutable Draft Revision (doc 06 §7, §13).

    Requires a ready candidate (``candidate_ready``) whose hash matches. Reuses
    ``pkg_repo.create_package`` (async/FK-safe), pinning the dependency snapshot
    from the current scan's resolved refs and the rationale family snapshot. The
    draft is private/pending/draft — not approved or published. Idempotent: a
    request that already has a draft returns the SAME root + revision.
    """
    root, detail = await _require_request(session, actor, request_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        await session.refresh(detail)
        # Idempotent replay: the draft already exists for this request.
        if detail.package_root_id is not None and detail.draft_revision_id is not None:
            return _draft_result(detail)
        if detail.state != CreatePackageState.CANDIDATE_READY:
            raise CandidateNotReady()
        if expected_candidate_hash is not None and detail.candidate_hash != expected_candidate_hash:
            raise CandidateStale()

        dependency_snapshot = await _draft_dependency_snapshot(session, detail)
        rationale_snapshot = await _draft_rationale_snapshot(session, detail)
        pkg_root, _detail, revision = await pkg_repo.create_package(
            session,
            owner_principal_id=actor.principal_id,
            created_by_principal_id=actor.principal_id,
            package_kind=detail.package_kind,
            input_contract={
                "request_id": detail.entity_id,
                "source_kind": str(detail.source_kind),
                "source_language": str(detail.source_language) if detail.source_language else None,
                "target_runtime": str(detail.target_runtime),
            },
            output_contract=detail.candidate_output_contract or detail.output_contract,
            dependency_snapshot=dependency_snapshot,
            implementation=detail.candidate_implementation,
            visibility_scope=VisibilityScope.PRIVATE,
            rationale_family_snapshot=rationale_snapshot,
            validation_state=PackageValidationState.PENDING,
            approval_state=ApprovalState.DRAFT,
            change_note="Draft created from candidate.",
        )
        await session.flush()
        detail.package_root_id = pkg_root.entity_id
        detail.draft_revision_id = revision.revision_id
        previous = detail.state
        detail.state = next_request_state(detail.state, CreatePackageState.DRAFT_CREATED)
        root.row_version += 1
        _audit_and_outbox(
            session,
            actor,
            event_kind="package_draft_created",
            target_kind=_PACKAGE_TARGET_KIND,
            entity_id=pkg_root.entity_id,
            revision_id=revision.revision_id,
            previous_state=str(previous),
            new_state=str(detail.state),
            action="draft_created",
        )
        return _draft_result(detail)

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "create_draft_from_candidate", "request_id": request_id},
        operation=_op,
    )


def _draft_result(detail: PackageRequest) -> dict[str, Any]:
    return {
        "request_id": detail.entity_id,
        "package_root_id": detail.package_root_id,
        "draft_revision_id": detail.draft_revision_id,
        "state": str(detail.state),
    }


async def _draft_dependency_snapshot(
    session: AsyncSession, detail: PackageRequest
) -> dict[str, Any]:
    """Pin the resolved ESP dependencies from the current scan (P4/L5).

    Code requests must have a current PASSED scan; its resolved refs become the
    immutable dependency snapshot. Description requests carry an empty snapshot.
    """
    if detail.source_kind == SourceKind.DESCRIPTION:
        return {"resolved": [], "source": "description"}
    scan = await cp_repo.get_current_scan(session, detail)
    if scan is None or scan.status != PrecheckScanStatus.PASSED:
        raise DependencyUnresolved()
    if scan.context_hash != detail.context_hash:
        raise PrecheckStale()
    return {"resolved": scan.resolved_refs, "scan_id": scan.scan_id}


async def _draft_rationale_snapshot(
    session: AsyncSession, detail: PackageRequest
) -> dict[str, Any] | None:
    if detail.rationale_family_id is None:
        return None
    family_root = await rationale_repo.get_family_root(session, detail.rationale_family_id)
    if family_root is None or family_root.deletion_state != DeletionState.ACTIVE:
        raise RationaleFamilyNotActive()
    revision = await rationale_repo.get_family_revision(
        session, family_root.current_revision_id or ""
    )
    if revision is None:
        raise RationaleFamilyNotActive()
    return {
        "rationale_family_id": family_root.entity_id,
        "rationale_family_revision_id": revision.revision_id,
        "display_name": revision.display_name,
        "normalized_name": revision.normalized_name,
    }


async def start_package_validation_run(
    session: AsyncSession,
    actor: Actor,
    *,
    request_id: str,
    expected_request_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Run Validation Tests over a draft revision, producing immutable evidence
    (doc 06 §4.4/§5/§7). Revives the ``validation_running`` -> ``eligible_for_approval``
    / ``revision_required`` states.

    Gate: the request must be in ``draft_created`` (has a draft revision). The seven
    mandatory checks run in the durable validation worker body
    (``application/jobs/package_validation``), which gathers the draft's real facts and
    produces an honest verdict (F-13): a ``not_executed`` / ``blocked`` mandatory check
    is NOT a pass, so only a fully-passing run reaches ``eligible_for_approval``; any
    unsatisfied check routes to ``revision_required``. The durable job + immutable run
    row are produced in-transaction (mirrors ``run_precheck``); the concurrency +
    evidence write live INSIDE the idempotent body.
    """
    root, detail = await _require_request(session, actor, request_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        await session.refresh(detail)
        _check_request_version(root, expected_request_version)
        if detail.package_root_id is None or detail.draft_revision_id is None:
            raise CandidateNotReady("This request has no draft revision to validate.")

        # Move to running FIRST (L2: an un-validatable state raises before any write).
        previous = detail.state
        detail.state = next_request_state(detail.state, CreatePackageState.VALIDATION_RUNNING)

        # F-13: the seven mandatory checks run in the durable validation worker body,
        # which gathers the draft's real facts (re-resolved deps, a real syntax probe,
        # the resolved native plan, the baseline parse). ``passed`` is honest — a
        # not_executed / blocked mandatory check does NOT pass and blocks approval.
        report = await run_package_validation(session, detail)
        status = ValidationRunStatus.PASSED if report.passed else ValidationRunStatus.FAILED
        # Certify the draft revision with this run's verdict. can_use requires the head
        # revision's validation_state == PASSED (domain/package/permissions), so without
        # this the draft stays PENDING and the approved+published package is never usable
        # — it cannot be pinned in the Strategy editor. A FAILED run marks it FAILED; a
        # regenerated candidate makes a fresh PENDING draft, so evidence never goes stale.
        draft_revision = await pkg_repo.get_revision(session, detail.draft_revision_id)
        if draft_revision is not None:
            draft_revision.validation_state = (
                PackageValidationState.PASSED if report.passed else PackageValidationState.FAILED
            )
        job = await _enqueue_stub_job(
            session, actor, queue="default", kind="validation", request_id=root.entity_id
        )
        run = await cp_repo.append_validation_run(
            session,
            request_entity_id=root.entity_id,
            package_root_id=detail.package_root_id,
            draft_revision_id=detail.draft_revision_id,
            candidate_hash=detail.candidate_hash,
            validator_version=report.validator_version,
            checks=[check.as_dict() for check in report.checks],
            status=status,
            job_id=job.job_id,
            correlation_id=actor.correlation_id or None,
            created_by_principal_id=actor.principal_id,
        )
        run.completed_at = datetime.now(UTC)
        await session.flush()
        detail.current_validation_run_id = run.validation_run_id
        terminal = (
            CreatePackageState.ELIGIBLE_FOR_APPROVAL
            if report.passed
            else CreatePackageState.REVISION_REQUIRED
        )
        detail.state = next_request_state(detail.state, terminal)
        root.row_version += 1
        _audit_and_outbox(
            session,
            actor,
            event_kind="validation_run_completed",
            target_kind=_PACKAGE_TARGET_KIND,
            entity_id=detail.package_root_id,
            revision_id=detail.draft_revision_id,
            previous_state=str(previous),
            new_state=str(detail.state),
            action="validation_run_completed",
        )
        return {
            "request_id": root.entity_id,
            "validation_run_id": run.validation_run_id,
            "attempt_no": run.attempt_no,
            "status": str(run.status),
            "state": str(detail.state),
            "checks": run.checks,
            "job_id": job.job_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "start_package_validation_run", "request_id": request_id},
        operation=_op,
    )


async def request_package_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    request_id: str,
    expected_request_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Request Revision: reopen a failed/rejected draft for a fresh attempt (doc 06 §5, §7).

    Legal from ``revision_required`` / ``rejected`` (state machine); moves through
    ``candidate_generating`` and regenerates a deterministic candidate so the loop
    (fail validation -> request revision -> new candidate -> new draft -> re-validate)
    closes. The draft head pointers are cleared so the next Create-Draft produces a
    fresh attempt. (A true parent-linked revision CHAIN needs the package
    revision-append machinery — GAP-06 — and is out of scope here.)
    """
    root, detail = await _require_request(session, actor, request_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        await session.refresh(detail)
        previous = detail.state
        # Legality FIRST (L2): only revision_required / rejected have this edge.
        detail.state = next_request_state(detail.state, CreatePackageState.CANDIDATE_GENERATING)
        detail.package_root_id = None
        detail.draft_revision_id = None
        detail.current_validation_run_id = None

        await _generate_and_store_candidate(session, detail)
        detail.state = next_request_state(detail.state, CreatePackageState.CANDIDATE_READY)
        root.row_version += 1
        _audit_and_outbox(
            session,
            actor,
            event_kind="revision_requested",
            target_kind=_REQUEST_TARGET_KIND,
            entity_id=root.entity_id,
            revision_id=None,
            previous_state=str(previous),
            new_state=str(detail.state),
            action="revision_requested",
        )
        return {
            "request_id": root.entity_id,
            "state": str(detail.state),
            "candidate_hash": detail.candidate_hash,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "request_package_revision", "request_id": request_id},
        operation=_op,
    )


async def upload_baseline_asset(
    session: AsyncSession,
    actor: Actor,
    *,
    request_id: str,
    content: bytes,
    baseline_metadata: dict[str, Any],
    content_type: str | None = None,
    original_filename: str | None = None,
    expected_request_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """UploadBaselineAsset: store an immutable baseline CSV + metadata (doc 06 §8.3).

    The file type/size gate runs OUTSIDE (FILE_TYPE_NOT_ALLOWED for a non-CSV, a
    422 for empty/oversize). The bytes are written to object storage content-
    addressed; the immutable ``baseline_asset`` row is the evidence and becomes the
    request's head baseline (a fresh upload is always a new ``attempt_no`` — a prior
    attempt is never mutated). The parse (StartBaselineParse) runs separately.
    """
    root, detail = await _require_request(session, actor, request_id)
    if not is_allowed_baseline_file(original_filename):
        raise FileTypeNotAllowedError("Upload a CSV baseline file.")
    if not content:
        raise ValidationError("The baseline file is empty.")
    if len(content) > _MAX_BASELINE_BYTES:
        raise ValidationError("The baseline file exceeds the maximum allowed size.")

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        await session.refresh(detail)
        _check_request_version(root, expected_request_version)
        object_key, digest = datasets.put_baseline_bytes(
            root.entity_id, content, content_type=content_type
        )
        asset = await cp_repo.append_baseline_asset(
            session,
            request_entity_id=root.entity_id,
            object_key=object_key,
            content_digest=digest,
            size_bytes=len(content),
            content_type=content_type,
            original_filename=original_filename,
            baseline_metadata=baseline_metadata,
            correlation_id=actor.correlation_id or None,
            created_by_principal_id=actor.principal_id,
        )
        await session.flush()
        detail.baseline_asset_id = asset.baseline_asset_id
        root.row_version += 1
        _audit_and_outbox(
            session,
            actor,
            event_kind="baseline_uploaded",
            target_kind=_REQUEST_TARGET_KIND,
            entity_id=root.entity_id,
            revision_id=asset.baseline_asset_id,
            previous_state=None,
            new_state=str(asset.parse_status),
            action="baseline_uploaded",
        )
        return {
            "request_id": root.entity_id,
            "baseline_asset_id": asset.baseline_asset_id,
            "attempt_no": asset.attempt_no,
            "parse_status": str(asset.parse_status),
            "content_digest": digest,
            "size_bytes": len(content),
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "upload_baseline_asset",
            "request_id": request_id,
            "content_digest": datasets.content_digest(content),
        },
        operation=_op,
    )


async def start_baseline_parse(
    session: AsyncSession,
    actor: Actor,
    *,
    request_id: str,
    expected_request_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """StartBaselineParse: validate the head baseline's metadata + CSV (doc 06 §8.3).

    Gate order (a file upload alone is not proof of equivalence, doc 06 §4.4):
    BASELINE_ASSET_NOT_FOUND if there is no head baseline; BASELINE_METADATA_INVALID
    if the submitted metadata is incomplete; PARSE_FAILED if the stored CSV does not
    parse. On success the head baseline transitions ``uploaded -> passed`` with the
    deterministic parse report, and a durable job records the work (CR-09). A failed
    parse raises (the stored asset stays as upload evidence) and the user uploads a
    corrected baseline (doc 06 §9). The concurrency + status write live INSIDE the
    idempotent body.
    """
    root, detail = await _require_request(session, actor, request_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        await session.refresh(detail)
        _check_request_version(root, expected_request_version)
        asset = await cp_repo.get_current_baseline_asset(session, detail)
        if asset is None:
            raise BaselineAssetNotFound()
        missing = missing_baseline_metadata_fields(asset.baseline_metadata)
        if missing:
            raise BaselineMetadataInvalid(
                "The baseline metadata is missing required fields.",
                details=[{"field": field, "issue": "required"} for field in missing],
            )
        report = parse_baseline_csv(datasets.get_raw_bytes(asset.object_key))
        if not report.is_parseable:
            raise BaselineParseFailed(report.detail)

        job = await _enqueue_stub_job(
            session, actor, queue="default", kind="baseline_parse", request_id=root.entity_id
        )
        asset.parse_status = BaselineParseStatus.PASSED
        asset.parse_report = report.as_dict()
        asset.parser_version = report.parser_version
        asset.parse_job_id = job.job_id
        asset.parsed_at = datetime.now(UTC)
        root.row_version += 1
        _audit_and_outbox(
            session,
            actor,
            event_kind="baseline_validated",
            target_kind=_REQUEST_TARGET_KIND,
            entity_id=root.entity_id,
            revision_id=asset.baseline_asset_id,
            previous_state=str(BaselineParseStatus.UPLOADED),
            new_state=str(asset.parse_status),
            action="baseline_validated",
        )
        return {
            "request_id": root.entity_id,
            "baseline_asset_id": asset.baseline_asset_id,
            "attempt_no": asset.attempt_no,
            "parse_status": str(asset.parse_status),
            "parser_version": report.parser_version,
            "parse_report": asset.parse_report,
            "job_id": job.job_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "start_baseline_parse", "request_id": request_id},
        operation=_op,
    )


async def approve_and_publish(
    session: AsyncSession,
    actor: Actor,
    *,
    request_id: str,
    expected_head_revision_id: str | None = None,
    note: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin-only: approve + publish the draft package revision (CR-02, doc 06 §7).

    A single-transaction transition: the draft revision becomes
    approved, the package root becomes published, and an approval_decision + audit
    are recorded. The Admin check is OUTSIDE; concurrency (expected_head_revision_id)
    and the legality checks live INSIDE the idempotent body so a completed-key
    replay returns the cached result. Non-Admins are rejected with
    APPROVAL_REQUIRES_ADMIN before the body runs.
    """
    ensure_can_approve_publish(actor)
    root, detail = await _require_request(session, actor, request_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        await session.refresh(detail)
        if detail.state == CreatePackageState.APPROVED:
            return _publish_result(detail)
        if detail.package_root_id is None or detail.draft_revision_id is None:
            raise CandidateNotReady("This request has no draft revision to approve.")
        # Evidence gate FIRST (doc 06 §4.4/§7): publish only from eligible_for_approval
        # with a current PASSED validation run that still certifies THIS draft's
        # candidate. A fresh draft (draft_created) has no APPROVED edge, so an
        # un-validated request raises VALIDATION_REQUIRED before any row mutation;
        # a regenerated candidate makes the evidence stale (VALIDATION_STALE).
        if detail.state != CreatePackageState.ELIGIBLE_FOR_APPROVAL:
            raise ValidationRequired()
        run = await cp_repo.get_current_validation_run(session, detail)
        if run is None or run.status != ValidationRunStatus.PASSED:
            raise ValidationRequired()
        if run.candidate_hash != detail.candidate_hash:
            raise ValidationStale()
        # Mode-aware baseline gate (doc 06 §4.4/§7): a package that claims
        # translation/repair/equivalence may publish only with a PASSED baseline
        # parse; a non-claiming request needs none (existing behaviour). A file
        # upload alone is not sufficient — the baseline must have parsed.
        if detail.claims_equivalence:
            baseline = await cp_repo.get_current_baseline_asset(session, detail)
            if baseline is None or baseline.parse_status != BaselineParseStatus.PASSED:
                raise BaselineRequired()
        # Only ELIGIBLE_FOR_APPROVAL has an APPROVED edge (state machine, L2).
        target_state = next_request_state(detail.state, CreatePackageState.APPROVED)

        pkg_root = await pkg_repo.get_package_root(session, detail.package_root_id)
        pkg_detail: PackageRoot | None = await pkg_repo.get_package_detail(
            session, detail.package_root_id
        )
        revision: PackageRevision | None = await pkg_repo.get_revision(
            session, detail.draft_revision_id
        )
        if pkg_root is None or pkg_detail is None or revision is None:
            raise CandidateNotReady("The draft package is missing.")
        check_head_revision(pkg_root.current_revision_id, expected_head_revision_id)
        if revision.approval_state == ApprovalState.REJECTED:
            raise DependencyUnresolved("This revision was rejected; create a new attempt.")

        previous_approval = revision.approval_state
        revision.approval_state = ApprovalState.APPROVED
        pkg_detail.visibility_scope = VisibilityScope.PUBLISHED
        pkg_root.row_version += 1
        approval_repo.add_approval_decision(
            session,
            target_entity_id=pkg_root.entity_id,
            target_kind=_PACKAGE_TARGET_KIND,
            decision=ApprovalState.APPROVED,
            target_revision_id=revision.revision_id,
            approver_principal_id=actor.principal_id,
            prior_state=str(previous_approval),
            new_state=str(ApprovalState.APPROVED),
            note=note,
            policy_context={"action": "approve_and_publish", "request_id": detail.entity_id},
        )
        previous = detail.state
        detail.state = target_state
        root.row_version += 1
        _audit_and_outbox(
            session,
            actor,
            event_kind="approval_granted",
            target_kind=_PACKAGE_TARGET_KIND,
            entity_id=pkg_root.entity_id,
            revision_id=revision.revision_id,
            previous_state=str(previous),
            new_state=str(detail.state),
            action="approval_granted",
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="revision_published",
            target_kind=_PACKAGE_TARGET_KIND,
            entity_id=pkg_root.entity_id,
            revision_id=revision.revision_id,
            previous_state=str(VisibilityScope.PRIVATE),
            new_state=str(VisibilityScope.PUBLISHED),
            action="revision_published",
        )
        return _publish_result(detail)

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "approve_and_publish", "request_id": request_id},
        operation=_op,
    )


def _publish_result(detail: PackageRequest) -> dict[str, Any]:
    return {
        "request_id": detail.entity_id,
        "package_root_id": detail.package_root_id,
        "revision_id": detail.draft_revision_id,
        "approval_state": str(ApprovalState.APPROVED),
        "visibility_scope": str(VisibilityScope.PUBLISHED),
        "state": str(detail.state),
    }


async def _enqueue_stub_job(
    session: AsyncSession, actor: Actor, *, queue: str, kind: str, request_id: str
) -> Job:
    """Insert a durable job row (CR-09 source of truth) and mark it succeeded.

    V1 stub: the worker pipeline is Future-Dev, so the job completes in-transaction.
    The durable row still records the work and survives browser close/logout.
    """
    from entropia.infrastructure.queues.enqueue import enqueue_job

    job = enqueue_job(
        session,
        queue=queue,
        payload={"kind": kind, "request_id": request_id},
        actor_principal_id=actor.principal_id,
        correlation_id=actor.correlation_id or None,
    )
    job.status = JobStatus.SUCCEEDED
    return job


__all__ = [
    "approve_and_publish",
    "create_draft_from_candidate",
    "create_package_request",
    "request_package_revision",
    "run_precheck",
    "start_baseline_parse",
    "start_package_validation_run",
    "submit_candidate_generation",
    "upload_baseline_asset",
]
