"""Rationale Families persistence (doc 10 §9.1, DOMAIN_MODEL §2.7).

The Root is the shared ``entity_registry`` (entity_type="rationale_family") with a
``rationale_family_root`` detail row; these helpers create/append immutable
``rationale_family_revision`` rows and maintain the ``package_rationale_assignment``
current-projection edge. ``create_family`` is async because it creates the registry
Root AND child rows in one unit-of-work: the root is flushed BEFORE the detail/
revision rows are added, since SQLAlchemy does not derive parent-before-child INSERT
order from a bare ``ForeignKey`` (no ``relationship()`` on the generic registry; L1).
Sync mutators add rows and never commit; async readers return ORM rows.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import DeletionState, PackageKind
from entropia.domain.rationale.enums import AssignmentTargetKind, RationaleAssignmentState
from entropia.domain.revision.hashing import content_hash
from entropia.domain.revision.head import next_revision_no
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    PackageRationaleAssignment,
    PackageRoot,
    RationaleFamilyRevision,
    RationaleFamilyRoot,
)
from entropia.shared.ids import new_id

ENTITY_TYPE = "rationale_family"
_PACKAGE_ENTITY_TYPE = "package"


def _family_content_hash(
    *,
    display_name: str,
    normalized_name: str,
    subfamilies: list[str],
    compatible_output_types: list[str],
) -> str:
    return content_hash(
        {
            "display_name": display_name,
            "normalized_name": normalized_name,
            "subfamilies": subfamilies,
            "compatible_output_types": compatible_output_types,
        }
    )


async def create_family(
    session: AsyncSession,
    *,
    owner_principal_id: str | None,
    created_by_principal_id: str | None,
    display_name: str,
    normalized_name: str,
    subfamilies: list[str],
    compatible_output_types: list[str],
    display_color: str,
    change_note: str | None = None,
    lifecycle_state: str | None = "active",
) -> tuple[EntityRegistry, RationaleFamilyRoot, RationaleFamilyRevision]:
    """Create the registry Root + ``rationale_family_root`` detail + first revision.

    The root is flushed BEFORE the detail/revision rows are added so the
    ``entity_id`` FK is satisfiable at flush time (L1).
    """
    entity_id = new_id("rf")
    root = EntityRegistry(
        entity_id=entity_id,
        entity_type=ENTITY_TYPE,
        owner_principal_id=owner_principal_id,
        created_by_principal_id=created_by_principal_id,
        lifecycle_state=lifecycle_state,
        deletion_state=DeletionState.ACTIVE,
        current_revision_id=None,
        row_version=1,
    )
    session.add(root)
    await session.flush()
    detail = RationaleFamilyRoot(entity_id=entity_id, display_color=display_color)
    session.add(detail)
    revision = RationaleFamilyRevision(
        revision_id=new_id("rfrev"),
        entity_id=entity_id,
        revision_no=next_revision_no(None),
        parent_revision_id=None,
        display_name=display_name,
        normalized_name=normalized_name,
        subfamilies_json=subfamilies,
        compatible_output_types_json=compatible_output_types,
        change_note=change_note,
        content_hash=_family_content_hash(
            display_name=display_name,
            normalized_name=normalized_name,
            subfamilies=subfamilies,
            compatible_output_types=compatible_output_types,
        ),
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    # Persist the head pointer so a same-transaction uniqueness query (which joins
    # on current_revision_id) sees this family even if autoflush is off (MEDIUM-1).
    await session.flush()
    return root, detail, revision


async def append_family_revision(
    session: AsyncSession,
    root: EntityRegistry,
    *,
    display_name: str,
    normalized_name: str,
    subfamilies: list[str],
    compatible_output_types: list[str],
    created_by_principal_id: str | None,
    change_note: str | None = None,
) -> RationaleFamilyRevision:
    """Insert revision N+1, advance the head pointer + row_version."""
    prior_no = await _max_revision_no(session, root.entity_id)
    revision = RationaleFamilyRevision(
        revision_id=new_id("rfrev"),
        entity_id=root.entity_id,
        revision_no=next_revision_no(prior_no),
        parent_revision_id=root.current_revision_id,
        display_name=display_name,
        normalized_name=normalized_name,
        subfamilies_json=subfamilies,
        compatible_output_types_json=compatible_output_types,
        change_note=change_note,
        content_hash=_family_content_hash(
            display_name=display_name,
            normalized_name=normalized_name,
            subfamilies=subfamilies,
            compatible_output_types=compatible_output_types,
        ),
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    root.row_version += 1
    return revision


async def get_family_root(session: AsyncSession, entity_id: str) -> EntityRegistry | None:
    """Return the registry Root iff it is a rationale family."""
    root = await session.get(EntityRegistry, entity_id)
    if root is None or root.entity_type != ENTITY_TYPE:
        return None
    return root


async def get_family_detail(session: AsyncSession, entity_id: str) -> RationaleFamilyRoot | None:
    return await session.get(RationaleFamilyRoot, entity_id)


async def get_family_revision(
    session: AsyncSession, revision_id: str
) -> RationaleFamilyRevision | None:
    return await session.get(RationaleFamilyRevision, revision_id)


async def find_active_or_reserved_by_name(
    session: AsyncSession, normalized_name: str, *, exclude_entity_id: str | None = None
) -> tuple[EntityRegistry, RationaleFamilyRevision] | None:
    """Find a non-purged family whose CURRENT revision matches ``normalized_name``.

    Returns ``(root, current_revision)`` so the command can map an ACTIVE match to
    NAME_CONFLICT and a soft-deleted match to NAME_RESERVED (doc 10 §10.1). The
    family being renamed is excluded via ``exclude_entity_id``.
    """
    stmt = (
        select(EntityRegistry, RationaleFamilyRevision)
        .join(
            RationaleFamilyRevision,
            RationaleFamilyRevision.revision_id == EntityRegistry.current_revision_id,
        )
        .where(
            EntityRegistry.entity_type == ENTITY_TYPE,
            EntityRegistry.deletion_state != DeletionState.PURGED,
            RationaleFamilyRevision.normalized_name == normalized_name,
        )
    )
    if exclude_entity_id is not None:
        stmt = stmt.where(EntityRegistry.entity_id != exclude_entity_id)
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    return row[0], row[1]


async def list_active_family_heads(
    session: AsyncSession, *, cursor: str | None, limit: int
) -> Sequence[tuple[EntityRegistry, RationaleFamilyRoot, RationaleFamilyRevision]]:
    """Active family roots with their detail + current revision, cursor by entity_id."""
    stmt = (
        select(EntityRegistry, RationaleFamilyRoot, RationaleFamilyRevision)
        .join(RationaleFamilyRoot, RationaleFamilyRoot.entity_id == EntityRegistry.entity_id)
        .join(
            RationaleFamilyRevision,
            RationaleFamilyRevision.revision_id == EntityRegistry.current_revision_id,
        )
        .where(
            EntityRegistry.entity_type == ENTITY_TYPE,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
        )
    )
    if cursor is not None:
        stmt = stmt.where(EntityRegistry.entity_id > cursor)
    stmt = stmt.order_by(EntityRegistry.entity_id.asc()).limit(limit)
    return [(r[0], r[1], r[2]) for r in (await session.execute(stmt)).all()]


async def count_family_roots(session: AsyncSession) -> int:
    """Total family roots (any deletion state) — used as a stable color ordinal."""
    stmt = select(func.count()).where(EntityRegistry.entity_type == ENTITY_TYPE)
    return int((await session.execute(stmt)).scalar_one())


async def list_assignable_package_heads(
    session: AsyncSession, *, kinds: Collection[PackageKind], cursor: str | None, limit: int
) -> Sequence[tuple[EntityRegistry, PackageRoot]]:
    """Active rationale-assignable package roots + detail, cursor by entity_id."""
    stmt = (
        select(EntityRegistry, PackageRoot)
        .join(PackageRoot, PackageRoot.entity_id == EntityRegistry.entity_id)
        .where(
            EntityRegistry.entity_type == _PACKAGE_ENTITY_TYPE,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
            PackageRoot.package_kind.in_(list(kinds)),
        )
    )
    if cursor is not None:
        stmt = stmt.where(EntityRegistry.entity_id > cursor)
    stmt = stmt.order_by(EntityRegistry.entity_id.asc()).limit(limit)
    return [(r[0], r[1]) for r in (await session.execute(stmt)).all()]


async def assignment_table_fingerprint(
    session: AsyncSession, *, kinds: Collection[PackageKind]
) -> str:
    """Deterministic version token over all active assignable packages' heads.

    Changes whenever any assignable package gains a new revision, so a concurrent
    package change invalidates a staged batch (doc 10 §5, §8.4 expected_table_version).
    Pairs ``(entity_id, current_revision_id)`` are sorted for a stable hash.
    """
    stmt = (
        select(EntityRegistry.entity_id, EntityRegistry.current_revision_id)
        .join(PackageRoot, PackageRoot.entity_id == EntityRegistry.entity_id)
        .where(
            EntityRegistry.entity_type == _PACKAGE_ENTITY_TYPE,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
            PackageRoot.package_kind.in_(list(kinds)),
        )
        .order_by(EntityRegistry.entity_id.asc())
    )
    pairs = [[eid, rev] for eid, rev in (await session.execute(stmt)).all()]
    return content_hash(pairs)


async def count_active_family_assignments(session: AsyncSession, family_id: str) -> int:
    """How many current-projection rows still point at this family as ASSIGNED.

    Soft-delete preflight (doc 20 §10, RATIONALE_FAMILY_IN_USE): a family with any
    active assignment needs a repair/unassign plan before it can enter Trash.
    ``assigned_to_deleted_family`` rows are historical flags, not active use.
    """
    stmt = select(func.count()).where(
        PackageRationaleAssignment.rationale_family_id == family_id,
        PackageRationaleAssignment.assignment_state == RationaleAssignmentState.ASSIGNED,
    )
    return int((await session.execute(stmt)).scalar_one())


async def get_assignment(
    session: AsyncSession, *, target_kind: AssignmentTargetKind, target_root_id: str
) -> PackageRationaleAssignment | None:
    stmt = select(PackageRationaleAssignment).where(
        PackageRationaleAssignment.target_kind == target_kind,
        PackageRationaleAssignment.target_root_id == target_root_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert_assignment(
    session: AsyncSession,
    *,
    target_kind: AssignmentTargetKind,
    target_root_id: str,
    target_revision_id: str,
    rationale_family_id: str | None,
    rationale_family_revision_id: str | None,
    rationale_display_snapshot: dict[str, str] | None,
    assignment_state: RationaleAssignmentState,
    updated_by_principal_id: str | None,
) -> PackageRationaleAssignment:
    """Insert or update the one current-projection row for a target."""
    existing = await get_assignment(session, target_kind=target_kind, target_root_id=target_root_id)
    if existing is None:
        row = PackageRationaleAssignment(
            assignment_id=new_id("pra"),
            target_kind=target_kind,
            target_root_id=target_root_id,
            target_revision_id=target_revision_id,
            rationale_family_id=rationale_family_id,
            rationale_family_revision_id=rationale_family_revision_id,
            rationale_display_snapshot=rationale_display_snapshot,
            assignment_state=assignment_state,
            updated_by_principal_id=updated_by_principal_id,
        )
        session.add(row)
        return row
    existing.target_revision_id = target_revision_id
    existing.rationale_family_id = rationale_family_id
    existing.rationale_family_revision_id = rationale_family_revision_id
    existing.rationale_display_snapshot = rationale_display_snapshot
    existing.assignment_state = assignment_state
    existing.updated_by_principal_id = updated_by_principal_id
    return existing


async def _max_revision_no(session: AsyncSession, entity_id: str) -> int | None:
    stmt = select(func.max(RationaleFamilyRevision.revision_no)).where(
        RationaleFamilyRevision.entity_id == entity_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


__all__ = [
    "ENTITY_TYPE",
    "append_family_revision",
    "assignment_table_fingerprint",
    "count_family_roots",
    "create_family",
    "find_active_or_reserved_by_name",
    "get_assignment",
    "get_family_detail",
    "get_family_revision",
    "get_family_root",
    "list_active_family_heads",
    "list_assignable_package_heads",
    "upsert_assignment",
]
