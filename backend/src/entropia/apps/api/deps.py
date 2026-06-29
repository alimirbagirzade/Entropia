"""Shared FastAPI dependencies: DB session, request context, and actor.

Authentication / IdP selection is deliberately deferred to a later security
decision (Master §20). Until then the transport supplies the principal id via the
``X-Actor-Id`` header (dev-mode); the ROLE is always resolved server-side from the
user/agent registry — the client never asserts its own role.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.identity import resolve_actor
from entropia.domain.identity import Actor
from entropia.infrastructure.postgres.engine import get_session_factory

ACTOR_ID_HEADER = "X-Actor-Id"


async def db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@dataclass(slots=True)
class RequestContext:
    """One transactional unit of work bound to the request's actor + trace ids."""

    session: AsyncSession
    actor: Actor


async def request_context(
    request: Request, session: AsyncSession = Depends(db_session)
) -> RequestContext:
    actor = await resolve_actor(
        session,
        principal_id=request.headers.get(ACTOR_ID_HEADER),
        request_id=getattr(request.state, "request_id", ""),
        correlation_id=getattr(request.state, "correlation_id", ""),
    )
    return RequestContext(session=session, actor=actor)
