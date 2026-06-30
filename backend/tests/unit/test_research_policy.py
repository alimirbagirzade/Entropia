"""Research policy + value-object unit tests (doc 12 §2, §5, §8.3)."""

from __future__ import annotations

import pytest

from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.research_data import policy as rd_policy
from entropia.domain.research_data.enums import ResearchCategory, ResearchTimezoneMode
from entropia.domain.research_data.value_objects import (
    CategorySpec,
    FieldDefinition,
    ResearchTimezoneSpec,
)
from entropia.shared.errors import (
    AccessDeniedError,
    ApprovalRequiresAdmin,
    CustomCategoryRequired,
    FieldMeaningInsufficient,
    TimePolicyInvalid,
    ValidationError,
)

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
GUEST = Actor.anonymous()


def test_only_admin_can_approve_and_revoke() -> None:
    rd_policy.ensure_can_approve(ADMIN)
    rd_policy.ensure_can_revoke(ADMIN)
    for actor in (OWNER, GUEST):
        with pytest.raises(ApprovalRequiresAdmin):
            rd_policy.ensure_can_approve(actor)
        with pytest.raises(ApprovalRequiresAdmin):
            rd_policy.ensure_can_revoke(actor)


def test_owner_can_edit_draft_others_cannot() -> None:
    rd_policy.ensure_can_edit_draft(OWNER, owner_principal_id="user_1")
    rd_policy.ensure_can_edit_draft(ADMIN, owner_principal_id="user_1")
    with pytest.raises(AccessDeniedError):
        rd_policy.ensure_can_edit_draft(OTHER, owner_principal_id="user_1")
    with pytest.raises(AccessDeniedError):
        rd_policy.ensure_can_edit_draft(GUEST, owner_principal_id="user_1")


def test_view_published_allowed_private_denied_for_guest() -> None:
    rd_policy.ensure_can_view(OTHER, owner_principal_id="user_1", visibility="published")
    with pytest.raises(AccessDeniedError):
        rd_policy.ensure_can_view(GUEST, owner_principal_id="user_1", visibility="private")


def test_custom_category_required_when_other() -> None:
    with pytest.raises(CustomCategoryRequired):
        CategorySpec(category=ResearchCategory.OTHER_CUSTOM)
    spec = CategorySpec(category=ResearchCategory.OTHER_CUSTOM, custom_category="basis_spread")
    assert spec.category_key == "basis_spread"


def test_builtin_category_rejects_custom_value() -> None:
    with pytest.raises(ValidationError):
        CategorySpec(category=ResearchCategory.OPEN_INTEREST, custom_category="x")
    assert CategorySpec(category=ResearchCategory.OPEN_INTEREST).category_key == "open_interest"


def test_custom_timezone_requires_valid_iana() -> None:
    with pytest.raises(TimePolicyInvalid):
        ResearchTimezoneSpec(mode=ResearchTimezoneMode.CUSTOM)
    with pytest.raises(TimePolicyInvalid):
        ResearchTimezoneSpec(mode=ResearchTimezoneMode.CUSTOM, iana="Not/AZone")
    spec = ResearchTimezoneSpec(mode=ResearchTimezoneMode.CUSTOM, iana="America/New_York")
    assert spec.zone.key == "America/New_York"


def test_utc_timezone_rejects_iana_value() -> None:
    with pytest.raises(ValidationError):
        ResearchTimezoneSpec(mode=ResearchTimezoneMode.UTC, iana="UTC")
    assert ResearchTimezoneSpec(mode=ResearchTimezoneMode.UTC).zone.key == "UTC"


def test_field_definition_requires_full_metadata() -> None:
    with pytest.raises(FieldMeaningInsufficient):
        FieldDefinition(
            field_name="open_interest_usd",
            semantic_type="",
            measurement_method="snapshot",
            null_semantics="missing",
            event_time_source="provider",
            availability_rule="t+2m",
            allowed_usage="research",
        )
    field = FieldDefinition(
        field_name="open_interest_usd",
        semantic_type="usd_notional",
        measurement_method="provider snapshot",
        null_semantics="no data published",
        event_time_source="provider event timestamp",
        availability_rule="fixed delay 2m",
        allowed_usage="research_backtest",
        unit_or_scale="usd",
    )
    assert field.field_name == "open_interest_usd"
