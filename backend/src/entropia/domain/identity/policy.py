"""Server-side authorization policy (DOMAIN_MODEL §4, §5).

Pure functions over an Actor (and the resource's owner/visibility). They raise
typed errors so the API layer maps them to 401/403/422. UI hide/disable is never
a substitute for these checks.
"""

from __future__ import annotations

from collections.abc import Iterable

from entropia.domain.identity.actor import Actor
from entropia.domain.lifecycle.enums import Role
from entropia.shared.errors import (
    AccessDeniedError,
    AdminManualWriteRequiredError,
    AdminPanelAccessRequiredError,
    AgentRoleNotAssignableError,
    CapabilityAccessDeniedError,
    LastAdminProtectedError,
    TrashAccessForbiddenError,
    UnauthenticatedError,
)

# Visibility scopes any actor may read regardless of ownership.
PUBLIC_VISIBILITIES = frozenset({"published", "system"})


def require_authenticated(actor: Actor) -> None:
    if not actor.is_authenticated:
        raise UnauthenticatedError()


def require_admin(actor: Actor) -> None:
    require_authenticated(actor)
    if not actor.is_admin:
        raise AccessDeniedError("This action requires the Admin role.")


def require_admin_panel(actor: Actor) -> None:
    """Panel / Management / Logs guard (doc 19 §2). Every Panel endpoint AND its
    service call this — a hidden menu item is never an authorization decision.
    Supervisor, User, Agent and anonymous callers are all denied here."""
    require_authenticated(actor)
    if not actor.is_admin:
        raise AdminPanelAccessRequiredError()


def require_trash_admin(actor: Actor) -> None:
    """Trash list/detail/restore/purge guard (doc 20 §2). Only an authenticated
    human Admin may use Trash; User/Supervisor/Agent get 403 TRASH_ACCESS_FORBIDDEN
    with no row metadata. The Rationale shared-editing exception never extends
    here, and the Agent principal keeps only its own-output soft-delete tool."""
    require_authenticated(actor)
    if not actor.is_admin:
        raise TrashAccessForbiddenError()


def require_manual_admin(actor: Actor) -> None:
    """User Manual write guard (doc 21 §2): append/upload/revise/delete/restore
    are Admin-only at the ROUTE and again inside the command. V18's visible
    ``canUploadUserManual()`` helper is never an authorization decision; the
    Agent principal keeps read/search/citation tools only (doc 21 §12)."""
    require_authenticated(actor)
    if not actor.is_admin:
        raise AdminManualWriteRequiredError()


def require_capability_admin(actor: Actor) -> None:
    """Capability lifecycle-transition guard (doc 22 §3, §12, FD-13): only an
    authenticated human Admin may run POST lifecycle-transitions, at the ROUTE
    and again inside the command. Supervisor, User, Agent and anonymous callers
    get 403 CAPABILITY_ACCESS_DENIED; the Agent can never transition (CR-08)."""
    require_authenticated(actor)
    if not actor.is_admin:
        raise CapabilityAccessDeniedError()


def require_role(actor: Actor, roles: Iterable[Role]) -> None:
    require_authenticated(actor)
    allowed = set(roles)
    if actor.role not in allowed:
        raise AccessDeniedError("Your role does not permit this action.")


def can_view(actor: Actor, *, owner_principal_id: str | None, visibility: str) -> bool:
    """Read access: admins see all; anyone sees published/system; owners see own;
    `explicitly_shared` is treated as readable to authenticated actors here (the
    fine-grained share list is resolved by the owning domain in later stages)."""
    if actor.is_admin:
        return True
    if visibility in PUBLIC_VISIBILITIES:
        return True
    if not actor.is_authenticated:
        return False
    if owner_principal_id is not None and owner_principal_id == actor.principal_id:
        return True
    return visibility == "explicitly_shared"


def ensure_can_view(actor: Actor, *, owner_principal_id: str | None, visibility: str) -> None:
    if not can_view(actor, owner_principal_id=owner_principal_id, visibility=visibility):
        raise AccessDeniedError()


def can_edit(actor: Actor, *, owner_principal_id: str | None) -> bool:
    """Edit access: admins may edit anything; everyone else edits only their own.
    Non-owners must Derive a new root instead of silently editing (later stages)."""
    if actor.is_admin:
        return True
    if not actor.is_authenticated:
        return False
    return owner_principal_id is not None and owner_principal_id == actor.principal_id


def ensure_can_edit(actor: Actor, *, owner_principal_id: str | None) -> None:
    if not can_edit(actor, owner_principal_id=owner_principal_id):
        raise AccessDeniedError("You can only edit resources you own.")


def assert_role_assignable(target_role: Role) -> None:
    """Only admin/supervisor/user are assignable. Agent is a non-login system
    actor and can never be assigned to a human (CR / DOMAIN_MODEL §4)."""
    if target_role not in (Role.ADMIN, Role.SUPERVISOR, Role.USER):
        raise AgentRoleNotAssignableError()


def ensure_not_last_admin(
    *, target_is_admin: bool, becomes_admin: bool, active_admin_count: int
) -> None:
    """Block demoting/deactivating the last remaining active Admin."""
    if target_is_admin and not becomes_admin and active_admin_count <= 1:
        raise LastAdminProtectedError()
