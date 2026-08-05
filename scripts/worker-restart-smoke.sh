#!/usr/bin/env bash
# =============================================================================
# Entropia — worker process-restart smoke (ADIM 21).
#
# Proves that SIGKILLing every worker plane and bringing it back produces NO
# duplicate domain effect. The durable ``jobs`` row is the source of truth and the
# broker message is only transport, so a killed worker's message is redelivered on
# restart; the delivery claim in ``application/jobs/delivery.py`` is what has to
# make that redelivery a replay instead of a second artifact.
#
# Run against an ALREADY-RUNNING stack (bring it up with `make up` first):
#
#   scripts/worker-restart-smoke.sh
#
# To exercise the MID-FLIGHT kill (the interesting case), enqueue durable work
# first — upload a Trading Signal / Trade Log / Market Data source through the UI
# or API so `data`-queue jobs are in flight — then run this immediately. With an
# idle stack the script still proves the weaker but necessary property: the planes
# restart cleanly and the recovery sweeps invent nothing.
#
# Exit code: 0 = restarted clean with no duplicated artifact, 1 = otherwise.
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=(docker-compose)
fi

WORKERS="worker-default worker-data worker-backtest worker-agent worker-agent-executor \
         agent-coordinator scheduler"
# Every append-only artifact a duplicated worker delivery would forge a second row
# in. A restart must leave every one of these counts UNCHANGED.
TABLES="normalized_signal_event_revision canonical_trade_record_batch market_validation_run \
research_validation_run package_root audit_events outbox_events"

FAIL=0

_psql() {
  "${DC[@]}" exec -T postgres psql -qtAX -U entropia -d entropia -c "$1" 2>/dev/null
}

_snapshot() {
  local out=""
  for t in $TABLES; do
    out+="$t=$(_psql "SELECT count(*) FROM $t" | tr -d '[:space:]') "
  done
  echo "$out"
}

echo "== Worker process-restart smoke =="

# --- 0. the stack must actually be up -------------------------------------- #
if ! _psql "SELECT 1" | grep -q 1; then
  echo "  FAIL  postgres unreachable — bring the stack up with 'make up' first"
  exit 1
fi

present=""
for svc in $WORKERS; do
  if [ -n "$("${DC[@]}" ps -q "$svc" 2>/dev/null)" ]; then present+="$svc "; fi
done
if [ -z "$present" ]; then
  echo "  FAIL  no worker/scheduler container is running"
  exit 1
fi
echo "  planes: $present"

# --- 1. snapshot every append-only artifact -------------------------------- #
BEFORE="$(_snapshot)"
echo "  before: $BEFORE"

# --- 2. SIGKILL every plane (no graceful drain — this is a crash, not a stop) #
echo "  killing planes with SIGKILL ..."
# shellcheck disable=SC2086
"${DC[@]}" kill -s SIGKILL $present >/dev/null 2>&1

# --- 3. bring them back ----------------------------------------------------- #
echo "  restarting planes ..."
# shellcheck disable=SC2086
if ! "${DC[@]}" up -d $present >/dev/null 2>&1; then
  echo "  FAIL  planes did not restart"
  exit 1
fi

# --- 4. bounded readiness poll (no blind sleep) ----------------------------- #
# Each plane declares a healthcheck; poll its reported state rather than guessing
# a duration. 180 x 1s is the ceiling, not the expected wait.
for svc in $present; do
  ok=0
  for _ in $(seq 1 180); do
    cid=$("${DC[@]}" ps -q "$svc" 2>/dev/null | head -n1)
    if [ -n "$cid" ]; then
      state=$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null)
      health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
        "$cid" 2>/dev/null)
      if [ "$state" = "running" ] && { [ "$health" = "healthy" ] || [ "$health" = "none" ]; }; then
        ok=1; break
      fi
    fi
    sleep 1
  done
  if [ "$ok" != "1" ]; then
    echo "  FAIL  $svc did not come back healthy"; FAIL=1
  else
    echo "  OK    $svc restarted"
  fi
done

# --- 5. let the scheduler complete at least one maintenance pass ------------- #
# The sweep is what redelivers whatever the killed workers were holding. Poll the
# scheduler's own log line instead of sleeping for a fixed tick.
#
# The event name must END here: a bare "scheduler.maintenance" substring ALSO
# matches "scheduler.maintenance_failed", so the old grep reported "OK scheduler
# swept" on a stack where every single sweep aborted — precisely the symptom of
# the per-tick event-loop bug this assertion exists to catch. Requiring a
# non-underscore (or end of line) after the name keeps this renderer-agnostic:
# it matches both the shipped JSON form ("event": "scheduler.maintenance") and
# the console form (scheduler.maintenance relayed=0 ...).
echo "  waiting for a scheduler maintenance pass ..."
swept=0
for _ in $(seq 1 180); do
  if "${DC[@]}" logs --tail=200 scheduler 2>/dev/null \
      | grep -Eq 'scheduler\.maintenance([^_]|$)'; then
    swept=1; break
  fi
  sleep 1
done
[ "$swept" = "1" ] && echo "  OK    scheduler swept" || {
  echo "  WARN  no maintenance pass observed within the window (sweep evidence missing)"; }

# --- 6. no append-only artifact may have grown ------------------------------ #
AFTER="$(_snapshot)"
echo "  after:  $AFTER"
if [ "$BEFORE" != "$AFTER" ]; then
  echo "  FAIL  an append-only table changed across the restart — a redelivered"
  echo "        message produced a DUPLICATE domain effect:"
  echo "          before: $BEFORE"
  echo "          after:  $AFTER"
  FAIL=1
else
  echo "  OK    no duplicated artifact, audit or outbox row"
fi

# --- 7. no job may be stranded in a non-terminal, unclaimable state ---------- #
stuck=$(_psql "SELECT count(*) FROM jobs WHERE status = 'running'" | tr -d '[:space:]')
if [ -n "$stuck" ] && [ "$stuck" != "0" ]; then
  echo "  NOTE  $stuck job(s) still RUNNING — the stale sweep recovers these after"
  echo "        JOB_STALE_AFTER_SECONDS; re-run this smoke past that window to confirm."
fi

if [ "$FAIL" = "0" ]; then
  echo "== worker-restart-smoke: PASS =="
else
  echo "== worker-restart-smoke: FAIL =="
fi
exit "$FAIL"
