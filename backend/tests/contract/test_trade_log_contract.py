"""Trade Log API contract tests (doc 05 §2, §8, §12). DB-free.

Asserts the authentication gate (Guest -> 401, no leak) and the pure config
validation that fires BEFORE any DB/object-storage work: a blank provider and a
price-context conflict both surface their typed 422 before ``_require_ready_import``
touches the session. DB-touching flows live in
tests/integration/test_trade_log_persistence.py. DI-override style mirrors
test_trading_signal_contract.py.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role


class _DummySession:
    """Stand-in; guest + pure-validation paths never touch it."""


def _actor(role: Role | None, ptype: PrincipalType, pid: str | None) -> Actor:
    return Actor(principal_id=pid, principal_type=ptype, role=role)


def _override(app: Any, actor: Actor) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=_DummySession(),  # type: ignore[arg-type]
        actor=actor,
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


async def _client(app: Any) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "trade_log",
        "identity": {"display_name": "Binance BTCUSDT trade history Q1"},
        "source": {"provider_name": "Binance Futures export", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btcusdt", "display_symbol": "BTCUSDT"},
        "time_model": {
            "resolution_kind": "event_based",
            "base_timeframe": None,
            "source_timezone": "UTC",
            "normalization_timezone": "UTC",
        },
        "classification": {"rationale_family_id": None},
        "data_quality": {"content_profile": "entry_exit_records_only"},
        "price_policy": {
            "source": "trade_log_entry_exit_price",
            "approved_market_data_revision_ref": None,
        },
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000", "currency": "USDT"},
        "import_binding": {
            "source_asset_id": "srcasset_x",
            "record_batch_revision_id": "tlbatch_x",
        },
    }
    payload.update(overrides)
    return payload


@pytest.mark.contract
async def test_guest_cannot_upload_source_asset(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/trade-logs/source-assets",
                json={"content": "x", "original_filename": "t.csv"},
            )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_guest_cannot_create_trade_log(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/trade-logs", json={"payload": _valid_payload()})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_guest_cannot_read_trade_log(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/trade-logs/wo_x")
        assert resp.status_code == 401
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_blank_provider_rejected_before_db(app) -> None:
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        payload = _valid_payload(source={"provider_name": "  ", "source_kind": "file"})
        async with await _client(app) as c:
            resp = await c.post("/api/v1/trade-logs", json={"payload": payload})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "TRADE_LOG_VALIDATION_FAILED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_price_context_conflict_rejected_before_db(app) -> None:
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        payload = _valid_payload(
            price_policy={
                "source": "ohlcv_intrabar_if_available",
                "approved_market_data_revision_ref": None,
            },
            ohlcv_policy={"use_mode": "ignore"},
        )
        async with await _client(app) as c:
            resp = await c.post("/api/v1/trade-logs", json={"payload": payload})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "PRICE_CONTEXT_CONFLICT"
    finally:
        next(gen, None)
