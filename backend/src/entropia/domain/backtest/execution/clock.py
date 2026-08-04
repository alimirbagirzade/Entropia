"""The unified valuation clock — the merged decision-time axis (ADR 0002 §4, ADIM 15).

Canon requires the portfolio engine's OUTER loop to be the merged timestamp axis across
all active items, not the item list (doc 13 §8.3; Modül 11 §5.2; Modül 12 §9.2 — restated
as removal condition #1 in ``domain/allocation/capability.py``). Today the worker loops
over items (``application/jobs/backtest_engine.py:298``) and folds finished runs in pin
order, which is why the composite curve is not a time series at all.

This module is the axis and NOTHING else. It answers exactly one question — *what are the
valuation points, and what does each item see at each of them* — and deliberately answers
none of the questions that follow from it:

* it holds no capital, books no PnL and owns no ledger (ADIM 17);
* it forms no intent, runs no phase loop and publishes no snapshot (ADIM 18);
* it arbitrates no conflict, caps no sleeve and rejects no order (ADIM 19);
* it does not decide how an unmarked position is marked — that is **OD-2, still open**;
  the clock reports the facts a mark policy would need and chooses nothing.

**Nothing imports this module yet.** Per ADR §12 the ADIM 15 rollback is "delete the
module"; ``run_engine`` keeps its signature *and its semantics* (ADR §3.2), so no shipped
number, digest or ``ENGINE_VERSION`` moves because this file exists.

Design notes that are contracts, not taste:

* **The tick key is ``t_ms``, UTC epoch milliseconds** (ADR §4.1) — the key the codebase
  already uses across items (``PriorItemInterval.start_ms/end_ms``). String timestamps are
  only accidentally ordered once mixed offset forms appear, so ``"...T02:00:00+01:00"`` and
  ``"...T01:00:00Z"`` must land on ONE tick; they do here and would not under a string sort.
* **A tick is a valuation point, never an (item, time) pair** (ADR §4.1). Items live INSIDE
  a tick so that "every item at ``t`` sees the same snapshot" is structural rather than a
  discipline a later reviewer has to re-verify.
* **Dedup is of the AXIS, never of an item's data.** ADR §4.2 defines the tick set as
  ``sorted(union of decision_times(item_i))`` deduplicated — a set of *instants*. If one item's
  pinned stream carries two bars at the same instant, both are surfaced in that item's view
  (``bars`` is a tuple) and the axis still advances once. Collapsing them would require a
  merge rule canon does not supply, and dropping one would silently discard pinned data.
* **Bar timestamp == decision time** (ADR §4.3, adjudication A-1): the clock keeps the
  shipped convention and does NOT branch on ``record_time_basis``. Honoring that field is
  OD-1 and would be a second semantic change landing in the same digest refresh.
* **Fail closed, never skip.** A bar whose timestamp cannot be placed in time, or a stream
  that goes backwards, raises. ADR §11 / Modül 12 §9: a worker that cannot place a tick
  fails the run rather than continuing on a silently broken axis.
* **Streaming.** The merge is a k-way heap merge over the existing chunked bar iterators;
  at most one bar per item is retained. Materializing all items' bars is not acceptable
  (ADR §11) and is pinned by a test that counts rows pulled from the source generators.
* **No wall clock, no randomness.** The axis is a pure function of its pinned inputs, so a
  replay is reproducible by construction.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from heapq import merge
from itertools import groupby
from typing import Any

from entropia.domain.backtest.execution.state import _Bar, _normalize
from entropia.domain.backtest.funding import parse_utc

# Pins the tick-set rule (ADR §4.2) together with adjudication A-1 (bar timestamp read as
# an absolute UTC instant). ADR §10.3 lists this as a MANIFEST field; writing it into the
# manifest belongs to ADIM 20 and is deliberately not done here — the constant exists so
# that the policy it names has one home from its first line, not so that it ships early.
CLOCK_POLICY_VERSION = "clock-policy-v1"

# Domain separator for ``timeline_identity`` so an axis digest can never collide with any
# other sha256 the codebase publishes.
_TIMELINE_IDENTITY_NAMESPACE = "entropia.backtest.clock.timeline"


class ClockAxisError(ValueError):
    """The merged axis cannot be built from the inputs as given.

    Mirrors ``engine.UnresolvedStrategyError``: a ``ValueError`` the worker turns into a
    failed run. Every subclass is a fail-closed refusal, never a degraded axis."""


class UnplaceableBarTimestampError(ClockAxisError):
    """A bar's timestamp could not be resolved to a UTC instant, so it has no place on the
    axis. Skipping it would silently drop pinned market data from the simulation and mark
    positions against a hole; the run fails instead (ADR §11)."""


class NonMonotonicBarStreamError(ClockAxisError):
    """An item's pinned bar stream went backwards in time. The engine replays a stream
    strictly forward, and a k-way merge over an unsorted input yields an axis that is not
    sorted — every downstream "no future data" guarantee would be void. Fail closed."""


class DuplicateItemStreamError(ClockAxisError):
    """Two streams claim the same ``item_id``. One item has exactly one cursor, so this is
    an incoherent input rather than a case with a sensible reading."""


@dataclass(frozen=True, slots=True)
class ItemBarStream:
    """One item's pinned bar source, as the worker already holds it.

    ``batches`` is the chunked iterator the worker builds today (``stream_bars`` /
    ``iter_bar_batches``), passed straight through — the clock consumes the same rows
    ``run_engine`` does and applies the same coercion (``_normalize``), so a row the engine
    would drop is dropped identically here.

    ``pin_ordinal`` is the item's index in the manifest's deterministic pin order
    (``manifest._pinned_items``, sorted by ``(root_id, selected_revision_id)``). It is the
    first half of the ``(pin_ordinal, item_id)`` tie-break of ADR §4.4 — never DOM order,
    never request-arrival order."""

    item_id: str
    pin_ordinal: int
    batches: Iterable[list[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class ItemTickView:
    """What ONE item sees at ONE tick.

    ``bars`` is empty when this item has no bar at this instant. ADR §5: *"A tick at which
    item i has no bar is not a decision for item i"* — it forms no intent. The view is still
    emitted, because the portfolio-wide ``E(t)`` of ADIM 17 has to account for the item's
    open position even when the item itself is silent, and a missing view would hide that.

    ``last_closed`` is the newest bar this item has admitted at or before ``t_ms`` — the
    item's latest closed/available state. It can never be a future bar: the cursor is
    advanced by the axis itself, so at tick ``t`` no bar with ``t' > t`` has been read into
    it. This is the *input* a mark policy needs, not a mark policy: whether a stale bar may
    be carried forward, and for how long, is **OD-2 and unanswered**. ``staleness_ms``
    likewise MEASURES the gap and applies no bound."""

    item_id: str
    pin_ordinal: int
    t_ms: int
    bars: tuple[_Bar, ...]
    last_closed: _Bar | None
    last_closed_t_ms: int | None

    @property
    def is_decision(self) -> bool:
        """Does this item decide at this tick? (ADR §5 — no fresh bar, no intent.)"""
        return bool(self.bars)

    @property
    def staleness_ms(self) -> int | None:
        """Age of ``last_closed`` at this tick; ``0`` when fresh, ``None`` before the item's
        first bar. A measurement with no threshold attached — see OD-2."""
        if self.last_closed_t_ms is None:
            return None
        return self.t_ms - self.last_closed_t_ms


@dataclass(frozen=True, slots=True)
class ClockTick:
    """One valuation point: an instant, and every item's view of it.

    ``views`` carries EVERY stream — deciding or not — in ``(pin_ordinal, item_id)`` order.
    That order is the serialization order ADR §4.4 reserves for ledger-writing work; it is
    published here so the later phases have one ordering to obey, and it can never change
    *what* an item decides because every view is built from the same frozen instant."""

    t_ms: int
    views: tuple[ItemTickView, ...]

    @property
    def deciding(self) -> tuple[ItemTickView, ...]:
        """The views that have a fresh bar at this tick."""
        return tuple(view for view in self.views if view.is_decision)

    def view_for(self, item_id: str) -> ItemTickView | None:
        for view in self.views:
            if view.item_id == item_id:
                return view
        return None


def tick_key(timestamp: str) -> int | None:
    """UTC epoch ms for a bar timestamp, ``None`` when it cannot be placed.

    The same convention as the two shipped wrappers over ``parse_utc``
    (``engine._epoch_ms_or_none``, ``execution.rules.bar_epoch_ms``) — ``source_zone=None``
    because replayed bars are UTC-normalized at ingest, so a naive value is an honest
    ``None`` rather than a guessed UTC. Kept as its own function so the clock does not
    depend on ``execution.rules``, which ADIM 19 retires; a test asserts all three agree."""
    parsed = parse_utc(timestamp, source_zone=None)
    return int(parsed.timestamp() * 1000) if parsed is not None else None


@dataclass(slots=True)
class _Cursor:
    """Per-item replay state the axis advances. One bar retained, never a buffer."""

    last_closed: _Bar | None = None
    last_closed_t_ms: int | None = None


def _ordered_streams(streams: Sequence[ItemBarStream]) -> tuple[ItemBarStream, ...]:
    seen: set[str] = set()
    for stream in streams:
        if stream.item_id in seen:
            raise DuplicateItemStreamError(f"Duplicate item stream '{stream.item_id}'.")
        seen.add(stream.item_id)
    return tuple(sorted(streams, key=lambda s: (s.pin_ordinal, s.item_id)))


def _placed_bars(stream: ItemBarStream) -> Iterator[tuple[int, int, str, _Bar]]:
    """One item's bars as placed axis entries, lazily and strictly forward."""
    previous: int | None = None
    for batch in stream.batches:
        for raw in batch:
            bar = _normalize(raw)
            if bar is None:
                # Same coercion boundary as the engine (``state._normalize``): a row missing
                # a price or carrying a non-numeric value is dropped there too, so the clock
                # cannot admit a bar the replay would not have seen.
                continue
            placed = tick_key(bar.timestamp)
            if placed is None:
                raise UnplaceableBarTimestampError(
                    f"Item '{stream.item_id}': bar timestamp {bar.timestamp!r} cannot be "
                    "placed on the UTC axis."
                )
            if previous is not None and placed < previous:
                raise NonMonotonicBarStreamError(
                    f"Item '{stream.item_id}': bar timestamp {bar.timestamp!r} "
                    f"({placed} ms) goes backwards from {previous} ms."
                )
            previous = placed
            yield (placed, stream.pin_ordinal, stream.item_id, bar)


def iter_ticks(streams: Sequence[ItemBarStream]) -> Iterator[ClockTick]:
    """Yield the merged valuation points in ascending time, one ``ClockTick`` per instant.

    ``ticks(run) = sorted(union over i of decision_times(item_i))``, deduplicated (ADR §4.2). With
    exactly one stream this reduces to that item's own bar axis, which is the single-item
    reduction ADR §3.2 makes the boundary of the whole programme.

    Streaming: a k-way heap merge over the per-item iterators, keyed on
    ``(t_ms, pin_ordinal, item_id)`` so equal instants resolve deterministically without
    ever consulting set or dict iteration order. Only the bars of the current instant plus
    one retained bar per item are held."""
    ordered = _ordered_streams(streams)
    if not ordered:
        return
    cursors: dict[str, _Cursor] = {stream.item_id: _Cursor() for stream in ordered}
    merged = merge(
        *(_placed_bars(stream) for stream in ordered),
        key=lambda entry: (entry[0], entry[1], entry[2]),
    )
    for t_ms, group in groupby(merged, key=lambda entry: entry[0]):
        fresh: dict[str, list[_Bar]] = {}
        for entry in group:
            fresh.setdefault(entry[2], []).append(entry[3])
        views: list[ItemTickView] = []
        for stream in ordered:
            bars = tuple(fresh.get(stream.item_id, ()))
            cursor = cursors[stream.item_id]
            if bars:
                # Duplicate instants inside one item are surfaced, not collapsed; the
                # cursor follows the last one, matching the engine's forward replay.
                cursor.last_closed = bars[-1]
                cursor.last_closed_t_ms = t_ms
            views.append(
                ItemTickView(
                    item_id=stream.item_id,
                    pin_ordinal=stream.pin_ordinal,
                    t_ms=t_ms,
                    bars=bars,
                    last_closed=cursor.last_closed,
                    last_closed_t_ms=cursor.last_closed_t_ms,
                )
            )
        yield ClockTick(t_ms=t_ms, views=tuple(views))


def timeline_identity(
    t_ms_values: Iterable[int], *, policy_version: str = CLOCK_POLICY_VERSION
) -> str:
    """A deterministic identity for one merged axis: sha256 hex over the tick instants.

    Two runs share an identity exactly when they have the same instants in the same order
    under the same clock policy. It is computed incrementally so an axis can be identified
    without materializing it — the same reason the merge streams (ADR §11).

    Deliberately NOT written to the manifest here: ADR §10.3 places
    ``clock_policy_version`` and its neighbours in ADIM 20, together with the
    ``ENGINE_VERSION`` bump they must land with."""
    digest = hashlib.sha256()
    digest.update(_TIMELINE_IDENTITY_NAMESPACE.encode("utf-8"))
    digest.update(b"\x1f")
    digest.update(policy_version.encode("utf-8"))
    count = 0
    for t_ms in t_ms_values:
        digest.update(b"\x1f")
        digest.update(str(t_ms).encode("utf-8"))
        count += 1
    digest.update(b"\x1f")
    digest.update(f"n={count}".encode())
    return digest.hexdigest()
