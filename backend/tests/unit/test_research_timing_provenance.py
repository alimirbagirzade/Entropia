"""R1 — the timing vocabulary is extracted, and the extraction moves ZERO bytes.

The deliverable of this slice is not the value object; it is the proof that
introducing it changed nothing on the wire. ``_research_entries`` feeds
``data_time_context`` -> ``execution_content`` -> ``execution_key``
(``domain/backtest/manifest.py:258``), so a single added, dropped or renamed key in
the revision sub-dict re-partitions the reuse namespace of every stored Result while
changing no engine number at all — the most expensive possible refactor bug, and a
completely silent one.

``_MAIN_INLINE_REVISION`` below is a VERBATIM transcription of the dict literal that
stood at ``backtest_run_context.py`` before the extraction (``origin/main``
``2a314ae``, lines 375-397). It is deliberately hand-copied rather than imported:
importing the new code to test the new code proves only that a function equals
itself. This transcription is the independent witness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from entropia.domain.research_data.timing_provenance import (
    MANIFEST_REVISION_KEYS,
    TimingProvenance,
)
from entropia.shared.manifest import manifest_hash


@dataclass
class _Row:
    """A ``research_dataset_revision`` row, shaped structurally (never the ORM model).

    Values are deliberately mixed: real-looking tokens for the enum columns, ``None``
    for two nullable ones, and ``0`` for ``available_delay_seconds`` — because ``0``
    and ``None`` are different availability facts and a projection that collapses
    falsy values would pass a fixture built only from truthy ones.
    """

    revision_id: str = "rdrev_01ABC"
    entity_id: str = "rd_01ROOT"
    revision_state: Any = "ACTIVE"
    validation_status: Any = "passed"
    category_key: str | None = "macro.rates"
    field_definition_version: int | None = 3
    linked_market_dataset_revision_id: str | None = "mdrev_01LINK"
    instrument_mapping_ref: str | None = "map/v2"
    event_time_semantics: Any = "event_time"
    available_time_policy: Any = "delayed"
    available_delay_seconds: int | None = 0
    frequency_policy: Any = None
    source_timezone_mode: Any = "declared"
    source_timezone_iana: str | None = None
    usage_scope: Any = "execution_allowed"
    content_hash: str = "c" * 64


def _enum(value: Any) -> str | None:
    """``backtest_run_context._enum``, transcribed as it stood before the extraction."""
    return None if value is None else str(value)


def _MAIN_INLINE_REVISION(revision: _Row, features: list[dict[str, Any]]) -> dict[str, Any]:
    """The pre-extraction literal, verbatim. Do NOT refactor this into the new code."""
    return {
        "entity_id": revision.entity_id,
        "revision_state": str(revision.revision_state),
        "category_key": revision.category_key,
        "usage_scope": _enum(revision.usage_scope),
        "content_hash": revision.content_hash,
        "available_time_policy": _enum(revision.available_time_policy),
        "available_delay_seconds": revision.available_delay_seconds,
        "event_time_semantics": _enum(revision.event_time_semantics),
        "frequency_policy": _enum(revision.frequency_policy),
        "source_timezone_mode": _enum(revision.source_timezone_mode),
        "source_timezone_iana": revision.source_timezone_iana,
        "linked_market_dataset_revision_id": revision.linked_market_dataset_revision_id,
        "instrument_mapping_ref": revision.instrument_mapping_ref,
        "field_definition_version": revision.field_definition_version,
        "feature_definitions": features,
    }


_FEATURES: list[dict[str, Any]] = [
    {
        "feature_definition_id": "feat_01",
        "feature_name": "carry",
        "feature_version": 2,
        "content_hash": "f" * 64,
        "approval_state": "APPROVED",
    }
]


def _projected(row: _Row) -> dict[str, Any]:
    return TimingProvenance.from_row(row).as_manifest_revision(feature_definitions=_FEATURES)


def test_the_extraction_reproduces_the_pre_refactor_dict_key_for_key() -> None:
    """Equality of the whole dict, not a spot-check of a few fields.

    Asserting a handful of keys would let a DROPPED key pass, which is precisely the
    failure mode that silently shifts ``execution_key``."""
    row = _Row()

    assert _projected(row) == _MAIN_INLINE_REVISION(row, _FEATURES)


def test_the_extraction_leaves_the_manifest_hash_byte_identical() -> None:
    """The byte claim, stated in the units that actually matter.

    Dict equality already implies hash equality, so this is not redundant with the
    test above for the SAME reason a golden digest is not redundant with a unit test:
    it pins the claim at the layer ``execution_key`` is computed on, through the real
    canonicaliser, so a future change to ``canonical_json`` (key ordering, number or
    ``None`` encoding) cannot move the wire identity while dict equality still holds.
    """
    row = _Row()

    assert manifest_hash(_projected(row)) == manifest_hash(_MAIN_INLINE_REVISION(row, _FEATURES))


def test_the_projection_is_hashed_identically_inside_a_data_time_context() -> None:
    """The same claim one level up — where the dict is actually consumed.

    ``_research_entries`` returns a LIST whose members carry the sub-dict, and that
    list lands in ``data_time_context`` inside ``execution_content``. Nesting is
    asserted explicitly because a projection can be correct standing alone and still
    be spliced in at the wrong depth."""
    row = _Row()
    extracted = [{"role": "funding_source", "revision": _projected(row)}]
    inline = [{"role": "funding_source", "revision": _MAIN_INLINE_REVISION(row, _FEATURES)}]

    assert manifest_hash({"data_time_context": extracted}) == manifest_hash(
        {"data_time_context": inline}
    )


@pytest.mark.parametrize(
    "column,value",
    [
        ("available_delay_seconds", None),
        ("frequency_policy", "continuous"),
        ("source_timezone_iana", "Europe/Istanbul"),
        ("category_key", None),
        ("usage_scope", None),
        ("field_definition_version", None),
    ],
)
def test_byte_identity_holds_across_the_nullable_columns(column: str, value: Any) -> None:
    """One row is one sample. The ``None``/value boundary is where a mapper drifts.

    ``available_delay_seconds`` flipping between ``0`` and ``None`` is the sharp case:
    both are falsy, they mean different things, and ``canonical_json`` encodes them
    differently."""
    row = _Row(**{column: value})

    assert _projected(row) == _MAIN_INLINE_REVISION(row, _FEATURES)
    assert manifest_hash(_projected(row)) == manifest_hash(_MAIN_INLINE_REVISION(row, _FEATURES))


def test_the_published_key_set_is_named_and_matches_what_is_projected() -> None:
    """``MANIFEST_REVISION_KEYS`` must not rot into decoration.

    It exists so a future field addition has to edit a constant that says out loud
    what it costs; a constant nothing compares against would not do that."""
    assert set(_projected(_Row())) == MANIFEST_REVISION_KEYS
    assert set(_MAIN_INLINE_REVISION(_Row(), _FEATURES)) == MANIFEST_REVISION_KEYS


def test_validation_status_is_absent_from_the_manifest_projection() -> None:
    """Ready Check reads it; the manifest never did.

    The value object carries the union of both surfaces' needs, so the tempting
    mistake is to project everything it holds. That would add a key to a hashed dict
    — an ``execution_key`` change wearing a refactor's clothes."""
    row = _Row(validation_status="failed")

    assert TimingProvenance.from_row(row).validation_status == "failed"
    assert "validation_status" not in _projected(row)


def test_the_proof_fails_when_a_key_is_dropped() -> None:
    """Negative control for the three assertions above.

    Without this, a projection that silently lost a key would still satisfy a suite
    that only ever compares the projection to itself."""
    row = _Row()
    mutated = dict(_projected(row))
    del mutated["frequency_policy"]

    assert mutated != _MAIN_INLINE_REVISION(row, _FEATURES)
    assert manifest_hash(mutated) != manifest_hash(_MAIN_INLINE_REVISION(row, _FEATURES))


def test_the_proof_fails_when_a_nullable_enum_is_pre_parsed() -> None:
    """Second negative control, aimed at the likeliest 'improvement'.

    Normalising ``None`` to ``""`` (or to the string ``"None"``) reads harmless and is
    exactly the change that would re-hash every manifest. Both surfaces require the
    RAW persisted value."""
    row = _Row(frequency_policy=None)
    mutated = dict(_projected(row))
    mutated["frequency_policy"] = ""

    assert manifest_hash(mutated) != manifest_hash(_MAIN_INLINE_REVISION(row, _FEATURES))


def test_ready_check_reads_the_same_vocabulary_as_the_manifest() -> None:
    """The point of the extraction: one row cannot yield two readings.

    Ready Check's ``ResearchSourceState`` and the manifest sub-dict overlap on six
    fields. Before R1 each was derived by hand, so a drift between them was possible
    and nothing compared them. Now they come from one object — asserted here so a
    future edit that re-inlines either side is caught."""
    row = _Row()
    timing = TimingProvenance.from_row(row)
    manifest = _projected(row)

    assert timing.revision_state == manifest["revision_state"]
    assert timing.usage_scope == manifest["usage_scope"]
    assert timing.available_time_policy == manifest["available_time_policy"]
    assert timing.available_delay_seconds == manifest["available_delay_seconds"]
    assert timing.linked_market_dataset_revision_id == manifest["linked_market_dataset_revision_id"]
    assert timing.instrument_mapping_ref == manifest["instrument_mapping_ref"]


def test_the_value_object_is_frozen() -> None:
    """A shared reading that a caller can mutate is not a shared reading."""
    timing = TimingProvenance.from_row(_Row())

    with pytest.raises((AttributeError, TypeError)):
        timing.available_delay_seconds = 99  # type: ignore[misc]
