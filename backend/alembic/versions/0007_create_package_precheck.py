"""stage 2e — Create Package + Pre-Check (package_request + dependency_scan)

The mutable ``package_request`` detail (hung off entity_registry) carrying the
normalized request + create-package flow state, and the INSERT-only immutable
``dependency_scan`` evidence table pinning resolved ESP revisions per attempt.

Revision ID: 0007_create_package_precheck
Revises: 0006_rationale_families
Create Date: 2026-06-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.create_package.enums import (
    CreatePackageState,
    CreationMode,
    PrecheckScanStatus,
    SourceKind,
    SourceLanguage,
)
from entropia.domain.esp.enums import RuntimeAdapter
from entropia.domain.lifecycle.enums import PackageKind
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0007_create_package_precheck"
down_revision: str | None = "0006_rationale_families"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.create_table(
        "package_request",
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), primary_key=True),
        sa.Column("package_kind", enum_column(PackageKind, "package_kind"), nullable=False),
        sa.Column("creation_mode", enum_column(CreationMode, "creation_mode"), nullable=False),
        sa.Column("source_kind", enum_column(SourceKind, "source_kind"), nullable=False),
        sa.Column("source_language", enum_column(SourceLanguage, "source_language"), nullable=True),
        sa.Column("other_language_label", sa.String(120), nullable=True),
        sa.Column("target_runtime", enum_column(RuntimeAdapter, "runtime_adapter"), nullable=False),
        sa.Column("request_body", sa.String(), nullable=False),
        sa.Column("source_hash", sa.String(80), nullable=False),
        sa.Column("context_hash", sa.String(80), nullable=False),
        sa.Column("output_contract", postgresql.JSONB(), nullable=False),
        sa.Column("rationale_family_id", sa.String(40), nullable=True),
        sa.Column("compatible_rationale_family_ids", postgresql.JSONB(), nullable=False),
        sa.Column("linked_indicator", postgresql.JSONB(), nullable=True),
        sa.Column("declared_dependencies", postgresql.JSONB(), nullable=False),
        sa.Column(
            "state",
            enum_column(CreatePackageState, "create_package_state"),
            nullable=False,
            server_default="requested",
        ),
        sa.Column("current_scan_id", sa.String(40), nullable=True),
        sa.Column("candidate_hash", sa.String(80), nullable=True),
        sa.Column("candidate_output_contract", postgresql.JSONB(), nullable=True),
        sa.Column("package_root_id", sa.String(40), nullable=True),
        sa.Column("draft_revision_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_package_request_package_kind", "package_request", ["package_kind"])
    op.create_index("ix_package_request_context_hash", "package_request", ["context_hash"])
    op.create_index(
        "ix_package_request_rationale_family_id", "package_request", ["rationale_family_id"]
    )
    op.create_index("ix_package_request_state", "package_request", ["state"])
    op.create_index("ix_package_request_package_root_id", "package_request", ["package_root_id"])

    op.create_table(
        "dependency_scan",
        sa.Column("scan_id", sa.String(40), primary_key=True),
        sa.Column("request_entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(80), nullable=False),
        sa.Column("context_hash", sa.String(80), nullable=False),
        sa.Column("language", sa.String(40), nullable=True),
        sa.Column("scanner_version", sa.String(64), nullable=False),
        sa.Column("registry_fingerprint", sa.String(80), nullable=False),
        sa.Column("detected_calls", postgresql.JSONB(), nullable=False),
        sa.Column("resolved_refs", postgresql.JSONB(), nullable=False),
        sa.Column("missing_calls", postgresql.JSONB(), nullable=False),
        sa.Column("unsupported_calls", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            enum_column(PrecheckScanStatus, "precheck_scan_status"),
            nullable=False,
            server_default="checking",
        ),
        sa.Column("job_id", sa.String(40), nullable=True),
        sa.Column("error_detail", postgresql.JSONB(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("request_entity_id", "attempt_no", name="uq_dependency_scan_attempt"),
    )
    op.create_index(
        "ix_dependency_scan_request_entity_id", "dependency_scan", ["request_entity_id"]
    )
    op.create_index("ix_dependency_scan_context_hash", "dependency_scan", ["context_hash"])
    op.create_index("ix_dependency_scan_status", "dependency_scan", ["status"])


def downgrade() -> None:
    op.drop_table("dependency_scan")
    op.drop_table("package_request")
