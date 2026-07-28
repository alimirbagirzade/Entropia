"""Durable, per-run monotonically sequenced backtest run stage events

O-05. Before this slice the worker's PROVISIONING/RUNNING transitions existed
only in its in-memory session and the whole ``run_backtest`` body was committed
once, at the end — so from outside the run appeared to jump QUEUED ->
SUCCEEDED/FAILED and doc 15 §8.3 ("Worker PROVISIONING/RUNNING events yazar")
had no persistence at all.

One new INSERT-only table ``backtest_run_event``:

* ``event_id`` VARCHAR(40) PK.
* ``run_id`` VARCHAR(40) NOT NULL, FK -> ``backtest_run.run_id`` ON DELETE
  CASCADE, indexed — an event is a child of the run root (the same pattern the
  result children use), so L1 parent-before-child insert order is enforced by
  the database, not by convention.
* ``sequence_no`` INTEGER NOT NULL — per-run monotonic, starts at 1.
* ``event_type`` VARCHAR + CHECK (non-native ``enum_column``) — the doc 15 §12
  spec tokens RUN_STARTED / RUN_STAGE_CHANGED / RUN_SUCCEEDED / RUN_FAILED /
  RUN_CANCELLED.
* ``previous_state`` (nullable) / ``state`` VARCHAR + CHECK over the canonical
  ``BacktestRunState`` (doc 15 §9.3).
* ``correlation_id`` VARCHAR(40) NULL, ``detail`` JSONB NULL, ``occurred_at``
  TIMESTAMPTZ NOT NULL DEFAULT now().
* ``UNIQUE(run_id, sequence_no)`` — this is what makes doc 15 §7 "Duplicate
  events de-duplicated by sequence_no" enforceable: one logical event can only
  ever hold one sequence for its run.

Additive only: no existing table or column is touched, so runs admitted before
this migration keep their exact behaviour (they simply carry no event rows and
replay returns an empty stream). Downgrade drops the table.

Revision ID: 0038_backtest_run_event
Revises: 0037_package_revision_link
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.backtest.enums import BacktestRunState, RunEventType
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0038_backtest_run_event"
down_revision: str | None = "0037_package_revision_link"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "backtest_run_event"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("event_id", sa.String(40), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(40),
            sa.ForeignKey("backtest_run.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column(
            "event_type",
            enum_column(RunEventType, "backtest_run_event_type"),
            nullable=False,
        ),
        sa.Column(
            "previous_state",
            enum_column(BacktestRunState, "backtest_run_state"),
            nullable=True,
        ),
        sa.Column(
            "state",
            enum_column(BacktestRunState, "backtest_run_state"),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(40), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("run_id", "sequence_no", name="uq_backtest_run_event_sequence"),
    )
    op.create_index(f"ix_{_TABLE}_run_id", _TABLE, ["run_id"])


def downgrade() -> None:
    op.drop_index(f"ix_{_TABLE}_run_id", table_name=_TABLE)
    op.drop_table(_TABLE)
