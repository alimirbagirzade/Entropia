"""ADIM 3 — shared capital allocation containment (doc 13 §8.3/§8.4/§13/§14 test 11).

Two halves, deliberately together in one file:

* the DEFECT, reproduced. These tests fail if the engine ever silently starts
  behaving like a unified clock, which is exactly when the containment must be
  revisited rather than left in place. They are the evidence the containment
  rests on, not decoration.
* the CONTAINMENT, pinned. The typed blocker, its remediation, the capability
  view the UI renders, and the guarantee that INDEPENDENT mode is untouched.

Infra-free: every function under test is pure.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.allocation.capability import (
    SHARED_ALLOCATION_FIELD_PATH,
    SHARED_ALLOCATION_MESSAGE,
    SHARED_ALLOCATION_REMEDIATION,
    SHARED_ALLOCATION_STATUS,
    shared_allocation_capability_view,
    shared_allocation_is_executable,
    shared_allocation_requested,
)
from entropia.domain.allocation.config import PortfolioAllocationConfigV1
from entropia.domain.allocation.enums import AllocationIssueCode as AllocCode
from entropia.domain.allocation.rules import AllocationItemRef, validate_allocation
from entropia.domain.backtest.engine import (
    EngineOutput,
    EquityPoint,
    ItemRun,
    TradeRow,
    resolve_allocation_execution,
)
from entropia.domain.backtest.execution.portfolio import combine_item_runs
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.readiness.enums import ReadinessIssueCode, ReadinessScope, ReadinessSeverity
from entropia.domain.readiness.validators import evaluate_readiness

_P0 = Decimal("10000.00")
_ZERO = Decimal("0.00")


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


def _item_run(item_id: str, closes: list[tuple[str, str]]) -> ItemRun:
    """One finished per-item run: a trade + an equity point per close time."""
    equity = _P0
    trades: list[TradeRow] = []
    points: list[EquityPoint] = [EquityPoint(0, "", _P0, _ZERO, _ZERO)]
    for seq, (timestamp, pnl) in enumerate(closes, start=1):
        equity += Decimal(pnl)
        trades.append(
            TradeRow(
                seq,
                timestamp,
                timestamp,
                "long",
                Decimal("100"),
                Decimal("101"),
                Decimal(pnl),
                "take_profit",
            )
        )
        points.append(EquityPoint(seq, timestamp, equity, _ZERO, _ZERO))
    return ItemRun(
        item_id,
        "strategy",
        None,
        None,
        EngineOutput(
            summary={
                "initial_capital": _P0,
                "final_equity": equity,
                "net_profit": equity - _P0,
                "net_profit_pct": None,
                "max_drawdown": _ZERO,
                "max_drawdown_pct": None,
                "symbol": "BTCUSDT",
                "timeframe": "1h",
            },
            trades=trades,
            equity_points=points,
            signal_events=[],
            diagnostics={"entry_model": "close", "warnings": []},
        ),
        item_label=item_id,
    )


def _capital_execution(*, enabled: bool = True) -> dict:
    return {
        "enabled": enabled,
        "config": {
            "initial_capital": {"amount": "10000.00", "currency": "USDT"},
            "reserve_cash_percent": "10.00",
            "compounding_mode": "COMPOUND_PORTFOLIO_EQUITY",
            "entries": [
                {"composition_item_id": "a", "active": True, "equity_share_percent": "50.00"},
                {"composition_item_id": "b", "active": True, "equity_share_percent": "50.00"},
            ],
        },
    }


def _plan(*, enabled: bool) -> PortfolioAllocationConfigV1:
    return PortfolioAllocationConfigV1.model_validate(
        {
            "enabled": enabled,
            "initial_capital": {"amount": "10000", "currency": "USDT"},
            "compounding_mode": "COMPOUND_PORTFOLIO_EQUITY",
            "reserve_cash_percent": "10",
            "entries": [
                {"composition_item_id": "a", "active": True, "equity_share_percent": "50"},
                {"composition_item_id": "b", "active": True, "equity_share_percent": "50"},
            ],
        }
    )


def _refs() -> dict[str, AllocationItemRef]:
    return {
        cid: AllocationItemRef(kind=MainboardItemKind.STRATEGY, available=True)
        for cid in ("a", "b")
    }


# --------------------------------------------------------------------------- #
# The defect, reproduced                                                       #
# --------------------------------------------------------------------------- #


def test_composite_portfolio_curve_is_not_time_ordered() -> None:
    """The composite "portfolio equity curve" is a per-item CONCATENATION.

    Doc 13 §8.3 requires one portfolio valuation snapshot per timestamp. The
    engine instead replays each item on its own bar axis and folds the finished
    runs in pin order, so the composite curve's points carry ITEM-order
    timestamps. A curve that is not time-ordered is not a portfolio valuation,
    and every metric measured along it (drawdown, and ROMAD through it) is a
    number that never existed.
    """
    # Item A moves at 01:00 and 04:00; item B moves in BETWEEN, at 02:00 / 03:00.
    a = _item_run("a", [("2024-01-01T01:00:00Z", "3000.00"), ("2024-01-01T04:00:00Z", "-2000.00")])
    b = _item_run("b", [("2024-01-01T02:00:00Z", "-3000.00"), ("2024-01-01T03:00:00Z", "3000.00")])

    combined = combine_item_runs(
        [a, b], portfolio_initial_capital=_P0, execution_key="k", item_count=2, shared_pool=True
    )

    stamps = [p.timestamp for p in combined.equity_points if p.timestamp]
    assert stamps != sorted(stamps), "curve is time-ordered — re-check the containment"
    assert stamps == [
        "2024-01-01T01:00:00Z",
        "2024-01-01T04:00:00Z",
        "2024-01-01T02:00:00Z",
        "2024-01-01T03:00:00Z",
    ]

    # The financial consequence, stated as a number. Folding item A whole and THEN
    # item B walks 10000 -> 13000 -> 11000 -> 8000 -> 11000: a 5000 trough measured
    # from a 13000 peak. Replaying the SAME four closes on one clock walks
    # 10000 -> 13000 -> 10000 -> 13000 -> 11000: the worst drawdown is 3000.
    assert combined.summary["max_drawdown"] == Decimal("5000.00")
    unified_peak, unified_equity, unified_dd = _P0, _P0, _ZERO
    for _stamp, pnl in sorted(
        [
            ("2024-01-01T01:00:00Z", Decimal("3000.00")),
            ("2024-01-01T02:00:00Z", Decimal("-3000.00")),
            ("2024-01-01T03:00:00Z", Decimal("3000.00")),
            ("2024-01-01T04:00:00Z", Decimal("-2000.00")),
        ]
    ):
        unified_equity += pnl
        unified_peak = max(unified_peak, unified_equity)
        unified_dd = max(unified_dd, unified_peak - unified_equity)
    assert unified_dd == Decimal("3000.00")
    assert combined.summary["max_drawdown"] > unified_dd

    # The deviation IS disclosed today — disclosure is why it was findable, and it
    # is also why disclosure alone was judged insufficient: the numbers above still
    # shipped as the canonical shared-capital Result.
    assert "portfolio_curve_sequential_not_unified_clock" in combined.diagnostics["warnings"]
    assert combined.diagnostics["composition"]["capital_allocation"] == "shared_pool"


def test_every_item_independently_resolves_the_full_pool() -> None:
    """No cross-item state exists in the capital projection.

    Each item is handed P0 and its own share, so under COMPOUND_PORTFOLIO_EQUITY an
    item's sleeve compounds off its OWN equity and can never see a sibling's PnL,
    fees or funding — the pool is shared in name only (doc 13 §8.3 E(t)).
    """
    snapshot = _capital_execution()
    resolved = {item: resolve_allocation_execution(snapshot, item_id=item) for item in ("a", "b")}

    assert resolved["a"] is not None and resolved["b"] is not None
    assert resolved["a"].initial_capital == resolved["b"].initial_capital == _P0
    assert resolved["a"].compound is True
    # The value object carries capital, reserve, compounding and the item's OWN
    # share — and nothing about any other item.
    assert set(type(resolved["a"]).__slots__) == {
        "initial_capital",
        "reserve_percent",
        "compound",
        "item_share_percent",
        "currency",
    }


# --------------------------------------------------------------------------- #
# The containment                                                              #
# --------------------------------------------------------------------------- #


def test_shared_mode_is_declared_non_executable() -> None:
    assert SHARED_ALLOCATION_STATUS == "future_dev"
    assert shared_allocation_is_executable() is False


def test_enabled_plan_leads_with_the_containment_blocker() -> None:
    issues, derived = validate_allocation(_plan(enabled=True), item_refs=_refs())

    assert str(issues[0].code) == str(AllocCode.SHARED_MODE_NOT_IN_BUILD)
    assert str(issues[0].severity) == "blocker"
    assert issues[0].field == SHARED_ALLOCATION_FIELD_PATH
    assert issues[0].message == SHARED_ALLOCATION_MESSAGE
    # The plan stays fully diagnosable and previewable — only the freeze and the
    # RUN are refused, so the page can still show the sleeve maths.
    assert derived is not None


def test_independent_mode_is_untouched() -> None:
    """Doc 13 §1.1: independent capital is a complete mode, not a degraded one."""
    issues, derived = validate_allocation(_plan(enabled=False), item_refs=_refs())

    assert issues == []
    assert derived is None
    # ... and a disabled snapshot resolves to no shared capital at all, so the
    # engine sizes from each strategy's own initial capital exactly as before.
    assert resolve_allocation_execution(_capital_execution(enabled=False), item_id="a") is None
    assert shared_allocation_requested(_capital_execution(enabled=False)) is False


def test_admission_guard_predicate_agrees_with_the_engine() -> None:
    """The guard and the engine must never disagree about which runs are shared."""
    for snapshot in (
        _capital_execution(enabled=True),
        _capital_execution(enabled=False),
        {"enabled": False},
        {},
        None,
        "not-a-dict",
    ):
        engine_shared = resolve_allocation_execution(snapshot, item_id="a") is not None  # type: ignore[arg-type]
        if engine_shared:
            assert shared_allocation_requested(snapshot) is True
    assert shared_allocation_requested(_capital_execution(enabled=True)) is True
    assert shared_allocation_requested(None) is False
    assert shared_allocation_requested("not-a-dict") is False
    assert shared_allocation_requested({"enabled": False}) is False


def test_ready_check_raises_the_typed_blocker_with_remediation() -> None:
    allocation_issues, _derived = validate_allocation(_plan(enabled=True), item_refs=_refs())

    evaluation = evaluate_readiness(
        [], allocation_enabled=True, allocation_issues=allocation_issues
    )

    contained = [
        i
        for i in evaluation.issues
        if i.code == ReadinessIssueCode.ALLOCATION_SHARED_MODE_NOT_IN_BUILD
    ]
    assert len(contained) == 1
    issue = contained[0]
    assert issue.severity == ReadinessSeverity.BLOCKER
    assert issue.scope == ReadinessScope.PORTFOLIO_ALLOCATION
    assert issue.message == SHARED_ALLOCATION_MESSAGE
    # Doc 14 §9.1: a readiness issue carries the ACTIONABLE half, not only the symptom.
    assert issue.remediation == SHARED_ALLOCATION_REMEDIATION
    assert issue.field_path == SHARED_ALLOCATION_FIELD_PATH
    assert evaluation.blocker_count >= 1
    assert str(evaluation.state) == "not_ready"


def test_ready_check_stays_clean_in_independent_mode() -> None:
    evaluation = evaluate_readiness([], allocation_enabled=False, allocation_issues=[])

    assert not any(
        i.code == ReadinessIssueCode.ALLOCATION_SHARED_MODE_NOT_IN_BUILD for i in evaluation.issues
    )


def test_capability_view_is_the_single_source_the_ui_renders() -> None:
    """UI <-> Ready Check <-> engine parity: one set of texts, one status."""
    view = shared_allocation_capability_view()

    assert view["status"] == SHARED_ALLOCATION_STATUS
    assert view["available"] is shared_allocation_is_executable()
    assert view["message"] == SHARED_ALLOCATION_MESSAGE
    assert view["remediation"] == SHARED_ALLOCATION_REMEDIATION
    assert view["field_path"] == SHARED_ALLOCATION_FIELD_PATH
    assert view["dependency"]
    assert view["key"] == "portfolio.shared_capital_allocation"
