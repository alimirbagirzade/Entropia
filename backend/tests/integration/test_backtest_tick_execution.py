"""F-07i (B) — tick-path pin + worker replay against a real database.

The admission command pins the approved tick/trade revision for every
tick-demanding Strategy into the immutable RUN manifest (``tick_data``), and the
worker streams THAT pinned revision's processed asset into the engine — never a
worker-time 'newest approved' lookup (doc 15 §15). Covers: the happy chain
(admit -> pin in manifest -> worker streams the pinned tick source -> SUCCEEDED),
the tick-less strategy carrying NO pin and streaming NO ticks, and the two
fail-closed worker paths (a stale manifest without the pin; a pin whose processed
tick asset is missing) -> terminal FAILED ASSET_UNAVAILABLE, never a silently
tickless run.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any

import pytest

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.queries.market_ticks import TickSourceRef
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    VisibilityScope,
)
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    ResolutionKind,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import BacktestRun
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import ReadinessBlockedError

# Reuse the seeding helpers from the sibling backtest persistence suite.
from tests.integration.test_backtest_persistence import (
    USER1,
    _e2e_bars,
    _empty_composition,
    _seed_principals,
    _strategy_payload,
)

pytestmark = pytest.mark.integration


async def _seed_tick_revision(
    session, *, instrument_id: str = "BTCUSDT", with_asset: bool = True
) -> str:
    """One APPROVED tick/trade revision (own ACTIVE root); optionally its processed asset."""
    tick_root, tick_rev = await md_repo.create_market_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        market_data_type=MarketDataType.TICK_TRADES,
        payload={"note": "seed ticks"},
        instrument_id=instrument_id,
    )
    tick_rev.revision_state = MarketRevisionState.APPROVED
    await session.flush()
    if with_asset:
        md_repo.add_processed_asset(
            session,
            entity_id=tick_root.entity_id,
            object_key=f"market/processed/{tick_root.entity_id}/ticks.parquet",
            content_digest="seed-ticks",
            size_bytes=2048,
            revision_id=tick_rev.revision_id,
            row_count=3,
        )
        await session.flush()
    return tick_rev.revision_id


async def _tick_composition(
    session, actor, *, tick_policy: str = "require", entry_timing: str | None = None
) -> str:
    """A ready composition whose one strategy carries the given intrabar tick policy.

    Mirrors ``test_backtest_persistence._ready_composition`` (approved OHLCV revision
    + processed bar asset + resolvable ta.sma indicator package) with a "1D" base
    timeframe so the engine can align tick prints to the daily ``_e2e_bars``."""
    workspace_id = await _empty_composition(session, actor)
    market_root, market_rev = await md_repo.create_market_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        market_data_type=MarketDataType.OHLCV,
        payload={"note": "seed bars"},
        instrument_id=None,
    )
    market_rev.resolution_kind = ResolutionKind.BAR
    market_rev.resolution_value = "1D"
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
    payload: dict[str, Any] = copy.deepcopy(
        _strategy_payload(
            market_root.entity_id,
            market_rev.revision_id,
            market_rev.content_hash,
            indicator_revision_id=pkg_rev.revision_id,
        )
    )
    payload["data"]["intrabar_policy"]["tick_policy"] = tick_policy
    if entry_timing is not None:
        payload["data"]["execution"]["entry_timing"] = entry_timing
    work_object = await mb_cmd.create_work_object(
        session, actor, object_kind="strategy", payload=payload
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


def _tick_recorder(calls: list[TickSourceRef]):
    """A ``stream_ticks`` double: records the resolved source, yields in-range prints."""

    def _stream(source: TickSourceRef) -> Iterator[list[dict[str, Any]]]:
        calls.append(source)
        yield [
            {"timestamp": "2024-02-22T01:00:00Z", "price": "101"},
            {"timestamp": "2024-02-22T02:00:00Z", "price": "96"},
        ]

    return _stream


def _tick_forbidden(_source: TickSourceRef) -> Iterator[list[dict[str, Any]]]:
    raise AssertionError("stream_ticks must not be called for a tick-less strategy")


async def test_admission_pins_tick_revision_and_worker_streams_it(session) -> None:
    await _seed_principals(session)
    tick_revision_id = await _seed_tick_revision(session)
    composition_id = await _tick_composition(session, USER1)

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    manifest = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert manifest is not None
    tick_data = manifest.manifest["tick_data"]
    item_id = manifest.manifest["mainboard_items"][0]["item_id"]
    assert tick_data == {
        item_id: {"tick_revision_id": tick_revision_id, "instrument_id": "BTCUSDT"}
    }

    calls: list[TickSourceRef] = []
    out = await run_backtest(
        session, admit["job_id"], stream_bars=_e2e_bars, stream_ticks=_tick_recorder(calls)
    )
    await session.commit()

    assert out["state"] == "succeeded"
    # The worker streamed exactly the PINNED revision's processed asset.
    assert [c.revision_id for c in calls] == [tick_revision_id]
    assert calls[0].object_key.endswith("/ticks.parquet")
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None and run.result_id == out["result_id"]


async def test_tickless_strategy_carries_no_pin_and_streams_no_ticks(session) -> None:
    await _seed_principals(session)
    await _seed_tick_revision(session)  # available, but the strategy never demands it
    composition_id = await _tick_composition(session, USER1, tick_policy="inherit")

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    manifest = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert manifest is not None and manifest.manifest["tick_data"] is None

    out = await run_backtest(
        session, admit["job_id"], stream_bars=_e2e_bars, stream_ticks=_tick_forbidden
    )
    await session.commit()
    assert out["state"] == "succeeded"


async def test_stale_manifest_without_tick_pin_fails_closed(session) -> None:
    await _seed_principals(session)
    await _seed_tick_revision(session)
    composition_id = await _tick_composition(session, USER1)

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    # Simulate a pre-v15 manifest (admitted before tick pinning existed).
    manifest = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert manifest is not None
    manifest.manifest = {**manifest.manifest, "tick_data": None}
    await session.flush()

    calls: list[TickSourceRef] = []
    out = await run_backtest(
        session, admit["job_id"], stream_bars=_e2e_bars, stream_ticks=_tick_recorder(calls)
    )
    await session.commit()

    assert out["state"] == "failed"
    assert out["failure_code"] == "RUN_FAILED_ASSET_UNAVAILABLE"
    assert calls == []  # never guessed a 'newest approved' fallback
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None and "pins no tick/trade revision" in run.failure_message


async def test_tick_pin_without_processed_asset_fails_closed(session) -> None:
    await _seed_principals(session)
    tick_revision_id = await _seed_tick_revision(session, with_asset=False)
    composition_id = await _tick_composition(session, USER1)

    # Ready Check passes ((i)a deliberately requires only an APPROVED revision) and
    # admission pins it; the missing processed asset is a WORKER-time hard failure.
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    manifest = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert manifest is not None
    assert next(iter(manifest.manifest["tick_data"].values()))["tick_revision_id"] == (
        tick_revision_id
    )

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "failed"
    assert out["failure_code"] == "RUN_FAILED_ASSET_UNAVAILABLE"
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None and "no processed tick asset" in run.failure_message


# --------------------------------------------------------------------------- #
# F-07i (C): the tick-dependent SETTINGS through the full admission chain      #
# --------------------------------------------------------------------------- #


async def test_admission_blocks_a_tick_timing_without_the_tick_demand(session) -> None:
    # ``intrabar_touch`` without 'Use Tick Data' = Yes is NOT modelled (C): the shared
    # predicate makes Ready Check block RUN — no run/manifest/job is left behind.
    await _seed_principals(session)
    await _seed_tick_revision(session)  # availability alone is NOT the gate — the demand is
    composition_id = await _tick_composition(
        session, USER1, tick_policy="inherit", entry_timing="intrabar_touch"
    )

    with pytest.raises(ReadinessBlockedError) as exc_info:
        await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.rollback()
    details = exc_info.value.details or []
    assert any(d.get("code") == "STRATEGY_EXECUTION_TIMING_UNSUPPORTED" for d in details)


async def test_tick_timing_runs_end_to_end_over_the_pinned_print_path(session) -> None:
    # The same timing WITH the demand admits (predicate True), pins the tick revision,
    # and the worker replays the settings over the pinned print path -> SUCCEEDED.
    await _seed_principals(session)
    tick_revision_id = await _seed_tick_revision(session)
    composition_id = await _tick_composition(session, USER1, entry_timing="intrabar_touch")

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    manifest = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert manifest is not None
    assert next(iter(manifest.manifest["tick_data"].values()))["tick_revision_id"] == (
        tick_revision_id
    )

    calls: list[TickSourceRef] = []
    out = await run_backtest(
        session, admit["job_id"], stream_bars=_e2e_bars, stream_ticks=_tick_recorder(calls)
    )
    await session.commit()

    assert out["state"] == "succeeded"
    assert [c.revision_id for c in calls] == [tick_revision_id]
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None and run.result_id == out["result_id"]
