#!/usr/bin/env bash
# =============================================================================
# Entropia — acceptance state gate (DEP-05).
#
# Proves every long-running plane is up and NO Compose service has
# exited/restarted/become unhealthy. Run against an ALREADY-RUNNING stack
# (bring it up with `make up` or `make up-dev-auth` first):
#
#   scripts/acceptance.sh                 # session stack (base compose)
#   COMPOSE_DEV_AUTH=1 scripts/acceptance.sh   # dev-auth stack (base + override)
#
# Rules:
#   * one-shots (minio-setup, migrate) MUST be exited with code 0;
#   * every other service MUST be running, healthy (if it declares a
#     healthcheck), and have RestartCount 0 — ANY restart fails the gate.
# Exit code: 0 = all planes healthy, 1 = a plane exited/restarted/unhealthy.
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

# Prefer the Compose v2 plugin; fall back to the standalone binary.
if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=(docker-compose)
fi
if [ "${COMPOSE_DEV_AUTH:-0}" = "1" ]; then
  DC+=(-f docker-compose.yml -f docker-compose.dev-auth.yml)
  PROFILE="dev-auth"
else
  PROFILE="session"
fi

ONE_SHOTS="minio-setup migrate"
FAIL=0

echo "== Acceptance gate ($PROFILE stack) =="

services=$("${DC[@]}" config --services) || { echo "  FAIL  cannot read compose config"; exit 1; }

for svc in $services; do
  cid=$("${DC[@]}" ps -aq "$svc" 2>/dev/null | head -n1)
  if [ -z "$cid" ]; then
    echo "  FAIL  $svc — no container (never created)"; FAIL=1; continue
  fi
  status=$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null)
  exitcode=$(docker inspect -f '{{.State.ExitCode}}' "$cid" 2>/dev/null)
  restarts=$(docker inspect -f '{{.RestartCount}}' "$cid" 2>/dev/null)
  health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null)

  is_oneshot=0
  for o in $ONE_SHOTS; do [ "$svc" = "$o" ] && is_oneshot=1; done

  if [ "$is_oneshot" = "1" ]; then
    if [ "$status" = "exited" ] && [ "$exitcode" = "0" ]; then
      echo "  PASS  $svc — one-shot completed (exit 0)"
    else
      echo "  FAIL  $svc — one-shot status=$status exit=$exitcode (want exited/0)"; FAIL=1
    fi
    continue
  fi

  problems=""
  [ "$status" != "running" ] && problems="$problems status=$status"
  if [ "${restarts:-0}" -gt 0 ]; then problems="$problems restarts=$restarts"; fi
  case "$health" in
    healthy|none) : ;;
    *) problems="$problems health=$health" ;;
  esac

  if [ -n "$problems" ]; then
    echo "  FAIL  $svc —$problems"; FAIL=1
  else
    echo "  PASS  $svc — running (health=$health restarts=$restarts)"
  fi
done

echo ""
if [ "$FAIL" = 0 ]; then
  echo "ACCEPTANCE OK — every plane is up; nothing exited/restarted/unhealthy."
else
  echo "ACCEPTANCE FAILED — see the FAIL lines above."
  "${DC[@]}" ps || true
fi
exit "$FAIL"
