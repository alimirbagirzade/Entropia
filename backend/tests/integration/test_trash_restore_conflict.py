"""O-17 — restore conflict resolution contract (doc 20 §5, §6, §8.2).

Before this slice ``RestoreConflictError`` was raised BARE: the Admin got a 409
with no alternatives, so doc 20 §8.2's "the Admin may pick only from the typed
resolutions the domain adapter offers" had nothing to select from, and the §6
"Restore needs attention" panel had no ``{conflict_summary}`` to interpolate.

Locked here:

* a conflict carries its typed option set (enum + human-readable copy) and the
  root stays ``soft_deleted`` — no partial projection (doc 20 §8.2, §15);
* the read-only preflight answers the same question WITHOUT mutating anything,
  echoing the ``expected_head_revision_id`` the retry must reuse;
* a supported resolution unlocks exactly its own conflict and says so in the
  audit trail — the handler never repairs silently;
* an unknown/unsupported resolution is a 422, never a dropped field (doc 20 §5);
* ``target_missing`` offers NO resolution, and a resolution valid for a DIFFERENT
  conflict does not unlock it — the generic handler must not invent a fix.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from entropia.application.commands.deletion import restore_trash_entry, soft_delete_entity
from entropia.application.commands.entities import create_entity
from entropia.application.queries.trash import get_restore_preflight
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.domain.trash.page import TrashEntryStatus, original_location_for
from entropia.domain.trash.restore import RestoreResolution
from entropia.infrastructure.postgres.models import AuditEvent, TrashEntry
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import (
    RestoreConflictError,
    TrashAccessForbiddenError,
    UnsupportedRestoreResolutionError,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_MOVED_HEAD = "rev_moved_after_delete"


async def _soft_deleted_entry(session) -> tuple[str, str]:
    """Return (entity_id, trash_entry_id) for a freshly soft-deleted root.

    Ids are returned as plain strings on purpose: an ORM instance loaded here is
    expired by the next commit/rollback, and touching it afterwards triggers lazy
    IO outside the async greenlet context.
    """
    root = await create_entity(session, USER, entity_type="demo_entity", payload={"v": 1})
    await session.commit()
    entity_id = root.entity_id
    await soft_delete_entity(session, USER, entity_id=entity_id, reason="cleanup")
    await session.commit()
    entry = await trash_repo.get_recoverable_entry_for_entity(session, entity_id)
    assert entry is not None
    return entity_id, entry.id


async def _entry_with_moved_head(session) -> tuple[str, str]:
    """Pin the snapshot to a head the root no longer points at (doc 20 §10)."""
    entity_id, entry_id = await _soft_deleted_entry(session)
    entry = await _reload_entry(session, entry_id)
    entry.dependency_snapshot = {"current_revision_id": _MOVED_HEAD}
    await session.commit()
    return entity_id, entry_id


async def _missing_target_entry(session) -> str:
    """A Trash entry whose root left the state machine entirely."""
    trash_repo.add_trash_entry(
        session,
        entity_id="ent_vanished",
        entity_type="demo_entity",
        deleted_by=USER.principal_id,
        reason="cleanup",
        owner_at_deletion=USER.principal_id,
        dependency_snapshot={"current_revision_id": None},
        display_name="Vanished Object",
        original_location=original_location_for("demo_entity"),
        deletion_snapshot={"current_revision_id": None},
        correlation_id=None,
    )
    await session.commit()
    entry = await trash_repo.get_recoverable_entry_for_entity(session, "ent_vanished")
    assert entry is not None
    return entry.id


async def _entry_status(session, trash_entry_id: str) -> TrashEntryStatus:
    return (await _reload_entry(session, trash_entry_id)).status


async def _root(session, entity_id: str):
    from entropia.infrastructure.postgres.repositories import entities as entity_repo

    root = await entity_repo.get_root(session, entity_id)
    assert root is not None
    return root


async def _reload_entry(session, trash_entry_id: str) -> TrashEntry:
    entry = await trash_repo.get_entry(session, trash_entry_id)
    assert entry is not None
    return entry


# --------------------------------------------------------------------------- #
# The 409 now carries its alternatives (doc 20 §6, §8.2)                       #
# --------------------------------------------------------------------------- #


async def test_restore_conflict_carries_typed_resolution_options(session) -> None:
    entity_id, entry_id = await _entry_with_moved_head(session)

    with pytest.raises(RestoreConflictError) as raised:
        await restore_trash_entry(session, ADMIN, trash_entry_id=entry_id)
    await session.rollback()

    error = raised.value
    assert error.code == "RESTORE_CONFLICT"
    assert error.http_status == 409
    # message IS the {conflict_summary} doc 20 §6 interpolates into the panel,
    # and it names BOTH heads so the Admin can see what actually moved.
    assert "revision pointer moved" in error.message
    assert _MOVED_HEAD in error.message
    # The typed option set — enum value + human-readable copy (doc 20 §5).
    assert [option["resolution"] for option in error.details] == [
        RestoreResolution.RESTORE_AT_CURRENT_HEAD
    ]
    option = error.details[0]
    assert option["conflict_kind"] == "head_pointer_moved"
    assert option["label"] and option["description"]
    assert error.remediation is not None
    assert error.scope_id == entity_id

    # No partial projection: the root and the entry both stay soft-deleted.
    assert await _entry_status(session, entry_id) == TrashEntryStatus.SOFT_DELETED
    assert (await _root(session, entity_id)).deletion_state == DeletionState.SOFT_DELETED


# --------------------------------------------------------------------------- #
# Preflight is a separate READ path (doc 20 §5 "typed enum from preflight")    #
# --------------------------------------------------------------------------- #


async def test_restore_conflict_preflight_reports_typed_options_without_mutating(session) -> None:
    entity_id, entry_id = await _entry_with_moved_head(session)

    preflight = await get_restore_preflight(session, ADMIN, trash_entry_id=entry_id)

    assert preflight["outcome"] == "conflict"
    assert preflight["conflict_kind"] == "head_pointer_moved"
    assert _MOVED_HEAD in preflight["conflict_summary"]
    assert [option["resolution"] for option in preflight["resolutions"]] == [
        RestoreResolution.RESTORE_AT_CURRENT_HEAD
    ]
    # The retry reuses the SAME expected deletion version the Admin reviewed.
    assert (
        preflight["expected_head_revision_id"]
        == (await _reload_entry(session, entry_id)).row_version
    )

    # Read-only: nothing moved.
    assert await _entry_status(session, entry_id) == TrashEntryStatus.SOFT_DELETED
    assert (await _root(session, entity_id)).deletion_state == DeletionState.SOFT_DELETED


async def test_restore_conflict_preflight_allows_a_clean_entry(session) -> None:
    _, entry_id = await _soft_deleted_entry(session)

    preflight = await get_restore_preflight(session, ADMIN, trash_entry_id=entry_id)

    assert preflight["outcome"] == "allow"
    assert preflight["conflict_kind"] is None
    assert preflight["blocked_reason"] is None
    assert preflight["resolutions"] == []


async def test_restore_conflict_preflight_is_admin_only(session) -> None:
    _, entry_id = await _soft_deleted_entry(session)

    with pytest.raises(TrashAccessForbiddenError):
        await get_restore_preflight(session, USER, trash_entry_id=entry_id)


# --------------------------------------------------------------------------- #
# A supported resolution unlocks its own conflict — and is recorded            #
# --------------------------------------------------------------------------- #


async def test_restore_conflict_supported_resolution_unlocks_and_audits(session) -> None:
    entity_id, entry_id = await _entry_with_moved_head(session)

    result = await restore_trash_entry(
        session,
        ADMIN,
        trash_entry_id=entry_id,
        resolution=str(RestoreResolution.RESTORE_AT_CURRENT_HEAD),
    )
    await session.commit()

    assert result["deletion_state"] == "active"
    assert result["applied_resolution"] == RestoreResolution.RESTORE_AT_CURRENT_HEAD
    assert (await _root(session, entity_id)).deletion_state == DeletionState.ACTIVE

    # The trail records that a HUMAN adopted the non-default outcome.
    metadata = (
        await session.execute(
            select(AuditEvent.event_metadata).where(
                AuditEvent.target_entity_id == entity_id,
                AuditEvent.event_kind == "trash.restored",
            )
        )
    ).scalar_one()
    assert metadata == {"restore_resolution": "restore_at_current_head"}


async def test_restore_conflict_clean_restore_records_no_resolution(session) -> None:
    entity_id, entry_id = await _soft_deleted_entry(session)

    result = await restore_trash_entry(session, ADMIN, trash_entry_id=entry_id)
    await session.commit()

    # Nothing was resolved because nothing conflicted — the field stays honest.
    assert result["applied_resolution"] is None
    metadata = (
        await session.execute(
            select(AuditEvent.event_metadata).where(
                AuditEvent.target_entity_id == entity_id,
                AuditEvent.event_kind == "trash.restored",
            )
        )
    ).scalar_one()
    assert metadata is None


# --------------------------------------------------------------------------- #
# No silent repair: unknown -> 422; target_missing offers nothing              #
# --------------------------------------------------------------------------- #


async def test_restore_conflict_unknown_resolution_is_422(session) -> None:
    entity_id, entry_id = await _entry_with_moved_head(session)

    with pytest.raises(UnsupportedRestoreResolutionError) as raised:
        await restore_trash_entry(
            session, ADMIN, trash_entry_id=entry_id, resolution="just_fix_it_somehow"
        )
    await session.rollback()

    error = raised.value
    assert error.code == "UNSUPPORTED_RESTORE_RESOLUTION"
    assert error.http_status == 422
    assert error.field_path == "resolution"
    # The rejection names what IS supported instead of silently dropping the field.
    assert error.details[0]["supported"] == [str(RestoreResolution.RESTORE_AT_CURRENT_HEAD)]

    assert await _entry_status(session, entry_id) == TrashEntryStatus.SOFT_DELETED
    assert (await _root(session, entity_id)).deletion_state == DeletionState.SOFT_DELETED


async def test_restore_conflict_empty_resolution_string_is_422(session) -> None:
    _, entry_id = await _soft_deleted_entry(session)

    # Fail-closed: an empty token is not "no resolution supplied".
    with pytest.raises(UnsupportedRestoreResolutionError):
        await restore_trash_entry(session, ADMIN, trash_entry_id=entry_id, resolution="")
    await session.rollback()
    assert await _entry_status(session, entry_id) == TrashEntryStatus.SOFT_DELETED


async def test_restore_conflict_target_missing_offers_no_resolution(session) -> None:
    entry_id = await _missing_target_entry(session)

    with pytest.raises(RestoreConflictError) as raised:
        await restore_trash_entry(session, ADMIN, trash_entry_id=entry_id)
    await session.rollback()

    error = raised.value
    # An EMPTY option set is a real answer: nothing can honestly unblock this.
    assert error.details == []
    assert "no longer resolvable" in error.message
    assert "No supported resolution" in (error.remediation or "")

    preflight = await get_restore_preflight(session, ADMIN, trash_entry_id=entry_id)
    assert preflight["outcome"] == "conflict"
    assert preflight["conflict_kind"] == "target_missing"
    assert preflight["resolutions"] == []


async def test_restore_conflict_resolution_for_another_conflict_does_not_unlock(session) -> None:
    """A KNOWN resolution is not a master key — it unlocks only its own conflict."""
    entry_id = await _missing_target_entry(session)

    with pytest.raises(RestoreConflictError) as raised:
        await restore_trash_entry(
            session,
            ADMIN,
            trash_entry_id=entry_id,
            resolution=str(RestoreResolution.RESTORE_AT_CURRENT_HEAD),
        )
    await session.rollback()

    assert raised.value.details == []
    assert await _entry_status(session, entry_id) == TrashEntryStatus.SOFT_DELETED
