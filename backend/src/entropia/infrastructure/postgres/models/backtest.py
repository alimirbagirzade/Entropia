"""Backtest execution + result plane persistence (Stage 5a, doc 15 §9.1).

Ten tables spanning the RUN -> Result pipeline. The RUN lifecycle root is mutable
(state advances QUEUED -> ... -> terminal); everything else is INSERT-only and
never UPDATEd once written:

* ``backtest_run`` — MUTABLE lifecycle root: pinned ``manifest_id`` +
  ``manifest_hash`` + ``composition_snapshot_id``/``composition_fingerprint``, the
  ``state`` machine, retry link, durable ``job_id`` and terminal failure metadata.
  ``result_id`` is back-filled only when a succeeded run materializes a Result.
* ``backtest_run_manifest`` — IMMUTABLE, hash-pinned exact dependency + engine
  context. ``manifest_hash`` is unique (one manifest per run). The worker's ONLY
  input; no 'latest' fallback (doc 15 §9.2, §15).
* ``backtest_result`` — IMMUTABLE final output root; only a succeeded run creates
  one (CR-03). Carries a local ``deletion_state`` flag + ``row_version`` for soft
  delete (doc 15 §7, §12) — Admin Trash restore/purge is Stage 6.
* ``result_summary`` / ``metric_value`` — the ResultSummary + MetricValue read
  model (doc 15 §9.1). A missing metric is NULL with a non-computed availability,
  never 0 (L4).
* ``result_equity_point`` / ``trade_ledger_row`` / ``signal_event`` /
  ``diagnostic_artifact`` — immutable result artifacts (curves, ledger, decision
  trace, diagnostics).
* ``result_manifest_snapshot`` — the manifest copy pinned to the RESULT so a
  historical result read never depends on the run/manifest rows (doc 15 §12).

Plain ``String(40)`` reference columns (no cross-table FK) mirror the head-pointer
style used across the codebase (``ready_check_report``); enums use ``enum_column``
(VARCHAR + CHECK, ``native_enum=False``) so NO PostgreSQL ``CREATE TYPE`` is
emitted. ``Numeric`` money/percent columns reject float at the domain boundary.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.backtest.enums import BacktestRunState, MetricAvailability
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.types import enum_column

_PRINCIPAL_FK = "principals.principal_id"
_RESULT_FK = "backtest_result.result_id"
_MONEY = Numeric(38, 10)


class BacktestRun(Base):
    """Mutable BacktestRun lifecycle root (doc 15 §9.1)."""

    __tablename__ = "backtest_run"

    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_entity_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    composition_snapshot_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    composition_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    manifest_id: Mapped[str] = mapped_column(String(40), nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[BacktestRunState] = mapped_column(
        enum_column(BacktestRunState, "backtest_run_state"),
        nullable=False,
        default=BacktestRunState.QUEUED,
        index=True,
    )
    requested_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    ready_report_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    retry_of_run_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BacktestRunManifest(Base):
    """Immutable hash-pinned run manifest — the worker's only input (doc 15 §9.2)."""

    __tablename__ = "backtest_run_manifest"

    manifest_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    execution_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    composition_snapshot_id: Mapped[str] = mapped_column(String(40), nullable=False)
    composition_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BacktestResult(Base):
    """Immutable final output root; only a succeeded run creates one (CR-03)."""

    __tablename__ = "backtest_result"

    result_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    manifest_id: Mapped[str] = mapped_column(String(40), nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workspace_entity_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    composition_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    deletion_state: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_principal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResultSummary(Base):
    """One-per-result headline summary projection (doc 15 §9.1)."""

    __tablename__ = "result_summary"

    summary_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_RESULT_FK, ondelete="CASCADE"), nullable=False, unique=True
    )
    symbol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timeframe: Mapped[str | None] = mapped_column(String(32), nullable=True)
    period_start: Mapped[str | None] = mapped_column(String(32), nullable=True)
    period_end: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    headline: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MetricValueRow(Base):
    """A single canonical MetricValue reading (doc 15 §9.1). NULL value never 0 (L4)."""

    __tablename__ = "metric_value"
    __table_args__ = (
        UniqueConstraint("result_id", "metric_key", name="uq_metric_value_result_key"),
    )

    metric_value_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_RESULT_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    metric_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    value_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    value: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    availability: Mapped[MetricAvailability] = mapped_column(
        enum_column(MetricAvailability, "metric_availability"), nullable=False
    )
    formula_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ResultEquityPoint(Base):
    """Immutable equity/drawdown/exposure curve point (doc 15 §3.2)."""

    __tablename__ = "result_equity_point"
    __table_args__ = (UniqueConstraint("result_id", "seq", name="uq_result_equity_point_seq"),)

    point_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_RESULT_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[str] = mapped_column(String(32), nullable=False)
    equity: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    drawdown: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    exposure: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)


class TradeLedgerRow(Base):
    """Immutable Trade Ledger root row (doc 15 §3.2, §14 Trade Root)."""

    __tablename__ = "trade_ledger_row"
    __table_args__ = (UniqueConstraint("result_id", "seq", name="uq_trade_ledger_row_seq"),)

    trade_row_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_RESULT_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_time: Mapped[str] = mapped_column(String(32), nullable=False)
    exit_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    pnl: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SignalEventRow(Base):
    """Immutable decision-trace signal event (doc 15 §14). NOT a fill."""

    __tablename__ = "signal_event"
    __table_args__ = (UniqueConstraint("result_id", "seq", name="uq_signal_event_seq"),)

    signal_event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_RESULT_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_time: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class DiagnosticArtifact(Base):
    """Immutable deterministic diagnostics artifact (doc 15 §3.2, §13)."""

    __tablename__ = "diagnostic_artifact"

    diagnostic_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_RESULT_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResultManifestSnapshot(Base):
    """Manifest copy pinned to the RESULT so historical reads never depend on the
    run/manifest rows (doc 15 §12 historical integrity)."""

    __tablename__ = "result_manifest_snapshot"

    snapshot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_RESULT_FK, ondelete="CASCADE"), nullable=False, unique=True
    )
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    execution_key: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
