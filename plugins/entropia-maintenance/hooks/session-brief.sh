#!/usr/bin/env bash
# Entropia SessionStart — kısa, repo'ya özgü doğrulama hatırlatması.
# Kapat: ENTROPIA_HOOKS=off
set -uo pipefail

if [ "${ENTROPIA_HOOKS:-on}" = "off" ]; then exit 0; fi
command -v python3 >/dev/null 2>&1 || exit 0
cat >/dev/null 2>&1 || true

read -r -d '' BRIEF <<'MSG' || true
Entropia oturum hatırlatması (proje hook'u):
- Handoff/özet/yerel branch BAYAT VARSAYILIR. Önce doğrula: git fetch && git log --oneline origin/main -6 && gh pr list --state all
- Sayısal otorite docs/generated/repository_facts.md (üretilmiş); CLAUDE.md §Current position elle yazılır, HEAD sha'sı yapısal olarak bayattır.
- Kod aramaya codemap (docs/CODEMAPS/) + codebase-memory-mcp ile başla; kör grep + tam dosya okuma pahalıdır.
- Proje skill'leri: entropia-canonical-rules, entropia-testing, entropia-regression-check, entropia-frontend-parity, ponytail-entropia.
- Proje ajanları: entropia-triage (teşhis), entropia-scoped-fix (dar diff), entropia-verifier (kapılar).
MSG

python3 -c '
import json, sys
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": sys.argv[1],
}}))' "$BRIEF"
exit 0
