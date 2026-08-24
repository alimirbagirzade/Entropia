<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).
> Bu belge **ADIM 99 indikten sonraki** durumu tarif eder ve **STALE-BY-DEFAULT** okunmalıdır:
> önce `git fetch`, `git log --oneline origin/main -8`, `list_pull_requests(state=open)`.

# ADIM 99 landed — kabul borcu batch 20 (doc 10 FRONTEND): `RF-18` kapandı

## 1. Neredeyiz

Bu slice **yalnız test + defter** indirdi. `backend/src`, `frontend/src/pages` ve
`frontend/src/lib` altında **sıfır satır** değişti; migration yok, OpenAPI değişmedi,
`ENGINE_VERSION` değişmedi, `SHARED_ALLOCATION_STATUS` **`future_dev`** olarak duruyor.
**Blocker sayısı DEĞİŞMEDİ — hâlâ tek blocker var (A-08), verdict BLOCKED.**

Kapanan kriter: **`RF-18`** (doc 10 §14, frontend). Son açık clause'u `.c1` idi →
kriter **covered**, **`debt_class` KALDIRILDI**.

**Tavanlar (ölçüldü, `--ratchet` ile `b7e66ad` üstünde):**

| Sayaç | Önce | Sonra |
|---|---|---|
| `status.partial` | 69 | **68** |
| `status.uncovered` | 7 | 7 (değişmedi) |
| `debt_class.B` | 37 | **36** |
| açık borç toplamı | 76 | **75** (A=1 · B=36 · C=6 · D=32) |
| clause `covered` | 1049 | **1051** |

> **Bu satırlar `2b41cf8` (ADIM 98 / #811 merged) üstünde ölçülmüştür.** Dal önce `b7e66ad`'e
> karşı **71 → 70 / 39 → 38** dondurulmuştu; #811 aynı baseline dosyasına iki kriter daha yazınca
> dal rebase edildi ve `--ratchet` **yeniden koşuldu**. Eski freeze'i taşımak tavanı gerçek sayının
> **iki üstünde** bırakırdı ve kapı **sonsuza dek yeşil kalırdı** (ölçülen < tavan asla kırmızı
> vermez). **İki freeze'i elle ÇIKARMA.**

## 2. Bu slice ne bıraktı (REUSE anchor'ları — tam sembol adlarıyla)

- **`frontend/src/test/rationaleFamilies.test.tsx`**
  - `renderPage(client = new QueryClient({ defaultOptions: { queries: { retry: false } } }))`
    — harness artık **opsiyonel** bir `QueryClient` alıyor. Varsayılan taze istemci olduğu için
    **sekiz mevcut çağıran bayt bayt aynı**. Aynı sayfayı **iki kez** mount etmesi gereken her
    yeni case bunu kullanabilir.
  - `it("discards staged reassignments on remount, leaving only the server projection")`
    — remount deseni: `cleanup()` + `renderPage(client)` **aynı** istemciyle.
  - `const writes = () => fetchMock.mock.calls.filter(([, init]) => (init?.method ?? "GET").toUpperCase() !== "GET")`
    — "hiçbir yazma gitmedi" deseni **küme** olarak (`toEqual([])`), sayı olarak değil.
- **`docs/audit/acceptance_semantic_map.yaml` §`RF-18`** — `notes` alanı üç negatif kontrolü ve
  paylaşımlı-istemci ölçümünü **birinci elden** taşıyor; yeni bir remount case'i yazan onu okusun.

## 3. Ölçülmüş dersler (bunları tekrar keşfetme)

1. **Paylaşımlı `QueryClient` bir üslup tercihi DEĞİL, taşıyıcı bir seçimdir.** Staging query
   cache'e park edilmiş bir dünyada **taze istemcili** remount testi **9/9 geçer**; paylaşımlı
   olan kırmızı verir. Taze istemci her implementasyonu önemsizce düşürür → **yanlış-negatif
   harness**. Bir "durum kayboldu" iddiasını ölçerken cache'i **sıcak** tut.
2. **Eski testin yeşil kalması KANITTIR.** Modül düzeyi store kontrolünde sekiz mevcut case yeşil
   kaldı ve **yalnız** yeni test kırmızı oldu — clause'un gerçekten açık olduğunun kanıtı bu.
3. **ADIM 97'nin harness kuralı işliyor.** `renderPage`'e parametre eklendiği için negatif kontrol
   **harness'ı tamamen atlayarak** (inline render) yeniden koşuldu; red aynı assertion'da kaldı →
   red **ürün kusuruna** atfedilebilir.
4. **TL-18 emsalini ÖNCE koş.** Parti seçmeden önce `grep -rn '<kriter-id>' frontend/src backend/tests`
   — bir kriter, kendi id'sini taşıyan bir testle beş dalga borç görünebilir. Burada grep boştu.

## 4. Sıradaki iş — ÖLÇEREK seç

**Doc 10'da testin kapatabileceği satır KALMADI**, ve **doc 14'ün backend borcu da bitti**
(#811 / ADIM 98). Doc 10'da kalan üç satır:
`RF-08` (batch 18'in kayıtlı bulgusu — 409 hiçbir `remediation` taşımıyor, **kullanıcıya görünen
metin = ürün kararı**), `RF-04` ve `RF-13` (**sınıf D**). Kapalı belgeler artık:
**doc 03, doc 07, doc 18** (tam) + **doc 02 / doc 10 / doc 14 / doc 17'nin backend'i** +
**doc 10'un frontend'i**. Doc 14'ün kalan tek satırı `RC-09.c3` ve o **frontend**.

- **HAT A — kabul borcu batch 21.** Bir sonraki en ucuz kalemi `--report` çıktısından **ölç**.
  **UYARI:** doc 12'nin dört sınıf-B satırının **dördü de kayıtlı bulgudur** (sınıf-D şeklinde) —
  parti seçmeden önce defterin `notes` alanını **oku**, sayıya bakma.
- **HAT B — mühendislik: `C4` / `E5`.** Açık PR'ları **ölç**, sonra karar ver.

## 5. Çakışma nasıl çözüldü (ölçülmüş emsal)

Bu dal yazılırken **#811 açıktı** ve `docs/ADIM98_LANDED_KICKOFF.md` **dosya yolunu** ekliyordu.
O **önce indi** (ADIM 98 / batch 19, doc 14 `RC-10` + `RC-17`), yani `96` bir boşluk **değil**,
#811'in taşıdığı numaradır. Bu dal:

1. **rebase edildi** (`Update branch` düğmesi **kullanılmadı** — ADIM 92/98'in kaydettiği zarar);
2. üretilmiş dosyalarda upstream sürümü alınıp **jeneratörle yeniden üretildi** (elle çakışma
   çözümü YOK): baseline, defter, izlenebilirlik raporu, `repository_facts` üçlüsü;
3. `--ratchet` **yeniden koşuldu** ve tavan **taze ölçümden** yazıldı;
4. `docs/ADIM98_LANDED_KICKOFF.md` `historical`a demote edildi (canlı işaret **en yüksek numaralı**
   dosyada olmalı), `PROJECT_HISTORY` ve handoff'ta **iki kaydın ikisi de korundu** (silinen kayıt
   yok — `git diff ... | grep '^-## '` boş).

**Sıradaki slice aynı şeyi yapmak zorunda kalabilir: kabul defteri SERİ bir kaynaktır.**

---

## Paste-ready resume prompt

```
ENTROPIA V18 — sıradaki slice

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı, tavanı ya da PR durumunu bu prompttan alma.
  git fetch --all --prune && git log --oneline origin/main -8
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  Canlı kickoff = ilk satırında 'doc-status: current' olan EN YÜKSEK numaralı ADIM dosyası:
    for f in docs/ADIM*KICKOFF.md; do head -1 "$f" | grep -q 'doc-status: current' && echo "$f"; done
  TAVANI DOSYADAN OKU: docs/audit/acceptance_coverage_baseline.json .ceilings
  (ADIM 99 indiğinde 68 partial / 7 uncovered / A1 B36 C6 D32, total 383 — BAYAT olabilir)

BAŞLAMADAN ÖNCE ÇAKIŞMA ARA — ve DOSYA YOLUNA bak, başlığa değil:
  list_pull_requests(state=open) → her açık PR'ın EKLEYECEĞİ docs/ADIM<n>_LANDED_KICKOFF.md
  yolunu çıkar. Çakışma başlıkta değil DOSYA YOLUNDADIR ve check_classification onu görmez.
  ADIM ile batch numarası BAĞIMSIZ taşınır ve bir slice hiç batch numarası taşımayabilir.
  Kabul defteri SERİ bir kaynaktır: paralel bir batch varsa ikinci inen REBASE edip tavanı
  YENİDEN ÖLÇER. İki freeze'i elle ÇIKARMA.

HAT A — kabul borcu batch 21. Doc 03/07/18 tam kapalı; doc 02, 10, 14 ve 17'nin BACKEND borcu
  bitti, doc 10'un FRONTEND borcu da bitti (ADIM 99). Doc 14'ün kalan tek satırı RC-09.c3 (frontend).
  UYARI: doc 12'nin dört sınıf-B satırının DÖRDÜ DE kayıtlı bulgudur. notes alanını OKU.
  cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report

HAT B — mühendislik: C4 / E5. Açık PR'ları ÖLÇ, sonra karar ver.

HER CLAUSE İÇİN PAZARLIKSIZ:
  1. Mevcut testler bu kusur altında YEŞİL mi kalıyor? Kalıyorsa yeni assertion BAŞKA eksende.
  2. "raise ediyor" ile "YAZMADAN raise ediyor" AYNI ŞEY DEĞİLDİR → satırları SAY ve geri oku.
  3. Refüz testinde ROLLBACK YAPMA: flush() + expire_all() ile veritabanından oku.
  4. HARNESS parametresi eklediysen red'in SENİN değişikliğine atfedilemeyeceğini ayrı bir
     negatif kontrolle göster (yeni case'i harness'ı ATLAYARAK koş).
  5. Negatif kontrol koş ve KİMİN kırmızıya döndüğünü OKU. Eski testin yeşil kalması KANITTIR.
  6. Koşamadığın suite'e (e2e / @a11y) assertion YAZMA.
  7. Kriterin SON clause'u kapanıyorsa debt_class'ı KALDIR.
  8. "Durum kayboldu/korundu" iddiasını ölçerken cache'i SICAK tut — remount'ta AYNI
     QueryClient'ı kullan; taze istemci her implementasyonu önemsizce geçirir (ADIM 99'da ölçüldü).

ÜRETİLMİŞ ARTEFAKTLAR (#809 kapısı): defter/rapor değiştiyse ONUN jeneratörüyle üret —
  uv run python ../docs/audit/acceptance_semantic_scan.py --root .. \
    --write-ledger docs/audit/acceptance_coverage_debt_ledger.md \
    --write-report docs/audit/acceptance_semantic_traceability.md
  Test eklediysen: uv run python ../scripts/generate_repository_facts.py --root ..
  (json + md + README bloğunun ÜÇÜ birden tazelenir). Elle düzenleme YOK, tavan genişletme YOK.
  ci.yml'ın birebir çağrısı: --report --check-generated --ratchet

GUARD TUZAĞI: guard-git.sh, üretilmiş defterin sayı taşıyan başlıklarını ("## Class B (37)" →
"(36)") KAYIT SİLME sanır ve commit'i bloklar. PROJECT_HISTORY'den silinen kayıt olmadığını
doğrula, kullanıcıdan onay al, commit'i BİR BETİK DOSYASINDAN koştur.

ORTAM: Postgres cluster'ı container yeniden başlayınca BOŞ gelebilir (rol + DB kaybolur).
  pg_ctlcluster 16 main start
  sudo -u postgres psql -c "CREATE ROLE entropia LOGIN PASSWORD 'entropia' SUPERUSER"
  sudo -u postgres psql -c "CREATE DATABASE entropia OWNER entropia"
  DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia \
    LC_ALL=C.UTF-8 PYTHONUTF8=1 uv run alembic upgrade head
  MİGRASYONU ATLAMA: contract testleri MİGRATE EDİLMİŞ DATABASE_URL'i kullanır → ~40 sahte hata.
  Hepsi "s" çıkan koşu YEŞİL DEĞİL, SKIPPED'dir (exit 0 verir). Nokta say.
  Alt küme koşarken --no-cov. `pytest … | tail` KULLANMA: exit code tail'in olur.
  Frontend'de node_modules YOK → npm ci (sonra `npm run lint`, `npm run typecheck`,
  `npx vitest run <dosya> --no-file-parallelism`, kapı için `npm run coverage`).

DUR koşulları: imzasız kapı, çözülmemiş PO kararı, kırmızı focused test, OpenAPI drift,
çoklu alembic head, historical Result davranışı değişimi.
PR'ı DRAFT aç, durumu dürüstçe yaz, DUR. MERGE ETME.
```
