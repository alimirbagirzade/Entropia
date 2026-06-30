"""ESP resolver trust state machine (doc 09 §11.2).

Pure transition validation, mirroring ``domain/market_data/state_machine.py``.
Key invariants (doc 09):
  * Activation moves ``candidate`` -> ``trusted_active`` (Admin-only at the
    policy layer; this module only validates legality).
  * Deprecation moves ``trusted_active`` -> ``deprecated``.
  * A soft-deleted / withdrawn entry becomes ``unavailable``.
Forbidden jumps are rejected here, before any I/O.
"""

from __future__ import annotations

from entropia.domain.esp.enums import ResolverTrustState
from entropia.shared.errors import ConflictError

_ALLOWED: dict[ResolverTrustState, frozenset[ResolverTrustState]] = {
    ResolverTrustState.CANDIDATE: frozenset(
        {ResolverTrustState.TRUSTED_ACTIVE, ResolverTrustState.UNAVAILABLE}
    ),
    ResolverTrustState.TRUSTED_ACTIVE: frozenset(
        {ResolverTrustState.DEPRECATED, ResolverTrustState.UNAVAILABLE}
    ),
    ResolverTrustState.DEPRECATED: frozenset({ResolverTrustState.UNAVAILABLE}),
    ResolverTrustState.UNAVAILABLE: frozenset(),
}


class IllegalResolverTrustTransition(ConflictError):
    code = "ILLEGAL_RESOLVER_TRUST_TRANSITION"
    message = "That resolver trust state transition is not allowed."


def can_activate(current: ResolverTrustState) -> bool:
    """Activation (candidate -> trusted_active) is only legal from ``candidate``."""
    return current == ResolverTrustState.CANDIDATE


def can_deprecate(current: ResolverTrustState) -> bool:
    """Deprecation is only legal from ``trusted_active``."""
    return current == ResolverTrustState.TRUSTED_ACTIVE


def next_resolver_trust_state(
    current: ResolverTrustState, target: ResolverTrustState
) -> ResolverTrustState:
    """Validate and return the target state, or raise IllegalResolverTrustTransition."""
    if target not in _ALLOWED.get(current, frozenset()):
        raise IllegalResolverTrustTransition(
            f"Cannot move resolver trust state from '{current}' to '{target}'."
        )
    return target
