"""Result export artifact persistence (Stage 5c, doc-15 deferred; doc 15 §9.1, §14).

One INSERT-only table. The row holds ONLY metadata — object-storage ``object_key``
+ ``checksum`` + ``schema_version`` + ``row_count`` — never the exported bytes
(doc 15 §9.1 "Immutable artifact metadata + object storage refs/checksum/schema
version"). ``source_manifest_hash`` is the PROVENANCE back to the source Result's
immutable manifest (doc 15 §9.1 ExportArtifact "+ source result manifest hash").
FK to ``backtest_result.result_id`` (ondelete CASCADE) so an export never outlives
a purged result. Enums use ``enum_column`` (no ``CREATE TYPE``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.backtest.export import ExportFormat, ExportType
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.types import enum_column

_RESULT_FK = "backtest_result.result_id"


class ExportArtifact(Base):
    """Immutable schema-versioned export derived from one Result (doc 15 §9.1)."""

    __tablename__ = "export_artifact"

    export_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_RESULT_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    export_type: Mapped[ExportType] = mapped_column(
        enum_column(ExportType, "result_export_type"), nullable=False
    )
    export_format: Mapped[ExportFormat] = mapped_column(
        enum_column(ExportFormat, "result_export_format"), nullable=False
    )
    source_manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filter_spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="complete", server_default="complete"
    )
    created_by_principal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
