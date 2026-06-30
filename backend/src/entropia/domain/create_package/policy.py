"""Create Package + Pre-Check authorization (docs 06 §2, 07 §2; CR-02).

Pure policy over the Actor (and a request's owner). Page access is role-aware
rather than fully gated: any authenticated actor (User/Supervisor/Admin/Agent)
may create requests and run Pre-Check on their OWN request; Guest is rejected.
Approval/publish is Admin-ONLY (CR-02) — non-Admins create requests only. UI
hide/disable is never a substitute for these checks.
"""

from __future__ import annotations

from entropia.domain.identity.actor import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.shared.errors import AccessDeniedError, ApprovalRequiresAdmin


def ensure_can_create_request(actor: Actor) -> None:
    """Any authenticated actor may create a Create-Package request (doc 06 §2)."""
    require_authenticated(actor)


def ensure_can_operate_request(actor: Actor, *, owner_principal_id: str | None) -> None:
    """Run Pre-Check / advance a request: the owner or an Admin (doc 07 §2).

    Non-owners must derive their own request rather than mutate someone else's.
    """
    require_authenticated(actor)
    if actor.is_admin:
        return
    if owner_principal_id is not None and owner_principal_id == actor.principal_id:
        return
    raise AccessDeniedError("You can only act on your own package request.")


def ensure_can_approve_publish(actor: Actor) -> None:
    """Approve & publish a package revision is Admin-ONLY (CR-02, doc 06 §7).

    Supervisor/User/Agent may prepare evidence and create approval requests but can
    never execute the publish transition themselves. Mirrors the ESP registry
    activation gate so the asserted code is the intended APPROVAL_REQUIRES_ADMIN.
    """
    require_authenticated(actor)
    if not actor.is_admin:
        raise ApprovalRequiresAdmin("Approving and publishing a package requires the Admin role.")
