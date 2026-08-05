"""ADIM 21 — every durable queue must have a consumer in the shipped stack.

The recovery machinery assumes something is LISTENING. ``ACTOR_BY_QUEUE`` marks a
queue as safely auto-redeliverable and the scheduler re-sends every stranded row
to it each grace window — but if no worker process consumes that queue, the sweep
becomes an infinite, futile re-send: the job is QUEUED forever, the Coordinator
keeps producing more, and nothing anywhere reports a problem, because from the
scheduler's side the send SUCCEEDED.

That is not hypothetical. ``agent-executor`` shipped with a registered actor, an
``ACTOR_BY_QUEUE`` entry, an in-tree dispatcher (``apps/agent_coordinator``) and a
codemap row claiming automatic redelivery — and no ``--queues`` list anywhere in
``docker-compose.yml`` that included it.

This test reads the deployment, not a doc, so it cannot drift from it.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml

from entropia.apps.worker import actors as worker_actors

_COMPOSE = Path(__file__).resolve().parents[3] / "docker-compose.yml"
_WORKER_ENTRYPOINT = "entropia.apps.worker"


def _declared_queues() -> set[str]:
    """Every queue a durable actor is registered on."""
    queues: set[str] = set()
    for name in dir(worker_actors):
        candidate = getattr(worker_actors, name)
        fn = getattr(candidate, "fn", None)
        if fn is None or not hasattr(candidate, "queue_name"):
            continue
        if "job_id" in inspect.signature(fn).parameters:
            queues.add(candidate.queue_name)
    return queues


def _consumed_queues() -> dict[str, list[str]]:
    """``queue -> [compose service, ...]`` read from the worker commands."""
    compose = yaml.safe_load(_COMPOSE.read_text())
    consumed: dict[str, list[str]] = {}
    for service, spec in (compose.get("services") or {}).items():
        command = spec.get("command")
        if not isinstance(command, list) or _WORKER_ENTRYPOINT not in command:
            continue
        if "--queues" not in command:
            continue
        raw = command[command.index("--queues") + 1]
        for queue in str(raw).split(","):
            consumed.setdefault(queue.strip(), []).append(service)
    return consumed


@pytest.mark.skipif(not _COMPOSE.exists(), reason="docker-compose.yml not in this checkout")
def test_every_durable_queue_has_a_worker_service() -> None:
    declared = _declared_queues()
    consumed = _consumed_queues()
    assert consumed, "no worker service with a --queues command found in docker-compose.yml"
    orphaned = declared - set(consumed)
    assert not orphaned, (
        f"durable queues with NO consumer in docker-compose.yml: {sorted(orphaned)} — "
        "jobs on these are enqueued, redelivered by the scheduler forever, and never run"
    )


@pytest.mark.skipif(not _COMPOSE.exists(), reason="docker-compose.yml not in this checkout")
def test_no_worker_service_consumes_a_queue_no_actor_serves() -> None:
    """The mirror defect: a service burning a container on a queue nothing produces
    to, which reads as a healthy plane and silently covers nothing."""
    declared = _declared_queues()
    unknown = {q: svcs for q, svcs in _consumed_queues().items() if q not in declared}
    assert not unknown, f"worker services consuming queues no durable actor serves: {unknown}"
