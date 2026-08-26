"""Trading costs and funding/carry (K-09 slice d).

Extracted from ``domain.backtest.engine``. Two kinds of thing live here:

* the per-fill cost model — ``_cost_params`` reads the pinned cost config and
  ``_effective_fill`` applies the adverse-side spread + slippage — both moved
  verbatim and already pure;
* the funding/carry DECISION — ``resolve_funding_decision_time`` and
  ``due_funding_charges`` answer "which pinned funding records fire at this bar,
  and what does each cost", with no reference to the bar loop's mutable state.

The split between deciding and applying is deliberate. Applying a charge mutates
``equity``/``peak``/the counters and emits a ``funding_charge`` decision event, so
that half stays in ``run_engine``; what moves is the part that was genuinely a
function of ``(records, index, decision_time, position)``. The observable behaviour
is identical — same records fire, in the same order, for the same amounts.

Two invariants this module owns, both load-bearing for K-02/K-03/F-11:

* the as-of comparison is NOT hand-rolled here — it delegates to
  ``research_data.time_policy.is_eligible_for_decision``, the single canonical
  rule-2 gate (instrument mapping AND ``available_at <= decision_time``), so every
  research value the engine consumes passes one audited predicate;
* an unresolvable bar timestamp FAILS CLOSED with ``FundingSourceInvalid``. Silently
  firing nothing would book an over-optimistic ZERO funding cost for the whole run.
  This deliberately differs from the date-blackout precedent, where a restrictive
  reading exists (treat the bar as inside the window) — a cost has no such reading.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from entropia.domain.backtest.execution.constants import _HUNDRED, _MONEY, _ONE, _ZERO
from entropia.domain.backtest.funding import FundingRecord, parse_utc
from entropia.domain.research_data.time_policy import is_eligible_for_decision
from entropia.shared.errors import FundingSourceInvalid

if TYPE_CHECKING:
    from entropia.domain.strategy.config import StrategyConfig


#: Basis points per unit: a ``bps`` commission of 1 is 0.01% of the fill notional.
_BPS_PER_UNIT = Decimal("10000")


@dataclass(frozen=True, slots=True)
class FillCosts:
    """The pinned per-fill cost triple, carried as one value instead of three parallel
    parameters (K-10b). Built once per run from ``_cost_params``; never recomputed, so
    every fill in a run is priced off the same pinned config."""

    half_spread: Decimal
    slippage: Decimal
    commission: Decimal
    #: Karar 1 (GH #552, signed 2026-08-25) — how ``commission`` is measured.
    #: Defaulted so every existing ``FillCosts(half_spread, slippage, commission)``
    #: construction keeps its exact meaning.
    commission_basis: str = "flat"

    def fee(self, notional: Decimal) -> Decimal:
        """The commission this ONE fill pays, given its own notional.

        The single derivation of the fee. Every charge site routes through it —
        ``booking`` (close, ``absorb_remainder``) and ``engine`` (entry, stacking,
        scale layer) — plus ``participant``, which MIRRORS the charged fee rather
        than charging one. Under ``bps`` each site owes a DIFFERENT amount, because
        each fill has a different notional. Inlining the arithmetic at any of them
        would create a second basis that drifts silently, which is the shape GH #552
        already had once: the fee scaled with the number of partial CLOSES rather
        than fills because one site computed its own.

        The sites are NAMED rather than counted on purpose: the previous wording
        said "six charge sites (three in ``booking``, three in ``engine``)" and
        ``booking`` has two, so the total counted the ``participant`` mirror as a
        charge. A hand-written count in prose has gone stale in this repo three
        times (layer counts, test collection, the hook-guard summary line); a name
        list goes stale only when a site is actually added or removed.

        ``flat`` ignores ``notional`` entirely and returns the configured amount —
        byte-identical to the pre-Karar-1 behaviour, which is what lets the default
        move no number. ``bps`` reads ``commission`` as basis points of the fill's
        notional (Master Ref Modul 4 §2.3). ``abs`` because a short's notional may
        arrive signed; a fee is never a rebate.
        """
        if self.commission <= _ZERO:
            return _ZERO
        if self.commission_basis == "bps":
            return (self.commission / _BPS_PER_UNIT * abs(notional)).quantize(_MONEY)
        return self.commission


@dataclass(frozen=True, slots=True)
class FundingCharge:
    """One funding record that fires at a bar, with the amount it costs the position.

    ``amount`` is signed the way the ledger books it: POSITIVE means the position
    pays (a long under a positive perp rate), negative means it receives (a short).
    """

    record: FundingRecord
    amount: Decimal


def resolve_funding_decision_time(timestamp: str) -> datetime:
    """The bar's decision time, or FAIL CLOSED (doc 12 §8.4 rule 2).

    With no resolvable decision time, available-time eligibility is unprovable; the
    engine refuses the run rather than book a zero funding cost it cannot justify.
    """
    resolved = parse_utc(timestamp, source_zone=None)
    if resolved is None:
        raise FundingSourceInvalid(
            "Funding is active but bar timestamp "
            f"'{timestamp}' cannot be resolved to a decision time; "
            "available-time eligibility is unprovable (doc 12 §8.4 rule 2).",
        )
    return resolved


def due_funding_charges(
    records: tuple[FundingRecord, ...],
    *,
    start_index: int,
    decision_time: datetime,
    has_instrument_mapping: bool,
    position_direction: str | None,
    position_notional: Decimal,
) -> tuple[int, list[FundingCharge]]:
    """A backward/as-of join: consume every record AVAILABLE at this bar, and cost the
    ones charged against a held position.

    Returns the advanced cursor plus the charges to apply, in record order. Records
    that become available while FLAT are consumed WITHOUT a charge (funding is paid
    only for the interval the position is actually held — the perp convention), which
    is why the cursor advances even when the returned list is empty. A record dated
    after the last replayed bar is simply never reached, so a future value cannot leak
    into the run by construction.

    ``position_direction`` is ``None`` when flat; a long pays a positive rate, a short
    receives it.
    """
    index = start_index
    charges: list[FundingCharge] = []
    while index < len(records) and is_eligible_for_decision(
        available_at=records[index].available_at,
        decision_time=decision_time,
        has_instrument_mapping=has_instrument_mapping,
    ):
        record = records[index]
        index += 1
        if position_direction is None:
            continue
        sign = _ONE if position_direction == "long" else -_ONE
        charges.append(
            FundingCharge(
                record=record,
                amount=(position_notional * record.rate * sign).quantize(_MONEY),
            )
        )
    return index, charges


def _cost_params(config: StrategyConfig) -> tuple[Decimal, Decimal, Decimal, str]:
    """(half_spread, slippage_fraction, commission_magnitude, commission_basis).

    The first three are non-negative. The magnitude is NOT a money amount on its own
    any more — ``commission_basis`` says what it measures (Karar 1)."""
    costs = config.data.costs
    spread = (costs.spread or _ZERO) / Decimal("2")
    slippage = (costs.slippage_value or _ZERO) / _HUNDRED
    commission = costs.commission or _ZERO
    return spread, slippage, commission, costs.commission_basis


def _effective_fill(
    price: Decimal, *, is_buy: bool, half_spread: Decimal, slip: Decimal
) -> Decimal:
    """Adverse-side fill: a buy pays up, a sell receives less (spread + slippage)."""
    adjusted = price + half_spread if is_buy else price - half_spread
    factor = Decimal("1") + slip if is_buy else Decimal("1") - slip
    return (adjusted * factor).quantize(_MONEY)
