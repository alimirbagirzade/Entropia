"""ESP (Embedded System Package) domain surface (doc 09). Re-exports only."""

from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.esp.policy import (
    ensure_can_activate,
    ensure_can_deprecate,
    ensure_can_view,
)
from entropia.domain.esp.resolver import (
    ResolutionOutcome,
    ResolutionReason,
    evaluate_resolution,
    signature_matches,
)
from entropia.domain.esp.state_machine import (
    IllegalResolverTrustTransition,
    can_activate,
    can_deprecate,
    next_resolver_trust_state,
)

__all__ = [
    "IllegalResolverTrustTransition",
    "ResolutionOutcome",
    "ResolutionReason",
    "ResolverTrustState",
    "RuntimeAdapter",
    "can_activate",
    "can_deprecate",
    "ensure_can_activate",
    "ensure_can_deprecate",
    "ensure_can_view",
    "evaluate_resolution",
    "next_resolver_trust_state",
    "signature_matches",
]
