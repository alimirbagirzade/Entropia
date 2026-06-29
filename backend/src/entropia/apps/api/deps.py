"""Shared FastAPI dependencies.

The ActorContext is a Stage-0 placeholder. Stage 1 replaces it with real
identity/role resolution; every mutation command will run under an actor with
server-side policy enforcement (Module 1).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.infrastructure.postgres.engine import get_session_factory


async def db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Who is making the request, plus its trace ids. Stage-0 stub: anonymous."""

    actor_id: str | None
    role: str
    request_id: str
    correlation_id: str


def actor_context(request: Request) -> ActorContext:
    return ActorContext(
        actor_id=None,
        role="anonymous",
        request_id=getattr(request.state, "request_id", ""),
        correlation_id=getattr(request.state, "correlation_id", ""),
    )
