#!/usr/bin/env bash
# =============================================================================
# Entropia — A-08 human screen-reader audit stack (ADIM 27).
#
# ONE command brings up the exact environment GitHub #514 requires, seeds the
# three fixtures the checklist names, and VALIDATES that the fixtures actually
# landed — so the auditor never spends an NVDA session on pages that are empty
# for a seeding reason rather than a product reason.
#
#   scripts/a11y-audit-stack.sh up        # build + start + seed + validate, STAYS UP
#   scripts/a11y-audit-stack.sh validate  # re-run fixture validation only
#   scripts/a11y-audit-stack.sh status    # what is running, where
#   scripts/a11y-audit-stack.sh down      # explicit teardown (volumes removed)
#
# WHY THIS IS NOT scripts/e2e-acceptance.sh
#   That harness tears the stack down in an EXIT trap, because its consumer is
#   CI. This one's consumer is a human wearing headphones for two hours: an
#   automatic teardown would destroy the session the moment the script returns.
#   Teardown here is a SEPARATE, explicit subcommand and nothing else calls it.
#
# WHAT THIS SCRIPT DOES NOT DO
#   It does not run, simulate, or approximate a screen-reader audit. It cannot.
#   It prepares an environment. A-08 stays HUMAN-BLOCKED until a person with
#   NVDA/Firefox and VoiceOver/Safari fills in
#   docs/audit/a11y_screen_reader_audit_results.md. See #514.
#
# Isolation contract (same discipline as scripts/e2e-acceptance.sh):
#   * Compose project is ALWAYS `entropia-a11y-audit`; `down` refuses any other
#     name, so the developer's own `entropia` project can never be destroyed.
#   * Non-colliding host ports, so this can run beside a normal `make up`.
#   * Hermetic, git-ignored `.env.a11y-audit` via ENTROPIA_ENV_FILE — the real
#     `.env` is never read or written.
#   * A strong ENTROPIA_SERVICE_TOKEN is generated per `up` and never printed.
#
# Remote screen readers: NVDA runs on Windows, VoiceOver on macOS, and the
# stack runs on one of them. `A11Y_HOST` (see below) is the single knob that
# makes the other machine able to reach it.
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

PROJECT="entropia-a11y-audit"
ENVFILE=".env.a11y-audit"

# Host ports — deliberately outside both the default range (8000/8080/5432/...)
# and scripts/e2e-acceptance.sh's 180xx block.
API_PORT="${A11Y_API_PORT:-18200}"
WEB_PORT="${A11Y_WEB_PORT:-18280}"
PG_PORT="${A11Y_PG_PORT:-15472}"
REDIS_PORT="${A11Y_REDIS_PORT:-16419}"
MINIO_PORT="${A11Y_MINIO_PORT:-19200}"
MINIO_CONSOLE_PORT="${A11Y_MINIO_CONSOLE_PORT:-19201}"

# ONE host knob, used for three things that must agree or the app fails closed:
# where the ports are published, what origin the browser will use, and what the
# web bundle is built to call. They are not independent — `VITE_API_BASE_URL` is
# baked in at IMAGE BUILD time and `API_CORS_ORIGINS` is checked against the
# browser's Origin header, so advertising one address while publishing another
# lands the auditor on "Cannot reach the server" with no clue why. (Observed:
# the first run of this script did exactly that.)
#
# Default 127.0.0.1 — a seeded stack with a known bootstrap Admin password is
# not something to put on a network by accident. NVDA runs on Windows and
# VoiceOver on macOS, so the second machine needs a routable address: pass the
# host's LAN IP, e.g.
#   A11Y_HOST=192.168.1.20 scripts/a11y-audit-stack.sh up
A11Y_HOST="${A11Y_HOST:-127.0.0.1}"

# 0.0.0.0 is a bind address, not a reachable one. Accepting it would publish the
# ports fine and then bake "http://0.0.0.0:18200/api/v1" into the web bundle and
# the CORS allowlist, so the auditor's browser would fail closed on a URL that
# can never resolve — the same dead end as the CORS bug above, one layer down.
if [ "$A11Y_HOST" = "0.0.0.0" ]; then
  echo "FATAL: A11Y_HOST=0.0.0.0 is a bind address, not one a browser can open." >&2
  echo "       Pass the address the auditor will actually type, e.g." >&2
  echo "         A11Y_HOST=192.168.1.20 $0 up" >&2
  exit 2
fi

BASE="http://$A11Y_HOST:$API_PORT/api/v1"
WEB="http://$A11Y_HOST:$WEB_PORT"

# Must match frontend/e2e/fixtures/auth.ts::ADMIN_ACTOR, so the Playwright
# prechecks and the human auditor sign in as the SAME Admin against the SAME
# stack. Diverging here would give the two halves different projections.
ADMIN_EMAIL="${A11Y_ADMIN_EMAIL:-e2e_admin@e2e.entropia.test}"
ADMIN_USERNAME="${A11Y_ADMIN_USERNAME:-e2e_admin}"
ADMIN_PASSWORD="${A11Y_ADMIN_PASSWORD:-E2e-Admin-Passw0rd!23}"

# ---- compose binary ---------------------------------------------------------
if docker compose version >/dev/null 2>&1; then
  COMPOSE_BIN=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_BIN=(docker-compose)
else
  echo "FATAL: neither 'docker compose' nor 'docker-compose' is available." >&2
  exit 2
fi
if ! docker version >/dev/null 2>&1; then
  echo "FATAL: the Docker daemon is not reachable — start Docker Desktop/OrbStack first." >&2
  exit 2
fi

# ---- output helpers ---------------------------------------------------------
BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; CYA=$'\033[36m'; RST=$'\033[0m'
PASS_N=0; FAIL_N=0
step()  { printf '\n%s— %s%s\n' "$CYA" "$*" "$RST"; }
ok()    { PASS_N=$((PASS_N+1)); printf '  %sPASS%s  %s\n' "$GRN" "$RST" "$*"; }
bad()   { FAIL_N=$((FAIL_N+1)); printf '  %sFAIL%s  %s\n' "$RED" "$RST" "$*"; }
warn()  { printf '  %sWARN%s  %s\n' "$YEL" "$RST" "$*"; }
info()  { printf '  %s%s%s\n' "$DIM" "$*" "$RST"; }
banner(){ printf '\n%s========== %s ==========%s\n' "$BOLD" "$*" "$RST"; }

export_ports() {
  export ENTROPIA_ENV_FILE="$ENVFILE"
  # docker-compose.yml publishes as "${X_HOST_PORT}:<container>", and the left
  # side of a compose mapping accepts "host:port" — so binding to a specific
  # interface needs no change to the compose file.
  export API_HOST_PORT="$A11Y_HOST:$API_PORT"
  export WEB_HOST_PORT="$A11Y_HOST:$WEB_PORT"
  export PG_HOST_PORT="$A11Y_HOST:$PG_PORT"
  export REDIS_HOST_PORT="$A11Y_HOST:$REDIS_PORT"
  export MINIO_HOST_PORT="$A11Y_HOST:$MINIO_PORT"
  export MINIO_CONSOLE_HOST_PORT="$A11Y_HOST:$MINIO_CONSOLE_PORT"
  # Baked into the web image at build time (compose build arg). It must name the
  # address the AUDITOR's browser will use, not the container's own view.
  export VITE_API_BASE_URL="$BASE"
}
dc() { export_ports; "${COMPOSE_BIN[@]}" -p "$PROJECT" -f docker-compose.yml "$@"; }

# ---- HTTP helpers -----------------------------------------------------------
LAST_STATUS=""; LAST_BODY=""
req() {
  local method="$1" path="$2"; shift 2
  local tmp; tmp="$(mktemp)"
  LAST_STATUS="$(curl -s -o "$tmp" -w '%{http_code}' --max-time 25 -X "$method" "$@" "$BASE$path" 2>/dev/null)"
  LAST_BODY="$(cat "$tmp")"; rm -f "$tmp"
}
has() { printf '%s' "$1" | grep -qF -- "$2"; }
jfield() { printf '%s' "$1" | sed -n 's/.*"'"$2"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1; }
# Counts occurrences of a key in a JSON list response — enough to prove "the
# fixture produced rows" without adding a jq dependency to an audit-prep script.
countkey() { printf '%s' "$1" | grep -o "\"$2\"" | wc -l | tr -d '[:space:]'; }

write_env() {
  local token; token="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  {
    echo "# GENERATED by scripts/a11y-audit-stack.sh — git-ignored, safe to delete."
    echo "# A-08 human screen-reader audit stack. Not a production profile."
    echo "ENTROPIA_ENV=local"
    echo "AUTH_MODE=session"
    echo "ENTROPIA_SERVICE_TOKEN=$token"
    echo "ENTROPIA_BOOTSTRAP_ADMIN_EMAIL=$ADMIN_EMAIL"
    echo "POSTGRES_USER=entropia"
    echo "POSTGRES_PASSWORD=entropia"
    echo "POSTGRES_DB=entropia"
    echo "DATABASE_URL=postgresql+asyncpg://entropia:entropia@postgres:5432/entropia"
    echo "REDIS_URL=redis://redis:6379/0"
    echo "OBJECT_STORAGE_ENDPOINT=http://minio:9000"
    echo "OBJECT_STORAGE_ACCESS_KEY=entropia"
    echo "OBJECT_STORAGE_SECRET_KEY=entropia-secret"
    echo "OBJECT_STORAGE_BUCKET=entropia-artifacts"
    # The API mounts CORS with allow_credentials=True and an explicit allowlist
    # (I-14), whose default only covers the 5173/8080 dev origins. The audit web
    # app is served from $WEB_PORT, so without this line every browser request
    # is blocked and the shell fails closed on "Cannot reach the server" — while
    # curl, which sends no Origin, reports the API perfectly healthy. Both the
    # localhost and 127.0.0.1 spellings are listed because an Origin header is
    # matched as a literal string, not resolved.
    echo "API_CORS_ORIGINS=http://$A11Y_HOST:$WEB_PORT,http://localhost:$WEB_PORT,http://127.0.0.1:$WEB_PORT"
    # A screen-reader auditor waiting a full 30s production tick for a Ready
    # Check result would be auditing the scheduler, not the announcement. 1s
    # keeps the REAL async path (job -> worker -> outbox -> SSE) intact while
    # taking the sweep cadence off the clock. Hermetic file only.
    echo "SCHEDULER_TICK_SECONDS=1"
  } > "$REPO_ROOT/$ENVFILE"
}

wait_ready() {
  info "waiting for the API and web app (first build + migrate can take minutes)"
  local i
  for i in $(seq 1 180); do
    if curl -fsS --max-time 5 "$BASE/health/ready" >/dev/null 2>&1 \
      && curl -fsS --max-time 5 "$WEB" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

# ---- admin session ----------------------------------------------------------
# Returns a bearer token on stdout, or empty. Signs the bootstrap Admin up on a
# fresh database (ENTROPIA_BOOTSTRAP_ADMIN_EMAIL auto-promotes the first
# signup); logs in when the row already exists, so `validate` is re-runnable.
admin_token() {
  req POST /auth/login -H 'Content-Type: application/json' \
    -d "{\"username\":\"$ADMIN_USERNAME\",\"password\":\"$ADMIN_PASSWORD\"}"
  local tok; tok="$(jfield "$LAST_BODY" token)"
  if [ -z "$tok" ]; then
    req POST /auth/signup -H 'Content-Type: application/json' \
      -d "{\"username\":\"$ADMIN_USERNAME\",\"password\":\"$ADMIN_PASSWORD\",\"email\":\"$ADMIN_EMAIL\"}"
    req POST /auth/login -H 'Content-Type: application/json' \
      -d "{\"username\":\"$ADMIN_USERNAME\",\"password\":\"$ADMIN_PASSWORD\"}"
    tok="$(jfield "$LAST_BODY" token)"
  fi
  printf '%s' "$tok"
}

# The audit routes. "22 pages" in the checklist counts the 22 numbered SPEC
# DOCUMENTS; doc 19 contributes TWO routes (/panel/management, /panel/logs), so
# the route list is 23 long. Kept in ONE place and cross-checked against
# frontend/e2e/utils/screenshotMatrix.ts::TARGET_PAGES by
# backend/tests/contract/test_a11y_audit_prep_contract.py, so the stack, the
# axe scan and the human worksheet can never drift onto different surfaces.
AUDIT_ROUTES=(
  "/" "/strategy" "/outsource-signal" "/trading-signal" "/trade-log"
  "/packages/create" "/packages/pre-check" "/packages/library" "/packages/embedded"
  "/rationale-families" "/market-data" "/research-data" "/portfolio"
  "/backtest/ready-check" "/backtest/run" "/backtest/history" "/backtest/metrics"
  "/analysis-lab" "/panel/management" "/panel/logs" "/trash" "/user-manual"
  "/future-dev"
)

# =============================================================================
# validate — is this stack actually auditable?
# =============================================================================
cmd_validate() {
  banner "A-08 AUDIT STACK — FIXTURE VALIDATION"
  PASS_N=0; FAIL_N=0

  step "[1] stack reachable"
  req GET /health/ready
  [ "$LAST_STATUS" = 200 ] && ok "API ready at $BASE" || bad "API /health/ready -> $LAST_STATUS"
  local webcode; webcode="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$WEB" 2>/dev/null)"
  [ "$webcode" = 200 ] && ok "web app served at $WEB" || bad "web app -> $webcode"

  step "[2] session profile (the profile a real user logs into)"
  req GET /meta
  has "$LAST_BODY" '"auth_mode":"session"' \
    && ok "/meta.auth_mode=session" \
    || bad "/meta.auth_mode is NOT session -> $LAST_BODY"

  step "[3] Admin session"
  local tok; tok="$(admin_token)"
  if [ -z "$tok" ]; then
    bad "could not obtain an Admin session for $ADMIN_USERNAME — the audit needs Admin (Trash / Panel pages)"
    finish_validate; return
  fi
  ok "Admin session obtained for $ADMIN_USERNAME (token withheld)"
  req GET /me -H "Authorization: Bearer $tok"
  has "$LAST_BODY" '"is_admin":true' \
    && ok "/me reports is_admin=true (Admin-only pages will render)" \
    || bad "/me is_admin is not true -> $LAST_BODY"

  step "[4] seeded fixtures — the three the checklist names"
  # SEED_E2E_GOLDEN: approved market dataset + approved/published indicator
  # package. Empty here means every data page in section A is a blank state and
  # the auditor cannot test tables, rows, or expand controls at all.
  req GET /market-datasets -H "Authorization: Bearer $tok"
  local mds; mds="$(countkey "$LAST_BODY" entity_id)"
  { [ "$LAST_STATUS" = 200 ] && [ "${mds:-0}" -ge 1 ]; } \
    && ok "SEED_E2E_GOLDEN — market datasets present ($mds row marker(s))" \
    || bad "SEED_E2E_GOLDEN — GET /market-datasets -> $LAST_STATUS, $mds row(s); data pages would audit as empty"

  req GET /library -H "Authorization: Bearer $tok"
  local libs; libs="$(countkey "$LAST_BODY" entity_id)"
  { [ "$LAST_STATUS" = 200 ] && [ "${libs:-0}" -ge 1 ]; } \
    && ok "SEED_E2E_GOLDEN/SEED_ESP_TA — Package Library populated ($libs row marker(s))" \
    || bad "Package Library empty — GET /library -> $LAST_STATUS, $libs row(s)"

  req GET /rationale-families -H "Authorization: Bearer $tok"
  local rfs; rfs="$(countkey "$LAST_BODY" entity_id)"
  { [ "$LAST_STATUS" = 200 ] && [ "${rfs:-0}" -ge 1 ]; } \
    && ok "SEED_RATIONALE — rationale families present ($rfs row marker(s))" \
    || bad "SEED_RATIONALE — GET /rationale-families -> $LAST_STATUS, $rfs row(s)"

  step "[5] every audit route is served (no 404 mid-session)"
  # The SPA answers every in-app path with the shell, so this proves the origin
  # and the route table, NOT that the page's own query succeeded — spec 17
  # (frontend/e2e/specs/17-page-coverage.spec.ts) is what asserts the latter.
  # Stated plainly so a green line here is not read as more than it is.
  local route code missing=0
  for route in "${AUDIT_ROUTES[@]}"; do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$WEB$route" 2>/dev/null)"
    [ "$code" = 200 ] || { warn "route $route -> $code"; missing=$((missing+1)); }
  done
  [ "$missing" -eq 0 ] \
    && ok "${#AUDIT_ROUTES[@]}/${#AUDIT_ROUTES[@]} routes served by $WEB (shell only — per-page reads are spec 17's job)" \
    || bad "$missing route(s) not served — the auditor would hit a dead page"

  finish_validate
}

finish_validate() {
  banner "RESULT"
  printf '  %s%d passed%s, %s%d failed%s\n' "$GRN" "$PASS_N" "$RST" "$RED" "$FAIL_N" "$RST"
  if [ "$FAIL_N" -ne 0 ]; then
    echo "AUDIT STACK NOT READY — fix the FAIL lines before booking auditor time." >&2
    exit 1
  fi
  cat <<TXT

${BOLD}Audit stack is ready.${RST}

  Web (auditor navigates here) : $WEB
  API                          : $BASE
  Admin username               : $ADMIN_USERNAME
  Admin password               : $ADMIN_PASSWORD
  Compose project              : $PROJECT

  Worksheet  : docs/audit/a11y_screen_reader_audit_results.md
  Checklist  : docs/implementation/a11y_screen_reader_audit_checklist.md
  Tracking   : GitHub #514  (human-only — an agent must not close it)

${YEL}A-08 is HUMAN-BLOCKED.${RST} This script prepared an environment. It did not
audit anything, and no output of it may be recorded as a screen-reader PASS.
TXT
  exit 0
}

# =============================================================================
cmd_up() {
  banner "A-08 AUDIT STACK — UP"
  write_env
  info "project=$PROJECT  env=$ENVFILE  web=$WEB  api=$BASE"
  if [ "$A11Y_HOST" != "127.0.0.1" ] && [ "$A11Y_HOST" != "localhost" ]; then
    warn "A11Y_HOST=$A11Y_HOST — the seeded stack and its bootstrap Admin will be reachable beyond this machine."
  fi

  step "build + start"
  # A registry/BuildKit transport blip ("TLS handshake timeout" resolving a base
  # image) kills the build in seconds, before anything real is attempted — the
  # same failure .github/workflows/e2e.yml retries around, and one this script
  # hit on its second run. Retried a bounded number of times.
  #
  # This masks nothing: a broken Dockerfile or an image that genuinely cannot be
  # built fails all three attempts identically and the step still exits non-zero.
  local attempt started=0
  for attempt in 1 2 3; do
    if dc up -d --build; then started=1; break; fi
    warn "docker compose up failed (attempt ${attempt}/3); retrying"
    sleep $((attempt * 10))
  done
  [ "$started" = 1 ] || { echo "compose up failed after 3 attempts" >&2; exit 1; }
  wait_ready || {
    echo "stack did not become ready" >&2
    dc ps; dc logs --tail 200
    exit 1
  }
  ok "stack is up"

  step "seed the audit fixture (idempotent: SEED_E2E_GOLDEN + SEED_ESP_TA + SEED_RATIONALE)"
  # Exactly the three flags GitHub #514 and the checklist name, and exactly the
  # three the E2E/a11y CI jobs use — the human auditor and the axe scan must
  # look at the same projection or their findings cannot be compared.
  dc exec -T -e SEED_E2E_GOLDEN=1 -e SEED_ESP_TA=1 -e SEED_RATIONALE=1 api python -m entropia.apps.seed \
    && ok "seed exit 0" || { bad "seed failed"; exit 1; }

  cmd_validate
}

cmd_status() {
  banner "A-08 AUDIT STACK — STATUS"
  dc ps
  printf '\n  web=%s  api=%s\n' "$WEB" "$BASE"
}

cmd_down() {
  banner "A-08 AUDIT STACK — DOWN"
  # Hard guard: this subcommand removes volumes. It may only ever act on this
  # script's own project name, never on whatever COMPOSE_PROJECT_NAME happens
  # to be exported in the caller's shell.
  case "$PROJECT" in
    entropia-a11y-audit) : ;;
    *) echo "REFUSING to 'down -v' non-audit project: $PROJECT" >&2; exit 2 ;;
  esac
  dc down -v --remove-orphans
  rm -f "$REPO_ROOT/$ENVFILE"
  echo "torn down; $ENVFILE removed."
}

case "${1:-up}" in
  up)       cmd_up ;;
  validate) cmd_validate ;;
  status)   cmd_status ;;
  down)     cmd_down ;;
  *) echo "usage: $0 [up|validate|status|down]" >&2; exit 2 ;;
esac
