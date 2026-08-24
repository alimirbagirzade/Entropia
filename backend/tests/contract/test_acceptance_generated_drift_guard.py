"""The acceptance drift guard must refuse the drift this repo actually shipped.

`docs/audit/acceptance_semantic_scan.py` generates two checked-in artefacts — the
traceability report and the A/B/C/D debt ledger — from
`docs/audit/acceptance_semantic_map.yaml`. Both are written by hand-run commands,
so nothing stopped them going stale: the report sat at ADIM 60's numbers through
seven acceptance batches (`234 covered / 126 partial` against a measured
`276 / 84`) while CI stayed green, because `--ratchet` bounds how much of the
contract is UNPROVEN and says nothing about whether the script's own output still
describes the tree.

`--check-generated` closes that hole. These tests pin it the way this repo pins a
gate: the negative is proven, not assumed. A gate that only ever passes is
indistinguishable from one that was quietly disabled, so each rule is driven to
red on a synthetic root and the whole gate is then run green against the real
repository.

MEASURED, and worth stating precisely because it narrows the claim: the LEDGER was
already guarded — ``tests/unit/test_acceptance_semantic_map.py::
test_the_debt_ledger_is_not_stale`` compares it to the map on every pytest run, and
that is exactly why the ledger never drifted while the report did. The unguarded
artefact was the REPORT alone. ``check_generated`` covers both anyway: it moves the
check into the CLI (so a contributor running the script sees it without pytest),
and one function that verifies every artefact this script writes cannot forget the
next one somebody adds.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "docs" / "audit" / "acceptance_semantic_scan.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("acceptance_scan_gate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Register before exec: the script defines a @dataclass, and dataclasses
    # resolves its annotations through sys.modules[cls.__module__].
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load()


def _real_document() -> dict:
    with open(REPO_ROOT / gate.MAP_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _blames(lines: list[str]) -> str:
    """Only the per-file findings, not the trailing fix hint.

    The hint deliberately names BOTH artefacts (regenerating one without the
    other is how they drift apart in the first place), so blame precision has to
    be asserted against the bullets.
    """
    return "\n".join(ln for ln in lines if ln.lstrip().startswith("- "))


def _seed(root: Path, document: dict, *, report: str | None, ledger: str | None) -> None:
    """Write a synthetic repo root carrying exactly the artefact bodies given."""
    for rel, body in ((gate.REPORT_PATH, report), (gate.LEDGER_PATH, ledger)):
        if body is None:
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")


def test_fresh_artefacts_pass(tmp_path: Path) -> None:
    document = _real_document()
    _seed(
        tmp_path,
        document,
        report=gate._rendered_report(document),
        ledger=gate._rendered_ledger(document),
    )
    ok, lines = gate.check_generated(document, str(tmp_path))
    assert ok, lines
    assert "fresh" in "\n".join(lines)


def test_a_stale_report_is_refused(tmp_path: Path) -> None:
    """The exact ADIM 60 shape: the ledger is current, the report is not."""
    document = _real_document()
    _seed(
        tmp_path,
        document,
        report="# Semantic acceptance traceability — coverage report\n\nstale\n",
        ledger=gate._rendered_ledger(document),
    )
    ok, lines = gate.check_generated(document, str(tmp_path))
    assert not ok
    blames = _blames(lines)
    assert gate.REPORT_PATH in blames and "STALE" in blames
    # The ledger was fresh and must NOT be blamed — a guard that reports both on
    # any drift cannot tell a maintainer which file to regenerate.
    assert gate.LEDGER_PATH not in blames


def test_a_single_edited_number_is_refused(tmp_path: Path) -> None:
    """Hand-editing one figure is the realistic drift, not wholesale rewriting."""
    document = _real_document()
    rendered = gate._rendered_report(document)
    tampered = rendered.replace("| **all** |", "| **all-tampered** |", 1)
    assert tampered != rendered
    _seed(tmp_path, document, report=tampered, ledger=gate._rendered_ledger(document))
    ok, _ = gate.check_generated(document, str(tmp_path))
    assert not ok


def test_a_stale_ledger_is_refused(tmp_path: Path) -> None:
    """Second line of defence, not the first.

    ``test_the_debt_ledger_is_not_stale`` in tests/unit already compares the
    shipped ledger with the map. This asserts the CLI gate reaches the same
    verdict, so the two cannot disagree about what "fresh" means.
    """
    document = _real_document()
    _seed(
        tmp_path,
        document,
        report=gate._rendered_report(document),
        ledger="# Acceptance coverage debt ledger\n\nstale\n",
    )
    ok, lines = gate.check_generated(document, str(tmp_path))
    assert not ok
    blames = _blames(lines)
    assert gate.LEDGER_PATH in blames and "STALE" in blames
    assert gate.REPORT_PATH not in blames


def test_a_missing_artefact_is_refused_not_skipped(tmp_path: Path) -> None:
    """Absent must not read as fresh — that is how a deleted artefact hides."""
    document = _real_document()
    _seed(tmp_path, document, report=None, ledger=gate._rendered_ledger(document))
    ok, lines = gate.check_generated(document, str(tmp_path))
    assert not ok
    assert "MISSING" in "\n".join(lines)


def test_the_failure_names_the_regeneration_command(tmp_path: Path) -> None:
    """A red gate that does not say how to fix it gets worked around."""
    document = _real_document()
    _seed(tmp_path, document, report="stale\n", ledger=gate._rendered_ledger(document))
    ok, lines = gate.check_generated(document, str(tmp_path))
    assert not ok
    body = "\n".join(lines)
    assert "--write-report" in body and "--write-ledger" in body


def test_the_writers_and_the_gate_share_one_renderer() -> None:
    """If the writer and the checker disagreed, the gate would be unsatisfiable.

    Source-level, deliberately: a behavioural test cannot see the two drifting
    apart, because a writer that emitted something the checker rejects would
    simply look like a permanently red gate.
    """
    source = SCRIPT.read_text(encoding="utf-8")
    assert "fh.write(_rendered_report(document))" in source
    assert "fh.write(_rendered_ledger(document))" in source


def test_ci_actually_runs_the_guard() -> None:
    """The gate is only real if the workflow invokes it (RC: a job nobody runs)."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    line = next(
        ln
        for ln in workflow.splitlines()
        if "acceptance_semantic_scan.py" in ln and ln.lstrip().startswith("run:")
    )
    assert "--check-generated" in line
    # Adding a gate must not cost the one already there. tests/unit's
    # test_the_ratchet_is_wired_into_ci asserts the same from the ratchet's side;
    # both are cheap and they fail for different reasons.
    assert "--ratchet" in line, "the ratchet must not be lost while adding the drift guard"


def test_this_repository_is_currently_fresh() -> None:
    """The live tree: both artefacts match the map they are generated from."""
    document = _real_document()
    ok, lines = gate.check_generated(document, str(REPO_ROOT))
    assert ok, "\n".join(lines)
