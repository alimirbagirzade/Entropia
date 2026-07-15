"""Resolve a pinned market revision to its processed bar source (INF-12).

The RUN manifest pins an exact ``market_revision_id``; this query maps that pin
to the content-addressed processed Parquet asset the Data/Backtest worker will
stream in bounded batches. Read-only — never touches 'latest', never re-reads
the Mainboard (doc 15 no-latest-leak contract).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
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


def parse_range_bound(value: str) -> datetime | None:
    """Parse a ``backtest_range`` boundary to a comparable UTC ``datetime`` (F-05).

    ``None`` when the value is not a valid ISO-8601 timestamp — the caller must
    treat that as an explicit reject, never a silently-ignored filter. A bound
    with no offset/zone is treated as UTC, matching the documented "engine
    manifest UTC normalization" (Master Technical Reference, Backtest Range)."""
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _bar_timestamp(row: dict[str, Any], lo: datetime, hi: datetime) -> bool:
    """Whether a raw bar row's ``timestamp`` falls within ``[lo, hi]`` inclusive.

    An unparseable/missing timestamp is dropped rather than guessed — it can
    never be proven in-range (fail-closed exclusion, doc 02 §2 boundary
    semantics: ``start <= end`` inclusive)."""
    raw_ts = row.get("timestamp")
    if raw_ts is None:
        return False
    parsed = parse_range_bound(str(raw_ts))
    return parsed is not None and lo <= parsed <= hi


def filter_bars_by_range(
    batches: Iterator[list[dict[str, Any]]], *, start: str, end: str
) -> Iterator[list[dict[str, Any]]]:
    """Physically filter the bar stream to ``[start, end]`` inclusive (F-05).

    Applied at the worker boundary so the engine itself stays a pure function of
    the bars it is handed — it never sees a bar outside the selected range. Empty
    batches are never yielded, so a fully-excluded stream yields nothing at all
    (the caller detects that and rejects the run rather than materializing an
    empty-but-"succeeded" result)."""
    lo = parse_range_bound(start)
    hi = parse_range_bound(end)
    if lo is None or hi is None or lo > hi:
        return
    for batch in batches:
        kept = [row for row in batch if _bar_timestamp(row, lo, hi)]
        if kept:
            yield kept


__all__ = [
    "BarSourceRef",
    "filter_bars_by_range",
    "iter_bar_batches",
    "parse_range_bound",
    "resolve_bar_source",
]
