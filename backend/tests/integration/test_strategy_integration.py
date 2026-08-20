"""Stage 3b Strategy Details — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers the doc 02 acceptance surface: draft create persists the shared work-object
registry root + strategy_root detail + editor draft with NO revision yet (AT-01);
Save creates an immutable ``strategy_revision`` + ``config_hash`` + pinned
references + a mirror ``work_object_revision`` and advances lifecycle draft->
validated (AT-02); an attached Mainboard item is re-pinned on Save so the
workspace ``composition_hash`` changes -> prior Ready report STALE (AT-20); sizing
exclusivity (AT-12) and trigger-source-conditional (AT-05) are typed 422s; a stale
``expected_draft_row_version`` -> STRATEGY_DRAFT_CONFLICT (AT-19); a foreign owner
cannot save (AT-22); Clear resets the draft without deleting the root (AT-23);
Save writes audit + outbox in the same tx; a repeated idempotency key returns the
cached revision (no second revision).
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import strategy_draft as strat_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import strategy as strat_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    EntityRegistry,
    OutboxEvent,
    Principal,
    RationaleFamilyRoot,
    StrategyRevision,
    StrategyRoot,
    TrashEntry,
    WorkObjectRevision,
    WorkObjectRoot,
)
from entropia.infrastructure.postgres.repositories import strategy as strat_repo
from entropia.shared.errors import (
    AccessDeniedError,
    RationaleFamilyNotActive,
    SizingMethodNotExclusiveError,
    StrategyDraftConflictError,
    StrategyValidationFailedError,
    TriggerSourceConditionRequiredError,
    UnauthenticatedError,
    ValidationError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)

_HASH = "a" * 64
_PKG_HASH = "f" * 64
_FAMILY_ID = "ratfam_int"


def _valid_payload(display_name: str = "Integration Strategy") -> dict[str, Any]:
    """A fully valid StrategyConfig payload (market order, one entry indicator,
    percentage stop, base sizing, scaling disabled)."""
    return {
        "strategy_root_id": "strat_placeholder",
        "display_name": display_name,
        "rationale_family_id": "ratfam_int",
        "data": {
            "instrument_id": "BTCUSDT",
            "market_dataset_root_id": "market_int_root",
            "market_dataset_revision_id": "mrev_int",
            "market_dataset_content_hash": _HASH,
            "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
            "initial_capital": "10000.00",
            "execution": {"entry_timing": "next_candle_open", "exit_timing": "next_candle_close"},
            "order_config": {"type": "market_order", "limit": None},
            "costs": {
                "commission": "0.001",
                "spread": "0.0002",
                "slippage_mode": "percentage_slippage",
                "slippage_value": "0.01",
            },
            "intrabar_policy": {"tick_policy": "inherit"},
            "funding": {"enabled": False},
        },
        "position_entry_logic": {
            "direction_mode": "long_and_short",
            "signal_block": {
                "rule": "required_indicator_blocks_only",
                "min_supporting_count": None,
            },
            "indicator_blocks": [
                {
                    "block_id": "ind_int",
                    "display_order": 0,
                    "enabled": True,
                    "package_ref": {
                        "package_root_id": "pkg_int",
                        "package_revision_id": "pkgrev_int",
                        "package_content_hash": _PKG_HASH,
                    },
                    "trigger_source": "indicator_native_trigger",
                    "direction": "long",
                    "timeframe": "same_as_base_tf",
                    "validity": "3_candles",
                    "requirement": "required",
                    "condition_block_rule": None,
                    "min_supporting_condition_count": None,
                    "condition_blocks": None,
                    "parameter_overrides": None,
                }
            ],
        },
        "position_exit_logic": {
            "applies_to_direction": "long_and_short",
            "close_percentage": "100",
            "partial_aftermath": "move_stop_to_entry",
            "signal_block": None,
            "indicator_blocks": None,
        },
        "protection_stop_logic": {
            "percentage_stop": {"enabled": True, "loss_percentage": "1.0"},
            "trailing_stop": None,
            "absolute_stop": None,
        },
        "position_sizing": {
            "method": "base_position_size",
            "base_position_size": "100.0",
            # GH #550: saved AFTER sizing became a percent of resolved capital, so
            # Ready Check raises no STRATEGY_SIZING_SEMANTICS_UNCONFIRMED blocker.
            "size_semantics": "percent_of_capital",
            "risk_based": None,
            "formula_based": None,
            "signal_strength_adjustment": "no_adjustment",
            "leverage_mode": "isolated",
            "position_size_limits": None,
        },
        "scaling_logic": {
            "enabled": False,
            "timeframe": "same_as_base_tf",
            "method": None,
            "price_scaling": None,
            "logic_scaling": None,
            "add_size": "percent_of_initial",
            "add_size_value": None,
            "scaling_limits": None,
        },
        "restrictions_filters": {"rule": "any", "filters": []},
        "conflict_position_handling": {
            "overlapping_signal_policy": "queue_sequential",
            "same_direction_stacking": "allow_stacking",
            "opposite_direction_hedge": "allow_hedge",
            "exit_on_opposite_signal": True,
        },
    }


async def _seed_principals(session) -> None:
    for pid in ("user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_rationale_family(session) -> str:
    """Make the literal ``ratfam_int`` a REAL family (I-08).

    ``strategy_root.rationale_family_id`` is a FK now, so the id these tests pass
    has to exist. It stays a fixed literal rather than a generated one so it still
    matches the ``rationale_family_id`` inside ``_valid_payload`` — the payload
    snapshot and the column are meant to agree.
    """
    await _seed_principals(session)
    if await session.get(RationaleFamilyRoot, _FAMILY_ID) is None:
        session.add(
            EntityRegistry(
                entity_id=_FAMILY_ID,
                entity_type="rationale_family",
                owner_principal_id="user_1",
                created_by_principal_id="user_1",
                deletion_state=DeletionState.ACTIVE,
                row_version=1,
            )
        )
        await session.flush()
        session.add(RationaleFamilyRoot(entity_id=_FAMILY_ID, display_color="#00a9e8"))
        await session.flush()
    return _FAMILY_ID


async def _new_draft(
    session, actor: Actor = USER1, *, payload: dict[str, Any] | None = None
) -> dict:
    await _seed_rationale_family(session)
    result = await strat_cmd.create_strategy_draft(
        session,
        actor,
        display_name="Integration Strategy",
        rationale_family_id=_FAMILY_ID,
        initial_payload=payload if payload is not None else _valid_payload(),
    )
    await session.flush()
    return result


# --------------------------------------------------------------------------- #
# Create draft (AT-01)                                                        #
# --------------------------------------------------------------------------- #


async def test_create_draft_persists_root_and_draft_without_revision(session) -> None:
    await _seed_principals(session)
    result = await _new_draft(session)

    assert result["draft_id"].startswith("stratdraft_")
    assert result["strategy_root_id"].startswith("strat_")
    assert result["row_version"] == 0

    root = await session.get(EntityRegistry, result["strategy_root_id"])
    assert root is not None
    assert root.entity_type == "work_object"
    assert root.deletion_state == DeletionState.ACTIVE

    detail = await session.get(StrategyRoot, result["strategy_root_id"])
    work_object = await session.get(WorkObjectRoot, result["strategy_root_id"])
    assert detail is not None and str(detail.lifecycle_state) == "draft"
    assert detail.current_revision_id is None  # AT-01: no revision until first Save
    assert work_object is not None and str(work_object.object_kind) == "strategy"


async def test_create_draft_rejects_unknown_rationale_family_before_fk(session) -> None:
    await _seed_principals(session)

    with pytest.raises(RationaleFamilyNotActive):
        await strat_cmd.create_strategy_draft(
            session,
            USER1,
            display_name="Unknown family",
            rationale_family_id="ratfam_missing",
        )


# --------------------------------------------------------------------------- #
# Save -> immutable revision + config_hash (AT-02)                            #
# --------------------------------------------------------------------------- #


async def test_save_creates_immutable_revision_and_pins_references(session) -> None:
    await _seed_principals(session)
    draft = await _new_draft(session)

    saved = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.flush()

    assert saved["revision_number"] == 1
    assert len(saved["config_hash"]) == 64
    assert saved["ready_state"] == "STALE"

    revision = await session.get(StrategyRevision, saved["strategy_revision_id"])
    assert revision is not None and revision.config_hash == saved["config_hash"]

    detail = await session.get(StrategyRoot, saved["strategy_root_id"])
    assert detail is not None
    assert detail.current_revision_id == saved["strategy_revision_id"]
    assert str(detail.lifecycle_state) == "validated"  # draft -> validated

    # References pin the market dataset + the entry indicator package (exact ids).
    refs = list(await strat_repo.list_references(session, saved["strategy_revision_id"]))
    roles = {str(r.dependency_role) for r in refs}
    assert "data_source" in roles and "entry_indicator" in roles

    # A second Save appends revision 2 (the original revision is unchanged).
    saved2 = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=1
    )
    await session.flush()
    assert saved2["revision_number"] == 2
    assert saved2["strategy_revision_id"] != saved["strategy_revision_id"]
    still = await session.get(StrategyRevision, saved["strategy_revision_id"])
    assert still is not None and still.revision_number == 1


# --------------------------------------------------------------------------- #
# Save re-pins an attached Mainboard item -> Ready STALE (AT-20)              #
# --------------------------------------------------------------------------- #


async def test_save_repins_attached_item_and_changes_composition_hash(session) -> None:
    await _seed_principals(session)
    draft = await _new_draft(session)
    projection = await mb_query.get_default_mainboard(session, USER1)
    workspace_id = projection["workspace_id"]

    saved1 = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.flush()

    attach = await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=workspace_id,
        root_id=saved1["strategy_root_id"],
        revision_id=saved1["mirror_revision_id"],
    )
    await session.flush()
    hash_after_attach = attach["composition_hash"]

    saved2 = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=1
    )
    await session.flush()

    assert saved2["pinned_items"], "Save must re-pin the attached Mainboard item"
    new_hash = saved2["pinned_items"][0]["composition_hash"]
    assert new_hash != hash_after_attach  # composition changed -> prior Ready STALE


# --------------------------------------------------------------------------- #
# Validation blockers (AT-12, AT-05)                                          #
# --------------------------------------------------------------------------- #


async def test_sizing_method_not_exclusive_is_rejected(session) -> None:
    await _seed_principals(session)
    payload = _valid_payload()
    payload["position_sizing"]["risk_based"] = {
        "risk_percentage_per_trade": "1.0",
        "stop_loss_point": "50.0",
    }
    draft = await _new_draft(session, payload=payload)
    with pytest.raises(SizingMethodNotExclusiveError):
        await strat_cmd.save_strategy_revision(
            session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=0
        )


async def test_trigger_source_condition_required_is_rejected(session) -> None:
    await _seed_principals(session)
    payload = _valid_payload()
    payload["position_entry_logic"]["indicator_blocks"][0]["trigger_source"] = (
        "indicator_native_trigger_plus_condition"
    )
    draft = await _new_draft(session, payload=payload)
    with pytest.raises(TriggerSourceConditionRequiredError):
        await strat_cmd.save_strategy_revision(
            session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=0
        )


# --------------------------------------------------------------------------- #
# Optimistic concurrency + authorization (AT-19, AT-22)                       #
# --------------------------------------------------------------------------- #


async def test_stale_expected_row_version_conflicts(session) -> None:
    await _seed_principals(session)
    draft = await _new_draft(session)
    with pytest.raises(StrategyDraftConflictError):
        await strat_cmd.save_strategy_revision(
            session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=99
        )


async def test_foreign_user_cannot_save(session) -> None:
    await _seed_principals(session)
    draft = await _new_draft(session, USER1)
    with pytest.raises(AccessDeniedError):
        await strat_cmd.save_strategy_revision(
            session, USER2, draft_id=draft["draft_id"], expected_draft_row_version=0
        )


# --------------------------------------------------------------------------- #
# Clear (AT-23) + audit/outbox + idempotency                                  #
# --------------------------------------------------------------------------- #


async def test_clear_resets_draft_without_deleting_root(session) -> None:
    await _seed_principals(session)
    draft = await _new_draft(session)
    cleared = await strat_cmd.clear_strategy_draft(
        session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.flush()
    assert cleared["cleared"] is True

    row = await strat_repo.get_strategy_draft(session, draft["draft_id"])
    assert row is not None and row.payload == {}
    # The root is untouched (Clear is not a delete).
    root = await session.get(EntityRegistry, draft["strategy_root_id"])
    assert root is not None and root.deletion_state == DeletionState.ACTIVE


async def test_save_writes_audit_and_outbox(session) -> None:
    await _seed_principals(session)
    draft = await _new_draft(session)
    saved = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.flush()

    audit = (
        (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.event_kind == "strategy.revision_created",
                    AuditEvent.target_entity_id == saved["strategy_root_id"],
                )
            )
        )
        .scalars()
        .all()
    )
    outbox = (
        (
            await session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.event_type == "strategy.revision_created",
                    OutboxEvent.resource_id == saved["strategy_root_id"],
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit) == 1 and len(outbox) == 1


async def test_repeated_idempotency_key_returns_cached_revision(session) -> None:
    await _seed_principals(session)
    draft = await _new_draft(session)
    first = await strat_cmd.save_strategy_revision(
        session,
        USER1,
        draft_id=draft["draft_id"],
        expected_draft_row_version=0,
        idempotency_key="save-1",
    )
    await session.flush()
    second = await strat_cmd.save_strategy_revision(
        session,
        USER1,
        draft_id=draft["draft_id"],
        expected_draft_row_version=0,
        idempotency_key="save-1",
    )
    await session.flush()

    assert first["strategy_revision_id"] == second["strategy_revision_id"]
    revisions = list(await strat_repo.list_strategy_revisions(session, draft["strategy_root_id"]))
    assert len(revisions) == 1  # no second revision created


# --------------------------------------------------------------------------- #
# F-18 — durable/discoverable drafts: list-mine query                          #
# --------------------------------------------------------------------------- #


async def test_list_strategy_drafts_returns_owner_drafts_newest_first(session) -> None:
    await _seed_principals(session)
    first = await _new_draft(session, USER1, payload=_valid_payload("Alpha"))
    second = await _new_draft(session, USER1, payload=_valid_payload("Beta"))

    listed = await strat_query.list_strategy_drafts(session, USER1)

    ids = [row["draft_id"] for row in listed]
    assert first["draft_id"] in ids and second["draft_id"] in ids
    # Newest edit first: ULID draft ids sort desc as a stable same-timestamp tiebreak.
    assert ids.index(max(first["draft_id"], second["draft_id"])) == 0
    row = next(r for r in listed if r["draft_id"] == first["draft_id"])
    assert row["display_name"] == "Integration Strategy"
    assert row["has_revision"] is False  # AT-01: unsaved draft has no revision
    assert row["is_attached"] is False
    assert row["is_dirty"] is True
    assert row["owner_principal_id"] == "user_1"


async def test_list_strategy_drafts_never_leaks_across_users(session) -> None:
    await _seed_principals(session)
    draft = await _new_draft(session, USER1)

    mine = await strat_query.list_strategy_drafts(session, USER1)
    theirs = await strat_query.list_strategy_drafts(session, USER2)

    assert draft["draft_id"] in {row["draft_id"] for row in mine}
    assert draft["draft_id"] not in {row["draft_id"] for row in theirs}


async def test_list_strategy_drafts_admin_sees_every_owner(session) -> None:
    await _seed_principals(session)
    d1 = await _new_draft(session, USER1)
    d2 = await _new_draft(session, USER2)

    admin = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
    listed = await strat_query.list_strategy_drafts(session, admin)

    ids = {row["draft_id"] for row in listed}
    assert d1["draft_id"] in ids and d2["draft_id"] in ids


async def test_list_strategy_drafts_flags_saved_and_attached(session) -> None:
    await _seed_principals(session)
    draft = await _new_draft(session, USER1)
    workspace_id = (await mb_query.get_default_mainboard(session, USER1))["workspace_id"]
    saved = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.flush()
    await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=workspace_id,
        root_id=saved["strategy_root_id"],
        revision_id=saved["mirror_revision_id"],
    )
    await session.flush()

    row = next(
        r
        for r in await strat_query.list_strategy_drafts(session, USER1)
        if r["draft_id"] == draft["draft_id"]
    )
    assert row["has_revision"] is True
    assert row["is_attached"] is True
    assert row["last_saved_revision_id"] == saved["strategy_revision_id"]


async def test_list_strategy_drafts_excludes_soft_deleted(session) -> None:
    await _seed_principals(session)
    draft = await _new_draft(session, USER1)
    await mb_cmd.soft_delete_work_object(session, USER1, root_id=draft["strategy_root_id"])
    await session.flush()

    listed = await strat_query.list_strategy_drafts(session, USER1)
    assert draft["draft_id"] not in {row["draft_id"] for row in listed}


async def test_list_strategy_drafts_excludes_attached_then_trashed_draft(session) -> None:
    # The literal "a Trashed draft must not linger on the Mainboard" case: a draft
    # that was SAVED + ATTACHED (so the is_attached EXISTS subquery is true) and
    # then soft-deleted must still drop out of the list — the deletion_state=ACTIVE
    # filter wins over the standing attachment, so the Mainboard draft row does not
    # survive the move to Trash.
    await _seed_principals(session)
    draft = await _new_draft(session, USER1)
    workspace_id = (await mb_query.get_default_mainboard(session, USER1))["workspace_id"]
    saved = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.flush()
    await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=workspace_id,
        root_id=saved["strategy_root_id"],
        revision_id=saved["mirror_revision_id"],
    )
    await session.flush()
    # Sanity: while active it IS listed and flagged attached.
    active = next(
        r
        for r in await strat_query.list_strategy_drafts(session, USER1)
        if r["draft_id"] == draft["draft_id"]
    )
    assert active["is_attached"] is True

    await mb_cmd.soft_delete_work_object(session, USER1, root_id=draft["strategy_root_id"])
    await session.flush()

    listed = await strat_query.list_strategy_drafts(session, USER1)
    assert draft["draft_id"] not in {row["draft_id"] for row in listed}


async def test_list_strategy_drafts_rejects_guest(session) -> None:
    await _seed_principals(session)
    await _new_draft(session, USER1)
    with pytest.raises(UnauthenticatedError):
        await strat_query.list_strategy_drafts(session, Actor.anonymous())


# --------------------------------------------------------------------------- #
# Acceptance batch 15 — doc 02 backend surface                                #
#                                                                             #
# AT-01.c2 unsaved draft cannot enter the Ready Check / RUN input             #
# AT-11.c2 a disabled stop leaves the saved revision AND its dependency edges #
# AT-11.c3 re-enabling a disabled stop revalidates its stored value           #
# AT-22.c3 Admin CAN mutate another owner's Strategy Root (Supervisor cannot) #
# AT-23.c3 a prior immutable revision survives a Clear untouched              #
# --------------------------------------------------------------------------- #


SUPERVISOR = Actor(
    principal_id="supervisor_1", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR
)
ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)


async def _seed_extra_principals(session) -> None:
    for pid in ("supervisor_1", "admin_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


def _stop_logic_block(block_id: str, *, enabled: bool, package_root_id: str) -> dict[str, Any]:
    """A Logic-Based Stop Block (§5.5) pinning its own indicator package.

    Shaped like the entry block in ``_valid_payload`` — a native trigger, so no
    Condition block is required by AT-05's rule.
    """
    return {
        "block_id": block_id,
        "display_order": 0,
        "enabled": enabled,
        "package_ref": {
            "package_root_id": package_root_id,
            "package_revision_id": f"{package_root_id}_rev",
            "package_content_hash": _PKG_HASH,
        },
        "trigger_source": "indicator_native_trigger",
        "direction": "long",
        "timeframe": "same_as_base_tf",
        "validity": "3_candles",
        "requirement": "required",
        "condition_block_rule": None,
        "min_supporting_condition_count": None,
        "condition_blocks": None,
        "parameter_overrides": None,
    }


async def test_unsaved_draft_cannot_be_pinned_into_a_mainboard_composition(session) -> None:
    """AT-01.c2 — the ONLY door into the Ready Check / RUN input is a pinned
    revision, and an unsaved draft has none.

    The refusal is measured on the seam that guards it (``attach_mainboard_item``
    resolves the exact ``(root_id, revision_id)`` pair, L5 — never a name or a
    "latest"), on BOTH the forged-id branches a client could take. The Save at the
    end is the positive control: same root, same actor, same workspace, and the
    attach then succeeds — so the refusal is attributable to the missing revision
    rather than to a broken harness.
    """
    await _seed_principals(session)
    unsaved = await _new_draft(session)
    other = await _new_draft(session)
    other_saved = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=other["draft_id"], expected_draft_row_version=0
    )
    await session.flush()

    workspace_id = (await mb_query.get_default_mainboard(session, USER1))["workspace_id"]

    # The load-bearing fact: an unsaved draft's root carries no revision at all,
    # so no argument exists that would let it into a composition.
    mirrors = (
        (
            await session.execute(
                select(WorkObjectRevision).where(
                    WorkObjectRevision.entity_id == unsaved["strategy_root_id"]
                )
            )
        )
        .scalars()
        .all()
    )
    assert mirrors == []

    # Branch 1: a revision id that does not exist.
    with pytest.raises(ValidationError) as missing:
        await mb_cmd.attach_mainboard_item(
            session,
            USER1,
            workspace_id=workspace_id,
            root_id=unsaved["strategy_root_id"],
            revision_id="wrev_not_a_revision",
        )
    assert [issue["field"] for issue in missing.value.details] == ["revision_id"]

    # Branch 2: a REAL, same-kind strategy revision borrowed from another root —
    # the shape a client would forge to get an unsaved draft into the run input.
    with pytest.raises(ValidationError) as borrowed:
        await mb_cmd.attach_mainboard_item(
            session,
            USER1,
            workspace_id=workspace_id,
            root_id=unsaved["strategy_root_id"],
            revision_id=other_saved["mirror_revision_id"],
        )
    # Pinned by field rather than by exception class: a same-kind revision of the
    # wrong root must fail the belongs-to-root check, not the AOS-12 kind check.
    assert [issue["actual"] for issue in borrowed.value.details] == [
        other_saved["mirror_revision_id"]
    ]

    board = await mb_query.get_default_mainboard(session, USER1)
    assert unsaved["strategy_root_id"] not in {
        item["work_object_root_id"] for item in board["items"]
    }

    # Positive control: Save is the only thing that changes, and the attach lands.
    now_saved = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=unsaved["draft_id"], expected_draft_row_version=0
    )
    await session.flush()
    await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=workspace_id,
        root_id=unsaved["strategy_root_id"],
        revision_id=now_saved["mirror_revision_id"],
    )
    await session.flush()
    board_after = await mb_query.get_default_mainboard(session, USER1)
    assert unsaved["strategy_root_id"] in {
        item["work_object_root_id"] for item in board_after["items"]
    }


async def test_disabled_stops_leave_the_saved_revision_and_its_dependency_edges(session) -> None:
    """AT-11.c2 — a disabled Percentage/Logic stop is absent from the stored
    canonical config AND from the pinned dependency edges.

    Both halves are asserted against enabled siblings in the SAME save, so the
    test cannot pass by dropping the section wholesale: the trailing stop and the
    enabled Logic block must survive exactly where the disabled ones vanish.
    """
    await _seed_principals(session)
    payload = _valid_payload()
    payload["protection_stop_logic"] = {
        "percentage_stop": {"enabled": False, "loss_percentage": "1.0"},
        "trailing_stop": {"enabled": True, "trail_percentage": "2.0", "lock_in_percentage": "0.8"},
        "absolute_stop": None,
        "logic_blocks": [
            _stop_logic_block("stopblk_on", enabled=True, package_root_id="pkg_stop_on"),
            _stop_logic_block("stopblk_off", enabled=False, package_root_id="pkg_stop_off"),
        ],
    }
    draft = await _new_draft(session, payload=payload)
    saved = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.flush()

    revision = await session.get(StrategyRevision, saved["strategy_revision_id"])
    assert revision is not None
    stops = revision.payload["protection_stop_logic"]
    assert stops.get("percentage_stop") is None  # disabled -> not in the evaluator config
    assert stops["trailing_stop"]["trail_percentage"] == "2.0"  # enabled sibling survives
    assert [block["block_id"] for block in stops["logic_blocks"]] == ["stopblk_on"]

    refs = list(await strat_repo.list_references(session, saved["strategy_revision_id"]))
    stop_refs = [r for r in refs if str(r.dependency_role) == "protection_stop_indicator"]
    assert [r.referenced_root_id for r in stop_refs] == ["pkg_stop_on"]
    assert "pkg_stop_off" not in {r.referenced_root_id for r in refs}


async def test_re_enabling_a_disabled_stop_revalidates_its_stored_value(session) -> None:
    """AT-11.c3 — the disabled stop's value is not validated while it is off, and
    not discarded either: re-enabling it revalidates the STORED value.

    The re-enable patch carries the draft's own persisted stop section with only
    ``enabled`` flipped, so the 422 can only come from the value that was already
    there — the client resupplies nothing.
    """
    await _seed_principals(session)
    payload = _valid_payload()
    payload["protection_stop_logic"] = {
        # gt 0 on PercentageStop.loss_percentage: invalid, but disabled sections
        # are filtered out BEFORE parsing (Binding Decision #2), so Save accepts it.
        "percentage_stop": {"enabled": False, "loss_percentage": "-5.0"},
        "trailing_stop": {"enabled": True, "trail_percentage": "2.0", "lock_in_percentage": "0.8"},
        "absolute_stop": None,
    }
    draft = await _new_draft(session, payload=payload)
    saved = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.flush()
    revision = await session.get(StrategyRevision, saved["strategy_revision_id"])
    assert revision is not None
    assert revision.payload["protection_stop_logic"].get("percentage_stop") is None

    stored = await strat_repo.get_strategy_draft(session, draft["draft_id"])
    assert stored is not None
    stops = dict(stored.payload["protection_stop_logic"])
    assert stops["percentage_stop"]["loss_percentage"] == "-5.0"  # the old value is kept
    stops["percentage_stop"] = {**stops["percentage_stop"], "enabled": True}
    patched = await strat_cmd.patch_strategy_draft(
        session,
        USER1,
        draft_id=draft["draft_id"],
        expected_draft_row_version=stored.row_version,
        patch={"protection_stop_logic": stops},
    )
    await session.flush()

    with pytest.raises(StrategyValidationFailedError) as exc:
        await strat_cmd.save_strategy_revision(
            session,
            USER1,
            draft_id=draft["draft_id"],
            expected_draft_row_version=patched["row_version"],
        )
    fields = {issue["field"] for issue in exc.value.details}
    assert "protection_stop_logic.percentage_stop.loss_percentage" in fields


async def test_admin_may_save_another_owners_strategy_but_supervisor_may_not(session) -> None:
    """AT-22.c3 — the GRANT half of the authorization row.

    ``ensure_can_edit`` admits Admin and nobody else across an ownership boundary,
    so both actors are driven against the SAME foreign draft in one test: the
    Supervisor (whom the criterion names alongside User) is refused, the Admin
    writes a real revision, and the root's ownership does not move under it.
    """
    await _seed_principals(session)
    await _seed_extra_principals(session)
    draft = await _new_draft(session, USER1)

    with pytest.raises(AccessDeniedError):
        await strat_cmd.save_strategy_revision(
            session, SUPERVISOR, draft_id=draft["draft_id"], expected_draft_row_version=0
        )

    saved = await strat_cmd.save_strategy_revision(
        session, ADMIN, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.flush()

    revision = await session.get(StrategyRevision, saved["strategy_revision_id"])
    assert revision is not None
    assert revision.created_by_principal == "admin_1"
    root = await session.get(EntityRegistry, draft["strategy_root_id"])
    assert root is not None and root.owner_principal_id == "user_1"  # edit, not takeover


async def test_clear_leaves_a_prior_immutable_revision_untouched(session) -> None:
    """AT-23.c3 — Clear wipes the editor draft over a root that ALREADY has a
    saved revision, and the revision, its head pointer and its dependency edges
    all survive; no Trash row is written.

    The shipped Clear test clears a draft that was never saved, so the immutable
    half of the row was never exercised.
    """
    await _seed_principals(session)
    draft = await _new_draft(session)
    saved = await strat_cmd.save_strategy_revision(
        session, USER1, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.flush()
    before = await session.get(StrategyRevision, saved["strategy_revision_id"])
    assert before is not None
    payload_before = dict(before.payload)
    ref_count_before = len(list(await strat_repo.list_references(session, before.revision_id)))

    stored = await strat_repo.get_strategy_draft(session, draft["draft_id"])
    assert stored is not None
    await strat_cmd.clear_strategy_draft(
        session,
        USER1,
        draft_id=draft["draft_id"],
        expected_draft_row_version=stored.row_version,
    )
    await session.flush()
    session.expire_all()

    after = await session.get(StrategyRevision, saved["strategy_revision_id"])
    assert after is not None
    assert after.revision_number == before.revision_number
    assert after.config_hash == saved["config_hash"]
    assert after.payload == payload_before
    assert len(list(await strat_repo.list_references(session, after.revision_id))) == (
        ref_count_before
    )

    detail = await session.get(StrategyRoot, saved["strategy_root_id"])
    assert detail is not None and detail.current_revision_id == saved["strategy_revision_id"]

    # Clear is not a delete, so it writes no Trash record for the root (doc 02 §7).
    trashed = (
        (
            await session.execute(
                select(TrashEntry).where(TrashEntry.entity_id == draft["strategy_root_id"])
            )
        )
        .scalars()
        .all()
    )
    assert trashed == []
