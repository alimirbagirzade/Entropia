"""The phase loop's INPUT contract — ``run_portfolio``'s per-item maps (ADR 0002 §8).

``run_portfolio`` already refuses a participant the allocation plan carries no share for. The
other per-item map it accepts, ``max_position_notional``, is passed straight through to
``arbitrate``, which reads it with ``.get(item_id)`` — so a key that names nobody is silently
dropped rather than refused.

The two failures are not symmetric, and that asymmetry is why this module exists. A missing
SHARE fails closed: the item has no sleeve and cannot size. A missing item risk LIMIT fails
**open**: the cap simply disappears and the item sizes against its sleeve alone. Modül 11
§6.1 layer 3 puts that limit above the allocation layer precisely so allocation can cap a
size and never relax one, and doc 13 §14 test 13 asks for a *deterministic* cap — a limit
that vanishes on a typo is neither.

No oracle passes ``max_position_notional`` today, so the loop's item-risk-limit layer was
unexercised end to end; the first test here closes that gap before the guard is asserted."""

from __future__ import annotations

from decimal import Decimal

import pytest

from entropia.domain.backtest.execution.portfolio_ledger import MAX_POSITION_CONSTRAINT
from entropia.domain.backtest.portfolio_engine import InvalidParticipantError

from .oracles.portfolio_harness import ScriptedItem, simulate

_HOURS = [f"2024-01-01T{h:02d}:00:00Z" for h in range(4)]
_FLAT = [(h, "100") for h in _HOURS]


def _two_items() -> list[ScriptedItem]:
    """Two items with a 50/50 sleeve; A wants 40 units at 100 = 4000 notional."""
    return [
        ScriptedItem(item_id="a", share="50", bars=_FLAT, entries={_HOURS[0]: ("long", "40")}),
        ScriptedItem(item_id="b", share="50", bars=_FLAT),
    ]


def test_a_per_item_risk_limit_binds_through_the_loop() -> None:
    """The baseline the guard below depends on, and which nothing exercised before.

    P0=10000, r=0 -> A0=10000, so A's 50 % sleeve is 5000 and its 4000 request fits. A 2000
    item risk limit is the tighter layer, so it — not the sleeve — must be what binds."""
    capped = simulate(_two_items(), max_position_notional={"a": "2000"})

    decision = capped.ticks[0].report.by_item("a")
    assert decision.granted_notional == Decimal("2000")
    assert decision.granted_units == Decimal("20")
    assert decision.binding_constraint == MAX_POSITION_CONSTRAINT

    # Without the limit the same request is bound only by the sleeve, so the fixture really
    # does distinguish the two layers rather than reporting a coincidence.
    uncapped = simulate(_two_items())
    assert uncapped.ticks[0].report.by_item("a").granted_notional == Decimal("4000")


def test_a_risk_limit_naming_no_participant_is_refused_rather_than_dropped() -> None:
    """The defect: ``arbitrate`` reads the map with ``.get()``, so ``"itme_a"`` never matches
    and item A runs with NO cap at all — the limit does not fail closed, it disappears.

    Refusing is the only reading that keeps Modül 11 §6.1 layer 3 true. Silently ignoring the
    key trades a typo for an unbounded position, and nothing in the Result would record that
    the configured limit was never applied."""
    with pytest.raises(InvalidParticipantError, match="itme_a"):
        simulate(_two_items(), max_position_notional={"itme_a": "2000"})


def test_a_risk_limit_map_may_still_name_a_subset() -> None:
    """The guard refuses UNKNOWN names, not incomplete ones. An item with no configured limit
    genuinely has none, and that must stay expressible."""
    run = simulate(_two_items(), max_position_notional={"a": "2000"})

    assert run.ticks[0].report.by_item("a").granted_notional == Decimal("2000")
    # Item B configures no limit and forms no intent, so it is simply absent from the tick's
    # arbitration — the guard must not require a limit for every participant.
    assert [d.item_id for d in run.ticks[0].report.decisions] == ["a"]
