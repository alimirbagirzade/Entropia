<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 107 LANDED — kabul borcu batch 28 (doc 11 Market Data, backend): `MKD-02` kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 107. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`45ecebc`** (`ADIM 106` / batch 27 = #819, doc 08 Package Library BACKEND). Dal
  kesilirken VE parti seçiminden hemen sonra açık PR listesi **boş** ölçüldü, son kayıt 106 →
  bu slice **107 / batch 28**.
- **Ürün kodu değişmedi** (`backend/src` altında sıfır satır). Migration yok, OpenAPI değişmedi,
  alembic head `0043_i08_registry_strategy_fks`, `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kapanan: `MKD-02` (c1)** — son açık clause'du → `debt_class` **kaldırıldı**.
- **Tavanlar İNDİ: `partial` 56 → 55, `debt_class.B` 24 → 23**; açık borç **63 → 62**
  (A=1 · B=23 · C=6 · D=32). **Doc 11 = 8 covered / 1 partial / 0 uncovered — testle
  kapanabilir sınıf-B satır KALMADI** (kalan `MKD-04` sınıf D: gateway'de market-data
  create/revise aracı yok).

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `backend/tests/integration/test_market_data_type_boundary.py` — bir **şema-sınırı** iddiasının
  kalıbı: üyelik LİTERAL pinlenir (set EŞİTLİĞİ, üretim sabitinden türetme), dışlananların
  öbür düzlemdeki EVİ de pinlenir, wire reddi **gerçek ASGI route'unda** yüzey başına sürülür
  (`_override`/`_client` ADIM 98 idiomu: `app.dependency_overrides[request_context]`), sıfır-satır
  iddiası `expire_all()` sonrası sayımla + yüzey başına pozitif kontrolle kurulur.
- 422 zarfı `{"error": {...}}` altında yuvalanır (`ErrorResponse.error`); tek alan düşen şema
  reddinde `field_path == "body.<alan>"`. Route öneki `/api/v1/...`.
- Create route'u `ETag` başlığı döner; append (`POST .../revisions`) `If-Match` + `timezone_mode`
  ister — pozitif kontrol append'i için create'in ETag'ini verbatim geçir.
- **Ortam bu container'da:** cluster `/var/lib/postgresql/16/main`'de VARDI ama kapalıydı ve
  `entropia` rolü/DB'leri YOKTU → rol + `entropia` + `entropia_esp` DB'leri oluşturuldu,
  `alembic upgrade head` `LC_ALL=C.UTF-8 PYTHONUTF8=1` ile koştu. Her koşudan önce `pg_isready`.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **BİR SINIR İDDİASININ İKİ KUSUR SINIFI VARSA İKİ EKSEN GEREKİR.** Enum'u genişleten kusuru
   yalnız literal üyelik eşitliği görür (route'lar reddetmeye devam ederken bile); route
   tiplemesini gevşeten kusuru yalnız wire testi görür (üyelik testi ona kördür — NC-2'de
   ölçüldü, üyelik YEŞİL kaldı). Tek eksen yazmak diğer kusur sınıfını görünmez bırakır.
2. **İKİNCİ SAVUNMA HATTI VACUITY DEĞİL, AMA İDDİAYI DARALTIR.** Route gevşetilince DB enum
   kolonu yine reddediyor (satır inmiyor) — yani "hiçbir satır yazılmadı" tek başına zayıf bir
   iddia olurdu; testin gerçek pinlediği şey **422 sözleşmesi** (gevşek dünyada red 500'e
   dönüşür). Defter notu bunu açıkça yazıyor.
3. **REDDEDİLEN ÇAĞRININ YÜZEYİ BAŞINA POZİTİF KONTROL** — aynı harness'ın kabul edilen tiple
   gerçekten yazdığı yüzey başına kanıtlanmalı; yoksa sıfır-satır iddiası yazamayan bir
   harness için de geçer.
4. **`ss` + exit 0 yeşil değildir; exit code'u `tail`'den okuma.** Çıktıyı dosyaya yaz,
   `$?`'i ayrı oku, nokta satırını say (`FF...` / `.F...` desenleri NC atfının kanıtıydı).

## Sıradaki iş — ölçülmüş adaylar (yine de kendin ölç)

- **Bitmiş belgeler/yüzeyler:** doc 05 · 18 · 10 · 16 · 22-B · 02-B · 17-B · 01-B · 14-B ·
  21-B · 20-B · 09-B · 06-B · 08-B · **11-B (bu slice)**.
- **Backend'de testle kapanabilir sınıf-B satır KALMADI** (batch 28 tabanında ölçüldü —
  `--report` ile doğrula: kalan B satırlarının hepsi ya bulgu/unfalsifiable şekilli ya da
  frontend clause'u taşıyor).
- **Frontend bitiricileri (sıradaki parti buradan):** `UM-15.c3` (doc 21) · `RC-09.c3`
  (doc 14 — stale/is_current=false projeksiyonla RUN kilidi assert'i, defter notu tarifi
  veriyor) · `CP-03.c4` (doc 06 — server reddi sonrası stale seçim temizliği) · `AT-07`
  (doc 02). Ortam: `cd frontend && npm ci`, vitest `--no-file-parallelism`.
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

Bu prompt yazılırken main `45ecebc` üzerine ADIM 107 / batch 28 yazıldı (doc 11 MARKET DATA
BACKEND, MKD-02). Yine de kendin ölç.

TAVANLAR: bu prompttan OKUMA. Tek otorite acceptance_coverage_baseline.json `ceilings`.
  Ratchet YALNIZ AŞAĞI iner; total_criteria bir TABANDIR. Rebase edersen tavanı TAŞIMA,
  merged ağaçta taze bir --report'tan yeniden ölç.

ORTAM: container ÇIPLAK başlayabilir ve YENİDEN BAŞLAYINCA POSTGRES DÜŞER.
  Bu container'da cluster /var/lib/postgresql/16/main'de ama entropia rolü/DB'leri
  kurulmamış olabilir — ADIM 107 kickoff §çapalar. `alembic upgrade head` için
  LC_ALL=C.UTF-8 PYTHONUTF8=1. Her alt küme koşusundan ÖNCE `pg_isready`;
  `ss` (skipped) + exit 0 bir yeşil DEĞİLDİR; exit code'u `tail`'den OKUMA.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  1) cd backend && python3 ../docs/audit/acceptance_semantic_scan.py --root .. --report
  2) BACKEND'DE TESTLE KAPANABİLİR SINIF-B SATIR KALMADI (batch 28 ölçümü — yine de doğrula).
     Sıradaki parti FRONTEND bitiricilerinden: UM-15.c3 · RC-09.c3 · CP-03.c4 · AT-07
     (`cd frontend && npm ci`, vitest --no-file-parallelism; entropia-frontend-parity kuralları:
     presentation-only, OCC/Idempotency/react-query key'lerine dokunma).
  3) ADAY SEÇTİKTEN SONRA, TEST YAZMADAN ÖNCE:
       grep -rn "<KRİTER-ID>" frontend/src backend/tests   (ADIM 88: kapsama sevk edilmiş olabilir)
     Davranışın sevk edildiğini üründe DOĞRULA; unshipped (D) · unconstructible (C) ·
     unfalsifiable (işaretle) ayır. Bir "X değişmedi" iddiasında ÖNCE X'in kayabileceği
     dünyanın var olduğunu kanıtla (ADIM 106); bir sınır iddiasının İKİ kusur sınıfı varsa
     İKİ eksen yaz (ADIM 107: enum'u genişleten kusuru yalnız literal üyelik, route'u
     gevşeten kusuru yalnız wire testi görür).

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
     (Route zarfı `{"error": {...}}` altında yuvalanır — ADIM 107.)
  g. EZME (satır demetleri) ile EKLEME (tam sıralı listeler) ayrı eksenlerdir.
  h. Bir SEEDER/tablo/enum sınıyorsan beklentiyi LİTERAL yaz — üretimden türetme (ADIM 104/107).
  i. Koşamadığın suite'e (E2E/A11Y) assertion YAZMA; sınırı yaz.
  j. Kriterin SON clause'u kapanıyorsa kriter-düzeyi `status`'ü covered yap ve `debt_class`'ı KALDIR.
  k. YAML notu düz skalerse `: ` ekleyemezsin -> tek tırnağa al, apostrofları ikile.

AÇIK BİR PR VARSA: o dal SENİN çalışma alanın DEĞİL (ADIM 105). Yerelde ilerle, ama commit'i o
  dala bağlama — patch olarak tut, PR merge olunca taze main'e uygula ve suite'leri MERGED
  ağaçta yeniden koştur.

BİTMİŞ: doc 05 · 18 · 10 · 16 · 22-B · 02-B · 17-B · 01-B · 14-B · 21-B · 20-B · 09-B ·
  06-B · 08-B · 11-B. Backend'de kapanabilir sınıf-B satır YOK (yine de ölç).
  Frontend bitiricileri: UM-15.c3 · RC-09.c3 · CP-03.c4 · AT-07.

KAPANIŞ: CLAUDE.md §Session CLOSING 6 madde. Numara + parti etiketini commit'ten hemen önce
  YENİDEN doğrula (dosya yolu ölçümü). TEST EKLEDİYSEN generate_repository_facts.py koş
  (repo KÖKÜNDEN — backend cwd'sinde docs/openapi.json bulamaz, ADIM 107).
  --write-report/--write-ledger yolları --root'a göre: `docs/audit/...`.
  Rebase gerekiyorsa "Update branch" DEĞİL; iki tarafı koruyarak çöz, üretilmişleri yeniden üret,
  tavanı taze --report'tan ölç. Sonra --report --check-generated --ratchet +
  grep -c '^## ADIM' (düşmemeli). git guard: fetch/doğrulama ile push'u AYRI Bash çağrılarına böl.
  PR'ı main'e aç.

DURMA KOŞULU: taze --report'ta testle kapanabilir sınıf-B satır kalmadıysa (backend VE
  frontend), yeni parti AÇMA; durumu raporla ve zinciri bitir.
```
