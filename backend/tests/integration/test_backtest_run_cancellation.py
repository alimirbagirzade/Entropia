"""O-06 — CancelBacktestRun: controlled cancellation, never a Result (doc 15 §8.4, §16).

Before this slice ``BacktestRunState.CANCELLED`` was defined, listed in
``RUN_RETRYABLE_STATES`` and named in the spec's state matrix — but nothing in the
codebase could ever produce it: there was no command, no endpoint and no worker
path. These tests pin the properties that fix has to keep true:

* a cancelled run reaches TERMINAL ``cancelled`` and materializes NO
  ``BacktestResult``, so it never appears in Results History (doc 15 §16, CR-03);
* cancellation is CONTROLLED, not a kill — a run the worker already owns is only
  flagged, and the worker stops it at one of its O-05 stage boundaries, writing the
  terminal state itself (doc 15 §8.4, §12);
* the cancellation audit event and the terminal reason are preserved, and partial
  diagnostics stay readable through the run status + the durable event stream;
* the policy gates hold: a foreign actor gets 403, an already-terminal run gets 409,
  and a stale ``expected_row_version`` gets the standard OCC conflict.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.queries import backtest_run as backtest_query
from entropia.application.queries import results_history as history_query
from entropia.domain.backtest.enums import BacktestRunState, RunEventType
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import JobStatus, PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    BacktestResult,
    BacktestRun,
    BacktestRunEvent,
    Job,
    OutboxEvent,
    Principal,
)
from entropia.shared.errors import (
    AccessDeniedError,
    RowVersionConflictError,
    RunNotCancellableError,
)
from tests.integration.test_backtest_persistence import (
    USER1,
    USER2,
    _e2e_bars,
    _ready_composition,
    _seed_principals,
)
from tests.integration.test_backtest_run_events import (
    _bars_killed_before_any_batch,
    _WorkerKilled,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)


async def _admit(session) -> dict[str, Any]:
    await _seed_principals(session)
    if await session.get(Principal, ADMIN.principal_id) is None:
        session.add(Principal(principal_id=ADMIN.principal_id, principal_type=PrincipalType.HUMAN))
        await session.flush()
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    return admit


async def _provisioning_run(session) -> dict[str, Any]:
    """Admit a run and leave it durably PROVISIONING, as a killed worker would.

    This is the state in which the worker OWNS the run, which is exactly the case a
    cancel may not terminate on its own."""
    admit = await _admit(session)
    with pytest.raises(_WorkerKilled):
        await run_backtest(session, admit["job_id"], stream_bars=_bars_killed_before_any_batch)
    await session.rollback()
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None and str(run.state) == BacktestRunState.PROVISIONING.value
    return admit


async def _events(session, run_id: str) -> list[BacktestRunEvent]:
    stmt = (
        select(BacktestRunEvent)
        .where(BacktestRunEvent.run_id == run_id)
        .order_by(BacktestRunEvent.sequence_no.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def _result_count(session) -> int:
    stmt = select(func.count()).select_from(BacktestResult)
    return int((await session.execute(stmt)).scalar_one())


async def _audit_kinds(session, run_id: str) -> list[str]:
    stmt = select(AuditEvent.event_kind).where(AuditEvent.target_entity_id == run_id)
    return [str(kind) for (kind,) in (await session.execute(stmt)).all()]


# --------------------------------------------------------------------------- #
# The QUEUED path — no worker owns the run, so the cancel IS terminal          #
# --------------------------------------------------------------------------- #


async def test_cancelling_a_queued_run_is_terminal_and_produces_no_result(session) -> None:
    admit = await _admit(session)

    out = await backtest_cmd.cancel_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.commit()

    assert out["state"] == BacktestRunState.CANCELLED.value
    assert out["cancellation"] == "cancelled"
    assert out["result_id"] is None
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None
    assert str(run.state) == BacktestRunState.CANCELLED.value
    assert run.result_id is None
    # doc 15 §16: the terminal reason is preserved, not merely logged.
    assert run.cancellation_reason is not None and "queued" in run.cancellation_reason
    assert run.cancel_requested_by_principal_id == USER1.principal_id
    assert run.cancel_requested_at is not None
    assert await _result_count(session) == 0

    # The terminal event closes the stream a watching client is replaying.
    events = await _events(session, admit["run_id"])
    assert [str(e.event_type) for e in events] == [RunEventType.RUN_CANCELLED.value]
    assert str(events[0].previous_state) == BacktestRunState.QUEUED.value
    assert events[0].detail["result_id"] is None

    # The durable job is finalized: nothing will ever execute it.
    job = await session.get(Job, admit["job_id"])
    assert job is not None and job.status == JobStatus.CANCELLED


async def test_worker_delivery_after_a_queued_cancel_runs_nothing(session) -> None:
    # The engine must never start for a cancelled run: the at-least-once terminal
    # guard is what makes the QUEUED-path cancel final even though the queue message
    # was already published at admission time.
    admit = await _admit(session)
    await backtest_cmd.cancel_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == BacktestRunState.CANCELLED.value
    assert out["result_id"] is None
    assert await _result_count(session) == 0
    # No further events were appended by the no-op delivery.
    assert len(await _events(session, admit["run_id"])) == 1


# --------------------------------------------------------------------------- #
# The in-flight path — controlled cancellation at an O-05 stage boundary       #
# --------------------------------------------------------------------------- #


async def test_cancelling_a_running_worker_records_intent_without_killing_it(session) -> None:
    # The whole point of "ani kill YOK": while the worker owns the run, the command
    # must NOT write a terminal state. It records the intent and says so.
    admit = await _provisioning_run(session)

    out = await backtest_cmd.cancel_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.commit()

    assert out["cancellation"] == "requested"
    assert out["state"] == BacktestRunState.PROVISIONING.value
    assert out["delivery_policy"] == "cancellation_safe_boundary"
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None
    # Still PROVISIONING — the run was flagged, not stopped.
    assert str(run.state) == BacktestRunState.PROVISIONING.value
    assert run.cancel_requested_at is not None
    assert run.cancellation_reason is None
    # No terminal event was invented for a run the worker has not finished.
    assert [str(e.event_type) for e in await _events(session, admit["run_id"])] == [
        RunEventType.RUN_STARTED.value
    ]


async def test_worker_honors_the_request_at_a_stage_boundary_and_writes_no_result(session) -> None:
    admit = await _provisioning_run(session)
    await backtest_cmd.cancel_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.commit()

    # The worker resumes (redelivery) with fully valid bars: left alone it would
    # succeed and materialize a Result. It must stop at its checkpoint instead.
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == BacktestRunState.CANCELLED.value
    assert out["result_id"] is None
    assert await _result_count(session) == 0
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None and str(run.state) == BacktestRunState.CANCELLED.value
    assert run.result_id is None
    assert run.cancellation_reason is not None
    assert "safe checkpoint" in run.cancellation_reason
    job = await session.get(Job, admit["job_id"])
    assert job is not None and job.status == JobStatus.CANCELLED

    # The redelivery re-attempts the incomplete run, so it appends its own
    # RUN_STARTED before the checkpoint fires (documented O-05 behaviour). What
    # matters is the tail: exactly one terminal event, and it is the cancellation.
    events = await _events(session, admit["run_id"])
    kinds = [str(e.event_type) for e in events]
    assert kinds[-1] == RunEventType.RUN_CANCELLED.value
    assert kinds.count(RunEventType.RUN_CANCELLED.value) == 1
    assert RunEventType.RUN_SUCCEEDED.value not in kinds
    assert RunEventType.RUN_FAILED.value not in kinds
    assert [e.sequence_no for e in events] == list(range(1, len(events) + 1))
    assert str(events[-1].state) == BacktestRunState.CANCELLED.value


async def test_cancelled_run_keeps_its_audit_trail_and_partial_diagnostics(session) -> None:
    # doc 15 §16: "cancellation audit event ve terminal reason korunur".
    admit = await _provisioning_run(session)
    await backtest_cmd.cancel_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.commit()
    await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    kinds = await _audit_kinds(session, admit["run_id"])
    # Both halves survive: the human's request AND the worker carrying it out.
    assert "backtest.run_cancellation_requested" in kinds
    assert "backtest.run_cancelled" in kinds
    outbox = (
        await session.execute(
            select(OutboxEvent.event_type).where(OutboxEvent.resource_id == admit["run_id"])
        )
    ).all()
    assert "backtest.run_cancelled" in [str(t) for (t,) in outbox]

    # Diagnostics are reachable without a Result: the run projection carries the
    # terminal reason and the requester, and the event stream carries the stage the
    # cancellation stopped at.
    view = await backtest_query.get_backtest_run(session, USER1, run_id=admit["run_id"])
    assert view["state"] == BacktestRunState.CANCELLED.value
    assert view["result_id"] is None
    assert view["cancellation_reason"] is not None
    assert view["cancel_requested_by_principal_id"] == USER1.principal_id

    stream = await backtest_query.list_backtest_run_events(session, USER1, run_id=admit["run_id"])
    terminal = stream["events"][-1]
    assert terminal["event_type"] == RunEventType.RUN_CANCELLED.value
    assert terminal["detail"]["cancelled_at_stage"] == BacktestRunState.PROVISIONING.value
    assert terminal["detail"]["requested_by_principal_id"] == USER1.principal_id
    assert terminal["detail"]["result_id"] is None


async def test_cancelled_run_never_reaches_results_history(session) -> None:
    # Results History indexes final Results; a cancelled run has none, so it must not
    # appear there under any listing (doc 15 §8.4, doc 16 §9.2).
    admit = await _provisioning_run(session)
    await backtest_cmd.cancel_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.commit()
    await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    history = await history_query.list_backtest_results(session, USER1)
    assert history["items"] == []
    assert history["next_cursor"] is None


# --------------------------------------------------------------------------- #
# Policy, OCC and idempotency                                                 #
# --------------------------------------------------------------------------- #


async def test_foreign_actor_cannot_cancel_someone_elses_run(session) -> None:
    admit = await _admit(session)

    with pytest.raises(AccessDeniedError):
        await backtest_cmd.cancel_backtest_run(session, USER2, run_id=admit["run_id"])
    await session.rollback()

    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None
    assert str(run.state) == BacktestRunState.QUEUED.value
    assert run.cancel_requested_at is None


async def test_admin_may_cancel_another_users_run(session) -> None:
    admit = await _admit(session)

    out = await backtest_cmd.cancel_backtest_run(session, ADMIN, run_id=admit["run_id"])
    await session.commit()

    assert out["state"] == BacktestRunState.CANCELLED.value
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None
    assert run.cancel_requested_by_principal_id == ADMIN.principal_id


async def test_cancelling_a_terminal_run_conflicts(session) -> None:
    admit = await _admit(session)
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out["state"] == BacktestRunState.SUCCEEDED.value

    with pytest.raises(RunNotCancellableError) as excinfo:
        await backtest_cmd.cancel_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.rollback()
    assert excinfo.value.http_status == 409
    assert excinfo.value.code == "RUN_NOT_CANCELLABLE"

    # A succeeded run's immutable Result is never withdrawn by a refused cancel.
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None
    assert str(run.state) == BacktestRunState.SUCCEEDED.value
    assert run.result_id == out["result_id"]


async def test_cancelling_an_already_cancelled_run_conflicts(session) -> None:
    admit = await _admit(session)
    await backtest_cmd.cancel_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.commit()

    with pytest.raises(RunNotCancellableError):
        await backtest_cmd.cancel_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.rollback()

    # Exactly one terminal event: the refused second cancel wrote nothing.
    assert len(await _events(session, admit["run_id"])) == 1


async def test_stale_expected_row_version_is_rejected(session) -> None:
    admit = await _admit(session)
    view = await backtest_query.get_backtest_run(session, USER1, run_id=admit["run_id"])

    with pytest.raises(RowVersionConflictError):
        await backtest_cmd.cancel_backtest_run(
            session,
            USER1,
            run_id=admit["run_id"],
            expected_row_version=view["row_version"] + 1,
        )
    await session.rollback()

    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None and str(run.state) == BacktestRunState.QUEUED.value

    # The current token is accepted and bumps the row version.
    out = await backtest_cmd.cancel_backtest_run(
        session, USER1, run_id=admit["run_id"], expected_row_version=view["row_version"]
    )
    await session.commit()
    assert out["row_version"] == view["row_version"] + 1


async def test_cancel_requester_must_be_a_real_principal(session) -> None:
    # L1 proof for the new FK: the requester column references ``principals``, so an
    # unknown principal is refused by the database, not by convention. The cancel
    # audit trail can therefore never name an actor that does not exist.
    admit = await _admit(session)
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None

    run.cancel_requested_by_principal_id = "principal_does_not_exist"
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()

    # The real principal is accepted on the same column.
    out = await backtest_cmd.cancel_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.commit()
    assert out["state"] == BacktestRunState.CANCELLED.value


async def test_replayed_idempotency_key_cancels_once(session) -> None:
    admit = await _admit(session)
    first = await backtest_cmd.cancel_backtest_run(
        session, USER1, run_id=admit["run_id"], idempotency_key="cancel-key-1"
    )
    await session.commit()

    # The replay returns the stored response instead of raising RUN_NOT_CANCELLABLE
    # on the now-terminal run, and appends no second terminal event.
    second = await backtest_cmd.cancel_backtest_run(
        session, USER1, run_id=admit["run_id"], idempotency_key="cancel-key-1"
    )
    await session.commit()

    assert second == first
    assert len(await _events(session, admit["run_id"])) == 1
    assert await _result_count(session) == 0
