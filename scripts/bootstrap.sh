#!/usr/bin/env bash
# Entropia V18 — one-time local bootstrap (macOS / Linux).
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf "\033[36m▸ %s\033[0m\n" "$1"; }

if [ ! -f .env ]; then
  say "Creating .env from .env.example"
  cp .env.example .env
else
  say ".env already exists — leaving it untouched"
fi

# Session mode (the default local profile) needs a service-line credential for
# the non-human runtimes. Generated into the git-ignored .env; an existing value
# is never rotated.
"$(dirname "$0")/ensure-service-token.sh"

if command -v uv >/dev/null 2>&1; then
  say "Installing backend dependencies (uv sync)"
  (cd backend && uv sync --all-extras)
else
  echo "WARN: 'uv' not found. Install from https://docs.astral.sh/uv/ then re-run." >&2
fi

if command -v npm >/dev/null 2>&1; then
  say "Installing frontend dependencies (npm install)"
  (cd frontend && npm install)
else
  echo "WARN: 'npm' not found. Install Node.js 20+ then re-run." >&2
fi

say "Bootstrap complete. Next: 'make up' (full stack) or 'make backend-dev' + 'make frontend-dev'."
