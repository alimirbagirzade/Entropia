#!/usr/bin/env bash
# Behaviour proof for the two BLOCKING agent hooks (ADIM 57).
#
# WHY THIS EXISTS. `plugins/entropia-maintenance/hooks/guard-git.sh` and
# `guard-generated.sh` are the repo's only automatic defence on two axes no CI
# job covers: no gate reads `docs/`, and no gate can see an Edit before it lands.
# They shipped inside a plugin — and the plugin is NOT installed in a remote
# container, because installing one needs an interactive approval prompt that a
# headless session never gets (measured 2026-08-13:
# `/root/.claude/plugins/installed_plugins.json` = `{"version":2,"plugins":{}}`).
# So the guard written to stop the #590/#604 docs regressions had never once run
# where those regressions actually happen. ADIM 57 registers both scripts
# directly in `.claude/settings.json`, independent of installation.
#
# `scripts/agent-config-gate.mjs` proves the WIRING (the path exists and is
# executable). It cannot prove the BEHAVIOUR: an edit to a `case` arm leaves
# every path valid while the gate silently stops blocking. This script is that
# second half — and it is written as a NEGATIVE control first. A guard that
# blocks everything passes any positive-only test while making itself useless,
# so every gate here is also fired with input it MUST let through.
#
# Network-free, DB-free, ~1s: it builds a throwaway git fixture in a temp dir and
# feeds each guard the same stdin JSON Claude Code sends on PreToolUse. The real
# repository's index is never touched.
#
# Usage: scripts/hook-guard-proof.sh    (needs git + python3; nothing else)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GIT_GUARD="$REPO_ROOT/plugins/entropia-maintenance/hooks/guard-git.sh"
GEN_GUARD="$REPO_ROOT/plugins/entropia-maintenance/hooks/guard-generated.sh"

for guard in "$GIT_GUARD" "$GEN_GUARD"; do
  [ -x "$guard" ] || { echo "FAIL: guard missing or not executable — $guard" >&2; exit 1; }
done

# The guards must also still be REGISTERED outside the plugin, or their behaviour
# is irrelevant in the environment this whole slice is about.
python3 - "$REPO_ROOT" <<'PY' || exit 1
import json, pathlib, sys

settings = json.loads((pathlib.Path(sys.argv[1]) / ".claude/settings.json").read_text())
commands = json.dumps(settings.get("hooks", {}))
missing = [s for s in ("guard-git.sh", "guard-generated.sh") if s not in commands]
if missing:
    print(
        "FAIL: .claude/settings.json no longer registers " + ", ".join(missing) + ".\n"
        "      Without that registration these guards only run where the plugin is\n"
        "      installed — which is never, in a remote container (ADIM 57).",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY

FIXTURE="$(mktemp -d)"
cleanup() { rm -rf "$FIXTURE"; }
trap cleanup EXIT

git init -q "$FIXTURE"
mkdir -p "$FIXTURE/docs"
printf '## ADIM 1 - kayit\n\ngovde\n\n## ADIM 2 - kayit\n\ngovde\n' > "$FIXTURE/docs/PROJECT_HISTORY.md"
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.email=proof@entropia -c user.name=proof commit -qm base

failures=0
passes=0

# probe <expected-exit> <guard> <payload> <description> [env assignments...]
probe() {
  local want="$1" guard="$2" payload="$3" name="$4"
  shift 4
  local out code
  out="$(printf '%s' "$payload" | env "$@" CLAUDE_PROJECT_DIR="$FIXTURE" bash "$guard" 2>&1)"
  code=$?
  if [ "$code" = "$want" ]; then
    passes=$((passes + 1))
    printf '  ok    exit=%s  %s\n' "$code" "$name"
  else
    failures=$((failures + 1))
    printf '  FAIL  exit=%s want=%s  %s\n' "$code" "$want" "$name" >&2
    printf '%s\n' "$out" | sed 's/^/        /' >&2
  fi
}

stage_history() { printf '%s' "$1" > "$FIXTURE/docs/PROJECT_HISTORY.md"; git -C "$FIXTURE" add -A; }

COMMIT='{"tool_input":{"command":"git commit -m wip"}}'
KEEP=$'## ADIM 1 - kayit\n\ngovde\n\n## ADIM 2 - kayit\n\ngovde\n'
DROP=$'## ADIM 1 - kayit\n\ngovde\n'

echo "guard-git.sh — gate 1: a commit that deletes a docs record"
stage_history "$DROP"
probe 2 "$GIT_GUARD" "$COMMIT" "staged '## ' record removal blocks" IGNORE=1
probe 0 "$GIT_GUARD" '{"tool_input":{"command":"git commit --dry-run"}}' \
      "--dry-run passes with the same removal staged" IGNORE=1
probe 0 "$GIT_GUARD" "$COMMIT" "ENTROPIA_HOOKS=off passes" ENTROPIA_HOOKS=off
stage_history "${KEEP}"$'\n## ADIM 3 - yeni\n'
probe 0 "$GIT_GUARD" "$COMMIT" "an ADDITIVE docs commit passes" IGNORE=1
probe 0 "$GIT_GUARD" 'not json at all' "unparseable stdin passes (fail-open by design)" IGNORE=1

echo "guard-git.sh — gate 2: self-merge"
probe 2 "$GIT_GUARD" '{"tool_input":{"command":"gh pr merge 123 --squash"}}' "gh pr merge blocks" IGNORE=1
probe 0 "$GIT_GUARD" '{"tool_input":{"command":"gh pr view 123"}}' "gh pr view passes" IGNORE=1
probe 0 "$GIT_GUARD" '{"tool_input":{"command":"gh pr checks 123 --watch"}}' "gh pr checks passes" IGNORE=1

echo "guard-git.sh — gate 3: force push to a shared branch"
# NOTE: the match is on the whole command STRING, so `feat/main-menu` is blocked
# too. That over-block is deliberate — the opposite error is letting one through.
probe 2 "$GIT_GUARD" '{"tool_input":{"command":"git push --force origin main"}}' \
      "force push to main blocks" IGNORE=1
probe 2 "$GIT_GUARD" '{"tool_input":{"command":"git push --force-with-lease origin main"}}' \
      "--force-with-lease to main blocks too" IGNORE=1
probe 0 "$GIT_GUARD" '{"tool_input":{"command":"git push --force origin feat/stage-9-x"}}' \
      "force push to a feature branch passes" IGNORE=1
probe 0 "$GIT_GUARD" '{"tool_input":{"command":"git push -u origin feat/stage-9-x"}}' \
      "ordinary push passes" IGNORE=1

echo "guard-generated.sh — generated files are not hand-edited"
gen_payload() { printf '{"tool_input":{"file_path":"%s/%s"}}' "$REPO_ROOT" "$1"; }
probe 2 "$GEN_GUARD" "$(gen_payload docs/openapi.json)" "docs/openapi.json blocks" IGNORE=1
probe 2 "$GEN_GUARD" "$(gen_payload docs/generated/repository_facts.md)" \
      "docs/generated/repository_facts.md blocks" IGNORE=1
probe 2 "$GEN_GUARD" "$(gen_payload docs/generated/anything.md)" "any docs/generated/* blocks" IGNORE=1
probe 0 "$GEN_GUARD" "$(gen_payload docs/PROJECT_HISTORY.md)" "a hand-written doc passes" IGNORE=1
probe 0 "$GEN_GUARD" "$(gen_payload backend/src/entropia/anything.py)" "backend source passes" IGNORE=1
probe 0 "$GEN_GUARD" "$(gen_payload docs/openapi.json)" "ENTROPIA_HOOKS=off passes" ENTROPIA_HOOKS=off
probe 0 "$GEN_GUARD" '{"tool_input":{}}' "a payload with no file_path passes" IGNORE=1

echo
if [ "$failures" -ne 0 ]; then
  echo "hook guard proof: ${failures} expectation(s) missed out of $((passes + failures))" >&2
  exit 1
fi
echo "hook guard proof: ${passes}/${passes} expectations met (6 blocks, $((passes - 6)) pass-throughs) OK"
