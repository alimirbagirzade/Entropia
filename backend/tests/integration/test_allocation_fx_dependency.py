"""S1 — Portfolio FX settlement-currency blocker (doc 13 §5.1, §6.2, §10.1).

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
A composition is seeded with strategy items whose pinned revision resolves to a
canonical instrument carrying a ``settlement_asset``; the allocation validate and
Ready Check paths must BLOCK a shared pool whose Base Currency differs from an
active item's settlement currency when no approved pinned FX conversion dataset
exists. V1 has no such dataset entity (the engine assumes a single-currency pool,
GAP-16), so a resolved mismatch always blocks fail-closed — never a silent convert.

Covers: (1) mismatched settlement currency -> FX_DEPENDENCY_MISSING blocker, the
draft cannot become a revision; (2) matching settlement currency -> no FX blocker,
validate PASSED; (3) unresolved (no-instrument) item -> FX check skipped, never a
fabricated difference; (4) the same blocker surfaces through Ready Check as
ALLOCATION_FX_DEPENDENCY -> NOT_READY.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.instrument.enums import ContractType
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import Principal
from entropia.infrastructure.postgres.repositories import instrument as instrument_repo
from entropia.shared.errors import AllocationHasBlockersError

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_FX_CODE = "FX_DEPENDENCY_MISSING"
_READINESS_FX_CODE = "ALLOCATION_FX_DEPENDENCY"


async def _seed_principals(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_instrument(session, *, symbol: str, settlement: str) -> str:
    """Create a canonical instrument with a settlement currency; return its id."""
    instrument = instrument_repo.create_instrument(
        session,
        resolution_key=f"binance:{symbol.lower()}:perpetual",
        venue_id="binance",
        symbol=symbol,
        contract_type=ContractType.PERPETUAL,
        display_name=f"{symbol} Perpetual",
        settlement_asset=settlement,
        created_by_principal_id="user_1",
    )
    await session.flush()
    return instrument.instrument_id


async def _add_strategy_item(
    session, actor: Actor, workspace_id: str, *, instrument_id: str | None
) -> None:
    """Attach a strategy work object pinning ``data.instrument_id`` (or none)."""
    payload: dict[str, Any] = (
        {"data": {"instrument_id": instrument_id}} if instrument_id else {"note": "no-instrument"}
    )
    work_object = await mb_cmd.create_work_object(
        session, actor, object_kind="strategy", payload=payload
    )
    await mb_cmd.attach_mainboard_item(
        session,
        actor,
        workspace_id=workspace_id,
        root_id=work_object["root_id"],
        revision_id=work_object["revision_id"],
        item_kind="strategy",
    )


async def _upsert_shared(
    session,
    actor: Actor,
    composition_id: str,
    entries: list[dict[str, Any]],
    *,
    expected_row_version: int | None = None,
    base_currency: str = "USDT",
) -> dict[str, Any]:
    result = await alloc_cmd.upsert_allocation_draft(
        session,
        actor,
        composition_id=composition_id,
        expected_row_version=expected_row_version,
        enabled=True,
        initial_capital={"amount": "10000", "currency": base_currency},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent="0",
        entries=entries,
    )
    await session.commit()
    return result


def _entries(*pairs: tuple[str, str]) -> list[dict[str, Any]]:
    return [
        {"composition_item_id": cid, "active": True, "equity_share_percent": share}
        for cid, share in pairs
    ]


async def _seed_two_items(
    session, actor: Actor, *, settlements: tuple[str | None, str | None]
) -> tuple[str, list[str]]:
    mb = await mb_query.get_default_mainboard(session, actor)
    workspace_id = mb["workspace_id"]
    for index, settlement in enumerate(settlements):
        instrument_id = (
            await _seed_instrument(session, symbol=f"S{index}{settlement}", settlement=settlement)
            if settlement is not None
            else None
        )
        await _add_strategy_item(session, actor, workspace_id, instrument_id=instrument_id)
    await session.commit()
    projection = await mb_query.get_default_mainboard(session, actor)
    return workspace_id, [item["item_id"] for item in projection["items"]]


# --------------------------------------------------------------------------- #
# (1) Mismatched settlement currency blocks                                   #
# --------------------------------------------------------------------------- #


async def test_mismatched_settlement_currency_blocks(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _seed_two_items(session, USER1, settlements=("USDT", "EUR"))

    await _upsert_shared(
        session, USER1, composition_id, _entries((items[0], "60"), (items[1], "40"))
    )
    report = await alloc_cmd.validate_allocation_draft(
        session, USER1, composition_id=composition_id
    )
    await session.commit()

    assert report["valid"] is False
    fx = [i for i in report["issues"] if i["code"] == _FX_CODE]
    assert len(fx) == 1
    # Only the EUR item is flagged; the USDT item matches the base and is clean.
    assert fx[0]["composition_item_id"] == items[1]
    assert fx[0]["severity"] == "blocker"
    assert all(
        i["composition_item_id"] != items[0] or i["code"] != _FX_CODE for i in report["issues"]
    )

    # A blocker-carrying draft can never become an immutable plan revision (§8.5).
    # (The draft is at row_version 1 after the single upsert; validate does not bump it.)
    with pytest.raises(AllocationHasBlockersError):
        await alloc_cmd.create_allocation_revision(
            session, USER1, composition_id=composition_id, expected_row_version=1
        )


# --------------------------------------------------------------------------- #
# (2) Matching settlement currency passes                                     #
# --------------------------------------------------------------------------- #


async def test_matching_settlement_currency_passes(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _seed_two_items(session, USER1, settlements=("USDT", "USDT"))

    await _upsert_shared(
        session, USER1, composition_id, _entries((items[0], "60"), (items[1], "40"))
    )
    report = await alloc_cmd.validate_allocation_draft(
        session, USER1, composition_id=composition_id
    )
    await session.commit()

    assert report["valid"] is True
    assert not any(i["code"] == _FX_CODE for i in report["issues"])

    # A clean draft yields an immutable revision.
    revision = await alloc_cmd.create_allocation_revision(
        session, USER1, composition_id=composition_id, expected_row_version=1
    )
    await session.commit()
    assert revision["plan_revision_id"]


# --------------------------------------------------------------------------- #
# (3) Unresolved settlement currency skips the check (no fabricated diff)      #
# --------------------------------------------------------------------------- #


async def test_unresolved_settlement_currency_skips_check(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _seed_two_items(session, USER1, settlements=(None, None))

    await _upsert_shared(
        session, USER1, composition_id, _entries((items[0], "60"), (items[1], "40"))
    )
    report = await alloc_cmd.validate_allocation_draft(
        session, USER1, composition_id=composition_id
    )
    await session.commit()

    assert report["valid"] is True
    assert not any(i["code"] == _FX_CODE for i in report["issues"])


# --------------------------------------------------------------------------- #
# (4) Ready Check surfaces the blocker as ALLOCATION_FX_DEPENDENCY             #
# --------------------------------------------------------------------------- #


async def test_readiness_surfaces_fx_dependency(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _seed_two_items(session, USER1, settlements=("USDT", "EUR"))
    await _upsert_shared(
        session, USER1, composition_id, _entries((items[0], "60"), (items[1], "40"))
    )

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    codes = {i["code"] for i in result["issues"]}
    assert _READINESS_FX_CODE in codes
    assert result["state"] == "not_ready"
