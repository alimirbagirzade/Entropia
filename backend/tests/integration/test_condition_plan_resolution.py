"""Integration: resolve nested threshold condition blocks into a computable plan (b).

Exercises ``resolve_indicator_plan`` against REAL persisted ``package_revision`` rows
for both the indicator package (``ta.*`` native trigger) and the nested condition
packages (``cond.*`` threshold), including every honest-boundary path that leaves a
block unresolved, plus one end-to-end run proving the resolved condition GATES the
engine's entry."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from entropia.application.queries.indicator_plan import resolve_indicator_plan
from entropia.domain.backtest.engine import run_engine
from entropia.domain.backtest.indicators import BUILTIN_ENTRY_MODEL
from entropia.domain.lifecycle.enums import ApprovalState, PackageKind, VisibilityScope
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.strategy.config import StrategyConfig
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


def _cblock(
    cond_rev: str,
    *,
    threshold: str | None = "70",
    source: str | None = None,
    requirement: str = "required",
    validity: str = "until_opposite_signal",
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if threshold is not None:
        overrides["threshold"] = threshold
    if source is not None:
        overrides["source"] = source
    return {
        "condition_block_id": "cb_1",
        "display_order": 0,
        "package_ref": {
            "package_root_id": "pkg_cond",
            "package_revision_id": cond_rev,
            "package_content_hash": "condhash",
        },
        "requirement": requirement,
        "validity": validity,
        "parameter_overrides": overrides or None,
    }


def _config(
    indicator_rev: str,
    *,
    trigger: str = "indicator_native_trigger_plus_condition",
    condition_blocks: list[dict[str, Any]] | None = None,
    condition_rule: str | None = None,
    min_support: int | None = None,
    ind_overrides: dict[str, Any] | None = None,
) -> StrategyConfig:
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Condition Plan Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
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
                        "requirement": "required",
                        "condition_block_rule": condition_rule,
                        "min_supporting_condition_count": min_support,
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


async def test_native_plus_condition_resolves_with_threshold_condition(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.rsi")
    cond = await _package(session, PackageKind.CONDITION, "cond.above")
    plan = await resolve_indicator_plan(
        session, _config(ind, condition_blocks=[_cblock(cond, threshold="70", source="close")])
    )
    assert plan.has_entry is True
    assert plan.unresolved == ()
    spec = plan.entry_specs[0]
    assert spec.canonical_key == "ta.rsi"
    assert len(spec.conditions) == 1
    condition = spec.conditions[0]
    assert condition.canonical_key == "cond.above"
    assert condition.source == "close"
    assert str(condition.threshold) == "70"
    assert condition.requirement == "required"


async def test_condition_source_defaults_to_close(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    cond = await _package(session, PackageKind.CONDITION, "cond.below")
    plan = await resolve_indicator_plan(
        session, _config(ind, condition_blocks=[_cblock(cond, threshold="100")])
    )
    assert plan.entry_specs[0].conditions[0].source == "close"  # engine-version default


async def test_condition_threshold_missing_is_unresolved(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.rsi")
    cond = await _package(session, PackageKind.CONDITION, "cond.above")
    plan = await resolve_indicator_plan(
        session, _config(ind, condition_blocks=[_cblock(cond, threshold=None)])
    )
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_threshold_missing:cb_1",)


async def test_native_plus_condition_without_condition_blocks_is_unresolved(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.rsi")
    plan = await resolve_indicator_plan(session, _config(ind, condition_blocks=None))
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_blocks_missing",)


async def test_condition_package_with_non_condition_key_is_unresolved(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.rsi")
    bogus = await _package(session, PackageKind.CONDITION, "ta.rsi")  # not a cond.* key
    plan = await resolve_indicator_plan(
        session, _config(ind, condition_blocks=[_cblock(bogus, threshold="70")])
    )
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_no_recognized_key:cb_1",)


async def test_missing_condition_package_revision_is_unresolved(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.rsi")
    plan = await resolve_indicator_plan(
        session, _config(ind, condition_blocks=[_cblock("pkgrev_missing", threshold="70")])
    )
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:condition_package_unresolved:cb_1",)


async def test_output_plus_condition_is_still_deferred(session) -> None:
    ind = await _package(session, PackageKind.INDICATOR, "ta.rsi")
    cond = await _package(session, PackageKind.CONDITION, "cond.above")
    plan = await resolve_indicator_plan(
        session,
        _config(
            ind,
            trigger="indicator_output_plus_condition",
            condition_blocks=[_cblock(cond, threshold="70")],
        ),
    )
    assert plan.has_entry is False
    assert plan.unresolved == (
        "entry:blk_1:trigger_source_deferred:indicator_output_plus_condition",
    )


def _bars(closes: list[str]) -> Iterator[list[dict[str, Any]]]:
    yield [
        {"timestamp": f"2024-03-{i + 1:02d}T00:00:00Z", "open": c, "high": c, "low": c, "close": c}
        for i, c in enumerate(closes)
    ]


async def test_resolved_condition_gates_the_engine_entry(session) -> None:
    """End-to-end: a published condition package's threshold gates the SMA cross."""
    ind = await _package(session, PackageKind.INDICATOR, "ta.sma")
    cond = await _package(session, PackageKind.CONDITION, "cond.above")
    closes = ["10", "10", "10", "10", "10", "10", "12", "12", "12"]  # SMA(3) long cross
    short_ma = {"length": 3}  # 9 bars is not enough to warm up the default MA(20)

    open_cfg = _config(
        ind,
        condition_blocks=[_cblock(cond, threshold="10", source="close")],
        condition_rule="required_condition_blocks_only",
        ind_overrides=short_ma,
    )
    opened = run_engine(
        strategy_config=open_cfg,
        bar_batches=_bars(closes),
        execution_key="k",
        indicator_plan=await resolve_indicator_plan(session, open_cfg),
    )
    assert opened.diagnostics["entry_model"] == BUILTIN_ENTRY_MODEL
    assert opened.diagnostics["condition_blocks"] == 1
    assert opened.summary["total_trades"] == 1

    shut_cfg = _config(
        ind,
        condition_blocks=[_cblock(cond, threshold="99", source="close")],
        ind_overrides=short_ma,
    )
    shut = run_engine(
        strategy_config=shut_cfg,
        bar_batches=_bars(closes),
        execution_key="k",
        indicator_plan=await resolve_indicator_plan(session, shut_cfg),
    )
    assert shut.summary["total_trades"] == 0  # close 12 never exceeds threshold 99
