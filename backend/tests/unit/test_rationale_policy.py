"""Rationale Families shared-editing policy (doc 10 §2, DOMAIN_MODEL §6).

Every authenticated actor (Admin/Supervisor/User/Agent) may manage families and
edit assignments — ownership is irrelevant. Only the Guest is rejected.
"""

from __future__ import annotations

import pytest

from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.rationale.policy import (
    ensure_can_edit_assignments,
    ensure_can_manage_families,
)
from entropia.shared.errors import UnauthenticatedError

_AUTHENTICATED = [
    Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN),
    Actor(principal_id="sup_1", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR),
    Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER),
    Actor(principal_id="agent_1", principal_type=PrincipalType.AGENT, role=None),
]


@pytest.mark.parametrize("actor", _AUTHENTICATED)
def test_all_authenticated_actors_can_manage_and_assign(actor: Actor) -> None:
    # Shared exception: no raise for any authenticated actor, regardless of role.
    ensure_can_manage_families(actor)
    ensure_can_edit_assignments(actor)


def test_guest_cannot_manage_families() -> None:
    with pytest.raises(UnauthenticatedError):
        ensure_can_manage_families(Actor.anonymous())


def test_guest_cannot_edit_assignments() -> None:
    with pytest.raises(UnauthenticatedError):
        ensure_can_edit_assignments(Actor.anonymous())
