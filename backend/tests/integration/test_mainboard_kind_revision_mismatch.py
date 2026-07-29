"""AOS-12 on the two revision-binding surfaces, against a real database (doc 03 §14).

The spec's sentence has two halves and this module asserts both: a Trading Signal
attach request carrying a Trade Log revision id returns ``KIND_REVISION_MISMATCH``
**and** creates no partial item. A ``pin_revision`` patch binds a revision id to an
item exactly the way an attach does, so it is proven here too — a gate that is
named on one surface and swallowed on the other is not fail-closed.

The negative half matters as much as the positive one: a revision of the *same*
kind that simply belongs to a different root keeps the pre-existing generic
``VALIDATION_ERROR``. The spec names no code for that case and inventing one would
outrun the contract; AOS-12 is specifically the cross-KIND defect.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import Principal
from entropia.shared.errors import KindRevisionMismatchError, ValidationError

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
_PAST = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)


async def _seed_principal(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _external(session, kind: str, *, name: str) -> dict:
    """Create an external work object (Trading Signal / Trade Log) with rev1."""
    created = await mb_cmd.create_work_object(
        session,
        USER1,
        object_kind=kind,
        payload={"name": name},
        available_time=_PAST,
    )
    await session.flush()
    return created


async def test_aos_12_signal_attach_with_a_trade_log_revision_id(session) -> None:
    """A Trading Signal attach carrying a Trade Log revision id -> KIND_REVISION_MISMATCH."""
    await _seed_principal(session)
    signal = await _external(session, "trading_signal", name="Sig")
    trade_log = await _external(session, "trade_log", name="Log")
    board = await mb_query.get_default_mainboard(session, USER1)

    with pytest.raises(KindRevisionMismatchError) as exc:
        await mb_cmd.attach_mainboard_item(
            session,
            USER1,
            workspace_id=board["workspace_id"],
            root_id=signal["root_id"],
            revision_id=trade_log["revision_id"],
            item_kind="trading_signal",
        )

    assert exc.value.code == "KIND_REVISION_MISMATCH"
    assert exc.value.http_status == 422
    assert exc.value.scope_id == trade_log["revision_id"]
    assert exc.value.field_path == "revision_id"
    # Second half of AOS-12: nothing was composed onto the board.
    after = await mb_query.get_default_mainboard(session, USER1)
    assert after["items"] == []


async def test_aos_12_holds_without_a_client_supplied_item_kind(session) -> None:
    """The gate compares the ROOT's server-derived kind, so omitting item_kind
    cannot route the request past it into the generic message."""
    await _seed_principal(session)
    signal = await _external(session, "trading_signal", name="Sig2")
    trade_log = await _external(session, "trade_log", name="Log2")
    board = await mb_query.get_default_mainboard(session, USER1)

    with pytest.raises(KindRevisionMismatchError):
        await mb_cmd.attach_mainboard_item(
            session,
            USER1,
            workspace_id=board["workspace_id"],
            root_id=signal["root_id"],
            revision_id=trade_log["revision_id"],
        )

    after = await mb_query.get_default_mainboard(session, USER1)
    assert after["items"] == []


async def test_aos_12_is_symmetric_on_the_attach_surface(session) -> None:
    """The reverse direction — a Trade Log attach carrying a Signal revision id."""
    await _seed_principal(session)
    signal = await _external(session, "trading_signal", name="Sig3")
    trade_log = await _external(session, "trade_log", name="Log3")
    board = await mb_query.get_default_mainboard(session, USER1)

    with pytest.raises(KindRevisionMismatchError):
        await mb_cmd.attach_mainboard_item(
            session,
            USER1,
            workspace_id=board["workspace_id"],
            root_id=trade_log["root_id"],
            revision_id=signal["revision_id"],
        )

    after = await mb_query.get_default_mainboard(session, USER1)
    assert after["items"] == []


async def test_aos_12_pin_revision_cannot_cross_kinds_either(session) -> None:
    """``pin_revision`` binds a revision id the same way an attach does."""
    await _seed_principal(session)
    signal = await _external(session, "trading_signal", name="Sig4")
    trade_log = await _external(session, "trade_log", name="Log4")
    board = await mb_query.get_default_mainboard(session, USER1)
    item = await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=board["workspace_id"],
        root_id=signal["root_id"],
        revision_id=signal["revision_id"],
    )
    await session.flush()

    with pytest.raises(KindRevisionMismatchError) as exc:
        await mb_cmd.patch_mainboard_item(
            session,
            USER1,
            item_id=item["item_id"],
            intent="pin_revision",
            expected_row_version=item["row_version"],
            revision_id=trade_log["revision_id"],
        )

    assert exc.value.code == "KIND_REVISION_MISMATCH"
    # The item still pins the revision it was attached with — no partial re-pin.
    after = await mb_query.get_default_mainboard(session, USER1)
    assert [row["pinned_revision_id"] for row in after["items"]] == [signal["revision_id"]]


async def test_a_same_kind_revision_of_another_root_keeps_the_generic_code(session) -> None:
    """The negative half: AOS-12 narrows the cross-KIND case OUT of the generic
    "does not belong to this work object" error — it does not replace it."""
    await _seed_principal(session)
    first = await _external(session, "trading_signal", name="SigA")
    second = await _external(session, "trading_signal", name="SigB")
    board = await mb_query.get_default_mainboard(session, USER1)

    with pytest.raises(ValidationError) as exc:
        await mb_cmd.attach_mainboard_item(
            session,
            USER1,
            workspace_id=board["workspace_id"],
            root_id=first["root_id"],
            revision_id=second["revision_id"],
        )

    assert exc.value.code == "VALIDATION_ERROR"
    assert not isinstance(exc.value, KindRevisionMismatchError)
    after = await mb_query.get_default_mainboard(session, USER1)
    assert after["items"] == []
