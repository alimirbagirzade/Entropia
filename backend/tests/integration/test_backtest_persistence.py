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

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.queries import backtest_run as backtest_query
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.market_data.enums import MarketDataType
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    BacktestRun,
    Job,
    MetricValueRow,
    Principal,
)
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
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
    market_root_id: str, market_revision_id: str, market_hash: str
) -> dict[str, Any]:
    return {
        "strategy_root_id": "strat_root_seed",
        "display_name": "Seed strategy",
        "rationale_family_id": "rf_1",
        "data": {
            "instrument_id": "BTCUSDT",
            "market_dataset_root_id": market_root_id,
            "market_dataset_revision_id": market_revision_id,
            "market_dataset_content_hash": market_hash,
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
                    "block_id": "ib_1",
                    "display_order": 0,
                    "package_ref": {
                        "package_root_id": "pkg_root_1",
                        "package_revision_id": "pkg_rev_1",
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


async def _ready_composition(session, actor: Actor) -> tuple[str, str, str]:
    workspace_id = await _empty_composition(session, actor)
    # Slice B: the strategy pins a REAL market revision (FK-valid entity) and the
    # bar-replay worker resolves its processed Parquet asset (INF-12); the bar bytes
    # are injected via ``_e2e_bars``.
    market_root, market_rev = await md_repo.create_market_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        market_data_type=MarketDataType.OHLCV,
        payload={"note": "seed bars"},
    )
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
    work_object = await mb_cmd.create_work_object(
        session,
        actor,
        object_kind="strategy",
        payload=_strategy_payload(
            market_root.entity_id, market_rev.revision_id, market_rev.content_hash
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
    assert await _count(session, BacktestResult) == 1
