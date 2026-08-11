#!/usr/bin/env bash
# =============================================================================
# Entropia — bounded external calls (ADIM 36, RC §6.7 P6-ek / P6-6).
#
# WHY THIS FILE EXISTS. A guard that can hang is not a guard. Two harness
# scripts asked an external tool a yes/no question with no bound on the answer:
#
#   * scripts/e2e-acceptance.sh — "is the Docker daemon reachable?" Against a
#     WEDGED daemon the probe itself blocks, so the FATAL/exit-2 branch written
#     directly underneath it can never be taken. MEASURED before the fix: the
#     script was still running after 25s and would have run forever.
#   * scripts/backup-verify.sh  — "drop the scratch database." A `dropdb` that
#     never returns hangs the whole verification; a `dropdb` that FAILS was
#     swallowed by `|| true`, the next `createdb` failed on the leftover
#     database, and the script exited 1 — the exact code its own header
#     documents as "the backup does not restore". MEASURED before the fix.
#
# The rule this file exists to enforce: turn a hang into a CLEAN FAILURE with a
# distinct exit code. Never into a silent pass. `bounded_run` cannot return 0
# for a command it had to kill.
#
#   bounded_run SECONDS CMD [ARG...]
#     -> CMD's own exit status if CMD finished inside SECONDS
#     -> BOUNDED_TIMEOUT_RC (124, GNU timeout's convention) if it did not
#
# Portability: no GNU `timeout` (absent on macOS, where this repo is developed),
# no `wait -n`, no fractional sleeps, no arrays in the hot path — this must run
# under the bash 3.2 that ships with macOS as well as under CI's bash 5.
#
# Implementation note: the deadline is a background watchdog and the result is
# taken from a real `wait` on the command, NOT from polling `kill -0`. Polling
# races with the shell reaping the child. The watchdog's stdout is redirected to
# /dev/null on purpose: inside `x="$(bounded_run ...)"` it would otherwise keep
# the command-substitution pipe open and stall the caller until the deadline
# even when the command answered immediately.
# =============================================================================

# GNU timeout's exit code for "killed at the deadline". Reused so a caller that
# does have `timeout` in some other context reads the same number.
BOUNDED_TIMEOUT_RC=124

# How long a TERMed command may take to die before it is KILLed.
BOUNDED_SIGKILL_GRACE_SECONDS="${BOUNDED_SIGKILL_GRACE_SECONDS:-2}"

bounded_run() {
  local limit="$1"; shift
  local flag pid wd rc=0 had_monitor=0

  # Non-empty == "the watchdog fired". A file rather than a variable because the
  # watchdog is a subshell and cannot write to this shell's variables.
  flag="$(mktemp)"

  # Job control ON for the launch, so the command becomes the leader of its OWN
  # process group and the watchdog can signal the WHOLE tree. Killing only the
  # direct child is not enough and was MEASURED to be not enough: `docker
  # compose ...` runs the compose plugin as a child of `docker`, and a surviving
  # grandchild keeps the `x="$(bounded_run ...)"` pipe open, so the CALLER stays
  # blocked until the grandchild exits — the very hang this file removes.
  case "$-" in *m*) had_monitor=1 ;; esac
  set -m
  "$@" &
  pid=$!

  # The watchdog is launched under job control too, so cancelling it below takes
  # its `sleep` with it. Otherwise a fast command would leave an orphan sleeping
  # for the whole bound — up to half an hour for the pg_restore limit.
  (
    sleep "$limit"
    kill -0 "$pid" 2>/dev/null || exit 0
    printf 'timeout' > "$flag"
    kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
    sleep "$BOUNDED_SIGKILL_GRACE_SECONDS"
    kill -KILL "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null
  ) >/dev/null 2>&1 &
  wd=$!
  [ "$had_monitor" -eq 1 ] || set +m

  wait "$pid" 2>/dev/null || rc=$?
  kill -TERM "-$wd" 2>/dev/null || kill -TERM "$wd" 2>/dev/null || true
  wait "$wd" 2>/dev/null || true

  if [ -s "$flag" ]; then
    rm -f "$flag"
    return "$BOUNDED_TIMEOUT_RC"
  fi
  rm -f "$flag"
  return "$rc"
}
