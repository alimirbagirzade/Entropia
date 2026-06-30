"""Research dataset revision state machine (doc 12 §8.2).

Pure transition validation, mirroring ``domain/market_data/state_machine.py``.
Key invariants (doc 12 §8.2, §11):
  * ``verified`` != ``approved``.
  * Approve is only legal from ``verified`` (Admin-only at the policy layer).
  * Revoke is only legal from ``approved`` (Admin-only at the policy layer).
  * Deprecate is legal from ``approved`` or ``approval_revoked``.
Forbidden jumps are rejected here, before any I/O.
"""

from __future__ import annotations

from entropia.domain.research_data.enums import ResearchRevisionState
from entropia.shared.errors import ConflictError

_ALLOWED: dict[ResearchRevisionState, frozenset[ResearchRevisionState]] = {
    ResearchRevisionState.DRAFT: frozenset({ResearchRevisionState.ANALYZING}),
    ResearchRevisionState.ANALYZING: frozenset(
        {ResearchRevisionState.NEEDS_REVIEW, ResearchRevisionState.VERIFIED}
    ),
    ResearchRevisionState.NEEDS_REVIEW: frozenset(
        {ResearchRevisionState.ANALYZING, ResearchRevisionState.VERIFIED}
    ),
    ResearchRevisionState.VERIFIED: frozenset(
        {ResearchRevisionState.APPROVED, ResearchRevisionState.NEEDS_REVIEW}
    ),
    ResearchRevisionState.APPROVED: frozenset(
        {ResearchRevisionState.DEPRECATED, ResearchRevisionState.APPROVAL_REVOKED}
    ),
    ResearchRevisionState.APPROVAL_REVOKED: frozenset({ResearchRevisionState.DEPRECATED}),
    ResearchRevisionState.DEPRECATED: frozenset(),
}


class IllegalResearchRevisionTransition(ConflictError):
    code = "ILLEGAL_RESEARCH_REVISION_TRANSITION"
    message = "That research revision state transition is not allowed."


def can_approve(current: ResearchRevisionState) -> bool:
    """Approve is only legal from ``verified`` (verified != approved)."""
    return current == ResearchRevisionState.VERIFIED


def can_revoke(current: ResearchRevisionState) -> bool:
    """Approval revocation is only legal from ``approved``."""
    return current == ResearchRevisionState.APPROVED


def can_deprecate(current: ResearchRevisionState) -> bool:
    """Deprecate is legal from ``approved`` or ``approval_revoked``."""
    return ResearchRevisionState.DEPRECATED in _ALLOWED.get(current, frozenset())


def can_verify(current: ResearchRevisionState) -> bool:
    return ResearchRevisionState.VERIFIED in _ALLOWED.get(current, frozenset())


def next_research_revision_state(
    current: ResearchRevisionState, target: ResearchRevisionState
) -> ResearchRevisionState:
    """Validate and return the target state, or raise the typed conflict."""
    if target not in _ALLOWED.get(current, frozenset()):
        raise IllegalResearchRevisionTransition(
            f"Cannot move research revision state from '{current}' to '{target}'."
        )
    return target
