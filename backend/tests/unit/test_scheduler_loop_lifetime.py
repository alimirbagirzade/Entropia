"""The scheduler holds ONE event loop for the whole process lifetime.

``get_engine`` is ``@lru_cache``d process-wide, so a pooled asyncpg connection
stays bound to the loop that first opened it. The previous shape — ``asyncio.run``
per tick — created AND closed a loop every tick, so the next tick checked out a
connection attached to a dead loop and the whole pass aborted ("Event loop is
closed" / "got Future attached to a different loop", raised from
``asyncpg/connection.py::_cancel_current_command``). The failed pass discarded
the bad connection, so the tick after it succeeded: passes alternated at exactly
50%, and half of every outbox relay, stale-RUNNING recovery (INF-09) and
lost-message redelivery (INF-03) was skipped and delayed a further tick.

These tests pin the structural invariant without a database — the end-to-end
proof against real Postgres is
``tests/integration/test_scheduler_maintenance_passes.py``. They also cover the
shutdown path, which had to be rebuilt when the uninterruptible ``time.sleep``
went away.
"""

from __future__ import annotations

import asyncio
import signal
from typing import Any

import pytest

from entropia.apps.scheduler import __main__ as scheduler

EMPTY_PASS: dict[str, Any] = {"relayed": 0, "requeued": 0, "failed_terminal": 0, "redelivered": 0}


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
    """Stands in for the cached ``AsyncEngine``; records the loop it was closed on."""

    def __init__(self) -> None:
        self.disposed_on: list[asyncio.AbstractEventLoop] = []

    async def dispose(self) -> None:
        self.disposed_on.append(asyncio.get_running_loop())


@pytest.fixture(autouse=True)
def _isolated_scheduler_state(monkeypatch) -> None:
    """Real signal handlers installed by a run must not leak into the rest of the suite."""
    original = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    monkeypatch.setattr(scheduler, "configure_logging", lambda: None)
    monkeypatch.setattr(scheduler, "tick_seconds", lambda: 0.001)
    yield
    for sig, handler in original.items():
        signal.signal(sig, handler)


@pytest.fixture
def log(monkeypatch) -> _RecordingLog:
    recorder = _RecordingLog()
    monkeypatch.setattr(scheduler, "log", recorder)
    return recorder


@pytest.fixture
def engine(monkeypatch) -> _DisposeSpy:
    spy = _DisposeSpy()
    monkeypatch.setattr(
        "entropia.infrastructure.postgres.engine.get_engine", lambda: spy, raising=True
    )
    return spy


@pytest.fixture
def heartbeats(monkeypatch) -> list[str]:
    """Silence the broker: an enqueue failure is a separate, already-tested path."""
    sent: list[str] = []
    monkeypatch.setattr(
        scheduler,
        "system_heartbeat",
        type("_Actor", (), {"send": staticmethod(lambda note: sent.append(note))})(),
    )
    return sent


def _stub_passes(
    monkeypatch, count: int, saw_a_dead_loop: list[bool] | None = None
) -> list[asyncio.AbstractEventLoop]:
    """Run exactly ``count`` maintenance passes, recording each one's running loop.

    ``saw_a_dead_loop`` collects, per pass, whether ANY loop an earlier pass ran on
    was already closed by the time this pass started — the pre-fix mechanism
    itself, observed from inside the tick rather than inferred after the fact.
    """
    loops: list[asyncio.AbstractEventLoop] = []

    async def _pass() -> dict[str, Any]:
        if saw_a_dead_loop is not None:
            saw_a_dead_loop.append(any(loop.is_closed() for loop in loops))
        loops.append(asyncio.get_running_loop())
        if len(loops) >= count:
            scheduler.request_stop()
        return EMPTY_PASS

    monkeypatch.setattr(scheduler, "_maintenance_pass", _pass)
    return loops


def test_every_pass_runs_on_the_same_event_loop(monkeypatch, log, engine, heartbeats) -> None:
    """The regression itself: six consecutive passes, one loop, and it stays open.

    Under the pre-fix ``asyncio.run``-per-tick shape this list held six DISTINCT
    loops, five of them already closed — which is what stranded the cached pool.
    """
    saw_a_dead_loop: list[bool] = []
    loops = _stub_passes(monkeypatch, count=6, saw_a_dead_loop=saw_a_dead_loop)

    scheduler.run()

    assert len(loops) == 6
    assert len({id(loop) for loop in loops}) == 1, "a new event loop was created mid-run"
    assert saw_a_dead_loop == [False] * 6, "a pass began with an earlier tick's loop closed"


def test_six_consecutive_passes_log_no_failure(monkeypatch, log, engine, heartbeats) -> None:
    _stub_passes(monkeypatch, count=6)

    scheduler.run()

    assert log.names().count("scheduler.maintenance") == 6
    assert "scheduler.maintenance_failed" not in log.names()
    assert log.names()[0] == "scheduler.start"
    assert log.names()[-1] == "scheduler.stop"


def test_a_failing_pass_is_reported_and_the_loop_continues(
    monkeypatch, log, engine, heartbeats
) -> None:
    """Unchanged behaviour: a pass that raises rolls back whole and the next tick retries."""
    attempts = 0

    async def _pass() -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("Event loop is closed")
        scheduler.request_stop()
        return EMPTY_PASS

    monkeypatch.setattr(scheduler, "_maintenance_pass", _pass)

    scheduler.run()

    assert attempts == 2
    failures = [fields for event, fields in log.events if event == "scheduler.maintenance_failed"]
    assert len(failures) == 1
    assert "Event loop is closed" in failures[0]["error"]
    assert log.names().count("scheduler.maintenance") == 1


def test_the_heartbeat_is_sent_once_per_tick(monkeypatch, log, engine, heartbeats) -> None:
    _stub_passes(monkeypatch, count=3)

    scheduler.run()

    assert heartbeats == ["scheduler-tick"] * 3


def test_the_engine_pool_is_returned_while_its_loop_is_still_open(
    monkeypatch, log, engine, heartbeats
) -> None:
    """Disposing after the loop closed would reproduce the very bug, as exit noise."""
    loops = _stub_passes(monkeypatch, count=2)

    scheduler.run()

    assert len(engine.disposed_on) == 1
    assert engine.disposed_on[0] is loops[0], "the pool was not closed on its own loop"


async def test_wait_for_tick_returns_at_once_when_a_stop_is_pending() -> None:
    """A 30s production tick must not become 30s of shutdown latency."""
    stop = asyncio.Event()
    stop.set()

    await asyncio.wait_for(scheduler._wait_for_tick(stop, 30.0), timeout=1.0)


async def test_wait_for_tick_otherwise_waits_out_the_tick() -> None:
    stop = asyncio.Event()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(scheduler._wait_for_tick(stop, 30.0), timeout=0.05)


async def test_sigterm_sets_the_stop_event() -> None:
    """SIGTERM used to need ``signal.signal``; it now lands as a loop callback.

    Raising a real signal is only safe once a handler is installed, so that is
    asserted first — otherwise SIGTERM's default action would kill the test run.
    """
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    scheduler._install_stop_handlers(stop)
    try:
        assert signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL

        signal.raise_signal(signal.SIGTERM)
        await asyncio.wait_for(stop.wait(), timeout=5.0)

        assert stop.is_set()
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)
