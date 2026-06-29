"""Infrastructure-level tables (system metadata only; no product domain).

Domain models (roots, revisions, snapshots, audit, jobs, ...) arrive Stage 1+
under entropia/domain/*. They register against the same Base.metadata.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from entropia.infrastructure.postgres.base import Base


class AppMetadata(Base):
    """Key/value schema + build markers used by health checks and migrations."""

    __tablename__ = "app_metadata"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
