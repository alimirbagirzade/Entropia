"""stage 5c — Arrange Metrics + Result export/artifact plane (doc 17; doc-15 deferred)

Four presentation/derivative-plane tables. NONE mutate a Backtest Result,
``metric_value`` or the run manifest (Arrange Metrics is display-only, CR-07):

* ``metric_definition`` — canonical versioned registry, SEEDED here from
  ``domain/metric_profile/registry.METRIC_REGISTRY`` (9 selectable + 18 future).
* ``result_view_metric_profile_root`` / ``result_view_metric_profile_revision`` —
  the immutable Apply/Lock/Unlock profile chain (root head pointer + row_version;
  revision INSERT-only). The revision FKs the root (ondelete CASCADE) so the root
  is created first.
* ``export_artifact`` — schema-versioned export metadata (object key + checksum +
  schema_version + row_count) with provenance = source result manifest hash; FKs
  ``backtest_result.result_id`` (created in 0014).

Enums use ``enum_column`` (VARCHAR + CHECK, ``native_enum=False``) so NO
``CREATE TYPE`` is emitted — identical to 0005-0014.

Revision ID: 0015_arrange_metrics_export
Revises: 0014_backtest_run_result
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.backtest.export import ExportFormat, ExportType
from entropia.domain.metric_profile.enums import MetricAvailabilityStatus, ProfileScope
from entropia.domain.metric_profile.registry import METRIC_REGISTRY, REGISTRY_VERSION
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0015_arrange_metrics_export"
down_revision: str | None = "0014_backtest_run_result"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"
_PROFILE_FK = "result_view_metric_profile_root.profile_id"
_RESULT_FK = "backtest_result.result_id"


def upgrade() -> None:
    op.create_table(
        "metric_definition",
        sa.Column("metric_code", sa.String(64), primary_key=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("value_format", sa.String(32), nullable=False),
        sa.Column(
            "availability_status",
            enum_column(MetricAvailabilityStatus, "metric_availability_status"),
            nullable=False,
        ),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("formula_version", sa.String(64), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("registry_version", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_metric_definition_availability", "metric_definition", ["availability_status"]
    )

    op.create_table(
        "result_view_metric_profile_root",
        sa.Column("profile_id", sa.String(40), primary_key=True),
        sa.Column("scope", enum_column(ProfileScope, "metric_profile_scope"), nullable=False),
        sa.Column("owner_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True),
        sa.Column("lifecycle_state", sa.String(16), nullable=False, server_default="active"),
        sa.Column("current_revision_id", sa.String(40), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "scope", "owner_principal_id", name="uq_result_view_metric_profile_owner"
        ),
    )
    op.create_index(
        "ix_result_view_metric_profile_root_scope", "result_view_metric_profile_root", ["scope"]
    )
    op.create_index(
        "ix_result_view_metric_profile_root_owner",
        "result_view_metric_profile_root",
        ["owner_principal_id"],
    )

    op.create_table(
        "result_view_metric_profile_revision",
        sa.Column("profile_revision_id", sa.String(40), primary_key=True),
        sa.Column(
            "profile_id",
            sa.String(40),
            sa.ForeignKey(_PROFILE_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("selected_metric_codes", postgresql.JSONB(), nullable=False),
        sa.Column("display_order", postgresql.JSONB(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metric_definition_registry_version", sa.String(32), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("previous_revision_id", sa.String(40), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("audit_correlation_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "profile_id", "revision_no", name="uq_result_view_metric_profile_revision_no"
        ),
    )
    op.create_index(
        "ix_result_view_metric_profile_revision_profile",
        "result_view_metric_profile_revision",
        ["profile_id"],
    )
    op.create_index(
        "ix_result_view_metric_profile_revision_hash",
        "result_view_metric_profile_revision",
        ["config_hash"],
    )

    op.create_table(
        "export_artifact",
        sa.Column("export_id", sa.String(40), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(40),
            sa.ForeignKey(_RESULT_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("export_type", enum_column(ExportType, "result_export_type"), nullable=False),
        sa.Column(
            "export_format", enum_column(ExportFormat, "result_export_format"), nullable=False
        ),
        sa.Column("source_manifest_hash", sa.String(64), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("filter_spec", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="complete"),
        sa.Column("created_by_principal_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_export_artifact_result", "export_artifact", ["result_id"])
    op.create_index("ix_export_artifact_source_hash", "export_artifact", ["source_manifest_hash"])

    # Seed the canonical metric registry (9 selectable + 18 future). created_at is
    # left to the column default. availability_status stores the enum value string.
    metric_definition = sa.table(
        "metric_definition",
        sa.column("metric_code", sa.String),
        sa.column("label", sa.String),
        sa.column("unit", sa.String),
        sa.column("value_format", sa.String),
        sa.column("availability_status", sa.String),
        sa.column("display_order", sa.Integer),
        sa.column("formula_version", sa.String),
        sa.column("description", sa.Text),
        sa.column("registry_version", sa.String),
    )
    op.bulk_insert(
        metric_definition,
        [
            {
                "metric_code": row.metric_code,
                "label": row.label,
                "unit": row.unit,
                "value_format": row.value_format,
                "availability_status": str(row.availability_status),
                "display_order": row.display_order,
                "formula_version": row.formula_version,
                "description": row.description,
                "registry_version": REGISTRY_VERSION,
            }
            for row in METRIC_REGISTRY
        ],
    )


def downgrade() -> None:
    op.drop_table("export_artifact")
    op.drop_table("result_view_metric_profile_revision")
    op.drop_table("result_view_metric_profile_root")
    op.drop_table("metric_definition")
