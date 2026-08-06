#!/usr/bin/env bash
# =============================================================================
# Entropia — DR workload driver (ADIM 23).
#
# `scripts/dr-acceptance.sh` proves that a backup RESTORES what the source
# database held. It cannot make the source hold anything: that is the caller's
# job, and until this script existed the caller was `apps/seed.py` alone.
#
# The seed is a fixture writer, not a user. It inserts rows through the
# repositories directly, so it produces:
#
#   * exactly ONE object  — `_seed_e2e_golden_market` calls
#     `infrastructure/s3/datasets.py::put_processed_parquet` once, and none of
#     the three other object writers (`put_source_asset_bytes`,
#     `put_raw_bytes`, `put_baseline_bytes`) is on any seed path at all;
#   * ZERO audit_events and ZERO outbox_events — it never goes through a
#     command, so `_audit_and_outbox` is never reached.
#
# Measured, not assumed (Actions run 31038908690, job `disaster-recovery`):
#   [7] audit_events 0 rows · outbox_events 0 rows · agent_checkpoint 0 rows
#   [8] 1 objects: path, size and md5 identical …
#
# So the DR harness's append-only step compared EMPTY to EMPTY — it said so out
# loud, which is why this gap is being closed rather than discovered — and its
# object step rested on a single parquet key written by a code path no operator
# ever triggers.
#
# This script drives ONE real, authenticated product operation instead:
# `POST /trade-logs/source-assets`. That single call writes, through the shipped
# command (`application/commands/trade_log.py::upload_source_asset`):
#
#   * a source-asset object under a DIFFERENT key prefix than the seed's parquet
#     (`put_source_asset_bytes`), so step [8] compares more than one key shape;
#   * an `audit_events` row AND an `outbox_events` row via `_audit_and_outbox`,
#     so step [7] compares real content instead of EMPTY == EMPTY;
#   * an idempotency record, because the route reads `Idempotency-Key` (O-13).
#
# Deliberately ONE operation. A longer script (import job -> worker -> report
# polling) would add rows of the same three kinds while adding instrument
# lookup, canonical-CSV construction and a poll loop that can flake — more
# machinery, not more evidence. What it would additionally cover is named as an
# open boundary in `docs/BACKUP_DR.md` rather than implied to be covered.
#
#   scripts/dr-workload.sh                       # against http://localhost:8000
#   DR_WORKLOAD_BASE=http://localhost:18200/api/v1 scripts/dr-workload.sh
#
# Exit code: 0 = the workload landed, 1 = it did not (the caller must fail).
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GRN=$'\033[32m'; RST=$'\033[0m'
ok()   { printf '  %sPASS%s  %s\n' "$GRN" "$RST" "$*"; }
bad()  { printf '  %sFAIL%s  %s\n' "$RED" "$RST" "$*" >&2; }
info() { printf '  %s%s%s\n' "$DIM" "$*" "$RST"; }

BASE="${DR_WORKLOAD_BASE:-http://localhost:8000/api/v1}"
USERNAME="${DR_WORKLOAD_USER:-dr_workload_admin}"
PASSWORD="${DR_WORKLOAD_PASSWORD:-DrWorkload!pw123}"
EMAIL="${DR_WORKLOAD_EMAIL:-dr_workload@e2e.entropia.test}"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT INT TERM

printf '\n%s========== DR WORKLOAD  (%s) ==========%s\n' "$BOLD" "$BASE" "$RST"

req() { # req METHOD PATH [curl args...] -> LAST_STATUS / LAST_BODY
  local method="$1" path="$2"; shift 2
  LAST_STATUS="$(curl -s -o "$WORK/body" -w '%{http_code}' --max-time 30 -X "$method" "$@" "$BASE$path" 2>/dev/null)"
  LAST_BODY="$(cat "$WORK/body" 2>/dev/null)"
}
jfield() { printf '%s' "$1" | sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -1; }

# --- [1] an authenticated principal -------------------------------------------
# AUTH_MODE=session (the .env.example default this stack runs on) has no
# credentialless Admin, so the workload has to bootstrap one. Signup is only
# open while no login-capable Admin exists; on a re-run it is already taken, so
# a 4xx here is expected and login carries the flow.
req POST /auth/signup -H 'Content-Type: application/json' \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\",\"email\":\"$EMAIL\"}"
if [ "$LAST_STATUS" = "201" ]; then
  info "[1] bootstrap principal created ($USERNAME)"
else
  info "[1] signup -> $LAST_STATUS (already bootstrapped; logging in instead)"
fi

req POST /auth/login -H 'Content-Type: application/json' \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}"
TOKEN="$(jfield "$LAST_BODY" token)"
if [ -z "$TOKEN" ]; then
  bad "[1] could not authenticate as '$USERNAME' -> $LAST_STATUS $LAST_BODY"
  exit 1
fi
ok "[1] authenticated (token withheld)"

# --- [2] one real upload through the shipped command --------------------------
# Content is unique per run so `upload_source_asset`'s content-addressed dedup
# (TL-15) returns a NEW asset rather than replaying a prior one — a deduplicated
# reply would write no object and no audit row, and the run would pass having
# proved nothing.
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$$"
CSV="$WORK/dr_workload_$STAMP.csv"
{
  echo "trade_id,symbol,side,quantity,price,executed_at"
  echo "dr-$STAMP-1,ES,buy,1,4200.25,2026-01-02T09:30:00Z"
  echo "dr-$STAMP-2,ES,sell,1,4210.75,2026-01-02T15:45:00Z"
} > "$CSV"

req POST /trade-logs/source-assets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: dr-workload-$STAMP" \
  -F "file=@$CSV;type=text/csv"
ASSET_ID="$(jfield "$LAST_BODY" source_asset_id)"
if [ "$LAST_STATUS" != "201" ] || [ -z "$ASSET_ID" ]; then
  bad "[2] source-asset upload -> $LAST_STATUS $LAST_BODY"
  exit 1
fi
case "$LAST_BODY" in
  *'"deduplicated":true'*)
    bad "[2] the upload was DEDUPLICATED — no object and no audit row were written."
    info "[2] the CSV is stamped per run, so this means the stamp collided; re-run."
    exit 1 ;;
esac
ok "[2] source asset $ASSET_ID stored (object + audit_events + outbox_events written)"

printf '\n%sWORKLOAD OK%s — the source stack now holds append-only rows and a second artifact key shape.\n' "$BOLD" "$RST"
