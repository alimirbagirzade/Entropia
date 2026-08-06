"""One long-lived asyncio event loop per PROCESS, for synchronous entrypoints.

Why this exists. Every dramatiq actor body used to wrap its coroutine in
``asyncio.run(...)``, which builds AND closes a fresh event loop per message.
``postgres/engine.py::get_engine`` is ``@lru_cache(maxsize=1)``, so the asyncpg
connection pool is process-wide and OUTLIVES every one of those loops. A dramatiq
worker runs several threads per process, so a pooled connection created under one
thread's loop gets checked out under another thread's loop and asyncpg raises::

    RuntimeError: Task <Task ... _run_market_data_analysis() ...>
      got Future <Future pending ...> attached to a different loop

Dramatiq then retries, ``max_retries`` is exhausted and the broker DISCARDS the
message. On the ``data`` queue that is unrecoverable: the queue is deliberately
excluded from the scheduler's re-dispatch registry
(``apps/scheduler/__main__.py::ACTOR_BY_QUEUE`` — re-dispatch is an operator
action), so the durable row stays QUEUED forever with ``attempts = 0`` (the body
crashed before committing its RUNNING transition) and the effect never happens.
A crash is not required to trigger it: any two ``data`` jobs in parallel suffice.

The fix is to give the pool a loop that outlives it instead of the other way
around: ONE loop per process, owned by a dedicated daemon thread, with every
sync entrypoint submitting its coroutine through ``run_sync``. Every pooled
connection is then created and awaited on the same loop for the life of the
process.

Scope — this is the seam for SYNC ENTRYPOINTS ONLY, and deliberately not a
process-wide loop policy. ``apps/scheduler/__main__.py`` and
``apps/agent_coordinator/__main__.py`` carried the same defect and were fixed
separately (#593, #600): each now holds ONE loop for its process lifetime as
``asyncio.run(_loop_until_stopped())``. They must NOT be routed through here, for
two reasons. They own their process's main loop and install SIGTERM/SIGINT with
``loop.add_signal_handler``, which raises ``RuntimeError: set_wakeup_fd only
works in main thread of the main interpreter`` anywhere but the main thread —
and this module's loop lives on a daemon thread by construction. And the shapes
differ: those two run a single long-lived async body that IS the process,
whereas an actor is a short sync entrypoint invoked once per message, which is
exactly the case that needs a loop outliving the call. Two mechanisms, one rule
(the loop must outlive the pool) — not an inconsistency to collapse.

Consequence worth knowing: coroutines submitted from all worker threads now
interleave on ONE loop thread. For the I/O-bound job bodies on these queues that
is a gain (they overlap instead of being one-per-thread), and CPU-bound stretches
were already GIL-serialized — but a long synchronous stretch inside a body now
delays other jobs' I/O rather than only holding the GIL. A body that becomes
CPU-heavy must hand that work to ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

_T = TypeVar("_T")

# Named so a thread dump from a stuck worker says which loop is which.
RUNTIME_THREAD_NAME = "entropia-async-runtime"

# How long ``shutdown_runtime`` waits for the loop thread to unwind.
_SHUTDOWN_TIMEOUT_SECONDS = 5.0

_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_owner_pid: int | None = None


def _serve(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _reset_after_fork() -> None:
    """Drop the inherited loop in a forked child.

    ``fork`` copies the loop object but NOT the thread running it, so a child
    that reused the parent's loop would block forever on the first submission —
    the same silent-stranding failure this module exists to remove. Dramatiq's
    ``--processes`` forks at boot, so this is the guard that keeps the fix true
    on a multi-process worker. The lock is rebuilt too: a lock held by another
    thread at fork time is inherited locked and would deadlock the child.
    """
    global _lock, _loop, _thread, _owner_pid
    _lock = threading.Lock()
    _loop = None
    _thread = None
    _owner_pid = None


os.register_at_fork(after_in_child=_reset_after_fork)


def get_runtime_loop() -> asyncio.AbstractEventLoop:
    """The process-wide loop, started on first use."""
    global _loop, _thread, _owner_pid
    with _lock:
        if _loop is not None and not _loop.is_closed() and _owner_pid == os.getpid():
            return _loop
        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=_serve, args=(loop,), name=RUNTIME_THREAD_NAME, daemon=True
        )
        thread.start()
        _loop, _thread, _owner_pid = loop, thread, os.getpid()
        return loop


def run_sync(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run ``coro`` on the process-wide loop and block for its result.

    Drop-in for ``asyncio.run`` at a synchronous entrypoint, minus the
    loop-per-call that orphans the connection pool. Exceptions propagate to the
    caller unchanged, so dramatiq's retry semantics are untouched.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        # Blocking on the runtime loop from inside a coroutine would deadlock it.
        coro.close()
        raise RuntimeError("run_sync() cannot be called from a running event loop; await instead.")

    future = asyncio.run_coroutine_threadsafe(coro, get_runtime_loop())
    try:
        return future.result()
    except BaseException:
        # The caller is leaving (dramatiq raises its shutdown/time-limit
        # interrupts INTO the worker thread, which is the thread parked here).
        # Without this the coroutine would keep running on the shared loop,
        # holding a connection, with nobody left to observe it. Best effort: a
        # future that already completed ignores the cancel.
        future.cancel()
        raise


def shutdown_runtime() -> None:
    """Stop the process-wide loop and wait for its thread. Idempotent.

    For a clean process exit and for tests that need a fresh loop; the next
    ``run_sync`` transparently starts a new one. Call it only when no submission
    is in flight — a caller already parked in ``run_sync`` waits on a loop that
    is no longer turning, and would block until the process ends.
    """
    global _loop, _thread, _owner_pid
    with _lock:
        loop, thread = _loop, _thread
        _loop, _thread, _owner_pid = None, None, None

    if loop is None:
        return
    loop.call_soon_threadsafe(loop.stop)
    if thread is not None:
        thread.join(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
    loop.close()


__all__ = ["RUNTIME_THREAD_NAME", "get_runtime_loop", "run_sync", "shutdown_runtime"]
