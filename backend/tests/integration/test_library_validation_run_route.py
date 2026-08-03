"""G-04 at the HTTP edge: POST /api/v1/library/{entity_id}/validation-runs.

``tests/integration/test_library_validation_run.py`` pins this behaviour at the
COMMAND level. That proves the wrapper, not the route: a dropped ``Header(...)``
parameter, a body field that never reaches the command, or a response field the
schema does not publish would all pass there and still leave the Package Library
UI unable to bind to anything. These tests close that gap end to end.

What is pinned here:

* the 201 envelope carries BOTH planes' identifiers (``request_id`` /
  ``validation_run_id`` / ``attempt_no`` / ``job_id`` beside the package ones) and
  is PUBLISHED in ``docs/openapi.json`` — a bare ``dict`` return would keep the
  drift guard green while hiding the contract (the O-30 trap);
* ``expected_head_revision_id`` actually reaches the command: a stale token is a
  409 ``PACKAGE_REVISION_CONFLICT``, not a silently accepted run;
* a run already in flight is a 409 ``VALIDATION_ALREADY_RUNNING`` whose ``details``
  name the existing run, so the UI can link to it instead of offering a duplicate;
* a package with no originating create-package request is a 422
  ``VALIDATION_PIPELINE_UNAVAILABLE`` — loud, never a silent no-op;
* a non-owner is a 403 at the route, so a hidden button is never the only guard;
* ``Idempotency-Key`` is forwarded — proven where it is observable. While a run is
  in flight the wrapper's guard precedes ``run_idempotent``, so a same-key retry is
  the 409, NOT a replayed 201; once the run has finished the same key replays the
  original admission verbatim. Both halves are pinned, because the first is the
  contract the UI's retry path has to be built against;
* the durable worker carries the queued run to ``passed`` and the Library read
  model the UI polls reflects it — one pipeline, no second certification path.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from entropia.application.jobs import create_package as cp_jobs
from entropia.application.queries import library as library_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.apps.api.routes import library as library_routes
from entropia.domain.create_package.enums import CreatePackageState, ValidationRunStatus
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import PackageValidationRun
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from tests.integration.test_library_validation_run import _library_head
from tests.integration.test_validation_evidence import OWNER

pytestmark = pytest.mark.integration

_PATH = "/api/v1/library/{entity_id}/validation-runs"

# A signed-in principal who owns nothing in this fixture — the 403 probe.
STRANGER = Actor(principal_id="user_stranger", principal_type=PrincipalType.HUMAN, role=Role.USER)


def _override(app, session, actor: Actor = OWNER) -> Iterator[None]:
    """Bind the route to THIS test's session, as the sibling route tests do.

    ``request.state.db_session`` stays unset, so the transaction-boundary middleware
    neither commits nor rolls back — the test owns the commits, one per request."""
    app.dependency_overrides[request_context] = lambda: RequestContext(session=session, actor=actor)
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


@pytest.fixture(autouse=True)
def dispatched(monkeypatch) -> list[str]:
    """Record the broker hand-off instead of performing it.

    The route now dispatches the durable job for real, and the Backend CI job runs
    without a broker — an unstubbed dispatch turns every test here into a Redis
    ConnectionError. Stubbing it is the established convention for a dispatching route
    (see ``tests/contract/test_market_data_contract.py``); the real hand-off is covered
    end to end by ``e2e/specs/20-library-request-validation.spec.ts`` against the Compose
    stack. Recording rather than discarding gives the dispatch test its assertion.
    """
    calls: list[str] = []
    monkeypatch.setattr(library_routes, "dispatch_create_package_job", calls.append)
    return calls


def _client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _count_runs(session) -> int:
    return int(
        (await session.execute(select(func.count()).select_from(PackageValidationRun))).scalar_one()
    )


async def test_the_201_envelope_names_both_planes_for_one_run(app, session) -> None:
    entity_id, revision_id = await _library_head(session)
    runs_before = await _count_runs(session)

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            resp = await client.post(
                _PATH.format(entity_id=entity_id),
                json={"revision_id": revision_id, "expected_head_revision_id": revision_id},
                headers={"Idempotency-Key": "idem-lib-val-1"},
            )
    finally:
        next(gen, None)
    await session.commit()

    assert resp.status_code == 201
    body: dict[str, Any] = resp.json()

    # The exact published field set — the frontend binds to these eight names.
    assert set(body) == {
        "entity_id",
        "revision_id",
        "request_id",
        "validation_run_id",
        "attempt_no",
        "status",
        "state",
        "job_id",
    }
    # Package-plane identity: answered in the terms the caller addressed.
    assert body["entity_id"] == entity_id
    assert body["revision_id"] == revision_id
    # CP-plane identity: the evidence, the attempt and the durable job.
    assert body["request_id"]
    assert body["validation_run_id"]
    assert body["job_id"]
    assert body["attempt_no"] >= 1
    # status and state answer DIFFERENT questions and are never collapsed.
    assert body["status"] == str(ValidationRunStatus.QUEUED)
    assert body["state"] == str(CreatePackageState.VALIDATION_RUNNING)

    # Exactly ONE new immutable evidence row — the CP plane's, not a Library copy.
    assert await _count_runs(session) == runs_before + 1
    run = await session.get(PackageValidationRun, body["validation_run_id"])
    assert run is not None
    assert run.package_root_id == entity_id
    assert run.request_entity_id == body["request_id"]


async def test_a_same_key_retry_while_in_flight_is_the_409_not_a_replay(app, session) -> None:
    """VERIFIED BOUNDARY, pinned so the UI is built against the real contract.

    ``Idempotency-Key`` does NOT make a mid-flight retry replay the 201. The Library
    wrapper's in-flight guard (``package_lifecycle.py`` ``request.state ==
    VALIDATION_RUNNING``) is evaluated BEFORE it ever calls the CP command, and
    ``run_idempotent`` lives inside that command (``create_package.py`` ``_op``). So the
    guard wins and the caller gets 409 ``VALIDATION_ALREADY_RUNNING`` — with the running
    run named in ``details``.

    This is safe, not a duplicate-write bug: the guard raises before any write, so the
    evidence-row count is unchanged. It IS a frontend requirement, though — a retried
    submit must land on the already-running recovery path, never on a "queued" render.
    """
    entity_id, revision_id = await _library_head(session)
    runs_before = await _count_runs(session)
    payload = {"revision_id": revision_id, "expected_head_revision_id": revision_id}
    headers = {"Idempotency-Key": "idem-lib-val-replay"}

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            first = await client.post(
                _PATH.format(entity_id=entity_id), json=payload, headers=headers
            )
            await session.commit()
            second = await client.post(
                _PATH.format(entity_id=entity_id), json=payload, headers=headers
            )
    finally:
        next(gen, None)
    await session.rollback()

    assert first.status_code == 201
    assert second.status_code == 409
    error = second.json()["error"]
    assert error["code"] == "VALIDATION_ALREADY_RUNNING"
    assert error["details"][0]["validation_run_id"] == first.json()["validation_run_id"]
    # The guard raised before any write — exactly one evidence row, not two.
    assert await _count_runs(session) == runs_before + 1


async def test_the_idempotency_key_reaches_the_command_once_the_run_is_done(app, session) -> None:
    """The header is genuinely forwarded — proven where the in-flight guard is silent.

    Once the durable worker has finished, the request has left ``validation_running``,
    so the wrapper's guard passes and the retry reaches ``run_idempotent``. The SAME key
    then replays the original admission verbatim instead of appending a second attempt.
    A dropped ``Header(...)`` parameter would surface here as a fresh run.
    """
    entity_id, revision_id = await _library_head(session)
    runs_before = await _count_runs(session)
    payload = {"revision_id": revision_id, "expected_head_revision_id": revision_id}
    headers = {"Idempotency-Key": "idem-lib-val-after-done"}

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            first = await client.post(
                _PATH.format(entity_id=entity_id), json=payload, headers=headers
            )
            await session.commit()
            assert first.status_code == 201
            # Drive the durable job to its terminal verdict, as the worker does.
            await cp_jobs.run_create_package_job(session, first.json()["job_id"])
            await session.commit()

            second = await client.post(
                _PATH.format(entity_id=entity_id), json=payload, headers=headers
            )
            await session.commit()
    finally:
        next(gen, None)

    assert second.status_code == 201
    # Same run, same attempt, same durable job — the key reached run_idempotent.
    assert second.json()["validation_run_id"] == first.json()["validation_run_id"]
    assert second.json()["attempt_no"] == first.json()["attempt_no"]
    assert second.json()["job_id"] == first.json()["job_id"]
    # No second certification attempt was appended.
    assert await _count_runs(session) == runs_before + 1


async def test_a_stale_expected_head_is_a_409_at_the_route(app, session) -> None:
    """Proves the BODY-form OCC token actually reaches the command."""
    entity_id, revision_id = await _library_head(session)
    runs_before = await _count_runs(session)

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            resp = await client.post(
                _PATH.format(entity_id=entity_id),
                json={
                    "revision_id": revision_id,
                    "expected_head_revision_id": "pkgrev_stale",
                },
                headers={"Idempotency-Key": "idem-lib-val-stale"},
            )
    finally:
        next(gen, None)
    await session.rollback()

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PACKAGE_REVISION_CONFLICT"
    assert await _count_runs(session) == runs_before


async def test_a_run_already_in_flight_is_a_409_that_names_the_existing_run(app, session) -> None:
    """The 409 must be actionable: the UI links to the running run, not a duplicate."""
    entity_id, revision_id = await _library_head(session)
    payload = {"revision_id": revision_id, "expected_head_revision_id": revision_id}

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            first = await client.post(
                _PATH.format(entity_id=entity_id),
                json=payload,
                headers={"Idempotency-Key": "idem-lib-val-a"},
            )
            await session.commit()
            runs_after_first = await _count_runs(session)
            # A DIFFERENT key, so this is a genuine second request, not a replay.
            second = await client.post(
                _PATH.format(entity_id=entity_id),
                json=payload,
                headers={"Idempotency-Key": "idem-lib-val-b"},
            )
    finally:
        next(gen, None)
    await session.rollback()

    assert second.status_code == 409
    error = second.json()["error"]
    assert error["code"] == "VALIDATION_ALREADY_RUNNING"
    assert error["details"][0]["validation_run_id"] == first.json()["validation_run_id"]
    assert error["details"][0]["request_id"] == first.json()["request_id"]
    # Retrying the same conflict would give the same answer, so it is not retryable.
    assert error["retryable"] is False
    assert await _count_runs(session) == runs_after_first


async def test_a_package_with_no_originating_request_is_a_422(app, session) -> None:
    """A Derived / seeded package has no draft to certify — say so, never no-op."""
    entity_id, revision_id = await _library_head(session)
    request = await cp_repo.get_request_for_package_root(session, entity_id)
    assert request is not None
    # Sever the link the way a Derived package is born: no originating request.
    request.package_root_id = None
    await session.flush()

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            resp = await client.post(
                _PATH.format(entity_id=entity_id),
                json={"revision_id": revision_id, "expected_head_revision_id": revision_id},
                headers={"Idempotency-Key": "idem-lib-val-orphan"},
            )
    finally:
        next(gen, None)
    await session.rollback()

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_PIPELINE_UNAVAILABLE"


async def test_a_non_owner_is_refused_at_the_route(app, session) -> None:
    """A hidden button is never the only guard — the server re-validates ownership."""
    entity_id, revision_id = await _library_head(session)
    runs_before = await _count_runs(session)

    gen = _override(app, session, actor=STRANGER)
    next(gen)
    try:
        async with _client(app) as client:
            resp = await client.post(
                _PATH.format(entity_id=entity_id),
                json={"revision_id": revision_id, "expected_head_revision_id": revision_id},
                headers={"Idempotency-Key": "idem-lib-val-stranger"},
            )
    finally:
        next(gen, None)
    await session.rollback()

    assert resp.status_code == 403
    assert await _count_runs(session) == runs_before


async def test_the_durable_worker_carries_the_queued_run_to_passed(app, session) -> None:
    """One pipeline: the Library admission is finished by the SAME CP worker, and
    the Library read model the UI polls reflects the terminal verdict."""
    entity_id, revision_id = await _library_head(session)

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            resp = await client.post(
                _PATH.format(entity_id=entity_id),
                json={"revision_id": revision_id, "expected_head_revision_id": revision_id},
                headers={"Idempotency-Key": "idem-lib-val-worker"},
            )
    finally:
        next(gen, None)
    await session.commit()
    assert resp.status_code == 201
    body = resp.json()

    finished = await cp_jobs.run_create_package_job(session, body["job_id"])
    await session.commit()
    assert finished["status"] == str(ValidationRunStatus.PASSED)

    run = await session.get(PackageValidationRun, body["validation_run_id"])
    assert run is not None
    assert str(run.status) == str(ValidationRunStatus.PASSED)

    # The projection the Library UI re-reads after the run completes.
    detail = await library_query.get_package_detail(session, OWNER, entity_id=entity_id)
    assert detail["entity_id"] == entity_id


def test_the_queued_envelope_is_published_in_the_openapi_schema(app) -> None:
    """A bare ``dict[str, Any]`` return keeps the drift guard green while leaving the
    contract invisible — the exact trap O-30 closed for the purge 202."""
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/library/{entity_id}/validation-runs"]["post"]
    ref = operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    model = schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]

    assert set(model["properties"]) == {
        "entity_id",
        "revision_id",
        "request_id",
        "validation_run_id",
        "attempt_no",
        "status",
        "state",
        "job_id",
    }
    # Every field is required: a partially-populated envelope would let the UI
    # render a queued run it cannot then follow to its durable job.
    assert set(model["required"]) == set(model["properties"])


async def test_the_route_hands_the_durable_job_to_the_broker(app, session, dispatched) -> None:
    """The admission writes the jobs row; DISPATCH is a separate step.

    Every Create-Package admission route calls ``dispatch_create_package_job`` after the
    command returns. The Library route did not, so a Library-started run wrote its QUEUED
    jobs row and then sat there until the INF-03 scheduler sweep re-sent it. Nothing
    caught it: the API contract is byte-identical either way, and the command-level tests
    (and the worker test above) invoke ``run_create_package_job`` directly, so they never
    exercise the broker hand-off at all. Only a real browser journey did.

    This asserts the hand-off itself — the exact job id the caller was handed.
    """
    entity_id, revision_id = await _library_head(session)

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            resp = await client.post(
                _PATH.format(entity_id=entity_id),
                json={"revision_id": revision_id, "expected_head_revision_id": revision_id},
                headers={"Idempotency-Key": "idem-lib-val-dispatch"},
            )
    finally:
        next(gen, None)
    await session.commit()

    assert resp.status_code == 201
    assert dispatched == [resp.json()["job_id"]]
