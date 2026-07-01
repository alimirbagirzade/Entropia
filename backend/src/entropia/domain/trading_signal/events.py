"""Pure signal-event parsing + normalization (Stage 3c, doc 04 §5.1, §9.3).

This module is INFRA-FREE and deterministic: it takes raw bytes (or already-parsed
rows) and produces a normalized event set + a skipped-row report. The durable
import worker (``application/jobs/trading_signal.py``) wires object storage +
persistence around it; everything decision-making lives here so it is unit-testable
with no database or MinIO.

Canonical rule (doc 04 §5.1): a signal event must resolve at least
``source_record_id``, ``event_time``, ``available_time``, ``instrument_id``,
``direction`` and ``signal_type``. The backtest may only evaluate an event AFTER
``available_time`` (anti-lookahead) — a missing/ambiguous availability is a
blocker, never inferred from render/import time.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from entropia.domain.trading_signal.enums import (
    NormalizedRevisionStatus,
    SignalDirection,
    SignalType,
)

# --- skip / blocker reason codes (surfaced in the skipped-row report) --------
REASON_SOURCE_RECORD_ID_MISSING = "SOURCE_RECORD_ID_MISSING"
REASON_EVENT_TIME_INVALID = "EVENT_TIME_INVALID"
REASON_EVENT_TIME_FUTURE = "EVENT_TIME_FUTURE"
REASON_AVAILABLE_TIME_REQUIRED = "AVAILABLE_TIME_REQUIRED"
REASON_AVAILABLE_TIME_INVALID = "AVAILABLE_TIME_INVALID"
REASON_INVALID_SIGNAL_DIRECTION = "INVALID_SIGNAL_DIRECTION"
REASON_SIGNAL_TYPE_UNMAPPED = "SIGNAL_TYPE_UNMAPPED"
REASON_INSTRUMENT_MISMATCH = "INSTRUMENT_MISMATCH"
REASON_DUPLICATE_SOURCE_RECORD_ID = "DUPLICATE_SOURCE_RECORD_ID"

# --- whole-file blocker codes (no accepted events possible) ------------------
BLOCKER_LEGACY_TRADE_LOG_SCHEMA = "LEGACY_TRADE_LOG_SCHEMA"
BLOCKER_NO_ACCEPTED_SIGNAL_EVENTS = "NO_ACCEPTED_SIGNAL_EVENTS"
BLOCKER_AVAILABLE_TIME_REQUIRED = "AVAILABLE_TIME_REQUIRED"

_DELIMITERS = (",", ";", "\t", "|")

# Canonical inbound instrument columns (V1 accepts canonically-named files).
_INSTRUMENT_COLUMNS = ("instrument_id", "instrument", "symbol")
_LEGACY_COLUMNS = ("entry_time", "exit_time", "entry_price", "exit_price")

_DIRECTION_ALIASES: dict[str, SignalDirection] = {
    "long": SignalDirection.LONG,
    "buy": SignalDirection.LONG,
    "l": SignalDirection.LONG,
    "1": SignalDirection.LONG,
    "short": SignalDirection.SHORT,
    "sell": SignalDirection.SHORT,
    "s": SignalDirection.SHORT,
    "-1": SignalDirection.SHORT,
}

_SIGNAL_TYPE_ALIASES: dict[str, SignalType] = {
    "entry": SignalType.ENTRY,
    "open": SignalType.ENTRY,
    "exit_hint": SignalType.EXIT_HINT,
    "exit": SignalType.EXIT_HINT,
    "scale_hint": SignalType.SCALE_HINT,
    "scale": SignalType.SCALE_HINT,
    "add": SignalType.SCALE_HINT,
    "close": SignalType.CLOSE,
    "flat": SignalType.CLOSE,
    "provider_custom": SignalType.PROVIDER_CUSTOM,
}


@dataclass(frozen=True, slots=True)
class NormalizedSignalEvent:
    """One accepted, time-safe, canonical signal event."""

    event_id: str
    source_record_id: str
    event_time: str  # UTC ISO-8601
    available_time: str  # UTC ISO-8601 (>= event_time)
    instrument_id: str
    direction: str
    signal_type: str
    suggested_entry_price: str | None = None
    suggested_exit_price: str | None = None
    confidence: str | None = None


@dataclass(frozen=True, slots=True)
class SkippedRow:
    """A rejected source row retained as evidence (never silently dropped)."""

    row_index: int
    reason_code: str
    message: str
    source_record_id: str | None = None


@dataclass(slots=True)
class ImportOutcome:
    """Aggregate result of parsing + normalizing a source asset."""

    status: NormalizedRevisionStatus
    accepted: list[NormalizedSignalEvent] = field(default_factory=list)
    skipped: list[SkippedRow] = field(default_factory=list)
    earliest_available_time: datetime | None = None
    instrument_id: str | None = None
    blocker_code: str | None = None

    @property
    def accepted_count(self) -> int:
        return len(self.accepted)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


def parse_delimited(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Decode + parse CSV/TXT bytes into ``(columns, rows)`` (V1, pure).

    Delimiter is sniffed from a candidate set (comma/semicolon/tab/pipe). The first
    line is the header. Values are stripped; empty strings are preserved as ``""``.
    """
    text = data.decode("utf-8-sig", errors="replace")
    if not text.strip():
        return [], []
    first_line = text.splitlines()[0]
    delimiter = max(_DELIMITERS, key=first_line.count)
    if first_line.count(delimiter) == 0:
        delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    columns = [c.strip() for c in (reader.fieldnames or [])]
    rows: list[dict[str, str]] = []
    for record in reader:
        rows.append({(k or "").strip(): (v or "").strip() for k, v in record.items()})
    return columns, rows


def normalize_signal_rows(
    columns: list[str],
    rows: list[dict[str, str]],
    *,
    source_timezone: str,
    instrument_id: str,
    now: datetime | None = None,
) -> ImportOutcome:
    """Normalize parsed rows into a time-safe event set (pure, deterministic).

    ``instrument_id`` is the root's canonical instrument scope; rows whose symbol
    disagrees are skipped (``INSTRUMENT_MISMATCH``). ``now`` seams the clock for the
    future-event check (defaults to ``datetime.now(UTC)``). A file that looks like a
    Trade Log ledger (entry/exit columns, no signal-event mapping) is a whole-file
    blocker so the user is directed to the Trade Log flow (doc 04 §5.1, TS-06).
    """
    clock = now if now is not None else datetime.now(UTC)
    if _is_legacy_trade_log(columns):
        return ImportOutcome(
            status=NormalizedRevisionStatus.FAILED,
            blocker_code=BLOCKER_LEGACY_TRADE_LOG_SCHEMA,
            instrument_id=instrument_id,
        )

    tz = _resolve_timezone(source_timezone)
    outcome = ImportOutcome(status=NormalizedRevisionStatus.PENDING, instrument_id=instrument_id)
    seen: set[str] = set()
    available_seen = False

    for index, row in enumerate(rows):
        result = _normalize_one(row, index, tz=tz, instrument_id=instrument_id, clock=clock)
        if isinstance(result, SkippedRow):
            if result.reason_code in (
                REASON_AVAILABLE_TIME_REQUIRED,
                REASON_AVAILABLE_TIME_INVALID,
            ):
                available_seen = True
            outcome.skipped.append(result)
            continue
        if result.source_record_id in seen:
            outcome.skipped.append(
                SkippedRow(
                    row_index=index,
                    reason_code=REASON_DUPLICATE_SOURCE_RECORD_ID,
                    message="Duplicate source_record_id for this provider was ignored.",
                    source_record_id=result.source_record_id,
                )
            )
            continue
        seen.add(result.source_record_id)
        outcome.accepted.append(result)

    _finalize(outcome, available_seen=available_seen)
    return outcome


def _finalize(outcome: ImportOutcome, *, available_seen: bool) -> None:
    if outcome.accepted:
        outcome.status = NormalizedRevisionStatus.SUCCEEDED
        earliest = min(datetime.fromisoformat(e.available_time) for e in outcome.accepted)
        outcome.earliest_available_time = earliest
        return
    outcome.status = NormalizedRevisionStatus.FAILED
    # Prefer the availability blocker so the UI shows the canonical remediation.
    outcome.blocker_code = (
        BLOCKER_AVAILABLE_TIME_REQUIRED if available_seen else BLOCKER_NO_ACCEPTED_SIGNAL_EVENTS
    )


def _normalize_one(
    row: dict[str, str],
    index: int,
    *,
    tz: ZoneInfo,
    instrument_id: str,
    clock: datetime,
) -> NormalizedSignalEvent | SkippedRow:
    source_record_id = row.get("source_record_id", "").strip()
    if not source_record_id:
        return SkippedRow(index, REASON_SOURCE_RECORD_ID_MISSING, "Missing source_record_id.")

    event_time = _parse_time(row.get("event_time", ""), tz)
    if event_time is None:
        return SkippedRow(
            index,
            REASON_EVENT_TIME_INVALID,
            "event_time is missing or unparseable.",
            source_record_id,
        )
    if event_time > clock:
        return SkippedRow(
            index, REASON_EVENT_TIME_FUTURE, "event_time is in the future.", source_record_id
        )

    raw_available = row.get("available_time", "").strip()
    if not raw_available:
        return SkippedRow(
            index, REASON_AVAILABLE_TIME_REQUIRED, "available_time is required.", source_record_id
        )
    available_time = _parse_time(raw_available, tz)
    if available_time is None:
        return SkippedRow(
            index, REASON_AVAILABLE_TIME_INVALID, "available_time is unparseable.", source_record_id
        )
    if available_time < event_time:
        return SkippedRow(
            index,
            REASON_AVAILABLE_TIME_INVALID,
            "available_time cannot precede event_time.",
            source_record_id,
        )

    symbol = _row_instrument(row)
    if symbol and symbol.upper() != instrument_id.upper():
        return SkippedRow(
            index,
            REASON_INSTRUMENT_MISMATCH,
            f"Row symbol {symbol!r} is out of scope.",
            source_record_id,
        )

    direction = _DIRECTION_ALIASES.get(row.get("direction", "").strip().lower())
    if direction is None:
        return SkippedRow(
            index, REASON_INVALID_SIGNAL_DIRECTION, "direction is not long/short.", source_record_id
        )

    signal_type = _SIGNAL_TYPE_ALIASES.get(row.get("signal_type", "").strip().lower())
    if signal_type is None:
        return SkippedRow(
            index,
            REASON_SIGNAL_TYPE_UNMAPPED,
            "signal_type has no canonical mapping.",
            source_record_id,
        )

    return NormalizedSignalEvent(
        event_id=_event_id(instrument_id, source_record_id, event_time),
        source_record_id=source_record_id,
        event_time=event_time.isoformat(),
        available_time=available_time.isoformat(),
        instrument_id=instrument_id,
        direction=direction.value,
        signal_type=signal_type.value,
        suggested_entry_price=_optional_price(row.get("suggested_entry_price")),
        suggested_exit_price=_optional_price(row.get("suggested_exit_price")),
        confidence=_optional_price(row.get("confidence")),
    )


def _is_legacy_trade_log(columns: list[str]) -> bool:
    lowered = {c.lower() for c in columns}
    has_legacy = {"entry_time", "exit_time"} <= lowered and bool(
        lowered & {"entry_price", "exit_price"}
    )
    has_signal_mapping = bool(lowered & {"event_time", "available_time", "source_record_id"})
    return has_legacy and not has_signal_mapping


def _row_instrument(row: dict[str, str]) -> str:
    for col in _INSTRUMENT_COLUMNS:
        value = row.get(col, "").strip()
        if value:
            return value
    return ""


def _resolve_timezone(source_timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(source_timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return ZoneInfo("UTC")


def _parse_time(value: str, tz: ZoneInfo) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(UTC)


def _optional_price(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _event_id(instrument_id: str, source_record_id: str, event_time: datetime) -> str:
    """Deterministic server-side canonical event id (doc 04 ID-04-01).

    Derived so a re-import of identical rows yields identical event ids (and thus a
    stable normalized content hash) — the id is NOT taken from the source.
    """
    seed = f"{instrument_id}|{source_record_id}|{event_time.isoformat()}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:26]
    return f"sigevt_{digest}"


def events_content_hash(events: list[NormalizedSignalEvent]) -> str:
    """Deterministic SHA-256 over the ordered accepted event set."""
    parts = [
        "|".join(
            [
                e.event_id,
                e.source_record_id,
                e.event_time,
                e.available_time,
                e.instrument_id,
                e.direction,
                e.signal_type,
                e.suggested_entry_price or "",
                e.suggested_exit_price or "",
                e.confidence or "",
            ]
        )
        for e in events
    ]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
