---
title: "Entropia V18 — RUN ve Backtest Results Page Documentation v1.1"
page_number: 15
document_type: "Page implementation specification"
source_document: "Entropia_V18_RUN_ve_Backtest_Results_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — RUN ve Backtest Results Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18
> **Original DOCX footer:** ENTROPIA V18 | RUN ve Backtest Results | Sayfa Dokümantasyonu 15/22 | Production V1 uygulama sözleşmesi

ENTROPIA V18

RUN ve BACKTEST RESULTS

Sayfa Dokümantasyonu 15/22 | Asenkron Backtest Run kabulü, immutable manifest, terminal lifecycle ve Mainboard içi Result görünümü

<table>
  <tr>
    <th>Kilit canonical karar. Backtest Run ile Backtest Result aynı nesne değildir. RUN yalnız immutable manifestli asenkron iş başlatma niyetidir. Sadece SUCCEEDED durumundaki run, immutable Backtest Result üretir; FAILED veya CANCELLED run normal sonuç, Results History kaydı ya da performans metrik kartı oluşturmaz.</th>
  </tr>
</table>

# 0. Document Control, Scope ve Source Traceability

Bu belge yalnızca Mainboard üzerinde görünen RUN kontrolünü ve RUN sonrasında aynı Mainboard yüzeyinde açılan güncel Backtest Result görünümünü açıklar. Ready Check raporunun ayrıntılı validator UI’si, Results History filtreleme/sıralama ekranı, Arrange Metrics ayar ekranı, Analysis Lab yorum akışı ve Future Dev alanları bu belgenin kapsamı dışındadır.

<table>
  <tr>
    <th>Kaynak / tür</th>
    <th>Bu sayfada kullanılan bölüm</th>
    <th>Kullanım amacı</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0</td>
    <td>Modül 12: Ready Check ve Backtest Run Orchestration; Modül 13: Results, Metrics, History ve Export; Modül 0-3, 9, 11, 19-20 çapraz sınırları.</td>
    <td>Canonical Production V1 domain, lifecycle, manifest, async, authorization, audit ve Result kararları.</td>
  </tr>
  <tr>
    <td>V18 ana HTML</td>
    <td>Mainboard `run-controls`, `runButton`, `resultsSection`, `result-card`, `createBacktestDetailsContent()`, mevcut `selectedMetrics`, detail grafik/tablo/export alanları.</td>
    <td>Kullanıcının gördüğü gerçek prototype layout, label, default ve local click davranışını doğrulamak.</td>
  </tr>
  <tr>
    <td>Handoff v1.1</td>
    <td>22 sayfa sırası, Field/Interaction/Content/Command sözleşmeleri, V18-Production ayrımı, Acceptance Tests.</td>
    <td>Sayfa belgesinin zorunlu anlatım ve kalite standardını uygulamak.</td>
  </tr>
  <tr>
    <td>2.3 Position Entry Logic</td>
    <td>Kavramların ilk kullanımda canonical açıklanması, engine bağlamı, Agent parity, validation ve test derinliği.</td>
    <td>Bu sayfanın teknik açıklama derinliği ve implementasyon dili için referans.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam içi</th>
    <th>Kapsam dışı</th>
  </tr>
  <tr>
    <td>RUN intent, current composition fingerprint, server-side preflight tekrar kontrolü, immutable Composition Snapshot/Run Manifest, queue ve worker statusları; Mainboard current-result satırı, summary metrics, charts, trade ledger summary, export/inspection actions, diagnostics ve soft delete projection.</td>
    <td>Backtest Ready Check validator ayrıntıları; Result History index/sıralaması; Arrange Metrics editing UI; Portfolio allocation form tasarımı; Strategy/Trading Signal/Trade Log konfigürasyon ekranları; AI Review veya Live Trade implementationı.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kavramsal Sınır

RUN yüzeyi, kullanıcının veya Agentın Mainboard Composition için bir backtest çalıştırma niyetini gönderebildiği kontrol katmanıdır. Bu yüzey hesaplama motoru değildir; browserda metric hesaplamaz, kullanıcıdan gelen item listesiyle manifest üretmez ve RUN tıklaması boyunca HTTP bağlantısı üzerinde beklemez. Production V1deki gerçek iş; server-side snapshot, mandatory preflight, immutable manifest, durable job queue, Backtest Worker ve Result materialization zinciridir.

<table>
  <tr>
    <th>Kavram</th>
    <th>Canonical tanım</th>
    <th>Bu sayfadaki uygulama etkisi</th>
  </tr>
  <tr>
    <td>MainboardWorkingItem</td>
    <td>Mainboard üzerinde çalışan canonical work nesnesi. item_kind yalnız `strategy`, `trading_signal` veya `trade_log` olabilir.</td>
    <td>RUN, yalnız aktif ve use-authorized MainboardWorkingItem revisionlarını composition snapshotına alır; bunlar Package Library package kind değildir.</td>
  </tr>
  <tr>
    <td>Backtest Run</td>
    <td>Belirli immutable Run Manifest ile queue/worker üzerinde yürüyen asenkron hesaplama işi.</td>
    <td>RUN tıklaması başarılı olduğunda create edilen nesnedir; QUEUED, PROVISIONING, RUNNING, SUCCEEDED, FAILED veya CANCELLED durumları taşır.</td>
  </tr>
  <tr>
    <td>Backtest Result</td>
    <td>Yalnız succeeded run sonrası materialize edilen immutable final output rootu.</td>
    <td>Mainboarddaki result satırı bu roota giden sunum referansıdır; yeni bir MainboardWorkingItem değildir.</td>
  </tr>
  <tr>
    <td>Run Manifest</td>
    <td>Aynı koşuyu tekrar üretmek için gereken exact revision, execution, time-policy, allocation, engine ve artifact kimliklerinin immutable kaydı.</td>
    <td>Worker current Mainboard state veya “latest” kaynakları okumaz; yalnız manifestte pinlenmiş kimlikleri kullanır.</td>
  </tr>
  <tr>
    <td>Result View Metric Profile</td>
    <td>Result ekranında hangi mevcut metriklerin görüneceğini belirleyen kullanıcı görünüm tercihi.</td>
    <td>Metric Profile engine metrics kapsamını değiştirmez, run kabulü veya Result üretimi için zorunlu input değildir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam sınırı. RUN yalnız geçmiş veri üzerinde deterministik simülasyon başlatır. Live Trade, broker/exchange emri, canlı para riski veya gerçek zamanlı execution session üretmez. Bunlar Future Dev kapsamındadır.</th>
  </tr>
</table>

# 2. Erişim, Görünürlük, Kullanım ve Server-Side Yetki

UIde RUN veya result satırının görünmesi, callerın run başlatma, sonuç okuma, export alma veya result silme yetkisine sahip olduğu anlamına gelmez. Her command ve queryde backend; caller principal, resource visibility, use/edit/delete policy, composition lifecycle, pinned dependency erişimi ve currentness kuralını yeniden değerlendirir.

<table>
  <tr>
    <th>Actor</th>
    <th>RUN ve run status</th>
    <th>Result view / export</th>
    <th>Result soft delete / Trash</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Görmez veya restricted state görür; command gönderemez.</td>
    <td>Private/shared result okuyamaz; export alamaz.</td>
    <td>Yasak.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Own + explicitly shared/published compositionları use policy uygunsa RUN intent gönderebilir.</td>
    <td>Own ve erişim izni olan resultları okuyabilir; export scope policyye bağlıdır.</td>
    <td>Yalnız own result root için normal soft delete; Trash erişemez.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Shared working scope içindeki kullanılabilir compositionlar için RUN intent gönderebilir; başkasının private draftını kullanamaz.</td>
    <td>Erişilebilir resultları okuyabilir ve policy uygunsa export alabilir.</td>
    <td>Yalnız own result root için normal soft delete; Trash erişemez.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm uygun compositionlarda RUN, view, export ve yönetim yetkisi.</td>
    <td>Tüm izinli resultları view/export edebilir.</td>
    <td>Soft delete yapabilir; Trashı görür, restore ve permanent delete yapar.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Human session olmadan trusted service identity ile same domain commandi çağırır.</td>
    <td>Policy kapsamında system working content/result artifactlerini okur; immutable Resultı değiştiremez.</td>
    <td>Yalnız own output için soft delete başlatabilir; Trashı göremez veya restore/purge yapamaz.</td>
  </tr>
</table>

Authorization note: Client body içindeki `role`, `is_ready`, `owner`, `result_id` veya “current result” işaretleri otorite değildir. Server, authenticated human session veya trusted Agent runtime contextinden principalı çözer; invalid/unauthorized istek başlamadan reddedilir.

# 3. V18 Interface Behavior: Gerçek Arayüz Yerleşimi ve Görünür Bileşenler

## 3.1 Mainboard altındaki sabit RUN kontrol grubu

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 görünümü / varsayılan</th>
    <th>Kullanıcı etkileşimi</th>
    <th>Prototype sınırı</th>
  </tr>
  <tr>
    <td>Backtest Ready Check düğmesi</td>
    <td>Mainboard sağ alt köşede, sabit `run-controls` grubunun solunda; metin üç satır: “Backtest / Ready / Check”.</td>
    <td>Ready Check modalını açar. Bu belgenin yalnız RUN için önkoşul ilişkisi açıklanır; validator detaili ayrı Ready Check sayfasındadır.</td>
    <td>Local `backtestReady` booleanı ve `buildBacktestReadyReport()` demo kontrolüdür.</td>
  </tr>
  <tr>
    <td>Ready status şeridi</td>
    <td>Ready Check ile RUN arasında 14px dikey status bar. Varsayılan kırmızı; ready olduğunda yeşil. Tooltip başlangıçta “Backtest Ready: Not Ready”.</td>
    <td>Yalnız görsel durum göstergesi.</td>
    <td>Productionda belirli report_id + fingerprint currentness yansıması olmalıdır; renk tek başına truth source değildir.</td>
  </tr>
  <tr>
    <td>RUN düğmesi</td>
    <td>Sağda 120x66, mavi “RUN” butonu. Başlangıçta `locked` sınıfı ile gri/disabled görünür.</td>
    <td>V18de `addBacktestResult()` çağırır; ready değilse Ready Check çalıştırır; local state bir result kartı ekler.</td>
    <td>Productionda server-side RequestBacktestRun commandine dönüşür; engine browserda çalışmaz.</td>
  </tr>
</table>

## 3.2 Backtest Results bölgesi

V18de `resultsSection` başlangıçta gizlidir. Local RUN demo fonksiyonu çağrıldığında “BACKTEST RESULTS” başlığı ve bir `result-card` görünür. Result row, açık mavi sınır/zemin, metin özeti, aç/kapat oku ve × delete düğmesinden oluşur. Üretilen V18 satır özeti: “BACKTEST RESULT | MAINBOARD ITEMS: n | BTCUSD | 15m | 2020-2025 | Net Profit +84.2% | Max DD -18.1% | Win Rate 54% | Profit Factor 1.72 | ROMAD 4.65”.

<table>
  <tr>
    <th>Result detail bölümü</th>
    <th>V18de görünen içerik</th>
    <th>Production V1 minimum karşılığı</th>
  </tr>
  <tr>
    <td>Summary Metrics</td>
    <td>Seçili metrik kutuları. V18 default: Net Profit, Max Drawdown, ROMAD, Win Rate, Profit Factor, Total Trades, Total Stops, Max Stop Streak, Total Winning Trades.</td>
    <td>`result_id` üzerinden ResultSummary + MetricValue read model. Value, unit, format, formula_version, availability ve null behavior registry üzerinden gelir.</td>
  </tr>
  <tr>
    <td>Equity / Drawdown</td>
    <td>İki dashed placeholder: (1) Price Chart + Entry / Exit / Stop / Scaling Layer Markers, (2) Equity Curve + Drawdown Curve + Exposure / Position Size.</td>
    <td>Immutable curve/marker artifactleri; chart yalnız visual projection. Downsampling sadece display cache; metric/export truth source olamaz.</td>
  </tr>
  <tr>
    <td>Trade List</td>
    <td>Columns: Entry Time, Exit Time, Direction, Entry Price, Exit Price, PnL, Exit Reason. Üç örnek row görünür.</td>
    <td>Cursor-paginated Trade Ledger root rows. One trade root birden fazla fill/scaling leg/partial exit taşıyabilir; UI root summary ve drill-down sağlar.</td>
  </tr>
  <tr>
    <td>Data Export</td>
    <td>Trade Log CSV, Signal Events CSV, Equity Curve CSV, PineScript Signal Marker, Result JSON.</td>
    <td>Export requestleri result artifactten schema-versioned ExportArtifact üretir. Büyük exportlar async ExportJobtır.</td>
  </tr>
  <tr>
    <td>Research Data / Agent Data</td>
    <td>Export Agent Dataset; View Signal Events; View Filtered Events; View Trade Ledger; View Regime Table.</td>
    <td>Artifact query/export. Agent dataset yalnız approved/scope-authorized artifactsden oluşturulur; UI local stateinden türetilmez.</td>
  </tr>
  <tr>
    <td>Diagnostics / AI Review Placeholder</td>
    <td>Diagnostics ve AI Review adlı iki açıklama kartı.</td>
    <td>Diagnostics deterministic result artifactidir. AI Review varsa ayrı immutable/provenanced analysis artifactidir; Result sayısal truth sourceunu değiştiremez.</td>
  </tr>
</table>

<table>
  <tr>
    <th>V18 placeholder sınırı. Diagnostic/AI Review kartı Future Dev veya later analysis capability için yer tutucudur. Production V1 bu kartın varlığına dayanarak otomatik model kararı, gizli Agent taskı veya sahte numeric diagnosis üretmez.</th>
  </tr>
</table>

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen / state</th>
    <th>Görünürlük ve UX</th>
    <th>Payload / engine etkisi</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>RUN - LOCKED / NOT_READY</td>
    <td>RUN gri/locked; status bar kırmızı. Ready Check çağrısı görünür kalır.</td>
    <td>Run command gönderilmez. Browserdaki disabled sınıfı security control değildir.</td>
    <td>Ready Check çalıştır; blockerları ilgili kaynaklarda düzelt; yeni report üret.</td>
  </tr>
  <tr>
    <td>RUN - READY / READY_WITH_WARNINGS</td>
    <td>RUN aktif görünür. Warning sayısı varsa görünür context taşımalıdır.</td>
    <td>RUN intent `expected_fingerprint`, optional report_id, idempotency_key ile gönderilebilir. Warningler manifestte kaydedilir; runı otomatik bloklamaz.</td>
    <td>RUN server preflightı tekrarlar; client ready flagine güvenmez.</td>
  </tr>
  <tr>
    <td>RUN - STALE</td>
    <td>Ready görünümü/raporu current composition fingerprintten farklı. UI RUNı kilitler ve “run again” uyarısı verir.</td>
    <td>Run admission reddedilir; manifest/job oluşmaz.</td>
    <td>Current composition için yeni Ready Check iste.</td>
  </tr>
  <tr>
    <td>BacktestRun - QUEUED / PROVISIONING / RUNNING</td>
    <td>Current result satırı henüz oluşmaz. UI stage message, run id ve reconnectable status sunar.</td>
    <td>Worker yalnız immutable manifest okur. UI refresh/logout runı durdurmaz.</td>
    <td>GET run status + SSE/polling ile yeniden bağlan; job state durable kaynaktan alınır.</td>
  </tr>
  <tr>
    <td>BacktestRun - SUCCEEDED</td>
    <td>Run terminal success. Mainboard result projection oluşur veya yenilenir.</td>
    <td>Transaction ile Result root, summary, metrics, artifact registry ve completion event materialize edilir.</td>
    <td>Result detaili yalnız `result_id`den yeniden hydrate edilir.</td>
  </tr>
  <tr>
    <td>BacktestRun - FAILED / CANCELLED</td>
    <td>Result satırı ve Results History kaydı oluşmaz. Failure/cancel detaili run statusta görünür.</td>
    <td>Error, terminal state, correlation id ve teşhis artifacti saklanabilir; normal Result yaratılmaz.</td>
    <td>Retry command yeni run_id + yeni immutable manifest ile çalışır.</td>
  </tr>
  <tr>
    <td>Result detail - COLLAPSED</td>
    <td>Result row özet metrikleri görünür; heavy artifacts yüklenmez.</td>
    <td>Sadece result summary projection okunur.</td>
    <td>Aç oku ile detail query/pagination başlat.</td>
  </tr>
  <tr>
    <td>Result detail - EXPANDED</td>
    <td>Metrics, charts, ledger, export/inspection actions görünür.</td>
    <td>Current Mainboard form state asla read edilmez; `result_id` pinli artifacts okunur.</td>
    <td>Artifact missing/integrity error varsa error state; local metric fallback yok.</td>
  </tr>
  <tr>
    <td>Result - soft_deleted</td>
    <td>Mainboard current result list ve History projectiondan çıkar.</td>
    <td>Historical run identity, manifest, provenance ve retention-safe artifacts korunur.</td>
    <td>Yalnız Admin Trash üzerinden restore veya permanent delete yapabilir.</td>
  </tr>
</table>

# 5. Field Contract Matrix: Görünür Kontroller ve Implicit Command Girdileri

Bu sayfada klasik form alanı azdır. RUN için asıl doğruluk girdisi browser DOMu değildir; serverdaki current Mainboard Composition Draft, current fingerprint, immutable report ve resolved dependency contextidir. Asterisk (*) ile işaretli field sayısı V18de görünmez; Production command contractında aşağıdaki conditional requiredness uygulanır.

<table>
  <tr>
    <th>Alan / kontrol</th>
    <th>V18 default ve tüm seçenekler</th>
    <th>Zorunluluk / koşul</th>
    <th>Production payload / validation</th>
  </tr>
  <tr>
    <td>RUN</td>
    <td>Locked görünür; Ready Check PASS sonrası active. Tek visible action.</td>
    <td>Conditionally required: current composition READY veya READY_WITH_WARNINGS olmalı ve fingerprint current olmalı.</td>
    <td>Domain command: `RequestBacktestRun`. `composition_id`, `expected_fingerprint*`, `idempotency_key*`; optional `ready_report_id`. Server report currentness + mandatory preflight yapar.</td>
  </tr>
  <tr>
    <td>expected_fingerprint (implicit)</td>
    <td>V18de görünmez.</td>
    <td>Always required for a run intent.</td>
    <td>Current composition fingerprintle eşleşmezse 409 `COMPOSITION_STALE`; client snapshotı kabul edilmez.</td>
  </tr>
  <tr>
    <td>idempotency_key (implicit)</td>
    <td>V18de görünmez.</td>
    <td>Always required for mutating RUN command.</td>
    <td>Same actor + same route + same key mevcut run referansını döndürür; second queue job oluşturmaz.</td>
  </tr>
  <tr>
    <td>ready_report_id (implicit)</td>
    <td>V18de only local modal outputu.</td>
    <td>Optional request field; supplied ise current report fingerprinti doğrulanır.</td>
    <td>Report stale/foreign/inaccessible ise ignore değil reject/recheck behavior uygulanır.</td>
  </tr>
  <tr>
    <td>Result expand arrow</td>
    <td>Default collapsed; “▼”, expanded “▲”.</td>
    <td>No requiredness. `result_id` existing ve view-authorized olmalı.</td>
    <td>Query: ResultSummary + selected metric profile + lazily paginated artifacts. Arrow state only client presentation stateidir.</td>
  </tr>
  <tr>
    <td>Result delete ×</td>
    <td>Expanded/collapsed row sağında. V18 local cardı Trasha taşır.</td>
    <td>Delete policy gerektirir. Soft delete sadece callerın own resultı veya Admin override.</td>
    <td>Command: `SoftDeleteBacktestResult(result_id, expected_row_version, idempotency_key)`. 403 policy denial; 409 stale result version.</td>
  </tr>
  <tr>
    <td>Metric boxes</td>
    <td>V18 selectedMetrics defaults 9 değer. Future metrics array ayrıca tanımlı ancak Result detailde default görünmez.</td>
    <td>No form requiredness. Selected metric profile, only `SELECTABLE` definitions ile oluşturulmuş olmalı.</td>
    <td>Read model uses `MetricDefinition` registry. Missing metric = “Not computed” / “Not available”; never 0 fallback.</td>
  </tr>
  <tr>
    <td>Trade ledger / artifact views</td>
    <td>No filters visible in V18 detail.</td>
    <td>View requires result visibility and retention availability.</td>
    <td>Cursor/page parameters, server-side sorting, artifact checksum verification. Browser state / rounded label sorting forbidden.</td>
  </tr>
  <tr>
    <td>Export buttons</td>
    <td>5 Result export + 5 Research/Agent inspection actions görünür.</td>
    <td>Export type/format scope required by clicked action; source artifact exists.</td>
    <td>Command: `RequestResultExport(result_id, export_type*, format*, filter_spec?, idempotency_key*)`. Large output -&gt; async ExportJob.</td>
  </tr>
</table>

# 6. Information Content Catalog ve Nihai UI Metinleri

V18 RUN düğmesinde, result rowunda, metric kartlarında veya export düğmelerinde ayrı bir ⓘ butonu görünmez. Bu nedenle V18 info button envanteri boştur. Aşağıdaki üç contextual ⓘ paneli, Masterın traceability gereksinimi için Production V1de önerilen Implementation Decisiondır; V18 görünümüne eklenirse bu metin doğrudan UIya yerleştirilecektir.

<table>
  <tr>
    <th>Info key / UI alanı</th>
    <th>Panel başlığı</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>runStatusInfo / RUN status</td>
    <td>Backtest Run Status</td>
    <td>RUN creates an asynchronous Backtest Run from the current server-side Mainboard composition. The browser does not calculate the test and closing this page does not stop the run. A run uses an immutable manifest that pins the strategy, external-item, market-data, research-data, allocation and engine context. Only a succeeded run creates a Backtest Result.</td>
  </tr>
  <tr>
    <td>resultEvidenceInfo / result row</td>
    <td>Result Evidence</td>
    <td>This result is an immutable record of one succeeded run. Its metrics, charts, trade ledger and diagnostics are read from stored result artifacts, not from the current Mainboard form. If the Mainboard changes after this run, the result remains valid for its own manifest but may no longer match the current composition.</td>
  </tr>
  <tr>
    <td>metricProfileInfo / Summary Metrics</td>
    <td>Visible Metrics</td>
    <td>Visible metrics are a reading preference only. Hiding a metric does not stop the engine from calculating it, and showing a metric does not create a value that was not computed for this result. A missing value is shown as Not computed, Not available or No qualifying trades.</td>
  </tr>
</table>

## 6.1 Nihai UI metinleri: placeholder, warning, toast, error ve empty state

<table>
  <tr>
    <th>Durum</th>
    <th>Nihai UI metni</th>
    <th>Kullanım koşulu</th>
  </tr>
  <tr>
    <td>RUN locked helper</td>
    <td>Run is unavailable until the current Mainboard composition passes Backtest Ready Check.</td>
    <td>Current report absent, blocker var veya report STALE.</td>
  </tr>
  <tr>
    <td>RUN queued toast</td>
    <td>Backtest run queued. You can leave this page; the run will continue in the background.</td>
    <td>Server run created + queue handoff accepted.</td>
  </tr>
  <tr>
    <td>RUN running status</td>
    <td>Backtest run is running. Progress is based on worker stages and may be estimated.</td>
    <td>QUEUED, PROVISIONING veya RUNNING.</td>
  </tr>
  <tr>
    <td>RUN success toast</td>
    <td>Backtest completed. A new immutable result is ready to inspect.</td>
    <td>SUCCEEDED + Result materialized.</td>
  </tr>
  <tr>
    <td>RUN failure error</td>
    <td>Backtest did not complete. No Backtest Result was created. Review the run diagnostics and retry with a new run.</td>
    <td>FAILED terminal state.</td>
  </tr>
  <tr>
    <td>RUN cancelled error</td>
    <td>Backtest was cancelled. No Backtest Result was created.</td>
    <td>CANCELLED terminal state.</td>
  </tr>
  <tr>
    <td>Stale error</td>
    <td>The Mainboard changed after readiness was checked. Run Backtest Ready Check again before starting a run.</td>
    <td>409 COMPOSITION_STALE / READY_REPORT_STALE.</td>
  </tr>
  <tr>
    <td>No result empty state</td>
    <td>No succeeded backtest result is available for this Mainboard view yet.</td>
    <td>No accessible/succeeded current result projection.</td>
  </tr>
  <tr>
    <td>Ledger empty state</td>
    <td>No qualifying trades were produced for the selected result.</td>
    <td>Trade ledger has no root trade rows.</td>
  </tr>
  <tr>
    <td>Artifact integrity error</td>
    <td>This result artifact is unavailable or failed integrity verification. The result will not be recalculated in the browser.</td>
    <td>Missing asset/checksum/schema failure.</td>
  </tr>
  <tr>
    <td>Delete confirmation</td>
    <td>Move this Backtest Result to Trash? The original run manifest and historical provenance remain protected.</td>
    <td>Soft-delete action requested.</td>
  </tr>
  <tr>
    <td>Delete success toast</td>
    <td>Backtest Result moved to Trash. Only an Admin can restore or permanently delete it.</td>
    <td>Soft delete accepted.</td>
  </tr>
  <tr>
    <td>Export queued toast</td>
    <td>Export requested. The file will be available when the export job completes.</td>
    <td>Async export created.</td>
  </tr>
</table>

# 7. Buton, Command ve State Sözleşmesi

Aşağıdaki HTTP yolları Implementation Decision olarak önerilir; canonical olan domain command ve server behaviorıdır. Transport katmanı Modül 19 sınırlarında aynı domain commandi farklı route altında sunabilir.

<table>
  <tr>
    <th>UI action</th>
    <th>Domain command / suggested transport</th>
    <th>Precondition ve disabled</th>
    <th>Success / error / audit</th>
  </tr>
  <tr>
    <td>RUN</td>
    <td>`RequestBacktestRun`; `POST /compositions/{composition_id}/backtest-runs`</td>
    <td>Use-authorized composition; expected_fingerprint current; preflight blocker yok; idempotency key present. Disabled: no current Ready report, STALE, ineligible/unauthorized.</td>
    <td>201/202 returns run_id, status=QUEUED, manifest_ref, event_stream_ref. 409 stale; 422 readiness blocked; 403 denied. Audit: RUN_REQUESTED, RUN_QUEUED.</td>
  </tr>
  <tr>
    <td>Observe run</td>
    <td>`GetBacktestRun`; `GET /backtest-runs/{run_id}` + SSE/polling</td>
    <td>Caller may view run. No state mutation.</td>
    <td>Returns durable status/stage/error. Duplicate events de-duplicated by sequence_no. Audit policy may record RUN_VIEWED.</td>
  </tr>
  <tr>
    <td>Expand result</td>
    <td>`GetBacktestResult`; `GET /backtest-results/{result_id}`</td>
    <td>Result exists, succeeded, view-authorized, not unavailable.</td>
    <td>Returns summary/manifest projection and links to artifact endpoints. Error: 404/403/RESULT_INTEGRITY_FAILED. No metric recomputation.</td>
  </tr>
  <tr>
    <td>Open ledger/events/regime</td>
    <td>`QueryResultArtifact`; `GET /backtest-results/{id}/artifacts/{type}`</td>
    <td>Artifact scope view-authorized; cursor/limit valid.</td>
    <td>Server-side pagination/ordering. Error: ARTIFACT_NOT_AVAILABLE, RETENTION_EXPIRED, integrity failure.</td>
  </tr>
  <tr>
    <td>Export</td>
    <td>`RequestResultExport`; `POST /backtest-results/{id}/exports`</td>
    <td>Result view+export policy; export_type/format valid; source artifact available.</td>
    <td>Small exports may be immediate; large exports return export_job_id. Audit: EXPORT_REQUESTED, EXPORT_COMPLETED/FAILED.</td>
  </tr>
  <tr>
    <td>Delete result</td>
    <td>`SoftDeleteBacktestResult`; `DELETE /backtest-results/{id}`</td>
    <td>Owner or Admin; expected_row_version current; result currently active.</td>
    <td>202/200 removes projection; Trash record + audit. 403 denied; 409 stale; retention is not purged.</td>
  </tr>
  <tr>
    <td>Retry failed/cancelled run</td>
    <td>`RetryBacktestRun`; `POST /backtest-runs/{id}/retries`</td>
    <td>Original run terminal FAILED/CANCELLED; caller use-authorized for current dependencies.</td>
    <td>Creates new run_id, new manifest hash, retry_of_run_id link. Original run is immutable and never reset.</td>
  </tr>
</table>

# 8. Kullanıcı ve Sistem Akışları

## 8.1 Flow A - RUN locked: no current readiness

- User Mainboardı açar; RUN düğmesi gri/locked, readiness status kırmızıdır.

- User RUNa tıklarsa V18 Ready Check açabilir. Production UI, RUN commandi göndermez ve helper mesajını gösterir.

- User Backtest Ready Checki çalıştırır. Ready Check report bu belgenin ayrı kapsamındaki validator ekranında oluşur.

- Report current fingerprint için READY veya READY_WITH_WARNINGS ise RUN aktifleşebilir; report yalnız green color değildir.

## 8.2 Flow B - RUN accepted, immutable manifest and background work

- User RUNa basar. Frontend only intent gönderir: composition_id, expected_fingerprint, optional ready_report_id, idempotency_key.

- Backend caller use policyyi doğrular, expected_fingerprinti current composition ile karşılaştırır, report currentnessini kontrol eder ve mandatory server preflightı çalıştırır.

- Server transaction içinde immutable Composition Snapshot, Backtest Run Manifest ve BacktestRun(status=QUEUED) kaydı oluşturur; manifest hash hesaplanır.

- Committen sonra outbox/queue yoluyla yalnız run_id Backtest Worker queueya publish edilir. Browser response engine sonucu beklemez.

- UI run_id/stage message gösterir. Refresh, modal close, browser tab close veya human logout workerı iptal etmez.

## 8.3 Flow C - worker progress, success and current-result projection

- Worker manifestte pinli Market Data, Research Data, Strategy/Package/External Item revisions, allocation snapshot, engine version ve artifact profileı yükler.

- Worker PROVISIONING/RUNNING events yazar. UI SSE/polling bağlantısı koparsa last sequence numberdan tekrar bağlanır veya current state endpointini okur.

- Worker başarıda summary metrics, curve artifacts, Trade Ledger, Signal/Filtered Events ve diagnostics kayıtlarını checksumlarıyla persist eder.

- Result materialization transactionı `BacktestResult` rootunu oluşturur; run=SUCCEEDED olur. UI Mainboard result projectionını current result satırı olarak gösterebilir.

- Result detaili açıldığında only result_idden immutable artifact read modelini yükler; kullanıcı bu sırada Mainboardı değiştirirse geçmiş result değişmez.

## 8.4 Flow D - failure, cancellation and retry

- Worker dependency/asset/engine hatası alırsa run=FAILED ve structured failure cause kaydeder; sonucunda normal Backtest Result yaratılmaz.

- Authorized cancel command varsa worker controlled cancellationa geçer ve terminal CANCELLED state yazar; partial diagnostic artifact mümkünse kalır fakat normal Result yaratılmaz.

- UI current result kartı eklemez; Results History başarılı final Result indexi olduğu için failed/cancelled runı listemez.

- Retry seçilirse backend original runı mutate etmez. Yeni run_id, retry_of_run_id ve yeni immutable manifest oluşturur; eski run audit/provenance için kalır.

## 8.5 Flow E - result inspection, export and deletion

- User result rowundaki oku açar. UI summary metricleri ve lazily loaded curve/ledger/artifact actionsı gösterir.

- User Export Trade Log CSV gibi action seçerse export result artifactten üretilir. Browserda görünen table rows export sourceu değildir.

- User × ile delete isterse UI confirmation gösterir. Server owner/Admin policy, expected_row_version ve retention dependencyyi değerlendirir.

- Soft delete sonrası row active listten kalkar. Admin restore ederse same result root, immutable manifest ve historical provenance yeniden görünür; re-computation yapılmaz.

# 9. Production Backend ve Domain Davranışı

## 9.1 Core object model

<table>
  <tr>
    <th>Nesne</th>
    <th>Mutability / owner</th>
    <th>Bu sayfadaki rol</th>
  </tr>
  <tr>
    <td>MainboardCompositionRoot + current draft</td>
    <td>Mutable root/draft. Composition mutationları explicit row version/fingerprint taşır.</td>
    <td>RUNun server-side snapshot kaynağıdır. Browser row listesi canonical değildir.</td>
  </tr>
  <tr>
    <td>CompositionSnapshot</td>
    <td>Immutable. `snapshot_id`, composition_fingerprint, composition item order ve pinned item revision refs taşır.</td>
    <td>Run manifestin composition evidence katmanı.</td>
  </tr>
  <tr>
    <td>BacktestRun</td>
    <td>Mutable lifecycle root; run state değişebilir ancak manifest content değişmez.</td>
    <td>Queue/worker execution kaydı; terminal status, timestamps, retry relation, failure metadata ve event stream referansı taşır.</td>
  </tr>
  <tr>
    <td>BacktestRunManifest</td>
    <td>Immutable. Hashlenmiş, exact dependencies ve engine contract içerir.</td>
    <td>Workerin tek canonical inputudur. “Latest” lookup veya current UI state fallbacki yasaktır.</td>
  </tr>
  <tr>
    <td>BacktestResult</td>
    <td>Immutable final output root; only succeeded run creates it.</td>
    <td>Mainboarddaki result rowun and detail endpointlerin primary identitysi.</td>
  </tr>
  <tr>
    <td>Result artifact registry</td>
    <td>Immutable artifact metadata + object storage refs/checksum/schema version.</td>
    <td>Curve, ledger, event, diagnostics ve export sources. UI cache veya worker memory değildir.</td>
  </tr>
  <tr>
    <td>ExportJob / ExportArtifact</td>
    <td>Async derivative output.</td>
    <td>Result exports: format/scope/filter/spec + source result manifest hash ile provenance taşır.</td>
  </tr>
</table>

## 9.2 Run Manifest minimum content

<table>
  <tr>
    <th>Manifest alan grubu</th>
    <th>Zorunlu içerik</th>
  </tr>
  <tr>
    <td>Identity / provenance</td>
    <td>run_id, composition_snapshot_id, composition_fingerprint, requested_by principal, created_at, manifest_hash, engine_version, correlation_id.</td>
  </tr>
  <tr>
    <td>Mainboard items</td>
    <td>Each enabled `MainboardWorkingItem`: item_kind, root_id, selected_revision_id, display/provenance metadata, enabled/position order.</td>
  </tr>
  <tr>
    <td>Strategy / package context</td>
    <td>Exact strategy_revision_id; all transitive indicator/condition/embedded system package revision ids; Strategy-local parameter snapshots; resolver revisions.</td>
  </tr>
  <tr>
    <td>External object context</td>
    <td>Trading Signal normalized event/import revision, mapping/timezone/availability/price-source policy; Trade Log canonical ledger/import revision and source validation context.</td>
  </tr>
  <tr>
    <td>Data / time context</td>
    <td>market_dataset_revision_id, research_dataset_revision_ids, coverage, execution resolution, research available_time policies, join/instrument mapping and feature-definition revisions.</td>
  </tr>
  <tr>
    <td>Capital / execution context</td>
    <td>Portfolio Allocation Plan revision/snapshot if enabled; otherwise item initial-capital context; base currency, compounding/reserve, commissions, spread, slippage, order/fill/priority policies.</td>
  </tr>
  <tr>
    <td>Result artifact context</td>
    <td>metric_set_version and output_artifact_profile. This is distinct from user Result View Metric Profile.</td>
  </tr>
</table>

## 9.3 Canonical run state machine and deterministic engine order

<table>
  <tr>
    <th>RequestBacktestRun<br/>  -&gt; QUEUED<br/>  -&gt; PROVISIONING<br/>  -&gt; RUNNING<br/>  -&gt; SUCCEEDED  -&gt; immutable BacktestResult + artifacts<br/>  -&gt; FAILED     -&gt; failure record + diagnostics only, no Result<br/>  -&gt; CANCELLED  -&gt; cancellation record + diagnostics only, no Result<br/><br/>Retry(FAILED | CANCELLED) -&gt; new BacktestRun(run_id != original), retry_of_run_id = original</th>
  </tr>
</table>

Engine simulation order is versioned and deterministic: (1) include only Market/Research data available by the clock time; (2) apply funding/fee/carry; (3) evaluate pending fills; (4) evaluate protection/stop/exit rules; (5) evaluate conflict/exposure/allocation constraints; (6) evaluate entry signals and schedule orders; (7) evaluate same-direction scaling; (8) write state snapshot, decision trace and diagnostic counters. Trading Signal events still pass the selected execution model; Trade Log replay is not Strategy signal generation.

## 9.4 Current-result projection: Implementation Decision

V18 local state permits only one current result card through `backtestResultCreated`. Production V1 must preserve all immutable Result roots. This document selects the following presentation policy: Mainboard Backtest Results shows the most recent accessible succeeded Result associated with the same `composition_id`; after the composition fingerprint changes, the row remains readable but displays a visible “Result snapshot differs from current Mainboard composition” context badge. It is never silently overwritten, deleted or treated as a current test of the modified composition. Full historical indexing remains Results History scope.

# 10. Agent Tool/API Eşdeğeri ve Sürekli Çalışma Sınırı

Agentın RUN kullanımı, human RUN butonuna browser otomasyonu ile basması değildir. Agent, trusted service principal olarak aynı readiness/orchestrator domain servicesini Tool Gateway veya internal API üzerinden çağırır. Agent için daha gevşek preflight, local browser bypassı veya workerı doğrudan invoke eden gizli yol oluşturulmaz.

<table>
  <tr>
    <th>Agent niyeti</th>
    <th>Tool/API eşdeğeri</th>
    <th>Artifact / checkpoint davranışı</th>
  </tr>
  <tr>
    <td>Bir candidateı test et</td>
    <td>`readiness_check.create` + `backtest_run.request`</td>
    <td>Current composition/snapshot fingerprinti, run_id ve manifest hash parent task checkpointine yazılır.</td>
  </tr>
  <tr>
    <td>Readiness blockerı çöz</td>
    <td>`readiness_check.get` + compatible data/package/query tools</td>
    <td>Agent blocker artifacti ve next task oluşturur. Başka ownerın private Strategy/Paketi sessizce mutate edilmez.</td>
  </tr>
  <tr>
    <td>Run sonucu bekle</td>
    <td>`backtest_run.get` / event subscription</td>
    <td>Agent parent taskı tamamen bloklamaz; run_idyi waiting dependency olarak saklar, bağımsız işleri sürdürebilir.</td>
  </tr>
  <tr>
    <td>Resultı incele</td>
    <td>`backtest_result.get`, ledger/events/diagnostics artifact queries</td>
    <td>Agent immutable ResultSummary/MetricValue/TradeLedgeri değiştirmez. Yorumu ayrı analysis artifact/provenance olarak kaydeder.</td>
  </tr>
  <tr>
    <td>Retry oluştur</td>
    <td>`backtest_run.retry`</td>
    <td>Unchanged failed runı resetlemez; policy uygun ise new run + new manifest üretir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Agent boundary. Analysis Labdeki normal discussion mesajı çalışan Backtest Workerı durdurmaz veya run parametrelerini değiştirmez. Yetkili directive veya controlled cancel operasyonu dahi durable queue/lifecycle ve safe checkpoint kurallarıyla yürür.</th>
  </tr>
</table>

# 11. Validation, Error ve Recovery Contract

<table>
  <tr>
    <th>Kod / durum</th>
    <th>Server meaning</th>
    <th>UI ve Agent recovery</th>
  </tr>
  <tr>
    <td>409 COMPOSITION_STALE</td>
    <td>expected_fingerprint current composition fingerprintle eşleşmez.</td>
    <td>RUN locked; server state rehydrate; yeni Ready Check çalıştır.</td>
  </tr>
  <tr>
    <td>409 READY_REPORT_STALE</td>
    <td>Supplied report current composition/dependency fingerprinti için geçerli değil.</td>
    <td>Old report gösterilebilir fakat RUN admission yok; yeni report oluştur.</td>
  </tr>
  <tr>
    <td>422 READINESS_BLOCKED</td>
    <td>Mandatory preflight blocker üretti; run/manifest/job yaratılmadı.</td>
    <td>Issue code/field path/remediation göster; dependencyyi düzelt; recheck.</td>
  </tr>
  <tr>
    <td>403 ACCESS_DENIED / USE_DENIED</td>
    <td>Caller composition veya required dependency için view/use/export/delete yetkisine sahip değil.</td>
    <td>Permission-safe error göster; private object metadata sızdırma. User share/publish/owner workflowuna yönlendirilebilir.</td>
  </tr>
  <tr>
    <td>409 RUN_IDEMPOTENCY_CONFLICT</td>
    <td>Same idempotency key farklı payload/intent ile tekrar kullanıldı.</td>
    <td>Existing runa yönlendir; new key ile explicit yeni intent gönder.</td>
  </tr>
  <tr>
    <td>RUN_FAILED_MANIFEST_RESOLUTION</td>
    <td>Worker manifestte pinli asset/dependencyyi çözemedı; latest fallback yasak.</td>
    <td>Failure detail + artifact. Source restore/revision availability kontrol et; new run request üret.</td>
  </tr>
  <tr>
    <td>RUN_FAILED_ASSET_UNAVAILABLE</td>
    <td>Pinned asset retention/storage erişimi başarısız.</td>
    <td>Diagnose storage/retention; mevcut runa fake result ekleme; remediate sonra new run.</td>
  </tr>
  <tr>
    <td>RESULT_INTEGRITY_FAILED</td>
    <td>Result artifact checksum/schema/metadata integrity doğrulanmadı.</td>
    <td>Detail error görünür; browser recompute veya zero fallback yapmaz; Admin/worker remediation event gerekir.</td>
  </tr>
  <tr>
    <td>EXPORT_FAILED</td>
    <td>Export job source artifact veya format dönüşümünde başarısız.</td>
    <td>Retry export yeni export_job / idempotency context ile; original Resulta etkisi yok.</td>
  </tr>
</table>

Stale/concurrency standard: RUN commandi `expected_fingerprint` taşır; result soft delete gibi root mutationlar `expected_row_version` taşır; HTTP transport `If-Match`/ETag kullanabilir fakat domain fingerprint/row version yerine geçmez. Her mutating action `idempotency_key` ile duplicate submissiondan korunur.

# 12. Lifecycle, Audit, Trash ve Historical Integrity

<table>
  <tr>
    <th>Olay</th>
    <th>Lifecycle etkisi</th>
    <th>Audit / provenance şartı</th>
  </tr>
  <tr>
    <td>RUN request accepted</td>
    <td>BacktestRun QUEUED. Manifest immutable.</td>
    <td>RUN_REQUESTED, RUN_QUEUED, actor, composition snapshot, expected_fingerprint, idempotency/correlation.</td>
  </tr>
  <tr>
    <td>Worker state change</td>
    <td>Run PROVISIONING/RUNNING/terminal.</td>
    <td>RUN_STARTED, RUN_STAGE_CHANGED, RUN_FAILED/CANCELLED/SUCCEEDED; event sequence ve correlation id.</td>
  </tr>
  <tr>
    <td>Result materialized</td>
    <td>Only SUCCEEDED -&gt; BacktestResult immutable root + artifacts.</td>
    <td>RUN_COMPLETED, RESULT_MATERIALIZED, result_id, manifest_hash, artifact checksums.</td>
  </tr>
  <tr>
    <td>Result viewed/exported</td>
    <td>No Result content mutation.</td>
    <td>Optional RESULT_VIEWED; EXPORT_REQUESTED/COMPLETED/FAILED with actor, scope, export manifest.</td>
  </tr>
  <tr>
    <td>Result soft delete</td>
    <td>Active Result projectiondan kalkar; history/current viewden filtrelenir.</td>
    <td>RESULT_SOFT_DELETED + Trash entry snapshot. Source run manifesti ve provenance silinmez.</td>
  </tr>
  <tr>
    <td>Result restore</td>
    <td>Admin-only. Same root/provenance restored to active projection if policy permits.</td>
    <td>RESULT_RESTORED; no recomputation, no new metric calculation.</td>
  </tr>
  <tr>
    <td>Permanent delete</td>
    <td>Admin-only, retention/dependency preflight sonrası recoverable result root purge.</td>
    <td>RESULT_PURGED, re-authentication/control audit. Historical run identity and audit policy retain required minimal evidence.</td>
  </tr>
</table>

Historical integrity rule: Strategy, Package, Market Data, Research Data veya allocation planı sonraki tarihte soft-deleted/deprecated olsa bile geçmiş BacktestRun Manifest ve Resultın meaningi değişmez. Normal active selection listeleri bu kaynakları gizleyebilir; historical result detaili manifestteki pinned revision metadata üzerinden okunabilir kalmalıdır.

# 13. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Konu</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>RUN trigger</td>
    <td>`addBacktestResult()` local demo functionı resultsSectiona one card ekler.</td>
    <td>RequestBacktestRun server command -&gt; snapshot + manifest + queue worker.</td>
    <td>V18 click hedefi korunur; local result creation kaldırılır, durable run status projection eklenir.</td>
  </tr>
  <tr>
    <td>Readiness</td>
    <td>Local `backtestReady` boolean ve modal text.</td>
    <td>Immutable ReadinessReport + current composition fingerprint + mandatory RUN preflight.</td>
    <td>Color/lock UX korunur; server currentness canonical olur.</td>
  </tr>
  <tr>
    <td>One result card</td>
    <td>`backtestResultCreated` only one card local flag.</td>
    <td>All succeeded runs have immutable Result roots.</td>
    <td>Mainboard latest-current-result projection shows one latest matching row; old results preserved and mismatch clearly labeled.</td>
  </tr>
  <tr>
    <td>Metrics</td>
    <td>Hard-coded `metricValues` object and selectedMetrics local array.</td>
    <td>MetricDefinition registry + ResultSummary/MetricValue artifacts.</td>
    <td>Default labels preserved; value source switches to result_id read model; no frontend formula.</td>
  </tr>
  <tr>
    <td>Charts</td>
    <td>Placeholder text boxes.</td>
    <td>Immutable curve/marker artifact-backed chart endpoints.</td>
    <td>Placeholder may remain until chart renderer exists; no fake chart/price data.</td>
  </tr>
  <tr>
    <td>Trade table</td>
    <td>Three hard-coded sample rows.</td>
    <td>Cursor-paginated Trade Ledger root rows, drill-down to fills/legs.</td>
    <td>Column labels preserved; sample data removed outside prototype/demo mode.</td>
  </tr>
  <tr>
    <td>Export buttons</td>
    <td>Buttons lack durable backend handlers.</td>
    <td>Result artifact export commands/jobs + manifest/provenance.</td>
    <td>Each visible button mapped to export_type or artifact query; async status UI added.</td>
  </tr>
  <tr>
    <td>Delete ×</td>
    <td>Local DOM removal + local Trash array, result section hidden.</td>
    <td>Soft delete Result root under policy; Admin-only Trash restore/purge.</td>
    <td>No client-only deletion. Result card removed only after server success; historical Run manifest remains.</td>
  </tr>
  <tr>
    <td>Diagnostics / AI Review</td>
    <td>Text placeholder.</td>
    <td>Diagnostics = deterministic artifact; AI Review = separate analysis artifact if capability is enabled.</td>
    <td>Do not implement active AI task or automatic verdict until capability is explicitly activated.</td>
  </tr>
</table>

# 14. Kavramsal Terimler

<table>
  <tr>
    <th>Terim</th>
    <th>Canonical kısa anlam</th>
  </tr>
  <tr>
    <td>Run Intent</td>
    <td>User veya Agentın run başlatma talebi. Tek başına sonuç veya manifest değildir.</td>
  </tr>
  <tr>
    <td>Composition Fingerprint</td>
    <td>Current Mainboard Compositionın engine-relevant stateini temsil eden deterministic hash/fingerprint. Readiness currentnessinin anahtarıdır.</td>
  </tr>
  <tr>
    <td>Immutable Manifest</td>
    <td>Exact pinned dependencies, time policies, execution/capital context ve engine versionı taşıyan, run sonrası değiştirilemeyen kanıt kaydı.</td>
  </tr>
  <tr>
    <td>Result Materialization</td>
    <td>Succeeded worker outputlarının BacktestResult root, metric summary ve immutable artifact registry olarak transactionla kaydedilmesi.</td>
  </tr>
  <tr>
    <td>Trade Root</td>
    <td>Bir position lifecycleini temsil eden ledger üst kaydı. Birden fazla fill, scale leg veya partial exit içerebilir; metric count bu ayrımı korur.</td>
  </tr>
  <tr>
    <td>Signal Event</td>
    <td>Signal/condition/filtered/no-entry gibi strategy karar izini taşıyan gözlemlenebilir event. Gerçek fill ile eş anlamlı değildir.</td>
  </tr>
  <tr>
    <td>Output Artifact Profile</td>
    <td>Runın materialize etmesi gereken result artifact sınıflarını belirleyen execution/output planı. Result View Metric Profiledan ayrıdır.</td>
  </tr>
</table>

# 15. Kodcu AI için Implementation Rules

- RUN düğmesini frontendde Backtest Result oluşturan bir fonksiyon olarak implement etme. UI yalnız RequestBacktestRun intentini gönderir; result only worker success sonrası materialize edilir.

- RUN endpointinde client `ready=true`, client item listesi, modal texti veya local `backtestReady` değerini canonical kabul etme. Current server compositiondan snapshot al ve mandatory preflightı tekrar çalıştır.

- BacktestRun ve BacktestResult için ayrı root/lifecycle modelleri kullan. FAILED veya CANCELLED BacktestRun normal Result, metric summary, current result row veya Results History recordu üretmez.

- Run manifestini exact revision ids ve content/dependency hashes ile oluştur. Worker current Mainboard, Package Library veya latest dataset tablosuna fallback yapamaz.

- Expected concurrency değerlerini karıştırma: RUN için expected_fingerprint; root mutation için expected_row_version; transportta If-Match/ETag; duplicate request kontrolü için idempotency_key kullan.

- Aynı idempotency key ile gelen duplicate RUN isteğinde ikinci job yaratma. Existing run referansını döndür. Retry, original runı resetlemez; new run_id + new manifest hash oluşturur.

- Progressi fake JavaScript timer veya kesin yüzde ile üretme. Durable run state, stage event ve sequence number kullan; reconnectte missed events veya current status yükle.

- Mainboard Result rowunu MainboardWorkingItem olarak persist etme. Bu row BacktestResult rootuna giden read-only view referenceidir.

- Result detailini current Mainboard form stateinden hesaplama veya güncelleme. Only result_id ve immutable result artifacts üzerinden hydrate et.

- Metric formulalarını frontend componentlerine koyma. MetricDefinition registry, formula_version, unit, formatting ve null behavior server result layerda çalışır.

- Result View Metric Profileı run config veya engine metric scope ile karıştırma. Profile yalnız görünüm tercihi; output artifact profile ve metric_set_version ayrı kavramlardır.

- Trade Ledgerı browsera tek seferde yükleme. Cursor pagination, server-side ordering ve root/leg drill-down kullan.

- Exportu rendered table/DOMdan oluşturma. Immutable source artifact, schema_version, filter_spec, source manifest hash ve ExportArtifact provenance kullan.

- Diagnostics ve AI Reviewu sayıların truth sourceu olarak kullanma. Diagnostics deterministic artifact; Agent yorumu ayrı provenance taşıyan analysis artifactidir.

- Result deletei DOMdan kaldırmakla sınırlama. Server-side policy, expected_row_version, soft delete, Trash record ve audit zorunludur. Restore/purge only Admin.

- Agent için UI click emülasyonu, looser preflight veya direct worker bypassı oluşturma. Tool Gateway aynı Readiness Service, Manifest Builder ve Orchestratora bağlanmalıdır.

- Future Dev AI Review veya Live Trade placeholderlarını gerçek transaction, broker order veya autonomous verdict mekanizması gibi implement etme.

# 16. Acceptance Tests

- Current Ready report yokken RUN görsel olarak locked kalır; direct API RUN isteği de server tarafında READY/preflight kontrolünden geçer.

- Ready compositionda RUN intent correct expected_fingerprint + idempotency_key ile çağrıldığında BacktestRun QUEUED oluşur, manifest hash döner ve UI engine sonucu beklemez.

- RUN requesti sırasında başka tab current compositionı değiştirdiğinde 409 COMPOSITION_STALE döner; manifest/job yaratılmaz.

- RUN endpointi browser item listesi değil server-side transactionally consistent composition snapshot kullanır.

- Same actor/route/idempotency_key ile duplicate RUN isteği same run_id döndürür; only one queue job yayınlanır.

- Workerin UI refresh, logout, modal close veya SSE disconnect sonrasında çalışmaya devam ettiği doğrulanır.

- Worker current Mainboard/Package Library yerine only manifest pinned dependencies kullanır; missing pinned assette latest fallback yerine failed terminal state üretir.

- SUCCEEDED run summary metrics, artifact checksums ve BacktestResult rootu oluşturur; Mainboard result projection result_id ile açılır.

- FAILED run no BacktestResult, no current result card and no Results History index entry üretir; failure diagnostics erişilebilir kalır.

- CANCELLED run no BacktestResult üretir; cancellation audit event ve terminal reason korunur.

- Retry failed/cancelled run original runı mutate etmeden new run_id, retry_of_run_id ve new manifest oluşturur.

- Result detaili açıldığında current Mainboard form değişiklikleri metric/chart/ledger değeri değiştirmez.

- Default V18 metric listesi ilk result detailinde doğru sırada görünür; hidden metric engine metric calculationını etkilemez.

- Unavailable metric 0 yerine “Not available”, “Not computed” veya “No qualifying trades” davranışı gösterir.

- Price/equity/drawdown chart projectionları immutable curve/marker artifactlerden okur; visual downsampling metric/export sourceu değildir.

- Trade ledger large resultlerde cursor pagination kullanır; UI root trade satırını fill/scale leglerden çift saymaz.

- Signal Events ve Filtered Events gerçek fill ile aynı yapı olarak zorla birleştirilmez; no-entry/filtered decision trace okunabilir.

- Each V18 export action correct export_type/format commandine bağlanır; export sourceu Result artifacttir ve export manifest source manifest hash taşır.

- Delete × action unauthorized actor için 403 döner; owner/Admin soft delete kabul edilirse result active listten kalkar ve Trash record oluşur.

- Only Admin Trash endpointi üzerinden result restore/permanent delete yapabilir; restore historical manifesti değiştirip re-run başlatmaz.

- Soft-deleted Strategy/Package/Dataset geçmiş Result manifestinde okunabilir kalır; active selectorlarda yeni run için seçilemez.

- Agent UIyı açmadan same readiness/run/result tool chainini kullanır; parent task run_idyi checkpointine yazar ve normal Lab discussion runı kesmez.

- V18 hard-coded result cardı Productionda BacktestResult rootuyla ilişkilendirilir; card MainboardWorkingItem veya Package olarak persist edilmez.

- Future Dev AI Review placeholderı no active agent task, no automatic performance verdict and no numeric fake metric üretir.

# 17. Final Master Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Run/Result separation</td>
    <td>Evet. BacktestRun orchestration rootudur; only succeeded run immutable BacktestResult yaratır.</td>
  </tr>
  <tr>
    <td>Package vs Working Item</td>
    <td>Evet. Trading Signal ve Trade Log external MainboardWorkingItem olarak doğrulanır; package kind değildir.</td>
  </tr>
  <tr>
    <td>Agent continuity</td>
    <td>Evet. Agent Tool Gateway/API yoluyla same backend capability kullanır; UI/browser/chat dependency değildir.</td>
  </tr>
  <tr>
    <td>Metric Profile boundary</td>
    <td>Evet. Result View Metric Profile only presentation preference; engine metrics, run profile ve artifact profiledan ayrıdır.</td>
  </tr>
  <tr>
    <td>Run manifest integrity</td>
    <td>Evet. exact revisions, data time policies, allocation/engine execution context pinned ve hashlenmiştir.</td>
  </tr>
  <tr>
    <td>Async durability</td>
    <td>Evet. queue/worker/event stream; refresh/logout does not stop run.</td>
  </tr>
  <tr>
    <td>Trash/Admin boundary</td>
    <td>Evet. normal soft delete; Admin-only Trash view/restore/permanent delete; historical provenance korunur.</td>
  </tr>
  <tr>
    <td>V18/Production separation</td>
    <td>Evet. local boolean, hard-coded metrics, placeholder charts, DOM delete and single-card behavior canonical Production yerine geçmez.</td>
  </tr>
  <tr>
    <td>Future Dev boundary</td>
    <td>Evet. Diagnostics/AI Review placeholder active Production V1 AI verdict/live trading gibi yazılmamıştır.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Canonical summary. Entropiada RUN bir “hesapla” butonu değil; current Mainboard composition için server-side preflight, immutable manifest ve durable queue üzerinden başlatılan BacktestRun intentidir. Backtest Results ise browserda üretilen bir dashboard değil, yalnız succeeded runın immutable kanıt artifactlerini okuyan result görünümüdür.</th>
  </tr>
</table>
