"""P-09 — Market Data registry digest projection, against a real database.

Finding P-09 (doc 11 §3.3): the registry row must carry Source, Resolution and a
Coverage summary as SERVER TRUTH so a user decides which dataset to open WITHOUT
expanding every row. Source/provider + market + the human resolution are read from
the persisted revision payload the create flow folds them into; a first-class
``resolution_value`` wins over the folded string; coverage is aggregated over the
analysis-written coverage slices and is ``None`` until the dataset is analyzed.

Auto-skips when no PostgreSQL is reachable (tests/integration/conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from entropia.application.commands import market_data as md_cmd
from entropia.application.queries.market_data import list_market_dataset_revisions
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.market_data.enums import MarketDataType, ResolutionKind
from entropia.infrastructure.postgres.models import Principal
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.shared.pagination import PageParams

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_owner(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
        await session.flush()


async def _row_for(session, entity_id: str) -> dict:
    page = await list_market_dataset_revisions(session, OWNER, PageParams(cursor=None, limit=50))
    return next(r for r in page["data"] if r["entity_id"] == entity_id)


async def test_digest_returns_source_market_resolution_and_coverage(session) -> None:
    await _seed_owner(session)
    root, revision = await md_cmd.create_market_dataset(
        session,
        OWNER,
        market_data_type=MarketDataType.OHLCV,
        payload={
            "source_provider": "Binance Futures",
            "market": "Crypto",
            "resolution": "15m",
        },
        title="BTCUSDT 15m",
    )
    # Two contiguous coverage slices for the head revision (as the analysis job writes).
    md_repo.add_coverage_slice(
        session,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        start_at=datetime(2026, 1, 1, tzinfo=UTC),
        end_at=datetime(2026, 3, 31, tzinfo=UTC),
        row_count=600,
    )
    md_repo.add_coverage_slice(
        session,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        start_at=datetime(2026, 4, 1, tzinfo=UTC),
        end_at=datetime(2026, 6, 30, tzinfo=UTC),
        row_count=400,
    )
    await session.commit()

    row = await _row_for(session, root.entity_id)
    assert row["source_provider"] == "Binance Futures"
    assert row["market"] == "Crypto"
    assert row["resolution"] == "15m"
    coverage = row["coverage"]
    assert coverage is not None
    assert coverage["start_at"].startswith("2026-01-01")
    assert coverage["end_at"].startswith("2026-06-30")
    assert coverage["row_count"] == 1000  # 600 + 400 summed across both slices
    assert coverage["slice_count"] == 2


async def test_digest_coverage_absent_until_analyzed(session) -> None:
    await _seed_owner(session)
    root, _ = await md_cmd.create_market_dataset(
        session,
        OWNER,
        market_data_type=MarketDataType.OHLCV,
        payload={"source_provider": "Kaiko"},
    )
    await session.commit()

    row = await _row_for(session, root.entity_id)
    # No coverage slices yet -> honest None (client renders "—"), never fabricated.
    assert row["coverage"] is None
    assert row["source_provider"] == "Kaiko"
    # market/resolution absent from the payload -> honest None, not an id-derived guess.
    assert row["market"] is None
    assert row["resolution"] is None


async def test_digest_prefers_first_class_resolution_over_payload(session) -> None:
    await _seed_owner(session)
    root, revision = await md_cmd.create_market_dataset(
        session,
        OWNER,
        market_data_type=MarketDataType.OHLCV,
        payload={"resolution": "15m"},
    )
    # A revision that declares a first-class resolution wins over the folded value.
    revision.resolution_value = "1h"
    revision.resolution_kind = ResolutionKind.BAR
    await session.commit()

    row = await _row_for(session, root.entity_id)
    assert row["resolution"] == "1h"
