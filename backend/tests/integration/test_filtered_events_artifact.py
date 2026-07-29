"""I-02 — Filtered Events as their OWN result artifact, engine -> DB -> HTTP.

Doc 15 §3.2's "Research Data / Agent Data" row lists five actions; "View Filtered
Events" had no artifact type, no table and no endpoint behind it — the engine's
``filtered_no_entry`` vetoes were appended into the SAME journal as fills and order
events. §16 requires the no-entry/filtered decision trace be readable in its own
right and never forced into the shape of a real fill.

The chain here is the one a worker actually walks: the real ``run_engine`` replays a
LONG-ONLY strategy over a down-crossing SMA fixture (so every short signal is vetoed),
the real ``create_result`` materializes the Result under a real run + hash-pinned
manifest, and the drill-down is then read over HTTP through the real route. What is
asserted:

* ``GET /backtest-results/{id}/artifacts/filtered_events`` returns 200 with the veto
  rows, and the SAME result's ``signal_events`` artifact carries none of them — the
  two are separate artifacts, not one journal filtered twice.
* The keyset cursor pages the artifact with no duplicates or gaps, mirroring the
  shipped Trade Ledger pagination.
* The stored checksum (doc 15 §7 "artifact checksum verification", §8.3 "persists ...
  with their checksums") re-derives EXACTLY from the rows the endpoint served, and is
  distinct from the signal-events checksum.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from entropia.application.queries import mainboard as mb_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.config.settings import get_settings
from entropia.domain.backtest.artifacts import ArtifactType, compute_artifact_checksum
from entropia.domain.backtest.manifest import ENGINE_VERSION, build_run_manifest
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    BacktestRun,
    BacktestRunManifest,
    FilteredEventRow,
    Principal,
    SignalEventRow,
)
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from tests.unit.test_backtest_decision_trace import _config, _plan_bars, _run, _sma_plan

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

# Six flat bars then a sustained drop: the SMA cross wants SHORT on every bar it holds,
# and the LONG-ONLY direction mode vetoes each one — several vetoes, no trade.
_BASE = get_settings().api_base_path
_CLOSES = ["10", "10", "10", "10", "10", "10", "8", "8", "8", "8", "8"]


async def _seed_principal(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _workspace(session) -> str:
    mb = await mb_query.get_default_mainboard(session, USER1)
    await session.commit()
    return mb["workspace_id"]


async def _materialize(session) -> tuple[str, Any]:
    """Replay the fixture with the REAL engine and materialize a real Result."""
    await _seed_principal(session)
    workspace_id = await _workspace(session)
    out = _run(_config(direction="long"), _plan_bars(_CLOSES), plan=_sma_plan())
    assert out.filtered_events, "fixture must produce filter vetoes"
    assert out.summary["total_trades"] == 0

    built = build_run_manifest(
        run_id="btrun_i02",
        composition_id=workspace_id,
        composition_snapshot_id="snap_i02",
        composition_fingerprint="fp_i02",
        item_manifest={
            "items": [
                {
                    "item_id": "mbi_1",
                    "kind": "strategy",
                    "root_id": "wo_a",
                    "revision_id": "rev_a",
                    "position": 10,
                    "enabled": True,
                }
            ]
        },
        capital_mode={"enabled": False},
        requested_by_principal_id="user_1",
        preflight={"ready_report_id": "rcrpt_1", "state": "ready", "warning_count": 0},
        correlation_id="corr_i02",
        created_at_iso="2024-01-01T00:00:00Z",
        engine_version=ENGINE_VERSION,
    )
    run = BacktestRun(
        run_id="btrun_i02",
        workspace_entity_id=workspace_id,
        composition_snapshot_id="snap_i02",
        composition_fingerprint="fp_i02",
        manifest_id="btman_i02",
        manifest_hash=built.manifest_hash,
        requested_by_principal_id="user_1",
    )
    manifest = BacktestRunManifest(
        manifest_id="btman_i02",
        run_id="btrun_i02",
        manifest_hash=built.manifest_hash,
        execution_key=built.execution_key,
        composition_snapshot_id="snap_i02",
        composition_fingerprint="fp_i02",
        engine_version=ENGINE_VERSION,
        manifest=built.manifest,
    )
    session.add_all([run, manifest])
    await session.flush()
    result = await bt_repo.create_result(
        session, run=run, manifest=manifest, engine_output=out, metric_values=[]
    )
    await session.flush()
    return result.result_id, out


def _override(app: Any, session) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(session=session, actor=USER1)
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


async def _get(app: Any, path: str, **params: Any) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        return await client.get(path, params=params)


async def test_filtered_events_artifact_is_served_separately_from_signal_events(
    app, session
) -> None:
    result_id, out = await _materialize(session)
    gen = _override(app, session)
    next(gen)
    try:
        filtered = await _get(
            app, f"{_BASE}/backtest-results/{result_id}/artifacts/filtered_events"
        )
        signals = await _get(app, f"{_BASE}/backtest-results/{result_id}/artifacts/signal_events")
    finally:
        next(gen, None)

    assert filtered.status_code == 200
    assert signals.status_code == 200
    filtered_body = filtered.json()
    assert filtered_body["artifact_type"] == "filtered_events"
    assert len(filtered_body["items"]) == len(out.filtered_events)
    assert {row["event_type"] for row in filtered_body["items"]} == {"filtered_no_entry"}
    # The split, asserted from the SERVED payloads: not one journal filtered twice.
    assert "filtered_no_entry" not in {row["event_type"] for row in signals.json()["items"]}
    # ...and from the tables themselves — two disjoint row sets under one result.
    stored_filtered = (
        (
            await session.execute(
                select(FilteredEventRow).where(FilteredEventRow.result_id == result_id)
            )
        )
        .scalars()
        .all()
    )
    stored_signals = (
        (await session.execute(select(SignalEventRow).where(SignalEventRow.result_id == result_id)))
        .scalars()
        .all()
    )
    assert len(stored_filtered) == len(out.filtered_events)
    assert not [r for r in stored_signals if r.event_type == "filtered_no_entry"]
    # Its own dense ``seq`` sequence — a veto is never a gap in either journal.
    assert sorted(r.seq for r in stored_filtered) == list(range(len(stored_filtered)))


async def test_filtered_events_cursor_pages_without_duplicates_and_checksum_verifies(
    app, session
) -> None:
    result_id, out = await _materialize(session)
    assert len(out.filtered_events) >= 3, "fixture must need more than one page"

    gen = _override(app, session)
    next(gen)
    try:
        walked: list[dict[str, Any]] = []
        cursor: str | None = None
        body: dict[str, Any] = {}
        for _ in range(len(out.filtered_events) + 1):
            params = {"limit": 2} if cursor is None else {"limit": 2, "cursor": cursor}
            response = await _get(
                app, f"{_BASE}/backtest-results/{result_id}/artifacts/filtered_events", **params
            )
            assert response.status_code == 200
            body = response.json()
            walked.extend(body["items"])
            cursor = body["next_cursor"]
            if cursor is None:
                break
        assert cursor is None, "pagination did not terminate"
        signal_body = (
            await _get(app, f"{_BASE}/backtest-results/{result_id}/artifacts/signal_events")
        ).json()
    finally:
        next(gen, None)

    # Server-side order, no duplicates or gaps.
    assert [row["seq"] for row in walked] == list(range(len(out.filtered_events)))
    # doc 15 §7/§14: the checksum re-derives from exactly the rows that were served.
    assert body["row_count"] == len(walked)
    assert body["checksum"] == compute_artifact_checksum(ArtifactType.FILTERED_EVENTS, walked)
    # Pinned to the artifact type: the signal journal's checksum is a different value.
    assert signal_body["checksum"] not in (None, body["checksum"])
