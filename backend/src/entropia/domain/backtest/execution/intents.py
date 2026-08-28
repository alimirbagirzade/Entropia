"""Per-item intents formed against ONE shared portfolio snapshot (ADR 0002 §6/§7).

Canon step 4 of doc 13 §8.4 is a single sentence: *"Tum active Mainboard itemleri ayni
data + valuation snapshotiyla intent uretir."* This module is that sentence and nothing
else — the typed, side-effect-free decision an item publishes at one valuation point,
plus the immutable snapshot every item at that point is handed.

It deliberately does NOT:

* hold capital, book PnL or own a ledger — ``PortfolioLedger`` and the mutable ledger
  rewrite are ADIM 17; only the frozen READ-ONLY snapshot value lives here;
* arbitrate conflicts, cap a sleeve, or reject for solvency — those are phases P5/P6b
  and belong to ADIM 19. An intent carries ``sleeve_capacity`` as a *dependency* so the
  cap layer can apply it; it never applies it itself;
* run the phase loop or drive the clock — ``run_portfolio`` is ADIM 18;
* decide how a position with no fresh bar is marked — OD-2 is **decided but unbuilt**
  (ADR §13.1: option (a), carry forward under a declared ``stale_after`` bound). The
  intent RECORDS which price it was formed at (``price_authority``) and chooses no
  mark policy;
* decide whether a non-executing kind may hold a sleeve — OD-6 is **decided and now
  BLOCKED AT ADMISSION** (`allocation/shared_mode_admission.py::non_executing_sleeve_holders`,
  ADIM 119); the composition never reaches this phase, so the ``blocked`` intent below
  stays as the loop-side belt to admission's braces
  (ADR §13.1: option (a) for ADIM 20, block a shared plan whose active entries include a
  non-executing kind; §13.1 puts that block at ADMISSION, not here). A Trading Signal /
  Trade Log item gets a ``blocked`` intent naming the honest V1 boundary, which is what
  (a) and the rejected (b) agree on at this phase.

**Nothing in production imports this module.** As with the ADIM 15 clock, the rollback is
"delete the module": ``run_engine`` keeps its signature *and* its semantics (ADR §3.2),
so no golden digest, ``ENGINE_VERSION`` or ``execution_key`` moves because this file
exists. ``test_the_clock_is_not_wired_into_production_yet`` names this module as the one
permitted importer of ``execution.clock``, and its sibling asserts nothing imports THIS.

Design notes that are contracts, not taste
------------------------------------------
**The decision is an INPUT, not something recomputed here.** An item's entry/exit/scale
decision is path-dependent across bars: it is produced by mutable ``BlockEvaluator``
state, the ``prev_entry_signal`` / ``prev_scale_signal`` edge detectors
(``engine.py:2714``, ``:3002``) and a ledger equity read *after* funding has been applied
(``engine.py:1900-1908``). A single-tick pure function cannot re-derive it, and
re-implementing the ~230-line entry block (``engine.py:2430-2661``) would create a second
engine that silently drifts from the first. So :class:`ItemDecision` is handed in, and
this module's job is to *type, price, size and trace* it — never to re-decide it.

**Sizes come from the shipped sizing chain, never from new arithmetic.** An entry's
pre-cap size is ``sizing._position_size`` over ``costs._effective_fill``; a scale layer's
is ``scaling.resolve_scale_layer_size``. Those are the exact functions ``run_engine``
calls, so parity is structural rather than a number this module hopes matches.

**The sleeve cap is NOT applied.** ``sizing.planned_size`` folds ``_cap_to_sleeve`` in
today; canon splits that (Modül 11 §6.1 layers: signal → sizing → item risk → allocation
sleeve → ledger, and ADR §8.2 P6a vs P6b). ``desired_size`` here is the pre-cap layer
only. See :data:`SIZING_BASE_DIVERGENCE` for the one open question this exposes.

**Mandatory events are formed BEFORE the snapshot exists.** ADR §6 rule 4 and Modül 11
§5.2: stops, exits, funding and fees are resolved at P1-P3, *before* ``E(t)`` is
published. :func:`form_mandatory_intent` therefore takes **no snapshot argument at all**,
so a P3 decision structurally *cannot depend on* ``E(t)``. To be precise about what that
does and does not buy: it makes the dependency impossible, not the call order — nothing
stops a caller building a snapshot first and forming the mandatory intent afterwards. The
order itself is the phase loop's obligation (ADIM 18). :func:`form_intent` (P4) refuses a
mandatory kind for the same reason, from the other side.

**Nothing is ever silently dropped.** ``no_op`` and ``blocked`` are first-class values
with their own reason tokens (ADR §6 rule 5). :func:`form_intents` returns exactly one
intent per view — structurally, one append per view — and refuses a decision for an item
that is not on the tick's axis instead of ignoring it.

**Reason tokens are the engine's own, by convention and by test.** Every ``blocked``
reason this module is *intended* to carry is a token ``run_engine`` already writes into
its decision trace (``sizing.blocked_reason``, ``scaling.resolve_scale_rejection``).
``ItemDecision.reason`` is a free ``str`` and this module does not police it — the engine
publishes no single exported set to police it against, and inventing one here would be a
second vocabulary. What IS pinned is the other direction: :data:`INTENT_LAYER_REASONS` is
closed at exactly three tokens — the states that only exist once there IS a shared axis —
and a test asserts they are disjoint from the live engine tokens read out of source.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal

from entropia.domain.backtest.execution.clock import ClockTick, ItemTickView
from entropia.domain.backtest.execution.constants import _ONE, _ZERO
from entropia.domain.backtest.execution.costs import _effective_fill
from entropia.domain.backtest.execution.scaling import resolve_scale_layer_size
from entropia.domain.backtest.execution.sizing import _position_size

if TYPE_CHECKING:  # pragma: no cover - typing only
    from entropia.domain.backtest.execution.costs import FillCosts
    from entropia.domain.strategy.config import StrategyConfig

# Pins the intent SHAPE and the reason vocabulary, exactly as ``CLOCK_POLICY_VERSION``
# pins the axis rule. ADR §10.3 places the manifest fields in ADIM 20; this constant
# exists so the contract it names has one home from its first line, not so it ships early.
INTENT_CONTRACT_VERSION = "item-intent-v1"

_SNAPSHOT_IDENTITY_NAMESPACE = "entropia.backtest.portfolio.snapshot"

IntentKind = Literal["entry", "scale_in", "exit", "partial_exit", "no_op", "blocked"]
"""ADR §6, verbatim. ``exit``/``partial_exit`` are P3 kinds (see rule 4)."""

IntentPhase = Literal["P3", "P4"]
"""Which side of the valuation point the intent was formed on (ADR §8.2).

``P3`` — mandatory protection/exit, formed BEFORE ``E(t)`` exists.
``P4`` — discretionary entry/scale, formed AGAINST the published snapshot."""

PriceAuthority = Literal["fresh_bar_close", "stale_last_close", "unavailable"]
"""Where ``reference_price`` came from — a fact, never a mark policy (OD-2)."""

SizingBaseSource = Literal["portfolio_equity", "allocation_sleeve"]
"""Which capital figure the pre-cap sizing chain was run against — see
:data:`SIZING_BASE_DIVERGENCE`."""

MANDATORY_KINDS: frozenset[str] = frozenset({"exit", "partial_exit"})
"""Resolved at P3, before the snapshot exists (ADR §6 rule 4; Modül 11 §5.2)."""

ACTIONABLE_KINDS: frozenset[str] = frozenset({"entry", "scale_in", "exit", "partial_exit"})
"""Kinds that assert the item actually wants to do something at this tick."""

NO_BAR_AT_TICK = "no_bar_at_tick"
"""ADR §5: a tick at which item *i* has no bar is not a decision for item *i*. The item
is still present on the axis (its open position is part of ``E(t)``), so it emits a
traced ``no_op`` rather than vanishing from the tick."""

NO_SIGNAL_AT_TICK = "no_signal_at_tick"
"""The item had a fresh bar and its evaluators fired nothing. A real ``no_op``."""

ITEM_KIND_DOES_NOT_EXECUTE = "item_kind_does_not_execute"
"""Trading Signal / Trade Log: pinned and participating, but the V1 bar-replay engine
runs no standalone simulation for them (``engine.ItemRun.output is None``). Emitting a
``blocked`` intent is what OD-6 (a) and (b) agree on at this phase — whether such an item
may hold a sleeve at all is the open part and is NOT decided here."""

INTENT_LAYER_REASONS: frozenset[str] = frozenset(
    {NO_BAR_AT_TICK, NO_SIGNAL_AT_TICK, ITEM_KIND_DOES_NOT_EXECUTE}
)
"""The ONLY reason tokens this layer introduces. Everything else must be a token the
shipped engine already emits, so an intent's trace reads in the engine's vocabulary."""

SIZING_BASE_DIVERGENCE = (
    "Modül 11 §6.1 orders the layers signal -> sizing -> item risk -> allocation sleeve "
    "-> ledger, so the sizing chain's capital base precedes the sleeve. Shipped "
    "``sizing.planned_size`` instead passes the SLEEVE as the base to ``_position_size`` "
    "whenever allocation is on (sizing.py:312-316), making the sleeve both the base and "
    "the cap. This module resolves nothing: the caller states the base it used and the "
    "intent records it as ``sizing_base_source``, so the divergence is visible in the "
    "trace and can be adjudicated with the ADIM 20 ENGINE_VERSION bump."
)

_EMPTY: Mapping[str, Any] = MappingProxyType({})


def _frozen(mapping: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """A read-only view over a defensive copy — an intent cannot be edited after the fact."""
    return _EMPTY if not mapping else MappingProxyType(dict(mapping))


def _frozen_decimals(mapping: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
    return MappingProxyType(dict(mapping))


def _canonical_decimal(value: Decimal) -> str:
    """One spelling per NUMBER, so a digest identifies a valuation and not a format.

    ``Decimal("3600") == Decimal("3600.00")`` but their ``str`` forms differ, and the two
    arise naturally from the same arithmetic (a quantized ledger read vs an unquantized
    share computation). ``normalize`` collapses the exponent; ``0`` is special-cased
    because ``Decimal("0.00").normalize()`` is ``Decimal("0")`` while
    ``Decimal("0E+2").normalize()`` is ``Decimal("0E+2")``."""
    if value == _ZERO:
        return "0"
    return str(value.normalize())


class IntentError(ValueError):
    """An intent cannot be formed from the inputs as given.

    Mirrors ``clock.ClockAxisError``: a ``ValueError`` the worker turns into a failed
    run. Every subclass is a fail-closed refusal, never a degraded intent."""


class SnapshotMismatchError(IntentError):
    """The snapshot was published at a different instant than the item's view.

    The whole point of the phase order is that every item at ``t`` sizes against the SAME
    ``E(t)``. Forming an intent against a snapshot from another tick would reintroduce
    exactly the per-item drift the unified clock exists to remove."""


class UnknownItemError(IntentError):
    """The snapshot does not know this item.

    A snapshot that omits a participating item is not a portfolio-wide valuation, so its
    ``E(t)`` cannot be the one this item is entitled to size against."""


class NoDecisionAtTickError(IntentError):
    """An actionable intent was requested for an item with no fresh bar at this tick.

    ADR §5 is explicit that such a tick is *not a decision* for that item; producing an
    entry there would size against a price the item has not seen."""


class MandatoryEventNotAnIntentError(IntentError):
    """A stop/exit was offered to the P4 former.

    ADR §6 rule 4: stops, exits, funding and fees resolve BEFORE the valuation snapshot
    exists (Modül 11 §5.2). Forming one against the snapshot would place a mandatory
    event after the valuation point and invert the canonical order. Use
    :func:`form_mandatory_intent`, which cannot see a snapshot at all."""


class MismatchedItemViewError(IntentError):
    """An item's identity was paired with another item's tick view.

    Every intent is built half from the identity (provenance, snapshot lookup) and half
    from the view (price, instant, staleness). Letting the two disagree would produce an
    intent attributed to one item and priced off another — cross-item contamination in the
    exact place ADR §6 rule 2 forbids it."""


class UndirectedIntentError(IntentError):
    """An actionable intent carries no usable direction.

    Fill pricing takes a side; an absent direction would silently be treated as a sell."""


class MissingSizingInputsError(IntentError):
    """An actionable intent was requested without the inputs its size is computed from.

    A sized intent with a fabricated 0 would read as "the strategy wanted nothing", which
    is a different — and false — statement from "the size could not be computed"."""


@dataclass(frozen=True, slots=True)
class ItemIdentity:
    """One item's pinned identity, as the run manifest froze it.

    Every field is read from ``manifest["mainboard_items"]`` (``item_id``, ``item_kind``,
    ``root_id``, ``selected_revision_id``) or its sibling label map
    (``manifest["mainboard_item_labels"]``) — never joined from the live composition. An
    intent must name the EXACT revision it was formed from, so a historical trace can be
    read back without re-interpreting today's registry (doc 13 §11.1).

    ``pin_ordinal`` is the item's index in ``manifest._pinned_items``' deterministic order
    (sorted by ``(str(root_id), str(selected_revision_id))``) — the first half of the
    ``(pin_ordinal, item_id)`` tie-break of ADR §4.4. Never DOM order (``position`` is
    presentation, doc 01 §5.2), never DB query order, never arrival order."""

    item_id: str
    item_kind: str
    pin_ordinal: int
    root_id: str | None = None
    selected_revision_id: str | None = None
    item_label: str | None = None

    @property
    def executes(self) -> bool:
        """Does the V1 bar-replay engine run a simulation for this kind?

        Only ``strategy`` reaches ``run_engine`` (``jobs/backtest_engine.py:596-602``);
        Trading Signal and Trade Log are pinned, participate, and produce
        ``ItemRun.output is None``. Kept as a property on the identity so no caller
        re-derives it from a kind string."""
        return self.item_kind == "strategy"


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """The ONE valuation published at a tick, handed to every item unchanged (ADR §7).

    Frozen, with read-only mappings, because "every item sees the same snapshot" has to be
    structural. An item that could mutate ``sleeve_capacity`` would silently change what
    its siblings size against, which is the defect the whole programme removes. The
    freezing, the derived ``item_ids`` and the identity are all done in ``__post_init__``,
    so a snapshot constructed DIRECTLY with plain dicts carries the same guarantees as one
    from :func:`build_snapshot` — the invariant does not depend on using the factory.

    ``__post_init__`` also enforces the one invariant a snapshot must carry on its own:
    every participating item appears in every per-item map, so an item can never be
    *missing* from the portfolio's own valuation.

    This is the read-only VALUE only. The mutable ``PortfolioLedger`` that derives it —
    and the ``E(t)`` rule that decides when a point is appended — is ADIM 17."""

    t_ms: int
    equity: Decimal
    reserve_nominal: Decimal
    allocatable: Decimal
    sleeve_capacity: Mapping[str, Decimal]
    deployed_notional: Mapping[str, Decimal]
    unallocated: Decimal
    item_ids: tuple[str, ...] = field(default=(), compare=False)
    identity: str = field(default="", compare=False, repr=False)

    def __post_init__(self) -> None:
        missing = set(self.sleeve_capacity) ^ set(self.deployed_notional)
        if missing:
            raise UnknownItemError(
                "A snapshot must value every participating item; these appear in only one "
                f"map: {sorted(missing)}."
            )
        object.__setattr__(self, "sleeve_capacity", _frozen_decimals(self.sleeve_capacity))
        object.__setattr__(self, "deployed_notional", _frozen_decimals(self.deployed_notional))
        # Derived, never accepted from the caller: a snapshot whose ``item_ids`` disagreed
        # with its maps would hash an item set it does not actually value.
        object.__setattr__(self, "item_ids", tuple(sorted(self.sleeve_capacity)))
        object.__setattr__(self, "identity", self._compute_identity())

    def remaining_sleeve_capacity(self, item_id: str) -> Decimal:
        """``max(0, Ci(t) - deployed_notional_i)`` — ADR §7, *a sleeve is a cap, not a
        wallet*. Read by the P6b cap layer (ADIM 19); published here so that layer has one
        definition to obey instead of re-deriving the subtraction at each call site."""
        if item_id not in self.sleeve_capacity:
            raise UnknownItemError(f"Item '{item_id}' is not in this portfolio snapshot.")
        return max(_ZERO, self.sleeve_capacity[item_id] - self.deployed_notional[item_id])

    def _compute_identity(self) -> str:
        """A deterministic sha256 identity for THIS valuation.

        Carried into every intent formed against it, so "all items saw one snapshot" is a
        checkable equality over the intents alone — no reference to the snapshot object,
        which a later serialization boundary would lose.

        Computed ONCE, in ``__post_init__``. As a recomputing property it made a tick of
        *n* items cost *n* full re-hashes of all *n* items — quadratic in the item count,
        in the one loop the whole programme exists to make linear.

        Every ``Decimal`` goes through :func:`_canonical_decimal` first. Otherwise the
        digest would identify the *formatting* rather than the valuation: a ledger that
        quantizes equity to ``0.01`` on one tick and not the next, or a sleeve computed as
        ``9000 * 40 / 100`` (``3600.00``) beside a fixture's ``3600``, are the SAME
        valuation and compare ``==`` under Decimal semantics, but would hash differently."""
        digest = hashlib.sha256()
        digest.update(_SNAPSHOT_IDENTITY_NAMESPACE.encode("utf-8"))
        for part in (
            INTENT_CONTRACT_VERSION,
            str(self.t_ms),
            _canonical_decimal(self.equity),
            _canonical_decimal(self.reserve_nominal),
            _canonical_decimal(self.allocatable),
            _canonical_decimal(self.unallocated),
        ):
            digest.update(b"\x1f")
            digest.update(part.encode("utf-8"))
        for item_id in self.item_ids:
            digest.update(b"\x1f")
            digest.update(
                f"{item_id}={_canonical_decimal(self.sleeve_capacity[item_id])}"
                f"/{_canonical_decimal(self.deployed_notional[item_id])}".encode()
            )
        return digest.hexdigest()


def build_snapshot(
    *,
    t_ms: int,
    equity: Decimal,
    reserve_nominal: Decimal,
    sleeve_capacity: Mapping[str, Decimal],
    deployed_notional: Mapping[str, Decimal],
) -> PortfolioSnapshot:
    """Freeze one valuation point (ADR §7).

    ``A(t) = max(0, E(t) - R0)`` and ``U(t) = A(t) - sum(Ci(t))`` are DERIVED here so the
    three figures can never be published inconsistently — the shape of defect the
    sequential fold produced. ``R0`` is taken as given: it is fixed nominal at run start
    (doc 13 §0.2, §6.1; Modül 11 §1.2.6) and is never re-derived from ``E(t)``.

    ``item_ids`` is sorted (in ``__post_init__``), so a snapshot built from a dict the DB
    happened to iterate in a different order is byte-identical — and so ``identity`` is.

    ``U(t)`` is deliberately NOT floored at zero, unlike ``A(t)``. ADR §7 floors the
    allocatable pool and says ``U0`` is never borrowed; it fixes no floor for ``U(t)``
    itself. Sleeves summing past ``A(t)`` means the plan over-allocated — a state
    ``allocation.rules.validate_allocation`` refuses upstream — and a negative ``U(t)``
    REPORTS that, where clamping to zero would hide it behind a healthy-looking figure."""
    allocatable = max(_ZERO, equity - reserve_nominal)
    return PortfolioSnapshot(
        t_ms=t_ms,
        equity=equity,
        reserve_nominal=reserve_nominal,
        allocatable=allocatable,
        sleeve_capacity=sleeve_capacity,
        deployed_notional=deployed_notional,
        unallocated=allocatable - sum(sleeve_capacity.values(), _ZERO),
    )


@dataclass(frozen=True, slots=True)
class EntrySizing:
    """Inputs for the pre-cap Strategy-Details sizing chain (ADR §8.2 P6a).

    ``base`` is the capital figure the chain runs against and ``base_source`` records
    which figure that was — see :data:`SIZING_BASE_DIVERGENCE`. Nothing here applies the
    allocation sleeve cap; that is P6b."""

    config: StrategyConfig
    fill_costs: FillCosts
    base: Decimal
    base_source: SizingBaseSource
    strength: Decimal = _ONE


@dataclass(frozen=True, slots=True)
class ScaleSizing:
    """Inputs for a scale layer's candidate size (``scaling.resolve_scale_layer_size``).

    The ladder is deliberately independent of ``_position_size``: it has no leverage and
    no signal-strength multiplier (§11.3). Modelling it through the entry chain would
    change shipped scale sizes, so the two paths stay separate here too."""

    basis: str
    value: Decimal
    initial_size: Decimal
    current_size: Decimal


@dataclass(frozen=True, slots=True)
class ClosingSize:
    """How much of an open position a P3 mandatory event closes.

    An exit's size is NOT a product of the entry sizing chain — it is a fraction of the
    position already held, derived by the engine's own close path
    (``booking.close_position`` with ``fraction=close_fraction``, from
    ``position_exit_logic.close_percentage``). That resolver runs at P3, before this
    intent is recorded, so the size is *stated* here rather than re-derived: re-deriving
    it would mean a second implementation of the close-fraction rule, free to drift from
    the one that actually books the trade.

    It is required rather than defaulted, for the same reason an entry's sizing inputs
    are: a mandatory exit recorded as size 0 would read as "closed nothing"."""

    units: Decimal


@dataclass(frozen=True, slots=True)
class ItemDecision:
    """What the item's own evaluators concluded at this tick — the INPUT to intent forming.

    This is handed in rather than recomputed: the conclusion depends on mutable
    ``BlockEvaluator`` warmup state and on cross-bar edge detectors, so it is not a
    function of one tick (see the module docstring). ``reason`` must be a token the engine
    already emits, or one of :data:`INTENT_LAYER_REASONS`.

    ``evidence`` carries the rule ids / block ids the engine's own
    ``entry_signal.detail["rule"]`` snapshot already produces, so an intent's justification
    is the engine's, not a paraphrase."""

    kind: IntentKind
    reason: str
    direction: str | None = None
    evidence: Mapping[str, Any] = field(default=_EMPTY)


@dataclass(frozen=True, slots=True)
class ItemIntent:
    """One item's typed, side-effect-free decision at one valuation point (ADR §6).

    Pure by construction: forming it writes no ledger, performs no I/O and mutates no item
    state. Blind to siblings by construction too — it is built from the item's own view
    plus the portfolio AGGREGATE, never from another item's position, cursor or pending
    order (doc 13 §8.4 step 4 / Modül 11 §6.2 step 4: *"Bir itemin yeni orderi baska
    itemin signal gorusunu degistirmez."*).

    ``dependencies`` is what this intent's validity RESTS ON — the snapshot it was formed
    against and the exact pinned revision it speaks for. A later phase can therefore
    verify an intent belongs to the tick it is being applied at, instead of trusting call
    order. ``diagnostics`` is measurement only: it never carries a threshold."""

    identity: ItemIdentity
    t_ms: int
    phase: IntentPhase
    kind: IntentKind
    direction: str | None
    desired_size: Decimal
    reference_price: Decimal | None
    effective_price: Decimal | None
    price_authority: PriceAuthority
    reason: str
    contract_version: str
    evidence: Mapping[str, Any]
    dependencies: Mapping[str, Any]
    diagnostics: Mapping[str, Any]

    @property
    def item_id(self) -> str:
        return self.identity.item_id

    @property
    def is_actionable(self) -> bool:
        """Does this intent ask for an order? ``no_op``/``blocked`` do not — and they are
        emitted anyway (ADR §6 rule 5), which is what makes a suppression auditable."""
        return self.kind in ACTIONABLE_KINDS

    @property
    def snapshot_identity(self) -> str | None:
        """The valuation this intent was formed against; ``None`` for a P3 mandatory
        event, which by contract is resolved before any snapshot exists."""
        value = self.dependencies.get("snapshot_identity")
        return str(value) if value is not None else None


def price_for(view: ItemTickView) -> tuple[Decimal | None, PriceAuthority]:
    """The price this item's intent is formed at, and where it came from.

    A fresh bar's close is the decision price the engine already uses. With no fresh bar
    the item's last closed bar is reported instead and labelled ``stale_last_close`` — a
    LABEL, not a forward-fill decision: whether such a price may be used at all, and for
    how long, is OD-2 and is answered by the caller, not here.

    When one item carries two bars at the same instant the clock surfaces both (axis dedup
    is of the axis, never of an item's data); the LAST is taken, matching the engine's
    strictly-forward replay and the clock's own cursor.

    PUBLIC because OD-2(a)'s mark binding reads it: ``portfolio_engine`` offers the same
    ``(price, authority)`` pair to ``PortfolioLedger.valuation`` at ``PV``. The alternative
    was a second transcription of this rule at the binding site, which is exactly the drift
    ADIM 126 measured. The bound that judges the pair still lives with the policy
    (``MARK_STALE_AFTER_MS``), not here — this function labels, it does not decide."""
    if view.bars:
        return view.bars[-1].close, "fresh_bar_close"
    if view.last_closed is not None:
        return view.last_closed.close, "stale_last_close"
    return None, "unavailable"


def _sized(
    kind: IntentKind,
    direction: str | None,
    reference_price: Decimal | None,
    sizing: EntrySizing | ScaleSizing | ClosingSize | None,
) -> tuple[Decimal, Decimal | None]:
    """``(desired_size, effective_price)`` from the SHIPPED sizing functions only.

    ``entry`` runs ``costs._effective_fill`` then ``sizing._position_size`` — the exact
    pre-sleeve chain ``planned_size`` runs — and stops there: ``_cap_to_sleeve`` is P6b.
    ``scale_in`` runs ``scaling.resolve_scale_layer_size`` and ``exit``/``partial_exit``
    carry the close size their P3 resolver already determined; neither is re-priced here,
    because re-pricing an already-resolved event would create a second answer to a
    question the engine has answered. A non-actionable kind is size 0 with no price
    authority claimed."""
    if kind == "no_op" or kind == "blocked":
        return _ZERO, None
    if kind in MANDATORY_KINDS:
        if not isinstance(sizing, ClosingSize):
            raise MissingSizingInputsError(f"A '{kind}' intent needs a ClosingSize.")
        return sizing.units, reference_price
    if kind == "scale_in":
        if not isinstance(sizing, ScaleSizing):
            raise MissingSizingInputsError("A 'scale_in' intent needs ScaleSizing inputs.")
        return (
            resolve_scale_layer_size(
                basis=sizing.basis,
                value=sizing.value,
                initial_size=sizing.initial_size,
                current_size=sizing.current_size,
            ),
            reference_price,
        )
    if not isinstance(sizing, EntrySizing):
        raise MissingSizingInputsError(f"A '{kind}' intent needs EntrySizing inputs.")
    if reference_price is None:
        raise MissingSizingInputsError(f"A '{kind}' intent has no price to size against.")
    if direction not in ("long", "short"):
        # ``_effective_fill`` takes a boolean side, so an absent or unrecognised direction
        # would be priced as a SELL: the adverse adjustment flips sign, the fill looks
        # better than it is and the size computed from it comes out larger. Fail closed
        # rather than let a directionless entry be silently priced as a short.
        raise UndirectedIntentError(
            f"A '{kind}' intent needs direction 'long' or 'short', got {direction!r}."
        )
    effective = _effective_fill(
        reference_price,
        is_buy=direction == "long",
        half_spread=sizing.fill_costs.half_spread,
        slip=sizing.fill_costs.slippage,
    )
    return (
        _position_size(sizing.config, effective, sizing.base, sizing.strength),
        effective,
    )


def _diagnostics(view: ItemTickView) -> Mapping[str, Any]:
    """Measurement only — no threshold, no policy (OD-2)."""
    return _frozen(
        {
            "pin_ordinal": view.pin_ordinal,
            "bars_at_tick": len(view.bars),
            "is_decision": view.is_decision,
            "staleness_ms": view.staleness_ms,
            "duplicate_instant": len(view.bars) > 1,
        }
    )


def _build(
    *,
    identity: ItemIdentity,
    view: ItemTickView,
    phase: IntentPhase,
    decision: ItemDecision,
    sizing: EntrySizing | ScaleSizing | ClosingSize | None,
    snapshot: PortfolioSnapshot | None,
) -> ItemIntent:
    # The single place the two halves of "one item" are checked against each other. Price,
    # t_ms, staleness and pin_ordinal are read off ``view`` while the snapshot is looked up
    # by ``identity.item_id``; without this gate a mismatched pair yields a well-formed
    # intent for item A sized off item B's bar — precisely the cross-item contamination
    # ADR §6 rule 2 forbids, arriving through the front door.
    if identity.item_id != view.item_id:
        raise MismatchedItemViewError(
            f"Identity '{identity.item_id}' was given item '{view.item_id}'s tick view; an "
            "intent may only ever be formed from its own item's data."
        )
    reference_price, authority = price_for(view)
    desired_size, effective_price = _sized(
        decision.kind, decision.direction, reference_price, sizing
    )
    dependencies: dict[str, Any] = {
        "root_id": identity.root_id,
        "selected_revision_id": identity.selected_revision_id,
        "item_kind": identity.item_kind,
        "contract_version": INTENT_CONTRACT_VERSION,
    }
    if isinstance(sizing, EntrySizing):
        dependencies["sizing_base"] = sizing.base
        dependencies["sizing_base_source"] = sizing.base_source
    if snapshot is not None:
        dependencies["snapshot_identity"] = snapshot.identity
        dependencies["snapshot_t_ms"] = snapshot.t_ms
        dependencies["portfolio_equity"] = snapshot.equity
        dependencies["reserve_nominal"] = snapshot.reserve_nominal
        dependencies["sleeve_capacity"] = snapshot.sleeve_capacity[identity.item_id]
        dependencies["remaining_sleeve_capacity"] = snapshot.remaining_sleeve_capacity(
            identity.item_id
        )
    return ItemIntent(
        identity=identity,
        t_ms=view.t_ms,
        phase=phase,
        kind=decision.kind,
        direction=decision.direction,
        desired_size=desired_size,
        reference_price=reference_price,
        effective_price=effective_price,
        price_authority=authority,
        reason=decision.reason,
        contract_version=INTENT_CONTRACT_VERSION,
        evidence=_frozen(decision.evidence),
        dependencies=_frozen(dependencies),
        diagnostics=_diagnostics(view),
    )


def form_intent(
    *,
    identity: ItemIdentity,
    view: ItemTickView,
    snapshot: PortfolioSnapshot,
    decision: ItemDecision,
    sizing: EntrySizing | ScaleSizing | None = None,
) -> ItemIntent:
    """Form ONE item's P4 intent against the published snapshot (doc 13 §8.4 step 4).

    Pure, idempotent and blind to siblings: called twice with the same inputs it returns an
    equal value, and it reads the portfolio only as an aggregate.

    Fails closed rather than degrading — a snapshot from another tick, an item the snapshot
    does not value, an actionable decision at a tick with no bar, and a mandatory event
    offered to P4 each raise instead of producing a plausible-looking intent."""
    if snapshot.t_ms != view.t_ms:
        raise SnapshotMismatchError(
            f"Item '{identity.item_id}' is at t_ms={view.t_ms} but the snapshot was "
            f"published at t_ms={snapshot.t_ms}; one valuation point, one snapshot."
        )
    if identity.item_id not in snapshot.sleeve_capacity:
        raise UnknownItemError(
            f"Item '{identity.item_id}' is not valued by this portfolio snapshot."
        )
    if decision.kind in MANDATORY_KINDS:
        raise MandatoryEventNotAnIntentError(
            f"'{decision.kind}' is a mandatory event resolved at P3, before E(t) exists "
            "(ADR §6 rule 4); use form_mandatory_intent."
        )
    if decision.kind in ACTIONABLE_KINDS and not view.is_decision:
        raise NoDecisionAtTickError(
            f"Item '{identity.item_id}' has no bar at t_ms={view.t_ms}, so this tick is "
            "not a decision for it (ADR §5)."
        )
    return _build(
        identity=identity,
        view=view,
        phase="P4",
        decision=decision,
        sizing=sizing,
        snapshot=snapshot,
    )


def form_mandatory_intent(
    *,
    identity: ItemIdentity,
    view: ItemTickView,
    decision: ItemDecision,
    sizing: ClosingSize | None = None,
) -> ItemIntent:
    """Record a P3 mandatory protection/exit decision as a typed intent.

    Takes **no snapshot**, and that is the contract: stops, exits, funding and fees are
    resolved before ``E(t)`` is published (ADR §6 rule 4; Modül 11 §5.2), so this former
    structurally cannot size against a valuation that does not exist yet. Its result
    carries ``phase="P3"`` and a ``None`` :attr:`ItemIntent.snapshot_identity`.

    It records the decision; it does not make or re-order it. Which of stop / exit /
    collision wins is the engine's versioned priority policy (``fills._resolve_stop``,
    ``engine._plan_exit``, the stop+exit collision block at ``engine.py:2281-2320``) and
    is unchanged by this module."""
    if decision.kind not in MANDATORY_KINDS and decision.kind in ACTIONABLE_KINDS:
        raise MandatoryEventNotAnIntentError(
            f"'{decision.kind}' is a P4 discretionary intent and must be formed against "
            "the published snapshot; use form_intent."
        )
    if decision.kind in MANDATORY_KINDS and not view.is_decision:
        raise NoDecisionAtTickError(
            f"Item '{identity.item_id}' has no bar at t_ms={view.t_ms}, so no mandatory "
            "event can be resolved on its own data here (ADR §5)."
        )
    return _build(
        identity=identity,
        view=view,
        phase="P3",
        decision=decision,
        sizing=sizing,
        snapshot=None,
    )


def idle_decision(identity: ItemIdentity, view: ItemTickView) -> ItemDecision:
    """The traced non-decision for an item that wants nothing at this tick.

    Three distinct silences, three distinct tokens — never one shrugging default:
    a non-executing kind is ``blocked`` (there is no simulation to speak for it), an item
    without a bar is a ``no_op`` that is *not a decision* (ADR §5), and an item with a bar
    and no signal is a genuine ``no_op``. Offered as a helper so a caller cannot invent a
    fourth spelling of "nothing happened"."""
    if not identity.executes:
        return ItemDecision(kind="blocked", reason=ITEM_KIND_DOES_NOT_EXECUTE)
    if not view.is_decision:
        return ItemDecision(kind="no_op", reason=NO_BAR_AT_TICK)
    return ItemDecision(kind="no_op", reason=NO_SIGNAL_AT_TICK)


def form_intents(
    tick: ClockTick,
    snapshot: PortfolioSnapshot,
    identities: Mapping[str, ItemIdentity],
    decisions: Mapping[str, tuple[ItemDecision, EntrySizing | ScaleSizing | None]],
) -> tuple[ItemIntent, ...]:
    """Form the whole tick's P4 intents — one per item, none dropped (ADR §6 rule 5).

    Order is the clock's ``(pin_ordinal, item_id)``, taken from ``tick.views`` rather than
    from ``decisions``: a mapping built by a DB query, a dict literal or an HTTP payload
    yields the same sequence, because the order is a property of the pinned manifest and
    never of how the caller happened to collect the work (ADR §4.4, doc 13 §13).

    An item with no supplied decision is not skipped — it gets :func:`idle_decision`, so
    "the caller forgot this item" and "this item chose nothing" are both visible and are
    both traced. Symmetrically, a decision for an item that is NOT on this tick's axis is
    refused rather than ignored: discarding it would drop a real decision silently, which
    is the failure mode this whole layer is built against.

    Exactly one intent per view is returned, and every one carries the same
    ``snapshot_identity``, because they are all built from the single snapshot passed here.

    **Honest boundary:** the axis carries only items with a bar STREAM, so an item the
    engine runs nothing for (Trading Signal / Trade Log) has no view here and therefore
    receives no ``blocked`` intent from this function. Giving such an item a per-tick
    presence is the phase loop's job, and it is not built yet — until then, use
    :func:`form_intent` with :func:`idle_decision` directly for those items."""
    extra = set(decisions) - {view.item_id for view in tick.views}
    if extra:
        raise UnknownItemError(
            "These items are not on this tick's axis, so their decisions would be "
            f"discarded rather than formed: {sorted(extra)}."
        )
    intents: list[ItemIntent] = []
    for view in tick.views:
        identity = identities.get(view.item_id)
        if identity is None:
            raise UnknownItemError(
                f"No pinned identity for item '{view.item_id}' on this tick; an intent "
                "must name the exact revision it speaks for."
            )
        decision, sizing = decisions.get(view.item_id, (idle_decision(identity, view), None))
        intents.append(
            form_intent(
                identity=identity,
                view=view,
                snapshot=snapshot,
                decision=decision,
                sizing=sizing,
            )
        )
    return tuple(intents)


def snapshot_identities(intents: Sequence[ItemIntent]) -> set[str | None]:
    """The distinct valuations a batch of intents was formed against.

    A single-element set is the checkable form of *"tum active Mainboard itemleri ayni
    valuation snapshotiyla intent uretir"* (doc 13 §8.4 step 4)."""
    return {intent.snapshot_identity for intent in intents}


__all__ = [
    "ACTIONABLE_KINDS",
    "INTENT_CONTRACT_VERSION",
    "INTENT_LAYER_REASONS",
    "ITEM_KIND_DOES_NOT_EXECUTE",
    "MANDATORY_KINDS",
    "NO_BAR_AT_TICK",
    "NO_SIGNAL_AT_TICK",
    "SIZING_BASE_DIVERGENCE",
    "ClosingSize",
    "EntrySizing",
    "IntentError",
    "IntentKind",
    "IntentPhase",
    "ItemDecision",
    "ItemIdentity",
    "ItemIntent",
    "MandatoryEventNotAnIntentError",
    "MismatchedItemViewError",
    "MissingSizingInputsError",
    "NoDecisionAtTickError",
    "PortfolioSnapshot",
    "PriceAuthority",
    "ScaleSizing",
    "SizingBaseSource",
    "SnapshotMismatchError",
    "UnknownItemError",
    "build_snapshot",
    "form_intent",
    "form_intents",
    "form_mandatory_intent",
    "idle_decision",
    "price_for",
    "snapshot_identities",
]
