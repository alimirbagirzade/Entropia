"""ADIM 21 — the queue -> actor registries the recovery sweeps depend on.

``ACTOR_BY_QUEUE`` is a fencing decision, not a lookup table. The scheduler
auto-redelivers a queue ONLY when the durable ``jobs`` row is enough to pick the
actor, which is true exactly when the queue hosts a single durable-job actor. The
five-actor ``data`` queue is deliberately absent — the row cannot say which of the
five to send — and is routed by an explicit operator action through
``DATA_ACTOR_BY_KIND`` instead.

Both halves are invariants that a future actor can silently break: adding a second
durable actor to ``backtest`` would make the sweep redeliver a backtest job to the
wrong body, and adding a sixth ``data`` kind without a ``DATA_ACTOR_BY_KIND`` entry
would make the operator tool count it ``skipped_unknown_kind`` forever. Nothing
enforced either before this file.
"""

from __future__ import annotations

import inspect

from entropia.application.jobs.data_queue import DATA_JOB_KINDS, DATA_QUEUE
from entropia.apps.scheduler.__main__ import ACTOR_BY_QUEUE
from entropia.apps.worker import actors as worker_actors


def _durable_actors() -> list:
    """Every registered actor whose body takes a durable ``job_id``.

    That parameter IS the definition of a durable-job actor here: it is the only
    thing the recovery sweeps can hand an actor, so an actor without it (the
    scheduler's ``system_heartbeat`` ping) can never be the target of one.
    """
    found = []
    for name in dir(worker_actors):
        candidate = getattr(worker_actors, name)
        fn = getattr(candidate, "fn", None)
        if fn is None or not hasattr(candidate, "queue_name"):
            continue
        if "job_id" in inspect.signature(fn).parameters:
            found.append(candidate)
    return found


def _durable_actors_by_queue() -> dict[str, list[str]]:
    by_queue: dict[str, list[str]] = {}
    for actor in _durable_actors():
        by_queue.setdefault(actor.queue_name, []).append(actor.actor_name)
    return by_queue


def test_every_single_actor_queue_is_registered_for_auto_redelivery() -> None:
    by_queue = _durable_actors_by_queue()
    single = {q for q, names in by_queue.items() if len(names) == 1}
    assert single, "the registry probe found no durable actors at all"
    missing = single - set(ACTOR_BY_QUEUE)
    assert not missing, (
        f"queues with exactly one durable actor but no auto-redelivery: {sorted(missing)} — "
        "a lost broker message on these would strand the job QUEUED forever"
    )


def test_no_multi_actor_queue_is_auto_redelivered() -> None:
    by_queue = _durable_actors_by_queue()
    multi = {q for q, names in by_queue.items() if len(names) > 1}
    assert multi == {DATA_QUEUE}, f"unexpected multi-actor queues: {sorted(multi)}"
    assert DATA_QUEUE not in ACTOR_BY_QUEUE


def test_the_registered_actor_is_the_one_that_actually_serves_the_queue() -> None:
    """A stale entry would send every recovered job to an actor listening on a
    different queue — a redelivery that silently never runs."""
    for queue, actor in ACTOR_BY_QUEUE.items():
        assert actor.queue_name == queue, f"{actor.actor_name} does not serve '{queue}'"


def test_every_data_job_kind_routes_to_an_actor() -> None:
    assert set(worker_actors.DATA_ACTOR_BY_KIND) == set(DATA_JOB_KINDS)
    for kind, actor in worker_actors.DATA_ACTOR_BY_KIND.items():
        assert actor.queue_name == DATA_QUEUE, f"'{kind}' routes off the data queue"


def test_the_data_kind_map_covers_every_durable_actor_on_the_queue() -> None:
    """The other direction: an actor added to ``data`` with no kind entry is
    unreachable by the operator recovery action."""
    on_data = {a.actor_name for a in _durable_actors() if a.queue_name == DATA_QUEUE}
    routed = {a.actor_name for a in worker_actors.DATA_ACTOR_BY_KIND.values()}
    assert on_data == routed, f"unroutable data actors: {sorted(on_data - routed)}"
