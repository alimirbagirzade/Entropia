<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu kaydeder;
> SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir. Canlı kickoff artık
> `docs/ADIM101_LANDED_KICKOFF.md`.

# ADIM 100 LANDED — kabul borcu batch 21 (doc 22 Future Dev, backend): iki kriter kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 100. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`bc25d22`** (`ADIM 99` / batch 20 = #812, doc 10 FRONTEND `RF-18`). Dal ilk olarak
  `2b41cf8`'den kesildi ve o an **açık PR görünmüyordu**; #812 bu PR açıkken indi ve **ADIM 99 ile
  batch 20'nin İKİSİNİ de** merge edilmiş adla aldı → bu slice **ADIM 100 / batch 21**'e taşındı
  (kickoff dosyası dahil yeniden adlandırıldı). Dal `origin/main` üzerine **rebase** edildi. **Ürün kodu değişmedi**
  (`backend/src` altında sıfır satır); diff = iki yeni integration case + kabul defteri +
  üretilmiş artefaktlar. Migration yok, OpenAPI değişmedi, alembic head
  `0043_i08_registry_strategy_fks`, `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kapananlar: `FD-04` (c4) · `FD-05` (c4)** — doc 22'nin BACKEND yüzeyi. İkisi de kendi
  kriterinin son açık clause'uydu → ikisinin de `debt_class`'ı **kaldırıldı**.
- **Tavanlar İNDİ: `partial` 68 → 66, `debt_class.B` 36 → 34**; açık borç **75 → 73**
  (A=1 · B=34 · C=6 · D=32). **Bu sayılar merged ağaçta YENİDEN ÖLÇÜLDÜ** — dalın rebase
  öncesi freeze'i 67/35 taşıyordu ve #812 arada **başka** bir kriteri (`RF-18`) kapatmıştı;
  67/35'i taşımak tavanı gerçek sayının **bir üstünde** bırakırdı ve `--ratchet` sonsuza dek
  yeşil kalırdı (ölçülen < tavan asla kırmızı vermez).
- **Doc 22 = 6 covered / 3 partial / 6 deliberate_future_dev** (bu slice 4 → 6 / 5 → 3). Kalan üç `partial` satırın
  **hiçbiri bir test slice'ının kapatabileceği şey değil**: `FD-02` (c4 — insan HTTP hattında
  denial kaydı **yok**), `FD-09` (c4 — `AnalysisArtifact`'te **split ve seed kolonu yok**,
  ŞEMA boşluğu), `FD-13` (c4 — refüz `_audit_and_outbox`'a **hiç ulaşmadan** raise ediyor).
  Üçü de sınıf **D**. **Doc 22'de sınıf-B kalmadı.**

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `backend/tests/integration/test_future_dev.py` — dosyanın sonundaki **"Acceptance batch 21"**
  bölümü. Dört yeniden kullanılabilir parça:
  - **`_seed_backtest_result(session)`** — YOĞUN bir `BacktestResult`: üç `metric_value`
    (biri bilerek `value=None` + `availability=no_drawdown`), iki `trade_ledger_row`, ve
    result'a pinlenmiş `result_manifest_snapshot`. `BacktestResult.run_id` **FK DEĞİL**
    (`String(40)`, yalnız UNIQUE) → bir `backtest_run` satırı olmadan tek başına insert edilir;
    `workspace_entity_id` de öyle. Bir "tarihsel kayıt kıpırdamadı" iddiası kuracak her slice
    bunu ödünç alabilir.
  - **`_result_snapshot(session)`** — **`session.expire_all()` ile başlar.** Integration
    fixture'ı session'ı `expire_on_commit=False` ile kurar (`tests/integration/conftest.py:48`),
    yani `commit` identity map'i temizlemez: `expire_all` olmadan her karşılaştırma
    **veritabanına değil, bu sürecin elindeki nesnelere** karşı yapılır. Bu satır
    **taşıyıcıdır**, silme.
  - **`_assert_dense(before)`** — vacuity muhafızı. Boş bir kökte *"hiçbir şey değişmedi"*
    **bedavadır**; snapshot'ın gerçekten dolu olduğunu çağrıdan ÖNCE assert et.
  - **Landing assertion deseni** — `ViewDataset` / `AnalysisArtifact` satırı var **ve** gerçek
    ref'i taşıyor. Bu olmadan "hiçbir şey kıpırdamadı" **hiçbir şey yapmamış** bir çağrı için
    de doğrudur.
- **Negatif kontrol harness'i** — `finally` ile geri yazan, yamanın uygulandığını **eşleşme
  sayısıyla** assert eden `run(name, edits, pytest_args)` sarmalayıcısı; bu slice onu
  scratchpad'de tuttu (deseni `PROJECT_HISTORY.md` §ADIM 94'te yazılı).
- **Ortam — bu container ÇIPLAK başladı** (`.venv` yok, cluster yok). Tam dizi:
  ```
  cd backend && uv sync --all-extras
  PGDATA=/var/lib/postgresql/entropia-data
  mkdir -p $PGDATA && chown postgres:postgres $PGDATA && chmod 700 $PGDATA
  su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $PGDATA -U postgres --auth=trust -E UTF8 --locale=C"
  su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA -l /tmp/pg.log -o '-p 5432' -w start"
  su postgres -c "/usr/lib/postgresql/16/bin/psql -p 5432 -U postgres -c \"CREATE ROLE entropia LOGIN SUPERUSER PASSWORD 'entropia';\""
  su postgres -c "/usr/lib/postgresql/16/bin/createdb -p 5432 -U postgres -O entropia entropia"
  cd backend && LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONUTF8=1 uv run alembic upgrade head
  ```
  **`LC_ALL=en_US.UTF-8` bu imajda alembic'i `UnicodeDecodeError` ile patlatır.** Alt küme
  koşarken kendi izole DB'ni ver:
  `export TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_fd"`.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **BİR REF'İN GERÇEK BİR SATIRI ADLANDIRDIĞINI DOĞRULA.** Bu partinin tamamı tek bir
   gözlemden çıktı: doc 22'nin FD-04/FD-05 testlerinin hepsi komuta `"result_abc123"` veriyordu
   ve o dize **hiçbir satırı adlandırmıyor**. *"Referans edilen Backtest Result'a dokunulmadı"*
   iddiası o dünyada doğruydu çünkü **dokunulacak bir şey yoktu**. Bir "X kıpırdamadı" clause'u
   seçtiğinde ilk soru *"X test veritabanında GERÇEKTEN VAR MI"* olmalı.
2. **`expire_on_commit=False` BİR TUZAKTIR.** Bu deponun integration session'ı öyle kurulur.
   `commit`'ten sonra bir alanı okumak **veritabanını okumak değildir**. Bir yan etkinin
   yokluğunu iddia eden her assertion'ın önünde `session.expire_all()` (veya taze bir bağlantı)
   olmalı — bu, ADIM 94'ün rollback kuralının **okuma yoluna** uygulanmış hâli ve aynı kusuru
   üretir: yeşil, ama hiçbir şey ölçmemiş.
3. **EZME İLE EKLEME İKİ AYRI KUSUR SINIFIDIR.** Satır **demetlerini** karşılaştırmak bir
   ezmeyi yakalar; tam sıralı **listeleri** karşılaştırmak bir eklemeyi yakalar. NC-3 (metrik
   ezme) ve NC-4 (ledger satırı ekleme) bunu ölçtü: **hiçbiri diğerinin kusurunu görmüyor.**
   `count(*)` assertion'ı da ikisini birden kaçırır (ezmede sayı sabit).
4. **GÖLGELENEN ASSERTION'I ÖLÇÜLMÜŞ SAYMA.** `FD-05` case'inin son `result_row` assertion'ı
   kendinden önceki üç assertion tarafından gölgelenir; bu slice onu **kendi ekseni saymadı** ve
   defter notuna **yazdı** (o iddia `FD-04`'ün NC-1'i ile bağımsız ölçülüyor). Sessizce
   bırakmak ölçülmemiş bir assertion'ı ölçülmüş göstermek olurdu.
5. **`finally` SÜREÇ ÖLDÜRÜLÜRSE KOŞMAZ.** Bir kontrol koşusu Bash aracının zaman aşımıyla
   SIGTERM aldı ve harness'ın `finally`'si hiç çalışmadı → ağaç yamalı kaldı. Bir sonraki
   kontrol kirli ağacı **sessizce** ölçerdi. **Her kontrol turundan sonra `git status`.**
   Uzun kontrol dizilerini `nohup`/arka planda koştur, sonra `until ! pgrep …` ile bekle.
6. **TEST EKLEYEN SLICE ÜRETİLMİŞ OLGULARI TAZELEMELİ.** `docs/generated/repository_facts.*`
   **test collection** sayısını taşır ve `README.md` aynı bloğu gömer; iki test eklemek üçünü
   birden bayatlattı (`--check` kırmızı verdi). `cd backend && uv run python
   ../scripts/generate_repository_facts.py --root ..` — ADIM 60'ın dersi, bu partide yine yaşandı.
7. **YAZICI PATH'İ `--root`'A GÖRE ÇÖZÜLÜR.** `--write-report ../docs/...` `../../docs/...`
   arar ve `FileNotFoundError` verir; doğrusu **`--write-report docs/audit/...`** (script'in
   kendi hata mesajı bu komutu zaten basıyor — onu oku, tahmin etme).

## Sıradaki tasarım işaretleri — ÖNCE ÖLÇ

- **Kalan sınıf-B yoğunluğu (bu freeze'den; sen yine ölç):** doc 21 (`UM-08` `UM-13` `UM-15`) ·
  doc 09 (`ESP-03` `ESP-05` `ESP-20`) · doc 06 (`CP-03` `CP-09` `CP-13`) · doc 16
  (`RH-13` `RH-14`) · doc 20 (`TR-07` `TR-08`).
  Tek otorite `docs/audit/acceptance_coverage_baseline.json` +
  `acceptance_semantic_scan.py --report`.
- **`UM-08.c5` bu freeze'in EN UCUZ satırı ve ölçüldü.** Olay **gerçekten yayımlanıyor** —
  `commands/manual.py` bir `ManualPublicationEvent` (`event_type="manual_document_soft_deleted"`)
  **ve** bir audit/outbox çifti (`event_kind="manual.document_soft_deleted"`) yazıyor — ama
  **hiçbir test ikisini de assert etmiyor**; suite aynı iddiayı yalnız **purge** için pinliyor
  (`_publication_event(..., "manual_document_purged")`). Kriterin son açık clause'u → kapanırsa
  `debt_class` kalkar. **Yine de kendin ölç:** olayın hâlâ yazıldığını ve testin gerçekten
  yokluğunu doğrulamadan yazma (ADIM 88'in emsali: bir kriter, kendi id'sini taşıyan bir testle
  beş dalga borç görünebilir).
- **`TR-08.c4` de tek clause ve aynı şekle sahip** (restore yolunda outbox emisyonu hiç
  sorgulanmıyor; mevcut test yalnız `AuditEvent.event_kind` okuyor). **Uyarı:** doc 20'nin
  kardeşi `TR-07.c3` **kapatılabilir görünmüyor** — *"repair plan required"* için raise edilen
  `RationaleFamilyInUseError` bir `remediation`/`field_path` taşımıyor; `RF-08.c2` ile aynı
  şekil, **bulgu olarak işaretle, kapatma**.
- **`UM-13.c3` eşzamanlılık ister** (`pg_advisory_xact_lock` + `uq_manual_stream_position`) ve
  tek session'lı bir integration testiyle **kurulamayabilir**; ikinci bir bağlantı gerekir.
  `tests/integration/conftest.py` ikinci bağlantı açan bir emsal taşıyor (concurrent demotion
  race) — önce onu oku.
- **`RC-09.c3` doc 14'ü bitirir ama FRONTEND** — bu container'da `node_modules` yok, önce
  `cd frontend && npm ci`.
- **Kabul borcu hattı mühendislik hattından AYRI.** Aynı PR'da karıştırma. Mühendislik tarafında
  sıradaki kalem hâlâ `C6` (`G11`+`G12` **iki imza**) — `PROJECT_HISTORY.md` §ADIM 92.

## Çalışma yöntemi (bu dalgada işe yarayan)

1. **Ölç, prompt'a güvenme:** `git fetch` → `git log --oneline origin/main -6` →
   `git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail` →
   `list_pull_requests(state=open)` → **açık PR'ların EKLEDİĞİ `docs/ADIM<n>_*.md` YOLLARI**
   (başlık değil).
2. **Ortamı kur** (yukarıdaki dizi), sonra hedef dosyayı **taban olarak** koştur — kaç nokta
   çıktığını **yaz**, kontrollerin greenlik ölçümü buna dayanacak.
3. **Aday seç → `grep -rn "<KRİTER-ID>" frontend/src backend/tests`** (kapsama zaten sevk
   edilmiş olabilir) **→ üründe davranışın sevk edildiğini doğrula** (bu partide iki komutun
   gövdesini okumak yetti: hiçbir result tablosuna yazma yok).
4. **Testi yaz, sonra her assertion için ayrı bir negatif kontrol kur.** Kontrolün
   **HANGİ assertion'da** kırmızıya döndüğünü **oku** — hedef assertion değilse kontrolü
   **reddet**, yenisini kur (ADIM 98). Kontrolden sonra **`git status`**.
5. **Kapanış:** map → `--report` → baseline freeze (provenance dahil) →
   `--write-report`/`--write-ledger` → `--report --check-generated --ratchet` →
   `generate_repository_facts.py --root ..` → ruff/format/mypy → `grep -c '^## ADIM'` (düşmemeli).

---

## Paste-ready resume prompt (bir sonraki oturuma yapıştır)

```
ENTROPIA V18 — kabul borcu (sıradaki parti)

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı, numarayı ve hiçbir sayıyı bu prompttan alma:
  git fetch && git log --oneline origin/main -6
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  git show origin/main:docs/PROJECT_HISTORY.md | grep -o 'batch [12][0-9]' | sort -u
  mcp__github__list_pull_requests(state=open)
  # NUMARAYI başlıktan değil, açık PR'ların EKLEDİĞİ docs/ADIM<n>_*.md YOLLARINDAN ölç.
  CANLI kickoff = en yüksek numaralı docs/ADIM<n>_LANDED_KICKOFF.md — onu oku, bunu değil.

Bu prompt yazılırken main `bc25d22` üzerine ADIM 100 / batch 21 yazıldı (doc 22 Future Dev
BACKEND, FD-04 + FD-05). Yine de kendin ölç.

TAVANLAR: bu prompttan OKUMA. Tek otorite acceptance_coverage_baseline.json `ceilings`.
  Ratchet YALNIZ AŞAĞI iner; total_criteria bir TABANDIR.

ORTAM: container ÇIPLAK başlayabilir — backend/.venv YOK, Postgres cluster YOK, ve
  container yeniden başlayınca Postgres DÜŞER.
  Kurulum dizisi: docs/ADIM100_LANDED_KICKOFF.md §çapalar.
  `alembic upgrade head` için LC_ALL=C.UTF-8 PYTHONUTF8=1 kullan — en_US.UTF-8 bu imajda
  UnicodeDecodeError verir. `ss` (skipped) + exit 0 bir yeşil DEĞİLDİR.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  1) cd backend && python3 ../docs/audit/acceptance_semantic_scan.py --root .. --report
  2) ADAY SEÇTİKTEN SONRA, TEST YAZMADAN ÖNCE:
       grep -rn "<KRİTER-ID>" frontend/src backend/tests
     Kapsama zaten sevk edilmiş olabilir -> cite et, yazma (ADIM 88).
  3) Kriterin adlandırdığı davranışın sevk edildiğini üründe DOĞRULA. Üç şekli ayır:
     unshipped (D) · unconstructible (C) · unfalsifiable (işaretle, kapatma).
  4) Bir "X kıpırdamadı" clause'u seçtiysen İLK SORU: X test veritabanında GERÇEKTEN VAR MI?
     ADIM 100: doc 22'nin tüm FD-04/FD-05 testleri literal "result_abc123" veriyordu, o dize
     hiçbir satırı adlandırmıyordu -> iddia doğruydu çünkü dokunulacak bir şey yoktu.

HER CLAUSE İÇİN ZORUNLU:
  a. Mevcut testler bu kusur altında yeşil mi kalıyor? Kalıyorsa yeni assertion BAŞKA bir
     eksene bakmalı — yoksa işaretleme yapıyorsun, kapsama değil.
  b. Negatif kontrol koş VE YAMANIN UYGULANDIĞINI DOĞRULA; geri yazmayı `finally`'ye koy —
     AMA `finally` süreç SIGTERM alırsa KOŞMAZ: her turdan sonra `git status` (ADIM 100).
  c. KIRMIZININ HANGİ ASSERTION'DA OLDUĞUNU OKU — ve o HEDEF assertion mı? Değilse KONTROLÜ
     REDDET, yenisini kur (ADIM 98). İlk kırmızı sonrakini GÖLGELER: gölgeyi kaldıran ayrı
     bir kontrol kur, ya da gölgelendiğini DEFTERE YAZ (ADIM 100).
  d. YEŞİL kontrol = yama uygulanmadı VEYA assertion totolojik. Bir yan etkinin YOKLUĞUNU
     iddia ediyorsan, önünde onu geri alan hiçbir şey olmamalı — rollback DE, identity map DE:
     integration session'ı `expire_on_commit=False` kurar, geri okumadan önce
     `session.expire_all()` (ADIM 100).
  e. Bir GÖVDE iddiasını key lookup'la kurma — serileştirilmiş metne karşı substring tara.
  f. EZME ile EKLEME ayrı kusur sınıflarıdır: satır DEMETLERİNİ karşılaştır (ezme) VE tam
     sıralı LİSTELERİ karşılaştır (ekleme); `count(*)` ikisini de kaçırır (ADIM 100).
  g. Koşamadığın suite'e (E2E/A11Y/frontend) assertion YAZMA; sınırı yaz.
  h. Kriterin SON clause'u kapanıyorsa KRİTER-DÜZEYİ `status`'ü de covered yap ve
     `debt_class`'ı KALDIR.
  i. YAML notu düz skalerse `: ` ekleyemezsin -> tek tırnağa al, apostrofları ikile.

KAPATMAYA ÇALIŞMA (bulgular): TL-01.c4, TL-02.c2, TL-11.c3, TL-14.c4, TL-16.c4, RF-08.c2,
  TR-07.c3, RD-01.c4, RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2, MB-22.c4
  + `unfalsifiable: true` clause'lar. Yeniden sınıflandırma tavan yükseltir = adjudication.

BİTMİŞ OLANLAR: doc 05 · doc 18 · doc 22-BACKEND · doc 02-BACKEND · doc 17-BACKEND ·
  doc 01-BACKEND · doc 14-BACKEND · **doc 10 TAMAMEN** (#812 = ADIM 99 `RF-18` frontend'i kapattı). Kalan sınıf-B yoğunluğu (yine de ölç):
  doc 21 (UM) · doc 09 (ESP) · doc 06 (CP) · doc 16 (RH) · doc 20 (TR).
  UM-08.c5 EN UCUZ satır: olay YAZILIYOR (manual.py, hem ManualPublicationEvent hem audit/outbox)
  ama hiçbir test okumuyor; suite aynı iddiayı yalnız purge için pinliyor.
  TR-08.c4 aynı şekil (restore yolunda outbox hiç sorgulanmıyor).
  UM-13.c3 eşzamanlılık ister, tek session'lı testle KURULAMAYABİLİR.
  RC-09.c3 doc 14'ü bitirir ama FRONTEND (`cd frontend && npm ci` gerekir).

KAPANIŞ: CLAUDE.md §Session CLOSING'in 6 maddesi. ADIM numarasını VE parti etiketini
  commit'ten hemen önce yeniden doğrula. Merge edilmiş ad kazanır.
  TEST EKLEDİYSEN `generate_repository_facts.py --root ..` KOŞ — collection sayısı bayatlar
  ve README'nin gömülü bloğu da (ADIM 60, ADIM 100).
  `--write-report`/`--write-ledger` yolları `--root`'a GÖRE çözülür: `docs/audit/...` yaz,
  `../docs/audit/...` DEĞİL.
  PR AÇIKKEN main ilerlerse: sunucu tarafı "Update branch" DÜĞMESİNE DAYANMA. Dalı güncel
  main üzerine REBASE et; çakışmaları İKİ TARAFI DA KORUYARAK çöz (PROJECT_HISTORY ve
  STAGE2_HANDOFF'ta her iki blok kalır, üretilmiş dosyalar main'den alınıp YENİDEN ÜRETİLİR,
  kickoff demote zinciri bir kademe kaydırılır, gerekirse slice RENUMBER edilir).
  TAVANI TAŞIMA, TAZE BİR --report'tan YENİDEN ÖLÇ.
  Sonra `--report --check-generated --ratchet` + `grep -c '^## ADIM'` (düşmemeli).

  NOT: git guard, komut dizesinin TAMAMINDA "force push" + "main" deseni görürse bloklar —
  fetch/doğrulama ile push'u AYRI Bash çağrılarına böl.

  PR'ı main'e aç, DUR, MERGE ETME.
```
