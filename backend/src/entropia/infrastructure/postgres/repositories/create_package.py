"""Create Package + Pre-Check persistence (docs 06 §9, 07 §10; Stage 2e).

The Root is the shared ``entity_registry`` (entity_type="package_request") with a
mutable ``package_request`` detail row. ``create_request`` is async because it
creates the registry Root AND the detail row in one unit-of-work: the root is
flushed BEFORE the detail row is added, since SQLAlchemy does not derive
parent-before-child INSERT order from a bare ``ForeignKey`` (L1/DC6). Dependency
scans are INSERT-only immutable evidence (append, never UPDATE). Sync mutators add
rows without committing (the request dependency owns the transaction); async
helpers query for the queries layer.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.create_package.enums import (
    BaselineParseStatus,
    CreatePackageState,
    CreationMode,
    PrecheckScanStatus,
    SourceKind,
    SourceLanguage,
    ValidationRunStatus,
)
from entropia.domain.esp.enums import RuntimeAdapter
from entropia.domain.lifecycle.enums import DeletionState, PackageKind
from entropia.infrastructure.postgres.models import (
    BaselineAsset,
    DependencyScan,
    EntityRegistry,
    PackageRequest,
    PackageValidationRun,
)
from entropia.shared.ids import new_id

ENTITY_TYPE = "package_request"


async def create_request(
    session: AsyncSession,
    *,
    owner_principal_id: str | None,
    created_by_principal_id: str | None,
    package_kind: PackageKind,
    creation_mode: CreationMode,
    source_kind: SourceKind,
    source_language: SourceLanguage | None,
    other_language_label: str | None,
    target_runtime: RuntimeAdapter,
    request_body: str,
    source_hash: str,
    context_hash: str,
    output_contract: dict[str, Any],
    rationale_family_id: str | None,
    compatible_rationale_family_ids: list[str],
    linked_indicator: dict[str, Any] | None,
    declared_dependencies: list[dict[str, Any]],
    claims_equivalence: bool = False,
    state: CreatePackageState = CreatePackageState.REQUESTED,
) -> tuple[EntityRegistry, PackageRequest]:
    """Create the registry Root + ``package_request`` detail in one flush (L1/DC6).

    The root is flushed BEFORE the detail row is added so the ``entity_id`` FK is
    satisfiable at flush time. ``row_version`` on the root is the request_version.
    """
    entity_id = new_id("pkgreq")
    root = EntityRegistry(
        entity_id=entity_id,
        entity_type=ENTITY_TYPE,
        owner_principal_id=owner_principal_id,
        created_by_principal_id=created_by_principal_id,
        lifecycle_state="active",
        deletion_state=DeletionState.ACTIVE,
        current_revision_id=None,
        row_version=1,
    )
    session.add(root)
    await session.flush()
    detail = PackageRequest(
        entity_id=entity_id,
        package_kind=package_kind,
        creation_mode=creation_mode,
        source_kind=source_kind,
        source_language=source_language,
        other_language_label=other_language_label,
        target_runtime=target_runtime,
        request_body=request_body,
        source_hash=source_hash,
        context_hash=context_hash,
        output_contract=output_contract,
        rationale_family_id=rationale_family_id,
        compatible_rationale_family_ids=compatible_rationale_family_ids,
        linked_indicator=linked_indicator,
        declared_dependencies=declared_dependencies,
        claims_equivalence=claims_equivalence,
        state=state,
        current_scan_id=None,
        candidate_hash=None,
        candidate_output_contract=None,
        package_root_id=None,
        draft_revision_id=None,
        baseline_asset_id=None,
    )
    session.add(detail)
    return root, detail


async def get_request_root(session: AsyncSession, entity_id: str) -> EntityRegistry | None:
    """Return the registry Root iff it is a package_request."""
    root = await session.get(EntityRegistry, entity_id)
    if root is None or root.entity_type != ENTITY_TYPE:
        return None
    return root


async def get_request_detail(session: AsyncSession, entity_id: str) -> PackageRequest | None:
    return await session.get(PackageRequest, entity_id)


async def append_dependency_scan(
    session: AsyncSession,
    *,
    request_entity_id: str,
    source_hash: str,
    context_hash: str,
    language: str | None,
    scanner_version: str,
    registry_fingerprint: str,
    detected_calls: list[str],
    resolved_refs: list[dict[str, Any]],
    missing_calls: list[dict[str, Any]],
    unsupported_calls: list[dict[str, Any]],
    source_warnings: list[dict[str, Any]],
    status: PrecheckScanStatus,
    job_id: str | None,
    error_detail: dict[str, Any] | None,
    correlation_id: str | None,
    created_by_principal_id: str | None,
) -> DependencyScan:
    """Insert immutable scan ``attempt_no = max+1`` for the request (doc 07 §8)."""
    prior = await _max_scan_attempt(session, request_entity_id)
    scan = DependencyScan(
        scan_id=new_id("dscan"),
        request_entity_id=request_entity_id,
        attempt_no=(prior or 0) + 1,
        source_hash=source_hash,
        context_hash=context_hash,
        language=language,
        scanner_version=scanner_version,
        registry_fingerprint=registry_fingerprint,
        detected_calls=detected_calls,
        resolved_refs=resolved_refs,
        missing_calls=missing_calls,
        unsupported_calls=unsupported_calls,
        source_warnings=source_warnings,
        status=status,
        job_id=job_id,
        error_detail=error_detail,
        correlation_id=correlation_id,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(scan)
    return scan


async def get_scan(session: AsyncSession, scan_id: str) -> DependencyScan | None:
    return await session.get(DependencyScan, scan_id)


async def get_current_scan(session: AsyncSession, detail: PackageRequest) -> DependencyScan | None:
    """The request's current scan (the head pointer), if any."""
    if detail.current_scan_id is None:
        return None
    return await session.get(DependencyScan, detail.current_scan_id)


async def _max_scan_attempt(session: AsyncSession, request_entity_id: str) -> int | None:
    stmt = select(func.max(DependencyScan.attempt_no)).where(
        DependencyScan.request_entity_id == request_entity_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def append_validation_run(
    session: AsyncSession,
    *,
    request_entity_id: str,
    package_root_id: str,
    draft_revision_id: str,
    candidate_hash: str | None,
    validator_version: str,
    checks: list[dict[str, Any]],
    status: ValidationRunStatus,
    job_id: str | None,
    correlation_id: str | None,
    created_by_principal_id: str | None,
) -> PackageValidationRun:
    """Insert immutable validation run ``attempt_no = max+1`` (doc 06 §4.4)."""
    prior = await _max_validation_attempt(session, request_entity_id)
    run = PackageValidationRun(
        validation_run_id=new_id("valrun"),
        request_entity_id=request_entity_id,
        attempt_no=(prior or 0) + 1,
        package_root_id=package_root_id,
        draft_revision_id=draft_revision_id,
        candidate_hash=candidate_hash,
        validator_version=validator_version,
        checks=checks,
        status=status,
        job_id=job_id,
        correlation_id=correlation_id,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(run)
    return run


async def get_validation_run(
    session: AsyncSession, validation_run_id: str
) -> PackageValidationRun | None:
    return await session.get(PackageValidationRun, validation_run_id)


async def get_current_validation_run(
    session: AsyncSession, detail: PackageRequest
) -> PackageValidationRun | None:
    """The request's current validation run (the head pointer), if any."""
    if detail.current_validation_run_id is None:
        return None
    return await session.get(PackageValidationRun, detail.current_validation_run_id)


async def _max_validation_attempt(session: AsyncSession, request_entity_id: str) -> int | None:
    stmt = select(func.max(PackageValidationRun.attempt_no)).where(
        PackageValidationRun.request_entity_id == request_entity_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def append_baseline_asset(
    session: AsyncSession,
    *,
    request_entity_id: str,
    object_key: str,
    content_digest: str,
    size_bytes: int,
    content_type: str | None,
    original_filename: str | None,
    baseline_metadata: dict[str, Any],
    correlation_id: str | None,
    created_by_principal_id: str | None,
) -> BaselineAsset:
    """Insert an immutable baseline upload ``attempt_no = max+1`` (doc 06 §8.3).

    The row starts ``uploaded``; StartBaselineParse transitions the current head to
    ``passed`` (or the parse raises a typed error and this row is left as evidence
    of the upload). A fresh upload is always a new attempt — a prior attempt's
    object key / digest / metadata are never mutated.
    """
    prior = await _max_baseline_attempt(session, request_entity_id)
    asset = BaselineAsset(
        baseline_asset_id=new_id("baseline"),
        request_entity_id=request_entity_id,
        attempt_no=(prior or 0) + 1,
        object_key=object_key,
        content_digest=content_digest,
        size_bytes=size_bytes,
        content_type=content_type,
        original_filename=original_filename,
        baseline_metadata=baseline_metadata,
        parse_status=BaselineParseStatus.UPLOADED,
        parse_report=None,
        parser_version=None,
        parse_job_id=None,
        correlation_id=correlation_id,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(asset)
    return asset


async def get_baseline_asset(session: AsyncSession, baseline_asset_id: str) -> BaselineAsset | None:
    return await session.get(BaselineAsset, baseline_asset_id)


async def get_current_baseline_asset(
    session: AsyncSession, detail: PackageRequest
) -> BaselineAsset | None:
    """The request's current baseline asset (the head pointer), if any."""
    if detail.baseline_asset_id is None:
        return None
    return await session.get(BaselineAsset, detail.baseline_asset_id)


async def _max_baseline_attempt(session: AsyncSession, request_entity_id: str) -> int | None:
    stmt = select(func.max(BaselineAsset.attempt_no)).where(
        BaselineAsset.request_entity_id == request_entity_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


__all__ = [
    "ENTITY_TYPE",
    "append_baseline_asset",
    "append_dependency_scan",
    "append_validation_run",
    "create_request",
    "get_baseline_asset",
    "get_current_baseline_asset",
    "get_current_scan",
    "get_current_validation_run",
    "get_request_detail",
    "get_request_root",
    "get_scan",
    "get_validation_run",
]
