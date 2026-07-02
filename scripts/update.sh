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
