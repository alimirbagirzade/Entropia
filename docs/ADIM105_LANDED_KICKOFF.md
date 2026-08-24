<!-- doc-status: historical -->
> **TARİHSEL.** Bu kickoff ADIM 105'in kapanışında yazıldı; ADIM 106 (batch 27) inince
> demote edildi. Canlı devam noktası: `docs/ADIM106_LANDED_KICKOFF.md`.

# ADIM 105 LANDED — kabul borcu batch 26 (doc 06 Create Package, backend): `CP-09` + `CP-13` kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 105. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`4c32bec`** (`ADIM 104` / batch 25 = #817, doc 09 ESP BACKEND). Kapanışta açık PR
  listesi **boş** ölçüldü, son kayıt 104 → bu slice **105 / batch 26**.
- **Ürün kodu değişmedi** (`backend/src` altında sıfır satır). Migration yok, OpenAPI değişmedi,
  alembic head `0043_i08_registry_strategy_fks`, `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kapananlar: `CP-09` (c2) · `CP-13` (c4)** — ikisi de son açık clause'du → ikisinin de
  `debt_class`'ı **kaldırıldı**.
- **Tavanlar İNDİ: `partial` 59 → 57, `debt_class.B` 27 → 25**; açık borç **66 → 64**
  (A=1 · B=25 · C=6 · D=32). **Doc 06 = 12 covered / 3 partial / 1 uncovered.**

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `test_create_package_persistence.py` sonundaki **"Acceptance batch 26"** bölümü — bir
  **idempotency replay** iddiasının kalıbı: yanıtın **tam sözlük** karşılaştırması (kimlik ekseni)
  + yan etki **sayısı** (Job satırı) + ilk çağrının gerçekten indiğine dair vacuity muhafızı.
  Mevcut harness (`_seed_principals`, `_seed_python_resolver`, `_seed_family`,
  `_create_indicator_request`, `_run_precheck`, `_count`) aynen ödünç alınabilir.
- `test_library_approval.py` sonundaki bölüm — bir **rol izni** iddiasının kalıbı:
  `@pytest.mark.parametrize` ile iki principal, `_seed_actor_principal(session, actor)` (AGENT
  için `principal_type`'ı aktörden alır), `_make_pkg(owner=actor.principal_id)`, ve **izin +
  yasak aynı kök üzerinde**.
- **TUZAK, iki kez ısırdı:** `session.expire_all()`'dan **sonra** expire edilmiş bir nesnenin
  id'sini okumak senkron lazy-load tetikler → `MissingGreenlet`. Id'leri **expire'dan önce**
  yerel değişkene al (`entity_id = root.entity_id`), sonra `await session.get(...)` ile yeniden
  yükle.
- **Ortam:** container bu oturumda **üç kez** yeniden başladı, Postgres her seferinde düştü. Her
  alt küme koşusundan önce `pg_isready`; kurulum dizisi `docs/ADIM101_LANDED_KICKOFF.md` §çapalar.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **BİR NEGATİF KONTROL, KIRMIZI VERDİĞİ HÂLDE REDDEDİLEBİLİR.** Kontrolün iki işi vardır:
   assertion'ın **canlı** olduğunu göstermek ve **boşluğun gerçek** olduğunu göstermek. İkincisi
   ancak **mevcut suite o kusur altında YEŞİL kalırsa** kanıtlanır. İlk NC'im 10 testi birden
   (mevcutlar dahil) kırmızı yaptı → doğru sebeple kırmızıydı ama **ayırt edici değildi**;
   reddedilip *"USER+Admin geçer, yalnız Supervisor/Agent reddedilir"* biçiminde yeniden kuruldu
   → 30 testte yalnız iki yeni case. Batch 24/25 *"yanlış sebeple kırmızı"* şeklini öğretmişti;
   bu üçüncü şekil: **doğru sebep, yanlış kapsam.**
2. **AÇIK BİR PR'IN DALI, SONRAKİ PARTİNİN ÇALIŞMA ALANI DEĞİLDİR.** Yerelde ilerlemek serbest,
   ama commit'i o dala bağlamak PR'ın sözleşmesini bozar: iki parti karışır, ~48 dk CI baştan
   başlar, ve yeni testler collection sayısını oynattığı için `repository_facts --check` PR'ı
   **kırmızıya çevirir**. Çare: işi **patch olarak** dışarı al, dalı origin ile aynıya sıfırla,
   merge sonrası taze main'e uygula ve **suite'leri merged ağaçta yeniden koştur**.
3. **KAPATILAMAYAN EKSENİ ZORLAMA, YAZ.** `CP-09.c2`'nin iki ekseni tek satırlık hiçbir kusurda
   ayrışmıyor (enqueue'yu idempotent gövdenin dışına almak **birinci** çağrıyı da değiştirir ve
   kırmızı vacuity muhafızına düşer). Eksen assert edildi, bağımsız kontrolü olmadığı **deftere
   yazıldı** (ADIM 100 emsali).
4. **BİR İZİN CLAUSE'UNDA KAPININ GENİŞLİĞİNİ ÖLÇ.** `request_package_approval` Owner-or-Admin;
   yani *"Supervisor/Agent approval request oluşturabilir"* **kendi** adayları için doğrudur.
   Başkasının adayı için reddedilir — bu, kriterin iddiası değil, ölçülmüş **sınır**.

## Sıradaki iş — ölçülmüş adaylar (yine de kendin ölç)

- **Bitmiş belgeler/yüzeyler:** doc 05 · 18 · 10 · 16 · 22-B · 02-B · 17-B · 01-B · 14-B · 21-B ·
  20-B · 09-B · **06-B (bu slice)**.
- **Kalan sınıf-B (batch 26 tabanında ölçüldü — `--report` ile doğrula):** doc 08 (`PL-07.c2` —
  pinlenmiş indicator revizyonu N+1 head'den sonra hâlâ N'i adlandırır; literal dizi hiç
  koşulmamış, yapı taşları ayrı ayrı kanıtlı) · doc 11 (`MKD-02.c1` — Market Data kanonik şeması
  yalnız ohlcv/tick_trades/spread_execution kabul eder; enum üyeliği ve funding-tipli bir market
  revizyonunun reddi hiç assert edilmemiş).
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
  # PARTİ SEÇTİKTEN HEMEN SONRA listeyi BİR KEZ DAHA ölç (ADIM 103: boş liste alındığı
  # oturumu bile kapsamaz — o partide çift iş bütünüyle geri alındı).
  Canlı kickoff = ilk satırında 'doc-status: current' olan EN YÜKSEK numaralı ADIM dosyası.

Bu prompt yazılırken main `4c32bec` üzerine ADIM 105 / batch 26 yazıldı (doc 06 CREATE PACKAGE
BACKEND, CP-09 + CP-13). Yine de kendin ölç.

TAVANLAR: bu prompttan OKUMA. Tek otorite acceptance_coverage_baseline.json `ceilings`.
  Ratchet YALNIZ AŞAĞI iner; total_criteria bir TABANDIR. Rebase edersen tavanı TAŞIMA,
  merged ağaçta taze bir --report'tan yeniden ölç.

ORTAM: container ÇIPLAK başlayabilir ve YENİDEN BAŞLAYINCA POSTGRES DÜŞER (bu oturumda üç kez).
  Kurulum dizisi: docs/ADIM101_LANDED_KICKOFF.md §çapalar.
  `alembic upgrade head` için LC_ALL=C.UTF-8 PYTHONUTF8=1.
  Her alt küme koşusundan ÖNCE `pg_isready`; `ss` (skipped) + exit 0 bir yeşil DEĞİLDİR.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  1) cd backend && python3 ../docs/audit/acceptance_semantic_scan.py --root .. --report
  2) ADAY SEÇTİKTEN SONRA, TEST YAZMADAN ÖNCE:
       grep -rn "<KRİTER-ID>" frontend/src backend/tests   (ADIM 88: kapsama sevk edilmiş olabilir)
     "olay yazılıyor" clause'unda OKUYAN testi ara (ADIM 101/103).
  3) Davranışın sevk edildiğini üründe DOĞRULA; unshipped (D) · unconstructible (C) ·
     unfalsifiable (işaretle) ayır. ADIM 104: bir clause'un SENARYOSU hiç olmayabilir.
     ADIM 105: bir İZİN clause'unda kapının GENİŞLİĞİNİ ölç (owner-only mu, rol tabanlı mı) —
     iddia genelde aktörün KENDİ nesnesi içindir.

HER CLAUSE İÇİN ZORUNLU:
  a. Mevcut testler bu kusur altında yeşil mi kalıyor? Kalıyorsa yeni assertion BAŞKA eksene bakmalı.
  b. Negatif kontrol koş VE yamanın uygulandığını eşleşme sayısıyla DOĞRULA; geri yazmayı
     `finally`'ye koy; her turdan sonra `git status`.
  c. KIRMIZININ HANGİ ASSERTION'DA olduğunu OKU — ve KAÇ TESTİN kırmızı olduğunu SAY.
     * yanlış sebeple kırmızı (unique kısıt, ön koşul) → REDDET, yeniden kur (ADIM 98/103/104)
     * doğru sebeple ama MEVCUT testleri de kırmızı yapıyor → AYIRT EDİCİ DEĞİL, REDDET ve
       kusuru daralt (ADIM 105: 10 kırmızı → yeniden kur → 30 testte yalnız 2 yeni case)
  d. Gölgeyi KALDIR: kusuru, önceki eksenleri GEÇİRECEK biçimde kur (ADIM 104 NC-4).
     Kaldıramıyorsan gölgelendiğini/ayrışmadığını DEFTERE yaz (ADIM 100/105) — ZORLAMA.
  e. YEŞİL kontrol = yama uygulanmadı VEYA assertion totolojik. Yan etkinin YOKLUĞUNU iddia
     ediyorsan önünde rollback DE identity map DE olamaz → `session.expire_all()`.
     TUZAK: expire'dan SONRA expired bir nesnenin id'sini okumak MissingGreenlet verir —
     id'leri expire'dan ÖNCE yerel değişkene al (ADIM 105).
  f. Bir GÖVDE iddiasını key lookup'la kurma; tam sözlük eşitliği ya da substring taraması.
  g. EZME (satır demetleri) ile EKLEME (tam sıralı listeler) ayrı eksenlerdir; `count(*)` ikisini
     de kaçırır.
  h. Bir SEEDER/tablo sınıyorsan beklentiyi LİTERAL yaz — üretimden türetme (ADIM 104).
  i. Koşamadığın suite'e (E2E/A11Y/frontend) assertion YAZMA; sınırı yaz.
  j. Kriterin SON clause'u kapanıyorsa kriter-düzeyi `status`'ü covered yap ve `debt_class`'ı KALDIR.
  k. YAML notu düz skalerse `: ` ekleyemezsin -> tek tırnağa al, apostrofları ikile.

AÇIK BİR PR VARSA: o dal SENİN çalışma alanın DEĞİL (ADIM 105). Yerelde ilerle, ama commit'i o
  dala bağlama — patch olarak tut, PR merge olunca taze main'e uygula ve suite'leri MERGED
  ağaçta yeniden koştur.

BİTMİŞ: doc 05 · 18 · 10 · 16 · 22-B · 02-B · 17-B · 01-B · 14-B · 21-B · 20-B · 09-B · 06-B.
  Kalan yoğunluk (yine de ölç): doc 08 (PL-07.c2) · doc 11 (MKD-02.c1).
  Frontend bitiricileri: UM-15.c3 · RC-09.c3 · CP-03.c4 · AT-07 (`cd frontend && npm ci`).

KAPANIŞ: CLAUDE.md §Session CLOSING 6 madde. Numara + parti etiketini commit'ten hemen önce
  YENİDEN doğrula (dosya yolu ölçümü). TEST EKLEDİYSEN generate_repository_facts.py koş.
  --write-report/--write-ledger yolları --root'a göre: `docs/audit/...`.
  Rebase gerekiyorsa "Update branch" DEĞİL; iki tarafı koruyarak çöz, üretilmişleri yeniden üret,
  tavanı taze --report'tan ölç. Sonra --report --check-generated --ratchet +
  grep -c '^## ADIM' (düşmemeli). git guard: fetch/doğrulama ile push'u AYRI Bash çağrılarına böl.
  PR'ı main'e aç; MERGE ETME — karar insanın.
```
