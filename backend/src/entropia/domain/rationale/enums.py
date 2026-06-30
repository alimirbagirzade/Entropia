"""Rationale Families per-domain enums (doc 10 §9, DOMAIN_MODEL §2.7, CR-04).

All values are lowercase snake_case and are returned over REST/SSE verbatim. A
Rationale Family root is *born active* and has no draft/approval flow (DOMAIN_MODEL
§3.2 "rationale family: active <-> deleted"); its removal is the generic deletion
overlay (``DeletionState``), so there is no family-specific lifecycle enum here.

``AssignmentTargetKind`` is the CR-01 target discriminator: a rationale assignment
points at a ``package_revision`` (indicator/condition/strategy/embedded_system) OR
a ``working_item_revision`` (Trading Signal / Trade Log). Trading Signal & Trade
Log are rationale-assignable WITHOUT becoming PackageKinds.
"""

from __future__ import annotations

from enum import StrEnum

from entropia.domain.lifecycle.enums import PackageKind

# V1 UI scope: only Indicator and Condition packages render in the assignment
# table (doc 10 §3.2 "Only Indicator and Condition rows render"). The model
# supports more target kinds, but the initial table must not expand scope.
RATIONALE_ASSIGNABLE_PACKAGE_KINDS: frozenset[PackageKind] = frozenset(
    {PackageKind.INDICATOR, PackageKind.CONDITION}
)


class AssignmentTargetKind(StrEnum):
    """What a Package Rationale Assignment edge points at (CR-01, doc 10 §9.1)."""

    PACKAGE_REVISION = "package_revision"
    WORKING_ITEM_REVISION = "working_item_revision"


class RationaleAssignmentState(StrEnum):
    """Current-projection state of a rationale assignment (doc 10 §9.2).

    ``assigned``: points at an ACTIVE family. ``unassigned``: explicit null family
    (valid; doc 10 §6.2 unassignedInfo). ``assigned_to_deleted_family``: the pinned
    family root was soft-deleted; the historical snapshot stays valid but the
    current projection flags it until restore/reassign (doc 10 §8.5).
    """

    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    ASSIGNED_TO_DELETED_FAMILY = "assigned_to_deleted_family"
