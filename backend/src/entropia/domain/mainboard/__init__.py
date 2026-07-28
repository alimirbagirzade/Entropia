"""Mainboard composition-plane domain (doc 01; DOMAIN_MODEL §2.2).

Re-export surface only — no logic lives here.
"""

from __future__ import annotations

from entropia.domain.mainboard.composition import (
    CompositionMember,
    assert_item_kind_matches,
    composition_hash,
)
from entropia.domain.mainboard.enums import MainboardItemKind, WorkspaceKind
from entropia.domain.mainboard.item_kind import (
    LEGACY_ITEM_KIND_ALIASES,
    ensure_mainboard_item_kind,
)

__all__ = [
    "LEGACY_ITEM_KIND_ALIASES",
    "CompositionMember",
    "MainboardItemKind",
    "WorkspaceKind",
    "assert_item_kind_matches",
    "composition_hash",
    "ensure_mainboard_item_kind",
]
