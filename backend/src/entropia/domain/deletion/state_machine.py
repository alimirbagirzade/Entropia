"""Soft-delete / restore / purge state machine (Module 3, DOMAIN_MODEL §7).

Normal delete is *only* a soft delete. Restore returns the same entity to
`active` (same entity_id, same current_revision_id, no new revision). Purge is an
Admin-only irreversible job. Forbidden jumps are rejected here, before any I/O.
"""

from __future__ import annotations

from entropia.domain.lifecycle.enums import DeletionState
from entropia.shared.errors import ConflictError

_ALLOWED: dict[DeletionState, frozenset[DeletionState]] = {
    DeletionState.ACTIVE: frozenset({DeletionState.SOFT_DELETED}),
    DeletionState.SOFT_DELETED: frozenset({DeletionState.ACTIVE, DeletionState.PURGE_PENDING}),
    DeletionState.PURGE_PENDING: frozenset({DeletionState.PURGED}),
    DeletionState.PURGED: frozenset(),
}


class IllegalDeletionTransition(ConflictError):
    code = "ILLEGAL_DELETION_TRANSITION"
    message = "That deletion-state transition is not allowed."


def can_soft_delete(current: DeletionState) -> bool:
    return current == DeletionState.ACTIVE


def can_restore(current: DeletionState) -> bool:
    # Restore is only valid from soft_deleted (never from purge_pending/purged).
    return current == DeletionState.SOFT_DELETED


def can_purge(current: DeletionState) -> bool:
    return current in (DeletionState.SOFT_DELETED, DeletionState.PURGE_PENDING)


def next_deletion_state(current: DeletionState, target: DeletionState) -> DeletionState:
    """Validate and return the target state, or raise IllegalDeletionTransition."""
    if target not in _ALLOWED.get(current, frozenset()):
        raise IllegalDeletionTransition(
            f"Cannot move deletion_state from '{current}' to '{target}'."
        )
    return target
