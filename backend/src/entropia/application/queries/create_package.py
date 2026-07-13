"""Create Package + Pre-Check read-side queries (docs 06 §9, 07 §10).

Role-aware: a request is visible to its owner or an Admin (doc 06 §2); the scan
artifact inherits the request's visibility. All return values are JSON-safe dicts
(``str(enum)``, ``.isoformat()``). The projection is what the UI rehydrates from —
never from local editor state. Staleness shown here is the cheap context-hash
comparison; the authoritative registry-race re-check happens at the Send gate.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.create_package.enums import (
    PrecheckScanStatus,
    SourceKind,
    ValidationRunStatus,
)
from entropia.domain.identity import Actor
from entropia.domain.identity import policy as identity_policy
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import (
    DependencyScan,
    EntityRegistry,
    PackageRequest,
    PackageValidationRun,
)
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.shared.errors import AccessDeniedError, PackageRequestNotFound
from entropia.shared.pagination import PageParams


def _request_dict(
    root: EntityRegistry,
    detail: PackageRequest,
    scan: DependencyScan | None,
    run: PackageValidationRun | None,
) -> dict[str, Any]:
    precheck_fresh = (
        scan is not None
        and scan.status == PrecheckScanStatus.PASSED
        and scan.context_hash == detail.context_hash
    )
    validation_fresh = (
        run is not None
        and run.status == ValidationRunStatus.PASSED
        and run.candidate_hash == detail.candidate_hash
    )
    return {
        "request_id": detail.entity_id,
        "package_type": str(detail.package_kind),
        "creation_mode": str(detail.creation_mode),
        "source_kind": str(detail.source_kind),
        "source_language": str(detail.source_language) if detail.source_language else None,
        "target_runtime": str(detail.target_runtime),
        "output_contract": detail.output_contract,
        "rationale_family_id": detail.rationale_family_id,
        "compatible_rationale_family_ids": detail.compatible_rationale_family_ids,
        "declared_dependencies": detail.declared_dependencies,
        "state": str(detail.state),
        "context_hash": detail.context_hash,
        "request_version": root.row_version,
        "owner_principal_id": root.owner_principal_id,
        "current_scan": _scan_summary(scan) if scan is not None else None,
        "precheck_fresh": precheck_fresh,
        "package_root_id": detail.package_root_id,
        "draft_revision_id": detail.draft_revision_id,
        "current_validation_run": _validation_summary(run) if run is not None else None,
        "validation_fresh": validation_fresh,
        "can_generate_candidate": _can_generate(detail, scan, precheck_fresh),
        "created_at": root.created_at.isoformat() if root.created_at else None,
    }


def _validation_summary(run: PackageValidationRun) -> dict[str, Any]:
    return {
        "validation_run_id": run.validation_run_id,
        "attempt_no": run.attempt_no,
        "status": str(run.status),
        "validator_version": run.validator_version,
        "checks": run.checks,
        "candidate_hash": run.candidate_hash,
        "draft_revision_id": run.draft_revision_id,
    }


def _can_generate(
    detail: PackageRequest, scan: DependencyScan | None, precheck_fresh: bool
) -> bool:
    """Read-only hint mirroring the server-side Send gate (authoritative server-side)."""
    if detail.source_kind == SourceKind.DESCRIPTION:
        return True
    return precheck_fresh


def _scan_summary(scan: DependencyScan) -> dict[str, Any]:
    return {
        "scan_id": scan.scan_id,
        "attempt_no": scan.attempt_no,
        "status": str(scan.status),
        "detected": scan.detected_calls,
        "resolved": scan.resolved_refs,
        "missing": scan.missing_calls,
        "scanner_version": scan.scanner_version,
        "registry_fingerprint": scan.registry_fingerprint,
        "context_hash": scan.context_hash,
    }


async def get_package_request(
    session: AsyncSession, actor: Actor, *, request_id: str
) -> dict[str, Any]:
    """Return the request projection (request + current scan + draft refs)."""
    root = await cp_repo.get_request_root(session, request_id)
    detail = await cp_repo.get_request_detail(session, request_id)
    if root is None or detail is None or root.deletion_state != DeletionState.ACTIVE:
        raise PackageRequestNotFound(f"Package request '{request_id}' not found.")
    _ensure_can_view(actor, root)
    scan = await cp_repo.get_current_scan(session, detail)
    run = await cp_repo.get_current_validation_run(session, detail)
    return _request_dict(root, detail, scan, run)


async def get_dependency_scan(
    session: AsyncSession, actor: Actor, *, scan_id: str
) -> dict[str, Any]:
    """Return the immutable scan detail, re-checking view permission server-side."""
    scan = await cp_repo.get_scan(session, scan_id)
    if scan is None:
        raise PackageRequestNotFound(f"Dependency scan '{scan_id}' not found.")
    root = await cp_repo.get_request_root(session, scan.request_entity_id)
    if root is None:
        raise PackageRequestNotFound(f"Dependency scan '{scan_id}' not found.")
    _ensure_can_view(actor, root)
    summary = _scan_summary(scan)
    summary.update(
        {
            "request_id": scan.request_entity_id,
            "unsupported": scan.unsupported_calls,
            "source_hash": scan.source_hash,
            "language": scan.language,
            "job_id": scan.job_id,
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        }
    )
    return summary


async def get_validation_run(
    session: AsyncSession, actor: Actor, *, validation_run_id: str
) -> dict[str, Any]:
    """Return the immutable validation-run evidence, re-checking view permission."""
    run = await cp_repo.get_validation_run(session, validation_run_id)
    if run is None:
        raise PackageRequestNotFound(f"Validation run '{validation_run_id}' not found.")
    root = await cp_repo.get_request_root(session, run.request_entity_id)
    if root is None:
        raise PackageRequestNotFound(f"Validation run '{validation_run_id}' not found.")
    _ensure_can_view(actor, root)
    summary = _validation_summary(run)
    summary.update(
        {
            "request_id": run.request_entity_id,
            "package_root_id": run.package_root_id,
            "job_id": run.job_id,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
    )
    return summary


async def list_package_requests(
    session: AsyncSession, actor: Actor, params: PageParams
) -> dict[str, Any]:
    """List the actor's own requests (Admins see all), newest first, cursor-paged."""
    identity_policy.require_authenticated(actor)
    stmt = (
        select(EntityRegistry, PackageRequest)
        .join(PackageRequest, PackageRequest.entity_id == EntityRegistry.entity_id)
        .where(
            EntityRegistry.entity_type == cp_repo.ENTITY_TYPE,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
        )
        .order_by(EntityRegistry.entity_id.desc())
    )
    if not actor.is_admin:
        stmt = stmt.where(EntityRegistry.owner_principal_id == actor.principal_id)
    if params.cursor is not None:
        stmt = stmt.where(EntityRegistry.entity_id < params.cursor)
    stmt = stmt.limit(params.limit + 1)

    rows = list((await session.execute(stmt)).all())
    has_more = len(rows) > params.limit
    page = rows[: params.limit]
    next_cursor = page[-1][0].entity_id if has_more and page else None
    return {
        "data": [
            {
                "request_id": detail.entity_id,
                "package_type": str(detail.package_kind),
                "state": str(detail.state),
                "source_kind": str(detail.source_kind),
                "package_root_id": detail.package_root_id,
            }
            for _root, detail in page
        ],
        "meta": {"cursor": next_cursor, "has_more": has_more},
    }


def _ensure_can_view(actor: Actor, root: EntityRegistry) -> None:
    if actor.is_admin:
        return
    if not actor.is_authenticated:
        raise AccessDeniedError()
    if root.owner_principal_id != actor.principal_id:
        raise AccessDeniedError("You can only view your own package requests.")


__all__ = [
    "get_dependency_scan",
    "get_package_request",
    "get_validation_run",
    "list_package_requests",
]
