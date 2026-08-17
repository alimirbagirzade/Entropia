"""R2 — the bundle member is projected from the shared object, and moves ZERO bytes.

`R1` gave the Run manifest and Ready Check one reading of a research revision's
timing provenance. The bundle compilers were deliberately left out of that slice
(the ordered plan: *"the bundle compilers are NOT changed in R1 — that is R2"*), so
``jobs/research_data.py::_pin_member`` went on re-deriving the same columns by hand
— while its own docstring asserted the block *"mirrors the Run manifest's revision
sub-dict field for field"*. Nothing checked that claim. R2 makes it true by
construction.

The member dict is hashed into ``bundle_hash`` (``_seal_bundle`` -> ``manifest_hash``),
so the same rule as R1 applies one surface over: a key added, dropped or renamed
re-partitions the bundle hash space. The difference from R1 is that here a *deliberate*
shape change already happened — GH #558 / Karar 2 (A1+A2, signed 2026-08-14) moved
``compiler_version`` to ``research-bundle-v2``. **This slice must not move it again.**
That is the whole point: a refactor that re-partitions a hash space is not a refactor.

``_MAIN_INLINE_MEMBER`` is a VERBATIM transcription of the literal that stood in
``_pin_member`` before the extraction (``origin/main`` ``b7d3789``). Hand-copied on
purpose — importing the new code to test the new code proves only that a function
equals itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from entropia.domain.research_data.timing_provenance import (
    BUNDLE_MEMBER_KEYS,
    TimingProvenance,
)
from entropia.shared.manifest import manifest_hash


@dataclass
class _Row:
    """A ``research_dataset_revision`` row, shaped structurally (never the ORM model).

    ``available_delay_seconds`` defaults to ``0`` and two nullable columns to ``None``
    for the R1 reason: ``0`` and ``None`` are different availability facts that a
    careless projection collapses, and a fixture built only from truthy values would
    never notice.
    """

    revision_id: str = "rdrev_01BUNDLE"
    entity_id: str = "rd_01ROOT"
    revision_state: Any = "ACTIVE"
    validation_status: Any = "passed"
    category_key: str | None = "macro.rates"
    field_definition_version: int | None = 4
    linked_market_dataset_revision_id: str | None = "mdrev_01LINK"
    instrument_mapping_ref: str | None = "map/v3"
    event_time_semantics: Any = "event_time"
    available_time_policy: Any = "delayed"
    available_delay_seconds: int | None = 0
    frequency_policy: Any = None
    source_timezone_mode: Any = "custom"
    source_timezone_iana: str | None = None
    usage_scope: Any = "execution_allowed"
    content_hash: str = "d" * 64


_MARKET_HASH = "m" * 64
_FEATURE_IDS = ["feat_01", "feat_02"]


def _enum(value: Any) -> str | None:
    """``jobs/research_data._enum``, transcribed as it stood before the extraction.

    That helper was the THIRD copy of one two-line coercion (after
    ``run_context._enum`` and the already-deleted ``readiness_check._enum_value``);
    all five of its call sites were inside ``_pin_member``, so the extraction left it
    dead and it was removed.
    """
    return None if value is None else str(value)


def _MAIN_INLINE_MEMBER(
    revision: _Row, market_content_hash: str | None, feature_ids: list[str]
) -> dict[str, Any]:
    """The pre-extraction literal, verbatim. Do NOT refactor this into the new code."""
    return {
        "research_revision_id": revision.revision_id,
        "research_content_hash": revision.content_hash,
        "usage_scope": _enum(revision.usage_scope),
        "market_dataset_revision_id": revision.linked_market_dataset_revision_id,
        "market_content_hash": market_content_hash,
        "available_time_policy": _enum(revision.available_time_policy),
        "available_delay_seconds": revision.available_delay_seconds,
        "event_time_semantics": _enum(revision.event_time_semantics),
        "frequency_policy": _enum(revision.frequency_policy),
        "source_timezone_mode": _enum(revision.source_timezone_mode),
        "source_timezone_iana": revision.source_timezone_iana,
        "instrument_mapping_ref": revision.instrument_mapping_ref,
        "feature_definition_ids": feature_ids,
    }


def _projected(
    row: _Row,
    *,
    market_content_hash: str | None = _MARKET_HASH,
    feature_ids: list[str] | None = None,
) -> dict[str, Any]:
    return TimingProvenance.from_row(row).as_bundle_member(
        market_content_hash=market_content_hash,
        feature_definition_ids=_FEATURE_IDS if feature_ids is None else feature_ids,
    )


def test_the_extraction_reproduces_the_pre_refactor_member_key_for_key() -> None:
    """Whole-dict equality, not a spot-check: a spot-check lets a DROPPED key pass."""
    row = _Row()

    assert _projected(row) == _MAIN_INLINE_MEMBER(row, _MARKET_HASH, _FEATURE_IDS)


def test_the_extraction_leaves_the_member_hash_byte_identical() -> None:
    """The byte claim in the units the bundle is actually addressed by.

    Not redundant with dict equality, for the R1 reason: this runs the real
    canonicaliser, so a future change to key ordering or ``None`` encoding cannot
    move the wire identity while dict equality still holds."""
    row = _Row()

    assert manifest_hash(_projected(row)) == manifest_hash(
        _MAIN_INLINE_MEMBER(row, _MARKET_HASH, _FEATURE_IDS)
    )


def test_the_member_hashes_identically_inside_a_sealed_body() -> None:
    """One level up — where ``_seal_bundle`` actually hashes it.

    ``bundle_hash = manifest_hash(body)`` over a body whose ``members`` is a LIST of
    these dicts. A projection can be correct standing alone and still be spliced in
    at the wrong depth, so the nesting is asserted rather than assumed."""
    row = _Row()
    extracted = {"members": [_projected(row)], "compiler_version": "research-bundle-v2"}
    inline = {
        "members": [_MAIN_INLINE_MEMBER(row, _MARKET_HASH, _FEATURE_IDS)],
        "compiler_version": "research-bundle-v2",
    }

    assert manifest_hash(extracted) == manifest_hash(inline)


@pytest.mark.parametrize(
    "column,value",
    [
        ("available_delay_seconds", None),
        ("frequency_policy", "continuous"),
        ("source_timezone_iana", "Europe/Istanbul"),
        ("usage_scope", None),
        ("instrument_mapping_ref", None),
        ("linked_market_dataset_revision_id", None),
    ],
)
def test_byte_identity_holds_across_the_nullable_columns(column: str, value: Any) -> None:
    """One row is one sample; the ``None``/value boundary is where a mapper drifts."""
    row = _Row(**{column: value})

    assert _projected(row) == _MAIN_INLINE_MEMBER(row, _MARKET_HASH, _FEATURE_IDS)
    assert manifest_hash(_projected(row)) == manifest_hash(
        _MAIN_INLINE_MEMBER(row, _MARKET_HASH, _FEATURE_IDS)
    )


def test_an_absent_market_link_still_projects_a_null_hash() -> None:
    """``link.market_content_hash if link else None`` — the no-link branch.

    The caller keeps this branch (it needs the session); the projection must carry a
    ``None`` through rather than dropping the key, because a MISSING key and a null
    key hash differently and the bundle publishes the difference."""
    row = _Row()

    member = _projected(row, market_content_hash=None)

    assert member["market_content_hash"] is None
    assert "market_content_hash" in member
    assert member == _MAIN_INLINE_MEMBER(row, None, _FEATURE_IDS)


def test_an_empty_feature_list_is_carried_not_dropped() -> None:
    """A revision with no feature definitions publishes ``[]``, never a missing key."""
    row = _Row()

    member = _projected(row, feature_ids=[])

    assert member["feature_definition_ids"] == []
    assert member == _MAIN_INLINE_MEMBER(row, _MARKET_HASH, [])


def test_the_published_key_set_is_named_and_matches_what_is_projected() -> None:
    """``BUNDLE_MEMBER_KEYS`` must not rot into decoration."""
    assert set(_projected(_Row())) == BUNDLE_MEMBER_KEYS
    assert set(_MAIN_INLINE_MEMBER(_Row(), _MARKET_HASH, _FEATURE_IDS)) == BUNDLE_MEMBER_KEYS


def test_the_bundle_member_carries_none_of_the_manifest_only_fields() -> None:
    """The two projections are siblings, not the same dict under two names.

    The value object holds the union of every surface's needs, so the standing
    temptation is to project everything it carries. ``revision_state``,
    ``category_key``, ``field_definition_version`` and ``validation_status`` were
    never in the shipped bundle; adding any of them would move every ``bundle_hash``
    under a refactor's cover — and would need a ``compiler_version`` bump to be
    honest about it."""
    member = _projected(_Row())

    for manifest_only in (
        "revision_state",
        "category_key",
        "field_definition_version",
        "validation_status",
        "entity_id",
    ):
        assert manifest_only not in member


def test_the_two_projections_disagree_on_names_but_never_on_values() -> None:
    """The bundle spells three ids its own way; the VALUES must still match.

    This is the property R2 buys. Before it, the two surfaces re-derived the same
    columns independently and a drift between them was possible with nothing
    comparing them."""
    row = _Row()
    timing = TimingProvenance.from_row(row)
    member = _projected(row)
    manifest = timing.as_manifest_revision(feature_definitions=[])

    assert member["research_revision_id"] == timing.revision_id
    assert member["research_content_hash"] == manifest["content_hash"]
    assert member["market_dataset_revision_id"] == manifest["linked_market_dataset_revision_id"]
    for shared in (
        "usage_scope",
        "available_time_policy",
        "available_delay_seconds",
        "event_time_semantics",
        "frequency_policy",
        "source_timezone_mode",
        "source_timezone_iana",
        "instrument_mapping_ref",
    ):
        assert member[shared] == manifest[shared]


def test_the_proof_fails_when_a_key_is_dropped() -> None:
    """Negative control: without it, a projection that lost a key would still pass."""
    row = _Row()
    mutated = dict(_projected(row))
    del mutated["source_timezone_mode"]

    assert mutated != _MAIN_INLINE_MEMBER(row, _MARKET_HASH, _FEATURE_IDS)
    assert manifest_hash(mutated) != manifest_hash(
        _MAIN_INLINE_MEMBER(row, _MARKET_HASH, _FEATURE_IDS)
    )


def test_the_proof_fails_when_a_key_is_renamed_to_the_manifest_spelling() -> None:
    """Second negative control, aimed at the likeliest 'consistency' improvement.

    Unifying the bundle's ``research_revision_id`` onto the manifest's
    ``revision_id`` reads like tidying and would re-hash every bundle."""
    row = _Row()
    mutated = dict(_projected(row))
    mutated["revision_id"] = mutated.pop("research_revision_id")

    assert manifest_hash(mutated) != manifest_hash(
        _MAIN_INLINE_MEMBER(row, _MARKET_HASH, _FEATURE_IDS)
    )
