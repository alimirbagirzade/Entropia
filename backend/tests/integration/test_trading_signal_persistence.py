"""Stage 3c Trading Signal — exercised against a real database (doc 04).

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Object storage is faked in-process (monkeypatched put/get) so the FULL durable
pipeline — upload source asset -> request import -> run worker -> normalized event
revision -> Save & Add native work object -> Mainboard item — runs on Postgres
alone (no MinIO). A Trading Signal is a NATIVE work object, so pin + soft-delete
REUSE the 3a Mainboard commands unchanged.

Covers: full happy-path pipeline (accepted events, earliest available_time, work
object + item + composition hash, audit + outbox, normalized revision pinned to the
revision); AVAILABLE_TIME_REQUIRED and legacy-schema import blockers; revision N+1
does NOT auto-repin; explicit pin changes the composition hash (3a reuse); stale
expected_head -> WORK_OBJECT_REVISION_CONFLICT; idempotent Save replay; foreign-owner
edit 403; soft-delete drops the item from the active projection; content-dedup upload.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import trading_signal as ts_cmd
from entropia.application.jobs.trading_signal import run_import
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import trading_signal as ts_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    NormalizedSignalEventRevision,
    OutboxEvent,
    Principal,
    WorkObjectRevision,
)
from entropia.infrastructure.postgres.repositories import trading_signal as ts_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import (
    AccessDeniedError,
    AvailableTimeRequiredError,
    SignalEventMappingRequiredError,
    WorkObjectRevisionConflictError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)

_HEADER = "source_record_id,event_time,available_time,direction,signal_type"
_GOOD_CSV = "\n".join(
    [
        _HEADER,
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


async def _seed_principals(session) -> None:
    for pid in ("user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _run_import_pipeline(
    session, actor: Actor, csv_bytes: bytes, *, instrument_id: str = "BTCUSDT"
) -> dict[str, Any]:
    """Upload -> request import -> run worker. Returns the import report projection."""
    upload = await ts_cmd.upload_source_asset(
        session, actor, content=csv_bytes, original_filename="signals.csv"
    )
    await session.commit()
    requested = await ts_cmd.request_trading_signal_import(
        session, actor, source_asset_id=upload["source_asset_id"], instrument_id=instrument_id
    )
    await session.commit()
    await run_import(session, requested["job_id"])
    await session.commit()
    report = await ts_query.get_import_report(session, actor, job_id=requested["job_id"])
    return {"source_asset_id": upload["source_asset_id"], "report": report}


def _payload(source_asset_id: str, normalized_revision_id: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "trading_signal",
        "identity": {"display_name": "Copy Trading Signal Source A"},
        "source": {"provider_name": "Provider X", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btcusdt", "display_symbol": "BTCUSDT"},
        "event_model": {"resolution_kind": "event_based", "base_timeframe": None},
        "classification": {"rationale_family_id": None},
        "data_quality": {"mode": "signal_events_only"},
        "time_policy": {"source_timezone": "UTC", "normalization_timezone": "UTC"},
        "price_policy": {"source": "suggested_signal_price", "fallback": None},
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000"},
        "import_binding": {
            "source_asset_id": source_asset_id,
            "normalized_event_revision_id": normalized_revision_id,
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
    normalized_id = report["normalized_event_revision_id"]

    payload = _payload(pipeline["source_asset_id"], normalized_id)
    result = await ts_cmd.create_trading_signal_and_attach(session, USER1, payload=payload)
    await session.commit()

    assert result["root_id"].startswith("wo_")
    assert result["object_kind"] == "trading_signal"
    assert result["attached"] is True
    assert result["ready_state"] == "STALE"
    assert result["composition_hash"]

    # The native work object revision carries the §9.2 payload + earliest available_time.
    revision = await session.get(WorkObjectRevision, result["revision_id"])
    assert revision is not None
    assert revision.payload["kind"] == "trading_signal"
    assert revision.available_time is not None

    # The normalized revision is pinned to the Trading Signal revision (Save-time link).
    normalized = await ts_repo.get_normalized_revision(session, normalized_id)
    assert normalized is not None
    assert normalized.work_object_revision_id == result["revision_id"]

    # The item shows up in the default Mainboard active projection.
    projection = await mb_query.get_default_mainboard(session, USER1)
    kinds = [item["item_kind"] for item in projection["items"]]
    assert "trading_signal" in kinds

    # A representative mutation wrote audit + outbox in the same tx.
    audit = (
        await session.execute(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_kind == "trading_signal.revision_created")
        )
    ).scalar_one()
    outbox = (
        await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "trading_signal.revision_created")
        )
    ).scalar_one()
    assert audit >= 1 and outbox >= 1


async def test_upload_is_content_deduplicated(session, fake_object_store) -> None:
    await _seed_principals(session)
    first = await ts_cmd.upload_source_asset(
        session, USER1, content=_GOOD_CSV, original_filename="a.csv"
    )
    await session.commit()
    second = await ts_cmd.upload_source_asset(
        session, USER1, content=_GOOD_CSV, original_filename="b.csv"
    )
    await session.commit()
    assert second["deduplicated"] is True
    assert second["source_asset_id"] == first["source_asset_id"]


# --------------------------------------------------------------------------- #
# Import blockers                                                              #
# --------------------------------------------------------------------------- #


async def test_available_time_required_blocks_save(session, fake_object_store) -> None:
    await _seed_principals(session)
    csv_bytes = "\n".join([_HEADER, "r1,2024-05-01T10:00:00Z,,long,entry"]).encode("utf-8")
    pipeline = await _run_import_pipeline(session, USER1, csv_bytes)
    assert pipeline["report"]["status"] == "failed"

    # The normalized revision exists but is empty/blocked; Save must refuse it.
    normalized = await ts_repo.get_normalized_revision_for_job(
        session, pipeline["report"]["job_id"]
    )
    assert normalized is not None
    payload = _payload(pipeline["source_asset_id"], normalized.normalized_revision_id)
    with pytest.raises(AvailableTimeRequiredError):
        await ts_cmd.create_trading_signal_and_attach(session, USER1, payload=payload)


async def test_legacy_schema_directs_to_trade_log(session, fake_object_store) -> None:
    await _seed_principals(session)
    legacy = "\n".join(
        [
            "entry_time,entry_price,exit_time,exit_price",
            "2024-05-01T10:00:00Z,100,2024-05-01T12:00:00Z,110",
        ]
    ).encode("utf-8")
    pipeline = await _run_import_pipeline(session, USER1, legacy)
    normalized = await ts_repo.get_normalized_revision_for_job(
        session, pipeline["report"]["job_id"]
    )
    assert normalized is not None
    payload = _payload(pipeline["source_asset_id"], normalized.normalized_revision_id)
    with pytest.raises(SignalEventMappingRequiredError):
        await ts_cmd.create_trading_signal_and_attach(session, USER1, payload=payload)


# --------------------------------------------------------------------------- #
# Revision / pin semantics                                                     #
# --------------------------------------------------------------------------- #


async def _saved_signal(session, actor: Actor, fake_object_store) -> dict[str, Any]:
    pipeline = await _run_import_pipeline(session, actor, _GOOD_CSV)
    normalized_id = pipeline["report"]["normalized_event_revision_id"]
    payload = _payload(pipeline["source_asset_id"], normalized_id)
    result = await ts_cmd.create_trading_signal_and_attach(session, actor, payload=payload)
    await session.commit()
    return {"pipeline": pipeline, "save": result}


async def test_new_revision_does_not_auto_repin(session, fake_object_store) -> None:
    await _seed_principals(session)
    saved = await _saved_signal(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]
    first_revision_id = saved["save"]["revision_id"]

    # A different upload/import -> a new normalized revision -> a new signal revision.
    other_csv = "\n".join(
        [_HEADER, "r9,2024-05-03T10:00:00Z,2024-05-03T10:05:00Z,long,entry"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, USER1, other_csv)
    payload2 = _payload(
        pipeline2["source_asset_id"],
        pipeline2["report"]["normalized_event_revision_id"],
        identity={"display_name": "Copy Trading Signal Source A v2"},
    )
    rev2 = await ts_cmd.create_trading_signal_revision(
        session, USER1, root_id=root_id, payload=payload2
    )
    await session.commit()
    assert rev2["revision_id"] != first_revision_id
    assert rev2["auto_repinned"] is False

    # The Mainboard item is STILL pinned to the first revision (no implicit latest).
    projection = await mb_query.get_default_mainboard(session, USER1)
    item = next(i for i in projection["items"] if i["work_object_root_id"] == root_id)
    assert item["pinned_revision_id"] == first_revision_id


async def test_explicit_pin_changes_composition_hash(session, fake_object_store) -> None:
    await _seed_principals(session)
    saved = await _saved_signal(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]
    hash_before = saved["save"]["composition_hash"]

    other_csv = "\n".join(
        [_HEADER, "r9,2024-05-03T10:00:00Z,2024-05-03T10:05:00Z,short,entry"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, USER1, other_csv)
    payload2 = _payload(
        pipeline2["source_asset_id"],
        pipeline2["report"]["normalized_event_revision_id"],
        identity={"display_name": "v2"},
    )
    rev2 = await ts_cmd.create_trading_signal_revision(
        session, USER1, root_id=root_id, payload=payload2
    )
    await session.commit()

    projection = await mb_query.get_default_mainboard(session, USER1)
    item = next(i for i in projection["items"] if i["work_object_root_id"] == root_id)
    # Explicit pin (REUSE 3a patch_mainboard_item) -> composition hash changes.
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
    saved = await _saved_signal(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]

    other_csv = "\n".join(
        [_HEADER, "r9,2024-05-03T10:00:00Z,2024-05-03T10:05:00Z,long,entry"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, USER1, other_csv)
    payload2 = _payload(
        pipeline2["source_asset_id"],
        pipeline2["report"]["normalized_event_revision_id"],
        identity={"display_name": "v2"},
    )
    with pytest.raises(WorkObjectRevisionConflictError):
        await ts_cmd.create_trading_signal_revision(
            session,
            USER1,
            root_id=root_id,
            payload=payload2,
            expected_head_revision_id="worev_stale",
        )


async def test_idempotent_save_replay(session, fake_object_store) -> None:
    await _seed_principals(session)
    pipeline = await _run_import_pipeline(session, USER1, _GOOD_CSV)
    payload = _payload(
        pipeline["source_asset_id"], pipeline["report"]["normalized_event_revision_id"]
    )
    first = await ts_cmd.create_trading_signal_and_attach(
        session, USER1, payload=payload, idempotency_key="ts-key-1"
    )
    await session.commit()
    second = await ts_cmd.create_trading_signal_and_attach(
        session, USER1, payload=payload, idempotency_key="ts-key-1"
    )
    await session.commit()
    assert second["root_id"] == first["root_id"]
    assert second["revision_id"] == first["revision_id"]
    # Exactly one native Trading Signal revision exists for that root.
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
    saved = await _saved_signal(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]

    other_csv = "\n".join(
        [_HEADER, "r9,2024-05-03T10:00:00Z,2024-05-03T10:05:00Z,long,entry"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, USER2, other_csv)
    payload2 = _payload(
        pipeline2["source_asset_id"],
        pipeline2["report"]["normalized_event_revision_id"],
        identity={"display_name": "hijack"},
    )
    with pytest.raises(AccessDeniedError):
        await ts_cmd.create_trading_signal_revision(
            session, USER2, root_id=root_id, payload=payload2
        )


async def test_soft_delete_removes_item_from_projection(session, fake_object_store) -> None:
    await _seed_principals(session)
    saved = await _saved_signal(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]

    # Soft-delete REUSES the 3a work-object command.
    await mb_cmd.soft_delete_work_object(session, USER1, root_id=root_id)
    await session.commit()

    projection = await mb_query.get_default_mainboard(session, USER1)
    roots = [item["work_object_root_id"] for item in projection["items"]]
    assert root_id not in roots


async def test_normalized_revision_row_persists_evidence(session, fake_object_store) -> None:
    await _seed_principals(session)
    pipeline = await _run_import_pipeline(session, USER1, _GOOD_CSV)
    total = (
        await session.execute(select(func.count()).select_from(NormalizedSignalEventRevision))
    ).scalar_one()
    assert total == 1
    normalized = await ts_repo.get_normalized_revision(
        session, pipeline["report"]["normalized_event_revision_id"]
    )
    assert normalized is not None
    assert len(normalized.events) == 2
    assert normalized.content_hash and len(normalized.content_hash) == 64
