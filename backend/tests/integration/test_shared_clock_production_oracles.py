"""`C8` — production-worker ORACLES and the historical-compatibility proof (plan §C8).

`C4` proved the shared-clock branch is *reached* and that its arbitration behaves. It did so
by asserting properties of the persisted artifacts. This module does the other half of the
plan's ask: it re-derives what the run SHOULD have produced, independently of the engine, and
compares that to what a real worker actually persisted. An assertion that reads a number back
and checks it is self-consistent cannot fail when both sides come from the same computation;
an oracle can.

Everything here runs the SHIPPED path — ``request_backtest_run`` -> ``run_backtest`` ->
``_shared_clock_inputs`` -> ``build_engine_participant`` -> ``iter_portfolio`` ->
``project_portfolio_run`` -> Postgres — and then reads only what a reader of a finished
Result can page.

**What this module adds that was not already proved:**

* **A4, the plan's stop condition.** It was recorded NOT EVALUABLE, and the recorded REASON
  ("needs the real engine behind the loop", W0 §A4/A18) was discharged by `C3` + `C4`. It is
  measured here for the first time, and the measurement is not the one the existing reversed
  -list case makes: that case permutes ``prepared_items``, and ``_shared_clock_inputs``' own
  docstring says ``pin_ordinal`` "comes from the MANIFEST ... and never from a list
  position". Permuting the list therefore proves list position is ignored — a WEAKER claim
  than A4, which is about the mainboard order itself. This module permutes
  ``manifest["mainboard_items"]``, the actual and only source of ``pin_ordinal``.
* **Reconciliation and sleeve parity over a PERSISTED Result.** Both invariants were proved
  by `C3` against a hand-built harness (``unit/oracles/test_oracle_engine_participant.py``).
  Neither had ever been read off a row in Postgres, which is the only surface a reader meets.
* **The historical-compatibility pair asserted as ONE mutual exclusion**, over two Results
  that both exist in the same database at the same time.

**What this module does NOT prove, stated here so the limit is visible where it is read:**

* **A4 is not marked covered.** The composition measured below is UNCONTENDED. Under joint
  insolvency ``(pin_ordinal, item_id)`` is the documented tie-break, so the mainboard order is
  *supposed* to decide there; that boundary is pinned by a companion test but the contended
  case itself is not measured.
* **A6/A7 (compound vs fixed sleeve) and A9/A10 (a blocked item's share is never transferred,
  solvency shortfall rejects)** are proved today only at unit level
  (``test_oracle_portfolio_capital.py``, ``test_backtest_cross_item_arbitration.py``,
  ``test_backtest_portfolio_ledger.py``). Lifting them onto the worker is the same shape as
  the two invariants below and is NOT done here.
* **A3, A5, A14, A18 and A21** are already pinned over the worker by the `C4` module and are
  deliberately not restated — a second copy would be a second place to update.

The lift fixture is ``_lifted`` from the `C4` module: it patches the module global
``capability.SHARED_ALLOCATION_STATUS`` for the duration of a block. It is test-owned and
production cannot reach it — ``tests/unit/test_shared_allocation_two_world_gate.py`` asserts
structurally that no env var, setter or second assignment in ``backend/src`` can do the same.
No ``future_dev`` pin is weakened here; moving those pins is `C9`.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.jobs import backtest_engine as worker
from entropia.domain.backtest.execution.arbitration import (
    CONTENTION_SELECTION_POLICY,
    ItemArbitrationProfile,
)
from entropia.domain.backtest.execution.portfolio import COMPOSITION_CURVE_WARNING
from entropia.infrastructure.postgres.models import (
    DiagnosticArtifact,
    ResultEquityPoint,
    SignalEventRow,
    TradeLedgerRow,
)
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from tests.integration.test_backtest_persistence import (
    USER1,
    _run_diagnostics,
    _seed_principals,
)
from tests.integration.test_shared_clock_worker_branch import (
    _admit_and_run,
    _artifact_checksums,
    _composition,
    _enable_shared_pool,
    _lifted,
)

pytestmark = pytest.mark.integration

#: The pool every fixture in this module funds, mirroring ``_enable_shared_pool``.
_P0 = Decimal("50000.00")

#: The three signal-event fields a mainboard permutation is ALLOWED to move, and why none
#: of them is the simulation:
#:
#: * ``pin_ordinal`` is the permuted quantity itself — it records WHERE an item was pinned;
#: * ``seq`` is the trace's emission order, which follows the pin order by construction;
#: * ``signal_event_id`` is a ULID minted per row, so it differs between ANY two runs. It is
#:   the same construction that keeps ``diagnostics`` out of :func:`_artifact_checksums`.
_PERMUTATION_MOBILE_FIELDS = frozenset(
    {".detail.diagnostics.pin_ordinal", ".seq", ".signal_event_id"}
)

#: The two checksummed artifacts whose ROW ORDER follows the pin order. Measured, not
#: assumed, and the measurement is the reason A4 is reported as a claim about CONTENT rather
#: than about bytes: ``trade_ledger`` rows carry no item tag (see
#: :func:`_trade_rows`), so two items closing at the SAME instant produce two rows whose
#: order is the only thing distinguishing them.
_PERMUTATION_REORDERED_ARTIFACTS = frozenset({"signal_events", "trade_ledger"})


def _canonical_rows(rows: Any) -> list[str]:
    """Per-item rows as a comparable MULTISET — order-insensitive, content-sensitive."""
    return sorted(json.dumps(row, sort_keys=True, default=str) for row in rows)


def _flatten(prefix: str, obj: Any, out: dict[str, Any]) -> None:
    """Flatten nested JSON to dotted leaf paths, so a diff names a FIELD, not a blob.

    Comparing two decision traces as opaque strings answers "are they equal"; the question
    A4 actually asks is "if they differ, WHICH field differs" — a run whose granted size
    moved and a run whose pin label moved are the same inequality and opposite verdicts."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            _flatten(f"{prefix}.{key}", value, out)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            _flatten(f"{prefix}[{index}]", value, out)
    else:
        out[prefix] = obj


async def _flat_signal_events(
    session: Any, result_id: str
) -> dict[tuple[Any, ...], dict[str, Any]]:
    """The Result's decision trace, keyed by an identity that survives a permutation.

    Keyed by ``(item_id, occurred_at, event_type)`` rather than by ``seq``: under a
    permutation ``seq`` is one of the things expected to move, so keying by it would compare
    an event with a different event and report a difference that is only a re-pairing."""
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
    events: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        raw = {
            column.name: getattr(row, column.name)
            for column in row.__table__.columns
            if column.name not in ("id", "result_id")
        }
        flat: dict[str, Any] = {}
        _flatten("", json.loads(json.dumps(raw, sort_keys=True, default=str)), flat)
        detail = raw.get("detail")
        item_id = detail.get("item_id") if isinstance(detail, dict) else None
        events[(item_id, str(raw.get("occurred_at")), str(raw.get("event_type")))] = flat
    return events


async def _trade_rows(session: Any, result_id: str) -> list[dict[str, Any]]:
    """The Result's composite trade ledger, in ``seq`` order, minus the per-row ULID.

    ``trade_row_id`` is minted per row and differs between any two runs by construction, so
    it is dropped for the same reason ``diagnostics`` is dropped from the checksum set: it
    says nothing about the simulation and would make every identity claim unsatisfiable.

    What is NOT dropped, and cannot be, is that a row carries no item tag. ``TradeRow`` has
    no item column (``_walk_trades`` has to return the tag alongside it precisely because the
    row cannot hold it), so on a shared pool two items closing at the same instant produce
    two rows that are distinguishable only by their ORDER. That is why the permutation case
    below compares this ledger as a multiset for content and separately as a sequence."""
    rows = (
        (
            await session.execute(
                select(TradeLedgerRow)
                .where(TradeLedgerRow.result_id == result_id)
                .order_by(TradeLedgerRow.seq)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            column.name: str(getattr(row, column.name))
            for column in row.__table__.columns
            if column.name not in ("id", "result_id", "seq", "trade_row_id")
        }
        for row in rows
    ]


async def _final_equity(session: Any, result_id: str) -> Decimal:
    """The last point of the Result's own persisted equity curve."""
    rows = (
        (
            await session.execute(
                select(ResultEquityPoint)
                .where(ResultEquityPoint.result_id == result_id)
                .order_by(ResultEquityPoint.seq)
            )
        )
        .scalars()
        .all()
    )
    assert rows, "a succeeded run must persist an equity curve"
    return Decimal(str(rows[-1].equity))


async def _enable_shared_pool_plan(
    session: Any,
    actor: Any,
    composition_id: str,
    *,
    reserve_percent: str = "0",
    shares: tuple[str, ...] | None = None,
    compound: bool = True,
) -> list[str]:
    """A shared-pool plan with an explicit reserve and explicit, optionally UNEQUAL shares.

    ``_enable_shared_pool`` splits the pool evenly, and even shares hide a whole class of
    defect from the permutation test: if sleeves were handed out BY PIN POSITION rather than
    by item identity, two 50% sleeves would swap into an indistinguishable arrangement and
    the permutation would reveal nothing. Unequal shares make that swap observable, which is
    what lets the A4 case below be falsifiable at all. Returns the item ids in mainboard
    order so a caller can say which share went to whom.

    ``compound`` selects the sizing base doc 13 §8.3 puts on the two sides of the A6/A7
    axis: a pool that recomputes ``Ci(t)`` from portfolio ``E(t)``, or one that holds
    ``Ci_fixed``. It is a parameter rather than a second helper because two runs on that
    axis must differ in exactly this and nothing else — a hand-written twin would be free
    to drift in the reserve, the shares or the capital, and the axis would stop being
    isolated."""
    items = [
        item
        for item in await mb_repo.list_active_items(session, composition_id)
        if str(item.item_kind) == "strategy"
    ]
    if shares is None:
        shares = tuple(str(Decimal(100) / Decimal(len(items))) for _ in items)
    assert len(shares) == len(items), "one share per strategy item"
    assert sum(Decimal(s) for s in shares) == Decimal(100), "shares must fund the whole pool"
    await alloc_cmd.upsert_allocation_draft(
        session,
        actor,
        composition_id=composition_id,
        expected_row_version=None,
        enabled=True,
        initial_capital={"amount": str(_P0), "currency": "USDT"},
        compounding_mode=(
            "COMPOUND_PORTFOLIO_EQUITY" if compound else "FIXED_INITIAL_PORTFOLIO_CAPITAL"
        ),
        reserve_cash_percent=reserve_percent,
        entries=[
            {
                "composition_item_id": item.item_id,
                "active": True,
                "equity_share_percent": share,
            }
            for item, share in zip(items, shares, strict=True)
        ],
        idempotency_key=f"c8-plan-{compound}-{reserve_percent}-{'-'.join(shares)}",
    )
    await session.commit()
    return [str(item.item_id) for item in items]


# --------------------------------------------------------------------------- #
# A4 — the plan's stop condition, measured                                     #
# --------------------------------------------------------------------------- #
async def test_permuting_the_mainboard_pins_does_not_move_one_financial_figure(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 **A4** — *item order does not change the result*, on a REAL Result.

    The plan records A4 as NOT EVALUABLE, and W0 records the REASON: it "needs the real
    engine behind the loop". `C3` put the engine behind the loop and `C4` wired the worker to
    it, so the reason is discharged and A4 is measured here for the first time.

    This is not the claim the existing reversed-list case makes. That one permutes
    ``prepared_items``, and ``_shared_clock_inputs``' own docstring says ``pin_ordinal``
    "comes from the MANIFEST ... and never from a list position" — so permuting the list
    proves list position is ignored, which is WEAKER than A4. The permutation here is applied
    to ``manifest["mainboard_items"]``, the list the worker enumerates to build ordinals and
    the only source of them. The SAME composition is run both ways: two separately seeded
    compositions carry different ULIDs and could never be compared at all.

    **The measured verdict, in the two halves it actually has.** The money is invariant: the
    equity curve and the filtered journal keep their stored checksums, every item's
    attribution row survives as a multiset, and the trade ledger holds the same trades at the
    same prices for the same PnL. What is NOT invariant is the ORDER of two artifacts —
    ``signal_events`` and ``trade_ledger``. Both are explained and both are bounded here
    rather than waved at: the decision trace moves in exactly three fields, each provenance
    rather than outcome (:data:`_PERMUTATION_MOBILE_FIELDS`), and the trade ledger reorders
    because its rows carry no item tag and the two trades close at the SAME instant, so the
    pin order is the only thing that can sequence them.

    Stating it as "identical digests" would therefore be false, and stating it as "the
    digests moved" would be misleading. The trace and the ledger are compared field-by-field
    and as a multiset instead, because "they differ" is the same inequality whether a pin
    LABEL moved or a granted size did, and only one of those is A4 failing.

    Honest boundary the fixture cannot state for itself: this composition is UNCONTENDED —
    every intent is admitted with no binding constraint. Where two intents are jointly
    insolvent, ``(pin_ordinal, item_id)`` is the documented tie-break, so there the mainboard
    order is *supposed* to decide and A4 is not a claim about that case. The companion test
    below pins that reading so this one cannot be read as more than it measured."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    # UNEQUAL, deliberately: see ``_enable_shared_pool_plan``. With two 50% sleeves a
    # projection that handed sleeves out by pin POSITION would swap them into an identical
    # arrangement and this test could never see it.
    await _enable_shared_pool_plan(session, USER1, composition_id, shares=("60", "40"))
    real = worker._shared_clock_inputs
    permutations: list[list[str]] = []

    def _reverse_the_manifest_pins(prepared_items: list[Any], **kwargs: Any) -> Any:
        manifest = dict(kwargs.pop("manifest"))
        pinned = list(manifest.get("mainboard_items", []))
        permutations.append([str(entry.get("item_id")) for entry in pinned])
        manifest["mainboard_items"] = list(reversed(pinned))
        return real(prepared_items, manifest=manifest, **kwargs)

    with _lifted(monkeypatch):
        control = await _admit_and_run(session, composition_id, idempotency_key="c8-order-a")
        monkeypatch.setattr(worker, "_shared_clock_inputs", _reverse_the_manifest_pins)
        permuted = await _admit_and_run(session, composition_id, idempotency_key="c8-order-b")

    assert control["state"] == "succeeded" and permuted["state"] == "succeeded"
    # The permutation really happened and really was non-trivial. Without this a patch that
    # silently failed to apply would turn the whole test into a run compared with itself.
    assert permutations and len(permutations[-1]) == 2
    assert permutations[-1] != list(reversed(permutations[-1]))

    control_sums = await _artifact_checksums(session, control["result_id"])
    permuted_sums = await _artifact_checksums(session, permuted["result_id"])
    moved = {kind for kind in control_sums if control_sums[kind] != permuted_sums[kind]}
    # The equity curve and the filtered journal are byte-identical, and they are named as the
    # ones that hold rather than left implicit: the curve is the pool's whole financial
    # history, so a permutation that moved any money at all would have to move it here.
    assert moved <= _PERMUTATION_REORDERED_ARTIFACTS, moved
    assert control_sums["equity_curve"] == permuted_sums["equity_curve"]
    assert control_sums["filtered_events"] == permuted_sums["filtered_events"]

    control_diag = await _run_diagnostics(session, control["result_id"])
    permuted_diag = await _run_diagnostics(session, permuted["result_id"])
    assert {k: v for k, v in control_diag.items() if k != "composition"} == {
        k: v for k, v in permuted_diag.items() if k != "composition"
    }
    control_comp, permuted_comp = control_diag["composition"], permuted_diag["composition"]
    assert {k: v for k, v in control_comp.items() if k != "items"} == {
        k: v for k, v in permuted_comp.items() if k != "items"
    }
    # A multiset, not a sequence: the per-item ROWS are emitted in pin order, so their order
    # is expected to follow the permutation. What may not change is any figure inside them —
    # and with 60/40 sleeves that is a real constraint, because a projection handing sleeves
    # out by pin POSITION would give the 60% item 40% here and be caught on this line.
    assert _canonical_rows(control_comp["items"]) == _canonical_rows(permuted_comp["items"])

    # The trade ledger, split into the two claims it actually supports. As CONTENT it is
    # invariant: the same trades closed at the same prices for the same PnL. As a SEQUENCE it
    # is not, and that is not a defect being tolerated — the rows carry no item tag, the two
    # trades here close at the SAME instant, and something has to order them. The pin order
    # does. Both halves are asserted because either alone misreports: the multiset alone
    # would hide that the mainboard order is observable at all, and the sequence alone would
    # read as money moving.
    control_trades = await _trade_rows(session, control["result_id"])
    permuted_trades = await _trade_rows(session, permuted["result_id"])
    assert sorted(map(str, control_trades)) == sorted(map(str, permuted_trades))
    assert {row["exit_time"] for row in control_trades} == {
        row["exit_time"] for row in permuted_trades
    }
    # The same-instant premise the reordering explanation rests on, measured rather than
    # asserted in prose: if these trades did NOT share an exit instant, a reordered ledger
    # would mean the merged axis itself had been permuted, which is a different and much
    # worse finding.
    assert len({row["exit_time"] for row in control_trades}) == 1

    control_events = await _flat_signal_events(session, control["result_id"])
    permuted_events = await _flat_signal_events(session, permuted["result_id"])
    # Same events happened to the same items at the same instants. If the permutation had
    # changed WHICH decisions were taken, this alone would fail.
    assert set(control_events) == set(permuted_events)
    differing: set[str] = set()
    for identity, control_event in control_events.items():
        permuted_event = permuted_events[identity]
        differing |= {
            field
            for field in set(control_event) | set(permuted_event)
            if control_event.get(field) != permuted_event.get(field)
        }
    assert differing <= _PERMUTATION_MOBILE_FIELDS, differing
    # The delta is not merely bounded, it is PRESENT: a permutation that silently failed to
    # reach the ordinals would leave the trace identical and satisfy the subset check above
    # vacuously.
    assert ".detail.diagnostics.pin_ordinal" in differing


def test_the_pin_ordinal_tie_break_is_the_documented_boundary_of_item_order_invariance() -> None:
    """The SCOPE of A4, pinned as a fact about the shipped arbitration rather than a comment.

    A4 is not "the mainboard order is inert". ``arbitration`` admits jointly-insolvent
    intents in ``(pin_ordinal, item_id)`` order — :data:`CONTENTION_SELECTION_POLICY` is
    literally ``"pin_order_admission"`` — so under contention the mainboard order is the
    deciding input BY DESIGN. Reading the test above as an unconditional invariance would
    make a future contended counter-example look like a regression when it is the documented
    rule working.

    Asserted on the comparable value itself, and asserted in the direction that matters: the
    ORDINAL must dominate the ``item_id``. A tie-break that compared ``item_id`` first would
    also be a total order, would also be deterministic, and would make A4 unconditionally
    true — so a test that only checked "some deterministic order exists" would pass on the
    implementation whose absence this scope note depends on."""
    later_ordinal_earlier_id = ItemArbitrationProfile(item_id="a", pin_ordinal=1)
    earlier_ordinal_later_id = ItemArbitrationProfile(item_id="b", pin_ordinal=0)

    assert earlier_ordinal_later_id.priority < later_ordinal_earlier_id.priority
    assert CONTENTION_SELECTION_POLICY == "pin_order_admission"


# --------------------------------------------------------------------------- #
# Invariant 1 — reconciliation, over a PERSISTED Result                        #
# --------------------------------------------------------------------------- #
async def test_the_persisted_per_item_attribution_closes_to_the_pools_own_equity_delta(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 reconciliation, read off Postgres instead of a hand-built ledger.

    `C3` proved this against a harness it constructed
    (``test_the_pools_attribution_equals_each_items_own_realized_delta``). That proof stops
    at the loop's return value: the projection still has to decompose the pool into per-item
    rows, and a decomposition that dropped, double-counted or rounded a component would leave
    the loop's invariant intact and the READER's rows wrong. The additive decomposition must
    close to a ZERO residual on the artifact a reader actually pages.

    Two independent legs, because either alone is weak:

    * the residual closes — ``sum(net_contribution) == final_equity - P0``;
    * each row's own components close — ``net == realized - fees - funding - other``. Without
      this, a projection that wrote the correct total into ``net_contribution`` while
      mis-splitting it across the cost buckets would still satisfy the first leg.

    A vacuity guard runs first: on a run where nothing traded, every figure is zero and both
    legs hold for a projection that emits constants."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)

    with _lifted(monkeypatch):
        out = await _admit_and_run(session, composition_id, idempotency_key="c8-reconcile")

    assert out["state"] == "succeeded", out
    composition = (await _run_diagnostics(session, out["result_id"]))["composition"]
    executed = [row for row in composition["items"] if row.get("executed")]
    assert len(executed) == 2, executed
    # The run has something to reconcile. A pool that never moved reconciles trivially.
    assert any(Decimal(str(row["realized_pnl"])) != 0 for row in executed)
    assert any(Decimal(str(row["fees"])) != 0 for row in executed)

    for row in executed:
        components = (
            Decimal(str(row["realized_pnl"]))
            - Decimal(str(row["fees"]))
            - Decimal(str(row["funding"]))
            - Decimal(str(row["other_costs"]))
        )
        assert components == Decimal(str(row["net_contribution"])), row["item_id"]

    attributed = sum((Decimal(str(row["net_contribution"])) for row in executed), Decimal("0"))
    assert attributed == await _final_equity(session, out["result_id"]) - _P0


# --------------------------------------------------------------------------- #
# Invariant 2 — sleeve parity, over a PERSISTED Result                         #
# --------------------------------------------------------------------------- #
async def test_the_persisted_sleeve_is_the_published_allocatable_base_times_the_share(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 sleeve parity: ``Ci(0)`` has two derivations and they must agree.

    The Result publishes the inputs (``allocatable_initial``, ``equity_share_percent``) and
    the answer (``initial_sleeve``) side by side, so the sleeve can be re-derived from the
    row's own published base rather than taken on trust.

    The reserve is what makes it a test. With ``reserve_cash_percent="0"`` the allocatable
    base equals ``P0`` and an implementation that ignored the reserve entirely would satisfy
    the identity; a 10% reserve separates the two, so the assertion pins that the sleeve is a
    slice of what is ALLOCATABLE and not of the headline capital. Both facts are asserted —
    that the reserve was actually withheld, and that the sleeves sum to the base — because
    the second could hold over a base that silently reverted to ``P0``."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    await _enable_shared_pool_plan(
        session, USER1, composition_id, reserve_percent="10", shares=("60", "40")
    )

    with _lifted(monkeypatch):
        out = await _admit_and_run(session, composition_id, idempotency_key="c8-sleeve")

    assert out["state"] == "succeeded", out
    composition = (await _run_diagnostics(session, out["result_id"]))["composition"]
    allocatable = Decimal(str(composition["allocatable_initial"]))
    reserve = Decimal(str(composition["reserve_nominal"]))

    # The reserve is real and the base is NOT the headline capital — the premise the parity
    # assertion below needs in order to distinguish the two derivations at all.
    assert reserve == _P0 * Decimal("10") / Decimal("100")
    assert allocatable == _P0 - reserve
    assert allocatable != _P0

    executed = [row for row in composition["items"] if row.get("executed")]
    assert len(executed) == 2, executed
    for row in executed:
        share = Decimal(str(row["equity_share_percent"]))
        assert Decimal(str(row["initial_sleeve"])) == allocatable * share / Decimal("100")

    sleeves = sum((Decimal(str(row["initial_sleeve"])) for row in executed), Decimal("0"))
    assert sleeves == allocatable


# --------------------------------------------------------------------------- #
# A19 — historical compatibility, both sides, in one database                  #
# --------------------------------------------------------------------------- #
async def test_the_sequential_marker_is_absent_from_a_unified_result_and_present_on_a_legacy_one(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR §14 **A19** — the same marker, asserted from BOTH sides at once.

    Each half already ships, on a different plane: the unified Result's *absence* in the `C4`
    worker module, the legacy Result's *presence* in the containment suite. Two passing
    tests in two modules do not state the property either one is really about, which is that
    the marker PARTITIONS Results — a reader must be able to tell which clock produced a row
    from the row alone. That is only a partition if the two Results can be told apart while
    both exist, which is what this test arranges: one unified run and one legacy-shaped
    Result in the same database, compared against each other rather than against a constant.

    The legacy Result is made by giving a finished run's stored diagnostics the shape a
    pre-containment shared run left behind — the same construction the containment suite
    uses, and the reason it is honest: containment gates ADMISSION, so a genuinely
    pre-containment row can no longer be produced by this build, and pretending otherwise
    would be the only alternative."""
    await _seed_principals(session)
    composition_id = await _composition(session, USER1, count=2, shared_safe=True)
    await _enable_shared_pool(session, USER1, composition_id)

    with _lifted(monkeypatch):
        unified = await _admit_and_run(session, composition_id, idempotency_key="c8-a19-new")
        legacy = await _admit_and_run(session, composition_id, idempotency_key="c8-a19-old")

    assert unified["state"] == "succeeded" and legacy["state"] == "succeeded"

    row = (
        await session.execute(
            select(DiagnosticArtifact).where(
                DiagnosticArtifact.result_id == legacy["result_id"],
                DiagnosticArtifact.kind == "run_diagnostics",
            )
        )
    ).scalar_one()
    aged = dict(row.content)
    aged["composition"] = {"capital_allocation": "shared_pool", "strategy_count": 2}
    aged["warnings"] = [*aged.get("warnings", []), COMPOSITION_CURVE_WARNING]
    row.content = aged
    await session.commit()

    unified_diag = await _run_diagnostics(session, unified["result_id"])
    legacy_diag = await _run_diagnostics(session, legacy["result_id"])

    # The partition, stated as one mutual exclusion over two rows that coexist.
    assert COMPOSITION_CURVE_WARNING not in unified_diag["warnings"]
    assert COMPOSITION_CURVE_WARNING in legacy_diag["warnings"]
    # And the aged row is untouched otherwise: containment re-interprets nothing it finds.
    assert legacy_diag["composition"]["capital_allocation"] == "shared_pool"
