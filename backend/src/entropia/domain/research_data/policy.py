"""Research Data authorization policy (doc 12 §2, DOMAIN_MODEL §4-§5).

Pure functions over an Actor plus the resource's owner/visibility. They raise
typed errors the API maps to 401/403/422. View/edit reuse the shared identity
policy; approval AND revocation are Admin-only and raise ``ApprovalRequiresAdmin``.

Page access is restricted to Admin/Supervisor/Agent (doc 12 §2): Users and Guests
are blocked at the route/query layer; ``ensure_can_view`` still applies per-row.
"""

from __future__ import annotations

from entropia.domain.identity import policy as identity_policy
from entropia.domain.identity.actor import Actor
from entropia.domain.lifecycle.enums import Role
from entropia.shared.errors import AccessDeniedError, ApprovalRequiresAdmin


def ensure_can_access_page(actor: Actor) -> None:
    """Research Data is an Agent-Workspace page: only Admin, Supervisor and the
    system Agent may access it (doc 12 §2/§4/§10/§12). Regular Users and Guests
    are blocked server-side regardless of UI gating. Guests (unauthenticated)
    get ``UNAUTHENTICATED``; authenticated non-eligible roles get ``ACCESS_DENIED``
    with 'Admin, Supervisor or Agent access required.'."""
    identity_policy.require_authenticated(actor)
    if actor.is_admin or actor.role == Role.SUPERVISOR or actor.is_agent:
        return
    raise AccessDeniedError("Admin, Supervisor or Agent access required.")


def ensure_can_view(actor: Actor, *, owner_principal_id: str | None, visibility: str) -> None:
    """Read access — delegates to the shared identity policy."""
    identity_policy.ensure_can_view(
        actor, owner_principal_id=owner_principal_id, visibility=visibility
    )


def ensure_can_edit_draft(actor: Actor, *, owner_principal_id: str | None) -> None:
    """Draft edits: the owner or an Admin only. Non-owners must derive a new
    revision from base instead of mutating someone else's draft (doc 12 §2)."""
    if actor.is_admin:
        return
    if not actor.is_authenticated:
        raise AccessDeniedError("You must be signed in to edit this draft.")
    if owner_principal_id is None or owner_principal_id != actor.principal_id:
        raise AccessDeniedError("You can only edit research datasets you own.")


def ensure_can_approve(actor: Actor) -> None:
    """Approval is Admin-only (doc 12 §2, M1, CR-09). Ownership/Agent status does
    not grant approval; non-Admin -> APPROVAL_REQUIRES_ADMIN (403)."""
    if not actor.is_admin:
        raise ApprovalRequiresAdmin()


def ensure_can_revoke(actor: Actor) -> None:
    """Approval revocation is Admin-only (doc 12 §2, §7)."""
    if not actor.is_admin:
        raise ApprovalRequiresAdmin()
