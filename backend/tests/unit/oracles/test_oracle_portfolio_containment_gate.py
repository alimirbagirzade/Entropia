"""The containment-lift gate, as executable evidence (ADR 0002 §14, capability.py §REMOVAL).

``docs/decisions/2026-08-03_shared_portfolio_containment.md`` §6 lists six conditions for
flipping ``SHARED_ALLOCATION_STATUS`` to ``"active_v1"``; ADR 0002 §14 expands them into the
A1-A22 acceptance matrix. The six per-module ``test_nothing_in_production_imports_*`` guards
each pin one edge of the containment. Nothing pins the SHAPE of the gap as a whole, and
nothing shows the two numbers — sequential and unified — side by side on one trade set.

This module does both. It is written to FAIL the day someone lifts the flag, bumps the engine
version or wires a driver without the rest of the matrix, which is precisely when a human must
re-read §14 rather than trust a green suite.
"""

from __future__ import annotations

import pathlib
from decimal import Decimal

from entropia.domain.allocation.capability import (
    SHARED_ALLOCATION_DEPENDENCY,
    SHARED_ALLOCATION_STATUS,
    shared_allocation_is_executable,
)
from entropia.domain.backtest.engine import (
    EngineOutput,
    EquityPoint,
    ItemRun,
    TradeRow,
)
from entropia.domain.backtest.execution.portfolio import combine_item_runs
from entropia.domain.backtest.manifest import ENGINE_VERSION

from .portfolio_harness import simulate
from .test_oracle_portfolio_clock import _HOURS, _interleaved_pair

_SRC = pathlib.Path(__file__).resolve().parents[3] / "src" / "entropia"
_P0 = Decimal("10000.00")
_ZERO = Decimal("0.00")

#: The unified-clock program's modules. ADR §12 puts the driver that would call them in ADIM
#: 18; until it exists they are reachable only from each other.
_PHASE_LOOP_MODULES = (
    "execution.clock",
    "execution.intents",
    "execution.portfolio_ledger",
    "execution.arbitration",
    "execution.attribution",
    "execution.provenance",
)


def _item_run(item_id: str, closes: list[tuple[str, str]]) -> ItemRun:
    """One finished per-item run — the shape ``jobs/backtest_engine.py`` still folds."""
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


def test_the_same_trades_read_5000_sequentially_and_3000_on_one_clock() -> None:
    """The contained defect and its unified answer, on ONE trade set, in one place.

    A realises +3000 at 01:00 and -2000 at 04:00; B realises -3000 at 02:00 and +3000 at
    03:00. Folding A whole and THEN B walks 10000 -> 13000 -> 11000 -> 8000 -> 11000 and
    measures a 5000 trough from the 13000 peak. The merged axis walks the same four closes
    10000 -> 13000 -> 10000 -> 13000 -> 11000 and measures 3000.

    The sequential number is what a shared-capital Result would still publish today, which is
    why the mode fails closed rather than merely disclosing the deviation."""
    sequential = combine_item_runs(
        [
            _item_run("a", [(_HOURS[1], "3000.00"), (_HOURS[4], "-2000.00")]),
            _item_run("b", [(_HOURS[2], "-3000.00"), (_HOURS[3], "3000.00")]),
        ],
        portfolio_initial_capital=_P0,
        execution_key="k",
        item_count=2,
        shared_pool=True,
    )
    unified = simulate(_interleaved_pair(), pool="10000")

    assert sequential.summary["max_drawdown"] == Decimal("5000.00")
    assert unified.max_drawdown == Decimal("3000.00")

    stamps = [p.timestamp for p in sequential.equity_points if p.timestamp]
    assert stamps != sorted(stamps)  # item-order timestamps, not a time series
    assert list(unified.instants) == sorted(unified.instants)

    # The shipped fold still discloses itself; nothing about it was changed here.
    assert "portfolio_curve_sequential_not_unified_clock" in sequential.diagnostics["warnings"]


def test_the_unified_clock_driver_exists_but_nothing_in_production_reaches_it() -> None:
    """ADR §12 ADIM 18 / §14 A1: the outer loop must become the merged timestamp axis.

    **Updated deliberately, which is what this module was built for.** Its own docstring says
    it is written to fail *"the day someone … wires a driver without the rest of the matrix,
    which is precisely when a human must re-read §14 rather than trust a green suite."* ADIM 18
    (PR #585) landed ``run_portfolio``, so the two assertions that encoded *"no such entry
    point exists"* are now false — and the PROPERTY they defended is unchanged, so it is
    restated rather than deleted:

    * the driver exists, and it lives in ``domain/backtest/portfolio_engine.py``;
    * that module is the ONLY production importer of the six unified-clock modules, and it has
      no importer of its own — so no request, retry or Agent call can reach a tick loop;
    * the worker still loops over items and folds finished per-item runs.

    Deleting the test instead would have removed the one gate that notices the difference
    between *"the loop exists"* and *"the loop runs"*. Wiring the worker is ADIM 18b, and this
    test is the thing that must go red when it happens."""
    sources = {p: p.read_text() for p in _SRC.rglob("*.py")}

    definitions = sorted(
        str(path.relative_to(_SRC)) for path, text in sources.items() if "def run_portfolio" in text
    )
    assert definitions == ["domain/backtest/portfolio_engine.py"]

    for module in _PHASE_LOOP_MODULES:
        importers = sorted(
            str(path.relative_to(_SRC))
            for path, text in sources.items()
            if f"execution.{module.split('.')[-1]} import" in text
            and path.parent.name != "execution"
        )
        assert importers == ["domain/backtest/portfolio_engine.py"], (
            f"{module} gained a production importer outside execution/ and the phase loop"
        )

    # The phase loop is contained in turn: nothing imports IT, so the chain from any
    # production entry point to a tick loop is still broken.
    assert [
        str(path.relative_to(_SRC))
        for path, text in sources.items()
        if "backtest.portfolio_engine" in text and path.name != "portfolio_engine.py"
    ] == []

    worker = (_SRC / "application" / "jobs" / "backtest_engine.py").read_text()
    assert "run_portfolio" not in worker
    assert "combine_item_runs(" in worker
    assert "for prepared in prepared_items:" in worker


def test_the_containment_flag_and_engine_version_are_both_untouched() -> None:
    """§6 condition 6 / ADR §14 A15: the lift REQUIRES an ``ENGINE_VERSION`` bump, so no
    sequential-era Result can be idempotently reused for a unified-clock re-run. Neither the
    flag nor the version has moved, and the dependency the capability names is still the
    co-simulation this package's oracles exercise only through a test-owned driver."""
    assert SHARED_ALLOCATION_STATUS == "future_dev"
    assert shared_allocation_is_executable() is False
    assert ENGINE_VERSION == "backtest-engine-v18-gap-adjusted-stop-fill"
    assert "unified-clock multi-item co-simulation" in SHARED_ALLOCATION_DEPENDENCY


def test_the_manifest_carries_none_of_the_policy_fields_the_lift_requires() -> None:
    """ADR §10.1 / §14 A16: a lifted build must record the resolved sleeve amounts, the FX
    refs and every policy version in the run manifest. The shipped manifest carries none of
    them — ``execution/provenance.py`` can build the block, but nothing calls it."""
    manifest = (_SRC / "domain" / "backtest" / "manifest.py").read_text()
    for field in (
        "engine_allocation_policy_version",
        "clock_policy_version",
        "arbitration_policy_version",
        "mark_staleness_policy",
    ):
        assert field not in manifest
