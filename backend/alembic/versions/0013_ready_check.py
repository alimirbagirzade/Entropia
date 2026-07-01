"""stage 4b — Backtest Ready Check plane (doc 14 §9.1, §12.1)

Two INSERT-only immutable tables on the readiness plane. The immutable
``mainboard_composition_snapshot`` already exists (0008) with its
``readiness_report_id`` + ``readiness_state`` slots — this stage FILLS them, no
ALTER is required:

* ``ready_check_report`` — the immutable report root: pinned
  ``composition_snapshot_id`` + ``composition_fingerprint`` (the stale-compare
  key), the derived ``state`` and summary counts. Never UPDATEd; rerun = new row.
* ``readiness_issue`` — immutable child findings (code/severity/scope/path/
  message/remediation), CASCADE-deleted with the report.

ENUM REUSE — ``state`` / ``severity`` / ``scope`` columns are built via
``enum_column`` (VARCHAR, ``native_enum=False``) so NO PostgreSQL ``CREATE TYPE``
is emitted (identical to 0005-0012). ``composition_snapshot_id`` carries NO
ForeignKey (mirrors the plain head-pointer style: the snapshot row is created in
the same tx and its ``readiness_report_id`` back-references the report).

Revision ID: 0013_ready_check
Revises: 0012_portfolio_allocation
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from entropia.domain.readiness.enums import (
    ReadinessScope,
    ReadinessSeverity,
    ReadinessState,
)
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0013_ready_check"
down_revision: str | None = "0012_portfolio_allocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"
_REPORT_FK = "ready_check_report.report_id"


def upgrade() -> None:
    op.create_table(
        "ready_check_report",
        sa.Column("report_id", sa.String(40), primary_key=True),
        sa.Column("workspace_entity_id", sa.String(40), nullable=False),
        sa.Column("composition_snapshot_id", sa.String(40), nullable=False),
        sa.Column("composition_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "state",
            enum_column(ReadinessState, "readiness_state_kind"),
            nullable=False,
        ),
        sa.Column("blocker_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pass_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allocation_enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "checked_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_ready_check_report_workspace_entity_id",
        "ready_check_report",
        ["workspace_entity_id"],
    )
    op.create_index(
        "ix_ready_check_report_composition_snapshot_id",
        "ready_check_report",
        ["composition_snapshot_id"],
    )
    op.create_index(
        "ix_ready_check_report_composition_fingerprint",
        "ready_check_report",
        ["composition_fingerprint"],
    )
    op.create_index("ix_ready_check_report_state", "ready_check_report", ["state"])

    op.create_table(
        "readiness_issue",
        sa.Column("issue_id", sa.String(40), primary_key=True),
        sa.Column(
            "report_id",
            sa.String(40),
            sa.ForeignKey(_REPORT_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column(
            "severity",
            enum_column(ReadinessSeverity, "readiness_severity"),
            nullable=False,
        ),
        sa.Column(
            "scope",
            enum_column(ReadinessScope, "readiness_scope"),
            nullable=False,
        ),
        sa.Column("field_path", sa.String(255), nullable=True),
        sa.Column("scope_id", sa.String(40), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("position_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_readiness_issue_report_id", "readiness_issue", ["report_id"])
    op.create_index("ix_readiness_issue_code", "readiness_issue", ["code"])
    op.create_index("ix_readiness_issue_severity", "readiness_issue", ["severity"])


def downgrade() -> None:
    op.drop_table("readiness_issue")
    op.drop_table("ready_check_report")
