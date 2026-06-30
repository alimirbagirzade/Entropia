"""Mainboard composition-plane persistence helpers (doc 01; DOMAIN_MODEL §2.2).

``create_workspace`` and ``create_work_object`` are async because each creates
the registry Root AND child rows in one unit-of-work: the root is flushed BEFORE
the detail/revision rows are added, since SQLAlchemy does not derive
parent-before-child INSERT order from a bare ``ForeignKey`` (L1/DC6 — there is no
``relationship()`` on the generic registry). These helpers add rows and flush as
needed; they NEVER commit (the caller's tx owns the commit).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.mainboard.enums import MainboardItemKind, WorkspaceKind
from entropia.domain.revision.hashing import content_hash
from entropia.domain.revision.head import next_revision_no
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    MainboardCompositionSnapshot,
    MainboardWorkingItem,
    MainboardWorkspace,
    WorkObjectRevision,
    WorkObjectRoot,
)
from entropia.shared.ids import new_id

WORKSPACE_ENTITY_TYPE = "mainboard_workspace"
WORK_OBJECT_ENTITY_TYPE = "work_object"

_POSITION_STEP = 10


def _revision_content_hash(
    *,
    object_kind: MainboardItemKind,
    payload: dict[str, Any],
    available_time: datetime | None,
) -> str:
    """Stable content hash for a work object revision."""
    return content_hash(
        {
            "object_kind": object_kind.value,
            "payload": payload,
            "available_time": available_time.isoformat() if available_time is not None else None,
        }
    )


async def create_workspace(
    session: AsyncSession,
    *,
    owner_principal_id: str | None,
    created_by_principal_id: str | None,
    workspace_kind: WorkspaceKind,
    title: str | None = None,
    is_default: bool = True,
    lifecycle_state: str | None = "active",
) -> tuple[EntityRegistry, MainboardWorkspace]:
    """Create the registry Root + ``mainboard_workspace`` detail (FK-safe).

    The root is flushed BEFORE the detail row is added so the ``entity_id`` FK is
    satisfiable at flush time (L1).
    """
    entity_id = new_id("mbws")
    root = EntityRegistry(
        entity_id=entity_id,
        entity_type=WORKSPACE_ENTITY_TYPE,
        owner_principal_id=owner_principal_id,
        created_by_principal_id=created_by_principal_id,
        lifecycle_state=lifecycle_state,
        deletion_state=DeletionState.ACTIVE,
        current_revision_id=None,
        row_version=1,
    )
    session.add(root)
    await session.flush()
    detail = MainboardWorkspace(
        entity_id=entity_id,
        workspace_kind=workspace_kind,
        title=title,
        is_default=is_default,
        status="active",
        composition_hash=None,
        row_version=1,
    )
    session.add(detail)
    return root, detail


async def create_work_object(
    session: AsyncSession,
    *,
    owner_principal_id: str | None,
    created_by_principal_id: str | None,
    object_kind: MainboardItemKind,
    payload: dict[str, Any],
    source_provenance: dict[str, Any] | None = None,
    available_time: datetime | None = None,
    lifecycle_state: str | None = "active",
) -> tuple[EntityRegistry, WorkObjectRoot, WorkObjectRevision]:
    """Create the registry Root + ``work_object_root`` detail + first revision.

    The root is flushed BEFORE the detail/revision rows are added (L1).
    """
    entity_id = new_id("wo")
    root = EntityRegistry(
        entity_id=entity_id,
        entity_type=WORK_OBJECT_ENTITY_TYPE,
        owner_principal_id=owner_principal_id,
        created_by_principal_id=created_by_principal_id,
        lifecycle_state=lifecycle_state,
        deletion_state=DeletionState.ACTIVE,
        current_revision_id=None,
        row_version=1,
    )
    session.add(root)
    await session.flush()
    detail = WorkObjectRoot(entity_id=entity_id, object_kind=object_kind)
    session.add(detail)
    revision = WorkObjectRevision(
        revision_id=new_id("worev"),
        entity_id=entity_id,
        revision_no=next_revision_no(None),
        parent_revision_id=None,
        supersedes_revision_id=None,
        object_kind=object_kind,
        payload=payload,
        source_provenance=source_provenance,
        validation_summary=None,
        available_time=available_time,
        content_hash=_revision_content_hash(
            object_kind=object_kind, payload=payload, available_time=available_time
        ),
        change_note=None,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    return root, detail, revision


async def append_work_object_revision(
    session: AsyncSession,
    root: EntityRegistry,
    *,
    object_kind: MainboardItemKind,
    payload: dict[str, Any],
    source_provenance: dict[str, Any] | None = None,
    available_time: datetime | None = None,
    created_by_principal_id: str | None,
    change_note: str | None = None,
) -> WorkObjectRevision:
    """Insert revision N+1, advance the head pointer + row_version."""
    prior_no = await _max_revision_no(session, root.entity_id)
    revision = WorkObjectRevision(
        revision_id=new_id("worev"),
        entity_id=root.entity_id,
        revision_no=next_revision_no(prior_no),
        parent_revision_id=root.current_revision_id,
        supersedes_revision_id=root.current_revision_id,
        object_kind=object_kind,
        payload=payload,
        source_provenance=source_provenance,
        validation_summary=None,
        available_time=available_time,
        content_hash=_revision_content_hash(
            object_kind=object_kind, payload=payload, available_time=available_time
        ),
        change_note=change_note,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    root.row_version += 1
    return revision


async def get_work_object_root(session: AsyncSession, root_id: str) -> EntityRegistry | None:
    """Return the registry Root iff it is a work object."""
    root = await session.get(EntityRegistry, root_id)
    if root is None or root.entity_type != WORK_OBJECT_ENTITY_TYPE:
        return None
    return root


async def get_work_object_detail(session: AsyncSession, entity_id: str) -> WorkObjectRoot | None:
    return await session.get(WorkObjectRoot, entity_id)


async def get_work_object_revision(
    session: AsyncSession, revision_id: str
) -> WorkObjectRevision | None:
    return await session.get(WorkObjectRevision, revision_id)


async def get_workspace(session: AsyncSession, entity_id: str) -> EntityRegistry | None:
    """Return the registry Root iff it is a mainboard workspace."""
    root = await session.get(EntityRegistry, entity_id)
    if root is None or root.entity_type != WORKSPACE_ENTITY_TYPE:
        return None
    return root


async def get_workspace_detail(session: AsyncSession, entity_id: str) -> MainboardWorkspace | None:
    return await session.get(MainboardWorkspace, entity_id)


async def find_default_workspace(
    session: AsyncSession, *, owner_principal_id: str
) -> MainboardWorkspace | None:
    """Return the actor's active default workspace detail row, if any."""
    stmt = (
        select(MainboardWorkspace)
        .join(EntityRegistry, EntityRegistry.entity_id == MainboardWorkspace.entity_id)
        .where(
            EntityRegistry.entity_type == WORKSPACE_ENTITY_TYPE,
            EntityRegistry.owner_principal_id == owner_principal_id,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
            MainboardWorkspace.is_default.is_(True),
        )
        .order_by(MainboardWorkspace.entity_id)
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def attach_item(
    session: AsyncSession,
    *,
    workspace_entity_id: str,
    item_kind: MainboardItemKind,
    work_object_root_id: str,
    pinned_revision_id: str,
    position_index: int,
    created_by_principal_id: str | None,
) -> MainboardWorkingItem:
    """Insert a new working item (always enabled, row_version=1). No commit."""
    item = MainboardWorkingItem(
        item_id=new_id("mbi"),
        workspace_entity_id=workspace_entity_id,
        item_kind=item_kind,
        work_object_root_id=work_object_root_id,
        pinned_revision_id=pinned_revision_id,
        position_index=position_index,
        is_enabled=True,
        display_label_override=None,
        row_version=1,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(item)
    return item


async def get_item(session: AsyncSession, item_id: str) -> MainboardWorkingItem | None:
    return await session.get(MainboardWorkingItem, item_id)


async def list_active_items(
    session: AsyncSession, workspace_entity_id: str
) -> Sequence[MainboardWorkingItem]:
    """All working items of a workspace whose work object root is ACTIVE,
    ordered by ``position_index`` (soft-deleted roots are filtered out)."""
    stmt = (
        select(MainboardWorkingItem)
        .join(EntityRegistry, EntityRegistry.entity_id == MainboardWorkingItem.work_object_root_id)
        .where(
            MainboardWorkingItem.workspace_entity_id == workspace_entity_id,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
        )
        .order_by(MainboardWorkingItem.position_index, MainboardWorkingItem.item_id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_items_for_root(
    session: AsyncSession, work_object_root_id: str
) -> Sequence[MainboardWorkingItem]:
    """All working items (any workspace) pinned to a given work object root."""
    stmt = select(MainboardWorkingItem).where(
        MainboardWorkingItem.work_object_root_id == work_object_root_id
    )
    return list((await session.execute(stmt)).scalars().all())


async def next_position_index(session: AsyncSession, workspace_entity_id: str) -> int:
    """The next position slot for a workspace: max + step (or step if empty)."""
    stmt = select(func.max(MainboardWorkingItem.position_index)).where(
        MainboardWorkingItem.workspace_entity_id == workspace_entity_id
    )
    current = (await session.execute(stmt)).scalar_one_or_none()
    return _POSITION_STEP if current is None else current + _POSITION_STEP


async def create_snapshot(
    session: AsyncSession,
    *,
    workspace_entity_id: str,
    composition_hash: str,
    item_manifest: dict[str, Any],
    created_by_principal_id: str | None,
    capital_mode_snapshot: dict[str, Any] | None = None,
) -> MainboardCompositionSnapshot:
    """Insert an immutable composition snapshot (readiness unevaluated). No commit."""
    snapshot = MainboardCompositionSnapshot(
        snapshot_id=new_id("mbsnap"),
        workspace_entity_id=workspace_entity_id,
        composition_hash=composition_hash,
        item_manifest=item_manifest,
        capital_mode_snapshot=capital_mode_snapshot,
        readiness_state="unevaluated",
        readiness_report_id=None,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(snapshot)
    return snapshot


async def _max_revision_no(session: AsyncSession, entity_id: str) -> int | None:
    stmt = select(func.max(WorkObjectRevision.revision_no)).where(
        WorkObjectRevision.entity_id == entity_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


__all__ = [
    "WORKSPACE_ENTITY_TYPE",
    "WORK_OBJECT_ENTITY_TYPE",
    "append_work_object_revision",
    "attach_item",
    "create_snapshot",
    "create_work_object",
    "create_workspace",
    "find_default_workspace",
    "get_item",
    "get_work_object_detail",
    "get_work_object_revision",
    "get_work_object_root",
    "get_workspace",
    "get_workspace_detail",
    "list_active_items",
    "list_items_for_root",
    "next_position_index",
]
