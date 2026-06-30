"""Research time-model unit tests (doc 12 §8.4, §10, DR4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from entropia.domain.research_data.enums import AvailableTimePolicy
from entropia.domain.research_data.time_policy import (
    MAX_AVAILABLE_DELAY,
    available_time_is_consistent,
    delay_is_valid,
    is_eligible_for_decision,
    resolve_available_at,
    time_policy_is_valid,
)
from entropia.shared.errors import TimePolicyInvalid

_T = datetime(2026, 1, 1, 10, 15, tzinfo=UTC)


def test_available_must_not_precede_event() -> None:
    assert available_time_is_consistent(_T, _T + timedelta(minutes=2))
    assert available_time_is_consistent(_T, _T)
    assert not available_time_is_consistent(_T, _T - timedelta(seconds=1))


def test_delay_must_be_positive_and_bounded() -> None:
    assert delay_is_valid(timedelta(minutes=2))
    assert not delay_is_valid(None)
    assert not delay_is_valid(timedelta(0))
    assert not delay_is_valid(timedelta(seconds=-1))
    assert not delay_is_valid(MAX_AVAILABLE_DELAY + timedelta(seconds=1))


def test_resolve_fixed_delay() -> None:
    resolved = resolve_available_at(
        _T, policy=AvailableTimePolicy.FIXED_DELAY, delay=timedelta(minutes=2)
    )
    assert resolved == _T + timedelta(minutes=2)


def test_resolve_fixed_delay_missing_raises() -> None:
    with pytest.raises(TimePolicyInvalid):
        resolve_available_at(_T, policy=AvailableTimePolicy.FIXED_DELAY, delay=None)


def test_resolve_provider_publish_requires_timestamp() -> None:
    with pytest.raises(TimePolicyInvalid):
        resolve_available_at(_T, policy=AvailableTimePolicy.PROVIDER_PUBLISH_TIMESTAMP)


def test_resolve_rejects_lookahead() -> None:
    with pytest.raises(TimePolicyInvalid):
        resolve_available_at(
            _T,
            policy=AvailableTimePolicy.PROVIDER_PUBLISH_TIMESTAMP,
            provider_publish_at=_T - timedelta(minutes=1),
        )


def test_time_policy_validity_matrix() -> None:
    assert time_policy_is_valid(policy=AvailableTimePolicy.FIXED_DELAY, delay=timedelta(minutes=2))
    assert not time_policy_is_valid(policy=AvailableTimePolicy.FIXED_DELAY, delay=None)
    # Non-fixed rules must carry no delay (hidden state sends null).
    assert time_policy_is_valid(policy=AvailableTimePolicy.SAME_AS_EVENT_TIME, delay=None)
    assert not time_policy_is_valid(
        policy=AvailableTimePolicy.SAME_AS_EVENT_TIME, delay=timedelta(minutes=2)
    )


def test_as_of_eligibility_anti_lookahead() -> None:
    # doc 12 §14: a 10:17 available record is NOT eligible for a 10:15 decision.
    decision = datetime(2026, 1, 1, 10, 15, tzinfo=UTC)
    available_late = datetime(2026, 1, 1, 10, 17, tzinfo=UTC)
    assert not is_eligible_for_decision(
        available_at=available_late, decision_time=decision, has_instrument_mapping=True
    )
    # The same record IS eligible at 10:17 and after.
    assert is_eligible_for_decision(
        available_at=available_late, decision_time=available_late, has_instrument_mapping=True
    )


def test_eligibility_requires_instrument_mapping() -> None:
    t = datetime(2026, 1, 1, 10, 15, tzinfo=UTC)
    assert not is_eligible_for_decision(
        available_at=t, decision_time=t, has_instrument_mapping=False
    )
