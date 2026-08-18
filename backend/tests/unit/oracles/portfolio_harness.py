"""Fixtures for the unified-clock portfolio oracles, driven through the SHIPPED phase loop.

This module builds INPUTS. It computes no expected value: every number a test asserts is
either a literal hand-derived from canon, or a figure the shipped primitives produced.
Realized PnL is *stated* by the fixture (``exits={ts: "-3000.00"}``) rather than re-derived
here, so no arithmetic of the harness can stand in for arithmetic under test.

WHAT MOVED AT ADIM 18, AND WHAT DID NOT (read this before trusting a green run)
------------------------------------------------------------------------------
The per-tick phase loop is no longer test-owned. ``simulate`` is now a thin adapter that
turns each :class:`ScriptedItem` into an :class:`~entropia.domain.backtest.portfolio_engine.
ItemParticipant` and hands it to the production entry point
``domain/backtest/portfolio_engine.py::run_portfolio``. The ADR §8.2 order — P1 funding/fee
-> P3 mandatory exits -> PV one snapshot -> P4 intents -> P5/P6b arbitrate -> P7 apply ->
P9 commit — is executed by that module, not by this one, and the oracles below were carried
over UNCHANGED across the substitution. That substitution is the acceptance evidence ADR §14
asks for, and it is what moved A1/A3/A5 off a test-owned driver.

What is still test-owned, and must stay disclosed: the DECISIONS. A ``ScriptedItem`` states
what it wants (``entries``), what it is forced to close (``exits``) and what it is charged
(``funding``/``fees``) as fixture data, where a real item would derive them from its own
indicator evaluators, stop resolver and pinned funding schedule. That is the participant
contract working as designed — ``execution.intents`` states that the decision is an INPUT —
but it means these oracles prove the LOOP and the primitives, not any particular item's
signal logic, which the engine's own suites cover.

The remaining boundary is the worker: ``application/jobs/backtest_engine.py`` still loops
over items and folds them with ``combine_item_runs``. Wiring it needs a participant backed
by the real engine (ADR §12's skipped ADIM 16 stepper), so ``SHARED_ALLOCATION_STATUS``
stays ``future_dev``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.execution.arbitration import ArbitrationDecision
from entropia.domain.backtest.execution.clock import ItemBarStream, ItemTickView
from entropia.domain.backtest.execution.intents import (
    ClosingSize,
    ItemDecision,
    ItemIdentity,
    ItemIntent,
    PortfolioSnapshot,
)
from entropia.domain.backtest.execution.portfolio_ledger import OpenPosition
from entropia.domain.backtest.portfolio_engine import (
    CarryCharges,
    MandatoryExit,
    PortfolioRun,
    PortfolioTick,
    run_portfolio,
)

_ZERO = Decimal("0")

__all__ = ["PortfolioRun", "PortfolioTick", "ScriptedItem", "row", "simulate"]


def row(timestamp: str, close: str) -> dict[str, Any]:
    """One OHLCV row in the shape ``state._normalize`` accepts.

    Flat OHLC at ``close``: these fixtures test capital sequencing, not fill geometry, and a
    row missing a price is DROPPED by the normalizer rather than raising."""
    return {
        "timestamp": timestamp,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": "1",
    }


@dataclass(slots=True)
class ScriptedItem:
    """One composition item: its pinned identity, its bar axis and its scripted decisions.

    ``entries``/``exits``/``funding``/``fees`` are keyed by the ISO timestamp of the tick they
    act on, so a fixture reads as a wall-clock story and two items' scripts can be compared by
    eye. An entry fires only when the item is FLAT; an exit only when it holds a position.
    """

    item_id: str
    share: str
    bars: Sequence[tuple[str, str]]
    instrument_id: str | None = "BTCUSDT"
    #: ``ts -> (direction, units)`` — what the item WANTS, pre-cap.
    entries: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    #: ``ts -> gross realized PnL`` booked when the mandatory exit closes the position.
    exits: Mapping[str, str] = field(default_factory=dict)
    #: ``ts -> commission paid on that exit's round trip``.
    commissions: Mapping[str, str] = field(default_factory=dict)
    #: ``ts -> funding paid (positive) or received (negative)``.
    funding: Mapping[str, str] = field(default_factory=dict)
    #: ``ts -> standalone fee paid``.
    fees: Mapping[str, str] = field(default_factory=dict)
    item_kind: str = "strategy"

    def stream(self, pin_ordinal: int, *, batch: int = 0) -> ItemBarStream:
        rows = [row(ts, close) for ts, close in self.bars]
        batches = [rows[i : i + batch] for i in range(0, len(rows), batch)] if batch else [rows]
        return ItemBarStream(item_id=self.item_id, pin_ordinal=pin_ordinal, batches=batches)

    def identity(self, pin_ordinal: int) -> ItemIdentity:
        return ItemIdentity(
            item_id=self.item_id,
            item_kind=self.item_kind,
            pin_ordinal=pin_ordinal,
            root_id=f"root_{self.item_id}",
            selected_revision_id=f"rev_{self.item_id}",
        )


def _p4_intent(
    *,
    identity: ItemIdentity,
    snapshot: PortfolioSnapshot,
    direction: str,
    units: Decimal,
    price: Decimal,
) -> ItemIntent:
    """A P4 entry intent in the exact shape ``form_intent`` builds one.

    Constructed directly so a portfolio fixture does not have to carry a whole
    ``StrategyConfig`` per item — ``form_intent`` sizes an entry through the real chain and
    would overwrite the literal unit counts these oracles assert. The shipped former is
    exercised end to end by
    ``test_backtest_cross_item_arbitration.py::test_it_arbitrates_what_form_intents_actually_produces``
    and by ``test_the_driver_arbitrates_what_the_shipped_former_actually_produces`` in this
    package, so the shortcut cannot drift from the shape it stands in for."""
    return ItemIntent(
        identity=identity,
        t_ms=snapshot.t_ms,
        phase="P4",
        kind="entry",
        direction=direction,
        desired_size=units,
        reference_price=price,
        effective_price=price,
        price_authority="fresh_bar_close",
        reason="entry_signal",
        contract_version="item-intent-v1",
        evidence={},
        dependencies={
            "snapshot_identity": snapshot.identity,
            "snapshot_t_ms": snapshot.t_ms,
        },
        diagnostics={"pin_ordinal": identity.pin_ordinal},
    )


@dataclass(frozen=True, slots=True)
class _ScriptedParticipant:
    """One ``ScriptedItem`` behind the production loop's participant contract.

    Every hook reads the item's script at the timestamp of the bar it was handed, so the
    fixture stays a wall-clock story and this class stays a lookup — it decides nothing the
    fixture did not already state."""

    item: ScriptedItem
    identity: ItemIdentity
    stream: ItemBarStream

    @property
    def instrument_id(self) -> str | None:
        return self.item.instrument_id

    def carry(self, view: ItemTickView) -> CarryCharges | None:
        stamp = view.bars[-1].timestamp
        funding = Decimal(self.item.funding.get(stamp, "0"))
        fee = Decimal(self.item.fees.get(stamp, "0"))
        if funding == _ZERO and fee == _ZERO:
            return None
        return CarryCharges(funding=funding, fee=fee)

    def mandatory_exit(self, view: ItemTickView, *, held: OpenPosition) -> MandatoryExit | None:
        stamp = view.bars[-1].timestamp
        if stamp not in self.item.exits:
            return None
        return MandatoryExit(
            decision=ItemDecision(kind="exit", direction=held.direction, reason="stop_loss"),
            sizing=ClosingSize(units=held.size),
            gross_pnl=Decimal(self.item.exits[stamp]),
            commission=Decimal(self.item.commissions.get(stamp, "0")),
        )

    def entry(
        self,
        view: ItemTickView,
        snapshot: PortfolioSnapshot,
        *,
        held: OpenPosition | None,
    ) -> ItemIntent | None:
        stamp = view.bars[-1].timestamp
        if held is not None or stamp not in self.item.entries:
            return None
        direction, units = self.item.entries[stamp]
        return _p4_intent(
            identity=self.identity,
            snapshot=snapshot,
            direction=direction,
            units=Decimal(units),
            price=view.bars[-1].close,
        )

    def settle(self, view: ItemTickView, *, admitted: ArbitrationDecision) -> None:
        """P7 — the scripted item keeps no book of its own, so there is nothing to mirror.

        A deliberate no-op, not an oversight: the fixture's story is told entirely through the
        SHARED ledger, and an item-local echo of the grant would be a second copy of a number
        the pool already owns. Present because the Protocol requires it (ADR §6 clause 6) — the
        point of requiring it is that forgetting it is a type error, not a silent flat run."""

    def finalize(self, view: ItemTickView) -> MandatoryExit | None:
        """P10 — scripted fixtures state their exits explicitly, so none is forced at the end.

        Returning ``None`` is what keeps every portfolio oracle byte-identical across this
        slice: P10 books nothing, so no equity point moves and no digest shifts."""
        return None


def simulate(
    items: Sequence[ScriptedItem],
    *,
    pool: str = "10000",
    reserve_percent: str = "0",
    compound: bool = True,
    policy: str | None = None,
    max_total_exposure_notional: str | None = None,
    max_position_notional: Mapping[str, str] | None = None,
    caller_order: Sequence[int] | None = None,
    batch: int = 0,
) -> PortfolioRun:
    """Run ``items`` through the shipped ``run_portfolio`` loop and return every tick.

    ``items`` is the MANIFEST PIN ORDER — ``pin_ordinal`` is the index and is never supplied.
    ``caller_order`` permutes only the sequence participants are HANDED to the engine in (the
    DOM/request order doc 13 §13 forbids from mattering); it never moves a pin, and the engine
    re-sorts to ``(pin_ordinal, item_id)`` before reading anything. ``batch`` chunks each
    item's bars, so a test can prove chunking cannot move a number."""
    order = list(caller_order) if caller_order is not None else list(range(len(items)))
    participants = [
        _ScriptedParticipant(
            item=items[i],
            identity=items[i].identity(i),
            stream=items[i].stream(i, batch=batch),
        )
        for i in order
    ]
    return run_portfolio(
        participants,
        pool_initial=Decimal(pool),
        shares={item.item_id: Decimal(item.share) for item in items},
        reserve_percent=Decimal(reserve_percent),
        compound=compound,
        conflict_policy=policy,
        max_position_notional=(
            {k: Decimal(v) for k, v in max_position_notional.items()}
            if max_position_notional
            else None
        ),
        max_total_exposure_notional=(
            Decimal(max_total_exposure_notional)
            if max_total_exposure_notional is not None
            else None
        ),
    )
