---
title: "Entropia V18 — Research Data Page Documentation v1.1"
page_number: 12
document_type: "Page implementation specification"
source_document: "Entropia_V18_Research_Data_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Research Data Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | SAYFA DOKÜMANTASYONU 12/22 | RESEARCH DATA
> **Original DOCX footer:** Canonical page documentation | Production V1 alignment |

*ENTROPIA V18*

# RESEARCH DATA

Sayfa Dokümantasyonu 12/22 | Agent ve uyumlu backtestler için native şemalı, time-safe destek veri katmanının UI ve Production V1 sözleşmesi

<table>
  <tr>
    <th>Belge kapsamı: Bu belge yalnız RESEARCH DATA sayfasını kapsar: dataset registry, filtreler, dataset setup formu, analiz/oluşturma/onay akışı, detail card, role policy, revision, approval, data-bundle, validation, audit ve soft-delete etkileri. Market Data, Analysis Lab, Strategy Details, Backtest Ready Check, RUN/Results, Trash ve Panel ayrı sayfa dokümanlarıdır; burada yalnız bu sayfanın doğrudan bağımlılığı olarak anılır.</th>
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
    <td>Entropia V18 | Page Documentation 12/22 | Research Data | v1.1</td>
  </tr>
  <tr>
    <td>Amaç</td>
    <td>V18 Research Data arayüzündeki her görünür bileşeni; Production V1deki Research Dataset Root/Revision, native payload, meaning-and-timing envelope, ingest/validation jobs, approval, Agent Data Bundle, Backtest Evidence Bundle, policy, audit ve recovery sözleşmesine indirmek.</td>
  </tr>
  <tr>
    <td>Ana canonical kaynak</td>
    <td>Master Technical Reference v1.0: Modül 5 Research Data; Modül 15 Research Data’nın Agent ve Backtest ile birleşmesi. Çapraz dayanak: Modül 0, 1, 2, 3, 4, 12, 14, 19 ve 20.</td>
  </tr>
  <tr>
    <td>V18 HTML referansı</td>
    <td>Agent Workspace &gt; Research Data; `showResearchData`, `renderResearchDataPage`, `renderResearchDataCreator`, `renderResearchDataRows`, `renderResearchDataDetail`, `analyzeResearchDataset`, `createResearchDataDataset`, `approveResearchDataDataset`, `filterResearchDataRegistry`.</td>
  </tr>
  <tr>
    <td>Detay seviyesi referansı</td>
    <td>2.3. POSITION ENTRY LOGIC: kavramları ilk geçişte canonical tanımlama; UI, backend, validation, state, Agent parity, lifecycle ve acceptance testleri aynı sözleşmede anlatma standardı.</td>
  </tr>
  <tr>
    <td>Kritik canonical kararlar</td>
    <td>Research Data ana fiyat/execution verisi değildir; native şemasını korur. Her aktif revision exact Approved Market Data revisionına immutable ID ile bağlanır. Event time ve available time ayrı tutulur. Approval / revocation yalnız Admin policy ile yapılır. Agent ve Backtest manifestleri exact revision IDleri pinler.</td>
  </tr>
  <tr>
    <td>Belge içi Implementation Decisions</td>
    <td>V18de görünmeyen IANA timezone alanı, content-type/size validation, optimistic concurrency, explicit job/error/retry surface, root/revision state ayrımı ve info-panel kataloğu Master ilkelerine dayanarak burada kesinleştirilmiştir.</td>
  </tr>
</table>

## 0.1 Source Traceability Map

<table>
  <tr>
    <th>Kaynak / bölüm</th>
    <th>Bu sayfadaki kullanımı</th>
    <th>Kritik sonuç</th>
  </tr>
  <tr>
    <td>Master Modül 5, §1-19</td>
    <td>Research Data tanımı, native schema/envelope, time model, market link, usage scope, lifecycle, approval, pipeline, data model, Agent/backtest tüketimi.</td>
    <td>Data girişinin dosya listesi değil; versioned, time-safe, policy-controlled destek veri hizmeti olması zorunludur.</td>
  </tr>
  <tr>
    <td>Master Modül 15, §1-9</td>
    <td>Source -&gt; bundle -&gt; feature -&gt; decision zinciri, Data Bundle Compiler, available-time join, raw-data prohibition, feature definition, evidence bundle.</td>
    <td>Raw research verisi doğrudan Strategy logic veya trade triggera bağlanamaz; versioned feature/package zinciri gerekir.</td>
  </tr>
  <tr>
    <td>Master Modül 1, §5-8; Modül 3</td>
    <td>Admin/Supervisor/User/Agent yetkileri, UI vs server policy, soft delete, Trash Admin-only.</td>
    <td>Page visibility ve button disable yalnız UXdir; endpoint policy, audit ve Trash kararları server-side uygulanır.</td>
  </tr>
  <tr>
    <td>Master Modül 4; Modül 12; Modül 19</td>
    <td>Approved Market Data dependency, run manifest and validation blockers, API/job/correlation convention.</td>
    <td>Linked market revision ile run primary market revision uyumu, exact revision pinning ve async job davranışı zorunludur.</td>
  </tr>
  <tr>
    <td>V18 HTML</td>
    <td>Görünür labels/defaults, workflow steps, filters, form fields, registry columns, detail grid, inline notes and prototype action order.</td>
    <td>Prototype browser-state davranışı korunabilir; persistence, authorization, approval ve async gerçeklik Mastera göre hizalanır.</td>
  </tr>
  <tr>
    <td>Handoff v1.1</td>
    <td>Field Contract, Interaction State, Content Catalog, command/state contract, lifecycle/audit, implementation rules and acceptance tests.</td>
    <td>Bu belge tüm zorunlu sayfa dokümantasyon başlıklarını içerir; uygulanmayan UI bileşeni açıkça belirtilir.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Sayfa Sınırı

Research Data, Agent araştırmasına ve policy ile uyumlu backtestlere bağlam sağlayan; kendi native veri şemasını koruyan, kaynak anlamını ve gerçek kullanılabilirlik zamanını kaydeden destek veri katmanıdır. OHLCV, tick/trades, bid-ask spread veya execution cost verisi değildir; bunlar Market Data alanında yaşar.

Sayfanın amacı dört işlem yüzeyini tek yerde sunmaktır: kayıtlı revisionları bulmak, yeni bir support-data revision taslağı hazırlamak, analizin zaman/anlam/kalite sonuçlarını görmek ve yetkili aktör için approval durumunu takip etmek.

<table>
  <tr>
    <th>Kapsam sınırı: Bu sayfa Strategy Details içindeki condition veya feature seçim ekranı değildir; Analysis Lab chat yüzeyi değildir; Market Data ingestion ekranı değildir; Backtest Ready Check veya RUN orchestration ekranı değildir. Research Data burada kaydedilir ve yönetilir; Strategy / Backtest tüketimi yalnız versioned feature/package ve manifest zinciri üzerinden gerçekleşir.</th>
  </tr>
</table>

## 1.1 Kavramsal Terimler

<table>
  <tr>
    <th>Terim</th>
    <th>Canonical anlam</th>
    <th>Yanlış yorum / uygulama</th>
  </tr>
  <tr>
    <td>Research Data</td>
    <td>Agent araştırması ve uyumlu backtestler için contextual/derived support input. Native şema korunur.</td>
    <td>OHLCV tablosuna ek kolon veya doğrudan order signal değildir.</td>
  </tr>
  <tr>
    <td>Native payload</td>
    <td>Kategoriye özgü ham/ayrıştırılmış alanlar. Örn. OI, funding, liquidation, order book fields.</td>
    <td>Bütün kategorileri tek canonical price schema içine zorlamak.</td>
  </tr>
  <tr>
    <td>Meaning-and-Timing Envelope</td>
    <td>Her revision için identity, source, category, market link, instrument scope, event/available time, frequency, timezone, usage, validation ve version metadata zarfı.</td>
    <td>Sadece display name veya serbest notla veri anlamı saklamak.</td>
  </tr>
  <tr>
    <td>Event time</td>
    <td>Değerin ait olduğu olayın veya ölçümün gerçekleştiği zaman.</td>
    <td>Decision anında mutlaka biliniyormuş kabul etmek.</td>
  </tr>
  <tr>
    <td>Available time / available_at</td>
    <td>Verinin sistem/strateji tarafından gerçekte kullanılabildiği ilk zaman.</td>
    <td>Event time ile birleştirmek veya boşsa event timeı varsaymak.</td>
  </tr>
  <tr>
    <td>Usage Scope</td>
    <td>Revisionın hangi sistem davranışına girebileceğini belirleyen server-side policy.</td>
    <td>Sadece UIdeki görünürlük filtresi.</td>
  </tr>
  <tr>
    <td>Feature Definition</td>
    <td>Raw Research Data alanını, zaman zincirini koruyarak kullanılabilir versioned featurea dönüştüren tanım.</td>
    <td>Raw open_interest_usd alanını doğrudan condition dropdowna koymak.</td>
  </tr>
  <tr>
    <td>Data Bundle / Evidence Bundle</td>
    <td>Agent veya Backtest için exact dataset revision, mapping, time policy, feature definition ve scope bilgilerini taşıyan immutable bağlam.</td>
    <td>Run sırasında “latest approved” verisini dinamik seçmek.</td>
  </tr>
</table>

# 2. Erişim, Görünürlük, Ownership ve Server-Side Policy

V18de Research Data, Agent Workspace altındadır. Production V1de aynı yetki endpoint, query ve command seviyesinde tekrar değerlendirilir. Bir menünün gizli, bir düğmenin disabled veya bir registry satırının görünür olması tek başına view/use/create/edit/approve/delete yetkisi vermez.

<table>
  <tr>
    <th>Actor</th>
    <th>Page / list / detail</th>
    <th>Create / edit / analyze</th>
    <th>Approve / revoke</th>
    <th>Delete / Trash</th>
    <th>Agent / API sınırı</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Erişemez.</td>
    <td>Erişemez.</td>
    <td>Erişemez.</td>
    <td>Erişemez.</td>
    <td>Human veya Agent identity adına command çalıştıramaz.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Bu sayfaya doğrudan erişemez.</td>
    <td>Bu sayfadan draft oluşturamaz veya yönetemez.</td>
    <td>Erişemez.</td>
    <td>Erişemez.</td>
    <td>Shared/published yüksek-seviye output kullanımı ayrı resource policyye tabidir; page erişimi vermez.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Shared working scope içindeki izinli kayıtları listeler/görüntüler/kullanır. Private personal draftlar otomatik görünmez.</td>
    <td>Kendi dataset draftını oluşturur, günceller, analyze/retry eder ve reviewe sunar; başka ownerın normal revisionını mutate edemez.</td>
    <td>Hayır. Approval için Admin review gerekir.</td>
    <td>Kendi normal objectini soft delete başlatabilir; Trash göremez/restore edemez.</td>
    <td>UI yerine aynı service commands kullanabilir; role context backendden gelir.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm uygun kayıtları listeler/görüntüler/kullanır.</td>
    <td>Her resource üzerinde override ile oluşturma/düzenleme/analyze/retry yapabilir.</td>
    <td>Evet. Shared production approval ve approval revocation Admin policydir.</td>
    <td>Soft delete başlatır; Trashı görüntüler, restore/purge eder.</td>
    <td>Admin UI veya API contexti gerçek principal olarak doğrulanır.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Human login olmadan, service principal ile allowed system working content ve Approved/uyumlu revisionları okur/kullanır.</td>
    <td>Kendi draftını, field-definition taslağını ve feature proposalını oluşturur; yalnız kendi outputunu normal policy ile mutate eder.</td>
    <td>Hayır.</td>
    <td>Kendi outputu için soft delete tetikleyebilir; Trash erişimi yoktur.</td>
    <td>Tool Gateway/API üzerinden çalışır; Analysis Lab veya browser açık kalmak zorunda değildir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Canonical Rule: Approval, approval revocation, Trash listesi, restore ve permanent delete yalnız Admin yetkisindedir. Dataset ownerı olmak approval yetkisi doğurmaz. V18 prototypeın approve düğmesi bu server-side policy yerine geçemez.</th>
  </tr>
</table>

# 3. Arayüz Yerleşimi, Navigasyon ve Görünür Bileşen Envanteri

<table>
  <tr>
    <th>Bölge</th>
    <th>V18 görünümü ve koşulu</th>
    <th>Production sorumluluğu</th>
  </tr>
  <tr>
    <td>Navigation</td>
    <td>Agent Workspace &gt; Research Data. V18de Admin/Supervisor/Agent için görünür; yetkisiz çağrıda “Admin, Supervisor or Agent access required.” mesajı.</td>
    <td>Route guard + resource query policy. UI nav cachei değil server-side principal policy otoritedir.</td>
  </tr>
  <tr>
    <td>Intro card</td>
    <td>Research Dataın native fields, identity, meaning, market link ve timing standardizasyonu açıklanır.</td>
    <td>Read-only orientation content. Değişmez product help metni veya User Manual referansı olabilir.</td>
  </tr>
  <tr>
    <td>Workflow strip</td>
    <td>1 Upload raw source; 2 Define meaning; 3 Set time &amp; market link; 4 Create dataset version; 5 Verify / approve for use.</td>
    <td>Pipelineı görselleştirir; gerçek status worker/job stateinden gelir.</td>
  </tr>
  <tr>
    <td>Registry toolbar</td>
    <td>Search datasets; Category filter; Source filter; + Add Research Dataset / Close Dataset Setup.</td>
    <td>Server-side list query + cursor/pageing, policy filter, canonical defaults and user preference projection.</td>
  </tr>
  <tr>
    <td>Integrity alert</td>
    <td>Approved Market Data yoksa setup düğmesi disabled; link requirement açıklaması gösterilir.</td>
    <td>Dependency failure UI projection. Browser kontrolü yerine approved market revision query sonucu kullanılır.</td>
  </tr>
  <tr>
    <td>Status legend</td>
    <td>Approved, Verified, Needs Review pillleri.</td>
    <td>Revision validation/approval state projection. Job state ile karıştırılmaz.</td>
  </tr>
  <tr>
    <td>Dataset setup shell</td>
    <td>Üç kolon: SOURCE &amp; MEANING; TIME &amp; ALIGNMENT; VALIDATION &amp; USE. Yalnız creator açıkken görünür.</td>
    <td>Editor Draft + upload session + job detail; saved revisionla aynı state değildir.</td>
  </tr>
  <tr>
    <td>Validation preview and quality list</td>
    <td>Envelope preview; category schema/fields, event/available time, coverage/duplicates, field definition satırları.</td>
    <td>Quality report projection; her satır structured check IDs, severity and evidence ile beslenir.</td>
  </tr>
  <tr>
    <td>Registry table</td>
    <td>Dataset, Category, Source, Linked Market Data, Coverage, Frequency, Status, Version, Action / Open.</td>
    <td>Backend query projection; display names exact revision IDs yerine yalnız render alanıdır.</td>
  </tr>
  <tr>
    <td>Detail card</td>
    <td>Meaning, market link, instrument scope, event time, available time rule, native fields, usage scope, validation, ownership &amp; version.</td>
    <td>Root metadata + exact revision metadata + field summary + provenance + lifecycle permissions gösterilir.</td>
  </tr>
</table>

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen</th>
    <th>Default / görünürlük</th>
    <th>Enabled / disabled koşulu</th>
    <th>Loading / success / error / stale davranışı</th>
    <th>Payload / engine etkisi</th>
  </tr>
  <tr>
    <td>Research Data page</td>
    <td>Role policy izinliyse route açılır. Creator kapalıdır.</td>
    <td>Admin/Supervisor/Agent page erişimi. User/Guest blocked.</td>
    <td>List loading skeleton; query error retry; auth denial route message. Stale list cursor refresh edilir.</td>
    <td>Sayfa view stateidir; engine inputu değildir.</td>
  </tr>
  <tr>
    <td>Add Research Dataset</td>
    <td>V18de Approved Market Data varsa enabled; yoksa disabled.</td>
    <td>En az bir ACTIVE + APPROVED Market Data revision görünürse enabled.</td>
    <td>Open editor transient draft yaratır. Close editor V18de local statei sıfırlar; Production unsaved-change confirmation gerekir.</td>
    <td>Tek başına dataset revision üretmez.</td>
  </tr>
  <tr>
    <td>Linked Market Data</td>
    <td>V18de yalnız Approved Market Data display name options.</td>
    <td>Creator only; seçenek server query ile policy/approval/lifecycle filtrelenir.</td>
    <td>Market revision delete/deprecate/stale olursa field blocked and relink required.</td>
    <td>Exact market_dataset_revision_id revision manifestte zorunludur.</td>
  </tr>
  <tr>
    <td>Available Time Rule / Fixed Delay</td>
    <td>Default Fixed delay + “2 minutes”; fixed delay row visible.</td>
    <td>Fixed Delay seçiliyken delay alanı required; diğer rulelarda gizlenir ve revision payloadında delay=null olmalıdır.</td>
    <td>Rule değişince UI stale analysis uyarısı verir; re-analyze required.</td>
    <td>time_policy_version ve resolved available_at hesaplamasını belirler.</td>
  </tr>
  <tr>
    <td>Analyze Data</td>
    <td>V18de required fields + approved market link sağlandığında client action; button görünür.</td>
    <td>Production: upload finalized, metadata complete, expected draft version current, policy allowed.</td>
    <td>queued -&gt; running -&gt; completed / failed / cancelled job states durable; duplicate click idempotent.</td>
    <td>Analysis native schema candidate, time/semantic report and quality checks üretir; revision approval yapmaz.</td>
  </tr>
  <tr>
    <td>Create Dataset</td>
    <td>V18de analyze flag true ise enabled; direct Verified v0.1 creates.</td>
    <td>Production: analysis job succeeded and validation terminal output exists; blocker olmamalı.</td>
    <td>Creates immutable revision; 409 conflict on stale draft; validation issue list retained.</td>
    <td>Root/current revision pointer may be created; exact revision immutable.</td>
  </tr>
  <tr>
    <td>Approve for Research</td>
    <td>V18de current prototype creator state Verified ise enabled.</td>
    <td>Production: only Admin; revision Verified, active linked market revision, no blocker, usage/time policy valid.</td>
    <td>Approval command server transaction; success returns approved projection; forbidden -&gt; ACCESS_DENIED; conflict -&gt; refresh.</td>
    <td>Makes revision eligible only within usage scope; does not update existing Agent/Backtest bundles.</td>
  </tr>
  <tr>
    <td>Registry filters</td>
    <td>Search placeholder; Category/Source defaults All categories/All sources.</td>
    <td>Always enabled if route loaded.</td>
    <td>Debounced server query; empty result exact message; network retry.</td>
    <td>View projection only; does not change dataset/revision state.</td>
  </tr>
  <tr>
    <td>Open detail</td>
    <td>Every registry row has Open.</td>
    <td>Caller must can_view revision.</td>
    <td>Detail fetch may return soft_deleted/permission/stale response; UI refetches list.</td>
    <td>Read projection only; no engine state change.</td>
  </tr>
  <tr>
    <td>Soft delete</td>
    <td>V18 Research Data page has no delete control.</td>
    <td>Production delete appears only when actor can_delete target resource and lifecycle permits.</td>
    <td>Confirmation; soft-delete success removes active list; historical use remains visible; failed command is retryable only if no policy failure.</td>
    <td>No cascade delete; old manifest/result remains immutable. Trash is Admin-only.</td>
  </tr>
</table>

# 5. Fields, Varsayılanlar, Zorunluluk ve Dependency Contract

Bu belgede “*” işareti zorunluluğu ifade eder. Zorunluluk yalnız label değildir: frontend validation, server request validation, validation worker, approval policy, Backtest Ready Check ve Agent Tool schema aynı kuralı taşır.

## 5.1 SOURCE & MEANING alanları

<table>
  <tr>
    <th>Alan / V18 default</th>
    <th>Zorunluluk ve seçenekler</th>
    <th>Production payload / validation / dependent behavior</th>
  </tr>
  <tr>
    <td>Raw source file *<br/>No file selected</td>
    <td>Always required. V18 Browse File opens native input; V18 allowed types are not enumerated.</td>
    <td>raw_asset_upload_id / raw_asset_digest. Allowlist content type + size + malware/file validation are implementation-level hardening; validate file non-empty, hash stable and object storage write succeeded. Immutable raw asset; replacement creates new revision.</td>
  </tr>
  <tr>
    <td>Dataset Name *<br/>empty<br/>Placeholder: e.g. BTCUSDT Open Interest · 5m</td>
    <td>Always required.</td>
    <td>display_name. Trim, reject blank/control chars, normalize whitespace; duplicate display name warning only unless root identity policy declares collision. Must not be used as dependency key.</td>
  </tr>
  <tr>
    <td>Data Category *<br/>Open Interest</td>
    <td>Options: Open Interest; Funding Rate; Liquidations; Order Book; Liquidity / Heatmap; On-chain / Flows; Macro / Calendar; Other / Custom. Always required.</td>
    <td>category_key, category_display_name. Category set is extensible; never closed enum only. Other / Custom activates Custom Category *. Category change after analysis invalidates analysis and requires re-run.</td>
  </tr>
  <tr>
    <td>Custom Category<br/>Optional or required for Other / Custom</td>
    <td>Conditionally required when Data Category = Other / Custom. Otherwise optional precisifier.</td>
    <td>custom_category. Production blocks empty custom value when Other / Custom selected. V18 fallback “Custom Research Data” is prototype-only and must not silently create an underspecified category.</td>
  </tr>
  <tr>
    <td>Source / Provider *<br/>empty<br/>Placeholder: e.g. Binance Futures API</td>
    <td>Always required.</td>
    <td>provider_name + optional provider_registry_ref. Trim; non-empty. Provider display text is not an access credential and not a source identity replacement.</td>
  </tr>
  <tr>
    <td>Field Meaning *<br/>empty<br/>Placeholder: Briefly define what each key field represents and how it was measured.</td>
    <td>Always required.</td>
    <td>meaning_definition_text + field_definition_draft[]. Minimum: field name, semantic meaning, unit/scale when applicable, source measurement/method, null/missing meaning, event time semantics. Parser/human review enriches to searchable field-level metadata; a single paragraph is insufficient as sole canonical backend structure.</td>
  </tr>
</table>

## 5.2 TIME & ALIGNMENT alanları

<table>
  <tr>
    <th>Alan / V18 default</th>
    <th>Zorunluluk ve seçenekler</th>
    <th>Production payload / validation / dependent behavior</th>
  </tr>
  <tr>
    <td>Linked Market Data *<br/>first Approved Market Data option</td>
    <td>Always required. V18 list uses Approved dataset display names; no option when none exists.</td>
    <td>linked_market_dataset_revision_id. Must reference an ACTIVE, APPROVED, policy-visible Market Data revision. Display name must resolve server-side to immutable ID. Change invalidates analysis; requires re-validate/rebuild revision.</td>
  </tr>
  <tr>
    <td>Instrument Scope *<br/>empty<br/>Placeholder: e.g. BTCUSDT Perpetual</td>
    <td>Always required.</td>
    <td>instrument_scope / instrument_mapping_ref. Must map to linked market universe or explicitly document market-wide/provider-defined scope. Unresolvable mapping blocks approval and backtest use.</td>
  </tr>
  <tr>
    <td>Event Time *<br/>Provider event timestamp</td>
    <td>Options: Provider event timestamp; Provider snapshot timestamp; Bar close / end time; Custom documented event time. Always required.</td>
    <td>event_time_semantics. The choice defines source timestamp interpretation; custom mode conditionally requires event_time_specification text in production UI/API. Event time is not a proxy for usable time.</td>
  </tr>
  <tr>
    <td>Available Time Rule *<br/>Fixed delay</td>
    <td>Options: Same as event time; Fixed delay; Provider publish timestamp; Custom documented rule. Always required.</td>
    <td>available_time_policy.type. Must be parseable / deterministic. Rule change invalidates timing validation and any prior analysis.</td>
  </tr>
  <tr>
    <td>Fixed Delay *<br/>2 minutes</td>
    <td>Visible and required only when Available Time Rule = Fixed delay. Hidden otherwise.</td>
    <td>available_time_policy.delay_iso8601 or seconds. Positive, bounded duration. V18 free text “2 minutes” must parse; Production canonical payload uses typed duration. Hidden state sends null; prior delay is not active and must not affect engine.</td>
  </tr>
  <tr>
    <td>Frequency *<br/>5m</td>
    <td>Options: Event Based; 1m; 5m; 15m; 1h; 8h; 1D; Provider Native. Always required.</td>
    <td>frequency_policy. Validate compatibility with source records and linked Market Data alignment. Frequency is not a guarantee that coverage has no gaps.</td>
  </tr>
  <tr>
    <td>Timezone *<br/>UTC</td>
    <td>Options: UTC; Exchange Time; Custom. Always required.</td>
    <td>source_timezone_mode + source_timezone_iana. Custom requires IANA timezone identifier, e.g. America/New_York. Engine normalizes timestamps to UTC while preserving source timezone metadata. Conversion failure blocks approval/run.</td>
  </tr>
</table>

## 5.3 VALIDATION & USE alanları

<table>
  <tr>
    <th>Alan / V18 default</th>
    <th>Zorunluluk ve seçenekler</th>
    <th>Production payload / validation / dependent behavior</th>
  </tr>
  <tr>
    <td>Usage Scope *<br/>Research + Backtest</td>
    <td>Options: Research + Backtest; Agent Research Only; Feature Input Only. Always required.</td>
    <td>usage_scope enum. Policy controls eligibility, not simply visibility. Research + Backtest requires Approved revision for backtest consumption. Agent Research Only is prohibited from Backtest Evidence Bundle, feature input and trade trigger. Feature Input Only requires an approved versioned feature definition before Strategy consumption.</td>
  </tr>
  <tr>
    <td>Standardization / Supporting-data preview</td>
    <td>Read-only. V18 before Analyze: generic envelope explanation; after Analyze: source | category | linked_market_dataset | instrument_scope | event_time | available_time | frequency | timezone | version.</td>
    <td>Projection of draft/revision envelope; not a substitute for immutable revision manifest. Should display resolved IDs on copyable technical view.</td>
  </tr>
  <tr>
    <td>Quality list</td>
    <td>Read-only. V18 rows: Category schema &amp; fields; Event / available time; Coverage / duplicates; Field definition. Initially Pending.</td>
    <td>Structured validation_report with check_id, status, severity, evidence, message, remediation. Needs Review vs Verified derives from report policy; single green badge is insufficient.</td>
  </tr>
  <tr>
    <td>Current status pill<br/>Draft</td>
    <td>Read-only. V18 status may become Verified then Approved.</td>
    <td>Separate revision lifecycle state from job status. Draft / AnalysisQueued / NeedsReview / Verified / Approved are revision projection states; queued/running/succeeded/failed/cancelled are job states.</td>
  </tr>
</table>

6. Information Content Catalog: ⓘ, Helper, Placeholder, Warning, Toast ve Error Metinleri

V18 Research Data ekranında görünür bir ⓘ icon button bulunmaz. Bu nedenle aşağıdaki “info key”ler V18 gözlemi değildir; Production usability alignment için önerilen field-help contractıdır. Metinler doğrudan UI popoverına yerleştirilebilir. Field helper ve warningler ise V18de görünen/önerilen nihai metin olarak ayrılmıştır.

<table>
  <tr>
    <th>Info key / UI alanı</th>
    <th>Panel başlığı</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>researchDataWhatIsInfo<br/>Research Data</td>
    <td>What Research Data Is</td>
    <td>Research Data is supporting context for agent research and eligible backtests. It is not primary price or execution data. Keep the source’s native fields, then record what the data means, which market version it relates to and when it could actually have been used. A Research Data record does not become a trade signal merely because it is registered.</td>
  </tr>
  <tr>
    <td>researchFieldMeaningInfo<br/>Field Meaning *</td>
    <td>Field Meaning</td>
    <td>Describe each key field so a person, an Agent and the backtest pipeline can interpret it consistently. Include the field name, meaning, unit or scale, how the provider measured it and what missing values mean. Do not write only a business label such as “OI”; explain whether it is contracts, USD notional, a snapshot or an aggregated change.</td>
  </tr>
  <tr>
    <td>researchMarketLinkInfo<br/>Linked Market Data *</td>
    <td>Linked Market Data</td>
    <td>Every active Research Data revision must link to one Approved Market Data revision. The link is stored by immutable revision ID, not by displayed name. This allows the system to validate instrument mapping, timeframe compatibility and reproducible backtest manifests.</td>
  </tr>
  <tr>
    <td>researchEventTimeInfo<br/>Event Time *</td>
    <td>Event Time</td>
    <td>Event Time is when the underlying event or measurement occurred. It is not automatically the time at which a strategy could have used the value. Use the provider’s documented timestamp semantics and choose Custom documented event time only when the rule is recorded in the dataset definition.</td>
  </tr>
  <tr>
    <td>researchAvailableTimeInfo<br/>Available Time Rule *</td>
    <td>Available Time</td>
    <td>Available Time is the first moment the value was truly available to the system. Backtests and Agent features may use a record only when available_at is less than or equal to their decision time. A fixed delay must reflect a documented or conservatively justified publication delay. Do not use event time as a shortcut when the provider publishes later.</td>
  </tr>
  <tr>
    <td>researchUsageScopeInfo<br/>Usage Scope *</td>
    <td>Usage Scope</td>
    <td>Usage Scope controls which system behavior may consume this revision. Research + Backtest can enter an eligible Evidence Bundle after approval. Agent Research Only may be used for investigation and context but never for a backtest feature or trade trigger. Feature Input Only requires a separate versioned Feature Definition before Strategy logic can use it.</td>
  </tr>
  <tr>
    <td>researchQualityInfo<br/>Quality report</td>
    <td>Validation Results</td>
    <td>Validation checks the parsed native schema, field definition, time policy, coverage, duplicates, nulls, types, ranges, instrument mapping and semantics. A warning is not silently repaired by the engine. Read the affected check and remediation guidance before approval or run submission.</td>
  </tr>
</table>

## 6.1 Exact helper, empty, warning, toast and error text

<table>
  <tr>
    <th>Durum / UI yeri</th>
    <th>Nihai metin</th>
  </tr>
  <tr>
    <td>V18 page access denied</td>
    <td>Admin, Supervisor or Agent access required.</td>
  </tr>
  <tr>
    <td>Search placeholder</td>
    <td>Search datasets</td>
  </tr>
  <tr>
    <td>Registry empty state</td>
    <td>No registered research dataset matches the current filter.</td>
  </tr>
  <tr>
    <td>Setup disabled title</td>
    <td>Create and approve Market Data before adding Research Data</td>
  </tr>
  <tr>
    <td>Integrity warning</td>
    <td>Research Data setup is waiting for an Approved Market Data version. Create and approve the primary price / execution dataset first; Research Data must always link to an approved market-data version.</td>
  </tr>
  <tr>
    <td>Initial editor note</td>
    <td>Define meaning and timing before the supporting dataset can be created.</td>
  </tr>
  <tr>
    <td>Analyze missing fields error</td>
    <td>Add the raw source file, dataset name, provider, instrument scope and field meaning before analysis.</td>
  </tr>
  <tr>
    <td>Analyze missing market link error</td>
    <td>Link this Research Data version to an Approved Market Data dataset before analysis.</td>
  </tr>
  <tr>
    <td>Analyze missing delay error</td>
    <td>Enter the documented fixed delay before analysis so available time can be validated.</td>
  </tr>
  <tr>
    <td>Analyze success note</td>
    <td>Meaning and timing envelope prepared. Review the native-schema preview, then create a versioned research dataset.</td>
  </tr>
  <tr>
    <td>Create invalid definition error</td>
    <td>A complete definition and an Approved Market Data link are required before the Research Data version can be created.</td>
  </tr>
  <tr>
    <td>Create success note - Production alignment</td>
    <td>Dataset revision created. Validation report is available. Approve for Research is enabled only after all blocking checks pass and an Admin confirms the revision.</td>
  </tr>
  <tr>
    <td>Approve success note</td>
    <td>Approved supporting dataset is now available wherever its market link, usage scope and available-time rule are compatible.</td>
  </tr>
  <tr>
    <td>Approval denied</td>
    <td>Approval requires an Admin role. You can keep this revision for review or submit it to an Admin.</td>
  </tr>
  <tr>
    <td>Stale editor warning</td>
    <td>This dataset changed while you were editing it. Reload the current revision, review the differences and create a new revision from the latest state.</td>
  </tr>
  <tr>
    <td>Job failure</td>
    <td>Dataset analysis did not complete. No Approved revision was created. Review the diagnostic report, correct the source or definition, then retry analysis.</td>
  </tr>
  <tr>
    <td>Soft delete confirmation</td>
    <td>Remove this Research Data root from active use? Historical Agent and Backtest manifests will remain intact. Only an Admin can restore or permanently delete the recoverable record.</td>
  </tr>
</table>

# 7. Buttons, Commands, Preconditions, State ve Audit Contract

<table>
  <tr>
    <th>UI action</th>
    <th>Domain command / query</th>
    <th>Preconditions / disabled</th>
    <th>Loading, success, error, retry</th>
    <th>Audit / state effect</th>
  </tr>
  <tr>
    <td>Search / filters</td>
    <td>GET research-dataset-revisions?search&amp;category&amp;source&amp;cursor</td>
    <td>Route policy; filters are optional.</td>
    <td>Debounced query; server returns items/next cursor. Empty state is not error. Query error shows retry.</td>
    <td>Read audit optional by policy; no revision mutation.</td>
  </tr>
  <tr>
    <td>+ Add Research Dataset</td>
    <td>BeginResearchDatasetDraft (client editor only; server draft optional)</td>
    <td>At least one allowed Approved Market Data revision must be available.</td>
    <td>Open editor; unsaved draft is local or persisted Draft by explicit command. Close asks confirm if dirty.</td>
    <td>No approval/revision creation solely from open.</td>
  </tr>
  <tr>
    <td>Browse File</td>
    <td>CreateUploadSession -&gt; UploadRawResearchAsset</td>
    <td>Create policy; supported file/size policy; upload session valid.</td>
    <td>Upload progress from durable transfer/session state; hash/file metadata after completion. Retry creates/resumes upload session.</td>
    <td>RAW_ASSET_UPLOADED; immutable object storage asset, correlation_id.</td>
  </tr>
  <tr>
    <td>Analyze Data</td>
    <td>RequestResearchDatasetAnalysis</td>
    <td>Draft metadata complete; raw asset finalized; linked market Approved; time policy parseable; expected_draft_version current.</td>
    <td>Returns job_id. UI shows queued/running/completed/failed/cancelled. Retry uses new idempotency key only after terminal failure.</td>
    <td>RESEARCH_ANALYSIS_REQUESTED; worker emits schema/timing/quality events.</td>
  </tr>
  <tr>
    <td>Create Dataset</td>
    <td>CreateResearchDatasetRevision</td>
    <td>Analysis job succeeded; validation report available; no blockers; expected draft revision current.</td>
    <td>Creates revision in Needs Review or Verified based on report. 409 conflict -&gt; reload/compare/retry.</td>
    <td>RESEARCH_DATASET_REVISION_CREATED; root/current pointer audit.</td>
  </tr>
  <tr>
    <td>Approve for Research</td>
    <td>ApproveResearchDatasetRevision</td>
    <td>Admin only; revision Verified; linked Market revision active+approved; no policy blocker; expected_head_revision_id current.</td>
    <td>Short transaction; success returns Approved. 403/409/422 gives recovery guidance.</td>
    <td>RESEARCH_DATASET_APPROVED; approval actor/time/policy version persisted.</td>
  </tr>
  <tr>
    <td>Revoke approval (Production)</td>
    <td>RevokeResearchDatasetApproval</td>
    <td>Admin only; lifecycle allows; dependency impact reviewed.</td>
    <td>Shows impact summary; existing manifests remain pinned.</td>
    <td>RESEARCH_DATASET_APPROVAL_REVOKED; stops new use, does not mutate old runs.</td>
  </tr>
  <tr>
    <td>Open</td>
    <td>GET research-dataset-revisions/{revision_id}</td>
    <td>Caller can_view.</td>
    <td>Detail loader; 404/deleted/permission mismatch refreshes registry.</td>
    <td>Read-only projection; no mutation.</td>
  </tr>
  <tr>
    <td>Edit / create new revision (Production)</td>
    <td>CreateResearchDatasetRevisionFromBase</td>
    <td>Caller can modify eligible root/revision; base revision remains immutable.</td>
    <td>Dirty editor / expected head revision; conflict resolution is reload then create from current base.</td>
    <td>New revision event; old revision preserved.</td>
  </tr>
  <tr>
    <td>Soft delete (Production)</td>
    <td>SoftDeleteResearchDatasetRoot</td>
    <td>can_delete; impact/scope constraints; expected root version current.</td>
    <td>Confirmation; success removes active list. Restore/purge are not on this page for non-Admin.</td>
    <td>RESEARCH_DATASET_SOFT_DELETED + Trash entry. No cascade delete.</td>
  </tr>
</table>

# 8. Production Backend ve Domain Davranışı

## 8.1 Root, Revision, Asset, Job ve Report Modeli

Implementation Decision - Non-Canonical Gap Resolution: Production V1, Masterın immutable revision ilkesiyle uyumlu olarak Research Dataset Root ile Research Dataset Revisionı ayırır. Root, kalıcı identity/lifecycle/owner contextini; revision ise native payload reference, envelope, validation output ve immutable technical truthu taşır.

<table>
  <tr>
    <th>ResearchDatasetRoot<br/>  root_id, owner_principal, visibility, lifecycle_state, current_revision_id, created_at, deleted_at?<br/><br/>ResearchDatasetRevision<br/>  revision_id, root_id, revision_number, base_revision_id?, display_name, category, provider,<br/>  raw_asset_id, parsed_native_asset_id?, native_schema_ref, field_definition_version,<br/>  linked_market_dataset_revision_id, instrument_mapping_ref, event_time_semantics,<br/>  available_time_policy, frequency_policy, source_timezone, usage_scope,<br/>  validation_report_id, validation_state, content_hash, parser_version,<br/>  validation_policy_version, semantic_meaning_version, manifest_hash, created_by, created_at<br/><br/>Supporting records<br/>  RawAsset | ParsedNativeAsset | FieldDefinition | TimePolicy | ValidationReport | IngestionJob | AuditEvent</th>
  </tr>
</table>

Root lifecycle ile revision validation/approval state ayrı değerlendirilir. Bir root ACTIVE olabilirken eski revisionlar historical contextte kalır. Yeni revision oluşturmak, Approved eski revisionı değiştirmez; Backtest Result ve Agent artifactları geçmiş manifestteki exact revisionı kullanmaya devam eder.

## 8.2 Canonical pipeline ve state transition

<table>
  <tr>
    <th>Katman</th>
    <th>State / davranış</th>
    <th>Not</th>
  </tr>
  <tr>
    <td>Editor Draft</td>
    <td>Draft metadata and upload references; not eligible for Agent/Backtest consumption.</td>
    <td>V18 close action local state resetleyebilir; Production saved draft ayrı root/revision oluşturmaz veya explicit draft record olarak saklanır.</td>
  </tr>
  <tr>
    <td>Upload</td>
    <td>Raw asset written to object storage, metadata/digest recorded.</td>
    <td>Raw asset immutable evidence objecttir. Same filename is not identity.</td>
  </tr>
  <tr>
    <td>Analysis / parsing job</td>
    <td>Queued -&gt; Running -&gt; Succeeded / Failed / Cancelled job state.</td>
    <td>Job state revision approval state değildir. Browser refresh/logout jobı iptal etmez.</td>
  </tr>
  <tr>
    <td>Validation outcome</td>
    <td>Needs Review or Verified based on quality report.</td>
    <td>Coverage/null/duplicates/timing/instrument/semantics evidence stored; no silent normalization.</td>
  </tr>
  <tr>
    <td>Approval</td>
    <td>Admin command moves eligible Verified revision to Approved.</td>
    <td>Approved means eligible under usage scope, not “automatically included in every run”.</td>
  </tr>
  <tr>
    <td>Deprecation / approval revoke</td>
    <td>Admin stops new selection/use according to policy.</td>
    <td>Historical Agent/Backtest manifests stay reproducible.</td>
  </tr>
  <tr>
    <td>Soft delete</td>
    <td>Root removed from active discovery/use; Trash record created.</td>
    <td>No cascade to raw asset, historical revision, result, artifact or manifest. Restore/purge is Admin-only.</td>
  </tr>
</table>

## 8.3 Common envelope and field definition

Her revision iki katman taşır: (1) native schema/payload ve (2) common meaning-and-timing envelope. Backend, Field Meaning textarea değerini yalnız raw prose olarak bırakmaz. En azından `field_name`, `semantic_type`, `unit_or_scale`, `measurement_method`, `null_semantics`, `event_time_source`, `availability_rule`, `allowed_usage` alanlarını üretir veya reviewe sunar.

## 8.4 Time model, alignment and lookahead protection

# 1. Kaynak timestampi source timezone ile alınır; engine için UTCye normalize edilir. Source timezone metadata kaybolmaz.

2. Bir decision_time t için yalnız valid instrument mappinge sahip ve available_at <= t olan recordlar adaydır. Event time tek başına eligibility sağlamaz.

3. Default join backward/as-of join olmalıdır: t anından önce/eşit available_at taşıyan en son uygun record seçilir.

4. Aggregation/window varsa başlangıç-bitiş ve transform completion time revision/feature manifestte saklanır. Feature available_at, kaynak inputların en geç available_at değeri ile transform policyyi ihlal etmez.

5. Forward fill yalnız field definition açıkça izin veriyorsa uygulanır. Provider gap, null veya delay otomatik “last value carry forward” gerekçesi değildir.

<table>
  <tr>
    <th>Canonical Rule: Available time yokken event timeı decision time gibi kullanmak yasaktır. Research Data değerini geçmişe sızdırmak, backtest performansını yapay olarak iyileştirir ve Ready Check / validation blocker üretmelidir.</th>
  </tr>
</table>

9. Agent ve Backtest ile UI-Siz Capability Parity

## 9.1 Agent Tool/API eşdeğeri

<table>
  <tr>
    <th>UI görünür işlev</th>
    <th>Agent Tool / Service equivalent</th>
    <th>Policy / provenance sonucu</th>
  </tr>
  <tr>
    <td>Registry search/filter</td>
    <td>search_research_dataset_revisions(filters, policy_context)</td>
    <td>Agent yalnız allowed scope ve visibilitydeki revisions döndürülür; display name ile resolve edilmez.</td>
  </tr>
  <tr>
    <td>Open detail</td>
    <td>get_research_dataset_revision(revision_id)</td>
    <td>Agent native schema summary, envelope, validation and lifecycle data reads; source revision ID checkpoint/artifacta yazılır.</td>
  </tr>
  <tr>
    <td>Create setup draft / upload</td>
    <td>create_research_dataset_draft; create_upload_session; attach_raw_asset</td>
    <td>Agent created output owner=Agent. Human UI/session bağımlılığı yoktur.</td>
  </tr>
  <tr>
    <td>Analyze Data</td>
    <td>request_research_dataset_analysis(draft_id, idempotency_key)</td>
    <td>Worker queue üzerinden yürür; Agent task browser kapanınca etkilenmez.</td>
  </tr>
  <tr>
    <td>Create revision</td>
    <td>create_research_dataset_revision_from_analysis</td>
    <td>Exact revisions and report IDs provenancea yazılır.</td>
  </tr>
  <tr>
    <td>Use for research</td>
    <td>compile_agent_data_bundle(task_id, revision_ids, alignment_policy)</td>
    <td>Agent Data Bundle exact revision IDs, usage scope and time policy pinler. “Latest approved” dynamic resolution forbidden.</td>
  </tr>
  <tr>
    <td>Use for backtest</td>
    <td>compile_backtest_evidence_bundle(run_request, revision_ids, feature_definition_ids)</td>
    <td>Only Approved + eligible usage + mapping/time compatibility revisions. Raw Feature Input Only direct use prohibited.</td>
  </tr>
  <tr>
    <td>Approve / revoke</td>
    <td>No Agent equivalent.</td>
    <td>Approval/revocation Admin-only. Agent can submit or recommend but cannot self-approve shared production data.</td>
  </tr>
</table>

Agentın Analysis Lab ile sohbet etmesi veya Lab ekranının açık olması Research Data tüketiminin koşulu değildir. Lab Assistant yalnız visible interaction adapterdır. Alpha Agent kendi continuous backend runtimeında approved data bundle ile araştırma yürütür; directive yalnız safe checkpointte kuyruktan alınır.

## 9.2 Backtest Evidence Bundle contract

<table>
  <tr>
    <th>BacktestEvidenceBundle<br/>  primary_market_dataset_revision_id<br/>  research_dataset_revision_ids[]<br/>  feature_definition_revision_ids[]<br/>  instrument_mapping_revision_ids[]<br/>  alignment_policy_versions[]<br/>  available_time_policies[]<br/>  missing_and_stale_policies[]<br/>  resolved_at, compiler_version, bundle_hash<br/><br/>Run manifest additionally pins: strategy_revision_id, package_revision_ids[],<br/>execution model, range, fee/spread/slippage, metric set and engine_version.</th>
  </tr>
</table>

Ready Check and Backtest worker must validate the bundle again server-side. The worker must not rely on a dropdown selection or a browser-held registry record. A newly Approved revision does not mutate a running Agent task or Backtest Run; it can be selected only in a newly compiled bundle.

## 9.3 Usage Scope policy matrix

<table>
  <tr>
    <th>Usage Scope</th>
    <th>Agent research</th>
    <th>Feature definition</th>
    <th>Backtest Evidence Bundle</th>
    <th>Direct Strategy / trade trigger</th>
  </tr>
  <tr>
    <td>Research + Backtest</td>
    <td>Allowed after approval and policy/mapping/time compatibility.</td>
    <td>Allowed with versioned definition.</td>
    <td>Allowed after Ready Check validation.</td>
    <td>Never raw; only through compatible feature/package output.</td>
  </tr>
  <tr>
    <td>Agent Research Only</td>
    <td>Allowed for hypotheses, context, quality notes and research artifacts.</td>
    <td>Proposal/draft allowed; approved production feature use is not automatic.</td>
    <td>Forbidden.</td>
    <td>Forbidden.</td>
  </tr>
  <tr>
    <td>Feature Input Only</td>
    <td>Allowed for research and feature development.</td>
    <td>Required path: versioned feature definition.</td>
    <td>Only via approved feature definition and eligible revision.</td>
    <td>Raw direct binding forbidden; feature/package contract required.</td>
  </tr>
</table>

# 10. Validation, Error ve Recovery Contract

<table>
  <tr>
    <th>Kategori</th>
    <th>Server-side rule / suggested code</th>
    <th>UI behavior and recovery</th>
  </tr>
  <tr>
    <td>Field validation</td>
    <td>VALIDATION_FAILED: missing file/name/provider/instrument/meaning/category/time/frequency/timezone/usage.</td>
    <td>Highlight field; preserve typed draft; inline exact message; Analyze/Create blocked until corrected.</td>
  </tr>
  <tr>
    <td>Custom category</td>
    <td>CUSTOM_CATEGORY_REQUIRED when Other / Custom and blank.</td>
    <td>Show “Enter a custom category for Other / Custom.” Do not silently create “Custom Research Data” in Production.</td>
  </tr>
  <tr>
    <td>Market dependency</td>
    <td>DEPENDENCY_BLOCKED: no Approved linked market revision or selected market is inactive/deleted/unavailable.</td>
    <td>Disable creator or link field; show approved Market Data prerequisite; user selects/relinks then re-analyzes.</td>
  </tr>
  <tr>
    <td>Time policy</td>
    <td>TIME_POLICY_INVALID: delay not parseable/positive, custom rule undocumented, timezone conversion invalid, event semantics incomplete.</td>
    <td>Show field-specific error; clear analysis freshness; require re-analysis.</td>
  </tr>
  <tr>
    <td>Schema / content</td>
    <td>NATIVE_SCHEMA_INVALID, FIELD_MEANING_INSUFFICIENT, FILE_PARSE_FAILED, DUPLICATE_EXCESSIVE, COVERAGE_INSUFFICIENT, INSTRUMENT_MAPPING_INVALID.</td>
    <td>Quality report marks blocker/warning, displays evidence and remediation; blockers stop create/approve or bundle use.</td>
  </tr>
  <tr>
    <td>Usage scope</td>
    <td>USAGE_SCOPE_FORBIDDEN: Agent Research Only in backtest or raw Feature Input Only requested as Strategy input.</td>
    <td>Explain correct flow: use research artifact only, or create approved versioned feature definition.</td>
  </tr>
  <tr>
    <td>Approval / auth</td>
    <td>ACCESS_DENIED or APPROVAL_ADMIN_REQUIRED.</td>
    <td>Keep revision unchanged; show approval request/review guidance. UI visibility does not change server decision.</td>
  </tr>
  <tr>
    <td>Lifecycle</td>
    <td>LIFECYCLE_BLOCKED: revision/root deleted, deprecated or not Approved for requested use.</td>
    <td>Refetch current state; choose a valid revision or ask Admin to restore/approve.</td>
  </tr>
  <tr>
    <td>Concurrency</td>
    <td>CONFLICT: expected root/revision/draft version does not match current server version.</td>
    <td>Do not overwrite. Reload current state, compare changes, create a new revision / retry consciously.</td>
  </tr>
  <tr>
    <td>Async job</td>
    <td>JOB_FAILED / JOB_CANCELLED / JOB_RETRY_NOT_ALLOWED.</td>
    <td>Show durable job diagnostic and correlation ID. Retry starts a new job only where safe; failed/cancelled analysis creates no Approved revision.</td>
  </tr>
  <tr>
    <td>Bundle / run</td>
    <td>BUNDLE_COMPILATION_FAILED: mapping/time/scope/feature policy mismatch.</td>
    <td>Block run submission; show exact dataset revision and failure reason; resolve then compile a new bundle.</td>
  </tr>
</table>

## 10.1 Validation decision tree

<table>
  <tr>
    <th>Draft metadata + raw asset<br/>  -&gt; linked Market Data revision Approved and active? no -&gt; DEPENDENCY_BLOCKED<br/>  -&gt; field meaning + event/available-time policy complete? no -&gt; VALIDATION_FAILED / TIME_POLICY_INVALID<br/>  -&gt; analysis job parses native schema and generates quality report<br/>      -&gt; blocker present -&gt; Needs Review / no approval<br/>      -&gt; no blocker -&gt; Verified<br/>          -&gt; Admin approval policy passes -&gt; Approved<br/>              -&gt; eligible usage scope + bundle compatibility -&gt; Agent/Backtest consumption<br/>              -&gt; otherwise -&gt; explicit policy or compatibility blocker</th>
  </tr>
</table>

# 11. Lifecycle, Revision, Audit ve Trash Etkileri

<table>
  <tr>
    <th>Konu</th>
    <th>Canonical behavior</th>
  </tr>
  <tr>
    <td>Revision immutability</td>
    <td>Raw file, parsed native asset, native field list, meaning/field definition, linked Market Data revision, available-time policy, usage scope, mapping or transform manifest change -&gt; new Research Dataset Revision. In-place overwrite forbidden.</td>
  </tr>
  <tr>
    <td>Historical preservation</td>
    <td>Backtest Run, Backtest Result, Agent task/checkpoint and artifact keep exact research_dataset_revision_id(s), feature definition and time policy. A new Approved revision never silently changes prior reproducible context.</td>
  </tr>
  <tr>
    <td>Owner / creator</td>
    <td>created_by, owner and updated_by are separate provenance/policy fields. Admin override does not automatically transfer owner. Agent-created outputs carry agent_run_id/task_id provenance.</td>
  </tr>
  <tr>
    <td>Approval</td>
    <td>Admin approval/revocation is an auditable state transition; owner status does not bypass Admin policy. Approval makes a revision eligible only under its usage scope.</td>
  </tr>
  <tr>
    <td>Soft delete</td>
    <td>Normal delete removes root/current projection from active lists and future selection. Root/revisions are not immediately erased; dependent historical result/artifact remains intact. No cascade delete.</td>
  </tr>
  <tr>
    <td>Trash</td>
    <td>Trash is Admin-only. Supervisor/User/Agent cannot list, restore or permanently delete, even if they own the dataset. Restore preserves root identity and dependency relationships where possible; permanent delete requires final Admin confirmation/re-auth and audit.</td>
  </tr>
  <tr>
    <td>Audit</td>
    <td>Each create, upload, analyze request/start/complete/fail, validation decision, revision creation, approval/revoke, consumption in bundle/run, soft delete, restore and purge emits actor, target root/revision, old/new state, correlation_id and timestamp.</td>
  </tr>
  <tr>
    <td>Stale / concurrency</td>
    <td>Every mutating command sends expected row/revision version. Last-writer-wins is forbidden for meaning/time/usage/link changes. A conflict results in explicit refetch and new revision choice.</td>
  </tr>
</table>

# 12. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Konu</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Research page access</td>
    <td>Menu rendered for Admin/Supervisor/Agent; showResearchData returns an access text for others.</td>
    <td>Route/query/command policy evaluates principal type, role, resource visibility, lifecycle and operation every request.</td>
    <td>Preserve menu UX but never trust `canAccessSystemWorkspace()` client function as authorization.</td>
  </tr>
  <tr>
    <td>Approved Market prerequisite</td>
    <td>Add Research Dataset disabled when no approved market exists; browser checks registry name/status.</td>
    <td>Linked Market Data stores exact immutable Approved Market Dataset Revision ID; backend validates state, mapping and policy.</td>
    <td>Display names remain UI projection only. Update HTML prototype behavior to submit IDs.</td>
  </tr>
  <tr>
    <td>Analyze Data</td>
    <td>Synchronous JavaScript validates a few fields and flips `analyzed=true`; quality line includes “Backend check queued”.</td>
    <td>Analyze is durable parse/validation job. Job state persists across refresh/logout; result includes quality evidence.</td>
    <td>Replace client boolean with job ID/status event stream; no fake completion.</td>
  </tr>
  <tr>
    <td>Create Dataset</td>
    <td>After Analyze, V18 immediately unshifts a v0.1 record with status Verified.</td>
    <td>Create emits immutable revision only after successful analysis/validation report. Result can be Needs Review or Verified.</td>
    <td>V18’s direct Verified result is a demo shortcut; worker policy is canonical.</td>
  </tr>
  <tr>
    <td>Approve for Research</td>
    <td>V18 enables approve after Verified without a visible Admin-only check inside function.</td>
    <td>Only Admin may approve/revoke. Server checks report, linked market state, time policy, usage scope and concurrency.</td>
    <td>Button hidden/disabled for non-Admin; direct endpoint call returns APPROVAL_ADMIN_REQUIRED.</td>
  </tr>
  <tr>
    <td>Time policy</td>
    <td>Fixed delay defaults to text “2 minutes”; Custom timezone has no visible extra input.</td>
    <td>Typed duration and IANA timezone; resolved policy version and available_at derivation saved in immutable manifest.</td>
    <td>Add conditional typed fields in Production; V18 strings are normalized during draft conversion.</td>
  </tr>
  <tr>
    <td>Custom category</td>
    <td>V18 accepts Other / Custom but falls back to “Custom Research Data” if blank.</td>
    <td>Other / Custom requires a custom category value.</td>
    <td>Block underspecified category; avoids unsearchable/ambiguous dataset registry entries.</td>
  </tr>
  <tr>
    <td>Registry filtering</td>
    <td>Client-side filters current in-memory array; options derived from loaded rows.</td>
    <td>Server-side indexed query, authorization filter, pagination/cursor and stable sort.</td>
    <td>Retain visual toolbar; replace direct array filter for production scale.</td>
  </tr>
  <tr>
    <td>Detail card</td>
    <td>Shows string values incl. owner/version/validation.</td>
    <td>Shows root/revision metadata, manifests, quality report, permissions and source dependencies.</td>
    <td>Keep concise card; add technical detail drawer/deep link, not a second data model.</td>
  </tr>
  <tr>
    <td>Delete/Trash</td>
    <td>No Research Data delete action visible in current V18 page.</td>
    <td>Normal delete soft-deletes; Trash/restore/purge Admin-only.</td>
    <td>Do not create client-only removal; use domain command and audit.</td>
  </tr>
</table>

# 13. Kodcu AI İçin Implementation Rules

- Research Datayı Market Data canonical OHLCV tablosuna kopyalama veya tek price schema içine zorlama; native payload + common envelope ayrımını koru.

- Event time ile available timeı tek timestampte birleştirme. Backtest/Agent eligibility için available_at <= decision_time kuralını uygula.

- Dataset dependencylerini display name ile çözme. Linked market, research dataset, mapping, feature and bundle bağlarını immutable revision ID ile sakla.

- V18deki Analyze Data client flagini production readiness kanıtı kabul etme. Parse/validation jobı, durable report and terminal status olmadan revisionı Verified/Approved yapma.

- Approval veya approval revocationı client bodydeki role/status alanına göre kabul etme; Admin server policy + validation report + expected_head_revision_id kontrolü zorunludur.

- Other / Custom category için custom kategori boşken fallback string üretme; server validation ile blokla.

- Fixed delayi serbest metin olarak enginee bırakma; typed durationa normalize et. Custom timezone için IANA timezone id iste ve UTC normalize sonucunu test et.

- Forward fill, missing default, coverage interpolation veya provider delay varsayımını field/feature policy olmadan sessizce uygulama.

- Agent Research Only revisionı Backtest Evidence Bundle, feature input, strategy decision veya trade triggera sokma.

- Feature Input Only raw datasetini doğrudan Strategy Details condition alanına bağlama. Önce versioned Feature Definition, sonra uyumlu Package/Strategy dependency oluştur.

- “Latest approved” referenceını running Agent task veya Backtest Run içinde dinamik çözme. Bundle compile anında exact revisions pinlenir; running job statei immutable kalır.

- Agentı browser/UI button automationına bağlama. Tool Gateway veya aynı domain service commands üzerinden Research Data capabilitylerine eriştir.

- UI filter sonuçlarını access authority sayma. List, detail, use, edit, approve and delete endpointleri ayrı server-side policy guard kullanır.

- Field Meaningi yalnız prose olarak saklama; parse/review sonrası field-level semantic metadata üretebilecek schema kur.

- Mutating commandlerde expected_head_revision_id ve idempotency key kullan. Conflict halinde sessiz overwrite veya duplicate job üretme.

- Raw asset, parsed asset, validation report, time policy, feature definition, bundle and run manifest arasındaki provenance zincirini koparma.

- Soft delete sırasında package, feature, Agent artifact, Backtest Run veya Backtest Result üzerinde cascade delete yapma. Historical reproducibility korunur.

- Trash erişimini owner/delete right ile karıştırma. Restore ve permanent delete yalnız Admin policy ile yapılır.

# 14. Acceptance Tests

<table>
  <tr>
    <th>Test alanı</th>
    <th>Doğrulanabilir senaryo / beklenen sonuç</th>
  </tr>
  <tr>
    <td>UI - prerequisite</td>
    <td>Approved Market Data yokken + Add Research Dataset disableddır; title ve integrity warning görünür; server create draft/analysis commandi linked market dependency olmadığında DEPENDENCY_BLOCKED döner.</td>
  </tr>
  <tr>
    <td>UI - default form</td>
    <td>Creator açıldığında V18 observed defaults: category Open Interest; event time Provider event timestamp; available time Fixed delay; delay 2 minutes; frequency 5m; timezone UTC; usage Research + Backtest; status Draft.</td>
  </tr>
  <tr>
    <td>Requiredness</td>
    <td>Raw file, dataset name, category, provider, field meaning, linked market, instrument scope, event time, available time rule, frequency, timezone and usage missingken Analyze/Create server-side blocklanır; Other / Custom custom categoryyi required yapar.</td>
  </tr>
  <tr>
    <td>Conditional state</td>
    <td>Available Time Rule Fixed delayden başka seçeneğe dönünce Fixed Delay gizlenir, payload delay=null olur, prior analysis stale kabul edilir ve re-analysis gerekir.</td>
  </tr>
  <tr>
    <td>Role policy</td>
    <td>Supervisor own draftını create/analyze/retry eder fakat approve endpointine 403/APPROVAL_ADMIN_REQUIRED alır. Admin same Verified revisionı approve eder. User route/query den access denied alır. Agent service principal UI olmadan own draft/analysis commands kullanır.</td>
  </tr>
  <tr>
    <td>Native schema integrity</td>
    <td>Order Book veya Macro / Calendar categorysi native fieldsini korur; backend bunu OHLCV columnsına dönüştürmez. Field definition contains key semantic metadata.</td>
  </tr>
  <tr>
    <td>Time safety</td>
    <td>10:15 event time, 10:17 available time recordı 10:15 decision_time için as-of joinle seçilmez; 10:17 ve sonrası eligible olur. UTC conversion source timezone metadata ile reproduce edilir.</td>
  </tr>
  <tr>
    <td>Validation report</td>
    <td>Analysis job duplicate/coverage/null/type/range/instrument/semantics checkleri için structured report üretir. Blocker varsa revision Needs Review ve approval disableddır; warning manifestte kaydedilir.</td>
  </tr>
  <tr>
    <td>Revision immutability</td>
    <td>Approved v1.0dan sonra available time veya linked market değiştirilirse v1.0 mutate edilmez; v1.1 draft/analysis/revision yaratılır. Existing run/result v1.0a bağlı kalır.</td>
  </tr>
  <tr>
    <td>Agent scope</td>
    <td>Agent Research Only revision Agent research bundlea girebilir; Backtest Evidence Bundle compile attempt USAGE_SCOPE_FORBIDDEN döner. Feature Input Only raw revision Strategy conditiona doğrudan bağlanamaz.</td>
  </tr>
  <tr>
    <td>Backtest reproducibility</td>
    <td>Evidence Bundle exact research revision IDs, feature definitions, time policies and mapping IDs pinler. New Approved revision running/finished run manifestini değiştirmez.</td>
  </tr>
  <tr>
    <td>Async resilience</td>
    <td>Analyze job sırasında browser refresh/logout olduğunda job durable state ile devam eder; UI tekrar açıldığında same job status/quality report gösterilir. Duplicate Analyze click same idempotency key ile second job yaratmaz.</td>
  </tr>
  <tr>
    <td>Concurrency</td>
    <td>Two actors same draft/revision üzerinde meaning/time policy değiştirirse second stale write CONFLICT alır; first revision korunur, client reload/compare/new revision pathını gösterir.</td>
  </tr>
  <tr>
    <td>Lifecycle / Trash</td>
    <td>Soft deleted root active registryden kaldırılır ve new selection/bundle use blocked olur. Historical manifests remain readable. Non-Admin Trash endpointine erişemez; Admin restore same root identityyi active statee döndürür; permanent delete audit event üretir.</td>
  </tr>
  <tr>
    <td>V18 alignment</td>
    <td>Production implementation client-only registry arrays, client status flip, client role guard veya raw display name dependency kullanmaz; V18 labels and workflow remain visibly aligned.</td>
  </tr>
</table>

# 15. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Master alignment</td>
    <td>Evet - Research Data, native schema + common envelope; exact Market Data revision link; event/available time ayrımı; Admin-only approval; revision/manifest pinning kuralları korunmuştur.</td>
  </tr>
  <tr>
    <td>Prototype separation</td>
    <td>Evet - V18 client-side analyze/create/approve akışı Production durable job, policy ve immutable revision davranışından ayrı açıklanmıştır.</td>
  </tr>
  <tr>
    <td>Agent continuity</td>
    <td>Evet - Agent Tool/API parity, bundle pinning, Lab Assistant ayrımı ve browser/session bağımsızlığı açıkça yazılmıştır.</td>
  </tr>
  <tr>
    <td>Usage scope</td>
    <td>Evet - Agent Research Only ve Feature Input Only için backtest/strategy direct-use yasakları açıkça belirtilmiştir.</td>
  </tr>
  <tr>
    <td>Run / Result integrity</td>
    <td>Evet - Research Data yalnız run/evidence bundle manifestinde exact revision olarak pinlenir; running/finished run yeni revisionla değişmez; Result lifecycle bu sayfada yeniden tanımlanmamıştır.</td>
  </tr>
  <tr>
    <td>Authorization / Trash</td>
    <td>Evet - UI hidden/disabled security kanıtı değildir; approval, restore and permanent delete Admin-only; soft delete historical chainsi bozmaz.</td>
  </tr>
  <tr>
    <td>Future Dev boundary</td>
    <td>Evet - Page behavior active Production V1 Research Data capabilityleriyle sınırlı tutulmuş; Future Dev yetenekleri active gibi anlatılmamıştır.</td>
  </tr>
  <tr>
    <td>Implementation decisions</td>
    <td>Evet - IANA timezone, typed duration, custom category strictness, job/ETag/idempotency and detail expansion kararları canonical olmayan gap resolution olarak ayrıştırılmıştır.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Teslim notu: Bu doküman yalnız Research Data sayfa sözleşmesini tanımlar. Market Data, Analysis Lab, Strategy Details, Backtest Ready Check, RUN/Results, Panel ve Trash için ayrı sayfa dokümanlarının sorumlulukları burada tekrar edilmemiş; yalnız kesin dependency, policy ve lifecycle sınırları işlenmiştir.</th>
  </tr>
</table>
