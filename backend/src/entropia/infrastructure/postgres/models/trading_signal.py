"""Trading Signal support tables (Stage 3c, doc 04 §9.1).

Two standalone (NOT entity_registry-anchored) immutable tables. They are created
during the *transient draft* phase — BEFORE any Trading Signal root exists — so
they cannot FK the work object root:

* ``source_asset`` — the raw uploaded TXT/CSV bytes evidence (object storage key +
  ``raw_asset_hash`` checksum). Immutable; never overwritten (a new upload is a new
  asset, doc 04 §5.2). Mirrors ``market_raw_asset`` but stands alone.
* ``normalized_signal_event_revision`` — the durable output of the import worker:
  the accepted time-safe event set, the skipped-row report, validation evidence and
  the ``content_hash``. Pinned to a Trading Signal revision at Save time via the
  nullable ``work_object_revision_id`` (plain column — the target is a
  ``work_object_revision``, set once, no circular-insert FK).

The Trading Signal ROOT/REVISION themselves reuse the 3a
``work_object_root`` / ``work_object_revision`` tables (native work object,
``object_kind=trading_signal``); the durable import JOB reuses the generic
``jobs`` table (queue ``data``). No new root/revision/job table is added.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.trading_signal.enums import NormalizedRevisionStatus
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_PRINCIPAL_FK = "principals.principal_id"
_SOURCE_ASSET_FK = "source_asset.source_asset_id"


class SourceAsset(TimestampMixin, Base):
    """Immutable raw uploaded source bytes evidence (doc 04 §9.1).

    Standalone: no ``entity_registry`` FK because the asset predates the Trading
    Signal root (uploaded on the transient draft). ``draft_id`` is a loose
    correlation handle, never identity.
    """

    __tablename__ = "source_asset"

    source_asset_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True, index=True
    )
    draft_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_asset_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    uploaded_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )


class NormalizedSignalEventRevision(Base):
    """Immutable normalized signal-event set produced by a durable import (doc 04 §9.1).

    ``work_object_revision_id`` is NULL until a Trading Signal revision pins this
    normalized revision at Save time. ``events`` / ``skipped_rows`` /
    ``validation_summary`` are JSONB evidence; ``content_hash`` is the deterministic
    digest of the accepted event set.
    """

    __tablename__ = "normalized_signal_event_revision"

    normalized_revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_asset_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_SOURCE_ASSET_FK), nullable=False, index=True
    )
    # Plain column (no FK) — mirrors market_validation_run.job_id; the job lives in
    # the generic ``jobs`` table and is written in a separate transaction.
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    status: Mapped[NormalizedRevisionStatus] = mapped_column(
        enum_column(NormalizedRevisionStatus, "normalized_revision_status"),
        nullable=False,
        default=NormalizedRevisionStatus.PENDING,
        index=True,
    )
    instrument_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    skipped_rows: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    validation_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    earliest_available_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Set once at Save time to the Trading Signal work_object_revision it backs.
    work_object_revision_id: Mapped[str | None] = mapped_column(
        String(40), nullable=True, index=True
    )
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
