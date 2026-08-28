"""`C4` (E5) — ``_use_unified_clock``, both conjuncts pinned SEPARATELY (P-C2 §C.5).

The worker's branch predicate is
``shared_allocation_is_executable() and shared_allocation_requested(capital_execution)``,
and the plan calls both conjuncts load-bearing for a reason that is not symmetric:

* drop ``shared_allocation_requested`` and EVERY multi-item run enters the shared loop;
* drop ``shared_allocation_is_executable`` and any run whose snapshot merely *looks* shared
  enters it, containment or not.

Either mistake silently re-prices independent composite Results — no flag, no
``ENGINE_VERSION`` bump, nothing a reader could see. Independent multi-item runs are a
first-class mode (doc 13 §1.1), so this is most of what production actually runs.

**A compound assertion cannot catch either one.** ``A and B`` short-circuits, so a test that
only checks the answer for the shipped world (False) passes with ``B`` deleted. That is the
measured lesson of ADIM 76, where eight negative controls left one conjunct green. So the
2x2 is enumerated: each cell names WHICH term it is holding at False.

Infra-free — the predicate is pure. The lift fixture is test-owned and patches the module
global; ``test_shared_allocation_two_world_gate.py`` asserts structurally that production has
no env var, no setter and no second assignment that could do the same.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from entropia.application.jobs.backtest_engine import (
    _TICK_CHECKPOINT_STRIDE,
    _use_unified_clock,
)
from entropia.domain.allocation import capability
from entropia.domain.allocation.capability import (
    shared_allocation_is_executable,
    shared_allocation_requested,
)

_SHARED: dict[str, Any] = {"enabled": True, "config": {"initial_capital": {"amount": "50000.00"}}}
_INDEPENDENT: dict[str, Any] = {"enabled": False}


@contextmanager
def _lifted(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    with monkeypatch.context() as patch:
        patch.setattr(capability, "SHARED_ALLOCATION_STATUS", "active_v1")
        yield


@contextmanager
def _contained(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The mirror of :func:`_lifted`, added at ADIM 20 — see the note on the test below."""
    with monkeypatch.context() as patch:
        patch.setattr(capability, "SHARED_ALLOCATION_STATUS", "future_dev")
        yield


def test_the_containment_fixture_actually_moves_the_world(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A two-world test whose fixture does not move the world is a one-world test twice.

    Renamed at ADIM 20: production ships lifted, so :func:`_contained` is the half that
    moves the world now."""
    assert shared_allocation_is_executable() is True
    with _contained(monkeypatch):
        assert shared_allocation_is_executable() is False
    assert shared_allocation_is_executable() is True


def test_the_contained_world_never_takes_the_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both cells of the ``future_dev`` row, including the one that ASKS for shared capital.

    Renamed from ``test_the_shipped_world_never_takes_the_branch``: since ADIM 20 the shipped
    world DOES take the branch, which is the whole point of the lift. What this test still
    pins is the contained row — a request can set every field it likes in
    ``capital_execution`` and still not reach the loop, because the other conjunct is a
    build-time constant no request can move."""
    with _contained(monkeypatch):
        assert _use_unified_clock(_INDEPENDENT) is False
        assert _use_unified_clock(_SHARED) is False
        # And the reason is the FLAG, not the snapshot — asserted rather than inferred, so
        # this test cannot silently become a test of ``shared_allocation_requested`` alone.
        assert shared_allocation_requested(_SHARED) is True
        assert shared_allocation_is_executable() is False

    # The shipped world is the other row, and it takes the branch exactly when asked to.
    assert _use_unified_clock(_SHARED) is True
    assert _use_unified_clock(_INDEPENDENT) is False


def test_lifting_the_flag_alone_does_not_take_the_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``shared_allocation_requested`` conjunct, isolated.

    Delete it from the predicate and this cell flips to True — which is the wiring that would
    route every independent multi-item run through the shared loop. The other three cells all
    stay correct without it, which is exactly why it needs its own assertion."""
    with _lifted(monkeypatch):
        assert shared_allocation_is_executable() is True
        assert _use_unified_clock(_INDEPENDENT) is False
        assert _use_unified_clock(None) is False
        assert _use_unified_clock({}) is False


def test_both_conjuncts_true_is_the_only_cell_that_takes_the_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fourth cell — and the anti-vacuity guard for the three above.

    Without it every assertion in this module could be satisfied by a predicate hard-wired to
    ``False``, which would pass the whole file while wiring nothing."""
    with _lifted(monkeypatch):
        assert _use_unified_clock(_SHARED) is True


def test_requested_reads_the_snapshot_exactly_as_the_engine_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The branch and the engine must agree about which runs are shared, or the worker would
    hand a shared run to a path that sizes it independently.

    ``shared_allocation_requested`` states in its own docstring that it mirrors
    ``resolve_allocation_execution``'s truthiness on the same key; this pins the pairing at
    the BRANCH, where a divergence would actually route a run wrongly."""
    from entropia.domain.backtest.engine import resolve_allocation_execution

    with _lifted(monkeypatch):
        for snapshot in (_SHARED, _INDEPENDENT, {}, None, {"enabled": True}):
            engine_says = resolve_allocation_execution(snapshot, item_id="mbi_1") is not None
            if engine_says:
                assert _use_unified_clock(snapshot) is True, snapshot
            # The converse does NOT hold and must not be asserted: ``{"enabled": True}`` with
            # no readable config is "requested but unresolvable", and the branch takes it so
            # the worker can FAIL it closed rather than silently replaying it independently.


def test_the_cancellation_stride_is_a_positive_constant() -> None:
    """ADR §11 anticipates per-K-ticks granularity; K must be a number that checks.

    A stride of 0 raises at the first tick, and a negative one never checks at all — the
    second is the interesting failure, because it turns a long shared run uncancellable while
    leaving every other test in this slice green."""
    assert isinstance(_TICK_CHECKPOINT_STRIDE, int)
    assert _TICK_CHECKPOINT_STRIDE >= 1
