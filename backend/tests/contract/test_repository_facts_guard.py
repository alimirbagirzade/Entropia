"""The documentation-truth gate must actually refuse a lie.

`scripts/generate_repository_facts.py` is only worth its CI minute if it fails on
the specific regressions this repo has already shipped: a stale alembic head in a
present-tense document, a landed kickoff that still reads as the live handoff, and
a generated artefact that was not regenerated after the tree moved.

Every test here is static and DB-free. The synthetic-root tests build a tiny fake
repository under `tmp_path` and drive the check functions directly, so a rule can
be proven to fire without waiting on the real tree; one live test then runs the
whole gate against this repository and asserts it is green.
"""

# ruff: noqa: RUF001
# Turkish is the documentation language of this repository, so the rule patterns and the
# fixtures that exercise them must contain dotless-i, s-cedilla and g-breve. RUF001 reads
# those as ambiguous look-alikes; here they are the literal characters being matched.

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "generate_repository_facts.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("repository_facts_gate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load()


# Enough of a facts dict for the assertion rules; the collectors are exercised
# by the live test below, not re-implemented here.
SYNTHETIC_FACTS = {
    "alembic": {"head": "0043_i08_registry_strategy_fks"},
    "engine": {
        "engine_version": "backtest-engine-v18-gap-adjusted-stop-fill",
        "shared_allocation_status": "future_dev",
    },
}


def _write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# The live gate


def test_the_repository_itself_passes_the_documentation_truth_gate() -> None:
    """The gate is green on this tree — so a later red build is a real finding."""
    assert gate.main(["--root", str(REPO_ROOT), "--check"]) == 0


def test_generated_artifacts_are_committed_and_parse() -> None:
    facts = json.loads((REPO_ROOT / gate.JSON_REL).read_text(encoding="utf-8"))
    assert facts["schema_version"] == gate.SCHEMA_VERSION
    assert (
        (REPO_ROOT / gate.MD_REL)
        .read_text(encoding="utf-8")
        .startswith("<!-- doc-status: current -->")
    )


def test_generated_facts_carry_no_commit_sha_timestamp_or_github_state() -> None:
    """A runtime fact would make the artefact impossible to keep green.

    A commit sha or a generation timestamp changes on every commit, so `--check`
    could never pass; GitHub state (open PR / issue counts) would additionally
    make an offline run fail for a reason no commit can fix.
    """
    raw = (REPO_ROOT / gate.JSON_REL).read_text(encoding="utf-8")
    facts = json.loads(raw)

    def keys(node: object) -> set[str]:
        if isinstance(node, dict):
            return set(node) | {k for v in node.values() for k in keys(v)}
        if isinstance(node, list):
            return {k for v in node for k in keys(v)}
        return set()

    forbidden = {
        "sha",
        "commit",
        "commit_sha",
        "head_sha",
        "generated_at",
        "timestamp",
        "date",
        "run_id",
        "open_prs",
        "open_issues",
        "pull_requests",
        "issues",
        "passed",
        "pass_count",
    }
    assert not (keys(facts) & forbidden)


def test_every_test_number_is_named_as_a_collection_not_a_pass_count() -> None:
    tests = json.loads((REPO_ROOT / gate.JSON_REL).read_text(encoding="utf-8"))["tests"]
    counters = [k for k, v in tests.items() if isinstance(v, int)]
    assert counters, "the tests block lost its counters"
    for name in counters:
        assert any(word in name for word in ("collected", "call_sites", "files", "markers")), (
            f"`tests.{name}` reads like a pass count; a static walk cannot know passes"
        )


# --------------------------------------------------------------------------
# Stale-assertion rules — each must fire on the lie and stay quiet on the truth


@pytest.mark.parametrize(
    ("line", "fires"),
    [
        ("alembic head `0035_portfolio_rules`", True),
        ("| Alembic head | **`0040_export_type_agent_pine`** (40 migration) |", True),
        ("**head = `0043_i08_registry_strategy_fks`**", False),
        # A parent revision named in narrative prose is not a head claim.
        ("(43 migration, tek head; `0042_package_import_source_name` üzerine)", False),
        # An explicitly historical line may name an old revision — that is how
        # this repo keeps its own drift auditable.
        ("*(Historical: the R2 close cited alembic `0035_portfolio_rules`.)*", False),
    ],
)
def test_stale_alembic_head_in_a_present_tense_document(
    tmp_path: Path, line: str, fires: bool
) -> None:
    _write(tmp_path, "CLAUDE.md", f"# guide\n\n{line}\n")
    failures = gate.check_assertions(tmp_path, SYNTHETIC_FACTS)
    assert bool(failures) is fires, failures


def test_stale_engine_version_and_shared_allocation_status(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "CLAUDE.md",
        "ENGINE_VERSION = `backtest-engine-v18-close-fill`\n"
        "SHARED_ALLOCATION_STATUS = `active_v1`\n",
    )
    failures = gate.check_assertions(tmp_path, SYNTHETIC_FACTS)
    assert any("ENGINE_VERSION" in f for f in failures)
    assert any("SHARED_ALLOCATION_STATUS" in f for f in failures)


@pytest.mark.parametrize(
    ("rule", "line"),
    [
        ("A08_COMPLETE", "A-08 screen reader acceptance: Complete."),
        ("WCAG_CONFORMANCE", "The product is WCAG 2.2 AA compliant."),
        ("RUN_IS_RESULT", "Backtest Run = Backtest Result, one row."),
        ("SIGNAL_IS_PACKAGE", "A Trading Signal is a Package like any other."),
        ("FUTURE_DEV_ACTIVE", "Future Dev produces its own artefacts."),
    ],
)
def test_each_forbidden_conflation_is_caught(tmp_path: Path, rule: str, line: str) -> None:
    _write(tmp_path, "README.md", f"# readme\n\n{line}\n")
    failures = gate.check_assertions(tmp_path, SYNTHETIC_FACTS)
    assert any(f"[{rule}]" in f for f in failures), failures


@pytest.mark.parametrize(
    "line",
    [
        "Backtest Run is NOT the same entity as Backtest Result.",
        "A Trading Signal is not a Package and never enters the package lifecycle.",
        "WCAG 2.2 AA 1.4.3 karşılanmıyor; ürün uyumlu sayılamaz.",
        "`capability.py` shared capital'in bu build'de **çalışmadığını** ilan eder.",
        "| Capability matrix | 62 rows (40 `active_v1`, 22 `future_dev`) |",
    ],
)
def test_a_sentence_that_states_the_invariant_is_not_flagged(tmp_path: Path, line: str) -> None:
    """The correction contains the same nouns as the error it corrects.

    Without the negation guard the gate would flag exactly the sentences the
    project wants documents to contain, which is how a gate gets switched off.
    """
    _write(tmp_path, "README.md", f"# readme\n\n{line}\n")
    assert gate.check_assertions(tmp_path, SYNTHETIC_FACTS) == []


def test_the_generated_block_is_not_scanned_as_prose(tmp_path: Path) -> None:
    """The generator writes those lines; `check_artifacts` already gates them."""
    _write(
        tmp_path,
        "README.md",
        f"# readme\n\n{gate.BEGIN_MARKER}\n| Alembic head | `0001_initial` |\n{gate.END_MARKER}\n",
    )
    assert gate.check_assertions(tmp_path, SYNTHETIC_FACTS) == []


# --------------------------------------------------------------------------
# Document classification


def test_an_unmarked_kickoff_fails_the_gate(tmp_path: Path) -> None:
    _write(tmp_path, "docs/STAGE9_KICKOFF.md", "# Stage 9 kickoff\n\nNext: do the thing.\n")
    failures = gate.check_classification(tmp_path)
    assert any("no `<!-- doc-status" in f for f in failures)


def test_a_marked_historical_kickoff_passes(tmp_path: Path) -> None:
    _write(tmp_path, "docs/STAGE9_KICKOFF.md", gate.HISTORICAL_BANNER + "\n# Stage 9\n")
    assert gate.check_classification(tmp_path) == []


def test_two_live_kickoffs_cannot_coexist(tmp_path: Path) -> None:
    """The failure this prevents: a superseded kickoff still reading as the handoff."""
    _write(tmp_path, "docs/STAGE9_KICKOFF.md", gate.CURRENT_BANNER + "\n# Stage 9\n")
    _write(tmp_path, "docs/STAGE10_KICKOFF.md", gate.CURRENT_BANNER + "\n# Stage 10\n")
    failures = gate.check_classification(tmp_path)
    assert any("more than one document claims" in f for f in failures)


def test_a_superseded_kickoff_cannot_stay_live(tmp_path: Path) -> None:
    """#697 shipped exactly this: ADIM 56 landed, its own kickoff was marked
    `historical`, and ADIM 55 kept the live marker. One `current` document, so the
    count rule stayed green while every fresh session read a stale resume seed."""
    _write(tmp_path, "docs/ADIM55_LANDED_KICKOFF.md", gate.CURRENT_BANNER + "\n# 55\n")
    _write(tmp_path, "docs/ADIM56_LANDED_KICKOFF.md", gate.HISTORICAL_BANNER + "\n# 56\n")
    failures = gate.check_classification(tmp_path)
    assert any("newer slice kickoff exists" in f for f in failures)
    assert any("docs/ADIM56_LANDED_KICKOFF.md" in f for f in failures)


def test_promoting_a_kickoff_that_is_already_behind_is_caught(tmp_path: Path) -> None:
    """#714 shipped the mirror image: ADIM 56 was promoted after ADIM 57 had landed.
    Correct when it was written, one slice behind by the time it was pushed."""
    _write(tmp_path, "docs/ADIM55_LANDED_KICKOFF.md", gate.HISTORICAL_BANNER + "\n# 55\n")
    _write(tmp_path, "docs/ADIM56_LANDED_KICKOFF.md", gate.CURRENT_BANNER + "\n# 56\n")
    _write(tmp_path, "docs/ADIM57_LANDED_KICKOFF.md", gate.HISTORICAL_BANNER + "\n# 57\n")
    failures = gate.check_classification(tmp_path)
    assert any("newer slice kickoff exists" in f for f in failures)


def test_the_newest_kickoff_may_be_live(tmp_path: Path) -> None:
    """Negative control: the rule must not fire on the arrangement it is asking for."""
    _write(tmp_path, "docs/ADIM55_LANDED_KICKOFF.md", gate.HISTORICAL_BANNER + "\n# 55\n")
    _write(tmp_path, "docs/ADIM56_LANDED_KICKOFF.md", gate.HISTORICAL_BANNER + "\n# 56\n")
    _write(tmp_path, "docs/ADIM57_LANDED_KICKOFF.md", gate.CURRENT_BANNER + "\n# 57\n")
    assert gate.check_classification(tmp_path) == []


def test_an_unnumbered_live_kickoff_is_left_alone(tmp_path: Path) -> None:
    """Deliberate silence, not an oversight: `STAGE*`/`O02`-style kickoffs carry no
    slice order, so there is nothing to compare them against. Ordering them by
    invention would redden a naming scheme this repo has not adopted."""
    _write(tmp_path, "docs/STAGE9_KICKOFF.md", gate.CURRENT_BANNER + "\n# stage 9\n")
    _write(tmp_path, "docs/ADIM57_LANDED_KICKOFF.md", gate.HISTORICAL_BANNER + "\n# 57\n")
    assert gate.check_classification(tmp_path) == []


def test_a_history_record_may_never_be_marked_current(tmp_path: Path) -> None:
    _write(tmp_path, "docs/PROJECT_HISTORY.md", gate.CURRENT_BANNER + "\n# history\n")
    failures = gate.check_classification(tmp_path)
    assert any("never the current handoff" in f for f in failures)


# --------------------------------------------------------------------------
# Artefact freshness


def test_a_tampered_artifact_is_reported_stale(tmp_path: Path) -> None:
    facts = {**SYNTHETIC_FACTS}
    _write(tmp_path, gate.JSON_REL, '{"schema_version": 1}\n')
    _write(tmp_path, gate.MD_REL, "# hand-edited\n")
    _write(tmp_path, "README.md", f"{gate.BEGIN_MARKER}\nstale\n{gate.END_MARKER}\n")

    real = gate.render_summary_rows
    gate.render_summary_rows = lambda _facts: ["| Fact | Value |", "|---|---|"]
    try:
        gate.render_markdown = lambda _facts: "# generated\n"
        gate.render_json = lambda _facts: '{"schema_version": 99}\n'
        failures = gate.check_artifacts(tmp_path, facts)
    finally:
        gate.render_summary_rows = real

    assert len(failures) == 3
    assert any(gate.JSON_REL in f for f in failures)
    assert any(gate.MD_REL in f for f in failures)
    assert any(gate.README_REL in f for f in failures)


def test_a_readme_without_the_markers_fails_loudly(tmp_path: Path) -> None:
    """Deleting the markers must not be a silent way to opt out of the gate."""
    with pytest.raises(SystemExit) as excinfo:
        gate.splice_readme("# readme with no markers\n", "block")
    assert "missing the generated markers" in str(excinfo.value)


# --------------------------------------------------------------------------
# Collector edge case that the deploy actually depends on


def test_a_split_revision_graph_is_reported_as_multiple_heads(tmp_path: Path) -> None:
    """Two heads make `alembic upgrade head` ambiguous — the branch cannot deploy."""
    versions = tmp_path / "backend" / "alembic" / "versions"
    versions.mkdir(parents=True)
    (versions / "0001_a.py").write_text(
        'revision: str = "0001_a"\ndown_revision: str | None = None\n', encoding="utf-8"
    )
    for name in ("0002_b", "0002_c"):
        (versions / f"{name}.py").write_text(
            f'revision: str = "{name}"\ndown_revision: str | None = "0001_a"\n',
            encoding="utf-8",
        )

    alembic = gate.collect_alembic(tmp_path)
    assert alembic["single_head"] is False
    assert alembic["head"] is None
    assert alembic["heads"] == ["0002_b", "0002_c"]
    assert alembic["revision_count"] == 3


# --------------------------------------------------------------------------
# Codemap coverage — a map that stops naming its subject must go red
#
# The counts this replaces were hand-written and went stale twice (`queries`
# said 37 against 38, `jobs` said 14 against 16). The deeper defect is that a
# count cannot see the drift that produced it: two `jobs` modules had no row at
# all while the header still advertised a number. What is gated is therefore
# membership, not arithmetic.


COMPLETE_LAYERS = (
    "# BACKEND_LAYERS\n\n"
    "## `application/commands/` — yazma yolu\n\n"
    "| `market_data.py` | writes |\n\n"
    "## `application/queries/` — okuma yolu\n\n"
    "| `market_data.py` | reads |\n\n"
    "## `application/jobs/` — durable worker gövdeleri\n\n"
    "| `delivery.py` | shared guard |\n"
)

COMPLETE_ACTORS = (
    '@dramatiq.actor(queue_name="data", max_retries=3)\n'
    "def run_market_data_analysis(job_id: str) -> None:\n"
    "    pass\n"
)

COMPLETE_JOBS_MAP = (
    "# JOBS_AND_EVENTS\n\n| `run_market_data_analysis` | `data` | `market_data.py` |\n"
)

# Only the branch `check_codemap_coverage` reads; the collectors that fill this
# key for real are exercised by the live tree, not re-implemented here.
LAYER_FACTS = {
    "backend_layers": {
        "application_module_names": {
            "commands": ["market_data.py"],
            "queries": ["market_data.py"],
            "jobs": ["delivery.py"],
        }
    }
}


def _codemap_tree(tmp_path: Path, *, layers: str, actors: str, jobs_map: str) -> Path:
    _write(tmp_path, gate.BACKEND_LAYERS_REL, layers)
    _write(tmp_path, gate.JOBS_AND_EVENTS_REL, jobs_map)
    _write(tmp_path, gate.ACTORS_REL, actors)
    return tmp_path


def test_a_complete_pair_of_codemaps_is_quiet(tmp_path: Path) -> None:
    """A map that names everything stays silent — so a finding below is real."""
    root = _codemap_tree(
        tmp_path,
        layers=COMPLETE_LAYERS,
        actors=COMPLETE_ACTORS,
        jobs_map=COMPLETE_JOBS_MAP,
    )
    assert gate.check_codemap_coverage(root, LAYER_FACTS) == []


def test_a_module_with_no_codemap_row_is_reported(tmp_path: Path) -> None:
    """The real regression: `delivery.py` and `heartbeat.py` were never named."""
    root = _codemap_tree(
        tmp_path,
        layers=COMPLETE_LAYERS.replace("| `delivery.py` | shared guard |\n", ""),
        actors=COMPLETE_ACTORS,
        jobs_map=COMPLETE_JOBS_MAP,
    )
    failures = gate.check_codemap_coverage(root, LAYER_FACTS)
    assert len(failures) == 1, failures
    assert "application/jobs/delivery.py" in failures[0]


def test_a_namesake_in_another_layer_does_not_cover_a_missing_row(tmp_path: Path) -> None:
    """`market_data.py` exists in three layers; a whole-file match would lie."""
    root = _codemap_tree(
        tmp_path,
        layers=COMPLETE_LAYERS.replace("| `market_data.py` | reads |\n", ""),
        actors=COMPLETE_ACTORS,
        jobs_map=COMPLETE_JOBS_MAP,
    )
    failures = gate.check_codemap_coverage(root, LAYER_FACTS)
    assert len(failures) == 1, failures
    assert "application/queries/market_data.py" in failures[0]


def test_an_actor_with_no_row_is_reported(tmp_path: Path) -> None:
    root = _codemap_tree(
        tmp_path,
        layers=COMPLETE_LAYERS,
        actors=COMPLETE_ACTORS,
        jobs_map="# JOBS_AND_EVENTS\n\nno actor table here\n",
    )
    failures = gate.check_codemap_coverage(root, LAYER_FACTS)
    assert len(failures) == 1, failures
    assert "run_market_data_analysis" in failures[0]


def test_an_actor_filed_under_the_wrong_queue_is_reported(tmp_path: Path) -> None:
    """The queue is the operationally load-bearing half of that row.

    `data` is deliberately excluded from the scheduler's redelivery sweep, so a
    row filing an actor under another queue misdescribes whether a lost message
    ever comes back.
    """
    root = _codemap_tree(
        tmp_path,
        layers=COMPLETE_LAYERS,
        actors=COMPLETE_ACTORS,
        jobs_map=COMPLETE_JOBS_MAP.replace("| `data` |", "| `maintenance` |"),
    )
    failures = gate.check_codemap_coverage(root, LAYER_FACTS)
    assert len(failures) == 1, failures
    assert "real queue `data`" in failures[0]


def test_the_layer_counts_are_derived_never_transcribed() -> None:
    """The generated artefact owns the numbers the codemap header used to state."""
    layers = json.loads((REPO_ROOT / gate.JSON_REL).read_text(encoding="utf-8"))["backend_layers"]
    assert layers["application_module_names"], "the layer walk found nothing"
    for layer, names in layers["application_module_names"].items():
        assert layers["application_module_counts"][layer] == len(names)
        assert "__init__.py" not in names
    assert layers["domain_package_count"] == len(layers["domain_packages"])
    assert not [p for p in layers["domain_packages"] if p.startswith("_")]
