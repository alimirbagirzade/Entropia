#!/usr/bin/env bash
# Entropia PreToolUse guard — üretilmiş dosyaların elle düzenlenmesini engeller.
# Kapat: ENTROPIA_HOOKS=off
set -uo pipefail

if [ "${ENTROPIA_HOOKS:-on}" = "off" ]; then exit 0; fi
command -v python3 >/dev/null 2>&1 || exit 0

file="$(python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(""); raise SystemExit
ti = d.get("tool_input") or {}
print(ti.get("file_path") or ti.get("notebook_path") or "")
' 2>/dev/null)"

[ -n "$file" ] || exit 0

case "$file" in
  */docs/openapi.json)
    cat >&2 <<'MSG'
BLOCKED — docs/openapi.json ÜRETİLMİŞ bir dosyadır, elle düzenlenmez.

Şemayı değiştirmek için kaynağı düzelt (route/response modeli), sonra:
    make openapi
Drift kapısı (CI'da bloklayıcı):
    cd backend && uv run python -m entropia.apps.api.openapi_export --check
MSG
    exit 2 ;;
  */docs/generated/repository_facts.md)
    cat >&2 <<'MSG'
BLOCKED — docs/generated/repository_facts.md ÜRETİLMİŞ sayısal otoritedir.

Elle düzenleme; üreticiyi koştur:
    cd backend && uv run python ../scripts/generate_repository_facts.py --root ..
Drift kapısı (CI'da bloklayıcı): aynı komut + --check
MSG
    exit 2 ;;
  */docs/generated/*)
    cat >&2 <<'MSG'
BLOCKED — docs/generated/ altındaki dosyalar üretilmiştir, elle düzenlenmez.
Üreticiyi bul ve onu koştur (scripts/generate_*.py).
MSG
    exit 2 ;;
esac

exit 0
