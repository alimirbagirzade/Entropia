"""Integration: resolve ``ta.vwap`` as a directional key into a plan (post-V1 (d)).

Exercises ``resolve_indicator_plan`` against REAL persisted ``package_revision`` rows:
a ``ta.vwap`` indicator package now resolves to a directional native-trigger spec (it was
``no_directional_dependency`` before (d)); ``ta.atr`` still does not (the honest boundary);
and a VWAP package is usable as a condition's reference-package RHS and as an N-ary chain
leg. One end-to-end run proves a published VWAP block drives the engine's entry from the
bars' volume — no package body executed.
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


async def _market_revision(session, *, base_tf: str | None = "1h") -> str:
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
    cond_rev: str, *, reference_package_rev: str, additional: list[dict[str, Any]] | None
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "condition_block_id": "cb_1",
        "display_order": 0,
        "package_ref": {
            "package_root_id": "pkg_cond",
            "package_revision_id": cond_rev,
            "package_content_hash": "condhash",
        },
        "requirement": "required",
        "validity": "1_candle",
        "reference_timeframe": "same_as_base_tf",
        "parameter_overrides": {"source": "close"},
        "reference_package_ref": {
            "package_root_id": "pkg_ref",
            "package_revision_id": reference_package_rev,
            "package_content_hash": "refhash",
        },
    }
    if additional is not None:
        block["additional_reference_package_refs"] = additional
    return block


def _leg(rev: str) -> dict[str, Any]:
    return {
        "package_ref": {
            "package_root_id": "pkg_ref_extra",
            "package_revision_id": rev,
            "package_content_hash": "extrahash",
        },
        "timeframe": "same_as_base_tf",
    }


def _config(
    indicator_rev: str,
    market_rev: str,
    *,
    trigger: str = "indicator_native_trigger",
    condition_blocks: list[dict[str, Any]] | None = None,
    ind_overrides: dict[str, Any] | None = None,
) -> StrategyConfig:
    block: dict[str, Any] = {
        "block_id": "blk_1",
        "display_order": 0,
        "package_ref": {
            "package_root_id": "pkg_ind",
            "package_revision_id": indicator_rev,
            "package_content_hash": "pkghash_1",
        },
        "trigger_source": trigger,
        "timeframe": "same_as_base_tf",
        "requirement": "required",
        "parameter_overrides": ind_overrides,
    }
    if condition_blocks is not None:
        block["condition_blocks"] = condition_blocks
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "VWAP Fixture",
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
                "indicator_blocks": [block],
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


# ------------------------------------------------------------------- native trigger


async def test_vwap_block_resolves_as_a_directional_native_trigger(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.vwap")
    market = await _market_revision(session)
    plan = await resolve_indicator_plan(session, _config(ind, market))
    assert plan.has_entry is True
    assert plan.unresolved == ()
    spec = plan.entry_specs[0]
    assert spec.canonical_key == "ta.vwap"
    assert spec.length == 20  # engine-version default (shared with the MA family)


async def test_atr_block_is_still_left_unresolved(session) -> None:
    # The honest boundary preserved: ATR is a volatility band, not a directional line.
    ind = await _package(session, PackageKind.INDICATOR, "ta.atr")
    market = await _market_revision(session)
    plan = await resolve_indicator_plan(session, _config(ind, market))
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:no_directional_dependency",)


# --------------------------------------------------------- VWAP as a reference RHS


async def test_vwap_reference_package_resolves_as_an_inline_series(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    cross = await _package(session, PackageKind.CONDITION, "cond.crosses_above")
    vwap = await _package(session, PackageKind.INDICATOR, "ta.vwap")
    market = await _market_revision(session)
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            trigger="indicator_output_plus_condition",
            condition_blocks=[_cblock(cross, reference_package_rev=vwap, additional=None)],
        ),
    )
    assert plan.has_entry is True
    assert plan.unresolved == ()
    assert plan.entry_specs[0].conditions[0].reference_key == "ta.vwap"


async def test_vwap_can_be_an_nary_chain_leg(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    cross = await _package(session, PackageKind.CONDITION, "cond.crosses_above")
    slow = await _package(session, PackageKind.INDICATOR, "ta.sma")
    vwap = await _package(session, PackageKind.INDICATOR, "ta.vwap")
    market = await _market_revision(session)
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            market,
            trigger="indicator_output_plus_condition",
            condition_blocks=[_cblock(cross, reference_package_rev=slow, additional=[_leg(vwap)])],
        ),
    )
    assert plan.has_entry is True
    cond = plan.entry_specs[0].conditions[0]
    assert tuple(leg.key for leg in cond.extra_references) == ("ta.vwap",)


# -------------------------------------------------------------------------- end-to-end


def _vwap_bars(rows: list[tuple[str, str]]) -> Iterator[list[dict[str, Any]]]:
    # rows: (close, volume); high=low=close
    yield [
        {
            "timestamp": f"2024-01-01T{h:02d}:00:00Z",
            "open": c,
            "high": c,
            "low": c,
            "close": c,
            "volume": v,
        }
        for h, (c, v) in enumerate(rows)
    ]


async def test_published_vwap_block_drives_a_real_engine_entry(session) -> None:
    """End-to-end: a VWAP(2) block. Flat 10s hold the price on the volume-weighted line,
    then a jump to 20 crosses up through it -> exactly one long, computed from the bars'
    volume with no package body executed."""
    ind = await _package(session, PackageKind.INDICATOR, "ta.vwap")
    market = await _market_revision(session)
    cfg = _config(ind, market, ind_overrides={"length": 2})
    plan = await resolve_indicator_plan(session, cfg)
    assert plan.entry_specs[0].canonical_key == "ta.vwap"

    rows = [("10", "1"), ("10", "1"), ("10", "1"), ("20", "1")]
    out = run_engine(
        strategy_config=cfg,
        bar_batches=_vwap_bars(rows),
        execution_key="k",
        indicator_plan=plan,
    )
    assert out.diagnostics["entry_model"] == BUILTIN_ENTRY_MODEL
    assert out.diagnostics["vwap_blocks"] == 1
    assert out.summary["total_trades"] == 1
    assert out.trades[0].direction == "long"
