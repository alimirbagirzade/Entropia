"""K-11b — the engine's output assembly, tested as its own unit.

``run_engine`` used to end with 389 inline lines that turned the finished ledger into
a summary, an L4 warning list and the diagnostics block. Reaching any one of those
branches meant replaying a strategy that actually hit it. Extracted into
``execution.output`` the whole tail is a pure projection of ``(ctx, led)``, so each
rule can be exercised directly.

What is tested here is deliberately NOT "the numbers add up" — the golden digest guard
already pins every emitted figure byte-for-byte across 46 scenarios. These cover the
rules that a byte-equality proof cannot express, because they are about what the engine
must REFUSE to report:

* a ratio with no denominator is ``None``, never a fabricated ``0.0`` that would read
  as a real measurement of a bad strategy instead of an absent one;
* every fail-closed capability gate names itself in the warning list, because that
  warning is the only record in the Result of why the run opened no position;
* the saved policy and the EXECUTED policy are reported as separate keys, so NET's
  conservative downgrade to block_opposite stays visible rather than being reported
  as honored.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.execution.costs import FillCosts
from entropia.domain.backtest.execution.output import (
    PORTFOLIO_RULES_SEQUENTIAL_WARNING,
    build_diagnostics,
    build_summary,
    build_warnings,
)
from entropia.domain.backtest.execution.state import (
    EquityPoint,
    TradeRow,
    _Bar,
    _Ledger,
    _RunConfig,
)
from tests.unit.test_backtest_engine import _config

_ZERO = Decimal("0")


def _bar(ts: str, close: str = "100") -> _Bar:
    c = Decimal(close)
    return _Bar(timestamp=ts, open=c, high=c, low=c, close=c, volume=Decimal("1"))


def _ctx(**over: object) -> _RunConfig:
    """A minimal resolved run. Every capability gate defaults to modelled, so a test
    that flips ONE gate is unambiguous about which warning it is asserting."""
    cfg = _config()
    base: dict[str, object] = {
        "config": cfg,
        "fill_costs": FillCosts(_ZERO, _ZERO, _ZERO),
        # The saved sub-configs the provenance block reports verbatim. Derived from the
        # same StrategyConfig the prologue reads, so a test never asserts against a
        # shape the engine would not actually hand the assembly.
        "order_cfg": cfg.data.order_config,
        "exit_logic": cfg.position_exit_logic,
        "scaling_cfg": cfg.scaling_logic,
        "restrictions_cfg": cfg.restrictions_filters,
        "conflict_cfg": cfg.conflict_position_handling,
        "partial_aftermath": cfg.position_exit_logic.partial_aftermath,
        "strength_mode": cfg.position_sizing.signal_strength_adjustment,
        "restriction_rule": cfg.restrictions_filters.rule,
        "stacking_policy": str(cfg.conflict_position_handling.same_direction_stacking),
        "hedge_policy": str(cfg.conflict_position_handling.opposite_direction_hedge),
        "overlap_policy": str(cfg.conflict_position_handling.overlapping_signal_policy),
        "alloc_on": False,
        "alloc_compound": False,
        "allocatable_initial": _ZERO,
        "item_share": _ZERO,
        "reserve_nominal": _ZERO,
        "portfolio_rules": None,
        "sizing_ok": True,
        "leverage_ok": True,
        "strength_ok": True,
        "capability_ok": True,
        "initial_capital": Decimal("10000"),
    }
    base.update(over)
    return _RunConfig(**base)  # type: ignore[arg-type]


def _led(**over: object) -> _Ledger:
    led = _Ledger()
    led.equity = Decimal("10000")
    led.peak = Decimal("10000")
    led.bars_seen = 10
    for k, v in over.items():
        setattr(led, k, v)
    return led


def _trade(pnl: str) -> TradeRow:
    return TradeRow(
        seq=1,
        entry_time="2024-01-01T00:00:00Z",
        exit_time="2024-01-02T00:00:00Z",
        direction="long",
        entry_price=Decimal("100"),
        exit_price=Decimal("101"),
        pnl=Decimal(pnl),
        exit_reason="exit_signal",
    )


# --------------------------------------------------------------------------- #
# build_summary — a ratio with no denominator is absent, never 0               #
# --------------------------------------------------------------------------- #
def test_win_rate_is_none_with_no_trades_not_zero() -> None:
    """0.0% would read as "this strategy lost every trade". It took none."""
    assert build_summary(_ctx(), _led())["win_rate"] is None


def test_win_rate_is_a_real_percentage_once_trades_exist() -> None:
    led = _led(trades=[_trade("10"), _trade("-5")], winners=1)
    assert build_summary(_ctx(), led)["win_rate"] == Decimal("50.0000")


def test_profit_factor_is_none_when_nothing_was_lost() -> None:
    """gross_loss 0 makes the ratio undefined, not infinite and not zero."""
    led = _led(trades=[_trade("10")], winners=1, gross_profit=Decimal("10"))
    assert build_summary(_ctx(), led)["profit_factor"] is None


def test_romad_is_none_without_a_drawdown() -> None:
    led = _led(equity=Decimal("11000"))
    assert build_summary(_ctx(), led)["romad"] is None


def test_net_profit_pct_is_none_on_a_zero_capital_run() -> None:
    summary = build_summary(_ctx(initial_capital=_ZERO), _led(equity=_ZERO))
    assert summary["net_profit_pct"] is None


def test_period_reports_the_bars_actually_replayed() -> None:
    """F-05: the ACTUAL first/last replayed bar, never the requested range bounds —
    that is what proves the manifest range matches the data processed."""
    led = _led(first_ts="2024-03-01T00:00:00Z", last_bar=_bar("2024-03-09T00:00:00Z"))
    summary = build_summary(_ctx(), led)
    assert summary["period_start"] == "2024-03-01T00:00:00Z"
    assert summary["period_end"] == "2024-03-09T00:00:00Z"


def test_period_is_none_when_no_bar_was_replayed() -> None:
    summary = build_summary(_ctx(), _led())
    assert summary["period_start"] is None and summary["period_end"] is None


def test_max_drawdown_comes_from_the_equity_curve() -> None:
    led = _led(
        equity_points=[
            EquityPoint(
                seq=1, timestamp="t1", equity=Decimal("10000"), drawdown=_ZERO, exposure=_ZERO
            ),
            EquityPoint(
                seq=2,
                timestamp="t2",
                equity=Decimal("9000"),
                drawdown=Decimal("1000"),
                exposure=_ZERO,
            ),
        ]
    )
    assert build_summary(_ctx(), led)["max_drawdown"] == Decimal("1000.00")


def test_funding_paid_is_surfaced_separately_from_net_profit() -> None:
    """It is already inside final_equity; it is reported on its own so the funding
    contribution stays auditable rather than buried in the net figure."""
    led = _led(equity=Decimal("9980"), funding_paid=Decimal("20"))
    summary = build_summary(_ctx(), led)
    assert summary["funding_paid"] == Decimal("20.00")
    assert summary["net_profit"] == Decimal("-20.00")


# --------------------------------------------------------------------------- #
# build_warnings — every fail-closed gate names itself                         #
# --------------------------------------------------------------------------- #
def test_no_bars_in_source_is_reported() -> None:
    assert "no_bars_in_source" in build_warnings(_ctx(), _led(bars_seen=0))


def test_a_clean_run_reports_no_warnings() -> None:
    assert build_warnings(_ctx(), _led()) == []


def test_each_unsupported_gate_emits_its_own_named_warning() -> None:
    """Ready Check should have blocked the run; reaching here means a stale readiness
    state got past admission, so the Result must say which option made it inert."""
    for field, prefix in (
        ("sizing_ok", "position_sizing_method_unsupported:"),
        ("leverage_ok", "leverage_unsupported:"),
        ("strength_ok", "signal_strength_unsupported:"),
        ("timing_ok", "execution_timing_unsupported:"),
        ("order_ok", "order_type_unsupported:"),
        ("partial_close_ok", "partial_close_unsupported:"),
        ("scaling_ok", "scaling_unsupported:"),
        ("restrictions_ok", "restrictions_unsupported:"),
    ):
        warnings = build_warnings(_ctx(**{field: False}), _led())
        assert any(w.startswith(prefix) for w in warnings), f"{field} -> {prefix}"


def test_restrictions_warning_names_the_prologue_resolved_types() -> None:
    """The set comes from the SAME parse that decided restrictions_ok. A warning
    naming a different set than the gate that opened no position would misreport
    why the run was inert."""
    ctx = _ctx(restrictions_ok=False, unmodelled_restriction_types=("spread", "volume"))
    assert "restrictions_unsupported:spread,volume" in build_warnings(ctx, _led())


def test_conflict_handling_warning_names_the_unmodelled_hedge() -> None:
    warnings = build_warnings(_ctx(conflict_ok=False), _led())
    assert "conflict_handling_unsupported:allow_hedge_without_exit_on_opposite" in warnings


def test_a_rules_active_run_always_discloses_sequential_pin_order() -> None:
    """V1 replays items in pin order and never re-simulates an earlier one. That is
    inherent to EVERY rules-active run, so it is disclosed unconditionally."""
    assert PORTFOLIO_RULES_SEQUENTIAL_WARNING in build_warnings(_ctx(rules_active=True), _led())


def test_net_downgrade_is_disclosed_as_its_own_warning() -> None:
    ctx = _ctx(rules_active=True, conflict_downgraded_from_net=True)
    assert "conflict_policy_net_executed_as_block_opposite" in build_warnings(ctx, _led())


def test_an_unknown_conflict_policy_fails_closed_and_says_so() -> None:
    ctx = _ctx(rules_active=True, conflict_policy_unknown=True)
    assert "portfolio_conflict_policy_unknown_fail_closed" in build_warnings(ctx, _led())


def test_degraded_partial_fill_evidence_is_never_silent() -> None:
    """A partial policy was active but no touching print carried a size, so the fills
    fell back to the coarse full-fill model. Never a fabricated fraction."""
    warnings = build_warnings(_ctx(), _led(partial_evidence_missing=True))
    assert "partial_fill_evidence_unavailable" in warnings


def test_tick_alignment_failure_is_never_silent() -> None:
    warnings = build_warnings(_ctx(tick_alignment_unavailable=True), _led())
    assert "tick_alignment_unavailable" in warnings


# --------------------------------------------------------------------------- #
# build_diagnostics — provenance the Result is read back through               #
# --------------------------------------------------------------------------- #
def test_warnings_are_carried_into_the_diagnostics_block() -> None:
    """The Result has no warnings field of its own; the diagnostics key IS the record."""
    diag = build_diagnostics(_ctx(), _led(), ["no_bars_in_source"])
    assert diag["warnings"] == ["no_bars_in_source"]


def test_bars_processed_reports_the_replayed_count() -> None:
    assert build_diagnostics(_ctx(), _led(bars_seen=42), [])["bars_processed"] == 42


def test_saved_and_executed_conflict_policy_are_separate_keys() -> None:
    """This pair is what keeps NET's downgrade visible. Collapsing them into one key
    would report a conservatively-downgraded run as if the saved policy was honored."""
    diag = build_diagnostics(_ctx(rules_active=True, conflict_gate_on=True), _led(), [])
    assert diag["portfolio_conflict_policy_executed"] == "block_opposite"


def test_executed_conflict_policy_is_none_when_no_rules_are_active() -> None:
    diag = build_diagnostics(_ctx(), _led(), [])
    assert diag["portfolio_conflict_policy_executed"] is None


def test_capability_not_in_build_is_empty_when_everything_is_modelled() -> None:
    diag = build_diagnostics(_ctx(), _led(), [])
    assert diag["capabilities_modelled"] is True
    assert diag["capability_not_in_build"] == []


def test_provenance_counters_come_from_the_ledger() -> None:
    """The 22 counters K-11a moved onto the ledger are read straight into this block,
    which is exactly where a dropped increment would surface."""
    led = _led(
        limit_orders_placed=7,
        limit_orders_filled=3,
        scale_layers_added=2,
        scale_layers_rejected=5,
        funding_charges=4,
    )
    diag = build_diagnostics(_ctx(), led, [])
    assert diag["limit_orders_placed"] == 7
    assert diag["limit_orders_filled"] == 3
    assert diag["scale_layers_added"] == 2
    assert diag["scale_layers_rejected"] == 5
    assert diag["funding_charges"] == 4


def test_decision_trace_schema_is_pinned_in_every_result() -> None:
    diag = build_diagnostics(_ctx(), _led(), [])
    assert diag["decision_trace_schema"] == "v1"
    assert "entry_fill" in diag["decision_trace_event_types"]


def test_execution_key_is_carried_into_diagnostics() -> None:
    diag = build_diagnostics(_ctx(execution_key="abc123"), _led(), [])
    assert diag["execution_key"] == "abc123"
