<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM88_LANDED_KICKOFF.md`'dir.**
> Bu belge yazıldığı andaki durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat
> olabilir. Sayısal gerçekler için otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (üretilmiş).
# ADIM 87 LANDED — kabul borcu batch 13 (doc 18 frontend) · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 87. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Kapanış yazılırken main **`7f331c7`** (ADIM 83 = #781 son kayıt; **#780 açık ve `ADIM 84`
  adını taşıyor** → bu slice **85**). **Ürün kodu değişmedi**: migration yok, OpenAPI
  değişmedi, `ENGINE_VERSION` değişmedi, `SHARED_ALLOCATION_STATUS` = `future_dev`.
  Diff `backend/src` ve `frontend/src/pages` altında **boş**; tek kod dosyası
  `frontend/src/test/analysisLab.test.tsx` (+1 vitest case).
- **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- Kabul borcu tavanı **yeniden donduruldu**: `partial` **85**, `uncovered` **8**,
  `debt_class` **A=1 · B=54 · C=6 · D=32**, `total_criteria` **383** (TABAN).
  Clause düzlemi: `covered` **1029**, `uncovered` **98**.
  **Bu sayıları buradan alma** — `docs/audit/acceptance_coverage_baseline.json` `.ceilings`
  otoritedir ve senden önce başka bir batch inmiş olabilir.
- **DOC 18 TAMAMEN KAPANDI (18 covered / 0 partial / 0 uncovered).** Doc 03 ve doc 07 daha
  önce bitmişti. Üç belge artık sıfır açık kriter taşıyor.

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam dosya/sembol adlarıyla)

- `frontend/src/test/analysisLab.test.tsx`
  - `> Analysis Lab page > keeps the typed directive text in the compose box after the 422
    rejection` — **reddedilen bir mutation'ın UI durumunu ölçmenin deseni**. Üç assertion
    birlikte çalışır: (a) `role="alert"` zarfı **reddin gerçekleştiğini** kanıtlar,
    (b) giden gövdenin `text`'i **submit'in gerçekten çıktığını** kanıtlar, (c) textarea
    değeri clause'un kendisidir. (a) ve (b) olmadan (c) **vacuous geçer**.
  - `apiErrorRoute(422, "MESSAGE_TEXT_REQUIRED", …)` — `stubApi` üzerinden kanonik hata
    zarfını sürmenin yolu (`src/test/helpers/apiStub.ts`); `mutationErrorText` çıktısı
    `"<CODE>: <message>"` biçimindedir, alert'i o biçimle assert et.

- **`U+001C` uyaranı** — sevk edilen istemcinin boş-metin kapısını **geçen**, komutunkinin
  **geçmediği** tek karakter ailesi (`U+001C`–`U+001F`). Doc 18 §15'in 422'sini frontend'de
  kurmanın **tek dürüst yolu** budur; yeni bir "reddedilen submit" testi yazarken bunu
  kopyala, boş string + stub'lanmış 422 **yazma** (üretimin üretemeyeceği dünya).

## Ölçülmüş kısıtlar — bunları yeniden keşfetme

1. **`Send as Directive` / `Send Message` düğmeleri `composeText.trim().length === 0` iken
   `disabled`** ve `sendDirective`/`sendMessage` aynı koşulda **erken döner**. Yani
   whitespace-only bir gövde **sunucuya hiç ulaşmaz**; "boş metin gönder" testi hiçbir kod
   yolu koşturmaz ve negatif kontrolden **geçmez**.
2. **Compose kutusunu YALNIZ `onSuccess` temizler**
   (`pages/AnalysisLab.tsx::LabConversationPanel`). Bu, `AL-06.c3`'ün tüm mekanizmasıdır;
   `onSettled`'a taşımak clause'u kırar. Yeni bir compose yüzeyi eklerken aynı deseni kullan.
3. **`docs/audit/acceptance_semantic_traceability.md` `--check` kapısının KAPSAMINDA DEĞİL.**
   ADIM 42 dönemi sayılarını (`234/126`) aylarca sessizce taşıdı. Kabul defterine dokunan her
   parti `--write-report` **ve** `--write-ledger` koşmalı; `generate_repository_facts.py
   --check` bu dosyayı **görmez**.
4. **Test ekleyen slice `repository_facts`'i tazelemek ZORUNDA** — `frontend_unit_test_call_sites`
   `it(` çağrılarını sayar (**724 → 725**), ve `--check` bloklayıcıdır.

## Sıradaki iş için işaretler — ÖLÇEREK doğrula, buna güvenme

- **`HAT B` / `C3` ŞU AN ÇAKIŞMALI.** `execution`/`domain/backtest/participant.py` adaptörünü
  **iki açık PR** birden sürüyor: **#777** ve **#782**. Bu satıra başlamadan önce
  `list_pull_requests(state=open)` koş ve hangisinin kazandığına bak; ADIM 87 bu yüzden
  `HAT B`'ye **hiç dokunmadı**.
- **Kabul borcu — kalan en kalın belgeler.** `--report`'un *Coverage by document* tablosundan
  **ölç** (bu freeze'de: doc 02 `8 partial`, doc 05 `8 partial`, doc 17 `7 partial`, doc 12
  `6 partial`, doc 10 `6 partial`). **Doc 03, 07 ve 18 bitti** — oralarda testin
  kapatabileceği satır kalmadı.
- **Parti seçmeden ÖNCE ÖLÇ.** Defterde **dokuz** yanlışlanamaz bulgu (`TL-11.c3`, `TL-16`,
  `TL-01.c4`, `RD-01.c4`, `RD-05.c5`, `RD-11.c2`, `RD-13.c4`, `PC-02.c2`, `PC-20.c3`) ve
  **dört** aynı şekilli adjudication kalemi var. Bir kriterin adlandırdığı davranış
  `backend/src`/`frontend/src`'te sevk edilmemişse **sınıfı yanlıştır** ve hiçbir test onu
  kapatamaz. **Yeniden sınıflandırma bir tavanı YÜKSELTİR → adjudication'dır, test
  slice'ının kararı değil.**

## Çalışma yöntemi (bu partide işe yarayan sıra)

1. `git fetch` → `origin/main` log → `PROJECT_HISTORY.md` son `## ADIM` → **canlı kickoff'u
   adıyla buldur** (`doc-status: current` grep'i) → `acceptance_coverage_baseline.json`
   `.ceilings`'i **dosyadan oku**.
2. `list_pull_requests(state=open)` → dokunacağın dosyaya dokunan açık PR var mı. **Kabul
   defteri seri bir kaynaktır**; paralel batch varsa ikinci inen rebase edip yeniden dondurur.
3. Clause'u seçmeden önce: *bu kusur altında mevcut testler yeşil mi kalıyor?* Kalıyorsa
   yeni assertion **başka bir eksene** bakmalı.
4. **İddianın karşıtının ÜRETİLEBİLECEĞİ bir dünya kur.** Bu partide bu, `U+001C` uyaranını
   bulmak demekti; ADIM 83'te durable executor'ı sürmek demişti. Aynı ders, iki yüzey.
5. Negatif kontrol koş ve **KİMİN** kırmızıya döndüğünü **oku** — clause kontrolünde yalnız
   yeni test düşmeli; vacuity kontrolünde **hangi assertion'ın** yakaladığına bak.
6. `--ratchet` → yeni tavanı **çıktıdan kopyala** (aritmetik yapma) → `--write-ledger`
   `--write-report` → `generate_repository_facts.py --root ..`.

## Dürüst sınırlar (bu slice'ın kendi ölçüm sınırı)

- **Backend kapıları koşulmadı** — bu slice backend'de tek satır değiştirmedi ve Postgres bu
  container'da ayakta değil (`pg_isready` → no response). Otorite **CI**.
- **e2e / `@a11y` suite'lerine assertion yazılmadı** (Docker Hub blob CDN **403**).
  Koşamadığın suite'e assertion yazma.
- Koşulan kapılar: `npm run lint` **0** · `npm run typecheck` **0** · `npm run coverage`
  **0** (**72 dosya / 735 test passed**) · acceptance `--ratchet` **0** ·
  `generate_repository_facts.py --check` **0**.
- **`AL-06`'nın `U+001C` ayrımı bir bulgu olarak KAYDEDİLMEDİ** çünkü fail-closed'dur ve
  §15'in sözleşmesini **ihlal etmez**. Onu bir kusur saymak bir ürün kararıdır; bu slice o
  kararı **vermedi**, yalnız ölçtü ve yazdı.

---

## Paste-ready resume prompt (temiz oturuma yapıştır)

```
ENTROPIA V18 — sıradaki slice

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı, tavanı ya da PR durumunu bu prompttan alma.
  git fetch --all --prune && git log --oneline origin/main -8
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  Canlı kickoff'u BULDUR (adıyla arama):
    for f in $(git ls-tree -r --name-only HEAD -- docs | grep -E 'KICKOFF.*\.md$'); do
      head -3 "$f" | grep -q 'doc-status: current' && echo "$f"
    done
  TAVANI DOSYADAN OKU: docs/audit/acceptance_coverage_baseline.json .ceilings
  (bu satır yazılırken 85 partial / 8 uncovered / A1 B54 C6 D32, total 383 — BAYAT olabilir)

BAŞLAMADAN ÖNCE ÇAKIŞMA ARA:
  mcp__github__list_pull_requests(state=open) → dokunacağın dosyaya dokunan açık PR var mı?
  Kabul defteri SERİ bir kaynaktır — paralel bir batch varsa ikinci inen rebase edip
  YENİDEN DONDURUR.

HAT A — kabul borcu batch 13. Doc 03, 07 ve 18 BİTTİ (sıfır açık kriter).
  Kalan en kalın belgeler (bu freeze'de ölçüldü, GÜVENME — yeniden ölç):
  doc 02 (8 partial) · doc 05 (8 partial) · doc 17 (7 partial) · doc 10 / 12 (6 partial).
  cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report

HAT B — mühendislik: C3 (execution/participant.py adaptörü). DİKKAT: 2026-08-19'da İKİ
  açık PR birden sürüyordu (#777, #782). Başlamadan önce hangisinin indiğini ÖLÇ; ikisi de
  açıksa bu hat KAPALIDIR, HAT A'ya geç.

HER CLAUSE İÇİN PAZARLIKSIZ:
  1. Mevcut testler bu kusur altında YEŞİL mi kalıyor? Kalıyorsa yeni assertion BAŞKA bir
     eksene bakmalı.
  2. İddiayı, karşıtının ÜRETİLEBİLECEĞİ bir dünyada ölç. ADIM 83: "Result yok" demek hiç
     backtest admit edilmemişse totolojidir. ADIM 87: "metin korundu" demek hiç submit
     edilmemişse totolojidir — reddin GERÇEKLEŞTİĞİNİ ayrı bir assertion ile gözle.
  3. Negatif kontrol koş ve KİMİN kırmızıya döndüğünü OKU; clause kontrolünde yalnız yeni
     test düşmeli.
  4. Koşamadığın bir suite'e (e2e / @a11y — Docker Hub 403) assertion YAZMA.
  5. Kriterin SON clause'u kapanıyorsa debt_class'ı KALDIR.

ORTAM: Postgres KURULABİLİR — pg_ctlcluster 16 main start + entropia rolü/DB, sonra
  LC_ALL=C.UTF-8 uv run alembic upgrade head. Integration suite Postgres'siz SESSİZCE skip
  eder; pg_isready ile ÖLÇ. Frontend'de node_modules YOK → önce `cd frontend && npm ci`.
  Alt küme: backend --no-cov -p no:randomly · frontend npx vitest run --no-file-parallelism.
  Test eklediysen repository_facts'i YENİDEN ÜRET (frontend it() çağrıları da sayılır) ve
  kabul defterine dokunduysan --write-ledger + --write-report koş (traceability raporu
  --check kapısının KAPSAMINDA DEĞİL, sessizce bayatlar).

DUR koşulları: imzasız kapı, çözülmemiş PO kararı, kırmızı focused test, OpenAPI drift,
çoklu alembic head, historical Result davranışı değişimi.
PR'ı DRAFT aç, durumu dürüstçe yaz, DUR. MERGE ETME.
```
