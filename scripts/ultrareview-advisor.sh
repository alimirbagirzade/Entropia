#!/usr/bin/env bash
# Decide whether a change is worth a /code-review ultra run — and say why.
#
# /code-review ultra is user-triggered and billed, and it is a DIFF tool: with no
# changed files it has nothing to read. Running it on every branch wastes money;
# never running it wastes the one review pass that catches what CI cannot. This
# script picks the middle: it scores a diff against the failure modes that this
# repo has actually shipped, and prints a verdict.
#
# The axes are not generic "code smells". Each one is a rule that ruff/mypy/pytest
# CANNOT gate, because the code is well-typed and passing while being wrong:
#
#   occ          — dual-token reconcile (shared/concurrency.py). A route that
#                  copies the rule instead of calling reconcile_occ_tokens looks
#                  fine and silently drops the conflict-409.
#   idempotency  — run_idempotent fingerprints. Hashing state the command ITSELF
#                  mutates (head pointer, row_version) type-checks and then 409s
#                  forever on retry.
#   deletion     — TRASH_OBJECT_LOCATIONS. A soft-delete path that forgets
#                  add_trash_entry removes the row from the active projection and
#                  never reaches Admin Trash: no entry for restore/purge to use.
#   envelope     — ErrorBody shape. A route returning bare dict keeps the drift
#                  guard green while hiding the contract from the schema.
#   upload       — assert_supported_source_file. A new upload surface that skips
#                  the shared gate is fail-OPEN, and nothing else notices.
#   auth         — role gates on routes. The auth remediation wave (#346-#364)
#                  exists because these were wrong once already.
#   migration    — alembic revisions: up/down/up and model<->column parity.
#   jobs         — dramatiq actors: at-least-once delivery, resumable steppers.
#   money        — Decimal quantize sites. The half-cent decision is adjudicated
#                  and re-quantizing instead of copying is a silent drift.
#
# Usage:
#   scripts/ultrareview-advisor.sh          # current branch vs main
#   scripts/ultrareview-advisor.sh 649      # a specific PR
#
# Exit codes: 0 = RUN recommended, 1 = SKIP, 2 = MAYBE (one medium axis only).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BASE_BRANCH="${ULTRAREVIEW_BASE:-main}"
PR_NUMBER="${1:-}"

# --- collect the changed-file list -------------------------------------------
if [[ -n "$PR_NUMBER" ]]; then
  if ! FILES="$(gh pr diff "$PR_NUMBER" --name-only 2>/dev/null)"; then
    echo "ultrareview-advisor: PR #${PR_NUMBER} okunamadi (gh auth / numara?)." >&2
    exit 1
  fi
  TARGET_LABEL="PR #${PR_NUMBER}"
  SUGGESTED_CMD="/code-review ultra ${PR_NUMBER}"
else
  FILES="$(git diff --name-only "${BASE_BRANCH}...HEAD" 2>/dev/null || true)"
  TARGET_LABEL="dal $(git rev-parse --abbrev-ref HEAD) vs ${BASE_BRANCH}"
  SUGGESTED_CMD="/code-review ultra"
fi

if [[ -z "${FILES//[[:space:]]/}" ]]; then
  echo "SKIP — ${TARGET_LABEL}: degisen dosya yok, ultrareview'un okuyacagi bir sey olmaz."
  exit 1
fi

FILE_COUNT="$(printf '%s\n' "$FILES" | grep -c . || true)"

# --- axis matching ------------------------------------------------------------
# Each axis: <weight>|<label>|<extended-regex over the changed-path list>.
# HIGH alone justifies a run; two MED do the same.
AXES=(
"HIGH|occ (dual-token reconcile)|entropia/shared/concurrency\.py"
"HIGH|idempotency (run_idempotent fingerprint)|entropia/application/idempotency\.py"
"HIGH|deletion / trash lifecycle|entropia/domain/trash/|application/commands/deletion\.py|application/jobs/purge\.py|application/queries/trash\.py"
"HIGH|upload fail-closed gate|domain/importing/source_file\.py"
"HIGH|alembic migration|backend/alembic/versions/"
"HIGH|auth / role gate|auth|/routes/.*(admin|role|session)"
"MED|error envelope (ErrorBody)|entropia/shared/(responses|errors)\.py"
"MED|mutating commands|entropia/application/commands/"
"MED|worker / dramatiq jobs|entropia/application/jobs/|entropia/apps/worker/"
"MED|http routes|entropia/apps/api/"
"MED|money / rounding|allocation|capital|sleeve"
# Gate + proof harnesses are code with fail-closed semantics, and this repo has
# already paid for a gate that passed while proving nothing. A gate that fails
# OPEN is invisible to every other check, including itself.
"MED|fail-closed gate / proof harness|scripts/.*-(gate|proof|acceptance)\.(sh|mjs|py)$|ops/.*\.(sh|py)$"
)

# --- noise floor FIRST --------------------------------------------------------
# Axes must score CODE, not prose. Matching the raw file list let a docs artifact
# named p5b_three_auth_modes.txt raise a HIGH "auth / role gate" on a test-only
# PR — a false HIGH is the exact failure this advisor exists to prevent, since it
# spends the user's money on a review with nothing to review.
CODE_FILES="$(printf '%s\n' "$FILES" \
  | grep -Ev '^(docs/|ops/alerts/.*\.md$|\.github/)' \
  | grep -Ev '(^|/)(tests?|__tests__)/' \
  | grep -Ev '\.(md|txt|lock)$' || true)"

if [[ -z "${CODE_FILES//[[:space:]]/}" ]]; then
  echo "SKIP — ${TARGET_LABEL}: ${FILE_COUNT} dosya, hepsi docs/test/CI. Ultrareview bunlarda deger uretmez."
  exit 1
fi

MATCHED_HIGH=()
MATCHED_MED=()

for axis in "${AXES[@]}"; do
  weight="${axis%%|*}"
  rest="${axis#*|}"
  label="${rest%%|*}"
  pattern="${rest#*|}"
  if printf '%s\n' "$CODE_FILES" | grep -Eq "$pattern"; then
    if [[ "$weight" == "HIGH" ]]; then
      MATCHED_HIGH+=("$label")
    else
      MATCHED_MED+=("$label")
    fi
  fi
done

# A brand-new create_* is the FK insert-order proof obligation from CLAUDE.md.
if [[ -n "$PR_NUMBER" ]]; then
  ADDED="$(gh pr diff "$PR_NUMBER" 2>/dev/null || true)"
else
  ADDED="$(git diff "${BASE_BRANCH}...HEAD" 2>/dev/null || true)"
fi
if printf '%s' "$ADDED" | grep -Eq '^\+(async )?def create_'; then
  MATCHED_MED+=("yeni create_* (FK insert-order kaniti)")
fi

# --- verdict ------------------------------------------------------------------
echo "ultrareview-advisor — ${TARGET_LABEL} (${FILE_COUNT} dosya)"
for m in "${MATCHED_HIGH[@]:-}"; do [[ -n "$m" ]] && echo "  [HIGH] ${m}"; done
for m in "${MATCHED_MED[@]:-}"; do [[ -n "$m" ]] && echo "  [MED ] ${m}"; done

HIGH_N="${#MATCHED_HIGH[@]}"
MED_N="${#MATCHED_MED[@]}"

if (( HIGH_N > 0 )) || (( MED_N >= 2 )); then
  echo
  echo "RUN — CI kapisinin yakalayamayacagi ekseni var. Kos:"
  echo "  ${SUGGESTED_CMD}"
  echo "Not: her CRITICAL/HIGH bulguyu duzeltmeden ONCE ampirik dogrula (CLAUDE.md)."
  exit 0
elif (( MED_N == 1 )); then
  echo
  echo "MAYBE — tek orta eksen. Diff kucukse elle oku; genisse: ${SUGGESTED_CMD}"
  exit 2
else
  echo
  echo "SKIP — riskli eksen yok."
  exit 1
fi
