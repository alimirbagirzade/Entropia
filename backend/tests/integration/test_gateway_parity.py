"""Stage 8a — Tool Gateway parity: Agent tool line == human command line.

Auto-skips without PostgreSQL. The Agent's UI-less tools delegate to the SAME
application commands a human calls (doc 18 §10), so policy outcomes must be
IDENTICAL on both lines — same server truth on success, same typed denial code
on refusal, zero side effects on a gate rejection. Also proves the Stage-8
Coordinator wiring: the plan step consumes ``exposed_tool_names`` over the live
capability registry (CR-08/FD-10, deferred from Stage 7b).

Covered:
- ready-check parity: the gateway report equals a directly-invoked command
  report for the same composition (same fingerprint, same state);
- denial parity: a foreign-composition backtest request raises the SAME error
  code for a human that is recorded on the Agent's REJECTED tool call;
- capability parity (CR-08/CR-09): while ``graphic_view`` is Placeholder BOTH
  lines refuse with CAPABILITY_NOT_ACTIVE and write no dataset row; once
  Limited BOTH lines succeed;
- Coordinator plan wiring: the cycle summary + the ``agent_task_created`` event
  payload carry exactly the CR-08 exposure at plan time, and a capability
  transition to Limited changes the offered menu.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.commands.agent_loop import run_coordinator_cycle
from entropia.application.commands.capability import query_view_dataset, transition_capability
from entropia.application.jobs import agent_tools
from entropia.application.queries import mainboard as mb_query
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.agent_lab.tool_gateway import exposed_tool_names
from entropia.domain.capability.baseline import initial_dependency_snapshot
from entropia.domain.capability.enums import GRAPHIC_VIEW, ActivationGate
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import (
    AgentEvent,
    AgentRuntime,
    AgentToolCall,
    BacktestRun,
    EntityRegistry,
    Job,
    MarketDatasetRevision,
    Principal,
    ViewDataset,
)
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import capability as capability_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import AccessDeniedError, CapabilityNotActiveError

pytestmark = pytest.mark.integration

_ADMIN_PID = "admin_1"
_OWNER_PID = "user_1"
_AGENT_PID = "agent_alpha"
ADMIN = Actor(principal_id=_ADMIN_PID, principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id=_OWNER_PID, principal_type=PrincipalType.HUMAN, role=Role.USER)
AGENT = Actor(
    principal_id=_AGENT_PID,
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_parity",
)

GATES_WITHOUT_UI = {"gates": {gate.value: gate is not ActivationGate.UI for gate in ActivationGate}}


def _strategy_payload(indicator_revision_id: str = "pkg_rev_parity") -> dict[str, Any]:
    return {
        "strategy_root_id": "strat_parity_seed",
        "display_name": "Parity strategy",
        "rationale_family_id": "rf_parity",
        "data": {
            "instrument_id": "BTCUSDT",
            "market_dataset_root_id": "md_root_parity",
            "market_dataset_revision_id": "md_rev_parity",
            "market_dataset_content_hash": "a" * 64,
            "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-06-01T00:00:00Z"},
            "initial_capital": "10000.00",
            "execution": {"entry_timing": "next_candle_open", "exit_timing": "next_candle_open"},
            "order_config": {"type": "market_order"},
            "costs": {"commission": "0.04", "spread": "0.01", "slippage_value": "0.1"},
            "intrabar_policy": {"tick_policy": "inherit"},
            "funding": {"enabled": False},
        },
        "position_entry_logic": {
            "signal_block": {"rule": "required_indicator_blocks_only"},
            "indicator_blocks": [
                {
                    "block_id": "ib_parity",
                    "display_order": 0,
                    "package_ref": {
                        "package_root_id": "pkg_root_parity",
                        "package_revision_id": indicator_revision_id,
                        "package_content_hash": "b" * 64,
                    },
                    "trigger_source": "indicator_native_trigger",
                    "requirement": "required",
                }
            ],
        },
        "position_exit_logic": {},
        "protection_stop_logic": {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}},
        "position_sizing": {"method": "base_position_size", "base_position_size": "1.0"},
        "restrictions_filters": {},
        "conflict_position_handling": {},
    }


async def _seed(session) -> None:
    for pid, ptype in (
        (_ADMIN_PID, PrincipalType.HUMAN),
        (_OWNER_PID, PrincipalType.HUMAN),
        (_AGENT_PID, PrincipalType.AGENT),
    ):
        session.add(Principal(principal_id=pid, principal_type=ptype))
    session.add(
        AgentRuntime(
            agent_id=ALPHA_AGENT_ID,
            mode=RuntimeMode.CONTINUOUS,
            status=RuntimeStatus.ACTIVE,
            row_version=1,
        )
    )
    await session.flush()


async def _ready_composition(session, actor: Actor) -> str:
    mb = await mb_query.get_default_mainboard(session, actor)
    workspace_id = mb["workspace_id"]
    # GAP-01: readiness requires the pinned market revision to be ACTIVE+APPROVED.
    # The strategy payload pins md_root_parity / md_rev_parity, so seed a real
    # approved market dataset revision the market-data validator can resolve.
    if await session.get(EntityRegistry, "md_root_parity") is None:
        root = EntityRegistry(
            entity_id="md_root_parity",
            entity_type="market_dataset",
            owner_principal_id=None,
            created_by_principal_id=None,
            lifecycle_state="active",
            current_revision_id=None,
        )
        session.add(root)
        await session.flush()
        session.add(
            MarketDatasetRevision(
                revision_id="md_rev_parity",
                entity_id="md_root_parity",
                revision_no=1,
                market_data_type=MarketDataType.OHLCV,
                revision_state=MarketRevisionState.APPROVED,
                payload={},
                content_hash="a" * 64,
                created_by_principal_id=None,
            )
        )
        root.current_revision_id = "md_rev_parity"
        await session.flush()
    # F-06: pin a REAL approved indicator package whose dependency snapshot resolves a
    # directional key (ta.sma), so the upfront Ready Check gate does not block the run
    # on STRATEGY_INDICATOR_UNRESOLVED and the parity walk reaches the ready state.
    _reg, _pkg_root, pkg_rev = await pkg_repo.create_package(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        package_kind=PackageKind.INDICATOR,
        input_contract={"source": "close"},
        output_contract={"kind": "directional_signal"},
        dependency_snapshot={"resolved": [{"call": "ta.sma", "canonical_key": "ta.sma"}]},
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.flush()
    work_object = await mb_cmd.create_work_object(
        session,
        actor,
        object_kind="strategy",
        payload=_strategy_payload(indicator_revision_id=pkg_rev.revision_id),
    )
    await mb_cmd.attach_mainboard_item(
        session,
        actor,
        workspace_id=workspace_id,
        root_id=work_object["root_id"],
        revision_id=work_object["revision_id"],
        item_kind="strategy",
    )
    await session.commit()
    return workspace_id


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _walk_graphic_view_to_limited(session) -> None:
    """placeholder -> designed -> internal -> shadow -> limited (legal chain)."""
    steps = (
        ("designed", 1, initial_dependency_snapshot()),
        ("internal", 2, None),
        ("shadow", 3, None),
        ("limited", 4, GATES_WITHOUT_UI),
    )
    for to_state, expected, snapshot in steps:
        await transition_capability(
            session,
            ADMIN,
            capability_key=GRAPHIC_VIEW,
            to_state=to_state,
            reason=f"stage 8 parity walk to {to_state}",
            expected_registry_version=expected,
            dependency_snapshot=snapshot,
            idempotency_key=f"parity-{GRAPHIC_VIEW}-{to_state}",
        )
    await session.commit()


# --------------------------------------------------------------------------- #
# Ready Check parity — same command, same server truth                         #
# --------------------------------------------------------------------------- #


async def test_ready_check_parity_same_report_contract(session) -> None:
    await _seed(session)
    composition_id = await _ready_composition(session, AGENT)

    direct = await readiness_cmd.run_readiness_check(session, AGENT, composition_id=composition_id)
    await session.commit()

    via_tool = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="backtest.ready_check",
        policy_scope="execution",
        request={"composition_id": composition_id},
    )
    await session.commit()

    assert via_tool["status"] == "succeeded"
    assert via_tool["state"] == direct["state"] == "ready"
    assert via_tool["composition_fingerprint"] == direct["composition_fingerprint"]
    assert via_tool["summary"]["blocker_count"] == direct["summary"]["blocker_count"] == 0


# --------------------------------------------------------------------------- #
# Denial parity — same typed code on both lines                                #
# --------------------------------------------------------------------------- #


async def test_foreign_composition_denial_code_parity(session) -> None:
    await _seed(session)
    composition_id = await _ready_composition(session, OWNER)

    # Human command line: the SAME actor calling the application command
    # directly gets the typed 403.
    with pytest.raises(AccessDeniedError) as exc_info:
        await backtest_cmd.request_backtest_run(session, AGENT, composition_id=composition_id)
    await session.rollback()
    human_line_code = exc_info.value.code

    via_tool = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="backtest.request",
        policy_scope="execution",
        request={"composition_id": composition_id},
    )
    await session.commit()

    assert via_tool["status"] == "rejected"
    assert via_tool["reason_code"] == human_line_code
    call = await session.get(AgentToolCall, via_tool["tool_call_id"])
    assert call is not None and call.failure_code == human_line_code
    assert await _count(session, BacktestRun) == 0  # neither line left a run


# --------------------------------------------------------------------------- #
# Capability parity (CR-08 / CR-09)                                            #
# --------------------------------------------------------------------------- #


async def test_capability_gate_parity_placeholder_rejects_both_lines(session) -> None:
    await _seed(session)
    await capability_repo.seed_baseline_capabilities(session)
    await session.commit()

    request = {"source_manifest_refs": ["btman_pinned_1"], "schema_version": "v1"}

    with pytest.raises(CapabilityNotActiveError) as exc_info:
        await query_view_dataset(
            session,
            AGENT,
            source_manifest_refs=list(request["source_manifest_refs"]),
            schema_version=str(request["schema_version"]),
        )
    await session.rollback()
    human_line_code = exc_info.value.code

    via_tool = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="view_dataset.query",
        policy_scope="research",
        request=request,
    )
    await session.commit()

    assert via_tool["status"] == "rejected"
    assert via_tool["reason_code"] == human_line_code == "CAPABILITY_NOT_ACTIVE"
    # CR-09: a refusal is never a fake output — no dataset row, no job, on EITHER line.
    assert await _count(session, ViewDataset) == 0
    assert await _count(session, Job) == 0


async def test_capability_gate_parity_limited_allows_both_lines(session) -> None:
    await _seed(session)
    await capability_repo.seed_baseline_capabilities(session)
    await session.commit()
    await _walk_graphic_view_to_limited(session)

    request = {"source_manifest_refs": ["btman_pinned_1"], "schema_version": "v1"}

    direct = await query_view_dataset(
        session,
        AGENT,
        source_manifest_refs=list(request["source_manifest_refs"]),
        schema_version=str(request["schema_version"]),
    )
    await session.commit()
    assert direct["view_dataset_id"]

    via_tool = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="view_dataset.query",
        policy_scope="research",
        request=request,
    )
    await session.commit()

    assert via_tool["status"] == "succeeded"
    assert via_tool["view_dataset_id"] != direct["view_dataset_id"]
    assert await _count(session, ViewDataset) == 2  # one per line, same contract


# --------------------------------------------------------------------------- #
# Coordinator plan wiring (Stage 8; deferred from 7b)                          #
# --------------------------------------------------------------------------- #


async def _queue_directive(session, text: str) -> str:
    directive = await al_repo.create_directive(
        session,
        author_principal_id=_ADMIN_PID,
        target_agent_id=ALPHA_AGENT_ID,
        related_task_id=None,
        text=text,
        priority=AgentTaskPriority.HIGH,
        correlation_id="corr_parity",
    )
    await session.flush()
    return directive.directive_id


async def _task_created_payload(session, task_id: str) -> dict[str, Any]:
    stmt = (
        select(AgentEvent)
        .where(AgentEvent.type == "agent_task_created")
        .where(AgentEvent.task_id == task_id)
    )
    event = (await session.execute(stmt)).scalars().one()
    return dict(event.payload or {})


async def test_coordinator_plan_step_consumes_cr08_exposure(session) -> None:
    await _seed(session)
    await capability_repo.seed_baseline_capabilities(session)
    await _queue_directive(session, "Plan with the baseline (all placeholder) menu")
    await session.commit()

    # All capabilities Placeholder: the plan menu equals the ungated exposure.
    cycle = await run_coordinator_cycle(session)
    await session.commit()
    assert cycle["exposed_tools"] == list(exposed_tool_names(frozenset()))
    assert "view_dataset.query" not in cycle["exposed_tools"]
    payload = await _task_created_payload(session, cycle["followup_task_id"])
    assert payload["exposed_tools"] == cycle["exposed_tools"]

    # graphic_view -> Limited: the SAME loop now plans with the gated tool offered.
    await _walk_graphic_view_to_limited(session)
    await _queue_directive(session, "Plan again with graphic_view Limited")
    await session.commit()

    cycle2 = await run_coordinator_cycle(session)
    await session.commit()
    assert "view_dataset.query" in cycle2["exposed_tools"]
    operational = await capability_repo.operational_capability_keys(session)
    assert cycle2["exposed_tools"] == list(exposed_tool_names(operational))
    payload2 = await _task_created_payload(session, cycle2["followup_task_id"])
    assert payload2["exposed_tools"] == cycle2["exposed_tools"]
