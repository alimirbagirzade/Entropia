---
title: "Entropia V18 — Results History Page Documentation v1.1"
page_number: 16
document_type: "Page implementation specification"
source_document: "Entropia_V18_Results_History_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Results History Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18
> **Original DOCX footer:** ENTROPIA V18 | Results History | Sayfa Dokümantasyonu 16/22 | Production V1 uygulama sözleşmesi

ENTROPIA V18

RESULTS HISTORY

Sayfa Dokümantasyonu 16/22 | Immutable Backtest Result indexi, history sorgusu, sorting, comparison context ve lifecycle görünümü

# 0. Document Control, Scope ve Source Traceability

Bu belge yalnız Results History sayfasını tanımlar. Sayfanın görevi tamamlanmış Backtest Result kayıtlarını kalıcı, policy-filtered ve immutable bir history indeksi olarak listelemektir. Mainboard üzerindeki güncel result kartının oluşturulması, Backtest Run lifecycle’ı, detaylı chart/ledger görünümü, Arrange Metrics düzenleyicisi, sonuç export ekranı, Ready Check ve Trash ekranının kendisi bu belgenin ayrı kapsamı değildir; burada yalnız Results History üzerindeki etkileri açıklanır.

<table>
  <tr>
    <th>Kilit canonical karar. Results History yalnız succeeded Backtest Run sonrasında materialize edilmiş immutable Backtest Result kayıtlarını indeksler. Failed veya cancelled Backtest Run için normal Backtest Result/history satırı oluşmaz. History listesi Mainboard’un anlık DOM state’inden veya localStorage listesinden türetilmez; server-side Result store üzerinden sorgulanır.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Kaynak / tür</th>
    <th>Bu sayfada kullanılan bölüm</th>
    <th>Kullanım amacı</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0</td>
    <td>Modül 13 §2-§10; özellikle §6 Results History, §9 authority/lifecycle, Canonical Integration CR-03/CR-04/CR-06/CR-07.</td>
    <td>Immutable result, server-side history, sort semantics, metric/profile ayrımı, access, soft delete, audit ve export/review sınırı.</td>
  </tr>
  <tr>
    <td>Master cross-cutting</td>
    <td>Modül 1-3, 12, 19 ve 20.</td>
    <td>Role/visibility, ownership, soft delete/Trash, run-to-result materialization, API ve async/event sınırları.</td>
  </tr>
  <tr>
    <td>V18 ana HTML</td>
    <td>Performance Metrics &gt; Results History; showResultsHistory(), renderResultsHistory(), refreshResultsHistory(), toggleHistoryDetails(); backtestHistory demo array.</td>
    <td>Görünen toolbar, six sort option, history card summary, expand/collapse arrow ve prototype detail text.</td>
  </tr>
  <tr>
    <td>Handoff v1.1</td>
    <td>Kilit şablon, source traceability, matrixler, UI/Production ayrımı, agent parity, acceptance tests.</td>
    <td>Belge yapısı ve açıklama derinliği.</td>
  </tr>
  <tr>
    <td>2.3 Position Entry Logic örneği</td>
    <td>Kavram-UI-backend-engine-agent-validation anlatım seviyesi.</td>
    <td>Detay kalitesi referansı; canonical teknik karar kaynağı değildir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam içi</th>
    <th>Kapsam dışı / çapraz referans</th>
  </tr>
  <tr>
    <td>History toolbar, sort selection, result summary cards, expandable manifest summary, empty/loading/error/stale state, server-side list query, result visibility, comparison-context warning, result history lifecycle/audit etkileri.</td>
    <td>RUN kabulü ve worker orchestration (Sayfa 15); Backtest Ready Check remediation (Sayfa 14); chart, trade ledger ve diagnostics detay renderer (Sayfa 15); Result View Metric Profile editor (Sayfa 17); Trash ekranı/restore UI (Sayfa 20); export detail actions (Sayfa 15).</td>
  </tr>
  <tr>
    <td>History read model, server-side sort/cursor behavior, result detail excerpt retrieval, policy filtering, Agent result query parity.</td>
    <td>Backtest engine’in metric hesaplama formüllerinin uygulanması; Strategy veya Package edit; Market/Research Data ingest; sonuçların yeni run ile oluşması.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kavramsal Sınır

Results History, geçmiş denemelerin geçici bir listesi değil; immutable Backtest Result kanıt paketlerini indeksleyen kalıcı bir sorgu katmanıdır. Her satır, bir başarılı run sonrasında üretilmiş result_id’ye bağlanır. Satırın açılması, o ResultManifestSnapshot’ın insan okunabilir özetini gösterir; açık Mainboard, yeni Strategy revision veya sonradan değiştirilmiş Metric Profile geçmiş Result’u değiştirmez.

<table>
  <tr>
    <th>Kavram</th>
    <th>Canonical tanım</th>
    <th>Bu sayfadaki uygulama etkisi</th>
  </tr>
  <tr>
    <td>Backtest Run</td>
    <td>Queue, execution, cancellation, failure/retry ve worker lifecycle sahibidir.</td>
    <td>History listesi Run değil, yalnız başarılı runın ürettiği final Result’u gösterir.</td>
  </tr>
  <tr>
    <td>Backtest Result</td>
    <td>Succeeded run sonrası oluşan immutable final evidence record; metrics, manifest snapshot, ledger/curve/diagnostics artifact referansları taşır.</td>
    <td>History satırının tek kaynak kimliği result_id’dir. Satırdaki sayı browserda tekrar hesaplanmaz.</td>
  </tr>
  <tr>
    <td>ResultManifestSnapshot</td>
    <td>Run manifestin final result anındaki canonical kopyası ve result artifact/engine bilgisi.</td>
    <td>Expanded detailde strategy/package/data/allocation/engine context insan okunabilir özet olarak gelir.</td>
  </tr>
  <tr>
    <td>Result View Metric Profile</td>
    <td>Result ekranında görünen metric subset/sırasını belirleyen presentation tercihi.</td>
    <td>History’nin sabit key-metric digestini veya historic metric value kayıtlarını değiştirmez.</td>
  </tr>
  <tr>
    <td>Soft delete</td>
    <td>Active alanlardan kaldırıp Admin Trash üzerinden geri alınabilir tutan root lifecycle işlemi.</td>
    <td>Soft-deleted result History querysinden çıkar. Restore aynı result_id ve artifact hashleriyle tekrar indekse döner.</td>
  </tr>
  <tr>
    <td>Comparison context</td>
    <td>İki immutable Result’un Market Data revision, engine version, allocation ve execution bağlamlarını karşılaştıran manifest farkı.</td>
    <td>Sonuçlar yanyana okunabilir; bağlam farkı gizlenmez veya daha yüksek return otomatik “daha iyi” sayılmaz.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam sınırı. Results History sonucunu yeniden çalıştırmaz, metric hesaplamaz, Result payload’ını değiştirmez ve başarısız/cancelled Run için sonuç satırı üretmez. Bu sayfa bir evidence indexidir; canlı trading, AI Review veya yeni bir backtest iş akışı değildir.</th>
  </tr>
</table>

# 2. Erişim, Görünürlük, Kullanım ve Server-Side Yetki

UIde Performance Metrics menüsünün görünmesi veya history satırının client listesinde bulunması yetki kanıtı değildir. Her list, detail, compare, export, delete veya restore isteğinde backend; principal, role, resource visibility, owner, lifecycle ve operation türünü yeniden doğrular. Direkt URL/API çağrısı UI gizleme davranışını aşamaz.

<table>
  <tr>
    <th>İşlem</th>
    <th>Guest</th>
    <th>User</th>
    <th>Supervisor</th>
    <th>Admin</th>
    <th>Agent</th>
  </tr>
  <tr>
    <td>Results History listeleme / detail görüntüleme</td>
    <td>Hayır. Authentication veya public policy yoksa sonuç döndürülmez.</td>
    <td>Kendi + explicitly shared + published sonuçlar.</td>
    <td>Erişilebilir/shared çalışma kapsamındaki sonuçlar; başkasının sonucu salt-okunur.</td>
    <td>Tüm erişilebilir sonuçlar ve gerekli audit bağlamı.</td>
    <td>Allowed research/result scope içindeki sistem içeriği ve kendi outputs; UI login’e bağlı değildir.</td>
  </tr>
  <tr>
    <td>History sort / cursor query</td>
    <td>Hayır.</td>
    <td>Yalnız policy-filtered result set üzerinde.</td>
    <td>Yalnız policy-filtered result set üzerinde.</td>
    <td>Yalnız policy-filtered result set üzerinde.</td>
    <td>Trusted tool context üzerinden policy-filtered result set üzerinde.</td>
  </tr>
  <tr>
    <td>Comparison context okuma</td>
    <td>Hayır.</td>
    <td>İki result için de view yetkisi şarttır.</td>
    <td>İki result için de view yetkisi şarttır.</td>
    <td>Yetkili tüm result çiftleri.</td>
    <td>İki result için de tool-level view/use policy şarttır.</td>
  </tr>
  <tr>
    <td>Soft delete</td>
    <td>Hayır.</td>
    <td>Yalnız own Backtest Result root/own output.</td>
    <td>Yalnız own Backtest Result root/own output.</td>
    <td>Her sonucu soft delete edebilir.</td>
    <td>Yalnız kendi ürettiği output/result rootu; human session bağımlılığı yoktur.</td>
  </tr>
  <tr>
    <td>Trash / restore / permanent delete</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Yalnız Admin.</td>
    <td>Hayır.</td>
  </tr>
</table>

Authorization note: Client tarafından gönderilen role, owner, result visibility, result status, selected row veya is_admin alanı otorite kabul edilmez. List endpoint unauthorized resultları hiç döndürmez; detail/compare endpointleri ayrıca yeniden can_view değerlendirmesi yapar.

# 3. V18 Interface Behavior: Gerçek Arayüz Yerleşimi ve Görünür Bileşenler

V18de Results History, üst navigation shell içindeki Performance Metrics açılır menüsünden açılır. Seçildiğinde workspace içinde generic page view gösterilir; başlık “Results History”, gövde ise page-box alanıdır. V18de ayrı modal, dialog, search form, pagination control, filter panel, comparison selector, export button, delete button veya ⓘ info icon görünmez.

<table>
  <tr>
    <th>Bölge / bileşen</th>
    <th>V18de gerçek görünüm ve default</th>
    <th>Etkileşim / görünme koşulu</th>
  </tr>
  <tr>
    <td>Navigation</td>
    <td>Performance Metrics menu &gt; Results History.</td>
    <td>Menu item tıklanınca showResultsHistory(event) çağrılır; page title ve page content render edilir.</td>
  </tr>
  <tr>
    <td>History toolbar</td>
    <td>Kalın label: “Sort Backtest Results:” + select. Default selected value: “Newest / Current First”.</td>
    <td>Select onchange refreshResultsHistory(this.value) çağrır ve pageContent içeriğini V18de yeniden üretir.</td>
  </tr>
  <tr>
    <td>Sort dropdown</td>
    <td>Newest / Current First; Highest Return; Highest ROMAD; Lowest Drawdown; Highest Win Rate; Most Trades.</td>
    <td>V18de backtestHistory array kopyası client-side sort edilir. “newest” seçiminde array existing order korunur.</td>
  </tr>
  <tr>
    <td>History card</td>
    <td>Her backtestHistory itemi için açık mavi history-card ve history-row.</td>
    <td>Card summary formatı: BACKTEST RESULT id | title | Net +% | ROMAD | DD -% | Win Rate %.</td>
  </tr>
  <tr>
    <td>Expand/collapse arrow</td>
    <td>Her rowda başlangıç “▼”.</td>
    <td>Tıklama details classını open yapar ve ikon “▲” olur; tekrar tıklama kapatır.</td>
  </tr>
  <tr>
    <td>History detail body</td>
    <td>Başlangıçta gizli; Strategies, Parameters, Data: BTCUSD, selected timeframe, stored Market Data source; Date ve explanatory note içerir.</td>
    <td>Arrow açıldığında görünür. V18 data bağlamı sabit demo metnidir; server request yapılmaz.</td>
  </tr>
  <tr>
    <td>Empty/loading/error/stale state</td>
    <td>V18de yok; demo array başlangıçta üç kayıtla doludur.</td>
    <td>Production V1de zorunlu read-state’lerdir; §4 ve §6daki final UI textleri kullanılmalıdır.</td>
  </tr>
</table>

<table>
  <tr>
    <th>V18 Interface Observation. V18de history data, in-memory backtestHistory arrayinden gelir; sort browserda yapılır; expanded details aynı demo objectten okunur. Bu davranış mevcut arayüz niyetini gösterir, Production V1 persistence, sorting, lifecycle veya authorization doğrusu değildir.</th>
  </tr>
</table>

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen</th>
    <th>Varsayılan / active state</th>
    <th>Loading / disabled / empty / error / stale davranışı</th>
    <th>Production payload ve engine etkisi</th>
  </tr>
  <tr>
    <td>History page</td>
    <td>Successful result varsa ilk cursor page “newest/current first” ile yüklenir.</td>
    <td>Loadingde skeleton rows + “Loading Results History...”. Emptyde §6 metni. Query failureda Retry. Stalede non-blocking refresh banner.</td>
    <td>Salt-okunur query projectionudur. Engine evaluation, run manifest veya result metriclerini değiştirmez.</td>
  </tr>
  <tr>
    <td>Sort dropdown</td>
    <td>Default newest_current semanticine map edilir; dropdown enableddir.</td>
    <td>Initial load veya sort request pending iken disabled; prior rows korunabilir fakat aria-busy gösterilir. Failureda previous successful sort görünür kalır.</td>
    <td>GET /backtest-results query parameterıdır; persisted Result, Result View Metric Profile veya run config değiştirmez.</td>
  </tr>
  <tr>
    <td>History card</td>
    <td>Result materialization_status=complete ve lifecycle_state=active olan erişilebilir result için görünür.</td>
    <td>Soft-deleted/access-revoked result next canonical refreshte listten çıkar. Result complete değilse card hiç görünmez.</td>
    <td>History row immutable result summaryden türetilir. Browser summary metric hesaplamaz.</td>
  </tr>
  <tr>
    <td>Expand arrow / detail</td>
    <td>Closed; “▼”.</td>
    <td>Detail fetch pendingde arrow disabled, inline “Loading result context...” gösterilir. 404/policy loss ise generic unavailable message ve card refresh edilir.</td>
    <td>GET /backtest-results/{result_id}; only manifest excerpt ve artifact availability okunur. Result state mutasyonu yoktur.</td>
  </tr>
  <tr>
    <td>Load more results</td>
    <td>V18de yok. Production Implementation Decision: next_cursor varsa görünür.</td>
    <td>Pendingde “Loading more...”; terminalde hidden. Cursor invalidse full refresh CTA gösterilir.</td>
    <td>Cursor query only. Query result snapshot sıradaki cursor’a bağlanır; client local append sadece projection cacheidir.</td>
  </tr>
  <tr>
    <td>Compare selection</td>
    <td>V18de yok. Production Implementation Decision: row-level compare checkbox; max two selection.</td>
    <td>0/1 selectionde Compare disabled; exactly 2de enabled; access kaybı/soft delete sonrası selection temizlenir.</td>
    <td>Transient client selection of result_id[]; Result mutate edilmez. Server compare request her id için policy kontrolü yapar.</td>
  </tr>
  <tr>
    <td>Comparison warning</td>
    <td>Yalnız comparison manifest contexts differ ise görünür.</td>
    <td>No difference varsa banner görünmez. Missing manifest field “Not available” ile açıkça işaretlenir; 0/fake default kullanılmaz.</td>
    <td>Market Data revision, engine version, allocation plan revision, execution assumptions ve relevant data context karşılaştırılır.</td>
  </tr>
  <tr>
    <td>History projection event</td>
    <td>SSE/resource changed sonrası liste invalidation alabilir.</td>
    <td>Open page refresh prompt gösterir; user refreshes veya safe auto-refresh uses current query. Scroll/selection korunamıyorsa açık mesaj verilir.</td>
    <td>Source of truth server result indexidir; stale local list kalıcı doğru değildir.</td>
  </tr>
</table>

# 5. Field Contract Matrix: Toolbar, Card ve Production Query Sözleşmesi

Results History klasik kayıt formu değildir. V18de kullanıcıdan kalıcı bir Result alanı istenmez; bu nedenle görünür yıldız (*) taşıyan zorunlu input yoktur. Ancak query parametreleri, history/detail/compare endpointlerine verilen kimlikler ve production cursor davranışı server-side doğrulanır. “Zorunlu” burada yalnız UI labelı değil, endpoint/tool schema gereksinimidir.

<table>
  <tr>
    <th>Alan / control</th>
    <th>UI tipi ve V18 default</th>
    <th>Zorunluluk / tüm seçenekler</th>
    <th>Production contract ve validation</th>
  </tr>
  <tr>
    <td>Sort Backtest Results</td>
    <td>Select. V18 default: Newest / Current First.</td>
    <td>UIde star yoktur. Query verildiğinde valid enum zorunludur. Options: Newest / Current First; Highest Return; Highest ROMAD; Lowest Drawdown; Highest Win Rate; Most Trades.</td>
    <td>V18 value map: newest -&gt; newest_current; highestReturn -&gt; net_profit_percent_desc; highestRomad -&gt; romad_desc; lowestDrawdown -&gt; max_drawdown_asc; highestWinrate -&gt; win_rate_desc; mostTrades -&gt; total_trades_desc. Unknown enum -&gt; INVALID_SORT_KEY.</td>
  </tr>
  <tr>
    <td>result_id</td>
    <td>V18de summaryde “BACKTEST RESULT {id}” olarak görünür; production primary key UI short formda maskelenebilir.</td>
    <td>Detail/compare/export/delete commandde required. User editable input değildir.</td>
    <td>UUID/opaque ID; visible history listten gelmiş olsa bile server can_view tekrar doğrular. Unknown/not visible -&gt; generic RESULT_NOT_AVAILABLE.</td>
  </tr>
  <tr>
    <td>cursor</td>
    <td>V18de yok.</td>
    <td>Production list queryde optional. First page absent/null; subsequent requestte next_cursor required.</td>
    <td>Opaque server cursor. Client decode/construct edemez. Invalid/expired cursor -&gt; CURSOR_INVALID ve full refresh recovery.</td>
  </tr>
  <tr>
    <td>page_limit</td>
    <td>V18de yok.</td>
    <td>Production default 25; client maximum 100 isteyebilir. Server safe limit uygular.</td>
    <td>Implementation Decision. Unbounded history response yasaktır; high-volume list cursor pagination ile gelir.</td>
  </tr>
  <tr>
    <td>expanded_result_id</td>
    <td>Arrow ile transient open/closed DOM state.</td>
    <td>Optional; aynı anda birden fazla card açık olabilir, ancak production lazy detail cache result_id content hash ile ilişkilidir.</td>
    <td>Persist edilmez ve Result state değildir. Soft delete/access change halinde cache discard edilir.</td>
  </tr>
  <tr>
    <td>compare_selection[]</td>
    <td>V18de yok.</td>
    <td>Production decision: 0-2 result_id. Compare action için exactly 2 required.</td>
    <td>İki id farklı olmalı; ikisinde de can_view şart. Same id -&gt; COMPARE_REQUIRES_TWO_DISTINCT_RESULTS.</td>
  </tr>
  <tr>
    <td>Result detail fields</td>
    <td>V18de Strategies, Parameters, Data, Date serbest demo text olarak görünür.</td>
    <td>No star. Production manifest excerptte field mevcut değilse missing value 0 olarak doldurulmaz.</td>
    <td>Human-readable display DTO: composition context, pinned strategy/package revisions, data context, allocation context, engine/execution, completed_at. Raw mutable Mainboard state kullanılamaz.</td>
  </tr>
</table>

# 6. Information Content Catalog ve Nihai UI Metinleri

V18 Results History toolbarı veya cards üzerinde ⓘ düğmesi göstermez. Bu nedenle V18de uygulanacak mevcut bilgi popoverı yoktur. Aşağıdaki üç panel, Production V1de helper content ihtiyacını karşılamak için Implementation Decision olarak tanımlanır; ilgili icon render edilirse metin doğrudan UIya yerleştirilmelidir. Icon render edilmiyorsa içerik ayrı help drawer veya inline helper olarak aynı anlamla sunulur.

<table>
  <tr>
    <th>Info key / alan</th>
    <th>Panel başlığı</th>
    <th>Nihai UI metni</th>
  </tr>
  <tr>
    <td>resultsHistorySortInfo / Sort Backtest Results</td>
    <td>How Results History sorting works</td>
    <td>Results History sorts immutable completed Backtest Results. Highest Return uses canonical net return percentage, not a nominal currency amount. Lowest Drawdown uses the absolute maximum drawdown value even when the card displays a minus sign. Results with a metric that was not computed are placed after results with a usable value. Sorting changes only this list view; it never changes a result, its metrics, or the current Mainboard.</td>
  </tr>
  <tr>
    <td>historyRecordInfo / History result card</td>
    <td>What this history record represents</td>
    <td>Each card represents one immutable Backtest Result created after a successful run. The summary and expanded context come from the result manifest and stored artifacts, not from the current Mainboard. Editing a strategy, package, dataset, allocation plan, or metric view preference later does not rewrite this record.</td>
  </tr>
  <tr>
    <td>comparisonContextInfo / comparison warning</td>
    <td>Why comparison context matters</td>
    <td>Two results can be read side by side, but they may not be directly comparable. A different Market Data revision, engine version, execution cost model, or Portfolio Allocation Plan revision can change the meaning of a higher return or lower drawdown. Review the comparison context before choosing a preferred result.</td>
  </tr>
</table>

## 6.1 Nihai UI metinleri: helper, empty, loading, warning, toast ve error

<table>
  <tr>
    <th>Durum / konum</th>
    <th>Nihai metin</th>
  </tr>
  <tr>
    <td>Initial load</td>
    <td>Loading Results History...</td>
  </tr>
  <tr>
    <td>Load more</td>
    <td>Loading more results...</td>
  </tr>
  <tr>
    <td>Empty active history</td>
    <td>No completed Backtest Results are available yet. Run a Ready Mainboard configuration to create the first immutable result.</td>
  </tr>
  <tr>
    <td>Filtered/visible empty</td>
    <td>No completed Backtest Results match this view. Results that are not visible to you are not shown.</td>
  </tr>
  <tr>
    <td>Generic load error</td>
    <td>Results History could not be loaded. Retry to request the current server index.</td>
  </tr>
  <tr>
    <td>Detail loading</td>
    <td>Loading immutable result context...</td>
  </tr>
  <tr>
    <td>Detail unavailable</td>
    <td>This Backtest Result is no longer available in your current view. Refresh Results History.</td>
  </tr>
  <tr>
    <td>Stale/invalidation banner</td>
    <td>Results History changed while this page was open. Refresh to load the current index.</td>
  </tr>
  <tr>
    <td>Soft-delete confirmation - only where an authorized production action is rendered</td>
    <td>Move this Backtest Result to Trash? It will disappear from active history. The run manifest and provenance remain preserved for audit and authorized restore.</td>
  </tr>
  <tr>
    <td>Soft-delete success</td>
    <td>Backtest Result moved to Trash.</td>
  </tr>
  <tr>
    <td>Restore success - Admin-only, surfaced after Trash workflow</td>
    <td>Backtest Result restored to active Results History.</td>
  </tr>
  <tr>
    <td>Comparison context differs</td>
    <td>Comparison context differs. Review Market Data revision, engine version, execution assumptions, and allocation context before interpreting the metrics.</td>
  </tr>
  <tr>
    <td>No comparable metric</td>
    <td>Not available</td>
  </tr>
  <tr>
    <td>No qualifying trade condition</td>
    <td>No qualifying trades</td>
  </tr>
  <tr>
    <td>Uncomputed metric condition</td>
    <td>Not computed</td>
  </tr>
</table>

# 7. Buton, Command ve State Sözleşmesi

V18de görünür actionable controls yalnız sort dropdown ile detail arrowdur. Aşağıdaki Production contracts aynı kullanıcı niyetini durable server behaviora taşır. API path örnekleri Implementation Decisiondır; canonical olan command semantiği, policy ve immutable Result sınırıdır.

<table>
  <tr>
    <th>UI action</th>
    <th>Production command / query</th>
    <th>Precondition ve disabled/loading</th>
    <th>Success / error / audit davranışı</th>
  </tr>
  <tr>
    <td>Sort seçimi</td>
    <td>GET /backtest-results?sort=&lt;enum&gt;&amp;cursor=&lt;opaque&gt;&amp;limit=&lt;n&gt;</td>
    <td>Authenticated/authorized context. Sort request pendingken select disabled veya request cancel/restart edilir.</td>
    <td>Server numeric canonical valuesle sıralar. Success yeni list DTO; failure previous list korunur + retry message. Read sort audit gerektirmez.</td>
  </tr>
  <tr>
    <td>Expand result detail</td>
    <td>GET /backtest-results/{result_id}</td>
    <td>Card COMPLETE+active ve caller can_view. Pendingde arrow disabled, inline loading.</td>
    <td>Returns summary + manifest excerpt + permission/artifact availability. RESULT_VIEWED audit only event policy açık ise yazılır; Result mutasyona uğramaz.</td>
  </tr>
  <tr>
    <td>Load more</td>
    <td>GET /backtest-results?cursor=&lt;next_cursor&gt;&amp;same query params</td>
    <td>next_cursor mevcut olmalı; duplicate in-flight request disabled.</td>
    <td>Append de-duplicated result_id set. CURSOR_INVALID -&gt; full refresh CTA. No mutation/audit.</td>
  </tr>
  <tr>
    <td>Compare selected - production decision</td>
    <td>POST /backtest-results/compare { result_ids:[a,b] } veya equivalent read query.</td>
    <td>Exactly two distinct selected result; both can_view. Button otherwise disabled.</td>
    <td>Read-only comparison DTO + context-difference flags. No result mutation. Access failure selection cleared and generic unavailable message shown.</td>
  </tr>
  <tr>
    <td>Soft delete result - no V18 History button</td>
    <td>POST /backtest-results/{result_id}/delete with If-Match result ETag and idempotency_key.</td>
    <td>Caller can_delete; result active; confirmation accepted. Button is not part of V18 History baseline.</td>
    <td>Result lifecycle -&gt; soft_deleted; history projection removes card; Trash entry and RESULT_SOFT_DELETED audit event. Conflict -&gt; refresh current list.</td>
  </tr>
  <tr>
    <td>Restore - outside active History page</td>
    <td>POST /trash/{trash_entry_id}/restore.</td>
    <td>Admin-only; eligible Trash entry.</td>
    <td>Same result_id and immutable artifact hashes return to active history. RESULT_RESTORED audit. History page refreshes through event/query.</td>
  </tr>
  <tr>
    <td>Permanent delete - outside active History page</td>
    <td>DELETE /trash/{trash_entry_id}/purge.</td>
    <td>Admin-only; retention/purge policy and re-authentication policy where configured.</td>
    <td>RESULT_PURGED audit; minimum provenance/tombstone retained according to retention policy. Not a normal History list action.</td>
  </tr>
</table>

# 8. Kullanıcı ve Sistem Akışları

## 8.1 Flow A - Varsayılan history listesi ve server-side sorting

- Yetkili kullanıcı Performance Metrics > Results History menüsünü açar. Frontend local demo arrayi yerine GET /backtest-results ile active, complete ve policy-visible result indexini ister.

- Server result visibility, owner/shared/published policy, lifecycle_state=active ve materialization_status=complete koşullarını uygular; failed/cancelled runları veya integrity_failed resultları normal history satırı olarak döndürmez.

- Default sort newest/current first semanticidir: completed_at desc, deterministic tie-breaker result_id desc. V18deki “Current First” ifadesi mutable Mainboard contentini history satırına bağlamaz.

- Kullanıcı dropdown seçimini değiştirir. Server sort keyi canonical numeric registry valueyle uygular; card üzerinde yuvarlanmış “+84.2%” metni üzerinden JavaScript sort yapılmaz.

- UI returned cursor pagei render eder. next_cursor varsa Load more control görünür; page state refresh/logout sonrası server queryden yeniden oluşturulur.

## 8.2 Flow B - Expanded immutable manifest summary

- Kullanıcı bir history card üzerindeki ▼ ikonuna basar. UI cardı açık statee geçirirken GET /backtest-results/{result_id} ile canonical summary/manifest excerpt ister.

- Server result_id için can_view değerlendirmesini tekrar yapar. Browserın daha önce listede card göstermiş olması yeterli değildir.

- Başarılı response, composition context, pinned strategy/package revision özeti, Market/Research Data bağlamı, allocation/execution/engine context ve completed timestamp içerir. Current Mainboard veya latest package isimleri yeniden resolve edilmez.

- UI available olmayan alanı 0 ya da boş başarı göstergesiyle doldurmaz; “Not available” veya “Not computed” kullanır.

- Kullanıcı ▲ ikonuna basınca detail visual state kapanır. Result root, audit, metric veya manifest değişmez.

## 8.3 Flow C - Comparison context warning

- Production Implementation Decision kapsamında kullanıcı iki erişilebilir Result seçer. Selection yalnız browser stateinde result_id[] olarak tutulur; result kayıtlarına write yapılmaz.

- Server her iki result için view policyyi uygular, immutable manifest excerptlerini karşılaştırır ve metrics/summary ile birlikte comparison context flags döndürür.

- Market Data revision, engine version, Portfolio Allocation Plan revision veya execution assumptions farklıysa UI “Comparison context differs” warningini gösterir.

- Kullanıcı yüksek Net Profit değerini otomatik bir üstünlük olarak yorumlayacak bir rank/badge görmez. Bağlam farklılığı görünür kalır.

- Selected result soft delete edilir veya access revoked olursa selection temizlenir; prior comparison drawer stale sayılır ve generic refresh message gösterilir.

## 8.4 Flow D - Result soft delete, restore ve history projection

- Yetkili actor resultu ayrı authorized result actionından soft delete ister. Results History V18de delete actionı göstermez; Productionda action render edilirse confirmation metni §6daki metin olmalıdır.

- Server owner/Admin policy, result active lifecycle, If-Match ETag ve idempotency keyi kontrol eder. Result content/manifest/metric value mutate edilmez.

- Commit sonrası BacktestResult lifecycle_state=soft_deleted olur, Trash entry ve RESULT_SOFT_DELETED audit event oluşur. History query aktif cardı döndürmez.

- Admin Trash üzerinden restore ettiğinde server aynı result_id ile lifecycle_state=active durumuna döner; immutable manifest/artifact hashleri değişmez. RESULT_RESTORED audit event yazılır.

- Failed/cancelled run diagnosticsi result delete/restore akışının yerine geçmez; bunlar normal Results History satırı değildir.

## 8.5 Flow E - Empty, permission, stale ve recovery

- İlk result yoksa empty state, “No completed Backtest Results are available yet...” metnini gösterir; fake example metric/card üretilmez.

- User başka kullanıcının private result_id değerini detail URL ile çağırırsa server resource existence sızdırmayacak generic RESULT_NOT_AVAILABLE / 404-or-policy response döndürür.

- SSE/resource event veya refresh sonrası open list stale olursa frontend cached listin canonical doğruluğunu iddia etmez; refresh bannerı gösterir.

- Cursor geçersizse UI partial/duplicated data append etmez. Result set baştan first cursor ile istenir.

- History request başarısızsa geçmiş başarılı rows ekranda tutulabilir; ancak UI “current” list iddiası yapmaz ve Retry server query gönderir.

# 9. Production Backend ve Domain Davranışı

## 9.1 Core object model ve immutable evidence chain

<table>
  <tr>
    <th>Nesne / projection</th>
    <th>Sorumluluk</th>
    <th>Results History ilişkisi</th>
  </tr>
  <tr>
    <td>BacktestRun</td>
    <td>Run command, queue/worker lifecycle, retry/failure/cancellation ve diagnostics sahibi.</td>
    <td>History record değildir. Succeeded run en fazla bir primary Backtest Result materialize eder.</td>
  </tr>
  <tr>
    <td>BacktestResult</td>
    <td>Immutable result identity, materialization state, result summary, manifest snapshot ve artifact reference sahibi.</td>
    <td>History row result_id üzerinden buna bağlanır. Content edit yapılamaz.</td>
  </tr>
  <tr>
    <td>ResultManifestSnapshot</td>
    <td>Strategy/Package/Data/Research/Allocation/Engine/Output/validation provenance canonical snapshotı.</td>
    <td>Expanded detail için human-readable excerpt kaynağı; current workspace statei yerine kullanılır.</td>
  </tr>
  <tr>
    <td>Result summary / metric values</td>
    <td>MetricDefinition registry ile versionlanmış canonical values ve null behavior.</td>
    <td>History key metrics fixed digestle gösterilir. Result View Metric Profile summary truthu değiştirmez.</td>
  </tr>
  <tr>
    <td>Result history query projection</td>
    <td>Policy-filtered, cursor-paginated, sortable index read model.</td>
    <td>V18 backtestHistory arrayinin Production karşılığıdır; localStorage/DOM değil server query kaynağıdır.</td>
  </tr>
  <tr>
    <td>Result artifacts</td>
    <td>Trade ledger, signal/filtered events, curves, diagnostics, export artifactleri.</td>
    <td>History row yalnız availability/summary gösterebilir; detail/full viewer başka Result surfaces üzerinden paginated/lazy yüklenir.</td>
  </tr>
  <tr>
    <td>TrashEntry + audit</td>
    <td>Soft delete restore/purge kaydı ve kim/ne/zaman izlenebilirliği.</td>
    <td>Active indexe dahil olmayan rootun recovery/provenance bağlamını korur.</td>
  </tr>
</table>

## 9.2 Result lifecycle ve history publish gate

<table>
  <tr>
    <th>BacktestRun.succeeded<br/>  -&gt; Result materialization transaction<br/>     -&gt; write immutable ResultManifestSnapshot + summary + required artifact references<br/>     -&gt; integrity validation<br/>     -&gt; BacktestResult.materialization_status = complete<br/>     -&gt; publish backtest_result.created / resource.changed<br/>     -&gt; Results History projection includes result<br/><br/>BacktestRun.failed or BacktestRun.cancelled<br/>  -&gt; diagnostics/failure artifacts may exist<br/>  -&gt; no final BacktestResult is published<br/>  -&gt; no Results History row is created</th>
  </tr>
</table>

Production state layering: BacktestResult.materialization_status (materializing | complete | integrity_failed) ile root lifecycle_state (active | soft_deleted) ayrı kavramlardır. Failed/cancelled bir BacktestResult statusu değildir; failed/cancelled BacktestRun terminal stateidir. Bu ayrım CR-03/CR-04 ile zorunludur.

<table>
  <tr>
    <th>Derived rule. History query varsayılanı materialization_status=complete AND lifecycle_state=active olmalıdır. “Deleted”, “failed”, “cancelled” gibi user-facing labels teknik state enumunun yerine kullanılmamalıdır; soft delete teknik statei soft_deleted olarak modellenir.</th>
  </tr>
</table>

## 9.3 History query, sorting ve deterministic pagination

<table>
  <tr>
    <th>GET /backtest-results<br/>  ?sort=newest_current|net_profit_percent_desc|romad_desc|max_drawdown_asc|win_rate_desc|total_trades_desc<br/>  &amp;cursor=&lt;opaque optional&gt;<br/>  &amp;limit=25<br/><br/>Response:<br/>  { items:[HistoryResultRowDTO...], next_cursor, query_fingerprint, server_time }</th>
  </tr>
</table>

<table>
  <tr>
    <th>V18 option</th>
    <th>Canonical production sort</th>
    <th>Deterministic rule</th>
  </tr>
  <tr>
    <td>Newest / Current First</td>
    <td>completed_at_utc DESC, result_id DESC.</td>
    <td>“Current” mutable Mainboard statei değildir. Yeni completed result normalde en yeni kayıttır; timestamp tie result_id ile çözülür.</td>
  </tr>
  <tr>
    <td>Highest Return</td>
    <td>net_profit_percent DESC.</td>
    <td>Nominal currency değil manifest initial_equity denominator ile tanımlı net return percentage. Null last.</td>
  </tr>
  <tr>
    <td>Highest ROMAD</td>
    <td>romad DESC.</td>
    <td>max drawdown=0 ise ROMAD null/no_drawdown olabilir; infinity veya fake large value yoktur. Null last.</td>
  </tr>
  <tr>
    <td>Lowest Drawdown</td>
    <td>absolute max_drawdown_percent ASC.</td>
    <td>UIde negatif işaret görünse de server absolute risk değeriyle sıralar. Null last.</td>
  </tr>
  <tr>
    <td>Highest Win Rate</td>
    <td>win_rate DESC.</td>
    <td>Canonical closed trade-root metric; breakeven denominator davranışı MetricDefinitiona göre. Null last.</td>
  </tr>
  <tr>
    <td>Most Trades</td>
    <td>total_trades DESC.</td>
    <td>Scale leg/fill sayısı değil completed trade root count. Null last.</td>
  </tr>
</table>

## 9.4 History row DTO ve expanded manifest excerpt

<table>
  <tr>
    <th>HistoryResultRowDTO {<br/>  result_id, display_title, composition_context,<br/>  key_metrics:{net_profit_percent, romad, max_drawdown_percent, win_rate, total_trades},<br/>  market_data_revision_summary, timeframe, backtest_range,<br/>  completed_at_utc, materialization_status:&quot;complete&quot;,<br/>  allowed_actions:{view, compare, export, soft_delete}<br/>}<br/><br/>ResultManifestExcerptDTO {<br/>  result_id, composition_snapshot_id, strategy_revision_refs[], package_revision_refs[],<br/>  market_data_revision, research_data_revision_refs[],<br/>  portfolio_allocation_plan_revision_id|null, execution_context,<br/>  engine_contract_version, completed_at_utc, artifact_availability<br/>}</th>
  </tr>
</table>

Raw provider files, complete ledger, curves, hidden policy data veya another owner private metadata History rowa serialize edilmez. Detail DTO only human-readable, policy-permitted manifest excerpt içerir. Büyük ledger/event/curve recordları result_id scoped paginated endpointsden read edilir; History expand buna fallback olarak entire artifact download yapmaz.

# 10. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Konu</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>History source</td>
    <td>In-memory backtestHistory arrayi ve local demo objectleri.</td>
    <td>Immutable BacktestResult index/query store; policy-filtered server data.</td>
    <td>V18 arrayi persistence modeli değildir. GET /backtest-results authoritative read path olur.</td>
  </tr>
  <tr>
    <td>Sorting</td>
    <td>renderResultsHistory içinde client-side array.sort; newest existing order.</td>
    <td>Server-side canonical numeric sort + cursor pagination.</td>
    <td>Rounded card textine göre sort yasaktır. V18 sort labels korunur, API semantic enumlarına map edilir.</td>
  </tr>
  <tr>
    <td>Details</td>
    <td>Strategies/Parameters/Data/Date static/demo stringlerinden render edilir.</td>
    <td>result_id üzerinden ResultManifestExcerptDTO lazy read edilir.</td>
    <td>Current Mainboard, latest Strategy veya latest Market Data kullanılmaz.</td>
  </tr>
  <tr>
    <td>History card identity</td>
    <td>Numeric demo id ve formatted string.</td>
    <td>Opaque result_id + immutable manifest/artifact hashes.</td>
    <td>UI kısa ID gösterebilir; API command canonical opaque ID kullanır.</td>
  </tr>
  <tr>
    <td>Empty/loading/error</td>
    <td>Yok; sample list daima dolu.</td>
    <td>Loading, empty, error, retry, stale and cursor recovery states required.</td>
    <td>§6daki final microcopy uygulanır; fake placeholder results gösterilmez.</td>
  </tr>
  <tr>
    <td>Comparison</td>
    <td>No UI control.</td>
    <td>Two immutable results can be compared with manifest-difference warning.</td>
    <td>Production compare affordance Implementation Decisiondır; V1de max two transient selection ve read-only comparison drawer tanımlanır.</td>
  </tr>
  <tr>
    <td>Delete/restore</td>
    <td>History card üzerinde action yok.</td>
    <td>Policy-guarded soft delete, Admin-only Trash restore/purge.</td>
    <td>History list yalnız active results gösterir; lifecycle command başka authorized surface içinde de render edilebilir.</td>
  </tr>
  <tr>
    <td>Metric presentation</td>
    <td>Card fixed demo metrics gösterir.</td>
    <td>Canonical summary metric values registryden gelir; Result View Metric Profile presentation-onlydir.</td>
    <td>History key-metric digest profile edit ile re-calculated veya silently removed edilmez.</td>
  </tr>
</table>

# 11. Agent Tool/API Eşdeğeri ve Sürekli Çalışma Sınırı

Agentın Results History kullanımı bir browserda Performance Metrics menüsüne basması değildir. Agent, trusted service principal altında Tool Gateway/API üzerinden aynı read/query commandlerini kullanır. Agentın normal kullanıcı UI listesine bağlı olmaması, Result visibility/ownership/retention policylerini aşabileceği anlamına gelmez.

<table>
  <tr>
    <th>Agent capability</th>
    <th>UI eşdeğeri</th>
    <th>Tool/API contract ve sınır</th>
  </tr>
  <tr>
    <td>list_backtest_results</td>
    <td>History list + sort + cursor.</td>
    <td>GET /backtest-results semantic querysini kullanır. Scope policyye göre only allowed results. Agent browser DOMundan result keşfetmez.</td>
  </tr>
  <tr>
    <td>get_backtest_result_summary</td>
    <td>History card expand.</td>
    <td>result_id ile immutable summary/manifest excerpt okur. Current Mainboard değişikliği old resultu değiştirmez.</td>
  </tr>
  <tr>
    <td>compare_backtest_results</td>
    <td>Production compare drawer.</td>
    <td>Two visible result id için server-side context compare alır; Market Data/engine/allocation/execution diff flaglerini tüketir.</td>
  </tr>
  <tr>
    <td>read_result_artifacts</td>
    <td>Detailed Result surface / export actions.</td>
    <td>Ledger/events/curve data result_id scoped, paginated veya artifact URI olarak okunur. Agent partial UI outputtan metric türetmez.</td>
  </tr>
  <tr>
    <td>create_result_interpretation_artifact</td>
    <td>UIde history note yok; Analysis Lab/Artifact surface cross reference.</td>
    <td>Agent immutable resultu değiştiremez. Yeni hypothesis/diagnostic yorum source_result_id, task/checkpoint ve provenance ile ayrı artifact olur.</td>
  </tr>
  <tr>
    <td>request_result_export</td>
    <td>Result detail export action.</td>
    <td>Policy-permitted export job oluşturabilir; output UI metric selectionına göre eksiltilmez; job async çalışır.</td>
  </tr>
  <tr>
    <td>soft_delete_own_result</td>
    <td>Authorized delete action.</td>
    <td>Agent yalnız owner olduğu result/output rootu için delete command çağırabilir. Trash access/restore/purge Agent için yoktur.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Agent boundary. Agent sonucu yorumlayabilir, diagnostic üretebilir, hypothesis oluşturabilir ve yeni Ready Check/Run talebi kuyruklayabilir. Agent ResultSummary, MetricValue, TradeLedger, manifest veya history sort sonucunu mutate edemez. Agent yorumu ayrı provenance taşıyan yeni Artifacttir.</th>
  </tr>
</table>

# 12. Validation, Error ve Recovery Contract

<table>
  <tr>
    <th>Kategori</th>
    <th>Blocker / hata koşulu</th>
    <th>Kullanıcı veya Agent recovery yolu</th>
  </tr>
  <tr>
    <td>Query enum</td>
    <td>Unknown / unsupported sort enum.</td>
    <td>Client known enumlara fallback yapmaz; INVALID_SORT_KEY gösterir, default newest_current ile yeniden query eder.</td>
  </tr>
  <tr>
    <td>Cursor integrity</td>
    <td>Expired, malformed, different query fingerprinte ait veya revizyonu geçersiz cursor.</td>
    <td>CURSOR_INVALID; append yapılan local list temizlenir ve first page refetch edilir.</td>
  </tr>
  <tr>
    <td>Result visibility</td>
    <td>Caller result_idyi bilse bile can_view false veya resource soft-deleted.</td>
    <td>Generic RESULT_NOT_AVAILABLE; UI source existence detayını sızdırmaz. Agent alternate allowed result scope ile devam eder.</td>
  </tr>
  <tr>
    <td>Result completion</td>
    <td>Result materializing/integrity_failed veya run failed/cancelled.</td>
    <td>No history card. Run diagnostic cross-reference ayrı scope üzerinden okunur; fake metrics/history entry gösterilmez.</td>
  </tr>
  <tr>
    <td>Null metric</td>
    <td>Sort/digest metric computed değil, denominator valid değil veya no qualifying trade.</td>
    <td>Null değer 0a çevrilmez. UI Not available / No qualifying trades / Not computed gösterir; sort null last.</td>
  </tr>
  <tr>
    <td>Comparison</td>
    <td>Same id iki kez seçilir; &gt;2 result; one/both result not visible.</td>
    <td>Compare disabled veya structured error. Selection normalize/clear edilir; result data mutasyona uğramaz.</td>
  </tr>
  <tr>
    <td>Soft delete race</td>
    <td>Result page açıkken başka actor rootu soft delete eder; If-Match ETag conflict.</td>
    <td>RESULT_CHANGED / 412; current history query refresh edilerek card kaldırılır. Silent overwrite yoktur.</td>
  </tr>
  <tr>
    <td>Event stream loss</td>
    <td>SSE event copy missed, browser refresh/logout.</td>
    <td>Last event cursor if supported; otherwise current list query refetch. UI temporary cachei canonical truth saymaz.</td>
  </tr>
  <tr>
    <td>Large volume</td>
    <td>Unbounded history/ledger DTO memory pressure.</td>
    <td>History cursor pagination, detail lazy fetch, artifact endpoints. Browserda full ledger preload yasaktır.</td>
  </tr>
</table>

# 13. Lifecycle, Audit ve Trash Etkileri

Backtest Result content immutabledir; soft delete yalnız active discovery/lifecycle katmanını değiştirir. Bir result silindiğinde onu üreten Run manifesti, input revision listesi ve audit/provenance bağı doğrudan yok edilmez. Retention/purge policy result payloadı için ayrı değerlendirilse bile minimum run identity, start/end time, engine version ve input hashleri tombstone/audit bağlamında korunur.

<table>
  <tr>
    <th>Olay</th>
    <th>Result / History etkisi</th>
    <th>Zorunlu audit minimumu</th>
  </tr>
  <tr>
    <td>RUN_COMPLETED</td>
    <td>Run terminal success kaydı; henüz result history cardı tek başına garanti etmez.</td>
    <td>run_id, actor/service, completed_at, terminal state, request/correlation id.</td>
  </tr>
  <tr>
    <td>RESULT_MATERIALIZED</td>
    <td>Immutable BacktestResult ve manifest/artifact refs yazılır.</td>
    <td>result_id, run_id, manifest_hash, artifact hashes/index, materialization outcome.</td>
  </tr>
  <tr>
    <td>backtest_result.created / projection refresh</td>
    <td>materialization_status=complete ise active History indexe girer.</td>
    <td>event id, result_id, projection timestamp, actor/service context.</td>
  </tr>
  <tr>
    <td>RESULT_INTEGRITY_FAILED</td>
    <td>No normal History row; result/detail unavailable olabilir.</td>
    <td>result/run id, failed integrity condition, safe diagnostic reference.</td>
  </tr>
  <tr>
    <td>RESULT_VIEWED</td>
    <td>Optional event policy; Result content değişmez.</td>
    <td>If enabled: actor, result_id, timestamp, view context; high-volume audit policy dikkatle uygulanır.</td>
  </tr>
  <tr>
    <td>RESULT_SOFT_DELETED</td>
    <td>Active History listten kalkar; Trash entry oluşur.</td>
    <td>actor, result_id, prior lifecycle, trash_entry_id, request id, timestamp.</td>
  </tr>
  <tr>
    <td>RESULT_RESTORED</td>
    <td>Same result_id, manifest snapshot ve artifact hashes ile active History indexe tekrar dahil edilir.</td>
    <td>actor=Admin, trash_entry_id, result_id, restore outcome, timestamp.</td>
  </tr>
  <tr>
    <td>RESULT_PURGED</td>
    <td>Active Historyde görünmez; retention policy allowed ise payload purge edilir, minimum provenance korunur.</td>
    <td>actor=Admin, result_id/tombstone reference, retention decision, timestamp.</td>
  </tr>
  <tr>
    <td>METRIC_PROFILE_UPDATED</td>
    <td>History Result canonical metric valuesi değişmez; only UI presentation profile revision değişir.</td>
    <td>actor, profile revision, old/new metric selection/lock state.</td>
  </tr>
</table>

# 14. Kavramsal Terimler

<table>
  <tr>
    <th>Terim</th>
    <th>Bu dokümanda canonical anlamı</th>
  </tr>
  <tr>
    <td>Immutable Result</td>
    <td>Başarılı Backtest Runın sabit input manifestiyle ürettiği, sonradan Strategy/Data/UI değişikliğiyle edit edilmeyen final BacktestResult kanıt kaydı.</td>
  </tr>
  <tr>
    <td>History index</td>
    <td>BacktestResult store üzerinden policy-filtered ve cursor-paginated sorgulanan kalıcı Results History projectionı.</td>
  </tr>
  <tr>
    <td>Key-metric digest</td>
    <td>History rowda sabit gösterilen karşılaştırma özeti; Result View Metric Profiledan bağımsız canonical result metric değerlerinin UI formatlı kısa bölümü.</td>
  </tr>
  <tr>
    <td>ResultManifestSnapshot</td>
    <td>Result oluşurken sabitlenen Strategy/Package/Data/Research/Allocation/Engine/validation provenance manifestinin immutable kopyası.</td>
  </tr>
  <tr>
    <td>Materialization</td>
    <td>Worker ham run outputsunu summary, manifest ve artifact referanslarına dönüştürme ve integrity gate sonrası Result olarak publish etme süreci.</td>
  </tr>
  <tr>
    <td>Comparison context differs</td>
    <td>İki Resultun anlamını etkileyebilecek pinned Market Data revision, engine, execution veya allocation bağlamı farkının görünür uyarısı.</td>
  </tr>
  <tr>
    <td>Soft deleted</td>
    <td>Result contentini aktif historyden kaldıran, Trash/audit ile restore edilebilir lifecycle durumu; permanent purge değildir.</td>
  </tr>
</table>

# 15. Kodcu AI için Implementation Rules

- Results History data kaynağı browser localStorage, current Mainboard DOMu veya V18 demo arrayi olamaz; only server-side immutable BacktestResult query kullanılmalıdır.

- History list yalnız materialization_status=complete ve lifecycle_state=active olan Resultları indekslemelidir. failed/cancelled BacktestRun için BacktestResult/history card üretmek yasaktır.

- History sorting browserda görünen yuvarlanmış stringler üzerinden yapılmamalıdır; canonical numeric MetricDefinition valuesle server-side uygulanmalıdır.

- Highest Return nominal currencyyle değil net_profit_percent ile; Lowest Drawdown UI eksi işaretinden bağımsız absolute max_drawdown_percent ile sıralanmalıdır.

- Null metric value 0, infinity veya sahte default değere dönüştürülmemelidir. UI MetricDefinition null behaviorına uygun metin göstermelidir.

- Expanded History detail current Mainboard stateinden, latest package revisiondan veya cached form stateinden türetilmemelidir; only result_idye bağlı immutable ResultManifestExcerpt okunmalıdır.

- Result View Metric Profile değişikliği BacktestResult metric valuesini, history key-metric digestini veya run manifestini değiştiremez.

- History list cursor-paginated olmalıdır. Browsera unbounded history, complete trade ledger veya complete curve dataset preload etmek yasaktır.

- List, detail, compare, export, delete ve restore operationları ayrı server-side policy kontrolleri taşımalıdır. UIde görünmeyen action direkt API ile authorize edilmiş sayılmaz.

- Compare action exactly two distinct policy-visible result_id ile çalışmalı; context difference görünür warning olmadan “winner” veya automatic rank üretmemelidir.

- Result soft delete BacktestRun, Strategy, Package, Market Data veya Research Data revisionini yok etmez. Only BacktestResult active visibility/lifecycle değişir; Trash/audit oluşur.

- Restore yalnız Admin tarafından çalıştırılmalı ve same result_id + immutable manifest/artifact hashes ile history projectiona dönmelidir.

- HTTP concurrency transportu için result lifecycle mutationlarında If-Match/ETag kullanılmalı; result content için editable draft/revision yolu oluşturulmamalıdır.

- Agent Result historyi Tool Gateway üzerinden sorgulamalı; UI butonlarına tıklama veya human sessiona bağlı browser state kullanmamalıdır.

- Agent yorum/artifact üretirken source_result_id, source_manifest_hash, agent_run_id/task_id ve checkpoint provenance taşımalıdır; ResultSummary/TradeLedger mutasyonu yapmamalıdır.

- SSE/polling reconnect sonrası frontend canonical query refetch ile history projectionu reconcile etmelidir. Local list stale ise quiet client-side merge kalıcı doğru sayılamaz.

# 16. Acceptance Tests

<table>
  <tr>
    <th>ID</th>
    <th>Senaryo</th>
    <th>Beklenen sonuç</th>
  </tr>
  <tr>
    <td>RH-01</td>
    <td>Yetkili user Results Historyyi açar.</td>
    <td>GET /backtest-results yalnız active+complete ve policy-visible immutable results döndürür; V18 sample array source of truth değildir.</td>
  </tr>
  <tr>
    <td>RH-02</td>
    <td>History “Highest Return” ile sıralanır.</td>
    <td>Server net_profit_percent DESC ile sıralar; rendered “+84.2%” metninin locale/string formuna göre sort yapılmaz.</td>
  </tr>
  <tr>
    <td>RH-03</td>
    <td>History “Lowest Drawdown” ile sıralanır.</td>
    <td>Server absolute max_drawdown_percent ASC ile sıralar; UI negative display sign sortingi tersine çevirmez.</td>
  </tr>
  <tr>
    <td>RH-04</td>
    <td>ROMAD null/no_drawdown olan result listede yer alır.</td>
    <td>Result card “Not available”/semantic null behavior gösterir ve Highest ROMAD sıralamasında null results last olur.</td>
  </tr>
  <tr>
    <td>RH-05</td>
    <td>User detail arrowı açar, sonra Mainboarddaki Strategy değiştirilir.</td>
    <td>Açık history detaili immutable manifest excerpti korur; current Mainboard değişikliği historical resultu güncellemez.</td>
  </tr>
  <tr>
    <td>RH-06</td>
    <td>Bir run FAILED veya CANCELLED olur.</td>
    <td>Diagnostics/run state saklanabilir fakat normal BacktestResult/history card oluşturulmaz.</td>
  </tr>
  <tr>
    <td>RH-07</td>
    <td>History query 10,000+ result içinde Load more çalıştırır.</td>
    <td>Cursor pagination kullanılır; browser full result set veya complete ledger yüklemez; duplicate card yoktur.</td>
  </tr>
  <tr>
    <td>RH-08</td>
    <td>User başka owner private result_idsiyle detail endpointi çağırır.</td>
    <td>Server resource visibilityyi tekrar doğrular ve generic unavailable/policy response döndürür; client list filteringe güvenilmez.</td>
  </tr>
  <tr>
    <td>RH-09</td>
    <td>Production compare için iki sonuç seçilir ve Market Data revisions farklıdır.</td>
    <td>Comparison read DTO context diff flag döndürür; warning görünür, auto winner/rank üretilmez.</td>
  </tr>
  <tr>
    <td>RH-10</td>
    <td>User aynı resultı iki kez compare selectiona eklemeye çalışır.</td>
    <td>Compare action disabled veya COMPARE_REQUIRES_TWO_DISTINCT_RESULTS döner; Resultlar mutate edilmez.</td>
  </tr>
  <tr>
    <td>RH-11</td>
    <td>Admin resultu soft delete eder.</td>
    <td>Historyden çıkar, TrashEntry + RESULT_SOFT_DELETED audit oluşur; run manifest/source revisions silinmez.</td>
  </tr>
  <tr>
    <td>RH-12</td>
    <td>Admin Trashdan result restore eder.</td>
    <td>Same result_id, manifest hash ve artifact hashleri ile active Historyye döner; RESULT_RESTORED audit yazılır.</td>
  </tr>
  <tr>
    <td>RH-13</td>
    <td>Result View Metric Profiledan Max Stop Streak kaldırılır.</td>
    <td>Historic metric value silinmez; History key digest ve immutable Result manifesti changesiz kalır.</td>
  </tr>
  <tr>
    <td>RH-14</td>
    <td>Agent UI açık değilken result query + hypothesis artifact üretir.</td>
    <td>Tool Gateway canonical result queryyi kullanır; AgentArtifact source_result_id/provenance taşır, BacktestResult mutate edilmez.</td>
  </tr>
  <tr>
    <td>RH-15</td>
    <td>SSE event bağlantısı kesilir; sonuç sonra materialize olur.</td>
    <td>Frontend yeniden bağlandığında veya refreshte history query canonical server indexini yükler; fake local result oluşturmaz.</td>
  </tr>
  <tr>
    <td>RH-16</td>
    <td>Result lifecycle delete request stale ETag ile gelir.</td>
    <td>Server precondition/conflict döndürür; UI current query ile refresh olur; silent overwrite yapılmaz.</td>
  </tr>
</table>

# 17. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 uyumu</td>
    <td>Evet. Modül 13teki immutable Result, server-side History index, sort, policy, audit ve lifecycle kararları uygulanmıştır.</td>
  </tr>
  <tr>
    <td>Run / Result ayrımı</td>
    <td>Evet. Failed/cancelled Run normal Result/history record üretmez; only succeeded Run final immutable Result materialize eder.</td>
  </tr>
  <tr>
    <td>Metric profile ayrımı</td>
    <td>Evet. Result View Metric Profile presentation-onlydir; engine metric setini veya historic result valuesini değiştirmez.</td>
  </tr>
  <tr>
    <td>V18 / Production ayrımı</td>
    <td>Evet. V18 in-memory sorting/details açıkça prototype olarak ayrılmış; Production server-side query/manifest behavior olarak yazılmıştır.</td>
  </tr>
  <tr>
    <td>Agent parity</td>
    <td>Evet. Agent aynı history/detail/compare capabilitylerini Tool Gateway/API üzerinden human UIden bağımsız kullanır.</td>
  </tr>
  <tr>
    <td>Trash / restore / purge</td>
    <td>Evet. Soft delete active historyden kaldırır; restore/purge yalnız Admin Trash policy ile yürür; provenance korunur.</td>
  </tr>
  <tr>
    <td>Portfolio terminology</td>
    <td>Evet. Allocation bağlamı yalnız Portfolio Allocation Plan / Revision olarak ifade edilmiştir; allocation-profile entity üretilmemiştir.</td>
  </tr>
  <tr>
    <td>Future Dev sınırı</td>
    <td>Evet. AI Review, live trading veya fake result generation bu page behaviora eklenmemiştir.</td>
  </tr>
  <tr>
    <td>Implementation Decision kayıtları</td>
    <td>Evet. Cursor pagination, compare affordance, API path/enum mapping ve helper popoverlar canonical rule olarak değil açık Implementation Decision olarak işaretlenmiştir.</td>
  </tr>
</table>
