"""GAP-02 — allocation engine execution unit tests (doc 13 §8.3, §8.4).

DB-free. Covers the resolved shared-pool capital model and its application in the
bar-replay engine: R0/A0/Ci sleeve distribution (AT#10-#13), compound vs fixed
sleeve recompute across valuation points, the ``allowed_size`` outer cap, the P0
capital-basis override, the item-not-in-plan and single-currency L4 boundaries,
and the byte-identical independent-mode regression (``allocation=None``).
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    AllocationExecution,
    EngineOutput,
    resolve_allocation_execution,
    run_engine,
)
from entropia.domain.strategy.config import StrategyConfig

# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


def _config(
    *,
    direction: str = "long",
    base_size: str = "1000000",  # huge, so the sleeve cap always binds
    with_stop: bool = False,
    initial_capital: str = "10000.00",
) -> StrategyConfig:
    """A minimal VALID StrategyConfig with ZERO costs (so pnl = (exit-entry)*size)."""
    protection: dict[str, Any] = (
        {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}} if with_stop else {}
    )
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Allocation Fixture",
            "rationale_family_id": "rf_1",
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
            "position_exit_logic": {
                "applies_to_direction": "long_and_short",
                "close_percentage": "100",
            },
            "protection_stop_logic": protection,
            "position_sizing": {"method": "base_position_size", "base_position_size": base_size},
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


def _bar(ts: str, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c, "volume": "10"}


def _flat(n: int, price: str = "90") -> list[dict[str, Any]]:
    return [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", price, price, price, price) for i in range(n)]


def _one_trade_bars() -> list[dict[str, Any]]:
    """20 flat @90 (window) → long breakout entry @100 → end-of-data exit @110."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "90", "100", "90", "100"))  # breakout -> long @100
    bars.append(_bar("2024-01-22T00:00:00Z", "100", "110", "100", "110"))  # ride -> EOD exit @110
    return bars


def _two_trade_bars() -> list[dict[str, Any]]:
    """A LOSING first trade (equity drops), then a winning re-entry — so a compound
    sleeve recompute shrinks the second sleeve vs a fixed sleeve."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "90", "100", "90", "100"))  # breakout -> long @100
    bars.append(_bar("2024-01-22T00:00:00Z", "100", "100", "80", "80"))  # close<win-min -> exit @80
    bars.append(_bar("2024-01-23T00:00:00Z", "80", "105", "80", "105"))  # breakout -> long @105
    bars.append(_bar("2024-01-24T00:00:00Z", "105", "115", "105", "115"))  # ride -> EOD exit @115
    return bars


def _batched(bars: list[dict[str, Any]], size: int = 8) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(bars), size):
        yield bars[start : start + size]


def _run(
    config: StrategyConfig,
    bars: list[dict[str, Any]],
    *,
    allocation: AllocationExecution | None = None,
) -> EngineOutput:
    return run_engine(
        strategy_config=config,
        bar_batches=_batched(bars),
        execution_key="exec_key_test",
        allocation=allocation,
    )


def _capexec(
    *,
    enabled: bool = True,
    amount: str = "10000.00",
    currency: str = "USDT",
    reserve: str = "0",
    mode: str = "COMPOUND_PORTFOLIO_EQUITY",
    item_id: str = "mbi_1",
    share: str | None = "100",
    active: bool = True,
) -> dict[str, Any]:
    """A manifest ``capital_execution`` snapshot (canonical_config shape, doc 13 §8.2)."""
    entries: list[dict[str, Any]] = []
    if share is not None:
        entries.append(
            {
                "composition_item_id": item_id,
                "item_type": "strategy",
                "active": active,
                "equity_share_percent": share,
            }
        )
    return {
        "enabled": enabled,
        "plan_id": "parp_1",
        "plan_revision_id": "parev_1",
        "config_hash": "hash",
        "config": {
            "enabled": enabled,
            "initial_capital": {"amount": amount, "currency": currency},
            "compounding_mode": mode,
            "reserve_cash_percent": reserve,
            "entries": entries,
        }
        if enabled
        else None,
    }


def _alloc(item_id: str = "mbi_1", **kw: Any) -> AllocationExecution | None:
    return resolve_allocation_execution(_capexec(item_id=item_id, **kw), item_id=item_id)


# --------------------------------------------------------------------------- #
# resolve_allocation_execution — projection of the manifest snapshot           #
# --------------------------------------------------------------------------- #


def test_resolve_returns_none_for_absent_or_disabled_allocation() -> None:
    assert resolve_allocation_execution(None, item_id="mbi_1") is None
    assert resolve_allocation_execution({"enabled": False}, item_id="mbi_1") is None
    # enabled with no config dict (independent snapshot) → None (engine unchanged).
    assert resolve_allocation_execution({"enabled": True, "config": None}, item_id="mbi_1") is None


def test_resolve_projects_pool_reserve_mode_and_item_share() -> None:
    alloc = _alloc(amount="10000.00", reserve="10", mode="COMPOUND_PORTFOLIO_EQUITY", share="40")
    assert alloc is not None
    assert alloc.initial_capital == Decimal("10000.00")
    assert alloc.reserve_percent == Decimal("10")
    assert alloc.compound is True
    assert alloc.item_share_percent == Decimal("40")
    assert alloc.currency == "USDT"


def test_resolve_fixed_mode_is_not_compound() -> None:
    alloc = _alloc(mode="FIXED_INITIAL_PORTFOLIO_CAPITAL")
    assert alloc is not None and alloc.compound is False


def test_resolve_item_share_is_zero_when_item_absent_from_plan() -> None:
    # The replayed item is not among the active entries → 0 sleeve (never the
    # strategy's own capital).
    alloc = resolve_allocation_execution(_capexec(item_id="mbi_other"), item_id="mbi_1")
    assert alloc is not None and alloc.item_share_percent == Decimal("0")


def test_resolve_item_share_is_zero_when_entry_inactive() -> None:
    alloc = _alloc(active=False)
    assert alloc is not None and alloc.item_share_percent == Decimal("0")


def test_resolve_negative_reserve_is_floored_to_zero() -> None:
    # A negative reserve could otherwise inflate the allocatable pool above P0.
    alloc = _alloc(reserve="-5")
    assert alloc is not None and alloc.reserve_percent == Decimal("0")


def test_resolve_fails_closed_on_non_positive_or_unparseable_pool() -> None:
    for amount in ("0", "-100", "nan", "not-a-number"):
        assert resolve_allocation_execution(_capexec(amount=amount), item_id="mbi_1") is None


# --------------------------------------------------------------------------- #
# Sleeve distribution — R0/A0/Ci formulas (AT#10-#13, doc 13 §8.3)             #
# --------------------------------------------------------------------------- #


def test_sleeve_cap_binds_the_booked_size_to_ci0() -> None:
    # P0=10000, reserve=0, share=40 → A0=10000, Ci0=4000; entry @100 → size=40;
    # pnl = (110-100)*40 = 400. The huge base size is capped down to the sleeve.
    out = _run(_config(), _one_trade_bars(), allocation=_alloc(reserve="0", share="40"))
    assert out.summary["total_trades"] == 1
    assert out.trades[0].pnl == Decimal("400.00")
    assert out.diagnostics["allocation_items_executed"] == 1
    assert out.diagnostics["allocation_sleeve_cap_active"] is True


def test_sleeve_scales_linearly_with_the_equity_share() -> None:
    # Doubling wi (40 → 80) exactly doubles the sleeve, hence the booked size/pnl.
    forty = _run(_config(), _one_trade_bars(), allocation=_alloc(share="40"))
    eighty = _run(_config(), _one_trade_bars(), allocation=_alloc(share="80"))
    assert forty.trades[0].pnl == Decimal("400.00")  # A0=10000 * 40% / 100 = 4000 → size 40
    assert eighty.trades[0].pnl == Decimal("800.00")  # 8000 → size 80


def test_reserve_reduces_the_allocatable_pool() -> None:
    # reserve=50 halves A0 (10000 → 5000), so share=80 gives the same sleeve (4000)
    # as share=40 with no reserve — R0 is held back before the sleeve split.
    reserved = _run(_config(), _one_trade_bars(), allocation=_alloc(reserve="50", share="80"))
    assert reserved.trades[0].pnl == Decimal("400.00")  # A0=5000 * 80% = 4000 → size 40


# --------------------------------------------------------------------------- #
# Compound vs fixed sleeve recompute across valuation points (doc 13 §8.3)     #
# --------------------------------------------------------------------------- #


def test_compound_sleeve_shrinks_after_a_losing_trade_but_fixed_holds() -> None:
    # First trade loses (equity drops); the second entry's sleeve recomputes from live
    # portfolio equity in compound mode (smaller) but stays at A0 in fixed mode.
    compound = _run(
        _config(), _two_trade_bars(), allocation=_alloc(mode="COMPOUND_PORTFOLIO_EQUITY")
    )
    fixed = _run(
        _config(), _two_trade_bars(), allocation=_alloc(mode="FIXED_INITIAL_PORTFOLIO_CAPITAL")
    )
    assert compound.summary["total_trades"] == fixed.summary["total_trades"] == 2
    # The losing first trade is identical (same starting sleeve).
    assert compound.trades[0].pnl == fixed.trades[0].pnl < Decimal("0")
    # The second trade is a win; the compound sleeve shrank → strictly smaller win.
    assert Decimal("0") < compound.trades[1].pnl < fixed.trades[1].pnl
    assert compound.diagnostics["allocation_compounding"] == "compound"
    assert fixed.diagnostics["allocation_compounding"] == "fixed"


# --------------------------------------------------------------------------- #
# Capital-basis override + boundaries                                          #
# --------------------------------------------------------------------------- #


def test_allocation_overrides_initial_capital_with_the_portfolio_pool() -> None:
    out = _run(
        _config(initial_capital="10000.00"), _one_trade_bars(), allocation=_alloc(amount="50000.00")
    )
    # The run is capitalised from P0 (50000), NOT the strategy's own 10000.
    assert out.summary["initial_capital"] == Decimal("50000.00")


def test_item_not_in_active_plan_yields_no_trades_and_an_l4_warning() -> None:
    # Allocation enabled but the replayed item has 0 share → 0 sleeve → no fills.
    alloc = resolve_allocation_execution(_capexec(item_id="mbi_other"), item_id="mbi_1")
    out = _run(_config(), _one_trade_bars(), allocation=alloc)
    assert out.summary["total_trades"] == 0
    assert "allocation_item_not_in_active_plan" in out.diagnostics["warnings"]
    assert out.diagnostics["allocation_items_executed"] == 0
    assert out.diagnostics["allocation_sleeve_cap_active"] is False


def test_enabled_allocation_surfaces_the_single_currency_l4_warning() -> None:
    out = _run(_config(), _one_trade_bars(), allocation=_alloc())
    assert "allocation_single_currency_pool_assumed" in out.diagnostics["warnings"]
    assert out.diagnostics["allocation_enabled"] is True


# --------------------------------------------------------------------------- #
# Independent-mode regression (allocation=None) — byte-identical               #
# --------------------------------------------------------------------------- #


def test_independent_mode_is_byte_identical_to_the_pre_allocation_engine() -> None:
    # No allocation: the run uses the strategy's own initial_capital and the full base
    # size — no sleeve cap, no allocation diagnostics/ warnings.
    out = _run(_config(base_size="50"), _one_trade_bars(), allocation=None)
    assert out.summary["initial_capital"] == Decimal("10000.00")  # the strategy's own
    assert out.diagnostics["allocation_enabled"] is False
    assert out.diagnostics["allocation_compounding"] is None
    assert out.diagnostics["allocation_items_executed"] == 0
    assert not any(w.startswith("allocation_") for w in out.diagnostics["warnings"])
    # base size 50 is honored verbatim (not capped): pnl = (110-100)*50 = 500.
    assert out.trades[0].pnl == Decimal("500.00")
