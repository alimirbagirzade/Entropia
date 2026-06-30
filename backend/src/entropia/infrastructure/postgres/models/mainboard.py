"""Mainboard composition-plane persistence (doc 01; DOMAIN_MODEL §2.2).

Five tables sit on the composition plane:

* ``mainboard_workspace`` — entity_registry-anchored DETAIL (entity_type
  ``mainboard_workspace``); owner/created_by/deletion_state live on the registry
  root. Carries the cached ``composition_hash``.
* ``work_object_root`` — entity_registry-anchored DETAIL (entity_type
  ``work_object``) carrying the stable ``object_kind`` discriminator.
* ``work_object_revision`` — INSERT-only immutable revision chain. Never UPDATEd.
* ``mainboard_working_item`` — a PLAIN child of a workspace (NOT registry-
  anchored). It pins an exact ``work_object_root_id`` + ``pinned_revision_id``.
  When a root is soft-deleted the item stays but is filtered from the active
  projection (detached), never auto-repointed.
* ``mainboard_composition_snapshot`` — INSERT-only immutable snapshot of a
  workspace's enabled composition. ``readiness_report_id`` stays NULL until
  Stage 4 consumes it.

``object_kind`` and ``item_kind`` both use ``MainboardItemKind`` so the CR-01
kind guard is exact enum equality. Stored via ``enum_column`` (portable VARCHAR
+ CHECK, ``native_enum=False``) — the same enum reused across three tables emits
NO PostgreSQL ``CREATE TYPE`` and so cannot collide at migration time.
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

from entropia.domain.mainboard.enums import MainboardItemKind, WorkspaceKind
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"
_REVISION_FK = "work_object_revision.revision_id"


class MainboardWorkspace(Base):
    """Per-workspace detail row hung off ``entity_registry`` (PK = entity_id).

    One active default per human owner is APP-ENFORCED (query-before-create in
    ``get_default_mainboard``); no cross-table DB constraint expresses it.
    """

    __tablename__ = "mainboard_workspace"

    entity_id: Mapped[str] = mapped_column(String(40), ForeignKey(_ENTITY_FK), primary_key=True)
    workspace_kind: Mapped[WorkspaceKind] = mapped_column(
        enum_column(WorkspaceKind, "workspace_kind"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    composition_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class WorkObjectRoot(Base):
    """Per-work-object detail row hung off ``entity_registry`` (PK = entity_id).

    ``object_kind`` is set at creation and never mutated. owner/current_revision_id
    /row_version/deletion_state live on the registry root.
    """

    __tablename__ = "work_object_root"

    entity_id: Mapped[str] = mapped_column(String(40), ForeignKey(_ENTITY_FK), primary_key=True)
    object_kind: Mapped[MainboardItemKind] = mapped_column(
        enum_column(MainboardItemKind, "mainboard_item_kind"), nullable=False, index=True
    )


class WorkObjectRevision(Base):
    """Immutable per-revision snapshot of a work object. Never UPDATEd."""

    __tablename__ = "work_object_revision"
    __table_args__ = (
        UniqueConstraint("entity_id", "revision_no", name="uq_work_object_revision_no"),
    )

    revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    supersedes_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    object_kind: Mapped[MainboardItemKind] = mapped_column(
        enum_column(MainboardItemKind, "mainboard_item_kind"), nullable=False, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    validation_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    available_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    change_note: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MainboardWorkingItem(TimestampMixin, Base):
    """A pinned placement of a work object on a workspace (plain child, NOT
    registry-anchored). Pins an exact root + revision; no unique(workspace, root)
    — a duplicate-same-object is a Ready-Check blocker (Stage 4), not an attach
    block.
    """

    __tablename__ = "mainboard_working_item"

    item_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    item_kind: Mapped[MainboardItemKind] = mapped_column(
        enum_column(MainboardItemKind, "mainboard_item_kind"), nullable=False
    )
    work_object_root_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False
    )
    pinned_revision_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_REVISION_FK), nullable=False
    )
    position_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_label_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_principal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)


class MainboardCompositionSnapshot(Base):
    """Immutable snapshot of a workspace's enabled composition (doc 01 §9.2).

    ``readiness_report_id`` stays NULL in Stage 3a; Stage 4 (Ready Check) is the
    only producer that fills it.
    """

    __tablename__ = "mainboard_composition_snapshot"

    snapshot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    composition_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    item_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    capital_mode_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    readiness_state: Mapped[str] = mapped_column(String(32), nullable=False, default="unevaluated")
    readiness_report_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
