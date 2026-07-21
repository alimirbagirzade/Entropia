# Entropia V18 — R2 (Remediation Round 2) Yol Haritası

> Kaynak: `docs/spec/Entropia_V18_Guncel_Arayuz_Eksikleri_ve_Yanlis_Anlamalar.md` (bundan sonra **GAP belgesi**).
> Bu yol haritası GAP belgesindeki 20 maddeyi kod üzerinde **empirik olarak doğrulamış**, uygulanabilir
> slice'lara bölmüş ve her slice için temiz bir oturuma yapıştırılacak **paste-ready prompt** üretmiştir.
> Hazırlanma tarihi: 2026-07-20. Referans commit: `origin/main` @ `8e9a1f4` (PR #323 sonrası).

---

## 1. Doğrulama özeti — GAP belgesi iddiaları vs kod (hepsi CONFIRMED)

| GAP maddesi | İddia | Kod kanıtı (doğrulandı) | Durum |
|---|---|---|---|
| 1, 2 | TS/TL Mainboard satırları inline editör değil, route launcher | `Mainboard.tsx:213-224` (`Edit in {label} →` primary link), `:387` (`Continue in the {label} workbench →`); kod yorumu bunu açıkça "a separate UI slice, UI-04/UI-05" diye kabul ediyor | CONFIRMED |
| 1, 4, 6 | Add Package popover yok; üst menü Add eylemleri route navigation | `Mainboard.tsx:590-591` (`<Link to="/packages/create">Add Package</Link>`), `app/nav.ts:172-180` (Add Strategy→`/strategy`, TS→`/trading-signal`, TL→`/trade-log`, Add Package→`/packages/create`) | CONFIRMED |
| 3 | TS/TL create/revise ham JSON textarea; Source asset id düzenlenebilir | `TradingSignal.tsx:255,541 (rows={16}),858 (rows={14})`; `TradeLog.tsx:258,544,860` | CONFIRMED |
| 5, 13 | Strategy Details'te Advanced raw payload role-gate'siz; composition kontrolleri görsel merkezde | `StrategyDetailsPanel.tsx:272-296,479,787`; `StrategyGraphForm.tsx:971` ("not yet surfaced remain in the Advanced editor"); `StrategyConfigForm.tsx:618` (formula params Advanced JSON'da) | CONFIRMED |
| 7, 9 | Normal kullanıcıdan altyapı ID'si isteniyor | `ResearchData.tsx:329-334` (`Linked Market Data entity id`), `ResearchLifecycle.tsx:205-225` (re-link + base revision id), `MarketData.tsx:1191-1205` (Instrument id + optional JSON payload) | CONFIRMED |
| 8 | Research dependency kilidi sahte: `dependencyReady = marketEntityId.trim().length > 0` | `ResearchData.tsx:103` — birebir bu satır | CONFIRMED |
| 11 | Create Package baseline metadata JSON; tam lifecycle E2E yok | `CreatePackage.tsx:841-932` (metadataText JSON parse); `e2e/specs/04-create-package-lifecycle.spec.ts` Pre-Check'te duruyor | CONFIRMED |
| 12 | Golden-path E2E blocked'ı başarı sayıyor | `e2e/specs/05-mainboard-ready-check-run.spec.ts:19-23,62` ("a structured outcome … not a specific verdict"; NOT_READY + disabled admit kabul); `e2e/README.md:55-70` golden-path derinliğini kapsam dışı ilan ediyor | CONFIRMED |
| 14 | Backend yokken sonsuz Loading; timeout yok | `lib/apiClient.ts` — `AbortController`/timeout YOK (grep boş) | CONFIRMED |
| 15 | Mobil shell ~513px min-width overflow | `docs/implementation/entropia_v18_remediation_status.md` UI-22 satırı: "pre-existing 513px app-shell baseline … out of §UI-22 scope" | CONFIRMED |
| 16 | 22 sayfalık final screenshot seti / visual-regression baseline yok | repo'da screenshot matrisi ya da Playwright screenshot baseline yok | CONFIRMED |
| 17 | Remediation status eksik işleri Complete gösteriyor | `entropia_v18_remediation_status.md`: UI-01/02/04/05/12/14/15… hepsi "Complete (this PR)" | CONFIRMED |

**Mevcut açık işlerle kesişim:** `docs/STAGE2_HANDOFF.md` video-alignment bölümündeki **KALAN-A**
(Market Data ham kaynak dosya upload UI, video 9:24–12:37) ve **KALAN-B** (Portfolio "Use Allocation
Backtest" + per-item pay UI, video 7:16–9:24) hâlâ açıktır ve bu yol haritasına paralel iş olarak
dahil edilmiştir. KALAN-C (per-item contribution) PR #319/#320 ile kapandı.

**Önemli REUSE keşfi:** `components/PackagePicker.tsx` + `components/DatasetPicker.tsx` zaten var ve
`StrategyGraphForm`/`StrategyConfigForm` tarafından kullanılıyor — GAP 7/8/9 maddelerinin istediği
"picker" deseni kodda mevcut; eksik olan bu desenin Research Data / Market Data / lifecycle formlarına
yayılmasıdır.

---

## 2. Slice haritası ve sıra

Tek oturumda kodlanabilir 16 slice + 2 kapanış aşaması. Bağımlılık kolonu sıralamayı belirler;
bağımsız olanlar paralel gidebilir.

### P0 — merkezî çalışma modeli (GAP §19 madde 1-8)

| ID | Başlık | GAP | Bağımlılık |
|---|---|---|---|
| R2-01a | TS/TL editörlerini reusable bileşenlere ayır (davranış değişmez refactor) | 1,2,3 hazırlık | — |
| R2-01b | Editörleri Mainboard satırlarına inline mount et (draft + persisted; save→persist; URL `/` kalır) | 1,2 | R2-01a |
| R2-02 | Üst menü Add eylemleri → Mainboard action dispatcher (tek Add modeli) | 6 | R2-01b |
| R2-03 | Add Package seçim popover'ı + Add Strategy From Package (derived Strategy Draft) | 4 | R2-02 |
| R2-04 | TS/TL typed config formları (primary JSON kalkar; Source asset id read-only; tam toolbar) | 3,7 kısmi | R2-01a (ideal: 01b sonrası) |
| R2-05a | Strategy Details typed form tamamlama (restriction/filter/formula/override + picker) | 5 | — |
| R2-05b | Advanced JSON role-gate + Composition settings disclosure | 5,13 | R2-05a |
| R2-06 | Research Data server-truth dependency picker + workflow kilidi | 8 | — |
| R2-07 | Golden-path E2E: Ready **PASS** → RUN **SUCCEEDED** → inline Result | 12 | R2-01b, R2-03 (markup stabilitesi) |

### P1 — ürün kullanılabilirliği (GAP §19 madde 9-13) + video kalanları

| ID | Başlık | GAP | Bağımlılık |
|---|---|---|---|
| R2-08 | Teknik ID sweep → picker/read-only provenance (ResearchLifecycle, MarketData revision, evidence formları) | 7,9 | R2-06 (picker desenleri) |
| R2-09 | Role-aware presentation: Admin-only eylemler `/me` projection ile fail-closed gizlenir | 10 | — |
| R2-10 | App shell backend/auth/hata durumları (apiClient timeout, Backend unavailable + Retry, UNAUTHENTICATED) | 14 | — |
| R2-11 | Mobil app-shell overflow: hamburger menü, yatay taşma sıfır, tek kolon inline paneller | 15 | R2-01b (inline panel varlığı) |
| R2-12 | Create Package typed baseline metadata + request→publish tam lifecycle E2E | 11 | — |
| KALAN-A ✅ | Market Data ham kaynak dosya UPLOAD UI (Browse File → ingest zinciri) — TAMAM (STAGE2_HANDOFF "KALAN-A landed") | video 9:24–12:37, GAP 18 | — (paralel; en yüksek P1) |
| KALAN-B ✅ | Portfolio "Use Allocation Backtest" toggle + Mainboard per-item pay UI — TAMAM (STAGE2_HANDOFF "KALAN-B landed") | video 7:16–9:24 | — (paralel) |

### P2 — görsel kabul ve kapanış (GAP §19 madde 14-18)

| ID | Başlık | GAP | Bağımlılık |
|---|---|---|---|
| R2-13 | 22 sayfa × 5 durum × 3 genişlik screenshot matrisi + V18 side-by-side + Playwright screenshot regression | 16 | tüm P0+P1 |
| R2-14 | Responsive + a11y son geçiş, product-owner onayı, remediation status kapanışı | 17,20 | R2-13 |

---

## 3. ORTAK KURALLAR (her slice prompt'u bunu uygular)

1. **Oturum başı:** `git fetch` + `git log --oneline origin/main -6` + `gh pr list --state open` — bu
   yol haritasındaki referanslar bayatlamış olabilir; önce ne landed doğrula. Sonra:
   bu dosyanın ilgili slice bölümü → GAP belgesi ilgili madde(ler) → `docs/spec/NN_*` sayfa belgesi →
   atıf verilen kod dosyaları.
2. **Empirik doğrulama:** her backend bağı için route/command imzasını OKU (OCC token biçimi,
   Idempotency-Key gereksinimi, dönüş dict'i). Wire tipleri backend dönüşlerinin VERBATIM aynasıdır.
   Mevcut OCC/Idempotency/react-query key/SSE taksonomisi bu yol haritası açıkça değiştirmedikçe
   KORUNUR.
3. **Görsel referans:** `docs/spec/index_guncellenmis_duzeltilmis_v18.html` (canonical v18 mockup) +
   `frontend/src/styles/global.css` tema değişkenleri (`--accent:#00a9e8 --border:#cfcfcf
   --radius:4px --text:#222`, Arial).
4. **ESKİ GUARDRAIL GÜNCELLEMESİ:** CLAUDE.md'deki "nav.ts NAV/ALL_NAV_ITEMS verbatim kalır" kuralı
   R2-02/R2-03 için **kullanıcı onaylı GAP belgesiyle** geçersizdir — bu iki slice menü DAVRANIŞINI
   bilinçli değiştirir (route path'leri ve deep-link'ler yaşamaya devam eder).
5. **Test disiplini:** bozulan vitest yeni markup'a göre yeniden hizalanır (görünür label /
   `aria-label` + `role` üzerinden; option value + OCC/Idempotency assert'leri DEĞİŞMEZ). Kapanışta
   `npm run test` + `tsc` + `eslint` + `vite build` yeşil; kabul ölçütleri GERÇEK tarayıcıda
   (Playwright veya canlı dev server) kanıtlanır.
6. **Kapanış ritüeli:** `docs/implementation/entropia_v18_remediation_status.md` ilgili satır(lar)ına
   gerçek evidence ekle (kod + E2E + ekran kanıtı; eksikse Complete YAZMA);
   `docs/STAGE2_HANDOFF.md`'ye landed bölümü ekle; branch `feat/v18-r2-XX-<slug>`; conventional
   commit, **AI attribution YOK**; PR aç, `gh pr checks --watch`; self-merge kapalı → kullanıcıdan
   merge iste. ecc knowledge graph + claude-mem checkpoint yaz.
7. **Backend değişikliği gerekirse:** önce mevcut yüzeyde çöz; yeni endpoint ancak GAP gereksinimi
   başka türlü karşılanamıyorsa, migration'sız ve additive olarak eklenir (read surface deseni:
   PR #143/#144 örnekleri). Alembic head (bu yazım anında `0035_portfolio_rules`) ve
   `ENGINE_VERSION` bu dalgada SABİT kalmalıdır — R2 slice'ları migration İÇERMEZ.

---

## 4. Paste-ready prompt'lar

Aşağıdaki blokların her biri TEK oturuma, olduğu gibi yapıştırılır.

---

### R2-01a — TS/TL editörlerini reusable bileşenlere ayır

```
Entropia V18-R2 slice R2-01a: Trading Signal ve Trade Log editörlerini reusable bileşenlere ayır
(davranış değişmez, saf refactor).

Önce oku: docs/V18_R2_ROADMAP.md (§3 ORTAK KURALLAR + R2-01a) → docs/spec/
Entropia_V18_Guncel_Arayuz_Eksikleri_ve_Yanlis_Anlamalar.md madde 1-3 → docs/spec/04_*.md +
05_*.md → frontend/src/pages/TradingSignal.tsx + TradeLog.tsx (ikisi ikiz; PR #119 tek slice'ta
yazdı — desen: lib/tradingSignal.ts + lib/tradeLog.ts hook'ları, upload → 202 import → report →
Save & Add → revision).

Görev:
1. pages/TradingSignal.tsx içindeki iki kolonlu editör gövdesini components/TradingSignalEditor.tsx
   olarak çıkar; pages/TradeLog.tsx için components/TradeLogEditor.tsx. Sayfalar ince wrapper kalır
   (URL modları ?job= / ?root= aynen çalışır).
2. Bileşen sözleşmesi (iki ikizde simetrik): props { mode: "page" | "inline", initialRoot?: string,
   onSaved?: (rootId: string) => void, onClose?: () => void }. "inline" modda sayfa-başlığı/nav
   render edilmez; onSaved Save & Add başarısında yeni root id ile çağrılır; onClose panel kapatma
   niyetini üst bileşene bildirir. Bu props'lar R2-01b'nin Mainboard mount'u için forward-contract.
3. lib/tradingSignal.ts, lib/tradeLog.ts, hook'lar, query key'ler, OCC (expected_head_revision_id
   BODY-form STR) ve Idempotency-Key davranışı BYTE-IDENTICAL kalır. Bu slice'ta hiçbir form alanı
   değişmez (typed formlar R2-04'ün işi).

Kabul: npm run test tamamı yeşil (mevcut testler markup değişmediği için aynen geçmeli; import
path güncellemeleri hariç); tsc + eslint + build temiz; tarayıcıda /trading-signal ve /trade-log
davranışı öncekiyle birebir aynı.

Sınır: Mainboard.tsx'e DOKUNMA (R2-01b'nin işi). Yeni hook/endpoint yok.
Kapanış: ORTAK KURALLAR §6.
```

---

### R2-01b — Editörleri Mainboard satırlarına inline mount et

```
Entropia V18-R2 slice R2-01b: Trading Signal ve Trade Log gerçek editörlerini Mainboard yatay
satırlarının İÇİNDE aç — route launcher davranışını bitir. (GAP belgesi madde 1, 2; kabul ölçütü:
kullanıcı Mainboard'dan hiç ayrılmadan oluştur→yükle→validate→kaydet→kapat tamamlar, URL hep "/".)

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-01b) → GAP belgesi madde 1-2 → docs/spec/01_*.md +
03_*.md → frontend/src/pages/Mainboard.tsx (:185-230 persisted satır editör dalı, :330-395
OutsourceDraftRow, :505-600 Add menüsü) → components/TradingSignalEditor.tsx + TradeLogEditor.tsx
(R2-01a'nın çıkardığı bileşenler; landed olduğunu doğrula) → StrategyDetailsPanel'in Mainboard
mount deseni (PR #314: draft yaratma + ilk Save→attach + onSaved ile pin).

Görev:
1. Persisted TS/TL satırı (item.item_kind trading_signal/trade_log): "Edit in {label} →" primary
   linki KALDIR; yerine <TradingSignalEditor|TradeLogEditor mode="inline"
   initialRoot={item.work_object_root_id}> mount et. "Open full page ↗" ikincil ghost link olarak
   kalabilir (deep-link back-compat, GAP zorunlu düzeltme #4).
2. OutsourceDraftRow: "Continue in the {label} workbench →" KALDIR; satır açılır açılmaz ilgili
   editörü mode="inline" mount et (yeni-kayıt modu). Save & Add başarısında onSaved(rootId):
   transient draft satırını listeden düş + ["mainboard"]+["readiness"] invalidate + yeni persisted
   satırı expanded aç. Kullanıcı sayfadan AYRILMAZ.
3. Draft kaldırma (transient satırı sil) / kaydedilmiş nesneyi silme (mevcut two-step soft-delete)
   / paneli kapatma (onClose → expanded=false) üç AYRI eylem olarak net etiketlenir (GAP madde 2
   son bent).
4. Editör toolbar'ında en az Validate / Save / Cancel / Close panel görünür (GAP madde 3 düzeltme
   #4) — inline modda Close panel onClose'a bağlanır. (Typed form içeriği R2-04'te; bu slice
   mevcut formu taşır.)

Kabul (GERÇEK tarayıcı testi, GAP madde 1 kabul ölçütü):
- Strategy, Trading Signal ve Trade Log için ayrı ayrı: Mainboard'dan ayrılmadan yeni satır oluştur,
  dosya seç/yükle, import report gör, kaydet, satır persisted'a dönüşsün, paneli kapat.
- Süreç boyunca URL "/" kalır (Playwright assert). Reload sonrası persisted satır durur.
- vitest: mainboard.test.tsx yeni markup'a hizalanır; TS/TL create-with-attach'ın
  ["mainboard"]+["readiness"] invalidation assert'leri korunur.

Sınır: lib/*.ts veri sözleşmelerine dokunma; TS/TL sayfa route'ları silinmez. Add menüsü ve nav.ts
R2-02'nin işi.
Kapanış: ORTAK KURALLAR §6 + remediation status UI-01/03/04/05 satırlarına gerçek tarayıcı evidence.
```

---

### R2-02 — Üst menü Add eylemleri → Mainboard action dispatcher

```
Entropia V18-R2 slice R2-02: üst menü ile Mainboard "+ Add" akışını TEK action modelinde birleştir
(GAP belgesi madde 6; iki ayrı ürün modeli bitiyor).

Önce oku: docs/V18_R2_ROADMAP.md (§3 ORTAK KURALLAR — özellikle #4 nav.ts guardrail güncellemesi +
R2-02) → GAP madde 6 → frontend/src/app/nav.ts (:170-205 MENU_BAR: Add Strategy→/strategy,
Trading Signal→/trading-signal, Trade Log→/trade-log, Add Package→/packages/create) →
pages/Mainboard.tsx Add menüsü (+ R2-01b'nin inline create eylemleri) → Layout.tsx menü render'ı →
test/nav.test.tsx (menü-hedef ↔ route sözleşmesini pinliyor; yeniden hizalanacak).

Görev:
1. Bir "Mainboard add intent" mekanizması kur: menü eylemi navigate("/", { state: { add:
   "strategy" | "trading_signal" | "trade_log" | "package" } }) (veya eşdeğeri query param) —
   Mainboard mount'ta intent'i okur, kendi +Add akışındaki AYNI handler'ı çağırır (Add Strategy →
   strategy draft satırı + inline editör; TS/TL → OutsourceDraftRow + inline editör; package →
   R2-03 popover'ı, o landed değilse geçici olarak mevcut Add menü davranışı) ve intent'i temizler
   (history.replaceState — reload'da tekrar tetiklenmez).
2. nav.ts MENU_BAR'daki bu dört eylem route-link olmaktan çıkar, dispatcher'a bağlanır. Kullanıcı
   /research-data gibi başka route'tayken Add Strategy seçerse: önce Mainboard açılır, ardından
   yeni satır + inline editör açılır (GAP madde 6).
3. /strategy, /trading-signal, /trade-log, /packages/create ROUTE'ları deep-link/back-compat için
   YAŞAR (App.tsx değişmez); sadece primary menü hedefi olmaktan çıkarlar (GAP madde 5 düzeltme #7
   ile tutarlı).
4. Workspace nav'ının kalan öğeleri (Package Library, Market Data …) normal route-link kalır.

Kabul: tarayıcıda — başka bir sayfadayken üst menüden Add Strategy / Trading Signal / Trade Log
seç → Mainboard'a gelinir ve doğru inline satır AÇIK; Mainboard'dayken aynı eylem route değiştirmez;
aynı isimli iki menü artık farklı sonuç üretmez (GAP madde 6 son bent). nav.test.tsx +
mainboard.test.tsx hizalanır; tsc/eslint/build/test yeşil.

Sınır: NAV yapısındaki diğer öğeler korunur; route path'leri değişmez.
Kapanış: ORTAK KURALLAR §6.
```

---

### R2-03 — Add Package popover + Add Strategy From Package

```
Entropia V18-R2 slice R2-03: Mainboard'a gerçek "Add Package" seçim popover'ı — mevcut Strategy
Package revision'ından yeni Strategy Draft türetme akışı (GAP belgesi madde 4).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-03) → GAP madde 4 → docs/spec/06_*.md (Add Package vs
Create Package ayrımı) + 01_*.md → docs/spec/index_guncellenmis_duzeltilmis_v18.html'de Add Package
popover görünümü → frontend/src/lib/library.ts (GET /library facet'leri + PackagePermissions.can_use
— PR #97) → components/PackagePicker.tsx (mevcut picker deseni, REUSE) → PR #314'ün Add Strategy
draft akışı (Mainboard.tsx + StrategyDetailsPanel onSaved/attach) → backend routes/strategy.py
create draft imzası (draft payload'a package pinleme biçimini EMPİRİK doğrula: StrategyGraphForm'un
pinned package referans şekli).

Görev:
1. Mainboard Add menüsündeki "Add Package" artık /packages/create'e GİTMEZ; küçük, bağlama bağlı
   bir popover açar (mockup'taki görünüm). İçerik: SEÇİLEBİLİR Strategy Package revision'ları —
   yalnızca aktif/published/usable ve kullanıcının use iznine sahip olduğu (server-truth
   permissions.can_use; client asla kendisi türetmez); Trading Signal / Trade Log package türleri
   LİSTELENMEZ. Arama + package adı + market/timeframe uyumluluğu + exact revision + kısa
   compatibility özeti göster (library detail projection'dan; alan yoksa dürüst "not provided").
2. "Add Strategy From Package": seçilen exact root/revision'dan YENİ bir Strategy Draft üret —
   source package MUTATE EDİLMEZ; draft payload'ı seçilen revision'ı pinler (dependency snapshot
   provenance ile; biçimi strategy editor'ün mevcut pin şeklinden empirik olarak al). Üretilen
   draft Mainboard'da yatay Strategy satırı olarak görünür ve gerçek Strategy Details editörü
   inline AÇIK gelir (PR #314 akışının parametrize edilmiş hali).
3. Popover'da ikincil eylem: "Create new package" → CP Agent workspace'i (/packages/create; R2-02
   dispatcher'ı ile uyumlu şekilde). Primary ve ikincil eylem görsel olarak ayrışır.
4. R2-02'deki "package" add-intent'i bu popover'ı açar.

Kabul: tarayıcıda — Add Package popover'ında yalnız eligible strategy package revision'ları
listelenir (can_use=false olan görünmez ya da disabled+neden); birinden Strategy Draft üretilir,
satır inline editörle açılır, source package library'de değişmemiştir; Create new package ikincil
yol çalışır. vitest: popover eligible-filtre + derive akışı + create-new ikincil yol testleri.
tsc/eslint/build/test yeşil.

Sınır: library.ts query key'leri korunur; yeni backend endpoint ancak draft-from-package mevcut
POST /strategy-drafts + PATCH ile kurulamıyorsa (önce empirik dene) eklenir — additive, migration'sız.
Kapanış: ORTAK KURALLAR §6 + remediation status UI-01/06 evidence.
```

---

### R2-04 — TS/TL typed config formları

```
Entropia V18-R2 slice R2-04: Trading Signal ve Trade Log config payload'larını typed form
kontrollerine çevir; ham JSON'u normal akıştan çıkar (GAP belgesi madde 3, 7-kısmi, 9-kısmi).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-04) → GAP madde 3 → docs/spec/04_*.md §(config alanları:
TradingSignalConfig time_policy/event_model/…) + 05_*.md §(TradeLogConfig time_model/…) → backend
domain modellerinde iki config'in GERÇEK şemasını empirik çıkar (routes/trading_signal.py +
trade_log.py create/revision imzaları + Pydantic modelleri; alan adları/enum'lar/zorunluluk) →
components/TradingSignalEditor.tsx + TradeLogEditor.tsx (R2-01a; rows={16} create textarea +
rows={14} revision textarea + Source asset id input).

Görev:
1. Create/Save aşamasındaki rows={16} JSON textarea'yı belgelenen alanlara karşılık gelen typed
   kontrollerle DEĞİŞTİR: enum → select/radio, boolean → checkbox, liste → tekrarlanabilir satır
   editörü, tarih/saat → uygun input (GAP madde 9 kural seti). İkiz farkları verbatim korunur
   (TS time_policy+event_model vs TL time_model; TL available_time daima null — doc 05 §10.4).
2. Revision düzenleme akışındaki rows={14} JSON textarea da aynı typed formu kullanır (report-seeded
   değerlerle dolu gelir).
3. Source asset id alanı normal formdan KALKAR: upload sonucundan sistemce taşınır, kullanıcıya
   read-only provenance satırı olarak gösterilir (GAP madde 3 düzeltme #3).
4. Ham JSON yalnızca kapalı "Advanced (raw payload)" disclosure olarak kalır ve /me server-truth
   admin/teknik role'e gate'lenir (R2-09 pattern'ı; role projection henüz yoksa fail-closed gizle).
   Typed form payload'ı ÜRETİR (tek source-of-truth); Advanced açıkken senkron kuralını net belirle.
5. Toolbar: Validate / Save / Cancel / Close panel tamdır (R2-01b'de eklendi; typed form
   validate'i schema+domain hatalarını alan yanında gösterir — JSON parse hatası tek başına yeterli
   değil, GAP madde 9 son bent).

Kabul: normal kullanıcı hiçbir JSON, root id, revision id veya source asset id GİRMEDEN TS ve TL
oluşturur+revize eder (tarayıcı kanıtı, Mainboard inline). OCC (expected_head_revision_id) ve
Idempotency-Key davranışı BYTE-IDENTICAL (mevcut assert'ler korunur). vitest typed-form doğrulama
+ payload üretim testleri; tsc/eslint/build/test yeşil.

Sınır: lib/tradingSignal.ts + tradeLog.ts wire tipleri backend'e verbatim ayna kalır; endpoint
değişikliği yok.
Kapanış: ORTAK KURALLAR §6 + remediation status UI-04/05 evidence.
```

---

### R2-05a — Strategy Details typed form tamamlama

```
Entropia V18-R2 slice R2-05a: Strategy Details'te structured formun kapsamadığı alanları typed
kontrollere taşı — "Advanced'e bırakılmış alan" kalmasın (GAP belgesi madde 5).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-05a) → GAP madde 5 → docs/spec/02_*.md (form alanları)
→ backend domain/strategy/config.py (restriction/filter tipleri, formula param şemaları, package
parameter override biçimi — GERÇEK Pydantic şemayı empirik çıkar) →
components/StrategyGraphForm.tsx (:47, :971 "not yet surfaced remain in the Advanced editor" —
hangi alanların dışarıda kaldığını kodda TESPİT ET) + StrategyConfigForm.tsx (:36, :618 formula
params Advanced'de) + PackagePicker.tsx/DatasetPicker.tsx (mevcut picker desenleri).

Görev:
1. Envanter çıkar: Advanced JSON'da kalan her alan (block advanced fields, restriction/filter
   config'leri, formula parametreleri, package parameter override'ları) → listeyi PR
   açıklamasına yaz.
2. Her desteklenen restriction/filter TÜRÜ için type-specific typed form (enum select, sayı input,
   tarih aralığı vb. — JSON textarea DEĞİL).
3. Formula parametreleri (ör. Kelly girdileri — engine'in formula_params şemasından:
   domain/backtest/engine.py _decimal_param kullanımından empirik doğrula) ve package parameter
   override'ları structured kontrollerle.
4. Reference chain (N-ary additional_reference_package_refs) ve dependency seçimleri kullanıcı
   dostu picker ile (PackagePicker REUSE; elle id girişi yok).
5. Hedef: geçerli bir stratejinin BÜTÜN ayarları yalnızca belgelenmiş form alanlarıyla kurulabilir
   (GAP madde 5 mevcut eksikler listesinin tersine çevrilmesi). Advanced editörün role-gate'i
   R2-05b'de — bu slice'ta Advanced'e YENİ alan bırakma.

Kabul: temsili karmaşık bir strateji (multi-block + condition'lı + restriction'lı + Kelly sizing +
N-ary reference) yalnızca typed formlarla kurulup validate PASSED alır (tarayıcı kanıtı);
validate/save OCC (expected_draft_row_version) davranışı değişmez. vitest form testleri;
tsc/eslint/build/test yeşil.

Sınır: lib/strategy.ts wire sözleşmesi verbatim; compiler issue formatı ({field,code,message})
verbatim render edilmeye devam eder.
Kapanış: ORTAK KURALLAR §6 + remediation status UI-02 evidence.
```

---

### R2-05b — Advanced role-gate + Composition settings disclosure

```
Entropia V18-R2 slice R2-05b: Strategy Details'te raw JSON'u normal kullanıcı akışından tamamen
kaldır; Mainboard composition kontrollerini ikincil disclosure'a taşı (GAP belgesi madde 5
düzeltme #4-6 + madde 13).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-05b) → GAP madde 5 ve 13 →
components/StrategyDetailsPanel.tsx (:272-296 AdvancedPayloadEditor, :479, :787) →
pages/Mainboard.tsx (satır altındaki pinned revision id / enable-disable / move up-down / label
override / OCC yönetim alanları) → /me projection'ı (role bilgisinin server-truth kaynağı —
routes'ta GET /me imzasını empirik doğrula).

Görev:
1. AdvancedPayloadEditor yalnızca /me server-truth admin/teknik role'e render edilir; permission
   yüklenirken FAIL-CLOSED (gizli). Varsayılan collapsed; açılınca şema doğrulamalı. Normal
   kullanıcı akışında hiçbir raw JSON görünmez.
2. Mainboard satırı: enable/disable + delete kompakt row action kalır; reorder drag-handle veya
   kompakt hareket kontrolü; pinned revision provenance, pin yönetimi ("Use This Revision"),
   label override, row-version/OCC açıklamaları kapalı "Composition settings" disclosure/menüsüne
   taşınır. Strategy Details editörünün altında ikinci uzun teknik form GÖRÜNMEZ (GAP madde 13).
3. Aynı hiyerarşi ayrımı TS/TL satırlarında da uygulanır (inline editör + kapalı Composition
   settings).

Kabul: normal (admin olmayan) kullanıcı Strategy/TS/TL satırını açtığında yalnız ürün editörünü
görür; Composition settings kapalı disclosure'dadır ve açılınca mevcut pin/reorder/label
işlevleri OCC assert'leri DEĞİŞMEDEN çalışır (mainboard.test.tsx'teki expected_row_version
assert'leri korunur). Admin, Advanced editörü görür. vitest role-gate + disclosure testleri;
tarayıcı kanıtı; tsc/eslint/build/test yeşil.

Sınır: PATCH /mainboard-items OCC sözleşmesi ve intent-per-call davranışı verbatim; işlev
KALDIRILMAZ, yalnız görsel hiyerarşi değişir.
Kapanış: ORTAK KURALLAR §6 + remediation status UI-01/02 evidence.
```

---

### R2-06 — Research Data server-truth dependency picker

```
Entropia V18-R2 slice R2-06: Research Data'nın Approved Market Data bağımlılığını gerçek
server-truth'a bağla — non-empty text ile açılan sahte kilidi kaldır (GAP belgesi madde 8).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-06) → GAP madde 8 → docs/spec/12_*.md (DR3 kuralı) →
frontend/src/pages/ResearchData.tsx (:103 dependencyReady = marketEntityId.trim().length > 0;
:325-345 Linked Market Data entity id text input; WorkflowStrip + dependency alert) →
components/DatasetPicker.tsx (mevcut approved-dataset picker deseni — StrategyConfigForm
kullanıyor; REUSE) → lib/marketData.ts registry hook'ları (state filtresi var mı empirik bak) →
backend create_research_dataset'in DR3 reddi (DEPENDENCY_BLOCKED) davranışı.

Görev:
1. "Linked Market Data entity id" serbest metin alanını KALDIR; yerine yalnızca ACTIVE+APPROVED ve
   kullanıcının erişebildiği Market Data revision'larını gösteren picker (DatasetPicker REUSE/
   uyarlama; isim+tür+durum+revision+uygunluk gösterir; immutable id'yi sistem taşır).
2. dependencyReady artık SEÇİLEN revision'ın server projection'ındaki gerçek durumdan türetilir;
   WorkflowStrip, dependency alert ve Create Dataset butonu AYNI server-truth kaynağına bağlanır.
3. Ayrı durumlar ayrı gösterilir: loading (fail-closed kilitli), invalid/bulunamadı, deprecated,
   rejected, permission denied, stale (GAP madde 8 düzeltme listesi). Kullanıcı ancak gerçekten
   uygun revision seçiliyken ilerleyebilir.
4. Backend reddi (DEPENDENCY_BLOCKED) yine verbatim render edilir — client kilidi sunucu
   doğrulamasının YERİNE geçmez, önüne geçer.

Kabul: tarayıcıda — picker'da yalnız approved revision'lar; seçim yokken 4./5. adımlar kilitli ve
Create disabled; approved seçimle açılır; deprecated/rejected seçilemez veya nedenli disabled.
"Alana rastgele yazı yazınca kilit açılıyor" senaryosu ARTIK KURULAMAZ (input yok). vitest:
picker + kilit durum testleri (research testleri yeni markup'a hizalanır, DR3 assert'leri
korunur); tsc/eslint/build/test yeşil.

Sınır: research create/finalize OCC-Idempotency davranışı verbatim; yeni endpoint yok (mevcut
market-data read surface yeterli olmalı — empirik doğrula, değilse additive read).
Kapanış: ORTAK KURALLAR §6 + remediation status UI-12 evidence.
```

---

### R2-07 — Golden-path E2E: Ready PASS → RUN SUCCEEDED → inline Result

```
Entropia V18-R2 slice R2-07: gerçek golden-path Playwright testi — blocked/error KABUL DEĞİL
(GAP belgesi madde 12).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-07) → GAP madde 12 → frontend/e2e/specs/
05-mainboard-ready-check-run.spec.ts (:15-25 "structured outcome" yaklaşımı — değişecek) +
e2e/README.md (:55-70 golden-path derinliği notu) → docs/STAGE2_HANDOFF.md video-alignment
bölümü: PR #316 zinciri (Translate ta.sma → Pre-Check → candidate → draft → validate →
approve/publish → Library can_use → editörde pinlenir) — bu zincir CANLIDA MANUEL KANITLANDI,
şimdi otomatikleşecek → backend/apps/seed.py + backend/scripts (seed yüzeyi).

Görev:
1. Test fixture/seed: Admin-approved Market Data revision + approved+published indicator package
   + (gerekirse) rationale family — GERÇEK kayıtlar olarak hazırla. Yol seçimi: (a) backend seed
   script genişletmesi (python -m entropia.apps.seed'e idempotent bir "e2e golden fixture" modu)
   veya (b) e2e global-setup'ta API zinciri; hangisi daha az kırılgansa onu seç, kararı yaz.
   Fixture idempotent ve tekrar koşulabilir olmalı (CI).
2. Playwright akışı (05 spec'i yeniden yaz): Mainboard'da Strategy INLINE oluştur (typed form;
   approved indicator'ı picker'dan pinle; approved market dataset'i seç) → validate → save →
   attach doğrulanır → Ready Check çalıştır → sonuç AÇIKÇA READY/PASS assert edilir → RUN
   butonunun disabled→enabled geçişi assert edilir → RUN başlat → gerçek run SUCCEEDED olana
   kadar bekle (SSE/poll; makul timeout) → Result'ın Mainboard altında inline açıldığı ve
   headline metrics + provenance gösterdiği assert edilir.
3. Blocked / NOT_READY / error bu testte BAŞARISIZLIKTIR. "Structured outcome yeterli" yaklaşımı
   bu golden-path spec'inden kaldırılır (mevcut negatif/edge senaryolar ayrı spec olarak
   kalabilir). e2e/README.md ilgili bölümü yeni gerçeğe göre güncellenir.

Kabul: yerel tam stack'te (docs/LOCAL_STACK.md) test yeşil; CI'da koşulabilirliği belgelenir
(CI'da tam stack yoksa dürüst sınır: hangi ortamda koşuyor yaz — ama "geçti" raporu yalnız gerçek
koşudan sonra). Test URL'nin "/" kaldığını da assert eder (GAP madde 1 kabul ölçütüyle birleşik).

Sınır: uygulama koduna yalnız test-id/aria eklemeleri; davranış değişikliği gerekirse ayrı bulgu
olarak raporla (bu slice test+seed slice'ıdır).
Kapanış: ORTAK KURALLAR §6 + remediation status UI-14/15 evidence + e2e/README güncel.
```

---

### R2-08 — Teknik ID sweep → picker / read-only provenance

```
Entropia V18-R2 slice R2-08: normal kullanıcıdan altyapı kimliği isteyen TÜM kalan alanları
picker/read-only provenance modeline çevir (GAP belgesi madde 7 + 9 kalanı; TS/TL source asset id
R2-04'te, Research linked-market R2-06'da çözüldü — bu slice süpürme yapar).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-08) → GAP madde 7 ve 9 → şu doğrulanmış noktalar:
components/ResearchLifecycle.tsx:205-225 (Re-link market entity id + Base revision id serbest
metin), pages/MarketData.tsx:1191-1205 (Instrument id + optional JSON payload), evidence/lifecycle
formlarındaki serbest revision/task/run id alanları (grep ile envanter çıkar: placeholder="md_…",
"rrev_…", "_id" içeren input'lar) → pages/Instruments.tsx (instrument read surface — picker
kaynağı) → DatasetPicker/PackagePicker desenleri.

Görev:
1. Envanter: frontend'de kullanıcıdan id isteyen her alanı listele (grep + görsel tarama);
   listeyi PR açıklamasına koy.
2. Her biri için: ilgili kaynak isim/tür/durum/owner/revision bilgisiyle picker'dan seçilir;
   immutable ID sistem tarafından taşınır; teknik ID yalnız read-only provenance/debug satırında
   ve gerekli role'de görünür. Manuel id girişi kalacaksa yalnızca açıkça "Advanced/Admin" olarak
   adlandırılmış araçta (R2-09 role-gate'iyle uyumlu).
3. ResearchLifecycle: re-link market → approved market picker (R2-06 bileşeni REUSE); base
   revision → mevcut revision listesinden seçim. MarketData revision formu: Instrument id →
   instruments picker; optional JSON payload → typed alanlar + Advanced disclosure (GAP madde 9).
4. JSON payload alanı kalan diğer ekranlar (Market/Research revision payload, feature definition)
   için de aynı kural: belgelenmiş alan → typed kontrol; şeması bilinmeyen → Advanced'de.

Kabul: normal kullanıcı akışlarında elle id girilen alan KALMAZ (envanter listesi %100 kapatılır
veya kalanlar Advanced/Admin olarak gerekçeli işaretlenir); mevcut OCC/Idempotency assert'leri
değişmez; tarayıcı kanıtı + vitest hizalaması; tsc/eslint/build/test yeşil.

Sınır: command/route sözleşmeleri verbatim — yalnız SEÇİMİN kaynağı değişir, gönderilen alan
adları değişmez.
Kapanış: ORTAK KURALLAR §6 + remediation status ilgili satırlar evidence.
```

---

### R2-09 — Role-aware presentation (Admin-only eylemler)

```
Entropia V18-R2 slice R2-09: Admin-only eylemleri yetkisiz kullanıcıya primary kontrol olarak
göstermeyi bitir — /me server-truth permission projection + fail-closed presentation
(GAP belgesi madde 10).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-09) → GAP madde 10 → docs/implementation/
entropia_v18_remediation_status.md UI-22 satırı (Future Dev'de landed olan ÖRNEK pattern:
"gates are PRESENTATION over server projections, fail-closed while unknown; server her dispatch'te
yeniden doğrular") → GET /me imzası (is_admin/role alanları — empirik) → Admin-gated eylemlerin
envanteri: MarketData approve/deprecate, ResearchLifecycle approve/revoke, ESP activate/deprecate
(pages/Embedded.tsx), Library admin eylemleri, Trash restore/purge, Panel role assignment, User
Manual admin bakımı, Capability transition (zaten gated — referans).

Görev:
1. Ortak bir useMe()/usePermissions() hook'u (varsa REUSE; yoksa lib/auth.ts'e additive) —
   permission YÜKLENİRKEN fail-closed (Admin kontrolleri gizli).
2. Envanterdeki her Admin-only eylem: yetkisiz kullanıcıya primary button olarak GÖRÜNMEZ; yerine
   read-only durum + "Admin approval required" açıklaması (GAP madde 10 düzeltme #3). Yetkili
   kullanıcı aynı kontrolü görür.
3. Client görünürlüğü hiçbir zaman authorization'ın yerine geçmez: server 403 davranışı ve verbatim
   envelope render'ı AYNEN kalır (stale-cache senaryosu için mevcut 403 testleri korunur —
   UI-22'deki "stale-cache denial still renders verbatim" deseni).
4. UI visibility testleri: admin görür / non-admin görmez + fail-closed loading durumu.

Kabul: non-admin oturumda tarayıcı taraması — envanterdeki hiçbir Admin eylemi primary kontrol
değil; admin oturumda hepsi çalışır; 403 verbatim assert'leri değişmeden yeşil. vitest +
tsc/eslint/build yeşil.

Sınır: hiçbir command/route çağrısının kendisi değişmez; yalnız render koşulu eklenir.
Kapanış: ORTAK KURALLAR §6 + remediation status ilgili satırlar evidence.
```

---

### R2-10 — App shell backend/auth/hata durumları

```
Entropia V18-R2 slice R2-10: sonsuz "Loading…" biter — API timeout, Backend unavailable ekranı,
gerçek UNAUTHENTICATED durumu (GAP belgesi madde 14).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-10) → GAP madde 14 → frontend/src/lib/apiClient.ts
(timeout/AbortController YOK — doğrulandı) → lib/sse.ts (SseStatus zaten var; PR #133 backoff) →
backend /health/live + /health/ready + /v1/meta yüzeyleri (empirik) → Layout.tsx (banner yeri) →
pages/Mainboard.tsx loading durumu → components/ErrorState.tsx (REUSE).

Görev:
1. apiClient: her isteğe AbortController tabanlı görünür timeout (varsayılan ~15s; named constant).
   Timeout/ağ hatası → typed hata (ör. code: "NETWORK_UNAVAILABLE") — mevcut ApiError sözleşmesine
   ADDITIVE, çağıran sayfaların verbatim error render'ı bozulmaz.
2. App shell health durumu: hafif healthcheck (GET /health/live; empirik en ucuz endpoint) ile
   "API reachable" bilgisi. Backend kapalıysa Layout'ta net durum: "Backend unavailable" +
   kullanılan API adresi (VITE_API_BASE_URL çözümü) + Retry eylemi (GAP madde 14).
3. AUTH_MODE=session'da 401 → loading yerine gerçek UNAUTHENTICATED durumu + Login eylemi
   (/login'e yönlendirme mevcut auth akışıyla).
4. SSE bağlantısı, API readiness ve authentication ÜÇ AYRI gösterge olarak sunulur (SseStatus
   REUSE); hiçbir primary sayfanın son durumu sonsuz spinner olamaz — react-query error state'leri
   ErrorState + Retry'a bağlanır.

Kabul: backend kapalıyken tarayıcıda Mainboard "Loading…"de TAKILMAZ — Backend unavailable + API
adresi + Retry görünür; backend açılınca Retry ile toparlar; session modda oturumsuz kullanıcı
UNAUTHENTICATED + Login görür. vitest: timeout + fail durum testleri (fetch double ile);
tsc/eslint/build/test yeşil.

Sınır: SSE taksonomisi, query key'ler, mevcut hata envelope render'ları değişmez; timeout
retry-fırtınası yaratmaz (Retry = kullanıcı eylemi; healthcheck polling mütevazı aralıkta).
Kapanış: ORTAK KURALLAR §6 + remediation status evidence.
```

---

### R2-11 — Mobil app-shell overflow

```
Entropia V18-R2 slice R2-11: 375px'te ~513px'e taşan ortak app shell'i düzelt — yatay overflow
sıfır (GAP belgesi madde 15; UI-22 kaydında "pre-existing 513px app-shell baseline" olarak kabul
edilmişti).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-11) → GAP madde 15 → Layout.tsx + app/nav.ts menü
render'ı + styles/global.css (menü bar genişlik kaynağı) → Mainboard inline panelleri (R2-01b
sonrası 2-3 kolonlu editörler) → ReadyCheckModal/fixed RUN kabuğu.

Görev:
1. Üst menü dar genişlikte hamburger/disclosure (veya kontrollü yatay scroll) modeline geçer —
   ~513px minimum genişlik dayatması kalkar.
2. Body/document seviyesinde yatay overflow: 375/768/1280/1440/1920'de sıfır (overflow-x denetimi);
   iç tablolar kendi overflow-x:auto container'ında kalır, sayfayı genişletmez.
3. Fixed Ready Check/RUN kabuğu mobil viewport'u kapatmaz (safe yerleşim).
4. Inline Strategy/TS/TL panelleri ≤768px'te bilinçli tek kolon düzenine iner (3/2 kolon grid'leri
   media query ile).
5. Playwright viewport testi: 5 genişlikte document.scrollWidth <= viewport genişliği assert'i +
   temel ekranların (Mainboard, TS/TL inline, Market Data, Panel) ekran görüntüleri.

Kabul: 375px'te hiçbir sayfada body-level yatay scroll yok (otomatik assert); menü mobilde
kullanılabilir; masaüstü görünüm 1280+ piksel'de DEĞİŞMEZ (v18 mockup masaüstü referansıdır).
vitest/e2e + tsc/eslint/build yeşil.

Sınır: renk/tipografi/masaüstü yerleşim değişmez; yalnız responsive davranış eklenir.
Kapanış: ORTAK KURALLAR §6 + remediation status evidence.
```

---

### R2-12 — Create Package typed metadata + tam lifecycle E2E

```
Entropia V18-R2 slice R2-12: Create Package baseline metadata'yı typed alanlara çevir + request →
published tam lifecycle'ı tek gerçek Playwright yolculuğunda kanıtla (GAP belgesi madde 11).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-12) → GAP madde 11 → docs/spec/06_*.md + 07_*.md →
pages/CreatePackage.tsx (:841-932 metadataText JSON textarea) → backend create_package
baseline_metadata'nın GERÇEK beklenen anahtarları (commands/create_package.py + candidate.py —
provider/symbol/timeframe/range vb. hangi anahtarlar okunuyor, empirik çıkar) →
e2e/specs/04-create-package-lifecycle.spec.ts (Pre-Check'te duruyor) → STAGE2_HANDOFF PR #316
kaydı (manuel kanıtlanan zincir: Translate ta.sma → Pre-Check → candidate → draft → validate →
approve/publish → Library can_use).

Görev:
1. Baseline metadata JSON textarea'sı yerine typed alanlar (provider, symbol, timeframe, range
   başlangıç/bitiş + backend'in gerçekten okuduğu diğer anahtarlar); bilinmeyen ek anahtar
   ihtiyacı için kapalı Advanced disclosure (R2-04/05 deseniyle tutarlı, role-gate'li).
2. CP Agent workspace'te lifecycle aşama gating'i: her aşama bir önceki GERÇEK server state ile
   açılır; kilitli eylemin NEDENİ doğrudan kontrolün yanında gösterilir ("Pre-Check PASSED değil",
   "candidate üretilmedi", "Admin approval bekliyor" — server hint alanlarından, client türetmez).
3. e2e/specs/04'ü tam yolculuğa genişlet: request oluştur → Pre-Check PASSED → candidate generate
   → draft → validate PASSED → Admin approve → publish → Library'de can_use=yes assert. Her
   beklenen state TEK TEK assert edilir; "blocked veya error da kabul" yaklaşımı YASAK (GAP madde
   11 son bent). Admin adımı için e2e'de admin aktör oturumu (mevcut e2e auth fixture'ları).

Kabul: tarayıcıda normal kullanıcı JSON yazmadan CP request oluşturur; e2e 04 tam lifecycle yeşil
(yerel tam stack; CI koşulabilirliği belgelenir). X-Request-Version OCC + Idempotency-Key
davranışları verbatim. vitest + tsc/eslint/build/test yeşil.

Sınır: CP command sözleşmeleri değişmez; GENERATOR_VERSION/ENGINE_VERSION sabit.
Kapanış: ORTAK KURALLAR §6 + remediation status UI-06 evidence + e2e/README güncel.
```

---

### KALAN-A — Market Data ham kaynak dosya UPLOAD UI

```
Entropia V18-R2 / KALAN-A: Market Data sayfasına videodaki "Raw Source File / Browse File" upload
deneyimini getir — videonun en güçlü şikâyeti (9:24–12:37: "süreci başlatacak ham kaynak dosya
yükleme seçeneği maalesef yok").

Önce oku: docs/V18_R2_ROADMAP.md (§3 + KALAN-A) → docs/STAGE2_HANDOFF.md "KALAN-A" bölümü →
docs/spec/Video Anlatımı /entropia_transkript.md (9:24–12:37) → docs/spec/11_*.md →
pages/MarketData.tsx (mevcut Step 1/2 ingest zinciri — PR #103: create dataset / raw-upload
start+finalize / durable 202 analysis / schema mapping; PR #105 lifecycle) → lib/marketData.ts →
e2e/specs/02-market-data-upload.spec.ts + 07-file-uploads.spec.ts (mevcut kapsam).

Görev:
1. Kullanıcının GERÇEK dosya seçerek (Browse File) süreci BAŞLATABİLDİĞİ akışı uçtan uca görünür
   ve çalışır yap: dosya seç → upload progress → finalize → analysis (202 job) → önerilen schema
   mapping'i gör/onayla → Create Dataset → revision zinciri → Approve for Use (Admin, R2-09
   role-aware sunumla). Backend yüzeyi HAZIR (PR #103/#105) — bu slice UI kompozisyon +
   kullanılabilirlik işidir; neyin gerçekten kopuk olduğunu oturum başında canlı stack'te
   ÇALIŞTIRARAK tespit et (videodaki şikâyetin bugünkü tam karşılığını yaz).
2. Ham bytes sayfadan geçmez (evidence satırı object key + digest pinler — mevcut sözleşme);
   upload cancel/retry durumları görünür.
3. Akış Mainboard değil Market Data sayfasında yaşar (doc 11); ama giriş noktası net ve birincil
   olmalı ("maalesef yok" hissi bitmeli).

Kabul: canlı stack'te tarayıcıyla örnek bir CSV/raw dosya seçilir, süreç Create Dataset +
Approve'a kadar UI üzerinden tamamlanır (video senaryosunun birebir karşılığı); e2e 02/07
genişletilir veya yeni spec eklenir. OCC/Idempotency verbatim; tsc/eslint/build/test yeşil.

Sınır: routes/market_data.py sözleşmeleri değişmez (gerekirse additive read); migration yok.
Kapanış: ORTAK KURALLAR §6 + STAGE2_HANDOFF KALAN-A'yı kapalı işaretle.
```

---

### KALAN-B — Portfolio "Use Allocation Backtest" + per-item pay UI

```
Entropia V18-R2 / KALAN-B: videodaki Portfolio deneyimini tamamla — "Use Allocation Backtest"
toggle + Mainboard'daki her öğeye pay atama görünürlüğü (video 7:16–9:24).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + KALAN-B) → docs/STAGE2_HANDOFF.md "KALAN-B" bölümü →
docs/spec/Video Anlatımı /entropia_transkript.md (7:16–9:24) → docs/spec/13_*.md →
pages/Portfolio.tsx + lib/allocation.ts (PR #113: draft OCC expected_row_version; PR #320:
portfolio-level rules Max Total Exposure + conflict policy) → pages/Mainboard.tsx satır özeti →
backend routes/allocation.py imzaları (toggle'ın backend karşılığını EMPİRİK tespit et: draft
alanı mı, ayrı flag mi — yoksa dürüst sınır olarak raporla).

Görev:
1. Videodaki "Use Allocation Backtest" deneyimi: allocation planının backtest'e uygulandığını
   kullanıcının AÇIK bir kontrol/etikette görmesi. Backend'de birebir toggle alanı var mı önce
   doğrula; varsa bağla; yoksa mevcut sözleşmeyle kurulabilen en yakın dürüst deneyimi kur
   (ör. plan varlığı + Ready/RUN'ın planı kullandığının görünür rozeti) ve farkı dürüst sınır
   olarak yaz — asla sahte toggle render etme.
2. Mainboard satırlarında per-item pay görünürlüğü: her Strategy/TS/TL satırında allocation
   payı (yüzde/miktar) server-truth'tan gösterilir; pay atama/düzenleme Portfolio editörüne
   deep-link'ler (veya inline mini editör — Portfolio OCC sözleşmesi expected_row_version ile,
   draft PUT invalidation seti ["allocation"]+["readiness"]+["mainboard"]+["audit"] verbatim).
3. Derived amounts/validation VERBATIM render (client capital math hesaplamaz — PR #113 kuralı).

Kabul: tarayıcıda — Mainboard'da her öğenin payı görünür; Portfolio'da pay değişince Mainboard
yansır (invalidation zinciri); video senaryosu (7:16–9:24) UI'da karşılanır ya da karşılanamayan
kısım dürüst sınır olarak PR'da yazılıdır. vitest + tsc/eslint/build/test yeşil.

Sınır: allocation OCC/Idempotency/pure-read sync sözleşmeleri verbatim; migration yok.
Kapanış: ORTAK KURALLAR §6 + STAGE2_HANDOFF KALAN-B'yi kapalı işaretle.
```

---

### R2-13 — 22 sayfa screenshot matrisi + side-by-side + screenshot regression

```
Entropia V18-R2 slice R2-13: 22 sayfanın gerçek veriyle screenshot matrisi + V18 prototip
side-by-side karşılaştırma + kritik sayfalara Playwright screenshot regression (GAP belgesi
madde 16; Implementation Spec zorunluluğu).

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-13) → GAP madde 16 → docs/spec/
Entropia_V18_Claude_Code_Implementation_Spec.md (:485, :799, :836, :855 screenshot/acceptance
şartları) → docs/spec/index_guncellenmis_duzeltilmis_v18.html (prototip) → R2-07'nin golden
fixture'ı (REUSE: gerçek veri seed'i) → e2e altyapısı.

Görev:
1. Full-stack seed ortamı: R2-07 fixture'ını genişleterek her sayfaya gerçek veri (empty, loading,
   normal-data, error, permission-denied durumlarını üretebilen fixture kombinasyonları).
2. 22 hedef sayfanın TAMAMI için 1280/1440/1920 px screenshot'ları; Mainboard + inline editörler
   için ek 375/768 px. Çıktılar repo'da versiyonlanabilir bir yerde
   (frontend/e2e/screenshots/baseline/… — adlandırma: sayfa×durum×genişlik).
3. V18 prototiple side-by-side inceleme: sapmaları docs/implementation/
   v18_visual_deviations.md'ye madde madde kaydet (issue niteliğinde; her sapma ya düzeltme
   slice'ı ya da product-owner onayına sunulacak bilinçli fark).
4. Kritik sayfalar (Mainboard, Strategy inline, TS/TL inline, Market Data, Create Package, Ready/
   RUN/Result) için Playwright toHaveScreenshot regression testleri (baseline commit'lenir;
   flake'e karşı maskeleme/threshold ayarları belgelenir).

Kabul: matris eksiksiz üretilmiş ve repo'da; sapma listesi çıkarılmış; screenshot regression CI'da
veya belgelenmiş yerel komutla tekrarlanabilir. Bu slice "Complete" İLAN ETMEZ — product-owner
onayı R2-14'ün işi.

Sınır: uygulama koduna yalnız test-id eklemeleri.
Kapanış: ORTAK KURALLAR §6.
```

---

### R2-14 — Son kabul: responsive + a11y + product-owner onayı + status kapanışı

```
Entropia V18-R2 slice R2-14: nihai kabul geçişi (GAP belgesi madde 17 + 20 "Nihai kabul tanımı").

Önce oku: docs/V18_R2_ROADMAP.md (§3 + R2-14 + §1 doğrulama tablosu) → GAP madde 17 ve 20 →
docs/implementation/entropia_v18_remediation_status.md + v18_visual_deviations.md (R2-13 çıktısı).

Görev:
1. GAP madde 20'deki nihai kabul listesini TEK TEK canlı stack'te doğrula (üç satır türü inline
   editör; route değişmeden CRUD; Add Package popover; raw JSON/ID girişi yok; server-truth
   kilitler; Ready PASS → RUN SUCCEEDED → inline Result; CP request→publish; hata/loading
   durumları; mobil taşma yok; screenshot seti karşılaştırılmış). Her madde için kanıt linki
   (test adı / screenshot yolu / PR) tablo halinde docs/implementation/v18_final_acceptance.md'ye.
2. Responsive (375/768/1280/1440/1920) + accessibility son geçişi: axe-core otomatik tarama +
   klavye-only temel akış denemesi; bulgular kapatılır veya kayıtlı sapma olur.
3. Sapma listesi product-owner'a sunulur; YAZILI onay alınmadan hiçbir madde Complete'e çekilmez.
4. Onay sonrası entropia_v18_remediation_status.md satırları gerçek evidence referanslarıyla
   Complete'e güncellenir; STAGE2_HANDOFF'a R2 dalgasının kapanış özeti yazılır.

Kabul: v18_final_acceptance.md eksiksiz; PO onayı belgede kayıtlı; status dosyası gerçekle uyumlu.
Kapanış: ORTAK KURALLAR §6.
```

---

## 5. Bu yol haritasının kendisiyle ilgili notlar

- Remediation status dosyasına bu PR ile bir **re-opening banner'ı** eklendi: GAP belgesinin
  CONFIRMED bulguları nedeniyle UI-01/02/04/05/06/12 ve fonksiyonel bağlıları R2 kapsamı kapanana
  kadar "Complete" sayılamaz (GAP madde 17 zorunlu düzeltmesi).
- `docs/spec/Video Anlatımı /entropia_transkript.md` referans verilen ama untracked bir dosyaydı;
  bu PR ile commit'lendi (video .mp4 dosyası bilinçli olarak commit DIŞI — 153MB binary).
- Slice'lar kodlanırken bu dosyadaki satır numaraları bayatlayabilir; her prompt bu yüzden oturum
  başında yeniden doğrulama emreder (§3 ORTAK KURALLAR #1).
