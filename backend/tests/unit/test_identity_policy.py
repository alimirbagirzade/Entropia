import pytest

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import (
    can_edit,
    can_view,
    ensure_not_last_admin,
    require_admin,
    require_role,
)
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.shared.errors import (
    AccessDeniedError,
    LastAdminProtectedError,
    UnauthenticatedError,
)


def _human(role: Role, pid: str = "user_1") -> Actor:
    return Actor(principal_id=pid, principal_type=PrincipalType.HUMAN, role=role)


def test_require_admin_rejects_anonymous() -> None:
    with pytest.raises(UnauthenticatedError):
        require_admin(Actor.anonymous())


def test_require_admin_rejects_non_admin() -> None:
    with pytest.raises(AccessDeniedError):
        require_admin(_human(Role.USER))


def test_require_admin_allows_admin() -> None:
    require_admin(_human(Role.ADMIN))  # no raise


def test_require_role() -> None:
    require_role(_human(Role.SUPERVISOR), [Role.SUPERVISOR, Role.ADMIN])
    with pytest.raises(AccessDeniedError):
        require_role(_human(Role.USER), [Role.ADMIN])


def test_can_view_published_is_public() -> None:
    assert can_view(Actor.anonymous(), owner_principal_id="x", visibility="published")
    assert not can_view(Actor.anonymous(), owner_principal_id="x", visibility="private")


def test_can_view_owner_sees_private() -> None:
    me = _human(Role.USER, "user_1")
    assert can_view(me, owner_principal_id="user_1", visibility="private")
    assert not can_view(me, owner_principal_id="user_2", visibility="private")


def test_admin_sees_everything() -> None:
    assert can_view(_human(Role.ADMIN), owner_principal_id="other", visibility="private")
    assert can_edit(_human(Role.ADMIN), owner_principal_id="other")


def test_can_edit_only_own() -> None:
    me = _human(Role.USER, "user_1")
    assert can_edit(me, owner_principal_id="user_1")
    assert not can_edit(me, owner_principal_id="user_2")


def test_last_admin_protection() -> None:
    # Demoting the last admin is blocked.
    with pytest.raises(LastAdminProtectedError):
        ensure_not_last_admin(target_is_admin=True, becomes_admin=False, active_admin_count=1)
    # With another admin present, demotion is fine.
    ensure_not_last_admin(target_is_admin=True, becomes_admin=False, active_admin_count=2)
    # Promoting to admin is always fine.
    ensure_not_last_admin(target_is_admin=False, becomes_admin=True, active_admin_count=1)
