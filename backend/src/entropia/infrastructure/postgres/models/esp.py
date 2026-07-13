"""ESP resolver registry persistence tables (doc 09 §4.1, DC2).

``embedded_resolver_contract``: one per ESP package revision — the canonical
signature, runtime adapter, timing/repaint semantics and evidence for a resolver.
``embedded_resolver_registry``: the canonical_key -> trusted active pointer that
makes a revision discoverable to Pre-Check (exactly one active registry row per
canonical_key). Both hang off the package's ``entity_registry.entity_id``.
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

from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


class EmbeddedResolverContract(Base):
    """Immutable canonical resolver contract for one ESP package revision."""

    __tablename__ = "embedded_resolver_contract"
    __table_args__ = (
        UniqueConstraint("revision_id", name="uq_embedded_resolver_contract_revision"),
    )

    contract_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    canonical_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    signature: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    runtime_adapter: Mapped[RuntimeAdapter] = mapped_column(
        enum_column(RuntimeAdapter, "runtime_adapter"), nullable=False
    )
    warm_up_period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timing_semantics: Mapped[str | None] = mapped_column(String(256), nullable=True)
    repaint: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EmbeddedResolverRegistry(TimestampMixin, Base):
    """The canonical_key -> trusted active revision pointer (doc 09 §4.1).

    Exactly one row per ``canonical_key`` (UNIQUE). ``trusted_active_revision_id``
    points at the exact ESP revision Pre-Check may select; it is nullable while a
    key has only candidate/deprecated entries.
    """

    __tablename__ = "embedded_resolver_registry"
    __table_args__ = (UniqueConstraint("canonical_key", name="uq_embedded_resolver_registry_key"),)

    registry_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    canonical_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    package_entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    trusted_active_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    trust_state: Mapped[ResolverTrustState] = mapped_column(
        enum_column(ResolverTrustState, "resolver_trust_state"),
        nullable=False,
        default=ResolverTrustState.CANDIDATE,
        index=True,
    )
    runtime_adapter: Mapped[RuntimeAdapter] = mapped_column(
        enum_column(RuntimeAdapter, "runtime_adapter"), nullable=False
    )
    registry_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    replacement_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    updated_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )


class EmbeddedResolverValidationRun(Base):
    """One validation-run over an ESP revision's stored test-vectors (doc 09 §11.1, R8).

    INSERT-only immutable evidence: each run pins the terminal ``status`` it certified, the
    ``validator_version`` namespace and the per-check breakdown. The run's status is copied
    onto ``revision.validation_state`` by the command; the activation gate then requires
    ``passed`` (not evidence presence). Mirrors the market/research ``*_validation_run`` and
    the ``package_validation_run`` (0025) immutable-evidence shape.
    """

    __tablename__ = "embedded_resolver_validation_run"

    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    revision_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    canonical_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[PackageValidationState] = mapped_column(
        enum_column(PackageValidationState, "package_validation_state"), nullable=False
    )
    validator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    vectors_run: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
