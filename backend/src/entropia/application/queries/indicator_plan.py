"""Resolve a pinned StrategyConfig into a computable indicator plan (post-V1 Slice C).

The DB-touching companion to the pure ``domain.backtest.indicators`` compute. For
each enabled indicator block the engine would replay, this dereferences the pinned
indicator *package revision* to learn WHICH canonical TA call it resolves to (from
the revision's frozen ``dependency_snapshot`` — the package body is never executed),
maps that to a built-in directional indicator, and folds in the block's trigger /
direction / validity / requirement plus the signal-block aggregation rule.

Honest boundary — every skipped block is surfaced as an ``unresolved`` warning, never
silently dropped:

* ``indicator_native_trigger`` (plain), ``indicator_native_trigger_plus_condition``
  (the cross GATED by conditions) and ``indicator_output_plus_condition`` (a
  condition-only signal whose direction comes from a REQUIRED cross edge) are computed;
  a condition-only block with no required cross is unresolved (no directional edge);
* a block may compute on a higher timeframe than the base bars: an explicit override
  strictly coarser than the pinned revision's base timeframe resamples (post-V1 (c));
  an override finer than a known base cannot be up-sampled and is honest-unresolved;
* only canonical keys with a defined native trigger fire (``ta.sma``/``ta.ema``/
  ``ta.rma``/``ta.wma``/``ta.rsi``); ``ta.atr``/``ta.vwap`` are recognized but
  non-directional in this slice. A condition's RHS may be a constant threshold, a
  bounded ``reference`` series, OR a second separately-pinned indicator package
  (``reference_package_ref`` — the two-package indicator-vs-indicator form, e.g. a
  fast-MA vs a slow-MA cross); a reference package that resolves to no computable
  series leaves the block honest-unresolved.

If no entry block resolves, the returned plan has no entry specs and the engine falls
back to its labelled breakout proxy.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.indicators import (
    CONDITION_KEYS,
    CONDITION_SOURCES,
    DEFAULT_CONDITION_SOURCE,
    DIRECTIONAL_KEYS,
    RANGE_CONDITION_KEYS,
    ConditionSpec,
    IndicatorPlan,
    IndicatorSpec,
    SignalRule,
    condition_direction,
    default_length,
    timeframe_seconds,
)
from entropia.domain.strategy.config import ConditionBlock, IndicatorBlock, StrategyConfig
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo

_NATIVE_TRIGGER = "indicator_native_trigger"
_NATIVE_PLUS_CONDITION = "indicator_native_trigger_plus_condition"
_OUTPUT_PLUS_CONDITION = "indicator_output_plus_condition"
# ``*_native_trigger_plus_condition`` fires the indicator's own cross GATED by the
# conditions; ``indicator_output_plus_condition`` has no native trigger and takes its
# direction from a REQUIRED cross edge (crosses_above -> long, crosses_below -> short).
_ACCEPTED_TRIGGERS = frozenset({_NATIVE_TRIGGER, _NATIVE_PLUS_CONDITION, _OUTPUT_PLUS_CONDITION})
_CONDITION_TRIGGERS = frozenset({_NATIVE_PLUS_CONDITION, _OUTPUT_PLUS_CONDITION})
_BASE_TIMEFRAMES = frozenset({"same_as_base_tf", "use_package_default_tf"})
_LENGTH_KEYS = ("length", "period", "len")
_LOWER_KEYS = ("rsi_lower", "lower", "oversold")
_UPPER_KEYS = ("rsi_upper", "upper", "overbought")
_THRESHOLD_KEYS = ("threshold", "value", "level")
_SOURCE_KEYS = ("source", "input", "series")
# ``cond.between`` bounds (both mandatory) and the optional series ``reference`` RHS.
_BOUND_LOWER_KEYS = ("lower", "lower_bound", "min")
_BOUND_UPPER_KEYS = ("upper", "upper_bound", "max")
_REFERENCE_KEYS = ("reference", "compare_to", "other")
# Look-back for the 2nd-package RHS indicator (``reference_package_ref``); the reference
# package's own body is never executed, so its length comes from a dedicated override key
# or the engine-version default (a reproducibility constant).
_REFERENCE_LENGTH_KEYS = ("reference_length", "compare_length", "reference_len")


async def resolve_indicator_plan(
    session: AsyncSession, strategy_config: StrategyConfig
) -> IndicatorPlan:
    """Build the deterministic indicator plan for a pinned strategy config."""
    base_seconds = await _resolve_base_seconds(session, strategy_config)
    entry_logic = strategy_config.position_entry_logic
    entry_specs, entry_unresolved = await _resolve_blocks(
        session, entry_logic.indicator_blocks, "entry", base_seconds
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
            session, exit_logic.indicator_blocks, "exit", base_seconds
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
    session: AsyncSession,
    blocks: list[IndicatorBlock] | None,
    side: str,
    base_seconds: int | None,
) -> tuple[tuple[IndicatorSpec, ...], list[str]]:
    specs: list[IndicatorSpec] = []
    unresolved: list[str] = []
    for block in blocks or []:
        if block.enabled is False:
            continue
        spec, reason = await _resolve_block(session, block, base_seconds)
        if spec is not None:
            specs.append(spec)
        elif reason is not None:
            unresolved.append(f"{side}:{block.block_id}:{reason}")
    return tuple(specs), unresolved


async def _resolve_block(
    session: AsyncSession, block: IndicatorBlock, base_seconds: int | None
) -> tuple[IndicatorSpec | None, str | None]:
    trigger = str(block.trigger_source)
    if trigger not in _ACCEPTED_TRIGGERS:
        return None, f"trigger_source_deferred:{block.trigger_source}"
    resample_seconds, tf_reason = _resolve_timeframe(str(block.timeframe), base_seconds)
    if tf_reason is not None:
        return None, tf_reason

    revision = await pkg_repo.get_revision(session, block.package_ref.package_revision_id)
    if revision is None:
        return None, "package_revision_unresolved"
    key = _primary_directional_key(revision.dependency_snapshot)
    if key is None:
        return None, "no_directional_dependency"

    conditions: tuple[ConditionSpec, ...] = ()
    condition_rule: str | None = None
    min_condition_support: int | None = None
    condition_only = trigger == _OUTPUT_PLUS_CONDITION
    if trigger in _CONDITION_TRIGGERS:
        # The block's effective timeframe is its own resample span when it computes on a
        # higher timeframe, else the base bars — the floor a per-condition reference
        # timeframe (post-V1 (i)) must be strictly coarser than.
        block_effective_seconds = resample_seconds if resample_seconds is not None else base_seconds
        conditions, reason = await _resolve_conditions(session, block, block_effective_seconds)
        if reason is not None:
            return None, reason
        condition_rule = str(block.condition_block_rule) if block.condition_block_rule else None
        min_condition_support = block.min_supporting_condition_count
        if condition_only:
            reason = _condition_only_direction_reason(conditions)
            if reason is not None:
                return None, reason

    overrides = block.parameter_overrides or {}
    kwargs: dict[str, Any] = {
        "block_id": block.block_id,
        "canonical_key": key,
        "length": _int_override(overrides, _LENGTH_KEYS) or default_length(key),
        "direction": str(block.direction),
        "requirement": str(block.requirement),
        "validity": str(block.validity),
        "conditions": conditions,
        "condition_rule": condition_rule,
        "min_condition_support": min_condition_support,
        "condition_only": condition_only,
        "resample_seconds": resample_seconds,
    }
    lower = _decimal_override(overrides, _LOWER_KEYS)
    if lower is not None:
        kwargs["rsi_lower"] = lower
    upper = _decimal_override(overrides, _UPPER_KEYS)
    if upper is not None:
        kwargs["rsi_upper"] = upper
    return IndicatorSpec(**kwargs), None


async def _resolve_base_seconds(
    session: AsyncSession, strategy_config: StrategyConfig
) -> int | None:
    """Span (seconds) of the pinned market revision's base bar timeframe, if known.

    Read from the immutable pinned revision (reproducibility-safe). ``None`` when the
    revision carries no bar-timeframe resolution — a higher-TF override then resolves
    anyway (it degrades to the base bars deterministically) but cannot be validated as
    strictly coarser than the base."""
    base_tf = await md_repo.get_base_timeframe_for_revision(
        session, strategy_config.data.market_dataset_revision_id
    )
    return timeframe_seconds(base_tf) if base_tf else None


def _resolve_timeframe(timeframe: str, base_seconds: int | None) -> tuple[int | None, str | None]:
    """Resolve a block's timeframe to a resample span (seconds) or an unresolved reason.

    ``same_as_base_tf`` / ``use_package_default_tf`` compute on the base bars (a ``None``
    span). A concrete override resamples the base bars to that timeframe when it is
    strictly COARSER than the base; equal-to-base collapses back to the base compute. An
    override strictly FINER than a known base cannot be up-sampled and is honest-
    unresolved. When the base timeframe is unknown the override still resolves (it
    degrades deterministically to the base bars) — the boundary is surfaced, not guessed."""
    if timeframe in _BASE_TIMEFRAMES:
        return None, None
    target = timeframe_seconds(timeframe)
    if target is None:
        return None, f"timeframe_override_unrecognized:{timeframe}"
    if base_seconds is not None:
        if target < base_seconds:
            return None, f"timeframe_finer_than_base:{timeframe}"
        if target == base_seconds:
            return None, None
    return target, None


async def _resolve_conditions(
    session: AsyncSession, block: IndicatorBlock, block_effective_seconds: int | None
) -> tuple[tuple[ConditionSpec, ...], str | None]:
    """Dereference a block's nested condition packages into computable threshold specs.

    Fail-closed and honest: any enabled condition that cannot fully resolve (missing
    package, no recognized ``cond.*`` dependency, or no threshold) leaves the WHOLE
    block unresolved with a specific reason, rather than computing a partial gate.
    ``block_effective_seconds`` is the parent block's effective timeframe span (its
    resample span, else the base bars) — the floor a per-condition reference timeframe
    must be coarser than."""
    enabled = [c for c in (block.condition_blocks or []) if c.enabled is not False]
    if not enabled:
        # A ``*_plus_condition`` trigger with no conditions is a misconfiguration; a
        # vacuous gate would silently equal the plain native trigger, so surface it.
        return (), "condition_blocks_missing"
    specs: list[ConditionSpec] = []
    for cond in enabled:
        spec, reason = await _resolve_condition(session, cond, block_effective_seconds)
        if spec is None:
            return (), reason or "condition_unresolved"
        specs.append(spec)
    return tuple(specs), None


def _condition_only_direction_reason(conditions: tuple[ConditionSpec, ...]) -> str | None:
    """``None`` if the REQUIRED conditions define one directional edge, else a reason.

    A condition-only signal takes its direction from a cross primitive; the directional
    driver must be REQUIRED (an entry direction cannot hinge on an optional supporting
    condition). No cross among the required set -> no edge; opposing crosses -> a
    conflict. Both are surfaced as honest-unresolved rather than silently mis-directed."""
    required = [c for c in conditions if c.requirement == "required"]
    pool = required or list(conditions)
    directions = {condition_direction(c.canonical_key) for c in pool}
    directions.discard(None)
    if len(directions) == 1:
        return None
    if not directions:
        return "condition_only_no_directional_edge"
    return "condition_only_conflicting_direction"


async def _resolve_condition(
    session: AsyncSession, cond: ConditionBlock, block_effective_seconds: int | None
) -> tuple[ConditionSpec | None, str | None]:
    revision = await pkg_repo.get_revision(session, cond.package_ref.package_revision_id)
    if revision is None:
        return None, f"condition_package_unresolved:{cond.condition_block_id}"
    key = _primary_condition_key(revision.dependency_snapshot)
    if key is None:
        return None, f"condition_no_recognized_key:{cond.condition_block_id}"
    overrides = cond.parameter_overrides or {}
    source = _source_override(overrides)

    # An optional 2nd separately-pinned indicator package as the RHS series (two-package
    # indicator-vs-indicator), optionally on a coarser per-condition timeframe (post-V1 (i)).
    # Fail-closed if pinned but not a computable series.
    ref_key, ref_length, ref_resample, ref_reason = await _resolve_reference_package(
        session, cond, block_effective_seconds
    )
    if ref_reason is not None:
        return None, ref_reason

    if key in RANGE_CONDITION_KEYS:
        if ref_key is not None:
            # A range compares against fixed bounds, not an RHS series; a reference
            # package here is a misconfiguration, surfaced rather than silently ignored.
            return None, f"condition_reference_package_on_range:{cond.condition_block_id}"
        # A range needs BOTH bounds (no universal default) and a well-ordered interval.
        lower = _decimal_override(overrides, _BOUND_LOWER_KEYS)
        upper = _decimal_override(overrides, _BOUND_UPPER_KEYS)
        if lower is None or upper is None:
            return None, f"condition_bounds_missing:{cond.condition_block_id}"
        if lower >= upper:
            return None, f"condition_bounds_invalid:{cond.condition_block_id}"
        return (
            ConditionSpec(
                condition_block_id=cond.condition_block_id,
                canonical_key=key,
                source=source,
                threshold=None,
                requirement=str(cond.requirement),
                validity=str(cond.validity),
                lower=lower,
                upper=upper,
            ),
            None,
        )

    # above/below/crosses RHS, in precedence order: a 2nd-package indicator series, a
    # bounded ``reference`` series, or a constant threshold.
    if ref_key is not None:
        return (
            ConditionSpec(
                condition_block_id=cond.condition_block_id,
                canonical_key=key,
                source=source,
                threshold=None,
                requirement=str(cond.requirement),
                validity=str(cond.validity),
                reference_key=ref_key,
                reference_length=ref_length,
                reference_resample_seconds=ref_resample,
            ),
            None,
        )
    reference = _reference_override(overrides)
    threshold: Decimal | None = None
    if reference is None:
        threshold = _decimal_override(overrides, _THRESHOLD_KEYS)
        if threshold is None:
            # No universal default for a threshold (instrument/scale specific); unlike an
            # indicator length it MUST be supplied when there is no reference series.
            return None, f"condition_threshold_missing:{cond.condition_block_id}"
    return (
        ConditionSpec(
            condition_block_id=cond.condition_block_id,
            canonical_key=key,
            source=source,
            threshold=threshold,
            requirement=str(cond.requirement),
            validity=str(cond.validity),
            reference=reference,
        ),
        None,
    )


async def _resolve_reference_package(
    session: AsyncSession, cond: ConditionBlock, block_effective_seconds: int | None
) -> tuple[str | None, int | None, int | None, str | None]:
    """Dereference the optional 2nd pinned INDICATOR package into ``(key, length, resample)``.

    The two-package indicator-vs-indicator RHS: the condition compares its source against
    THIS package's computed output series (e.g. a fast MA vs a slow MA). Returns
    ``(None, None, None, None)`` when no reference package is pinned; a specific fail-closed
    reason when pinned but the revision is missing or resolves to no computable series
    (only ``DIRECTIONAL_KEYS`` — the MA/RSI family — are computable as an inline series).

    ``resample`` is the per-condition multi-timeframe reference span (post-V1 (i)): the RHS
    may compute on a timeframe strictly COARSER than the parent block's effective timeframe
    (``block_effective_seconds``). A reference-timeframe override with NO reference package
    has no series to resample — a misconfiguration surfaced, not silently ignored."""
    ref = cond.reference_package_ref
    ref_tf = str(cond.reference_timeframe)
    if ref is None:
        if ref_tf not in _BASE_TIMEFRAMES:
            return (
                None,
                None,
                None,
                (f"condition_reference_timeframe_without_package:{cond.condition_block_id}"),
            )
        return None, None, None, None
    revision = await pkg_repo.get_revision(session, ref.package_revision_id)
    if revision is None:
        return None, None, None, f"condition_reference_package_unresolved:{cond.condition_block_id}"
    key = _primary_directional_key(revision.dependency_snapshot)
    if key is None:
        return None, None, None, f"condition_reference_no_series:{cond.condition_block_id}"
    resample, tf_reason = _resolve_reference_timeframe(
        ref_tf, block_effective_seconds, cond.condition_block_id
    )
    if tf_reason is not None:
        return None, None, None, tf_reason
    overrides = cond.parameter_overrides or {}
    length = _int_override(overrides, _REFERENCE_LENGTH_KEYS) or default_length(key)
    return key, length, resample, None


def _resolve_reference_timeframe(
    timeframe: str, block_effective_seconds: int | None, condition_block_id: str
) -> tuple[int | None, str | None]:
    """Resolve a condition's reference timeframe to a resample span (seconds) or a reason.

    Per-condition multi-timeframe reference (post-V1 (i)). The RHS reference indicator may
    compute on a timeframe COARSER than the parent block's effective timeframe.
    ``same_as_base_tf`` / ``use_package_default_tf`` keep the RHS on the block's timeframe (a
    ``None`` span — the (#53) two-package behaviour). A concrete override resamples the RHS
    when strictly coarser than the block; equal-to-block collapses to the block compute. An
    override strictly FINER than a known block timeframe cannot be up-sampled (the RHS would
    have to advance faster than the condition ticks) and is honest-unresolved. When the block
    timeframe is unknown the override still resolves (it degrades deterministically to the
    block's bars) — the boundary is surfaced, not guessed."""
    if timeframe in _BASE_TIMEFRAMES:
        return None, None
    target = timeframe_seconds(timeframe)
    if target is None:
        return None, f"condition_reference_timeframe_unrecognized:{condition_block_id}"
    if block_effective_seconds is not None:
        if target < block_effective_seconds:
            return None, f"condition_reference_timeframe_finer_than_block:{condition_block_id}"
        if target == block_effective_seconds:
            return None, None
    return target, None


def _primary_condition_key(dependency_snapshot: dict[str, Any]) -> str | None:
    """The first resolved canonical call that is a recognized ``cond.*`` comparator."""
    resolved = None
    if isinstance(dependency_snapshot, dict):
        resolved = dependency_snapshot.get("resolved")
    if not isinstance(resolved, list):
        return None
    for entry in resolved:
        if isinstance(entry, dict) and str(entry.get("canonical_key", "")) in CONDITION_KEYS:
            return str(entry["canonical_key"])
    return None


def _source_override(overrides: dict[str, Any]) -> str:
    """The condition's compared source; defaults to the engine-version ``close``."""
    for key in _SOURCE_KEYS:
        raw = overrides.get(key)
        if isinstance(raw, str) and raw in CONDITION_SOURCES:
            return raw
    return DEFAULT_CONDITION_SOURCE


def _reference_override(overrides: dict[str, Any]) -> str | None:
    """An optional ``reference`` series RHS (bounded, single-package).

    When set, the comparator's right-hand side is another available series (a bar price
    field or the parent block's ``indicator_output``) instead of a constant threshold.
    Comparing two SEPARATE indicator packages uses ``reference_package_ref`` instead
    (resolved in ``_resolve_reference_package``)."""
    for key in _REFERENCE_KEYS:
        raw = overrides.get(key)
        if isinstance(raw, str) and raw in CONDITION_SOURCES:
            return raw
    return None


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
