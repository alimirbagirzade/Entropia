# V18 Görsel Sapma Listesi (R2-13)

Kaynak: `frontend/e2e/screenshots/baseline/**` (canlı seeded stack, 22 sayfa ×
durum × genişlik) ↔ `frontend/e2e/screenshots/prototype/**` (V18 mockup
`docs/spec/index_guncellenmis_duzeltilmis_v18.html`, ekran başına 1440 px).

Üretim komutları: `frontend/e2e/README.md` §"R2-13 — Screenshot matrix".

**Statü sözlüğü** — her madde ikisinden birine düşer:

- `FIX(R2-xx)` — düzeltme slice'ı önerilir (görsel/etkileşim prototipten
  istenmeyen biçimde sapmış).
- `PO-APPROVE` — bilinçli fark; product-owner onayına sunulur (R2-14).
  Gerekçesi yazılıdır.

Bu doküman R2-13 çıktısıdır; hiçbir maddeyi kendi başına "Complete" yapmaz —
nihai karar R2-14'te product-owner'ındır.

---

## 01 Mainboard (`/` ↔ prototip `showMainboard`)

| # | Sapma | Statü |
|---|---|---|
| 1.1 | Uygulama "Mainboard" başlığı + "Backtest composition · human_default" alt satırı gösteriyor; prototipte yalnız STRATEGIES etiketi var. | PO-APPROVE — server-truth workspace kimliği bilinçli eklendi (R2 dalgası). |
| 1.2 | Sağ üstte kalıcı "+ Add" düğmesi; prototipte ekleme yalnız üst menü hover'ından. | PO-APPROVE — R2-02 tek aksiyon modeli; menü yolu da korunuyor. |
| 1.3 | "Use Allocation Backtest: OFF/ON" mod şeridi + Portfolio deep-link; prototipte yok. | PO-APPROVE — KALAN-B server-truth mod görünürlüğü (video 7:16–9:24). |
| 1.4 | BACKTEST RESULTS kartı + Composition (hash / Workspace version / Freeze) paneli prototipte yok. | PO-APPROVE — Stage 4/5 OCC-freeze sözleşmesinin görünür yüzü. |
| 1.5 | Satır rozetleri: uygulamada "Strategy · Enabled/Unsaved draft · #paylaşım" rozetleri; prototipte yalın metin satırı ("STRATEGY 1"). | PO-APPROVE — durum görünürlüğü kasıtlı. |
| 1.6 | **375 px: yatay taşma** — satır rozetleri/uzun metinler viewport'u aşıyor ("Enabled #10" kırpılıyor, composition hash taşıyor, açıklama metni sarmıyor). | **FIX(R2-14 a11y/responsive geçişi)** — Implementation Spec "horizontal page overflow" açık fail kriteri. |
| 1.7 | **375 px: katman çakışması** — Ready Check / RUN yüzer kontrolleri son strateji satırının üstüne biniyor. | **FIX(R2-14)** — "overlapping layers" fail kriteri. |

## 02 Strategy Details / inline editör (`/strategy` ↔ prototip inline STRATEGY kutusu)

| # | Sapma | Statü |
|---|---|---|
| 2.1 | Prototip inline editör 3 kolonlu yoğun grid (SETUP & DATA / DECISION LOGIC / RISK MANAGEMENT, 10 bölüm tek panelde); uygulamanın `/strategy` sayfası Create + My drafts + Attached tabloları gösteriyor — 10 bölümlü editör Mainboard inline'da açılıyor. | PO-APPROVE — sayfa, draft yönetim yüzeyi olarak bilinçle ayrıştı (R2-05/R2-07); inline editör prototip yerleşimini Mainboard'da veriyor. R2-14'te inline açık halinin ekran kanıtı sunulacak. |
| 2.2 | Prototipteki "Save as Strategy Package / Clear" alt bar'ına karşılık uygulamada Validate / Save akışı ve OCC rozetleri. | PO-APPROVE — sözleşme gereği (AT-01). |

## 04 Trading Signal (`/trading-signal` ↔ prototip inline TRADING SIGNAL kutusu)

| # | Sapma | Statü |
|---|---|---|
| 4.1 | Prototip: 4-kolon kompakt alan grid'i (Name/Source/Market/Base TF tek satırda); uygulama: tek kolon dikey uzun form — sayfa ~2.4× daha uzun. | **FIX önerisi (yeni slice: form grid sıkılaştırma)** ya da PO-APPROVE; ürün kararı gerekli. |
| 4.2 | Buton adları: prototip "Save As Trading Signal Package / Clear / Export As Package"; uygulama "Validate / Save Trading Signal / Cancel". | PO-APPROVE — package-export modeli V1'de yok (Future-Dev). |
| 4.3 | Uygulamada prototipte olmayan alanlar: Resolution kind, OHLCV use, Source binding (system-carried), Attach checkbox, Attached trading signals paneli. | PO-APPROVE — server sözleşmesinin gerçek alanları. |
| 4.4 | Import akışı iki panel (identity+mapping / file upload) olarak prototiple aynı bilgi mimarisinde; görsel ton uyumlu. | Sapma yok. |

## 05 Trade Log (`/trade-log`)

| # | Sapma | Statü |
|---|---|---|
| 5.1 | 4.1 ile aynı yoğunluk farkı (kompakt grid ↔ dikey form). | Aynı karar 4.1 ile birlikte. |
| 5.2 | 4.2/4.3 ile aynı buton adı + ek alan farkları (Currency, Approved market data revision vb.). | PO-APPROVE. |

## 06 Create Package (`/packages/create`)

| # | Sapma | Statü |
|---|---|---|
| 6.1 | Dropdown'lar makine değerleri gösteriyor: "indicator", "translate_existing_code", "pinescript", "python", "directional_signal" — prototipte insan-okur etiketler ("Indicator Package", "Translate Existing Code", "PineScript", "PHP", "Directional Signal"). | **FIX(önerilen mini slice: CP dropdown display-label haritası)** — presentation-only, sözleşme değişmez. |
| 6.2 | "Source code" ve "Declared dependencies" girişleri daralmış küçük textarea'lar olarak satır içine sıkışmış; prototipte geniş prompt textarea'sı formun ana bloğu. | **FIX(önerilen aynı mini slice: CP form yerleşimi)**. |
| 6.3 | "My requests" chip paneli uygulamada var, prototipte yok. | PO-APPROVE — request seçimi/geri dönüş R2-12 gereksinimi. |
| 6.4 | PACKAGE STATUS paneli request oluşmadan Baseline/Validation/Resolver bölümlerini gizliyor (prototip hepsini boş halde gösterir); "Create or select a request…" yönlendirme metni ekli. | PO-APPROVE — progressive disclosure bilinçli. |
| 6.5 | Başlık "Create Package" title-case; prototip "CREATE PACKAGE" all-caps. Sayfa başlık stilinde genel bir karar (bkz. 11.2). | PO-APPROVE (tema tutarlılığı) — tüm sayfalarda tutarlı uygulanmış. |

## 11 Market Data (`/market-data`)

| # | Sapma | Statü |
|---|---|---|
| 11.1 | Prototipte 4 adımlı süreç şeridi (Upload → Analyze → Create → Verify), 3 özet kartı (Registered/Allowed/Backtest Rule) ve "SÜREÇ REHBERİ" düğmesi; uygulamadaki karşılıkları R2/KALAN-A yüzeyinde birebir olmalı — matris tamamlanınca `normal--1440` ile hizalama R2-14'te teyit edilecek. | İnceleme R2-14'e taşındı (baseline bu PR'da). |
| 11.2 | Prototip sayfa başlıkları ALL-CAPS ("MARKET DATA"); uygulama title-case. | PO-APPROVE — global tipografi kararı. |

### 11 Market Data — baseline incelemesi (normal--1440)

| # | Sapma | Statü |
|---|---|---|
| 11.3 | Süreç şeridi, özet kartları, "+ Add Market Dataset", SÜREÇ REHBERİ ve registry tablosu prototiple aynı bilgi mimarisinde. Süreç adımlarında ek "PENDING" alt etiketi var (server-truth durum). | Sapma yok / PO-APPROVE (PENDING rozetleri). |
| 11.4 | Registry kolonları farklı: uygulama Revision state / Validation / Rev / Created (UTC); prototip Coverage / Resolution / Status / Version. Coverage ve Resolution kolonları uygulamada yok. | **PO-APPROVE adayı** — kolon seti server-truth şemadan; Coverage/Resolution eklenecekse ayrı slice (backend projeksiyon). |
| 11.5 | Type kolonu makine değeri "ohlcv" (prototip "OHLCV"). | FIX(6.1 ile aynı display-label mini slice). |

## 14/15 Ready Check + RUN & Backtest Results (`/backtest/ready-check`, `/backtest/run`)

| # | Sapma | Statü |
|---|---|---|
| 15.1 | Prototipte Ready Check sonucu Mainboard üstünde modal (Passed / Failed / Warnings 3 kolon) ve backtest sonucu Mainboard'ın BACKTEST RESULTS bölümünde inline; uygulamada bunlara ek olarak bağımsız `/backtest/ready-check` ve `/backtest/run` sayfaları var (Composition kartı + Request Backtest Run + No active run boş durumu). Mainboard inline sonuç kartı uygulamada da mevcut (bkz. 1.4). | PO-APPROVE — sayfalar TIER-2 route yüzeyi; inline davranış korunmuş. |
| 15.2 | Uygulama RUN sayfası workspace/hash/readiness satırlarını monospace ID'lerle gösteriyor; prototipte ID kavramı yok. | PO-APPROVE — raw ID görünürlüğü yalnız teknik alanlarda (GAP "raw JSON/ID girişi yok" kuralı giriş alanları içindir, salt-okur kimlikler değil). |

## 13 Portfolio / Equity Allocation (`/portfolio`)

| # | Sapma | Statü |
|---|---|---|
| 13.1 | 4 bölümlü yapı (Shared Capital Pool / Equity Allocation / Calculation Preview / Allocation Check) ve "USE EQUITY ALLOCATION FOR THIS BACKTEST" checkbox'ı prototiple birebir. | Sapma yok. |
| 13.2 | "+ Add item" aday listesi öğeleri ham `mbi_…` ULID + küçük "strategy" etiketiyle gösteriyor; prototip insan-okur adlar ("Strategy 1", "Copy Signal A"). | **FIX(önerilen mini slice: allocation aday satırında item display adı — Mainboard'ın kullandığı isim projeksiyonu zaten mevcut)**. |
| 13.3 | Uygulamada ek bölümler: Composition kartı, Portfolio Rules (Max total exposure / Conflicting signals — PR #320), Sync from Mainboard, Plan revision. Prototipte yok. | PO-APPROVE — KALAN-C + plan-revision sözleşmesi. |
| 13.4 | Prototip Equity Share % / Capital / Sizing Base kolon başlıklarını boş durumda da gösterir; uygulama satır eklenmeden kolonları göstermiyor (empty-state metni var). | PO-APPROVE — progressive disclosure. |

## 08 Package Library (`/packages/library`)

| # | Sapma | Statü |
|---|---|---|
| 8.1 | Filtre seti farklı: prototip Type / Market / Timeframe / Rationale Family / Status / Sort By; uygulama Type / Rationale family / Lifecycle / Validation / Approval / Visibility / Sort + Search kutusu. Market ve Timeframe filtreleri uygulamada yok. | PO-APPROVE adayı — Market/Timeframe server projeksiyonunda yok; eklenmesi backend slice ister. Kalanı süperset. |
| 8.2 | Satır rozetleri makine değerleri ("indicator v1", "embedded_system v1", "active/passed/approved" küçük harf); adı olmayan seed paketleri "—" görünüyor. | FIX(6.1 display-label mini slice kapsamına) + seed adlandırması test verisi meselesi (kod değil). |
| 8.3 | Prototip 6 tür bölümünü boş halde de listeler ("No package matched current filters."); uygulama yalnız dolu bölümleri gösteriyor. | PO-APPROVE adayı — boş bölüm başlıklarının gösterimi ürün kararı. |
| 8.4 | Uygulamada Import package paneli (manifest JSON, Recent imports) var; prototipte yok. | PO-APPROVE — post-V1 import/export yüzeyi. |

## 16 Results History (`/backtest/history`)

| # | Sapma | Statü |
|---|---|---|
| 16.1 | Mavi sonuç barları, sort dropdown ve ▼ genişletme prototiple uyumlu. Uygulama ek olarak checkbox + "Compare selected (0/2)" + View/Delete + Previous/Next sayfalama sunuyor. | PO-APPROVE — karşılaştırma/sayfalama sözleşme yüzeyi (superset). |
| 16.2 | Kapalı satır etiketi: prototip "BACKTEST RESULT n \| sembol \| TF \| strateji adları \| Net \| ROMAD \| DD \| Win Rate" headline metriklerini satırda gösterir; uygulama `btres_…` ULID + tarih + TF + sembol gösteriyor, metrikler ancak satır açılınca. | **FIX(önerilen mini slice: history satırında headline metrik özeti — server projeksiyonda metrikler zaten var)**. |

## 20 Trash (`/trash`)

| # | Sapma | Statü |
|---|---|---|
| 20.1 | Başlık, Admin-only açıklaması, tür filtresi + arama + "recoverable" sayacı ve boş durum metni prototiple hizalı. Küçük farklar: arama/tür sırası ters, prototipteki "0 audit events" sayacı uygulamada satırda değil. | PO-APPROVE (minör). |

## Kalan sayfalar — hızlı geçiş (detaylı inceleme R2-14)

Aşağıdaki sayfalar bu oturumda baseline+prototip çifti üretilmiş ancak
madde-madde derin karşılaştırması R2-14 son kabul geçişine bırakılmıştır
(dürüst sınır — "Complete" iddiası yok):

| Sayfa | İlk gözlem |
|---|---|
| 03 Outsource Signal | Deep-link chooser; birincil akışta menü alt seçenekleri (UI-03 uyumlu). |
| 07 Pre-Check | Uygulamada Create Package akışının sayfası olarak ayrı route; prototipte CP içinde. |
| 09 Embedded System Packages | Library ile aynı kalıp; 8.2 display-label bulgusu geçerli. |
| 10 Rationale Families | Yapı uyumlu görünüyor; derin kıyas R2-14. |
| 12 Research Data | Market Data kalıbında; derin kıyas R2-14. |
| 17 Arrange Metrics | Derin kıyas R2-14. |
| 18 Analysis Lab | Derin kıyas R2-14. |
| 19 Panel Management/Logs | Derin kıyas R2-14. |
| 21 User Manual / 22 Future Dev | Statik içerik sayfaları; derin kıyas R2-14. |

---

## Özet — düzeltme adayları (FIX) tek listede

| ID | Bulgu | Önerilen iş |
|---|---|---|
| F-1 | 375 px yatay taşma + RUN kontrollerinin içerik üstüne binmesi (1.6, 1.7) | R2-14 responsive geçişinde kapat (Implementation Spec fail kriteri). |
| F-2 | Makine-değeri görünümleri: CP dropdown'ları (6.1), Market Data "ohlcv" (11.5), Library rozetleri (8.2) | Tek "display-label haritası" mini slice — presentation-only. |
| F-3 | CP Source code / Declared dependencies alan yerleşimi (6.2) | Aynı mini slice ya da ayrı küçük slice. |
| F-4 | Portfolio "+ Add item" adayları ham `mbi_…` ULID (13.2) | Item display-adı projeksiyonunu kullan (frontend-only). |
| F-5 | Results History kapalı satırında headline metrik yok (16.2) | Satır özet metrikleri — server projeksiyonda veri mevcut. |
| F-6 | TS/TL formlarının dikey yoğunluğu prototipin kompakt grid'inden uzak (4.1, 5.1) | Ürün kararı: grid sıkılaştırma slice'ı ya da PO-APPROVE. |

Kalan tüm maddeler PO-APPROVE kategorisinde ve R2-14'te product-owner'a yazılı
onay için sunulacaktır. Bu doküman R2-13 kapsamında hiçbir maddeyi kapatmaz.

## Üretim kayıtları

- Baseline matris: 122 PNG (`normal` 77 · `empty` 14 · `loading` 14 · `error` 14 ·
  `permission-denied` 3), toplam ~20 MB — `frontend/e2e/screenshots/baseline/`.
- Prototip referansları: 20 PNG @1440 — `frontend/e2e/screenshots/prototype/`.
- Durum doğrulaması: loading = gerçek spinner UI (API stall), error = "Backend
  unavailable" banner'ı + kart-içi hata, permission-denied = server-truth
  `TRASH_ACCESS_FORBIDDEN` render'ı (ekran kanıtları baseline ağacında).
