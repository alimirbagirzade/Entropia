<!-- doc-status: historical -->
> **HISTORICAL — demoted by ADIM 102 (kabul borcu batch 23, doc 16 Results History BACKEND).**
> Canlı kickoff `docs/ADIM102_LANDED_KICKOFF.md`. Aşağısı yazıldığı andaki durumu kaydeder;
> tavanları **bayattır** (`partial` 64 / `debt_class.B` 32 → ADIM 102 sonrası **62 / 30**).

# ADIM 101 LANDED — kabul borcu batch 22 (doc 21 User Manual, backend): iki kriter kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 101. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`7f4d927`** (`ADIM 100` / batch 21 = #813, doc 22 Future Dev BACKEND). Dal
  kesilirken `list_pull_requests(state=open)` **boş** döndü — son üç partinin kaydettiği gibi bu
  bir **garanti değil, anlık görüntüdür**. **Ürün kodu değişmedi** (`backend/src` altında sıfır
  satır); diff = iki yeni integration case + kabul defteri + üretilmiş artefaktlar. Migration yok,
  OpenAPI değişmedi, alembic head `0043_i08_registry_strategy_fks`,
  `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kapananlar: `UM-08` (c5) · `UM-13` (c3)** — doc 21'in BACKEND yüzeyi. İkisi de kendi
  kriterinin son açık clause'uydu → ikisinin de `debt_class`'ı **kaldırıldı**.
- **Tavanlar İNDİ: `partial` 66 → 64, `debt_class.B` 34 → 32**; açık borç **73 → 71**
  (A=1 · B=32 · C=6 · D=32).
- **Doc 21 = 15 covered / 3 partial** (13 → 15, 5 → 3). Kalan üçünün **hiçbiri backend test borcu
  değil**: `UM-04` (c4, sınıf D) · `UM-12` (c3, sınıf D) · **`UM-15` (c3, sınıf B ama FRONTEND**
  — 409 `MANUAL_STREAM_CONFLICT` sonrası istemcinin stream'i yeniden hidratlaması).
  **Doc 21'in BACKEND borcu bitti.**

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `backend/tests/integration/test_user_manual.py` — dosyanın sonundaki **"Acceptance batch 22"**
  bölümü. Üç yeniden kullanılabilir parça:
  - **`_event_trail(session, document_id)`** — belgenin TÜM publication trail'ini
    `resulting_stream_version` sırasında **demet listesi** olarak döndürür. Bir "iz bozulmadı"
    iddiası kuracak her slice bunu ödünç alabilir: **demetleri** karşılaştırmak bir **ezmeyi**,
    tam sıralı **listeyi** karşılaştırmak bir **eklemeyi** yakalar, `count(*)` ikisini de kaçırır.
  - **`_append_in_own_transaction(barrier, *, title, content)`** — kendi engine'i, bağlantısı ve
    transaction'ı olan tek bir append; `asyncio.Barrier` ile ikinci bir görevle **birlikte
    salınır**. Advisory-lock/unique-constraint çekişmesi ölçecek her slice için hazır harness.
    **Bariyer komuttan ÖNCE salınır** — komutun içinde salmak kilitlenir.
  - **Mevcut yardımcılar** `_publication_event` (`.one()` → *"tam olarak bir tane"* de pinler),
    `_latest_audit`, `_latest_outbox`, `_seed`, `_add_doc`, `_count` aynen kullanılabilir.
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
  `export TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_um"`.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **GÖLGE KALDIRILABİLİR, sadece kaydedilmek zorunda değil.** Bir testin ilk assertion'ı
   sonrakileri gölgeler: iz hakkındaki çoğu kusur zaten (1)'de kırmızı verir, yani (4)'ün kendi
   ekseni ölçülemez. Çözüm, gölgeyi **atlayan** bir kontrol tasarlamaktır — NC-4 belgenin ESKİ
   olaylarını siler ama delete olayını **doğru alanlarla** yazar → (1)(2)(3) **geçer**, yalnız
   sıralı iz karşılaştırması düşer. ADIM 100 gölgelenen assertion'ı deftere yazmakla yetinmişti;
   önce **kaldırmayı** dene.
2. **BİR YARIŞ TESTİNİN VACUITY KANITI, KENDİ NEGATİF KONTROLÜDÜR.** *"İki çağıran gerçekten
   örtüşüyor"* iddiası doğrudan gözlenemez. Ama kilit kaldırılınca **çakışma oluyorsa**, örtüşme
   ölçülmüş demektir — sıralı iki append çakışmazdı. Kontrolü **iki yönde de** koştur: kilitle
   8/8 yeşil, kilitsiz 5/5 kırmızı. Tek bir kırmızı, deterministik olduğunu söylemez.
3. **BARİYERİ KİLİDİN İÇİNE KOYMA.** İki görevi komutun İÇİNDE buluşturmak **kilitlenir**:
   birinci görev advisory kilidi tutarken ikinciyi bekler, ikinci ise kilidi bekler. Rendezvous
   **kilit alınmadan önce** olmalı; ondan sonrası zaten üretimin kendi serileştirmesidir.
4. **"OLAY YAZILIYOR" İLE "OLAY OKUNUYOR" AYRI ŞEYLERDİR.** `UM-08.c5`'in tamamı bundan ibaretti:
   üç düzlem de yazılıyordu, hiçbiri hiçbir testte okunmuyordu, ve **tüm iz komuttan silinse 27
   test yeşil kalırdı**. Bir defter satırı *"olay emit ediliyor"* diyorsa bu clause'un
   **kapandığı** anlamına gelmez — `grep` ile okuyan testi ara.
5. **BİR GÖVDE İDDİASINI TAM SÖZLÜK EŞİTLİĞİYLE KUR.** `outbox.payload == {...}` bir anahtarın
   **düşmesini** de yakalar; `payload["x"] == y` yakalamaz.

## Sıradaki iş — ölçülmüş adaylar (yine de kendin ölç)

- **Bitmiş belgeler/yüzeyler:** doc 05 · doc 18 · doc 10 · doc 22-BACKEND · doc 02-BACKEND ·
  doc 17-BACKEND · doc 01-BACKEND · doc 14-BACKEND · **doc 21-BACKEND (bu slice)**.
- **Kalan sınıf-B yoğunluğu:** doc 09 (ESP: `ESP-03` gerçek seeder'ı hiç çağrılmıyor,
  `ESP-05` resolver payload koruması, `ESP-20` yabancı aktörle rol filtresi) · doc 06 (CP:
  `CP-09` Send replay'i hiç iki kez sürülmüyor, `CP-13` Supervisor/Agent approval-request izni) ·
  doc 16 (RH: `RH-13`, `RH-14` — ikisi de "Result satırı kıpırdamadı", `_event_trail` deseni
  doğrudan uygulanır) · doc 20 (TR: **`TR-08.c4` `UM-08.c5`'in birebir ikizi** — restore yolunda
  `OutboxEvent` hiç sorgulanmıyor) · doc 08 (`PL-07` pinlenmiş indicator revizyonu).
- **`UM-15.c3`** doc 21'i bitirir ama **FRONTEND** (`cd frontend && npm ci`).

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
  Canlı kickoff = ilk satırında 'doc-status: current' olan EN YÜKSEK numaralı ADIM dosyası:
    for f in docs/ADIM*KICKOFF.md; do head -1 "$f" | grep -q 'doc-status: current' && echo "$f"; done
  Onu oku, bunu değil.

Bu prompt yazılırken main `7f4d927` üzerine ADIM 101 / batch 22 yazıldı (doc 21 User Manual
BACKEND, UM-08 + UM-13). Yine de kendin ölç.

TAVANLAR: bu prompttan OKUMA. Tek otorite acceptance_coverage_baseline.json `ceilings`.
  Ratchet YALNIZ AŞAĞI iner; total_criteria bir TABANDIR.

ORTAM: container ÇIPLAK başlayabilir — backend/.venv YOK, Postgres cluster YOK, ve
  container yeniden başlayınca Postgres DÜŞER.
  Kurulum dizisi: docs/ADIM101_LANDED_KICKOFF.md §çapalar.
  `alembic upgrade head` için LC_ALL=C.UTF-8 PYTHONUTF8=1 kullan — en_US.UTF-8 bu imajda
  UnicodeDecodeError verir. `ss` (skipped) + exit 0 bir yeşil DEĞİLDİR.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  1) cd backend && python3 ../docs/audit/acceptance_semantic_scan.py --root .. --report
  2) ADAY SEÇTİKTEN SONRA, TEST YAZMADAN ÖNCE:
       grep -rn "<KRİTER-ID>" frontend/src backend/tests
     Kapsama zaten sevk edilmiş olabilir -> cite et, yazma (ADIM 88).
  3) Kriterin adlandırdığı davranışın sevk edildiğini üründe DOĞRULA. Üç şekli ayır:
     unshipped (D) · unconstructible (C) · unfalsifiable (işaretle, kapatma).
  4) "X kıpırdamadı" clause'unda İLK SORU: X test veritabanında GERÇEKTEN VAR MI? (ADIM 100)
     "Olay yazılıyor" clause'unda İLK SORU: onu OKUYAN bir test var mı? (ADIM 101 — üç düzlem
     de yazılıyordu, hiçbiri okunmuyordu, iz silinse 27 test yeşil kalırdı.)

HER CLAUSE İÇİN ZORUNLU:
  a. Mevcut testler bu kusur altında yeşil mi kalıyor? Kalıyorsa yeni assertion BAŞKA bir
     eksene bakmalı — yoksa işaretleme yapıyorsun, kapsama değil.
  b. Negatif kontrol koş VE YAMANIN UYGULANDIĞINI DOĞRULA; geri yazmayı `finally`'ye koy —
     AMA `finally` süreç SIGTERM alırsa KOŞMAZ: her turdan sonra `git status` (ADIM 100).
  c. KIRMIZININ HANGİ ASSERTION'DA OLDUĞUNU OKU — ve o HEDEF assertion mı? Değilse KONTROLÜ
     REDDET, yenisini kur (ADIM 98). İlk kırmızı sonrakini GÖLGELER: önce gölgeyi KALDIRAN
     bir kontrol tasarla (ADIM 101 NC-4: gölgeleyen assertion'ları GEÇİREN bir kusur kur);
     ancak kaldırılamıyorsa gölgelendiğini DEFTERE YAZ (ADIM 100).
  d. YEŞİL kontrol = yama uygulanmadı VEYA assertion totolojik. Bir yan etkinin YOKLUĞUNU
     iddia ediyorsan, önünde onu geri alan hiçbir şey olmamalı — rollback DE, identity map DE:
     integration session'ı `expire_on_commit=False` kurar, geri okumadan önce
     `session.expire_all()` (ADIM 100).
  e. Bir GÖVDE iddiasını key lookup'la kurma — tam sözlük eşitliği ya da serileştirilmiş
     metne karşı substring taraması (ADIM 98/101).
  f. EZME ile EKLEME ayrı kusur sınıflarıdır: satır DEMETLERİNİ karşılaştır (ezme) VE tam
     sıralı LİSTELERİ karşılaştır (ekleme); `count(*)` ikisini de kaçırır (ADIM 100/101 —
     hazır yardımcı: `test_user_manual.py::_event_trail`).
  g. Koşamadığın suite'e (E2E/A11Y/frontend) assertion YAZMA; sınırı yaz.
  h. Kriterin SON clause'u kapanıyorsa KRİTER-DÜZEYİ `status`'ü de covered yap ve
     `debt_class`'ı KALDIR.
  i. YAML notu düz skalerse `: ` ekleyemezsin -> tek tırnağa al, apostrofları ikile.
  j. EŞZAMANLILIK clause'u seçtiysen: iki AYRI engine/bağlantı + `asyncio.Barrier`, bariyer
     komuttan ÖNCE salınır (içeride salmak KİLİTLENİR). Hazır harness:
     `test_user_manual.py::_append_in_own_transaction`. Determinizmi İKİ YÖNDE ölç —
     kusursuz N/N yeşil VE kusurlu N/N kırmızı (ADIM 101).

KAPATMAYA ÇALIŞMA (bulgular): TL-01.c4, TL-02.c2, TL-11.c3, TL-14.c4, TL-16.c4, RF-08.c2,
  TR-07.c3, RD-01.c4, RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2, MB-22.c4
  + `unfalsifiable: true` clause'lar. Yeniden sınıflandırma tavan yükseltir = adjudication.

BİTMİŞ OLANLAR: doc 05 · doc 18 · doc 10 · doc 22-BACKEND · doc 02-BACKEND · doc 17-BACKEND ·
  doc 01-BACKEND · doc 14-BACKEND · doc 21-BACKEND. Kalan sınıf-B yoğunluğu (yine de ölç):
  doc 09 (ESP) · doc 06 (CP) · doc 16 (RH) · doc 20 (TR) · doc 08 (PL).
  TR-08.c4 EN UCUZ satır: UM-08.c5'in birebir ikizi — restore `add_outbox_event` çağırıyor ama
  test yalnız `AuditEvent.event_kind` okuyor, `OutboxEvent` hiç sorgulanmıyor.
  RH-13/RH-14 "Result satırı kıpırdamadı" şeklinde; `_event_trail` deseni doğrudan uygulanır.
  UM-15.c3 ve RC-09.c3 kendi belgelerini bitirir ama FRONTEND (`cd frontend && npm ci`).

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

  PR'ı main'e aç. Merge kararı insanındır — aksi açıkça söylenmediyse MERGE ETME.
```
