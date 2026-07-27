"""Publish-time package dependency-graph resolution + cycle gate (doc 08 §10, §13, §14).

Doc 08 §13 requires the dependency graph to be *"resolved with exact revision
references and cycle-detected BEFORE publish/use"* and §14 fixes the acceptance:
a publish attempt that creates an ``A -> B -> A`` path is rejected by the SERVER
with a diagnostic that identifies the cycle path — the UI is never the gate.

This module is the read side of that guard. It walks the pinned dependency refs of
a candidate revision through the immutable ``package_revision`` rows, projects the
walk onto package ROOTS, and hands the adjacency to the pure
``domain.package.dependency_graph`` for detection.

Resolution rules (all fail-closed):

* The revision row is authoritative for its root (``PackageRevision.entity_id``), so
  a snapshot that names a root which does not own the pinned revision can never
  widen the graph past the truth on disk.
* A root-only claim (no pinned revision) resolves to that root's CURRENT head — the
  edge a name-only reference would take.
* A claim naming a root that does not exist still contributes its edge. It cannot
  invent a cycle (a loop needs that root to be a real ancestor on the walk) but it
  can never hide one either.
* A pinned revision that cannot be loaded ends the walk on that leg. Unresolved
  dependencies are a DIFFERENT gate (``PACKAGE_DEPENDENCY_UNRESOLVED``, doc 08 §10);
  this one only ever reports cycles.

Termination is guaranteed by the visited-revision set: every revision row is
expanded at most once, and the table is finite.
"""

from __future__ import annotations

from collections import deque

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.package.dependency_graph import (
    PackageRef,
    extract_package_refs,
    find_dependency_cycle,
)
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import PackageDependencyCycle


async def collect_root_edges(
    session: AsyncSession,
    *,
    revision_id: str,
) -> dict[str, tuple[str, ...]]:
    """Materialize the root-level adjacency reachable from ``revision_id``.

    Returns ``{source_root_id: (target_root_id, ...)}`` with declaration order kept
    and duplicates collapsed, so the cycle path a caller reports is deterministic.
    """
    edges: dict[str, list[str]] = {}
    expanded: set[str] = set()
    frontier: deque[str] = deque([revision_id])

    while frontier:
        current_revision_id = frontier.popleft()
        if current_revision_id in expanded:
            continue
        expanded.add(current_revision_id)
        revision = await pkg_repo.get_revision(session, current_revision_id)
        if revision is None:
            continue
        for ref in extract_package_refs(revision.dependency_snapshot):
            target_root, target_revision_id = await _resolve_ref(session, ref)
            if target_root is None:
                continue
            # ``entity_id`` is the revision's owning root — the authoritative source
            # of the edge, never the claim's own idea of who owns it.
            targets = edges.setdefault(revision.entity_id, [])
            if target_root not in targets:
                targets.append(target_root)
            if target_revision_id is not None:
                frontier.append(target_revision_id)

    return {source: tuple(targets) for source, targets in edges.items()}


async def ensure_no_dependency_cycle(
    session: AsyncSession,
    *,
    root_id: str,
    revision_id: str,
) -> None:
    """Reject a publish whose pinned dependency graph closes a loop (doc 08 §14).

    The ONE guard both publish surfaces call (Package Library Approve & Publish and
    the Create Package approval). Raises ``PackageDependencyCycle`` (409) carrying
    the closed root-id path; the candidate revision is never mutated, so the draft
    survives for repair.
    """
    edges = await collect_root_edges(session, revision_id=revision_id)
    cycle_path = find_dependency_cycle(root_id, edges)
    if cycle_path is not None:
        raise PackageDependencyCycle(cycle_path, scope_id=revision_id)


async def _resolve_ref(
    session: AsyncSession,
    ref: PackageRef,
) -> tuple[str | None, str | None]:
    """Normalize a raw claim to ``(root_id, pinned_revision_id)``."""
    if ref.revision_id is not None:
        revision = await pkg_repo.get_revision(session, ref.revision_id)
        if revision is not None:
            return revision.entity_id, revision.revision_id
    if ref.root_id is not None:
        root = await pkg_repo.get_package_root(session, ref.root_id)
        if root is None:
            # An unknown root is kept as an edge: it cannot close a loop on its own,
            # and dropping it would let a dangling claim mask one.
            return ref.root_id, None
        return root.entity_id, root.current_revision_id
    return None, None


__all__ = ["collect_root_edges", "ensure_no_dependency_cycle"]
