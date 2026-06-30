"""Market Data persistence tables (doc 11, decision D1).

The universal Root is the shared ``entity_registry`` (entity_type="market_dataset").
These tables hang off ``entity_registry.entity_id`` and carry the per-domain
revision lifecycle + assets + schema mapping + validation + coverage. Revisions
are INSERT-only (no ``updated_at``). Price/volume rows live in the processed
Parquet asset, never as float columns (D6); relational decimals use ``Numeric``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    RecordTimeBasis,
    ResolutionKind,
    TimezoneMode,
)
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


class MarketDatasetRevision(Base):
    """Immutable per-revision snapshot of a market dataset. Never UPDATEd."""

    __tablename__ = "market_dataset_revision"
    __table_args__ = (
        UniqueConstraint("entity_id", "revision_no", name="uq_market_dataset_revision_no"),
    )

    revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    supersedes_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    market_data_type: Mapped[MarketDataType] = mapped_column(
        enum_column(MarketDataType, "market_data_type"), nullable=False
    )
    revision_state: Mapped[MarketRevisionState] = mapped_column(
        enum_column(MarketRevisionState, "market_revision_state"),
        nullable=False,
        default=MarketRevisionState.DRAFT,
        index=True,
    )
    validation_status: Mapped[ValidationStatus | None] = mapped_column(
        enum_column(ValidationStatus, "validation_status"), nullable=True
    )
    resolution_kind: Mapped[ResolutionKind | None] = mapped_column(
        enum_column(ResolutionKind, "resolution_kind"), nullable=True
    )
    resolution_value: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timezone_mode: Mapped[TimezoneMode | None] = mapped_column(
        enum_column(TimezoneMode, "timezone_mode"), nullable=True
    )
    timezone_iana: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_time_basis: Mapped[RecordTimeBasis | None] = mapped_column(
        enum_column(RecordTimeBasis, "record_time_basis"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    instrument_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MarketRawAsset(TimestampMixin, Base):
    """Original uploaded source bytes (evidence). Immutable; never overwritten."""

    __tablename__ = "market_raw_asset"

    asset_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    uploaded_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )


class MarketProcessedAsset(TimestampMixin, Base):
    """Normalized, typed, partitioned Parquet output. One per revision."""

    __tablename__ = "market_processed_asset"

    asset_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    raw_asset_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    row_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    schema_descriptor: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class MarketSchemaMapping(TimestampMixin, Base):
    """Source-column -> canonical-field mapping proposal + confirmation (D7)."""

    __tablename__ = "market_schema_mapping"

    mapping_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    market_data_type: Mapped[MarketDataType] = mapped_column(
        enum_column(MarketDataType, "market_data_type"), nullable=False
    )
    mapping_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    proposed_mapping: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confirmed_mapping: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    review_required: Mapped[bool] = mapped_column(nullable=False, default=False)
    confirmed_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MarketValidationRun(TimestampMixin, Base):
    """One validation pass over a revision's processed data (doc 11 §)."""

    __tablename__ = "market_validation_run"

    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[ValidationStatus] = mapped_column(
        enum_column(ValidationStatus, "validation_status"), nullable=False
    )
    rows_checked: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MarketValidationIssue(Base):
    """A single validation finding within a run. Immutable."""

    __tablename__ = "market_validation_issue"

    issue_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("market_validation_run.run_id"), nullable=False, index=True
    )
    severity: Mapped[ValidationStatus] = mapped_column(
        enum_column(ValidationStatus, "validation_status"), nullable=False
    )
    rule_code: Mapped[str] = mapped_column(String(96), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sample: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DatasetCoverageSlice(Base):
    """A contiguous covered interval for a dataset revision. Immutable."""

    __tablename__ = "dataset_coverage_slice"

    slice_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    row_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    gap_seconds: Mapped[Any | None] = mapped_column(Numeric(20, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
