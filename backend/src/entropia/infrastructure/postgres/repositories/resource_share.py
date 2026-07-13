"""Explicit resource-share persistence (GAP-17; Master Reference §6, §6.4).

Sync mutators add/close grant rows (no commit, mirroring the other repos); async
readers resolve the ACTIVE grantee set for a resource and the resources shared
with one grantee — the two lookups the identity ``can_view`` policy and the
Package Library catalog need. "ACTIVE" means ``revoked_at IS NULL``; a revoked
grant is retained for audit and never blocks a fresh re-share (the partial unique
index only constrains active rows). The application command layer validates
authorization, shareable-visibility and optimistic concurrency first.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.infrastructure.postgres.models import ResourceShare
from entropia.shared.ids import new_id


def create_share(
    session: AsyncSession,
    *,
    resource_type: str,
    resource_id: str,
    grantee_principal_id: str,
    granted_by_principal_id: str | None,
) -> ResourceShare:
    """Insert a new ACTIVE share grant (``revoked_at`` NULL)."""
    grant = ResourceShare(
        share_id=new_id("shr"),
        resource_type=resource_type,
        resource_id=resource_id,
        grantee_principal_id=grantee_principal_id,
        granted_by_principal_id=granted_by_principal_id,
    )
    session.add(grant)
    return grant


def revoke_share(
    grant: ResourceShare, *, revoked_by_principal_id: str | None, now: datetime
) -> ResourceShare:
    """Soft-close an active grant (idempotent: an already-revoked grant is kept)."""
    if grant.revoked_at is None:
        grant.revoked_at = now
        grant.revoked_by_principal_id = revoked_by_principal_id
    return grant


async def get_share(session: AsyncSession, share_id: str) -> ResourceShare | None:
    return await session.get(ResourceShare, share_id)


async def get_active_grant(
    session: AsyncSession,
    *,
    resource_type: str,
    resource_id: str,
    grantee_principal_id: str,
) -> ResourceShare | None:
    stmt = select(ResourceShare).where(
        ResourceShare.resource_type == resource_type,
        ResourceShare.resource_id == resource_id,
        ResourceShare.grantee_principal_id == grantee_principal_id,
        ResourceShare.revoked_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_active_grants(
    session: AsyncSession, *, resource_type: str, resource_id: str
) -> Sequence[ResourceShare]:
    """Active grants for one resource, oldest-first (grant order is stable)."""
    stmt = (
        select(ResourceShare)
        .where(
            ResourceShare.resource_type == resource_type,
            ResourceShare.resource_id == resource_id,
            ResourceShare.revoked_at.is_(None),
        )
        .order_by(ResourceShare.share_id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def count_active_grants(
    session: AsyncSession, *, resource_type: str, resource_id: str
) -> int:
    stmt = (
        select(func.count())
        .select_from(ResourceShare)
        .where(
            ResourceShare.resource_type == resource_type,
            ResourceShare.resource_id == resource_id,
            ResourceShare.revoked_at.is_(None),
        )
    )
    return int((await session.execute(stmt)).scalar_one())


async def active_grantee_ids(
    session: AsyncSession, *, resource_type: str, resource_id: str
) -> set[str]:
    """The set of principal ids a resource is currently shared with."""
    stmt = select(ResourceShare.grantee_principal_id).where(
        ResourceShare.resource_type == resource_type,
        ResourceShare.resource_id == resource_id,
        ResourceShare.revoked_at.is_(None),
    )
    return set((await session.execute(stmt)).scalars().all())


async def shared_resource_ids(
    session: AsyncSession, *, grantee_principal_id: str, resource_type: str
) -> set[str]:
    """The set of resource ids of ``resource_type`` shared with one grantee."""
    stmt = select(ResourceShare.resource_id).where(
        ResourceShare.resource_type == resource_type,
        ResourceShare.grantee_principal_id == grantee_principal_id,
        ResourceShare.revoked_at.is_(None),
    )
    return set((await session.execute(stmt)).scalars().all())


__all__ = [
    "active_grantee_ids",
    "count_active_grants",
    "create_share",
    "get_active_grant",
    "get_share",
    "list_active_grants",
    "revoke_share",
    "shared_resource_ids",
]
