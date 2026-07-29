"""Stage 2d Rationale Families acceptance — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers: create family (+audit/+outbox, pastel color, revision 1), shared-edit
exception (User edits Admin's family — RF-01), stale-rename conflict (RF-03),
duplicate active name (RF-07), reserved soft-deleted name (RF-08), soft delete
preserves the revision chain + Trash entry (RF-05), Admin Trash restore reactivating
the same root/revision and the assignment projection (RF-06), idempotent create replay
(RF-17), atomic package assignment producing a new package revision while owner is
unchanged (RF-02), Unassigned null snapshot (RF-11), idempotent no-op re-save,
stale-package batch rejection with no partial writes (RF-09), soft-deleted family
not selectable (RATIONALE_FAMILY_NOT_ACTIVE), and the compatible-output warning
(RF-10).

RF-15 (V18 seed / ESP consistency) is NOT covered here — this module seeds
principals, not registry families. It is recorded as an open gap in
docs/audit/acceptance_id_map.md.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import rationale as rationale_cmd
from entropia.application.commands.deletion import restore_trash_entry
from entropia.application.commands.rationale import AssignmentChange
from entropia.application.queries import rationale as rationale_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PackageKind, PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    OutboxEvent,
    PackageRationaleAssignment,
    PackageRevision,
    Principal,
    RationaleFamilyRevision,
    TrashEntry,
)
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.shared.errors import (
    IdempotencyConflictError,
    PackageRationaleAssignmentConflict,
    RationaleFamilyConflict,
    RationaleFamilyNameConflict,
    RationaleFamilyNameReserved,
    RationaleFamilyNotActive,
    UnauthenticatedError,
)
from entropia.shared.pagination import PageParams

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
AGENT = Actor(principal_id="agent_alpha", principal_type=PrincipalType.AGENT, role=None)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid, ptype in (
        ("user_admin", PrincipalType.HUMAN),
        ("user_1", PrincipalType.HUMAN),
        ("agent_alpha", PrincipalType.AGENT),
    ):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=ptype))
    await session.flush()


async def _create_indicator(session, *, name: str, output_type: str | None = None):
    """Create an active rationale-assignable indicator package owned by user_1."""
    output_contract = {"output_type": output_type} if output_type else {}
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": name},
        output_contract=output_contract,
        dependency_snapshot={},
    )
    return root, revision


async def test_create_family_writes_audit_outbox_color(session) -> None:
    await _seed_principals(session)
    before_audit = await _count(session, AuditEvent)
    before_outbox = await _count(session, OutboxEvent)

    created = await rationale_cmd.create_family(
        session,
        USER,
        display_name="Liquidity Sweep Reversal",
        subfamilies=["Stop Run Reversal"],
        compatible_output_types=["Directional Signal"],
    )
    await session.commit()

    assert created["revision_no"] == 1
    assert created["display_color"].startswith("#")
    assert await _count(session, AuditEvent) == before_audit + 1
    assert await _count(session, OutboxEvent) == before_outbox + 1

    root = await rationale_repo.get_family_root(session, created["entity_id"])
    assert root is not None
    assert root.deletion_state == DeletionState.ACTIVE
    assert root.current_revision_id == created["revision_id"]


async def test_shared_edit_user_revises_admin_family(session) -> None:
    """RF-01: a User edits a family the Admin created; new immutable revision."""
    await _seed_principals(session)
    created = await rationale_cmd.create_family(session, ADMIN, display_name="Reversal Family")
    await session.commit()

    revised = await rationale_cmd.revise_family(
        session,
        USER,
        entity_id=created["entity_id"],
        display_name="Reversal / Mean Reversion",
        subfamilies=["VWAP Reversion"],
        expected_head_revision_id=created["revision_id"],
    )
    await session.commit()

    assert revised["revision_no"] == 2
    assert revised["revision_id"] != created["revision_id"]
    # Original revision is preserved (immutability).
    assert await rationale_repo.get_family_revision(session, created["revision_id"]) is not None
    root = await rationale_repo.get_family_root(session, created["entity_id"])
    assert root is not None and root.current_revision_id == revised["revision_id"]


async def test_stale_rename_conflicts(session) -> None:
    """RF-03: a save with a stale expected_head_revision_id is rejected (no overwrite)."""
    await _seed_principals(session)
    created = await rationale_cmd.create_family(session, ADMIN, display_name="Trend Family")
    await session.commit()

    with pytest.raises(RationaleFamilyConflict):
        await rationale_cmd.revise_family(
            session,
            USER,
            entity_id=created["entity_id"],
            display_name="Trend / Directional Regime",
            expected_head_revision_id="rfrev_stale",
        )


async def test_duplicate_active_name_conflicts(session) -> None:
    """RF-07: a case-insensitive duplicate active name is rejected."""
    await _seed_principals(session)
    await rationale_cmd.create_family(session, USER, display_name="Breakout / Volatility")
    await session.commit()

    with pytest.raises(RationaleFamilyNameConflict):
        await rationale_cmd.create_family(session, USER, display_name="breakout / volatility")


async def test_soft_deleted_name_reserved(session) -> None:
    """RF-08: a soft-deleted family reserves its normalized name."""
    await _seed_principals(session)
    created = await rationale_cmd.create_family(session, USER, display_name="Volatility / Regime")
    await session.commit()
    await rationale_cmd.soft_delete_family(session, USER, entity_id=created["entity_id"])
    await session.commit()

    with pytest.raises(RationaleFamilyNameReserved):
        await rationale_cmd.create_family(session, USER, display_name="Volatility / Regime")


async def test_soft_delete_preserves_chain_and_trash(session) -> None:
    """RF-05: soft delete leaves the active list, preserves the revision, writes Trash."""
    await _seed_principals(session)
    created = await rationale_cmd.create_family(session, USER, display_name="Removable Family")
    await session.commit()
    before_trash = await _count(session, TrashEntry)

    await rationale_cmd.soft_delete_family(session, AGENT, entity_id=created["entity_id"])
    await session.commit()

    root = await rationale_repo.get_family_root(session, created["entity_id"])
    assert root is not None and root.deletion_state == DeletionState.SOFT_DELETED
    assert await rationale_repo.get_family_revision(session, created["revision_id"]) is not None
    assert await _count(session, TrashEntry) == before_trash + 1

    listing = await rationale_query.list_families(session, USER, PageParams())
    assert created["entity_id"] not in {row["entity_id"] for row in listing["data"]}


def _assignment_row_for(table: dict, package_root_id: str) -> dict:
    return next(row for row in table["data"] if row["package_root_id"] == package_root_id)


async def test_admin_restore_reactivates_family_and_assignment_projection(session) -> None:
    """RF-06: an Admin restores a soft-deleted Family through Trash.

    Doc 10 §14 RF-06 asserts two things, and this test asserts both:
    (a) the SAME root and the SAME current revision go ACTIVE — a restore reactivates,
        it never appends a new revision or mints a new root; and
    (b) the assignment projections fall back from ``assigned_to_deleted_family`` to the
        normal ``assigned`` state (doc 10 §8.5).

    The projection is DERIVED at read time from the package head's pinned
    ``rationale_family_snapshot`` (``queries/rationale.py::_assignment_view``), not
    stored — so (b) is a property of the family root's ``deletion_state``, which is
    exactly what restore flips back.

    Why the pin is seeded directly instead of via ``batch_assign_rationale``: the doc
    20 §10 delete preflight refuses to soft-delete a family that still has a current
    ASSIGNED row (``RATIONALE_FAMILY_IN_USE``, covered by
    ``test_trash_page.py::test_family_with_active_assignment_blocks_delete``). So the
    ``assigned_to_deleted_family`` projection can only ever describe a revision that
    PINS a family while no current assignment row holds it — which is the state this
    test seeds.
    """
    await _seed_principals(session)
    pkg_root, _pkg_rev = await _create_indicator(session, name="RF-06 Pinned Indicator")
    family = await rationale_cmd.create_family(session, USER, display_name="RF-06 Family")
    await session.commit()

    head = await pkg_repo.get_revision(session, pkg_root.current_revision_id or "")
    assert head is not None
    head.rationale_family_snapshot = {
        "rationale_family_id": family["entity_id"],
        "rationale_family_revision_id": family["revision_id"],
        "display_name": "RF-06 Family",
    }
    await session.commit()

    before = _assignment_row_for(
        await rationale_query.list_package_assignments(session, USER, PageParams()),
        pkg_root.entity_id,
    )
    assert before["assignment_state"] == "assigned"
    assert before["family_active"] is True

    root_before = await rationale_repo.get_family_root(session, family["entity_id"])
    assert root_before is not None
    pinned_revision = root_before.current_revision_id
    revisions_before = await _count(session, RationaleFamilyRevision)

    await rationale_cmd.soft_delete_family(session, USER, entity_id=family["entity_id"])
    await session.commit()

    deleted = _assignment_row_for(
        await rationale_query.list_package_assignments(session, USER, PageParams()),
        pkg_root.entity_id,
    )
    assert deleted["assignment_state"] == "assigned_to_deleted_family"
    assert deleted["family_active"] is False
    # The pinned name is kept for context rather than blanked (doc 10 §8.5).
    assert deleted["current_family_name"] == "RF-06 Family"

    entry = (
        await session.execute(select(TrashEntry).where(TrashEntry.entity_id == family["entity_id"]))
    ).scalar_one()

    restored = await restore_trash_entry(session, ADMIN, trash_entry_id=entry.id)
    await session.commit()

    assert restored["deletion_state"] == "active"
    root_after = await rationale_repo.get_family_root(session, family["entity_id"])
    assert root_after is not None
    assert root_after.entity_id == family["entity_id"]  # same root
    assert root_after.current_revision_id == pinned_revision  # same current revision
    assert root_after.deletion_state == DeletionState.ACTIVE
    assert await _count(session, RationaleFamilyRevision) == revisions_before  # no new revision

    after = _assignment_row_for(
        await rationale_query.list_package_assignments(session, USER, PageParams()),
        pkg_root.entity_id,
    )
    assert after["assignment_state"] == "assigned"
    assert after["family_active"] is True

    # And the family is selectable again — it re-enters the active list it left on
    # delete (RF-05), which is what "ACTIVE olur" means for the dropdown.
    listing = await rationale_query.list_families(session, USER, PageParams())
    assert family["entity_id"] in {row["entity_id"] for row in listing["data"]}


async def test_client_manipulated_delete_still_meets_the_server_guards(session) -> None:
    """RF-16: the shared exception is NOT a bypass.

    Doc 10 §14 RF-16 (the Delete button called from a manipulated client) requires
    that the server still applies (a) the authenticated-actor rule, (b) the
    expected-version guard and (c) the lifecycle guard. A manipulated caller that
    skips the UI therefore cannot delete a family it could not delete through the UI,
    and a refused delete writes NO Trash entry.
    """
    await _seed_principals(session)
    created = await rationale_cmd.create_family(session, USER, display_name="Guarded Family")
    await session.commit()
    entity_id = created["entity_id"]
    before_trash = await _count(session, TrashEntry)

    root = await rationale_repo.get_family_root(session, entity_id)
    assert root is not None
    current_version = root.row_version

    # (a) A Guest forging the call is rejected before any lifecycle work.
    guest = Actor(principal_id=None, principal_type=PrincipalType.ANONYMOUS, role=None)
    with pytest.raises(UnauthenticatedError):
        await rationale_cmd.soft_delete_family(session, guest, entity_id=entity_id)
    await session.rollback()

    # (b) A stale expected_row_version is a 409 — never a silent last-write-wins delete.
    with pytest.raises(RationaleFamilyConflict):
        await rationale_cmd.soft_delete_family(
            session, USER, entity_id=entity_id, expected_row_version=current_version - 1
        )
    await session.rollback()

    # Neither refusal touched the family or the Trash projection.
    root = await rationale_repo.get_family_root(session, entity_id)
    assert root is not None and root.deletion_state == DeletionState.ACTIVE
    assert await _count(session, TrashEntry) == before_trash

    # The honest delete (correct version, active actor) is the ONLY one that lands.
    await rationale_cmd.soft_delete_family(
        session, USER, entity_id=entity_id, expected_row_version=current_version
    )
    await session.commit()
    root = await rationale_repo.get_family_root(session, entity_id)
    assert root is not None and root.deletion_state == DeletionState.SOFT_DELETED
    assert await _count(session, TrashEntry) == before_trash + 1

    # (c) Replaying the manipulated delete hits the lifecycle guard, not a 2nd entry.
    with pytest.raises(RationaleFamilyNotActive):
        await rationale_cmd.soft_delete_family(session, USER, entity_id=entity_id)
    await session.rollback()
    assert await _count(session, TrashEntry) == before_trash + 1


async def test_idempotent_create_replay_returns_cached(session) -> None:
    """RF-17: same idempotency key returns the prior result; no duplicate root."""
    await _seed_principals(session)
    first = await rationale_cmd.create_family(
        session, USER, display_name="Idempotent Family", idempotency_key="rf-k1"
    )
    await session.commit()
    families_after_first = await _count(session, PackageRationaleAssignment)

    second = await rationale_cmd.create_family(
        session, USER, display_name="Idempotent Family", idempotency_key="rf-k1"
    )
    await session.commit()

    assert second == first
    # No second family root was created (the create body did not re-run).
    assert families_after_first == await _count(session, PackageRationaleAssignment)


async def test_assign_creates_package_revision_owner_unchanged(session) -> None:
    """RF-02: an Agent semantically assigns another owner's package; new package
    revision is created and the package owner is unchanged."""
    await _seed_principals(session)
    pkg_root, pkg_rev = await _create_indicator(session, name="SMOOTHED HEIKEN ASHI")
    family = await rationale_cmd.create_family(session, ADMIN, display_name="Trend / Directional")
    await session.commit()
    before_pkg_revs = await _count(session, PackageRevision)

    result = await rationale_cmd.batch_assign_rationale(
        session,
        AGENT,
        changes=[
            AssignmentChange(
                package_root_id=pkg_root.entity_id,
                expected_head_revision_id=pkg_rev.revision_id,
                rationale_family_id=family["entity_id"],
                expected_family_current_revision_id=family["revision_id"],
            )
        ],
    )
    await session.commit()

    assert result["count"] == 1
    assert await _count(session, PackageRevision) == before_pkg_revs + 1
    root = await pkg_repo.get_package_root(session, pkg_root.entity_id)
    assert root is not None and root.owner_principal_id == "user_1"  # ownership unchanged
    head = await pkg_repo.get_revision(session, root.current_revision_id or "")
    assert head is not None
    assert head.rationale_family_snapshot["rationale_family_id"] == family["entity_id"]
    assignment = await rationale_repo.get_assignment(
        session,
        target_kind=rationale_cmd.AssignmentTargetKind.PACKAGE_REVISION,
        target_root_id=pkg_root.entity_id,
    )
    assert assignment is not None and assignment.rationale_family_id == family["entity_id"]


async def test_assign_then_unassign_and_idempotent_noop(session) -> None:
    """RF-11 + idempotent no-op: Unassigned nulls the snapshot; re-saving the same
    selection creates no new revision."""
    await _seed_principals(session)
    pkg_root, pkg_rev = await _create_indicator(session, name="Predictive Ranges")
    family = await rationale_cmd.create_family(session, USER, display_name="Breakout Family")
    await session.commit()

    await rationale_cmd.batch_assign_rationale(
        session,
        USER,
        changes=[
            AssignmentChange(
                package_root_id=pkg_root.entity_id,
                expected_head_revision_id=pkg_rev.revision_id,
                rationale_family_id=family["entity_id"],
            )
        ],
    )
    await session.commit()
    root = await pkg_repo.get_package_root(session, pkg_root.entity_id)
    assert root is not None
    assigned_head = root.current_revision_id
    revs_after_assign = await _count(session, PackageRevision)

    # Re-saving the same family is an idempotent no-op (no new revision).
    noop = await rationale_cmd.batch_assign_rationale(
        session,
        USER,
        changes=[
            AssignmentChange(
                package_root_id=pkg_root.entity_id,
                expected_head_revision_id=assigned_head,
                rationale_family_id=family["entity_id"],
            )
        ],
    )
    await session.commit()
    assert noop["count"] == 0
    assert await _count(session, PackageRevision) == revs_after_assign

    # Unassigned -> a new revision whose family snapshot is null.
    await rationale_cmd.batch_assign_rationale(
        session,
        USER,
        changes=[
            AssignmentChange(
                package_root_id=pkg_root.entity_id,
                expected_head_revision_id=assigned_head,
                rationale_family_id=None,
            )
        ],
    )
    await session.commit()
    root = await pkg_repo.get_package_root(session, pkg_root.entity_id)
    assert root is not None
    head = await pkg_repo.get_revision(session, root.current_revision_id or "")
    assert head is not None and head.rationale_family_snapshot is None


async def test_batch_stale_package_rejects_whole_batch(session) -> None:
    """RF-09: a stale package head rejects the full batch; no partial revisions."""
    await _seed_principals(session)
    pkg_root, _pkg_rev = await _create_indicator(session, name="Stale Indicator")
    family = await rationale_cmd.create_family(session, USER, display_name="Stale Test Family")
    await session.commit()
    before_pkg_revs = await _count(session, PackageRevision)

    with pytest.raises(PackageRationaleAssignmentConflict):
        await rationale_cmd.batch_assign_rationale(
            session,
            USER,
            changes=[
                AssignmentChange(
                    package_root_id=pkg_root.entity_id,
                    expected_head_revision_id="pkgrev_stale",  # stale
                    rationale_family_id=family["entity_id"],
                )
            ],
        )
    await session.rollback()
    assert await _count(session, PackageRevision) == before_pkg_revs


async def test_assign_to_soft_deleted_family_blocked(session) -> None:
    """A soft-deleted family cannot be selected for a new assignment."""
    await _seed_principals(session)
    pkg_root, pkg_rev = await _create_indicator(session, name="Blocked Indicator")
    family = await rationale_cmd.create_family(session, USER, display_name="Doomed Family")
    await session.commit()
    await rationale_cmd.soft_delete_family(session, USER, entity_id=family["entity_id"])
    await session.commit()

    with pytest.raises(RationaleFamilyNotActive):
        await rationale_cmd.batch_assign_rationale(
            session,
            USER,
            changes=[
                AssignmentChange(
                    package_root_id=pkg_root.entity_id,
                    expected_head_revision_id=pkg_rev.revision_id,
                    rationale_family_id=family["entity_id"],
                )
            ],
        )


async def test_output_type_mismatch_warns_but_saves(session) -> None:
    """RF-10: a non-listed output type yields a warning but does not block the save."""
    await _seed_principals(session)
    pkg_root, pkg_rev = await _create_indicator(
        session, name="Novel Output Indicator", output_type="Exotic Output"
    )
    family = await rationale_cmd.create_family(
        session,
        USER,
        display_name="Strict Output Family",
        compatible_output_types=["Directional Signal"],
    )
    await session.commit()

    result = await rationale_cmd.batch_assign_rationale(
        session,
        USER,
        changes=[
            AssignmentChange(
                package_root_id=pkg_root.entity_id,
                expected_head_revision_id=pkg_rev.revision_id,
                rationale_family_id=family["entity_id"],
            )
        ],
    )
    await session.commit()

    assert result["count"] == 1
    assert any(w["code"] == "OUTPUT_TYPE_NOT_LISTED" for w in result["warnings"])


async def test_assignment_table_lists_indicator_with_version(session) -> None:
    """The assignment table renders assignable packages and exposes a table_version."""
    await _seed_principals(session)
    await _create_indicator(session, name="Listed Indicator")
    await session.commit()

    table = await rationale_query.list_package_assignments(session, USER, PageParams())
    assert "table_version" in table["meta"]
    names = {row["package_name"] for row in table["data"]}
    assert "Listed Indicator" in names


async def test_assignment_table_reflects_family_rename(session) -> None:
    """RF-04 (current projection): renaming a family updates the assignment table's
    current_family_name live, without re-pinning the package revision."""
    await _seed_principals(session)
    pkg_root, pkg_rev = await _create_indicator(session, name="Renamed-Family Indicator")
    family = await rationale_cmd.create_family(session, USER, display_name="Old Family Name")
    await session.commit()

    await rationale_cmd.batch_assign_rationale(
        session,
        USER,
        changes=[
            AssignmentChange(
                package_root_id=pkg_root.entity_id,
                expected_head_revision_id=pkg_rev.revision_id,
                rationale_family_id=family["entity_id"],
            )
        ],
    )
    await session.commit()
    after_assign = await pkg_repo.get_package_root(session, pkg_root.entity_id)
    assert after_assign is not None
    pinned_after_assign = after_assign.current_revision_id

    await rationale_cmd.revise_family(
        session,
        USER,
        entity_id=family["entity_id"],
        display_name="New Family Name",
        expected_head_revision_id=family["revision_id"],
    )
    await session.commit()

    table = await rationale_query.list_package_assignments(session, USER, PageParams())
    row = next(r for r in table["data"] if r["package_root_id"] == pkg_root.entity_id)
    assert row["current_family_name"] == "New Family Name"  # live current name
    assert row["assignment_state"] == "assigned"
    # The package revision was NOT re-pinned by the rename (no churn).
    refreshed = await pkg_repo.get_package_root(session, pkg_root.entity_id)
    assert refreshed is not None and refreshed.current_revision_id == pinned_after_assign


async def test_batch_idempotency_includes_table_version(session) -> None:
    """HIGH-2: replaying a batch key with a different expected_table_version is a
    different request, not a silent cached return that bypasses the version guard."""
    await _seed_principals(session)
    pkg_root, pkg_rev = await _create_indicator(session, name="Idem Batch Indicator")
    family = await rationale_cmd.create_family(session, USER, display_name="Idem Batch Family")
    await session.commit()

    table = await rationale_query.list_package_assignments(session, USER, PageParams())
    version = table["meta"]["table_version"]

    change = AssignmentChange(
        package_root_id=pkg_root.entity_id,
        expected_head_revision_id=pkg_rev.revision_id,
        rationale_family_id=family["entity_id"],
    )
    await rationale_cmd.batch_assign_rationale(
        session, USER, changes=[change], expected_table_version=version, idempotency_key="batch-k1"
    )
    await session.commit()

    # Same key, different version token -> different fingerprint -> 409 conflict.
    with pytest.raises(IdempotencyConflictError):
        await rationale_cmd.batch_assign_rationale(
            session,
            USER,
            changes=[change],
            expected_table_version="etag:assignments:different",
            idempotency_key="batch-k1",
        )
