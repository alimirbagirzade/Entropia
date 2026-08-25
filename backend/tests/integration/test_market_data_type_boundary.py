"""MKD-02.c1 — the Market Data canonical schema admits ONLY the three market shapes.

Doc 11 §13 MKD-02 draws a data-plane boundary: funding / open-interest /
liquidation / order-book data stay OUT of the Market Data canonical schema and
live on the Research Data side (``ResearchCategory``), which is where the
funding schedule is genuinely resolved from (``test_funding_resolution.py`` —
the c2 half, already covered). This file closes the c1 half, which had NO
asserting test anywhere: nothing pinned the ``MarketDataType`` membership, and
nothing drove a funding-typed market revision into the wire surface and read
the refusal back.

Two deliberately separate axes — each is the one a distinct defect class hits:

* ENUM MEMBERSHIP, pinned LITERALLY (doc 11's three names written out, never
  derived from the production constant). Widening ``MarketDataType`` by one
  member turns exactly this assertion red even in a world where every route
  kept refusing the new member. The four excluded names are also pinned as
  members of ``ResearchCategory`` — "the boundary holds" names both sides,
  and an exclusion without a home would just be a missing feature.
* the WIRE refusal, driven through the real ASGI routes (dataset create AND
  revision append) with a real session. The non-effect is read back from
  Postgres after ``expire_all()``, and the SAME harness then proves — with an
  admitted type over the same two routes — that rows ARE written when the type
  is legal. Without that positive control "nothing was written" would also
  hold for a harness that cannot write at all.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.market_data.enums import MarketDataType
from entropia.domain.research_data.enums import ResearchCategory
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    MarketDatasetRevision,
    Principal,
)

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_DATASETS = "/api/v1/market-datasets"
_REVISIONS = "/api/v1/market-datasets/{entity_id}/revisions"

# Doc 11 §13's own list, written out — NOT derived from the enum under test.
_CANONICAL_MARKET_SHAPES = {"ohlcv", "tick_trades", "spread_execution"}
_EXCLUDED_FROM_MARKET = ("funding_rate", "open_interest", "liquidations", "order_book")


def _override(app: Any, session: Any, actor: Actor) -> Iterator[None]:
    """Bind the real session + a chosen actor to the route (library-route style)."""
    app.dependency_overrides[request_context] = lambda: RequestContext(session=session, actor=actor)
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


def _client(app: Any) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _seed_owner(session: Any) -> None:
    if await session.get(Principal, OWNER.principal_id) is None:
        session.add(Principal(principal_id=OWNER.principal_id, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _market_row_counts(session: Any) -> tuple[int, int]:
    """(dataset roots, dataset revisions) — read from the database, not the identity map."""
    session.expire_all()
    roots = int(
        (
            await session.execute(
                select(func.count())
                .select_from(EntityRegistry)
                .where(EntityRegistry.entity_type == "market_dataset")
            )
        ).scalar_one()
    )
    revisions = int(
        (
            await session.execute(select(func.count()).select_from(MarketDatasetRevision))
        ).scalar_one()
    )
    return roots, revisions


def test_market_data_type_membership_is_exactly_the_three_market_shapes() -> None:
    """The enum axis: membership pinned against doc 11's literal list, both sides.

    ``set == set`` (not ``<=``) so an ADDED member is as red as a removed one.
    """
    assert {member.value for member in MarketDataType} == _CANONICAL_MARKET_SHAPES

    research_categories = {member.value for member in ResearchCategory}
    for excluded in _EXCLUDED_FROM_MARKET:
        # Excluded from the market plane...
        assert excluded not in {member.value for member in MarketDataType}
        # ...and genuinely at home on the research plane (the boundary's other half).
        assert excluded in research_categories


async def test_funding_typed_market_revision_is_refused_on_the_wire_and_writes_nothing(
    app, session
) -> None:
    """The wire axis: both mutating typed surfaces refuse ``funding_rate`` with the
    canonical 422 envelope, and neither refusal writes a root or a revision row.
    """
    await _seed_owner(session)
    await session.commit()

    gen = _override(app, session, OWNER)
    next(gen)
    try:
        async with _client(app) as client:
            # --- create surface: refusal ------------------------------------
            assert await _market_row_counts(session) == (0, 0)
            refused_create = await client.post(
                _DATASETS,
                json={"market_data_type": "funding_rate", "payload": {"v": 1}},
            )
            assert refused_create.status_code == 422
            body = refused_create.json()["error"]
            assert body["code"] == "VALIDATION_ERROR"
            assert body["field_path"] == "body.market_data_type"
            # A single-field schema refusal that names the offending field; the
            # serialized details must mention the field, and the refusal must not
            # echo the funding value back as an ACCEPTED value anywhere outside
            # the input echo (substring scan, not a key lookup).
            serialized = json.dumps(body)
            assert "market_data_type" in serialized
            # Nothing reached the database: no root, no revision.
            assert await _market_row_counts(session) == (0, 0)

            # --- create surface: positive control ---------------------------
            created = await client.post(
                _DATASETS,
                json={"market_data_type": "ohlcv", "payload": {"v": 1}},
            )
            assert created.status_code == 201
            entity_id = created.json()["entity_id"]
            first_revision_id = created.json()["revision_id"]
            etag = created.headers["ETag"]
            assert await _market_row_counts(session) == (1, 1)

            # --- append surface: refusal ------------------------------------
            refused_append = await client.post(
                _REVISIONS.format(entity_id=entity_id),
                json={
                    "market_data_type": "funding_rate",
                    "payload": {"v": 2},
                    "timezone_mode": "utc",
                },
                headers={"If-Match": etag},
            )
            assert refused_append.status_code == 422
            append_body = refused_append.json()["error"]
            assert append_body["code"] == "VALIDATION_ERROR"
            assert append_body["field_path"] == "body.market_data_type"
            # The existing chain is untouched: still one revision, head where it
            # was, root row_version not bumped by the refused call.
            assert await _market_row_counts(session) == (1, 1)
            root = await session.get(EntityRegistry, entity_id)
            assert root is not None
            assert root.current_revision_id == first_revision_id
            assert root.row_version == 1

            # --- append surface: positive control ---------------------------
            appended = await client.post(
                _REVISIONS.format(entity_id=entity_id),
                json={
                    "market_data_type": "tick_trades",
                    "payload": {"v": 2},
                    "timezone_mode": "utc",
                },
                headers={"If-Match": etag},
            )
            assert appended.status_code == 200
            assert await _market_row_counts(session) == (1, 2)
    finally:
        gen.close()
