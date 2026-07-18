"""Regression: "Add Strategy" — create a Strategy work object in ONE transaction,
then attach it to the default Mainboard in a SEPARATE transaction, exactly as the
two sequential HTTP requests do (POST /work-objects then POST /mainboards/{id}/items).

The pre-existing ``test_mainboard_persistence`` suite exercises create+attach inside
ONE session, where the SQLAlchemy identity map masks any commit/visibility gap. This
test crosses the real request boundary — a committed work object in session A must be
found by ``attach_mainboard_item`` in a fresh session B and then appear in the default
projection read from a third session — so a persistence-visibility regression on this
path (the reported create→attach 404) cannot pass silently.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import Principal

pytestmark = pytest.mark.integration

USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def test_add_strategy_create_then_attach_across_transactions(session) -> None:
    # Session A — seed the principal and auto-create the default workspace (the
    # Mainboard-page GET), then create a Strategy work object and COMMIT it.
    session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()
    workspace_id = (await mb_query.get_default_mainboard(session, USER))["workspace_id"]
    created = await mb_cmd.create_work_object(
        session, USER, object_kind="strategy", payload={}, idempotency_key="add-strategy-create"
    )
    await session.commit()
    root_id, revision_id = created["root_id"], created["revision_id"]

    # A brand-new session on the same engine — the second HTTP request's unit of
    # work. The just-committed work object must be visible here (no 404), attach
    # must write the item, and the composition hash must move.
    factory = async_sessionmaker(bind=session.bind, expire_on_commit=False)
    async with factory() as attach_session:
        item = await mb_cmd.attach_mainboard_item(
            attach_session,
            USER,
            workspace_id=workspace_id,
            root_id=root_id,
            revision_id=revision_id,
            idempotency_key="add-strategy-attach",
        )
        await attach_session.commit()
    assert item["item_kind"] == "strategy"
    assert item["work_object_root_id"] == root_id
    assert item["pinned_revision_id"] == revision_id
    assert item["composition_hash"] is not None

    # A third session — the post-attach Mainboard refetch. The inline row is present
    # in the active projection, pinned to the exact created revision.
    async with factory() as read_session:
        projection = await mb_query.get_default_mainboard(read_session, USER)
    rows = projection["items"]
    assert [r["item_id"] for r in rows] == [item["item_id"]]
    assert rows[0]["work_object_root_id"] == root_id
    assert rows[0]["pinned_revision_id"] == revision_id
    assert rows[0]["is_enabled"] is True
