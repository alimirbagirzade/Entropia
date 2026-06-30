"""Market dataset revision state machine (doc 11 §).

Pure transition validation, mirroring ``domain/deletion/state_machine.py``.
Key invariants (doc 11):
  * ``verified`` != ``approved``.
  * Approve is only legal from ``verified``.
  * Deprecate is only legal from ``approved``.
Forbidden jumps are rejected here, before any I/O.
"""

from __future__ import annotations

from entropia.domain.market_data.enums import MarketRevisionState
from entropia.shared.errors import ConflictError

_ALLOWED: dict[MarketRevisionState, frozenset[MarketRevisionState]] = {
    MarketRevisionState.DRAFT: frozenset(
        {MarketRevisionState.UPLOADING, MarketRevisionState.REJECTED}
    ),
    MarketRevisionState.UPLOADING: frozenset(
        {MarketRevisionState.ANALYZING, MarketRevisionState.REJECTED}
    ),
    MarketRevisionState.ANALYZING: frozenset(
        {
            MarketRevisionState.NEEDS_REVIEW,
            MarketRevisionState.VERIFIED,
            MarketRevisionState.REJECTED,
        }
    ),
    MarketRevisionState.NEEDS_REVIEW: frozenset(
        {
            MarketRevisionState.ANALYZING,
            MarketRevisionState.VERIFIED,
            MarketRevisionState.REJECTED,
        }
    ),
    MarketRevisionState.VERIFIED: frozenset(
        {
            MarketRevisionState.APPROVED,
            MarketRevisionState.REJECTED,
            MarketRevisionState.NEEDS_REVIEW,
        }
    ),
    MarketRevisionState.APPROVED: frozenset({MarketRevisionState.DEPRECATED}),
    MarketRevisionState.REJECTED: frozenset(),
    MarketRevisionState.DEPRECATED: frozenset(),
}


class IllegalMarketRevisionTransition(ConflictError):
    code = "ILLEGAL_MARKET_REVISION_TRANSITION"
    message = "That market revision state transition is not allowed."


def can_approve(current: MarketRevisionState) -> bool:
    """Approve is only legal from ``verified`` (verified != approved)."""
    return current == MarketRevisionState.VERIFIED


def can_deprecate(current: MarketRevisionState) -> bool:
    """Deprecate is only legal from ``approved``."""
    return current == MarketRevisionState.APPROVED


def can_verify(current: MarketRevisionState) -> bool:
    return MarketRevisionState.VERIFIED in _ALLOWED.get(current, frozenset())


def can_reject(current: MarketRevisionState) -> bool:
    return MarketRevisionState.REJECTED in _ALLOWED.get(current, frozenset())


def next_market_revision_state(
    current: MarketRevisionState, target: MarketRevisionState
) -> MarketRevisionState:
    """Validate and return the target state, or raise IllegalMarketRevisionTransition."""
    if target not in _ALLOWED.get(current, frozenset()):
        raise IllegalMarketRevisionTransition(
            f"Cannot move market revision state from '{current}' to '{target}'."
        )
    return target
