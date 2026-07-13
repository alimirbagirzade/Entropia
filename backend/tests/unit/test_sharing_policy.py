"""Unit tests for the GAP-17 explicit-sharing policy and the fail-closed
``can_view`` grantee check (Master Reference §6, §6.4)."""

from __future__ import annotations

import pytest

from entropia.domain.identity import policy as identity_policy
from entropia.domain.identity.actor import Actor
from entropia.domain.lifecycle.enums import ApprovalState, PrincipalType, Role
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.package.permissions import package_permissions
from entropia.domain.sharing import (
    ensure_can_manage_shares,
    ensure_distinct_grantee,
    ensure_shareable_visibility,
)
from entropia.shared.errors import (
    ShareManagementForbiddenError,
    ShareNotAllowedForVisibilityError,
    ShareWithSelfError,
)

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
GRANTEE = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_3", principal_type=PrincipalType.HUMAN, role=Role.USER)


def test_can_view_explicitly_shared_is_fail_closed_without_a_grant() -> None:
    # A non-owner with NO resolved grant can never read an explicitly_shared
    # resource — the prior "any authenticated actor" over-share is gone.
    assert not identity_policy.can_view(
        OTHER, owner_principal_id="user_1", visibility="explicitly_shared"
    )
    assert not identity_policy.can_view(
        OTHER,
        owner_principal_id="user_1",
        visibility="explicitly_shared",
        shared_principal_ids=set(),
    )


def test_can_view_explicitly_shared_honors_the_resolved_grantee_set() -> None:
    grantees = {"user_2"}
    assert identity_policy.can_view(
        GRANTEE,
        owner_principal_id="user_1",
        visibility="explicitly_shared",
        shared_principal_ids=grantees,
    )
    # A different actor not in the set is still refused.
    assert not identity_policy.can_view(
        OTHER,
        owner_principal_id="user_1",
        visibility="explicitly_shared",
        shared_principal_ids=grantees,
    )


def test_can_view_owner_and_admin_ignore_the_grant_set() -> None:
    assert identity_policy.can_view(
        OWNER, owner_principal_id="user_1", visibility="explicitly_shared"
    )
    assert identity_policy.can_view(
        ADMIN, owner_principal_id="user_1", visibility="explicitly_shared"
    )


def test_manage_shares_requires_owner_or_admin() -> None:
    ensure_can_manage_shares(OWNER, owner_principal_id="user_1")  # owner: ok
    ensure_can_manage_shares(ADMIN, owner_principal_id="user_1")  # admin: ok
    with pytest.raises(ShareManagementForbiddenError):
        ensure_can_manage_shares(OTHER, owner_principal_id="user_1")
    # A grantee is a viewer, not a manager — cannot re-share.
    with pytest.raises(ShareManagementForbiddenError):
        ensure_can_manage_shares(GRANTEE, owner_principal_id="user_1")


def test_shareable_visibility_rejects_public_scopes() -> None:
    ensure_shareable_visibility("private")
    ensure_shareable_visibility("explicitly_shared")
    for public in ("published", "system"):
        with pytest.raises(ShareNotAllowedForVisibilityError):
            ensure_shareable_visibility(public)


def test_distinct_grantee_rejects_self_share() -> None:
    ensure_distinct_grantee("user_1", "user_2")  # distinct: ok
    with pytest.raises(ShareWithSelfError):
        ensure_distinct_grantee("user_1", "user_1")


def _perms(actor: Actor, *, owner: str | None, visibility: str, lifecycle: str = "active"):
    return package_permissions(
        actor,
        owner_principal_id=owner,
        visibility_scope=visibility,
        lifecycle_state=lifecycle,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.DRAFT,
    )


def test_can_share_flag_is_owner_only_on_an_active_private_head() -> None:
    assert _perms(OWNER, owner="user_1", visibility="private").can_share
    assert _perms(OWNER, owner="user_1", visibility="explicitly_shared").can_share
    # A grantee/foreign user never gains share authority.
    assert not _perms(OTHER, owner="user_1", visibility="explicitly_shared").can_share
    # Sharing a published head is a no-op (already public) -> not offered.
    assert not _perms(OWNER, owner="user_1", visibility="published").can_share
    # A deprecated head is not active -> not offered.
    assert not _perms(OWNER, owner="user_1", visibility="private", lifecycle="deprecated").can_share
