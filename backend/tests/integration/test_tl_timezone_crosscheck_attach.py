"""O-28 — the save path refuses an import that ran under a different time zone.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py). The
FULL durable pipeline runs here (upload -> request import -> worker -> record batch ->
Save & Add), because the defect only exists at the seam between two calls: the import
takes ``source_timezone`` as its own job parameter while the config declares its own,
and nothing used to compare them.

Concretely, before this fix a Trade Log could be saved declaring ``America/New_York``
while its pinned batch had been normalized as ``UTC``. Every entry/exit instant was
then off by the true offset, ``_require_ready_import`` still passed (it only checked
SUCCEEDED + ``accepted_count > 0``), and the immutable revision recorded the wrong
zone as evidence. Both twins are locked: doc 05 §5.2 for Trade Log, doc 04 §5 for
Trading Signal.

The pure gate (IANA validity, agreement semantics, fail-closed on absent evidence)
is covered without a database in ``tests/unit/test_tl_timezone_crosscheck.py``.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from entropia.application.commands import trade_log as tl_cmd
from entropia.application.commands import trading_signal as ts_cmd
from entropia.application.jobs.trade_log import run_import as run_trade_log_import
from entropia.application.jobs.trading_signal import run_import as run_signal_import
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import Principal
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import (
    SourceTimezoneMismatchError,
    TradeLogTimeZoneInvalidError,
    TradingSignalTimezoneInvalidError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_TRADE_HEADER = "direction,entry_time,entry_price,exit_time,exit_price,symbol"
_TRADE_CSV = "\n".join(
    [
        _TRADE_HEADER,
        "Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850,BTCUSDT",
        "Short,2024-01-02 09:15,43000,2024-01-02 18:00,41950,BTCUSDT",
    ]
).encode("utf-8")

_SIGNAL_HEADER = "source_record_id,event_time,available_time,direction,signal_type"
_SIGNAL_CSV = "\n".join(
    [
        _SIGNAL_HEADER,
        "r1,2024-05-01T10:00:00Z,2024-05-01T10:03:00Z,long,entry",
        "r2,2024-05-02T10:00:00Z,2024-05-02T10:01:00Z,sell,exit",
    ]
).encode("utf-8")


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    """In-process object storage so upload + worker read run without MinIO."""
    store: dict[str, bytes] = {}

    def _put(source_asset_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"signals/source/{source_asset_id}/{digest}"
        store[key] = data
        return key, digest

    def _get(object_key: str) -> bytes:
        return store[object_key]

    monkeypatch.setattr(datasets, "put_source_asset_bytes", _put)
    monkeypatch.setattr(datasets, "get_raw_bytes", _get)
    return store


async def _seed_principal(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()


# --------------------------------------------------------------------------- #
# Trade Log (doc 05 §5.2, §12.1)                                               #
# --------------------------------------------------------------------------- #


async def _trade_log_import(session, *, source_timezone: str) -> dict[str, Any]:
    upload = await tl_cmd.upload_source_asset(
        session, USER1, content=_TRADE_CSV, original_filename="trades.csv"
    )
    await session.commit()
    requested = await tl_cmd.request_trade_log_import(
        session,
        USER1,
        source_asset_id=upload["source_asset_id"],
        instrument_id="BTCUSDT",
        source_timezone=source_timezone,
    )
    await session.commit()
    result = await run_trade_log_import(session, requested["job_id"])
    await session.commit()
    return {
        "source_asset_id": upload["source_asset_id"],
        "record_batch_revision_id": result["record_batch_revision_id"],
    }


def _trade_log_payload(
    source_asset_id: str, record_batch_revision_id: str, *, source_timezone: str
) -> dict[str, Any]:
    return {
        "kind": "trade_log",
        "identity": {"display_name": "Binance BTCUSDT trade history Q1"},
        "source": {"provider_name": "Binance Futures export", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btcusdt", "display_symbol": "BTCUSDT"},
        "time_model": {
            "resolution_kind": "event_based",
            "base_timeframe": None,
            "source_timezone": source_timezone,
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
            "source_asset_id": source_asset_id,
            "record_batch_revision_id": record_batch_revision_id,
        },
    }


async def test_trade_log_attach_is_refused_when_the_import_ran_under_another_zone(
    session, fake_object_store
) -> None:
    """The headline case: import normalized as UTC, config declares America/New_York."""
    await _seed_principal(session)
    imported = await _trade_log_import(session, source_timezone="UTC")
    payload = _trade_log_payload(
        imported["source_asset_id"],
        imported["record_batch_revision_id"],
        source_timezone="America/New_York",
    )

    with pytest.raises(SourceTimezoneMismatchError) as excinfo:
        await tl_cmd.create_trade_log_and_attach(session, USER1, payload=payload)

    error = excinfo.value
    assert error.code == "TIMEZONE_MISMATCH"
    assert error.http_status == 422
    assert error.retryable is False
    assert error.field_path == "time_model.source_timezone"
    assert error.scope_id == imported["record_batch_revision_id"]
    assert error.details[0]["declared_source_timezone"] == "America/New_York"
    assert error.details[0]["imported_source_timezone"] == "UTC"


async def test_trade_log_attach_succeeds_when_the_zones_match(session, fake_object_store) -> None:
    """The same non-UTC zone on both sides still saves — the gate blocks disagreement,
    not non-UTC data."""
    await _seed_principal(session)
    imported = await _trade_log_import(session, source_timezone="America/New_York")
    payload = _trade_log_payload(
        imported["source_asset_id"],
        imported["record_batch_revision_id"],
        source_timezone="America/New_York",
    )

    result = await tl_cmd.create_trade_log_and_attach(session, USER1, payload=payload)
    await session.commit()
    assert result["attached"] is True
    assert result["object_kind"] == "trade_log"


async def test_trade_log_revision_n_plus_one_is_gated_too(session, fake_object_store) -> None:
    """Save New Revision binds a batch as well, so it cannot be the way around the gate."""
    await _seed_principal(session)
    matched = await _trade_log_import(session, source_timezone="UTC")
    saved = await tl_cmd.create_trade_log_and_attach(
        session,
        USER1,
        payload=_trade_log_payload(
            matched["source_asset_id"],
            matched["record_batch_revision_id"],
            source_timezone="UTC",
        ),
    )
    await session.commit()

    with pytest.raises(SourceTimezoneMismatchError):
        await tl_cmd.create_trade_log_revision(
            session,
            USER1,
            root_id=saved["root_id"],
            payload=_trade_log_payload(
                matched["source_asset_id"],
                matched["record_batch_revision_id"],
                source_timezone="Europe/Istanbul",
            ),
        )


async def test_trade_log_import_request_rejects_a_non_iana_zone(session, fake_object_store) -> None:
    """Doc 05 §12.1 ``TIME_ZONE_INVALID`` — an unresolvable zone never reaches the
    durable job, so the worker cannot normalize a batch under a zone no config could
    legally declare."""
    await _seed_principal(session)
    upload = await tl_cmd.upload_source_asset(
        session, USER1, content=_TRADE_CSV, original_filename="trades.csv"
    )
    await session.commit()

    with pytest.raises(TradeLogTimeZoneInvalidError) as excinfo:
        await tl_cmd.request_trade_log_import(
            session,
            USER1,
            source_asset_id=upload["source_asset_id"],
            instrument_id="BTCUSDT",
            source_timezone="America/New York",
        )
    assert excinfo.value.code == "TIME_ZONE_INVALID"


async def test_trade_log_config_with_an_invalid_zone_is_a_time_zone_error(
    session, fake_object_store
) -> None:
    """The §12.1 code fires instead of a generic VALIDATION_FAILED, so the UI can point
    at the Time Zone field."""
    await _seed_principal(session)
    imported = await _trade_log_import(session, source_timezone="UTC")
    payload = _trade_log_payload(
        imported["source_asset_id"],
        imported["record_batch_revision_id"],
        source_timezone="Mars/Olympus_Mons",
    )

    with pytest.raises(TradeLogTimeZoneInvalidError) as excinfo:
        await tl_cmd.create_trade_log_and_attach(session, USER1, payload=payload)
    assert excinfo.value.code == "TIME_ZONE_INVALID"


# --------------------------------------------------------------------------- #
# Trading Signal twin (doc 04 §5, §11)                                         #
# --------------------------------------------------------------------------- #


async def _signal_import(session, *, source_timezone: str) -> dict[str, Any]:
    upload = await ts_cmd.upload_source_asset(
        session, USER1, content=_SIGNAL_CSV, original_filename="signals.csv"
    )
    await session.commit()
    requested = await ts_cmd.request_trading_signal_import(
        session,
        USER1,
        source_asset_id=upload["source_asset_id"],
        instrument_id="BTCUSDT",
        source_timezone=source_timezone,
    )
    await session.commit()
    result = await run_signal_import(session, requested["job_id"])
    await session.commit()
    return {
        "source_asset_id": upload["source_asset_id"],
        "normalized_event_revision_id": result["normalized_event_revision_id"],
    }


def _signal_payload(
    source_asset_id: str, normalized_revision_id: str, *, source_timezone: str
) -> dict[str, Any]:
    return {
        "kind": "trading_signal",
        "identity": {"display_name": "Copy Trading Signal Source A"},
        "source": {"provider_name": "Provider X", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btcusdt", "display_symbol": "BTCUSDT"},
        "event_model": {"resolution_kind": "event_based", "base_timeframe": None},
        "classification": {"rationale_family_id": None},
        "data_quality": {"mode": "signal_events_only"},
        "time_policy": {
            "source_timezone": source_timezone,
            "normalization_timezone": "UTC",
        },
        "price_policy": {"source": "suggested_signal_price", "fallback": None},
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000"},
        "import_binding": {
            "source_asset_id": source_asset_id,
            "normalized_event_revision_id": normalized_revision_id,
        },
    }


async def test_trading_signal_attach_is_refused_when_the_import_ran_under_another_zone(
    session, fake_object_store
) -> None:
    await _seed_principal(session)
    imported = await _signal_import(session, source_timezone="UTC")
    payload = _signal_payload(
        imported["source_asset_id"],
        imported["normalized_event_revision_id"],
        source_timezone="America/New_York",
    )

    with pytest.raises(SourceTimezoneMismatchError) as excinfo:
        await ts_cmd.create_trading_signal_and_attach(session, USER1, payload=payload)

    error = excinfo.value
    assert error.code == "TIMEZONE_MISMATCH"
    assert error.field_path == "time_policy.source_timezone"
    assert error.scope_id == imported["normalized_event_revision_id"]


async def test_trading_signal_attach_succeeds_when_the_zones_match(
    session, fake_object_store
) -> None:
    await _seed_principal(session)
    imported = await _signal_import(session, source_timezone="UTC")
    payload = _signal_payload(
        imported["source_asset_id"],
        imported["normalized_event_revision_id"],
        source_timezone="UTC",
    )

    result = await ts_cmd.create_trading_signal_and_attach(session, USER1, payload=payload)
    await session.commit()
    assert result["attached"] is True
    assert result["object_kind"] == "trading_signal"


async def test_trading_signal_import_request_rejects_a_non_iana_zone(
    session, fake_object_store
) -> None:
    """Doc 04 §11 ``TIMEZONE_INVALID``. This gate matters most on this twin:
    ``domain/trading_signal/events.py::_resolve_timezone`` silently falls back to UTC
    for an unresolvable zone, so an invalid zone reaching the worker would shift every
    event with no blocker at all."""
    await _seed_principal(session)
    upload = await ts_cmd.upload_source_asset(
        session, USER1, content=_SIGNAL_CSV, original_filename="signals.csv"
    )
    await session.commit()

    with pytest.raises(TradingSignalTimezoneInvalidError) as excinfo:
        await ts_cmd.request_trading_signal_import(
            session,
            USER1,
            source_asset_id=upload["source_asset_id"],
            instrument_id="BTCUSDT",
            source_timezone="Mars/Olympus_Mons",
        )
    assert excinfo.value.code == "TIMEZONE_INVALID"
