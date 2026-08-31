<!-- doc-status: current -->
# ADIM 148 landed — panel-management'in CLS'i kaynağında düzeltildi; ve kapı onu koruyamıyor

## Nerede olduğumuz

Taban `origin/main` @ `a5595f07` (ADIM 147). Yazıldığı taban `5e766910` (ADIM 146) idi;
ADIM 147 (PR #887) bu PR sıra beklerken indi ve dal onun üzerine **REBASE edildi** —
*"Update branch"* düğmesi KULLANILMADI (ADIM 61: sunucu tarafı merge kayıt düşürür).
Dört çakışmanın dördü de belge/JSON'du ve **iki taraf da korunarak** çözüldü; kod
dosyaları temiz birleşti. `PROJECT_HISTORY.md` başlık sayısı 161 → 162 (yalnız ADIM 148
eklendi, hiçbir kayıt düşmedi). Dört dosya: `frontend/src/styles/global.css` ·
`frontend/src/pages/PanelManagement.tsx` · `frontend/src/test/panelManagement.test.tsx` ·
`frontend/e2e/lighthouse-baseline.json` (yalnız `provenance` prozası) + üretilmiş artefaktlar.
**Backend'de SIFIR SATIR** · migration yok · `ENGINE_VERSION` değişmedi · OpenAPI değişmedi ·
**`floors`/`armed`/`policy` EL DEĞMEDİ**. **Blocker DEĞİŞMEDİ (1 — yalnız A-08) → BLOCKED.**

## Bu slice'ın bıraktığı çapalar

- `global.css` → `.panel-card-async { min-height: 244px }` — **ölçülmüş** sayı (loading 166px,
  settled 244px), gerekçesi kuralın üstündeki yorumda
- `PanelManagement.tsx` → üç kartın **yalnız loading dalı** o sınıfla sarılı
- `panelManagement.test.tsx` → `"reserves each async panel card's height while its query is in
  flight"` — **kapının koruyamadığı** şeyin tek muhafızı
- `lighthouse-baseline.json` → `provenance.cls_fixed_2026_08_31`

## ASIL BULGU — KAPI BU DÜZELTMEYİ KORUYAMIYOR

Tavan `do_not_tighten` gereği **98'de kalıyor**. Düzeltme geri alınırsa CLS 0.09'a döner,
performance yine **98** olur ve **Lighthouse kapısı YEŞİL kalır**. Muhafız bir tercih değil,
**zorunluluk**. Negatif kontrol: sarmalayıcı sınıfı düşünce **tam 1 test kırmızı**, 11 yeşil.

## ÖLÇÜM ZİNCİRİ (üç kez yanlış dünya kuruldu, üçünde de ölçüm söyledi)

0 ms stub → CLS 0 (değişken **gecikme**) → 200/600 ms → iki rota da **birebir aynı** sayı
(rota hiç render olmuyor; `layout-shifts` düğümü **AUTH-02 boot gate**'ini gösterdi, stub
`/meta`'ya 401 dönüyordu) → `/meta` **ve** `/health/live` 200 (CI'ın şekli) → **reprodüksiyon
TAM**: yerel 0.0898/0.0361 ↔ CI 0.085/0.035. Ara adımda banner açıkken **oran doğru, mutlak
değer yanlıştı** — *doğru oran, doğru ölçüm demek değildir*.

**Suçlu:** `main#main-content > section.card.panel-card[aria-labelledby="actors-h"]`
(System actors), skor 0.0898 = CLS'in tamamı. **Sonuç:** 0.0898 → **0.0000516**, audit skoru
0.92 → **1**; dokunulmamış kontrol rotası `create-package` **0.0361 → 0.0358** (değişmedi).

## DÜRÜST SINIR

- **#677 KAPATILMADI** — `errors-in-console` (23/23) el değmedi.
- **TAVAN SIKIŞTIRILMADI ve sıkıştırılmamalı** — sonraki koşu 100 medyanlarsa
  `lighthouse-baseline.tightened.json` yükseltmeyi **önerecek**; öneri **reddedilir**.
- **İddia EDİLMEYEN:** oturum açık rotanın shift'i olmadığı. Ölçüm oturumsuz kabukta
  (ADIM 147). `min-height` sıçramayı **küçültür**, sildiğini iddia etmez.
- Yerel Lighthouse sayıları **teşhis**, tavan değil (runner sınıfı farklı).
- Backend kapıları koşulmadı (sıfır satır) → otorite CI.

## Paste-ready resume prompt

```
ENTROPIA — ÖNCE AÇIK PR'LARIN DURUMUNU ÖLÇ.

DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -3 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  gh issue view 677 --json state && gh issue view 514 --json state
  grep -c 'Imza:\|İmza:' docs/decisions/closure_i703_instrument_mapping_writer_2026-08-30.md
  # 0 = #703'un imzasi (PR #886) agacta DEGIL -> #703 kod slice'ina BASLAMA

DURUM: bu oturumda ÜÇ dal açıldı — #886 (#703'un dört imzası, docs-only, KULLANICININ),
ADIM 147 / PR #887 (Lighthouse'un sekmesi oturumu TAŞIMIYOR — ölçüm), ADIM 148 (bu slice:
panel-management CLS'i kaynağında düzeltildi). Üçü de merge bekliyor olabilir.

SIRADAKİ İŞ:
  (a) #703 uygulaması (KOD) — DÖRT karar da #886'da İMZALI: (b) linkten türet · (b2)
      fail-closed düz · §2 = A harness üretim şekline çekilsin · §3 = A RD-09.c4 bağlıdır.
      #886 MERGE OLMADAN BAŞLAMA. Dördü AYNI slice'ta; test_readiness_research_data'nın
      iki testi KASITLI güncellenecek (bedel ADIM 140 NC-3'te ölçülü). RD-09.c4 `partial`
      KALIR, kabul borcu tavanları EL DEĞMEZ. PRE-1 (üretim sayımı) ilk deploy'da.
  (b) Lighthouse harness düzeltmesi (ADIM 147'nin açık bıraktığı) —
      chromium.launchPersistentContext ile Playwright'ın sayfasını DEFAULT context'e almak.
      23 skorun HEPSİNİ oynatır ve tavanların CI'dan YENİDEN DONDURULMASINI zorunlu kılar
      (asla yerel koşudan). Bir SLICE'tır, bir satır değil.
  (c) errors-in-console (23/23) — ADIM 147 dünyayı belirledi; düzeltme (b)'ye bağlı olabilir.

DİĞER AÇIK KALEMLER: #854 (9 kutu BOŞ) · #534 (CLOSED ama kapanış yorumu YOK, 4 kutu BOŞ) ·
#547 (0 yorum) · #582 (ÖNCÜLÜ BAYAT) · #514 A-08 (TEK BLOCKER, human-only).

KURALLAR: tavanı ASLA yerel koşudan alma; do_not_tighten YÜRÜRLÜKTE (panel-management 98);
yeşil exit code kanıt değildir; e2e'nin gerçek tip kapısı `npx tsc --noEmit -p
e2e/tsconfig.json`; vitest'i --no-file-parallelism ile koş; test ekleyen slice üretilmiş
olguları tazelemeli (backend/.venv gerekir); kapanış ritüeli ZORUNLU; kickoff'lardan yalnız
EN YÜKSEK numaralı olan `current` olabilir.
```
