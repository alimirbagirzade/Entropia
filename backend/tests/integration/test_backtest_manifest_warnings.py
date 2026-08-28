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
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.queries import allocation_plan as alloc_query
from entropia.domain.allocation import capability
from entropia.domain.identity import Actor
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.shared.errors import ReadinessBlockedError
from tests.integration.test_backtest_persistence import (
    USER1,
    _ready_composition,
    _seed_principals,
)

pytestmark = pytest.mark.integration

_UNALLOCATED_CASH = "ALLOCATION_UNALLOCATED_CASH"
_EXECUTION_ASSUMPTIONS = "EXECUTION_ASSUMPTIONS_DEFAULT"
# ADIM 3: shared capital is fail-closed at admission.
_SHARED_MODE_BLOCKER = "ALLOCATION_SHARED_MODE_NOT_IN_BUILD"


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
    """RC-03 over a STRATEGY-scoped warning.

    ADIM 3 changed which warning this can use. RC-03's original fixture was
    "unallocated cash below 100% allocation" — a shared-capital plan, which is now
    fail-closed at admission (shared capital does not execute in this build), so it
    can no longer produce an ADMITTED run to inspect. RC-03's subject is unchanged:
    a warning must survive into the immutable manifest as a full row, not a count.
    A strategy with no commission/spread assumptions raises
    ``EXECUTION_ASSUMPTIONS_DEFAULT`` (doc 14 §9.2) — still a warning, still on a
    still-admissible composition.
    """
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1, costs={})

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
    assert _EXECUTION_ASSUMPTIONS in codes

    row = next(w for w in preflight["warnings"] if w["code"] == _EXECUTION_ASSUMPTIONS)
    # The four fields RC-03 needs to be actionable from the manifest alone.
    assert set(row) == {"code", "scope", "scope_id", "field_path", "message"}
    assert row["scope"] == "strategy"
    assert row["field_path"] == "data.costs"
    assert row["scope_id"]
    assert row["message"]


async def test_shared_allocation_warning_path_is_now_fail_closed(session, monkeypatch) -> None:
    """The allocation warning RC-03 used to ride on is unreachable by design.

    ``ALLOCATION_UNALLOCATED_CASH`` is a WARNING, but it can only exist on an
    ENABLED shared plan — and an enabled plan now leads with a BLOCKER, so the
    composition is NOT_READY and no run is admitted. Pinned here so removing the
    containment restores a CHECKED behaviour rather than a forgotten one.
    """
    # CONTAINED WORLD, forced since ADIM 20 (`C9`). This case characterizes the
    # containment blanket, which the lift removed as the shipped default but did not
    # delete: `future_dev` is still a legal status and still behaves exactly this way.
    monkeypatch.setattr(capability, "SHARED_ALLOCATION_STATUS", "future_dev")
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    await _enable_partial_allocation(session, USER1, composition_id)

    report = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    assert report["state"] == "not_ready"
    by_code = {i["code"]: i for i in report["issues"]}
    assert by_code[_SHARED_MODE_BLOCKER]["severity"] == "blocker"
    # The unallocated-cash finding is still computed and still only a warning — the
    # containment ADDS a blocker, it does not re-classify anything else.
    assert by_code[_UNALLOCATED_CASH]["severity"] == "warning"

    with pytest.raises(ReadinessBlockedError):
        await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.rollback()


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
