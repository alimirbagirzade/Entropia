"""Heavy result-artifact drill-down query (Stage 5c, doc-15 deferred; doc 15 §7).

Read-only, cursor-paginated over the IMMUTABLE result artifacts (equity / ledger /
signals / diagnostics). Server-side ordering + an opaque keyset cursor (never a
browser offset or rounded-label sort — doc 15 §3.2, §7). Visibility reuses the 5a
workspace-view guard; a soft-deleted / missing result is BACKTEST_RESULT_NOT_FOUND.
A Trade Ledger row is a trade ROOT, so a page never double-counts a leg (doc 15 §14).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.artifacts import (
    decode_artifact_cursor,
    encode_artifact_cursor,
    normalize_artifact_type,
)
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import result_artifacts as ra_repo
from entropia.shared.errors import BacktestResultNotFoundError, CompositionNotFoundError

_ACTIVE = "active"
_DEFAULT_LIMIT = 50


async def query_result_artifact(
    session: AsyncSession,
    actor: Actor,
    *,
    result_id: str,
    artifact_type: str,
    cursor: str | None = None,
    limit: int = _DEFAULT_LIMIT,
) -> dict[str, Any]:
    """One keyset page of a result's immutable artifact (doc 15 §7)."""
    require_authenticated(actor)
    canonical = normalize_artifact_type(artifact_type)

    result = await bt_repo.get_result(session, result_id)
    if result is None or result.deletion_state != _ACTIVE:
        raise BacktestResultNotFoundError()
    await _ensure_can_view_workspace(session, actor, result.workspace_entity_id)

    last_key = (
        decode_artifact_cursor(cursor, artifact_type=canonical).last_key
        if cursor is not None
        else None
    )
    rows = await ra_repo.page_artifacts(
        session,
        result_id=result_id,
        artifact_type=canonical,
        last_key=last_key,
        limit=limit,
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    items = [ra_repo.project_row(canonical, row) for row in page]
    next_cursor = (
        encode_artifact_cursor(canonical, last_key=ra_repo.cursor_key_of(canonical, page[-1]))
        if has_more and page
        else None
    )
    return {
        "result_id": result_id,
        "artifact_type": str(canonical),
        "items": items,
        "next_cursor": next_cursor,
    }


async def _ensure_can_view_workspace(
    session: AsyncSession, actor: Actor, workspace_entity_id: str
) -> None:
    workspace = await mb_repo.get_workspace(session, workspace_entity_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    ensure_can_view(actor, owner_principal_id=workspace.owner_principal_id, visibility="private")


__all__ = ["query_result_artifact"]
