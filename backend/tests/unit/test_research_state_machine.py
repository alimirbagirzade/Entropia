"""Research revision state-machine unit tests (doc 12 §8.2, DR2)."""

from __future__ import annotations

import pytest

from entropia.domain.research_data.enums import ResearchRevisionState as S
from entropia.domain.research_data.state_machine import (
    IllegalResearchRevisionTransition,
    can_approve,
    can_deprecate,
    can_revoke,
    can_verify,
    next_research_revision_state,
)


def test_legal_pipeline_transitions() -> None:
    assert next_research_revision_state(S.DRAFT, S.ANALYZING) == S.ANALYZING
    assert next_research_revision_state(S.ANALYZING, S.VERIFIED) == S.VERIFIED
    assert next_research_revision_state(S.ANALYZING, S.NEEDS_REVIEW) == S.NEEDS_REVIEW
    assert next_research_revision_state(S.NEEDS_REVIEW, S.VERIFIED) == S.VERIFIED
    assert next_research_revision_state(S.VERIFIED, S.APPROVED) == S.APPROVED
    assert next_research_revision_state(S.APPROVED, S.APPROVAL_REVOKED) == S.APPROVAL_REVOKED
    assert next_research_revision_state(S.APPROVED, S.DEPRECATED) == S.DEPRECATED


def test_verified_is_not_approved_only_from_verified() -> None:
    assert can_approve(S.VERIFIED)
    assert not can_approve(S.NEEDS_REVIEW)
    assert not can_approve(S.DRAFT)
    with pytest.raises(IllegalResearchRevisionTransition):
        next_research_revision_state(S.NEEDS_REVIEW, S.APPROVED)


def test_revoke_only_from_approved() -> None:
    assert can_revoke(S.APPROVED)
    assert not can_revoke(S.VERIFIED)
    with pytest.raises(IllegalResearchRevisionTransition):
        next_research_revision_state(S.VERIFIED, S.APPROVAL_REVOKED)


def test_deprecate_from_approved_and_revoked() -> None:
    assert can_deprecate(S.APPROVED)
    assert can_deprecate(S.APPROVAL_REVOKED)
    assert not can_deprecate(S.DRAFT)


def test_can_verify_from_review_paths() -> None:
    assert can_verify(S.ANALYZING)
    assert can_verify(S.NEEDS_REVIEW)
    assert not can_verify(S.DRAFT)


def test_terminal_deprecated_has_no_exit() -> None:
    with pytest.raises(IllegalResearchRevisionTransition):
        next_research_revision_state(S.DEPRECATED, S.APPROVED)
