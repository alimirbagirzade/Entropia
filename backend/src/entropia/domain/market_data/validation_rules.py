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

from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.market_data.enums import MarketDataType, ResolutionKind, TradeSide

DecimalLike = Decimal | str | int


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


def parse_timestamp(value: Any) -> datetime | None:
    """Best-effort parse to a timezone-aware UTC datetime; ``None`` if unresolvable.

    Accepts ``datetime``/``date``, epoch seconds/milliseconds (int/float or their
    string form) and ISO-8601 strings (trailing ``Z`` allowed). A naive value is
    read as UTC. ``bool`` is rejected (it is an ``int`` subclass)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if isinstance(value, (int, float)):
        return _from_epoch(float(value))
    if isinstance(value, str):
        return _parse_timestamp_str(value)
    return None


def _parse_timestamp_str(text: str) -> datetime | None:
    stripped = text.strip()
    if not stripped:
        return None
    iso = f"{stripped[:-1]}+00:00" if stripped.endswith("Z") else stripped
    try:
        parsed: datetime | None = datetime.fromisoformat(iso)
    except ValueError:
        parsed = None
    if parsed is not None:
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    try:
        return _from_epoch(float(stripped))
    except ValueError:
        return None


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
    resolution_kind: ResolutionKind | None = None,
    resolution_value: str | None = None,
    spread_unit: str | None = None,
) -> CrossRowReport:
    """Aggregate cross-row validation (doc 11 §7.4).

    * unresolvable timestamp -> BLOCKING_FAIL (an unorderable row).
    * non-monotonic timestamp (out-of-order in delivered order) -> BLOCKING_FAIL.
    * duplicate ``instrument+timestamp+resolution`` -> BLOCKING_FAIL. Instrument and
      resolution are fixed per revision, so the key reduces to the timestamp.
    * declared cadence gap (OHLCV bar data) -> WARNING + a coverage segment per run.
    * undeclared spread unit (spread/execution) -> WARNING.

    Blocking findings force the revision to NEEDS_REVIEW (never auto-verified), so a
    corrupt series cannot reach APPROVED and feed the money-sizing engine."""
    issues: list[CrossRowIssue] = []

    resolved: list[datetime] = []
    unresolved = 0
    for row in rows:
        moment = parse_timestamp(row.get("timestamp"))
        if moment is None:
            unresolved += 1
        else:
            resolved.append(moment)

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

    coverage: tuple[CoverageSegment, ...] = ()
    cadence = cadence_seconds(resolution_value) if resolution_kind == ResolutionKind.BAR else None
    if market_data_type == MarketDataType.OHLCV and cadence is not None and counts:
        segments, gap_count = _build_coverage(counts, cadence)
        coverage = tuple(segments)
        if gap_count:
            issues.append(
                CrossRowIssue(
                    ValidationStatus.WARNING,
                    "CADENCE_GAP",
                    "Declared cadence gaps detected between consecutive bars.",
                    gap_count,
                )
            )

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
