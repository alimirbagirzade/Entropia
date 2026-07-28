"""O-05 — durable, sequenced run stage observability (doc 15 §7, §8.3, §11, §12).

Before this slice the worker set PROVISIONING/RUNNING on an in-memory ORM object
and the whole job body was committed once, at the very end, so from outside the
run jumped QUEUED -> SUCCEEDED/FAILED and no stage event existed anywhere. These
tests pin the four properties that fix costs us nothing to keep true:

* the stage trail is durable and monotonic (QUEUED -> PROVISIONING -> RUNNING ->
  terminal), each stage COMMITTED before the next begins — proved by killing the
  worker mid-stage and showing the earlier stage survives the rollback;
* a client reconnecting from ``last_sequence`` loses nothing and repeats nothing;
* one logical event owns its ``sequence_no`` forever, so a redelivered event
  de-duplicates by that key (``UNIQUE(run_id, sequence_no)``);
* the at-least-once guard is untouched — a terminal run is never re-run and
  writes no further events.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.queries import backtest_run as backtest_query
from entropia.domain.backtest.enums import BacktestRunState, RunEventType
from entropia.infrastructure.postgres.models import BacktestRun, BacktestRunEvent
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.shared.errors import AccessDeniedError
from entropia.shared.ids import new_id
from tests.integration.test_backtest_persistence import (
    USER1,
    USER2,
    _e2e_bars,
    _ready_composition,
    _seed_principals,
)

pytestmark = pytest.mark.integration


class _WorkerKilled(BaseException):
    """A hard worker kill (SIGKILL-like), NOT an ``Exception``.

    Deliberately outside the ``Exception`` hierarchy so it bypasses the engine's
    ``except Exception`` -> FAILED handling and escapes ``run_backtest`` exactly the
    way a killed process would: no terminal state is written, and whatever the job
    had already committed is all that survives."""


def _bars_killed_before_any_batch(_source: Any) -> Iterator[list[dict[str, Any]]]:
    """Dies while the run is still PROVISIONING (the first batch is pulled there)."""
    raise _WorkerKilled("worker killed during provisioning")
    yield []  # pragma: no cover - unreachable, keeps this a generator


def _bars_killed_mid_replay(_source: Any) -> Iterator[list[dict[str, Any]]]:
    """Yields the batch PROVISIONING consumes, then dies inside the engine replay.

    The first pull happens during preparation (the empty-range probe); every later
    pull comes from ``run_engine`` itself, i.e. while the run is durably RUNNING."""
    yield [
        {
            "timestamp": f"2024-02-{i + 1:02d}T00:00:00Z",
            "open": "100",
            "high": "100",
            "low": "100",
            "close": "100",
            "volume": "5",
        }
        for i in range(20)
    ]
    raise _WorkerKilled("worker killed during bar replay")


async def _admit(session) -> dict[str, Any]:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    return admit


async def _events(session, run_id: str) -> list[BacktestRunEvent]:
    stmt = (
        select(BacktestRunEvent)
        .where(BacktestRunEvent.run_id == run_id)
        .order_by(BacktestRunEvent.sequence_no.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def _durable_state(session, run_id: str) -> str:
    """The run state as another reader would see it (committed data only)."""
    run = await session.get(BacktestRun, run_id)
    assert run is not None
    return str(run.state)


# --------------------------------------------------------------------------- #
# The full trail                                                              #
# --------------------------------------------------------------------------- #


async def test_successful_run_writes_the_full_monotonic_stage_trail(session) -> None:
    admit = await _admit(session)
    assert admit["state"] == "queued"

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out["state"] == "succeeded"

    events = await _events(session, admit["run_id"])
    assert [e.sequence_no for e in events] == [1, 2, 3]
    assert [str(e.event_type) for e in events] == [
        RunEventType.RUN_STARTED.value,
        RunEventType.RUN_STAGE_CHANGED.value,
        RunEventType.RUN_SUCCEEDED.value,
    ]
    # QUEUED -> PROVISIONING -> RUNNING -> SUCCEEDED, every hop attributed.
    assert [(str(e.previous_state), str(e.state)) for e in events] == [
        (BacktestRunState.QUEUED.value, BacktestRunState.PROVISIONING.value),
        (BacktestRunState.PROVISIONING.value, BacktestRunState.RUNNING.value),
        (BacktestRunState.RUNNING.value, BacktestRunState.SUCCEEDED.value),
    ]
    assert events[2].detail["result_id"] == out["result_id"]

    view = await backtest_query.get_backtest_run(session, USER1, run_id=admit["run_id"])
    assert view["last_sequence"] == 3


async def test_failed_run_records_its_terminal_event(session) -> None:
    # An unresolved pin fails the run while PROVISIONING — the trail must show the
    # stage it died in, and never claim it reached RUNNING.
    admit = await _admit(session)
    run = await session.get(BacktestRun, admit["run_id"])
    manifest = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert run is not None and manifest is not None
    broken = dict(manifest.manifest)
    broken["mainboard_items"] = [
        {**item, "selected_revision_id": "wor_missing"}
        for item in broken.get("mainboard_items", [])
    ]
    manifest.manifest = broken
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out["state"] == "failed"

    events = await _events(session, admit["run_id"])
    assert [str(e.event_type) for e in events] == [
        RunEventType.RUN_STARTED.value,
        RunEventType.RUN_FAILED.value,
    ]
    assert [e.sequence_no for e in events] == [1, 2]
    assert str(events[1].previous_state) == BacktestRunState.PROVISIONING.value
    assert events[1].detail["failure_code"] == out["failure_code"]
    assert BacktestRunState.RUNNING.value not in [str(e.state) for e in events]


# --------------------------------------------------------------------------- #
# Durability: each stage is COMMITTED before the next begins                  #
# --------------------------------------------------------------------------- #


async def test_provisioning_survives_a_worker_kill(session) -> None:
    # The whole point of the intermediate commit: kill the worker before it reaches
    # RUNNING, roll back exactly what the actor would roll back, and the run must
    # still read PROVISIONING. With the pre-O-05 single end-of-job commit this
    # rollback returned the run to QUEUED and destroyed every trace of the attempt.
    admit = await _admit(session)

    with pytest.raises(_WorkerKilled):
        await run_backtest(session, admit["job_id"], stream_bars=_bars_killed_before_any_batch)
    await session.rollback()

    assert await _durable_state(session, admit["run_id"]) == BacktestRunState.PROVISIONING.value
    events = await _events(session, admit["run_id"])
    assert [str(e.event_type) for e in events] == [RunEventType.RUN_STARTED.value]
    assert events[0].sequence_no == 1


async def test_running_survives_a_worker_kill_mid_replay(session) -> None:
    # RUNNING is committed BEFORE the engine replays, so a kill during the
    # simulation leaves the honest "it was running" state — not a silent revert and
    # not a fabricated terminal outcome.
    admit = await _admit(session)

    with pytest.raises(_WorkerKilled):
        await run_backtest(session, admit["job_id"], stream_bars=_bars_killed_mid_replay)
    await session.rollback()

    assert await _durable_state(session, admit["run_id"]) == BacktestRunState.RUNNING.value
    events = await _events(session, admit["run_id"])
    assert [str(e.event_type) for e in events] == [
        RunEventType.RUN_STARTED.value,
        RunEventType.RUN_STAGE_CHANGED.value,
    ]
    assert [e.sequence_no for e in events] == [1, 2]
    # No terminal event was invented for a run nobody finished.
    assert all(
        str(e.state) in {BacktestRunState.PROVISIONING.value, BacktestRunState.RUNNING.value}
        for e in events
    )


# --------------------------------------------------------------------------- #
# Reconnect + de-duplication (doc 15 §7, §11)                                 #
# --------------------------------------------------------------------------- #


async def test_reconnect_from_last_sequence_is_lossless(session) -> None:
    admit = await _admit(session)
    await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    run_id = admit["run_id"]

    full = await backtest_query.list_backtest_run_events(session, USER1, run_id=run_id)
    assert [e["sequence_no"] for e in full["events"]] == [1, 2, 3]
    assert full["has_more"] is False

    # Walk the stream one event at a time, exactly as a client resuming after each
    # dropped connection would: the concatenation must reproduce the full stream
    # with no gap and no repeat.
    replayed: list[dict[str, Any]] = []
    cursor = 0
    while True:
        page = await backtest_query.list_backtest_run_events(
            session, USER1, run_id=run_id, last_sequence=cursor, limit=1
        )
        if not page["events"]:
            break
        replayed.extend(page["events"])
        assert page["next_sequence"] > cursor
        cursor = page["next_sequence"]
    assert replayed == full["events"]
    assert [e["sequence_no"] for e in replayed] == [1, 2, 3]

    # Resuming from the end yields nothing and does not move the cursor.
    tail = await backtest_query.list_backtest_run_events(
        session, USER1, run_id=run_id, last_sequence=full["last_sequence"]
    )
    assert tail["events"] == [] and tail["next_sequence"] == full["last_sequence"]
    assert tail["state"] == "succeeded"


async def test_overlapping_replays_de_duplicate_by_sequence_no(session) -> None:
    # At-least-once delivery means a client can receive the same event twice. It is
    # de-duplicated by sequence_no because one logical event always carries the SAME
    # sequence, whichever window it arrives in (doc 15 §7).
    admit = await _admit(session)
    await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    run_id = admit["run_id"]

    first = await backtest_query.list_backtest_run_events(session, USER1, run_id=run_id, limit=2)
    overlapping = await backtest_query.list_backtest_run_events(
        session, USER1, run_id=run_id, last_sequence=0
    )
    delivered = [*first["events"], *overlapping["events"]]
    assert len(delivered) == 5  # 2 + 3, with two genuine duplicates in the middle

    by_sequence = {event["sequence_no"]: event for event in delivered}
    assert sorted(by_sequence) == [1, 2, 3]
    for event in delivered:
        assert by_sequence[event["sequence_no"]] == event  # identical, not merely same id


async def test_duplicate_sequence_for_a_run_is_rejected(session) -> None:
    # The de-duplication key is enforced, not merely conventional.
    admit = await _admit(session)
    await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    session.add(
        BacktestRunEvent(
            event_id=new_id("brev"),
            run_id=admit["run_id"],
            sequence_no=1,
            event_type=RunEventType.RUN_STAGE_CHANGED,
            previous_state=BacktestRunState.QUEUED,
            state=BacktestRunState.PROVISIONING,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


# --------------------------------------------------------------------------- #
# L1 FK insert order + the untouched at-least-once guard                      #
# --------------------------------------------------------------------------- #


async def test_run_event_requires_its_parent_run_row(session) -> None:
    # L1 proof: the event is a child of the run root. Parent first — the worker
    # always holds a persisted run — and an orphan is refused by the database, not
    # by convention.
    admit = await _admit(session)
    parented = await bt_repo.record_run_event(
        session,
        run_id=admit["run_id"],
        event_type=RunEventType.RUN_STARTED,
        previous_state=BacktestRunState.QUEUED,
        state=BacktestRunState.PROVISIONING,
    )
    await session.commit()
    assert parented.sequence_no == 1

    with pytest.raises(IntegrityError):
        await bt_repo.record_run_event(
            session,
            run_id="run_does_not_exist",
            event_type=RunEventType.RUN_STARTED,
            previous_state=BacktestRunState.QUEUED,
            state=BacktestRunState.PROVISIONING,
        )
    await session.rollback()

    total = (await session.execute(select(func.count()).select_from(BacktestRunEvent))).scalar_one()
    assert int(total) == 1


async def test_terminal_redelivery_writes_no_further_events(session) -> None:
    # The at-least-once guard is untouched by O-05: a redelivered message for a
    # terminal run returns the durable outcome, re-runs nothing and appends nothing.
    admit = await _admit(session)
    first = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    before = await _events(session, admit["run_id"])

    second = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert second["result_id"] == first["result_id"]
    after = await _events(session, admit["run_id"])
    assert [e.sequence_no for e in after] == [e.sequence_no for e in before]
    assert len(after) == 3


async def test_foreign_actor_cannot_replay_the_event_stream(session) -> None:
    admit = await _admit(session)
    await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    with pytest.raises(AccessDeniedError):
        await backtest_query.list_backtest_run_events(session, USER2, run_id=admit["run_id"])
