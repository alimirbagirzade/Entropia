"""Shared package persistence tables (doc 09 §2.5, §4.1; DC1).

The universal Root is the shared ``entity_registry`` (entity_type="package").
``package_root`` is a per-package detail table (PK = entity_id) carrying the
package-kind/visibility facets; ``package_revision`` is the INSERT-only immutable
revision chain. Introduced here for ESP and reused by the broader package
pipeline (2e). Revisions are never UPDATEd (no ``updated_at``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.lifecycle.enums import ApprovalState, PackageKind, VisibilityScope
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.types import enum_column

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


class PackageRoot(Base):
    """Per-package detail row hung off ``entity_registry`` (PK = entity_id).

    Carries the stable package-kind identity and visibility facet. ``package_kind``
    is set at root creation and never mutated (doc 09 §4.1 "package_type ... later
    mutate edilmez").
    """

    __tablename__ = "package_root"

    entity_id: Mapped[str] = mapped_column(String(40), ForeignKey(_ENTITY_FK), primary_key=True)
    package_kind: Mapped[PackageKind] = mapped_column(
        enum_column(PackageKind, "package_kind"), nullable=False, index=True
    )
    visibility_scope: Mapped[VisibilityScope] = mapped_column(
        enum_column(VisibilityScope, "visibility_scope"),
        nullable=False,
        default=VisibilityScope.PRIVATE,
        index=True,
    )
    derived_from_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Import provenance (doc 08 §10, master ref Modül 7 §12): when this local root was
    # created by importing a foreign export manifest, this pins the manifest's
    # ``package_root_id`` so the origin is auditable. NULL for natively-authored roots.
    origin_package_id: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PackageRevision(Base):
    """Immutable per-revision snapshot of a package. Never UPDATEd."""

    __tablename__ = "package_revision"
    __table_args__ = (UniqueConstraint("entity_id", "revision_no", name="uq_package_revision_no"),)

    revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    supersedes_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    package_kind: Mapped[PackageKind] = mapped_column(
        enum_column(PackageKind, "package_kind"), nullable=False, index=True
    )
    input_contract: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_contract: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    dependency_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rationale_family_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    validation_state: Mapped[PackageValidationState] = mapped_column(
        enum_column(PackageValidationState, "package_validation_state"),
        nullable=False,
        default=PackageValidationState.PENDING,
        index=True,
    )
    approval_state: Mapped[ApprovalState] = mapped_column(
        enum_column(ApprovalState, "package_approval_state"),
        nullable=False,
        default=ApprovalState.DRAFT,
        index=True,
    )
    validation_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # F-14: the immutable loadable implementation generated for this revision (source,
    # entry symbol, plan, executable flag, provenance). NULL for pre-F-14 / hand-built
    # revisions; the resolver/validation sandbox loads a real artifact when present.
    implementation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    change_note: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
