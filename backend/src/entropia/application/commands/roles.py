"""Human role assignment (Admin-only) with last-admin protection (M1, §4)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import (
    assert_role_assignable,
    ensure_not_last_admin,
    require_admin,
)
from entropia.domain.lifecycle.enums import Role
from entropia.infrastructure.postgres.models import HumanUser
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import identity as identity_repo
from entropia.shared.errors import NotFoundError


async def change_user_role(
    session: AsyncSession,
    actor: Actor,
    *,
    target_user_id: str,
    new_role: Role,
    auth_mode: str = "dev",
) -> HumanUser:
    """Change a human user's role with mode-aware last-Admin protection.

    ``auth_mode`` selects the operational Admin count (audit PROV-03): ``session``
    protects the last login-capable Admin, ``dev`` the last active Admin role row.
    The legacy ``/users/{id}/role`` path historically lacked the shared advisory
    lock around count-and-demote; it now takes ``lock_admin_count`` on the demote
    path exactly like :func:`assign_user_role`, so two concurrent demotions of
    different Admins can no longer both read count==2 and drop to zero (TOCTOU)."""
    require_admin(actor)
    assert_role_assignable(new_role)

    user = await identity_repo.get_human_user(session, target_user_id)
    if user is None:
        raise NotFoundError(f"User '{target_user_id}' not found.")

    previous_role = user.current_role
    if previous_role == new_role:
        return user  # idempotent no-op

    if previous_role == Role.ADMIN and new_role != Role.ADMIN:
        # Demotion is the only path that can breach last-admin. Serialize the
        # count+check against concurrent demotions of a *different* Admin with the
        # shared transaction-scoped advisory lock (released at commit/rollback).
        await identity_repo.lock_admin_count(session)
        active_admins = await identity_repo.count_operational_admins(session, auth_mode=auth_mode)
        ensure_not_last_admin(
            target_is_admin=True,
            becomes_admin=False,
            active_admin_count=active_admins,
        )

    user.current_role = new_role
    user.version += 1
    user.role_changed_at = datetime.now(UTC)
    user.role_changed_by = actor.principal_id

    audit_repo.add_audit_event(
        session,
        event_kind="user.role_changed",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=user.user_id,
        target_entity_type="human_user",
        previous_state=str(previous_role),
        new_state=str(new_role),
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type="human_user",
        resource_id=user.user_id,
        payload={"action": "role_changed", "role": str(new_role)},
        correlation_id=actor.correlation_id,
    )
    return user
