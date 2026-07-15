"""F-08 — Logic-Based Stop: pinned-package resolution + reference edges + engine wiring.

Exercises the DB-touching paths that make a Logic-Based Stop Block real end to end:
``resolve_indicator_plan`` dereferences a stop block's pinned package into a computable
``stop_specs`` entry (and surfaces an unresolvable one as a ``stop:``-prefixed warning
that fails the RUN closed), ``_extract_references`` records the block's package as a
first-class dependency edge, and ``run_engine`` builds and consumes the stop evaluators.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.application.commands.strategy_draft import _extract_references
from entropia.application.queries.indicator_plan import resolve_indicator_plan
from entropia.domain.lifecycle.enums import ApprovalState, PackageKind, VisibilityScope
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.strategy.config import StrategyConfig
from entropia.domain.strategy.enums import DependencyRoleEnum
from entropia.infrastructure.postgres.repositories import packages as pkg_repo

pytestmark = pytest.mark.asyncio


async def _indicator_package(session, canonical_key: str) -> str:
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


def _config(*, stop_revision_id: str) -> StrategyConfig:
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Logic Stop Fixture",
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
                        "block_id": "blk_entry",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_entry",
                            "package_revision_id": "pkgrev_entry",
                            "package_content_hash": "hash_entry",
                        },
                        "trigger_source": "indicator_native_trigger",
                        "requirement": "required",
                    }
                ],
            },
            "position_exit_logic": {
                "applies_to_direction": "long_and_short",
                "close_percentage": "100",
            },
            "protection_stop_logic": {
                "logic_blocks": [
                    {
                        "block_id": "stopblk_1",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_stop",
                            "package_revision_id": stop_revision_id,
                            "package_content_hash": "hash_stop",
                        },
                        "trigger_source": "indicator_native_trigger",
                        "direction": "short",
                        "requirement": "required",
                    }
                ],
            },
            "position_sizing": {"method": "base_position_size", "base_position_size": "50"},
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


async def test_logic_stop_block_resolves_to_a_computable_stop_spec(session) -> None:
    revision_id = await _indicator_package(session, "ta.rsi")
    plan = await resolve_indicator_plan(session, _config(stop_revision_id=revision_id))
    assert plan.has_stop is True
    assert len(plan.stop_specs) == 1
    spec = plan.stop_specs[0]
    assert spec.block_id == "stopblk_1"
    assert spec.canonical_key == "ta.rsi"
    assert spec.direction == "short"
    assert not any(u.startswith("stop:") for u in plan.unresolved)


async def test_unresolvable_logic_stop_is_surfaced_with_a_stop_prefix(session) -> None:
    plan = await resolve_indicator_plan(session, _config(stop_revision_id="pkgrev_does_not_exist"))
    assert plan.has_stop is False
    stop_unresolved = [u for u in plan.unresolved if u.startswith("stop:")]
    assert stop_unresolved  # the stop block failed to resolve -> RUN fails closed
    assert "stopblk_1" in stop_unresolved[0]


async def test_extract_references_records_the_logic_stop_package_edge() -> None:
    config = _config(stop_revision_id="pkgrev_stop_1")
    refs = _extract_references(config)
    roles = [r["role"] for r in refs]
    assert DependencyRoleEnum.PROTECTION_STOP_INDICATOR in roles
    stop_ref = next(r for r in refs if r["role"] == DependencyRoleEnum.PROTECTION_STOP_INDICATOR)
    assert stop_ref["revision_id"] == "pkgrev_stop_1"


async def test_run_engine_builds_and_consumes_the_stop_plan(session) -> None:
    from entropia.domain.backtest.engine import run_engine

    revision_id = await _indicator_package(session, "ta.rsi")
    plan = await resolve_indicator_plan(session, _config(stop_revision_id=revision_id))

    def _bars() -> Any:
        rows = [
            {
                "timestamp": f"2024-01-{i + 1:02d}T00:00:00Z",
                "open": "100",
                "high": "100",
                "low": "100",
                "close": "100",
                "volume": "10",
            }
            for i in range(24)
        ]
        yield rows

    out = run_engine(
        strategy_config=_config(stop_revision_id=revision_id),
        bar_batches=_bars(),
        execution_key="ek_logic_stop",
        indicator_plan=plan,
    )
    # The stop evaluators were built from the resolved plan and carried through the run.
    assert out.diagnostics["logic_stop_blocks"] == 1
    assert out.diagnostics["stop_trigger_requirement"] == "any_active"
