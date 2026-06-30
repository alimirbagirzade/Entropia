"""Mainboard composition fingerprint + CR-01 kind guard (doc 01 §5.2, §9.3-9.4).

The ``composition_hash`` is the engine-meaningful fingerprint of a workspace's
composition. A Ready Check report (Stage 4) is valid only while the hash it was
computed against is unchanged.

NON-CANONICAL GAP RESOLUTION — composition_hash definition
----------------------------------------------------------
DOMAIN_MODEL/doc 01 fix the *semantics* of when the fingerprint must change but
do not pin its byte layout. We resolve it as:

    composition_hash(enabled_items) =
        manifest_hash({"composition": sorted_tuples})

where ``sorted_tuples`` is the list of ``{"kind", "root_id", "revision_id"}``
projections for ENABLED items only, sorted by ``(root_id, revision_id)``.

The fingerprint deliberately EXCLUDES ``position_index``,
``display_label_override``, and disabled items. Consequences (doc 01 §5.2 "order
is presentation only, not engine priority"; §9.3 label-only/reorder => No):

* add / soft-delete / enable-toggle / pin-change  => hash CHANGES => prior Ready
  report becomes STALE.
* reorder / label-only / expand-collapse          => hash UNCHANGED => report
  stays valid.

An empty enabled set still produces a deterministic (non-null) hash so callers
can persist and compare it uniformly.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.shared.errors import MainboardItemKindMismatchError
from entropia.shared.manifest import manifest_hash


@dataclass(frozen=True, slots=True)
class CompositionMember:
    """An enabled composition member contributing to the fingerprint.

    ``position_index`` and label overrides are intentionally NOT part of this
    structure — they never influence the engine-meaningful fingerprint.
    """

    kind: MainboardItemKind | str
    root_id: str
    revision_id: str


def _member_tuple(member: CompositionMember) -> dict[str, str]:
    kind = member.kind.value if isinstance(member.kind, MainboardItemKind) else str(member.kind)
    return {"kind": kind, "root_id": member.root_id, "revision_id": member.revision_id}


def composition_hash(enabled_items: Iterable[CompositionMember]) -> str:
    """Return the deterministic fingerprint over the ENABLED members only.

    Members are normalized to ``{kind, root_id, revision_id}`` and sorted by
    ``(root_id, revision_id)`` so the hash is independent of insertion/display
    order. An empty iterable yields a stable empty-composition hash.
    """
    tuples: Sequence[dict[str, str]] = sorted(
        (_member_tuple(item) for item in enabled_items),
        key=lambda m: (m["root_id"], m["revision_id"]),
    )
    return manifest_hash({"composition": list(tuples)})


def assert_item_kind_matches(
    item_kind: MainboardItemKind | str,
    object_kind: MainboardItemKind | str,
) -> None:
    """CR-01 kind guard: a working item's kind must equal its root's object kind.

    Raises ``MainboardItemKindMismatchError`` (422) on any divergence. Comparison
    is exact enum-value equality — never name/substring matching.
    """
    item_value = item_kind.value if isinstance(item_kind, MainboardItemKind) else str(item_kind)
    object_value = (
        object_kind.value if isinstance(object_kind, MainboardItemKind) else str(object_kind)
    )
    if item_value != object_value:
        raise MainboardItemKindMismatchError(
            f"Item kind {item_value!r} does not match work object kind {object_value!r}.",
            details=[{"field": "item_kind", "expected": object_value, "actual": item_value}],
        )
