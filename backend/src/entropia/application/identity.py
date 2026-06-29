"""Resolve the server-side Actor from a principal id (M1).

NOTE: Real authentication / IdP selection is deliberately deferred to a later
security decision (Master §20 scope note). Until then, a principal id is provided
by the transport adapter (e.g. a dev header) and resolved here against the user /
agent registry. The resolved role is ALWAYS taken from the database, never from
the client.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType
from entropia.infrastructure.postgres.repositories import identity as identity_repo


async def resolve_actor(
    session: AsyncSession,
    *,
    principal_id: str | None,
    request_id: str = "",
    correlation_id: str = "",
) -> Actor:
    if not principal_id:
        return Actor.anonymous(request_id=request_id, correlation_id=correlation_id)

    user = await identity_repo.get_human_user(session, principal_id)
    if user is not None and user.deletion_state == DeletionState.ACTIVE and user.status == "active":
        return Actor(
            principal_id=user.user_id,
            principal_type=PrincipalType.HUMAN,
            role=user.current_role,
            request_id=request_id,
            correlation_id=correlation_id,
        )

    agent = await identity_repo.get_agent(session, principal_id)
    if agent is not None and agent.enabled:
        return Actor(
            principal_id=agent.agent_id,
            principal_type=PrincipalType.AGENT,
            role=None,
            request_id=request_id,
            correlation_id=correlation_id,
        )

    return Actor.anonymous(request_id=request_id, correlation_id=correlation_id)
