"""The coordinator holds ONE event loop for the whole process lifetime (#591).

Identical defect to the scheduler's (#593), found by the same analysis: the loop
called ``asyncio.run(_run_cycle())`` once per cycle, creating AND closing a fresh
event loop each time, while ``get_engine`` is ``@lru_cache``d process-wide. The
pooled asyncpg connection stayed bound to the previous, now-closed loop, so the
next cycle checked it out and the whole cycle aborted ("Event loop is closed" /
"got Future attached to a different loop"). The failed cycle discarded the bad
connection, so the one after it succeeded — cycles alternated at exactly 50%.

It surfaced under a different event name (``agent_coordinator.cycle_failed``, not
``scheduler.maintenance_failed``), which is why it survived the scheduler fix.

These tests pin the structural invariant without a database. There is deliberately
no live-Postgres twin of ``tests/integration/test_scheduler_maintenance_passes.py``
here: a real cycle needs seeded Agent runtime state, and the mechanism it would
re-prove is already proven there against the identical shape.
"""

from __future__ import annotations

import asyncio
import signal
from typing import Any

import pytest

from entropia.apps.agent_coordinator import __main__ as coordinator

IDLE_CYCLE: dict[str, Any] = {
    "runtime_status": "idle",
    "consumed": None,
    "followup_task_id": None,
    "executor_job_id": None,
}


class _RecordingLog:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def info(self, event: str, **fields: Any) -> None:
        self.events.append((event, fields))

    def warning(self, event: str, **fields: Any) -> None:
        self.events.append((event, fields))

    def names(self) -> list[str]:
        return [event for event, _fields in self.events]


class _DisposeSpy:
    def __init__(self) -> None:
        self.disposed_on: list[asyncio.AbstractEventLoop] = []

    async def dispose(self) -> None:
        self.disposed_on.append(asyncio.get_running_loop())


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch) -> None:
    """Real signal handlers installed by a run must not leak into the rest of the suite."""
    original = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    monkeypatch.setattr(coordinator, "configure_logging", lambda: None)
    monkeypatch.setattr(coordinator, "CYCLE_SLEEP_SECONDS", 0.001)
    monkeypatch.setattr(coordinator, "send_job", lambda actor, job_id: None)
    yield
    for sig, handler in original.items():
        signal.signal(sig, handler)


@pytest.fixture
def log(monkeypatch) -> _RecordingLog:
    recorder = _RecordingLog()
    monkeypatch.setattr(coordinator, "log", recorder)
    return recorder


@pytest.fixture
def engine(monkeypatch) -> _DisposeSpy:
    spy = _DisposeSpy()
    monkeypatch.setattr(
        "entropia.infrastructure.postgres.engine.get_engine", lambda: spy, raising=True
    )
    return spy


def _stub_cycles(
    monkeypatch, count: int, saw_a_dead_loop: list[bool] | None = None
) -> list[asyncio.AbstractEventLoop]:
    """Run exactly ``count`` cycles, recording the loop each one ran on.

    ``saw_a_dead_loop`` collects, per cycle, whether ANY loop an earlier cycle ran
    on was already closed when this one started — the pre-fix mechanism observed
    from inside the cycle rather than inferred afterwards.
    """
    loops: list[asyncio.AbstractEventLoop] = []

    async def _cycle() -> dict[str, Any]:
        if saw_a_dead_loop is not None:
            saw_a_dead_loop.append(any(loop.is_closed() for loop in loops))
        loops.append(asyncio.get_running_loop())
        if len(loops) >= count:
            coordinator.request_stop()
        return IDLE_CYCLE

    monkeypatch.setattr(coordinator, "_run_cycle", _cycle)
    return loops


def test_every_cycle_runs_on_the_same_event_loop(monkeypatch, log, engine) -> None:
    """Under the pre-fix shape these were six DISTINCT loops, five already closed."""
    saw_a_dead_loop: list[bool] = []
    loops = _stub_cycles(monkeypatch, count=6, saw_a_dead_loop=saw_a_dead_loop)

    coordinator.run()

    assert len(loops) == 6
    assert len({id(loop) for loop in loops}) == 1, "a new event loop was created mid-run"
    assert saw_a_dead_loop == [False] * 6, "a cycle began with an earlier cycle's loop closed"


def test_six_consecutive_cycles_log_no_failure(monkeypatch, log, engine) -> None:
    _stub_cycles(monkeypatch, count=6)

    coordinator.run()

    assert log.names().count("agent_coordinator.cycle") == 6
    assert "agent_coordinator.cycle_failed" not in log.names()
    assert log.names()[0] == "agent_coordinator.start"
    assert log.names()[-1] == "agent_coordinator.stop"


def test_a_failing_cycle_is_reported_and_the_loop_continues(monkeypatch, log, engine) -> None:
    """Unchanged behaviour: a bad cycle rolls back whole and the next one retries."""
    attempts = 0

    async def _cycle() -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("Event loop is closed")
        coordinator.request_stop()
        return IDLE_CYCLE

    monkeypatch.setattr(coordinator, "_run_cycle", _cycle)

    coordinator.run()

    assert attempts == 2
    failures = [f for event, f in log.events if event == "agent_coordinator.cycle_failed"]
    assert len(failures) == 1
    assert "Event loop is closed" in failures[0]["error"]


def test_the_executor_dispatch_still_happens_after_the_cycle(monkeypatch, log, engine) -> None:
    """F-20 dispatch is unchanged: commit-then-send, once per cycle that produced a job."""
    dispatched: list[str] = []
    monkeypatch.setattr(coordinator, "send_job", lambda actor, job_id: dispatched.append(job_id))

    async def _cycle() -> dict[str, Any]:
        coordinator.request_stop()
        return {**IDLE_CYCLE, "executor_job_id": "job_exec_1"}

    monkeypatch.setattr(coordinator, "_run_cycle", _cycle)

    coordinator.run()

    assert dispatched == ["job_exec_1"]
    assert "agent_coordinator.dispatch_failed" not in log.names()


def test_a_failed_dispatch_is_warned_without_failing_the_cycle(monkeypatch, log, engine) -> None:
    """The row stays durably QUEUED; the scheduler's INF-03 sweep re-sends it."""

    def _raise(actor: Any, job_id: str) -> None:
        raise RuntimeError("broker unreachable")

    monkeypatch.setattr(coordinator, "send_job", _raise)

    async def _cycle() -> dict[str, Any]:
        coordinator.request_stop()
        return {**IDLE_CYCLE, "executor_job_id": "job_exec_1"}

    monkeypatch.setattr(coordinator, "_run_cycle", _cycle)

    coordinator.run()

    assert "agent_coordinator.dispatch_failed" in log.names()
    assert "agent_coordinator.cycle_failed" not in log.names()
    assert log.names().count("agent_coordinator.cycle") == 1


def test_the_engine_pool_is_returned_while_its_loop_is_still_open(monkeypatch, log, engine) -> None:
    loops = _stub_cycles(monkeypatch, count=2)

    coordinator.run()

    assert len(engine.disposed_on) == 1
    assert engine.disposed_on[0] is loops[0], "the pool was not closed on its own loop"


async def test_wait_for_cycle_returns_at_once_when_a_stop_is_pending() -> None:
    stop = asyncio.Event()
    stop.set()

    await asyncio.wait_for(coordinator._wait_for_cycle(stop, 30.0), timeout=1.0)


async def test_wait_for_cycle_otherwise_waits_out_the_cycle() -> None:
    stop = asyncio.Event()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(coordinator._wait_for_cycle(stop, 30.0), timeout=0.05)


async def test_sigterm_sets_the_stop_event() -> None:
    """Raising a real signal is only safe once a handler is installed — asserted first."""
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    coordinator._install_stop_handlers(stop)
    try:
        assert signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL

        signal.raise_signal(signal.SIGTERM)
        await asyncio.wait_for(stop.wait(), timeout=5.0)

        assert stop.is_set()
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)
