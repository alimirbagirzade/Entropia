"""Research Data point-in-time evidence — the pure layer (doc 12 §5.2, §8.4, §11).

ADIM 13. Companion to ``tests/integration/test_research_point_in_time_parity.py``
(the DB-backed Agent-bundle vs Backtest-bundle parity half). Everything here is a
pure-function proof over the SHARED time-policy layer both consumers must obey:

* the as-of gate's exact boundary, down to one microsecond;
* what a duplicate / late / out-of-order record does to the backward join;
* what a NON-UTC declared source zone does to a funding schedule;
* what an ambiguous (DST fold) or nonexistent (DST gap) local wall clock resolves
  to — CHARACTERIZED, not asserted as canon: doc 12 declares no DST rule, so these
  tests pin the behavior that ships instead of inventing a policy (see the audit
  matrix ``docs/audit/research_point_in_time_matrix.md`` row T-9);
* the ADIM 13 fix: an approved revision's available-time policy is frozen.

Companion coverage that already existed and is deliberately NOT repeated here:
``test_research_time_policy.py`` (predicate matrix), ``test_funding_schedule.py``
(column resolution / drop-vs-fail-closed), ``test_backtest_available_time_gate.py``
(one-second boundary), ``test_backtest_costs.py`` (cursor semantics).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from entropia.domain.backtest.execution.costs import due_funding_charges
from entropia.domain.backtest.funding import (
    FundingRecord,
    build_funding_schedule,
    parse_utc,
)
from entropia.domain.market_data.validation_rules import resolve_timestamp
from entropia.domain.research_data.enums import AvailableTimePolicy, ResearchRevisionState
from entropia.domain.research_data.time_policy import (
    TIME_POLICY_FROZEN_STATES,
    ensure_time_policy_mutable,
    is_eligible_for_decision,
    resolve_available_at,
    time_policy_is_frozen,
)
from entropia.shared.errors import FundingSourceInvalid, LifecycleBlocked, TimePolicyInvalid

_NY = ZoneInfo("America/New_York")
_UTC_ZONE = ZoneInfo("UTC")
_DECISION = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)


def _record(available_at: datetime, *, rate: str = "0.0001") -> FundingRecord:
    return FundingRecord(available_at=available_at, event_at=available_at, rate=Decimal(rate))


# --------------------------------------------------------------------------- #
# T-2/T-3 — the as-of boundary is exact to the microsecond                      #
# --------------------------------------------------------------------------- #


def test_a_record_available_exactly_at_the_decision_time_is_eligible() -> None:
    # doc 12 §8.4 rule 2 is "available_at <= t", i.e. INCLUSIVE at the boundary.
    assert is_eligible_for_decision(
        available_at=_DECISION, decision_time=_DECISION, has_instrument_mapping=True
    )


def test_one_microsecond_after_the_decision_time_is_not_eligible() -> None:
    # The finest resolution the column can hold must still exclude. A gate that
    # only discriminates at second granularity would leak a sub-second lookahead.
    assert not is_eligible_for_decision(
        available_at=_DECISION + timedelta(microseconds=1),
        decision_time=_DECISION,
        has_instrument_mapping=True,
    )


def test_one_microsecond_before_the_decision_time_is_eligible() -> None:
    assert is_eligible_for_decision(
        available_at=_DECISION - timedelta(microseconds=1),
        decision_time=_DECISION,
        has_instrument_mapping=True,
    )


def test_the_microsecond_boundary_is_the_only_difference_either_side() -> None:
    # Same mapping, same decision time; ONE microsecond flips the answer both ways.
    before = _record(_DECISION - timedelta(microseconds=1))
    after = _record(_DECISION + timedelta(microseconds=1))
    index, charges = due_funding_charges(
        (before, after),
        start_index=0,
        decision_time=_DECISION,
        has_instrument_mapping=True,
        position_direction="long",
        position_notional=Decimal("1000"),
    )
    assert index == 1  # the cursor stopped ON the future record, never consumed it
    assert [c.record.available_at for c in charges] == [before.available_at]


# --------------------------------------------------------------------------- #
# T-4 — duplicates and late arrival in the backward/as-of join                  #
# --------------------------------------------------------------------------- #


def test_two_records_sharing_one_available_at_both_fire_exactly_once() -> None:
    # Duplicate availability is a DATA-QUALITY finding at ingest, not a silently
    # deduplicated one at execution: the as-of join owes each stored record exactly
    # one firing, so the cost is 2x, not 1x. Locking this stops a future "dedupe"
    # from quietly halving a booked funding cost.
    first = _record(_DECISION, rate="0.0001")
    second = _record(_DECISION, rate="0.0002")
    index, charges = due_funding_charges(
        (first, second),
        start_index=0,
        decision_time=_DECISION,
        has_instrument_mapping=True,
        position_direction="long",
        position_notional=Decimal("1000"),
    )
    assert index == 2
    assert [c.record.rate for c in charges] == [Decimal("0.0001"), Decimal("0.0002")]


def test_a_late_arriving_record_never_fires_for_an_earlier_decision_time() -> None:
    # "Late arrival" = the value reaches the system after the decision it would have
    # informed. Its available_at is what decides, so replaying the same bar again
    # yields the same empty answer — the record is not retroactively eligible.
    late = _record(_DECISION + timedelta(days=30))
    for _ in range(2):
        index, charges = due_funding_charges(
            (late,),
            start_index=0,
            decision_time=_DECISION,
            has_instrument_mapping=True,
            position_direction="long",
            position_notional=Decimal("1000"),
        )
        assert index == 0
        assert charges == []


def test_a_record_available_while_flat_advances_the_cursor_without_charging() -> None:
    # It is consumed (never re-fires later, when a position exists) but costs nothing.
    record = _record(_DECISION)
    index, charges = due_funding_charges(
        (record,),
        start_index=0,
        decision_time=_DECISION,
        has_instrument_mapping=True,
        position_direction=None,
        position_notional=Decimal("0"),
    )
    assert index == 1
    assert charges == []


# --------------------------------------------------------------------------- #
# T-1 — event time is never a proxy for usable time                             #
# --------------------------------------------------------------------------- #


def test_a_fixed_delay_source_is_ineligible_at_its_own_event_time() -> None:
    # doc 12 §14 "Time safety": a 10:15 event with a 10:17 availability is NOT
    # selected for a 10:15 decision; it becomes eligible at 10:17 and after.
    event_at = datetime(2026, 3, 2, 10, 15, tzinfo=UTC)
    schedule = build_funding_schedule(
        [{"event_time": event_at.isoformat(), "funding_rate": "0.0001"}],
        source_revision_id="rrev_x",
        columns=["event_time", "funding_rate"],
        policy=AvailableTimePolicy.FIXED_DELAY,
        delay_seconds=120,
        source_zone=_UTC_ZONE,
        has_instrument_mapping=True,
    )
    (record,) = schedule.records
    assert record.event_at == event_at
    assert record.available_at == event_at + timedelta(minutes=2)
    assert not is_eligible_for_decision(
        available_at=record.available_at, decision_time=event_at, has_instrument_mapping=True
    )
    assert is_eligible_for_decision(
        available_at=record.available_at,
        decision_time=event_at + timedelta(minutes=2),
        has_instrument_mapping=True,
    )


def test_a_resolved_available_time_can_never_precede_its_event_time() -> None:
    event_at = datetime(2026, 3, 2, 10, 15, tzinfo=UTC)
    with pytest.raises(TimePolicyInvalid):
        resolve_available_at(
            event_at,
            policy=AvailableTimePolicy.PROVIDER_PUBLISH_TIMESTAMP,
            provider_publish_at=event_at - timedelta(seconds=1),
        )


# --------------------------------------------------------------------------- #
# T-8 — a NON-UTC declared source zone reaches the funding schedule             #
# --------------------------------------------------------------------------- #


def test_a_naive_new_york_event_time_lands_on_the_true_utc_instant() -> None:
    # Every pre-existing funding test passes ZoneInfo("UTC"), so the branch that
    # actually applies a declared offset was never exercised on this path.
    schedule = build_funding_schedule(
        [{"event_time": "2026-07-01T09:30:00", "funding_rate": "0.0001"}],
        source_revision_id="rrev_ny",
        columns=["event_time", "funding_rate"],
        policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
        delay_seconds=None,
        source_zone=_NY,
        has_instrument_mapping=True,
    )
    # EDT is UTC-4 in July: 09:30 local is 13:30Z, NOT 09:30Z.
    assert schedule.records[0].event_at == datetime(2026, 7, 1, 13, 30, tzinfo=UTC)


def test_a_naive_row_under_an_unresolvable_zone_drops_instead_of_assuming_utc() -> None:
    # ``exchange`` mode carries no IANA identifier -> source_zone is None. Reading
    # the cell as UTC would book the rate at an instant that never occurred, so the
    # row drops; an ENTIRELY naive source therefore fails closed rather than
    # silently booking a zero-cost run.
    assert parse_utc("2026-07-01T09:30:00", source_zone=None) is None
    with pytest.raises(FundingSourceInvalid):
        build_funding_schedule(
            [{"event_time": "2026-07-01T09:30:00", "funding_rate": "0.0001"}],
            source_revision_id="rrev_naive",
            columns=["event_time", "funding_rate"],
            policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
            delay_seconds=None,
            source_zone=None,
            has_instrument_mapping=True,
        )


def test_an_offset_carrying_row_ignores_the_declared_zone_entirely() -> None:
    schedule = build_funding_schedule(
        [{"event_time": "2026-07-01T09:30:00+00:00", "funding_rate": "0.0001"}],
        source_revision_id="rrev_off",
        columns=["event_time", "funding_rate"],
        policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
        delay_seconds=None,
        source_zone=_NY,
        has_instrument_mapping=True,
    )
    assert schedule.records[0].event_at == datetime(2026, 7, 1, 9, 30, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# T-9 — DST fold / gap: CHARACTERIZATION, not canon                             #
# --------------------------------------------------------------------------- #
# Doc 12 §5.2 requires UTC normalization and says "conversion failure blocks
# approval/run", but it declares NO rule for the two local wall clocks that are
# not a 1:1 mapping. Rather than invent one (forbidden by the ADIM 13 charter),
# these tests pin what ships so the behavior is visible and any future product
# decision is a deliberate, reviewable change. Tracked as an open product question.


def test_an_ambiguous_dst_fold_string_resolves_to_the_first_occurrence() -> None:
    # 2024-11-03 01:30 America/New_York happens TWICE (EDT -04:00, then EST -05:00).
    # An offset-less STRING cannot express which one, and ``fold`` defaults to 0, so
    # the earlier (EDT) instant wins. The later occurrence is UNREACHABLE from a
    # source file: it is one hour of data that can never be addressed.
    ambiguous = "2024-11-03T01:30:00"
    edt_instant = datetime(2024, 11, 3, 5, 30, tzinfo=UTC)
    est_instant = datetime(2024, 11, 3, 6, 30, tzinfo=UTC)

    assert resolve_timestamp(ambiguous, source_zone=_NY).moment == edt_instant
    assert parse_utc(ambiguous, source_zone=_NY) == edt_instant
    # Neither reader flags the ambiguity; the second occurrence is simply not chosen.
    assert resolve_timestamp(ambiguous, source_zone=_NY).timezone_unresolved is False
    assert edt_instant != est_instant


def test_a_nonexistent_dst_gap_string_is_accepted_not_rejected() -> None:
    # 2024-03-10 02:30 America/New_York NEVER occurred (the clock jumped 02:00->03:00).
    # It is nevertheless normalized (as if the pre-transition EST offset applied)
    # rather than reported as a conversion failure.
    nonexistent = "2024-03-10T02:30:00"
    resolved = datetime(2024, 3, 10, 7, 30, tzinfo=UTC)

    assert resolve_timestamp(nonexistent, source_zone=_NY).moment == resolved
    assert parse_utc(nonexistent, source_zone=_NY) == resolved
    assert resolve_timestamp(nonexistent, source_zone=_NY).timezone_unresolved is False


@pytest.mark.parametrize(
    "text",
    ["2024-11-03T01:30:00", "2024-03-10T02:30:00", "2026-07-01T09:30:00"],
)
def test_the_ingest_normalizer_and_the_funding_reader_agree_on_every_dst_case(
    text: str,
) -> None:
    # The research ingest path (``resolve_timestamp``) and the funding schedule
    # builder (``parse_utc``) are two SEPARATE implementations. A divergence would
    # mean a value is stored at one instant and replayed at another, so their
    # agreement is the real invariant — whatever the DST answer turns out to be.
    assert resolve_timestamp(text, source_zone=_NY).moment == parse_utc(text, source_zone=_NY)


# --------------------------------------------------------------------------- #
# T-6 — an approved revision's available-time policy is frozen (ADIM 13 fix)    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "state",
    [
        ResearchRevisionState.DRAFT,
        ResearchRevisionState.ANALYZING,
        ResearchRevisionState.NEEDS_REVIEW,
        ResearchRevisionState.VERIFIED,
    ],
)
def test_a_pre_approval_revision_may_still_be_retimed(state: ResearchRevisionState) -> None:
    assert not time_policy_is_frozen(state)
    ensure_time_policy_mutable(state=state, revision_id="rrev_1")


@pytest.mark.parametrize(
    "state",
    [
        ResearchRevisionState.APPROVED,
        ResearchRevisionState.APPROVAL_REVOKED,
        ResearchRevisionState.DEPRECATED,
    ],
)
def test_a_post_approval_revision_is_frozen(state: ResearchRevisionState) -> None:
    assert time_policy_is_frozen(state)
    with pytest.raises(LifecycleBlocked):
        ensure_time_policy_mutable(state=state, revision_id="rrev_1")


def test_an_unreadable_state_fails_closed_as_frozen() -> None:
    # We cannot prove such a revision is still pre-approval, and a wrong "editable"
    # answer rewrites evidence a finished Run already cited.
    assert time_policy_is_frozen(None)
    with pytest.raises(LifecycleBlocked):
        ensure_time_policy_mutable(state=None, revision_id="rrev_1")


def test_the_frozen_set_is_exhaustive_over_the_lifecycle() -> None:
    # Every state is classified; a new lifecycle state cannot slip in unjudged.
    assert set(ResearchRevisionState) >= TIME_POLICY_FROZEN_STATES
    assert {s for s in ResearchRevisionState if time_policy_is_frozen(s)} == (
        TIME_POLICY_FROZEN_STATES
    )


def test_the_freeze_error_carries_the_canonical_recovery_envelope() -> None:
    # O-02: the raise site pins the object and field the caller must act on, and the
    # conflict is NOT advertised as retryable (retrying the same write always fails).
    with pytest.raises(LifecycleBlocked) as excinfo:
        ensure_time_policy_mutable(state=ResearchRevisionState.APPROVED, revision_id="rrev_frozen")
    err = excinfo.value
    assert err.code == "LIFECYCLE_BLOCKED"
    assert err.http_status == 409
    assert err.retryable is False
    assert err.scope_type == "research_dataset_revision"
    assert err.scope_id == "rrev_frozen"
    assert err.field_path == "available_time_policy"
    assert err.suggested_action == "create_new_revision"
    assert err.remediation
    assert err.details == [{"revision_id": "rrev_frozen", "revision_state": "approved"}]
