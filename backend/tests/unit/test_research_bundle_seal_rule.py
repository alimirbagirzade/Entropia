"""R3 — a sealed-shape change must move ``compiler_version``, and this makes it hurt.

Doc 12 §9.2's complaint against the pre-#558 bundle was that it could not attest its
own timing rule. Karar 2 fixed the shape and moved ``compiler_version`` to
``research-bundle-v2``. What it did NOT leave behind was a way to notice the next such
change: the suite pinned individual keys (``"instrument_mapping_revision_ids" in
forward``) and the version's literal VALUE, so a seventh key could be added to the
sealed body and every test would stay green — leaving two bundles compiled under
different field sets sharing one ``compiler_version`` while being non-comparable.

This module closes that with a golden digest, the idiom the engine already uses
(``engine_golden_digests.json``). ``_seal_bundle`` is synchronous and takes no
session, so the digest is pinned as a literal here rather than in a JSON side-file:
the input is small enough to read beside the expected output, which is the whole
point of a golden.

**If a golden below moves, exactly two outcomes are legitimate:** revert the shape
change, or bump ``_BUNDLE_COMPILER_VERSION`` *and* re-pin the golden in the same
commit. Editing the golden alone is the one move that must not happen quietly — it
would silently re-partition the bundle hash space, which is precisely what the
version exists to announce.

R3's other half — ``resolved_at`` outside the hash — shipped with #730 and is
asserted end-to-end in ``tests/integration/test_research_point_in_time_parity.py``.
It is re-asserted here at the unit level because that test needs a database and a
compiled revision, while the property is a pure fact about ``_seal_bundle``.
"""

from __future__ import annotations

from typing import Any

from entropia.application.jobs.research_data import (
    _BUNDLE_COMPILER_VERSION,
    _SEALED_BODY_KEYS,
    _seal_bundle,
)
from entropia.shared.manifest import manifest_hash

# The two keys written AFTER the hash. Duplicated from the integration module on
# purpose: a shared constant would let one edit silence both surfaces at once.
_UNHASHED = frozenset({"resolved_at", "bundle_hash"})

_MEMBERS: list[dict[str, Any]] = [
    {
        "research_revision_id": "rdrev_01GOLDEN",
        "research_content_hash": "a" * 64,
        "usage_scope": "execution_allowed",
        "market_dataset_revision_id": "mdrev_01GOLDEN",
        "market_content_hash": "b" * 64,
        "available_time_policy": "fixed_delay",
        "available_delay_seconds": 120,
        "event_time_semantics": "event_time",
        "frequency_policy": None,
        "source_timezone_mode": "utc",
        "source_timezone_iana": None,
        "instrument_mapping_ref": "map/v1",
        "feature_definition_ids": ["feat_01"],
    }
]

# Golden digests, measured from the shipped code at ``research-bundle-v2``.
_GOLDEN_EVIDENCE = "bfb5d51b7ccbd282f4d6be4938b369724a31ad824e0779689c6627bd26f04a65"
_GOLDEN_AGENT = "65223f8005b0276023ec27d9878ad47f01bd36ee77dc5573f553488f7e28b90a"


def _evidence() -> dict[str, Any]:
    return _seal_bundle("backtest_evidence_bundle", _MEMBERS, extra={"run_request_id": "req_01"})


def _agent() -> dict[str, Any]:
    return _seal_bundle("agent_data_bundle", _MEMBERS, extra={"task_id": None})


def test_the_evidence_bundle_shape_is_pinned_to_its_compiler_version() -> None:
    """The golden and the version are asserted TOGETHER, deliberately.

    Either alone is weak: the version alone says nothing about the shape, and the
    hash alone does not say which version it belongs to. The pair is the rule."""
    sealed = _evidence()

    assert sealed["compiler_version"] == "research-bundle-v2"
    assert sealed["compiler_version"] == _BUNDLE_COMPILER_VERSION
    assert sealed["bundle_hash"] == _GOLDEN_EVIDENCE


def test_the_agent_bundle_shape_is_pinned_too() -> None:
    """Both compilers seal through one function, so both shapes are pinned.

    They differ in ``bundle_kind`` and in which optional key they carry, so one
    golden cannot stand in for the other."""
    sealed = _agent()

    assert sealed["compiler_version"] == _BUNDLE_COMPILER_VERSION
    assert sealed["bundle_hash"] == _GOLDEN_AGENT
    assert sealed["bundle_hash"] != _GOLDEN_EVIDENCE


def test_the_core_hashed_key_set_is_exactly_what_the_constant_names() -> None:
    """``_SEALED_BODY_KEYS`` must not rot into decoration.

    Asserted as the hashed key set MINUS the caller's optional extra, because that
    extra is per-caller by design while this core is invariant."""
    evidence_hashed = {k for k in _evidence() if k not in _UNHASHED}
    agent_hashed = {k for k in _agent() if k not in _UNHASHED}

    assert evidence_hashed - {"run_request_id"} == _SEALED_BODY_KEYS
    assert agent_hashed == _SEALED_BODY_KEYS
    assert _UNHASHED.isdisjoint(_SEALED_BODY_KEYS)


def test_resolved_at_and_bundle_hash_sit_outside_the_hashed_body() -> None:
    """Recomputing over the body minus the two volatile keys reproduces the hash.

    This also pins that NOTHING ELSE was excluded: if a third key were being written
    after the hash, the recomputation would not match."""
    sealed = _evidence()

    assert (
        manifest_hash({k: v for k, v in sealed.items() if k not in _UNHASHED})
        == (sealed["bundle_hash"])
    )


def test_the_same_input_seals_to_the_same_hash_twice() -> None:
    """Determinism, and the reason ``resolved_at`` may be wall-clock at all.

    ``resolved_at`` differs between these two calls (it is ``datetime.now``); the
    hash must not."""
    first, second = _evidence(), _evidence()

    assert first["bundle_hash"] == second["bundle_hash"]
    assert "resolved_at" in first


def test_a_none_extra_is_dropped_rather_than_hashed_as_null() -> None:
    """``task_id=None`` must leave NO key, not a null one.

    A missing key and a null key hash differently, so this is a wire decision, not a
    formatting one — and it is why the Agent golden differs from a hypothetical one
    carrying ``task_id: null``."""
    sealed = _agent()

    assert "task_id" not in sealed
    assert (
        manifest_hash({**{k: v for k, v in sealed.items() if k not in _UNHASHED}})
        == (sealed["bundle_hash"])
    )


def test_a_present_extra_enters_the_hash() -> None:
    """The optional key is not cosmetic: supplying it changes the identity."""
    without = _seal_bundle("agent_data_bundle", _MEMBERS, extra={"task_id": None})
    with_task = _seal_bundle("agent_data_bundle", _MEMBERS, extra={"task_id": "task_01"})

    assert with_task["bundle_hash"] != without["bundle_hash"]


def test_the_golden_moves_when_a_key_is_added_to_the_sealed_body() -> None:
    """Negative control for the rule itself.

    Simulates the exact regression the constant exists to catch — a seventh key
    added to the hashed body. If this did NOT move the hash, the golden would be
    incapable of noticing a shape change and the whole module would be theatre."""
    sealed = _evidence()
    body = {k: v for k, v in sealed.items() if k not in _UNHASHED}

    assert manifest_hash({**body, "alignment_policy_versions": []}) != _GOLDEN_EVIDENCE


def test_the_golden_moves_when_the_compiler_version_changes() -> None:
    """Second negative control: the version is INSIDE the hashed body.

    That is what lets a bump partition the hash space by itself, with no migration
    and no dual-read — the property #730 relied on when it moved v1 to v2."""
    sealed = _evidence()
    body = {k: v for k, v in sealed.items() if k not in _UNHASHED}

    assert manifest_hash({**body, "compiler_version": "research-bundle-v3"}) != _GOLDEN_EVIDENCE


def test_the_member_list_is_inside_the_hash() -> None:
    """A bundle's identity is its members; a golden that ignored them would be inert."""
    sealed = _evidence()
    body = {k: v for k, v in sealed.items() if k not in _UNHASHED}
    mutated = {**body, "members": []}

    assert manifest_hash(mutated) != _GOLDEN_EVIDENCE
