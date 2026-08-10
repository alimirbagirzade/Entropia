#!/usr/bin/env bash
# Entropia PreToolUse notu — frontend/src altında .ts/.tsx yazılırken, vendor'lanan
# iki Vercel skill'inin HANGİ kural ailesinin bu projede geçerli olduğunu söyler.
# Skill'ler kendilerini "React and Next.js" diye tanıtır; Entropia Vite SPA'dır,
# yani kuralların yarısı burada geçersizdir. Sınırın kendisi bu hook'un işi DEĞİL —
# onu entropia-frontend-parity skill'i taşır, buradan sadece ona işaret edilir.
# ASLA bloklamaz. Kapat: ENTROPIA_HOOKS=off
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

case "$file" in
  */frontend/src/*.ts|*/frontend/src/*.tsx|frontend/src/*.ts|frontend/src/*.tsx) ;;
  *) exit 0 ;;
esac

python3 -c '
import json
note = (
    "[vendor React kurallari] Bu dosya frontend/src altinda. Kurulu iki Vercel "
    "skill'"'"'i kendini \"React and Next.js\" diye tanitir; Entropia React 18.3 + Vite + "
    "react-query SPA'"'"'dir, Next.js DEGILDIR.\n"
    "  - vercel-composition-patterns: architecture-* / state-* / patterns-* GECERLI. "
    "react19-* ATLA (React 18.3).\n"
    "  - vercel-react-best-practices: yalniz rerender-* / rendering-* / js-* / advanced-* "
    "GECERLI. async-* / bundle-* / server-* / client-swr-* Next.js + RSC ozeldir, "
    "bu projede GECERSIZ.\n"
    "Sinir (presentation-only, ellenmeyenler listesi): entropia-frontend-parity skill'"'"'ini oku."
)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": note}}))
'
exit 0
