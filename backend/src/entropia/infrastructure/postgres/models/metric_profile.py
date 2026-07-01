"""Arrange Metrics persistence (Stage 5c, doc 17 §5.1, §9.1, §9.3).

Three presentation-plane tables. NONE of them ever touch a Backtest Result,
``metric_value``, ``result_summary`` or the run manifest — Arrange Metrics is a
pure display preference (doc 17 §1, CR-07):

* ``metric_definition`` — the canonical, versioned registry seeded from
  ``domain/metric_profile/registry.METRIC_REGISTRY`` (migration 0015). ``metric_code``
  is the natural PK; ``availability_status`` (selectable/future/experimental) gates
  what a profile may select. A future metric is reference-only, never a fake value.
* ``result_view_metric_profile_root`` — the profile ROOT carrying the MUTABLE head
  (``current_revision_id``, plain column — no FK, mirrors ``entity_registry`` /
  ``portfolio_allocation_plan``) + ``row_version`` optimistic-concurrency token. One
  personal profile per principal is enforced by UNIQUE(scope, owner_principal_id).
  The System Default profile is resolved in-memory from the registry (no DB row in
  V1); Admin-writable default is a tracked later refinement.
* ``result_view_metric_profile_revision`` — INSERT-only immutable Apply/Lock/Unlock
  revision (selected codes + display order + ``is_locked`` + ``config_hash`` +
  registry version). Never UPDATEd; each Apply/Lock/Unlock appends a new revision.

Enums use ``enum_column`` (VARCHAR + CHECK, ``native_enum=False``) so no PostgreSQL
``CREATE TYPE`` is emitted (identical to 0005-0014).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.metric_profile.enums import MetricAvailabilityStatus, ProfileScope
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_PRINCIPAL_FK = "principals.principal_id"
_PROFILE_FK = "result_view_metric_profile_root.profile_id"


class MetricDefinition(Base):
    """Canonical, versioned metric registry row (doc 17 §9.2). Global (no owner)."""

    __tablename__ = "metric_definition"

    metric_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    value_format: Mapped[str] = mapped_column(String(32), nullable=False)
    availability_status: Mapped[MetricAvailabilityStatus] = mapped_column(
        enum_column(MetricAvailabilityStatus, "metric_availability_status"),
        nullable=False,
        index=True,
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    formula_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    registry_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResultViewMetricProfileRoot(TimestampMixin, Base):
    """Metric profile root + mutable head pointer (doc 17 §5.1, §9.3)."""

    __tablename__ = "result_view_metric_profile_root"
    __table_args__ = (
        UniqueConstraint("scope", "owner_principal_id", name="uq_result_view_metric_profile_owner"),
    )

    profile_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    scope: Mapped[ProfileScope] = mapped_column(
        enum_column(ProfileScope, "metric_profile_scope"), nullable=False, index=True
    )
    owner_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True, index=True
    )
    lifecycle_state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    # Plain column (no FK): set once the first revision exists (mirrors entity_registry).
    current_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ResultViewMetricProfileRevision(Base):
    """Immutable Apply/Lock/Unlock revision (doc 17 §5.1, §9.3). Never UPDATEd."""

    __tablename__ = "result_view_metric_profile_revision"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "revision_no", name="uq_result_view_metric_profile_revision_no"
        ),
    )

    profile_revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_PROFILE_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_metric_codes: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    display_order: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    is_locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    metric_definition_registry_version: Mapped[str] = mapped_column(String(32), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    audit_correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
