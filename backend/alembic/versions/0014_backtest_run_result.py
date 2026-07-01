"""stage 5a — Backtest RUN + Result plane (doc 15 §9.1, §9.2)

Ten tables for the RUN -> Result pipeline. ``backtest_run`` is the mutable
lifecycle root; every other table is INSERT-only. Child result-artifact tables FK
to ``backtest_result.result_id`` (ondelete CASCADE) and are therefore created
AFTER it; ``backtest_run`` / ``backtest_run_manifest`` use plain reference columns
(head-pointer style — same as ``ready_check_report``) so they carry no ordering
constraint. Enums (``backtest_run_state`` / ``metric_availability``) use
``enum_column`` (VARCHAR + CHECK, ``native_enum=False``) so NO ``CREATE TYPE`` is
emitted — identical to 0005-0013.

Revision ID: 0014_backtest_run_result
Revises: 0013_ready_check
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.backtest.enums import BacktestRunState, MetricAvailability
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0014_backtest_run_result"
down_revision: str | None = "0013_ready_check"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"
_RESULT_FK = "backtest_result.result_id"
_MONEY = sa.Numeric(38, 10)


def upgrade() -> None:
    op.create_table(
        "backtest_run",
        sa.Column("run_id", sa.String(40), primary_key=True),
        sa.Column("workspace_entity_id", sa.String(40), nullable=False),
        sa.Column("composition_snapshot_id", sa.String(40), nullable=False),
        sa.Column("composition_fingerprint", sa.String(64), nullable=False),
        sa.Column("manifest_id", sa.String(40), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("state", enum_column(BacktestRunState, "backtest_run_state"), nullable=False),
        sa.Column(
            "requested_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("ready_report_id", sa.String(40), nullable=True),
        sa.Column("retry_of_run_id", sa.String(40), nullable=True),
        sa.Column("job_id", sa.String(40), nullable=True),
        sa.Column("correlation_id", sa.String(40), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("result_id", sa.String(40), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_backtest_run_workspace", "backtest_run", ["workspace_entity_id"])
    op.create_index("ix_backtest_run_snapshot", "backtest_run", ["composition_snapshot_id"])
    op.create_index("ix_backtest_run_fingerprint", "backtest_run", ["composition_fingerprint"])
    op.create_index("ix_backtest_run_manifest_hash", "backtest_run", ["manifest_hash"])
    op.create_index("ix_backtest_run_state", "backtest_run", ["state"])
    op.create_index("ix_backtest_run_retry_of", "backtest_run", ["retry_of_run_id"])
    op.create_index("ix_backtest_run_result_id", "backtest_run", ["result_id"])

    op.create_table(
        "backtest_run_manifest",
        sa.Column("manifest_id", sa.String(40), primary_key=True),
        sa.Column("run_id", sa.String(40), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("execution_key", sa.String(64), nullable=False),
        sa.Column("composition_snapshot_id", sa.String(40), nullable=False),
        sa.Column("composition_fingerprint", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(64), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_backtest_run_manifest_run", "backtest_run_manifest", ["run_id"])
    op.create_index("ix_backtest_run_manifest_exec", "backtest_run_manifest", ["execution_key"])

    op.create_table(
        "backtest_result",
        sa.Column("result_id", sa.String(40), primary_key=True),
        sa.Column("run_id", sa.String(40), nullable=False, unique=True),
        sa.Column("manifest_id", sa.String(40), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("workspace_entity_id", sa.String(40), nullable=False),
        sa.Column("composition_fingerprint", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(64), nullable=False),
        sa.Column("deletion_state", sa.String(16), nullable=False, server_default="active"),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_principal_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_backtest_result_manifest_hash", "backtest_result", ["manifest_hash"])
    op.create_index("ix_backtest_result_workspace", "backtest_result", ["workspace_entity_id"])
    op.create_index(
        "ix_backtest_result_fingerprint", "backtest_result", ["composition_fingerprint"]
    )

    op.create_table(
        "result_summary",
        sa.Column("summary_id", sa.String(40), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(40),
            sa.ForeignKey(_RESULT_FK, ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("symbol", sa.String(64), nullable=True),
        sa.Column("timeframe", sa.String(32), nullable=True),
        sa.Column("period_start", sa.String(32), nullable=True),
        sa.Column("period_end", sa.String(32), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("headline", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "metric_value",
        sa.Column("metric_value_id", sa.String(40), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(40),
            sa.ForeignKey(_RESULT_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("value_format", sa.String(32), nullable=True),
        sa.Column("value", _MONEY, nullable=True),
        sa.Column(
            "availability", enum_column(MetricAvailability, "metric_availability"), nullable=False
        ),
        sa.Column("formula_version", sa.String(64), nullable=True),
        sa.Column("position_index", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("result_id", "metric_key", name="uq_metric_value_result_key"),
    )
    op.create_index("ix_metric_value_result", "metric_value", ["result_id"])

    op.create_table(
        "result_equity_point",
        sa.Column("point_id", sa.String(40), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(40),
            sa.ForeignKey(_RESULT_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.String(32), nullable=False),
        sa.Column("equity", _MONEY, nullable=False),
        sa.Column("drawdown", _MONEY, nullable=False),
        sa.Column("exposure", _MONEY, nullable=True),
        sa.UniqueConstraint("result_id", "seq", name="uq_result_equity_point_seq"),
    )
    op.create_index("ix_result_equity_point_result", "result_equity_point", ["result_id"])

    op.create_table(
        "trade_ledger_row",
        sa.Column("trade_row_id", sa.String(40), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(40),
            sa.ForeignKey(_RESULT_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("entry_time", sa.String(32), nullable=False),
        sa.Column("exit_time", sa.String(32), nullable=True),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("entry_price", _MONEY, nullable=False),
        sa.Column("exit_price", _MONEY, nullable=True),
        sa.Column("pnl", _MONEY, nullable=True),
        sa.Column("exit_reason", sa.String(64), nullable=True),
        sa.UniqueConstraint("result_id", "seq", name="uq_trade_ledger_row_seq"),
    )
    op.create_index("ix_trade_ledger_row_result", "trade_ledger_row", ["result_id"])

    op.create_table(
        "signal_event",
        sa.Column("signal_event_id", sa.String(40), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(40),
            sa.ForeignKey(_RESULT_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_time", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(8), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("result_id", "seq", name="uq_signal_event_seq"),
    )
    op.create_index("ix_signal_event_result", "signal_event", ["result_id"])

    op.create_table(
        "diagnostic_artifact",
        sa.Column("diagnostic_id", sa.String(40), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(40),
            sa.ForeignKey(_RESULT_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_diagnostic_artifact_result", "diagnostic_artifact", ["result_id"])

    op.create_table(
        "result_manifest_snapshot",
        sa.Column("snapshot_id", sa.String(40), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(40),
            sa.ForeignKey(_RESULT_FK, ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("execution_key", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(64), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_result_manifest_snapshot_hash", "result_manifest_snapshot", ["manifest_hash"]
    )


def downgrade() -> None:
    op.drop_table("result_manifest_snapshot")
    op.drop_table("diagnostic_artifact")
    op.drop_table("signal_event")
    op.drop_table("trade_ledger_row")
    op.drop_table("result_equity_point")
    op.drop_table("metric_value")
    op.drop_table("result_summary")
    op.drop_table("backtest_result")
    op.drop_table("backtest_run_manifest")
    op.drop_table("backtest_run")
