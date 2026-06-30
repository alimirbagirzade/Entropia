"""Market Data authorization policy (doc 11 §2.2, DOMAIN_MODEL §4-§5).

Pure functions over an Actor plus the resource's owner/visibility. They raise
typed errors the API maps to 401/403/422. View/edit reuse the shared identity
policy; approval is Admin-only and raises ``ApprovalRequiresAdmin``.
"""

from __future__ import annotations

from entropia.domain.identity import policy as identity_policy
from entropia.domain.identity.actor import Actor
from entropia.shared.errors import AccessDeniedError, ApprovalRequiresAdmin


def ensure_can_view(actor: Actor, *, owner_principal_id: str | None, visibility: str) -> None:
    """Read access — delegates to the shared identity policy."""
    identity_policy.ensure_can_view(
        actor, owner_principal_id=owner_principal_id, visibility=visibility
    )


def ensure_can_edit_draft(actor: Actor, *, owner_principal_id: str | None) -> None:
    """Draft edits: the owner or an Admin only. Non-owners must Derive."""
    if actor.is_admin:
        return
    if not actor.is_authenticated:
        raise AccessDeniedError("You must be signed in to edit this draft.")
    if owner_principal_id is None or owner_principal_id != actor.principal_id:
        raise AccessDeniedError("You can only edit market datasets you own.")


def ensure_can_approve(actor: Actor) -> None:
    """Approval is Admin-only (CR-02)."""
    if not actor.is_admin:
        raise ApprovalRequiresAdmin()
