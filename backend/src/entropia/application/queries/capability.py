"""Future Dev read models (Stage 7b, doc 22 §5, §7, §8).

Read-only registry projections: the capability list/detail every client uses
to refresh state, and the Graphic View placeholder overview. The overview is a
QUERY — it renders the static doc-22 §4.1 copy plus the server-side lifecycle
state; it never prepares chart data, starts a job or fakes progress (CR-09)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.capability.baseline import (
    GRAPHIC_VIEW_CARDS,
    GRAPHIC_VIEW_INTRO,
    STATE_MESSAGES,
)
from entropia.domain.capability.enums import GRAPHIC_VIEW, OPERATIONAL_STATES
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.infrastructure.postgres.models import FutureCapability
from entropia.infrastructure.postgres.repositories import capability as capability_repo
from entropia.shared.errors import CapabilityNotFoundError


def _capability_view(capability: FutureCapability) -> dict[str, Any]:
    state = capability.lifecycle_state
    return {
        "capability_key": capability.capability_key,
        "title": capability.title,
        "menu_path": capability.menu_path,
        "lifecycle_state": state.value,
        "is_operational": state in OPERATIONAL_STATES,
        "ui_surface_version": capability.ui_surface_version,
        "domain_contract_version": capability.domain_contract_version,
        "registry_version": capability.registry_version,
        "enabled_at": capability.enabled_at.isoformat() if capability.enabled_at else None,
        "retirement_at": (
            capability.retirement_at.isoformat() if capability.retirement_at else None
        ),
        "status_message": STATE_MESSAGES[state],
    }


async def list_capabilities(session: AsyncSession, actor: Actor) -> dict[str, Any]:
    """GET /capabilities (doc 22 §8): the client may cache the display state,
    but the server re-checks before any command dispatch."""
    require_authenticated(actor)
    rows = await capability_repo.list_capabilities(session)
    return {"capabilities": [_capability_view(row) for row in rows], "count": len(rows)}


async def get_capability(
    session: AsyncSession, actor: Actor, *, capability_key: str
) -> dict[str, Any]:
    """GET /capabilities/{key} (doc 22 §8): detail incl. the dependency
    snapshot and the last transition provenance."""
    require_authenticated(actor)
    capability = await capability_repo.get_capability_by_key(session, capability_key)
    if capability is None:
        raise CapabilityNotFoundError()
    return {
        **_capability_view(capability),
        "dependency_snapshot": capability.dependency_snapshot or {},
        "changed_by_actor_id": capability.changed_by_actor_id,
        "change_reason": capability.change_reason,
    }


async def get_graphic_view_overview(session: AsyncSession, actor: Actor) -> dict[str, Any]:
    """GET /future-dev/graphic_view/overview (doc 22 §4.1, §8, FD-01/03): the
    static intro + six future cards + the server-side registry state. No chart
    request, no View Dataset job, no marker computation, no persistence."""
    require_authenticated(actor)
    capability = await capability_repo.get_capability_by_key(session, GRAPHIC_VIEW)
    if capability is None:
        raise CapabilityNotFoundError()
    state = capability.lifecycle_state
    return {
        "capability_key": capability.capability_key,
        "title": capability.title,
        "lifecycle_state": state.value,
        "is_operational": state in OPERATIONAL_STATES,
        "registry_version": capability.registry_version,
        "intro": GRAPHIC_VIEW_INTRO,
        "cards": [dict(card) for card in GRAPHIC_VIEW_CARDS],
        "status_message": STATE_MESSAGES[state],
    }


__all__ = ["get_capability", "get_graphic_view_overview", "list_capabilities"]
