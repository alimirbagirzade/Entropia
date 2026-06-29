import pytest

from entropia.domain.deletion import (
    can_purge,
    can_restore,
    can_soft_delete,
    next_deletion_state,
)
from entropia.domain.deletion.state_machine import IllegalDeletionTransition
from entropia.domain.lifecycle.enums import DeletionState


def test_soft_delete_only_from_active() -> None:
    assert can_soft_delete(DeletionState.ACTIVE)
    assert not can_soft_delete(DeletionState.SOFT_DELETED)


def test_restore_only_from_soft_deleted() -> None:
    assert can_restore(DeletionState.SOFT_DELETED)
    assert not can_restore(DeletionState.PURGE_PENDING)
    assert not can_restore(DeletionState.PURGED)


def test_active_to_purged_is_forbidden() -> None:
    with pytest.raises(IllegalDeletionTransition):
        next_deletion_state(DeletionState.ACTIVE, DeletionState.PURGED)


def test_purged_is_terminal() -> None:
    assert not can_purge(DeletionState.PURGED)
    with pytest.raises(IllegalDeletionTransition):
        next_deletion_state(DeletionState.PURGED, DeletionState.ACTIVE)


def test_valid_chain() -> None:
    assert (
        next_deletion_state(DeletionState.ACTIVE, DeletionState.SOFT_DELETED)
        == DeletionState.SOFT_DELETED
    )
    assert (
        next_deletion_state(DeletionState.SOFT_DELETED, DeletionState.ACTIVE)
        == DeletionState.ACTIVE
    )
    assert (
        next_deletion_state(DeletionState.SOFT_DELETED, DeletionState.PURGE_PENDING)
        == DeletionState.PURGE_PENDING
    )
    assert (
        next_deletion_state(DeletionState.PURGE_PENDING, DeletionState.PURGED)
        == DeletionState.PURGED
    )
