"""GAP-22 — TL/TS column mapping through the real durable pipeline (doc 04 §5.1,
doc 05 §5.2). Auto-skips when no PostgreSQL is reachable (tests/integration/conftest.py).

Object storage is faked in-process. Proves: a file with aliased headers imports and
records mapping evidence (mapping_hash + resolved_mapping) in the batch validation
summary; the Save path threads import_binding.mapping_revision_id into the revision
source-provenance (the field was previously dead); ambiguous headers fail closed to
a typed 422 at Save; and a Trading Signal accepts an explicit mapping.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from entropia.application.commands import trade_log as tl_cmd
from entropia.application.commands import trading_signal as ts_cmd
from entropia.application.jobs.trade_log import run_import as run_tl_import
from entropia.application.jobs.trading_signal import run_import as run_ts_import
from entropia.application.queries import trade_log as tl_query
from entropia.application.queries import trading_signal as ts_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import Principal, WorkObjectRevision
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import AmbiguousColumnMappingError

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    store: dict[str, bytes] = {}

    def _put(source_asset_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"src/{source_asset_id}/{digest}"
        store[key] = data
        return key, digest

    monkeypatch.setattr(datasets, "put_source_asset_bytes", _put)
    monkeypatch.setattr(datasets, "get_raw_bytes", lambda key: store[key])
    return store


async def _seed(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _tl_import(session, csv: bytes, mapping: dict[str, str] | None = None) -> dict[str, Any]:
    upload = await tl_cmd.upload_source_asset(
        session, USER1, content=csv, original_filename="t.csv"
    )
    await session.commit()
    requested = await tl_cmd.request_trade_log_import(
        session,
        USER1,
        source_asset_id=upload["source_asset_id"],
        instrument_id="BTCUSDT",
        import_mapping=mapping,
    )
    await session.commit()
    await run_tl_import(session, requested["job_id"])
    await session.commit()
    report = await tl_query.get_import_report(session, USER1, job_id=requested["job_id"])
    return {"source_asset_id": upload["source_asset_id"], "report": report}


def _tl_payload(source_asset_id: str, batch_id: str, mapping_revision_id: str) -> dict[str, Any]:
    return {
        "kind": "trade_log",
        "identity": {"display_name": "Aliased header ledger"},
        "source": {"provider_name": "Broker export", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btc", "display_symbol": "BTCUSDT"},
        "time_model": {
            "resolution_kind": "event_based",
            "source_timezone": "UTC",
            "normalization_timezone": "UTC",
        },
        "data_quality": {"content_profile": "entry_exit_records_only"},
        "price_policy": {"source": "trade_log_entry_exit_price"},
        "ohlcv_policy": {"use_mode": "ignore"},
        "import_binding": {
            "source_asset_id": source_asset_id,
            "record_batch_revision_id": batch_id,
            "mapping_revision_id": mapping_revision_id,
        },
    }


_ALIASED_TL = (
    b"side,open_time,open_price,close_time,close_price,ticker\n"
    b"Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850,BTCUSDT"
)


async def test_tl_aliased_import_records_mapping_evidence_and_provenance(
    session, fake_object_store
) -> None:
    await _seed(session)
    pipeline = await _tl_import(session, _ALIASED_TL)
    report = pipeline["report"]
    assert report["status"] == "succeeded"
    assert report["accepted_count"] == 1
    summary = report["validation_summary"]
    mapping_hash = summary["mapping_hash"]
    assert mapping_hash.startswith("sha256:")
    assert summary["resolved_mapping"]["direction"] == "side"

    payload = _tl_payload(
        pipeline["source_asset_id"], report["record_batch_revision_id"], mapping_hash
    )
    result = await tl_cmd.create_trade_log_and_attach(session, USER1, payload=payload, attach=False)
    await session.commit()

    revision = await session.get(WorkObjectRevision, result["revision_id"])
    assert revision is not None
    # The formerly-dead import_binding.mapping_revision_id now rides the provenance.
    assert revision.source_provenance["mapping_revision_id"] == mapping_hash


_AMBIGUOUS_TL = (
    b"direction,open_time,entry_date,entry_price,exit_time,exit_price\n"
    b"Long,2024-01-01 10:00,2024-01-01 09:00,42100,2024-01-01 15:30,42850"
)


async def test_tl_ambiguous_headers_fail_closed_at_save(session, fake_object_store) -> None:
    await _seed(session)
    pipeline = await _tl_import(session, _AMBIGUOUS_TL)
    assert pipeline["report"]["status"] == "failed"
    assert pipeline["report"]["validation_summary"]["blocker_code"] == "AMBIGUOUS_COLUMN_MAPPING"

    payload = _tl_payload(
        pipeline["source_asset_id"], pipeline["report"]["record_batch_revision_id"] or "x", ""
    )
    with pytest.raises(AmbiguousColumnMappingError):
        await tl_cmd.create_trade_log_and_attach(session, USER1, payload=payload, attach=False)


_MAPPED_TS = b"rid,made_at,seen_at,dir,kind\nr1,2024-01-01 10:00,2024-01-01 11:00,long,entry"


async def test_ts_explicit_mapping_import_succeeds(session, fake_object_store) -> None:
    await _seed(session)
    upload = await ts_cmd.upload_source_asset(
        session, USER1, content=_MAPPED_TS, original_filename="s.csv"
    )
    await session.commit()
    requested = await ts_cmd.request_trading_signal_import(
        session,
        USER1,
        source_asset_id=upload["source_asset_id"],
        instrument_id="BTCUSDT",
        import_mapping={
            "source_record_id": "rid",
            "event_time": "made_at",
            "available_time": "seen_at",
            "direction": "dir",
            "signal_type": "kind",
        },
    )
    await session.commit()
    await run_ts_import(session, requested["job_id"])
    await session.commit()
    report = await ts_query.get_import_report(session, USER1, job_id=requested["job_id"])
    assert report["status"] == "succeeded"
    assert report["accepted_count"] == 1
    assert report["validation_summary"]["mapping_hash"].startswith("sha256:")
