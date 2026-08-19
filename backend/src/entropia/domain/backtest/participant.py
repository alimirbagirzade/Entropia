"""The engine-backed ``ItemParticipant`` — ADR-0002 §5 / §8.2, the E4c adapter.

ONE item's shipped bar replay (``engine._build_stepper``'s :class:`~entropia.domain.backtest.
engine._ItemStepper`) presented to the phase loop as a participant. It is the last missing
piece between the loop and the worker: the loop asks an item what it is CHARGED (P1), what it
must CLOSE (P3), what it WANTS (P4), tells it what arbitration GRANTED (P7) and what
end-of-data FORCES (P10) — and every one of those answers already exists inside the stepper,
in a half that books and a half that describes.

WHY THIS MODULE IS NOT IN ``execution/``
----------------------------------------
``tests/unit/oracles/test_oracle_portfolio_containment_gate.py`` scans ``backend/src`` for
production importers of the six unified-clock modules and allows an enumerated list.
``domain/backtest/execution/participant.py`` would have been EXEMPT from that scan
(``path.parent.name != "execution"``), so the guard would have stayed green while the
unified-clock surface grew — satisfied by construction rather than by fact. Placed here it
turns red, and the allowlist had to be widened by one NAMED module, in a reviewed diff, under
a signed decision: ``docs/decisions/closure_participant_importer_allowlist_2026-08-18.md``
(Option A, signed 2026-08-18). A third importer still turns the gate red.

WHAT THIS MODULE DOES NOT DO
----------------------------
1. **No caller.** Nothing in ``backend/src`` constructs an ``_EngineParticipant``; wiring the
   worker is E5/`C4` and ``SHARED_ALLOCATION_STATUS`` stays ``future_dev`` until `C9`. This
   module ships the adapter and its two invariants and nothing else.
2. **No bar translation.** ``clock.py`` and ``engine.py`` import the same ``_Bar`` and the
   same ``_normalize`` from ``execution/state.py``, so ``ItemTickView.bars`` are already the
   bars the stepper consumes and this module reads ``_Bar`` from that same module rather than
   through either of them. A second normalization would be a second coercion policy.
3. **No re-validation of the intent.** ``portfolio_engine._validated_intent`` checks the five
   boundary properties (right item, ``phase == "P4"``, not a mandatory kind, right ``t_ms``,
   right ``snapshot_identity``) at the boundary that needs them. Duplicating them here would
   move the refusal away from the loop, which is the point of having them there.
4. **No mark policy, no P2, no P8.** Those are the loop's own honest boundaries and this
   adapter does not paper over them — see §DUAL BOOKING below for what it does instead.

DUAL BOOKING, AND THE TWO WAYS IT IS KEPT HONEST
------------------------------------------------
The item's own ``_Ledger`` keeps booking exactly as in a single-item run — stop ladders,
``bars_seen``, trade rows and the decision trace all behave identically, which is what keeps
the item's arithmetic comparable to the recorded goldens. The ``PortfolioLedger`` books the
same money and is the ONLY authority for ``E(t)`` and for the Result. Two books, one truth,
and nothing structural stops them drifting. So two things are checked rather than hoped:

* **Money parity.** Every hook reports the item ledger's OWN equity movement, and
  :meth:`_EngineParticipant._require_reported` then asserts that no equity moved that was not
  reported. A phase the loop cannot receive — a deferred fill resolving at P2, a scale layer
  at P8, an opposite-signal close in the tail — moves the item's equity with no channel to
  the pool, and raises :class:`UnmirroredItemBookingError` instead of producing a run whose
  composite equity is quietly wrong. This is derived, not enumerated: it needs no list of
  unsupported Strategy settings and cannot go stale when a new engine feature lands.
* **Position parity.** The pool's ``held`` and ``stepper.open_position()`` must agree at every
  hook that is handed one. An item that stayed flat where the pool opened (or the reverse)
  would size, stop and close against a book that does not exist.

THE ONE DEFERRAL, NAMED RATHER THAN HIDDEN
------------------------------------------
Since GH #552 / PD-2 commission is charged PER FILL, so the entry fill charges the item's
ledger inside :meth:`_EngineParticipant.settle` — at P7, which has no fee channel:
``ItemParticipant.settle`` returns ``None`` and ``_phase_7_apply`` books only the position.
The charge is therefore carried as :attr:`_EngineParticipant.deferred_entry_fee` and reported
to the pool as ``CarryCharges.fee`` at the item's NEXT P1, or folded into the P10 close when
the entry happened on the item's last bar. Cumulative attribution is exact either way; what
is one tick late on the shared path is the INSTANT at which ``E(t)`` records the entry fee,
and in the P10 fold that one charge lands in ``realized_pnl`` rather than in ``fees`` (the
``net_contribution`` is unaffected — see ``ItemAttribution``). Closing it needs a fee channel
on the Protocol at P7, which is an ADR amendment and not this slice's to make.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from entropia.domain.backtest.engine import _EntryDecision, _ItemStepper
from entropia.domain.backtest.execution.arbitration import ArbitrationDecision
from entropia.domain.backtest.execution.clock import ItemBarStream, ItemTickView
from entropia.domain.backtest.execution.constants import _MONEY, _ZERO
from entropia.domain.backtest.execution.intents import (
    ClosingSize,
    EntrySizing,
    ItemDecision,
    ItemIdentity,
    ItemIntent,
    PortfolioSnapshot,
    form_intent,
)
from entropia.domain.backtest.execution.portfolio_ledger import OpenPosition
from entropia.domain.backtest.execution.sizing import sleeve_capital
from entropia.domain.backtest.execution.state import _Bar
from entropia.domain.backtest.portfolio_engine import (
    CarryCharges,
    MandatoryExit,
    PortfolioEngineError,
)

ENTRY_SIGNAL_REASON = "entry_signal"
"""The F-10 trace token the engine already emits for an entry DECISION (``engine._apply_entry``).

``ItemDecision.reason`` must be a token the engine emits or one of ``INTENT_LAYER_REASONS``
(``execution/intents.py``); naming the engine's own event keeps an intent's justification in
the engine's vocabulary rather than in a paraphrase this module invented."""


class UnmirroredItemBookingError(PortfolioEngineError):
    """The item's own ledger moved in a way the phase loop cannot be told about.

    Raised rather than degraded, exactly as the loop refuses an unmodelled admitted kind: the
    alternative is a composite ``E(t)`` that is quietly missing an item's realized money, with
    no warning, no flag and no version bump to make it visible. Every known producer is a
    phase the loop states it does not model — P2 deferred fills and resting orders, P8 scaling,
    and the tail's conflict-driven stack / replace / opposite-signal close."""


class ParticipantStateMismatchError(PortfolioEngineError):
    """The pool's book and the item's book disagree about whether a position is open.

    The pool is the authority for ``E(t)``; the item is the authority for its own stops,
    ladders and trace. An item that is flat where the pool holds would evaluate every
    subsequent bar against a position that does not exist on its side — and would never
    offer the loop the close that releases the pool's committed capital."""


class _EngineParticipant:
    """One ``_ItemStepper`` behind ``portfolio_engine.ItemParticipant`` (ADR §5).

    Constructed per ``_PreparedStrategy`` at the worker's PROVISIONING/RUNNING boundary; the
    stepper is built from exactly the pins the independent path resolves, so the shared and
    independent paths read the same snapshot. ``pin_ordinal`` comes from the manifest pin
    order via ``identity``/``stream`` — never from list position — and
    ``portfolio_engine._ordered`` enforces that the two agree.

    Per-bar phase order is ``_step``'s, split across the shared tick:

        tail(previous bar) -> admit -> P1 carry -> open fills -> P3 held
        -> [PV] -> P4 describe -> [P5/P6b] -> P7 book -> [P9]

    The tail of bar *n* runs at the head of bar *n+1* rather than at the end of the tick,
    because the loop's last per-item hook (``settle``) is called only for an ADMITTED
    decision — there is no end-of-tick hook to run it from. Nothing about the item's state
    observes the difference: ``led.bars_seen`` has not advanced (``admit`` has not run), so
    the same-bar guards the tail reads (``position.entry_bar_seq != led.bars_seen``) evaluate
    exactly as they do inside ``_step``."""

    def __init__(
        self,
        *,
        identity: ItemIdentity,
        stream: ItemBarStream,
        stepper: _ItemStepper,
        instrument_id: str | None = None,
    ) -> None:
        self._identity = identity
        self._stream = stream
        self._stepper = stepper
        self._instrument_id = instrument_id
        self._current: _Bar | None = None
        self._tail_due = False
        self._plan: _EntryDecision | None = None
        self._plan_equity: Decimal | None = None
        # The item ledger's equity at construction — ``_build_stepper`` seeds it with the
        # run's initial capital, which under allocation is the shared POOL P0. Every parity
        # figure below is measured against it, so the adapter never re-derives a capital base.
        self._opening_equity = stepper.ledger.equity
        self._reported = _ZERO
        self._deferred_entry_fee = _ZERO

    # ---- what the loop reads before it runs anything ---------------------------------

    @property
    def identity(self) -> ItemIdentity:
        return self._identity

    @property
    def stream(self) -> ItemBarStream:
        return self._stream

    @property
    def instrument_id(self) -> str | None:
        return self._instrument_id

    @property
    def stepper(self) -> _ItemStepper:
        """The replay this participant adapts.

        Exposed so the sleeve-parity oracle can ask ``sizing.sleeve_capital`` what the ENGINE
        derives ``Ci(t)`` to be and compare it with the pool's ``snapshot.sleeve_capacity``.
        Those are two independent derivations of one canonical quantity (P-C2 §C.3.5, seam
        #7); the comparison is what turns *"they should agree"* into *"they do"*."""
        return self._stepper

    @property
    def deferred_entry_fee(self) -> Decimal:
        """The entry fill's commission, booked by the item and not yet told to the pool.

        Non-zero only between P7 and the item's next P1 (or its P10 close) — see the module
        docstring's §THE ONE DEFERRAL. Published so a test can pin the bound instead of
        trusting the narrative."""
        return self._deferred_entry_fee

    @property
    def unreported_equity(self) -> Decimal:
        """Item equity movement not yet mirrored to the pool. Must always equal
        ``-deferred_entry_fee``; :meth:`_require_reported` is what enforces it."""
        return self._stepper.ledger.equity - self._opening_equity - self._reported

    # ---- the five Protocol hooks ------------------------------------------------------

    def carry(self, view: ItemTickView) -> CarryCharges | None:
        """P1 — advance the item to this tick and report what its funding schedule charged.

        The bar advance lives HERE because P1 is the loop's first per-item call at a tick and
        is made only for a deciding view, which is exactly ``bool(view.bars)``. A tick at
        which the item has no bar therefore reaches no hook at all (ADR §5) while its open
        position stays in ``E(t)``, because the shared ledger holds it and the view does not.

        Every bar at this instant is ADMITTED — P0 books nothing — and the tick's decision
        phases run against the LAST of them: one valuation point, one decision (ADR §5). The
        clock reports a duplicate instant as a diagnostic (``ItemTickView`` / OD-2) and this
        adapter does not turn that measurement into a policy."""
        self._advance(view)
        bar = self._require_current()

        before = self._stepper.ledger.equity
        plan = self._stepper.compute_carry(bar)
        if plan is not None:
            self._stepper.book_carry(bar, plan)
        # Reported as the equity the item ACTUALLY paid, not as the sum of the plan's raw
        # charges: ``_book_carry`` quantizes each charge as it applies it while the pool
        # quantizes once, so a summed figure could land a cent from the item's own book.
        funding = before - self._stepper.ledger.equity
        fee, self._deferred_entry_fee = self._deferred_entry_fee, _ZERO
        self._reported += -funding - fee

        # P2 on the item's own timeline. It may not book here: a deferred entry fill would
        # open a position the pool never arbitrated, and a deferred exit would realize money
        # ``E(t)`` never sees. Both are refused below rather than silently executed.
        held_before = self._stepper.open_position()
        self._stepper.open_fills(bar)
        if self._stepper.open_position() is not held_before:
            raise UnmirroredItemBookingError(
                f"Item '{self._identity.item_id}' resolved a deferred fill or resting order at "
                f"t_ms={view.t_ms}. The phase loop does not model P2, so the position change "
                "would never be arbitrated and the pool would never see the capital move."
            )
        self._require_reported()
        if funding == _ZERO and fee == _ZERO:
            return None
        return CarryCharges(funding=funding, fee=fee)

    def mandatory_exit(self, view: ItemTickView, *, held: OpenPosition) -> MandatoryExit | None:
        """P3 — the protection/exit this bar forces, applied item-locally and reported.

        Mandatory events are NOT arbitrated (``_phase_3_mandatory`` books them immediately),
        so the item may take the arm in the same call. Which of stop / exit / collision wins
        was decided by ``fills._resolve_stop`` + ``engine._plan_exit`` and is not re-decided:
        the describe half NAMES the arm and the booking half executes it."""
        self._require_position_parity(held=held)
        bar = self._require_current()
        position = self._stepper.open_position()
        assert position is not None  # parity above; the loop calls this only while held

        before = self._stepper.ledger.equity
        lots_before = len(self._stepper.ledger.trades)
        decision = self._stepper.evaluate_held(bar)
        if decision is None:  # pragma: no cover — parity above makes this unreachable
            raise ParticipantStateMismatchError(
                f"Item '{self._identity.item_id}' described no P3 arm while holding a position."
            )
        self._stepper.apply_held(bar, decision)
        realized = self._stepper.ledger.equity - before

        if len(self._stepper.ledger.trades) == lots_before:
            # A non-closing arm — a trail anchor advanced, a touch level rested, nothing
            # realized. Anything that moved equity without booking a lot has no channel.
            self._require_reported()
            return None
        if self._stepper.open_position() is not None:
            raise UnmirroredItemBookingError(
                f"Item '{self._identity.item_id}' closed only part of its position at "
                f"t_ms={view.t_ms} (F-07c). The loop releases the item's committed capital "
                "with a FULL close_position, so the two books would hold different sizes from "
                "this tick on."
            )

        commission = self._stepper.ctx.fill_costs.commission
        self._reported += realized
        self._require_reported()
        lot = self._stepper.ledger.trades[-1]
        return MandatoryExit(
            decision=ItemDecision(
                kind="exit",
                reason=lot.exit_reason,
                direction=lot.direction,
                evidence={"position_seq": position.position_seq, "exit_price": str(lot.exit_price)},
            ),
            sizing=ClosingSize(units=position.size),
            # Stated from what the close BOOKED, never recomputed: ``booking.close_position``
            # applies ONE quantized ``gross - commission`` to equity, and that single figure
            # is the one the pool has to agree with. ``book_trade`` subtracts the same
            # commission back out, so the pool applies exactly ``realized``.
            gross_pnl=realized + commission,
            commission=commission,
        )

    def entry(
        self,
        view: ItemTickView,
        snapshot: PortfolioSnapshot,
        *,
        held: OpenPosition | None,
    ) -> ItemIntent | None:
        """P4 — the entry this item wants against THAT snapshot. Commits no capital.

        The flat check is reproduced here deliberately: ``_step`` guards entry with
        ``if not _phase_held(bar)``, i.e. the guard lives in the DRIVER, while
        ``_evaluate_entry``'s own precondition list carries ``pending`` / ``working_limit`` /
        ``working_stop`` but **not** ``position``. Without this branch the loop would
        arbitrate an entry for an item that already holds one.

        The evaluation's own trace effects — ``suppressed_entries``,
        ``entries_blocked_by_restriction``, ``strength_adjustments`` and their
        ``filtered_no_entry`` events — ARE booked here, against this bar. They are counters
        and trace rows, never capital, and there is no later hook to book them from: the pool
        calls ``settle`` only for an ADMITTED decision, so a refused or silent item would lose
        its own suppression record and read as a bar where the strategy wanted nothing."""
        self._require_position_parity(held=held)
        if held is not None:
            return None
        bar = self._require_current()
        decision = self._stepper.evaluate_entry(bar)
        if decision is None:
            return None

        self._stepper.apply_entry(bar, replace(decision, want=None))
        self._require_reported()
        if decision.want is None:
            return None

        self._plan = replace(decision, effects=())
        self._plan_equity = snapshot.equity
        ctx = self._stepper.ctx
        return form_intent(
            identity=self._identity,
            view=view,
            snapshot=snapshot,
            decision=ItemDecision(
                kind="entry",
                reason=ENTRY_SIGNAL_REASON,
                direction=decision.want,
                evidence=dict(decision.entry_detail),
            ),
            # The pre-cap chain only (``intents._sized`` runs ``_effective_fill`` then
            # ``_position_size`` and stops); the sleeve cap is the pool's P6b. ``base`` is the
            # figure ``sizing.planned_size`` itself passes under allocation, so the intent
            # records the base the engine used rather than a second reading of it
            # (``intents.SIZING_BASE_DIVERGENCE``).
            sizing=EntrySizing(
                config=ctx.config,
                fill_costs=ctx.fill_costs,
                base=sleeve_capital(ctx, snapshot.equity) if ctx.alloc_on else snapshot.equity,
                base_source="allocation_sleeve" if ctx.alloc_on else "portfolio_equity",
                strength=decision.strength,
            ),
        )

    def settle(self, view: ItemTickView, *, admitted: ArbitrationDecision) -> None:
        """P7 — book the entry the pool ADMITTED, at the size it granted.

        ``granted_units`` is not ``desired_size``: arbitration caps. ``_open`` takes the
        smaller of its own sized figure and the override, so a grant the pool narrowed is
        honoured and a grant it did not is a no-op — the item can never book MORE than the
        pool decided. The snapshot equity the intent was formed against is the equity the
        booking sizes against, so the two halves of P4 cannot straddle two valuations."""
        plan, self._plan = self._plan, None
        equity, self._plan_equity = self._plan_equity, None
        if plan is None:
            raise ParticipantStateMismatchError(
                f"Item '{self._identity.item_id}' was granted an entry at t_ms={view.t_ms} "
                "without having formed one at P4."
            )
        bar = self._require_current()
        before = self._stepper.ledger.equity
        self._stepper.apply_entry(bar, plan, equity=equity, size_override=admitted.granted_units)
        if self._stepper.open_position() is None:
            raise ParticipantStateMismatchError(
                f"Item '{self._identity.item_id}' opened nothing for the {admitted.granted_units} "
                f"units admitted at t_ms={view.t_ms}; the pool has already booked the position, "
                "so the two books would disagree from this tick on."
            )
        moved = self._stepper.ledger.equity - before
        # The ONLY equity an admitted entry may move is its own per-fill commission (#552).
        # A bound, not a re-derivation of the engine's charge: anything larger, or of the
        # wrong sign, means a phase the loop cannot receive ran inside this call.
        if moved > _ZERO or -moved > self._stepper.ctx.fill_costs.commission + _MONEY:
            raise UnmirroredItemBookingError(
                f"Item '{self._identity.item_id}' moved its ledger by {moved} while booking an "
                f"admitted entry at t_ms={view.t_ms}; only the entry fill's own commission may "
                "move here, and P7 has no channel to report anything else."
            )
        self._deferred_entry_fee = -moved
        self._require_reported()

    def finalize(self, view: ItemTickView) -> MandatoryExit | None:
        """P10 — the close end-of-data forces on a still-open position.

        Runs the item's LAST tail first, then ``stepper.finalize``: a resting order past the
        last bar is cancelled (an auditable no-fill, F-07b/F-07h) and any open position is
        closed at that bar's close. Without this the run would end with the pool holding open
        risk and the composite final equity would be wrong, not merely incomplete."""
        self._run_tail()
        before = self._stepper.ledger.equity
        lots_before = len(self._stepper.ledger.trades)
        position = self._stepper.open_position()
        self._stepper.finalize()
        realized = self._stepper.ledger.equity - before

        if len(self._stepper.ledger.trades) == lots_before:
            if self._deferred_entry_fee != _ZERO:  # pragma: no cover — see the raise message
                raise UnmirroredItemBookingError(
                    f"Item '{self._identity.item_id}' ends the run owing an entry fee with no "
                    "close to fold it into; the pool would never be charged for a fill it "
                    "booked."
                )
            self._require_reported()
            return None
        assert position is not None  # a lot at P10 can only come from a held position

        commission = self._stepper.ctx.fill_costs.commission
        owed, self._deferred_entry_fee = self._deferred_entry_fee, _ZERO
        self._reported += realized - owed
        self._require_reported()
        lot = self._stepper.ledger.trades[-1]
        return MandatoryExit(
            decision=ItemDecision(
                kind="exit",
                reason=lot.exit_reason,
                direction=lot.direction,
                evidence={"position_seq": position.position_seq, "exit_price": str(lot.exit_price)},
            ),
            sizing=ClosingSize(units=position.size),
            # ``- owed`` folds an entry fee the item paid after its last P1 into this close,
            # because P10 has no fee channel either. It changes the fees/realized SPLIT of
            # this one charge and not ``net_contribution`` — module docstring §THE ONE DEFERRAL.
            gross_pnl=realized - owed + commission,
            commission=commission,
        )

    # ---- the machinery the five hooks share -------------------------------------------

    def _advance(self, view: ItemTickView) -> None:
        self._run_tail()
        for bar in view.bars:
            self._stepper.admit(bar)
        self._current = view.bars[-1]
        self._tail_due = True

    def _run_tail(self) -> None:
        """Steps (3d)/(6)/(7)/(8) of the item's PREVIOUS bar — see the class docstring."""
        if not self._tail_due or self._current is None:
            return
        held_before = self._stepper.open_position()
        self._stepper.tail(self._current)
        self._tail_due = False
        if self._stepper.open_position() is not held_before:
            raise UnmirroredItemBookingError(
                f"Item '{self._identity.item_id}' opened or closed a position in its bar tail "
                "(a conflict-driven stack / replace, an opposite-signal close, or a scale "
                "layer). None of those is arbitrated, so the pool would hold a different book."
            )
        self._require_reported()

    def _require_current(self) -> _Bar:
        if self._current is None:  # pragma: no cover — the loop calls hooks only for a
            raise ParticipantStateMismatchError(  # deciding view, which always has a bar
                f"Item '{self._identity.item_id}' was asked to decide before it had a bar."
            )
        return self._current

    def _require_position_parity(self, *, held: OpenPosition | None) -> None:
        mine = self._stepper.open_position()
        if (held is None) == (mine is None):
            return
        raise ParticipantStateMismatchError(
            f"Item '{self._identity.item_id}' holds "
            f"{'a position' if mine is not None else 'nothing'} while the shared ledger holds "
            f"{'a position' if held is not None else 'nothing'}."
        )

    def _require_reported(self) -> None:
        outstanding = self.unreported_equity + self._deferred_entry_fee
        if outstanding == _ZERO:
            return
        raise UnmirroredItemBookingError(
            f"Item '{self._identity.item_id}' moved its own ledger by {outstanding} with no "
            "phase to report it through; the composite E(t) would be missing that money."
        )


__all__ = [
    "ENTRY_SIGNAL_REASON",
    "ParticipantStateMismatchError",
    "UnmirroredItemBookingError",
]
