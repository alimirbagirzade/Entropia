#!/usr/bin/env bash
# Bring the full agentmemory server up, idempotently.
#
# Why this exists. The MCP shim decides ONCE, at connect time, whether a server
# is reachable: if the probe fails it falls back to 7 local tools for the whole
# session and never upgrades. The full server is what turns literal keyword
# matching into hybrid retrieval — measured on this repo, the English query
# "focus ring contrast accessibility" finds the Turkish §ADIM 48 record with the
# server up and returns NOTHING without it. So the server has to be live before
# the shim probes, which is why scripts/memory_mcp.sh calls this first.
#
# Nothing is hosted. The store is a derived index (scripts/memory_index.mjs), so
# an ephemeral container losing it costs a few seconds, not a checkpoint — the
# reason ADIM 53 inverted the dependency in the first place.
#
# Exit 0 = a server is live at $AGENTMEMORY_URL. Exit 1 = it is not; the caller
# is expected to carry on with the reduced fallback rather than fail the session.
set -uo pipefail

URL="${AGENTMEMORY_URL:-http://localhost:3111}"
PACKAGE="@agentmemory/agentmemory@0.9.28"
LOG="${AGENTMEMORY_LOG:-/tmp/agentmemory-server.log}"
# Cold start measured at 33s in a fresh remote container (npm download included).
DEADLINE="${AGENTMEMORY_START_TIMEOUT:-120}"

live() { curl -sf -m 3 "$URL/agentmemory/livez" >/dev/null 2>&1; }

if live; then
  echo "agentmemory: zaten canlı ($URL)" >&2
  exit 0
fi

# A remote URL is somebody else's server — starting a local one would silently
# answer a different store than the caller asked for.
case "$URL" in
  http://localhost:*|http://127.0.0.1:*) ;;
  *)
    echo "agentmemory: $URL canlı değil ve yerel değil — kendiliğinden başlatılmıyor" >&2
    exit 1
    ;;
esac

# The server binds III_REST_PORT (3111 by default), NOT whatever port the URL
# names. Without this the probe and the process disagree: a URL on :3999 would
# spawn a server on :3111, never satisfy the probe, and leave it running. Caught
# by this script's own negative control, not by reading the docs.
PORT="${URL##*:}"
PORT="${PORT%%/*}"
[ -n "$PORT" ] && [ "$PORT" -eq "$PORT" ] 2>/dev/null || PORT=3111

command -v npx >/dev/null 2>&1 || { echo "agentmemory: npx yok" >&2; exit 1; }

echo "agentmemory: başlatılıyor ($PACKAGE, port $PORT, log: $LOG)" >&2
III_REST_PORT="$PORT" nohup npx -y "$PACKAGE" >"$LOG" 2>&1 &

waited=0
while [ "$waited" -lt "$DEADLINE" ]; do
  sleep 2
  waited=$((waited + 2))
  if live; then
    echo "agentmemory: canlı ${waited}s içinde ($URL)" >&2
    exit 0
  fi
done

echo "agentmemory: ${DEADLINE}s içinde ayağa kalkmadı — son log:" >&2
tail -5 "$LOG" >&2 2>/dev/null || true
exit 1
