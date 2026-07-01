"""Stage 4a — Portfolio / Equity Allocation against a real database (doc 13).

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
A composition is seeded by reusing the 3a Mainboard commands (create work object
-> attach item), then the allocation draft/validate/revision commands run on it.

Covers: full happy path (autosave draft -> validate READY_WITH_WARNINGS -> immutable
plan revision + config hash + audit/outbox), stale ``expected_row_version`` conflict,
unknown-item DEPENDENCY_BLOCKED, total-share>100 blocks the revision, a soft-deleted
composition item is flagged ITEM_UNAVAILABLE at validation, independent mode is valid
but has no revision, foreign-owner edit 403, and idempotent PUT replay.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.queries import allocation_plan as alloc_query
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    OutboxEvent,
    PortfolioAllocationPlanRevision,
    Principal,
)
from entropia.shared.errors import (
    AccessDeniedError,
    AllocationDependencyBlockedError,
    AllocationDraftConflictError,
    AllocationHasBlockersError,
    AllocationValidationFailedError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_principals(session) -> None:
    for pid in ("user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _composition_with_items(session, actor: Actor, count: int = 3) -> tuple[str, list[str]]:
    """Seed the actor's default composition with ``count`` attached work items."""
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


async def _put_shared_draft(
    session,
    actor: Actor,
    composition_id: str,
    entries: list[dict[str, Any]],
    *,
    expected_row_version: int | None = None,
    reserve: str = "10",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    result = await alloc_cmd.upsert_allocation_draft(
        session,
        actor,
        composition_id=composition_id,
        expected_row_version=expected_row_version,
        enabled=True,
        initial_capital={"amount": "10000", "currency": "USDT"},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent=reserve,
        entries=entries,
        idempotency_key=idempotency_key,
    )
    await session.commit()
    return result


# --------------------------------------------------------------------------- #
# Full happy path                                                             #
# --------------------------------------------------------------------------- #


async def test_full_flow_draft_validate_revision(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1)

    put = await _put_shared_draft(
        session,
        USER1,
        composition_id,
        _entries((items[0], "40"), (items[1], "35"), (items[2], "15")),
    )
    assert put["row_version"] == 1
    assert put["readiness_invalidated"] is True
    assert put["derived"]["reserved_cash"] and Decimal(put["derived"]["reserved_cash"]) == Decimal(
        "1000"
    )

    draft = await alloc_query.get_allocation_draft(session, USER1, composition_id=composition_id)
    assert draft["draft"]["enabled"] is True
    assert len(draft["draft"]["entries"]) == 3
    assert draft["candidate_items"] == []  # all three items represented
    assert draft["row_version"] == 1

    report = await alloc_cmd.validate_allocation_draft(
        session, USER1, composition_id=composition_id
    )
    await session.commit()
    assert report["state"] == "READY_WITH_WARNINGS"
    assert report["valid"] is True
    assert Decimal(report["derived"]["total_allocated"]) == Decimal("8100")
    assert len(report["config_hash"]) == 64

    revision = await alloc_cmd.create_allocation_revision(
        session, USER1, composition_id=composition_id, expected_row_version=1
    )
    await session.commit()
    assert revision["revision_no"] == 1
    assert revision["current_revision_id"] == revision["plan_revision_id"]
    assert revision["row_version"] == 2

    stored = (
        await session.execute(select(func.count()).select_from(PortfolioAllocationPlanRevision))
    ).scalar_one()
    assert stored == 1

    audit = (
        await session.execute(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_kind == "portfolio_allocation.revision_created")
        )
    ).scalar_one()
    outbox = (
        await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "portfolio_allocation.revision_created")
        )
    ).scalar_one()
    assert audit >= 1 and outbox >= 1


# --------------------------------------------------------------------------- #
# Concurrency / dependency / validation                                       #
# --------------------------------------------------------------------------- #


async def test_stale_row_version_conflicts(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1, count=1)
    await _put_shared_draft(session, USER1, composition_id, _entries((items[0], "100")))
    with pytest.raises(AllocationDraftConflictError):
        await _put_shared_draft(
            session, USER1, composition_id, _entries((items[0], "50")), expected_row_version=99
        )


async def test_unknown_item_dependency_blocked(session) -> None:
    await _seed_principals(session)
    composition_id, _ = await _composition_with_items(session, USER1, count=1)
    with pytest.raises(AllocationDependencyBlockedError):
        await _put_shared_draft(session, USER1, composition_id, _entries(("cmbi_not_real", "40")))


async def test_total_over_100_blocks_revision(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1, count=2)
    put = await _put_shared_draft(
        session, USER1, composition_id, _entries((items[0], "70"), (items[1], "45"))
    )
    report = await alloc_cmd.validate_allocation_draft(
        session, USER1, composition_id=composition_id
    )
    await session.commit()
    assert report["valid"] is False
    with pytest.raises(AllocationHasBlockersError):
        await alloc_cmd.create_allocation_revision(
            session, USER1, composition_id=composition_id, expected_row_version=put["row_version"]
        )


async def test_soft_deleted_item_flagged_unavailable(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1, count=2)
    await _put_shared_draft(
        session, USER1, composition_id, _entries((items[0], "50"), (items[1], "50"))
    )
    # Soft-delete the work object behind the first item; its working item detaches.
    projection = await mb_query.get_default_mainboard(session, USER1)
    root_id = next(
        i["work_object_root_id"] for i in projection["items"] if i["item_id"] == items[0]
    )
    await mb_cmd.soft_delete_work_object(session, USER1, root_id=root_id)
    await session.commit()

    report = await alloc_cmd.validate_allocation_draft(
        session, USER1, composition_id=composition_id
    )
    await session.commit()
    codes = {issue["code"] for issue in report["issues"]}
    assert "ITEM_UNAVAILABLE" in codes
    assert report["valid"] is False


async def test_independent_mode_valid_without_revision(session) -> None:
    await _seed_principals(session)
    composition_id, _ = await _composition_with_items(session, USER1, count=1)
    result = await alloc_cmd.upsert_allocation_draft(
        session, USER1, composition_id=composition_id, expected_row_version=None, enabled=False
    )
    await session.commit()
    report = await alloc_cmd.validate_allocation_draft(
        session, USER1, composition_id=composition_id
    )
    await session.commit()
    assert report["state"] == "NOT_SELECTED"
    assert report["valid"] is True
    with pytest.raises(AllocationValidationFailedError):
        await alloc_cmd.create_allocation_revision(
            session,
            USER1,
            composition_id=composition_id,
            expected_row_version=result["row_version"],
        )


async def test_foreign_owner_cannot_edit(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1, count=1)
    with pytest.raises(AccessDeniedError):
        await _put_shared_draft(session, USER2, composition_id, _entries((items[0], "100")))


async def test_idempotent_upsert_replay(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1, count=1)
    first = await _put_shared_draft(
        session, USER1, composition_id, _entries((items[0], "100")), idempotency_key="alloc-key-1"
    )
    second = await _put_shared_draft(
        session, USER1, composition_id, _entries((items[0], "100")), idempotency_key="alloc-key-1"
    )
    assert second["plan_id"] == first["plan_id"]
    assert second["row_version"] == first["row_version"]
    plans = (
        await session.execute(select(func.count()).select_from(PortfolioAllocationPlanRevision))
    ).scalar_one()
    assert plans == 0  # a draft PUT never creates a revision
