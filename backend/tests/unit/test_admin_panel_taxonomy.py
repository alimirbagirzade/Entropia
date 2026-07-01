"""Unit tests for the Admin Panel domain: log taxonomy, cursor, role matrix (doc 19)."""

from __future__ import annotations

import pytest

from entropia.domain.admin_panel import (
    ROLE_MATRIX_REVISION,
    build_role_matrix,
    decode_log_cursor,
    encode_log_cursor,
    event_family,
    normalize_actor_type,
    normalize_family,
    normalize_severity,
)
from entropia.domain.admin_panel.log_taxonomy import LOG_EVENT_FAMILIES
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_admin_panel
from entropia.domain.lifecycle.enums import ActorKind, PrincipalType, Role
from entropia.shared.errors import (
    AdminPanelAccessRequiredError,
    CursorInvalidError,
    LogFilterInvalidError,
    UnauthenticatedError,
)


def _human(role: Role) -> Actor:
    return Actor(principal_id="u1", principal_type=PrincipalType.HUMAN, role=role)


# ---------- require_admin_panel ----------


def test_require_admin_panel_allows_admin() -> None:
    require_admin_panel(_human(Role.ADMIN))  # no raise


@pytest.mark.parametrize("role", [Role.SUPERVISOR, Role.USER])
def test_require_admin_panel_denies_non_admin(role: Role) -> None:
    with pytest.raises(AdminPanelAccessRequiredError):
        require_admin_panel(_human(role))


def test_require_admin_panel_denies_anonymous() -> None:
    with pytest.raises(UnauthenticatedError):
        require_admin_panel(Actor.anonymous())


def test_require_admin_panel_denies_agent() -> None:
    agent = Actor(principal_id="agent_alpha", principal_type=PrincipalType.AGENT, role=None)
    with pytest.raises(AdminPanelAccessRequiredError):
        require_admin_panel(agent)


# ---------- event_family classification ----------


@pytest.mark.parametrize(
    ("kind", "family"),
    [
        ("user.role_assigned", "role_access"),
        ("backtest.run_failed", "backtest"),
        ("dataset.approved", "data"),
        ("package.precheck_passed", "package"),
        ("strategy.saved", "strategy"),
        ("agent.runtime.pause", "agent"),
        ("entity.soft_deleted", "trash_lifecycle"),
        ("something.unknown_kind", "system_other"),
    ],
)
def test_event_family(kind: str, family: str) -> None:
    assert event_family(kind) == family


def test_every_family_is_registered() -> None:
    assert "all" in LOG_EVENT_FAMILIES
    assert "system_other" in LOG_EVENT_FAMILIES


# ---------- filter normalization ----------


def test_normalize_family_defaults_and_validates() -> None:
    assert normalize_family(None) == "all"
    assert normalize_family("") == "all"
    assert normalize_family("Backtest") == "backtest"
    with pytest.raises(LogFilterInvalidError):
        normalize_family("nonsense")


def test_normalize_severity() -> None:
    assert normalize_severity(None) is None
    assert normalize_severity("ERROR") == "error"
    with pytest.raises(LogFilterInvalidError):
        normalize_severity("critical")


def test_normalize_actor_type() -> None:
    assert normalize_actor_type(None) is None
    assert normalize_actor_type("human") == ActorKind.HUMAN
    assert normalize_actor_type("system_agent") == ActorKind.AGENT
    assert normalize_actor_type("system") == ActorKind.SYSTEM_SERVICE
    with pytest.raises(LogFilterInvalidError):
        normalize_actor_type("robot")


# ---------- cursor roundtrip ----------


def test_log_cursor_roundtrip() -> None:
    token = encode_log_cursor(occurred_at_iso="2026-07-01T00:00:00+00:00", event_id="evt_123")
    assert decode_log_cursor(token) == ("2026-07-01T00:00:00+00:00", "evt_123")


def test_log_cursor_rejects_foreign_namespace() -> None:
    from entropia.domain.agent_lab.cursor import encode_cursor

    foreign = encode_cursor("other_ns", last_key="2026|evt_1")
    with pytest.raises(CursorInvalidError):
        decode_log_cursor(foreign)


def test_log_cursor_rejects_garbage() -> None:
    with pytest.raises(CursorInvalidError):
        decode_log_cursor("!!!not-base64!!!")


# ---------- role matrix ----------


def test_role_matrix_projection() -> None:
    matrix = build_role_matrix()
    assert matrix["policy_revision"] == ROLE_MATRIX_REVISION
    roles = {row["role"]: row for row in matrix["rows"]}
    assert set(roles) == {"admin", "supervisor", "user", "agent"}
    # Only Admin manages roles; Agent is a non-assignable system actor.
    assert roles["admin"]["role_assignment"] == "manage"
    assert roles["supervisor"]["assignable"] is True
    assert roles["agent"]["assignable"] is False
    assert roles["agent"]["is_system_actor"] is True
