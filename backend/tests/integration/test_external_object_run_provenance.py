"""A completed Run's provenance outlives the object that produced it (docs 03/04/05).

Auto-skips without PostgreSQL (see tests/integration/conftest.py).

Every criterion here rests on the same missing machinery: **a COMPLETED Backtest Run
over a composition that contains an external work object**. No test in the suite put a
Trade Log into a run composition at all, and the Trading Signal side stopped at
admission — so "revision N+1 does not disturb a finished run" and "a historical Result
still resolves its original provenance" were arguments, not assertions.

Acceptance (batch 02 of the class-B ledger, ADIM 49):

- ``TL-12.c2`` revision N's content hash + source asset ref are unchanged after N+1
- ``TL-12.c3`` a completed run's manifest still resolves the revision it pinned
- ``TL-20.c3`` a completed historical Result still resolves the original Trade Log
  revision and provenance from its manifest — *after the root is soft-deleted*
- ``TS-11.c3`` a completed run manifest is unchanged by a new Signal revision
- ``TS-21.c1`` Signal save / import / export create no Backtest Result row
- ``AOS-21.c1`` selecting or saving an external object creates no Backtest Result row

The harness is deliberately assembled from the EXISTING builders rather than a new
one: ``_ready_composition`` (strategy + market revision + indicator package),
``_e2e_bars`` (deterministic bar replay) and ``_attach_trading_signal`` are reused
verbatim; only the Trade Log attach had no equivalent and is added here.

NOT covered here, and deliberately so: ``TL-11.c3`` names a run over an
*allocation-enabled* composition. Shared capital allocation is fail-closed at
admission in this build (``SHARED_ALLOCATION_STATUS == "future_dev"`` ->
``ALLOCATION_SHARED_MODE_NOT_IN_BUILD``), so that run cannot be admitted and no test
can construct it. See the ledger note on TL-11.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import trade_log as tl_cmd
from entropia.application.commands import trading_signal as ts_cmd
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.jobs.trade_log import run_import
from entropia.application.jobs.trading_signal import run_import as ts_run_import
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import trade_log as tl_query
from entropia.domain.identity import Actor
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    WorkObjectRevision,
)
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.s3 import datasets
from tests.integration.test_backtest_manifest_pinning import _attach_trading_signal
from tests.integration.test_backtest_persistence import (
    USER1,
    _count,
    _e2e_bars,
    _ready_composition,
    _seed_principals,
)

pytestmark = pytest.mark.integration

_HEADER = "direction,entry_time,entry_price,exit_time,exit_price,symbol"
_GOOD_CSV = "\n".join(
    [
        _HEADER,
        "Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850,BTCUSDT",
        "Short,2024-01-02 09:15,43000,2024-01-02 18:00,41950,BTCUSDT",
    ]
).encode("utf-8")
_SECOND_CSV = "\n".join(
    [_HEADER, "Long,2024-02-01 10:00,50000,2024-02-01 12:00,51000,BTCUSDT"]
).encode("utf-8")
_SIGNAL_CSV = "\n".join(
    [
        "event_time,symbol,side",
        "2024-01-01 10:00,BTCUSDT,long",
        "2024-01-02 10:00,BTCUSDT,short",
    ]
).encode("utf-8")


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    """In-process object storage so upload + the import worker run without MinIO."""
    store: dict[str, bytes] = {}

    def _put(source_asset_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"signals/source/{source_asset_id}/{digest}"
        store[key] = data
        return key, digest

    monkeypatch.setattr(datasets, "put_source_asset_bytes", _put)
    monkeypatch.setattr(datasets, "get_raw_bytes", lambda object_key: store[object_key])
    return store


def _trade_log_payload(source_asset_id: str, batch_id: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "trade_log",
        "identity": {"display_name": "Binance BTCUSDT trade history"},
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
            "record_batch_revision_id": batch_id,
        },
    }
    payload.update(overrides)
    return payload


async def _import_trade_log(session, actor: Actor, csv_bytes: bytes) -> dict[str, Any]:
    """Upload -> request import -> run the worker. Returns the asset + batch ids."""
    upload = await tl_cmd.upload_source_asset(
        session, actor, content=csv_bytes, original_filename="trades.csv"
    )
    await session.commit()
    requested = await tl_cmd.request_trade_log_import(
        session, actor, source_asset_id=upload["source_asset_id"], instrument_id="BTCUSDT"
    )
    await session.commit()
    await run_import(session, requested["job_id"])
    await session.commit()
    report = await tl_query.get_import_report(session, actor, job_id=requested["job_id"])
    assert report["status"] == "succeeded"
    return {
        "source_asset_id": upload["source_asset_id"],
        "record_batch_revision_id": report["record_batch_revision_id"],
    }


async def _attach_trade_log(session, actor: Actor, workspace_id: str) -> dict[str, Any]:
    """The Trade Log twin of ``_attach_trading_signal`` — the piece that did not exist.

    Runs the REAL durable pipeline (upload -> import worker -> Save & Add) so the
    composition carries a genuine canonical record batch, not a hand-written row.
    """
    imported = await _import_trade_log(session, actor, _GOOD_CSV)
    saved = await tl_cmd.create_trade_log_and_attach(
        session,
        actor,
        payload=_trade_log_payload(
            imported["source_asset_id"], imported["record_batch_revision_id"]
        ),
        workspace_id=workspace_id,
    )
    await session.commit()
    assert saved["attached"] is True
    return {**imported, "root_id": saved["root_id"], "revision_id": saved["revision_id"]}


async def _completed_run(session, composition_id: str) -> dict[str, Any]:
    """Admit and drive one run to SUCCEEDED. Returns run/result ids + manifest hash."""
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out["state"] == "succeeded"
    return {"run_id": admit["run_id"], **out}


def _external_entry(manifest: dict[str, Any], item_kind: str) -> dict[str, Any]:
    return next(e for e in manifest["external_object_context"] if e["item_kind"] == item_kind)


# --------------------------------------------------------------------------- #
# TL-12 — revision N is immutable, and a finished run keeps pointing at it     #
# --------------------------------------------------------------------------- #


async def test_trade_log_revision_n_survives_n_plus_one_byte_for_byte(
    session, fake_object_store
) -> None:
    """TL-12.c2: appending N+1 leaves N's content hash AND source asset ref alone.

    ``test_new_revision_does_not_auto_repin`` proves a NEW id appears and the board pin
    does not move; neither fact would notice revision N being rewritten underneath.
    This reads N's own columns before and after.
    """
    await _seed_principals(session)
    workspace_id = (await _ready_composition(session, USER1))[0]
    first = await _attach_trade_log(session, USER1, workspace_id)

    revision_n = await session.get(WorkObjectRevision, first["revision_id"])
    assert revision_n is not None
    hash_before = revision_n.content_hash
    provenance_before = dict(revision_n.source_provenance or {})
    payload_before = dict(revision_n.payload)
    assert hash_before and provenance_before

    second = await _import_trade_log(session, USER1, _SECOND_CSV)
    revised = await tl_cmd.create_trade_log_revision(
        session,
        USER1,
        root_id=first["root_id"],
        payload=_trade_log_payload(
            second["source_asset_id"],
            second["record_batch_revision_id"],
            identity={"display_name": "Binance BTCUSDT trade history v2"},
        ),
    )
    await session.commit()
    assert revised["revision_id"] != first["revision_id"]

    # Re-READ N from the database rather than trusting the identity map.
    session.expire_all()
    revision_n = await session.get(WorkObjectRevision, first["revision_id"])
    assert revision_n is not None
    assert revision_n.content_hash == hash_before
    assert dict(revision_n.source_provenance or {}) == provenance_before
    assert revision_n.payload == payload_before
    # The source asset ref is the clause's own words — pin it by name, not by blob.
    assert revision_n.payload["import_binding"]["source_asset_id"] == first["source_asset_id"]
    assert revision_n.payload["import_binding"]["source_asset_id"] != second["source_asset_id"]


async def test_completed_run_manifest_keeps_the_trade_log_revision_it_pinned(
    session, fake_object_store
) -> None:
    """TL-12.c3: a finished run resolves the revision it pinned, never the new head."""
    await _seed_principals(session)
    workspace_id = (await _ready_composition(session, USER1))[0]
    trade_log = await _attach_trade_log(session, USER1, workspace_id)
    run = await _completed_run(session, workspace_id)

    manifest_before = (await bt_repo.get_manifest_by_run(session, run["run_id"])).manifest
    pinned = _external_entry(manifest_before, "trade_log")
    assert pinned["work_object_revision_id"] == trade_log["revision_id"]

    second = await _import_trade_log(session, USER1, _SECOND_CSV)
    revised = await tl_cmd.create_trade_log_revision(
        session,
        USER1,
        root_id=trade_log["root_id"],
        payload=_trade_log_payload(
            second["source_asset_id"],
            second["record_batch_revision_id"],
            identity={"display_name": "Binance BTCUSDT trade history v2"},
        ),
    )
    await session.commit()

    session.expire_all()
    stored = await bt_repo.get_manifest_by_run(session, run["run_id"])
    after = _external_entry(dict(stored.manifest), "trade_log")
    assert after["work_object_revision_id"] == trade_log["revision_id"]
    assert after["work_object_revision_id"] != revised["revision_id"]
    # The whole entry is untouched, not merely its id field, and the manifest hash the
    # run was admitted under still matches — a rewritten manifest would move it.
    assert after == pinned
    assert stored.manifest_hash == run["manifest_hash"]


async def test_soft_deleted_trade_log_still_resolves_from_the_historical_manifest(
    session, fake_object_store
) -> None:
    """TL-20.c3: the Result outlives the object — provenance is read from the manifest.

    ``test_soft_delete_removes_item_from_projection`` proves the row LEAVES the active
    board and reaches Trash. It says nothing about the finished Result, which is the
    half that matters: a Result whose provenance were joined from the live composition
    would go blank here.
    """
    await _seed_principals(session)
    workspace_id = (await _ready_composition(session, USER1))[0]
    trade_log = await _attach_trade_log(session, USER1, workspace_id)
    run = await _completed_run(session, workspace_id)
    assert await _count(session, BacktestResult) == 1

    await mb_cmd.soft_delete_work_object(session, USER1, root_id=trade_log["root_id"])
    await session.commit()

    # The active projection has genuinely dropped it — otherwise the assertions below
    # would be satisfied by an object that never left.
    projection = await mb_query.get_default_mainboard(session, USER1)
    assert trade_log["root_id"] not in [item["work_object_root_id"] for item in projection["items"]]

    session.expire_all()
    stored = await bt_repo.get_manifest_by_run(session, run["run_id"])
    assert stored is not None
    entry = _external_entry(dict(stored.manifest), "trade_log")
    assert entry["work_object_revision_id"] == trade_log["revision_id"]
    # Provenance, not just identity: the source asset and the canonical batch that
    # produced the numbers are still named, with the batch's own content hash.
    assert entry["import_binding"]["source_asset_id"] == trade_log["source_asset_id"]
    assert (
        entry["import_binding"]["record_batch_revision_id"] == trade_log["record_batch_revision_id"]
    )
    batch = entry["canonical_record_batch"]
    assert batch["record_batch_revision_id"] == trade_log["record_batch_revision_id"]
    assert batch["status"] == "succeeded"
    assert batch["accepted_count"] == 2
    assert len(batch["content_hash"]) == 64
    # The Result row itself survives the delete and still points at this run.
    result = await session.get(BacktestResult, run["result_id"])
    assert result is not None
    assert await _count(session, BacktestResult) == 1


# --------------------------------------------------------------------------- #
# TS-11 — the Trading Signal twin of TL-12.c3                                  #
# --------------------------------------------------------------------------- #


async def test_completed_run_manifest_is_unchanged_by_a_new_signal_revision(
    session,
) -> None:
    """TS-11.c3: revision N+1 on a Signal does not disturb a finished run's manifest."""
    await _seed_principals(session)
    workspace_id = (await _ready_composition(session, USER1))[0]
    signal = await _attach_trading_signal(session, USER1, workspace_id)
    run = await _completed_run(session, workspace_id)

    manifest_before = (await bt_repo.get_manifest_by_run(session, run["run_id"])).manifest
    pinned = _external_entry(manifest_before, "trading_signal")
    assert pinned["work_object_revision_id"] == signal["revision_id"]

    # A second Signal, imported and attached the same way, stands in for the provider
    # change: what the clause guards is the FINISHED manifest, not the edit path.
    second = await _attach_trading_signal(session, USER1, workspace_id)
    assert second["revision_id"] != signal["revision_id"]

    session.expire_all()
    stored = await bt_repo.get_manifest_by_run(session, run["run_id"])
    after = _external_entry(dict(stored.manifest), "trading_signal")
    assert after == pinned
    assert after["work_object_revision_id"] != second["revision_id"]
    assert stored.manifest_hash == run["manifest_hash"]


# --------------------------------------------------------------------------- #
# TS-21 / AOS-21 — only a succeeded Run mints a Result                         #
# --------------------------------------------------------------------------- #


async def _root_id_of(session, revision_id: str) -> str:
    revision = await session.get(WorkObjectRevision, revision_id)
    assert revision is not None
    return revision.entity_id


async def test_signal_import_save_and_export_create_no_backtest_result(
    session, fake_object_store
) -> None:
    """TS-21.c1: the Signal-side half of the Result boundary.

    The Run side is proven from both directions in test_backtest_persistence.py; this
    counts the table after each of the three operations the criterion names by word —
    import, save and export — rather than after a single one standing in for all.
    """
    await _seed_principals(session)
    workspace_id = (await _ready_composition(session, USER1))[0]
    assert await _count(session, BacktestResult) == 0

    # import: the durable worker, not a seeded row.
    upload = await ts_cmd.upload_source_asset(
        session, USER1, content=_SIGNAL_CSV, original_filename="signals.csv"
    )
    await session.commit()
    requested = await ts_cmd.request_trading_signal_import(
        session, USER1, source_asset_id=upload["source_asset_id"], instrument_id="BTCUSDT"
    )
    await session.commit()
    await ts_run_import(session, requested["job_id"])
    await session.commit()
    assert await _count(session, BacktestResult) == 0

    # save
    signal = await _attach_trading_signal(session, USER1, workspace_id)
    assert await _count(session, BacktestResult) == 0

    # export
    exported = await ts_cmd.export_trading_signal(
        session, USER1, root_id=await _root_id_of(session, signal["revision_id"])
    )
    await session.commit()
    assert exported["manifest_hash"]
    assert await _count(session, BacktestResult) == 0

    # A zero is only evidence if this counter can reach one: drive the run that IS
    # allowed to mint a Result, so the three zeros above cannot be a broken query.
    run = await _completed_run(session, workspace_id)
    assert run["result_id"]
    assert await _count(session, BacktestResult) == 1


async def test_saving_an_external_object_creates_no_backtest_result(
    session, fake_object_store
) -> None:
    """AOS-21.c1: doc 03 scopes the claim to the external object line as a whole.

    Both children of the Add Outsource Signal chooser are exercised — a Trading Signal
    and a Trade Log — because doc 03's row is about the page, not one kind. Only after
    a run is driven does a Result appear, which is what makes the zeros above mean
    something rather than describing an empty database.
    """
    await _seed_principals(session)
    workspace_id = (await _ready_composition(session, USER1))[0]

    await _attach_trading_signal(session, USER1, workspace_id)
    assert await _count(session, BacktestResult) == 0

    await _attach_trade_log(session, USER1, workspace_id)
    assert await _count(session, BacktestResult) == 0

    run = await _completed_run(session, workspace_id)
    assert run["result_id"]
    assert await _count(session, BacktestResult) == 1
