"""ADIM 19 — the Result read path says which co-simulation produced the numbers.

Covers, end to end against real Postgres:
(1) a legacy-era shared-pool Result is labelled ``legacy_sequential`` with the shipped
    ``LEGACY_SEQUENTIAL_RESULT_NOTE``, and is declared NOT comparable with a unified run;
(2) a single-item Result needs no portfolio characterisation;
(3) editing the live composition afterwards does not change the label of a Result that
    already exists (doc 13 §14 test 19, ADR 0002 §10.4);
(4) a FAILED run produces no Result at all, so there is nothing to label (doc 15 §9.3).

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.queries import backtest_run as backtest_query
from entropia.application.queries import results_history as history_query
from entropia.domain.allocation.capability import LEGACY_SEQUENTIAL_RESULT_NOTE
from entropia.domain.backtest.portfolio_mode import (
    PORTFOLIO_MODE_LEGACY_SEQUENTIAL,
    PORTFOLIO_MODE_SINGLE_ITEM,
)
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    BacktestRun,
    DiagnosticArtifact,
)
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from tests.integration.test_backtest_persistence import (
    USER1,
    _count,
    _e2e_bars,
    _ready_composition,
    _seed_principals,
)

pytestmark = pytest.mark.integration

_CURVE_WARNING = "portfolio_curve_sequential_not_unified_clock"


async def _materialize(session) -> str:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert out["state"] == "succeeded"
    return str(out["result_id"])


async def _diagnostics_row(session, result_id: str) -> DiagnosticArtifact:
    return (
        await session.execute(
            select(DiagnosticArtifact).where(
                DiagnosticArtifact.result_id == result_id,
                DiagnosticArtifact.kind == "run_diagnostics",
            )
        )
    ).scalar_one()


async def _make_legacy(session, result_id: str) -> None:
    """Give the stored artifact the shape a pre-containment SHARED run left behind.

    Patching the persisted row is the only honest way to construct a legacy-era artifact:
    this build refuses to admit a shared run, so one cannot be produced afresh."""
    row = await _diagnostics_row(session, result_id)
    legacy = dict(row.content)
    legacy["composition"] = {"capital_allocation": "shared_pool", "strategy_count": 2}
    legacy["warnings"] = [*legacy.get("warnings", []), _CURVE_WARNING]
    row.content = legacy
    await session.commit()


async def test_a_legacy_shared_pool_result_is_labelled_and_declared_incomparable(
    session,
) -> None:
    result_id = await _materialize(session)
    await _make_legacy(session, result_id)

    view = await backtest_query.get_backtest_result(session, USER1, result_id=result_id)
    context = view["portfolio_simulation"]

    assert context["mode"] == PORTFOLIO_MODE_LEGACY_SEQUENTIAL
    assert context["note"] == LEGACY_SEQUENTIAL_RESULT_NOTE
    assert context["comparable_with_unified_clock"] is False


async def test_labelling_does_not_rewrite_the_immutable_artifact(session) -> None:
    """Reading is not writing (doc 15 §3.2). The label is derived, never persisted."""
    result_id = await _materialize(session)
    await _make_legacy(session, result_id)
    before = dict((await _diagnostics_row(session, result_id)).content)

    await backtest_query.get_backtest_result(session, USER1, result_id=result_id)
    await backtest_query.get_backtest_result(session, USER1, result_id=result_id)

    after = dict((await _diagnostics_row(session, result_id)).content)
    assert after == before
    assert await _count(session, BacktestResult) == 1


async def test_a_single_item_result_needs_no_portfolio_characterisation(session) -> None:
    result_id = await _materialize(session)
    view = await backtest_query.get_backtest_result(session, USER1, result_id=result_id)
    assert view["portfolio_simulation"]["mode"] == PORTFOLIO_MODE_SINGLE_ITEM
    assert view["portfolio_simulation"]["comparable_with_unified_clock"] is False


async def test_a_later_composition_edit_does_not_relabel_an_existing_result(session) -> None:
    """doc 13 §14 test 19: the historical manifest/label is fixed at materialisation.

    The composition is mutated by running a SECOND, independent backtest over it; the
    first Result's label must be identical before and after."""
    result_id = await _materialize(session)
    await _make_legacy(session, result_id)
    before = await backtest_query.get_backtest_result(session, USER1, result_id=result_id)

    composition_id = before["composition_id"]
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    after = await backtest_query.get_backtest_result(session, USER1, result_id=result_id)
    assert after["portfolio_simulation"] == before["portfolio_simulation"]
    assert after["manifest_hash"] == before["manifest_hash"]


async def test_the_history_index_labels_each_row_from_its_own_evidence(session) -> None:
    """doc 16: the index lists Results side by side, so it must say which era each row is
    from — a sequential fold's drawdown and a unified valuation's are different quantities.
    The list and the detail must agree, because both call the same resolver."""
    result_id = await _materialize(session)
    await _make_legacy(session, result_id)

    page = await history_query.list_backtest_results(session, USER1)
    row = next(item for item in page["items"] if item["result_id"] == result_id)

    assert row["portfolio_simulation"]["mode"] == PORTFOLIO_MODE_LEGACY_SEQUENTIAL
    assert row["portfolio_simulation"]["note"] == LEGACY_SEQUENTIAL_RESULT_NOTE
    assert row["portfolio_simulation"]["comparable_with_unified_clock"] is False

    detail = await backtest_query.get_backtest_result(session, USER1, result_id=result_id)
    assert row["portfolio_simulation"] == detail["portfolio_simulation"]


async def test_the_history_index_reads_the_modes_in_a_bounded_number_of_queries(
    session,
) -> None:
    """No per-row manifest/diagnostics N+1: the mode markers are two batched ``IN (...)``
    reads regardless of how many rows the page carries."""
    first = await _materialize(session)
    await _make_legacy(session, first)

    calls: list[str] = []
    original = bt_repo.get_portfolio_mode_markers

    async def counting(session_arg, result_ids):  # type: ignore[no-untyped-def]
        calls.append(",".join(sorted(result_ids)))
        return await original(session_arg, result_ids)

    bt_repo.get_portfolio_mode_markers = counting  # type: ignore[assignment]
    try:
        page = await history_query.list_backtest_results(session, USER1)
    finally:
        bt_repo.get_portfolio_mode_markers = original  # type: ignore[assignment]

    assert len(calls) == 1, "the markers must be loaded once per page, not once per row"
    assert all(item["portfolio_simulation"] is not None for item in page["items"])


async def test_a_failed_run_produces_no_result_to_label(session) -> None:
    """doc 15 §9.3: only SUCCEEDED materialises a Result. There is nothing to characterise."""
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(
        session,
        USER1,
        backtest_range={"start": "2025-01-01T00:00:00Z", "end": "2025-02-01T00:00:00Z"},
    )
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    out = await run_backtest(session, admit["job_id"], stream_bars=_e2e_bars)
    await session.commit()

    assert out["state"] == "failed"
    run = await session.get(BacktestRun, admit["run_id"])
    assert run.result_id is None
    assert await _count(session, BacktestResult) == 0
    assert await _count(session, DiagnosticArtifact) == 0
