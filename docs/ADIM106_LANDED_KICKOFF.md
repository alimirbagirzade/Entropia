<!-- doc-status: historical -->
> **TARİHSEL.** Bu kickoff ADIM 107 inince demote edildi; canlı kickoff
> `docs/ADIM107_LANDED_KICKOFF.md`.

# ADIM 106 LANDED — kabul borcu batch 27 (doc 08 Package Library, backend): `PL-07` kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 106. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`680ba1e`** (`ADIM 105` / batch 26 = #818, doc 06 Create Package BACKEND). Dal
  kesilirken açık PR listesi **boş** ölçüldü, son kayıt 105 → bu slice **106 / batch 27**.
  (#818'i bu oturumun promptu "merge et" diyordu — ölçüm zaten merge edilmiş buldu.)
- **Ürün kodu değişmedi** (`backend/src` altında sıfır satır). Migration yok, OpenAPI değişmedi,
  alembic head `0043_i08_registry_strategy_fks`, `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kapanan: `PL-07` (c2)** — son açık clause'du → `debt_class` **kaldırıldı**.
- **Tavanlar İNDİ: `partial` 57 → 56, `debt_class.B` 25 → 24**; açık borç **64 → 63**
  (A=1 · B=24 · C=6 · D=32). **Doc 08 = 19 covered / 2 partial / 0 uncovered — testle
  kapanabilir sınıf-B satır KALMADI** (kalan `PL-08` + `PL-20`, ikisi de sınıf D bulgu).

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `test_strategy_integration.py` sonundaki **"Acceptance batch 27"** bölümü — bir
  **no-auto-repin / pin-kalıcılığı** iddiasının kalıbı: GERÇEK bir ACTIVE paket tohumla
  (`pkg_repo.create_package(owner_principal_id="user_1", package_kind=PackageKind.INDICATOR, …)`),
  gerçek head'i `_valid_payload()`'ın `package_ref`'ine koy, Save et, head'i
  `pkg_cmd.create_package_revision(…, expected_head_revision_id=<N>)` ile ilerlet, **atıf
  muhafızı** (`head != N`) + `expire_all()` sonrası geri okuma + **ikinci Save** eksenlerini ayrı
  assert et.
- **VACUITY ÖLÇÜMÜ ÖNCE:** strateji fixture'larının placeholder pinleri (`pkg_int`/`pkgrev_int`)
  hiçbir satırı adlandırmaz ve `_assert_references_active` **V1-lenient'tir** — placeholder'ların
  üstüne "değişmedi" iddiası kurma. Bu ölçüm aynı zamanda NC'nin ayırt ediciliğinin sebebi:
  kusur yalnız **çözülebilen** köklerde tetiklenir, mevcut testler yeşil kalır.
- `_extract_references` (commands/strategy_draft.py:785) pinleri **verbatim** kenara çevirir;
  `entry_indicator` kenarı `strat_repo.list_references` ile okunur, rol `str(r.dependency_role)`.
- **Ortam bu container'da:** cluster `/var/lib/postgresql/16/main`'de VARDI ama kapalıydı ve
  `entropia` rolü/DB'leri YOKTU → rol + `entropia` + `entropia_esp` DB'leri oluşturuldu,
  `alembic upgrade head` `LC_ALL=C.UTF-8 PYTHONUTF8=1` ile koştu. Her koşudan önce `pg_isready`.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **VACUITY TUZAĞINI TEST YAZMADAN ÖNCE ÖLÇ.** ADIM 100 bu şekli kapanışta öğrenmişti
   (literal `"result_abc123"` hiçbir satırı adlandırmıyordu); bu parti aynı ölçümü **önce**
   yaptı ve harness kararı (gerçek paket tohumla) oradan çıktı. Bir "X değişmedi" iddiasında
   önce X'in kayabileceği bir dünyanın var olduğunu kanıtla.
2. **MEVCUT TESTLERİN YEŞİL KALMASI KUSURUN TASARIMINA GİRER.** NC-1'in kusuru (kenar yazımı
   head'i çözer) bilerek yalnız çözülebilen kökleri etkiler → 24 testte yalnız yeni case
   kırmızı, 23'ü yeşil. Ayırt edicilik tesadüf değil, kusur sınıfı seçiminin sonucudur
   (ADIM 105'in "doğru sebep, yanlış kapsam" dersinin tümleyeni).
3. **NC'NİN GÖRECEĞİ EKSENİ TESTE KOY.** NC-2 (Save config'i head'e yeniden yazar) ancak
   head != pin iken koşan bir Save'den SONRA config okunursa görünür — o eksen (Save2 sonrası
   saklanan config) teste bilerek eklendi. Kontrolü tasarlarken "bu kusuru hangi satır görür"
   sorusunun cevabı testte yoksa, önce ekseni ekle.
4. **`ss` + exit 0 yeşil değildir; exit code'u `tail`'den okuma.** Çıktıyı dosyaya yaz,
   `$?`'i ayrı oku, nokta satırını say (bu oturumda da uygulandı).

## Sıradaki iş — ölçülmüş adaylar (yine de kendin ölç)

- **Bitmiş belgeler/yüzeyler:** doc 05 · 18 · 10 · 16 · 22-B · 02-B · 17-B · 01-B · 14-B ·
  21-B · 20-B · 09-B · 06-B · **08-B (bu slice)**.
- **Kalan sınıf-B backend (batch 27 tabanında ölçüldü — `--report` ile doğrula):** doc 11
  (`MKD-02.c1` — Market Data kanonik şeması yalnız ohlcv/tick_trades/spread_execution kabul
  eder; `MarketDataType` enum üyeliği ve funding-tipli bir market revizyonunun REDDİ hiç
  assert edilmemiş. Defter notu: sınır gerçek — funding/OI/liquidation `ResearchDataType`'ta).
- **Frontend bitiricileri:** `UM-15.c3` (doc 21) · `RC-09.c3` (doc 14) · `CP-03.c4` (doc 06) ·
  `AT-07` (doc 02) — `cd frontend && npm ci`.
- **Bulgu satırları** (kapatmaya çalışma): TL-01.c4, TL-02.c2, TL-11.c3, TL-14.c4, TL-16.c4,
  RF-08.c2, TR-07.c3, RD-01.c4, RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2,
  MB-22.c4, ESP-05.c3.

## Paste-ready resume prompt (bir sonraki oturuma yapıştır)

```
ENTROPIA V18 — kabul borcu (sıradaki parti)

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı, numarayı ve hiçbir sayıyı bu prompttan alma:
  git fetch && git log --oneline origin/main -6
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  mcp__github__list_pull_requests(state=open)
  # NUMARAYI açık PR'ların EKLEDİĞİ docs/ADIM<n>_*.md YOLLARINDAN ölç, başlıktan değil.
  # PARTİ SEÇTİKTEN HEMEN SONRA listeyi BİR KEZ DAHA ölç (ADIM 103 emsali).
  Canlı kickoff = ilk satırında 'doc-status: current' olan EN YÜKSEK numaralı ADIM dosyası.

Bu prompt yazılırken main `680ba1e` üzerine ADIM 106 / batch 27 yazıldı (doc 08 PACKAGE
LIBRARY BACKEND, PL-07). Yine de kendin ölç.

TAVANLAR: bu prompttan OKUMA. Tek otorite acceptance_coverage_baseline.json `ceilings`.
  Ratchet YALNIZ AŞAĞI iner; total_criteria bir TABANDIR. Rebase edersen tavanı TAŞIMA,
  merged ağaçta taze bir --report'tan yeniden ölç.

ORTAM: container ÇIPLAK başlayabilir ve YENİDEN BAŞLAYINCA POSTGRES DÜŞER.
  Bu container'da cluster /var/lib/postgresql/16/main'de ama entropia rolü/DB'leri
  kurulmamış olabilir — ADIM 106 kickoff §çapalar. `alembic upgrade head` için
  LC_ALL=C.UTF-8 PYTHONUTF8=1. Her alt küme koşusundan ÖNCE `pg_isready`;
  `ss` (skipped) + exit 0 bir yeşil DEĞİLDİR; exit code'u `tail`'den OKUMA.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  1) cd backend && python3 ../docs/audit/acceptance_semantic_scan.py --root .. --report
  2) ADAY SEÇTİKTEN SONRA, TEST YAZMADAN ÖNCE:
       grep -rn "<KRİTER-ID>" frontend/src backend/tests   (ADIM 88: kapsama sevk edilmiş olabilir)
     "olay yazılıyor" clause'unda OKUYAN testi ara (ADIM 101/103).
  3) Davranışın sevk edildiğini üründe DOĞRULA; unshipped (D) · unconstructible (C) ·
     unfalsifiable (işaretle) ayır. Bir "X değişmedi" iddiasında ÖNCE X'in kayabileceği
     dünyanın var olduğunu kanıtla — placeholder/fixture pinleri hiçbir satırı
     adlandırmıyor olabilir (ADIM 106: vacuity tuzağını YAZMADAN ÖNCE ölç).

HER CLAUSE İÇİN ZORUNLU:
  a. Mevcut testler bu kusur altında yeşil mi kalıyor? Kalıyorsa yeni assertion BAŞKA eksene bakmalı.
     Ayırt edicilik tesadüf değildir: kusuru MEVCUT testlerin görmeyeceği sınıfta KUR (ADIM 106).
  b. Negatif kontrol koş VE yamanın uygulandığını eşleşme sayısıyla DOĞRULA; geri yazmayı
     `finally`'ye koy; her turdan sonra `git status`.
  c. KIRMIZININ HANGİ ASSERTION'DA olduğunu OKU — ve KAÇ TESTİN kırmızı olduğunu SAY.
     * yanlış sebeple kırmızı (unique kısıt, ön koşul) → REDDET, yeniden kur (ADIM 98/103/104)
     * doğru sebeple ama MEVCUT testleri de kırmızı yapıyor → AYIRT EDİCİ DEĞİL, REDDET (ADIM 105)
  d. Kontrolün kusurunu hangi assertion'ın GÖRECEĞİNİ önceden söyle; o eksen testte yoksa
     önce ekseni EKLE (ADIM 106 NC-2). Gölgeyi KALDIR (ADIM 104); kaldıramıyorsan deftere yaz.
  e. YEŞİL kontrol = yama uygulanmadı VEYA assertion totolojik. Yan etkinin YOKLUĞUNU iddia
     ediyorsan önünde rollback DE identity map DE olamaz → `session.expire_all()`.
     TUZAK: expire'dan SONRA expired nesnenin id'sini okumak MissingGreenlet verir —
     id'leri expire'dan ÖNCE yerel değişkene al (ADIM 105/106).
  f. Bir GÖVDE iddiasını key lookup'la kurma; tam sözlük eşitliği ya da substring taraması.
  g. EZME (satır demetleri) ile EKLEME (tam sıralı listeler) ayrı eksenlerdir.
  h. Bir SEEDER/tablo sınıyorsan beklentiyi LİTERAL yaz — üretimden türetme (ADIM 104).
  i. Koşamadığın suite'e (E2E/A11Y/frontend) assertion YAZMA; sınırı yaz.
  j. Kriterin SON clause'u kapanıyorsa kriter-düzeyi `status`'ü covered yap ve `debt_class`'ı KALDIR.
  k. YAML notu düz skalerse `: ` ekleyemezsin -> tek tırnağa al, apostrofları ikile.

AÇIK BİR PR VARSA: o dal SENİN çalışma alanın DEĞİL (ADIM 105). Yerelde ilerle, ama commit'i o
  dala bağlama — patch olarak tut, PR merge olunca taze main'e uygula ve suite'leri MERGED
  ağaçta yeniden koştur.

BİTMİŞ: doc 05 · 18 · 10 · 16 · 22-B · 02-B · 17-B · 01-B · 14-B · 21-B · 20-B · 09-B ·
  06-B · 08-B. Kalan backend yoğunluğu (yine de ölç): doc 11 (MKD-02.c1).
  Frontend bitiricileri: UM-15.c3 · RC-09.c3 · CP-03.c4 · AT-07 (`cd frontend && npm ci`).

KAPANIŞ: CLAUDE.md §Session CLOSING 6 madde. Numara + parti etiketini commit'ten hemen önce
  YENİDEN doğrula (dosya yolu ölçümü). TEST EKLEDİYSEN generate_repository_facts.py koş.
  --write-report/--write-ledger yolları --root'a göre: `docs/audit/...`.
  Rebase gerekiyorsa "Update branch" DEĞİL; iki tarafı koruyarak çöz, üretilmişleri yeniden üret,
  tavanı taze --report'tan ölç. Sonra --report --check-generated --ratchet +
  grep -c '^## ADIM' (düşmemeli). git guard: fetch/doğrulama ile push'u AYRI Bash çağrılarına böl.
  PR'ı main'e aç.
```
