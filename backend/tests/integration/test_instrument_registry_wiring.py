"""R1 (GAP-16) — instrument-registry resolution wired into the ingest/save flows.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Proves the actual goal (Master §8.1): the SAME symbol resolves to DIFFERENT
canonical ``instrument_id``s for spot vs perpetual across Trading Signal import,
Trade Log import and Strategy save; an unresolvable scope fails closed (422) on
every flow and never enqueues/persists a silent free-text instrument.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import instrument as instrument_cmd
from entropia.application.commands import strategy_draft as strat_cmd
from entropia.application.commands import trade_log as tl_cmd
from entropia.application.commands import trading_signal as ts_cmd
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import Job, Principal, StrategyRevision
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import InstrumentScopeUnresolvableError
from tests.integration.test_strategy_integration import _valid_payload

pytestmark = pytest.mark.integration

USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
SPOT = {"venue_id": "binance", "symbol": "BTCUSDT", "contract_type": "spot"}
PERP = {"venue_id": "binance", "symbol": "BTCUSDT", "contract_type": "perpetual"}
MISSING = {"venue_id": "binance", "symbol": "XRPUSDT", "contract_type": "spot"}
_CSV = b"source_record_id,event_time\nr1,2024-05-01T10:00:00Z\n"


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    """In-process object storage so the upload step runs without MinIO."""
    store: dict[str, bytes] = {}

    def _put(source_asset_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"source/{source_asset_id}/{digest}"
        store[key] = data
        return key, digest

    monkeypatch.setattr(datasets, "put_source_asset_bytes", _put)
    return store


async def _seed_principal(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _register_spot_and_perp(session) -> tuple[str, str]:
    spot = await instrument_cmd.register_instrument(
        session,
        USER,
        venue_id="binance",
        symbol="BTCUSDT",
        contract_type="spot",
        display_name="BTCUSDT Spot",
    )
    perp = await instrument_cmd.register_instrument(
        session,
        USER,
        venue_id="binance",
        symbol="BTCUSDT",
        contract_type="perpetual",
        display_name="BTCUSDT Perpetual",
    )
    await session.commit()
    return spot["instrument_id"], perp["instrument_id"]


async def _job_instrument_id(session, job_id: str) -> str:
    job = await session.get(Job, job_id)
    assert job is not None and job.payload is not None
    return str(job.payload["instrument_id"])


# --------------------------------------------------------------------------- #
# Trading Signal import                                                        #
# --------------------------------------------------------------------------- #


async def test_trading_signal_import_resolves_spot_vs_perp(session, fake_object_store) -> None:
    await _seed_principal(session)
    spot_id, perp_id = await _register_spot_and_perp(session)

    upload = await ts_cmd.upload_source_asset(
        session, USER, content=_CSV, original_filename="signals.csv"
    )
    await session.commit()

    spot_job = await ts_cmd.request_trading_signal_import(
        session,
        USER,
        source_asset_id=upload["source_asset_id"],
        instrument_id="BTCUSDT",
        instrument_scope=SPOT,
        idempotency_key="ts-spot",
    )
    perp_job = await ts_cmd.request_trading_signal_import(
        session,
        USER,
        source_asset_id=upload["source_asset_id"],
        instrument_id="BTCUSDT",
        instrument_scope=PERP,
        idempotency_key="ts-perp",
    )
    await session.commit()

    # Same free-text symbol, but the durable payload carries the two DISTINCT
    # canonical instruments (spot vs perpetual can no longer collide).
    assert await _job_instrument_id(session, spot_job["job_id"]) == spot_id
    assert await _job_instrument_id(session, perp_job["job_id"]) == perp_id
    assert spot_id != perp_id


async def test_trading_signal_import_unresolvable_scope_fails(session, fake_object_store) -> None:
    await _seed_principal(session)
    await _register_spot_and_perp(session)
    upload = await ts_cmd.upload_source_asset(
        session, USER, content=_CSV, original_filename="signals.csv"
    )
    await session.commit()
    before = int((await session.execute(select(func.count()).select_from(Job))).scalar_one())

    with pytest.raises(InstrumentScopeUnresolvableError):
        await ts_cmd.request_trading_signal_import(
            session,
            USER,
            source_asset_id=upload["source_asset_id"],
            instrument_id="BTCUSDT",
            instrument_scope=MISSING,
        )
    # Fail closed BEFORE enqueue — no durable job was created.
    after = int((await session.execute(select(func.count()).select_from(Job))).scalar_one())
    assert after == before


# --------------------------------------------------------------------------- #
# Trade Log import                                                             #
# --------------------------------------------------------------------------- #


async def test_trade_log_import_resolves_spot_vs_perp(session, fake_object_store) -> None:
    await _seed_principal(session)
    spot_id, perp_id = await _register_spot_and_perp(session)

    upload = await tl_cmd.upload_source_asset(
        session, USER, content=_CSV, original_filename="trades.csv"
    )
    await session.commit()

    spot_job = await tl_cmd.request_trade_log_import(
        session,
        USER,
        source_asset_id=upload["source_asset_id"],
        instrument_id="BTCUSDT",
        instrument_scope=SPOT,
        idempotency_key="tl-spot",
    )
    perp_job = await tl_cmd.request_trade_log_import(
        session,
        USER,
        source_asset_id=upload["source_asset_id"],
        instrument_id="BTCUSDT",
        instrument_scope=PERP,
        idempotency_key="tl-perp",
    )
    await session.commit()

    assert await _job_instrument_id(session, spot_job["job_id"]) == spot_id
    assert await _job_instrument_id(session, perp_job["job_id"]) == perp_id
    assert spot_id != perp_id


async def test_trade_log_import_unresolvable_scope_fails(session, fake_object_store) -> None:
    await _seed_principal(session)
    await _register_spot_and_perp(session)
    upload = await tl_cmd.upload_source_asset(
        session, USER, content=_CSV, original_filename="trades.csv"
    )
    await session.commit()
    before = int((await session.execute(select(func.count()).select_from(Job))).scalar_one())

    with pytest.raises(InstrumentScopeUnresolvableError):
        await tl_cmd.request_trade_log_import(
            session,
            USER,
            source_asset_id=upload["source_asset_id"],
            instrument_id="BTCUSDT",
            instrument_scope=MISSING,
        )
    after = int((await session.execute(select(func.count()).select_from(Job))).scalar_one())
    assert after == before


# --------------------------------------------------------------------------- #
# Strategy save                                                                #
# --------------------------------------------------------------------------- #


async def _save_strategy_with_scope(session, scope: dict[str, Any]) -> str:
    payload = _valid_payload()
    payload["data"]["instrument_scope"] = scope
    draft = await strat_cmd.create_strategy_draft(
        session,
        USER,
        display_name="Scoped Strategy",
        rationale_family_id="ratfam_int",
        initial_payload=payload,
    )
    await session.flush()
    saved = await strat_cmd.save_strategy_revision(
        session, USER, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.commit()
    revision = await session.get(StrategyRevision, saved["strategy_revision_id"])
    assert revision is not None
    return str(revision.payload["data"]["instrument_id"])


async def test_strategy_save_resolves_spot_vs_perp(session) -> None:
    await _seed_principal(session)
    spot_id, perp_id = await _register_spot_and_perp(session)

    spot_saved = await _save_strategy_with_scope(session, SPOT)
    perp_saved = await _save_strategy_with_scope(session, PERP)

    # The free-text "BTCUSDT" in the config was rewritten to the canonical instrument.
    assert spot_saved == spot_id
    assert perp_saved == perp_id
    assert spot_saved != perp_saved


async def test_strategy_save_unresolvable_scope_fails(session) -> None:
    await _seed_principal(session)
    await _register_spot_and_perp(session)
    payload = _valid_payload()
    payload["data"]["instrument_scope"] = MISSING
    draft = await strat_cmd.create_strategy_draft(
        session,
        USER,
        display_name="Bad Scope Strategy",
        rationale_family_id="ratfam_int",
        initial_payload=payload,
    )
    await session.flush()

    with pytest.raises(InstrumentScopeUnresolvableError):
        await strat_cmd.save_strategy_revision(
            session, USER, draft_id=draft["draft_id"], expected_draft_row_version=0
        )
