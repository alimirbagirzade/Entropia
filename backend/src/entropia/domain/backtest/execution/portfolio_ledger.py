"""The ONE shared portfolio ledger: capital, sleeves, exposure, solvency (ADR 0002 §7).

Canon's shared-capital model is a *single* account book. Doc 13 §8.3 and Modül 11 §5.1-§5.3
give it in five lines::

    P0 = initial_capital ;  r = reserve_cash_percent/100 ;  R0 = P0*r      # fixed nominal
    A0 = max(0, P0 - R0) ;  Ci0 = A0*wi/100 ;  U0 = A0 - sum(Ci0)
    E(t) = P0 + realized_pnl(t) - fees(t) - funding(t) - other_realized_costs(t)
    A(t) = max(0, E(t) - R0)          Ci(t) = A(t)*wi/100      (fixed: Ci = A0*wi/100)
    allowed_size = min(desired, remaining_sleeve_capacity, item_risk_limits, ledger_solvency)

What ships today is one ``_Ledger`` **per item**, each seeded from the full pool
(``engine.py:846``, ``resolve_allocation_execution``) — so an item's sleeve compounds off its
own equity and can never see a sibling's PnL, fees or funding. This module is the replacement
for that: **one** ledger per run, holding ``P0``/``R0``/``U0`` once, deriving exactly one
``PortfolioSnapshot`` per valuation point, and answering the capacity question against it.

It deliberately does NOT:

* run the phase loop or drive the clock — ``run_portfolio`` is ADIM 18. This module is the
  state the loop mutates, plus the arithmetic it mutates the state with;
* arbitrate BETWEEN items — when two intents are individually affordable but jointly
  insolvent, *which* one is rejected is **OD-3, still open** (ADR §13). :meth:`resolve_capacity`
  answers one item's question against the ledger as it stands; the selection rule is ADIM 19's;
* define cross-item conflict or ``NET`` netting — ADR §9.4 / GH #544. ``net_exposure`` here is
  a **measurement**, never an offset: no cap, no solvency figure and no margin requirement is
  computed from it (see :class:`PortfolioValuation`);
* decide how a position with no fresh bar is marked — **OD-2, still open**. A mark is *given*
  to :meth:`valuation` with the authority it came from; an unmarkable position is REPORTED,
  never valued at zero;
* model margin or leverage. Canon defines no maintenance-margin formula and Master Ref §10.2
  delegates ``leverage_mode=cross`` to a portfolio risk model that does not exist. The ledger
  therefore uses the shipped convention — **committed capital == entry-basis notional**
  (``_Position.entry_notional``, ``sizing._cap_to_sleeve``) — and no other.

**Nothing in production imports this module.** As with the ADIM 15 clock and the ADIM 16
intent layer, the rollback is "delete the module": ``run_engine`` keeps its signature *and*
its semantics (ADR §3.2), so no golden digest, ``ENGINE_VERSION`` or ``execution_key`` moves
because this file exists.

Design notes that are contracts, not taste
------------------------------------------
**The accounting identity is exact by construction, not by hope.** Every booking applies its
delta to ``equity`` with the *same incremental quantization the shipped engine uses*
(``(equity + delta).quantize(0.01)``, ``booking.py:96``, ``engine.py:1953``) and then files
**the delta that was actually applied** into its bucket. So
``E(t) == P0 + realized - fees - funding - other`` holds to the last cent at every point in
the run, and ``equity`` is byte-identical to what the shipped per-item ledger would hold. The
naive alternative — accumulate each component independently and subtract at read time — is
NOT equivalent: ``quantize`` is only translation-invariant across an exact multiple of the
quantum when the tie-break parity agrees, so a half-cent commission can land one cent apart
depending on which side of the sum it is rounded on.

**Spread and slippage are already inside the prices; they are never booked again.** The
shipped cost model folds them into the *fill price* (``costs._effective_fill``) before any PnL
is computed, so ``gross_pnl`` handed to :meth:`book_trade` already carries them. Booking them
a second time as a "cost" would double-count every fill. Only commission, funding and other
realized costs are separate ledger lines, which is exactly the split doc 13 §8.3 names.

**``E(t)`` is realized-only, so a mark never touches it.** Doc 13 §8.3's ``E(t)`` is
``P0 + realized - fees - funding - other_realized_costs``; unrealized movement is absent from
it. :meth:`valuation` therefore marks open positions at the tick's one valuation point and
reports the unrealized figure *beside* ``E(t)`` — it never folds it in. Sizing an entry off a
marked-to-market equity would be a different, uncanonical capital model.

**A sleeve is a cap, not a wallet** (ADR §7; Modül 11 §6.1). Capital is not physically
partitioned: ``Ci(t)`` bounds what an item may *newly* deploy, and ``remaining`` is
``max(0, Ci(t) - deployed_i)``. Existing open positions are never force-rebalanced when equity
moves (doc 13 §8.3, §6.1) — which is why the no-borrow guard bounds the *increase* in deployed
capital, not the standing total.

**The snapshot freezes the ledger.** ADR §8.1: *"FROZEN: no writer may run until P7"*.
:meth:`publish_snapshot` makes that structural — every booking and position mutation raises
:class:`LedgerFrozenError` until :meth:`begin_apply` opens the write phase again. "Every item
read the same ``E(t)``" then cannot be violated by a caller getting the phase order wrong.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from types import MappingProxyType
from typing import Literal

from entropia.domain.backtest.execution.constants import _HUNDRED, _MONEY, _ONE, _QTY, _ZERO
from entropia.domain.backtest.execution.intents import (
    PortfolioSnapshot,
    PriceAuthority,
    build_snapshot,
)

# Pins the accounting identity, the quanta and the rounding, exactly as
# ``CLOCK_POLICY_VERSION`` pins the axis rule and ``INTENT_CONTRACT_VERSION`` the intent
# shape. ADR §10.3 places the manifest fields in ADIM 20; this constant exists so the policy
# it names has one home from its first line, not so it ships early.
LEDGER_POLICY_VERSION = "portfolio-ledger-v1"

MONEY_QUANTUM = _MONEY
"""Every money figure the ledger publishes is a multiple of this (0.01) — the engine's own
step (``execution.constants``), so a ledger figure and an engine figure are comparable."""

QTY_QUANTUM = _QTY
"""Capacity converted from money to units quantizes here (1e-8) — the step
``sizing._cap_to_sleeve`` and the exposure clamp (``engine.py:1466``) already use."""

MONEY_ROUNDING = ROUND_HALF_EVEN
"""Pinned rather than inherited. The shipped engine calls ``.quantize(_MONEY)`` with no
``rounding=``, so it takes the ambient ``decimal`` context — which is ``ROUND_HALF_EVEN`` by
default and is what every recorded golden digest was produced under. Naming it here makes a
booked figure independent of a context a caller may have changed, without changing any value
under the default context. Note this is NOT the ``ROUND_HALF_UP`` of the allocation *preview*
(``allocation/rules.py:51``): that rounds for DISPLAY at the last step, over the same
unrounded arithmetic."""

# ---------------------------------------------------------------------- capacity vocabulary

SLEEVE_CONSTRAINT = "remaining_sleeve"
MAX_POSITION_CONSTRAINT = "max_position_notional"
EXPOSURE_CONSTRAINT = "max_total_exposure"
SOLVENCY_CONSTRAINT = "ledger_solvency"

CAPACITY_CONSTRAINTS: frozenset[str] = frozenset(
    {SLEEVE_CONSTRAINT, MAX_POSITION_CONSTRAINT, EXPOSURE_CONSTRAINT, SOLVENCY_CONSTRAINT}
)
"""The four layers ``allowed_size`` is a ``min`` over (doc 13 §8.3). ``item_risk_limits`` is
the caller's ``max_position_notional``: its authority is Strategy Details (Modül 11 §6.1
layer 3, applied at P6a by ``sizing._clamp_to_limits``), so the ledger honours one when it is
handed one and never invents one."""

SLEEVE_ZERO_CAPACITY = "sleeve_zero_capacity"
PORTFOLIO_MAX_TOTAL_EXPOSURE = "portfolio_max_total_exposure"
"""Reason tokens the shipped engine already writes into its decision trace
(``sizing.blocked_reason:344``, ``engine.py:1474``). Reused verbatim so a ledger rejection
reads in the engine's own vocabulary rather than a second one."""

NO_REQUESTED_SIZE = "no_requested_size"
UNPRICEABLE_CAPACITY = "unpriceable_capacity"
MAX_POSITION_NOTIONAL_EXCEEDED = "max_position_notional_exceeded"
LEDGER_INSOLVENT = "ledger_insolvent"

LEDGER_LAYER_REASONS: frozenset[str] = frozenset(
    {
        NO_REQUESTED_SIZE,
        UNPRICEABLE_CAPACITY,
        MAX_POSITION_NOTIONAL_EXCEEDED,
        LEDGER_INSOLVENT,
    }
)
"""The ONLY reason tokens this layer introduces — the states that exist only once capital is
genuinely shared. Everything else is a token the shipped engine already emits."""

CapacityOutcome = Literal["admitted", "capped", "rejected"]
"""``capped`` is a real, canonical outcome for the *cap* layers (doc 13 §14 test 13: the
engine applies a deterministic cap **or** reject). ``ledger_solvency`` is the one layer that
may never cap: Modül 11 §5.3 — *"engine orderi reddeder, kismi fill veya sessiz borrow
yapmaz"*."""


# ------------------------------------------------------------------------------- refusals


class LedgerError(ValueError):
    """The ledger cannot honour the operation as given.

    Mirrors ``clock.ClockAxisError`` / ``intents.IntentError``: a ``ValueError`` the worker
    turns into a failed run (ADR §11 — a ledger that cannot place a booking fails the run
    rather than skipping it). Every subclass is a fail-closed refusal."""


class InvalidCapitalPlanError(LedgerError):
    """The shared-capital plan cannot found a ledger.

    A non-positive ``P0``, a negative share or active shares summing past 100 are all
    canonical Ready-Check blockers (doc 13 §10.1; Modül 11 §7.1). They are refused here too so
    a bypassed readiness state cannot seed a pool that does not add up."""


class UnknownLedgerItemError(LedgerError):
    """An item the ledger's share plan does not know.

    Every participating item must appear in the plan — with share ``0`` when it has no active
    entry. A ``0`` share is a real, zero-capacity sleeve; an ABSENT item would silently be
    valued by nothing at all."""


class LedgerFrozenError(LedgerError):
    """A write was attempted between ``PV`` and ``P7`` (ADR §8.1).

    The whole point of publishing exactly one snapshot per tick is that every item sizes
    against the same ``E(t)``. A booking in that window would change ``E(t)`` under items that
    have already read it — the per-item drift the unified clock exists to remove."""


class MismatchedSnapshotError(LedgerError):
    """A capacity question was asked against a valuation from another tick.

    The sleeve headroom comes from the snapshot and the solvency headroom from the ledger, so
    a snapshot published at a different instant would answer half the question from one
    valuation point and half from another — the per-item drift the unified clock removes,
    arriving through the front door. Mirrors ``intents.SnapshotMismatchError`` on the intent
    side."""


class LedgerSolvencyViolation(LedgerError):
    """Deploying this capital would borrow.

    Reserve cash is capital active items cannot use (Modül 11 §5.1) and unallocated cash is
    never auto-borrowed (doc 13 §6.1 *"fark unallocated cash olarak boşta kalir ve başka
    itemler tarafindan otomatik kullanilmaz"*). Reaching this exception means a caller
    deployed without asking :meth:`resolve_capacity` first: it is a programming error, and it
    fails closed rather than quietly overdrawing the pool."""


class PositionStateError(LedgerError):
    """The position operation contradicts what the ledger holds for that item."""


# --------------------------------------------------------------------------- value types


def _frozen_decimals(mapping: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
    return MappingProxyType(dict(mapping))


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)


@dataclass(frozen=True, slots=True)
class SleevePlan:
    """The run's capital structure, resolved ONCE and never re-derived (doc 13 §8.3).

    ``reserve_nominal`` is ``R0``, a fixed nominal amount (doc 13 §0.2, §6.1; Modül 11
    §1.2.6) — *"Reserve orani her barda current equitye yeniden uygulanmaz"*. It is taken as a
    given amount rather than a percent so that nothing downstream is even able to re-apply the
    percentage to a later equity.

    ``shares`` must carry EVERY participating item; an item with no active entry carries share
    ``0``. ``allocatable_initial`` (``A0``), ``initial_sleeves`` (``Ci0``) and
    ``unallocated_initial`` (``U0``) are derived in ``__post_init__``, so a plan constructed
    directly carries the same guarantees as one from :func:`build_sleeve_plan` — the invariant
    does not depend on using the factory."""

    pool_initial: Decimal
    reserve_nominal: Decimal
    shares: Mapping[str, Decimal]
    compound: bool
    allocatable_initial: Decimal = field(default=_ZERO, compare=False)
    initial_sleeves: Mapping[str, Decimal] = field(default_factory=dict, compare=False)
    unallocated_initial: Decimal = field(default=_ZERO, compare=False)

    def __post_init__(self) -> None:
        if self.pool_initial <= _ZERO:
            raise InvalidCapitalPlanError(
                f"Shared pool P0 must be positive; got {self.pool_initial}."
            )
        if self.reserve_nominal < _ZERO:
            raise InvalidCapitalPlanError(
                f"Reserve R0 must be non-negative; got {self.reserve_nominal}."
            )
        negative = sorted(item for item, share in self.shares.items() if share < _ZERO)
        if negative:
            raise InvalidCapitalPlanError(f"Negative equity share for {negative}.")
        total = sum(self.shares.values(), _ZERO)
        if total > _HUNDRED:
            raise InvalidCapitalPlanError(
                f"Active equity shares total {total}%, which exceeds 100% (doc 13 §10.1)."
            )
        allocatable = max(_ZERO, self.pool_initial - self.reserve_nominal)
        sleeves = {item: allocatable * share / _HUNDRED for item, share in self.shares.items()}
        object.__setattr__(self, "shares", _frozen_decimals(self.shares))
        object.__setattr__(self, "allocatable_initial", allocatable)
        object.__setattr__(self, "initial_sleeves", _frozen_decimals(sleeves))
        object.__setattr__(self, "unallocated_initial", allocatable - sum(sleeves.values(), _ZERO))

    @property
    def item_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.shares))

    @property
    def compounding_mode(self) -> str:
        """The canonical token, for the decision trace and (at ADIM 20) the manifest."""
        return "COMPOUND_PORTFOLIO_EQUITY" if self.compound else "FIXED_INITIAL_PORTFOLIO_CAPITAL"

    def allocatable(self, equity: Decimal) -> Decimal:
        """``A(t) = max(0, E(t) - R0)`` — floored, because a pool cannot be negative."""
        return max(_ZERO, equity - self.reserve_nominal)

    def sleeve_capacity(self, equity: Decimal) -> Mapping[str, Decimal]:
        """``Ci(t)`` for every participating item, from ONE equity reading.

        Compound recomputes from ``A(t)``; fixed holds ``Ci_fixed = A0*wi/100`` — *"Ci_fixed
        zamanla degismez"* (Modül 11 §5.3). PnL, fees and funding are booked in BOTH modes;
        fixed only refuses to let them change the sizing base."""
        if not self.compound:
            return self.initial_sleeves
        allocatable = self.allocatable(equity)
        return _frozen_decimals(
            {item: allocatable * share / _HUNDRED for item, share in self.shares.items()}
        )


def build_sleeve_plan(
    *,
    pool_initial: Decimal,
    reserve_percent: Decimal,
    shares: Mapping[str, Decimal],
    compound: bool,
) -> SleevePlan:
    """Resolve ``P0``/``R0`` exactly as the shipped engine prologue does (``engine.py:838``).

    ``P0`` is quantized to the money step first and ``R0 = P0 * r / 100`` is left unquantized,
    so the ledger's ``A0``/``Ci0``/``U0`` are the same numbers ``allocation.rules._derive``
    previews to the user — doc 13 §13 and Modül 11 §5.1 both require preview and engine to
    agree exactly. A negative reserve percent is floored at 0 (it would otherwise inflate the
    pool above ``P0``); an over-100 one needs no upper clamp, since ``max(0, P0 - R0)`` drives
    the allocatable pool to 0."""
    p0 = _money(pool_initial)
    r0 = p0 * max(reserve_percent, _ZERO) / _HUNDRED
    return SleevePlan(pool_initial=p0, reserve_nominal=r0, shares=dict(shares), compound=compound)


@dataclass(frozen=True, slots=True)
class OpenPosition:
    """One item's open position as the LEDGER holds it — capital, not strategy state.

    Deliberately not ``state._Position``: that carries stop levels, trailing anchors, ladder
    cursors and lifecycle ids, none of which the pool needs and all of which stay item-local
    (ADR §5). ``notional`` is the entry-basis figure the engine already books
    (``_Position.entry_notional``, ``booking.py:219``) and is the ledger's definition of
    *committed capital* — see the module docstring on margin."""

    item_id: str
    direction: str
    size: Decimal
    entry_price: Decimal
    notional: Decimal = field(default=_ZERO, compare=False)

    def __post_init__(self) -> None:
        if self.direction not in ("long", "short"):
            raise PositionStateError(f"Unknown position direction {self.direction!r}.")
        if self.size <= _ZERO:
            raise PositionStateError(f"A held position must have a positive size; got {self.size}.")
        object.__setattr__(self, "notional", _money(self.entry_price * self.size))

    @property
    def sign(self) -> Decimal:
        return _ONE if self.direction == "long" else -_ONE

    @property
    def signed_notional(self) -> Decimal:
        return self.notional * self.sign

    def unrealized(self, mark: Decimal) -> Decimal:
        """Mark-to-market PnL at ``mark``. Reported beside ``E(t)``, never folded into it."""
        return _money((mark - self.entry_price) * self.size * self.sign)


@dataclass(frozen=True, slots=True)
class MarkPrice:
    """A price offered for marking one item's position, with where it came from.

    ``authority`` and ``staleness_ms`` are the clock's own facts (``ItemTickView``), carried
    so a valuation is auditable. They are RECORDED, not judged: whether a stale price may mark
    a position, and for how long, is **OD-2 and unanswered** (ADR §13). ``unavailable`` — and
    a non-positive price — mean the position cannot be marked at all, which is REPORTED rather
    than valued at zero."""

    price: Decimal
    authority: PriceAuthority
    staleness_ms: int | None = None

    @property
    def is_usable(self) -> bool:
        return self.authority != "unavailable" and self.price > _ZERO


@dataclass(frozen=True, slots=True)
class PortfolioEquityPoint:
    """One point on the portfolio's own equity curve.

    A distinct type from ``state.EquityPoint`` on purpose. That one is a per-ITEM record keyed
    by trade sequence, whose ``exposure`` is *the closed lot's* notional over the equity before
    the close (``booking.py:100``). This one is keyed by the merged axis and its exposure is
    the PORTFOLIO's held notional over ``E(t)``. Reusing the shipped type would have kept the
    field names while silently redefining what two of them mean."""

    seq: int
    t_ms: int | None
    equity: Decimal
    drawdown: Decimal
    gross_exposure_percent: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    """The marked view of the portfolio at one tick — reported, never fed back into ``E(t)``.

    ``gross_exposure`` / ``net_exposure`` are on the ENTRY basis (committed capital), which is
    what the caps and the solvency limit read. The ``marked_*`` figures are on the mark basis
    and are ``None`` whenever any open position could not be marked: a partial marked exposure
    would read as a smaller portfolio than the one actually held.

    ``net_exposure`` is a MEASUREMENT. Nothing in this module offsets a long against a short —
    no cap, no headroom and no solvency figure is computed from it. Netting semantics are
    undefined in canon (ADR §9.4, GH #544) and defining them here would ship ``NET`` by
    accident."""

    t_ms: int
    equity: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    gross_exposure_percent: Decimal
    unrealized_pnl: Decimal | None
    marked_gross_exposure: Decimal | None
    marked_net_exposure: Decimal | None
    unmarked_items: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CapacityDecision:
    """What one item is allowed to deploy at this valuation point, and why.

    ``limits`` carries every layer's headroom in money, whether or not it bound — a reviewer
    reading a capped fill needs to see the layer that bound it *and* the ones that did not.
    ``binding_constraint`` names the layer that actually reduced the request (``None`` when
    nothing did)."""

    item_id: str
    outcome: CapacityOutcome
    requested_units: Decimal
    granted_units: Decimal
    requested_notional: Decimal
    granted_notional: Decimal
    binding_constraint: str | None
    reason: str | None
    limits: Mapping[str, Decimal]
    policy_version: str = LEDGER_POLICY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "limits", _frozen_decimals(self.limits))

    @property
    def is_admitted(self) -> bool:
        return self.outcome != "rejected"


@dataclass(slots=True)
class ItemAttribution:
    """One item's contribution to the shared ledger (ADR §7 — writes are *tagged*).

    The pool is shared, so "which item earned this" is not recoverable from ``E(t)``; it is
    recorded as the booking happens or it is gone."""

    realized_pnl: Decimal = _ZERO
    fees: Decimal = _ZERO
    funding: Decimal = _ZERO
    other_costs: Decimal = _ZERO

    @property
    def net_contribution(self) -> Decimal:
        return self.realized_pnl - self.fees - self.funding - self.other_costs


# ----------------------------------------------------------------------------- the ledger


class PortfolioLedger:
    """ONE account book for the whole run (ADR §7, removal condition #2).

    Mutable and not frozen, exactly like ``_Ledger``: this is the accumulator the phase loop
    writes to. Determinism comes from the ordered writes (``(pin_ordinal, item_id)``, ADR
    §4.4), not from immutability."""

    __slots__ = (
        "_frozen_at",
        "_last_point_equity",
        "attribution",
        "equity",
        "equity_points",
        "fees",
        "funding",
        "other_costs",
        "peak",
        "plan",
        "positions",
        "realized_pnl",
    )

    def __init__(self, plan: SleevePlan) -> None:
        self.plan = plan
        # The book opens at the pool, and the curve opens with the corresponding
        # zero-drawdown seed — the same shape ``engine.py:846`` seeds a per-item ledger with.
        self.equity: Decimal = plan.pool_initial
        self.peak: Decimal = plan.pool_initial
        self.realized_pnl: Decimal = _ZERO
        self.fees: Decimal = _ZERO
        self.funding: Decimal = _ZERO
        self.other_costs: Decimal = _ZERO
        self.positions: dict[str, OpenPosition] = {}
        self.attribution: dict[str, ItemAttribution] = {
            item: ItemAttribution() for item in plan.shares
        }
        self.equity_points: list[PortfolioEquityPoint] = [
            PortfolioEquityPoint(
                seq=0,
                t_ms=None,
                equity=plan.pool_initial,
                drawdown=_money(_ZERO),
                gross_exposure_percent=_money(_ZERO),
            )
        ]
        self._last_point_equity: Decimal = plan.pool_initial
        self._frozen_at: int | None = None

    # ---------------------------------------------------------------- phase discipline

    @property
    def is_frozen(self) -> bool:
        """True between ``PV`` and ``P7`` — the window in which ``E(t)`` is published."""
        return self._frozen_at is not None

    def _assert_writable(self) -> None:
        if self._frozen_at is not None:
            raise LedgerFrozenError(
                f"The ledger is frozen at the t={self._frozen_at} valuation point; no writer "
                "may run between PV and P7 (ADR §8.1). Call begin_apply() first."
            )

    def _item(self, item_id: str) -> ItemAttribution:
        try:
            return self.attribution[item_id]
        except KeyError:
            raise UnknownLedgerItemError(
                f"Item '{item_id}' has no sleeve in this run's share plan."
            ) from None

    # ------------------------------------------------------------------------ accounting

    def _apply(self, raw_delta: Decimal) -> Decimal:
        """Move equity by ``raw_delta`` and return the delta ACTUALLY applied.

        The quantization is on the SUM, not on the delta — byte-identical to
        ``booking.py:96`` / ``engine.py:1953`` — and the applied delta is what the buckets
        record, which is what makes the accounting identity exact (module docstring)."""
        before = self.equity
        self.equity = (before + raw_delta).quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)
        self.peak = max(self.peak, self.equity)
        return self.equity - before

    def book_trade(
        self, item_id: str, *, gross_pnl: Decimal, commission: Decimal = _ZERO
    ) -> Decimal:
        """Book one realized lot: gross PnL and the round-trip commission it paid.

        The two are separate ledger lines (doc 13 §8.3 counts ``realized_pnl`` and ``fees``
        apart) but ONE equity write, because the shipped engine computes
        ``pnl = (gross - commission).quantize(0.01)`` and applies that single figure
        (``booking.py:94-96``). Splitting the write would round twice and could land a cent
        away from the per-item ledger this replaces.

        ``gross_pnl`` already carries spread and slippage: they are inside the effective fill
        prices it was computed from (``costs._effective_fill``). Passing them again as a cost
        would double-count every fill."""
        self._assert_writable()
        net = (gross_pnl - commission).quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)
        applied = self._apply(net)
        fee_part = commission.quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)
        attribution = self._item(item_id)
        attribution.realized_pnl += applied + fee_part
        attribution.fees += fee_part
        self.realized_pnl += applied + fee_part
        self.fees += fee_part
        return applied

    def book_fee(self, item_id: str, *, amount: Decimal) -> Decimal:
        """A standalone fee — the per-fill commission of a scale, stack or remainder lot
        (``booking.py:222``, ``engine.py:2909``/``:3095``). Positive means paid."""
        self._assert_writable()
        attribution = self._item(item_id)
        applied = self._apply(-amount)
        attribution.fees += -applied
        self.fees += -applied
        return applied

    def book_funding(self, item_id: str, *, amount: Decimal) -> Decimal:
        """A funding/carry charge against a held position (``engine.py:1953``).

        Signed the way the engine books it: POSITIVE means the position pays, negative means
        it receives (``costs.FundingCharge``)."""
        self._assert_writable()
        attribution = self._item(item_id)
        applied = self._apply(-amount)
        attribution.funding += -applied
        self.funding += -applied
        return applied

    def book_other_cost(self, item_id: str, *, amount: Decimal) -> Decimal:
        """``other_realized_costs`` of doc 13 §8.3 — a realized cost that is neither
        commission nor funding. Kept as its own line so the identity's fourth term is never
        silently folded into fees."""
        self._assert_writable()
        attribution = self._item(item_id)
        applied = self._apply(-amount)
        attribution.other_costs += -applied
        self.other_costs += -applied
        return applied

    @property
    def accounting_identity(self) -> Decimal:
        """``P0 + realized - fees - funding - other``. Equal to :attr:`equity`, always."""
        return (
            self.plan.pool_initial + self.realized_pnl - self.fees - self.funding - self.other_costs
        )

    # -------------------------------------------------------------------------- positions

    @property
    def gross_exposure(self) -> Decimal:
        """Total committed capital — the figure the caps and the solvency limit read."""
        return sum((pos.notional for pos in self.positions.values()), _ZERO)

    @property
    def net_exposure(self) -> Decimal:
        """Signed held notional. A MEASUREMENT — see :class:`PortfolioValuation`."""
        return sum((pos.signed_notional for pos in self.positions.values()), _ZERO)

    def deployed_notional(self) -> Mapping[str, Decimal]:
        """Every participating item's committed capital; ``0`` when flat.

        Every item, not just the open ones: a snapshot that omitted a flat item would not be a
        portfolio-wide valuation (``PortfolioSnapshot.__post_init__`` refuses it)."""
        return _frozen_decimals(
            {
                item: self.positions[item].notional if item in self.positions else _ZERO
                for item in self.plan.shares
            }
        )

    @property
    def available_capital(self) -> Decimal:
        """``max(0, A(t) - deployed)`` — what the pool can still commit without borrowing.

        Reserve is excluded because active items cannot use it (Modül 11 §5.1); the floor is
        what makes "no silent borrow" (doc 13 §14 test 12) structural. Under FIXED mode the
        sleeves stay at ``Ci_fixed`` while ``A(t)`` can fall below them, which is the one
        place genuine contention arises (ADR §9.1)."""
        return max(_ZERO, self.plan.allocatable(self.equity) - self.gross_exposure)

    def _assert_no_borrow(self, increase: Decimal) -> None:
        if increase > self.available_capital:
            raise LedgerSolvencyViolation(
                f"Deploying {increase} exceeds the {self.available_capital} the pool can "
                "still commit. Ask resolve_capacity() before deploying — the ledger never "
                "borrows the reserve or the unallocated cash (Modül 11 §5.1, §5.3)."
            )

    def set_position(
        self, item_id: str, *, direction: str, size: Decimal, entry_price: Decimal
    ) -> OpenPosition:
        """Open a position, or replace the held one with a new size/basis (scale, partial
        close, remainder absorb — the engine keeps ONE position per item, ``engine.py:1146``).

        Only the INCREASE in committed capital is checked against the pool. An existing
        position that has grown past its sleeve because equity fell is left exactly as it is:
        *"mevcut açik pozisyonlar equity değişti diye zorla rebalance edilmez"* (doc 13
        §8.3).

        A REVERSAL is refused. Flipping the direction in place would net the new notional
        against the old one and check only the difference, when a reversal actually releases
        one commitment and takes another — the engine models it as a close then an open
        (``positions_replaced``), and so must this. Close first."""
        self._assert_writable()
        self._item(item_id)
        candidate = OpenPosition(
            item_id=item_id, direction=direction, size=size, entry_price=entry_price
        )
        held = self.positions.get(item_id)
        if held is not None and held.direction != direction:
            raise PositionStateError(
                f"Item '{item_id}' holds a {held.direction} position; reversing to "
                f"{direction} in place would net two different commitments against each "
                "other. Close it first, as the engine's own replace path does."
            )
        increase = candidate.notional - (held.notional if held is not None else _ZERO)
        if increase > _ZERO:
            self._assert_no_borrow(increase)
        self.positions[item_id] = candidate
        return candidate

    def close_position(self, item_id: str) -> OpenPosition:
        """Release the item's committed capital. The realized PnL of the close is a SEPARATE
        booking (:meth:`book_trade`) — releasing capital and realizing a result are two
        different ledger facts and the engine emits them as two."""
        self._assert_writable()
        self._item(item_id)
        held = self.positions.pop(item_id, None)
        if held is None:
            raise PositionStateError(f"Item '{item_id}' holds no position to close.")
        return held

    # ------------------------------------------------------------------ valuation point

    def sleeve_capacity(self) -> Mapping[str, Decimal]:
        """``Ci(t)`` for every item, from the ledger's ONE current equity reading."""
        return self.plan.sleeve_capacity(self.equity)

    def publish_snapshot(self, t_ms: int) -> PortfolioSnapshot:
        """``PV`` — freeze the ledger and publish the one valuation of this tick.

        Every item at ``t`` is handed this exact value (ADR §7; doc 13 §8.3). The freeze holds
        until :meth:`begin_apply`, so no booking can move ``E(t)`` under an item that has
        already sized against it."""
        snapshot = build_snapshot(
            t_ms=t_ms,
            equity=self.equity,
            reserve_nominal=self.plan.reserve_nominal,
            sleeve_capacity=self.sleeve_capacity(),
            deployed_notional=self.deployed_notional(),
        )
        self._frozen_at = t_ms
        return snapshot

    def begin_apply(self, t_ms: int) -> None:
        """``P7`` — reopen the ledger for the writes this tick admitted."""
        if self._frozen_at is not None and self._frozen_at != t_ms:
            raise LedgerFrozenError(
                f"The ledger is frozen at t={self._frozen_at}; it cannot be reopened at "
                f"t={t_ms}. The apply phase belongs to the tick that published the snapshot."
            )
        self._frozen_at = None

    def valuation(
        self, t_ms: int, marks: Mapping[str, MarkPrice] | None = None
    ) -> PortfolioValuation:
        """Mark every open position at ONE valuation point and report the result.

        Pure: it writes nothing. ``E(t)`` is realized-only by canon, so an unrealized figure
        is reported *beside* it and never folded in (module docstring). A position with no
        usable mark makes ``unrealized_pnl`` and both ``marked_*`` figures ``None`` and lands
        in ``unmarked_items`` — an unmarkable position is never valued at zero."""
        offered = marks or {}
        unrealized = _ZERO
        marked_gross = _ZERO
        marked_net = _ZERO
        unmarked: list[str] = []
        for item_id in sorted(self.positions):
            position = self.positions[item_id]
            mark = offered.get(item_id)
            if mark is None or not mark.is_usable:
                unmarked.append(item_id)
                continue
            unrealized += position.unrealized(mark.price)
            value = _money(mark.price * position.size)
            marked_gross += value
            marked_net += value * position.sign
        complete = not unmarked
        gross = self.gross_exposure
        return PortfolioValuation(
            t_ms=t_ms,
            equity=self.equity,
            gross_exposure=gross,
            net_exposure=self.net_exposure,
            gross_exposure_percent=self._exposure_percent(gross),
            unrealized_pnl=unrealized if complete else None,
            marked_gross_exposure=marked_gross if complete else None,
            marked_net_exposure=marked_net if complete else None,
            unmarked_items=tuple(unmarked),
        )

    def _exposure_percent(self, gross: Decimal) -> Decimal:
        if self.equity <= _ZERO:
            return _money(_ZERO)
        return (gross / self.equity * _HUNDRED).quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)

    def commit_tick(self, t_ms: int) -> PortfolioEquityPoint | None:
        """``P9`` — append at most ONE equity point for this tick (ADR §7).

        A point is appended exactly when ``E(t)`` moved since the previous one. Canon fixes no
        cardinality (Modül 12 §10 asks only for *"Timestamped equity, drawdown, exposure..."*),
        and ``E(t)`` is realized-only, so a point at every tick would add flat repeats and no
        information. The curve is time-ordered BY CONSTRUCTION because the axis is
        (removal condition #5)."""
        self._assert_writable()
        if self.equity == self._last_point_equity:
            return None
        point = PortfolioEquityPoint(
            seq=len(self.equity_points),
            t_ms=t_ms,
            equity=self.equity,
            drawdown=_money(self.peak - self.equity),
            gross_exposure_percent=self._exposure_percent(self.gross_exposure),
        )
        self.equity_points.append(point)
        self._last_point_equity = self.equity
        return point

    # -------------------------------------------------------------------------- capacity

    def resolve_capacity(
        self,
        *,
        item_id: str,
        snapshot: PortfolioSnapshot,
        requested_units: Decimal,
        price: Decimal,
        max_position_notional: Decimal | None = None,
        max_total_exposure_notional: Decimal | None = None,
    ) -> CapacityDecision:
        """``P6b`` — ``allowed_size = min(desired, sleeve, item_risk_limits, solvency)``.

        The three CAP layers clamp (doc 13 §14 test 13 — *"deterministik cap/reject"*, and the
        shipped ``_cap_to_sleeve`` / exposure clamp both take a ``min``); the SOLVENCY layer
        may only reject, never trim, because Modül 11 §5.3 forbids a partial fill or a silent
        borrow. It is therefore evaluated LAST, against whatever the caps produced.

        ``snapshot`` is the tick's published valuation, so a decision is made against the same
        ``E(t)`` every sibling saw — not against a ledger that a sibling's fill has since
        moved. While the ledger is frozen the snapshot must be the one it published: the sleeve
        headroom is read from the snapshot and the solvency headroom from the ledger, and
        answering half the question from each of two valuation points is refused rather than
        averaged. Which of several jointly-insolvent intents is rejected is **OD-3**: this
        method answers one item's question, in the order the caller asks.

        ``requested_units`` is what the item wants to deploy NEWLY at this tick — the entry's
        size, or a scale layer's added size, never the resulting total. The solvency headroom
        already nets off everything the pool has committed, so passing a total would subtract
        the held position twice.

        ``max_position_notional`` bounds THIS order's notional. Its authority is Strategy
        Details (Modül 11 §6.1 layer 3), so a caller whose limit is position-level nets any
        held notional off it before passing it — the ledger applies the number it is given and
        infers nothing."""
        self._item(item_id)
        if self._frozen_at is not None and snapshot.t_ms != self._frozen_at:
            raise MismatchedSnapshotError(
                f"The ledger is frozen at t={self._frozen_at} but the snapshot was published "
                f"at t={snapshot.t_ms}."
            )
        sleeve_headroom = snapshot.remaining_sleeve_capacity(item_id)
        exposure_headroom = (
            max(_ZERO, max_total_exposure_notional - self.gross_exposure)
            if max_total_exposure_notional is not None
            else None
        )
        solvency_headroom = self.available_capital
        limits: dict[str, Decimal] = {
            SLEEVE_CONSTRAINT: sleeve_headroom,
            SOLVENCY_CONSTRAINT: solvency_headroom,
        }
        if max_position_notional is not None:
            limits[MAX_POSITION_CONSTRAINT] = max(_ZERO, max_position_notional)
        if exposure_headroom is not None:
            limits[EXPOSURE_CONSTRAINT] = exposure_headroom

        def decision(
            outcome: CapacityOutcome,
            granted: Decimal,
            *,
            binding: str | None = None,
            reason: str | None = None,
        ) -> CapacityDecision:
            return CapacityDecision(
                item_id=item_id,
                outcome=outcome,
                requested_units=requested_units,
                granted_units=granted,
                requested_notional=_money(requested_units * price)
                if price > _ZERO
                else _money(_ZERO),
                granted_notional=_money(granted * price) if price > _ZERO else _money(_ZERO),
                binding_constraint=binding,
                reason=reason,
                limits=limits,
            )

        if requested_units <= _ZERO:
            return decision("rejected", _ZERO, reason=NO_REQUESTED_SIZE)
        if price <= _ZERO:
            # A capacity in money cannot be converted to units without a price, and a
            # fabricated one would size a real order. Fail closed (``_cap_to_sleeve``'s own
            # non-positive-price branch returns 0 for the same reason).
            return decision("rejected", _ZERO, reason=UNPRICEABLE_CAPACITY)

        granted = requested_units
        binding: str | None = None
        for constraint, headroom, reason in (
            (SLEEVE_CONSTRAINT, sleeve_headroom, SLEEVE_ZERO_CAPACITY),
            (
                MAX_POSITION_CONSTRAINT,
                limits.get(MAX_POSITION_CONSTRAINT),
                MAX_POSITION_NOTIONAL_EXCEEDED,
            ),
            (EXPOSURE_CONSTRAINT, exposure_headroom, PORTFOLIO_MAX_TOTAL_EXPOSURE),
        ):
            if headroom is None:
                continue
            allowed = (
                (headroom / price).quantize(QTY_QUANTUM, rounding=MONEY_ROUNDING)
                if headroom > _ZERO
                else _ZERO
            )
            if allowed <= _ZERO:
                return decision("rejected", _ZERO, binding=constraint, reason=reason)
            if allowed < granted:
                granted = allowed
                binding = constraint
        granted_notional = _money(granted * price)
        if granted_notional > solvency_headroom:
            # Never a partial fill and never a borrow (Modül 11 §5.3): the whole order goes.
            return decision("rejected", _ZERO, binding=SOLVENCY_CONSTRAINT, reason=LEDGER_INSOLVENT)
        if binding is None:
            return decision("admitted", granted)
        return decision("capped", granted, binding=binding)


def ledger_for_items(
    *,
    pool_initial: Decimal,
    reserve_percent: Decimal,
    shares: Mapping[str, Decimal],
    compound: bool,
) -> PortfolioLedger:
    """The one-call constructor the phase loop (ADIM 18) will use."""
    return PortfolioLedger(
        build_sleeve_plan(
            pool_initial=pool_initial,
            reserve_percent=reserve_percent,
            shares=shares,
            compound=compound,
        )
    )


__all__ = [
    "CAPACITY_CONSTRAINTS",
    "EXPOSURE_CONSTRAINT",
    "LEDGER_INSOLVENT",
    "LEDGER_LAYER_REASONS",
    "LEDGER_POLICY_VERSION",
    "MAX_POSITION_CONSTRAINT",
    "MAX_POSITION_NOTIONAL_EXCEEDED",
    "MONEY_QUANTUM",
    "MONEY_ROUNDING",
    "NO_REQUESTED_SIZE",
    "PORTFOLIO_MAX_TOTAL_EXPOSURE",
    "QTY_QUANTUM",
    "SLEEVE_CONSTRAINT",
    "SLEEVE_ZERO_CAPACITY",
    "SOLVENCY_CONSTRAINT",
    "UNPRICEABLE_CAPACITY",
    "CapacityDecision",
    "CapacityOutcome",
    "InvalidCapitalPlanError",
    "ItemAttribution",
    "LedgerError",
    "LedgerFrozenError",
    "LedgerSolvencyViolation",
    "MarkPrice",
    "MismatchedSnapshotError",
    "OpenPosition",
    "PortfolioEquityPoint",
    "PortfolioLedger",
    "PortfolioValuation",
    "PositionStateError",
    "SleevePlan",
    "UnknownLedgerItemError",
    "build_sleeve_plan",
    "ledger_for_items",
]
