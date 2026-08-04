"""R-1 — the Composition Snapshot must pin the config of the revision it NAMES.

doc 13 §1.2 fixes the chain ``draft -> plan revision -> composition snapshot ->
run manifest``; §8.5 says the snapshot pins the *exact* allocation plan revision
and §11.1 states the draft "direct engine input degildir". Master Ref Modul 11
(``... sonuc manifest'te exact allocation plan revision/snapshot olarak
saklanir``) says the same. So in shared mode the snapshot's ``config`` /
``config_hash`` must be the frozen revision's, never a config recomputed from the
live draft and merely LABELLED with the revision id.

Containment note: ``create_allocation_revision`` cannot run while
``SHARED_ALLOCATION_STATUS = "future_dev"`` (an enabled plan always carries the
containment BLOCKER), so the frozen revision here is seeded through the same
repository call the production command uses. That is the persisted state a
pre-containment build could already have written, and the state every shared plan
will have once containment lifts.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.domain.allocation.rules import canonical_config, compute_config_hash
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    MainboardCompositionSnapshot,
    Principal,
)
from entropia.infrastructure.postgres.repositories import allocation as alloc_repo

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_principals(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _composition_with_items(session, actor: Actor, count: int = 2) -> tuple[str, list[str]]:
    mb = await mb_query.get_default_mainboard(session, actor)
    workspace_id = mb["workspace_id"]
    for index in range(count):
        work_object = await mb_cmd.create_work_object(
            session, actor, object_kind="strategy", payload={"note": f"seed-{index}"}
        )
        await mb_cmd.attach_mainboard_item(
            session,
            actor,
            workspace_id=workspace_id,
            root_id=work_object["root_id"],
            revision_id=work_object["revision_id"],
            item_kind="strategy",
        )
    await session.commit()
    projection = await mb_query.get_default_mainboard(session, actor)
    return workspace_id, [item["item_id"] for item in projection["items"]]


def _entries(*pairs: tuple[str, str]) -> list[dict[str, Any]]:
    return [
        {"composition_item_id": cid, "active": True, "equity_share_percent": share}
        for cid, share in pairs
    ]


async def _put_draft(
    session,
    composition_id: str,
    entries: list[dict[str, Any]],
    *,
    expected_row_version: int | None,
    enabled: bool = True,
) -> dict[str, Any]:
    result = await alloc_cmd.upsert_allocation_draft(
        session,
        USER1,
        composition_id=composition_id,
        expected_row_version=expected_row_version,
        enabled=enabled,
        initial_capital={"amount": "10000", "currency": "USDT"},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent="10",
        entries=entries,
    )
    await session.commit()
    return result


async def _freeze_revision(session, composition_id: str) -> Any:
    """Freeze the current draft exactly as ``create_allocation_revision`` would.

    The command itself is refused by the ADIM 3 containment blocker, so the same
    repository write is issued directly; nothing else about the row differs.
    """
    plan = await alloc_repo.get_plan_for_workspace(session, composition_id)
    assert plan is not None
    entries = await alloc_repo.list_entries(session, plan.plan_id)
    config = alloc_cmd._plan_to_config(plan, entries)
    revision = await alloc_repo.create_revision(
        session,
        plan_id=plan.plan_id,
        revision_no=await alloc_repo.max_revision_no(session, plan.plan_id) + 1,
        config=canonical_config(config),
        config_hash=compute_config_hash(config),
        derived_amounts=None,
        source_draft_row_version=plan.row_version,
        created_by_principal_id=USER1.principal_id,
    )
    plan.current_revision_id = revision.plan_revision_id
    plan.row_version += 1
    await session.commit()
    return revision


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


async def test_snapshot_pins_the_named_revision_not_the_diverged_draft(session) -> None:
    """R-1: naming a revision and pinning the live draft's config is the defect."""
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1)

    await _put_draft(
        session,
        composition_id,
        _entries((items[0], "40"), (items[1], "35")),
        expected_row_version=None,
    )
    revision = await _freeze_revision(session, composition_id)

    # The draft is re-cut and NO new revision is frozen: the plan's head pointer
    # still names the revision above while the draft rows no longer match it.
    await _put_draft(
        session,
        composition_id,
        _entries((items[0], "10"), (items[1], "5")),
        expected_row_version=2,
    )

    capital = await _capital_mode(session, composition_id)

    assert capital["plan_revision_id"] == revision.plan_revision_id
    # The snapshot must carry what that revision froze, byte for byte.
    assert capital["config"] == revision.config
    assert capital["config_hash"] == revision.config_hash
    # ... and the test is not vacuous: the live draft really did diverge.
    plan = await alloc_repo.get_plan_for_workspace(session, composition_id)
    assert plan is not None
    entries = await alloc_repo.list_entries(session, plan.plan_id)
    live = canonical_config(alloc_cmd._plan_to_config(plan, entries))
    assert live != revision.config


async def test_snapshot_falls_back_to_the_draft_when_no_revision_is_frozen(session) -> None:
    """No revision named -> no revision claimed: config and pointer stay consistent."""
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1)
    await _put_draft(
        session,
        composition_id,
        _entries((items[0], "40"), (items[1], "35")),
        expected_row_version=None,
    )

    capital = await _capital_mode(session, composition_id)

    plan = await alloc_repo.get_plan_for_workspace(session, composition_id)
    assert plan is not None
    entries = await alloc_repo.list_entries(session, plan.plan_id)
    live = alloc_cmd._plan_to_config(plan, entries)
    assert capital["plan_revision_id"] is None
    assert capital["config"] == canonical_config(live)
    assert capital["config_hash"] == compute_config_hash(live)


async def test_toggling_off_keeps_independent_mode_despite_a_frozen_revision(session) -> None:
    """The MODE is the live plan's (doc 13 §10.1); a stale revision cannot re-enable it."""
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1)
    await _put_draft(
        session,
        composition_id,
        _entries((items[0], "40"), (items[1], "35")),
        expected_row_version=None,
    )
    await _freeze_revision(session, composition_id)
    await _put_draft(session, composition_id, [], expected_row_version=2, enabled=False)

    capital = await _capital_mode(session, composition_id)

    assert capital["enabled"] is False
    assert capital["config"] is None
    assert capital["config_hash"] is None
