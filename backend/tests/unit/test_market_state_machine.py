"""Market revision state-machine unit tests (doc 11, AT #11-#13)."""

from __future__ import annotations

import pytest

from entropia.domain.market_data.enums import MarketRevisionState as S
from entropia.domain.market_data.state_machine import (
    IllegalMarketRevisionTransition,
    can_approve,
    can_deprecate,
    can_reject,
    can_verify,
    next_market_revision_state,
)


def test_approve_only_from_verified() -> None:
    assert can_approve(S.VERIFIED)
    assert not can_approve(S.ANALYZING)
    assert not can_approve(S.NEEDS_REVIEW)
    assert not can_approve(S.APPROVED)


def test_verified_is_not_approved() -> None:
    # verified != approved: the only legal way to approve is an explicit hop.
    assert next_market_revision_state(S.VERIFIED, S.APPROVED) == S.APPROVED
    with pytest.raises(IllegalMarketRevisionTransition):
        next_market_revision_state(S.NEEDS_REVIEW, S.APPROVED)


def test_deprecate_only_from_approved() -> None:
    assert can_deprecate(S.APPROVED)
    assert not can_deprecate(S.VERIFIED)
    assert next_market_revision_state(S.APPROVED, S.DEPRECATED) == S.DEPRECATED


def test_terminal_states_have_no_transitions() -> None:
    for terminal in (S.REJECTED, S.DEPRECATED):
        with pytest.raises(IllegalMarketRevisionTransition):
            next_market_revision_state(terminal, S.VERIFIED)


def test_analyzing_can_branch_to_review_or_verified() -> None:
    assert can_verify(S.ANALYZING)
    assert next_market_revision_state(S.ANALYZING, S.NEEDS_REVIEW) == S.NEEDS_REVIEW
    assert next_market_revision_state(S.ANALYZING, S.VERIFIED) == S.VERIFIED


def test_reject_reachable_from_active_states() -> None:
    for state in (S.DRAFT, S.UPLOADING, S.ANALYZING, S.NEEDS_REVIEW, S.VERIFIED):
        assert can_reject(state)


def test_draft_cannot_jump_to_approved() -> None:
    with pytest.raises(IllegalMarketRevisionTransition):
        next_market_revision_state(S.DRAFT, S.APPROVED)
