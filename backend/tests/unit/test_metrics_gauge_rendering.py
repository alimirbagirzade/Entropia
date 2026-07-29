"""The ``/metrics`` gauge exposition is byte-identical to the pre-I-05 body.

I-05 moved the gauge SQL out of ``apps/api/routes/metrics.py`` and into
``application/queries/job_gauges.py``; the route kept only the Prometheus text
rendering. A scraper's dashboards and recording rules are keyed on the exact
bytes, so this locks the wire format against a VERBATIM copy of the old route
body rather than against a hand-written expectation that could drift with it.

Scope, honestly: this covers the formatting half only. The SQL half (grouping,
``coalesce(started_at, claimed_at)``, the RUNNING filter) is exercised against a
real database by ``tests/contract/test_hardening_contract.py`` and
``tests/contract/test_metrics_scrape_gate.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from entropia.application.queries.job_gauges import JobGauges
from entropia.apps.api.routes.metrics import _render_operational_gauges
from entropia.domain.lifecycle.enums import JobStatus

NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def _legacy_gauge_text(rows, lag, oldest, now):
    """Verbatim transcription of the pre-I-05 ``_operational_gauges`` body."""
    lines: list[str] = []
    lines.append("# TYPE entropia_jobs_depth gauge")
    for queue, status, count in rows:
        lines.append(f'entropia_jobs_depth{{queue="{queue}",status="{status!s}"}} {count}')

    lines.append("# TYPE entropia_outbox_lag_seconds gauge")
    lines.append(f"entropia_outbox_lag_seconds {0.0 if lag is None else lag:.3f}")

    age = 0.0 if oldest is None else (now - oldest).total_seconds()
    lines.append("# TYPE entropia_job_lease_age_seconds gauge")
    lines.append(f"entropia_job_lease_age_seconds {max(0.0, age):.3f}")
    return "\n".join(lines) + "\n"


CASES = [
    pytest.param((), None, None, id="idle-cluster"),
    pytest.param(
        (("backtest", JobStatus.RUNNING, 3), ("default", JobStatus.QUEUED, 11)),
        0.0,
        NOW - timedelta(seconds=90.5),
        id="busy-cluster",
    ),
    pytest.param(
        (("ingest", JobStatus.FAILED_RETRYABLE, 1),),
        12.3456,
        NOW - timedelta(milliseconds=1),
        id="lag-rounds-to-three-decimals",
    ),
    pytest.param(
        (("default", JobStatus.QUEUED, 0),),
        None,
        NOW + timedelta(seconds=5),
        id="clock-skew-clamps-to-zero",
    ),
]


@pytest.mark.parametrize(("rows", "lag", "oldest"), CASES)
def test_rendering_matches_the_pre_i05_body(rows, lag, oldest) -> None:
    age = 0.0 if oldest is None else (NOW - oldest).total_seconds()
    gauges = JobGauges(
        queue_depth=rows,
        outbox_lag_seconds=lag,
        oldest_lease_age_seconds=max(0.0, age),
    )

    assert _render_operational_gauges(gauges) == _legacy_gauge_text(rows, lag, oldest, NOW)


def test_metric_names_and_label_order_are_pinned() -> None:
    """The three metric names and the ``queue`` -> ``status`` label order are contract."""
    gauges = JobGauges(
        queue_depth=(("backtest", JobStatus.RUNNING, 2),),
        outbox_lag_seconds=1.5,
        oldest_lease_age_seconds=60.0,
    )

    assert _render_operational_gauges(gauges) == (
        "# TYPE entropia_jobs_depth gauge\n"
        'entropia_jobs_depth{queue="backtest",status="running"} 2\n'
        "# TYPE entropia_outbox_lag_seconds gauge\n"
        "entropia_outbox_lag_seconds 1.500\n"
        "# TYPE entropia_job_lease_age_seconds gauge\n"
        "entropia_job_lease_age_seconds 60.000\n"
    )
