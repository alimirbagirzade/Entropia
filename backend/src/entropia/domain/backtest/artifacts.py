"""Heavy result-artifact drill-down: type registry + opaque keyset cursor.

Stage 5c, doc-15 deferred (doc 15 §3.2, §7 QueryResultArtifact, §14). The Trade
Ledger / equity curve / signal events / diagnostics are paginated SERVER-side with
a stable ascending key and an opaque base64url cursor the client cannot forge (same
shape as the Stage 5b Results-History cursor). The cursor carries a generic string
key: the ``seq`` (as text) for the seq-ordered artifacts, or the row id for
diagnostics (which have no ``seq``). A Trade Ledger row is a trade ROOT (one per
fully closed trade) — fills / scaling legs never become separate rows, so
pagination never double-counts a root as a leg (doc 15 §3.2, §14, §9.4).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from enum import StrEnum

from entropia.shared.errors import ArtifactTypeInvalidError, CursorInvalidError


class ArtifactType(StrEnum):
    """The queryable immutable result artifacts (doc 15 §3.2)."""

    EQUITY_CURVE = "equity_curve"
    TRADE_LEDGER = "trade_ledger"
    SIGNAL_EVENTS = "signal_events"
    DIAGNOSTICS = "diagnostics"


# V18 drill-down labels -> canonical artifact type (the UI wording is preserved).
ARTIFACT_TYPE_ALIASES: dict[str, ArtifactType] = {
    "equity": ArtifactType.EQUITY_CURVE,
    "ledger": ArtifactType.TRADE_LEDGER,
    "trades": ArtifactType.TRADE_LEDGER,
    "signals": ArtifactType.SIGNAL_EVENTS,
    "events": ArtifactType.SIGNAL_EVENTS,
    "diagnostics": ArtifactType.DIAGNOSTICS,
}

# The three artifacts ordered by an integer ``seq``; diagnostics is ordered by id.
SEQ_ORDERED_TYPES: frozenset[ArtifactType] = frozenset(
    {ArtifactType.EQUITY_CURVE, ArtifactType.TRADE_LEDGER, ArtifactType.SIGNAL_EVENTS}
)


def normalize_artifact_type(raw: str) -> ArtifactType:
    """Resolve a path value to a canonical ``ArtifactType`` (alias or enum).

    An unknown value is a hard ``ARTIFACT_TYPE_INVALID`` — never a silent fallback.
    """
    alias = ARTIFACT_TYPE_ALIASES.get(raw)
    if alias is not None:
        return alias
    try:
        return ArtifactType(raw)
    except ValueError as exc:
        raise ArtifactTypeInvalidError() from exc


@dataclass(frozen=True, slots=True)
class ArtifactCursor:
    """Decoded keyset position: the previous page's last ordering key (as text)."""

    last_key: str


def encode_artifact_cursor(artifact_type: ArtifactType, *, last_key: str) -> str:
    """Build an opaque forward cursor pinned to ``artifact_type`` (doc 15 §7)."""
    payload = {"t": str(artifact_type), "k": last_key}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_artifact_cursor(cursor: str, *, artifact_type: ArtifactType) -> ArtifactCursor:
    """Decode + validate a cursor for ``artifact_type``.

    A malformed token, or one built for a different artifact type, is a
    ``CURSOR_INVALID`` recovery signal — the client refetches the first page and
    never appends partial/duplicated data (doc 15 §7 server-side ordering).
    """
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, TypeError) as exc:
        raise CursorInvalidError() from exc
    if not isinstance(payload, dict) or payload.get("t") != str(artifact_type):
        raise CursorInvalidError()
    last_key = payload.get("k")
    if not isinstance(last_key, str):
        raise CursorInvalidError()
    return ArtifactCursor(last_key=last_key)


__all__ = [
    "ARTIFACT_TYPE_ALIASES",
    "SEQ_ORDERED_TYPES",
    "ArtifactCursor",
    "ArtifactType",
    "decode_artifact_cursor",
    "encode_artifact_cursor",
    "normalize_artifact_type",
]
