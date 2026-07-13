"""Explicit-sharing authorization policy (GAP-17; Master Reference §6, §6.4).

Pure guards over an Actor + the resource's owner/visibility. Only the resource
owner or an Admin may manage shares (owner-or-admin === identity ``can_edit``);
sharing never changes ownership (Master §6.4). A resource can only be explicitly
shared while it is PRIVATE or already EXPLICITLY_SHARED — a published/system
resource is visible to everyone already, so sharing it is a no-op the caller
should not be silently granted. Self-sharing is rejected (the owner already sees
their own resource). The API layer maps the raised errors to 403/409/422.
"""

from __future__ import annotations

from entropia.domain.identity import policy as identity_policy
from entropia.domain.identity.actor import Actor
from entropia.domain.lifecycle.enums import VisibilityScope
from entropia.shared.errors import (
    ShareManagementForbiddenError,
    ShareNotAllowedForVisibilityError,
    ShareWithSelfError,
)

# Visibility scopes from/into which an explicit share is meaningful.
SHAREABLE_VISIBILITIES: frozenset[str] = frozenset(
    {VisibilityScope.PRIVATE, VisibilityScope.EXPLICITLY_SHARED}
)


def ensure_can_manage_shares(actor: Actor, *, owner_principal_id: str | None) -> None:
    """Only the owner or an Admin may grant/revoke shares of a resource."""
    if not identity_policy.can_edit(actor, owner_principal_id=owner_principal_id):
        raise ShareManagementForbiddenError()


def ensure_shareable_visibility(visibility: str) -> None:
    """A resource must be private (or already explicitly shared) to be shared."""
    if visibility not in SHAREABLE_VISIBILITIES:
        raise ShareNotAllowedForVisibilityError(
            "This resource is already public; explicit sharing does not apply."
        )


def ensure_distinct_grantee(actor_principal_id: str | None, grantee_principal_id: str) -> None:
    """The owner cannot share a resource with themselves (they already see it)."""
    if actor_principal_id is not None and actor_principal_id == grantee_principal_id:
        raise ShareWithSelfError()
