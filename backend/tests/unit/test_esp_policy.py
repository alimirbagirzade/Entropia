"""ESP authorization policy (doc 09 §2, §10.3, CR-02)."""

from __future__ import annotations

import pytest

from entropia.domain.esp import policy as esp_policy
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.shared.errors import AccessDeniedError, ApprovalRequiresAdmin

ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
SUPERVISOR = Actor(principal_id="sup_1", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
AGENT = Actor(principal_id="agent_1", principal_type=PrincipalType.AGENT, role=None)


def test_admin_can_activate() -> None:
    esp_policy.ensure_can_activate(ADMIN)  # no raise


def test_supervisor_cannot_activate() -> None:
    with pytest.raises(ApprovalRequiresAdmin):
        esp_policy.ensure_can_activate(SUPERVISOR)


def test_agent_cannot_activate() -> None:
    with pytest.raises(ApprovalRequiresAdmin):
        esp_policy.ensure_can_activate(AGENT)


def test_admin_can_deprecate() -> None:
    esp_policy.ensure_can_deprecate(ADMIN)  # no raise


def test_user_cannot_deprecate() -> None:
    with pytest.raises(ApprovalRequiresAdmin):
        esp_policy.ensure_can_deprecate(USER)


def test_any_authenticated_actor_can_view_system_resolver() -> None:
    # Trusted resolvers are system-owned/published -> visible to all (doc 09 §2).
    esp_policy.ensure_can_view(USER, owner_principal_id=None, visibility="system")
    esp_policy.ensure_can_view(AGENT, owner_principal_id=None, visibility="published")


def test_private_proposal_hidden_from_non_owner() -> None:
    with pytest.raises(AccessDeniedError):
        esp_policy.ensure_can_view(USER, owner_principal_id="someone_else", visibility="private")
