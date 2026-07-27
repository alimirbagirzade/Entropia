"""Package dependency graph reader + cycle detection (doc 08 §9.1, §10, §13, §14).

Pure and side-effect free. The caller materializes the pinned dependency edges out
of the database; this module answers ONE question — does the dependency graph close
a loop (``A -> B -> A``)? — and names the exact roots on that loop, because doc 08
§14 "Dependency cycle" requires more than a bare rejection: *"Server rejects publish;
diagnostic identifies cycle path; UI preserves draft for repair."*

Two independent pieces:

``extract_package_refs``
    Reads the package-to-package claims out of an immutable
    ``package_revision.dependency_snapshot``. That snapshot is a free-form JSONB
    document (the Create Revision API accepts a caller-supplied one), so the reader
    is deliberately tolerant about SHAPE but strict about KEYS: only canonical
    package-scoped identifiers count as a package edge. Embedded System Package
    resolver refs (``embedded_entity_id`` / ``embedded_revision_id``, doc 09) pin a
    DIFFERENT registry and are never package edges.

``find_dependency_cycle``
    Iterative DFS over the ROOT graph. Roots — not revisions — are the cycle
    granularity: package revisions are immutable, so a mutual dependency normally
    pins a different revision number on each leg and only shows up as ``A -> B -> A``
    once projected onto roots. Root granularity is also the fail-closed choice; it
    can only reject more than a revision-level walk, never less. A revision that
    pins any revision of its own root is therefore a one-element self-cycle.

Recursion is explicit (an iterative stack), so a pathologically deep chain raises
no ``RecursionError``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

# Snapshot keys whose value is a LIST of dependency entries. ``resolved`` is the
# Pre-Check scan's frozen resolver list (doc 07 §8); its ESP entries carry
# ``embedded_*`` ids and are skipped by the key filter below, but a package-scoped
# entry parked in the same list is still read.
_REF_COLLECTION_KEYS: Final[tuple[str, ...]] = (
    "packages",
    "package_refs",
    "package_dependencies",
    "resolved",
)

# Canonical package-ROOT identifiers. ``linked_indicator_package_root_id`` is the
# Explicit Indicator Link a Condition package pins (doc 06 §4: "the saved dependency
# is the root and revision identifier").
_ROOT_ID_KEYS: Final[tuple[str, ...]] = (
    "package_root_id",
    "target_root_id",
    "linked_indicator_package_root_id",
)

# Canonical package-REVISION identifiers (never name-only / "latest", doc 08 §13).
_REVISION_ID_KEYS: Final[tuple[str, ...]] = (
    "package_revision_id",
    "target_revision_id",
    "linked_indicator_package_revision_id",
)


@dataclass(frozen=True)
class PackageRef:
    """A raw package-to-package dependency claim read out of a snapshot.

    Both ids are optional individually (a claim may name only the root or only the
    pinned revision) but at least one is always present — ``extract_package_refs``
    never emits an empty ref. ``origin`` records the snapshot key path the claim came
    from so a diagnostic can point at the offending field.
    """

    root_id: str | None
    revision_id: str | None
    origin: str


def extract_package_refs(dependency_snapshot: object) -> tuple[PackageRef, ...]:
    """Return every package-to-package claim in ``dependency_snapshot``, in order.

    A non-mapping snapshot (``None``, a list, a scalar) yields no refs rather than
    raising — an unreadable snapshot declares no package dependency, and the
    unresolved-dependency contract (``PACKAGE_DEPENDENCY_UNRESOLVED``, doc 08 §10) is
    a separate gate. Claims are returned in declaration order so the reported cycle
    path is deterministic.
    """
    if not isinstance(dependency_snapshot, Mapping):
        return ()
    refs: list[PackageRef] = []
    # A snapshot may carry the Explicit Indicator Link at the top level.
    _append_ref(refs, dependency_snapshot, origin="dependency_snapshot")
    for key in _REF_COLLECTION_KEYS:
        entries = dependency_snapshot.get(key)
        if not isinstance(entries, (list, tuple)):
            continue
        for index, entry in enumerate(entries):
            if isinstance(entry, Mapping):
                _append_ref(refs, entry, origin=f"{key}[{index}]")
    return tuple(refs)


def find_dependency_cycle(
    start_root_id: str,
    edges: Mapping[str, Sequence[str]],
) -> tuple[str, ...] | None:
    """Return the closed cycle path reachable from ``start_root_id``, else ``None``.

    ``edges`` maps a package root id to the root ids it depends on, in declaration
    order. The returned path is closed — ``("a", "b", "a")`` for ``A -> B -> A``,
    ``("a", "a")`` for a self-reference — so the diagnostic reads as a path rather
    than a set. The FIRST cycle encountered in declaration order wins, which makes
    the result stable for a given graph.
    """
    on_path: set[str] = {start_root_id}
    path: list[str] = [start_root_id]
    # A root whose whole subtree was explored without closing a loop can never be
    # part of one later (standard DFS back-edge argument), so it is never re-walked.
    finished: set[str] = set()
    stack: list[tuple[str, int]] = [(start_root_id, 0)]

    while stack:
        root_id, index = stack[-1]
        targets = edges.get(root_id, ())
        if index >= len(targets):
            stack.pop()
            finished.add(root_id)
            on_path.discard(path.pop())
            continue
        stack[-1] = (root_id, index + 1)
        target = targets[index]
        if target in on_path:
            return (*path[path.index(target) :], target)
        if target in finished:
            continue
        path.append(target)
        on_path.add(target)
        stack.append((target, 0))
    return None


def _append_ref(refs: list[PackageRef], mapping: Mapping[str, Any], *, origin: str) -> None:
    root_id = _first_identifier(mapping, _ROOT_ID_KEYS)
    revision_id = _first_identifier(mapping, _REVISION_ID_KEYS)
    if root_id is None and revision_id is None:
        return
    refs.append(PackageRef(root_id=root_id, revision_id=revision_id, origin=origin))


def _first_identifier(mapping: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


__all__ = ["PackageRef", "extract_package_refs", "find_dependency_cycle"]
