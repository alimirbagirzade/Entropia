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

import ast
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

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.commands.backtest_run import _resolve_tick_pins
from entropia.application.commands.readiness_check import (
    _resolve_market_data_issues,
    _resolve_research_sources,
    _resolve_signal_market_data_issues,
    _resolve_tick_data_issues,
)
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
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.package.catalog import CatalogFilters
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.readiness.issues import ReadinessItemInput
from entropia.domain.strategy.enums import ValidationStatusEnum
from entropia.infrastructure.postgres.models import (
    AgentRuntime,
    BacktestResult,
    EntityRegistry,
    MarketDatasetRevision,
    MetricValueRow,
    Principal,
    ResultSummary,
)
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import strategy as strat_repo
from entropia.shared.pagination import PageParams
from tests.integration.test_readiness_query_count import (
    _config,
    _market_revision,
    _package,
    _research_revision,
)
from tests.integration.test_readiness_signal_market_data import _signal_payload

pytestmark = pytest.mark.integration

BUDGET_FILE = Path(__file__).resolve().parents[3] / "docs" / "performance" / "query_budgets.json"

ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
#: The Ready Check runs as the composition's OWNER, not as an admin — the whole-operation
#: row measures the path a normal user takes.
_READINESS_USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
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


async def test_ready_check_signal_market_data_leg(session) -> None:
    """Ready Check's Trading Signal OHLCV-fallback leg (K-08, doc 04 §5).

    The same residual shape the market-data leg carried until #617: the pins were
    already batched, then the Root each pinned revision names was dereferenced INSIDE
    the item loop. ``test_readiness_query_count`` cannot see it — that file filters on
    ``market_dataset_revision`` and this read is against ``entity_registry``.
    """
    items: list[ReadinessItemInput] = []

    async def grow(count: int) -> None:
        for _ in range(count):
            revision_id = await _market_revision(session)
            index = len(items)
            items.append(
                ReadinessItemInput(
                    item_id=f"signal_{index}",
                    kind=MainboardItemKind.TRADING_SIGNAL,
                    root_id=f"root_{index}",
                    revision_id=f"rev_{index}",
                    available=True,
                    payload=_signal_payload(
                        f"srcast_{index}",
                        f"nsr_{index}",
                        {
                            "source": "ohlcv_close_if_needed",
                            "approved_market_data_revision_ref": revision_id,
                        },
                    ),
                )
            )

    async def run() -> None:
        issues = await _resolve_signal_market_data_issues(session, items)
        # Seeded revisions are DRAFT, so every signal is still blocked — the budget is
        # measured on the path that actually dereferences the Root.
        assert len(issues) == len(items)

    await _measure(session, "readiness_check.signal_market_data_leg", grow=grow, run=run)


async def test_ready_check_research_funding_leg(session) -> None:
    """Ready Check's Research funding leg (O-01, doc 12 §9.2).

    Third instance of the same residual: batched revisions, then a per-item
    ``get_dataset_root``. Every pin here RESOLVES, so each item reaches the branch that
    dereferences the Root — a fixture of unresolvable pins would short-circuit to
    ``found=False`` and measure a path the user never waits on.
    """
    items: list[ReadinessItemInput] = []

    async def grow(count: int) -> None:
        for _ in range(count):
            revision_id = await _research_revision(session)
            index = len(items)
            items.append(
                ReadinessItemInput(
                    item_id=f"funded_{index}",
                    kind=MainboardItemKind.STRATEGY,
                    root_id=f"root_{index}",
                    revision_id=f"rev_{index}",
                    available=True,
                    payload=_config(
                        indicator_rev="pkg_x",
                        condition_rev="pkg_y",
                        reference_rev="pkg_z",
                        leg_revs=[],
                        market_rev="md_rev_budget",
                        funding_revision_id=revision_id,
                    ).model_dump(mode="json"),
                )
            )

    async def run() -> None:
        sources = await _resolve_research_sources(session, items)
        assert len(sources) == len(items)
        assert all(source.found for source in sources), "the budget must measure the resolved path"

    await _measure(session, "readiness_check.research_funding_leg", grow=grow, run=run)


async def test_ready_check_tick_data_leg(session) -> None:
    """Ready Check's tick-data availability leg (F-07i, Master Ref §6.4 / §11.2).

    The fourth instance of the #617 shape, and the one with the narrowest door: the
    loop `continue`s on a non-Strategy item, an unavailable item, a config that does
    not parse, and — crucially — on every strategy whose ``intrabar_policy.tick_policy``
    is not ``require``. **A fixture that leaves the default ``inherit`` measures a leg
    that never runs**, reports a slope of 0 and proves nothing. The payload below
    flips the policy for exactly that reason, and ``run`` asserts every item comes
    back BLOCKED, which is the positive evidence that the read fired once per item.

    The axis is one DISTINCT instrument per item. Sharing an instrument would let a
    repeated identical query masquerade as a batch.
    """
    items: list[ReadinessItemInput] = []

    async def grow(count: int) -> None:
        for _ in range(count):
            index = len(items)
            payload = _config(
                indicator_rev="pkg_x",
                condition_rev="pkg_y",
                reference_rev="pkg_z",
                leg_revs=[],
                market_rev="md_rev_budget",
            ).model_dump(mode="json")
            payload["data"]["intrabar_policy"]["tick_policy"] = "require"
            payload["data"]["instrument_id"] = f"INSTR_{index}"
            items.append(
                ReadinessItemInput(
                    item_id=f"tick_{index}",
                    kind=MainboardItemKind.STRATEGY,
                    root_id=f"root_{index}",
                    revision_id=f"rev_{index}",
                    available=True,
                    payload=payload,
                )
            )

    async def run() -> None:
        issues = await _resolve_tick_data_issues(session, items)
        # No approved tick/trade revision exists for any of these instruments, so every
        # item must come back blocked. An empty list is ALSO what a leg that never ran
        # returns — this assertion is what tells the two apart.
        assert len(issues) == len(items)

    await _measure(session, "readiness_check.tick_data_leg", grow=grow, run=run)


# ---------------------------------------------------- RUN admission (doc 15 §15)


def _require_tick_config(index: int) -> dict[str, Any]:
    """A StrategyConfig that DEMANDS tick data, on its own instrument.

    Both edits are load-bearing. ``tick_policy`` must be ``require`` or
    ``tick_data_required`` is false and the leg's loop ``continue``s past every item;
    the instrument must be DISTINCT per item or eleven identical per-item queries
    would collapse in the fixture and a per-item read would read as batched.
    """
    payload = _config(
        indicator_rev="pkg_x",
        condition_rev="pkg_y",
        reference_rev="pkg_z",
        leg_revs=[],
        market_rev="md_rev_budget",
    ).model_dump(mode="json")
    payload["data"]["intrabar_policy"]["tick_policy"] = "require"
    payload["data"]["instrument_id"] = f"INSTR_{index}"
    return payload


async def _approved_tick_revision(session, index: int) -> str:
    """One APPROVED tick/trade revision on its own ACTIVE root, for ``INSTR_<index>``.

    Availability is not decoration here: ``_resolve_tick_pins`` is FAIL-CLOSED and
    raises 422 on the FIRST instrument it cannot pin, so a fixture without these rows
    would measure a leg that stopped after one item.
    """
    root = EntityRegistry(
        entity_id=f"budget_tick_root_{index}",
        entity_type="market_dataset",
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        lifecycle_state="active",
    )
    session.add(root)
    await session.flush()
    revision = MarketDatasetRevision(
        revision_id=f"budget_tick_rev_{index}",
        entity_id=root.entity_id,
        revision_no=1,
        market_data_type=MarketDataType.TICK_TRADES,
        revision_state=MarketRevisionState.APPROVED,
        instrument_id=f"INSTR_{index}",
        payload={},
        content_hash="c" * 64,
        created_by_principal_id="user_1",
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    await session.flush()
    return revision.revision_id


async def _mirror_pinned_strategy_item(session, index: int) -> dict[str, Any]:
    """One manifest entry in the doc 02 §7.1 MIRROR shape (the Strategy-editor path).

    The pinned work-object revision carries only ``strategy_revision_id``; the real
    config lives on the typed ``StrategyRevision`` behind it. That is what makes the
    mirror deref a SECOND per-item read on this leg, on top of the tick probe.
    """
    registry_root, strategy_root, _work_root, _draft = await strat_repo.create_strategy(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        display_name=f"Budget strategy {index}",
        rationale_family_id=None,
        initial_payload={"data": {}},
    )
    await session.flush()
    strategy_revision = await strat_repo.append_strategy_revision(
        session,
        strategy_root,
        payload=_require_tick_config(index),
        config_hash="0" * 64,
        validation_status=ValidationStatusEnum.VALID,
        created_by_principal_id="user_1",
    )
    await session.flush()
    mirror = await mb_repo.append_work_object_revision(
        session,
        registry_root,
        object_kind=MainboardItemKind.STRATEGY,
        payload={"strategy_revision_id": strategy_revision.revision_id},
        source_provenance={"strategy_revision_id": strategy_revision.revision_id},
        created_by_principal_id="user_1",
    )
    await session.flush()
    return {
        "item_id": f"tick_pin_{index}",
        "kind": str(MainboardItemKind.STRATEGY),
        "root_id": registry_root.entity_id,
        "revision_id": mirror.revision_id,
        "enabled": True,
    }


async def test_run_admission_tick_pins(session) -> None:
    """RUN admission's tick-pin leg — the first budget row on the admission path.

    ``docs/performance/README.md`` §8 names Run admission as the surface whose DB cost
    is gated deterministically *instead of* by the nightly load run, because driving a
    mutation per repeat would measure the seeding. That gate did not exist: no row in
    ``query_budgets.json`` measured admission at all.

    Two properties of this leg make the fixture, not the assertion, the hard part:

    * it is **fail-closed** — an instrument with no approved tick revision raises 422
      ``TICK_DATA_UNAVAILABLE`` from inside the loop, so a fixture that blocks measures
      a leg that stopped at item one and reports a comfortable, meaningless slope. Every
      item here is pinnable, and ``run`` asserts the returned map to prove the loop ran
      to completion over every item;
    * its door is narrow — a strategy whose ``intrabar_policy.tick_policy`` is left at
      the default ``inherit`` is skipped entirely, so a green ``0`` can equally mean
      "batched" and "never executed". The payload flips the policy for that reason.
    """
    await _principal(session, "user_1")
    items: list[dict[str, Any]] = []
    expected: dict[str, str] = {}

    async def grow(count: int) -> None:
        for _ in range(count):
            index = len(items)
            expected[f"tick_pin_{index}"] = await _approved_tick_revision(session, index)
            items.append(await _mirror_pinned_strategy_item(session, index))

    async def run() -> None:
        pins = await _resolve_tick_pins(session, {"items": items})
        # Positive evidence that the leg FIRED, once per item: ``None`` is what a leg
        # whose every item was skipped returns, and it is indistinguishable from a
        # batched one by statement count alone.
        assert pins is not None
        assert {item_id: pin["tick_revision_id"] for item_id, pin in pins.items()} == expected

    await _measure(session, "backtest_run.admission_tick_pins", grow=grow, run=run)


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


async def test_ready_check_whole_operation(session) -> None:
    """The WHOLE Ready Check, not one leg — the backstop the per-leg rows cannot be.

    Every other readiness row here measures one leg through its own internal helper.
    A leg can be flat while the operation that calls it grows, because the growth
    lives between the legs — so a suite of green leg budgets can coexist with an
    operation that is linear in the composition. This row closes that gap by
    measuring ``run_readiness_check`` end to end.

    **The axis is deliberately the EXTERNAL item kind.** The composition's per-item
    cost is not uniform, and both halves were measured rather than assumed:

    * a strategy-only composition is **FLAT at 9 statements** (n=1 and n=11 alike) —
      every strategy in that fixture pins the same package revision, so the per-item
      ``_resolve_strategy_payload`` read is absorbed by the identity map, which is the
      blind spot the file header already names;
    * a trade-log composition is **8 -> 18**, i.e. exactly **one statement per item**.

    That one statement is ``_resolve_external`` (`readiness_check.py:341`), called
    inside ``for item, available in enabled:`` and issuing
    ``resolve_trade_log_batch`` / ``resolve_signal_revision`` per row. It is leg 3 of
    P-C2 §D.1 and it is **live and unrepaired on purpose**: batching it changes which
    row wins when two items pin the same ``work_object_revision_id``, which is not
    UNIQUE — an undecided product question (gate G15). P3 measures; it does not repair.

    Recording 0 here would be false, and omitting the row to avoid the number is the
    silence this gate exists to break.
    """
    await _principal(session, "user_1")
    await session.commit()
    workspace_id = (await mb_query.get_default_mainboard(session, _READINESS_USER))["workspace_id"]
    await session.commit()
    seen = {"n": 0}

    async def grow(count: int) -> None:
        for _ in range(count):
            seen["n"] += 1
            work_object = await mb_cmd.create_work_object(
                session,
                _READINESS_USER,
                object_kind="trade_log",
                payload={"display_name": f"budget trade log {seen['n']}"},
                available_time=_BASE_TIME,
            )
            await mb_cmd.attach_mainboard_item(
                session,
                _READINESS_USER,
                workspace_id=workspace_id,
                root_id=work_object["root_id"],
                revision_id=work_object["revision_id"],
                item_kind="trade_log",
            )

    async def run() -> None:
        # Unpinned trade logs, so every item is NOT_READY — the budget is measured on
        # the path that actually dereferences each item, exactly as the market-data
        # leg is measured against DRAFT revisions.
        await readiness_cmd.run_readiness_check(
            session, _READINESS_USER, composition_id=workspace_id
        )

    await _measure(session, "readiness_check.run_readiness_check", grow=grow, run=run)


def _measured_surfaces() -> set[str]:
    """The surfaces this module actually measures, read from its OWN source.

    Derived rather than hand-listed. The literal set this replaces could drift from
    the tests in either direction: a surface measured but never added to the JSON, or
    a name kept in both places after its test stopped calling ``_measure``. Reading
    the call sites means the two can only agree by actually agreeing.

    Static (``ast``) rather than runtime registration on purpose — a set populated as
    tests execute would be empty under ``-k`` or a single-test run, and this gate
    would then pass by measuring nothing.
    """
    tree = ast.parse(Path(__file__).read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Name) or func.id != "_measure":
            continue
        # _measure(session, "<surface>", grow=..., run=...)
        surface = node.args[1] if len(node.args) >= 2 else None
        assert isinstance(surface, ast.Constant) and isinstance(surface.value, str), (
            "every _measure call must name its surface as a string literal, or this "
            "gate cannot see it"
        )
        found.add(surface.value)
    return found


def test_every_registered_surface_has_a_budget() -> None:
    """The budget file and this module name the SAME surfaces.

    A surface silently dropped from the JSON would stop being gated while the suite
    stayed green — the failure mode this file exists to prevent.
    """
    measured = _measured_surfaces()
    assert measured, "no _measure call site was found — the derivation itself is broken"
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
