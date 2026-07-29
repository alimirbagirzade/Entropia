"""K-03 — the funding step-order fix, end to end from the stored revision to the Result.

DB-backed (isolated schema), object-storage-free: an Approved funding Research revision is
seeded, ``resolve_funding_schedule`` projects it with an injected ``load_rows`` (mirroring
tests/integration/test_funding_resolution.py), and the resulting schedule is replayed by the
real ``run_engine`` over a deterministic bar fixture. This is the chain a worker actually
walks — revision -> provenance gate -> available-time schedule -> engine -> summary — so the
step-2 placement is proven where it matters, not only on the pure engine surface.

What the fixture documents, with the OLD (end-of-bar) numbers written down beside the new
ones so the incomparability is on the record:

    bar 21  long @102, 200.00000000 units (10000 * 2% risk / 1.0 stop point)  -- both orders
    bar 22  funding available (rate 0.001); the 1% stop also trips on this bar
              NEW: charged first  -> 20400.00 * 0.001 = 20.40 booked, THEN the stop closes
              OLD: charged last   -> the book was already flat, the charge was DROPPED
    bar 29  second long @120, sized from the equity left after bar 22
              NEW: (10000 - 204.00 - 20.40) * 2% = 195.51200000 units
              OLD: (10000 - 204.00)         * 2% = 195.92000000 units
    final   NEW final_equity 9775.60   OLD final_equity 9796.00

The gap is one bar of carry on ONE exit; it compounds with every exit a real perp run makes,
always in the same direction (larger positions, a later-binding exposure cap). Results
produced under the old order stay valid under their own pinned ``engine_version`` but are NOT
comparable with new ones — which is exactly what the ENGINE_VERSION bump asserted at the end
of this module is for: it shifts the execution_key namespace so a pre-K-03 Result is never
idempotently reused for a re-RUN (INF-04/INF-05).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from entropia.application.queries.funding import resolve_funding_schedule
from entropia.domain.backtest.engine import run_engine
from entropia.domain.backtest.manifest import ENGINE_VERSION, build_run_manifest
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    ResearchCategory,
    ResearchRevisionState,
    UsageScope,
)
from entropia.domain.strategy.config import FundingPolicy
from entropia.infrastructure.postgres.models.registry import EntityRegistry
from entropia.infrastructure.postgres.models.research_data import (
    ResearchDatasetRevision,
    ResearchNativeAsset,
)
from tests.unit.engine_signal_plan import sma_entry_plan
from tests.unit.test_backtest_engine import _bar, _batched, _config, _flat

pytestmark = pytest.mark.asyncio

_HASH = "k03fundinghash_1"
_ENTITY = "rdent_k03"
_REVISION = "rdrev_k03"
# One funding print, on the bar that also stops the first position out.
_ROWS: list[dict[str, Any]] = [{"event_time": "2024-01-22T00:00:00Z", "funding_rate": "0.001"}]

# The pre-K-03 (end-of-bar) values, kept literal so the divergence is auditable.
_OLD_ORDER_SECOND_ENTRY_SIZE = "195.92000000"
_OLD_ORDER_FINAL_EQUITY = Decimal("9796.00")


def _rows(_object_key: str) -> list[dict[str, Any]]:
    return list(_ROWS)


async def _seed_funding_revision(session: Any) -> str:
    """Insert a minimal APPROVED funding Research revision (+ native asset); return its id."""
    session.add(EntityRegistry(entity_id=_ENTITY, entity_type="research_dataset", row_version=1))
    session.add(
        ResearchNativeAsset(
            asset_id="rnat_k03",
            entity_id=_ENTITY,
            object_key="s3://processed/k03_funding.parquet",
            content_digest="dig_k03",
            size_bytes=64,
            row_count=len(_ROWS),
            schema_descriptor={"columns": ["event_time", "funding_rate"]},
        )
    )
    session.add(
        ResearchDatasetRevision(
            revision_id=_REVISION,
            entity_id=_ENTITY,
            revision_no=1,
            revision_state=ResearchRevisionState.APPROVED,
            category_key=ResearchCategory.FUNDING_RATE.value,
            native_asset_id="rnat_k03",
            available_time_policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
            available_delay_seconds=None,
            usage_scope=UsageScope.RESEARCH_BACKTEST,
            payload={},
            content_hash=_HASH,
        )
    )
    await session.flush()
    return _REVISION


def _policy(revision_id: str) -> FundingPolicy:
    return FundingPolicy(
        enabled=True,
        source_root_id=_ENTITY,
        source_revision_id=revision_id,
        source_content_hash=_HASH,
    )


def _fixture_bars() -> list[dict[str, Any]]:
    """20 look-back bars -> long @102 (bar 21) -> stop-out (bar 22) -> long @120 (bar 29)."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "102", "100", "102"))
    bars.append(_bar("2024-01-22T00:00:00Z", "102", "102", "90", "95"))
    bars.extend(_bar(f"2024-01-{23 + i:02d}T00:00:00Z", "95", "95", "95", "95") for i in range(6))
    bars.append(_bar("2024-01-29T00:00:00Z", "95", "120", "95", "120"))
    bars.append(_bar("2024-01-30T00:00:00Z", "120", "121", "119", "120"))
    return bars


def _replay(funding: Any) -> Any:
    # risk_based_sizing makes the entry size a pure function of equity, so the charge is
    # visible directly in the position the engine opens.
    return run_engine(
        strategy_config=_config(method="risk_based_sizing", risk_pct="2.0", stop_point="1.0"),
        bar_batches=_batched(_fixture_bars(), 8),
        execution_key="exec_key_k03_integration",
        funding=funding,
        indicator_plan=sma_entry_plan(),
    )


def _entry_sizes(out: Any) -> list[str]:
    return [e.detail["size"] for e in out.signal_events if e.event_type == "entry_fill"]


async def test_stored_funding_revision_is_charged_before_the_exit_that_bar(session) -> None:
    revision_id = await _seed_funding_revision(session)
    schedule = await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)
    assert schedule is not None and schedule.source_revision_id == revision_id

    out = _replay(schedule)
    # The record becomes available on bar 22, where the position is still held at the top of
    # the bar and stopped out later in it. Step 2 charges it; the old end-of-bar order did not.
    assert out.diagnostics["funding_charges"] == 1
    assert out.summary["funding_paid"] == Decimal("20.40")
    bar_22 = [e.event_type for e in out.signal_events if e.detail.get("bar_seq") == 22]
    assert bar_22[0] == "funding_charge"
    assert bar_22.index("funding_charge") < bar_22.index("position_close")


async def test_the_charge_propagates_into_the_next_entry_and_the_final_equity(session) -> None:
    revision_id = await _seed_funding_revision(session)
    schedule = await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)

    on, off = _replay(schedule), _replay(None)
    assert _entry_sizes(off) == ["200.00000000", _OLD_ORDER_SECOND_ENTRY_SIZE]
    assert _entry_sizes(on) == ["200.00000000", "195.51200000"]
    # The documented divergence: the un-funded/old-order run opens the LARGER second position.
    assert Decimal(_entry_sizes(on)[1]) < Decimal(_entry_sizes(off)[1])
    assert off.summary["final_equity"] == _OLD_ORDER_FINAL_EQUITY
    assert on.summary["final_equity"] == _OLD_ORDER_FINAL_EQUITY - Decimal("20.40")


async def test_the_engine_version_bump_shifts_the_execution_key_namespace() -> None:
    # New Results carry the CURRENT engine version; a run identity that hashed to one
    # execution_key under any previous version hashes to a different one now, so a Result
    # produced under the old funding order can never be idempotently reused for a re-RUN.
    #
    # S5c: the literal assertion that stood here is DELETED, not re-pinned to the next
    # release name. It had to be edited by I-15a and again by S5c without either slice
    # touching a single funding number — a test that breaks on unrelated changes is a
    # tripwire, not a check. What this test is actually about is the NAMESPACE SHIFT, which
    # the comparison below proves against a distinct prior pin without any test needing to
    # know what the current release is called (the post-PR-#45 stub-version convention).

    def _built(engine_version: str) -> Any:
        return build_run_manifest(
            run_id="btrun_k03",
            composition_id="mbws_1",
            composition_snapshot_id="snap_k03",
            composition_fingerprint="fp_k03",
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
            correlation_id="corr_1",
            created_at_iso="2024-01-01T00:00:00Z",
            engine_version=engine_version,
        )

    new = _built(ENGINE_VERSION)
    stale = _built("backtest-engine-v18-available-time-gate")
    assert new.manifest["identity"]["engine_version"] == ENGINE_VERSION
    assert new.execution_key != stale.execution_key
    assert new.manifest_hash != stale.manifest_hash
