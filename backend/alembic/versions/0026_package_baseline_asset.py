"""gap-07b — package baseline CSV upload/parse evidence + mode-aware baseline gate

Adds the INSERT-only immutable ``baseline_asset`` evidence table (one request has N
uploads by ``attempt_no``; each pins the content-addressed object key + digest of one
uploaded CSV, the submitted BaselineMetadata JSONB and — after StartBaselineParse —
the deterministic parse report + terminal ``parse_status``) plus two
``package_request`` columns: ``claims_equivalence`` (the mode-aware equivalence
signal the approval baseline gate reads) and ``baseline_asset_id`` (the head pointer
to the current baseline). No behaviour lives here; the UploadBaselineAsset /
StartBaselineParse commands + the approval gate drive these rows. Mirrors the
``dependency_scan`` / ``package_validation_run`` immutable-evidence shape (0007/0025).

Revision ID: 0026_package_baseline_asset
Revises: 0025_package_validation_run
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.create_package.enums import BaselineParseStatus
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0026_package_baseline_asset"
down_revision: str | None = "0025_package_validation_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.add_column(
        "package_request",
        sa.Column(
            "claims_equivalence",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "package_request",
        sa.Column("baseline_asset_id", sa.String(40), nullable=True),
    )
    op.create_table(
        "baseline_asset",
        sa.Column("baseline_asset_id", sa.String(40), primary_key=True),
        sa.Column("request_entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("content_digest", sa.String(80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("baseline_metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "parse_status",
            enum_column(BaselineParseStatus, "baseline_parse_status"),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("parse_report", postgresql.JSONB(), nullable=True),
        sa.Column("parser_version", sa.String(64), nullable=True),
        sa.Column("parse_job_id", sa.String(40), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("request_entity_id", "attempt_no", name="uq_baseline_asset_attempt"),
    )
    op.create_index("ix_baseline_asset_request_entity_id", "baseline_asset", ["request_entity_id"])
    op.create_index("ix_baseline_asset_parse_status", "baseline_asset", ["parse_status"])


def downgrade() -> None:
    op.drop_table("baseline_asset")
    op.drop_column("package_request", "baseline_asset_id")
    op.drop_column("package_request", "claims_equivalence")
