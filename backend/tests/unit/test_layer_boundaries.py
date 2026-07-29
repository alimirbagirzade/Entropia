"""Layer-direction and import-cycle guard for the ``entropia`` package (I-04).

``shared`` is the bottom layer: it may not import ``domain``, ``application``,
``infrastructure``, or ``apps``. Before I-04 this was violated by
``shared.idempotency`` and ``shared.manifest``, which both reached up into
``domain.revision.hashing`` for the canonical-JSON serializer; the serializer
now lives in ``shared.hashing`` and ``domain.revision.hashing`` re-exports it.

The scan is static (AST) and looks only at *executed* module-level imports:
``if TYPE_CHECKING:`` blocks and function-local imports are skipped, because
neither can raise ImportError at import time.
"""

from __future__ import annotations

import ast
import pathlib
from collections import defaultdict

import entropia

PACKAGE = "entropia"
SOURCE_ROOT = pathlib.Path(entropia.__file__).parent

# A layer may import anything to its left, never anything to its right.
FORBIDDEN_DIRECTIONS = frozenset(
    {
        ("shared", "domain"),
        ("shared", "application"),
        ("shared", "infrastructure"),
        ("shared", "apps"),
        ("domain", "application"),
        ("domain", "infrastructure"),
        ("domain", "apps"),
        ("application", "apps"),
    }
)


def _module_name(path: pathlib.Path) -> str:
    parts = list(path.relative_to(SOURCE_ROOT.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _is_type_checking_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _executed_imports(path: pathlib.Path) -> set[str]:
    """In-package targets imported when this module is executed."""
    targets: set[str] = set()
    for node in ast.parse(path.read_text(encoding="utf-8"), str(path)).body:
        if _is_type_checking_guard(node):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.ImportFrom):
                if sub.level == 0 and sub.module and sub.module.startswith(PACKAGE):
                    targets.add(sub.module)
            elif isinstance(sub, ast.Import):
                targets.update(a.name for a in sub.names if a.name.startswith(PACKAGE))
    return targets


def _build_graph() -> dict[str, set[str]]:
    raw = {
        _module_name(path): _executed_imports(path) for path in sorted(SOURCE_ROOT.rglob("*.py"))
    }

    def resolve(target: str) -> str | None:
        """Map an import target onto the module that actually defines it."""
        parts = target.split(".")
        while parts:
            candidate = ".".join(parts)
            if candidate in raw:
                return candidate
            parts.pop()
        return None

    graph: dict[str, set[str]] = defaultdict(set)
    for module, targets in raw.items():
        graph[module] = {
            resolved
            for resolved in (resolve(t) for t in targets)
            if resolved is not None and resolved != module
        }
    return graph


def _layer(module: str) -> str:
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else "<root>"


def _strongly_connected_components(graph: dict[str, set[str]]) -> list[list[str]]:
    """Iterative Tarjan — recursion would blow the stack on a 373-module graph."""
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[list[str]] = []
    counter = 0

    for root in sorted(graph):
        if root in index:
            continue
        index[root] = lowlink[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(sorted(graph.get(root, ()))))]

        while work:
            node, successors = work[-1]
            descended = False
            for successor in successors:
                if successor not in index:
                    index[successor] = lowlink[successor] = counter
                    counter += 1
                    stack.append(successor)
                    on_stack.add(successor)
                    work.append((successor, iter(sorted(graph.get(successor, ())))))
                    descended = True
                    break
                if successor in on_stack:
                    lowlink[node] = min(lowlink[node], index[successor])
            if descended:
                continue

            work.pop()
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
            if lowlink[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(component)

    return components


def test_shared_is_the_bottom_layer() -> None:
    """No module in ``shared`` may import a higher layer (I-04 regression)."""
    graph = _build_graph()
    violations = sorted(
        f"{module} -> {target}"
        for module, targets in graph.items()
        for target in targets
        if (_layer(module), _layer(target)) in FORBIDDEN_DIRECTIONS and _layer(module) == "shared"
    )
    assert violations == [], "shared/ must not import a higher layer: " + "; ".join(violations)


def test_no_layer_direction_is_inverted() -> None:
    """The full layer order shared < domain < application < apps holds."""
    graph = _build_graph()
    violations = sorted(
        f"{module} -> {target}"
        for module, targets in graph.items()
        for target in targets
        if (_layer(module), _layer(target)) in FORBIDDEN_DIRECTIONS
    )
    assert violations == [], "inverted layer imports: " + "; ".join(violations)


def test_import_graph_has_no_cycles() -> None:
    """Zero circular dependencies — keep it that way."""
    graph = _build_graph()
    cycles = [
        sorted(component)
        for component in _strongly_connected_components(graph)
        if len(component) > 1 or component[0] in graph.get(component[0], set())
    ]
    assert cycles == [], f"circular imports detected: {cycles}"


def test_hashing_re_export_is_the_same_object() -> None:
    """``domain.revision.hashing`` must delegate, not fork a second hasher."""
    from entropia.domain.revision import hashing as domain_hashing
    from entropia.shared import hashing as shared_hashing

    assert domain_hashing.canonical_json is shared_hashing.canonical_json
    assert domain_hashing.content_hash is shared_hashing.content_hash
