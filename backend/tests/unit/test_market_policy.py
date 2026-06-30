"""Market policy + schema-mapping unit tests (doc 11 §2.2, AT #10, D7)."""

from __future__ import annotations

import pytest

from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.market_data import policy as md_policy
from entropia.domain.market_data.enums import MarketDataType
from entropia.domain.market_data.schema_mapping import (
    confirmed_mapping_is_complete,
    propose_schema_mapping,
)
from entropia.shared.errors import AccessDeniedError, ApprovalRequiresAdmin

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
GUEST = Actor.anonymous()


def test_only_admin_can_approve() -> None:
    md_policy.ensure_can_approve(ADMIN)  # no raise
    with pytest.raises(ApprovalRequiresAdmin):
        md_policy.ensure_can_approve(OWNER)
    with pytest.raises(ApprovalRequiresAdmin):
        md_policy.ensure_can_approve(GUEST)


def test_owner_can_edit_draft_others_cannot() -> None:
    md_policy.ensure_can_edit_draft(OWNER, owner_principal_id="user_1")
    md_policy.ensure_can_edit_draft(ADMIN, owner_principal_id="user_1")
    with pytest.raises(AccessDeniedError):
        md_policy.ensure_can_edit_draft(OTHER, owner_principal_id="user_1")
    with pytest.raises(AccessDeniedError):
        md_policy.ensure_can_edit_draft(GUEST, owner_principal_id="user_1")


def test_view_published_allowed_private_denied_for_other() -> None:
    md_policy.ensure_can_view(OTHER, owner_principal_id="user_1", visibility="published")
    with pytest.raises(AccessDeniedError):
        md_policy.ensure_can_view(GUEST, owner_principal_id="user_1", visibility="private")


def test_schema_mapping_auto_confirms_exact_match() -> None:
    proposal = propose_schema_mapping(
        MarketDataType.OHLCV,
        ["timestamp", "open", "high", "low", "close", "volume"],
    )
    assert proposal.review_required is False
    assert proposal.proposed["close"] == "close"
    assert proposal.proposed["volume"] == "volume"


def test_schema_mapping_synonym_match() -> None:
    proposal = propose_schema_mapping(MarketDataType.OHLCV, ["ts", "o", "h", "l", "c"])
    assert proposal.review_required is False
    assert proposal.proposed["open"] == "o"


def test_schema_mapping_missing_essential_requires_review() -> None:
    proposal = propose_schema_mapping(MarketDataType.OHLCV, ["timestamp", "open", "high"])
    assert proposal.review_required is True
    assert "low" in proposal.unmapped_fields


def test_schema_mapping_ambiguous_essential_requires_review() -> None:
    # Two columns both resolve to the same canonical "close".
    proposal = propose_schema_mapping(
        MarketDataType.OHLCV,
        ["timestamp", "open", "high", "low", "close", "last"],
    )
    assert proposal.review_required is True
    assert "close" in proposal.ambiguous_fields


def test_confirmed_mapping_completeness() -> None:
    complete = {"timestamp": "ts", "price": "p"}
    assert confirmed_mapping_is_complete(MarketDataType.TICK_TRADES, complete)
    assert not confirmed_mapping_is_complete(MarketDataType.TICK_TRADES, {"timestamp": "ts"})
