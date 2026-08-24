<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 104 LANDED — kabul borcu batch 25 (doc 09 ESP, backend): `ESP-20` + `ESP-03` kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 104. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`b80388a`** (`ADIM 103` / batch 24 = #816, doc 20 Trash BACKEND). Dal kesilirken ve
  kapanışta **iki kez** ölçüldü: açık PR yok, son kayıt 103 → bu slice **104 / batch 25**.
- **Ürün kodu değişmedi** (`backend/src` altında sıfır satır). Migration yok, OpenAPI değişmedi,
  alembic head `0043_i08_registry_strategy_fks`, `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kapananlar: `ESP-20` (c2 + c3) · `ESP-03` (c4)** — ikisi de kendi kriterinin son açık
  clause'uydu → ikisinin de `debt_class`'ı **kaldırıldı**.
- **Tavanlar İNDİ: `partial` 61 → 59, `debt_class.B` 29 → 27**; açık borç **68 → 66**
  (A=1 · B=27 · C=6 · D=32). **Doc 09 = 17 covered / 3 partial.**

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `backend/tests/integration/test_esp_persistence.py` sonundaki **"Acceptance batch 25"** bölümü:
  - **`_scoped_rows(session, actor)`** — scoped resolver listesini `canonical_key`'e göre sözlük
    olarak döndürür; bir görünürlük/rol iddiası kuracak her slice ödünç alabilir.
  - **`FOREIGN` aktörü + pozitif kontrol deseni** — yabancı reddi kurarken **aynı satır** üzerinde
    sahibin çağrısını da sür; yoksa red *"kim sordu"*ya değil satırın yokluğuna atfedilebilir.
  - **`_NullLog`** — seed yardımcılarını testten çağırmak için (idiom `test_acceptance_esp_package_gaps`'ten).
  - **Literal fixture tablosu** (`_EXPECTED_TA_FIXTURES`) — bir seeder'ı sınarken beklentiyi
    **üretim tuple'ından TÜRETME**; türetirsen seeder'ı kendisiyle karşılaştırırsın.
- **Negatif kontrol koşucusu** scratchpad'de (`nc_esp.py`): yamayı eşleşme sayısıyla doğrular,
  `finally`'de geri yazar, hedef test dosyalarını izole DB'de koşar.
- **Ortam:** ADIM 101 kickoff'undaki kurulum dizisi geçerli. Bu oturumda container **iki kez**
  yeniden başladı ve Postgres her seferinde düştü → alt küme koşusundan önce `pg_isready`.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **BİR UNIQUE KISIT, ASSERTION'IN YERİNE GEÇEBİLİR (ikinci kez).** NC-5'in ilk sürümü kırmızı
   verdi ama `uq_embedded_resolver_registry_key` ihlaliyle — sınanan assertion'a hiç ulaşmadan.
   Kontrol **reddedilir**, kusur DB kısıdını tetiklemeyen bir şekilde yeniden kurulur. Batch 24'te
   aynısı `uq_metric_value_result_key` ile olmuştu: bu artık bir **desen**, tesadüf değil.
2. **GÖLGEYİ KALDIRMANIN ŞEKLİ: kusuru, önceki ekseni GEÇİRECEK biçimde kur.** NC-4 fixture'ı
   yeniden adlandırıp **anahtarını korudu** → anahtar/trust assertion'ları geçti, kırmızı yalnız ad
   assertion'ına düştü. Böylece ad ekseni kendi başına ölçüldü (ADIM 101 kuralı uygulandı).
3. **BİR SEEDER'I SINARKEN BEKLENTİYİ LİTERAL YAZ.** `_ESP_TA_RESOLVERS`'tan türetilen bir
   beklenti, düşen/yanlış yazılan bir anahtarla birlikte **sessizce** küçülür ve test yeşil kalır.
4. **"PREDICATE VAR VE UNIT-TEST'Lİ" ≠ "SORGU ONU UYGULUYOR".** ESP-20'nin tamamı buydu: predicate
   doğruydu, iki sorguya da bağlıydı, ama hiçbir test **yabancı bir aktörle** çağırmıyordu — filtre
   satırı silinse mevcut testler yeşil kalırdı. Bir görünürlük clause'unda ilk soru: *o sorguyu
   sahibi OLMAYAN biri olarak sürüyor muyuz?*
5. **BİR CLAUSE'UN SENARYOSU HİÇ OLMAYABİLİR.** `ESP-05.c3` bir **yeniden atamanın** yan etkilerini
   soruyor; ESP kökleri rationale-assignable değil, yani gözlenecek işlem yok. Kardeş clause'un
   (`c2`) `covered` olması aldatıcıdır — o **farklı bir paket türü** üzerinde koşuyor.

## Sıradaki iş — ölçülmüş adaylar (yine de kendin ölç)

- **Bitmiş belgeler/yüzeyler:** doc 05 · 18 · 10 · 16 · 22-B · 02-B · 17-B · 01-B · 14-B · 21-B ·
  20-B · **09-B (bu slice; kalan üç satır: `ESP-05` bulgu + iki sınıf C/D)**.
- **Kalan sınıf-B yoğunluğu (batch 25 tabanında ölçüldü):** doc 06 (CP: **`CP-09.c2`** Send
  replay'i aynı Idempotency-Key ile hiç iki kez sürülmüyor — `submit_candidate_generation`
  `run_idempotent` ile sarılı ama testlerde anahtar yalnız C.D.P çağrısına geçiyor; **`CP-13.c4`**
  Supervisor/Agent'ın approval request **oluşturabildiği** hiç sürülmemiş — yasak yarısı iki
  principal için de kanıtlı; `CP-03.c4` **frontend**) · doc 08 (`PL-07.c2` — pinlenmiş indicator
  revizyonu N+1 head'den sonra hâlâ N'i adlandırır; literal dizi hiç koşulmamış) ·
  doc 11 (`MKD-02.c1` — Market Data kanonik şeması yalnız üç tipi kabul eder; enum üyeliği ve
  funding-tipli bir market revizyonunun reddi hiç assert edilmemiş).
- **Frontend bitiricileri:** `UM-15.c3` (doc 21) · `RC-09.c3` (doc 14) · `CP-03.c4` (doc 06) ·
  `AT-07` (doc 02) — `cd frontend && npm ci`.

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
  Canlı kickoff = ilk satırında 'doc-status: current' olan EN YÜKSEK numaralı ADIM dosyası:
    for f in docs/ADIM*KICKOFF.md; do head -1 "$f" | grep -q 'doc-status: current' && echo "$f"; done
  Onu oku.

Bu prompt yazılırken main `b80388a` üzerine ADIM 104 / batch 25 yazıldı (doc 09 ESP BACKEND,
ESP-20 + ESP-03). Yine de kendin ölç.

TAVANLAR: bu prompttan OKUMA. Tek otorite acceptance_coverage_baseline.json `ceilings`.
  Ratchet YALNIZ AŞAĞI iner; total_criteria bir TABANDIR. Rebase edersen tavanı TAŞIMA,
  merged ağaçta taze bir --report'tan yeniden ölç.

ORTAM: container ÇIPLAK başlayabilir ve YENİDEN BAŞLAYINCA POSTGRES DÜŞER.
  Kurulum dizisi: docs/ADIM101_LANDED_KICKOFF.md §çapalar.
  `alembic upgrade head` için LC_ALL=C.UTF-8 PYTHONUTF8=1.
  Her alt küme koşusundan önce `pg_isready`; `ss` (skipped) + exit 0 bir yeşil DEĞİLDİR.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  1) cd backend && python3 ../docs/audit/acceptance_semantic_scan.py --root .. --report
  2) ADAY SEÇTİKTEN SONRA, TEST YAZMADAN ÖNCE:
       grep -rn "<KRİTER-ID>" frontend/src backend/tests   (ADIM 88: kapsama sevk edilmiş olabilir)
     "olay yazılıyor" clause'unda OKUYAN testi ara (ADIM 101/103).
  3) Davranışın sevk edildiğini üründe DOĞRULA; unshipped (D) · unconstructible (C) ·
     unfalsifiable (işaretle) ayır. ADIM 104: bir clause'un SENARYOSU hiç olmayabilir — kardeş
     clause'un covered olması aldatıcıdır, o başka bir tür/yüzey üzerinde koşuyor olabilir.

HER CLAUSE İÇİN ZORUNLU:
  a. Mevcut testler bu kusur altında yeşil mi kalıyor? Kalıyorsa yeni assertion BAŞKA eksene bakmalı.
     ("Predicate var ve unit-test'li" ≠ "sorgu onu uyguluyor" — ADIM 104.)
  b. Negatif kontrol koş VE yamanın uygulandığını eşleşme sayısıyla DOĞRULA; geri yazmayı
     `finally`'ye koy; her turdan sonra `git status`.
  c. KIRMIZININ HANGİ ASSERTION'DA olduğunu OKU. Yanlış sebeple kırmızı = kontrolü REDDET.
     ADIM 103/104: bir UNIQUE KISIT assertion'ın yerine geçebilir — kusuru kısıdı tetiklemeyen
     bir şekilde yeniden kur.
  d. Gölgeyi KALDIR: kusuru, önceki eksenleri GEÇİRECEK biçimde kur (ADIM 104 NC-4: adı değiştir,
     anahtarı koru). Kaldıramıyorsan gölgelendiğini DEFTERE yaz.
  e. YEŞİL kontrol = yama uygulanmadı VEYA assertion totolojik. Yan etkinin YOKLUĞUNU iddia
     ediyorsan önünde rollback DE identity map DE olamaz → `session.expire_all()`.
  f. Bir GÖVDE iddiasını key lookup'la kurma; tam sözlük eşitliği ya da substring taraması.
  g. EZME (satır demetleri) ile EKLEME (tam sıralı listeler) ayrı eksenlerdir; `count(*)` ikisini
     de kaçırır.
  h. Bir SEEDER/tablo sınıyorsan beklentiyi LİTERAL yaz — üretimden türetme (ADIM 104).
  i. Koşamadığın suite'e (E2E/A11Y/frontend) assertion YAZMA; sınırı yaz.
  j. Kriterin SON clause'u kapanıyorsa kriter-düzeyi `status`'ü covered yap ve `debt_class`'ı KALDIR.
  k. YAML notu düz skalerse `: ` ekleyemezsin -> tek tırnağa al, apostrofları ikile.

KAPATMAYA ÇALIŞMA (bulgular): TL-01.c4, TL-02.c2, TL-11.c3, TL-14.c4, TL-16.c4, RF-08.c2,
  TR-07.c3, RD-01.c4, RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2, MB-22.c4,
  ESP-05.c3 + `unfalsifiable: true` clause'lar. Yeniden sınıflandırma tavan yükseltir = adjudication.

BİTMİŞ: doc 05 · 18 · 10 · 16 · 22-B · 02-B · 17-B · 01-B · 14-B · 21-B · 20-B · 09-B.
  Kalan yoğunluk (yine de ölç): doc 06 (CP-09.c2 Send replay'i, CP-13.c4 Supervisor/Agent
  approval request oluşturabilir) · doc 08 (PL-07.c2) · doc 11 (MKD-02.c1).
  Frontend bitiricileri: UM-15.c3 · RC-09.c3 · CP-03.c4 · AT-07 (`cd frontend && npm ci`).

KAPANIŞ: CLAUDE.md §Session CLOSING 6 madde. Numara + parti etiketini commit'ten hemen önce
  YENİDEN doğrula (dosya yolu ölçümü). TEST EKLEDİYSEN generate_repository_facts.py koş.
  --write-report/--write-ledger yolları --root'a göre: `docs/audit/...`.
  Rebase gerekiyorsa "Update branch" DEĞİL; iki tarafı koruyarak çöz, üretilmişleri yeniden üret,
  tavanı taze --report'tan ölç. Sonra --report --check-generated --ratchet +
  grep -c '^## ADIM' (düşmemeli). git guard: fetch/doğrulama ile push'u AYRI Bash çağrılarına böl.
  PR'ı main'e aç; MERGE ETME — karar insanın.
```
