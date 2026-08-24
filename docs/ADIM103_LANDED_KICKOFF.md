<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 103 LANDED — kabul borcu batch 24 (doc 20 Trash, backend): `TR-08` kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 103. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`43dc70d`** (`ADIM 101` / batch 22 = #814, doc 21 User Manual BACKEND).
  **`ADIM 102` bu dalın DEĞİL, #815'İN — ve İNDİ:** paralel oturumun #815'i doc 16'yı
  (`RH-13` + `RH-14`) `ADIM 102 / batch 23` olarak kapattı ve bu PR açıkken **merge edildi**
  (`4dab3de`). Sonra-inen yükü bu dala düştü ve ödendi: dal merged main üzerine **rebase**
  edildi, `ADIM102` kickoff'u `historical` işaretlendi, canlı işaret EN YÜKSEK numaralı
  dosyada (`ADIM103`, bu belge) kaldı.
- **Ürün kodu değişmedi** (`backend/src` altında sıfır satır); diff = tek integration case +
  kabul defteri + üretilmiş artefaktlar. Migration yok, OpenAPI değişmedi, alembic head
  `0043_i08_registry_strategy_fks`, `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kapanan: `TR-08` (c4)** — restore'un outbox olayı. Son açık clause'du → `debt_class`
  **kaldırıldı**. **Tavanlar merged ağaçta TAZE ölçüldü: `partial` 62 → 61, `debt_class.B`
  30 → 29**; açık borç **68** (A=1 · B=29 · C=6 · D=32). Dalın #815'siz freeze'i (63/31)
  rebase'de TAŞINMADI — taze `--report`'tan yeniden ölçüldü.
- **Doc 20 = 14 covered / 2 partial**, kalan ikisi kapatılabilir sınıf-B değil
  (`TR-07` = bulgu · `TR-12` = sınıf C). **Doc 20'nin kapatılabilir backend borcu bitti.**

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `backend/tests/integration/test_trash_page.py::test_restore_emits_its_trash_outbox_event` —
  bir "olay yazılıyor AMA okunuyor mu" clause'unun kalıbı: (1) atıf muhafızı (aynı entity +
  aynı `event_type` için ÖNCE sıfır satır), (2) `scalar_one` ile tam-olarak-bir emisyon,
  (3) payload **tam sözlük eşitliği**, (4) `published_at is None` (yayımlayan relay).
  Outbox tipi ile audit kind'ı AYRI adlardır (`entity.restored` / `trash.restored`) —
  sevk edilen ad kanonik (O-02/O-31).
- **Negatif kontrol çifti şablonu:** NC-1 emisyonu kaldırır → kırmızı varlık okumasında ve
  komşu suite'ler (e2e pipeline'ın kendi restore'u dahil) yeşil kalır = boşluğun ölçümü;
  NC-2 olayı bırakıp payload'ı boşaltır → varlık geçer, kırmızı sözlük eşitliğine taşınır =
  payload ekseni gölgesiz. Koşucu deseni scratchpad'de (`finally` geri yazma + eşleşme sayısı
  assert'i + her turdan sonra `git status`), `PROJECT_HISTORY.md` §ADIM 94'teki yazılı desen.
- **Ortam:** ADIM 101 kickoff'undaki kurulum dizisi aynen geçerli (çıplak container →
  `uv sync --all-extras`, Postgres 16 initdb/start, `LC_ALL=C.UTF-8 PYTHONUTF8=1` ile
  `alembic upgrade head`). Alt kümeye izole DB:
  `TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_<slug>"`.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **BOŞ BİR AÇIK-PR LİSTESİ, ALINDIĞI OTURUMU BİLE KAPSAMAZ.** Bu oturum listeyi boş ölçtü,
   raporun gösterdiği en değerli partiyi (doc 16) sonuna kadar yazdı — testler yeşil, beş
   negatif kontrol okunmuş, tavanlar inmiş — ve kapanış doğrulamasında aynı iki kriteri
   `ADIM 102 / batch 23` olarak kapatan açık **#815**'i buldu. ADIM 86 emsali uygulandı: açık
   ve tamamlanmış rakip kazanır, çift iş **push edilmeden bütünüyle geri alındı**. Bundan
   sonra: **parti seçiminden hemen sonra** listeyi bir kez daha ölç; iki oturak aynı raporu
   okuyorsa aynı partiyi seçer.
2. **BİR UNIQUE KISIT, ASSERTION'IN YERİNE GEÇEBİLİR.** (Geri alınan işten taşınan tek ders.)
   "Ekleme" kusurunu mevcut bir anahtarla kurmak `uq_*` kısıtına takılır ve test **yanlış
   sebeple** kırmızı olur — kontrol reddedilir, kusur **yeni bir anahtarla** kurulur. Kırmızının
   hangi satırda olduğunu okumak (ADIM 98) bunu yakalayan tek şeydir.
3. **"OLAY YAZILIYOR" DEFTERDE BİLE YAZIYORDU — yine de açıktı.** TR-08'in defter notu outbox
   çağrısının varlığını satır satır tarif ediyordu; clause yine de kapsanmamıştı çünkü tarif
   bir test değildir. `grep OutboxEvent <suite>` üç saniyede ölçtü (ADIM 101 md. 4'ün grep
   kuralı burada birebir işledi).

## Sıradaki iş — ölçülmüş adaylar (yine de kendin ölç)

- **#815 İNDİ, rebase + kickoff zinciri + taze `--report` bu dalda YAPILDI** — tekrar etme.
- **Bitmiş belgeler/yüzeyler:** doc 05 · 18 · 10 · 22-B · 02-B · 17-B · 01-B · 14-B · 21-B ·
  **doc 16 (#815 ile) · doc 20-B (bu slice)**.
- **Kalan sınıf-B yoğunluğu (batch 24 tabanında):** doc 09 (ESP: `ESP-03` gerçek seeder,
  `ESP-05` resolver payload, `ESP-20` yabancı aktör rol filtresi) · doc 06 (CP: `CP-09` Send
  replay'i, `CP-13` Supervisor/Agent approval izni) · doc 08 (`PL-07` pinlenmiş indicator
  revizyonu) · doc 12 (kalan RD satırlarının çoğu bulgu — listeye bak).
- **Frontend bitiricileri:** `UM-15.c3` (doc 21) · `RC-09.c3` (doc 14) — `cd frontend && npm ci`.

## Paste-ready resume prompt (bir sonraki oturuma yapıştır)

```
ENTROPIA V18 — kabul borcu (sıradaki parti)

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı, numarayı ve hiçbir sayıyı bu prompttan alma:
  git fetch && git log --oneline origin/main -6
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  mcp__github__list_pull_requests(state=open)
  # NUMARAYI açık PR'ların EKLEDİĞİ docs/ADIM<n>_*.md YOLLARINDAN ölç.
  # PARTİ SEÇTİKTEN HEMEN SONRA listeyi BİR KEZ DAHA ölç (ADIM 103: boş liste alındığı
  # oturumu bile kapsamaz — bu partide çift iş bütünüyle geri alındı).
  Canlı kickoff = ilk satırında 'doc-status: current' olan EN YÜKSEK numaralı ADIM dosyası:
    for f in docs/ADIM*KICKOFF.md; do head -1 "$f" | grep -q 'doc-status: current' && echo "$f"; done
  Onu oku.

Bu prompt yazılırken: main = `4dab3de` (ADIM 102 / batch 23 = #815, doc 16) + bu dal
ADIM 103 / batch 24 (doc 20 TR-08, #816, rebase edilmiş). Yine de ölç.

TAVANLAR: tek otorite acceptance_coverage_baseline.json `ceilings`. Ratchet YALNIZ AŞAĞI;
  total_criteria TABAN. Rebase sonrası tavanı TAŞIMA, taze --report'tan yeniden ölç.

ORTAM: container ÇIPLAK başlayabilir; kurulum dizisi docs/ADIM101_LANDED_KICKOFF.md §çapalar.
  alembic için LC_ALL=C.UTF-8 PYTHONUTF8=1. `ss` + exit 0 yeşil DEĞİLDİR.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  1) cd backend && python3 ../docs/audit/acceptance_semantic_scan.py --root .. --report
  2) ADAY SEÇTİKTEN SONRA: grep -rn "<KRİTER-ID>" frontend/src backend/tests
     ve grep -rn "<okunan modeli>" ilgili suite — kapsama sevk edilmiş olabilir (ADIM 88),
     "olay yazılıyor" clause'unda OKUYAN test ara (ADIM 101/103).
  3) Davranışın sevk edildiğini üründe DOĞRULA; unshipped (D) · unconstructible (C) ·
     unfalsifiable (işaretle) ayır.

HER CLAUSE İÇİN ZORUNLU (ADIM 98/100/101/103 disiplini):
  a. Mevcut testler kusur altında yeşil kalıyorsa yeni assertion BAŞKA eksene bakmalı.
  b. Negatif kontrol: yama uygulandı doğrulaması + finally geri yazma + her turdan sonra
     git status.
  c. Kırmızının HANGİ assertion'da olduğunu OKU; yanlış sebeple kırmızı = kontrolü REDDET
     (ADIM 103: unique kısıt assertion'ın yerine geçebilir — eklemeyi YENİ anahtarla kur).
  d. Yokluk iddiasının önünde rollback/identity map olamaz; geri okumadan önce
     session.expire_all().
  e. Gövde iddiası = tam sözlük eşitliği, key lookup değil.
  f. EZME (demetler) ile EKLEME (tam sıralı listeler) ayrı eksenlerdir; count(*) ikisini kaçırır.
  g. Koşamadığın suite'e assertion yazma; sınırı yaz.
  h. Son clause kapanıyorsa kriter status'ü covered + debt_class KALDIR.
  i. YAML notunda ': ' varsa tek tırnak, apostrof ikile.
  j. Eşzamanlılık: iki AYRI engine + asyncio.Barrier komuttan ÖNCE; determinizm İKİ yönde.

KAPATMAYA ÇALIŞMA (bulgular): TL-01.c4, TL-02.c2, TL-11.c3, TL-14.c4, TL-16.c4, RF-08.c2,
  TR-07.c3, RD-01.c4, RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2, MB-22.c4
  + `unfalsifiable: true` clause'lar. Yeniden sınıflandırma tavan yükseltir = adjudication.

BİTMİŞ: doc 05 · 18 · 10 · 22-B · 02-B · 17-B · 01-B · 14-B · 21-B · 16 (#815) · 20-B.
  Kalan yoğunluk: doc 09 (ESP) · doc 06 (CP) · doc 08 (PL-07) — yine de ölç.
  UM-15.c3 ve RC-09.c3 kendi belgelerini bitirir ama FRONTEND.

KAPANIŞ: CLAUDE.md §Session CLOSING 6 madde. Numara + parti etiketini commit'ten hemen önce
  YENİDEN doğrula (dosya yolu ölçümü). TEST EKLEDİYSEN generate_repository_facts.py koş.
  --write-report/--write-ledger yolları --root'a göre: `docs/audit/...`.
  Rebase gerekiyorsa "Update branch" DEĞİL; iki tarafı koruyarak çöz, üretilmişleri yeniden
  üret, tavanı taze --report'tan ölç. Sonra --report --check-generated --ratchet +
  grep -c '^## ADIM' (düşmemeli). git guard: fetch/doğrulama ile push'u AYRI Bash çağrılarına
  böl. PR'ı main'e aç; MERGE ETME — karar insanın.
```
