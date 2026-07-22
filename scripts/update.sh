#!/usr/bin/env bash
# Entropia V18 — pull latest + update deps + migrate DB (Docker-free).
# Run this on any machine to bring your local checkout up to date:
#   ./scripts/update.sh      (or: make update)
set -euo pipefail

# When run from cron the PATH is minimal — make the usual per-user / Homebrew
# tool locations (uv, git, node) reachable before we call them.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

cd "$(dirname "$0")/.."

say()  { printf "\033[36m▸ %s\033[0m\n" "$1"; }
warn() { printf "\033[33m! %s\033[0m\n" "$1" >&2; }

# 1. Latest code — fast-forward only, so your local commits are never rewritten.
say "Fetching latest code (git pull --ff-only)"
if ! git pull --ff-only; then
  warn "git pull failed. Commit or stash local changes (or resolve conflicts), then re-run."
  exit 1
fi

# 2. Ensure .env exists — never overwrite an existing one (it holds your secrets).
if [ ! -f .env ]; then
  say "Creating .env from .env.example"
  cp .env.example .env
  warn "New .env created. For a Docker-free run, set hosts to 'localhost' (see README)."
fi

# 2b. Non-destructive configuration audit + migration (DEP-03). We never echo a
#     secret value, only key names; we back up .env before any mutation; and we
#     refuse to declare success on unresolved required configuration.
. "$(dirname "$0")/lib/env-audit.sh"

auth_mode="$(env_get AUTH_MODE)"

# Legacy / ambiguous auth profile — require an EXPLICIT, acknowledged choice
# rather than silently accepting or silently changing an intentional setup.
if [ -z "$auth_mode" ]; then
  warn "AUTH_MODE is not set in .env — choose a profile before updating:"
  warn "  • normal browser login:  ./scripts/configure-local-session.sh"
  warn "  • local dev impersonation: set AUTH_MODE=dev in .env, re-run with ENTROPIA_ALLOW_DEV_AUTH=1"
  exit 1
elif [ "$auth_mode" = "dev" ] && [ "${ENTROPIA_ALLOW_DEV_AUTH:-}" != "1" ]; then
  warn "AUTH_MODE=dev detected — local X-Actor-Id impersonation, no login."
  warn "This is a deliberate developer profile; update will not change it silently."
  warn "  • keep dev impersonation:  re-run with ENTROPIA_ALLOW_DEV_AUTH=1"
  warn "  • switch to session login: ./scripts/configure-local-session.sh"
  exit 1
elif [ "$auth_mode" != "dev" ] && [ "$auth_mode" != "session" ]; then
  warn "AUTH_MODE=$auth_mode is not a valid profile (expected 'session' or 'dev')."
  exit 1
fi

# Back up .env once, then migrate — but only if there is actually something to
# change (missing safe keys, or a session profile with no service token yet).
needs_token=0
if [ "$auth_mode" = "session" ] && ! env_has ENTROPIA_SERVICE_TOKEN; then needs_token=1; fi
missing_keys="$(env_missing_example_keys .env.example)"
if [ -n "$missing_keys" ] || [ "$needs_token" = "1" ]; then
  backup="$(env_backup)"
  [ -n "$backup" ] && say "Backed up .env -> $backup"
  added="$(env_append_missing_from_example .env.example)"
  [ -n "$added" ] && say "Added missing non-secret keys: $added"
  # Session mode needs a service-line credential for the non-human runtimes; this
  # only fills an EMPTY value — an existing token is never rotated by an update.
  [ "$needs_token" = "1" ] && "$(dirname "$0")/ensure-service-token.sh"
fi

# Refuse to proceed on unresolved required configuration (values never shown).
unresolved="$(env_unresolved_required)"
if [ -n "$unresolved" ]; then
  warn "Unresolved required configuration (set these in .env, values not shown): $unresolved"
  warn "Update aborted — fix the keys above and re-run. (No changes were applied beyond the .env backup.)"
  exit 1
fi
if [ "$auth_mode" = "dev" ]; then
  say "Auth profile: dev (local impersonation, acknowledged)."
else
  say "Auth profile: session (browser login)."
fi

# 3. Backend dependencies (uv resolves + installs from the committed lockfile).
if command -v uv >/dev/null 2>&1; then
  say "Updating backend dependencies (uv sync)"
  (cd backend && uv sync --all-extras)

  # 4. Database migrations — needs a reachable PostgreSQL.
  say "Applying database migrations (alembic upgrade head)"
  if ! (cd backend && uv run alembic upgrade head); then
    warn "Migration failed — is PostgreSQL running and DATABASE_URL correct?"
    exit 1
  fi
else
  warn "'uv' not found — skipping backend. Install from https://docs.astral.sh/uv/ then re-run."
fi

# 5. Frontend dependencies (only needed for the web UI).
if command -v npm >/dev/null 2>&1; then
  say "Updating frontend dependencies (npm install)"
  (cd frontend && npm install)
else
  warn "'npm' not found — skipping frontend deps (only needed for the web UI)."
fi

say "Update complete. Restart the API / workers to pick up the changes."
