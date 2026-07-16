"""Funding-rate cost model + available-time (anti-lookahead) join (F-11, doc 12 §8.4).

Research Data is stored today only as pinned provenance; F-11 makes the backtest engine
actually READ and USE a pinned ``funding_rate`` Research revision. This module is the PURE
core of that path:

* ``FundingRecord`` / ``FundingSchedule`` — a pre-resolved, available-time-safe series of
  funding rates. Every record already carries its ``available_at`` (the first moment the
  value could truly have been used — event time shifted by the revision's available-time
  policy). The schedule is the ONLY funding input the engine sees, so the engine can never
  reach a raw event-time value: future leakage is impossible by construction.
* ``build_funding_schedule`` — turns native funding rows (columns from the uploaded source)
  into that safe schedule by resolving each row's ``available_at`` via
  ``research_data.time_policy.resolve_available_at`` (doc 12 §8.4 rule 2). Fail-closed on an
  unresolvable schema / policy — never a silent skip that would quietly disable funding.

No I/O, clock, or randomness — the worker fetches the native rows from S3 and hands them to
``build_funding_schedule``; unit tests build a schedule directly. The engine consumes the
schedule with a backward/as-of join (a record fires at the first bar whose time is >= its
``available_at``), so a value dated after the last replayed bar can never affect the run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from entropia.domain.research_data.enums import AvailableTimePolicy
from entropia.domain.research_data.time_policy import resolve_available_at
from entropia.shared.errors import FundingSourceInvalid

# Canonical native-column resolution (doc 12: the source keeps its native schema; there is
# no fixed funding schema). We resolve the event-time column and the rate column by a
# documented candidate list, case-insensitively, and FAIL CLOSED when neither is present —
# a funding revision the engine cannot interpret must block the run, never be ignored.
_TIME_COLUMN_CANDIDATES = (
    "event_time",
    "event_at",
    "funding_time",
    "timestamp",
    "time",
    "ts",
)
_RATE_COLUMN_CANDIDATES = (
    "funding_rate",
    "rate",
    "funding",
    "value",
)


@dataclass(frozen=True, slots=True)
class FundingRecord:
    """One funding rate that becomes usable at ``available_at`` (already policy-shifted)."""

    available_at: datetime  # tz-aware UTC; the first moment this rate could be used
    event_at: datetime  # tz-aware UTC; when the funding event occurred (for the trace)
    rate: Decimal  # funding rate as a signed fraction (0.0001 = 1 bps per interval)


@dataclass(frozen=True, slots=True)
class FundingSchedule:
    """An available-time-safe, ascending funding series pinned to one Research revision."""

    source_revision_id: str
    records: tuple[FundingRecord, ...]  # sorted by available_at ascending

    def __bool__(self) -> bool:
        return bool(self.records)


def parse_utc(value: Any) -> datetime | None:
    """Coerce an ISO-8601 string / ``datetime`` to a tz-aware UTC ``datetime``.

    Returns ``None`` for an absent or unparseable value (the caller decides whether that is
    fail-closed or a dropped row). A naive datetime is assumed UTC; a ``Z`` suffix is
    normalized to ``+00:00`` so ``datetime.fromisoformat`` accepts it on every runtime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _to_rate(value: Any) -> Decimal | None:
    """Coerce a native rate cell to a FINITE ``Decimal``; ``None`` when unusable."""
    if value is None:
        return None
    try:
        rate = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return rate if rate.is_finite() else None


def resolve_funding_columns(columns: list[str]) -> tuple[str, str]:
    """Resolve (time_column, rate_column) from a native schema, case-insensitively.

    Raises ``FundingSourceInvalid`` when either cannot be resolved — a funding revision the
    engine cannot read must block the run (doc 12: a warning is never silently repaired)."""
    lookup = {col.lower(): col for col in columns}
    time_col = next((lookup[c] for c in _TIME_COLUMN_CANDIDATES if c in lookup), None)
    rate_col = next((lookup[c] for c in _RATE_COLUMN_CANDIDATES if c in lookup), None)
    if time_col is None or rate_col is None:
        raise FundingSourceInvalid(
            "Funding source native schema is missing an event-time or rate column "
            f"(saw columns={sorted(columns)}).",
        )
    return time_col, rate_col


def build_funding_schedule(
    rows: list[dict[str, Any]],
    *,
    source_revision_id: str,
    columns: list[str],
    policy: AvailableTimePolicy,
    delay_seconds: int | None,
) -> FundingSchedule:
    """Build an available-time-safe funding schedule from native rows (doc 12 §8.4).

    Each row's ``available_at`` is derived from its event time and the revision's
    available-time policy (``same_as_event_time`` / ``fixed_delay``), so a value can only be
    consumed at or after that resolved time. ``provider_publish_timestamp`` and
    ``custom_documented_rule`` need per-record inputs this generic reader does not carry and
    FAIL CLOSED (``FundingSourceInvalid``) rather than silently degrade to event time — the
    exact leakage the anti-lookahead rule forbids. Rows with an unparseable event time or a
    non-finite rate are dropped (they cannot inform a decision); an all-dropped source is a
    fail-closed error so a funding-enabled run never silently books zero cost."""
    if policy not in (AvailableTimePolicy.SAME_AS_EVENT_TIME, AvailableTimePolicy.FIXED_DELAY):
        raise FundingSourceInvalid(
            f"Funding available-time policy '{policy}' cannot be resolved from native rows "
            "without per-record publish/custom inputs.",
        )
    time_col, rate_col = resolve_funding_columns(columns)
    delay = timedelta(seconds=delay_seconds) if delay_seconds is not None else None

    records: list[FundingRecord] = []
    for row in rows:
        event_at = parse_utc(row.get(time_col))
        rate = _to_rate(row.get(rate_col))
        if event_at is None or rate is None:
            continue
        available_at = resolve_available_at(event_at, policy=policy, delay=delay)
        records.append(FundingRecord(available_at=available_at, event_at=event_at, rate=rate))

    if rows and not records:
        raise FundingSourceInvalid(
            "Funding source produced no usable rows (all event times / rates were unparseable).",
        )
    records.sort(key=lambda r: (r.available_at, r.event_at))
    return FundingSchedule(source_revision_id=source_revision_id, records=tuple(records))


__all__ = [
    "FundingRecord",
    "FundingSchedule",
    "build_funding_schedule",
    "parse_utc",
    "resolve_funding_columns",
]
