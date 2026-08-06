"""Worker-liveness heartbeat: age semantics, exposition shape, and alert wiring (ADIM 25).

Two things are being defended here.

The first is that "never recorded" must not render as "alive one instant ago".
``None`` collapsing to ``0.0`` on the wire would be a silent fallback that lies
in exactly the direction an operator cannot afford — a deployment whose async
plane never started would look perfectly healthy.

The second is that the SIMULATED failure states actually cross the thresholds the
shipped alert rules use. Thresholds are read out of ``ops/alerts/entropia.rules.yml``
rather than duplicated, so loosening a rule without re-checking its scenario fails
here instead of quietly widening the blind spot.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from entropia.application.jobs.heartbeat import (
    MAINTENANCE_HEARTBEAT_KEY,
    worker_heartbeat_age_seconds,
)
from entropia.application.queries.job_gauges import JobGauges
from entropia.apps.api.routes.metrics import _render_operational_gauges
from entropia.domain.lifecycle.enums import JobStatus

NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)
RULES_PATH = Path(__file__).resolve().parents[3] / "ops" / "alerts" / "entropia.rules.yml"


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _FakeSession:
    """Just enough AsyncSession to exercise the read path without a database."""

    def __init__(self, stored: str | None) -> None:
        self._stored = stored

    async def execute(self, statement: Any) -> _FakeResult:
        return _FakeResult(self._stored)


def _threshold(alert_name: str) -> float:
    """The numeric bound the shipped rule actually compares against."""
    document = yaml.safe_load(RULES_PATH.read_text())
    for group in document["groups"]:
        for rule in group["rules"]:
            if rule["alert"] == alert_name:
                match = re.search(r">\s*([0-9.]+)\s*$", rule["expr"].strip())
                assert match, f"{alert_name} has no trailing numeric bound: {rule['expr']}"
                return float(match.group(1))
    raise AssertionError(f"{alert_name} is not declared in {RULES_PATH}")


# --------------------------------------------------------------------------- age


@pytest.mark.asyncio
async def test_age_is_seconds_since_the_recorded_stamp() -> None:
    session = _FakeSession((NOW - timedelta(seconds=42)).isoformat())
    assert await worker_heartbeat_age_seconds(session, now=NOW) == pytest.approx(42.0)


@pytest.mark.asyncio
async def test_a_missing_row_is_none_not_zero() -> None:
    """The whole point: absent liveness is not fresh liveness."""
    assert await worker_heartbeat_age_seconds(_FakeSession(None), now=NOW) is None


@pytest.mark.asyncio
async def test_a_corrupt_value_reports_never_seen_rather_than_guessing() -> None:
    session = _FakeSession("not-a-timestamp")
    assert await worker_heartbeat_age_seconds(session, now=NOW) is None


@pytest.mark.asyncio
async def test_a_naive_stamp_is_read_as_utc() -> None:
    session = _FakeSession((NOW - timedelta(seconds=10)).replace(tzinfo=None).isoformat())
    assert await worker_heartbeat_age_seconds(session, now=NOW) == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_clock_skew_clamps_to_zero() -> None:
    """A worker clock running ahead is skew; a negative age is not a thing this means."""
    session = _FakeSession((NOW + timedelta(seconds=30)).isoformat())
    assert await worker_heartbeat_age_seconds(session, now=NOW) == 0.0


def test_the_key_names_the_queue_it_actually_proves() -> None:
    """The heartbeat covers `maintenance` only; the key must not over-claim."""
    assert MAINTENANCE_HEARTBEAT_KEY == "worker.maintenance.last_heartbeat_at"


# ---------------------------------------------------------------------- rendering


def _gauges(heartbeat: float | None) -> JobGauges:
    return JobGauges(
        queue_depth=(("maintenance", JobStatus.RUNNING, 1),),
        outbox_lag_seconds=0.5,
        oldest_lease_age_seconds=2.0,
        worker_heartbeat_age_seconds=heartbeat,
    )


def test_a_recorded_heartbeat_renders_a_sample() -> None:
    body = _render_operational_gauges(_gauges(12.5))
    assert "# TYPE entropia_worker_heartbeat_age_seconds gauge" in body
    assert "entropia_worker_heartbeat_age_seconds 12.500" in body


def test_an_unrecorded_heartbeat_renders_the_type_line_and_no_sample() -> None:
    """`absent(...)` can only alert if the series is genuinely absent."""
    body = _render_operational_gauges(_gauges(None))
    assert "# TYPE entropia_worker_heartbeat_age_seconds gauge" in body

    samples = [
        line
        for line in body.splitlines()
        if line.startswith("entropia_worker_heartbeat_age_seconds")
    ]
    assert samples == [], f"an unrecorded heartbeat emitted a sample: {samples}"


def test_the_new_family_does_not_disturb_the_families_that_preceded_it() -> None:
    """Existing gauge names, labels and order are contract; the new one appends."""
    body = _render_operational_gauges(_gauges(1.0))
    assert body.startswith(
        "# TYPE entropia_jobs_depth gauge\n"
        'entropia_jobs_depth{queue="maintenance",status="running"} 1\n'
        "# TYPE entropia_outbox_lag_seconds gauge\n"
        "entropia_outbox_lag_seconds 0.500\n"
        "# TYPE entropia_job_lease_age_seconds gauge\n"
        "entropia_job_lease_age_seconds 2.000\n"
    )


# --------------------------------------------------------------------- simulation


@pytest.mark.asyncio
async def test_a_worker_silent_for_six_scheduler_ticks_crosses_the_paging_threshold() -> None:
    """Simulated stale heartbeat: the scenario must actually trip the shipped rule."""
    bound = _threshold("EntropiaWorkerHeartbeatStale")
    stale_at = NOW - timedelta(seconds=bound + 30)

    age = await worker_heartbeat_age_seconds(_FakeSession(stale_at.isoformat()), now=NOW)

    assert age is not None and age > bound
    assert f"entropia_worker_heartbeat_age_seconds {age:.3f}" in _render_operational_gauges(
        _gauges(age)
    )


def test_a_healthy_heartbeat_stays_clear_of_the_paging_threshold() -> None:
    """A heartbeat one tick old must not trip the alert — otherwise it pages forever."""
    assert _threshold("EntropiaWorkerHeartbeatStale") > 30.0


@pytest.mark.parametrize(
    ("alert", "simulated"),
    [
        ("EntropiaOutboxLagGrowing", 301.0),
        ("EntropiaOutboxLagSevere", 1801.0),
    ],
)
def test_simulated_outbox_lag_crosses_its_rule(alert: str, simulated: float) -> None:
    bound = _threshold(alert)
    assert simulated > bound

    body = _render_operational_gauges(
        JobGauges(
            queue_depth=(),
            outbox_lag_seconds=simulated,
            oldest_lease_age_seconds=0.0,
            worker_heartbeat_age_seconds=1.0,
        )
    )
    assert f"entropia_outbox_lag_seconds {simulated:.3f}" in body


def test_simulated_stale_job_lease_crosses_its_rule() -> None:
    """A lease aging past 2x JOB_STALE_AFTER_SECONDS proves the reclaim sweep is not running."""
    bound = _threshold("EntropiaJobLeaseStuck")
    simulated = bound + 60.0

    body = _render_operational_gauges(
        JobGauges(
            queue_depth=(("backtest", JobStatus.RUNNING, 1),),
            outbox_lag_seconds=0.0,
            oldest_lease_age_seconds=simulated,
            worker_heartbeat_age_seconds=1.0,
        )
    )
    assert f"entropia_job_lease_age_seconds {simulated:.3f}" in body
