"""Resolve a pinned market revision to its processed bar source (INF-12).

The RUN manifest pins an exact ``market_revision_id``; this query maps that pin
to the content-addressed processed Parquet asset the Data/Backtest worker will
stream in bounded batches. Read-only — never touches 'latest', never re-reads
the Mainboard (doc 15 no-latest-leak contract).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.s3.parquet_stream import DEFAULT_BATCH_SIZE, stream_processed_batches
from entropia.shared.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class BarSourceRef:
    """Everything a worker needs to stream one pinned revision's bars."""

    entity_id: str
    revision_id: str
    object_key: str
    content_digest: str
    size_bytes: int
    row_count: int | None


async def resolve_bar_source(session: AsyncSession, *, market_revision_id: str) -> BarSourceRef:
    """Map a pinned market revision to its processed Parquet asset."""
    asset = await md_repo.get_processed_asset_for_revision(session, market_revision_id)
    if asset is None:
        raise NotFoundError(
            f"No processed asset exists for market revision '{market_revision_id}'."
        )
    return BarSourceRef(
        entity_id=asset.entity_id,
        revision_id=market_revision_id,
        object_key=asset.object_key,
        content_digest=asset.content_digest,
        size_bytes=asset.size_bytes,
        row_count=asset.row_count,
    )


def iter_bar_batches(
    source: BarSourceRef,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    columns: list[str] | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Stream the resolved source's rows in bounded batches (worker plane only)."""
    yield from stream_processed_batches(source.object_key, batch_size=batch_size, columns=columns)


__all__ = ["BarSourceRef", "iter_bar_batches", "resolve_bar_source"]
