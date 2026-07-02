"""Capability Registry vocabulary (Stage 7b, doc 22 §2, §9, §9.1, §9.2).

The Capability Registry is the SERVER-SIDE source of truth for what Future Dev
may do — never a frontend feature flag, CSS hide/show or localStorage boolean
(doc 22 §2, §15). A capability below Limited/Active accepts no domain command,
starts no job and produces no persistent output (CR-09).
"""

from __future__ import annotations

from enum import StrEnum

# Trash/audit dispatch type for registry rows (registry rows are Retired, never
# Trashed — doc 22 §13; the constant exists for audit target typing only).
CAPABILITY_ENTITY_TYPE = "future_capability"

# Baseline capability keys — the fixed V18 navigation slots (doc 22 §4, §10).
LIVE_TRADE = "live_trade"
GRAPHIC_VIEW = "graphic_view"
BACKTEST_REVIEW = "backtest_review"
SIGNAL_INTELLIGENCE = "signal_intelligence"
REGIME_RESEARCH = "regime_research"
HYPOTHESIS_LAB = "hypothesis_lab"
PARAMETER_FIELDS = "parameter_fields"

BASELINE_CAPABILITY_KEYS: tuple[str, ...] = (
    LIVE_TRADE,
    GRAPHIC_VIEW,
    BACKTEST_REVIEW,
    SIGNAL_INTELLIGENCE,
    REGIME_RESEARCH,
    HYPOTHESIS_LAB,
    PARAMETER_FIELDS,
)


class CapabilityState(StrEnum):
    """Lifecycle states (doc 22 §9.1). Only LIMITED/ACTIVE are operational."""

    PLACEHOLDER = "placeholder"
    DESIGNED = "designed"
    INTERNAL = "internal"
    SHADOW = "shadow"
    LIMITED = "limited"
    ACTIVE = "active"
    RETIRED = "retired"


class ActivationGate(StrEnum):
    """The seven activation gates every Limited/Active transition must satisfy
    (doc 22 §9.2). Gate completion lives in the capability's
    ``dependency_snapshot`` — a single Admin click never bypasses them."""

    DOMAIN = "domain"
    DATA = "data"
    POLICY = "policy"
    UI = "ui"
    BACKEND = "backend"
    VERIFICATION = "verification"
    ROLLBACK = "rollback"


# States in which a capability may accept real operations (doc 22 §1, §9.1).
OPERATIONAL_STATES: frozenset[CapabilityState] = frozenset(
    {CapabilityState.LIMITED, CapabilityState.ACTIVE}
)

__all__ = [
    "BACKTEST_REVIEW",
    "BASELINE_CAPABILITY_KEYS",
    "CAPABILITY_ENTITY_TYPE",
    "GRAPHIC_VIEW",
    "HYPOTHESIS_LAB",
    "LIVE_TRADE",
    "OPERATIONAL_STATES",
    "PARAMETER_FIELDS",
    "REGIME_RESEARCH",
    "SIGNAL_INTELLIGENCE",
    "ActivationGate",
    "CapabilityState",
]
