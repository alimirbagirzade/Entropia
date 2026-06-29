"""Trash read model — soft-deleted roots, Admin-only at the route (M3, §7)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.infrastructure.postgres.repositories import entities as entity_repo
from entropia.shared.pagination import PageParams


async def list_trash(session: AsyncSession, params: PageParams) -> list[dict[str, Any]]:
    rows = await entity_repo.list_soft_deleted(session, limit=params.limit)
    return [
        {
            "entity_id": r.entity_id,
            "entity_type": r.entity_type,
            "owner_principal_id": r.owner_principal_id,
            "deleted_at": r.deleted_at.isoformat() if r.deleted_at else None,
            "deleted_by": r.deleted_by,
            "delete_reason": r.delete_reason,
        }
        for r in rows
    ]
