"""Integration: resolve a pinned StrategyConfig into an indicator plan (Slice C).

Exercises ``resolve_indicator_plan`` against REAL persisted ``package_revision`` rows
(the pin -> dependency_snapshot -> canonical key dereference the engine relies on),
including every honest-boundary path that leaves a block unresolved."""

from __future__ import annotations

from typing import Any

import pytest

from entropia.application.queries.indicator_plan import resolve_indicator_plan
from entropia.domain.lifecycle.enums import ApprovalState, PackageKind, VisibilityScope
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.strategy.config import StrategyConfig
from entropia.infrastructure.postgres.repositories import packages as pkg_repo

pytestmark = pytest.mark.asyncio


async def _indicator_package(session, canonical_key: str) -> str:
    """Publish an indicator package revision whose snapshot resolves ``canonical_key``."""
    _registry, _root, revision = await pkg_repo.create_package(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        package_kind=PackageKind.INDICATOR,
        input_contract={"source": "close"},
        output_contract={"kind": "directional_signal"},
        dependency_snapshot={"resolved": [{"call": canonical_key, "canonical_key": canonical_key}]},
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.flush()
    return revision.revision_id


def _config(
    revision_id: str,
    *,
    trigger: str = "indicator_native_trigger",
    timeframe: str = "same_as_base_tf",
    overrides: dict[str, Any] | None = None,
) -> StrategyConfig:
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Plan Resolution Fixture",
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
                            "package_root_id": "pkg_root_1",
                            "package_revision_id": revision_id,
                            "package_content_hash": "pkghash_1",
                        },
                        "trigger_source": trigger,
                        "timeframe": timeframe,
                        "requirement": "required",
                        "parameter_overrides": overrides,
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


async def test_directional_package_resolves_to_a_computable_spec(session) -> None:
    revision_id = await _indicator_package(session, "ta.rsi")
    plan = await resolve_indicator_plan(session, _config(revision_id))
    assert plan.has_entry is True
    assert len(plan.entry_specs) == 1
    spec = plan.entry_specs[0]
    assert spec.canonical_key == "ta.rsi"
    assert spec.length == 14  # engine-version default (no override in source body)
    assert spec.requirement == "required"
    assert plan.unresolved == ()
    assert plan.exit_on_opposite is True


async def test_parameter_override_sets_the_length(session) -> None:
    revision_id = await _indicator_package(session, "ta.sma")
    plan = await resolve_indicator_plan(session, _config(revision_id, overrides={"length": 9}))
    assert plan.entry_specs[0].length == 9


async def test_non_directional_key_is_left_unresolved(session) -> None:
    revision_id = await _indicator_package(session, "ta.atr")  # volatility, no native trigger
    plan = await resolve_indicator_plan(session, _config(revision_id))
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:no_directional_dependency",)


async def test_non_native_trigger_source_is_deferred(session) -> None:
    revision_id = await _indicator_package(session, "ta.rsi")
    plan = await resolve_indicator_plan(
        session, _config(revision_id, trigger="indicator_native_trigger_plus_condition")
    )
    assert plan.has_entry is False
    assert plan.unresolved[0].startswith("entry:blk_1:trigger_source_deferred")


async def test_timeframe_override_is_deferred(session) -> None:
    revision_id = await _indicator_package(session, "ta.rsi")
    plan = await resolve_indicator_plan(session, _config(revision_id, timeframe="1h"))
    assert plan.has_entry is False
    assert plan.unresolved[0].startswith("entry:blk_1:timeframe_override_deferred")


async def test_missing_package_revision_is_unresolved(session) -> None:
    plan = await resolve_indicator_plan(session, _config("pkgrev_does_not_exist"))
    assert plan.has_entry is False
    assert plan.unresolved == ("entry:blk_1:package_revision_unresolved",)
