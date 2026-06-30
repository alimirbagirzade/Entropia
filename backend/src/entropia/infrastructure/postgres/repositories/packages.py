"""Shared package persistence (doc 09 §2.5, DC1/DC6).

The Root is the shared ``entity_registry`` (entity_type="package") with a
``package_root`` detail row; these helpers create/append immutable
``package_revision`` rows. ``create_package`` is async because it creates the
registry Root AND child rows in one unit-of-work: the root is flushed BEFORE the
detail/revision rows are added, since SQLAlchemy does not derive parent-before-
child INSERT order from a bare ``ForeignKey`` (no ``relationship()`` on the
generic registry). Sync mutators mirror ``repositories/entities.py`` (no commit);
async readers return ORM rows for the queries layer.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import (
    ApprovalState,
    DeletionState,
    PackageKind,
    VisibilityScope,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.revision.hashing import content_hash
from entropia.domain.revision.head import next_revision_no
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    PackageRevision,
    PackageRoot,
)
from entropia.shared.ids import new_id

ENTITY_TYPE = "package"


async def create_package(
    session: AsyncSession,
    *,
    owner_principal_id: str | None,
    created_by_principal_id: str | None,
    package_kind: PackageKind,
    input_contract: dict[str, Any],
    output_contract: dict[str, Any],
    dependency_snapshot: dict[str, Any],
    visibility_scope: VisibilityScope = VisibilityScope.PRIVATE,
    rationale_family_snapshot: dict[str, Any] | None = None,
    validation_state: PackageValidationState = PackageValidationState.PENDING,
    approval_state: ApprovalState = ApprovalState.DRAFT,
    change_note: str | None = None,
    derived_from_revision_id: str | None = None,
    lifecycle_state: str | None = "active",
) -> tuple[EntityRegistry, PackageRoot, PackageRevision]:
    """Create the registry Root + ``package_root`` detail + first revision.

    The root is flushed BEFORE the detail/revision rows are added so the
    ``entity_id`` FK is satisfiable at flush time (L1/DC6).
    """
    entity_id = new_id("pkg")
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
    detail = PackageRoot(
        entity_id=entity_id,
        package_kind=package_kind,
        visibility_scope=visibility_scope,
        derived_from_revision_id=derived_from_revision_id,
    )
    session.add(detail)
    revision = PackageRevision(
        revision_id=new_id("pkgrev"),
        entity_id=entity_id,
        revision_no=next_revision_no(None),
        parent_revision_id=None,
        supersedes_revision_id=None,
        package_kind=package_kind,
        input_contract=input_contract,
        output_contract=output_contract,
        dependency_snapshot=dependency_snapshot,
        rationale_family_snapshot=rationale_family_snapshot,
        validation_state=validation_state,
        approval_state=approval_state,
        validation_summary=None,
        content_hash=content_hash(
            {
                "input_contract": input_contract,
                "output_contract": output_contract,
                "dependency_snapshot": dependency_snapshot,
            }
        ),
        change_note=change_note,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    return root, detail, revision


async def append_package_revision(
    session: AsyncSession,
    root: EntityRegistry,
    *,
    package_kind: PackageKind,
    input_contract: dict[str, Any],
    output_contract: dict[str, Any],
    dependency_snapshot: dict[str, Any],
    created_by_principal_id: str | None,
    rationale_family_snapshot: dict[str, Any] | None = None,
    validation_state: PackageValidationState = PackageValidationState.PENDING,
    approval_state: ApprovalState = ApprovalState.DRAFT,
    change_note: str | None = None,
    supersedes_revision_id: str | None = None,
) -> PackageRevision:
    """Insert revision N+1, advance the head pointer + row_version."""
    prior_no = await _max_revision_no(session, root.entity_id)
    revision = PackageRevision(
        revision_id=new_id("pkgrev"),
        entity_id=root.entity_id,
        revision_no=next_revision_no(prior_no),
        parent_revision_id=root.current_revision_id,
        supersedes_revision_id=supersedes_revision_id or root.current_revision_id,
        package_kind=package_kind,
        input_contract=input_contract,
        output_contract=output_contract,
        dependency_snapshot=dependency_snapshot,
        rationale_family_snapshot=rationale_family_snapshot,
        validation_state=validation_state,
        approval_state=approval_state,
        validation_summary=None,
        content_hash=content_hash(
            {
                "input_contract": input_contract,
                "output_contract": output_contract,
                "dependency_snapshot": dependency_snapshot,
            }
        ),
        change_note=change_note,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    root.row_version += 1
    return revision


async def get_package_root(session: AsyncSession, entity_id: str) -> EntityRegistry | None:
    """Return the registry Root iff it is a package."""
    root = await session.get(EntityRegistry, entity_id)
    if root is None or root.entity_type != ENTITY_TYPE:
        return None
    return root


async def get_package_detail(session: AsyncSession, entity_id: str) -> PackageRoot | None:
    return await session.get(PackageRoot, entity_id)


async def get_revision(session: AsyncSession, revision_id: str) -> PackageRevision | None:
    return await session.get(PackageRevision, revision_id)


async def list_packages(
    session: AsyncSession,
    *,
    package_kind: PackageKind | None = None,
    limit: int = 50,
) -> Sequence[PackageRevision]:
    """Latest (head) revision rows for active packages, optional kind filter."""
    stmt = (
        select(PackageRevision)
        .join(EntityRegistry, EntityRegistry.entity_id == PackageRevision.entity_id)
        .where(
            EntityRegistry.entity_type == ENTITY_TYPE,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
            PackageRevision.revision_id == EntityRegistry.current_revision_id,
        )
        .order_by(PackageRevision.created_at.desc())
        .limit(limit)
    )
    if package_kind is not None:
        stmt = stmt.where(PackageRevision.package_kind == package_kind)
    return list((await session.execute(stmt)).scalars().all())


async def _max_revision_no(session: AsyncSession, entity_id: str) -> int | None:
    stmt = select(func.max(PackageRevision.revision_no)).where(
        PackageRevision.entity_id == entity_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


__all__ = [
    "ENTITY_TYPE",
    "append_package_revision",
    "create_package",
    "get_package_detail",
    "get_package_root",
    "get_revision",
    "list_packages",
]
