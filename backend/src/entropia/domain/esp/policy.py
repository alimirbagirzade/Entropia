"""ESP authorization policy (doc 09 §2, §10.3, CR-02).

Pure functions over an Actor plus the resource's owner/visibility. They raise
typed errors the API maps to 401/403. View/use reuse the shared identity policy;
registry mutation (activate/deprecate) is Admin-only — an Agent or Supervisor
that reaches these calls receives ``ApprovalRequiresAdmin`` (doc 09 §2 table:
"Cannot self-approve / activate canonical resolver"; §8 "Approve and activate /
Deprecate" Admin-only; §15 "Permission" acceptance test).
"""

from __future__ import annotations

from entropia.domain.identity import policy as identity_policy
from entropia.domain.identity.actor import Actor
from entropia.shared.errors import AccessDeniedError, ApprovalRequiresAdmin


def ensure_can_view(actor: Actor, *, owner_principal_id: str | None, visibility: str) -> None:
    """Read/use access — delegates to the shared identity policy (doc 09 §2).

    Trusted ESPs are ``system``-owned/``published`` and visible to any actor;
    private proposal drafts are visible only to their owner or an Admin.
    """
    identity_policy.ensure_can_view(
        actor, owner_principal_id=owner_principal_id, visibility=visibility
    )


def ensure_can_activate(actor: Actor) -> None:
    """Registry activation (candidate -> trusted_active) is Admin-only (CR-02).

    Agent and Supervisor are rejected even if a client sends a fabricated role
    payload (doc 09 §10.3, §15 Permission/Agent parity).
    """
    if not actor.is_admin:
        raise ApprovalRequiresAdmin("Activating a trusted resolver requires the Admin role.")


def ensure_can_deprecate(actor: Actor) -> None:
    """Registry deprecation (trusted_active -> deprecated) is Admin-only (CR-02)."""
    if not actor.is_admin:
        raise ApprovalRequiresAdmin("Deprecating a trusted resolver requires the Admin role.")


def ensure_can_run_validation(actor: Actor, *, owner_principal_id: str | None) -> None:
    """A resolver's owner or an Admin may run its validation suite (doc 09 §5 "Draft /
    candidate": owner/Admin evidence collection; §11.1 test-vector layer, R8).

    Validation writes durable evidence and moves ``revision.validation_state``, so it is
    NOT an anonymous read — a non-owner, non-Admin actor is denied. Activation itself
    stays Admin-only (``ensure_can_activate``)."""
    identity_policy.require_authenticated(actor)
    if actor.is_admin or actor.principal_id == owner_principal_id:
        return
    raise AccessDeniedError("You may only run validation on a resolver you own.")
