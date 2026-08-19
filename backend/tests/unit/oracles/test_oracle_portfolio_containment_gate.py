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
from collections.abc import Mapping
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

#: The production modules outside ``execution/`` that may name a phase-loop module, as an
#: exhaustive NAMED list per state of the tree. ``participant.py`` is the `C3` adapter: it
#: takes ``ItemTickView``/``PortfolioSnapshot``/``ArbitrationDecision`` in its signatures, so
#: it cannot exist without appearing here, and it sits outside ``execution/`` on purpose —
#: inside, the scan below would have exempted it and this guard would have gone BLIND rather
#: than satisfied. Signed 2026-08-18, Option A — ONE NAMED module, never a wildcard:
#: ``docs/decisions/closure_participant_importer_allowlist_2026-08-18.md``.
_AUTHORISED_PHASE_LOOP_IMPORTERS: tuple[list[str], ...] = (
    [],
    ["domain/backtest/portfolio_engine.py"],
    ["domain/backtest/participant.py", "domain/backtest/portfolio_engine.py"],
)

#: Every public way INTO the phase loop. The caller scan below is a text search, so it
#: covers exactly the names listed here. ``iter_portfolio`` (C2) is the tick-drivable form
#: and is the one a worker would reach for first, so omitting it would leave the loop's
#: most likely production entry point unguarded.
_LOOP_ENTRY_POINTS = ("run_portfolio", "iter_portfolio")

#: The ONE production module `C4` authorises to drive the phase loop and to project its
#: run. Named by exact path, never a prefix: a second caller — a route, a command, a
#: second job — is still a red build, which is the whole of what "nothing calls it" used
#: to buy. This list REPLACES an emptiness assertion with an authorisation one, and the
#: design says so in as many words (P-C2 §C.6): *the gate is narrowed, never deleted*.
#: The behavioural half that a text scan cannot give lives in
#: ``tests/integration/test_backtest_unified_clock_wiring.py``.
_AUTHORISED_LOOP_CALLERS = ["application/jobs/backtest_engine.py"]
_AUTHORISED_PROJECTION_CALLERS = ["application/jobs/backtest_engine.py"]


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


def _importers_outside_execution(module: str, sources: Mapping[pathlib.Path, str]) -> list[str]:
    """Every production module OUTSIDE ``execution/`` that imports one phase-loop module.

    Factored out of the test so the widening of :data:`_AUTHORISED_PHASE_LOOP_IMPORTERS`
    can be negative-controlled against the real predicate rather than against a paraphrase
    of it — a restated scan would be a second implementation, free to disagree with the one
    that actually guards the tree."""
    return sorted(
        str(path.relative_to(_SRC))
        for path, text in sources.items()
        if f"execution.{module.split('.')[-1]} import" in text and path.parent.name != "execution"
    )


def test_the_phase_loop_exists_but_no_production_path_reaches_it() -> None:
    """ADR §12 ADIM 18 / §14 A1 — the positive counterpart of the pre-ADIM-18 assertion.

    The outer loop over the merged timestamp axis now EXISTS: ``run_portfolio`` is a shipped
    production entry point and this package's oracles run on it unchanged. A1 is therefore no
    longer "no such loop"; it is "the loop is there and nothing in production calls it".

    **`C4` changed what that second half can assert, and this is the deliberate update.**
    Until now the worker named nothing: the adapter (`C3`, ``participant.py``) had no caller
    and the loop had none either, so emptiness was provable by a text scan. `C4` wires ONE
    caller — ``application/jobs/backtest_engine.py`` — so the invariant becomes *no production
    REQUEST can reach the loop, because its only caller is guarded by
    ``shared_allocation_is_executable()``, which is ``future_dev``*. That is a genuinely
    weaker property and a text scan cannot prove it, so the scan was **narrowed to an
    authorised-caller allowlist** (never deleted, never loosened to "some callers are fine")
    and the reachability half moved to behavioural tests in
    ``tests/integration/test_backtest_unified_clock_wiring.py``. P-C2 §C.6 designs exactly
    this pair.

    The stepper this is all built on shipped long ago: ADR §12's ADIM 16 landed as PR #602
    (see that ADR's own AMENDMENT, which supersedes the SKIPPED paragraph above it) — an
    earlier version of this docstring still said it *"was never written"*, and W0 flagged that
    as documentation drift. ``engine._build_stepper`` hands back an ``_ItemStepper`` enterable
    one bar at a time, `C1` split its phases into describe/book halves, and `C3` put those
    halves behind ``ItemParticipant``.

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
        importers = _importers_outside_execution(module, sources)
        assert importers in _AUTHORISED_PHASE_LOOP_IMPORTERS, (
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
    assert callers == _AUTHORISED_LOOP_CALLERS, (
        f"run_portfolio/iter_portfolio gained an UNAUTHORISED production caller: {callers}"
    )

    worker = sources[_SRC / "application" / "jobs" / "backtest_engine.py"]
    # UNCHANGED, and they must stay that way. The independent-mode fold and its item loop
    # have to survive the wiring: deleting either would route every independent composite
    # run through the shared loop and silently re-price it, with no flag and no bump.
    assert "combine_item_runs(" in worker
    assert "for prepared in prepared_items:" in worker
    # What replaces "nothing calls it": the one authorised caller is FLAG-GUARDED, so no
    # production REQUEST can reach the loop while the flag is future_dev.
    assert "shared_allocation_is_executable" in worker


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
    assert callers == _AUTHORISED_PROJECTION_CALLERS, (
        f"the Result projection gained an UNAUTHORISED production caller: {callers}"
    )

    # The worker now legitimately NAMES the projection — `C4` wired it. What must hold
    # instead is that the branch which reaches it is flag-guarded, and that the sequential
    # fold is still there for every run that is not on the unified clock.
    worker = sources[_SRC / "application" / "jobs" / "backtest_engine.py"]
    assert "shared_allocation_is_executable" in worker
    assert "combine_item_runs(" in worker


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


def test_widening_the_importer_allowlist_did_not_disable_it() -> None:
    """The negative control the `C3` allowlist decision was signed ON, kept executable.

    ``docs/decisions/closure_participant_importer_allowlist_2026-08-18.md`` makes this
    mandatory rather than optional, in its closing limits, item 4: a fabricated second or
    third importer must STILL turn the gate red — otherwise what was performed was not a
    widening but a disabling.

    Both halves of that are asserted, because only the pair distinguishes a NAMED list from
    a loosened one:

    * a **third** importer is refused — the allowlist did not become "two entries are fine";
    * a **differently-named second** importer is refused — it did not become "one extra
      module is fine", which is what a ``len()`` check or a wildcard would have produced.

    The real predicate is exercised, not a paraphrase: the probe modules are injected into
    the same ``sources`` mapping ``_importers_outside_execution`` reads, so a scan that
    stopped detecting imports at all would fail this test instead of passing it silently."""
    sources = {p: p.read_text() for p in _SRC.rglob("*.py")}
    module = "execution.clock"
    live = _importers_outside_execution(module, sources)

    # The tree as it stands is authorised — and it is the WIDENED entry that authorises it,
    # so this test fails if the adapter is ever moved into ``execution/`` and the widening
    # is left behind as dead permission.
    assert live in _AUTHORISED_PHASE_LOOP_IMPORTERS
    assert live == ["domain/backtest/participant.py", "domain/backtest/portfolio_engine.py"]

    probe_src = "from entropia.domain.backtest.execution.clock import ItemTickView\n"
    third = _SRC / "domain" / "backtest" / "_probe_third_importer.py"
    second = _SRC / "domain" / "backtest" / "_probe_other_adapter.py"
    assert third not in sources and second not in sources

    with_third = _importers_outside_execution(module, {**sources, third: probe_src})
    assert len(with_third) == 3
    assert with_third not in _AUTHORISED_PHASE_LOOP_IMPORTERS, (
        "a third production importer of the phase loop passed the widened allowlist; the "
        "widening disabled the tripwire instead of extending it by one named module"
    )

    without_adapter = {p: t for p, t in sources.items() if p.name != "participant.py"}
    with_other = _importers_outside_execution(module, {**without_adapter, second: probe_src})
    assert len(with_other) == 2
    assert with_other not in _AUTHORISED_PHASE_LOOP_IMPORTERS, (
        "a DIFFERENTLY-NAMED second importer passed the allowlist; it is a named list, not "
        "a count, and Option B/C were rejected precisely because they stop naming anything"
    )
