---
title: "Entropia V18 — Future Dev Page Documentation v1.1"
page_number: 22
document_type: "Page implementation specification"
source_document: "Entropia_V18_Future_Dev_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Future Dev Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | FUTURE DEV | SAYFA DOKÜMANTASYONU 22/22
> **Original DOCX footer:** Entropia V18 | Future Dev Page Documentation v1.0 | Production V1 implementation reference

ENTROPIA V18

FUTURE DEV

Sayfa Dokümantasyonu 22/22 | Capability Registry, Placeholder Surface, Activation Gates, Graphic View, Future AI/Research Areas, Agent Tool Boundary ve Audit Sözleşmesi

<table>
  <tr>
    <th>Belge kapsamı<br/>Bu belge yalnız üst menüdeki Future Dev alanını tanımlar: Live Trade, Graphic View, AI Operations alt menüsü, Research alt menüsü, Graphic View placeholder görünümü, capability lifecycle, activation boundary, ortak registry/event contractı ve Agent tool exposure sınırı bu kapsamın içindedir. Mainboard, Backtest Results, Arrange Metrics, Analysis Lab, Panel veya gelecekteki aktif Live Trade/Review/Hypothesis ekranlarının kendi ayrıntılı UI sözleşmeleri burada tasarlanmaz.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Kilit Production V1 sınırı<br/>Future Dev menüsünün görünmesi, bir capabilitynin active olduğu anlamına gelmez. V1de Future Dev bir placeholder/roadmap ve controlled activation boundarydir. Active olmayan capability gerçek order, live decision, chart worker, fake progress, kalıcı sahte kayıt veya authoritative result üretemez.</th>
  </tr>
</table>

# 0. Document Control, Scope ve Source Traceability

Bu teslim, Entropia V18 Future Dev sayfası için Production V1 implementation specificationdır. V18 ana HTML, kullanıcının bugün gördüğü navigasyon ve Graphic View placeholderını doğrular. Domain state, authorization, API, lifecycle, event/audit ve Agent davranışında Master Technical Reference v1.0 canonical otoritedir.

<table>
  <tr>
    <th>Kaynak / referans</th>
    <th>Bu sayfada kullanılan karar</th>
    <th>Öncelik ve uygulama notu</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 - Modül 18, Canonical Integration CR-08/CR-09</td>
    <td>Future Dev controlled expansion boundary; Capability Registry; lifecycle states; activation gates; no fake service/job/core entity; Admin-only lifecycle transition; Agent tool gating.</td>
    <td>Canonical technical authority.</td>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 - Modül 0, 1, 2, 3, 12-16, 19, 20</td>
    <td>Active scope boundary, role/policy, immutable revision/result, Trash/audit, agent autonomy, API and worker responsibility, logs/manual linkage.</td>
    <td>Çapraz canonical bağımlılık.</td>
  </tr>
  <tr>
    <td>V18 ana HTML - Future Dev top menu ve showGraphicView()</td>
    <td>Blue dropdown; Live Trade; Graphic View; AI Operations &gt; Backtest Review/Signal Intelligence; Research &gt; Regime Research/Hypothesis Lab/Parameter Fields; Graphic View static cards.</td>
    <td>V18 Interface Observation; production backend doğrusu değildir.</td>
  </tr>
  <tr>
    <td>Sayfa Bazlı Dokümantasyon Handoff v1.1</td>
    <td>Field/state/content/command matrices; V18 vs Production ayrımı; Future Dev Boundary etiketi; Agent parity; acceptance test standardı.</td>
    <td>Yazım ve teslim standardı.</td>
  </tr>
  <tr>
    <td>2.3 POSITION ENTRY LOGIC örneği</td>
    <td>Kavramları insan, frontend, backend, engine ve Agent katmanlarında; validation/recovery/test düzeyinde açıklama standardı.</td>
    <td>Anlatım derinliği referansı; canonical karar kaynağı değildir.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kapsam Sınırı

Future Dev, bugün tamamlanmamış özelliklerin rastgele form, endpoint veya local-state ile "çalışıyor gibi" gösterildiği alan değildir. Entropia içinde kontrollü genişleme sınırıdır. Mevcut Strategy, Package, Market Data, Research Data, Backtest, Result ve Agent çekirdeğini yarım doğrulanmış özelliklerden ayırır; buna karşılık gelecekteki navigasyon yolunu ve teknik geçiş şartlarını sabit tutar.

Canonical Rule: Bir Future Dev capability, server-side Capability Registry içinde açıkça Active veya policy ile izinli Limited durumuna alınmadıkça gerçek production state, gerçek market/execution orderı, authoritative result veya mevcut Backtest Result üzerinde mutation oluşturamaz.

Future Dev Boundary: Bu belge Live Trade, Graphic View renderer, Backtest Review, Signal Intelligence, Regime Research, Hypothesis Lab veya Parameter Fieldsin aktif ürün modüllerini bugün implement etmez. Yalnız bunların placeholderdan gerçek capabilityye geçiş sözleşmesini tanımlar.

<table>
  <tr>
    <th>Alan</th>
    <th>Bu sayfanın sorumluluğu</th>
    <th>Bu sayfanın sorumluluğu değildir</th>
  </tr>
  <tr>
    <td>Future Dev navigation shell</td>
    <td>Sabit capability key ve menu yolu ile placeholder/active durumunu görünür kılmak.</td>
    <td>Mevcut Mainboard veya Backtest Results iş mantığını devralmak.</td>
  </tr>
  <tr>
    <td>Capability Registry</td>
    <td>Future capability stateini, contract versionını, dependency snapshotını ve transition auditini server-side kaynak doğrusu olarak tutmak.</td>
    <td>Tek başına Live Trade, chart, AI review veya research engine üretmek.</td>
  </tr>
  <tr>
    <td>Graphic View placeholder</td>
    <td>V18deki statik kartları ve operasyon dışı açıklamayı göstermek.</td>
    <td>Chart data hazırlamak, price stream açmak, marker hesaplamak veya browserda backtest logic çalıştırmak.</td>
  </tr>
  <tr>
    <td>Future capability activation</td>
    <td>Domain/data/policy/API/test/rollback kapılarının varlığını doğrulamak.</td>
    <td>Eksik capabilityyi sırf menüde var diye active kabul etmek.</td>
  </tr>
</table>

# 2. Kavramsal Terimler

<table>
  <tr>
    <th>Terim</th>
    <th>Canonical kısa anlam</th>
    <th>Uygulama sınırı</th>
  </tr>
  <tr>
    <td>Future Dev</td>
    <td>Hazır olmayan alanların controlled expansion boundarysi ve navigation shellidir.</td>
    <td>Active product module veya roadmapta yazan her şeyin çalıştığı alan değildir.</td>
  </tr>
  <tr>
    <td>Capability</td>
    <td>Belirli bir domain contract, UI surface, API/worker, policy ve lifecycle kuralları olan bağımsız genişleme alanı.</td>
    <td>Sadece menu labelı veya frontend feature flag değildir.</td>
  </tr>
  <tr>
    <td>Capability Registry</td>
    <td>Capability key ve lifecycle state için server-side source of truth olan versioned/auditable kayıt katmanı.</td>
    <td>CSS hide/show veya localStorage booleanı değildir.</td>
  </tr>
  <tr>
    <td>Activation Gate</td>
    <td>Bir capabilitynin lifecycle transitionından önce geçmesi gereken domain, data, policy, UI, API/job, validation ve rollback kapıları.</td>
    <td>Tek bir Admin clickiyle dependency bypassı değildir.</td>
  </tr>
  <tr>
    <td>Placeholder</td>
    <td>Yalnızca amaç, bağımlılık ve erişim sınırını açıklayan inactive state.</td>
    <td>Mock success, fake job, fake output veya kalıcı demo data değildir.</td>
  </tr>
  <tr>
    <td>View Dataset</td>
    <td>Graphic View için immutable Backtest Result veya versioned Market Data referanslarından üretilen renderer-independent input modeli.</td>
    <td>Market/Result stateini mutate eden chart sessionı değildir.</td>
  </tr>
  <tr>
    <td>Analysis Artifact</td>
    <td>Review, Monte Carlo, WFA, sensitivity vb. future analysis outputlarını input manifest refs ve method version ile taşıyan ayrı artifact.</td>
    <td>Backtest Resultın canonical metric alanına sonradan yazılan değer değildir.</td>
  </tr>
  <tr>
    <td>Retired</td>
    <td>Yeni command kabul etmeyen; ancak history/artifact erişimini read-only koruyan capability lifecycle statei.</td>
    <td>Trash veya geçmiş kayıtların imhası değildir.</td>
  </tr>
</table>

# 3. Erişim, Görünürlük ve Server-Side Policy

V18de Future Dev top-menu shelli admin-only CSS sınıfına bağlı değildir; bu nedenle demo arayüzde menu kullanıcıya görünür. Productionda placeholder navigasyonu görünebilir olsa bile operasyon izni, lifecycle state ve command policy server-side yeniden doğrulanır. UI görünürlüğü hiçbir zaman capability kullanım yetkisi değildir.

<table>
  <tr>
    <th>Principal / rol</th>
    <th>Placeholder veya Designed overview</th>
    <th>Limited/Active operation</th>
    <th>Capability lifecycle transition</th>
  </tr>
  <tr>
    <td>Guest / anonymous</td>
    <td>V18de görünür navigation shelli varsa read-only public placeholder metni görebilir. Production expose policy route bazında açıkça uygulanır.</td>
    <td>Hayır. Authenticated principal ve feature-specific policy gerekir.</td>
    <td>Hayır.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Read-only overview ve allowed metadata görebilir.</td>
    <td>Capability-specific contracta göre view/use; mutasyon yalnız explicit policy ile.</td>
    <td>Hayır.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Read-only overview ve allowed metadata görebilir.</td>
    <td>Limited/Active capabilityde policy izin verirse use/create own output. Başkasının normal outputunu mutate edemez.</td>
    <td>Hayır.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm overview ve registry statuslarını görebilir.</td>
    <td>Capability-specific Admin override/policy sınırları içinde işlem yapar.</td>
    <td>Evet. CR-08: lifecycle transition yalnız Admin guard ile.</td>
  </tr>
  <tr>
    <td>Agent system actor</td>
    <td>UIya bağımlı değildir; Placeholder/Designed capability tool registryye verilmez.</td>
    <td>Yalnız Active veya policy ile izinli Limited tool contractı üzerinden kullanır; own output policy geçerlidir.</td>
    <td>Hayır. Agent lifecycle transition yapamaz.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Implementation Decision - Guest visibility<br/>Master Future Dev navigation shelli için Guest görünürlüğünü ayrı bir role matrisiyle kesinleştirmez. V18 menu shelli görünür olduğu için Production V1de public placeholder overviewların Guest tarafından read-only görülebilmesi seçilmiştir. Bu karar yalnız navigation/overview içindir; hiçbir command, artifact, data source veya capability transition izni vermez. Deploymentte public navigation kapatılırsa route da aynı policy ile kapatılmalıdır.</th>
  </tr>
</table>

# 4. V18 Interface Behavior: Gerçek Arayüz Envanteri

V18de Future Dev, üst menu barında mavi arka planla ayrılan bir dropdown olarak görünür. Dropdown parent hover ile açılır. AI Operations ve Research satırları hover ile sağa açılan nested submenu taşır. Graphic View seçilebilir tek placeholder routeudur; diğer capability satırları V18 prototipinde navigasyon/operasyon komutu çalıştırmaz.

<table>
  <tr>
    <th>V18 bileşeni</th>
    <th>Görünür davranış</th>
    <th>Tıklama / hover</th>
    <th>Production yorum</th>
  </tr>
  <tr>
    <td>Future Dev top menu</td>
    <td>Mavi arka planlı menu. Hoverda dropdown açılır.</td>
    <td>Hover only; route açmaz.</td>
    <td>Navigation shell; capability statei değildir.</td>
  </tr>
  <tr>
    <td>Live Trade</td>
    <td>Mavi normal item.</td>
    <td>onclick/clickable tanımı yok; operasyon yok.</td>
    <td>Future execution orchestration slotu.</td>
  </tr>
  <tr>
    <td>Graphic View</td>
    <td>Mavi clickable item.</td>
    <td>showGraphicView() ile page view açılır.</td>
    <td>Placeholder route; chart/job/data yok.</td>
  </tr>
  <tr>
    <td>AI Operations</td>
    <td>Mavi has-sub item.</td>
    <td>Hoverda submenu açılır.</td>
    <td>Grup labelı; bağımsız operation değildir.</td>
  </tr>
  <tr>
    <td>Backtest Review</td>
    <td>AI Operations alt itemı.</td>
    <td>V18de clickable değildir; no-op.</td>
    <td>Future review_artifact capability slotu.</td>
  </tr>
  <tr>
    <td>Signal Intelligence</td>
    <td>AI Operations alt itemı.</td>
    <td>V18de clickable değildir; no-op.</td>
    <td>Future signal event research capability slotu.</td>
  </tr>
  <tr>
    <td>Research</td>
    <td>Mavi has-sub item.</td>
    <td>Hoverda submenu açılır.</td>
    <td>Grup labelı; bağımsız operation değildir.</td>
  </tr>
  <tr>
    <td>Regime Research</td>
    <td>Research alt itemı.</td>
    <td>V18de clickable değildir; no-op.</td>
    <td>Future versioned feature/regime artifact slotu.</td>
  </tr>
  <tr>
    <td>Hypothesis Lab</td>
    <td>Research alt itemı.</td>
    <td>V18de clickable değildir; no-op.</td>
    <td>Future hypothesis/experiment workspace slotu.</td>
  </tr>
  <tr>
    <td>Parameter Fields</td>
    <td>Research alt itemı.</td>
    <td>V18de clickable değildir; no-op.</td>
    <td>Future search-space/sensitivity capability slotu.</td>
  </tr>
</table>

# 4.1 Graphic View Placeholder Page

Graphic View seçildiğinde V18, mainboard view yerine page view açar. Başlık "FUTURE DEV / GRAPHIC VIEW"dir. Page box içinde yalnız statik intro ve altı panel kartı gösterilir. Toolbar, form, filter, modal, input, toggle, checkbox, submit butonu, loading indicator veya chart canvas bulunmaz.

<table>
  <tr>
    <th>Görünür alan / kart</th>
    <th>V18 nihai metni</th>
    <th>V18 state</th>
    <th>Production V1 karşılığı</th>
  </tr>
  <tr>
    <td>Intro</td>
    <td>Graphic View is reserved for future chart and visual-review development. The page is intentionally a placeholder until the chart engine, event markers and structured visual datasets are implemented.</td>
    <td>Static placeholder copy.</td>
    <td>Capability state Placeholder iken read-only overview copy.</td>
  </tr>
  <tr>
    <td>Price Chart</td>
    <td>Future: entry, exit, stop and scaling markers with S1 / S2 / S3 labels.</td>
    <td>Static panel-card.</td>
    <td>View Dataset + renderer adapter aktifleşmeden chart yok.</td>
  </tr>
  <tr>
    <td>Equity Curve</td>
    <td>Future: total portfolio and strategy-level equity curves.</td>
    <td>Static panel-card.</td>
    <td>Pinned Backtest Result / portfolio snapshot olmadan curve yok.</td>
  </tr>
  <tr>
    <td>Drawdown Chart</td>
    <td>Future: time-based drawdown from equity peaks.</td>
    <td>Static panel-card.</td>
    <td>Canonical resultı değiştirmeden visual datasetten render edilir.</td>
  </tr>
  <tr>
    <td>Exposure / Position Size</td>
    <td>Future: open position size, layer count and leverage impact.</td>
    <td>Static panel-card.</td>
    <td>Live execution veya portfolio visualization capabilitysi olmadan operational exposure yok.</td>
  </tr>
  <tr>
    <td>Trade Distribution</td>
    <td>Future: profit/loss distribution, average win, average loss and outlier behavior.</td>
    <td>Static panel-card.</td>
    <td>Analysis/metric contract tamamlanmadan hesaplanmış metric gibi gösterilmez.</td>
  </tr>
  <tr>
    <td>Regime Overlay</td>
    <td>Future: trend, range, high-volatility and low-volatility context labels.</td>
    <td>Static panel-card.</td>
    <td>Yalnız published feature/regime artifact ve as-of availability policy ile.</td>
  </tr>
</table>

# 4.2 V18de Bulunmayan Bileşenler

<table>
  <tr>
    <th>Bileşen türü</th>
    <th>V18 Future Dev görünümü</th>
    <th>Dokümantasyon / implementation sonucu</th>
  </tr>
  <tr>
    <td>Toolbar / filter / table</td>
    <td>Yok.</td>
    <td>Future Active UI tasarlanırken ayrı spec gerekir; bu sayfa uydurma filter veya table tanımlamaz.</td>
  </tr>
  <tr>
    <td>Modal / popup</td>
    <td>Yok.</td>
    <td>V18de capability activation veya operation modalı yoktur.</td>
  </tr>
  <tr>
    <td>ⓘ information button</td>
    <td>Yok.</td>
    <td>Bu sürümde bilgi butonu catalogu &quot;uygulanmaz&quot;dır; yeni info control yalnız ilgili future capability UI specinde eklenebilir.</td>
  </tr>
  <tr>
    <td>Input / select / checkbox / toggle</td>
    <td>Yok.</td>
    <td>Zorunlu alan veya payload formu yoktur.</td>
  </tr>
  <tr>
    <td>Success / error toast</td>
    <td>Yok.</td>
    <td>V18 local success/error üretmez; Production placeholder route da fake toast üretmez.</td>
  </tr>
  <tr>
    <td>Async progress</td>
    <td>Yok.</td>
    <td>No job exists in Placeholder state. Timer veya mock progress yasaktır.</td>
  </tr>
</table>

# 5. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen / capability state</th>
    <th>Varsayılan görünüm</th>
    <th>Aktifleşme / geçiş koşulu</th>
    <th>Disabled veya inactive iken etkisi</th>
    <th>Recovery / kullanıcı mesajı</th>
  </tr>
  <tr>
    <td>Future Dev dropdown</td>
    <td>Visible blue menu; hover dropdown.</td>
    <td>Top menu render edilir.</td>
    <td>No domain payload, no job, no persistence.</td>
    <td>N/A; navigation shell.</td>
  </tr>
  <tr>
    <td>Live Trade - Placeholder</td>
    <td>Normal menu label, no clickable handler.</td>
    <td>Capability registry Active/Limited + ayrı execution domain contractı olmadan route/command yok.</td>
    <td>Order submit/cancel/modify, broker adapter, execution session ve ledger başlatılamaz.</td>
    <td>&quot;Live Trade is not active in Production V1. No execution action is available.&quot;</td>
  </tr>
  <tr>
    <td>Graphic View - Placeholder</td>
    <td>Clickable static page; six future cards.</td>
    <td>V18 route always shows static overview. Production overview GET may render based on registry state.</td>
    <td>No chart request, View Dataset job, marker, live data or local config persistence.</td>
    <td>&quot;Graphic View is a controlled placeholder. No visual dataset has been prepared.&quot;</td>
  </tr>
  <tr>
    <td>Designed</td>
    <td>Read-only scope/dependency summary can be shown.</td>
    <td>Contract/version/dependencies designed but operation not released.</td>
    <td>Operation endpoint closed; no form submit.</td>
    <td>&quot;This capability is designed but not operational in this environment.&quot;</td>
  </tr>
  <tr>
    <td>Internal</td>
    <td>Clearly experimental/internal badge.</td>
    <td>Internal validation environment and test policy.</td>
    <td>Production user flow unavailable; isolated data only.</td>
    <td>&quot;Internal validation only. Output is not authoritative.&quot;</td>
  </tr>
  <tr>
    <td>Shadow</td>
    <td>Read-only output/comparison surface.</td>
    <td>Real data may be read under policy without affecting production decisions.</td>
    <td>No execution or canonical result mutation.</td>
    <td>&quot;Shadow output does not affect production decisions.&quot;</td>
  </tr>
  <tr>
    <td>Limited</td>
    <td>Explicit limited badge, eligibility/status/history/rollback note.</td>
    <td>Defined user/object scope, policy gate, audit and rollback contract.</td>
    <td>Out-of-scope callers cannot operate.</td>
    <td>&quot;This capability is available only to its approved limited scope.&quot;</td>
  </tr>
  <tr>
    <td>Active</td>
    <td>Normal operations UI and job feedback after future page spec is approved.</td>
    <td>All activation gates, API/job/event/test requirements pass; Admin lifecycle transition recorded.</td>
    <td>None beyond normal policy/validation.</td>
    <td>Normal capability-specific status messages.</td>
  </tr>
  <tr>
    <td>Retired</td>
    <td>Read-only history/migration explanation.</td>
    <td>Admin transition; no new command accepted.</td>
    <td>New work blocked; history/artifacts preserved.</td>
    <td>&quot;This capability is retired. Historical records remain read-only.&quot;</td>
  </tr>
</table>

# 6. Field Contract Matrix: Zorunluluk, Default ve Payload

<table>
  <tr>
    <th>Uygulanmaz - V18 form alanı yoktur<br/>Future Dev V18 placeholderında input, dropdown, toggle, checkbox, date selector, file upload veya submit control bulunmaz. Bu nedenle kullanıcı tarafından doldurulan * zorunlu alan yoktur. Capability state, route veya capability_key kullanıcı form fieldı değildir; server-side registryden okunur.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Alan / değer</th>
    <th>UI tipi / default</th>
    <th>Zorunluluk</th>
    <th>Production payload / source of truth</th>
    <th>Validation</th>
  </tr>
  <tr>
    <td>capability_key</td>
    <td>UIda gizli system identifier. V18 label/route ile dolaylı eşleşir.</td>
    <td>User input değildir.</td>
    <td>future_capability.capability_key; ör: graphic_view.</td>
    <td>Unique; immutable route mapping; client supplied value authority değildir.</td>
  </tr>
  <tr>
    <td>lifecycle_state</td>
    <td>Badge/overview state. V18de explicit badge yok; Graphic View static placeholderdır.</td>
    <td>User input değildir.</td>
    <td>future_capability.lifecycle_state server-side.</td>
    <td>Transition only allowed state graph + Admin policy.</td>
  </tr>
  <tr>
    <td>dependency_snapshot</td>
    <td>Placeholderda read-only conceptual dependency text.</td>
    <td>N/A.</td>
    <td>Server-side JSON snapshot.</td>
    <td>Active/Limited transitionde domain/data/policy/API/test/rollback gates complete olmalı.</td>
  </tr>
  <tr>
    <td>Graphic View cards</td>
    <td>Static panel-card list.</td>
    <td>N/A.</td>
    <td>No command payload; V18 static copy.</td>
    <td>Card wording operation varmış izlenimi vermemeli.</td>
  </tr>
  <tr>
    <td>Activation reason</td>
    <td>Future Admin lifecycle control surface; V18 Future Dev sayfasında yok.</td>
    <td>Transition commandde required.</td>
    <td>capability transition command body.</td>
    <td>Non-empty reason, expected state/version, Admin only.</td>
  </tr>
</table>

# 6.1 Conditional Requiredness ve Dependent-State Kuralları

<table>
  <tr>
    <th>Kural</th>
    <th>Ne zaman aktifleşir</th>
    <th>Zorunlu sonuç</th>
  </tr>
  <tr>
    <td>Activation reason *</td>
    <td>Admin lifecycle transition commandi gönderildiğinde.</td>
    <td>Boş reason ile transition reddedilir; auditte actor, from_state, to_state, reason ve timestamp tutulur.</td>
  </tr>
  <tr>
    <td>Dependency snapshot</td>
    <td>Designed, Internal, Shadow, Limited veya Active stateine geçerken.</td>
    <td>Domain/data/policy/UI/API/test/rollback bağımlılıkları snapshotta bulunur; Placeholder stateinde minimum metadata yeterlidir.</td>
  </tr>
  <tr>
    <td>Source manifest refs</td>
    <td>Graphic View View Dataset, Backtest Review, Signal Intelligence veya future metric artifact üretilirken.</td>
    <td>Immutable result/data/revision refs pinlenmeden job/analysis başlamaz.</td>
  </tr>
  <tr>
    <td>Method version</td>
    <td>Analysis Artifact veya Parameter/Regime experiment outputu üretilirken.</td>
    <td>Output reproducibility için zorunludur; UI texti veya free-form prompt tek başına method değildir.</td>
  </tr>
  <tr>
    <td>Allowed scope / policy</td>
    <td>Limited veya Active capability operationı çağrıldığında.</td>
    <td>Server caller role, owner/visibility, lifecycle state ve capability policyyi doğrular.</td>
  </tr>
</table>

# 7. Information Content Catalog, Placeholder, Warning ve Error Metinleri

V18de ⓘ düğmesi bulunmaz. Aşağıdaki metinler mevcut static placeholder copy ve Production V1de gerekli capability status/warning/error içerikleridir. Bu metinler doğrudan UIya yerleştirilebilir; ancak Placeholder stateinde sahte işlem sonucuna dönüşmez.

<table>
  <tr>
    <th>Key / konum</th>
    <th>Başlık</th>
    <th>Nihai UI metni</th>
    <th>Kullanım koşulu</th>
  </tr>
  <tr>
    <td>futureDevOverview.placeholder</td>
    <td>This capability is not active</td>
    <td>This capability is currently a controlled Future Dev placeholder. It does not generate operational data, background jobs, execution actions, or persistent production output. Activation requires a completed domain contract, data lineage, policy, API/worker, audit, rollback, and acceptance-test gate.</td>
    <td>Placeholder route overview.</td>
  </tr>
  <tr>
    <td>futureDevOverview.designed</td>
    <td>Designed, not operational</td>
    <td>The capability contract and dependencies are being defined. No operational command is available in this environment.</td>
    <td>Designed state.</td>
  </tr>
  <tr>
    <td>futureDevOverview.limited</td>
    <td>Limited capability</td>
    <td>This capability is active only for its approved limited scope. Eligibility, policy, history, and rollback information are shown before an operation can start.</td>
    <td>Limited state.</td>
  </tr>
  <tr>
    <td>futureDevGraphicView.placeholder</td>
    <td>Graphic View</td>
    <td>Graphic View is reserved for future chart and visual-review development. The page is intentionally a placeholder until the chart engine, event markers and structured visual datasets are implemented.</td>
    <td>V18 text; Placeholder state.</td>
  </tr>
  <tr>
    <td>futureDevDisabled.tooltip</td>
    <td>Not available</td>
    <td>This capability is planned but not active in Production V1. No operational command is available.</td>
    <td>Disabled/non-operational button or item.</td>
  </tr>
  <tr>
    <td>CAPABILITY_NOT_ACTIVE</td>
    <td>Capability not active</td>
    <td>This feature is not active in the current environment. No operation was started.</td>
    <td>Operation command attempted while state is below Limited/Active or policy does not allow it.</td>
  </tr>
  <tr>
    <td>CAPABILITY_DEPENDENCY_MISSING</td>
    <td>Activation blocked</td>
    <td>Activation is blocked because required domain, data, policy, API, test, or rollback dependencies are incomplete. Review the capability dependency record.</td>
    <td>Admin transition gate fails.</td>
  </tr>
  <tr>
    <td>CAPABILITY_STATE_STALE</td>
    <td>Capability state changed</td>
    <td>The capability state changed while this page was open. Refresh capability status before continuing.</td>
    <td>Stale client after registry transition.</td>
  </tr>
  <tr>
    <td>CAPABILITY_ACCESS_DENIED</td>
    <td>Permission denied</td>
    <td>You are not permitted to perform this capability operation or lifecycle transition.</td>
    <td>Role/policy check fails.</td>
  </tr>
  <tr>
    <td>futureDevNoHistory.empty</td>
    <td>No output history</td>
    <td>No output exists because this capability has not produced an operational artifact in the current state.</td>
    <td>Placeholder/Designed or empty Limited/Active history.</td>
  </tr>
</table>

# 8. Button / Command / State Contract

Future Dev V18 menüsünde gerçek domain mutation buttonu yoktur. Graphic View clicki bir V18 page switchidir; backend command değildir. Capability lifecycle transition, Future Dev shell içinde değil; future administrative management surfaceinde Admin-only server command olarak uygulanır. Aşağıdaki contract, UI ve Agent parity için gerçek Production davranışını tanımlar.

<table>
  <tr>
    <th>UI action / trigger</th>
    <th>Backend query or command</th>
    <th>Precondition</th>
    <th>State behavior</th>
    <th>Audit / idempotency</th>
  </tr>
  <tr>
    <td>Click Graphic View</td>
    <td>GET /api/v1/future-dev/graphic_view/overview or local V18 placeholder renderer.</td>
    <td>Route visible. Placeholder overview is allowed; no operation permission required for public policy view.</td>
    <td>Loading only for query. Placeholder result renders static explanation. No fake job.</td>
    <td>Read query may be access logged; no mutation audit.</td>
  </tr>
  <tr>
    <td>Select Live Trade / inactive submenu item</td>
    <td>No V18 command. No Live Trade order endpoint exists in V1 core scope.</td>
    <td>None.</td>
    <td>No-op in V18. A registered generic capability operation route, if invoked while inactive, returns CAPABILITY_NOT_ACTIVE; a direct Live Trade order endpoint is absent.</td>
    <td>No success toast; denial may be audit/logged.</td>
  </tr>
  <tr>
    <td>Refresh capability state</td>
    <td>GET /api/v1/capabilities and GET /api/v1/capabilities/{key}.</td>
    <td>Route allowed.</td>
    <td>Client can cache display state, but server rechecks state before command dispatch.</td>
    <td>Read trace optional; source of truth remains server.</td>
  </tr>
  <tr>
    <td>Admin lifecycle transition</td>
    <td>POST /api/v1/capabilities/{key}/lifecycle-transitions.</td>
    <td>Authenticated Admin + legal transition + expected_registry_version + reason + activation gates pass.</td>
    <td>Loading locks duplicate submit. Success returns canonical registry state. Failure returns structured issue list.</td>
    <td>CapabilityStateChanged event + immutable activation audit; idempotency key and expected registry version required.</td>
  </tr>
  <tr>
    <td>Future View Dataset request</td>
    <td>POST /api/v1/view-datasets/query - only when capability Limited/Active and contract exists.</td>
    <td>Allowed state, policy, pinned source refs, schema/version validation.</td>
    <td>Async or query state based on contract; Placeholder cannot start it.</td>
    <td>ViewDatasetPrepared event where applicable; source manifest refs pinned.</td>
  </tr>
  <tr>
    <td>Future Analysis Artifact request</td>
    <td>POST /api/v1/analysis-artifacts - only when relevant capability Limited/Active.</td>
    <td>Allowed state/policy; input manifest refs; method version; artifact contract.</td>
    <td>Durable job state, not UI timer.</td>
    <td>AnalysisArtifactCreated event; idempotency key; immutable output.</td>
  </tr>
</table>

# 9. Production Backend Behavior: Capability Registry, Event ve API Modeli

Production V1in ortak Future Dev çekirdeği, her capabilitynin aktif uygulaması değildir. Uygulanacak ortak altyapı Capability Registry, immutable capability activation eventleri ve gelecekteki artifact/view/experiment/execution contractlarına referans verebilen bir modeldir. Capability Registry, feature flag gibi yalnız frontendde yaşayan bir boolean olamaz.

<table>
  <tr>
    <th>Entity</th>
    <th>Temel alanlar</th>
    <th>Bugünkü V1 davranışı</th>
    <th>Future capabilityde rolü</th>
  </tr>
  <tr>
    <td>future_capability</td>
    <td>capability_key, lifecycle_state, ui_surface_version, domain_contract_version, dependency_snapshot, enabled_at, retirement_at, changed_by_actor_id, change_reason.</td>
    <td>Registry entry exists; baseline future keys Placeholder durumunda olabilir.</td>
    <td>Capabilitynin authoritative availability kaydı.</td>
  </tr>
  <tr>
    <td>capability_activation_event</td>
    <td>capability_key, from_state, to_state, actor, reason, timestamp, dependency snapshot/hash.</td>
    <td>Immutable audit event.</td>
    <td>Logs, User Manual update, UI cache invalidation and Agent Coordinator policy cache consume eder.</td>
  </tr>
  <tr>
    <td>analysis_artifact</td>
    <td>artifact_type, input_manifest_refs, method_version, output_ref, lifecycle, owner_actor.</td>
    <td>Future-only output root; no fake instance in Placeholder.</td>
    <td>Backtest Review, WFA, Monte Carlo, sensitivity vb.</td>
  </tr>
  <tr>
    <td>view_dataset</td>
    <td>source_manifest_refs, series/marker refs, range, schema_version.</td>
    <td>Future-only; no V1 Graphic View dataset creation while Placeholder.</td>
    <td>Renderer-independent Graphic View input.</td>
  </tr>
  <tr>
    <td>experiment_proposal</td>
    <td>hypothesis_ref, input bundle refs, parameter plan ref, status, acceptance criteria.</td>
    <td>Future-only; no Hypothesis Lab action in Placeholder.</td>
    <td>Hypothesis Lab / Parameter Fields bridge.</td>
  </tr>
  <tr>
    <td>execution_plan (future)</td>
    <td>strategy/portfolio/data refs, execution policy refs, lifecycle.</td>
    <td>Does not exist as active V1 live trading domain.</td>
    <td>Live Trade entry root when separately activated.</td>
  </tr>
</table>

# 9.1 Capability Lifecycle State Machine

<table>
  <tr>
    <th>State</th>
    <th>Meaning</th>
    <th>Allowed backend behavior</th>
    <th>Forbidden behavior</th>
  </tr>
  <tr>
    <td>Placeholder</td>
    <td>Roadmap/overview state; domain contract incomplete.</td>
    <td>GET overview/metadata. Static explanation.</td>
    <td>Any domain command, fake job, persistent output, real order, authoritative calculation.</td>
  </tr>
  <tr>
    <td>Designed</td>
    <td>Contract/dependencies/tests designed; operation implementation may not exist.</td>
    <td>GET metadata/dependency scope.</td>
    <td>Operational endpoint, user form submit or execution.</td>
  </tr>
  <tr>
    <td>Internal</td>
    <td>Internal validation in isolated environment.</td>
    <td>Sandbox/test workers and internal UI only.</td>
    <td>Production state mutation or ambiguity about authoritative status.</td>
  </tr>
  <tr>
    <td>Shadow</td>
    <td>Reads relevant real data without influencing production decisions.</td>
    <td>Non-authoritative artifact/comparison output.</td>
    <td>Execution, canonical result mutation, silent policy impact.</td>
  </tr>
  <tr>
    <td>Limited</td>
    <td>Controlled, policy-scoped operation.</td>
    <td>Defined user/object scope; audit; rollback; durable state.</td>
    <td>Open-ended general release or undefined eligibility.</td>
  </tr>
  <tr>
    <td>Active</td>
    <td>Complete production contract.</td>
    <td>Versioned API, worker/event, normal UI, logs/manual, capability-specific policy.</td>
    <td>UI-only mutation or server state bypass.</td>
  </tr>
  <tr>
    <td>Retired</td>
    <td>No new operation; historical access preserved.</td>
    <td>Read-only history, migration explanation, audit.</td>
    <td>New command acceptance or deletion of provenance history.</td>
  </tr>
</table>

# 9.2 Activation Gate Contract

- Domain boundary gate: readable roots/revisions/artifacts and any newly created entity must be defined before transition.

- Data contract gate: input data requires version pinning, available-time rules, coverage and quality conditions.

- Policy/lifecycle gate: Admin, Supervisor, User and Agent behavior; soft delete/audit/restore effects must be explicit.

- UI gate: placeholder, loading, empty, blocked, failed, completed and stale states must be implemented before Active release.

- Backend gate: versioned API, idempotent command/job behavior, durable events and structured error contract must exist.

- Verification gate: deterministic, integration and feature acceptance tests must pass.

- Rollback gate: Limited/Active failure behavior, downgrade state and historical artifact preservation must be specified.

# 10. Capability Cards: UI Meaning, Future Contract ve Non-Goals

## 10.1 Live Trade

Live Trade, Backtest RUN butonunun gerçek para kullanan varyasyonu değildir. Backtest Run geçmiş veri üzerinde deterministik simulation üretir; Live Trade gerçek zaman, data freshness, order acceptance, partial fill, rejection, external account state, broker adapter ve reconciliation gerektirir.

<table>
  <tr>
    <th>Future component</th>
    <th>Minimum active responsibility</th>
    <th>Non-goal / V1 boundary</th>
  </tr>
  <tr>
    <td>Execution Plan</td>
    <td>Pinned Strategy Revision, Package Revision, market data feed policy, portfolio mode and order intents.</td>
    <td>Backtest configurationdan otomatik canlı order türetmek.</td>
  </tr>
  <tr>
    <td>Execution Session</td>
    <td>Server-side durable long-lived session.</td>
    <td>Browser tab or local UI state.</td>
  </tr>
  <tr>
    <td>Broker/Venue Adapter</td>
    <td>Submission, acknowledgement, fill, cancel, reconciliation.</td>
    <td>Generic placeholder menu item.</td>
  </tr>
  <tr>
    <td>Order Ledger</td>
    <td>Immutable intent/sent/accepted/partially_filled/filled/rejected/cancelled event chain.</td>
    <td>Backtest trade tableyi gerçek execution ledger gibi kullanmak.</td>
  </tr>
  <tr>
    <td>Risk/Freshness Gate</td>
    <td>Data staleness, strategy revision, allocation and configuration consistency check.</td>
    <td>UIdan gelen fiyatla live decision üretmek.</td>
  </tr>
</table>

Future Dev Boundary: Production V1de Live Trade için broker adapter, order endpoint, execution session veya live market decision worker başlatılmaz. Capability Placeholder iken UI menu iteminin görünmesi hiçbir execution yan etkisi doğurmaz.

## 10.2 Graphic View

Graphic View visual review için merkezi future yüzeydir. Active sürümde renderer sadece View Dataset contractını tüketen adapter olmalıdır; chart library business logic, metric calculation veya backtest state taşımaz.

<table>
  <tr>
    <th>View Dataset bölümü</th>
    <th>Zorunlu içerik</th>
    <th>Immutable source</th>
  </tr>
  <tr>
    <td>Price Series</td>
    <td>Instrument, timeframe, OHLCV/tick ref, timezone, visible range.</td>
    <td>Pinned Market Data revision.</td>
  </tr>
  <tr>
    <td>Decision/Signal Markers</td>
    <td>Decision time, available input refs, action type, trigger reason, strategy item ref.</td>
    <td>Backtest Result signal events or future execution ledger.</td>
  </tr>
  <tr>
    <td>Order/Trade Markers</td>
    <td>Entry/exit/stop/scale, size, fill/model price, outcome.</td>
    <td>Trade ledger.</td>
  </tr>
  <tr>
    <td>Portfolio Curves</td>
    <td>Equity, drawdown, exposure, reserved cash, allocation context.</td>
    <td>Backtest Result / Portfolio Allocation snapshot.</td>
  </tr>
  <tr>
    <td>Regime Overlay</td>
    <td>Label, effective interval, source feature definition, confidence/evidence.</td>
    <td>Published Research Data feature / regime artifact.</td>
  </tr>
  <tr>
    <td>Chart View Config</td>
    <td>Panels, ranges, marker visibility, comparison selection.</td>
    <td>Separate user-scoped view preference root; never changes Result.</td>
  </tr>
</table>

## 10.3 AI Operations - Backtest Review

Backtest Review, immutable Backtest Result üzerindeki diagnostics verisini okunabilir, evidence-linked Review Artifacte dönüştürür. Review sonucu sonucu yeniden hesaplamaz veya "başarılı/başarısız" authoritative hükmü vermez.

<table>
  <tr>
    <th>Input</th>
    <th>Output</th>
    <th>Forbidden</th>
  </tr>
  <tr>
    <td>Pinned Backtest Result manifest, metrics, trade ledger, signal events, diagnostics, export refs.</td>
    <td>review_artifact: summary, findings, evidence links, limitation notes, follow-up hypothesis or experiment request.</td>
    <td>Net profit, trade ledger, canonical metric values or original run manifest mutation.</td>
  </tr>
  <tr>
    <td>Agent/Lab Assistant request or scheduled review job after activation.</td>
    <td>Versioned review revision and attached evidence map.</td>
    <td>Direct package publish, strategy mutation or live execution from free-form review text.</td>
  </tr>
</table>

## 10.4 AI Operations - Signal Intelligence

Signal Intelligence, signal eventlerini geniş ölçekte sınıflandırır ve araştırmaya açar. Entry/exit kararı vermez; mevcut Strategy Details condition bloklarını gizli biçimde değiştirmez.

<table>
  <tr>
    <th>Component</th>
    <th>Minimum active contract</th>
  </tr>
  <tr>
    <td>Signal event corpus</td>
    <td>Pinned run or selected period ledger; each event retains strategy/package revision, decision time and instrument scope.</td>
  </tr>
  <tr>
    <td>Signal label set</td>
    <td>Versioned label definitions for pattern, co-occurrence, regime, outcome bucket or anomaly.</td>
  </tr>
  <tr>
    <td>Intelligence artifact</td>
    <td>Immutable output containing coverage, method version, label distribution, evidence examples and limitations.</td>
  </tr>
  <tr>
    <td>Follow-up bridge</td>
    <td>Only opens a Hypothesis Lab proposal; never performs automatic Strategy edit.</td>
  </tr>
</table>

## 10.5 Research - Regime Research, Hypothesis Lab ve Parameter Fields

<table>
  <tr>
    <th>Capability</th>
    <th>Future purpose</th>
    <th>Input/output contract</th>
    <th>Hard boundary</th>
  </tr>
  <tr>
    <td>Regime Research</td>
    <td>Separately study trend/range, volatility, liquidity or other market context.</td>
    <td>Approved Market/Research Data revisions + method; outputs regime_artifact or versioned Feature Definition.</td>
    <td>Not &quot;trade now&quot; signal. Strategy use only through published feature definition + available-time/as-of policy.</td>
  </tr>
  <tr>
    <td>Hypothesis Lab</td>
    <td>Turn human/Agent research idea into repeatable hypothesis-to-experiment lifecycle.</td>
    <td>Hypothesis root/artifact, evidence refs, experiment proposal and acceptance criteria.</td>
    <td>Does not replace Analysis Lab or interrupt Alpha Agent continuous task.</td>
  </tr>
  <tr>
    <td>Parameter Fields</td>
    <td>Define controlled parameter search-space and sensitivity experiment plans.</td>
    <td>Parameter definition/range/baseline, experiment policy, result surface; outputs candidate configuration, experiment request or revision request.</td>
    <td>Never silently overwrites active Strategy Details parameters.</td>
  </tr>
</table>

## 10.6 Future Version Metrics Boundary

V18 Arrange Metrics içinde Sharpe Ratio, Sortino Ratio, Recovery Factor, Robustness Test, Monte Carlo Result, Walk-Forward Result, Out of Sample Result, Average Trade, Average Holding Time, Consecutive Losses, Exposure, Long / Short Distribution, Monthly Return, Timeframe Sensitivity, Regime Sensitivity, Parameter Stability, Slippage Sensitivity ve Commission Sensitivity future-only görünür. Bu görünürlük, mevcut Backtest Resultın canonical alanlarına bu değerlerin hesaplandığı anlamına gelmez.

<table>
  <tr>
    <th>Metric/analysis type</th>
    <th>Doğru gelecek model</th>
    <th>Neden mevcut Result UIya basitçe eklenmez</th>
  </tr>
  <tr>
    <td>Ledger-derived metric</td>
    <td>Metric Registry formula + required fields + metric definition version.</td>
    <td>Formula, denominator/netting and evidence must be explicit.</td>
  </tr>
  <tr>
    <td>Distribution/time metric</td>
    <td>Result Metric Extension from pinned trade/equity ledger.</td>
    <td>Timezone, holding interval and fill model context must be preserved.</td>
  </tr>
  <tr>
    <td>Sensitivity metric</td>
    <td>New analysis/experiment job + Analysis Artifact.</td>
    <td>Timeframe/slippage/commission scenarios require new run evidence.</td>
  </tr>
  <tr>
    <td>Monte Carlo/WFA/OOS</td>
    <td>Analysis Artifact with method version, random seed/split policy and input run set.</td>
    <td>These are validation procedures, not one extra Result metric.</td>
  </tr>
</table>

# 11. Agent Tool/API Eşdeğeri ve Süreklilik Sınırı

Agent, Future Dev menu itemlerini tıklayan UI bot değildir. Agent Coordinator, Capability Registryden yalnız Active veya policy ile izinli Limited capabilitylerin tool contractını alır. Placeholder ve Designed capabilityler Agent tool registryye hiç eklenmez; Agent böyle bir yetenek varmış gibi plan yapmaz.

<table>
  <tr>
    <th>Capability</th>
    <th>Agentın izinli rolü aktifleştiğinde</th>
    <th>Agentın izinli olmadığı davranış</th>
  </tr>
  <tr>
    <td>Graphic View</td>
    <td>View Dataset request veya existing result visual evidence reference oluşturmak.</td>
    <td>Chart üzerinden Strategy state veya Backtest Result değiştirmek.</td>
  </tr>
  <tr>
    <td>Backtest Review</td>
    <td>Review artifact draft/analysis job başlatmak ve evidence bağlamak.</td>
    <td>Canonical metrics veya trade ledger mutation.</td>
  </tr>
  <tr>
    <td>Signal Intelligence</td>
    <td>Signal corpus üzerinde label/research artifact üretmek.</td>
    <td>Signal event silmek veya entry conditionı otomatik rewrite etmek.</td>
  </tr>
  <tr>
    <td>Regime Research</td>
    <td>Research Data/Feature pipeline ile regime artifact üretmek.</td>
    <td>Raw Research Data doğrudan trading triggera bağlamak.</td>
  </tr>
  <tr>
    <td>Hypothesis Lab</td>
    <td>Hypothesis/experiment proposal oluşturmak; safe checkpointte directive tüketmek.</td>
    <td>Human approval/publish yerine geçmek.</td>
  </tr>
  <tr>
    <td>Parameter Fields</td>
    <td>Experiment request ve sensitivity artifact üretmek.</td>
    <td>Active Strategy configini silently overwrite etmek.</td>
  </tr>
  <tr>
    <td>Live Trade</td>
    <td>Ayrı capability/policy oluşana kadar hiçbir execution actionı yoktur.</td>
    <td>Order submit/cancel/modify.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Süreklilik ilkesi<br/>Bir future capability ileride Agent veya worker işi başlatırsa iş server-side queue/worker, checkpoint, artifact store ve durable event stream üzerinde sürer. Browser kapanması, Future Dev pagein kapanması veya insanın yeni bir chat mesajı göndermesi işi durduramaz. Placeholder stateinde ise Agent için iş yoktur; fake agent task üretilmez.</th>
  </tr>
</table>

# 12. Validation, Error ve Recovery Contract

<table>
  <tr>
    <th>Katman</th>
    <th>Validation / error</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>Lifecycle</td>
    <td>Illegal transition, missing reason, missing dependency snapshot, non-Admin actor.</td>
    <td>Return structured CAPABILITY_TRANSITION_REJECTED or CAPABILITY_ACCESS_DENIED; show current state and blocking gates.</td>
  </tr>
  <tr>
    <td>Stale concurrency</td>
    <td>Client expected_registry_version eski; state page open iken değişti.</td>
    <td>Return CAPABILITY_STATE_STALE; refresh canonical registry state; do not retry blindly.</td>
  </tr>
  <tr>
    <td>Dependency</td>
    <td>Source revisions, quality/coverage, available-time, policy, test or rollback gate missing.</td>
    <td>Return CAPABILITY_DEPENDENCY_MISSING with per-gate issue list and owning module link.</td>
  </tr>
  <tr>
    <td>Inactive operation</td>
    <td>Command called for Placeholder/Designed/Retired or policy-disallowed state.</td>
    <td>Return CAPABILITY_NOT_ACTIVE; do not create job/output; Agent records blocker or selects active alternative.</td>
  </tr>
  <tr>
    <td>Job failure - future active state</td>
    <td>Worker fails after command accepted.</td>
    <td>Persist failed job/event with input manifest, error classification, retry eligibility and no partial authoritative mutation.</td>
  </tr>
  <tr>
    <td>Authorization</td>
    <td>UI item visible but server policy denies route/command.</td>
    <td>Return CAPABILITY_ACCESS_DENIED; never disclose protected output via frontend filtering alone.</td>
  </tr>
  <tr>
    <td>Reference integrity</td>
    <td>View/Analysis request source Result/Data/Feature ref is soft-deleted, inaccessible, incompatible or not pinned.</td>
    <td>Block request; present source status; use restore/alternate permitted revision flow.</td>
  </tr>
</table>

# 13. Lifecycle, Audit, Trash ve Historical Integrity

Future Dev Placeholder stateinde user-generated operational output yoktur; bu nedenle normal browsing Graphic View V18de Trash entry, Result mutation veya artifact history üretmez. Buna karşılık Capability Registry transitionları immutable audit olayıdır. Gelecekte capability Active/Limited olduğunda üretilen View Dataset, Analysis Artifact, Experiment Proposal veya execution outputları normal lifecycle, audit ve soft-delete kurallarına girer.

<table>
  <tr>
    <th>Nesne / olay</th>
    <th>Lifecycle / audit kuralı</th>
    <th>Trash etkisi</th>
  </tr>
  <tr>
    <td>future_capability</td>
    <td>Registry entry lifecycle state ile yönetilir. Retirement, capabilityyi Trash yerine Retired stateine alır; registry lineage korunur.</td>
    <td>Normal UI soft delete yerine Retired/migration; capability recordi rastgele silinmez.</td>
  </tr>
  <tr>
    <td>capability_activation_event</td>
    <td>Immutable audit event; actor, state transition, reason, timestamp, dependency snapshot/hash tutulur.</td>
    <td>Trasha taşınmaz; historical audit korunur.</td>
  </tr>
  <tr>
    <td>Placeholder Graphic View visit</td>
    <td>Read/query only. No mutation.</td>
    <td>Trash etkisi yok.</td>
  </tr>
  <tr>
    <td>Future analysis/view/experiment output</td>
    <td>Root/revision/artifact lifecycle; source immutable refs ve owner/provenance tutulur.</td>
    <td>Soft delete sonrası Trash record oluşur; restore/permanent delete yalnız Admin.</td>
  </tr>
  <tr>
    <td>Source Backtest Result/Data Revision</td>
    <td>Future view/analysis yalnız reference verir; original sourceyi mutate etmez.</td>
    <td>Source soft-deleted/inaccessible ise new operation blocked; historical manifests preserved.</td>
  </tr>
</table>

# 14. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Başlık</th>
    <th>Ayrım</th>
  </tr>
  <tr>
    <td>V18 Interface Behavior</td>
    <td>Future Dev mavi dropdown olarak görünür. Live Trade, Backtest Review, Signal Intelligence, Regime Research, Hypothesis Lab ve Parameter Fields yalnız navigation labelsidir. Graphic View clickable static page açar; price/equity/drawdown/exposure/distribution/regime kartları placeholder copy taşır. V18de capability badge, registry query, lifecycle control, server job, real chart veya operation formu yoktur.</td>
  </tr>
  <tr>
    <td>Production Backend Behavior</td>
    <td>Capability Registry server-side source of truth olur. Placeholder/Designed stateinde operation command, fake job, persistent core entity, live order, authoritative chart/result mutation kabul edilmez. Admin-only lifecycle transitions are audited. Agent tool gateway only exposes Limited/Active capability contracts. Future Active capabilityler immutable source refs, versioned API, durable jobs/events, policy and acceptance gates ile gelir.</td>
  </tr>
  <tr>
    <td>Implementation Alignment Note</td>
    <td>V18 navigation labels and Graphic View visual placeholder korunur. Static page shell, server-returned capability overview ile hizalanır; active statee geçmeden statik cardlar gerçek dataset/metric varmış gibi render edilmez. Inactive menu itemleri no-op veya disabled explanatory behavior taşıyabilir; command dispatch server capability/policy check olmadan yapılmaz.</td>
  </tr>
</table>

# 15. Kodcu AI İçin Implementation Rules

- Future Dev altındaki hiçbir başlığı yalnız menu labelı görünür diye active domain olarak implement etme; Capability Registry stateini server-side kontrol et.

- Placeholder ekranlarda localStorage, mock success, fake progress, random result, sahte chart data veya kalıcı demo object üretme. Read-only static explanation yeterlidir.

- Yeni capability için geliştirme sırası: domain root/revision/artifact modeli -> policy/lifecycle -> API/job/event contract -> UI surface -> Agent tool contract -> tests/manual/logs.

- Capability Registry yalnız frontend feature flagi değildir. lifecycle_state, contract/dependency versionları, transition actor/reason ve eventler server-side persistence içinde tutulur.

- Capability lifecycle transitionı yalnız Admin çalıştırır. Supervisor, User veya Agent direct API ile bypass edemez.

- Backtest Result, Strategy Revision, Package Revision, Market Data Revision ve Research Data Revision immutable source nesneleridir. Future visualization/analysis bunları mutate etmez; pinned reference kullanır.

- Graphic View rendererı View Dataset adapterı olmalıdır. Chart library business logic, metric calculation, signal generation veya backtest state taşımaz.

- Live Tradei Backtest RUN butonunun varyasyonu olarak kodlama. Ayrı execution_plan, execution_session, broker adapter, order ledger, risk/freshness gate ve reconciliation domaini gerektirir.

- Backtest Review veya Signal Intelligence outputu canonical resultın yerine geçmez. Outputlar evidence-linked immutable artifact olarak saklanır.

- Regime Research outputu raw Research Data olarak trading triggera bağlanmaz. Published feature definition, available-time and as-of join policy zorunludur.

- Parameter Fields sonucu active Strategy Details stateini in-place değiştiremez. Yalnız candidate configuration, experiment request veya new Strategy Revision request üretir.

- Future Version Metricsi Result UIya basit checkbox/formula olarak ekleme. Metric Registry veya Analysis Artifact modelini, input evidence ve method versionını pinle.

- Client cachede lifecycle state olsa bile command dispatch öncesi server state/policy yeniden doğrulanmalıdır. expected_registry_version ve idempotency key kullan.

- Agent Placeholder/Designed capability için tool almamalıdır. Agent UIya tıklamayacak; yalnız Active/Limited Tool Gateway contractını kullanacaktır.

- Capability activation/deactivation Panel Logs ve User Manual akışına audit/documentation bağlanmadan tamam sayılmaz.

# 16. Acceptance Tests

<table>
  <tr>
    <th>ID</th>
    <th>Senaryo</th>
    <th>Beklenen sonuç</th>
  </tr>
  <tr>
    <td>FD-01</td>
    <td>Placeholder capability route açılır.</td>
    <td>Purpose/dependency explanation görünür; mutation command, fake progress, fake success veya persistent output yoktur.</td>
  </tr>
  <tr>
    <td>FD-02</td>
    <td>Client eski cached state ile inactive capability için POST yollar.</td>
    <td>Server capability state/policy check ile reddeder; CAPABILITY_NOT_ACTIVE döner; job/output oluşmaz; relevant denial/log kaydı üretilir.</td>
  </tr>
  <tr>
    <td>FD-03</td>
    <td>Graphic View Placeholder iken route açılır.</td>
    <td>Yalnız static overview/cards görünür; market data stream, chart worker, custom renderer job veya view dataset preparation başlamaz.</td>
  </tr>
  <tr>
    <td>FD-04</td>
    <td>Graphic View Limited/Active iken Backtest Result seçilir.</td>
    <td>View Dataset exact result/market references ile hazırlanır; chart config or result view manifest/result stateini değiştirmez.</td>
  </tr>
  <tr>
    <td>FD-05</td>
    <td>Backtest Review artifact tamamlanır.</td>
    <td>Review evidence references ile ayrı immutable artifact olur; canonical metrics/trade ledger/original run manifest değişmez.</td>
  </tr>
  <tr>
    <td>FD-06</td>
    <td>Signal Intelligence label set üretir.</td>
    <td>Output versioned intelligence artifact olur; Strategy Details condition blokları otomatik değişmez.</td>
  </tr>
  <tr>
    <td>FD-07</td>
    <td>Regime Research outputu Strategyde kullanılmak istenir.</td>
    <td>Yalnız published Feature Definition ve available-time/as-of policy Ready Checkten geçerse kullanılır; raw research trigger blocked.</td>
  </tr>
  <tr>
    <td>FD-08</td>
    <td>Parameter Fields experiment sonucu baseline Strategyden farklıdır.</td>
    <td>New candidate configuration, experiment proposal veya revision request oluşur; active Strategy in-place değişmez.</td>
  </tr>
  <tr>
    <td>FD-09</td>
    <td>Future metric WFA veya Monte Carlo seçilir.</td>
    <td>Analysis Artifact method/split/random seed/input refs ile çalışır; mevcut immutable Backtest Resulta sonradan authoritative metric yazılmaz.</td>
  </tr>
  <tr>
    <td>FD-10</td>
    <td>Agent Placeholder capabilityyi kullanmaya çalışır.</td>
    <td>Coordinator/tool registry capabilityyi sunmaz; Agent deterministic blocker/alternative plan üretir; no UI automation.</td>
  </tr>
  <tr>
    <td>FD-11</td>
    <td>Capability Active -&gt; Retired transitionı yapılır.</td>
    <td>Yeni commandler reject edilir; historical artifacts/read-only history korunur; transition Admin audit eventini taşır.</td>
  </tr>
  <tr>
    <td>FD-12</td>
    <td>Live Trade menu item visible while Placeholder.</td>
    <td>Broker adapter, order endpoint, execution session, external account mutation veya order ledger start edilemez.</td>
  </tr>
  <tr>
    <td>FD-13</td>
    <td>Non-Admin lifecycle transition API çağrısı yapar.</td>
    <td>Server denies; no state transition; CAPABILITY_ACCESS_DENIED + audit-relevant denial.</td>
  </tr>
  <tr>
    <td>FD-14</td>
    <td>Admin transition reason olmadan veya incomplete gates ile Active yapmayı dener.</td>
    <td>Validation rejects with per-gate issue list; canonical lifecycle state değişmez.</td>
  </tr>
  <tr>
    <td>FD-15</td>
    <td>Browser tabı kapatılırken future active analysis job çalışmaktadır.</td>
    <td>Durable worker/job/event state devam eder; browser close jobı durdurmaz. Placeholder stateinde job zaten başlatılamaz.</td>
  </tr>
</table>

# 17. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 - Modül 18 ve CR-08/CR-09 uyumu</td>
    <td>Evet. Future Dev controlled capability boundarydir; lifecycle transitions Admin-only; inactive capability gerçek endpoint/job/core output üretmez.</td>
  </tr>
  <tr>
    <td>V18 prototype / Production V1 ayrımı</td>
    <td>Evet. V18 static menu/card behavior ile production registry/policy/API sınırı ayrı yazılmıştır.</td>
  </tr>
  <tr>
    <td>Placeholderın aktif işlev gibi anlatılması</td>
    <td>Hayır. Her capability için inactive/activation boundary, no fake job/data/order kuralı açık yazılmıştır.</td>
  </tr>
  <tr>
    <td>Agent sürekli çalışma ilkesi</td>
    <td>Evet. Agent UI bot değildir; Placeholder tool almaz; future Active joblar durable backendde sürer.</td>
  </tr>
  <tr>
    <td>Run/Result mutability</td>
    <td>Evet. Future visual/review/analysis immutable source refs kullanır; canonical Resultı mutate etmez.</td>
  </tr>
  <tr>
    <td>Trash/audit</td>
    <td>Evet. Registry transition eventleri immutable audit; future outputs normal soft delete/Trash policyye tabidir; restore/permanent delete Admin-onlydir.</td>
  </tr>
  <tr>
    <td>ⓘ information content</td>
    <td>Uygulanmaz. V18de Future Dev üzerinde ⓘ control yoktur; absence açıkça kaydedilmiştir.</td>
  </tr>
  <tr>
    <td>Field requiredness</td>
    <td>Uygulanmaz. V18de user-editable field yoktur; future activation reason ve gates server command contractında conditionally required olarak tanımlanmıştır.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Teslim sonucu<br/>Future Dev sayfası, aktif bir live-trading veya chart/AI/research modülü değil; server-side Capability Registry ile yönetilen kontrollü bir genişleme yüzeyidir. V18deki Graphic View statik placeholderı korunur. Yeni capability ancak ayrı domain/API/worker/policy/audit/test sözleşmesi tamamlandığında, Admin lifecycle transitionı ile Limited veya Active duruma alınabilir.</th>
  </tr>
</table>
