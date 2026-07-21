#!/usr/bin/env bash
# Ensure .env carries a non-empty ENTROPIA_SERVICE_TOKEN (macOS / Linux).
#
# Session mode is the normal local profile, and in session mode the non-human
# runtimes (agent, scheduler, coordinator, every worker) authenticate with this
# static service token plus their own X-Actor-Id. An empty value disables the
# service line, so those runtimes silently lose their identity.
#
# The value is generated locally into the git-ignored .env and never committed.
# An existing non-empty value is ALWAYS left untouched — this script must be safe
# to re-run from update.sh without rotating a working deployment's secret.
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf "\033[36m▸ %s\033[0m\n" "$1"; }

[ -f .env ] || { say "No .env yet — skipping service-token check"; exit 0; }

if grep -qE '^ENTROPIA_SERVICE_TOKEN=.+$' .env; then
  say "ENTROPIA_SERVICE_TOKEN already set — leaving it untouched"
  exit 0
fi

if command -v openssl >/dev/null 2>&1; then
  token="$(openssl rand -hex 32)"
else
  token="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi

tmp="$(mktemp)"
if grep -qE '^ENTROPIA_SERVICE_TOKEN=' .env; then
  # sed -i is not portable across BSD/GNU, so write through a temp file.
  sed "s|^ENTROPIA_SERVICE_TOKEN=.*|ENTROPIA_SERVICE_TOKEN=${token}|" .env > "$tmp"
else
  cp .env "$tmp"
  printf '\nENTROPIA_SERVICE_TOKEN=%s\n' "$token" >> "$tmp"
fi
mv "$tmp" .env
say "Generated ENTROPIA_SERVICE_TOKEN into .env (git-ignored — never commit it)"
