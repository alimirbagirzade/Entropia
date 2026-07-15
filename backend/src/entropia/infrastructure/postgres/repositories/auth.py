"""Persistence helpers for local auth (credentials + sessions)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.infrastructure.postgres.models import (
    AuthSession,
    HumanCredential,
    HumanUser,
    ReauthProof,
)


async def get_user_by_username(session: AsyncSession, username: str) -> HumanUser | None:
    result = await session.execute(select(HumanUser).where(HumanUser.username == username))
    return result.scalar_one_or_none()


async def get_credential(session: AsyncSession, user_id: str) -> HumanCredential | None:
    return await session.get(HumanCredential, user_id)


async def get_session_by_token_hash(session: AsyncSession, token_hash: str) -> AuthSession | None:
    result = await session.execute(select(AuthSession).where(AuthSession.token_hash == token_hash))
    return result.scalar_one_or_none()


def is_session_active(record: AuthSession, *, now: datetime) -> bool:
    return record.revoked_at is None and record.expires_at > now


async def get_reauth_proof_by_hash(session: AsyncSession, proof_hash: str) -> ReauthProof | None:
    result = await session.execute(select(ReauthProof).where(ReauthProof.proof_hash == proof_hash))
    return result.scalar_one_or_none()
