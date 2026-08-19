"""`C4` / E5 — the ONE place that chooses the shared clock, and both of its terms.

``_use_unified_clock`` is a two-term ``and``, and the terms are tested SEPARATELY rather
than only through the function's combined answer. That is not pedantry: a short-circuiting
``and`` lets either term be deleted while every test of the composite result stays green,
and each deletion has its own financial consequence (P-C2 §C.5, plan §PACKAGE C `C4`):

* drop ``shared_allocation_requested`` -> EVERY multi-item run takes the shared clock;
* drop ``shared_allocation_is_executable`` -> any snapshot mis-read takes it.

Either one silently re-prices every independent composite Result — a different number with
no flag, no ``ENGINE_VERSION`` bump and nothing the user can see. So each cell below pins
one conjunct's contribution, and the two "forced flag" cells are the ones a single-term
implementation cannot satisfy at the same time.

The flag is forced by monkeypatching the symbol AS THE WORKER IMPORTED IT. That fixture is
test-owned and is never importable from ``backend/src`` — forcing it in production is the
lift (`C9` / ADIM 20), behind the ADR §16 human gate.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.application.jobs import backtest_engine as worker
from entropia.domain.allocation.capability import (
    SHARED_ALLOCATION_STATUS,
    shared_allocation_is_executable,
    shared_allocation_requested,
)

_SHARED: dict[str, Any] = {"enabled": True, "config": {"initial_capital": {"amount": "50000.00"}}}
_INDEPENDENT: dict[str, Any] = {"enabled": False}


def _force_flag(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    """Make the worker's own reference to the capability answer ``value``.

    Patched on the WORKER module, not on ``capability``: the worker binds the function at
    import, so patching the definition site would leave the call site pointing at the real
    one and the test would prove nothing about the branch it claims to drive."""
    monkeypatch.setattr(worker, "shared_allocation_is_executable", lambda: value)


def test_as_shipped_no_capital_snapshot_takes_the_shared_clock() -> None:
    """The containment, stated as this function's answer: with the flag at ``future_dev``
    there is no ``capital_execution`` that turns it True — including one that explicitly
    asks for shared capital, which is the only shape anybody could construct."""
    assert SHARED_ALLOCATION_STATUS == "future_dev"
    assert shared_allocation_is_executable() is False
    assert worker._use_unified_clock(_SHARED) is False
    assert worker._use_unified_clock(_INDEPENDENT) is False
    assert worker._use_unified_clock(None) is False


def test_the_requested_term_alone_does_not_open_the_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Term 1 is load-bearing: a snapshot that ASKS for shared capital is not enough.

    This is the cell that fails if ``shared_allocation_is_executable`` is dropped from the
    conjunction — the request alone would then route the run through the unified loop."""
    _force_flag(monkeypatch, False)
    assert shared_allocation_requested(_SHARED) is True  # the term really is satisfied
    assert worker._use_unified_clock(_SHARED) is False


def test_the_executable_term_alone_does_not_open_the_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Term 2 is load-bearing: a build that CAN co-simulate still replays independent
    compositions independently.

    This is the cell that fails if ``shared_allocation_requested`` is dropped — a lifted
    build would then re-price every independent multi-item Result on the shared clock."""
    _force_flag(monkeypatch, True)
    assert worker._use_unified_clock(_INDEPENDENT) is False
    assert worker._use_unified_clock(None) is False
    assert worker._use_unified_clock({}) is False


def test_only_both_terms_together_open_the_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The positive cell. Reachable only under a forced flag, which is the containment."""
    _force_flag(monkeypatch, True)
    assert worker._use_unified_clock(_SHARED) is True


def test_the_capability_is_read_at_the_branch_and_never_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR §11: flipping the constant back is a ONE-CONSTANT rollback. A capability cached
    at import — a module-level ``_SHARED_ON = shared_allocation_is_executable()`` — would
    survive that flip inside a running worker, so the rollback would not be one constant.
    Driven by flipping the answer between two calls with no reload in between."""
    answers = iter([True, False])
    monkeypatch.setattr(worker, "shared_allocation_is_executable", lambda: next(answers))
    assert worker._use_unified_clock(_SHARED) is True
    assert worker._use_unified_clock(_SHARED) is False


# --------------------------------------------------------------------------- #
# The merge order the shared clock reads                                       #
# --------------------------------------------------------------------------- #


def test_pin_ordinals_number_the_manifest_order_not_the_replayed_subset() -> None:
    """ADR §4.4 — ``pin_ordinal`` is an index into the MANIFEST's pinned items.

    The distinction is invisible in the common case and load-bearing in the general one:
    ``prepared_items`` holds only the STRATEGY items that resolved, so numbering it with
    ``enumerate`` agrees with the manifest exactly until a non-Strategy item sits between
    two Strategies — and then the two numberings differ, which moves the
    ``(pin_ordinal, item_id)`` tie-break that orders a tick's decisions. A composition
    would silently arbitrate in a different order depending on whether a Trade Log happened
    to be pinned in the middle of it.

    The fixture puts a Trade Log between the two Strategies for exactly that reason: with
    the item removed, list position and manifest position agree and this test could not
    fail."""
    manifest = {
        "mainboard_items": [
            {"item_id": "mbi_a", "item_kind": "strategy"},
            {"item_id": "mbi_log", "item_kind": "trade_log"},
            {"item_id": "mbi_b", "item_kind": "strategy"},
        ]
    }

    ordinals = worker._manifest_pin_ordinals(manifest)

    assert ordinals == {"mbi_a": 0, "mbi_log": 1, "mbi_b": 2}
    # The replayed subset is ["mbi_a", "mbi_b"]; numbering IT would have given b == 1.
    assert ordinals["mbi_b"] == 2
    # Presentation ``position`` (doc 01 §5.2) is never consulted — the key is absent here
    # and the ordinals are still well defined.
    assert all("position" not in item for item in manifest["mainboard_items"])


def test_pin_ordinals_survive_a_manifest_that_predates_the_key() -> None:
    """A manifest with no ``mainboard_items`` yields no ordinals rather than raising.

    The caller turns a missing ordinal into a typed ``MANIFEST_RESOLUTION`` failure — the
    shared clock has no deterministic place to merge an item it cannot number, and guessing
    one would make the merge order depend on dict iteration (ADR §11 determinism)."""
    assert worker._manifest_pin_ordinals({}) == {}
    assert worker._manifest_pin_ordinals({"mainboard_items": [{"item_kind": "strategy"}]}) == {}
