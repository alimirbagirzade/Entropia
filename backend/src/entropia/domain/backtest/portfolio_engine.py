"""The per-tick phase loop — ``run_portfolio`` (ADR 0002 §8, ADIM 18).

Canon does not describe a portfolio simulation as "run each item, then combine". It
describes ONE clock: at every valuation point the mandatory events resolve first, then
**exactly one** ``E(t)`` is published, then every active item forms its intent against
that one number (Modül 11 §5.2; doc 13 §8.3/§8.4; Modül 12 §9.2). This module is that
loop and nothing else — the five modules it drives already exist and are reused verbatim:

* the merged axis and the per-item views of it (ADIM 15);
* the typed intent contract and the frozen snapshot value (ADIM 16 as shipped);
* the one shared ledger, its freeze window and its capacity layers (ADIM 17);
* cross-item conflict + capacity arbitration (PR #575);
* per-item attribution and the run manifest section (PR #581).

**What this module owns, and it is the whole point:** the ORDER. Every invariant below is
enforced here, at the site, rather than asserted by a test that a later refactor can
delete:

* ``publish_snapshot`` is called exactly ONCE per tick, after the mandatory writes and
  before any discretionary read;
* between ``PV`` and ``P7`` the ledger is frozen, so no sibling's booking can move
  ``E(t)`` under an item that has already sized against it (the freeze itself raises);
* every P4 intent of a tick carries the SAME ``snapshot_identity`` — checked, not assumed
  (doc 13 §14 test 11);
* ledger-writing work runs in ``(pin_ordinal, item_id)`` order and nothing else does, so
  item order can never change what an item DECIDES (ADR §4.4);
* the tick axis is strictly increasing, which is what makes the composite equity curve
  time-ordered **by construction** rather than by sorting it afterwards (removal
  condition #5).

**Not wired, on purpose.** ``run_engine`` (``domain/backtest/engine.py:755``) keeps its
signature *and its semantics* (ADR §3.2): it is not routed through this loop, and the
worker still runs its item loop. Nothing in ``application/`` imports this module, so no
shipped Result, digest or ``ENGINE_VERSION`` moves because this file exists and the
rollback is still "revert the commit".

**Honest boundary — why the per-item work is injected.** ADR §12's ADIM 16 (extracting
``run_engine``'s bar loop into a resumable stepper) was never written; the bar loop at
``engine.py:1782`` is still monolithic. A loop cannot advance an item's real replay to a
given ``t`` until that stepper exists. So the per-item half is a collaborator
(:class:`ItemDriver`) that REPORTS facts, and this loop performs every ledger write
itself. That split is not a workaround to be undone later — it is what keeps the phase
discipline in one place. When the stepper lands it becomes one implementation of
:class:`ItemDriver`, and the loop does not change.

Two things the driver deliberately may NOT do, because they are open decisions:

* it is never handed the ledger, only the frozen snapshot — an intent that could read a
  sibling's position would violate ADR §6 rule 2 through the front door;
* it is never asked to mark a stale position. Marks are supplied by the caller and
  default to *none*: whether a last-closed bar may be carried forward, and for how long,
  is **OD-2 and unanswered**. ``E(t)`` is realized-only by canon, so the loop needs no
  mark to be correct; attribution simply reports the position as unmarked.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from entropia.domain.backtest.execution.arbitration import (
    ArbitrationDecision,
    ArbitrationReport,
    ConflictPolicyRule,
    ItemArbitrationProfile,
    arbitrate,
    profiles_from_pins,
    resolve_policy,
)
from entropia.domain.backtest.execution.attribution import (
    ContributionReport,
    PortfolioAttribution,
    attribute,
    build_contribution_report,
)
from entropia.domain.backtest.execution.clock import (
    ClockTick,
    ItemBarStream,
    ItemTickView,
    iter_ticks,
)
from entropia.domain.backtest.execution.intents import (
    ClosingSize,
    EntrySizing,
    ItemDecision,
    ItemIdentity,
    ItemIntent,
    PortfolioSnapshot,
    ScaleSizing,
    form_intents,
    form_mandatory_intent,
    snapshot_identities,
)
from entropia.domain.backtest.execution.portfolio_ledger import (
    MarkPrice,
    OpenPosition,
    PortfolioEquityPoint,
    PortfolioLedger,
)
from entropia.domain.backtest.execution.provenance import (
    AllocationProvenance,
    PortfolioManifest,
    build_portfolio_manifest,
)

_ZERO = Decimal("0")

# Pins the phase ORDER of ADR §8.2 — the one thing this module contributes. ADR §10.3
# places the manifest's policy-version fields in ADIM 20 together with the
# ``ENGINE_VERSION`` bump; this constant exists so the policy it names has one home from
# its first line, not so that it ships early.
PHASE_LOOP_VERSION = "phase-loop-v1"

# Domain separator so a run identity can never collide with the snapshot, arbitration or
# timeline digests it is computed over.
_RUN_IDENTITY_NAMESPACE = "entropia.backtest.portfolio.run"


class PhaseLoopError(ValueError):
    """The tick cannot be executed as canon orders it.

    Mirrors ``ClockAxisError`` / ``LedgerError``: a ``ValueError`` a worker turns into a
    failed run. Every subclass is a fail-closed refusal (ADR §11, Modül 12 §9 — a worker
    that cannot place a tick fails the run rather than skipping it)."""


class IncoherentRunInputsError(PhaseLoopError):
    """The axis, the pinned identities, the drivers and the sleeve plan do not describe
    the same set of items. Simulating the intersection would silently drop an item that a
    user allocated capital to."""


class MisdirectedEventError(PhaseLoopError):
    """A driver reported an event for an item that is not its own. Applying it would book
    one item's PnL against another's sleeve — cross-item contamination arriving through
    the mandatory window instead of the intent window."""


class SnapshotLeakError(PhaseLoopError):
    """The intents of one tick do not all name the same valuation.

    This is doc 13 §14 test 11 enforced at the site: *"tum active Mainboard itemleri ayni
    valuation snapshotiyla intent uretir"*. It can only fire if a driver fabricated an
    intent instead of returning a decision, which is exactly the smuggling route the
    single-snapshot rule exists to close."""


class TickOrderError(PhaseLoopError):
    """The axis did not advance strictly forward. Every "no future data" guarantee
    downstream rests on it, so a repeated or backwards instant fails the run rather than
    producing a curve whose order has to be trusted."""


class ScaleBasisNotSuppliedError(PhaseLoopError):
    """A grant would add to a held position, and no driver supplied the resulting basis.

    The averaging rule for a scale-in belongs to the engine's own ladder path
    (``execution/scaling.py``), not to this loop. Inventing a second one here would give
    the codebase two answers to one question, free to drift; refusing is the honest
    alternative to guessing."""


@dataclass(frozen=True, slots=True)
class AppliedFill:
    """The position an item HOLDS after a fill — the resulting total, never the delta.

    ``size`` and ``entry_price`` describe the position as it stands once the fill is
    applied, because that is what ``PortfolioLedger.set_position`` records and what the
    sleeve's deployed notional is read from. Stating a delta here would make every caller
    re-derive the total, and one of them would eventually derive it differently.

    ``commission`` is booked as a fee in the same phase as the fill (``booking.py:222``
    and the stack/ladder sites of ``engine.py`` do the same), and BEFORE the position is
    recorded, so the ledger's no-borrow check sees post-fee capital rather than capital
    the fee has already spent."""

    direction: str
    size: Decimal
    entry_price: Decimal
    commission: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class CashEvent:
    """P1 — funding, a standalone fee, or another realized cost on an open position.

    One of the three ledger lines doc 13 §8.3 counts apart from realized PnL. Applied
    before the valuation point because Modül 11 §5.2 puts *"zorunlu exit/stop/funding/fee
    islemleri"* ahead of it: a funding charge that landed after ``E(t)`` would let an item
    size against equity it no longer has."""

    item_id: str
    kind: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class FillEvent:
    """P2 — a previously scheduled order resolving at this tick."""

    item_id: str
    fill: AppliedFill


@dataclass(frozen=True, slots=True)
class CloseEvent:
    """P3 — a mandatory protection/stop or exit, with the trade it realizes.

    ``decision`` and ``closing`` are required, not optional: ADR §6 rule 5 forbids a
    silent suppression, and a mandatory event that booked PnL without appearing in the
    decision trace would be exactly that. They are recorded through the shipped
    :func:`form_mandatory_intent`, which takes no snapshot — a P3 event structurally
    cannot size against a valuation that does not exist yet.

    ``resulting`` is the remainder of a PARTIAL exit. The ledger holds at most one
    position per item and ``close_position`` releases all of it, so a partial exit is
    modelled the way the engine models it: release, realize, then record what is still
    held. ``None`` is a full close.

    Which of stop / exit / collision wins is the engine's versioned priority policy and is
    NOT re-decided here; this event records an outcome that policy already produced."""

    item_id: str
    gross_pnl: Decimal
    commission: Decimal
    decision: ItemDecision
    closing: ClosingSize
    resulting: AppliedFill | None = None


MandatoryEvent = CashEvent | FillEvent | CloseEvent
ItemProposal = tuple[ItemDecision, EntrySizing | ScaleSizing | None]


class ItemDriver(Protocol):
    """One item's half of a tick — facts only; every ledger write is the loop's.

    Three questions, one per phase window, and never the ledger itself:

    * :meth:`mandatory` — what the item's own P1-P3 resolvers concluded from its data;
    * :meth:`propose` — what it wants at P4, given the ONE published valuation;
    * :meth:`apply` — what it holds once an admitted grant is executed.

    A driver may keep whatever mutable replay state it needs (warmup, edge detectors, an
    open order book): the phase loop makes no purity claim about the driver, only about
    the ORDER in which it is consulted. What it may not do is see a sibling — it is handed
    its own view and the portfolio aggregate, which is doc 13 §8.4 step 4 made structural.
    """

    def mandatory(self, view: ItemTickView) -> Sequence[MandatoryEvent]:
        """P1-P3 facts for this item at this tick, in the order they should be booked."""
        ...

    def propose(self, view: ItemTickView, snapshot: PortfolioSnapshot) -> ItemProposal | None:
        """The item's P4 decision and its pre-cap sizing inputs; ``None`` means "nothing",
        which :func:`form_intents` still traces as an idle intent rather than a silence."""
        ...

    def apply(
        self,
        *,
        grant: ArbitrationDecision,
        intent: ItemIntent,
        held: OpenPosition | None,
    ) -> AppliedFill:
        """The position resulting from an admitted grant. Must raise rather than return a
        guess: an admitted grant that quietly applied nothing would read as a fill."""
        ...


def default_fill(
    *, grant: ArbitrationDecision, intent: ItemIntent, held: OpenPosition | None
) -> AppliedFill:
    """The unambiguous half of P7, offered so a driver need not restate it.

    Opening a position from flat has exactly one reading: the granted units at the price
    the intent was formed at. Adding to a held position does not — the resulting basis is
    the engine's ladder rule — so this raises instead of averaging. Fail closed."""
    if held is not None:
        raise ScaleBasisNotSuppliedError(
            f"Item '{grant.item_id}' already holds a position; the resulting basis of a "
            "scale-in is the engine's ladder rule, not this loop's to invent. Supply it "
            "from the item's driver."
        )
    if grant.direction is None:
        raise ScaleBasisNotSuppliedError(
            f"Item '{grant.item_id}' was granted {grant.granted_units} units with no "
            "direction; a directionless fill has no side to book."
        )
    price = intent.effective_price if intent.effective_price is not None else intent.reference_price
    if price is None:
        raise ScaleBasisNotSuppliedError(
            f"Item '{grant.item_id}' has no price to book its fill at."
        )
    return AppliedFill(direction=grant.direction, size=grant.granted_units, entry_price=price)


@dataclass(frozen=True, slots=True)
class TickRecord:
    """One completed valuation point, kept whole so a tick can be audited on its own.

    Both intent sets are retained: ``mandatory_intents`` are the P3 events that ran BEFORE
    ``E(t)`` existed and ``intents`` are the P4 decisions formed against it. Collapsing
    them into one list would lose exactly the distinction Modül 11 §5.2 draws."""

    t_ms: int
    snapshot: PortfolioSnapshot
    mandatory_intents: tuple[ItemIntent, ...]
    intents: tuple[ItemIntent, ...]
    arbitration: ArbitrationReport
    equity_point: PortfolioEquityPoint | None
    attribution: PortfolioAttribution


@dataclass(frozen=True, slots=True)
class PortfolioRun:
    """The finished co-simulation: the one ledger, every tick, and one identity.

    ``identity`` is a deterministic digest over the tick sequence. Two runs share it
    exactly when they published the same valuations, arbitrated them the same way and
    ended with the same book — which is what makes *"item order does not change the
    result"* (doc 13 §14 test 11) and cross-item batch invariance (ADR §11) single string
    comparisons rather than deep structural diffs.

    ``contribution`` is ``None`` only for a run with no ticks at all. An empty report would
    read as "no contribution", which is a different claim from "there were no valuation
    points"."""

    ledger: PortfolioLedger
    ticks: tuple[TickRecord, ...]
    identity: str
    contribution: ContributionReport | None
    policy: ConflictPolicyRule
    phase_loop_version: str = PHASE_LOOP_VERSION

    @property
    def tick_instants(self) -> tuple[int, ...]:
        return tuple(record.t_ms for record in self.ticks)

    @property
    def equity_points(self) -> tuple[PortfolioEquityPoint, ...]:
        return tuple(self.ledger.equity_points)


def _canonical_decimal(value: Decimal) -> str:
    """Identify the VALUE, never its formatting.

    ``3600`` and ``3600.00`` are one equity reading under ``Decimal`` semantics and must
    hash alike, or a ledger that quantized on one tick and not the next would fork a run's
    identity without changing a number. The same normalization the snapshot and
    arbitration identities already use."""
    normalized = value.normalize()
    return (
        format(normalized, "f") if normalized == normalized.to_integral_value() else str(normalized)
    )


def _run_identity(records: Sequence[TickRecord], ledger: PortfolioLedger) -> str:
    digest = hashlib.sha256()
    digest.update(_RUN_IDENTITY_NAMESPACE.encode("utf-8"))
    digest.update(b"\x1f")
    digest.update(PHASE_LOOP_VERSION.encode("utf-8"))
    for record in records:
        digest.update(b"\x1f")
        digest.update(
            f"{record.t_ms}|{record.snapshot.identity}|{record.arbitration.identity}"
            f"|{_canonical_decimal(record.attribution.equity)}".encode()
        )
    for label, amount in (
        ("equity", ledger.equity),
        ("realized_pnl", ledger.realized_pnl),
        ("fees", ledger.fees),
        ("funding", ledger.funding),
        ("other_costs", ledger.other_costs),
    ):
        digest.update(b"\x1f")
        digest.update(f"{label}={_canonical_decimal(amount)}".encode())
    digest.update(b"\x1f")
    digest.update(f"n={len(records)}".encode())
    return digest.hexdigest()


def _ordered_identities(identities: Mapping[str, ItemIdentity]) -> tuple[ItemIdentity, ...]:
    """Pinned order, from the manifest's own ordinals — never dict insertion order."""
    return tuple(sorted(identities.values(), key=lambda i: (i.pin_ordinal, i.item_id)))


def _check_inputs(
    *,
    streams: Sequence[ItemBarStream],
    identities: Mapping[str, ItemIdentity],
    drivers: Mapping[str, ItemDriver],
    ledger: PortfolioLedger,
) -> None:
    """One set of items, named four times; any disagreement fails the run.

    A missing identity, driver or sleeve is not a case with a sensible reading: the item is
    on the axis because a user pinned it, so simulating the intersection would drop a
    participant silently. Items WITHOUT a bar stream are refused for the opposite reason —
    whether a non-executing kind may hold a sleeve at all is **OD-6, still open**, and this
    loop must not answer it by quietly giving one a per-tick presence."""
    axis = {stream.item_id for stream in streams}
    for label, named in (
        ("pinned identity", set(identities)),
        ("driver", set(drivers)),
        ("sleeve", set(ledger.plan.item_ids)),
    ):
        missing = sorted(axis - named)
        if missing:
            raise IncoherentRunInputsError(
                f"These items are on the merged axis but have no {label}: {missing}."
            )
        extra = sorted(named - axis)
        if extra:
            raise IncoherentRunInputsError(
                f"These items have a {label} but no bar stream, so the loop would run "
                f"nothing for them: {extra}. Whether a non-executing item may hold a "
                "sleeve is OD-6 and is not decided here."
            )


def _book_mandatory(
    *,
    ledger: PortfolioLedger,
    tick: ClockTick,
    identities: Mapping[str, ItemIdentity],
    events: Mapping[str, Sequence[MandatoryEvent]],
) -> tuple[ItemIntent, ...]:
    """P1 → P2 → P3, each phase swept across every item in pinned order.

    The sweep is per PHASE, not per item, and that is the canonical order rather than a
    style choice: Modül 12 §9.2 numbers funding (100), scheduled fills (101) and
    stop/exit (102) as three separate clock steps. Running one item's stop before another
    item's funding would interleave three steps into one and let the ledger reach the
    valuation point through a sequence canon does not describe."""
    traced: list[ItemIntent] = []
    for view in tick.views:
        for event in events[view.item_id]:
            if event.item_id != view.item_id:
                raise MisdirectedEventError(
                    f"Driver for '{view.item_id}' reported an event for '{event.item_id}'."
                )
    for view in tick.views:
        for event in events[view.item_id]:
            if isinstance(event, CashEvent):
                _book_cash(ledger, event)
    for view in tick.views:
        for event in events[view.item_id]:
            if isinstance(event, FillEvent):
                _record_fill(ledger, event.item_id, event.fill)
    for view in tick.views:
        for event in events[view.item_id]:
            if not isinstance(event, CloseEvent):
                continue
            traced.append(
                form_mandatory_intent(
                    identity=identities[view.item_id],
                    view=view,
                    decision=event.decision,
                    sizing=event.closing,
                )
            )
            ledger.close_position(event.item_id)
            ledger.book_trade(event.item_id, gross_pnl=event.gross_pnl, commission=event.commission)
            if event.resulting is not None:
                _record_fill(ledger, event.item_id, event.resulting)
    return tuple(traced)


def _book_cash(ledger: PortfolioLedger, event: CashEvent) -> None:
    if event.kind == "funding":
        ledger.book_funding(event.item_id, amount=event.amount)
    elif event.kind == "fee":
        ledger.book_fee(event.item_id, amount=event.amount)
    elif event.kind == "other_cost":
        ledger.book_other_cost(event.item_id, amount=event.amount)
    else:
        raise PhaseLoopError(
            f"Unknown mandatory cash kind {event.kind!r} for item '{event.item_id}'; the "
            "ledger counts funding, fees and other realized costs apart (doc 13 §8.3) and "
            "an unnamed line would land in none of them."
        )


def _record_fill(ledger: PortfolioLedger, item_id: str, fill: AppliedFill) -> None:
    """Fee first, then the position — see :class:`AppliedFill`."""
    if fill.commission != _ZERO:
        ledger.book_fee(item_id, amount=fill.commission)
    ledger.set_position(
        item_id, direction=fill.direction, size=fill.size, entry_price=fill.entry_price
    )


def run_portfolio(
    *,
    streams: Sequence[ItemBarStream],
    identities: Mapping[str, ItemIdentity],
    drivers: Mapping[str, ItemDriver],
    ledger: PortfolioLedger,
    instruments: Mapping[str, str | None] | None = None,
    policy: str | None = None,
    marks: Callable[[ClockTick], Mapping[str, MarkPrice]] | None = None,
    max_position_notional: Mapping[str, Decimal] | None = None,
    max_total_exposure_notional: Decimal | None = None,
) -> PortfolioRun:
    """Co-simulate every item on ONE clock (ADR §8; removal conditions #1, #3, #5).

    The outer loop is the merged timestamp axis, never the item list. Per tick:

    ``CLOCK ADVANCE`` → ``P0..P3`` mandatory (ledger writes) → ``PV`` publish exactly one
    ``PortfolioSnapshot`` (ledger FROZEN) → ``P4`` form intents → ``P5``/``P6b``
    arbitrate → ``P7`` apply → ``P8`` scaling → ``P9`` commit.

    ``P6a`` — the Strategy-Details sizing chain and item risk limits — is not a separate
    call here because it is already inside intent forming: ``form_intents`` runs the
    shipped ``_effective_fill``/``_position_size`` pre-cap chain. ADR A-2 makes that
    placement immaterial: P6a is a pure per-item computation whose position relative to P5
    cannot change any outcome, since a blocked intent's size is irrelevant.

    ``policy`` is resolved ONCE, before the first tick, so an unexecutable cross-item
    policy (``NET``, GH #544) fails the run immediately instead of after an hour of
    replay that must then be discarded.

    ``marks`` is optional and defaults to none. ``E(t)`` is realized-only by canon, so the
    loop is exact without a mark; supplying one only enriches attribution. Carrying a
    stale bar forward is **OD-2** and is the caller's decision, never this loop's.

    :raises PhaseLoopError: on any incoherent input or out-of-order phase. Nothing is
        skipped and nothing degrades — ADR §11 / Modül 12 §9.
    """
    _check_inputs(streams=streams, identities=identities, drivers=drivers, ledger=ledger)
    rule = resolve_policy(policy)
    ordered = _ordered_identities(identities)
    named_instruments = instruments or {}
    profiles: Mapping[str, ItemArbitrationProfile] = profiles_from_pins(
        [(identity.item_id, named_instruments.get(identity.item_id)) for identity in ordered]
    )
    pin_ordinals = {identity.item_id: identity.pin_ordinal for identity in ordered}

    records: list[TickRecord] = []
    attributions: list[PortfolioAttribution] = []
    previous_t_ms: int | None = None

    for tick in iter_ticks(streams):
        if previous_t_ms is not None and tick.t_ms <= previous_t_ms:
            raise TickOrderError(
                f"The axis returned t_ms={tick.t_ms} after {previous_t_ms}; the merged "
                "clock must advance strictly forward."
            )
        previous_t_ms = tick.t_ms

        # --- P0..P3 -- mandatory, ledger writes, no discretion ------------------------ #
        events = {view.item_id: drivers[view.item_id].mandatory(view) for view in tick.views}
        mandatory_intents = _book_mandatory(
            ledger=ledger, tick=tick, identities=identities, events=events
        )

        # --- PV -- exactly one valuation, published once, frozen until P7 ------------- #
        if ledger.is_frozen:
            raise PhaseLoopError(
                f"The ledger was still frozen when t={tick.t_ms} tried to publish; a "
                "previous tick did not reach its apply phase."
            )
        snapshot = ledger.publish_snapshot(tick.t_ms)

        # --- P4 -- discretionary, reads PV only, no ledger writes --------------------- #
        proposals: dict[str, ItemProposal] = {}
        for view in tick.views:
            proposal = drivers[view.item_id].propose(view, snapshot)
            if proposal is not None:
                proposals[view.item_id] = proposal
        intents = form_intents(tick, snapshot, identities, proposals)
        seen = snapshot_identities(intents)
        if seen != {snapshot.identity}:
            raise SnapshotLeakError(
                f"The intents at t={tick.t_ms} name {len(seen)} valuations; every item at "
                "one timestamp must form its intent against the same snapshot "
                "(doc 13 §8.3, §14 test 11)."
            )

        # --- P5 / P6b -- conflict then capacity, against the frozen E(t) -------------- #
        report = arbitrate(
            ledger=ledger,
            snapshot=snapshot,
            intents=intents,
            profiles=profiles,
            policy=policy,
            max_position_notional=max_position_notional,
            max_total_exposure_notional=max_total_exposure_notional,
        )

        # --- P7 / P8 -- apply admitted work in pinned order --------------------------- #
        ledger.begin_apply(tick.t_ms)
        by_item = {intent.item_id: intent for intent in intents}
        for decision in report.decisions:
            if not decision.is_admitted:
                continue
            fill = drivers[decision.item_id].apply(
                grant=decision,
                intent=by_item[decision.item_id],
                held=ledger.positions.get(decision.item_id),
            )
            _record_fill(ledger, decision.item_id, fill)

        # --- P9 -- commit the tick: at most one equity point, then attribute ---------- #
        point = ledger.commit_tick(tick.t_ms)
        snapshot_attribution = attribute(
            ledger=ledger,
            t_ms=tick.t_ms,
            marks=marks(tick) if marks is not None else None,
            pin_ordinals=pin_ordinals,
        )
        attributions.append(snapshot_attribution)
        records.append(
            TickRecord(
                t_ms=tick.t_ms,
                snapshot=snapshot,
                mandatory_intents=mandatory_intents,
                intents=intents,
                arbitration=report,
                equity_point=point,
                attribution=snapshot_attribution,
            )
        )

    return PortfolioRun(
        ledger=ledger,
        ticks=tuple(records),
        identity=_run_identity(records, ledger),
        contribution=build_contribution_report(attributions) if attributions else None,
        policy=rule,
    )


def portfolio_manifest_for(
    run: PortfolioRun,
    *,
    engine_version: str,
    allocation: AllocationProvenance,
    identities: Sequence[ItemIdentity],
    data_revisions: Mapping[str, Mapping[str, str]] | None = None,
) -> PortfolioManifest:
    """The run's manifest section, assembled from what the loop actually executed.

    A thin adapter, deliberately: the manifest's field names, checksums and canon
    adjudications live in ``execution/provenance.py`` and are not restated here. What this
    adds is that the instants, the equity points, the sleeve plan and the conflict policy
    come from the RUN rather than from its configuration — a manifest that described the
    intended run instead of the executed one is the drift ADR §10.2 records as R-1.

    Writing any of these fields into the shipped ``domain/backtest/manifest.py`` is ADIM
    20 and is deliberately not done here."""
    return build_portfolio_manifest(
        engine_version=engine_version,
        allocation=allocation,
        identities=identities,
        conflict_policy=run.policy,
        tick_instants=run.tick_instants,
        equity_points=run.equity_points,
        plan=run.ledger.plan,
        data_revisions=data_revisions,
    )


__all__ = [
    "PHASE_LOOP_VERSION",
    "AppliedFill",
    "CashEvent",
    "CloseEvent",
    "FillEvent",
    "IncoherentRunInputsError",
    "ItemDriver",
    "ItemProposal",
    "MandatoryEvent",
    "MisdirectedEventError",
    "PhaseLoopError",
    "PortfolioRun",
    "ScaleBasisNotSuppliedError",
    "SnapshotLeakError",
    "TickOrderError",
    "TickRecord",
    "default_fill",
    "portfolio_manifest_for",
    "run_portfolio",
]
