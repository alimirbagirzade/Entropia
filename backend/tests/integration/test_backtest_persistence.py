"""Stage 5a — RUN + Backtest Result against a real database (doc 15 §7-§9, §16).

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py). A
ready composition is seeded by reusing the 3a Mainboard commands; the RUN admission
+ engine worker + result read model then run on it. Covers: admission -> QUEUED run
+ hash-pinned manifest + durable job; worker -> SUCCEEDED + immutable Result +
summary + 9 metrics + artifacts (L1 FK proof: children persist under the result);
409 COMPOSITION_STALE; 422 READINESS_BLOCKED leaves no run/manifest/job; idempotent
duplicate RUN; retry FAILED -> new run_id + retry_of + new manifest_hash; worker
FAILED on an unresolved pin (no 'latest' fallback, no Result); result soft delete;
foreign-owner 403; guest 401; and the OBJECT_IN_ACTIVE_RUN soft-delete guard.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.queries import backtest_run as backtest_query
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    ResolutionKind,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    BacktestRun,
    DiagnosticArtifact,
    Job,
    MetricValueRow,
    PackageRevision,
    Principal,
    ResultSummary,
)
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import (
    AccessDeniedError,
    BacktestResultNotFoundError,
    CompositionStaleError,
    ObjectInActiveRunError,
    ReadinessBlockedError,
    UnauthenticatedError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_principals(session) -> None:
    for pid in ("user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


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


def _strategy_payload(
    market_root_id: str,
    market_revision_id: str,
    market_hash: str,
    indicator_revision_id: str = "pkg_rev_1",
    backtest_range: dict[str, str] | None = None,
    instrument_id: str = "BTCUSDT",
) -> dict[str, Any]:
    return {
        "strategy_root_id": "strat_root_seed",
        "display_name": "Seed strategy",
        "rationale_family_id": "rf_1",
        "data": {
            "instrument_id": instrument_id,
            "market_dataset_root_id": market_root_id,
            "market_dataset_revision_id": market_revision_id,
            "market_dataset_content_hash": market_hash,
            "backtest_range": backtest_range
            or {"start": "2024-01-01T00:00:00Z", "end": "2024-06-01T00:00:00Z"},
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
                    "block_id": "ib_1",
                    "display_order": 0,
                    "package_ref": {
                        "package_root_id": "pkg_root_1",
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


async def _empty_composition(session, actor: Actor) -> str:
    mb = await mb_query.get_default_mainboard(session, actor)
    await session.commit()
    return mb["workspace_id"]


async def _ready_composition(
    session,
    actor: Actor,
    *,
    base_tf: str | None = None,
    resolvable_indicator: bool = True,
    market_instrument_id: str | None = None,
    strategy_instrument_id: str = "BTCUSDT",
    backtest_range: dict[str, str] | None = None,
) -> tuple[str, str, str]:
    workspace_id = await _empty_composition(session, actor)
    # Slice B: the strategy pins a REAL market revision (FK-valid entity) and the
    # bar-replay worker resolves its processed Parquet asset (INF-12); the bar bytes
    # are injected via ``_e2e_bars``. ``base_tf`` pins the revision's bar timeframe
    # so the worker can surface it in the result summary. ``market_instrument_id``
    # pins the revision's dataset-level instrument identity (F-05 GAP-16 cross-check);
    # ``None`` (the default) mirrors legacy/unset revisions.
    market_root, market_rev = await md_repo.create_market_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        market_data_type=MarketDataType.OHLCV,
        payload={"note": "seed bars"},
        instrument_id=market_instrument_id,
    )
    if base_tf is not None:
        market_rev.resolution_kind = ResolutionKind.BAR
        market_rev.resolution_value = base_tf
    # GAP-01: readiness now requires the pinned market revision to be ACTIVE+APPROVED.
    market_rev.revision_state = MarketRevisionState.APPROVED
    await session.flush()
    md_repo.add_processed_asset(
        session,
        entity_id=market_root.entity_id,
        object_key=f"market/processed/{market_root.entity_id}/seed.parquet",
        content_digest="seed-bars",
        size_bytes=4096,
        revision_id=market_rev.revision_id,
        row_count=22,
    )
    await session.flush()
    # F-06: the strategy pins a REAL indicator package. When ``resolvable_indicator``
    # its dependency snapshot resolves a directional key (ta.sma) so
    # ``resolve_indicator_plan`` yields a computable entry — the worker's fail-closed
    # gate never blocks the happy path, and the run drives real built-in compute (not
    # the removed breakout proxy). When not, a recognized-but-non-directional key
    # (ta.atr) leaves the block unresolved — the upfront Ready Check gate blocks RUN.
    indicator_key = "ta.sma" if resolvable_indicator else "ta.atr"
    _reg, _pkg_root, pkg_rev = await pkg_repo.create_package(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        package_kind=PackageKind.INDICATOR,
        input_contract={"source": "close"},
        output_contract={"kind": "directional_signal"},
        dependency_snapshot={"resolved": [{"call": indicator_key, "canonical_key": indicator_key}]},
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.flush()
    work_object = await mb_cmd.create_work_object(
        session,
        actor,
        object_kind="strategy",
        payload=_strategy_payload(
            market_root.entity_id,
            market_rev.revision_id,
            market_rev.content_hash,
            indicator_revision_id=pkg_rev.revision_id,
            backtest_range=backtest_range,
            instrument_id=strategy_instrument_id,
        ),
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
    return workspace_id, work_object["root_id"], work_object["revision_id"]


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


# --------------------------------------------------------------------------- #
# Happy path: admission -> worker -> immutable result                          #
# --------------------------------------------------------------------------- #


async def test_admission_queues_run_and_worker_materializes_result(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    assert admit["state"] == "queued"
    assert len(admit["manifest_hash"]) == 64
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None and str(run.state) == "queued"
    manifest = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert manifest is not None and manifest.manifest_hash == admit["manifest_hash"]
    job = await session.get(Job, admit["job_id"])
    assert job is not None and job.queue == "backtest"

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "succeeded"
    run = await session.get(BacktestRun, admit["run_id"])
    assert str(run.state) == "succeeded" and run.result_id == out["result_id"]

    # L1 FK proof: the result root + its metric/artifact children persist together.
    result = await session.get(BacktestResult, out["result_id"])
    assert result is not None and result.deletion_state == "active"
    assert await _count(session, MetricValueRow) == 9

    view = await backtest_query.get_backtest_result(session, USER1, result_id=out["result_id"])
    assert len(view["metrics"]) == 9
    assert view["artifact_counts"]["trades"] >= 1
    assert view["manifest"]["manifest_hash"] == admit["manifest_hash"]

    run_view = await backtest_query.get_backtest_run(session, USER1, run_id=admit["run_id"])
    assert run_view["state"] == "succeeded" and run_view["result_id"] == out["result_id"]


async def test_result_summary_carries_pinned_market_timeframe(session) -> None:
    # The worker resolves the pinned revision's bar timeframe (resolution_kind=BAR)
    # and it lands verbatim in the persisted summary + the result read model.
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1, base_tf="1m")
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "succeeded"
    summary_row = (
        await session.execute(
            select(ResultSummary).where(ResultSummary.result_id == out["result_id"])
        )
    ).scalar_one()
    assert summary_row.timeframe == "1m"
    assert summary_row.headline["timeframe"] == "1m"
    view = await backtest_query.get_backtest_result(session, USER1, result_id=out["result_id"])
    assert view["summary"]["timeframe"] == "1m"


async def test_result_summary_timeframe_none_when_revision_not_bar_timeframed(session) -> None:
    # A revision without a bar resolution (event-based / unknown) surfaces an honest
    # None — the worker never guesses a timeframe from the bars (L4).
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "succeeded"
    summary_row = (
        await session.execute(
            select(ResultSummary).where(ResultSummary.result_id == out["result_id"])
        )
    ).scalar_one()
    assert summary_row.timeframe is None


# --------------------------------------------------------------------------- #
# F-05: backtest_range + instrument physical filter                            #
# --------------------------------------------------------------------------- #


async def test_result_period_matches_actually_processed_bars(session) -> None:
    # F-05 acceptance: "Manifest range/instrument values match the data actually
    # processed." period_start/end reflect the REAL first/last replayed bar
    # timestamps (2024-02-01..2024-02-22), not the wider requested backtest_range
    # (2024-01-01..2024-06-01).
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "succeeded"
    summary_row = (
        await session.execute(
            select(ResultSummary).where(ResultSummary.result_id == out["result_id"])
        )
    ).scalar_one()
    assert summary_row.period_start == "2024-02-01T00:00:00Z"
    assert summary_row.period_end == "2024-02-22T00:00:00Z"


async def test_narrower_backtest_range_processes_fewer_bars(session) -> None:
    # F-05 acceptance: "Different selected ranges over the same dataset process
    # only their respective bars." A range that excludes the breakout window
    # (only 10 of the 20 flat warm-up bars survive) leaves the breakout proxy
    # without a full look-back -> zero trades, proving the filter is PHYSICAL,
    # not cosmetic.
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(
        session,
        USER1,
        backtest_range={"start": "2024-02-11T00:00:00Z", "end": "2024-02-22T00:00:00Z"},
    )
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "succeeded"
    summary_row = (
        await session.execute(
            select(ResultSummary).where(ResultSummary.result_id == out["result_id"])
        )
    ).scalar_one()
    assert summary_row.period_start == "2024-02-11T00:00:00Z"
    assert summary_row.period_end == "2024-02-22T00:00:00Z"
    assert summary_row.total_trades == 0
    diagnostics = await _run_diagnostics(session, out["result_id"])
    assert diagnostics["bars_processed"] == 12  # 2024-02-11..2024-02-22 inclusive


async def test_worker_fails_closed_when_range_excludes_every_bar(session) -> None:
    # F-05 acceptance: "Reject an empty or invalid filtered range explicitly."
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(
        session,
        USER1,
        backtest_range={"start": "2025-01-01T00:00:00Z", "end": "2025-02-01T00:00:00Z"},
    )
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "failed"
    assert out["failure_code"] == "RUN_FAILED_EMPTY_FILTERED_RANGE"
    run = await session.get(BacktestRun, admit["run_id"])
    assert str(run.state) == "failed" and run.result_id is None
    assert await _count(session, BacktestResult) == 0


async def test_worker_fails_closed_on_unparseable_backtest_range(session) -> None:
    # An out-of-calendar timestamp ("month 13") passes the DateRange field's
    # ``start<end`` regex/lexicographic checks at save time but is not a real
    # ISO-8601 instant — the worker must reject it explicitly, never guess.
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(
        session,
        USER1,
        backtest_range={"start": "2024-01-01T00:00:00Z", "end": "2024-13-40T99:99:00Z"},
    )
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "failed"
    assert out["failure_code"] == "RUN_FAILED_INVALID_BACKTEST_RANGE"
    assert await _count(session, BacktestResult) == 0


async def test_worker_fails_closed_on_instrument_mismatch(session) -> None:
    # F-05 acceptance: "Bars from unselected instruments never enter decisions,
    # positions, metrics, or artifacts." The pinned revision is scoped to a
    # DIFFERENT instrument than the strategy's selected one.
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(
        session,
        USER1,
        market_instrument_id="ETHUSDT",
        strategy_instrument_id="BTCUSDT",
    )
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "failed"
    assert out["failure_code"] == "RUN_FAILED_INSTRUMENT_MISMATCH"
    run = await session.get(BacktestRun, admit["run_id"])
    assert str(run.state) == "failed" and run.result_id is None
    assert await _count(session, BacktestResult) == 0


async def test_matching_instrument_scoped_revision_still_succeeds(session) -> None:
    # Regression: a revision whose instrument_id IS set and matches the strategy's
    # selected instrument runs exactly like the legacy/unset-instrument happy path.
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(
        session,
        USER1,
        market_instrument_id="BTCUSDT",
        strategy_instrument_id="BTCUSDT",
    )
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "succeeded"


# --------------------------------------------------------------------------- #
# Stale / blocked admission                                                    #
# --------------------------------------------------------------------------- #


async def test_run_rejected_when_composition_stale(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    with pytest.raises(CompositionStaleError):
        await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, expected_fingerprint="wrong_fp"
        )


async def test_empty_composition_blocks_run_and_leaves_nothing(session) -> None:
    await _seed_principals(session)
    composition_id = await _empty_composition(session, USER1)
    with pytest.raises(ReadinessBlockedError):
        await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.rollback()
    assert await _count(session, BacktestRun) == 0
    assert await _count(session, Job) == 0


# --------------------------------------------------------------------------- #
# Idempotency                                                                  #
# --------------------------------------------------------------------------- #


async def test_duplicate_run_is_idempotent(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)

    first = await backtest_cmd.request_backtest_run(
        session, USER1, composition_id=composition_id, idempotency_key="run-key-1"
    )
    await session.commit()
    second = await backtest_cmd.request_backtest_run(
        session, USER1, composition_id=composition_id, idempotency_key="run-key-1"
    )
    await session.commit()

    assert first["run_id"] == second["run_id"]
    assert await _count(session, BacktestRun) == 1
    assert await _count(session, Job) == 1


# --------------------------------------------------------------------------- #
# Worker manifest-resolution failure + retry                                   #
# --------------------------------------------------------------------------- #


async def test_worker_fails_on_unresolved_pin_and_retry_creates_new_run(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    # Tamper the (normally immutable) manifest to pin a revision that cannot resolve,
    # exercising the worker's no-'latest'-fallback guard (doc 15 §11, §15).
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
    assert out["failure_code"] == "RUN_FAILED_MANIFEST_RESOLUTION"
    run = await session.get(BacktestRun, admit["run_id"])
    assert str(run.state) == "failed" and run.result_id is None
    assert await _count(session, BacktestResult) == 0  # CR-03: no Result on failure

    retry = await backtest_cmd.retry_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.commit()

    assert retry["run_id"] != admit["run_id"]
    assert retry["retry_of_run_id"] == admit["run_id"]
    assert retry["manifest_hash"] != admit["manifest_hash"]
    new_run = await session.get(BacktestRun, retry["run_id"])
    assert new_run.retry_of_run_id == admit["run_id"] and str(new_run.state) == "queued"


async def test_run_admission_blocked_when_indicator_dependency_unresolved(session) -> None:
    """F-06 upfront RUN gate: RUN cannot start with an unresolved required package.

    The strategy pins an indicator whose dependency is recognized but non-directional
    (ta.atr), so no computable entry resolves. Admission runs Ready Check first and
    refuses to queue a run — the blocker names the strategy scope (spec F-06)."""
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(
        session, USER1, resolvable_indicator=False
    )
    with pytest.raises(ReadinessBlockedError) as excinfo:
        await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)

    codes = {detail["code"] for detail in excinfo.value.details}
    assert "STRATEGY_INDICATOR_UNRESOLVED" in codes
    # No run/manifest was created — RUN never started (spec F-06 acceptance).
    assert await _count(session, BacktestRun) == 0


async def test_worker_fails_closed_when_indicator_becomes_unresolved(session) -> None:
    """F-06 defence in depth: even if a bypassed/stale readiness reaches the worker,
    the engine fails fast instead of substituting the breakout proxy.

    A resolvable run is admitted normally, then the pinned indicator package loses its
    directional dependency (simulating a bypassed Ready Check). The worker must
    terminate FAILED with UNRESOLVED_DEPENDENCY and materialize NO Result — metrics
    from a strategy the user did not select can never be produced (spec F-06)."""
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    # Break the pinned indicator's resolution AFTER admission (readiness already passed).
    pkg = (
        await session.execute(
            select(PackageRevision).where(PackageRevision.package_kind == PackageKind.INDICATOR)
        )
    ).scalar_one()
    pkg.dependency_snapshot = {"resolved": [{"call": "ta.atr", "canonical_key": "ta.atr"}]}
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "failed"
    assert out["failure_code"] == "RUN_FAILED_UNRESOLVED_DEPENDENCY"
    run = await session.get(BacktestRun, admit["run_id"])
    assert str(run.state) == "failed" and run.result_id is None
    assert await _count(session, BacktestResult) == 0  # CR-03: no Result on failure


# --------------------------------------------------------------------------- #
# Result soft delete                                                           #
# --------------------------------------------------------------------------- #


async def test_soft_delete_result_removes_projection(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    result = await session.get(BacktestResult, out["result_id"])
    deleted = await backtest_cmd.soft_delete_backtest_result(
        session, USER1, result_id=out["result_id"], expected_row_version=result.row_version
    )
    await session.commit()
    assert deleted["deletion_state"] == "soft_deleted"

    with pytest.raises(BacktestResultNotFoundError):
        await backtest_query.get_backtest_result(session, USER1, result_id=out["result_id"])


# --------------------------------------------------------------------------- #
# Authorization + active-run guard                                             #
# --------------------------------------------------------------------------- #


async def test_foreign_owner_cannot_run(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    with pytest.raises(AccessDeniedError):
        await backtest_cmd.request_backtest_run(session, USER2, composition_id=composition_id)


async def test_guest_cannot_run(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    with pytest.raises(UnauthenticatedError):
        await backtest_cmd.request_backtest_run(
            session, Actor.anonymous(), composition_id=composition_id
        )


async def test_active_run_blocks_work_object_delete(session) -> None:
    await _seed_principals(session)
    composition_id, root_id, _rev = await _ready_composition(session, USER1)
    await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    with pytest.raises(ObjectInActiveRunError):
        await mb_cmd.soft_delete_work_object(session, USER1, root_id=root_id)


async def test_worker_is_redelivery_idempotent(session) -> None:
    # Dramatiq is at-least-once: a redelivered message for a run that already
    # succeeded must return the durable outcome and NOT run the engine again (a
    # second create_result would violate UNIQUE(backtest_result.run_id)).
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    first = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert first["state"] == "succeeded"

    second = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert second["state"] == "succeeded"
    assert second["result_id"] == first["result_id"]


# --------------------------------------------------------------------------- #
# GAP-02: shared-pool allocation execution flows end-to-end (doc 13 §8.3)      #
# --------------------------------------------------------------------------- #


async def _enable_allocation(session, actor: Actor, composition_id: str, *, amount: str) -> None:
    """Enable a shared-pool allocation plan capitalising the composition's sole
    strategy item at 100% share (doc 13 §7). Bound by the item's composition_item_id."""
    items = await mb_repo.list_active_items(session, composition_id)
    strategy_item = next(it for it in items if str(it.item_kind) == "strategy")
    await alloc_cmd.upsert_allocation_draft(
        session,
        actor,
        composition_id=composition_id,
        expected_row_version=None,
        enabled=True,
        initial_capital={"amount": amount, "currency": "USDT"},
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        reserve_cash_percent="0",
        entries=[
            {
                "composition_item_id": strategy_item.item_id,
                "active": True,
                "equity_share_percent": "100",
            }
        ],
        idempotency_key="alloc-enable-1",
    )
    await session.commit()


async def _run_diagnostics(session, result_id: str) -> dict[str, Any]:
    """The immutable ``run_diagnostics`` artifact content for a result (doc 15 §3.2)."""
    row = (
        await session.execute(
            select(DiagnosticArtifact).where(
                DiagnosticArtifact.result_id == result_id,
                DiagnosticArtifact.kind == "run_diagnostics",
            )
        )
    ).scalar_one()
    return dict(row.content)


async def test_worker_applies_the_pinned_allocation_pool_capital(session) -> None:
    # GAP-02: the manifest pins an enabled allocation plan; the worker must READ
    # capital_execution and capitalise the run from the portfolio pool P0 (50000),
    # not the strategy's own initial_capital (10000). Proves the pin is now APPLIED.
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    await _enable_allocation(session, USER1, composition_id, amount="50000.00")

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out["state"] == "succeeded"

    view = await backtest_query.get_backtest_result(session, USER1, result_id=out["result_id"])
    # The run is capitalised from the portfolio pool P0 (50000), which is only possible
    # if the worker read + applied capital_execution (the strategy's own is 10000).
    assert view["summary"]["headline"]["initial_capital"] == "50000.00"

    diagnostics = await _run_diagnostics(session, out["result_id"])
    assert diagnostics["allocation_enabled"] is True
    assert diagnostics["allocation_items_executed"] == 1
    assert "allocation_single_currency_pool_assumed" in diagnostics["warnings"]


async def test_worker_independent_run_uses_the_strategy_own_capital(session) -> None:
    # Regression: with no allocation plan the run is capitalised from the strategy's
    # own initial_capital (10000) and carries no allocation execution — byte-identical
    # to the pre-GAP-02 engine.
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    view = await backtest_query.get_backtest_result(session, USER1, result_id=out["result_id"])
    assert view["summary"]["headline"]["initial_capital"] == "10000.00"  # the strategy's own
    diagnostics = await _run_diagnostics(session, out["result_id"])
    assert diagnostics["allocation_enabled"] is False
    assert await _count(session, BacktestResult) == 1
