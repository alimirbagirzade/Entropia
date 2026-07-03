"""Resolve a pinned StrategyConfig into a computable indicator plan (post-V1 Slice C).

The DB-touching companion to the pure ``domain.backtest.indicators`` compute. For
each enabled indicator block the engine would replay, this dereferences the pinned
indicator *package revision* to learn WHICH canonical TA call it resolves to (from
the revision's frozen ``dependency_snapshot`` — the package body is never executed),
maps that to a built-in directional indicator, and folds in the block's trigger /
direction / validity / requirement plus the signal-block aggregation rule.

Native-trigger-only foundation (honest boundary — every skipped block is surfaced as
an ``unresolved`` warning, never silently dropped):

* only ``trigger_source == "indicator_native_trigger"`` is computed; ``*_plus_condition``
  sources are deferred (computing only the native part would drop the condition and
  change the signal semantics);
* only base-timeframe blocks (``same_as_base_tf`` / ``use_package_default_tf``) are
  computed; an explicit timeframe override is deferred (needs multi-TF resampling);
* only canonical keys with a defined native trigger fire (``ta.sma``/``ta.ema``/
  ``ta.rma``/``ta.wma``/``ta.rsi``); ``ta.atr``/``ta.vwap`` are recognized but
  non-directional in this slice.

If no entry block resolves, the returned plan has no entry specs and the engine falls
back to its labelled breakout proxy.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.indicators import (
    DIRECTIONAL_KEYS,
    IndicatorPlan,
    IndicatorSpec,
    SignalRule,
    default_length,
)
from entropia.domain.strategy.config import IndicatorBlock, StrategyConfig
from entropia.infrastructure.postgres.repositories import packages as pkg_repo

_NATIVE_TRIGGER = "indicator_native_trigger"
_BASE_TIMEFRAMES = frozenset({"same_as_base_tf", "use_package_default_tf"})
_LENGTH_KEYS = ("length", "period", "len")
_LOWER_KEYS = ("rsi_lower", "lower", "oversold")
_UPPER_KEYS = ("rsi_upper", "upper", "overbought")


async def resolve_indicator_plan(
    session: AsyncSession, strategy_config: StrategyConfig
) -> IndicatorPlan:
    """Build the deterministic indicator plan for a pinned strategy config."""
    entry_logic = strategy_config.position_entry_logic
    entry_specs, entry_unresolved = await _resolve_blocks(
        session, entry_logic.indicator_blocks, "entry"
    )
    entry_rule = SignalRule(
        rule=str(entry_logic.signal_block.rule),
        min_supporting_count=entry_logic.signal_block.min_supporting_count,
    )

    exit_logic = strategy_config.position_exit_logic
    exit_specs: tuple[IndicatorSpec, ...] = ()
    exit_rule: SignalRule | None = None
    exit_unresolved: list[str] = []
    if exit_logic.indicator_blocks:
        exit_specs, exit_unresolved = await _resolve_blocks(
            session, exit_logic.indicator_blocks, "exit"
        )
        if exit_logic.signal_block is not None:
            exit_rule = SignalRule(
                rule=str(exit_logic.signal_block.rule),
                min_supporting_count=exit_logic.signal_block.min_supporting_count,
            )

    return IndicatorPlan(
        entry_rule=entry_rule,
        entry_specs=entry_specs,
        exit_rule=exit_rule,
        exit_specs=exit_specs,
        exit_on_opposite=bool(strategy_config.conflict_position_handling.exit_on_opposite_signal),
        unresolved=tuple(entry_unresolved + exit_unresolved),
    )


async def _resolve_blocks(
    session: AsyncSession, blocks: list[IndicatorBlock] | None, side: str
) -> tuple[tuple[IndicatorSpec, ...], list[str]]:
    specs: list[IndicatorSpec] = []
    unresolved: list[str] = []
    for block in blocks or []:
        if block.enabled is False:
            continue
        spec, reason = await _resolve_block(session, block)
        if spec is not None:
            specs.append(spec)
        elif reason is not None:
            unresolved.append(f"{side}:{block.block_id}:{reason}")
    return tuple(specs), unresolved


async def _resolve_block(
    session: AsyncSession, block: IndicatorBlock
) -> tuple[IndicatorSpec | None, str | None]:
    if str(block.trigger_source) != _NATIVE_TRIGGER:
        return None, f"trigger_source_deferred:{block.trigger_source}"
    if str(block.timeframe) not in _BASE_TIMEFRAMES:
        return None, f"timeframe_override_deferred:{block.timeframe}"

    revision = await pkg_repo.get_revision(session, block.package_ref.package_revision_id)
    if revision is None:
        return None, "package_revision_unresolved"
    key = _primary_directional_key(revision.dependency_snapshot)
    if key is None:
        return None, "no_directional_dependency"

    overrides = block.parameter_overrides or {}
    kwargs: dict[str, Any] = {
        "block_id": block.block_id,
        "canonical_key": key,
        "length": _int_override(overrides, _LENGTH_KEYS) or default_length(key),
        "direction": str(block.direction),
        "requirement": str(block.requirement),
        "validity": str(block.validity),
    }
    lower = _decimal_override(overrides, _LOWER_KEYS)
    if lower is not None:
        kwargs["rsi_lower"] = lower
    upper = _decimal_override(overrides, _UPPER_KEYS)
    if upper is not None:
        kwargs["rsi_upper"] = upper
    return IndicatorSpec(**kwargs), None


def _primary_directional_key(dependency_snapshot: dict[str, Any]) -> str | None:
    """The first resolved canonical TA call that has a native directional trigger.

    ``dependency_snapshot["resolved"]`` is the frozen list of resolver refs the
    package pinned (each ``{"canonical_key", ...}``). A recognized-but-non-directional
    call (``ta.atr``/``ta.vwap``) alone does not yield a signal."""
    resolved = None
    if isinstance(dependency_snapshot, dict):
        resolved = dependency_snapshot.get("resolved")
    if not isinstance(resolved, list):
        return None
    for entry in resolved:
        if isinstance(entry, dict) and str(entry.get("canonical_key", "")) in DIRECTIONAL_KEYS:
            return str(entry["canonical_key"])
    return None


def _int_override(overrides: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        raw = overrides.get(key)
        if isinstance(raw, bool):
            continue
        if isinstance(raw, int) and raw > 0:
            return raw
        if isinstance(raw, str) and raw.isdigit() and int(raw) > 0:
            return int(raw)
    return None


def _decimal_override(overrides: dict[str, Any], keys: tuple[str, ...]) -> Decimal | None:
    for key in keys:
        raw = overrides.get(key)
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
            continue
        try:
            return Decimal(str(raw))
        except (InvalidOperation, ValueError):
            continue
    return None


__all__ = ["resolve_indicator_plan"]
