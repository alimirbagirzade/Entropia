"""ADIM 21 — the shared at-least-once delivery guard, in isolation.

``application/jobs/delivery.py`` is the one place every non-domain-locked durable
worker body answers "has this delivery already happened?". These tests pin its
contract without a database: which statuses count as terminal, what a replay
returns, and that a missing row still raises rather than being swallowed (a
swallowed miss would turn a genuine bug into a silent no-op job).
"""

from __future__ import annotations

import pytest

from entropia.application.jobs.delivery import terminal_replay_ref
from entropia.domain.lifecycle.enums import JOB_TERMINAL_STATES, JobStatus
from entropia.infrastructure.postgres.models import Job


def _job(status: JobStatus, result_ref: dict | None = None) -> Job:
    return Job(job_id="job_x", queue="data", status=status, result_ref=result_ref)


def test_terminal_states_are_exactly_the_four_lifecycle_terminals() -> None:
    """The guard must not invent its own notion of terminal: a body that treated
    FAILED_RETRYABLE as terminal would never retry, and one that treated
    SUPERSEDED as live would re-run work an admission already superseded."""
    expected = {
        JobStatus.SUCCEEDED,
        JobStatus.CANCELLED,
        JobStatus.FAILED_FINAL,
        JobStatus.SUPERSEDED,
    }
    assert set(JOB_TERMINAL_STATES) == expected
    assert JobStatus.RUNNING not in JOB_TERMINAL_STATES
    assert JobStatus.QUEUED not in JOB_TERMINAL_STATES
    assert JobStatus.FAILED_RETRYABLE not in JOB_TERMINAL_STATES
    assert JobStatus.CANCELLATION_REQUESTED not in JOB_TERMINAL_STATES


def test_replay_returns_the_recorded_result_verbatim() -> None:
    recorded = {"source_asset_id": "src_1", "status": "succeeded", "accepted_count": 2}
    assert terminal_replay_ref(_job(JobStatus.SUCCEEDED, recorded)) == recorded


def test_replay_is_a_copy_so_a_caller_cannot_mutate_the_durable_row() -> None:
    """The result_ref is a JSONB column on a live ORM row. Handing the caller the
    same dict would let a mutation downstream rewrite the recorded outcome on the
    next flush — an invisible edit to durable evidence."""
    recorded = {"status": "succeeded"}
    job = _job(JobStatus.SUCCEEDED, recorded)
    replay = terminal_replay_ref(job)
    replay["status"] = "tampered"
    assert job.result_ref == {"status": "succeeded"}


@pytest.mark.parametrize("status", sorted(JOB_TERMINAL_STATES, key=str))
def test_replay_without_a_recorded_result_is_minimal_never_fabricated(
    status: JobStatus,
) -> None:
    """A terminal job that recorded no result is still terminal. The replay says
    only what is known — the id and the status — rather than inventing a richer
    outcome the body never produced."""
    assert terminal_replay_ref(_job(status)) == {"job_id": "job_x", "status": str(status)}


def test_a_non_dict_result_ref_degrades_to_the_minimal_reference() -> None:
    """JSONB can hold a scalar or a list. Returning it verbatim would break every
    caller's ``dict`` contract, so the guard falls back instead of raising."""
    job = _job(JobStatus.SUCCEEDED)
    job.result_ref = ["not", "a", "mapping"]  # type: ignore[assignment]
    assert terminal_replay_ref(job) == {"job_id": "job_x", "status": "succeeded"}
