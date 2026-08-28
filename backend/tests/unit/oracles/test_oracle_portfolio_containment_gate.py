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

**Updated again at `C4` (E5) — the scan is NARROWED, never deleted.** The worker now carries
the shared branch, so "nothing calls it" is no longer true and cannot be made true again
without un-wiring. What replaces it is strictly weaker and is stated as such: *the loop and
the Result projection have exactly ONE authorised production caller each, and that caller
reads ``shared_allocation_is_executable`` at the branch.* A second caller — a route, a
command, a second job — is still a red build.

Reachability is behavioural and a text scan cannot prove it, so the scan does not pretend to.
The half a scan cannot give lands in the same slice, in two INFRA-BOUND modules that cannot
live in this infra-free package:

* ``tests/integration/test_shared_clock_worker_branch.py`` — a real two-Strategy independent
  run never reaches the loop, and (with the flag forced by a test-owned fixture) a shared one
  does, is cancellable between ticks, and fails closed on a shape the adapter cannot drive.
  It now also carries the half this file states only as SOURCE facts. The two assertions
  below — ``combine_item_runs(`` present, and the item loop's header present exactly once —
  prove the independent fold still EXISTS; that module proves it still produces the same
  BYTES with the flag lifted, over the stored per-artifact content checksums. Existing and
  pricing identically are different claims, and a negative control separated them: folding a
  lone Strategy as a one-row composite, and letting the fold read the capability flag instead
  of the run's own plan, each left every assertion in THIS file green;
* ``tests/integration/test_shared_allocation_containment.py`` — already shipped, and it must
  stay green **unweakened**: it is what proves no request can ask for the branch at all.

``tests/unit/test_shared_clock_branch_predicate.py`` carries the 2x2 that pins each conjunct
of ``_use_unified_clock`` separately, because ``A and B`` short-circuits and a test of the
compound answer passes with ``B`` deleted.

Two of the assertions below are deliberately UNTOUCHED by the narrowing and must stay green:
``combine_item_runs(`` and ``for prepared in prepared_items:``. Deleting either would silently
re-price every INDEPENDENT composite Result, and the wiring PR is exactly when that could
happen unnoticed.

The per-module importer allowlist is **also** untouched, and that took work rather than luck:
the worker builds its participants through ``participant.build_engine_participant`` so it
never names ``ItemIdentity`` or ``ItemBarStream`` itself. Naming them was tried, measured
(five assertions across three files red) and REJECTED — it would have widened an allowlist a
human signed for exactly one module by a second, unsigned one.

The two test names below outlive their own wording on purpose. They are cited from
``domain/backtest/portfolio_engine.py`` (a file `C4` must not touch) and from several frozen
evidence documents; renaming them would break those citations to fix a sentence these
docstrings already correct.
"""

from __future__ import annotations

import pathlib
import re
from collections.abc import Mapping
from decimal import Decimal

import pytest

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
#: **UNCHANGED at `C4` (E5), and that took work rather than luck.** Wiring the worker's
#: shared branch by naming ``ItemIdentity`` / ``ItemBarStream`` in
#: ``application/jobs/backtest_engine.py`` was tried first, and it turned FIVE assertions
#: across THREE files red: this one, the two caller scans below, and the per-module clock /
#: intents guards (the ledger, arbitration, attribution and provenance guards stayed green —
#: the worker names none of those four). That would have widened a SIGNED allowlist by a
#: second, UNSIGNED module, which is exactly the debt GH #731 already tracks. So the worker
#: goes through ``participant.build_engine_participant`` instead and is a CALLER of the phase
#: loop without being an IMPORTER of its vocabulary. This list is where the signature left it.
_AUTHORISED_PHASE_LOOP_IMPORTERS: tuple[list[str], ...] = (
    [],
    ["domain/backtest/portfolio_engine.py"],
    ["domain/backtest/participant.py", "domain/backtest/portfolio_engine.py"],
)

#: The ONE production caller the `C4` wiring authorises, by exact path. A second caller — a
#: route, a command, a second job — is still a red build. This replaces the pre-`C4`
#: ``callers == []``: the invariant is genuinely weaker (*no production REQUEST reaches the
#: loop, because its only caller is flag-guarded*) and a text scan cannot prove reachability,
#: which is why the behavioural modules named in this module's docstring land in the same
#: slice. Narrowed, never deleted.
_AUTHORISED_LOOP_CALLERS = ["application/jobs/backtest_engine.py"]

#: Same, for the Result projection. It is listed separately from the loop's allowlist on
#: purpose: they happen to name the same module today, and collapsing them into one constant
#: would make a future divergence unstateable.
_AUTHORISED_PROJECTION_CALLERS = ["application/jobs/backtest_engine.py"]

#: Every public way INTO the phase loop. The caller scan below is a text search, so it
#: covers exactly the names listed here. ``iter_portfolio`` (C2) is the tick-drivable form
#: and is the one a worker would reach for first, so omitting it would leave the loop's
#: most likely production entry point unguarded.
_LOOP_ENTRY_POINTS = ("run_portfolio", "iter_portfolio")


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

    **The name is now historical; the assertion is not.** As of `C4` a production path DOES
    reach the loop — the worker's shared branch. What holds the containment closed is no
    longer the absence of a caller but the pair of conditions that caller sits behind:
    ``shared_allocation_is_executable()`` (``future_dev``, so False) AND
    ``shared_allocation_requested(...)``. Either conjunct alone would silently re-price every
    independent composite Result, which is why the worker states them in one predicate and
    why this test asserts the worker names the flag at all.

    The adapter the pre-`C4` version of this docstring called "the honest gap" landed at `C3`
    (``domain/backtest/participant.py``): the stepper's phases BOOK where ``ItemParticipant``
    needs them to DESCRIBE, and that translation is the whole of it. The stepper itself
    shipped earlier still, as PR #602 — ADR §12's own AMENDMENT supersedes the paragraph
    above it that says ADIM 16 was SKIPPED, and this docstring said otherwise until now.

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

    # The containment, as `C4` leaves it: the loop has exactly ONE authorised caller.
    # BOTH entry points are named. Greping only for ``run_portfolio`` would let a production
    # module drive the whole phase loop — P10 included — through ``iter_portfolio`` with this
    # assertion still green, which is exactly the wiring this gate exists to bound.
    callers = sorted(
        str(path.relative_to(_SRC))
        for path, text in sources.items()
        if path != loop
        and any(f"{name}(" in text or f"import {name}" in text for name in _LOOP_ENTRY_POINTS)
    )
    assert callers == _AUTHORISED_LOOP_CALLERS, (
        f"the phase loop gained an UNAUTHORISED production caller: {callers}"
    )

    worker = sources[_SRC / "application" / "jobs" / "backtest_engine.py"]
    # UNCHANGED by `C4`, and they must stay green: the independent-mode fold and its item
    # loop have to SURVIVE the wiring. Deleting either is the silent re-price of every
    # independent composite Result — no flag, no version bump, nothing a reader could see.
    assert "combine_item_runs(" in worker
    # EXACTLY once, not merely present. These are text scans, so a second copy of the loop
    # header anywhere in the worker — another loop, or a comment quoting it — satisfies a
    # bare ``in`` check while the real loop is gone. That is not hypothetical: `C4`'s own
    # shared-branch helper looped with the same variable name, and a negative control that
    # deleted the independent loop left this assertion GREEN. Counting pins the shadow as
    # well as the deletion.
    assert worker.count("for prepared in prepared_items:") == 1, (
        "the independent item loop's header appears more than once (or not at all); a "
        "second copy blunts this assertion into proving nothing"
    )
    # The assertion that REPLACES "nothing calls it". A text scan cannot prove that no
    # request reaches the loop; what it can prove is that the one authorised caller reads
    # the containment flag at the branch rather than caching or re-deriving the answer.
    #
    # MEASURED LIMIT, do not read this line as more than it is (the finding #800 handed
    # forward, reproduced here by negative control): deleting the conjunct from
    # ``_use_unified_clock``'s return expression leaves this assertion GREEN, because the
    # symbol is also named in that function's own docstring. A substring catches the guard
    # being deleted WHOLESALE, never its being THINNED. The load-bearing pins for the two
    # conjuncts are elsewhere and both went red under that control:
    # ``test_shared_allocation_two_world_gate.py``'s
    # ``test_the_worker_fold_never_consults_the_capability_flag`` (an ``ast`` walk, which
    # sees Call nodes and not prose) and ``test_shared_clock_branch_predicate.py``'s
    # ``test_the_shipped_world_never_takes_the_branch`` (behavioural). Strengthen those,
    # never this one, if the axis needs more.
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

    # The worker's INDEPENDENT Result still comes from per-item runs folded sequentially.
    # That half is what the projection could have replaced silently, so it is asserted here
    # too rather than only in the loop's test.
    worker = sources[_SRC / "application" / "jobs" / "backtest_engine.py"]
    assert "combine_item_runs(" in worker
    assert "shared_allocation_is_executable" in worker


#: The version `C7` bumped to. Recorded so the NEXT bump can be required rather than
#: remembered. This is the one literal in this file that is allowed to be compared against
#: ``ENGINE_VERSION`` for INEQUALITY, and only in the lifted world.
_C7_ENGINE_VERSION = "backtest-engine-v18-a16-manifest-policy-provenance"


def test_the_containment_flag_and_engine_version_are_both_lifted() -> None:
    """§6 condition 6 / ADR §14 A15 — **the lift happened at ADIM 20 (`C9`), and this pin is
    the record of it.**

    Renamed from ``..._are_both_untouched``. Every earlier slice found this test asserting
    that NOTHING had moved, and that was the tripwire's whole value: the module docstring says
    it is *"written to FAIL the day someone lifts the flag, bumps the engine version or closes
    the last gap without the rest of the matrix, which is precisely when a human must re-read
    §14 rather than trust a green suite."* It fired on exactly that day. A human re-read §14,
    Gate 2 was signed (`G10`, 2026-08-28), and the pin was moved as the ACT of lifting rather
    than loosened to get a green suite — it still pins two exact literals and still fails on
    any drift of either.

    A15 is discharged HERE and not before: `C7`'s bump was spent on a RECORD change (A16), so
    a contained-era Result and a unified-clock Result would have shared an ``execution_key``
    namespace had `C9` not bumped again. The sibling test below enforces exactly that and is
    what makes this line's new value non-negotiable rather than cosmetic."""
    assert SHARED_ALLOCATION_STATUS == "active_v1"
    assert shared_allocation_is_executable() is True
    # ADR §10.3's proposed name, taken verbatim rather than invented — the version string is
    # a namespace, and inventing one here would have made the namespace this slice's opinion.
    assert ENGINE_VERSION == "backtest-engine-v18-unified-clock-portfolio"
    assert ENGINE_VERSION != _C7_ENGINE_VERSION
    assert "unified-clock multi-item co-simulation" in SHARED_ALLOCATION_DEPENDENCY


def _lift_reuses_the_c7_namespace(status: str, engine_version: str) -> bool:
    """True when containment is lifted while the engine still carries `C7`'s version."""
    return status == "active_v1" and engine_version == _C7_ENGINE_VERSION


def test_lifting_containment_requires_a_second_engine_version_bump() -> None:
    """A15 is NOT discharged by `C7`'s bump, and this is what stops it being assumed to be.

    `C7` bumped ``ENGINE_VERSION`` for a RECORD change (the A16 policy provenance), not for
    an executed-behaviour change. A15 exists for a different failure: a CONTAINED-era
    Result must never be idempotently reused for a UNIFIED-CLOCK re-RUN. Only a bump in the
    commit that lifts ``SHARED_ALLOCATION_STATUS`` can prevent that, because until the lift
    the two eras produce the same numbers and afterwards they do not.

    The namespace shift is a one-shot resource and `C7` spent one. If `C9` lifts the flag
    without spending another, a contained-era Result and a unified-clock Result share an
    ``execution_key`` namespace — silently, with no test to say so. Hence this.

    **Written as a predicate, not as an ``if``.** A bare ``if lifted: assert ...`` is
    vacuously green today, so it would prove nothing about whether it WORKS until the day
    it had to. The four corners below exercise the lifted world as an INPUT, which is the
    same move ``test_shared_clock_branch_predicate.py`` makes for ``_use_unified_clock``:
    an ``and`` short-circuits, so a test of the compound answer passes with either conjunct
    broken.
    """
    # 1. The predicate itself, on all four corners — this is the non-vacuous half.
    assert _lift_reuses_the_c7_namespace("active_v1", _C7_ENGINE_VERSION) is True
    assert _lift_reuses_the_c7_namespace("active_v1", "backtest-engine-v19-unified") is False
    assert _lift_reuses_the_c7_namespace("future_dev", _C7_ENGINE_VERSION) is False
    assert _lift_reuses_the_c7_namespace("future_dev", "backtest-engine-v19-unified") is False

    # 2. Applied to the tree as it stands. Today the flag is down, so this passes on the
    #    third corner. The day `C9` flips it without bumping, it passes on the FIRST — and
    #    turns red here, in the file a human must re-read before lifting.
    assert not _lift_reuses_the_c7_namespace(SHARED_ALLOCATION_STATUS, ENGINE_VERSION), (
        "containment was lifted while ENGINE_VERSION still carries `C7`'s string. A15 "
        "requires the lift to shift the execution_key namespace itself; `C7`'s bump was "
        "spent on the A16 manifest record and does not discharge it. Bump ENGINE_VERSION "
        "in the same commit that lifts the flag, and regenerate the golden baseline."
    )


#: ADR 0002 §16 makes flag-flip approval (`G10`, "Gate 2") a GATE, and the ordered plan's
#: `C9` row spells its stop condition literally: *"Any of the 22 preconditions unmet, or
#: **G10 unsigned** -> do not open this PR."* Measured at ADIM 130: the whole `backend/`
#: tree contained ZERO occurrences of `G10` or "Gate 2", so that stop condition was
#: enforced by NOBODY — `C9` could lift the flag with Gate 2 still deferred and every
#: test would stay green. Reading the decision record from a test is this repo's existing
#: idiom for exactly this shape (`tests/contract/test_a11y_audit_prep_contract.py` reads a
#: worksheet, `tests/unit/test_acceptance_semantic_map.py` reads the acceptance ledger).
_GATE2_DECISION = (
    pathlib.Path(__file__).resolve().parents[4]
    / "docs"
    / "decisions"
    / "closure_g10_containment_lift_gate2_2026-08-26.md"
)

#: The SECOND request's box. The first request is signed `B — ERTELE` and is history; the
#: gate must read the live box, not the archived one, so it is anchored to that heading.
_GATE2_REQUEST_HEADING = "## Yeniden talep — Gate 2,"
_GATE2_OPTION = re.compile(r"^([\u2611\u2610]) \*\*([ABC]) — ", re.MULTILINE)


def _gate2_is_approved(document: str) -> bool:
    """Is Gate 2 APPROVED in this decision record?

    **Fail-closed, deliberately (K-07's shape).** Every way of not being able to answer —
    the section deleted, the option lines renamed, two options ticked at once — raises
    instead of returning ``False``. Returning ``False`` would look identical to "deferred"
    and would keep the suite green on a mangled record, which is the failure mode a gate
    exists to prevent. Only a record that parses cleanly and ticks exactly `A` is approval.
    """
    _, marker, rest = document.partition(_GATE2_REQUEST_HEADING)
    if not marker:
        raise AssertionError(
            f"{_GATE2_DECISION.name} no longer contains a {_GATE2_REQUEST_HEADING!r} "
            "section. Gate 2's live request box is what this gate reads; without it the "
            "`C9` stop condition is unenforced again."
        )
    section = rest.split("\n## ")[0]
    options = _GATE2_OPTION.findall(section)
    letters = [letter for _, letter in options]
    if letters != ["A", "B", "C"]:
        raise AssertionError(
            "Gate 2's request box no longer offers exactly A/B/C in order; parsed "
            f"{letters!r}. The box shape is the gate's input — change it and this gate "
            "must be changed with it, deliberately."
        )
    ticked = [letter for mark, letter in options if mark == "\u2611"]
    if len(ticked) > 1:
        raise AssertionError(
            f"Gate 2's request box ticks more than one option ({ticked!r}). An ambiguous "
            "signature is not a signature."
        )
    return ticked == ["A"]


def _lift_without_gate2(status: str, document: str) -> bool:
    """True when containment is lifted while Gate 2 has not been approved."""
    return status == "active_v1" and not _gate2_is_approved(document)


def _request_box(*ticked: str) -> str:
    """A synthetic Gate 2 request box, for exercising the predicate on both worlds."""
    lines = [
        ("\u2611" if letter in ticked else "\u2610")
        + " **"
        + letter
        + " — "
        + letter.lower()
        + "**"
        for letter in "ABC"
    ]
    return _GATE2_REQUEST_HEADING + " ikinci istek\n\n" + "\n".join(lines) + "\n"


def test_lifting_containment_requires_gate2_approval() -> None:
    """ADR §16 Gate 2 (`G10`), enforced instead of remembered.

    `G10` was requested on 2026-08-26 and signed **`B` — ERTELE**: deferred, not refused,
    with a written re-request condition of three clauses. Two were already discharged then;
    the third (`G14`'s `B` half shipped and `#544` closed) was discharged on 2026-08-27 by
    ADIM 124. So the deferral's own condition is spent — and nothing anywhere would have
    noticed, because no test knew Gate 2 existed.

    **Written as a predicate, not as an ``if``** — the same move
    :func:`test_lifting_containment_requires_a_second_engine_version_bump` makes, and for
    the same reason: ``if lifted: assert ...`` is vacuously green today and would prove
    nothing about whether it works on the one day it must.

    It goes one step further than its sibling in two places, both of which were needed:

    * ``and`` short-circuits, so applying the predicate to a tree whose flag is down would
      never parse the real record — the fail-closed half would lie dormant until the lift.
      The real document is therefore parsed UNCONDITIONALLY, today, on every run.
    * The lifted world is then exercised against the REAL record rather than only against
      synthetic ones, which is possible without touching ``capability.py`` (that file is
      `C9`'s) because the status is an INPUT here.

    This gate does not decide anything. If the owner ticks `A`, it goes quiet on its own —
    there is no literal in this file to update.
    """
    approved_doc = _request_box("A")
    deferred_doc = _request_box()

    # 1. The predicate on all four corners — the non-vacuous half.
    assert _lift_without_gate2("active_v1", deferred_doc) is True
    assert _lift_without_gate2("active_v1", approved_doc) is False
    assert _lift_without_gate2("future_dev", deferred_doc) is False
    assert _lift_without_gate2("future_dev", approved_doc) is False

    # 2. Fail-closed, proven rather than asserted in prose: three ways of being unable to
    #    answer, none of which may quietly read as "deferred" (or as "approved").
    for mangled in (
        "no request box at all",  # the section was deleted
        _request_box("A", "B"),  # two options ticked at once
        _request_box().replace("\u2610 **B — b**\n", ""),  # an option went missing
    ):
        with pytest.raises(AssertionError):
            _gate2_is_approved(mangled)

    # 3. The real record, parsed UNCONDITIONALLY so the fail-closed half runs today rather
    #    than for the first time on the day of the lift.
    document = _GATE2_DECISION.read_text(encoding="utf-8")
    approved = _gate2_is_approved(document)

    # 4. The lifted world against the REAL record — no flag is flipped to ask this.
    assert _lift_without_gate2("active_v1", document) is (not approved)

    # 5. And the tree as it stands.
    assert not _lift_without_gate2(SHARED_ALLOCATION_STATUS, document), (
        "containment was lifted while ADR §16 Gate 2 (`G10`) is not approved. The ordered "
        "plan's `C9` stop condition is explicit: G10 unsigned -> do not open this PR. Tick "
        f"option A in the request box of {_GATE2_DECISION.name} first — this gate reads it."
    )


def test_the_manifest_carries_none_of_the_policy_fields_the_lift_requires() -> None:
    """INVERTED at `C7`: A16 is discharged, so this now asserts the fields are PRESENT.

    Was: *the shipped manifest carries none of them*. That was true for as long as A16 was
    open — ``execution/provenance.py`` could build the block and nothing called it. `C7`
    closed the gap: ``domain/backtest/manifest.py`` now declares the four policy versions
    as literals and pins them into both the manifest body and ``execution_content``.

    **The name is deliberately NOT changed**, on this file's own stated convention: it is
    cited from three frozen evidence documents (``unified_portfolio_oracle_acceptance.md``,
    ``closure_w0_shared_portfolio_2026-08-13.md``,
    ``final_closure_ordered_plan_2026-08-13.md``), and renaming it would break those
    citations to fix a sentence this docstring already corrects.

    **This is a re-aim, not a relaxation.** The gate's job is to fail the day someone
    closes a gap without the rest of §14, so deleting the assertion when the gap closed
    would have spent the tripwire. What it guards now is the opposite edge: the fields must
    stay, and they must stay CORRECT. Their agreement with the modules that own the
    policies is proved separately in ``tests/unit/test_a16_manifest_policy_parity.py``,
    because that claim needs to import the contained layer and this package must not.
    """
    manifest = (_SRC / "domain" / "backtest" / "manifest.py").read_text()
    for field in (
        "engine_allocation_policy_version",
        "clock_policy_version",
        "arbitration_policy_version",
        "mark_staleness_policy",
    ):
        assert field in manifest, (
            f"{field!r} left the shipped manifest; A16 was discharged at `C7` and a "
            "Result that cannot state its policy provenance is the gap that closed"
        )


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

    # `C4` must not have re-entered this list through the back door. The worker is a CALLER
    # (asserted above) and must never become an IMPORTER of the loop's vocabulary — which is
    # the whole reason ``participant.build_engine_participant`` exists, and the assertion
    # that keeps that reason from decaying into a comment.
    assert "application/jobs/backtest_engine.py" not in live
