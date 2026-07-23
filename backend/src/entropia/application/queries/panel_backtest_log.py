"""Admin Panel backtest-log read model (doc 19, finding P-14).

The Panel / Logs page's PRIMARY view: the "All User Backtest Logs" table the V18
prototype shows (User · Date · Backtest · Net Profit · ROMAD · Trades). This is the
Admin's answer to "which user ran which backtest" WITHOUT decoding domain events —
a newest-first, cursor-paginated projection over the immutable ``backtest_result``
index, NOT the audit-event stream (that stays the *secondary* technical view in
``log_projection.py``, doc 19 §4.3/§5).

Design invariants:
* Admin-only. ``require_admin_panel`` re-runs here — the route guard is never the
  only check (doc 19 §2, §13).
* Cross-user by design: an Admin sees EVERY user's active succeeded results (a
  result only ever exists for a succeeded run — CR-03/doc 16 §9.2). No owner filter.
* The ``User`` label is the workspace OWNER resolved to a human label, with an
  honest raw-principal-id fallback when no ``human_users`` row exists (never a
  fabricated name — mirrors the W3a "human labels over raw ids" rule).
* Net Profit / ROMAD / Trades come from the canonical ``metric_value`` rows —
  server-truth, NEVER recomputed in the browser. A non-computed metric surfaces its
  availability, never a silent ``0`` (L4).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.agent_lab.cursor import decode_cursor, encode_cursor
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_admin_panel
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import EntityRegistry, HumanUser
from entropia.infrastructure.postgres.models.backtest import BacktestResult, MetricValueRow
from entropia.shared.errors import CursorInvalidError

DEFAULT_BACKTEST_LOG_LIMIT = 25
MAX_BACKTEST_LOG_LIMIT = 100

_ACTIVE = "active"
_CURSOR_NAMESPACE = "admin_backtest_log"
_CURSOR_SEP = "\x1f"

# The three columns the V18 "All User Backtest Logs" table shows besides User/Date.
# Sourced from the canonical metric_value rows so the number the Admin reads is the
# same server-truth Results History sorts on — never a browser re-computation.
LOG_METRIC_KEYS: tuple[str, ...] = ("net_profit", "romad", "total_trades")


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_BACKTEST_LOG_LIMIT
    return max(1, min(limit, MAX_BACKTEST_LOG_LIMIT))


def _encode_cursor(*, created_at_iso: str, result_id: str) -> str:
    """Opaque forward cursor pinned to the newest-first ``(created_at, result_id)``
    ordering. The client cannot construct it; a token built for another projection
    is rejected by its namespace."""
    return encode_cursor(_CURSOR_NAMESPACE, last_key=f"{created_at_iso}{_CURSOR_SEP}{result_id}")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    """Decode into ``(last_created_at, last_result_id)``; a malformed token is a
    ``CURSOR_INVALID`` recovery signal, never a silent reset to page 1."""
    decoded = decode_cursor(cursor, namespace=_CURSOR_NAMESPACE)
    created_at_iso, sep, result_id = decoded.last_key.partition(_CURSOR_SEP)
    if not sep or not created_at_iso or not result_id:
        raise CursorInvalidError()
    try:
        last_at = datetime.fromisoformat(created_at_iso)
    except ValueError as exc:
        raise CursorInvalidError() from exc
    return last_at, result_id


def _apply_keyset(stmt: Select[Any], cursor: str | None) -> Select[Any]:
    """Newest-first on ``(created_at, result_id)`` with a stable ``result_id`` DESC
    tie-break; the cursor carries the composite so equal timestamps never skip or
    repeat a row."""
    stmt = stmt.order_by(BacktestResult.created_at.desc(), BacktestResult.result_id.desc())
    if cursor is None:
        return stmt
    last_at, last_id = _decode_cursor(cursor)
    return stmt.where(
        or_(
            BacktestResult.created_at < last_at,
            and_(
                BacktestResult.created_at == last_at,
                BacktestResult.result_id < last_id,
            ),
        )
    )


async def _load_metrics(session: AsyncSession, result_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Batch-load the log's key metrics for the page (one query, no per-row N+1)."""
    if not result_ids:
        return {}
    stmt = select(MetricValueRow).where(
        MetricValueRow.result_id.in_(result_ids),
        MetricValueRow.metric_key.in_(LOG_METRIC_KEYS),
    )
    grouped: dict[str, dict[str, Any]] = {}
    for row in (await session.execute(stmt)).scalars().all():
        grouped.setdefault(row.result_id, {})[row.metric_key] = _metric_cell(row)
    return grouped


def _metric_cell(row: MetricValueRow) -> dict[str, Any]:
    """The immutable metric cell (mirrors results_history.py). The frontend formats
    it; a ``None`` value with a non-computed availability is honest, not a zero."""
    return {
        "key": row.metric_key,
        "label": row.label,
        "unit": row.unit,
        "value_format": row.value_format,
        "value": None if row.value is None else str(row.value),
        "availability": str(row.availability),
    }


def _row(
    result: BacktestResult,
    *,
    owner_principal_id: str | None,
    username: str | None,
    display_name: str | None,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "result_id": result.result_id,
        # Human label with an honest raw-id fallback (W3a): username/display_name are
        # None when no human_users row resolves the owner — never a fabricated name.
        "user": {
            "principal_id": owner_principal_id,
            "username": username,
            "display_name": display_name,
        },
        "completed_at_utc": result.created_at.isoformat() if result.created_at else None,
        "backtest": {
            "result_id": result.result_id,
            "workspace_entity_id": result.workspace_entity_id,
            "composition_fingerprint": result.composition_fingerprint,
            "display_title": f"Backtest Result {result.result_id}",
        },
        "net_profit": metrics.get("net_profit"),
        "romad": metrics.get("romad"),
        "total_trades": metrics.get("total_trades"),
        "engine_version": result.engine_version,
    }


async def list_admin_backtest_log(
    session: AsyncSession,
    actor: Actor,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Admin-only, cross-user, newest-first cursor page over the immutable backtest
    result index — the Panel / Logs primary "All User Backtest Logs" view (P-14)."""
    require_admin_panel(actor)
    page_limit = _clamp_limit(limit)

    stmt: Select[Any] = (
        select(
            BacktestResult,
            EntityRegistry.owner_principal_id,
            HumanUser.username,
            HumanUser.display_name,
        )
        .join(EntityRegistry, EntityRegistry.entity_id == BacktestResult.workspace_entity_id)
        # OUTER join to the human registry: an active result whose owner has no
        # human_users row (e.g. a purged principal) must still appear with a raw-id
        # fallback, never vanish from the Admin's cross-user log.
        .outerjoin(HumanUser, HumanUser.user_id == EntityRegistry.owner_principal_id)
        .where(
            BacktestResult.deletion_state == _ACTIVE,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
        )
    )
    stmt = _apply_keyset(stmt, cursor).limit(page_limit + 1)

    rows = (await session.execute(stmt)).all()
    has_more = len(rows) > page_limit
    page = rows[:page_limit]

    result_ids = [row[0].result_id for row in page]
    metrics = await _load_metrics(session, result_ids)

    data = [
        _row(
            result,
            owner_principal_id=owner_principal_id,
            username=username,
            display_name=display_name,
            metrics=metrics.get(result.result_id, {}),
        )
        for (result, owner_principal_id, username, display_name) in page
    ]

    next_cursor: str | None = None
    if has_more and page:
        last_result = page[-1][0]
        if last_result.created_at is not None:
            next_cursor = _encode_cursor(
                created_at_iso=last_result.created_at.isoformat(),
                result_id=last_result.result_id,
            )

    return {
        "data": data,
        "meta": {"cursor": next_cursor, "has_more": has_more, "limit": page_limit},
    }


__all__ = [
    "DEFAULT_BACKTEST_LOG_LIMIT",
    "LOG_METRIC_KEYS",
    "MAX_BACKTEST_LOG_LIMIT",
    "list_admin_backtest_log",
]
