"""The shared production-reachable entry plan for the engine unit fixtures (F-24).

Why this exists
---------------
``run_engine`` has two entry-signal sources: a real ``IndicatorPlan`` (built-in TA native
triggers) and, when no plan resolves, a labelled breakout PROXY. F-06 made the proxy
unreachable in production — an unresolved indicator plan is a Ready Check blocker and the
worker fails closed before the engine is ever called — so a unit fixture that omits the
plan exercises a path a real RUN can never take.

F-24 requires that the suite not act as a regression lock for behaviour the product has
ruled out. Every engine unit fixture therefore drives its entries through this plan: a
real ``ta.sma`` price/MA cross, exactly as a production RUN does.

Why these parameters
--------------------
``length=20`` matches the proxy's own look-back (``engine._BREAKOUT_WINDOW``). The engine
fixtures share one geometry — N flat bars, then a breakout/breakdown bar — so a 20-bar MA
sits at the flat price and the breakout bar crosses it on the SAME bar the proxy fired on.
That is what lets the fixtures keep their expected fill prices, trade counts and PnL: the
signal SOURCE changes, the bar the signal lands on does not. A short MA (e.g. 3) tracks the
follow-up bars closely enough to whipsaw spurious opposite crosses mid-fixture.

``validity="current_candle_only"`` keeps the signal an EDGE — live only on the cross bar,
like the proxy. A held (``until_opposite_signal``) signal stays active on every later bar
and would re-fire entries while follow-up bars are still resolving an order or a stop.
"""

from __future__ import annotations

from entropia.domain.backtest.indicators import IndicatorPlan, IndicatorSpec, SignalRule

# Matches engine._BREAKOUT_WINDOW: the MA rests at the flat price, so the breakout bar
# crosses it on the same bar the retired proxy signalled on.
PLAN_MA_LENGTH = 20


def sma_entry_plan(
    *,
    block_id: str = "blk_1",
    direction: str = "long_and_short",
    length: int = PLAN_MA_LENGTH,
    validity: str = "current_candle_only",
) -> IndicatorPlan:
    """A resolvable single-block ``ta.sma`` cross plan — the fixtures' entry signal.

    ``direction`` mirrors the block-level direction filter (the strategy config carries its
    own ``direction_mode``; both must allow a side for it to fire)."""
    return IndicatorPlan(
        entry_rule=SignalRule(rule="required_indicator_blocks_only"),
        entry_specs=(
            IndicatorSpec(
                block_id=block_id,
                canonical_key="ta.sma",
                length=length,
                direction=direction,
                requirement="required",
                validity=validity,
            ),
        ),
    )
