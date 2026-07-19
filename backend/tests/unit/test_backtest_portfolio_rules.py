"""Portfolio-level rules engine unit tests (cross-item, doc 13 §8.4).

DB-free. Covers the manifest-snapshot resolver (``resolve_portfolio_rules``), the
closed-position window pipeline (``position_intervals`` -> ``build_prior_intervals``),
and the engine gates: the opposing same-instrument conflict block (BLOCK_OPPOSITE,
NET's conservative downgrade, unknown-symbol fail-closed) and the composition-wide
Max Total Exposure cap (prior-exposure headroom clamp, zero-headroom block, the
solo-item breach, the unreadable-cap ZERO fail-close) — plus the L4 provenance
(warnings + diagnostics counters) and the rules-off byte-identical regression.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    AllocationExecution,
    EngineOutput,
    PortfolioRules,
    PriorItemInterval,
    _epoch_ms_or_none,
    build_prior_intervals,
    resolve_portfolio_rules,
    run_engine,
)
from entropia.domain.strategy.config import StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan

# --------------------------------------------------------------------------- #
# Fixtures (the allocation-suite geometry: 20 flat @90 -> breakout @100 ->     #
# EOD exit @110; zero costs so pnl = (exit-entry)*size)                        #
# --------------------------------------------------------------------------- #


def _config(*, direction: str = "long", base_size: str = "1000000") -> StrategyConfig:
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Portfolio Rules Fixture",
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
            "protection_stop_logic": {},
            "position_sizing": {"method": "base_position_size", "base_position_size": base_size},
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


def _bar(ts: str, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c, "volume": "10"}


def _one_trade_bars() -> list[dict[str, Any]]:
    bars = [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", "90", "90", "90", "90") for i in range(20)]
    bars.append(_bar("2024-01-21T00:00:00Z", "90", "100", "90", "100"))  # cross -> long @100
    bars.append(_bar("2024-01-22T00:00:00Z", "100", "110", "100", "110"))  # ride -> EOD exit @110
    return bars


def _batched(bars: list[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(bars), 8):
        yield bars[start : start + 8]


_ALLOC = AllocationExecution(
    initial_capital=Decimal("10000.00"),
    reserve_percent=Decimal("0"),
    compound=False,
    item_share_percent=Decimal("100"),
    currency="USDT",
)


def _ms(ts: str) -> int:
    parsed = _epoch_ms_or_none(ts)
    assert parsed is not None
    return parsed


def _iv(
    *,
    direction: str = "short",
    symbol: str | None = "BTCUSDT",
    start: str | None = "2024-01-01T00:00:00Z",
    end: str | None = "2024-12-31T00:00:00Z",
    notional: str = "9000",
) -> PriorItemInterval:
    return PriorItemInterval(
        item_id="mbi_prior",
        symbol=symbol,
        direction=direction,
        start_ms=_ms(start) if start is not None else None,
        end_ms=_ms(end) if end is not None else None,
        notional=Decimal(notional),
    )


def _rules(
    *,
    pct: str | None = None,
    policy: str | None = None,
    symbol: str | None = "BTCUSDT",
    priors: tuple[PriorItemInterval, ...] = (),
    invalid: bool = False,
) -> PortfolioRules:
    return PortfolioRules(
        max_total_exposure_percent=Decimal(pct) if pct is not None else None,
        conflict_policy=policy,
        own_symbol=symbol,
        prior_intervals=priors,
        exposure_percent_invalid=invalid,
    )


def _run(
    config: StrategyConfig,
    *,
    rules: PortfolioRules | None,
    allocation: AllocationExecution | None = _ALLOC,
) -> EngineOutput:
    return run_engine(
        strategy_config=config,
        bar_batches=_batched(_one_trade_bars()),
        execution_key="exec_key_test",
        allocation=allocation,
        indicator_plan=sma_entry_plan(),
        portfolio_rules=rules,
    )


def _blocked_reasons(out: EngineOutput) -> list[str]:
    return [
        str(e.detail.get("reason")) for e in out.signal_events if e.event_type == "entry_blocked"
    ]


# --------------------------------------------------------------------------- #
# resolve_portfolio_rules — projection of the manifest snapshot               #
# --------------------------------------------------------------------------- #


def _capexec(config: dict[str, Any] | None, *, enabled: bool = True) -> dict[str, Any]:
    return {"enabled": enabled, "config": config}


def test_resolver_returns_none_for_absent_disabled_or_ruleless_snapshots() -> None:
    assert resolve_portfolio_rules(None) is None
    assert resolve_portfolio_rules(_capexec({"enabled": True}, enabled=False)) is None
    # Enabled shared allocation with NO portfolio-level rule set -> None (the
    # byte-identical pre-rules path).
    assert resolve_portfolio_rules(_capexec({"enabled": True})) is None
    # An explicit KEEP_SEPARATE with no cap IS the pre-rules behaviour.
    assert resolve_portfolio_rules(_capexec({"conflict_policy": "KEEP_SEPARATE"})) is None


def test_resolver_parses_cap_percent_and_normalizes_the_policy_token() -> None:
    rules = resolve_portfolio_rules(
        _capexec({"max_total_exposure_percent": "150", "conflict_policy": "net"})
    )
    assert rules is not None
    assert rules.max_total_exposure_percent == Decimal("150")
    assert rules.conflict_policy == "NET"
    assert rules.exposure_percent_invalid is False
    assert rules.prior_intervals == ()


def test_resolver_flags_an_unreadable_or_nonpositive_cap_as_invalid() -> None:
    # Fail closed: a SET-but-unreadable cap must NOT dissolve into "no cap".
    for bad in ("abc", "-5", "0", "NaN"):
        rules = resolve_portfolio_rules(_capexec({"max_total_exposure_percent": bad}))
        assert rules is not None, bad
        assert rules.max_total_exposure_percent is None
        assert rules.exposure_percent_invalid is True


# --------------------------------------------------------------------------- #
# position_intervals -> build_prior_intervals                                  #
# --------------------------------------------------------------------------- #


def test_closed_position_window_is_recorded_and_converts_to_a_prior_interval() -> None:
    out = _run(_config(), rules=None)
    assert len(out.trades) == 1
    assert len(out.position_intervals) == 1
    window = out.position_intervals[0]
    assert window["entry_time"] == out.trades[0].entry_time
    assert window["exit_time"] == out.trades[0].exit_time
    assert window["direction"] == "long"
    # Sleeve-capped entry: 10000 / 100 = 100 units @ eff 100 -> peak notional 10000.
    assert window["peak_notional"] == Decimal("10000.00")

    intervals = build_prior_intervals(
        item_id="mbi_1", symbol="BTCUSDT", position_intervals=out.position_intervals
    )
    assert len(intervals) == 1
    assert intervals[0].symbol == "BTCUSDT"
    assert intervals[0].direction == "long"
    assert intervals[0].start_ms == _ms("2024-01-21T00:00:00Z")
    assert intervals[0].end_ms == _ms("2024-01-22T00:00:00Z")
    assert intervals[0].notional == Decimal("10000.00")


def test_build_prior_intervals_fails_closed_on_bad_bounds_and_drops_zero_notional() -> None:
    intervals = build_prior_intervals(
        item_id="mbi_1",
        symbol=None,
        position_intervals=[
            {
                "entry_time": "not-a-time",
                "exit_time": None,
                "direction": "short",
                "peak_notional": Decimal("50"),
            },
            {  # constrains nothing -> dropped, never a fabricated figure
                "entry_time": "2024-01-01T00:00:00Z",
                "exit_time": "2024-01-02T00:00:00Z",
                "direction": "long",
                "peak_notional": Decimal("0"),
            },
        ],
    )
    assert len(intervals) == 1
    # Unparseable bounds -> unbounded on BOTH sides (over-covers, never under-covers).
    assert intervals[0].start_ms is None
    assert intervals[0].end_ms is None
    assert intervals[0].notional == Decimal("50")


# --------------------------------------------------------------------------- #
# Conflict gate (BLOCK_OPPOSITE / NET downgrade / fail-closed identity)        #
# --------------------------------------------------------------------------- #


def test_block_opposite_blocks_the_overlapping_opposite_same_instrument_entry() -> None:
    out = _run(
        _config(),
        rules=_rules(policy="BLOCK_OPPOSITE", priors=(_iv(direction="short"),)),
    )
    assert out.trades == []
    assert out.diagnostics["portfolio_conflict_blocked_entries"] == 1
    assert "portfolio_conflict_blocked" in _blocked_reasons(out)
    assert out.diagnostics["portfolio_conflict_policy_executed"] == "block_opposite"
    assert "portfolio_rules_sequential_pin_order_precedence" in out.diagnostics["warnings"]


def test_conflict_gate_ignores_non_overlapping_windows_and_other_instruments() -> None:
    ended_early = _run(
        _config(),
        rules=_rules(
            policy="BLOCK_OPPOSITE",
            priors=(_iv(direction="short", end="2024-01-10T00:00:00Z"),),
        ),
    )
    assert len(ended_early.trades) == 1

    other_symbol = _run(
        _config(),
        rules=_rules(policy="BLOCK_OPPOSITE", priors=(_iv(direction="short", symbol="ETHUSDT"),)),
    )
    assert len(other_symbol.trades) == 1
    assert other_symbol.diagnostics["portfolio_conflict_blocked_entries"] == 0


def test_conflict_gate_never_blocks_the_same_direction() -> None:
    out = _run(
        _config(),
        rules=_rules(policy="BLOCK_OPPOSITE", priors=(_iv(direction="long"),)),
    )
    assert len(out.trades) == 1
    assert out.diagnostics["portfolio_conflict_blocked_entries"] == 0


def test_net_policy_executes_as_block_opposite_and_discloses_the_downgrade() -> None:
    out = _run(_config(), rules=_rules(policy="NET", priors=(_iv(direction="short"),)))
    assert out.trades == []
    assert out.diagnostics["portfolio_conflict_policy"] == "NET"
    assert out.diagnostics["portfolio_conflict_policy_executed"] == "block_opposite"
    assert "conflict_policy_net_executed_as_block_opposite" in out.diagnostics["warnings"]


def test_unknown_instrument_identity_fails_closed_as_a_conflict() -> None:
    # The prior window's symbol is unknown -> a same-instrument conflict cannot be
    # RULED OUT; the entry is blocked and the fail-close is surfaced (L4).
    out = _run(
        _config(),
        rules=_rules(policy="BLOCK_OPPOSITE", priors=(_iv(direction="short", symbol=None),)),
    )
    assert out.trades == []
    assert out.diagnostics["portfolio_conflict_blocked_entries"] == 1
    assert "portfolio_conflict_symbol_unknown_fail_closed" in out.diagnostics["warnings"]


# --------------------------------------------------------------------------- #
# Max Total Exposure cap                                                       #
# --------------------------------------------------------------------------- #


def test_exposure_cap_clamps_the_entry_to_the_prior_exposure_headroom() -> None:
    # Cap = 100% of P0 = 10000; a concurrent prior window holds 9000 -> headroom
    # 1000 -> 10 units @100. PnL = (110-100)*10 = 100.
    out = _run(
        _config(),
        rules=_rules(pct="100", priors=(_iv(direction="long", notional="9000"),)),
    )
    assert len(out.trades) == 1
    assert out.summary["net_profit"] == Decimal("100.00")
    assert out.diagnostics["portfolio_exposure_clamped_entries"] == 1
    assert out.diagnostics["portfolio_max_total_exposure_cap"] == "10000.00"


def test_exposure_cap_blocks_the_entry_when_no_headroom_remains() -> None:
    out = _run(
        _config(),
        rules=_rules(pct="100", priors=(_iv(direction="long", notional="10000"),)),
    )
    assert out.trades == []
    assert out.diagnostics["portfolio_exposure_blocked_entries"] == 1
    assert "portfolio_max_total_exposure" in _blocked_reasons(out)


def test_exposure_cap_binds_a_single_item_with_no_priors() -> None:
    # A lone item can breach the composition ceiling by itself: cap 50% of P0 =
    # 5000 -> 50 units @100 (the sleeve alone would deploy 100). PnL = 500.
    out = _run(_config(), rules=_rules(pct="50"))
    assert len(out.trades) == 1
    assert out.summary["net_profit"] == Decimal("500.00")
    assert out.diagnostics["portfolio_exposure_clamped_entries"] == 1


def test_an_unreadable_cap_fails_closed_to_a_zero_cap() -> None:
    out = _run(_config(), rules=_rules(invalid=True))
    assert out.trades == []
    assert out.diagnostics["portfolio_exposure_blocked_entries"] == 1
    assert "portfolio_max_exposure_unparseable_zero_cap" in out.diagnostics["warnings"]
    assert out.diagnostics["portfolio_max_total_exposure_cap"] == "0.00"


# --------------------------------------------------------------------------- #
# Rules-off regression + provenance                                            #
# --------------------------------------------------------------------------- #


def test_rules_off_is_byte_identical_and_carries_no_portfolio_warnings() -> None:
    plain = _run(_config(), rules=None)
    assert plain.diagnostics["portfolio_rules_active"] is False
    assert plain.diagnostics["portfolio_conflict_blocked_entries"] == 0
    assert plain.diagnostics["portfolio_exposure_blocked_entries"] == 0
    assert plain.diagnostics["portfolio_exposure_clamped_entries"] == 0
    assert not any(w.startswith("portfolio_") for w in plain.diagnostics["warnings"])
    assert len(plain.trades) == 1
    assert plain.summary["net_profit"] == Decimal("1000.00")  # 100 units * 10
