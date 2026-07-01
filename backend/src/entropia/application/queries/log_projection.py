"""Admin Logs read model (doc 19 §4.3, §5, §9.4, §13).

A filtered, newest-first, cursor-paginated projection over the immutable
``audit_events`` table — NOT a mutable log store and NOT the backtest-metrics table
the V18 prototype shows. Every entry point re-applies ``require_admin_panel`` (the
route guard is never the only check). The list never ships the whole history to the
browser: server-side filters + ``limit`` + opaque composite keyset cursor only. The
projection is append-only; there is no edit/delete path — a correction is a NEW
event linked by ``causation_event_id`` (doc 19 §11, §13).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.admin_panel.log_taxonomy import (
    LOG_EVENT_FAMILIES,
    decode_log_cursor,
    encode_log_cursor,
    event_family,
    family_kind_prefixes,
    normalize_actor_type,
    normalize_family,
    normalize_severity,
)
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_admin_panel
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import AuditEvent, EntityRegistry
from entropia.shared.errors import CursorInvalidError, NotFoundError

DEFAULT_LOG_LIMIT = 50
MAX_LOG_LIMIT = 100
MAX_QUERY_TEXT = 128
MAX_CORRELATION_LEN = 64
_CORRELATION_CHAIN_CAP = 200


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LOG_LIMIT
    return max(1, min(limit, MAX_LOG_LIMIT))


def _contains_any(tokens: list[str]) -> Any:
    return or_(*[func.lower(AuditEvent.event_kind).contains(t) for t in tokens])


def _family_predicate(family: str) -> Any:
    """SQL predicate that mirrors ``event_family`` EXACTLY (substring + first-match).

    A named family owns an event only when the kind contains one of its tokens AND
    contains no token of an EARLIER family — otherwise a kind like
    ``user.role_import_note`` (role_access, but contains ``import``) would leak into
    the ``data`` filter while its displayed family stays ``role_access``.
    ``system_other`` is the complement: no named token at all."""
    named = [f for f in LOG_EVENT_FAMILIES if f not in ("all", "system_other")]
    all_tokens = [t for fam in named for t in family_kind_prefixes(fam)]
    if family == "system_other":
        return and_(*[~func.lower(AuditEvent.event_kind).contains(t) for t in all_tokens])
    earlier = named[: named.index(family)]
    own = _contains_any(list(family_kind_prefixes(family)))
    earlier_tokens = [t for fam in earlier for t in family_kind_prefixes(fam)]
    if not earlier_tokens:
        return own
    return and_(own, *[~func.lower(AuditEvent.event_kind).contains(t) for t in earlier_tokens])


def _apply_filters(
    stmt: Select[Any],
    *,
    from_at: datetime | None,
    to_at: datetime | None,
    family: str,
    severity: str | None,
    actor_kind: Any,
    actor_id: str | None,
    resource_type: str | None,
    correlation_id: str | None,
    query_text: str | None,
) -> Select[Any]:
    if from_at is not None:
        stmt = stmt.where(AuditEvent.occurred_at >= from_at)
    if to_at is not None:
        stmt = stmt.where(AuditEvent.occurred_at <= to_at)
    if family != "all":
        stmt = stmt.where(_family_predicate(family))
    if severity is not None:
        stmt = stmt.where(AuditEvent.severity == severity)
    if actor_kind is not None:
        stmt = stmt.where(AuditEvent.actor_kind == actor_kind)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_principal_id == actor_id)
    if resource_type:
        stmt = stmt.where(AuditEvent.target_entity_type == resource_type)
    if correlation_id:
        # Exact-or-prefix, bounded length, no raw wildcard (doc 19 §6.2).
        stmt = stmt.where(func.lower(AuditEvent.correlation_id).startswith(correlation_id.lower()))
    if query_text:
        needle = query_text.lower()
        stmt = stmt.where(
            or_(
                func.lower(AuditEvent.event_kind).contains(needle),
                func.lower(AuditEvent.target_entity_id).contains(needle),
                func.lower(AuditEvent.reason).contains(needle),
            )
        )
    return stmt


def _apply_keyset(stmt: Select[Any], cursor: str | None) -> Select[Any]:
    """Newest-first ordering on ``(occurred_at, event_id)`` with a stable tie-break;
    the cursor carries the composite so pages never skip or repeat on equal times."""
    stmt = stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.event_id.desc())
    if cursor is None:
        return stmt
    occurred_at_iso, event_id = decode_log_cursor(cursor)
    try:
        last_at = datetime.fromisoformat(occurred_at_iso)
    except ValueError as exc:
        raise CursorInvalidError() from exc
    return stmt.where(
        or_(
            AuditEvent.occurred_at < last_at,
            and_(AuditEvent.occurred_at == last_at, AuditEvent.event_id < event_id),
        )
    )


def _row(event: AuditEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "event_kind": event.event_kind,
        "family": event_family(event.event_kind),
        "severity": event.severity,
        "actor_type": str(event.actor_kind),
        "actor_id": event.actor_principal_id,
        "subject_type": event.target_entity_type,
        "subject_id": event.target_entity_id,
        "correlation_id": event.correlation_id,
        "causation_event_id": event.causation_event_id,
        "message": event.reason or event.event_kind,
    }


async def list_log_events(
    session: AsyncSession,
    actor: Actor,
    *,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    family: str | None = None,
    severity: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    resource_type: str | None = None,
    correlation_id: str | None = None,
    query_text: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Admin-only, filtered, newest-first cursor page over immutable audit events."""
    require_admin_panel(actor)
    page_limit = _clamp_limit(limit)

    stmt = _apply_filters(
        select(AuditEvent),
        from_at=from_at,
        to_at=to_at,
        family=normalize_family(family),
        severity=normalize_severity(severity),
        actor_kind=normalize_actor_type(actor_type),
        actor_id=actor_id,
        resource_type=resource_type,
        correlation_id=(correlation_id or "")[:MAX_CORRELATION_LEN] or None,
        query_text=(query_text or "").strip()[:MAX_QUERY_TEXT] or None,
    )
    stmt = _apply_keyset(stmt, cursor).limit(page_limit + 1)

    rows = list((await session.execute(stmt)).scalars().all())
    has_more = len(rows) > page_limit
    page = rows[:page_limit]
    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        next_cursor = encode_log_cursor(
            occurred_at_iso=last.occurred_at.isoformat(), event_id=last.event_id
        )
    return {
        "data": [_row(r) for r in page],
        "meta": {"cursor": next_cursor, "has_more": has_more, "limit": page_limit},
    }


async def _subject_status(session: AsyncSession, event: AuditEvent) -> str | None:
    """Best-effort lifecycle of the event's subject: ``deleted`` if the registry row
    is soft-deleted/purged, ``active`` if present and active, ``None`` if unresolved
    (the event is retained either way — doc 19 §5, §11)."""
    if event.target_entity_id is None:
        return None
    reg = await session.get(EntityRegistry, event.target_entity_id)
    if reg is None:
        return None
    return "active" if reg.deletion_state == DeletionState.ACTIVE else "deleted"


async def get_log_event(session: AsyncSession, actor: Actor, *, event_id: str) -> dict[str, Any]:
    """Admin-only read-only event detail with correlation chain + causation ref.

    Never exposes an edit/delete/retry control or raw payload; only safe technical
    identifiers and stable references (doc 19 §5, §9.4, §13).
    """
    require_admin_panel(actor)
    event = await session.get(AuditEvent, event_id)
    if event is None:
        raise NotFoundError("This event is no longer available for detail view.")

    subject_status = await _subject_status(session, event)
    chain: list[dict[str, Any]] = []
    if event.correlation_id is not None:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.correlation_id == event.correlation_id)
            .order_by(AuditEvent.occurred_at.asc(), AuditEvent.event_id.asc())
            .limit(_CORRELATION_CHAIN_CAP)
        )
        chain = [_row(r) for r in (await session.execute(stmt)).scalars().all()]

    causation: dict[str, Any] | None = None
    if event.causation_event_id is not None:
        cause = await session.get(AuditEvent, event.causation_event_id)
        if cause is not None:
            causation = _row(cause)

    detail = _row(event)
    detail.update(
        {
            "previous_state": event.previous_state,
            "new_state": event.new_state,
            "reason": event.reason,
            "subject_status": subject_status,
            "subject_deleted": None if subject_status is None else subject_status == "deleted",
            "technical": {
                "trace_id": event.source_run_id,
                "job_id": event.source_task_id,
                "target_revision_id": event.target_revision_id,
            },
            "correlation_chain": chain,
            "causation_event": causation,
        }
    )
    return detail


__all__ = ["DEFAULT_LOG_LIMIT", "MAX_LOG_LIMIT", "get_log_event", "list_log_events"]
