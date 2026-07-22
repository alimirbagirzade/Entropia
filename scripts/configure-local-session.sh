#!/usr/bin/env bash
# =============================================================================
# scripts/configure-local-session.sh (DEP-03) — idempotently switch the local
# .env to the NORMAL session profile (real browser login), touching only the
# auth keys. Safe to re-run; never prints a secret or the bootstrap email.
#
#   ./scripts/configure-local-session.sh
#   ./scripts/configure-local-session.sh --email you@example.com   # first Admin
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

say()  { printf "\033[36m▸ %s\033[0m\n" "$1"; }
warn() { printf "\033[33m! %s\033[0m\n" "$1" >&2; }

email=""
while [ $# -gt 0 ]; do
  case "$1" in
    --email) email="${2:-}"; shift 2 ;;
    --email=*) email="${1#--email=}"; shift ;;
    *) warn "Unknown argument: $1"; exit 2 ;;
  esac
done

if [ ! -f .env ]; then
  say "Creating .env from .env.example"
  cp .env.example .env
fi

. "$(dirname "$0")/lib/env-audit.sh"

backup="$(env_backup)"
[ -n "$backup" ] && say "Backed up .env -> $backup"

# Only the auth keys change. AUTH_MODE -> session is idempotent.
env_set AUTH_MODE session
say "AUTH_MODE=session"

# Bootstrap email is recorded but never echoed (it is a sensitive identifier).
if [ -n "$email" ]; then
  env_set ENTROPIA_BOOTSTRAP_ADMIN_EMAIL "$email"
  say "Recorded first-Admin bootstrap email (value not shown)."
fi

# Session mode requires a non-empty service token; generate one only if empty.
"$(dirname "$0")/ensure-service-token.sh"

unresolved="$(env_unresolved_required)"
if [ -n "$unresolved" ]; then
  warn "Still-unresolved required keys (set them in .env, values not shown): $unresolved"
  exit 1
fi

say "Session profile ready. Start the app and Sign Up / Log In in the browser."
