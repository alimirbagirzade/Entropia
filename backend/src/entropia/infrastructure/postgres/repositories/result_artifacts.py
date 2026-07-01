"""Heavy result-artifact page reads (Stage 5c, doc-15 deferred; doc 15 §3.2, §7).

Read-only, no commits. Each queryable artifact is paginated SERVER-side with a
stable ascending key (``seq`` for equity/ledger/signals, ``diagnostic_id`` for
diagnostics — which has no ``seq``) so a keyset cursor never skips or double-counts
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
    ArtifactType.DIAGNOSTICS: DiagnosticArtifact,
}


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
    if artifact_type is ArtifactType.SIGNAL_EVENTS:
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


def _dstr(value: Any) -> str | None:
    return None if value is None else str(value)


__all__ = ["cursor_key_of", "page_artifacts", "project_row"]
