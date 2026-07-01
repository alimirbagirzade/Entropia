"""Strategy read-side queries (doc 02 §7, §9; DOMAIN_MODEL §2.3).

Authentication-gated: a Guest is rejected with 401 before any read. An
authenticated non-owner (non-Admin) that targets another actor's private strategy
gets 403 (``can_view`` with ``visibility='private'``). Drafts and revisions are
private to the strategy owner in Stage 3b (no strategy sharing surface yet).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_view, require_authenticated
from entropia.infrastructure.postgres.repositories import strategy as strat_repo
from entropia.shared.errors import (
    StrategyDraftNotFoundError,
    StrategyNotFoundError,
    StrategyRevisionNotFoundError,
)


async def get_strategy_draft(session: AsyncSession, actor: Actor, draft_id: str) -> dict[str, Any]:
    """Return a mutable draft's current editor state (owner/Admin only)."""
    require_authenticated(actor)
    draft = await strat_repo.get_strategy_draft(session, draft_id)
    if draft is None:
        raise StrategyDraftNotFoundError(f"Strategy draft '{draft_id}' not found.")
    owner = await _owner_of(session, draft.strategy_root_id)
    ensure_can_view(actor, owner_principal_id=owner, visibility="private")
    return {
        "draft_id": draft.draft_id,
        "strategy_root_id": draft.strategy_root_id,
        "payload": draft.payload,
        "is_dirty": draft.is_dirty,
        "row_version": draft.row_version,
        "last_saved_revision_id": draft.last_saved_revision_id,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


async def get_strategy(session: AsyncSession, actor: Actor, root_id: str) -> dict[str, Any]:
    """Return the strategy root header + current revision pointer (owner/Admin)."""
    require_authenticated(actor)
    detail = await strat_repo.get_strategy_root(session, root_id)
    registry = await strat_repo.get_strategy_registry_root(session, root_id)
    if detail is None or registry is None:
        raise StrategyNotFoundError(f"Strategy '{root_id}' not found.")
    ensure_can_view(actor, owner_principal_id=registry.owner_principal_id, visibility="private")
    return {
        "strategy_root_id": detail.entity_id,
        "display_name": detail.display_name,
        "lifecycle_state": str(detail.lifecycle_state),
        "current_revision_id": detail.current_revision_id,
        "current_row_version": detail.current_row_version,
        "rationale_family_id": detail.rationale_family_id,
        "owner_principal_id": registry.owner_principal_id,
        "deletion_state": str(registry.deletion_state),
    }


async def get_strategy_revision(
    session: AsyncSession, actor: Actor, revision_id: str
) -> dict[str, Any]:
    """Return an immutable revision + its pinned dependency references (owner/Admin)."""
    require_authenticated(actor)
    revision = await strat_repo.get_strategy_revision(session, revision_id)
    if revision is None:
        raise StrategyRevisionNotFoundError(f"Strategy revision '{revision_id}' not found.")
    owner = await _owner_of(session, revision.entity_id)
    ensure_can_view(actor, owner_principal_id=owner, visibility="private")
    references = await strat_repo.list_references(session, revision_id)
    return {
        "strategy_revision_id": revision.revision_id,
        "strategy_root_id": revision.entity_id,
        "revision_number": revision.revision_number,
        "config_hash": revision.config_hash,
        "validation_status": str(revision.validation_status),
        "lifecycle_snapshot": revision.lifecycle_snapshot,
        "family_snapshot": revision.family_snapshot,
        "payload": revision.payload,
        "references": [
            {
                "referenced_entity_type": str(ref.referenced_entity_type),
                "dependency_role": str(ref.dependency_role),
                "referenced_root_id": ref.referenced_root_id,
                "referenced_revision_id": ref.referenced_revision_id,
                "referenced_content_hash": ref.referenced_content_hash,
                "position_in_graph": ref.position_in_graph,
            }
            for ref in references
        ],
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
    }


async def list_strategy_revisions(
    session: AsyncSession, actor: Actor, root_id: str, *, limit: int = 100
) -> list[dict[str, Any]]:
    """Return the revision history (newest first) for a strategy (owner/Admin)."""
    require_authenticated(actor)
    detail = await strat_repo.get_strategy_root(session, root_id)
    registry = await strat_repo.get_strategy_registry_root(session, root_id)
    if detail is None or registry is None:
        raise StrategyNotFoundError(f"Strategy '{root_id}' not found.")
    ensure_can_view(actor, owner_principal_id=registry.owner_principal_id, visibility="private")
    revisions = await strat_repo.list_strategy_revisions(session, root_id, limit=limit)
    return [
        {
            "strategy_revision_id": rev.revision_id,
            "revision_number": rev.revision_number,
            "config_hash": rev.config_hash,
            "validation_status": str(rev.validation_status),
            "created_at": rev.created_at.isoformat() if rev.created_at else None,
        }
        for rev in revisions
    ]


async def _owner_of(session: AsyncSession, strategy_root_id: str | None) -> str | None:
    if strategy_root_id is None:
        return None
    registry = await strat_repo.get_strategy_registry_root(session, strategy_root_id)
    return registry.owner_principal_id if registry is not None else None


__all__ = [
    "get_strategy",
    "get_strategy_draft",
    "get_strategy_revision",
    "list_strategy_revisions",
]
