"""P-06 — Package Library Market + Timeframe catalog facets (doc 08 §3.2, finding P-06).

Exercised against a real database (auto-skips without PostgreSQL). Covers the derived
``market_scope`` / ``timeframe_scope`` projection (ESP -> System; a declared
``input_contract`` scope; the UNSPECIFIED default), server-side WHERE filtering on each
facet, and the documented Type + Market + Timeframe + Rationale acceptance query — the
facet is server-queryable, not a fabricated no-op or "absent by design".
"""

from __future__ import annotations

import pytest

from entropia.application.queries import library as library_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.catalog import parse_catalog_filters
from entropia.infrastructure.postgres.models import Principal
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.pagination import PageParams

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_principal(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _create_pkg(
    session,
    *,
    kind: PackageKind,
    name: str,
    market_scope: str | None = None,
    timeframe_scope: str | None = None,
    family: dict | None = None,
) -> str:
    # market_scope / timeframe_scope live in the revision input_contract (forward-
    # compatible with a create flow that declares them); the projection derives the
    # catalog facet from them + the package kind.
    input_contract: dict = {"name": name}
    if market_scope is not None:
        input_contract["market_scope"] = market_scope
    if timeframe_scope is not None:
        input_contract["timeframe_scope"] = timeframe_scope
    root, _detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        package_kind=kind,
        input_contract=input_contract,
        output_contract={"output_kinds": ["signal"]},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.PUBLISHED,
        rationale_family_snapshot=family,
    )
    return root.entity_id


async def _list(session, **filter_kwargs):
    return await library_query.list_packages(
        session, USER1, PageParams(limit=50), filters=parse_catalog_filters(**filter_kwargs)
    )


async def _ids(session, **filter_kwargs) -> set[str]:
    return {row["entity_id"] for row in (await _list(session, **filter_kwargs))["data"]}


async def test_scope_projection_esp_is_system_others_derive_or_unspecified(session) -> None:
    await _seed_principal(session)
    esp = await _create_pkg(session, kind=PackageKind.EMBEDDED_SYSTEM, name="Resolver")
    declared = await _create_pkg(
        session,
        kind=PackageKind.STRATEGY,
        name="BTC Reversal",
        market_scope="BTCUSDT",
        timeframe_scope="explicit",
    )
    bare = await _create_pkg(session, kind=PackageKind.INDICATOR, name="RSI")
    await session.commit()

    rows = {row["entity_id"]: row for row in (await _list(session))["data"]}
    # ESP is System / Not applicable for both facets (never fabricated, finding P-06).
    assert rows[esp]["market_scope"] == "system"
    assert rows[esp]["timeframe_scope"] == "system"
    # A declared scope is projected (normalized so it matches the server filter exactly).
    assert rows[declared]["market_scope"] == "btcusdt"
    assert rows[declared]["timeframe_scope"] == "explicit"
    # A package that declares no scope defaults to UNSPECIFIED, never System.
    assert rows[bare]["market_scope"] == "unspecified"
    assert rows[bare]["timeframe_scope"] == "unspecified"


async def test_market_filter_is_server_side(session) -> None:
    await _seed_principal(session)
    btc = await _create_pkg(session, kind=PackageKind.STRATEGY, name="BTC", market_scope="BTCUSDT")
    esp = await _create_pkg(session, kind=PackageKind.EMBEDDED_SYSTEM, name="Resolver")
    bare = await _create_pkg(session, kind=PackageKind.INDICATOR, name="RSI")
    await session.commit()

    # Case-insensitive open market match -> only the declared row.
    assert await _ids(session, market="btcusdt") == {btc}
    # System market -> only the ESP (the System sentinel).
    assert await _ids(session, market="system") == {esp}
    # Unspecified -> the non-ESP package that declared no scope.
    assert await _ids(session, market="unspecified") == {bare}
    # A market no package carries is an empty page, never an error (values not hidden).
    assert await _ids(session, market="ethusdt") == set()


async def test_timeframe_filter_is_server_side(session) -> None:
    await _seed_principal(session)
    multi = await _create_pkg(
        session, kind=PackageKind.INDICATOR, name="Trend", timeframe_scope="multi"
    )
    esp = await _create_pkg(session, kind=PackageKind.EMBEDDED_SYSTEM, name="Resolver")
    bare = await _create_pkg(session, kind=PackageKind.CONDITION, name="Cross")
    await session.commit()

    assert await _ids(session, timeframe="multi") == {multi}
    assert await _ids(session, timeframe="system") == {esp}
    assert await _ids(session, timeframe="unspecified") == {bare}


async def test_type_market_timeframe_rationale_acceptance_query(session) -> None:
    # Finding P-06 acceptance: the user performs the documented composite query and
    # receives exactly the server-filtered result — one facet off excludes the row.
    await _seed_principal(session)
    fam = {"rationale_family_id": "rf_reversal", "display_name": "Reversal"}
    target = await _create_pkg(
        session,
        kind=PackageKind.STRATEGY,
        name="BTC Reversal 15m",
        market_scope="BTCUSDT",
        timeframe_scope="explicit",
        family=fam,
    )
    await _create_pkg(
        session,
        kind=PackageKind.INDICATOR,
        name="Wrong type",
        market_scope="BTCUSDT",
        timeframe_scope="explicit",
        family=fam,
    )
    await _create_pkg(
        session,
        kind=PackageKind.STRATEGY,
        name="Wrong market",
        market_scope="ethusdt",
        timeframe_scope="explicit",
        family=fam,
    )
    await _create_pkg(
        session,
        kind=PackageKind.STRATEGY,
        name="Wrong tf",
        market_scope="BTCUSDT",
        timeframe_scope="multi",
        family=fam,
    )
    await _create_pkg(
        session,
        kind=PackageKind.STRATEGY,
        name="Wrong family",
        market_scope="BTCUSDT",
        timeframe_scope="explicit",
    )
    await session.commit()

    result = await _list(
        session,
        package_type="strategy",
        market="btcusdt",
        timeframe="explicit",
        rationale_family_id="rf_reversal",
    )
    assert {row["entity_id"] for row in result["data"]} == {target}
