"""S-L1 / doc 13 §7.2 + §10.2 Flow E — the 409 carries current_draft + changed_paths[].

Flow E: a save attempt carrying the OLD expected_row_version returns 409 CONFLICT and
the server supplies the current draft plus the changed paths; the UI presents the
local unsaved fields against the server state in a compare view and the user chooses
reapply or discard. Last-write-wins is forbidden.

ALLOCATION_DRAFT_CONFLICT used to be a bare code + message. A client receiving that
can only discard the user's edits or blindly re-PUT and clobber — both are the
outcome Flow E rules out, because neither can build the compare view.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.shared.errors import AllocationDraftConflictError
from tests.integration.test_allocation_persistence import (
    USER1,
    _composition_with_items,
    _entries,
    _put_shared_draft,
    _seed_principals,
)

pytestmark = pytest.mark.integration


def _conflict_detail(exc: AllocationDraftConflictError) -> dict[str, Any]:
    assert len(exc.details) == 1
    return exc.details[0]


async def _stale_put(
    session, composition_id: str, entries: list[dict[str, Any]], *, expected: int
) -> AllocationDraftConflictError:
    with pytest.raises(AllocationDraftConflictError) as excinfo:
        await _put_shared_draft(
            session, USER1, composition_id, entries, expected_row_version=expected
        )
    await session.rollback()
    return excinfo.value


async def test_stale_put_returns_the_server_draft_and_the_disputed_paths(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1, count=2)
    await _put_shared_draft(
        session, USER1, composition_id, _entries((items[0], "40"), (items[1], "35"))
    )

    # A second tab saved v1; this caller still holds v0 and changed one share.
    exc = await _stale_put(
        session, composition_id, _entries((items[0], "40"), (items[1], "50")), expected=0
    )

    detail = _conflict_detail(exc)
    assert detail["code"] == "ALLOCATION_DRAFT_STALE"
    assert detail["expected_row_version"] == 0
    assert detail["current_row_version"] == 1

    # current_draft is the SERVER state, in the same canonical shape the caller sends.
    current = detail["current_draft"]
    assert current is not None
    assert current["enabled"] is True
    server_shares = {
        e["composition_item_id"]: Decimal(e["equity_share_percent"]) for e in current["entries"]
    }
    assert server_shares[items[1]] == Decimal("35")  # not the caller's 50

    # changed_paths names exactly the field in dispute — nothing else.
    assert detail["changed_paths"] == [f"entries[{items[1]}].equity_share_percent"]

    # The envelope's recovery block routes the UI without parsing details.
    assert exc.retryable is False
    assert exc.suggested_action == "reload_and_compare_allocation_draft"
    assert exc.scope_type == "portfolio_allocation_plan"
    assert exc.scope_id is not None


async def test_changed_paths_covers_scalars_capital_and_added_removed_entries(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1, count=2)
    await _put_shared_draft(session, USER1, composition_id, _entries((items[0], "40")))

    # Change a scalar, the capital currency, and drop/add an entry in one submission.
    with pytest.raises(AllocationDraftConflictError) as excinfo:
        await alloc_cmd.upsert_allocation_draft(
            session,
            USER1,
            composition_id=composition_id,
            expected_row_version=0,
            enabled=True,
            initial_capital={"amount": "10000", "currency": "USD"},
            compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
            reserve_cash_percent="25",
            entries=_entries((items[1], "40")),
        )
    await session.rollback()

    paths = set(_conflict_detail(excinfo.value)["changed_paths"])
    assert "reserve_cash_percent" in paths
    assert "initial_capital.currency" in paths
    # An entry present on one side only is reported as a whole disputed entry —
    # keyed by composition_item_id, never by list index.
    assert f"entries[{items[0]}]" in paths
    assert f"entries[{items[1]}]" in paths


async def test_identical_resubmission_conflicts_with_no_disputed_paths(session) -> None:
    """A stale token is still a conflict even when nothing actually differs.

    The compare view then correctly shows an empty diff, and the user can reapply
    with the fresh row_version instead of being told to reconcile phantom changes.
    """
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1, count=1)
    await _put_shared_draft(session, USER1, composition_id, _entries((items[0], "40")))

    exc = await _stale_put(session, composition_id, _entries((items[0], "40")), expected=0)
    assert _conflict_detail(exc)["changed_paths"] == []


async def test_conflict_on_a_composition_with_no_plan_reports_a_null_draft(session) -> None:
    """No plan row exists, so there is no server draft to compare against.

    An empty dict here would be a lie — it reads as "the server has a blank draft".
    """
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1, count=1)

    exc = await _stale_put(session, composition_id, _entries((items[0], "40")), expected=7)
    detail = _conflict_detail(exc)
    assert detail["current_draft"] is None
    assert detail["current_row_version"] == 0
    assert detail["changed_paths"] == []
    assert exc.scope_id is None


async def test_stale_revision_request_reports_the_server_draft_without_a_diff(session) -> None:
    """create_allocation_revision submits no draft body, so there is nothing to diff."""
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1, count=1)
    await _put_shared_draft(
        session,
        USER1,
        composition_id,
        _entries(
            (items[0], "100"),
        ),
    )

    with pytest.raises(AllocationDraftConflictError) as excinfo:
        await alloc_cmd.create_allocation_revision(
            session, USER1, composition_id=composition_id, expected_row_version=99
        )
    await session.rollback()

    detail = _conflict_detail(excinfo.value)
    assert detail["expected_row_version"] == 99
    assert detail["current_row_version"] == 1
    assert detail["current_draft"] is not None
    assert detail["changed_paths"] == []
