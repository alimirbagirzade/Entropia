"""Stage 6b acceptance — Panel / Management / Logs (doc 19) against a real database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from entropia.application.commands.role_assignment import assign_user_role
from entropia.application.queries.log_projection import get_log_event, list_log_events
from entropia.application.queries.user_registry import (
    get_role_matrix,
    list_registered_users,
    list_system_actors,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import ActorKind, DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    Agent,
    AuditEvent,
    EntityRegistry,
    HumanCredential,
    HumanUser,
    OutboxEvent,
    Principal,
)
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.shared.errors import (
    AdminPanelAccessRequiredError,
    AgentRoleNotAssignableError,
    CursorInvalidError,
    LastAdminProtectedError,
    NotFoundError,
    UserRoleVersionConflictError,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(
    principal_id="user_admin",
    principal_type=PrincipalType.HUMAN,
    role=Role.ADMIN,
    correlation_id="corr_admin",
)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
_BASE_TIME = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_human(
    session, uid: str, username: str, role: Role, *, version: int = 1
) -> HumanUser:
    session.add(Principal(principal_id=uid, principal_type=PrincipalType.HUMAN))
    await session.flush()  # FK: principal before user
    user = HumanUser(
        user_id=uid,
        username=username,
        display_name=username.title(),
        current_role=role,
        status="active",
        version=version,
    )
    session.add(user)
    await session.flush()
    return user


async def _seed_agent(session, aid: str, name: str) -> Agent:
    session.add(Principal(principal_id=aid, principal_type=PrincipalType.AGENT))
    await session.flush()
    agent = Agent(agent_id=aid, name=name, enabled=True)
    session.add(agent)
    await session.flush()
    return agent


def _seed_event(
    session,
    *,
    kind: str,
    severity: str = "info",
    actor_id: str | None = "user_admin",
    actor_kind: ActorKind = ActorKind.HUMAN,
    target_id: str | None = None,
    target_type: str | None = None,
    correlation_id: str | None = None,
    causation_event_id: str | None = None,
    occurred_at: datetime | None = None,
) -> AuditEvent:
    event = audit_repo.add_audit_event(
        session,
        event_kind=kind,
        actor_principal_id=actor_id,
        actor_kind=actor_kind,
        target_entity_id=target_id,
        target_entity_type=target_type,
        correlation_id=correlation_id,
        severity=severity,
    )
    if causation_event_id is not None:
        event.causation_event_id = causation_event_id
    if occurred_at is not None:
        event.occurred_at = occurred_at
    return event


# --------------------------------------------------------------------------- #
# Role assignment command                                                     #
# --------------------------------------------------------------------------- #


async def test_assign_role_success_bumps_version_and_writes_events(session) -> None:
    await _seed_human(session, "usr_bob", "bob", Role.USER)
    await session.commit()
    audit_before = await _count(session, AuditEvent)
    outbox_before = await _count(session, OutboxEvent)

    result = await assign_user_role(
        session,
        ADMIN,
        target_user_id="usr_bob",
        target_role=Role.SUPERVISOR,
        expected_head_revision_id=1,
        reason="promote",
    )
    await session.commit()

    assert result["changed"] is True
    assert result["role"] == "supervisor"
    assert result["version"] == 2
    assert result["audit_event_id"] is not None
    user = await session.get(HumanUser, "usr_bob")
    assert user.current_role == Role.SUPERVISOR
    assert user.role_changed_by == "user_admin"
    assert user.role_changed_at is not None
    # Identity fields untouched by a role change (doc 19 §4.2 step 4).
    assert user.username == "bob"
    assert user.display_name == "Bob"
    assert await _count(session, AuditEvent) == audit_before + 1
    assert await _count(session, OutboxEvent) == outbox_before + 1

    ev = (
        await session.execute(select(AuditEvent).where(AuditEvent.target_entity_id == "usr_bob"))
    ).scalar_one()
    assert ev.event_kind == "user.role_assigned"
    assert ev.previous_state == "user"
    assert ev.new_state == "supervisor"


async def test_assign_role_noop_writes_no_audit(session) -> None:
    await _seed_human(session, "usr_amy", "amy", Role.USER)
    await session.commit()
    audit_before = await _count(session, AuditEvent)

    result = await assign_user_role(
        session, ADMIN, target_user_id="usr_amy", target_role=Role.USER, expected_head_revision_id=1
    )
    await session.commit()

    assert result["changed"] is False
    user = await session.get(HumanUser, "usr_amy")
    assert user.version == 1  # no bump
    assert await _count(session, AuditEvent) == audit_before


async def test_assign_role_version_conflict(session) -> None:
    await _seed_human(session, "usr_carl", "carl", Role.USER, version=3)
    await session.commit()

    with pytest.raises(UserRoleVersionConflictError):
        await assign_user_role(
            session,
            ADMIN,
            target_user_id="usr_carl",
            target_role=Role.SUPERVISOR,
            expected_head_revision_id=2,  # stale
        )


async def test_last_admin_protection(session) -> None:
    await _seed_human(session, "solo_admin", "solo", Role.ADMIN)
    await session.commit()

    with pytest.raises(LastAdminProtectedError):
        await assign_user_role(
            session,
            ADMIN,
            target_user_id="solo_admin",
            target_role=Role.USER,
            expected_head_revision_id=1,
        )
    user = await session.get(HumanUser, "solo_admin")
    assert user.current_role == Role.ADMIN
    assert user.version == 1


async def test_last_admin_protection_session_mode_counts_login_capable(session) -> None:
    """PROV-03: a legacy credentialless Admin pads the Admin ROLE-ROW count to two,
    but in session mode only the login-capable Admin is operational. Demoting the
    one real Admin must still be blocked — a role-row count would wrongly allow it
    and lock the installation out."""
    await _seed_human(session, "user_admin", "legacy", Role.ADMIN)  # no credential
    real = await _seed_human(session, "usr_real", "real", Role.ADMIN)
    session.add(
        HumanCredential(user_id="usr_real", password_hash="argon2id$stub", algorithm="argon2id")
    )
    await session.commit()

    with pytest.raises(LastAdminProtectedError):
        await assign_user_role(
            session,
            ADMIN,
            target_user_id="usr_real",
            target_role=Role.USER,
            expected_head_revision_id=real.version,
            auth_mode="session",
        )
    user = await session.get(HumanUser, "usr_real")
    assert user.current_role == Role.ADMIN and user.version == 1


async def test_last_admin_protection_dev_mode_counts_role_rows(session) -> None:
    """Contrast to the session-mode case: in dev mode an X-Actor-Id Admin needs no
    credential, so both Admin role rows are operational — demoting one is allowed
    (historical behavior preserved). Proves the fix is mode-aware, not always-block."""
    await _seed_human(session, "user_admin", "legacy", Role.ADMIN)  # no credential
    real = await _seed_human(session, "usr_real", "real", Role.ADMIN)
    await session.commit()

    result = await assign_user_role(
        session,
        ADMIN,
        target_user_id="usr_real",
        target_role=Role.USER,
        expected_head_revision_id=real.version,
        auth_mode="dev",
    )
    await session.commit()
    assert result["changed"] is True
    user = await session.get(HumanUser, "usr_real")
    assert user.current_role == Role.USER


async def test_agent_target_rejected(session) -> None:
    await _seed_agent(session, "agent_alpha", "Alpha")
    await session.commit()

    with pytest.raises(AgentRoleNotAssignableError):
        await assign_user_role(
            session,
            ADMIN,
            target_user_id="agent_alpha",
            target_role=Role.SUPERVISOR,
            expected_head_revision_id=1,
        )


async def test_unknown_target_not_found(session) -> None:
    with pytest.raises(NotFoundError):
        await assign_user_role(
            session,
            ADMIN,
            target_user_id="usr_missing",
            target_role=Role.SUPERVISOR,
            expected_head_revision_id=1,
        )


async def test_non_admin_denied_on_assign(session) -> None:
    await _seed_human(session, "usr_dan", "dan", Role.USER)
    await session.commit()

    with pytest.raises(AdminPanelAccessRequiredError):
        await assign_user_role(
            session,
            USER,
            target_user_id="usr_dan",
            target_role=Role.SUPERVISOR,
            expected_head_revision_id=1,
        )


async def test_assign_role_idempotent_replay(session) -> None:
    await _seed_human(session, "usr_eve", "eve", Role.USER)
    await session.commit()
    audit_before = await _count(session, AuditEvent)

    first = await assign_user_role(
        session,
        ADMIN,
        target_user_id="usr_eve",
        target_role=Role.SUPERVISOR,
        expected_head_revision_id=1,
        idempotency_key="key-eve-1",
    )
    await session.commit()
    replay = await assign_user_role(
        session,
        ADMIN,
        target_user_id="usr_eve",
        target_role=Role.SUPERVISOR,
        expected_head_revision_id=1,
        idempotency_key="key-eve-1",
    )
    await session.commit()

    assert replay["audit_event_id"] == first["audit_event_id"]
    assert await _count(session, AuditEvent) == audit_before + 1  # no duplicate event


# --------------------------------------------------------------------------- #
# Logs projection                                                             #
# --------------------------------------------------------------------------- #


async def test_logs_newest_first_and_cursor_pagination(session) -> None:
    for i in range(5):
        _seed_event(
            session,
            kind="user.role_assigned",
            occurred_at=_BASE_TIME + timedelta(minutes=i),
        )
    await session.commit()

    first = await list_log_events(session, ADMIN, limit=2)
    assert len(first["data"]) == 2
    assert first["meta"]["has_more"] is True
    # newest-first: minute 4 then minute 3.
    times = [row["occurred_at"] for row in first["data"]]
    assert times == sorted(times, reverse=True)

    second = await list_log_events(session, ADMIN, limit=2, cursor=first["meta"]["cursor"])
    assert len(second["data"]) == 2
    first_ids = {r["event_id"] for r in first["data"]}
    second_ids = {r["event_id"] for r in second["data"]}
    assert first_ids.isdisjoint(second_ids)  # no overlap across pages


async def test_logs_filters(session) -> None:
    _seed_event(session, kind="user.role_assigned", severity="info", correlation_id="corr_x")
    _seed_event(session, kind="backtest.run_failed", severity="error", correlation_id="corr_y")
    _seed_event(
        session,
        kind="agent.runtime.pause",
        severity="warning",
        actor_id="agent_alpha",
        actor_kind=ActorKind.AGENT,
    )
    await session.commit()

    by_sev = await list_log_events(session, ADMIN, severity="error")
    assert [r["event_kind"] for r in by_sev["data"]] == ["backtest.run_failed"]

    by_family = await list_log_events(session, ADMIN, family="backtest")
    assert all(r["family"] == "backtest" for r in by_family["data"])
    assert len(by_family["data"]) == 1

    by_actor = await list_log_events(session, ADMIN, actor_type="system_agent")
    assert [r["actor_type"] for r in by_actor["data"]] == ["agent"]

    by_corr = await list_log_events(session, ADMIN, correlation_id="corr_x")
    assert [r["correlation_id"] for r in by_corr["data"]] == ["corr_x"]

    empty = await list_log_events(session, ADMIN, family="strategy")
    assert empty["data"] == []
    assert empty["meta"]["has_more"] is False


async def test_logs_invalid_cursor_rejected(session) -> None:
    with pytest.raises(CursorInvalidError):
        await list_log_events(session, ADMIN, cursor="not-a-real-cursor")


async def test_logs_denied_for_non_admin(session) -> None:
    with pytest.raises(AdminPanelAccessRequiredError):
        await list_log_events(session, USER)


async def test_log_detail_with_correlation_chain_and_causation(session) -> None:
    root = _seed_event(
        session,
        kind="user.role_assigned",
        correlation_id="corr_chain",
        occurred_at=_BASE_TIME,
    )
    await session.flush()
    child = _seed_event(
        session,
        kind="resource.changed",
        correlation_id="corr_chain",
        causation_event_id=root.event_id,
        occurred_at=_BASE_TIME + timedelta(seconds=1),
    )
    await session.commit()

    detail = await get_log_event(session, ADMIN, event_id=child.event_id)
    assert detail["event_id"] == child.event_id
    assert detail["causation_event"]["event_id"] == root.event_id
    chain_ids = [r["event_id"] for r in detail["correlation_chain"]]
    assert chain_ids == [root.event_id, child.event_id]  # chain ordered oldest-first
    assert "trace_id" in detail["technical"]


async def test_log_detail_deleted_subject(session) -> None:
    session.add(
        EntityRegistry(
            entity_id="ent_gone",
            entity_type="strategy",
            deletion_state=DeletionState.SOFT_DELETED,
        )
    )
    await session.flush()
    ev = _seed_event(session, kind="strategy.saved", target_id="ent_gone", target_type="strategy")
    await session.commit()

    detail = await get_log_event(session, ADMIN, event_id=ev.event_id)
    assert detail["subject_status"] == "deleted"
    assert detail["subject_deleted"] is True


async def test_log_detail_unknown_event(session) -> None:
    with pytest.raises(NotFoundError):
        await get_log_event(session, ADMIN, event_id="evt_missing")


# --------------------------------------------------------------------------- #
# Management read models                                                       #
# --------------------------------------------------------------------------- #


async def test_user_registry_lists_humans_only(session) -> None:
    await _seed_human(session, "usr_amy", "amy", Role.USER)
    await _seed_human(session, "usr_bob", "bob", Role.ADMIN)
    await _seed_agent(session, "agent_alpha", "Alpha")
    await session.commit()

    page = await list_registered_users(session, ADMIN, limit=50)
    usernames = [r["username"] for r in page["data"]]
    assert usernames == ["amy", "bob"]  # stable username-asc order, agent excluded
    assert all("role" in r and "version" in r for r in page["data"])


async def test_user_registry_keyset(session) -> None:
    for name in ["amy", "bob", "cara"]:
        await _seed_human(session, f"usr_{name}", name, Role.USER)
    await session.commit()

    first = await list_registered_users(session, ADMIN, limit=2)
    assert [r["username"] for r in first["data"]] == ["amy", "bob"]
    assert first["meta"]["has_more"] is True
    second = await list_registered_users(session, ADMIN, limit=2, cursor=first["meta"]["cursor"])
    assert [r["username"] for r in second["data"]] == ["cara"]


async def test_system_actors_projection(session) -> None:
    await _seed_agent(session, "agent_alpha", "Alpha")
    await session.commit()

    result = await list_system_actors(session, ADMIN)
    assert result["data"][0]["actor_type"] == "system_agent"
    assert result["data"][0]["assignable"] is False


async def test_role_matrix_admin_only(session) -> None:
    matrix = await get_role_matrix(session, ADMIN)
    assert matrix["policy_revision"]
    with pytest.raises(AdminPanelAccessRequiredError):
        await get_role_matrix(session, USER)


async def test_management_denied_for_non_admin(session) -> None:
    with pytest.raises(AdminPanelAccessRequiredError):
        await list_registered_users(session, USER)
    with pytest.raises(AdminPanelAccessRequiredError):
        await list_system_actors(session, USER)


# --------------------------------------------------------------------------- #
# Regression: review findings F1 (family first-match) + F2 (last-admin race)   #
# --------------------------------------------------------------------------- #


async def test_logs_family_filter_first_match_wins(session) -> None:
    # 'user.role_import_note' is classified role_access (matches 'user.' first) yet
    # also contains the 'data' token 'import'. The family filter must agree with the
    # displayed family: it appears under role_access, never under data.
    from entropia.domain.admin_panel import event_family

    assert event_family("user.role_import_note") == "role_access"
    _seed_event(session, kind="user.role_import_note")
    await session.commit()

    role_page = await list_log_events(session, ADMIN, family="role_access")
    assert "user.role_import_note" in [r["event_kind"] for r in role_page["data"]]

    data_page = await list_log_events(session, ADMIN, family="data")
    assert "user.role_import_note" not in [r["event_kind"] for r in data_page["data"]]


async def test_last_admin_race_serialized(session) -> None:
    # Two Admins demoted concurrently from separate transactions: the advisory lock
    # must serialize the count+check so exactly one succeeds and one is blocked —
    # never a zero-admin outcome (review finding F2).
    import asyncio
    import os

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    await _seed_human(session, "adm_a", "adma", Role.ADMIN)
    await _seed_human(session, "adm_b", "admb", Role.ADMIN)
    await session.commit()

    url = os.getenv(
        "TEST_DATABASE_URL",
        os.getenv("DATABASE_URL", "postgresql+asyncpg://entropia:entropia@localhost:5432/entropia"),
    )
    engine = create_async_engine(url, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def _demote(uid: str) -> str:
        async with factory() as s:
            try:
                await assign_user_role(
                    s,
                    ADMIN,
                    target_user_id=uid,
                    target_role=Role.USER,
                    expected_head_revision_id=1,
                )
                await s.commit()
                return "ok"
            except LastAdminProtectedError:
                await s.rollback()
                return "blocked"

    try:
        results = await asyncio.gather(_demote("adm_a"), _demote("adm_b"))
    finally:
        await engine.dispose()

    assert sorted(results) == ["blocked", "ok"]  # exactly one demotion, one blocked
    remaining = (
        await session.execute(
            select(func.count()).select_from(HumanUser).where(HumanUser.current_role == Role.ADMIN)
        )
    ).scalar_one()
    assert remaining == 1  # never zero admins
