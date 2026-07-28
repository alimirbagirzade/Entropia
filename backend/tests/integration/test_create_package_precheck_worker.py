"""F-01a Pre-Check durable worker — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers the async plane Finding F-01 demands: admission returns ``queued`` with a
DURABLE QUEUED job (browser close never cancels it); the worker body drives the
lifecycle queued -> running -> succeeded (PASSED / BLOCKED / NOT_APPLICABLE) and
records the immutable scan + state advance + outbox; a compute failure is a durable
terminal FAILED state (never a silent success); a redelivered message replays the
durable outcome (at-least-once); a request that advanced past Pre-Check supersedes
the stale delivery; a stale OCC token is rejected at admission.

Also covers the doc 07 §12 fail-closed error classes, each of which must land on a
NEGATIVE result rather than a silently green one: SOURCE_LANGUAGE_MISMATCH (PC-10),
REQUIRES_CLARIFICATION, PARSE_UNSUPPORTED and RESOLVER_NOT_ACTIVE.

Acceptance (doc 07 §16) by behaviour:
- PC-04  passed scan pins exact resolver revision refs -> the PASSED lifecycle case
- PC-05  missing resolver -> BLOCKED, no candidate job queued
- PC-07  RESOLVER_NOT_ACTIVE / signature mismatch is BLOCKED, never passed
- PC-09  registry revision moved under a Passed scan -> PRECHECK_STALE on recheck
- PC-11  duplicate admission / same idempotency key -> one scan, replayed outcome
- PC-12  source edited while the scan runs -> the superseded stale delivery case
  (the completed old scan never overwrites the newer context)
- PC-17  browser close / refresh does not cancel the DURABLE queued job
- PC-21  no TA dependency found -> PASSED (NOT_APPLICABLE/empty-call lifecycle)
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import create_package as cp_cmd
from entropia.application.jobs import create_package as cp_jobs
from entropia.domain.create_package.enums import (
    CreatePackageState,
    CreationMode,
    PrecheckScanStatus,
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
from entropia.infrastructure.postgres.models import (
    DependencyScan,
    Job,
    OutboxEvent,
    Principal,
)
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.shared.errors import PrecheckBlocked, RequestVersionConflict

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


async def _seed_python_resolver(
    session,
    *,
    key: str = "ta.rsi",
    trust_state: ResolverTrustState = ResolverTrustState.TRUSTED_ACTIVE,
) -> str:
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
        trust_state=trust_state,
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


async def test_admission_returns_queued_durable_job(session) -> None:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_indicator_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()

    queued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()

    # The admission never fabricates a result: it is CHECKING with a durable QUEUED job.
    assert queued["status"] == str(PrecheckScanStatus.CHECKING)
    assert queued["state"] == str(CreatePackageState.REQUESTED)
    assert queued["scan_id"] == ""
    job = await session.get(Job, queued["job_id"])
    assert job is not None
    assert job.status == JobStatus.QUEUED
    assert job.queue == "default"
    assert job.payload == {"kind": "precheck", "request_id": created["request_id"]}
    # No scan exists yet — the UI cannot show success before the worker finishes.
    assert await _count(session, DependencyScan) == 0
    # OCC: admission bumped the request_version, so a stale token now conflicts.
    with pytest.raises(RequestVersionConflict):
        await cp_cmd.run_precheck(
            session,
            OWNER,
            request_id=created["request_id"],
            expected_request_version=created["request_version"],
        )


async def test_worker_lifecycle_passed(session) -> None:
    await _seed_principals(session)
    resolver_rev = await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_indicator_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()

    queued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    outbox_before = await _count(session, OutboxEvent)

    result = await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()

    assert result["status"] == str(PrecheckScanStatus.PASSED)
    assert result["state"] == str(CreatePackageState.PRECHECK_PASSED)
    assert result["resolved"] == 1
    assert result["missing"] == []
    scan = await session.get(DependencyScan, result["scan_id"])
    assert scan is not None
    assert scan.attempt_no == 1
    assert scan.resolved_refs[0]["embedded_revision_id"] == resolver_rev
    assert scan.job_id == queued["job_id"]
    job = await session.get(Job, queued["job_id"])
    assert job is not None
    assert job.status == JobStatus.SUCCEEDED
    assert job.started_at is not None and job.finished_at is not None
    assert job.result_ref == result
    # Completion emits the request-scoped resource.changed outbox (the SSE catch-all
    # the Pre-Check overlay refetches on) — never a job-scoped event.
    assert await _count(session, OutboxEvent) == outbox_before + 1
    outbox = (
        (await session.execute(select(OutboxEvent).order_by(OutboxEvent.created_at.desc())))
        .scalars()
        .first()
    )
    assert outbox is not None
    assert outbox.event_type == "resource.changed"
    assert outbox.resource_type == "package_request"
    assert outbox.resource_id == created["request_id"]


async def test_worker_lifecycle_blocked(session) -> None:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_indicator_request(
        session,
        family_id=family_id,
        deps=[_RSI_DEP, {"key": "ta.unknown", "signature": _RSI_SIG}],
    )
    await session.commit()

    queued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    result = await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()

    assert result["status"] == str(PrecheckScanStatus.BLOCKED)
    assert result["state"] == str(CreatePackageState.PRECHECK_BLOCKED)
    assert result["missing"][0]["call"] == "ta.unknown"
    job = await session.get(Job, queued["job_id"])
    assert job is not None and job.status == JobStatus.SUCCEEDED


async def test_worker_description_not_applicable(session) -> None:
    await _seed_principals(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await cp_cmd.create_package_request(
        session,
        OWNER,
        package_type="indicator",
        creation_mode=CreationMode.GENERATE_FROM_DESCRIPTION,
        source_language=None,
        other_language_label=None,
        target_runtime=RuntimeAdapter.PYTHON,
        request_body="A momentum oscillator over closing prices.",
        output_contract=_INDICATOR_OUTPUT,
        rationale_family_id=family_id,
    )
    await session.commit()

    queued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    result = await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()

    assert result["status"] == str(PrecheckScanStatus.NOT_APPLICABLE)
    assert result["state"] == str(CreatePackageState.PRECHECK_NOT_APPLICABLE)


async def test_worker_failure_is_durable_failed_state(session, monkeypatch) -> None:
    """Finding F-01: a worker failure must land as a durable FAILED state the UI can
    read — never a silent success, never an eternally-running job."""
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_indicator_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()
    queued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()

    async def _boom(_session, _detail):
        raise RuntimeError("registry unreachable")

    monkeypatch.setattr(cp_jobs, "compute_precheck", _boom)
    result = await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()

    assert result["status"] == str(PrecheckScanStatus.FAILED)
    assert result["state"] == str(CreatePackageState.PRECHECK_FAILED)
    job = await session.get(Job, queued["job_id"])
    assert job is not None
    assert job.status == JobStatus.FAILED_FINAL
    assert job.error == {"code": "PRECHECK_WORKER_FAILED", "message": "registry unreachable"}
    scan = await session.get(DependencyScan, result["scan_id"])
    assert scan is not None
    assert scan.status == PrecheckScanStatus.FAILED
    assert scan.error_detail == job.error

    # A user can re-run Pre-Check after a failure; the real compute now succeeds.
    monkeypatch.undo()
    requeued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    retry = await cp_jobs.run_create_package_job(session, requeued["job_id"])
    await session.commit()
    assert retry["status"] == str(PrecheckScanStatus.PASSED)
    assert retry["state"] == str(CreatePackageState.PRECHECK_PASSED)


async def test_worker_is_redelivery_idempotent(session) -> None:
    """Dramatiq is at-least-once: a redelivered message for a job that already
    succeeded must replay the durable outcome and never append a duplicate scan."""
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_indicator_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()
    queued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()

    first = await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()
    second = await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()

    assert second == first
    assert await _count(session, DependencyScan) == 1


async def test_stale_delivery_is_superseded(session) -> None:
    """A Pre-Check delivery that arrives after the request advanced past the
    Pre-Check states records nothing (an illegal transition otherwise)."""
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_indicator_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()

    # First Pre-Check completes; a second is admitted but its delivery stalls.
    q1 = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    await cp_jobs.run_create_package_job(session, q1["job_id"])
    await session.commit()
    q2 = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()

    # The request advances past Pre-Check before the stale delivery lands. Admitting
    # candidate generation is enough — candidate_generating is already outside the
    # Pre-Check-recordable states (F-01b made the generation itself async too).
    sent = await cp_cmd.submit_candidate_generation(
        session, OWNER, request_id=created["request_id"]
    )
    await session.commit()
    assert sent["state"] == str(CreatePackageState.CANDIDATE_GENERATING)

    late = await cp_jobs.run_create_package_job(session, q2["job_id"])
    await session.commit()
    assert late["superseded"] is True
    job = await session.get(Job, q2["job_id"])
    assert job is not None and job.status == JobStatus.SUPERSEDED
    # Only the first scan exists; the stale delivery appended nothing.
    assert await _count(session, DependencyScan) == 1


# ---------------------------------------------------------------------------
# Fail-closed classes (doc 07 §12, §9.5; PC-10) — none of these may reach Passed
# ---------------------------------------------------------------------------


async def _create_code_request(
    session,
    *,
    family_id: str,
    body: str,
    language: SourceLanguage = SourceLanguage.PINESCRIPT,
    deps: list[dict] | None = None,
) -> dict:
    """A code request with a caller-supplied body + declared source language."""
    return await cp_cmd.create_package_request(
        session,
        OWNER,
        package_type="indicator",
        creation_mode=CreationMode.TRANSLATE_EXISTING_CODE,
        source_language=language,
        other_language_label=None,
        target_runtime=RuntimeAdapter.PYTHON,
        request_body=body,
        output_contract=_INDICATOR_OUTPUT,
        rationale_family_id=family_id,
        declared_dependencies=deps or [],
        equivalence_claim=False,
    )


async def _run_precheck(session, request_id: str) -> dict:
    queued = await cp_cmd.run_precheck(session, OWNER, request_id=request_id)
    await session.commit()
    result = await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()
    return result


async def test_pc10_language_mismatch_fails_and_starts_no_candidate(session) -> None:
    """PC-10: Source Language is PineScript but the content is Python. No candidate
    starts; the scan is FAILED with SOURCE_LANGUAGE_MISMATCH, never Passed.

    Without the content gate this body scans to ZERO ``ta.*`` calls, reconciles
    cleanly against an empty declared list and reaches PASSED — a green Pre-Check on
    a source the production lexer never understood.
    """
    await _seed_principals(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_code_request(
        session,
        family_id=family_id,
        body="import pandas as pd\n\n\ndef rsi(series, length):\n    return series.mean()\n",
        language=SourceLanguage.PINESCRIPT,
    )
    await session.commit()

    result = await _run_precheck(session, created["request_id"])

    assert result["status"] == str(PrecheckScanStatus.FAILED)
    assert result["state"] == str(CreatePackageState.PRECHECK_FAILED)
    assert result["error"]["code"] == "SOURCE_LANGUAGE_MISMATCH"
    scan = await session.get(DependencyScan, result["scan_id"])
    assert scan is not None
    assert scan.status == PrecheckScanStatus.FAILED
    assert scan.unsupported_calls[0]["code"] == "SOURCE_LANGUAGE_MISMATCH"
    assert scan.unsupported_calls[0]["evidence"]["detected_language"] == "python"
    assert scan.detected_calls == []

    # The Send gate requires a PASSED scan, so no candidate can start on this result.
    with pytest.raises(PrecheckBlocked):
        await cp_cmd.submit_candidate_generation(session, OWNER, request_id=created["request_id"])


async def test_ambiguous_language_requires_clarification(session) -> None:
    """Competing evidence must ask, not guess (doc 07 §12 REQUIRES_CLARIFICATION)."""
    await _seed_principals(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_code_request(
        session,
        family_id=family_id,
        body=("//@version=5\nindicator('x')\nimport numpy as np\ndef helper():\n    return 1\n"),
    )
    await session.commit()

    result = await _run_precheck(session, created["request_id"])

    assert result["status"] == str(PrecheckScanStatus.FAILED)
    assert result["error"]["code"] == "REQUIRES_CLARIFICATION"
    scan = await session.get(DependencyScan, result["scan_id"])
    assert scan is not None
    assert scan.unsupported_calls[0]["evidence"]["detected_language"] is None


async def test_unparseable_source_fails_with_parse_unsupported(session) -> None:
    """doc 07 §12 PARSE_UNSUPPORTED: a body the lexer cannot account for is Failed /
    manual review — the pre-fix scanner silently skipped these characters and passed."""
    await _seed_principals(session)
    family_id = await _seed_family(session)
    await session.commit()
    # A mis-decoded binary export pasted into the form: the header survives, the body
    # arrives as replacement characters. (NUL bytes are not used here — Postgres
    # rejects them at the column, so they never reach a scan.)
    created = await _create_code_request(
        session,
        family_id=family_id,
        body="//@version=5\nx = ����������",
    )
    await session.commit()

    result = await _run_precheck(session, created["request_id"])

    assert result["status"] == str(PrecheckScanStatus.FAILED)
    assert result["state"] == str(CreatePackageState.PRECHECK_FAILED)
    assert result["error"]["code"] == "PARSE_UNSUPPORTED"
    scan = await session.get(DependencyScan, result["scan_id"])
    assert scan is not None
    assert scan.unsupported_calls[0]["evidence"]["reason"] == "unrecognized_token_ratio"
    assert scan.scanner_version == "source-lexer-2.0"
    # A determinate refusal is a completed job, not a crashed one: the retry path is a
    # fresh Pre-Check on a fixed source, not a redelivery of this job.
    job = await session.get(Job, result["job_id"])
    assert job is not None and job.status == JobStatus.SUCCEEDED


async def test_unterminated_string_cannot_hide_a_call(session) -> None:
    """The unclosed quote swallows the ``ta.rsi`` call below it. Reporting an empty
    call set here would Pass a source with a real, unresolved dependency."""
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_code_request(
        session,
        family_id=family_id,
        body='//@version=5\nindicator("x")\nlabel = "unclosed\nta.rsi(close, 14)',
    )
    await session.commit()

    result = await _run_precheck(session, created["request_id"])

    assert result["status"] == str(PrecheckScanStatus.FAILED)
    assert result["error"]["code"] == "PARSE_UNSUPPORTED"
    scan = await session.get(DependencyScan, result["scan_id"])
    assert scan is not None
    assert scan.unsupported_calls[0]["evidence"]["reason"] == "unterminated_string"


async def test_deprecated_resolver_blocks_with_resolver_not_active(session) -> None:
    """doc 07 §12 RESOLVER_NOT_ACTIVE: a resolver deprecated for new use blocks the
    scan with its own code — distinct from 'no resolver exists at all'."""
    await _seed_principals(session)
    await _seed_python_resolver(session, trust_state=ResolverTrustState.DEPRECATED)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_indicator_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()

    result = await _run_precheck(session, created["request_id"])

    assert result["status"] == str(PrecheckScanStatus.BLOCKED)
    assert result["state"] == str(CreatePackageState.PRECHECK_BLOCKED)
    assert result["missing"][0]["code"] == "RESOLVER_NOT_ACTIVE"
    assert result["missing"][0]["call"] == "ta.rsi"


async def test_clean_pinescript_still_passes(session) -> None:
    """Regression guard for the whole slice: the fail-closed gates must not turn a
    legitimate, declared, resolvable PineScript request into a refusal."""
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_indicator_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()

    result = await _run_precheck(session, created["request_id"])

    assert result["status"] == str(PrecheckScanStatus.PASSED)
    assert result["unsupported"] == []
    assert result["error"] is None


async def test_unknown_kind_raises(session) -> None:
    from entropia.infrastructure.queues.enqueue import enqueue_job

    job = enqueue_job(session, queue="default", payload={"kind": "mystery"})
    await session.flush()
    with pytest.raises(ValueError, match="Unsupported create-package job kind"):
        await cp_jobs.run_create_package_job(session, job.job_id)
