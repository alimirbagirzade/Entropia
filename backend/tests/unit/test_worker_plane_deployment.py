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

The same class of gap repeats one layer up, in the OVERRIDE files. A plane added
to ``docker-compose.yml`` but forgotten in ``docker-compose.dev-auth.yml`` still
starts and still looks healthy — it just runs the WRONG auth mode, because the
override is what forces ``AUTH_MODE=dev`` and every plane it omits keeps the
``AUTH_MODE=session`` coming from ``env_file: .env``. That is not hypothetical
either: ``worker-agent-executor`` shipped in the base stack and was missing from
the dev-auth override, so under ``make up-dev-auth`` it was the one plane still
demanding session tokens.

These tests read the deployment, not a doc, so they cannot drift from it.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml

from entropia.apps.worker import actors as worker_actors

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _REPO_ROOT / "docker-compose.yml"
_DEV_AUTH_COMPOSE = _REPO_ROOT / "docker-compose.dev-auth.yml"
_WORKER_ENTRYPOINT = "entropia.apps.worker"
_BACKEND_IMAGE = "entropia-backend:local"


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


def _backend_planes() -> set[str]:
    """Every base-stack service running the backend image (api + workers + one-shots).

    Read from the resolved ``image:`` rather than a hand-kept name list, so a plane
    added via the ``*backend-build`` anchor is covered the moment it is written.
    """
    compose = yaml.safe_load(_COMPOSE.read_text())
    return {
        service
        for service, spec in (compose.get("services") or {}).items()
        if (spec or {}).get("image") == _BACKEND_IMAGE
    }


def _dev_auth_overrides() -> dict[str, dict]:
    override = yaml.safe_load(_DEV_AUTH_COMPOSE.read_text())
    return {service: (spec or {}) for service, spec in (override.get("services") or {}).items()}


_HAS_BOTH_COMPOSE_FILES = _COMPOSE.exists() and _DEV_AUTH_COMPOSE.exists()


@pytest.mark.skipif(not _HAS_BOTH_COMPOSE_FILES, reason="compose files not in this checkout")
def test_dev_auth_override_forces_dev_mode_on_every_backend_plane() -> None:
    """A plane the override forgets keeps ``AUTH_MODE=session`` from ``env_file``.

    It still starts and still passes its healthcheck, so the stack reads green while
    one plane rejects the impersonation headers every other plane is honouring.
    """
    overrides = _dev_auth_overrides()
    missing = sorted(plane for plane in _backend_planes() if plane not in overrides)
    assert not missing, (
        f"backend planes absent from docker-compose.dev-auth.yml: {missing} — under "
        "`make up-dev-auth` these keep AUTH_MODE=session from env_file while every "
        "other plane runs AUTH_MODE=dev"
    )

    wrong_mode = {
        plane: spec.get("environment")
        for plane, spec in overrides.items()
        if (spec.get("environment") or {}).get("AUTH_MODE") != "dev"
    }
    assert not wrong_mode, f"dev-auth override services not pinned to AUTH_MODE=dev: {wrong_mode}"


@pytest.mark.skipif(not _HAS_BOTH_COMPOSE_FILES, reason="compose files not in this checkout")
def test_dev_auth_override_declares_no_service_the_base_stack_lacks() -> None:
    """The mirror defect: a misspelt service name in the override.

    Compose merges by name, so ``worker-agent-exectuor:`` does not raise — it defines
    a brand-new imageless service AND leaves the real plane on session mode.
    """
    stray = sorted(set(_dev_auth_overrides()) - _backend_planes())
    assert not stray, (
        f"dev-auth override defines services the base stack has no backend plane for: "
        f"{stray} — a typo here silently leaves the real plane on AUTH_MODE=session"
    )
