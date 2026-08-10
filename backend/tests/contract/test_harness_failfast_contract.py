"""A harness guard that can HANG is not a guard (ADIM 35, RC §6.7 P6-ek / P6-6).

Two acceptance scripts asked an external tool a yes/no question with no bound on
the answer, and both defects survived because nobody notices a hang by hand —
you notice it as "the run is taking a while", then you Ctrl-C and move on.

Both were REPRODUCED before the fix, on the development host:

  * ``scripts/e2e-acceptance.sh`` — with a non-answering ``docker`` on PATH the
    script was still running after 25s. The ``FATAL … exit 2`` branch sits
    directly underneath the probe and could never be taken, because the probe
    itself never returned.
  * ``scripts/backup-verify.sh`` — a wedged ``dropdb`` hung the script outright;
    a ``dropdb`` that merely FAILED was swallowed by ``|| true``, the following
    ``createdb`` failed on the leftover database, and the script exited **1** —
    the code its own header documents as "the backup does not restore". A sound
    backup, reported as a broken one.

So this file drives the fault, not the shape of the source. Each test puts a
FAKE binary on PATH — one that hangs, or fails, or answers instantly — and
asserts the exit code and that the script came back inside a bound. A regression
makes the test FAIL (an explicit ``pytest.fail``), never makes CI hang.

The exit codes are the contract, and the three states are kept apart on purpose:

  e2e-acceptance.sh   0 = all steps passed · 1 = a step failed · 2 = the harness
                      could not run (Compose absent, daemon unreachable, daemon
                      HUNG)
  backup-verify.sh    0 = restores · 1 = does NOT restore (about the BACKUP) ·
                      3 = could not be verified (about the ENVIRONMENT)

The direction that matters most is the one a backup check must never drift in:
``test_backup_verify_still_fails_a_genuinely_incoherent_dump`` and
``test_backup_verify_still_passes_a_sound_backup`` are here so "stop reporting
sound backups as broken" can never be satisfied by reporting broken backups as
sound.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_SCRIPT = REPO_ROOT / "scripts" / "e2e-acceptance.sh"
BACKUP_VERIFY_SCRIPT = REPO_ROOT / "scripts" / "backup-verify.sh"
BOUNDED_LIB = REPO_ROOT / "scripts" / "lib" / "bounded.sh"

#: What the scripts are told to use, so the real 20s/60s code path runs in
#: seconds. The DEFAULTS are justified against measurements in the scripts.
PROBE_TIMEOUT_SECONDS = 3
#: SIGTERM -> SIGKILL grace inside bounded_run, plus room for process startup on
#: a loaded runner. A script that answers inside this proves the bound ended it.
BOUNDED_BUDGET_SECONDS = PROBE_TIMEOUT_SECONDS * 3 + 15
#: A hard stop, so a regression is a red test rather than a wedged CI job.
SUBPROCESS_TIMEOUT_SECONDS = 90

EXIT_OK = 0
EXIT_STEP_FAILED = 1
EXIT_HARNESS_CANNOT_RUN = 2
EXIT_NOT_RESTORABLE = 1
EXIT_UNVERIFIED = 3

#: bounded_run's timeout status, GNU timeout's convention.
BOUNDED_TIMEOUT_RC = 124

WEDGED = "sleep 3600\n"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="POSIX shell harness needs bash"
)


def _fake_tool(directory: Path, name: str, body: str) -> None:
    """Put an executable stub named ``name`` in ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    tool = directory / name
    tool.write_text("#!/bin/sh\n" + body)
    tool.chmod(0o755)


def _run(
    script: Path,
    args: list[str],
    fake_bin: Path,
    env_extra: dict[str, str],
) -> tuple[subprocess.CompletedProcess[str], float]:
    """Run ``script`` with ``fake_bin`` shadowing the real tools on PATH."""
    env = dict(os.environ)
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env.update(env_extra)
    started = time.monotonic()
    try:
        proc = subprocess.run(
            ["bash", str(script), *args],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            env=env,
            cwd=REPO_ROOT,
        )
    except subprocess.TimeoutExpired as exc:
        # `raise`, not `pytest.fail`: both end the test, but only this one makes
        # the exit obvious to a reader AND to static analysis. CodeQL does not
        # model `pytest.fail` as NoReturn, so it read `proc` below as possibly
        # unbound — 24 alerts from this one line and its twin in `_bash`.
        raise AssertionError(
            f"{script.name} was STILL RUNNING after {SUBPROCESS_TIMEOUT_SECONDS}s — "
            "the harness hung instead of failing fast. This is the ADIM 35 regression."
        ) from exc
    return proc, time.monotonic() - started


def _assert_bounded(elapsed: float, script_name: str) -> None:
    assert elapsed < BOUNDED_BUDGET_SECONDS, (
        f"{script_name} returned, but only after {elapsed:.1f}s "
        f"(budget {BOUNDED_BUDGET_SECONDS}s) — the bound is not what ended it."
    )


def _bash(snippet: str) -> tuple[subprocess.CompletedProcess[str], float]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            ["bash", "-c", f". {BOUNDED_LIB}\n{snippet}"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            cwd=REPO_ROOT,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            "bounded_run itself hung — it is the thing that must not hang."
        ) from exc
    return proc, time.monotonic() - started


@pytest.fixture
def backup_dir(tmp_path: Path) -> Path:
    """A backup directory shaped like scripts/backup.sh writes one."""
    src = tmp_path / "20260810T000000Z"
    src.mkdir()
    (src / "postgres.dump").write_bytes(b"")
    (src / "MANIFEST.json").write_text(
        '{"alembic_head": "0043_i08_registry_strategy_fks", "public_table_count": 120}\n'
    )
    return src


def _sound_psql() -> str:
    """A psql stub that answers both catalog reads of a coherent restore."""
    return (
        'case "$*" in\n'
        "  *alembic_version*) echo '0043_i08_registry_strategy_fks' ;;\n"
        "  *information_schema.tables*) echo '120' ;;\n"
        "esac\n"
        "exit 0\n"
    )


def _pg_toolchain(directory: Path, **overrides: str) -> Path:
    """The four postgres client tools, all trivially succeeding unless overridden."""
    bodies = {"dropdb": "exit 0\n", "createdb": "exit 0\n", "pg_restore": "exit 0\n"}
    bodies["psql"] = _sound_psql()
    bodies.update(overrides)
    for name, body in bodies.items():
        _fake_tool(directory, name, body)
    return directory


def _backup_env() -> dict[str, str]:
    return {
        "BACKUP_VERIFY_PG_TIMEOUT_SECONDS": str(PROBE_TIMEOUT_SECONDS),
        "BACKUP_VERIFY_RESTORE_TIMEOUT_SECONDS": str(PROBE_TIMEOUT_SECONDS),
        "VERIFY_DB": "entropia_failfast_probe",
    }


# ---------------------------------------------------------------------------
# The mechanism itself: scripts/lib/bounded.sh
# ---------------------------------------------------------------------------


def test_bounded_run_returns_the_commands_own_status() -> None:
    """A command that finishes in time is reported by ITS status, untouched."""
    proc, elapsed = _bash('bounded_run 5 /bin/sh -c "exit 7"; echo "rc=$?"')
    assert "rc=7" in proc.stdout
    _assert_bounded(elapsed, "bounded_run")


def test_bounded_run_never_reports_success_for_a_command_it_killed() -> None:
    """The whole point: a timeout is a distinct non-zero status, never 0."""
    proc, elapsed = _bash('bounded_run 2 /bin/sleep 300; echo "rc=$?"')
    assert f"rc={BOUNDED_TIMEOUT_RC}" in proc.stdout
    _assert_bounded(elapsed, "bounded_run")


def test_bounded_run_kills_the_whole_process_tree() -> None:
    """Killing only the direct child leaves the caller blocked.

    ``docker compose ...`` runs the compose plugin as a CHILD of ``docker``. A
    surviving grandchild keeps the command-substitution pipe open, so the caller
    stays blocked for the full sleep even though the deadline already fired —
    MEASURED at 60s against a 2s bound before the process group was killed.
    """
    proc, elapsed = _bash(
        'out="$(bounded_run 2 /bin/sh -c "sleep 300; echo never")"; echo "rc=$? out=[$out]"'
    )
    assert f"rc={BOUNDED_TIMEOUT_RC} out=[]" in proc.stdout
    _assert_bounded(elapsed, "bounded_run")


# ---------------------------------------------------------------------------
# P6-ek — scripts/e2e-acceptance.sh preflight
# ---------------------------------------------------------------------------


def test_e2e_preflight_exits_2_when_the_docker_cli_is_wedged(tmp_path: Path) -> None:
    """The reproduced fault: a docker that never answers anything."""
    fake_bin = tmp_path / "bin"
    _fake_tool(fake_bin, "docker", WEDGED)

    proc, elapsed = _run(
        E2E_SCRIPT,
        ["session"],
        fake_bin,
        {"E2E_DOCKER_PROBE_TIMEOUT_SECONDS": str(PROBE_TIMEOUT_SECONDS)},
    )

    assert proc.returncode == EXIT_HARNESS_CANNOT_RUN, proc.stderr
    assert "HUNG" in proc.stderr
    _assert_bounded(elapsed, E2E_SCRIPT.name)


def test_e2e_preflight_exits_2_when_only_the_daemon_query_is_wedged(tmp_path: Path) -> None:
    """The second probe must be bounded too, not just the first one.

    A wedged daemon with a healthy CLI answers ``docker compose version`` (client
    side, no daemon round trip) and then hangs on ``docker version``.
    """
    fake_bin = tmp_path / "bin"
    _fake_tool(
        fake_bin,
        "docker",
        '[ "$1" = "compose" ] && { echo "Docker Compose version v5.1.2"; exit 0; }\n' + WEDGED,
    )

    proc, elapsed = _run(
        E2E_SCRIPT,
        ["session"],
        fake_bin,
        {"E2E_DOCKER_PROBE_TIMEOUT_SECONDS": str(PROBE_TIMEOUT_SECONDS)},
    )

    assert proc.returncode == EXIT_HARNESS_CANNOT_RUN, proc.stderr
    assert "HUNG" in proc.stderr
    assert "docker version" in proc.stderr
    _assert_bounded(elapsed, E2E_SCRIPT.name)


def test_e2e_preflight_still_names_an_absent_daemon_as_absent(tmp_path: Path) -> None:
    """Control: the bound must not swallow the diagnosis it replaced.

    A daemon that REFUSES instantly is a different fact from one that hangs, and
    the operator is told which one they have.
    """
    fake_bin = tmp_path / "bin"
    _fake_tool(fake_bin, "docker", 'echo "Cannot connect to the Docker daemon" >&2\nexit 1\n')

    proc, elapsed = _run(
        E2E_SCRIPT,
        ["session"],
        fake_bin,
        {"E2E_DOCKER_PROBE_TIMEOUT_SECONDS": str(PROBE_TIMEOUT_SECONDS)},
    )

    assert proc.returncode == EXIT_HARNESS_CANNOT_RUN, proc.stderr
    assert "not reachable" in proc.stderr
    assert "HUNG" not in proc.stderr
    _assert_bounded(elapsed, E2E_SCRIPT.name)


# ---------------------------------------------------------------------------
# P6-6 — scripts/backup-verify.sh
# ---------------------------------------------------------------------------


def test_backup_verify_reports_unverified_when_dropdb_is_wedged(
    tmp_path: Path, backup_dir: Path
) -> None:
    """The named fault: ``dropdb`` hangs, so nothing was learned about the dump."""
    fake_bin = _pg_toolchain(tmp_path / "bin", dropdb=WEDGED)

    proc, elapsed = _run(BACKUP_VERIFY_SCRIPT, [str(backup_dir)], fake_bin, _backup_env())

    assert proc.returncode == EXIT_UNVERIFIED, proc.stdout + proc.stderr
    assert proc.returncode != EXIT_NOT_RESTORABLE
    assert "UNVERIFIED" in proc.stderr
    _assert_bounded(elapsed, BACKUP_VERIFY_SCRIPT.name)


def test_backup_verify_does_not_blame_the_backup_for_a_leftover_scratch_db(
    tmp_path: Path, backup_dir: Path
) -> None:
    """The reproduced FALSE NEGATIVE, verbatim.

    ``dropdb`` fails, the leftover database makes ``createdb`` fail, and the old
    script exited 1 — "the backup does not restore" — about a backup it had not
    read a single byte of.
    """
    fake_bin = _pg_toolchain(
        tmp_path / "bin",
        dropdb="exit 1\n",
        createdb='echo "database already exists" >&2\nexit 1\n',
    )

    proc, elapsed = _run(BACKUP_VERIFY_SCRIPT, [str(backup_dir)], fake_bin, _backup_env())

    assert proc.returncode == EXIT_UNVERIFIED, proc.stdout + proc.stderr
    assert proc.returncode != EXIT_NOT_RESTORABLE
    assert "says nothing about the backup" in proc.stderr
    _assert_bounded(elapsed, BACKUP_VERIFY_SCRIPT.name)


def test_backup_verify_reports_unverified_when_pg_restore_is_wedged(
    tmp_path: Path, backup_dir: Path
) -> None:
    """Same fault class, the other long call: a partial restore proves nothing."""
    fake_bin = _pg_toolchain(tmp_path / "bin", pg_restore=WEDGED)

    proc, elapsed = _run(BACKUP_VERIFY_SCRIPT, [str(backup_dir)], fake_bin, _backup_env())

    assert proc.returncode == EXIT_UNVERIFIED, proc.stdout + proc.stderr
    _assert_bounded(elapsed, BACKUP_VERIFY_SCRIPT.name)


def test_backup_verify_still_fails_a_genuinely_incoherent_dump(
    tmp_path: Path, backup_dir: Path
) -> None:
    """Anti-drift control #1: the plumbing works, the restored catalog is empty.

    This MUST stay 1. If "stop reporting sound backups as broken" ever turned
    into "report broken backups as sound", this is the test that goes red.
    """
    fake_bin = _pg_toolchain(tmp_path / "bin", psql="exit 0\n")

    proc, elapsed = _run(BACKUP_VERIFY_SCRIPT, [str(backup_dir)], fake_bin, _backup_env())

    assert proc.returncode == EXIT_NOT_RESTORABLE, proc.stdout + proc.stderr
    assert "alembic_version missing" in proc.stderr
    _assert_bounded(elapsed, BACKUP_VERIFY_SCRIPT.name)


def test_backup_verify_still_passes_a_sound_backup(tmp_path: Path, backup_dir: Path) -> None:
    """Anti-drift control #2: a coherent restore is still exit 0.

    The manifest head and table count are the ones the fixture writes, so this
    also proves the manifest comparison still runs.
    """
    fake_bin = _pg_toolchain(tmp_path / "bin")

    proc, elapsed = _run(BACKUP_VERIFY_SCRIPT, [str(backup_dir)], fake_bin, _backup_env())

    assert proc.returncode == EXIT_OK, proc.stdout + proc.stderr
    assert "VERIFY OK" in proc.stdout
    _assert_bounded(elapsed, BACKUP_VERIFY_SCRIPT.name)


def test_the_three_e2e_exit_codes_stay_distinct() -> None:
    """A restatement of the contract, so a future edit has to notice it."""
    assert len({EXIT_OK, EXIT_STEP_FAILED, EXIT_HARNESS_CANNOT_RUN}) == 3
    assert len({EXIT_OK, EXIT_NOT_RESTORABLE, EXIT_UNVERIFIED}) == 3
