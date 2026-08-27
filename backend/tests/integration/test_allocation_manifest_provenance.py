"""A16 end-to-end: admission RESOLVES the sleeve amounts and FX refs, and pins them.

``tests/unit/test_a16_manifest_policy_parity.py`` pins the CONTRACT — that a manifest built
over a ``capital_execution`` carrying these groups exposes them. It cannot prove the
admission path actually fills them in, because it hands the builder a literal dict. This
module closes that half against a real Postgres.

The gap it guards is specific and was real until `C7`: ``_resolve_allocation`` already
computed both groups — ``validate_allocation`` returns the derived amounts, and
``resolve_settlement_currencies`` returns the per-item currencies — and then DISCARDED
them into ``_derived`` and an unused local. The snapshot recorded only the plan pointer and
the config, so ADR §10.1's *"resolved sleeve amounts, currency/FX refs"* were absent from
every Result.

The numbers are ADR 0002 §14 A12's canonical fixture (doc 13 §14 test 10) on purpose:
``R0=1000``, ``A0=9000``, sleeves ``3600/3150/1350``, ``U0=900``. Asserting the exact
resolved money — rather than "a number is present" — is what makes this a provenance test
and not a smoke test: a builder that echoed the share PERCENT, or that recomputed sleeves
from a live draft, produces a different set of strings here.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import MainboardCompositionSnapshot, Principal

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_principals(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _composition_with_items(session, count: int) -> tuple[str, list[str]]:
    mb = await mb_query.get_default_mainboard(session, USER1)
    workspace_id = mb["workspace_id"]
    for index in range(count):
        work_object = await mb_cmd.create_work_object(
            session, USER1, object_kind="strategy", payload={"note": f"a16-{index}"}
        )
        await mb_cmd.attach_mainboard_item(
            session,
            USER1,
            workspace_id=workspace_id,
            root_id=work_object["root_id"],
            revision_id=work_object["revision_id"],
            item_kind="strategy",
        )
    await session.commit()
    projection = await mb_query.get_default_mainboard(session, USER1)
    return workspace_id, [item["item_id"] for item in projection["items"]]


async def _put_draft(session, composition_id: str, shares: list[tuple[str, str]], *, enabled: bool):
    await alloc_cmd.upsert_allocation_draft(
        session,
        USER1,
        composition_id=composition_id,
        expected_row_version=None,
        enabled=enabled,
        initial_capital={"amount": "10000", "currency": "USDT"},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent="10",
        entries=[
            {"composition_item_id": cid, "active": True, "equity_share_percent": share}
            for cid, share in shares
        ],
    )
    await session.commit()


async def _capital_mode(session, composition_id: str) -> dict[str, Any]:
    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()
    snapshot = (
        await session.execute(
            select(MainboardCompositionSnapshot).where(
                MainboardCompositionSnapshot.snapshot_id == result["snapshot_id"]
            )
        )
    ).scalar_one()
    assert snapshot.capital_mode_snapshot is not None
    return snapshot.capital_mode_snapshot


async def test_admission_pins_the_resolved_sleeve_amounts(session) -> None:
    """The A12 fixture, resolved and recorded — not the share percent echoed back."""
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, 3)
    await _put_draft(
        session,
        composition_id,
        [(items[0], "40"), (items[1], "35"), (items[2], "15")],
        enabled=True,
    )

    derived = (await _capital_mode(session, composition_id))["derived_amounts"]
    assert derived is not None, "A16's resolved amounts were discarded again"

    # The portfolio arithmetic (ADR §14 A12).
    assert derived["portfolio_initial_capital"] == "10000.00"
    assert derived["reserved_cash"] == "1000.00"
    assert derived["capital_available"] == "9000.00"
    assert derived["total_allocated"] == "8100.00"
    assert derived["unallocated"] == "900.00"

    # The per-sleeve RESOLVED money. Keyed by item so a reordering cannot pass by luck,
    # and compared as an exact mapping so a missing sleeve is as red as a wrong one.
    assert {s["composition_item_id"]: s["initial_sleeve_capital"] for s in derived["sleeves"]} == {
        items[0]: "3600.00",
        items[1]: "3150.00",
        items[2]: "1350.00",
    }
    # The share percent was ALREADY pinned inside ``config``; what A16 adds is the money
    # above. Both are present, and they are not the same number in the same units — the
    # percent carries SHARE quantisation (6 dp) while the sleeve carries MONEY quantisation
    # (2 dp), which is why echoing the percent could never have satisfied §10.1. The
    # literals here were corrected from a guess by running this test.
    assert {s["composition_item_id"]: s["equity_share_percent"] for s in derived["sleeves"]} == {
        items[0]: "40.000000",
        items[1]: "35.000000",
        items[2]: "15.000000",
    }


async def test_admission_pins_an_fx_ref_for_every_allocated_entry(session) -> None:
    """One key per entry, present even when the currency cannot be resolved.

    A null here means *unresolvable*, which is a different fact from *absent* — these
    seeded Strategy items carry no instrument, so null is the correct value and the KEY
    SET is what carries the claim. Dropping unresolvable items instead would make a
    partially-resolvable plan indistinguishable from a fully-resolved one.
    """
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, 2)
    await _put_draft(session, composition_id, [(items[0], "60"), (items[1], "40")], enabled=True)

    fx = (await _capital_mode(session, composition_id))["settlement_currencies"]
    assert fx is not None, "A16's currency refs were discarded again"
    assert set(fx) == {items[0], items[1]}


async def test_independent_mode_pins_no_allocation_provenance(session) -> None:
    """Independent mode has no shared pool, so both groups are null — not empty.

    ``validate_allocation`` returns no derived amounts for a disabled plan (§4, §14#2), and
    fabricating ``{}`` / ``[]`` here would advertise a resolved-but-empty allocation. The
    absence is the honest record.
    """
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, 2)
    await _put_draft(session, composition_id, [(items[0], "60"), (items[1], "40")], enabled=False)

    capital_mode = await _capital_mode(session, composition_id)
    assert capital_mode["enabled"] is False
    assert capital_mode["derived_amounts"] is None
    assert capital_mode["settlement_currencies"] is None
