"""Unit tests for the Package Library permission projection (doc 08 §2, §4.2)."""

from __future__ import annotations

from entropia.domain.identity.actor import Actor
from entropia.domain.lifecycle.enums import ApprovalState, PrincipalType, Role
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.package.permissions import PackagePermissions, package_permissions

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
GUEST = Actor.anonymous()


def _perms(
    actor: Actor,
    *,
    owner: str | None = "user_1",
    visibility: str = "private",
    lifecycle: str | None = "active",
    validation: PackageValidationState = PackageValidationState.PASSED,
    approval: ApprovalState = ApprovalState.DRAFT,
) -> PackagePermissions:
    return package_permissions(
        actor,
        owner_principal_id=owner,
        visibility_scope=visibility,
        lifecycle_state=lifecycle,
        validation_state=validation,
        approval_state=approval,
    )


def test_owner_of_active_passed_package_has_full_edit_rights() -> None:
    p = _perms(OWNER)
    assert p.can_view and p.can_use and p.can_derive
    assert p.can_create_revision and p.can_request_validation and p.can_request_approval
    assert p.can_deprecate and p.can_soft_delete and p.can_export
    assert not p.can_approve_publish  # owner is not Admin (CR-02)


def test_foreign_user_can_view_and_derive_but_not_edit_published() -> None:
    p = _perms(OTHER, owner="user_1", visibility="published")
    assert p.can_view and p.can_use and p.can_derive and p.can_export
    assert not p.can_create_revision  # non-owner must Derive, not edit (doc 08 §8.2)
    assert not p.can_request_validation
    assert not p.can_request_approval
    assert not p.can_deprecate
    assert not p.can_soft_delete


def test_admin_can_approve_publish_only_when_requested_and_passed() -> None:
    requested = _perms(ADMIN, owner="user_1", approval=ApprovalState.APPROVAL_REQUESTED)
    assert requested.can_approve_publish
    draft = _perms(ADMIN, owner="user_1", approval=ApprovalState.DRAFT)
    assert not draft.can_approve_publish
    failed = _perms(
        ADMIN,
        owner="user_1",
        validation=PackageValidationState.FAILED,
        approval=ApprovalState.APPROVAL_REQUESTED,
    )
    assert not failed.can_approve_publish
    # Already-approved and rejected heads must NOT re-trigger publish — pins the
    # `== APPROVAL_REQUESTED` equality against a looser `!= DRAFT` regression (CR-02).
    assert not _perms(ADMIN, owner="user_1", approval=ApprovalState.APPROVED).can_approve_publish
    assert not _perms(ADMIN, owner="user_1", approval=ApprovalState.REJECTED).can_approve_publish


def test_foreign_viewer_cannot_use_deprecated_or_failed_package() -> None:
    # can_use gating (active + validation passed) holds on the non-owner axis too.
    deprecated = _perms(OTHER, owner="user_1", visibility="published", lifecycle="deprecated")
    assert deprecated.can_view and not deprecated.can_use
    blocked = _perms(
        OTHER, owner="user_1", visibility="published", validation=PackageValidationState.FAILED
    )
    assert blocked.can_view and not blocked.can_use


def test_deprecated_package_is_not_useable_or_deprecatable() -> None:
    p = _perms(OWNER, lifecycle="deprecated")
    assert not p.can_use  # deprecated is not offered for new work by default
    assert not p.can_create_revision
    assert not p.can_deprecate
    assert p.can_soft_delete  # still removable to Trash
    assert p.can_view and p.can_derive


def test_validation_blocked_package_cannot_be_used_or_approval_requested() -> None:
    p = _perms(OWNER, validation=PackageValidationState.FAILED)
    assert not p.can_use
    assert not p.can_request_approval
    assert p.can_create_revision  # editing to fix the revision is still allowed
    assert p.can_request_validation


def test_guest_sees_nothing_on_a_private_package() -> None:
    p = _perms(GUEST, owner="user_1", visibility="private")
    assert not p.can_view
    assert not p.can_use
    assert not p.can_derive
    assert not p.can_export
    assert not p.can_create_revision
