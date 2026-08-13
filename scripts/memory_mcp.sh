#!/usr/bin/env bash
# MCP entry point for agentmemory: ensure the server, then become the shim.
#
# `.mcp.json` runs this instead of the shim directly so that the 53-tool server
# is reachable by the time the shim probes it. If the server cannot be brought
# up we still exec the shim — it degrades to its 7-tool local fallback, which is
# worse at recall but never blocks a session.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$ROOT/scripts/memory_server.sh" || echo "agentmemory: sunucusuz kip (7 araç, harf eşleşmesi)" >&2

exec npx -y @agentmemory/mcp@0.9.28
