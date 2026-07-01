"""Pure trade-record parsing + normalization (Stage 3d, doc 05 §5.4, §10.3).

This module is INFRA-FREE and deterministic: it takes raw bytes (or already-parsed
rows) and produces a canonical trade-record set + a skipped-row report. The durable
import worker (``application/jobs/trade_log.py``) wires object storage + persistence
around it; everything decision-making lives here so it is unit-testable with no
database or MinIO.

Canonical rule (doc 05 §5.4): a trade record must resolve ``direction``,
``entry_time``, ``entry_price``, ``exit_time`` and ``exit_price``. Missing any
required COLUMN is a whole-file blocker (``REQUIRED_COLUMN_MISSING``, TL-05); an
individual bad row is skipped with a reason and retained as evidence — never
silently corrected or dropped (Implementation Rule 6, TL-07/TL-08).
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from entropia.domain.trade_log.enums import RecordBatchStatus, TradeDirection

# --- skip reason codes (surfaced per-row in the skipped-row report) ----------
REASON_DIRECTION_INVALID = "INVALID_TRADE_DIRECTION"
REASON_ENTRY_TIME_INVALID = "ENTRY_TIME_INVALID"
REASON_EXIT_TIME_INVALID = "EXIT_TIME_INVALID"
REASON_EXIT_BEFORE_ENTRY = "EXIT_BEFORE_ENTRY"
REASON_ENTRY_PRICE_INVALID = "ENTRY_PRICE_INVALID"
REASON_EXIT_PRICE_INVALID = "EXIT_PRICE_INVALID"
REASON_SIZE_INVALID = "SIZE_INVALID"
REASON_FEES_INVALID = "FEES_INVALID"
REASON_INSTRUMENT_MISMATCH = "INSTRUMENT_MISMATCH"

# --- non-destructive warning codes (row still accepted) ----------------------
WARN_PNL_MISMATCH = "PNL_MISMATCH"

# --- whole-file blocker codes (no accepted records possible) -----------------
BLOCKER_REQUIRED_COLUMN_MISSING = "REQUIRED_COLUMN_MISSING"
BLOCKER_TIMEZONE_INVALID = "TIMEZONE_INVALID"
BLOCKER_NO_ACCEPTED_TRADE_RECORDS = "NO_ACCEPTED_TRADE_RECORDS"

_DELIMITERS = (",", ";", "\t", "|")

_REQUIRED_COLUMNS = ("direction", "entry_time", "entry_price", "exit_time", "exit_price")
_INSTRUMENT_COLUMNS = ("symbol", "instrument", "instrument_id")

_DIRECTION_ALIASES: dict[str, TradeDirection] = {
    "long": TradeDirection.LONG,
    "buy": TradeDirection.LONG,
    "l": TradeDirection.LONG,
    "1": TradeDirection.LONG,
    "short": TradeDirection.SHORT,
    "sell": TradeDirection.SHORT,
    "s": TradeDirection.SHORT,
    "-1": TradeDirection.SHORT,
}

# Relative P&L tolerance before a source-reported pnl is flagged (non-destructive).
_PNL_REL_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class CanonicalTradeRecord:
    """One accepted, normalized historical trade record (entry/exit ledger)."""

    record_id: str
    direction: str
    entry_time: str  # UTC ISO-8601
    entry_price: str
    exit_time: str  # UTC ISO-8601 (>= entry_time)
    exit_price: str
    instrument_id: str
    size: str | None = None
    fees: str | None = None
    pnl: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SkippedRow:
    """A rejected source row retained as evidence (never silently dropped)."""

    row_index: int
    reason_code: str
    message: str


@dataclass(slots=True)
class ImportOutcome:
    """Aggregate result of parsing + normalizing a source asset."""

    status: RecordBatchStatus
    accepted: list[CanonicalTradeRecord] = field(default_factory=list)
    skipped: list[SkippedRow] = field(default_factory=list)
    earliest_entry_time: datetime | None = None
    latest_exit_time: datetime | None = None
    instrument_id: str | None = None
    blocker_code: str | None = None

    @property
    def accepted_count(self) -> int:
        return len(self.accepted)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def warning_count(self) -> int:
        return sum(len(r.warnings) for r in self.accepted)


def parse_delimited(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Decode + parse CSV/TXT bytes into ``(columns, rows)`` (V1, pure).

    Delimiter is sniffed from a candidate set (comma/semicolon/tab/pipe). The first
    line is the header. Values are stripped; empty strings are preserved as ``""``.
    A quoting-aware ``csv.DictReader`` handles embedded delimiters (TL-06).
    """
    text = data.decode("utf-8-sig", errors="replace")
    if not text.strip():
        return [], []
    first_line = text.splitlines()[0]
    delimiter = max(_DELIMITERS, key=first_line.count)
    if first_line.count(delimiter) == 0:
        delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    # Canonicalize header keys to lowercase so the required-column blocker and every
    # per-row lookup agree regardless of source-file header casing (broker/MT4/MT5
    # exports emit capitalized headers). Values keep their original case.
    columns = [c.strip().lower() for c in (reader.fieldnames or [])]
    rows: list[dict[str, str]] = []
    for record in reader:
        rows.append({(k or "").strip().lower(): (v or "").strip() for k, v in record.items()})
    return columns, rows


def normalize_trade_rows(
    columns: list[str],
    rows: list[dict[str, str]],
    *,
    source_timezone: str,
    instrument_id: str,
) -> ImportOutcome:
    """Normalize parsed rows into a canonical trade-record set (pure, deterministic).

    ``instrument_id`` is the root's canonical instrument scope; rows whose symbol
    disagrees are skipped (``INSTRUMENT_MISMATCH``, TL-09). A file missing any
    required column is a whole-file blocker (``REQUIRED_COLUMN_MISSING``, TL-05); an
    invalid/ambiguous timezone is a whole-file blocker (``TIMEZONE_INVALID``, TL-07).
    """
    missing = _missing_required_columns(columns)
    if missing:
        return ImportOutcome(
            status=RecordBatchStatus.FAILED,
            blocker_code=BLOCKER_REQUIRED_COLUMN_MISSING,
            instrument_id=instrument_id,
        )

    tz = _resolve_timezone(source_timezone)
    if tz is None:
        return ImportOutcome(
            status=RecordBatchStatus.FAILED,
            blocker_code=BLOCKER_TIMEZONE_INVALID,
            instrument_id=instrument_id,
        )

    outcome = ImportOutcome(status=RecordBatchStatus.PENDING, instrument_id=instrument_id)
    for index, row in enumerate(rows):
        result = _normalize_one(row, index, tz=tz, instrument_id=instrument_id)
        if isinstance(result, SkippedRow):
            outcome.skipped.append(result)
            continue
        outcome.accepted.append(result)

    _finalize(outcome)
    return outcome


def _finalize(outcome: ImportOutcome) -> None:
    if not outcome.accepted:
        outcome.status = RecordBatchStatus.FAILED
        outcome.blocker_code = BLOCKER_NO_ACCEPTED_TRADE_RECORDS
        return
    outcome.status = RecordBatchStatus.SUCCEEDED
    outcome.earliest_entry_time = min(
        datetime.fromisoformat(r.entry_time) for r in outcome.accepted
    )
    outcome.latest_exit_time = max(datetime.fromisoformat(r.exit_time) for r in outcome.accepted)


def _normalize_one(
    row: dict[str, str],
    index: int,
    *,
    tz: ZoneInfo,
    instrument_id: str,
) -> CanonicalTradeRecord | SkippedRow:
    symbol = _row_instrument(row)
    if symbol and symbol.upper() != instrument_id.upper():
        return SkippedRow(
            index, REASON_INSTRUMENT_MISMATCH, f"Row symbol {symbol!r} is out of scope."
        )

    direction = _DIRECTION_ALIASES.get(row.get("direction", "").strip().lower())
    if direction is None:
        return SkippedRow(index, REASON_DIRECTION_INVALID, "direction is not long/short.")

    entry_time = _parse_time(row.get("entry_time", ""), tz)
    if entry_time is None:
        return SkippedRow(index, REASON_ENTRY_TIME_INVALID, "entry_time is missing or unparseable.")

    exit_time = _parse_time(row.get("exit_time", ""), tz)
    if exit_time is None:
        return SkippedRow(index, REASON_EXIT_TIME_INVALID, "exit_time is missing or unparseable.")
    if exit_time < entry_time:
        return SkippedRow(index, REASON_EXIT_BEFORE_ENTRY, "exit_time precedes entry_time.")

    entry_price = _parse_positive_price(row.get("entry_price", ""))
    if entry_price is None:
        return SkippedRow(
            index, REASON_ENTRY_PRICE_INVALID, "entry_price is not a positive finite number."
        )

    exit_price = _parse_positive_price(row.get("exit_price", ""))
    if exit_price is None:
        return SkippedRow(
            index, REASON_EXIT_PRICE_INVALID, "exit_price is not a positive finite number."
        )

    size, size_err = _parse_optional_positive(row.get("size"))
    if size_err:
        return SkippedRow(index, REASON_SIZE_INVALID, "size is not a positive finite number.")

    fees, fees_err = _parse_optional_non_negative(row.get("fees"))
    if fees_err:
        return SkippedRow(index, REASON_FEES_INVALID, "fees is not a non-negative finite number.")

    pnl = _optional_text(row.get("pnl"))
    warnings = _pnl_warnings(direction, entry_price, exit_price, size, pnl)

    return CanonicalTradeRecord(
        record_id=_record_id(
            instrument_id,
            direction.value,
            entry_time,
            exit_time,
            str(entry_price),
            str(exit_price),
        ),
        direction=direction.value,
        entry_time=entry_time.isoformat(),
        entry_price=str(entry_price),
        exit_time=exit_time.isoformat(),
        exit_price=str(exit_price),
        instrument_id=instrument_id,
        size=str(size) if size is not None else None,
        fees=str(fees) if fees is not None else None,
        pnl=pnl,
        warnings=warnings,
    )


def _pnl_warnings(
    direction: TradeDirection,
    entry_price: Decimal,
    exit_price: Decimal,
    size: Decimal | None,
    pnl: str | None,
) -> tuple[str, ...]:
    """Flag (never overwrite) a source-reported pnl that disagrees with price/size."""
    if pnl is None or size is None:
        return ()
    try:
        reported = Decimal(pnl)
    except (InvalidOperation, ValueError):
        return ()
    if not reported.is_finite():
        return ()
    sign = Decimal(1) if direction == TradeDirection.LONG else Decimal(-1)
    expected = (exit_price - entry_price) * size * sign
    scale = max(abs(expected), Decimal(1))
    if abs(reported - expected) > _PNL_REL_TOLERANCE * scale:
        return (WARN_PNL_MISMATCH,)
    return ()


def _missing_required_columns(columns: list[str]) -> list[str]:
    lowered = {c.lower() for c in columns}
    return [c for c in _REQUIRED_COLUMNS if c not in lowered]


def _row_instrument(row: dict[str, str]) -> str:
    for col in _INSTRUMENT_COLUMNS:
        value = row.get(col, "").strip()
        if value:
            return value
    return ""


def _resolve_timezone(source_timezone: str) -> ZoneInfo | None:
    try:
        return ZoneInfo(source_timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return None


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


def _parse_positive_price(value: str) -> Decimal | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    return parsed


def _parse_optional_positive(value: str | None) -> tuple[Decimal | None, bool]:
    text = (value or "").strip()
    if not text:
        return None, False
    parsed = _parse_positive_price(text)
    return (parsed, parsed is None)


def _parse_optional_non_negative(value: str | None) -> tuple[Decimal | None, bool]:
    text = (value or "").strip()
    if not text:
        return None, False
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None, True
    if not parsed.is_finite() or parsed < 0:
        return None, True
    return parsed, False


def _optional_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _record_id(
    instrument_id: str,
    direction: str,
    entry_time: datetime,
    exit_time: datetime,
    entry_price: str,
    exit_price: str,
) -> str:
    """Deterministic server-side canonical record id.

    Derived so a re-import of identical rows yields identical record ids (and thus a
    stable batch content hash) — the id is NOT taken from the source file. Price is
    part of the seed so two distinct same-minute trades never share an id.
    """
    seed = (
        f"{instrument_id}|{direction}|{entry_time.isoformat()}|{exit_time.isoformat()}"
        f"|{entry_price}|{exit_price}"
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:26]
    return f"tlrec_{digest}"


def records_content_hash(records: list[CanonicalTradeRecord]) -> str:
    """Deterministic SHA-256 over the ordered accepted record set."""
    parts = [
        "|".join(
            [
                r.record_id,
                r.direction,
                r.entry_time,
                r.entry_price,
                r.exit_time,
                r.exit_price,
                r.instrument_id,
                r.size or "",
                r.fees or "",
                r.pnl or "",
            ]
        )
        for r in records
    ]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
