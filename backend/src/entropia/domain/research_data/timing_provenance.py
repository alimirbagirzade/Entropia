"""The ONE spelling of a Research revision's timing provenance (R1, doc 12 §9.1/§9.2).

The question *"which availability rule was this compiled under?"* was answered
independently on every surface that had to answer it, each re-deriving the same
columns off a ``research_dataset_revision`` row by hand:

* the Run manifest, via ``commands/backtest_run_context.py::_research_entries``;
* Ready Check, via ``commands/readiness_check.py::_resolve_research_sources``,
  whose docstring already conceded it was *"deliberately identical"* to the first.

Two hand-copies of one vocabulary is not a style problem. ``_research_entries``
feeds ``data_time_context`` -> ``execution_content`` -> ``execution_key``
(``domain/backtest/manifest.py``), so a field that drifts between the surfaces does
not merely read oddly: Ready Check admits a run against one reading of the timing
rules while the manifest pins another, and the divergence is invisible because
nothing compares them.

This module is that comparison point. It carries the columns verbatim — no parsing,
no normalisation, no defaults — because every consumer needs the RAW persisted value
(the ``ResearchSourceState`` rule: a row written under an older enum member must
still reach the validator and be *judged* rather than explode during resolution).

**Why this is a value object and not a mapper.** ``from_row`` is the only place the
column-to-token transformation is written. The manifest projection reproduces the
previously inlined sub-dict **key for key and transformation for transformation**;
:mod:`tests.unit.test_research_timing_provenance` pins that the resulting
``execution_key`` is byte-identical, because a shifted key would re-partition the
reuse namespace of every stored Result without changing a single engine number.

**Layer.** ``domain/`` is pure (``BACKEND_LAYERS.md``: *"saf, I/O yok"*, locked by
``tests/unit/test_layer_boundaries.py``), so the ORM row is accepted structurally
through :class:`ResearchRevisionRow` rather than imported — the
``domain/package/export_contract.py::_ResolverContractRow`` idiom.

**Package.** It joins the existing ``domain/research_data/`` package rather than
opening a near-homonym beside it: the timing columns it reads are the same ones
``time_policy.py`` and ``value_objects.py`` already reason about, and two packages
named ``research`` and ``research_data`` would be a coin flip at every import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ResearchRevisionRow(Protocol):
    """The ``research_dataset_revision`` columns the timing vocabulary is read from."""

    revision_id: str
    entity_id: str
    revision_state: Any
    validation_status: Any
    category_key: str | None
    field_definition_version: int | None
    linked_market_dataset_revision_id: str | None
    instrument_mapping_ref: str | None
    event_time_semantics: Any
    available_time_policy: Any
    available_delay_seconds: int | None
    frequency_policy: Any
    source_timezone_mode: Any
    source_timezone_iana: str | None
    usage_scope: Any
    content_hash: str


def _token(value: Any) -> str | None:
    """The raw persisted string of a NULLABLE enum column, never a parsed object.

    ``readiness_check._enum_value`` was this function under another name and is gone;
    ``backtest_run_context._enum`` was its twin but SURVIVES, because that module
    still spells the *market* dataset's enums (``resolution_kind``, ``timezone_mode``,
    ``record_time_basis``) and market-data provenance is a different vocabulary that
    this slice does not claim. Two helpers with one body was the symptom; the disease
    was two readings of the RESEARCH columns, and only that is cured here.

    ``None`` stays ``None``: an absent policy and a policy spelled ``"None"`` are
    different facts, and the manifest publishes the difference.
    """
    return None if value is None else str(value)


@dataclass(frozen=True, slots=True)
class TimingProvenance:
    """One revision's timing/provenance vocabulary, read once and spelled once.

    Every field is the RAW persisted value. ``revision_state`` and ``content_hash``
    are non-nullable columns and are therefore plain ``str``; everything else is
    nullable and passes through :func:`_token` or straight through.
    """

    revision_id: str
    entity_id: str
    revision_state: str
    validation_status: str | None
    category_key: str | None
    field_definition_version: int | None
    linked_market_dataset_revision_id: str | None
    instrument_mapping_ref: str | None
    event_time_semantics: str | None
    available_time_policy: str | None
    available_delay_seconds: int | None
    frequency_policy: str | None
    source_timezone_mode: str | None
    source_timezone_iana: str | None
    usage_scope: str | None
    content_hash: str

    @classmethod
    def from_row(cls, row: ResearchRevisionRow) -> TimingProvenance:
        """Read the vocabulary off one revision row.

        ``revision_state`` is stringified unconditionally rather than through
        :func:`_token` because its column is NOT NULL — preserving exactly what the
        two call sites did, which is what keeps ``execution_key`` byte-identical.
        """
        return cls(
            revision_id=row.revision_id,
            entity_id=row.entity_id,
            revision_state=str(row.revision_state),
            validation_status=_token(row.validation_status),
            category_key=row.category_key,
            field_definition_version=row.field_definition_version,
            linked_market_dataset_revision_id=row.linked_market_dataset_revision_id,
            instrument_mapping_ref=row.instrument_mapping_ref,
            event_time_semantics=_token(row.event_time_semantics),
            available_time_policy=_token(row.available_time_policy),
            available_delay_seconds=row.available_delay_seconds,
            frequency_policy=_token(row.frequency_policy),
            source_timezone_mode=_token(row.source_timezone_mode),
            source_timezone_iana=row.source_timezone_iana,
            usage_scope=_token(row.usage_scope),
            content_hash=row.content_hash,
        )

    def as_manifest_revision(self, *, feature_definitions: list[dict[str, Any]]) -> dict[str, Any]:
        """The Run manifest's ``research_datasets[].revision`` sub-dict.

        **The key set is a wire contract, not a convenience.** This dict is hashed
        into ``execution_key`` (``manifest.py::build_manifest`` ->
        ``execution_content.data_time_context``), so adding, dropping or renaming a
        key here re-partitions the reuse namespace of every stored Result. Two
        surfaces publish a superset/subset of this vocabulary and neither may quietly
        diverge; ``validation_status`` is deliberately ABSENT because the manifest
        never carried it, and adding it here would be a silent ``execution_key``
        change wearing a refactor's clothes.

        ``feature_definitions`` stays a parameter: it needs a second dereference
        (``list_feature_definitions``), and this layer performs no I/O.
        """
        return {
            "entity_id": self.entity_id,
            "revision_state": self.revision_state,
            "category_key": self.category_key,
            "usage_scope": self.usage_scope,
            "content_hash": self.content_hash,
            "available_time_policy": self.available_time_policy,
            "available_delay_seconds": self.available_delay_seconds,
            "event_time_semantics": self.event_time_semantics,
            "frequency_policy": self.frequency_policy,
            "source_timezone_mode": self.source_timezone_mode,
            "source_timezone_iana": self.source_timezone_iana,
            "linked_market_dataset_revision_id": self.linked_market_dataset_revision_id,
            "instrument_mapping_ref": self.instrument_mapping_ref,
            "field_definition_version": self.field_definition_version,
            "feature_definitions": feature_definitions,
        }

    def as_bundle_member(
        self,
        *,
        market_content_hash: str | None,
        feature_definition_ids: list[str],
    ) -> dict[str, Any]:
        """One Research Data bundle member (doc 12 §9.1/§9.2, Karar 2 = A1+A2).

        **The same values under different names, deliberately.** The bundle spells
        three of them its own way — ``research_revision_id``, ``research_content_hash``
        and ``market_dataset_revision_id`` — because a bundle member sits beside
        *market* members and has to say which side each id belongs to, whereas the
        manifest's ``revision`` sub-dict is already nested under a research feed and
        does not. Renaming either surface to match the other would be a wire change,
        not a tidy-up. What must never differ is the VALUE, and that is exactly what
        routing both through this object buys.

        **This dict is hashed into ``bundle_hash``** (``jobs/research_data.py::
        _seal_bundle`` -> ``manifest_hash``), so the key set is a wire contract on
        this surface too. It carries the six timing fields the Run manifest pins plus
        ``instrument_mapping_ref``; ``_seal_bundle`` derives doc 12 §9.2's flat
        top-level arrays from these members, which stay authoritative (O-30 idiom).

        Fields the row cannot answer stay parameters, because this layer performs no
        I/O: ``market_content_hash`` needs the market link, and
        ``feature_definition_ids`` a second dereference. ``revision_state``,
        ``category_key``, ``field_definition_version`` and ``validation_status`` are
        deliberately ABSENT — the shipped bundle never carried them, and adding one
        here would move every ``bundle_hash`` under a refactor's cover.
        """
        return {
            "research_revision_id": self.revision_id,
            "research_content_hash": self.content_hash,
            "usage_scope": self.usage_scope,
            "market_dataset_revision_id": self.linked_market_dataset_revision_id,
            "market_content_hash": market_content_hash,
            "available_time_policy": self.available_time_policy,
            "available_delay_seconds": self.available_delay_seconds,
            "event_time_semantics": self.event_time_semantics,
            "frequency_policy": self.frequency_policy,
            "source_timezone_mode": self.source_timezone_mode,
            "source_timezone_iana": self.source_timezone_iana,
            "instrument_mapping_ref": self.instrument_mapping_ref,
            "feature_definition_ids": feature_definition_ids,
        }


BUNDLE_MEMBER_KEYS: frozenset[str] = frozenset(
    {
        "research_revision_id",
        "research_content_hash",
        "usage_scope",
        "market_dataset_revision_id",
        "market_content_hash",
        "available_time_policy",
        "available_delay_seconds",
        "event_time_semantics",
        "frequency_policy",
        "source_timezone_mode",
        "source_timezone_iana",
        "instrument_mapping_ref",
        "feature_definition_ids",
    }
)
"""The exact key set :meth:`TimingProvenance.as_bundle_member` publishes.

The bundle twin of :data:`MANIFEST_REVISION_KEYS`, and named for the same reason:
this set is hashed into ``bundle_hash``, so growing it costs a ``compiler_version``
bump and a re-partitioned hash space. A test compares against it so the constant
cannot rot into decoration.
"""


MANIFEST_REVISION_KEYS: frozenset[str] = frozenset(
    {
        "entity_id",
        "revision_state",
        "category_key",
        "usage_scope",
        "content_hash",
        "available_time_policy",
        "available_delay_seconds",
        "event_time_semantics",
        "frequency_policy",
        "source_timezone_mode",
        "source_timezone_iana",
        "linked_market_dataset_revision_id",
        "instrument_mapping_ref",
        "field_definition_version",
        "feature_definitions",
    }
)
"""The exact key set :meth:`TimingProvenance.as_manifest_revision` publishes.

Named so a test can assert the wire shape without re-listing it, and so a future
field addition has to touch a constant that says out loud what it costs.
"""


__all__ = [
    "BUNDLE_MEMBER_KEYS",
    "MANIFEST_REVISION_KEYS",
    "ResearchRevisionRow",
    "TimingProvenance",
]
