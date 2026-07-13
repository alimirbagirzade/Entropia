"""Stage 8a — Integration flow (a): the full human pipeline end-to-end (Stage 8).

Auto-skips without PostgreSQL. One continuous chain over REAL ingested data (no
placeholder ids anywhere): Market + Research ingest -> approve -> Create Package
(Pre-Check -> candidate -> draft -> approve/publish) -> Strategy revision pinning
the published package + approved market revision -> Mainboard attach ->
Allocation -> Ready Check -> RUN -> succeeded Result -> Results History ->
Arrange Metrics -> soft-delete -> Trash -> Admin restore.

Stage 8 acceptance proven here:
- the run manifest pins EXACT revision ids resolved from the real ingest chain;
- identical re-run with the same idempotency key reuses the run (INF-04);
- a later approved market successor NEVER changes an existing manifest and a new
  run still pins the strategy revision's original refs (no 'latest' leak, INF-05);
- two runs over the same pins share one ``execution_key`` and yield identical
  metric values (pinned-manifest reproducibility);
- a failed run never yields Result/History (CR-03);
- every pipeline mutation grows the audit + outbox trails monotonically;
- soft-delete -> Trash entry -> Admin restore keeps the historical pinned
  manifest intact.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import create_package as cp_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import market_data as md_cmd
from entropia.application.commands import metric_profile as mp_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.commands import research_data as rd_cmd
from entropia.application.commands import strategy_draft as strat_cmd
from entropia.application.commands.deletion import restore_trash_entry
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.queries import backtest_run as backtest_query
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import metric_profile as mp_query
from entropia.application.queries import results_history as history_query
from entropia.domain.backtest.indicators import BUILTIN_ENTRY_MODEL
from entropia.domain.create_package.enums import (
    CreatePackageState,
    CreationMode,
    PrecheckScanStatus,
    SourceLanguage,
)
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    DeletionState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.metric_profile.registry import METRIC_REGISTRY
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    EventTimeSemantics,
    ResearchCategory,
    ResearchRevisionState,
    UsageScope,
)
from entropia.domain.research_data.value_objects import CategorySpec
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    BacktestResult,
    BacktestRun,
    DiagnosticArtifact,
    MetricDefinition,
    OutboxEvent,
    Principal,
)
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_RSI_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
_RSI_DEP = {"key": "ta.rsi", "signature": _RSI_SIG}


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _trail(session) -> tuple[int, int]:
    return await _count(session, AuditEvent), await _count(session, OutboxEvent)


def _assert_trail_grew(before: tuple[int, int], after: tuple[int, int], phase: str) -> None:
    assert after[0] > before[0], f"{phase}: no audit event was written"
    assert after[1] > before[1], f"{phase}: no outbox event was written"


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_metric_registry(session) -> None:
    for row in METRIC_REGISTRY:
        session.add(
            MetricDefinition(
                metric_code=row.metric_code,
                label=row.label,
                unit=row.unit,
                value_format=row.value_format,
                availability_status=row.availability_status,
                display_order=row.display_order,
                formula_version=row.formula_version,
                description=row.description,
                registry_version="v1",
            )
        )
    await session.flush()


# --------------------------------------------------------------------------- #
# Ingest + publish chain (all REAL ids)                                        #
# --------------------------------------------------------------------------- #


async def _approved_market(session) -> dict[str, str]:
    """Ingest + approve one market dataset; return its real pinned identifiers."""
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
    return {
        "root_id": root.entity_id,
        "revision_id": revision.revision_id,
        "content_hash": revision.content_hash,
    }


async def _approved_research(session, market_root_id: str) -> str:
    """Ingest + approve one research dataset linked to the approved market."""
    root, _ = await rd_cmd.create_research_dataset(
        session,
        ADMIN,
        market_entity_id=market_root_id,
        payload={"series": [0.1, 0.2]},
        category=CategorySpec(category=ResearchCategory.OPEN_INTEREST),
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        display_name="OI",
    )
    await session.flush()
    revision = await rd_repo.get_revision(session, root.current_revision_id or "")
    assert revision is not None
    revision.revision_state = ResearchRevisionState.VERIFIED
    revision.event_time_semantics = EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP
    revision.available_time_policy = AvailableTimePolicy.FIXED_DELAY
    revision.available_delay_seconds = 120
    await session.flush()
    approve = await rd_cmd.approve_research_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    assert approve["revision_state"] == "approved"
    return revision.revision_id


async def _seed_python_resolver(session, *, key: str = "ta.rsi") -> str:
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        package_kind=PackageKind.EMBEDDED_SYSTEM,
        input_contract={"resolver_key": key},
        output_contract={"return": "series"},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.SYSTEM,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    esp_repo.add_resolver_contract(
        session,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        canonical_key=key,
        signature=_RSI_SIG,
        runtime_adapter=RuntimeAdapter.PYTHON,
    )
    esp_repo.upsert_registry_entry(
        session,
        canonical_key=key,
        package_entity_id=root.entity_id,
        runtime_adapter=RuntimeAdapter.PYTHON,
        trust_state=ResolverTrustState.TRUSTED_ACTIVE,
        trusted_active_revision_id=revision.revision_id,
        updated_by_principal_id="user_admin",
    )
    return revision.revision_id


async def _seed_family(session) -> str:
    root, _detail, _revision = await rationale_repo.create_family(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        display_name="Reversal / Mean Reversion",
        normalized_name="reversal / mean reversion",
        subfamilies=[],
        compatible_output_types=["directional_signal"],
        display_color="#FFD1DC",
        change_note=None,
    )
    return root.entity_id


async def _published_package(session, family_id: str) -> dict[str, str]:
    """Full Create Package pipeline: request -> Pre-Check -> candidate -> draft
    -> Admin approve/publish. Returns the published pinned identifiers."""
    created = await cp_cmd.create_package_request(
        session,
        OWNER,
        package_type="indicator",
        creation_mode=CreationMode.TRANSLATE_EXISTING_CODE,
        source_language=SourceLanguage.PINESCRIPT,
        other_language_label=None,
        target_runtime=RuntimeAdapter.PYTHON,
        request_body="//@version=5\nindicator('rsi')\nta.rsi(close, 14)",
        output_contract={"kind": "directional_signal"},
        rationale_family_id=family_id,
        declared_dependencies=[_RSI_DEP],
        # The pipeline under test is run -> history -> metrics -> trash; this package
        # asserts no equivalence, so publish needs no baseline (GAP-07b mode-aware gate).
        equivalence_claim=False,
    )
    await session.commit()
    request_id = created["request_id"]

    pre = await cp_cmd.run_precheck(session, OWNER, request_id=request_id)
    await session.commit()
    assert pre["status"] == str(PrecheckScanStatus.PASSED)

    sent = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    await session.commit()
    assert sent["state"] == str(CreatePackageState.CANDIDATE_READY)

    draft = await cp_cmd.create_draft_from_candidate(
        session, OWNER, request_id=request_id, expected_candidate_hash=sent["candidate_hash"]
    )
    await session.commit()

    # GAP-07: publish requires passing validation evidence on the draft revision.
    validated = await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()
    assert validated["state"] == str(CreatePackageState.ELIGIBLE_FOR_APPROVAL)

    published = await cp_cmd.approve_and_publish(
        session,
        ADMIN,
        request_id=request_id,
        expected_head_revision_id=draft["draft_revision_id"],
    )
    await session.commit()
    assert published["approval_state"] == str(ApprovalState.APPROVED)
    assert published["visibility_scope"] == str(VisibilityScope.PUBLISHED)

    revision = await pkg_repo.get_revision(session, draft["draft_revision_id"])
    assert revision is not None
    return {
        "root_id": draft["package_root_id"],
        "revision_id": draft["draft_revision_id"],
        "content_hash": revision.content_hash,
    }


def _strategy_payload(
    market: dict[str, str], package: dict[str, str], family_id: str
) -> dict[str, Any]:
    """A fully valid StrategyConfig pinning ONLY real ingested identifiers."""
    return {
        "strategy_root_id": "strat_placeholder",
        "display_name": "E2E pipeline strategy",
        "rationale_family_id": family_id,
        "data": {
            "instrument_id": "BTCUSDT",
            "market_dataset_root_id": market["root_id"],
            "market_dataset_revision_id": market["revision_id"],
            "market_dataset_content_hash": market["content_hash"],
            "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
            "initial_capital": "10000.00",
            "execution": {"entry_timing": "next_candle_open", "exit_timing": "next_candle_close"},
            "order_config": {"type": "market_order", "limit": None},
            "costs": {
                "commission": "0.001",
                "spread": "0.0002",
                "slippage_mode": "percentage_slippage",
                "slippage_value": "0.01",
            },
            "intrabar_policy": {"tick_policy": "inherit"},
            "funding": {"enabled": False},
        },
        "position_entry_logic": {
            "direction_mode": "long_and_short",
            "signal_block": {
                "rule": "required_indicator_blocks_only",
                "min_supporting_count": None,
            },
            "indicator_blocks": [
                {
                    "block_id": "ib_e2e",
                    "display_order": 0,
                    "enabled": True,
                    "package_ref": {
                        "package_root_id": package["root_id"],
                        "package_revision_id": package["revision_id"],
                        "package_content_hash": package["content_hash"],
                    },
                    "trigger_source": "indicator_native_trigger",
                    "direction": "long",
                    "timeframe": "same_as_base_tf",
                    "validity": "3_candles",
                    "requirement": "required",
                    "condition_block_rule": None,
                    "min_supporting_condition_count": None,
                    "condition_blocks": None,
                    "parameter_overrides": None,
                }
            ],
        },
        "position_exit_logic": {
            "applies_to_direction": "long_and_short",
            "close_percentage": "100",
            "partial_aftermath": "move_stop_to_entry",
            "signal_block": None,
            "indicator_blocks": None,
        },
        "protection_stop_logic": {
            "percentage_stop": {"enabled": True, "loss_percentage": "1.0"},
            "trailing_stop": None,
            "absolute_stop": None,
        },
        "position_sizing": {
            "method": "base_position_size",
            "base_position_size": "100.0",
            "risk_based": None,
            "formula_based": None,
            "signal_strength_adjustment": "no_adjustment",
            "leverage_mode": "isolated",
            "position_size_limits": None,
        },
        "scaling_logic": {
            "enabled": False,
            "timeframe": "same_as_base_tf",
            "method": None,
            "price_scaling": None,
            "logic_scaling": None,
            "add_size": "percent_of_initial",
            "add_size_value": None,
            "scaling_limits": None,
        },
        "restrictions_filters": {"rule": "any", "filters": []},
        "conflict_position_handling": {
            "overlapping_signal_policy": "queue_sequential",
            "same_direction_stacking": "allow_stacking",
            "opposite_direction_hedge": "allow_hedge",
            "exit_on_opposite_signal": True,
        },
    }


def _e2e_bars(_source: Any) -> Iterator[list[dict[str, Any]]]:
    """Deterministic OHLCV bars for the worker's bar-replay (S3-free injection).

    Replaces the real S3-backed ``iter_bar_batches`` at the worker seam so the flow
    exercises resolve -> replay -> materialize without object storage. 20 flat bars
    fill the breakout window, then an upside breakout and a stop-out yield one real,
    reproducible trade."""
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


async def _ready_pipeline(session) -> dict[str, Any]:
    """Run the whole ingest -> publish -> compose -> allocate chain; return every
    pinned identifier plus the composition ready to RUN."""
    await _seed_principals(session)
    trail = await _trail(session)

    market = await _approved_market(session)
    # Slice B: the bar-replay worker resolves the strategy's pinned market revision
    # to a processed Parquet asset (INF-12). Seed that metadata row so resolution
    # succeeds; the bar bytes themselves are injected via ``_e2e_bars``.
    md_repo.add_processed_asset(
        session,
        entity_id=market["root_id"],
        object_key=f"market/processed/{market['root_id']}/e2e.parquet",
        content_digest="e2e-bars",
        size_bytes=4096,
        revision_id=market["revision_id"],
        row_count=22,
    )
    await session.flush()
    research_revision_id = await _approved_research(session, market["root_id"])
    await session.commit()
    after_ingest = await _trail(session)
    _assert_trail_grew(trail, after_ingest, "ingest+approve")

    resolver_revision_id = await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()

    package = await _published_package(session, family_id)
    after_publish = await _trail(session)
    _assert_trail_grew(after_ingest, after_publish, "package publish")

    draft = await strat_cmd.create_strategy_draft(
        session,
        OWNER,
        display_name="E2E pipeline strategy",
        rationale_family_id=family_id,
        initial_payload=_strategy_payload(market, package, family_id),
    )
    saved = await strat_cmd.save_strategy_revision(
        session, OWNER, draft_id=draft["draft_id"], expected_draft_row_version=0
    )
    await session.commit()
    assert saved["revision_number"] == 1

    mb = await mb_query.get_default_mainboard(session, OWNER)
    workspace_id = mb["workspace_id"]
    await mb_cmd.attach_mainboard_item(
        session,
        OWNER,
        workspace_id=workspace_id,
        root_id=saved["strategy_root_id"],
        revision_id=saved["mirror_revision_id"],
        item_kind="strategy",
    )
    await session.commit()
    after_attach = await _trail(session)
    _assert_trail_grew(after_publish, after_attach, "strategy save + attach")

    items = (await mb_query.get_default_mainboard(session, OWNER))["items"]
    assert len(items) == 1
    await alloc_cmd.upsert_allocation_draft(
        session,
        OWNER,
        composition_id=workspace_id,
        expected_row_version=None,
        enabled=True,
        initial_capital={"amount": "10000", "currency": "USDT"},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent="10",
        entries=[
            {
                "composition_item_id": items[0]["item_id"],
                "active": True,
                "equity_share_percent": "90",
            }
        ],
    )
    await session.commit()
    report = await alloc_cmd.validate_allocation_draft(session, OWNER, composition_id=workspace_id)
    await session.commit()
    assert report["valid"] is True
    await alloc_cmd.create_allocation_revision(
        session, OWNER, composition_id=workspace_id, expected_row_version=1
    )
    await session.commit()

    ready = await readiness_cmd.run_readiness_check(session, OWNER, composition_id=workspace_id)
    await session.commit()
    assert ready["summary"]["blocker_count"] == 0

    return {
        "workspace_id": workspace_id,
        "market": market,
        "research_revision_id": research_revision_id,
        "resolver_revision_id": resolver_revision_id,
        "family_id": family_id,
        "package": package,
        "strategy": saved,
        "ready": ready,
    }


# --------------------------------------------------------------------------- #
# Flow (a): the full pipeline, Trash round-trip included                        #
# --------------------------------------------------------------------------- #


async def test_full_pipeline_run_history_metrics_trash_restore(session) -> None:
    await _seed_metric_registry(session)
    ctx = await _ready_pipeline(session)
    workspace_id = ctx["workspace_id"]

    before_run = await _trail(session)
    admit = await backtest_cmd.request_backtest_run(
        session,
        OWNER,
        composition_id=workspace_id,
        ready_report_id=ctx["ready"]["report_id"],
        idempotency_key="e2e-run-1",
    )
    await session.commit()
    assert admit["state"] == "queued"
    _assert_trail_grew(before_run, await _trail(session), "run admission")

    # INF-04: the identical re-run replays the SAME admission (no duplicate run).
    replay = await backtest_cmd.request_backtest_run(
        session,
        OWNER,
        composition_id=workspace_id,
        ready_report_id=ctx["ready"]["report_id"],
        idempotency_key="e2e-run-1",
    )
    await session.commit()
    assert replay["run_id"] == admit["run_id"]
    assert await _count(session, BacktestRun) == 1

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out["state"] == "succeeded"
    result_id = out["result_id"]

    # Slice C: the pinned RSI indicator package drove REAL built-in indicator compute
    # (native trigger), not the breakout proxy — proven end-to-end through the job.
    diag = (
        await session.execute(
            select(DiagnosticArtifact).where(DiagnosticArtifact.result_id == result_id)
        )
    ).scalar_one()
    assert diag.content["entry_model"] == BUILTIN_ENTRY_MODEL

    # The manifest pins the EXACT mirror revision that the ingest chain produced.
    manifest = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert manifest is not None and manifest.manifest_hash == admit["manifest_hash"]
    pinned = {
        item["root_id"]: item["selected_revision_id"]
        for item in manifest.manifest["mainboard_items"]
    }
    assert pinned == {ctx["strategy"]["strategy_root_id"]: ctx["strategy"]["mirror_revision_id"]}

    # Result detail resolves through the same pinned manifest.
    view = await backtest_query.get_backtest_result(session, OWNER, result_id=result_id)
    assert view["manifest"]["manifest_hash"] == admit["manifest_hash"]
    assert len(view["metrics"]) == 9

    # Results History lists the succeeded result for its owner.
    page = await history_query.list_backtest_results(session, OWNER)
    assert [row["result_id"] for row in page["items"]] == [result_id]

    # Arrange Metrics: the owner forks a personal profile over the registry.
    applied = await mp_cmd.create_metric_profile_revision(
        session,
        OWNER,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit", "win_rate"],
        is_locked=False,
    )
    await session.commit()
    assert applied["is_personal"] is True
    resolved = await mp_query.get_resolved_metric_profile(session, OWNER)
    assert resolved["selected_metric_codes"] == ["net_profit", "win_rate"]

    # Soft-delete -> Trash entry -> restore; the pinned manifest never breaks.
    result = await session.get(BacktestResult, result_id)
    await backtest_cmd.soft_delete_backtest_result(
        session, OWNER, result_id=result_id, expected_row_version=result.row_version
    )
    await session.commit()
    page = await history_query.list_backtest_results(session, OWNER)
    assert page["items"] == []

    entry = await trash_repo.get_recoverable_entry_for_entity(session, result_id)
    assert entry is not None and entry.entity_type == "backtest_result"

    restored = await restore_trash_entry(session, ADMIN, trash_entry_id=entry.id)
    await session.commit()
    assert restored["deletion_state"] == "active"

    result = await session.get(BacktestResult, result_id)
    assert result.deletion_state == DeletionState.ACTIVE.value

    page = await history_query.list_backtest_results(session, OWNER)
    assert [row["result_id"] for row in page["items"]] == [result_id]

    # The historical manifest survived the whole Trash round-trip untouched.
    manifest_after = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert manifest_after.manifest_hash == admit["manifest_hash"]
    assert manifest_after.manifest["mainboard_items"] == manifest.manifest["mainboard_items"]


# --------------------------------------------------------------------------- #
# CR-03: a failed run never yields Result/History                              #
# --------------------------------------------------------------------------- #


async def test_failed_run_yields_no_result_and_no_history(session) -> None:
    ctx = await _ready_pipeline(session)
    admit = await backtest_cmd.request_backtest_run(
        session, OWNER, composition_id=ctx["workspace_id"]
    )
    await session.commit()

    # Tamper the pinned revision so manifest resolution fails inside the worker
    # (no 'latest' fallback exists to silently save the run, doc 15 §11).
    manifest = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    doc = dict(manifest.manifest)
    items = [dict(item) for item in doc["mainboard_items"]]
    items[0]["selected_revision_id"] = "worev_missing"
    doc["mainboard_items"] = items
    manifest.manifest = doc
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "failed"
    run = await session.get(BacktestRun, admit["run_id"])
    assert str(run.state) == "failed" and run.result_id is None
    assert await _count(session, BacktestResult) == 0
    page = await history_query.list_backtest_results(session, OWNER)
    assert page["items"] == []


# --------------------------------------------------------------------------- #
# INF-05 / reproducibility: successor revisions never leak into manifests       #
# --------------------------------------------------------------------------- #


async def test_market_successor_never_leaks_and_rerun_is_reproducible(session) -> None:
    ctx = await _ready_pipeline(session)
    workspace_id = ctx["workspace_id"]

    first = await backtest_cmd.request_backtest_run(session, OWNER, composition_id=workspace_id)
    await session.commit()
    out1 = await run_backtest(session, first["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out1["state"] == "succeeded"

    # The market head moves AFTER the run: successor revision, verified+approved.
    market_root_id = ctx["market"]["root_id"]
    successor = await md_cmd.create_successor_revision(
        session,
        ADMIN,
        entity_id=market_root_id,
        payload={"instrument": "BTCUSDT", "candles": [4, 5, 6]},
        market_data_type=MarketDataType.OHLCV,
    )
    await session.commit()
    successor.revision_state = MarketRevisionState.VERIFIED
    await session.flush()
    await md_cmd.approve_market_dataset_revision(
        session, ADMIN, entity_id=market_root_id, revision_id=successor.revision_id
    )
    await session.commit()
    root = await md_repo.get_dataset_root(session, market_root_id)
    assert root.current_revision_id == successor.revision_id  # head really moved

    # INF-05: the existing manifest is unchanged; a new run over the unchanged
    # composition pins the SAME execution content (no 'latest' resolution).
    second = await backtest_cmd.request_backtest_run(session, OWNER, composition_id=workspace_id)
    await session.commit()
    out2 = await run_backtest(session, second["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out2["state"] == "succeeded"
    assert second["run_id"] != first["run_id"]

    manifest1 = await bt_repo.get_manifest_by_run(session, first["run_id"])
    manifest2 = await bt_repo.get_manifest_by_run(session, second["run_id"])
    assert manifest2.execution_key == manifest1.execution_key
    assert manifest2.manifest["mainboard_items"] == manifest1.manifest["mainboard_items"]

    # Deterministic engine: identical pins -> identical metric values.
    view1 = await backtest_query.get_backtest_result(session, OWNER, result_id=out1["result_id"])
    view2 = await backtest_query.get_backtest_result(session, OWNER, result_id=out2["result_id"])
    metrics1 = {m["key"]: m["value"] for m in view1["metrics"]}
    metrics2 = {m["key"]: m["value"] for m in view2["metrics"]}
    assert metrics1 == metrics2

    # The composition pin is still the ORIGINAL strategy mirror revision.
    assert (
        manifest2.manifest["mainboard_items"][0]["selected_revision_id"]
        == ctx["strategy"]["mirror_revision_id"]
    )
