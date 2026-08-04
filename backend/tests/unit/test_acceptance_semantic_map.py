"""The semantic-acceptance map must be enforceable, not merely present.

`docs/audit/acceptance_semantic_scan.py` is the gate that replaces "an acceptance
ID appears somewhere in a docstring" with "a named test node asserts this clause".
A gate is only worth its name if it actually fails, so every failure mode below is
provoked against a synthetic repo tree rather than assumed.

The last test in this module is the important one for the product: it runs the gate
against the SHIPPED map and the real test tree, so a renamed or deleted test that
some criterion cites turns red here as well as in the standalone CI step.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCANNER_PATH = REPO_ROOT / "docs" / "audit" / "acceptance_semantic_scan.py"
MAP_PATH = REPO_ROOT / "docs" / "audit" / "acceptance_semantic_map.yaml"


def _load_scanner() -> Any:
    spec = importlib.util.spec_from_file_location("acceptance_semantic_scan", SCANNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


scan = _load_scanner()


# ---------------------------------------------------------------------------
# A synthetic repo just big enough to have real nodes to resolve against.

FAKE_PY_UNIT = """
def test_ok():
    pass


class TestGroup:
    def test_inner(self):
        pass
"""

FAKE_PY_INTEGRATION = """
def test_durable():
    pass
"""

FAKE_TSX = """
describe("Fake page", () => {
  it("renders the board", () => {});
  it(`${mode} mode renders the board`, () => {});
});
"""


@pytest.fixture
def fake_root(tmp_path: Path) -> Path:
    (tmp_path / "backend/tests/unit").mkdir(parents=True)
    (tmp_path / "backend/tests/integration").mkdir(parents=True)
    (tmp_path / "frontend/src/test").mkdir(parents=True)
    (tmp_path / "docs/spec").mkdir(parents=True)
    (tmp_path / "backend/tests/unit/test_fake.py").write_text(FAKE_PY_UNIT)
    (tmp_path / "backend/tests/integration/test_fake_int.py").write_text(FAKE_PY_INTEGRATION)
    (tmp_path / "frontend/src/test/fake.test.tsx").write_text(FAKE_TSX)
    (tmp_path / "docs/spec/07_fake.md").write_text("# fake spec\n")
    return tmp_path


UNIT_NODE = "backend/tests/unit/test_fake.py::test_ok"
INT_NODE = "backend/tests/integration/test_fake_int.py::test_durable"
TSX_NODE = "frontend/src/test/fake.test.tsx > Fake page > renders the board"


def make_record(**overrides: Any) -> dict[str, Any]:
    """A record that validates clean, so each test perturbs exactly one thing."""
    record: dict[str, Any] = {
        "id": "XX-01",
        "document": "docs/spec/07_fake.md",
        "section": "16",
        "summary": "a fake criterion",
        "clauses": [
            {
                "id": "XX-01.c1",
                "text": "the thing happens",
                "status": "covered",
                "test_evidence": [UNIT_NODE],
            }
        ],
        "production_paths": ["backend/src/entropia/fake.py"],
        "test_evidence": [UNIT_NODE],
        "evidence_type": ["backend_unit"],
        "positive": [UNIT_NODE],
        "negative": [],
        "auth": [],
        "occ": [],
        "idempotency": [],
        "async_recovery": [],
        "historical_integrity": [],
        "agent_parity": [],
        "status": "covered",
        "notes": "",
    }
    record.update(overrides)
    return record


def codes(root: Path, *records: dict[str, Any]) -> list[str]:
    index = scan.TestIndex(root=str(root))
    return [v.code for v in scan.validate({"criteria": list(records)}, index)]


# ---------------------------------------------------------------------------


def test_a_well_formed_record_produces_no_violations(fake_root: Path) -> None:
    assert codes(fake_root, make_record()) == []


def test_duplicate_criterion_id_is_rejected(fake_root: Path) -> None:
    assert "DUPLICATE_ID" in codes(fake_root, make_record(), make_record())


def test_duplicate_clause_id_is_rejected(fake_root: Path) -> None:
    second = make_record(id="XX-02")
    assert "DUPLICATE_CLAUSE_ID" in codes(fake_root, make_record(), second)


def test_a_node_whose_file_is_absent_is_rejected(fake_root: Path) -> None:
    node = "backend/tests/unit/test_absent.py::test_ok"
    record = make_record(
        test_evidence=[node],
        positive=[node],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [node]}],
    )
    assert codes(fake_root, record).count("UNRESOLVED_NODE") == 2


def test_a_node_whose_function_is_absent_is_rejected(fake_root: Path) -> None:
    node = "backend/tests/unit/test_fake.py::test_does_not_exist"
    record = make_record(
        test_evidence=[node],
        positive=[node],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [node]}],
    )
    assert "UNRESOLVED_NODE" in codes(fake_root, record)


def test_a_vitest_title_that_does_not_exist_is_rejected(fake_root: Path) -> None:
    node = "frontend/src/test/fake.test.tsx > Fake page > renders nothing at all"
    record = make_record(
        test_evidence=[node],
        evidence_type=["frontend_component"],
        positive=[node],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [node]}],
    )
    assert "UNRESOLVED_NODE" in codes(fake_root, record)


def test_a_class_nested_test_resolves(fake_root: Path) -> None:
    node = "backend/tests/unit/test_fake.py::TestGroup::test_inner"
    record = make_record(
        test_evidence=[node],
        positive=[node],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [node]}],
    )
    assert codes(fake_root, record) == []


def test_a_parametrized_node_id_resolves_without_its_parameters(fake_root: Path) -> None:
    node = "backend/tests/unit/test_fake.py::test_ok[session]"
    record = make_record(
        test_evidence=[node],
        positive=[node],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [node]}],
    )
    assert codes(fake_root, record) == []


def test_an_interpolated_vitest_title_resolves_by_pattern(fake_root: Path) -> None:
    node = "frontend/src/test/fake.test.tsx > Fake page > session mode renders the board"
    record = make_record(
        test_evidence=[node],
        evidence_type=["frontend_component"],
        positive=[node],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [node]}],
    )
    assert codes(fake_root, record) == []


def test_a_node_id_with_no_selector_is_rejected(fake_root: Path) -> None:
    node = "backend/tests/unit/test_fake.py"
    record = make_record(
        test_evidence=[node],
        positive=[node],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [node]}],
    )
    assert "UNRESOLVED_NODE" in codes(fake_root, record)


@pytest.mark.parametrize("status", ["covered", "partial"])
def test_claiming_coverage_without_any_evidence_is_rejected(fake_root: Path, status: str) -> None:
    record = make_record(
        status=status,
        notes="argued",
        test_evidence=[],
        evidence_type=[],
        positive=[],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": status, "test_evidence": []}],
    )
    assert codes(fake_root, record).count("EMPTY_EVIDENCE") == 2


@pytest.mark.parametrize("status", ["uncovered", "not_applicable", "product_decision_required"])
def test_a_status_that_denies_evidence_may_not_cite_any(fake_root: Path, status: str) -> None:
    record = make_record(
        status=status,
        notes="argued",
        clauses=[{"id": "XX-01.c1", "text": "t", "status": status, "test_evidence": [UNIT_NODE]}],
    )
    assert codes(fake_root, record).count("EVIDENCE_ON_EMPTY_STATUS") == 2


def test_an_unknown_status_is_rejected(fake_root: Path) -> None:
    assert "UNKNOWN_STATUS" in codes(fake_root, make_record(status="mostly_fine"))


def test_a_missing_required_field_is_rejected(fake_root: Path) -> None:
    record = make_record()
    del record["production_paths"]
    assert "MISSING_FIELD" in codes(fake_root, record)


def test_an_unknown_spec_document_is_rejected(fake_root: Path) -> None:
    assert "UNKNOWN_DOCUMENT" in codes(fake_root, make_record(document="docs/spec/99_nope.md"))


def test_a_judgement_status_must_be_argued_in_notes(fake_root: Path) -> None:
    record = make_record(
        status="uncovered",
        notes="",
        test_evidence=[],
        evidence_type=[],
        positive=[],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "uncovered", "test_evidence": []}],
    )
    assert "NOTES_REQUIRED" in codes(fake_root, record)


def test_a_criterion_may_not_out_claim_its_own_clauses(fake_root: Path) -> None:
    record = make_record(
        clauses=[
            {"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [UNIT_NODE]},
            {"id": "XX-01.c2", "text": "u", "status": "uncovered", "test_evidence": []},
        ]
    )
    assert "STATUS_CLAUSE_MISMATCH" in codes(fake_root, record)


def test_an_uncovered_criterion_with_a_proven_clause_is_rejected(fake_root: Path) -> None:
    record = make_record(
        status="uncovered",
        notes="argued",
        test_evidence=[],
        evidence_type=[],
        positive=[],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": []}],
    )
    assert "STATUS_CLAUSE_MISMATCH" in codes(fake_root, record)


def test_axis_evidence_must_also_be_listed_as_criterion_evidence(fake_root: Path) -> None:
    assert "AXIS_NOT_IN_EVIDENCE" in codes(fake_root, make_record(auth=[INT_NODE]))


def test_a_clause_may_not_cite_evidence_the_criterion_omits(fake_root: Path) -> None:
    record = make_record(
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [INT_NODE]}]
    )
    assert "AXIS_NOT_IN_EVIDENCE" in codes(fake_root, record)


def test_authorization_cannot_be_proven_by_a_rendered_ui_alone(fake_root: Path) -> None:
    record = make_record(
        test_evidence=[TSX_NODE],
        evidence_type=["frontend_component"],
        positive=[TSX_NODE],
        auth=[TSX_NODE],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [TSX_NODE]}],
    )
    assert "AXIS_EVIDENCE_TOO_WEAK" in codes(fake_root, record)


def test_durable_recovery_cannot_be_proven_by_a_unit_test_alone(fake_root: Path) -> None:
    assert "AXIS_EVIDENCE_TOO_WEAK" in codes(fake_root, make_record(async_recovery=[UNIT_NODE]))


def test_durable_recovery_accepts_an_integration_test(fake_root: Path) -> None:
    record = make_record(
        test_evidence=[UNIT_NODE, INT_NODE],
        evidence_type=["backend_unit", "backend_integration"],
        async_recovery=[INT_NODE],
    )
    assert codes(fake_root, record) == []


def test_evidence_type_must_match_where_the_node_lives(fake_root: Path) -> None:
    record = make_record(
        test_evidence=[INT_NODE],
        evidence_type=["backend_unit"],
        positive=[INT_NODE],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [INT_NODE]}],
    )
    assert codes(fake_root, record).count("EVIDENCE_TYPE_MISMATCH") == 2


def test_a_declared_evidence_type_with_no_cited_node_is_rejected(fake_root: Path) -> None:
    record = make_record(evidence_type=["backend_unit", "e2e"])
    assert "EVIDENCE_TYPE_MISMATCH" in codes(fake_root, record)


def test_an_unknown_evidence_type_is_rejected(fake_root: Path) -> None:
    assert "UNKNOWN_EVIDENCE_TYPE" in codes(fake_root, make_record(evidence_type=["vibes"]))


def test_a_covered_criterion_must_declare_a_positive_or_negative_path(fake_root: Path) -> None:
    assert "POSITIVE_NEGATIVE_MISSING" in codes(fake_root, make_record(positive=[]))


def test_a_criterion_without_clauses_is_rejected(fake_root: Path) -> None:
    assert "NO_CLAUSES" in codes(fake_root, make_record(clauses=[]))


def test_main_exits_non_zero_on_a_map_that_lies(fake_root: Path, capsys: Any) -> None:
    bad = make_record(
        test_evidence=["backend/tests/unit/test_absent.py::test_ok"],
        positive=["backend/tests/unit/test_absent.py::test_ok"],
        clauses=[
            {
                "id": "XX-01.c1",
                "text": "t",
                "status": "covered",
                "test_evidence": ["backend/tests/unit/test_absent.py::test_ok"],
            }
        ],
    )
    path = fake_root / "map.yaml"
    path.write_text(yaml.safe_dump({"criteria": [bad]}, sort_keys=False))
    assert scan.main(["--root", str(fake_root), "--map", "map.yaml"]) == 1
    assert "UNRESOLVED_NODE" in capsys.readouterr().err


def test_main_exits_zero_on_a_truthful_map(fake_root: Path) -> None:
    path = fake_root / "map.yaml"
    path.write_text(yaml.safe_dump({"criteria": [make_record()]}, sort_keys=False))
    assert scan.main(["--root", str(fake_root), "--map", "map.yaml"]) == 0


def test_main_exits_non_zero_when_the_map_is_missing(tmp_path: Path) -> None:
    assert scan.main(["--root", str(tmp_path), "--map", "nope.yaml"]) == 1


# ---------------------------------------------------------------------------
# The shipped map, against the real tree.


@pytest.fixture(scope="module")
def shipped_map() -> dict[str, Any]:
    with open(MAP_PATH, encoding="utf-8") as fh:
        return dict(yaml.safe_load(fh))


def test_the_shipped_map_validates_against_the_real_test_tree(
    shipped_map: dict[str, Any],
) -> None:
    violations = scan.validate(shipped_map, scan.TestIndex(root=str(REPO_ROOT)))
    assert violations == [], "\n".join(str(v) for v in violations[:40])


def test_the_shipped_map_covers_every_acceptance_row_in_the_spec_corpus(
    shipped_map: dict[str, Any],
) -> None:
    """A map that quietly drops rows would score well by omission."""
    expected = _spec_row_counts()
    actual: dict[str, int] = {}
    for record in shipped_map["criteria"]:
        doc = Path(str(record["document"])).name[:2]
        actual[doc] = actual.get(doc, 0) + 1
    assert actual == expected


def _spec_row_counts() -> dict[str, int]:
    import re

    heading = re.compile(r"^#+ *\d+\. *Acceptance Tests", re.M)
    table = re.compile(r"<table>(.*?)</table>", re.S)
    row = re.compile(r"<tr>(.*?)</tr>", re.S)
    counts: dict[str, int] = {}
    for path in sorted((REPO_ROOT / "docs" / "spec").glob("[0-2][0-9]_*.md")):
        text = path.read_text(encoding="utf-8")
        found = heading.search(text)
        if not found:
            continue
        block = table.search(text[found.end() :])
        if not block:
            continue
        # minus one for the header row
        counts[path.name[:2]] = len(row.findall(block.group(1))) - 1
    return counts


def test_every_criterion_id_is_unique_and_prefixed_by_its_document(
    shipped_map: dict[str, Any],
) -> None:
    prefixes: dict[str, set[str]] = {}
    seen: set[str] = set()
    for record in shipped_map["criteria"]:
        cid = str(record["id"])
        assert cid not in seen, f"duplicate id {cid}"
        seen.add(cid)
        doc = Path(str(record["document"])).name[:2]
        prefixes.setdefault(doc, set()).add(cid.rsplit("-", 1)[0])
    for doc, found in prefixes.items():
        assert len(found) == 1, f"doc {doc} mixes id prefixes: {sorted(found)}"


def test_no_criterion_cites_a_production_path_that_does_not_exist(
    shipped_map: dict[str, Any],
) -> None:
    missing: list[str] = []
    for record in shipped_map["criteria"]:
        for path in record.get("production_paths") or []:
            if not (REPO_ROOT / str(path)).exists():
                missing.append(f"{record['id']} -> {path}")
    assert missing == [], "\n".join(missing[:40])


@pytest.mark.parametrize(
    "field_name",
    ["auth", "occ", "idempotency", "historical_integrity", "agent_parity"],
)
def test_server_truth_axes_never_rest_on_frontend_evidence_alone(
    shipped_map: dict[str, Any], field_name: str
) -> None:
    offenders = [
        record["id"]
        for record in shipped_map["criteria"]
        if (nodes := record.get(field_name) or [])
        and not any(str(n).startswith("backend/tests/") for n in nodes)
    ]
    assert offenders == []


def test_the_gate_is_wired_into_ci() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "acceptance_semantic_scan.py" in workflow


def test_the_report_renders_without_raising(shipped_map: dict[str, Any]) -> None:
    rendered = scan.report(shipped_map)
    assert "## Coverage by document" in rendered
    assert "## Clause-level totals" in rendered


def test_helper_signature_is_stable() -> None:
    """Guards the import contract this module depends on."""
    for name in ("validate", "report", "main", "TestIndex"):
        assert hasattr(scan, name)
    assert isinstance(scan.main, Callable)


def test_a_future_dev_criterion_may_cite_inertness_evidence(fake_root: Path) -> None:
    """The one status where evidence is expected rather than forbidden.

    A Future-Dev capability is proven by a test showing it stays inert — no fake
    job, no fake output, no silent fallback. A covered inertness clause must not
    be read as "partially delivered".
    """
    record = make_record(
        status="deliberate_future_dev",
        notes="doc 22 marks this Future-Dev; the test proves the surface stays inert",
    )
    assert codes(fake_root, record) == []


def test_an_unquoted_node_id_containing_a_colon_is_reported_not_crashed(
    fake_root: Path,
) -> None:
    """YAML turns `- a > b: c` into a dict; the gate must survive it.

    vitest titles routinely contain ": ", so an author who forgets to quote one
    hands the scanner a dict where a string belongs. A gate that raises
    AttributeError on bad input teaches people to route around it.
    """
    broken = {"frontend/src/test/fake.test.tsx > Fake page > fail-closed": "hides the button"}
    record = make_record(
        test_evidence=[broken],
        evidence_type=["frontend_component"],
        positive=[broken],
        clauses=[{"id": "XX-01.c1", "text": "t", "status": "covered", "test_evidence": [broken]}],
    )
    found = codes(fake_root, record)
    assert "UNRESOLVED_NODE" in found
    assert "EVIDENCE_TYPE_MISMATCH" in found
