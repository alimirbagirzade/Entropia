#!/usr/bin/env bash
# Entropia SessionStart — doğrulama hatırlatması + YÖNLENDİRME TABLOSU.
#
# Tablo neden burada: bu depoda bir düzine skill, üç ajan ve dört komut var ve hepsi
# kurulum istemeden yüklenir — ama "yüklü olmak" ile "doğru anda kullanılmak" ayrı
# şeylerdir. Skill'ler kendi açıklamalarıyla kendiliğinden tetiklenir; tablo o
# tetiklemenin YEDEĞİdir ve asıl işi SIRAYI söylemektir (triage → scoped-fix →
# verifier; sast-analysis → sast-*; kanonik kural → düzeltme). Bir prompt geldiğinde
# hangi aracın hangi sırayla kullanılacağı tahmin edilmek zorunda kalmasın diye.
#
# Kısa tut: bu metin HER oturumda bağlama girer.
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

YÖNLENDİRME — prompt şuna benziyorsa, şunu kullan:
- "şu bug / CI kırmızı / bu nerede yapılıyor"  -> ajan entropia-triage (KOD YAZMADAN teşhis), sonra entropia-scoped-fix, sonra entropia-verifier. Sıra budur.
- "testler geçiyor mu / commit-PR öncesi"      -> /verify ya da ajan entropia-verifier. Sayı uydurma, exit code'u ayrı oku.
- oturum başı / "neredeyiz"                    -> /session-start   |   merge öncesi -> /merge-check   |   slice kapanışı -> /close-session
- endpoint, hata zarfı, OCC, Idempotency-Key, soft-delete, upload -> skill entropia-canonical-rules (O-02/O-12/O-13/O-30/K-06/K-07 PAZARLIKSIZ).
- sayfa, stil, etiket, mockup, kırık frontend testi -> skill entropia-frontend-parity (presentation-only sınırı).
- test yazma, coverage, migration               -> skill entropia-testing.
- docs değişikliği, "landed mi", PR merge       -> skill entropia-regression-check.
- "en az kodla nasıl", fazla mühendislik şüphesi-> skill ponytail-entropia   |   repo geneli denetim -> ponytail-audit-entropia.
- PR kırmızı / "yeşile getir"                   -> skill pr-drive-to-green.
- güvenlik taraması (IDOR, auth, SQLi, RCE, upload, path, sır, iş mantığı)
                                                -> ÖNCE skill sast-analysis (sast/architecture.md'yi yazar), SONRA ilgili sast-*, EN SON sast-report.
                                                   Bulgu bir DÜZELTME EMRİ DEĞİLDİR: uygulamadan önce entropia-canonical-rules ile doğrula.
- sembol/çağrı zinciri arama                    -> codebase-memory-mcp (taze container'da indeks BOŞ: önce index_repository).
- geçmiş slice ayrıntısı                        -> agentmemory (boşsa: node scripts/memory_index.mjs --sync). Kayıt otorite DEĞİL, işaret ettiği PROJECT_HISTORY.md bölümü otorite.
- React/frontend kuralı                         -> vercel-* skill'leri; hangi kural ailesi geçerli, vendor-react-rules hook'u söyler (Next.js kuralları GEÇERSİZ).
- yeni bir dış skill/plugin önerisi geldi        -> docs/EXTERNAL_SKILLS_REGISTRY.md'ye BAK. 17 depo karara bağlandı; yeniden tartışma, satır yoksa ekle.
MSG

python3 -c '
import json, sys
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": sys.argv[1],
}}))' "$BRIEF"
exit 0
