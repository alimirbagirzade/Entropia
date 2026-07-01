"""Stage 3d Trade Log — exercised against a real database (doc 05).

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Object storage is faked in-process (monkeypatched put/get) so the FULL durable
pipeline — upload source asset -> request import -> run worker -> canonical
trade-record batch -> Save & Add native work object -> Mainboard item — runs on
Postgres alone (no MinIO). A Trade Log is a NATIVE work object, so pin + soft-delete
REUSE the 3a Mainboard commands unchanged.

Covers: full happy-path pipeline (accepted records, work object + item + composition
hash, audit + outbox, batch pinned to the revision, available_time None for historical
data); REQUIRED_COLUMN_MISSING import blocker; revision N+1 does NOT auto-repin;
explicit pin changes the composition hash (3a reuse); stale expected_head ->
WORK_OBJECT_REVISION_CONFLICT; idempotent Save replay; foreign-owner edit 403;
soft-delete drops the item from the active projection; content-dedup upload; batch
evidence persisted.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import trade_log as tl_cmd
from entropia.application.jobs.trade_log import run_import
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import trade_log as tl_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    CanonicalTradeRecordBatch,
    OutboxEvent,
    Principal,
    WorkObjectRevision,
)
from entropia.infrastructure.postgres.repositories import trade_log as tl_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import (
    AccessDeniedError,
    RequiredColumnMissingError,
    WorkObjectRevisionConflictError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)

_HEADER = "direction,entry_time,entry_price,exit_time,exit_price,symbol"
_GOOD_CSV = "\n".join(
    [
        _HEADER,
        "Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850,BTCUSDT",
        "Short,2024-01-02 09:15,43000,2024-01-02 18:00,41950,BTCUSDT",
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


async def _seed_principals(session) -> None:
    for pid in ("user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _run_import_pipeline(
    session, actor: Actor, csv_bytes: bytes, *, instrument_id: str = "BTCUSDT"
) -> dict[str, Any]:
    """Upload -> request import -> run worker. Returns the import report projection."""
    upload = await tl_cmd.upload_source_asset(
        session, actor, content=csv_bytes, original_filename="trades.csv"
    )
    await session.commit()
    requested = await tl_cmd.request_trade_log_import(
        session, actor, source_asset_id=upload["source_asset_id"], instrument_id=instrument_id
    )
    await session.commit()
    await run_import(session, requested["job_id"])
    await session.commit()
    report = await tl_query.get_import_report(session, actor, job_id=requested["job_id"])
    return {"source_asset_id": upload["source_asset_id"], "report": report}


def _payload(
    source_asset_id: str, record_batch_revision_id: str, **overrides: Any
) -> dict[str, Any]:
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
            "source_asset_id": source_asset_id,
            "record_batch_revision_id": record_batch_revision_id,
        },
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# Full pipeline                                                                #
# --------------------------------------------------------------------------- #


async def test_full_pipeline_upload_import_save_and_attach(session, fake_object_store) -> None:
    await _seed_principals(session)
    pipeline = await _run_import_pipeline(session, USER1, _GOOD_CSV)
    report = pipeline["report"]
    assert report["status"] == "succeeded"
    assert report["accepted_count"] == 2
    batch_id = report["record_batch_revision_id"]

    payload = _payload(pipeline["source_asset_id"], batch_id)
    result = await tl_cmd.create_trade_log_and_attach(session, USER1, payload=payload)
    await session.commit()

    assert result["root_id"].startswith("wo_")
    assert result["object_kind"] == "trade_log"
    assert result["attached"] is True
    assert result["ready_state"] == "STALE"
    assert result["composition_hash"]

    # The native work object revision carries the §10.2 payload; historical data =>
    # no anti-lookahead available_time (doc 05 §10.4).
    revision = await session.get(WorkObjectRevision, result["revision_id"])
    assert revision is not None
    assert revision.payload["kind"] == "trade_log"
    assert revision.available_time is None

    # The record batch is pinned to the Trade Log revision (Save-time link).
    batch = await tl_repo.get_record_batch(session, batch_id)
    assert batch is not None
    assert batch.work_object_revision_id == result["revision_id"]

    # The item shows up in the default Mainboard active projection.
    projection = await mb_query.get_default_mainboard(session, USER1)
    kinds = [item["item_kind"] for item in projection["items"]]
    assert "trade_log" in kinds

    # A representative mutation wrote audit + outbox in the same tx.
    audit = (
        await session.execute(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_kind == "trade_log.revision_created")
        )
    ).scalar_one()
    outbox = (
        await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "trade_log.revision_created")
        )
    ).scalar_one()
    assert audit >= 1 and outbox >= 1


async def test_upload_is_content_deduplicated(session, fake_object_store) -> None:
    await _seed_principals(session)
    first = await tl_cmd.upload_source_asset(
        session, USER1, content=_GOOD_CSV, original_filename="a.csv"
    )
    await session.commit()
    second = await tl_cmd.upload_source_asset(
        session, USER1, content=_GOOD_CSV, original_filename="b.csv"
    )
    await session.commit()
    assert second["deduplicated"] is True
    assert second["source_asset_id"] == first["source_asset_id"]


# --------------------------------------------------------------------------- #
# Import blockers                                                              #
# --------------------------------------------------------------------------- #


async def test_required_column_missing_blocks_save(session, fake_object_store) -> None:
    await _seed_principals(session)
    bad = "\n".join(
        [
            "direction,entry_time,entry_price,exit_time",
            "Long,2024-01-01 10:00,100,2024-01-01 12:00",
        ]
    ).encode("utf-8")
    pipeline = await _run_import_pipeline(session, USER1, bad)
    assert pipeline["report"]["status"] == "failed"

    batch = await tl_repo.get_record_batch_for_job(session, pipeline["report"]["job_id"])
    assert batch is not None
    payload = _payload(pipeline["source_asset_id"], batch.record_batch_id)
    with pytest.raises(RequiredColumnMissingError):
        await tl_cmd.create_trade_log_and_attach(session, USER1, payload=payload)


# --------------------------------------------------------------------------- #
# Revision / pin semantics                                                     #
# --------------------------------------------------------------------------- #


async def _saved_trade_log(session, actor: Actor, fake_object_store) -> dict[str, Any]:
    pipeline = await _run_import_pipeline(session, actor, _GOOD_CSV)
    batch_id = pipeline["report"]["record_batch_revision_id"]
    payload = _payload(pipeline["source_asset_id"], batch_id)
    result = await tl_cmd.create_trade_log_and_attach(session, actor, payload=payload)
    await session.commit()
    return {"pipeline": pipeline, "save": result}


async def test_new_revision_does_not_auto_repin(session, fake_object_store) -> None:
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]
    first_revision_id = saved["save"]["revision_id"]

    other_csv = "\n".join(
        [_HEADER, "Long,2024-02-01 10:00,50000,2024-02-01 12:00,51000,BTCUSDT"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, USER1, other_csv)
    payload2 = _payload(
        pipeline2["source_asset_id"],
        pipeline2["report"]["record_batch_revision_id"],
        identity={"display_name": "Binance BTCUSDT trade history Q1 v2"},
    )
    rev2 = await tl_cmd.create_trade_log_revision(session, USER1, root_id=root_id, payload=payload2)
    await session.commit()
    assert rev2["revision_id"] != first_revision_id
    assert rev2["auto_repinned"] is False

    projection = await mb_query.get_default_mainboard(session, USER1)
    item = next(i for i in projection["items"] if i["work_object_root_id"] == root_id)
    assert item["pinned_revision_id"] == first_revision_id


async def test_explicit_pin_changes_composition_hash(session, fake_object_store) -> None:
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]
    hash_before = saved["save"]["composition_hash"]

    other_csv = "\n".join(
        [_HEADER, "Short,2024-02-01 10:00,50000,2024-02-01 12:00,49000,BTCUSDT"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, USER1, other_csv)
    payload2 = _payload(
        pipeline2["source_asset_id"],
        pipeline2["report"]["record_batch_revision_id"],
        identity={"display_name": "v2"},
    )
    rev2 = await tl_cmd.create_trade_log_revision(session, USER1, root_id=root_id, payload=payload2)
    await session.commit()

    projection = await mb_query.get_default_mainboard(session, USER1)
    item = next(i for i in projection["items"] if i["work_object_root_id"] == root_id)
    pin = await mb_cmd.patch_mainboard_item(
        session,
        USER1,
        item_id=item["item_id"],
        intent="pin_revision",
        expected_row_version=item["row_version"],
        revision_id=rev2["revision_id"],
    )
    await session.commit()
    assert pin["composition_hash"] != hash_before


async def test_stale_expected_head_conflicts(session, fake_object_store) -> None:
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]

    other_csv = "\n".join(
        [_HEADER, "Long,2024-02-01 10:00,50000,2024-02-01 12:00,51000,BTCUSDT"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, USER1, other_csv)
    payload2 = _payload(
        pipeline2["source_asset_id"],
        pipeline2["report"]["record_batch_revision_id"],
        identity={"display_name": "v2"},
    )
    with pytest.raises(WorkObjectRevisionConflictError):
        await tl_cmd.create_trade_log_revision(
            session,
            USER1,
            root_id=root_id,
            payload=payload2,
            expected_head_revision_id="worev_stale",
        )


async def test_idempotent_save_replay(session, fake_object_store) -> None:
    await _seed_principals(session)
    pipeline = await _run_import_pipeline(session, USER1, _GOOD_CSV)
    payload = _payload(pipeline["source_asset_id"], pipeline["report"]["record_batch_revision_id"])
    first = await tl_cmd.create_trade_log_and_attach(
        session, USER1, payload=payload, idempotency_key="tl-key-1"
    )
    await session.commit()
    second = await tl_cmd.create_trade_log_and_attach(
        session, USER1, payload=payload, idempotency_key="tl-key-1"
    )
    await session.commit()
    assert second["root_id"] == first["root_id"]
    assert second["revision_id"] == first["revision_id"]
    count = (
        await session.execute(
            select(func.count())
            .select_from(WorkObjectRevision)
            .where(WorkObjectRevision.entity_id == first["root_id"])
        )
    ).scalar_one()
    assert count == 1


# --------------------------------------------------------------------------- #
# Authorization + lifecycle                                                    #
# --------------------------------------------------------------------------- #


async def test_foreign_owner_cannot_create_revision(session, fake_object_store) -> None:
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]

    other_csv = "\n".join(
        [_HEADER, "Long,2024-02-01 10:00,50000,2024-02-01 12:00,51000,BTCUSDT"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, USER2, other_csv)
    payload2 = _payload(
        pipeline2["source_asset_id"],
        pipeline2["report"]["record_batch_revision_id"],
        identity={"display_name": "hijack"},
    )
    with pytest.raises(AccessDeniedError):
        await tl_cmd.create_trade_log_revision(session, USER2, root_id=root_id, payload=payload2)


async def test_soft_delete_removes_item_from_projection(session, fake_object_store) -> None:
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]

    await mb_cmd.soft_delete_work_object(session, USER1, root_id=root_id)
    await session.commit()

    projection = await mb_query.get_default_mainboard(session, USER1)
    roots = [item["work_object_root_id"] for item in projection["items"]]
    assert root_id not in roots


async def test_record_batch_persists_evidence(session, fake_object_store) -> None:
    await _seed_principals(session)
    pipeline = await _run_import_pipeline(session, USER1, _GOOD_CSV)
    total = (
        await session.execute(select(func.count()).select_from(CanonicalTradeRecordBatch))
    ).scalar_one()
    assert total == 1
    batch = await tl_repo.get_record_batch(session, pipeline["report"]["record_batch_revision_id"])
    assert batch is not None
    assert len(batch.records) == 2
    assert batch.content_hash and len(batch.content_hash) == 64
    assert batch.earliest_entry_time is not None
    assert batch.latest_exit_time is not None
