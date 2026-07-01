"""Management read models for the Admin Panel (doc 19 §3.3, §4.1, §6.1).

Three Admin-only projections: the paged *human* user registry (the only role
assignment target), the read-only System Actor card (Agents — never in the user
registry, never role-assignable), and the canonical Role Scope Matrix. The Agent is
deliberately excluded from the user list and role dropdown (doc 19 §4.1, §13).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.admin_panel.role_matrix import build_role_matrix
from entropia.domain.agent_lab.cursor import clamp_limit, decode_cursor, encode_cursor
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_admin_panel
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import Agent, HumanUser

_USERS_CURSOR_NAMESPACE = "admin_users"


def _user_row(user: HumanUser) -> dict[str, Any]:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "role": str(user.current_role),
        "version": user.version,
        "status": user.status,
        "role_changed_at": user.role_changed_at.isoformat() if user.role_changed_at else None,
        "role_changed_by": user.role_changed_by,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


async def list_registered_users(
    session: AsyncSession, actor: Actor, *, cursor: str | None = None, limit: int | None = None
) -> dict[str, Any]:
    """Admin-only, stable-ordered (username asc) human user registry with an opaque
    keyset cursor. Agents/system actors never appear here (doc 19 §4.1, §13)."""
    require_admin_panel(actor)
    page_limit = clamp_limit(limit)

    stmt = (
        select(HumanUser)
        .where(HumanUser.deletion_state == DeletionState.ACTIVE)
        .order_by(HumanUser.username.asc())
    )
    if cursor is not None:
        decoded = decode_cursor(cursor, namespace=_USERS_CURSOR_NAMESPACE)
        stmt = stmt.where(HumanUser.username > decoded.last_key)
    stmt = stmt.limit(page_limit + 1)

    rows = list((await session.execute(stmt)).scalars().all())
    has_more = len(rows) > page_limit
    page = rows[:page_limit]
    next_cursor = (
        encode_cursor(_USERS_CURSOR_NAMESPACE, last_key=page[-1].username)
        if has_more and page
        else None
    )
    return {
        "data": [_user_row(u) for u in page],
        "meta": {"cursor": next_cursor, "has_more": has_more, "limit": page_limit},
    }


async def list_system_actors(session: AsyncSession, actor: Actor) -> dict[str, Any]:
    """Admin-only read-only System Actor projection (Agents). No mutation, no role
    assignment, no revoke (doc 19 §3.3, §4.1)."""
    require_admin_panel(actor)
    stmt = select(Agent).order_by(Agent.name.asc())
    agents = list((await session.execute(stmt)).scalars().all())
    return {
        "data": [
            {
                "actor_type": "system_agent",
                "actor_id": a.agent_id,
                "display_name": a.name,
                "status": "enabled" if a.enabled else "disabled",
                "assignable": False,
            }
            for a in agents
        ]
    }


async def get_role_matrix(session: AsyncSession, actor: Actor) -> dict[str, Any]:
    """Admin-only canonical role-scope matrix projection (read-only, server truth)."""
    require_admin_panel(actor)
    return build_role_matrix()


__all__ = ["get_role_matrix", "list_registered_users", "list_system_actors"]
