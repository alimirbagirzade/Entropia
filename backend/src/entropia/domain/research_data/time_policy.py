"""Research Data time model & anti-lookahead protection (doc 12 §8.4, §10, §M5).

Pure predicates with no I/O. The canonical rules enforced here:
  * event time != available time; ``available_at >= event_at`` MUST hold.
  * eligibility for a ``decision_time`` t: a record is a candidate only when it
    has a valid instrument mapping AND ``available_at <= t`` (backward/as-of).
  * a Fixed-delay rule requires a positive, bounded delay; every other rule must
    carry ``delay = None`` so a stale prior delay never affects the engine.
  * forward-fill is never silent — only a field/feature definition may allow it.

A revision whose time policy fails ``time_policy_is_valid`` cannot be approved or
used; the command layer raises ``TimePolicyInvalid`` (422).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from entropia.domain.research_data.enums import AvailableTimePolicy
from entropia.shared.errors import TimePolicyInvalid

# A defensive upper bound on a declared availability delay (doc 12: "bounded").
MAX_AVAILABLE_DELAY = timedelta(days=31)


def available_time_is_consistent(event_at: datetime, available_at: datetime) -> bool:
    """Anti-lookahead: a value cannot be available before the event occurred."""
    return available_at >= event_at


def delay_is_valid(delay: timedelta | None) -> bool:
    """A Fixed-delay value must be strictly positive and bounded."""
    if delay is None:
        return False
    return timedelta(0) < delay <= MAX_AVAILABLE_DELAY


def resolve_available_at(
    event_at: datetime,
    *,
    policy: AvailableTimePolicy,
    delay: timedelta | None = None,
    provider_publish_at: datetime | None = None,
    custom_available_at: datetime | None = None,
) -> datetime:
    """Derive the first usable time for a record from its policy.

    Raises ``TimePolicyInvalid`` if the inputs the policy requires are missing or
    would violate the anti-lookahead rule (``available_at < event_at``).
    """
    if policy == AvailableTimePolicy.SAME_AS_EVENT_TIME:
        resolved = event_at
    elif policy == AvailableTimePolicy.FIXED_DELAY:
        if not delay_is_valid(delay):
            raise TimePolicyInvalid("Fixed delay must be a positive, bounded duration.")
        assert delay is not None  # narrowed by delay_is_valid
        resolved = event_at + delay
    elif policy == AvailableTimePolicy.PROVIDER_PUBLISH_TIMESTAMP:
        if provider_publish_at is None:
            raise TimePolicyInvalid("Provider publish timestamp is required for this rule.")
        resolved = provider_publish_at
    elif policy == AvailableTimePolicy.CUSTOM_DOCUMENTED_RULE:
        if custom_available_at is None:
            raise TimePolicyInvalid("A custom documented rule must resolve an available time.")
        resolved = custom_available_at
    else:  # pragma: no cover - exhaustive over the enum
        raise TimePolicyInvalid(f"Unsupported available-time policy '{policy}'.")

    if not available_time_is_consistent(event_at, resolved):
        raise TimePolicyInvalid("Resolved available time must not precede event time.")
    return resolved


def time_policy_is_valid(
    *,
    policy: AvailableTimePolicy,
    delay: timedelta | None,
) -> bool:
    """Structural validity of the available-time policy payload (doc 12 §5.2).

    Fixed-delay requires a valid delay; every other rule requires ``delay`` to be
    absent (hidden state must send null).
    """
    if policy == AvailableTimePolicy.FIXED_DELAY:
        return delay_is_valid(delay)
    return delay is None


def is_eligible_for_decision(
    *,
    available_at: datetime,
    decision_time: datetime,
    has_instrument_mapping: bool,
) -> bool:
    """Backward/as-of eligibility: a record may inform a decision at ``t`` only
    when it is mapped and ``available_at <= t`` (doc 12 §8.4 rule 2)."""
    return has_instrument_mapping and available_at <= decision_time
