"""ADIM 21 — crash / retry / redelivery semantics for every worker plane.

The broker message is only transport; the ``jobs`` row is the source of truth. That
makes every durable actor an AT-LEAST-once delivery, and the target is not
exactly-once transport but EFFECTIVELY-once domain effects: whatever the broker or
the scheduler does, the durable world must end up with exactly one immutable
revision / validation run / imported package / purge outcome, one audit trail and
one outbox fan-out.

Two independent duplicate sources are exercised here:

* **the commit/ack boundary** — a worker commits its transaction and dies before
  the ack, so the SAME message is delivered again to a fresh session;
* **the lease-expiry boundary** — ``maintenance.redeliverable_queued_jobs``
  re-dispatches every row still QUEUED past the grace window, and a body that never
  commits its ``RUNNING`` transition mid-flight stays QUEUED for its whole run, so
  a second worker can be handed a job the first is still executing.

Failure is injected at real seams — the injectable ``load_and_parse`` /
``write_processed`` / ``stream_bars`` kwargs the bodies already expose, and the
object-store monkeypatch the ingest suites already use. There is no sleep anywhere
in this file; the concurrency test synchronises on Postgres row locks, not on time.

Planes whose redelivery idempotence is already pinned by a landed suite are
cross-referenced rather than duplicated:

* ``backtest``       -> test_backtest_persistence.py::test_worker_is_redelivery_idempotent
                        and test_backtest_run_events.py::
                        test_terminal_redelivery_writes_no_further_events
* ``agent-executor`` -> test_agent_executor.py (replay + pending-pause deferral)
* ``default``        -> test_create_package_{precheck,baseline,candidate_validation}_worker.py
* ``agent``/``agent-high`` -> test_gateway_parity_*.py (AL-14 tool-call idempotency)

What had NO coverage before this file — and, as the reproduction tests below show,
no guard either — is the five-actor ``data`` queue.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import package_import as import_cmd
from entropia.application.commands import trade_log as tl_cmd
from entropia.application.commands import trading_signal as ts_cmd
from entropia.application.jobs import purge as purge_job
from entropia.application.jobs.delivery import claim_job_for_delivery
from entropia.application.jobs.market_data import ParsedDataset
from entropia.application.jobs.market_data import run_analysis as run_market_analysis
from entropia.application.jobs.package_import import run_import as run_package_import
from entropia.application.jobs.research_data import ParsedResearch
from entropia.application.jobs.research_data import run_analysis as run_research_analysis
from entropia.application.jobs.trade_log import run_import as run_trade_log_import
from entropia.application.jobs.trading_signal import run_import as run_signal_import
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import JobStatus, PrincipalType, Role
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState, ResolutionKind
from entropia.domain.research_data.enums import AvailableTimePolicy, ResearchRevisionState
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    CanonicalTradeRecordBatch,
    Job,
    MarketValidationRun,
    NormalizedSignalEventRevision,
    OutboxEvent,
    PackageRoot,
    Principal,
    ResearchNativeAsset,
    ResearchValidationRun,
)
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.ids import new_id

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)

_SIGNAL_CSV = (
    b"source_record_id,event_time,available_time,direction,signal_type\n"
    b"r1,2024-05-01T10:00:00Z,2024-05-01T10:03:00Z,long,entry\n"
    b"r2,2024-05-02T10:00:00Z,2024-05-02T10:01:00Z,sell,exit\n"
)

_TRADE_CSV = (
    b"direction,entry_time,entry_price,exit_time,exit_price,symbol\n"
    b"long,2024-05-01T10:00:00Z,100,2024-05-01T12:00:00Z,110,BTCUSDT\n"
)


# --------------------------------------------------------------------------- #
# Shared fixtures / helpers                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    """In-process object storage so the ingest bodies run without MinIO."""
    store: dict[str, bytes] = {}

    def _put(source_asset_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"signals/source/{source_asset_id}/{digest}"
        store[key] = data
        return key, digest

    monkeypatch.setattr(datasets, "put_source_asset_bytes", _put)
    monkeypatch.setattr(datasets, "get_raw_bytes", lambda key: store[key])
    return store


async def _seed_principals(session: AsyncSession) -> None:
    for pid in ("user_admin", "user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _count(session: AsyncSession, model: Any, *where: Any) -> int:
    stmt = select(func.count()).select_from(model)
    for clause in where:
        stmt = stmt.where(clause)
    return int((await session.execute(stmt)).scalar_one())


async def _audit_and_outbox_counts(session: AsyncSession, kind: str) -> tuple[int, int]:
    """Audit + outbox rows carrying ``kind``. A duplicated worker run duplicates
    BOTH — the audit trail lies and SSE fans the same change out twice."""
    audits = await _count(session, AuditEvent, AuditEvent.event_kind == kind)
    outbox = await _count(session, OutboxEvent, OutboxEvent.event_type == kind)
    return audits, outbox


# --------------------------------------------------------------------------- #
# Per-plane job builders (the durable row + everything its body needs)          #
# --------------------------------------------------------------------------- #


async def _signal_import_job(session: AsyncSession) -> tuple[str, str]:
    upload = await ts_cmd.upload_source_asset(
        session, USER1, content=_SIGNAL_CSV, original_filename="signals.csv"
    )
    await session.commit()
    requested = await ts_cmd.request_trading_signal_import(
        session, USER1, source_asset_id=upload["source_asset_id"], instrument_id="BTCUSDT"
    )
    await session.commit()
    return str(requested["job_id"]), str(upload["source_asset_id"])


async def _trade_log_import_job(session: AsyncSession) -> tuple[str, str]:
    upload = await tl_cmd.upload_source_asset(
        session, USER1, content=_TRADE_CSV, original_filename="trades.csv"
    )
    await session.commit()
    requested = await tl_cmd.request_trade_log_import(
        session, USER1, source_asset_id=upload["source_asset_id"], instrument_id="BTCUSDT"
    )
    await session.commit()
    return str(requested["job_id"]), str(upload["source_asset_id"])


def _ohlcv(ts: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": "1", "high": "2", "low": "1", "close": "2", "volume": "10"}


async def _market_analysis_job(session: AsyncSession) -> tuple[str, str, ParsedDataset]:
    root, revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        market_data_type=MarketDataType.OHLCV,
        payload={"v": 1},
        revision_state=MarketRevisionState.ANALYZING,
    )
    revision.resolution_kind = ResolutionKind.BAR
    revision.resolution_value = "1m"
    await session.flush()
    job = Job(
        job_id=new_id("job"),
        queue="data",
        status=JobStatus.QUEUED,
        payload={"entity_id": root.entity_id, "revision_id": revision.revision_id},
    )
    session.add(job)
    await session.flush()
    parsed = ParsedDataset(
        market_data_type=MarketDataType.OHLCV,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
        rows=[
            _ohlcv("2024-05-01T10:00:00Z"),
            _ohlcv("2024-05-01T10:01:00Z"),
            _ohlcv("2024-05-01T10:02:00Z"),
        ],
    )
    return job.job_id, root.entity_id, parsed


async def _research_analysis_job(session: AsyncSession) -> tuple[str, str, ParsedResearch]:
    root, revision = await rd_repo.create_research_dataset(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        payload={"v": 1},
        linked_market_dataset_revision_id=None,
        revision_state=ResearchRevisionState.ANALYZING,
    )
    revision.available_time_policy = AvailableTimePolicy.SAME_AS_EVENT_TIME
    revision.instrument_mapping_ref = None
    await session.flush()
    job = Job(
        job_id=new_id("job"),
        queue="data",
        status=JobStatus.QUEUED,
        payload={"entity_id": root.entity_id, "revision_id": revision.revision_id},
    )
    session.add(job)
    await session.flush()
    parsed = ParsedResearch(
        columns=["x", "label"], rows=[{"x": i, "label": f"r{i}"} for i in range(5)]
    )
    return job.job_id, root.entity_id, parsed


def _import_manifest(**overrides: Any) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "package_root_id": "pkg_origin",
        "revision_id": "pkgrev_origin",
        "revision_no": 1,
        "package_kind": "indicator",
        "name": "Imported RSI",
        "input_contract": {"name": "Imported RSI"},
        "output_contract": {"kind": "directional_signal"},
        "dependency_snapshot": {"resolved": []},
        "rationale_family_snapshot": None,
        "validation_state": "passed",
        "approval_state": "approved",
        "content_hash": "c" * 64,
        "derived_from_revision_id": None,
    }
    manifest.update(overrides)
    return manifest


async def _package_import_job(session: AsyncSession) -> str:
    submitted = await import_cmd.submit_package_import(session, USER1, manifest=_import_manifest())
    await session.commit()
    return str(submitted["job_id"])


# --------------------------------------------------------------------------- #
# Group A — terminal redelivery (the commit/ack boundary), per data-plane actor #
# --------------------------------------------------------------------------- #
#
# Every test in this group is the SAME scenario: the body committed, the ack was
# lost, the broker handed the identical message to a fresh worker. Before the
# shared delivery claim landed, all five wrote a second immutable artifact plus a
# second audit + outbox row. The result the second delivery returns must also be
# the FIRST delivery's recorded outcome, not a newly minted one — a caller that
# reads ``normalized_event_revision_id`` off the replay would otherwise be pointed
# at a duplicate.


async def test_signal_import_redelivered_after_commit_writes_one_revision(
    session, fake_object_store
) -> None:
    await _seed_principals(session)
    job_id, asset_id = await _signal_import_job(session)

    first = await run_signal_import(session, job_id)
    await session.commit()
    replay = await run_signal_import(session, job_id)
    await session.commit()

    assert replay == first  # the recorded outcome, replayed verbatim
    assert (
        await _count(
            session,
            NormalizedSignalEventRevision,
            NormalizedSignalEventRevision.source_asset_id == asset_id,
        )
        == 1
    )
    assert await _audit_and_outbox_counts(session, "trading_signal.import_completed") == (1, 1)


async def test_trade_log_import_redelivered_after_commit_writes_one_batch(
    session, fake_object_store
) -> None:
    await _seed_principals(session)
    job_id, asset_id = await _trade_log_import_job(session)

    first = await run_trade_log_import(session, job_id)
    await session.commit()
    replay = await run_trade_log_import(session, job_id)
    await session.commit()

    assert replay == first
    assert (
        await _count(
            session,
            CanonicalTradeRecordBatch,
            CanonicalTradeRecordBatch.source_asset_id == asset_id,
        )
        == 1
    )
    assert await _audit_and_outbox_counts(session, "trade_log.import_completed") == (1, 1)


async def test_market_analysis_redelivered_after_commit_writes_one_validation_run(
    session,
) -> None:
    await _seed_principals(session)
    job_id, entity_id, parsed = await _market_analysis_job(session)

    async def _load(_s: AsyncSession, _e: str, _r: Any) -> ParsedDataset:
        return parsed

    async def _write(_s: AsyncSession, _e: str, _rid: str, _p: ParsedDataset) -> str:
        return "sha256:deadbeef"

    first = await run_market_analysis(session, job_id, load_and_parse=_load, write_processed=_write)
    await session.commit()
    replay = await run_market_analysis(
        session, job_id, load_and_parse=_load, write_processed=_write
    )
    await session.commit()

    assert replay == first
    assert (
        await _count(session, MarketValidationRun, MarketValidationRun.entity_id == entity_id) == 1
    )


async def test_research_analysis_redelivered_after_commit_writes_one_validation_run(
    session,
) -> None:
    await _seed_principals(session)
    job_id, entity_id, parsed = await _research_analysis_job(session)

    async def _load(_s: AsyncSession, _e: str) -> ParsedResearch:
        return parsed

    async def _write(s: AsyncSession, e: str, rid: str, p: ParsedResearch) -> ResearchNativeAsset:
        # Only the S3 write is faked; the asset ROW is written for real so the job's own
        # reverse pointer (``native_asset_id``, GH #703) is exercised, not stubbed.
        return rd_repo.add_native_asset(
            s,
            entity_id=e,
            object_key=f"s3://processed/{e}.parquet",
            content_digest="sha256:deadbeef",
            size_bytes=128,
            revision_id=rid,
            row_count=len(p.rows),
            schema_descriptor={"columns": p.columns},
        )

    first = await run_research_analysis(session, job_id, load_and_parse=_load, write_native=_write)
    await session.commit()
    replay = await run_research_analysis(session, job_id, load_and_parse=_load, write_native=_write)
    await session.commit()

    assert replay == first
    assert (
        await _count(session, ResearchValidationRun, ResearchValidationRun.entity_id == entity_id)
        == 1
    )


async def test_package_import_redelivered_after_commit_imports_one_package(session) -> None:
    """The worst duplicate of the five: a second delivery would mint a SECOND
    DRAFT package root with a fresh id, so the same imported package would exist
    twice in the registry with no way to tell which one anybody pinned."""
    await _seed_principals(session)
    job_id = await _package_import_job(session)
    before = await _count(session, PackageRoot)

    first = await run_package_import(session, job_id)
    await session.commit()
    replay = await run_package_import(session, job_id)
    await session.commit()

    assert replay == first
    assert await _count(session, PackageRoot) == before + 1
    assert await _audit_and_outbox_counts(session, "package.imported") == (1, 0)


async def test_purge_redelivery_never_purges_twice(session) -> None:
    """The maintenance plane's own guard (entry status != PURGE_PENDING) under the
    same at-least-once pressure: the second delivery is a recorded skip, not a
    second tombstone and not an overwrite of the recorded outcome."""
    from entropia.application.commands.agent_artifact import soft_delete_hypothesis_artifact
    from entropia.application.commands.deletion import request_purge
    from entropia.domain.agent_lab.enums import AgentTaskStatus, HypothesisStatus
    from entropia.domain.trash.page import TrashEntryStatus
    from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
    from entropia.infrastructure.postgres.repositories import trash as trash_repo
    from tests.integration.test_trash_agent_artifact import (
        AGENT,
        _entry_for,
        _mint_reauth_proof,
        _seed,
        _seed_task,
    )

    await _seed(session)
    task = await _seed_task(session, status=AgentTaskStatus.SUCCEEDED)
    artifact = await al_repo.create_hypothesis(
        session,
        status=HypothesisStatus.EXPLORING,
        title="Redelivery probe",
        mechanism="m",
        source_task_id=task.task_id,
        created_by_principal_id=AGENT.principal_id,
    )
    artifact_id = artifact.artifact_id
    await soft_delete_hypothesis_artifact(session, ADMIN, artifact_id=artifact_id)
    await session.commit()
    entry = await _entry_for(session, artifact_id)
    accepted = await request_purge(
        session,
        ADMIN,
        trash_entry_id=entry.id,
        confirmation_phrase="Redelivery probe",
        reauth_proof=await _mint_reauth_proof(session),
    )
    await session.commit()

    first = await purge_job.run_purge(session, str(accepted["purge_job_id"]))
    await session.commit()
    replay = await purge_job.run_purge(session, str(accepted["purge_job_id"]))
    await session.commit()

    assert first["purge_status"] == "completed"
    assert replay["skipped"] is True
    assert entry.status == TrashEntryStatus.PURGED
    assert await _count(session, AuditEvent, AuditEvent.event_kind == "trash.purge_completed") == 1
    tombstones = await trash_repo.get_tombstone(session, artifact_id)
    assert tombstones is not None


# --------------------------------------------------------------------------- #
# Group B — the lease-expiry boundary: two workers, one live job                #
# --------------------------------------------------------------------------- #
#
# The terminal guard alone cannot close this window. A data-plane body runs in ONE
# transaction, so its ``RUNNING`` transition is invisible until it commits — the
# durable row reads QUEUED for the whole run, which is exactly what
# ``maintenance.redeliverable_queued_jobs`` sweeps past the grace window. Two
# workers would therefore both read a pre-terminal status and both write.
#
# The claim's ``FOR UPDATE`` is what serializes them. These tests assert the lock
# is REALLY taken (a ``NOWAIT`` probe from a second connection must fail) rather
# than waiting on a clock — there is no sleep and no timeout here.


async def _second_connection_factory():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from .conftest import DATABASE_URL

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def test_a_live_delivery_locks_the_job_row_against_a_second_worker(
    session, fake_object_store
) -> None:
    """Worker A claimed the job and has not committed. Worker B must not be able
    to read the row for update — if it could, both would compute and both would
    insert, which is the duplicate the terminal guard cannot see."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    await _seed_principals(session)
    job_id, _asset_id = await _signal_import_job(session)

    job, replay = await claim_job_for_delivery(session, job_id)
    assert replay is None  # A owns this delivery
    assert job.job_id == job_id
    # A's transaction is still open: nothing is committed yet.

    engine, factory = await _second_connection_factory()
    try:
        async with factory() as worker_b:
            with pytest.raises(DBAPIError):  # asyncpg LockNotAvailableError (55P03)
                await worker_b.execute(
                    text("SELECT 1 FROM jobs WHERE job_id = :j FOR UPDATE NOWAIT"),
                    {"j": job_id},
                )
            await worker_b.rollback()
    finally:
        await engine.dispose()


async def test_a_second_worker_replays_once_the_first_delivery_commits(
    session, fake_object_store
) -> None:
    """The other half of the same window: once A commits, B's claim finds a
    terminal row and replays A's outcome instead of recomputing it."""
    await _seed_principals(session)
    job_id, asset_id = await _signal_import_job(session)

    first = await run_signal_import(session, job_id)
    await session.commit()

    engine, factory = await _second_connection_factory()
    try:
        async with factory() as worker_b:
            replay = await run_signal_import(worker_b, job_id)
            await worker_b.commit()
    finally:
        await engine.dispose()

    assert replay == first
    assert (
        await _count(
            session,
            NormalizedSignalEventRevision,
            NormalizedSignalEventRevision.source_asset_id == asset_id,
        )
        == 1
    )


# --------------------------------------------------------------------------- #
# Group C — crash BEFORE the commit: the guard must not break a genuine retry   #
# --------------------------------------------------------------------------- #
#
# A body that raises rolls its whole transaction back, so the durable row never
# reaches a terminal status and dramatiq's ``max_retries=3`` re-runs it from
# scratch. That path is the reason the guard keys on the DURABLE status and not
# on "have I seen this message before": a crashed attempt left nothing behind and
# must be retried, while a committed attempt must not.


async def test_a_crash_before_commit_leaves_nothing_and_the_retry_writes_once(
    session,
) -> None:
    await _seed_principals(session)
    job_id, entity_id, parsed = await _market_analysis_job(session)
    await session.commit()

    async def _load(_s: AsyncSession, _e: str, _r: Any) -> ParsedDataset:
        return parsed

    async def _boom(_s: AsyncSession, _e: str, _rid: str, _p: ParsedDataset) -> str:
        raise RuntimeError("worker killed mid-write")

    async def _ok(_s: AsyncSession, _e: str, _rid: str, _p: ParsedDataset) -> str:
        return "sha256:deadbeef"

    with pytest.raises(RuntimeError):
        await run_market_analysis(session, job_id, load_and_parse=_load, write_processed=_boom)
    await session.rollback()  # exactly what the actor wrapper does

    job = await session.get(Job, job_id)
    assert job is not None
    assert job.status is JobStatus.QUEUED  # the RUNNING write rolled back with it
    assert (
        await _count(session, MarketValidationRun, MarketValidationRun.entity_id == entity_id) == 0
    )

    # Redelivery of the crashed attempt runs the body for real, exactly once.
    await run_market_analysis(session, job_id, load_and_parse=_load, write_processed=_ok)
    await session.commit()
    assert (
        await _count(session, MarketValidationRun, MarketValidationRun.entity_id == entity_id) == 1
    )
    assert (await session.get(Job, job_id)).status is JobStatus.SUCCEEDED  # type: ignore[union-attr]


async def test_an_expected_business_failure_is_recorded_and_never_retried(session) -> None:
    """Requirement 8's other half: an *expected* failure is a durable terminal
    outcome, not an exception. A malformed import manifest fails the import row,
    succeeds the job, and a redelivery replays that failure instead of re-running
    the parse — infra failures retry, business failures do not."""
    await _seed_principals(session)
    submitted = await import_cmd.submit_package_import(
        session, USER1, manifest=_import_manifest(input_contract=None)
    )
    await session.commit()
    job_id = str(submitted["job_id"])

    first = await run_package_import(session, job_id)
    await session.commit()
    assert first["status"] == "failed"
    assert first["result_package_root_id"] is None

    replay = await run_package_import(session, job_id)
    await session.commit()
    assert replay == first
    job = await session.get(Job, job_id)
    assert job is not None and job.status is JobStatus.SUCCEEDED  # the JOB did its job
    assert await _count(session, AuditEvent, AuditEvent.event_kind == "package.imported") == 1


# --------------------------------------------------------------------------- #
# Group D — the object-store boundary                                          #
# --------------------------------------------------------------------------- #


async def test_object_writes_are_content_addressed_so_a_retry_orphans_nothing(
    session, monkeypatch
) -> None:
    """Requirement 9. The object write happens BEFORE the DB commit, so a crash
    between them leaves an object with no row. There is no reconciliation sweep —
    and none is needed for a deterministic retry: every data-plane object key is
    ``<prefix>/<entity_id>/<sha256-of-bytes>``, so a retry that re-parses the same
    source rewrites the SAME key. The residual orphan is bounded to the case where
    a retry produces DIFFERENT bytes; this test pins the addressing that makes the
    common case self-healing rather than asserting a cleanup that does not exist.
    """
    from entropia.infrastructure.s3.datasets import content_digest, processed_object_key

    await _seed_principals(session)
    job_id, entity_id, parsed = await _market_analysis_job(session)
    await session.commit()

    written: list[str] = []

    async def _load(_s: AsyncSession, _e: str, _r: Any) -> ParsedDataset:
        return parsed

    async def _write(_s: AsyncSession, e: str, _rid: str, p: ParsedDataset) -> str:
        # Mirrors _write_processed's real addressing without needing MinIO.
        payload = repr(p.rows).encode("utf-8")
        digest = content_digest(payload)
        written.append(processed_object_key(e, digest))
        raise RuntimeError("killed after the object write, before the commit")

    with pytest.raises(RuntimeError):
        await run_market_analysis(session, job_id, load_and_parse=_load, write_processed=_write)
    await session.rollback()

    # The DB knows nothing about the object that was just written: a true orphan.
    assert (
        await _count(session, MarketValidationRun, MarketValidationRun.entity_id == entity_id) == 0
    )

    async def _write_ok(_s: AsyncSession, e: str, _rid: str, p: ParsedDataset) -> str:
        payload = repr(p.rows).encode("utf-8")
        digest = content_digest(payload)
        written.append(processed_object_key(e, digest))
        return digest

    await run_market_analysis(session, job_id, load_and_parse=_load, write_processed=_write_ok)
    await session.commit()

    # The retry addressed the SAME key -> the orphan was overwritten, not leaked.
    assert len(written) == 2
    assert written[0] == written[1]
    assert (
        await _count(session, MarketValidationRun, MarketValidationRun.entity_id == entity_id) == 1
    )
