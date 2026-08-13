"""Fixture construction for the independent financial oracles (ADIM 12).

This module builds INPUTS only — bars, a strategy config, a signal plan, a run. It
computes no expected value, so nothing a test asserts can be traced back to here.

The shared geometry
-------------------
Every fixture opens with ``FLAT_BARS`` (20) bars at ``FLAT_PRICE`` (100). The entry signal
is a ``ta.sma`` cross with ``length=20``: after 20 identical bars the moving average sits
exactly at 100, so bar 21 crosses it in whichever direction that bar closes. That makes the
signal bar KNOWN (bar 21, 1-based ``bar_seq``) without reading the indicator implementation
— the arithmetic of a 20-bar mean over 20 copies of the same number is not in question.

``validity="current_candle_only"`` keeps the signal an EDGE: it is live on the cross bar
only, so a later bar cannot silently re-fire an entry mid-fixture and change the ledger a
test hand-computed.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import EngineOutput, run_engine
from entropia.domain.backtest.funding import FundingSchedule
from entropia.domain.backtest.indicators import IndicatorPlan, IndicatorSpec, SignalRule
from entropia.domain.strategy.config import StrategyConfig

FLAT_BARS = 20
FLAT_PRICE = "100"
#: 1-based ``bar_seq`` of the bar the SMA cross fires on (the first bar after the flat run).
SIGNAL_BAR_SEQ = FLAT_BARS + 1
INITIAL_CAPITAL = Decimal("10000.00")


def bar(
    day: int, open_: str, high: str, low: str, close: str, volume: str = "10"
) -> dict[str, Any]:
    """One OHLCV row, dated ``2024-01-<day>`` at midnight UTC (one bar per day)."""
    return {
        "timestamp": f"2024-01-{day:02d}T00:00:00Z",
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def bar_time(day: int) -> str:
    """The ISO timestamp of the bar on ``day`` — what a trade row echoes back."""
    return f"2024-01-{day:02d}T00:00:00Z"


def flat_run(price: str = FLAT_PRICE, count: int = FLAT_BARS) -> list[dict[str, Any]]:
    """The look-back: ``count`` identical bars, so the 20-bar SMA rests exactly at ``price``."""
    return [bar(i + 1, price, price, price, price) for i in range(count)]


def batched(bars: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(bars), size):
        yield bars[start : start + size]


def entry_plan(
    *, direction: str = "long_and_short", validity: str = "current_candle_only"
) -> IndicatorPlan:
    """The 20-bar SMA cross that fires the entry on ``SIGNAL_BAR_SEQ``."""
    spec = IndicatorSpec(
        block_id="blk_1",
        canonical_key="ta.sma",
        length=FLAT_BARS,
        direction=direction,
        requirement="required",
        validity=validity,
    )
    return IndicatorPlan(
        entry_rule=SignalRule(rule="required_indicator_blocks_only"), entry_specs=(spec,)
    )


def entry_and_exit_plan(*, direction: str = "long_and_short") -> IndicatorPlan:
    """One close-confirmed SMA cross driving BOTH the entry and the exit rule."""
    spec = IndicatorSpec(
        block_id="blk_1",
        canonical_key="ta.sma",
        length=FLAT_BARS,
        direction=direction,
        requirement="required",
        validity="current_candle_only",
    )
    rule = SignalRule(rule="required_indicator_blocks_only")
    return IndicatorPlan(entry_rule=rule, entry_specs=(spec,), exit_rule=rule, exit_specs=(spec,))


def oracle_config(
    *,
    direction: str = "long_and_short",
    initial_capital: str = "10000.00",
    entry_timing: str = "current_candle_close",
    exit_timing: str = "current_candle_close",
    order_config: dict[str, Any] | None = None,
    costs: dict[str, Any] | None = None,
    protection: dict[str, Any] | None = None,
    sizing: dict[str, Any] | None = None,
    scaling: dict[str, Any] | None = None,
    restrictions: dict[str, Any] | None = None,
    conflict: dict[str, Any] | None = None,
    exit_logic: dict[str, Any] | None = None,
    tick_policy: str = "inherit",
) -> StrategyConfig:
    """A minimal VALID strategy config whose every priced knob is passed in explicitly.

    Defaults are the ZERO-COST baseline: no spread, no slippage, no commission, a 50-unit
    fixed size and a 1% percentage stop. A test that cares about a cost switches exactly
    that cost on, so the delta it asserts is attributable to one knob.
    """
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_oracle",
            "display_name": "Financial Oracle Fixture",
            "rationale_family_id": "rf_oracle",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {
                    "start": "2024-01-01T00:00:00Z",
                    "end": "2024-12-31T23:59:59Z",
                },
                "initial_capital": initial_capital,
                "execution": {"entry_timing": entry_timing, "exit_timing": exit_timing},
                "order_config": order_config or {"type": "market_order"},
                "costs": costs or {"slippage_mode": "percentage_slippage", "slippage_value": "0"},
                "intrabar_policy": {"tick_policy": tick_policy},
                "funding": {"enabled": False},
            },
            "position_entry_logic": {
                "direction_mode": direction,
                "signal_block": {"rule": "required_indicator_blocks_only"},
                "indicator_blocks": [
                    {
                        "block_id": "blk_1",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_1",
                            "package_revision_id": "pkgrev_1",
                            "package_content_hash": "pkghash_1",
                        },
                        "trigger_source": "indicator_native_trigger",
                        "requirement": "required",
                    }
                ],
            },
            "position_exit_logic": exit_logic
            or {"applies_to_direction": "long_and_short", "close_percentage": "100"},
            "protection_stop_logic": (
                {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}}
                if protection is None
                else protection
            ),
            # GH #550: ``base_position_size`` and the min/max limits are PERCENTAGES of
            # resolved capital, not unit counts. This default used to read
            # ``base_position_size: "50"`` and mean 50 units at any price.
            #
            # It is now stated as RISK-BASED sizing, which is the one modelled method that
            # is price-INDEPENDENT: ``equity * risk% / stop_distance`` = 10 000 * 1% / 2.00
            # = exactly 50 units, whatever the bar prices are. The percent reading cannot
            # do that. Percent sizing divides by the EFFECTIVE fill price, so under a
            # spread or a slippage the size itself moves — and these fixtures are about
            # fills, costs, stops, scaling and restrictions, with the 50-unit position as
            # their INPUT rather than their subject. Sizing a cost oracle off the very
            # price the cost perturbs would destroy the one-knob-one-delta property the
            # module docstring rests on: the pnl delta would mix the cost with a size
            # change. ``test_oracle_sizing.py`` covers the percent path head-on.
            #
            # ``stop_loss_point`` here is a SIZING input only — nothing installs a stop
            # from it (the protection stop is the separate ``protection_stop_logic``
            # argument above), so this does not smuggle an exit into any fixture.
            #
            # Still equity-dependent, exactly as the percent reading is: a fixture that
            # opens a SECOND position after booking PnL sizes off the new equity. Those
            # numbers moved on purpose and were recomputed, not patched.
            "position_sizing": sizing
            or {
                "method": "risk_based_sizing",
                "risk_based": {"risk_percentage_per_trade": "1", "stop_loss_point": "2.00"},
            },
            **({"scaling_logic": scaling} if scaling is not None else {}),
            "restrictions_filters": restrictions or {"rule": "any", "filters": []},
            "conflict_position_handling": conflict or {},
        }
    )


def run_oracle(
    config: StrategyConfig,
    bars: list[dict[str, Any]],
    *,
    batch: int = 8,
    plan: IndicatorPlan | None = None,
    funding: FundingSchedule | None = None,
    timeframe: str | None = None,
    tick_batches: Iterator[list[dict[str, Any]]] | None = None,
) -> EngineOutput:
    return run_engine(
        strategy_config=config,
        bar_batches=batched(bars, batch),
        execution_key="oracle_exec_key",
        indicator_plan=plan or entry_plan(),
        funding=funding,
        timeframe=timeframe,
        tick_batches=tick_batches,
    )
