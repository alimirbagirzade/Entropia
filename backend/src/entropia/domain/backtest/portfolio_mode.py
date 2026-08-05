"""Which co-simulation produced a persisted Result (ADIM 19).

A multi-item Result today is a SEQUENTIAL fold: each item was replayed on its own and the
runs were concatenated in pin order, so the composite curve is not a portfolio valuation
and its drawdown is not a portfolio drawdown. A future unified-clock Result will be a
genuine co-simulation. The two are not comparable, and until now nothing in the read path
said which one a given Result is — the only signal was a raw warning token
(``portfolio_curve_sequential_not_unified_clock``) buried in the diagnostics artifact.

This module turns that into a first-class, honest label.

**It reads PINNED data only.** The mode is derived from the Result's own immutable manifest
snapshot and its own immutable diagnostics — never from the live composition, never from the
live ``SHARED_ALLOCATION_STATUS`` flag. ADR 0002 §10.4 and doc 13 §14 test 19 are explicit:
a historical Result must not be re-interpreted by anything that can change after it was
written. Flipping the capability flag must not silently re-label a Result that already
exists, and this function cannot, because it never looks at the flag.

**It never mutates a Result.** The label is computed at read time (doc 15 §3.2 immutability);
``LEGACY_SEQUENTIAL_RESULT_NOTE`` is reused verbatim from ``domain.allocation.capability``
rather than a second copy being written here.

**Unknown stays unknown.** A Result whose diagnostics were not retained resolves to
``PORTFOLIO_MODE_UNKNOWN``, not to "legacy" — absence of evidence is not evidence.
"""

from __future__ import annotations

from typing import Any

from entropia.domain.allocation.capability import LEGACY_SEQUENTIAL_RESULT_NOTE
from entropia.domain.backtest.execution.portfolio import COMPOSITION_CURVE_WARNING

#: A single-item run: there is no portfolio co-simulation to characterise.
PORTFOLIO_MODE_SINGLE_ITEM = "single_item"

#: Multi-item, replayed item-by-item and folded in pin order (everything shipped to date).
PORTFOLIO_MODE_LEGACY_SEQUENTIAL = "legacy_sequential"

#: Multi-item, co-simulated on one merged clock against one shared ledger.
PORTFOLIO_MODE_UNIFIED_CLOCK = "unified_clock"

#: Multi-item, but the evidence needed to tell the two apart was not retained.
PORTFOLIO_MODE_UNKNOWN = "unknown"

PORTFOLIO_MODES: frozenset[str] = frozenset(
    {
        PORTFOLIO_MODE_SINGLE_ITEM,
        PORTFOLIO_MODE_LEGACY_SEQUENTIAL,
        PORTFOLIO_MODE_UNIFIED_CLOCK,
        PORTFOLIO_MODE_UNKNOWN,
    }
)

#: The manifest key a unified-clock run will pin (``execution.provenance``). Named here as a
#: STRING on purpose: this production module must not import the contained layer, and the
#: containment tests prove it does not.
UNIFIED_MANIFEST_KEY = "portfolio_simulation"
UNIFIED_MANIFEST_VERSION_FIELD = "portfolio_manifest_version"

#: ``diagnostics.engine_kind``, written by the engine itself. The single-item bypass
#: (``execution/output.py:369``) and the composite fold (``execution/portfolio.py:570``)
#: stamp different values, and a single-item run emits NO ``composition`` block at all —
#: so without this marker a one-item Result is indistinguishable from a Result whose
#: diagnostics were never retained. Both are pinned, engine-authored strings.
SINGLE_ITEM_ENGINE_KIND = "v1_bar_replay"
COMPOSITION_ENGINE_KIND = "v1_bar_replay_composition"

SINGLE_ITEM_NOTE = (
    "A single item was executed, so there is no cross-item portfolio simulation to "
    "characterise. The equity curve is that item's own."
)

UNKNOWN_MODE_NOTE = (
    "This Result does not retain the diagnostics needed to say which co-simulation "
    "produced it. It is reported as unknown rather than assumed."
)

UNIFIED_CLOCK_NOTE = (
    "Produced by the unified-clock co-simulation: every item advanced on one merged "
    "timestamp axis against one shared ledger, so the equity curve is a portfolio "
    "valuation and its drawdown is a portfolio drawdown."
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _executing_item_count(diagnostics: Any) -> int | None:
    composition = _mapping(_mapping(diagnostics).get("composition"))
    count = composition.get("strategy_count")
    return count if isinstance(count, int) else None


def _has_sequential_warning(diagnostics: Any) -> bool:
    warnings = _mapping(diagnostics).get("warnings")
    return isinstance(warnings, list) and COMPOSITION_CURVE_WARNING in warnings


def _unified_manifest_version(manifest: Any) -> str | None:
    """The pinned unified-clock manifest section, if this Result carries one."""
    section = _mapping(_mapping(manifest).get(UNIFIED_MANIFEST_KEY))
    versions = _mapping(section.get("policy_versions"))
    version = versions.get(UNIFIED_MANIFEST_VERSION_FIELD)
    return version if isinstance(version, str) and version else None


def resolve_portfolio_simulation_mode(
    manifest: dict[str, Any] | None,
    diagnostics: dict[str, Any] | None,
) -> str:
    """Classify a persisted Result from its own pinned manifest + diagnostics.

    Order matters. A pinned unified-clock manifest section is the strongest evidence and is
    checked first; the sequential warning is the shipped era's own marker; a composition
    that executed one item needs no portfolio characterisation at all. Anything else is
    ``unknown`` — this function never guesses.
    """
    return resolve_mode_from_parts(_unified_manifest_version(manifest), diagnostics)


def resolve_mode_from_parts(
    unified_manifest_version: str | None,
    diagnostics: dict[str, Any] | None,
) -> str:
    """Same classification, from already-extracted parts.

    The history index pages many Results at once and must not read a whole manifest
    (or a whole diagnostics blob) per row. It extracts the one pinned version string and
    the diagnostics markers in two batched ``IN (...)`` reads, then calls this — so the
    list and the detail page cannot drift apart by re-implementing the rule twice."""
    if unified_manifest_version:
        return PORTFOLIO_MODE_UNIFIED_CLOCK
    if _has_sequential_warning(diagnostics):
        return PORTFOLIO_MODE_LEGACY_SEQUENTIAL
    if _mapping(diagnostics).get("engine_kind") == SINGLE_ITEM_ENGINE_KIND:
        return PORTFOLIO_MODE_SINGLE_ITEM
    count = _executing_item_count(diagnostics)
    if count is not None and count <= 1:
        return PORTFOLIO_MODE_SINGLE_ITEM
    return PORTFOLIO_MODE_UNKNOWN


def portfolio_simulation_note(mode: str) -> str | None:
    """The reader-facing sentence for a mode. ``None`` for an unrecognised token."""
    return {
        PORTFOLIO_MODE_LEGACY_SEQUENTIAL: LEGACY_SEQUENTIAL_RESULT_NOTE,
        PORTFOLIO_MODE_UNIFIED_CLOCK: UNIFIED_CLOCK_NOTE,
        PORTFOLIO_MODE_SINGLE_ITEM: SINGLE_ITEM_NOTE,
        PORTFOLIO_MODE_UNKNOWN: UNKNOWN_MODE_NOTE,
    }.get(mode)


def portfolio_simulation_context(
    manifest: dict[str, Any] | None,
    diagnostics: dict[str, Any] | None,
) -> dict[str, Any]:
    """``{mode, note, comparable_with_unified_clock}`` for the Result read path.

    ``comparable_with_unified_clock`` is stated rather than left for the reader to infer:
    a sequential fold's drawdown and a unified valuation's drawdown are different
    quantities, and a UI that puts them side by side without saying so is misleading.
    """
    return _context(resolve_portfolio_simulation_mode(manifest, diagnostics))


def portfolio_simulation_context_from_parts(
    unified_manifest_version: str | None,
    diagnostics: dict[str, Any] | None,
) -> dict[str, Any]:
    """The same context, for the batched history index. See :func:`resolve_mode_from_parts`."""
    return _context(resolve_mode_from_parts(unified_manifest_version, diagnostics))


def _context(mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "note": portfolio_simulation_note(mode),
        "comparable_with_unified_clock": mode == PORTFOLIO_MODE_UNIFIED_CLOCK,
    }


__all__ = [
    "COMPOSITION_ENGINE_KIND",
    "PORTFOLIO_MODES",
    "PORTFOLIO_MODE_LEGACY_SEQUENTIAL",
    "PORTFOLIO_MODE_SINGLE_ITEM",
    "PORTFOLIO_MODE_UNIFIED_CLOCK",
    "PORTFOLIO_MODE_UNKNOWN",
    "SINGLE_ITEM_ENGINE_KIND",
    "SINGLE_ITEM_NOTE",
    "UNIFIED_CLOCK_NOTE",
    "UNIFIED_MANIFEST_KEY",
    "UNIFIED_MANIFEST_VERSION_FIELD",
    "UNKNOWN_MODE_NOTE",
    "portfolio_simulation_context",
    "portfolio_simulation_context_from_parts",
    "portfolio_simulation_note",
    "resolve_mode_from_parts",
    "resolve_portfolio_simulation_mode",
]
