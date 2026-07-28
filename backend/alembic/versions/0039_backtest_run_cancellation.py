"""Backtest run cancellation: request intent + preserved terminal reason

Three additive nullable columns on ``backtest_run`` (doc 15 §8.4, §16). A run is
NEVER killed mid-flight: an authorized cancel records the INTENT here, and the
worker honors it at one of its O-05 stage boundaries, writing terminal
``cancelled`` with no Backtest Result (CR-03).

* ``cancel_requested_at`` TIMESTAMPTZ NULL — the moment an authorized cancel was
  accepted. NULL = never requested. This single column is what the worker reads
  at each safe checkpoint; it is deliberately NOT a run state, because doc 15 §4
  fixes the BacktestRun state set at QUEUED/PROVISIONING/RUNNING/SUCCEEDED/
  FAILED/CANCELLED and a request is not a state.
* ``cancel_requested_by_principal_id`` VARCHAR(40) NULL FK principals — who asked.
  Nullable + ``ON DELETE`` untouched, mirroring ``requested_by_principal_id`` on
  the same table.
* ``cancellation_reason`` TEXT NULL — the doc 15 §16 "terminal reason": which
  checkpoint honored the cancellation, preserved on the run forever. Mirrors the
  existing ``failure_message`` column for the FAILED path.

All three are nullable with no backfill, so every existing run keeps its exact
behaviour (never requested, never cancelled). Downgrade drops the columns.

Revision ID: 0039_backtest_run_cancellation
Revises: 0038_backtest_run_event
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039_backtest_run_cancellation"
down_revision: str | None = "0038_backtest_run_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "backtest_run"
_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        _TABLE,
        sa.Column("cancel_requested_by_principal_id", sa.String(40), nullable=True),
    )
    op.add_column(_TABLE, sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_backtest_run_cancel_requested_by",
        _TABLE,
        "principals",
        ["cancel_requested_by_principal_id"],
        ["principal_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_backtest_run_cancel_requested_by", _TABLE, type_="foreignkey")
    op.drop_column(_TABLE, "cancellation_reason")
    op.drop_column(_TABLE, "cancel_requested_by_principal_id")
    op.drop_column(_TABLE, "cancel_requested_at")
