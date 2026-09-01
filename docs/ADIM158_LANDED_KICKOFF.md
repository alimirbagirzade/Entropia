<!-- doc-status: current -->
# ADIM 158 landed — A-08 insan kabulünün muhasebesi: kanıt paketi üretildi, insan kanıtı EKLENMEDİ

> **Tek cümlede:** Bir ajan A-08'in insan kanıtını üretemez ve ÜRETMEDİ — bu slice
> kanıtın *yokluğunun* tarihli, eksiksiz muhasebesini çıkardı (46 rota oturumu + 20 akış,
> tek tek), ortamı denetçinin kendi Mac'inde yeniden doğrulayıp **AYAKTA bıraktı** ve
> verdict'i yeniden türetti: **BLOCKED** (1 blocker — yalnız A-08).

## Nerede duruyoruz (2026-09-01, taban `9c48b0da`)

- **#514 AÇIK**, `human-only`, yeniden açılıştan (2026-08-12) beri **sıfır etkinlik** —
  defterle ayrışma YOK (gh ile ölçüldü).
- Defter: **2/184** Section A hücresi (yalnız SR-2 rota 1, A-1+A-2) · **0/10** akış ·
  **0** bulgu · çıkış kriterleri **0/4** · **SR-1 hiç başlamadı** (makine + denetçi yok).
- **Kanıt paketi:** `docs/releases/evidence/2026-09-01/A08_acceptance_evidence_bundle.md`
  (+ stack transkripti + 3 precheck JSON). 0/46 rota tam · 1/46 kısmî · 0/20 akış.
- **Stack AYAKTA bırakıldı** (bilerek — script'in tasarımı: teardown açık insan komutu):
  web `http://127.0.0.1:18280`, Admin `e2e_admin`, compose projesi `entropia-a11y-audit`.
  İndirme: `scripts/a11y-audit-stack.sh down`.
- D-10 (1.4.3 karşılanmıyor, 45 düğüm) + D-11 (landmark kümesi üç) **imzalı sapma olarak
  aynen duruyor** — hiçbiri uygunluğa çevrilmedi; A-08 kapsamında imzalı sapma YOK.

## Bu slice'ın bıraktıkları (REUSE çapaları)

| Çapa | Ne işe yarar |
|---|---|
| `docs/releases/evidence/2026-09-01/A08_acceptance_evidence_bundle.md` | 46+20'nin tek tek muhasebesi; verdict şablonu — bir sonraki muhasebe bunu kopyalayıp tarihler |
| Defter §6.1d | Precheck ×3 tablosu + K-7'nin ÇİFT YÖNLÜ ilk-DOM yarışı (mekanizma: `components/Loading.tsx` `role="status"` render eder — mid-load yakalanan rota K-7 kümesinden ÇIKAR) |
| Defter §STATUS "Re-verified 2026-09-01" bloğu | #514 ↔ defter uzlaştırmasının dated deseni |
| `backend/tests/contract/test_a11y_audit_prep_contract.py` | Defter düzenlemelerinin yapısal kapısı — bu slice'ta 21/21 yeşil koştu |
| Stack komutları | `scripts/a11y-audit-stack.sh up` idempotent; `validate` yeniden koşulabilir; precheck: `cd frontend/e2e && E2E_BASE_URL=http://127.0.0.1:18280 npx playwright test specs/20-a11y-prechecks.spec.ts` (×2, soğuk atılır) |

## Ölçülen tuzaklar (yenileri)

1. **K-7 sayısı host-timing'e ÇİFT YÖNDE duyarlı** — ılık iki koşu arasında 5 rota oynadı
   (15/19/16). Yerleşik sayı İDDİA EDİLMEDİ; runner-class 21/23 (2026-08-12) korundu.
   K-7'ye yeni sayı yazacak kişi CI-class runner'da ×2 ılık koşsun.
2. **Çıplak worktree venv tuzağı bir kez daha:** `uv run pytest` → "Failed to spawn";
   önce `uv sync --all-extras`.
3. Bu Mac'te Docker daemon VAR (29.4.0) — §6.1a'nın container engeli bu makineye
   uygulanmaz; gelecek ortam-yenileme işleri yerelde yapılabilir.

## Sıradaki iş

1. **A-08 SR-2 devamı — İNSAN.** Stack ayakta; runbook §0 kartı: rota 1 `/`, hücre
   **A-3** (yeniden yazılmış soru: yapı YANILTIYOR mu), sonra A-4…A-8, sonra rota 2–23,
   sonra B-1…B-10. Oturum kaydını defter §0/§1/§5'e insan yazar.
2. **A-08 SR-1 zamanlaması — İNSAN.** Windows + NVDA makinesi ve denetçi ataması.
3. **Tavan takibi (koşullu):** 4. kusursuz Lighthouse main koşusu inince sıkıştırma
   slice'ı (tavanlar o PR'ın KENDİ CI artefaktından, yerelden ASLA).
4. Yeni imza/karar inerse: `docs/decisions/` kutusunu ADIM 90 üç-ölçüm kuralıyla doğrula.

---

## Paste-ready resume prompt

```
Entropia — ADIM 159. Session START protokolünü uygula: git fetch, git log --oneline
origin/main -6, gh pr list --state all (handoff STALE-BY-DEFAULT). Sonra oku:
docs/ADIM158_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md (son "## Next") →
docs/PROJECT_HISTORY.md §ADIM 158 (hedefli).

DURUM: İMZALI KOD KUYRUĞU BOŞ. A-08 (#514) TEK BLOCKER, human-only — ajan ilerletemez;
muhasebesi ve kanıt paketi docs/releases/evidence/2026-09-01/ altında, denetçi stack'i
büyük olasılıkla http://127.0.0.1:18280'de AYAKTA (değilse scripts/a11y-audit-stack.sh up).
Kalan hatlar: (2) tavan takibi KOŞULLU (4. kusursuz Lighthouse main koşusu); (3) yeni
imza/karar inmişse docs/decisions/ kutusunu ADIM 90 üç-ölçüm kuralıyla doğrula.
İş yoksa: durumu raporla ve dur; iş İCAT ETME. İnsan kanıtı ASLA uydurma — defter
hücrelerini yalnız kulaklık takan insan doldurur.

KURALLAR: ölçmediğini iddia etme; öncülü defterin KENDİSİNDE doğrula; yeşil exit code
kanıt değildir (exit code'u AYRI oku); alt küme pytest'te --no-cov (önce uv sync
--all-extras); vitest --no-file-parallelism; kapanış ritüeli ZORUNLU; kickoff'lardan
yalnız EN YÜKSEK numaralı current; self-merge bloklu.
```
