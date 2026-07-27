"""Finding O-23 — the scheduler's redelivery sweep reports failures.

A broker send that fails is neither fatal nor a data loss (the row stays durably
QUEUED and the next tick re-sweeps it), but swallowing it silently made a broker
rejecting EVERY send indistinguishable from "nothing needed redelivery" in the
``scheduler.maintenance`` summary. These tests pin the evidence AND the unchanged
recovery behaviour: the loop still continues, the count still excludes the failure.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.apps.scheduler import __main__ as scheduler


class _RecordingLog:
    def __init__(self) -> None:
        self.warnings: list[tuple[str, dict[str, Any]]] = []

    def warning(self, event: str, **fields: Any) -> None:
        self.warnings.append((event, fields))


@pytest.fixture
def log(monkeypatch) -> _RecordingLog:
    recorder = _RecordingLog()
    monkeypatch.setattr(scheduler, "log", recorder)
    return recorder


def _send_stub(monkeypatch, failing_job_ids: set[str]) -> list[str]:
    """Record every attempted job id; raise for the ids named as failing."""
    attempted: list[str] = []

    def _send(actor: Any, job_id: str) -> None:
        attempted.append(job_id)
        if job_id in failing_job_ids:
            raise RuntimeError("broker unreachable")

    monkeypatch.setattr(scheduler, "send_job", _send)
    return attempted


def test_failed_send_is_logged_with_job_and_queue(monkeypatch, log) -> None:
    _send_stub(monkeypatch, {"job_bad"})

    assert scheduler._redeliver([("backtest", "job_bad")]) == 0

    assert len(log.warnings) == 1
    event, fields = log.warnings[0]
    assert event == "scheduler.redeliver_failed"
    assert fields["job_id"] == "job_bad"
    assert fields["queue"] == "backtest"
    assert "broker unreachable" in fields["error"]


def test_failed_send_does_not_stop_the_sweep(monkeypatch, log) -> None:
    """Behaviour is unchanged: the loop continues past a failure and the returned
    count reflects only the sends that actually reached the broker."""
    attempted = _send_stub(monkeypatch, {"job_bad"})

    redelivered = scheduler._redeliver(
        [("backtest", "job_ok1"), ("agent", "job_bad"), ("maintenance", "job_ok2")]
    )

    assert redelivered == 2
    assert attempted == ["job_ok1", "job_bad", "job_ok2"]
    assert [fields["job_id"] for _event, fields in log.warnings] == ["job_bad"]


def test_every_failure_is_reported_not_just_the_first(monkeypatch, log) -> None:
    _send_stub(monkeypatch, {"job_a", "job_b"})

    assert scheduler._redeliver([("backtest", "job_a"), ("backtest", "job_b")]) == 0
    assert [fields["job_id"] for _event, fields in log.warnings] == ["job_a", "job_b"]


def test_unmapped_queue_is_skipped_without_a_warning(monkeypatch, log) -> None:
    """``data`` hosts several actor types and is deliberately NOT auto-redelivered
    (module docstring) — skipping it is designed behaviour, not a failure."""
    attempted = _send_stub(monkeypatch, set())

    assert "data" not in scheduler.ACTOR_BY_QUEUE
    assert scheduler._redeliver([("data", "job_data")]) == 0
    assert attempted == []
    assert log.warnings == []


def test_all_sends_succeeding_logs_nothing(monkeypatch, log) -> None:
    attempted = _send_stub(monkeypatch, set())

    assert scheduler._redeliver([("backtest", "job_1"), ("agent-high", "job_2")]) == 2
    assert attempted == ["job_1", "job_2"]
    assert log.warnings == []


def test_empty_candidate_list_is_a_no_op(monkeypatch, log) -> None:
    attempted = _send_stub(monkeypatch, set())

    assert scheduler._redeliver([]) == 0
    assert attempted == []
    assert log.warnings == []
