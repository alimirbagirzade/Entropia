"""Projecting a finished portfolio co-simulation into ONE composite ``EngineOutput``.

ADR 0002 §12 stops one step short of the Result. The phase loop returns a
``PortfolioRun`` — one shared ledger plus every tick it walked — while the worker's Result
assembly speaks ``EngineOutput``. Nothing bridged the two, which is why ADR §14's **A4**
(*"permuting the items yields an identical EngineOutput digest"*) and **A18**
(*"chunking each item's bars differently yields an identical digest"*) could not be
evaluated at all: there was no ``EngineOutput`` on that path to digest. This module is
that bridge and only that — it reads a finished run and states what it found. It computes
no fill, sizes nothing, and re-derives no amount the ledger already applied.

Why ONE portfolio-level output instead of N item-level ones
-----------------------------------------------------------
The obvious shape — project the run back into per-item ``EngineOutput``s and keep folding
them with ``execution.portfolio.combine_item_runs`` — is wrong twice over, and both
reasons are canon rather than taste.

*It would un-order the curve.* ``combine_item_runs`` builds the composite curve by
CONCATENATING each item's realized progression in pin order; that is exactly the defect it
discloses as ``portfolio_curve_sequential_not_unified_clock``, and exactly what ADR §14 A5
(*time-ordered by construction*) exists to remove. The ledger's curve already is
time-ordered — feeding it through the sequential fold would take an ordered series and
re-derive an unordered one.

*There is no per-item equity to split.* ADR §7: the pool is shared and *"a sleeve is a
cap, not a wallet"* — capital is not physically partitioned. Splitting ``E(t)`` into N
per-item curves would be an allocation-attribution MODEL that canon does not define. What
the ledger genuinely records per item is ``ItemAttribution`` (realized PnL, fees, funding,
other realized costs) — a net contribution, not a curve and not a drawdown basis. This
module publishes that and refuses to invent the rest.

So on the shared path this projection **replaces** ``combine_item_runs`` rather than
feeding it. Neither calls the other, the sequential fold is untouched, its four
``portfolio.combine*`` golden digests cannot move because this file exists, and this
module has no production caller at all — the containment ADR §12 describes is intact.

What is deliberately ABSENT, and why (fail-closed, never zero-filled)
----------------------------------------------------------------------
Each of these is a number the phase loop does not have. Emitting ``0`` would read as
*"measured zero"*, and emitting a derived value would be a second implementation of a rule
that lives elsewhere. They are omitted and NAMED in ``diagnostics["warnings"]``:

* **Item-local engine counters** — ``bars_processed``, ``indicator_blocks``, … the
  ``_DIAG_SUM_KEYS`` set ``combine_item_runs`` sums out of per-item diagnostics. The phase
  loop never sees a bar body, so it counts none of them.
* **The filter-veto journal.** ``filtered_events`` is item-local by construction
  (``execution.state.FILTERED_EVENT_TYPES``); no filter veto ever reaches a participant
  hook. The journal is empty because none happened *here*, not because none happened.
* **``position_intervals``.** Its ``peak_notional`` is tracked across a held window by the
  per-item engine; the shared ledger books entry-basis notional only.
* **The Contribution block.** ``combine_item_runs`` computes leave-one-out marginals by
  re-folding the remaining items' finished outputs, and states why that is sound: *"each
  item's simulation is independent of the others"*. Under a shared pool it is **not** —
  removing an item changes every sibling's ``Ci(t)`` and therefore its fills. The marginal
  analysis needs a re-SIMULATION, so it is refused rather than approximated.

One redefinition is declared rather than hidden: ``EquityPoint.exposure`` on a per-item
curve is *the closed lot's* notional over the equity before the close
(``booking.py:100``), while here it is the PORTFOLIO's gross exposure over ``E(t)`` —
which is what ``PortfolioEquityPoint.gross_exposure_percent`` means. The artifact's field
name is the shipped one, so the change of basis is published as a warning instead of being
carried silently under a familiar label.

``diagnostics["policy_versions"]`` records the two versions that decide the SHAPE of this
output — the projection's own and the loop's — and stops there. It is deliberately **not**
the ADR §10.3 manifest block: ``clock_policy_version``, ``arbitration_policy_version`` and
their neighbours belong to ADIM 20 and are built by ``build_portfolio_manifest`` in
``execution/provenance.py``, which nothing calls. (Spelled as a path rather than a dotted
import on purpose — that module's containment guard is a text scan, and a docstring mention
would read to it as a production importer.) Reading them here
would also have made this module an importer of three separately contained modules — each
pinned by an exact-list guard — to publish a field no consumer reads yet. The narrower
import surface is the point: the only unified-clock module this projection reaches is
``execution.intents``, and only for the intent type it reads out of a finished run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    EngineOutput,
    EquityPoint,
    SignalEventRow,
    TradeRow,
)
from entropia.domain.backtest.execution.arbitration import resolve_policy
from entropia.domain.backtest.execution.constants import (
    _HUNDRED,
    _MONEY,
    _PCT,
    _RATIO,
    _ZERO,
)
from entropia.domain.backtest.execution.intents import ItemIdentity, ItemIntent
from entropia.domain.backtest.execution.provenance import (
    AllocationProvenance,
    SleeveProvenance,
    build_portfolio_manifest,
    money_str,
)
from entropia.domain.backtest.portfolio_engine import (
    PORTFOLIO_LOOP_VERSION,
    PortfolioRun,
    PortfolioTick,
)

PORTFOLIO_PROJECTION_VERSION = "portfolio-projection-v1"
"""Pins the SHAPE this projection publishes, exactly as ``PORTFOLIO_LOOP_VERSION`` pins the
phase order. Changing which fields are stated — or the basis any of them is stated on —
changes this string."""

ENGINE_KIND = "v1_unified_clock_portfolio"
"""Distinct from ``combine_item_runs``' ``v1_bar_replay_composition``: a reader must be able
to tell a unified-clock Result from a sequentially folded one without inspecting the curve."""

ITEM_LOCAL_COUNTERS_ABSENT = "portfolio_projection_item_local_engine_counters_absent"
FILTER_JOURNAL_IS_ITEM_LOCAL = "portfolio_projection_filter_veto_journal_is_item_local"
POSITION_INTERVALS_ABSENT = "portfolio_projection_position_intervals_absent"
CONTRIBUTION_NEEDS_RESIMULATION = "portfolio_projection_contribution_requires_resimulation"
EXPOSURE_BASIS_IS_PORTFOLIO = "portfolio_projection_equity_exposure_is_portfolio_gross_percent"

ABSENT_BY_CONSTRUCTION: tuple[str, ...] = (
    ITEM_LOCAL_COUNTERS_ABSENT,
    FILTER_JOURNAL_IS_ITEM_LOCAL,
    POSITION_INTERVALS_ABSENT,
    CONTRIBUTION_NEEDS_RESIMULATION,
    EXPOSURE_BASIS_IS_PORTFOLIO,
)
"""Every boundary this projection declares, as one list, so a caller can assert the whole
disclosure set rather than a string it happened to remember. Emitted verbatim into
``diagnostics["warnings"]``."""

PER_ITEM_BASIS = (
    "Per-item figures are the shared ledger's own attribution (realized PnL, fees, funding "
    "and other realized costs, tagged as each booking happened) — NOT a standalone bar-replay "
    "of the item. A shared pool is not partitioned into per-item capital, so an item has no "
    "initial capital, no equity curve and no drawdown basis of its own, and none is stated. "
    "Trade counts are the item's own closed lots on the merged axis; the composite trade "
    "sequence interleaves items by time, so no item owns a contiguous seq range."
)

NON_EXECUTING_NOTE = "non_executing_participating_object"
"""The token ``combine_item_runs`` already uses for a pinned-but-not-simulated object; reused
verbatim so a reader does not have to learn a second spelling of the same fact."""


class PortfolioProjectionError(ValueError):
    """Base for every fail-closed refusal this projection raises."""


class UnpinnedItemError(PortfolioProjectionError):
    """An item traded in the run but the caller supplied no pinned record for it. Projecting
    it anyway would put an unnamed, unattributable row into an immutable Result."""


class MissingPinOrdinalError(PortfolioProjectionError):
    """An executing item reached the provenance builder with no pin ordinal. The manifest
    states a PIN; inferring one from list position would record an order nobody assigned."""


class UnpairedCloseError(PortfolioProjectionError):
    """A booked close with no open recorded before it. A trade row built across that gap
    would carry a fabricated entry time and entry price."""


class UnpricedIntentError(PortfolioProjectionError):
    """An intent that opened or closed a position carries neither an effective nor a
    reference price. A trade row needs a real fill price; there is none to state."""


@dataclass(frozen=True, slots=True)
class PinnedItem:
    """The per-item metadata a run cannot derive from itself, as PINNED in the manifest.

    The phase loop knows ``item_id`` and nothing else about an item's identity: labels,
    revisions and the market it trades live with the worker's immutable snapshot. F-07 §4.4
    forbids re-labelling a Result from the live composition, so these travel in rather than
    being joined at read time — the same contract ``ItemRun`` carries for the sequential fold.
    """

    item_id: str
    item_kind: str
    root_id: str | None = None
    revision_id: str | None = None
    item_label: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    pin_ordinal: int | None = None
    """The item's index in the manifest's deterministic pin order, when the caller knows it.

    Optional because the OUTPUT projection never reads it — executing rows follow the
    ledger's own order, which the loop already sorted by ``(pin_ordinal, item_id)``, so a
    row cannot move whether this is set or not (ADR §14 A4). It is carried here because
    :func:`build_portfolio_provenance` needs the ordinal to state a pin, and the alternative
    was a second per-item record travelling the same seam with one extra field.

    ``None`` means the caller did not pin an order; the provenance builder refuses to guess
    one from list position, because a positional ordinal that merely LOOKS right would enter
    an immutable manifest as a pin nobody assigned."""


@dataclass(frozen=True, slots=True)
class _OpenLot:
    """What an admitted entry committed, held until the close that pairs with it."""

    entry_time: str
    entry_price: Decimal
    direction: str


def _intent_price(intent: ItemIntent) -> Decimal:
    """The price an intent actually names — effective if it has one, else the reference.

    Same reading as ``portfolio_engine``'s admission path applies before it opens a position,
    so a trade row's entry price is the price the ledger booked against, never a second
    opinion about what the fill was."""
    price = intent.effective_price if intent.effective_price is not None else intent.reference_price
    if price is None:
        raise UnpricedIntentError(
            f"Item '{intent.item_id}' {intent.phase} intent at t_ms={intent.t_ms} carries no "
            "price; a trade row cannot state a fill that was never priced."
        )
    return price


def _close_lots(
    tick: PortfolioTick,
    open_lots: dict[str, _OpenLot],
    trades: list[tuple[str, TradeRow]],
) -> None:
    """P3's booked closes, as trade rows. Runs before this tick's opens, as the loop does."""
    exits = {intent.item_id: intent for intent in tick.mandatory}
    for close in tick.closes:
        lot = open_lots.pop(close.item_id, None)
        if lot is None:
            raise UnpairedCloseError(
                f"Item '{close.item_id}' booked a close at t_ms={tick.t_ms} with no open "
                "position recorded before it."
            )
        intent = exits[close.item_id]
        trades.append(
            (
                close.item_id,
                TradeRow(
                    seq=len(trades) + 1,
                    entry_time=lot.entry_time,
                    exit_time=tick.timestamp,
                    direction=lot.direction,
                    entry_price=lot.entry_price,
                    exit_price=_intent_price(intent),
                    # The figure ``PortfolioLedger.book_trade`` ACTUALLY applied to E(t),
                    # not ``gross - commission`` recomputed here: the ledger quantizes the
                    # sum once, and a second implementation of that could land a cent away.
                    pnl=close.net_pnl,
                    exit_reason=intent.reason,
                ),
            )
        )


def _open_lots(tick: PortfolioTick, open_lots: dict[str, _OpenLot]) -> None:
    """P7's admissions, remembered until they close. Same predicate the apply phase uses."""
    formed = {intent.item_id: intent for intent in tick.intents}
    for decision in tick.report.decisions:
        if not decision.is_admitted or decision.granted_units <= _ZERO or not decision.direction:
            continue
        open_lots[decision.item_id] = _OpenLot(
            entry_time=tick.timestamp,
            entry_price=_intent_price(formed[decision.item_id]),
            direction=decision.direction,
        )


def _walk_trades(run: PortfolioRun) -> list[tuple[str, TradeRow]]:
    """Every closed lot in merged-axis order, each tagged with the item that closed it.

    The tag is what makes per-item trade counts possible at all: ``TradeRow`` carries no
    item, and on a shared pool the composite sequence interleaves items by time rather than
    grouping them, so it cannot be recovered from a seq range afterwards."""
    open_lots: dict[str, _OpenLot] = {}
    trades: list[tuple[str, TradeRow]] = []
    for tick in run.ticks:
        _close_lots(tick, open_lots, trades)
        _open_lots(tick, open_lots)
    return trades


def _equity_points(run: PortfolioRun) -> list[EquityPoint]:
    """The ledger's own curve, time-ordered BY CONSTRUCTION (ADR §14 A5) — never re-folded.

    ``t_ms`` is resolved back to the tick's wall-clock stamp because the artifact is keyed by
    timestamp; the ``t_ms=None`` seed keeps the empty stamp ``combine_item_runs`` also uses."""
    stamps = {tick.t_ms: tick.timestamp for tick in run.ticks}
    return [
        EquityPoint(
            seq=point.seq,
            timestamp="" if point.t_ms is None else stamps[point.t_ms],
            equity=point.equity,
            drawdown=point.drawdown,
            # Basis change, declared in ``warnings``: portfolio gross exposure over E(t).
            exposure=point.gross_exposure_percent,
        )
        for point in run.ledger.equity_points
    ]


def _opt_str(value: Any) -> str | None:
    """``None`` stays ``None``; everything else is spelled as text.

    Mirrors ``provenance._opt_str`` deliberately: an ABSENT pin must reach the manifest as
    ``null`` rather than as the string ``"None"``, which would read as a value."""
    return None if value is None else str(value)


def _event_detail(
    intent: ItemIntent, tick: PortfolioTick, pinned: Mapping[str, PinnedItem]
) -> dict[str, Any]:
    """One decision-trace row's payload: what the item stated, and what the pool answered."""
    record = pinned[intent.item_id]
    detail: dict[str, Any] = {
        "phase": intent.phase,
        "reason": intent.reason,
        "t_ms": intent.t_ms,
        "desired_size": intent.desired_size,
        "reference_price": intent.reference_price,
        "effective_price": intent.effective_price,
        "price_authority": intent.price_authority,
        "contract_version": intent.contract_version,
        "evidence": dict(intent.evidence),
        "diagnostics": dict(intent.diagnostics),
        # F-10 — bind every event to the exact pinned object revision the run replayed, so a
        # reviewer resolves a rule id back to the immutable Strategy/Package revision.
        "item_id": record.item_id,
        "root_id": record.root_id,
        "revision_id": record.revision_id,
    }
    if intent.phase == "P4":
        # Every P4 intent is arbitrated, actionable or not — a ``no_op`` lands as
        # ``outcome="not_actionable"`` rather than being dropped, which is what makes a
        # suppression auditable (ADR §6 rule 5).
        decision = tick.report.by_item(intent.item_id)
        detail["arbitration"] = {
            "outcome": decision.outcome,
            "granted_units": decision.granted_units,
            "granted_notional": decision.granted_notional,
            "binding_constraint": decision.binding_constraint,
            "reason": decision.reason,
            "counterparty_item_id": decision.counterparty_item_id,
        }
    return detail


def _signal_events(run: PortfolioRun, pinned: Mapping[str, PinnedItem]) -> list[SignalEventRow]:
    """The decision trace: every mandatory event then every discretionary intent, per tick.

    Order within a tick is the phase order — P3 before P4 — so the journal reads in the order
    the run actually decided things, not in the order a reporter found them."""
    events: list[SignalEventRow] = []
    for tick in run.ticks:
        for intent in (*tick.mandatory, *tick.intents):
            events.append(
                SignalEventRow(
                    seq=len(events),
                    event_time=tick.timestamp,
                    event_type=intent.kind,
                    direction=intent.direction,
                    detail=_event_detail(intent, tick, pinned),
                )
            )
    return events


def _trade_metrics(trades: Sequence[TradeRow]) -> dict[str, Any]:
    """Trade-derived summary metrics, counted by the SHIPPED fold's rule.

    Deliberately the same predicate set ``combine_item_runs`` applies (a non-positive lot is a
    loser; only ``stop_loss`` extends the stop streak; ``profit_factor`` is null on zero gross
    loss and ``win_rate`` null with no trades) so a unified-clock number and a sequential one
    differ only where the SIMULATION differs, never because two folds counted differently."""
    winners = stops = stop_streak = max_stop_streak = 0
    gross_profit = gross_loss = _ZERO
    for trade in trades:
        if trade.pnl > _ZERO:
            winners += 1
            gross_profit += trade.pnl
        else:
            gross_loss += -trade.pnl
        if trade.exit_reason == "stop_loss":
            stops += 1
            stop_streak += 1
            max_stop_streak = max(max_stop_streak, stop_streak)
        else:
            stop_streak = 0
    total = len(trades)
    return {
        "total_trades": total,
        "total_winning_trades": winners,
        "total_stops": stops,
        "max_stop_streak": max_stop_streak,
        "win_rate": (
            (Decimal(winners) / Decimal(total) * _HUNDRED).quantize(_PCT) if total else None
        ),
        "profit_factor": (
            (gross_profit / gross_loss).quantize(_RATIO) if gross_loss > _ZERO else None
        ),
    }


def _capital_metrics(run: PortfolioRun) -> dict[str, Any]:
    """The pool's own figures, read off the ledger — no metric is recomputed from trades.

    No guard on ``P0``/``peak`` being positive: ``SleevePlan`` refuses a non-positive pool at
    construction and ``peak`` opens at ``P0`` and only ever rises, so a zero denominator is
    unreachable rather than unhandled."""
    ledger = run.ledger
    initial = ledger.plan.pool_initial.quantize(_MONEY)
    final_equity = ledger.equity.quantize(_MONEY)
    net_profit = (final_equity - initial).quantize(_MONEY)
    net_profit_pct = (net_profit / initial * _HUNDRED).quantize(_PCT)
    max_drawdown = run.max_drawdown.quantize(_MONEY)
    max_drawdown_pct = (max_drawdown / ledger.peak * _HUNDRED).quantize(_PCT)
    return {
        "initial_capital": initial,
        "final_equity": final_equity,
        "net_profit": net_profit,
        "net_profit_pct": net_profit_pct,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "romad": (
            (net_profit_pct / max_drawdown_pct).quantize(_RATIO)
            if max_drawdown_pct > _ZERO
            else None
        ),
    }


def _single_value(values: Sequence[Any]) -> Any:
    """One shared value, or ``None`` when the items disagree — the shipped fold's rule."""
    distinct = set(values)
    return next(iter(distinct)) if len(distinct) == 1 else None


def _executed_row(
    record: PinnedItem, run: PortfolioRun, counts: Mapping[str, tuple[int, int]]
) -> dict[str, Any]:
    """One executing item's row: its pinned identity, its sleeve, its booked contribution."""
    attribution = run.ledger.attribution[record.item_id]
    total, winners = counts.get(record.item_id, (0, 0))
    return {
        "item_id": record.item_id,
        "item_kind": record.item_kind,
        "item_label": record.item_label,
        "root_id": record.root_id,
        "revision_id": record.revision_id,
        "executed": True,
        "symbol": record.symbol,
        "timeframe": record.timeframe,
        "equity_share_percent": run.ledger.plan.shares[record.item_id],
        "initial_sleeve": run.ledger.plan.initial_sleeves[record.item_id],
        "realized_pnl": attribution.realized_pnl,
        "fees": attribution.fees,
        "funding": attribution.funding,
        "other_costs": attribution.other_costs,
        "net_contribution": attribution.net_contribution,
        "total_trades": total,
        "winning_trades": winners,
    }


def _non_executing_row(record: PinnedItem) -> dict[str, Any]:
    """A pinned object that took no part in the co-simulation — recorded, never faked."""
    return {
        "item_id": record.item_id,
        "item_kind": record.item_kind,
        "item_label": record.item_label,
        "root_id": record.root_id,
        "revision_id": record.revision_id,
        "executed": False,
        "symbol": None,
        "timeframe": None,
        "equity_share_percent": None,
        "initial_sleeve": None,
        "realized_pnl": None,
        "fees": None,
        "funding": None,
        "other_costs": None,
        "net_contribution": None,
        "total_trades": 0,
        "winning_trades": 0,
        "note": NON_EXECUTING_NOTE,
    }


def _composition(
    run: PortfolioRun,
    *,
    pinned: Mapping[str, PinnedItem],
    others: Sequence[PinnedItem],
    counts: Mapping[str, tuple[int, int]],
) -> dict[str, Any]:
    """The composition block. Executing rows follow the LEDGER's order, which is the
    ``(pin_ordinal, item_id)`` order the loop sorted participants into before reading any of
    them — so a caller that permutes ``items`` cannot move a row (ADR §14 A4). Non-executing
    rows are sorted by ``item_id`` for the same reason: they have no pin to follow."""
    plan = run.ledger.plan
    return {
        "strategy_count": len(run.ledger.attribution),
        "participating_item_count": len(run.ledger.attribution) + len(others),
        "capital_allocation": "shared_pool",
        "clock": "unified_merged_axis",
        "compounding_mode": plan.compounding_mode,
        "reserve_nominal": plan.reserve_nominal,
        "allocatable_initial": plan.allocatable_initial,
        "unallocated_initial": plan.unallocated_initial,
        "per_item_basis": PER_ITEM_BASIS,
        "items": [
            *(_executed_row(pinned[item_id], run, counts) for item_id in run.ledger.attribution),
            *(_non_executing_row(record) for record in sorted(others, key=lambda r: r.item_id)),
        ],
    }


def _partition(
    run: PortfolioRun, items: Sequence[PinnedItem]
) -> tuple[dict[str, PinnedItem], list[PinnedItem]]:
    """Split the pinned records into the ones that traded and the ones that merely took part.

    Fails closed on a traded item with no record: the alternative is an unnamed row in an
    immutable Result, which F-07 §4.4 exists to prevent. An extra record is not an error —
    a pinned Trading Signal / Trade Log legitimately participates without simulating."""
    pinned = {record.item_id: record for record in items}
    unpinned = sorted(item_id for item_id in run.ledger.attribution if item_id not in pinned)
    if unpinned:
        raise UnpinnedItemError(
            f"These items traded in the run but carry no pinned record: {unpinned}. "
            "A Result row that cannot be named cannot be attributed either."
        )
    return pinned, [record for record in items if record.item_id not in run.ledger.attribution]


def project_portfolio_run(
    run: PortfolioRun,
    *,
    items: Sequence[PinnedItem],
    execution_key: str,
    item_count: int,
) -> EngineOutput:
    """Project a finished co-simulation into the ONE composite ``EngineOutput`` (ADR §14).

    ``items`` carries the manifest's pinned per-item metadata; its ORDER is not read for
    anything the output states — executing rows follow the ledger's pin order and every other
    field is a property of the merged axis — so permuting it cannot move a number (A4).

    Raises rather than degrades: a traded item with no pinned record, a booked close with no
    open before it, and a position opened or closed at no price each stop the projection.
    None of them has a safe partial reading, and each would otherwise reach an immutable
    Result as a plausible-looking row."""
    pinned, others = _partition(run, items)
    walked = _walk_trades(run)
    trades = [trade for _, trade in walked]
    counts: dict[str, tuple[int, int]] = {}
    for item_id, trade in walked:
        total, winners = counts.get(item_id, (0, 0))
        counts[item_id] = (total + 1, winners + (1 if trade.pnl > _ZERO else 0))
    events = _signal_events(run, pinned)
    executing = [pinned[item_id] for item_id in run.ledger.attribution]
    summary: dict[str, Any] = {
        "symbol": _single_value([record.symbol for record in executing]),
        "timeframe": _single_value([record.timeframe for record in executing]),
        # F-05: the first and last valuation points actually walked, which on the merged axis
        # is the portfolio's own replayed range — not the range anybody requested.
        "period_start": run.ticks[0].timestamp if run.ticks else None,
        "period_end": run.ticks[-1].timestamp if run.ticks else None,
        **_capital_metrics(run),
        **_trade_metrics(trades),
    }
    diagnostics: dict[str, Any] = {
        "engine_kind": ENGINE_KIND,
        "reproducibility_note": (
            "Deterministic co-simulation of every pinned item on ONE merged valuation axis "
            "over ONE shared pool, projected into a single composite result. The equity "
            "curve is the ledger's own and is time-ordered by construction."
        ),
        "item_count": item_count,
        "tick_count": len(run.ticks),
        "decision_trace_count": len(events),
        "filtered_event_count": 0,
        "composition": _composition(run, pinned=pinned, others=others, counts=counts),
        "execution_key": execution_key,
        "policy_versions": {
            "portfolio_projection_version": PORTFOLIO_PROJECTION_VERSION,
            "portfolio_loop_version": PORTFOLIO_LOOP_VERSION,
        },
        "warnings": list(ABSENT_BY_CONSTRUCTION),
    }
    return EngineOutput(
        summary=summary,
        trades=trades,
        equity_points=_equity_points(run),
        signal_events=events,
        diagnostics=diagnostics,
        # Empty by construction, both declared in ``warnings``: the phase loop records no
        # held-window peak notional, and a filter veto never reaches a participant hook.
        position_intervals=[],
        filtered_events=[],
    )


def _allocation_provenance(
    run: PortfolioRun,
    *,
    pinned: Mapping[str, PinnedItem],
    capital_execution: Mapping[str, Any] | None,
) -> AllocationProvenance:
    """The frozen allocation record for this run, doc 13 §13.

    Identity (``plan_id`` / ``plan_revision_id`` / ``config_hash``) is copied from the run
    manifest's IMMUTABLE ``capital_execution`` snapshot — the same block the sizing chain
    resolved from — so the manifest names the exact plan revision the run replayed and never
    today's plan.

    The AMOUNTS come from the executed ``SleevePlan`` rather than from a re-read of the
    config. They are not a second opinion: the plan is the one the ledger actually charged
    against, and re-deriving them here would make the manifest capable of disagreeing with
    the Result it describes.

    **Honest boundary.** The run manifest pins the allocation CONFIG (via ``config_hash``)
    but not the plan revision's frozen ``derived_amounts`` payload, so there is no
    independently frozen preview here to cross-check the executed sleeves against. The
    caller therefore passes ``plan=None`` to :func:`build_portfolio_manifest` and
    ``divergences`` stays empty — which records that no comparison was made, NOT that a
    comparison was made and agreed."""
    snapshot = capital_execution if isinstance(capital_execution, Mapping) else {}
    config = snapshot.get("config")
    config_map = config if isinstance(config, Mapping) else {}
    plan = run.ledger.plan
    sleeves = plan.initial_sleeves
    entries = tuple(
        SleeveProvenance(
            composition_item_snapshot_id=item_id,
            # ``_partition`` has already refused a traded item with no pinned record, so
            # this lookup cannot miss; guarding it would suggest a fallback that must not
            # exist (an unnamed sleeve in an immutable manifest).
            item_revision_id=pinned[item_id].revision_id,
            share_percent=str(plan.shares.get(item_id, _ZERO)),
            initial_sleeve_capital=money_str(sleeves.get(item_id, _ZERO)),
        )
        # The LEDGER's order, which is the ``(pin_ordinal, item_id)`` order the loop sorted
        # participants into — so a caller that permutes its input cannot move an entry, the
        # same guarantee ``_composition`` states for the executing rows (ADR §14 A4).
        for item_id in run.ledger.attribution
    )
    return AllocationProvenance(
        # Stated, not read back from the snapshot. This function is reached only from the
        # worker's shared branch, which ``_use_unified_clock`` gates on
        # ``shared_allocation_requested(capital_execution)`` and which fails the run closed
        # if any item resolves to no sleeve — so shared capital is not an inference here, it
        # is the precondition. Echoing a ``False`` back from the snapshot would let a
        # disagreeing block label a genuinely shared run "independent", which doc 13 §13
        # treats as the one thing the record must never say.
        enabled=True,
        plan_id=_opt_str(snapshot.get("plan_id")),
        plan_revision_id=_opt_str(snapshot.get("plan_revision_id")),
        config_hash=_opt_str(snapshot.get("config_hash")),
        base_currency=_opt_str(config_map.get("currency")),
        compounding_mode=plan.compounding_mode,
        initial_capital=money_str(plan.pool_initial),
        reserve_amount=money_str(plan.reserve_nominal),
        capital_available=money_str(plan.allocatable_initial),
        total_allocated=money_str(sum(sleeves.values(), _ZERO)),
        unallocated=money_str(plan.unallocated_initial),
        active_share_total=str(sum(plan.shares.values(), _ZERO)),
        entries=entries,
    )


def build_portfolio_provenance(
    run: PortfolioRun,
    *,
    items: Sequence[PinnedItem],
    engine_version: str,
    capital_execution: Mapping[str, Any] | None,
    conflict_policy: str | None,
    data_revisions: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Assemble the ``portfolio_simulation`` manifest section for a finished co-simulation.

    This is the WRITER half of ``domain/backtest/portfolio_mode.py``. That module classifies
    a persisted Result by looking for exactly this section's
    ``policy_versions.portfolio_manifest_version``, and until this function had a production
    caller the ``unified_clock`` branch was unreachable from any real Result — every shared
    run read back as ``unknown``, which is the honest answer to "no evidence was retained"
    and the wrong one for a run that co-simulated on a merged clock.

    It lives HERE, inside ``execution/``, rather than in the worker on purpose.
    ``execution.provenance`` is a contained phase-loop module whose production importers are
    an allowlist a human signed with two named modules in it, and the containment gate scans
    for that import in every production module OUTSIDE this package. Assembling the section
    in ``application/jobs/backtest_engine.py`` would have widened that signed allowlist by a
    third, unsigned module. The worker stays a CALLER of this seam and never an IMPORTER of
    the phase loop's vocabulary — the same shape `C3`/`C4` settled for the loop itself.

    Every field is derived from the run that just finished and from the run manifest's own
    immutable snapshot. Nothing here reads the live composition, the live allocation plan or
    the live capability flag, so re-reading a Result written by this function can never
    re-interpret it.

    Raises rather than degrades, on the projection's own principle: a section that entered an
    immutable manifest with a guessed pin ordinal or an unnameable policy would be a
    provenance record nobody could trust."""
    pinned, _others = _partition(run, items)
    identities: list[ItemIdentity] = []
    for item_id in run.ledger.attribution:
        record = pinned[item_id]
        if record.pin_ordinal is None:
            raise MissingPinOrdinalError(
                f"Item '{item_id}' executed in the run but carries no pin ordinal. The "
                "manifest states a PIN, and a pin inferred from list position is one "
                "nobody assigned."
            )
        identities.append(
            ItemIdentity(
                item_id=record.item_id,
                item_kind=record.item_kind,
                pin_ordinal=record.pin_ordinal,
                root_id=record.root_id,
                selected_revision_id=record.revision_id,
                item_label=record.item_label,
            )
        )
    manifest = build_portfolio_manifest(
        engine_version=engine_version,
        allocation=_allocation_provenance(run, pinned=pinned, capital_execution=capital_execution),
        identities=identities,
        conflict_policy=resolve_policy(conflict_policy),
        tick_instants=run.instants,
        # The SAME series ``_equity_points`` persists as the equity-curve artifact, so the
        # ledger reference the manifest pins and the artifact a reader pages are the one
        # curve — a second selection here (``dated_points``, say) would pin a digest of
        # something nobody can fetch.
        equity_points=run.ledger.equity_points,
        # No frozen preview to compare against — see ``_allocation_provenance``.
        plan=None,
        data_revisions=data_revisions,
    )
    return manifest.as_dict()


__all__ = [
    "ABSENT_BY_CONSTRUCTION",
    "CONTRIBUTION_NEEDS_RESIMULATION",
    "ENGINE_KIND",
    "EXPOSURE_BASIS_IS_PORTFOLIO",
    "FILTER_JOURNAL_IS_ITEM_LOCAL",
    "ITEM_LOCAL_COUNTERS_ABSENT",
    "NON_EXECUTING_NOTE",
    "PER_ITEM_BASIS",
    "PORTFOLIO_PROJECTION_VERSION",
    "POSITION_INTERVALS_ABSENT",
    "MissingPinOrdinalError",
    "PinnedItem",
    "PortfolioProjectionError",
    "UnpairedCloseError",
    "UnpinnedItemError",
    "UnpricedIntentError",
    "build_portfolio_provenance",
    "project_portfolio_run",
]
