"""Integration: resolve a per-condition multi-timeframe reference into a plan (i).

Exercises ``resolve_indicator_plan`` against REAL persisted rows — an indicator
``package_revision`` (native trigger), a ``cond.*`` condition package, a SECOND indicator
package as the reference RHS, and a ``market_dataset_revision`` pinning the base bar
timeframe. Covers every branch of the reference-timeframe resolution — coarser resamples,
equal collapses to the block, finer is honest-unresolved, an override with no reference
package is a misconfiguration, an unknown base still resolves, and a coarser-than-a-HTF-
block reference resamples — plus one end-to-end run proving a resampled 2h reference cross
drives the engine's entry over 1h base bars.
"""

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


async def _package(session, kind: PackageKind, canonical_key: str) -> str:
    """Publish a package revision whose snapshot resolves ``canonical_key``."""
    _root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        package_kind=kind,
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


def _cblock(
    cond_rev: str,
    *,
    reference_package_rev: str | None = None,
    reference_timeframe: str = "same_as_base_tf",
    reference_length: str | None = None,
    source: str = "close",
    cb_id: str = "cb_1",
) -> dict[str, Any]:
    overrides: dict[str, Any] = {"source": source}
    if reference_length is not None:
        overrides["reference_length"] = reference_length
    block: dict[str, Any] = {
        "condition_block_id": cb_id,
        "display_order": 0,
        "package_ref": {
            "package_root_id": "pkg_cond",
            "package_revision_id": cond_rev,
            "package_content_hash": "condhash",
        },
        "requirement": "required",
        "validity": "1_candle",
        "reference_timeframe": reference_timeframe,
        "parameter_overrides": overrides,
    }
    if reference_package_rev is not None:
        block["reference_package_ref"] = {
            "package_root_id": "pkg_ref",
            "package_revision_id": reference_package_rev,
            "package_content_hash": "refhash",
        }
    return block


def _config(
    indicator_rev: str,
    market_rev: str,
    *,
    condition_blocks: list[dict[str, Any]],
    block_timeframe: str = "same_as_base_tf",
    trigger: str = "indicator_output_plus_condition",
    ind_overrides: dict[str, Any] | None = None,
) -> StrategyConfig:
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Per-Condition TF Fixture",
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
                        "trigger_source": trigger,
                        "timeframe": block_timeframe,
                        "requirement": "required",
                        "condition_blocks": condition_blocks,
                        "parameter_overrides": ind_overrides,
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


async def _cross(session) -> str:
    return await _package(session, PackageKind.CONDITION, "cond.crosses_above")


# --------------------------------------------------------- reference-timeframe branches


async def test_coarser_reference_timeframe_resolves_with_a_resample_span(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            condition_blocks=[
                _cblock(await _cross(session), reference_package_rev=slow, reference_timeframe="4h")
            ],
        ),
    )
    assert plan.has_entry is True
    assert plan.unresolved == ()
    cond = plan.entry_specs[0].conditions[0]
    assert cond.reference_key == "ta.sma"
    assert cond.reference_resample_seconds == 14400  # 4h coarser than the 1h block


async def test_reference_timeframe_equal_to_block_collapses_to_block_compute(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            condition_blocks=[
                _cblock(await _cross(session), reference_package_rev=slow, reference_timeframe="1h")
            ],
        ),
    )
    assert plan.has_entry is True
    assert plan.entry_specs[0].conditions[0].reference_resample_seconds is None


async def test_reference_timeframe_finer_than_block_is_unresolved(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            condition_blocks=[
                _cblock(
                    await _cross(session), reference_package_rev=slow, reference_timeframe="15m"
                )
            ],
        ),
    )
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_reference_timeframe_finer_than_block:cb_1",)


async def test_reference_timeframe_without_a_reference_package_is_unresolved(session) -> None:
    # A reference-timeframe override needs a reference package to resample; without one it
    # has no RHS series — a misconfiguration surfaced, not silently ignored.
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            condition_blocks=[_cblock(await _cross(session), reference_timeframe="4h")],
        ),
    )
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_reference_timeframe_without_package:cb_1",)


async def test_reference_timeframe_resolves_when_the_base_is_unknown(session) -> None:
    # No bar-timeframe resolution: the override cannot be validated as coarser but still
    # resolves (it degrades deterministically to the block's bars).
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf=None)
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            condition_blocks=[
                _cblock(await _cross(session), reference_package_rev=slow, reference_timeframe="4h")
            ],
        ),
    )
    assert plan.has_entry is True
    assert plan.entry_specs[0].conditions[0].reference_resample_seconds == 14400


async def test_reference_coarser_than_a_higher_tf_block_resamples(session) -> None:
    # The block itself resamples to 2h; a 4h reference is coarser than the BLOCK's effective
    # timeframe (not just the base) and resamples on top of it.
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            block_timeframe="2h",
            condition_blocks=[
                _cblock(await _cross(session), reference_package_rev=slow, reference_timeframe="4h")
            ],
        ),
    )
    assert plan.has_entry is True
    spec = plan.entry_specs[0]
    assert spec.resample_seconds == 7200  # block resamples to 2h
    assert spec.conditions[0].reference_resample_seconds == 14400  # reference coarser still


async def test_reference_finer_than_a_higher_tf_block_is_unresolved(session) -> None:
    # A 2h reference under a 4h block is FINER than the block's effective timeframe — the
    # reference would have to advance faster than the condition ticks. Honest-unresolved.
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            block_timeframe="4h",
            condition_blocks=[
                _cblock(await _cross(session), reference_package_rev=slow, reference_timeframe="2h")
            ],
        ),
    )
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_reference_timeframe_finer_than_block:cb_1",)


# ------------------------------------------------------------------------ end-to-end


def _hourly_bars(closes: list[str]) -> Iterator[list[dict[str, Any]]]:
    yield [
        {"timestamp": f"2024-01-01T{h:02d}:00:00Z", "open": c, "high": c, "low": c, "close": c}
        for h, c in enumerate(closes)
    ]


async def test_multi_timeframe_reference_cross_drives_the_engine_entry(session) -> None:
    """End-to-end: a base-TF price crossing above a 2h-resampled reference SMA(2) opens one
    long. The reference only advances on a completed 2h candle, so the fast source cannot
    cross a still-forming reference — the causal, look-ahead-free multi-timeframe entry."""
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    cross = await _package(session, PackageKind.CONDITION, "cond.crosses_above")
    market = await _market_revision(session, base_tf="1h")
    closes = ["10", "10", "10", "10", "5", "5", "30", "30"]  # crosses the 2h ref at bar 6
    cfg = _config(
        ind,
        market,
        condition_blocks=[
            _cblock(
                cross,
                reference_package_rev=slow,
                reference_timeframe="2h",
                reference_length="2",
                source="close",
            )
        ],
        ind_overrides={"length": 2},
    )
    plan = await resolve_indicator_plan(session, cfg)
    assert plan.entry_specs[0].conditions[0].reference_resample_seconds == 7200

    out = run_engine(
        strategy_config=cfg,
        bar_batches=_hourly_bars(closes),
        execution_key="k",
        indicator_plan=plan,
    )
    assert out.diagnostics["entry_model"] == BUILTIN_ENTRY_MODEL
    assert out.diagnostics["per_condition_timeframe_conditions"] == 1
    assert out.summary["total_trades"] == 1
    assert out.trades[0].direction == "long"
