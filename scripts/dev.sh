#!/usr/bin/env bash
# Bring up the full Docker stack (macOS / Linux).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
exec docker compose up -d --build
