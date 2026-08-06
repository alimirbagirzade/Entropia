"""The alert rules must stay tied to metrics this deployment actually emits (ADIM 25).

An alerting file rots in a way dashboards do not: a rule whose metric was renamed
keeps parsing, keeps loading into Prometheus, and simply never fires again. It
reads as coverage while providing none, and nothing notices until the incident it
was supposed to catch. So the allowed metric set here is NOT a hand-maintained
list — it is DERIVED from the exposition code itself, by rendering both halves of
``GET /metrics`` and reading back the ``# TYPE`` lines. Rename a metric in
``infrastructure/observability/metrics.py`` or ``routes/metrics.py`` and the alert
that referenced it fails this test in the same commit.

The same applies to label VALUES: ``entropia_jobs_depth`` is labelled with
``str(JobStatus)``, so a rule matching ``status="failed"`` would silently match
nothing (the real terminal value is ``failed_final``). That class of typo is
checked against the enum rather than against a copy of it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from entropia.application.queries.job_gauges import JobGauges
from entropia.apps.api.routes.metrics import _render_operational_gauges
from entropia.domain.lifecycle.enums import JobStatus
from entropia.infrastructure.observability.metrics import render_process_metrics

REPO_ROOT = Path(__file__).resolve().parents[3]
RULES_PATH = REPO_ROOT / "ops" / "alerts" / "entropia.rules.yml"

#: Series Prometheus synthesises for every scrape target. Not produced by us,
#: but legitimately referenceable — ``up`` is how a dead API is detected at all.
SCRAPER_PROVIDED = {"up"}

#: PromQL syntax that survives the tokenizer below. Kept deliberately small: an
#: unknown token must fail loudly as a suspected metric name rather than be
#: waved through, so adding a new PromQL function is an explicit edit here.
PROMQL_TOKENS = {
    "sum",
    "rate",
    "delta",
    "increase",
    "absent",
    "min_over_time",
    "max_over_time",
    "avg_over_time",
    "histogram_quantile",
    "by",
    "without",
    "and",
    "or",
    "unless",
    "on",
    "ignoring",
    "Inf",
}

REQUIRED_ANNOTATIONS = {
    "summary",
    "derivation",
    "diagnosis",
    "response",
    "mitigation",
    "recovery",
    "escalation",
    "false_positives",
    "runbook",
}

VALID_SEVERITIES = {"page", "ticket"}


def _emitted_metric_names() -> set[str]:
    """Every series name ``GET /metrics`` can emit, read out of the real renderers."""
    exposition = render_process_metrics() + _render_operational_gauges(
        JobGauges(
            queue_depth=(("backtest", JobStatus.RUNNING, 1),),
            outbox_lag_seconds=1.0,
            oldest_lease_age_seconds=1.0,
            worker_heartbeat_age_seconds=1.0,
        )
    )
    names: set[str] = set()
    for line in exposition.splitlines():
        if not line.startswith("# TYPE "):
            continue
        _, _, name, kind = line.split(maxsplit=3)
        names.add(name)
        if kind == "histogram":
            # A histogram family is three wire-level series, and the alerts
            # legitimately reference the bucket one directly.
            names.update({f"{name}_bucket", f"{name}_sum", f"{name}_count"})
    return names


def _rules() -> list[tuple[str, dict]]:
    document = yaml.safe_load(RULES_PATH.read_text())
    return [(group["name"], rule) for group in document["groups"] for rule in group["rules"]]


def _referenced_metric_names(expr: str) -> set[str]:
    """Metric names in an expression: strip everything that is not one, then tokenize.

    Each strip closes a specific hole found while reviewing this file:

    * ``{...}`` — label matchers. Their VALUES are checked separately; their keys
      are not metric names.
    * ``[5m]`` — range selectors.
    * ``by (queue)`` / ``without (job)`` — grouping labels. Without this strip a
      perfectly legal ``sum by (queue) (entropia_jobs_depth)`` reported ``queue``
      as an unknown metric, i.e. the gate rejected correct PromQL. That is worse
      than a miss: it teaches the next author to distrust the test.
    * ``offset 5m`` — the modifier keyword and its duration.
    """
    stripped = re.sub(r"\{[^}]*\}", " ", expr)
    stripped = re.sub(r"\[[^\]]*\]", " ", stripped)
    stripped = re.sub(
        r"\b(?:by|without|on|ignoring|group_left|group_right)\s*\([^)]*\)", " ", stripped
    )
    stripped = re.sub(r"\boffset\s+[0-9]+[smhdwy]\b", " ", stripped)
    tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", stripped))
    return tokens - PROMQL_TOKENS


ALL_RULES = _rules()
RULE_IDS = [rule["alert"] for _, rule in ALL_RULES]


def test_the_rules_file_parses_and_is_not_empty() -> None:
    assert ALL_RULES, "ops/alerts/entropia.rules.yml declares no alerts"


@pytest.mark.parametrize(("group", "rule"), ALL_RULES, ids=RULE_IDS)
def test_every_alert_references_only_metrics_we_emit(group: str, rule: dict) -> None:
    """The anti-rot gate: no rule may name a series nothing produces."""
    allowed = _emitted_metric_names() | SCRAPER_PROVIDED
    referenced = _referenced_metric_names(rule["expr"])
    unknown = referenced - allowed
    assert not unknown, (
        f"{rule['alert']} references {sorted(unknown)}, which GET /metrics does not emit. "
        f"Emitted series: {sorted(allowed)}"
    )


@pytest.mark.parametrize(("group", "rule"), ALL_RULES, ids=RULE_IDS)
def test_every_alert_is_actionable(group: str, rule: dict) -> None:
    """Severity, a duration, and the full operator annotation set are mandatory."""
    assert rule["labels"]["severity"] in VALID_SEVERITIES
    assert rule["labels"].get("component"), f"{rule['alert']} declares no component"
    assert rule.get("for"), f"{rule['alert']} has no `for:` and would fire on a single sample"

    missing = REQUIRED_ANNOTATIONS - set(rule["annotations"])
    assert not missing, f"{rule['alert']} is missing annotations: {sorted(missing)}"
    for key in REQUIRED_ANNOTATIONS:
        assert rule["annotations"][key].strip(), f"{rule['alert']}.{key} is blank"


@pytest.mark.parametrize(("group", "rule"), ALL_RULES, ids=RULE_IDS)
def test_every_alert_points_at_a_runbook_that_exists(group: str, rule: dict) -> None:
    """A runbook link that 404s at 3am is worse than no link."""
    runbook = REPO_ROOT / rule["annotations"]["runbook"]
    assert runbook.is_file(), f"{rule['alert']} points at missing runbook {runbook}"


@pytest.mark.parametrize(("group", "rule"), ALL_RULES, ids=RULE_IDS)
def test_job_status_label_matchers_name_real_states(group: str, rule: dict) -> None:
    """``status="failed"`` would match nothing forever — the real value is ``failed_final``."""
    valid = {str(status) for status in JobStatus}
    for value in re.findall(r'status\s*=\s*"([a-z_]+)"', rule["expr"]):
        assert value in valid, (
            f"{rule['alert']} matches status={value!r}, which is not a JobStatus value. "
            f"Valid: {sorted(valid)}"
        )


def test_paging_alerts_cover_the_dependencies_that_take_the_product_down() -> None:
    """A regression guard on coverage, not on wording: these must stay page-severity."""
    paging = {rule["alert"] for _, rule in ALL_RULES if rule["labels"]["severity"] == "page"}
    for required in (
        "EntropiaApiDown",
        "EntropiaMetricsDatabaseProbeFailing",
        "EntropiaWorkerHeartbeatStale",
        "EntropiaJobLeaseStuck",
    ):
        assert required in paging, f"{required} must remain a paging alert"


# --------------------------------------------------------------------------------
# Derivation guards.
#
# Every threshold in the rules file claims, in its `derivation` annotation, to be
# a multiple of a shipped configuration default rather than a number somebody
# liked. That claim is only worth anything if it is checked: change
# SCHEDULER_TICK_SECONDS from 30s to 5s and these tests fail, forcing the alert
# to be revisited instead of silently becoming 36 missed ticks instead of 6.
#
# This is also the guard against re-introducing an invented latency SLO.
# docs/performance/README.md leaves the p95 row deliberately blank; no rule here
# may quietly fill it in.
# --------------------------------------------------------------------------------


def _bound(alert_name: str) -> float:
    for _, rule in ALL_RULES:
        if rule["alert"] == alert_name:
            match = re.search(r">\s*([0-9.]+)\s*$", rule["expr"].strip())
            assert match, f"{alert_name} has no trailing numeric bound: {rule['expr']}"
            return float(match.group(1))
    raise AssertionError(f"{alert_name} is not declared")


def test_worker_and_outbox_thresholds_are_multiples_of_the_scheduler_tick() -> None:
    from entropia.config import get_settings

    tick = get_settings().scheduler_tick_seconds

    assert _bound("EntropiaWorkerHeartbeatStale") == 6 * tick
    assert _bound("EntropiaOutboxLagGrowing") == 10 * tick
    assert _bound("EntropiaOutboxLagSevere") == 60 * tick


def test_the_lease_threshold_is_twice_the_scheduler_reclaim_bound() -> None:
    """By 2x JOB_STALE_AFTER_SECONDS a healthy sweep has had ~20 chances to reclaim."""
    from entropia.config import get_settings

    assert _bound("EntropiaJobLeaseStuck") == 2 * get_settings().job_stale_after_seconds


def test_the_queue_drain_window_is_twice_the_redelivery_grace() -> None:
    from entropia.config import get_settings

    grace_minutes = get_settings().job_redeliver_grace_seconds / 60
    for _, rule in ALL_RULES:
        if rule["alert"] == "EntropiaQueueNeverDrains":
            window = re.search(r"\[(\d+)m\]", rule["expr"])
            assert window, "EntropiaQueueNeverDrains lost its range selector"
            assert float(window.group(1)) == 2 * grace_minutes
            return
    raise AssertionError("EntropiaQueueNeverDrains is not declared")


def test_no_rule_invents_an_absolute_latency_target() -> None:
    """The only latency bound permitted is the histogram's own largest bucket."""
    from entropia.infrastructure.observability.metrics import _BUCKETS

    largest = str(max(_BUCKETS))
    for _, rule in ALL_RULES:
        buckets = re.findall(r'le\s*=\s*"([^"]+)"', rule["expr"])
        for value in buckets:
            assert value in {largest, "+Inf"}, (
                f"{rule['alert']} compares against le={value!r}. Only the shipped largest "
                f"bucket ({largest}) and +Inf are structural; anything else is a new "
                "latency SLO, which docs/performance/README.md deliberately leaves unset."
            )


def test_absent_is_always_joined_with_on_to_match_label_sets() -> None:
    """`and absent(...)` without `on()` silently evaluates to the empty vector.

    `absent()` over a selector carrying no equality matchers returns a
    LABEL-LESS element. `and` matches on the full label set by default, so
    joining it to `up{job="entropia-api"}` — which carries `job` and `instance` —
    never matches and the alert can never fire. It parses, it loads, it reads as
    coverage, and it is dead. `on()` matches on the empty label set, which is
    what these rules mean.

    Caught while reviewing this very slice; the guard exists so the next author
    does not have to catch it again.
    """
    for _, rule in ALL_RULES:
        expr = " ".join(rule["expr"].split())
        if "absent(" not in expr:
            continue
        assert "and on()" in expr or "unless on()" in expr, (
            f"{rule['alert']} joins absent() without `on()`; it will never fire. Expr: {expr}"
        )


def test_no_rule_selects_a_metric_through_a_name_matcher() -> None:
    """``{__name__="..."}`` would smuggle a metric name past the tokenizer.

    The label-matcher strip erases the whole ``{...}`` block, so
    ``{__name__="entropia_bogus"} > 0`` — valid PromQL selecting a series nothing
    emits — reported ZERO referenced metrics and sailed through the emitted-names
    gate. Rules must name their metric directly, where it can be checked.
    """
    for _, rule in ALL_RULES:
        assert "__name__" not in rule["expr"], (
            f"{rule['alert']} selects via __name__, which bypasses the emitted-metric gate"
        )


def test_the_tokenizer_still_catches_a_bogus_metric_name() -> None:
    """A guard on the guard: prove the gate would actually fail on a typo."""
    allowed = _emitted_metric_names() | SCRAPER_PROVIDED

    assert _referenced_metric_names("entropia_bogus_metric > 0") - allowed == {
        "entropia_bogus_metric"
    }
    # ...and does not cry wolf over legal grouping or modifier syntax.
    assert not _referenced_metric_names("sum by (queue) (entropia_jobs_depth)") - allowed
    assert not _referenced_metric_names("entropia_outbox_lag_seconds offset 5m") - allowed
