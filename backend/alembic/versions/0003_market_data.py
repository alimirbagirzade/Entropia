"""stage 2a — market data + generic approval-decision tables

Per-domain market dataset revisions, raw/processed assets, schema mapping,
validation runs/issues, coverage slices (all hung off entity_registry), plus the
generic approval_decision table reused by later stages.

Revision ID: 0003_market_data
Revises: 0002_stage1
Create Date: 2026-06-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.lifecycle.enums import ApprovalState, ValidationStatus
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    RecordTimeBasis,
    ResolutionKind,
    TimezoneMode,
)
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0003_market_data"
down_revision: str | None = "0002_stage1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.create_table(
        "market_dataset_revision",
        sa.Column("revision_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", sa.String(40), nullable=True),
        sa.Column("supersedes_revision_id", sa.String(40), nullable=True),
        sa.Column(
            "market_data_type", enum_column(MarketDataType, "market_data_type"), nullable=False
        ),
        sa.Column(
            "revision_state",
            enum_column(MarketRevisionState, "market_revision_state"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "validation_status", enum_column(ValidationStatus, "validation_status"), nullable=True
        ),
        sa.Column("resolution_kind", enum_column(ResolutionKind, "resolution_kind"), nullable=True),
        sa.Column("resolution_value", sa.String(32), nullable=True),
        sa.Column("timezone_mode", enum_column(TimezoneMode, "timezone_mode"), nullable=True),
        sa.Column("timezone_iana", sa.String(64), nullable=True),
        sa.Column(
            "record_time_basis", enum_column(RecordTimeBasis, "record_time_basis"), nullable=True
        ),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("instrument_id", sa.String(128), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("entity_id", "revision_no", name="uq_market_dataset_revision_no"),
    )
    op.create_index(
        "ix_market_dataset_revision_entity_id", "market_dataset_revision", ["entity_id"]
    )
    op.create_index(
        "ix_market_dataset_revision_state", "market_dataset_revision", ["revision_state"]
    )

    op.create_table(
        "market_raw_asset",
        sa.Column("asset_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=True),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("original_filename", sa.String(512), nullable=True),
        sa.Column(
            "uploaded_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_market_raw_asset_entity_id", "market_raw_asset", ["entity_id"])
    op.create_index("ix_market_raw_asset_revision_id", "market_raw_asset", ["revision_id"])
    op.create_index("ix_market_raw_asset_content_digest", "market_raw_asset", ["content_digest"])

    op.create_table(
        "market_processed_asset",
        sa.Column("asset_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=True),
        sa.Column("raw_asset_id", sa.String(40), nullable=True),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("schema_descriptor", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_market_processed_asset_entity_id", "market_processed_asset", ["entity_id"])
    op.create_index(
        "ix_market_processed_asset_revision_id", "market_processed_asset", ["revision_id"]
    )
    op.create_index(
        "ix_market_processed_asset_content_digest",
        "market_processed_asset",
        ["content_digest"],
    )

    op.create_table(
        "market_schema_mapping",
        sa.Column("mapping_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=True),
        sa.Column(
            "market_data_type", enum_column(MarketDataType, "market_data_type"), nullable=False
        ),
        sa.Column("mapping_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("proposed_mapping", postgresql.JSONB(), nullable=False),
        sa.Column("confirmed_mapping", postgresql.JSONB(), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "confirmed_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_market_schema_mapping_entity_id", "market_schema_mapping", ["entity_id"])
    op.create_index(
        "ix_market_schema_mapping_revision_id", "market_schema_mapping", ["revision_id"]
    )

    op.create_table(
        "market_validation_run",
        sa.Column("run_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=True),
        sa.Column("job_id", sa.String(40), nullable=True),
        sa.Column("status", enum_column(ValidationStatus, "validation_status"), nullable=False),
        sa.Column("rows_checked", sa.BigInteger(), nullable=True),
        sa.Column("summary", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_market_validation_run_entity_id", "market_validation_run", ["entity_id"])
    op.create_index(
        "ix_market_validation_run_revision_id", "market_validation_run", ["revision_id"]
    )

    op.create_table(
        "market_validation_issue",
        sa.Column("issue_id", sa.String(40), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(40),
            sa.ForeignKey("market_validation_run.run_id"),
            nullable=False,
        ),
        sa.Column("severity", enum_column(ValidationStatus, "validation_status"), nullable=False),
        sa.Column("rule_code", sa.String(96), nullable=False),
        sa.Column("message", sa.String(1024), nullable=False),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sample", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_market_validation_issue_run_id", "market_validation_issue", ["run_id"])

    op.create_table(
        "dataset_coverage_slice",
        sa.Column("slice_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("gap_seconds", sa.Numeric(20, 6), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_dataset_coverage_slice_entity_id", "dataset_coverage_slice", ["entity_id"])
    op.create_index(
        "ix_dataset_coverage_slice_revision_id", "dataset_coverage_slice", ["revision_id"]
    )

    op.create_table(
        "approval_decision",
        sa.Column("decision_id", sa.String(40), primary_key=True),
        sa.Column("target_entity_id", sa.String(40), nullable=False),
        sa.Column("target_revision_id", sa.String(40), nullable=True),
        sa.Column("target_kind", sa.String(64), nullable=False),
        sa.Column(
            "decision", enum_column(ApprovalState, "approval_decision_state"), nullable=False
        ),
        sa.Column(
            "approver_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("prior_state", sa.String(48), nullable=True),
        sa.Column("new_state", sa.String(48), nullable=True),
        sa.Column("note", sa.String(1024), nullable=True),
        sa.Column("policy_context", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_approval_decision_target_entity_id", "approval_decision", ["target_entity_id"]
    )
    op.create_index(
        "ix_approval_decision_target_revision_id", "approval_decision", ["target_revision_id"]
    )


def downgrade() -> None:
    op.drop_table("approval_decision")
    op.drop_table("dataset_coverage_slice")
    op.drop_table("market_validation_issue")
    op.drop_table("market_validation_run")
    op.drop_table("market_schema_mapping")
    op.drop_table("market_processed_asset")
    op.drop_table("market_raw_asset")
    op.drop_table("market_dataset_revision")
