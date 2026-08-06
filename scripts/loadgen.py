#!/usr/bin/env python3
"""Entropia load driver — ONE framework for both the PR smoke and the nightly run.

Why not locust/k6: the mandate is one framework, and the only thing either of those
buys over ``asyncio`` + ``httpx`` here is a web UI nobody watches in CI. ``httpx`` is
already a backend dependency (``backend/pyproject.toml``), so this adds nothing to the
dependency set — the ponytail ladder's answer.

Three modes, deliberately separated by what they can honestly prove:

``--check-catalogue``
    Offline. Every scenario path must exist in ``docs/openapi.json`` with the method
    it claims. This is the PR-cheap half: it costs no stack and it stops the scenario
    list from silently rotting into "we load-test six endpoints that were renamed".

``--profile smoke``
    A short, low-concurrency pass against a live stack. Gate: **errors only**. It
    proves the driver, the auth path and every scenario still answer; it does NOT
    judge latency, because a shared runner's latency is noise and a gate built on
    noise gets disabled within a month.

``--profile full``
    The nightly/manual matrix: cold pass, then warm passes at the configured
    concurrency and repeat count. Writes the baseline JSON. With ``--compare`` it
    fails on a **ratio** against a recorded baseline measured on the same runner
    class — never on an absolute millisecond target, which is what "do not build a
    gate on an absolute noisy number" rules out.

Client-side numbers are latency percentiles, throughput, errors and bytes. Server-side
numbers come from the app's own credentialed ``/metrics`` exposition (golden signals,
queue depth per queue/status, outbox lag, oldest lease age), snapshotted before and
after and reported as a delta. Anything neither side can see — container RSS, host CPU,
object-store I/O — is recorded in ``not_measured`` with the reason, never estimated.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENAPI = REPO_ROOT / "docs" / "openapi.json"
SCHEMA_VERSION = 1

# Statuses that are a legitimate answer under load rather than a defect. 200 and 204
# are the normal shapes; 401/403 are NOT here — a scenario that 401s means the load
# run authenticated as nobody and every latency number below it would be measuring the
# auth rejection path, which is exactly the silent-green failure this list prevents.
OK_STATUSES = frozenset({200, 204})

# The within-run control the ratio gate normalizes by: unauthenticated, no database
# read, no queue. If IT moves between two runs, the machine moved.
CONTROL_SCENARIO = "meta"


@dataclass(frozen=True)
class Scenario:
    """One measured surface. ``group`` maps it to the ADIM 24 scope list."""

    name: str
    method: str
    path: str
    group: str
    note: str = ""


# The scope this run claims to cover. Grouped by the surface list ADIM 24 names, so a
# reader can see at a glance which named surface has no scenario behind it.
SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "meta",
        "GET",
        "/api/v1/meta",
        "control",
        "Unauthenticated, no DB read. The within-run control: if THIS moves, the "
        "runner moved, not the application.",
    ),
    Scenario("mainboard", "GET", "/api/v1/mainboards/default", "interactive_read"),
    Scenario("library", "GET", "/api/v1/library?limit=25", "interactive_read"),
    Scenario(
        "library_shared", "GET", "/api/v1/library-shared-with-me?limit=25", "interactive_read"
    ),
    Scenario("results_history", "GET", "/api/v1/backtest-results?limit=25", "interactive_read"),
    Scenario("strategy_drafts", "GET", "/api/v1/strategy-drafts", "interactive_read"),
    Scenario("market_datasets", "GET", "/api/v1/market-datasets?limit=25", "interactive_read"),
    Scenario("research_datasets", "GET", "/api/v1/research-datasets?limit=25", "interactive_read"),
    Scenario("instruments", "GET", "/api/v1/instruments", "interactive_read"),
    Scenario("capabilities", "GET", "/api/v1/capabilities", "interactive_read"),
    Scenario("agent_tasks", "GET", "/api/v1/agent-tasks", "analysis_lab"),
    Scenario("agent_overview", "GET", "/api/v1/agent-workspace/overview", "analysis_lab"),
    Scenario("hypotheses", "GET", "/api/v1/hypotheses", "analysis_lab"),
    Scenario("lab_messages", "GET", "/api/v1/lab/messages", "analysis_lab"),
    Scenario("audit_events", "GET", "/api/v1/audit-events?limit=25", "audit"),
    Scenario("admin_logs", "GET", "/api/v1/admin/logs?limit=25", "audit"),
    Scenario("trash_entries", "GET", "/api/v1/trash-entries?limit=25", "interactive_read"),
)

# Named in the ADIM 24 scope but NOT driven by this file, with the reason. Copied into
# the baseline JSON so a report can never read as fuller coverage than the run had.
NOT_COVERED: dict[str, str] = {
    "ready_check_admission": (
        "POST /readiness-checks mutates and needs a composition whose items are all "
        "pinned and approved; seeding one per repeat would measure the seed. Its DB "
        "cost is gated deterministically instead — docs/performance/query_budgets.json "
        "-> readiness_check.market_data_leg."
    ),
    "backtest_run_admission": (
        "POST /backtest-runs enqueues real work; a load run would fill the queue with "
        "runs nothing consumes. Admission cost is gated by "
        "tests/integration/test_backtest_query_count.py."
    ),
    "worker_throughput": (
        "Ingest/import/validation/backtest/export/Agent worker time is not observable "
        "from an HTTP client. The run reports the queue-depth and oldest-lease-age "
        "gauges the API exposes; per-actor worker time needs worker-side "
        "instrumentation that does not exist yet."
    ),
    "api_rss_and_cpu": (
        "Container memory/CPU is not exposed by the application. The nightly workflow "
        "captures `docker stats` alongside this JSON rather than having the driver "
        "guess."
    ),
}


# --------------------------------------------------------------------------- results


@dataclass
class Sample:
    latencies_ms: list[float] = field(default_factory=list)
    statuses: dict[int, int] = field(default_factory=dict)
    bytes_received: int = 0
    transport_errors: int = 0

    def record(self, status: int, elapsed_ms: float, size: int) -> None:
        self.latencies_ms.append(elapsed_ms)
        self.statuses[status] = self.statuses.get(status, 0) + 1
        self.bytes_received += size

    @property
    def errors(self) -> int:
        bad = sum(n for s, n in self.statuses.items() if s not in OK_STATUSES)
        return bad + self.transport_errors


def _percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile — no interpolation.

    Interpolated percentiles read prettier and are harder to reason about when a
    sample is small; nearest-rank means every reported number is a request that
    actually happened.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return round(ordered[rank - 1], 3)


def _summarize(sample: Sample, wall_seconds: float) -> dict[str, Any]:
    n = len(sample.latencies_ms)
    return {
        "requests": n,
        "errors": sample.errors,
        "status_counts": {str(k): v for k, v in sorted(sample.statuses.items())},
        "transport_errors": sample.transport_errors,
        "throughput_rps": round(n / wall_seconds, 3) if wall_seconds > 0 else None,
        "bytes_received": sample.bytes_received,
        "latency_ms": {
            "p50": _percentile(sample.latencies_ms, 0.50),
            "p95": _percentile(sample.latencies_ms, 0.95),
            "p99": _percentile(sample.latencies_ms, 0.99),
            "max": round(max(sample.latencies_ms), 3) if n else None,
            "mean": round(statistics.fmean(sample.latencies_ms), 3) if n else None,
        },
    }


# ------------------------------------------------------------------------ scrape


_METRIC_LINE = re.compile(
    r"^(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)(?P<labels>\{[^}]*\})? (?P<value>\S+)$"
)


def _parse_prometheus(text: str) -> dict[str, float]:
    """Flatten an exposition into ``{name{labels}: value}``. Comments are skipped."""
    out: dict[str, float] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _METRIC_LINE.match(line)
        if match is None:
            continue
        try:
            out[f"{match['name']}{match['labels'] or ''}"] = float(match["value"])
        except ValueError:
            continue
    return out


async def _scrape(client: httpx.AsyncClient, base_url: str, token: str | None) -> dict[str, float]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = await client.get(f"{base_url}/api/v1/metrics", headers=headers, timeout=10.0)
    except httpx.HTTPError:
        return {}
    if response.status_code != 200:
        return {}
    return _parse_prometheus(response.text)


# --------------------------------------------------------------------------- auth


async def _authenticate(
    client: httpx.AsyncClient, base_url: str, args: argparse.Namespace
) -> dict[str, str]:
    """Return the headers every measured request carries.

    Dev-auth (``--actor``) and session login are BOTH supported because the two CI
    stacks differ, and a driver that silently fell back to anonymous would report the
    latency of 401 responses as the latency of the page.
    """
    if args.actor:
        return {"X-Actor-Id": args.actor}
    if args.login_username:
        response = await client.post(
            f"{base_url}/api/v1/auth/login",
            json={"username": args.login_username, "password": args.login_password},
            timeout=30.0,
        )
        response.raise_for_status()
        return {"Authorization": f"Bearer {response.json()['token']}"}
    raise SystemExit(
        "loadgen: no credentials. Pass --actor (dev-auth stack) or "
        "--login-username/--login-password (session stack). An anonymous run would "
        "measure the rejection path."
    )


# ---------------------------------------------------------------------------- run


async def _one(
    client: httpx.AsyncClient,
    base_url: str,
    scenario: Scenario,
    headers: dict[str, str],
    sample: Sample,
) -> None:
    started = time.perf_counter()
    try:
        response = await client.request(
            scenario.method, f"{base_url}{scenario.path}", headers=headers, timeout=60.0
        )
    except httpx.HTTPError:
        sample.transport_errors += 1
        return
    sample.record(
        response.status_code, (time.perf_counter() - started) * 1000.0, len(response.content)
    )


async def _phase(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    *,
    concurrency: int,
    repeats: int,
) -> tuple[dict[str, dict[str, Any]], float]:
    """One pass: every scenario ``repeats`` times at ``concurrency`` in flight."""
    samples = {scenario.name: Sample() for scenario in SCENARIOS}
    gate = asyncio.Semaphore(concurrency)

    async def _guarded(scenario: Scenario) -> None:
        async with gate:
            await _one(client, base_url, scenario, headers, samples[scenario.name])

    started = time.perf_counter()
    await asyncio.gather(*(_guarded(scenario) for _ in range(repeats) for scenario in SCENARIOS))
    wall = time.perf_counter() - started
    return {name: _summarize(sample, wall) for name, sample in samples.items()}, wall


async def _sse_probe(base_url: str, headers: dict[str, str], *, seconds: float) -> dict[str, Any]:
    """Hold the SSE stream open and count what the client observes.

    A reconnect here is a real signal: the taxonomy is delivered over one long-lived
    stream, so a stream that drops under load is a user-visible defect even when every
    polled endpoint answers 200.
    """
    url = f"{base_url}/api/v1/events"
    connects = 0
    events = 0
    disconnects = 0
    deadline = time.perf_counter() + seconds
    first_byte_ms: float | None = None

    async def _read(response: httpx.Response, started: float) -> None:
        nonlocal events, first_byte_ms
        async for line in response.aiter_lines():
            if first_byte_ms is None:
                first_byte_ms = (time.perf_counter() - started) * 1000.0
            if line.startswith("data:"):
                events += 1

    async with httpx.AsyncClient(follow_redirects=True) as client:
        while (remaining := deadline - time.perf_counter()) > 0:
            connects += 1
            started = time.perf_counter()
            try:
                async with client.stream(
                    "GET", url, headers={**headers, "Accept": "text/event-stream"}, timeout=30.0
                ) as response:
                    if response.status_code != 200:
                        return {
                            "supported": False,
                            "status": response.status_code,
                            "note": "stream refused; nothing measured",
                        }
                    # The window is a hard bound. Without it the probe blocks inside
                    # aiter_lines until the server's own heartbeat interval elapses —
                    # measured at ~15s on an idle stack — and a 3s probe silently
                    # becomes a 15s one, which is how a "smoke" grows a five-minute tail.
                    try:
                        await asyncio.wait_for(_read(response, started), timeout=remaining)
                    except TimeoutError:
                        break  # the window closed with the stream still healthy
            except httpx.HTTPError:
                disconnects += 1
            if time.perf_counter() < deadline:
                await asyncio.sleep(0.2)
    return {
        "supported": True,
        "window_seconds": seconds,
        "connects": connects,
        # connects beyond the first are reconnects: the stream did not survive.
        "reconnects": max(0, connects - 1),
        "transport_disconnects": disconnects,
        "events_received": events,
        # None means "no line arrived inside the window" — an idle stack emits its
        # first heartbeat later than a short probe runs. It is not a failure, and it
        # is not reported as a zero.
        "time_to_first_line_ms": None if first_byte_ms is None else round(first_byte_ms, 3),
    }


# ------------------------------------------------------------------------- gates


def _error_gate(phases: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for phase, scenarios in phases.items():
        for name, summary in scenarios.items():
            if summary["errors"]:
                failures.append(
                    f"{phase}/{name}: {summary['errors']} error(s) "
                    f"{summary['status_counts']} transport={summary['transport_errors']}"
                )
            if summary["requests"] == 0:
                failures.append(f"{phase}/{name}: no request completed")
    return failures


def _control_p95(phase: dict[str, Any]) -> float | None:
    value = phase.get(CONTROL_SCENARIO, {}).get("latency_ms", {}).get("p95")
    return value if value else None


def _ratio_gate(current: dict[str, Any], baseline: dict[str, Any], max_ratio: float) -> list[str]:
    """Compare each scenario's p95 **relative to the within-run control**.

    A raw p95-vs-baseline ratio was tried first and does not survive contact with a
    shared machine: two back-to-back full runs against an unchanged stack moved the
    control scenario — unauthenticated, no database work — by 4.4x, which failed
    every scenario at a 3x band. That gate would have been switched off inside a week,
    and switching a gate off is worse than not having built it.

    Normalizing by ``meta`` cancels the weather. ``scenario_p95 / control_p95`` is the
    cost of the application's own work expressed in units of "how fast is this box
    today", so what is compared across runs is a property of the code. The raw
    milliseconds stay in the report (they are the operational picture); the RATIO is
    what fails the build.
    """
    failures: list[str] = []
    base_phase = baseline.get("phases", {}).get("warm", {})
    cur_phase = current.get("phases", {}).get("warm", {})
    base_control = _control_p95(base_phase)
    cur_control = _control_p95(cur_phase)
    if base_control is None or cur_control is None:
        return [
            f"ratio gate skipped: the '{CONTROL_SCENARIO}' control has no p95 in "
            "one of the two runs, so nothing can be normalized — treat this run as "
            "unmeasured rather than as a pass"
        ]
    for name, summary in cur_phase.items():
        if name == CONTROL_SCENARIO:
            continue
        recorded = base_phase.get(name, {}).get("latency_ms", {}).get("p95")
        observed = summary.get("latency_ms", {}).get("p95")
        if not recorded or observed is None:
            continue
        base_norm = recorded / base_control
        cur_norm = observed / cur_control
        ratio = cur_norm / base_norm
        if ratio > max_ratio:
            failures.append(
                f"warm/{name}: p95 {observed}ms / control {cur_control}ms = "
                f"{cur_norm:.2f} control-units, baseline {recorded}ms / "
                f"{base_control}ms = {base_norm:.2f} -> {ratio:.2f}x (band {max_ratio}x)"
            )
    return failures


# -------------------------------------------------------------------------- modes


def _check_catalogue() -> int:
    """Assert every scenario is a real published endpoint (offline, PR-cheap)."""
    if not OPENAPI.exists():
        print(f"loadgen: {OPENAPI} not found", file=sys.stderr)
        return 1
    spec = json.loads(OPENAPI.read_text())
    paths = spec.get("paths", {})
    problems: list[str] = []
    for scenario in SCENARIOS:
        bare = scenario.path.split("?", 1)[0]
        entry = paths.get(bare)
        if entry is None:
            problems.append(f"{scenario.name}: {bare} is not in docs/openapi.json")
        elif scenario.method.lower() not in entry:
            problems.append(f"{scenario.name}: {bare} has no {scenario.method}")
    if problems:
        print("loadgen: scenario catalogue is stale:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"loadgen: {len(SCENARIOS)} scenarios all resolve against docs/openapi.json")
    return 0


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    base_url = args.base_url.rstrip("/")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        headers = await _authenticate(client, base_url, args)
        before = await _scrape(client, base_url, args.metrics_token)

        # Cold pass: one sequential lap, nothing warmed. Reported apart from the warm
        # numbers because a first-touch page is a different measurement, not an outlier.
        cold, cold_wall = await _phase(client, base_url, headers, concurrency=1, repeats=1)
        warm, warm_wall = await _phase(
            client, base_url, headers, concurrency=args.concurrency, repeats=args.repeats
        )
        after = await _scrape(client, base_url, args.metrics_token)

    sse = await _sse_probe(base_url, headers, seconds=args.sse_seconds)

    delta = {
        key: round(after[key] - before.get(key, 0.0), 6)
        for key in after
        if key.startswith(("entropia_http_requests_total", "entropia_http_request_duration"))
    }
    gauges = {
        key: value
        for key, value in after.items()
        if key.startswith(
            (
                "entropia_jobs_depth",
                "entropia_outbox_lag",
                "entropia_job_lease_age",
                "entropia_http_requests_in_flight",
            )
        )
    }

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "profile": args.profile,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "runner": os.getenv("RUNNER_NAME") or os.getenv("HOSTNAME") or "local",
            "runner_os": os.getenv("RUNNER_OS", sys.platform),
            "runner_class": args.runner_class,
            "base_url": base_url,
            "git_sha": os.getenv("GITHUB_SHA", ""),
            "concurrency": args.concurrency,
            "repeats": args.repeats,
            "auth": "dev-actor" if args.actor else "session-login",
        },
        "scenarios": [asdict(scenario) for scenario in SCENARIOS],
        "phases": {"cold": cold, "warm": warm},
        "wall_seconds": {"cold": round(cold_wall, 3), "warm": round(warm_wall, 3)},
        "sse": sse,
        "server_metrics": {"delta": delta, "gauges_after": gauges, "scraped": bool(after)},
        "not_measured": NOT_COVERED,
    }

    return report


def _report_and_gate(report: dict[str, Any], args: argparse.Namespace) -> int:
    """Persist, print and judge a finished run.

    Kept out of the async path on purpose: writing and re-reading JSON is blocking
    file I/O, and doing it inside the coroutine that just measured latency would put
    a synchronous stall inside the thing under measurement.
    """
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"loadgen: wrote {args.out}")

    failures = _error_gate(report["phases"])
    if args.compare:
        baseline = json.loads(Path(args.compare).read_text())
        failures.extend(_ratio_gate(report, baseline, args.max_ratio))

    for name, summary in report["phases"]["warm"].items():
        print(
            f"  {name:<20} n={summary['requests']:<4} err={summary['errors']:<3} "
            f"p50={summary['latency_ms']['p50']}ms p95={summary['latency_ms']['p95']}ms "
            f"p99={summary['latency_ms']['p99']}ms"
        )
    if failures:
        print("\nloadgen: FAILED", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("\nloadgen: OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-catalogue",
        action="store_true",
        help="Offline: verify every scenario against docs/openapi.json.",
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--profile",
        choices=("smoke", "full"),
        default="smoke",
        help="A LABEL recorded in the report, not a preset: the load shape comes "
        "from --concurrency/--repeats so a report can never claim a profile "
        "it did not actually run.",
    )
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--sse-seconds", type=float, default=5.0)
    parser.add_argument(
        "--actor",
        default=os.getenv("LOADGEN_ACTOR", ""),
        help="Dev-auth stack: the X-Actor-Id to send.",
    )
    parser.add_argument("--login-username", default=os.getenv("LOADGEN_USERNAME", ""))
    parser.add_argument("--login-password", default=os.getenv("LOADGEN_PASSWORD", ""))
    parser.add_argument("--metrics-token", default=os.getenv("ENTROPIA_METRICS_TOKEN", ""))
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--compare", default="", help="Baseline JSON to ratio-compare warm p95 against."
    )
    parser.add_argument(
        "--max-ratio",
        type=float,
        default=2.0,
        help="Band for the control-normalized p95 ratio. "
        "2.0 = twice the recorded cost in control units.",
    )
    parser.add_argument(
        "--runner-class",
        default=os.getenv("LOADGEN_RUNNER_CLASS", "unknown"),
        help="The fixed environment this baseline belongs to, e.g. "
        "'github-ubuntu-latest-2c'. A baseline is only comparable "
        "within its own class.",
    )
    args = parser.parse_args()

    if args.check_catalogue:
        return _check_catalogue()
    return _report_and_gate(asyncio.run(_run(args)), args)


if __name__ == "__main__":
    raise SystemExit(main())
