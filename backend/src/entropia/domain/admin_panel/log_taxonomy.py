"""Log-event taxonomy + opaque keyset cursor for the Admin Logs projection (doc 19
§4.3, §6.2). Server-owned taxonomy — the client never asserts a family/severity as
authority; it hydrates the option list from these constants and the server rejects
unknown values. Ordering is newest-first on ``(occurred_at, event_id)``; the cursor
carries that composite key so pages are stable across ties (doc 19 §5, §13)."""

from __future__ import annotations

from entropia.domain.agent_lab.cursor import decode_cursor, encode_cursor
from entropia.domain.lifecycle.enums import ActorKind
from entropia.shared.errors import CursorInvalidError, LogFilterInvalidError

LOGS_CURSOR_NAMESPACE = "admin_logs"
_CURSOR_SEP = "|"

# Canonical event families (doc 19 §6.2). ``all`` = no filter; ``system_other`` =
# anything not claimed by a named family. Values are the server taxonomy, not
# hard-coded client authority.
LOG_EVENT_FAMILIES: tuple[str, ...] = (
    "all",
    "role_access",
    "backtest",
    "data",
    "package",
    "strategy",
    "agent",
    "trash_lifecycle",
    "system_other",
)

# A family owns a set of ``event_kind`` prefixes. An event_kind is dotted/underscored
# (e.g. ``user.role_assigned``, ``backtest.run_failed``, ``agent.runtime.pause``).
_FAMILY_PREFIXES: dict[str, tuple[str, ...]] = {
    "role_access": ("user.", "role", "access", "auth"),
    "backtest": ("backtest", "run.", "result"),
    "data": ("dataset", "market_data", "research_data", "import"),
    "package": ("package",),
    "strategy": ("strategy",),
    "agent": ("agent",),
    "trash_lifecycle": ("delete", "restore", "purge", "trash", "lifecycle"),
}

LOG_SEVERITIES: tuple[str, ...] = ("info", "warning", "error")

# Logs actor filter (doc 19 §6.2) -> canonical ActorKind.
ACTOR_TYPE_TO_KIND: dict[str, ActorKind] = {
    "human": ActorKind.HUMAN,
    "system_agent": ActorKind.AGENT,
    "system": ActorKind.SYSTEM_SERVICE,
}


def event_family(event_kind: str) -> str:
    """Classify an ``event_kind`` into its canonical family (``system_other`` if no
    named family claims a token). FIRST match wins by family declaration order, so a
    kind that contains tokens from two families is owned by the earlier one. The SQL
    filter in ``log_projection`` mirrors this exactly (substring + first-match)."""
    kind = event_kind.lower()
    for family, prefixes in _FAMILY_PREFIXES.items():
        if any(token in kind for token in prefixes):
            return family
    return "system_other"


def family_kind_prefixes(family: str) -> tuple[str, ...]:
    """Return the ``event_kind`` prefixes owned by a named family. Empty for
    ``all``/``system_other`` (those are handled by the query, not by prefixes)."""
    return _FAMILY_PREFIXES.get(family, ())


def normalize_family(value: str | None) -> str:
    """Return a valid family slug (default ``all``); reject unknown values."""
    if value is None or value == "":
        return "all"
    slug = value.strip().lower()
    if slug not in LOG_EVENT_FAMILIES:
        raise LogFilterInvalidError(f"Unknown event family '{value}'.")
    return slug


def normalize_severity(value: str | None) -> str | None:
    """Return a valid severity (``None`` = all); reject unknown values."""
    if value is None or value == "":
        return None
    sev = value.strip().lower()
    if sev not in LOG_SEVERITIES:
        raise LogFilterInvalidError(f"Unknown severity '{value}'.")
    return sev


def normalize_actor_type(value: str | None) -> ActorKind | None:
    """Return the canonical ``ActorKind`` for an actor filter (``None`` = all)."""
    if value is None or value == "":
        return None
    key = value.strip().lower()
    if key not in ACTOR_TYPE_TO_KIND:
        raise LogFilterInvalidError(f"Unknown actor type '{value}'.")
    return ACTOR_TYPE_TO_KIND[key]


def encode_log_cursor(*, occurred_at_iso: str, event_id: str) -> str:
    """Build an opaque forward cursor pinned to the newest-first log ordering."""
    return encode_cursor(
        LOGS_CURSOR_NAMESPACE, last_key=f"{occurred_at_iso}{_CURSOR_SEP}{event_id}"
    )


def decode_log_cursor(cursor: str) -> tuple[str, str]:
    """Decode a log cursor into ``(occurred_at_iso, event_id)``; a malformed token
    is a ``CURSOR_INVALID`` recovery signal, never a silent reset to page 1."""
    decoded = decode_cursor(cursor, namespace=LOGS_CURSOR_NAMESPACE)
    occurred_at_iso, sep, event_id = decoded.last_key.partition(_CURSOR_SEP)
    if not sep or not occurred_at_iso or not event_id:
        raise CursorInvalidError()
    return occurred_at_iso, event_id


__all__ = [
    "ACTOR_TYPE_TO_KIND",
    "LOGS_CURSOR_NAMESPACE",
    "LOG_EVENT_FAMILIES",
    "LOG_SEVERITIES",
    "decode_log_cursor",
    "encode_log_cursor",
    "event_family",
    "family_kind_prefixes",
    "normalize_actor_type",
    "normalize_family",
    "normalize_severity",
]
