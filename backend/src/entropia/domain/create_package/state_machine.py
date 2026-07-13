"""Create-Package flow + Pre-Check scan state machines (DOMAIN_MODEL §3.2).

Pure transition validation (no I/O), mirroring ``domain/esp/state_machine.py``.
Two orthogonal machines live here:

* ``next_request_state`` — the request's create-package flow lifecycle
  (requested → precheck_* → candidate_* → draft_created → ... → approved).
* ``next_scan_status`` — the immutable dependency-scan's own result lifecycle
  (not_checked → checking → passed|blocked|not_applicable|failed ; passed/blocked
  → stale ; stale/blocked/failed → checking on retry).

Forbidden jumps raise before any persistence; the application layer maps the
typed error to a 409.
"""

from __future__ import annotations

from entropia.domain.create_package.enums import CreatePackageState, PrecheckScanStatus
from entropia.shared.errors import ConflictError

_REQUEST_ALLOWED: dict[CreatePackageState, frozenset[CreatePackageState]] = {
    CreatePackageState.REQUESTED: frozenset(
        {
            CreatePackageState.PRECHECK_PASSED,
            CreatePackageState.PRECHECK_BLOCKED,
            CreatePackageState.PRECHECK_NOT_APPLICABLE,
            CreatePackageState.PRECHECK_FAILED,
            CreatePackageState.CANDIDATE_GENERATING,
        }
    ),
    CreatePackageState.PRECHECK_PASSED: frozenset(
        {
            CreatePackageState.PRECHECK_STALE,
            CreatePackageState.PRECHECK_BLOCKED,
            CreatePackageState.PRECHECK_PASSED,
            CreatePackageState.CANDIDATE_GENERATING,
        }
    ),
    CreatePackageState.PRECHECK_BLOCKED: frozenset(
        {
            CreatePackageState.PRECHECK_STALE,
            CreatePackageState.PRECHECK_PASSED,
            CreatePackageState.PRECHECK_BLOCKED,
        }
    ),
    CreatePackageState.PRECHECK_NOT_APPLICABLE: frozenset(
        {
            CreatePackageState.PRECHECK_PASSED,
            CreatePackageState.PRECHECK_BLOCKED,
            CreatePackageState.CANDIDATE_GENERATING,
            CreatePackageState.PRECHECK_NOT_APPLICABLE,
        }
    ),
    CreatePackageState.PRECHECK_STALE: frozenset(
        {
            CreatePackageState.PRECHECK_PASSED,
            CreatePackageState.PRECHECK_BLOCKED,
            CreatePackageState.PRECHECK_NOT_APPLICABLE,
            CreatePackageState.PRECHECK_FAILED,
        }
    ),
    CreatePackageState.PRECHECK_FAILED: frozenset(
        {
            CreatePackageState.PRECHECK_PASSED,
            CreatePackageState.PRECHECK_BLOCKED,
            CreatePackageState.PRECHECK_FAILED,
            CreatePackageState.PRECHECK_STALE,
        }
    ),
    CreatePackageState.CANDIDATE_GENERATING: frozenset(
        {CreatePackageState.CANDIDATE_READY, CreatePackageState.CANDIDATE_FAILED}
    ),
    CreatePackageState.CANDIDATE_READY: frozenset(
        {CreatePackageState.DRAFT_CREATED, CreatePackageState.CANDIDATE_GENERATING}
    ),
    CreatePackageState.CANDIDATE_FAILED: frozenset({CreatePackageState.CANDIDATE_GENERATING}),
    # A fresh draft has NO validation evidence yet, so it has no APPROVED edge: the
    # only path to approval is through a passed validation run (VALIDATION_RUNNING ->
    # ELIGIBLE_FOR_APPROVAL). This is what closes the "publish without evidence"
    # bypass (doc 06 §4.4/§7 — approval requires current validation evidence).
    CreatePackageState.DRAFT_CREATED: frozenset(
        {
            CreatePackageState.VALIDATION_RUNNING,
            CreatePackageState.ELIGIBLE_FOR_APPROVAL,
            CreatePackageState.REVISION_REQUIRED,
            CreatePackageState.REJECTED,
            CreatePackageState.CANDIDATE_GENERATING,
        }
    ),
    CreatePackageState.VALIDATION_RUNNING: frozenset(
        {
            CreatePackageState.ELIGIBLE_FOR_APPROVAL,
            CreatePackageState.REVISION_REQUIRED,
        }
    ),
    CreatePackageState.ELIGIBLE_FOR_APPROVAL: frozenset(
        {
            CreatePackageState.APPROVED,
            CreatePackageState.REJECTED,
            CreatePackageState.REVISION_REQUIRED,
        }
    ),
    CreatePackageState.REVISION_REQUIRED: frozenset({CreatePackageState.CANDIDATE_GENERATING}),
    # APPROVED is terminal: publishing a package produces a fresh Create-Package
    # request/revision, so the flow never "supersedes" an approved request in place
    # (doc 06 models supersede on the Candidate facet, not the request flow — R7).
    CreatePackageState.APPROVED: frozenset(),
    CreatePackageState.REJECTED: frozenset({CreatePackageState.CANDIDATE_GENERATING}),
}

_SCAN_ALLOWED: dict[PrecheckScanStatus, frozenset[PrecheckScanStatus]] = {
    PrecheckScanStatus.NOT_CHECKED: frozenset(
        {PrecheckScanStatus.CHECKING, PrecheckScanStatus.NOT_APPLICABLE}
    ),
    PrecheckScanStatus.CHECKING: frozenset(
        {
            PrecheckScanStatus.PASSED,
            PrecheckScanStatus.BLOCKED,
            PrecheckScanStatus.NOT_APPLICABLE,
            PrecheckScanStatus.FAILED,
        }
    ),
    PrecheckScanStatus.PASSED: frozenset({PrecheckScanStatus.STALE}),
    PrecheckScanStatus.BLOCKED: frozenset({PrecheckScanStatus.STALE, PrecheckScanStatus.CHECKING}),
    PrecheckScanStatus.NOT_APPLICABLE: frozenset({PrecheckScanStatus.CHECKING}),
    PrecheckScanStatus.FAILED: frozenset({PrecheckScanStatus.CHECKING}),
    PrecheckScanStatus.STALE: frozenset({PrecheckScanStatus.CHECKING}),
}

# Scan results that block the candidate-generation gate for a code request.
SCAN_BLOCKING_STATES: frozenset[PrecheckScanStatus] = frozenset(
    {
        PrecheckScanStatus.BLOCKED,
        PrecheckScanStatus.FAILED,
        PrecheckScanStatus.STALE,
        PrecheckScanStatus.NOT_CHECKED,
        PrecheckScanStatus.CHECKING,
    }
)


class IllegalCreatePackageTransition(ConflictError):
    code = "ILLEGAL_CREATE_PACKAGE_TRANSITION"
    message = "That create-package state transition is not allowed."


class IllegalPrecheckScanTransition(ConflictError):
    code = "ILLEGAL_PRECHECK_SCAN_TRANSITION"
    message = "That pre-check scan status transition is not allowed."


def next_request_state(
    current: CreatePackageState, target: CreatePackageState
) -> CreatePackageState:
    """Validate and return the target flow state, or raise IllegalCreatePackageTransition."""
    if target not in _REQUEST_ALLOWED.get(current, frozenset()):
        raise IllegalCreatePackageTransition(
            f"Cannot move create-package state from '{current}' to '{target}'."
        )
    return target


def next_scan_status(current: PrecheckScanStatus, target: PrecheckScanStatus) -> PrecheckScanStatus:
    """Validate and return the target scan status, or raise IllegalPrecheckScanTransition."""
    if target not in _SCAN_ALLOWED.get(current, frozenset()):
        raise IllegalPrecheckScanTransition(
            f"Cannot move pre-check scan status from '{current}' to '{target}'."
        )
    return target
