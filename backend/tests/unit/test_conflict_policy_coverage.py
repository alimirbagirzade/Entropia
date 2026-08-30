"""GH #536 — the conflict options that ship untested (F-5, §3.7 / §3.5).

Two gaps, both about DISCLOSURE rather than behaviour; no production code changes.

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
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from tests.unit.test_backtest_engine import (
    _config,
    _long_breakout_then_stop,
    _run,
    _same_candle_entry_exit_plan,
)

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
