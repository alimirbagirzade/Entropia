"""Rationale Families persistence tables (doc 10 §9.1, DOMAIN_MODEL §2.7).

The universal Root is the shared ``entity_registry`` (entity_type="rationale_family").
``rationale_family_root`` is a per-family detail table (PK = entity_id) carrying the
root-level ``display_color`` presentation metadata; ``rationale_family_revision`` is
the INSERT-only immutable revision chain (display name, normalized name, advisory
lists). ``package_rationale_assignment`` is the current-assignment edge/projection
(one row per target). The authoritative assignment lives on the target's immutable
package revision (``package_revision.rationale_family_snapshot``); this edge is a
read optimization kept in sync on each batch save (doc 10 §9.1 "Read optimization
only").
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.rationale.enums import AssignmentTargetKind, RationaleAssignmentState
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


class RationaleFamilyRoot(Base):
    """Per-family detail row hung off ``entity_registry`` (PK = entity_id).

    ``display_color`` is root-level presentation metadata only — stable across
    revisions/rename and never name-hash derived (doc 10 §5, §13.5). Identity,
    lifecycle, head pointer, ``row_version`` and deletion live on the registry row.
    """

    __tablename__ = "rationale_family_root"

    entity_id: Mapped[str] = mapped_column(String(40), ForeignKey(_ENTITY_FK), primary_key=True)
    display_color: Mapped[str] = mapped_column(String(16), nullable=False)


class RationaleFamilyRevision(Base):
    """Immutable per-revision snapshot of a family. Never UPDATEd."""

    __tablename__ = "rationale_family_revision"
    __table_args__ = (
        UniqueConstraint("entity_id", "revision_no", name="uq_rationale_family_revision_no"),
    )

    revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    subfamilies_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    compatible_output_types_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    change_note: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PackageRationaleAssignment(TimestampMixin, Base):
    """Current rationale-assignment projection for one target (doc 10 §9.1).

    One row per ``(target_kind, target_root_id)``. The authoritative classification
    is the pinned snapshot on the target's package revision; this edge mirrors it
    for fast table rendering and is updated whenever a batch save creates a new
    package revision. ``rationale_family_id``/``rationale_family_revision_id`` are
    null for an Unassigned target.
    """

    __tablename__ = "package_rationale_assignment"
    __table_args__ = (
        UniqueConstraint(
            "target_kind", "target_root_id", name="uq_package_rationale_assignment_target"
        ),
    )

    assignment_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    target_kind: Mapped[AssignmentTargetKind] = mapped_column(
        enum_column(AssignmentTargetKind, "assignment_target_kind"), nullable=False
    )
    target_root_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_revision_id: Mapped[str] = mapped_column(String(40), nullable=False)
    rationale_family_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    rationale_family_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rationale_display_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    assignment_state: Mapped[RationaleAssignmentState] = mapped_column(
        enum_column(RationaleAssignmentState, "rationale_assignment_state"),
        nullable=False,
        default=RationaleAssignmentState.UNASSIGNED,
        index=True,
    )
    updated_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
