"""Stage 1 acceptance — exercised against a real database."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands.deletion import (
    restore_entity,
    soft_delete_entity,
)
from entropia.application.commands.entities import create_entity, save_revision
from entropia.application.commands.roles import change_user_role
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    EntityRevision,
    HumanUser,
    OutboxEvent,
    Principal,
    TrashEntry,
)
from entropia.shared.errors import LastAdminProtectedError, StaleRevisionError

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def test_create_inserts_revision_and_audit_and_outbox(session) -> None:
    before_audit = await _count(session, AuditEvent)
    before_outbox = await _count(session, OutboxEvent)

    root = await create_entity(session, USER, entity_type="demo_entity", payload={"v": 1})
    await session.commit()

    assert root.row_version == 1
    assert root.current_revision_id is not None
    assert await _count(session, EntityRevision) >= 1
    assert await _count(session, AuditEvent) == before_audit + 1
    assert await _count(session, OutboxEvent) == before_outbox + 1


async def test_save_advances_head_and_concurrency_guard(session) -> None:
    root = await create_entity(session, USER, entity_type="demo_entity", payload={"v": 1})
    await session.commit()
    first_head = root.current_revision_id

    await save_revision(
        session, USER, entity_id=root.entity_id, payload={"v": 2}, expected_row_version=1
    )
    await session.commit()
    assert root.row_version == 2
    assert root.current_revision_id != first_head

    # Stale expected_row_version -> 409 StaleRevision.
    with pytest.raises(StaleRevisionError):
        await save_revision(
            session, USER, entity_id=root.entity_id, payload={"v": 3}, expected_row_version=1
        )


async def test_soft_delete_then_restore_reuses_identity(session) -> None:
    root = await create_entity(session, USER, entity_type="demo_entity", payload={"v": 1})
    await session.commit()
    entity_id = root.entity_id
    head = root.current_revision_id
    trash_before = await _count(session, TrashEntry)

    await soft_delete_entity(session, USER, entity_id=entity_id, reason="cleanup")
    await session.commit()
    assert root.deletion_state == DeletionState.SOFT_DELETED
    assert await _count(session, TrashEntry) == trash_before + 1

    # Restore is Admin-only and reuses the same entity_id + head revision.
    await restore_entity(session, ADMIN, entity_id=entity_id)
    await session.commit()
    assert root.deletion_state == DeletionState.ACTIVE
    assert root.entity_id == entity_id
    assert root.current_revision_id == head


async def test_last_admin_protection(session) -> None:
    session.add(Principal(principal_id="solo_admin", principal_type=PrincipalType.HUMAN))
    session.add(
        HumanUser(
            user_id="solo_admin",
            username="solo_admin",
            display_name="Solo",
            current_role=Role.ADMIN,
            status="active",
        )
    )
    await session.commit()

    with pytest.raises(LastAdminProtectedError):
        await change_user_role(session, ADMIN, target_user_id="solo_admin", new_role=Role.USER)
