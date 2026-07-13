"""GAP-16 canonical instrument registry — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers: register (+1 audit & +1 outbox, ACTIVE + resolution_key + aliases),
duplicate resolution_key rejection, alias/triple resolution, unresolvable scope,
cross-instrument alias conflict, Admin-only deprecate with registry-version OCC,
non-Admin deprecation rejection, list/detail, idempotent register replay, and the
Market Data ingest wiring (instrument_scope -> canonical instrument_id).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import instrument as instrument_cmd
from entropia.application.commands import market_data as md_cmd
from entropia.application.queries import instrument as instrument_query
from entropia.domain.identity import Actor
from entropia.domain.instrument.enums import InstrumentState
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.market_data.enums import MarketDataType
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    InstrumentAlias,
    InstrumentRegistry,
    OutboxEvent,
    Principal,
)
from entropia.infrastructure.postgres.repositories import instrument as instrument_repo
from entropia.shared.errors import (
    InstrumentAlreadyRegisteredError,
    InstrumentDeprecateRequiresAdminError,
    InstrumentRegistryConflictError,
    InstrumentScopeUnresolvableError,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _register_btc_perp(session, *, actor: Actor = OWNER, idempotency_key: str | None = None):
    return await instrument_cmd.register_instrument(
        session,
        actor,
        venue_id="binance",
        symbol="BTCUSDT",
        contract_type="perpetual",
        display_name="BTCUSDT Perpetual",
        base_asset="BTC",
        quote_asset="USDT",
        settlement_asset="USDT",
        multiplier="1",
        market_class="crypto",
        aliases=["BTCUSDT Perpetual", "BTCUSDT.P"],
        idempotency_key=idempotency_key,
    )


async def test_register_inserts_audit_outbox_and_active(session) -> None:
    await _seed_principals(session)
    before_audit = await _count(session, AuditEvent)
    before_outbox = await _count(session, OutboxEvent)

    created = await _register_btc_perp(session)
    await session.commit()

    assert created["state"] == str(InstrumentState.ACTIVE)
    assert created["resolution_key"] == "binance:btcusdt:perpetual"
    assert created["registry_version"] == 1
    assert created["alias_count"] == 2
    assert await _count(session, AuditEvent) == before_audit + 1
    assert await _count(session, OutboxEvent) == before_outbox + 1
    assert await _count(session, InstrumentAlias) == 2

    instrument = await instrument_repo.get_by_resolution_key(session, "binance:btcusdt:perpetual")
    assert instrument is not None
    assert instrument.state == InstrumentState.ACTIVE


async def test_register_duplicate_resolution_key_rejected(session) -> None:
    await _seed_principals(session)
    await _register_btc_perp(session)
    await session.commit()

    with pytest.raises(InstrumentAlreadyRegisteredError):
        await _register_btc_perp(session)


async def test_resolve_by_alias_and_triple(session) -> None:
    await _seed_principals(session)
    created = await _register_btc_perp(session)
    await session.commit()

    by_alias = await instrument_query.resolve_scope(session, alias="BTCUSDT Perpetual")
    assert by_alias["instrument_id"] == created["instrument_id"]

    by_triple = await instrument_query.resolve_scope(
        session, venue_id="Binance", symbol="btcusdt", contract_type="perpetual"
    )
    assert by_triple["instrument_id"] == created["instrument_id"]
    assert by_triple["resolved"] is True


async def test_resolve_unresolvable_scope_raises(session) -> None:
    await _seed_principals(session)
    with pytest.raises(InstrumentScopeUnresolvableError):
        await instrument_query.resolve_scope(session, alias="Nonexistent Instrument")
    with pytest.raises(InstrumentScopeUnresolvableError):
        await instrument_query.resolve_scope(
            session, venue_id="kraken", symbol="XRPUSD", contract_type="spot"
        )


async def test_alias_conflict_across_instruments(session) -> None:
    await _seed_principals(session)
    await _register_btc_perp(session)
    await session.commit()

    other = await instrument_cmd.register_instrument(
        session,
        OWNER,
        venue_id="binance",
        symbol="ETHUSDT",
        contract_type="perpetual",
        display_name="ETHUSDT Perpetual",
    )
    await session.commit()

    # "BTCUSDT Perpetual" already resolves to the BTC instrument.
    with pytest.raises(InstrumentAlreadyRegisteredError):
        await instrument_cmd.add_instrument_alias(
            session, OWNER, instrument_id=other["instrument_id"], alias="BTCUSDT Perpetual"
        )


async def test_deprecate_admin_and_registry_version_occ(session) -> None:
    await _seed_principals(session)
    created = await _register_btc_perp(session)
    await session.commit()

    result = await instrument_cmd.deprecate_instrument(
        session,
        ADMIN,
        instrument_id=created["instrument_id"],
        reason="delisted",
        expected_registry_version=1,
    )
    await session.commit()
    assert result["state"] == str(InstrumentState.DEPRECATED)
    assert result["registry_version"] == 2

    # A deprecated instrument still resolves (historical pins keep reading).
    resolved = await instrument_query.resolve_scope(session, alias="BTCUSDT Perpetual")
    assert resolved["state"] == str(InstrumentState.DEPRECATED)

    # A second deprecate with the now-stale token conflicts.
    with pytest.raises(InstrumentRegistryConflictError):
        await instrument_cmd.deprecate_instrument(
            session,
            ADMIN,
            instrument_id=created["instrument_id"],
            reason="again",
            expected_registry_version=1,
        )


async def test_deprecate_requires_admin(session) -> None:
    await _seed_principals(session)
    created = await _register_btc_perp(session)
    await session.commit()

    with pytest.raises(InstrumentDeprecateRequiresAdminError):
        await instrument_cmd.deprecate_instrument(
            session, OWNER, instrument_id=created["instrument_id"], reason="nope"
        )
    # Untouched — no partial deprecation.
    instrument = await instrument_repo.get_by_resolution_key(session, "binance:btcusdt:perpetual")
    assert instrument is not None
    assert instrument.state == InstrumentState.ACTIVE
    assert instrument.registry_version == 1


async def test_list_and_detail(session) -> None:
    await _seed_principals(session)
    await _register_btc_perp(session)
    await instrument_cmd.register_instrument(
        session,
        OWNER,
        venue_id="coinbase",
        symbol="BTC-USD",
        contract_type="spot",
        display_name="BTC-USD Spot",
    )
    await session.commit()

    from entropia.shared.pagination import PageParams

    page = await instrument_query.list_instruments(session, OWNER, PageParams(limit=20))
    keys = [row["resolution_key"] for row in page["data"]]
    # Ordered by resolution_key ascending.
    assert keys == sorted(keys)
    assert "binance:btcusdt:perpetual" in keys
    assert "coinbase:btc-usd:spot" in keys

    instrument = await instrument_repo.get_by_resolution_key(session, "binance:btcusdt:perpetual")
    assert instrument is not None
    detail = await instrument_query.get_instrument_detail(
        session, OWNER, instrument_id=instrument.instrument_id
    )
    assert {a["alias_norm"] for a in detail["aliases"]} == {"btcusdt perpetual", "btcusdt.p"}
    assert detail["row_version"] == 1


async def test_idempotent_register_replay_returns_cached(session) -> None:
    await _seed_principals(session)
    first = await _register_btc_perp(session, idempotency_key="reg-k1")
    await session.commit()
    audit_after_first = await _count(session, AuditEvent)

    second = await _register_btc_perp(session, idempotency_key="reg-k1")
    await session.commit()

    assert second == first
    assert await _count(session, AuditEvent) == audit_after_first
    assert await _count(session, InstrumentRegistry) == 1


async def test_market_dataset_create_resolves_instrument_scope(session) -> None:
    await _seed_principals(session)
    created = await _register_btc_perp(session)
    await session.commit()

    _root, revision = await md_cmd.create_market_dataset(
        session,
        OWNER,
        market_data_type=MarketDataType.OHLCV,
        payload={"source": "unit"},
        title="BTC perp bars",
        instrument_scope={"alias": "BTCUSDT.P"},
    )
    await session.commit()
    assert revision.instrument_id == created["instrument_id"]


async def test_market_dataset_create_unresolvable_scope_fails(session) -> None:
    await _seed_principals(session)
    before = await _count(session, InstrumentRegistry)
    with pytest.raises(InstrumentScopeUnresolvableError):
        await md_cmd.create_market_dataset(
            session,
            OWNER,
            market_data_type=MarketDataType.OHLCV,
            payload={"source": "unit"},
            instrument_scope={"venue_id": "x", "symbol": "y", "contract_type": "spot"},
        )
    # No instrument was created as a side effect of a failed resolution.
    assert await _count(session, InstrumentRegistry) == before
