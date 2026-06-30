"""Pastel display-color assignment for family cards (doc 10 §5, §6.2, §13.5).

The color is root-level presentation metadata only: persistent, stable across
rename/reload, and explicitly **not** name-hash derived and carrying no risk /
performance / owner / priority meaning. Selection rotates through a fixed pastel
palette by the count of existing family roots, then the chosen value is stored on
the root so it never changes afterwards.
"""

from __future__ import annotations

# Fixed pastel palette (doc 10 §3 "Pastel background"). Order is stable so a given
# creation ordinal always maps to the same swatch.
PASTEL_PALETTE: tuple[str, ...] = (
    "#FDE2E4",  # rose
    "#E2ECE9",  # mint
    "#FFF1E6",  # peach
    "#E2F0CB",  # sage
    "#DDE7F0",  # periwinkle
    "#F0E6FF",  # lilac
    "#FCF4DD",  # butter
    "#D8F3F0",  # aqua
)


def pick_color(existing_family_count: int) -> str:
    """Return the next pastel swatch by creation ordinal (not name-derived)."""
    return PASTEL_PALETTE[existing_family_count % len(PASTEL_PALETTE)]
