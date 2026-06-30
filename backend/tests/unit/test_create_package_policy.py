"""Unit tests for Create-Package authorization policy (Stage 2e, CR-02)."""

from __future__ import annotations

import pytest

from entropia.domain.create_package.policy import (
    ensure_can_approve_publish,
    ensure_can_create_request,
    ensure_can_operate_request,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.shared.errors import (
    AccessDeniedError,
    ApprovalRequiresAdmin,
    UnauthenticatedError,
)

ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
AGENT = Actor(principal_id="agent_1", principal_type=PrincipalType.AGENT, role=None)


def test_create_request_requires_auth() -> None:
    ensure_can_create_request(USER)
    ensure_can_create_request(AGENT)
    with pytest.raises(UnauthenticatedError):
        ensure_can_create_request(Actor.anonymous())


def test_operate_request_owner_or_admin() -> None:
    ensure_can_operate_request(USER, owner_principal_id="user_1")
    ensure_can_operate_request(ADMIN, owner_principal_id="user_1")
    with pytest.raises(AccessDeniedError):
        ensure_can_operate_request(OTHER, owner_principal_id="user_1")


def test_approve_is_admin_only() -> None:
    ensure_can_approve_publish(ADMIN)
    with pytest.raises(ApprovalRequiresAdmin):
        ensure_can_approve_publish(USER)
    with pytest.raises(ApprovalRequiresAdmin):
        ensure_can_approve_publish(AGENT)
