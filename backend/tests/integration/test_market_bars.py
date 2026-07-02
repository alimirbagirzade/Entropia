"""post-V1 dilim A — pinned revision -> processed bar source (INF-12 resolution).

Auto-skips without PostgreSQL. Proves the resolve line the backtest worker will
use: a pinned market revision maps to its content-addressed processed Parquet
asset; a re-processed revision resolves to the NEWEST asset; a revision without
a processed asset is a clean NOT_FOUND (never a fabricated source).
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.queries.market_bars import resolve_bar_source
from entropia.domain.market_data.enums import MarketDataType
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.shared.errors import NotFoundError

pytestmark = pytest.mark.integration


async def _dataset(session: AsyncSession) -> tuple[str, str]:
    root, revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        market_data_type=MarketDataType.OHLCV,
        payload={"note": "bars"},
    )
    await session.flush()
    return root.entity_id, revision.revision_id


async def test_resolves_pinned_revision_to_processed_asset(session: AsyncSession) -> None:
    entity_id, revision_id = await _dataset(session)
    md_repo.add_processed_asset(
        session,
        entity_id=entity_id,
        object_key=f"market/processed/{entity_id}/aaa.parquet",
        content_digest="aaa",
        size_bytes=1234,
        revision_id=revision_id,
        row_count=50_000,
    )
    await session.flush()

    source = await resolve_bar_source(session, market_revision_id=revision_id)

    assert source.object_key == f"market/processed/{entity_id}/aaa.parquet"
    assert source.content_digest == "aaa"
    assert source.row_count == 50_000
    assert source.entity_id == entity_id


async def test_reprocessed_revision_resolves_to_newest_asset(session: AsyncSession) -> None:
    entity_id, revision_id = await _dataset(session)
    first = md_repo.add_processed_asset(
        session,
        entity_id=entity_id,
        object_key=f"market/processed/{entity_id}/old.parquet",
        content_digest="old",
        size_bytes=10,
        revision_id=revision_id,
    )
    await session.flush()
    await asyncio.sleep(0.005)  # ULID ids are time-ordered across ms, random within one
    second = md_repo.add_processed_asset(
        session,
        entity_id=entity_id,
        object_key=f"market/processed/{entity_id}/new.parquet",
        content_digest="new",
        size_bytes=20,
        revision_id=revision_id,
    )
    await session.flush()
    assert first.asset_id != second.asset_id

    source = await resolve_bar_source(session, market_revision_id=revision_id)
    assert source.content_digest == "new"


async def test_missing_processed_asset_is_not_found(session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await resolve_bar_source(session, market_revision_id="mrev_ghost")
