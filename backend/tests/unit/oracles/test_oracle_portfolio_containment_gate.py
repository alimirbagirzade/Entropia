"""The containment-lift gate, as executable evidence (ADR 0002 §14, capability.py §REMOVAL).

``docs/decisions/2026-08-03_shared_portfolio_containment.md`` §6 lists six conditions for
flipping ``SHARED_ALLOCATION_STATUS`` to ``"active_v1"``; ADR 0002 §14 expands them into the
A1-A22 acceptance matrix. The six per-module containment guards each pin one edge. Nothing
pins the SHAPE of the gap as a whole, and nothing shows the two numbers — sequential and
unified — side by side on one trade set.

This module does both. It is written to FAIL the day someone lifts the flag, bumps the engine
version or closes the last gap without the rest of the matrix, which is precisely when a human
must re-read §14 rather than trust a green suite.

**Updated at ADIM 18.** ``run_portfolio`` now exists and the oracles run on it, so the gate no
longer asserts that no driver exists — it asserts the two facts that are still true and are
what actually keeps the containment closed: the loop has no production CALLER (the worker
still folds finished per-item runs), and every unified-clock module is reachable only through
it. A phase loop nothing calls cannot change a shipped Result.
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

#: The unified-clock program's modules. Since ADIM 18 the phase loop reaches four of them; the
#: other two (attribution, provenance) are still reachable only from inside ``execution/``.
_PHASE_LOOP_MODULES = (
    "execution.clock",
    "execution.intents",
    "execution.portfolio_ledger",
    "execution.arbitration",
    "execution.attribution",
    "execution.provenance",
)

#: Every public way INTO the phase loop. The caller scan below is a text search, so it
#: covers exactly the names listed here. ``iter_portfolio`` (C2) is the tick-drivable form
#: and is the one a worker would reach for first, so omitting it would leave the loop's
#: most likely production entry point unguarded.
_LOOP_ENTRY_POINTS = ("run_portfolio", "iter_portfolio")

#: The production modules outside ``execution/`` that may name a unified-clock module.
#: Widened from two entries to three at `C3`, under the signed decision
#: ``docs/decisions/closure_participant_importer_allowlist_2026-08-18.md`` (Option A,
#: 2026-08-18): the adapter is deliberately placed at ``domain/backtest/participant.py``
#: rather than inside ``execution/``, where the scan's ``parent.name`` exemption would have
#: kept this gate green while the surface grew. The list is NAMED, never a glob or a prefix
#: — a wildcard would open the gate at class width and the widening would stop showing up in
#: a diff. An unexpected THIRD importer still turns this red, which is the whole point;
#: ``test_a_third_importer_still_turns_the_gate_red`` is the negative control the decision
#: required, so this widening is provably an extension and not a disabling.
_ALLOWED_IMPORTERS: tuple[list[str], ...] = (
    [],
    ["domain/backtest/portfolio_engine.py"],
    ["domain/backtest/participant.py", "domain/backtest/portfolio_engine.py"],
)


def _importers_outside_execution(sources: dict[pathlib.Path, str], module: str) -> list[str]:
    """Production modules OUTSIDE ``execution/`` that name ``module``'s import literal.

    Extracted so the gate below and its negative control run the SAME scan over different
    source maps. A negative control that re-implemented the scan would only prove that the
    copy is red."""
    return sorted(
        str(path.relative_to(_SRC))
        for path, text in sources.items()
        if f"execution.{module.split('.')[-1]} import" in text and path.parent.name != "execution"
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


def test_the_phase_loop_exists_but_no_production_path_reaches_it() -> None:
    """ADR §12 ADIM 18 / §14 A1 — the positive counterpart of the pre-ADIM-18 assertion.

    The outer loop over the merged timestamp axis now EXISTS: ``run_portfolio`` is a shipped
    production entry point and this package's oracles run on it unchanged. A1 is therefore no
    longer "no such loop"; it is "the loop is there and nothing in production calls it".

    That second half is what still holds the containment closed, and it is the honest gap:
    wiring the worker needs an ``ItemParticipant`` backed by the real engine — a per-item
    replay advanceable to a given ``t``. **What is missing is that ADAPTER, not the stepper.**
    The stepper ADR §12 calls ADIM 16 SHIPPED as PR #602 (see that ADR's own AMENDMENT, which
    supersedes the SKIPPED paragraph above it): ``engine._build_stepper`` hands back an
    ``_ItemStepper`` that can be entered one bar at a time, and ``run_engine`` is a short
    driver over it on every single-item run today. The remaining gap is one of SHAPE — the
    stepper's phases BOOK, while ``ItemParticipant`` needs them to DESCRIBE so the loop can
    arbitrate first. So the worker keeps its item loop and ``combine_item_runs``, no request or
    retry can reach a tick loop, and no shipped Result can change. When the participant lands,
    this test is the one that must be updated deliberately.

    Every unified-clock module stays reachable ONLY through the phase loop: the per-module
    guards name their importers exactly, and this asserts the containing shape of that — the
    single production module they may be imported from."""
    sources = {p: p.read_text() for p in _SRC.rglob("*.py")}

    loop = _SRC / "domain" / "backtest" / "portfolio_engine.py"
    assert "def run_portfolio" in sources[loop]
    # Exactly one production module defines the driver — two would be two answers to the
    # phase-order question, which is the one thing this loop exists to make single.
    assert [p.name for p, text in sources.items() if "def run_portfolio" in text] == [
        "portfolio_engine.py"
    ]

    for module in _PHASE_LOOP_MODULES:
        importers = _importers_outside_execution(sources, module)
        assert importers in _ALLOWED_IMPORTERS, (
            f"{module} gained a production importer outside the phase loop: {importers}"
        )

    # The containment itself: nothing CALLS the loop, and the worker is untouched.
    # BOTH entry points are named. Greping only for ``run_portfolio`` would let a production
    # module drive the whole phase loop — P10 included — through ``iter_portfolio`` with this
    # assertion still green, which is exactly the wiring this gate exists to make impossible.
    callers = sorted(
        str(path.relative_to(_SRC))
        for path, text in sources.items()
        if path != loop
        and any(f"{name}(" in text or f"import {name}" in text for name in _LOOP_ENTRY_POINTS)
    )
    assert callers == [], f"the phase loop gained a production caller: {callers}"

    worker = sources[_SRC / "application" / "jobs" / "backtest_engine.py"]
    assert "combine_item_runs(" in worker
    assert "for prepared in prepared_items:" in worker


def test_the_result_projection_exists_but_no_production_path_reaches_it_either() -> None:
    """The second half of the path, and the same answer: it exists, nothing calls it.

    ``execution/portfolio_projection.py`` turns a finished ``PortfolioRun`` into the composite
    ``EngineOutput`` ADR §14's A4 and A18 are worded over — until it existed there was no
    artifact on that path to digest, so neither criterion could be evaluated at all. It moves
    no shipped number because the half in front of it is still uncalled.

    Asserted rather than assumed, for two reasons the phase loop's own test does not cover.
    The projection sits INSIDE ``execution/``, which the per-module importer check above
    exempts, so nothing there can see it widen the unified-clock surface. And unlike the loop
    it produces the exact type the worker persists — a single import in
    ``jobs/backtest_engine.py`` would be enough to change every multi-item Result, with no
    participant, no adapter and no ``ENGINE_VERSION`` bump in between. When the call site
    lands, this test is the one that must be updated deliberately."""
    sources = {p: p.read_text() for p in _SRC.rglob("*.py")}
    projection = _SRC / "domain" / "backtest" / "execution" / "portfolio_projection.py"

    assert "def project_portfolio_run" in sources[projection]
    # One module answers "what does a portfolio run look like as a Result"; two would be two
    # answers, which is the same reason exactly one module defines the phase order.
    assert [p.name for p, text in sources.items() if "def project_portfolio_run" in text] == [
        "portfolio_projection.py"
    ]

    callers = sorted(
        str(path.relative_to(_SRC))
        for path, text in sources.items()
        if path != projection
        and ("project_portfolio_run(" in text or "import project_portfolio_run" in text)
    )
    assert callers == [], f"the Result projection gained a production caller: {callers}"

    # The worker's Result still comes from per-item runs folded sequentially, untouched.
    worker = sources[_SRC / "application" / "jobs" / "backtest_engine.py"]
    assert "portfolio_projection" not in worker


def test_the_containment_flag_and_engine_version_are_both_untouched() -> None:
    """§6 condition 6 / ADR §14 A15: the lift REQUIRES an ``ENGINE_VERSION`` bump, so no
    sequential-era Result can be idempotently reused for a unified-clock re-run. Neither the
    flag nor the version has moved, and the dependency the capability names is still the
    co-simulation this package's oracles exercise only through a test-owned driver."""
    assert SHARED_ALLOCATION_STATUS == "future_dev"
    assert shared_allocation_is_executable() is False
    # The literal moves only when something OUTSIDE the contained work bumps the version;
    # #550/#551/#552 (percent sizing, the zero-size guard, per-fill commission) did, and
    # the tripwire is unchanged by that: lifting containment still cannot happen without
    # editing this line.
    assert ENGINE_VERSION == "backtest-engine-v18-percent-sizing-per-fill-commission"
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


def test_every_public_loop_driver_is_named_in_the_caller_scan() -> None:
    """The caller scan cannot be wider than the names it greps for.

    The scan in the containment test is a TEXT search, so it covers exactly the entry
    points ``_LOOP_ENTRY_POINTS`` lists and nothing else. That is a standing hazard, and
    it already bit once: C2 added ``iter_portfolio`` to the phase-loop module as a public
    export — the only form a worker can drive, since its cancellation check is ``async``
    and cannot run inside a synchronous loop — while the scan still named only
    ``run_portfolio``. A production module could have imported it and driven every phase,
    P10 included, with the containment assertion green.

    This derives the answer from the module rather than restating it: every public
    callable taking ``participants`` IS a way into the loop. A third entry point therefore
    turns this red until someone adds it to the tuple, instead of silently narrowing the
    containment assertion the way the second one did.
    """
    import inspect

    from entropia.domain.backtest import portfolio_engine as pe

    drivers = sorted(
        name
        for name in pe.__all__
        if inspect.isfunction(getattr(pe, name))
        and "participants" in inspect.signature(getattr(pe, name)).parameters
    )
    assert drivers == sorted(_LOOP_ENTRY_POINTS), (
        "a new public way into the phase loop appeared; add it to _LOOP_ENTRY_POINTS or the "
        f"containment caller scan will not see it. Found: {drivers}"
    )


def test_the_widened_allowlist_names_a_module_that_actually_imports_the_loop_surface() -> None:
    """The third entry is load-bearing, not decoration.

    ``domain/backtest/participant.py`` has to NAME the gated types — ``ItemTickView``,
    ``ItemIdentity``, ``PortfolioSnapshot``, ``OpenPosition``, ``ArbitrationDecision`` — and
    ``portfolio_engine.__all__`` re-exports none of them, so the adapter can only reach them
    from ``execution.*``. That is why the gate turned red and why the allowlist had to be
    widened by a human decision rather than by a re-export that would have kept it green
    while measuring nothing (the signed decision's Option C, refused).

    Asserted so the entry cannot silently become dead text: if the adapter ever stops
    importing the surface, the extra name has to come back OUT of the allowlist."""
    sources = {p: p.read_text() for p in _SRC.rglob("*.py")}
    adapter = "domain/backtest/participant.py"

    reached = [
        m for m in _PHASE_LOOP_MODULES if adapter in _importers_outside_execution(sources, m)
    ]
    assert reached, (
        "no unified-clock module is imported by the adapter, so the widened allowlist entry "
        "is measuring nothing and must be removed"
    )
    # And the narrower, pre-C3 allowlist would have REFUSED it — the widening was a real
    # decision, not a formality.
    for module in reached:
        assert _importers_outside_execution(sources, module) not in (
            [],
            ["domain/backtest/portfolio_engine.py"],
        )


def test_a_third_importer_still_turns_the_gate_red() -> None:
    """The negative control the signed decision made mandatory.

    ``closure_participant_importer_allowlist_2026-08-18.md`` §"Karar ne verilirse verilsin"
    item 4: *"a fake second/third importer must still turn the gate red — otherwise what was
    done is a disabling, not a widening."* The probe is injected into the SCANNED SOURCE MAP
    rather than written to disk, so a failing run cannot leave a stray module in
    ``backend/src`` (the decision's own measurement used two temporary files and deleted them
    by hand).

    Every gated module is probed, not just one: an allowlist that happened to be widened per
    module would pass a single-module control."""
    sources = {p: p.read_text() for p in _SRC.rglob("*.py")}
    probe = _SRC / "domain" / "backtest" / "_probe_third_importer.py"
    assert probe not in sources  # the probe is synthetic; it must not exist on disk

    for module in _PHASE_LOOP_MODULES:
        leaf = module.split(".")[-1]
        widened = dict(sources)
        widened[probe] = f"from entropia.domain.backtest.execution.{leaf} import something\n"
        importers = _importers_outside_execution(widened, module)

        assert "domain/backtest/_probe_third_importer.py" in importers
        assert importers not in _ALLOWED_IMPORTERS, (
            f"a third importer of {module} passed the allowlist: the gate has been disabled, "
            "not widened"
        )
