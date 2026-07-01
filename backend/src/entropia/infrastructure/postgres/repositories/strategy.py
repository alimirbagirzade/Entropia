"""Strategy persistence helpers (Stage 3b, doc 02; DOMAIN_MODEL §2.3).

``create_strategy`` is async because it creates the registry Root AND detail rows
in one unit-of-work: the root is flushed BEFORE the detail/draft rows are added,
since SQLAlchemy does not derive parent-before-child INSERT order from a bare
``ForeignKey`` (L1). A Strategy shares its registry Root with a work object
(``entity_type='work_object'`` + ``work_object_root.object_kind='strategy'``) so
3a's ``attach_mainboard_item`` / ``pin_revision`` bind it unchanged; the typed
config lives in ``strategy_root`` / ``strategy_revision``.

These helpers add rows and flush as needed; they NEVER commit (the caller's tx
owns the commit).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.revision.head import next_revision_no
from entropia.domain.strategy.enums import (
    DependencyRoleEnum,
    ReferencedEntityTypeEnum,
    StrategyLifecycleStateEnum,
    ValidationStatusEnum,
)
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    StrategyEditorDraft,
    StrategyRevision,
    StrategyRevisionReference,
    StrategyRoot,
    WorkObjectRoot,
)
from entropia.infrastructure.postgres.repositories.mainboard import WORK_OBJECT_ENTITY_TYPE
from entropia.shared.ids import new_id


async def create_strategy(
    session: AsyncSession,
    *,
    owner_principal_id: str,
    created_by_principal_id: str,
    display_name: str,
    rationale_family_id: str | None,
    initial_payload: dict[str, Any],
) -> tuple[EntityRegistry, StrategyRoot, WorkObjectRoot, StrategyEditorDraft]:
    """Create the shared registry Root + strategy/work-object details + draft (FK-safe).

    The registry Root is ``entity_type='work_object'`` so the Mainboard can attach
    it once a revision exists; ``object_kind='strategy'`` marks it a Strategy. No
    revision is created yet (both head pointers stay NULL until the first Save).
    The root is flushed BEFORE detail/draft rows are added (L1).
    """
    entity_id = new_id("strat")
    root = EntityRegistry(
        entity_id=entity_id,
        entity_type=WORK_OBJECT_ENTITY_TYPE,
        owner_principal_id=owner_principal_id,
        created_by_principal_id=created_by_principal_id,
        lifecycle_state=StrategyLifecycleStateEnum.DRAFT.value,
        deletion_state=DeletionState.ACTIVE,
        current_revision_id=None,
        row_version=1,
    )
    session.add(root)
    await session.flush()

    work_object = WorkObjectRoot(entity_id=entity_id, object_kind=MainboardItemKind.STRATEGY)
    session.add(work_object)

    strategy_root = StrategyRoot(
        entity_id=entity_id,
        current_revision_id=None,
        current_row_version=1,
        lifecycle_state=StrategyLifecycleStateEnum.DRAFT,
        display_name=display_name,
        rationale_family_id=rationale_family_id,
        created_by_principal=created_by_principal_id,
        updated_by_principal=created_by_principal_id,
    )
    session.add(strategy_root)
    # Flush the strategy_root BEFORE the draft: strategy_editor_draft.strategy_root_id
    # FKs strategy_root, and SQLAlchemy cannot derive parent-before-child order from a
    # bare ForeignKey (no relationship()). Without this flush the draft may INSERT
    # first and violate the FK (L1).
    await session.flush()

    draft = StrategyEditorDraft(
        draft_id=new_id("stratdraft"),
        strategy_root_id=entity_id,
        last_saved_revision_id=None,
        payload=initial_payload,
        is_dirty=True,
        row_version=0,
        created_by_principal=created_by_principal_id,
        updated_by_principal=created_by_principal_id,
    )
    session.add(draft)
    return root, strategy_root, work_object, draft


async def append_strategy_revision(
    session: AsyncSession,
    strategy_root: StrategyRoot,
    *,
    payload: dict[str, Any],
    config_hash: str,
    validation_status: ValidationStatusEnum,
    created_by_principal_id: str,
    lifecycle_snapshot: str | None = None,
    family_snapshot: str | None = None,
    validation_errors: list[dict[str, Any]] | None = None,
) -> StrategyRevision:
    """Insert immutable revision N+1 and advance the strategy head pointer.

    ``revision_number`` is derived from the current max for the entity (INSERT-only
    chain). Repoints ``strategy_root.current_revision_id`` and bumps
    ``current_row_version``. The caller must flush before adding references so the
    ``strategy_revision_id`` FK is satisfiable (L1).
    """
    prior_no = await _max_revision_number(session, strategy_root.entity_id)
    revision = StrategyRevision(
        revision_id=new_id("stratrev"),
        entity_id=strategy_root.entity_id,
        revision_number=next_revision_no(prior_no),
        parent_revision_id=strategy_root.current_revision_id,
        payload=payload,
        config_hash=config_hash,
        content_hash=config_hash,
        schema_version="v1",
        validation_status=validation_status,
        validation_errors=validation_errors,
        lifecycle_snapshot=lifecycle_snapshot,
        family_snapshot=family_snapshot,
        created_by_principal=created_by_principal_id,
    )
    session.add(revision)
    strategy_root.current_revision_id = revision.revision_id
    strategy_root.current_row_version += 1
    return revision


async def add_strategy_reference(
    session: AsyncSession,
    *,
    strategy_revision_id: str,
    referenced_entity_type: ReferencedEntityTypeEnum,
    referenced_root_id: str,
    referenced_revision_id: str,
    referenced_content_hash: str,
    dependency_role: DependencyRoleEnum,
    position_in_graph: int,
) -> StrategyRevisionReference:
    """Insert an immutable pinned dependency edge. No commit."""
    reference = StrategyRevisionReference(
        reference_id=new_id("stratref"),
        strategy_revision_id=strategy_revision_id,
        referenced_entity_type=referenced_entity_type,
        referenced_root_id=referenced_root_id,
        referenced_revision_id=referenced_revision_id,
        referenced_content_hash=referenced_content_hash,
        dependency_role=dependency_role,
        position_in_graph=position_in_graph,
    )
    session.add(reference)
    return reference


async def get_strategy_registry_root(
    session: AsyncSession, entity_id: str
) -> EntityRegistry | None:
    """Return the registry Root iff it backs a Strategy (has a strategy_root detail)."""
    detail = await session.get(StrategyRoot, entity_id)
    if detail is None:
        return None
    return await session.get(EntityRegistry, entity_id)


async def get_strategy_root(session: AsyncSession, entity_id: str) -> StrategyRoot | None:
    return await session.get(StrategyRoot, entity_id)


async def get_strategy_revision(session: AsyncSession, revision_id: str) -> StrategyRevision | None:
    return await session.get(StrategyRevision, revision_id)


async def list_strategy_revisions(
    session: AsyncSession, entity_id: str, *, limit: int = 100
) -> Sequence[StrategyRevision]:
    """All revisions for a strategy, newest first."""
    stmt = (
        select(StrategyRevision)
        .where(StrategyRevision.entity_id == entity_id)
        .order_by(StrategyRevision.revision_number.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_strategy_draft(session: AsyncSession, draft_id: str) -> StrategyEditorDraft | None:
    return await session.get(StrategyEditorDraft, draft_id)


async def list_references(
    session: AsyncSession, strategy_revision_id: str
) -> Sequence[StrategyRevisionReference]:
    """All pinned dependency edges of a revision, ordered by graph position."""
    stmt = (
        select(StrategyRevisionReference)
        .where(StrategyRevisionReference.strategy_revision_id == strategy_revision_id)
        .order_by(StrategyRevisionReference.position_in_graph)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _max_revision_number(session: AsyncSession, entity_id: str) -> int | None:
    stmt = select(func.max(StrategyRevision.revision_number)).where(
        StrategyRevision.entity_id == entity_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


__all__ = [
    "add_strategy_reference",
    "append_strategy_revision",
    "create_strategy",
    "get_strategy_draft",
    "get_strategy_registry_root",
    "get_strategy_revision",
    "get_strategy_root",
    "list_references",
    "list_strategy_revisions",
]
