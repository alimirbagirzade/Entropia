"""stage 2d — Rationale Families (shared-edit families + package assignment)

Family tables (``rationale_family_root`` detail + INSERT-only
``rationale_family_revision``) hung off entity_registry, plus the
``package_rationale_assignment`` current-projection edge.

Revision ID: 0006_rationale_families
Revises: 0005_esp_packages
Create Date: 2026-06-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.rationale.enums import AssignmentTargetKind, RationaleAssignmentState
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0006_rationale_families"
down_revision: str | None = "0005_esp_packages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.create_table(
        "rationale_family_root",
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), primary_key=True),
        sa.Column("display_color", sa.String(16), nullable=False),
    )

    op.create_table(
        "rationale_family_revision",
        sa.Column("revision_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", sa.String(40), nullable=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("normalized_name", sa.String(120), nullable=False),
        sa.Column("subfamilies_json", postgresql.JSONB(), nullable=False),
        sa.Column("compatible_output_types_json", postgresql.JSONB(), nullable=False),
        sa.Column("change_note", sa.String(1024), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("entity_id", "revision_no", name="uq_rationale_family_revision_no"),
    )
    op.create_index(
        "ix_rationale_family_revision_entity_id", "rationale_family_revision", ["entity_id"]
    )
    op.create_index(
        "ix_rationale_family_revision_normalized_name",
        "rationale_family_revision",
        ["normalized_name"],
    )

    op.create_table(
        "package_rationale_assignment",
        sa.Column("assignment_id", sa.String(40), primary_key=True),
        sa.Column(
            "target_kind",
            enum_column(AssignmentTargetKind, "assignment_target_kind"),
            nullable=False,
        ),
        sa.Column("target_root_id", sa.String(40), nullable=False),
        sa.Column("target_revision_id", sa.String(40), nullable=False),
        sa.Column("rationale_family_id", sa.String(40), nullable=True),
        sa.Column("rationale_family_revision_id", sa.String(40), nullable=True),
        sa.Column("rationale_display_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column(
            "assignment_state",
            enum_column(RationaleAssignmentState, "rationale_assignment_state"),
            nullable=False,
            server_default="unassigned",
        ),
        sa.Column(
            "updated_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "target_kind", "target_root_id", name="uq_package_rationale_assignment_target"
        ),
    )
    op.create_index(
        "ix_package_rationale_assignment_target_root_id",
        "package_rationale_assignment",
        ["target_root_id"],
    )
    op.create_index(
        "ix_package_rationale_assignment_rationale_family_id",
        "package_rationale_assignment",
        ["rationale_family_id"],
    )
    op.create_index(
        "ix_package_rationale_assignment_assignment_state",
        "package_rationale_assignment",
        ["assignment_state"],
    )


def downgrade() -> None:
    op.drop_table("package_rationale_assignment")
    op.drop_table("rationale_family_revision")
    op.drop_table("rationale_family_root")
