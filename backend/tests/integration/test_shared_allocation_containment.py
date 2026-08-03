"""ADIM 3 — shared capital allocation containment, end to end (doc 13, 14, 15).

Shared capital does not execute in this build: the engine replays each composition
item independently and folds the finished runs in pin order, so there is no
per-timestamp portfolio valuation snapshot and the composite equity curve is not
even time-ordered (proved in ``tests/unit/test_shared_allocation_containment.py``).
Until the unified-clock co-simulation lands, an enabled plan must never produce a
Backtest Result.

Covers: (1) Ready Check reports the typed blocker with its remediation; (2) run
admission refuses and leaves NO run/manifest/job behind; (3) the admission guard
holds even when the Ready Check evaluation is bypassed; (4) independent mode is
untouched and still runs to a Result; (5) the Agent line sees the same refusal;
(6) an already-persisted shared-pool Result stays readable, unmodified.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.jobs import agent_tools
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.queries import backtest_run as backtest_query
from entropia.domain.agent_lab.enums import ALPHA_AGENT_ID, RuntimeMode, RuntimeStatus
from entropia.domain.allocation.capability import (
    SHARED_ALLOCATION_MESSAGE,
    SHARED_ALLOCATION_REMEDIATION,
)
from entropia.infrastructure.postgres.models import (
    AgentRuntime,
    BacktestResult,
    BacktestRun,
    BacktestRunManifest,
    DiagnosticArtifact,
    Job,
)
from entropia.shared.errors import ReadinessBlockedError
from tests.integration.test_backtest_persistence import (
    USER1,
    _count,
    _e2e_bars,
    _enable_allocation,
    _ready_composition,
    _seed_principals,
)

pytestmark = pytest.mark.integration

_BLOCKER = "ALLOCATION_SHARED_MODE_NOT_IN_BUILD"
_CURVE_WARNING = "portfolio_curve_sequential_not_unified_clock"


# --------------------------------------------------------------------------- #
# (1) Ready Check                                                              #
# --------------------------------------------------------------------------- #


async def test_ready_check_reports_the_typed_blocker_with_remediation(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    await _enable_allocation(session, USER1, composition_id, amount="50000.00")

    report = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    assert report["state"] == "not_ready"
    assert report["summary"]["allocation_enabled"] is True
    issue = next(i for i in report["issues"] if i["code"] == _BLOCKER)
    # Doc 14 §9.1: code + severity + scope + field_path + message + remediation.
    assert issue["severity"] == "blocker"
    assert issue["scope"] == "portfolio_allocation"
    assert issue["field_path"] == "enabled"
    assert issue["message"] == SHARED_ALLOCATION_MESSAGE
    assert issue["remediation"] == SHARED_ALLOCATION_REMEDIATION


# --------------------------------------------------------------------------- #
# (2) Run admission                                                            #
# --------------------------------------------------------------------------- #


async def test_run_admission_refuses_and_leaves_nothing_behind(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    await _enable_allocation(session, USER1, composition_id, amount="50000.00")

    with pytest.raises(ReadinessBlockedError) as exc_info:
        await backtest_cmd.request_backtest_run(
            session, USER1, composition_id=composition_id, idempotency_key="shared-run-1"
        )
    await session.rollback()

    error = exc_info.value
    assert error.code == "READINESS_BLOCKED"
    assert error.category is not None
    assert error.scope_type == "portfolio_allocation"
    assert error.field_path == "enabled"
    assert error.remediation == SHARED_ALLOCATION_REMEDIATION
    assert _BLOCKER in {d["code"] for d in error.details}

    # Doc 15 §9.3: no run, manifest, job or result is created.
    assert await _count(session, BacktestRun) == 0
    assert await _count(session, BacktestRunManifest) == 0
    assert await _count(session, Job) == 0
    assert await _count(session, BacktestResult) == 0


async def test_admission_guard_holds_when_ready_check_is_bypassed(session, monkeypatch) -> None:
    """The guard does not depend on the readiness evaluation producing the blocker.

    A regressed / replaced / short-circuited allocation validator is simulated by
    forcing the readiness command to report the plan as ENABLED but ISSUE-FREE. The
    preflight then passes with zero blockers — and admission must STILL refuse,
    because the guard reads the pinned capital snapshot directly.
    """
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    await _enable_allocation(session, USER1, composition_id, amount="50000.00")

    real_resolve = readiness_cmd._resolve_allocation

    async def _blind_resolve(*args: Any, **kwargs: Any):
        _enabled, _issues, capital_mode = await real_resolve(*args, **kwargs)
        return True, [], capital_mode  # enabled, but the blocker is gone

    monkeypatch.setattr(readiness_cmd, "_resolve_allocation", _blind_resolve)

    # The preflight now really is clean — proving the bypass is effective.
    report = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()
    assert report["summary"]["blocker_count"] == 0
    assert not any(i["code"] == _BLOCKER for i in report["issues"])

    with pytest.raises(ReadinessBlockedError) as exc_info:
        await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.rollback()

    assert {d["code"] for d in exc_info.value.details} == {_BLOCKER}
    assert await _count(session, BacktestRun) == 0
    assert await _count(session, BacktestRunManifest) == 0


async def test_retry_of_a_shared_composition_is_refused(session, monkeypatch) -> None:
    """Retry re-admits against the CURRENT composition, so it hits the same guard."""
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)

    # Admit + fail a run in INDEPENDENT mode, so there is something retryable.
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    run = await session.get(BacktestRun, admit["run_id"])
    assert run is not None
    run.state = "failed"
    await session.commit()

    # Now the user switches the composition to shared capital and retries.
    await _enable_allocation(session, USER1, composition_id, amount="50000.00")

    with pytest.raises(ReadinessBlockedError):
        await backtest_cmd.retry_backtest_run(session, USER1, run_id=admit["run_id"])
    await session.rollback()

    # The original run is untouched and no second run was created.
    assert await _count(session, BacktestRun) == 1


# --------------------------------------------------------------------------- #
# (3) Independent mode is untouched                                            #
# --------------------------------------------------------------------------- #


async def test_independent_mode_still_runs_to_a_result(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "succeeded"
    view = await backtest_query.get_backtest_result(session, USER1, result_id=out["result_id"])
    # The strategy's OWN capital funds the run — no shared pool, no containment.
    assert view["summary"]["headline"]["initial_capital"] == "10000.00"


# --------------------------------------------------------------------------- #
# (4) Agent parity                                                             #
# --------------------------------------------------------------------------- #


async def test_agent_backtest_request_sees_the_same_blocker(session) -> None:
    """Doc 18 §10: an Agent is never a privileged caller."""
    await _seed_principals(session)
    # The tool-call row FKs onto a live runtime.
    session.add(
        AgentRuntime(
            agent_id=ALPHA_AGENT_ID,
            mode=RuntimeMode.CONTINUOUS,
            status=RuntimeStatus.ACTIVE,
            row_version=1,
        )
    )
    await session.flush()
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    await _enable_allocation(session, USER1, composition_id, amount="50000.00")

    with pytest.raises(ReadinessBlockedError) as human_exc:
        await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.rollback()

    with pytest.raises(ReadinessBlockedError) as agent_exc:
        await agent_tools.dispatch_tool_call(
            session,
            USER1,
            tool_name="backtest.request",
            policy_scope="execution",
            request={"composition_id": composition_id},
        )
    await session.rollback()

    assert agent_exc.value.code == human_exc.value.code
    assert {d["code"] for d in agent_exc.value.details} == {
        d["code"] for d in human_exc.value.details
    }
    assert await _count(session, BacktestRun) == 0


# --------------------------------------------------------------------------- #
# (5) Historical results stay readable and unmodified                          #
# --------------------------------------------------------------------------- #


async def test_a_legacy_shared_pool_result_stays_readable_and_unmodified(session) -> None:
    """Containment never rewrites history (doc 15 §3.2 — a Result is immutable).

    A run is materialised the normal way, then its stored diagnostics artifact is
    given the shape a pre-containment SHARED run left behind (``capital_allocation:
    shared_pool`` plus the sequential-curve warning). The read path must return it
    verbatim: the containment gates ADMISSION, it does not re-interpret or suppress
    artifacts that already exist.
    """
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    result_id = out["result_id"]

    row = (
        await session.execute(
            select(DiagnosticArtifact).where(
                DiagnosticArtifact.result_id == result_id,
                DiagnosticArtifact.kind == "run_diagnostics",
            )
        )
    ).scalar_one()
    legacy = dict(row.content)
    legacy["composition"] = {"capital_allocation": "shared_pool", "strategy_count": 2}
    legacy["warnings"] = [*legacy.get("warnings", []), _CURVE_WARNING]
    row.content = legacy
    await session.commit()

    # Still readable, byte-for-byte what was stored.
    view = await backtest_query.get_backtest_result(session, USER1, result_id=result_id)
    assert view["result_id"] == result_id
    stored = (
        await session.execute(
            select(DiagnosticArtifact).where(
                DiagnosticArtifact.result_id == result_id,
                DiagnosticArtifact.kind == "run_diagnostics",
            )
        )
    ).scalar_one()
    assert stored.content["composition"]["capital_allocation"] == "shared_pool"
    assert _CURVE_WARNING in stored.content["warnings"]
    assert await _count(session, BacktestResult) == 1
