"""The notification path must stay wired, and must stay fail-closed (ADIM 31).

ADIM 25 shipped eleven alert rules. ADIM 26 proved they are CORRECT — valid
PromQL over metrics that exist, thresholds derived from shipped configuration,
each one evaluated to ``alertstate="firing"`` against synthetic series in a
blocking CI job. Neither slice made a single one of them reach a human. Seven
carry ``severity: page``; ``severity`` was a label with no reader. The release
readiness report recorded that as a blocker
(``docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md`` §6.3) and ADIM 31
closed it by shipping the path rather than by signing for its absence.

WHY THIS FILE EXISTS ON TOP OF ``scripts/alert-notification-gate.sh``. That gate
runs a real ``amtool check-config``, which is necessary and not sufficient —
MEASURED, not assumed. ``amtool check-config`` returns SUCCESS on a receiver
declared with NO notifier configs at all, i.e. the silent black hole this slice
bans by name ("placeholder receiver YOK · /dev/null route YOK · sessiz düşürme
YOK"). It has no opinion about whether ``page`` and ``ticket`` end up at the same
place, about whether an endpoint was inlined into a tracked file, or about
whether the deployment that runs the config can start without a destination. All
of that is structure, and structure is what this file checks.

The division of labour across the three, deliberately:

  * this file                                — structure, on every PR (backend job)
  * scripts/alert-notification-gate.sh       — a real Alertmanager loads it (alerts job)
  * scripts/alert-notification-proof.sh      — a real alert reaches a real
                                               receiver. NOT a CI gate: minutes of
                                               wall clock and three containers.
                                               Run on change, recorded as release
                                               evidence.

The reason the split is written down is that this whole slice exists because a
green ``Alert rules — promtool`` badge was being read as "alerting works".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
ALERTMANAGER_CONFIG_PATH = REPO_ROOT / "ops" / "alertmanager" / "alertmanager.yml"
ALERTMANAGER_ENTRYPOINT_PATH = REPO_ROOT / "ops" / "alertmanager" / "entrypoint.sh"
PROMETHEUS_CONFIG_PATH = REPO_ROOT / "ops" / "prometheus" / "prometheus.yml"
PROMETHEUS_ENTRYPOINT_PATH = REPO_ROOT / "ops" / "prometheus" / "entrypoint.sh"
RULES_PATH = REPO_ROOT / "ops" / "alerts" / "entropia.rules.yml"
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"

#: The variable a deployment MUST supply. Named here so a rename has to be
#: deliberate in three places at once (config, entrypoint, compose).
NOTIFY_URL_VAR = "ALERTMANAGER_NOTIFY_URL"

#: Compose profile the observability plane hides behind, so that a plain
#: `docker compose up` — which every acceptance script runs — is unaffected.
OBSERVABILITY_PROFILE = "observability"


def _alertmanager_config() -> dict:
    return yaml.safe_load(ALERTMANAGER_CONFIG_PATH.read_text())


def _compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text())


def _service(name: str) -> dict:
    services = _compose().get("services") or {}
    assert name in services, f"docker-compose.yml declares no `{name}` service"
    return services[name] or {}


def _routes(node: dict) -> list[dict]:
    """The route tree, flattened depth-first (the root included)."""
    found = [node]
    for child in node.get("routes") or []:
        found.extend(_routes(child))
    return found


def _rules() -> list[dict]:
    document = yaml.safe_load(RULES_PATH.read_text())
    return [rule for group in document["groups"] for rule in group["rules"]]


def _severity_of(alertname: str) -> str | None:
    for rule in _rules():
        if rule["alert"] == alertname:
            return (rule.get("labels") or {}).get("severity")
    return None


def _alertnames_in_matchers(matchers: list[str]) -> set[str]:
    """Alert names named by ``alertname="X"`` or ``alertname=~"A|B"`` matchers."""
    names: set[str] = set()
    for matcher in matchers:
        exact = re.fullmatch(r'alertname\s*=\s*"([^"]+)"', matcher)
        if exact:
            names.add(exact.group(1))
            continue
        regex = re.fullmatch(r'alertname\s*=~\s*"([^"]+)"', matcher)
        if regex:
            names.update(part for part in regex.group(1).split("|") if part)
    return names


# --------------------------------------------------------------------------------
# The routing tree: every alert must reach a receiver, and page must not be ticket.
# --------------------------------------------------------------------------------


def test_the_alertmanager_config_parses_and_declares_a_route() -> None:
    config = _alertmanager_config()
    assert config.get("route"), "ops/alertmanager/alertmanager.yml declares no route"
    assert config.get("receivers"), "ops/alertmanager/alertmanager.yml declares no receivers"


def test_every_routed_receiver_is_declared() -> None:
    """A route naming a receiver that does not exist is a load error, not a drop —
    but the mirror case (a declared receiver nothing routes to) is dead config,
    and both mean somebody edited one half of a pair."""
    config = _alertmanager_config()
    declared = {receiver["name"] for receiver in config["receivers"]}
    routed = {route["receiver"] for route in _routes(config["route"]) if route.get("receiver")}

    assert routed <= declared, f"routes name undeclared receivers: {sorted(routed - declared)}"
    assert declared <= routed, f"receivers nothing routes to: {sorted(declared - routed)}"


def test_no_receiver_is_a_silent_black_hole() -> None:
    """THE CHECK amtool CANNOT MAKE.

    ``amtool check-config`` returns SUCCESS on a receiver with no notifier
    configs whatsoever — measured against v0.28.1 while building this gate, not
    inferred. Such a receiver accepts everything routed to it and discards it,
    which is indistinguishable from working right up until the incident. A
    "temporary placeholder receiver" is exactly this shape, so it is rejected
    here rather than trusted to be temporary.
    """
    for receiver in _alertmanager_config()["receivers"]:
        # Any `*_configs` key, not just `webhook_configs`: a future email or
        # PagerDuty receiver must satisfy the same rule without editing this test.
        configured = [
            entry
            for key, value in receiver.items()
            if key.endswith("_configs")
            for entry in (value or [])
        ]
        assert configured, (
            f"receiver {receiver['name']!r} has no notifier config at all. It would accept "
            "every alert routed to it and deliver none, while amtool reports SUCCESS."
        )


def test_no_endpoint_is_inlined_into_the_tracked_config() -> None:
    """A webhook URL is routinely itself a credential.

    Slack, PagerDuty and Opsgenie ingest URLs embed a key, so an inlined ``url``
    would commit the credential AND hard-code a destination this repository is
    not entitled to choose. Every endpoint must come from ``url_file``, the same
    idiom ops/prometheus/prometheus.yml uses for ``credentials_file``.
    """
    for receiver in _alertmanager_config()["receivers"]:
        for entry in receiver.get("webhook_configs") or []:
            assert "url" not in entry, (
                f"receiver {receiver['name']!r} inlines a webhook `url`. Use `url_file` — "
                "the destination is a deployment secret, not repository content."
            )
            assert entry.get("url_file"), (
                f"receiver {receiver['name']!r} declares a webhook with neither url nor url_file"
            )


def test_page_and_ticket_do_not_collapse_into_one_receiver() -> None:
    """The severity split has to be real, not decorative.

    Before ADIM 31, ``severity: page`` and ``severity: ticket`` were labels
    nothing read — four degradation rules were indistinguishable from seven
    outage rules. Routing both to a single receiver would restore exactly that
    state while looking configured.
    """
    config = _alertmanager_config()
    by_severity: dict[str, str] = {}
    for route in _routes(config["route"])[1:]:  # skip the root: it has no matcher
        for matcher in route.get("matchers") or []:
            match = re.fullmatch(r'severity\s*=\s*"([^"]+)"', matcher)
            if match:
                by_severity[match.group(1)] = route["receiver"]

    assert {"page", "ticket"} <= set(by_severity), (
        f"the route tree resolves severities {sorted(by_severity)}; both page and ticket must route"
    )
    assert by_severity["page"] != by_severity["ticket"], (
        f"page and ticket both route to {by_severity['page']!r} — the split is decorative"
    )


def test_every_severity_the_rules_emit_has_a_route() -> None:
    """A rule labelled with a severity nothing matches falls to the root.

    The root is a REAL receiver on purpose (see below), so nothing is lost — but
    a severity with no branch of its own is silently getting page timings, and
    that should be a deliberate edit rather than a discovery during an incident.
    """
    emitted = {(rule.get("labels") or {}).get("severity") for rule in _rules()}
    emitted.discard(None)

    routed = set()
    for route in _routes(_alertmanager_config()["route"])[1:]:
        for matcher in route.get("matchers") or []:
            match = re.fullmatch(r'severity\s*=\s*"([^"]+)"', matcher)
            if match:
                routed.add(match.group(1))

    assert emitted <= routed, (
        f"ops/alerts/entropia.rules.yml emits severities with no route: {sorted(emitted - routed)}"
    )


def test_the_root_receiver_is_a_real_one() -> None:
    """An alert matching no branch must PAGE, never vanish.

    Alertmanager's usual idiom is a ``null`` catch-all. Here that would rebuild
    the exact blind spot this slice removed: a rule shipped without a severity
    label would be routed into nothing and nobody would learn it until the
    outage it was written for.
    """
    config = _alertmanager_config()
    root_receiver = config["route"].get("receiver")
    assert root_receiver, "the root route declares no receiver — unmatched alerts would be dropped"
    assert root_receiver in {r["name"] for r in config["receivers"]}
    assert "null" not in root_receiver.lower(), (
        f"the root route falls through to {root_receiver!r}, which reads as a drain"
    )


def test_resolved_notifications_are_sent() -> None:
    """Several rules' ``recovery`` annotations are written as conditions someone
    is expected to observe. Without ``send_resolved`` an operator who was paged is
    never told the page cleared."""
    for receiver in _alertmanager_config()["receivers"]:
        for entry in receiver.get("webhook_configs") or []:
            assert entry.get("send_resolved") is True, (
                f"receiver {receiver['name']!r} does not send resolved notifications"
            )


# --------------------------------------------------------------------------------
# Inhibition: real alert names, and never a ticket silencing a page.
# --------------------------------------------------------------------------------


def _inhibit_rules() -> list[dict]:
    return _alertmanager_config().get("inhibit_rules") or []


@pytest.mark.parametrize("index", range(len(_inhibit_rules())))
def test_inhibit_rules_name_alerts_that_exist(index: int) -> None:
    """An inhibit rule keyed on a renamed alert is dead configuration.

    It parses, it loads, it suppresses nothing — the same shape as the ADIM 25
    rules that could never fire, one layer up the stack.
    """
    declared = {rule["alert"] for rule in _rules()}
    rule = _inhibit_rules()[index]
    for field in ("source_matchers", "target_matchers"):
        for name in _alertnames_in_matchers(rule.get(field) or []):
            assert name in declared, (
                f"inhibit_rules[{index}].{field} names {name!r}, which no alert rule declares"
            )


@pytest.mark.parametrize("index", range(len(_inhibit_rules())))
def test_no_ticket_severity_alert_can_suppress_a_page(index: int) -> None:
    """Inhibition must only ever suppress DOWNWARD.

    Each shipped inhibition encodes a containment claim ("the API being down
    contains its own 5xx"), and in every one the source alert is itself
    delivered, so the incident still reaches someone. A ticket suppressing a page
    would invert that: the loud signal disappears behind the quiet one.
    """
    rule = _inhibit_rules()[index]
    sources = {
        _severity_of(name) for name in _alertnames_in_matchers(rule.get("source_matchers") or [])
    }
    targets = {
        _severity_of(name) for name in _alertnames_in_matchers(rule.get("target_matchers") or [])
    }

    if "page" in targets:
        assert sources == {"page"}, (
            f"inhibit_rules[{index}] lets a {sorted(s for s in sources if s)} alert suppress a page"
        )


# --------------------------------------------------------------------------------
# Fail-closed: no destination, no process.
# --------------------------------------------------------------------------------


def test_the_alertmanager_service_has_no_default_destination() -> None:
    """The one thing this repository must never invent.

    A default URL here would be either a lie (an endpoint nobody reads) or a
    leak (somebody's real webhook, committed). Compose passes the variable
    through with an EMPTY fallback on purpose — the refusal happens inside the
    container, because a `${VAR:?}` required-marker aborts interpolation for the
    whole file and would break every `docker compose up` in the repo even though
    this service is profiled off.
    """
    environment = _service("alertmanager").get("environment") or {}
    assert NOTIFY_URL_VAR in environment, (
        f"the alertmanager service does not pass {NOTIFY_URL_VAR} through at all"
    )
    value = str(environment[NOTIFY_URL_VAR])
    assert value == f"${{{NOTIFY_URL_VAR}:-}}", (
        f"{NOTIFY_URL_VAR} is wired as {value!r}. It must carry an EMPTY fallback: any default "
        "is either an endpoint nobody reads or a committed credential."
    )


def test_the_alertmanager_service_runs_the_fail_closed_entrypoint() -> None:
    """The compose service and the refusal must not drift apart.

    Point the service at the image's own entrypoint and every check in
    ops/alertmanager/entrypoint.sh is bypassed in one line, with no test failing.
    """
    entrypoint = _service("alertmanager").get("entrypoint")
    assert isinstance(entrypoint, list), "the alertmanager entrypoint must be an exec-form list"
    assert "/ops/alertmanager/entrypoint.sh" in entrypoint, (
        f"the alertmanager service runs {entrypoint!r}, bypassing the fail-closed launcher"
    )


def test_the_entrypoint_actually_refuses_a_missing_destination() -> None:
    """Read the launcher, not just its name.

    ``scripts/alert-notification-proof.sh`` phase 1 observes the refusal for
    real (exit 78). This is the cheap seam that keeps the refusal from being
    deleted between proof runs — the proof is not a CI gate, so nothing else
    would notice.
    """
    source = ALERTMANAGER_ENTRYPOINT_PATH.read_text()
    assert NOTIFY_URL_VAR in source
    assert "require_url" in source, "the launcher no longer validates its destination"
    assert re.search(r"exit\s+78", source), (
        "the launcher no longer exits non-zero on a missing destination"
    )
    # An `:-` default anywhere on the assignment line would restore the hole the
    # compose-level check just closed.
    assignment = re.search(rf'NOTIFY_URL="\$\{{{NOTIFY_URL_VAR}:-(.*?)\}}"', source)
    assert assignment, f"could not find where the launcher reads {NOTIFY_URL_VAR}"
    assert assignment.group(1) == "", (
        f"the launcher defaults {NOTIFY_URL_VAR} to {assignment.group(1)!r} instead of refusing"
    )


def test_the_config_reads_the_files_the_entrypoint_writes() -> None:
    """``url_file`` is only fail-closed if the file comes from the launcher.

    A path the launcher does not write would make Alertmanager fail to load —
    loudly, which is acceptable — but a path some OTHER thing could create is the
    quiet version of the same drift. Pin them to each other.
    """
    written = set(re.findall(r'> "\$RUNTIME_DIR/(\S+)"', ALERTMANAGER_ENTRYPOINT_PATH.read_text()))
    runtime_dir = re.search(
        r"^RUNTIME_DIR=(\S+)", ALERTMANAGER_ENTRYPOINT_PATH.read_text(), re.MULTILINE
    )
    assert runtime_dir, "the launcher declares no RUNTIME_DIR"
    expected = {f"{runtime_dir.group(1)}/{name}" for name in written}
    assert expected, "the launcher writes no destination files"

    for receiver in _alertmanager_config()["receivers"]:
        for entry in receiver.get("webhook_configs") or []:
            assert entry["url_file"] in expected, (
                f"receiver {receiver['name']!r} reads {entry['url_file']}, which "
                f"ops/alertmanager/entrypoint.sh never writes (it writes {sorted(expected)})"
            )


def test_the_observability_plane_is_profiled_off_by_default() -> None:
    """Every acceptance script runs a plain `docker compose up`.

    scripts/acceptance.sh, scripts/e2e-acceptance.sh and
    scripts/a11y-audit-stack.sh must bring up exactly the stack they brought up
    before this slice; a monitoring plane that starts with them would change the
    meaning of every one of those runs.
    """
    for service in ("prometheus", "alertmanager"):
        profiles = _service(service).get("profiles")
        assert profiles == [OBSERVABILITY_PROFILE], (
            f"the {service} service declares profiles {profiles!r}; it must be "
            f"[{OBSERVABILITY_PROFILE!r}] so a plain `docker compose up` is unchanged"
        )


# --------------------------------------------------------------------------------
# Provenance: the deployed Prometheus is configured FROM this tree.
# --------------------------------------------------------------------------------


def test_prometheus_sends_its_alerts_to_the_shipped_alertmanager() -> None:
    """Rule evaluation without an `alerting:` block ends at "firing".

    That state is visible only to whoever is already looking at Prometheus's own
    UI — which is what §6.3 measured: eleven correct rules, nobody notified.
    """
    config = yaml.safe_load(PROMETHEUS_CONFIG_PATH.read_text())
    alerting = config.get("alerting")
    assert alerting, (
        "ops/prometheus/prometheus.yml has no `alerting:` block — fired alerts go nowhere"
    )

    targets = {
        target
        for alertmanager in alerting["alertmanagers"]
        for static in alertmanager["static_configs"]
        for target in static["targets"]
    }
    assert targets, "the alerting block names no Alertmanager target"

    services = (_compose().get("services") or {}).keys()
    for target in targets:
        host = target.split(":")[0]
        assert host in services, (
            f"the alerting block points at {target!r}, but docker-compose.yml declares no "
            f"`{host}` service — the alerts would be retried into a name that never resolves"
        )


def test_the_prometheus_service_is_configured_from_this_tree() -> None:
    """THE PROVENANCE GATE, static half.

    §6.3 named two unverified points, and this is the second: "no gate proves the
    deployed Prometheus is actually configured from this file". The live half is
    scripts/alert-notification-proof.sh phase 3, which hashes the staged config
    against the working tree and reads the process's own --config.file flag. This
    half runs on every PR and pins the wiring that makes that possible: the WHOLE
    ops/ tree is mounted (mounting only prometheus/ would load a config whose
    relative `rule_files` resolves to nothing — successfully), and the launcher
    stages it rather than templating it.
    """
    service = _service("prometheus")

    mounts = [str(volume) for volume in (service.get("volumes") or [])]
    assert "./ops:/ops:ro" in mounts, (
        f"the prometheus service mounts {mounts!r}. It must mount the whole ops/ tree read-only: "
        "`rule_files` is the relative path ../alerts/entropia.rules.yml."
    )

    entrypoint = service.get("entrypoint")
    assert isinstance(entrypoint, list) and "/ops/prometheus/entrypoint.sh" in entrypoint, (
        f"the prometheus service runs {entrypoint!r} rather than the tracked launcher"
    )

    source = PROMETHEUS_ENTRYPOINT_PATH.read_text()
    assert re.search(r"^SOURCE_TREE=/ops$", source, re.MULTILINE), (
        "the launcher no longer stages from the mounted /ops tree"
    )
    assert re.search(r'cp -R "\$SOURCE_TREE/\." "\$RUNTIME_TREE/"', source), (
        "the launcher no longer copies the config VERBATIM. Any templating breaks the hash "
        "comparison in scripts/alert-notification-proof.sh, and with it the only evidence "
        "that the running Prometheus is configured from this repository."
    )
    assert re.search(r"ENTROPIA_METRICS_TOKEN", source), (
        "the launcher no longer requires a scrape credential; an anonymous scrape reads a "
        "healthy API as up == 0 and pages continuously"
    )
