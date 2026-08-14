"""The A-08 audit preparation must stay usable, aligned and honest (ADIM 28).

Preparation artifacts rot in a specific way: the worksheet keeps listing routes
that were renamed, the stack script keeps seeding a fixture the checklist no
longer names, and the "completion" line at the bottom of a section keeps saying
``0 / 23`` long after somebody filled rows in. Each of those failures is silent
— the document still renders, still looks like a plan — and each one is only
discovered by the auditor, mid-session, with headphones on.

So the three artifacts are pinned against each other and against the code:

* the worksheet's route list is DERIVED-CHECKED against
  ``frontend/e2e/utils/screenshotMatrix.ts::TARGET_PAGES`` — the same matrix the
  axe scan walks. Rename a route and the human audit follows it automatically,
  or this fails in the same commit.
* the worksheet's declared completion counters are recomputed from the cells.
  A counter that disagrees with its own table is the failure mode that lets a
  half-finished audit read as untouched (or as finished).
* the stack script's seed flags and route list are checked against the same
  sources, so the environment the auditor gets is the environment the checklist
  describes.

And the honesty invariants: while the audit is incomplete the worksheet must
still carry ``A-08 HUMAN-BLOCKED``, the precheck spec must stamp every record
``screen_reader_verified: false``, and no automated artifact may be recorded as
a screen-reader result. A-08 is a human gate (GitHub #514, ``human-only``);
these tests exist so no future edit can quietly convert it into a paper one.
"""

# ruff: noqa: RUF001
# Turkish is the documentation language of this repository, so a test that asserts on
# the content of a Turkish document must contain dotless-i. RUF001 reads it as an
# ambiguous look-alike; here it is the literal character being matched.

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

WORKSHEET = REPO_ROOT / "docs" / "audit" / "a11y_screen_reader_audit_results.md"
CHECKLIST = REPO_ROOT / "docs" / "implementation" / "a11y_screen_reader_audit_checklist.md"
MATRIX = REPO_ROOT / "frontend" / "e2e" / "utils" / "screenshotMatrix.ts"
STACK_SCRIPT = REPO_ROOT / "scripts" / "a11y-audit-stack.sh"
PRECHECK_SPEC = REPO_ROOT / "frontend" / "e2e" / "specs" / "20-a11y-prechecks.spec.ts"
ISSUE_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "a11y_screen_reader_finding.yml"

#: The two combinations ``~/.claude/rules/accessibility.md`` requires. One is
#: not enough and never becomes enough.
COMBINATIONS = ("SR-1", "SR-2")

#: The eight per-page checks of checklist section A.
SECTION_A_CHECKS = ("A-1", "A-2", "A-3", "A-4", "A-5", "A-6", "A-7", "A-8")

#: Seed flags GitHub #514 names. The auditor and the axe scan must look at the
#: same projection, so this set is shared with the E2E workflow.
SEED_FLAGS = ("SEED_E2E_GOLDEN=1", "SEED_ESP_TA=1", "SEED_RATIONALE=1")

#: Every column the findings register must carry. A finding missing its
#: environment cannot be reproduced; one missing its disposition cannot be
#: closed. Both are how a11y findings quietly expire.
FINDINGS_COLUMNS = (
    "ID",
    "Auditor",
    "Date",
    "OS",
    "Screen reader + ver",
    "Browser + ver",
    "Route",
    "Flow",
    "Expected",
    "Observed",
    "WCAG SC",
    "Severity",
    "Disposition",
    "PO",
    "Evidence",
    "Retest",
)

#: The cell value meaning "not run". Anything else is a recorded result.
NOT_RUN = "—"


# --------------------------------------------------------------------------- #
# parsing helpers
# --------------------------------------------------------------------------- #
def _read(path: Path) -> str:
    assert path.is_file(), f"missing A-08 preparation artifact: {path}"
    return path.read_text(encoding="utf-8")


def _target_pages() -> list[tuple[int, str, str]]:
    """(doc, slug, path) straight out of the TypeScript matrix.

    Parsed rather than duplicated: a hand-copied list is exactly what drifts.
    """
    src = _read(MATRIX)
    block = src.split("export const TARGET_PAGES: TargetPage[] = [")[1].split("];")[0]
    pages = [
        (int(doc), slug, path)
        for doc, slug, path in re.findall(
            r'\{\s*doc:\s*(\d+),\s*slug:\s*"([^"]+)",\s*path:\s*"([^"]+)"', block
        )
    ]
    assert pages, "TARGET_PAGES could not be parsed — the matrix format changed"
    return pages


def _table(text: str) -> tuple[list[str], list[list[str]]]:
    """Header cells and body rows of the FIRST markdown table in ``text``.

    Prose between the heading and the table is skipped, so a table may be
    introduced by an explanatory paragraph without breaking the parse.
    """
    header: list[str] = []
    rows: list[list[str]] = []
    seen_separator = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):  # the |---|---| separator
                seen_separator = True
                continue
            if seen_separator:
                rows.append(cells)
            elif not header:
                header = cells
            continue
        if seen_separator and stripped:
            break  # a non-table line after the body: the table ended
    assert header, "no markdown table found in the requested section"
    return header, rows


def _section(markdown: str, heading: str) -> str:
    """Everything from ``heading`` up to the next heading of the same level."""
    parts = markdown.split(heading, 1)
    assert len(parts) > 1, f"worksheet has no section {heading!r}"
    level = len(heading) - len(heading.lstrip("#"))
    rest = parts[1]
    nxt = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _combination_section(markdown: str, section: str, combo: str) -> str:
    """The ``### SR-n — …`` sub-section INSIDE section A or B.

    Scoped deliberately: the same ``### SR-1 — NVDA …`` heading also opens the
    session-header block in §0, so splitting the whole document on the heading
    text would silently parse the wrong table.
    """
    part = _section(markdown, section)
    match = re.search(rf"^### {re.escape(combo)} — .*$", part, re.M)
    assert match, f"{section}: no heading for combination {combo}"
    return _section(part, match.group(0))


# --------------------------------------------------------------------------- #
# the artifacts exist and are wired to the code
# --------------------------------------------------------------------------- #
def test_every_preparation_artifact_exists() -> None:
    for path in (WORKSHEET, CHECKLIST, MATRIX, STACK_SCRIPT, PRECHECK_SPEC, ISSUE_TEMPLATE):
        assert path.is_file(), f"A-08 preparation is incomplete: {path} is missing"


def test_worksheet_section_a_covers_exactly_the_axe_matrix() -> None:
    """The human audit and the automated scan must walk the SAME surface.

    If they diverge, a finding on one cannot be compared against the other, and
    a route can be audited by neither while both look complete.
    """
    markdown = _read(WORKSHEET)
    expected = [path for _, _, path in _target_pages()]
    for combo in COMBINATIONS:
        _, rows = _table(_combination_section(markdown, "## 1. Section A", combo))
        listed = [re.sub(r"\s*\*\(Admin\)\*", "", r[1]).strip().strip("`") for r in rows]
        assert listed == expected, (
            f"Section A / {combo} routes have drifted from "
            f"screenshotMatrix.ts::TARGET_PAGES.\n  worksheet: {listed}\n  matrix:    {expected}"
        )


def test_section_a_row_count_is_23_not_22() -> None:
    """Doc 19 contributes two routes; auditing "22 rows" would skip an Admin page."""
    pages = _target_pages()
    assert len(pages) == 23, f"expected 23 routes across the 22 spec docs, got {len(pages)}"
    assert len({doc for doc, _, _ in pages}) == 22


def test_worksheet_section_b_covers_every_checklist_flow() -> None:
    checklist_flows = sorted(
        set(re.findall(r"^\| (B-\d+)", _read(CHECKLIST), re.M)),
        key=lambda code: int(code.split("-")[1]),
    )
    assert len(checklist_flows) == 10, f"checklist section B changed: {checklist_flows}"

    markdown = _read(WORKSHEET)
    for combo in COMBINATIONS:
        _, rows = _table(_combination_section(markdown, "## 2. Section B", combo))
        listed = [r[0].strip() for r in rows]
        assert listed == checklist_flows, (
            f"Section B / {combo} flows have drifted from the checklist.\n"
            f"  worksheet: {listed}\n  checklist: {checklist_flows}"
        )


def test_section_a_header_carries_all_eight_checks() -> None:
    markdown = _read(WORKSHEET)
    for combo in COMBINATIONS:
        header, _ = _table(_combination_section(markdown, "## 1. Section A", combo))
        for check in SECTION_A_CHECKS:
            assert check in header, f"Section A / {combo}: column {check} is missing"


# --------------------------------------------------------------------------- #
# the worksheet cannot lie about its own progress
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("combo", COMBINATIONS)
def test_declared_completion_matches_the_cells(combo: str) -> None:
    """A completion counter that disagrees with its table is the whole failure mode.

    It lets a half-finished audit read as untouched, and — far worse — lets a
    barely-started one read as finished. Recomputed here from the cells, so the
    two can only move together.
    """
    markdown = _read(WORKSHEET)

    _, a_rows = _table(_combination_section(markdown, "## 1. Section A", combo))
    # A route counts as audited only when all eight checks carry a result.
    a_done = sum(1 for r in a_rows if all(c != NOT_RUN for c in r[3 : 3 + len(SECTION_A_CHECKS)]))
    a_claim = re.search(
        rf"\*\*{re.escape(combo)} Section A completion:\*\* (\d+) / (\d+) routes",
        markdown,
    )
    assert a_claim, f"{combo}: Section A completion line is missing"
    assert int(a_claim.group(1)) == a_done, (
        f"{combo} Section A claims {a_claim.group(1)} completed routes; "
        f"{a_done} row(s) actually carry a result in every check column"
    )
    assert int(a_claim.group(2)) == len(a_rows)

    _, b_rows = _table(_combination_section(markdown, "## 2. Section B", combo))
    b_done = sum(1 for r in b_rows if r[3] != NOT_RUN)
    b_claim = re.search(
        rf"\*\*{re.escape(combo)} Section B completion:\*\* (\d+) / (\d+) flows",
        markdown,
    )
    assert b_claim, f"{combo}: Section B completion line is missing"
    assert int(b_claim.group(1)) == b_done, (
        f"{combo} Section B claims {b_claim.group(1)} completed flows; "
        f"{b_done} row(s) actually carry a result"
    )
    assert int(b_claim.group(2)) == len(b_rows)


def test_human_blocked_banner_stands_while_the_audit_is_incomplete() -> None:
    markdown = _read(WORKSHEET)
    claims = re.findall(r"Section [AB] completion:\*\* (\d+) / (\d+)", markdown)
    assert claims, "worksheet has no completion counters"
    incomplete = any(int(done) < int(total) for done, total in claims)
    if incomplete:
        assert "A-08 HUMAN-BLOCKED" in markdown, (
            "the audit is incomplete but the worksheet no longer declares "
            "A-08 HUMAN-BLOCKED — a partially-run audit must not read as closed"
        )
        assert "#514" in markdown, "the worksheet must keep pointing at the tracking issue"


def test_findings_register_carries_every_required_column() -> None:
    markdown = _read(WORKSHEET)
    columns, _ = _table(_section(markdown, "## 3. Findings register"))
    for column in FINDINGS_COLUMNS:
        assert column in columns, f"findings register is missing the {column!r} column"


def test_recorded_findings_are_fully_specified() -> None:
    """A finding with empty cells cannot be reproduced, retested or closed.

    Vacuously true today (the register holds only its placeholder row); it
    becomes the real gate the moment a human records a finding.
    """
    markdown = _read(WORKSHEET)
    _, rows = _table(_section(markdown, "## 3. Findings register"))
    for row in rows:
        if not row or not row[0].strip() or row[0].startswith("*("):
            continue  # placeholder
        assert len(row) == len(FINDINGS_COLUMNS), (
            f"finding {row[0]!r} has {len(row)} cells, expected {len(FINDINGS_COLUMNS)}"
        )
        for column, cell in zip(FINDINGS_COLUMNS, row, strict=True):
            if column == "PO":
                continue  # legitimately empty for a FIX
            assert cell.strip(), f"finding {row[0]!r}: column {column!r} is empty"
        disposition = row[FINDINGS_COLUMNS.index("Disposition")].strip()
        assert disposition in {"FIX", "PO-APPROVE"}, (
            f"finding {row[0]!r}: disposition {disposition!r} — only FIX or PO-APPROVE exist"
        )


# --------------------------------------------------------------------------- #
# the environment the auditor gets is the one the checklist describes
# --------------------------------------------------------------------------- #
def test_stack_script_is_executable() -> None:
    assert STACK_SCRIPT.stat().st_mode & 0o111, f"{STACK_SCRIPT} is not executable"


def test_stack_script_seeds_exactly_the_flags_the_issue_names() -> None:
    script = _read(STACK_SCRIPT)
    for flag in SEED_FLAGS:
        assert flag in script, f"the audit stack does not seed {flag} — pages would audit as empty"


def test_stack_script_routes_match_the_axe_matrix() -> None:
    script = _read(STACK_SCRIPT)
    block = script.split("AUDIT_ROUTES=(", 1)[1].split(")", 1)[0]
    listed = re.findall(r'"([^"]+)"', block)
    expected = [path for _, _, path in _target_pages()]
    assert listed == expected, (
        "scripts/a11y-audit-stack.sh validates a different route set than the audit "
        f"matrix.\n  script: {listed}\n  matrix: {expected}"
    )


def test_stack_script_never_tears_itself_down_implicitly() -> None:
    """The consumer is a human mid-session, not CI.

    ``scripts/e2e-acceptance.sh`` tears down in an EXIT trap because its caller
    is a job. The same trap here would destroy the auditor's stack the instant
    the script returned, so teardown must stay an explicit subcommand.
    """
    script = _read(STACK_SCRIPT)
    assert not re.search(r"^\s*trap\s+\w+\s+EXIT", script, re.M), (
        "the audit stack installs an EXIT trap — it would tear down the stack "
        "the auditor is still using"
    )
    assert "cmd_down" in script and "REFUSING to 'down -v' non-audit project" in script, (
        "teardown must be an explicit, project-guarded subcommand"
    )


# --------------------------------------------------------------------------- #
# nothing automated may be recorded as a screen-reader result
# --------------------------------------------------------------------------- #
def test_precheck_spec_stamps_every_record_unverified() -> None:
    spec = _read(PRECHECK_SPEC)
    assert "screen_reader_verified: false" in spec, (
        "the precheck report must stamp screen_reader_verified: false — without it "
        "its JSON is indistinguishable from audit evidence"
    )
    assert "HUMAN-BLOCKED" in spec, "the precheck spec must restate that A-08 is human-blocked"


def test_precheck_spec_declares_what_it_did_not_walk() -> None:
    """A narrowed scope that does not announce itself reads as full coverage."""
    spec = _read(PRECHECK_SPEC)
    assert "tab_order_routes_NOT_walked" in spec, (
        "the precheck report must name the routes whose tab order was not walked"
    )


def test_worksheet_refuses_automated_output_as_evidence() -> None:
    markdown = _read(WORKSHEET)
    assert "An empty template is not evidence" in markdown
    assert "axe-core" in markdown and "does NOT prove" in markdown.replace(
        "What it does NOT prove", "does NOT prove"
    ), "the worksheet must state what the automated artifacts do not prove"


def test_checklist_still_records_the_audit_as_incomplete() -> None:
    """Guards the seam: preparation must not be mistaken for performance.

    The original form of this guard pinned the checklist's "the audit has not
    been performed" sentence. That sentence was true when it was written and
    became false on 2026-08-12, when SR-2's first session filled two cells — at
    which point the gate was protecting a statement the canonical worksheet
    contradicts. The seam it exists to defend is not "nothing has run"; it is
    "nothing may read as finished", and that is what it asserts now: the recipe
    must say the audit is unfinished, and must never claim the opposite.
    """
    checklist = _read(CHECKLIST)
    assert "BAŞLADI, BİTMEDİ" in checklist, (
        "the checklist must state the audit's real state — started and unfinished. "
        "Neither 'not performed' (stale since SR-2 session 1) nor silence."
    )
    assert "#514" in checklist

    # The negative half. A recipe that advertises completion is the failure this
    # guard was written for, whichever wording it arrives in.
    for claim in ("Denetim tamamlandı", "A-08 Complete", "A-08 PASS"):
        assert claim not in checklist, f"the checklist claims completion: {claim!r}"


# --------------------------------------------------------------------------- #
# the finding issue template
# --------------------------------------------------------------------------- #
def test_issue_template_is_valid_and_collects_every_register_column() -> None:
    template = yaml.safe_load(_read(ISSUE_TEMPLATE))
    ids = {block.get("id") for block in template["body"] if block.get("id")}
    required = {
        "finding_id",
        "auditor",
        "audit_date",
        "combination",
        "environment",
        "stack_commit",
        "route",
        "check_ref",
        "steps",
        "expected",
        "observed",
        "wcag",
        "severity",
        "disposition",
        "evidence",
        "retest",
        "human_attestation",
    }
    missing = required - ids
    assert not missing, f"the finding template cannot fill the register: missing {sorted(missing)}"


def test_issue_template_requires_a_human_attestation() -> None:
    """The one field that separates a heard defect from an inferred one."""
    template = yaml.safe_load(_read(ISSUE_TEMPLATE))
    block = next(b for b in template["body"] if b.get("id") == "human_attestation")
    options = block["attributes"]["options"]
    assert any(opt.get("required") for opt in options), (
        "the attestation checkbox must be required — otherwise a DOM-derived "
        "observation can be filed as a screen-reader finding"
    )


def test_issue_template_disposition_has_exactly_two_values() -> None:
    template = yaml.safe_load(_read(ISSUE_TEMPLATE))
    block = next(b for b in template["body"] if b.get("id") == "disposition")
    options = block["attributes"]["options"]
    assert len(options) == 2, (
        "FIX and PO-APPROVE are the only dispositions; a third value would let a "
        f"finding be parked without a decision: {options}"
    )
