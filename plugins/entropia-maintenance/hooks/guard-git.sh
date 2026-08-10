#!/usr/bin/env bash
# Entropia PreToolUse (Bash) — tehlikeli git/gh işlemlerini OTOMATİK yakalar.
# Üç kapı: (1) docs kayıt silen commit, (2) self-merge, (3) main'e force push.
# Kapat: ENTROPIA_HOOKS=off
set -uo pipefail

if [ "${ENTROPIA_HOOKS:-on}" = "off" ]; then exit 0; fi
command -v python3 >/dev/null 2>&1 || exit 0

cmd="$(python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(""); raise SystemExit
print((d.get("tool_input") or {}).get("command") or "")
' 2>/dev/null)"

[ -n "$cmd" ] || exit 0
root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$root" ] || exit 0

# --- 1. docs kayıt silen commit (üç kez oldu: #590 211 satır, #604 194 satır) ---
case "$cmd" in
  *"git commit"*)
    case "$cmd" in *--dry-run*) exit 0 ;; esac
    removed="$(cd "$root" && git diff --cached -- docs/ 2>/dev/null | grep '^-## ' || true)"
    if [ -n "$removed" ]; then
      {
        echo "BLOCKED — bu commit docs/ altından KAYIT SİLİYOR."
        echo
        echo "Silinen başlıklar:"
        printf '%s\n' "$removed" | head -20
        echo
        echo "Bu regresyon üç kez oldu (#590: 211 satır, #604: 194 satır) ve hiçbir CI"
        echo "kapısı docs/ okumaz. Neredeyse her zaman nedeni BAYAT BASE'dir."
        echo
        echo "Yap:  git fetch && git rebase origin/main   (sonra kaydı geri koy)"
        echo "Doğrula:  git diff --cached -- docs/ | grep '^-## '   → boş olmalı"
        echo "Silme gerçekten kasıtlıysa kullanıcıdan açık onay al."
      } >&2
      exit 2
    fi
    ;;
esac

# --- 2. self-merge (repo kuralı: merge yetkisi insandadır) ---
case "$cmd" in
  *"gh pr merge"*)
    {
      echo "BLOCKED — self-merge bu repoda kapalıdır; merge'ü KULLANICI yapar."
      echo
      echo "Merge öncesi beş kapı için: /entropia-maintenance:merge-check <PR>"
      echo "  1 docs kayıt silme  2 base tazeliği  3 drift guard'ları"
      echo "  4 CI gerçekten koştu mu (0-job'lı 'yeşil' tuzağı)  5 iddia kanıtı"
      echo
      echo "Kapılar yeşilse kullanıcıya söyle, merge'ü o yapsın."
    } >&2
    exit 2
    ;;
esac

# --- 3. main / shared branch'e force push ---
case "$cmd" in
  *"git push"*)
    case "$cmd" in
      *--force-with-lease*) : ;;   # görece güvenli, yine de main'e izin verme
    esac
    case "$cmd" in
      *--force*|*" -f "*|*" -f")
        case "$cmd" in
          *main*|*master*|*origin\ HEAD*)
            {
              echo "BLOCKED — main/shared branch'e force push."
              echo "Repo kuralı: 'Never force push to main or shared branches.'"
              echo "Feature branch'e force push gerekiyorsa branch adını açıkça yaz."
            } >&2
            exit 2
            ;;
        esac
        ;;
    esac
    ;;
esac

exit 0
