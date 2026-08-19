"""`C4` / E5 — the worker's unified-clock branch, and the proof nobody can enter it.

`C4` replaced the containment gate's strongest assertion. Until this slice the phase loop
had **no production caller at all**, and a text scan could prove it: ``assert callers ==
[]``. Now there is exactly one caller — this worker — and the invariant is weaker and
BEHAVIOURAL: *no production **request** can reach the loop, because its only caller is
guarded by ``shared_allocation_is_executable()``, which is ``future_dev``.*

A text scan cannot prove reachability, so P-C2 §C.6 splits the gate in two: the scan is
**narrowed to an authorised-caller allowlist** (never deleted, never loosened) in
``tests/unit/oracles/test_oracle_portfolio_containment_gate.py``, and the reachability
half is these tests. They are what the emptiness assertion used to buy for free.

WHAT THESE TESTS ARE NOT
------------------------
They do not test the shared branch's arithmetic — **nothing in this build can reach it**,
which is the point. `C9` lifts the flag and E6's oracles then prove the numbers. What is
provable today is the fork: which side a real run takes, that both conjuncts of the guard
are load-bearing, and that the cancellation checkpoint the shared branch needs actually
honours a pending cancel.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.jobs.backtest_engine import (
    _TICK_CHECKPOINT_STRIDE,
    _replay_unified_clock,
    _use_unified_clock,
    run_backtest,
)
from entropia.application.queries import backtest_run as backtest_query
from entropia.domain.allocation import capability as capability_mod
from entropia.domain.backtest.enums import BacktestRunState
from entropia.domain.backtest.execution.portfolio import COMPOSITION_CURVE_WARNING
from entropia.domain.backtest.execution.portfolio_projection import (
    ENGINE_KIND as UNIFIED_ENGINE_KIND,
)
from entropia.domain.backtest.portfolio_engine import PortfolioRun
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    BacktestRun,
    DiagnosticArtifact,
    Job,
)
from tests.integration.test_backtest_persistence import (
    USER1,
    _e2e_bars,
    _seed_principals,
    _two_strategy_composition,
)
from tests.integration.test_backtest_run_cancellation import _provisioning_run
from tests.unit.oracles.portfolio_harness import ScriptedItem, _ScriptedParticipant

pytestmark = pytest.mark.integration

#: The sequential fold's own marker. A Result carrying this was assembled by
#: ``combine_item_runs`` from finished per-item runs — it did not walk a merged axis.
SEQUENTIAL_ENGINE_KIND = "v1_bar_replay_composition"


# --------------------------------------------------------------------------- #
# (1) Which side of the fork a REAL run takes                                  #
# --------------------------------------------------------------------------- #


async def test_an_independent_multi_item_run_never_reaches_the_unified_loop(session) -> None:
    """The headline behavioural proof: with the flag as SHIPPED, a real two-Strategy run
    is folded sequentially and the unified branch is not taken.

    Asserted on the Result's own diagnostics rather than by spying on the worker, because
    that is what a user and a reviewer can actually read back. The two paths label
    themselves differently by construction — ``combine_item_runs`` stamps
    ``v1_bar_replay_composition`` and ``project_portfolio_run`` stamps
    ``v1_unified_clock_portfolio`` plus a ``portfolio_loop_version`` — so this cannot pass
    by coincidence: the wrong branch produces a different, named artifact.

    This is the test that would catch the silent re-price §C.5 warns about. If someone
    dropped a conjunct from ``_use_unified_clock``, or deleted the item loop, every
    independent composite Result would start walking a merged axis with no flag, no
    ``ENGINE_VERSION`` bump and nothing visible to the user — and this assertion is what
    turns that into a red build."""
    await _seed_principals(session)
    composition_id, _revisions = await _two_strategy_composition(session, USER1)

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == BacktestRunState.SUCCEEDED.value
    view = await backtest_query.get_backtest_result(session, USER1, result_id=out["result_id"])
    stored = (
        await session.execute(
            select(DiagnosticArtifact).where(
                DiagnosticArtifact.result_id == out["result_id"],
                DiagnosticArtifact.kind == "run_diagnostics",
            )
        )
    ).scalar_one()
    diagnostics: dict[str, Any] = dict(stored.content)

    assert diagnostics.get("engine_kind") == SEQUENTIAL_ENGINE_KIND
    assert diagnostics.get("engine_kind") != UNIFIED_ENGINE_KIND
    # The projection's own provenance block is ABSENT — it is only ever written by the
    # unified path, so its absence is a positive statement about which branch ran.
    assert "portfolio_loop_version" not in str(diagnostics.get("policy_versions", {}))
    # The sequential fold's own disclosure, which the design names as THE marker: it is
    # written by ``combine_item_runs`` for every folded run, shared pool or not, and
    # ``project_portfolio_run`` never emits it (ADR §15). Measured, not assumed — the
    # first draft of this test asserted its ABSENCE on the independent path and was wrong.
    assert COMPOSITION_CURVE_WARNING in diagnostics["warnings"]
    assert diagnostics["composition"]["capital_allocation"] == "independent"

    assert view["summary"]["headline"]["initial_capital"] is not None


# --------------------------------------------------------------------------- #
# (2) BOTH conjuncts of the guard, pinned SEPARATELY                           #
# --------------------------------------------------------------------------- #


def test_the_guard_needs_both_conjuncts_and_the_shipped_build_answers_no(monkeypatch) -> None:
    """``_use_unified_clock`` is an ``and`` — so the TERMS are pinned, not the result.

    Asserting only the shipped ``False`` would pass just as well against a guard that had
    lost either half, because short-circuiting hides the second one. Each row below holds
    one conjunct and varies the other, so a dropped term changes an answer here:

    * flag off + shared requested  -> False   (today's build; the branch is unreachable)
    * flag off + independent       -> False
    * flag ON  + independent       -> False   ← only ``shared_allocation_requested`` says so
    * flag ON  + shared requested  -> True    ← the only combination that routes

    Row three is the one that matters most. Without it, dropping
    ``shared_allocation_requested`` would still leave every assertion green while every
    INDEPENDENT multi-item run silently started walking a merged axis at lift time."""
    shared = {"enabled": True, "config": {"initial_capital": {"amount": "10000"}}}
    independent: dict[str, Any] = {"enabled": False}

    # As shipped: the first conjunct is False, so nothing routes.
    assert capability_mod.SHARED_ALLOCATION_STATUS == "future_dev"
    assert capability_mod.shared_allocation_is_executable() is False
    assert _use_unified_clock(shared) is False
    assert _use_unified_clock(independent) is False
    assert _use_unified_clock(None) is False

    # The second conjunct, isolated: with the flag forced ON, an independent snapshot
    # still must NOT route. This is the assertion the silent re-price would trip.
    #
    # The patch target is the WORKER's own binding, not ``capability``'s. The worker
    # imported the predicate by value (``from ... import shared_allocation_is_executable``),
    # so rebinding it in the capability module would leave ``_use_unified_clock`` calling
    # the original and this test would prove nothing — it would pass while asserting
    # against an unpatched build.
    monkeypatch.setattr(
        "entropia.application.jobs.backtest_engine.shared_allocation_is_executable",
        lambda: True,
    )
    assert _use_unified_clock(independent) is False
    assert _use_unified_clock(None) is False
    assert _use_unified_clock(shared) is True

    # ``monkeypatch`` undoes this at teardown, so the build is contained again for every
    # later test — including the ones in this module that drive a real run.
    monkeypatch.undo()
    assert _use_unified_clock(shared) is False


# --------------------------------------------------------------------------- #
# (3) The checkpoint the shared branch needs (ADR §14 A21)                     #
# --------------------------------------------------------------------------- #


def _ticking_pair() -> list[Any]:
    """Two scripted items on interleaved instants — enough ticks to cross a stride.

    Test-owned participants, deliberately: the shared branch cannot be reached through a
    real run, so the only way to drive :func:`_replay_unified_clock` at all is to hand it
    participants directly. That exercises the DRIVER — the generator protocol, the stride
    and the cancel — which is the half `C4` actually wires; the phase loop's own
    arithmetic is the oracle package's job."""
    hours = [f"2024-01-01T{h:02d}:00:00Z" for h in range(24)]
    return [
        _ScriptedParticipant(
            item=ScriptedItem(item_id="a", share="60", bars=[(ts, "100") for ts in hours[::2]]),
            identity=ScriptedItem(item_id="a", share="60", bars=()).identity(0),
            stream=ScriptedItem(
                item_id="a", share="60", bars=[(ts, "100") for ts in hours[::2]]
            ).stream(0),
        ),
        _ScriptedParticipant(
            item=ScriptedItem(item_id="b", share="40", bars=[(ts, "100") for ts in hours[1::2]]),
            identity=ScriptedItem(item_id="b", share="40", bars=()).identity(1),
            stream=ScriptedItem(
                item_id="b", share="40", bars=[(ts, "100") for ts in hours[1::2]]
            ).stream(1),
        ),
    ]


class _Plan:
    """The capital fields ``_replay_unified_clock`` reads off a resolved allocation."""

    initial_capital = Decimal("10000.00")
    reserve_percent = Decimal("0")
    compound = True


async def test_the_tick_checkpoint_honours_a_pending_cancel_and_writes_no_result(
    session, monkeypatch
) -> None:
    """A21 — a long shared run stays cancellable, and a cancel past it writes NO Result.

    Checkpoint #3 does not survive the shared path: it sits BETWEEN two items' replays and
    the unified loop has no such line. Without this stride a shared run would be
    uncancellable for its whole duration, which is the concrete defect §C.3.9 names.

    The stride is monkeypatched to 1 so the fixture does not need hundreds of ticks. That
    changes WHEN the probe runs, never WHETHER it is wired — the constant is a
    latency/round-trip trade, and the mechanism under test is the driver honouring it."""
    monkeypatch.setattr(
        "entropia.application.jobs.backtest_engine._TICK_CHECKPOINT_STRIDE", 1, raising=True
    )
    admit = await _provisioning_run(session)
    await backtest_cmd.cancel_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.commit()
    job = await session.get(Job, admit["job_id"])
    run = await session.get(BacktestRun, admit["run_id"])
    assert job is not None and run is not None

    outcome = await _replay_unified_clock(
        session,
        job,
        run,
        participants=_ticking_pair(),
        shares={"a": Decimal("60"), "b": Decimal("40")},
        plan=_Plan(),
        capital_execution={"enabled": True},
        strategy_item_count=2,
    )
    await session.commit()

    # It stopped at the checkpoint rather than returning a finished run.
    assert not isinstance(outcome, PortfolioRun)
    assert outcome["state"] == BacktestRunState.CANCELLED.value
    assert outcome["result_id"] is None
    assert run.result_id is None
    # doc 15 §16 — a CANCELLED run produces no BacktestResult. The projection and
    # ``create_result`` both sit AFTER this return, which is what makes that true.
    results = await session.scalar(select(func.count()).select_from(BacktestResult))
    assert results == 0


async def test_the_driver_returns_the_finished_run_when_no_cancel_is_pending(session) -> None:
    """The other half: with nothing pending, the generator is exhausted and its RETURN
    VALUE comes back — not ``None``.

    Worth its own test because the bug is silent and specific: a plain ``for`` loop over a
    generator DISCARDS what it returns, and the assembled ``PortfolioRun`` is exactly that
    value. A driver written that way would hand the worker ``None``, and the failure would
    surface far downstream as a projection error rather than as a wiring mistake."""
    admit = await _provisioning_run(session)
    job = await session.get(Job, admit["job_id"])
    run = await session.get(BacktestRun, admit["run_id"])
    assert job is not None and run is not None

    outcome = await _replay_unified_clock(
        session,
        job,
        run,
        participants=_ticking_pair(),
        shares={"a": Decimal("60"), "b": Decimal("40")},
        plan=_Plan(),
        capital_execution={"enabled": True},
        strategy_item_count=2,
    )

    assert isinstance(outcome, PortfolioRun)
    # It really walked the merged axis: 24 hourly instants across the two interleaved
    # items, time-ordered by construction (ADR §14 A5).
    assert len(outcome.ticks) == 24
    assert list(outcome.instants) == sorted(outcome.instants)
    assert _TICK_CHECKPOINT_STRIDE >= 1
