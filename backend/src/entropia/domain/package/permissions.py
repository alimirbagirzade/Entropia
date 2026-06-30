"""Package permission projection (doc 08 §2, §4.2).

Pure computation of the per-package capability flags the catalog returns so the
client can render availability — "absent actions are explained by permission /
lifecycle, not merely hidden" (doc 08 §4.3). The server still RE-VALIDATES every
guard on each command; this projection is a UX hint, never the authority (doc 08
§2). Flags derive from the shared identity policy (``can_view`` / ``can_edit``),
the Admin-only publish rule (CR-02), and the orthogonal lifecycle/validation/
approval facets.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from entropia.domain.identity import policy as identity_policy
from entropia.domain.identity.actor import Actor
from entropia.domain.lifecycle.enums import ApprovalState
from entropia.domain.package.enums import PackageValidationState

_ACTIVE = "active"
_DEPRECATED = "deprecated"


@dataclass(frozen=True, slots=True)
class PackagePermissions:
    """The ten capability flags a catalog row/detail exposes (doc 08 §4.2)."""

    can_view: bool
    can_use: bool
    can_derive: bool
    can_create_revision: bool
    can_request_validation: bool
    can_request_approval: bool
    can_approve_publish: bool
    can_deprecate: bool
    can_soft_delete: bool
    can_export: bool

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)


def package_permissions(
    actor: Actor,
    *,
    owner_principal_id: str | None,
    visibility_scope: str,
    lifecycle_state: str | None,
    validation_state: PackageValidationState,
    approval_state: ApprovalState,
) -> PackagePermissions:
    """Project the capabilities ``actor`` has over one package head.

    - View/Use/Derive/Export follow ``can_view`` (any viewer may reference a
      package or derive their own root from it — doc 08 §2 "Derive" column);
      Use additionally requires an active, validation-PASSED head (a deprecated or
      validation-blocked package is not offered for new work — doc 08 §4.4).
    - Create-revision / request-validation / request-approval follow ``can_edit``
      (owner or Admin; a non-owner must Derive, not edit — doc 08 §8.2).
    - Approve & Publish is Admin-only and only when a revision is awaiting
      approval with passed validation (CR-02 / doc 08 §4.3).
    """
    can_view = identity_policy.can_view(
        actor, owner_principal_id=owner_principal_id, visibility=visibility_scope
    )
    can_edit = identity_policy.can_edit(actor, owner_principal_id=owner_principal_id)
    is_active = lifecycle_state == _ACTIVE
    is_listed = lifecycle_state in (_ACTIVE, _DEPRECATED)
    validation_passed = validation_state == PackageValidationState.PASSED

    return PackagePermissions(
        can_view=can_view,
        can_use=can_view and is_active and validation_passed,
        can_derive=can_view,
        can_create_revision=can_edit and is_active,
        can_request_validation=can_edit and is_active,
        can_request_approval=can_edit and is_active and validation_passed,
        can_approve_publish=(
            actor.is_admin
            and validation_passed
            and approval_state == ApprovalState.APPROVAL_REQUESTED
        ),
        can_deprecate=can_edit and is_active,
        can_soft_delete=can_edit and is_listed,
        can_export=can_view,
    )


__all__ = [
    "PackagePermissions",
    "package_permissions",
]
