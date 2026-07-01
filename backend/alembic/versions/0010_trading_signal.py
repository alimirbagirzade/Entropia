"""stage 3c — Trading Signal support tables (doc 04 §9.1)

Two standalone immutable tables backing the Trading Signal external work object:

* ``source_asset`` — raw uploaded TXT/CSV bytes evidence (object key + checksum).
* ``normalized_signal_event_revision`` — durable import output (accepted time-safe
  events + skipped-row report + evidence + content hash), pinned to the Trading
  Signal ``work_object_revision`` at Save time via a plain ``work_object_revision_id``.

The Trading Signal ROOT/REVISION reuse the existing 3a
``work_object_root`` / ``work_object_revision`` tables (native work object,
``object_kind=trading_signal``); the durable import JOB reuses the generic
``jobs`` table — so this migration adds NO new root/revision/job table.

ENUM REUSE — the status column is built via ``enum_column`` (VARCHAR + CHECK,
``native_enum=False``) so no PostgreSQL ``CREATE TYPE`` is emitted (identical to
0005/0008/0009). ``job_id`` / ``work_object_revision_id`` carry NO ForeignKey:
their targets live in different lifecycles/transactions (mirrors
``market_validation_run.job_id``).

Revision ID: 0010_trading_signal
Revises: 0009_strategy_details
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.trading_signal.enums import NormalizedRevisionStatus
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0010_trading_signal"
down_revision: str | None = "0009_strategy_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"
_SOURCE_ASSET_FK = "source_asset.source_asset_id"


def upgrade() -> None:
    op.create_table(
        "source_asset",
        sa.Column("source_asset_id", sa.String(40), primary_key=True),
        sa.Column("owner_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True),
        sa.Column("draft_id", sa.String(40), nullable=True),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("raw_asset_hash", sa.String(64), nullable=False),
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
    op.create_index("ix_source_asset_owner_principal_id", "source_asset", ["owner_principal_id"])
    op.create_index("ix_source_asset_draft_id", "source_asset", ["draft_id"])
    op.create_index("ix_source_asset_raw_asset_hash", "source_asset", ["raw_asset_hash"])

    op.create_table(
        "normalized_signal_event_revision",
        sa.Column("normalized_revision_id", sa.String(40), primary_key=True),
        sa.Column(
            "source_asset_id",
            sa.String(40),
            sa.ForeignKey(_SOURCE_ASSET_FK),
            nullable=False,
        ),
        sa.Column("job_id", sa.String(40), nullable=True),
        sa.Column(
            "status",
            enum_column(NormalizedRevisionStatus, "normalized_revision_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("instrument_id", sa.String(128), nullable=True),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("events", postgresql.JSONB(), nullable=False),
        sa.Column("skipped_rows", postgresql.JSONB(), nullable=False),
        sa.Column("validation_summary", postgresql.JSONB(), nullable=True),
        sa.Column("earliest_available_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("work_object_revision_id", sa.String(40), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_normalized_signal_event_revision_source_asset_id",
        "normalized_signal_event_revision",
        ["source_asset_id"],
    )
    op.create_index(
        "ix_normalized_signal_event_revision_job_id",
        "normalized_signal_event_revision",
        ["job_id"],
    )
    op.create_index(
        "ix_normalized_signal_event_revision_status",
        "normalized_signal_event_revision",
        ["status"],
    )
    op.create_index(
        "ix_normalized_signal_event_revision_content_hash",
        "normalized_signal_event_revision",
        ["content_hash"],
    )
    op.create_index(
        "ix_normalized_signal_event_revision_work_object_revision_id",
        "normalized_signal_event_revision",
        ["work_object_revision_id"],
    )


def downgrade() -> None:
    op.drop_table("normalized_signal_event_revision")
    op.drop_table("source_asset")
