"""Portfolio / Equity Allocation commands (doc 13 §7, §8, §10, §11).

Every mutating command runs in ONE transaction supplied by the request dependency
and NEVER commits. Shape mirrors the Strategy/Mainboard commands: authorization +
pure input validation OUTSIDE the idempotent body -> ``run_idempotent`` op {
optimistic-concurrency (``expected_row_version`` via
``session.refresh(with_for_update=True)``) BEFORE any mutation -> repo mutation ->
audit + outbox }.

Binding rules (Stage 4a acceptance, doc 13 §13/§14):

* The plan is 1:1 with a Mainboard composition (``mainboard_workspace``); the
  autosave PUT upserts the mutable draft (no visible Save button, §7.1).
* Entries bind by ``composition_item_id`` (= ``mainboard_working_item.item_id``),
  NEVER by name/DOM/Type; ``item_type`` is server-DERIVED from the composition item.
  An unknown/foreign item on the PUT -> DEPENDENCY_BLOCKED (422); an item that was
  valid but has since left the composition is preserved as an orphan and flagged
  ITEM_UNAVAILABLE at validation (§4.1).
* Money/percent are NUMERIC (Decimal), never float (§13).
* ``expected_row_version`` is a live optimistic-concurrency token; a stale
  PUT/revision -> ALLOCATION_DRAFT_CONFLICT (409), never last-write-wins (§10.1).
* Validate != Plan Revision != Run. Validate returns an immutable report id;
  a revision is created only from a blocker-free enabled draft (§8.5).
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.domain.allocation.config import PortfolioAllocationConfigV1
from entropia.domain.allocation.rules import (
    AllocationItemRef,
    canonical_config,
    compute_config_hash,
    has_blockers,
    validate_allocation,
)
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_edit, ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.infrastructure.postgres.models import EntityRegistry, PortfolioAllocationEntry
from entropia.infrastructure.postgres.repositories import allocation as alloc_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.shared.errors import (
    AllocationDependencyBlockedError,
    AllocationDraftConflictError,
    AllocationHasBlockersError,
    AllocationPlanNotFoundError,
    AllocationValidationFailedError,
    CompositionNotFoundError,
)
from entropia.shared.ids import new_id

_PLAN_TARGET = "portfolio_allocation_plan"
_BLOCKER = "blocker"
_WARNING = "warning"


# --------------------------------------------------------------------------- #
# PUT draft (autosave upsert)                                                  #
# --------------------------------------------------------------------------- #


async def upsert_allocation_draft(
    session: AsyncSession,
    actor: Actor,
    *,
    composition_id: str,
    expected_row_version: int | None,
    enabled: bool = False,
    initial_capital: dict[str, Any] | None = None,
    compounding_mode: str | None = None,
    reserve_cash_percent: str | None = None,
    entries: list[dict[str, Any]] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Upsert the composition's mutable allocation draft (doc 13 §7, §7.2)."""
    require_authenticated(actor)
    await _load_workspace_for_edit(session, actor, composition_id)
    raw_entries = entries or []
    config = _parse_config(
        {
            "enabled": enabled,
            "initial_capital": initial_capital,
            "compounding_mode": compounding_mode,
            "reserve_cash_percent": reserve_cash_percent,
            "entries": raw_entries,
        }
    )

    async def _op() -> dict[str, Any]:
        plan = await alloc_repo.get_plan_for_workspace(session, composition_id)
        previous_enabled = plan.enabled if plan is not None else False
        current_entries = (
            await alloc_repo.list_entries(session, plan.plan_id) if plan is not None else []
        )
        active = await _active_items(session, composition_id)
        resolved = _resolve_entries(config, active, current_entries)
        canonical = _canonical_draft(config, resolved)
        fingerprint = _hash_dict(canonical)
        amount = config.initial_capital.amount if config.initial_capital else None
        currency = config.initial_capital.currency if config.initial_capital else None

        if plan is None:
            if expected_row_version not in (None, 0):
                raise AllocationDraftConflictError()
            plan = await alloc_repo.create_plan(
                session,
                workspace_entity_id=composition_id,
                created_by_principal_id=actor.principal_id,
                enabled=config.enabled,
                initial_capital_amount=amount,
                initial_capital_currency=currency,
                compounding_mode=config.compounding_mode,
                reserve_cash_percent=config.reserve_cash_percent,
                draft_fingerprint=fingerprint,
            )
        else:
            await session.refresh(plan, with_for_update=True)
            if expected_row_version is None or plan.row_version != expected_row_version:
                raise AllocationDraftConflictError()
            plan.enabled = config.enabled
            plan.initial_capital_amount = amount
            plan.initial_capital_currency = currency
            plan.compounding_mode = config.compounding_mode
            plan.reserve_cash_percent = config.reserve_cash_percent
            plan.draft_fingerprint = fingerprint
            plan.row_version += 1

        await alloc_repo.replace_entries(session, plan_id=plan.plan_id, entries=resolved)

        item_refs = _item_refs_from_resolved(resolved, active)
        issues, derived = validate_allocation(config, item_refs=item_refs)

        if config.enabled != previous_enabled:
            _audit_and_outbox(
                session,
                actor,
                event_kind="portfolio_allocation.enabled_changed",
                target_entity_id=plan.plan_id,
                previous_state=str(previous_enabled),
                new_state=str(config.enabled),
                payload={"composition_id": composition_id, "enabled": config.enabled},
            )
        _audit_and_outbox(
            session,
            actor,
            event_kind="portfolio_allocation.draft_changed",
            target_entity_id=plan.plan_id,
            new_state=str(plan.row_version),
            payload={
                "composition_id": composition_id,
                "enabled": config.enabled,
                "entry_count": len(resolved),
                "draft_fingerprint": fingerprint,
            },
        )
        return {
            "composition_id": composition_id,
            "plan_id": plan.plan_id,
            "enabled": config.enabled,
            "row_version": plan.row_version,
            "draft_fingerprint": fingerprint,
            "inline_issues": [i.as_dict() for i in issues],
            "derived": derived.as_dict() if derived is not None else None,
            "readiness_invalidated": True,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "upsert_allocation_draft",
            "composition_id": composition_id,
            "expected_row_version": expected_row_version,
            "enabled": enabled,
            "initial_capital": initial_capital,
            "compounding_mode": compounding_mode,
            "reserve_cash_percent": reserve_cash_percent,
            "entries": raw_entries,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Validate (no revision)                                                       #
# --------------------------------------------------------------------------- #


async def validate_allocation_draft(
    session: AsyncSession,
    actor: Actor,
    *,
    composition_id: str,
) -> dict[str, Any]:
    """Validate the current draft; return an immutable report (doc 13 §7, §11.2).

    Rerun = new ``validation_report_id`` (§11.1). No plan revision or run is created.
    """
    require_authenticated(actor)
    await _load_workspace_for_view(session, actor, composition_id)
    plan = await alloc_repo.get_plan_for_workspace(session, composition_id)
    report_id = new_id("parpt")

    if plan is None:
        _audit_and_outbox(
            session,
            actor,
            event_kind="portfolio_allocation.validated",
            target_entity_id=composition_id,
            payload={
                "validation_report_id": report_id,
                "composition_id": composition_id,
                "enabled": False,
                "valid": True,
            },
        )
        return {
            "validation_report_id": report_id,
            "composition_id": composition_id,
            "enabled": False,
            "state": "NOT_SELECTED",
            "valid": True,
            "issues": [],
            "warnings": [],
            "derived": None,
            "config_hash": None,
        }

    entries = await alloc_repo.list_entries(session, plan.plan_id)
    config = _plan_to_config(plan, entries)
    active = await _active_items(session, composition_id)
    item_refs = {
        e.composition_item_id: AllocationItemRef(
            kind=e.item_type, available=e.composition_item_id in active
        )
        for e in entries
    }
    issues, derived = validate_allocation(config, item_refs=item_refs)
    config_hash = compute_config_hash(config)
    valid = not has_blockers(issues)
    warnings = [i.as_dict() for i in issues if str(i.severity) == _WARNING]

    _audit_and_outbox(
        session,
        actor,
        event_kind="portfolio_allocation.validated",
        target_entity_id=plan.plan_id,
        payload={
            "validation_report_id": report_id,
            "composition_id": composition_id,
            "config_hash": config_hash,
            "valid": valid,
            "blocker_count": sum(1 for i in issues if str(i.severity) == _BLOCKER),
            "warning_count": len(warnings),
        },
    )
    return {
        "validation_report_id": report_id,
        "composition_id": composition_id,
        "enabled": config.enabled,
        "state": _readiness_state(config.enabled, issues),
        "valid": valid,
        "issues": [i.as_dict() for i in issues],
        "warnings": warnings,
        "derived": derived.as_dict() if derived is not None else None,
        "config_hash": config_hash,
    }


# --------------------------------------------------------------------------- #
# Create plan revision (immutable)                                            #
# --------------------------------------------------------------------------- #


async def create_allocation_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    composition_id: str,
    expected_row_version: int | None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Turn a validated, blocker-free enabled draft into an immutable plan revision
    (doc 13 §7, §8.5, §11.2)."""
    require_authenticated(actor)
    await _load_workspace_for_edit(session, actor, composition_id)
    plan = await alloc_repo.get_plan_for_workspace(session, composition_id)
    if plan is None:
        raise AllocationPlanNotFoundError()

    async def _op() -> dict[str, Any]:
        await session.refresh(plan, with_for_update=True)
        if expected_row_version is None or plan.row_version != expected_row_version:
            raise AllocationDraftConflictError()

        entries = await alloc_repo.list_entries(session, plan.plan_id)
        config = _plan_to_config(plan, entries)
        if not config.enabled:
            raise AllocationValidationFailedError(
                "A plan revision can only be created in shared allocation mode (enabled=true).",
                details=[{"code": "ALLOCATION_NOT_ENABLED", "field": "enabled"}],
            )
        active = await _active_items(session, composition_id)
        item_refs = {
            e.composition_item_id: AllocationItemRef(
                kind=e.item_type, available=e.composition_item_id in active
            )
            for e in entries
        }
        issues, derived = validate_allocation(config, item_refs=item_refs)
        if has_blockers(issues):
            raise AllocationHasBlockersError(
                details=[i.as_dict() for i in issues if str(i.severity) == _BLOCKER]
            )

        config_hash = compute_config_hash(config)
        revision_no = await alloc_repo.max_revision_no(session, plan.plan_id) + 1
        source_version = plan.row_version
        revision = await alloc_repo.create_revision(
            session,
            plan_id=plan.plan_id,
            revision_no=revision_no,
            config=canonical_config(config),
            config_hash=config_hash,
            derived_amounts=derived.as_dict() if derived is not None else None,
            source_draft_row_version=source_version,
            created_by_principal_id=actor.principal_id,
        )
        plan.current_revision_id = revision.plan_revision_id
        plan.row_version += 1

        _audit_and_outbox(
            session,
            actor,
            event_kind="portfolio_allocation.revision_created",
            target_entity_id=plan.plan_id,
            target_revision_id=revision.plan_revision_id,
            payload={
                "plan_revision_id": revision.plan_revision_id,
                "revision_no": revision_no,
                "config_hash": config_hash,
                "source_draft_row_version": source_version,
            },
        )
        return {
            "composition_id": composition_id,
            "plan_id": plan.plan_id,
            "plan_revision_id": revision.plan_revision_id,
            "revision_no": revision_no,
            "config_hash": config_hash,
            "current_revision_id": revision.plan_revision_id,
            "row_version": plan.row_version,
            "derived": derived.as_dict() if derived is not None else None,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "create_allocation_revision",
            "composition_id": composition_id,
            "expected_row_version": expected_row_version,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Shared helpers                                                              #
# --------------------------------------------------------------------------- #


async def _load_workspace_for_edit(
    session: AsyncSession, actor: Actor, composition_id: str
) -> EntityRegistry:
    workspace = await mb_repo.get_workspace(session, composition_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    ensure_can_edit(actor, owner_principal_id=workspace.owner_principal_id)
    return workspace


async def _load_workspace_for_view(
    session: AsyncSession, actor: Actor, composition_id: str
) -> EntityRegistry:
    workspace = await mb_repo.get_workspace(session, composition_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    ensure_can_view(actor, owner_principal_id=workspace.owner_principal_id, visibility="private")
    return workspace


async def _active_items(session: AsyncSession, composition_id: str) -> dict[str, MainboardItemKind]:
    items = await mb_repo.list_active_items(session, composition_id)
    return {item.item_id: item.item_kind for item in items}


def _parse_config(raw: dict[str, Any]) -> PortfolioAllocationConfigV1:
    try:
        return PortfolioAllocationConfigV1.model_validate(raw)
    except PydanticValidationError as exc:
        details = [
            {
                "field": ".".join(str(p) for p in err.get("loc", ())),
                "issue": err.get("msg", ""),
            }
            for err in exc.errors()
        ]
        raise AllocationValidationFailedError(details=details) from exc


def _resolve_entries(
    config: PortfolioAllocationConfigV1,
    active: dict[str, MainboardItemKind],
    current_entries: list[PortfolioAllocationEntry],
) -> list[dict[str, Any]]:
    """Server-derive ``item_type`` + membership for each entry (doc 13 §8.2, §14#7).

    Resolvable now -> derive the current kind. Previously stored but no longer in
    the composition -> keep the prior kind (orphan, flagged at validation). Never
    seen (unknown/foreign) -> DEPENDENCY_BLOCKED.
    """
    prior = {e.composition_item_id: e.item_type for e in current_entries}
    resolved: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for entry in config.entries:
        cid = entry.composition_item_id
        if cid in active:
            item_type: MainboardItemKind = active[cid]
        elif cid in prior:
            item_type = prior[cid]
        else:
            blocked.append({"field": "entries", "composition_item_id": cid})
            continue
        resolved.append(
            {
                "composition_item_id": cid,
                "item_type": item_type,
                "active": entry.active,
                "equity_share_percent": entry.equity_share_percent,
            }
        )
    if blocked:
        raise AllocationDependencyBlockedError(details=blocked)
    return resolved


def _item_refs_from_resolved(
    resolved: list[dict[str, Any]], active: dict[str, MainboardItemKind]
) -> dict[str, AllocationItemRef]:
    return {
        entry["composition_item_id"]: AllocationItemRef(
            kind=entry["item_type"], available=entry["composition_item_id"] in active
        )
        for entry in resolved
    }


def _plan_to_config(
    plan: Any, entries: list[PortfolioAllocationEntry]
) -> PortfolioAllocationConfigV1:
    initial_capital = None
    if plan.initial_capital_amount is not None and plan.initial_capital_currency is not None:
        initial_capital = {
            "amount": str(plan.initial_capital_amount),
            "currency": str(plan.initial_capital_currency),
        }
    raw = {
        "enabled": plan.enabled,
        "initial_capital": initial_capital,
        "compounding_mode": str(plan.compounding_mode)
        if plan.compounding_mode is not None
        else None,
        "reserve_cash_percent": (
            str(plan.reserve_cash_percent) if plan.reserve_cash_percent is not None else None
        ),
        "entries": [
            {
                "composition_item_id": e.composition_item_id,
                "item_type": str(e.item_type),
                "active": e.active,
                "equity_share_percent": (
                    str(e.equity_share_percent) if e.equity_share_percent is not None else None
                ),
            }
            for e in entries
        ],
    }
    return PortfolioAllocationConfigV1.model_validate(raw)


def _canonical_draft(
    config: PortfolioAllocationConfigV1, resolved: list[dict[str, Any]]
) -> dict[str, Any]:
    """Canonical draft dict (server-derived item_types) used for the fingerprint."""
    initial_capital = None
    if config.initial_capital is not None:
        initial_capital = {
            "amount": str(config.initial_capital.amount),
            "currency": str(config.initial_capital.currency),
        }
    return {
        "enabled": config.enabled,
        "initial_capital": initial_capital,
        "compounding_mode": (
            str(config.compounding_mode) if config.compounding_mode is not None else None
        ),
        "reserve_cash_percent": (
            str(config.reserve_cash_percent) if config.reserve_cash_percent is not None else None
        ),
        "entries": [
            {
                "composition_item_id": e["composition_item_id"],
                "item_type": str(e["item_type"]),
                "active": e["active"],
                "equity_share_percent": (
                    str(e["equity_share_percent"])
                    if e["equity_share_percent"] is not None
                    else None
                ),
            }
            for e in resolved
        ],
    }


def _hash_dict(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _readiness_state(enabled: bool, issues: list[Any]) -> str:
    if not enabled:
        return "NOT_SELECTED"
    if has_blockers(issues):
        return "NOT_READY"
    if any(str(i.severity) == _WARNING for i in issues):
        return "READY_WITH_WARNINGS"
    return "READY"


def _audit_and_outbox(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    target_entity_id: str,
    target_revision_id: str | None = None,
    previous_state: str | None = None,
    new_state: str | None = None,
    payload: dict[str, Any],
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=target_entity_id,
        target_entity_type=_PLAN_TARGET,
        target_revision_id=target_revision_id,
        previous_state=previous_state,
        new_state=new_state,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type=event_kind,
        resource_type=_PLAN_TARGET,
        resource_id=target_entity_id,
        payload=payload,
        correlation_id=actor.correlation_id,
    )


__all__ = [
    "create_allocation_revision",
    "upsert_allocation_draft",
    "validate_allocation_draft",
]
