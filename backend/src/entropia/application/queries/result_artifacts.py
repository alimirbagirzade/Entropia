"""Heavy result-artifact drill-down query (Stage 5c, doc-15 deferred; doc 15 §7).

Read-only, cursor-paginated over the IMMUTABLE result artifacts (equity / ledger /
signals / filtered / diagnostics). Server-side ordering + an opaque keyset cursor (never a
browser offset or rounded-label sort — doc 15 §3.2, §7). Visibility reuses the 5a
workspace-view guard; a soft-deleted / missing result is BACKTEST_RESULT_NOT_FOUND.
A Trade Ledger row is a trade ROOT, so a page never double-counts a leg (doc 15 §14).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.queries import result_access
from entropia.domain.backtest.artifacts import (
    decode_artifact_cursor,
    encode_artifact_cursor,
    normalize_artifact_type,
)
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import result_artifacts as ra_repo
from entropia.shared.errors import BacktestResultNotFoundError

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
    await result_access.ensure_can_view_composition(session, actor, result.workspace_entity_id)

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
    # doc 15 §7 names artifact checksum verification as part of this contract. The
    # checksum covers the WHOLE artifact (not this page), so a caller that walked every
    # page can re-derive it; ``row_count`` is what it should have walked. A Result
    # materialized before I-02 carries no checksum row and honestly reports ``null``
    # rather than a value computed from today's rows.
    stored = await ra_repo.get_artifact_checksum(
        session, result_id=result_id, artifact_type=canonical
    )
    return {
        "result_id": result_id,
        "artifact_type": str(canonical),
        "items": items,
        "next_cursor": next_cursor,
        "row_count": stored.row_count if stored is not None else None,
        "checksum": stored.checksum if stored is not None else None,
        "checksum_schema_version": stored.schema_version if stored is not None else None,
    }


__all__ = ["query_result_artifact"]
