"""stage 2b — research data tables

Per-domain research dataset revisions, raw/native assets, field/feature
definitions, time policy, immutable market link, validation runs/issues (all hung
off entity_registry). Revisions are INSERT-only; native payload preserves
category-specific fields (never coerced to OHLCV).

Revision ID: 0004_research_data
Revises: 0003_market_data
Create Date: 2026-06-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    EventTimeSemantics,
    FrequencyPolicy,
    ResearchRevisionState,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0004_research_data"
down_revision: str | None = "0003_market_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.create_table(
        "research_dataset_revision",
        sa.Column("revision_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", sa.String(40), nullable=True),
        sa.Column("base_revision_id", sa.String(40), nullable=True),
        sa.Column("supersedes_revision_id", sa.String(40), nullable=True),
        sa.Column(
            "revision_state",
            enum_column(ResearchRevisionState, "research_revision_state"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "validation_status", enum_column(ValidationStatus, "validation_status"), nullable=True
        ),
        sa.Column("display_name", sa.String(256), nullable=True),
        sa.Column("category_key", sa.String(128), nullable=True),
        sa.Column("custom_category", sa.String(256), nullable=True),
        sa.Column("provider_name", sa.String(256), nullable=True),
        sa.Column("raw_asset_id", sa.String(40), nullable=True),
        sa.Column("native_asset_id", sa.String(40), nullable=True),
        sa.Column("native_schema_descriptor", postgresql.JSONB(), nullable=True),
        sa.Column("field_definition_version", sa.Integer(), nullable=True),
        sa.Column("linked_market_dataset_revision_id", sa.String(40), nullable=True),
        sa.Column("instrument_mapping_ref", sa.String(256), nullable=True),
        sa.Column(
            "event_time_semantics",
            enum_column(EventTimeSemantics, "event_time_semantics"),
            nullable=True,
        ),
        sa.Column(
            "available_time_policy",
            enum_column(AvailableTimePolicy, "available_time_policy"),
            nullable=True,
        ),
        sa.Column("available_delay_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "frequency_policy", enum_column(FrequencyPolicy, "frequency_policy"), nullable=True
        ),
        sa.Column(
            "source_timezone_mode",
            enum_column(ResearchTimezoneMode, "research_timezone_mode"),
            nullable=True,
        ),
        sa.Column("source_timezone_iana", sa.String(64), nullable=True),
        sa.Column("usage_scope", enum_column(UsageScope, "research_usage_scope"), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=True),
        sa.Column("parser_version", sa.String(64), nullable=True),
        sa.Column("validation_policy_version", sa.String(64), nullable=True),
        sa.Column("semantic_meaning_version", sa.String(64), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("entity_id", "revision_no", name="uq_research_dataset_revision_no"),
    )
    op.create_index(
        "ix_research_dataset_revision_entity_id", "research_dataset_revision", ["entity_id"]
    )
    op.create_index(
        "ix_research_dataset_revision_state", "research_dataset_revision", ["revision_state"]
    )
    op.create_index(
        "ix_research_dataset_revision_category", "research_dataset_revision", ["category_key"]
    )
    op.create_index(
        "ix_research_dataset_revision_market_link",
        "research_dataset_revision",
        ["linked_market_dataset_revision_id"],
    )

    op.create_table(
        "research_raw_asset",
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
    op.create_index("ix_research_raw_asset_entity_id", "research_raw_asset", ["entity_id"])
    op.create_index("ix_research_raw_asset_revision_id", "research_raw_asset", ["revision_id"])
    op.create_index(
        "ix_research_raw_asset_content_digest", "research_raw_asset", ["content_digest"]
    )

    op.create_table(
        "research_native_asset",
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
    op.create_index("ix_research_native_asset_entity_id", "research_native_asset", ["entity_id"])
    op.create_index(
        "ix_research_native_asset_revision_id", "research_native_asset", ["revision_id"]
    )
    op.create_index(
        "ix_research_native_asset_content_digest", "research_native_asset", ["content_digest"]
    )

    op.create_table(
        "research_field_definition",
        sa.Column("field_definition_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=True),
        sa.Column("definition_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("field_name", sa.String(256), nullable=False),
        sa.Column("semantic_type", sa.String(128), nullable=False),
        sa.Column("unit_or_scale", sa.String(128), nullable=True),
        sa.Column("measurement_method", sa.String(512), nullable=True),
        sa.Column("null_semantics", sa.String(512), nullable=True),
        sa.Column("event_time_source", sa.String(256), nullable=True),
        sa.Column("availability_rule", sa.String(256), nullable=True),
        sa.Column("allowed_usage", sa.String(128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_research_field_definition_entity_id", "research_field_definition", ["entity_id"]
    )
    op.create_index(
        "ix_research_field_definition_revision_id", "research_field_definition", ["revision_id"]
    )

    op.create_table(
        "research_feature_definition",
        sa.Column("feature_definition_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=True),
        sa.Column("feature_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("feature_name", sa.String(256), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("approval_state", sa.String(48), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_research_feature_definition_entity_id", "research_feature_definition", ["entity_id"]
    )
    op.create_index(
        "ix_research_feature_definition_revision_id",
        "research_feature_definition",
        ["revision_id"],
    )

    op.create_table(
        "research_time_policy",
        sa.Column("time_policy_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=True),
        sa.Column("time_policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "event_time_semantics",
            enum_column(EventTimeSemantics, "event_time_semantics"),
            nullable=False,
        ),
        sa.Column(
            "available_time_policy",
            enum_column(AvailableTimePolicy, "available_time_policy"),
            nullable=False,
        ),
        sa.Column("delay_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "source_timezone_mode",
            enum_column(ResearchTimezoneMode, "research_timezone_mode"),
            nullable=False,
        ),
        sa.Column("source_timezone_iana", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_research_time_policy_entity_id", "research_time_policy", ["entity_id"])
    op.create_index("ix_research_time_policy_revision_id", "research_time_policy", ["revision_id"])

    op.create_table(
        "research_market_link",
        sa.Column("link_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=True),
        sa.Column("market_dataset_revision_id", sa.String(40), nullable=False),
        sa.Column("market_content_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_research_market_link_entity_id", "research_market_link", ["entity_id"])
    op.create_index("ix_research_market_link_revision_id", "research_market_link", ["revision_id"])
    op.create_index(
        "ix_research_market_link_market_revision",
        "research_market_link",
        ["market_dataset_revision_id"],
    )

    op.create_table(
        "research_validation_run",
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
    op.create_index(
        "ix_research_validation_run_entity_id", "research_validation_run", ["entity_id"]
    )
    op.create_index(
        "ix_research_validation_run_revision_id", "research_validation_run", ["revision_id"]
    )

    op.create_table(
        "research_validation_issue",
        sa.Column("issue_id", sa.String(40), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(40),
            sa.ForeignKey("research_validation_run.run_id"),
            nullable=False,
        ),
        sa.Column("severity", enum_column(ValidationStatus, "validation_status"), nullable=False),
        sa.Column("check_id", sa.String(96), nullable=False),
        sa.Column("message", sa.String(1024), nullable=False),
        sa.Column("remediation", sa.String(1024), nullable=True),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_research_validation_issue_run_id", "research_validation_issue", ["run_id"])


def downgrade() -> None:
    op.drop_table("research_validation_issue")
    op.drop_table("research_validation_run")
    op.drop_table("research_market_link")
    op.drop_table("research_time_policy")
    op.drop_table("research_feature_definition")
    op.drop_table("research_field_definition")
    op.drop_table("research_native_asset")
    op.drop_table("research_raw_asset")
    op.drop_table("research_dataset_revision")
