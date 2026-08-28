"""`C9`-preparation — the CAPITAL invariants of a shared pool, on a REAL worker Result.

`C8` (ADIM 127) lifted A4, A19, reconciliation and sleeve parity onto the production worker
and recorded, in its own honest boundary, what it did NOT lift: **A6/A7** (the compounding
axis) and **A9/A10** (a blocked item's share is never transferred; a solvency shortfall
rejects whole). All four ship today with unit-level proofs only —
``unit/oracles/test_oracle_portfolio_capital.py`` and
``unit/test_backtest_cross_item_arbitration.py`` drive a hand-built ledger. This module is
the other half of that sentence: the same four properties, re-derived from the artifacts a
reader of a finished Result can page, after the SHIPPED path
(``request_backtest_run`` -> ``run_backtest`` -> ``build_engine_participant`` ->
``iter_portfolio`` -> ``project_portfolio_run`` -> Postgres) actually ran.

**The one fixture change that makes any of this observable.** ``Ci(t)`` is not a published
column — the Result publishes ``initial_sleeve``, which is ``Ci(0)``. What it does publish
per decision is ``arbitration.granted_notional``, and when a decision is ``capped`` by
:data:`SLEEVE_CONSTRAINT` that number IS the sleeve at that tick, because the sleeve was the
binding limit. Every fixture here therefore sizes at :data:`_OVERSIZED` — a percent ABOVE
100 of the resolved capital — so the item always wants more than its sleeve and the pool
always has to say how much the sleeve was. With the suite's stock 1% sizing the request is
two orders of magnitude below the sleeve, nothing ever binds, and ``Ci(t)`` is invisible.

**Why the shipped ``_e2e_bars`` fixture is enough, measured rather than assumed.** Both
items break out on 2024-02-21 and stop out on 2024-02-22, and on that second bar the phase
order puts both P3 exits (which BOOK the loss) before both P4 entries. So the second entry
of every run below is decided against a pool that has already lost money — which is exactly
the situation A6, A7, A9 and A10 are all statements about. No bar had to be invented.

**Contention is a FIXED-mode phenomenon, and that too is measured.** Under
``COMPOUND_PORTFOLIO_EQUITY`` the sleeves are recomputed from ``A(t)`` and therefore sum to
``A(t)`` exactly, so the pool can always fund every sleeve and solvency never binds. Under
``FIXED_INITIAL_PORTFOLIO_CAPITAL`` the sleeves hold ``Ci_fixed`` while the pool's real
allocatable capital follows ``E(t)`` down — ADR §9.1's *"the one place genuine contention
arises"*. Every contended assertion below is therefore on the fixed side, and that is a
property of the shipped design, not of the fixture.

**What this module does NOT claim.** A4 is still not marked covered. The last test measures
the CONTENDED case `C8` deliberately left out and finds the mainboard order deciding — which
is the documented ``pin_order_admission`` rule working, not A4 failing. See its docstring.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.jobs import backtest_engine as worker
from entropia.domain.backtest.execution.portfolio_ledger import (
    LEDGER_INSOLVENT,
    SLEEVE_CONSTRAINT,
    SOLVENCY_CONSTRAINT,
)
from entropia.infrastructure.postgres.models import SignalEventRow
from tests.integration.test_backtest_persistence import (
    USER1,
    _run_diagnostics,
    _seed_principals,
)
from tests.integration.test_shared_clock_production_oracles import (
    _P0,
    _canonical_rows,
    _enable_shared_pool_plan,
    _final_equity,
    _trade_rows,
)
from tests.integration.test_shared_clock_worker_branch import (
    _admit_and_run,
    _composition,
    _lifted,
)

pytestmark = pytest.mark.integration

#: ``position_sizing.base_position_size`` as a percent of the resolved capital (GH #550).
#: Above 100 so the sleeve is the BINDING limit on every entry — see the module docstring.
#: 150 rather than 101 so that the amount an item is refused is large relative to the cent
#: it is quantized to, and so that its full request still FITS in the pool's headroom, which
#: is what makes the A9 case below falsifiable at all.
_OVERSIZED = "150.0"

#: The reserve every fixture withholds. Non-zero deliberately: with ``0`` the allocatable
#: base equals ``P0`` and a sleeve that silently ignored the reserve would satisfy every
#: identity below.
_RESERVE_PERCENT = "10"

#: Deliberately UNEQUAL. Equal sleeves make an implementation that hands capacity out by pin
#: POSITION indistinguishable from one that honours the share structure, which is the vacuity
#: hole `C8` measured the hard way (ADIM 127, its A4 case).
_SHARES = ("60", "40")

#: ``costs.commission`` from ``_strategy_payload``, charged FLAT per fill since ADIM 114
#: (``commission_basis`` defaults to ``flat``). Named because the A10 case reads it as the
#: material evidence that a refused entry produced no fill at all — not merely a report
#: saying zero.
_FLAT_COMMISSION_PER_FILL = Decimal("0.04")

_CENT = Decimal("0.01")


def _cents(value: Decimal) -> Decimal:
    """A published money figure, at the precision ``granted_notional`` is stored in."""
    return value.quantize(_CENT)


async def _entry_ticks(session: Any, result_id: str) -> list[list[dict[str, Any]]]:
    """The Result's P4 entry decisions, grouped by instant, both in ``seq`` order.

    Grouped rather than flat because every claim here is about what the pool did with ONE
    frozen valuation, and read from the persisted trace rather than from the in-memory run:
    an invariant that never survives to the artifact is an invariant no reader can check."""
    rows = (
        (
            await session.execute(
                select(SignalEventRow)
                .where(SignalEventRow.result_id == result_id)
                .order_by(SignalEventRow.seq)
            )
        )
        .scalars()
        .all()
    )
    ticks: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        detail = row.detail
        if detail.get("phase") == "P4" and detail.get("arbitration") is not None:
            ticks[detail["t_ms"]].append(detail)
    return [ticks[key] for key in sorted(ticks)]


async def _oversized_shared_run(
    session: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    compound: bool,
    idempotency_key: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One shared-pool run at :data:`_OVERSIZED` sizing, plus its stored diagnostics.

    The two callers that differ only in ``compound`` are the A6/A7 axis, so everything else
    — capital, reserve, shares, bars, sizing — is fixed here rather than at the call sites,
    where it could drift and quietly stop isolating the axis."""
    await _seed_principals(session)
    composition_id = await _composition(
        session, USER1, count=2, shared_safe=True, size_percent=_OVERSIZED
    )
    await _enable_shared_pool_plan(
        session,
        USER1,
        composition_id,
        reserve_percent=_RESERVE_PERCENT,
        shares=_SHARES,
        compound=compound,
    )
    with _lifted(monkeypatch):
        out = await _admit_and_run(session, composition_id, idempotency_key=idempotency_key)
    assert out["state"] == "succeeded", out
    return dict(out), await _run_diagnostics(session, out["result_id"])


async def _pool_equity_at_the_second_entry(session: Any, result_id: str) -> Decimal:
    """``E(t)`` at the tick the second entries are decided on, re-derived independently.

    The pool's own equity curve does not publish this instant — it carries the tick's own
    valuation, not the intra-tick state after P3 booked. So it is rebuilt from the trade
    ledger: ``P0`` plus every lot that had closed by then. That is what makes this an ORACLE
    rather than a read-back — the sleeve is compared against a figure derived from a
    different artifact by different arithmetic."""
    closed = [Decimal(row["pnl"]) for row in await _trade_rows(session, result_id)]
    assert len(closed) == 2, closed
    return _P0 + sum(closed, Decimal("0"))


# --------------------------------------------------------------------------- #
# A6 — compound: the sleeve follows the POOL, siblings included                #
# --------------------------------------------------------------------------- #
async def test_a_compounding_sleeve_follows_the_pools_equity_and_not_the_items_own(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 **A6** — *sleeves recompute from portfolio E(t) incl. siblings' PnL*, on a
    persisted Result rather than on the hand-built ledger that proves it today.

    The measurement it takes to see this at all: on the second tick both items are ``capped``
    by :data:`SLEEVE_CONSTRAINT`, so each ``granted_notional`` IS that item's ``Ci(t)``. Both
    are then compared against ``A(t) * wi / 100`` where ``A(t)`` comes from the TRADE LEDGER
    — ``P0`` plus the lots that closed on this very tick — and not from anything the sizing
    path also read.

    **The sibling half, stated as a refutation rather than as a hope.** "The sleeve fell" is
    satisfied by an item compounding off its OWN realized result, which is precisely what the
    shipped sequential engine does and precisely what A6 exists to exclude. So the two
    single-lot counterfactuals are named and denied: neither ``(P0 + this item's lot)`` nor
    ``(P0 + the sibling's lot)`` produces the sleeve the pool actually granted. Only the sum
    does. The guard that keeps that non-vacuous is asserted first — the two lots must differ,
    or there is one counterfactual wearing two hats."""
    out, diagnostics = await _oversized_shared_run(
        session, monkeypatch, compound=True, idempotency_key="c9-a6-compound"
    )
    composition = diagnostics["composition"]
    assert composition["compounding_mode"] == "COMPOUND_PORTFOLIO_EQUITY"
    reserve = Decimal(str(composition["reserve_nominal"]))
    shares = {
        row["item_id"]: Decimal(str(row["equity_share_percent"])) for row in composition["items"]
    }
    sleeves_at_zero = {
        row["item_id"]: Decimal(str(row["initial_sleeve"])) for row in composition["items"]
    }

    lots = [Decimal(row["pnl"]) for row in await _trade_rows(session, out["result_id"])]
    # Non-vacuity, both ways: the pool really moved, and the two lots are DISTINGUISHABLE, so
    # the two counterfactuals below are genuinely two different numbers.
    assert len(lots) == 2 and all(lot < 0 for lot in lots), lots
    assert lots[0] != lots[1], lots

    pool_equity = await _pool_equity_at_the_second_entry(session, out["result_id"])
    allocatable = pool_equity - reserve
    assert pool_equity < _P0

    ticks = await _entry_ticks(session, out["result_id"])
    assert len(ticks) == 2, ticks
    second = ticks[-1]
    assert len(second) == 2, second

    for decision in second:
        share = shares[decision["item_id"]]
        arbitration = decision["arbitration"]
        # The sleeve is only READABLE because it bound. Asserting the cap is not decoration:
        # an ``admitted`` decision publishes what the item asked for, which is a different
        # number and would make every identity below a coincidence.
        assert arbitration["outcome"] == "capped", arbitration
        assert arbitration["binding_constraint"] == SLEEVE_CONSTRAINT, arbitration
        granted = Decimal(str(arbitration["granted_notional"]))

        assert granted == _cents(allocatable * share / Decimal(100)), decision["item_id"]
        # It really recomputed — a fixed base would have republished Ci(0) here.
        assert granted < sleeves_at_zero[decision["item_id"]]

        # A6's actual content: the base is the POOL's equity, so removing either lot from it
        # changes the answer. An item compounding off its own realized result would have
        # landed on one of these two values.
        for solo in lots:
            counterfactual = _cents((_P0 + solo - reserve) * share / Decimal(100))
            assert granted != counterfactual, (decision["item_id"], solo)


# --------------------------------------------------------------------------- #
# A7 — fixed: the base holds, and the pool still refuses to borrow             #
# --------------------------------------------------------------------------- #
async def test_a_fixed_sleeve_holds_its_initial_base_while_the_pool_refuses_to_borrow(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 **A7** — *sizing base stays ``Ci_fixed``; no auto-compounding; no silent
    borrow* — over a Result, on the same fixture the A6 case runs.

    Two halves, and the second is the one a "the number did not change" assertion cannot
    reach on its own. ``Ci_fixed`` holding is asserted against BOTH candidate values: it
    equals ``A0 * wi / 100`` and it is NOT the compound answer the sibling test just measured
    — so a run that had quietly compounded could not pass by arithmetic coincidence.

    Then the borrow. Holding ``Ci_fixed`` while ``E(t)`` falls is exactly what makes the
    fixed sleeves overcommit: their SUM exceeds what the pool can actually fund at this tick.
    That is the situation in which a silent borrow would be invisible in any single figure —
    every item would simply get what its sleeve said. The pool is asserted not to have done
    it: what it committed is bounded by ``A(t)``, not by the sum of the sleeves it published
    at ``t=0``.

    **A measured property of the fixture, written here because it bounds what any control
    can show.** Contention exists only while ``sum(Ci_fixed)`` sits inside ``(A(t), A0]`` —
    below it every sleeve is fundable, above it the refusal moves to the FIRST tick and the
    second lot never closes. Perturbing the fixed base therefore cannot leave the contended
    cases below untouched: on one composition, "the base held" and "the contention resolved
    this way" are not independently falsifiable."""
    out, diagnostics = await _oversized_shared_run(
        session, monkeypatch, compound=False, idempotency_key="c9-a7-fixed"
    )
    composition = diagnostics["composition"]
    assert composition["compounding_mode"] == "FIXED_INITIAL_PORTFOLIO_CAPITAL"
    reserve = Decimal(str(composition["reserve_nominal"]))
    allocatable_initial = Decimal(str(composition["allocatable_initial"]))
    rows = {row["item_id"]: row for row in composition["items"]}

    pool_equity = await _pool_equity_at_the_second_entry(session, out["result_id"])
    allocatable_now = pool_equity - reserve
    # The base COULD have moved: the pool is poorer than it started. Without this the
    # "unchanged" assertion below holds for a run in which nothing ever happened.
    assert pool_equity < _P0
    assert allocatable_now < allocatable_initial

    ticks = await _entry_ticks(session, out["result_id"])
    assert len(ticks) == 2, ticks
    admitted = ticks[-1][0]
    arbitration = admitted["arbitration"]
    assert arbitration["outcome"] == "capped", arbitration
    assert arbitration["binding_constraint"] == SLEEVE_CONSTRAINT, arbitration
    granted = Decimal(str(arbitration["granted_notional"]))
    share = Decimal(str(rows[admitted["item_id"]]["equity_share_percent"]))

    # Ci_fixed, stated against both candidates rather than only against the one it is.
    assert granted == _cents(allocatable_initial * share / Decimal(100))
    assert granted == Decimal(str(rows[admitted["item_id"]]["initial_sleeve"])).quantize(_CENT)
    assert granted != _cents(allocatable_now * share / Decimal(100))

    # No silent borrow. The fixed sleeves now promise more than the pool holds — that is the
    # premise, and it is asserted rather than assumed — and the pool committed less than it
    # can fund anyway.
    published_sleeves = sum(
        (Decimal(str(row["initial_sleeve"])) for row in composition["items"]), Decimal("0")
    )
    assert published_sleeves > allocatable_now
    committed = sum(
        (Decimal(str(decision["arbitration"]["granted_notional"])) for decision in ticks[-1]),
        Decimal("0"),
    )
    assert committed <= allocatable_now
    assert committed < published_sleeves


# --------------------------------------------------------------------------- #
# A10 — a solvency shortfall rejects WHOLE                                     #
# --------------------------------------------------------------------------- #
async def test_a_jointly_insolvent_entry_is_refused_whole_and_never_trimmed_to_the_headroom(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 **A10** / Modül 11 §5.3 — *solvency shortfall => reject; never partial fill,
    never borrow* — reached through the worker instead of through a scripted ledger.

    The refusal is only meaningful next to the number it refused to grant. The pool had
    positive headroom left after funding the earlier pin, and that headroom was smaller than
    the later pin's sleeve — so a trimming implementation had somewhere to trim TO, and the
    test names that amount and denies it. ``granted == 0`` alone would also be satisfied by a
    pool that had no headroom at all, which is a different and much weaker situation.

    And the fill, not merely the report. A partial fill would have opened a position, which
    on this fixture never closes and so never becomes a trade row — the ledger cannot see it.
    What does see it is the item's own realized fee: commission is charged FLAT per fill
    (ADIM 114), so the refused item ends the run exactly one commission behind the sibling
    that was funded at this tick. Nothing was filled for it at all.

    **Which guard this actually exercises — measured, after a control aimed at the wrong one
    stayed green.** The refusal here does NOT come from the ledger's own solvency branch in
    ``resolve_capacity``. That branch asks whether ONE order fits the frozen pool, and on
    this fixture the earlier pin's sleeve fits it comfortably. The refusal comes from
    ``arbitration._capacity_for``'s OD-3 branch, which nets what a SIBLING already committed
    at this same tick off the headroom — *"the case the ledger alone cannot see"*, in its own
    words. A worker-level A10 test that pinned the ledger's branch would be pinning a path
    the shared clock does not take on this shape."""
    out, diagnostics = await _oversized_shared_run(
        session, monkeypatch, compound=False, idempotency_key="c9-a10-reject"
    )
    composition = diagnostics["composition"]
    reserve = Decimal(str(composition["reserve_nominal"]))
    rows = {row["item_id"]: row for row in composition["items"]}
    allocatable_now = await _pool_equity_at_the_second_entry(session, out["result_id"]) - reserve

    contended = (await _entry_ticks(session, out["result_id"]))[-1]
    assert len(contended) == 2, contended
    funded, refused = contended[0], contended[1]

    assert funded["arbitration"]["outcome"] == "capped", funded
    refusal = refused["arbitration"]
    assert refusal["outcome"] == "rejected", refusal
    assert Decimal(str(refusal["granted_units"])) == Decimal("0")
    assert Decimal(str(refusal["granted_notional"])) == Decimal("0")
    assert refusal["binding_constraint"] == SOLVENCY_CONSTRAINT, refusal
    assert refusal["reason"] == LEDGER_INSOLVENT, refusal

    # The refusal was a CHOICE, not an absence of money. There was headroom, it was positive,
    # and it was less than the sleeve this item would otherwise have been capped to.
    headroom = allocatable_now - Decimal(str(funded["arbitration"]["granted_notional"]))
    refused_sleeve = Decimal(str(rows[refused["item_id"]]["initial_sleeve"]))
    assert headroom > 0
    assert headroom < refused_sleeve
    # The number a trimming pool would have granted, named and denied.
    assert Decimal(str(refusal["granted_notional"])) != _cents(headroom)

    # Nothing was filled. Both items entered once on the first tick; only the funded one
    # entered again here, and its realized commission is exactly one fill ahead.
    funded_fees = Decimal(str(rows[funded["item_id"]]["fees"]))
    refused_fees = Decimal(str(rows[refused["item_id"]]["fees"]))
    assert funded_fees - refused_fees == _FLAT_COMMISSION_PER_FILL


# --------------------------------------------------------------------------- #
# A9 — the refused item's share is not handed to anybody                       #
# --------------------------------------------------------------------------- #
async def test_the_refused_items_released_sleeve_is_never_handed_to_the_item_that_wanted_more(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 **A9** / doc 13 §8.4.6 — *a blocked item's share is never transferred*, made
    falsifiable at the worker by giving the surviving item somewhere to put it.

    This is the assertion the unit suite calls "checked the only way that means anything",
    and on a persisted Result the only way that means anything is different: the funded item
    must have WANTED the released capacity and must have been able to AFFORD it. Both are
    established rather than hoped for. It wanted it — it was capped by its own sleeve, and
    the request the pool priced (recovered from the same decision, ``granted_notional`` per
    granted unit times the units it asked for) is larger than that sleeve. It could have
    afforded it — that request is smaller than the pool's whole allocatable capital at this
    tick, so solvency was not what stopped it.

    What stopped it was the share structure, and the share structure did not move: the funded
    item got exactly ``A0 * wi / 100`` while a whole sibling sleeve sat released and unused,
    and the sleeves the Result publishes still sum to the allocatable base they were cut
    from."""
    out, diagnostics = await _oversized_shared_run(
        session, monkeypatch, compound=False, idempotency_key="c9-a9-no-transfer"
    )
    composition = diagnostics["composition"]
    reserve = Decimal(str(composition["reserve_nominal"]))
    allocatable_initial = Decimal(str(composition["allocatable_initial"]))
    rows = {row["item_id"]: row for row in composition["items"]}
    allocatable_now = await _pool_equity_at_the_second_entry(session, out["result_id"]) - reserve

    contended = (await _entry_ticks(session, out["result_id"]))[-1]
    funded, refused = contended[0], contended[1]
    assert refused["arbitration"]["outcome"] == "rejected", refused

    arbitration = funded["arbitration"]
    granted = Decimal(str(arbitration["granted_notional"]))
    granted_units = Decimal(str(arbitration["granted_units"]))
    assert arbitration["binding_constraint"] == SLEEVE_CONSTRAINT, arbitration
    # The price the pool itself used, recovered from the decision rather than re-derived from
    # a bar: the claim is about what THIS decision priced, and a second derivation of the
    # effective price would be a second thing that can be wrong.
    wanted = Decimal(str(funded["desired_size"])) / granted_units * granted

    # It wanted the capacity, and the pool could have funded the whole request. So only the
    # share structure can explain the number below.
    assert wanted > granted
    assert wanted < allocatable_now

    share = Decimal(str(rows[funded["item_id"]]["equity_share_percent"]))
    released = Decimal(str(rows[refused["item_id"]]["initial_sleeve"]))
    assert released > 0
    assert granted == _cents(allocatable_initial * share / Decimal(100))
    assert granted < _cents(allocatable_initial * share / Decimal(100) + released)

    # The published share structure is the same one the run started with.
    assert (
        sum((Decimal(str(row["initial_sleeve"])) for row in composition["items"]), Decimal("0"))
        == allocatable_initial
    )


# --------------------------------------------------------------------------- #
# A4 — the CONTENDED boundary `C8` measured around                             #
# --------------------------------------------------------------------------- #
async def test_under_contention_the_mainboard_order_decides_which_item_is_refused(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other side of ADR §14 **A4**, measured on Results instead of argued from a policy.

    `C8` measured A4 on an UNCONTENDED composition and found the money invariant under a
    mainboard permutation; it pinned the boundary of that reading with a unit assertion on
    ``ItemArbitrationProfile.priority``. This test closes the pair from the expensive side:
    the same permutation, applied to a composition where the two intents are jointly
    insolvent, and the consequence read off two persisted Results.

    **The measured answer is that A4 as ADR §14 words it — "permuting ``mainboard_items``
    yields an identical ``EngineOutput`` digest" — does not hold under contention, and is not
    supposed to.** ``CONTENTION_SELECTION_POLICY`` is ``"pin_order_admission"``: the pool
    admits in pin order and refuses what no longer fits, so the mainboard order decides WHICH
    item is refused and therefore how much capital the run deploys. The permutation is
    applied to ``manifest["mainboard_items"]`` for the same reason `C8` applies it there — it
    is the only source of ``pin_ordinal``.

    Three consequences, each a strictly stronger statement than the last, because "the
    outcomes differ" and "the money differs" are not the same finding: the refusal lands on a
    DIFFERENT item; the pool commits a different amount; and the pool's own final equity
    differs. That last one is the one a reader cares about, and it is exactly what `C8`
    measured to be INVARIANT on an uncontended composition. This test is therefore the reason
    A4 is not marked covered by either module."""
    await _seed_principals(session)
    composition_id = await _composition(
        session, USER1, count=2, shared_safe=True, size_percent=_OVERSIZED
    )
    await _enable_shared_pool_plan(
        session,
        USER1,
        composition_id,
        reserve_percent=_RESERVE_PERCENT,
        shares=_SHARES,
        compound=False,
    )
    real = worker._shared_clock_inputs
    permutations: list[list[str]] = []

    def _reverse_the_manifest_pins(prepared_items: list[Any], **kwargs: Any) -> Any:
        manifest = dict(kwargs.pop("manifest"))
        pinned = list(manifest.get("mainboard_items", []))
        permutations.append([str(entry.get("item_id")) for entry in pinned])
        manifest["mainboard_items"] = list(reversed(pinned))
        return real(prepared_items, manifest=manifest, **kwargs)

    with _lifted(monkeypatch):
        control = await _admit_and_run(session, composition_id, idempotency_key="c9-a4-a")
        monkeypatch.setattr(worker, "_shared_clock_inputs", _reverse_the_manifest_pins)
        permuted = await _admit_and_run(session, composition_id, idempotency_key="c9-a4-b")

    assert control["state"] == "succeeded" and permuted["state"] == "succeeded"
    # The permutation applied and was non-trivial — without this the whole test degenerates
    # into a run compared with itself, which would pass every inequality below by failing.
    assert permutations and len(permutations[-1]) == 2
    assert permutations[-1] != list(reversed(permutations[-1]))

    async def _contended(result_id: str) -> tuple[str, Decimal]:
        contended = (await _entry_ticks(session, result_id))[-1]
        assert len(contended) == 2, contended
        # SEARCHED for, never taken by position. Taking the refusal from slot 1 would fold
        # the claim into the helper: a pool that stopped honouring the pin order would then
        # fail here, in a precondition, instead of failing the comparison this test is FOR.
        refused = [d for d in contended if d["arbitration"]["outcome"] == "rejected"]
        funded = [d for d in contended if d["arbitration"]["outcome"] != "rejected"]
        assert len(refused) == 1 and len(funded) == 1, contended
        assert refused[0]["arbitration"]["binding_constraint"] == SOLVENCY_CONSTRAINT, refused
        return str(refused[0]["item_id"]), Decimal(
            str(funded[0]["arbitration"]["granted_notional"])
        )

    control_refused, control_committed = await _contended(control["result_id"])
    permuted_refused, permuted_committed = await _contended(permuted["result_id"])

    # (1) A different item is refused.
    assert control_refused != permuted_refused
    # (2) The pool deploys a different amount of capital.
    assert control_committed != permuted_committed
    # (3) And the money itself differs — the per-item attribution and the pool's own closing
    #     equity, the two figures `C8` measured to be invariant when nothing contended.
    control_items = (await _run_diagnostics(session, control["result_id"]))["composition"]["items"]
    permuted_items = (await _run_diagnostics(session, permuted["result_id"]))["composition"][
        "items"
    ]
    assert _canonical_rows(control_items) != _canonical_rows(permuted_items)
    assert await _final_equity(session, control["result_id"]) != await _final_equity(
        session, permuted["result_id"]
    )
