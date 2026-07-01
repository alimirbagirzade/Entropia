"""Results History server read model (Stage 5b, doc 16 §8, §9.3, §9.4).

The authoritative history index over immutable ``backtest_result`` rows — NOT the
V18 in-memory array or the current Mainboard (doc 16 §15). The list is filtered to
``deletion_state='active'`` results only; a result only ever exists for a succeeded
run (CR-03), so failed/cancelled runs never produce a history row (doc 16 §9.2).
Visibility is pushed into SQL (owner or Admin) so the ``has_more``/cursor count the
authorized set. Sorting is on the CANONICAL NUMERIC ``metric_value`` (never the
rounded card string), nulls last, with a deterministic ``result_id`` tie-break
(doc 16 §9.3). Compare reads two immutable manifest excerpts and flags any context
difference — it never auto-ranks a "winner" (doc 16 §8.3).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.history import (
    KEY_METRIC_KEYS,
    SORT_SPECS,
    HistorySort,
    SortSpec,
    decode_cursor,
    diff_manifest_contexts,
    encode_cursor,
    extract_manifest_context,
    normalize_sort_key,
)
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import can_edit, ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import EntityRegistry
from entropia.infrastructure.postgres.models.backtest import (
    BacktestResult,
    MetricValueRow,
    ResultSummary,
)
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.shared.errors import (
    BacktestResultNotFoundError,
    CompareRequiresTwoDistinctResultsError,
    CompositionNotFoundError,
    CursorInvalidError,
)

_ACTIVE = "active"


# --------------------------------------------------------------------------- #
# History list + sort + cursor                                                #
# --------------------------------------------------------------------------- #


async def list_backtest_results(
    session: AsyncSession,
    actor: Actor,
    *,
    sort: str | None = None,
    cursor: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Cursor-paginated, policy-filtered immutable result index (doc 16 §9.3)."""
    require_authenticated(actor)
    sort_key = normalize_sort_key(sort)
    spec = SORT_SPECS[sort_key]

    stmt = _visible_results_stmt(actor)
    stmt = _apply_sort_and_keyset(stmt, sort_key, spec, cursor)
    stmt = stmt.limit(limit + 1)

    rows = (await session.execute(stmt)).all()
    has_more = len(rows) > limit
    page = rows[:limit]

    result_ids = [row[0].result_id for row in page]
    digests = await _load_digests(session, result_ids)
    summaries = await _load_summaries(session, result_ids)

    items = [
        _row_dto(
            result,
            owner=owner,
            actor=actor,
            digest=digests.get(result.result_id, {}),
            summary=summaries.get(result.result_id),
        )
        for (result, owner, _sort_value) in page
    ]

    next_cursor = _next_cursor(sort_key, spec, page) if has_more else None
    return {
        "items": items,
        "next_cursor": next_cursor,
        "query_fingerprint": str(sort_key),
        "sort": str(sort_key),
    }


def _visible_results_stmt(actor: Actor) -> Select[Any]:
    """Active results whose composition the actor may view (owner or Admin)."""
    stmt = (
        select(BacktestResult, EntityRegistry.owner_principal_id)
        .join(EntityRegistry, EntityRegistry.entity_id == BacktestResult.workspace_entity_id)
        .where(
            BacktestResult.deletion_state == _ACTIVE,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
        )
    )
    if not actor.is_admin:
        stmt = stmt.where(EntityRegistry.owner_principal_id == actor.principal_id)
    return stmt


def _apply_sort_and_keyset(
    stmt: Select[Any], sort_key: HistorySort, spec: SortSpec, cursor: str | None
) -> Select[Any]:
    tie = BacktestResult.result_id.desc()
    if spec.metric_key is None:
        sort_col = BacktestResult.created_at
        stmt = stmt.add_columns(sort_col.label("sort_value"))
        if cursor is not None:
            decoded = decode_cursor(cursor, sort=sort_key)
            last_dt = _parse_dt(decoded.last_value)
            stmt = stmt.where(
                or_(
                    sort_col < last_dt,
                    and_(sort_col == last_dt, BacktestResult.result_id < decoded.last_result_id),
                )
            )
        return stmt.order_by(sort_col.desc(), tie)

    mv = MetricValueRow
    # OUTER join (not inner): a result missing a metric_value row for this key must
    # sort into the NULL tail, never silently vanish from the index (doc 16 §9.2 —
    # every active succeeded result is indexed; a non-computed metric is NULL, L4).
    stmt = stmt.outerjoin(
        mv,
        and_(mv.result_id == BacktestResult.result_id, mv.metric_key == spec.metric_key),
    ).add_columns(mv.value.label("sort_value"))
    if cursor is not None:
        decoded = decode_cursor(cursor, sort=sort_key)
        if decoded.last_value is None:
            # Already inside the null tail: only smaller-id null rows remain.
            stmt = stmt.where(
                and_(mv.value.is_(None), BacktestResult.result_id < decoded.last_result_id)
            )
        else:
            last_val = _parse_decimal(decoded.last_value)
            beyond = mv.value < last_val if spec.descending else mv.value > last_val
            stmt = stmt.where(
                or_(
                    beyond,
                    and_(mv.value == last_val, BacktestResult.result_id < decoded.last_result_id),
                    mv.value.is_(None),  # nulls always sort after any non-null value
                )
            )
    ordered = mv.value.desc() if spec.descending else mv.value.asc()
    return stmt.order_by(ordered.nulls_last(), tie)


def _next_cursor(sort_key: HistorySort, spec: SortSpec, page: Sequence[Any]) -> str | None:
    if not page:
        return None
    last = page[-1]
    result = last[0]
    sort_value = last[-1]
    if spec.metric_key is None:
        last_value: str | None = sort_value.isoformat()
    else:
        last_value = None if sort_value is None else str(sort_value)
    return encode_cursor(sort_key, last_value=last_value, last_result_id=result.result_id)


# --------------------------------------------------------------------------- #
# Comparison context                                                          #
# --------------------------------------------------------------------------- #


async def compare_backtest_results(
    session: AsyncSession,
    actor: Actor,
    *,
    result_ids: list[str],
) -> dict[str, Any]:
    """Read-only comparison of exactly two distinct visible results (doc 16 §8.3)."""
    require_authenticated(actor)
    if len(result_ids) != 2 or result_ids[0] == result_ids[1]:
        raise CompareRequiresTwoDistinctResultsError()

    contexts: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []
    for result_id in result_ids:
        result = await bt_repo.get_result(session, result_id)
        if result is None or result.deletion_state != _ACTIVE:
            raise BacktestResultNotFoundError()
        await _ensure_can_view_workspace(session, actor, result.workspace_entity_id)
        snapshot = await bt_repo.get_manifest_snapshot(session, result_id)
        summary = await bt_repo.get_summary(session, result_id)
        metrics = await bt_repo.list_metric_values(session, result_id)
        contexts.append(extract_manifest_context(snapshot.manifest if snapshot else None))
        payloads.append(
            {
                "result_id": result.result_id,
                "engine_version": result.engine_version,
                "manifest_hash": result.manifest_hash,
                "summary": _summary_projection(summary),
                "key_metrics": _digest_from_rows(metrics),
            }
        )

    diff = diff_manifest_contexts(contexts[0], contexts[1])
    return {"results": payloads, "context": diff, "context_differs": diff["context_differs"]}


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


async def _ensure_can_view_workspace(
    session: AsyncSession, actor: Actor, workspace_entity_id: str
) -> None:
    workspace = await mb_repo.get_workspace(session, workspace_entity_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    ensure_can_view(actor, owner_principal_id=workspace.owner_principal_id, visibility="private")


async def _load_digests(session: AsyncSession, result_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not result_ids:
        return {}
    stmt = select(MetricValueRow).where(
        MetricValueRow.result_id.in_(result_ids),
        MetricValueRow.metric_key.in_(KEY_METRIC_KEYS),
    )
    grouped: dict[str, dict[str, Any]] = {}
    for row in (await session.execute(stmt)).scalars().all():
        grouped.setdefault(row.result_id, {})[row.metric_key] = _metric_cell(row)
    return grouped


async def _load_summaries(session: AsyncSession, result_ids: list[str]) -> dict[str, ResultSummary]:
    if not result_ids:
        return {}
    stmt = select(ResultSummary).where(ResultSummary.result_id.in_(result_ids))
    return {row.result_id: row for row in (await session.execute(stmt)).scalars().all()}


def _row_dto(
    result: BacktestResult,
    *,
    owner: str | None,
    actor: Actor,
    digest: dict[str, Any],
    summary: ResultSummary | None,
) -> dict[str, Any]:
    return {
        "result_id": result.result_id,
        "display_title": f"Backtest Result {result.result_id}",
        "composition_context": {
            "composition_id": result.workspace_entity_id,
            "composition_fingerprint": result.composition_fingerprint,
        },
        "key_metrics": {key: digest.get(key) for key in KEY_METRIC_KEYS},
        # Not separately pinned in the V1 manifest — honest null, never fabricated.
        "market_data_revision_summary": None,
        "timeframe": summary.timeframe if summary is not None else None,
        "backtest_range": {
            "start": summary.period_start if summary is not None else None,
            "end": summary.period_end if summary is not None else None,
        },
        "manifest_hash": result.manifest_hash,
        "engine_version": result.engine_version,
        "completed_at_utc": _iso(result.created_at),
        "materialization_status": "complete",
        "allowed_actions": {
            "view": True,
            "compare": True,
            "export": True,
            "soft_delete": can_edit(actor, owner_principal_id=owner),
        },
    }


def _digest_from_rows(rows: list[MetricValueRow]) -> dict[str, Any]:
    digest = {
        row.metric_key: _metric_cell(row) for row in rows if row.metric_key in KEY_METRIC_KEYS
    }
    return {key: digest.get(key) for key in KEY_METRIC_KEYS}


def _metric_cell(row: MetricValueRow) -> dict[str, Any]:
    return {
        "key": row.metric_key,
        "label": row.label,
        "unit": row.unit,
        "value_format": row.value_format,
        "value": _decimal_str(row.value),
        "availability": str(row.availability),
    }


def _summary_projection(summary: ResultSummary | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    return {
        "symbol": summary.symbol,
        "timeframe": summary.timeframe,
        "period_start": summary.period_start,
        "period_end": summary.period_end,
        "total_trades": summary.total_trades,
        "headline": summary.headline,
    }


def _parse_dt(value: str | None) -> datetime:
    if value is None:
        raise CursorInvalidError()
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise CursorInvalidError() from exc


def _parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise CursorInvalidError() from exc


def _decimal_str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


__all__ = ["compare_backtest_results", "list_backtest_results"]
