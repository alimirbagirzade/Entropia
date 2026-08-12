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
  * a `partial`/`uncovered` criterion with no `debt_class`, or a settled one carrying one

What makes `--ratchet` fail (exit 1):

  * the count of `partial` / `uncovered` criteria, or of any A/B/C/D debt class,
    rising above the frozen ceiling in `docs/audit/acceptance_coverage_baseline.json`
  * the criteria corpus SHRINKING below its frozen size — deleting an inconvenient
    row must not read as progress

The validator proves the map does not lie about itself. It does NOT bound how much
of the contract is unproven, which is how 131 partial + 8 uncovered criteria passed
green for months. `--ratchet` freezes that debt as a ceiling instead, the same trade
the a11y ratchet already makes in this repo (`frontend/e2e/a11y-baseline.json`).

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
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

import yaml

MAP_PATH = "docs/audit/acceptance_semantic_map.yaml"
BASELINE_PATH = "docs/audit/acceptance_coverage_baseline.json"

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

#: Debt taxonomy (ADIM 42 / RC §6.7 P1-Gate3). "partial" hid at least four
#: different situations behind one word, which made the aggregate number
#: unplannable: nobody can budget "131 partial" without knowing how much of it a
#: test could even close. Every partial/uncovered criterion carries exactly one:
#:
#:   A  NAME DRIFT       — the behaviour ships, under a different name than the
#:                         spec row uses. Costs an adjudication plus a one-line pin.
#:   B  TEST DEBT        — the behaviour is implemented, the assertion is missing.
#:                         A test closes it. This is the only class a test slice owns.
#:   C  NOT ASSERTABLE   — the open clause is a statement about a DOCUMENT, a
#:                         deliberately-closed V1 feature, or a scenario Production
#:                         cannot construct. To be justified, never "closed".
#:   D  IMPLEMENTATION   — the code, field, error class or Agent tool the criterion
#:                         names does not exist. NO test can close it; it needs
#:                         product work, and several need a product ruling first.
#:
#: The A/B/C/D split is the point: without it, class D debt (product work) reads as
#: test debt and gets budgeted to the wrong slice.
DEBT_CLASSES = ("A", "B", "C", "D")

#: Only open debt is classified. A `covered` row has nothing to plan, and the three
#: "settled" statuses are already argued in `notes`; forcing a class onto them would
#: invite re-litigating a closed decision at every edit.
STATUSES_REQUIRING_DEBT_CLASS = ("partial", "uncovered")

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

        # ---- debt class
        # A new `partial` row that arrives unclassified is exactly how "131 partial"
        # became an opaque number in the first place, so the gate refuses it.
        debt_class = record.get("debt_class")
        if status in STATUSES_REQUIRING_DEBT_CLASS:
            if debt_class not in DEBT_CLASSES:
                out.append(
                    Violation(
                        "DEBT_CLASS_REQUIRED",
                        where,
                        f"status {status!r} needs a `debt_class` in "
                        f"{'/'.join(DEBT_CLASSES)} — an unclassified open criterion "
                        "cannot be planned, budgeted or ratcheted",
                    )
                )
        elif debt_class is not None:
            out.append(
                Violation(
                    "DEBT_CLASS_NOT_ALLOWED",
                    where,
                    f"status {status!r} is not open debt, so it must not carry a "
                    f"`debt_class` (found {debt_class!r})",
                )
            )

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


#: Both artefacts live under `docs/audit/`, which
#: `scripts/generate_repository_facts.py::ALWAYS_HISTORICAL_GLOBS` requires to be
#: marked `historical`. The banner is emitted HERE rather than hand-prepended to the
#: output: it was hand-prepended once, and the next regeneration silently deleted it
#: and turned the documentation-truth gate red. A generated file's header has to be
#: generated too.
HISTORICAL_BANNER = """<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

"""

REPORT_PREAMBLE = HISTORICAL_BANNER + """<!-- GENERATED FILE — do not edit by hand.
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

    # Open debt by class. The status totals above say HOW MUCH is unproven; this
    # says how much of it a test could even close (B) versus how much is product
    # work wearing a coverage label (D).
    by_class: Counter[str] = Counter(
        str(r["debt_class"]) for r in criteria if r.get("debt_class")
    )
    lines.append("\n## Open debt by class\n")
    lines.append("| Class | Criteria |")
    lines.append("|---|---|")
    for cls in DEBT_CLASSES:
        lines.append(f"| {cls} | {by_class.get(cls, 0)} |")
    lines.append(f"| **open total** | **{sum(by_class.values())}** |")

    for label, wanted in (("partial", "partial"), ("uncovered", "uncovered")):
        rows = [r for r in criteria if r["status"] == wanted]
        lines.append(f"\n## {label.title()} criteria ({len(rows)})\n")
        if not rows:
            lines.append("_none_")
            continue
        lines.append("| ID | Class | Summary | Why |")
        lines.append("|---|---|---|---|")
        for r in rows:
            note = " ".join(str(r.get("notes", "")).split())
            lines.append(
                f"| `{r['id']}` | {r.get('debt_class', '?')} | {r['summary']} | {note} |"
            )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Ratchet
#
# The validator above proves the map does not LIE. It says nothing about how much
# of the contract is actually proven, so 131 partial + 8 uncovered criteria passed
# it green for months. Making those a hard failure would block every PR behind 139
# items; freezing them as a CEILING is the same trade the a11y ratchet already
# makes in this repo (frontend/e2e/a11y-baseline.json + specs/13-a11y-scan.spec.ts),
# so this reuses that shape rather than inventing a second one.


def measured_counts(document: dict[str, Any]) -> dict[str, Any]:
    """Today's debt, in the baseline file's own shape."""
    criteria = document["criteria"]
    by_status: Counter[str] = Counter(str(r.get("status")) for r in criteria)
    by_class: Counter[str] = Counter(
        str(r["debt_class"]) for r in criteria if r.get("debt_class")
    )
    return {
        "total_criteria": len(criteria),
        "status": {s: by_status.get(s, 0) for s in STATUSES_REQUIRING_DEBT_CLASS},
        "debt_class": {c: by_class.get(c, 0) for c in DEBT_CLASSES},
    }


def ratchet(document: dict[str, Any], baseline: dict[str, Any]) -> tuple[bool, list[str]]:
    """Compare today's debt against the frozen ceiling. Returns (ok, lines)."""
    measured = measured_counts(document)
    ceilings = baseline.get("ceilings")
    if not isinstance(ceilings, dict):
        return False, ["ratchet: baseline has no `ceilings` mapping"]

    failures: list[str] = []
    improvements: list[str] = []

    # Rows may be ADDED, never removed. Without this, deleting an inconvenient
    # `partial` criterion would read as progress and tighten the ceiling for free.
    floor = int(ceilings.get("total_criteria", 0))
    if measured["total_criteria"] < floor:
        failures.append(
            f"total_criteria {measured['total_criteria']} < frozen {floor} — criteria "
            "may be added but never dropped; a shrinking corpus is not progress"
        )

    for group in ("status", "debt_class"):
        frozen = ceilings.get(group)
        if not isinstance(frozen, dict):
            failures.append(f"ratchet: baseline has no `ceilings.{group}` mapping")
            continue
        for key, value in measured[group].items():
            ceiling = int(frozen.get(key, 0))
            if value > ceiling:
                failures.append(
                    f"{group}.{key}: {value} measured, ceiling {ceiling} "
                    f"(+{value - ceiling})"
                )
            elif value < ceiling:
                improvements.append(f"{group}.{key}: {value} < {ceiling}")

    lines: list[str] = []
    if failures:
        lines.append("FAIL: acceptance coverage debt grew past its frozen ceiling\n")
        lines.extend(f"  {failure}" for failure in failures)
        lines.append(
            "\nThe ceiling is a frozen debt figure, not a budget with headroom. Either "
            "cover the new criterion (cite a test node that asserts it) or argue its "
            "class in `notes` and adjudicate the raise in "
            "docs/audit/acceptance_coverage_debt_ledger.md — never widen the ceiling "
            "to make CI green."
        )
        return False, lines

    if improvements:
        lines.append(
            f"acceptance ratchet: debt fell below the ceiling on "
            f"{len(improvements)} counter(s) — re-freeze "
            "docs/audit/acceptance_coverage_baseline.json with:"
        )
        lines.extend(f"  {improvement}" for improvement in improvements)
        lines.append(json.dumps({"ceilings": measured}, indent=2))
    lines.append(
        f"acceptance ratchet OK: {measured['status']['partial']} partial / "
        f"{measured['status']['uncovered']} uncovered against a frozen ceiling of "
        f"{ceilings['status']['partial']} / {ceilings['status']['uncovered']}; "
        f"classes {measured['debt_class']}."
    )
    return True, lines


# --------------------------------------------------------------------------
# Debt ledger


LEDGER_PREAMBLE = HISTORICAL_BANNER + """<!-- GENERATED FILE — do not edit by hand.
     Regenerate with:
       cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py \\
           --root .. --write-ledger docs/audit/acceptance_coverage_debt_ledger.md
     The source of truth is docs/audit/acceptance_semantic_map.yaml. -->

# Acceptance coverage debt — the ledger

Every open acceptance criterion, sorted into the class that decides **who owns it
and what it costs**. Before this file existed the RC readiness report carried one
number — "131 partial" — and no way to act on it: a criterion whose error code was
never implemented and a criterion missing one `assert` line were the same word.

| Class | Meaning | Who closes it |
|---|---|---|
| **A** | The behaviour ships under a **different name** than the spec row uses. | An adjudication plus a one-line pin. |
| **B** | The behaviour is implemented; the **assertion is missing**. | A test slice. This is the only class a test slice owns. |
| **C** | The open clause is **not assertable** — a statement about a document, a deliberately-closed V1 feature, or a scenario Production cannot construct. | Nobody. To be justified, never "closed". |
| **D** | The code, field, error class or Agent tool the criterion **names does not exist**. | Product work — and several need a **product ruling** first. No test can close these. |

> **Class D is the finding.** Reading the aggregate as test debt budgets product
> work to a test slice. A class-D row cannot be closed by anyone writing tests, no
> matter how many are written.

The `Why` column is the criterion's own `notes` field, truncated. Read the full
argument in `acceptance_semantic_map.yaml` before planning any row.

"""


def ledger(document: dict[str, Any]) -> str:
    criteria = document["criteria"]
    open_rows = [r for r in criteria if r.get("debt_class")]
    counts = Counter(str(r["debt_class"]) for r in open_rows)
    lines = ["## Totals\n", "| Class | Criteria |", "|---|---|"]
    for cls in DEBT_CLASSES:
        lines.append(f"| {cls} | {counts.get(cls, 0)} |")
    lines.append(f"| **open total** | **{len(open_rows)}** |")

    for cls in DEBT_CLASSES:
        rows = sorted(
            (r for r in open_rows if r["debt_class"] == cls),
            key=lambda r: (str(r.get("document", "")), str(r.get("id", ""))),
        )
        lines.append(f"\n## Class {cls} ({len(rows)})\n")
        if not rows:
            lines.append("_none_")
            continue
        lines.append("| ID | Doc | Status | Summary | Why |")
        lines.append("|---|---|---|---|---|")
        for r in rows:
            doc = str(r.get("document", "?")).split("/")[-1][:2]
            note = " ".join(str(r.get("notes", "")).split())
            if len(note) > 400:
                note = note[:397] + "…"
            lines.append(
                f"| `{r['id']}` | {doc} | {r['status']} | {r['summary']} | {note} |"
            )
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
    parser.add_argument(
        "--write-ledger",
        metavar="PATH",
        help="regenerate the A/B/C/D debt ledger at PATH",
    )
    parser.add_argument(
        "--ratchet",
        nargs="?",
        const=BASELINE_PATH,
        metavar="PATH",
        help="fail when open-debt counts exceed the frozen ceiling in PATH "
        f"(default: {BASELINE_PATH})",
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
    if args.write_ledger:
        target = os.path.join(args.root, args.write_ledger)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(LEDGER_PREAMBLE)
            fh.write(ledger(document))
            fh.write("\n")
        print(f"wrote {args.write_ledger}")
    if args.report:
        print()
        print(report(document))
    if args.ratchet:
        path = os.path.join(args.root, args.ratchet)
        if not os.path.isfile(path):
            print(f"FAIL: no coverage baseline at {path}", file=sys.stderr)
            return 1
        with open(path, encoding="utf-8") as fh:
            baseline = json.load(fh)
        ok, lines = ratchet(document, baseline)
        print()
        print("\n".join(lines), file=sys.stderr if not ok else sys.stdout)
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
