"""Stage 8a — Integration flow (b): the UI-independent Agent loop end-to-end.

Auto-skips without PostgreSQL. The whole chain runs with ZERO UI/browser/HTTP
involvement (INF-06): an Admin queues a directive; the Coordinator consumes it at
a safe checkpoint and materializes an AUTONOMOUS follow-up task (recording the
CR-08 plan-time tool exposure); the Agent then works the task purely through the
Tool Gateway: data bundle resolve (evidence-scope gates enforced) -> backtest
request on its OWN composition -> engine worker -> result query -> hypothesis
artifact linked to the result.

Stage 8 acceptance proven here:
- the loop consumes each directive exactly once (AL-14; a second cycle spawns no
  duplicate follow-up);
- every Agent step is a durable, policy-scoped tool-call row (doc 18 §9.2);
- the Agent's backtest run pins a manifest exactly like a human run and a
  succeeded run materializes an immutable Result (CR-03 positive path);
- the hypothesis artifact carries provenance links to the produced result;
- the Agent never escalates beyond its own outputs: a backtest request against a
  HUMAN-owned composition is a recorded REJECTED denial, never a run.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import market_data as md_cmd
from entropia.application.commands.agent_loop import run_coordinator_cycle
from entropia.application.jobs import agent_tools
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.queries import mainboard as mb_query
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    RuntimeMode,
    RuntimeStatus,
)
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
from entropia.domain.research_data.enums import UsageScope
from entropia.infrastructure.postgres.models import (
    AgentRuntime,
    AgentTask,
    AgentToolCall,
    ArtifactLink,
    BacktestResult,
    BacktestRun,
    HypothesisArtifact,
    Job,
    Principal,
)
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import research_data as research_repo

pytestmark = pytest.mark.integration

_ADMIN_PID = "admin_1"
_AGENT_PID = "agent_alpha"
ADMIN = Actor(principal_id=_ADMIN_PID, principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
AGENT = Actor(
    principal_id=_AGENT_PID,
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_e2e_agent",
)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_runtime_and_principals(session) -> None:
    session.add(Principal(principal_id=_ADMIN_PID, principal_type=PrincipalType.HUMAN))
    session.add(Principal(principal_id=_AGENT_PID, principal_type=PrincipalType.AGENT))
    session.add(
        AgentRuntime(
            agent_id=ALPHA_AGENT_ID,
            mode=RuntimeMode.CONTINUOUS,
            status=RuntimeStatus.ACTIVE,
            row_version=1,
        )
    )
    await session.flush()


async def _approved_market(session) -> dict[str, str]:
    root, _ = await md_cmd.create_market_dataset(
        session,
        ADMIN,
        market_data_type=MarketDataType.OHLCV,
        payload={"instrument": "BTCUSDT", "candles": [1, 2, 3]},
        title="BTCUSDT 1h",
    )
    await session.flush()
    revision = await md_repo.get_revision(session, root.current_revision_id or "")
    assert revision is not None
    revision.revision_state = MarketRevisionState.VERIFIED
    await session.flush()
    await md_cmd.approve_market_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.flush()
    # Slice B: seed the processed Parquet asset the bar-replay worker resolves for
    # this revision (INF-12); the bar bytes are injected via ``_e2e_bars``.
    md_repo.add_processed_asset(
        session,
        entity_id=root.entity_id,
        object_key=f"market/processed/{root.entity_id}/e2e.parquet",
        content_digest="e2e-bars",
        size_bytes=4096,
        revision_id=revision.revision_id,
        row_count=22,
    )
    await session.flush()
    return {
        "root_id": root.entity_id,
        "revision_id": revision.revision_id,
        "content_hash": revision.content_hash,
    }


def _e2e_bars(_source: Any) -> Iterator[list[dict[str, Any]]]:
    """Deterministic OHLCV bars for the bar-replay worker (S3-free injection).

    20 flat bars fill the breakout window, then an upside breakout and a stop-out
    yield one real, reproducible trade — enough for a succeeded Result."""
    bars: list[dict[str, Any]] = [
        {
            "timestamp": f"2024-02-{i + 1:02d}T00:00:00Z",
            "open": "100",
            "high": "100",
            "low": "100",
            "close": "100",
            "volume": "5",
        }
        for i in range(20)
    ]
    bars.append(
        {
            "timestamp": "2024-02-21T00:00:00Z",
            "open": "100",
            "high": "103",
            "low": "100",
            "close": "103",
            "volume": "5",
        }
    )
    bars.append(
        {
            "timestamp": "2024-02-22T00:00:00Z",
            "open": "103",
            "high": "103",
            "low": "95",
            "close": "98",
            "volume": "5",
        }
    )
    yield bars


async def _research_revision(session) -> str:
    """An agent-usable research revision (RESEARCH_BACKTEST enters evidence bundles)."""
    _, revision = await research_repo.create_research_dataset(
        session,
        owner_principal_id=_AGENT_PID,
        created_by_principal_id=_AGENT_PID,
        payload={"series": [1, 2, 3]},
        usage_scope=UsageScope.RESEARCH_BACKTEST,
    )
    await session.flush()
    return revision.revision_id


async def _real_package(session) -> dict[str, str]:
    """A REAL approved package root the strategy pins (embedded-system kind)."""
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id=_ADMIN_PID,
        created_by_principal_id=_ADMIN_PID,
        package_kind=PackageKind.EMBEDDED_SYSTEM,
        input_contract={"resolver_key": "ta.rsi"},
        output_contract={"return": "series"},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.SYSTEM,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.flush()
    return {
        "root_id": root.entity_id,
        "revision_id": revision.revision_id,
        "content_hash": revision.content_hash,
    }


def _strategy_payload(market: dict[str, str], package: dict[str, str]) -> dict[str, Any]:
    return {
        "strategy_root_id": "strat_agent_seed",
        "display_name": "Agent research strategy",
        "rationale_family_id": "rf_agent",
        "data": {
            "instrument_id": "BTCUSDT",
            "market_dataset_root_id": market["root_id"],
            "market_dataset_revision_id": market["revision_id"],
            "market_dataset_content_hash": market["content_hash"],
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
                    "block_id": "ib_agent",
                    "display_order": 0,
                    "package_ref": {
                        "package_root_id": package["root_id"],
                        "package_revision_id": package["revision_id"],
                        "package_content_hash": package["content_hash"],
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


async def _agent_composition(session, market: dict[str, str], package: dict[str, str]) -> str:
    """The Agent composes its OWN Mainboard through the same commands a human
    uses (doc 18 §10 parity) — no UI involved anywhere."""
    mb = await mb_query.get_default_mainboard(session, AGENT)
    workspace_id = mb["workspace_id"]
    work_object = await mb_cmd.create_work_object(
        session, AGENT, object_kind="strategy", payload=_strategy_payload(market, package)
    )
    await mb_cmd.attach_mainboard_item(
        session,
        AGENT,
        workspace_id=workspace_id,
        root_id=work_object["root_id"],
        revision_id=work_object["revision_id"],
        item_kind="strategy",
    )
    await session.commit()
    return workspace_id


async def _directive_task_count(session) -> int:
    stmt = select(func.count()).select_from(AgentTask).where(AgentTask.source == "directive")
    return int((await session.execute(stmt)).scalar_one())


async def test_agent_loop_directive_to_hypothesis_without_ui(session) -> None:
    await _seed_runtime_and_principals(session)
    market = await _approved_market(session)
    research_revision_id = await _research_revision(session)
    package = await _real_package(session)
    await session.commit()
    composition_id = await _agent_composition(session, market, package)

    # 1. A human Admin queues a directive; the Coordinator (not a UI) consumes it
    #    at a safe checkpoint and materializes ONE autonomous follow-up task.
    directive = await al_repo.create_directive(
        session,
        author_principal_id=_ADMIN_PID,
        target_agent_id=ALPHA_AGENT_ID,
        related_task_id=None,
        text="Probe BTCUSDT funding-reversal robustness on the pinned bundle",
        priority=AgentTaskPriority.HIGH,
        correlation_id="corr_e2e_agent",
    )
    await session.commit()

    cycle = await run_coordinator_cycle(session)
    await session.commit()
    assert cycle["consumed"]["consumed"] == directive.directive_id
    task_id = cycle["followup_task_id"]
    assert task_id is not None
    # Stage 8 wiring: the plan step consumed the CR-08 exposure — with every
    # capability non-operational the gated tools are absent from the plan menu.
    assert "data_bundle.resolve" in cycle["exposed_tools"]
    assert "view_dataset.query" not in cycle["exposed_tools"]

    # AL-14: a second cycle never re-consumes the directive -> no duplicate task.
    again = await run_coordinator_cycle(session)
    await session.commit()
    assert again["consumed"].get("consumed") is None
    assert await _directive_task_count(session) == 1

    # 2. Bundle resolve under EXECUTION scope: the evidence gate admits the
    #    research_backtest revision and pins exact ids into a context manifest.
    bundle = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="data_bundle.resolve",
        policy_scope="execution",
        request={
            "market_revision_ids": [market["revision_id"]],
            "research_revisions": [
                {"revision_id": research_revision_id, "has_approved_feature_definition": False}
            ],
        },
        task_id=task_id,
        idempotency_key="e2e-agent-bundle-1",
    )
    await session.commit()
    assert bundle["status"] == "succeeded"
    assert bundle["market_revision_ids"] == [market["revision_id"]]
    assert bundle["research_revision_ids"] == [research_revision_id]
    manifest_id = bundle["context_manifest_id"]

    # 3. Backtest request through the gateway — the SAME admission command a
    #    human uses; Ready Check runs inside it and the manifest is pinned.
    run_req = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="backtest.request",
        policy_scope="execution",
        request={"composition_id": composition_id},
        task_id=task_id,
        input_manifest_id=manifest_id,
        idempotency_key="e2e-agent-run-1",
    )
    await session.commit()
    assert run_req["status"] == "succeeded"
    assert run_req["state"] == "queued"
    assert len(run_req["manifest_hash"]) == 64
    job = await session.get(Job, run_req["job_id"])
    assert job is not None and job.queue == "backtest"

    # 4. The engine worker materializes the immutable Result (CR-03 happy path).
    out = await run_backtest(session, run_req["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out["state"] == "succeeded"
    run = await session.get(BacktestRun, run_req["run_id"])
    assert str(run.state) == "succeeded" and run.result_id == out["result_id"]

    # 5. The Agent reads its run outcome through the gateway, never a UI query.
    queried = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="result.query",
        policy_scope="observation",
        request={"run_id": run_req["run_id"]},
        task_id=task_id,
    )
    await session.commit()
    assert queried["found"] is True and queried["result_id"] == out["result_id"]

    # 6. Hypothesis artifact with provenance links to the produced result.
    hypothesis = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.create",
        policy_scope="research",
        request={
            "title": "Funding reversal holds on pinned bundle",
            "mechanism": "Long bias after negative funding extremes persists OOS.",
            "evidence_refs": [out["result_id"]],
            "links": [
                {
                    "target_type": "backtest_result",
                    "target_id": out["result_id"],
                    "relation_type": "evidenced_by",
                }
            ],
        },
        task_id=task_id,
        idempotency_key="e2e-agent-hypothesis-1",
    )
    await session.commit()
    # NOTE: the merged response's "status" is the DOMAIN hypothesis status (the
    # handler payload shadows the envelope key); the durable tool-call row is
    # the authoritative call outcome.
    assert hypothesis["status"] == "exploring"
    call = await session.get(AgentToolCall, hypothesis["tool_call_id"])
    assert call is not None and str(call.status) == "succeeded"

    artifact = await session.get(HypothesisArtifact, hypothesis["artifact_id"])
    assert artifact is not None
    assert artifact.created_by_principal_id == _AGENT_PID
    assert artifact.source_task_id == task_id
    links = (
        (
            await session.execute(
                select(ArtifactLink).where(
                    ArtifactLink.source_artifact_id == hypothesis["artifact_id"]
                )
            )
        )
        .scalars()
        .all()
    )
    assert [(link.target_type, link.target_id) for link in links] == [
        ("backtest_result", out["result_id"])
    ]

    # Every Agent step above is a durable tool-call row (doc 18 §9.2).
    assert await _count(session, AgentToolCall) == 4


async def test_agent_cannot_run_backtest_on_human_composition(session) -> None:
    await _seed_runtime_and_principals(session)
    market = await _approved_market(session)
    package = await _real_package(session)
    await session.commit()

    # A HUMAN-owned ready composition (Admin owner).
    mb = await mb_query.get_default_mainboard(session, ADMIN)
    human_workspace = mb["workspace_id"]
    work_object = await mb_cmd.create_work_object(
        session, ADMIN, object_kind="strategy", payload=_strategy_payload(market, package)
    )
    await mb_cmd.attach_mainboard_item(
        session,
        ADMIN,
        workspace_id=human_workspace,
        root_id=work_object["root_id"],
        revision_id=work_object["revision_id"],
        item_kind="strategy",
    )
    await session.commit()

    runs_before = await _count(session, BacktestRun)
    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="backtest.request",
        policy_scope="execution",
        request={"composition_id": human_workspace},
    )
    await session.commit()

    # The denial is a durable REJECTED governance record — never a run/job/result.
    assert result["status"] == "rejected"
    call = await session.get(AgentToolCall, result["tool_call_id"])
    assert call is not None and str(call.status) == "rejected"
    assert await _count(session, BacktestRun) == runs_before
    assert await _count(session, BacktestResult) == 0
