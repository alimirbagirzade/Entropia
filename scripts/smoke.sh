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

say "== Identity (dev-mode actor header) =="
me=$(fetch -H "X-Actor-Id: $ACTOR" "$BASE_URL/me")
case "$me" in
  *'"principal_id":"'"$ACTOR"'"'*) pass "/me as $ACTOR -> $me" ;;
  *'"principal_type":"anonymous"'*) warn "/me -> anonymous. Seed first: ./scripts/smoke.sh --seed (or AUTH_MODE=session is active — log in via the web app instead)" ;;
  *) warn "/me -> ${me:-no response}" ;;
esac

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
