"""F-01b candidate-generation + validation durable workers — real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers what Finding F-01 demands for the two remaining long steps of the
Create-Package flow: the POST is an ADMISSION that returns a durable QUEUED job and
never a fabricated result; the worker body drives queued -> running ->
succeeded/failed and writes the durable evidence (candidate pins / immutable
validation run) plus the state advance and the outbox; a compute failure is a durable
terminal state (candidate_failed / a FAILED run + revision_required), never a silent
success; a redelivered message replays the durable outcome; a delivery whose request
already advanced is SUPERSEDED; and the admission-time gates (Pre-Check PC-13, the
draft gate, the OCC token) still fail fast with their typed errors.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import create_package as cp_cmd
from entropia.application.jobs import create_package as cp_jobs
from entropia.application.queries import create_package as cp_query
from entropia.domain.create_package.enums import (
    CreatePackageState,
    CreationMode,
    SourceLanguage,
    ValidationRunStatus,
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
from entropia.infrastructure.postgres.models import (
    Job,
    OutboxEvent,
    PackageValidationRun,
    Principal,
)
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.shared.errors import CandidateNotReady, PrecheckBlocked, RequestVersionConflict

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_RSI_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
_RSI_DEP = {"key": "ta.rsi", "signature": _RSI_SIG}
_INDICATOR_OUTPUT = {"kind": "directional_signal"}


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


async def _create_indicator_request(session, *, family_id: str, deps: list[dict]) -> dict:
    return await cp_cmd.create_package_request(
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
        declared_dependencies=deps,
        equivalence_claim=False,
    )


async def _run_job(session, job_id: str) -> dict:
    """Drive one durable delivery through the dispatcher, exactly as the actor does."""
    return await cp_jobs.run_create_package_job(session, job_id)


async def _seeded_request(session, *, deps: list[dict] | None = None) -> str:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_indicator_request(
        session, family_id=family_id, deps=deps if deps is not None else [_RSI_DEP]
    )
    await session.commit()
    queued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    await _run_job(session, queued["job_id"])
    await session.commit()
    return str(created["request_id"])


async def _drive_to_candidate_ready(session, request_id: str) -> dict:
    admitted = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    await session.commit()
    result = await _run_job(session, admitted["job_id"])
    await session.commit()
    return result


async def _drive_to_draft(session, request_id: str) -> dict:
    candidate = await _drive_to_candidate_ready(session, request_id)
    draft = await cp_cmd.create_draft_from_candidate(
        session,
        OWNER,
        request_id=request_id,
        expected_candidate_hash=candidate["candidate_hash"],
    )
    await session.commit()
    return draft


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------


async def test_candidate_admission_returns_queued_durable_job(session) -> None:
    request_id = await _seeded_request(session)

    admitted = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    await session.commit()

    # The admission never fabricates a candidate: no hash exists yet.
    assert admitted["state"] == str(CreatePackageState.CANDIDATE_GENERATING)
    assert admitted["candidate_hash"] == ""
    job = await session.get(Job, admitted["job_id"])
    assert job is not None
    assert job.status == JobStatus.QUEUED
    assert job.queue == "default"
    assert job.payload == {"kind": "candidate_generation", "request_id": request_id}
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["state"] == str(CreatePackageState.CANDIDATE_GENERATING)
    assert projection["candidate_hash"] is None
    # OCC: the admission bumped the request_version, so a stale token now conflicts.
    with pytest.raises(RequestVersionConflict):
        await cp_cmd.submit_candidate_generation(
            session,
            OWNER,
            request_id=request_id,
            expected_request_version=admitted["request_version"] - 1,
        )


async def test_candidate_worker_lifecycle_ready(session) -> None:
    request_id = await _seeded_request(session)
    admitted = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    await session.commit()
    outbox_before = await _count(session, OutboxEvent)

    result = await _run_job(session, admitted["job_id"])
    await session.commit()

    assert result["state"] == str(CreatePackageState.CANDIDATE_READY)
    assert result["candidate_hash"].startswith("sha256:")
    job = await session.get(Job, admitted["job_id"])
    assert job is not None
    assert job.status == JobStatus.SUCCEEDED
    assert job.started_at is not None and job.finished_at is not None
    assert job.result_ref == result
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["candidate_hash"] == result["candidate_hash"]
    # The completion emits the request-scoped resource.changed the C.D.P surface
    # refetches on (the exact event the sync path emitted) — never job.updated.
    assert await _count(session, OutboxEvent) == outbox_before + 1
    outbox = (
        (await session.execute(select(OutboxEvent).order_by(OutboxEvent.created_at.desc())))
        .scalars()
        .first()
    )
    assert outbox is not None
    assert outbox.event_type == "resource.changed"
    assert outbox.resource_type == "package_request"
    assert outbox.resource_id == request_id
    assert outbox.payload["action"] == "candidate_generation_completed"


async def test_candidate_generation_is_deterministic(session) -> None:
    """The worker's candidate matches the in-transaction revision loop's byte for byte."""
    request_id = await _seeded_request(session)
    first = await _drive_to_candidate_ready(session, request_id)

    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None
    regenerated = await cp_jobs.generate_and_store_candidate(session, detail)
    await session.commit()

    assert regenerated.candidate_hash == first["candidate_hash"]


async def test_candidate_worker_failure_is_durable_failed_state(session, monkeypatch) -> None:
    request_id = await _seeded_request(session)
    admitted = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    await session.commit()

    def _boom(**_kwargs):
        raise RuntimeError("generator exploded")

    monkeypatch.setattr(cp_jobs, "generate_candidate", _boom)
    result = await _run_job(session, admitted["job_id"])
    await session.commit()

    # A worker crash is a DURABLE failed state, never a silent success.
    assert result["state"] == str(CreatePackageState.CANDIDATE_FAILED)
    assert result["candidate_hash"] == ""
    assert result["error"]["code"] == "CANDIDATE_GENERATION_WORKER_FAILED"
    job = await session.get(Job, admitted["job_id"])
    assert job is not None
    assert job.status == JobStatus.FAILED_FINAL
    assert job.error is not None
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["state"] == str(CreatePackageState.CANDIDATE_FAILED)
    assert projection["candidate_hash"] is None


async def test_candidate_worker_is_redelivery_idempotent(session) -> None:
    request_id = await _seeded_request(session)
    admitted = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    await session.commit()
    first = await _run_job(session, admitted["job_id"])
    await session.commit()

    replay = await _run_job(session, admitted["job_id"])
    await session.commit()

    assert replay == first
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["candidate_hash"] == first["candidate_hash"]


async def test_candidate_stale_delivery_is_superseded(session) -> None:
    request_id = await _seeded_request(session)
    admitted = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    await session.commit()
    # A concurrent delivery won the race and already left candidate_generating.
    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None
    detail.state = CreatePackageState.CANDIDATE_READY
    await session.commit()

    result = await _run_job(session, admitted["job_id"])
    await session.commit()

    assert result["superseded"] is True
    job = await session.get(Job, admitted["job_id"])
    assert job is not None and job.status == JobStatus.SUPERSEDED
    # Recording nothing is the point: the winner's candidate is untouched.
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["state"] == str(CreatePackageState.CANDIDATE_READY)


async def test_candidate_admission_still_enforces_precheck_gate(session) -> None:
    """PC-13 fails fast at admission — a blocked scan never reaches the worker."""
    request_id = await _seeded_request(
        session, deps=[_RSI_DEP, {"key": "ta.unknown", "signature": _RSI_SIG}]
    )
    jobs_before = await _count(session, Job)

    with pytest.raises(PrecheckBlocked):
        await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    await session.rollback()

    assert await _count(session, Job) == jobs_before


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def test_validation_admission_returns_queued_run_and_job(session) -> None:
    request_id = await _seeded_request(session)
    await _drive_to_draft(session, request_id)

    admitted = await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()

    assert admitted["state"] == str(CreatePackageState.VALIDATION_RUNNING)
    assert admitted["status"] == str(ValidationRunStatus.QUEUED)
    assert admitted["checks"] == []
    run = await session.get(PackageValidationRun, admitted["validation_run_id"])
    assert run is not None
    assert run.status == ValidationRunStatus.QUEUED
    assert run.completed_at is None
    job = await session.get(Job, admitted["job_id"])
    assert job is not None
    assert job.status == JobStatus.QUEUED
    assert job.queue == "default"
    assert job.payload == {
        "kind": "validation",
        "request_id": request_id,
        "validation_run_id": admitted["validation_run_id"],
    }
    assert run.job_id == job.job_id
    # The queued run is not evidence: it can never certify the draft for approval.
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["validation_fresh"] is False


async def test_validation_worker_lifecycle_passed(session) -> None:
    request_id = await _seeded_request(session)
    draft = await _drive_to_draft(session, request_id)
    admitted = await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()
    outbox_before = await _count(session, OutboxEvent)

    result = await _run_job(session, admitted["job_id"])
    await session.commit()

    assert result["status"] == str(ValidationRunStatus.PASSED)
    assert result["state"] == str(CreatePackageState.ELIGIBLE_FOR_APPROVAL)
    assert len(result["checks"]) >= 7
    run = await session.get(PackageValidationRun, admitted["validation_run_id"])
    assert run is not None
    assert run.status == ValidationRunStatus.PASSED
    assert run.completed_at is not None
    assert run.attempt_no == 1
    # The worker certifies the draft revision, else can_use could never be true.
    revision = await pkg_repo.get_revision(session, draft["draft_revision_id"])
    assert revision is not None
    assert revision.validation_state == PackageValidationState.PASSED
    job = await session.get(Job, admitted["job_id"])
    assert job is not None
    assert job.status == JobStatus.SUCCEEDED
    assert job.result_ref == result
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["validation_fresh"] is True
    assert await _count(session, OutboxEvent) == outbox_before + 1
    outbox = (
        (await session.execute(select(OutboxEvent).order_by(OutboxEvent.created_at.desc())))
        .scalars()
        .first()
    )
    assert outbox is not None
    assert outbox.event_type == "resource.changed"
    assert outbox.resource_type == "package"
    assert outbox.payload["action"] == "validation_run_completed"


async def test_validation_worker_failure_is_durable_failed_run(session, monkeypatch) -> None:
    request_id = await _seeded_request(session)
    draft = await _drive_to_draft(session, request_id)
    admitted = await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()

    async def _boom(_session, _detail):
        raise RuntimeError("validator exploded")

    monkeypatch.setattr(cp_jobs, "run_package_validation", _boom)
    result = await _run_job(session, admitted["job_id"])
    await session.commit()

    # A crashed validator is NOT a pass: the run lands FAILED and the request is
    # routed to the real next step (Request Revision).
    assert result["status"] == str(ValidationRunStatus.FAILED)
    assert result["state"] == str(CreatePackageState.REVISION_REQUIRED)
    assert result["error"]["code"] == "VALIDATION_WORKER_FAILED"
    assert result["checks"][0]["status"] == "blocked"
    run = await session.get(PackageValidationRun, admitted["validation_run_id"])
    assert run is not None and run.status == ValidationRunStatus.FAILED
    revision = await pkg_repo.get_revision(session, draft["draft_revision_id"])
    assert revision is not None
    assert revision.validation_state == PackageValidationState.FAILED
    job = await session.get(Job, admitted["job_id"])
    assert job is not None and job.status == JobStatus.FAILED_FINAL
    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["validation_fresh"] is False


async def test_validation_worker_is_redelivery_idempotent(session) -> None:
    request_id = await _seeded_request(session)
    await _drive_to_draft(session, request_id)
    admitted = await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()
    first = await _run_job(session, admitted["job_id"])
    await session.commit()
    runs_after_first = await _count(session, PackageValidationRun)

    replay = await _run_job(session, admitted["job_id"])
    await session.commit()

    assert replay == first
    # A redelivery never forges a second attempt.
    assert await _count(session, PackageValidationRun) == runs_after_first


async def test_validation_stale_delivery_is_superseded(session) -> None:
    request_id = await _seeded_request(session)
    await _drive_to_draft(session, request_id)
    admitted = await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()
    # The request leaves validation_running by another route before the delivery lands.
    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None
    detail.state = CreatePackageState.ELIGIBLE_FOR_APPROVAL
    await session.commit()

    result = await _run_job(session, admitted["job_id"])
    await session.commit()

    assert result["superseded"] is True
    job = await session.get(Job, admitted["job_id"])
    assert job is not None and job.status == JobStatus.SUPERSEDED
    run = await session.get(PackageValidationRun, admitted["validation_run_id"])
    assert run is not None
    # Nothing was recorded: the queued run keeps its admission state.
    assert run.status == ValidationRunStatus.QUEUED


async def test_validation_admission_requires_a_draft(session) -> None:
    request_id = await _seeded_request(session)
    jobs_before = await _count(session, Job)

    with pytest.raises(CandidateNotReady):
        await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.rollback()

    assert await _count(session, Job) == jobs_before
    assert await _count(session, PackageValidationRun) == 0
