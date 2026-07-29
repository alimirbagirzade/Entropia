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
    BaselineParseStatus,
    PrecheckScanStatus,
    SourceKind,
    ValidationRunStatus,
)
from entropia.domain.identity import Actor
from entropia.domain.identity import policy as identity_policy
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import (
    BaselineAsset,
    DependencyScan,
    EntityRegistry,
    PackageRequest,
    PackageRevision,
    PackageRevisionLink,
    PackageValidationRun,
    RationaleFamilyRevision,
)
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.shared.errors import AccessDeniedError, PackageRequestNotFound
from entropia.shared.pagination import PageParams


def _request_dict(
    root: EntityRegistry,
    detail: PackageRequest,
    scan: DependencyScan | None,
    run: PackageValidationRun | None,
    baseline: BaselineAsset | None,
    revision_links: list[PackageRevisionLink],
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
    baseline_ready = baseline is not None and baseline.parse_status == BaselineParseStatus.PASSED
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
        # Explicit Indicator Link (doc 06 §4): the persisted root+revision pins of a
        # linked indicator dependency (Condition packages), round-tripped so a
        # save→reload preserves the operator's selection. NULL when not linked.
        "linked_indicator": detail.linked_indicator,
        "declared_dependencies": detail.declared_dependencies,
        "state": str(detail.state),
        "context_hash": detail.context_hash,
        "request_version": root.row_version,
        "owner_principal_id": root.owner_principal_id,
        "current_scan": _scan_summary(scan) if scan is not None else None,
        "precheck_fresh": precheck_fresh,
        "package_root_id": detail.package_root_id,
        "draft_revision_id": detail.draft_revision_id,
        # The candidate the durable generation worker pinned (F-01b). The admission no
        # longer returns a hash — it does not exist yet — so this projection is where the
        # client reads the staleness token it passes to Create-Draft.
        "candidate_hash": detail.candidate_hash,
        "current_validation_run": _validation_summary(run) if run is not None else None,
        "validation_fresh": validation_fresh,
        "can_generate_candidate": _can_generate(detail, scan, precheck_fresh),
        # Mode-aware baseline projection (doc 06 §4.4): whether the package claims
        # equivalence, its current baseline, and whether the approval baseline gate
        # is satisfied (a claiming package needs baseline_ready, a non-claiming one
        # never requires it).
        "claims_equivalence": detail.claims_equivalence,
        "current_baseline": _baseline_summary(baseline) if baseline is not None else None,
        "baseline_ready": baseline_ready,
        "baseline_required": bool(detail.claims_equivalence),
        # Revision chain (doc 06 §7/§15). ``revision_attempt_no`` is the attempt the
        # request is ON (1 = the original), so the UI reads "Revision N of M" straight
        # off the projection with M = the same number (the head is always the newest
        # attempt) and each chain entry naming its own attempt. ``parent_revision_ref``
        # / ``prior_validation_run_ref`` are the head pins — the prior attempt's draft
        # revision and validation run survive the head clearing Request Revision does.
        "revision_attempt_no": detail.revision_attempt_no,
        "revision_total_attempts": detail.revision_attempt_no,
        "parent_revision_ref": detail.parent_revision_ref,
        "prior_validation_run_ref": detail.prior_validation_run_ref,
        "revision_chain": [_revision_link_summary(link) for link in revision_links],
        "created_at": root.created_at.isoformat() if root.created_at else None,
    }


def _revision_link_summary(link: PackageRevisionLink) -> dict[str, Any]:
    return {
        "revision_link_id": link.revision_link_id,
        "attempt_no": link.attempt_no,
        "parent_package_root_id": link.parent_package_root_id,
        "parent_revision_ref": link.parent_revision_ref,
        "prior_validation_run_ref": link.prior_validation_run_ref,
        "prior_candidate_hash": link.prior_candidate_hash,
        "prior_state": str(link.prior_state),
        "created_at": link.created_at.isoformat() if link.created_at else None,
    }


def _baseline_summary(asset: BaselineAsset) -> dict[str, Any]:
    return {
        "baseline_asset_id": asset.baseline_asset_id,
        "attempt_no": asset.attempt_no,
        "parse_status": str(asset.parse_status),
        "content_digest": asset.content_digest,
        "size_bytes": asset.size_bytes,
        "original_filename": asset.original_filename,
        "baseline_metadata": asset.baseline_metadata,
        "parse_report": asset.parse_report,
        "parser_version": asset.parser_version,
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
        "warnings": scan.source_warnings,
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
    baseline = await cp_repo.get_current_baseline_asset(session, detail)
    revision_links = await cp_repo.list_revision_links(session, detail.entity_id)
    return _request_dict(root, detail, scan, run, baseline, revision_links)


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


async def get_baseline_asset(
    session: AsyncSession, actor: Actor, *, baseline_asset_id: str
) -> dict[str, Any]:
    """Return the immutable baseline asset + parse report, re-checking view permission."""
    asset = await cp_repo.get_baseline_asset(session, baseline_asset_id)
    if asset is None:
        raise PackageRequestNotFound(f"Baseline asset '{baseline_asset_id}' not found.")
    root = await cp_repo.get_request_root(session, asset.request_entity_id)
    if root is None:
        raise PackageRequestNotFound(f"Baseline asset '{baseline_asset_id}' not found.")
    _ensure_can_view(actor, root)
    summary = _baseline_summary(asset)
    summary.update(
        {
            "request_id": asset.request_entity_id,
            "object_key": asset.object_key,
            "content_type": asset.content_type,
            "parse_job_id": asset.parse_job_id,
            "parsed_at": asset.parsed_at.isoformat() if asset.parsed_at else None,
            "created_at": asset.created_at.isoformat() if asset.created_at else None,
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
    labels = await _request_display_labels(session, [detail for _root, detail in page])
    return {
        "data": [
            {
                "request_id": detail.entity_id,
                "package_type": str(detail.package_kind),
                "state": str(detail.state),
                "source_kind": str(detail.source_kind),
                "package_root_id": detail.package_root_id,
                # F-07 §4.4 — a human name for the request, resolved SERVER-side from
                # what the request actually pins (see ``_request_display_labels``). The
                # Pre-Check picker shows it as the primary identification and keeps the
                # request id as a secondary/copyable token. Null when the request pins
                # nothing nameable yet — the browser then shows the id and never
                # reconstructs a name from it.
                "display_label": labels.get(detail.entity_id),
                # A request has no user-assigned name before C.D.P (doc 06 §510-512:
                # "V18 has no editable field; name is generated after C.D.P"), so the
                # creation time is what distinguishes two same-type requests. Same
                # reasoning §4.4 used to rule Results History NOT a violation. Read off
                # the REGISTRY row, exactly like ``_request_dict`` — the two projections
                # must not report different creation times for the same request.
                "created_at": root.created_at.isoformat() if root.created_at else None,
            }
            for root, detail in page
        ],
        "meta": {"cursor": next_cursor, "has_more": has_more},
    }


async def _request_display_labels(
    session: AsyncSession, details: list[PackageRequest]
) -> dict[str, str]:
    """Resolve ``request_id -> human label`` for a page of requests (F-07 §4.4).

    A Create-Package request carries no name of its own, so the label is taken from the
    named object the request POINTS AT, in falling order of specificity:

    1. the package the request produced — its ``input_contract.name`` (doc 06 §510-512
       generates this at C.D.P);
    2. the Rationale Family the request pins — the family's current ``display_name``.

    Neither is derived from an identifier: both are names a user gave an object the
    request genuinely references. A request that pins neither yields NO entry and the
    caller sends ``display_label: null`` — a fabricated name is never substituted.

    Two batched lookups per page, never one per row.
    """
    if not details:
        return {}
    labels: dict[str, str] = {}

    family_ids = {d.rationale_family_id for d in details if d.rationale_family_id}
    if family_ids:
        family_stmt = select(EntityRegistry.entity_id, RationaleFamilyRevision.display_name).join(
            RationaleFamilyRevision,
            RationaleFamilyRevision.revision_id == EntityRegistry.current_revision_id,
        )
        family_stmt = family_stmt.where(
            EntityRegistry.entity_id.in_(family_ids),
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
        )
        family_names = {
            row[0]: row[1] for row in (await session.execute(family_stmt)).all() if row[1]
        }
        for detail in details:
            name = family_names.get(detail.rationale_family_id or "")
            if name:
                labels[detail.entity_id] = name

    package_ids = {d.package_root_id for d in details if d.package_root_id}
    if package_ids:
        name_expr = PackageRevision.input_contract.op("->>")("name")
        package_stmt = select(EntityRegistry.entity_id, name_expr).join(
            PackageRevision, PackageRevision.revision_id == EntityRegistry.current_revision_id
        )
        package_stmt = package_stmt.where(
            EntityRegistry.entity_id.in_(package_ids),
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
        )
        package_names = {
            row[0]: row[1] for row in (await session.execute(package_stmt)).all() if row[1]
        }
        for detail in details:
            # The produced package outranks the family: it is THIS request's own result,
            # while a family is shared by many requests.
            name = package_names.get(detail.package_root_id or "")
            if name:
                labels[detail.entity_id] = name

    return labels


def _ensure_can_view(actor: Actor, root: EntityRegistry) -> None:
    if actor.is_admin:
        return
    if not actor.is_authenticated:
        raise AccessDeniedError()
    if root.owner_principal_id != actor.principal_id:
        raise AccessDeniedError("You can only view your own package requests.")


__all__ = [
    "get_baseline_asset",
    "get_dependency_scan",
    "get_package_request",
    "get_validation_run",
    "list_package_requests",
]
