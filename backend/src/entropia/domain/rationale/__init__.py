"""Rationale Families domain surface (doc 10). Re-exports only."""

from entropia.domain.rationale.colors import PASTEL_PALETTE, pick_color
from entropia.domain.rationale.enums import (
    RATIONALE_ASSIGNABLE_PACKAGE_KINDS,
    AssignmentTargetKind,
    RationaleAssignmentState,
)
from entropia.domain.rationale.names import (
    clean_display_name,
    clean_metadata_list,
    normalized_name,
)
from entropia.domain.rationale.policy import (
    ensure_can_edit_assignments,
    ensure_can_manage_families,
)

__all__ = [
    "PASTEL_PALETTE",
    "RATIONALE_ASSIGNABLE_PACKAGE_KINDS",
    "AssignmentTargetKind",
    "RationaleAssignmentState",
    "clean_display_name",
    "clean_metadata_list",
    "ensure_can_edit_assignments",
    "ensure_can_manage_families",
    "normalized_name",
    "pick_color",
]
