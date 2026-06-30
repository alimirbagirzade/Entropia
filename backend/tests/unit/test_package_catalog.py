"""Unit tests for Package Library catalog filter parsing (doc 08 §3.2, §5, §13)."""

from __future__ import annotations

import pytest

from entropia.domain.lifecycle.enums import ApprovalState, PackageKind, VisibilityScope
from entropia.domain.package.catalog import MAX_QUERY_LENGTH, UNASSIGNED, parse_catalog_filters
from entropia.domain.package.enums import PackageValidationState
from entropia.shared.errors import CatalogFilterInvalid, ClientLegacyTypeRejected


def test_parse_empty_filters_are_all_none() -> None:
    filters = parse_catalog_filters()
    assert filters.package_kind is None
    assert filters.lifecycle_state is None
    assert filters.validation_state is None
    assert filters.approval_state is None
    assert filters.visibility_scope is None
    assert filters.rationale_family_id is None
    assert filters.query is None


def test_parse_valid_facets_coerce_to_enums() -> None:
    filters = parse_catalog_filters(
        package_type="indicator",
        lifecycle_state="deprecated",
        validation_state="passed",
        approval_state="approved",
        visibility_scope="published",
        rationale_family_id="rf_reversal",
        query="  momentum  ",
    )
    assert filters.package_kind == PackageKind.INDICATOR
    assert filters.lifecycle_state == "deprecated"
    assert filters.validation_state == PackageValidationState.PASSED
    assert filters.approval_state == ApprovalState.APPROVED
    assert filters.visibility_scope == VisibilityScope.PUBLISHED
    assert filters.rationale_family_id == "rf_reversal"
    assert filters.query == "momentum"


def test_legacy_type_filter_is_rejected() -> None:
    # CR-01: trading_signal / trade_log are external objects, never packages.
    with pytest.raises(ClientLegacyTypeRejected):
        parse_catalog_filters(package_type="trading_signal")


def test_unknown_type_filter_is_rejected() -> None:
    with pytest.raises(ClientLegacyTypeRejected):
        parse_catalog_filters(package_type="not_a_type")


def test_invalid_validation_state_is_rejected() -> None:
    with pytest.raises(CatalogFilterInvalid):
        parse_catalog_filters(validation_state="bogus")


def test_invalid_approval_state_is_rejected() -> None:
    with pytest.raises(CatalogFilterInvalid):
        parse_catalog_filters(approval_state="bogus")


def test_invalid_visibility_scope_is_rejected() -> None:
    with pytest.raises(CatalogFilterInvalid):
        parse_catalog_filters(visibility_scope="bogus")


def test_non_catalog_lifecycle_state_is_rejected() -> None:
    # soft_deleted is Admin/Trash-only, never a catalog lifecycle filter.
    with pytest.raises(CatalogFilterInvalid):
        parse_catalog_filters(lifecycle_state="soft_deleted")


def test_unassigned_family_sentinel_passes_through() -> None:
    assert parse_catalog_filters(rationale_family_id=UNASSIGNED).rationale_family_id == UNASSIGNED


def test_query_is_trimmed_and_truncated() -> None:
    filters = parse_catalog_filters(query="x" * (MAX_QUERY_LENGTH + 50))
    assert filters.query is not None
    assert len(filters.query) == MAX_QUERY_LENGTH


def test_blank_query_becomes_none() -> None:
    assert parse_catalog_filters(query="   ").query is None
