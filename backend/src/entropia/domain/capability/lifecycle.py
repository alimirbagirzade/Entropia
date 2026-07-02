"""Capability lifecycle state graph + activation-gate contract (doc 22 §9.1,
§9.2, §12).

Pure functions: they validate a requested transition against the fixed legal
edge set and the capability's ``dependency_snapshot`` gate record, raising the
typed doc-22 errors. Persistence/OCC live in ``application/commands/capability``.

Snapshot shape (server-side JSON, doc 22 §6):

    {"gates": {"domain": true, "data": {"complete": false, "note": "..."}, ...}}

A gate entry may be a plain boolean or an object with ``complete``; anything
else counts as incomplete. Transitions into Designed/Internal/Shadow require
every gate KEY to be present (dependency snapshot recorded, §6.1); Limited
requires all gates complete except UI; Active requires all seven (§6, §9.2 "UI
gate ... before Active release").
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from entropia.domain.capability.enums import (
    OPERATIONAL_STATES,
    ActivationGate,
    CapabilityState,
)
from entropia.shared.errors import (
    CapabilityDependencyMissingError,
    CapabilityNotActiveError,
    CapabilityTransitionRejectedError,
)

# Legal edges (doc 22 §9.1): staged forward progression, explicit rollback
# downgrades (§9.2 rollback gate), retirement only from an operational state.
# Retired is terminal — history stays read-only, no new command (FD-11).
ALLOWED_TRANSITIONS: dict[CapabilityState, frozenset[CapabilityState]] = {
    CapabilityState.PLACEHOLDER: frozenset({CapabilityState.DESIGNED}),
    CapabilityState.DESIGNED: frozenset({CapabilityState.INTERNAL}),
    CapabilityState.INTERNAL: frozenset({CapabilityState.SHADOW}),
    CapabilityState.SHADOW: frozenset({CapabilityState.LIMITED}),
    CapabilityState.LIMITED: frozenset(
        {CapabilityState.ACTIVE, CapabilityState.SHADOW, CapabilityState.RETIRED}
    ),
    CapabilityState.ACTIVE: frozenset({CapabilityState.LIMITED, CapabilityState.RETIRED}),
    CapabilityState.RETIRED: frozenset(),
}

# Targets that must carry a dependency snapshot with every gate key (§6.1);
# Placeholder itself needs only minimum metadata, Retired needs none.
SNAPSHOT_REQUIRED_TARGETS: frozenset[CapabilityState] = frozenset(
    {
        CapabilityState.DESIGNED,
        CapabilityState.INTERNAL,
        CapabilityState.SHADOW,
        CapabilityState.LIMITED,
        CapabilityState.ACTIVE,
    }
)

# Gates that must be COMPLETE for a given target state (§6, §9.2).
REQUIRED_COMPLETE_GATES: dict[CapabilityState, frozenset[ActivationGate]] = {
    CapabilityState.LIMITED: frozenset(ActivationGate) - {ActivationGate.UI},
    CapabilityState.ACTIVE: frozenset(ActivationGate),
}


def parse_capability_state(raw: str) -> CapabilityState:
    try:
        return CapabilityState(raw)
    except ValueError as exc:
        raise CapabilityTransitionRejectedError(
            f"Unknown capability lifecycle state '{raw}'.",
            details=[{"field": "to_state", "issue": "unknown_state"}],
        ) from exc


def ensure_transition_legal(from_state: CapabilityState, to_state: CapabilityState) -> None:
    """Only the fixed state graph is legal — same-state repeats included (§9.1)."""
    allowed = ALLOWED_TRANSITIONS[from_state]
    if to_state not in allowed:
        raise CapabilityTransitionRejectedError(
            f"Transition {from_state.value} -> {to_state.value} is not a legal "
            "capability lifecycle edge.",
            details=[
                {
                    "field": "to_state",
                    "issue": "illegal_transition",
                    "current_state": from_state.value,
                    "allowed_targets": sorted(state.value for state in allowed),
                }
            ],
        )


def _gate_complete(entry: Any) -> bool:
    if entry is True:
        return True
    return isinstance(entry, dict) and entry.get("complete") is True


def gate_issues(snapshot: Any, to_state: CapabilityState) -> list[dict[str, Any]]:
    """Per-gate issue list for a target state (doc 22 §12 dependency row):
    a missing gate key blocks any snapshot-carrying target; an incomplete gate
    blocks only Limited/Active. An empty list means the gates pass."""
    if to_state not in SNAPSHOT_REQUIRED_TARGETS:
        return []
    gates = snapshot.get("gates") if isinstance(snapshot, dict) else None
    if not isinstance(gates, dict):
        gates = {}
    must_complete = REQUIRED_COMPLETE_GATES.get(to_state, frozenset())
    issues: list[dict[str, Any]] = []
    for gate in ActivationGate:
        entry = gates.get(gate.value)
        if entry is None:
            issues.append({"gate": gate.value, "issue": "gate_missing"})
        elif gate in must_complete and not _gate_complete(entry):
            issues.append({"gate": gate.value, "issue": "gate_incomplete"})
    return issues


def ensure_gates_pass(snapshot: Any, to_state: CapabilityState) -> None:
    issues = gate_issues(snapshot, to_state)
    if issues:
        raise CapabilityDependencyMissingError(details=issues)


def ensure_operational(state: CapabilityState, capability_key: str) -> None:
    """Inactive operation guard (doc 22 §12, FD-02): below Limited/Active no
    job, no output, no persistent record — only CAPABILITY_NOT_ACTIVE."""
    if state not in OPERATIONAL_STATES:
        raise CapabilityNotActiveError(
            details=[{"capability_key": capability_key, "lifecycle_state": state.value}]
        )


def snapshot_checksum(snapshot: Any) -> str:
    """Deterministic sha256 over the canonical JSON form — the activation event
    keeps the snapshot hash for immutable audit (doc 22 §9, §13)."""
    canonical = json.dumps(snapshot or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "ALLOWED_TRANSITIONS",
    "REQUIRED_COMPLETE_GATES",
    "SNAPSHOT_REQUIRED_TARGETS",
    "ensure_gates_pass",
    "ensure_operational",
    "ensure_transition_legal",
    "gate_issues",
    "parse_capability_state",
    "snapshot_checksum",
]
