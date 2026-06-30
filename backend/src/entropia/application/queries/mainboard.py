"""Mainboard read-side query: the default workspace projection (doc 01 §4, §9).

The Mainboard is authentication-gated: a Guest gets no workspace at all — the
query raises UNAUTHENTICATED before resolving or auto-creating anything (AT#1, no
leak). For an authenticated actor the default workspace is resolved owner-scoped;
if none exists yet it is auto-created (FK-safe registry Root -> flush -> detail)
with a kind derived from the actor (``agent_research`` for an Agent, else
``human_default``). "One active default per human owner" is APP-ENFORCED here
(query-before-create) — there is no cross-table DB uniqueness constraint
(follow-up).

The item list is the ACTIVE projection: items whose work object root is
soft-deleted are filtered out server-side (they remain rows, but never appear),
ordered by ``position_index``. Readiness / latest-result are deliberate
placeholders (``not_ready`` / null), never fabricated values (L4).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.mainboard.enums import WorkspaceKind
from entropia.infrastructure.postgres.models import MainboardWorkingItem, MainboardWorkspace
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo


async def get_default_mainboard(session: AsyncSession, actor: Actor) -> dict[str, Any]:
    """Resolve (or auto-create) the actor's default Mainboard workspace projection.

    Guests are rejected with 401 before any read/create. The returned shape is the
    workspace header + the active item projection + readiness/result placeholders.
    """
    require_authenticated(actor)
    detail = await mb_repo.find_default_workspace(
        session, owner_principal_id=actor.principal_id or ""
    )
    if detail is None:
        detail = await _auto_create_default(session, actor)

    items = await mb_repo.list_active_items(session, detail.entity_id)
    return {
        "workspace_id": detail.entity_id,
        "workspace_kind": str(detail.workspace_kind),
        "composition_hash": detail.composition_hash,
        "row_version": detail.row_version,
        "items": [_item_projection(item) for item in items],
        "ready_summary": {"state": "not_ready", "report_id": None},
        "latest_result_summary": None,
    }


async def _auto_create_default(session: AsyncSession, actor: Actor) -> MainboardWorkspace:
    """Create the actor's default workspace (FK-safe Root -> flush -> detail)."""
    workspace_kind = WorkspaceKind.AGENT_RESEARCH if actor.is_agent else WorkspaceKind.HUMAN_DEFAULT
    _root, detail = await mb_repo.create_workspace(
        session,
        owner_principal_id=actor.principal_id,
        created_by_principal_id=actor.principal_id,
        workspace_kind=workspace_kind,
        title=None,
        is_default=True,
    )
    return detail


def _item_projection(item: MainboardWorkingItem) -> dict[str, Any]:
    return {
        "item_id": item.item_id,
        "item_kind": str(item.item_kind),
        "work_object_root_id": item.work_object_root_id,
        "pinned_revision_id": item.pinned_revision_id,
        "position_index": item.position_index,
        "is_enabled": item.is_enabled,
        "display_label_override": item.display_label_override,
        "row_version": item.row_version,
    }


__all__ = ["get_default_mainboard"]
