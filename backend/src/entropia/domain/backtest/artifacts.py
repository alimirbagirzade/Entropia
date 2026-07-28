"""Heavy result-artifact drill-down: type registry + opaque keyset cursor.

Stage 5c, doc-15 deferred (doc 15 §3.2, §7 QueryResultArtifact, §14). The Trade
Ledger / equity curve / signal events / filtered events / diagnostics are paginated
SERVER-side with a stable ascending key and an opaque base64url cursor the client
cannot forge (same shape as the Stage 5b Results-History cursor). The cursor carries
a generic string key: the ``seq`` (as text) for the seq-ordered artifacts, or the row
id for diagnostics (which have no ``seq``). A Trade Ledger row is a trade ROOT (one
per fully closed trade) — fills / scaling legs never become separate rows, so
pagination never double-counts a root as a leg (doc 15 §3.2, §14, §9.4).

I-02: ``filtered_events`` is its OWN artifact, never a subset view of
``signal_events`` — doc 15 §3.2's Research Data / Agent Data row lists "View Signal
Events" and "View Filtered Events" as two distinct drill-downs, and §16 requires the
no-entry/filtered decision trace stay readable rather than be forced into the shape
of a real fill. The engine journals the filter vetoes separately
(``execution.state.FILTERED_EVENT_TYPES``) and they are persisted into their own
table with their own ``seq`` sequence.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any

from entropia.shared.errors import ArtifactTypeInvalidError, CursorInvalidError


class ArtifactType(StrEnum):
    """The queryable immutable result artifacts (doc 15 §3.2)."""

    EQUITY_CURVE = "equity_curve"
    TRADE_LEDGER = "trade_ledger"
    SIGNAL_EVENTS = "signal_events"
    FILTERED_EVENTS = "filtered_events"
    DIAGNOSTICS = "diagnostics"


# V18 drill-down labels -> canonical artifact type (the UI wording is preserved).
# "events" keeps its shipped meaning (SIGNAL_EVENTS); the Filtered Events drill-down
# gets its own unambiguous aliases rather than overloading that one.
ARTIFACT_TYPE_ALIASES: dict[str, ArtifactType] = {
    "equity": ArtifactType.EQUITY_CURVE,
    "ledger": ArtifactType.TRADE_LEDGER,
    "trades": ArtifactType.TRADE_LEDGER,
    "signals": ArtifactType.SIGNAL_EVENTS,
    "events": ArtifactType.SIGNAL_EVENTS,
    "filtered": ArtifactType.FILTERED_EVENTS,
    "no_entry": ArtifactType.FILTERED_EVENTS,
    "diagnostics": ArtifactType.DIAGNOSTICS,
}

# The four artifacts ordered by an integer ``seq``; diagnostics is ordered by id.
SEQ_ORDERED_TYPES: frozenset[ArtifactType] = frozenset(
    {
        ArtifactType.EQUITY_CURVE,
        ArtifactType.TRADE_LEDGER,
        ArtifactType.SIGNAL_EVENTS,
        ArtifactType.FILTERED_EVENTS,
    }
)

# The artifact-checksum schema. Bumping it changes every stored checksum, so it is
# pinned INTO the hashed payload exactly like ``EXPORT_SCHEMA_VERSION`` (doc 15 §14).
ARTIFACT_CHECKSUM_SCHEMA_VERSION = "artifact-checksum-v1"


def compute_artifact_checksum(artifact_type: ArtifactType, rows: list[dict[str, Any]]) -> str:
    """Content checksum over an artifact's FULL projected row list (doc 15 §7, §14).

    Mirrors ``domain.backtest.export.compute_export_checksum``: sha256 over the
    canonical JSON of the same projection the drill-down and the export both read, so
    a caller can re-derive it from the rows it was served and detect a tampered or
    re-typed artifact. Pinned to ``artifact_type`` so two artifacts that happen to
    project identical rows never share a checksum.
    """
    payload = {
        "schema_version": ARTIFACT_CHECKSUM_SCHEMA_VERSION,
        "artifact_type": str(artifact_type),
        "rows": rows,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


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
    "ARTIFACT_CHECKSUM_SCHEMA_VERSION",
    "ARTIFACT_TYPE_ALIASES",
    "SEQ_ORDERED_TYPES",
    "ArtifactCursor",
    "ArtifactType",
    "compute_artifact_checksum",
    "decode_artifact_cursor",
    "encode_artifact_cursor",
    "normalize_artifact_type",
]
