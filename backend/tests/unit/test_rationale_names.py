"""Rationale Family name + metadata validation (doc 10 §5, §10.1)."""

from __future__ import annotations

import pytest

from entropia.domain.rationale.names import (
    clean_display_name,
    clean_metadata_list,
    normalized_name,
)
from entropia.shared.errors import (
    RationaleFamilyInvalidText,
    RationaleFamilyMetadataLimit,
    RationaleFamilyNameRequired,
    RationaleFamilyNameTooLong,
)


def test_trims_and_collapses_internal_whitespace() -> None:
    assert clean_display_name("  Liquidity   Sweep\tReversal  ") == "Liquidity Sweep Reversal"


def test_blank_name_rejected() -> None:
    for raw in ("", "   ", "\t\n"):
        with pytest.raises(RationaleFamilyNameRequired):
            clean_display_name(raw)


def test_single_visible_char_rejected_as_required() -> None:
    with pytest.raises(RationaleFamilyNameRequired):
        clean_display_name("A")


def test_too_long_name_rejected() -> None:
    with pytest.raises(RationaleFamilyNameTooLong):
        clean_display_name("x" * 121)


def test_control_characters_rejected() -> None:
    with pytest.raises(RationaleFamilyInvalidText):
        clean_display_name("Bad\x07Name")


def test_normalized_name_is_casefolded_and_collapsed() -> None:
    assert normalized_name("Reversal /  Mean Reversion") == "reversal / mean reversion"
    assert normalized_name("VWAP Reversion") == normalized_name("vwap reversion")


def test_metadata_list_trims_and_drops_empty() -> None:
    assert clean_metadata_list([" VWAP Reversion ", "", "  ", "Panic Reversion"]) == [
        "VWAP Reversion",
        "Panic Reversion",
    ]


def test_metadata_none_is_empty_list() -> None:
    assert clean_metadata_list(None) == []


def test_metadata_item_too_long_rejected() -> None:
    with pytest.raises(RationaleFamilyMetadataLimit):
        clean_metadata_list(["x" * 161])


def test_metadata_too_many_items_rejected() -> None:
    with pytest.raises(RationaleFamilyMetadataLimit):
        clean_metadata_list([f"item-{i}" for i in range(101)])


def test_metadata_control_char_rejected() -> None:
    with pytest.raises(RationaleFamilyInvalidText):
        clean_metadata_list(["good", "bad\x00item"])
