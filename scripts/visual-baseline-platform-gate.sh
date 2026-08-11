#!/usr/bin/env bash
# Every committed visual baseline must belong to a platform a job actually
# asserts (RC §6.7 / P11-3).
#
# WHY THIS EXISTS. Playwright suffixes `toHaveScreenshot` baselines with the
# platform that produced them (`…-chromium-linux.png`, `…-chromium-darwin.png`)
# and only ever compares against the suffix matching the RUNNING platform.
# Every `runs-on:` in .github/workflows is ubuntu-latest, so CI can only ever
# read the `-linux` set. A `-darwin` set was committed anyway and sat there for
# twenty days across sixty-seven frontend commits with nothing to check it; by
# the time it was measured, six of its eight baselines no longer matched what
# the app renders on darwin. A baseline nothing asserts does not protect the
# pages it names — it only looks like it does, and the one person who does run
# it (a macOS developer) gets a red gate reporting a regression that is not
# there. That teaches people to ignore the gate, which is worse than having no
# gate at all. The eight `-darwin` files were therefore deleted rather than
# refreshed, and this gate stops the class from coming back silently.
#
# TO ADD A PLATFORM: add a job that RUNS the visual suite on it first, then add
# it to ASSERTED_PLATFORMS below. In that order. GitHub-hosted macOS minutes
# bill at ten times the Linux rate, and the product ships as a Linux container
# (frontend/Dockerfile runtime: nginxinc/nginx-unprivileged) — so a second
# platform needs a reason, not just a baseline file.
#
# Usage: scripts/visual-baseline-platform-gate.sh    (needs git; nothing else)
set -euo pipefail

ASSERTED_PLATFORMS="linux"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT_DIR="frontend/e2e/specs/11-visual-regression.spec.ts-snapshots"

cd "$REPO_ROOT"

# git-tracked only: a macOS developer's locally generated baselines are their
# own business right up until they are committed.
tracked="$(git ls-files -- "$SNAPSHOT_DIR")"

if [ -z "$tracked" ]; then
  echo "FAIL: no baselines tracked under ${SNAPSHOT_DIR}" >&2
  echo "      the visual gate asserts against committed baselines; an empty" >&2
  echo "      directory makes every @visual test fail on a missing snapshot." >&2
  exit 1
fi

allowed_re="-chromium-($(echo "$ASSERTED_PLATFORMS" | tr ' ' '|'))\.png$"

# `-e` is load-bearing: the pattern starts with '-', which grep would otherwise
# parse as a bundle of options. And the exit status is read in three branches
# rather than swallowed with `|| true` — that idiom turns grep's ERROR exit (2)
# into "no offenders found" and hands back a green gate for a gate that never
# ran. That is the exact failure class this file exists to prevent, and it was
# caught here by running the gate against a tree that was supposed to make it
# red (it printed OK instead).
set +e
offenders="$(echo "$tracked" | grep -E -v -e "$allowed_re")"
grep_status=$?
set -e
if [ "$grep_status" -gt 1 ]; then
  echo "FAIL: grep exited ${grep_status} — the gate could not evaluate, so it does not pass." >&2
  exit 1
fi

total=$(echo "$tracked" | wc -l | tr -d ' ')

if [ -n "$offenders" ]; then
  echo "FAIL: baseline(s) committed for a platform no job asserts." >&2
  echo "      asserted platform(s): ${ASSERTED_PLATFORMS}" >&2
  echo "$offenders" | sed 's/^/        /' >&2
  echo >&2
  echo "      Either add a CI job that runs 'npm run visual' on that platform," >&2
  echo "      or delete the files. An unasserted baseline goes stale in silence." >&2
  exit 1
fi

echo "OK: ${total} visual baseline(s) tracked, all for asserted platform(s): ${ASSERTED_PLATFORMS}"
