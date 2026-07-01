"""Trade Log support table (Stage 3d, doc 05 §10.1).

One standalone (NOT entity_registry-anchored) immutable table:

* ``canonical_trade_record_batch`` — the durable output of the import worker: the
  accepted, normalized entry/exit records, the skipped-row report, validation
  evidence and the ``content_hash``. Pinned to a Trade Log revision at Save time via
  the nullable ``work_object_revision_id`` (plain column — the target is a
  ``work_object_revision``, set once, no circular-insert FK).

The raw uploaded bytes live in the shared ``source_asset`` table (introduced 3c,
model in ``models/trading_signal.py``); this batch FKs that asset. The Trade Log
ROOT/REVISION themselves reuse the 3a ``work_object_root`` / ``work_object_revision``
tables (native work object, ``object_kind=trade_log``); the durable import JOB
reuses the generic ``jobs`` table (queue ``data``). No new root/revision/job/asset
table is added.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.trade_log.enums import RecordBatchStatus
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.types import enum_column

_PRINCIPAL_FK = "principals.principal_id"
_SOURCE_ASSET_FK = "source_asset.source_asset_id"


class CanonicalTradeRecordBatch(Base):
    """Immutable normalized entry/exit record set produced by a durable import (doc 05 §10.1).

    ``work_object_revision_id`` is NULL until a Trade Log revision pins this batch at
    Save time. ``records`` / ``skipped_rows`` / ``validation_summary`` are JSONB
    evidence; ``content_hash`` is the deterministic digest of the accepted record set.
    ``earliest_entry_time`` / ``latest_exit_time`` capture the historical temporal
    span for provenance (doc 05 §10.4).
    """

    __tablename__ = "canonical_trade_record_batch"

    record_batch_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_asset_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_SOURCE_ASSET_FK), nullable=False, index=True
    )
    # Plain column (no FK) — mirrors normalized_signal_event_revision.job_id; the job
    # lives in the generic ``jobs`` table and is written in a separate transaction.
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    status: Mapped[RecordBatchStatus] = mapped_column(
        enum_column(RecordBatchStatus, "trade_record_batch_status"),
        nullable=False,
        default=RecordBatchStatus.PENDING,
        index=True,
    )
    instrument_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    skipped_rows: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    validation_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    earliest_entry_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latest_exit_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Set once at Save time to the Trade Log work_object_revision it backs.
    work_object_revision_id: Mapped[str | None] = mapped_column(
        String(40), nullable=True, index=True
    )
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
