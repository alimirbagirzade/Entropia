"""Research Data read-side queries (doc 12 §3, §7).

Role-aware: soft-deleted and unauthorized datasets are excluded server-side, not
by the client. Page access is restricted to Admin/Supervisor/Agent (doc 12 §2).
Cursor pagination uses the "fetch limit+1" pattern. All return values are
JSON-safe dicts so routes can serialize them directly.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity import policy as identity_policy
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.research_data import policy as rd_policy
from entropia.infrastructure.postgres.models import EntityRegistry, ResearchDatasetRevision
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from entropia.shared.errors import NotFoundError
from entropia.shared.pagination import PageParams


def _visibility_of(root: EntityRegistry) -> str:
    """Coarse visibility: active datasets are published; else private."""
    return "published" if root.lifecycle_state == "active" else "private"


def can_view(actor: Actor, root: EntityRegistry) -> bool:
    return identity_policy.can_view(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility=_visibility_of(root),
    )


def _revision_dict(root: EntityRegistry, revision: ResearchDatasetRevision) -> dict[str, Any]:
    return {
        "entity_id": root.entity_id,
        "revision_id": revision.revision_id,
        "revision_no": revision.revision_no,
        "revision_state": str(revision.revision_state),
        "validation_status": (
            str(revision.validation_status) if revision.validation_status else None
        ),
        "display_name": revision.display_name,
        "category_key": revision.category_key,
        "custom_category": revision.custom_category,
        "provider_name": revision.provider_name,
        "usage_scope": str(revision.usage_scope) if revision.usage_scope else None,
        "linked_market_dataset_revision_id": revision.linked_market_dataset_revision_id,
        "event_time_semantics": (
            str(revision.event_time_semantics) if revision.event_time_semantics else None
        ),
        "available_time_policy": (
            str(revision.available_time_policy) if revision.available_time_policy else None
        ),
        "available_delay_seconds": revision.available_delay_seconds,
        "frequency_policy": (str(revision.frequency_policy) if revision.frequency_policy else None),
        "source_timezone_mode": (
            str(revision.source_timezone_mode) if revision.source_timezone_mode else None
        ),
        "source_timezone_iana": revision.source_timezone_iana,
        "content_hash": revision.content_hash,
        "manifest_hash": revision.manifest_hash,
        "owner_principal_id": root.owner_principal_id,
        "row_version": root.row_version,
        "lifecycle_state": root.lifecycle_state,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
    }


async def list_research_dataset_revisions(
    session: AsyncSession, actor: Actor, params: PageParams
) -> dict[str, Any]:
    """List head revisions visible to the actor (active only), cursor-paginated."""
    rd_policy.ensure_can_access_page(actor)
    stmt = (
        select(EntityRegistry, ResearchDatasetRevision)
        .join(
            ResearchDatasetRevision,
            ResearchDatasetRevision.revision_id == EntityRegistry.current_revision_id,
        )
        .where(
            EntityRegistry.entity_type == rd_repo.ENTITY_TYPE,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
        )
        .order_by(EntityRegistry.entity_id.desc())
    )
    if params.cursor is not None:
        stmt = stmt.where(EntityRegistry.entity_id < params.cursor)
    stmt = stmt.limit(params.limit + 1)

    pairs = list((await session.execute(stmt)).all())
    visible = [(root, rev) for root, rev in pairs if can_view(actor, root)]

    has_more = len(visible) > params.limit
    page = visible[: params.limit]
    next_cursor = page[-1][0].entity_id if has_more and page else None
    return {
        "data": [_revision_dict(root, rev) for root, rev in page],
        "meta": {"cursor": next_cursor, "has_more": has_more},
    }


async def get_research_dataset_detail(
    session: AsyncSession, actor: Actor, *, entity_id: str
) -> dict[str, Any]:
    """Return the dataset head detail, re-checking view permission server-side."""
    rd_policy.ensure_can_access_page(actor)
    root = await rd_repo.get_dataset_root(session, entity_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise NotFoundError(f"Research dataset '{entity_id}' not found.")
    rd_policy.ensure_can_view(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility=_visibility_of(root),
    )
    revision = await rd_repo.get_revision(session, root.current_revision_id or "")
    if revision is None:
        raise NotFoundError("Research dataset has no current revision.")
    detail = _revision_dict(root, revision)
    revisions = await rd_repo.list_revisions(session, entity_id, limit=50)
    detail["revisions"] = [
        {
            "revision_id": r.revision_id,
            "revision_no": r.revision_no,
            "revision_state": str(r.revision_state),
        }
        for r in revisions
    ]
    return detail
