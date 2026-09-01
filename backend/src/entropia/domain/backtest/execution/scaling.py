"""Partial close aftermath and the same-direction scaling ladder (K-09 slice b).

Extracted from ``domain.backtest.engine``. The two modelled-config predicates move
verbatim; the rest is the decide/apply split this refactor has used throughout —
``apply_partial_aftermath`` mutates only the position object handed to it and REPORTS
whether a profit lock was applied, while ``resolve_scale_layer_size``,
``scale_threshold_crossed`` and ``resolve_scale_rejection`` answer the ladder's
questions without touching the loop's equity or counters.

``resolve_scale_rejection`` is the one worth having on its own. Its cap PRECEDENCE is
observable — the losing cap's name is written into the rejected layer's ledger reason —
so the order (degenerate size, then the per-strategy total, then the configured size
limit, then the sleeve, then the composition-wide money cap) is behaviour, not an
implementation detail, and is now pinned by tests. An over-cap layer is REJECTED with
that reason, never auto-trimmed (§11.4 exposure binding).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from entropia.domain.backtest.execution.constants import _HUNDRED, _ONE, _QTY, _ZERO
from entropia.domain.backtest.execution.costs import _effective_fill
from entropia.domain.backtest.execution.fills import _trail_pct
from entropia.domain.backtest.execution.state import _Position
from entropia.domain.backtest.indicators import timeframe_seconds
from entropia.domain.strategy.config import CANONICAL_TIMEFRAMES

if TYPE_CHECKING:
    from entropia.domain.strategy.config import ScalingLogic, StrategyConfig


# §4 Partial-close aftermath modelled by the bar-replay (F-07c). ``close_percentage`` < 100
# closes only that fraction of the position on an EXIT SIGNAL and holds the remainder; the
# aftermath governs the remainder. ``move_stop_to_entry`` (breakeven the remainder's stop) and
# ``close_all`` (the signal closes 100% regardless) are deterministic over OHLCV. A
# ``move_stop_to_entry`` / ``lock_in_profit`` need no extra strategy config (they mutate the
# remainder's stop from data already on the open position). A full close (close_percentage
# == 100) never produces a remainder, so its aftermath is irrelevant and always modelled.
# ``trailing_stop`` is CONFIG-DEPENDENT (post-V1 (f)): the schema carries no separate
# trailing-distance/activation fields on ``PositionExitLogic`` itself, so the aftermath
# reuses ``protection_stop_logic.trailing_stop`` — modelled only when that rule is
# configured/enabled (checked in ``partial_close_is_modelled`` via ``_trail_pct``).
_MODELLED_PARTIAL_AFTERMATHS = frozenset({"move_stop_to_entry", "close_all", "lock_in_profit"})


def partial_close_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's partial-close behaviour modelled (F-07c/f)?

    The single shared source of truth for the readiness ``STRATEGY_PARTIAL_CLOSE_UNSUPPORTED``
    blocker and the engine's fail-closed entry gate. A full close (``close_percentage`` >= 100)
    is always modelled. A partial close is modelled when its aftermath is move-stop-to-entry,
    close-all or lock-in-profit (self-contained — no extra config needed), or trailing-stop
    WHEN the strategy's own ``protection_stop_logic.trailing_stop`` rule is configured and
    enabled (the aftermath has no trailing parameters of its own to reuse). A trailing-stop
    aftermath with no such rule configured fails closed (blocked at Ready Check AND opens no
    position if a stale readiness state slips through to the worker)."""
    exit_logic = config.position_exit_logic
    if exit_logic.close_percentage >= _HUNDRED:
        return True
    aftermath = exit_logic.partial_aftermath
    if aftermath in _MODELLED_PARTIAL_AFTERMATHS:
        return True
    if aftermath == "trailing_stop":
        return _trail_pct(config) is not None
    return False


def scaling_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's same-direction scaling modelled (F-07d, S5c)?

    The single shared source of truth for the readiness ``STRATEGY_SCALING_UNSUPPORTED``
    blocker and the engine's fail-closed entry gate. Disabled/absent scaling is always
    modelled; enabled scaling is modelled only as the price-distance ladder with a
    derivable positive add size and sane caps — anything else is blocked at Ready Check
    AND opens no position if a stale readiness state slips through to the worker (never a
    silently un-scaled run the user did not configure).

    S5c lifted two halves of that gate. LOGIC-BASED scaling is now modelled (its blocks
    resolve through the same plan resolver as entry/exit/stop and propose a same-direction
    layer on the signal's EDGE), and with it the per-layer TIMEFRAME sequence that doc 02
    §6.1 names as its ONLY consumer: ``same_strategy`` (every layer on the base timeframe)
    and ``custom_sequence`` (layer N on sequence entry N under the closed-bar rule —
    ``layer_timeframe`` / ``layer_bucket``) are both modelled. GH #547 lifted the third
    mode, ``increasing_by_layer``: doc 02 §6.1 fixes the rung (each layer steps ONE
    canonical timeframe up from the run's base — 15m -> 30m -> 1h, i.e.
    ``CANONICAL_TIMEFRAMES`` index + 1), and the signed top-of-ladder decision follows the
    custom_sequence precedent — past the last rung (``1D``) the ladder simply runs out, no
    repeat-the-last or fall-back-to-base rule is invented.

    Still UNMODELLED, on purpose:
    * a flat ``timeframe`` override — that field picks ONE evaluation timeframe for the
      whole ladder and honouring it needs resampled bars the replay does not build (the
      per-layer sequence needs none: it only gates WHICH base bars are decision points);
    * an UNBOUNDED logic ladder — logic-based scaling has no ``layers`` field of its own
      (§5.7 gives ladder depth to the price method only), so with neither
      ``max_scaling_layers`` nor a per-layer timeframe structure to bound it there is no
      declared depth, and a ladder that adds a layer on every signal edge for the life of
      the position is not something to run on a guess.
    """
    scaling = config.scaling_logic
    if scaling is None or not scaling.enabled:
        return True
    if scaling.timeframe != "same_as_base_tf":
        return False
    if scaling.timeframe_mode == "custom_sequence" and not scaling.custom_timeframe_sequence:
        return False
    if scaling.method == "logic_based_scaling":
        return _logic_scaling_is_modelled(scaling)
    if scaling.method != "price_distance_scaling" or scaling.price_scaling is None:
        return False
    if scaling.add_size_value is None or scaling.add_size_value <= _ZERO:
        return False
    limits = scaling.scaling_limits
    if limits is not None:
        if limits.max_scaling_layers is not None and limits.max_scaling_layers < 0:
            return False
        if limits.max_total_position_size is not None and limits.max_total_position_size <= _ZERO:
            return False
    return True


def _logic_scaling_is_modelled(scaling: ScalingLogic) -> bool:
    """The Logic-Based Scaling half of ``scaling_is_modelled`` (S5c, doc 02 §5.7).

    Split out because its conditions differ in KIND from the price ladder's: it needs
    resolvable blocks and a DECLARED DEPTH (it has no ``layers`` field of its own), where
    the price ladder needs a distance and a subtree. Keeping them in one flat chain made
    it read as though ``layers`` bounded both.

    GH #547: ``increasing_by_layer`` counts as a declared depth the same way a custom
    sequence does — the canonical ladder is finite and the mode ends at its top rung
    (``increasing_ladder_depth``), so the ladder can never exceed the rungs above the
    run's base timeframe.
    """
    if scaling.logic_scaling is None or not scaling.logic_scaling.indicator_blocks:
        return False
    limits = scaling.scaling_limits
    bounded = (
        (limits is not None and limits.max_scaling_layers is not None)
        or bool(scaling.timeframe_mode == "custom_sequence" and scaling.custom_timeframe_sequence)
        or scaling.timeframe_mode == "increasing_by_layer"
    )
    if not bounded:
        return False
    if scaling.add_size_value is None or scaling.add_size_value <= _ZERO:
        return False
    if limits is not None:
        if limits.max_scaling_layers is not None and limits.max_scaling_layers < 0:
            return False
        if limits.max_total_position_size is not None and limits.max_total_position_size <= _ZERO:
            return False
    return True


def layer_timeframe(
    config: StrategyConfig, layers_filled: int, *, base_timeframe: str | None = None
) -> str | None:
    """The timeframe the NEXT scaling layer is decided on, or ``None`` when every base bar
    is a decision point (S5c, doc 02 §5.7).

    ``None`` is the same_strategy answer — the ladder is ungated and behaves exactly as it
    did before S5c. Under custom_sequence, layer N (1-based) is decided on sequence entry N,
    so the next layer's timeframe is ``sequence[layers_filled]``. Under increasing_by_layer
    (GH #547) layer N is decided one canonical rung per layer above the RUN's base
    timeframe — ``CANONICAL_TIMEFRAMES[index(base) + N]``, doc 02 §6.1's
    "15m -> 30m -> 1h" — so the caller must pass ``base_timeframe`` (the run-level pinned
    bar timeframe; it is not a config field). A missing or non-canonical base resolves no
    rung at all: the engine's ladder-depth cap (``increasing_ladder_depth``) is 0 there, so
    no candidate is ever evaluated. Past the end of either ladder is UNREACHABLE: the
    engine caps its layer count at the sequence length / the remaining rung count precisely
    so that no "what happens after the last entry" rule has to be invented — the ladder
    simply runs out (the signed GH #547 exhaustion decision is exactly the custom_sequence
    precedent)."""
    scaling = config.scaling_logic
    if scaling is None:
        return None
    if scaling.timeframe_mode == "increasing_by_layer":
        if base_timeframe is None or base_timeframe not in CANONICAL_TIMEFRAMES:
            return None
        rung = CANONICAL_TIMEFRAMES.index(base_timeframe) + layers_filled + 1
        if rung >= len(CANONICAL_TIMEFRAMES):
            return None
        return CANONICAL_TIMEFRAMES[rung]
    if scaling.timeframe_mode != "custom_sequence":
        return None
    sequence = scaling.custom_timeframe_sequence
    if not sequence or layers_filled >= len(sequence):
        return None
    return sequence[layers_filled]


def increasing_ladder_depth(base_timeframe: str | None) -> int:
    """How many rungs the canonical ladder holds ABOVE the run's base timeframe (GH #547).

    This is the increasing_by_layer analogue of custom_sequence's ``len(sequence)`` bound:
    the engine caps the ladder's layer count at this depth, so a layer past the top rung
    (``1D``) is never a candidate — the ladder runs out rather than repeating the last
    rung, falling back to the base, or ungating (the signed exhaustion decision). A run
    with no pinned bar timeframe, or one off the canonical ladder, has no rung above it —
    depth 0: the position still opens and trades, it just never scales (fail closed for
    the ladder, inert for nothing else)."""
    if base_timeframe is None or base_timeframe not in CANONICAL_TIMEFRAMES:
        return 0
    return len(CANONICAL_TIMEFRAMES) - 1 - CANONICAL_TIMEFRAMES.index(base_timeframe)


def layer_bucket(epoch_ms: int | None, layer_timeframe_: str | None) -> int | None:
    """The layer timeframe's candle index a bar falls in, or ``None`` when the ladder is
    ungated / the moment is unplaceable / the timeframe is unrecognized.

    ``floor(epoch / span)`` — the SAME bucketing the multi-timeframe indicator path uses
    (``indicators._htf_bucket``), so "a higher-TF candle closed" means one thing in this
    engine: the bucket index CHANGED, i.e. the first base bar of the next bucket is the
    decision point. Reusing that convention is the point — a second, subtly different
    closed-bar rule for scaling would make two parts of the same run disagree about when a
    15m candle ends. A ``None`` here leaves the caller's anchor untouched and the candidate
    ungated only for same_strategy; for a gated ladder an unplaceable bar simply never
    becomes a decision point (fail closed, the ``_epoch_seconds`` precedent)."""
    if layer_timeframe_ is None or epoch_ms is None:
        return None
    span = timeframe_seconds(layer_timeframe_)
    if span is None:
        return None
    return epoch_ms // (span * 1000)


def apply_partial_aftermath(
    pos: _Position,
    exit_price_raw: Decimal,
    *,
    aftermath: str,
    half_spread: Decimal,
    slippage: Decimal,
) -> bool:
    """Govern the remainder after a partial close (F-07c/f §4); return True iff a profit
    lock was applied (the caller books the ``lock_in_locks`` counter).

    ``move_stop_to_entry`` breakevens the remainder's percentage stop (any dip back to
    the entry now stops it out). ``lock_in_profit`` moves the stop to the cost-adjusted
    price achieved AT this partial close — a one-time ratchet: a LATER partial close
    (long via ``max``, short via ``min``) can only tighten it further, never loosen it
    (it never reaches here without a prior stop level, so the initial application always
    sets it verbatim). ``trailing_stop`` force-activates the remainder's
    already-configured protection trailing stop (``partial_close_is_modelled``
    guarantees ``trail_pct`` / ``trail_lock_in_pct`` are set whenever this branch is
    reachable) immediately, even if the protection-level profit-lock threshold has not
    yet been reached — the partial exit itself is the activation event; ``trail_anchor``
    only ever moves toward the threshold (``max``/``min``), never backward, so it cannot
    loosen an already-active trail. ``close_all`` never reaches here (it closes fully)."""
    is_long = pos.direction == "long"
    if aftermath == "move_stop_to_entry":
        pos.pct_stop = pos.entry_price
        return False
    if aftermath == "lock_in_profit":
        exit_eff = _effective_fill(
            exit_price_raw, is_buy=not is_long, half_spread=half_spread, slip=slippage
        )
        if pos.pct_stop is None:
            pos.pct_stop = exit_eff
        elif is_long:
            pos.pct_stop = max(pos.pct_stop, exit_eff)
        else:
            pos.pct_stop = min(pos.pct_stop, exit_eff)
        return True
    if (
        aftermath == "trailing_stop"
        and pos.trail_pct is not None
        and pos.trail_lock_in_pct is not None
    ):
        threshold = (
            pos.entry_price * (_ONE + pos.trail_lock_in_pct)
            if is_long
            else pos.entry_price * (_ONE - pos.trail_lock_in_pct)
        )
        pos.trail_anchor = (
            max(pos.trail_anchor, threshold) if is_long else min(pos.trail_anchor, threshold)
        )
        return True
    return False


def scale_threshold_crossed(
    *, reference: Decimal, distance_pct: Decimal, close: Decimal, is_long: bool
) -> bool:
    """Has this bar's close crossed ``distance_pct``% ADVERSE from the ladder reference?

    One cross = ONE candidate. The caller advances the reference on every cross, accepted
    or not, so each further candidate needs a further full step — bounded events, never
    O(bars) re-trigger spam."""
    step = reference * distance_pct / _HUNDRED
    return close <= reference - step if is_long else close >= reference + step


def resolve_scale_layer_size(
    *, basis: str, value: Decimal, initial_size: Decimal, current_size: Decimal
) -> Decimal:
    """The candidate layer's size for the configured add-size basis (§11.3)."""
    if basis == "fixed_amount":
        return value.quantize(_QTY)
    layer_base = initial_size if basis == "percent_of_initial" else current_size
    return (layer_base * value / _HUNDRED).quantize(_QTY)


def resolve_scale_rejection(
    *,
    layer_size: Decimal,
    layer_notional: Decimal,
    scaled_size: Decimal,
    max_total_size: Decimal | None,
    max_position_size: Decimal | None,
    sleeve_remaining: Decimal | None,
    portfolio_headroom: Decimal | None,
) -> tuple[str | None, str | None]:
    """(reason, cap) for a scaling candidate, or ``(None, None)`` when it is accepted.

    The ORDER is behaviour: the reason it returns is written into the rejected layer's
    ledger entry, so which cap "wins" when several bind at once is observable. A
    degenerate candidate is caught first (a percent basis can quantize to 0 — that adds
    nothing and must never become a phantom 0-size layer), then the per-strategy total
    in size units, then the configured position-size limit, then the allocation sleeve's
    remaining capacity, and last the composition-wide money cap. ``None`` for a bound
    means it is not configured for this run, not that it is unlimited-by-default.

    An over-cap layer is REJECTED, never auto-trimmed to fit (§11.4 exposure binding)."""
    if layer_size <= _ZERO:
        return "layer_size_not_positive", None
    if max_total_size is not None and scaled_size > max_total_size:
        return "max_total_exposure", str(max_total_size)
    if max_position_size is not None and scaled_size > max_position_size:
        return "position_size_limit", str(max_position_size)
    if sleeve_remaining is not None and layer_notional > sleeve_remaining:
        return "sleeve_capacity", str(max(sleeve_remaining, _ZERO).quantize(Decimal("0.01")))
    if portfolio_headroom is not None and layer_notional > portfolio_headroom:
        return "portfolio_max_total_exposure", str(
            max(portfolio_headroom, _ZERO).quantize(Decimal("0.01"))
        )
    return None, None
