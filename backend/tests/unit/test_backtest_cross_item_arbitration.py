"""Cross-item conflict and capacity arbitration — pure unit tests (ADR 0002 §9, P5/P6b).

Proves the question that only exists once the pool is genuinely shared: when two items want
incompatible things at one instant, who gives way and why; when several individually
affordable orders are jointly unaffordable, which is refused and in what shape; and that
neither answer can be changed by the order a caller happened to build its inputs in.

The load-bearing claims, and how each is checked rather than asserted:

* **An unnameable policy is refused, not downgraded.** The shipped sequential engine
  substitutes ``BLOCK_OPPOSITE`` for ``NET`` and discloses it (``engine.py:862-871``); this
  layer refuses
  the run instead, because canon defines no netting price, custody, fee split, PnL
  attribution or margin (GH #544). The five gaps are named in the refusal.
* **KEEP_SEPARATE separates BOOKS, not capital.** Its rows still meet the sleeve cap, the
  portfolio exposure cap and the solvency limit.
* **A held position never gives way** — whatever its pin ordinal. The forward-only
  "later-pinned loses" rule was an artifact of the sequential loop and is retired here.
* **Solvency rejects whole; caps clamp.** Modül 11 §5.3 forbids a partial fill and a silent
  borrow, so a contended order is refused entirely — never trimmed to what is left.
* **A blocked item's capacity is never handed to a sibling** — checked the only way that
  means anything: the sibling's grant is byte-identical with and without the blocked item.

Every expected number is computed by hand from the canonical formula and written as a
literal. Containment is part of the contract: nothing in production imports this layer, so
the rollback stays "delete the module" and no shipped digest can move because it exists."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

import pytest

from entropia.domain.allocation.enums import CrossItemConflictPolicy
from entropia.domain.backtest.execution import arbitration
from entropia.domain.backtest.execution.arbitration import (
    ARBITRATION_POLICY_VERSION,
    ARBITRATION_REASONS,
    CONFLICT_POLICY_TABLE,
    CONFLICT_SYMBOL_UNKNOWN_GATE,
    CONTENTION_SELECTION_POLICY,
    CONTENTION_SELECTION_STATUS,
    EXPOSURE_CONSTRAINT,
    MAX_POSITION_CONSTRAINT,
    PORTFOLIO_CONFLICT_BLOCKED,
    SLEEVE_CONSTRAINT,
    SOLVENCY_CONSTRAINT,
    ConflictPolicyRule,
    DuplicateIntentError,
    ItemArbitrationProfile,
    LedgerNotFrozenError,
    MandatoryIntentNotArbitrableError,
    MismatchedTickError,
    UnknownArbitrationItemError,
    UnsupportedConflictPolicyError,
    arbitrate,
    profiles_from_pins,
    resolve_policy,
)
from entropia.domain.backtest.execution.clock import ItemBarStream, iter_ticks
from entropia.domain.backtest.execution.intents import (
    ItemDecision,
    ItemIdentity,
    ItemIntent,
    PortfolioSnapshot,
    ScaleSizing,
    form_intent,
    form_intents,
    form_mandatory_intent,
    idle_decision,
)
from entropia.domain.backtest.execution.portfolio_ledger import (
    LEDGER_INSOLVENT,
    SLEEVE_ZERO_CAPACITY,
    PortfolioLedger,
    ledger_for_items,
)
from entropia.domain.backtest.manifest import ENGINE_VERSION

_ZERO = Decimal("0")
_T = 1_700_000_000_000
_BLOCK = CrossItemConflictPolicy.BLOCK_OPPOSITE.value
_KEEP = CrossItemConflictPolicy.KEEP_SEPARATE.value
_NET = "NET"  # the REMOVED token, kept as a literal: it is no longer an enum member


# ---------------------------------------------------------------------------- fixtures


def _ledger(
    *,
    pool: str = "10000",
    reserve: str = "0",
    shares: dict[str, str] | None = None,
    compound: bool = True,
) -> PortfolioLedger:
    return ledger_for_items(
        pool_initial=Decimal(pool),
        reserve_percent=Decimal(reserve),
        shares={k: Decimal(v) for k, v in (shares or {"item_a": "50", "item_b": "50"}).items()},
        compound=compound,
    )


def _profiles(
    *pins: tuple[str, str | None],
) -> Mapping[str, ItemArbitrationProfile]:
    """Profiles in manifest pin order — the ordinal is the INDEX, never supplied."""
    return profiles_from_pins(pins or (("item_a", "BTCUSDT"), ("item_b", "BTCUSDT")))


def _intent(
    item_id: str,
    *,
    snapshot: PortfolioSnapshot,
    pin_ordinal: int,
    kind: str = "entry",
    direction: str | None = "long",
    units: str = "50",
    price: str = "100",
    reason: str = "entry_signal",
    phase: str = "P4",
) -> ItemIntent:
    """A P4 intent as ``form_intent`` builds one — same fields, same dependency keys.

    Constructed directly so a conflict fixture does not have to carry a whole
    ``StrategyConfig``; ``test_it_arbitrates_what_form_intents_actually_produces`` runs the
    real former end to end so this shortcut cannot drift from the shape it stands in for."""
    return ItemIntent(
        identity=ItemIdentity(
            item_id=item_id,
            item_kind="strategy",
            pin_ordinal=pin_ordinal,
            root_id=f"root_{item_id}",
            selected_revision_id=f"rev_{item_id}",
        ),
        t_ms=snapshot.t_ms,
        phase=phase,  # type: ignore[arg-type]
        kind=kind,  # type: ignore[arg-type]
        direction=direction,
        desired_size=Decimal(units),
        reference_price=Decimal(price),
        effective_price=Decimal(price),
        price_authority="fresh_bar_close",
        reason=reason,
        contract_version="item-intent-v1",
        evidence={},
        dependencies={
            "snapshot_identity": snapshot.identity,
            "snapshot_t_ms": snapshot.t_ms,
        },
        diagnostics={"pin_ordinal": pin_ordinal},
    )


_BAR_TS = "2023-11-14T22:13:20Z"
"""The ISO spelling of ``_T`` — the clock's ``tick_key`` maps one to the other, and the
interop tests below rely on the two agreeing."""


def _row(ts: str = _BAR_TS, close: str = "100") -> dict[str, Decimal | str]:
    """A raw OHLCV row in the shape ``state._normalize`` accepts — a row missing a price is
    DROPPED there, so a short-hand dict would silently produce an empty axis."""
    price = Decimal(close)
    return {
        "timestamp": ts,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": Decimal("1"),
    }


def _stream(item_id: str, pin_ordinal: int) -> ItemBarStream:
    return ItemBarStream(item_id=item_id, pin_ordinal=pin_ordinal, batches=[[_row()]])


# ------------------------------------------------------------------ the policy table / NET


def test_the_policy_table_covers_every_shipped_conflict_policy() -> None:
    """One table, keyed by the canonical wire token, so no call site re-derives a policy's
    behaviour from a string comparison. A policy added to the enum without a row here would
    reach ``resolve_policy`` and be refused — which is the right failure, but the table is
    what makes it visible."""
    assert set(CONFLICT_POLICY_TABLE) == {p.value for p in CrossItemConflictPolicy}
    for token, rule in CONFLICT_POLICY_TABLE.items():
        assert rule.policy == token
        # The policy governs POSITIONS. No row hands an item a private wallet.
        assert rule.shares_capital is True
        assert rule.separate_position_books is True


def test_net_is_gone_from_the_enum_and_from_the_table_and_is_refused_as_unknown() -> None:
    """G14 decision ``B`` (GH #544, migration 0044) removed the value rather than defining it.

    Three axes, because a partial removal is the failure mode this pins. The ENUM must not
    offer it (nothing can select it), the TABLE must not carry a row for it (nothing can
    execute it), and ``resolve_policy`` must still REFUSE the literal token — an already
    pinned manifest is a historical record and could carry the string even though no new
    plan can. The refusal moved from the ``supported=False`` branch to the unknown-token
    branch; both raise the same error, so what changed is the message, never the outcome."""
    assert "NET" not in {p.value for p in CrossItemConflictPolicy}
    assert _NET not in CONFLICT_POLICY_TABLE

    with pytest.raises(UnsupportedConflictPolicyError) as excinfo:
        resolve_policy(_NET)
    message = str(excinfo.value)
    assert _NET in message
    # It names what CAN be chosen. A refusal that lists nothing leaves the operator stuck.
    assert _KEEP in message and _BLOCK in message

    # And it is refused BEFORE any decision exists — never a report full of blocks that
    # someone could read as "NET ran and blocked everything".
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    with pytest.raises(UnsupportedConflictPolicyError):
        arbitrate(
            ledger=ledger,
            snapshot=snapshot,
            intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0)],
            profiles=_profiles(),
            policy=_NET,
        )


def test_the_unsupported_row_branch_still_guards_a_policy_that_does_not_execute() -> None:
    """No shipped row is ``supported=False`` now that NET is gone, so this branch guards a
    row that does not yet exist. Deleting it because it is unreachable would turn a
    fail-closed guard into a fail-open one: a future policy added with ``supported=False``
    would execute silently. Exercised against a table this test builds itself."""
    unsupported = ConflictPolicyRule(
        policy="FUTURE_POLICY",
        supported=False,
        opposite_same_instrument="undefined",
        same_direction_same_instrument="undefined",
        separate_position_books=True,
        shares_capital=True,
        canon="test-only row",
        undefined_semantics=("what it does",),
    )
    # The shipped table is a MappingProxyType on purpose, so the module attribute is
    # swapped rather than mutated -- the immutability itself is part of what ships.
    widened = MappingProxyType({**CONFLICT_POLICY_TABLE, "FUTURE_POLICY": unsupported})
    with (
        patch.object(arbitration, "CONFLICT_POLICY_TABLE", widened),
        pytest.raises(UnsupportedConflictPolicyError) as excinfo,
    ):
        resolve_policy("FUTURE_POLICY")
    message = str(excinfo.value)
    assert "FUTURE_POLICY" in message
    assert "what it does" in message
    assert _KEEP in message and _BLOCK in message


def test_an_unknown_policy_token_is_refused_rather_than_failed_closed_to_blocking() -> None:
    """The shipped gate fails an unknown token closed *to blocking* (``engine.py:866-871``),
    which executes a policy nobody can name. Refusing produces no Result at all, which is
    strictly safer — nothing is published under a label that does not describe it."""
    with pytest.raises(UnsupportedConflictPolicyError) as excinfo:
        resolve_policy("HEDGE_EVERYTHING")
    assert "HEDGE_EVERYTHING" in str(excinfo.value)


def test_an_absent_policy_is_keep_separate_exactly_as_the_shipped_resolver_reads_it() -> None:
    """``engine.resolve_portfolio_rules`` returns ``None`` for an unset or explicit
    KEEP_SEPARATE policy — the pre-rules behaviour. Same reading here, and case/whitespace
    tolerant because the token arrives from a pinned JSON snapshot."""
    for token in (None, "", "   ", "keep_separate", " Keep_Separate "):
        assert resolve_policy(token).policy == _KEEP


# ----------------------------------------------------------------------- KEEP_SEPARATE


def test_keep_separate_admits_opposing_entries_on_the_same_instrument() -> None:
    """The pre-rules behaviour: no cross-item position constraint. Both items open, each in
    its own book — the ledger keys positions by ``item_id``, so separateness is structural."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
            _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="short"),
        ],
        profiles=_profiles(),
        policy=_KEEP,
    )
    assert [d.outcome for d in report.decisions] == ["admitted", "admitted"]
    assert report.refused == ()


def test_keep_separate_still_meets_the_sleeve_the_exposure_cap_and_solvency() -> None:
    """*"only the position books are separate"* — a separate book is not a separate pool. Modül 11
    §6.1's cap layers are not a function of the conflict policy, so KEEP_SEPARATE must clamp
    exactly where BLOCK_OPPOSITE would."""
    ledger = _ledger(shares={"item_a": "50", "item_b": "50"})
    snapshot = ledger.publish_snapshot(_T)
    # A0 = 10000, Ci = 5000 each. item_a takes its whole sleeve (5000); the composition-wide
    # cap of 6000 then leaves item_b 1000 -> 10 units at 100.
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
            _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="short"),
        ],
        profiles=_profiles(),
        policy=_KEEP,
        max_total_exposure_notional=Decimal("6000"),
    )
    first, second = report.decisions
    assert (first.outcome, first.granted_notional) == ("admitted", Decimal("5000.00"))
    assert second.outcome == "capped"
    assert second.binding_constraint == EXPOSURE_CONSTRAINT
    assert second.granted_units == Decimal("10")
    assert report.committed_notional == Decimal("6000.00")


# ---------------------------------------------------------------------- BLOCK_OPPOSITE


def test_two_opposing_intents_at_one_tick_resolve_by_the_pinned_tie_break() -> None:
    """ADR §4.4: ``(pin_ordinal, item_id)``. Exactly one side gives way, the loser is a
    function of the manifest, and the block carries the counterparty and how the tie broke —
    a rejection with no attributable cause is not a decision trace."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
            _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="short"),
        ],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    winner, loser = report.decisions
    assert winner.outcome == "admitted"
    assert loser.outcome == "blocked"
    assert loser.reason == PORTFOLIO_CONFLICT_BLOCKED
    assert loser.counterparty_item_id == "item_a"
    assert loser.conflict_source == "same_tick_intent"
    assert loser.diagnostics["resolved_by"] == "pin_order_tie_break"
    assert loser.granted_units == _ZERO


def test_a_held_position_never_gives_way_even_to_an_earlier_pinned_item() -> None:
    """The shipped rule is forward-only — an EARLIER-pinned holder blocks a LATER-pinned
    entry — because the sequential loop cannot see a later item's position at all. A merged
    axis can, and the pin-order half of that sentence is an artifact of the old loop. What
    canon states is that conflict rules limit two items OPENING opposing positions (Modül 11
    §6.3), and doc 13 §8.3 forbids force-rebalancing an open one. So the holder wins here
    even though it is pinned LAST."""
    ledger = _ledger()
    ledger.set_position("item_b", direction="short", size=Decimal("10"), entry_price=Decimal("100"))
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long")],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    blocked = report.by_item("item_a")
    assert blocked.outcome == "blocked"
    assert blocked.counterparty_item_id == "item_b"
    assert blocked.conflict_source == "held_position"
    assert blocked.diagnostics["resolved_by"] == "held_position_precedence"


@pytest.mark.parametrize("opened_first", ["item_b", "item_c"])
def test_the_reported_counterparty_is_the_lowest_pinned_holder_not_the_first_opened(
    opened_first: str,
) -> None:
    """``ledger.positions`` is a dict, and its insertion order is *when each position happened
    to be opened during the replay* — deterministic, but not the manifest. With two opposing
    holders the block would otherwise name whichever traded first. ADR §4.4 forbids letting
    dict iteration decide an outcome, and the attributed counterparty IS an outcome: it is
    what the decision trace blames."""
    profiles = _profiles(("item_a", "BTCUSDT"), ("item_b", "BTCUSDT"), ("item_c", "BTCUSDT"))
    ledger = _ledger(shares={"item_a": "30", "item_b": "30", "item_c": "30"})
    order = [opened_first, "item_c" if opened_first == "item_b" else "item_b"]
    for item_id in order:
        ledger.set_position(
            item_id, direction="short", size=Decimal("5"), entry_price=Decimal("100")
        )
    assert list(ledger.positions) == order  # the dict really does carry the opening order
    snapshot = ledger.publish_snapshot(_T)

    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long")],
        profiles=profiles,
        policy=_BLOCK,
    )
    blocked = report.by_item("item_a")
    assert blocked.outcome == "blocked"
    assert blocked.counterparty_item_id == "item_b"  # pin 1, whichever opened first


def test_same_direction_on_the_same_instrument_is_never_a_conflict() -> None:
    """BLOCK_OPPOSITE blocks the OPPOSITE. Two items agreeing on a direction is concentration
    — a capacity question for the sleeve and exposure layers, never a conflict.

    ``item_b`` already holds 1000 of its 5000 sleeve, so its scale layer is CAPPED to the
    4000 that is left. A cap is an admission at a smaller size; the point of the test is that
    nothing is BLOCKED and no reason mentions a conflict."""
    ledger = _ledger()
    ledger.set_position("item_b", direction="long", size=Decimal("10"), entry_price=Decimal("100"))
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
            _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="long", kind="scale_in"),
        ],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    assert [d.outcome for d in report.decisions] == ["admitted", "capped"]
    assert all(d.is_admitted for d in report.decisions)
    assert all(d.conflict_source is None for d in report.decisions)
    scaled = report.by_item("item_b")
    assert scaled.binding_constraint == SLEEVE_CONSTRAINT
    assert scaled.granted_units == Decimal("40")  # (5000 - 1000) / 100


def test_two_different_instruments_cannot_conflict() -> None:
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
            _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="short"),
        ],
        profiles=_profiles(("item_a", "BTCUSDT"), ("item_b", "ETHUSDT")),
        policy=_BLOCK,
    )
    assert [d.outcome for d in report.decisions] == ["admitted", "admitted"]


def test_an_unknown_instrument_identity_fails_closed_to_a_conflict() -> None:
    """Verbatim the shipped reading (``execution/rules.py::conflicts_with_prior``): an
    unnameable instrument can never RULE a conflict OUT. The finding stays
    ``portfolio_conflict_blocked``; the fail-closed route is recorded as the shipped L4 gate
    token in the diagnostics rather than as a second reason for one thing."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
            _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="short"),
        ],
        profiles=_profiles(("item_a", "BTCUSDT"), ("item_b", None)),
        policy=_BLOCK,
    )
    loser = report.by_item("item_b")
    assert loser.outcome == "blocked"
    assert loser.reason == PORTFOLIO_CONFLICT_BLOCKED
    assert loser.diagnostics["gate"] == CONFLICT_SYMBOL_UNKNOWN_GATE


# -------------------------------------------------------------- order and determinism


@pytest.mark.parametrize("order", [(0, 1, 2), (2, 1, 0), (1, 2, 0)])
def test_the_caller_s_input_order_cannot_change_any_outcome(order: tuple[int, ...]) -> None:
    """doc 13 §13 / ADR A4: not DOM order, not API arrival order, not DB iteration order. The
    report is ordered by the PINNED profile, so all three permutations produce the identical
    decision tuple *and* the identical digest."""
    profiles = _profiles(("item_a", "BTCUSDT"), ("item_b", "BTCUSDT"), ("item_c", "ETHUSDT"))
    ledger = _ledger(shares={"item_a": "40", "item_b": "35", "item_c": "15"})
    snapshot = ledger.publish_snapshot(_T)
    built = [
        _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
        _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="short"),
        _intent("item_c", snapshot=snapshot, pin_ordinal=2, direction="short"),
    ]
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[built[i] for i in order],
        profiles=profiles,
        policy=_BLOCK,
    )
    assert [d.item_id for d in report.decisions] == ["item_a", "item_b", "item_c"]
    # doc 13 §14 test 10's shares: Ci = 4000 / 3500 / 1500 against A0 = 10000, so the 5000
    # requests are capped by their sleeves — and item_b is blocked before capacity is asked.
    assert [d.outcome for d in report.decisions] == ["capped", "blocked", "capped"]
    assert report.identity == _REFERENCE_IDENTITY


def _reference_identity() -> str:
    profiles = _profiles(("item_a", "BTCUSDT"), ("item_b", "BTCUSDT"), ("item_c", "ETHUSDT"))
    ledger = _ledger(shares={"item_a": "40", "item_b": "35", "item_c": "15"})
    snapshot = ledger.publish_snapshot(_T)
    return arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
            _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="short"),
            _intent("item_c", snapshot=snapshot, pin_ordinal=2, direction="short"),
        ],
        profiles=profiles,
        policy=_BLOCK,
    ).identity


_REFERENCE_IDENTITY = _reference_identity()


def test_the_report_identity_moves_when_an_outcome_moves() -> None:
    """A digest that did not distinguish outcomes would make "replayable" unfalsifiable."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    intents = [
        _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
        _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="short"),
    ]
    blocked = arbitrate(
        ledger=ledger, snapshot=snapshot, intents=intents, profiles=_profiles(), policy=_BLOCK
    )
    separate = arbitrate(
        ledger=ledger, snapshot=snapshot, intents=intents, profiles=_profiles(), policy=_KEEP
    )
    assert blocked.identity != separate.identity
    assert len(blocked.identity) == 64
    assert blocked.policy_version == ARBITRATION_POLICY_VERSION


def test_priority_comes_from_the_pinned_manifest_and_not_from_the_intent() -> None:
    """``profiles_from_pins`` derives the ordinal from the pin INDEX, so it cannot be
    supplied. A profile and an intent that disagree about the ordinal are refused rather than
    silently resolved to one of them: a plan re-ordered after the run must not be able to
    change how an old Result's conflicts were decided (doc 13 §11.1)."""
    profiles = _profiles()
    assert profiles["item_a"].pin_ordinal == 0
    assert profiles["item_b"].pin_ordinal == 1
    assert profiles["item_b"].priority == (1, "item_b")

    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    with pytest.raises(UnknownArbitrationItemError):
        arbitrate(
            ledger=ledger,
            snapshot=snapshot,
            intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=7)],
            profiles=profiles,
            policy=_BLOCK,
        )


def test_an_item_with_no_pinned_profile_is_refused() -> None:
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    with pytest.raises(UnknownArbitrationItemError):
        arbitrate(
            ledger=ledger,
            snapshot=snapshot,
            intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0)],
            profiles=_profiles(("item_b", "BTCUSDT")),
            policy=_BLOCK,
        )


# --------------------------------------------------------------- capacity contention


def test_jointly_insolvent_orders_are_admitted_in_pin_order_and_the_rest_rejected_whole() -> None:
    """The OD-3 case, and the one thing a per-item capacity question structurally cannot see.

    Fixed mode, ``P0=10000``, ``r=0`` -> ``Ci_fixed = 5000`` each. A 4000 loss drops ``E(t)``
    to 6000, so ``A(t)`` is 6000 while the sleeves stay at 5000 (*"Ci_fixed zamanla
    degismez"*). Each 50-unit order at 100 is 5000 — individually inside its sleeve AND
    inside the pool's 6000, but 10000 together.

    The ledger's own ``resolve_capacity`` admits BOTH, because the frozen ledger reads the
    same 6000 for each. The tick-level tally is what refuses the second, and it refuses it
    WHOLE: Modül 11 §5.3 forbids a partial fill and a silent borrow, so "1000 is left, take
    1000" is not an available answer."""
    ledger = _ledger(compound=False)
    ledger.book_trade("item_a", gross_pnl=Decimal("-4000"))
    assert ledger.equity == Decimal("6000.00")
    snapshot = ledger.publish_snapshot(_T)
    assert snapshot.sleeve_capacity["item_b"] == Decimal("5000")

    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
            _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="long"),
        ],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    first, second = report.decisions
    assert (first.outcome, first.granted_notional) == ("admitted", Decimal("5000.00"))
    assert second.outcome == "rejected"
    assert second.reason == LEDGER_INSOLVENT
    assert second.binding_constraint == SOLVENCY_CONSTRAINT
    assert second.granted_units == _ZERO  # never trimmed to the 1000 that was left
    assert second.granted_notional == _ZERO
    assert second.diagnostics["contended"] is True
    assert second.diagnostics["tick_committed_before"] == Decimal("5000.00")
    assert second.limits[SOLVENCY_CONSTRAINT] == Decimal("1000.00")
    assert report.committed_notional == Decimal("5000.00")
    assert report.selection_policy == CONTENTION_SELECTION_POLICY
    assert report.selection_status == CONTENTION_SELECTION_STATUS


def test_the_ledger_alone_would_have_admitted_both_of_those_orders() -> None:
    """The counter-check for the test above: without the tick-level tally, the pool is
    handed out twice. If ``resolve_capacity`` ever grew cross-item state of its own this
    test would fail and the arbitration layer's reason for existing would need re-stating."""
    ledger = _ledger(compound=False)
    ledger.book_trade("item_a", gross_pnl=Decimal("-4000"))
    snapshot = ledger.publish_snapshot(_T)
    for item_id in ("item_a", "item_b"):
        decision = ledger.resolve_capacity(
            item_id=item_id,
            snapshot=snapshot,
            requested_units=Decimal("50"),
            price=Decimal("100"),
        )
        assert decision.outcome == "admitted"
        assert decision.granted_notional == Decimal("5000.00")


def test_a_cap_layer_clamps_where_solvency_would_reject() -> None:
    """doc 13 §14 test 13 — the cap layers produce a deterministic *cap or reject*, and a
    ``capped`` outcome is a smaller ADMITTED size, not a partially filled order. Only
    solvency is forbidden from trimming."""
    ledger = _ledger(shares={"item_a": "20", "item_b": "20"})
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0)],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    capped = report.by_item("item_a")
    assert capped.outcome == "capped"  # Ci = 10000 * 20% = 2000 -> 20 units at 100
    assert capped.binding_constraint == SLEEVE_CONSTRAINT
    assert capped.granted_units == Decimal("20")
    assert capped.granted_notional == Decimal("2000.00")
    assert capped.is_admitted is True


def test_allocation_never_relaxes_an_item_risk_limit() -> None:
    """Modül 11 §6.1 layer 3: the Strategy-Details limit is the item's own authority. A big
    sleeve does not widen it — the ``min`` runs over every layer, and the tightest binds."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0)],
        profiles=_profiles(),
        policy=_BLOCK,
        max_position_notional={"item_a": Decimal("1000")},
    )
    capped = report.by_item("item_a")
    assert capped.outcome == "capped"
    assert capped.binding_constraint == MAX_POSITION_CONSTRAINT
    assert capped.granted_units == Decimal("10")


def test_a_zero_sleeve_is_rejected_rather_than_admitted_at_size_zero() -> None:
    """An item with no active entry carries share 0 — a real, zero-capacity sleeve. A
    0-size "admission" would read as a trade that happened."""
    ledger = _ledger(shares={"item_a": "0", "item_b": "50"})
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0)],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    refused = report.by_item("item_a")
    assert refused.outcome == "rejected"
    assert refused.reason == SLEEVE_ZERO_CAPACITY
    assert refused.binding_constraint == SLEEVE_CONSTRAINT


def test_fees_booked_before_the_valuation_point_shrink_what_the_next_item_may_deploy() -> None:
    """``E(t) = P0 + realized - fees - funding - other`` (doc 13 §8.3) feeds ``A(t)`` feeds
    ``Ci(t)`` feeds the grant. Under compound mode a fee is therefore visible in a SIBLING's
    capacity at the same tick — the single fact the per-item ledgers could never carry."""
    clean = _ledger()
    clean_snapshot = clean.publish_snapshot(_T)
    charged = _ledger()
    charged.book_fee("item_a", amount=Decimal("4000"))
    charged_snapshot = charged.publish_snapshot(_T)
    assert charged.equity == Decimal("6000.00")
    assert charged.accounting_identity == charged.equity

    def grant(ledger: PortfolioLedger, snapshot: PortfolioSnapshot) -> Decimal:
        report = arbitrate(
            ledger=ledger,
            snapshot=snapshot,
            intents=[_intent("item_b", snapshot=snapshot, pin_ordinal=1)],
            profiles=_profiles(),
            policy=_BLOCK,
        )
        return report.by_item("item_b").granted_units

    assert grant(clean, clean_snapshot) == Decimal("50")  # Ci = 5000 -> the whole 50 units
    assert grant(charged, charged_snapshot) == Decimal("30")  # Ci = 3000 -> 30 units


def test_a_blocked_items_capacity_is_never_handed_to_a_sibling() -> None:
    """doc 13 §8.4 step 6, §13, Modül 11 §6.3 — a blocked item's share is never re-routed to
    another item inside the run (a blocked item's share is not re-routed).

    Checked the only way that means anything: the surviving item's grant is identical whether
    the blocked item was in the tick at all. An implementation that recycled the loser's
    sleeve would make the first number larger."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    with_conflict = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
            _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="short"),
        ],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    alone = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long")],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    assert with_conflict.by_item("item_a").granted_units == alone.by_item("item_a").granted_units
    assert with_conflict.by_item("item_a").granted_notional == Decimal("5000.00")
    # The blocked item's own sleeve is untouched in the published valuation, too.
    assert snapshot.sleeve_capacity["item_b"] == Decimal("5000")
    assert with_conflict.released_capacity_reallocated is False
    assert with_conflict.by_item("item_b").diagnostics["share_transferred"] is False


# ------------------------------------------------------- mandatory events and phase order


def test_a_mandatory_p3_intent_is_never_offered_to_arbitration() -> None:
    """ADR §6 rule 4 / Modül 11 §5.2: stops, exits, funding and fees resolve BEFORE the
    valuation point, so by P5 they are already in the ledger. Arbitrating one would either
    apply it twice or let a sibling veto a protective exit — an outcome canon never offers."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    stub = _intent("item_a", snapshot=snapshot, pin_ordinal=0)
    # Both halves are refused, not just the phase tag: a hand-built intent could carry a P4
    # phase with a mandatory kind, and an exit that reached P5 would be conflict-checked and
    # re-sized as if it were discretionary.
    for mandatory in (
        replace(stub, phase="P3", kind="exit", reason="stop_loss"),
        replace(stub, phase="P4", kind="partial_exit", reason="exit_signal"),
    ):
        with pytest.raises(MandatoryIntentNotArbitrableError):
            arbitrate(
                ledger=ledger,
                snapshot=snapshot,
                intents=[mandatory],
                profiles=_profiles(),
                policy=_BLOCK,
            )


def test_a_stop_that_fired_at_this_tick_frees_the_instrument_for_the_opposing_item() -> None:
    """The phase order is the whole point: P3 closes the position, THEN ``PV`` publishes, THEN
    P5 arbitrates against a ledger that no longer holds it. The sibling's opposing entry is
    admitted — not because arbitration made an exception, but because there is nothing left
    to conflict with."""
    ledger = _ledger()
    ledger.set_position("item_b", direction="short", size=Decimal("10"), entry_price=Decimal("100"))
    # P3: the stop fires and the position is released before the valuation point.
    ledger.close_position("item_b")
    ledger.book_trade("item_b", gross_pnl=Decimal("-100"), commission=Decimal("1"))
    snapshot = ledger.publish_snapshot(_T)

    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long")],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    admitted = report.by_item("item_a")
    assert admitted.is_admitted is True
    assert admitted.outcome != "blocked"
    assert admitted.conflict_source is None
    # The stop's loss is already inside E(t), so the sleeve it sizes against is the
    # post-stop one — 4949.50, not the pre-stop 5000.
    assert admitted.granted_notional == Decimal("4949.50")


def test_arbitration_refuses_to_run_against_a_writable_ledger() -> None:
    """P5/P6b sit between ``PV`` and ``P7`` (ADR §8.1). Against a writable ledger a sibling's
    booking could move ``E(t)``, the sleeve headroom and the solvency headroom under the items
    still being arbitrated — the per-item drift the unified clock exists to remove."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    ledger.begin_apply(_T)
    assert ledger.is_frozen is False
    with pytest.raises(LedgerNotFrozenError):
        arbitrate(
            ledger=ledger,
            snapshot=snapshot,
            intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0)],
            profiles=_profiles(),
            policy=_BLOCK,
        )


def test_arbitration_writes_nothing() -> None:
    """It is a decision layer. Every ledger write belongs to P7-P9."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    before = (ledger.equity, dict(ledger.positions), len(ledger.equity_points), ledger.fees)
    arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
            _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="short"),
        ],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    assert (ledger.equity, dict(ledger.positions), len(ledger.equity_points), ledger.fees) == before


def test_an_intent_from_another_valuation_point_is_refused() -> None:
    """One tick, one snapshot, one ``E(t)``. Arbitrating an intent formed against a different
    valuation would decide half the tick from one snapshot and half from another."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    other = ledger.publish_snapshot(_T + 60_000)
    with pytest.raises(MismatchedTickError):
        arbitrate(
            ledger=ledger,
            snapshot=snapshot,
            intents=[_intent("item_a", snapshot=other, pin_ordinal=0)],
            profiles=_profiles(),
            policy=_BLOCK,
        )


def test_two_intents_for_one_item_at_one_tick_are_refused() -> None:
    """The engine keeps ONE position per item (``engine.py:1146``); a second intent would be
    arbitrated against its own twin."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    intent = _intent("item_a", snapshot=snapshot, pin_ordinal=0)
    with pytest.raises(DuplicateIntentError):
        arbitrate(
            ledger=ledger,
            snapshot=snapshot,
            intents=[intent, intent],
            profiles=_profiles(),
            policy=_BLOCK,
        )


# --------------------------------------------------------------- trace completeness


def test_nothing_is_dropped_and_every_reason_is_a_token_the_engine_already_speaks() -> None:
    """ADR §6 rule 5 and this layer's own promise: exactly one decision per intent, and NO new
    vocabulary. A cross-item block reads the engine's own ``portfolio_conflict_blocked``;
    every capacity refusal reads the ledger's own token.

    ``item_c`` carries share 0, so this one tick produces all three shapes at once: ``item_a``
    admitted, ``item_b`` blocked by the conflict, ``item_c`` rejected for a zero sleeve."""
    ledger = _ledger(shares={"item_a": "50", "item_b": "50", "item_c": "0"})
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent("item_a", snapshot=snapshot, pin_ordinal=0, direction="long"),
            _intent("item_b", snapshot=snapshot, pin_ordinal=1, direction="short"),
            _intent("item_c", snapshot=snapshot, pin_ordinal=2, direction="long"),
        ],
        profiles=_profiles(("item_a", "BTCUSDT"), ("item_b", "BTCUSDT"), ("item_c", "BTCUSDT")),
        policy=_BLOCK,
    )
    assert len(report.decisions) == 3
    assert {d.outcome for d in report.decisions} == {"admitted", "blocked", "rejected"}
    for decision in report.refused:
        assert decision.reason in ARBITRATION_REASONS
    assert report.admitted + report.refused == report.decisions


def test_a_non_actionable_intent_is_recorded_with_its_own_reason() -> None:
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[
            _intent(
                "item_a",
                snapshot=snapshot,
                pin_ordinal=0,
                kind="no_op",
                direction=None,
                units="0",
                reason="no_bar_at_tick",
            )
        ],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    idle = report.by_item("item_a")
    assert idle.outcome == "not_actionable"
    assert idle.reason == "no_bar_at_tick"
    assert idle.granted_units == _ZERO
    assert report.refused == ()  # a non-decision is not a refusal


# ------------------------------------------------------------------------ interop


def test_it_arbitrates_what_form_intents_actually_produces() -> None:
    """End to end over the real layers: the ADIM 15 clock builds the tick, the ADIM 17 ledger
    publishes the one snapshot, the ADIM 16 former builds the intents and this module
    arbitrates them. The hand-built ``_intent`` fixture above is a shortcut; this is the
    proof it stands in for the real shape."""
    streams = [_stream("item_a", 0), _stream("item_b", 1)]
    ticks = list(iter_ticks(streams))
    assert len(ticks) == 1
    tick = ticks[0]

    ledger = _ledger()
    ledger.set_position("item_a", direction="long", size=Decimal("10"), entry_price=Decimal("100"))
    snapshot = ledger.publish_snapshot(tick.t_ms)

    identities = {
        view.item_id: ItemIdentity(
            item_id=view.item_id,
            item_kind="strategy",
            pin_ordinal=view.pin_ordinal,
            root_id=f"root_{view.item_id}",
            selected_revision_id=f"rev_{view.item_id}",
        )
        for view in tick.views
    }
    scale = form_intent(
        identity=identities["item_b"],
        view=next(v for v in tick.views if v.item_id == "item_b"),
        snapshot=snapshot,
        decision=ItemDecision(kind="scale_in", direction="short", reason="scale_signal"),
        sizing=ScaleSizing(
            basis="fixed_amount",
            value=Decimal("5"),
            initial_size=Decimal("5"),
            current_size=Decimal("5"),
        ),
    )
    idle = form_intent(
        identity=identities["item_a"],
        view=next(v for v in tick.views if v.item_id == "item_a"),
        snapshot=snapshot,
        decision=idle_decision(
            identities["item_a"], next(v for v in tick.views if v.item_id == "item_a")
        ),
    )
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[scale, idle],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    assert report.t_ms == tick.t_ms
    assert report.snapshot_identity == snapshot.identity
    # item_a holds the long and wants nothing; item_b's opposing scale is blocked by it.
    assert report.by_item("item_a").outcome == "not_actionable"
    blocked = report.by_item("item_b")
    assert blocked.outcome == "blocked"
    assert blocked.counterparty_item_id == "item_a"
    assert blocked.conflict_source == "held_position"


def test_form_intents_and_arbitrate_agree_on_the_pinned_order() -> None:
    """Both layers order by ``(pin_ordinal, item_id)`` read off the pinned axis, so a tick's
    intents and its decisions line up item for item without either side re-sorting."""
    streams = [_stream("item_b", 1), _stream("item_a", 0)]
    tick = next(iter(iter_ticks(streams)))
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(tick.t_ms)
    identities = {
        view.item_id: ItemIdentity(
            item_id=view.item_id, item_kind="strategy", pin_ordinal=view.pin_ordinal
        )
        for view in tick.views
    }
    intents = form_intents(tick, snapshot, identities, {})
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=intents,
        profiles=_profiles(),
        policy=_BLOCK,
    )
    assert [i.item_id for i in intents] == ["item_a", "item_b"]
    assert [d.item_id for d in report.decisions] == ["item_a", "item_b"]


def test_a_p3_intent_built_by_the_real_former_is_still_refused() -> None:
    """``form_mandatory_intent`` is the only way a P3 intent is meant to exist, and it is
    exactly the one arbitration must not accept."""
    tick = next(iter(iter_ticks([_stream("item_a", 0)])))
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(tick.t_ms)
    from entropia.domain.backtest.execution.intents import ClosingSize

    mandatory = form_mandatory_intent(
        identity=ItemIdentity(item_id="item_a", item_kind="strategy", pin_ordinal=0),
        view=tick.views[0],
        decision=ItemDecision(kind="exit", direction="long", reason="stop_loss"),
        sizing=ClosingSize(units=Decimal("5")),
    )
    assert mandatory.phase == "P3"
    with pytest.raises(MandatoryIntentNotArbitrableError):
        arbitrate(
            ledger=ledger,
            snapshot=snapshot,
            intents=[mandatory],
            profiles=_profiles(),
            policy=_BLOCK,
        )


# ---------------------------------------------------------------------- containment


def _imports_arbitration(source: str) -> bool:
    """Every spelling that would actually import the module."""
    return (
        "execution.arbitration" in source
        or "execution import arbitration" in source
        or "from . import arbitration" in source
    )


def test_the_arbitration_layer_is_reachable_only_through_the_phase_loop() -> None:
    """**ADIM 18 wired the phase loop in, and this is the deliberate update for it.**

    ``domain/backtest/portfolio_engine.py`` calls ``arbitrate`` at P5/P6b against a FROZEN
    ledger, which is the only context in which the answer is meaningful — the layer refuses an
    unfrozen one. It is a production entry point rather than a contained sibling, so "nothing
    in production imports the arbitration layer" is retired here on purpose and replaced by
    the property that has to hold instead: arbitration is reached from the phase loop and
    nowhere else, so nothing can arbitrate outside the P5/P6b window.

    **Widened deliberately at `C3` (E4c), by ONE NAMED module.** ``domain/backtest/participant.py``
    is the engine-backed ``ItemParticipant`` adapter; it names the phase loop's own types in
    its signatures, so it cannot exist without appearing here. It sits OUTSIDE ``execution/``
    on purpose — inside, the containment gate's importer scan would have exempted it and the
    guard would have gone blind rather than satisfied. The widening is a named entry, never a
    wildcard, so a THIRD importer is still a red build. Signed 2026-08-18, Option A:
    ``docs/decisions/closure_participant_importer_allowlist_2026-08-18.md``.

    ``execution/provenance.py`` remains the other named importer (ADIM 19): it pins the
    resolved ``ConflictPolicyRule`` and ``ARBITRATION_POLICY_VERSION`` into the manifest
    section, and is itself still contained — ``test_backtest_portfolio_provenance.py`` asserts
    nothing imports IT.

    ``sorted()``: ``rglob`` yields in filesystem order, which differs between macOS and the
    Linux runner. With one importer that was invisible; with two it makes the assertion
    platform-dependent, exactly as the clock's own guard already records."""
    src = Path(__file__).resolve().parents[2] / "src" / "entropia"
    importers = sorted(
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if path.name != "arbitration.py" and _imports_arbitration(path.read_text(encoding="utf-8"))
    )
    assert importers == [
        "domain/backtest/execution/provenance.py",
        "domain/backtest/participant.py",
        "domain/backtest/portfolio_engine.py",
    ]


def test_the_shipped_sequential_conflict_gate_is_untouched() -> None:
    """This slice adds a module; it does not edit the engine. The sequential gate — including
    its NET downgrade — still reads exactly as it did, so no replay and no digest can move."""
    engine_src = (
        Path(__file__).resolve().parents[2] / "src/entropia/domain/backtest/engine.py"
    ).read_text(encoding="utf-8")
    assert 'led.portfolio_block_reason = "portfolio_conflict_blocked"' in engine_src
    assert 'conflict_downgraded_from_net = policy_token == "NET"' in engine_src


def test_no_arbitration_field_ships_in_the_manifest_yet_and_the_engine_version_stands() -> None:
    """NARROWED at `C7`: ``arbitration_policy_version`` now ships; the BEHAVIOUR does not.

    ADR §10.3 placed the policy version with the ``ENGINE_VERSION`` bump. `C7` shipped both
    — the version as a manifest RECORD (A16), declared as a literal because this layer is
    contained and the manifest must not import it. What still must not appear is
    ``conflict_policy``: that is the arbitration BEHAVIOUR, and a sequential manifest naming
    it would claim a cross-item resolution that did not run. The name is kept because it is
    cited; this docstring carries the correction."""
    manifest_src = (
        Path(__file__).resolve().parents[2] / "src/entropia/domain/backtest/manifest.py"
    ).read_text(encoding="utf-8")
    # Moved at ADIM 20 (`C9`) AS THE ACT OF LIFTING, and moved again by GH #532 — an
    # OUTSIDE bump (the decision-trace taxonomy gained ``entry_exit_collision``), which is
    # the same class as #550/#551/#552 and `C7`'s A16 record change. The literal tracks the
    # CURRENT shipped version; what it pins is that the namespace cannot shift without a
    # human editing this line. The assertion below it has never loosened: the sequential
    # manifest still must not name the portfolio BEHAVIOUR.
    assert ENGINE_VERSION == "backtest-engine-v18-entry-exit-collision-registered"
    # Shipped at `C7` (A16). Parity with this module's own constant is proved in
    # ``tests/unit/test_a16_manifest_policy_parity.py``, which may import both sides.
    for present in ("arbitration_policy_version", "arbitration-policy-v1"):
        assert present in manifest_src, f"{present!r} left the shipped manifest; A16 needs it"
    # The behaviour, still contained.
    assert "conflict_policy" not in manifest_src


def test_the_containment_flag_is_lifted() -> None:
    """Renamed at ADIM 20 from ``..._is_untouched``.

    Its old sentence — *"no slice before the last one lifts containment (ADR §12)"* — was
    true of every slice that came before and is now spent: `C9` IS the last one. The pin is
    kept rather than deleted because this module's arbitration work was written under
    containment, and a reader arriving here needs to know that assumption no longer holds."""
    from entropia.domain.allocation.capability import (
        SHARED_ALLOCATION_STATUS,
        shared_allocation_is_executable,
    )

    assert SHARED_ALLOCATION_STATUS == "active_v1"
    assert shared_allocation_is_executable() is True


def test_the_od3_selection_rule_is_labelled_as_approved() -> None:
    """OD-3 is DECIDED (ADR §13.1, 2026-08-05, option (a)) and at ADIM 20 the LABEL caught up.

    Renamed from ``..._is_labelled_as_pending_approval``, which pinned the LAG. The lag was
    real and deliberate — §13.1 assigned this flip to ADIM 20 so that no label would advertise
    a decision before a manifest carried it — and it ended when the lift landed
    (containment-lift precondition 18).

    **The policy assertion below is the load-bearing one and it did NOT move.** OD-3's flip is
    a disclosure change, not a behaviour change: ``pin_order_admission`` has been the shipped
    rule since ADIM 19. If a future edit ever moves ``CONTENTION_SELECTION_POLICY`` while this
    status still reads ``approved``, that is a silently-adopted resolution — which is the exact
    failure §13.1 wrote the label to prevent."""
    assert CONTENTION_SELECTION_POLICY == "pin_order_admission"
    assert CONTENTION_SELECTION_STATUS == "approved"
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0)],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    assert report.selection_status == "approved"
    assert report.by_item("item_a").diagnostics["selection_policy"] == CONTENTION_SELECTION_POLICY


def test_the_od3_disclosure_does_not_contradict_itself() -> None:
    """One claim, three spellings — and for two of them the answer had gone stale.

    ADR §13.1 (2026-08-05) resolved OD-3 to option (a) and the ADR is Accepted. #852 named
    that in :data:`CONTENTION_SELECTION_STATUS`'s docstring and stopped there, leaving
    :data:`CONTENTION_SELECTION_NOTE` and one test docstring still saying the decision was
    unresolved. Nothing caught it because ``CONTENTION_SELECTION_NOTE`` has no reader — it
    is exported and never consumed, so no behavioural test can reach it, and the constant
    that says the decision is DECIDED sat three lines above the one that said it was not.

    The cost was paid once already: ``closure_c9_containment_lift_verdict_2026-08-26.md``
    quoted this module's pre-#852 wording and recorded OD-3 as open, a condition blocking
    the containment lift. This test is what stops the module contradicting itself again.

    It does NOT assert that the status label has flipped. It has not, and that lag is the
    ADR's own instruction (§13.1 gives the flip to ADIM 20) — pinned by
    ``test_the_od3_selection_rule_is_labelled_as_pending_approval`` right above."""
    note = arbitration.CONTENTION_SELECTION_NOTE
    assert "DECIDED" in note, "the note must not leave OD-3's resolution unnamed"
    assert "§13.1" in note, "the note must cite the resolution it relies on"
    for stale in ("is unresolved", "is open", "under review"):
        assert stale not in note, f"the note still calls OD-3 undecided: {stale!r}"

    # The source-level half. The exported string is one surface; the sentence the
    # 2026-08-26 verdict actually quoted was a DOCSTRING, so the scan has to reach prose
    # that is not this constant.
    #
    # COMMENT LINES ARE EXCLUDED, AND THE EXCLUSION IS THE RULE, NOT A LOOPHOLE. A comment
    # may quote a retired claim in order to record that it was retired — that is how this
    # repo keeps evidence, and deleting the quote would delete the proof. What may never
    # come back is an ASSERTION of it: a docstring or a string literal that states OD-3 is
    # undecided reaches a reader as the module's current answer. Written the naive way this
    # assertion fired on the comment block above, which is the distinction being drawn.
    lines = [
        line
        for line in Path(arbitration.__file__).read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    prose = "\n".join(lines)
    for stale in ("OD-3 is open", "OD-3 (ADR 0002 §13) is unresolved"):
        assert stale not in prose, f"a retired claim came back into the module: {stale!r}"

    # The label itself is deliberately NOT asserted here. It is pinned one test above, and
    # duplicating it would shadow that axis: NC-3 (flip the label) reddened both tests, so
    # these two lines bought no coverage the neighbour did not already own. Removed rather
    # than merely recorded — the docstring above already delegates the claim.


def test_the_report_is_a_value_and_cannot_be_edited_after_the_fact() -> None:
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(_T)
    report = arbitrate(
        ledger=ledger,
        snapshot=snapshot,
        intents=[_intent("item_a", snapshot=snapshot, pin_ordinal=0)],
        profiles=_profiles(),
        policy=_BLOCK,
    )
    decision = report.by_item("item_a")
    with pytest.raises((TypeError, AttributeError)):
        decision.limits["invented"] = Decimal("1")  # type: ignore[index]
    with pytest.raises((TypeError, AttributeError)):
        decision.diagnostics["invented"] = "x"  # type: ignore[index]
    with pytest.raises(UnknownArbitrationItemError):
        report.by_item("item_zzz")


def test_the_module_reads_no_live_registry_and_pins_travel_with_the_report() -> None:
    """A plan edited after the run must not change how an old Result's conflicts were
    resolved (doc 13 §11.1). Everything the module reads is either the frozen ledger, the
    published snapshot, the intent (which names its pinned revision) or the profile map built
    from the manifest pins — there is no composition join anywhere in the signature."""
    import inspect

    from entropia.domain.backtest.execution import arbitration

    source = inspect.getsource(arbitration)
    for forbidden in ("session", "select(", "AsyncSession", "await "):
        assert forbidden not in source
    profiles = profiles_from_pins((("item_a", "BTCUSDT"), ("item_b", None)))
    assert [p.pin_ordinal for p in profiles.values()] == [0, 1]
    assert profiles["item_b"].instrument_id is None
