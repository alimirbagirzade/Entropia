"""Unit tests for the Create-Package + Pre-Check state machines (Stage 2e)."""

from __future__ import annotations

import pytest

from entropia.domain.create_package.enums import CreatePackageState, PrecheckScanStatus
from entropia.domain.create_package.state_machine import (
    _REQUEST_ALLOWED,
    IllegalCreatePackageTransition,
    IllegalPrecheckScanTransition,
    next_request_state,
    next_scan_status,
)


def test_request_happy_path_transitions() -> None:
    assert (
        next_request_state(CreatePackageState.REQUESTED, CreatePackageState.PRECHECK_PASSED)
        == CreatePackageState.PRECHECK_PASSED
    )
    assert (
        next_request_state(
            CreatePackageState.PRECHECK_PASSED, CreatePackageState.CANDIDATE_GENERATING
        )
        == CreatePackageState.CANDIDATE_GENERATING
    )
    assert (
        next_request_state(
            CreatePackageState.CANDIDATE_GENERATING, CreatePackageState.CANDIDATE_READY
        )
        == CreatePackageState.CANDIDATE_READY
    )
    assert (
        next_request_state(CreatePackageState.CANDIDATE_READY, CreatePackageState.DRAFT_CREATED)
        == CreatePackageState.DRAFT_CREATED
    )
    # A draft must be validated before approval (GAP-07 evidence gate).
    assert (
        next_request_state(CreatePackageState.DRAFT_CREATED, CreatePackageState.VALIDATION_RUNNING)
        == CreatePackageState.VALIDATION_RUNNING
    )
    assert (
        next_request_state(
            CreatePackageState.VALIDATION_RUNNING, CreatePackageState.ELIGIBLE_FOR_APPROVAL
        )
        == CreatePackageState.ELIGIBLE_FOR_APPROVAL
    )
    assert (
        next_request_state(CreatePackageState.ELIGIBLE_FOR_APPROVAL, CreatePackageState.APPROVED)
        == CreatePackageState.APPROVED
    )


def test_request_illegal_transitions_raise() -> None:
    # Cannot jump straight from requested to approved.
    with pytest.raises(IllegalCreatePackageTransition):
        next_request_state(CreatePackageState.REQUESTED, CreatePackageState.APPROVED)
    # A fresh draft has no evidence yet, so it cannot be approved directly (GAP-07).
    with pytest.raises(IllegalCreatePackageTransition):
        next_request_state(CreatePackageState.DRAFT_CREATED, CreatePackageState.APPROVED)
    # A failed validation run routes to revision_required, never straight to approved.
    with pytest.raises(IllegalCreatePackageTransition):
        next_request_state(CreatePackageState.REVISION_REQUIRED, CreatePackageState.APPROVED)
    # Approved is now fully terminal — the supersede edge was removed (R7).
    with pytest.raises(IllegalCreatePackageTransition):
        next_request_state(CreatePackageState.APPROVED, CreatePackageState.DRAFT_CREATED)
    with pytest.raises(IllegalCreatePackageTransition):
        next_request_state(CreatePackageState.APPROVED, CreatePackageState.ELIGIBLE_FOR_APPROVAL)


def test_experimental_and_superseded_states_are_removed() -> None:
    # R7: EXPERIMENTAL and SUPERSEDED were speculative Create-Package flow states
    # that no command ever transitioned into. Doc 06 treats "experimental" as a UI
    # label over the no-equivalence-claim approval path (already modelled by
    # claims_equivalence=False) and "superseded" as a Candidate facet — neither is
    # a request-flow state. They are deleted from the enum entirely.
    member_names = {member.name for member in CreatePackageState}
    assert "EXPERIMENTAL" not in member_names
    assert "SUPERSEDED" not in member_names


def test_approved_is_terminal() -> None:
    # With the supersede edge gone, APPROVED has no outgoing transition at all.
    assert _REQUEST_ALLOWED[CreatePackageState.APPROVED] == frozenset()
    for target in CreatePackageState:
        with pytest.raises(IllegalCreatePackageTransition):
            next_request_state(CreatePackageState.APPROVED, target)


def test_every_transition_target_is_a_live_state() -> None:
    # Defensive invariant: no edge may point at a removed/unknown state. Guards
    # against re-introducing a reference to a deleted flow state.
    members = set(CreatePackageState)
    for source, targets in _REQUEST_ALLOWED.items():
        assert source in members
        assert targets <= members


def test_scan_passes_and_stales() -> None:
    assert (
        next_scan_status(PrecheckScanStatus.NOT_CHECKED, PrecheckScanStatus.CHECKING)
        == PrecheckScanStatus.CHECKING
    )
    assert (
        next_scan_status(PrecheckScanStatus.CHECKING, PrecheckScanStatus.PASSED)
        == PrecheckScanStatus.PASSED
    )
    assert (
        next_scan_status(PrecheckScanStatus.PASSED, PrecheckScanStatus.STALE)
        == PrecheckScanStatus.STALE
    )
    # A stale scan can only be re-run, never directly re-passed.
    assert (
        next_scan_status(PrecheckScanStatus.STALE, PrecheckScanStatus.CHECKING)
        == PrecheckScanStatus.CHECKING
    )


def test_scan_illegal_transitions_raise() -> None:
    with pytest.raises(IllegalPrecheckScanTransition):
        next_scan_status(PrecheckScanStatus.PASSED, PrecheckScanStatus.PASSED)
    with pytest.raises(IllegalPrecheckScanTransition):
        next_scan_status(PrecheckScanStatus.NOT_APPLICABLE, PrecheckScanStatus.PASSED)
    with pytest.raises(IllegalPrecheckScanTransition):
        next_scan_status(PrecheckScanStatus.STALE, PrecheckScanStatus.PASSED)
