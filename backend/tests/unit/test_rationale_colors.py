"""Pastel color assignment (doc 10 §5, §13.5)."""

from __future__ import annotations

from entropia.domain.rationale.colors import PASTEL_PALETTE, pick_color


def test_pick_color_returns_palette_member() -> None:
    for ordinal in range(20):
        assert pick_color(ordinal) in PASTEL_PALETTE


def test_pick_color_is_stable_for_same_ordinal() -> None:
    assert pick_color(3) == pick_color(3)


def test_pick_color_rotates_through_palette() -> None:
    assert pick_color(0) != pick_color(1)
    assert pick_color(0) == pick_color(len(PASTEL_PALETTE))
