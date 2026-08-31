<!-- doc-status: current -->
# ADIM 147 landed — kapı 23 rotanın 23'ünü de OTURUMSUZ puanlıyor, ve artık bunu söylüyor

## Nerede olduğumuz

Taban `origin/main` @ `5e766910` (ADIM 146). **İki dosya**:
`frontend/e2e/specs/21-lighthouse.spec.ts` + `frontend/e2e/lighthouse-baseline.json`.
**Ürün kodunda SIFIR SATIR** · migration yok · `ENGINE_VERSION` değişmedi · OpenAPI
değişmedi · **`floors`/`armed`/`policy` EL DEĞMEDİ** (JSON diff ile kanıtlı) → kapı
davranışı **bayt bayt aynı**. **Blocker DEĞİŞMEDİ (1 — yalnız A-08) → BLOCKED.**

## Bu slice'ın bıraktığı çapalar

`frontend/e2e/specs/21-lighthouse.spec.ts`:
- `SESSION_TOKEN_KEY` — `frontend/src/lib/session.ts`'in `entropia.sessionToken` anahtarı
- `lighthouseTabSeesSession()` — Lighthouse'un açtığı sekmenin **aynısını** açar
  (`connectOverCDP` → `contexts()[0].newPage()`), oturumu görüp görmediğini döner
- `sessionCarried: boolean | null` — `null` = probe hiç koşmadı (**`false`'tan AYRI**)
- `conditions.session_carried_into_lighthouse_tab` — rapora yazılan boolean

`frontend/e2e/lighthouse-baseline.json`:
- `provenance.session_state_2026_08_31` — tavanların hangi dünyada donduğu
- `provenance.conditions` — **`"Admin session"` ifadesi düzeltildi** (karşı-olgusaldı)

## ASIL BULGU

**Taşımıyor.** Zincir altı halkada, kurulu paketlerin kaynağından kanıtlandı:
`browser.newContext()` ayrı bir context → `lighthouse(url,{port},cfg)` **`page`'siz**
çağrılıyor → `navigation-runner.js:278-282` `puppeteer.connect(...).newPage()` yolunu
alıyor → `cdp/Browser.js:204` `#defaultContext`'e yolluyor → `:76` + `:211-213`
`Target.createTarget`'ı **`browserContextId` OLMADAN** gönderiyor → o partisyon token'ı
**`null`** okuyor.

**Kusur ÜRÜNDE değil, HARNESS'ta.** Kapı, `errors-in-console` dahil, **oturumsuz kabuğu**
puanlıyor — ve tavanlar (ADIM 145'in `seo` 82→100 sıkıştırması dahil) o dünyada donduruldu.

**Ölçüm uygulamadan BAĞIMSIZ kuruldu** (sentetik origin, Entropia devrede değil) — yerel
stack'i sürmeyi iki oturum boyunca yenen sorun böylece tamamen atlandı.

## ADIM 146'NIN BİR ÇIKARIMI DÜZELTİLDİ

*"23 farklı LCP → 'hepsi oturumsuz kabuk' okuması desteklenmiyor"* — **gözlem doğru,
çıkarım fazlaydı**: anonim → `/login` yönlendirmesi yok, yani 23 **farklı** oturumsuz
kabuk 23 farklı LCP üretir. ADIM 146'nın kaydı donmuş, **değiştirilmedi**.

## DÜRÜST SINIR

- **#677 KAPATILMADI**, `errors-in-console` **DÜZELTİLMEDİ**, **harness DÜZELTİLMEDİ**.
- **İDDİA EDİLMEYEN:** uygulamanın oturum **açıkken** konsol hatası olmadığı — ÖLÇÜLMEDİ.
- Tavanlar, `armed`, `do_not_tighten`, `policy`: **el değmedi**.
- Spec yerelde uçtan uca **koşulmadı** (seeded stack + Lighthouse ister) → sevk edilen
  probe'un canlı kanıtı **PR'ın kendi CI koşusu**.
- Backend kapıları koşulmadı (sıfır satır) → otorite CI.

## Paste-ready resume prompt

```
ENTROPIA — ÖNCE ADIM 147'NİN PR'ININ DURUMUNU ÖLÇ.

DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -3 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  gh issue view 677 --json state && gh issue view 514 --json state
  # #703'un imzasi #886'da: agacta mi? (main'de 11 kutu BOS idi)
  grep -c 'Imza:\|İmza:' docs/decisions/closure_i703_instrument_mapping_writer_2026-08-30.md   # 0 = imza agacta degil

DURUM: ADIM 147 ÖLÇTÜ — Lighthouse'un sekmesi oturumu TAŞIMIYOR; kapı 23 rotayı
OTURUMSUZ puanlıyor. Kusur HARNESS'ta. DÜZELTİLMEDİ; her koşu artık
`conditions.session_carried_into_lighthouse_tab` ile hangi dünyada olduğunu söylüyor.

SIRADAKİ İŞ — ürün sahibinin bu oturumda seçtiği sıra:
  (a) CLS `panel-management` — gerçek layout işi, tavanı 98'de BIRAK (do_not_tighten).
  (b) #703 uygulaması — DÖRT karar da #886'da İMZALI ((b) linkten türet + (b2)
      fail-closed düz + harness üretim şekline çekilsin + RD-09.c4 bağlıdır).
      #886 MERGE OLMADAN BAŞLAMA: imza otoritesi o belgede. Dördü AYNI slice'ta;
      test_readiness_research_data'nın iki testi KASITLI güncellenecek (bedel NC-3'te
      ölçülü). RD-09.c4 `partial` KALIR, tavanlar el değmez.
  (c) Harness düzeltmesi (ADIM 147'nin açık bıraktığı) — chromium.launchPersistentContext
      ile Playwright'ın sayfasını DEFAULT context'e almak. 23 skorun HEPSİNİ oynatır ve
      tavanların CI'dan YENİDEN DONDURULMASINI zorunlu kılar (asla yerel koşudan).
      Bu bir SLICE'tır, bir düzeltme satırı değil.

DİĞER AÇIK KALEMLER: #854 (9 kutu BOŞ) · #534 (CLOSED ama kapanış yorumu YOK, 4 kutu
BOŞ) · #547 (0 yorum) · #582 (ÖNCÜLÜ BAYAT) · #514 A-08 (TEK BLOCKER, human-only).

KURALLAR: ölçmediğini iddia etme; tavanı ASLA yerel koşudan alma; yeşil exit code kanıt
değildir; e2e'nin gerçek tip kapısı `npx tsc --noEmit -p e2e/tsconfig.json` (npm run
typecheck e2e'yi KAPSAMAZ); vitest'i --no-file-parallelism ile koş; kapanış ritüeli
ZORUNLU; kickoff'lardan yalnız EN YÜKSEK numaralı olan `current` olabilir.
```
