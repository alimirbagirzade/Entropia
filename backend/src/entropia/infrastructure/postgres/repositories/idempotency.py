"""Idempotency-key data access (Module 20 §6.2)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.infrastructure.postgres.models import IdempotencyKey


async def get_key(session: AsyncSession, key: str) -> IdempotencyKey | None:
    return await session.get(IdempotencyKey, key)


def add_key(
    session: AsyncSession, *, key: str, actor_principal_id: str | None, request_hash: str
) -> IdempotencyKey:
    row = IdempotencyKey(
        key=key,
        actor_principal_id=actor_principal_id,
        request_hash=request_hash,
        status="in_progress",
    )
    session.add(row)
    return row


def complete_key(row: IdempotencyKey, *, response_ref: dict[str, Any]) -> None:
    row.response_ref = response_ref
    row.status = "completed"
