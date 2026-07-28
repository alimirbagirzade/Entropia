"""Composition-scoped Result access resolution (doc 16 §2; finding O-14).

The DB-bound half of ``domain/backtest/result_visibility.py``: it resolves the
``resource_share`` grantee facts the pure predicate needs and mirrors that same
predicate in SQL so the history list filters INSIDE the query — the
``has_more``/cursor pair must count the authorized set, never a post-filtered
page (doc 16 §9.3).

Every Result read surface routes through exactly one of the two entry points so
list, detail, compare, metrics and artifacts cannot drift apart:

* ``visible_composition_stmt`` — the list predicate (Results History index).
* ``ensure_can_view_composition`` — the per-result re-check doc 16 §2 requires of
  detail/compare ("the detail/compare endpoints additionally re-evaluate
  can_view"): having seen a card in a list is never authorization.

Grants are read from the SAME generic ``resource_share`` table Package sharing
writes (GAP-17) — ``resource_type='mainboard_workspace'``, active grants only
(``revoked_at IS NULL``), so a revoked grant drops the result out of the index on
the next query with no extra bookkeeping.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.result_visibility import (
    LAB_SCOPE_ROLES,
    ensure_can_view_result_composition,
)
from entropia.domain.identity import Actor
from entropia.domain.identity import policy as identity_policy
from entropia.domain.lifecycle.enums import DeletionState, VisibilityScope
from entropia.domain.mainboard.enums import WorkspaceKind
from entropia.domain.sharing import ShareResourceType
from entropia.infrastructure.postgres.models import EntityRegistry, MainboardWorkspace
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import resource_share as share_repo
from entropia.shared.errors import CompositionNotFoundError

RESOURCE_TYPE = str(ShareResourceType.COMPOSITION)


async def shared_composition_ids(session: AsyncSession, actor: Actor) -> set[str]:
    """Composition ids explicitly shared with this actor (empty when none).

    Mirrors ``library._viewer_shared_ids``: ONE set lookup per request, then a
    pure SQL ``IN`` — never a per-row share probe.
    """
    if actor.principal_id is None:
        return set()
    return await share_repo.shared_resource_ids(
        session,
        grantee_principal_id=actor.principal_id,
        resource_type=RESOURCE_TYPE,
    )


def visible_composition_stmt(
    stmt: Select[Any], actor: Actor, *, shared_ids: set[str]
) -> Select[Any]:
    """Restrict a statement already joined to ``EntityRegistry`` to readable rows.

    The Agent-research lab scope needs the composition's ``workspace_kind``, so the
    detail table is joined ONLY for the roles that scope applies to. The join is an
    OUTER join on purpose: a composition whose detail row is missing must still be
    listed for its owner/Admin (a missing detail is a repair gap, not a reason to
    silently drop an owner's own evidence row).
    """
    if actor.is_admin:
        return stmt
    conditions = [EntityRegistry.owner_principal_id == actor.principal_id]
    if shared_ids:
        conditions.append(EntityRegistry.entity_id.in_(shared_ids))
    if actor.role in LAB_SCOPE_ROLES:
        stmt = stmt.outerjoin(
            MainboardWorkspace, MainboardWorkspace.entity_id == EntityRegistry.entity_id
        )
        conditions.append(MainboardWorkspace.workspace_kind == WorkspaceKind.AGENT_RESEARCH)
    return stmt.where(or_(*conditions))


async def ensure_can_view_composition(
    session: AsyncSession, actor: Actor, workspace_entity_id: str
) -> None:
    """Re-evaluate read access for ONE composition (detail / compare / artifacts).

    A missing or soft-deleted composition is a metadata-free ``CompositionNotFound``
    before any policy branch, so an unauthorized caller cannot distinguish "does not
    exist" from "not yours" (doc 16 §11 generic RESULT_NOT_AVAILABLE).
    """
    workspace = await mb_repo.get_workspace(session, workspace_entity_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    # Fast path: owner/Admin is decidable from the root alone, so the common read
    # keeps exactly the round-trip count it had before O-14 — only a non-owner pays
    # for the detail + grant lookups.
    if identity_policy.can_view(
        actor,
        owner_principal_id=workspace.owner_principal_id,
        visibility=str(VisibilityScope.PRIVATE),
    ):
        return
    detail = await mb_repo.get_workspace_detail(session, workspace_entity_id)
    grantees = await share_repo.active_grantee_ids(
        session, resource_type=RESOURCE_TYPE, resource_id=workspace_entity_id
    )
    ensure_can_view_result_composition(
        actor,
        owner_principal_id=workspace.owner_principal_id,
        workspace_kind=None if detail is None else str(detail.workspace_kind),
        shared_principal_ids=grantees,
    )


__all__ = [
    "RESOURCE_TYPE",
    "ensure_can_view_composition",
    "shared_composition_ids",
    "visible_composition_stmt",
]
