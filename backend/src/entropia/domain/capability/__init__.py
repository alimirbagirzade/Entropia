"""Future Dev capability registry domain (Stage 7b, doc 22)."""

from entropia.domain.capability.enums import (
    BASELINE_CAPABILITY_KEYS,
    CAPABILITY_ENTITY_TYPE,
    GRAPHIC_VIEW,
    OPERATIONAL_STATES,
    ActivationGate,
    CapabilityState,
)
from entropia.domain.capability.lifecycle import (
    ALLOWED_TRANSITIONS,
    ensure_gates_pass,
    ensure_operational,
    ensure_transition_legal,
    gate_issues,
    parse_capability_state,
    snapshot_checksum,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "BASELINE_CAPABILITY_KEYS",
    "CAPABILITY_ENTITY_TYPE",
    "GRAPHIC_VIEW",
    "OPERATIONAL_STATES",
    "ActivationGate",
    "CapabilityState",
    "ensure_gates_pass",
    "ensure_operational",
    "ensure_transition_legal",
    "gate_issues",
    "parse_capability_state",
    "snapshot_checksum",
]
