"""Fixture construction and the ADR §8 phase driver for the unified-clock portfolio oracles.

This module builds INPUTS and SEQUENCES them. It computes no expected value: every number a
test asserts is either a literal hand-derived from canon, or a figure the shipped primitives
produced. Realized PnL is *stated* by the fixture (``exits={ts: "-3000.00"}``) rather than
re-derived here, so no arithmetic of the harness can stand in for arithmetic under test.

WHY A TEST-OWNED DRIVER (honest boundary — read this before trusting a green run)
--------------------------------------------------------------------------------
``docs/adr/0002-unified-clock-portfolio-simulation.md`` §12 places the per-tick phase loop in
a **new** ``run_portfolio(...)`` entry point (ADIM 18). That entry point **does not exist on
this commit**: ``grep -rn "def run_portfolio" backend/src`` returns nothing, and
``application/jobs/backtest_engine.py:298`` still loops over ITEMS and folds the finished runs
with ``execution.portfolio.combine_item_runs`` (``:363``). The six unified-clock modules are
imported only by each other — the six ``test_nothing_in_production_imports_*`` guards pin
exactly that.

So this driver sequences the shipped primitives through the phase order ADR §8.2 specifies. It
proves the PRIMITIVES satisfy the oracles below. It does **not** prove the shipped engine does,
because the shipped engine never calls them. When ADIM 18 lands, ``simulate`` should be
replaced by ``run_portfolio`` and these oracles re-run unchanged — that substitution is the
acceptance evidence ADR §14 asks for, and nothing here may be read as a substitute for it.

The phase order implemented (ADR §8.2), once per tick:

    P1 funding/fees -> P3 mandatory exits (formed by the SHIPPED former, before any
    snapshot exists) -> PV publish exactly one PortfolioSnapshot -> P4 discretionary
    intents against PV -> P5/P6b arbitrate -> P7 apply admitted orders -> P9 commit
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.execution.arbitration import (
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
from entropia.domain.backtest.execution.intents import (
    ClosingSize,
    ItemDecision,
    ItemIdentity,
    ItemIntent,
    PortfolioSnapshot,
    form_mandatory_intent,
)
from entropia.domain.backtest.execution.portfolio_ledger import (
    PortfolioEquityPoint,
    PortfolioLedger,
    ledger_for_items,
)

_ZERO = Decimal("0")


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


@dataclass(frozen=True, slots=True)
class TickRecord:
    """Everything one tick published, kept so an oracle can inspect the phase boundary."""

    t_ms: int
    timestamp: str
    views: tuple[ItemTickView, ...]
    snapshot: PortfolioSnapshot
    mandatory: tuple[ItemIntent, ...]
    intents: tuple[ItemIntent, ...]
    report: ArbitrationReport
    equity_point: PortfolioEquityPoint | None


@dataclass(frozen=True, slots=True)
class PortfolioRun:
    ledger: PortfolioLedger
    ticks: tuple[TickRecord, ...]

    @property
    def dated_points(self) -> tuple[PortfolioEquityPoint, ...]:
        """The curve without the ``t_ms=None`` seed the ledger opens the book with."""
        return tuple(p for p in self.ledger.equity_points if p.t_ms is not None)

    @property
    def instants(self) -> tuple[int, ...]:
        return tuple(p.t_ms for p in self.dated_points)

    @property
    def max_drawdown(self) -> Decimal:
        """The ledger's OWN per-point ``peak - equity``, maximised. Not recomputed here."""
        return max((p.drawdown for p in self.ledger.equity_points), default=_ZERO)

    def tick_at(self, timestamp: str) -> TickRecord:
        for record in self.ticks:
            if record.timestamp == timestamp:
                return record
        raise KeyError(f"no tick at {timestamp}")


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
    ``StrategyConfig`` per item; the shipped former is exercised end to end by
    ``test_backtest_cross_item_arbitration.py::test_it_arbitrates_what_form_intents_actually_produces``
    and by ``test_the_driver_arbitrates_what_the_shipped_former_produces`` in this package, so
    the shortcut cannot drift from the shape it stands in for."""
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
    """Run the ADR §8 phase loop over ``items`` and return every tick it published.

    ``items`` is the MANIFEST PIN ORDER — ``pin_ordinal`` is the index and is never supplied.
    ``caller_order`` permutes only the sequence the driver *visits* items in (the DOM/request
    order doc 13 §13 forbids from mattering); it never moves a pin. ``batch`` chunks each
    item's bars, so a test can prove chunking cannot move a number."""
    order = list(caller_order) if caller_order is not None else list(range(len(items)))
    ledger = ledger_for_items(
        pool_initial=Decimal(pool),
        reserve_percent=Decimal(reserve_percent),
        shares={item.item_id: Decimal(item.share) for item in items},
        compound=compound,
    )
    profiles: Mapping[str, ItemArbitrationProfile] = profiles_from_pins(
        [(item.item_id, item.instrument_id) for item in items]
    )
    identities = {item.item_id: item.identity(i) for i, item in enumerate(items)}
    caps = (
        {k: Decimal(v) for k, v in max_position_notional.items()} if max_position_notional else None
    )
    exposure_cap = (
        Decimal(max_total_exposure_notional) if max_total_exposure_notional is not None else None
    )
    streams = [items[i].stream(i, batch=batch) for i in order]

    records: list[TickRecord] = []
    for tick in iter_ticks(streams):
        records.append(
            _run_tick(
                tick,
                items=items,
                order=order,
                ledger=ledger,
                identities=identities,
                profiles=profiles,
                policy=policy,
                caps=caps,
                exposure_cap=exposure_cap,
            )
        )
    return PortfolioRun(ledger=ledger, ticks=tuple(records))


def _run_tick(
    tick: ClockTick,
    *,
    items: Sequence[ScriptedItem],
    order: Sequence[int],
    ledger: PortfolioLedger,
    identities: Mapping[str, ItemIdentity],
    profiles: Mapping[str, ItemArbitrationProfile],
    policy: str | None,
    caps: Mapping[str, Decimal] | None,
    exposure_cap: Decimal | None,
) -> TickRecord:
    """One full cycle of ADR §8.1. Split out so the phase boundaries stay readable."""
    visiting = [items[i] for i in order]
    stamp = ""

    # --- P1 -- funding and standalone fees on held positions (ledger writes, no discretion).
    for item in visiting:
        view = tick.view_for(item.item_id)
        if view is None or not view.is_decision:
            continue
        ts = view.bars[-1].timestamp
        stamp = stamp or ts
        if ts in item.funding:
            ledger.book_funding(item.item_id, amount=Decimal(item.funding[ts]))
        if ts in item.fees:
            ledger.book_fee(item.item_id, amount=Decimal(item.fees[ts]))

    # --- P3 -- mandatory exits, formed by the SHIPPED former BEFORE E(t) exists.
    mandatory: list[ItemIntent] = []
    for item in visiting:
        view = tick.view_for(item.item_id)
        if view is None or not view.is_decision:
            continue
        ts = view.bars[-1].timestamp
        held = ledger.positions.get(item.item_id)
        if ts not in item.exits or held is None:
            continue
        mandatory.append(
            form_mandatory_intent(
                identity=identities[item.item_id],
                view=view,
                decision=ItemDecision(kind="exit", direction=held.direction, reason="stop_loss"),
                sizing=ClosingSize(units=held.size),
            )
        )
        ledger.close_position(item.item_id)
        ledger.book_trade(
            item.item_id,
            gross_pnl=Decimal(item.exits[ts]),
            commission=Decimal(item.commissions.get(ts, "0")),
        )

    # --- PV -- exactly one valuation, and the ledger freezes until P7.
    snapshot = ledger.publish_snapshot(tick.t_ms)

    # --- P4 -- discretionary intents, every one of them against THAT snapshot.
    intents: list[ItemIntent] = []
    prices: dict[str, Decimal] = {}
    for item in visiting:
        view = tick.view_for(item.item_id)
        if view is None or not view.is_decision:
            continue
        ts = view.bars[-1].timestamp
        if ts not in item.entries or item.item_id in ledger.positions:
            continue
        direction, units = item.entries[ts]
        price = view.bars[-1].close
        prices[item.item_id] = price
        intents.append(
            _p4_intent(
                identity=identities[item.item_id],
                snapshot=snapshot,
                direction=direction,
                units=Decimal(units),
                price=price,
            )
        )

    # --- P5 / P6b -- conflict then capacity, against the frozen ledger.
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=intents,
        profiles=profiles,
        policy=policy,
        max_position_notional=caps,
        max_total_exposure_notional=exposure_cap,
    )

    # --- P7 -- apply what was admitted, in pinned order. --- P9 -- one equity point.
    ledger.begin_apply(tick.t_ms)
    for decision in report.decisions:
        if decision.is_admitted and decision.granted_units > _ZERO and decision.direction:
            ledger.set_position(
                decision.item_id,
                direction=decision.direction,
                size=decision.granted_units,
                entry_price=prices[decision.item_id],
            )
    point = ledger.commit_tick(tick.t_ms)
    return TickRecord(
        t_ms=tick.t_ms,
        timestamp=stamp,
        views=tick.views,
        snapshot=snapshot,
        mandatory=tuple(mandatory),
        intents=tuple(intents),
        report=report,
        equity_point=point,
    )
