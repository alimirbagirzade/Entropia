#!/usr/bin/env bash
# =============================================================================
# Entropia — smoke test. Verifies a running stack from the outside, read-only
# except for the idempotent identity seed (optional, --seed).
#
#   ./scripts/smoke.sh                    # API on localhost:8000 (compose or local)
#   BASE_URL=http://localhost:8000/api/v1 ACTOR=user_admin ./scripts/smoke.sh
#   ./scripts/smoke.sh --seed             # also run the identity seed first
#
# Exit code: 0 = core healthy (API + Postgres), 1 = a hard check failed.
# Redis / object storage may be reported "down" in the Docker-free minimal
# setup (README "Bölüm A") — that is a WARN, not a failure.
#
# The FULL end-to-end path (ingest -> package -> strategy -> mainboard ->
# ready check -> RUN -> result -> history -> trash/restore) is executable as
# a single integration test against a dedicated database:
#   cd backend && TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_smoke \
#     uv run pytest tests/integration/test_e2e_pipeline.py --no-cov -q
# =============================================================================
set -u

BASE_URL="${BASE_URL:-http://localhost:8000/api/v1}"
ACTOR="${ACTOR:-user_admin}"
FRONTEND_URLS=("${FRONTEND_URL:-http://localhost:5173}" "http://localhost:8080")
FAIL=0

say()  { printf '%s\n' "$*"; }
pass() { say "  PASS  $*"; }
warn() { say "  WARN  $*"; }
fail() { say "  FAIL  $*"; FAIL=1; }

fetch() { curl -s --max-time 5 "$@" 2>/dev/null; }
# /health/ready probes every dependency live; DOWN deps wait out their own
# connect timeouts, so this endpoint legitimately takes >5s in minimal setups.
fetch_slow() { curl -s --max-time 30 "$@" 2>/dev/null; }
code_of() { curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$@" 2>/dev/null; }

if [ "${1:-}" = "--seed" ]; then
  say "== Seeding baseline identities (idempotent) =="
  (cd "$(dirname "$0")/../backend" && uv run python -m entropia.apps.seed) || fail "seed failed"
fi

say "== Core API =="
live=$(fetch "$BASE_URL/health/live")
if [ "$live" = '{"status":"ok"}' ]; then pass "/health/live -> $live"; else fail "/health/live -> ${live:-no response}"; fi

meta=$(fetch "$BASE_URL/meta")
case "$meta" in
  *'"name":"Entropia'*) pass "/meta -> $meta" ;;
  *) fail "/meta -> ${meta:-no response}" ;;
esac

openapi=$(code_of "$BASE_URL/../../openapi.json")
if [ "$openapi" = "200" ]; then pass "/openapi.json -> 200"; else warn "/openapi.json -> $openapi"; fi

say "== Dependencies (/health/ready) =="
ready=$(fetch_slow "$BASE_URL/health/ready")
say "  raw: ${ready:-no response}"
case "$ready" in
  *'"postgres":"ok"'*) pass "postgres reachable" ;;
  *) fail "postgres NOT reachable — nothing works without it" ;;
esac
case "$ready" in
  *'"redis":"ok"'*) pass "redis reachable (queues live)" ;;
  *) warn "redis down — workers/jobs disabled (OK for the minimal Docker-free setup)" ;;
esac
case "$ready" in
  *'"object_storage":"ok"'*) pass "object storage reachable (artifacts live)" ;;
  *) warn "object storage down — uploads/backtest artifacts disabled (OK for minimal setup)" ;;
esac

say "== Metrics =="
metrics=$(fetch "$BASE_URL/metrics")
case "$metrics" in
  *entropia_http_requests_total*) pass "/metrics serves Prometheus exposition" ;;
  *) fail "/metrics missing entropia_http_requests_total" ;;
esac

# The identity contract depends entirely on the mode the API reports through
# /meta.auth_mode — dev trusts the X-Actor-Id header, session requires a real
# login and ignores that header outright. We branch on the live value so the
# assertions match what the server actually enforces (DEP-06).
say "== Identity (auth-mode aware) =="
auth_mode=""
case "$meta" in
  *'"auth_mode":"session"'*) auth_mode="session" ;;
  *'"auth_mode":"dev"'*)     auth_mode="dev" ;;
esac

if [ -z "$auth_mode" ]; then
  fail "/meta did not report auth_mode — cannot verify the identity contract"
elif [ "$auth_mode" = "dev" ]; then
  # Dev profile: identity comes from the X-Actor-Id header; a seeded actor MUST
  # resolve. Anonymous is now a hard FAILURE, not a warning.
  me=$(fetch -H "X-Actor-Id: $ACTOR" "$BASE_URL/me")
  case "$me" in
    *'"principal_id":"'"$ACTOR"'"'*) pass "dev: /me as $ACTOR -> $me" ;;
    *'"principal_type":"anonymous"'*) fail "dev: /me is anonymous for X-Actor-Id: $ACTOR — seed identities: ./scripts/smoke.sh --seed" ;;
    *) fail "dev: /me -> ${me:-no response}" ;;
  esac
else
  # Session profile: login-based. No X-Actor-Id in the normal path; the header
  # must be ignored; and the login endpoint must be live and reject bad creds.
  # 1) No credential -> anonymous is the correct, enforced state.
  me_anon=$(fetch "$BASE_URL/me")
  case "$me_anon" in
    *'"principal_type":"anonymous"'*) pass "session: unauthenticated /me is anonymous (login required)" ;;
    *) fail "session: unauthenticated /me is NOT anonymous -> ${me_anon:-no response}" ;;
  esac
  # 2) Regression guard: the dev impersonation header must NOT grant identity
  #    under session mode (the "login 200 -> protected 401" mismatch, inverted).
  me_hdr=$(fetch -H "X-Actor-Id: $ACTOR" "$BASE_URL/me")
  case "$me_hdr" in
    *'"principal_id":"'"$ACTOR"'"'*) fail "session: X-Actor-Id impersonation is ACTIVE — dev/session mismatch -> $me_hdr" ;;
    *'"principal_type":"anonymous"'*) pass "session: X-Actor-Id header ignored (no impersonation)" ;;
    *) warn "session: /me with header -> ${me_hdr:-no response}" ;;
  esac
  # 3) Login endpoint is live and rejects bogus credentials with 401.
  login_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    -X POST -H 'Content-Type: application/json' \
    -d '{"username":"__smoke_nobody__","password":"__smoke_wrong__"}' \
    "$BASE_URL/auth/login" 2>/dev/null)
  case "$login_code" in
    401) pass "session: /auth/login live and rejects bad credentials (401)" ;;
    200) fail "session: /auth/login accepted bogus credentials (200) — auth is broken" ;;
    *)   fail "session: /auth/login -> $login_code (expected 401)" ;;
  esac
  # 4) Optional full proof: real login -> Bearer /me -> logout. Credentials come
  #    from the environment and are never echoed.
  if [ -n "${SMOKE_USERNAME:-}" ] && [ -n "${SMOKE_PASSWORD:-}" ]; then
    login_json=$(curl -s --max-time 5 -X POST -H 'Content-Type: application/json' \
      -d "{\"username\":\"${SMOKE_USERNAME}\",\"password\":\"${SMOKE_PASSWORD}\"}" \
      "$BASE_URL/auth/login" 2>/dev/null)
    token=$(printf '%s' "$login_json" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
    if [ -n "$token" ]; then
      me_auth=$(fetch -H "Authorization: Bearer $token" "$BASE_URL/me")
      case "$me_auth" in
        *'"principal_type":"anonymous"'*) fail "session: Bearer /me is anonymous after a successful login" ;;
        *'"principal_id":"'*)             pass "session: login -> Bearer /me resolves a principal" ;;
        *) fail "session: Bearer /me -> ${me_auth:-no response}" ;;
      esac
      logout_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
        -X POST -H "Authorization: Bearer $token" "$BASE_URL/auth/logout" 2>/dev/null)
      if [ "$logout_code" = "200" ]; then pass "session: logout revoked the smoke session"; else warn "session: logout -> $logout_code"; fi
    else
      fail "session: SMOKE_USERNAME/SMOKE_PASSWORD set but login returned no token"
    fi
  else
    say "  (set SMOKE_USERNAME + SMOKE_PASSWORD to also assert a full login -> Bearer /me)"
  fi
fi

say "== Frontend (optional) =="
found_frontend=""
for url in "${FRONTEND_URLS[@]}"; do
  c=$(code_of "$url/")
  if [ "$c" = "200" ]; then pass "$url -> 200"; found_frontend=1; fi
done
[ -z "$found_frontend" ] && warn "no frontend on :5173 (npm run dev) or :8080 (docker compose web) — API-only setup"

say ""
if [ "$FAIL" = "0" ]; then
  say "SMOKE OK — core stack is healthy."
else
  say "SMOKE FAILED — fix the FAIL lines above."
fi
exit "$FAIL"
