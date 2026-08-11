<!-- doc-status: historical -->
> **SUPERSEDED — canlı devir belgesi `docs/ADIM40_LANDED_KICKOFF.md`'dir.**
> Bu belge **ADIM 39 kapanışında** yazıldı ve o anın kaydıdır; aşağıdaki *paste-ready resume
> prompt* artık **kullanılmamalıdır**. ADIM 40 görsel/E2E eksenine **dokunmadı** — RC §6.7'nin
> belge kalemlerini (**P1-B1/B2, P8-B1/B3**) kapattı; bu belgenin açık bıraktığı
> **P11-1 / P11-6b / P11-8** hâlâ **açıktır**. §3'ün iki görsel-baseline önkoşulu
> **geçerliliğini korur** — yeni baseline üretecek herkes onları okumalıdır.

# ADIM 39 landed — devir belgesi (RC §6.7 / P11-2)

**PR #665** · branch `test/rc-p11b2-visual-coverage` · base `ed83688` (ADIM 38).

---

## 1. Nerede duruyoruz

Görsel regresyon kapısı artık **23 rotanın 23'ünü** assert ediyor (önce 8). Runner'da
**iki kez, aynı commit'te 23/23**. Blocker sayısı **değişmedi (üç)**, §8 verdict
**BLOCKED**. **P11 KAPANMADI.**

## 2. Bu slice'ın bıraktığı REUSE çapaları (tam sembol adlarıyla)

| Çapa | Ne işe yarar |
|---|---|
| `frontend/e2e/utils/screenshotMatrix.ts::TARGET_PAGES` | **Rota listesinin tek kaynağı.** Dört tüketici: specs/10 (matris), specs/11 (**görsel kapı — bu slice bağladı**), specs/13 (axe), specs/20 (keyboard). Yeni rota buraya eklenir, dördü birden kapsar. |
| `frontend/e2e/specs/11-visual-regression.spec.ts` | 23 rotalık `toHaveScreenshot` döngüsü. **Elle liste YOK**, `mode: "serial"` YOK. |
| `frontend/e2e/specs/11-visual-regression.spec.ts-snapshots/<slug>-chromium-linux.png` | 23 baseline, adları **TARGET_PAGES slug'ı**. |
| `scripts/visual-baseline-platform-gate.sh` | ADIM 38'in kapısı; `ASSERTED_PLATFORMS="linux"`. Artık `OK: 23`. |
| `frontend/e2e/README.md` §R2-13 | **İki yazılı olmayan önkoşul artık burada yazılı** (§3). |
| `docs/implementation/v18_visual_deviations.md` | Adjudicated sapma defteri (A-06, D-1 imzalı) — v18 inceleme kapısının dayanağı. |

## 3. Bir sonraki kişinin BİLMEK ZORUNDA olduğu iki şey

**(a) Baseline'lar salt-seed stack'i tarif ETMİYOR.** `e2e.yml` görsel kapıyı
`npm test`'ten **sonra** koşar; kapının fotoğrafladığı sayfalar journey suite'inin
yarattığı varlıkları içerir. Salt-seed bir stack'te mevcut sekiz baseline'ın **dördü**
yalnız yükseklik yüzünden düşer (929↔900, 947↔900, 1411↔1396, 900↔1135). Yeniden
üretirken sırayı koru:

```sh
docker compose down -v && docker compose up -d --build
docker compose exec -T -e SEED_E2E_GOLDEN=1 -e SEED_ESP_TA=1 -e SEED_RATIONALE=1 \
  api python -m entropia.apps.seed
cd frontend/e2e && npm test && npm run screenshots:update
```

**(b) "Linux" ile "runner" aynı şey değil.** `mcr.microsoft.com/playwright:v1.55.1-noble`
23 sayfanın 22'sini `ubuntu-latest` ile birebir verdi; `analysis-lab` 6 px saptı
(konteyner 1496 / runner 1490 — runner iki denemede **byte-identical**, yani jitter değil,
sembol glifi font farkı). CI-dışı üretiyorsan bir-iki sayfanın reddedilmesini **bekle** ve
runner'ın kendi `test-results/**/<slug>-actual.png` dosyasını baseline'ın üstüne kopyala.
**Toleransı büyütme, maske icat etme, rotayı listeden çıkarma.**

## 4. Bu slice'ta BİLEREK yapılmayanlar

- **Görsel kusur düzeltilmedi.** Slice test slice'ıydı; bulunan kusurlar dondurulup
  **bildirildi** (F-2, F-4, F-07 sınıfı ham `btres_…`). Düzeltmek ayrı bir ürün slice'ı.
- **Maske eklenmedi.** Altı baseline oynak ULID/timestamp taşıyor; ölçüldü, %2'nin altında
  kalıyor. Maske eklemek yeni bir stabilizasyon deseni icat etmek olurdu.
- **`ready-check` için kalem açılmadı** — yerelde 946/947/950 salınıyor, runner'da üç
  koşunun üçünde de geçiyor. CI'da görünmeyen davranış için §6.7'ye kalem eklemek defteri
  şişirirdi; kanıt belgesine yazıldı.
- **F-5** görünüşe göre kapanmış (history satırı artık headline metrik gösteriyor) ama
  defter hâlâ açık listeliyor → **PO kararı**, agent kapatamaz.

## 5. Açık kalanlar (P11 KAPANMADI)

| Kalem | Neden açık |
|---|---|
| **P11-1** | `main`'de branch protection/ruleset YOK → kapılar **required status check değil**. **Repo ayarı = insan kararı**, agent yapamaz. |
| **P11-6b** | Tab-sırası sondası **Tab'a basmıyor** ve hiçbir rota onu kıramaz. Gerçek Tab yürüyüşü yeni bir modelleme kararı → ayrı PR. |
| **P11-8** | Lighthouse bağlı değil. |
| **A-08** | Ekran-okuyucu denetimi **yapılmadı**; defter BOŞ, dört kriter ☐, #514 kanıtsız kapalı. **Bu slice'ın hiçbir çıktısı A-08 değildir.** |

---

## 6. Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 40: RC §6.7 — sıradaki kalem

[[ ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ / PR DİSİPLİNİ
   bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — PR #665 merge olmuş OLMALI; olmadıysa DUR)

OTURUM BAŞLANGICI
  · git fetch && git log --oneline origin/main -6 && gh pr list --state all
  · docs/ADIM39_LANDED_KICKOFF.md (bu belge) → docs/STAGE2_HANDOFF.md §ADIM 39 →
    docs/PROJECT_HISTORY.md §ADIM 39 → RC raporu §6.7 tablosu + §6.7.7

DURUM
  · Görsel kapı 23/23 (P11-2 KAPANDI). P11-3b CEVAPLANDI.
  · Blocker sayısı ÜÇ, §8 verdict BLOCKED. "READY" YAZMA.

SIRADAKİ KALEM — BİRİNİ SEÇ, KULLANICIYA SOR:
  · P11-6b — tab sondası gerçek Tab yürüyüşü (yeni modelleme kararı: radio grupları,
    <select>, roving tabindex). ORTA iş.
  · P11-8 — Lighthouse kapısı. Yeni job + bütçe kararı.
  · P11-1 — AGENT İŞİ DEĞİL (repo ayarı). Kullanıcıya hatırlat, kendin yapma.
  · PR B — ItemParticipant adaptörü: ADR §16 insan kapısı gerektirir, o kapıdan
    geçmeden başlama.

GÖRSEL KAPIYA DOKUNACAKSAN — PAZARLIKSIZ
  · Rota listesini ELLE YAZMA: TARGET_PAGES türetir.
  · Baseline üretim sırası: down -v → up → seed → npm test → screenshots:update.
    (Salt-seed stack'te 4/8 düşer — bu bir hata değil, önkoşul.)
  · CI-dışı Linux'ta ürettiysen reddedilen sayfanın baseline'ını runner'ın
    test-results/**/<slug>-actual.png dosyasından al. TOLERANSI BÜYÜTME.
  · Yalnız -linux commit edilebilir (visual-baseline-platform-gate.sh).

KAPANIŞ
  · CLAUDE.md §Session CLOSING ritüelinin 6 maddesi
  · cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
  · docs PR'ı öncesi: git diff origin/main -- docs/ | grep '^-## ' → BOŞ olmalı
```
