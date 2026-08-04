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

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.durable_audit import AuditSessionFactory, record_durable_audit
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
from entropia.domain.backtest.execution.fills import (
    tick_data_required,
)
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.mainboard.composition import CompositionMember, composition_hash
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.market_data.enums import MarketRevisionState, supports_intrabar_execution
from entropia.domain.readiness.enums import ReadinessIssueCode, ReadinessScope, ReadinessSeverity
from entropia.domain.readiness.issues import (
    ExternalImportState,
    ReadinessIssue,
    ReadinessItemInput,
    ResearchSourceState,
)
from entropia.domain.readiness.validators import evaluate_readiness
from entropia.domain.strategy.config import StrategyConfig
from entropia.domain.trading_signal.config import TradingSignalConfig
from entropia.domain.trading_signal.enums import PriceSourceMode as SignalPriceSource
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    MainboardWorkingItem,
    PortfolioAllocationEntry,
    PortfolioAllocationPlanRevision,
)
from entropia.infrastructure.postgres.repositories import allocation as alloc_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import market_data as market_repo
from entropia.infrastructure.postgres.repositories import readiness as readiness_repo
from entropia.infrastructure.postgres.repositories import research_data as research_repo
from entropia.infrastructure.postgres.repositories import strategy as strat_repo
from entropia.shared.errors import (
    AccessDeniedError,
    CompositionNotFoundError,
    CompositionStaleError,
)

# K-08: the two Trading Signal price sources that must be backed by approved Market
# Data (doc 04 §5 Price Source row). Kept as strings for the same reason the pure
# validator does — the Trade Log twin declares the identical values.
_SIGNAL_OHLCV_FALLBACK_SOURCES = frozenset(
    {
        str(SignalPriceSource.OHLCV_CLOSE_IF_NEEDED),
        str(SignalPriceSource.OHLCV_INTRABAR_IF_AVAILABLE),
    }
)

_REPORT_TARGET = "ready_check_report"
_SNAPSHOT_TARGET = "mainboard_composition_snapshot"
_WORKSPACE_TARGET = "mainboard_workspace"
_ACCESS_DENIED_EVENT = "readiness.access_denied"
_SUCCEEDED = "succeeded"
_EXTERNAL_KINDS = frozenset({MainboardItemKind.TRADING_SIGNAL, MainboardItemKind.TRADE_LOG})


async def run_readiness_check(
    session: AsyncSession,
    actor: Actor,
    *,
    composition_id: str,
    expected_fingerprint: str | None = None,
    idempotency_key: str | None = None,
    parent_agent_task_id: str | None = None,
    audit_session_factory: AuditSessionFactory | None = None,
) -> dict[str, Any]:
    """Run the Ready Check for a composition and persist an immutable report
    (doc 14 §7, §9.2).

    ``parent_agent_task_id`` is the doc 14 §12.2 audit field for a check an Agent
    ran as part of a task (``jobs.agent_tools`` passes its task id); a human check
    leaves it null. ``audit_session_factory`` only reaches the DURABLE denial path
    (O-04) — see :func:`record_readiness_access_denied`.
    """
    require_authenticated(actor)
    await _load_workspace_for_check(
        session,
        actor,
        composition_id,
        operation="run_readiness_check",
        audit_session_factory=audit_session_factory,
    )

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
        signal_market_data_issues = await _resolve_signal_market_data_issues(session, items)
        strategy_indicator_issues = await _resolve_strategy_indicator_issues(session, items)
        research_sources = await _resolve_research_sources(session, items)
        evaluation = evaluate_readiness(
            items,
            allocation_enabled=allocation_enabled,
            allocation_issues=allocation_issues,
            market_data_issues=market_data_issues,
            tick_data_issues=tick_data_issues,
            signal_market_data_issues=signal_market_data_issues,
            strategy_indicator_issues=strategy_indicator_issues,
            research_sources=research_sources,
        )

        scope_labels = {
            item.item_id: item.display_label_override
            for item, _ok in enabled
            if item.display_label_override
        }
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
            parent_agent_task_id=parent_agent_task_id,
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
            # F-07 §4.4: parity with ``queries.readiness_check`` — a just-created report
            # returns the SAME issue shape the read model serves, so the page does not
            # lose its labels between the POST response and the next GET. The labels
            # come from the items this very transaction snapshotted.
            "issues": [_labelled_issue(i, scope_labels) for i in evaluation.issues],
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


async def record_readiness_access_denied(
    actor: Actor,
    *,
    composition_id: str,
    operation: str,
    denial_code: str,
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Persist the doc 14 §12.2 ``readiness_access_denied`` audit DURABLY (O-04).

    A denial is a raise, and the request tx is rolled back on the resulting 403, so
    an in-transaction row would never survive — this one is written in its own
    committed transaction (see ``application.durable_audit``). Shared with the RUN
    admission surface (``commands.backtest_run``) so both denials land under one
    event kind, distinguished by ``operation``.

    The target id is the composition the actor was denied, never the owner's
    principal id or any resource content — "target type/id redacted as policy
    requires" (doc 14 §12.2).
    """
    await record_durable_audit(
        actor,
        event_kind=_ACCESS_DENIED_EVENT,
        target_entity_id=composition_id,
        target_entity_type=_WORKSPACE_TARGET,
        new_state=denial_code,
        reason="access_denied",
        metadata={"operation": operation, "denial_code": denial_code},
        audit_session_factory=audit_session_factory,
    )


async def _load_workspace_for_check(
    session: AsyncSession,
    actor: Actor,
    composition_id: str,
    *,
    operation: str = "run_readiness_check",
    audit_session_factory: AuditSessionFactory | None = None,
) -> EntityRegistry:
    workspace = await mb_repo.get_workspace(session, composition_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    try:
        ensure_can_view(
            actor, owner_principal_id=workspace.owner_principal_id, visibility="private"
        )
    except AccessDeniedError as denial:
        await record_readiness_access_denied(
            actor,
            composition_id=composition_id,
            operation=operation,
            denial_code=denial.code,
            audit_session_factory=audit_session_factory,
        )
        raise
    return workspace


def _labelled_issue(
    issue: ReadinessIssue, scope_labels: Mapping[str, str]
) -> dict[str, str | None]:
    """``issue.as_dict()`` plus the pinned ``scope_label`` (F-07 §4.4).

    The label is NOT persisted on the issue row: the read model recovers it from the
    report's composition snapshot, so there is exactly one stored copy and the two
    surfaces can never drift.
    """
    data = issue.as_dict()
    data["scope_label"] = scope_labels.get(issue.scope_id) if issue.scope_id else None
    return data


async def _build_item_inputs(
    session: AsyncSession,
    enabled: list[tuple[MainboardWorkingItem, bool]],
) -> list[ReadinessItemInput]:
    inputs: list[ReadinessItemInput] = []
    # O-24b: one IN() read for every available item's pinned revision instead of one per
    # item. An id with no row is absent from the map, so the empty-payload fallback below
    # is unchanged — an unresolvable pin still reaches the validators as ``payload={}``.
    revisions = await mb_repo.get_work_object_revisions(
        session, [item.pinned_revision_id for item, available in enabled if available]
    )
    for item, available in enabled:
        payload: dict[str, Any] = {}
        external: ExternalImportState | None = None
        if available:
            revision = revisions.get(item.pinned_revision_id)
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


def _is_strategy(item: ReadinessItemInput) -> bool:
    return item.available and item.kind == MainboardItemKind.STRATEGY


def _market_pin(item: ReadinessItemInput) -> str:
    """The strategy's declared market dataset pin, or ``""`` when it declares none.

    The blank stands in for 'no pin' exactly as before: it matches no row, so the item
    falls into the NOT_APPROVED blocker instead of resolving to some other dataset."""
    data = item.payload.get("data")
    revision_id = data.get("market_dataset_revision_id") if isinstance(data, dict) else None
    return str(revision_id or "")


async def _resolve_market_data_issues(
    session: AsyncSession, items: list[ReadinessItemInput]
) -> list[ReadinessIssue]:
    """Fail closed unless every strategy's exact market-data pin is usable.

    A processed asset may exist before validation finishes, so asset presence is
    not approval evidence. The pinned revision itself must be APPROVED and its
    dataset root must still be ACTIVE (doc 11; doc 14 §9.2/§11).
    """
    issues: list[ReadinessIssue] = []
    # O-24b: one IN() read for every strategy's pinned dataset. A pin that is missing (or
    # blank) is absent from the map, so it still falls into the NOT_APPROVED blocker below
    # exactly as the per-item ``session.get`` miss did.
    revisions = await market_repo.get_revisions(
        session, [_market_pin(item) for item in items if _is_strategy(item)]
    )
    for item in items:
        if not item.available or item.kind != MainboardItemKind.STRATEGY:
            continue
        revision = revisions.get(_market_pin(item))
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


def _signal_price_pins(
    items: list[ReadinessItemInput],
) -> list[tuple[ReadinessItemInput, TradingSignalConfig, str]]:
    """Every Trading Signal whose price source declares an OHLCV fallback pin.

    Split out of the loop so the pins can be batched, and so the two deliberate
    silences stay in ONE place: a config that does not parse is left to
    ``EXTERNAL_IMPORT_INVALID``, and a config with NO reference at all is left to the
    pure validator — neither is a defect this resolver reports."""
    pins: list[tuple[ReadinessItemInput, TradingSignalConfig, str]] = []
    for item in items:
        if not item.available or item.kind != MainboardItemKind.TRADING_SIGNAL:
            continue
        try:
            config = TradingSignalConfig(**item.payload)
        except PydanticValidationError:
            continue  # EXTERNAL_IMPORT_INVALID already surfaces this in the validators.
        price = config.price_policy
        ref = price.approved_market_data_revision_ref
        if str(price.source) not in _SIGNAL_OHLCV_FALLBACK_SOURCES or ref is None:
            continue
        pins.append((item, config, ref))
    return pins


async def _resolve_signal_market_data_issues(
    session: AsyncSession, items: list[ReadinessItemInput]
) -> list[ReadinessIssue]:
    """K-08: prove a Trading Signal's OHLCV pin is approved AND intrabar-capable.

    Doc 04 §5 Price Source row requires "compatible approved Market Data at Ready
    Check" — two words the pure validator cannot check on its own:

    * *approved* — the declared ``price_policy.approved_market_data_revision_ref`` must
      still resolve to an APPROVED revision on an ACTIVE dataset root. Same approval
      semantics as ``_resolve_market_data_issues``; an unresolvable / revoked pin is
      reported with the doc 04 §11 Dependency code ``MARKET_DATA_DEPENDENCY_BLOCKED``,
      the same code the pure layer uses for a MISSING pin (one page vocabulary for one
      defect: "the market data this fallback needs is not there").
    * *compatible* — doc 04 §5.2 "Price Source = OHLCV Intrabar If Available" needs a
      dataset that carries sub-bar detail. ``supports_intrabar_execution`` is the single
      shared definition; a bar-only OHLCV pin yields ``INTRABAR_DATA_UNAVAILABLE``
      rather than an intrabar resolution the data cannot support.

    A config that does not parse is left to ``EXTERNAL_IMPORT_INVALID``, and a config
    with NO reference at all is left to the pure validator — this resolver deliberately
    stays silent on both so one defect never produces two blockers.
    """
    issues: list[ReadinessIssue] = []
    signals = _signal_price_pins(items)
    # O-24b: one IN() read for every signal's OHLCV fallback pin. A revoked/purged pin is
    # absent from the map, so it still produces MARKET_DATA_DEPENDENCY_BLOCKED below.
    revisions = await market_repo.get_revisions(session, [ref for _item, _config, ref in signals])
    for item, config, ref in signals:
        price = config.price_policy
        revision = revisions.get(ref)
        root = (
            await market_repo.get_dataset_root(session, revision.entity_id)
            if revision is not None
            else None
        )
        approved = (
            revision is not None
            and revision.revision_state == MarketRevisionState.APPROVED
            and root is not None
            and root.deletion_state == DeletionState.ACTIVE
        )
        if not approved:
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.MARKET_DATA_DEPENDENCY_BLOCKED,
                    severity=ReadinessSeverity.BLOCKER,
                    scope=ReadinessScope.MARKET_DATA,
                    message=(
                        "The Market Data revision this price fallback pins is not an APPROVED "
                        "revision of an ACTIVE dataset."
                    ),
                    remediation=(
                        "Pin an Approved Market Data revision on an active dataset (or ask an "
                        "Admin to approve/restore it), then re-run the check."
                    ),
                    field_path="price_policy.approved_market_data_revision_ref",
                    scope_id=item.item_id,
                )
            )
            continue  # intrabar capability of an unusable pin is not a separate defect
        if str(price.source) == str(
            SignalPriceSource.OHLCV_INTRABAR_IF_AVAILABLE
        ) and not supports_intrabar_execution(revision.market_data_type if revision else ""):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.INTRABAR_DATA_UNAVAILABLE,
                    severity=ReadinessSeverity.BLOCKER,
                    scope=ReadinessScope.MARKET_DATA,
                    message=(
                        "'OHLCV Intrabar If Available' needs a dataset carrying intrabar "
                        "detail, but the pinned revision is not a tick/trade dataset."
                    ),
                    remediation=(
                        "Pin an Approved tick/trade Market Data revision, or select 'OHLCV "
                        "Close If Needed' to run on the conservative bar model."
                    ),
                    field_path="price_policy.approved_market_data_revision_ref",
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


def _funded_strategies(
    items: list[ReadinessItemInput],
) -> list[tuple[ReadinessItemInput, StrategyConfig, str]]:
    """Every strategy with funding ON, paired with its (possibly blank) source pin.

    Split out of the loop so the pins can be batched. Funding OFF and a config that does
    not parse are skipped exactly as before — the latter is ``STRATEGY_CONFIG_INVALID``'s
    defect, not this resolver's."""
    funded: list[tuple[ReadinessItemInput, StrategyConfig, str]] = []
    for item in items:
        if not item.available or item.kind != MainboardItemKind.STRATEGY:
            continue
        try:
            config = StrategyConfig(**item.payload)
        except PydanticValidationError:
            continue  # STRATEGY_CONFIG_INVALID already surfaces this in the validators.
        if not config.data.funding.enabled:
            continue
        funded.append((item, config, config.data.funding.source_revision_id or ""))
    return funded


async def _resolve_research_sources(
    session: AsyncSession, items: list[ReadinessItemInput]
) -> list[ResearchSourceState]:
    """O-01: dereference every Research Data revision the composition pins.

    Doc 12 §9.2 makes Ready Check a MANDATORY second validator of the evidence bundle,
    alongside the worker. Before this the Research layer was absent from Ready Check
    entirely, so a composition pinning an ``agent_research_only`` (or unapproved, or
    available-time-less) revision reported READY and then failed inside the worker's
    ``FundingSourceInvalid`` gate — which stays exactly where it is (doc 12 §9.2 wants
    BOTH layers; eligibility can change between admission and execution).

    Honest boundary — deliberately identical to ``backtest_run_context._research_entries``:
    the V1 engine consumes exactly ONE research feed, the pinned funding source, so that
    is the only pin resolved here. Ready Check never claims to validate a feed the engine
    does not read. When another research consumption path lands, add it here and to the
    manifest context together.

    Resolving is a DB read (revision + root dereference), so it lives in the command; the
    judgement itself is the pure ``validate_research_sources`` (doc 14 §9.2 "validators
    must be separate pure deterministic domain services").
    """
    funded = _funded_strategies(items)
    # O-24b: one IN() read for every enabled funding pin. A blank id is never queried (it
    # short-circuits to ``found=False`` below, as before) and an id with no row is absent
    # from the map, so an unresolvable feed still reports ``found=False``.
    revisions = await research_repo.get_revisions(
        session, [revision_id for _item, _config, revision_id in funded if revision_id]
    )
    sources: list[ResearchSourceState] = []
    for item, config, revision_id in funded:
        field_path = "data.funding.source_revision_id"
        revision = revisions.get(revision_id) if revision_id else None
        if revision is None:
            sources.append(
                ResearchSourceState(
                    item_id=item.item_id,
                    revision_id=revision_id,
                    field_path=field_path,
                    found=False,
                    strategy_market_dataset_revision_id=config.data.market_dataset_revision_id,
                )
            )
            continue
        root = await research_repo.get_dataset_root(session, revision.entity_id)
        sources.append(
            ResearchSourceState(
                item_id=item.item_id,
                revision_id=revision.revision_id,
                field_path=field_path,
                found=True,
                root_active=root is not None and root.deletion_state == DeletionState.ACTIVE,
                revision_state=str(revision.revision_state),
                usage_scope=_enum_value(revision.usage_scope),
                available_time_policy=_enum_value(revision.available_time_policy),
                available_delay_seconds=revision.available_delay_seconds,
                linked_market_dataset_revision_id=revision.linked_market_dataset_revision_id,
                instrument_mapping_ref=revision.instrument_mapping_ref,
                validation_status=_enum_value(revision.validation_status),
                strategy_market_dataset_revision_id=config.data.market_dataset_revision_id,
            )
        )
    return sources


def _enum_value(value: Any) -> str | None:
    """The raw persisted string of a nullable enum column (never a parsed object)."""
    return None if value is None else str(value)


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
    """Resolve the persisted allocation state into (enabled, issues, capital_mode).

    R-1 — the config pinned in ``capital_mode`` is the config of the revision the
    snapshot NAMES. Doc 13 §1.2 fixes the chain ``draft -> plan revision ->
    composition snapshot -> run manifest``, §8.5 says the snapshot pins the *exact*
    plan revision, and §11.1 says the draft "direct engine input degildir" (Master
    Ref Modul 11: "sonuc manifest'te exact allocation plan revision/snapshot olarak
    saklanir"). A re-cut draft therefore takes effect only once it is frozen into a
    NEW revision (§1.2); it does not retro-fit the config attributed to the old
    one. Divergence is not a finding here: doc 14 §9.2 enumerates the portfolio
    blockers/warnings and defines none for it, so raising one would be taxonomy
    this project does not own.

    The live draft is pinned ONLY when nothing else is — independent mode, or
    before a first revision exists — and then ``plan_revision_id`` is null, so the
    pinned config and the pointer cannot disagree in either direction.

    The MODE stays the live plan's toggle (doc 13 §10.1): a plan switched back to
    independent stays independent even though a frozen revision still exists.
    ``validate_allocation`` re-applies the Modul 11 rules to whichever config was
    pinned, against LIVE item availability — an item frozen into a revision and
    soft-deleted since is still ITEM_UNAVAILABLE.
    """
    plan = await alloc_repo.get_plan_for_workspace(session, composition_id)
    if plan is None:
        return False, [], {"enabled": False}

    revision = await _pinned_revision(session, plan)
    if revision is None:
        entries = await alloc_repo.list_entries(session, plan.plan_id)
        config = _plan_to_config(plan, entries)
    else:
        config = PortfolioAllocationConfigV1.model_validate(revision.config)
    active_ids = {item.item_id for item in available_items}
    settlement = await resolve_settlement_currencies(session, available_items)
    item_refs = {
        e.composition_item_id: AllocationItemRef(
            kind=e.item_type,
            available=e.composition_item_id in active_ids,
            settlement_currency=settlement.get(e.composition_item_id),
        )
        for e in config.entries
        # An entry whose kind is unresolvable gets NO ref, so validation blocks it
        # as ITEM_UNAVAILABLE instead of guessing a kind. A draft always carries one
        # (the column is NOT NULL); this only guards a hand-written config.
        if e.item_type is not None
    }
    issues, _derived = validate_allocation(config, item_refs=item_refs)
    capital_mode: dict[str, Any] = {
        "enabled": config.enabled,
        "plan_id": plan.plan_id,
        "plan_revision_id": None if revision is None else revision.plan_revision_id,
        "config_hash": _pinned_config_hash(config, revision),
        "config": canonical_config(config) if config.enabled else None,
    }
    return config.enabled, list(issues), capital_mode


async def _pinned_revision(
    session: AsyncSession, plan: Any
) -> PortfolioAllocationPlanRevision | None:
    """The frozen revision this snapshot may pin, or ``None`` for the live draft.

    Only shared mode pins one — the mode is the live toggle (doc 13 §10.1), so a
    plan toggled back to independent must not be re-enabled by a leftover head
    pointer. A pointer that does not resolve within this plan pins NOTHING: the
    snapshot then reports the draft with a null ``plan_revision_id``, the same
    self-consistent shape as "enabled but never frozen". Naming a revision whose
    config was never read is the one outcome R-1 forbids.
    """
    if not plan.enabled or plan.current_revision_id is None:
        return None
    return await alloc_repo.get_plan_revision(session, plan.plan_id, plan.current_revision_id)


def _pinned_config_hash(
    config: PortfolioAllocationConfigV1, revision: PortfolioAllocationPlanRevision | None
) -> str | None:
    """The hash OF the pinned config: the revision's own, or one over the draft.

    The revision's stored ``config_hash`` is preferred over recomputing it, so the
    snapshot reproduces what was frozen even if the canonical serialization is ever
    revised — a recomputed hash would silently disagree with the immutable row it
    claims to describe.
    """
    if revision is not None:
        return str(revision.config_hash)
    return compute_config_hash(config) if config.enabled else None


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
                # F-07 §4.4 — the item's human name pinned AT SNAPSHOT TIME. The report
                # this snapshot backs is immutable and is_current-tracked, so its issue
                # scopes MUST be labelled from here; reading the live composition would
                # label a stale report with names it never saw. Twin of
                # ``commands.mainboard._snapshot_manifest``.
                "label": item.display_label_override,
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
    parent_agent_task_id: str | None = None,
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind="readiness.check_requested",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=composition_id,
        target_entity_type=_SNAPSHOT_TARGET,
        correlation_id=actor.correlation_id,
        # doc 14 §12.2 requires the parent Agent task id (nullable) on the request
        # event; the 64-char fingerprint cannot ride ``new_state`` (VARCHAR(48)).
        metadata={
            "composition_fingerprint": fingerprint,
            "parent_agent_task_id": parent_agent_task_id,
        },
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


__all__ = ["record_readiness_access_denied", "run_readiness_check"]
