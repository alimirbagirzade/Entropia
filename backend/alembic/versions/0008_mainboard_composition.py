"""stage 3a — Mainboard composition plane (doc 01; DOMAIN_MODEL §2.2)

Five composition-plane tables: ``mainboard_workspace`` (entity_registry detail),
``work_object_root`` (entity_registry detail), the INSERT-only immutable
``work_object_revision`` chain, the plain ``mainboard_working_item`` child of a
workspace, and the INSERT-only immutable ``mainboard_composition_snapshot``.

ENUM REUSE — ``MainboardItemKind`` is used as ``object_kind`` on both
``work_object_root`` and ``work_object_revision`` and as ``item_kind`` on
``mainboard_working_item``. ``enum_column`` builds a non-native (VARCHAR + CHECK)
column (``native_enum=False``), so reusing the same enum across multiple tables
emits NO PostgreSQL ``CREATE TYPE`` and cannot collide — identical to how 0005
reuses ``PackageKind`` across ``package_root`` and ``package_revision``.

Revision ID: 0008_mainboard_composition
Revises: 0007_create_package_precheck
Create Date: 2026-06-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.mainboard.enums import MainboardItemKind, WorkspaceKind
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0008_mainboard_composition"
down_revision: str | None = "0007_create_package_precheck"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"
_REVISION_FK = "work_object_revision.revision_id"


def upgrade() -> None:
    op.create_table(
        "mainboard_workspace",
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), primary_key=True),
        sa.Column("workspace_kind", enum_column(WorkspaceKind, "workspace_kind"), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("composition_hash", sa.String(64), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_mainboard_workspace_workspace_kind", "mainboard_workspace", ["workspace_kind"]
    )

    op.create_table(
        "work_object_root",
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), primary_key=True),
        sa.Column(
            "object_kind", enum_column(MainboardItemKind, "mainboard_item_kind"), nullable=False
        ),
    )
    op.create_index("ix_work_object_root_object_kind", "work_object_root", ["object_kind"])

    op.create_table(
        "work_object_revision",
        sa.Column("revision_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", sa.String(40), nullable=True),
        sa.Column("supersedes_revision_id", sa.String(40), nullable=True),
        sa.Column(
            "object_kind", enum_column(MainboardItemKind, "mainboard_item_kind"), nullable=False
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("source_provenance", postgresql.JSONB(), nullable=True),
        sa.Column("validation_summary", postgresql.JSONB(), nullable=True),
        sa.Column("available_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("change_note", sa.String(1024), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("entity_id", "revision_no", name="uq_work_object_revision_no"),
    )
    op.create_index("ix_work_object_revision_entity_id", "work_object_revision", ["entity_id"])
    op.create_index("ix_work_object_revision_object_kind", "work_object_revision", ["object_kind"])

    op.create_table(
        "mainboard_working_item",
        sa.Column("item_id", sa.String(40), primary_key=True),
        sa.Column("workspace_entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column(
            "item_kind", enum_column(MainboardItemKind, "mainboard_item_kind"), nullable=False
        ),
        sa.Column("work_object_root_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("pinned_revision_id", sa.String(40), sa.ForeignKey(_REVISION_FK), nullable=False),
        sa.Column("position_index", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_label_override", sa.String(255), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_principal_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_mainboard_working_item_workspace_entity_id",
        "mainboard_working_item",
        ["workspace_entity_id"],
    )

    op.create_table(
        "mainboard_composition_snapshot",
        sa.Column("snapshot_id", sa.String(40), primary_key=True),
        sa.Column("workspace_entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("composition_hash", sa.String(64), nullable=False),
        sa.Column("item_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("capital_mode_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("readiness_state", sa.String(32), nullable=False, server_default="unevaluated"),
        sa.Column("readiness_report_id", sa.String(40), nullable=True),
        sa.Column("created_by_principal_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_mainboard_composition_snapshot_workspace_entity_id",
        "mainboard_composition_snapshot",
        ["workspace_entity_id"],
    )


def downgrade() -> None:
    op.drop_table("mainboard_composition_snapshot")
    op.drop_table("mainboard_working_item")
    op.drop_table("work_object_revision")
    op.drop_table("work_object_root")
    op.drop_table("mainboard_workspace")
