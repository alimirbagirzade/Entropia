"""The process-wide asyncio runtime behind every sync worker entrypoint.

Infra-free. The integration counterpart (``tests/integration/
test_worker_actor_event_loop.py``) proves the same seam against a real engine;
this file pins the contract itself plus a STATIC guard that no actor may go back
to ``asyncio.run``, which is the defect that stranded ``data``-queue jobs.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from entropia.infrastructure.async_runtime import (
    RUNTIME_THREAD_NAME,
    _reset_after_fork,
    get_runtime_loop,
    run_sync,
    shutdown_runtime,
)


async def _echo(value: int) -> int:
    await asyncio.sleep(0)
    return value


async def _boom() -> None:
    await asyncio.sleep(0)
    raise ValueError("body failed")


def test_run_sync_returns_the_coroutine_result() -> None:
    assert run_sync(_echo(7)) == 7


def test_run_sync_propagates_the_body_exception_unchanged() -> None:
    # Dramatiq's retry policy keys off the exception escaping the actor body, so
    # the wrapper must not swallow or rewrap it.
    with pytest.raises(ValueError, match="body failed"):
        run_sync(_boom())


def test_every_thread_shares_one_loop_on_a_named_thread() -> None:
    """The whole point: one loop per process, so the pool never outlives it."""

    def observe() -> int:
        return run_sync(_loop_identity())

    with ThreadPoolExecutor(max_workers=8) as pool:
        observed = set(pool.map(lambda _: observe(), range(24)))

    assert observed == {id(get_runtime_loop())}
    assert RUNTIME_THREAD_NAME in {t.name for t in threading.enumerate()}


async def _loop_identity() -> int:
    return id(asyncio.get_running_loop())


async def test_run_sync_refuses_to_run_inside_a_running_loop() -> None:
    # Blocking the runtime loop from inside a coroutine would deadlock it; the
    # caller is told to await instead rather than hanging the worker.
    with pytest.raises(RuntimeError, match="cannot be called from a running event loop"):
        run_sync(_echo(1))


def test_shutdown_is_idempotent_and_the_loop_restarts_on_demand() -> None:
    first = get_runtime_loop()
    shutdown_runtime()
    shutdown_runtime()  # no loop left to stop — must not raise
    assert first.is_closed()

    second = get_runtime_loop()
    assert second is not first
    assert run_sync(_echo(3)) == 3


def test_fork_reset_drops_the_inherited_loop() -> None:
    """A forked child inherits the loop object but not the thread running it.

    Reusing it would block the child forever on its first submission — the same
    silent stranding this module removes — so the child starts a fresh one.
    Dramatiq's ``--processes`` forks, which is why this guard is not theoretical.
    """
    inherited = get_runtime_loop()
    _reset_after_fork()

    rebuilt = get_runtime_loop()
    assert rebuilt is not inherited
    assert run_sync(_echo(5)) == 5

    inherited.call_soon_threadsafe(inherited.stop)  # retire the orphaned loop


def test_no_actor_body_uses_asyncio_run() -> None:
    """Static guard (AST, so a docstring mention cannot satisfy or break it).

    ``asyncio.run`` closes its loop per message while the ``@lru_cache`` asyncpg
    pool is process-wide; on the multi-actor ``data`` queue the resulting
    discarded message is UNRECOVERABLE (that queue is deliberately absent from
    ``ACTOR_BY_QUEUE``). A new actor added with the old shape fails here.
    """
    from entropia.apps.worker import actors

    tree = ast.parse(Path(inspect.getfile(actors)).read_text(encoding="utf-8"))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "asyncio"
    ]
    assert offenders == [], f"asyncio.run() at actors.py lines {offenders}; use run_sync()"


def test_every_actor_crosses_the_boundary_through_run_sync() -> None:
    from entropia.apps.worker import actors

    source = Path(inspect.getfile(actors)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    actor_bodies = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "actor"
            for d in node.decorator_list
        )
    ]
    assert len(actor_bodies) >= 12  # the shipped actor set; more is fine, fewer is a regression

    for body in actor_bodies:
        calls = {
            node.func.id
            for node in ast.walk(body)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        # ``system_heartbeat`` is pure logging and needs no async body at all.
        assert "run_sync" in calls or body.name == "system_heartbeat", (
            f"actor {body.name} does not reach its async body through run_sync()"
        )
