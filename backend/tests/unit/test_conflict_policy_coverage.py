"""GH #536 — the conflict options that ship untested (F-5, §3.7 / §3.5).

Three gaps, all about DISCLOSURE rather than behaviour; no production code changes.

**Gap B (``same_candle_entry_exit``).** Five literals ship. Only two were ever driven:
``use_intrabar_data_if_available`` and ``exit_first`` (measured — grepping the suite for
the field returns three hits, all ``exit_first``). The other three
(``stop_first``, ``ignore_trade``, ``conservative_rule``) all suppress the flat-position
entry today, and nothing asserted that. Suppression alone is the weak half of the claim:
a test that only counted trades would keep passing if two policies were silently merged,
so each case also pins that the emitted ``entry_exit_collision`` names ITS OWN policy.
GH #532 registered that event type in the published taxonomy (ADIM 136); these cases are
what make its ``detail["policy"]`` field falsifiable per literal.

**Gap A (``overlapping_signal_policy``).** All four literals produce a byte-identical run.
The engine has no branch on the field: it is read once and echoed into diagnostics
verbatim. The engine's own argument is that this is VACUOUS rather than unimplemented --
at most one aggregated signal exists per evaluation window, so the policy could never bite
(``domain/backtest/engine.py``, the ``overlapping_signal_policy`` note above ``_step``).
That argument lived only in a source comment while the diagnostics echo reads as "this
policy was honoured", and no test pinned either half.

This case turns the undocumented no-op into a DELIBERATE, defended one. It is a tripwire,
not an approval: if the aggregation model ever makes overlapping signals reachable, this
test goes red and forces the disclosure decision (capability row / diagnostics wording)
rather than letting a policy quietly start biting.

**Gap B (``stop_conflict_resolution``).** Four literals ship and the suite drove them --
but only through ``_resolve_stop``, and it never once read back WHICH policy the engine
said had governed. Measured on ``origin/main`` @ ``17bb495f``:
``diagnostics["stop_conflict_resolution"]`` has zero assertions, the ``stop_resolution``
event's ``detail["resolution"]`` has zero, ``detail["requirement"]`` has zero, and
``record_all_execute_highest`` had never reached the engine plane at all.

The issue's own framing of this gap partly rotted before it was worked: it asks for
``most_conservative`` to be set explicitly (two oracle cases already do), for
``stop_priority_order`` to cover ``logic:<block_id>`` entries (ADIM 137 covers that at the
``stop_priority_sequence`` plane) and for ``all_active`` coverage (already asserted through
diagnostics). What survived measurement is the ECHO, on both planes it is published on.

That measurement also turned up a second twin: ``record_all_execute_highest`` and
``priority_order`` share one branch and produce byte-identical runs. It is pinned the same
way Gap A is -- as a deliberate, defended duplicate rather than an accident.

**Gap B (``stop_priority_order`` over a logic block).** ADIM 142 left this as an honest
boundary -- no engine-level logic-stop fixture existed, and building one was judged a
slice of its own. It is built below. The measurement that motivated it: the schema
documents ``logic:<block_id>`` as a valid precedence entry and names a canonical default
("logic blocks in display order, then percentage, trailing, absolute"), and neither had
ever been driven through ``run_engine``. Every ``logic:`` key in the suite was fed to
``_resolve_stop`` directly or handed to ``stop_priority_sequence`` as a literal; the one
engine-plane run that builds a stop plan replays flat bars, so its block never fires.
``logic_stop_triggers`` -- published on every Result and aggregated across a portfolio --
had zero assertions anywhere, because its only writer sits on that unreached path.

**Gap B (the resolution that decides whether the order is read at all).** ADIM 143 drove
the contest only under ``priority_order``. That left the sharper half open: ``most_conservative``
consults ``stop_priority_order`` ONLY to break a distance tie, and ``first_trigger_wins``
never lets a logic block win a tick-resolved bar at all. Both are pinned below and at the
``_resolve_stop`` plane (``test_backtest_logic_stop``), where the measurement was taken:
deleting the conservative tie-break term, or admitting logic stops into the tick candidates,
each leaves the whole unit suite green (2597 passed, ``origin/main`` @ ``c9676816``).

HONEST BOUNDARY: Gap C (md. 4) remains out of scope, and ``record_all_execute_highest``
remains pinned as a twin rather than fixed -- both are decisions, not assertions. The
engine-plane contest below carries no tick path, so ``first_trigger_wins`` is exercised
there only on its OHLCV fallback; its tick-resolved arm is covered at the unit plane.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

import pytest

from entropia.domain.backtest.indicators import IndicatorPlan, IndicatorSpec
from tests.unit.engine_signal_plan import sma_entry_plan
from tests.unit.test_backtest_engine import (
    _config,
    _long_breakout_then_stop,
    _run,
    _same_candle_entry_exit_plan,
)
from tests.unit.test_backtest_policy_provenance import _patched

# The three literals that ship with no dedicated case (measured on origin/main @ 31593c79).
_SUPPRESSING_POLICIES = ["stop_first", "ignore_trade", "conservative_rule"]

_OVERLAPPING_POLICIES = [
    "queue_sequential",
    "cancel_pending",
    "merge_signals",
    "ignore_if_active",
]


def _fingerprint(out: Any) -> str:
    """Hash of everything the run OBSERVABLY produced, minus the policy echo itself.

    ``diagnostics`` is excluded wholesale rather than filtered: the field under test is
    echoed there, so including it would make every value differ trivially and the test
    would pass without measuring anything.
    """
    payload = {
        "summary": out.summary,
        "trades": [t.as_dict() if hasattr(t, "as_dict") else str(t) for t in out.trades],
        "events": [
            (e.event_type, e.seq if hasattr(e, "seq") else None, json.dumps(e.detail, default=str))
            for e in out.signal_events
        ],
        "equity": [str(p) for p in out.equity_points],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


@pytest.mark.parametrize("policy", _SUPPRESSING_POLICIES)
def test_the_untested_same_candle_policies_suppress_the_entry_and_name_themselves(
    policy: str,
) -> None:
    # Same fixture as the two literals the engine suite already drives
    # (``test_same_candle_entry_exit_default_suppresses_ambiguous_flat_entry``): the last
    # bar is dropped so exactly ONE collision bar exists, which is what makes "names its
    # own policy" a statement about a single, identified decision.
    out = _run(
        _config(with_stop=False, same_candle_entry_exit=policy),
        _long_breakout_then_stop()[:-1],
        indicator_plan=_same_candle_entry_exit_plan(),
    )

    # Half 1 -- the behaviour: the flat-position entry is suppressed, so no trade opens.
    assert out.summary["total_trades"] == 0, (
        f"'{policy}' admitted an entry; it is documented as a suppressing policy"
    )

    # Half 2 -- the disclosure: exactly one collision is emitted and it names THIS policy.
    # Without this, a change that collapsed two literals onto one code path would keep
    # half 1 green while the Result could no longer be read back to the chosen option.
    collisions = [e for e in out.signal_events if e.event_type == "entry_exit_collision"]
    assert len(collisions) == 1
    assert collisions[0].detail["policy"] == policy


def test_the_five_same_candle_literals_are_covered_by_a_case_between_them() -> None:
    """Anti-drift: a newly added literal must not arrive with zero cases.

    ``_SUPPRESSING_POLICIES`` plus the two literals the engine suite already drives must
    equal the shipped Literal. A sixth value added to the schema fails here, in the same
    shape as GH #532's source-level guard (a behavioural test cannot see a literal that
    no scenario happens to select).
    """
    from entropia.domain.strategy.config import ConflictPositionHandling

    shipped = set(
        ConflictPositionHandling.model_fields["same_candle_entry_exit"].annotation.__args__
    )
    covered_here = set(_SUPPRESSING_POLICIES)
    covered_elsewhere = {"use_intrabar_data_if_available", "exit_first"}
    assert covered_here | covered_elsewhere == shipped, (
        "a same_candle_entry_exit literal has no case: add one (do not widen this set)"
    )


def test_every_overlapping_signal_policy_produces_an_identical_run() -> None:
    """Gap A: the four literals are equivalent TODAY, and that is deliberate.

    See the module docstring: the vacuity argument is the engine's, and this pins it so a
    future aggregation change cannot make one of these values start biting unannounced.
    """
    fingerprints = {}
    for policy in _OVERLAPPING_POLICIES:
        out = _run(
            _config(overlapping_signal_policy=policy),
            _long_breakout_then_stop(),
        )
        fingerprints[policy] = _fingerprint(out)
        # The echo is the ONLY thing that may differ, and it must be verbatim -- that is
        # what makes the equivalence above readable rather than a silent collapse.
        assert out.diagnostics["overlapping_signal_policy"] == policy

    # Vacuity guard: the run must actually do something, else "identical" is trivially
    # true for four empty runs and this case would measure nothing.
    sample = _run(_config(), _long_breakout_then_stop())
    assert sample.summary["total_trades"] >= 1

    assert len(set(fingerprints.values())) == 1, (
        "overlapping_signal_policy started to bite: "
        f"{ {k: v[:12] for k, v in fingerprints.items()} }. "
        "This is not automatically a bug -- but it is now a DISCLOSURE decision "
        "(capability row + diagnostics wording), see GH #536."
    )


# --------------------------------------------------------------------------- #
# Gap B (2) -- stop_conflict_resolution: the policy that governed, per literal #
# --------------------------------------------------------------------------- #

#: literal -> (executed rule, exit price, ``first_trigger_approximated``).
#: Measured on ``origin/main`` @ ``17bb495f`` with the two-stop fixture below; entry is
#: 102.00, so the percentage stop rests at 100.98 and the absolute stop at 101.50.
_STOP_RESOLUTIONS: dict[str, tuple[str, str, bool]] = {
    # Tightest adverse level wins: |102 - 101.50| beats |102 - 100.98|.
    "most_conservative": ("absolute", "101.50", False),
    # Rank wins over distance: the shipped default order puts percentage first.
    "priority_order": ("percentage", "100.98", False),
    # Byte-identical to priority_order -- see the twin tripwire below.
    "record_all_execute_highest": ("percentage", "100.98", False),
    # No tick path over OHLCV: resolves to the conservative model and FLAGS it (§9.3).
    "first_trigger_wins": ("absolute", "101.50", True),
}


def _two_stop_config(resolution: str) -> Any:
    """The base fixture plus a SECOND, conflicting stop, so the resolution decides.

    ``_config`` exposes only the percentage stop (``loss_pct`` / ``with_stop``); widening
    it for an absolute stop and a resolution would change a fixture eight other modules
    share. ``_patched`` is the idiom that already exists for exactly this
    (``test_backtest_policy_provenance``), so no third way is invented here.
    """
    return _patched(
        _config(),
        {
            "protection_stop_logic": {
                "absolute_stop": {"enabled": True, "absolute_price": "101.50"},
                "stop_conflict_resolution": resolution,
            }
        },
    )


def _stop_fingerprint(out: Any) -> str:
    """Like ``_fingerprint``, but strips the echo from BOTH planes it is published on.

    ``_fingerprint`` cannot be reused here and the difference is load-bearing:
    ``overlapping_signal_policy`` is echoed into ``diagnostics`` only, so excluding
    diagnostics wholesale was enough for Gap A. ``stop_conflict_resolution`` is ALSO
    stamped into every ``stop_resolution`` event as ``detail["resolution"]``, which
    ``_fingerprint`` hashes. Reusing it would report four distinct runs for four literals
    no matter what the engine did -- a tripwire that can never fire.
    """
    events = [
        (
            e.event_type,
            json.dumps(
                {k: v for k, v in e.detail.items() if k != "resolution"},
                sort_keys=True,
                default=str,
            ),
        )
        for e in out.signal_events
    ]
    payload = {
        "summary": out.summary,
        "trades": [t.as_dict() if hasattr(t, "as_dict") else str(t) for t in out.trades],
        "events": events,
        "equity": [str(p) for p in out.equity_points],
        "diagnostics": {
            k: v for k, v in out.diagnostics.items() if k != "stop_conflict_resolution"
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


@pytest.mark.parametrize("resolution", sorted(_STOP_RESOLUTIONS))
def test_the_stop_conflict_resolution_that_governed_is_published_per_literal(
    resolution: str,
) -> None:
    """Four literals ship; nothing read back which one governed.

    Measured on ``origin/main`` @ ``17bb495f``: ``diagnostics["stop_conflict_resolution"]``
    has ZERO assertions in the suite, and so does the ``stop_resolution`` event's
    ``detail["resolution"]`` -- both are published (``execution/output.py``,
    ``engine.py``) and both were unread. ``record_all_execute_highest`` had never reached
    the engine plane at all; its only case drives ``_resolve_stop`` directly.

    Behaviour and disclosure are pinned TOGETHER on purpose. Asserting the echo alone
    would pass while the engine ignored the setting; asserting the outcome alone would
    pass while the Result named a policy the run never applied.
    """
    expected_rule, expected_exit, expected_approximated = _STOP_RESOLUTIONS[resolution]
    out = _run(_two_stop_config(resolution), _long_breakout_then_stop())

    # Half 1 -- the behaviour: this resolution picked THIS rule, at THIS price.
    assert out.summary["total_trades"] == 1
    assert str(out.trades[0].exit_price) == expected_exit
    assert out.trades[0].exit_reason == "stop_loss"

    # Half 2 -- the disclosure: both published planes name THIS literal, verbatim.
    assert out.diagnostics["stop_conflict_resolution"] == resolution

    events = [e for e in out.signal_events if e.event_type == "stop_resolution"]
    assert len(events) == 1, "both stops trigger, so exactly one resolution is recorded"
    detail = events[0].detail
    assert detail["resolution"] == resolution
    assert detail["executed"] == expected_rule
    assert detail["first_trigger_approximated"] is expected_approximated
    # Every literal carries EVERY co-triggered rule -- the fact the twin tripwire rests on.
    assert sorted(detail["triggered"]) == ["absolute", "percentage"]
    # The requirement is echoed beside the resolution and was likewise never read.
    assert detail["requirement"] == "any_active"


def test_the_four_stop_conflict_resolutions_are_covered_by_a_case_between_them() -> None:
    """Anti-drift: a newly added literal must not arrive with zero cases.

    Same shape as the ``same_candle_entry_exit`` guard above -- a behavioural test cannot
    see a literal that no scenario happens to select, so the coverage set is compared to
    the shipped ``Literal`` instead of being trusted.
    """
    from entropia.domain.strategy.config import ProtectionStopLogic

    shipped = set(ProtectionStopLogic.model_fields["stop_conflict_resolution"].annotation.__args__)
    assert set(_STOP_RESOLUTIONS) == shipped, (
        "a stop_conflict_resolution literal has no case: add one (do not widen this set)"
    )


def test_record_all_execute_highest_is_a_deliberate_twin_of_priority_order() -> None:
    """``record_all_execute_highest`` is indistinguishable from ``priority_order`` TODAY.

    Measured, not asserted: the two share a single branch (``execution/fills.py`` --
    ``if resolution in ("priority_order", "record_all_execute_highest")``), and the whole
    of ``record_all_execute_highest`` in ``backend/src`` is that one branch plus the schema
    literal and its prose. The schema promises the difference is that "record_all also
    records every co-triggered rule in the ledger" -- but ``_StopOutcome.triggered`` is
    built the same way in EVERY branch, so that promise is already kept by all four
    literals and distinguishes none of them.

    The pre-existing case (``test_record_all_execute_highest_records_every_triggered_rule``)
    cannot see this: both of its assertions hold for ``priority_order`` too, so it proves
    the shared branch works, not that ``record_all`` records anything extra.

    This is a TRIPWIRE, not an approval. If the literal is ever given a real distinct
    effect -- or removed -- this goes red and forces the decision (GH #536) rather than
    letting a documented difference stay fictional.
    """
    runs = {
        literal: _run(_two_stop_config(literal), _long_breakout_then_stop())
        for literal in ("priority_order", "record_all_execute_highest")
    }

    # Vacuity guard: an empty run would make "identical" trivially true.
    assert all(out.summary["total_trades"] == 1 for out in runs.values())
    assert all(out.summary["total_stops"] == 1 for out in runs.values())

    # The echo is the ONLY thing that may differ, and it must be verbatim on both planes.
    for literal, out in runs.items():
        assert out.diagnostics["stop_conflict_resolution"] == literal
        event = next(e for e in out.signal_events if e.event_type == "stop_resolution")
        assert event.detail["resolution"] == literal

    fingerprints = {literal: _stop_fingerprint(out) for literal, out in runs.items()}
    assert len(set(fingerprints.values())) == 1, (
        "record_all_execute_highest stopped being a twin of priority_order: "
        f"{ {k: v[:12] for k, v in fingerprints.items()} }. "
        "That is not automatically a bug -- but the schema's 'records every co-triggered "
        "rule in the ledger' claim is now either true or still fiction, and which one it "
        "is has become a DISCLOSURE decision, see GH #536."
    )


# --------------------------------------------------------------------------- #
# Gap B (3) -- stop_priority_order over a logic:<block_id>, at the ENGINE plane #
# --------------------------------------------------------------------------- #

_STOP_BLOCK_ID = "stop_1"
_LOGIC_KEY = f"logic:{_STOP_BLOCK_ID}"


def _logic_stop_plan() -> IndicatorPlan:
    """The shared entry plan plus a Logic-Based Stop Block that fires on the stop-out bar.

    Built with ``replace`` off ``sma_entry_plan`` rather than re-declared, so the entry
    signal stays the one every engine fixture drives (F-24) and this plan differs from
    its neighbours in exactly one respect: it pins a stop block.

    ``length=3`` is chosen against the fixture's geometry, not arbitrarily. Over the 20
    flat bars the MA rests at the flat price and never crosses; the breakout bar closes
    ABOVE it (a ``long`` signal, which is not adverse to a long position and so triggers
    nothing); the drop bar closes at 95 against an MA of 99 and crosses BELOW, which is
    the adverse signal the engine turns into ``logic:stop_1``. A longer span would still
    cross on that bar -- 2, 3 and 5 were measured identical -- but 3 is the shortest that
    keeps the flat run cross-free.
    """
    return replace(
        sma_entry_plan(),
        stop_specs=(
            IndicatorSpec(
                block_id=_STOP_BLOCK_ID,
                canonical_key="ta.sma",
                length=3,
                direction="long_and_short",
                requirement="required",
                validity="current_candle_only",
            ),
        ),
    )


def _priority_config(order: list[str] | None, *, requirement: str = "any_active") -> Any:
    """``priority_order`` resolution, so ``stop_priority_order`` is what decides.

    Under the default ``most_conservative`` the order is only a tie-break, so a test that
    left the resolution alone would be measuring distance, not precedence.
    """
    protection: dict[str, Any] = {
        "stop_conflict_resolution": "priority_order",
        "stop_trigger_requirement": requirement,
    }
    if order is not None:
        protection["stop_priority_order"] = order
    return _patched(_config(), {"protection_stop_logic": protection})


#: label -> (saved ``stop_priority_order``, executed rule, exit price).
#: Measured on ``origin/main`` @ ``6fec0e51``. Entry is 102.00, so the 1% percentage stop
#: rests at 100.98 and the logic block exits at the drop bar's close, 95.00.
_PRIORITY_CONTESTS: dict[str, tuple[list[str] | None, str, str]] = {
    # The schema's documented default: "logic blocks in display order, then percentage,
    # trailing, absolute". Never driven through the engine before.
    "null -- canonical order, logic leads": (None, _LOGIC_KEY, "95.00"),
    "explicit, logic still leads": ([_LOGIC_KEY, "percentage"], _LOGIC_KEY, "95.00"),
    # The one that matters: an explicit order OVERRIDES the canonical logic-first rule.
    "explicit, percentage promoted over the logic block": (
        ["percentage", _LOGIC_KEY],
        "percentage",
        "100.98",
    ),
}


@pytest.mark.parametrize("label", sorted(_PRIORITY_CONTESTS))
def test_a_logic_block_takes_its_place_in_the_stop_priority_order_that_governed(
    label: str,
) -> None:
    """``stop_priority_order`` accepts ``logic:<block_id>``; nothing drove one end to end.

    Measured on ``origin/main`` @ ``6fec0e51``: every ``logic:`` key in the suite is
    either fed to ``_resolve_stop`` directly (``test_backtest_logic_stop``) or handed to
    ``stop_priority_sequence`` as a literal (``test_backtest_policy_provenance``). The one
    engine-plane run that builds a stop plan at all
    (``integration/test_logic_based_stop::test_run_engine_builds_and_consumes_the_stop_plan``)
    replays 24 flat bars, so its block never fires -- it proves WIRING, not FIRING, and it
    configures no priority order. This is the ADIM 142 honest boundary being discharged.

    The claim is falsifiable because the order moves REAL MONEY, not just a label: the
    same bars exit at 95.00 or at 100.98 depending on which key leads.
    """
    order, expected_rule, expected_exit = _PRIORITY_CONTESTS[label]
    out = _run(
        _priority_config(order), _long_breakout_then_stop(), indicator_plan=_logic_stop_plan()
    )

    events = [e for e in out.signal_events if e.event_type == "stop_resolution"]
    assert len(events) == 1, "one bar resolves the stop, so exactly one trace is recorded"
    detail = events[0].detail
    triggered = sorted(detail["triggered"])

    # Contest guard: BOTH rules must fire on the same bar, else precedence decides nothing
    # and every ordering would agree by default -- the case would measure zero.
    assert triggered == ["logic:stop_1", "percentage"], (
        f"no contest: only {triggered} fired, so the order was never consulted"
    )

    # Half 1 -- the behaviour: this order picked THIS rule, at THIS price.
    assert out.summary["total_trades"] == 1
    assert out.summary["total_stops"] == 1
    assert detail["executed"] == expected_rule
    assert str(out.trades[0].exit_price) == expected_exit
    assert out.trades[0].exit_reason == "stop_loss"

    # Half 2 -- the disclosure: the SAVED order is echoed verbatim (``null`` stays null),
    # and the RESOLVED order is total and actually explains the winner.
    assert out.diagnostics["stop_priority_order"] == order
    resolved = out.diagnostics["stop_priority_order_resolved"]
    assert sorted(resolved) == sorted([_LOGIC_KEY, "percentage", "trailing", "absolute"]), (
        "the resolved order must stay TOTAL -- an omitted key has no defined precedence"
    )
    # The winner is the earliest TRIGGERED key in the resolved order. Asserting
    # ``resolved[0] == executed`` would be weaker and sometimes wrong: the leading key
    # need not have triggered at all.
    assert next(key for key in resolved if key in detail["triggered"]) == expected_rule


def test_the_logic_stop_trigger_counter_counts_a_real_engine_firing() -> None:
    """``logic_stop_triggers`` is written, published and aggregated -- and never read.

    Measured on ``origin/main`` @ ``6fec0e51``: the counter has ZERO assertions in
    ``backend/tests``. It is incremented in ``engine.py``'s ``_emit_stop_resolution``,
    published by ``execution/output.py``, and carried through portfolio aggregation
    (``execution/portfolio.py``) -- so a Result and a portfolio roll-up both report it,
    and nothing checked it. Its only writer needs a logic stop to fire at the engine
    plane, which is precisely the path no test drove.

    The zero arm is what makes this falsifiable: a counter hard-wired to 1 would pass the
    firing half alone.
    """
    fired = _run(
        _priority_config(None), _long_breakout_then_stop(), indicator_plan=_logic_stop_plan()
    )
    # Same config and same bars; the ONLY difference is that no stop block is pinned.
    not_fired = _run(_priority_config(None), _long_breakout_then_stop())

    assert fired.diagnostics["logic_stop_blocks"] == 1
    assert fired.diagnostics["logic_stop_triggers"] == 1

    assert not_fired.diagnostics["logic_stop_blocks"] == 0
    assert not_fired.diagnostics["logic_stop_triggers"] == 0
    # Vacuity guard: the second run must still stop out (on the percentage rule), else the
    # zero above would just be the absence of any stop at all.
    assert not_fired.summary["total_stops"] == 1


def test_the_stop_resolution_event_names_all_active_as_the_requirement_that_governed() -> None:
    """The requirement echo, on the literal ADIM 142 could not reach.

    Measured on ``origin/main`` @ ``6fec0e51``: every ``all_active`` case in the suite
    stops at ``_resolve_stop`` or at the diagnostics echo. No test reads
    ``all_active`` off a ``stop_resolution`` EVENT -- the parametrized case above pins
    only ``any_active``, because its fixture has no second rule that could satisfy an AND.

    The logic-stop fixture supplies one: both rules fire on the drop bar, so ``all_active``
    is satisfied and the trace records the requirement that actually governed.
    """
    out = _run(
        _priority_config(["percentage", _LOGIC_KEY], requirement="all_active"),
        _long_breakout_then_stop(),
        indicator_plan=_logic_stop_plan(),
    )

    event = next(e for e in out.signal_events if e.event_type == "stop_resolution")
    # Load-bearing: under all_active a single-rule bar fires nothing, so the AND is only
    # satisfied here because BOTH rules triggered.
    assert sorted(event.detail["triggered"]) == ["logic:stop_1", "percentage"]
    assert event.detail["requirement"] == "all_active"
    assert out.diagnostics["stop_trigger_requirement"] == "all_active"
    assert out.summary["total_stops"] == 1


#: resolution -> (executed rule, exit price, ``first_trigger_approximated``).
#: Measured on ``origin/main`` @ ``c9676816`` with ONE fixed ``stop_priority_order``
#: (``_ORDER_UNDER_TEST``) held constant across all three, so the resolution literal is
#: the only variable. ``record_all_execute_highest`` is deliberately absent: it shares
#: ``priority_order``'s branch and is pinned as a twin above.
_ORDER_UNDER_TEST = [_LOGIC_KEY, "percentage"]
_RESOLUTION_CONTESTS: dict[str, tuple[str, str, bool]] = {
    # Reads the order: the logic block leads, so it executes at the drop bar's close.
    "priority_order": (_LOGIC_KEY, "95.00", False),
    # Ignores the order (no tie): |102 - 100.98| = 1.02 beats |102 - 95.00| = 7.00.
    "most_conservative": ("percentage", "100.98", False),
    # No tick path over OHLCV -> degrades to the conservative model and FLAGS it (§9.3).
    "first_trigger_wins": ("percentage", "100.98", True),
}


@pytest.mark.parametrize("resolution", sorted(_RESOLUTION_CONTESTS))
def test_the_stop_priority_order_governs_only_under_the_resolution_that_reads_it(
    resolution: str,
) -> None:
    """One order, one set of bars, three resolutions -- and two different exit prices.

    ``_STOP_RESOLUTIONS`` above already drives all four literals at this plane, but with
    two PRICE stops and no explicit ``stop_priority_order``; it therefore cannot say
    whether a saved order is authoritative. This case holds the order fixed and varies
    only the resolution, which is the claim that was missing: ``stop_priority_order`` is
    read by ``priority_order`` (and its twin) and is otherwise at most a tie-break.

    The stake is real money on identical bars -- 95.00 under one literal, 100.98 under the
    other two -- and the echo cannot explain it, which is the point of the last assertion:
    the SAVED order is byte-identical in all three runs, so a reader who trusted the
    disclosure alone would conclude the logic block always leads.
    """
    expected_rule, expected_exit, expected_approximated = _RESOLUTION_CONTESTS[resolution]
    out = _run(
        _patched(
            _config(),
            {
                "protection_stop_logic": {
                    "stop_conflict_resolution": resolution,
                    "stop_priority_order": _ORDER_UNDER_TEST,
                }
            },
        ),
        _long_breakout_then_stop(),
        indicator_plan=_logic_stop_plan(),
    )

    events = [e for e in out.signal_events if e.event_type == "stop_resolution"]
    assert len(events) == 1, "one bar resolves the stop, so exactly one trace is recorded"
    detail = events[0].detail

    # Contest guard: both rules must fire on the same bar, else the resolution has nothing
    # to resolve and all three literals would agree for a reason unrelated to precedence.
    assert sorted(detail["triggered"]) == ["logic:stop_1", "percentage"], (
        f"no contest: only {sorted(detail['triggered'])} fired"
    )

    assert out.summary["total_trades"] == 1
    assert out.summary["total_stops"] == 1
    assert detail["executed"] == expected_rule
    assert detail["resolution"] == resolution
    assert detail["first_trigger_approximated"] is expected_approximated
    assert str(out.trades[0].exit_price) == expected_exit

    # The disclosure is CONSTANT while the outcome moves: the saved order is echoed
    # verbatim under every resolution, including the two that never consult it.
    assert out.diagnostics["stop_priority_order"] == _ORDER_UNDER_TEST
