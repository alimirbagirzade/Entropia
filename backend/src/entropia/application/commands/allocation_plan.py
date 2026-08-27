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
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.application.queries.allocation_currency import resolve_settlement_currencies
from entropia.domain.allocation.config import PortfolioAllocationConfigV1
from entropia.domain.allocation.enums import CrossItemConflictPolicy
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
    CrossItemConflictPolicyNotSelectableError,
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
    max_total_exposure_percent: str | None = None,
    conflict_policy: str | None = None,
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
            "max_total_exposure_percent": max_total_exposure_percent,
            "conflict_policy": conflict_policy,
            "entries": raw_entries,
        }
    )
    # B0 (G14 / GH #544, signed 2026-08-27): the write path is frozen for NET. THIS is the
    # freeze -- the ``Sev.BLOCKER`` flip in ``rules.py`` cannot be, because this is the only
    # function that writes ``plan.conflict_policy`` and it deliberately never consults
    # ``has_blockers`` (a draft may be invalid). Measured with ``ast``, not grep: the set
    # that writes the column and the set that enforces blockers are DISJOINT.
    #
    # The guard sits ABOVE the mutation and above ``run_idempotent`` on purpose: a refusal
    # must leave no row and no replayable idempotency envelope behind.
    #
    # It refuses the TOKEN, not "any blocker" -- an enabled plan always carries the
    # containment blocker in this build, so refusing blockers here would make shared
    # allocation entirely unsavable. And it lives here rather than in
    # ``config.py::_norm_conflict`` because ``_plan_to_config`` re-validates STORED rows
    # through that same model: refusing there would turn reading an existing NET plan into
    # a 500. Reading stays untouched; only new writes are frozen.
    if config.conflict_policy == CrossItemConflictPolicy.NET:
        raise CrossItemConflictPolicyNotSelectableError(
            details=[
                {
                    "field": "conflict_policy",
                    "submitted": str(CrossItemConflictPolicy.NET),
                    "supported": [
                        str(CrossItemConflictPolicy.KEEP_SEPARATE),
                        str(CrossItemConflictPolicy.BLOCK_OPPOSITE),
                    ],
                }
            ]
        )

    async def _op() -> dict[str, Any]:
        plan = await alloc_repo.get_plan_for_workspace(session, composition_id)
        previous_enabled = plan.enabled if plan is not None else False
        current_entries = (
            await alloc_repo.list_entries(session, plan.plan_id) if plan is not None else []
        )
        active, settlement = await _resolve_items(session, composition_id)
        resolved = _resolve_entries(config, active, current_entries)
        canonical = _canonical_draft(config, resolved)
        fingerprint = _hash_dict(canonical)
        amount = config.initial_capital.amount if config.initial_capital else None
        currency = config.initial_capital.currency if config.initial_capital else None

        if plan is None:
            if expected_row_version not in (None, 0):
                # The caller believes it is editing a draft that does not exist —
                # there is nothing to compare against, so ``current_draft`` is an
                # explicit null rather than a fabricated empty draft.
                raise _draft_conflict(
                    plan_id=None,
                    expected_row_version=expected_row_version,
                    current_row_version=0,
                    current_draft=None,
                    submitted_draft=canonical,
                )
            plan = await alloc_repo.create_plan(
                session,
                workspace_entity_id=composition_id,
                created_by_principal_id=actor.principal_id,
                enabled=config.enabled,
                initial_capital_amount=amount,
                initial_capital_currency=currency,
                compounding_mode=config.compounding_mode,
                reserve_cash_percent=config.reserve_cash_percent,
                max_total_exposure_percent=config.max_total_exposure_percent,
                conflict_policy=config.conflict_policy,
                draft_fingerprint=fingerprint,
            )
        else:
            await session.refresh(plan, with_for_update=True)
            if expected_row_version is None or plan.row_version != expected_row_version:
                # Flow E: "server current draft + changed paths". The entries are
                # re-read AFTER the lock so the compare view shows what is on the
                # server right now, not what was loaded before the refresh.
                server_entries = await alloc_repo.list_entries(session, plan.plan_id)
                raise _draft_conflict(
                    plan_id=plan.plan_id,
                    expected_row_version=expected_row_version,
                    current_row_version=plan.row_version,
                    current_draft=_stored_canonical_draft(plan, server_entries),
                    submitted_draft=canonical,
                )
            plan.enabled = config.enabled
            plan.initial_capital_amount = amount
            plan.initial_capital_currency = currency
            plan.compounding_mode = config.compounding_mode
            plan.reserve_cash_percent = config.reserve_cash_percent
            plan.max_total_exposure_percent = config.max_total_exposure_percent
            plan.conflict_policy = config.conflict_policy
            plan.draft_fingerprint = fingerprint
            plan.row_version += 1

        await alloc_repo.replace_entries(session, plan_id=plan.plan_id, entries=resolved)

        item_refs = _item_refs_from_resolved(resolved, active, settlement)
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
            "max_total_exposure_percent": max_total_exposure_percent,
            "conflict_policy": conflict_policy,
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
    active, settlement = await _resolve_items(session, composition_id)
    item_refs = {
        e.composition_item_id: AllocationItemRef(
            kind=e.item_type,
            available=e.composition_item_id in active,
            settlement_currency=settlement.get(e.composition_item_id),
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
            # A revision request submits no draft body, so there is nothing to diff:
            # ``changed_paths`` is empty and the caller reloads ``current_draft``.
            stale_entries = await alloc_repo.list_entries(session, plan.plan_id)
            raise _draft_conflict(
                plan_id=plan.plan_id,
                expected_row_version=expected_row_version,
                current_row_version=plan.row_version,
                current_draft=_stored_canonical_draft(plan, stale_entries),
                submitted_draft=None,
            )

        entries = await alloc_repo.list_entries(session, plan.plan_id)
        config = _plan_to_config(plan, entries)
        if not config.enabled:
            raise AllocationValidationFailedError(
                "A plan revision can only be created in shared allocation mode (enabled=true).",
                details=[{"code": "ALLOCATION_NOT_ENABLED", "field": "enabled"}],
            )
        active, settlement = await _resolve_items(session, composition_id)
        item_refs = {
            e.composition_item_id: AllocationItemRef(
                kind=e.item_type,
                available=e.composition_item_id in active,
                settlement_currency=settlement.get(e.composition_item_id),
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


async def _resolve_items(
    session: AsyncSession, composition_id: str
) -> tuple[dict[str, MainboardItemKind], dict[str, str | None]]:
    """Active composition items -> (kind map, settlement-currency map) (doc 13 §5.1).

    The settlement map feeds the pure ``validate_allocation`` FX cross-check; an
    item that does not resolve to an instrument settlement currency maps to ``None``.
    """
    items = await mb_repo.list_active_items(session, composition_id)
    active = {item.item_id: item.item_kind for item in items}
    settlement = await resolve_settlement_currencies(session, items)
    return active, settlement


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
    resolved: list[dict[str, Any]],
    active: dict[str, MainboardItemKind],
    settlement: dict[str, str | None],
) -> dict[str, AllocationItemRef]:
    return {
        entry["composition_item_id"]: AllocationItemRef(
            kind=entry["item_type"],
            available=entry["composition_item_id"] in active,
            settlement_currency=settlement.get(entry["composition_item_id"]),
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
        "max_total_exposure_percent": (
            str(plan.max_total_exposure_percent)
            if plan.max_total_exposure_percent is not None
            else None
        ),
        "conflict_policy": (
            str(plan.conflict_policy) if plan.conflict_policy is not None else None
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
        "max_total_exposure_percent": (
            str(config.max_total_exposure_percent)
            if config.max_total_exposure_percent is not None
            else None
        ),
        "conflict_policy": (
            str(config.conflict_policy) if config.conflict_policy is not None else None
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


# --------------------------------------------------------------------------- #
# Stale-draft conflict body (doc 13 §7.2, §10.2 Flow E)                        #
# --------------------------------------------------------------------------- #


def _stored_canonical_draft(plan: Any, entries: list[PortfolioAllocationEntry]) -> dict[str, Any]:
    """The SERVER's draft in the same canonical shape the caller submits.

    Reuses ``_plan_to_config`` + ``_canonical_draft`` rather than hand-projecting the
    ORM rows, so the compare view and the fingerprint can never drift apart.
    """
    config = _plan_to_config(plan, entries)
    resolved = [
        {
            "composition_item_id": e.composition_item_id,
            "item_type": e.item_type,
            "active": e.active,
            "equity_share_percent": e.equity_share_percent,
        }
        for e in entries
    ]
    return _canonical_draft(config, resolved)


def _same_value(left: Any, right: Any) -> bool:
    """Compare two canonical-draft values by VALUE, not by spelling.

    The submitted draft stringifies the parsed input (``"10000"``, ``"40"``) while the
    server draft stringifies what NUMERIC gave back (``"10000.000000000000000000"``,
    ``"40.000000"``). Comparing those as text reports every money/percent field as
    disputed on any conflict — the compare view would light up fields the user never
    touched, which is worse than no diff at all.
    """
    if left == right:
        return True
    if isinstance(left, str) and isinstance(right, str):
        try:
            return Decimal(left) == Decimal(right)
        except InvalidOperation:
            return False
    return False


def _changed_paths(current: dict[str, Any] | None, submitted: dict[str, Any] | None) -> list[str]:
    """Dotted paths where the submitted draft and the server draft disagree.

    This is what turns a 409 into a usable compare view (Flow E step 3): the UI can
    highlight exactly the fields in dispute instead of asking the user to eyeball two
    whole drafts. Entries are keyed by ``composition_item_id`` — never by list index,
    which would report every row as changed after a single insertion.

    Both sides absent (a revision request, which submits no body) -> empty list.
    """
    if current is None or submitted is None:
        return []

    paths: list[str] = []
    for field in (
        "enabled",
        "compounding_mode",
        "reserve_cash_percent",
        "max_total_exposure_percent",
        "conflict_policy",
    ):
        if not _same_value(current.get(field), submitted.get(field)):
            paths.append(field)

    cur_capital = current.get("initial_capital") or {}
    sub_capital = submitted.get("initial_capital") or {}
    for key in ("amount", "currency"):
        if not _same_value(cur_capital.get(key), sub_capital.get(key)):
            paths.append(f"initial_capital.{key}")

    cur_entries = {e["composition_item_id"]: e for e in current.get("entries", [])}
    sub_entries = {e["composition_item_id"]: e for e in submitted.get("entries", [])}
    for cid in sorted(set(cur_entries) | set(sub_entries)):
        if cid not in cur_entries or cid not in sub_entries:
            # Added on one side only — the whole entry is the disputed unit.
            paths.append(f"entries[{cid}]")
            continue
        for key in ("item_type", "active", "equity_share_percent"):
            if not _same_value(cur_entries[cid].get(key), sub_entries[cid].get(key)):
                paths.append(f"entries[{cid}].{key}")
    return paths


def _draft_conflict(
    *,
    plan_id: str | None,
    expected_row_version: int | None,
    current_row_version: int,
    current_draft: dict[str, Any] | None,
    submitted_draft: dict[str, Any] | None,
) -> AllocationDraftConflictError:
    """Build the 409 body doc 13 §7.2 specifies: ``current_draft`` + ``changed_paths[]``.

    The error used to be a bare ``code`` + ``message``, which left the client with no
    way to honour Flow E (the UI presents the local unsaved fields against the server
    state in a compare view; last-write-wins is forbidden) — it could only tell the
    user something changed and discard their edits, or blindly re-PUT and clobber.
    Both are the outcome §10.2 rules out.
    """
    return AllocationDraftConflictError(
        details=[
            {
                "code": "ALLOCATION_DRAFT_STALE",
                "expected_row_version": expected_row_version,
                "current_row_version": current_row_version,
                "current_draft": current_draft,
                "changed_paths": _changed_paths(current_draft, submitted_draft),
            }
        ],
        scope_type=_PLAN_TARGET,
        scope_id=plan_id,
    )


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
