"""Create Package + Pre-Check commands (docs 06 §7, 07 §8; CR-02; Stage 2e).

Each command runs in one transaction supplied by the request dependency and NEVER
commits (mirrors Stage 1/2a/2b/2c/2d). The shape per mutation is: authorization +
pure validation (OUTSIDE) -> idempotent body { optimistic-concurrency + state-
machine legality checks INSIDE (L2) -> repo mutation } -> audit + outbox.

Reuse: the shared Package model from 2c (``pkg_repo.create_package``, async/FK-safe)
for Create Draft Package and the publish head; the ESP resolver registry from 2c
(``esp_query.resolve_embedded_dependency``) for Pre-Check dependency resolution;
the durable job row (``enqueue_job``) as the source of truth (CR-09).

Async plane (F-01a + F-01b): Pre-Check, candidate generation and Validation Tests are
ADMISSIONS here — each enqueues a durable QUEUED job and returns immediately; the
compute, the durable evidence and the terminal state advance happen in the
``default``-queue worker (``application/jobs/create_package.py``), so a browser close /
logout never cancels the work and the UI never shows a result before it exists
(Finding F-01). Baseline parse stays in-transaction (a bounded read of an already-
uploaded CSV), and the revision loop regenerates its deterministic candidate inline.

V1 boundaries (Future-Dev): the candidate generator is deterministic, not an LLM, and
the Pre-Check "parser" reads the request's explicitly declared canonical TA keys (a real
PineScript parser replaces it later) and resolves each against the trusted ESP registry.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.application.jobs.create_package import (
    generate_and_store_candidate,
    registry_fingerprint,
)
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
    source_hash,
)
from entropia.domain.create_package.validation import VALIDATOR_VERSION
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
    ValidationError,
    ValidationRequired,
    ValidationStale,
)

_REQUEST_TARGET_KIND = "package_request"
_PACKAGE_TARGET_KIND = "package"
# The Create-Package workers ride the general-purpose plane consumed by the ``default,
# maintenance`` worker (docker-compose); the compute semantics for every kind live in
# jobs/create_package.py.
_WORKER_QUEUE = "default"
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
    # Compatibility declarations (doc 06 §4): both are persisted with the immutable
    # request and validated against real rows — a Compatible Family must reference an
    # ACTIVE Rationale Family (never auto-created), and an Explicit Indicator Link is
    # pinned to an existing indicator root+revision (name-only selection prohibited).
    compatible_ids = await _validate_compatible_families(
        session, normalized.package_kind, family_id, compatible_rationale_family_ids
    )
    linked = await _validate_linked_indicator(session, normalized.package_kind, linked_indicator)
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
            compatible_rationale_family_ids=compatible_ids,
            linked_indicator=linked,
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
            "compatible_rationale_family_ids": compatible_ids,
            "linked_indicator": linked,
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


async def _validate_compatible_families(
    session: AsyncSession,
    kind: PackageKind,
    family_id: str | None,
    compatible_rationale_family_ids: list[str] | None,
) -> list[str]:
    """Resolve the Compatible Family declaration to a clean list of ACTIVE family ids.

    A Compatible Family is a discovery hint (doc 06 §4: "Must not auto-create any
    Family"): each referenced family must already exist and be ACTIVE. ESP has no
    rationale family, so it carries none. The assigned family is implicit ("Same
    Rationale Family") and duplicates are dropped, so the stored list is exactly the
    distinct OTHER families the package declares compatibility with.
    """
    if kind == PackageKind.EMBEDDED_SYSTEM or not compatible_rationale_family_ids:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for candidate_id in compatible_rationale_family_ids:
        if candidate_id == family_id or candidate_id in seen:
            continue
        family_root = await rationale_repo.get_family_root(session, candidate_id)
        if family_root is None or family_root.deletion_state != DeletionState.ACTIVE:
            raise RationaleFamilyNotActive()
        seen.add(candidate_id)
        result.append(candidate_id)
    return result


async def _validate_linked_indicator(
    session: AsyncSession,
    kind: PackageKind,
    linked_indicator: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Pin an Explicit Indicator Link to an existing indicator root + revision.

    doc 06 §4: the link is used only when a Condition Package requires a specific
    Indicator Package's output, and "Choosing an indicator by display name alone is
    not sufficient; the saved dependency is the root and revision identifier." So a
    non-Condition request rejects the link, and a link must resolve to a real
    indicator revision that belongs to the named root (never name-only/latest).

    V1 honest boundary: existence + kind + root↔revision linkage are enforced;
    output/input contract-match against the condition is Future-Dev.
    """
    if linked_indicator is None:
        return None
    if kind != PackageKind.CONDITION:
        raise ValidationError("An Explicit Indicator Link is only allowed for a Condition package.")
    root_id = linked_indicator.get("linked_indicator_package_root_id")
    revision_id = linked_indicator.get("linked_indicator_package_revision_id")
    if not isinstance(root_id, str) or not isinstance(revision_id, str):
        raise ValidationError(
            "An Explicit Indicator Link requires an indicator root id and revision id."
        )
    if not root_id or not revision_id:
        raise ValidationError(
            "An Explicit Indicator Link requires an indicator root id and revision id."
        )
    pkg_root = await pkg_repo.get_package_root(session, root_id)
    revision = await pkg_repo.get_revision(session, revision_id)
    if (
        pkg_root is None
        or pkg_root.deletion_state != DeletionState.ACTIVE
        or revision is None
        or revision.entity_id != root_id
        or revision.package_kind != PackageKind.INDICATOR
    ):
        raise ValidationError("The linked indicator revision was not found.")
    return {
        "linked_indicator_package_root_id": root_id,
        "linked_indicator_package_revision_id": revision_id,
    }


async def run_precheck(
    session: AsyncSession,
    actor: Actor,
    *,
    request_id: str,
    expected_request_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admit a Pre-Check dependency scan for a request (doc 07 §8, §10; Finding F-01).

    Enqueues a DURABLE Pre-Check job and returns ``queued`` immediately — the scan runs in
    the ``default``-queue worker (``jobs.create_package.run_precheck_job``), so a browser
    close / logout never cancels it and the UI never shows a result before the work is
    done. The immutable scan, the request state advance (precheck_passed / blocked /
    not_applicable, or precheck_failed on worker failure) and the ``resource.changed``
    outbox are produced by the worker. The OCC guard (``expected_request_version``) and the
    row lock live INSIDE the idempotent body; the row_version is bumped at admission so a
    concurrent re-submit with a stale token is rejected.
    """
    root, detail = await _require_request(session, actor, request_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        _check_request_version(root, expected_request_version)
        job = _enqueue_create_package_job(
            session, actor, kind="precheck", request_id=root.entity_id
        )
        # Advance the request_version so expected_request_version detects a concurrent
        # admission (the token is otherwise inert until the worker records the scan).
        root.row_version += 1
        return {
            "request_id": root.entity_id,
            "job_id": job.job_id,
            "status": str(PrecheckScanStatus.CHECKING),
            "state": str(detail.state),
            # The scan does not exist yet; these placeholders keep the response
            # assignable to the client's PrecheckActionResult contract. The overlay shows
            # an in-flight state until the worker's resource.changed refetch lands the
            # real scan (never a synthesized PASSED/BLOCKED).
            "scan_id": "",
            "attempt_no": 0,
            "resolved": 0,
            "missing": [],
            "warnings": [],
            "registry_fingerprint": "",
            "request_version": root.row_version,
        }

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


async def submit_candidate_generation(
    session: AsyncSession,
    actor: Actor,
    *,
    request_id: str,
    expected_request_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Send: gate Pre-Check, then ADMIT candidate generation (doc 06 §5, doc 07 §9.3;
    Finding F-01).

    The candidate-generation GATE (PC-13) is enforced server-side AT ADMISSION, so a
    blocked / stale Pre-Check still fails fast with the typed 409 the client expects: a
    code request needs a current PASSED scan that is not stale against the live registry;
    a description request needs no scan.

    Past the gate this is an admission, not the compute: it enqueues a DURABLE job and
    returns ``candidate_generating`` immediately. The deterministic generation, the
    candidate pins and the advance to ``candidate_ready`` (or the durable
    ``candidate_failed`` on worker failure) are produced by
    ``jobs.create_package.run_candidate_generation_job`` — closing the browser never
    cancels it, and the response never carries a candidate hash that does not exist yet.
    """
    root, detail = await _require_request(session, actor, request_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        _check_request_version(root, expected_request_version)
        await _enforce_precheck_gate(session, detail)

        job = _enqueue_create_package_job(
            session, actor, kind="candidate_generation", request_id=root.entity_id
        )
        previous = detail.state
        detail.state = next_request_state(detail.state, CreatePackageState.CANDIDATE_GENERATING)
        # The admission itself advances the request_version so a concurrent submit with
        # a stale token is rejected (the token is otherwise inert until the worker lands).
        root.row_version += 1
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
        return {
            "request_id": root.entity_id,
            "state": str(detail.state),
            # No candidate exists yet. The empty hash keeps the response assignable to
            # the client's CandidateActionResult contract while making it impossible to
            # chain a draft against a candidate the worker has not produced.
            "candidate_hash": "",
            "job_id": job.job_id,
            "request_version": root.row_version,
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
    current_fingerprint = await registry_fingerprint(session, detail.declared_dependencies)
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
    """ADMIT a Validation Tests run over a draft revision (doc 06 §4.4/§5/§7;
    Finding F-01). Drives ``validation_running`` -> ``eligible_for_approval`` /
    ``revision_required`` through the durable worker.

    Gate: the request must be in ``draft_created`` (has a draft revision) — checked here
    so an un-validatable state raises before any write. The admission appends the
    immutable run row in its ``queued`` state (the spec's queued/running row states, so
    the UI has a real evidence row from the first render), enqueues a DURABLE job and
    returns immediately.

    The seven mandatory checks then run in the durable worker
    (``jobs.create_package.run_validation_job`` -> ``jobs.package_validation``), which
    gathers the draft's real facts and produces an honest verdict (F-13): a
    ``not_executed`` / ``blocked`` mandatory check is NOT a pass, so only a fully-passing
    run reaches ``eligible_for_approval``; any unsatisfied check — and a worker failure —
    routes to ``revision_required``. The OCC guard + the row lock live INSIDE the
    idempotent body; the row_version is bumped at admission.
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

        run = await cp_repo.append_validation_run(
            session,
            request_entity_id=root.entity_id,
            package_root_id=detail.package_root_id,
            draft_revision_id=detail.draft_revision_id,
            # The run pins the exact candidate it will certify, so regenerating the
            # candidate makes this evidence stale on read (validation_fresh).
            candidate_hash=detail.candidate_hash,
            validator_version=VALIDATOR_VERSION,
            checks=[],
            status=ValidationRunStatus.QUEUED,
            job_id=None,
            correlation_id=actor.correlation_id or None,
            created_by_principal_id=actor.principal_id,
        )
        await session.flush()
        job = _enqueue_create_package_job(
            session,
            actor,
            kind="validation",
            request_id=root.entity_id,
            payload_extra={"validation_run_id": run.validation_run_id},
        )
        run.job_id = job.job_id
        detail.current_validation_run_id = run.validation_run_id
        root.row_version += 1
        _audit_and_outbox(
            session,
            actor,
            event_kind="validation_run_started",
            target_kind=_PACKAGE_TARGET_KIND,
            entity_id=detail.package_root_id,
            revision_id=detail.draft_revision_id,
            previous_state=str(previous),
            new_state=str(detail.state),
            action="validation_run_started",
        )
        return {
            "request_id": root.entity_id,
            "validation_run_id": run.validation_run_id,
            "attempt_no": run.attempt_no,
            "status": str(run.status),
            "state": str(detail.state),
            # No verdict exists yet — the checks land when the worker completes.
            "checks": run.checks,
            "job_id": job.job_id,
            "request_version": root.row_version,
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

        await generate_and_store_candidate(session, detail)
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

        job = await _enqueue_completed_job(
            session, actor, queue=_WORKER_QUEUE, kind="baseline_parse", request_id=root.entity_id
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


def _enqueue_create_package_job(
    session: AsyncSession,
    actor: Actor,
    *,
    kind: str,
    request_id: str,
    payload_extra: dict[str, Any] | None = None,
) -> Job:
    """Insert a durable QUEUED Create-Package job (CR-09 source of truth) for the real
    ``default``-queue worker (F-01a/F-01b).

    The ``kind`` discriminator is what ``jobs.create_package.run_create_package_job``
    routes on. Does not commit or dispatch — the route dispatches the actor after the
    admission tx commits (mirrors the other worker routes), and the job is NEVER marked
    succeeded here: the compute and its durable outcome belong to the worker.
    """
    from entropia.infrastructure.queues.enqueue import enqueue_job

    return enqueue_job(
        session,
        queue=_WORKER_QUEUE,
        payload={"kind": kind, "request_id": request_id, **(payload_extra or {})},
        actor_principal_id=actor.principal_id,
        correlation_id=actor.correlation_id or None,
    )


async def _enqueue_completed_job(
    session: AsyncSession, actor: Actor, *, queue: str, kind: str, request_id: str
) -> Job:
    """Insert a durable job row (CR-09 source of truth) and mark it succeeded.

    Used by the baseline parse alone: the parse is a bounded read of an already-uploaded
    CSV that completes inside the request transaction, so the durable row records work
    that is genuinely done — it is not a placeholder for an absent worker.
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
