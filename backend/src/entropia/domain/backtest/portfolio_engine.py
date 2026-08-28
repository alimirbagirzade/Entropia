"""The ADR 0002 §8 per-tick phase loop — ``run_portfolio``, the multi-item entry point.

This is ADIM 18. It owns exactly one thing: the ORDER in which a portfolio's shared state is
read and written at each valuation point, and the freeze discipline that makes *"every item
sizes against the same E(t)"* structural rather than a convention someone has to remember.

    P1 funding/fee -> P3 mandatory exits (formed BEFORE any snapshot exists)
    -> PV publish exactly one PortfolioSnapshot(t), ledger FROZEN
    -> P4 discretionary intents, every one against THAT snapshot
    -> P5/P6b arbitrate against the frozen ledger
    -> P7 apply admitted orders in (pin_ordinal, item_id) order -> P9 commit one equity point

Everything it needs to do that already shipped as ADIM 15-19 primitives (``execution.clock``,
``execution.intents``, ``execution.portfolio_ledger``, ``execution.arbitration``). This module
adds no arithmetic of its own: it books what a participant states, it caps nothing itself, and
it computes no size. If a number moves, it moved in a primitive that has its own tests.

Why ``run_engine`` is untouched (ADR §3.2)
------------------------------------------
``domain/backtest/engine.py::run_engine`` keeps its signature **and its semantics**: one item,
its own ``_Ledger``, per-close equity points. A single-Strategy composition therefore replays
byte-identically and the 46 recorded golden digests cannot move because this file exists. The
shared ``PortfolioLedger`` and the per-tick equity rule live HERE and nowhere else, and nothing
in this module is reachable from a bare ``run_engine`` call.

Why P4 takes a FORMED intent instead of calling ``form_intents`` (contract decision)
------------------------------------------------------------------------------------
``execution.intents`` states its own rule: *the decision is an INPUT, not something recomputed
here* — it depends on mutable ``BlockEvaluator`` state and cross-bar edge detectors that no
single-tick function can re-derive. The same argument reaches one step further for an ENTRY.
``form_intent`` sizes an entry through ``costs._effective_fill`` + ``sizing._position_size``,
which need the item's own ``StrategyConfig`` and ``FillCosts``. Those live with the item, not
with the pool. So a participant forms its own P4 intent with the shipped formers and hands it
over; this loop **validates** it (right item, right tick, right snapshot, right phase, not a
mandatory kind) rather than trusting call order. What ``form_intents`` would have guaranteed is
therefore checked here, at the boundary where the guarantee actually has to hold.

One consequence is stated rather than hidden: unlike ``form_intents``, this loop does not
synthesize a traced ``no_op`` for a silent item. A participant with nothing to do returns
``None``, and the tick records the intents that were actually formed. Adding a per-item silence
record is a reporting change, not a capital one, and belongs with the decision trace.

HONEST BOUNDARY — what this module does NOT do
-----------------------------------------------
1. **No production caller.** ``application/jobs/backtest_engine.py`` still loops over ITEMS and
   folds finished runs with ``combine_item_runs``. Wiring it needs an ``ItemParticipant`` backed
   by the real engine, i.e. a per-item replay that can be advanced to a given ``t``. Until that
   adapter exists, the only participant is the oracle package's scripted one, and
   ``SHARED_ALLOCATION_STATUS`` stays ``future_dev``.

   **What is missing is the ADAPTER, not the stepper.** This paragraph used to say the stepper
   "was never written" and offered ``grep -n "def step" engine.py`` as the check. That was true
   when it was written and stopped being true on 2026-08-05: ADR §12's **ADIM 16** landed as
   PR #602 (see that ADR's own AMENDMENT, which supersedes the SKIPPED paragraph above it).
   ``engine._build_stepper`` is now ``run_engine``'s body up to the bar loop and hands back an
   ``_ItemStepper`` that can be entered one bar at a time; ``run_engine`` keeps its signature and
   its semantics and is a short driver over it, and all 46 golden digests were unmoved. So the
   grep the old text prescribed now returns hits, and a reader running it would conclude this
   containment had lapsed. **It has not.** ADIM 16 added no caller — the boundary this item
   states is intact and is asserted, not assumed, by
   ``tests/unit/oracles/test_oracle_portfolio_containment_gate.py::
   test_the_phase_loop_exists_but_no_production_path_reaches_it``. Only the reason changed:
   the remaining work is the ``ItemParticipant`` adapter over the stepper plus the call-site
   change, which ADR §16 puts behind a human gate.

   What actually blocks the wiring, measured against THIS tree (not remembered):

   * **(a)** *Closed.* The bar no longer has to be stepped atomically: ``_ItemStepper`` exposes
     ``admit`` / ``carry`` / ``open_fills`` / ``held`` / ``entry`` / ``tail`` as separate
     callables mapped to the ADR's phases, and ``entry`` already takes the shared ``E(t)`` as
     its ``equity`` argument (``engine._phase_entry``). A caller owning a merged clock can
     therefore split one bar across P1 → P3 → PV → P4 without calling ``step``.
   * **(b)** **The remaining blocker.** Those phases BOOK. An ``ItemParticipant`` has to state
     an intent that this loop — not the item — decides to apply, so it needs a hook that
     DESCRIBES an entry without booking it, against the item-local indicator warmup that lives
     in the stepper's closure.
   * **(c)** *Closed at ADIM 35.* ``execution/portfolio_projection.py::project_portfolio_run``
     projects a finished ``PortfolioRun`` into one composite ``EngineOutput``.

   (b) reaches into ``run_engine``'s bar body, which re-opens the byte-identity question
   PR #602 closed — which is why ADR §16's human gate also needs an ADR amendment. Do not
   start it from this docstring. Measurement and seam ordering:
   ``docs/audit/closure_w0_shared_portfolio_2026-08-13.md``.
2. **P0 / P2 / P8 are not modelled.** Data admission is the clock's cursor (P0); pending fills
   (P2) and same-direction scaling (P8) belong to the item's own execution model. An admitted
   ``scale_in`` therefore raises :class:`UnsupportedIntentKindError` rather than being applied
   through :meth:`PortfolioLedger.set_position`, which would REPLACE the held size with the
   layer size and quietly shrink the position.
3. **Mark policy: REPORTED, never folded.** ``E(t)`` is realized-only, exactly as the ledger
   defines it — a mark cannot move it. How an open position is marked at a tick where its own
   item has no fresh bar is **OD-2, decided (a) in ADR §13.1, built in ADIM 132 and BOUND HERE
   in ADIM 135**: ``_run_tick`` values the book once per tick at ``PV`` and the result reaches
   ``diagnostics["mark_staleness"]`` only. The earlier wording, *"No mark policy … not yet
   built"*, was accurate until ADIM 132 shipped the policy and ADIM 135 bound it.
   Product-owner decision (b), 2026-08-28: diagnostics only — NOT provenance, NOT identity.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from entropia.domain.backtest.execution.arbitration import (
    ArbitrationDecision,
    ArbitrationReport,
    ItemArbitrationProfile,
    arbitrate,
    profiles_from_pins,
)
from entropia.domain.backtest.execution.clock import (
    ClockTick,
    ItemBarStream,
    ItemTickView,
    iter_ticks,
)
from entropia.domain.backtest.execution.constants import _ZERO
from entropia.domain.backtest.execution.intents import (
    MANDATORY_KINDS,
    ClosingSize,
    ItemDecision,
    ItemIdentity,
    ItemIntent,
    PortfolioSnapshot,
    form_mandatory_intent,
    price_for,
)
from entropia.domain.backtest.execution.portfolio_ledger import (
    MarkPrice,
    OpenPosition,
    PortfolioEquityPoint,
    PortfolioLedger,
    PortfolioValuation,
    ledger_for_items,
)

PHASE_ORDER: tuple[str, ...] = ("P1", "P3", "PV", "P4", "P5", "P6b", "P7", "P9", "P10")
"""The phases this loop executes, in the order it executes them (ADR §8.2).

Published as a value so a test can assert the contract without re-reading the source. P0 is the
clock's cursor advance; P2 and P8 are item-local execution phases this loop does not model (see
the module docstring's honest boundary)."""

PORTFOLIO_LOOP_VERSION = "portfolio-phase-loop-v1"
"""Pins the phase ORDER, exactly as ``CLOCK_POLICY_VERSION`` pins the axis rule. ADR §10.3
places the manifest fields in ADIM 20; this constant exists so the contract it names has one
home from its first line, not so it ships early."""


class PortfolioEngineError(ValueError):
    """Base for every fail-closed refusal this loop raises."""


class InvalidParticipantError(PortfolioEngineError):
    """A participant contradicts itself or its siblings — a duplicate ``item_id``, an identity
    that names a different item than its bar stream, or a share the plan does not carry. Each
    would produce a well-formed run for a composition nobody asked for."""


class MisformedIntentError(PortfolioEngineError):
    """A participant handed back an intent that does not belong to this tick, this item, this
    snapshot or this phase. Refused rather than arbitrated: an intent sized against another
    valuation is exactly the cross-item contamination the shared snapshot exists to prevent."""


class UnsupportedIntentKindError(PortfolioEngineError):
    """An admitted intent whose apply phase this loop does not model (ADR §8.2 P8)."""


class UnpriceableAdmissionError(PortfolioEngineError):
    """An admitted order carries no price to open the position at. The ledger books entry
    notional from a price; without one there is no committed capital to record."""


@dataclass(frozen=True, slots=True)
class CarryCharges:
    """P1 — what an item's own funding/fee schedule charges at this tick.

    Amounts are STATED by the item, never derived here: the shipped resolver is
    ``execution.costs.due_funding_charges`` over the item's pinned ``FundingSchedule``, and a
    second implementation would be free to drift from it. Positive is paid, negative received,
    the same sign convention ``run_engine`` books. A zero component books nothing at all, so a
    schedule with no due record leaves the item's attribution counters untouched."""

    funding: Decimal = _ZERO
    fee: Decimal = _ZERO
    other_cost: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class MandatoryExit:
    """P3 — a stop/exit the item's own priority policy already resolved.

    Which of stop / exit / collision wins is ``fills._resolve_stop`` + ``engine._plan_exit``
    and is not re-decided here. ``gross_pnl`` and ``commission`` are stated for the same reason
    ``CarryCharges`` are: the close path that computes them is the engine's."""

    decision: ItemDecision
    sizing: ClosingSize
    gross_pnl: Decimal
    commission: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class BookedClose:
    """What P3 actually BOOKED for one item at this tick — recorded, never re-derived.

    Kept because the loop otherwise consumes this and forgets it. The intent in
    :attr:`PortfolioTick.mandatory` records THAT a close happened and at what price, but the
    money it realized lands only in ``E(t)`` and in the item's running attribution total,
    where a per-trade figure can no longer be recovered — the same reason ``ItemAttribution``
    exists at all (*"recorded as the booking happens or it is gone"*).

    ``gross_pnl`` and ``commission`` are the amounts the participant STATED. ``net_pnl`` is
    the figure :meth:`PortfolioLedger.book_trade` actually applied to ``E(t)``: it quantizes
    the sum once, so a reader recomputing ``gross - commission`` would be a second
    implementation of that rounding, free to land a cent away from the ledger.

    Additive and reporting-only: nothing in this loop reads it back, no phase branches on it,
    and no arithmetic changed when it was added."""

    item_id: str
    gross_pnl: Decimal
    commission: Decimal
    net_pnl: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioTick:
    """Everything one tick published, kept so a caller can inspect the phase boundary.

    ``mandatory`` and ``intents`` are the two sides of ``PV``: the first was formed before the
    snapshot existed and carries ``phase="P3"`` with no snapshot identity, the second was formed
    against it and carries ``phase="P4"``. ``equity_point`` is ``None`` when ``E(t)`` did not
    move — the ledger appends a point only when it does. ``closes`` pairs one-to-one with
    ``mandatory`` by ``item_id``: what each of those exits realized.

    ``valuation`` is OD-2(a)'s marked view of THIS tick, taken inside the frozen window beside
    the snapshot. It is REPORTED, never fed back: ``E(t)`` is realized-only by canon, so a mark
    cannot move a number here (``portfolio_ledger`` module docstring). It is carried per tick
    rather than recomputed at the end because P10 closes every open position, so a terminal
    valuation would always observe an empty book and report nothing."""

    t_ms: int
    timestamp: str
    views: tuple[ItemTickView, ...]
    snapshot: PortfolioSnapshot
    mandatory: tuple[ItemIntent, ...]
    intents: tuple[ItemIntent, ...]
    report: ArbitrationReport
    equity_point: PortfolioEquityPoint | None
    valuation: PortfolioValuation
    closes: tuple[BookedClose, ...] = ()


@dataclass(frozen=True, slots=True)
class PortfolioRun:
    """The finished co-simulation: the one ledger, and every tick it walked."""

    ledger: PortfolioLedger
    ticks: tuple[PortfolioTick, ...]
    final_closes: tuple[BookedClose, ...] = ()
    """What P10 realized at end of data, if anything — the same shape ``PortfolioTick.closes``
    carries, kept for the same reason: once it folds into ``E(t)`` a per-trade figure is gone."""

    @property
    def dated_points(self) -> tuple[PortfolioEquityPoint, ...]:
        """The curve without the ``t_ms=None`` seed the ledger opens the book with."""
        return tuple(p for p in self.ledger.equity_points if p.t_ms is not None)

    @property
    def instants(self) -> tuple[int, ...]:
        """The curve's timestamps. Sorted BY CONSTRUCTION — the axis is (ADR §14 A5)."""
        return tuple(p.t_ms for p in self.dated_points if p.t_ms is not None)

    @property
    def max_drawdown(self) -> Decimal:
        """The ledger's OWN per-point ``peak - equity``, maximised. Not recomputed here."""
        return max((p.drawdown for p in self.ledger.equity_points), default=_ZERO)

    def tick_at(self, timestamp: str) -> PortfolioTick:
        for tick in self.ticks:
            if tick.timestamp == timestamp:
                return tick
        raise KeyError(f"no tick at {timestamp}")


class ItemParticipant(Protocol):
    """One executing item, as the phase loop needs to see it.

    Deliberately narrow: the loop asks an item what it is CHARGED (P1), what it must CLOSE (P3)
    and what it WANTS (P4). It never asks how any of those were computed, and it never reaches
    into item-local state — cursors, indicator warmup, stop ladders and lifecycle ids all stay
    behind this interface (ADR §5). That is what keeps the pool's arithmetic and the item's
    arithmetic from growing into each other.

    Each hook is called only for a tick at which the item HAS a fresh bar (``view.is_decision``),
    because a tick at which item *i* has no bar is not a decision for item *i* (ADR §5). The
    item is still valued at that tick — its open position is in ``E(t)`` regardless."""

    @property
    def identity(self) -> ItemIdentity:
        """The pinned identity every intent this item forms must name."""

    @property
    def stream(self) -> ItemBarStream:
        """This item's pinned bars, in the batches the worker already streams them in."""

    @property
    def instrument_id(self) -> str | None:
        """What the item trades, for same-instrument conflict detection. ``None`` means unknown,
        which the arbitration layer treats as a conflict gate, never as "no conflict"."""

    def carry(self, view: ItemTickView) -> CarryCharges | None:
        """P1 — funding/fees due on a held position at this tick, or ``None`` for nothing."""

    def mandatory_exit(self, view: ItemTickView, *, held: OpenPosition) -> MandatoryExit | None:
        """P3 — the protection/exit this tick forces, or ``None``. Called only while a position
        is held, and always BEFORE the snapshot is published."""

    def entry(
        self,
        view: ItemTickView,
        snapshot: PortfolioSnapshot,
        *,
        held: OpenPosition | None,
    ) -> ItemIntent | None:
        """P4 — the discretionary intent this item forms against ``snapshot``, or ``None``.

        The item forms it with the shipped formers (``intents.form_intent``) because the sizing
        chain needs its own config; the loop validates what comes back."""

    def settle(self, view: ItemTickView, *, admitted: ArbitrationDecision) -> None:
        """P7 — "your intent was admitted, in THIS form" (ADR §6 clause 6).

        The only point at which an item may book capital against an intent it formed. Called
        once per admitted decision, after the pool has arbitrated and the shared ledger has
        opened the position, in the same ``(pin_ordinal, item_id)`` order.

        ``admitted`` carries the GRANTED figures, which are not the requested ones: arbitration
        caps. An item that books ``intent.desired_size`` instead of ``admitted.granted_units``
        has re-decided what the pool already decided.

        Required, never ``hasattr``-probed. Probing is fail-open, and a participant that forgot
        ``settle`` would run silently flat — the pool would hold a position the item does not
        know it has."""

    def finalize(self, view: ItemTickView) -> MandatoryExit | None:
        """P10 — the close end-of-data forces on a still-open position, or ``None``.

        A *mandatory* event in the sense of §6 clause 4, not an intent: it is not arbitrated and
        it forms no ``ItemIntent``. Called once, after the tick loop, with the item's LAST view.

        Required for the same reason ``settle`` is: an unclosed position at end of data leaves
        ``E(t)`` holding open risk, and the composite final equity would be wrong rather than
        merely incomplete."""


def _ordered(participants: Sequence[ItemParticipant]) -> tuple[ItemParticipant, ...]:
    """Participants in the ``(pin_ordinal, item_id)`` order of ADR §4.4.

    Sorting here rather than trusting the argument is the point: the caller's sequence is DOM
    or request order, which doc 13 §13 forbids from mattering. A permuted argument list yields
    the same tuple, so nothing downstream can even observe the difference."""
    seen: set[str] = set()
    for participant in participants:
        identity, stream = participant.identity, participant.stream
        if identity.item_id != stream.item_id:
            raise InvalidParticipantError(
                f"Participant identity '{identity.item_id}' carries item "
                f"'{stream.item_id}'s bar stream; an item has exactly one of each."
            )
        if identity.pin_ordinal != stream.pin_ordinal:
            raise InvalidParticipantError(
                f"Item '{identity.item_id}' is pinned at ordinal {identity.pin_ordinal} but "
                f"its bar stream claims {stream.pin_ordinal}; the pin has one value."
            )
        if identity.item_id in seen:
            raise InvalidParticipantError(f"Duplicate participant for item '{identity.item_id}'.")
        seen.add(identity.item_id)
    return tuple(sorted(participants, key=lambda p: (p.identity.pin_ordinal, p.identity.item_id)))


def _validated_intent(
    intent: ItemIntent,
    *,
    view: ItemTickView,
    snapshot: PortfolioSnapshot,
) -> ItemIntent:
    """The guarantees ``form_intents`` gives, checked at the boundary that needs them."""
    if intent.identity.item_id != view.item_id:
        raise MisformedIntentError(
            f"Item '{view.item_id}' returned an intent for '{intent.identity.item_id}'; an "
            "intent may only ever speak for its own item."
        )
    if intent.phase != "P4":
        raise MisformedIntentError(
            f"Item '{view.item_id}' returned a {intent.phase} intent at P4. Mandatory events "
            "are resolved before E(t) is published (ADR §6 rule 4)."
        )
    if intent.kind in MANDATORY_KINDS:
        raise MisformedIntentError(
            f"'{intent.kind}' is a mandatory event resolved at P3, not a discretionary intent."
        )
    if intent.t_ms != view.t_ms:
        raise MisformedIntentError(
            f"Item '{view.item_id}' returned an intent at t_ms={intent.t_ms} for the "
            f"t_ms={view.t_ms} tick; one valuation point, one intent."
        )
    if intent.snapshot_identity != snapshot.identity:
        raise MisformedIntentError(
            f"Item '{view.item_id}' formed its intent against another valuation than the one "
            "published at this tick; every item sizes against the same E(t) (doc 13 §8.4/4)."
        )
    return intent


def _entry_price(intent: ItemIntent) -> Decimal:
    price = intent.effective_price if intent.effective_price is not None else intent.reference_price
    if price is None:
        raise UnpriceableAdmissionError(
            f"Item '{intent.identity.item_id}' was admitted at t_ms={intent.t_ms} with no price "
            "to open at; the ledger books committed capital from a price."
        )
    return price


@dataclass(slots=True)
class _RunContext:
    """The run-level working set, so each phase function's inputs are visible in its signature
    rather than closed over. ``prices`` is per-tick and is cleared before every P4."""

    ledger: PortfolioLedger
    by_item: Mapping[str, ItemParticipant]
    profiles: Mapping[str, ItemArbitrationProfile]
    conflict_policy: str | None
    max_position_notional: Mapping[str, Decimal] | None
    max_total_exposure_notional: Decimal | None
    prices: dict[str, Decimal] = field(default_factory=dict)


def _phase_1_carry(tick: ClockTick, ctx: _RunContext) -> str:
    """P1 — funding and standalone fees on held positions. Ledger writes, no discretion.

    Returns the tick's wall-clock stamp, read off the first DECIDING view in pinned order, so
    the label is a property of the axis and not of the order a caller happened to pass."""
    stamp = ""
    for view in tick.views:
        if not view.is_decision:
            continue
        if not stamp:
            stamp = view.bars[-1].timestamp
        charges = ctx.by_item[view.item_id].carry(view)
        if charges is None:
            continue
        if charges.funding != _ZERO:
            ctx.ledger.book_funding(view.item_id, amount=charges.funding)
        if charges.fee != _ZERO:
            ctx.ledger.book_fee(view.item_id, amount=charges.fee)
        if charges.other_cost != _ZERO:
            ctx.ledger.book_other_cost(view.item_id, amount=charges.other_cost)
    return stamp


def _phase_3_mandatory(
    tick: ClockTick, ctx: _RunContext
) -> tuple[tuple[ItemIntent, ...], tuple[BookedClose, ...]]:
    """P3 — mandatory exits, formed by the shipped former BEFORE ``E(t)`` exists.

    The intent is formed from the position as it is still HELD, then the capital is released and
    the result booked: releasing and realizing are two ledger facts and the engine emits two.
    Returns both halves of that: what was DECIDED (the intents) and what it REALIZED (the booked
    amounts), because the second is otherwise unrecoverable once it folds into ``E(t)``."""
    formed: list[ItemIntent] = []
    booked: list[BookedClose] = []
    for view in tick.views:
        if not view.is_decision:
            continue
        held = ctx.ledger.positions.get(view.item_id)
        if held is None:
            continue
        exit_event = ctx.by_item[view.item_id].mandatory_exit(view, held=held)
        if exit_event is None:
            continue
        formed.append(
            form_mandatory_intent(
                identity=ctx.by_item[view.item_id].identity,
                view=view,
                decision=exit_event.decision,
                sizing=exit_event.sizing,
            )
        )
        ctx.ledger.close_position(view.item_id)
        booked.append(
            BookedClose(
                item_id=view.item_id,
                gross_pnl=exit_event.gross_pnl,
                commission=exit_event.commission,
                net_pnl=ctx.ledger.book_trade(
                    view.item_id,
                    gross_pnl=exit_event.gross_pnl,
                    commission=exit_event.commission,
                ),
            )
        )
    return tuple(formed), tuple(booked)


def _phase_4_intents(
    tick: ClockTick, snapshot: PortfolioSnapshot, ctx: _RunContext
) -> tuple[ItemIntent, ...]:
    """P4 — every active item's discretionary intent, each against THAT one snapshot."""
    intents: list[ItemIntent] = []
    for view in tick.views:
        if not view.is_decision:
            continue
        intent = ctx.by_item[view.item_id].entry(
            view, snapshot, held=ctx.ledger.positions.get(view.item_id)
        )
        if intent is None:
            continue
        intents.append(_validated_intent(intent, view=view, snapshot=snapshot))
        # Priced only if it asks for an order. A traced ``no_op``/``blocked`` legitimately
        # carries no price, and demanding one would refuse a run over an intent that can
        # never be applied.
        if intent.is_actionable:
            ctx.prices[view.item_id] = _entry_price(intent)
    return tuple(intents)


def _phase_7_apply(tick: ClockTick, report: ArbitrationReport, ctx: _RunContext) -> None:
    """P7 — open what was admitted, in the pinned order ``arbitrate`` already decided in.

    Each admitted item is then told what it got, via ``settle`` (ADR §6 clause 6). The callback
    runs AFTER ``set_position``, so the shared ledger is already the authority on the position
    when the item books against it — the item mirrors a fact, it does not create one."""
    views = {view.item_id: view for view in tick.views}
    ctx.ledger.begin_apply(tick.t_ms)
    for decision in report.decisions:
        if not decision.is_admitted or decision.granted_units <= _ZERO or not decision.direction:
            continue
        if decision.kind != "entry":
            raise UnsupportedIntentKindError(
                f"Item '{decision.item_id}' was admitted with kind '{decision.kind}', whose "
                "apply phase is P8 (same-direction scaling) and is not modelled by this loop. "
                "Applying it through set_position would REPLACE the held size with the layer "
                "size and silently shrink the position."
            )
        ctx.ledger.set_position(
            decision.item_id,
            direction=decision.direction,
            size=decision.granted_units,
            entry_price=ctx.prices[decision.item_id],
        )
        ctx.by_item[decision.item_id].settle(views[decision.item_id], admitted=decision)


def _marks_at(views: Sequence[ItemTickView]) -> dict[str, MarkPrice]:
    """Offer every item's current price as a mark, with the clock's own provenance.

    Nothing here is a new financial computation: the pair comes from ``intents.price_for``
    — the same function that prices an intent — and the age from ``ItemTickView`` which
    already measures it. Both were being discarded before OD-2(a) was bound.

    An item with no price at all is simply not offered. It then lands in ``unmarked_items``
    exactly as an offered-but-unusable mark would, but NOT in ``stale_refused_items``, which
    is correct: absence of a price is not a staleness event, and counting it as one would
    inflate the very counter OD-2(a) asks for.

    Marks are offered for every view, not only for open positions; ``valuation`` reads the
    ones it needs by ``item_id`` and ignores the rest. Filtering here would couple this
    function to the ledger's book and buy nothing."""
    marks: dict[str, MarkPrice] = {}
    for view in views:
        price, authority = price_for(view)
        if price is None:
            continue
        marks[view.item_id] = MarkPrice(
            price=price, authority=authority, staleness_ms=view.staleness_ms
        )
    return marks


def _run_tick(tick: ClockTick, ctx: _RunContext) -> PortfolioTick:
    """One full cycle of ADR §8.1.

    The two hard boundaries are both structural, not conventional: ``publish_snapshot`` FREEZES
    the ledger, so any writer between here and ``begin_apply`` raises ``LedgerFrozenError``; and
    ``arbitrate`` REFUSES an unfrozen ledger, so the permission envelope cannot be computed
    against an ``E(t)`` a sibling has already moved."""
    stamp = _phase_1_carry(tick, ctx)
    mandatory, closes = _phase_3_mandatory(tick, ctx)

    snapshot = ctx.ledger.publish_snapshot(tick.t_ms)
    # OD-2(a), bound here and nowhere else. ``valuation`` is PURE — it assigns nothing and
    # never touches ``_frozen_at`` — so calling it inside the frozen window is legal and
    # leaves the freeze discipline exactly as it was.
    valuation = ctx.ledger.valuation(tick.t_ms, marks=_marks_at(tick.views))

    # Cleared, not overwritten: a price left over from an earlier tick could only ever be read
    # by mistake, and reading one would open a position at a stale bar.
    ctx.prices.clear()
    intents = _phase_4_intents(tick, snapshot, ctx)
    report = arbitrate(
        ledger=ctx.ledger,
        snapshot=snapshot,
        intents=intents,
        profiles=ctx.profiles,
        policy=ctx.conflict_policy,
        max_position_notional=ctx.max_position_notional,
        max_total_exposure_notional=ctx.max_total_exposure_notional,
    )

    _phase_7_apply(tick, report, ctx)
    point = ctx.ledger.commit_tick(tick.t_ms)
    return PortfolioTick(
        t_ms=tick.t_ms,
        timestamp=stamp,
        views=tick.views,
        snapshot=snapshot,
        mandatory=mandatory,
        intents=intents,
        report=report,
        equity_point=point,
        valuation=valuation,
        closes=closes,
    )


def _phase_10_finalize(
    ctx: _RunContext, last_views: Mapping[str, ItemTickView], last_t_ms: int | None
) -> tuple[tuple[BookedClose, ...], PortfolioEquityPoint | None]:
    """P10 — end-of-data: close what is still open, then FOLD the settled figure in.

    Runs ONCE, after the tick loop, in the same ``(pin_ordinal, item_id)`` order every other
    ledger-writing phase uses. Without it a run ends with positions still open and ``E(t)``
    holding unrealized risk, so the composite final equity would be wrong — not merely missing
    a row.

    ``fold_tick`` rather than ``commit_tick`` is the whole of G13 (ADR §13.2): the closes land
    at the SAME instant the last tick already committed, and appending there would put two
    points on one ``t_ms``. See :meth:`PortfolioLedger.fold_tick`.

    A run with no ticks at all has no instant to settle at, so it books nothing."""
    if last_t_ms is None:
        return (), None
    booked: list[BookedClose] = []
    for item_id, participant in ctx.by_item.items():
        view = last_views.get(item_id)
        if view is None:
            continue
        closing = participant.finalize(view)
        if closing is None:
            continue
        if ctx.ledger.positions.get(item_id) is None:
            continue
        ctx.ledger.close_position(item_id)
        booked.append(
            BookedClose(
                item_id=item_id,
                gross_pnl=closing.gross_pnl,
                commission=closing.commission,
                net_pnl=ctx.ledger.book_trade(
                    item_id,
                    gross_pnl=closing.gross_pnl,
                    commission=closing.commission,
                ),
            )
        )
    return tuple(booked), ctx.ledger.fold_tick(last_t_ms)


def iter_portfolio(
    participants: Sequence[ItemParticipant],
    *,
    pool_initial: Decimal,
    shares: Mapping[str, Decimal],
    reserve_percent: Decimal = _ZERO,
    compound: bool = True,
    conflict_policy: str | None = None,
    max_position_notional: Mapping[str, Decimal] | None = None,
    max_total_exposure_notional: Decimal | None = None,
) -> Generator[PortfolioTick, None, PortfolioRun]:
    """Co-simulate ``participants`` on ONE merged clock over ONE shared pool (ADR §3).

    The outer loop is the merged, deduplicated set of valuation points across every item —
    never the item list (ADR §14 A1). At each of them exactly one ``PortfolioSnapshot`` is
    published and every item forms its intent against it (A3), and exactly one equity point is
    appended when ``E(t)`` moves — so the composite curve is time-ordered by construction (A5),
    which is the defect ``allocation/capability.py`` currently contains.

    ``participants`` may arrive in any order: they are re-ordered to ``(pin_ordinal, item_id)``
    before anything reads them, and the clock sorts its streams the same way. ``shares`` is the
    allocation plan's ``wi`` per item — it is the PLAN's authority, not the item's, so it is
    passed in rather than read off a participant.

    The worker calls this only when more than one item executes; a single-item composition stays
    on ``run_engine`` (ADR §3.2), which this module never touches. One participant is still
    accepted, because the single-item reduction — the merged axis IS that item's bar axis — is a
    property worth being able to assert directly.

    Raises rather than degrades: a self-contradicting participant, an intent formed against
    another valuation, an admitted kind whose apply phase is not modelled, and an admitted order
    with no price each stop the run. None of them has a safe partial reading."""
    ordered = _ordered(participants)
    if not ordered:
        raise InvalidParticipantError("A portfolio run needs at least one participating item.")
    item_ids = [p.identity.item_id for p in ordered]
    missing = [item_id for item_id in item_ids if item_id not in shares]
    if missing:
        raise InvalidParticipantError(
            f"The allocation plan carries no share for these participating items: {missing}. "
            "An item with no sleeve would size against a capacity nobody allocated."
        )
    # The other per-item map is checked in the OTHER direction, and the asymmetry is the
    # point. ``shares`` must COVER every participant, because a missing share fails closed —
    # the item has no sleeve and cannot size. ``max_position_notional`` need not cover
    # anyone, but every name it carries must exist, because ``arbitrate`` reads it with
    # ``.get(item_id)``: a key that matches nobody is silently dropped, and a dropped item
    # risk limit fails OPEN. Modül 11 §6.1 puts that limit at layer 3, above the allocation
    # sleeve, precisely so allocation can cap a size and never relax one; doc 13 §14 test 13
    # asks for a deterministic cap, and a cap that vanishes on a typo is neither.
    unknown_limits = sorted(set(max_position_notional or {}) - set(item_ids))
    if unknown_limits:
        raise InvalidParticipantError(
            f"These items carry a max_position_notional limit but do not participate in this "
            f"run: {unknown_limits}. The limit would be silently dropped and the item it was "
            "meant for would size with no item risk limit at all."
        )

    ledger = ledger_for_items(
        pool_initial=pool_initial,
        reserve_percent=reserve_percent,
        shares={item_id: shares[item_id] for item_id in item_ids},
        compound=compound,
    )
    ctx = _RunContext(
        ledger=ledger,
        by_item={p.identity.item_id: p for p in ordered},
        profiles=profiles_from_pins([(p.identity.item_id, p.instrument_id) for p in ordered]),
        conflict_policy=conflict_policy,
        max_position_notional=max_position_notional,
        max_total_exposure_notional=max_total_exposure_notional,
    )

    ticks: list[PortfolioTick] = []
    last_views: dict[str, ItemTickView] = {}
    last_t_ms: int | None = None
    for tick in iter_ticks([p.stream for p in ordered]):
        for view in tick.views:
            if view.is_decision:
                last_views[view.item_id] = view
        last_t_ms = tick.t_ms
        committed = _run_tick(tick, ctx)
        ticks.append(committed)
        yield committed

    final_closes, _final_point = _phase_10_finalize(ctx, last_views, last_t_ms)
    return PortfolioRun(ledger=ledger, ticks=tuple(ticks), final_closes=final_closes)


def run_portfolio(
    participants: Sequence[ItemParticipant],
    *,
    pool_initial: Decimal,
    shares: Mapping[str, Decimal],
    reserve_percent: Decimal = _ZERO,
    compound: bool = True,
    conflict_policy: str | None = None,
    max_position_notional: Mapping[str, Decimal] | None = None,
    max_total_exposure_notional: Decimal | None = None,
) -> PortfolioRun:
    """:func:`iter_portfolio`, exhausted. Signature and semantics unchanged.

    Every caller that does not need to interleave work between ticks — the oracles, the harness
    — keeps using this and sees no difference. A caller that DOES need to (the worker, whose
    cancellation check is ``async`` and cannot run from inside a synchronous loop) drives the
    generator instead and takes the run from ``StopIteration.value``, which is what ``yield
    from`` returns."""
    ticks = iter_portfolio(
        participants,
        pool_initial=pool_initial,
        shares=shares,
        reserve_percent=reserve_percent,
        compound=compound,
        conflict_policy=conflict_policy,
        max_position_notional=max_position_notional,
        max_total_exposure_notional=max_total_exposure_notional,
    )
    # Drained by hand rather than with ``for``: a plain loop DISCARDS a generator's return
    # value, and the assembled ``PortfolioRun`` is exactly that value.
    while True:
        try:
            next(ticks)
        except StopIteration as exhausted:
            run: PortfolioRun = exhausted.value
            return run


__all__ = [
    "PHASE_ORDER",
    "PORTFOLIO_LOOP_VERSION",
    "BookedClose",
    "CarryCharges",
    "InvalidParticipantError",
    "ItemParticipant",
    "MandatoryExit",
    "MisformedIntentError",
    "PortfolioEngineError",
    "PortfolioRun",
    "PortfolioTick",
    "UnpriceableAdmissionError",
    "UnsupportedIntentKindError",
    "iter_portfolio",
    "run_portfolio",
]
