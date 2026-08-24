"""Stage 4b — Backtest Ready Check against a real database (doc 14 §9, §15).

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
A composition is seeded by reusing the 3a Mainboard commands, then the readiness
command/query run on it. Covers: RC-01 empty -> NOT_READY (immutable report +
snapshot.readiness_report_id filled), RC-02 valid strategy -> READY, RC-09
expected_fingerprint mismatch -> 409, RC-18 rerun = new immutable report id, the
STALE recompute after a composition change, foreign-owner 403 (RC-17), and the L1
FK insert order (report row precedes its issue children on real Postgres).
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import readiness_check as readiness_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.readiness.enums import ReadinessState
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    MainboardCompositionSnapshot,
    MarketDatasetRevision,
    Principal,
    ReadinessIssueRow,
    ReadyCheckReport,
)
from entropia.infrastructure.postgres.models.audit import OutboxEvent
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import (
    AccessDeniedError,
    CompositionStaleError,
    ReadinessReportNotFoundError,
    UnauthenticatedError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_principals(session) -> None:
    for pid in ("user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_market_revision(session, state: MarketRevisionState) -> None:
    root = await session.get(EntityRegistry, "md_root_1")
    if root is None:
        root = EntityRegistry(
            entity_id="md_root_1",
            entity_type="market_dataset",
            owner_principal_id="user_1",
            created_by_principal_id="user_1",
            lifecycle_state="active",
            current_revision_id=None,
        )
        session.add(root)
        await session.flush()
        session.add(
            MarketDatasetRevision(
                revision_id="md_rev_1",
                entity_id=root.entity_id,
                revision_no=1,
                market_data_type=MarketDataType.OHLCV,
                revision_state=state,
                payload={},
                content_hash="a" * 64,
                created_by_principal_id="user_1",
            )
        )
        root.current_revision_id = "md_rev_1"
    else:
        revision = await session.get(MarketDatasetRevision, "md_rev_1")
        assert revision is not None
        revision.revision_state = state
    await session.flush()


def _strategy_payload(indicator_revision_id: str = "pkg_rev_1") -> dict[str, Any]:
    return {
        "strategy_root_id": "strat_root_seed",
        "display_name": "Seed strategy",
        "rationale_family_id": "rf_1",
        "data": {
            "instrument_id": "BTCUSDT",
            "market_dataset_root_id": "md_root_1",
            "market_dataset_revision_id": "md_rev_1",
            "market_dataset_content_hash": "a" * 64,
            "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-06-01T00:00:00Z"},
            "initial_capital": "10000.00",
            "execution": {"entry_timing": "next_candle_open", "exit_timing": "next_candle_open"},
            "order_config": {"type": "market_order"},
            "costs": {"commission": "0.04", "spread": "0.01", "slippage_value": "0.1"},
            "intrabar_policy": {"tick_policy": "inherit"},
            "funding": {"enabled": False},
        },
        "position_entry_logic": {
            "signal_block": {"rule": "required_indicator_blocks_only"},
            "indicator_blocks": [
                {
                    "block_id": "ib_1",
                    "display_order": 0,
                    "package_ref": {
                        "package_root_id": "pkg_root_1",
                        "package_revision_id": indicator_revision_id,
                        "package_content_hash": "b" * 64,
                    },
                    "trigger_source": "indicator_native_trigger",
                    "requirement": "required",
                }
            ],
        },
        "position_exit_logic": {},
        "protection_stop_logic": {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}},
        # GH #550: ``size_semantics`` marks this revision as saved AFTER sizing became a
        # percent of resolved capital. Without it Ready Check raises the
        # STRATEGY_SIZING_SEMANTICS_UNCONFIRMED transition blocker and this fixture stops
        # being a fixture for whatever it is about.
        "position_sizing": {
            "method": "base_position_size",
            "base_position_size": "1.0",
            "size_semantics": "percent_of_capital",
        },
        "restrictions_filters": {},
        "conflict_position_handling": {},
    }


async def _empty_composition(session, actor: Actor) -> str:
    mb = await mb_query.get_default_mainboard(session, actor)
    await session.commit()
    return mb["workspace_id"]


async def _composition_with_strategy(session, actor: Actor) -> str:
    await _seed_market_revision(session, MarketRevisionState.APPROVED)
    workspace_id = await _empty_composition(session, actor)
    # F-06: the pinned indicator must resolve to a computable signal, else the upfront
    # Ready Check gate blocks it (STRATEGY_INDICATOR_UNRESOLVED). Seed a real approved
    # package whose dependency snapshot yields the directional key ta.sma.
    _reg, _pkg_root, pkg_rev = await pkg_repo.create_package(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        package_kind=PackageKind.INDICATOR,
        input_contract={"source": "close"},
        output_contract={"kind": "directional_signal"},
        dependency_snapshot={"resolved": [{"call": "ta.sma", "canonical_key": "ta.sma"}]},
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.flush()
    work_object = await mb_cmd.create_work_object(
        session,
        actor,
        object_kind="strategy",
        payload=_strategy_payload(indicator_revision_id=pkg_rev.revision_id),
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
    return workspace_id


# --------------------------------------------------------------------------- #
# RC-01: empty composition                                                    #
# --------------------------------------------------------------------------- #


async def test_rc01_empty_composition_persists_not_ready_report(session) -> None:
    await _seed_principals(session)
    composition_id = await _empty_composition(session, USER1)

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    assert result["state"] == "not_ready"
    assert any(i["code"] == "COMPOSITION_EMPTY" for i in result["issues"])

    report = await session.get(ReadyCheckReport, result["report_id"])
    assert report is not None and str(report.state) == "not_ready"
    # RC: snapshot.readiness_report_id slot (null in 3a) is now filled.
    snapshot = await session.get(MainboardCompositionSnapshot, result["snapshot_id"])
    assert snapshot is not None
    assert snapshot.readiness_report_id == result["report_id"]
    assert str(snapshot.readiness_state) == "not_ready"

    # L1: at least one issue child persisted under the report (FK satisfied).
    issue_count = (
        await session.execute(
            select(func.count())
            .select_from(ReadinessIssueRow)
            .where(ReadinessIssueRow.report_id == result["report_id"])
        )
    ).scalar_one()
    assert issue_count >= 1


# --------------------------------------------------------------------------- #
# RC-02: valid strategy -> READY                                              #
# --------------------------------------------------------------------------- #


async def test_rc02_valid_strategy_is_ready(session) -> None:
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    assert result["state"] == "ready"
    assert result["issues"] == []
    assert result["summary"]["blocker_count"] == 0

    # A report_created outbox event is published for downstream projections.
    published = (
        await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "readiness.report_created")
        )
    ).scalar_one()
    assert published >= 1


async def test_unapproved_market_dataset_blocks_then_approved_passes(session) -> None:
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)
    await _seed_market_revision(session, MarketRevisionState.NEEDS_REVIEW)

    blocked = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert blocked["state"] == "not_ready"
    assert any(i["code"] == "MARKET_DATASET_NOT_APPROVED" for i in blocked["issues"])

    await _seed_market_revision(session, MarketRevisionState.APPROVED)
    approved = await readiness_cmd.run_readiness_check(
        session, USER1, composition_id=composition_id
    )
    assert approved["state"] == "ready"
    assert approved["issues"] == []


# --------------------------------------------------------------------------- #
# RC-09: expected_fingerprint mismatch -> 409                                 #
# --------------------------------------------------------------------------- #


async def test_rc09_expected_fingerprint_mismatch_conflicts(session) -> None:
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)

    with pytest.raises(CompositionStaleError):
        await readiness_cmd.run_readiness_check(
            session, USER1, composition_id=composition_id, expected_fingerprint="stale_hash"
        )


async def test_matching_expected_fingerprint_succeeds(session) -> None:
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)

    first = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()
    fingerprint = first["composition_fingerprint"]

    ok = await readiness_cmd.run_readiness_check(
        session, USER1, composition_id=composition_id, expected_fingerprint=fingerprint
    )
    await session.commit()
    assert ok["state"] == "ready"


# --------------------------------------------------------------------------- #
# RC-18: rerun = new immutable report id                                       #
# --------------------------------------------------------------------------- #


async def test_rc18_rerun_creates_new_report_id(session) -> None:
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)

    first = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()
    second = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    assert first["report_id"] != second["report_id"]
    # The older report remains retrievable (immutable, historical).
    older = await session.get(ReadyCheckReport, first["report_id"])
    assert older is not None


# --------------------------------------------------------------------------- #
# STALE recompute after a composition change                                   #
# --------------------------------------------------------------------------- #


async def test_report_becomes_stale_after_composition_change(session) -> None:
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)

    checked = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()
    report_id = checked["report_id"]

    # Add another enabled item -> composition fingerprint changes -> report STALE.
    extra = await mb_cmd.create_work_object(
        session, USER1, object_kind="strategy", payload=_strategy_payload()
    )
    await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=composition_id,
        root_id=extra["root_id"],
        revision_id=extra["revision_id"],
        item_kind="strategy",
    )
    await session.commit()

    view = await readiness_query.get_readiness_report(session, USER1, report_id=report_id)
    assert view["state"] == "stale"
    assert view["is_current"] is False


# --------------------------------------------------------------------------- #
# RC-17: foreign owner cannot check a private composition                       #
# --------------------------------------------------------------------------- #


async def test_rc17_foreign_owner_denied(session) -> None:
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)

    with pytest.raises(AccessDeniedError):
        await readiness_cmd.run_readiness_check(session, USER2, composition_id=composition_id)


async def test_unknown_report_not_found(session) -> None:
    await _seed_principals(session)
    with pytest.raises(ReadinessReportNotFoundError):
        await readiness_query.get_readiness_report(session, USER1, report_id="rcrpt_missing")


# --------------------------------------------------------------------------- #
# Acceptance batch 17 — doc 01 Mainboard, backend surface                     #
#                                                                             #
# MB-01.c4 a guest Ready Check request is rejected server-side                #
# MB-27.c4 disabling a live item stales the report and leaves the Ready scope #
# --------------------------------------------------------------------------- #


async def test_guest_ready_check_is_refused_server_side_and_writes_no_report(session) -> None:
    """MB-01.c4 — the anonymous refusal is a SERVER guarantee, not a hidden button.

    The sibling clauses cover the projection read, the draft surfaces and RUN
    admission; the Ready Check mutation the criterion also names was never driven
    with an anonymous actor. The refusal is asserted together with its ABSENCE of
    a side effect — a guard that raises after writing the report row would satisfy
    ``pytest.raises`` alone — and an authenticated call over the same composition
    afterwards is the positive control, so the refusal is attributable to the
    actor rather than to an unusable composition.
    """
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)

    before = await session.scalar(select(func.count()).select_from(ReadyCheckReport))

    with pytest.raises(UnauthenticatedError):
        await readiness_cmd.run_readiness_check(
            session, Actor.anonymous(), composition_id=composition_id
        )

    # Deliberately NOT rolled back first: a rollback here would discard any row the
    # command had written and make this count pass no matter what. Measured — with
    # the guard relocated below the insert the count goes to 1 and this line reddens.
    after = await session.scalar(select(func.count()).select_from(ReadyCheckReport))
    assert after == before == 0  # refused BEFORE any immutable report exists

    # Positive control: the same composition is checkable by its owner.
    checked = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()
    assert checked["report_id"]
    assert await session.scalar(select(func.count()).select_from(ReadyCheckReport)) == 1


async def test_disabling_a_live_item_stales_the_report_and_leaves_the_ready_scope(
    session,
) -> None:
    """MB-27.c4 — the last clause of the disable row, and the one the suite only
    ever reached by a two-step inference.

    Exclusion from the hashed set and from the run result is asserted elsewhere;
    what nothing did was disable a PERSISTED item and then READ the report. Two
    independent observations are made here. (1) The existing report's EFFECTIVE
    state flips to ``stale`` while its STORED state does not move — the pair
    matters, because a test that only read ``state`` could not tell a recomputed
    projection from a rewritten row. (2) Re-running Ready Check afterwards reports
    an EMPTY composition, which is the "removed from Ready Check scope" half: the
    disabled item is not merely flagged, it is gone from the checked set.
    """
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)

    checked = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()
    report_id = checked["report_id"]
    assert checked["state"] == "ready"

    fresh = await readiness_query.get_readiness_report(session, USER1, report_id=report_id)
    assert fresh["state"] == "ready" and fresh["is_current"] is True

    board = await mb_query.get_default_mainboard(session, USER1)
    item = board["items"][0]
    await mb_cmd.patch_mainboard_item(
        session,
        USER1,
        item_id=item["item_id"],
        intent="set_enabled",
        expected_row_version=item["row_version"],
        is_enabled=False,
    )
    await session.commit()

    view = await readiness_query.get_readiness_report(session, USER1, report_id=report_id)
    assert view["state"] == "stale"  # effective state moved...
    assert view["stored_state"] == "ready"  # ...the immutable row did not
    assert view["is_current"] is False
    assert view["composition_fingerprint"] != view["current_fingerprint"]

    # The disabled item is out of the CHECKED set, not merely flagged inside it.
    rechecked = await readiness_cmd.run_readiness_check(
        session, USER1, composition_id=composition_id
    )
    await session.commit()
    assert rechecked["state"] == "not_ready"
    assert "COMPOSITION_EMPTY" in {issue["code"] for issue in rechecked["issues"]}


# --------------------------------------------------------------------------- #
# Acceptance batch 19 — doc 14 Backtest Ready Check, backend surface           #
#                                                                             #
# RC-10.c2 a NEWER catalog revision the draft does not pin never stales a      #
#          report; the fingerprint is over the PINNED revision ids only.       #
#                                                                             #
# The sibling clause (`RC-10.c1`) is a pure unit fact — ``is_stale(a, a)`` is  #
# False — and says nothing about which revision id the current fingerprint is  #
# built from. The two cases below drive the two catalogs a composition pins:   #
# the work object's own revision head, and the market dataset the strategy     #
# payload names. Both assert the CONTRAST directly (fingerprint unchanged,     #
# effective state still the stored one, ``is_current`` still true) rather than #
# inferring it from an unchanged manifest, which is what                       #
# ``test_e2e_pipeline.py::test_market_successor_never_leaks_and_rerun_is_...`` #
# already proves without ever reading a readiness report back.                 #
# --------------------------------------------------------------------------- #


async def _pinned_item(session, composition_id: str):
    items = await mb_repo.list_active_items(session, composition_id)
    assert len(items) == 1, "the fixture attaches exactly one item"
    return items[0]


async def test_rc10_newer_work_object_revision_the_board_does_not_pin_keeps_the_report_current(
    session,
) -> None:
    """RC-10.c2 — the work-object catalog axis.

    A revision append advances the ROOT head but never re-pins the Mainboard item
    (``commands/mainboard.py::create_work_object_revision``, AT#5). The report must
    therefore stay current. Every precondition is measured rather than assumed: if
    the successor silently no-op'd (the content-hash idempotency branch) the head
    would not move and this test would assert "nothing changed" in a world where
    nothing was published — the vacuous shape ADIM 91 recorded.
    """
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)
    report = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    item = await _pinned_item(session, composition_id)
    root = await session.get(EntityRegistry, item.work_object_root_id)
    assert root is not None
    pinned_revision_id = item.pinned_revision_id
    assert root.current_revision_id == pinned_revision_id  # head == pin BEFORE the append

    before = await readiness_query.get_readiness_report(
        session, USER1, report_id=report["report_id"]
    )
    assert before["is_current"] is True

    # Publish revision N+1 on the SAME root. The payload must differ, else the
    # content-hash branch returns the existing head and nothing is published.
    successor_payload = _strategy_payload()
    successor_payload["display_name"] = "Seed strategy (successor)"
    successor = await mb_cmd.create_work_object_revision(
        session, USER1, root_id=item.work_object_root_id, payload=successor_payload
    )
    await session.commit()

    # The successor really landed, and it really is one the board does not pin.
    assert successor["revision_id"] != pinned_revision_id
    await session.refresh(root)
    assert root.current_revision_id == successor["revision_id"]
    assert (await _pinned_item(session, composition_id)).pinned_revision_id == pinned_revision_id

    after = await readiness_query.get_readiness_report(
        session, USER1, report_id=report["report_id"]
    )
    # "does not stale solely because a newer catalog revision exists" (doc 14 §15).
    assert after["current_fingerprint"] == after["composition_fingerprint"]
    assert after["current_fingerprint"] == before["current_fingerprint"]
    assert after["is_current"] is True
    assert after["state"] == after["stored_state"] == before["state"]
    assert after["state"] != str(ReadinessState.STALE)


async def test_rc10_newer_approved_market_revision_keeps_the_pinned_report_current(
    session,
) -> None:
    """RC-10.c2 — the market-data catalog axis.

    RC-09's contrast case: changing the market dataset revision the draft pins
    stales the report. RC-10 is the other half — publishing an APPROVED successor
    the draft does NOT pin must not. The strategy payload pins ``md_rev_1``
    verbatim, so moving the dataset root's head to ``md_rev_2`` leaves every pinned
    id untouched.
    """
    await _seed_principals(session)
    composition_id = await _composition_with_strategy(session, USER1)
    report = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    before = await readiness_query.get_readiness_report(
        session, USER1, report_id=report["report_id"]
    )
    assert before["is_current"] is True

    md_root = await session.get(EntityRegistry, "md_root_1")
    assert md_root is not None and md_root.current_revision_id == "md_rev_1"
    session.add(
        MarketDatasetRevision(
            revision_id="md_rev_2",
            entity_id=md_root.entity_id,
            revision_no=2,
            market_data_type=MarketDataType.OHLCV,
            revision_state=MarketRevisionState.APPROVED,
            payload={},
            content_hash="c" * 64,
            created_by_principal_id="user_1",
        )
    )
    md_root.current_revision_id = "md_rev_2"
    await session.commit()

    # The successor really is the catalog head, and it really is APPROVED — a DRAFT
    # successor would be invisible to any resolver and prove nothing.
    await session.refresh(md_root)
    assert md_root.current_revision_id == "md_rev_2"
    successor = await session.get(MarketDatasetRevision, "md_rev_2")
    assert successor is not None
    assert successor.revision_state == MarketRevisionState.APPROVED
    # The draft still names the OLD exact revision (doc 14 §15 "still pins old exact
    # revision") — read back from the stored payload, not from the fixture literal.
    item = await _pinned_item(session, composition_id)
    revision = await mb_repo.get_work_object_revision(session, item.pinned_revision_id)
    assert revision is not None
    assert revision.payload["data"]["market_dataset_revision_id"] == "md_rev_1"

    after = await readiness_query.get_readiness_report(
        session, USER1, report_id=report["report_id"]
    )
    assert after["current_fingerprint"] == after["composition_fingerprint"]
    assert after["current_fingerprint"] == before["current_fingerprint"]
    assert after["is_current"] is True
    assert after["state"] == after["stored_state"] == before["state"]
    assert after["state"] != str(ReadinessState.STALE)
