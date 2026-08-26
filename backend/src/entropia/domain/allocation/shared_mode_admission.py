"""The admission-side refusal table for SHARED-capital runs (ADR 0002 §13.1).

This module is the plan-level half of `C6`. Its sibling is
:func:`entropia.domain.backtest.participant._unsupported_shapes`, which states the
same kind of thing for ONE resolved run — and the split between them is a property
of the questions, not a convenience:

* ``_unsupported_shapes`` asks *"can the loop model THIS item's resolved config?"*
  (P2 deferred fills, P8 scaling, partial closes). Every one of its rows is knowable
  from a single item.
* This module asks *"can the loop model this COMPOSITION at all?"* — OD-1 compares
  two pinned revisions against each other, and OD-6 is about an entry that has no
  resolved run to inspect. Neither question can be phrased over one item, which is
  why neither appears in that table and why nothing here is copied from it.

A reviewer holding the two lists side by side should therefore find them disjoint by
construction, not overlapping-but-drifted.

Both predicates read the IMMUTABLE snapshot / pinned manifest context straight,
exactly as :func:`..capability.shared_allocation_requested` does, so a refusal never
depends on Ready Check having produced (or been given the chance to produce) the
finding — the admission guard is the last place these can be stopped.

Honest boundary
---------------
While ``SHARED_ALLOCATION_STATUS`` is ``future_dev`` the containment guard refuses
every shared run first, so nothing here is reachable in the shipped build. These are
the fail-closed floor that must already exist when `C9` lifts containment; the plan
says the same thing ("only shared runs are affected, and no shared run is admissible
until C9"). The two-world tests drive them through the lifted world.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from entropia.domain.mainboard.enums import MainboardItemKind

EXECUTING_ITEM_KINDS: frozenset[MainboardItemKind] = frozenset({MainboardItemKind.STRATEGY})
"""Kinds the V1 bar-replay engine actually simulates.

Stated as the POSITIVE set on purpose. ``application/jobs/backtest_engine.py``
(``_enabled_non_strategy_items``) hands every non-Strategy item ``output=None``, so
"executes" is exactly "is a Strategy" — and writing the complement instead would let
a newly added :class:`MainboardItemKind` silently earn a sleeve it cannot use. Derived
this way, a widened enum fails CLOSED, which is the same reasoning
``rules.ALLOCATABLE_ITEM_KINDS`` records for its own set.
"""

NON_EXECUTING_ITEM_FIELD_PATH = "entries"
"""Entry-level findings point at ``entries`` (mirrors ``validate_allocation``)."""

MIXED_RECORD_TIME_BASIS_FIELD_PATH = "data.market_dataset_revision_id"
"""OD-1's divergence is between the pinned market-dataset revisions themselves."""

NON_EXECUTING_ITEM_MESSAGE = (
    "Shared capital allocation cannot give a sleeve to an item the engine runs no "
    "simulation for. Trading Signal and Trade Log are EXTERNAL work objects: they "
    "affect execution only as a Strategy data input, so the V1 bar-replay engine "
    "produces no run for them (F-04). On a shared pool that item's share would be "
    "withheld from every item that CAN trade while doing nothing itself — the silent "
    "degradation ADR 0002 §13.1 OD-6(a) blocks."
)

NON_EXECUTING_ITEM_REMEDIATION = (
    "Deactivate the Trading Signal / Trade Log allocation entry and redistribute its "
    "share across the Strategy entries, or turn the Portfolio Allocation toggle off "
    "and run in independent mode. The item stays in the composition either way — a "
    "Strategy can still consume it as a data input."
)

MIXED_RECORD_TIME_BASIS_MESSAGE = (
    "Shared capital allocation cannot merge pinned market datasets that declare "
    "different record time bases. The engine keeps ONE decision-time convention and "
    "does not branch on 'record_time_basis' (A-1), so on a shared clock two "
    "differently-based datasets would be folded onto the same timestamp axis as if "
    "they were identical and every item would be valued against the other's bar "
    "boundary — ADR 0002 §13.1 OD-1(a)."
)

MIXED_RECORD_TIME_BASIS_REMEDIATION = (
    "Pin market datasets that share one record time basis for every Strategy in the "
    "composition, or turn the Portfolio Allocation toggle off — independent mode "
    "replays each item on its own axis, where a per-item basis is well defined."
)


def _active_entries(capital_execution: Any) -> list[dict[str, Any]]:
    """Active allocation rows off the immutable capital snapshot, defensively.

    Anything that is not a well-formed enabled mapping yields no rows; the caller
    has already established that shared capital was REQUESTED, and a snapshot that
    cannot be read is not evidence of a violation.
    """
    if not isinstance(capital_execution, dict):
        return []
    config = capital_execution.get("config")
    if not isinstance(config, dict):
        return []
    raw = config.get("entries")
    if not isinstance(raw, list):
        return []
    # ``active`` defaults to True in AllocationEntryV1, so an entry that omits the key
    # is active — only an explicit false deactivates it.
    return [e for e in raw if isinstance(e, dict) and e.get("active") is not False]


def _holds_capital(entry: dict[str, Any]) -> bool:
    """Does this entry actually claim a slice of the pool?

    OD-6's harm is a positive share that silently does nothing, so a null or
    non-positive share is not the defect this blocker names (and is already a
    separate ``validate_allocation`` finding). An unparseable share is treated as
    claiming capital: fail closed rather than let a malformed row through.
    """
    share = entry.get("equity_share_percent")
    if share is None:
        return False
    try:
        return Decimal(str(share)) > 0
    except (ArithmeticError, InvalidOperation, ValueError):
        return True


def non_executing_sleeve_holders(capital_execution: Any) -> tuple[str, ...]:
    """OD-6(a): active entries holding a sleeve for a kind the engine never runs.

    Returns the offending composition item ids in snapshot order (empty = no
    violation). An entry whose ``item_type`` is absent yields nothing: a kind that
    was never recorded is not proof of a non-executing one, and such a row is
    already ``ITEM_UNAVAILABLE`` at validation.
    """
    offenders: list[str] = []
    for entry in _active_entries(capital_execution):
        item_type = entry.get("item_type")
        if item_type is None or not _holds_capital(entry):
            continue
        if str(item_type) in {str(kind) for kind in EXECUTING_ITEM_KINDS}:
            continue
        item_id = entry.get("composition_item_id")
        if isinstance(item_id, str) and item_id:
            offenders.append(item_id)
    return tuple(offenders)


def declared_record_time_bases(data_time: list[dict[str, Any]]) -> tuple[str, ...]:
    """The DISTINCT record time bases the pinned market datasets declare, sorted.

    Only Strategy items reach ``data_time`` (``resolve_run_manifest_context`` sends
    every other kind to ``external_objects``), so this is already scoped to the items
    that actually replay bars. A revision that resolved to nothing, or that declares
    no basis, contributes NOTHING rather than a ``None`` bucket — absence of a
    declaration is not a second convention, and counting it as one would block a
    composition for a gap instead of for a conflict.
    """
    bases = {
        str(dataset["record_time_basis"])
        for entry in data_time
        if isinstance(entry, dict)
        for dataset in (entry.get("market_dataset"),)
        if isinstance(dataset, dict) and dataset.get("record_time_basis") is not None
    }
    return tuple(sorted(bases))


def mixed_record_time_bases(data_time: list[dict[str, Any]]) -> tuple[str, ...]:
    """OD-1(a): the declared bases when MORE THAN ONE is pinned (else empty)."""
    bases = declared_record_time_bases(data_time)
    return bases if len(bases) > 1 else ()


__all__ = [
    "EXECUTING_ITEM_KINDS",
    "MIXED_RECORD_TIME_BASIS_FIELD_PATH",
    "MIXED_RECORD_TIME_BASIS_MESSAGE",
    "MIXED_RECORD_TIME_BASIS_REMEDIATION",
    "NON_EXECUTING_ITEM_FIELD_PATH",
    "NON_EXECUTING_ITEM_MESSAGE",
    "NON_EXECUTING_ITEM_REMEDIATION",
    "declared_record_time_bases",
    "mixed_record_time_bases",
    "non_executing_sleeve_holders",
]
