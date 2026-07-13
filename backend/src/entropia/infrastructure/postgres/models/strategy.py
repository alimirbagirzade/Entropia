"""Strategy persistence models (Stage 3b, doc 02; DOMAIN_MODEL §2.3).

Four tables implementing the Strategy typed-config plane, all anchored on the
shared ``entity_registry`` root (a Strategy is also a work object — its
``entity_id`` carries a ``work_object_root`` detail with ``object_kind=strategy``
so 3a's ``attach_mainboard_item`` / ``pin_revision`` bind it unchanged):

1. ``strategy_root`` — entity_registry-anchored DETAIL (head pointer to the
   current immutable revision + display facets). Mutable pointers only.
2. ``strategy_editor_draft`` — mutable in-progress editor state (``row_version``);
   may be partial/invalid. Cleared/discarded without a Trash entry.
3. ``strategy_revision`` — INSERT-only immutable typed StrategyConfig snapshot
   with ``config_hash``. Never UPDATEd.
4. ``strategy_revision_references`` — INSERT-only immutable pinned dependency
   edges (exact ``root_id`` + ``revision_id`` + ``content_hash``; no "latest").

ID widths are ``String(40)`` to match ``entity_registry`` / ``principals`` /
every ``*_revision`` table (a 26-char ULID body + prefix fits comfortably).

Cross-domain references (``referenced_root_id`` / ``referenced_revision_id`` /
``family_snapshot``) are pinned by id + content_hash and carry NO ForeignKey:
their targets are heterogeneous (package / market / research revision tables),
so there is no single FK target — exactly the canonical normalized-reference
pattern (DOMAIN_MODEL §1; ARCHITECTURE §4.1). ``current_revision_id`` also has no
FK (mirrors ``entity_registry.current_revision_id``), avoiding a circular
root<->revision constraint and parent-before-child insert ordering hazards.
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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.strategy.enums import (
    DependencyRoleEnum,
    ReferencedEntityTypeEnum,
    StrategyLifecycleStateEnum,
    ValidationStatusEnum,
)
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.types import enum_column

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"
_STRATEGY_ROOT_FK = "strategy_root.entity_id"
_STRATEGY_REVISION_FK = "strategy_revision.revision_id"


class StrategyRoot(Base):
    """Per-strategy detail row hung off ``entity_registry`` (PK = entity_id).

    Mutable head pointer to the current immutable revision. owner/created_by/
    deletion_state live on the registry root; this table carries strategy-specific
    facets (display_name, rationale family, lifecycle). ``current_revision_id`` is
    a plain column (no FK — same as ``entity_registry``) so the root and its first
    revision can be created without a circular constraint.
    """

    __tablename__ = "strategy_root"

    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK, ondelete="CASCADE"), primary_key=True
    )
    current_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_row_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    lifecycle_state: Mapped[StrategyLifecycleStateEnum] = mapped_column(
        enum_column(StrategyLifecycleStateEnum, "strategy_lifecycle_state"),
        nullable=False,
        default=StrategyLifecycleStateEnum.DRAFT,
        server_default="draft",
        index=True,
    )
    # Name uniqueness is APP-enforced (per-owner), not a global DB unique — two
    # owners may legitimately share a display_name (follow-up: per-owner index).
    display_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    rationale_family_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    created_by_principal: Mapped[str] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=False
    )
    updated_by_principal: Mapped[str] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StrategyRevision(Base):
    """Immutable per-revision snapshot of a strategy. Never UPDATEd.

    Stores the canonical (disabled-section-filtered) StrategyConfig JSONB, the
    ``config_hash`` (SHA-256 of the canonical serialization), validation status,
    and pinned snapshots of lifecycle + rationale family. Revisions chain via
    ``parent_revision_id``; ``(entity_id, revision_number)`` is unique.
    """

    __tablename__ = "strategy_revision"
    __table_args__ = (
        UniqueConstraint("entity_id", "revision_number", name="uq_strategy_revision_entity_number"),
    )

    revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # content_hash mirrors config_hash for cross-domain manifest compatibility.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(16), nullable=False, default="v1", server_default="v1"
    )
    validation_status: Mapped[ValidationStatusEnum] = mapped_column(
        enum_column(ValidationStatusEnum, "strategy_validation_status"),
        nullable=False,
        default=ValidationStatusEnum.VALID,
        server_default="valid",
        index=True,
    )
    validation_errors: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    lifecycle_snapshot: Mapped[str | None] = mapped_column(String(48), nullable=True)
    # Pinned rationale family revision id (no FK — historical snapshot, never recomputed).
    family_snapshot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_by_principal: Mapped[str] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class StrategyRevisionReference(Base):
    """Immutable dependency edge: strategy revision -> pinned package/dataset.

    Every reference pins an exact ``(referenced_root_id, referenced_revision_id,
    referenced_content_hash)`` tuple. ``referenced_root_id`` /
    ``referenced_revision_id`` carry NO ForeignKey — the targets are heterogeneous
    (indicator/condition/ESP package, market/research dataset revisions), so there
    is no single FK table. Integrity is enforced at Save (resolve + active check)
    and verified by content_hash at manifest time (Stage 5).
    """

    __tablename__ = "strategy_revision_references"

    reference_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    strategy_revision_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey(_STRATEGY_REVISION_FK, ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    referenced_entity_type: Mapped[ReferencedEntityTypeEnum] = mapped_column(
        enum_column(ReferencedEntityTypeEnum, "strategy_reference_entity_type"),
        nullable=False,
    )
    referenced_root_id: Mapped[str] = mapped_column(String(40), nullable=False)
    referenced_revision_id: Mapped[str] = mapped_column(String(40), nullable=False)
    referenced_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_role: Mapped[DependencyRoleEnum] = mapped_column(
        enum_column(DependencyRoleEnum, "strategy_dependency_role"),
        nullable=False,
        index=True,
    )
    position_in_graph: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StrategyEditorDraft(Base):
    """Mutable in-progress editor state (may be partial/invalid).

    Holds the work-in-progress StrategyConfig payload (which MAY contain disabled
    blocks — the Save compiler filters them before persisting the immutable
    revision). Optimistic concurrency via ``row_version`` (bumped on every PATCH /
    Save). Clear/discard mutates the draft; it never creates a Trash entry.
    """

    __tablename__ = "strategy_editor_draft"

    draft_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    strategy_root_id: Mapped[str | None] = mapped_column(
        String(40),
        ForeignKey(_STRATEGY_ROOT_FK, ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Plain column (no FK): set once a revision exists; cleared on discard.
    last_saved_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # GAP-03: when a draft is derived from a Strategy Package, records the pinned
    # source (root+revision+content_hash) and the inherited dependency list (doc 01
    # §8.2). NULL for ordinary drafts. No FK — the source is a heterogeneous package
    # revision pinned by content_hash (normalized-reference pattern). Survives
    # PATCH/Clear (it is a fact about origin, not editable config).
    source_provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_dirty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_by_principal: Mapped[str] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=False
    )
    updated_by_principal: Mapped[str] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
