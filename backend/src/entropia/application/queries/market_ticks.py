"""Resolve a pinned tick/trade revision to its processed tick source (F-07i B).

Mirror of ``market_bars`` for the intrabar execution path: the RUN manifest pins
an exact ``tick_revision_id`` per tick-demanding Strategy (resolved at ADMISSION
time from the same approved-revision probe Ready Check used — the worker never
resolves 'newest approved' itself, doc 15 §15 no-'latest' contract); this query
maps that pin to the content-addressed processed Parquet asset the Backtest
worker streams in bounded batches. Read-only, worker plane only.
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
class TickSourceRef:
    """Everything a worker needs to stream one pinned tick revision's prints."""

    entity_id: str
    revision_id: str
    object_key: str
    content_digest: str
    size_bytes: int
    row_count: int | None


async def resolve_tick_source(session: AsyncSession, *, tick_revision_id: str) -> TickSourceRef:
    """Map a pinned tick/trade revision to its processed Parquet asset.

    Approval was proven at Ready Check + pinned at admission; a pin whose processed
    asset is missing at run time is a hard worker failure (``ASSET_UNAVAILABLE``),
    never a silently tickless run."""
    asset = await md_repo.get_processed_asset_for_revision(session, tick_revision_id)
    if asset is None:
        raise NotFoundError(f"No processed asset exists for tick revision '{tick_revision_id}'.")
    return TickSourceRef(
        entity_id=asset.entity_id,
        revision_id=tick_revision_id,
        object_key=asset.object_key,
        content_digest=asset.content_digest,
        size_bytes=asset.size_bytes,
        row_count=asset.row_count,
    )


def iter_tick_batches(
    source: TickSourceRef,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    columns: list[str] | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Stream the resolved tick source's rows in bounded batches (worker plane only).

    The stream is NOT pre-filtered to the backtest range: the engine's tick cursor
    aligns prints to per-bar windows itself (pre-range rows are scanned through and
    dropped; rows after the last replayed bar are simply never pulled), so a range
    filter here could only truncate the LAST bar's intrabar window at the inclusive
    range-end boundary."""
    yield from stream_processed_batches(source.object_key, batch_size=batch_size, columns=columns)


__all__ = ["TickSourceRef", "iter_tick_batches", "resolve_tick_source"]
