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

# Mainboard item kind pinned as the internal, package-backed strategy object
# (doc 01 §5.2); trading_signal / trade_log are the EXTERNAL work objects.
_STRATEGY_KIND = "strategy"
_EXTERNAL_KINDS: frozenset[str] = frozenset({"trading_signal", "trade_log"})


def _pinned_item_refs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Project the manifest's pinned ``mainboard_items`` into immutable refs.

    Read-only over the immutable manifest — the exact (kind, root, revision) tuples
    the run pinned (never re-resolved from the current Mainboard, doc 16 §15). Order
    is preserved from the manifest, which already sorts them stably (doc 15 §9.2).
    """
    raw = manifest.get("mainboard_items")
    items = raw if isinstance(raw, list) else []
    refs: list[dict[str, Any]] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        refs.append(
            {
                "item_id": entry.get("item_id"),
                "item_kind": entry.get("item_kind"),
                "root_id": entry.get("root_id"),
                "revision_id": entry.get("selected_revision_id"),
                "position": entry.get("position"),
                "enabled": entry.get("enabled"),
            }
        )
    return refs


def _package_revision_refs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """The transitive package revisions the run pinned (K-04, doc 15 §9.2).

    Projected from ``strategy_package_context`` into the same immutable ref tuple the
    Mainboard pins use, so an auditor sees WHICH indicator/condition/reference package
    revision produced a Result — not just the strategy that referenced it. Empty for a
    pre-K-04 manifest, which pinned no package group (honest, never fabricated)."""
    refs: list[dict[str, Any]] = []
    for entry in _group(manifest, "strategy_package_context"):
        item_id = entry.get("item_id")
        for position, package in enumerate(_entries(entry.get("package_revisions"))):
            refs.append(
                {
                    "item_id": item_id,
                    "item_kind": "package",
                    "root_id": package.get("package_root_id"),
                    "revision_id": package.get("package_revision_id"),
                    "position": position,
                    "enabled": True,
                }
            )
    return refs


def _research_revision_refs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """The research feed revisions the run pinned (K-04, doc 15 §9.2 data/time group)."""
    refs: list[dict[str, Any]] = []
    for entry in _group(manifest, "data_time_context"):
        item_id = entry.get("item_id")
        for position, feed in enumerate(_entries(entry.get("research_datasets"))):
            refs.append(
                {
                    "item_id": item_id,
                    "item_kind": "research_data",
                    "root_id": feed.get("root_id"),
                    "revision_id": feed.get("revision_id"),
                    "position": position,
                    "enabled": True,
                }
            )
    return refs


def _market_data_revision(manifest: dict[str, Any]) -> str | None:
    """The run's pinned market dataset revision, when the composition has exactly one.

    K-04 pins it per Strategy item. The DTO carries a SINGLE value, so a composition
    whose strategies pin different datasets resolves to ``None`` — the caller renders
    "Not available" rather than one arbitrarily chosen dataset (doc 16 §4); the full
    per-item truth stays in the manifest's data/time group."""
    revision_ids = {
        str(entry["market_dataset_revision_id"])
        for entry in _group(manifest, "data_time_context")
        if entry.get("market_dataset_revision_id")
    }
    return next(iter(revision_ids)) if len(revision_ids) == 1 else None


def _group(manifest: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return _entries(manifest.get(key))


def _entries(raw: Any) -> list[dict[str, Any]]:
    return [entry for entry in raw if isinstance(entry, dict)] if isinstance(raw, list) else []


def _allocation_plan_revision_id(manifest: dict[str, Any]) -> str | None:
    """The pinned Portfolio Allocation Plan revision id, if the run pinned one.

    Sourced from the immutable ``capital_execution`` snapshot (doc 14 §9.1); ``None``
    when the run had no allocation plan (independent mode) — honest, never blank.
    """
    capital = manifest.get("capital_execution")
    if not isinstance(capital, dict):
        return None
    value = capital.get("plan_revision_id")
    return value if isinstance(value, str) else None


def extract_manifest_context(manifest: dict[str, Any] | None) -> dict[str, Any]:
    """Human-readable comparison context from a result's pinned manifest snapshot.

    Only policy-permitted, immutable fields are surfaced (doc 16 §9.4). Since K-04 the
    manifest pins the Market Data revision per Strategy item (doc 15 §9.2), so it is
    stated directly; a pre-K-04 manifest — or a composition whose strategies pin
    different datasets — still resolves to ``None`` so the caller renders "Not
    available", never a fabricated 0/blank (doc 16 §4, §8.2). Either way a dataset
    change also surfaces transitively as a differing strategy revision (doc 16 §8.3,
    RH-09).
    """
    manifest = manifest if isinstance(manifest, dict) else {}
    identity = manifest.get("identity")
    identity = identity if isinstance(identity, dict) else {}
    refs = _pinned_item_refs(manifest)
    return {
        "engine_version": identity.get("engine_version"),
        "execution_key": manifest.get("execution_key"),
        "composition_fingerprint": identity.get("composition_fingerprint"),
        "allocation_context": manifest.get("capital_execution"),
        "portfolio_allocation_plan_revision_id": _allocation_plan_revision_id(manifest),
        "strategy_revision_refs": [r for r in refs if r.get("item_kind") == _STRATEGY_KIND],
        "artifact_context": manifest.get("result_artifact_context"),
        # K-04: the manifest now pins the market dataset revision per Strategy item, so
        # a dataset change is visible directly (not only transitively via a differing
        # strategy revision). A pre-K-04 manifest, or a multi-dataset composition, still
        # resolves to None — "Not available", never a fabricated value (doc 16 §4).
        "market_data_revision": _market_data_revision(manifest),
    }


def build_manifest_excerpt(
    manifest: dict[str, Any] | None,
    *,
    result_id: str,
    completed_at_utc: str | None,
    artifact_availability: dict[str, Any],
) -> dict[str, Any]:
    """Immutable ``ResultManifestExcerptDTO`` from the pinned manifest (doc 16 §9.4).

    Read-only over the immutable manifest snapshot; never re-resolves the current
    Mainboard, latest package names, or cached form state (doc 16 §8.2, §15). Since
    K-04 the manifest pins the transitive package, market dataset and research feed
    revisions (doc 15 §9.2), so ``package_revision_refs`` / ``market_data_revision`` /
    ``research_data_revision_refs`` are stated from it. A pre-K-04 manifest carries
    none of those groups and still yields honest empty/``None`` values — those runs
    remain identified transitively by ``strategy_revision_refs`` (doc 16 §4, §8.2).
    """
    manifest = manifest if isinstance(manifest, dict) else {}
    identity = manifest.get("identity")
    identity = identity if isinstance(identity, dict) else {}
    refs = _pinned_item_refs(manifest)
    return {
        "result_id": result_id,
        "composition_snapshot_id": identity.get("composition_snapshot_id"),
        "strategy_revision_refs": [r for r in refs if r.get("item_kind") == _STRATEGY_KIND],
        "external_work_refs": [r for r in refs if r.get("item_kind") in _EXTERNAL_KINDS],
        # K-04: the manifest now pins these groups directly (doc 15 §9.2), so the
        # excerpt states them instead of deferring to the strategy config. A pre-K-04
        # manifest carries none of them and still yields honest empty/null.
        "package_revision_refs": _package_revision_refs(manifest),
        "market_data_revision": _market_data_revision(manifest),
        "research_data_revision_refs": _research_revision_refs(manifest),
        "portfolio_allocation_plan_revision_id": _allocation_plan_revision_id(manifest),
        "execution_context": {
            "execution_key": manifest.get("execution_key"),
            "composition_fingerprint": identity.get("composition_fingerprint"),
            "capital_execution": manifest.get("capital_execution"),
        },
        "engine_contract_version": identity.get("engine_version"),
        "artifact_context": manifest.get("result_artifact_context"),
        "completed_at_utc": completed_at_utc,
        "artifact_availability": artifact_availability,
    }


# Order of the comparison rows the UI reads (doc 16 §8.3 warning fields).
_COMPARE_FIELDS: tuple[str, ...] = (
    "market_data_revision",
    "strategy_revision_refs",
    "engine_version",
    "allocation_context",
    "portfolio_allocation_plan_revision_id",
    "artifact_context",
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
    "build_manifest_excerpt",
    "decode_cursor",
    "diff_manifest_contexts",
    "encode_cursor",
    "extract_manifest_context",
    "normalize_sort_key",
]
