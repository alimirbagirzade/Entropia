"""Operator recovery command: re-dispatch stuck ``data``-queue jobs (INF-03, doc 20 §6).

A durable ``data``-queue job whose broker message was lost sits QUEUED forever —
the scheduler recovers it back to QUEUED but does not auto-redeliver the
multi-actor ``data`` queue (it cannot know which of the four actors to send). This
Admin-only command lists such rows past the redeliver grace window, resolves each
to its actor via the payload ``job_kind`` discriminator, and returns the routable
set for the caller to dispatch (the route sends the actors after the tx, mirroring
the other worker routes). Un-routable legacy rows (no ``job_kind``) are counted,
never guessed. The action is audited once as an operator recovery event.

Redelivery is inherently safe: the durable row is untouched (it stays QUEUED) and
every data-plane worker is redelivery-idempotent, so a double send is a no-op.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.jobs.data_queue import list_redeliverable_data_jobs
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_admin_panel
from entropia.infrastructure.postgres.repositories import audit as audit_repo

_JOB_TARGET = "job"
_EVENT_KIND = "data_queue.redelivery_requested"


async def redeliver_data_queue_jobs(
    session: AsyncSession,
    actor: Actor,
    *,
    grace_seconds: int,
) -> dict[str, Any]:
    """List + resolve stuck ``data``-queue jobs for operator re-dispatch. Does not
    commit (the request scope commits) and does not send actors (the route does)."""
    require_admin_panel(actor)

    candidates = await list_redeliverable_data_jobs(session, grace_seconds=grace_seconds)
    routable = [
        {"job_kind": kind, "job_id": job_id} for kind, job_id in candidates if kind is not None
    ]
    skipped_unknown_kind = sum(1 for kind, _ in candidates if kind is None)

    summary = {
        "scanned": len(candidates),
        "redeliverable": routable,
        "skipped_unknown_kind": skipped_unknown_kind,
    }

    audit_repo.add_audit_event(
        session,
        event_kind=_EVENT_KIND,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_type=_JOB_TARGET,
        correlation_id=actor.correlation_id,
        metadata={
            "scanned": summary["scanned"],
            "routable": len(routable),
            "skipped_unknown_kind": skipped_unknown_kind,
        },
    )
    audit_repo.add_outbox_event(
        session,
        event_type=_EVENT_KIND,
        resource_type=_JOB_TARGET,
        resource_id=None,
        payload={
            "scanned": summary["scanned"],
            "routable": len(routable),
            "skipped_unknown_kind": skipped_unknown_kind,
        },
        correlation_id=actor.correlation_id,
    )

    return summary


__all__ = ["redeliver_data_queue_jobs"]
