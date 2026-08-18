"""P-E6 / C8 — the containment gate, exercised in BOTH values of the flag.

Every containment test shipped to date asserts the ``future_dev`` world. Measured on
``0f0651d``: ``SHARED_ALLOCATION_STATUS`` is set to ``"active_v1"`` in exactly ONE backend
test (``test_backtest_portfolio_mode.py:160``) and that test exists to prove the Result
resolver **ignores** the flag. So no test anywhere exercises the three production readers

* ``domain/allocation/rules.py:154``            — the Ready Check blocker
* ``application/commands/backtest_run.py:542``  — the run-admission guard
* ``application/queries/allocation_plan.py:59`` — the capability block the UI renders

in the world the lift creates. The gate was a ONE-WORLD gate: the act of flipping the flag
would have been the first time anyone learned what those three surfaces do.

This module is that second world. It does not weaken a single ``future_dev`` pin — those
are the gate, and ADR §14 A15 / the ordered plan's ``C9`` row update them deliberately, as
the act of lifting. It adds the other half, so a lift PR reads as a diff against measured
behaviour instead of against nothing.

**The flag is forced by a test-owned fixture that production cannot reach**, which
:func:`test_containment_is_not_runtime_configurable` asserts structurally: there is no env
var, no setter and no second assignment in ``backend/src``. A configurable containment is
not a containment.

Infra-free: every function under test is pure, matching
``test_shared_allocation_containment.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from entropia.domain.allocation import capability
from entropia.domain.allocation.capability import (
    LEGACY_SEQUENTIAL_RESULT_NOTE,
    SHARED_ALLOCATION_MESSAGE,
    SHARED_ALLOCATION_REMEDIATION,
    shared_allocation_capability_view,
    shared_allocation_is_executable,
    shared_allocation_requested,
)
from entropia.domain.allocation.enums import AllocationIssueCode as AllocCode
from entropia.domain.backtest.execution.portfolio import (
    COMPOSITION_CURVE_WARNING,
    combine_item_runs,
)
from entropia.domain.backtest.portfolio_mode import (
    PORTFOLIO_MODE_LEGACY_SEQUENTIAL,
    portfolio_simulation_context,
)
from tests.unit.test_shared_allocation_containment import (
    _capital_execution,
    _item_run,
    _plan,
    _refs,
)

_SRC = Path(__file__).resolve().parents[2] / "src" / "entropia"
_P0 = Decimal("10000.00")


# --------------------------------------------------------------------------- #
# The test-owned lift fixture                                                  #
# --------------------------------------------------------------------------- #
@contextmanager
def _lifted(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Force the ``active_v1`` world for the duration of the block.

    Patching the module global (not a re-imported copy) is what makes this reach every
    reader: ``rules.py`` and ``backtest_run.py`` hold a reference to the *function*
    ``shared_allocation_is_executable``, whose ``__globals__`` IS this module's dict, so
    they observe the patch without importing anything from here.
    """
    with monkeypatch.context() as patch:
        patch.setattr(capability, "SHARED_ALLOCATION_STATUS", "active_v1")
        yield


def _validate(*, enabled: bool, plan_overrides: dict[str, Any] | None = None) -> list[Any]:
    """``validate_allocation`` issue codes, in emission order."""
    from entropia.domain.allocation.rules import validate_allocation

    plan = _plan(enabled=enabled)
    if plan_overrides:
        plan = plan.model_copy(update=plan_overrides)
    issues, _derived = validate_allocation(plan, item_refs=_refs())
    return [str(issue.code) for issue in issues]


# --------------------------------------------------------------------------- #
# Anti-vacuity — without this, every test below could be a silent no-op        #
# --------------------------------------------------------------------------- #
def test_the_lift_fixture_actually_moves_the_world(monkeypatch: pytest.MonkeyPatch) -> None:
    """A two-world test whose fixture does not move the world is a one-world test twice.

    Asserted through the PUBLIC reader the production call sites use, not through the
    constant, so a future indirection (a cache, a settings object) cannot make the fixture
    inert while this file keeps passing.
    """
    assert shared_allocation_is_executable() is False

    with _lifted(monkeypatch):
        assert capability.SHARED_ALLOCATION_STATUS == "active_v1"
        assert shared_allocation_is_executable() is True

    # ... and the world is restored, so no test after this one inherits a lifted flag.
    assert capability.SHARED_ALLOCATION_STATUS == "future_dev"
    assert shared_allocation_is_executable() is False


# --------------------------------------------------------------------------- #
# Reader 1 — the Ready Check blocker (rules.py:154)                            #
# --------------------------------------------------------------------------- #
def test_the_flag_gates_exactly_one_readiness_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lifting removes the containment blocker and NOTHING else.

    The risk this pins is not that the blocker survives the lift — it is that the lift
    quietly takes the sleeve validation with it. ``rules.py`` emits the containment blocker
    first and then falls through to the §5.1 field checks; had any of those checks been
    written inside the ``if not shared_allocation_is_executable():`` branch, a lifted build
    would validate an invalid plan as clean. This compares the two worlds' full issue lists
    on the SAME deliberately-invalid plan, so that regression is a red test and not a
    financial surprise.
    """
    invalid = {"reserve_cash_percent": Decimal("140")}

    contained = _validate(enabled=True, plan_overrides=invalid)
    with _lifted(monkeypatch):
        lifted = _validate(enabled=True, plan_overrides=invalid)

    blocker = str(AllocCode.SHARED_MODE_NOT_IN_BUILD)
    assert contained[0] == blocker, "the containment blocker must LEAD (it is the one to fix)"
    assert blocker not in lifted, "a lifted build must not advertise a blocker it does not apply"
    # The one and only difference between the two worlds is that lead blocker.
    assert lifted == contained[1:]
    # ... and the invalid field is still caught in BOTH worlds, which is the whole point.
    assert str(AllocCode.RESERVE_OUT_OF_RANGE) in contained
    assert str(AllocCode.RESERVE_OUT_OF_RANGE) in lifted


def test_independent_mode_is_identical_in_both_worlds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Doc 13 §1.1. The lift is about SHARED capital; independent mode must not feel it."""
    assert _validate(enabled=False) == []
    with _lifted(monkeypatch):
        assert _validate(enabled=False) == []


# --------------------------------------------------------------------------- #
# Reader 2 — the run-admission guard (backtest_run.py:542)                     #
# --------------------------------------------------------------------------- #
def test_the_request_predicate_is_flag_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    """``shared_allocation_requested`` answers "did the USER ask?" — never "may they?".

    The guard is a conjunction: ``not is_executable() and requested(snapshot)``. If the
    request half ever started consulting the flag, the conjunction would collapse to a
    constant and the containment would become fail-OPEN without any test noticing. Both
    halves are pinned here as independent axes.
    """
    snapshots: tuple[Any, ...] = (
        _capital_execution(enabled=True),
        _capital_execution(enabled=False),
        {"enabled": True},
        {"enabled": False},
        {},
        None,
        "not-a-dict",
    )
    contained = [shared_allocation_requested(s) for s in snapshots]
    with _lifted(monkeypatch):
        lifted = [shared_allocation_requested(s) for s in snapshots]

    assert contained == lifted
    assert contained == [True, False, True, False, False, False, False]


def test_the_admission_guard_refuses_in_exactly_one_of_the_four_cells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 2x2 truth table of (world) x (requested), as the guard composes it.

    Spelled as the guard's own expression rather than as a mock of it, so a change to the
    conjunction at ``backtest_run.py:542`` shows up here. Only the contained-and-requested
    cell refuses; in particular a lifted build refuses NOTHING, which is exactly why the
    preconditions and not the flag are what protect the numbers.

    **Both conjuncts are asserted per cell, not just the composed verdict.** The guard is an
    ``and``, so in the lifted world it short-circuits on the first term and never evaluates
    the second — which means a composed-only assertion is blind to any change in the request
    half of two of the four cells. This test's own negative control demonstrated that: making
    ``shared_allocation_requested`` flag-aware left the composed table entirely green. The
    per-conjunct rows below are what close it.
    """

    def cell(snapshot: Any) -> tuple[bool, bool, bool]:
        executable, requested = (
            shared_allocation_is_executable(),
            shared_allocation_requested(snapshot),
        )
        return executable, requested, (not executable and requested)

    shared, independent = _capital_execution(enabled=True), _capital_execution(enabled=False)

    #        (is_executable, requested, refuses)
    assert cell(shared) == (False, True, True)
    assert cell(independent) == (False, False, False)
    with _lifted(monkeypatch):
        assert cell(shared) == (True, True, False)
        assert cell(independent) == (True, False, False)


# --------------------------------------------------------------------------- #
# The measured reason the flag is NOT the feature                              #
# --------------------------------------------------------------------------- #
def test_lifting_the_flag_alone_still_folds_the_sequential_curve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**The finding this slice exists to pin.** The flag is a refusal, not an engine.

    Measured on ``0f0651d``: the worker replays each item independently
    (``jobs/backtest_engine.py:299``) and folds the finished runs with
    ``combine_item_runs`` (``:364``). It reads ``capital_execution`` only to choose the
    pool's starting capital and to label the composition ``shared_pool`` — it never
    consults ``shared_allocation_is_executable``. ``_use_unified_clock`` does not exist on
    this commit, and neither does ``_EngineParticipant``.

    So a lift performed today would remove the Ready Check blocker and the admission guard
    and then compute the shared-capital Result with the sequential approximation: the same
    5000 drawdown against a true 3000, which
    ``test_shared_allocation_containment.py::test_composite_portfolio_curve_is_not_time_ordered``
    measures in the contained world. The containment message calls those numbers wrong; the
    flag alone does not make them right. That is the difference between lifting the
    containment and delivering the feature, and it is why ``C9`` is last and not first.
    """
    a = _item_run("a", [("2024-01-01T01:00:00Z", "3000.00"), ("2024-01-01T04:00:00Z", "-2000.00")])
    b = _item_run("b", [("2024-01-01T02:00:00Z", "-3000.00"), ("2024-01-01T03:00:00Z", "3000.00")])

    with _lifted(monkeypatch):
        combined = combine_item_runs(
            [a, b],
            portfolio_initial_capital=_P0,
            execution_key="k",
            item_count=2,
            shared_pool=True,
        )

    stamps = [p.timestamp for p in combined.equity_points if p.timestamp]
    assert stamps != sorted(stamps), "a lifted flag must not be mistaken for a unified clock"
    # The wrong number, still wrong, in the world where nothing refuses it any more.
    assert combined.summary["max_drawdown"] == Decimal("5000.00")
    # ... and the fold still tells the truth about itself, because it never read the flag.
    assert COMPOSITION_CURVE_WARNING in combined.diagnostics["warnings"]
    assert combined.diagnostics["composition"]["capital_allocation"] == "shared_pool"


def test_the_worker_fold_never_consults_the_capability_flag() -> None:
    """Why the test above holds, stated structurally so it cannot drift silently.

    A behavioural test alone would keep passing if the worker grew a flag branch that
    happened not to change this fixture's numbers. The source-level assertion is the one
    that survives that. When ``C4`` lands ``_use_unified_clock``, this test is the file that
    must be updated — deliberately, as part of wiring the branch.
    """
    worker = (_SRC / "application" / "jobs" / "backtest_engine.py").read_text(encoding="utf-8")
    for absent in (
        "shared_allocation_is_executable",
        "SHARED_ALLOCATION_STATUS",
        "_use_unified_clock",
        "run_portfolio",
    ):
        assert absent not in worker, f"{absent!r} reached the worker — re-read this docstring"


# --------------------------------------------------------------------------- #
# Historical compatibility (A19) — in BOTH worlds                              #
# --------------------------------------------------------------------------- #
def test_a_stored_sequential_result_reads_identically_in_both_worlds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0002 §10.4 / doc 13 §14 test 19, from the Result read path.

    ``test_backtest_portfolio_mode.py`` proves the resolver ignores the flag. This proves
    the consequence a reader actually meets: the full read-time context of an
    already-persisted sequential Result — mode, note and the explicit
    ``comparable_with_unified_clock`` verdict — is byte-identical either side of the lift.
    A Result written before the containment lifted keeps saying what it is, forever.
    """
    a = _item_run("a", [("2024-01-01T01:00:00Z", "3000.00")])
    b = _item_run("b", [("2024-01-01T02:00:00Z", "-1000.00")])
    stored = combine_item_runs(
        [a, b], portfolio_initial_capital=_P0, execution_key="k", item_count=2, shared_pool=True
    )
    diagnostics = stored.diagnostics

    contained = portfolio_simulation_context({}, diagnostics)
    with _lifted(monkeypatch):
        lifted = portfolio_simulation_context({}, diagnostics)

    assert contained == lifted
    assert contained["mode"] == PORTFOLIO_MODE_LEGACY_SEQUENTIAL
    assert contained["note"] == LEGACY_SEQUENTIAL_RESULT_NOTE
    # Stated, not left to inference: a sequential drawdown and a unified drawdown are
    # different quantities, and a lifted build must keep saying so about old rows.
    assert contained["comparable_with_unified_clock"] is False


# --------------------------------------------------------------------------- #
# Reader 3 — the capability block (allocation_plan.py:59) — a MEASURED DEFECT  #
# --------------------------------------------------------------------------- #
def test_the_capability_texts_do_not_follow_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """CHARACTERIZATION — this pins a defect, and ``C9`` owns fixing it.

    ``shared_allocation_capability_view`` derives ``status`` and ``available`` from the
    flag but returns ``message``, ``remediation`` and ``dependency`` as unconditional
    constants. Measured in the lifted world, the published block says both things at once:

        ``available: true`` + "Shared capital allocation is not available in this build."
        + "Turn the Portfolio Allocation toggle off ..." + "re-opens when the
        unified-clock multi-item co-simulation lands" (the thing that just landed)

    Today's Portfolio page is safe from it: ``Portfolio.tsx:358`` gates all three strings
    behind ``!capability.available``, so nothing contradictory is rendered. But the block
    is the published CONTRACT — ``allocation_plan.py`` returns it verbatim by design, on
    the stated principle that the browser renders SERVER state and never re-derives
    availability — and any second consumer that reads ``message`` without first checking
    ``available`` would print a falsehood.

    Pinned as a characterization test, on the ``#559`` precedent: it records what ships so
    the fix is a deliberate, reviewable change rather than a silent one. When ``C9`` makes
    these three strings flag-aware, THIS test is the one that must be updated, and its
    failure is the reminder that the texts are part of the lift.
    """
    contained = shared_allocation_capability_view()
    with _lifted(monkeypatch):
        lifted = shared_allocation_capability_view()

    # The two fields that DO follow the flag.
    assert (contained["status"], contained["available"]) == ("future_dev", False)
    assert (lifted["status"], lifted["available"]) == ("active_v1", True)

    # The three that do not — and the contradiction they produce, stated as an assertion.
    assert lifted["message"] == contained["message"] == SHARED_ALLOCATION_MESSAGE
    assert lifted["remediation"] == contained["remediation"] == SHARED_ALLOCATION_REMEDIATION
    assert lifted["dependency"] == contained["dependency"]
    assert lifted["available"] is True and "not available in this build" in lifted["message"]
    assert "toggle off" in lifted["remediation"]


# --------------------------------------------------------------------------- #
# The containment must not be configurable                                     #
# --------------------------------------------------------------------------- #
def test_containment_is_not_runtime_configurable() -> None:
    """The lift is a reviewed source edit, not a deployment knob.

    The ordered plan requires the lift fixture to be test-owned and unreachable from
    ``backend/src``. The other half of that requirement is asserted here: production
    assigns the flag exactly once — its definition — and reads no environment for it, so
    the only way to reach the world this file exercises is to edit the line and have a
    human review the diff.
    """
    source = (_SRC / "domain" / "allocation" / "capability.py").read_text(encoding="utf-8")
    assignments = [
        line
        for line in source.splitlines()
        if line.startswith("SHARED_ALLOCATION_STATUS") and "=" in line
    ]
    assert assignments == ['SHARED_ALLOCATION_STATUS: SharedAllocationStatus = "future_dev"']
    for knob in ("getenv", "environ", "os.env", "settings", "Settings"):
        assert knob not in source, f"{knob!r} would make the containment a deployment knob"

    # No other production module may assign it either — reading is fine, writing is not.
    writers = [
        str(path.relative_to(_SRC))
        for path in _SRC.rglob("*.py")
        if "SHARED_ALLOCATION_STATUS =" in path.read_text(encoding="utf-8")
    ]
    assert writers == ["domain/allocation/capability.py"]
