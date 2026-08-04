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

from entropia.domain.research_data.enums import AvailableTimePolicy, ResearchRevisionState
from entropia.shared.errors import LifecycleBlocked, TimePolicyInvalid

# A defensive upper bound on a declared availability delay (doc 12: "bounded").
MAX_AVAILABLE_DELAY = timedelta(days=31)

# States after which a revision's available-time policy is FROZEN (doc 12 §11
# "Revision immutability", §14 "Revision immutability"). Once a revision has been
# approved it can be pinned by a Backtest Run manifest, a Backtest Result and an
# Agent bundle — and the execution path re-reads the LIVE policy fields off the
# revision row (``application/queries/funding.py``), while ``content_hash`` covers
# the payload bytes only. Retiming such a revision in place therefore re-interprets
# a finished Run's evidence under a rule that Run never used, which §14 forbids:
# changing the available time after v1.0 is Approved must NOT mutate v1.0 — a v1.1
# draft/analysis/revision is created, and existing run/result stay bound to v1.0.
# ``approval_revoked``/``deprecated`` are frozen for the same reason — revoking or
# deprecating stops NEW use, it does not unpin the manifests that already cite it.
TIME_POLICY_FROZEN_STATES = frozenset(
    {
        ResearchRevisionState.APPROVED,
        ResearchRevisionState.APPROVAL_REVOKED,
        ResearchRevisionState.DEPRECATED,
    }
)

# Native-schema column names that carry a record's EVENT time, most specific first.
# Research payload keeps its native schema (M5 — it is never coerced to Market Data's
# canonical OHLCV shape), so the event-time column is resolved by convention rather
# than declared. Used by the K-01 ingest timezone normalization.
#
# A deliberate SUPERSET of ``backtest.funding._TIME_COLUMN_CANDIDATES``: that list
# stays separate because resolving it is a fail-closed precondition there (an
# unresolved column raises ``FundingSourceInvalid`` and blocks the run), whereas here
# an unresolved column simply means "nothing to normalize". Narrowing this list to
# match funding's would leave a ``date``-keyed research source un-normalized — the
# exact ambiguous-date case doc 11 §9.1 forbids reading as UTC.
EVENT_TIME_COLUMN_CANDIDATES = (
    "event_time",
    "event_at",
    "funding_time",
    "timestamp",
    "time",
    "ts",
    "date",
)


def resolve_event_time_column(columns: list[str]) -> str | None:
    """The native column carrying event time, matched case-insensitively.

    Returns the column name AS SPELLED in the source (so the caller can index the
    row dicts), or ``None`` when the native schema declares no recognizable event
    time — a schema-agnostic payload the timezone normalizer must leave untouched."""
    lookup = {col.lower(): col for col in columns}
    return next((lookup[c] for c in EVENT_TIME_COLUMN_CANDIDATES if c in lookup), None)


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


def time_policy_is_frozen(state: ResearchRevisionState | None) -> bool:
    """Is this revision past the point where its time policy may still be edited?

    ``None`` (an unreadable/absent state) is treated as FROZEN — fail-closed: we
    cannot prove a revision is still pre-approval, and a wrong "still editable"
    answer silently retimes evidence a finished Run already cited."""
    return state is None or state in TIME_POLICY_FROZEN_STATES


def ensure_time_policy_mutable(
    *, state: ResearchRevisionState | None, revision_id: str | None = None
) -> None:
    """Gate an in-place available-time-policy write (doc 12 §11, §14).

    Raises ``LifecycleBlocked`` (409 ``LIFECYCLE_BLOCKED``, doc 12 §10 "Lifecycle")
    once the revision is frozen. The caller's recovery is the canonical one the page
    already implements: append a NEW revision (``create_research_dataset_revision``
    advances the head to a fresh DRAFT) and set the policy there, so the previously
    pinned revision keeps the exact rule its Runs and bundles were compiled under."""
    if not time_policy_is_frozen(state):
        return
    raise LifecycleBlocked(
        f"Research revision '{revision_id}' is {state} — its available-time policy is "
        "frozen. Create a new revision to change it.",
        details=[{"revision_id": revision_id, "revision_state": str(state) if state else None}],
        remediation=(
            "Create a new research dataset revision and set the time policy on that "
            "draft; the approved revision stays bound to the runs that pinned it."
        ),
        suggested_action="create_new_revision",
        scope_type="research_dataset_revision",
        scope_id=revision_id,
        field_path="available_time_policy",
    )


def instrument_mapping_is_valid(
    *,
    linked_market_dataset_revision_id: str | None,
    instrument_mapping_ref: str | None,
) -> bool:
    """Rule 2's MAPPING conjunct: is the revision's instrument mapping coherent?

    ``is_eligible_for_decision`` requires a valid instrument mapping as well as
    ``available_at <= t``. What "valid" can truthfully mean today is COHERENCE between
    the two declared halves (doc 12 §5.2): a revision linked to a market dataset must
    name its instrument mapping, and a mapping reference must not dangle without a link.
    A revision declaring NEITHER is coherent — it reaches a run pinned by revision id,
    not resolved through a mapping table.

    Honest boundary (unchanged by K-02): canonical instrument-resolution wiring is still
    backlog R1, so an INCOHERENT pair is the only mapping defect this predicate can
    detect. It mirrors ``quality_rules._check_instrument_mapping``, which surfaces the
    same gap as a validation WARNING, and never widens that into a new block on
    revisions that were already approved."""
    has_link = bool((linked_market_dataset_revision_id or "").strip())
    has_ref = bool((instrument_mapping_ref or "").strip())
    return has_link == has_ref


def is_eligible_for_decision(
    *,
    available_at: datetime,
    decision_time: datetime,
    has_instrument_mapping: bool,
) -> bool:
    """Backward/as-of eligibility: a record may inform a decision at ``t`` only
    when it is mapped and ``available_at <= t`` (doc 12 §8.4 rule 2).

    K-02: this is the SINGLE gate every engine research-feed access passes through.
    ``domain/backtest/engine.py`` calls it once per candidate funding record, so a
    research value can never reach a decision point by an ungated comparison."""
    return has_instrument_mapping and available_at <= decision_time
