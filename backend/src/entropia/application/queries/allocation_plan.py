"""Portfolio / Equity Allocation read-side queries (doc 13 §3.3, §7, §9).

Read-only: resolve the composition's draft projection (default independent draft
when no plan exists yet), the candidate item picker (unrepresented compatible
composition items, §3.3/§14#8), and the non-destructive Sync-From-Mainboard merge
preview (§10.2 Flow D — nothing is applied here; a destructive apply requires an
explicit PUT with the merged entries, §14#9).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import PortfolioAllocationEntry
from entropia.infrastructure.postgres.repositories import allocation as alloc_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.shared.errors import CompositionNotFoundError


async def get_allocation_draft(
    session: AsyncSession, actor: Actor, *, composition_id: str
) -> dict[str, Any]:
    """Return the draft projection + candidate items + concurrency row_version."""
    require_authenticated(actor)
    await _load_workspace_for_view(session, actor, composition_id)

    plan = await alloc_repo.get_plan_for_workspace(session, composition_id)
    items = await mb_repo.list_active_items(session, composition_id)
    # The persisted allocation entry binds by composition_item_id only (§8.2) and
    # carries no human name of its own; resolve each row's server-owned display
    # label from the composition item here so the browser NEVER reconstructs a
    # name from the raw mbi_ id (audit P-11 / F-07). Missing (soft-deleted /
    # detached) items fall back to None → the client shows the item-kind label.
    label_by_item = {item.item_id: item.display_label_override for item in items}

    if plan is None:
        draft: dict[str, Any] = {
            "enabled": False,
            "initial_capital": None,
            "compounding_mode": None,
            "reserve_cash_percent": None,
            "max_total_exposure_percent": None,
            "conflict_policy": None,
            "entries": [],
        }
        return {
            "composition_id": composition_id,
            "plan_id": None,
            "current_revision_id": None,
            "row_version": 0,
            "draft": draft,
            "candidate_items": [_candidate(item) for item in items],
        }

    entries = await alloc_repo.list_entries(session, plan.plan_id)
    represented = {e.composition_item_id for e in entries}
    return {
        "composition_id": composition_id,
        "plan_id": plan.plan_id,
        "current_revision_id": plan.current_revision_id,
        "row_version": plan.row_version,
        "draft": _draft_projection(plan, entries, label_by_item),
        "candidate_items": [_candidate(item) for item in items if item.item_id not in represented],
    }


async def sync_preview(
    session: AsyncSession, actor: Actor, *, composition_id: str
) -> dict[str, Any]:
    """Non-destructive Sync-From-Mainboard merge preview (doc 13 §10.2 Flow D)."""
    require_authenticated(actor)
    await _load_workspace_for_view(session, actor, composition_id)

    plan = await alloc_repo.get_plan_for_workspace(session, composition_id)
    items = await mb_repo.list_active_items(session, composition_id)
    item_ids = {item.item_id for item in items}
    label_by_item = {item.item_id: item.display_label_override for item in items}
    entries = await alloc_repo.list_entries(session, plan.plan_id) if plan is not None else []
    entry_ids = {e.composition_item_id for e in entries}

    retained = [
        _entry_projection(e, label_by_item) for e in entries if e.composition_item_id in item_ids
    ]
    # A missing entry's item is gone from the composition, so its label resolves
    # to None (label_by_item.get) → the client renders the item-kind label.
    missing = [
        _entry_projection(e, label_by_item)
        for e in entries
        if e.composition_item_id not in item_ids
    ]
    new_candidates = [_candidate(item) for item in items if item.item_id not in entry_ids]

    return {
        "composition_id": composition_id,
        "retained": retained,
        "missing": missing,
        "new_candidates": new_candidates,
        # A removal of previously-planned entries is destructive and must be
        # explicitly confirmed by a follow-up PUT (§14#9); a preview never mutates.
        "requires_confirmation": bool(missing),
    }


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


async def _load_workspace_for_view(
    session: AsyncSession, actor: Actor, composition_id: str
) -> None:
    workspace = await mb_repo.get_workspace(session, composition_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    ensure_can_view(actor, owner_principal_id=workspace.owner_principal_id, visibility="private")


def _draft_projection(
    plan: Any,
    entries: list[PortfolioAllocationEntry],
    label_by_item: dict[str, str | None],
) -> dict[str, Any]:
    initial_capital = None
    if plan.initial_capital_amount is not None and plan.initial_capital_currency is not None:
        initial_capital = {
            "amount": str(plan.initial_capital_amount),
            "currency": str(plan.initial_capital_currency),
        }
    return {
        "enabled": plan.enabled,
        "initial_capital": initial_capital,
        "compounding_mode": (
            str(plan.compounding_mode) if plan.compounding_mode is not None else None
        ),
        "reserve_cash_percent": (
            str(plan.reserve_cash_percent) if plan.reserve_cash_percent is not None else None
        ),
        "max_total_exposure_percent": (
            str(plan.max_total_exposure_percent)
            if plan.max_total_exposure_percent is not None
            else None
        ),
        "conflict_policy": (
            str(plan.conflict_policy) if plan.conflict_policy is not None else None
        ),
        "draft_fingerprint": plan.draft_fingerprint,
        "entries": [_entry_projection(e, label_by_item) for e in entries],
    }


def _entry_projection(
    entry: PortfolioAllocationEntry, label_by_item: dict[str, str | None]
) -> dict[str, Any]:
    return {
        "entry_id": entry.entry_id,
        "composition_item_id": entry.composition_item_id,
        "item_type": str(entry.item_type),
        "active": entry.active,
        "equity_share_percent": (
            str(entry.equity_share_percent) if entry.equity_share_percent is not None else None
        ),
        "position_index": entry.position_index,
        # Server-owned human name of the bound composition item (None when the
        # item is gone); the client shows it as the primary label and keeps the
        # composition_item_id as a secondary binding key only (audit P-11 / F-07).
        "display_label_override": label_by_item.get(entry.composition_item_id),
    }


def _candidate(item: Any) -> dict[str, Any]:
    return {
        "composition_item_id": item.item_id,
        "item_type": str(item.item_kind),
        "work_object_root_id": item.work_object_root_id,
        "is_enabled": item.is_enabled,
        "position_index": item.position_index,
        "display_label_override": item.display_label_override,
    }


__all__ = ["get_allocation_draft", "sync_preview"]
