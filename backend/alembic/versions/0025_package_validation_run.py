"""gap-07 — package validation-run evidence plane + evidence-gated approval

Adds the INSERT-only immutable ``package_validation_run`` evidence table (one draft
has N runs; each pins the ``candidate_hash`` it certified + the per-check breakdown +
terminal status) and the ``package_request.current_validation_run_id`` head pointer.
No behaviour lives here; the approval gate + StartPackageValidationRun command drive
these rows. Mirrors the ``dependency_scan`` immutable-evidence shape (0007).

Revision ID: 0025_package_validation_run
Revises: 0024_strategy_draft_provenance
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.create_package.enums import ValidationRunStatus
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0025_package_validation_run"
down_revision: str | None = "0024_strategy_draft_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.add_column(
        "package_request",
        sa.Column("current_validation_run_id", sa.String(40), nullable=True),
    )
    op.create_table(
        "package_validation_run",
        sa.Column("validation_run_id", sa.String(40), primary_key=True),
        sa.Column("request_entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("package_root_id", sa.String(40), nullable=False),
        sa.Column("draft_revision_id", sa.String(40), nullable=False),
        sa.Column("candidate_hash", sa.String(80), nullable=True),
        sa.Column("validator_version", sa.String(64), nullable=False),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            enum_column(ValidationRunStatus, "validation_run_status"),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("job_id", sa.String(40), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "request_entity_id", "attempt_no", name="uq_package_validation_run_attempt"
        ),
    )
    op.create_index(
        "ix_package_validation_run_request_entity_id",
        "package_validation_run",
        ["request_entity_id"],
    )
    op.create_index("ix_package_validation_run_status", "package_validation_run", ["status"])


def downgrade() -> None:
    op.drop_table("package_validation_run")
    op.drop_column("package_request", "current_validation_run_id")
