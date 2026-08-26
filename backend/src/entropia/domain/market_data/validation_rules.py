"""Pure per-type market-data validation rules (doc 11 §, AT #7-#9).

Each rule takes a single typed row and returns a ``ValidationStatus``. No I/O.
Numeric inputs are ``Decimal`` (or decimal-parseable ``str``) — never ``float``
(project DB rule D6). Side values for ticks are preserved, never guessed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from typing import Any
from zoneinfo import ZoneInfo

from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.market_data.enums import MarketDataType, ResolutionKind, TradeSide
from entropia.shared.dst import is_nonexistent_local_time

DecimalLike = Decimal | str | int

# K-01: the canonical code for "a naive source timestamp could not be localized".
# Shared verbatim with ``shared.errors.MarketDataTimezoneUnresolved.code`` so the
# validation-issue row and the API error surface name the same failure.
TIMEZONE_UNRESOLVED_RULE_CODE = "MARKET_DATA_TIMEZONE_UNRESOLVED"


def _as_decimal(value: DecimalLike) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"'{value}' is not a valid decimal.") from exc


@dataclass(frozen=True, slots=True)
class OhlcvRow:
    open: DecimalLike
    high: DecimalLike
    low: DecimalLike
    close: DecimalLike
    volume: DecimalLike | None = None


@dataclass(frozen=True, slots=True)
class TickRow:
    price: DecimalLike
    side: TradeSide = TradeSide.UNKNOWN


@dataclass(frozen=True, slots=True)
class SpreadRow:
    bid: DecimalLike
    ask: DecimalLike


def validate_ohlcv_row(row: OhlcvRow) -> ValidationStatus:
    """OHLC must be positive; ``high >= max(open, close)``; ``low <= min(open, close)``.
    Negative volume is a blocking failure; zero volume is a contextual warning."""
    o, h, low, c = (
        _as_decimal(row.open),
        _as_decimal(row.high),
        _as_decimal(row.low),
        _as_decimal(row.close),
    )
    if any(v <= 0 for v in (o, h, low, c)):
        return ValidationStatus.BLOCKING_FAIL
    if h < max(o, c) or low > min(o, c):
        return ValidationStatus.BLOCKING_FAIL
    if row.volume is not None:
        vol = _as_decimal(row.volume)
        if vol < 0:
            return ValidationStatus.BLOCKING_FAIL
        if vol == 0:
            return ValidationStatus.WARNING
    return ValidationStatus.PASS


def validate_tick_row(row: TickRow) -> ValidationStatus:
    """Price must be positive. ``UNKNOWN`` side is preserved (not rejected) and
    surfaces as a downstream warning rather than a blocking failure."""
    if _as_decimal(row.price) <= 0:
        return ValidationStatus.BLOCKING_FAIL
    if row.side == TradeSide.UNKNOWN:
        return ValidationStatus.WARNING
    return ValidationStatus.PASS


def validate_spread_row(row: SpreadRow) -> ValidationStatus:
    """``ask < bid`` is a blocking failure; non-positive quotes also block."""
    bid, ask = _as_decimal(row.bid), _as_decimal(row.ask)
    if bid <= 0 or ask <= 0:
        return ValidationStatus.BLOCKING_FAIL
    if ask < bid:
        return ValidationStatus.BLOCKING_FAIL
    return ValidationStatus.PASS


# --- Cross-row aggregate validation (doc 11 §7.4) --------------------------------
#
# The per-row rules above cannot see relationships BETWEEN rows. Timestamp
# monotonicity, duplicate (instrument+timestamp+resolution), declared cadence gaps
# and spread-unit declaration are aggregate properties: a dataset that is per-row
# clean can still be non-monotonic or duplicated, which silently corrupts the
# bar-replay backtest/allocation engine it feeds (GAP-02 money sizing). These pure
# helpers compute the findings; the analysis job persists them as validation
# issues + coverage slices.

_SEVERITY_RANK: dict[ValidationStatus, int] = {
    ValidationStatus.PASS: 0,
    ValidationStatus.WARNING: 1,
    ValidationStatus.BLOCKING_FAIL: 2,
}

# Cadence suffixes -> seconds; a bare integer is read as minutes (TradingView form).
_CADENCE_UNIT_SECONDS: dict[str, int] = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}

# Recognised spread-unit declarations (doc 11 §7.4: absolute/bps/% must be declared).
_DECLARED_SPREAD_UNITS: frozenset[str] = frozenset(
    {"absolute", "abs", "bps", "percent", "pct", "%"}
)

# Epoch values at/above this magnitude are milliseconds, below are seconds.
_MILLISECOND_EPOCH_THRESHOLD = 1_000_000_000_000


@dataclass(frozen=True, slots=True)
class CrossRowIssue:
    """A single aggregate finding, ready to persist as a validation issue."""

    severity: ValidationStatus
    rule_code: str
    message: str
    occurrences: int
    sample: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class CoverageSegment:
    """A contiguous covered interval; ``gap_seconds`` is the gap that follows it."""

    start_at: datetime
    end_at: datetime
    row_count: int
    gap_seconds: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CrossRowReport:
    """Aggregate outcome: worst severity + issues + coverage segments."""

    worst: ValidationStatus
    issues: tuple[CrossRowIssue, ...]
    coverage: tuple[CoverageSegment, ...]


@dataclass(frozen=True, slots=True)
class TimestampParse:
    """Outcome of reading one raw timestamp cell against the declared source zone.

    ``moment`` is the canonical UTC instant, or ``None`` when the cell could not be
    resolved. ``timezone_unresolved`` distinguishes the two ways that happens: a
    genuinely unparseable cell (``False``) versus a *parseable but naive* cell the
    declared timezone could not localize (``True``). The second case is K-01's
    fail-closed branch — doc 11 §9.1 forbids a silent UTC fallback for exactly it.
    """

    moment: datetime | None
    timezone_unresolved: bool = False


def resolve_timestamp(value: Any, *, source_zone: ZoneInfo | None) -> TimestampParse:
    """Read one raw timestamp cell into a canonical UTC instant (doc 11 §7.3 step 5).

    Accepts ``datetime``/``date``, epoch seconds/milliseconds (int/float or their
    string form) and ISO-8601 strings (trailing ``Z`` allowed). ``bool`` is rejected
    (it is an ``int`` subclass).

    Timezone contract (K-01):

    * a value that already carries an offset is converted with ``astimezone(UTC)``;
    * an epoch number is absolute and needs no zone;
    * a NAIVE value (bare ``datetime``/``date``/offset-less ISO string) is localized
      in ``source_zone`` — the revision's declared timezone;
    * when ``source_zone`` is ``None`` (an ``exchange`` mode carries no resolvable
      IANA identifier) a naive value is UNRESOLVED, never assumed to be UTC.
    """
    if value is None or isinstance(value, bool):
        return TimestampParse(None)
    if isinstance(value, datetime):
        return _localize(value, source_zone)
    if isinstance(value, date):
        return _localize(datetime(value.year, value.month, value.day), source_zone)
    if isinstance(value, (int, float)):
        return TimestampParse(_from_epoch(float(value)))
    if isinstance(value, str):
        return _resolve_timestamp_str(value, source_zone)
    return TimestampParse(None)


def parse_timestamp(value: Any, *, source_zone: ZoneInfo | None) -> datetime | None:
    """The canonical UTC instant for a raw cell, or ``None`` when unresolvable.

    Thin wrapper over :func:`resolve_timestamp` for callers that do not need to tell
    an unparseable cell apart from an unlocalizable naive one. ``source_zone`` is
    keyword-ONLY and REQUIRED so no call site can silently inherit a UTC default."""
    return resolve_timestamp(value, source_zone=source_zone).moment


def _localize(moment: datetime, source_zone: ZoneInfo | None) -> TimestampParse:
    """Normalize one parsed ``datetime`` to UTC under the declared source zone.

    G8 (GH #559, signed 2026-08-26): a DST **gap** is a conversion failure — the wall clock
    never occurred, so there is no instant to normalize to and inventing one would publish a
    timestamp that never existed. A DST **fold** is NOT a failure: the hour occurred twice
    and ``fold=0`` picks the earlier instant, which is a decided answer to a real question
    (A1). The asymmetry is the decision; see :mod:`entropia.shared.dst`.

    The gap reuses the SAME ``timezone_unresolved`` channel the ``source_zone is None`` case
    already uses — a third reason for a shipped fail-closed branch, not a new mechanism."""
    if moment.tzinfo is not None:
        return TimestampParse(moment.astimezone(UTC))
    if source_zone is None:
        return TimestampParse(None, timezone_unresolved=True)
    if is_nonexistent_local_time(moment, source_zone):
        return TimestampParse(None, timezone_unresolved=True)
    return TimestampParse(moment.replace(tzinfo=source_zone).astimezone(UTC))


def _resolve_timestamp_str(text: str, source_zone: ZoneInfo | None) -> TimestampParse:
    stripped = text.strip()
    if not stripped:
        return TimestampParse(None)
    iso = f"{stripped[:-1]}+00:00" if stripped.endswith("Z") else stripped
    try:
        parsed: datetime | None = datetime.fromisoformat(iso)
    except ValueError:
        parsed = None
    if parsed is not None:
        return _localize(parsed, source_zone)
    try:
        return TimestampParse(_from_epoch(float(stripped)))
    except ValueError:
        return TimestampParse(None)


def _from_epoch(value: float) -> datetime | None:
    seconds = value / 1000 if abs(value) >= _MILLISECOND_EPOCH_THRESHOLD else value
    try:
        return datetime.fromtimestamp(seconds, UTC)
    except (OverflowError, OSError, ValueError):
        return None


def cadence_seconds(resolution_value: str | None) -> int | None:
    """Declared bar cadence in seconds (``"1m"``/``"15m"``/``"1h"``/``"1D"`` …).

    A bare integer is read as minutes (``"60"`` -> 3600). ``None`` when the value
    is absent or not a positive cadence."""
    if not resolution_value:
        return None
    text = resolution_value.strip().lower()
    if not text:
        return None
    unit = text[-1]
    if unit in _CADENCE_UNIT_SECONDS and text[:-1].isdigit():
        quantity = int(text[:-1])
        return quantity * _CADENCE_UNIT_SECONDS[unit] if quantity > 0 else None
    if text.isdigit():
        quantity = int(text)
        return quantity * 60 if quantity > 0 else None
    return None


def evaluate_cross_row(
    market_data_type: MarketDataType,
    rows: list[dict[str, Any]],
    *,
    source_zone: ZoneInfo | None,
    resolution_kind: ResolutionKind | None = None,
    resolution_value: str | None = None,
    spread_unit: str | None = None,
) -> CrossRowReport:
    """Aggregate cross-row validation (doc 11 §7.4).

    ``source_zone`` is the revision's declared source timezone (keyword-ONLY and
    REQUIRED — K-01: there is no UTC default to fall back to silently).

    * naive timestamp with no resolvable source zone -> BLOCKING_FAIL.
    * unresolvable timestamp -> BLOCKING_FAIL (an unorderable row).
    * non-monotonic timestamp (out-of-order in delivered order) -> BLOCKING_FAIL.
    * duplicate ``instrument+timestamp+resolution`` -> BLOCKING_FAIL. Instrument and
      resolution are fixed per revision, so the key reduces to the timestamp.
    * declared cadence gap (OHLCV bar data) -> WARNING + a coverage segment per run.
    * undeclared spread unit (spread/execution) -> WARNING.

    Coverage segments are produced for EVERY data type (O-29). Declared-cadence OHLCV
    bars are segmented against that cadence; tick/trades, spread/execution and any bar
    series whose cadence is unreadable are segmented by consecutive covered UTC days
    (:func:`_build_daily_coverage`). Only the cadence path raises ``CADENCE_GAP``.

    Blocking findings force the revision to NEEDS_REVIEW (never auto-verified), so a
    corrupt series cannot reach APPROVED and feed the money-sizing engine."""
    issues: list[CrossRowIssue] = []

    resolved: list[datetime] = []
    unresolved = 0
    timezone_unresolved = 0
    for row in rows:
        parse = resolve_timestamp(row.get("timestamp"), source_zone=source_zone)
        if parse.moment is not None:
            resolved.append(parse.moment)
        elif parse.timezone_unresolved:
            timezone_unresolved += 1
        else:
            unresolved += 1

    # K-01: a naive cell the declared timezone cannot localize is its OWN blocking
    # finding, distinct from a garbage cell. Reading it as UTC would silently shift
    # every bar by the source offset and still auto-verify (doc 11 §9.1).
    if timezone_unresolved:
        issues.append(
            CrossRowIssue(
                ValidationStatus.BLOCKING_FAIL,
                TIMEZONE_UNRESOLVED_RULE_CODE,
                "One or more rows carry a naive timestamp that the declared source "
                "timezone cannot resolve to a UTC instant.",
                timezone_unresolved,
            )
        )

    if unresolved:
        issues.append(
            CrossRowIssue(
                ValidationStatus.BLOCKING_FAIL,
                "TIMESTAMP_UNRESOLVABLE",
                "One or more rows have a missing or unparseable timestamp.",
                unresolved,
            )
        )

    out_of_order = sum(1 for prev, cur in pairwise(resolved) if cur < prev)
    if out_of_order:
        issues.append(
            CrossRowIssue(
                ValidationStatus.BLOCKING_FAIL,
                "TIMESTAMP_NON_MONOTONIC",
                "Timestamps are not in non-decreasing order.",
                out_of_order,
            )
        )

    counts = Counter(resolved)
    duplicate_groups = [moment for moment, n in counts.items() if n > 1]
    if duplicate_groups:
        issues.append(
            CrossRowIssue(
                ValidationStatus.BLOCKING_FAIL,
                "DUPLICATE_TIMESTAMP",
                "Duplicate rows share the same instrument+timestamp+resolution.",
                sum(counts[m] - 1 for m in duplicate_groups),
                sample={"duplicate_groups": len(duplicate_groups)},
            )
        )

    # O-29: every analyzed revision that resolved at least one timestamp records its
    # coverage. Which SEGMENTATION applies depends on whether a cadence was declared,
    # not on the data type: only a declared cadence can say that a step is too wide.
    coverage: tuple[CoverageSegment, ...] = ()
    cadence = cadence_seconds(resolution_value) if resolution_kind == ResolutionKind.BAR else None
    if counts:
        if market_data_type == MarketDataType.OHLCV and cadence is not None:
            segments, gap_count = _build_coverage(counts, cadence)
            if gap_count:
                issues.append(
                    CrossRowIssue(
                        ValidationStatus.WARNING,
                        "CADENCE_GAP",
                        "Declared cadence gaps detected between consecutive bars.",
                        gap_count,
                    )
                )
        else:
            segments = _build_daily_coverage(counts)
        coverage = tuple(segments)

    if market_data_type == MarketDataType.SPREAD_EXECUTION:
        declared = (spread_unit or "").strip().lower()
        if declared not in _DECLARED_SPREAD_UNITS:
            issues.append(
                CrossRowIssue(
                    ValidationStatus.WARNING,
                    "SPREAD_UNIT_UNDECLARED",
                    "Spread unit (absolute/bps/percent) is not declared.",
                    1,
                )
            )

    worst = ValidationStatus.PASS
    for issue in issues:
        if _SEVERITY_RANK[issue.severity] > _SEVERITY_RANK[worst]:
            worst = issue.severity
    return CrossRowReport(worst=worst, issues=tuple(issues), coverage=coverage)


def _build_coverage(counts: Counter[datetime], cadence: int) -> tuple[list[CoverageSegment], int]:
    """Split the sorted unique timestamps into contiguous coverage segments.

    A step wider than one cadence interval closes the current segment and records
    the gap that follows it; the final segment carries no trailing gap."""
    ordered = sorted(counts)
    segments: list[CoverageSegment] = []
    gap_count = 0
    start = ordered[0]
    end = ordered[0]
    row_count = counts[ordered[0]]
    for prev, cur in pairwise(ordered):
        delta = (cur - prev).total_seconds()
        if delta > cadence:
            segments.append(CoverageSegment(start, end, row_count, Decimal(str(delta))))
            gap_count += 1
            start = cur
            row_count = 0
        end = cur
        row_count += counts[cur]
    segments.append(CoverageSegment(start, end, row_count, None))
    return segments, gap_count


def _build_daily_coverage(counts: Counter[datetime]) -> list[CoverageSegment]:
    """Split cadence-less timestamps into runs of consecutive covered UTC days (O-29).

    Event-based data (tick/trades, spread/execution) declares no step, so there is no
    interval a gap could be measured against. The boundary used instead is the system's
    OWN coverage granularity: the processed asset is written in instrument + date
    partitions (doc 11 §7.3 step 5), so a calendar day with no row closes the current
    segment. Nothing is inferred — the day is a declared structural unit, not a tuned
    threshold, and ``gap_seconds`` on the closed segment is the real distance to the
    next observed instant.

    No gap finding is raised here: for a "selected sessions" dataset (doc 11 §3.3's
    tick row) an absent day is intent, not a defect, and §7.4 lists cadence gaps only
    under OHLCV. The segments are recorded, never judged."""
    ordered = sorted(counts)
    segments: list[CoverageSegment] = []
    start = ordered[0]
    end = ordered[0]
    row_count = counts[ordered[0]]
    for prev, cur in pairwise(ordered):
        if (cur.date() - prev.date()).days > 1:
            gap = Decimal(str((cur - prev).total_seconds()))
            segments.append(CoverageSegment(start, end, row_count, gap))
            start = cur
            row_count = 0
        end = cur
        row_count += counts[cur]
    segments.append(CoverageSegment(start, end, row_count, None))
    return segments
