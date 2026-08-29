"""GH #534 — the two conflict policies the provenance block did not publish.

The engine's diagnostics block is the surface a reviewer uses to reconstruct WHICH policy
governed a Result without dereferencing the strategy revision. It published every conflict
field except two, and each omission hid a different kind of fact:

* ``same_candle_entry_exit`` was observable ONLY inside an ``entry_exit_collision`` event's
  ``detail["policy"]``. A run where no collision fired therefore recorded the governing
  policy NOWHERE -- and "no event" reads identically whether the policy suppressed nothing
  or was never consulted at all. Its one aggregate signal, ``suppressed_entries``, is
  SHARED with two unrelated suppression paths, so a non-zero value does not attribute here.

* the stop precedence order was invisible whenever the config left ``stop_priority_order``
  null -- which is the common case. Publishing the raw nullable input would have printed
  ``None`` and told the reader nothing; what governs is the RESOLVED total order that
  ``fills._stop_priority_index`` builds, so that is what is published.

These are assertions about the PROVENANCE surface, not about execution: the sibling suite
already pins which stop wins. What is pinned here is that a reader can SEE the rule.
"""

from __future__ import annotations

from typing import Any

import tests.unit.test_backtest_engine as base
from entropia.domain.backtest.execution.fills import _CANONICAL_PRICE_STOP_ORDER


def _diagnostics(**cfg: Any) -> dict[str, Any]:
    """Run the shared breakout fixture and hand back only the diagnostics block."""
    return base._run(base._config(**cfg), base._long_breakout_then_stop()).diagnostics


# --------------------------------------------------------------------------- #
# same_candle_entry_exit                                                       #
# --------------------------------------------------------------------------- #


def test_same_candle_entry_exit_is_published_beside_its_stop_exit_sibling() -> None:
    """Both keys must be present TOGETHER: they are two different rules a reader
    routinely conflates, and the bug was that only one of them was legible."""
    diagnostics = _diagnostics()
    assert "same_candle_entry_exit" in diagnostics
    assert "stop_exit_conflict" in diagnostics
    # The schema default is published as a real token -- not as ``None``, which would be
    # indistinguishable from "not modelled". Only ``exit_first`` admits the entry; every
    # other member of the Literal (this default included) suppresses it.
    assert diagnostics["same_candle_entry_exit"] == "use_intrabar_data_if_available"


def test_same_candle_entry_exit_publishes_the_configured_policy_not_a_constant() -> None:
    """A key that always prints the same string is provenance-shaped but carries no
    provenance. Drive BOTH policies and require the published token to follow."""
    assert _diagnostics()["same_candle_entry_exit"] == "use_intrabar_data_if_available"
    assert _diagnostics(same_candle_entry_exit="exit_first")["same_candle_entry_exit"] == (
        "exit_first"
    )


def test_the_policy_is_published_even_when_no_collision_ever_fired() -> None:
    """The defect in one assertion.

    This fixture never produces a flat-position entry+exit collision, so it emits no
    ``entry_exit_collision`` event -- the policy's only previous trace. Before #534 the
    governing policy was unrecoverable from such a run; now it is on the block regardless.
    """
    out = base._run(
        base._config(same_candle_entry_exit="exit_first"), base._long_breakout_then_stop()
    )
    collisions = [e for e in out.signal_events if e.event_type == "entry_exit_collision"]
    assert collisions == [], "fixture must NOT collide, or this test proves nothing"
    assert out.diagnostics["same_candle_entry_exit"] == "exit_first"


# --------------------------------------------------------------------------- #
# stop_priority_resolved                                                       #
# --------------------------------------------------------------------------- #


def test_null_config_publishes_the_canonical_order_not_none() -> None:
    """The common case. A raw-input projection would print ``None`` here; the resolved
    projection prints the Master Ref 9.2 order that actually governed."""
    resolved = _diagnostics()["stop_priority_resolved"]
    assert resolved is not None
    assert resolved == list(_CANONICAL_PRICE_STOP_ORDER)


def test_explicit_order_leads_and_omitted_keys_are_appended_canonically() -> None:
    """An explicit order leads; anything it omits still has to appear, because the order
    ``_stop_priority_index`` builds is TOTAL. Publishing a partial list would misreport
    the precedence of every key the operator did not name."""
    resolved = _diagnostics(stop_priority_order=["absolute"])["stop_priority_resolved"]
    assert resolved[0] == "absolute"
    assert sorted(resolved) == sorted(_CANONICAL_PRICE_STOP_ORDER)
    # the tail keeps canonical relative order among the keys the operator left out
    tail = list(resolved[1:])
    assert tail == [key for key in _CANONICAL_PRICE_STOP_ORDER if key != "absolute"]


def test_the_published_order_is_the_one_the_resolver_would_build() -> None:
    """Anti-drift: the block must not carry a SECOND transcription of the order.

    Compare the published list against ``_stop_priority_index`` itself. If someone later
    re-derives the order inside ``output.py``, the two can disagree and this fails."""
    from entropia.domain.backtest.execution.fills import _stop_priority_index

    order = ["trailing", "absolute"]
    resolved = _diagnostics(stop_priority_order=order)["stop_priority_resolved"]
    index = _stop_priority_index(order, [])
    assert resolved == sorted(index, key=index.__getitem__)
