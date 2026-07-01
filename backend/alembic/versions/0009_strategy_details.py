"""stage 3b — Strategy Details typed-config plane (doc 02; DOMAIN_MODEL §2.3)

Four tables: ``strategy_root`` (entity_registry detail head pointer),
``strategy_editor_draft`` (mutable editor state), the INSERT-only immutable
``strategy_revision`` chain (typed StrategyConfig + ``config_hash``), and the
INSERT-only immutable ``strategy_revision_references`` pinned-dependency edges.

ENUM REUSE — every enum column is built via ``enum_column`` (VARCHAR + CHECK,
``native_enum=False``), so no PostgreSQL ``CREATE TYPE`` is emitted and reuse
across tables/stages cannot collide (identical to 0005/0008).

Cross-domain reference columns (``referenced_root_id`` / ``referenced_revision_id``
/ ``family_snapshot`` / ``current_revision_id`` / ``last_saved_revision_id``)
carry NO ForeignKey: their targets are heterogeneous (package/market/research
revision tables) or would create a circular root<->revision constraint. They are
pinned by id + content_hash and validated in the Save transaction.

Revision ID: 0009_strategy_details
Revises: 0008_mainboard_composition
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.strategy.enums import (
    DependencyRoleEnum,
    ReferencedEntityTypeEnum,
    StrategyLifecycleStateEnum,
    ValidationStatusEnum,
)
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0009_strategy_details"
down_revision: str | None = "0008_mainboard_composition"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"
_STRATEGY_ROOT_FK = "strategy_root.entity_id"
_STRATEGY_REVISION_FK = "strategy_revision.revision_id"


def upgrade() -> None:
    op.create_table(
        "strategy_root",
        sa.Column(
            "entity_id",
            sa.String(40),
            sa.ForeignKey(_ENTITY_FK, ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("current_revision_id", sa.String(40), nullable=True),
        sa.Column("current_row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "lifecycle_state",
            enum_column(StrategyLifecycleStateEnum, "strategy_lifecycle_state"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("rationale_family_id", sa.String(40), nullable=True),
        sa.Column(
            "created_by_principal", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=False
        ),
        sa.Column(
            "updated_by_principal", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_strategy_root_lifecycle_state", "strategy_root", ["lifecycle_state"])
    op.create_index("ix_strategy_root_display_name", "strategy_root", ["display_name"])
    op.create_index(
        "ix_strategy_root_rationale_family_id", "strategy_root", ["rationale_family_id"]
    )

    op.create_table(
        "strategy_revision",
        sa.Column("revision_id", sa.String(40), primary_key=True),
        sa.Column(
            "entity_id",
            sa.String(40),
            sa.ForeignKey(_ENTITY_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", sa.String(40), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="v1"),
        sa.Column(
            "validation_status",
            enum_column(ValidationStatusEnum, "strategy_validation_status"),
            nullable=False,
            server_default="valid",
        ),
        sa.Column("validation_errors", postgresql.JSONB(), nullable=True),
        sa.Column("lifecycle_snapshot", sa.String(48), nullable=True),
        sa.Column("family_snapshot", sa.String(40), nullable=True),
        sa.Column(
            "created_by_principal", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "entity_id", "revision_number", name="uq_strategy_revision_entity_number"
        ),
    )
    op.create_index("ix_strategy_revision_entity_id", "strategy_revision", ["entity_id"])
    op.create_index("ix_strategy_revision_config_hash", "strategy_revision", ["config_hash"])
    op.create_index(
        "ix_strategy_revision_validation_status", "strategy_revision", ["validation_status"]
    )
    op.create_index("ix_strategy_revision_created_at", "strategy_revision", ["created_at"])

    op.create_table(
        "strategy_revision_references",
        sa.Column("reference_id", sa.String(40), primary_key=True),
        sa.Column(
            "strategy_revision_id",
            sa.String(40),
            sa.ForeignKey(_STRATEGY_REVISION_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referenced_entity_type",
            enum_column(ReferencedEntityTypeEnum, "strategy_reference_entity_type"),
            nullable=False,
        ),
        sa.Column("referenced_root_id", sa.String(40), nullable=False),
        sa.Column("referenced_revision_id", sa.String(40), nullable=False),
        sa.Column("referenced_content_hash", sa.String(64), nullable=False),
        sa.Column(
            "dependency_role",
            enum_column(DependencyRoleEnum, "strategy_dependency_role"),
            nullable=False,
        ),
        sa.Column("position_in_graph", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_strategy_revision_references_strategy_revision_id",
        "strategy_revision_references",
        ["strategy_revision_id"],
    )
    op.create_index(
        "ix_strategy_revision_references_dependency_role",
        "strategy_revision_references",
        ["dependency_role"],
    )

    op.create_table(
        "strategy_editor_draft",
        sa.Column("draft_id", sa.String(40), primary_key=True),
        sa.Column(
            "strategy_root_id",
            sa.String(40),
            sa.ForeignKey(_STRATEGY_ROOT_FK, ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("last_saved_revision_id", sa.String(40), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("is_dirty", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_by_principal", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=False
        ),
        sa.Column(
            "updated_by_principal", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_strategy_editor_draft_strategy_root_id",
        "strategy_editor_draft",
        ["strategy_root_id"],
    )
    op.create_index("ix_strategy_editor_draft_updated_at", "strategy_editor_draft", ["updated_at"])


def downgrade() -> None:
    op.drop_table("strategy_editor_draft")
    op.drop_table("strategy_revision_references")
    op.drop_table("strategy_revision")
    op.drop_table("strategy_root")
