#!/usr/bin/env bash
# =============================================================================
# Entropia — REAL Docker E2E acceptance harness (audit §9.4 / §9.5 / §9.6, W7).
#
# Runs the three mandated acceptance flows, each in a FULLY ISOLATED Compose
# project with ISOLATED named volumes and NON-COLLIDING host ports, so it can
# run alongside the user's normal `make up` stack and NEVER touches its data:
#
#   scripts/e2e-acceptance.sh session     # §9.4 clean session-mode bootstrap
#   scripts/e2e-acceptance.sh legacy      # §9.5 legacy credentialless upgrade
#   scripts/e2e-acceptance.sh dev-auth    # §9.6 dev-mode X-Actor-Id impersonation
#   scripts/e2e-acceptance.sh flows       # the FIVE acceptance flows (a)-(e)
#   scripts/e2e-acceptance.sh all         # (default) all four, in sequence
#
# `flows` closes the coverage gap the V18 RC readiness report names in §6.2:
# until it existed this script proved AUTH/identity bootstrap and nothing about
# Strategy->Run, Library validation, ESP, Agent/Trading-Signal tools or Trash.
# Its body lives in scripts/lib/acceptance-flows.sh and reuses everything here —
# the isolation contract, the hermetic env file, `dc`, `req` and the PASS/FAIL
# accounting. Set E2E_KEEP_UP=1 to leave that stack up for inspection.
#
# Isolation contract (safety-critical):
#   * Compose project name is ALWAYS `entropia-e2e-<flow>` — a hard guard
#     refuses to `down -v` anything whose name is not that prefix, so the
#     user's `entropia` project can never be destroyed by this script.
#   * Each backend container reads a hermetic `.env.e2e.<flow>` (git-ignored)
#     via ENTROPIA_ENV_FILE — the real `.env` is never read or written.
#   * A strong ENTROPIA_SERVICE_TOKEN is generated per run and NEVER printed.
#   * An EXIT/INT/TERM trap tears the isolated project down (with its volumes)
#     even on failure or Ctrl-C.
#
# Backend-observable steps are asserted directly here against the live stack.
# Purely browser-level steps (DevActorControl visibility, single redirect, no
# Authorization header) are asserted at the frontend layer (audit §9.3:
# frontend/src/test/* and frontend/e2e/specs/01-auth.spec.ts) — the backend
# CONTRACT those UI behaviors depend on is asserted here and cross-referenced.
#
# Exit code: 0 = every asserted step passed for every requested flow, 1 = a
# step failed (details on the FAIL lines), the stack never became healthy, or
# more steps were SKIPPED than E2E_MAX_SKIPS allows (unset = no ceiling; CI
# pins it — see the skip-ceiling block at the bottom of this file),
# 2 = the harness could not run at all — Compose missing, the daemon
# unreachable, or (ADIM 36) the daemon HUNG. Those states are distinct on
# purpose: a hang is never reported as a step failure and never as a pass.
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

# ---- bounded external calls --------------------------------------------------
# ADIM 36 / RC §6.7 P6-ek. The preflight below is a GUARD, and a guard that can
# hang is not a guard: against a wedged daemon the probe itself blocked, so the
# FATAL branch written directly underneath it could never be taken. MEASURED
# before the fix — with a non-answering `docker` on PATH this script was still
# running after 25s and would have run forever.
. "$REPO_ROOT/scripts/lib/bounded.sh"

# Bound for docker probes that are INSTANTANEOUS on a healthy daemon. MEASURED
# on the development host: `docker version` 1.44s (client -> daemon round trip),
# `docker compose version` 0.16s (client only), `docker inspect` well under 1s.
# 20s is ~14x the slowest of those and still a bound, so a wedged daemon gets
# reported instead of waited on. Overridable so the regression test can drive
# this exact code path in seconds.
DOCKER_PROBE_TIMEOUT_SECONDS="${E2E_DOCKER_PROBE_TIMEOUT_SECONDS:-20}"
# Teardown removes ONE small isolated project with its volumes — seconds in
# practice. 180s absorbs a slow volume reaper without letting the EXIT trap
# block a CI runner forever.
TEARDOWN_TIMEOUT_SECONDS="${E2E_TEARDOWN_TIMEOUT_SECONDS:-180}"

# ---- Compose binary (v2 plugin preferred, v1 standalone fallback) -----------
bounded_run "$DOCKER_PROBE_TIMEOUT_SECONDS" docker compose version >/dev/null 2>&1
PROBE_RC=$?
if [ "$PROBE_RC" -eq 0 ]; then
  COMPOSE_BIN=(docker compose)
elif [ "$PROBE_RC" -eq "$BOUNDED_TIMEOUT_RC" ]; then
  # Deliberately NOT a fallback case: a docker CLI that cannot answer its own
  # version query is wedged, and the v1 standalone binary talks to the same
  # wedged socket. Falling back here would trade one hang for another.
  echo "FATAL: 'docker compose version' did not answer within ${DOCKER_PROBE_TIMEOUT_SECONDS}s — the Docker CLI/daemon is HUNG, not absent. Restart Docker Desktop/OrbStack and re-run." >&2
  exit 2
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_BIN=(docker-compose)
else
  echo "FATAL: neither 'docker compose' nor 'docker-compose' is available." >&2
  exit 2
fi

bounded_run "$DOCKER_PROBE_TIMEOUT_SECONDS" docker version >/dev/null 2>&1
PROBE_RC=$?
if [ "$PROBE_RC" -eq "$BOUNDED_TIMEOUT_RC" ]; then
  echo "FATAL: the Docker daemon did not answer 'docker version' within ${DOCKER_PROBE_TIMEOUT_SECONDS}s — it is HUNG, not merely unreachable. Restart Docker Desktop/OrbStack and re-run." >&2
  exit 2
elif [ "$PROBE_RC" -ne 0 ]; then
  echo "FATAL: the Docker daemon is not reachable — start Docker Desktop/OrbStack first." >&2
  exit 2
fi

# ---- output helpers ----------------------------------------------------------
BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; CYA=$'\033[36m'; RST=$'\033[0m'
PASS_N=0; FAIL_N=0
step()  { printf '\n%s— %s%s\n' "$CYA" "$*" "$RST"; }
ok()    { PASS_N=$((PASS_N+1)); printf '  %sPASS%s  %s\n' "$GRN" "$RST" "$*"; }
bad()   { FAIL_N=$((FAIL_N+1)); printf '  %sFAIL%s  %s\n' "$RED" "$RST" "$*"; }
info()  { printf '  %s%s%s\n' "$DIM" "$*" "$RST"; }
banner(){ printf '\n%s========== %s ==========%s\n' "$BOLD" "$*" "$RST"; }

# The five acceptance flows (a)-(e). Sourced, not forked: they assert through
# the helpers above and add to the same PASS_N/FAIL_N tally, so `flows` reports
# in one voice with the three auth flows instead of alongside them.
. "$REPO_ROOT/scripts/lib/acceptance-flows.sh"

# ---- per-flow isolation state (set by begin_flow) ---------------------------
PROJECT=""; ENVFILE=""; BASE=""; API_HOST_PORT=""; COMPOSE_FILES=()

# Guarded teardown — refuses anything that is not an entropia-e2e-* project.
teardown() {
  [ -z "$PROJECT" ] && return 0
  case "$PROJECT" in
    entropia-e2e-*) : ;;
    *) echo "REFUSING to 'down -v' non-E2E project: $PROJECT" >&2; return 0 ;;
  esac
  info "tearing down $PROJECT (isolated volumes removed)"
  # Bounded: this runs from the EXIT trap, so an unbounded `down -v` against a
  # daemon that wedged mid-run would hang the script AFTER it had already
  # decided its verdict — a hang with the answer in hand. Never fatal here.
  local down_rc=0
  bounded_run "$TEARDOWN_TIMEOUT_SECONDS" \
    "${COMPOSE_BIN[@]}" -p "$PROJECT" "${COMPOSE_FILES[@]}" down -v --remove-orphans >/dev/null 2>&1 || down_rc=$?
  if [ "$down_rc" -eq "$BOUNDED_TIMEOUT_RC" ]; then
    echo "WARN: teardown of $PROJECT did not finish within ${TEARDOWN_TIMEOUT_SECONDS}s — its containers/volumes may still exist; the Docker daemon is likely hung." >&2
  fi
  [ -n "$ENVFILE" ] && rm -f "$REPO_ROOT/$ENVFILE"
  PROJECT=""; ENVFILE=""
}
trap teardown EXIT INT TERM

# dc — run compose for the CURRENT flow with all interpolation vars exported.
# Deliberately UNBOUNDED: its callers are `up --build`, `exec` and `logs`, whose
# honest duration is minutes. Bounding those would invent false failures, which
# is the opposite of what ADIM 36 is for.
dc() { "${COMPOSE_BIN[@]}" -p "$PROJECT" "${COMPOSE_FILES[@]}" "$@"; }

# dc_probe / inspect_field — the SHORT queries, bounded. Returns the command's
# own status, or BOUNDED_TIMEOUT_RC when Docker did not answer in time.
dc_probe()      { bounded_run "$DOCKER_PROBE_TIMEOUT_SECONDS" "${COMPOSE_BIN[@]}" -p "$PROJECT" "${COMPOSE_FILES[@]}" "$@"; }
inspect_field() { bounded_run "$DOCKER_PROBE_TIMEOUT_SECONDS" docker inspect -f "$1" "$2" 2>/dev/null; }

# ---- HTTP helpers (curl; no jq/python dependency) ---------------------------
LAST_STATUS=""; LAST_BODY=""
req() {
  # req METHOD PATH [extra curl args...]
  local method="$1" path="$2"; shift 2
  local tmp; tmp="$(mktemp)"
  LAST_STATUS="$(curl -s -o "$tmp" -w '%{http_code}' --max-time 25 -X "$method" "$@" "$BASE$path" 2>/dev/null)"
  LAST_BODY="$(cat "$tmp")"; rm -f "$tmp"
}
jfield() { # jfield JSON FIELD -> first string value of "FIELD":"..."
  printf '%s' "$1" | sed -n 's/.*"'"$2"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1
}
has() { printf '%s' "$1" | grep -qF -- "$2"; }

wait_healthy() {
  local url="$BASE/health/live" i
  info "waiting for API health at :$API_HOST_PORT (build + migrate can take a few minutes)"
  for i in $(seq 1 180); do
    if [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null)" = "200" ]; then
      return 0
    fi
    sleep 2
  done
  return 1
}

# Assert every long-running worker/coordinator/scheduler plane is up & healthy.
assert_planes_healthy() {
  # Every long-running plane docker-compose.yml defines. `worker-agent-executor`
  # is not optional: without it the Coordinator enqueues Agent tasks nobody
  # consumes and the scheduler re-sends them forever, every send reporting
  # success — the silent loop that service's own comment describes. It was
  # missing from this list, so the flow could pass with that plane absent.
  local planes="worker-default worker-data worker-backtest worker-agent worker-agent-executor agent-coordinator scheduler"
  local svc cid status health restarts probe_rc hung
  for svc in $planes; do
    # Same fault class as the preflight: these are instantaneous queries, and an
    # unbounded one turns a wedged daemon into a hang HERE instead of a verdict.
    # A timed-out probe is reported as its own thing — it is a statement about
    # Docker, NOT a verdict on the plane, and it is never a pass.
    cid="$(dc_probe ps -aq "$svc" 2>/dev/null)"; probe_rc=$?
    if [ "$probe_rc" -eq "$BOUNDED_TIMEOUT_RC" ]; then
      bad "[$1] plane $svc — 'compose ps' did not answer within ${DOCKER_PROBE_TIMEOUT_SECONDS}s (Docker is hung; not a verdict on the plane)"; continue
    fi
    cid="$(printf '%s' "$cid" | head -n1)"
    if [ -z "$cid" ]; then bad "[$1] plane $svc — no container"; continue; fi
    hung=0
    status="$(inspect_field '{{.State.Status}}' "$cid")"; [ $? -eq "$BOUNDED_TIMEOUT_RC" ] && hung=1
    restarts="$(inspect_field '{{.RestartCount}}' "$cid")"; [ $? -eq "$BOUNDED_TIMEOUT_RC" ] && hung=1
    health="$(inspect_field '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid")"; [ $? -eq "$BOUNDED_TIMEOUT_RC" ] && hung=1
    if [ "$hung" -eq 1 ]; then
      bad "[$1] plane $svc — 'docker inspect' did not answer within ${DOCKER_PROBE_TIMEOUT_SECONDS}s (Docker is hung; not a verdict on the plane)"; continue
    fi
    if [ "$status" = "running" ] && [ "${restarts:-0}" -eq 0 ] && { [ "$health" = "healthy" ] || [ "$health" = "none" ]; }; then
      ok "[$1] plane $svc broker-connected (health=$health restarts=$restarts)"
    else
      bad "[$1] plane $svc unhealthy (status=$status health=$health restarts=$restarts)"
    fi
  done
}

# ---- hermetic env-file writer -----------------------------------------------
# write_env FLOW AUTH_MODE  — emits .env.e2e.<flow> with non-colliding ports.
# Extra KEY=VALUE lines may follow (e.g. SEED_* toggles for the legacy fixture).
write_env() {
  local flow="$1" mode="$2"; shift 2
  local token; token="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  ENVFILE=".env.e2e.$flow"
  {
    echo "# GENERATED by scripts/e2e-acceptance.sh — git-ignored, safe to delete."
    echo "ENTROPIA_ENV=local"
    echo "AUTH_MODE=$mode"
    echo "ENTROPIA_SERVICE_TOKEN=$token"
    echo "ENTROPIA_BOOTSTRAP_ADMIN_EMAIL=$BOOTSTRAP_EMAIL"
    echo "POSTGRES_USER=entropia"
    echo "POSTGRES_PASSWORD=entropia"
    echo "POSTGRES_DB=entropia"
    echo "DATABASE_URL=postgresql+asyncpg://entropia:entropia@postgres:5432/entropia"
    echo "REDIS_URL=redis://redis:6379/0"
    echo "OBJECT_STORAGE_ENDPOINT=http://minio:9000"
    echo "OBJECT_STORAGE_ACCESS_KEY=entropia"
    echo "OBJECT_STORAGE_SECRET_KEY=entropia-secret"
    echo "OBJECT_STORAGE_BUCKET=entropia-artifacts"
    # The scheduler tick also relays the outbox that feeds SSE, so at the 30s
    # production cadence every advertised-async step (Pre-Check, candidate,
    # baseline parse, validation) waits up to a full tick before the UI can see
    # its result — four steps ≈ 90s, exactly the Create Package spec's budget,
    # which made that spec pass or fail on the sum rather than on behaviour.
    # 1s here keeps the suite measuring the REAL async path (durable job ->
    # worker -> outbox -> SSE) while taking the sweep cadence off the clock.
    # Hermetic file only: the developer's own .env is never touched.
    echo "SCHEDULER_TICK_SECONDS=1"
    local kv; for kv in "$@"; do echo "$kv"; done
  } > "$REPO_ROOT/$ENVFILE"
}

# begin_flow FLOW AUTH_MODE API WEB PG REDIS MINIO MINIOC [dev-auth] [env extras...]
begin_flow() {
  local flow="$1" mode="$2"
  API_HOST_PORT="$3"; local web="$4" pg="$5" redis="$6" minio="$7" minioc="$8"; shift 8
  COMPOSE_FILES=(-f docker-compose.yml)
  if [ "${1:-}" = "dev-auth" ]; then COMPOSE_FILES+=(-f docker-compose.dev-auth.yml); shift; fi
  BOOTSTRAP_EMAIL="admin-e2e@entropia.local"
  PROJECT="entropia-e2e-$flow"
  write_env "$flow" "$mode" "$@"
  # Exported here so BOTH compose interpolation and container env resolve them.
  export ENTROPIA_ENV_FILE="$ENVFILE"
  export API_HOST_PORT WEB_HOST_PORT="$web" PG_HOST_PORT="$pg" REDIS_HOST_PORT="$redis"
  export MINIO_HOST_PORT="$minio" MINIO_CONSOLE_HOST_PORT="$minioc"
  export VITE_API_BASE_URL="http://localhost:$API_HOST_PORT/api/v1"
  BASE="http://localhost:$API_HOST_PORT/api/v1"
  info "project=$PROJECT  auth_mode=$mode  api=:$API_HOST_PORT  env=$ENVFILE"
}

# =============================================================================
# §9.4 — Real session-mode Docker E2E (clean bootstrap on a fresh database)
# =============================================================================
flow_session() {
  banner "§9.4 SESSION-CLEAN"
  begin_flow session session 18000 18080 15432 16379 19000 19001
  step "[1] build the normal session profile (no ad-hoc mode replacement) + [14] bring the stack up"
  dc up -d --build >/dev/null 2>&1 || { bad "compose up failed"; return; }
  wait_healthy || { bad "API never became healthy"; dc ps; return; }
  req GET /meta
  [ "$LAST_STATUS" = 200 ] && has "$LAST_BODY" '"auth_mode":"session"' \
    && ok "[1] /meta.auth_mode=session (real session profile)" || bad "[1] /meta -> $LAST_STATUS $LAST_BODY"

  step "[2] a strong service token is configured (never printed)"
  local tok; tok="$(sed -n 's/^ENTROPIA_SERVICE_TOKEN=//p' "$REPO_ROOT/$ENVFILE")"
  [ "${#tok}" -ge 32 ] && ok "[2] ENTROPIA_SERVICE_TOKEN present, length ${#tok} (value withheld)" \
    || bad "[2] service token missing/too short"

  step "[3] mode-safe provisioning completed (session skips the credentialless Admin)"
  dc exec -T api python -m entropia.apps.seed >/dev/null 2>&1 && ok "[3] seed (provisioning) exit 0" || bad "[3] seed failed"
  req GET /auth/bootstrap-status
  [ "$LAST_STATUS" = 200 ] && has "$LAST_BODY" '"login_capable_admin_exists":false' \
    && ok "[3] fresh DB — no login-capable Admin yet (bootstrap open)" || bad "[3] bootstrap-status -> $LAST_STATUS $LAST_BODY"

  step "[4] sign up the bootstrap Admin on the fresh database"
  req POST /auth/signup -H 'Content-Type: application/json' \
    -d "{\"username\":\"e2eadmin\",\"password\":\"Bootstrap!pw123\",\"email\":\"$BOOTSTRAP_EMAIL\"}"
  local admin_id; admin_id="$(jfield "$LAST_BODY" user_id)"
  { [ "$LAST_STATUS" = 201 ] && has "$LAST_BODY" '"role":"admin"'; } \
    && ok "[4] bootstrap Admin created (role=admin, id=$admin_id)" || bad "[4] signup -> $LAST_STATUS $LAST_BODY"
  req GET /auth/bootstrap-status
  has "$LAST_BODY" '"login_capable_admin_exists":true' \
    && ok "[4] bootstrap-status now reports a login-capable Admin" || bad "[4] bootstrap did not register"

  step "[5] log out and log in again"
  req POST /auth/login -H 'Content-Type: application/json' -d '{"username":"e2eadmin","password":"Bootstrap!pw123"}'
  local tokA; tokA="$(jfield "$LAST_BODY" token)"
  [ -n "$tokA" ] && ok "[5] first login issued a session token" || bad "[5] login A -> $LAST_STATUS $LAST_BODY"
  req POST /auth/logout -H "Authorization: Bearer $tokA"
  { [ "$LAST_STATUS" = 200 ] && has "$LAST_BODY" '"revoked":true'; } && ok "[5] logout revoked the session" || bad "[5] logout -> $LAST_STATUS $LAST_BODY"
  req POST /auth/login -H 'Content-Type: application/json' -d '{"username":"e2eadmin","password":"Bootstrap!pw123"}'
  local tokB; tokB="$(jfield "$LAST_BODY" token)"
  [ -n "$tokB" ] && ok "[5] second login issued a fresh token" || bad "[5] login B -> $LAST_STATUS $LAST_BODY"

  step "[6] /me returns the exact authenticated principal and role"
  req GET /me -H "Authorization: Bearer $tokB"
  { [ "$LAST_STATUS" = 200 ] && has "$LAST_BODY" '"is_admin":true' && has "$LAST_BODY" '"is_authenticated":true' && has "$LAST_BODY" "\"principal_id\":\"$admin_id\""; } \
    && ok "[6] /me -> principal_id=$admin_id, is_admin=true" || bad "[6] /me -> $LAST_STATUS $LAST_BODY"

  step "[7] Mainboard and strategy endpoints do not return 401 + [8] no auth error in protected surface"
  req GET /mainboards/default -H "Authorization: Bearer $tokB"
  [ "$LAST_STATUS" != 401 ] && ok "[7] GET /mainboards/default -> $LAST_STATUS (not 401)" || bad "[7] /mainboards/default 401"
  req GET /strategy-drafts -H "Authorization: Bearer $tokB"
  [ "$LAST_STATUS" != 401 ] && ok "[7/8] GET /strategy-drafts -> $LAST_STATUS (protected surface renders, no auth error)" || bad "[7/8] /strategy-drafts 401"

  step "[9] refresh and retain the session"
  req GET /me -H "Authorization: Bearer $tokB"
  { [ "$LAST_STATUS" = 200 ] && has "$LAST_BODY" "\"principal_id\":\"$admin_id\""; } \
    && ok "[9] re-request with the stored token still authenticates (session retained)" || bad "[9] session not retained -> $LAST_STATUS"

  step "[10] create a normal User and prove the Admin surface is hidden"
  req POST /auth/signup -H 'Content-Type: application/json' \
    -d '{"username":"e2euser","password":"Member!pw123","email":"member-e2e@entropia.local"}'
  { [ "$LAST_STATUS" = 201 ] && has "$LAST_BODY" '"role":"user"'; } && ok "[10] normal User created (role=user)" || bad "[10] user signup -> $LAST_STATUS $LAST_BODY"
  req POST /auth/login -H 'Content-Type: application/json' -d '{"username":"e2euser","password":"Member!pw123"}'
  local tokU; tokU="$(jfield "$LAST_BODY" token)"
  req GET /me -H "Authorization: Bearer $tokU"
  has "$LAST_BODY" '"is_admin":false' && ok "[10] /me for the User -> is_admin=false" || bad "[10] user /me -> $LAST_BODY"
  req GET /admin/users -H "Authorization: Bearer $tokU"
  [ "$LAST_STATUS" = 403 ] && ok "[10] GET /admin/users as User -> 403 (Admin surface hidden)" || bad "[10] admin route not gated -> $LAST_STATUS"
  req GET /admin/users -H "Authorization: Bearer $tokB"
  [ "$LAST_STATUS" = 200 ] && ok "[10] GET /admin/users as Admin -> 200 (surface visible to Admin)" || bad "[10] admin route denied to Admin -> $LAST_STATUS"

  step "[11] revoke/logout and prove the old token is rejected + [12] one clean SESSION_INVALID redirect"
  req POST /auth/logout -H "Authorization: Bearer $tokU"
  has "$LAST_BODY" '"revoked":true' && ok "[11] User session revoked" || bad "[11] logout -> $LAST_STATUS $LAST_BODY"
  req GET /me -H "Authorization: Bearer $tokU"
  { [ "$LAST_STATUS" = 401 ] && has "$LAST_BODY" 'SESSION_INVALID'; } \
    && ok "[11/12] revoked token -> 401 SESSION_INVALID (canonical single-redirect signal, not silent anonymous)" \
    || bad "[11/12] revoked token -> $LAST_STATUS $LAST_BODY (want 401 SESSION_INVALID)"

  step "[13] every worker plane is up and broker-connected"
  assert_planes_healthy 13
  info "[13] per-plane JOB execution (data/backtest/agent pipelines) is exercised by backend integration — tests/integration/test_e2e_pipeline.py (honest boundary: not re-driven from this shell harness)"

  step "[14] full stack acceptance gate — API, web, Postgres, Redis, MinIO, scheduler, coordinator, all workers"
  if COMPOSE_PROJECT_NAME="$PROJECT" ENTROPIA_ENV_FILE="$ENVFILE" bash scripts/acceptance.sh >/tmp/e2e_accept_$$ 2>&1; then
    ok "[14] acceptance gate — nothing exited/restarted/unhealthy"
  else
    bad "[14] acceptance gate FAILED:"; sed 's/^/      /' /tmp/e2e_accept_$$
  fi
  rm -f /tmp/e2e_accept_$$
  teardown
}

# =============================================================================
# §9.5 — Real legacy-upgrade E2E (credentialless user_admin + owned records)
# =============================================================================
flow_legacy() {
  banner "§9.5 LEGACY-UPGRADE"
  # Phase A: OLD state — dev mode seeds the credentialless user_admin + owned
  # domain records (instruments/market data). SAME project/volumes reused in B.
  begin_flow legacy dev 18010 18090 15442 16389 19010 19011 \
    SEED_DEV_ADMIN=1 SEED_INSTRUMENTS=1 SEED_DEMO_MARKET=1
  step "[1] create the OLD database state (credentialless user_admin + owned records)"
  dc up -d --build >/dev/null 2>&1 || { bad "compose up (phase A) failed"; return; }
  wait_healthy || { bad "API (phase A) never healthy"; return; }
  dc exec -T api python -m entropia.apps.seed >/dev/null 2>&1 && ok "[1] legacy seed exit 0" || bad "[1] legacy seed failed"
  req GET /me -H 'X-Actor-Id: user_admin'
  has "$LAST_BODY" '"is_admin":true' && ok "[1] credentialless user_admin resolves as Admin via X-Actor-Id" || bad "[1] user_admin not admin -> $LAST_BODY"
  # Shape-independent snapshot straight from Postgres (ground truth).
  local a_hu a_pr a_ag a_ir a_ae adminrow
  a_hu="$(dc exec -T postgres psql -U entropia -d entropia -tAc 'select count(*) from human_users' 2>/dev/null | tr -d '[:space:]')"
  a_pr="$(dc exec -T postgres psql -U entropia -d entropia -tAc 'select count(*) from principals' 2>/dev/null | tr -d '[:space:]')"
  a_ag="$(dc exec -T postgres psql -U entropia -d entropia -tAc 'select count(*) from agents' 2>/dev/null | tr -d '[:space:]')"
  a_ir="$(dc exec -T postgres psql -U entropia -d entropia -tAc 'select count(*) from instrument_registry' 2>/dev/null | tr -d '[:space:]')"
  a_ae="$(dc exec -T postgres psql -U entropia -d entropia -tAc 'select count(*) from audit_events' 2>/dev/null | tr -d '[:space:]')"
  adminrow="$(dc exec -T postgres psql -U entropia -d entropia -tAc "select user_id||'|'||username||'|'||current_role from human_users where user_id='user_admin'" 2>/dev/null | tr -d '[:space:]')"
  info "[1] snapshot: human_users=$a_hu principals=$a_pr agents=$a_ag instruments=$a_ir audit=$a_ae admin_row=$adminrow"
  [ -n "$adminrow" ] && ok "[1] representative owned records + admin row captured" || bad "[1] snapshot empty (seed did not populate)"

  step "[2] apply the NEW configuration (AUTH_MODE=session) WITHOUT resetting volumes"
  # Rewrite the hermetic env in place (same file, session mode); recreate the
  # backend containers on the SAME named volumes — this is the real upgrade.
  write_env legacy session
  export ENTROPIA_ENV_FILE="$ENVFILE"
  dc up -d >/dev/null 2>&1 || { bad "compose up (phase B) failed"; return; }
  wait_healthy || { bad "API (phase B) never healthy"; return; }
  req GET /meta; has "$LAST_BODY" '"auth_mode":"session"' && ok "[2] upgraded stack now runs AUTH_MODE=session (volumes intact)" || bad "[2] meta -> $LAST_BODY"

  step "[3] run mode-aware provisioning TWICE (idempotent)"
  dc exec -T api python -m entropia.apps.seed >/dev/null 2>&1 && ok "[3] provisioning run #1 exit 0" || bad "[3] provisioning #1 failed"
  dc exec -T api python -m entropia.apps.seed >/dev/null 2>&1 && ok "[3] provisioning run #2 exit 0 (idempotent)" || bad "[3] provisioning #2 failed"

  step "[4] bootstrap a real Admin (legacy credentialless Admin does NOT block bootstrap — PROV-05)"
  req GET /auth/bootstrap-status
  has "$LAST_BODY" '"login_capable_admin_exists":false' && ok "[4] no login-capable Admin yet — bootstrap still open despite legacy user_admin" || bad "[4] bootstrap blocked -> $LAST_BODY"
  req POST /auth/signup -H 'Content-Type: application/json' \
    -d "{\"username\":\"realadmin\",\"password\":\"Real!admin123\",\"email\":\"$BOOTSTRAP_EMAIL\"}"
  local real_id; real_id="$(jfield "$LAST_BODY" user_id)"
  { [ "$LAST_STATUS" = 201 ] && has "$LAST_BODY" '"role":"admin"'; } && ok "[4] real Admin bootstrapped (id=$real_id)" || bad "[4] bootstrap signup -> $LAST_STATUS $LAST_BODY"

  step "[5] log in and access the Admin surface"
  req POST /auth/login -H 'Content-Type: application/json' -d '{"username":"realadmin","password":"Real!admin123"}'
  local tokR; tokR="$(jfield "$LAST_BODY" token)"
  req GET /admin/users -H "Authorization: Bearer $tokR"
  [ "$LAST_STATUS" = 200 ] && ok "[5] real Admin logged in and reached GET /admin/users -> 200" || bad "[5] admin access -> $LAST_STATUS"

  step "[6] all prior IDs, ownership, audit history and domain data are preserved"
  local b_hu b_pr b_ag b_ir b_ae adminrow2
  b_hu="$(dc exec -T postgres psql -U entropia -d entropia -tAc 'select count(*) from human_users' 2>/dev/null | tr -d '[:space:]')"
  b_pr="$(dc exec -T postgres psql -U entropia -d entropia -tAc 'select count(*) from principals' 2>/dev/null | tr -d '[:space:]')"
  b_ag="$(dc exec -T postgres psql -U entropia -d entropia -tAc 'select count(*) from agents' 2>/dev/null | tr -d '[:space:]')"
  b_ir="$(dc exec -T postgres psql -U entropia -d entropia -tAc 'select count(*) from instrument_registry' 2>/dev/null | tr -d '[:space:]')"
  b_ae="$(dc exec -T postgres psql -U entropia -d entropia -tAc 'select count(*) from audit_events' 2>/dev/null | tr -d '[:space:]')"
  adminrow2="$(dc exec -T postgres psql -U entropia -d entropia -tAc "select user_id||'|'||username||'|'||current_role from human_users where user_id='user_admin'" 2>/dev/null | tr -d '[:space:]')"
  [ "$adminrow2" = "$adminrow" ] && [ -n "$adminrow" ] && ok "[6] legacy user_admin row field-for-field identical ($adminrow2)" || bad "[6] admin row changed: '$adminrow' -> '$adminrow2'"
  [ "${b_ir:-0}" = "${a_ir:-x}" ] && ok "[6] owned instrument records preserved ($b_ir)" || bad "[6] instruments changed: $a_ir -> $b_ir"
  { [ "${b_pr:-0}" -ge "${a_pr:-0}" ] && [ "${b_hu:-0}" -ge "${a_hu:-0}" ] && [ "${b_ag:-0}" -ge "${a_ag:-0}" ]; } \
    && ok "[6] principals/human_users/agents non-destructive (A: $a_pr/$a_hu/$a_ag -> B: $b_pr/$b_hu/$b_ag)" || bad "[6] identity rows lost"
  [ "${b_ae:-0}" -ge "${a_ae:-0}" ] && ok "[6] audit history retained and appended-only (A:$a_ae -> B:$b_ae)" || bad "[6] audit history shrank: $a_ae -> $b_ae"

  step "[7] the real Admin is protected as the last login-capable Admin"
  req POST "/users/$real_id/role" -H "Authorization: Bearer $tokR" -H 'Content-Type: application/json' -d '{"role":"user"}'
  [ "$LAST_STATUS" != 200 ] && ok "[7] self-demotion of the last Admin blocked -> $LAST_STATUS (not 200)" || bad "[7] last Admin was demotable (200)"
  req GET /me -H "Authorization: Bearer $tokR"
  has "$LAST_BODY" '"is_admin":true' && ok "[7] after the attempt the last Admin is STILL admin (invariant holds)" || bad "[7] admin lost its role -> $LAST_BODY"
  teardown
}

# =============================================================================
# §9.6 — Real dev-mode Docker E2E (X-Actor-Id impersonation, no login)
# =============================================================================
flow_dev_auth() {
  banner "§9.6 DEV-AUTH"
  begin_flow dev-auth dev 18020 18100 15452 16399 19020 19021 dev-auth
  step "[1] start the explicit local dev-auth profile"
  dc up -d --build >/dev/null 2>&1 || { bad "compose up (dev-auth) failed"; return; }
  wait_healthy || { bad "API never healthy"; return; }
  ok "[1] base + docker-compose.dev-auth.yml stack is up"

  step "[2] /meta.auth_mode=dev"
  req GET /meta
  { [ "$LAST_STATUS" = 200 ] && has "$LAST_BODY" '"auth_mode":"dev"'; } && ok "[2] /meta.auth_mode=dev" || bad "[2] /meta -> $LAST_STATUS $LAST_BODY"

  step "[3] Login/Sign Up is not functional (login rejected before touching credentials)"
  req POST /auth/login -H 'Content-Type: application/json' -d '{"username":"anyone","password":"whatever"}'
  { [ "$LAST_STATUS" != 200 ] && has "$LAST_BODY" 'AUTH_MODE_MISMATCH'; } \
    && ok "[3] POST /auth/login -> $LAST_STATUS AUTH_MODE_MISMATCH (login dead-on-arrival under dev)" || bad "[3] login not rejected -> $LAST_STATUS $LAST_BODY"

  step "[4] a stale session token in storage is IGNORED + [8] no Bearer is honored"
  req GET /me -H 'Authorization: Bearer stale-token-from-a-previous-session'
  { has "$LAST_BODY" '"is_authenticated":false' && has "$LAST_BODY" 'anonymous'; } \
    && ok "[4/8] Bearer-only request -> anonymous (stale token cannot authenticate under dev)" || bad "[4/8] stale token honored -> $LAST_STATUS $LAST_BODY"

  step "[5] DevActorControl visibility — backend contract (/meta.auth_mode=dev, asserted in [2])"
  info "[5] browser-level visibility is asserted in the frontend layer (audit §9.3: frontend/src/test/*, frontend/e2e/specs/01-auth.spec.ts)"
  ok "[5] backend advertises dev mode so the shell renders DevActorControl"

  step "[6] provision the dev fixture and [7] select user_admin — /me authenticates it via X-Actor-Id"
  dc exec -T api python -m entropia.apps.seed >/dev/null 2>&1 && ok "[6] dev seed exit 0 (credentialless user_admin provisioned)" || bad "[6] dev seed failed"
  req GET /me -H 'X-Actor-Id: user_admin'
  { [ "$LAST_STATUS" = 200 ] && has "$LAST_BODY" '"principal_id":"user_admin"' && has "$LAST_BODY" '"is_authenticated":true' && has "$LAST_BODY" '"is_admin":true'; } \
    && ok "[7] /me -H X-Actor-Id: user_admin -> authenticated Admin principal" || bad "[7] /me -> $LAST_STATUS $LAST_BODY"

  step "[8] a Bearer alongside X-Actor-Id is ignored — only X-Actor-Id resolves"
  req GET /me -H 'X-Actor-Id: user_admin' -H 'Authorization: Bearer bogus'
  has "$LAST_BODY" '"principal_id":"user_admin"' && ok "[8] Bearer ignored; X-Actor-Id wins (no Bearer path under dev)" || bad "[8] Bearer leaked into resolution -> $LAST_BODY"

  step "[9] protected pages work under dev-auth"
  req GET /mainboards/default -H 'X-Actor-Id: user_admin'
  [ "$LAST_STATUS" != 401 ] && ok "[9] GET /mainboards/default -H X-Actor-Id -> $LAST_STATUS (not 401)" || bad "[9] protected page 401 under dev"
  teardown
}

# =============================================================================
# The five acceptance flows (a)-(e) — RC readiness §6.2 blocker 2.
# =============================================================================
# Same isolation contract as the three auth flows above: its own compose
# project, its own volumes, its own non-colliding port block (180xx/181xx, kept
# clear of the a11y audit stack's 182xx), its own hermetic env file.
flow_acceptance() {
  banner "ACCEPTANCE FLOWS (a)-(e)"
  # The three fixtures the flows read are exactly the three the a11y audit stack
  # and .github/workflows/e2e.yml seed, so the browser journeys invoked from
  # here observe the projection they were written against.
  # API_CORS_ORIGINS is not optional here. The API mounts CORS with an explicit
  # allowlist whose default only covers the 5173/8080 dev origins, so the web app
  # published on 18110 is blocked at preflight — and curl, which sends no Origin,
  # reports the very same API perfectly healthy. Measured on the first run of this
  # flow: OPTIONS /meta with Origin http://localhost:18110 -> 400, and every
  # browser journey failed on a shell that could not reach its own backend.
  # (scripts/a11y-audit-stack.sh carries the same line for the same reason.)
  begin_flow flows session 18030 18110 15462 16409 19030 19031 \
    "API_CORS_ORIGINS=http://localhost:18110,http://127.0.0.1:18110"
  step "[flows] bring the isolated stack up"
  dc up -d --build >/dev/null 2>&1 || { bad "compose up (flows) failed"; return; }
  wait_healthy || { bad "API (flows) never became healthy"; dc ps; return; }
  dc exec -T -e SEED_E2E_GOLDEN=1 -e SEED_ESP_TA=1 -e SEED_RATIONALE=1 api \
    python -m entropia.apps.seed >/dev/null 2>&1 \
    && ok "[flows] seed (SEED_E2E_GOLDEN + SEED_ESP_TA + SEED_RATIONALE) exit 0" \
    || { bad "[flows] seed failed"; return; }
  assert_planes_healthy flows

  af_run_all_flows

  if [ "${E2E_KEEP_UP:-0}" = "1" ]; then
    info "E2E_KEEP_UP=1 — leaving $PROJECT up (web http://localhost:$WEB_HOST_PORT, api $BASE)"
    trap - EXIT INT TERM
  else
    teardown
  fi
}

# ---- driver -----------------------------------------------------------------
FLOW="${1:-all}"
case "$FLOW" in
  session)  flow_session ;;
  legacy)   flow_legacy ;;
  dev-auth) flow_dev_auth ;;
  flows)    flow_acceptance ;;
  all)      flow_session; flow_legacy; flow_dev_auth; flow_acceptance ;;
  *) echo "usage: $0 [session|legacy|dev-auth|flows|all]" >&2; exit 2 ;;
esac

banner "RESULT"
printf '  %s%d passed%s, %s%d failed%s, %s%d skipped%s\n' \
  "$GRN" "$PASS_N" "$RST" "$RED" "$FAIL_N" "$RST" "$YEL" "${AF_SKIP_N:-0}" "$RST"
# A SKIP is work that did not happen. It never counts as green, but it must not
# be silently swallowed either — it is printed above and named on its own line.
[ "${AF_SKIP_N:-0}" -gt 0 ] && echo "  (${AF_SKIP_N} step(s) SKIPPED — see the SKIP lines; they are NOT passes)"

# ---- skip ceiling (ADIM 45) --------------------------------------------------
# Wiring `flows` into CI created a hole this script did not have as a local
# command: a SKIP does not fail the run, so a step that QUIETLY STOPS RUNNING —
# a browser toolchain that vanished, a fixture that stopped being seeded, a new
# `af_skip` added in passing — would keep the gate green while measuring less
# than it did yesterday. That is the exact "a regression can come back silently"
# failure this gate was wired to prevent, reintroduced one level up.
#
# So CI pins the number: E2E_MAX_SKIPS is the ADJUDICATED skip count, and one
# more than that fails. It is NOT a way to bless skips — the ceiling only freezes
# the ones already written down with a reason, and a new one must be argued for
# in the same place the old ones were (RC readiness §6.2) before this number may
# move. Unset = no ceiling, so a developer's local run is unchanged, and so is
# .github/workflows/install-acceptance.yml, which runs `legacy` (zero skips).
if [ -n "${E2E_MAX_SKIPS:-}" ] && [ "${AF_SKIP_N:-0}" -gt "$E2E_MAX_SKIPS" ]; then
  echo "E2E ACCEPTANCE FAILED — ${AF_SKIP_N} step(s) skipped, ceiling is ${E2E_MAX_SKIPS}."
  echo "  A NEW skip appeared. Either restore the step, or adjudicate it in"
  echo "  docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.2 and raise the ceiling THERE."
  exit 1
fi
[ "$FAIL_N" -eq 0 ] && { echo "E2E ACCEPTANCE OK — every asserted step passed."; exit 0; }
echo "E2E ACCEPTANCE FAILED — see the FAIL lines above."; exit 1
