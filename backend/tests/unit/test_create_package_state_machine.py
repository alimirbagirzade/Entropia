"""Unit tests for the Create-Package + Pre-Check state machines (Stage 2e)."""

from __future__ import annotations

import pytest

from entropia.domain.create_package.enums import CreatePackageState, PrecheckScanStatus
from entropia.domain.create_package.state_machine import (
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
    assert (
        next_request_state(CreatePackageState.DRAFT_CREATED, CreatePackageState.APPROVED)
        == CreatePackageState.APPROVED
    )


def test_request_illegal_transitions_raise() -> None:
    # Cannot jump straight from requested to approved.
    with pytest.raises(IllegalCreatePackageTransition):
        next_request_state(CreatePackageState.REQUESTED, CreatePackageState.APPROVED)
    # Approved is terminal except for supersede.
    with pytest.raises(IllegalCreatePackageTransition):
        next_request_state(CreatePackageState.APPROVED, CreatePackageState.DRAFT_CREATED)
    with pytest.raises(IllegalCreatePackageTransition):
        next_request_state(CreatePackageState.SUPERSEDED, CreatePackageState.APPROVED)


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
