"""Create Package + Pre-Check persistence tables (docs 06 §9.1, 07 §10.1).

Two Stage 2e tables, both hung off the shared ``entity_registry`` Root:

* ``package_request`` — a per-request MUTABLE detail row (PK = entity_id). It
  carries the normalized request inputs, the staleness anchors (``source_hash`` /
  ``context_hash``), the create-package flow ``state`` facet and the head pointers
  to the current scan / candidate / draft. Identity, deletion and the optimistic
  ``row_version`` (= request_version) live on the registry row.
* ``dependency_scan`` — an INSERT-only immutable Pre-Check evidence row. One
  request has N scans (``attempt_no``); each pins the exact resolved ESP revisions
  for one ``(source_hash, context_hash)`` at one registry fingerprint and is never
  reused for a different context (it goes stale instead).
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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.create_package.enums import (
    BaselineParseStatus,
    CreatePackageState,
    CreationMode,
    PackageImportStatus,
    PrecheckScanStatus,
    SourceKind,
    SourceLanguage,
    ValidationRunStatus,
)
from entropia.domain.esp.enums import RuntimeAdapter
from entropia.domain.lifecycle.enums import PackageKind
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


class PackageRequest(TimestampMixin, Base):
    """Mutable per-request detail row hung off ``entity_registry`` (PK = entity_id).

    The registry row owns identity, owner, deletion and ``row_version`` (the
    request_version used for optimistic concurrency). This detail row carries the
    normalized request and the create-package flow ``state``; it is updated in
    place as the request advances (it is work context, not an immutable revision).
    """

    __tablename__ = "package_request"

    entity_id: Mapped[str] = mapped_column(String(40), ForeignKey(_ENTITY_FK), primary_key=True)
    package_kind: Mapped[PackageKind] = mapped_column(
        enum_column(PackageKind, "package_kind"), nullable=False, index=True
    )
    creation_mode: Mapped[CreationMode] = mapped_column(
        enum_column(CreationMode, "creation_mode"), nullable=False
    )
    source_kind: Mapped[SourceKind] = mapped_column(
        enum_column(SourceKind, "source_kind"), nullable=False
    )
    source_language: Mapped[SourceLanguage | None] = mapped_column(
        enum_column(SourceLanguage, "source_language"), nullable=True
    )
    other_language_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_runtime: Mapped[RuntimeAdapter] = mapped_column(
        enum_column(RuntimeAdapter, "runtime_adapter"), nullable=False
    )
    request_body: Mapped[str] = mapped_column(String, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    output_contract: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rationale_family_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    compatible_rationale_family_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    linked_indicator: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    declared_dependencies: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    state: Mapped[CreatePackageState] = mapped_column(
        enum_column(CreatePackageState, "create_package_state"),
        nullable=False,
        default=CreatePackageState.REQUESTED,
        index=True,
    )
    current_scan_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    candidate_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    candidate_output_contract: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    package_root_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    draft_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_validation_run_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Whether the request claims equivalence to an external reference (doc 06 §4.4):
    # derived from the creation mode (translate/repair/review) or set explicitly.
    # The mode-aware approval baseline gate reads this — a claiming package needs a
    # passed baseline parse before publish; a non-claiming one does not.
    claims_equivalence: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Head pointer to the current immutable baseline_asset (its parse_status +
    # parse_report are the equivalence-comparison evidence).
    baseline_asset_id: Mapped[str | None] = mapped_column(String(40), nullable=True)


class DependencyScan(Base):
    """Immutable Pre-Check dependency-scan evidence (doc 07 §10.1). Never UPDATEd.

    Pins the resolved ESP revisions for exactly one ``(source_hash, context_hash)``
    at one ``registry_fingerprint``. Reuse against a different context is forbidden
    — the request treats it as stale and runs a fresh scan (new ``attempt_no``).
    """

    __tablename__ = "dependency_scan"
    __table_args__ = (
        UniqueConstraint("request_entity_id", "attempt_no", name="uq_dependency_scan_attempt"),
    )

    scan_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    request_entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scanner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    registry_fingerprint: Mapped[str] = mapped_column(String(80), nullable=False)
    detected_calls: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    resolved_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    missing_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    unsupported_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    source_warnings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    status: Mapped[PrecheckScanStatus] = mapped_column(
        enum_column(PrecheckScanStatus, "precheck_scan_status"),
        nullable=False,
        default=PrecheckScanStatus.CHECKING,
        index=True,
    )
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BaselineAsset(Base):
    """Immutable baseline-comparison evidence (doc 06 §4.4/§5/§8.3). Never re-keyed.

    One request has N baseline assets (``attempt_no``); each pins the exact
    content-addressed object key + digest of one uploaded CSV, the submitted
    ``BaselineMetadata`` and — after StartBaselineParse — the deterministic parse
    report + terminal ``parse_status``. A fresh upload is a new attempt; the object
    key / digest / metadata of a prior attempt are never mutated. The parse
    transitions ``uploaded -> passed`` on the current head; a rejected parse raises
    a typed error (PARSE_FAILED / BASELINE_METADATA_INVALID) and the user uploads a
    new baseline (doc 06 §9 "Baseline rejected").
    """

    __tablename__ = "baseline_asset"
    __table_args__ = (
        UniqueConstraint("request_entity_id", "attempt_no", name="uq_baseline_asset_attempt"),
    )

    baseline_asset_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    request_entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    baseline_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parse_status: Mapped[BaselineParseStatus] = mapped_column(
        enum_column(BaselineParseStatus, "baseline_parse_status"),
        nullable=False,
        default=BaselineParseStatus.UPLOADED,
        index=True,
    )
    parse_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parse_job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PackageValidationRun(Base):
    """Immutable package validation-run evidence (doc 06 §4.4/§5/§7). Never UPDATEd.

    One draft has N validation runs (``attempt_no``); each pins the exact
    ``candidate_hash`` it certified, the per-check breakdown and the terminal
    status. Reuse against a regenerated candidate is forbidden — the run goes
    ``stale`` (computed on read) and a fresh run is required before approval.
    """

    __tablename__ = "package_validation_run"
    __table_args__ = (
        UniqueConstraint(
            "request_entity_id", "attempt_no", name="uq_package_validation_run_attempt"
        ),
    )

    validation_run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    request_entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    package_root_id: Mapped[str] = mapped_column(String(40), nullable=False)
    draft_revision_id: Mapped[str] = mapped_column(String(40), nullable=False)
    candidate_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    validator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    status: Mapped[ValidationRunStatus] = mapped_column(
        enum_column(ValidationRunStatus, "validation_run_status"),
        nullable=False,
        default=ValidationRunStatus.QUEUED,
        index=True,
    )
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PackageImportJob(Base):
    """Durable package-import job projection (doc 08 §9.1/§10/§14, master ref Modül 7 §12).

    The reverse of package Export. A submitted export manifest is recorded here with
    the ``manifest_hash`` it certifies and the foreign origin (``origin_package_id`` /
    ``origin_revision_id``); a worker parses it, re-resolves its dependencies against
    the local ESP registry and either creates a clean DRAFT root (``succeeded``,
    ``result_package_root_id`` set) or a FAILED-validation DRAFT root with the missing
    calls in ``diagnostics`` (``blocked`` — never silently executable, doc 08 §10). A
    structurally-unparseable manifest is ``failed`` with no package. ``job_id`` links
    the durable ``jobs`` row that dispatched the worker; this row is the read model the
    Library Import report reads. Rows are append-then-terminal (created ``queued``,
    updated exactly once to a terminal status by the worker); the immutable evidence is
    the ``manifest_hash`` + ``diagnostics`` it pins.
    """

    __tablename__ = "package_import_job"

    import_job_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    origin_package_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    origin_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    package_kind: Mapped[PackageKind] = mapped_column(
        enum_column(PackageKind, "package_kind"), nullable=False
    )
    result_package_root_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[PackageImportStatus] = mapped_column(
        enum_column(PackageImportStatus, "package_import_status"),
        nullable=False,
        default=PackageImportStatus.QUEUED,
        index=True,
    )
    diagnostics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
