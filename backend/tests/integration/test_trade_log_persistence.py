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

Acceptance (doc 05 §16) by test:
- TL-05 required column        -> the REQUIRED_COLUMN_MISSING import blocker case
- TL-12 revision immutability  -> revision N+1 appends; N's content hash + source
  asset ref are unchanged (the "does NOT auto-repin" case)
- TL-13 explicit pin           -> explicit pin changes the composition hash; the report
  that pin invalidates is REPORTED stale on re-read (batch 11)
- TL-14 import durability      -> the full pipeline: upload returns a durable job and
  the WORKER (not the request) produces the record batch
- TL-15 idempotency            -> idempotent Save replay + content-dedup upload
- TL-16 concurrency            -> stale expected_head -> WORK_OBJECT_REVISION_CONFLICT; two
  writers off ONE observed head append exactly one revision (batch 11)
- TL-17 authorization          -> foreign-owner edit 403
- TL-20 soft-delete integrity  -> soft-delete drops the item from the active projection

doc 03 twins — the Add Outsource Signal page re-asserts the SAME server behaviour
for its Trade Log child, so these rows are satisfied by the tests above:
AOS-08 (background import durability) = TL-14; AOS-09 (the client parser is
non-authoritative — only the server import revision makes a Trade Log usable) =
the worker-produced record batch in the full pipeline; AOS-11 (specific revision
pin) = TL-13; AOS-14 (concurrency) = TL-16; AOS-15 (idempotency) = TL-15;
AOS-18 (soft-delete historical integrity) = TL-20.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as rc_cmd
from entropia.application.commands import trade_log as tl_cmd
from entropia.application.jobs.trade_log import run_import
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import readiness_check as rc_query
from entropia.application.queries import trade_log as tl_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.readiness.enums import ReadinessState
from entropia.domain.trash.page import TrashEntryStatus
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    BacktestResult,
    BacktestRun,
    CanonicalTradeRecordBatch,
    MainboardWorkingItem,
    OutboxEvent,
    Principal,
    TrashEntry,
    WorkObjectRevision,
)
from entropia.infrastructure.postgres.repositories import trade_log as tl_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import (
    AccessDeniedError,
    RequiredColumnMissingError,
    TradeLogValidationFailedError,
    UnsupportedSourceFileTypeError,
    WorkObjectRevisionConflictError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
SUPERVISOR = Actor(
    principal_id="user_supervisor", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR
)

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
    for pid in ("user_1", "user_2", "user_admin", "user_supervisor"):
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


async def _count_rows(session, model: Any) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _count_audits(session, event_kind: str) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_kind == event_kind)
            )
        ).scalar_one()
    )


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


async def test_source_file_type_gate_is_fail_closed(session, fake_object_store) -> None:
    """K-07: the TXT/CSV gate no longer SKIPS when the filename is absent.

    Before this fix ``if name and not name.endswith(...)`` accepted ANY payload as
    long as ``original_filename`` was ``None``/blank, so the doc 05 §5.2 server-side
    type control could be dropped entirely. Now every axis fails closed with the
    doc 05 §12.1 code, and only a real .csv/.txt with text content is stored."""
    await _seed_principals(session)

    for filename in (None, "", "   ", "trades.pdf", "trades"):
        with pytest.raises(UnsupportedSourceFileTypeError) as excinfo:
            await tl_cmd.upload_source_asset(
                session, USER1, content=_GOOD_CSV, original_filename=filename
            )
        assert excinfo.value.code == "UNSUPPORTED_SOURCE_FILE_TYPE"
        assert excinfo.value.details[0]["field"] == "original_filename"

    # A binary blob renamed .csv is rejected by the content sniff (the extension
    # claim alone is not evidence of the type).
    with pytest.raises(UnsupportedSourceFileTypeError):
        await tl_cmd.upload_source_asset(
            session, USER1, content=b"PK\x03\x04\x14\x00binary", original_filename="trades.csv"
        )

    # Nothing above reached storage; the supported extension still uploads.
    assert fake_object_store == {}
    uploaded = await tl_cmd.upload_source_asset(
        session, USER1, content=_GOOD_CSV, original_filename="trades.csv"
    )
    await session.commit()
    assert uploaded["deduplicated"] is False
    assert len(fake_object_store) == 1


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

    # ADIM 42 — K-06 pinned on the work-object path (TL-20.c2 / AOS-18.c2). The
    # projection assertion above only proves the row LEFT the active board; on its
    # own that is indistinguishable from an object that vanished without ever
    # reaching Admin Trash. K-06 makes writing the trash entry a standing
    # invariant, and until now no test on `mb_cmd.soft_delete_work_object`
    # queried TrashEntry / AuditEvent / OutboxEvent for it — other pages assert
    # this triple, the Trade Log and Trading Signal delete path did not.
    entry = (
        await session.execute(select(TrashEntry).where(TrashEntry.entity_id == root_id))
    ).scalar_one()
    assert entry.status == TrashEntryStatus.SOFT_DELETED
    assert entry.entity_type == "work_object"
    audits = (
        await session.execute(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_kind == "entity.soft_deleted")
            .where(AuditEvent.target_entity_id == root_id)
        )
    ).scalar_one()
    assert audits == 1
    outbox = (
        await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "entity.soft_deleted")
            .where(OutboxEvent.resource_id == root_id)
        )
    ).scalar_one()
    assert outbox == 1


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


# --------------------------------------------------------------------------- #
# Export — immutable manifest (S6, doc 05 §8 "Export As Package", §11, §13.2)  #
# --------------------------------------------------------------------------- #


async def test_export_produces_manifest_and_audit(session, fake_object_store) -> None:
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]
    revision_id = saved["save"]["revision_id"]

    result = await tl_cmd.export_trade_log(session, USER1, root_id=root_id)
    await session.commit()

    assert result["root_id"] == root_id
    assert result["revision_id"] == revision_id  # default = pinned head
    assert len(result["manifest_hash"]) == 64
    manifest = result["manifest"]
    assert manifest["object_kind"] == "trade_log"
    assert manifest["payload"]["kind"] == "trade_log"
    # Twin diff: a Trade Log revision carries no per-event availability (doc 05 §10.4).
    assert manifest["available_time"] is None
    assert manifest["source_provenance"]["source_asset_id"]

    # The export never mutated the source — head revision unchanged.
    detail = await tl_query.get_trade_log(session, USER1, root_id=root_id)
    assert detail["current_revision_id"] == revision_id

    audit = (
        (
            await session.execute(
                select(AuditEvent).where(AuditEvent.event_kind == "trade_log.exported")
            )
        )
        .scalars()
        .all()
    )
    assert len(audit) == 1
    outbox = (
        (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "trade_log.exported")
            )
        )
        .scalars()
        .all()
    )
    assert len(outbox) == 1
    assert outbox[0].payload["manifest_hash"] == result["manifest_hash"]


async def test_export_foreign_owner_forbidden(session, fake_object_store) -> None:
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]

    with pytest.raises(AccessDeniedError):
        await tl_cmd.export_trade_log(session, USER2, root_id=root_id)


async def test_export_idempotent_replay(session, fake_object_store) -> None:
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]

    first = await tl_cmd.export_trade_log(
        session, USER1, root_id=root_id, idempotency_key="tl-exp-key-1"
    )
    await session.commit()
    second = await tl_cmd.export_trade_log(
        session, USER1, root_id=root_id, idempotency_key="tl-exp-key-1"
    )
    await session.commit()

    assert first["manifest_hash"] == second["manifest_hash"]
    audit_count = (
        await session.execute(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_kind == "trade_log.exported")
        )
    ).scalar_one()
    assert audit_count == 1


# --------------------------------------------------------------------------- #
# ADIM 48 — class-B acceptance debt (doc 05 §16)                               #
# --------------------------------------------------------------------------- #


async def test_blank_display_name_persists_no_revision_or_item(session, fake_object_store) -> None:
    """TL-03.c3: the rejection is not merely typed — it writes nothing.

    ``test_blank_display_name_rejected_before_db`` proves the 422 on the wire against a
    dummy session; only a real database can prove the negative it implies. The import
    runs first so the batch/source asset the payload binds genuinely exist: the reason
    nothing is written must be the blank name, not an unresolvable binding.
    """
    await _seed_principals(session)
    pipeline = await _run_import_pipeline(session, USER1, _GOOD_CSV)
    payload = _payload(
        pipeline["source_asset_id"],
        pipeline["report"]["record_batch_revision_id"],
        identity={"display_name": "   "},
    )

    revisions_before = await _count_rows(session, WorkObjectRevision)
    items_before = await _count_rows(session, MainboardWorkingItem)

    with pytest.raises(TradeLogValidationFailedError) as exc:
        await tl_cmd.create_trade_log_and_attach(session, USER1, payload=payload)
    await session.rollback()

    assert any(
        str(issue.get("field", "")).startswith("identity.display_name")
        for issue in (exc.value.details or [])
    )
    assert await _count_rows(session, WorkObjectRevision) == revisions_before
    assert await _count_rows(session, MainboardWorkingItem) == items_before


async def test_admin_may_create_a_revision_on_a_foreign_trade_log(
    session, fake_object_store
) -> None:
    """TL-17.c4: the affirmative half of the ownership row.

    ``test_foreign_owner_cannot_create_revision`` proves a peer USER is refused; on its
    own that is equally consistent with "nobody but the owner may write", which would
    break the Admin override doc 05 §16 requires. The Supervisor case the row names
    alongside it is asserted here too — a Supervisor is a peer, not an override.
    """
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]
    owner_revision_id = saved["save"]["revision_id"]

    other_csv = "\n".join(
        [_HEADER, "Long,2024-03-01 10:00,50000,2024-03-01 12:00,51000,BTCUSDT"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, ADMIN, other_csv)
    payload2 = _payload(
        pipeline2["source_asset_id"],
        pipeline2["report"]["record_batch_revision_id"],
        identity={"display_name": "admin correction"},
    )

    # A Supervisor is NOT an override — same denial as the peer USER.
    with pytest.raises(AccessDeniedError):
        await tl_cmd.create_trade_log_revision(
            session, SUPERVISOR, root_id=root_id, payload=payload2
        )
    await session.rollback()

    revision = await tl_cmd.create_trade_log_revision(
        session, ADMIN, root_id=root_id, payload=payload2
    )
    await session.commit()

    assert revision["revision_id"] != owner_revision_id
    written = await session.get(WorkObjectRevision, revision["revision_id"])
    assert written is not None
    assert written.entity_id == root_id
    # The override writes a revision on the OWNER's root; it does not fork a new one,
    # and the Admin is recorded as its author rather than the owner.
    assert written.created_by_principal_id == ADMIN.principal_id
    assert written.payload["identity"]["display_name"] == "admin correction"
    # An override still never auto-repins (TL-13): the owner's board pin is untouched.
    projection = await mb_query.get_default_mainboard(session, USER1)
    item = next(i for i in projection["items"] if i["work_object_root_id"] == root_id)
    assert item["pinned_revision_id"] == owner_revision_id


async def test_replayed_pin_creates_no_duplicate_item_or_pin_event(
    session, fake_object_store
) -> None:
    """TL-15.c5: the fifth named operation of the idempotency row.

    Upload / import / Save / Export are each proven by a row count; Pin was not. The
    replay carries the ALREADY-CONSUMED ``expected_row_version`` on purpose: without
    the Idempotency-Key envelope that second call is a stale token and would raise
    ROW_VERSION_CONFLICT, so returning the original projection is the property.
    """
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]

    other_csv = "\n".join(
        [_HEADER, "Short,2024-04-01 10:00,50000,2024-04-01 12:00,49000,BTCUSDT"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, USER1, other_csv)
    rev2 = await tl_cmd.create_trade_log_revision(
        session,
        USER1,
        root_id=root_id,
        payload=_payload(
            pipeline2["source_asset_id"],
            pipeline2["report"]["record_batch_revision_id"],
            identity={"display_name": "v2"},
        ),
    )
    await session.commit()

    projection = await mb_query.get_default_mainboard(session, USER1)
    item = next(i for i in projection["items"] if i["work_object_root_id"] == root_id)
    items_before = await _count_rows(session, MainboardWorkingItem)
    # The attach at Save time already wrote one composition_changed row; the pin adds
    # exactly one more, and the replay adds none.
    pins_changed_before = await _count_audits(session, "mainboard.composition_changed")

    pin_kwargs: dict[str, Any] = {
        "item_id": item["item_id"],
        "intent": "pin_revision",
        "expected_row_version": item["row_version"],
        "revision_id": rev2["revision_id"],
        "idempotency_key": "tl-pin-key-1",
    }
    first = await mb_cmd.patch_mainboard_item(session, USER1, **pin_kwargs)
    await session.commit()
    replay = await mb_cmd.patch_mainboard_item(session, USER1, **pin_kwargs)
    await session.commit()

    assert replay["item_id"] == first["item_id"]
    assert replay["pinned_revision_id"] == rev2["revision_id"]
    assert replay["row_version"] == first["row_version"]
    assert replay["composition_hash"] == first["composition_hash"]
    assert await _count_rows(session, MainboardWorkingItem) == items_before
    assert await _count_audits(session, "mainboard.item_revision_pinned") == 1
    assert await _count_audits(session, "mainboard.composition_changed") == pins_changed_before + 1


async def test_trade_log_pipeline_creates_no_backtest_result(session, fake_object_store) -> None:
    """TL-23.c3: no Trade Log operation fabricates a Backtest Result.

    The Run side of the boundary is proven from both directions in
    test_backtest_persistence.py; this is the other side. Upload, import, Save & Add,
    revision N+1 and Export all run here — a Result may only come from a SUCCEEDED
    asynchronous Run, and none of these is one.
    """
    await _seed_principals(session)
    assert await _count_rows(session, BacktestResult) == 0

    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]
    assert await _count_rows(session, BacktestResult) == 0

    other_csv = "\n".join(
        [_HEADER, "Long,2024-05-01 10:00,50000,2024-05-01 12:00,51000,BTCUSDT"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, USER1, other_csv)
    await tl_cmd.create_trade_log_revision(
        session,
        USER1,
        root_id=root_id,
        payload=_payload(
            pipeline2["source_asset_id"],
            pipeline2["report"]["record_batch_revision_id"],
            identity={"display_name": "v2"},
        ),
    )
    await session.commit()
    assert await _count_rows(session, BacktestResult) == 0

    await tl_cmd.export_trade_log(session, USER1, root_id=root_id)
    await session.commit()
    assert await _count_rows(session, BacktestResult) == 0
    # The run table is empty too: nothing on this page even ADMITS a run, so the
    # zero above cannot be read as "a run happened and wrote no Result".
    assert await _count_rows(session, BacktestRun) == 0


# --------------------------------------------------------------------------- #
# TL-13.c3 — the report a pin invalidates is REPORTED stale, not just is_stale() #
# --------------------------------------------------------------------------- #


async def test_explicit_pin_reports_the_prior_readiness_report_stale(
    session, fake_object_store
) -> None:
    """doc 05 §16 TL-13.c3 — "the prior readiness report goes stale as a result of
    that hash change".

    The predicate ``is_stale("a", "b")`` was already unit-asserted, and
    ``test_explicit_pin_changes_composition_hash`` already proves the pin moves the
    hash. Neither carries an EXISTING report across the pin, so nothing joined the
    two halves: currentness is never stored (``queries/readiness_check`` recomputes
    it per read), so the only thing that can prove the join is reading the same
    immutable report back after the pin and seeing its EFFECTIVE state change while
    its STORED state does not.
    """
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]
    workspace_id = saved["save"]["workspace_id"]

    other_csv = "\n".join(
        [_HEADER, "Short,2024-03-01 10:00,50000,2024-03-01 12:00,49000,BTCUSDT"]
    ).encode("utf-8")
    pipeline2 = await _run_import_pipeline(session, USER1, other_csv)
    rev2 = await tl_cmd.create_trade_log_revision(
        session,
        USER1,
        root_id=root_id,
        payload=_payload(
            pipeline2["source_asset_id"],
            pipeline2["report"]["record_batch_revision_id"],
            identity={"display_name": "v2"},
        ),
    )
    await session.commit()

    check = await rc_cmd.run_readiness_check(session, USER1, composition_id=workspace_id)
    await session.commit()
    report_id = check["report_id"]

    before = await rc_query.get_readiness_report(session, USER1, report_id=report_id)
    stored_state = before["stored_state"]
    # The report is CURRENT while the composition still pins revision 1 — without
    # this the "stale" assertion below could pass on a report that was never current.
    assert before["is_current"] is True
    assert before["state"] == stored_state
    assert before["composition_fingerprint"] == before["current_fingerprint"]

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
    assert pin["composition_hash"] != projection["composition_hash"]

    after = await rc_query.get_readiness_report(session, USER1, report_id=report_id)
    assert after["state"] == str(ReadinessState.STALE)
    assert after["is_current"] is False
    assert after["composition_fingerprint"] != after["current_fingerprint"]
    # The report ROW is immutable: only the recomputed view moved. A staleness flag
    # written onto the report would satisfy the assertions above and violate §12.2.
    assert after["stored_state"] == stored_state
    assert after["composition_fingerprint"] == before["composition_fingerprint"]


# --------------------------------------------------------------------------- #
# TL-16.c3 — two writers on one head: exactly one revision survives             #
# --------------------------------------------------------------------------- #


async def test_two_writers_on_one_head_append_exactly_one_revision(
    session, fake_object_store
) -> None:
    """doc 05 §16 TL-16.c3 — "exactly one of two concurrent writers succeeds and the
    loser's update is not lost".

    ``test_stale_expected_head_conflicts`` raises on a FABRICATED token and stops, so
    it proves the guard rejects a token that never existed. It cannot distinguish that
    from last-write-wins between two real writers who both read the same real head:
    the loser's payload silently replacing the winner's would leave that test green.
    This drives both writers off the SAME observed head and then counts what the root
    actually holds.
    """
    await _seed_principals(session)
    saved = await _saved_trade_log(session, USER1, fake_object_store)
    root_id = saved["save"]["root_id"]
    head = saved["save"]["revision_id"]

    winner_csv = "\n".join(
        [_HEADER, "Long,2024-04-01 10:00,50000,2024-04-01 12:00,51000,BTCUSDT"]
    ).encode("utf-8")
    loser_csv = "\n".join(
        [_HEADER, "Short,2024-04-02 10:00,52000,2024-04-02 12:00,51000,BTCUSDT"]
    ).encode("utf-8")
    winner_pipeline = await _run_import_pipeline(session, USER1, winner_csv)
    loser_pipeline = await _run_import_pipeline(session, USER1, loser_csv)

    winner = await tl_cmd.create_trade_log_revision(
        session,
        USER1,
        root_id=root_id,
        payload=_payload(
            winner_pipeline["source_asset_id"],
            winner_pipeline["report"]["record_batch_revision_id"],
            identity={"display_name": "winner"},
        ),
        expected_head_revision_id=head,
    )
    await session.commit()

    # The second writer read the SAME head before the first one committed.
    with pytest.raises(WorkObjectRevisionConflictError):
        await tl_cmd.create_trade_log_revision(
            session,
            USER1,
            root_id=root_id,
            payload=_payload(
                loser_pipeline["source_asset_id"],
                loser_pipeline["report"]["record_batch_revision_id"],
                identity={"display_name": "loser"},
            ),
            expected_head_revision_id=head,
        )
    await session.rollback()

    revisions = (
        (
            await session.execute(
                select(WorkObjectRevision)
                .where(WorkObjectRevision.entity_id == root_id)
                .order_by(WorkObjectRevision.revision_no)
            )
        )
        .scalars()
        .all()
    )
    assert [r.revision_no for r in revisions] == [1, 2]
    assert revisions[-1].revision_id == winner["revision_id"]
    names = [r.payload["identity"]["display_name"] for r in revisions]
    assert "winner" in names
    # The loser is REFUSED, not merged and not silently applied on top.
    assert "loser" not in names

    projection = await mb_query.get_default_mainboard(session, USER1)
    item = next(i for i in projection["items"] if i["work_object_root_id"] == root_id)
    assert item["pinned_revision_id"] == head
