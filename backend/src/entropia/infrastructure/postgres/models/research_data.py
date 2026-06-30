"""Research Data persistence tables (doc 12, decision D1).

The universal Root is the shared ``entity_registry`` (entity_type="research_dataset").
These tables hang off ``entity_registry.entity_id`` and carry the per-domain
revision lifecycle + native/raw assets + field/feature definitions + time policy +
the immutable market link + validation runs/issues. Revisions are INSERT-only (no
``updated_at``). Native payload preserves category-specific fields and is never
coerced into Market Data's canonical OHLCV schema (M5). Relational decimals use
``Numeric``; timestamps are ``DateTime(timezone=True)``.
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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    EventTimeSemantics,
    FrequencyPolicy,
    ResearchRevisionState,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


class ResearchDatasetRevision(Base):
    """Immutable per-revision snapshot of a research dataset. Never UPDATEd.

    Carries the meaning-and-timing envelope: native schema descriptor, the linked
    ACTIVE+APPROVED market revision, event/available time semantics, usage scope,
    frequency, source timezone, validation status, and the content/manifest hashes.
    """

    __tablename__ = "research_dataset_revision"
    __table_args__ = (
        UniqueConstraint("entity_id", "revision_no", name="uq_research_dataset_revision_no"),
    )

    revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    base_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    supersedes_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    revision_state: Mapped[ResearchRevisionState] = mapped_column(
        enum_column(ResearchRevisionState, "research_revision_state"),
        nullable=False,
        default=ResearchRevisionState.DRAFT,
        index=True,
    )
    validation_status: Mapped[ValidationStatus | None] = mapped_column(
        enum_column(ValidationStatus, "validation_status"), nullable=True
    )
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    category_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    custom_category: Mapped[str | None] = mapped_column(String(256), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    raw_asset_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    native_asset_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    native_schema_descriptor: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    field_definition_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    linked_market_dataset_revision_id: Mapped[str | None] = mapped_column(
        String(40), nullable=True, index=True
    )
    instrument_mapping_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    event_time_semantics: Mapped[EventTimeSemantics | None] = mapped_column(
        enum_column(EventTimeSemantics, "event_time_semantics"), nullable=True
    )
    available_time_policy: Mapped[AvailableTimePolicy | None] = mapped_column(
        enum_column(AvailableTimePolicy, "available_time_policy"), nullable=True
    )
    available_delay_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frequency_policy: Mapped[FrequencyPolicy | None] = mapped_column(
        enum_column(FrequencyPolicy, "frequency_policy"), nullable=True
    )
    source_timezone_mode: Mapped[ResearchTimezoneMode | None] = mapped_column(
        enum_column(ResearchTimezoneMode, "research_timezone_mode"), nullable=True
    )
    source_timezone_iana: Mapped[str | None] = mapped_column(String(64), nullable=True)
    usage_scope: Mapped[UsageScope | None] = mapped_column(
        enum_column(UsageScope, "research_usage_scope"), nullable=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    semantic_meaning_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResearchRawAsset(TimestampMixin, Base):
    """Original uploaded research bytes (evidence). Immutable; never overwritten.
    Replacement creates a new revision (doc 12 §8.2)."""

    __tablename__ = "research_raw_asset"

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


class ResearchNativeAsset(TimestampMixin, Base):
    """Parsed native-schema product. Preserves category-specific fields (OI,
    funding, liquidation, order book, macro) — never coerced to OHLCV (M5)."""

    __tablename__ = "research_native_asset"

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


class ResearchFieldDefinition(TimestampMixin, Base):
    """Versioned field-level semantic metadata (doc 12 §8.3). One row per field;
    a single prose paragraph is insufficient (FIELD_MEANING_INSUFFICIENT)."""

    __tablename__ = "research_field_definition"

    field_definition_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    field_name: Mapped[str] = mapped_column(String(256), nullable=False)
    semantic_type: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_or_scale: Mapped[str | None] = mapped_column(String(128), nullable=True)
    measurement_method: Mapped[str | None] = mapped_column(String(512), nullable=True)
    null_semantics: Mapped[str | None] = mapped_column(String(512), nullable=True)
    event_time_source: Mapped[str | None] = mapped_column(String(256), nullable=True)
    availability_rule: Mapped[str | None] = mapped_column(String(256), nullable=True)
    allowed_usage: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ResearchFeatureDefinition(TimestampMixin, Base):
    """Versioned feature definition (doc 12 §9.3). Required path before a
    Feature-Input-Only revision can feed Strategy logic."""

    __tablename__ = "research_feature_definition"

    feature_definition_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    feature_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    feature_name: Mapped[str] = mapped_column(String(256), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    approval_state: Mapped[str | None] = mapped_column(String(48), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ResearchTimePolicy(TimestampMixin, Base):
    """Resolved event/available time policy for a revision (doc 12 §8.4)."""

    __tablename__ = "research_time_policy"

    time_policy_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    time_policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    event_time_semantics: Mapped[EventTimeSemantics] = mapped_column(
        enum_column(EventTimeSemantics, "event_time_semantics"), nullable=False
    )
    available_time_policy: Mapped[AvailableTimePolicy] = mapped_column(
        enum_column(AvailableTimePolicy, "available_time_policy"), nullable=False
    )
    delay_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_timezone_mode: Mapped[ResearchTimezoneMode] = mapped_column(
        enum_column(ResearchTimezoneMode, "research_timezone_mode"), nullable=False
    )
    source_timezone_iana: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ResearchMarketLink(Base):
    """Immutable edge pinning a research revision to an exact ACTIVE+APPROVED
    market dataset revision by ID + content hash (doc 12 §5.2, anti-orphan)."""

    __tablename__ = "research_market_link"

    link_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    market_dataset_revision_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    market_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResearchValidationRun(TimestampMixin, Base):
    """One validation pass over a revision's parsed native data (doc 12 §5.3)."""

    __tablename__ = "research_validation_run"

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


class ResearchValidationIssue(Base):
    """A single structured validation finding within a run (doc 12 §10). Immutable."""

    __tablename__ = "research_validation_issue"

    issue_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("research_validation_run.run_id"), nullable=False, index=True
    )
    severity: Mapped[ValidationStatus] = mapped_column(
        enum_column(ValidationStatus, "validation_status"), nullable=False
    )
    check_id: Mapped[str] = mapped_column(String(96), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    remediation: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
