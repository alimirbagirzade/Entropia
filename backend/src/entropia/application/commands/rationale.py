"""Rationale Families commands (doc 10 §7, §8, §9, §11; DOMAIN_MODEL §6).

Each command runs in one transaction supplied by the request dependency and NEVER
commits (mirrors Stage 1/2a/2b/2c). Authorization is the shared-editing exception
(``ensure_can_manage_families`` / ``ensure_can_edit_assignments``) — any
authenticated Admin/Supervisor/User/Agent, regardless of ``created_by``; Guest is
rejected. Owner policy is NOT used here.

The shape per mutation is: shared policy + pure validation (outside) -> idempotent
body { optimistic-concurrency + legality checks INSIDE (L2) -> repo mutation } ->
audit + outbox. Family rename creates a NEW immutable revision (never in-place).
Assignment save is atomic all-or-nothing: any stale/invalid row raises and rolls
back the whole batch; each changed assignment makes a new package revision and an
identical resubmit is an idempotent no-op (doc 10 §10.2).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.domain.deletion import next_deletion_state
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.rationale import (
    RATIONALE_ASSIGNABLE_PACKAGE_KINDS,
    AssignmentTargetKind,
    RationaleAssignmentState,
    clean_display_name,
    clean_metadata_list,
    ensure_can_edit_assignments,
    ensure_can_manage_families,
    normalized_name,
    pick_color,
)
from entropia.domain.trash.page import original_location_for
from entropia.infrastructure.postgres.models import EntityRegistry, PackageRevision, PackageRoot
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import (
    LifecycleBlocked,
    NotFoundError,
    PackageNotFound,
    PackageRationaleAssignmentConflict,
    RationaleFamilyConflict,
    RationaleFamilyInUseError,
    RationaleFamilyNameConflict,
    RationaleFamilyNameReserved,
    RationaleFamilyNotActive,
    ValidationError,
)

_FAMILY_TARGET_KIND = "rationale_family"
_PACKAGE_TARGET_KIND = "package"
_OUTPUT_TYPE_NOT_LISTED = "OUTPUT_TYPE_NOT_LISTED"


@dataclass(frozen=True, slots=True)
class AssignmentChange:
    """One staged row of the assignment batch (doc 10 §7.1)."""

    package_root_id: str
    expected_head_revision_id: str | None = None
    rationale_family_id: str | None = None
    expected_family_current_revision_id: str | None = None


def _audit_and_outbox(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    target_kind: str,
    entity_id: str,
    revision_id: str | None,
    previous_state: str | None = None,
    new_state: str | None = None,
    action: str,
    reason: str | None = None,
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=entity_id,
        target_entity_type=target_kind,
        target_revision_id=revision_id,
        previous_state=previous_state,
        new_state=new_state,
        reason=reason,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=target_kind,
        resource_id=entity_id,
        payload={"action": action, "revision_id": revision_id},
        correlation_id=actor.correlation_id,
    )


async def _check_name_available(
    session: AsyncSession, norm: str, *, exclude_entity_id: str | None
) -> None:
    """Map a normalized-name collision to NAME_CONFLICT (active) or NAME_RESERVED
    (soft-deleted) — doc 10 §10.1, RF-07/RF-08."""
    hit = await rationale_repo.find_active_or_reserved_by_name(
        session, norm, exclude_entity_id=exclude_entity_id
    )
    if hit is None:
        return
    root, _revision = hit
    if root.deletion_state == DeletionState.ACTIVE:
        raise RationaleFamilyNameConflict()
    raise RationaleFamilyNameReserved()


async def create_family(
    session: AsyncSession,
    actor: Actor,
    *,
    display_name: str,
    subfamilies: Sequence[str] | None = None,
    compatible_output_types: Sequence[str] | None = None,
    change_note: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create a Family root + revision 1 + persistent pastel color (doc 10 §7, §8.1).

    Validation + the shared policy run outside; uniqueness (a legality check) runs
    inside the idempotent body so a replayed key returns the cached result instead
    of a spurious NAME_CONFLICT (L2). A duplicate active name -> NAME_CONFLICT, a
    soft-deleted reserved name -> NAME_RESERVED (RF-07/RF-08/RF-17).
    """
    ensure_can_manage_families(actor)
    clean_name = clean_display_name(display_name)
    norm = normalized_name(clean_name)
    subs = clean_metadata_list(subfamilies)
    outputs = clean_metadata_list(compatible_output_types)

    async def _op() -> dict[str, Any]:
        await _check_name_available(session, norm, exclude_entity_id=None)
        color = pick_color(await rationale_repo.count_family_roots(session))
        root, _detail, revision = await rationale_repo.create_family(
            session,
            owner_principal_id=actor.principal_id,
            created_by_principal_id=actor.principal_id,
            display_name=clean_name,
            normalized_name=norm,
            subfamilies=subs,
            compatible_output_types=outputs,
            display_color=color,
            change_note=change_note,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="rationale_family.created",
            target_kind=_FAMILY_TARGET_KIND,
            entity_id=root.entity_id,
            revision_id=revision.revision_id,
            new_state="active",
            action="created",
        )
        return {
            "entity_id": root.entity_id,
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "display_name": clean_name,
            "display_color": color,
            "row_version": root.row_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "create_family", "normalized_name": norm},
        operation=_op,
    )


async def revise_family(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    display_name: str,
    subfamilies: Sequence[str] | None = None,
    compatible_output_types: Sequence[str] | None = None,
    change_note: str | None = None,
    expected_head_revision_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Append a new immutable Family revision (rename/enrich) — doc 10 §7, §8.3.

    The root id and ``display_color`` are preserved; historical snapshots are
    untouched. Optimistic concurrency on the head revision lives inside the
    idempotent body: a stale ``expected_head_revision_id`` -> RATIONALE_FAMILY_CONFLICT
    (409, RF-03). A rename to another active/deleted family's name is rejected.
    """
    ensure_can_manage_families(actor)
    clean_name = clean_display_name(display_name)
    norm = normalized_name(clean_name)
    subs = clean_metadata_list(subfamilies)
    outputs = clean_metadata_list(compatible_output_types)
    root = await _require_active_family(session, entity_id)

    async def _op() -> dict[str, Any]:
        # Refresh against committed state so the concurrency token is compared to
        # the live head, not a stale identity-map snapshot (HIGH-1).
        await session.refresh(root)
        if (
            expected_head_revision_id is not None
            and root.current_revision_id != expected_head_revision_id
        ):
            raise RationaleFamilyConflict()
        # Only re-check uniqueness when the normalized name actually changes.
        current = await rationale_repo.get_family_revision(session, root.current_revision_id or "")
        if current is None or current.normalized_name != norm:
            await _check_name_available(session, norm, exclude_entity_id=entity_id)
        revision = await rationale_repo.append_family_revision(
            session,
            root,
            display_name=clean_name,
            normalized_name=norm,
            subfamilies=subs,
            compatible_output_types=outputs,
            created_by_principal_id=actor.principal_id,
            change_note=change_note,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="rationale_family.revision_created",
            target_kind=_FAMILY_TARGET_KIND,
            entity_id=entity_id,
            revision_id=revision.revision_id,
            previous_state=expected_head_revision_id,
            new_state=revision.revision_id,
            action="revision_created",
        )
        return {
            "entity_id": entity_id,
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "display_name": clean_name,
            "row_version": root.row_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "revise_family", "entity_id": entity_id, "normalized_name": norm},
        operation=_op,
    )


async def soft_delete_family(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    expected_row_version: int | None = None,
) -> dict[str, Any]:
    """Soft-delete a shared Family (any active actor) — doc 10 §7, §8.5, RF-05/RF-16.

    Sets the registry root ``soft_deleted`` + writes a Trash entry + audit; no
    cascade delete. The soft-deleted normalized name stays reserved (the current
    revision is preserved). A stale ``expected_row_version`` -> RATIONALE_FAMILY_CONFLICT.
    """
    ensure_can_manage_families(actor)
    root = await _require_active_family(session, entity_id)
    # Row-lock + reload committed state so concurrent deletes of the same family
    # serialize: the loser re-reads soft_deleted and gets a 409 from the state
    # machine instead of writing a duplicate Trash Entry (doc 20 §14).
    await session.refresh(root, with_for_update=True)
    if expected_row_version is not None and root.row_version != expected_row_version:
        raise RationaleFamilyConflict()

    # Doc 20 §10 delete preflight: an actively-assigned family needs a repair/
    # unassign plan BEFORE it can enter Trash — no dangling assignment, and no
    # Trash Entry is written for a blocked delete (RATIONALE_FAMILY_IN_USE).
    if await rationale_repo.count_active_family_assignments(session, root.entity_id) > 0:
        raise RationaleFamilyInUseError()

    revision = await rationale_repo.get_family_revision(session, root.current_revision_id or "")
    name_snapshot = revision.display_name if revision is not None else None

    previous = root.deletion_state
    root.deletion_state = next_deletion_state(previous, DeletionState.SOFT_DELETED)
    root.deleted_by = actor.principal_id
    root.deleted_at = datetime.now(UTC)

    trash_repo.add_trash_entry(
        session,
        entity_id=root.entity_id,
        entity_type=root.entity_type,
        deleted_by=actor.principal_id,
        reason=None,
        owner_at_deletion=root.owner_principal_id,
        dependency_snapshot={
            "current_revision_id": root.current_revision_id,
            "display_name": name_snapshot,
        },
        display_name=name_snapshot,
        original_location=original_location_for(root.entity_type),
        deletion_snapshot={
            "current_revision_id": root.current_revision_id,
            "display_name": name_snapshot,
        },
        correlation_id=actor.correlation_id,
    )
    _audit_and_outbox(
        session,
        actor,
        event_kind="rationale_family.soft_deleted",
        target_kind=_FAMILY_TARGET_KIND,
        entity_id=root.entity_id,
        revision_id=root.current_revision_id,
        previous_state=str(previous),
        new_state=str(root.deletion_state),
        action="soft_deleted",
    )
    return {
        "entity_id": root.entity_id,
        "deletion_state": str(root.deletion_state),
        "display_name": name_snapshot,
    }


async def batch_assign_rationale(
    session: AsyncSession,
    actor: Actor,
    *,
    changes: Sequence[AssignmentChange],
    expected_table_version: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Atomically reclassify a set of packages (doc 10 §7, §8.4, §10.2).

    All-or-nothing: any stale/invalid row raises and the request transaction rolls
    back, so no partial Package revisions are created (RF-09). Each changed row
    creates a new immutable package revision pinning the family snapshot; an
    identical row is an idempotent no-op (RF-11). Compatible-output mismatch is a
    non-blocking OUTPUT_TYPE_NOT_LISTED warning (RF-10).
    """
    ensure_can_edit_assignments(actor)
    if not changes:
        raise ValidationError("At least one assignment change is required.")
    seen: set[str] = set()
    for change in changes:
        if change.package_root_id in seen:
            raise ValidationError(f"Duplicate package '{change.package_root_id}' in batch.")
        seen.add(change.package_root_id)

    async def _op() -> dict[str, Any]:
        if expected_table_version is not None:
            current_version = await rationale_repo.assignment_table_fingerprint(
                session, kinds=RATIONALE_ASSIGNABLE_PACKAGE_KINDS
            )
            if current_version != expected_table_version:
                raise PackageRationaleAssignmentConflict()

        created: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        for change in changes:
            applied = await _apply_assignment_change(session, actor, change)
            if applied is not None:
                created.append(applied["revision"])
                warnings.extend(applied["warnings"])

        # Flush the new package revisions before recomputing the version so the
        # returned token reflects every change in this batch (MEDIUM-5).
        await session.flush()
        new_version = await rationale_repo.assignment_table_fingerprint(
            session, kinds=RATIONALE_ASSIGNABLE_PACKAGE_KINDS
        )
        return {
            "created_revisions": created,
            "count": len(created),
            "warnings": warnings,
            "table_version": new_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        # The full change tuples AND expected_table_version are part of the
        # fingerprint: replaying the key with a different version token or row set
        # is a different request (-> fresh run or IDEMPOTENCY_KEY_CONFLICT), never a
        # silent cached return that bypasses the version guard (HIGH-2).
        request_payload={
            "op": "batch_assign_rationale",
            "expected_table_version": expected_table_version,
            "changes": [
                {
                    "package_root_id": c.package_root_id,
                    "expected_head_revision_id": c.expected_head_revision_id,
                    "rationale_family_id": c.rationale_family_id,
                    "expected_family_current_revision_id": c.expected_family_current_revision_id,
                }
                for c in changes
            ],
        },
        operation=_op,
    )


async def _apply_assignment_change(
    session: AsyncSession, actor: Actor, change: AssignmentChange
) -> dict[str, Any] | None:
    """Validate + apply one row. Returns None for an idempotent no-op, else the
    new package revision summary + any warnings. Raises (rolling back the whole
    batch) on any stale/invalid condition (doc 10 §10.2)."""
    root = await pkg_repo.get_package_root(session, change.package_root_id)
    if root is None:
        raise PackageNotFound(f"Package '{change.package_root_id}' not found.")
    if root.deletion_state != DeletionState.ACTIVE:
        raise LifecycleBlocked("This package is not active.")
    detail: PackageRoot | None = await pkg_repo.get_package_detail(session, change.package_root_id)
    if detail is None or detail.package_kind not in RATIONALE_ASSIGNABLE_PACKAGE_KINDS:
        raise LifecycleBlocked("This package type is not rationale-assignable.")
    if (
        change.expected_head_revision_id is not None
        and root.current_revision_id != change.expected_head_revision_id
    ):
        raise PackageRationaleAssignmentConflict()

    head: PackageRevision | None = await pkg_repo.get_revision(
        session, root.current_revision_id or ""
    )
    if head is None:
        raise LifecycleBlocked("This package has no current revision.")

    family_snapshot, display_snapshot, family_revision_id, warnings = await _resolve_family_target(
        session, change, head
    )

    current_family_id = (head.rationale_family_snapshot or {}).get("rationale_family_id")
    if current_family_id == change.rationale_family_id:
        return None  # idempotent no-op: same family root already assigned

    new_revision = await pkg_repo.append_package_revision(
        session,
        root,
        package_kind=detail.package_kind,
        input_contract=head.input_contract,
        output_contract=head.output_contract,
        dependency_snapshot=head.dependency_snapshot,
        rationale_family_snapshot=family_snapshot,
        validation_state=head.validation_state,
        approval_state=head.approval_state,
        change_note="Rationale reassignment.",
        created_by_principal_id=actor.principal_id,
        supersedes_revision_id=head.revision_id,
    )
    assigned = change.rationale_family_id is not None
    await rationale_repo.upsert_assignment(
        session,
        target_kind=AssignmentTargetKind.PACKAGE_REVISION,
        target_root_id=root.entity_id,
        target_revision_id=new_revision.revision_id,
        rationale_family_id=change.rationale_family_id,
        rationale_family_revision_id=family_revision_id,
        rationale_display_snapshot=display_snapshot,
        assignment_state=(
            RationaleAssignmentState.ASSIGNED if assigned else RationaleAssignmentState.UNASSIGNED
        ),
        updated_by_principal_id=actor.principal_id,
    )
    _audit_and_outbox(
        session,
        actor,
        event_kind="rationale_family.package_assigned"
        if assigned
        else "rationale_family.package_unassigned",
        target_kind=_PACKAGE_TARGET_KIND,
        entity_id=root.entity_id,
        revision_id=new_revision.revision_id,
        previous_state=current_family_id,
        new_state=change.rationale_family_id,
        action="assigned" if assigned else "unassigned",
    )
    return {
        "revision": {
            "package_root_id": root.entity_id,
            "revision_id": new_revision.revision_id,
            "rationale_family_id": change.rationale_family_id,
        },
        "warnings": warnings,
    }


async def _resolve_family_target(
    session: AsyncSession, change: AssignmentChange, head: PackageRevision
) -> tuple[dict[str, Any] | None, dict[str, str] | None, str | None, list[dict[str, Any]]]:
    """Resolve the selected family to a pinned snapshot + warnings (doc 10 §10.2).

    Unassigned -> all-null. A soft-deleted family -> RATIONALE_FAMILY_NOT_ACTIVE; a
    stale ``expected_family_current_revision_id`` -> RATIONALE_FAMILY_CONFLICT. A
    package output type not in the family's compatible list yields a non-blocking
    OUTPUT_TYPE_NOT_LISTED warning.
    """
    if change.rationale_family_id is None:
        return None, None, None, []

    family_root = await rationale_repo.get_family_root(session, change.rationale_family_id)
    if family_root is None or family_root.deletion_state != DeletionState.ACTIVE:
        raise RationaleFamilyNotActive()
    family_revision = await rationale_repo.get_family_revision(
        session, family_root.current_revision_id or ""
    )
    if family_revision is None:
        raise RationaleFamilyNotActive()
    if (
        change.expected_family_current_revision_id is not None
        and family_root.current_revision_id != change.expected_family_current_revision_id
    ):
        raise RationaleFamilyConflict()

    snapshot: dict[str, Any] = {
        "rationale_family_id": family_root.entity_id,
        "rationale_family_revision_id": family_revision.revision_id,
        "display_name": family_revision.display_name,
        "normalized_name": family_revision.normalized_name,
    }
    display_snapshot = {
        "display_name": family_revision.display_name,
        "normalized_name": family_revision.normalized_name,
    }
    warnings: list[dict[str, Any]] = []
    output_type = head.output_contract.get("output_type") or head.output_contract.get("type")
    compatible = family_revision.compatible_output_types_json or []
    if output_type and compatible and output_type not in compatible:
        warnings.append(
            {
                "code": _OUTPUT_TYPE_NOT_LISTED,
                "package_root_id": head.entity_id,
                "message": "Current output type is not listed as compatible; "
                "the assignment was saved.",
            }
        )
    return snapshot, display_snapshot, family_revision.revision_id, warnings


async def _require_active_family(session: AsyncSession, entity_id: str) -> EntityRegistry:
    root = await rationale_repo.get_family_root(session, entity_id)
    if root is None:
        raise NotFoundError(f"Rationale Family '{entity_id}' not found.")
    if root.deletion_state != DeletionState.ACTIVE:
        raise RationaleFamilyNotActive(f"Rationale Family '{entity_id}' is not active.")
    return root


__all__ = [
    "AssignmentChange",
    "batch_assign_rationale",
    "create_family",
    "revise_family",
    "soft_delete_family",
]
