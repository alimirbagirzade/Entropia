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
#
# NEDEN DÜZ BİR `grep '^-## '` DEĞİL (ADIM 111). Eski hâli tüm `docs/` diff'inde
# kaldırılmış her `## ` satırını kayıt silme sayıyordu. Bu, kapıyı her kabul borcu
# partisinde YANLIŞ POZİTİFE düşürüyordu: üretilmiş defterlerin bölüm başlıkları
# SAYI TAŞIR (`## Class B (23)`, `## Partial criteria (55)`) ve borç azaldığında o
# başlık kaldırılıp yerine küçüğü eklenir. Ölçüldü — merge edilmiş #821 (ADIM 107)
# ve #826 (ADIM 110) birebir aynı şekli taşıyor. Her partide çalan bir alarm,
# insanı onu susturmaya alıştırır; asıl risk budur.
#
# Yeni kural: bir başlık ancak KÖKÜ (sondaki `(N)` sayacı atılmış hâli) AYNI
# DOSYADA eklenen başlıkların kökleri arasında YOKSA silinmiş sayılır.
#   `## Class B (23)` -> `## Class B (21)`   kök aynı   -> DEĞİŞİKLİK, geçer
#   `## ADIM 92 — foo` -> (yok)              kök yok    -> SİLME, bloklar
#   `## ADIM 92` -> `## ADIM 93`             kök farklı -> SİLME, bloklar
#                                            (ADIM 61: başlık yeniden adlandırma
#                                             kayıt silme gibi görünür, öyle KALSIN)
# Karşılaştırma DOSYA BAŞINADIR: A dosyasından silinip B dosyasına eklenen bir
# başlık hâlâ bloklanır. Path allowlist'i (`docs/generated/*` gibi) bilerek
# SEÇİLMEDİ — yeni bir üretilmiş dosya her seferinde kod değişikliği isterdi ve o
# dosyaları GERÇEK silmelere karşı da körleştirirdi.
case "$cmd" in
  *"git commit"*)
    case "$cmd" in *--dry-run*) exit 0 ;; esac
    removed="$(cd "$root" && git diff --cached -- docs/ 2>/dev/null | python3 -c '
import re, sys

# path -> ([kaldirilan basliklar], [eklenen basliklar])
files, cur, prev_minus = {}, None, None
for line in sys.stdin.read().splitlines():
    if line.startswith("--- "):
        prev_minus = line[4:].strip()
        continue
    if line.startswith("+++ "):
        new = line[4:].strip()
        # Tamamen silinen bir dosyada `+++ /dev/null` gelir; yolu `---` tarafindan al.
        path = prev_minus if new == "/dev/null" else new
        if path.startswith(("a/", "b/")):
            path = path[2:]
        cur = path
        files.setdefault(cur, ([], []))
        continue
    if cur is None:
        continue
    if line.startswith("-## "):
        files[cur][0].append(line[1:])
    elif line.startswith("+## "):
        files[cur][1].append(line[1:])

def stem(h):
    """Sondaki `(N)` sayacini at — sayi tasiyan uretilmis basliklarin kimligi."""
    return re.sub(r"\s*\(\d+\)\s*$", "", h).strip()

for path, (gone, added) in files.items():
    added_stems = {stem(h) for h in added}
    for h in gone:
        if stem(h) not in added_stems:
            print(path + ": " + h)
' 2>/dev/null || true)"
    if [ -n "$removed" ]; then
      {
        echo "BLOCKED — bu commit docs/ altından KAYIT SİLİYOR."
        echo
        echo "Silinen başlıklar (dosya: başlık):"
        printf '%s\n' "$removed" | head -20
        echo
        echo "Bu regresyon üç kez oldu (#590: 211 satır, #604: 194 satır) ve hiçbir CI"
        echo "kapısı docs/ okumaz. Neredeyse her zaman nedeni BAYAT BASE'dir."
        echo
        echo "NOT: bu kapı artık yalnız GERÇEK silmeyi yakalar — aynı dosyada kökü"
        echo "korunarak sayısı değişen bir başlık (ör. '## Class B (23)' -> '(21)')"
        echo "DEĞİŞİKLİKTİR ve geçer. Yukarıdakiler o türden değil."
        echo
        echo "Yap:  git fetch && git rebase origin/main   (sonra kaydı geri koy)"
        echo "Doğrula:  git diff --cached -- docs/PROJECT_HISTORY.md | grep '^-## '   → boş olmalı"
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
