"""K-02 — available-time (anti-lookahead) enforcement end to end (doc 12 §8.4, §14).

DB-backed (isolated schema), object-storage-free: ``resolve_funding_schedule`` takes an
injected ``load_rows``, so the full chain a real RUN takes — pinned Research revision ->
policy-resolved schedule -> ``run_engine``'s ``is_eligible_for_decision`` gate — is
exercised without S3.

The central proof is a LOOK-AHEAD fixture: two revisions over the SAME native rows, whose
event times fall inside the held window. One declares ``same_as_event_time``; the other
declares a ``fixed_delay`` that pushes availability past the last replayed bar. An engine
that (wrongly) keyed consumption on EVENT time would produce identical results for both.
The results differ — the delayed revision books nothing and is byte-identical to
funding-off — so the available-time rule, not the event time, is what actually gates the
run (doc 12 §14 "Time safety").

The remaining tests pin the fail-closed boundary: an UNDEFINED available-time policy, an
incoherent policy/delay pair, and an incoherent instrument mapping each refuse the run
rather than silently degrading it to a zero-cost backtest.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from entropia.application.queries.funding import resolve_funding_schedule
from entropia.domain.backtest.engine import run_engine
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
from entropia.shared.errors import FundingSourceInvalid
from tests.unit.engine_signal_plan import sma_entry_plan
from tests.unit.test_backtest_engine import _bar, _batched, _config, _flat

pytestmark = pytest.mark.asyncio

_HASH = "k02_funding_hash"
# Both funding events fall INSIDE the held window (entry 2024-01-21, last bar 2024-01-25).
# Keyed on EVENT time they always fire; keyed on AVAILABLE time a delay can defer them out.
_ROWS = [
    {"event_time": "2024-01-22T00:00:00Z", "funding_rate": "0.001"},
    {"event_time": "2024-01-23T00:00:00Z", "funding_rate": "0.001"},
]
_DELAY_PAST_LAST_BAR_SECONDS = 10 * 24 * 3600  # 2024-01-22 + 10d = 2024-02-01 > last bar


def _rows(_object_key: str) -> list[dict[str, Any]]:
    return list(_ROWS)


def _held_bars() -> list[dict[str, Any]]:
    """20 flat bars -> an upside breakout (long @102) -> 4 held bars (no stop)."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "102", "100", "102"))
    for day in range(22, 26):
        bars.append(_bar(f"2024-01-{day:02d}T00:00:00Z", "102", "102", "101", "102"))
    return bars


async def _seed(
    session: Any,
    *,
    suffix: str,
    policy: AvailableTimePolicy | None = AvailableTimePolicy.SAME_AS_EVENT_TIME,
    delay_seconds: int | None = None,
    linked_market_revision_id: str | None = None,
    instrument_mapping_ref: str | None = None,
) -> str:
    """Insert one Approved funding revision (+ native asset); return its revision id."""
    entity_id = f"rdent_k02_{suffix}"
    native_id = f"rnat_k02_{suffix}"
    revision_id = f"rdrev_k02_{suffix}"
    session.add(EntityRegistry(entity_id=entity_id, entity_type="research_dataset", row_version=1))
    session.add(
        ResearchNativeAsset(
            asset_id=native_id,
            entity_id=entity_id,
            object_key=f"s3://processed/funding_{suffix}.parquet",
            content_digest=f"dig_{suffix}",
            size_bytes=128,
            row_count=len(_ROWS),
            schema_descriptor={"columns": ["event_time", "funding_rate"]},
        )
    )
    revision = ResearchDatasetRevision(
        revision_id=revision_id,
        entity_id=entity_id,
        revision_no=1,
        revision_state=ResearchRevisionState.APPROVED,
        category_key=ResearchCategory.FUNDING_RATE.value,
        native_asset_id=native_id,
        available_time_policy=policy,
        available_delay_seconds=delay_seconds,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        payload={},
        content_hash=_HASH,
    )
    revision.linked_market_dataset_revision_id = linked_market_revision_id
    revision.instrument_mapping_ref = instrument_mapping_ref
    session.add(revision)
    await session.flush()
    return revision_id


def _policy(revision_id: str) -> FundingPolicy:
    return FundingPolicy(
        enabled=True,
        source_root_id="rdent_k02",
        source_revision_id=revision_id,
        source_content_hash=_HASH,
    )


def _run(schedule: Any) -> Any:
    return run_engine(
        strategy_config=_config(),
        bar_batches=_batched(_held_bars(), 8),
        execution_key="exec_key_k02_integration",
        funding=schedule,
        indicator_plan=sma_entry_plan(),
    )


async def test_lookahead_fixture_changes_the_result_available_time_not_event_time(
    session,
) -> None:
    """doc 12 §14 Time safety: the SAME events, gated by availability, change the outcome."""
    same_time_id = await _seed(session, suffix="same")
    delayed_id = await _seed(
        session,
        suffix="delayed",
        policy=AvailableTimePolicy.FIXED_DELAY,
        delay_seconds=_DELAY_PAST_LAST_BAR_SECONDS,
    )

    available_now = await resolve_funding_schedule(session, _policy(same_time_id), load_rows=_rows)
    available_later = await resolve_funding_schedule(session, _policy(delayed_id), load_rows=_rows)
    assert available_now is not None and available_later is not None
    # Identical EVENT times; only the resolved availability differs.
    assert [r.event_at for r in available_now.records] == [
        r.event_at for r in available_later.records
    ]
    assert all(r.available_at == r.event_at for r in available_now.records)
    assert all(r.available_at > r.event_at for r in available_later.records)

    leaky_result = _run(available_now)
    gated_result = _run(available_later)
    funding_off = _run(None)

    # Both events are available inside the held window -> two real charges (2 x 5100 x 0.001).
    assert leaky_result.diagnostics["funding_charges"] == 2
    assert leaky_result.summary["funding_paid"] == Decimal("10.20")
    # Delayed past the last bar -> nothing fires. Had the engine keyed on EVENT time, this
    # run would be identical to the one above; instead it is identical to funding-off.
    assert gated_result.diagnostics["funding_charges"] == 0
    assert gated_result.summary["funding_paid"] == Decimal("0.00")
    assert gated_result.summary == funding_off.summary
    # The verifiable divergence between the two revisions.
    assert leaky_result.summary["final_equity"] < gated_result.summary["final_equity"]
    assert gated_result.summary["net_profit"] - leaky_result.summary["net_profit"] == Decimal(
        "10.20"
    )


async def test_a_partial_delay_defers_which_events_are_eligible(session) -> None:
    """A delay that clears only the LAST bar leaves exactly one event eligible."""
    # 2024-01-22 + 3d = 2024-01-25 (the last bar, inclusive -> eligible);
    # 2024-01-23 + 3d = 2024-01-26 (past the last bar -> never eligible).
    revision_id = await _seed(
        session,
        suffix="partial",
        policy=AvailableTimePolicy.FIXED_DELAY,
        delay_seconds=3 * 24 * 3600,
    )
    schedule = await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)
    out = _run(schedule)
    assert out.diagnostics["funding_charges"] == 1
    assert out.summary["funding_paid"] == Decimal("5.10")


async def test_undefined_available_time_policy_fails_closed(session) -> None:
    """An available time the revision never declares can never be resolved — refuse the run."""
    revision_id = await _seed(session, suffix="nopolicy", policy=None)
    with pytest.raises(FundingSourceInvalid):
        await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)


async def test_incoherent_policy_and_delay_fails_closed(session) -> None:
    """A stale delay under same_as_event_time would silently resolve to raw EVENT time."""
    revision_id = await _seed(session, suffix="staledelay", delay_seconds=7200)
    with pytest.raises(FundingSourceInvalid):
        await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)


async def test_incoherent_instrument_mapping_fails_closed(session) -> None:
    """Rule 2's mapping conjunct: a linked market revision with no mapping reference."""
    revision_id = await _seed(
        session,
        suffix="nomapping",
        linked_market_revision_id="mdrev_1",
        instrument_mapping_ref=None,
    )
    with pytest.raises(FundingSourceInvalid):
        await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)


async def test_a_coherent_link_and_mapping_pair_resolves(session) -> None:
    """The mapping gate is a coherence check, not a new blanket block on linked revisions."""
    revision_id = await _seed(
        session,
        suffix="mapped",
        linked_market_revision_id="mdrev_1",
        instrument_mapping_ref="BTCUSDT",
    )
    schedule = await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)
    assert schedule is not None
    assert schedule.has_instrument_mapping is True
    assert _run(schedule).diagnostics["funding_charges"] == 2
