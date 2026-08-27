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
from entropia.domain.allocation.enums import CrossItemConflictPolicy
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    OutboxEvent,
    PortfolioAllocationPlan,
    PortfolioAllocationPlanRevision,
    Principal,
)
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.shared.errors import (
    AccessDeniedError,
    AllocationDependencyBlockedError,
    AllocationDraftConflictError,
    AllocationHasBlockersError,
    AllocationValidationFailedError,
    CrossItemConflictPolicyNotSelectableError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

# ADIM 3: every ENABLED plan now leads with the shared-capital containment blocker
# (domain/allocation/capability.py) — shared capital does not execute in this build.
_CONTAINMENT_CODE = "SHARED_MODE_NOT_IN_BUILD"
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
    # ADIM 3 containment: an ENABLED plan is NOT_READY and never `valid` — shared
    # capital does not execute in this build. The draft round-trip, the derived
    # sleeve maths and the config hash are unaffected: the plan stays authorable and
    # previewable; only the freeze and the RUN are refused.
    assert report["state"] == "NOT_READY"
    assert report["valid"] is False
    assert {i["code"] for i in report["issues"] if i["severity"] == "blocker"} == {
        _CONTAINMENT_CODE
    }
    assert Decimal(report["derived"]["total_allocated"]) == Decimal("8100")
    assert len(report["config_hash"]) == 64

    # The immutable revision is refused: freezing a plan that cannot run would pin a
    # configuration no RUN could ever honour.
    with pytest.raises(AllocationHasBlockersError):
        await alloc_cmd.create_allocation_revision(
            session, USER1, composition_id=composition_id, expected_row_version=1
        )
    await session.rollback()

    stored = (
        await session.execute(select(func.count()).select_from(PortfolioAllocationPlanRevision))
    ).scalar_one()
    assert stored == 0

    # ... and nothing was announced: a refused freeze emits no revision audit/outbox.
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
    assert audit == 0 and outbox == 0


async def test_projection_carries_item_display_label(session) -> None:
    """P-11 / F-07: the candidate picker AND the persisted entry projection expose
    the composition item's server-owned display label, so the browser never
    reconstructs a human name from the raw ``mbi_`` id. An item with no override
    resolves to ``None`` → the client falls back to the item-kind label.
    """
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1)

    # Give the first item an explicit human label (the Mainboard set-label path);
    # the others keep the default None.
    labelled = await mb_repo.get_item(session, items[0])
    assert labelled is not None
    labelled.display_label_override = "Momentum Alpha"
    await session.commit()

    # Before any plan row exists: the candidate picker carries the label.
    draft = await alloc_query.get_allocation_draft(session, USER1, composition_id=composition_id)
    candidates = {c["composition_item_id"]: c for c in draft["candidate_items"]}
    assert candidates[items[0]]["display_label_override"] == "Momentum Alpha"
    assert candidates[items[1]]["display_label_override"] is None

    # After a shared draft: the persisted entry projection resolves the label from
    # the bound composition item (the entry row stores no name of its own).
    await _put_shared_draft(
        session, USER1, composition_id, _entries((items[0], "40"), (items[1], "35"))
    )
    draft2 = await alloc_query.get_allocation_draft(session, USER1, composition_id=composition_id)
    entries = {e["composition_item_id"]: e for e in draft2["draft"]["entries"]}
    assert entries[items[0]]["display_label_override"] == "Momentum Alpha"
    assert entries[items[1]]["display_label_override"] is None


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


# --------------------------------------------------------------------------- #
# Portfolio-level rules (cross-item, doc 13 §8.4)                              #
# --------------------------------------------------------------------------- #


async def test_portfolio_rules_round_trip_and_revision_carry(session) -> None:
    """PUT persists the two rule fields; the draft GET, the immutable revision config
    and the blocker path all reflect them.

    This used to drive the policy field with ``"net"``. B0 (signed 2026-08-27) froze that
    write path, so the field is now driven with ``"block_opposite"`` -- the claim under
    test is that the TWO RULE FIELDS round-trip, and that claim never depended on which
    policy token was used. The lowercase input is kept deliberately: the normalisation
    axis (``_norm_conflict``) is part of what this test covers. NET's own behaviour moved
    to ``test_b0_freezes_the_net_write_path``.
    """
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1)

    put = await alloc_cmd.upsert_allocation_draft(
        session,
        USER1,
        composition_id=composition_id,
        expected_row_version=None,
        enabled=True,
        initial_capital={"amount": "10000", "currency": "USDT"},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent="10",
        max_total_exposure_percent="150",
        conflict_policy="block_opposite",
        entries=_entries((items[0], "40"), (items[1], "35"), (items[2], "15")),
    )
    await session.commit()
    # A supported policy raises no policy issue at all.
    codes = {i["code"] for i in put["inline_issues"]}
    assert "CONFLICT_POLICY_NET_V1" not in codes
    # ADIM 3 containment: the draft still SAVES (authoring is preserved) and the only
    # blocker among the inline issues is the shared-mode containment.
    assert {i["code"] for i in put["inline_issues"] if i["severity"] == "blocker"} == {
        _CONTAINMENT_CODE
    }

    draft = await alloc_query.get_allocation_draft(session, USER1, composition_id=composition_id)
    assert draft["draft"]["max_total_exposure_percent"] == "150.000000"
    assert draft["draft"]["conflict_policy"] == "BLOCK_OPPOSITE"

    # ADIM 3 containment: the rules still round-trip through the DRAFT (asserted
    # above), but they can no longer be frozen into an immutable revision — shared
    # capital does not execute in this build, so pinning a plan revision would pin a
    # configuration no RUN could honour. The freeze is refused with the containment
    # as its only blocker, and no revision row is written.
    with pytest.raises(AllocationHasBlockersError) as exc_info:
        await alloc_cmd.create_allocation_revision(
            session, USER1, composition_id=composition_id, expected_row_version=1
        )
    await session.rollback()
    assert {d["code"] for d in exc_info.value.details} == {_CONTAINMENT_CODE}
    assert (await session.execute(select(PortfolioAllocationPlanRevision))).first() is None


async def test_nonpositive_max_total_exposure_blocks_the_revision(session) -> None:
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1)

    put = await alloc_cmd.upsert_allocation_draft(
        session,
        USER1,
        composition_id=composition_id,
        expected_row_version=None,
        enabled=True,
        initial_capital={"amount": "10000", "currency": "USDT"},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent="10",
        max_total_exposure_percent="0",
        entries=_entries((items[0], "100")),
    )
    await session.commit()
    assert "MAX_TOTAL_EXPOSURE_INVALID" in {i["code"] for i in put["inline_issues"]}

    with pytest.raises(AllocationHasBlockersError):
        await alloc_cmd.create_allocation_revision(
            session, USER1, composition_id=composition_id, expected_row_version=1
        )


# --------------------------------------------------------------------------- #
# B0 — the NET write path is frozen (G14 / GH #544, signed 2026-08-27)         #
# --------------------------------------------------------------------------- #


async def test_b0_freezes_the_net_write_path(session) -> None:
    """A submitted NET token is refused BEFORE anything is written.

    ``pytest.raises`` alone would not close this clause: moving the guard below the
    mutation raises the very same exception while leaving the row behind (the ADIM 94
    lesson). So the plan table is READ BACK, and the read happens without a rollback --
    a rollback would discard a row a below-the-mutation guard had written and the test
    would pass vacuously.
    """
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1)

    for token in ("NET", "net", "  Net  "):
        with pytest.raises(CrossItemConflictPolicyNotSelectableError) as exc_info:
            await alloc_cmd.upsert_allocation_draft(
                session,
                USER1,
                composition_id=composition_id,
                expected_row_version=None,
                enabled=True,
                initial_capital={"amount": "10000", "currency": "USDT"},
                compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
                reserve_cash_percent="10",
                conflict_policy=token,
                entries=_entries((items[0], "40")),
            )
        # No rollback: the assertion below must see whatever the command actually left.
        assert (await session.execute(select(PortfolioAllocationPlan))).first() is None, token

    # The envelope carries the recovery fields the page needs (O-02), not just a code.
    err = exc_info.value
    assert err.code == "CROSS_ITEM_CONFLICT_POLICY_NOT_SELECTABLE"
    assert err.field_path == "conflict_policy"
    assert err.suggested_action == "choose_supported_conflict_policy"
    assert err.details[0]["supported"] == ["KEEP_SEPARATE", "BLOCK_OPPOSITE"]

    # Positive control: the SAME call with a supported token writes exactly one row, so
    # the refusal above is attributable to the token and not to a broken fixture.
    await _put_shared_draft(session, USER1, composition_id, _entries((items[0], "40")))
    plan_count = await session.scalar(select(func.count()).select_from(PortfolioAllocationPlan))
    assert plan_count == 1


async def test_a_stored_net_plan_still_reads_back_verbatim(session) -> None:
    """B0 freezes WRITES; it must not touch reads.

    A plan saved before B0 still carries ``'NET'``. The value is not rewritten, not
    nulled and not downgraded -- B1 and B2 were both considered and rejected. This is
    also the guard against the placement trap: putting the refusal in the shared Pydantic
    model would have turned this read into a 500, because ``_plan_to_config`` re-validates
    STORED rows through that same model.
    """
    await _seed_principals(session)
    composition_id, items = await _composition_with_items(session, USER1)
    await _put_shared_draft(session, USER1, composition_id, _entries((items[0], "40")))

    # Simulate a row written before B0: the command path can no longer produce one.
    plan = (await session.execute(select(PortfolioAllocationPlan))).scalar_one()
    plan.conflict_policy = CrossItemConflictPolicy.NET
    await session.commit()
    session.expire_all()

    draft = await alloc_query.get_allocation_draft(session, USER1, composition_id=composition_id)
    assert draft["draft"]["conflict_policy"] == "NET"

    # Validation reads the stored row back through ``_plan_to_config`` -- the exact path
    # that a refusal in the shared Pydantic model would have turned into a 500. It must
    # succeed, and the NET issue must now be a BLOCKER: that is the drainage signal B3
    # needs, since it is how the operator finds the rows that would halt the migration.
    #
    # ``state``/``valid`` are NOT asserted here: an enabled plan already carries the
    # containment blocker, so both are pinned by containment whatever NET's severity is.
    # The severity of the NET issue itself is the only distinguishing axis.
    report = await alloc_cmd.validate_allocation_draft(
        session, USER1, composition_id=composition_id
    )
    net = [i for i in report["issues"] if i["code"] == "CONFLICT_POLICY_NET_V1"]
    assert len(net) == 1
    assert net[0]["severity"] == "blocker"
    assert net[0] not in report["warnings"]
