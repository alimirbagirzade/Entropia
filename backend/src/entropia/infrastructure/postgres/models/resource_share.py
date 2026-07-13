"""Explicit resource share grants (GAP-17; Master Reference §6, §6.4).

``resource_share`` records *who* a private resource is explicitly shared with —
the fine-grained grantee list the ``explicitly_shared`` visibility state needs.
An ACTIVE grant is one with ``revoked_at IS NULL``; the partial unique index
guarantees at most one active grant per (resource, grantee), so a repeated share
is idempotent and a revoked grant never blocks a later re-share. Revocation is a
soft close so the grant history stays auditable. V1 uses ``resource_type =
'package'``; the table is generic so future resources reuse it verbatim.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin

_PRINCIPAL_FK = "principals.principal_id"


class ResourceShare(TimestampMixin, Base):
    """One explicit share grant of a resource to a grantee principal."""

    __tablename__ = "resource_share"
    __table_args__ = (
        Index(
            "uq_resource_share_active_grant",
            "resource_type",
            "resource_id",
            "grantee_principal_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "ix_resource_share_grantee_active",
            "grantee_principal_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "ix_resource_share_resource_active",
            "resource_type",
            "resource_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    share_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(40), nullable=False)
    grantee_principal_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=False
    )
    granted_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
