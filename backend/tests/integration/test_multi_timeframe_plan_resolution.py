"""Integration: resolve a higher-timeframe indicator block into a resampling plan (c).

Exercises ``resolve_indicator_plan`` against a REAL persisted ``market_dataset_revision``
(whose ``resolution_value`` is the base bar timeframe) and an indicator ``package_revision``.
Covers every branch of the timeframe resolution — a coarser override resamples, a finer
override is honest-unresolved, an equal override collapses to the base compute, and an
unknown base still resolves the override — plus one end-to-end run proving a resampled
higher-TF SMA cross drives the engine's entry."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from entropia.application.queries.indicator_plan import resolve_indicator_plan
from entropia.domain.backtest.engine import run_engine
from entropia.domain.backtest.indicators import BUILTIN_ENTRY_MODEL
from entropia.domain.lifecycle.enums import ApprovalState, PackageKind, VisibilityScope
from entropia.domain.market_data.enums import MarketDataType, ResolutionKind
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.strategy.config import StrategyConfig
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo

pytestmark = pytest.mark.asyncio


async def _indicator(session, canonical_key: str = "ta.sma") -> str:
    """Publish an indicator package revision whose snapshot resolves ``canonical_key``."""
    _root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        package_kind=PackageKind.INDICATOR,
        input_contract={"source": "close"},
        output_contract={"kind": "directional_signal"},
        dependency_snapshot={"resolved": [{"canonical_key": canonical_key}]},
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.flush()
    return revision.revision_id


async def _market_revision(session, *, base_tf: str | None) -> str:
    """Create a market revision; when ``base_tf`` is set, pin it as the bar timeframe."""
    _root, revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        market_data_type=MarketDataType.OHLCV,
        payload={"kind": "ohlcv"},
    )
    if base_tf is not None:
        revision.resolution_kind = ResolutionKind.BAR
        revision.resolution_value = base_tf
    await session.flush()
    return revision.revision_id


def _config(
    indicator_rev: str,
    market_rev: str,
    *,
    timeframe: str,
    length: int | None = None,
) -> StrategyConfig:
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "MTF Plan Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": market_rev,
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
                "initial_capital": "10000.00",
                "execution": {
                    "entry_timing": "current_candle_close",
                    "exit_timing": "current_candle_close",
                },
                "order_config": {"type": "market_order"},
                "costs": {"slippage_mode": "percentage_slippage", "slippage_value": "0"},
                "intrabar_policy": {"tick_policy": "inherit"},
                "funding": {"enabled": False},
            },
            "position_entry_logic": {
                "direction_mode": "long_and_short",
                "signal_block": {"rule": "required_indicator_blocks_only"},
                "indicator_blocks": [
                    {
                        "block_id": "blk_1",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_ind",
                            "package_revision_id": indicator_rev,
                            "package_content_hash": "pkghash_1",
                        },
                        "trigger_source": "indicator_native_trigger",
                        "timeframe": timeframe,
                        "requirement": "required",
                        "parameter_overrides": {"length": length} if length else None,
                    }
                ],
            },
            "position_exit_logic": {
                "applies_to_direction": "long_and_short",
                "close_percentage": "100",
            },
            "protection_stop_logic": {},
            "position_sizing": {"method": "base_position_size", "base_position_size": "50"},
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


async def test_coarser_override_resolves_with_a_resample_span(session) -> None:
    ind = await _indicator(session)
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(session, _config(ind, market, timeframe="4h"))
    assert plan.has_entry is True
    assert plan.unresolved == ()
    assert plan.entry_specs[0].resample_seconds == 14400  # 4h coarser than the 1h base


async def test_finer_override_than_a_known_base_is_unresolved(session) -> None:
    ind = await _indicator(session)
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(session, _config(ind, market, timeframe="15m"))
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:timeframe_finer_than_base:15m",)


async def test_override_equal_to_the_base_computes_on_the_base(session) -> None:
    ind = await _indicator(session)
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(session, _config(ind, market, timeframe="1h"))
    assert plan.has_entry is True
    assert plan.entry_specs[0].resample_seconds is None  # equal to base => base compute


async def test_override_resolves_when_the_base_timeframe_is_unknown(session) -> None:
    # No bar-timeframe resolution on the revision: the override cannot be validated as
    # coarser than the base but still resolves (it degrades to the base bars).
    ind = await _indicator(session)
    market = await _market_revision(session, base_tf=None)
    plan = await resolve_indicator_plan(session, _config(ind, market, timeframe="4h"))
    assert plan.has_entry is True
    assert plan.entry_specs[0].resample_seconds == 14400


def _hourly_bars(closes: list[str]) -> Iterator[list[dict[str, Any]]]:
    yield [
        {"timestamp": f"2024-01-01T{h:02d}:00:00Z", "open": c, "high": c, "low": c, "close": c}
        for h, c in enumerate(closes)
    ]


async def test_multi_timeframe_ma_cross_drives_the_engine_entry(session) -> None:
    """End-to-end: a 2h-resampled SMA(2) cross over 1h base bars opens exactly one long.

    Twelve hourly bars aggregate to six 2h candles with closes [10,10,10,10,12,12]; the
    SMA(2) price/MA cross fires LONG on the closed candle 4 — the resampled higher-TF
    signal, resolved end-to-end from real rows."""
    ind = await _indicator(session, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    closes = ["10", "10", "10", "10", "10", "10", "10", "10", "11", "12", "12", "12"]
    cfg = _config(ind, market, timeframe="2h", length=2)
    plan = await resolve_indicator_plan(session, cfg)
    assert plan.entry_specs[0].resample_seconds == 7200

    out = run_engine(
        strategy_config=cfg,
        bar_batches=_hourly_bars(closes),
        execution_key="k",
        indicator_plan=plan,
    )
    assert out.diagnostics["entry_model"] == BUILTIN_ENTRY_MODEL
    assert out.diagnostics["multi_timeframe_blocks"] == 1
    assert out.summary["total_trades"] == 1
    assert [t.direction for t in out.trades] == ["long"]
