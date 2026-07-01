"""Backtest Ready Check persistence (Stage 4b, doc 14 §9.1, §12.1).

Two INSERT-only immutable tables on the readiness plane, both bound to a Mainboard
composition + its immutable ``mainboard_composition_snapshot`` (created by 3a; its
``readiness_report_id`` slot is filled by this stage):

* ``ready_check_report`` — the immutable report ROOT: the pinned
  ``composition_snapshot_id`` + ``composition_fingerprint`` (the stale-compare
  key), the derived ``state`` and the blocker/warning/pass summary counts. Never
  UPDATEd; a rerun creates a NEW report (doc 14 §9.1, §12.1).
* ``readiness_issue`` — an immutable child finding (code/severity/scope/path/
  message/remediation). Severity is only BLOCKER or WARNING; a PASS lives in the
  report summary, not as a row (doc 14 §9.1).

``composition_snapshot_id`` carries NO ForeignKey to keep the snapshot<->report
link uncoupled from insert order (the snapshot row is created in the same tx and
its ``readiness_report_id`` is back-filled) — mirrors the plain head-pointer
pattern used across the codebase. Enums use ``enum_column`` (VARCHAR + CHECK,
``native_enum=False``) so NO PostgreSQL ``CREATE TYPE`` is emitted.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.readiness.enums import (
    ReadinessScope,
    ReadinessSeverity,
    ReadinessState,
)
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.types import enum_column

_PRINCIPAL_FK = "principals.principal_id"
_REPORT_FK = "ready_check_report.report_id"


class ReadyCheckReport(Base):
    """Immutable readiness report pinned to a composition snapshot (doc 14 §9.1)."""

    __tablename__ = "ready_check_report"

    report_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_entity_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # Plain column (no FK): the snapshot is created in the same tx and its own
    # readiness_report_id is back-filled to point here (mirrors head-pointer style).
    composition_snapshot_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    composition_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[ReadinessState] = mapped_column(
        enum_column(ReadinessState, "readiness_state_kind"), nullable=False, index=True
    )
    blocker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allocation_enabled: Mapped[bool] = mapped_column(
        # stored as a small int flag via Integer keeps parity with count columns
        Integer,
        nullable=False,
        default=0,
    )
    checked_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReadinessIssueRow(Base):
    """Immutable child finding of a readiness report (doc 14 §9.1)."""

    __tablename__ = "readiness_issue"

    issue_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_REPORT_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[ReadinessSeverity] = mapped_column(
        enum_column(ReadinessSeverity, "readiness_severity"), nullable=False, index=True
    )
    scope: Mapped[ReadinessScope] = mapped_column(
        enum_column(ReadinessScope, "readiness_scope"), nullable=False
    )
    field_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scope_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    position_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
