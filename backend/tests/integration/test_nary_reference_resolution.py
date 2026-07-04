"""Integration: resolve an N-ary reference chain into a plan (post-V1 Slice C follow-up (ii)).

Exercises ``resolve_indicator_plan`` against REAL persisted rows — an indicator
``package_revision`` (native trigger), a ``cond.*`` condition package, a PRIMARY indicator
reference package, and one or more ADDITIONAL indicator reference packages forming the
comparison chain. Covers the chain resolving with two extra legs, the fail-closed paths
(additional legs without a primary, a missing revision, a non-directional leg, a finer
per-leg timeframe), a coarser per-leg timeframe resampling, and a per-leg length override —
plus one end-to-end run proving a three-MA fan crossover drives the engine's entry.
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


def _leg(rev: str, timeframe: str = "same_as_base_tf", length: str | None = None) -> dict[str, Any]:
    leg: dict[str, Any] = {
        "package_ref": {
            "package_root_id": "pkg_ref_extra",
            "package_revision_id": rev,
            "package_content_hash": "extrahash",
        },
        "timeframe": timeframe,
    }
    if length is not None:
        leg["parameter_overrides"] = {"reference_length": length}
    return leg


def _cblock(
    cond_rev: str,
    *,
    reference_package_rev: str | None = None,
    reference_timeframe: str = "same_as_base_tf",
    reference_length: str | None = None,
    additional: list[dict[str, Any]] | None = None,
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
    if additional is not None:
        block["additional_reference_package_refs"] = additional
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
            "display_name": "N-ary Reference Fixture",
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


# ------------------------------------------------------------------ chain resolution


async def test_nary_chain_resolves_primary_plus_two_extra_legs(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slower = await _package(session, PackageKind.INDICATOR, "ta.ema")
    slowest = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            condition_blocks=[
                _cblock(
                    await _cross(session),
                    reference_package_rev=slow,
                    additional=[_leg(slower), _leg(slowest)],
                )
            ],
        ),
    )
    assert plan.has_entry is True
    assert plan.unresolved == ()
    cond = plan.entry_specs[0].conditions[0]
    assert cond.reference_key == "ta.sma"
    assert tuple(leg.key for leg in cond.extra_references) == ("ta.ema", "ta.sma")


async def test_additional_reference_without_a_primary_is_unresolved(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slower = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            condition_blocks=[_cblock(await _cross(session), additional=[_leg(slower)])],
        ),
    )
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_additional_reference_without_primary:cb_1",)


async def test_additional_leg_with_a_missing_revision_is_unresolved(session) -> None:
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
                    await _cross(session),
                    reference_package_rev=slow,
                    additional=[_leg("01JZZZNONEXISTENTREVISIONXX")],
                )
            ],
        ),
    )
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_additional_reference_unresolved:cb_1:0",)


async def test_additional_leg_with_no_computable_series_is_unresolved(session) -> None:
    # ta.atr is recognized but non-directional -> not a computable inline series.
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    atr = await _package(session, PackageKind.INDICATOR, "ta.atr")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            condition_blocks=[
                _cblock(
                    await _cross(session),
                    reference_package_rev=slow,
                    additional=[_leg(atr)],
                )
            ],
        ),
    )
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_additional_reference_no_series:cb_1:0",)


async def test_additional_leg_on_a_coarser_timeframe_resamples(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slower = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            condition_blocks=[
                _cblock(
                    await _cross(session),
                    reference_package_rev=slow,
                    additional=[_leg(slower, timeframe="4h")],
                )
            ],
        ),
    )
    assert plan.has_entry is True
    leg = plan.entry_specs[0].conditions[0].extra_references[0]
    assert leg.resample_seconds == 14400  # 4h coarser than the 1h block


async def test_additional_leg_finer_than_the_block_is_unresolved(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slower = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            block_timeframe="2h",
            condition_blocks=[
                _cblock(
                    await _cross(session),
                    reference_package_rev=slow,
                    reference_timeframe="2h",
                    additional=[_leg(slower, timeframe="1h")],
                )
            ],
        ),
    )
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_reference_timeframe_finer_than_block:cb_1",)


async def test_additional_leg_length_override_is_honored(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slower = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            condition_blocks=[
                _cblock(
                    await _cross(session),
                    reference_package_rev=slow,
                    additional=[_leg(slower, length="7")],
                )
            ],
        ),
    )
    assert plan.has_entry is True
    assert plan.entry_specs[0].conditions[0].extra_references[0].length == 7


# ------------------------------------------------------------------------ end-to-end


def _hourly_bars(closes: list[str]) -> Iterator[list[dict[str, Any]]]:
    yield [
        {"timestamp": f"2024-01-01T{h:02d}:00:00Z", "open": c, "high": c, "low": c, "close": c}
        for h, c in enumerate(closes)
    ]


async def test_three_ma_fan_cross_drives_the_engine_entry(session) -> None:
    """End-to-end: ``close crosses_above SMA(3) > SMA(4)`` — a three-MA fan aligning on one
    bar opens exactly one long. The whole N-ary chain is computed inline from the pinned
    reference packages; no package body is executed."""
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slowest = await _package(session, PackageKind.INDICATOR, "ta.sma")
    cross = await _package(session, PackageKind.CONDITION, "cond.crosses_above")
    market = await _market_revision(session, base_tf="1h")
    closes = ["10", "10", "10", "10", "20", "20"]  # the fan aligns bullishly on bar 5
    cfg = _config(
        ind,
        market,
        condition_blocks=[
            _cblock(
                cross,
                reference_package_rev=slow,
                reference_length="3",
                additional=[_leg(slowest, length="4")],
                source="close",
            )
        ],
        ind_overrides={"length": 2},
    )
    plan = await resolve_indicator_plan(session, cfg)
    extras = plan.entry_specs[0].conditions[0].extra_references
    assert tuple(leg.key for leg in extras) == ("ta.sma",)

    out = run_engine(
        strategy_config=cfg,
        bar_batches=_hourly_bars(closes),
        execution_key="k",
        indicator_plan=plan,
    )
    assert out.diagnostics["entry_model"] == BUILTIN_ENTRY_MODEL
    assert out.diagnostics["nary_reference_conditions"] == 1
    assert out.summary["total_trades"] == 1
    assert out.trades[0].direction == "long"


# ------------------------------------------------------- fail-closed / parity hardening


async def test_additional_legs_cannot_ride_a_range_condition(session) -> None:
    # A cond.between (RANGE) compares against fixed bounds, not an RHS chain; a reference
    # chain here is a misconfiguration rejected before the extra legs matter.
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slower = await _package(session, PackageKind.INDICATOR, "ta.sma")
    between = await _package(session, PackageKind.CONDITION, "cond.between")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            trigger="indicator_native_trigger_plus_condition",
            condition_blocks=[
                _cblock(between, reference_package_rev=slow, additional=[_leg(slower)])
            ],
        ),
    )
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_reference_package_on_range:cb_1",)


async def test_additional_leg_with_package_default_timeframe_stays_on_the_block(session) -> None:
    # use_package_default_tf keeps a leg on the block's timeframe (a None resample span),
    # identically to the primary reference's handling — no per-leg resampling.
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    slower = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session, base_tf="1h")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            condition_blocks=[
                _cblock(
                    await _cross(session),
                    reference_package_rev=slow,
                    additional=[_leg(slower, timeframe="use_package_default_tf")],
                )
            ],
        ),
    )
    assert plan.has_entry is True
    assert plan.entry_specs[0].conditions[0].extra_references[0].resample_seconds is None
