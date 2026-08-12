"""ADIM 24 — the load driver's decision logic, tested where it is cheap to test.

``scripts/loadgen.py`` only earns its place if the parts that decide pass/fail are
themselves under test. The driver lives outside ``backend/src`` (it is an operator
tool, not shipped code) and is loaded here by path, the same way
``docs/audit/acceptance_semantic_scan.py`` is executed by path from CI.

What is proven here, all of it pure and DB-free:

* the percentile is nearest-rank, so every number the report prints is a request that
  really happened rather than an interpolated one;
* a non-2xx status is an ERROR, not a sample — a run that 401s everywhere must fail
  loudly instead of publishing the rejection path's latency as the page's latency;
* a scenario that completed zero requests fails rather than passing vacuously;
* the ratio gate normalizes by the within-run control, so identical application cost
  on a machine that got 4x slower is a PASS, and 4x more application work on an
  unchanged machine is a FAIL. That asymmetry is the whole reason the gate exists.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_LOADGEN_PATH = Path(__file__).resolve().parents[3] / "scripts" / "loadgen.py"
_spec = importlib.util.spec_from_file_location("entropia_loadgen", _LOADGEN_PATH)
assert _spec is not None and _spec.loader is not None
loadgen = importlib.util.module_from_spec(_spec)
# Registered BEFORE exec: @dataclass resolves annotations through
# sys.modules[cls.__module__], so a module executed outside sys.modules blows up
# on its own first dataclass.
sys.modules[_spec.name] = loadgen
_spec.loader.exec_module(loadgen)


def _warm(**scenarios: float | None) -> dict[str, Any]:
    return {
        "phases": {
            "warm": {name: {"latency_ms": {"p95": value}} for name, value in scenarios.items()}
        }
    }


# ------------------------------------------------------------------ percentiles


def test_percentile_is_nearest_rank_not_interpolated() -> None:
    values = [float(n) for n in range(1, 101)]
    assert loadgen._percentile(values, 0.50) == 50.0
    assert loadgen._percentile(values, 0.95) == 95.0
    assert loadgen._percentile(values, 0.99) == 99.0


def test_percentile_of_a_single_sample_is_that_sample() -> None:
    """A smoke profile can legitimately produce one sample per scenario; the report
    must show that request, not None and not a zero."""
    assert loadgen._percentile([7.5], 0.99) == 7.5


def test_percentile_of_nothing_is_none_never_zero() -> None:
    assert loadgen._percentile([], 0.95) is None


# ----------------------------------------------------------------- error gating


def test_a_non_2xx_status_counts_as_an_error() -> None:
    sample = loadgen.Sample()
    sample.record(200, 5.0, 100)
    sample.record(401, 1.0, 20)
    sample.record(500, 2.0, 30)
    assert sample.errors == 2


def test_transport_failures_are_errors_too() -> None:
    """A connection reset is the most severe outcome a load run can have and it
    produces no status code — counting only statuses would score it as a clean run."""
    sample = loadgen.Sample()
    sample.record(200, 5.0, 100)
    sample.transport_errors = 3
    assert sample.errors == 3


def test_error_gate_names_the_failing_scenario() -> None:
    phases = {
        "warm": {
            "library": {
                "requests": 10,
                "errors": 2,
                "status_counts": {"200": 8, "403": 2},
                "transport_errors": 0,
            }
        }
    }
    failures = loadgen._error_gate(phases)
    assert len(failures) == 1
    assert "warm/library" in failures[0]


def test_a_scenario_that_never_ran_fails_instead_of_passing_silently() -> None:
    phases = {
        "warm": {
            "library": {
                "requests": 0,
                "errors": 0,
                "status_counts": {},
                "transport_errors": 0,
            }
        }
    }
    assert loadgen._error_gate(phases) == ["warm/library: no request completed"]


# ------------------------------------------------------------------ ratio gate


def test_a_uniformly_slower_machine_is_not_a_regression() -> None:
    """Everything got 4x slower INCLUDING the control: the box changed, not the code."""
    baseline = _warm(meta=10.0, library=30.0)
    current = _warm(meta=40.0, library=120.0)
    assert loadgen._ratio_gate(current, baseline, 2.0) == []


def test_application_work_growing_against_a_steady_control_fails() -> None:
    """The control is unchanged and the page tripled: that is the code."""
    baseline = _warm(meta=10.0, library=30.0)
    current = _warm(meta=10.0, library=120.0)
    failures = loadgen._ratio_gate(current, baseline, 2.0)
    assert len(failures) == 1
    assert "warm/library" in failures[0]


def test_the_control_itself_is_never_gated() -> None:
    """Gating the control on itself would always read 1.00x — a green light that
    proves nothing and hides that the control is the thing that moved."""
    baseline = _warm(meta=10.0)
    current = _warm(meta=400.0)
    assert loadgen._ratio_gate(current, baseline, 2.0) == []


def test_a_missing_control_is_reported_as_unmeasured_not_as_a_pass() -> None:
    baseline = _warm(meta=10.0, library=30.0)
    current = _warm(meta=None, library=30.0)
    failures = loadgen._ratio_gate(current, baseline, 2.0)
    assert len(failures) == 1
    assert "unmeasured" in failures[0]


def test_a_scenario_absent_from_the_baseline_is_skipped_not_invented() -> None:
    """A newly added scenario has nothing to compare against; the gate must not
    fabricate a verdict for it."""
    baseline = _warm(meta=10.0)
    current = _warm(meta=10.0, brand_new=900.0)
    assert loadgen._ratio_gate(current, baseline, 2.0) == []


# ------------------------------------------------------- exposition parsing


def test_prometheus_lines_parse_with_and_without_labels() -> None:
    text = "\n".join(
        [
            "# TYPE entropia_http_requests_total counter",
            'entropia_http_requests_total{method="GET",path="/library",status="200"} 12',
            "entropia_http_requests_in_flight 3",
            "# a comment",
            "malformed line without a value",
        ]
    )
    parsed = loadgen._parse_prometheus(text)
    assert parsed['entropia_http_requests_total{method="GET",path="/library",status="200"}'] == 12.0
    assert parsed["entropia_http_requests_in_flight"] == 3.0
    assert len(parsed) == 2


# --------------------------------------------------------------- the catalogue


def test_every_scenario_resolves_against_the_published_schema() -> None:
    """The same check CI runs offline: a renamed endpoint must break the load run's
    scenario list here, not silently reduce what the nightly run covers."""
    assert loadgen._check_catalogue() == 0


def test_the_control_scenario_is_registered_and_unauthenticated() -> None:
    """The ratio gate is only meaningful if the control does no application work."""
    control = next(s for s in loadgen.SCENARIOS if s.name == loadgen.CONTROL_SCENARIO)
    assert control.group == "control"
    assert control.path == "/api/v1/meta"


@pytest.mark.parametrize("scenario", loadgen.SCENARIOS, ids=lambda s: s.name)
def test_scenarios_are_read_only(scenario: Any) -> None:
    """A load driver that mutates would leave the stack it measured in a different
    state than it found it, and every later repeat would measure a different system."""
    assert scenario.method == "GET"


# ------------------------------------------ the ARMED gate (RC §6.7 / P10-7)
#
# The gate is only as good as the two things CI actually reads: the committed
# baseline and the band on the command line. Both are plain files that a later
# edit can quietly desynchronise from the reason they were chosen, so both are
# pinned here. These tests are the reason a "just widen it a bit" edit cannot
# land silently — the number lives in three places and they must agree.

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BASELINE_CI = _REPO_ROOT / "docs" / "performance" / "baseline_ci.json"
_PERF_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "performance.yml"

# Measured, not chosen: the worst control-normalised p95 ratio any of the six
# observed nightlies (2026-08-07..08-12) produced against the committed
# baseline. docs/performance/README.md section 6 derives the band from it.
_OBSERVED_WORST_RATIO = 1.62
_BAND = 2.5


def _committed_baseline() -> dict[str, Any]:
    import json

    return json.loads(_BASELINE_CI.read_text(encoding="utf-8"))


def test_the_committed_ci_baseline_is_a_real_nightly_from_the_gated_runner_class() -> None:
    """A hand-edited or laptop-recorded baseline would make every future ratio a
    comparison against fiction. docs/performance/README.md section 2: a baseline is
    only comparable inside its own runner class."""
    baseline = _committed_baseline()
    env = baseline["environment"]
    assert baseline["profile"] == "full"
    assert env["runner_class"] == "github-ubuntu-latest"
    assert env["auth"] == "session-login"
    assert env["git_sha"], "a baseline with no commit cannot be traced to the code it measured"
    # The nightly's own parameters. A baseline recorded at a different
    # concurrency is a different measurement wearing the same filename.
    assert (env["concurrency"], env["repeats"]) == (16, 40)


def test_the_committed_baseline_carries_a_control_and_no_errors() -> None:
    """Without the control the gate has nothing to normalise by and reports every
    run as unmeasured; with errors in it, the recorded p95 is the rejection path's."""
    warm = _committed_baseline()["phases"]["warm"]
    assert loadgen._control_p95(warm), "the control scenario has no p95 in the baseline"
    assert [name for name, s in warm.items() if s["errors"]] == []


def test_the_baseline_passes_its_own_gate() -> None:
    """Identity must be green. If comparing the frozen baseline to itself failed,
    the band would be below 1.0x and every nightly would be red from day one."""
    baseline = _committed_baseline()
    assert loadgen._ratio_gate(baseline, baseline, _BAND) == []


def test_a_three_times_regression_against_a_steady_control_fails_at_the_shipped_band() -> None:
    """The negative, proven rather than assumed: the band is wide, but it is not so
    wide that a real regression walks through it."""
    import copy

    baseline = _committed_baseline()
    regressed = copy.deepcopy(baseline)
    warm = regressed["phases"]["warm"]
    victim = next(name for name in warm if name != loadgen.CONTROL_SCENARIO)
    warm[victim]["latency_ms"]["p95"] *= 3.0

    failures = loadgen._ratio_gate(regressed, baseline, _BAND)
    assert len(failures) == 1
    assert f"warm/{victim}" in failures[0]


def test_the_band_still_clears_the_worst_night_that_was_actually_observed() -> None:
    """The band exists to survive normal weather. A later tightening that drops it
    under the worst spread six real nights produced would be re-introducing the
    flapping gate docs/performance/README.md section 1 refuses to build — so the
    observed number is pinned beside the band rather than left in a commit message."""
    import math

    assert _BAND > _OBSERVED_WORST_RATIO
    # Section 6 step 3: "roughly 1.5x the observed spread". Rounded UP to one
    # decimal, never down: rounding a derived band down turns a measured number
    # into a tighter one nobody measured.
    assert math.ceil(1.5 * _OBSERVED_WORST_RATIO * 10) / 10 == _BAND


def test_the_nightly_actually_passes_the_band_this_file_pins() -> None:
    """Three copies of one number — the workflow's --max-ratio, the band asserted
    above, and the baseline path — must not drift apart. A gate armed in the
    workflow with a different band than the one reasoned about here would be a
    gate nobody has justified."""
    import re

    # Comment lines are stripped first: the block above the step explains the
    # band in prose ("--compare is on the NIGHTLY, never on load-smoke"), and a
    # scan that counted prose would pin the explanation instead of the command.
    text = "\n".join(
        line
        for line in _PERF_WORKFLOW.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    ratios = re.findall(r"--max-ratio\s+([0-9.]+)", text)
    assert ratios == [str(_BAND)], (
        "performance.yml must arm the ratio gate exactly once, at the band this "
        f"file pins ({_BAND}); found {ratios}"
    )
    compares = re.findall(r"--compare\s+(\S+)", text)
    assert compares == ["../docs/performance/baseline_ci.json"]
    # `--compare` belongs to the nightly only. On `load-smoke` it would be the
    # per-PR millisecond gate section 1 exists to refuse.
    smoke_start = text.index("load-smoke:")
    full_start = text.index("load-full:")
    assert "--compare" not in text[smoke_start:full_start]
