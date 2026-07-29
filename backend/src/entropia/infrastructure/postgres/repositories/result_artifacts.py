"""Heavy result-artifact page reads (Stage 5c, doc-15 deferred; doc 15 §3.2, §7).

Read-only, no commits. Each queryable artifact is paginated SERVER-side with a
stable ascending key (``seq`` for equity/ledger/signals/filtered, ``diagnostic_id``
for diagnostics — which has no ``seq``) so a keyset cursor never skips or double-counts
a row. Fetches ``limit + 1`` so the caller can detect ``has_more`` without a second
COUNT. A Trade Ledger row is a trade ROOT — legs/fills are not separate rows, so no
root≠leg double count is possible here (doc 15 §14, §9.4).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.artifacts import SEQ_ORDERED_TYPES, ArtifactType
from entropia.infrastructure.postgres.models.backtest import (
    DiagnosticArtifact,
    FilteredEventRow,
    ResultArtifactChecksum,
    ResultEquityPoint,
    SignalEventRow,
    TradeLedgerRow,
)

# Value typed ``Any`` so the per-type column access below is not narrowed to the
# common ``type[Base]`` supertype (mypy attr-defined).
_MODEL: dict[ArtifactType, Any] = {
    ArtifactType.EQUITY_CURVE: ResultEquityPoint,
    ArtifactType.TRADE_LEDGER: TradeLedgerRow,
    ArtifactType.SIGNAL_EVENTS: SignalEventRow,
    ArtifactType.FILTERED_EVENTS: FilteredEventRow,
    ArtifactType.DIAGNOSTICS: DiagnosticArtifact,
}

# Materialization bookkeeping, not artifact content: excluded from the checksum so the
# value a caller re-derives from the rows it was SERVED matches the stored one. Only
# ``diagnostics`` carries one (its ``created_at`` is a server default that does not
# exist yet while the checksum is computed); for the four seq-ordered artifacts this
# is a no-op.
_NON_CONTENT_KEYS = ("created_at",)


def cursor_key_of(artifact_type: ArtifactType, row: Any) -> str:
    """The stable ascending page key for a row (doc 15 §7 server-side ordering)."""
    if artifact_type in SEQ_ORDERED_TYPES:
        return str(row.seq)
    return str(row.diagnostic_id)


async def page_artifacts(
    session: AsyncSession,
    *,
    result_id: str,
    artifact_type: ArtifactType,
    last_key: str | None,
    limit: int,
) -> list[Any]:
    """One keyset page of an artifact type (``limit + 1`` rows for has_more)."""
    model = _MODEL[artifact_type]
    stmt = select(model).where(model.result_id == result_id)
    if artifact_type in SEQ_ORDERED_TYPES:
        order_col = model.seq
        if last_key is not None:
            stmt = stmt.where(model.seq > int(last_key))
    else:
        order_col = model.diagnostic_id
        if last_key is not None:
            stmt = stmt.where(model.diagnostic_id > last_key)
    stmt = stmt.order_by(order_col.asc()).limit(limit + 1)
    return list((await session.execute(stmt)).scalars().all())


def project_row(artifact_type: ArtifactType, row: Any) -> dict[str, Any]:
    """Immutable-row projection for the drill-down list (doc 15 §3.2)."""
    if artifact_type is ArtifactType.EQUITY_CURVE:
        return {
            "seq": row.seq,
            "timestamp": row.timestamp,
            "equity": _dstr(row.equity),
            "drawdown": _dstr(row.drawdown),
            "exposure": _dstr(row.exposure),
        }
    if artifact_type is ArtifactType.TRADE_LEDGER:
        return {
            "seq": row.seq,
            "entry_time": row.entry_time,
            "exit_time": row.exit_time,
            "direction": row.direction,
            "entry_price": _dstr(row.entry_price),
            "exit_price": _dstr(row.exit_price),
            "pnl": _dstr(row.pnl),
            "exit_reason": row.exit_reason,
        }
    if artifact_type in (ArtifactType.SIGNAL_EVENTS, ArtifactType.FILTERED_EVENTS):
        # Same projection for both journals — they are separate ARTIFACTS, not separate
        # row shapes (I-02; doc 15 §3.2 lists them as two drill-downs of one trace
        # vocabulary). ``event_type`` still says which decision class a row is.
        return {
            "seq": row.seq,
            "event_time": row.event_time,
            "event_type": row.event_type,
            "direction": row.direction,
            "detail": row.detail,
        }
    return {
        "diagnostic_id": row.diagnostic_id,
        "kind": row.kind,
        "content": row.content,
        "created_at": row.created_at.isoformat() if row.created_at is not None else None,
    }


def checksum_rows(artifact_type: ArtifactType, rows: list[Any]) -> list[dict[str, Any]]:
    """The full projected rows a checksum is taken over (doc 15 §7, §14).

    The SAME projection the drill-down serves, minus the materialization bookkeeping
    keys — so a caller that paged the whole artifact can re-derive the stored value.
    """
    return [
        {k: v for k, v in project_row(artifact_type, row).items() if k not in _NON_CONTENT_KEYS}
        for row in rows
    ]


async def get_artifact_checksum(
    session: AsyncSession, *, result_id: str, artifact_type: ArtifactType
) -> ResultArtifactChecksum | None:
    """The stored checksum row, or ``None`` for a Result materialized before I-02.

    A missing row is reported as ``null`` by the caller and never back-filled on read:
    a checksum computed now would attest to the rows as they are TODAY, which is
    exactly the tampering the stored value exists to detect (doc 15 §14).
    """
    stmt = select(ResultArtifactChecksum).where(
        ResultArtifactChecksum.result_id == result_id,
        ResultArtifactChecksum.artifact_type == str(artifact_type),
    )
    return (await session.execute(stmt)).scalars().first()


def _dstr(value: Any) -> str | None:
    return None if value is None else str(value)


__all__ = [
    "checksum_rows",
    "cursor_key_of",
    "get_artifact_checksum",
    "page_artifacts",
    "project_row",
]
