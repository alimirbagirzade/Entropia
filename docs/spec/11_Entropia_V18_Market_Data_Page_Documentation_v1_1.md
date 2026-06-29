---
title: "Entropia V18 — Market Data Page Documentation v1.1"
page_number: 11
document_type: "Page implementation specification"
source_document: "Entropia_V18_Market_Data_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Market Data Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | SAYFA DOKÜMANTASYONU 11/22 | MARKET DATA
> **Original DOCX footer:** Canonical page documentation | Production V1 alignment |

*ENTROPIA V18*

# MARKET DATA

Sayfa Dokümantasyonu 11/22 | Ana fiyat ve execution veri katmanının kayıt, ingestion, validation, approval ve tüketim sözleşmesi

<table>
  <tr>
    <th>Belge kapsamı: Bu belge yalnız MARKET DATA sayfasının görünür arayüzünü ve onun Production V1 backend, lifecycle, job, validation, authorization, Agent parity ve audit davranışını kapsar. Research Data, Strategy Details, Ready Check, Run/Results, Trash ve Panel sayfaları ayrı dokümanlardır; burada yalnız Market Data ile doğrudan kesiştikleri kadar anılır.</th>
  </tr>
</table>

# 0. Document Control, Scope ve Source Traceability

<table>
  <tr>
    <th>Öğe</th>
    <th>İçerik</th>
  </tr>
  <tr>
    <td>Belge kimliği</td>
    <td>Entropia V18 | Page Documentation 11/22 | Market Data | v1.1</td>
  </tr>
  <tr>
    <td>Amaç</td>
    <td>V18 Market Data ekranındaki her görünür bileşeni; Production V1deki Market Dataset Root/Revision, raw asset, schema mapping, validation, approval, job, manifest, authorization ve audit sözleşmelerine indirgemek.</td>
  </tr>
  <tr>
    <td>Ana canonical kaynak</td>
    <td>Master Technical Reference v1.0, Modül 4: Market Data: Ana Fiyat ve Execution Veri Katmanı; ayrıca Modül 0, 1, 2, 3, 5, 10, 12, 14, 19 ve 20 çapraz bağımlılıkları.</td>
  </tr>
  <tr>
    <td>V18 HTML referansı</td>
    <td>Edit &gt; Market Data; `marketDataRegistry`; `renderMarketDataPage`; `renderMarketDataUploader`; `renderMarketDataDetail`; `analyzeMarketDataset`; `createMarketDataDataset`; `approveMarketDataDataset`; `openMarketDataDataset`; `getMarketDataWorkflowGuide`.</td>
  </tr>
  <tr>
    <td>Detay seviyesi referansı</td>
    <td>2.3. POSITION ENTRY LOGIC: kavramların ilk geçişte canonical tanımı, UI + backend + validation + state + Agent parity + acceptance test anlatım standardı.</td>
  </tr>
  <tr>
    <td>Kritik canonical kararlar</td>
    <td>Yalnız Approved Market Dataset Revision resmi backtest/candidate result, Package validation ve Research Data linki için kullanılabilir; approval yalnız Admin; raw asset immutable; UI browser state kaynak doğrusu değildir; her run exact revision + asset digest ile pinlenir.</td>
  </tr>
  <tr>
    <td>Açık Implementation Decisions</td>
    <td>V18de olmayan IANA timezone alanı, type-aware option gating, explicit mapping-review state, server-side list/query projection, job detail/retry düzeni ve optimistic concurrency davranışı bu belgede Master ilkelerine dayanarak netleştirilmiştir.</td>
  </tr>
</table>

## 0.1 Source Traceability Map

<table>
  <tr>
    <th>Sayfa bölümü</th>
    <th>Master ref</th>
    <th>V18 HTML ref</th>
    <th>Çapraz bağımlılık</th>
    <th>Karar / not</th>
  </tr>
  <tr>
    <td>Intro, process ribbon, summary cards</td>
    <td>M4 §1-3, §14</td>
    <td>`data-page-intro`, `data-workflow`, `dataset-summary-grid`</td>
    <td>M0 product boundary</td>
    <td>V18 workflow sıralaması korunur; kart sayıları client demo verisi değil backend projectiondan gelir.</td>
  </tr>
  <tr>
    <td>Dataset Setup</td>
    <td>M4 §6, §8-10, §14.2</td>
    <td>`renderMarketDataUploader`</td>
    <td>M1 roles; M2 revisions; M20 storage/workers</td>
    <td>Yıldızlı alanlar server-side preflight zorunluluğudur. UI field names canonical IDs yerine görünür labelsdır.</td>
  </tr>
  <tr>
    <td>Analyze / Create / Approve</td>
    <td>M4 §6, §15, §17</td>
    <td>`analyzeMarketDataset`, `createMarketDataDataset`, `approveMarketDataDataset`</td>
    <td>M3 audit; M19 API</td>
    <td>V18 local state mutasyonları Productionda command + durable job + immutable revision + Admin approval olur.</td>
  </tr>
  <tr>
    <td>Registry and Open detail</td>
    <td>M4 §4-5, §13-14</td>
    <td>`marketDataRegistry`, `renderMarketDataRows`, `renderMarketDataDetail`</td>
    <td>M10 selector; M12 run manifest; M5 link</td>
    <td>Registry root/current-revision projectiondır; detail raw file name değil immutable asset metadata/digest referansı gösterir.</td>
  </tr>
  <tr>
    <td>Delete/restore impact</td>
    <td>M4 §16; M3; M1</td>
    <td>V18 Market Data page delete UI içermez</td>
    <td>Trash page; Results/history</td>
    <td>Soft delete Page action olarak şart değildir; lifecycle etkisi açıkça uygulanır. Restore/permanent delete Admin-onlydir.</td>
  </tr>
</table>

## 0.2 Rule Provenance Register

<table>
  <tr>
    <th>Etiket</th>
    <th>Bu belgede kullanım biçimi</th>
  </tr>
  <tr>
    <td>Canonical Rule</td>
    <td>Masterda açıkça kilitli Production V1 kuralıdır. Kesin kipte yazılır. Örnek: Approved olmayan revision resmi backtest veya Research Data linki için kullanılamaz.</td>
  </tr>
  <tr>
    <td>Derived Rule</td>
    <td>Canonical kuralın teknik olarak zorunlu sonucudur. Örnek: Strategy Data Source dropdownu dataset adı değil `market_dataset_revision_id` döndürmelidir.</td>
  </tr>
  <tr>
    <td>V18 Interface Observation</td>
    <td>HTMLde görünen prototype davranışıdır. Örnek: Analyze Data client içinde schema preview üretir; Create Dataset doğrudan v0.1/Verified satırını local registryye ekler.</td>
  </tr>
  <tr>
    <td>Implementation Decision - Non-Canonical Gap Resolution</td>
    <td>Master teknik yönü zorunlu kıldığı halde UI ayrıntısını kilitlemediğinde kullanılır. Örnek: Custom timezone seçilince IANA timezone inputu zorunlu hale gelir.</td>
  </tr>
  <tr>
    <td>Future Dev Boundary</td>
    <td>Bu sayfada canlı broker/exchange emri, live quote trading veya gerçek para mutasyonu yoktur. Market Data ingestion aktif Production V1 davranışıdır; Live Trade değildir.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kapsam Sınırı

Market Data:Market Data, Entropia araştırma zincirinin ana fiyat ve execution gerçekliği katmanıdır. Bu sayfa, bir ham kaynağın yalnız dosya adı olarak saklanmasını değil; kimliği, instrument kapsamı, zaman anlamı, canonical mappingi, kalite raporu, immutable revisionı ve kullanım yetkisi açık bir dataset haline gelmesini sağlar.

Bu sayfa, Research Data için yer tutucu değildir; funding, open interest, liquidation, order-book imbalance, liquidity heatmap, on-chain, makro takvim ve benzeri context/feature kaynakları Research Data altında kendi native schema ve event/available-time sözleşmeleriyle yaşar. Market Data ayrıca Strategy Detailsdeki execution modeli, commission veya slippage alanlarını yönetmez. Dataset gözlemlenmiş fiyat/execution inputunu taşır; execution model bu inputu bir Run sırasında nasıl yorumlayacağını tanımlar.

<table>
  <tr>
    <th>Kapsam dışı sınır: Bu belge Research Data upload ekranını, Strategy Detailsdeki Data Source dropdownunun tüm alanlarını, Backtest Ready Check rule setini, Backtest Run workerını veya Trash kullanıcı arayüzünü yeniden tanımlamaz. Bunlar yalnız Market Dataset Revisionın seçilebilirlik, manifest pinning, lifecycle ve policy etkisi kadar anılır.</th>
  </tr>
</table>

## 1.1 Canonical kavramlar

<table>
  <tr>
    <th>Kavram</th>
    <th>Canonical kısa tanım</th>
    <th>Bu sayfadaki sonuç</th>
  </tr>
  <tr>
    <td>Market Dataset Root</td>
    <td>Bir veri ailesinin kalıcı kimliği. Örnek: belirli venue/instrument/resolution bağlamında kaynak seti.</td>
    <td>Liste satırı root kimliği ile ilişkilidir; rootun adı aynı kalırken yeni revisionlar üretilebilir.</td>
  </tr>
  <tr>
    <td>Market Dataset Revision</td>
    <td>Belirli raw asset, mapping, metadata, validation ve processed asset kümesinin immutable sürümü.</td>
    <td>Backtest, Research Data ve Strategy exact revisiona pinlenir; current revision SQL UPDATE ile mutate edilmez.</td>
  </tr>
  <tr>
    <td>Raw Asset</td>
    <td>Sağlayıcıdan geldiği haliyle immutable saklanan orijinal dosya/stream snapshot.</td>
    <td>Browse File sonrası saklanan dosya adı otorite değildir; asset ID ve digest otoritedir.</td>
  </tr>
  <tr>
    <td>Processed Asset</td>
    <td>Canonical schema ile normalize edilmiş, kalite kontrollerinden geçmiş kullanım verisi. Varsayılan biçim Parquet.</td>
    <td>Worker üretir; object storageda partitioned olarak saklanır; Backtest worker buradan okur.</td>
  </tr>
  <tr>
    <td>Schema Mapping</td>
    <td>Raw sütunların canonical alanlara açık dönüşümü.</td>
    <td>Analyzer mapping önerir; belirsizlik mapping review ile çözülür; mapping değişirse yeni revision gerekir.</td>
  </tr>
  <tr>
    <td>Record Time Basis</td>
    <td>Timestampin Bar Close/End, Bar Open/Start veya Event Time anlamı.</td>
    <td>Backtestte neyin hangi anda bilindiğini belirler; sadece format metadata değildir.</td>
  </tr>
  <tr>
    <td>Validation Run</td>
    <td>Parser/validator workerının belirli revision inputu için ürettiği kalite raporu.</td>
    <td>Her issue PASS/WARNING/BLOCKING_FAIL severitysi ile kaydedilir.</td>
  </tr>
  <tr>
    <td>Approval</td>
    <td>Adminin revisionı production research/backtest girdisi olarak kabul etmesi.</td>
    <td>Verified olmak Approval değildir; Approve for Use yalnız Admin commandidir.</td>
  </tr>
  <tr>
    <td>Manifest</td>
    <td>Kullanılan revision, raw/processed digest, mapping, coverage ve relevant engine contextini sabitleyen kayıt.</td>
    <td>Run and Agent provenance current/latest dataset adına dayanmaz.</td>
  </tr>
</table>

## 1.2 Sistem zincirindeki yeri

<table>
  <tr>
    <th>Raw source / provider connector<br/>  -&gt; asset intake + immutable raw storage<br/>  -&gt; profile + canonical mapping review<br/>  -&gt; normalize + validation + immutable revision manifest<br/>  -&gt; VERIFIED / NEEDS_REVIEW / REJECTED<br/>  -&gt; Admin APPROVED<br/>  -&gt; Strategy selector + Research Data link + Ready Check + Backtest Run manifest<br/>  -&gt; Result / Agent artifact provenance</th>
  </tr>
</table>

# 2. Erişim, Görünürlük, Ownership ve Server-Side Policy

UI görünürlüğü, enabled/disabled button veya doğrudan URL erişimi tek başına yetki değildir. Her query ve mutating command backendde principal, role, ownership, resource lifecycle, visibility, dependency state ve operation türü üzerinden yeniden doğrulanır. Rationale Families için geçerli global shared-editing exception Market Data için geçerli değildir.

## 2.1 Role matrisi

<table>
  <tr>
    <th>Actor</th>
    <th>Sayfayı/listeleri görme</th>
    <th>Draft/upload/analyze</th>
    <th>Create revision / edit</th>
    <th>Approve</th>
    <th>Delete / Trash</th>
    <th>Use</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Hayır; yalnız açık ürün açıklaması varsa public read yüzeyi.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Kendi + explicitly shared/published/system Market Data projectionları.</td>
    <td>Kendi ownerlığında draft, upload, analyze/validation request oluşturabilir.</td>
    <td>Kendi draft/revision adayını düzenleme yerine yeni candidate revision/mapping kararı üretebilir.</td>
    <td>Hayır.</td>
    <td>Kendi normal dataset rootlarını soft delete edebilir; Trash göremez.</td>
    <td>Yalnız ACTIVE + APPROVED ve policy ile izinli revisionları seçebilir.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Çalışma kapsamındaki erişilebilir datasetleri görür ve kullanır.</td>
    <td>Kendi draftı için yapabilir.</td>
    <td>Yalnız kendi ownerlığındaki mutable draft/aday akışında mutasyon yapar.</td>
    <td>Hayır.</td>
    <td>Kendi rootlarını soft delete edebilir; Trash yok.</td>
    <td>Erişilebilir ACTIVE + APPROVED revisionları kullanabilir.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm erişilebilir root/revision, validation, audit ve selector projectionlarını görür.</td>
    <td>Yapabilir.</td>
    <td>Tüm uygun kaynaklarda policy override ile yönetebilir; immutable Approved revisionı değiştirmek yerine yeni revision üretir.</td>
    <td>Evet, yalnız Admin.</td>
    <td>Tüm normal resource soft delete; Trash view/restore/permanent delete yalnız Admin.</td>
    <td>Tüm uygun ACTIVE + APPROVED revisionları kullanır.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Uygun system working content ve policy ile izinli veri projectionlarını backend API üzerinden görür.</td>
    <td>Kendi Agent ownerlığında draft/intake/analyze job oluşturabilir.</td>
    <td>Yalnız kendi output/draftlarını değiştirir; başkasının rootuna mutate etmez.</td>
    <td>Hayır.</td>
    <td>Yalnız kendi outputları için soft delete başlatabilir; Trash yok.</td>
    <td>Approved revisionları doğrudan Tool Gateway üzerinden kullanır; Verified/Needs Review veriyi yalnız metadata/validation bağlamı olarak inceler.</td>
  </tr>
</table>

## 2.2 Server-side authorization değerlendirme sırası

1. Caller principalını çöz: authenticated human session veya trusted Agent/service identity. Client bodydeki role/owner alanını otorite kabul etme.

2. Operationı sınıflandır: list, view, upload, analyze, confirm_mapping, create_revision, approve, reject, deprecate, use, soft_delete, restore veya permanent_delete.

3. Target root/revision/asset contextini yükle: owner, visibility, lifecycle, approval state, validation summary, existing manifest pins ve deletion state.

4. Role policyyi, ownershipi, approval-only-Admin kuralını ve lifecycle/dependency gateini uygula.

5. İzin yoksa mutation başlatmadan structured error döndür; UI optimistic stateini kalıcı kabul etme.

6. İzin varsa transaction + audit/outbox event + gerektiğinde async job enqueue ile commandi tamamla.

3. V18 Interface Behavior: Görünür Yerleşim ve Bileşen Envanteri

V18de page title satırında MARKET DATA başlığı ile sağda `ⓘ SÜREÇ REHBERİ` butonu bulunur. Başlık altında üç alan görünür: açıklama metni, dört adımlı workflow ribbon ve üç adet özet kartı. Bu alanların tamamı birincil sayfa içeriğidir; dataset setup alanı ise `+ Add Market Dataset` ile açılıp kapanır.

## 3.1 Üst açıklama ve workflow ribbon

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 görünümü / varsayılan metin</th>
    <th>Production davranışı</th>
  </tr>
  <tr>
    <td>Page Intro</td>
    <td>“Market Data is the primary price and execution layer for research and backtests…”; yalnız OHLCV, tick/trades ve spread/execution veri burada tutulur.</td>
    <td>Statik yönlendirme metnidir; locale/versioned content registryden sunulabilir ancak domain state üretmez.</td>
  </tr>
  <tr>
    <td>Step 1</td>
    <td>Upload raw source.</td>
    <td>Asset intake başlayabilmesi için raw asset kaydı gerekir.</td>
  </tr>
  <tr>
    <td>Step 2</td>
    <td>Analyze &amp; map fields.</td>
    <td>Durable profile/mapping jobı raw dosyayı değiştirmeden çalışır.</td>
  </tr>
  <tr>
    <td>Step 3</td>
    <td>Create dataset version.</td>
    <td>Immutable revision manifest ve processed asset üretimidir; client-side array push değildir.</td>
  </tr>
  <tr>
    <td>Step 4</td>
    <td>Verify / approve for use.</td>
    <td>VERIFIED technical state ile Admin APPROVED kararı ayrıdır.</td>
  </tr>
</table>

## 3.2 Özet kartları

<table>
  <tr>
    <th>Kart</th>
    <th>V18 varsayılanı</th>
    <th>Production Projection</th>
  </tr>
  <tr>
    <td>REGISTERED DATASETS</td>
    <td>Registrydeki local array uzunluğu.</td>
    <td>Role-aware query ile görünen, ACTIVE ve erişilebilir root/revision projection sayısı. Soft-deleted ve unauthorized kayıtlar sayıya dahil edilmez.</td>
  </tr>
  <tr>
    <td>ALLOWED DATA TYPES</td>
    <td>3: OHLCV, tick/trades, spread/execution.</td>
    <td>Canonical type registryden gelir. UI ya da API başka bir market data typeı sessizce kabul etmez.</td>
  </tr>
  <tr>
    <td>BACKTEST RULE</td>
    <td>Known Time: approvaldan önce time basis declared.</td>
    <td>Record Time Basis, timezone, resolution, schema mapping ve validation stateinin Run/Ready Check açısından minimum sonuç özetidir.</td>
  </tr>
</table>

## 3.3 Registry tablosu ve V18 başlangıç satırları

V18 registry tablosu sütunları: Dataset, Type, Source, Instrument, Coverage, Resolution, Status, Version ve Action. Her satırdaki `Open` butonu seçili dataset detail kartını tablonun altında açar. Aşağıdaki üç satır HTMLdeki demo başlangıç kaydıdır; Productionda bunlar sample data değil backend catalog projectionıdır.

<table>
  <tr>
    <th>Dataset</th>
    <th>Type</th>
    <th>Source</th>
    <th>Instrument</th>
    <th>Coverage</th>
    <th>Resolution</th>
    <th>Status</th>
    <th>Version</th>
  </tr>
  <tr>
    <td>Binance Futures Core Universe · 15m OHLCV</td>
    <td>OHLCV</td>
    <td>Binance Futures</td>
    <td>BTCUSDT Perpetual</td>
    <td>2022–2026</td>
    <td>15m</td>
    <td>Approved</td>
    <td>v1.0</td>
  </tr>
  <tr>
    <td>FX Majors · 1h OHLCV</td>
    <td>OHLCV</td>
    <td>Dukascopy</td>
    <td>EURUSD, GBPUSD, USDJPY</td>
    <td>2020–2026</td>
    <td>1h</td>
    <td>Verified</td>
    <td>v0.9</td>
  </tr>
  <tr>
    <td>BTCUSDT Selected Sessions · Tick Trades</td>
    <td>Tick / Trades</td>
    <td>External Provider</td>
    <td>BTCUSDT Perpetual</td>
    <td>Selected 2025 sessions</td>
    <td>Event Based</td>
    <td>Needs Review</td>
    <td>v0.1</td>
  </tr>
</table>

## 3.4 Open dataset detail card

<table>
  <tr>
    <th>Visible item</th>
    <th>V18 behaviour</th>
    <th>Production requirement</th>
  </tr>
  <tr>
    <td>Title</td>
    <td>Selected dataset name.</td>
    <td>Dataset Root display name + current/selected revision identity + lifecycle/approval badge. Name alone is not command target.</td>
  </tr>
  <tr>
    <td>Raw source</td>
    <td>Raw file name or “Stored source file”.</td>
    <td>Asset name is descriptive; show asset ID, immutable digest, original content type/size and controlled retrieval authority. Raw bytes remain immutable.</td>
  </tr>
  <tr>
    <td>Time context</td>
    <td>Timezone + Record Time Basis.</td>
    <td>Show canonical timezone/IANA identifier, record time basis, resolution, availability semantics and coverage summary.</td>
  </tr>
  <tr>
    <td>Canonical schema</td>
    <td>Text such as `timestamp | instrument_id | open | high | low | close | volume`.</td>
    <td>Show schema version, required columns, unit meaning and mapping reference; type-specific details are expandable.</td>
  </tr>
  <tr>
    <td>Validation</td>
    <td>Human-readable validation summary.</td>
    <td>Show latest Validation Run ID/status, issue counts by severity, coverage, validator engine version and open blocking issues.</td>
  </tr>
  <tr>
    <td>Usage</td>
    <td>Primary price/execution input for selected workflows.</td>
    <td>Show policy-aware use eligibility and usage/provenance counters; no implicit claim that every strategy or execution model is compatible.</td>
  </tr>
  <tr>
    <td>Ownership &amp; version</td>
    <td>Owner label + v0.1.</td>
    <td>Show owner principal, created/updated metadata, root ID, revision ID, supersedes link, approval identity/timestamp and deletion state where relevant.</td>
  </tr>
</table>

4. Dataset Setup: Tüm Alanlar, Varsayılanlar ve Dependency Contract

V18de `+ Add Market Dataset` butonu bir üç kolonlu MARKET DATASET SETUP kabuğunu açar: SOURCE & IDENTITY, TIME & INSTRUMENT, ANALYSIS, VALIDATION & USE. `Close Dataset Setup` formu kapatır ve V18 local workflow stateini sıfırlar. Productionda close yalnız UI draft görünümünü kapatır; serverda zaten yaratılmış asset/job/revision varsa bunlar ancak explicit discard/cancel policy ile değiştirilebilir.

## 4.1 Interaction State Matrix

<table>
  <tr>
    <th>Bileşen</th>
    <th>Default</th>
    <th>Aktifleşme koşulu</th>
    <th>Disabled / hidden iken payload &amp; engine etkisi</th>
    <th>Stale/recovery</th>
  </tr>
  <tr>
    <td>Dataset Setup shell</td>
    <td>Kapalı.</td>
    <td>`+ Add Market Dataset` tıklanır.</td>
    <td>Kapalıyken form alanı DOM/payloadta yoktur; mevcut server draft silinmiş sayılmaz.</td>
    <td>UI tekrar açıldığında current draft/job state backendden hydrate edilir; V18 reset behavior canonical değildir.</td>
  </tr>
  <tr>
    <td>Browse File</td>
    <td>Enabled. “No file selected”.</td>
    <td>Setup açık.</td>
    <td>File yoksa Analyze Data validation blocker.</td>
    <td>Upload expired/failed ise yeniden upload istenir; raw asset digest değişirse analysis result stale olur.</td>
  </tr>
  <tr>
    <td>Analyze Data</td>
    <td>Enabled.</td>
    <td>Tüm minimum metadata + raw asset mevcut olmalıdır. V18 buton enable kalabilir ancak validasyon clickte yapılır.</td>
    <td>Eksik girişte command accepted olmaz; mapping/validation job oluşmaz.</td>
    <td>Metadata veya raw asset değişirse previous analysis stale olur; yeniden analyze gerekir.</td>
  </tr>
  <tr>
    <td>Create Dataset</td>
    <td>Disabled.</td>
    <td>Analysis/mapping preview terminal başarı sonucu verir; unresolved blocking mapping yoktur.</td>
    <td>Disabled iken revision created olmaz, selector projectiona kayıt düşmez.</td>
    <td>Mapping, timezone, data type, coverage veya raw asset değişirse create eligibility yeniden hesaplanır.</td>
  </tr>
  <tr>
    <td>Approve for Use</td>
    <td>Disabled.</td>
    <td>Revision VERIFIED, ACTIVE, non-deleted, no blocking issue; caller Admin.</td>
    <td>Non-Admin / non-Verified / soft-deleted durumda approval command yürütülmez.</td>
    <td>New validation run, deprecation veya conflict ile stale hale gelirse user refreshes revision state.</td>
  </tr>
  <tr>
    <td>Open detail</td>
    <td>Her registry satırında enabled.</td>
    <td>Caller can_view ve row projection exists.</td>
    <td>Unauthorized/deleted root detail endpointten de dönmez.</td>
    <td>Revision current state değişmişse detail header `Current revision changed` banner gösterir; UI server response ile yenilenir.</td>
  </tr>
</table>

## 4.2 Field Contract Matrix - SOURCE & IDENTITY

<table>
  <tr>
    <th>Alan</th>
    <th>V18 UI / default</th>
    <th>Zorunluluk</th>
    <th>Options / conditional behavior</th>
    <th>Production payload &amp; validation</th>
  </tr>
  <tr>
    <td>Raw source file *</td>
    <td>Hidden native file input + Browse File. Default: No file selected.</td>
    <td>Always required before Analyze.</td>
    <td>Accepted upload type configured server-side; V18 file picker restricts no visible extensions. XLSX is not base ingestion contract.</td>
    <td>`raw_asset_id` after finalized upload; filename only metadata. Require immutable digest, size, content type and source asset provenance.</td>
  </tr>
  <tr>
    <td>Dataset Name *</td>
    <td>Text input. Placeholder: “e.g. Binance Futures BTCUSDT · 15m OHLCV”.</td>
    <td>Always required.</td>
    <td>Whitespace-normalized. Duplicate visible name allowed only if root identity differs; same exact root identity needs duplicate detection.</td>
    <td>`display_name`; must be non-empty and max length bounded. Never use display name as revision identity.</td>
  </tr>
  <tr>
    <td>Market *</td>
    <td>Select. Default: Crypto.</td>
    <td>Always required.</td>
    <td>Crypto; Forex; Other. UI label is market class, not instrument identity.</td>
    <td>`market_class` enum. `Other` remains valid but instrument registry resolution must still succeed.</td>
  </tr>
  <tr>
    <td>Data Type *</td>
    <td>Select. Default: OHLCV.</td>
    <td>Always required.</td>
    <td>OHLCV; Tick / Trades; Spread / Execution. Choice controls canonical target schema and type-specific validators.</td>
    <td>`data_type` enum. Type switch invalidates prior analysis/mapping and requires re-analyze.</td>
  </tr>
  <tr>
    <td>Source / Provider *</td>
    <td>Text input. Placeholder: “e.g. Binance Futures”.</td>
    <td>Always required.</td>
    <td>Provider may be file-origin, API/vendor, or controlled connector; source name is not a security identity.</td>
    <td>`provider_label` plus optional `provider_id`/connector reference. Must be recorded in revision manifest.</td>
  </tr>
</table>

## 4.3 Field Contract Matrix - TIME & INSTRUMENT

<table>
  <tr>
    <th>Alan</th>
    <th>V18 UI / default</th>
    <th>Zorunluluk</th>
    <th>Options / conditional behavior</th>
    <th>Production payload &amp; validation</th>
  </tr>
  <tr>
    <td>Instrument Scope *</td>
    <td>Text input. Placeholder: “e.g. BTCUSDT Perpetual”.</td>
    <td>Always required.</td>
    <td>May describe one or multiple instruments in prototype. Production resolves each to canonical registry IDs.</td>
    <td>`instrument_ids[]`, venue/contract metadata. Free-text display cannot be sole linkage; spot/futures/perpetual distinctions must resolve.</td>
  </tr>
  <tr>
    <td>Resolution *</td>
    <td>Select. Default: 15m.</td>
    <td>Always required.</td>
    <td>1m; 5m; 15m; 1h; 1D; Event Based. Production type-aware gate: Event Based allowed for Tick/Trades and event-style Spread/Execution; OHLCV must use declared bar resolution.</td>
    <td>`resolution_kind` + `resolution_value`. Must match inferred dataset cadence or a documented normalization transform.</td>
  </tr>
  <tr>
    <td>Timezone *</td>
    <td>Select. Default: UTC.</td>
    <td>Always required.</td>
    <td>UTC; Exchange Time; Custom. **Implementation Decision:** Custom activates required IANA timezone input, e.g. `America/New_York`; V18 does not yet render it.</td>
    <td>`timezone_mode`, `timezone_iana`. Timezone must convert timestamps deterministically to UTC canonical instants.</td>
  </tr>
  <tr>
    <td>Record Time Basis *</td>
    <td>Select. Default: Bar Close / End Time.</td>
    <td>Always required.</td>
    <td>Bar Close / End Time; Bar Open / Start Time; Event Time. Selection determines known-time semantics and is immutable revision metadata.</td>
    <td>`record_time_basis` enum. Change requires a new revision; it cannot be patched on an Approved revision.</td>
  </tr>
  <tr>
    <td>What will be standardized?</td>
    <td>Read-only preview card.</td>
    <td>Not a user input.</td>
    <td>Text changes depending on data type.</td>
    <td>UI must state: only selected type’s price/execution fields are normalized; raw source remains unchanged and separate.</td>
  </tr>
</table>

## 4.4 Field Contract Matrix - ANALYSIS, VALIDATION & USE

<table>
  <tr>
    <th>Item</th>
    <th>V18 default</th>
    <th>Activation / conditional requirement</th>
    <th>Production data &amp; behavior</th>
  </tr>
  <tr>
    <td>Standardization preview</td>
    <td>“Choose the source and minimum context, then select Analyze Data.”</td>
    <td>After successful analyze/profile job, show candidate mapping, schema, detected fields, timezone parse assumptions and unresolved ambiguities.</td>
    <td>Server returns analysis job result; browser must not declare final mapping based on local file inspection.</td>
  </tr>
  <tr>
    <td>Schema mapping quality</td>
    <td>Pending.</td>
    <td>Becomes Ready for mapping only when target schema requirements can be deterministically mapped or user/Agent confirms mapping.</td>
    <td>Store mapping proposal + confirmation + mapping version. Ambiguous essential fields block revision creation.</td>
  </tr>
  <tr>
    <td>Time gaps / duplicates</td>
    <td>Pending.</td>
    <td>Analyze/validate job must run.</td>
    <td>Persist issue counts/samples and deterministic dedupe policy if a transform is approved.</td>
  </tr>
  <tr>
    <td>Price / execution consistency</td>
    <td>Pending.</td>
    <td>Type-specific rules required.</td>
    <td>OHLC low/high rules; Tick ordering/side unknown; Spread bid/ask and unit consistency. Blocking failure prevents VERIFIED/APPROVED.</td>
  </tr>
  <tr>
    <td>Instrument &amp; timezone</td>
    <td>Pending.</td>
    <td>Metadata + parser profile must agree or result becomes Needs Review/Rejected.</td>
    <td>Instrument registry and timezone resolution are validated server-side; silent local assumption forbidden.</td>
  </tr>
  <tr>
    <td>Current status</td>
    <td>Draft until terminal state.</td>
    <td>Draft -&gt; analysis/running -&gt; Needs Review / Rejected / Verified -&gt; Approved.</td>
    <td>V18 visible labels are simplified projection. Deletion lifecycle is separate from approval/workflow state.</td>
  </tr>
</table>

## 4.5 Conditional field reset and preservation rules

<table>
  <tr>
    <th>Trigger</th>
    <th>UI state after change</th>
    <th>Payload/engine effect</th>
    <th>User-visible warning</th>
  </tr>
  <tr>
    <td>Raw source replaced</td>
    <td>Analysis preview and validation state marked stale. Create/Approve disabled.</td>
    <td>New `raw_asset_id` changes manifest input; prior mapping cannot be reused silently.</td>
    <td>“Raw source changed. Re-analyze the dataset before creating a new revision.”</td>
  </tr>
  <tr>
    <td>Data Type changed</td>
    <td>Schema preview, mapping proposal, type-specific validation and coverage inference cleared.</td>
    <td>No existing type mapping enters revision payload.</td>
    <td>“Data type changed. Previous schema mapping is no longer valid.”</td>
  </tr>
  <tr>
    <td>Instrument/Resolution/Timezone/Record Time Basis changed after analysis</td>
    <td>Analysis must be rerun; the old terminal result remains historic job output but cannot create new revision.</td>
    <td>Known-time and compatibility semantics change; previous mapping/validation no longer establishes a valid revision.</td>
    <td>“Time or instrument context changed. Re-analyze before creating a dataset revision.”</td>
  </tr>
  <tr>
    <td>Close Dataset Setup</td>
    <td>V18 resets local form workflow.</td>
    <td>Production: only client draft UI closes. Persisted asset/job/draft remains unless an explicit discard/cancel command succeeds.</td>
    <td>“Setup closed. Existing uploaded assets and analysis jobs remain available in your draft.”</td>
  </tr>
  <tr>
    <td>Approved revision needs correction</td>
    <td>Edit controls do not patch current Approved revision.</td>
    <td>New draft/candidate revision must be created with `supersedes_revision_id`.</td>
    <td>“Approved revisions are immutable. Create a new revision to change source, mapping, coverage or time context.”</td>
  </tr>
</table>

5. Information Content Catalog: ⓘ, Helper, Warning, Toast ve Error Metinleri

Bu sayfada visible information control, başlıktaki `ⓘ SÜREÇ REHBERİ` butonudur. Aşağıdaki metin Production UI için doğrudan kullanılabilir nihai içeriktir. Form alanlarının yanında ayrı ⓘ ikonları V18de bulunmaz; bu nedenle yeni field-level info icon eklenmesi zorunlu değildir. Bilgi ihtiyacı helper text, validation message ve Workflow Guide ile karşılanır.

5.1 ⓘ SÜREÇ REHBERİ - Panel Title: “MARKET DATA — SÜREÇ REHBERİ”

<table>
  <tr>
    <th>Amaç: Market Data, araştırma ve backtest için ana fiyat ve execution katmanıdır. Bu sayfada yalnız OHLCV, Tick / Trades veya Spread / Execution girdileri bulunur. Funding, open interest, liquidation, heatmap ve diğer destekleyici araştırma verileri Research Data altında tutulur.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Panel bölümü</th>
    <th>Nihai UI metni</th>
  </tr>
  <tr>
    <td>1. Bu sayfaya hangi veriler gelir?</td>
    <td>OHLCV: bar temelli fiyat ve hacim verisi. Tick / Trades: tekil fiyat, miktar ve yön olayları. Spread / Execution: bid/ask veya işlem maliyeti girdileri. Funding, open interest, liquidation, order-book research feature ve türetilmiş bağlam verileri burada tutulmaz.</td>
  </tr>
  <tr>
    <td>2. Zorunlu kimlik bilgileri</td>
    <td>Dataset adı ve kaynak/sağlayıcı; gerçek instrument kapsamı; veri tipi ve çözünürlük; timezone ve kayıt zamanının neyi temsil ettiği; değişmeden saklanan ham kaynak dosyası.</td>
  </tr>
  <tr>
    <td>3. Zorunlu süreç</td>
    <td>1) Ham kaynağı yükle: Orijinal dosya kanıt olarak saklanır; mapping ham dosyanın üzerine yazmaz. 2) Analiz et ve eşle: Ingestion servisi kolonları, timestampleri ve kaynak yapısını okur; uygun canonical şemayı önerir. 3) Validasyonu incele: Coverage, gaps, duplicates, geçersiz değerler ve zaman bağlamını kontrol et. 4) Dataset sürümü oluştur: Sürüm taşıyan immutable araştırma nesnesi oluşur; mevcut çalışmalar kendi kullandıkları sürüme sabit kalır. 5) Verify / approve: Ana backtest kaynağı olarak yalnız Approved revision seçilebilir.</td>
  </tr>
  <tr>
    <td>4. Canonical mapping</td>
    <td>OHLCV: `timestamp | instrument_id | open | high | low | close | volume`. Tick / Trades: `timestamp | instrument_id | price | size | side`. Spread / Execution: `timestamp | instrument_id | bid | ask | spread | execution_cost`. Bütün veri türleri tek evrensel tabloya zorlanmaz.</td>
  </tr>
  <tr>
    <td>5. Backtest korumaları</td>
    <td>Instrument stratejinin hedeflediği piyasa ile gerçekten eşleşmelidir. Timezone ile bar/event time açıkça tanımlanmalıdır. 15m veri görünmeyen intrabar ayrıntısına dayanan varsayımları desteklemez. Gap, duplicate ve geçersiz OHLC/fiyat kayıtları approval öncesinde incelenmelidir.</td>
  </tr>
  <tr>
    <td>Örnek — 15 dakikalık OHLCV</td>
    <td>Ham kaynak: `binance_btcusdt_15m_2022_2026.parquet`. Instrument: BTCUSDT Perpetual — Binance Futures. Kayıt zamanının anlamı: Bar Close / End Time. Timezone: UTC. Canonical dataset: BTCUSDT Binance Futures · 15m OHLCV · v1.0. Backtest uygunluğu: Approved.</td>
  </tr>
  <tr>
    <td>Canlı sistem kuralı</td>
    <td>Bu arayüz süreci gösterir; gerçek approval dosyayı ayrıştıran, raw ve mapped assetleri saklayan, validation sonuçlarını hesaplayan ve onaysız revisionların backteste girmesini engelleyen backend işleriyle zorunlu olarak uygulanır.</td>
  </tr>
</table>

## 5.2 Form helper, warning, toast ve error catalog

<table>
  <tr>
    <th>UI context</th>
    <th>Nihai metin</th>
    <th>Severity / behavior</th>
  </tr>
  <tr>
    <td>Initial setup note</td>
    <td>Select the source and minimum context, then analyze the intended mapping.</td>
    <td>Info. Setup first opened. Localized production equivalent may be Turkish UI language settingine göre render edilir.</td>
  </tr>
  <tr>
    <td>No file selected</td>
    <td>No file selected</td>
    <td>Neutral filename state. Analyze Data için raw source blocker.</td>
  </tr>
  <tr>
    <td>Analyze blocked: missing inputs</td>
    <td>Dataset name, source/provider, instrument scope and raw source file are required before analysis.</td>
    <td>Inline validation. Focus first missing field; job queueye command bırakma.</td>
  </tr>
  <tr>
    <td>Analyze accepted</td>
    <td>Analysis started. Parsing, profiling and validation continue in the background. You can close this panel without stopping the job.</td>
    <td>Loading toast + job badge. UI poll/event stream ile state günceller.</td>
  </tr>
  <tr>
    <td>Analysis preview ready</td>
    <td>Analysis preview completed. Review the intended mapping and create a versioned dataset.</td>
    <td>Success/info. Create Dataset only mapping prerequisites satisfied when enabled.</td>
  </tr>
  <tr>
    <td>Mapping ambiguity</td>
    <td>The source contains fields that cannot be mapped unambiguously. Review the highlighted mapping before creating a revision.</td>
    <td>Blocking or Needs Review, depending on whether essential field missing/ambiguous.</td>
  </tr>
  <tr>
    <td>Create success</td>
    <td>Dataset revision {revision_label} was created. Full validation status is available in the dataset detail.</td>
    <td>Success. Do not promise Approved. Detail route returns canonical revision ID/state.</td>
  </tr>
  <tr>
    <td>Approval blocked</td>
    <td>This revision is not Verified with all required checks complete. Approval is unavailable.</td>
    <td>Error/disabled reason.</td>
  </tr>
  <tr>
    <td>Approval denied</td>
    <td>Only an Admin can approve a Market Data revision for production use.</td>
    <td>403. UI role display never substitutes for server guard.</td>
  </tr>
  <tr>
    <td>Approval success</td>
    <td>Dataset revision {revision_label} is approved for use and is now available in compatible Strategy, Research Data and Backtest workflows.</td>
    <td>Success + selector index update after server event.</td>
  </tr>
  <tr>
    <td>Stale input</td>
    <td>Dataset context changed while you were editing. Refresh the latest revision state before continuing.</td>
    <td>409/412 conflict. Preserve user input locally for compare/reapply where safe.</td>
  </tr>
  <tr>
    <td>Dataset soft-deleted</td>
    <td>This Market Data revision is soft-deleted and cannot be selected for new work. Historical manifests remain unchanged.</td>
    <td>Lifecycle warning.</td>
  </tr>
  <tr>
    <td>Resolution compatibility</td>
    <td>The selected 15m OHLCV dataset cannot support an execution mode that requires intrabar fill order. Select tick data or explicitly use a documented model assumption.</td>
    <td>Ready Check / use compatibility blocker or warning as appropriate.</td>
  </tr>
</table>

# 6. Buttons, Commands ve State Davranışı

<table>
  <tr>
    <th>Visible action</th>
    <th>V18 behavior</th>
    <th>Production command / precondition</th>
    <th>Loading, success, error, retry, audit</th>
  </tr>
  <tr>
    <td>+ Add Market Dataset</td>
    <td>Toggles setup shell open.</td>
    <td>UI-only `open_market_dataset_setup`. Caller must be authenticated before server draft creation; no persistent object required merely to open UI.</td>
    <td>No job. If server draft is resumed, fetch draft state. Audit only if persistent draft is created.</td>
  </tr>
  <tr>
    <td>Close Dataset Setup</td>
    <td>Closes shell and resets V18 local workflow.</td>
    <td>UI-only close; explicit `discard_market_dataset_draft` or `cancel_market_job` is separate and confirmation-gated.</td>
    <td>Do not silently cancel upload/analysis. Show recoverable draft notice.</td>
  </tr>
  <tr>
    <td>Browse File</td>
    <td>Opens native file picker.</td>
    <td>Two-phase upload: `start_market_raw_upload` -&gt; object upload -&gt; `finalize_market_raw_upload`. Validate content/size server-side.</td>
    <td>Show upload progress; failure retains metadata but no finalized asset. Audit: MARKET_RAW_UPLOAD_STARTED/FINALIZED.</td>
  </tr>
  <tr>
    <td>Analyze Data</td>
    <td>Client validates name/source/instrument/file and updates preview.</td>
    <td>`request_market_dataset_analysis(draft_id, raw_asset_id, metadata, idempotency_key)`. Preflight metadata required. Enqueues durable profiling/mapping/validation job.</td>
    <td>Button becomes loading; duplicate request returns same job/ref. Job errors structured with retry action. Audit: MARKET_ANALYSIS_REQUESTED.</td>
  </tr>
  <tr>
    <td>Create Dataset</td>
    <td>V18 adds local `v0.1`, status Verified.</td>
    <td>`create_market_dataset_revision(draft_id, confirmed_mapping_id, expected_draft_version, idempotency_key)`. Requires terminal valid mapping/validation facts; creates immutable revision manifest/processed asset.</td>
    <td>Loading while command validates/inserts. Success returns revision ID/state. 409 stale -&gt; refresh/compare. Audit: MARKET_MAPPING_CONFIRMED, MARKET_REVISION_CREATED.</td>
  </tr>
  <tr>
    <td>Approve for Use</td>
    <td>V18 immediately changes status Approved.</td>
    <td>`approve_market_dataset_revision(revision_id, expected_revision_state, approval_note?, idempotency_key)`. Caller Admin; revision VERIFIED, active, non-deleted, no blockers.</td>
    <td>Loading lock + server state refresh. 403/422/409 explicit. Success updates selector projection. Audit: MARKET_REVISION_APPROVED.</td>
  </tr>
  <tr>
    <td>Open</td>
    <td>Sets selected index and renders detail card.</td>
    <td>`get_market_dataset_detail(root_id, revision_id?)`. Server verifies view policy and returns root/current or requested allowed revision projection.</td>
    <td>No long job. 404/403 must not reveal private data. If current changed, show revision-changed banner.</td>
  </tr>
  <tr>
    <td>Detail actions (production extension)</td>
    <td>Not separately visible in V18.</td>
    <td>Policy-aware `create_successor_revision`, `deprecate_market_dataset_revision`, `soft_delete_market_dataset`, `request_market_data_purge`.</td>
    <td>Implementation Decision: actions live within detail overflow. Never patch Approved revision in place; destructive actions confirmed/audited.</td>
  </tr>
</table>

## 6.1 Command idempotency and concurrency contract

<table>
  <tr>
    <th>Mutating request envelope (conceptual)<br/>{<br/>  request_id,<br/>  idempotency_key,<br/>  actor_context: server-derived,<br/>  expected_draft_version | expected_revision_state,<br/>  command_payload<br/>}<br/><br/>Server behavior<br/>- Same actor + same idempotency_key + same semantic payload -&gt; return existing job/revision/result.<br/>- Same target with stale expected_head_revision_id/state -&gt; 409/412; do not overwrite mapping, approval or lifecycle state.<br/>- Every accepted mutation -&gt; audit event + outbox/event stream correlation_id.</th>
  </tr>
</table>

# 7. Production Backend and Domain Behavior

## 7.1 Persistent domain model

<table>
  <tr>
    <th>Entity</th>
    <th>Responsibility</th>
    <th>Key identity / integrity rules</th>
  </tr>
  <tr>
    <td>MarketDatasetRoot</td>
    <td>Stable dataset family identity, owner, visibility, root lifecycle, current revision pointer.</td>
    <td>`market_dataset_root_id`; root name is not unique technical identity; `deleted_at` independent from revision approval state.</td>
  </tr>
  <tr>
    <td>MarketDatasetRevision</td>
    <td>Immutable technical truth: metadata, scope, timezone, time basis, schema, coverage, validation snapshot, state.</td>
    <td>`market_dataset_revision_id`; optional `supersedes_revision_id`; Approved content cannot be patched.</td>
  </tr>
  <tr>
    <td>MarketRawAsset</td>
    <td>Immutable original file/stream snapshot.</td>
    <td>`asset_id`, digest, size, content type, source filename, object path not user identity.</td>
  </tr>
  <tr>
    <td>MarketProcessedAsset</td>
    <td>Normalized canonical data product.</td>
    <td>Partitioned Parquet; digest and mapping/schema version pinned in revision manifest.</td>
  </tr>
  <tr>
    <td>MarketSchemaMapping</td>
    <td>Raw-to-canonical mapping proposal and approved mapping version.</td>
    <td>Every essential canonical field mapping explicit; unambiguous transform definition required.</td>
  </tr>
  <tr>
    <td>MarketValidationRun / ValidationIssue</td>
    <td>Validator execution and rule-level findings.</td>
    <td>Rule code, severity PASS/WARNING/BLOCKING_FAIL, sample reference, coverage summary, engine version.</td>
  </tr>
  <tr>
    <td>MarketApprovalDecision</td>
    <td>Admin approval/rejection provenance.</td>
    <td>Admin principal, timestamp, prior state, note/reason, policy context; approval does not alter revision payload.</td>
  </tr>
  <tr>
    <td>MarketDataJob</td>
    <td>Durable upload/profile/validate/process/index job status and retry metadata.</td>
    <td>Job ID/correlation ID supports UI event stream; browser lifetime independent.</td>
  </tr>
  <tr>
    <td>Run / Agent Manifest Reference</td>
    <td>Downstream pin of exact revision and asset context.</td>
    <td>References exact `market_dataset_revision_id`, raw/processed asset digest and coverage slice; never floating latest lookup.</td>
  </tr>
</table>

## 7.2 State model and transitions

Master, Production backendin V18de görünen Needs Review / Verified / Approved etiketlerinden daha ayrıntılı iç state taşımasını ister. Aşağıdaki state model Masterın zorunlu lifecycle ilkelerini somutlaştıran Implementation Decisiondır; V18 UI bunu sade etiketlere projekte edebilir.

<table>
  <tr>
    <th>Layer</th>
    <th>States</th>
    <th>Transition rule</th>
  </tr>
  <tr>
    <td>Draft/intake</td>
    <td>DRAFT, UPLOAD_PENDING, UPLOAD_FINALIZED.</td>
    <td>Draft metadata preflight olmadan parser jobı başlatılmaz. Upload tamamlanmadan raw_asset_id valid değildir.</td>
  </tr>
  <tr>
    <td>Analysis</td>
    <td>ANALYSIS_QUEUED, ANALYSIS_RUNNING, MAPPING_REVIEW_REQUIRED, PROCESSING, VALIDATION_RUNNING.</td>
    <td>Worker state durable jobdan gelir. Browser refresh/close durumu değiştirmez.</td>
  </tr>
  <tr>
    <td>Technical outcome</td>
    <td>NEEDS_REVIEW, REJECTED, VERIFIED.</td>
    <td>Blocking issue varsa NEEDS_REVIEW/REJECTED; zorunlu checks complete ise VERIFIED. Warning may retain VERIFIED only if policy permits and usage constraint stored.</td>
  </tr>
  <tr>
    <td>Approval</td>
    <td>APPROVAL_PENDING, APPROVED, DEPRECATED.</td>
    <td>Only Admin can move VERIFIED -&gt; APPROVED. Approved revision deprecation does not erase historic manifest pins.</td>
  </tr>
  <tr>
    <td>Deletion overlay</td>
    <td>ACTIVE or soft_deleted; later PURGE_REQUESTED/PURGED under strict retention policy.</td>
    <td>Deletion overlay workflow/approval stateinden ayrıdır. Soft-deleted APPROVED revision new selectorsdan çıkar; historical result remains reproducible where assets retained.</td>
  </tr>
</table>

## 7.3 Ingestion and validation worker flow

1. Intake: multipart upload veya controlled connector kaynak asset metadata, hash, size ve source filename ile kaydedilir; bytes immutable object storagea yazılır.

2. Metadata preflight: Dataset Name, Source/Provider, Market, Data Type, Instrument Scope, Resolution, Timezone ve Record Time Basis server tarafında kontrol edilir.

3. Profile: Worker format/encoding/delimiter/columns/sample/timestamp/numeric field olasılıklarını çıkarır; raw asseti değiştirmez.

4. Schema mapping: Data typea göre target schema seçilir. Alias/provider profile mapping önerir; ambiguity varsa review statee geçer.

5. Normalize: Confirmed mapping ile canonical records processed assete, varsayılan instrument + date partition Parquet biçiminde yazılır.

6. Validate: Schema, time, quality, instrument, OHLC/tick/spread execution rules çalışır; rule-level validation issue kayıtları üretilir.

7. Manifest: Raw digest, processed digest, mapping version, coverage, validation report, parser/validator engine version ile immutable revision manifest üretilir.

8. Status/index: Blocking fail -> Needs Review/Rejected; passing required controls -> Verified. Admin approval sonrası consumer index/selector projection güncellenir.

## 7.4 Canonical type-specific schema & validation

<table>
  <tr>
    <th>Data Type</th>
    <th>Minimum canonical fields</th>
    <th>Critical validation</th>
  </tr>
  <tr>
    <td>OHLCV</td>
    <td>timestamp, instrument_id, open, high, low, close, volume.</td>
    <td>Timestamp non-null and timezone-resolvable. OHLC positive; low &lt;= min(open, close); high &gt;= max(open, close). Duplicate instrument+timestamp+resolution reported. Declared cadence gaps recorded. Negative volume blocks; zero volume warning/allowed contextually.</td>
  </tr>
  <tr>
    <td>Tick / Trades</td>
    <td>timestamp, instrument_id, price, size, side.</td>
    <td>Trade ID/sequence available ise duplicate/ordering kontrolü. Unknown side guessed as BUY/SELL olmaz; `UNKNOWN` is preserved and downstream requirement check emits warning/blocker.</td>
  </tr>
  <tr>
    <td>Spread / Execution</td>
    <td>timestamp, instrument_id, bid, ask, spread, execution_cost.</td>
    <td>Ask &lt; bid blocking error. Bid/ask varsa spread = ask - bid consistency. Direct spread unit absolute/bps/% must be declared. Stale quote duration reported; old quote auto-use forbidden.</td>
  </tr>
</table>

## 7.5 Time correctness and execution boundary

<table>
  <tr>
    <th>Known-time rule: Bir barın tamamlanmış close/high/low bilgisi bar kapanmadan biliniyor kabul edilemez. 15m OHLCV yalnız o barın uç değerlerini verir; aynı bar içinde stop ve targeta dokunulduysa hangi olayın önce gerçekleştiğini ispatlamaz. Engine fill priority, conservative assumption veya higher-resolution data requirementini Run manifestine yazar.</th>
  </tr>
</table>

Record Time Basis, timezone ve resolution dataset metadata alanları değil, backtest mantığının çalışma sınırlarıdır. Strategyde “Current Candle Close” kullanımı, close bilgisinin bilindiği an ile order/fill gecikmesini execution policyde açıkça bağlamalıdır. Market Data anti-lookahead kuralı, Research Data için ayrıca gereken event_time/available_time korumasının yerine geçmez.

8. Agent Tool/API Eşdeğeri ve Sürekli Çalışma Modeli

Agent, Market Data UIını tıklamak zorunda değildir. UI button -> API Command -> Domain Service -> Async Job zincirinin aynı domain commandları, Agent Tool Gatewayden policy-aware olarak çağrılabilir. Agentın browser, human session veya visible page state bağımlılığı yoktur.

<table>
  <tr>
    <th>Agent intent</th>
    <th>UI eşdeğeri</th>
    <th>Tool/API eşdeğeri</th>
    <th>Policy/provenance</th>
  </tr>
  <tr>
    <td>dataset.discover</td>
    <td>Registry/table görünümü.</td>
    <td>`search_market_dataset_revisions(filters)`</td>
    <td>Approved eligibility, instrument/resolution/coverage/validation facets ile query. Result includes exact revision IDs.</td>
  </tr>
  <tr>
    <td>dataset.inspect</td>
    <td>Open detail.</td>
    <td>`get_market_dataset_revision_detail(revision_id)`</td>
    <td>Can-view policy; validation/coverage/schema/manifest summarized.</td>
  </tr>
  <tr>
    <td>dataset.intake</td>
    <td>Add dataset + Browse File.</td>
    <td>`create_market_dataset_draft`, `upload_market_raw_asset`, `request_market_dataset_analysis`</td>
    <td>Agent owns its draft/job; source asset and task/checkpoint provenance stored.</td>
  </tr>
  <tr>
    <td>dataset.resolve_mapping</td>
    <td>Analyze preview / review.</td>
    <td>`get_mapping_proposal`, `confirm_market_schema_mapping`</td>
    <td>Agent may resolve only safely mapped fields; ambiguous essential mapping must remain reviewable/audited.</td>
  </tr>
  <tr>
    <td>dataset.create_revision</td>
    <td>Create Dataset.</td>
    <td>`create_market_dataset_revision`</td>
    <td>Exact raw asset, mapping and validation references pinned. No duplicate candidate with same semantic input/idempotency key.</td>
  </tr>
  <tr>
    <td>dataset.request_approval</td>
    <td>Approve button not available to Agent.</td>
    <td>`request_market_dataset_approval` or follow-up task creation.</td>
    <td>Agent cannot grant approval; creates request/artifact for Admin decision.</td>
  </tr>
  <tr>
    <td>dataset.use</td>
    <td>Strategy/Run selectors elsewhere.</td>
    <td>`resolve_approved_market_data_bundle`</td>
    <td>Only ACTIVE + APPROVED revision can feed official candidate/result. Returned bundle carries manifest-ready IDs/digests.</td>
  </tr>
  <tr>
    <td>dataset.raise_quality_followup</td>
    <td>No direct V18 control.</td>
    <td>`create_data_quality_followup_task`</td>
    <td>Result suspicion references validation report/revision; task runs durable queue, not chat/UI memory.</td>
  </tr>
</table>

## 8.1 Agent restrictions

- Agent bir Approved revisionın mappingini, raw assetini, coverageini veya validation özetini in-place değiştiremez; kendi yeni candidate revisionını üretir.

- Agent, Verified veya Needs Review revisionı metadata/quality context olarak okuyabilir; fakat bunlarla resmi Strategy candidate, canonical Backtest Result veya Research Data linki oluşturamaz.

- Agentın approval yetkisi yoktur. Approval bekleme durumunu durable task/artifact olarak kaydeder veya alternatif Approved dataset arar.

- Agent outputları kullandığı `market_dataset_revision_id`, asset digest, coverage slice, validation summary ve task/checkpoint identity ile provenance taşır.

# 9. Validation, Error, Recovery ve Kullanıcı Akışları

## 9.1 Validation matrix

<table>
  <tr>
    <th>Kural kategorisi</th>
    <th>Server-side validation</th>
    <th>UI davranışı</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>Minimum metadata</td>
    <td>Name, source/provider, market, type, instrument scope, resolution, timezone, record time basis, raw asset.</td>
    <td>Required star and inline errors. Analyze/Create disabled reason shown.</td>
    <td>Complete fields; finalize raw upload; retry analysis.</td>
  </tr>
  <tr>
    <td>Instrument identity</td>
    <td>Display text must resolve to canonical instrument registry scope.</td>
    <td>Instrument field can accept text entry but selected/confirmed detail shows resolved identity.</td>
    <td>Correct venue/symbol/contract type or select valid registry instrument.</td>
  </tr>
  <tr>
    <td>Timezone/time basis</td>
    <td>Timestamp must parse with declared timezone and time basis.</td>
    <td>Show parser issue/candidate mapping; no silent UTC fallback for ambiguous dates.</td>
    <td>Choose correct UTC/Exchange/Custom IANA timezone and rerun analysis.</td>
  </tr>
  <tr>
    <td>Schema mapping</td>
    <td>Essential canonical fields must map deterministically.</td>
    <td>Preview highlights unresolved/ambiguous columns. Create remains disabled.</td>
    <td>Confirm mapping or supply data with required fields.</td>
  </tr>
  <tr>
    <td>OHLC/tick/spread quality</td>
    <td>OHLC inequalities, duplicate/gap, volume; tick ordering/side; bid/ask/spread/unit/staleness.</td>
    <td>Quality list and detail report show PASS/WARNING/BLOCKING_FAIL.</td>
    <td>Fix source/mapping/metadata; create successor revision. Never alter raw asset.</td>
  </tr>
  <tr>
    <td>Approval</td>
    <td>Revision must be VERIFIED, active, non-deleted; actor Admin.</td>
    <td>Approve disabled/non-interactive with reason; direct API produces structured 403/422.</td>
    <td>Resolve blockers or request Admin review.</td>
  </tr>
  <tr>
    <td>Use compatibility</td>
    <td>Approval + active state, data type/instrument/resolution/time semantics satisfy caller.</td>
    <td>Selector may hide incompatible revisions; Ready Check reports precise mismatch.</td>
    <td>Select compatible data, adjust execution assumptions, or create suitable revision.</td>
  </tr>
  <tr>
    <td>Stale/concurrency</td>
    <td>Expected draft/revision state must match current server state.</td>
    <td>Conflict banner; no silent overwrite.</td>
    <td>Reload detail; compare changes; reapply on new draft/revision if allowed.</td>
  </tr>
</table>

## 9.2 User and system flows

Flow A - Successful raw source to Approved dataset

1. User opens `+ Add Market Dataset`, provides raw file and all starred identity/time fields. Client validates for usability; server remains source of truth.

2. User selects Analyze Data. Backend accepts idempotent command, records job and returns job ID. UI displays queued/running state; raw file remains immutable.

3. Worker profiles source, proposes mapping, validates time/instrument/quality, writes issue records and returns mapping/validation result.

4. User or authorized Agent confirms unambiguous mapping. Create Dataset creates immutable Market Dataset Revision and processed Parquet asset. Terminal technical state becomes VERIFIED only when required checks pass.

5. Admin opens revision detail, reviews validation/provenance and chooses Approve for Use. Backend records approval decision and exposes revision in selector projection.

6. Strategy, Research Data and Run flows select the exact Approved revision. Future changes create successor revisions; the Approved revision does not mutate.

Flow B - Missing required data before analysis

1. User clicks Analyze Data without dataset name, source, instrument or file.

2. UI highlights missing fields and shows: “Dataset name, source/provider, instrument scope and raw source file are required before analysis.”

3. Server receives no analysis job if client blocks; if direct API called, backend returns 422 with per-field codes. No asset/revision/index side effect is created.

Flow C - Blocking validation failure

1. Analyzer identifies OHLC violation, unparseable timezone or `ask < bid`. Validation Run records `BLOCKING_FAIL` issue with sample reference.

2. Revision remains NEEDS_REVIEW or is REJECTED according to policy; Create/Approve is unavailable. UI shows reason and no primary-data selector exposure.

3. User corrects metadata/mapping or provides corrected raw source, then creates a new candidate revision. Raw source and failed validation history remain auditable.

Flow D - Unauthorized approval

1. User, Supervisor or Agent attempts Approve for Use via UI or direct API.

2. Backend resolves principal/role and rejects before state change with `APPROVAL_REQUIRES_ADMIN`. UI returns role-specific explanation.

3. User may request approval / create follow-up artifact. No client role flag can bypass server policy.

Flow E - Stale draft / duplicate submit

# 1. Two tabs or actors alter mapping/metadata, or user double-clicks Create Dataset.

2. Same semantic idempotency key returns existing in-flight/completed job or revision. Different stale version returns conflict; no duplicate v0.1 or overwrite occurs.

3. UI reloads current state and offers compare/reapply. If a prior revision exists, user creates a successor revision instead of patching it.

Flow F - Soft delete / restore history preservation

1. Authorized actor soft-deletes a Market Dataset Root or Revision. It disappears from active selectors/new Strategy and Research Data choices.

2. Historical Run/Result/Agent manifests retain exact revision ID, asset digest, mapping and validation snapshot. A past result does not lose its data provenance.

3. Only Admin sees the Trash record, can restore same identity or request permanent deletion. Restore must confirm retained assets; missing physical asset means restore fails visibly rather than showing a false active state.

# 10. Lifecycle, Audit, Trash ve Historical Integrity

## 10.1 Revision and delete behavior

<table>
  <tr>
    <th>Event</th>
    <th>Canonical behavior</th>
  </tr>
  <tr>
    <td>New raw file / mapping / coverage / time interpretation / validator effect changes</td>
    <td>Create a new Market Dataset Revision. Link with `supersedes_revision_id` if it replaces a prior revision. Do not update Approved revision fields in place.</td>
  </tr>
  <tr>
    <td>Approved revision selected by a Run</td>
    <td>Run manifest pins exact revision ID, raw/processed digest, mapping version and coverage slice. Later changes or new revisions cannot alter completed result context.</td>
  </tr>
  <tr>
    <td>Soft delete</td>
    <td>Remove root/revision from active catalog and new selector/use projections. Preserve historical revision/manifest provenance and raw/processed assets subject to retention.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>Admin-only. Restore same root/revision identity; do not create a new revision. If revision was APPROVED, it may reappear after policy review; restore is audited.</td>
  </tr>
  <tr>
    <td>Permanent delete/purge</td>
    <td>Admin-only, high-control operation. Must check retention and pinned historical manifest dependencies. Normal UI delete never immediately deletes raw bytes/object assets.</td>
  </tr>
  <tr>
    <td>Deprecate</td>
    <td>Separate from delete. Deprecated revision may remain historical/reproducible but is not default for new selection. Deprecation does not erase prior approval/audit facts.</td>
  </tr>
</table>

## 10.2 Mandatory audit events

<table>
  <tr>
    <th>MARKET_DATASET_DRAFT_CREATED<br/>MARKET_RAW_UPLOAD_STARTED<br/>MARKET_RAW_UPLOAD_FINALIZED<br/>MARKET_ANALYSIS_REQUESTED<br/>MARKET_MAPPING_CONFIRMED<br/>MARKET_VALIDATION_COMPLETED<br/>MARKET_REVISION_CREATED<br/>MARKET_REVISION_APPROVED<br/>MARKET_REVISION_REJECTED<br/>MARKET_REVISION_DEPRECATED<br/>MARKET_DATASET_SOFT_DELETED<br/>MARKET_DATASET_RESTORED<br/>MARKET_DATASET_PURGE_REQUESTED</th>
  </tr>
</table>

Her audit record en az actor principal, target root/revision/asset ID, timestamp, request/correlation ID, previous and next state, relevant manifest/digest reference ve human-readable reason/command metadata taşır. Audit eventı UI toast yerine geçmez; durable system recorddur.

# 11. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Konum</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Analyze Data</td>
    <td>Client checks basic fields, immediately shows canonical schema preview and “Backend check queued”.</td>
    <td>Command enqueues durable profile/mapping/validation worker; all final findings server persistence from.</td>
    <td>Keep quick UX preview only as provisional. Show job ID/state and do not expose final eligibility until server response.</td>
  </tr>
  <tr>
    <td>Create Dataset</td>
    <td>Directly inserts a local `v0.1` / Verified object.</td>
    <td>Creates immutable revision after mapping/validation prerequisites, writes manifest and processed asset.</td>
    <td>No local registry mutation as source of truth. UI rehydrates created revision from response/event.</td>
  </tr>
  <tr>
    <td>Approve for Use</td>
    <td>Button flips current local status to Approved.</td>
    <td>Admin-only command validates Verified/active/non-deleted/no blockers and writes approval decision/audit.</td>
    <td>Use explicit server 403/422/409 paths; no fake approval progress.</td>
  </tr>
  <tr>
    <td>Registry</td>
    <td>Small in-memory `marketDataRegistry` array.</td>
    <td>Role-aware server query over root/current-revision projection; pagination/search/filter extension allowed.</td>
    <td>Do not send unauthorized datasets to browser. Table state is a projection, not database.</td>
  </tr>
  <tr>
    <td>Open detail</td>
    <td>Renders selected local object fields.</td>
    <td>Queries root/revision detail plus validation, assets, manifest/usage and policy-specific actions.</td>
    <td>Detail target is IDs, not array index/name. Current revision change handled explicitly.</td>
  </tr>
  <tr>
    <td>Close Setup</td>
    <td>Resets local workflow state.</td>
    <td>Cannot silently discard server draft, raw asset or running job.</td>
    <td>Show recoverable draft/ongoing-job state; make cancel/discard separate commands if implemented.</td>
  </tr>
  <tr>
    <td>Record Time / Timezone</td>
    <td>Simple dropdown labels.</td>
    <td>Immutable revision metadata that influences known-time/backtest semantics.</td>
    <td>Add Custom IANA timezone resolution and type-aware compatibility guard; preserve V18 visible choices.</td>
  </tr>
</table>

# 12. Implementation Rules for Kodcu AI

1. Market Datayı dosya listesi veya mutable SQL satırı olarak modelleme; Market Dataset Root + immutable Market Dataset Revision + asset/mapping/validation/approval nesnelerini ayır.

2. Backtest, Research Data veya Strategy Data Source seçiminde dataset display name kullanma; exact `market_dataset_revision_id` kullan.

3. Raw source bytesi mapping, cleaning, dedupe veya downsample sırasında asla overwrite etme. Her processed output yeni asset/digest ve gerektiğinde yeni revision üretir.

# 4. OHLCV, Tick/Trades ve Spread/Executionı tek evrensel tabloya zorlamadan versioned canonical schema registry ile uygula.

5. Analyze, validate, process, export ve index updatei HTTP request veya browser memory içinde bitirme; durable queue/worker üzerinden yürüt.

6. Upload, analyze, create revision ve approve commandlarında idempotency key uygula. Aynı semantic input iki ayrı v0.1/revision/job üretmemelidir.

# 7. Approval yalnız Admin olmalıdır. Dataset ownerlığı, validate edebilmek veya Agent olarak çalışmak approval yetkisi vermez.

8. UI star, disabled button veya hidden menu server validation/authorization yerine geçmez. Direct API calls aynı policy/validationdan geçmelidir.

9. Approved revisionın mapping, raw asset, coverage, schema, record-time basis veya validation contextini in-place update etme. Yeni revision yarat ve supersession bağını sakla.

10. Strategy/Run/Agent use pathinde implicit latest/current resolution kullanma. Ready Checkin kabul ettiği exact revision + asset digest + coverage slice manifestte sabitlenmelidir.

# 11. Tick side eksikse BUY/SELL uydurma; `UNKNOWN`u koru ve downstream requirement validationına aktar.

# 12. Bar data ile intrabar execution gerçeği varsayma. Resolution yetersizse blocker/warning ve açık model assumption üret.

13. Soft delete yeni seçimleri engellemeli; historical run/result/agent provenanceını bozmayacak şekilde root/revision/asset referanslarını korumalıdır.

14. Restore ve permanent delete yalnız Admin olmalıdır. Restore missing raw/processed asset durumunda false-active state yaratmamalıdır.

15. Agent aynı domain commandları Tool Gateway üzerinden çağırmalı; Agentın UI sayfasını tıklaması, human session veya browser açık kalması zorunlu olmamalıdır.

16. Every mutating command audit/outbox event ve correlation ID üretmelidir; validation report, approval decision ve lifecycle transitionlar yalnız toastta yaşamamalıdır.

# 13. Acceptance Tests

1. Setup açıldığında V18de görünen tüm input/dropdownlar ve defaultlar render edilir: Crypto, OHLCV, 15m, UTC, Bar Close / End Time; all starred fields visibly required.

2. Raw source file, dataset name, source/provider or instrument scope missingken Analyze command serverda job oluşturmaz ve exact required error döner.

3. Dataset Type = Tick / Trades seçildiğinde canonical preview `timestamp | instrument_id | price | size | side` olur; OHLCV mapping alanları final schema olarak kullanılmaz.

# 4. Dataset Type değiştiğinde old mapping/analysis stale olur, Create disabled olur ve re-analysis warning gösterilir.

# 5. Custom timezone seçildiğinde valid IANA timezone bilgisi olmadan analysis/revision creation 422 ile reddedilir.

6. Same raw asset + same metadata + same mapping + same idempotency key ile Create Dataset iki kez çağrıldığında aynı job/revision referansı döner; duplicate revision oluşmaz.

7. OHLCVde `high < close`, `low > open`, negative volume veya unparseable timezone BLOCKING_FAIL üretir ve revision VERIFIED/APPROVED olamaz.

# 8. Tick dataset side eksik olduğunda canonical field `UNKNOWN` kalır; system BUY/SELL tahmini yazmaz.

# 9. Spread dataset ask < bid içerdiğinde BLOCKING_FAIL oluşur; spread unit belirsizse VERIFIED statee geçemez.

10. Supervisor, User veya Agent `approve_market_dataset_revision` çağırdığında 403 / APPROVAL_REQUIRES_ADMIN döner; audit approval event oluşmaz.

11. Admin, active non-deleted VERIFIED revisionı approve ettiğinde APPROVED state, approval decision, audit event ve selector index update oluşur.

12. Strategy Data Source querysi yalnız ACTIVE + APPROVED + caller policy ile allowed exact Market Dataset Revisionları döndürür; Needs Review ve soft-deleted kayıtlar görünmez.

# 13. Research Data link commandi Approved olmayan Market Dataset Revisiona bağlanmaya çalıştığında blocker ile reddedilir.

14. 15m OHLCV ile intrabar fill-order gerektiren execution use denendiğinde Ready Check compatible-data warning/blocker üretir ve manifestte model assumption olmadan Run başlatılmaz.

15. A completed Backtest Run manifest contains exact market_dataset_revision_id, raw/processed digest, mapping/version and coverage slice; later revision update does not change historic result.

16. Soft-deleted Market Dataset Root active registry/selectorsdan kaybolur, ancak historical result detailde manifest references remain readable.

17. Only Admin can restore or request purge. Restore asset retention failure returns explicit recovery error and does not expose dataset as active.

18. Agent can discover/use Approved revision via Tool Gateway while no browser is open; Agent cannot approve it and records exact revision provenance in its artifact/checkpoint.

19. Current revision changes in another tab while detail is open; subsequent mutation with stale expected_head_revision_id receives conflict and UI prompts reload/compare rather than overwrite.

20. Browser refresh or tab close during analysis does not cancel server job; re-opening page shows durable job/revision status.

# 14. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Canonical authority</td>
    <td>Master Technical Reference v1.0 Modül 4 esas alınmıştır; V18 HTML yalnız görünür UI behavior için kullanılmıştır.</td>
  </tr>
  <tr>
    <td>Market vs Research boundary</td>
    <td>Funding/OI/liquidation/order-book/feature verileri Market Data canonical şemasına eklenmemiş; Research Data sınırı korunmuştur.</td>
  </tr>
  <tr>
    <td>Run/Result distinction</td>
    <td>Market Data yalnız run input manifestini besler. Backtest Run ve Result lifecyclei bu sayfada yeniden tanımlanmamıştır.</td>
  </tr>
  <tr>
    <td>Agent boundary</td>
    <td>Agent browser/UI bağımlılığı olmadan Tool Gateway ile aynı domain capabilitylere erişir; approval yetkisi yoktur.</td>
  </tr>
  <tr>
    <td>Authorization</td>
    <td>UI hidden/disabled state server-side role/ownership/lifecycle policy yerine geçmez; approval/Trash rules ayrı uygulanır.</td>
  </tr>
  <tr>
    <td>Versioning/lifecycle</td>
    <td>Root/revision/asset/mapping/validation/approval ayrımı, immutable Approved revision, soft delete/history preservation ve Admin restore/purge kuralı korunmuştur.</td>
  </tr>
  <tr>
    <td>Future Dev boundary</td>
    <td>No live broker/exchange order, fake live service or Future Dev core entity described as active behavior.</td>
  </tr>
  <tr>
    <td>Scope boundary</td>
    <td>Bu belge yalnız Market Data sayfasını kapsar; Research Data, Strategy, Ready Check, Run/Results, Trash ve Panel kendi sayfa dokümanlarına bırakılmıştır.</td>
  </tr>
</table>
