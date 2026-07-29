"""S-L4 / doc 14 RC-03 — a readiness WARNING survives into the immutable manifest.

RC-03: "Valid composition with unallocated cash below 100% allocation ->
READY_WITH_WARNINGS; warning retained in report AND later manifest; RUN allowed
after fresh preflight."

The manifest used to carry ``warning_count`` alone. A count cannot name the item or
the field, so a later reader of an archived manifest could not reconstruct what the
run was knowingly admitted despite — the detail was reachable only by dereferencing
the readiness report, a separate row with its own lifetime.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.queries import allocation_plan as alloc_query
from entropia.domain.identity import Actor
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from tests.integration.test_backtest_persistence import (
    USER1,
    _ready_composition,
    _seed_principals,
)

pytestmark = pytest.mark.integration

_UNALLOCATED_CASH = "ALLOCATION_UNALLOCATED_CASH"


async def _enable_partial_allocation(session, actor: Actor, composition_id: str) -> str:
    """Enable shared allocation with 60% of the equity assigned — RC-03's setup.

    Returns the composition_item_id the warning should point at.
    """
    draft = await alloc_query.get_allocation_draft(session, actor, composition_id=composition_id)
    item_id = str(draft["candidate_items"][0]["composition_item_id"])
    await alloc_cmd.upsert_allocation_draft(
        session,
        actor,
        composition_id=composition_id,
        expected_row_version=None,
        enabled=True,
        initial_capital={"amount": "10000", "currency": "USDT"},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent="0",
        entries=[{"composition_item_id": item_id, "active": True, "equity_share_percent": "60"}],
    )
    await session.commit()
    return item_id


def _preflight(manifest: dict[str, Any]) -> dict[str, Any]:
    return dict(manifest["preflight"])


async def test_rc03_warning_is_retained_in_the_manifest_not_only_counted(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    await _enable_partial_allocation(session, USER1, composition_id)

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    # RC-03: the run IS admitted — a warning never blocks.
    assert admit["state"] == "queued"
    assert admit["warning_count"] >= 1

    stored = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert stored is not None
    preflight = _preflight(stored.manifest)
    assert preflight["state"] == "ready_with_warnings"
    assert preflight["warning_count"] == len(preflight["warnings"])

    codes = [w["code"] for w in preflight["warnings"]]
    assert _UNALLOCATED_CASH in codes

    row = next(w for w in preflight["warnings"] if w["code"] == _UNALLOCATED_CASH)
    # The four fields RC-03 needs to be actionable from the manifest alone.
    assert set(row) == {"code", "scope", "scope_id", "field_path", "message"}
    assert row["scope"] == "portfolio_allocation"
    assert row["message"]


async def test_a_clean_composition_pins_an_empty_warning_list(session) -> None:
    """No warnings -> an explicit empty list, never a missing key.

    A reader must be able to distinguish "this run had no warnings" from "this
    manifest predates the field", so the key is always present.
    """
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    stored = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert stored is not None
    preflight = _preflight(stored.manifest)
    assert preflight["state"] == "ready"
    assert preflight["warning_count"] == 0
    assert preflight["warnings"] == []
