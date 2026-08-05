"""Shared at-least-once delivery guard for durable worker bodies (INF-03/INF-09).

The broker message is only transport; the ``jobs`` row is the source of truth. That
makes every durable actor an AT-LEAST-once delivery, from two independent sources:

* **the broker** — a worker that commits its transaction and then dies before the
  ack gets the SAME message again on restart (the commit/ack boundary);
* **the scheduler** — ``maintenance.redeliverable_queued_jobs`` re-dispatches every
  row still QUEUED past ``JOB_REDELIVER_GRACE_SECONDS``, and a body that never
  commits its ``RUNNING`` transition mid-flight stays QUEUED for its whole run, so
  the sweep can hand a *live* job to a second worker (the lease-expiry boundary).

A durable body therefore has to answer two questions before it writes anything:

1. *Has this job already finished?* — replay the recorded outcome, write nothing.
   A second run would forge a duplicate of an append-only artifact (a normalized
   revision, a validation run, an imported package root) that no unique constraint
   rejects, because each carries a freshly generated id.
2. *Is another delivery running right now?* — serialize behind it, then answer (1).
   The terminal check alone cannot see a concurrent delivery: neither worker has
   committed, so both read the same pre-terminal status and both proceed.

:func:`claim_job_for_delivery` answers both with one locked read of the durable row.
The ``FOR UPDATE`` is held for the rest of the caller's transaction, so a second
delivery *waits* for the first to finish and then replays its outcome instead of
recomputing it. Waiting is the point: the alternative — returning immediately —
cannot tell "already done" from "in flight", which is the case that duplicates.

This is a different axis from ``application/idempotency.py::run_idempotent``. That
one de-duplicates an HTTP request by its caller-supplied ``Idempotency-Key`` inside
the admission transaction, and by the time a worker runs, the key is already
completed with the *admission* response (``202 queued``). Replaying it would hand
back the acceptance envelope, never the worker's outcome. The two compose: the key
stops a second job from being created, this guard stops one job from running twice.

Bodies that already hold a domain-row lock and guard on a domain terminal state —
``backtest_engine`` (run row), ``agent_executor`` (runtime + task rows),
``create_package`` (request root + ``job.status``) — answer both questions through
that lock and do not call this helper.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import JOB_TERMINAL_STATES
from entropia.infrastructure.postgres.models import Job


def terminal_replay_ref(job: Job) -> dict[str, Any]:
    """The durable outcome a redelivered terminal job replays.

    ``result_ref`` verbatim when the body recorded one (every durable body writes
    it on its terminal path), else a minimal reference — a terminal job with no
    recorded result is still terminal, and inventing a richer body would be a
    fabricated outcome.
    """
    if isinstance(job.result_ref, dict):
        return dict(job.result_ref)
    return {"job_id": job.job_id, "status": str(job.status)}


async def claim_job_for_delivery(
    session: AsyncSession, job_id: str
) -> tuple[Job, dict[str, Any] | None]:
    """Lock the durable job row; report an already-terminal delivery as a replay.

    Returns ``(job, None)`` when this delivery owns the job and must run the body,
    or ``(job, replay)`` when the job already reached a terminal status and the
    body must write nothing and return ``replay``.

    Raises ``ValueError`` when the row does not exist — the same failure the
    bodies raised before this helper existed, so a genuinely missing job still
    escapes into the dramatiq retry path rather than being silently swallowed.
    """
    job = await session.get(Job, job_id, with_for_update=True)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found.")
    if job.status in JOB_TERMINAL_STATES:
        return job, terminal_replay_ref(job)
    return job, None


__all__ = ["claim_job_for_delivery", "terminal_replay_ref"]
