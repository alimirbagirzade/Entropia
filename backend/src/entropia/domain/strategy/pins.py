"""The package references a StrategyConfig pins, in ONE traversal (O-24b).

Two hot-path callers walk the same tree and must never disagree about which
packages a strategy depends on:

* ``queries.indicator_plan.resolve_indicator_plan`` dereferences each pinned
  revision to build the computable plan (and prefetches the whole set in one
  batch — a ref this traversal missed would be read as *unresolved* and would
  silently fail a block closed);
* ``commands.backtest_run_context`` records each pin (plus its Strategy-local
  parameter overrides) into the immutable Run Manifest.

Keeping the walk here makes drift impossible: a new reference site is added once
and both callers see it. Pure — no session, no I/O.

Skip rules mirror the engine exactly: a DISABLED block or condition is never
dereferenced, so it is never pinned either. The traversal is deliberately a
SUPERSET of what any single caller dereferences (it does not filter on
``trigger_source``); over-collecting costs one extra row in a batch already being
read, while under-collecting would change behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from entropia.domain.strategy.config import IndicatorBlock, PackageReference, StrategyConfig

# The role prefix every Logic-Based Scaling pin carries (matching the plan's ``scale:``
# unresolved prefix). The Run Manifest does NOT yet record this group — see
# ``backtest_run_context._strategy_entry`` — so it is filtered there by this prefix
# rather than by omitting it here, which would leave the resolver's own pins unprefetched.
SCALING_ROLE = "scale"


@dataclass(frozen=True, slots=True)
class PinnedPackage:
    """One pinned package reference plus where in the config it sits."""

    role: str
    block_id: str
    condition_block_id: str | None
    leg_index: int | None
    ref: PackageReference
    parameter_overrides: dict[str, Any] | None


def iter_pinned_packages(config: StrategyConfig) -> list[PinnedPackage]:
    """Every package reference the engine's block traversal would dereference.

    Entry, exit, Logic-Based Stop and (S5c) Logic-Based Scaling blocks, their nested
    enabled conditions, each condition's reference package and its N-ary chain legs, in
    a deterministic depth-first order.

    The scaling group is deliberately collected WITHOUT re-testing
    ``scaling_logic.enabled`` / ``method``: a superset costs one extra row in a batch
    already being read, while a subset would leave a block the resolver DOES dereference
    unprefetched — which would read as 'unresolved' and fail it closed."""
    pinned: list[PinnedPackage] = []
    stop_blocks = (
        config.protection_stop_logic.logic_blocks
        if config.protection_stop_logic is not None
        else None
    )
    scaling = config.scaling_logic
    scale_blocks = (
        scaling.logic_scaling.indicator_blocks
        if scaling is not None and scaling.logic_scaling is not None
        else None
    )
    groups: list[tuple[str, list[IndicatorBlock] | None]] = [
        ("entry", config.position_entry_logic.indicator_blocks),
        ("exit", config.position_exit_logic.indicator_blocks),
        ("stop", stop_blocks),
        (SCALING_ROLE, scale_blocks),
    ]
    for role, blocks in groups:
        for block in blocks or []:
            if block.enabled is False:
                continue
            pinned.append(
                PinnedPackage(
                    role=role,
                    block_id=block.block_id,
                    condition_block_id=None,
                    leg_index=None,
                    ref=block.package_ref,
                    parameter_overrides=block.parameter_overrides,
                )
            )
            pinned.extend(_pinned_condition_packages(role, block))
    return pinned


def pinned_package_revision_ids(config: StrategyConfig) -> list[str]:
    """The de-duplicated revision ids of :func:`iter_pinned_packages`, in first-seen
    order — the exact prefetch set for a batched dereference."""
    return list(dict.fromkeys(p.ref.package_revision_id for p in iter_pinned_packages(config)))


def _pinned_condition_packages(role: str, block: IndicatorBlock) -> list[PinnedPackage]:
    pinned: list[PinnedPackage] = []
    for condition in block.condition_blocks or []:
        if condition.enabled is False:
            continue
        pinned.append(
            PinnedPackage(
                role=f"{role}_condition",
                block_id=block.block_id,
                condition_block_id=condition.condition_block_id,
                leg_index=None,
                ref=condition.package_ref,
                parameter_overrides=condition.parameter_overrides,
            )
        )
        if condition.reference_package_ref is not None:
            pinned.append(
                PinnedPackage(
                    role=f"{role}_condition_reference",
                    block_id=block.block_id,
                    condition_block_id=condition.condition_block_id,
                    leg_index=None,
                    ref=condition.reference_package_ref,
                    parameter_overrides=condition.parameter_overrides,
                )
            )
        for index, leg in enumerate(condition.additional_reference_package_refs or []):
            pinned.append(
                PinnedPackage(
                    role=f"{role}_condition_reference_leg",
                    block_id=block.block_id,
                    condition_block_id=condition.condition_block_id,
                    leg_index=index,
                    ref=leg.package_ref,
                    parameter_overrides=leg.parameter_overrides,
                )
            )
    return pinned


__all__ = [
    "SCALING_ROLE",
    "PinnedPackage",
    "iter_pinned_packages",
    "pinned_package_revision_ids",
]
