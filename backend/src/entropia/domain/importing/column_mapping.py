"""Pure column-mapping resolution for delimited source imports (doc 04 §5.1,
doc 05 §5.2/§5.4).

INFRA-FREE + deterministic. Given the parsed header row, a canonical field
catalog, a built-in header-alias table and an OPTIONAL explicit
``{canonical_field -> source_header}`` mapping, decide which source column feeds
each canonical field so files whose headers are NOT already the exact canonical
names can still be imported.

Two hard rules straight from the spec:

* **"Server cannot infer an ambiguous mapping."** When a canonical field is not
  present under its own (case-normalized) name and MORE THAN ONE source column
  aliases to it, resolution fails closed with ``AMBIGUOUS_COLUMN_MAPPING`` — the
  server never guesses which column was meant. The caller must supply an explicit
  mapping to disambiguate.
* **An explicit mapping wins** over the alias table and over case-normalization.
  An explicit entry referencing a missing source column, or an unknown canonical
  field, fails closed with ``INVALID_COLUMN_MAPPING``.

Only the parsed in-memory header/rows are renamed; the immutable raw source asset
is never touched. Resolution is a pure function so both importers unit-test it
without a database or object storage.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

# --- whole-file blocker codes (surfaced by both importers) -------------------
BLOCKER_AMBIGUOUS_COLUMN_MAPPING = "AMBIGUOUS_COLUMN_MAPPING"
BLOCKER_INVALID_COLUMN_MAPPING = "INVALID_COLUMN_MAPPING"


@dataclass(frozen=True, slots=True)
class MappingResolution:
    """Outcome of resolving a header row against the canonical field catalog.

    ``rename`` maps each ACTUAL source header that must be renamed to its canonical
    field (identity matches are omitted). ``resolved`` is the effective
    ``canonical_field -> actual_source_header`` map for every field that resolved
    (identity included) — the evidence hashed into ``mapping_hash``. A non-empty
    ``blocker_code`` means resolution failed closed and nothing may be renamed.
    """

    rename: dict[str, str] = field(default_factory=dict)
    resolved: dict[str, str] = field(default_factory=dict)
    blocker_code: str | None = None
    detail: str | None = None

    @property
    def applied(self) -> bool:
        """True when a real (non-identity) rename or explicit mapping was used."""
        return bool(self.rename)


def resolve_column_mapping(
    columns: list[str],
    *,
    canonical_fields: tuple[str, ...],
    alias_table: dict[str, str],
    explicit_mapping: dict[str, str] | None,
) -> MappingResolution:
    """Resolve which source column feeds each canonical field (pure, fail-closed).

    Precedence per canonical field: explicit mapping > case-normalized exact header
    > exactly-one aliased header. Two or more aliased candidates → AMBIGUOUS; an
    explicit entry that names a missing source column or an unknown canonical field
    → INVALID. Fields with no resolution are simply absent (a required-column
    blocker is the downstream importer's concern, unchanged).
    """
    lower_to_actual: dict[str, str] = {}
    for col in columns:
        key = col.strip().lower()
        lower_to_actual.setdefault(key, col)  # first occurrence wins on a dup header
    canonical_set = set(canonical_fields)
    explicit = dict((explicit_mapping or {}).items())

    invalid = _validate_explicit(explicit, canonical_set, lower_to_actual)
    if invalid is not None:
        return MappingResolution(blocker_code=BLOCKER_INVALID_COLUMN_MAPPING, detail=invalid)

    # A source column named by an explicit mapping is reserved for that field — the
    # alias resolver must never steal it for a different canonical.
    explicit_targets = {(source or "").strip().lower() for source in explicit.values()}

    rename: dict[str, str] = {}
    resolved: dict[str, str] = {}
    for canonical in canonical_fields:
        if canonical in explicit:
            actual = lower_to_actual[explicit[canonical].strip().lower()]
        elif canonical in lower_to_actual:
            actual = lower_to_actual[canonical]
        else:
            candidates = sorted(
                actual
                for low, actual in lower_to_actual.items()
                if low not in canonical_set
                and low not in explicit_targets
                and alias_table.get(low) == canonical
            )
            if len(candidates) > 1:
                return MappingResolution(
                    blocker_code=BLOCKER_AMBIGUOUS_COLUMN_MAPPING,
                    detail=(
                        f"{canonical!r} matches multiple source columns {candidates}; "
                        "supply an explicit column mapping to disambiguate."
                    ),
                )
            if not candidates:
                continue
            actual = candidates[0]
        resolved[canonical] = actual
        if actual != canonical:
            rename[actual] = canonical
    return MappingResolution(rename=rename, resolved=resolved)


def _validate_explicit(
    explicit: dict[str, str],
    canonical_set: set[str],
    lower_to_actual: dict[str, str],
) -> str | None:
    for canonical, source in explicit.items():
        if canonical not in canonical_set:
            return f"Unknown canonical field {canonical!r} in the column mapping."
        if (source or "").strip().lower() not in lower_to_actual:
            return f"Column mapping references source column {source!r}, which is not in the file."
    return None


def apply_rename(rows: list[dict[str, str]], rename: dict[str, str]) -> list[dict[str, str]]:
    """Return rows with each mapped source key moved onto its canonical key (pure).

    Ambiguity/clobber is impossible here: ``resolve_column_mapping`` only renames a
    source header onto a canonical whose exact name was absent, and distinct sources
    map to distinct canonicals.
    """
    if not rename:
        return rows
    remapped: list[dict[str, str]] = []
    for row in rows:
        new = dict(row)
        for source, canonical in rename.items():
            if source in new:
                new[canonical] = new.pop(source)
        remapped.append(new)
    return remapped


def rename_columns(columns: list[str], rename: dict[str, str]) -> list[str]:
    """Return the header list with mapped source headers replaced by canonical names."""
    if not rename:
        return columns
    return [rename.get(col, col) for col in columns]


def mapping_hash(resolved: dict[str, str]) -> str:
    """Deterministic evidence hash over the effective canonical->source mapping."""
    parts = [f"{canonical}={source}" for canonical, source in sorted(resolved.items())]
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


__all__ = [
    "BLOCKER_AMBIGUOUS_COLUMN_MAPPING",
    "BLOCKER_INVALID_COLUMN_MAPPING",
    "MappingResolution",
    "apply_rename",
    "mapping_hash",
    "rename_columns",
    "resolve_column_mapping",
]
