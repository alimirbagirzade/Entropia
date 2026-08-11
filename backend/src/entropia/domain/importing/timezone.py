"""Shared source-timezone gate for the file-import surfaces (O-28).

Two rules, kept in ONE place so the Trade Log and Trading Signal twins cannot drift:

* a declared source time zone is a REAL IANA identifier — ``zoneinfo`` must resolve
  it (the pattern already used by ``domain/market_data/value_objects.py::TimezoneSpec``);
* the time zone a saved CONFIG declares is the SAME one the durable import job
  actually normalized the source timestamps under.

The second rule exists because the import receives ``source_timezone`` as a separate
job parameter (``request_trade_log_import`` / ``request_trading_signal_import``), not
from the config. Without a cross-check a config could declare ``America/New_York``
while the pinned batch was parsed as ``UTC``: every stored instant would be off by the
true offset, the save would still succeed, and the evidence would look clean. Doc 05
§5.2 rejects an invalid/ambiguous zone outright and doc 04 §5 states that a timezone
changed after import means "the normalized import revision cannot be reused as valid;
reparse/remap job required" — this module is where that is enforced.

Comparison is FAIL-CLOSED: import evidence that declares no time zone at all cannot be
shown to agree, so it counts as a disagreement rather than an assumed match.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Identifiers that all resolve to UTC. Two of these names describe ONE zone, so they
# agree by fact — not as a convenience exemption. Same list the K-01 backward-compat
# audit uses (``application/queries/timezone_audit.py``).
UTC_EQUIVALENT_IANA = ("UTC", "Etc/UTC", "Etc/GMT", "Etc/Zulu", "Universal", "Zulu")


def normalize_iana_timezone(value: str | None) -> str:
    """Trim and verify an IANA identifier, returning the canonical trimmed string.

    Raises ``ValueError`` (not an ``AppError``) so it can be called straight from a
    Pydantic ``field_validator``; the command layer maps the resulting issue to the
    page's typed 422 code.
    """
    trimmed = (value or "").strip()
    if not trimmed:
        raise ValueError("source_timezone is required.")
    try:
        ZoneInfo(trimmed)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise ValueError(f"'{trimmed}' is not a valid IANA time zone identifier.") from exc
    return trimmed


def is_valid_iana_timezone(value: str | None) -> bool:
    """Non-raising sibling of :func:`normalize_iana_timezone`."""
    try:
        normalize_iana_timezone(value)
    except ValueError:
        return False
    return True


def timezones_agree(declared: str | None, imported: str | None) -> bool:
    """Do the config's zone and the import batch's zone describe the same zone?

    Fail-closed: a blank/absent value on either side is NOT agreement.
    """
    left = (declared or "").strip()
    right = (imported or "").strip()
    if not left or not right:
        return False
    if left.casefold() == right.casefold():
        return True
    return _is_utc(left) and _is_utc(right)


def _is_utc(value: str) -> bool:
    return any(value.casefold() == alias.casefold() for alias in UTC_EQUIVALENT_IANA)


def parse_source_timestamp(value: str, tz: ZoneInfo) -> datetime | None:
    """Read one source timestamp cell and normalize it to UTC, or ``None``.

    A naive timestamp is stamped with the declared source zone ``tz`` — that is the
    whole point of the O-28 cross-check above: the zone a row is read under must be
    the zone the config declares. An offset already carried by the cell wins over
    ``tz`` (the source stated it explicitly). Unparseable or blank reads as absent
    rather than raising, so one bad cell surfaces as a row-level issue instead of
    failing the batch.

    Lives here, not in the twins, because Trade Log records and Trading Signal
    events parsed timestamps with byte-identical copies of this function.
    """
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


__all__ = [
    "UTC_EQUIVALENT_IANA",
    "is_valid_iana_timezone",
    "normalize_iana_timezone",
    "parse_source_timestamp",
    "timezones_agree",
]
