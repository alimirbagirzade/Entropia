"""ADR 0002 §5 / §8.2 — the engine-backed ``ItemParticipant`` (E4c, P-C2 §C.1).

The phase loop asks an item what it is CHARGED (P1), what it must CLOSE (P3), what it
WANTS (P4), what it GOT (P7) and what end-of-data forces (P10). ``engine._ItemStepper``
can answer all five, one bar at a time, but its phases BOOK where the loop needs them to
DESCRIBE. `C1` split three of them into a pure half and a booking half; this module is the
translation between the two shapes, and nothing else.

Where this file lives, and why it is NOT in ``execution/``
----------------------------------------------------------
The containment gate's importer scan exempts ``execution/``. Putting the adapter there
would make the scan green *by construction* — the guard would be blind, not satisfied.
Outside it, the guard turns red and the allowlist has to be widened by one NAMED module,
in a diff a human reads. That trade was measured and signed:
``docs/decisions/closure_participant_importer_allowlist_2026-08-18.md`` (Option A).

Dual booking, and the two invariants that make it safe rather than lucky
------------------------------------------------------------------------
The item's own ``_Ledger`` keeps booking, so every item-local mechanism — stop ladders,
``led.bars_seen``, trade rows, the decision trace — behaves exactly as in a single-item
run. The ``PortfolioLedger`` books the same amounts and is the ONLY authority for ``E(t)``.
Two books can drift, so two properties are asserted rather than hoped for:

* **Reconciliation** (§C.3.3) — the pool's attribution deltas equal the item ledger's
  realized deltas. Every amount this adapter states is MEASURED off the item ledger
  (``equity`` before/after the booking half), never recomputed here: a second
  implementation of the engine's arithmetic is exactly what would drift.
* **Sleeve parity** (§C.3.5) — ``Ci(t)`` is derived TWICE, by the engine from the injected
  ``E(t)`` (``sizing.planned_size``) and by the ledger as ``snapshot.sleeve_capacity``.
  :meth:`_EngineParticipant.entry` compares them on every deciding tick and refuses on a
  divergence. A divergence means the item sized against a capacity the pool never granted.

What this adapter refuses, and why refusing is the whole point
--------------------------------------------------------------
``_step`` drives five phases; this adapter drives four of them and never calls
``tail``. ``tail``'s scaling section was measured INSEPARABLE at `C1`, and its stacking /
hedge sections OPEN and CLOSE positions with no ``PortfolioSnapshot`` behind them — the
exact silent-degradation shape the working standard forbids. Rather than run a phase that
can commit capital outside arbitration, or drop a configured behaviour silently, the
adapter refuses the shapes that need it AT CONSTRUCTION: see :data:`_UNSUPPORTED_SHAPES`.

P-C2 §C.3.7 (deferred fills) and §C.3.8 (scaling) each recommend option (a) — block the
shape at admission — and `C6` is where those become user-visible Ready Check blockers.
This list is the engine-side half of the same decision: it makes a wrong shared run
impossible before `C6` exists, instead of merely improbable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from entropia.domain.backtest.engine import _EntryDecision, _ItemStepper
from entropia.domain.backtest.execution.arbitration import ArbitrationDecision
from entropia.domain.backtest.execution.clock import ItemBarStream, ItemTickView
from entropia.domain.backtest.execution.constants import _ZERO
from entropia.domain.backtest.execution.fills import _fill_schedule
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
from entropia.domain.backtest.execution.state import _Bar, _RunConfig
from entropia.domain.backtest.portfolio_engine import (
    CarryCharges,
    ItemParticipant,
    MandatoryExit,
    PortfolioEngineError,
)

#: Order types that fill at the timing-chosen price. Everything else RESTS a working order
#: which only ``_phase_open_fills`` can resolve — a phase the shared path never runs.
_IMMEDIATE_ORDER_TYPES = frozenset({"market_order", "simulation_only"})

#: ``position_exit_logic.close_percentage`` for a FULL close. Anything else leaves a
#: remainder the pool has already released the capital for.
_FULL_CLOSE_PERCENT = Decimal("100")

#: Same-direction policies that EXECUTE a second entry inside ``_phase_tail``. Both commit
#: capital (``allow_stacking``) or close and re-open a position (``replace_existing``) with
#: no snapshot behind them; ``ignore`` and ``scale_existing`` only trace.
_EXECUTING_STACKING_POLICIES = frozenset({"allow_stacking", "replace_existing"})


class EngineParticipantError(PortfolioEngineError):
    """Base for this adapter's fail-closed refusals — a ``ValueError``, like every other
    refusal the phase loop raises, so the worker turns it into a failed run rather than a
    degraded one."""


class UnsupportedStrategyShapeError(EngineParticipantError):
    """The strategy configures execution this adapter cannot drive on a shared clock.

    Raised at CONSTRUCTION, before a single bar is admitted, so an unsupported shape can
    never produce a partially-correct run. Each entry of :data:`_UNSUPPORTED_SHAPES` names
    the phase that would have had to run and what it would have booked unarbitrated."""


class ParticipantDivergenceError(EngineParticipantError):
    """The item's own book and the pool's book disagree about the same fact.

    Either the two derivations of ``Ci(t)`` parted (sleeve parity, §C.3.5) or the item did
    not book what the pool just granted (§C.3.6). Both mean the shared ledger is no longer
    a description of what the items actually hold, and neither has a safe partial reading."""


def _unsupported_shapes(ctx: _RunConfig) -> tuple[tuple[bool, str], ...]:
    """The construction-time refusal table: ``(is_violated, why)`` for one resolved run.

    Stated as data rather than as a chain of ``if``s so the set can be READ — it is the
    engine-side statement of which compositions `C6` must block at admission, and a
    reviewer comparing the two lists should not have to trace control flow to do it."""
    execution = ctx.config.data.execution
    exit_logic = ctx.config.position_exit_logic
    conflict = ctx.config.conflict_position_handling
    scaling = ctx.config.scaling_logic
    return (
        (
            not ctx.alloc_on,
            "the run carries no AllocationExecution, so the item would size against its own "
            "private ledger and its sleeve Ci(t) would have no pool to be a slice of",
        ),
        (
            ctx.portfolio_rules is not None,
            "cross-item PortfolioRules are the POOL's authority on a shared run "
            "(arbitration's conflict policy and max_total_exposure); applying them inside "
            "the item too would be two answers to one question",
        ),
        (
            not ctx.plan_active,
            "the run has no resolved indicator plan, so entries would come from the "
            "breakout proxy — which reads the look-back window that only _phase_tail fills, "
            "and which F-04 forbids in production anyway",
        ),
        (
            _fill_schedule(execution.entry_timing) != "immediate",
            f"entry_timing '{execution.entry_timing}' defers or rests the entry fill; it is "
            "resolved by _phase_open_fills / _phase_tail, so the pool would arbitrate an "
            "entry the item never opens at this tick (P-C2 §C.3.7 option (a))",
        ),
        (
            _fill_schedule(execution.exit_timing) != "immediate",
            f"exit_timing '{execution.exit_timing}' defers or rests the exit fill; the pool "
            "would keep holding a position the item has already decided to close",
        ),
        (
            ctx.config.data.order_config.type not in _IMMEDIATE_ORDER_TYPES,
            f"order type '{ctx.config.data.order_config.type}' rests a working order that "
            "only _phase_open_fills can fill",
        ),
        (
            exit_logic.close_percentage != _FULL_CLOSE_PERCENT
            and exit_logic.partial_aftermath != "close_all",
            "a partial close leaves the item holding a remainder while _phase_3_mandatory "
            "releases the WHOLE position's capital in the pool",
        ),
        (
            scaling is not None and scaling.enabled,
            "same-direction scaling runs the layer ladder inside _phase_tail and books "
            "layers with no PortfolioSnapshot behind them; the loop refuses an admitted "
            "scale_in for the same reason (P-C2 §C.3.8 option (a))",
        ),
        (
            str(conflict.same_direction_stacking) in _EXECUTING_STACKING_POLICIES,
            f"same_direction_stacking '{conflict.same_direction_stacking}' opens a second "
            "entry inside _phase_tail, outside arbitration",
        ),
        (
            not (ctx.sizing_ok and ctx.leverage_ok and ctx.strength_ok and ctx.capability_ok),
            "a fail-closed capability gate is down (sizing / leverage / signal strength / a "
            "future_dev capability selection), so ``_open`` would refuse every entry the "
            "describe half still wants — the pool would open positions the item never books. "
            "On an independent run that shape produces an empty run; on a shared pool it "
            "produces a wrong one, which is why it is refused rather than tolerated",
        ),
        (
            str(conflict.opposite_direction_hedge) == "close_existing",
            "opposite_direction_hedge 'close_existing' closes the position inside "
            "_phase_tail, so the realized money would never reach E(t)",
        ),
    )


@dataclass(slots=True)
class _EngineParticipant:
    """One ``_ItemStepper`` behind the phase loop's participant contract.

    Constructed with an ALREADY-BUILT stepper rather than with ``_build_stepper``'s
    arguments: the worker resolves those pins once per item today (``_replay_strategy``)
    and `C4` reuses that resolution, so re-declaring the list here would be a second place
    for it to drift. What this constructor owns instead is the refusal
    (:func:`_unsupported_shapes`), which is a property of the RESOLVED run and therefore
    knowable only once the stepper exists."""

    identity: ItemIdentity
    stream: ItemBarStream
    stepper: _ItemStepper
    instrument_id: str | None = None

    #: The bar :meth:`carry` admitted at this tick — proof that P0 ran for the bar the
    #: later phases are about to decide on. ``None`` before the item's first deciding tick.
    _current: _Bar | None = field(default=None, init=False, repr=False)
    #: The entry :meth:`entry` described and did not place, with the ``E(t)`` it was
    #: described against. Consumed by :meth:`settle`, which is the only phase allowed to
    #: book it (ADR §6 clause 6). The equity travels WITH the plan because the sizing chain
    #: must run against the snapshot the intent was formed from and no other.
    _pending: _EntryDecision | None = field(default=None, init=False, repr=False)
    _pending_equity: Decimal | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.identity.item_id != self.stream.item_id:
            raise UnsupportedStrategyShapeError(
                f"Participant identity '{self.identity.item_id}' carries item "
                f"'{self.stream.item_id}'s bar stream; an item has exactly one of each."
            )
        violations = [why for violated, why in _unsupported_shapes(self.stepper.ctx) if violated]
        if violations:
            raise UnsupportedStrategyShapeError(
                f"Item '{self.identity.item_id}' cannot participate in a shared-clock run: "
                + "; ".join(violations)
                + "."
            )

    # ---------------------------------------------------------------- item-ledger probes

    def _measured(self, book: Callable[[], None]) -> tuple[Decimal, int]:
        """Run one BOOKING half and report what the item's own ledger did.

        ``(equity delta, trade rows appended)``. Measuring rather than re-deriving is the
        whole discipline of this module: ``CarryCharges`` and ``MandatoryExit`` are amounts
        the item STATES, and the only statement that cannot drift from the engine is the
        one read back off the engine's own ledger."""
        led = self.stepper.ledger
        equity_before, trades_before = led.equity, len(led.trades)
        book()
        return equity_before - led.equity, len(led.trades) - trades_before

    def _closed_by(self, book: Callable[[], None]) -> MandatoryExit | None:
        """A close the item just booked, in the shape ``run_portfolio`` books it with.

        ``gross_pnl``/``commission`` are split the way ``booking.close_position`` splits
        them: the trade row's ``pnl`` IS ``gross - commission`` already, so stating the
        measured equity delta plus the pinned per-fill commission reproduces the engine's
        single rounding exactly — ``book_trade`` then re-derives the same net.

        The exit REASON is read off the row the close just appended rather than mapped from
        the decision's branch. The branch does not determine it on its own — a stop/exit
        collision books ``exit_signal`` or ``stop_loss`` depending on the resolved priority
        policy — and a mapping table here would be a second answer to a question the close
        path has already answered.

        Refuses a PARTIAL close: ``_phase_3_mandatory`` releases the whole position's
        committed capital, so a remainder the item still holds would be capital the pool
        thinks is free.

        The booking half runs FIRST and unconditionally, before anything is decided about
        what to report. ``stepper.finalize`` does end-of-data work on a FLAT item too — it
        cancels a resting order — and skipping it because there is nothing to report would
        leave the replay unfinished for whatever reads its ``output`` afterwards."""
        held = self.stepper.open_position()
        outflow, rows = self._measured(book)
        if held is None or rows == 0:
            return None
        size, direction = held.size, held.direction
        if rows > 1 or self.stepper.open_position() is not None:
            raise ParticipantDivergenceError(
                f"Item '{self.identity.item_id}' booked {rows} lot(s) and "
                f"{'still holds' if self.stepper.open_position() is not None else 'closed'} "
                "its position at one mandatory event; the phase loop models one FULL close "
                "per event and releases the whole position's capital."
            )
        commission = self.stepper.ctx.fill_costs.commission
        return MandatoryExit(
            decision=ItemDecision(
                kind="exit", direction=direction, reason=self.stepper.ledger.trades[-1].exit_reason
            ),
            sizing=ClosingSize(units=size),
            gross_pnl=-outflow + commission,
            commission=commission,
        )

    # ------------------------------------------------------------------- the five phases

    def carry(self, view: ItemTickView) -> CarryCharges | None:
        """P1 — admit this tick's bars (P0), then charge what the funding schedule owes.

        P0 has no hook of its own in the loop and needs none: ``_phase_1_carry`` is the
        first per-item call at a tick and is made exactly for the views that have a fresh
        bar, which is the same condition ``_step`` admits under. The bars arrive as the
        clock's ``_Bar`` values — the SAME type and the same ``_normalize`` the stepper
        consumes, because ``clock.py`` and ``engine.py`` import both from
        ``execution/state.py``. There is deliberately NO translation layer here: a second
        normalization would be a second coercion policy."""
        for bar in view.bars:
            self.stepper.admit(bar)
        self._current = view.bars[-1]
        # A described entry belongs to the tick it was described at and to no other: if the
        # pool did not admit it, ``settle`` is never called for it (``_phase_7_apply`` skips
        # a refused decision) and the plan is dead. Clearing it here, at the tick's FIRST
        # hook, is what stops a stale plan from being booked against a later valuation.
        self._pending, self._pending_equity = None, None
        plan = self.stepper.compute_carry(self._current)
        if plan is None:
            return None
        bar, held = self._current, self.stepper.open_position()
        paid, _rows = self._measured(lambda: self.stepper.book_carry(bar, plan))
        if held is None or paid == _ZERO:
            # A record that becomes available while FLAT is consumed without a charge (the
            # perp convention ``due_funding_charges`` implements). The cursor still moved.
            return None
        return CarryCharges(funding=paid)

    def mandatory_exit(self, view: ItemTickView, *, held: OpenPosition) -> MandatoryExit | None:
        """P3 — the protection/exit this tick forces, applied item-locally and reported.

        Applied here rather than deferred, and that is the loop's design: a mandatory event
        is NOT arbitrated (``_phase_3_mandatory`` books it immediately), so the two ledgers
        stay in step within one phase. Which of stop / exit / collision wins is
        ``fills._resolve_stop`` + ``engine._plan_exit`` and is not re-decided here."""
        bar = self._bar_for(view)
        decision = self.stepper.evaluate_held(bar)
        if decision is None:
            return None
        return self._closed_by(lambda: self.stepper.apply_held(bar, decision))

    def entry(
        self,
        view: ItemTickView,
        snapshot: PortfolioSnapshot,
        *,
        held: OpenPosition | None,
    ) -> ItemIntent | None:
        """P4 — the entry this item wants against ``snapshot``, committing nothing.

        Two guards before anything is described, in this order:

        **Sleeve parity (§C.3.5).** Checked on EVERY deciding tick, before the flat check,
        because the divergence it looks for is a property of the wiring rather than of the
        item's state: a share the worker passed to one derivation and not the other would
        otherwise only surface on the ticks the item happens to trade on.

        **The flat check (§C.3.2).** ``_step`` guards entry with ``if not _phase_held(bar)``
        — the *flat* test lives in the DRIVER, not in ``_evaluate_entry``, whose guard list
        carries ``pending``/``working_limit``/``working_stop`` but NOT ``position``.
        Omitting it here would let the loop arbitrate a second entry for an item that
        already holds one.

        What is deliberately NOT repeated: ``_validated_intent``'s five boundary checks.
        Letting the loop refuse a misformed intent is the point of having them there."""
        capacity = snapshot.sleeve_capacity[self.identity.item_id]
        derived = sleeve_capital(self.stepper.ctx, snapshot.equity)
        if derived != capacity:
            raise ParticipantDivergenceError(
                f"Item '{self.identity.item_id}' derives a sleeve of {derived} from E(t)="
                f"{snapshot.equity} while the pool published {capacity} at t_ms="
                f"{snapshot.t_ms}. The item would size against a capacity nobody granted."
            )
        if held is not None or self.stepper.open_position() is not None:
            return None
        bar = self._bar_for(view)
        plan = self.stepper.evaluate_entry(bar)
        if plan is None:
            return None
        if plan.want is None:
            # Nothing is wanted, so nothing is arbitrated — but the suppression counters and
            # the ``filtered_no_entry`` trace the describe half deferred are the item's own
            # journal, cost no money and reach no pool. Booking them now keeps the item's
            # ledger the same one the goldens describe; holding them would lose them, since
            # ``settle`` is only called for an ADMITTED decision.
            self.stepper.apply_entry(bar, plan, equity=snapshot.equity)
            return None
        self._pending, self._pending_equity = plan, snapshot.equity
        return form_intent(
            identity=self.identity,
            view=view,
            snapshot=snapshot,
            decision=ItemDecision(
                kind="entry",
                direction=plan.want,
                reason="entry_signal",
                evidence=plan.entry_detail,
            ),
            sizing=EntrySizing(
                config=self.stepper.ctx.config,
                fill_costs=self.stepper.ctx.fill_costs,
                # The SLEEVE, matching what ``sizing.planned_size`` runs the chain against
                # under allocation (``SIZING_BASE_DIVERGENCE`` records that this is the
                # shipped reading of Modül 11 §6.1's layer order). Passing the pool equity
                # instead would size the intent through a different chain than the one that
                # books it, and ``settle``'s size check would fire on every entry.
                base=derived,
                base_source="allocation_sleeve",
                strength=plan.strength,
            ),
        )

    def settle(self, view: ItemTickView, *, admitted: ArbitrationDecision) -> None:
        """P7 — book what arbitration GRANTED, which is not always what was wanted.

        ``size_override`` is the cap channel ``_open`` already had for the partial-fill
        path: the granted size may be smaller than the planned one (an item risk limit or
        an exposure cap), and the item must book what was granted, never what it asked for.

        The check afterwards is the fail-closed half of dual booking. If the item did not
        end up holding exactly what the pool just opened, the two books have already parted
        and every later phase — stops, funding, exposure — would be computed against a
        position one of them does not have."""
        plan, equity = self._pending, self._pending_equity
        self._pending, self._pending_equity = None, None
        if plan is None:
            raise ParticipantDivergenceError(
                f"Item '{self.identity.item_id}' was granted {admitted.granted_units} units "
                f"at t_ms={view.t_ms} for an entry it never described."
            )
        self.stepper.apply_entry(
            self._bar_for(view), plan, equity=equity, size_override=admitted.granted_units
        )
        opened = self.stepper.open_position()
        if (
            opened is None
            or opened.direction != admitted.direction
            or opened.size != admitted.granted_units
        ):
            raise ParticipantDivergenceError(
                f"Item '{self.identity.item_id}' was granted {admitted.granted_units} "
                f"{admitted.direction} units at t_ms={view.t_ms} but booked "
                f"{'nothing' if opened is None else f'{opened.size} {opened.direction}'}. "
                "The pool holds a position the item does not."
            )

    def finalize(self, view: ItemTickView) -> MandatoryExit | None:
        """P10 — the close end-of-data forces on a still-open position, or ``None``.

        ``stepper.finalize`` cancels a resting order and closes any open position at the
        last bar's close. On the shared path that close realizes money the POOL's ledger
        must see: without it ``E(t)`` ends the run holding unrealized risk and the
        composite final equity is wrong rather than merely incomplete."""
        del view  # the stepper closes at its OWN last admitted bar (``led.last_bar``)
        return self._closed_by(self.stepper.finalize)

    # ------------------------------------------------------------------------- internals

    def _bar_for(self, view: ItemTickView) -> _Bar:
        """The bar :meth:`carry` admitted for this view, refusing a skipped P0.

        Every hook is called for a view that HAS a fresh bar, and ``_phase_1_carry`` runs
        first at every tick, so a mismatch means the driver skipped a phase — which would
        have the item deciding on a bar its evaluators never saw."""
        bar = view.bars[-1] if view.bars else None
        if bar is None or self._current is None or self._current.timestamp != bar.timestamp:
            raise ParticipantDivergenceError(
                f"Item '{self.identity.item_id}' was asked to decide at t_ms={view.t_ms} "
                "before P1 admitted that tick's bar; the phases run in ADR §8.2 order."
            )
        return self._current


def _protocol_check(participant: _EngineParticipant) -> ItemParticipant:
    """mypy's structural proof that the adapter IS an ``ItemParticipant``.

    ``settle`` and ``finalize`` are REQUIRED Protocol members, never ``hasattr``-probed,
    precisely so that a participant which forgets one is a type error rather than a run
    that silently stays flat. That guarantee is only worth anything if something actually
    type-checks the assignment, and this is that something."""
    return participant


__all__ = [
    "EngineParticipantError",
    "ParticipantDivergenceError",
    "UnsupportedStrategyShapeError",
]
