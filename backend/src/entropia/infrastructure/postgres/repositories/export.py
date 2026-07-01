"""Result export persistence + source-row loading (Stage 5c, doc-15 deferred).

No commits — the command layer owns the transaction. ``create_export`` flushes so
the ``export_id`` is available. ``load_source_rows`` reads the IMMUTABLE source
artifact for an export type (doc 15 §8.5 "the rendered table rows are not the
export source") — the export bytes are derived from persisted artifacts, never
from UI/DOM state, so the checksum + row_count are reproducible (doc 15 §14).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.artifacts import ArtifactType
from entropia.domain.backtest.export import ExportFormat, ExportType
from entropia.infrastructure.postgres.models.backtest import (
    DiagnosticArtifact,
    ResultEquityPoint,
    ResultSummary,
    SignalEventRow,
    TradeLedgerRow,
)
from entropia.infrastructure.postgres.models.export import ExportArtifact
from entropia.infrastructure.postgres.repositories.result_artifacts import project_row

_EXPORT_TO_ARTIFACT = {
    ExportType.TRADE_LEDGER: ArtifactType.TRADE_LEDGER,
    ExportType.EQUITY_CURVE: ArtifactType.EQUITY_CURVE,
    ExportType.SIGNAL_EVENTS: ArtifactType.SIGNAL_EVENTS,
    ExportType.DIAGNOSTICS: ArtifactType.DIAGNOSTICS,
}
# ``(model, order_column)`` typed ``Any`` so the per-type column access is not
# narrowed to the common ``type[Base]`` supertype (mypy attr-defined).
_ARTIFACT_MODEL: dict[ArtifactType, tuple[Any, Any]] = {
    ArtifactType.EQUITY_CURVE: (ResultEquityPoint, ResultEquityPoint.seq),
    ArtifactType.TRADE_LEDGER: (TradeLedgerRow, TradeLedgerRow.seq),
    ArtifactType.SIGNAL_EVENTS: (SignalEventRow, SignalEventRow.seq),
    ArtifactType.DIAGNOSTICS: (DiagnosticArtifact, DiagnosticArtifact.diagnostic_id),
}


async def load_source_rows(
    session: AsyncSession, *, result_id: str, export_type: ExportType
) -> list[dict[str, Any]]:
    """The immutable source rows for an export, in stable order (doc 15 §8.5, §14)."""
    if export_type is ExportType.SUMMARY:
        summary = (
            (
                await session.execute(
                    select(ResultSummary).where(ResultSummary.result_id == result_id)
                )
            )
            .scalars()
            .first()
        )
        if summary is None:
            return []
        return [
            {
                "symbol": summary.symbol,
                "timeframe": summary.timeframe,
                "period_start": summary.period_start,
                "period_end": summary.period_end,
                "total_trades": summary.total_trades,
                "headline": summary.headline,
            }
        ]
    artifact_type = _EXPORT_TO_ARTIFACT[export_type]
    model, order_col = _ARTIFACT_MODEL[artifact_type]
    stmt = select(model).where(model.result_id == result_id).order_by(order_col.asc())
    rows = (await session.execute(stmt)).scalars().all()
    return [project_row(artifact_type, row) for row in rows]


async def create_export(
    session: AsyncSession,
    *,
    export_id: str,
    result_id: str,
    export_type: ExportType,
    export_format: ExportFormat,
    source_manifest_hash: str,
    object_key: str,
    checksum: str,
    schema_version: str,
    row_count: int,
    filter_spec: dict[str, Any] | None,
    created_by_principal_id: str | None,
) -> ExportArtifact:
    """Insert the export metadata row (status='complete'). Flushes for the id."""
    export = ExportArtifact(
        export_id=export_id,
        result_id=result_id,
        export_type=export_type,
        export_format=export_format,
        source_manifest_hash=source_manifest_hash,
        object_key=object_key,
        checksum=checksum,
        schema_version=schema_version,
        row_count=row_count,
        filter_spec=filter_spec,
        status="complete",
        created_by_principal_id=created_by_principal_id,
    )
    session.add(export)
    await session.flush()
    return export


async def get_export(session: AsyncSession, export_id: str) -> ExportArtifact | None:
    return await session.get(ExportArtifact, export_id)


async def list_exports(session: AsyncSession, result_id: str) -> list[ExportArtifact]:
    stmt = (
        select(ExportArtifact)
        .where(ExportArtifact.result_id == result_id)
        .order_by(ExportArtifact.created_at.desc(), ExportArtifact.export_id.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


__all__ = ["create_export", "get_export", "list_exports", "load_source_rows"]
