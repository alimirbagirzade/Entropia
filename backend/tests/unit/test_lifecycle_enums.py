from entropia.domain.lifecycle.enums import (
    JOB_TERMINAL_STATES,
    DeletionState,
    JobStatus,
    Role,
)


def test_roles_are_exactly_admin_supervisor_user() -> None:
    # Agent is NOT an assignable human role (structurally prevented).
    assert {r.value for r in Role} == {"admin", "supervisor", "user"}
    assert "agent" not in {r.value for r in Role}


def test_lifecycle_values_are_lowercase_snake_case() -> None:
    for enum in (DeletionState, JobStatus, Role):
        for member in enum:
            assert member.value == member.value.lower()
            assert " " not in member.value


def test_job_terminal_states() -> None:
    assert JobStatus.SUCCEEDED in JOB_TERMINAL_STATES
    assert JobStatus.RUNNING not in JOB_TERMINAL_STATES
