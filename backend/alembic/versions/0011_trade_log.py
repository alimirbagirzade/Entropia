"""stage 3d — Trade Log support table (doc 05 §10.1)

One standalone immutable table backing the Trade Log external work object:

* ``canonical_trade_record_batch`` — durable import output (accepted normalized
  entry/exit records + skipped-row report + evidence + content hash), pinned to the
  Trade Log ``work_object_revision`` at Save time via a plain ``work_object_revision_id``.

The raw uploaded bytes reuse the shared ``source_asset`` table introduced in
``0010_trading_signal`` (no schema change). The Trade Log ROOT/REVISION reuse the
existing 3a ``work_object_root`` / ``work_object_revision`` tables (native work
object, ``object_kind=trade_log``); the durable import JOB reuses the generic
``jobs`` table — so this migration adds NO new root/revision/job/asset table.

ENUM REUSE — the status column is built via ``enum_column`` (VARCHAR + CHECK,
``native_enum=False``) so no PostgreSQL ``CREATE TYPE`` is emitted (identical to
0005/0008/0009/0010). ``job_id`` / ``work_object_revision_id`` carry NO ForeignKey:
their targets live in different lifecycles/transactions (mirrors
``normalized_signal_event_revision``).

Revision ID: 0011_trade_log
Revises: 0010_trading_signal
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.trade_log.enums import RecordBatchStatus
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0011_trade_log"
down_revision: str | None = "0010_trading_signal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"
_SOURCE_ASSET_FK = "source_asset.source_asset_id"


def upgrade() -> None:
    op.create_table(
        "canonical_trade_record_batch",
        sa.Column("record_batch_id", sa.String(40), primary_key=True),
        sa.Column(
            "source_asset_id",
            sa.String(40),
            sa.ForeignKey(_SOURCE_ASSET_FK),
            nullable=False,
        ),
        sa.Column("job_id", sa.String(40), nullable=True),
        sa.Column(
            "status",
            enum_column(RecordBatchStatus, "trade_record_batch_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("instrument_id", sa.String(128), nullable=True),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records", postgresql.JSONB(), nullable=False),
        sa.Column("skipped_rows", postgresql.JSONB(), nullable=False),
        sa.Column("validation_summary", postgresql.JSONB(), nullable=True),
        sa.Column("earliest_entry_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_exit_time", sa.DateTime(timezone=True), nullable=True),
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
        "ix_canonical_trade_record_batch_source_asset_id",
        "canonical_trade_record_batch",
        ["source_asset_id"],
    )
    op.create_index(
        "ix_canonical_trade_record_batch_job_id",
        "canonical_trade_record_batch",
        ["job_id"],
    )
    op.create_index(
        "ix_canonical_trade_record_batch_status",
        "canonical_trade_record_batch",
        ["status"],
    )
    op.create_index(
        "ix_canonical_trade_record_batch_content_hash",
        "canonical_trade_record_batch",
        ["content_hash"],
    )
    op.create_index(
        "ix_canonical_trade_record_batch_work_object_revision_id",
        "canonical_trade_record_batch",
        ["work_object_revision_id"],
    )


def downgrade() -> None:
    op.drop_table("canonical_trade_record_batch")
