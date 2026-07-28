"""AOS-03 on the attach surface, against a real database (doc 03 §11.1).

``POST /mainboards/{id}/items`` is the one route whose client-supplied field is
literally named ``item_kind``. It resolves the workspace/root/revision first, so
the rejection cannot be proven DB-free like the other two surfaces — hence this
integration test rather than a contract one.

Asserts both halves of AOS-03: the spec-named code comes back, AND no working item
is created by the rejected call.
"""

from __future__ import annotations

import pytest

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import Principal
from entropia.shared.errors import InvalidItemKindError

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_principal(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()


@pytest.mark.parametrize("legacy", ["signal_package", "trade_log_package"])
async def test_aos_03_attach_with_legacy_item_kind_creates_no_item(session, legacy: str) -> None:
    await _seed_principal(session)
    created = await mb_cmd.create_work_object(
        session,
        USER1,
        object_kind="strategy",
        payload={"name": "Strat"},
    )
    await session.flush()
    board = await mb_query.get_default_mainboard(session, USER1)

    with pytest.raises(InvalidItemKindError) as exc:
        await mb_cmd.attach_mainboard_item(
            session,
            USER1,
            workspace_id=board["workspace_id"],
            root_id=created["root_id"],
            revision_id=created["revision_id"],
            item_kind=legacy,
        )

    assert exc.value.code == "INVALID_ITEM_KIND"
    assert exc.value.field_path == "item_kind"
    # Second half of AOS-03: nothing was composed onto the board.
    after = await mb_query.get_default_mainboard(session, USER1)
    assert after["items"] == []
