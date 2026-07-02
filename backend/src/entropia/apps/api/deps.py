"""Shared FastAPI dependencies: DB session, request context, and actor.

AUTH_MODE selects the transport trust model (M1 §4 / Master §20):

- ``dev``:     the transport supplies the principal id via ``X-Actor-Id``
               (local + test default); the ROLE is always resolved server-side
               from the user/agent registry — the client never asserts a role.
- ``session``: humans present an opaque Bearer session token (a live
               ``auth_sessions`` row); non-human runtimes present the static
               service token plus ``X-Actor-Id`` naming an agent principal.
               A bare ``X-Actor-Id`` is IGNORED — no spoofing line remains.
"""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands.auth import hash_token
from entropia.application.identity import resolve_actor
from entropia.config import get_settings
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType
from entropia.infrastructure.postgres.engine import get_session_factory
from entropia.infrastructure.postgres.repositories import auth as auth_repo
from entropia.shared.errors import ServiceLineForbiddenError, SessionInvalidError

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


def bearer_token(request: Request) -> str | None:
    """Extract the RFC 6750 Bearer credential, or None when absent/malformed."""
    header = request.headers.get("Authorization")
    if not header:
        return None
    scheme, _, credential = header.partition(" ")
    credential = credential.strip()
    if scheme.lower() != "bearer" or not credential:
        return None
    return credential


@dataclass(slots=True)
class RequestContext:
    """One transactional unit of work bound to the request's actor + trace ids."""

    session: AsyncSession
    actor: Actor


async def _session_mode_actor(
    request: Request,
    session: AsyncSession,
    *,
    request_id: str,
    correlation_id: str,
) -> Actor:
    settings = get_settings()
    token = bearer_token(request)
    if token is None:
        # No credential at all -> anonymous; route-level policy decides access.
        return Actor.anonymous(request_id=request_id, correlation_id=correlation_id)

    if settings.service_token and hmac.compare_digest(token, settings.service_token):
        # Service line (M1 §3.3): trusted infra names its runtime principal via
        # the header, but the line can never impersonate a human account.
        actor = await resolve_actor(
            session,
            principal_id=request.headers.get(ACTOR_ID_HEADER),
            request_id=request_id,
            correlation_id=correlation_id,
        )
        if not actor.is_authenticated or actor.principal_type == PrincipalType.HUMAN:
            raise ServiceLineForbiddenError()
        return actor

    record = await auth_repo.get_session_by_token_hash(session, hash_token(token))
    if record is None or not auth_repo.is_session_active(record, now=datetime.now(UTC)):
        raise SessionInvalidError()
    # Role is re-read from the registry on EVERY request (M1 §4.2): an Admin
    # role change applies to the next request, and a user disabled or deleted
    # after login loses the session immediately.
    actor = await resolve_actor(
        session,
        principal_id=record.user_id,
        request_id=request_id,
        correlation_id=correlation_id,
    )
    if not actor.is_authenticated:
        raise SessionInvalidError()
    return actor


async def request_context(
    request: Request, session: AsyncSession = Depends(db_session)
) -> RequestContext:
    request_id = getattr(request.state, "request_id", "")
    correlation_id = getattr(request.state, "correlation_id", "")
    if get_settings().auth_mode == "session":
        actor = await _session_mode_actor(
            request, session, request_id=request_id, correlation_id=correlation_id
        )
    else:
        actor = await resolve_actor(
            session,
            principal_id=request.headers.get(ACTOR_ID_HEADER),
            request_id=request_id,
            correlation_id=correlation_id,
        )
    return RequestContext(session=session, actor=actor)
