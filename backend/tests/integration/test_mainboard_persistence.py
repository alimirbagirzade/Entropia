"""Stage 3a Mainboard composition plane — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers: default-workspace auto-creation (registry root + detail); work-object
create persists root + detail + immutable rev1 with ``current_revision_id`` set;
revision append bumps row_version and does NOT auto-repin a pinned item (AT#5);
attach writes a working item and recomputes ``composition_hash`` (kind match), and
rejects a divergent client kind (CR-01); patch pin_revision moves the hash while
reorder does not; a stale ``expected_row_version`` raises ROW_VERSION_CONFLICT;
snapshot writes an immutable row carrying the item manifest; soft-deleting a root
drops its item out of the active projection and is idempotent on repeat. A
representative mutation is asserted to have written audit + outbox rows in the same
transaction.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.domain.mainboard.composition import composition_hash
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    BacktestResult,
    MainboardCompositionSnapshot,
    OutboxEvent,
    Principal,
    ResultSummary,
)
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.shared.errors import (
    MainboardItemKindMismatchError,
    RowVersionConflictError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_principals(session) -> None:
    for pid in ("user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _create_strategy(session, actor: Actor = USER1, *, name: str = "Strat") -> dict:
    result = await mb_cmd.create_work_object(
        session,
        actor,
        object_kind="strategy",
        payload={"name": name},
    )
    await session.flush()
    return result


# --------------------------------------------------------------------------- #
# Default workspace                                                           #
# --------------------------------------------------------------------------- #


async def test_get_default_mainboard_auto_creates_workspace(session) -> None:
    await _seed_principals(session)

    projection = await mb_query.get_default_mainboard(session, USER1)
    await session.commit()

    workspace_id = projection["workspace_id"]
    assert workspace_id.startswith("mbws_")
    assert projection["workspace_kind"] == "human_default"
    assert projection["items"] == []
    # A never-checked composition is not_checked (a transient UI state, no report),
    # NOT not_ready — the real Ready Check projection, GAP-05 / doc 14 §4.
    assert projection["ready_summary"] == {"state": "not_checked", "report_id": None}
    assert projection["latest_result_summary"] is None

    # A registry root + detail row now exist for the workspace.
    root = await mb_repo.get_workspace(session, workspace_id)
    detail = await mb_repo.get_workspace_detail(session, workspace_id)
    assert root is not None and root.owner_principal_id == "user_1"
    assert detail is not None and detail.is_default is True

    # Calling again returns the same workspace (query-before-create, one default).
    again = await mb_query.get_default_mainboard(session, USER1)
    assert again["workspace_id"] == workspace_id


# --------------------------------------------------------------------------- #
# Work objects                                                                #
# --------------------------------------------------------------------------- #


async def test_create_work_object_persists_root_detail_and_rev1(session) -> None:
    await _seed_principals(session)

    result = await _create_strategy(session)
    await session.commit()

    root_id = result["root_id"]
    assert root_id.startswith("wo_")
    assert result["revision_no"] == 1
    assert result["object_kind"] == "strategy"

    root = await mb_repo.get_work_object_root(session, root_id)
    detail = await mb_repo.get_work_object_detail(session, root_id)
    revision = await mb_repo.get_work_object_revision(session, result["revision_id"])
    assert root is not None and root.deletion_state == DeletionState.ACTIVE
    assert root.current_revision_id == result["revision_id"]  # head pointer set
    assert detail is not None and str(detail.object_kind) == "strategy"
    assert revision is not None and revision.revision_no == 1


async def test_create_work_object_revision_appends_and_does_not_repin(session) -> None:
    await _seed_principals(session)
    created = await _create_strategy(session, name="v1")
    root_id = created["root_id"]
    rev1_id = created["revision_id"]

    # Attach an item pinned to rev1 so we can prove the append does NOT repin it.
    board = await mb_query.get_default_mainboard(session, USER1)
    workspace_id = board["workspace_id"]
    attached = await mb_cmd.attach_mainboard_item(
        session, USER1, workspace_id=workspace_id, root_id=root_id, revision_id=rev1_id
    )
    await session.flush()
    item_id = attached["item_id"]

    rev2 = await mb_cmd.create_work_object_revision(
        session, USER1, root_id=root_id, payload={"name": "v2"}
    )
    await session.commit()

    assert rev2["revision_no"] == 2
    assert rev2["revision_id"] != rev1_id
    root = await mb_repo.get_work_object_root(session, root_id)
    assert root is not None and root.current_revision_id == rev2["revision_id"]
    assert root.row_version == 2  # advanced on append

    # AT#5: the working item still pins rev1 — no auto-repin.
    item = await mb_repo.get_item(session, item_id)
    assert item is not None and item.pinned_revision_id == rev1_id


# --------------------------------------------------------------------------- #
# Attach + CR-01                                                              #
# --------------------------------------------------------------------------- #


async def test_attach_writes_item_and_updates_composition_hash(session) -> None:
    await _seed_principals(session)
    created = await _create_strategy(session)
    board = await mb_query.get_default_mainboard(session, USER1)
    workspace_id = board["workspace_id"]
    assert board["composition_hash"] is None  # empty workspace, not yet stored

    attached = await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=workspace_id,
        root_id=created["root_id"],
        revision_id=created["revision_id"],
    )
    await session.commit()

    assert attached["item_id"].startswith("mbi_")
    assert attached["item_kind"] == "strategy"  # server-derived
    assert attached["pinned_revision_id"] == created["revision_id"]
    assert attached["is_enabled"] is True
    new_hash = attached["composition_hash"]
    assert new_hash is not None

    detail = await mb_repo.get_workspace_detail(session, workspace_id)
    assert detail is not None and detail.composition_hash == new_hash

    listed = await mb_query.get_default_mainboard(session, USER1)
    assert [i["item_id"] for i in listed["items"]] == [attached["item_id"]]


async def test_attach_with_mismatched_client_kind_is_rejected(session) -> None:
    await _seed_principals(session)
    created = await _create_strategy(session)  # object_kind == strategy
    board = await mb_query.get_default_mainboard(session, USER1)

    with pytest.raises(MainboardItemKindMismatchError):
        await mb_cmd.attach_mainboard_item(
            session,
            USER1,
            workspace_id=board["workspace_id"],
            root_id=created["root_id"],
            revision_id=created["revision_id"],
            item_kind="trading_signal",  # divergent client value -> CR-01 422
        )


# --------------------------------------------------------------------------- #
# Patch intents                                                               #
# --------------------------------------------------------------------------- #


async def _attach_strategy_item(session, actor: Actor = USER1) -> tuple[str, str, str]:
    """Create a strategy + a second revision, attach pinned to rev1. Returns
    (workspace_id, item_id, rev2_id)."""
    created = await mb_cmd.create_work_object(
        session, actor, object_kind="strategy", payload={"name": "v1"}
    )
    await session.flush()
    rev2 = await mb_cmd.create_work_object_revision(
        session, actor, root_id=created["root_id"], payload={"name": "v2"}
    )
    await session.flush()
    board = await mb_query.get_default_mainboard(session, actor)
    attached = await mb_cmd.attach_mainboard_item(
        session,
        actor,
        workspace_id=board["workspace_id"],
        root_id=created["root_id"],
        revision_id=created["revision_id"],
    )
    await session.flush()
    return board["workspace_id"], attached["item_id"], rev2["revision_id"]


async def test_patch_pin_revision_changes_hash(session) -> None:
    await _seed_principals(session)
    workspace_id, item_id, rev2_id = await _attach_strategy_item(session)
    before = (await mb_repo.get_workspace_detail(session, workspace_id)).composition_hash

    patched = await mb_cmd.patch_mainboard_item(
        session,
        USER1,
        item_id=item_id,
        intent="pin_revision",
        expected_row_version=1,
        revision_id=rev2_id,
    )
    await session.commit()

    assert patched["pinned_revision_id"] == rev2_id
    assert patched["row_version"] == 2  # bumped
    assert patched["composition_hash"] != before  # pin moves the fingerprint


async def test_patch_reorder_does_not_change_hash(session) -> None:
    await _seed_principals(session)
    workspace_id, item_id, _rev2_id = await _attach_strategy_item(session)
    before = (await mb_repo.get_workspace_detail(session, workspace_id)).composition_hash

    patched = await mb_cmd.patch_mainboard_item(
        session,
        USER1,
        item_id=item_id,
        intent="reorder",
        expected_row_version=1,
        position_index=999,
    )
    await session.commit()

    assert patched["position_index"] == 999
    assert patched["row_version"] == 2  # still bumped
    assert patched["composition_hash"] == before  # reorder is presentation-only


async def test_patch_with_stale_row_version_conflicts(session) -> None:
    await _seed_principals(session)
    _workspace_id, item_id, _rev2_id = await _attach_strategy_item(session)

    with pytest.raises(RowVersionConflictError):
        await mb_cmd.patch_mainboard_item(
            session,
            USER1,
            item_id=item_id,
            intent="reorder",
            expected_row_version=99,  # stale
            position_index=5,
        )


# --------------------------------------------------------------------------- #
# Snapshot                                                                    #
# --------------------------------------------------------------------------- #


async def test_create_composition_snapshot_writes_immutable_row(session) -> None:
    await _seed_principals(session)
    created = await _create_strategy(session)
    board = await mb_query.get_default_mainboard(session, USER1)
    workspace_id = board["workspace_id"]
    await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=workspace_id,
        root_id=created["root_id"],
        revision_id=created["revision_id"],
    )
    await session.flush()

    result = await mb_cmd.create_composition_snapshot(session, USER1, workspace_id=workspace_id)
    await session.commit()

    assert result["snapshot_id"].startswith("mbsnap_")
    assert result["item_count"] == 1

    snapshot = await session.get(MainboardCompositionSnapshot, result["snapshot_id"])
    assert snapshot is not None
    assert snapshot.readiness_state == "unevaluated"
    assert snapshot.readiness_report_id is None  # Stage 4 fills this
    manifest = snapshot.item_manifest
    assert manifest["snapshot_id"] == result["snapshot_id"]  # backfilled
    assert manifest["composition_hash"] == result["composition_hash"]
    assert len(manifest["items"]) == 1
    assert manifest["items"][0]["root_id"] == created["root_id"]


# --------------------------------------------------------------------------- #
# Soft delete                                                                 #
# --------------------------------------------------------------------------- #


async def test_soft_delete_drops_item_from_projection_and_is_idempotent(session) -> None:
    await _seed_principals(session)
    created = await _create_strategy(session)
    board = await mb_query.get_default_mainboard(session, USER1)
    workspace_id = board["workspace_id"]
    await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=workspace_id,
        root_id=created["root_id"],
        revision_id=created["revision_id"],
    )
    await session.flush()
    assert len((await mb_query.get_default_mainboard(session, USER1))["items"]) == 1

    deleted = await mb_cmd.soft_delete_work_object(session, USER1, root_id=created["root_id"])
    await session.commit()
    assert deleted["root_id"] == created["root_id"]

    root = await mb_repo.get_work_object_root(session, created["root_id"])
    assert root is not None and root.deletion_state == DeletionState.SOFT_DELETED
    # The item row still exists but is filtered out of the active projection.
    assert (await mb_query.get_default_mainboard(session, USER1))["items"] == []

    # Repeat delete is an idempotent no-op (no error raised).
    again = await mb_cmd.soft_delete_work_object(session, USER1, root_id=created["root_id"])
    await session.commit()
    assert again["root_id"] == created["root_id"]


# --------------------------------------------------------------------------- #
# Audit + outbox same-tx                                                      #
# --------------------------------------------------------------------------- #


async def test_attach_writes_audit_and_outbox_rows(session) -> None:
    await _seed_principals(session)
    created = await _create_strategy(session)
    board = await mb_query.get_default_mainboard(session, USER1)
    await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=board["workspace_id"],
        root_id=created["root_id"],
        revision_id=created["revision_id"],
    )
    await session.commit()

    audit_kinds = set((await session.execute(select(AuditEvent.event_kind))).scalars().all())
    outbox_types = set((await session.execute(select(OutboxEvent.event_type))).scalars().all())
    # The attach mutation emits both the item-attached and composition-changed events.
    assert "mainboard.item_attached" in audit_kinds
    assert "mainboard.composition_changed" in audit_kinds
    assert "mainboard.work_object_created" in audit_kinds
    assert "mainboard.item_attached" in outbox_types
    assert "mainboard.composition_changed" in outbox_types


# --------------------------------------------------------------------------- #
# Latest-result + readiness projection (GAP-05)                               #
# --------------------------------------------------------------------------- #


async def test_default_mainboard_surfaces_latest_result_and_snapshot_badge(session) -> None:
    # GAP-05 / doc 15 §9.4: the default Mainboard shows the most recent ACTIVE
    # succeeded Result for its composition; flags "snapshot differs" when the live
    # composition fingerprint has moved past the result's pinned one; prefers the
    # newest by time; excludes soft-deleted results; never fabricates a summary.
    await _seed_principals(session)
    board = await mb_query.get_default_mainboard(session, USER1)
    workspace_id = board["workspace_id"]
    current_fp = composition_hash([])  # the empty composition's live fingerprint

    older = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    newer = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)

    # A succeeded Result pinned to the CURRENT composition -> snapshot matches.
    # BacktestResult is flushed before its ResultSummary child: these models carry
    # no ORM relationship(), so the FK insert order is not derived (PR #147 lesson).
    session.add(
        BacktestResult(
            result_id="btr_current",
            run_id="btrun_current",
            manifest_id="btman_current",
            manifest_hash="a" * 64,
            workspace_entity_id=workspace_id,
            composition_fingerprint=current_fp,
            engine_version="backtest-engine-test",
            deletion_state="active",
            created_at=older,
        )
    )
    await session.flush()
    session.add(
        ResultSummary(
            summary_id="btsum_current",
            result_id="btr_current",
            symbol="BTCUSD",
            timeframe="1h",
            period_start="2026-01-01",
            period_end="2026-02-01",
            total_trades=7,
            headline={"pnl": "123.45"},
        )
    )
    await session.flush()

    latest = (await mb_query.get_default_mainboard(session, USER1))["latest_result_summary"]
    assert latest is not None
    assert latest["result_id"] == "btr_current"
    assert latest["composition_fingerprint"] == current_fp
    assert latest["snapshot_differs"] is False
    assert latest["summary"] == {
        "symbol": "BTCUSD",
        "timeframe": "1h",
        "period_start": "2026-01-01",
        "period_end": "2026-02-01",
        "total_trades": 7,
        "headline": {"pnl": "123.45"},
    }

    # A NEWER Result pinned to a DIFFERENT composition -> newest wins + badge on;
    # it has no ResultSummary row -> honest null summary (never fabricated, L4).
    session.add(
        BacktestResult(
            result_id="btr_stale",
            run_id="btrun_stale",
            manifest_id="btman_stale",
            manifest_hash="b" * 64,
            workspace_entity_id=workspace_id,
            composition_fingerprint="d" * 64,
            engine_version="backtest-engine-test",
            deletion_state="active",
            created_at=newer,
        )
    )
    await session.flush()

    latest = (await mb_query.get_default_mainboard(session, USER1))["latest_result_summary"]
    assert latest["result_id"] == "btr_stale"
    assert latest["snapshot_differs"] is True
    assert latest["summary"] is None

    # Soft-deleting the newest excludes it -> falls back to the older active one.
    stale = await session.get(BacktestResult, "btr_stale")
    assert stale is not None
    stale.deletion_state = "deleted"
    await session.flush()

    latest = (await mb_query.get_default_mainboard(session, USER1))["latest_result_summary"]
    assert latest["result_id"] == "btr_current"
    assert latest["snapshot_differs"] is False
