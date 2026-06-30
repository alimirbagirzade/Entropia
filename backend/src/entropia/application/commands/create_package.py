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
from entropia.application.queries import esp as esp_query
from entropia.domain.create_package import (
    CreatePackageState,
    CreationMode,
    PrecheckScanStatus,
    SourceKind,
    SourceLanguage,
    clean_declared_dependencies,
    context_hash,
    ensure_can_approve_publish,
    ensure_can_create_request,
    ensure_can_operate_request,
    next_request_state,
    normalize_request,
    source_hash,
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
from entropia.shared.concurrency import check_head_revision
from entropia.shared.errors import (
    CandidateNotReady,
    CandidateStale,
    DependencyUnresolved,
    PackageRequestNotFound,
    PrecheckBlocked,
    PrecheckStale,
    RationaleFamilyNotActive,
    RequestVersionConflict,
    ResolverAdapterIncompatible,
    ResolverNotResolved,
    ResolverSignatureMismatch,
    ValidationError,
)

_REQUEST_TARGET_KIND = "package_request"
_PACKAGE_TARGET_KIND = "package"
_SCANNER_VERSION = "stub-declared-1.0"
_RESOLVE_ERRORS = (ResolverNotResolved, ResolverSignatureMismatch, ResolverAdapterIncompatible)


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
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create an immutable Create-Package request (Send step 1, doc 06 §5, §7).

    Validates field requiredness (type/mode/language/runtime/output contract) and,
    for Indicator/Condition, a resolvable ACTIVE Rationale Family; ESP requests
    take the system classification (personal family ignored). Description requests
    start ``precheck_not_applicable``; code requests start ``requested`` and must
    pass Pre-Check before candidate generation.
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
                status=PrecheckScanStatus.NOT_APPLICABLE,
                registry_fingerprint="sha256:not_applicable",
                next_state=CreatePackageState.PRECHECK_NOT_APPLICABLE,
            )

        detected = [str(dep["key"]) for dep in detail.declared_dependencies]
        resolved_refs, missing_calls = await _resolve_declared(
            session, detail.declared_dependencies, detail.target_runtime
        )
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
        # V1 stub: the candidate completes synchronously with the request's output
        # contract; a real worker would write the generated implementation artifact.
        candidate_payload = {"request_id": root.entity_id, "context_hash": detail.context_hash}
        candidate_hash = f"sha256:{content_hash(candidate_payload)}"
        detail.candidate_hash = candidate_hash
        detail.candidate_output_contract = detail.output_contract
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
            "candidate_hash": candidate_hash,
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
        # Legality FIRST (L2): an un-approvable state raises before any row mutation.
        # Only DRAFT_CREATED / ELIGIBLE_FOR_APPROVAL have an APPROVED edge; states
        # like validation_running / experimental must reach eligible_for_approval.
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
    "run_precheck",
    "submit_candidate_generation",
]
