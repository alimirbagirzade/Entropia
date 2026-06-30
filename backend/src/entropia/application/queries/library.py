"""Package Library catalog read-side queries (doc 08 §3, §4, §9.2).

The catalog is authentication-gated: Guests get no catalog at all (doc 08 §2
"Protected library ... katalog döndürülmez"), so the query raises UNAUTHENTICATED
before returning any data. Visibility is enforced SERVER-SIDE in SQL (ARCHITECTURE
§9.5 "List endpoints exclude unauthorized rows server-side") — admins see every
active root; everyone else sees published/system/explicitly_shared packages plus
their own — so ``has_more``/``cursor`` count the post-visibility set (no
client-side hiding, no under-filled pages). Only the four canonical kinds are
listed (CR-01); soft-deleted roots are never discoverable (a soft-deleted detail
GET returns 404, DOMAIN_MODEL §7). Each row carries the ten-flag permission
projection (doc 08 §4.2) and never fabricates performance metrics for
non-Strategy types (L4 / doc 08 §13). All values are JSON-safe dicts.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from entropia.domain.identity import Actor
from entropia.domain.identity import policy as identity_policy
from entropia.domain.lifecycle.enums import DeletionState, VisibilityScope
from entropia.domain.package.catalog import (
    CATALOG_LIFECYCLE_STATES,
    CATALOG_PACKAGE_KINDS,
    UNASSIGNED,
    CatalogFilters,
)
from entropia.domain.package.permissions import package_permissions
from entropia.infrastructure.postgres.models import (
    DependencyScan,
    EntityRegistry,
    PackageRequest,
    PackageRevision,
    PackageRoot,
)
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.shared.errors import NotFoundError
from entropia.shared.pagination import PageParams

# Visibility scopes a non-admin actor may always read (mirrors identity policy
# ``can_view``: public scopes + explicitly_shared are readable to authenticated
# actors; the row's own owner is added per-request below).
_CATALOG_VISIBLE_SCOPES: tuple[VisibilityScope, ...] = (
    VisibilityScope.PUBLISHED,
    VisibilityScope.SYSTEM,
    VisibilityScope.EXPLICITLY_SHARED,
)

# Catalog performance metrics: only Strategy packages with linked runs can ever
# carry them, and no runs are linked in this stage — so every field is N/A, never
# a fabricated zero (doc 08 §3.2 boxed, L4).
_NOT_APPLICABLE = "not_applicable"
_PERFORMANCE_FIELDS: tuple[str, ...] = (
    "net_profit",
    "max_drawdown",
    "romad",
    "win_rate",
    "trade_count",
    "out_of_sample",
)


async def list_packages(
    session: AsyncSession,
    actor: Actor,
    params: PageParams,
    *,
    filters: CatalogFilters,
) -> dict[str, Any]:
    """List catalog package heads visible to the actor, cursor-paginated.

    Newest-first by ``entity_id`` (a ULID-like, time-sortable key — the platform
    cursor convention). Visibility + facet filters are applied in SQL so the page
    is exactly the authorized, filtered set.
    """
    identity_policy.require_authenticated(actor)
    conditions: list[ColumnElement[bool]] = [
        EntityRegistry.entity_type == pkg_repo.ENTITY_TYPE,
        EntityRegistry.deletion_state == DeletionState.ACTIVE,
        EntityRegistry.lifecycle_state.in_(sorted(CATALOG_LIFECYCLE_STATES)),
        PackageRoot.package_kind.in_(CATALOG_PACKAGE_KINDS),
        *_visibility_conditions(actor),
        *_filter_conditions(filters),
    ]
    if params.cursor is not None:
        conditions.append(EntityRegistry.entity_id < params.cursor)

    stmt = (
        select(EntityRegistry, PackageRoot, PackageRevision)
        .join(PackageRoot, PackageRoot.entity_id == EntityRegistry.entity_id)
        .join(PackageRevision, PackageRevision.revision_id == EntityRegistry.current_revision_id)
        .where(*conditions)
        .order_by(EntityRegistry.entity_id.desc())
        .limit(params.limit + 1)
    )
    rows = list((await session.execute(stmt)).all())
    has_more = len(rows) > params.limit
    page = rows[: params.limit]
    next_cursor = page[-1][0].entity_id if has_more and page else None
    return {
        "data": [_package_row(actor, root, detail, revision) for root, detail, revision in page],
        "meta": {"cursor": next_cursor, "has_more": has_more},
    }


def _visibility_conditions(actor: Actor) -> list[ColumnElement[bool]]:
    """SQL predicate that mirrors identity ``can_view`` for the catalog list."""
    if actor.is_admin:
        return []
    visible = PackageRoot.visibility_scope.in_(_CATALOG_VISIBLE_SCOPES)
    if actor.principal_id is not None:
        return [visible | (EntityRegistry.owner_principal_id == actor.principal_id)]
    return [visible]


def _filter_conditions(filters: CatalogFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.package_kind is not None:
        conditions.append(PackageRoot.package_kind == filters.package_kind)
    if filters.lifecycle_state is not None:
        conditions.append(EntityRegistry.lifecycle_state == filters.lifecycle_state)
    if filters.validation_state is not None:
        conditions.append(PackageRevision.validation_state == filters.validation_state)
    if filters.approval_state is not None:
        conditions.append(PackageRevision.approval_state == filters.approval_state)
    if filters.visibility_scope is not None:
        conditions.append(PackageRoot.visibility_scope == filters.visibility_scope)

    family = filters.rationale_family_id
    family_id_expr = PackageRevision.rationale_family_snapshot.op("->>")("rationale_family_id")
    if family == UNASSIGNED:
        conditions.append(family_id_expr.is_(None))
    elif family is not None:
        conditions.append(family_id_expr == family)

    if filters.query is not None:
        name_expr = PackageRevision.input_contract.op("->>")("name")
        conditions.append(name_expr.ilike(f"%{_escape_like(filters.query)}%", escape="\\"))
    return conditions


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so a search term is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _package_row(
    actor: Actor,
    root: EntityRegistry,
    detail: PackageRoot,
    revision: PackageRevision,
) -> dict[str, Any]:
    snapshot = revision.rationale_family_snapshot or {}
    permissions = package_permissions(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility_scope=str(detail.visibility_scope),
        lifecycle_state=root.lifecycle_state,
        validation_state=revision.validation_state,
        approval_state=revision.approval_state,
    )
    return {
        "entity_id": root.entity_id,
        "package_kind": str(detail.package_kind),
        "name": _package_name(revision.input_contract),
        "current_revision_id": revision.revision_id,
        "revision_no": revision.revision_no,
        "lifecycle_state": root.lifecycle_state,
        "validation_state": str(revision.validation_state),
        "approval_state": str(revision.approval_state),
        "visibility_scope": str(detail.visibility_scope),
        "rationale_family": _pinned_family(snapshot),
        "output_kinds": _output_kinds(revision.output_contract),
        "derived_from_revision_id": detail.derived_from_revision_id,
        "owner_principal_id": root.owner_principal_id,
        "row_version": root.row_version,
        "content_hash": revision.content_hash,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
        "permissions": permissions.as_dict(),
        "performance": _performance_na(),
    }


def _package_name(contract: dict[str, Any]) -> str | None:
    name = contract.get("name") if isinstance(contract, dict) else None
    return name if isinstance(name, str) else None


def _pinned_family(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    family_id = snapshot.get("rationale_family_id")
    if not family_id:
        return None
    return {"id": family_id, "name": snapshot.get("display_name")}


def _output_kinds(contract: dict[str, Any]) -> list[str]:
    if not isinstance(contract, dict):
        return []
    raw = contract.get("output_kinds") or contract.get("kinds") or contract.get("kind")
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def _performance_na() -> dict[str, str]:
    return dict.fromkeys(_PERFORMANCE_FIELDS, _NOT_APPLICABLE)


async def get_package_detail(
    session: AsyncSession, actor: Actor, *, entity_id: str
) -> dict[str, Any]:
    """Return the catalog detail projection, re-checking view permission.

    Re-runs ``can_view`` even for a resource that appeared in the list (doc 08
    §9.2); a soft-deleted or non-package id is a 404 that leaks no metadata.
    Enriches the row with full contracts, dependency snapshot, the live rationale
    family name, Stage-2e provenance, and the revision history.
    """
    identity_policy.require_authenticated(actor)
    root = await pkg_repo.get_package_root(session, entity_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise NotFoundError(f"Package '{entity_id}' not found.")
    detail = await pkg_repo.get_package_detail(session, entity_id)
    if detail is None or detail.package_kind not in CATALOG_PACKAGE_KINDS:
        raise NotFoundError(f"Package '{entity_id}' not found.")
    identity_policy.ensure_can_view(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility=str(detail.visibility_scope),
    )
    revision = await pkg_repo.get_revision(session, root.current_revision_id or "")
    if revision is None:
        raise NotFoundError(f"Package '{entity_id}' has no current revision.")

    data = _package_row(actor, root, detail, revision)
    data["input_contract"] = revision.input_contract
    data["output_contract"] = revision.output_contract
    data["dependency_snapshot"] = revision.dependency_snapshot
    data["validation_summary"] = revision.validation_summary
    data["change_note"] = revision.change_note
    data["rationale_family"] = await _live_family(session, revision.rationale_family_snapshot)
    data["provenance"] = await _provenance(session, entity_id)
    data["revisions"] = await _revision_history(session, entity_id)
    return data


async def _live_family(
    session: AsyncSession, snapshot: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Resolve a pinned family snapshot to its CURRENT name (rename without re-pin).

    A soft-deleted family keeps its pinned historical name and is flagged inactive
    (doc 08 §4.3 section 6; doc 10 §8.5).
    """
    snapshot = snapshot or {}
    family_id = snapshot.get("rationale_family_id")
    if not family_id:
        return None
    pinned_name = snapshot.get("display_name")
    family_root = await rationale_repo.get_family_root(session, family_id)
    if family_root is not None and family_root.deletion_state == DeletionState.ACTIVE:
        current = await rationale_repo.get_family_revision(
            session, family_root.current_revision_id or ""
        )
        live_name = current.display_name if current is not None else pinned_name
        return {
            "id": family_id,
            "name": live_name,
            "pinned_name": pinned_name,
            "family_active": True,
        }
    return {
        "id": family_id,
        "name": pinned_name,
        "pinned_name": pinned_name,
        "family_active": False,
    }


async def _provenance(session: AsyncSession, entity_id: str) -> dict[str, Any] | None:
    """Best-effort Stage-2e creation provenance for a package built via a request."""
    stmt = select(PackageRequest).where(PackageRequest.package_root_id == entity_id).limit(1)
    request = (await session.execute(stmt)).scalars().first()
    if request is None:
        return None
    scan = (
        await session.get(DependencyScan, request.current_scan_id)
        if request.current_scan_id is not None
        else None
    )
    return {
        "request_entity_id": request.entity_id,
        "creation_mode": str(request.creation_mode),
        "source_kind": str(request.source_kind),
        "source_language": (
            str(request.source_language) if request.source_language is not None else None
        ),
        "target_runtime": str(request.target_runtime),
        "draft_revision_id": request.draft_revision_id,
        "scan": _scan_summary(scan),
    }


def _scan_summary(scan: DependencyScan | None) -> dict[str, Any] | None:
    if scan is None:
        return None
    return {
        "scan_id": scan.scan_id,
        "attempt_no": scan.attempt_no,
        "status": str(scan.status),
        "detected_calls": list(scan.detected_calls or []),
        "resolved_refs": list(scan.resolved_refs or []),
        "missing_calls": list(scan.missing_calls or []),
        "unsupported_calls": list(scan.unsupported_calls or []),
        "registry_fingerprint": scan.registry_fingerprint,
        "context_hash": scan.context_hash,
    }


async def _revision_history(
    session: AsyncSession, entity_id: str, *, limit: int = 50
) -> list[dict[str, Any]]:
    stmt = (
        select(PackageRevision)
        .where(PackageRevision.entity_id == entity_id)
        .order_by(PackageRevision.revision_no.desc())
        .limit(limit)
    )
    revisions = (await session.execute(stmt)).scalars().all()
    return [
        {
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "validation_state": str(revision.validation_state),
            "approval_state": str(revision.approval_state),
            "change_note": revision.change_note,
            "created_at": revision.created_at.isoformat() if revision.created_at else None,
        }
        for revision in revisions
    ]


__all__ = [
    "get_package_detail",
    "list_packages",
]
