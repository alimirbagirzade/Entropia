"""Audit rows that must SURVIVE the request unit-of-work rollback (O-04).

Every command in this codebase runs inside ONE transaction supplied by the request
dependency and never commits it (``apps.api.deps.TransactionBoundaryMiddleware``
commits on 2xx, rolls back on >=4xx). That is correct for state, but it makes an
in-transaction audit row STRUCTURALLY unwritable for any decision that *is* the
rejection: the command raises, the middleware rolls back, and the audit row the
spec mandates disappears with it.

The mandatory-audit tables list several such events — doc 14 §12.2
``run_admission_rejected`` / ``readiness_access_denied`` and doc 07 §13.2
``precheck_stale`` are all reached only by raising — so they are written HERE, in
their OWN committed transaction, exactly mirroring the existing
``commands.auth._record_login_failure`` / ``_record_reauth_failure`` pattern
(injectable factory for tests, best-effort, structured log on failure).

Best-effort is deliberate: an audit-infrastructure hiccup must never convert a
typed 403/409/422 into a 500, so a write failure is logged (never silently
swallowed) and the original rejection still propagates.

Only REJECTION/DENIAL events belong here. An event on a path that commits
normally (``readiness.became_stale`` from a Mainboard mutation, the Pre-Check
``dependency_resolved`` rows from the worker) stays in the caller's transaction —
moving it out would break the transactional-outbox guarantee.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from entropia.domain.identity import Actor
from entropia.infrastructure.observability import get_logger
from entropia.infrastructure.postgres.engine import get_session_factory
from entropia.infrastructure.postgres.repositories import audit as audit_repo

log = get_logger(__name__)

AuditSessionFactory = async_sessionmaker[AsyncSession]


async def record_durable_audit(
    actor: Actor,
    *,
    event_kind: str,
    target_entity_id: str | None = None,
    target_entity_type: str | None = None,
    new_state: str | None = None,
    severity: str = "warning",
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Write one audit event in its OWN committed transaction.

    ``audit_session_factory`` defaults to the app factory; tests inject a factory
    bound to the test engine (the production ``lru_cache`` factory is not safe
    across test event loops).
    """
    factory = audit_session_factory or get_session_factory()
    try:
        async with factory() as audit_session:
            audit_repo.add_audit_event(
                audit_session,
                event_kind=event_kind,
                actor_principal_id=actor.principal_id,
                actor_kind=actor.actor_kind,
                target_entity_id=target_entity_id,
                target_entity_type=target_entity_type,
                new_state=new_state,
                severity=severity,
                reason=reason,
                correlation_id=actor.correlation_id or None,
                metadata=metadata,
            )
            await audit_session.commit()
    except Exception:
        log.exception(
            "durable_audit_write_failed",
            event_kind=event_kind,
            correlation_id=actor.correlation_id,
        )


__all__ = ["AuditSessionFactory", "record_durable_audit"]
