#!/usr/bin/env python3
"""Generated repository facts + a documentation-truth GATE.

WHY THIS EXISTS
---------------
Entropia's prose documentation has drifted from the tree repeatedly: a merged
docs PR built on a stale base deleted history records three separate times, and
`CLAUDE.md` carried a "4 deliberate xfail" claim for weeks after the real number
became 1. Nothing in CI reads `docs/`, so every one of those regressions was
caught (or missed) by a human.

This module closes that hole from two directions:

1. **Generation.** It derives a set of facts that can be read straight off the
   working tree — alembic head, tables/FKs, HTTP operations, frontend routes,
   `ENGINE_VERSION`, capability counts, statically collected test nodes,
   acceptance-map status totals, visual baselines, recorded deviations — and
   writes them to `docs/generated/repository_facts.{json,md}`. `README.md`
   carries the same table inside generated markers.

2. **Checking (`--check`).** It regenerates in memory and fails when the
   committed artefacts are stale, when a document is not classified as current
   or historical, when a codemap stops naming a module or an actor it promises
   to name, or when a *current* document asserts something the tree contradicts.

WHAT IS DELIBERATELY NOT A FACT HERE
------------------------------------
* **Nothing from the GitHub API.** Open PR/issue counts, merge state and run
  results are runtime facts about a server, not properties of this tree. Baking
  them in would make the generated file un-reproducible offline and would make
  `--check` fail for reasons no commit can fix.
* **No commit sha, no timestamp.** Either one would change on every commit, so
  the artefact would be stale the moment it was written and `--check` could
  never be green.
* **No test PASS count.** A pass count only exists after a full suite run.
  What is counted here is *collection* — test nodes discovered by a static
  `ast`/regex walk — and every field says so in its own name.

Usage (from the repo root):
    python3 scripts/generate_repository_facts.py            # write artefacts
    python3 scripts/generate_repository_facts.py --check    # CI gate

The collectors for the database schema, capability matrix and engine constants
import `entropia`, so this runs inside the backend environment:
    cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
"""

# ruff: noqa: RUF001
# Turkish is the documentation language of this repository, so the rule patterns and the
# fixtures that exercise them must contain dotless-i, s-cedilla and g-breve. RUF001 reads
# those as ambiguous look-alikes; here they are the literal characters being matched.

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

JSON_REL = "docs/generated/repository_facts.json"
MD_REL = "docs/generated/repository_facts.md"
README_REL = "README.md"

BEGIN_MARKER = "<!-- BEGIN GENERATED: repository-facts -->"
END_MARKER = "<!-- END GENERATED: repository-facts -->"

STATUS_MARKER_RE = re.compile(r"<!--\s*doc-status:\s*(current|historical)\s*-->")


# ==========================================================================
# Collectors — each one reads the tree and returns plain, sortable data.
# ==========================================================================


def collect_alembic(root: Path) -> dict[str, Any]:
    """Revision graph facts read from the migration files themselves.

    `single_head` is the one that matters operationally: two heads means
    `alembic upgrade head` is ambiguous and the branch cannot be deployed.
    """
    versions = sorted((root / "backend" / "alembic" / "versions").glob("*.py"))
    revisions: dict[str, str | None] = {}
    for path in versions:
        text = path.read_text(encoding="utf-8")
        rev = re.search(r'^revision: str = "([^"]+)"', text, re.MULTILINE)
        down = re.search(r'^down_revision: str \| None = (?:"([^"]+)"|None)', text, re.MULTILINE)
        if rev is None:
            raise SystemExit(f"migration without a `revision:` assignment: {path}")
        revisions[rev.group(1)] = down.group(1) if down and down.group(1) else None

    parents = {down for down in revisions.values() if down}
    heads = sorted(rev for rev in revisions if rev not in parents)
    return {
        "revision_count": len(revisions),
        "heads": heads,
        "head": heads[0] if len(heads) == 1 else None,
        "single_head": len(heads) == 1,
    }


def collect_database() -> dict[str, Any]:
    """Table and foreign-key totals from the SQLAlchemy metadata (no database)."""
    import entropia.infrastructure.postgres.models  # noqa: F401
    from entropia.infrastructure.postgres.base import Base

    tables = []
    for name in sorted(Base.metadata.tables):
        table = Base.metadata.tables[name]
        tables.append(
            {
                "name": name,
                "columns": len(table.columns),
                "foreign_keys": len(table.foreign_keys),
            }
        )
    return {
        "table_count": len(tables),
        "foreign_key_count": sum(t["foreign_keys"] for t in tables),
        "tables": tables,
    }


def collect_http_api(root: Path) -> dict[str, Any]:
    """Operation totals read from the committed OpenAPI snapshot.

    Read from `docs/openapi.json` rather than from a live `create_app()` on
    purpose: the snapshot is already pinned to the app by the OpenAPI drift
    guard in CI, so chaining onto it keeps exactly one definition of "the HTTP
    surface" instead of introducing a second, independently-drifting one.
    """
    schema = json.loads((root / "docs" / "openapi.json").read_text(encoding="utf-8"))
    verbs = ("get", "post", "put", "patch", "delete", "head", "options", "trace")
    methods: Counter[str] = Counter()
    operations: list[str] = []
    for path in sorted(schema.get("paths", {})):
        for verb in verbs:
            if verb in schema["paths"][path]:
                methods[verb] += 1
                operations.append(f"{verb.upper()} {path}")
    return {
        "openapi_version": schema.get("openapi", ""),
        "path_count": len(schema.get("paths", {})),
        "operation_count": sum(methods.values()),
        "operations_by_method": dict(sorted(methods.items())),
        "operations": sorted(operations),
    }


def collect_frontend_routes(root: Path) -> dict[str, Any]:
    """Router paths (App.tsx) and the nav registry (nav.ts), counted separately.

    They are not the same set and the gap is meaningful: `/outsource-signal`
    is a reachable deep link that was deliberately removed from primary nav.
    """
    app = (root / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    router_paths = sorted(set(re.findall(r'<Route\s+path="([^"]+)"', app)))

    nav = (root / "frontend" / "src" / "app" / "nav.ts").read_text(encoding="utf-8")
    nav_items = re.findall(
        r'\{\s*path:\s*"([^"]+)",\s*label:\s*"[^"]*",\s*stage:\s*\d+(,\s*adminOnly:\s*true)?\s*\}',
        nav,
    )
    subpages = re.findall(r'^\s*path:\s*"(/future-dev/[^"]+)",', nav, re.MULTILINE)
    return {
        "router_path_count": len(router_paths),
        "router_paths": router_paths,
        "nav_item_count": len(nav_items),
        "nav_admin_only_count": sum(1 for _, admin in nav_items if admin),
        "nav_paths": sorted(path for path, _ in nav_items),
        "future_dev_subpage_count": len(subpages),
    }


APPLICATION_LAYERS = ("commands", "queries", "jobs")


def collect_backend_layers(root: Path) -> dict[str, Any]:
    """Application-layer module names and `domain/` packages, read off the tree.

    `docs/CODEMAPS/BACKEND_LAYERS.md` used to hand-write these counts in its own
    header, and two of the three went stale (`queries` said 37 against 38 real,
    `jobs` said 14 against 16). The counts are derived here so the codemap can
    point at them instead of restating them; the module NAMES are kept because
    `check_codemap_coverage` gates the rows, which is the drift a count cannot
    see — both uncounted `jobs` modules had no row at all.
    """
    application = root / "backend" / "src" / "entropia" / "application"
    modules = {
        layer: sorted(p.name for p in (application / layer).glob("*.py") if p.name != "__init__.py")
        for layer in APPLICATION_LAYERS
    }
    domain = root / "backend" / "src" / "entropia" / "domain"
    packages = sorted(p.name for p in domain.iterdir() if p.is_dir() and not p.name.startswith("_"))
    return {
        "application_module_counts": {layer: len(names) for layer, names in modules.items()},
        "application_module_names": modules,
        "domain_package_count": len(packages),
        "domain_packages": packages,
    }


def collect_engine_and_capabilities() -> dict[str, Any]:
    """`ENGINE_VERSION` and the capability matrix, imported rather than grepped."""
    from entropia.domain.allocation.capability import SHARED_ALLOCATION_STATUS
    from entropia.domain.backtest.capabilities import CAPABILITY_MATRIX
    from entropia.domain.backtest.manifest import ENGINE_VERSION

    statuses = Counter(option.status for option in CAPABILITY_MATRIX)
    return {
        "engine": {
            "engine_version": ENGINE_VERSION,
            "shared_allocation_status": SHARED_ALLOCATION_STATUS,
        },
        "capabilities": {
            "total": len(CAPABILITY_MATRIX),
            "active_v1": statuses.get("active_v1", 0),
            "future_dev": statuses.get("future_dev", 0),
        },
    }


def _count_python_tests(path: Path) -> tuple[int, int, int]:
    """(test functions, xfail markers, strict xfail markers) in one module."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return (0, 0, 0)
    functions = 0
    xfail = 0
    strict = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                functions += 1
            for decorator in node.decorator_list:
                source = ast.unparse(decorator)
                if "mark.xfail" in source:
                    xfail += 1
                    if "strict=True" in source:
                        strict += 1
    return (functions, xfail, strict)


def collect_tests(root: Path) -> dict[str, Any]:
    """Statically COLLECTED test nodes. Not a pass count — nothing is executed."""
    backend_files = sorted((root / "backend" / "tests").rglob("test_*.py"))
    functions = xfail = strict = 0
    for path in backend_files:
        f, x, s = _count_python_tests(path)
        functions += f
        xfail += x
        strict += s

    unit_files = sorted(
        p for p in (root / "frontend" / "src").rglob("*.test.ts*") if p.suffix in {".ts", ".tsx"}
    )
    case_re = re.compile(r"^\s*(?:it|test)(?:\.\w+)*\s*\(", re.MULTILINE)
    unit_cases = sum(len(case_re.findall(p.read_text(encoding="utf-8"))) for p in unit_files)

    e2e_files = sorted((root / "frontend" / "e2e" / "specs").glob("*.spec.ts"))
    e2e_cases = sum(len(case_re.findall(p.read_text(encoding="utf-8"))) for p in e2e_files)

    return {
        "collection_method": (
            "static ast/regex walk of the test tree — no suite is executed, so these are "
            "COLLECTED counts and never pass counts. They are also LOWER than a runner's "
            "count, because one parametrized site expands into many cases at run time: "
            "`npx vitest list` reports 721 cases over the same 70 files this walk sees as "
            "711 call sites, and pytest expands `@pytest.mark.parametrize` the same way. "
            "Compare file counts across the two, never case counts."
        ),
        "backend_test_files": len(backend_files),
        "backend_collected_test_functions": functions,
        "backend_xfail_markers": xfail,
        "backend_xfail_strict_markers": strict,
        "frontend_unit_test_files": len(unit_files),
        "frontend_unit_test_call_sites": unit_cases,
        "e2e_spec_files": len(e2e_files),
        "e2e_test_call_sites": e2e_cases,
    }


def collect_acceptance(root: Path) -> dict[str, Any]:
    """Status totals from the hand-authored semantic acceptance map."""
    import yaml

    path = root / "docs" / "audit" / "acceptance_semantic_map.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    criteria = data.get("criteria") or []

    by_criterion: Counter[str] = Counter()
    by_clause: Counter[str] = Counter()
    clause_total = 0
    for criterion in criteria:
        by_criterion[str(criterion.get("status", "?"))] += 1
        for clause in criterion.get("clauses") or []:
            clause_total += 1
            by_clause[str(clause.get("status", "?"))] += 1

    return {
        "criteria_count": len(criteria),
        "clause_count": clause_total,
        "criteria_by_status": dict(sorted(by_criterion.items())),
        "clauses_by_status": dict(sorted(by_clause.items())),
    }


def collect_visual_and_deviations(root: Path) -> dict[str, Any]:
    """Committed visual baselines and the two written deviation registers."""
    e2e = root / "frontend" / "e2e"
    playwright = sorted((e2e / "specs").rglob("*-snapshots/*.png"))
    baseline = sorted((e2e / "screenshots" / "baseline").rglob("*.png"))
    prototype = sorted((e2e / "screenshots" / "prototype").rglob("*.png"))

    # Only the `pages` map holds ceilings. Its sibling `provenance` block holds a
    # GitHub Actions `run_id`, so walking the whole document would fold an
    # 11-digit run id into the node total instead of counting nodes.
    a11y_path = e2e / "a11y-baseline.json"
    frozen_nodes = 0
    frozen_pages = 0
    if a11y_path.exists():
        pages = json.loads(a11y_path.read_text(encoding="utf-8")).get("pages") or {}
        frozen_pages = len(pages)
        for rules in pages.values():
            frozen_nodes += sum(int(v) for v in rules.values() if isinstance(v, int))

    deviations = (root / "docs" / "implementation" / "v18_visual_deviations.md").read_text(
        encoding="utf-8"
    )
    rows = [line for line in deviations.splitlines() if re.match(r"^\|\s*\d+\.\d+\s*\|", line)]
    fix_rows = [line for line in rows if "FIX(" in line]
    po_rows = [line for line in rows if "PO-APPROVE" in line]

    return {
        "visual_baselines": {
            "playwright_snapshot_pngs": len(playwright),
            "screenshot_baseline_pngs": len(baseline),
            "screenshot_prototype_pngs": len(prototype),
            "a11y_frozen_serious_nodes": frozen_nodes,
            "a11y_frozen_pages": frozen_pages,
        },
        "deviations": {
            "visual_deviation_rows": len(rows),
            "visual_deviation_fix_rows": len(fix_rows),
            "visual_deviation_po_approve_rows": len(po_rows),
            # Reported explicitly so the three numbers partition the total. Some
            # rows record "sapma yok", a decision already taken on another row,
            # or a review deferred to a later slice — without this key the table
            # would silently imply that FIX + PO-APPROVE covers every row.
            "visual_deviation_other_rows": len(rows) - len(fix_rows) - len(po_rows),
        },
    }


def collect_facts(root: Path) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "scripts/generate_repository_facts.py",
        "contains": (
            "working-tree facts only — no commit sha, no timestamp, no GitHub state, "
            "and no test pass count; regenerate with the generator, never by hand"
        ),
        "alembic": collect_alembic(root),
        "database": collect_database(),
        "http_api": collect_http_api(root),
        "frontend": collect_frontend_routes(root),
        "backend_layers": collect_backend_layers(root),
    }
    facts.update(collect_engine_and_capabilities())
    facts["tests"] = collect_tests(root)
    facts["acceptance"] = collect_acceptance(root)
    facts.update(collect_visual_and_deviations(root))
    return facts


# ==========================================================================
# Rendering
# ==========================================================================


def _row(label: str, value: Any) -> str:
    return f"| {label} | {value} |"


def render_summary_rows(facts: dict[str, Any]) -> list[str]:
    """The headline table — mirrored verbatim into README.md's generated block."""
    alembic = facts["alembic"]
    tests = facts["tests"]
    return [
        "| Fact | Value |",
        "|---|---|",
        _row("Alembic head", f"`{alembic['head'] or ', '.join(alembic['heads'])}`"),
        _row(
            "Alembic revisions",
            f"{alembic['revision_count']} "
            f"({'single head' if alembic['single_head'] else 'MULTIPLE HEADS'})",
        ),
        _row("Postgres tables", facts["database"]["table_count"]),
        _row("Foreign keys", facts["database"]["foreign_key_count"]),
        _row("HTTP paths", facts["http_api"]["path_count"]),
        _row("HTTP operations", facts["http_api"]["operation_count"]),
        _row("Frontend router paths", facts["frontend"]["router_path_count"]),
        _row("Frontend nav items", facts["frontend"]["nav_item_count"]),
        _row(
            "Application modules (`domain/` packages)",
            " · ".join(
                f"{count} `{layer}`"
                for layer, count in facts["backend_layers"]["application_module_counts"].items()
            )
            + f" ({facts['backend_layers']['domain_package_count']} packages)",
        ),
        _row("`ENGINE_VERSION`", f"`{facts['engine']['engine_version']}`"),
        _row(
            "`SHARED_ALLOCATION_STATUS`",
            f"`{facts['engine']['shared_allocation_status']}`",
        ),
        _row(
            "Capability matrix",
            f"{facts['capabilities']['total']} rows "
            f"({facts['capabilities']['active_v1']} `active_v1`, "
            f"{facts['capabilities']['future_dev']} `future_dev`)",
        ),
        _row(
            "Backend tests **collected** (static, not a pass count)",
            f"{tests['backend_collected_test_functions']} in {tests['backend_test_files']} files",
        ),
        _row(
            "Backend `xfail` markers",
            f"{tests['backend_xfail_markers']} ({tests['backend_xfail_strict_markers']} strict)",
        ),
        _row(
            "Frontend unit test **call sites** (static; `.each` expands at run time)",
            f"{tests['frontend_unit_test_call_sites']} in "
            f"{tests['frontend_unit_test_files']} files",
        ),
        _row(
            "E2E test **call sites** (static)",
            f"{tests['e2e_test_call_sites']} in {tests['e2e_spec_files']} specs",
        ),
        _row("Acceptance criteria mapped", facts["acceptance"]["criteria_count"]),
        _row("Acceptance clauses mapped", facts["acceptance"]["clause_count"]),
    ]


def render_markdown(facts: dict[str, Any]) -> str:
    lines: list[str] = [
        "<!-- doc-status: current -->",
        "# Repository facts (GENERATED — do not edit by hand)",
        "",
        "> Regenerate with `cd backend && uv run python ../scripts/generate_repository_facts.py"
        " --root ..`.",
        "> CI runs the same script with `--check` and fails when this file is stale, so an"
        " out-of-date",
        "> number here is a red build rather than a document a later agent believes.",
        "",
        "**This file contains working-tree facts only.** No commit sha, no timestamp and no GitHub",
        "state (open PRs, issue status, workflow runs) — those are properties of a server, not"
        " of this",
        "tree, and embedding them would make the artefact impossible to reproduce or to keep"
        " green.",
        "**No test pass count either:** every test number below is a *collected* node count from a",
        "static walk. Only a full CI run reports passes.",
        "",
        "## Summary",
        "",
        *render_summary_rows(facts),
        "",
        "## Acceptance map status totals",
        "",
        "| Level | " + " | ".join(sorted(facts["acceptance"]["criteria_by_status"])) + " |",
        "|---|" + "---|" * len(facts["acceptance"]["criteria_by_status"]),
        "| Criteria | "
        + " | ".join(
            str(facts["acceptance"]["criteria_by_status"][k])
            for k in sorted(facts["acceptance"]["criteria_by_status"])
        )
        + " |",
        "| Clauses | "
        + " | ".join(
            str(facts["acceptance"]["clauses_by_status"].get(k, 0))
            for k in sorted(facts["acceptance"]["criteria_by_status"])
        )
        + " |",
        "",
        "## HTTP operations by method",
        "",
        "| Method | Count |",
        "|---|---|",
        *(
            f"| `{method.upper()}` | {count} |"
            for method, count in sorted(facts["http_api"]["operations_by_method"].items())
        ),
        "",
        "## Visual baselines and recorded deviations",
        "",
        "| Fact | Value |",
        "|---|---|",
        _row(
            "Playwright snapshot PNGs",
            facts["visual_baselines"]["playwright_snapshot_pngs"],
        ),
        _row(
            "Screenshot baseline PNGs",
            facts["visual_baselines"]["screenshot_baseline_pngs"],
        ),
        _row(
            "Screenshot prototype PNGs",
            facts["visual_baselines"]["screenshot_prototype_pngs"],
        ),
        _row(
            "a11y frozen serious nodes (`frontend/e2e/a11y-baseline.json`)",
            f"{facts['visual_baselines']['a11y_frozen_serious_nodes']} across "
            f"{facts['visual_baselines']['a11y_frozen_pages']} pages",
        ),
        _row("Visual deviation rows", facts["deviations"]["visual_deviation_rows"]),
        _row("… awaiting a FIX slice", facts["deviations"]["visual_deviation_fix_rows"]),
        _row("… PO-APPROVE (deliberate)", facts["deviations"]["visual_deviation_po_approve_rows"]),
        _row(
            "… neither (no deviation / decided on another row / deferred)",
            facts["deviations"]["visual_deviation_other_rows"],
        ),
        "",
        "> The full per-table, per-route and per-path lists live in "
        "[`repository_facts.json`](repository_facts.json).",
        "",
    ]
    return "\n".join(lines)


def render_json(facts: dict[str, Any]) -> str:
    return json.dumps(facts, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_readme_block(facts: dict[str, Any]) -> str:
    return "\n".join(
        [
            BEGIN_MARKER,
            "<!-- Written by scripts/generate_repository_facts.py; `--check` gates it in CI. -->",
            "",
            *render_summary_rows(facts),
            "",
            "*Generated from the working tree — no commit sha, no GitHub state, no pass counts.*",
            "*Full detail: "
            "[`docs/generated/repository_facts.md`](docs/generated/repository_facts.md).*",
            "",
            END_MARKER,
        ]
    )


def splice_readme(text: str, block: str) -> str:
    """Replace the generated block in README.md, preserving everything around it."""
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise SystemExit(
            f"{README_REL} is missing the generated markers.\n"
            f"Add these two lines where the facts table belongs:\n"
            f"  {BEGIN_MARKER}\n  {END_MARKER}"
        )
    return text[:start] + block + text[end + len(END_MARKER) :]


# ==========================================================================
# Document classification
# ==========================================================================

# Documents that a later agent can mistake for the present tense. A landed
# kickoff, a dated audit and a history record all read like instructions; the
# marker is what tells a reader (and this gate) which one is live.
CLASSIFIED_GLOBS = (
    "docs/*KICKOFF*.md",
    "docs/PROJECT_HISTORY.md",
    "docs/POST_V1_SPEC_GAP_BACKLOG_*.md",
    "docs/V18_R2_ROADMAP.md",
    "docs/audit/*.md",
    "docs/implementation/*.md",
)

# These are records of what was true on a date. None of them may ever be the
# current handoff, so `doc-status: current` on one is itself the defect.
ALWAYS_HISTORICAL_GLOBS = (
    "docs/PROJECT_HISTORY.md",
    "docs/POST_V1_SPEC_GAP_BACKLOG_*.md",
    "docs/V18_R2_ROADMAP.md",
    "docs/audit/*.md",
    "docs/implementation/*.md",
)

HISTORICAL_BANNER = (
    "<!-- doc-status: historical -->\n"
    "> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu\n"
    "> kaydeder; SHA'lar, sayılar, alembic head'i ve \"next\" maddeleri bayat olabilir.\n"
    "> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`\n"
    "> (üretilmiş, CI'da `--check` ile kapılı).\n"
)

CURRENT_BANNER = (
    "<!-- doc-status: current -->\n"
    "> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:\n"
    "> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).\n"
)


def _expand(root: Path, globs: tuple[str, ...]) -> list[Path]:
    seen: set[Path] = set()
    for pattern in globs:
        seen.update(p for p in root.glob(pattern) if p.is_file())
    return sorted(seen)


def _doc_status(path: Path) -> str | None:
    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:3])
    match = STATUS_MARKER_RE.search(head)
    return match.group(1) if match else None


def check_classification(root: Path) -> list[str]:
    failures: list[str] = []
    always_historical = set(_expand(root, ALWAYS_HISTORICAL_GLOBS))
    current_docs: list[str] = []

    for path in _expand(root, CLASSIFIED_GLOBS):
        rel = path.relative_to(root).as_posix()
        status = _doc_status(path)
        if status is None:
            failures.append(
                f"{rel}: no `<!-- doc-status: current|historical -->` marker in the first 3 "
                "lines. A kickoff/handoff/audit with no marker reads as present tense."
            )
            continue
        if status == "current":
            current_docs.append(rel)
            if path in always_historical:
                failures.append(
                    f"{rel}: marked `current`, but a history/audit record is never the "
                    "current handoff. Mark it `historical`."
                )

    if len(current_docs) > 1:
        failures.append(
            "more than one document claims `doc-status: current`: "
            + ", ".join(sorted(current_docs))
            + ". Exactly one kickoff may be live; demote the superseded one(s)."
        )
    return failures


# ==========================================================================
# Stale-assertion scan over the present-tense surfaces
# ==========================================================================

# Documents an agent reads first and treats as "what is true now".
PRESENT_TENSE_GLOBS = (
    "README.md",
    "CLAUDE.md",
    "backend/README.md",
    "frontend/README.md",
    "docs/README.md",
    "docs/CODEMAPS/*.md",
)

# The invariant rules also cover the wider set of present-tense prose: these
# read as current even though they carry per-slice history inside them.
INVARIANT_GLOBS = (
    *PRESENT_TENSE_GLOBS,
    "docs/STAGE2_HANDOFF.md",
    "docs/STAGE_BUILD_PLAN.md",
    "docs/ARCHITECTURE.md",
    "docs/DOMAIN_MODEL.md",
    "docs/USAGE.md",
)

# A line that explicitly frames itself as a past value is allowed to name an old
# revision — that is how this repo keeps its own drift auditable.
HISTORICAL_HEDGE_RE = re.compile(
    r"Historical|historical|Tarihsel|tarihsel|önceki|eskiden|previously|as of|o gün",
)

# Only formatting punctuation may sit between "head" and the revision, so an
# assertion ("head = 0043…", or a "| Alembic head | 0043… |" table cell) matches
# while narrative prose about a PARENT revision ("tek head; 0042… üzerine") does
# not — the semicolon is not in the allowed gap.
HEAD_ASSERTION_RE = re.compile(r"(?:alembic\s+)?heads?[\s`*=:|—-]+(\d{4}_[a-z0-9_]+)", re.I)
ENGINE_VERSION_RE = re.compile(r"backtest-engine-v18[a-z0-9-]*")
SHARED_ALLOCATION_RE = re.compile(r"SHARED_ALLOCATION_STATUS[\s`*=:|—-]+(?:is\s+)?(\w+)")

# A line that DENIES the claim necessarily contains the claim's own words, so
# without this the gate would flag the very sentences that state the invariant
# correctly ("shared capital does NOT run in this build"). Turkish negates with a
# verb suffix rather than a particle, so the -ma-/-me- forms are listed too.
NEGATION_RE = re.compile(
    r"DEĞİL|değil|DEGIL|değildir|olamaz|yanlış|yasak|"
    r"çalışma(z|dığı|yan|ması)|çalışmıyor|üretme(z|diği)|KAPALI|kapalı|\bYOK\b|"
    r"karşılanmıyor|sayılamaz|"
    # NOT `\bno\b`: under re.I it matches an ordinary English "no" anywhere on the
    # line, which would silently swallow a real hit such as
    # "Backtest Run = Backtest Result, no exceptions".
    r"\bnot\b|\bnever\b|forbidden|MUST NOT|is not|aren't|does not|cannot",
    re.I,
)


INVARIANT_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    # (rule id, pattern, human message)
    (
        "A08_COMPLETE",
        re.compile(r"A-08[^\n]{0,80}?(Complete|COMPLETE|PASS|Done|tamamlan|kapandı)"),
        "A-08 (screen-reader acceptance) is claimed complete. It requires a human "
        "NVDA/VoiceOver audit that this tree records only a first partial session of "
        "(SR-2, 2026-08-12: 2 of 184 Section A cells, 0 of 10 flows; SR-1 never "
        "started). GH #514's state is not the evidence in either direction — it was "
        "closed unaudited on 2026-08-07 and re-opened by a human on 2026-08-12. The "
        "gate is the four exit criteria. See "
        "docs/audit/a11y_screen_reader_audit_results.md §STATUS.",
    ),
    (
        "WCAG_CONFORMANCE",
        re.compile(
            r"WCAG[^\n]{0,40}(AA|2\.2)[^\n]{0,80}?"
            r"(uyumlu|compliant|conformant|conforms|karşılan|meets|Complete|PASS)"
        ),
        "a WCAG 2.2 AA conformance claim. D-10 is a SIGNED, permanent contrast "
        "deviation — 1.4.3 is not met, so the product cannot be called conformant.",
    ),
    (
        "RUN_IS_RESULT",
        re.compile(
            r"(Backtest\s+)?Run[^\n]{0,20}?(=|==|ile aynı|aynı entity|is the same|"
            r"same entity|eşdeğer)[^\n]{0,20}?(Backtest\s+)?Result",
        ),
        "Backtest Run and Backtest Result are conflated. They are distinct entities; "
        "only a SUCCEEDED Run produces an immutable Result.",
    ),
    (
        "SIGNAL_IS_PACKAGE",
        re.compile(
            r"(Trading\s+Signal|Trade\s+Log)[^\n]{0,25}?"
            r"(=|==|bir\s+Package|is\s+a\s+Package|Package'?t[ıi]r|sayılır)",
        ),
        "a Trading Signal / Trade Log is described as a Package. They are not "
        "Packages and never enter the package lifecycle.",
    ),
    # Keyed on the FEATURE name, not on the bare `future_dev` literal: the literal
    # appears in vocabulary lists ("`active_v1` | `future_dev` + `dependency`"),
    # in containment prose and in this file's own count rows, none of which
    # asserts anything. The falsifiable half of "Future Dev is active" — the
    # shared-allocation flag — is pinned by its own fact rule instead.
    (
        "FUTURE_DEV_ACTIVE",
        re.compile(
            r"Future[\s-]?Dev[^\n]{0,60}?"
            r"(çalışır|çalışıyor|executes\b|runs\b|üretir|produces|generates|is active|aktiftir)"
        ),
        "the Future Dev surface is described as executing or producing output. A "
        "Future Dev capability never runs in this build: it opens no position, "
        "emits no job and no artefact, and trips STRATEGY_CAPABILITY_NOT_IN_BUILD.",
    ),
)


# ==========================================================================
# Codemap coverage — the maps claim to name their subjects exhaustively
# ==========================================================================

BACKEND_LAYERS_REL = "docs/CODEMAPS/BACKEND_LAYERS.md"
JOBS_AND_EVENTS_REL = "docs/CODEMAPS/JOBS_AND_EVENTS.md"
ACTORS_REL = "backend/src/entropia/apps/worker/actors.py"

ACTOR_RE = re.compile(r'@dramatiq\.actor\(\s*queue_name="([^"]+)"[^)]*\)\s*\ndef\s+(\w+)')


def _layer_section(text: str, layer: str) -> str:
    """The BACKEND_LAYERS.md section for one application layer.

    Scoped rather than searched whole-file on purpose: three layers share module
    names (`market_data.py` exists in `commands`, `queries` and `jobs`), so a
    whole-file membership test would call a missing query row covered by its
    command namesake.
    """
    heading = f"## `application/{layer}/`"
    start = text.find(heading)
    if start == -1:
        return ""
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end == -1 else text[start:end]


def check_codemap_coverage(root: Path, facts: dict[str, Any]) -> list[str]:
    """Every application module and every dramatiq actor must be NAMED in its map.

    The codemaps promise an exhaustive naming, and a later agent trusts that
    promise instead of walking the tree. Two `application/jobs` modules
    (`delivery.py`, `heartbeat.py`) sat outside the map for a whole wave while
    its header still advertised a count. A count in prose cannot catch a missing
    row — it only records that someone once counted — so what is gated here is
    membership, and the counts live in the generated artefact instead.
    """
    failures: list[str] = []

    layers_text = (root / BACKEND_LAYERS_REL).read_text(encoding="utf-8")
    for layer, names in facts["backend_layers"]["application_module_names"].items():
        section = _layer_section(layers_text, layer)
        if not section:
            failures.append(f"{BACKEND_LAYERS_REL}: no `## `application/{layer}/`` section.")
            continue
        for name in names:
            if f"`{name}`" not in section:
                failures.append(
                    f"{BACKEND_LAYERS_REL}: `application/{layer}/{name}` has no row. The map "
                    "names every module in the layer; add the row rather than a count."
                )

    actors_text = (root / ACTORS_REL).read_text(encoding="utf-8")
    jobs_lines = (root / JOBS_AND_EVENTS_REL).read_text(encoding="utf-8").splitlines()
    for queue, actor in ACTOR_RE.findall(actors_text):
        row = next((line for line in jobs_lines if line.startswith(f"| `{actor}` |")), None)
        if row is None:
            failures.append(
                f"{JOBS_AND_EVENTS_REL}: dramatiq actor `{actor}` has no row in the actor table."
            )
        elif f"| `{queue}` |" not in row:
            failures.append(
                f"{JOBS_AND_EVENTS_REL}: `{actor}` is not mapped to its real queue `{queue}`."
            )
    return failures


def _scan(root: Path, globs: tuple[str, ...]):
    """Yield (rel path, 1-based line number, line) for every present-tense line.

    Lines inside a generated block are skipped: this script writes them, and
    their freshness is already gated by `check_artifacts`. Scanning them would
    make the generator's own summary rows ("62 rows (40 `active_v1`, 22
    `future_dev`)") read as prose claims.
    """
    for path in _expand(root, globs):
        rel = path.relative_to(root).as_posix()
        generated = False
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if BEGIN_MARKER in line:
                generated = True
            elif END_MARKER in line:
                generated = False
            elif not generated:
                yield rel, number, line


def check_assertions(root: Path, facts: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    head = facts["alembic"]["head"]
    engine_version = facts["engine"]["engine_version"]
    shared_status = facts["engine"]["shared_allocation_status"]

    for rel, number, line in _scan(root, PRESENT_TENSE_GLOBS):
        if HISTORICAL_HEDGE_RE.search(line):
            continue
        for match in HEAD_ASSERTION_RE.finditer(line):
            if head is not None and match.group(1) != head:
                failures.append(
                    f"{rel}:{number}: names `{match.group(1)}` as the alembic head; the tree's "
                    f"head is `{head}`. Fix the text or hedge the line as historical."
                )
        for match in ENGINE_VERSION_RE.finditer(line):
            if match.group(0) != engine_version:
                failures.append(
                    f"{rel}:{number}: cites ENGINE_VERSION `{match.group(0)}`; the tree's value "
                    f"is `{engine_version}`."
                )
        for match in SHARED_ALLOCATION_RE.finditer(line):
            if match.group(1) in {"active_v1", "future_dev"} and match.group(1) != shared_status:
                failures.append(
                    f"{rel}:{number}: says SHARED_ALLOCATION_STATUS is `{match.group(1)}`; "
                    f"the tree's value is `{shared_status}`."
                )

    for rel, number, line in _scan(root, INVARIANT_GLOBS):
        if NEGATION_RE.search(line):
            # A line that states the invariant ("Run is NOT Result") necessarily
            # contains both nouns; refusing to skip it would flag the correction.
            continue
        for rule_id, pattern, message in INVARIANT_RULES:
            if pattern.search(line):
                failures.append(f"{rel}:{number}: [{rule_id}] {message}")
    return failures


# ==========================================================================
# CLI
# ==========================================================================


def write_artifacts(root: Path, facts: dict[str, Any]) -> list[str]:
    written: list[str] = []
    for rel, body in (
        (JSON_REL, render_json(facts)),
        (MD_REL, render_markdown(facts)),
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")
        written.append(rel)

    readme = root / README_REL
    spliced = splice_readme(readme.read_text(encoding="utf-8"), render_readme_block(facts))
    readme.write_text(spliced, encoding="utf-8", newline="\n")
    written.append(README_REL)
    return written


def check_artifacts(root: Path, facts: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for rel, expected in (
        (JSON_REL, render_json(facts)),
        (MD_REL, render_markdown(facts)),
    ):
        path = root / rel
        actual = path.read_text(encoding="utf-8") if path.exists() else ""
        if actual != expected:
            failures.append(
                f"{rel} is STALE — the tree moved but the artefact was not regenerated."
            )

    readme = root / README_REL
    text = readme.read_text(encoding="utf-8")
    if splice_readme(text, render_readme_block(facts)) != text:
        failures.append(
            f"{README_REL}'s generated block is STALE (between {BEGIN_MARKER} and {END_MARKER})."
        )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root (default: cwd)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; fail when an artefact is stale, a document is unclassified, "
        "or a present-tense document contradicts the tree",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    facts = collect_facts(root)

    if not args.check:
        for rel in write_artifacts(root, facts):
            print(f"wrote {rel}")
        return 0

    failures = check_artifacts(root, facts)
    failures += check_classification(root)
    failures += check_codemap_coverage(root, facts)
    failures += check_assertions(root, facts)

    if failures:
        print(
            f"documentation-truth gate FAILED ({len(failures)} finding(s)):\n",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "\nRegenerate with:\n"
            "  cd backend && uv run python ../scripts/generate_repository_facts.py --root ..\n"
            "…then fix any prose finding by hand.",
            file=sys.stderr,
        )
        return 1

    print("documentation-truth gate OK — artefacts fresh, documents classified, no stale claims.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
