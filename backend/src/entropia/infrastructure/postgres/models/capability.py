"""Future Dev tables (Stage 7b, doc 22 §9, §13).

``future_capability`` is the server-side Capability Registry row — the
authoritative availability record with a per-row monotonic ``registry_version``
(the OCC token behind ``expected_registry_version``). Registry rows are managed
by lifecycle state (Retired, never Trash — doc 22 §13).
``capability_activation_event`` is the immutable append-only transition audit;
``(capability_id, resulting_registry_version)`` is unique so the event chain is
gap-checkable per capability.

``analysis_artifact`` and ``view_dataset`` are the future OUTPUT roots a
Limited/Active capability may create (immutable content + ``deletion_state``
overlay for normal soft-delete/Trash rules once created — §13).
``experiment_proposal`` and ``execution_plan`` are future-only roots: the
tables exist as the doc-22 §9 contract, but Production V1 exposes no command
that writes them (CR-09 — no fake instance while Placeholder).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.capability.enums import CapabilityState
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_PRINCIPAL_FK = "principals.principal_id"
_CAPABILITY_FK = "future_capability.capability_id"


class FutureCapability(TimestampMixin, Base):
    """Capability Registry row (doc 22 §9 entity table)."""

    __tablename__ = "future_capability"
    __table_args__ = (
        UniqueConstraint("capability_key", name="uq_future_capability_key"),
        Index("ix_future_capability_state", "lifecycle_state"),
    )

    capability_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    capability_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    menu_path: Mapped[str] = mapped_column(String(160), nullable=False)
    lifecycle_state: Mapped[CapabilityState] = mapped_column(
        enum_column(CapabilityState, "capability_lifecycle_state"),
        nullable=False,
        default=CapabilityState.PLACEHOLDER,
        server_default=CapabilityState.PLACEHOLDER.value,
    )
    ui_surface_version: Mapped[str] = mapped_column(String(32), nullable=False)
    domain_contract_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dependency_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    registry_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retirement_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changed_by_actor_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    change_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


class CapabilityActivationEvent(Base):
    """Immutable lifecycle-transition audit event (doc 22 §9, §13)."""

    __tablename__ = "capability_activation_event"
    __table_args__ = (
        UniqueConstraint(
            "capability_id",
            "resulting_registry_version",
            name="uq_capability_event_registry_version",
        ),
        Index("ix_capability_events_key", "capability_key"),
    )

    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    capability_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_CAPABILITY_FK), nullable=False
    )
    capability_key: Mapped[str] = mapped_column(String(64), nullable=False)
    from_state: Mapped[CapabilityState] = mapped_column(
        enum_column(CapabilityState, "capability_event_from_state"), nullable=False
    )
    to_state: Mapped[CapabilityState] = mapped_column(
        enum_column(CapabilityState, "capability_event_to_state"), nullable=False
    )
    actor_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    dependency_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    snapshot_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    prior_registry_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_registry_version: Mapped[int] = mapped_column(Integer, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AnalysisArtifact(TimestampMixin, Base):
    """Immutable future analysis output root (doc 22 §9): review, Monte Carlo,
    WFA, sensitivity etc. carry input manifest refs + method version — never a
    late write into a canonical Backtest Result (FD-05/09)."""

    __tablename__ = "analysis_artifact"
    __table_args__ = (
        Index("ix_analysis_artifact_type", "artifact_type"),
        Index("ix_analysis_artifact_capability", "capability_key"),
    )

    artifact_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_key: Mapped[str] = mapped_column(String(64), nullable=False)
    input_manifest_refs: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    method_version: Mapped[str] = mapped_column(String(64), nullable=False)
    output_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deletion_state: Mapped[DeletionState] = mapped_column(
        enum_column(DeletionState, "analysis_artifact_deletion_state"),
        nullable=False,
        default=DeletionState.ACTIVE,
        server_default=DeletionState.ACTIVE.value,
    )
    owner_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ViewDataset(TimestampMixin, Base):
    """Renderer-independent Graphic View input model (doc 22 §9, §10.2): pinned
    immutable source refs only; it never mutates Market/Result state (FD-04)."""

    __tablename__ = "view_dataset"
    __table_args__ = (Index("ix_view_dataset_capability", "capability_key"),)

    view_dataset_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    capability_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_manifest_refs: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    series_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    marker_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    range_spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    deletion_state: Mapped[DeletionState] = mapped_column(
        enum_column(DeletionState, "view_dataset_deletion_state"),
        nullable=False,
        default=DeletionState.ACTIVE,
        server_default=DeletionState.ACTIVE.value,
    )
    owner_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ExperimentProposal(TimestampMixin, Base):
    """Future-only Hypothesis Lab / Parameter Fields bridge root (doc 22 §9).
    No V1 command writes it — the contract exists, the fake instance does not."""

    __tablename__ = "experiment_proposal"

    proposal_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    hypothesis_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_bundle_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    parameter_plan_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="proposed", server_default="proposed"
    )
    acceptance_criteria: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    owner_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ExecutionPlan(TimestampMixin, Base):
    """Future-only Live Trade entry root (doc 22 §9, §10.1): a SEPARATE
    execution plane — no V1 order endpoint, broker adapter or session writes it
    (FD-12); it is never derived from a Backtest RUN configuration."""

    __tablename__ = "execution_plan"

    plan_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    strategy_revision_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    package_revision_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    market_data_policy_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    portfolio_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_policy_refs: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    lifecycle_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft"
    )
    owner_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
