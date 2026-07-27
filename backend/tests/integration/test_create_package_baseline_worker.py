"""F-01c baseline-parse durable worker — real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py). This is
the LAST advertised-async Create-Package operation Finding F-01 called out: the POST is an
ADMISSION that returns a durable QUEUED job and a ``parsing`` asset with NO parse evidence;
the worker body drives queued -> running -> succeeded/failed, reads the stored CSV and
writes the terminal ``passed`` / ``failed`` status; an unparseable CSV or a worker crash is
a DURABLE failed attempt (never a silent pass, never an infinite retry); a redelivered
message replays the durable outcome; a delivery whose head baseline moved on is SUPERSEDED;
and the admission-time gates (head baseline, metadata completeness, the OCC token) still
fail fast with their typed errors.

The browser-close acceptance is structural, not timing-based: the admission transaction
commits with the parse UNDONE and the durable job as the only pointer to the remaining
work, so nothing about the HTTP request's lifetime can cancel it. The tests below assert
exactly that split — the asset is still ``parsing`` and ``baseline_ready`` is false after
the admission commits, and only the separately-driven worker delivery lands the verdict.
"""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import func, select

from entropia.application.commands import create_package as cp_cmd
from entropia.application.jobs import create_package as cp_jobs
from entropia.application.queries import create_package as cp_query
from entropia.domain.create_package.enums import (
    BaselineParseStatus,
    CreationMode,
    SourceLanguage,
)
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    JobStatus,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import AuditEvent, Job, OutboxEvent, Principal
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import (
    BaselineAssetNotFound,
    BaselineMetadataInvalid,
    RequestVersionConflict,
)

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_RSI_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
_RSI_DEP = {"key": "ta.rsi", "signature": _RSI_SIG}
_INDICATOR_OUTPUT = {"kind": "directional_signal"}
_FULL_METADATA = {
    "provider": "tradingview",
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "range": {"start": "2024-01-01", "end": "2024-06-01"},
    "timezone": "UTC",
    "settings": {"rsi_length": 14},
    "source_revision_context": "pine v5 @ abcdef",
}
_GOOD_CSV = b"time,rsi\n2024-01-01T00:00:00Z,55.2\n2024-01-01T01:00:00Z,48.7\n"
_HEADER_ONLY_CSV = b"time,rsi\n"


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    """In-process object storage so the upload + the worker's read run without MinIO."""
    store: dict[str, bytes] = {}

    def _put(request_entity_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"create-package/baseline/{request_entity_id}/{digest}"
        store[key] = data
        return key, digest

    def _get(object_key: str) -> bytes:
        return store[object_key]

    monkeypatch.setattr(datasets, "put_baseline_bytes", _put)
    monkeypatch.setattr(datasets, "get_raw_bytes", _get)
    return store


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_python_resolver(session, *, key: str = "ta.rsi") -> str:
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        package_kind=PackageKind.EMBEDDED_SYSTEM,
        input_contract={"resolver_key": key},
        output_contract={"return": "series"},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.SYSTEM,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    esp_repo.add_resolver_contract(
        session,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        canonical_key=key,
        signature=_RSI_SIG,
        runtime_adapter=RuntimeAdapter.PYTHON,
    )
    esp_repo.upsert_registry_entry(
        session,
        canonical_key=key,
        package_entity_id=root.entity_id,
        runtime_adapter=RuntimeAdapter.PYTHON,
        trust_state=ResolverTrustState.TRUSTED_ACTIVE,
        trusted_active_revision_id=revision.revision_id,
        updated_by_principal_id="user_admin",
    )
    return revision.revision_id


async def _seed_family(session) -> str:
    root, _detail, _revision = await rationale_repo.create_family(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        display_name="Reversal / Mean Reversion",
        normalized_name="reversal / mean reversion",
        subfamilies=[],
        compatible_output_types=["directional_signal"],
        display_color="#FFD1DC",
        change_note=None,
    )
    return root.entity_id


async def _run_job(session, job_id: str) -> dict:
    """Drive one durable delivery through the dispatcher, exactly as the actor does."""
    return await cp_jobs.run_create_package_job(session, job_id)


async def _seeded_request(session) -> str:
    """A TRANSLATE (equivalence-claiming) request — the baseline gate is live."""
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await cp_cmd.create_package_request(
        session,
        OWNER,
        package_type="indicator",
        creation_mode=CreationMode.TRANSLATE_EXISTING_CODE,
        source_language=SourceLanguage.PINESCRIPT,
        other_language_label=None,
        target_runtime=RuntimeAdapter.PYTHON,
        request_body="//@version=5\nindicator('rsi')\nta.rsi(close, 14)",
        output_contract=_INDICATOR_OUTPUT,
        rationale_family_id=family_id,
        declared_dependencies=[_RSI_DEP],
        equivalence_claim=True,
    )
    await session.commit()
    return str(created["request_id"])


async def _upload(session, request_id: str, content: bytes = _GOOD_CSV) -> dict:
    uploaded = await cp_cmd.upload_baseline_asset(
        session,
        OWNER,
        request_id=request_id,
        content=content,
        baseline_metadata=_FULL_METADATA,
        original_filename="baseline.csv",
    )
    await session.commit()
    return uploaded


async def _admit(session, request_id: str) -> dict:
    admitted = await cp_cmd.start_baseline_parse(session, OWNER, request_id=request_id)
    await session.commit()
    return admitted


async def _head_asset(session, request_id: str):
    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None
    return await cp_repo.get_current_baseline_asset(session, detail)


# ---------------------------------------------------------------------------
# Admission
# ---------------------------------------------------------------------------


async def test_admission_returns_queued_durable_job_and_no_evidence(
    session, fake_object_store
) -> None:
    request_id = await _seeded_request(session)
    uploaded = await _upload(session, request_id)

    admitted = await _admit(session, request_id)

    # The admission never fabricates a verdict: the CSV has not been read yet.
    assert admitted["parse_status"] == str(BaselineParseStatus.PARSING)
    assert admitted["parser_version"] == ""
    assert admitted["parse_report"] == {}
    assert admitted["baseline_asset_id"] == uploaded["baseline_asset_id"]
    job = await session.get(Job, admitted["job_id"])
    assert job is not None
    assert job.status == JobStatus.QUEUED
    assert job.queue == "default"
    assert job.payload == {
        "kind": "baseline_parse",
        "request_id": request_id,
        "baseline_asset_id": uploaded["baseline_asset_id"],
    }
    # This is the browser-close guarantee: the admission tx is committed with the parse
    # undone, and the durable job row is the only thing that owns the remaining work.
    asset = await _head_asset(session, request_id)
    assert asset is not None
    assert asset.parse_status == BaselineParseStatus.PARSING
    assert asset.parse_job_id == admitted["job_id"]
    assert asset.parse_report is None
    assert asset.parsed_at is None
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["current_baseline"]["parse_status"] == str(BaselineParseStatus.PARSING)
    assert projection["baseline_ready"] is False


async def test_admission_bumps_request_version_for_occ(session, fake_object_store) -> None:
    request_id = await _seeded_request(session)
    await _upload(session, request_id)
    before = await cp_query.get_package_request(session, OWNER, request_id=request_id)

    admitted = await _admit(session, request_id)
    assert admitted["request_version"] == before["request_version"] + 1

    # A second submit holding the pre-admission token is rejected (no second job).
    jobs_before = await _count(session, Job)
    with pytest.raises(RequestVersionConflict):
        await cp_cmd.start_baseline_parse(
            session,
            OWNER,
            request_id=request_id,
            expected_request_version=before["request_version"],
        )
    await session.rollback()
    assert await _count(session, Job) == jobs_before


async def test_admission_gates_still_fail_fast(session, fake_object_store) -> None:
    """The pure gates stay at admission — they never reach the worker."""
    request_id = await _seeded_request(session)
    jobs_before = await _count(session, Job)

    with pytest.raises(BaselineAssetNotFound):
        await cp_cmd.start_baseline_parse(session, OWNER, request_id=request_id)
    await session.rollback()

    await cp_cmd.upload_baseline_asset(
        session,
        OWNER,
        request_id=request_id,
        content=_GOOD_CSV,
        baseline_metadata={"provider": "tradingview", "symbol": "BTCUSDT"},
        original_filename="baseline.csv",
    )
    await session.commit()
    with pytest.raises(BaselineMetadataInvalid):
        await cp_cmd.start_baseline_parse(session, OWNER, request_id=request_id)
    await session.rollback()

    assert await _count(session, Job) == jobs_before
    asset = await _head_asset(session, request_id)
    assert asset is not None
    assert asset.parse_status == BaselineParseStatus.UPLOADED


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------


async def test_worker_lifecycle_passed(session, fake_object_store) -> None:
    request_id = await _seeded_request(session)
    await _upload(session, request_id)
    admitted = await _admit(session, request_id)
    outbox_before = await _count(session, OutboxEvent)
    audit_before = await _count(session, AuditEvent)

    result = await _run_job(session, admitted["job_id"])
    await session.commit()

    assert result["parse_status"] == str(BaselineParseStatus.PASSED)
    assert result["parse_report"]["row_count"] == 2
    assert result["parse_report"]["columns"] == ["time", "rsi"]
    assert result["parser_version"] != ""
    job = await session.get(Job, admitted["job_id"])
    assert job is not None
    assert job.status == JobStatus.SUCCEEDED
    assert job.started_at is not None
    assert job.finished_at is not None
    assert job.result_ref == result

    asset = await _head_asset(session, request_id)
    assert asset is not None
    assert asset.parse_status == BaselineParseStatus.PASSED
    assert asset.parsed_at is not None
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["baseline_ready"] is True
    # One resource.changed + one audit event, produced by the worker (not the admission).
    assert await _count(session, OutboxEvent) == outbox_before + 1
    assert await _count(session, AuditEvent) == audit_before + 1


async def test_unparseable_csv_is_a_durable_failed_attempt(session, fake_object_store) -> None:
    request_id = await _seeded_request(session)
    await _upload(session, request_id, content=_HEADER_ONLY_CSV)
    admitted = await _admit(session, request_id)

    result = await _run_job(session, admitted["job_id"])
    await session.commit()

    assert result["parse_status"] == str(BaselineParseStatus.FAILED)
    assert result["error"]["code"] == "PARSE_FAILED"
    job = await session.get(Job, admitted["job_id"])
    assert job is not None
    assert job.status == JobStatus.FAILED_FINAL
    assert job.error is not None

    asset = await _head_asset(session, request_id)
    assert asset is not None
    assert asset.parse_status == BaselineParseStatus.FAILED
    assert asset.parse_report["is_parseable"] is False
    assert asset.parse_report["code"] == "PARSE_FAILED"
    # The equivalence gate is unaffected by a failed parse: still not publishable.
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["baseline_ready"] is False
    assert projection["baseline_required"] is True


async def test_worker_crash_is_a_durable_failed_attempt(
    session, fake_object_store, monkeypatch
) -> None:
    """A read/compute crash is NOT a pass — it is a recorded failure (Finding F-01)."""
    request_id = await _seeded_request(session)
    await _upload(session, request_id)
    admitted = await _admit(session, request_id)

    def _boom(_content):
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(cp_jobs, "parse_baseline_csv", _boom)
    result = await _run_job(session, admitted["job_id"])
    await session.commit()

    assert result["parse_status"] == str(BaselineParseStatus.FAILED)
    assert result["error"]["code"] == "BASELINE_PARSE_WORKER_FAILED"
    job = await session.get(Job, admitted["job_id"])
    assert job is not None
    assert job.status == JobStatus.FAILED_FINAL
    asset = await _head_asset(session, request_id)
    assert asset is not None
    assert asset.parse_status == BaselineParseStatus.FAILED
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["baseline_ready"] is False


async def test_worker_is_redelivery_idempotent(session, fake_object_store) -> None:
    request_id = await _seeded_request(session)
    await _upload(session, request_id)
    admitted = await _admit(session, request_id)
    first = await _run_job(session, admitted["job_id"])
    await session.commit()
    audit_after_first = await _count(session, AuditEvent)

    replay = await _run_job(session, admitted["job_id"])
    await session.commit()

    assert replay == first
    # A redelivery re-parses nothing and emits no second event.
    assert await _count(session, AuditEvent) == audit_after_first


async def test_reupload_supersedes_an_in_flight_delivery(session, fake_object_store) -> None:
    """A fresh upload makes a NEW head attempt; the older delivery records nothing."""
    request_id = await _seeded_request(session)
    first_upload = await _upload(session, request_id)
    admitted = await _admit(session, request_id)

    second_upload = await _upload(session, request_id, content=_GOOD_CSV + b"x,1\n")
    assert second_upload["baseline_asset_id"] != first_upload["baseline_asset_id"]

    result = await _run_job(session, admitted["job_id"])
    await session.commit()

    assert result["superseded"] is True
    job = await session.get(Job, admitted["job_id"])
    assert job is not None and job.status == JobStatus.SUPERSEDED
    # The superseded attempt keeps its own in-flight status; the new head is untouched.
    stale = await cp_repo.get_baseline_asset(session, first_upload["baseline_asset_id"])
    assert stale is not None
    assert stale.parse_status == BaselineParseStatus.PARSING
    assert stale.parse_report is None
    head = await _head_asset(session, request_id)
    assert head is not None
    assert head.baseline_asset_id == second_upload["baseline_asset_id"]
    assert head.parse_status == BaselineParseStatus.UPLOADED


async def test_terminal_asset_delivery_is_superseded(session, fake_object_store) -> None:
    """A duplicate job for an already-parsed asset records nothing a second time."""
    request_id = await _seeded_request(session)
    await _upload(session, request_id)
    first = await _admit(session, request_id)
    await _run_job(session, first["job_id"])
    await session.commit()

    # A second admission for the same (now PASSED) head, delivered after the first landed.
    second = await _admit(session, request_id)
    await session.commit()
    asset = await _head_asset(session, request_id)
    assert asset is not None and asset.parse_status == BaselineParseStatus.PARSING

    # Simulate the head having already reached a terminal status before this delivery.
    asset.parse_status = BaselineParseStatus.PASSED
    await session.commit()
    result = await _run_job(session, second["job_id"])
    await session.commit()

    assert result["superseded"] is True
    job = await session.get(Job, second["job_id"])
    assert job is not None and job.status == JobStatus.SUPERSEDED


async def test_dispatcher_rejects_an_unknown_kind(session, fake_object_store) -> None:
    request_id = await _seeded_request(session)
    await _upload(session, request_id)
    admitted = await _admit(session, request_id)
    job = await session.get(Job, admitted["job_id"])
    assert job is not None
    job.payload = {**(job.payload or {}), "kind": "not_a_kind"}
    await session.commit()

    with pytest.raises(ValueError, match="Unsupported create-package job kind"):
        await _run_job(session, admitted["job_id"])
