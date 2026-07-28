"""O-09 — the pure ref reader behind the Approve-time dependency gate (doc 06 §7).

``ensure_pinned_resolvers_active`` itself reads the registry, so it is exercised
against a real database in
``tests/integration/test_create_package_approve_dependency_gate.py``. What is pure —
and what decides whether a pin is even SEEN by that gate — is the snapshot reader:
a shape it silently drops is a pin nobody re-validates.
"""

from __future__ import annotations

import pytest

from entropia.application.queries.dependency_pins import pinned_resolver_refs


def test_reads_the_pinned_refs_in_order() -> None:
    snapshot = {
        "resolved": [
            {"call": "ta.rsi", "canonical_key": "ta.rsi", "embedded_revision_id": "pkgr_1"},
            {"call": "ta.ema", "canonical_key": "ta.ema", "embedded_revision_id": "pkgr_2"},
        ],
        "scan_id": "cpds_1",
    }
    assert [ref["canonical_key"] for ref in pinned_resolver_refs(snapshot)] == ["ta.rsi", "ta.ema"]


def test_description_route_snapshot_has_no_pins() -> None:
    assert pinned_resolver_refs({"resolved": [], "source": "description"}) == []


@pytest.mark.parametrize(
    "snapshot",
    [None, {}, [], "pkgr_1", 7, {"resolved": None}, {"resolved": "not-a-list"}],
)
def test_unusable_snapshot_shapes_yield_no_pins(snapshot: object) -> None:
    """A snapshot the reader cannot understand contributes nothing — it never
    fabricates a ref, and the gates that own the snapshot contract fail on it."""
    assert pinned_resolver_refs(snapshot) == []


def test_non_dict_entries_are_dropped_but_dict_entries_survive() -> None:
    """A malformed entry cannot hide the real pin next to it."""
    snapshot = {"resolved": ["ta.rsi", None, {"canonical_key": "ta.ema"}]}
    assert pinned_resolver_refs(snapshot) == [{"canonical_key": "ta.ema"}]
