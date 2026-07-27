"""K-02 — the engine's research-feed access is gated by ``is_eligible_for_decision``.

DB-free. Doc 12 §8.4 rule 2/3 says a research record may inform a decision at ``t`` ONLY
when it is mapped and ``available_at <= t``, resolved by a backward/as-of join. Before
K-02 the predicate had ZERO production callers: the engine compared ``available_at`` to
the bar time inline and the funding builder never carried the mapping conjunct.

These tests pin the enforcement on the surfaces that actually decide:
  * ``available_at > decision_time`` -> excluded; ``==`` -> included (boundary is inclusive);
  * an UNRESOLVABLE decision time (unparseable bar timestamp) while funding is active
    FAILS CLOSED instead of silently booking a zero funding cost;
  * a schedule whose mapping conjunct is false can never be built (fail-closed at the
    boundary), so the engine never receives one it would silently empty;
  * an incoherent available-time policy/delay pair fails closed rather than resolving
    every record to its raw EVENT time.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from entropia.domain.backtest.engine import run_engine
from entropia.domain.backtest.funding import (
    FundingRecord,
    FundingSchedule,
    build_funding_schedule,
)
from entropia.domain.research_data.enums import AvailableTimePolicy
from entropia.shared.errors import FundingSourceInvalid
from tests.unit.engine_signal_plan import sma_entry_plan
from tests.unit.test_backtest_engine import _bar, _batched, _config, _flat

_UTC = ZoneInfo("UTC")
# The bar the position is held on; its timestamp IS the decision time the gate evaluates.
_DECISION_BAR = datetime(2024, 1, 23, tzinfo=UTC)


def _long_held(hold: int = 4) -> list[dict[str, Any]]:
    """20 flat bars -> an upside breakout (long @102) -> ``hold`` flat bars (no stop)."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "102", "100", "102"))
    for i in range(hold):
        day = 22 + i
        bars.append(_bar(f"2024-01-{day:02d}T00:00:00Z", "102", "102", "101", "102"))
    return bars


def _one_record(available_at: datetime, *, mapped: bool = True) -> FundingSchedule:
    """A single-record schedule; the event stays at the decision bar, availability moves."""
    return FundingSchedule(
        source_revision_id="rdrev_k02",
        records=(
            FundingRecord(available_at=available_at, event_at=_DECISION_BAR, rate=Decimal("0.001")),
        ),
        has_instrument_mapping=mapped,
    )


def _run(bars: list[dict[str, Any]], funding: FundingSchedule | None) -> Any:
    return run_engine(
        strategy_config=_config(),
        bar_batches=_batched(bars, 8),
        execution_key="exec_key_k02",
        funding=funding,
        indicator_plan=sma_entry_plan(),
    )


def test_available_at_after_the_decision_time_is_excluded() -> None:
    # The value was published one second AFTER the bar that would have used it: consuming it
    # is look-ahead. It must not fire at that bar (and here, not at all — the run ends first).
    late = _one_record(datetime(2024, 1, 25, 0, 0, 1, tzinfo=UTC))
    out = _run(_long_held(), late)
    assert out.diagnostics["funding_charges"] == 0
    assert out.summary["funding_paid"] == Decimal("0.00")


def test_available_at_equal_to_the_decision_time_is_included() -> None:
    # doc 12 §8.4 rule 2 is ``available_at <= t`` — the boundary is INCLUSIVE. Availability
    # exactly at the decision bar's timestamp fires at that bar, not the next one.
    out = _run(_long_held(), _one_record(_DECISION_BAR))
    assert out.diagnostics["funding_charges"] == 1
    charge = next(e for e in out.signal_events if e.event_type == "funding_charge")
    assert charge.event_time == "2024-01-23T00:00:00Z"
    assert charge.detail["available_at"].startswith("2024-01-23")


def test_the_gate_is_the_only_difference_one_second_either_side() -> None:
    # The SAME event at the SAME bar, one second either side of the decision time, produces a
    # verifiably different result — proof the gate (not some other engine path) decides.
    just_in = _run(_long_held(), _one_record(datetime(2024, 1, 23, tzinfo=UTC)))
    just_out = _run(_long_held(), _one_record(datetime(2024, 1, 23, 0, 0, 1, tzinfo=UTC)))
    assert just_in.summary["funding_paid"] == Decimal("5.10")
    # One second later, the record is not yet available at bar 2024-01-23 — it fires at the
    # NEXT bar instead, so the charge still happens but at a later decision point.
    assert just_out.diagnostics["funding_charges"] == 1
    late_charge = next(e for e in just_out.signal_events if e.event_type == "funding_charge")
    assert late_charge.event_time == "2024-01-24T00:00:00Z"


def test_unresolvable_decision_time_fails_closed_while_funding_is_active() -> None:
    # An unparseable bar timestamp means there is NO decision time to evaluate eligibility
    # against. Silently firing nothing would book an over-optimistic ZERO funding cost for
    # the whole run, so the engine refuses the run instead.
    bars = _long_held()
    bars[-1] = _bar("not-a-timestamp", "102", "102", "101", "102")
    with pytest.raises(FundingSourceInvalid):
        _run(bars, _one_record(_DECISION_BAR))


def test_unresolvable_bar_timestamp_is_harmless_when_funding_is_off() -> None:
    # The fail-closed guard is scoped to the research feed: with no funding pinned there is
    # no eligibility to prove, so the pre-K-02 behaviour is untouched.
    bars = _long_held()
    bars[-1] = _bar("not-a-timestamp", "102", "102", "101", "102")
    assert _run(bars, None).summary["funding_paid"] == Decimal("0.00")


def test_a_schedule_without_a_valid_instrument_mapping_cannot_be_built() -> None:
    # Rule 2's other conjunct. An unmappable source can never be eligible at ANY decision
    # time, so it fails closed at the boundary rather than reaching the engine as a schedule
    # the gate would silently empty into a zero-cost run.
    with pytest.raises(FundingSourceInvalid):
        build_funding_schedule(
            [{"event_time": "2024-01-23T00:00:00Z", "funding_rate": "0.001"}],
            source_revision_id="rdrev_k02",
            columns=["event_time", "funding_rate"],
            policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
            delay_seconds=None,
            source_zone=_UTC,
            has_instrument_mapping=False,
        )


def test_an_unmapped_schedule_makes_every_record_ineligible_in_the_engine() -> None:
    # Defence in depth: even if a schedule were constructed directly with a false mapping
    # conjunct (tests, or a future caller), the ENGINE gate excludes every record — the
    # predicate's mapping argument is a real input, never a hardcoded True.
    out = _run(_long_held(), _one_record(_DECISION_BAR, mapped=False))
    assert out.diagnostics["funding_charges"] == 0
    assert out.summary["funding_paid"] == Decimal("0.00")


def test_an_incoherent_policy_and_delay_pair_fails_closed() -> None:
    # A stale 2h delay left on a same_as_event_time revision: ``resolve_available_at`` ignores
    # the delay under that rule, so every record would resolve to its raw EVENT time under a
    # policy the revision no longer declares — the silent event-time fallback §8.4 forbids.
    with pytest.raises(FundingSourceInvalid):
        build_funding_schedule(
            [{"event_time": "2024-01-23T00:00:00Z", "funding_rate": "0.001"}],
            source_revision_id="rdrev_k02",
            columns=["event_time", "funding_rate"],
            policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
            delay_seconds=7200,
            source_zone=_UTC,
            has_instrument_mapping=True,
        )


def test_a_fixed_delay_rule_without_its_delay_fails_closed() -> None:
    # The mirror case: a fixed_delay rule whose delay is missing would silently resolve
    # ``available_at`` to the event time — the same leak, from the other direction.
    with pytest.raises(FundingSourceInvalid):
        build_funding_schedule(
            [{"event_time": "2024-01-23T00:00:00Z", "funding_rate": "0.001"}],
            source_revision_id="rdrev_k02",
            columns=["event_time", "funding_rate"],
            policy=AvailableTimePolicy.FIXED_DELAY,
            delay_seconds=None,
            source_zone=_UTC,
            has_instrument_mapping=True,
        )
