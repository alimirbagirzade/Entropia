"""Rationale Families read-side queries (doc 10 §3, §4, §7).

Authentication-gated: Guests get neither the family registry nor the assignment
table (doc 10 §2 "Guest ... active registry veya assignment tablosu dönmez") — the
query raises UNAUTHENTICATED before returning any data. The shared-editing
exception means every authenticated actor sees the same shared projections, so
there is no per-row owner filter here (unlike market/research/ESP lists).

Current assignment is derived from each package head revision's pinned
``rationale_family_snapshot`` (the source of truth); a snapshot whose family root
is now soft-deleted is surfaced as ``assigned_to_deleted_family`` (doc 10 §8.5,
§9.2). All return values are JSON-safe dicts.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.rationale import RATIONALE_ASSIGNABLE_PACKAGE_KINDS, RationaleAssignmentState
from entropia.infrastructure.postgres.models import EntityRegistry, RationaleFamilyRevision
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.shared.errors import NotFoundError
from entropia.shared.pagination import PageParams


def _family_dict(
    root: EntityRegistry, color: str, revision: RationaleFamilyRevision
) -> dict[str, Any]:
    return {
        "entity_id": root.entity_id,
        "current_revision_id": revision.revision_id,
        "revision_no": revision.revision_no,
        "display_name": revision.display_name,
        "normalized_name": revision.normalized_name,
        "subfamilies": list(revision.subfamilies_json or []),
        "compatible_output_types": list(revision.compatible_output_types_json or []),
        "display_color": color,
        "created_by_actor_id": root.created_by_principal_id,
        "row_version": root.row_version,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
    }


async def list_families(
    session: AsyncSession,
    actor: Actor,
    params: PageParams,
    *,
    state: str = "active",
) -> dict[str, Any]:
    """List ACTIVE Family cards, cursor-paginated (doc 10 §3, §7 "Open page").

    Only the active projection is exposed here; soft-deleted families live in the
    Admin-only Trash surface. The shared exception makes the same list visible to
    every authenticated actor.
    """
    require_authenticated(actor)
    rows = await rationale_repo.list_active_family_heads(
        session, cursor=params.cursor, limit=params.limit + 1
    )
    has_more = len(rows) > params.limit
    page = rows[: params.limit]
    next_cursor = page[-1][0].entity_id if has_more and page else None
    return {
        "data": [
            _family_dict(root, detail.display_color, revision) for root, detail, revision in page
        ],
        "meta": {"cursor": next_cursor, "has_more": has_more},
    }


async def get_family(session: AsyncSession, actor: Actor, *, entity_id: str) -> dict[str, Any]:
    """Return the active Family detail + current revision (doc 10 §7 "Edit")."""
    require_authenticated(actor)
    root = await rationale_repo.get_family_root(session, entity_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise NotFoundError(f"Rationale Family '{entity_id}' not found.")
    detail = await rationale_repo.get_family_detail(session, entity_id)
    revision = await rationale_repo.get_family_revision(session, root.current_revision_id or "")
    if detail is None or revision is None:
        raise NotFoundError(f"Rationale Family '{entity_id}' has no current revision.")
    return _family_dict(root, detail.display_color, revision)


async def list_package_assignments(
    session: AsyncSession, actor: Actor, params: PageParams
) -> dict[str, Any]:
    """The Package Rationale Assignment table (doc 10 §3.2, §7 "Open page").

    Lists active rationale-assignable packages (Indicator + Condition in V1) with
    their CURRENT family assignment derived from the head revision snapshot. The
    ``meta.table_version`` is the optimistic-concurrency token a batch save must
    echo back as ``expected_table_version``.
    """
    require_authenticated(actor)
    rows = await rationale_repo.list_assignable_package_heads(
        session,
        kinds=RATIONALE_ASSIGNABLE_PACKAGE_KINDS,
        cursor=params.cursor,
        limit=params.limit + 1,
    )
    has_more = len(rows) > params.limit
    page = rows[: params.limit]
    data = [await _assignment_row(session, root, detail.package_kind) for root, detail in page]
    next_cursor = page[-1][0].entity_id if has_more and page else None
    table_version = await rationale_repo.assignment_table_fingerprint(
        session, kinds=RATIONALE_ASSIGNABLE_PACKAGE_KINDS
    )
    return {
        "data": data,
        "meta": {
            "cursor": next_cursor,
            "has_more": has_more,
            "table_version": table_version,
        },
    }


async def _assignment_row(
    session: AsyncSession, root: EntityRegistry, package_kind: Any
) -> dict[str, Any]:
    head = await pkg_repo.get_revision(session, root.current_revision_id or "")
    snapshot = (head.rationale_family_snapshot if head is not None else None) or {}
    family_id = snapshot.get("rationale_family_id")
    state, family_active, current_name = await _assignment_view(session, snapshot)
    return {
        "package_root_id": root.entity_id,
        "package_kind": str(package_kind),
        "package_name": (head.input_contract.get("name") if head is not None else None),
        "current_package_revision_id": root.current_revision_id,
        "rationale_family_id": family_id,
        "rationale_family_revision_id": snapshot.get("rationale_family_revision_id"),
        "current_family_name": current_name,
        "assignment_state": str(state),
        "family_active": family_active,
    }


async def _assignment_view(
    session: AsyncSession, snapshot: dict[str, Any]
) -> tuple[RationaleAssignmentState, bool, str | None]:
    """Resolve a package's pinned family snapshot to its CURRENT projection.

    ``current_family_name`` reflects the family's live head revision (so a rename is
    visible without re-pinning every package — doc 10 §9.1 "current_family_name").
    A soft-deleted family keeps its historical pinned name for context and flags
    ``assigned_to_deleted_family`` (doc 10 §8.5).
    """
    family_id = snapshot.get("rationale_family_id")
    if family_id is None:
        return RationaleAssignmentState.UNASSIGNED, True, None
    family_root = await rationale_repo.get_family_root(session, family_id)
    if family_root is not None and family_root.deletion_state == DeletionState.ACTIVE:
        current = await rationale_repo.get_family_revision(
            session, family_root.current_revision_id or ""
        )
        name = current.display_name if current is not None else snapshot.get("display_name")
        return RationaleAssignmentState.ASSIGNED, True, name
    return RationaleAssignmentState.ASSIGNED_TO_DELETED_FAMILY, False, snapshot.get("display_name")


__all__ = [
    "get_family",
    "list_families",
    "list_package_assignments",
]
