#!/usr/bin/env python3
"""Semantic acceptance traceability scanner — a GATE, not a report.

`acceptance_id_scan.py` (its sibling) answers a weaker question: *does any test
file contain the string `PC-19`?* A docstring mentioning an ID satisfies that
scan, which makes "coverage" a claim about text rather than about behaviour.

This scanner reads `docs/audit/acceptance_semantic_map.yaml` — a hand-authored,
clause-level mapping from every acceptance criterion in `docs/spec/01..22` to the
**real test node ids** that exercise it — and refuses to pass when the map lies
about itself. It never infers coverage; it only refuses to let an unbacked claim
stand.

What makes it fail (exit 1):

  * a duplicate criterion or clause id
  * an evidence node id whose FILE does not exist
  * an evidence node id whose FUNCTION / CLASS / test title does not exist
  * `status: covered` (or `partial`) with no evidence at all
  * evidence attached to a status that asserts there is none
    (`uncovered`, `not_applicable`, `product_decision_required`)
  * a status outside the fixed vocabulary
  * a criterion status that contradicts its own clause statuses
  * axis evidence (`auth`, `occ`, ...) that is not also listed in `test_evidence`
  * `evidence_type` that disagrees with where the node actually lives
  * a server-truth axis proven only by a jsdom render, or `async_recovery`
    proven only by a unit test  (see AXIS_RULES)

Resolution is STATIC — `ast` for Python, title extraction for vitest/playwright.
No database, no test run, no network: this is safe to run as a fast CI gate and
its verdict cannot drift with the environment.

Usage (from the repo root):
    python3 docs/audit/acceptance_semantic_scan.py            # gate
    python3 docs/audit/acceptance_semantic_scan.py --report   # gate + coverage tables
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

import yaml

MAP_PATH = "docs/audit/acceptance_semantic_map.yaml"

# --------------------------------------------------------------------------
# Vocabulary

STATUSES = (
    "covered",
    "partial",
    "uncovered",
    "deliberate_future_dev",
    "not_applicable",
    "product_decision_required",
)

#: Statuses that assert evidence EXISTS. Anything here with an empty
#: `test_evidence` is the exact failure this scanner was written to catch.
STATUSES_REQUIRING_EVIDENCE = ("covered", "partial")

#: Statuses that assert there is NO evidence. Attaching a node id to one of these
#: is a contradiction: if a test proves it, the criterion is not uncovered.
STATUSES_FORBIDDING_EVIDENCE = ("uncovered", "not_applicable", "product_decision_required")

#: Statuses whose whole content is a judgement call, so they must be argued.
STATUSES_REQUIRING_NOTES = (
    "partial",
    "uncovered",
    "deliberate_future_dev",
    "not_applicable",
    "product_decision_required",
)

#: evidence_type -> the path prefix a node of that type must live under. This is
#: what stops "unit test" from being claimed for an integration file (and back).
EVIDENCE_TYPE_ROOTS = {
    "backend_unit": ("backend/tests/unit/",),
    "backend_integration": ("backend/tests/integration/",),
    "backend_contract": ("backend/tests/contract/",),
    "backend_deterministic": ("backend/tests/deterministic/",),
    "backend_acceptance": ("backend/tests/acceptance/",),
    "frontend_component": ("frontend/src/",),
    "e2e": ("frontend/e2e/",),
}

BACKEND_ROOT = "backend/tests/"
#: A durable-recovery claim needs a test that actually crosses a process/tx
#: boundary. A unit test can prove a pure function retries; it cannot prove a
#: QUEUED row survives and is redelivered.
DURABLE_ROOTS = ("backend/tests/integration/", "backend/tests/contract/")

#: axis -> (predicate on a node id, human reason). Encodes the brief's rule:
#: "UI render does not prove backend policy; a unit test does not prove durable
#: recovery; a domain command does not prove the Gateway literal."
AXIS_RULES: dict[str, tuple[tuple[str, ...], str]] = {
    "auth": ((BACKEND_ROOT,), "server-side authorization cannot be proven by a rendered UI"),
    "occ": ((BACKEND_ROOT,), "optimistic-concurrency tokens are a server contract"),
    "idempotency": ((BACKEND_ROOT,), "Idempotency-Key replay is a server contract"),
    "historical_integrity": ((BACKEND_ROOT,), "pinned/manifest integrity is a server contract"),
    "agent_parity": ((BACKEND_ROOT,), "the Agent has no browser; parity is a server-side claim"),
    "async_recovery": (DURABLE_ROOTS, "durable queue recovery needs an integration/contract test"),
}

AXES = (
    "positive",
    "negative",
    "auth",
    "occ",
    "idempotency",
    "async_recovery",
    "historical_integrity",
    "agent_parity",
)

REQUIRED_FIELDS = (
    "id",
    "document",
    "section",
    "summary",
    "clauses",
    "production_paths",
    "test_evidence",
    "evidence_type",
    "status",
    "notes",
)


# --------------------------------------------------------------------------
# Test-node resolution


@dataclass
class Violation:
    code: str
    where: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return f"[{self.code}] {self.where}: {self.message}"


PY_PARAM_RE = re.compile(r"\[.*\]$")
JS_TITLE_RE = re.compile(
    r"""\b(?:describe|it|test)(?:\.\w+)*\s*\(\s*(?P<q>["'`])(?P<t>(?:\\.|(?!(?P=q)).)*)(?P=q)""",
    re.S,
)
JS_ESCAPE_RE = re.compile(r"\\(.)")
JS_INTERPOLATION_RE = re.compile(r"\$\{[^}]*\}")


@dataclass
class TestIndex:
    """Static index of every addressable test node in the repo."""

    root: str = "."
    py_symbols: dict[str, set[tuple[str, ...]]] = field(default_factory=dict)
    js_titles: dict[str, tuple[set[str], list[re.Pattern[str]]]] = field(default_factory=dict)

    def _abs(self, rel: str) -> str:
        return os.path.join(self.root, rel)

    def file_exists(self, rel: str) -> bool:
        return os.path.isfile(self._abs(rel))

    def python_symbols(self, rel: str) -> set[tuple[str, ...]]:
        if rel not in self.py_symbols:
            try:
                tree = ast.parse(open(self._abs(rel), encoding="utf-8").read())
            except (OSError, SyntaxError):
                self.py_symbols[rel] = set()
                return self.py_symbols[rel]
            found: set[tuple[str, ...]] = set()

            def walk(node: ast.AST, prefix: tuple[str, ...]) -> None:
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                        path = (*prefix, child.name)
                        found.add(path)
                        walk(child, path)

            walk(tree, ())
            self.py_symbols[rel] = found
        return self.py_symbols[rel]

    def js_test_titles(self, rel: str) -> tuple[set[str], list[re.Pattern[str]]]:
        """Literal titles, plus regexes for the `it(\\`${x} …\\`)` interpolated ones.

        `it.each`-style titles are template literals, so the title vitest reports
        is only known at run time. Matching them as patterns keeps a real,
        runnable node id resolvable instead of forcing the map to avoid those
        files. A title that is ENTIRELY interpolation is dropped rather than
        turned into `.+` — a pattern that matches everything would resolve
        node ids that do not exist, which is the failure this gate exists to
        prevent.
        """
        if rel not in self.js_titles:
            try:
                text = open(self._abs(rel), encoding="utf-8").read()
            except OSError:
                self.js_titles[rel] = (set(), [])
                return self.js_titles[rel]
            literals: set[str] = set()
            patterns: list[re.Pattern[str]] = []
            for match in JS_TITLE_RE.finditer(text):
                raw = JS_ESCAPE_RE.sub(r"\1", match.group("t"))
                if "${" not in raw:
                    literals.add(raw)
                    continue
                parts = JS_INTERPOLATION_RE.split(raw)
                if not any(part.strip() for part in parts):
                    continue
                patterns.append(
                    re.compile("^" + ".+?".join(re.escape(part) for part in parts) + "$")
                )
            self.js_titles[rel] = (literals, patterns)
        return self.js_titles[rel]

    # ------------------------------------------------------------------
    def resolve(self, node_id: str) -> str | None:
        """Return None when the node id resolves, else a reason string."""
        if not isinstance(node_id, str) or not node_id.strip():
            return "empty node id"
        if "::" in node_id:
            path, _, tail = node_id.partition("::")
            segments = tail.split("::")
            sep = "::"
        elif " > " in node_id:
            path, _, tail = node_id.partition(" > ")
            segments = tail.split(" > ")
            sep = " > "
        else:
            return (
                "node id has no test selector — expected 'path::function' (pytest) "
                "or 'path > title' (vitest/playwright)"
            )
        path = path.strip()
        if not self.file_exists(path):
            return f"file does not exist: {path}"
        if path.endswith(".py"):
            if sep != "::":
                return "python node ids use '::', not ' > '"
            segments = [PY_PARAM_RE.sub("", s).strip() for s in segments]
            if tuple(segments) in self.python_symbols(path):
                return None
            # A parametrized id may name only the function; the chain check above
            # already covers that. Anything left is genuinely absent.
            return f"no such function/class in {path}: {'::'.join(segments)}"
        if sep != " > ":
            return "javascript node ids use ' > ', not '::'"
        literals, patterns = self.js_test_titles(path)
        for segment in (seg.strip() for seg in segments):
            if segment in literals:
                continue
            if any(pattern.match(segment) for pattern in patterns):
                continue
            return f"no such describe/it title in {path}: {segment!r}"
        return None


# --------------------------------------------------------------------------
# Validation


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _node_path(node: Any) -> str:
    """The file part of a node id, or "" when the entry is not a node id at all.

    A YAML author who forgets to quote a node id containing ``": "`` gets a dict
    instead of a string (vitest titles routinely contain colons). That must
    surface as a violation, not an AttributeError — a gate that crashes on bad
    input teaches people to route around it.
    """
    if not isinstance(node, str):
        return ""
    return node.split("::")[0].split(" > ")[0].strip()


def _rank(status: str) -> int:
    """Order used to check a criterion does not out-claim its own clauses."""
    return {"covered": 3, "partial": 2}.get(status, 1)


def validate(document: Any, index: TestIndex) -> list[Violation]:
    out: list[Violation] = []
    if not isinstance(document, dict):
        return [Violation("BAD_ROOT", MAP_PATH, "top level must be a mapping")]
    criteria = document.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return [Violation("BAD_ROOT", MAP_PATH, "`criteria:` must be a non-empty list")]

    seen_ids: dict[str, int] = {}
    seen_clause_ids: dict[str, str] = {}

    for position, record in enumerate(criteria):
        where = f"criteria[{position}]"
        if not isinstance(record, dict):
            out.append(Violation("BAD_RECORD", where, "record must be a mapping"))
            continue
        cid = record.get("id")
        if isinstance(cid, str) and cid:
            where = cid
            if cid in seen_ids:
                out.append(
                    Violation(
                        "DUPLICATE_ID", cid, f"id already used at criteria[{seen_ids[cid]}]"
                    )
                )
            else:
                seen_ids[cid] = position
        else:
            out.append(Violation("MISSING_FIELD", where, "`id` is required and must be a string"))

        for name in REQUIRED_FIELDS:
            if name not in record:
                out.append(Violation("MISSING_FIELD", where, f"`{name}` is required"))

        status = record.get("status")
        if status not in STATUSES:
            out.append(
                Violation(
                    "UNKNOWN_STATUS",
                    where,
                    f"status {status!r} is not one of {', '.join(STATUSES)}",
                )
            )
            status = None

        doc_path = record.get("document")
        if isinstance(doc_path, str) and not index.file_exists(doc_path):
            out.append(Violation("UNKNOWN_DOCUMENT", where, f"no such spec file: {doc_path}"))

        notes = record.get("notes")
        if status in STATUSES_REQUIRING_NOTES and not (isinstance(notes, str) and notes.strip()):
            out.append(
                Violation(
                    "NOTES_REQUIRED",
                    where,
                    f"status {status!r} is a judgement call and must be argued in `notes`",
                )
            )

        evidence = _as_list(record.get("test_evidence"))
        evidence_types = _as_list(record.get("evidence_type"))
        for node in evidence:
            reason = index.resolve(node)
            if reason:
                out.append(Violation("UNRESOLVED_NODE", where, f"{node!r} — {reason}"))
        for etype in evidence_types:
            if etype not in EVIDENCE_TYPE_ROOTS:
                out.append(
                    Violation("UNKNOWN_EVIDENCE_TYPE", where, f"unknown evidence_type {etype!r}")
                )
        # Every node must be explained by one of the declared evidence types, and
        # every declared type must actually be used. Both directions matter: the
        # first stops an undeclared surface sneaking in, the second stops a record
        # advertising an integration test it does not cite.
        for node in evidence:
            path = _node_path(node)
            matched = [
                t
                for t in evidence_types
                if t in EVIDENCE_TYPE_ROOTS and path and path.startswith(EVIDENCE_TYPE_ROOTS[t])
            ]
            if not matched:
                out.append(
                    Violation(
                        "EVIDENCE_TYPE_MISMATCH",
                        where,
                        f"{path} is not covered by any declared evidence_type "
                        f"({', '.join(evidence_types) or 'none'})",
                    )
                )
        for etype in evidence_types:
            if etype not in EVIDENCE_TYPE_ROOTS:
                continue
            if not any(
                _node_path(node).startswith(EVIDENCE_TYPE_ROOTS[etype])
                for node in evidence
                if _node_path(node)
            ):
                out.append(
                    Violation(
                        "EVIDENCE_TYPE_MISMATCH",
                        where,
                        f"evidence_type {etype!r} is declared but no cited node lives there",
                    )
                )

        if status in STATUSES_REQUIRING_EVIDENCE and not evidence:
            out.append(
                Violation(
                    "EMPTY_EVIDENCE",
                    where,
                    f"status {status!r} claims coverage but cites no test node — "
                    "a comment or docstring mentioning the ID is not evidence",
                )
            )
        if status in STATUSES_FORBIDDING_EVIDENCE and evidence:
            out.append(
                Violation(
                    "EVIDENCE_ON_EMPTY_STATUS",
                    where,
                    f"status {status!r} asserts nothing proves this, but {len(evidence)} "
                    "node(s) are cited",
                )
            )

        # ---- axes
        # Only hashable (string) entries; a malformed one is already reported as an
        # UNRESOLVED_NODE above, and set() would raise on an unquoted-YAML dict.
        evidence_set = {node for node in evidence if isinstance(node, str)}
        for axis in AXES:
            nodes = _as_list(record.get(axis))
            for node in nodes:
                if not isinstance(node, str):
                    out.append(
                        Violation(
                            "UNRESOLVED_NODE",
                            where,
                            f"`{axis}` entry is not a node id: {node!r} — an unquoted "
                            'YAML scalar containing ": " parses as a mapping',
                        )
                    )
                elif node not in evidence_set:
                    out.append(
                        Violation(
                            "AXIS_NOT_IN_EVIDENCE",
                            where,
                            f"`{axis}` cites {node!r}, which is absent from `test_evidence`",
                        )
                    )
            if not nodes or axis not in AXIS_RULES:
                continue
            roots, reason = AXIS_RULES[axis]
            if not any(_node_path(n).startswith(roots) for n in nodes if _node_path(n)):
                seen_paths = sorted({_node_path(n) or repr(n)[:60] for n in nodes})
                out.append(
                    Violation(
                        "AXIS_EVIDENCE_TOO_WEAK",
                        where,
                        f"`{axis}` is proven only by {seen_paths} — {reason}",
                    )
                )
        if status == "covered" and not (
            _as_list(record.get("positive")) or _as_list(record.get("negative"))
        ):
            out.append(
                Violation(
                    "POSITIVE_NEGATIVE_MISSING",
                    where,
                    "a covered criterion must say whether the happy path, the rejection "
                    "path, or both were proven (`positive` / `negative`)",
                )
            )

        # ---- clauses
        clauses = record.get("clauses")
        if not isinstance(clauses, list) or not clauses:
            out.append(
                Violation("NO_CLAUSES", where, "`clauses` must list at least one clause")
            )
            continue
        clause_statuses: list[str] = []
        for ci, clause in enumerate(clauses):
            cwhere = f"{where}.clauses[{ci}]"
            if not isinstance(clause, dict):
                out.append(Violation("BAD_CLAUSE", cwhere, "clause must be a mapping"))
                continue
            clid = clause.get("id")
            if not isinstance(clid, str) or not clid:
                out.append(Violation("MISSING_FIELD", cwhere, "clause `id` is required"))
            elif clid in seen_clause_ids:
                out.append(
                    Violation(
                        "DUPLICATE_CLAUSE_ID",
                        cwhere,
                        f"clause id {clid!r} already used by {seen_clause_ids[clid]}",
                    )
                )
            else:
                seen_clause_ids[clid] = where
                cwhere = clid
            if not str(clause.get("text", "")).strip():
                out.append(Violation("MISSING_FIELD", cwhere, "clause `text` is required"))
            cstatus = clause.get("status")
            if cstatus not in STATUSES:
                out.append(
                    Violation("UNKNOWN_STATUS", cwhere, f"clause status {cstatus!r} is invalid")
                )
                continue
            clause_statuses.append(cstatus)
            cev = _as_list(clause.get("test_evidence"))
            for node in cev:
                reason = index.resolve(node)
                if reason:
                    out.append(Violation("UNRESOLVED_NODE", cwhere, f"{node!r} — {reason}"))
                elif node not in evidence_set:
                    out.append(
                        Violation(
                            "AXIS_NOT_IN_EVIDENCE",
                            cwhere,
                            f"clause cites {node!r}, which is absent from the criterion's "
                            "`test_evidence`",
                        )
                    )
            if cstatus in STATUSES_REQUIRING_EVIDENCE and not cev:
                out.append(
                    Violation(
                        "EMPTY_EVIDENCE",
                        cwhere,
                        f"clause status {cstatus!r} claims coverage but cites no test node",
                    )
                )
            if cstatus in STATUSES_FORBIDDING_EVIDENCE and cev:
                out.append(
                    Violation(
                        "EVIDENCE_ON_EMPTY_STATUS",
                        cwhere,
                        f"clause status {cstatus!r} asserts nothing proves this, but "
                        f"{len(cev)} node(s) are cited",
                    )
                )

        # A criterion may not out-claim its own clauses: `covered` requires every
        # clause covered, and a criterion with a covered clause is at least partial.
        if status and clause_statuses:
            if status == "covered" and not all(c == "covered" for c in clause_statuses):
                weak = sorted({c for c in clause_statuses if c != "covered"})
                out.append(
                    Violation(
                        "STATUS_CLAUSE_MISMATCH",
                        where,
                        f"status 'covered' but clause statuses include {', '.join(weak)} — "
                        "a criterion with an unproven clause is at most `partial`",
                    )
                )
            # `deliberate_future_dev` is exempt: it is the one status where evidence is
            # EXPECTED, because the thing being proven is that the capability stays
            # inert — no fake job, no fake output, no silent fallback. A covered
            # inertness clause does not make the criterion partially delivered.
            if (
                _rank(status) < 2
                and status != "deliberate_future_dev"
                and any(c in ("covered", "partial") for c in clause_statuses)
            ):
                out.append(
                    Violation(
                        "STATUS_CLAUSE_MISMATCH",
                        where,
                        f"status {status!r} but at least one clause is proven — "
                        "that makes the criterion `partial`",
                    )
                )
    return out


# --------------------------------------------------------------------------
# Report


REPORT_PREAMBLE = """<!-- GENERATED FILE — do not edit by hand.
     Regenerate with:
       cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py \\
           --root .. --write-report docs/audit/acceptance_semantic_traceability.md
     The source of truth is docs/audit/acceptance_semantic_map.yaml. -->

# Semantic acceptance traceability — coverage report

Every number below is derived from `docs/audit/acceptance_semantic_map.yaml`, which
maps each acceptance criterion in `docs/spec/01..22` to the **test node ids** that
assert it, clause by clause. `docs/audit/acceptance_semantic_scan.py` re-resolves
every cited node against the live test tree and fails CI when one is absent, when a
criterion claims coverage it cannot cite, or when a server-truth axis rests on a
rendered UI.

> **This is not a project-completion percentage.** It measures one thing: how much
> of the written acceptance contract is tied to a test that actually asserts it. A
> criterion counted `uncovered` here may well be implemented correctly — the claim
> is only that nothing in the suite proves it. Reading these tables as "the product
> is N% done" is a category error.

Its predecessor, `acceptance_id_scan.py`, asked whether the string `PC-19` appeared
anywhere in a test file. A docstring satisfied it. Nothing below is satisfied by a
comment.

## Scope boundary — what these tables do NOT cover

The map covers every acceptance row in the **page documents** `docs/spec/01..22`,
which are the canonical per-page acceptance contract.

It does **not** yet cover the module-level acceptance tables inside
`docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md` — 21 sections titled
"Kabul Kriterleri" / "Kabul Testleri" / "Acceptance tests". Those are the upstream
originals the page documents restate (Master §11.3, for example, maps onto doc 08's
Package Library rows), but the wording differs and some rows have no page
equivalent, so they are a second corpus rather than a duplicate. Mapping them is
tracked as follow-up work; they are named here so their absence is visible rather
than silently counted as covered.

`docs/E2E_ACCEPTANCE.md` and the stage handoff documents are likewise out of scope
for this map.

"""


def report(document: dict[str, Any]) -> str:
    criteria = document["criteria"]
    lines: list[str] = []
    by_doc: dict[str, Counter[str]] = defaultdict(Counter)
    by_type: Counter[str] = Counter()
    overall: Counter[str] = Counter()
    clause_overall: Counter[str] = Counter()
    for record in criteria:
        doc = str(record.get("document", "?")).split("/")[-1][:2]
        by_doc[doc][record["status"]] += 1
        overall[record["status"]] += 1
        for etype in _as_list(record.get("evidence_type")):
            by_type[etype] += 1
        for clause in _as_list(record.get("clauses")):
            if isinstance(clause, dict):
                clause_overall[clause.get("status", "?")] += 1

    lines.append("## Coverage by document\n")
    lines.append("| Doc | " + " | ".join(STATUSES) + " | total |")
    lines.append("|---" * (len(STATUSES) + 2) + "|")
    for doc in sorted(by_doc):
        row = by_doc[doc]
        lines.append(
            f"| {doc} | "
            + " | ".join(str(row.get(s, 0)) for s in STATUSES)
            + f" | {sum(row.values())} |"
        )
    lines.append(
        "| **all** | "
        + " | ".join(f"**{overall.get(s, 0)}**" for s in STATUSES)
        + f" | **{sum(overall.values())}** |"
    )
    lines.append("\n## Clause-level totals\n")
    lines.append("| Status | Clauses |")
    lines.append("|---|---|")
    for s in STATUSES:
        lines.append(f"| {s} | {clause_overall.get(s, 0)} |")
    lines.append(f"| **total** | **{sum(clause_overall.values())}** |")
    lines.append("\n## Criteria citing each evidence type\n")
    lines.append("| Evidence type | Criteria |")
    lines.append("|---|---|")
    for etype in sorted(by_type):
        lines.append(f"| {etype} | {by_type[etype]} |")

    for label, wanted in (("partial", "partial"), ("uncovered", "uncovered")):
        rows = [r for r in criteria if r["status"] == wanted]
        lines.append(f"\n## {label.title()} criteria ({len(rows)})\n")
        if not rows:
            lines.append("_none_")
            continue
        lines.append("| ID | Summary | Why |")
        lines.append("|---|---|---|")
        for r in rows:
            note = " ".join(str(r.get("notes", "")).split())
            lines.append(f"| `{r['id']}` | {r['summary']} | {note} |")
    return "\n".join(lines)


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", default=MAP_PATH)
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", action="store_true", help="print coverage tables")
    parser.add_argument(
        "--write-report",
        metavar="PATH",
        help="regenerate the human-readable traceability report at PATH",
    )
    args = parser.parse_args(argv)

    path = os.path.join(args.root, args.map)
    if not os.path.isfile(path):
        print(f"FAIL: no semantic map at {path}", file=sys.stderr)
        return 1
    with open(path, encoding="utf-8") as fh:
        document = yaml.safe_load(fh)

    violations = validate(document, TestIndex(root=args.root))
    if violations:
        print(f"FAIL: {len(violations)} violation(s) in {args.map}\n", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        print(
            "\nA criterion is covered when a named test node exercises it. "
            "A comment is not a test.",
            file=sys.stderr,
        )
        return 1

    total = len(document["criteria"])
    clauses = sum(len(_as_list(r.get("clauses"))) for r in document["criteria"])
    print(f"OK: {total} criteria / {clauses} clauses validate against the live test tree")
    if args.write_report:
        target = os.path.join(args.root, args.write_report)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(REPORT_PREAMBLE)
            fh.write(report(document))
            fh.write("\n")
        print(f"wrote {args.write_report}")
    if args.report:
        print()
        print(report(document))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
