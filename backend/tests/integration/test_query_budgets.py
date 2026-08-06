"""ADIM 24 — every interactive read and mutation admission has a DB round-trip budget.

Auto-skips without PostgreSQL (see tests/integration/conftest.py). The three existing
``*_query_count`` files each pin ONE table on ONE surface, which is how a residual N+1
survives a green suite: ``test_readiness_query_count`` counted only
``market_dataset_revision`` reads and declared Ready Check batched, while the per-item
``get_dataset_root`` in the same loop kept costing one round trip per Strategy.

This file counts EVERY statement the operation issues — no table filter, nothing
excluded — and does it twice per surface in one session: once at ``n_small`` and once
at ``n_large``. That yields two properties a single absolute number cannot express:

* the **total** is at or under its recorded budget (a regression that adds any read,
  batched or not, fails), and
* the **per-item slope** ``(large - small) / (n_large - n_small)`` matches what the
  budget file records. A flat surface that becomes an N+1 fails on the slope even if
  the small-N total is unchanged — which is exactly how these defects ship.

The budgets live in ``docs/performance/query_budgets.json``, not in this file: they are
MEASURED values, and the file is a ratchet, not a wish. Coming in under budget prints a
"tighten me" line naming the new number; going over fails. Raising a budget (or a slope)
is a deliberate edit to a reviewed file with a written reason, the same idiom as
``frontend/e2e/a11y-baseline.json``.

Counts are DB round trips, not wall-clock: deterministic on any machine, so this is a
PR-blocking gate. Latency lives in the nightly load run (``scripts/loadgen.py`` /
``docs/performance/``), where a shared runner's noise cannot turn a green PR red.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event

from entropia.application.commands.readiness_check import _resolve_market_data_issues
from entropia.application.queries import agent_workspace as agent_query
from entropia.application.queries import library as library_query
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import results_history as history_query
from entropia.application.queries.audit_log import list_audit_events
from entropia.application.queries.dependency_pins import ensure_pinned_resolvers_active
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.backtest.enums import MetricAvailability
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ActorKind,
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.package.catalog import CatalogFilters
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.readiness.issues import ReadinessItemInput
from entropia.infrastructure.postgres.models import (
    AgentRuntime,
    BacktestResult,
    MetricValueRow,
    Principal,
    ResultSummary,
)
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.pagination import PageParams
from tests.integration.test_readiness_query_count import _market_revision, _package

pytestmark = pytest.mark.integration

BUDGET_FILE = Path(__file__).resolve().parents[3] / "docs" / "performance" / "query_budgets.json"

ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
PAGE = PageParams(limit=100)
_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


# --------------------------------------------------------------------------- counting


@contextmanager
def _all_statements(session) -> Iterator[list[str]]:
    """Every statement the block issues, from a COLD identity map.

    The seeding writes each row through this same session, so without the expunge a
    warm identity map would satisfy the reads from memory and report a budget of ~1
    for a surface that in production issues one round trip per row.
    """
    session.expunge_all()
    engine = session.get_bind()
    sync_engine = getattr(engine, "sync_engine", engine)
    seen: list[str] = []

    def _record(_conn, _cursor, statement, _params, _context, _many) -> None:
        seen.append(statement)

    event.listen(sync_engine, "before_cursor_execute", _record)
    try:
        yield seen
    finally:
        event.remove(sync_engine, "before_cursor_execute", _record)


# --------------------------------------------------------------------------- budgets


@dataclass(frozen=True)
class Budget:
    title: str
    axis: str
    n_small: int
    n_large: int
    queries_small: int
    queries_large: int
    per_item: int
    note: str


def _budgets() -> dict[str, Budget]:
    raw = json.loads(BUDGET_FILE.read_text())
    return {key: Budget(**value) for key, value in raw["surfaces"].items()}


BUDGETS = _budgets()


async def _measure(
    session,
    surface: str,
    *,
    grow: Callable[[int], Awaitable[None]],
    run: Callable[[], Awaitable[Any]],
) -> None:
    """Grow the fixture to each budget size and hold the operation to its budget.

    ``grow(k)`` adds ``k`` more rows on the surface's axis; ``run()`` performs the
    operation under measurement. Both sizes are measured in ONE session so the slope
    is a property of the same code path, not of two differently-built fixtures.
    """
    budget = BUDGETS[surface]

    await grow(budget.n_small)
    await session.commit()
    with _all_statements(session) as small:
        await run()

    await grow(budget.n_large - budget.n_small)
    await session.commit()
    with _all_statements(session) as large:
        await run()

    span = budget.n_large - budget.n_small
    measured_slope = (len(large) - len(small)) / span

    assert len(small) <= budget.queries_small, (
        f"{surface}: {len(small)} queries at n={budget.n_small}, "
        f"budget {budget.queries_small}\n" + "\n".join(small)
    )
    assert len(large) <= budget.queries_large, (
        f"{surface}: {len(large)} queries at n={budget.n_large}, "
        f"budget {budget.queries_large}\n" + "\n".join(large)
    )
    # The slope is the N+1 gate. A surface recorded as flat (per_item 0) that starts
    # reading per row fails HERE even when the small-N total still fits its budget.
    assert measured_slope <= budget.per_item, (
        f"{surface}: {measured_slope} queries per {budget.axis} "
        f"(recorded {budget.per_item}) — {len(small)} at n={budget.n_small} vs "
        f"{len(large)} at n={budget.n_large}"
    )
    if len(small) < budget.queries_small or len(large) < budget.queries_large:
        print(
            f"[query-budget] {surface} came in under budget: "
            f"queries_small {budget.queries_small} -> {len(small)}, "
            f"queries_large {budget.queries_large} -> {len(large)}, "
            f"per_item {budget.per_item} -> {measured_slope}"
        )


# --------------------------------------------------------------------------- fixtures


async def _principal(session, principal_id: str) -> None:
    if await session.get(Principal, principal_id) is None:
        session.add(Principal(principal_id=principal_id, principal_type=PrincipalType.HUMAN))
        await session.flush()


# --------------------------------------------------------------- Library (doc 08 §3)


async def test_library_catalog_page(session) -> None:
    """One catalog page costs the same whether it lists one package or eleven."""
    await _principal(session, "admin_1")
    filters = CatalogFilters(
        package_kind=None,
        lifecycle_state=None,
        validation_state=None,
        approval_state=None,
        visibility_scope=None,
        rationale_family_id=None,
        market_scope=None,
        timeframe_scope=None,
        query=None,
    )

    async def grow(count: int) -> None:
        for _ in range(count):
            await _package(session, PackageKind.INDICATOR, "ta.sma")

    async def run() -> None:
        page = await library_query.list_packages(session, ADMIN, PAGE, filters=filters)
        assert page["data"], "the catalog page must not be empty — the budget would be a lie"

    await _measure(session, "library.list_packages", grow=grow, run=run)


# ------------------------------------------------------- Results History (doc 16 §9.3)


async def test_results_history_page(session) -> None:
    """The history index reads its digests, summaries and portfolio markers in batches."""
    await _principal(session, "admin_1")
    board = await mb_query.get_default_mainboard(session, ADMIN)
    await session.commit()
    workspace_id = board["workspace_id"]
    seeded = 0

    async def grow(count: int) -> None:
        nonlocal seeded
        for _ in range(count):
            seeded += 1
            result_id = f"btres_budget_{seeded:03d}"
            session.add(
                BacktestResult(
                    result_id=result_id,
                    run_id=f"run_{result_id}",
                    manifest_id=f"man_{result_id}",
                    manifest_hash="a" * 64,
                    workspace_entity_id=workspace_id,
                    composition_fingerprint=f"fp_{result_id}",
                    engine_version="backtest-engine-v1-stub",
                    deletion_state="active",
                    row_version=1,
                    created_by_principal_id="admin_1",
                    created_at=_BASE_TIME + timedelta(hours=seeded),
                )
            )
            await session.flush()
            session.add(
                ResultSummary(
                    summary_id=f"btsum_{result_id}",
                    result_id=result_id,
                    symbol="BTCUSDT",
                    timeframe="1h",
                    period_start="2024-01-01T00:00:00Z",
                    period_end="2024-12-31T23:59:59Z",
                    total_trades=3,
                    headline={},
                )
            )
            session.add(
                MetricValueRow(
                    metric_value_id=f"mv_{result_id}_net_profit",
                    result_id=result_id,
                    metric_key="net_profit",
                    label="Net Profit",
                    unit="usd",
                    value_format="currency",
                    value=Decimal("100.00"),
                    availability=MetricAvailability.COMPUTED,
                    position_index=0,
                )
            )
            await session.flush()

    async def run() -> None:
        page = await history_query.list_backtest_results(session, ADMIN, limit=100)
        assert page["items"], "the history page must not be empty"

    await _measure(session, "results_history.list_backtest_results", grow=grow, run=run)


# ------------------------------------------------------ Ready Check (doc 14 §9.2/§11)


async def test_ready_check_market_data_leg(session) -> None:
    """Ready Check's market-data leg, counted across EVERY table it touches.

    ``test_readiness_query_count`` pins the ``market_dataset_revision`` read at one.
    This counts the whole leg, which is where the residual per-item
    ``get_dataset_root`` shows up — see the note on this surface in the budget file.
    """
    items: list[ReadinessItemInput] = []

    async def grow(count: int) -> None:
        for _ in range(count):
            revision_id = await _market_revision(session)
            index = len(items)
            items.append(
                ReadinessItemInput(
                    item_id=f"item_{index}",
                    kind=MainboardItemKind.STRATEGY,
                    root_id=f"root_{index}",
                    revision_id=f"rev_{index}",
                    available=True,
                    payload={"data": {"market_dataset_revision_id": revision_id}},
                )
            )

    async def run() -> None:
        issues = await _resolve_market_data_issues(session, items)
        # Seeded revisions are DRAFT, so every item is still blocked — the budget is
        # measured on the path that actually dereferences the root.
        assert len(issues) == len(items)

    await _measure(session, "readiness_check.market_data_leg", grow=grow, run=run)


# ------------------------------------------------- pinned resolver refs (doc 06 §7)


async def test_pinned_resolver_refs_revalidation(session) -> None:
    """Approve-time re-validation of a revision's pinned ESP resolver refs."""
    refs: list[dict[str, Any]] = []

    async def grow(count: int) -> None:
        for _ in range(count):
            index = len(refs)
            key = f"ta.budget_{index:03d}"
            root, _detail, revision = await pkg_repo.create_package(
                session,
                owner_principal_id=None,
                created_by_principal_id=None,
                package_kind=PackageKind.EMBEDDED_SYSTEM,
                input_contract={"source": "close"},
                output_contract={"kind": "directional_signal"},
                dependency_snapshot={"resolved": []},
                visibility_scope=VisibilityScope.SYSTEM,
                validation_state=PackageValidationState.PASSED,
                approval_state=ApprovalState.APPROVED,
            )
            await session.flush()
            esp_repo.upsert_registry_entry(
                session,
                canonical_key=key,
                package_entity_id=root.entity_id,
                runtime_adapter=RuntimeAdapter.PYTHON,
                trust_state=ResolverTrustState.TRUSTED_ACTIVE,
                trusted_active_revision_id=revision.revision_id,
            )
            await session.flush()
            refs.append({"canonical_key": key, "embedded_revision_id": revision.revision_id})

    async def run() -> None:
        # Every pin is trusted+passed+approved, so this returns cleanly: the budget
        # measures the full per-pin path, not an early defect short-circuit.
        await ensure_pinned_resolvers_active(
            session,
            dependency_snapshot={"resolved": list(refs)},
            scope_id="pkg_under_approval",
        )

    await _measure(session, "dependency_pins.ensure_pinned_resolvers_active", grow=grow, run=run)


# ------------------------------------------------------- Agent task history (doc 18 §7)


async def test_agent_task_history_page(session) -> None:
    """One page of the Alpha Agent task queue/history."""
    await _principal(session, "admin_1")
    session.add(
        AgentRuntime(
            agent_id=ALPHA_AGENT_ID, mode=RuntimeMode.CONTINUOUS, status=RuntimeStatus.PAUSED
        )
    )
    await session.flush()

    async def grow(count: int) -> None:
        for index in range(count):
            await al_repo.create_task(
                session,
                agent_id=ALPHA_AGENT_ID,
                task_type="research",
                title=f"budget task {index}",
                source="operator",
                priority=AgentTaskPriority.NORMAL,
                status=AgentTaskStatus.QUEUED,
            )

    async def run() -> None:
        page = await agent_query.list_tasks(session, ADMIN, limit=100)
        assert page["tasks"], "the task page must not be empty"

    await _measure(session, "agent_workspace.list_tasks", grow=grow, run=run)


# -------------------------------------------------------------- Audit log (M3, §8)


async def test_audit_event_page(session) -> None:
    """The Admin audit page. Its budget is a GUARD, not a repair: the projection is a
    flat row today, and the recorded slope of zero is what stops a future
    "resolve each row's target label" from shipping as a per-row read."""

    async def grow(count: int) -> None:
        for index in range(count):
            audit_repo.add_audit_event(
                session,
                event_kind="package.approved",
                actor_principal_id="admin_1",
                actor_kind=ActorKind.HUMAN,
                target_entity_id=f"pkg_{index}",
                target_entity_type="package",
            )
        await session.flush()

    async def run() -> None:
        data, _cursor = await list_audit_events(session, PAGE)
        assert data, "the audit page must not be empty"

    await _measure(session, "audit_log.list_audit_events", grow=grow, run=run)


# ---------------------------------------------------------------- the file itself


def test_every_registered_surface_has_a_budget() -> None:
    """The budget file and this module name the SAME surfaces.

    A surface silently dropped from the JSON would stop being gated while the suite
    stayed green — the failure mode this file exists to prevent.
    """
    measured = {
        "library.list_packages",
        "results_history.list_backtest_results",
        "readiness_check.market_data_leg",
        "dependency_pins.ensure_pinned_resolvers_active",
        "agent_workspace.list_tasks",
        "audit_log.list_audit_events",
    }
    assert set(BUDGETS) == measured


def test_recorded_slope_matches_the_recorded_totals() -> None:
    """``per_item`` is not an independent knob: it must be exactly the slope the two
    recorded totals describe. Without this, a budget could record a flat slope while
    its own numbers grow — and the N+1 assertion would pass against a lie."""
    for surface, budget in BUDGETS.items():
        span = budget.n_large - budget.n_small
        assert span > 0, surface
        delta = budget.queries_large - budget.queries_small
        assert delta == budget.per_item * span, (
            f"{surface}: recorded per_item={budget.per_item} does not match "
            f"({budget.queries_large} - {budget.queries_small}) / {span}"
        )
