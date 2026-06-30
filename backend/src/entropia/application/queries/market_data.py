"""Market Data read-side queries (doc 11 §, decision D8).

Role-aware: soft-deleted and unauthorized datasets are excluded server-side, not
by the client. Cursor pagination uses the "fetch limit+1" pattern from
``shared/pagination``. All return values are JSON-safe dicts (``str(enum)``,
``.isoformat()``) so routes can serialize them directly.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.market_data import policy as md_policy
from entropia.domain.market_data.enums import MarketRevisionState
from entropia.infrastructure.postgres.models import EntityRegistry, MarketDatasetRevision
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.shared.errors import NotFoundError
from entropia.shared.pagination import PageParams


def _visibility_of(root: EntityRegistry) -> str:
    """Coarse visibility: approved+active datasets are published; else private."""
    return "published" if root.lifecycle_state == "active" else "private"


def _revision_dict(root: EntityRegistry, revision: MarketDatasetRevision) -> dict[str, Any]:
    return {
        "entity_id": root.entity_id,
        "revision_id": revision.revision_id,
        "revision_no": revision.revision_no,
        "revision_state": str(revision.revision_state),
        "market_data_type": str(revision.market_data_type),
        "validation_status": (
            str(revision.validation_status) if revision.validation_status else None
        ),
        "title": revision.title,
        "instrument_id": revision.instrument_id,
        "content_hash": revision.content_hash,
        "manifest_hash": revision.manifest_hash,
        "owner_principal_id": root.owner_principal_id,
        "row_version": root.row_version,
        "lifecycle_state": root.lifecycle_state,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
    }


async def list_market_dataset_revisions(
    session: AsyncSession, actor: Actor, params: PageParams
) -> dict[str, Any]:
    """List head revisions visible to the actor (active only), cursor-paginated."""
    stmt = (
        select(EntityRegistry, MarketDatasetRevision)
        .join(
            MarketDatasetRevision,
            MarketDatasetRevision.revision_id == EntityRegistry.current_revision_id,
        )
        .where(
            EntityRegistry.entity_type == md_repo.ENTITY_TYPE,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
        )
        .order_by(EntityRegistry.entity_id.desc())
    )
    if params.cursor is not None:
        stmt = stmt.where(EntityRegistry.entity_id < params.cursor)
    stmt = stmt.limit(params.limit + 1)

    pairs = list((await session.execute(stmt)).all())
    visible = [(root, rev) for root, rev in pairs if md_policy_can_view(actor, root)]

    has_more = len(visible) > params.limit
    page = visible[: params.limit]
    next_cursor = page[-1][0].entity_id if has_more and page else None
    return {
        "data": [_revision_dict(root, rev) for root, rev in page],
        "meta": {"cursor": next_cursor, "has_more": has_more},
    }


def md_policy_can_view(actor: Actor, root: EntityRegistry) -> bool:
    from entropia.domain.identity import policy as identity_policy

    return identity_policy.can_view(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility=_visibility_of(root),
    )


async def get_market_dataset_detail(
    session: AsyncSession, actor: Actor, *, entity_id: str
) -> dict[str, Any]:
    """Return the dataset head detail, re-checking view permission server-side."""
    root = await md_repo.get_dataset_root(session, entity_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise NotFoundError(f"Market dataset '{entity_id}' not found.")
    md_policy.ensure_can_view(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility=_visibility_of(root),
    )
    revision = await md_repo.get_revision(session, root.current_revision_id or "")
    if revision is None:
        raise NotFoundError("Market dataset has no current revision.")
    detail = _revision_dict(root, revision)
    revisions = await md_repo.list_revisions(session, entity_id, limit=50)
    detail["revisions"] = [
        {
            "revision_id": r.revision_id,
            "revision_no": r.revision_no,
            "revision_state": str(r.revision_state),
        }
        for r in revisions
    ]
    return detail


async def resolve_approved_market_data_bundle(
    session: AsyncSession, *, entity_id: str
) -> dict[str, Any]:
    """Resolve the exact APPROVED revision a Run/Agent must consume.

    Only an ACTIVE root with an APPROVED current revision qualifies. Returns the
    exact revision id + content/manifest hashes so the consumer pins the precise
    bytes (AT #15 — manifest pins exact revision). Raises NotFound otherwise so
    consumers never silently bind to an unapproved/deleted dataset.
    """
    root = await md_repo.get_dataset_root(session, entity_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise NotFoundError(f"No approved market dataset '{entity_id}'.")
    revision = await md_repo.get_revision(session, root.current_revision_id or "")
    if revision is None or revision.revision_state != MarketRevisionState.APPROVED:
        raise NotFoundError(f"Market dataset '{entity_id}' has no ACTIVE+APPROVED revision.")
    return {
        "entity_id": entity_id,
        "revision_id": revision.revision_id,
        "revision_no": revision.revision_no,
        "revision_state": str(revision.revision_state),
        "content_hash": revision.content_hash,
        "manifest_hash": revision.manifest_hash,
        "market_data_type": str(revision.market_data_type),
    }
