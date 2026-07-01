"""Canonical Admin role assignment command (doc 19 §4.2, §9, §11).

The single Management mutation: change one *human* user's current role atomically.
Layered on the M1 policy helpers (``require_admin``/``assert_role_assignable``/
``ensure_not_last_admin``) but adds the Panel contract — Admin-only guard, row lock,
``expected_head_revision_id`` optimistic concurrency, a no-op (``changed=false``)
path that writes no audit noise, Agent-target rejection, and a ``role_assigned``
audit/outbox pair in the SAME transaction. Owner, created_by, historical manifests
and prior audit records are never touched (doc 19 §4.2 step 4, §13).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import (
    assert_role_assignable,
    ensure_not_last_admin,
    require_admin_panel,
)
from entropia.domain.lifecycle.enums import Role
from entropia.infrastructure.postgres.models import HumanUser
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import identity as identity_repo
from entropia.shared.errors import (
    AgentRoleNotAssignableError,
    NotFoundError,
    UserRoleVersionConflictError,
)

_TARGET_TYPE = "human_user"


def _projection(
    user: HumanUser, *, changed: bool, audit_event_id: str | None, correlation_id: str
) -> dict[str, Any]:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": str(user.current_role),
        "version": user.version,
        "role_changed_at": user.role_changed_at.isoformat() if user.role_changed_at else None,
        "role_changed_by": user.role_changed_by,
        "changed": changed,
        "audit_event_id": audit_event_id,
        "correlation_id": correlation_id,
    }


async def assign_user_role(
    session: AsyncSession,
    actor: Actor,
    *,
    target_user_id: str,
    target_role: Role,
    expected_head_revision_id: int,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Assign ``target_role`` to a human user (Admin-only, atomic, OCC-guarded).

    Returns a JSON-safe user projection with ``changed`` (false on a no-op) and the
    ``role_assigned`` ``audit_event_id`` when a mutation actually occurred.
    """
    require_admin_panel(actor)  # service-side guard — not just the route
    assert_role_assignable(target_role)

    async def _op() -> dict[str, Any]:
        user = await identity_repo.get_human_user(session, target_user_id)
        if user is None:
            # A system actor (Agent) is never an assignable human target (§4.1, §11).
            agent = await identity_repo.get_agent(session, target_user_id)
            if agent is not None:
                raise AgentRoleNotAssignableError()
            raise NotFoundError(f"User '{target_user_id}' not found.")

        # Row-lock the target so two concurrent Admins serialize on this user.
        await session.refresh(user, with_for_update=True)

        # Optimistic concurrency: the caller must have loaded the current version.
        if expected_head_revision_id != user.version:
            raise UserRoleVersionConflictError()

        previous_role = user.current_role
        if previous_role == target_role:
            # No-op save: no version bump, no audit event (doc 19 §4.2 decision).
            return _projection(
                user, changed=False, audit_event_id=None, correlation_id=actor.correlation_id
            )

        if previous_role == Role.ADMIN and target_role != Role.ADMIN:
            # Demoting an Admin is the only path that can breach last-admin. Serialize
            # the count+check against concurrent demotions of a *different* Admin
            # (TOCTOU -> zero admins) with a transaction-scoped advisory lock.
            await identity_repo.lock_admin_count(session)
            active_admins = await identity_repo.count_active_admins(session)
            ensure_not_last_admin(
                target_is_admin=True,
                becomes_admin=False,
                active_admin_count=active_admins,
            )

        user.current_role = target_role
        user.version += 1
        user.role_changed_at = datetime.now(UTC)
        user.role_changed_by = actor.principal_id

        event = audit_repo.add_audit_event(
            session,
            event_kind="user.role_assigned",
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            target_entity_id=user.user_id,
            target_entity_type=_TARGET_TYPE,
            previous_state=str(previous_role),
            new_state=str(target_role),
            correlation_id=actor.correlation_id,
            reason=reason,
        )
        audit_repo.add_outbox_event(
            session,
            event_type="role_assigned",
            resource_type=_TARGET_TYPE,
            resource_id=user.user_id,
            payload={
                "action": "role_assigned",
                "role": str(target_role),
                "previous_role": str(previous_role),
                "audit_event_id": event.event_id,
            },
            correlation_id=actor.correlation_id,
        )
        return _projection(
            user, changed=True, audit_event_id=event.event_id, correlation_id=actor.correlation_id
        )

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "assign_user_role",
            "target_user_id": target_user_id,
            "target_role": str(target_role),
            "expected_head_revision_id": expected_head_revision_id,
        },
        operation=_op,
    )


__all__ = ["assign_user_role"]
