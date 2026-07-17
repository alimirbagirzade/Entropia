"""Backtest Ready Check command (doc 14 §7, §9.2, §9.3).

Ready Check is a server-side immutable-snapshot validator, NOT a browser form
check (doc 14 §14). One transaction, supplied by the request dependency, never
committed here. Shape mirrors 4a: authorization + pure input validation OUTSIDE
the idempotent body -> ``run_idempotent`` op {
  read persisted draft -> compute current fingerprint ->
  ``expected_fingerprint`` guard (mismatch => 409, RC-09) ->
  transactional immutable snapshot (from persisted draft, NOT DOM/file) ->
  resolve pinned revision payloads + external import evidence + allocation ->
  pure ``evaluate_readiness`` -> persist immutable report + issues ->
  back-fill snapshot.readiness_report_id -> audit + outbox
}.

A rerun always creates a NEW immutable report id (RC-18); reports/issues are never
patched (doc 14 §9.1, §12.1). RUN admission (``POST /backtest-runs``) is a
separate stage and is intentionally NOT implemented here (doc 14 §9.3, out of the
Ready Check page scope).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.application.queries.allocation_currency import resolve_settlement_currencies
from entropia.application.queries.indicator_plan import resolve_indicator_plan
from entropia.domain.allocation.config import PortfolioAllocationConfigV1
from entropia.domain.allocation.rules import (
    AllocationItemRef,
    canonical_config,
    compute_config_hash,
    validate_allocation,
)
from entropia.domain.backtest.engine import tick_data_required
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.mainboard.composition import CompositionMember, composition_hash
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.market_data.enums import MarketRevisionState
from entropia.domain.readiness.enums import ReadinessIssueCode, ReadinessScope, ReadinessSeverity
from entropia.domain.readiness.issues import ExternalImportState, ReadinessIssue, ReadinessItemInput
from entropia.domain.readiness.validators import evaluate_readiness
from entropia.domain.strategy.config import StrategyConfig
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    MainboardWorkingItem,
    PortfolioAllocationEntry,
)
from entropia.infrastructure.postgres.repositories import allocation as alloc_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import market_data as market_repo
from entropia.infrastructure.postgres.repositories import readiness as readiness_repo
from entropia.infrastructure.postgres.repositories import strategy as strat_repo
from entropia.shared.errors import CompositionNotFoundError, CompositionStaleError

_REPORT_TARGET = "ready_check_report"
_SNAPSHOT_TARGET = "mainboard_composition_snapshot"
_SUCCEEDED = "succeeded"
_EXTERNAL_KINDS = frozenset({MainboardItemKind.TRADING_SIGNAL, MainboardItemKind.TRADE_LOG})


async def run_readiness_check(
    session: AsyncSession,
    actor: Actor,
    *,
    composition_id: str,
    expected_fingerprint: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Run the Ready Check for a composition and persist an immutable report
    (doc 14 §7, §9.2)."""
    require_authenticated(actor)
    await _load_workspace_for_check(session, actor, composition_id)

    async def _op() -> dict[str, Any]:
        enabled = await readiness_repo.list_enabled_items_with_root_state(session, composition_id)
        available_items = [item for item, ok in enabled if ok]
        current_fingerprint = composition_hash(_members(available_items))

        # RC-09: an explicit expected fingerprint that no longer matches the current
        # draft is a stale conflict — no snapshot/report is created (doc 14 §11).
        if expected_fingerprint is not None and expected_fingerprint != current_fingerprint:
            raise CompositionStaleError()

        allocation_enabled, allocation_issues, capital_mode = await _resolve_allocation(
            session, composition_id, available_items
        )

        snapshot = await mb_repo.create_snapshot(
            session,
            workspace_entity_id=composition_id,
            composition_hash=current_fingerprint,
            item_manifest=_manifest(actor, composition_id, current_fingerprint, available_items),
            created_by_principal_id=actor.principal_id,
            capital_mode_snapshot=capital_mode,
        )

        items = await _build_item_inputs(session, enabled)
        market_data_issues = await _resolve_market_data_issues(session, items)
        tick_data_issues = await _resolve_tick_data_issues(session, items)
        strategy_indicator_issues = await _resolve_strategy_indicator_issues(session, items)
        evaluation = evaluate_readiness(
            items,
            allocation_enabled=allocation_enabled,
            allocation_issues=allocation_issues,
            market_data_issues=market_data_issues,
            tick_data_issues=tick_data_issues,
            strategy_indicator_issues=strategy_indicator_issues,
        )

        blocked_ids = {
            i.scope_id for i in evaluation.issues if str(i.severity) == "blocker" and i.scope_id
        }
        pass_count = sum(1 for it in items if it.available and it.item_id not in blocked_ids)

        report = await readiness_repo.create_report(
            session,
            workspace_entity_id=composition_id,
            composition_snapshot_id=snapshot.snapshot_id,
            composition_fingerprint=current_fingerprint,
            state=str(evaluation.state),
            blocker_count=evaluation.blocker_count,
            warning_count=evaluation.warning_count,
            pass_count=pass_count,
            allocation_enabled=allocation_enabled,
            checked_by_principal_id=actor.principal_id,
        )
        await readiness_repo.add_issues(
            session, report_id=report.report_id, issues=evaluation.issues
        )

        # Fill the slot 3a left null; currentness is still recomputed at read time.
        snapshot.readiness_report_id = report.report_id
        snapshot.readiness_state = str(evaluation.state)

        _emit_audit(
            session,
            actor,
            report_id=report.report_id,
            snapshot_id=snapshot.snapshot_id,
            composition_id=composition_id,
            fingerprint=current_fingerprint,
            evaluation=evaluation,
        )
        return {
            "report_id": report.report_id,
            "composition_id": composition_id,
            "state": str(evaluation.state),
            "snapshot_id": snapshot.snapshot_id,
            "composition_fingerprint": current_fingerprint,
            "summary": {
                "blocker_count": evaluation.blocker_count,
                "warning_count": evaluation.warning_count,
                "pass_count": pass_count,
                "allocation_enabled": allocation_enabled,
            },
            "issues": [i.as_dict() for i in evaluation.issues],
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "run_readiness_check",
            "composition_id": composition_id,
            "expected_fingerprint": expected_fingerprint,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Resolution helpers                                                          #
# --------------------------------------------------------------------------- #


async def _load_workspace_for_check(
    session: AsyncSession, actor: Actor, composition_id: str
) -> EntityRegistry:
    workspace = await mb_repo.get_workspace(session, composition_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    ensure_can_view(actor, owner_principal_id=workspace.owner_principal_id, visibility="private")
    return workspace


async def _build_item_inputs(
    session: AsyncSession,
    enabled: list[tuple[MainboardWorkingItem, bool]],
) -> list[ReadinessItemInput]:
    inputs: list[ReadinessItemInput] = []
    for item, available in enabled:
        payload: dict[str, Any] = {}
        external: ExternalImportState | None = None
        if available:
            revision = await mb_repo.get_work_object_revision(session, item.pinned_revision_id)
            payload = dict(revision.payload) if revision is not None else {}
            if item.item_kind == MainboardItemKind.STRATEGY:
                payload = await _resolve_strategy_payload(session, payload)
            if item.item_kind in _EXTERNAL_KINDS:
                external = await _resolve_external(session, item)
        inputs.append(
            ReadinessItemInput(
                item_id=item.item_id,
                kind=item.item_kind,
                root_id=item.work_object_root_id,
                revision_id=item.pinned_revision_id,
                available=available,
                payload=payload,
                external=external,
            )
        )
    return inputs


async def _resolve_strategy_payload(
    session: AsyncSession, payload: dict[str, Any]
) -> dict[str, Any]:
    """Resolve a Strategy-editor MIRROR pin to its typed canonical config.

    A strategy Mainboard item pins either a direct StrategyConfig payload (a
    work object created with the full config) or the doc-02 §7.1 mirror
    work-object revision (``{"strategy_revision_id", "config_hash", ...}``) that
    ``save_strategy_revision`` appends. Ready Check must always validate the
    REAL immutable configuration, so the mirror is dereferenced here; an
    unresolvable mirror falls through unchanged and fails config validation
    visibly (never silently passes)."""
    mirror_ref = payload.get("strategy_revision_id")
    if not mirror_ref:
        return payload
    revision = await strat_repo.get_strategy_revision(session, str(mirror_ref))
    if revision is None:
        return payload
    return dict(revision.payload)


async def _resolve_market_data_issues(
    session: AsyncSession, items: list[ReadinessItemInput]
) -> list[ReadinessIssue]:
    """Fail closed unless every strategy's exact market-data pin is usable.

    A processed asset may exist before validation finishes, so asset presence is
    not approval evidence. The pinned revision itself must be APPROVED and its
    dataset root must still be ACTIVE (doc 11; doc 14 §9.2/§11).
    """
    issues: list[ReadinessIssue] = []
    for item in items:
        if not item.available or item.kind != MainboardItemKind.STRATEGY:
            continue
        data = item.payload.get("data")
        revision_id = data.get("market_dataset_revision_id") if isinstance(data, dict) else None
        revision = await market_repo.get_revision(session, str(revision_id or ""))
        root = (
            await market_repo.get_dataset_root(session, revision.entity_id)
            if revision is not None
            else None
        )
        if (
            revision is not None
            and revision.revision_state == MarketRevisionState.APPROVED
            and root is not None
            and root.deletion_state == DeletionState.ACTIVE
        ):
            continue
        issues.append(
            ReadinessIssue(
                code=ReadinessIssueCode.MARKET_DATASET_NOT_APPROVED,
                severity=ReadinessSeverity.BLOCKER,
                scope=ReadinessScope.MARKET_DATA,
                message="The pinned market dataset revision is not ACTIVE and APPROVED.",
                remediation=(
                    "Approve the pinned market dataset revision or select an approved revision, "
                    "then re-run the check."
                ),
                field_path="data.market_dataset_revision_id",
                scope_id=item.item_id,
            )
        )
    return issues


async def _resolve_tick_data_issues(
    session: AsyncSession, items: list[ReadinessItemInput]
) -> list[ReadinessIssue]:
    """F-07i: fail closed when a strategy demands tick data but none is approved.

    'Use Tick Data = Yes' (``intrabar_policy.tick_policy == 'require'``) makes an
    approved tick/trade revision for the strategy's instrument MANDATORY (Master Ref
    §6.4). Master Ref §11.2 (line ~3558): Ready Check evaluates dataset resolution
    sufficiency for intrabar-sensitive execution — an unmet requirement blocks RUN
    rather than silently resolving over OHLCV ('cannot silently imitate unavailable
    detail'). 'None'/'No' (``inherit``/``disable``) never require tick data.

    Resolving availability is a DB read (approved tick revision lookup), so it lives
    here in the command, not in the pure validators — the same shape as
    ``_resolve_market_data_issues``. A config that does not even parse is left to the
    ``STRATEGY_CONFIG_INVALID`` validator. The ``tick_data_required`` predicate is the
    single engine-owned source of truth for 'requires tick', shared so the engine's
    later intrabar gate (sub-slice B) and this blocker never diverge.
    """
    issues: list[ReadinessIssue] = []
    for item in items:
        if not item.available or item.kind != MainboardItemKind.STRATEGY:
            continue
        try:
            config = StrategyConfig(**item.payload)
        except PydanticValidationError:
            continue  # STRATEGY_CONFIG_INVALID already surfaces this in the validators.
        if not tick_data_required(config):
            continue
        revision = await market_repo.find_approved_tick_revision_for_instrument(
            session, config.data.instrument_id
        )
        if revision is not None:
            continue
        issues.append(
            ReadinessIssue(
                code=ReadinessIssueCode.TICK_DATA_UNAVAILABLE,
                severity=ReadinessSeverity.BLOCKER,
                scope=ReadinessScope.MARKET_DATA,
                message=(
                    "The strategy requires tick data ('Use Tick Data' = Yes) but no approved "
                    "tick/trade dataset is available for its instrument."
                ),
                remediation=(
                    "Approve a tick/trade dataset revision for this instrument, or set 'Use "
                    "Tick Data' to None or No to run on the conservative OHLCV model."
                ),
                field_path="data.intrabar_policy.tick_policy",
                scope_id=item.item_id,
            )
        )
    return issues


async def _resolve_strategy_indicator_issues(
    session: AsyncSession, items: list[ReadinessItemInput]
) -> list[ReadinessIssue]:
    """F-06: block RUN when a strategy's pinned indicator dependency does not resolve.

    Ready Check is the upfront RUN gate (doc 14 §4). The worker's fail-closed guard
    (``jobs.backtest_engine``) is the last line of defence; this makes the missing
    package/revision a *pre-run* blocker with a concrete remediation, so the user is
    never allowed to admit a run that would either fabricate breakout-proxy metrics
    (F-06) or fail terminally.

    Resolving the plan is a DB read (pinned ``package_revision`` dereference), so it
    lives here in the command, not in the pure validators — the same shape as
    ``_resolve_market_data_issues``. A config that does not even parse is left to the
    ``STRATEGY_CONFIG_INVALID`` validator; a strategy with no enabled entry block is
    left to ``STRATEGY_NO_ENTRY_LOGIC`` — this check only fires when entry blocks
    exist but their pinned packages resolve to no computable signal, or any block is
    left unresolved.
    """
    issues: list[ReadinessIssue] = []
    for item in items:
        if not item.available or item.kind != MainboardItemKind.STRATEGY:
            continue
        try:
            config = StrategyConfig(**item.payload)
        except PydanticValidationError:
            continue  # STRATEGY_CONFIG_INVALID already surfaces this in the validators.
        entry_blocks = [b for b in config.position_entry_logic.indicator_blocks if b.enabled]
        protection = config.protection_stop_logic
        has_logic_stops = protection is not None and bool(protection.logic_blocks)
        if not entry_blocks and not has_logic_stops:
            continue  # STRATEGY_NO_ENTRY_LOGIC covers a strategy with no entry block.
        plan = await resolve_indicator_plan(session, config)
        # F-08: split stop-scoped unresolved dependencies from entry/exit ones so each
        # gets its own accurate blocker code / message / field path.
        stop_unresolved = [u for u in plan.unresolved if u.startswith("stop:")]
        entry_unresolved = [u for u in plan.unresolved if not u.startswith("stop:")]
        if entry_blocks and (not plan.has_entry or entry_unresolved):
            detail = entry_unresolved or ["no computable entry signal from the pinned packages"]
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.STRATEGY_INDICATOR_UNRESOLVED,
                    severity=ReadinessSeverity.BLOCKER,
                    scope=ReadinessScope.STRATEGY,
                    message=(
                        "A pinned indicator package or dependency does not resolve to a "
                        f"computable signal: {detail}."
                    ),
                    remediation=(
                        "Pin an approved indicator package whose dependencies resolve (or fix "
                        "the unresolved block), then re-run the check."
                    ),
                    field_path="position_entry_logic.indicator_blocks",
                    scope_id=item.item_id,
                )
            )
        if stop_unresolved:
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.STRATEGY_LOGIC_STOP_UNRESOLVED,
                    severity=ReadinessSeverity.BLOCKER,
                    scope=ReadinessScope.STRATEGY,
                    message=(
                        "A pinned Logic-Based Stop Block dependency does not resolve to a "
                        f"computable stop signal: {stop_unresolved}."
                    ),
                    remediation=(
                        "Pin an approved indicator/condition package whose dependencies resolve "
                        "for the logic stop block (or remove the block), then re-run the check."
                    ),
                    field_path="protection_stop_logic.logic_blocks",
                    scope_id=item.item_id,
                )
            )
    return issues


async def _resolve_external(
    session: AsyncSession, item: MainboardWorkingItem
) -> ExternalImportState:
    if item.item_kind == MainboardItemKind.TRADE_LOG:
        batch = await readiness_repo.resolve_trade_log_batch(session, item.pinned_revision_id)
        if batch is None:
            return ExternalImportState(found=False, succeeded=False, accepted_count=0)
        return ExternalImportState(
            found=True,
            succeeded=str(batch.status) == _SUCCEEDED,
            accepted_count=batch.accepted_count,
            instrument_id=batch.instrument_id,
            skipped_reason_codes=_reason_codes(batch.skipped_rows),
        )
    revision = await readiness_repo.resolve_signal_revision(session, item.pinned_revision_id)
    if revision is None:
        return ExternalImportState(found=False, succeeded=False, accepted_count=0)
    return ExternalImportState(
        found=True,
        succeeded=str(revision.status) == _SUCCEEDED,
        accepted_count=revision.accepted_count,
        instrument_id=revision.instrument_id,
        skipped_reason_codes=_reason_codes(revision.skipped_rows),
    )


def _reason_codes(skipped_rows: list[dict[str, Any]] | None) -> frozenset[str]:
    if not skipped_rows:
        return frozenset()
    return frozenset(
        str(row["reason_code"])
        for row in skipped_rows
        if isinstance(row, dict) and "reason_code" in row
    )


async def _resolve_allocation(
    session: AsyncSession,
    composition_id: str,
    available_items: list[MainboardWorkingItem],
) -> tuple[bool, list[Any], dict[str, Any] | None]:
    """Resolve the persisted allocation draft into (enabled, issues, capital_mode).

    Reuses the 4a plan/entries + ``validate_allocation`` (issues are empty in
    independent mode). ``capital_mode`` pins the plan's current revision config
    where one exists (doc 14 §9.1 capital mode snapshot), else the live draft.
    """
    plan = await alloc_repo.get_plan_for_workspace(session, composition_id)
    if plan is None:
        return False, [], {"enabled": False}

    entries = await alloc_repo.list_entries(session, plan.plan_id)
    config = _plan_to_config(plan, entries)
    active_ids = {item.item_id for item in available_items}
    settlement = await resolve_settlement_currencies(session, available_items)
    item_refs = {
        e.composition_item_id: AllocationItemRef(
            kind=e.item_type,
            available=e.composition_item_id in active_ids,
            settlement_currency=settlement.get(e.composition_item_id),
        )
        for e in entries
    }
    issues, _derived = validate_allocation(config, item_refs=item_refs)
    capital_mode: dict[str, Any] = {
        "enabled": config.enabled,
        "plan_id": plan.plan_id,
        "plan_revision_id": plan.current_revision_id,
        "config_hash": compute_config_hash(config) if config.enabled else None,
        "config": canonical_config(config) if config.enabled else None,
    }
    return config.enabled, list(issues), capital_mode


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
        "compounding_mode": (
            str(plan.compounding_mode) if plan.compounding_mode is not None else None
        ),
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


def _members(items: list[MainboardWorkingItem]) -> list[CompositionMember]:
    return [
        CompositionMember(
            kind=item.item_kind,
            root_id=item.work_object_root_id,
            revision_id=item.pinned_revision_id,
        )
        for item in items
    ]


def _manifest(
    actor: Actor,
    composition_id: str,
    fingerprint: str,
    items: list[MainboardWorkingItem],
) -> dict[str, Any]:
    return {
        "workspace_id": composition_id,
        "composition_hash": fingerprint,
        "items": [
            {
                "item_id": item.item_id,
                "kind": str(item.item_kind),
                "root_id": item.work_object_root_id,
                "revision_id": item.pinned_revision_id,
                "enabled": item.is_enabled,
                "position": item.position_index,
            }
            for item in items
        ],
        "created_by_actor_id": actor.principal_id,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _emit_audit(
    session: AsyncSession,
    actor: Actor,
    *,
    report_id: str,
    snapshot_id: str,
    composition_id: str,
    fingerprint: str,
    evaluation: Any,
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind="readiness.check_requested",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=composition_id,
        target_entity_type=_SNAPSHOT_TARGET,
        correlation_id=actor.correlation_id,
        metadata={"composition_fingerprint": fingerprint},
    )
    audit_repo.add_audit_event(
        session,
        event_kind="readiness.snapshot_created",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=snapshot_id,
        target_entity_type=_SNAPSHOT_TARGET,
        new_state=snapshot_id,
        correlation_id=actor.correlation_id,
        metadata={"composition_fingerprint": fingerprint},
    )
    audit_repo.add_audit_event(
        session,
        event_kind="readiness.report_created",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=report_id,
        target_entity_type=_REPORT_TARGET,
        new_state=str(evaluation.state),
        correlation_id=actor.correlation_id,
        metadata={
            "blocker_count": evaluation.blocker_count,
            "warning_count": evaluation.warning_count,
        },
    )
    for issue in evaluation.issues:
        audit_repo.add_audit_event(
            session,
            event_kind="readiness.issue_detected",
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            target_entity_id=report_id,
            target_entity_type=_REPORT_TARGET,
            new_state=str(issue.code),
            severity=str(issue.severity),
            correlation_id=actor.correlation_id,
            metadata={"scope": str(issue.scope), "scope_id": issue.scope_id},
        )
    audit_repo.add_outbox_event(
        session,
        event_type="readiness.report_created",
        resource_type=_REPORT_TARGET,
        resource_id=report_id,
        payload={
            "report_id": report_id,
            "composition_id": composition_id,
            "snapshot_id": snapshot_id,
            "state": str(evaluation.state),
            "composition_fingerprint": fingerprint,
            "blocker_count": evaluation.blocker_count,
            "warning_count": evaluation.warning_count,
        },
        correlation_id=actor.correlation_id,
    )


__all__ = ["run_readiness_check"]
