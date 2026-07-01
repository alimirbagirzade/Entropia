"""Results History sort registry, opaque keyset cursor + compare context diff.

Stage 5b, doc 16 (§5, §8.3, §9.3, §9.4). Pure — no DB, no clock. The server sorts
on the CANONICAL NUMERIC metric values, never on the rounded card string (doc 16
§9.3, RH-02/RH-03). ``null`` metrics always sort LAST (doc 16 §6, §9.3). The cursor
is an opaque base64url token the client cannot construct (doc 16 §5); it pins the
sort key so a cursor built for a different sort is rejected (CURSOR_INVALID).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from entropia.shared.errors import CursorInvalidError, InvalidSortKeyError


class HistorySort(StrEnum):
    """Canonical server sort keys (doc 16 §5 value map, §9.3)."""

    NEWEST_CURRENT = "newest_current"
    NET_PROFIT_PERCENT_DESC = "net_profit_percent_desc"
    ROMAD_DESC = "romad_desc"
    MAX_DRAWDOWN_ASC = "max_drawdown_asc"
    WIN_RATE_DESC = "win_rate_desc"
    TOTAL_TRADES_DESC = "total_trades_desc"


DEFAULT_SORT = HistorySort.NEWEST_CURRENT

# V18 dropdown option value -> canonical server sort (doc 16 §5, §8.1). The V18
# labels are preserved in the UI; only the wire enum maps here.
V18_SORT_ALIASES: dict[str, HistorySort] = {
    "newest": HistorySort.NEWEST_CURRENT,
    "highestReturn": HistorySort.NET_PROFIT_PERCENT_DESC,
    "highestRomad": HistorySort.ROMAD_DESC,
    "lowestDrawdown": HistorySort.MAX_DRAWDOWN_ASC,
    "highestWinrate": HistorySort.WIN_RATE_DESC,
    "mostTrades": HistorySort.TOTAL_TRADES_DESC,
}


@dataclass(frozen=True, slots=True)
class SortSpec:
    """How one sort key orders the immutable result index.

    ``metric_key`` is ``None`` for the recency sort (order by the result's
    ``created_at``); otherwise it names the canonical ``metric_value.metric_key``
    whose numeric ``value`` drives the order. ``descending`` picks the direction;
    ``null``s always fall last (doc 16 §9.3). The tie-break is always
    ``result_id`` DESC for a total, deterministic order.
    """

    metric_key: str | None
    descending: bool


SORT_SPECS: dict[HistorySort, SortSpec] = {
    HistorySort.NEWEST_CURRENT: SortSpec(metric_key=None, descending=True),
    HistorySort.NET_PROFIT_PERCENT_DESC: SortSpec(metric_key="net_profit", descending=True),
    HistorySort.ROMAD_DESC: SortSpec(metric_key="romad", descending=True),
    # max_drawdown metric value is stored ABSOLUTE (>= 0, engine peak-to-trough),
    # so ascending == lowest drawdown first; the UI minus sign never flips it (RH-03).
    HistorySort.MAX_DRAWDOWN_ASC: SortSpec(metric_key="max_drawdown", descending=False),
    HistorySort.WIN_RATE_DESC: SortSpec(metric_key="win_rate", descending=True),
    HistorySort.TOTAL_TRADES_DESC: SortSpec(metric_key="total_trades", descending=True),
}

# The fixed key-metric digest shown on every history card (doc 16 §9.4 key_metrics).
KEY_METRIC_KEYS: tuple[str, ...] = (
    "net_profit",
    "romad",
    "max_drawdown",
    "win_rate",
    "total_trades",
)


def normalize_sort_key(raw: str | None) -> HistorySort:
    """Resolve a request sort value to a canonical ``HistorySort``.

    Accepts the canonical wire enum or a V18 dropdown alias. An unknown value is a
    hard ``INVALID_SORT_KEY`` — never a silent fallback to a known enum (doc 16 §12).
    """
    if raw is None:
        return DEFAULT_SORT
    alias = V18_SORT_ALIASES.get(raw)
    if alias is not None:
        return alias
    try:
        return HistorySort(raw)
    except ValueError as exc:
        raise InvalidSortKeyError() from exc


# --------------------------------------------------------------------------- #
# Opaque keyset cursor                                                         #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Cursor:
    """Decoded keyset position: the previous page's last row.

    ``last_value`` is the string form of that row's sort value (a decimal for a
    metric sort, an ISO timestamp for the recency sort) or ``None`` when the last
    row was in the ``null`` tail. ``last_result_id`` is the tie-break anchor.
    """

    last_value: str | None
    last_result_id: str


def encode_cursor(sort: HistorySort, *, last_value: str | None, last_result_id: str) -> str:
    """Build an opaque forward cursor pinned to ``sort`` (doc 16 §5)."""
    payload = {"s": str(sort), "v": last_value, "r": last_result_id}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, *, sort: HistorySort) -> Cursor:
    """Decode + validate a cursor for ``sort``.

    A malformed token, or one built for a different sort/query fingerprint, is a
    ``CURSOR_INVALID`` recovery signal — the client refetches the first page and
    never appends partial/duplicated data (doc 16 §5, §12, RH-07).
    """
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, TypeError) as exc:
        raise CursorInvalidError() from exc
    if not isinstance(payload, dict) or payload.get("s") != str(sort):
        raise CursorInvalidError()
    result_id = payload.get("r")
    value = payload.get("v")
    if not isinstance(result_id, str) or (value is not None and not isinstance(value, str)):
        raise CursorInvalidError()
    return Cursor(last_value=value, last_result_id=result_id)


# --------------------------------------------------------------------------- #
# Comparison context (doc 16 §8.3, §9.4)                                       #
# --------------------------------------------------------------------------- #

_NOT_AVAILABLE = "Not available"


def extract_manifest_context(manifest: dict[str, Any] | None) -> dict[str, Any]:
    """Human-readable comparison context from a result's pinned manifest snapshot.

    Only policy-permitted, immutable fields are surfaced (doc 16 §9.4). A field the
    V1 manifest does not separately pin (e.g. a dedicated Market Data revision) is
    left ``None`` so the caller renders "Not available" — never a fabricated 0/blank
    (doc 16 §4, §8.2).
    """
    manifest = manifest if isinstance(manifest, dict) else {}
    identity = manifest.get("identity")
    identity = identity if isinstance(identity, dict) else {}
    return {
        "engine_version": identity.get("engine_version"),
        "execution_key": manifest.get("execution_key"),
        "composition_fingerprint": identity.get("composition_fingerprint"),
        "allocation_context": manifest.get("capital_execution"),
        # Market Data revisions are pinned inside strategy configs, not separately
        # in the V1 manifest — honestly surfaced as "Not available" (doc 16 §4).
        "market_data_revision": None,
    }


# Order of the comparison rows the UI reads (doc 16 §8.3 warning fields).
_COMPARE_FIELDS: tuple[str, ...] = (
    "market_data_revision",
    "engine_version",
    "allocation_context",
    "execution_key",
    "composition_fingerprint",
)


def diff_manifest_contexts(context_a: dict[str, Any], context_b: dict[str, Any]) -> dict[str, Any]:
    """Compare two result contexts; flag any field that differs (doc 16 §8.3).

    Returns per-field ``{a, b, differs}`` plus an overall ``context_differs`` flag.
    A higher return is never auto-ranked as "better"; the difference is only made
    visible (doc 16 §1, §8.3, RH-09).
    """
    fields: dict[str, Any] = {}
    context_differs = False
    for name in _COMPARE_FIELDS:
        raw_a = context_a.get(name)
        raw_b = context_b.get(name)
        differs = raw_a != raw_b
        context_differs = context_differs or differs
        fields[name] = {
            "a": _NOT_AVAILABLE if raw_a is None else raw_a,
            "b": _NOT_AVAILABLE if raw_b is None else raw_b,
            "differs": differs,
        }
    return {"fields": fields, "context_differs": context_differs}


__all__ = [
    "DEFAULT_SORT",
    "KEY_METRIC_KEYS",
    "SORT_SPECS",
    "V18_SORT_ALIASES",
    "Cursor",
    "HistorySort",
    "SortSpec",
    "decode_cursor",
    "diff_manifest_contexts",
    "encode_cursor",
    "extract_manifest_context",
    "normalize_sort_key",
]
