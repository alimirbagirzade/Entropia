#!/usr/bin/env bash
# Entropia PostToolUse — değişen TEK dosya üzerinde hızlı ruff kapısı + hatırlatmalar.
#
# YAN ETKİSİ YOKTUR: ruff yalnız HAZIR bir binary'den koşar. `uv run` bilerek
# kullanılmaz — worktree'de .venv yoksa onu yaratır ve paket kurar; bir
# PostToolUse hook'u bunu yapmamalı.
# Tam suite burada KOŞMAZ (pahalı); kapılar entropia-verifier ajanındadır.
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
print(ti.get("file_path") or "")
' 2>/dev/null)"

[ -n "$file" ] || exit 0
[ -f "$file" ] || exit 0

root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$root" ] || exit 0

emit_context() {
  python3 -c '
import json, sys
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": sys.argv[1],
}}))' "$1"
}

# --- backend Python: tek dosya ruff (hızlı, kapsam dar, yan etkisiz) ---
case "$file" in
  "$root"/backend/*.py)
    RUFF=""
    if [ -x "$root/backend/.venv/bin/ruff" ]; then
      RUFF="$root/backend/.venv/bin/ruff"
    elif command -v ruff >/dev/null 2>&1; then
      RUFF="$(command -v ruff)"
    fi
    # ruff kurulu değil (ör. deps'i kurulmamış worktree) → sessizce geç.
    if [ -n "$RUFF" ]; then
      check_out="$("$RUFF" check --force-exclude "$file" 2>&1)"; check_rc=$?
      fmt_out="$("$RUFF" format --check --force-exclude "$file" 2>&1)"; fmt_rc=$?
      if [ $check_rc -ne 0 ] || [ $fmt_rc -ne 0 ]; then
        {
          echo "ruff bu dosyada kırmızı — düzelt:"
          echo "  cd backend && uv run ruff format <file> && uv run ruff check --fix <file>"
          [ $check_rc -ne 0 ] && echo "$check_out"
          [ $fmt_rc -ne 0 ] && echo "$fmt_out"
        } >&2
        exit 2
      fi
    fi
    ;;
esac

# --- hatırlatmalar (bloklamaz, bağlam ekler) ---
case "$file" in
  */alembic/versions/*.py)
    emit_context "Yeni/değişen migration: kapanmadan önce ÜÇ kanıt zorunlu — (1) L1 FK insert-order proof her yeni create_* için, (2) alembic <n> up/down/up (LC_ALL=en_US.UTF-8, önce DROP SCHEMA public CASCADE; CREATE SCHEMA public;), (3) migration↔model kolon paritesi. Ayrıntı: entropia-testing skill'i."
    exit 0 ;;
  "$root"/frontend/src/lib/*)
    emit_context "lib/*.ts VERİ MANTIĞIDIR — presentation-only iş buraya dokunamaz. Route path / react-query key / OCC token (If-Match, expected_*_version, X-*-Version) / Idempotency-Key / SSE taksonomisi değişiyorsa bu iş artık presentation-only değildir: dur ve kullanıcıya söyle. Ayrıntı: entropia-frontend-parity skill'i."
    exit 0 ;;
  "$root"/frontend/src/app/nav.ts)
    emit_context "app/nav.ts: NAV ve ALL_NAV_ITEMS birebir kalır (presentation-only kuralı). Değişmesi gerekiyorsa kullanıcı onayı gerekir."
    exit 0 ;;
  "$root"/backend/src/entropia/shared/concurrency.py|"$root"/backend/src/entropia/shared/responses.py|"$root"/backend/src/entropia/shared/errors.py|"$root"/backend/src/entropia/application/idempotency.py)
    emit_context "ADJUDICATED alan değişti. Bu dosyalar O-02 (hata zarfı), O-12 (OCC dual-token), O-13 (Idempotency-Key) sözleşmelerini taşır; alan adları ve 409/retryable semantiği karara bağlanmıştır. Değişikliği entropia-canonical-rules skill'ine göre doğrula."
    exit 0 ;;
  */docs/PROJECT_HISTORY.md)
    emit_context "PROJECT_HISTORY.md değişti. Merge öncesi kayıt silme kontrolü ZORUNLU (üç kez oldu): git show <sha> -- docs/ | grep '^-## '  → çıktı boş olmalı. Ayrıntı: entropia-regression-check skill'i."
    exit 0 ;;
esac

exit 0
