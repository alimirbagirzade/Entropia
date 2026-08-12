#!/usr/bin/env bash
# Verify every check name in a ruleset payload against checks GitHub ACTUALLY
# produced, BEFORE the ruleset is created (RC §6.7 / P11-1).
#
# WHY THIS EXISTS. A required status check is matched by NAME, and GitHub does
# not validate that the name corresponds to anything. Require a name no job
# emits and the check is never created, so it sits `Expected — Waiting for
# status to be reported` forever: every pull request becomes unmergeable, and
# the repository cannot tell you why because from its side nothing is wrong.
# The names in this repository are hostile to hand-typing — they carry em
# dashes (`Backend — lint, type, test`), section marks (`RC §6.2`), parentheses
# and a matrix expansion (`CodeQL — python`) — so one transcription slip locks
# the branch. This script removes the transcription step: it diffs the payload
# against the live check-run list and refuses anything it cannot see.
#
# It also reports the reverse direction — checks that ran but are NOT required.
# That half is informational, not a failure: five jobs are nightly/manual by
# design and one is a code-scanning summary from a different app. But a NEWLY
# added job showing up there is the signal that a gate landed without being
# wired into the merge block, which is the exact hole P11-1 exists to close.
#
# Usage:
#   scripts/required-checks-preflight.sh                 # vs. latest main commit
#   scripts/required-checks-preflight.sh <pr-number>     # vs. that PR's head
#
# Needs: gh (authenticated), python3. Read-only — it changes nothing.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD="${RULESET_PAYLOAD:-$REPO_ROOT/.github/rulesets/main-required-status-checks.json}"
PR_NUMBER="${1:-}"

command -v gh >/dev/null || { echo "FATAL: gh CLI not found" >&2; exit 2; }
[ -f "$PAYLOAD" ] || { echo "FATAL: payload not found: $PAYLOAD" >&2; exit 2; }

REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

# Resolve the commit whose checks we compare against. A PR head is the better
# sample: it is what a required check will actually be evaluated on, and it
# includes PR-only checks (the code-scanning summary) that never appear on a
# push to main.
if [ -n "$PR_NUMBER" ]; then
  SHA="$(gh pr view "$PR_NUMBER" --json headRefOid -q .headRefOid)"
  echo "Sampling checks from PR #$PR_NUMBER head $SHA"
else
  SHA="$(gh api "repos/$REPO/commits/main" -q .sha)"
  echo "Sampling checks from main $SHA"
  echo "NOTE: a push-to-main commit does not carry PR-only checks. To include"
  echo "      those, re-run against a recent pull request number."
fi

gh api "repos/$REPO/commits/$SHA/check-runs?per_page=100" \
  --jq '.check_runs[] | {name, conclusion, app: .app.slug}' > /tmp/entropia-checks.$$.jsonl
trap 'rm -f /tmp/entropia-checks.$$.jsonl' EXIT

python3 - "$PAYLOAD" "/tmp/entropia-checks.$$.jsonl" << 'PYEOF'
import json, sys, collections

payload_path, checks_path = sys.argv[1], sys.argv[2]

payload = json.load(open(payload_path))
required = []
for rule in payload.get("rules", []):
    if rule.get("type") == "required_status_checks":
        required = [c["context"] for c in rule["parameters"]["required_status_checks"]]
if not required:
    sys.exit("FATAL: payload declares no required_status_checks rule")

produced = [json.loads(line) for line in open(checks_path) if line.strip()]
names = collections.Counter(c["name"] for c in produced)

missing = [n for n in required if n not in names]
# A name emitted by two different workflows cannot be required unambiguously:
# both must report, and neither file knows about the other.
ambiguous = [n for n in required if names[n] > 1]
unrequired = sorted(n for n in names if n not in set(required))

print(f"\npayload:  {payload_path}")
print(f"required: {len(required)}    produced: {len(produced)}\n")

for n in sorted(set(required)):
    print(f"  OK       {n}")

if unrequired:
    print("\nProduced but NOT required (expected: nightly/manual + other apps):")
    for n in unrequired:
        dup = f"  [emitted by {names[n]} workflows]" if names[n] > 1 else ""
        print(f"  not-req  {n}{dup}")

status = 0
if ambiguous:
    print("\nFATAL — required name emitted by more than one workflow:")
    for n in ambiguous:
        print(f"  {n}  (x{names[n]})")
    status = 1
if missing:
    print("\nFATAL — required but NEVER PRODUCED. Creating this ruleset would")
    print("make every pull request permanently unmergeable:")
    for n in missing:
        print(f"  {n}")
    status = 1

if status == 0:
    print("\nPASS — every required name was produced by this commit.")
sys.exit(status)
PYEOF
