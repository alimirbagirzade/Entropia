#!/usr/bin/env bash
# Install Chromium + its system libraries for the Playwright jobs in e2e.yml.
#
# WHY THIS SCRIPT EXISTS — measured, not guessed (2026-08-19, PR #780's run).
# `npx playwright install --with-deps chromium` hung inside apt and took two
# jobs down with it. The log is unambiguous:
#
#   04:52:02  Switching to root user to install dependencies...
#   04:52:32  Ign: azure.archive.ubuntu.com noble InRelease      <- mirror down
#   04:52:39  Hit: archive.ubuntu.com  (fell back)
#   04:52:40  Get: noble-{updates,backports,security} InRelease
#             ... 28m22s of TOTAL SILENCE ...
#   05:21:02  ##[error]The operation was canceled.
#
# F-23 died at exactly 30.3 min and A11Y at 40.3 min — their `timeout-minutes`.
# GitHub reports a timeout-killed job as `cancelled`, which is why this read as
# "cancelled, probably a superseding push" for two waves. It was neither.
#
# apt has NO overall deadline of its own: a socket that opens but never delivers
# is waited on indefinitely, so one sick mirror burns the whole job budget.
#
# WHAT IS NOT THE FIX: dropping `--with-deps`. That flag is deliberate and the
# reason is recorded in e2e.yml's acceptance-flows step — without the system
# libraries the download succeeds and chromium then fails to LAUNCH, which the
# harness records as a SKIP rather than a failure. Keep the flag; make it
# survive a flaky mirror.
set -uo pipefail

# 1. Give every apt fetch a deadline and a bounded retry count. Without this
#    the stall above is unbounded.
if command -v sudo >/dev/null 2>&1; then
  sudo tee /etc/apt/apt.conf.d/99-entropia-ci-timeouts >/dev/null <<'APTEOF'
Acquire::http::Timeout "20";
Acquire::https::Timeout "20";
Acquire::ftp::Timeout "20";
Acquire::Retries "3";
APTEOF
fi

# 2. Bound each attempt with coreutils `timeout` rather than relying on the
#    step budget. A healthy install is ~1-2 min on a GitHub runner, so 5 min is
#    2.5-5x headroom; a hang now dies in 5 min instead of eating 30.
#    `timeout` exits 124 when it fires — that is the hang, reported as a hang.
ATTEMPT_SECONDS="${PLAYWRIGHT_INSTALL_TIMEOUT_SECONDS:-300}"

# 3. One retry, because the failure this guards against is a TRANSIENT mirror
#    outage. A second failure is not the flake and is allowed to go red — this
#    script must never convert a real breakage into a green.
for attempt in 1 2; do
  # Capture the exit status DIRECTLY. Do not wrap this in `if ...; then`:
  # after an `if` block closes, `$?` is the status of the `if`, not of the
  # command it tested, so `status` would read 0 on every failure and this
  # script would turn a real breakage into a green. That defect was written,
  # caught by driving the script against stubbed failures, and fixed here.
  timeout "${ATTEMPT_SECONDS}" npx playwright install --with-deps chromium
  status=$?
  if [ "${status}" -eq 0 ]; then
    exit 0
  fi
  if [ "${attempt}" -eq 2 ]; then
    if [ "${status}" -eq 124 ]; then
      echo "::error::playwright install hung twice (>${ATTEMPT_SECONDS}s each). Not the known mirror flake — investigate before re-running." >&2
    else
      echo "::error::playwright install failed twice (exit ${status}). Not the known mirror flake — investigate before re-running." >&2
    fi
    exit "${status}"
  fi
  if [ "${status}" -eq 124 ]; then
    echo "::warning::playwright install hung (>${ATTEMPT_SECONDS}s), retrying once — see scripts/ci-install-playwright-chromium.sh" >&2
  else
    echo "::warning::playwright install failed (exit ${status}), retrying once" >&2
  fi
  sudo apt-get clean >/dev/null 2>&1 || true
done
