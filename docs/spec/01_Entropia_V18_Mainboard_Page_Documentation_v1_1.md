---
title: "Entropia V18 — Mainboard Page Documentation v1.1"
page_number: 1
document_type: "Page implementation specification"
source_document: "Entropia_V18_Mainboard_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Mainboard Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18  |  PAGE DOCUMENTATION  |  MAINBOARD
> **Original DOCX footer:** Entropia V18 | Mainboard | Page  of

# MAINBOARD

*Sayfa Dokümantasyonu [1/22] | Entropia V18 | Production V1 implementation specification*

<table>
  <tr>
    <th>BELGE AMACI<br/>Bu doküman Mainboard görünümünü yalnız bir satır listesi olarak değil; Strategy, Trading Signal ve Trade Log çalışma nesnelerini birleştiren, sürümleri sabitleyen, Ready Check ve Backtest Run için tekrarlanabilir giriş oluşturan kalıcı çalışma kompozisyonu olarak tanımlar. HTML prototipin görünür davranışı ile Production V1 server-side doğrusu açıkça ayrıştırılmıştır.</th>
  </tr>
</table>

# Document Control

<table>
  <tr>
    <th>Alan</th>
    <th>Değer</th>
  </tr>
  <tr>
    <td>Belge adı</td>
    <td>Entropia V18 — Mainboard Page Documentation</td>
  </tr>
  <tr>
    <td>Belge kodu</td>
    <td>ENT-V18-PG-01-MAINBOARD</td>
  </tr>
  <tr>
    <td>Sürüm</td>
    <td>v1.1</td>
  </tr>
  <tr>
    <td>Kapsam</td>
    <td>Mainboard çalışma kompozisyonu; satır hostu; Ready Check/RUN entrypoint; Mainboard altındaki en güncel Result summary projection.</td>
  </tr>
  <tr>
    <td>Kapsam dışı</td>
    <td>Strategy Details alanlarının tam sözleşmesi; Add Outsource Signal form ayrıntıları; Trading Signal ve Trade Log detay şemaları; Add Package/Create Package detayları; Portfolio / Equity Allocation formu; Result detail/History. Bunlar kendi sayfa dokümanlarında canonical kaynaklarına dayanarak ayrıntılanacaktır.</td>
  </tr>
  <tr>
    <td>Kaynak önceliği</td>
    <td>1) Master Technical Reference v1.0, 2) V18 ana HTML, 3) Handoff v1.1, 4) 2.3 POSITION ENTRY LOGIC örneği.</td>
  </tr>
  <tr>
    <td>Kural dili</td>
    <td>Master’daki kararlar Canonical Rule olarak uygulanır. Master’ın boşluk bıraktığı teknik yönler açıkça Implementation Decision — Non-Canonical Gap Resolution etiketiyle ayrılır.</td>
  </tr>
  <tr>
    <td>Teslim sınırı</td>
    <td>Bu belge yalnız Mainboard sayfasını kapsar; başka sayfa için ayrı DOCX üretilmez.</td>
  </tr>
</table>

# Kaynak İzlenebilirliği ve Sayfa Sınırı

<table>
  <tr>
    <th>Kaynak</th>
    <th>İlgili bölüm / UI referansı</th>
    <th>Bu belgede kullanım</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0</td>
    <td>Modül 0 §§2–9; Modül 1 §§5–8; Modül 2 root/revision/lifecycle; Modül 3 soft delete/Trash/audit; Modül 7–8 package kaynak ayrımı; Modül 9 Mainboard ve Çalışma Nesneleri; Modül 10 host/dependency sınırı; Modül 11 allocation bağı; Modül 12 Ready Check/Run; Modül 13 Result summary; Modül 19 API ve async altyapı sınırı; CR-01, CR-09.</td>
    <td>Production V1 domain, authorization, lifecycle, revision pinning, snapshot, Ready/Run, Agent ve audit davranışının tek canonical kaynağı.</td>
  </tr>
  <tr>
    <td>V18 ana HTML</td>
    <td>DOM: `#mainboardView`, `#strategyList`, `#resultsSection`, `#resultsList`, `#backtestReadyStatus`, `#runButton`; actions: `showMainboard`, `addStrategyBox`, `addSignalPackageBox`, `addTradeLogBox`, `showAddPackagePanel`, `runBacktestReadyCheck`, `addBacktestResult`, `moveMainboardItemToTrash`.</td>
    <td>Kullanıcının prototipte gördüğü menu, row, popover, modal, görünürlük, label ve local interaction hedefini doğrular. Server-side doğrusu değildir.</td>
  </tr>
  <tr>
    <td>Handoff v1.1</td>
    <td>Sections 2–10; Field Contract, Interaction State Matrix, Content Catalog, command/recovery, lifecycle/audit, implementation rules ve acceptance tests.</td>
    <td>Bu belgenin zorunlu üretim yapısı ve QA standardı.</td>
  </tr>
  <tr>
    <td>2.3 POSITION ENTRY LOGIC örneği</td>
    <td>Kavram tanımı, nested state, typed payload, validation, deterministic engine ve Agent parity anlatım biçimi.</td>
    <td>Derinlik ve anlatım örneği. Mainboard domain kararlarını override etmez.</td>
  </tr>
</table>

<table>
  <tr>
    <th>SCOPE BOUNDARY<br/>Mainboard, içindeki Strategy Details veya external-object editörlerini host edebilir. Ancak host etmesi, bu iç panellerin alan sözleşmelerinin Mainboard tarafından tanımlandığı anlamına gelmez. Bu belge Mainboardun satır/kompozisyon/snapshot/ready/run sorumluluğunu; sonraki sayfa belgeleri ise ilgili detay panelin form ve domain sorumluluğunu tanımlar.</th>
  </tr>
</table>

# 1. Amaç ve Sistem İçindeki Yer

Mainboard, Entropia içindeki aktif çalışma kompozisyonudur. Kullanıcı veya Agent burada test edilmek istenen Strategy, Trading Signal ve Trade Log çalışma nesnelerini aynı board altında toplar; her nesnenin hangi immutable revision’ının kullanılacağını sabitler; kompozisyonun çalıştırılabilirliğini Ready Check ile doğrular ve yalnız doğrulanmış snapshot üzerinden Backtest Run başlatır.

Mainboard bir Package Library değildir; bir package kataloğu değildir; tarayıcı sekmesinin geçici satır listesi değildir; backtest worker değildir; Agent’ın sürekli araştırma döngüsünün tek çalışma alanı değildir; Backtest Result arşivi değildir. Mainboardda görünen result satırı yalnız immutable Result artifactine giden read-only özet projeksiyondur.

## 1.1 Araştırma ve Backtest Zincirindeki Konumu

<table>
  <tr>
    <th>Hypothesis / Research Task<br/>  -&gt; Strategy | Trading Signal | Trade Log work object<br/>  -&gt; Mainboard Composition (pinned revisions + order + enabled state)<br/>  -&gt; Immutable Composition Snapshot + Ready Check Report<br/>  -&gt; Backtest Run (queued worker job)<br/>  -&gt; succeeded only: Backtest Result + ledger + curves + diagnostics<br/>  -&gt; Results History / Agent interpretation / next task</th>
  </tr>
</table>

## 1.2 Kanonik Kavramlar

<table>
  <tr>
    <th>Terim</th>
    <th>Canonical anlam</th>
    <th>Mainboard sonucu</th>
  </tr>
  <tr>
    <td>Mainboard Workspace</td>
    <td>Bir actorun aktif çalışma kompozisyonunu taşıyan kalıcı root nesnesi.</td>
    <td>V1 UI yalnız Default Mainboardu gösterir; schema human_default, agent_research ve system workspace türlerine hazırdır.</td>
  </tr>
  <tr>
    <td>Mainboard Item</td>
    <td>Board içindeki tek satır; Work Object rootuna ve exact revisiona bağlanan composition kaydı.</td>
    <td>Kendi başına Strategy payloadı taşımaz; row adı veya sıra kimlik değildir.</td>
  </tr>
  <tr>
    <td>Work Object</td>
    <td>Strategy, Trading Signal veya Trade Logun kalıcı root nesnesi.</td>
    <td>İçeriği immutable revisionlarda yaşar; Mainboard yalnız referans/pin taşır.</td>
  </tr>
  <tr>
    <td>Pinned Revision</td>
    <td>Itemin Ready Check ve Backtestte kullanacağı exact immutable revision.</td>
    <td>“Latest revision” otomatik kullanılmaz.</td>
  </tr>
  <tr>
    <td>Transient Draft</td>
    <td>Henüz root/revision haline gelmemiş UI veya client taslağı.</td>
    <td>Görünür olabilir; Ready Check/RUN manifestine giremez; discard edildiğinde Trash oluşmaz.</td>
  </tr>
  <tr>
    <td>Composition Snapshot</td>
    <td>Enabled, persisted itemler ile ortak sermaye/run bağlamının server-side immutable manifesti.</td>
    <td>Ready Check reportu ve Run, aynı composition hash ile bu snapshot üzerinden çalışır.</td>
  </tr>
  <tr>
    <td>Ready Check Report</td>
    <td>Belirli snapshot/fingerprint için immutable preflight sonucu.</td>
    <td>Boolean değildir; change sonrası STALE olur.</td>
  </tr>
  <tr>
    <td>External Work Object</td>
    <td>Trading Signal veya Trade Log gibi harici source/event/import sözleşmesi taşıyan çalışma nesnesi.</td>
    <td>Package type değildir; Add Outsource Signal altında üretilir.</td>
  </tr>
  <tr>
    <td>Result Summary Projection</td>
    <td>Mainboard altında gösterilen, en güncel succeeded Resulta bağlı kısa read-only görünüm.</td>
    <td>Yeni Mainboard item değildir; mevcut Mainboard state’inden metrik hesaplamaz.</td>
  </tr>
</table>

<table>
  <tr>
    <th>CANONICAL RULE — MODÜL 9 / CR-01<br/>Mainboard item kind enumu yalnız `strategy`, `trading_signal` ve `trade_log` değerlerini taşır. Trading Signal ve Trade Log, Package Library package type değildir; Add Outsource Signal altında oluşan external Mainboard Working Item’larıdır.</th>
  </tr>
</table>

## 1.3 Sayfa Erişim Noktaları

• Primary navigation: Üst menüdeki Mainboard alanı Mainboard workspaceini tekrar görünür yapar.

• Mainboard menu actions: Add Strategy, Add Outsource Signal > Trading Signal, Add Outsource Signal > Trade Log, Add Package ve Portfolio / Equity Allocation girişleri.

• Deep links / server routes: Yetkili kullanıcı doğrudan Mainboard routeuna gelse bile backend list/detail policy uygulanır; UI menu görünürlüğü tek başına izin kanıtı değildir.

• Agent path: Agent, Mainboard UI’yi açmadan aynı composition command/API yeteneklerine Tool Gateway üzerinden erişir.

# 2. Erişim, Görünürlük, Sahiplik ve Policy

Mainboard görünürlüğü, bir Work Objecti görme, onu kullanma, boarda attach etme, yeni revision üretme, silme, restore etme ve RUN başlatma aynı yetki değildir. Her requestte principal, operation, resource owner, visibility, lifecycle, dependency ve active job state server-side yeniden değerlendirilir.

<table>
  <tr>
    <th>Principal / rol</th>
    <th>Mainboard görünümü</th>
    <th>View / use / attach</th>
    <th>Create / edit / delete</th>
    <th>Trash / restore</th>
    <th>Agent ve oturum notu</th>
  </tr>
  <tr>
    <td>Guest / anonymous</td>
    <td>Tanıtım veya restricted state; private composition listesi gösterilmez.</td>
    <td>Kalıcı resource view/use/attach yapamaz.</td>
    <td>Create/edit/delete/Ready/Run yapamaz.</td>
    <td>Yok.</td>
    <td>V18 demo “guest | User” gösterse bile Productionda anonymous, registered User değildir.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Kendi + explicitly shared/published sistem kaynaklarıyla çalışma alanı.</td>
    <td>Gördüğü/izinli Strategy Package veya external sourceu policyye uygun use/derive/attach edebilir.</td>
    <td>Kendi Work Objectlerini create/edit/soft delete eder; başkasının normal objectini mutate/delete edemez.</td>
    <td>Yok.</td>
    <td>Human authenticated session gerekir.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Shared working scope ve erişilebilir nesneler.</td>
    <td>Erişilebilir kaynakları kendi outputunda use/derive/attach edebilir.</td>
    <td>Kendi Work Objectlerini create/edit/soft delete eder; başka owner rootunu edit/delete edemez.</td>
    <td>Yok.</td>
    <td>Queued directive gönderebilir; bu Agentın aktif işini anında kesmez.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm erişilebilir workspace ve nesneler.</td>
    <td>Tüm uygun kaynakları view/use/attach eder.</td>
    <td>Admin override ile Work Object yönetir; lifecycle/dependency blockerlarını yine atlayamaz.</td>
    <td>Yalnız Admin Trash görür, restore/purge başlatır.</td>
    <td>Role ve system configuration yetkileri Mainboard yetkisinden ayrıdır.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Human UI zorunlu değildir; gerekli görünür state mevcut olabilir.</td>
    <td>Allowed system working content ve policy izinli shared/published kaynaklarla server-side composition kurar.</td>
    <td>Kendi outputlarını create/revise/soft delete eder; insan private rootunu izinsiz mutate/delete edemez.</td>
    <td>Yok.</td>
    <td>Agent human login rolü değildir; internal runtime principal ile çalışır.</td>
  </tr>
</table>

## 2.1 Authorization Değerlendirme Sırası

1. Caller principal belirlenir: anonymous, authenticated human veya trusted Agent/system runtime.

2. Operation sınıflandırılır: list, view, use, attach, derive, create, edit, pin_revision, reorder, set_enabled, soft_delete, restore, purge, ready_check veya run.

3. Workspace, Mainboard Item ve target Work Object contexti yüklenir: owner, visibility, deletion/lifecycle state, current/pinned revision, job/dependency state.

4. Role policy ve resource-specific policy uygulanır; shared/published/use ile edit/delete birbirinden ayrılır.

5. Yetki yoksa mutation başlamadan structured error döner. Client tarafından gönderilen `role`, `owner`, `isAdmin` veya `ready=true` alanları authority değildir.

6. Yetki varsa command transaction içinde yürür; canonical server state, audit event, composition fingerprint ve gerektiğinde outbox/domain event üretilir.

<table>
  <tr>
    <th>IMPLEMENTATION DECISION — NON-CANONICAL GAP RESOLUTION<br/>Mainboard satırındaki arrow, delete, Ready Check ve RUN kontrollerinde frontend action visibility server policy ile aynı response modelini kullanacaktır. UI zaten yasak olan actionı saklayabilir veya disabled gösterebilir; ancak bütün mutating endpoints `ACCESS_DENIED`/`OWNER_REQUIRED`/domain-specific code ile tekrar guard edilir. Bu karar Masterın “UI görünürlüğü authorization değildir” ilkesinin zorunlu uygulama sonucudur.</th>
  </tr>
</table>

# 3. V18 Interface Behavior — Yerleşim, Navigasyon ve Görünür Bileşenler

V18 HTML’de Mainboard, kalıcı üst menü kabuğu altında `#mainboardView` içinde render edilir. Mainboard görünürken `#pageView` gizlenir. Mainboard menu clicki `showMainboard()` ile bu görünümü geri getirir. Prototip içindeki sayfa geçişi single-workspace local DOM davranışıdır; Productionda bu davranış route/view state ile sürdürülebilir ancak canonical object state serverdan okunur.

## 3.1 Mainboard Sayfa Anatomisi

<table>
  <tr>
    <th>Bölge</th>
    <th>V18 görünümü</th>
    <th>Görünme koşulu</th>
    <th>Production sorumluluğu / sınır</th>
  </tr>
  <tr>
    <td>Global navigation shell</td>
    <td>Top title/login area ve menu bar sürekli görünür. Mainboard menüsü açılır dropdown taşır.</td>
    <td>Tüm workspace boyunca görünür.</td>
    <td>Bu belgede yalnız Mainboard menüsünün actionsları açıklanır. Diğer menu alanlarının kendi sayfa dokümanları vardır.</td>
  </tr>
  <tr>
    <td>Mainboard action dropdown</td>
    <td>Mainboard &gt; Add Strategy; Add Outsource Signal &gt; Trading Signal / Trade Log; Add Package; Portfolio / Equity Allocation.</td>
    <td>Mainboard menu hover/click interactionında görünür.</td>
    <td>Yeni work-object draftı veya source picker başlatır. Alan detayları ilgili sayfa dokümanlarına aittir.</td>
  </tr>
  <tr>
    <td>Strategies heading</td>
    <td>`STRATEGIES` başlığı.</td>
    <td>Mainboard view her zaman görünür.</td>
    <td>Productionda başlık, serverdan gelen active workspace item listesi ile birlikte kullanılmalıdır.</td>
  </tr>
  <tr>
    <td>Strategy list</td>
    <td>`#strategyList` içinde dinamik satırlar.</td>
    <td>Başlangıçta boş olabilir; V18 explicit empty-state metni vermez.</td>
    <td>Persisted item projection; transient draft rowları görsel olarak ayrıştırılır.</td>
  </tr>
  <tr>
    <td>Mainboard row</td>
    <td>Beyaz satır; title/ellipsis; right-side ▼ / × actions. Açık satır açık mavi tonlu ve details paneli gösterir.</td>
    <td>Her Strategy, Trading Signal veya Trade Log rowu için.</td>
    <td>Row bir `mainboard_item` projectionıdır; title/sıra persistent kimlik değildir.</td>
  </tr>
  <tr>
    <td>Inline details host</td>
    <td>Row open olduğunda Strategy Details veya external data details paneli satırın altında açılır.</td>
    <td>Arrow ile expanded state.</td>
    <td>Expanded state presentation-only’dir. İç alanların form sözleşmesi sonraki sayfa dokümanlarında tanımlanır.</td>
  </tr>
  <tr>
    <td>Backtest Results section</td>
    <td>`BACKTEST RESULTS` ve `#resultsList`.</td>
    <td>V18 başlangıçta gizli; demo RUN sonrası görünür.</td>
    <td>Productionda yalnız latest succeeded Result summary projection gösterilir; failed/cancelled run sonuç kartı üretmez.</td>
  </tr>
  <tr>
    <td>Run controls</td>
    <td>Sağ alt fixed alan: Backtest Ready Check button, dar ready status indicator, RUN button.</td>
    <td>Mainboard view açıkken görünür.</td>
    <td>Ready/Run state server-authoritative composition fingerprint ve run lifecycle ile render edilir.</td>
  </tr>
  <tr>
    <td>Ready Check modal</td>
    <td>Modal title “Backtest Ready Check”; Passed, Failed, Warnings cards; Close button.</td>
    <td>V18 Ready Check butonuna basıldığında.</td>
    <td>Productionda immutable Ready Check Reportun issue listesi gösterilir; client-side DOM scan sonucu authoritative değildir.</td>
  </tr>
  <tr>
    <td>Add Package popover</td>
    <td>Floating popover: Choose Package Type, Choose Package, Close, Add Selected Package.</td>
    <td>Mainboard &gt; Add Package actionında.</td>
    <td>V18 options ile Production source rule farklıdır; ayrıntı §13 Alignment içinde.</td>
  </tr>
</table>

## 3.2 Mainboard Menu Dropdown — V18 Gözlemi

<table>
  <tr>
    <th>UI label</th>
    <th>V18 click sonucu</th>
    <th>Mainboarda etkisi</th>
    <th>Production sınırlaması</th>
  </tr>
  <tr>
    <td>Add Strategy</td>
    <td>`addStrategyBox(event)` local strategy row ve inline details paneli ekler.</td>
    <td>V18 `strategyCount` artar; local `backtestReady=false` olur.</td>
    <td>Production transient Strategy Draft başlatır. Persisted root/revision oluşana kadar Ready/Run inputu değildir.</td>
  </tr>
  <tr>
    <td>Add Outsource Signal &gt; Trading Signal</td>
    <td>`addSignalPackageBox(event)` local signal row ve details paneli ekler.</td>
    <td>V18 `signalCount` artar; local ready state sıfırlanır.</td>
    <td>Production `trading_signal` external work-object draftı başlatır; package type üretmez.</td>
  </tr>
  <tr>
    <td>Add Outsource Signal &gt; Trade Log</td>
    <td>`addTradeLogBox(event)` local trade-log row ve import/details paneli ekler.</td>
    <td>V18 `tradeLogCount` artar; local ready state sıfırlanır.</td>
    <td>Production `trade_log` external work-object draftı + import/validation job akışını başlatır; package type üretmez.</td>
  </tr>
  <tr>
    <td>Add Package</td>
    <td>`showAddPackagePanel(event)` floating type/package picker açar.</td>
    <td>Seçilen V18 entry bir local row olarak eklenir.</td>
    <td>Productionda yalnız Strategy Package üzerinden derived Strategy Draft üretilir. Signal/Trade Log Add Package optionları kaldırılır.</td>
  </tr>
  <tr>
    <td>Portfolio / Equity Allocation</td>
    <td>`showPortfolioEquityPanel(event)` ayrı page view açar.</td>
    <td>Active listten DOM ile item names/capital okunur.</td>
    <td>Production allocation rows, display name değil `mainboard_working_item_id` üzerinden eşleşir. Ayrıntı Page [13/22].</td>
  </tr>
</table>

## 3.3 Row Presentation Contract

<table>
  <tr>
    <th>Row elementi</th>
    <th>V18 davranışı</th>
    <th>Production effective behavior</th>
  </tr>
  <tr>
    <td>Primary label</td>
    <td>Default: `STRATEGY N`, `TRADING SIGNAL N`, `TRADE LOG N`; package sourced rowlarda legacy “... PACKAGE N” texti.</td>
    <td>Display label revision snapshotından gelir; optional `display_label_override` yalnız presentation içindir. Legacy Signal/Trade Log “Package” termleri migrate edilir.</td>
  </tr>
  <tr>
    <td>Arrow button ▼ / ▲</td>
    <td>Row class `open` toggle eder; details panelini açar/kapatır.</td>
    <td>Presentation-only state; revision, readiness, audit veya engine davranışı değiştirmez. Optional user UI preference olarak saklanabilir.</td>
  </tr>
  <tr>
    <td>Delete button ×</td>
    <td>Rowu DOMdan kaldırır, local Trash entry ekler, ready false yapar.</td>
    <td>Type-specific “Delete Strategy / Delete Trading Signal / Delete Trade Log” confirmation akışını başlatır. Server success sonrası root soft delete + item active boarddan kalkar.</td>
  </tr>
  <tr>
    <td>Visual order</td>
    <td>DOM append sırası.</td>
    <td>Persistent `position_index`; yalnız kullanıcı düzeni. Engine event priority veya Agent scheduling sırası değildir.</td>
  </tr>
  <tr>
    <td>Enabled state</td>
    <td>Ayrı V18 toggle yok; eklenen satırlar fiilen aktif varsayılır.</td>
    <td>Backend `is_enabled=true` default taşır. Disabled item görünür kalabilir fakat snapshot, Ready Check, Allocation ve Run inputundan çıkarılır.</td>
  </tr>
  <tr>
    <td>Unsaved marker</td>
    <td>V18 explicit marker yok.</td>
    <td>Production transient local draft rowu `Unsaved` badgei taşımalıdır; title/row yalnız UI convenience olarak var olabilir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>CANONICAL RULE<br/>Expanded/collapsed durum yalnız sunum stateidir. Bir satırın açılması/kapanması Strategy revision üretmez, Ready Checki stale yapmaz ve audit event zorunluluğu doğurmaz. Buna karşılık item add/delete/enable/pinned-revision/Allocation değişikliği composition hashini değiştirir ve Ready reportu STALE yapar.</th>
  </tr>
</table>

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen / state</th>
    <th>Varsayılan / giriş</th>
    <th>Kullanıcıya görünen davranış</th>
    <th>Payload / engine etkisi</th>
    <th>Recovery / next action</th>
  </tr>
  <tr>
    <td>Workspace loading</td>
    <td>Mainboard route ilk açılır.</td>
    <td>Skeleton veya “Loading Mainboard…”; stale local list authoritative kabul edilmez.</td>
    <td>Query in-flight; engine etkisi yok.</td>
    <td>GET current workspace tamamlanınca canonical items/permissions/ready summary ile hydrate et.</td>
  </tr>
  <tr>
    <td>Empty workspace</td>
    <td>Persisted enabled item yok.</td>
    <td>`STRATEGIES` altında empty state görünür; Results section gizli veya “No recent result for this Mainboard.”.</td>
    <td>Snapshot oluşturulamaz; Ready Check blocker.</td>
    <td>Add Strategy veya Add Outsource Signal başlat; package kaynaklı Strategy Draft oluştur.</td>
  </tr>
  <tr>
    <td>Transient draft row</td>
    <td>Add action sonrası Save öncesi.</td>
    <td>`Unsaved` badge, Draft context, Save / Discard affordance.</td>
    <td>Root/revision yok; Ready/Run snapshotına girmez.</td>
    <td>Save ile root+revision+item oluştur; Discard ile local row kapat. Trash yok.</td>
  </tr>
  <tr>
    <td>Persisted enabled item</td>
    <td>Root/revision kaydedildi ve item pinlendi.</td>
    <td>Normal row; optional revision badge/updated indicator.</td>
    <td>Snapshot/Ready/Run inputuna girer.</td>
    <td>Edit sonrası new revision save/pin veya current pin korunur.</td>
  </tr>
  <tr>
    <td>Persisted disabled item</td>
    <td>Backend `is_enabled=false`.</td>
    <td>Row görünür, `Disabled` badge; Run contribution muted.</td>
    <td>Snapshot, Ready Check, Allocation calculation ve Run manifestinden çıkar.</td>
    <td>Enable action expected row version ile itemi aktive eder; yeni composition hash gerekir.</td>
  </tr>
  <tr>
    <td>Collapsed / expanded row</td>
    <td>Collapsed default.</td>
    <td>▼ detailsi açar; ▲ kapatır.</td>
    <td>Yok; presentation only.</td>
    <td>Toggle local/UI preference. No audit required.</td>
  </tr>
  <tr>
    <td>Ready absent</td>
    <td>Açılış, empty veya current report yok.</td>
    <td>Status indicator: Not Ready; RUN disabled.</td>
    <td>No eligible `ready_report_id`.</td>
    <td>Run Backtest Ready Check.</td>
  </tr>
  <tr>
    <td>Ready evaluating</td>
    <td>Ready Check command accepted.</td>
    <td>Ready button loading; RUN disabled; report modal/drawer issue rows oluşana kadar pending.</td>
    <td>Server snapshot + validators çalışır.</td>
    <td>Wait; retry only if server returns retryable job/service error.</td>
  </tr>
  <tr>
    <td>Ready pass</td>
    <td>No blocker, current fingerprint.</td>
    <td>Green status; RUN enabled.</td>
    <td>Current `ready_report_id` + exact `composition_hash` eligible.</td>
    <td>RUN may be requested until composition/dependency changes.</td>
  </tr>
  <tr>
    <td>Ready with warnings</td>
    <td>No blocker but warnings.</td>
    <td>Green status plus “Ready with warnings”; warning count accessible.</td>
    <td>Run allowed; warnings manifestte kaydedilir.</td>
    <td>Review warnings; RUN allowed unless actor cancels.</td>
  </tr>
  <tr>
    <td>Ready failed</td>
    <td>One or more blockers.</td>
    <td>Red status; RUN disabled; report lists field/dependency failures.</td>
    <td>No run manifest.</td>
    <td>Fix source issue; run Ready Check again.</td>
  </tr>
  <tr>
    <td>Ready stale</td>
    <td>Composition/dependency fingerprint changed after report.</td>
    <td>Amber “Changes detected — Ready Check required”; RUN disabled.</td>
    <td>Old report cannot authorize RUN.</td>
    <td>Create fresh snapshot/report.</td>
  </tr>
  <tr>
    <td>Run queued / running</td>
    <td>RUN accepted.</td>
    <td>RUN becomes non-repeatable; stage text / progress; page may be closed.</td>
    <td>Immutable BacktestRun + manifest; worker reads manifest only.</td>
    <td>Observe via event stream/polling; user may navigate away.</td>
  </tr>
  <tr>
    <td>Run succeeded</td>
    <td>Worker terminal success.</td>
    <td>Latest Result summary projection appears/refreshes below Mainboard.</td>
    <td>Immutable Backtest Result artifact created.</td>
    <td>Open detail; browse History. Mainboard edits do not rewrite result.</td>
  </tr>
  <tr>
    <td>Run failed / cancelled</td>
    <td>Worker terminal non-success.</td>
    <td>Run status/error detail; no Backtest Result summary card.</td>
    <td>Failure/cancel audit + diagnostics optional; no normal Result.</td>
    <td>Use retry/new run path with fresh run id + new manifest.</td>
  </tr>
  <tr>
    <td>Delete pending / blocked</td>
    <td>User clicks delete.</td>
    <td>Confirmation modal, then loading; or blocker message if active run owns input.</td>
    <td>No root deletion before server transaction commits.</td>
    <td>Cancel, wait/cancel active job, or resolve policy blocker.</td>
  </tr>
  <tr>
    <td>Soft deleted</td>
    <td>Delete success.</td>
    <td>Row disappears from active board; success toast; Admin sees Trash entry.</td>
    <td>Root `soft_deleted`; item detach projection; historical manifests remain.</td>
    <td>Only Admin may restore. Non-admin cannot access Trash.</td>
  </tr>
  <tr>
    <td>Row version conflict</td>
    <td>Another actor changed item/pin/order.</td>
    <td>Inline conflict/banner; no optimistic state retained.</td>
    <td>Server rejects stale write; no new composition hash from client attempt.</td>
    <td>Reload canonical state; compare/merge/retry with latest row_version.</td>
  </tr>
</table>

## 4.1 State Transition Summary

<table>
  <tr>
    <th>EMPTY<br/>  -&gt; transient draft (local only)<br/>  -&gt; Save succeeds<br/>  -&gt; StrategyRoot / TradingSignalRoot / TradeLogRoot (as applicable) + immutable Revision + MainboardWorkingItem(is_enabled=true, pinned_revision_id)<br/>  -&gt; Composition fingerprint changes<br/>  -&gt; Ready Check Report: PASS | PASS_WITH_WARNINGS | FAIL<br/>  -&gt; RUN accepted only for current report/fingerprint<br/>  -&gt; BacktestRun: QUEUED -&gt; PROVISIONING -&gt; RUNNING -&gt; SUCCEEDED | FAILED | CANCELLED<br/>  -&gt; SUCCEEDED only: immutable BacktestResult + Mainboard latest-result summary projection</th>
  </tr>
</table>

# 5. Alanlar, Varsayılanlar, Zorunluluk ve Dependency Contract

Mainboard root yüzeyi form alanı yoğun bir sayfa değildir. Sayfa; action triggerları, source pickerları, hidden concurrency fields ve state-gated controls taşır. Strategy Details ve external-object editors içindeki alanlar kendi sayfa dokümanlarında tanımlanır. Bu bölüm yalnız Mainboardun sahip olduğu veya Mainboard commandini tetikleyen alanları kapsar.

## 5.1 Visible Root Controls

<table>
  <tr>
    <th>Alan / control</th>
    <th>UI tipi ve V18 default</th>
    <th>Zorunluluk</th>
    <th>Koşul / seçenek</th>
    <th>Production payload</th>
    <th>Validation / dependency</th>
  </tr>
  <tr>
    <td>Mainboard menu</td>
    <td>Dropdown trigger; label `Mainboard`.</td>
    <td>Zorunlu input değildir.</td>
    <td>Actions: Add Strategy; Add Outsource Signal; Add Package; Portfolio / Equity Allocation.</td>
    <td>N/A — navigation/action trigger.</td>
    <td>Visibility may be role-aware; endpoint authorization separately enforced.</td>
  </tr>
  <tr>
    <td>Add Strategy</td>
    <td>Button/menu item.</td>
    <td>Action seçimi zorunlu değildir.</td>
    <td>Transient Strategy Draft başlatır.</td>
    <td>`create_strategy_draft` intent; idempotency key.</td>
    <td>Authenticated create policy; no Ready input until persisted revision exists.</td>
  </tr>
  <tr>
    <td>Add Outsource Signal</td>
    <td>Parent submenu trigger.</td>
    <td>Child kind selection zorunlu.</td>
    <td>Options: Trading Signal, Trade Log.</td>
    <td>`create_external_work_object_draft(kind)` intent.</td>
    <td>kind enum only `trading_signal` or `trade_log`; user must have create rights.</td>
  </tr>
  <tr>
    <td>Add Package &gt; Package Type *</td>
    <td>V18 select initial: `Choose Package Type` (disabled selected). V18 options: Strategy, Trading Signal, Trade Log.</td>
    <td>Required only when user presses “Add Selected Package”.</td>
    <td>Production option set: Strategy Package only. Signal/Trade Log are removed from this picker.</td>
    <td>`source_package_root_id`, `source_package_revision_id` used to derive Strategy Draft.</td>
    <td>Must be accessible, active/published/usable Strategy Package revision. Never use display name alone.</td>
  </tr>
  <tr>
    <td>Add Package &gt; Package *</td>
    <td>V18 disabled select until type chosen; initial: `Choose Package`.</td>
    <td>Conditionally required after package type selected and before Add Selected Package.</td>
    <td>List comes from selected type; V18 local static group.</td>
    <td>Exact source package root/revision reference.</td>
    <td>Server filters by use policy, lifecycle and compatibility. Selection cannot be stale/deleted.</td>
  </tr>
  <tr>
    <td>Add Selected Package</td>
    <td>Button; V18 no disabled visual guard except empty early return.</td>
    <td>Requires Type + Package.</td>
    <td>Production creates derived Strategy Draft, not Mainboard package row.</td>
    <td>`derive_strategy_draft_from_package` with idempotency key.</td>
    <td>No direct package item attach; provenance mandatory.</td>
  </tr>
  <tr>
    <td>Backtest Ready Check</td>
    <td>Fixed button; default available.</td>
    <td>No form field. Requires valid current persisted composition to pass.</td>
    <td>Can be invoked while failures exist to receive report.</td>
    <td>`request_ready_check(workspace_id, snapshot_id?)`.</td>
    <td>Server builds/reads current snapshot and validates all direct/transitive dependencies.</td>
  </tr>
  <tr>
    <td>Ready status indicator</td>
    <td>V18 narrow red/green bar; title defaults `Backtest Ready: Not Ready`.</td>
    <td>Not an input.</td>
    <td>Production values: NOT_READY, CHECKING, READY, READY_WITH_WARNINGS, FAILED, STALE.</td>
    <td>Read model only: report_id/fingerprint/status.</td>
    <td>Client status cannot enable RUN without current server report.</td>
  </tr>
  <tr>
    <td>RUN</td>
    <td>Large button; V18 default locked/gray.</td>
    <td>Conditionally enabled only when current Ready report has no blockers.</td>
    <td>Production must also allow READY_WITH_WARNINGS.</td>
    <td>`request_backtest_run(ready_report_id, composition_snapshot_id, expected_composition_hash, idempotency_key)`.</td>
    <td>Server repeats preflight/fingerprint match; ignores client `ready=true` claim.</td>
  </tr>
  <tr>
    <td>Row arrow</td>
    <td>▼ collapsed / ▲ expanded.</td>
    <td>Not required.</td>
    <td>One row at a time or multiple open is UI choice; V18 independent toggles.</td>
    <td>Optional user UI preference only.</td>
    <td>No revision, Ready, audit or engine impact.</td>
  </tr>
  <tr>
    <td>Row × delete</td>
    <td>Icon button.</td>
    <td>Action confirmation required in Production.</td>
    <td>Type-specific: Strategy, Trading Signal, Trade Log; Result row delete is result-specific and separately policy guarded.</td>
    <td>`soft_delete_work_object(root_id, reason?, idempotency_key)`.</td>
    <td>Owner/Admin policy; root must be ACTIVE; active Run/Queue input blocks delete.</td>
  </tr>
  <tr>
    <td>Result summary row</td>
    <td>V18 initially absent; created by demo RUN.</td>
    <td>Not editable.</td>
    <td>Only latest succeeded Result summary for this board.</td>
    <td>`GET result summary projection`.</td>
    <td>May render only after server Result materialization; failed/cancelled run never creates it.</td>
  </tr>
</table>

## 5.2 Hidden / Backend-Controlled Fields

<table>
  <tr>
    <th>Field</th>
    <th>Owner</th>
    <th>Default / source</th>
    <th>Mandatory behavior</th>
    <th>UI rule</th>
  </tr>
  <tr>
    <td>`workspace_id`</td>
    <td>Server</td>
    <td>Default Mainboard resolved from authenticated human; Agent uses agent_research workspace.</td>
    <td>Every command targets exact workspace.</td>
    <td>Never infer from visible title text.</td>
  </tr>
  <tr>
    <td>`mainboard_working_item_id`</td>
    <td>Server</td>
    <td>UUID generated at attach.</td>
    <td>Stable composition identity for Allocation, audit, result manifest, events.</td>
    <td>Never use `Strategy 1` or display position as ID.</td>
  </tr>
  <tr>
    <td>`item_kind`</td>
    <td>Server enum</td>
    <td>`strategy` | `trading_signal` | `trade_log`.</td>
    <td>Must match target root object kind.</td>
    <td>Reject mismatch with `MAINBOARD_ITEM_KIND_MISMATCH`.</td>
  </tr>
  <tr>
    <td>`work_object_root_id`</td>
    <td>Server/reference</td>
    <td>Exact source root.</td>
    <td>Mandatory for persisted item.</td>
    <td>Display name cannot substitute root ID.</td>
  </tr>
  <tr>
    <td>`pinned_revision_id`</td>
    <td>Server/reference</td>
    <td>Exact revision at attach/save/pin.</td>
    <td>Mandatory; no implicit latest.</td>
    <td>New revision must be explicitly pinned.</td>
  </tr>
  <tr>
    <td>`position_index`</td>
    <td>Server</td>
    <td>Assigned transactionally; initial UI append order may map to next index.</td>
    <td>Presentation order only; persist for deterministic view read model.</td>
    <td>Do not use as engine priority.</td>
  </tr>
  <tr>
    <td>`is_enabled`</td>
    <td>Server</td>
    <td>Default `true` for newly attached item.</td>
    <td>Disabled items excluded from snapshot/Ready/Allocation/Run.</td>
    <td>V18 has no control; future UI must not silently leave disabled values engine-active.</td>
  </tr>
  <tr>
    <td>`row_version` / ETag</td>
    <td>Server</td>
    <td>Incremented by mutation.</td>
    <td>Required with item PATCH/reorder/enable/pin commands.</td>
    <td>409 conflict triggers reload/merge workflow.</td>
  </tr>
  <tr>
    <td>`composition_hash`</td>
    <td>Server</td>
    <td>Calculated from current relevant composition/dependencies.</td>
    <td>Ready report binds to it; RUN verifies it.</td>
    <td>Do not calculate authoritative hash from DOM/localStorage.</td>
  </tr>
  <tr>
    <td>`ready_report_id`</td>
    <td>Server</td>
    <td>Created by Ready Check.</td>
    <td>Run requires current, PASS or PASS_WITH_WARNINGS report.</td>
    <td>Invalidated/staled after material composition change.</td>
  </tr>
  <tr>
    <td>`idempotency_key`</td>
    <td>Client/Tool gateway</td>
    <td>Generated per logical mutation/run request.</td>
    <td>Mandatory for add/attach/delete/run class commands.</td>
    <td>Same key must not create duplicate item/run.</td>
  </tr>
  <tr>
    <td>`actor / principal context`</td>
    <td>Server session or Agent runtime</td>
    <td>Not client-selected.</td>
    <td>Required for policy/audit/provenance.</td>
    <td>Ignore request body claims such as `currentRole=Admin`.</td>
  </tr>
</table>

<table>
  <tr>
    <th>MANDATORY-STAR STANDARD<br/>Mainboard root screeninde static `*` ile işaretlenen bağımsız form alanı yoktur. Add Package popoverında Package Type ve Package seçimleri action submit aşamasında zorunludur. Add Strategy, Trading Signal, Trade Log ve Portfolio form alanlarının yıldız/conditional requiredness sözleşmesi kendi sayfa dokümanlarında yazılır; Mainboard Ready Check bunların persisted revision/import outcomeunu aggregate eder.</th>
  </tr>
</table>

# 6. Bilgi Metinleri ve Content Catalog

## 6.1 ⓘ Bilgi Panelleri

V18 Mainboard root yüzeyinde Mainboarda ait bir ⓘ bilgi düğmesi bulunmaz. Strategy Details ve external-object details paneli içinde görünen ⓘ düğmeleri, Mainboard tarafından sadece host edilir; metinleri Page [2/22], [4/22] ve [5/22] dokümanlarının sahipliğindedir. Bu nedenle Mainboard adına duplicate/çelişkili info text yazılmaz.

<table>
  <tr>
    <th>UI owner</th>
    <th>Mainboard içindeki görünümü</th>
    <th>Mainboard dokümanındaki karar</th>
  </tr>
  <tr>
    <td>Strategy Details info controls</td>
    <td>Expanded Strategy row altında görülebilir.</td>
    <td>Varlığı Mainboard host behavior olarak kaydedilir; tam panel title/text Page [2/22] sahibidir.</td>
  </tr>
  <tr>
    <td>Trading Signal details info controls</td>
    <td>Expanded Trading Signal row altında görülebilir.</td>
    <td>Tam bilgi içerikleri Page [4/22] sahibidir.</td>
  </tr>
  <tr>
    <td>Trade Log details info controls</td>
    <td>Expanded Trade Log row altında görülebilir.</td>
    <td>Tam bilgi içerikleri Page [5/22] sahibidir.</td>
  </tr>
  <tr>
    <td>Mainboard Ready status</td>
    <td>V18 status indicator yalnız `title` tooltip kullanır.</td>
    <td>Productionda text status + accessible description zorunludur; ⓘ panel eklemek opsiyoneldir, iş mantığını gizlememelidir.</td>
  </tr>
</table>

## 6.2 Final UI Text Catalog — Mainboard Owned Text

<table>
  <tr>
    <th>Context / key</th>
    <th>Final UI text</th>
    <th>Display rule</th>
  </tr>
  <tr>
    <td>Empty state title</td>
    <td>Your Mainboard is empty.</td>
    <td>Persisted enabled item olmadığı zaman `STRATEGIES` altında gösterilir.</td>
  </tr>
  <tr>
    <td>Empty state body</td>
    <td>Add a Strategy, Trading Signal, or Trade Log to build a backtest composition. Unsaved drafts are not included in Backtest Ready Check or RUN.</td>
    <td>Empty state title altında helper text.</td>
  </tr>
  <tr>
    <td>Empty state primary action</td>
    <td>Add Strategy</td>
    <td>User create policy uygunsa göster.</td>
  </tr>
  <tr>
    <td>Empty state secondary action</td>
    <td>Add Outsource Signal</td>
    <td>User create policy uygunsa göster; submenu Trading Signal / Trade Log açar.</td>
  </tr>
  <tr>
    <td>Transient draft badge</td>
    <td>Unsaved</td>
    <td>Local transient rowda title yanında.</td>
  </tr>
  <tr>
    <td>Transient draft helper</td>
    <td>This draft is visible only in this editor session. Save it to include it in Backtest Ready Check and RUN.</td>
    <td>Expanded draft header veya inline warning.</td>
  </tr>
  <tr>
    <td>Unsaved Ready blocker</td>
    <td>This Mainboard contains an unsaved draft. Save or discard it before running Backtest Ready Check.</td>
    <td>Ready Check report blocker/inline error.</td>
  </tr>
  <tr>
    <td>Not-ready status</td>
    <td>Backtest Ready: Not Ready</td>
    <td>No current passing report; status indicator accessible label.</td>
  </tr>
  <tr>
    <td>Checking status</td>
    <td>Backtest Ready: Checking current composition…</td>
    <td>Ready Check request in progress.</td>
  </tr>
  <tr>
    <td>Ready status</td>
    <td>Backtest Ready: Ready</td>
    <td>Current report PASS.</td>
  </tr>
  <tr>
    <td>Ready-with-warnings status</td>
    <td>Backtest Ready: Ready with warnings</td>
    <td>Current report PASS_WITH_WARNINGS.</td>
  </tr>
  <tr>
    <td>Stale status</td>
    <td>Changes detected. Run Backtest Ready Check again.</td>
    <td>Current report fingerprint no longer matches composition.</td>
  </tr>
  <tr>
    <td>Run disabled helper</td>
    <td>RUN is available only after a current Backtest Ready Check passes.</td>
    <td>Disabled RUN tooltip/aria-description.</td>
  </tr>
  <tr>
    <td>Ready modal title</td>
    <td>Backtest Ready Check</td>
    <td>Report modal/drawer title.</td>
  </tr>
  <tr>
    <td>Ready report sections</td>
    <td>Passed | Blockers | Warnings</td>
    <td>Production text; V18 “Failed” can be migrated to clearer “Blockers”.</td>
  </tr>
  <tr>
    <td>No passed rows</td>
    <td>No passing check has been recorded yet.</td>
    <td>Passed card empty state.</td>
  </tr>
  <tr>
    <td>No blockers</td>
    <td>No blocking issue detected.</td>
    <td>Blockers card empty state.</td>
  </tr>
  <tr>
    <td>Common warning</td>
    <td>Review commission, spread, and slippage assumptions before running a production backtest.</td>
    <td>Warning when execution-cost assumptions are absent/weak or generic review reminder applies.</td>
  </tr>
  <tr>
    <td>Package type placeholder</td>
    <td>Choose Package Type</td>
    <td>Disabled initial option in Add Package popover.</td>
  </tr>
  <tr>
    <td>Package placeholder</td>
    <td>Choose Package</td>
    <td>Disabled until valid package type/source is resolved.</td>
  </tr>
  <tr>
    <td>Add Package empty list</td>
    <td>No usable Strategy Package is available for this Mainboard.</td>
    <td>No accessible active Strategy Package in picker query.</td>
  </tr>
  <tr>
    <td>New revision badge</td>
    <td>Newer revision available</td>
    <td>Mainboard item remains pinned to older revision while source root current revision differs.</td>
  </tr>
  <tr>
    <td>Revision pin helper</td>
    <td>This Mainboard currently uses revision {revision_no}. Update the pinned revision only when you want a new Ready Check and Backtest Run to use the newer definition.</td>
    <td>Item metadata/popover.</td>
  </tr>
  <tr>
    <td>Delete modal title</td>
    <td>Delete {item_type}?</td>
    <td>Type-specific confirmation.</td>
  </tr>
  <tr>
    <td>Delete modal body</td>
    <td>You are about to soft-delete “{display_name}”. It will be removed from the active Mainboard and new selection lists. Existing Backtest Runs and Results keep their historical pinned revision references.</td>
    <td>All normal Work Object deletes.</td>
  </tr>
  <tr>
    <td>Delete modal warning</td>
    <td>Only an Admin can restore this item from Trash.</td>
    <td>Always in confirmation text for non-Admin and Admin; conveys policy.</td>
  </tr>
  <tr>
    <td>Delete blocked</td>
    <td>This item is used by a queued or running Backtest Run and cannot be deleted yet. Wait for the run to finish or cancel it through the run lifecycle controls.</td>
    <td>409 OBJECT_IN_ACTIVE_RUN / DELETE_BLOCKED_BY_RUNNING_JOB.</td>
  </tr>
  <tr>
    <td>Delete success</td>
    <td>“{display_name}” was moved to Trash.</td>
    <td>Only after server soft-delete transaction succeeds.</td>
  </tr>
  <tr>
    <td>Access denied</td>
    <td>You do not have permission to perform this action on this Mainboard item.</td>
    <td>403 / owner policy denial.</td>
  </tr>
  <tr>
    <td>Conflict banner</td>
    <td>This item changed in another session. Reload the latest state before trying again.</td>
    <td>409 ROW_VERSION_CONFLICT.</td>
  </tr>
  <tr>
    <td>Run queued</td>
    <td>Backtest run queued. You can leave this page; the run will continue in the background.</td>
    <td>BacktestRun QUEUED after accepted command.</td>
  </tr>
  <tr>
    <td>Run running</td>
    <td>Backtest run is running from an immutable snapshot of this Mainboard.</td>
    <td>RUNNING state.</td>
  </tr>
  <tr>
    <td>Run success</td>
    <td>Backtest completed. The latest result is available below; earlier results remain in Results History.</td>
    <td>SUCCEEDED + Result materialized.</td>
  </tr>
  <tr>
    <td>Run failed</td>
    <td>Backtest did not complete. No Backtest Result was created. Review the run diagnostics and retry with a new run.</td>
    <td>FAILED terminal state.</td>
  </tr>
  <tr>
    <td>Run cancelled</td>
    <td>Backtest was cancelled. No Backtest Result was created.</td>
    <td>CANCELLED terminal state.</td>
  </tr>
  <tr>
    <td>Result empty</td>
    <td>No succeeded Backtest Result is available for this Mainboard yet.</td>
    <td>Results projection has no result to show.</td>
  </tr>
  <tr>
    <td>Close</td>
    <td>Close</td>
    <td>Modal/popover close action.</td>
  </tr>
  <tr>
    <td>Add Selected Package</td>
    <td>Create Strategy Draft from Selected Package</td>
    <td>Production label replaces V18 ambiguous “Add Selected Package”.</td>
  </tr>
</table>

## 6.3 Placeholder, Helper, Warning ve Error İçerik İlkeleri

• No fabricated result data: Production metric labels never show V18 demo values such as `Net Profit +84.2%` unless immutable Result artifact actually contains the metric.

• No silent status substitution: “Ready” is not a generic success color; it must mean a current report, current fingerprint and no blocker. If warnings exist, text explicitly says so.

• No silent package migration: Legacy V18 Signal/Trade Log package labels are not merely cosmetically renamed. Picker option and API/domain type are removed from Package Library flow.

• Error language is actionable: Each user-facing error says whether the user should save, select another revision, reload, repair dependency, wait for a run, or retry a new run.

# 7. Butonlar, Command’ler ve State Davranışı

<table>
  <tr>
    <th>UI action</th>
    <th>Logical command / endpoint</th>
    <th>Precondition</th>
    <th>Disabled / loading</th>
    <th>Success</th>
    <th>Error / retry / audit</th>
  </tr>
  <tr>
    <td>Open Mainboard</td>
    <td>`GET /mainboards/default` or route data query</td>
    <td>Caller may access resolved default workspace.</td>
    <td>Loading skeleton while query resolves.</td>
    <td>Canonical items, permissions, latest result summary and ready-state projection hydrate UI.</td>
    <td>403/404 restricted state; no mutation/audit required.</td>
  </tr>
  <tr>
    <td>Add Strategy</td>
    <td>`POST /strategy-drafts` (logical create draft) or local transient draft bootstrap</td>
    <td>Authenticated create policy.</td>
    <td>Action disabled while draft bootstrap duplicate command is pending.</td>
    <td>Transient editor row appears; save later creates root/revision/item.</td>
    <td>Retry only if bootstrap persistence command used; audit once a persistent root/revision is created.</td>
  </tr>
  <tr>
    <td>Save Strategy from hosted editor</td>
    <td>Owned by Page [2/22]; creates immutable Strategy revision and may pin item.</td>
    <td>Edit policy, valid strategy schema, dependencies, expected draft version.</td>
    <td>Save loading; Ready state shown stale after relevant mutation.</td>
    <td>New revision; existing or newly attached item gets explicit pin according to command result.</td>
    <td>422 validation / 409 draft conflict; audit `object_revision_created`, optional `mainboard_item_revision_changed`.</td>
  </tr>
  <tr>
    <td>Create Trading Signal / Trade Log</td>
    <td>`POST /external-work-object-drafts` with `kind`</td>
    <td>Authenticated create policy; `kind` valid.</td>
    <td>Source/import staging state shown.</td>
    <td>Draft external object created; import/validation runs separately; attach only after valid revision.</td>
    <td>422/403; source/import errors are owned by Pages [3/22]–[5/22].</td>
  </tr>
  <tr>
    <td>Open Add Package</td>
    <td>Read query of accessible Strategy Package revisions.</td>
    <td>None to open; selection requires use permission.</td>
    <td>Package select disabled until source list resolves.</td>
    <td>Picker shows eligible Strategy Package revisions.</td>
    <td>Empty state if none; no audit for opening/query.</td>
  </tr>
  <tr>
    <td>Create derived Strategy Draft from package</td>
    <td>`POST /strategy-drafts` with `source_package_root_id`, `source_package_revision_id`</td>
    <td>Selected source must be active, usable and revision-resolved.</td>
    <td>Submit disabled until Type + Package chosen; loading after submit.</td>
    <td>New draft + provenance; package itself remains unchanged.</td>
    <td>422 dependency/lifecycle; audit draft/root creation when persisted.</td>
  </tr>
  <tr>
    <td>Toggle row expansion</td>
    <td>No domain command. Optional user preference PATCH.</td>
    <td>Item visible.</td>
    <td>Immediate UI transition.</td>
    <td>Details host opens/closes.</td>
    <td>No Ready invalidation and no audit required.</td>
  </tr>
  <tr>
    <td>Pin new revision</td>
    <td>`PATCH /mainboard-items/{id}` with `pinned_revision_id`, `expected_row_version`</td>
    <td>Caller can attach/use revision and mutate item; root/revision active and kind compatible.</td>
    <td>Disable pin control while request pending.</td>
    <td>Server returns updated item + new composition fingerprint; ready report marked stale.</td>
    <td>409 ROW_VERSION_CONFLICT; 409 OBJECT_NOT_ACTIVE; audit `mainboard_item_revision_pinned`.</td>
  </tr>
  <tr>
    <td>Enable / disable item</td>
    <td>`PATCH /mainboard-items/{id}` with `is_enabled`, `expected_row_version`</td>
    <td>Future visible control; item belongs to current workspace and policy permits mutation.</td>
    <td>Toggle pending state.</td>
    <td>Snapshot eligibility changes; report stale.</td>
    <td>409 conflict; audit `mainboard_item_disabled` / composition change.</td>
  </tr>
  <tr>
    <td>Ready Check</td>
    <td>`POST /mainboards/{id}/snapshots` then `POST /mainboards/{id}/ready-checks` or atomic service command</td>
    <td>May be invoked even when composition likely invalid; server must see current workspace.</td>
    <td>Button loading; RUN locked.</td>
    <td>Immutable snapshot/report returns PASS, PASS_WITH_WARNINGS or FAIL; status reflects current hash.</td>
    <td>422 COMPOSITION_EMPTY or UNSAVED_MAINBOARD_DRAFT; retry after repair. Audit/report creation according to policy.</td>
  </tr>
  <tr>
    <td>RUN</td>
    <td>`POST /backtest-runs` with `ready_report_id`, `composition_snapshot_id`, `expected_composition_hash`, `idempotency_key`</td>
    <td>Current report pass/warnings; exact snapshot current; caller may use every dependency.</td>
    <td>Locked when not ready/stale; once submitted prevent duplicate click.</td>
    <td>BacktestRun QUEUED; immutable manifest; event stream URI/status metadata returned.</td>
    <td>409 READY_REPORT_STALE; 422 blockers; duplicate idempotency returns existing run, not second job. Audit `run_requested`.</td>
  </tr>
  <tr>
    <td>Open Result summary</td>
    <td>`GET /backtest-results/{result_id}` summary/detail query</td>
    <td>Result visibility policy.</td>
    <td>Loading detail panel.</td>
    <td>Read-only immutable result details open.</td>
    <td>404/forbidden if deleted/not visible; no recalculation.</td>
  </tr>
  <tr>
    <td>Delete Work Object</td>
    <td>`DELETE /work-objects/{root_id}` with reason?, idempotency key</td>
    <td>Delete policy; root ACTIVE; not pinned by queued/running run.</td>
    <td>Confirmation + pending state; disable row action after submit.</td>
    <td>Root soft_deleted; row removed; Trash Entry/audit/outbox event created; stale Ready state.</td>
    <td>403 DELETE_FORBIDDEN / 409 OBJECT_IN_ACTIVE_RUN / ENTITY_ALREADY_SOFT_DELETED. Retry only as idempotent reconciliation.</td>
  </tr>
  <tr>
    <td>Delete Result summary</td>
    <td>Result soft-delete command; implementation owned by Result/Trash pages.</td>
    <td>Result delete policy.</td>
    <td>Confirmation/pending.</td>
    <td>Result removed from Mainboard summary and History active projection; run provenance remains.</td>
    <td>Never delete BacktestRun itself as side effect. Admin-only restore/purge via Trash.</td>
  </tr>
</table>

<table>
  <tr>
    <th>CANONICAL RULE — IDEMPOTENCY AND AUTHORITATIVE REHYDRATE<br/>Her mutation and RUN logical commandi idempotency key taşır. Server transaction başarıyla commit ettikten sonra canonical state döner; frontend optimistic DOM değişikliğini authority kabul etmez. Retry aynı logical commandi iki Strategy/Signal/Trade Log itemi veya iki BacktestRun üretmeyecek şekilde uygulanır.</th>
  </tr>
</table>

## 7.1 Ready Check ve RUN Semantiği

1. Ready Check, current persisted enabled itemlerden transactionally consistent snapshot alır; composition fingerprint/hash üretir.

2. Validators item kind, pinned revision, lifecycle, package/data/import/research available-time, allocation, execution ve policy bağımlılıklarını kontrol eder.

3. Report immutable kaydedilir. PASS/PASS_WITH_WARNINGS ile current fingerprint eşleşiyorsa RUN UI’da açılabilir.

4. RUN requesti clienttan gelen ready booleanını kabul etmez; current fingerprint ve equivalent preflightı server-side tekrar doğrular.

5. Server immutable Backtest Run Manifest oluşturur; Run QUEUED kaydı yazar; worker queueya yalnız run kimliği/manifest referansı ile iş verir.

6. Worker UI DOMu, Mainboardun güncel satırlarını veya “latest package revision”ı okumaz. Yalnız manifestte pinlenmiş inputları kullanır.

7. Sadece SUCCEEDED run immutable Backtest Result üretir. FAILED/CANCELLED run için failure/audit/diagnostic kayıtları olabilir; normal Result summary/History kaydı oluşmaz.

# 8. Kullanıcı Akışları

## 8.1 Başarılı Akış — Yeni Strategy ile Backtest

1. Kullanıcı Mainboardu açar. Empty state, mevcut Default Mainboardun persisted projectionını gösterir.

2. Kullanıcı Add Strategy seçer; transient `Unsaved` Strategy Draft rowu görünür.

3. Kullanıcı hosted Strategy Details editörünü tamamlar ve Save Strategy komutunu çalıştırır. Backend immutable Strategy revision üretir ve Mainboard itemi exact revisiona pinler.

4. Composition hash değişir; prior Ready report varsa STALE olur. UI `Changes detected. Run Backtest Ready Check again.` gösterir.

5. Kullanıcı Backtest Ready Checke basar. Backend snapshot/report üretir; blocker yoksa Ready veya Ready with warnings durumunu döndürür.

6. Kullanıcı RUNa basar. Server current report/fingerprinti doğrular; BacktestRun QUEUED olur ve worker çalışır.

7. Kullanıcı sayfadan ayrılabilir. Worker RUNNING -> SUCCEEDED olduğunda immutable Result artifactleri üretir.

8. Mainboard, latest Result summary projectionını gösterir. Kullanıcı rowu açarak Result detail ekranına gider; history ayrı Result indexinden okunur.

## 8.2 Başarılı Akış — Strategy Package’den Derived Strategy

1. Kullanıcı Add Package popoverını açar.

2. Production picker yalnız usable Strategy Package revisionlarını listeler.

3. Kullanıcı source package revisionını seçer ve Create Strategy Draft from Selected Package actionını kullanır.

4. Backend derived Strategy Draft üretir; `source_package_root_id`, `source_package_revision_id` ve inherited dependency listesi provenance içine yazılır.

5. Kullanıcı yeni Strategyyi değiştirirse original package değişmez; yalnız derived Strategy revisionı değişir.

6. Kaydedilen Strategy revisionı Mainboarda explicit pin edilir; Ready report stale olur ve normal Ready/Run akışı yeniden başlar.

## 8.3 Başarılı Akış — External Working Item

1. Kullanıcı Add Outsource Signal altında Trading Signal veya Trade Log seçer.

2. Seçim ilgili transient external-object draftını başlatır. Trading Signal event source/mapping; Trade Log import/source/parse akışı kendi sayfasında tamamlanır.

3. Productionda source asset ve mapping/import doğrulaması ayrı ingestion/validation jobdan geçer; UI file selector dolu görünmesi sufficient evidence değildir.

4. Geçerli immutable external revision oluşturulduktan sonra Mainboard item `trading_signal` veya `trade_log` kindi ile attach edilir.

5. Ready Check bu iki kindi Strategy ile aynı form kurallarıyla değil, kendi external source/import/time availability şemalarıyla değerlendirir.

## 8.4 Empty, Validation ve Dependency Recovery

<table>
  <tr>
    <th>Durum</th>
    <th>Kullanıcıya görünen sonuç</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>No Mainboard item</td>
    <td>Ready Check report: composition empty blocker; RUN locked.</td>
    <td>Persisted enabled Strategy, Trading Signal veya Trade Log oluştur/attach et.</td>
  </tr>
  <tr>
    <td>Unsaved local row</td>
    <td>UNSAVED_MAINBOARD_DRAFT; rowda Save/Discard action.</td>
    <td>Kaydet veya discard et. Draft cleanup Trash üretmez.</td>
  </tr>
  <tr>
    <td>Deleted/invalid pinned revision</td>
    <td>OBJECT_NOT_ACTIVE veya dependency blocker.</td>
    <td>Active/accessible revisionı explicit seçip pinle; gerekirse Admin restore veya replacement source kullan.</td>
  </tr>
  <tr>
    <td>Package source no longer usable</td>
    <td>Picker shows no selectable item or server rejects stale selection.</td>
    <td>Refresh picker; select active/published usable Strategy Package revision.</td>
  </tr>
  <tr>
    <td>External file selected but not imported</td>
    <td>Ready Check blocker; source file UI state alone accepted değildir.</td>
    <td>Ingestion/parse/validation jobunu tamamla; normalized immutable import revision oluştur.</td>
  </tr>
  <tr>
    <td>Allocation changed after Ready</td>
    <td>Ready report stale; RUN locked.</td>
    <td>Allocation page üzerinden configi doğrula, sonra fresh Ready Check yap.</td>
  </tr>
  <tr>
    <td>Market/Research dependency invalid</td>
    <td>Ready Check issue, e.g. not approved / unavailable-time rule missing.</td>
    <td>Approved/compatible data revision seç; data owner workflowunu tamamla; Strategy revisionu tekrar kaydet/pinle.</td>
  </tr>
  <tr>
    <td>Concurrent item update</td>
    <td>ROW_VERSION_CONFLICT, local change rejected.</td>
    <td>Reload latest canonical state; reconcile field changes; retry with new row_version.</td>
  </tr>
  <tr>
    <td>Running run uses item</td>
    <td>Delete blocked.</td>
    <td>Run tamamlanana kadar bekle veya controlled cancellation path kullan; active runı silerek bozma.</td>
  </tr>
</table>

## 8.5 Delete, Restore ve Result Recovery

1. User/Supervisor/Agent kendi policy-scope Work Objectinin × actionını başlatır; Production type-specific delete confirmation gösterir.

2. Server delete preflight yapar: owner/role, lifecycle, active run/queue input, dependency ve idempotency kontrol edilir.

3. Başarıda root `soft_deleted` olur; Mainboard active projectiondan satır kalkar; immutable Trash Entry snapshotı ve audit event oluşur. Eski run/result manifestleri değişmez.

4. Sadece Admin Trashta restore başlatabilir. Restore, aynı root ID ve current revision pointerını ACTIVEye döndürür; yeni revision üretmez.

5. Restore sonrası item original board konumuna uygun olarak geri attach/projection edilir; Destination conflict varsa safe fallback/repair planı görünür. Ready state artık current değildir; fresh Ready Check gerekir.

6. Purge ayrı Admin-only asynchronous işlemdir. Normal × actionı hiçbir zaman permanent delete değildir.

# 9. Production Backend Behavior — Domain Model, Snapshot ve Events

## 9.1 Kalıcı Model

<table>
  <tr>
    <th>Entity</th>
    <th>Minimum alanlar</th>
    <th>Mainboard görevi</th>
  </tr>
  <tr>
    <td>`mainboard_workspaces`</td>
    <td>`id`, `owner_actor_id`, `workspace_kind`, `title`, `is_default`, `status`, `row_version`, timestamps.</td>
    <td>Human default, agent_research veya system composition rootu. Bir human actor için yalnız bir active default board.</td>
  </tr>
  <tr>
    <td>`mainboard_items`</td>
    <td>`id`, `workspace_id`, `item_kind`, `work_object_root_id`, `pinned_revision_id`, `position_index`, `is_enabled`, `display_label_override`, `row_version`.</td>
    <td>Tek satır/attachment. Exact revision pin, order, enable ve presentation metadata taşır.</td>
  </tr>
  <tr>
    <td>`work_object_roots`</td>
    <td>`id`, `object_kind`, `owner_actor_id`, `current_revision_id`, lifecycle/deletion metadata.</td>
    <td>Strategy, Trading Signal veya Trade Logun stable identitysi.</td>
  </tr>
  <tr>
    <td>`work_object_revisions`</td>
    <td>`id`, `root_id`, `revision_no`, `payload_json`, `source_provenance_json`, `validation_summary_json`, `content_hash`, `supersedes_revision_id`.</td>
    <td>Immutable business definition/source mapping/import snapshot. Historical Run exact revisiona bağlanır.</td>
  </tr>
  <tr>
    <td>`mainboard_composition_snapshots`</td>
    <td>`id`, `workspace_id`, `composition_hash`, `item_manifest_json`, `capital_mode_snapshot_json`, `readiness_state`, `readiness_report_id`.</td>
    <td>Ready Check ve Run için server-side frozen composition.</td>
  </tr>
  <tr>
    <td>`ready_check_reports`</td>
    <td>Report id, snapshot/fingerprint, validator version, immutable issues, status, timestamps, actor.</td>
    <td>Specific compositiona ait preflight evidence. Mutasyona uğramaz; stale olabilir.</td>
  </tr>
  <tr>
    <td>`backtest_runs` / manifests</td>
    <td>Run id, status, immutable manifest, requested_by, queue/job metadata, timestamps.</td>
    <td>RUN actionın async orchestration rootu. Result değildir.</td>
  </tr>
  <tr>
    <td>`backtest_results` / artifacts</td>
    <td>Result id, run id, manifest ref, metric summary, ledger/curve/diagnostic artifact refs, lifecycle.</td>
    <td>Sadece succeeded run sonrası oluşur; Mainboard latest summary projection buradan okunur.</td>
  </tr>
  <tr>
    <td>`trash_entries` / `audit_events`</td>
    <td>Delete snapshot, original location/owner, deletion and restore metadata; append-only event chain.</td>
    <td>Soft delete, restore/purge, historical evidence ve UI recovery için.</td>
  </tr>
</table>

## 9.2 Composition Snapshot Contract

Snapshot, Mainboardun “o an ekranda görünen hali” değildir. Current enabled persisted itemler, exact pinned revisions, display/order metadata, allocation/capital contexti ve Ready/Run anlamını değiştiren resolved dependencies ile server tarafında dondurulmuş immutable manifesttir.

<table>
  <tr>
    <th>{<br/>  &quot;snapshot_id&quot;: &quot;mbs_...&quot;,<br/>  &quot;workspace_id&quot;: &quot;mb_...&quot;,<br/>  &quot;composition_hash&quot;: &quot;sha256:...&quot;,<br/>  &quot;items&quot;: [<br/>    {&quot;item_id&quot;:&quot;mbi_1&quot;,&quot;kind&quot;:&quot;strategy&quot;,&quot;root_id&quot;:&quot;str_1&quot;,&quot;revision_id&quot;:&quot;strr_7&quot;,&quot;enabled&quot;:true,&quot;position&quot;:10},<br/>    {&quot;item_id&quot;:&quot;mbi_2&quot;,&quot;kind&quot;:&quot;trading_signal&quot;,&quot;root_id&quot;:&quot;sig_1&quot;,&quot;revision_id&quot;:&quot;sigr_3&quot;,&quot;enabled&quot;:true,&quot;position&quot;:20},<br/>    {&quot;item_id&quot;:&quot;mbi_3&quot;,&quot;kind&quot;:&quot;trade_log&quot;,&quot;root_id&quot;:&quot;log_1&quot;,&quot;revision_id&quot;:&quot;logr_2&quot;,&quot;enabled&quot;:true,&quot;position&quot;:30}<br/>  ],<br/>  &quot;equity_allocation_mode&quot;: false,<br/>  &quot;created_by_actor_id&quot;: &quot;actor_...&quot;,<br/>  &quot;created_at&quot;: &quot;UTC timestamp&quot;<br/>}</th>
  </tr>
</table>

## 9.3 Composition Hash / Ready Stale Kuralları

<table>
  <tr>
    <th>Change</th>
    <th>New snapshot / hash?</th>
    <th>Ready report effect</th>
  </tr>
  <tr>
    <td>Row expanded/collapsed</td>
    <td>No.</td>
    <td>Current report remains valid.</td>
  </tr>
  <tr>
    <td>Display label override only</td>
    <td>No, if presentation-only.</td>
    <td>Current report remains valid.</td>
  </tr>
  <tr>
    <td>Item add, soft delete/detach, enable/disable</td>
    <td>Yes.</td>
    <td>Current report becomes STALE.</td>
  </tr>
  <tr>
    <td>Pinned revision changes</td>
    <td>Yes.</td>
    <td>Current report becomes STALE.</td>
  </tr>
  <tr>
    <td>Strategy/Signal/Log new revision saved but not pinned</td>
    <td>No.</td>
    <td>Current report remains valid for old pin.</td>
  </tr>
  <tr>
    <td>Strategy/Signal/Log new revision saved and explicitly pinned</td>
    <td>Yes.</td>
    <td>Current report becomes STALE.</td>
  </tr>
  <tr>
    <td>Equity Allocation mode/share/capital changes</td>
    <td>Yes.</td>
    <td>Current report becomes STALE.</td>
  </tr>
  <tr>
    <td>Run profile / engine/execution assumption changes</td>
    <td>Yes.</td>
    <td>Current report becomes STALE.</td>
  </tr>
  <tr>
    <td>Result summary opens/closes</td>
    <td>No.</td>
    <td>No effect on composition readiness.</td>
  </tr>
</table>

## 9.4 Domain Events and Read Model Refresh

Mainboard mutations commit after authorization, idempotency, expected_head_revision_id, lifecycle/dependency validation, mutation, composition fingerprint recomputation, audit write and outbox append succeed in one transaction. Event consumer failure must not make the core transaction ambiguous.

<table>
  <tr>
    <th>mainboard_item_attached<br/>mainboard_item_revision_pinned<br/>mainboard_item_disabled<br/>mainboard_composition_changed<br/>mainboard_snapshot_created<br/>ready_report_staled</th>
  </tr>
</table>

• UI, allocation projection, Agent Coordinator and event-stream consumers server eventleri tüketebilir; ancak UI local cachei source of truth değildir.

• Event delivery at-least-once olabilir. Client `sequence_no` ile de-duplicate etmeli; event re-delivery Result veya item duplication yaratmamalıdır.

• Refetch/re-hydrate sonrası row state, available actions, report currentness ve result summary backend responseundan tekrar render edilir.

## 9.5 Minimum Command/API Contract

<table>
  <tr>
    <th>Logical route / command</th>
    <th>Input</th>
    <th>Server guarantees</th>
  </tr>
  <tr>
    <td>`GET /mainboards/default`</td>
    <td>Actor context.</td>
    <td>Default workspace, active items, pinned revisions, allowed actions, ready projection, latest result summary projection.</td>
  </tr>
  <tr>
    <td>`POST /strategy-drafts`</td>
    <td>Initial optional metadata, idempotency key.</td>
    <td>Draft bootstrap; no implicit Run eligibility.</td>
  </tr>
  <tr>
    <td>`POST /external-work-object-drafts`</td>
    <td>`kind=trading_signal|trade_log`, source metadata, idempotency key.</td>
    <td>External draft/import staging; kind enum validation.</td>
  </tr>
  <tr>
    <td>`POST /mainboards/{id}/items`</td>
    <td>`root_id`, `revision_id`, position, idempotency key.</td>
    <td>Attach only if kind/root/revision/policy/lifecycle valid; composition change event.</td>
  </tr>
  <tr>
    <td>`PATCH /mainboard-items/{id}`</td>
    <td>`pinned_revision_id`, `is_enabled`, `position_index`, `expected_row_version`.</td>
    <td>expected_head_revision_id guard; new composition fingerprint; stale report projection.</td>
  </tr>
  <tr>
    <td>`POST /mainboards/{id}/snapshots`</td>
    <td>Optional purpose `ready_check|agent_research`.</td>
    <td>Immutable snapshot from current enabled persisted items.</td>
  </tr>
  <tr>
    <td>`POST /mainboards/{id}/ready-checks`</td>
    <td>`snapshot_id` or atomic current snapshot command.</td>
    <td>Immutable readiness report with status/issues/fingerprint.</td>
  </tr>
  <tr>
    <td>`POST /backtest-runs`</td>
    <td>`ready_report_id`, `composition_snapshot_id`, `expected_composition_hash`, idempotency key.</td>
    <td>Current preflight verification, immutable manifest, one BacktestRun queued or same idempotent response.</td>
  </tr>
  <tr>
    <td>`DELETE /work-objects/{root_id}`</td>
    <td>`reason?`, idempotency key.</td>
    <td>Soft delete preflight; active item removal; Trash Entry + audit/outbox on commit.</td>
  </tr>
  <tr>
    <td>`GET /backtest-runs/{id}` + event stream</td>
    <td>Run id, actor policy.</td>
    <td>Durable run state/events; UI closure does not cancel worker.</td>
  </tr>
  <tr>
    <td>`GET /backtest-results/{id}`</td>
    <td>Result id, actor policy.</td>
    <td>Read-only immutable artifact projection; never recalculates using current Mainboard.</td>
  </tr>
</table>

# 10. Agent İlişkisi ve UI’siz Tool/API Eşdeğeri

Mainboard, Agent’ın çalışabileceği bir kontrol yüzeyi olabilir; fakat Agentın ana araştırma döngüsünün zorunlu çalışma ortamı değildir. Alpha Agent backend üzerinde task queue, coordinator, checkpoint store, artifact store ve Tool Gateway ile sürekli çalışır. Mainboard UI’nın açık/kapalı olması, accordion statei, normal Lab Assistant discussionı veya human login/logoutu Agentın devamını belirlemez.

## 10.1 Tool Parity Contract

<table>
  <tr>
    <th>Human UI intent</th>
    <th>Agent Tool/API eşdeğeri</th>
    <th>Agent policy / output</th>
  </tr>
  <tr>
    <td>Add Strategy</td>
    <td>`CreateStrategyDraft` / `POST /strategy-drafts`.</td>
    <td>Agent own work object draftı oluşturur; provenance actor=Agent, task/checkpoint refs taşır.</td>
  </tr>
  <tr>
    <td>Save / revise Strategy</td>
    <td>`SaveStrategyRevision` / domain service.</td>
    <td>Same schema/validation; Agent bypass pathı yoktur. Agent yalnız own normal rootunu mutate eder.</td>
  </tr>
  <tr>
    <td>Add Trading Signal / Trade Log</td>
    <td>`CreateExternalWorkObjectDraft(kind)`; import/source tools.</td>
    <td>External object source/import evidence ve available-time rule üretilir. Agent package enumunu genişletemez.</td>
  </tr>
  <tr>
    <td>Attach / pin Mainboard item</td>
    <td>`AttachMainboardItem`, `PinMainboardRevision`.</td>
    <td>Agent own agent_research workspaceinde bağımsız composition kurar. Human private boarda automatic attach yapmaz.</td>
  </tr>
  <tr>
    <td>Ready Check</td>
    <td>`RequestCompositionReadiness`.</td>
    <td>Same validators; blockerlar Agent taskına structured issue/artifact olarak döner.</td>
  </tr>
  <tr>
    <td>RUN</td>
    <td>`RequestBacktestRun`.</td>
    <td>Same current report/fingerprint/idempotency preflight. Run id Agent checkpointine dependency olarak kaydedilir.</td>
  </tr>
  <tr>
    <td>Observe run</td>
    <td>`GetRunStatus`, event subscription.</td>
    <td>Agent result beklerken checkpoint yazıp bağımsız tasklara devam edebilir.</td>
  </tr>
  <tr>
    <td>Delete own output</td>
    <td>`SoftDeleteWorkObject`.</td>
    <td>Agent only own root output; Agent Trash görüntüleyemez, restore/purge yapamaz.</td>
  </tr>
  <tr>
    <td>Suggest human board addition</td>
    <td>`CreateCandidate` / artifact / queued directive context.</td>
    <td>Human Mainboarda zorla row eklemez. Explicit policy-controlled attach/pin gerekir.</td>
  </tr>
</table>

## 10.2 Agent Workspace Ayrımı

• Human default Mainboard: Human kullanıcıya ait aktif compositiondır. Agent yalnız policy izinli shared/published kaynakları use edebilir; human private rootu izinsiz mutate/delete edemez.

• Agent research workspace: `workspace_kind=agent_research` olan agent-owned compositiondur. Agent varyasyon/hipotez/backtest adaylarını burada oluşturabilir; UI’de görünür hale getirilmesi ayrı product policy/attachment kararıdır.

• Candidate / recommendation boundary: Agent outputu bir artifact, draft veya candidate olarak insana sunulabilir. Bir resultın veya Strategy draftının varlığı onu human default Mainboarda otomatik eklemez.

• Directive boundary: Admin/Supervisor directive durable queueya yazılır ve Agent tarafından safe checkpointte değerlendirilir. Normal discussion, active Mainboard/Run commandini anında değiştirmez.

<table>
  <tr>
    <th>CANONICAL RULE — AGENT PARITY<br/>UI Button -&gt; API Command -&gt; Domain Service -&gt; Persistent Object/Async Job hattı ile Agent Tool -&gt; same API Command/Domain Service -&gt; same Persistent Object/Async Job hattı aynı iş kuralını kullanmalıdır. UIya özel gizli business logic veya Agent için UI bypassı oluşturulamaz.</th>
  </tr>
</table>

# 11. Validation, Hata, Concurrency ve Recovery

## 11.1 Validation Katmanları

<table>
  <tr>
    <th>Katman</th>
    <th>Mainboard örneği</th>
    <th>Server davranışı</th>
    <th>UI / Agent recovery</th>
  </tr>
  <tr>
    <td>Field/action validation</td>
    <td>Add Package submitte type/package yok.</td>
    <td>422 validation; command başlamaz.</td>
    <td>Required field marker; select type + package; retry.</td>
  </tr>
  <tr>
    <td>Kind validation</td>
    <td>`mainboard_item.kind=trading_signal` ama root Strategy.</td>
    <td>422 `MAINBOARD_ITEM_KIND_MISMATCH`.</td>
    <td>UI item eklemez; source selection refresh.</td>
  </tr>
  <tr>
    <td>Persistence validation</td>
    <td>Transient draft, root/revision oluşmadan Ready Check.</td>
    <td>422 `UNSAVED_MAINBOARD_DRAFT`.</td>
    <td>Save or Discard action; no manifest entry.</td>
  </tr>
  <tr>
    <td>Lifecycle validation</td>
    <td>Deleted/soft-deleted revision pinlenmek istenir.</td>
    <td>409 `OBJECT_NOT_ACTIVE` / lifecycle blocked.</td>
    <td>Choose active revision, restore (Admin) or replace dependency.</td>
  </tr>
  <tr>
    <td>Dependency validation</td>
    <td>External file selected but normalized import revision yok.</td>
    <td>Ready Check blocker.</td>
    <td>Complete ingestion/parse/validation; attach only validated revision.</td>
  </tr>
  <tr>
    <td>Data/time validation</td>
    <td>Signal available-time/mapping missing; Trade Log timestamp order invalid.</td>
    <td>Blocker; no Run manifest.</td>
    <td>Fix source mapping/import validation; create new revision.</td>
  </tr>
  <tr>
    <td>Authorization validation</td>
    <td>User tries to attach/edit private other-owner root.</td>
    <td>403 `ACCESS_DENIED` / `OBJECT_EDIT_FORBIDDEN`.</td>
    <td>Remove optimistic UI; request sharing or use allowed source.</td>
  </tr>
  <tr>
    <td>Composition validation</td>
    <td>No enabled item; duplicate enabled same working object.</td>
    <td>Ready Check `COMPOSITION_EMPTY` or duplicate blocker.</td>
    <td>Add/enable valid item; remove duplicate/disable one.</td>
  </tr>
  <tr>
    <td>Readiness currentness</td>
    <td>Item/strategy/allocation changed after Ready Check.</td>
    <td>409 `READY_REPORT_STALE` on RUN.</td>
    <td>Fresh Ready Check; no silent auto-run.</td>
  </tr>
  <tr>
    <td>Concurrency validation</td>
    <td>Another actor changed row version/pin/order.</td>
    <td>409 `ROW_VERSION_CONFLICT`.</td>
    <td>Reload canonical row; merge/retry with current row_version.</td>
  </tr>
  <tr>
    <td>Active job validation</td>
    <td>Delete root used by queued/running run.</td>
    <td>409 `OBJECT_IN_ACTIVE_RUN` / delete blocked.</td>
    <td>Wait or use controlled run cancellation; do not detach input from active manifest.</td>
  </tr>
  <tr>
    <td>Async job failure</td>
    <td>Worker cannot resolve manifest asset.</td>
    <td>Run FAILED; error/diagnostics persistent; no Result.</td>
    <td>Fix source; Retry creates new run id + manifest, never overwrites failed run.</td>
  </tr>
</table>

## 11.2 Structured Error Envelope

<table>
  <tr>
    <th>IMPLEMENTATION DECISION — NON-CANONICAL GAP RESOLUTION<br/>Mainboard-facing backend errors will use a stable, machine-readable response envelope. Master names key domain codes but does not prescribe a single response JSON shape. The following envelope is selected so UI and Agent recovery consume the same information.</th>
  </tr>
</table>

<table>
  <tr>
    <th>{<br/>  &quot;error&quot;: {<br/>    &quot;code&quot;: &quot;READY_REPORT_STALE&quot;,<br/>    &quot;message&quot;: &quot;Changes detected. Run Backtest Ready Check again.&quot;,<br/>    &quot;category&quot;: &quot;concurrency_or_preflight&quot;,<br/>    &quot;field_issues&quot;: [],<br/>    &quot;retryable&quot;: true,<br/>    &quot;suggested_action&quot;: &quot;rerun_ready_check&quot;,<br/>    &quot;correlation_id&quot;: &quot;cmd_...&quot;<br/>  }<br/>}</th>
  </tr>
</table>

## 11.3 Stale/Concurrency Resolution Contract

1. Client mutating requesti target `row_version` veya draft revision versionını taşır.

2. Server `FOR UPDATE` veya equivalent concurrency guard ile current statei yükler.

3. expected_head_revision_id farklıysa mutation uygulanmaz; current canonical item/draft summary, changed paths veya refetch token döner.

4. Frontend optimistic row stateini rollback eder; `This item changed in another session…` bannerını gösterir.

5. Kullanıcı diff/merge gerektiren Strategy Details formunda latest draftı açar; Mainboard item pin/order mutationında server statei reload edilir.

6. Agent task conflict yaşarsa task `blocked_by_concurrency` reasonıyla checkpoint/Artifact yazar; human editorı overwrite etmez.

# 12. Lifecycle, Audit ve Trash Etkileri

## 12.1 Root / Draft / Revision / Snapshot Ayrımı

<table>
  <tr>
    <th>Katman</th>
    <th>Mutable mi?</th>
    <th>Mainboard etkisi</th>
    <th>Historical impact</th>
  </tr>
  <tr>
    <td>Transient UI draft</td>
    <td>Evet; client/editor session.</td>
    <td>V18 host rowu olarak görünür olabilir; Ready/Run inputu değildir.</td>
    <td>Discard edilirse historical record/Trash yok.</td>
  </tr>
  <tr>
    <td>Work Object root</td>
    <td>Head pointer/lifecycle/deletion metadata kontrollü mutable.</td>
    <td>Mainboard item roota referans verir.</td>
    <td>Root soft delete sonrası old runs/manifests historical provenance taşımayı sürdürür.</td>
  </tr>
  <tr>
    <td>Immutable Work Object revision</td>
    <td>Hayır.</td>
    <td>Item exact `pinned_revision_id` taşır.</td>
    <td>Old result/run exact revisionu kaybetmez.</td>
  </tr>
  <tr>
    <td>Mainboard item</td>
    <td>Controlled mutable: pin/enable/order/display metadata.</td>
    <td>Composition identity, snapshot eligibility ve Ready currentnessi belirler.</td>
    <td>Item mutation new hash/stale report üretir; old snapshotlar immutable kalır.</td>
  </tr>
  <tr>
    <td>Composition snapshot / Ready report</td>
    <td>Hayır.</td>
    <td>Run eligibility evidence.</td>
    <td>Historical run decisionleri açıklanabilir kalır.</td>
  </tr>
  <tr>
    <td>BacktestRun manifest</td>
    <td>Hayır.</td>
    <td>Worker inputu.</td>
    <td>Yeni board editleri running/complete runı değiştiremez.</td>
  </tr>
  <tr>
    <td>BacktestResult</td>
    <td>Hayır; result root deletion state ayrı.</td>
    <td>Mainboard yalnız latest summary projection gösterir.</td>
    <td>Result soft delete görünümden kaldırır; Run identity/input provenance korunur.</td>
  </tr>
</table>

## 12.2 Soft Delete / Restore Rules

<table>
  <tr>
    <th>Operation</th>
    <th>Who</th>
    <th>Transaction effect</th>
    <th>Mainboard / history effect</th>
  </tr>
  <tr>
    <td>Delete Strategy / Signal / Trade Log</td>
    <td>Admin any; Supervisor/User own; Agent own output only.</td>
    <td>Preflight -&gt; immutable Trash Entry snapshot -&gt; root `soft_deleted` -&gt; audit -&gt; outbox commit.</td>
    <td>Active row disappears; no new selection/attach; old snapshot/run/result references stay intact.</td>
  </tr>
  <tr>
    <td>Delete result summary</td>
    <td>Result policy owner/Admin; UI action does not delete run or source items.</td>
    <td>Result root soft delete + Trash/audit.</td>
    <td>Mainboard latest projection refreshes; Results History active index removes result; run provenance remains.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>Admin only.</td>
    <td>Restore preflight -&gt; root `ACTIVE` using same root ID/current revision pointer -&gt; Trash entry RESTORED -&gt; audit/outbox.</td>
    <td>Original board location restore attempt; current Ready status not assumed valid; new Ready Check required.</td>
  </tr>
  <tr>
    <td>Permanent delete / purge</td>
    <td>Admin only; async job.</td>
    <td>Purge Pending -&gt; retention/dependency checks -&gt; cleanup; tombstone/audit minimum evidence retained.</td>
    <td>Not a Mainboard × action. Running run/task or immutable evidence may block purge.</td>
  </tr>
  <tr>
    <td>Discard transient draft</td>
    <td>Current editor actor.</td>
    <td>Local draft closes; optional DRAFT_DISCARDED audit only.</td>
    <td>No root, no Trash, no result/history impact.</td>
  </tr>
</table>

## 12.3 Mainboard Audit Events

<table>
  <tr>
    <th>Event</th>
    <th>When written</th>
    <th>Minimum audit context</th>
  </tr>
  <tr>
    <td>`mainboard_item_attached`</td>
    <td>Persisted root/revision attached.</td>
    <td>Actor, workspace, item id/kind/root/revision, source/provenance, correlation id.</td>
  </tr>
  <tr>
    <td>`mainboard_item_revision_pinned`</td>
    <td>Pin changed.</td>
    <td>Old/new revision IDs, row version, composition hash before/after.</td>
  </tr>
  <tr>
    <td>`mainboard_item_disabled`</td>
    <td>Enabled state changes.</td>
    <td>Old/new enabled state, item id, composition hash delta.</td>
  </tr>
  <tr>
    <td>`mainboard_composition_changed`</td>
    <td>Any material item/order/enable/pin/alloc change.</td>
    <td>Workspace, changed subjects, previous/current fingerprint.</td>
  </tr>
  <tr>
    <td>`mainboard_snapshot_created`</td>
    <td>Snapshot committed.</td>
    <td>Snapshot id, composition hash, actor/purpose.</td>
  </tr>
  <tr>
    <td>`ready_report_staled`</td>
    <td>Current report invalidated by relevant change.</td>
    <td>Old report id/hash, triggering command/change.</td>
  </tr>
  <tr>
    <td>`backtest_run_requested`</td>
    <td>RUN accepted.</td>
    <td>Run id, report/snapshot/manifest hash, actor/idempotency/correlation id.</td>
  </tr>
  <tr>
    <td>`entity.delete.completed`</td>
    <td>Soft delete commit.</td>
    <td>Trash entry id, before/after delete state, original location, actor.</td>
  </tr>
  <tr>
    <td>`trash.restore.completed`</td>
    <td>Admin restore commit.</td>
    <td>Trash entry, root, actor, repair/fallback details.</td>
  </tr>
  <tr>
    <td>`run.completed` / `run.failed` / `run.cancelled`</td>
    <td>Worker terminal state.</td>
    <td>Run id, terminal status, result id if succeeded, diagnostics/ref reason.</td>
  </tr>
  <tr>
    <td>`result.materialized`</td>
    <td>Succeeded Run produced Result.</td>
    <td>Result id, run id, artifact summary and manifest reference.</td>
  </tr>
</table>

<table>
  <tr>
    <th>CANONICAL RULE — HISTORICAL INTEGRITY<br/>Bir Strategy, Trading Signal, Trade Log, Package veya Dataset daha sonra düzenlense ya da soft-delete edilse bile önceki Backtest Run manifesti ve succeeded Result kendi pinlenmiş revision/asset snapshotıyla okunabilir kalır. Mainboard UI, historical Result detailini current board state veya “latest” resource üzerinden yeniden yazamaz.</th>
  </tr>
</table>

# 13. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Kontrat alanı</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Workspace identity</td>
    <td>HTML initial workspace DOM listesi; `currentUser=guest`/demo role behavior.</td>
    <td>Per human Default Mainboard persisted; Agent uses separate agent_research workspace; anonymous != registered User.</td>
    <td>V18 demo identity state backend authority olarak taşınmaz. Route loads canonical workspace by principal.</td>
  </tr>
  <tr>
    <td>Row creation</td>
    <td>Buttons append DOM row; counters `strategyCount`, `signalCount`, `tradeLogCount` generate labels.</td>
    <td>Server UUID root/revision/item identities; draft vs persisted distinction.</td>
    <td>Counters only prototype labels. Production uses immutable IDs and `Unsaved` badge for non-persisted drafts.</td>
  </tr>
  <tr>
    <td>Package picker types</td>
    <td>Strategy, Trading Signal, Trade Log options; selected object creates corresponding row.</td>
    <td>Only Strategy Package may create derived Strategy Draft; Signal/Trade Log come from Add Outsource Signal external-object flow.</td>
    <td>Remove Signal/Trade Log from Add Package UI/API. Never add them to PackageKind enum.</td>
  </tr>
  <tr>
    <td>Signal / log labels</td>
    <td>Rows may say `TRADING SIGNAL PACKAGE` / `TRADE LOG PACKAGE`.</td>
    <td>Canonical terms are Trading Signal and Trade Log external working objects.</td>
    <td>Migrate visible labels, API values and database enums. Old label is V18 observation only.</td>
  </tr>
  <tr>
    <td>Row expansion</td>
    <td>CSS class / DOM panel toggle.</td>
    <td>Presentation-only UI state.</td>
    <td>Keep interaction; do not create revision/audit/stale result.</td>
  </tr>
  <tr>
    <td>Ready state</td>
    <td>Client boolean `backtestReady`, DOM scans, red/green status bar.</td>
    <td>Immutable Ready Check Report bound to server composition hash; RUN preflight repeats validation.</td>
    <td>Replace local bool with report/fingerprint state. Any relevant change stales report.</td>
  </tr>
  <tr>
    <td>RUN</td>
    <td>Immediate local demo result with fixed sample metrics/history record.</td>
    <td>Async BacktestRun queue worker; only succeeded run materializes immutable Result.</td>
    <td>RUN never computes in browser; failed/cancelled run produces no normal result card.</td>
  </tr>
  <tr>
    <td>Result row</td>
    <td>Created below Mainboard and can be deleted via generic local Trash helper.</td>
    <td>Latest succeeded Result summary projection, read-only, result_id based; detailed result is separate page contract.</td>
    <td>Use actual immutable Result metrics only. Result deletion never deletes its run/inputs.</td>
  </tr>
  <tr>
    <td>Delete ×</td>
    <td>DOM remove + local Trash entry; immediate effect.</td>
    <td>Confirmation -&gt; server preflight -&gt; root soft delete + Trash/audit/outbox. Active run input blocks deletion.</td>
    <td>Use type-specific label and failure recovery. Do not use row removal as proof of success.</td>
  </tr>
  <tr>
    <td>Trade Log import</td>
    <td>Client-side parsing / file selection used in demo flows.</td>
    <td>Ingestion worker produces immutable source asset, parse report, skipped rows, canonical revision and validation evidence.</td>
    <td>File input value is not Ready Check evidence.</td>
  </tr>
  <tr>
    <td>Allocation binding</td>
    <td>DOM row names / initial-capital fields used as source.</td>
    <td>Allocation references `mainboard_working_item_id` / exact composition item.</td>
    <td>Do not bind by display name or visual index.</td>
  </tr>
  <tr>
    <td>Agent use</td>
    <td>V18 can simulate Agent login/menu visibility.</td>
    <td>Agent is a non-login backend system actor with Tool Gateway/API parity.</td>
    <td>Do not require browser automation, UI login or open Mainboard for Agent work.</td>
  </tr>
</table>

## 13.1 Explicit Alignment Decisions

<table>
  <tr>
    <th>IMPLEMENTATION DECISION — RESULT PROJECTION POLICY<br/>V18 supports one local “current result” card. Production Mainboard will display at most one **latest succeeded Result summary projection per active workspace**, ordered by completed_at descending. This projection is not an additional Result entity and is not a replacement for Results History. This decision preserves V18 visual simplicity while respecting the canonical Result/History model.</th>
  </tr>
</table>

<table>
  <tr>
    <th>IMPLEMENTATION DECISION — EMPTY STATE AND UNSAVED AFFORDANCE<br/>V18 has no explicit Mainboard empty-state or Unsaved badge. Production will add both. The decisions make the canonical persisted-vs-transient boundary visible and prevent the user from assuming that an open form row will be included in Ready Check/RUN.</th>
  </tr>
</table>

<table>
  <tr>
    <th>IMPLEMENTATION DECISION — ENDPOINT ENVELOPE<br/>Master specifies required command semantics and several route examples but not a universal API error body. Mainboard uses the structured envelope in §11.2 so UI and Agent recovery share error code, suggested action and correlation information.</th>
  </tr>
</table>

# 14. Kodcu AI İçin Implementation Rules

1. Mainboardu client-side array veya DOM listesi olarak kalıcı source of truth yapma. Persisted Mainboard Workspace and Item projectionini backendden oku ve mutasyon sonrası canonical response ile rehydrate et.

2. MainboardWorkingItem `item_kind` enumunu yalnız `strategy | trading_signal | trade_log` ile sınırla. Trading Signal veya Trade Logu PackageKind enumuna ekleme.

3. Her persisted Mainboard itemde `work_object_root_id` ve `pinned_revision_id` zorunlu olsun. “Use latest revision” veya displayed name üzerinden implicit resolution yapma.

4. Transient draft ile persisted root/revisionı ayrı state katmanlarında tut. Unsaved UI rowu Ready Check veya Run manifestine dahil etme.

5. Add Package akışında yalnız Strategy Package -> Derived Strategy Draft yolunu uygula. Indicator/Condition top-level Mainboard rowu yapma; Signal/Trade Log için Add Outsource Signal kullan.

6. Add Package source seçimini display name ile persist etme. `source_package_root_id` + `source_package_revision_id` + provenance/dependency setini sakla.

7. Expanded/collapsed UI stateini business mutation olarak işleme. Arrow toggle revision üretmez, composition hash değiştirmez ve audit zorunluluğu doğurmaz.

8. Item add/delete/enable/pin/reorder/allocation link değişikliğinde server composition fingerprintini transaction içinde yeniden hesapla ve matching Ready reportları STALE yap.

9. Ready Checki yalnız UI validationı olarak yapma. Server-side immutable snapshot, validator seti ve immutable report üret; RUN kabulünde current fingerprint/preflightı tekrar doğrula.

10. RUN komutunu synchronous engine calla dönüştürme. BacktestRun + immutable manifest kaydı oluştur; job queue/worker yürütür; UI closure workerı durdurmaz.

11. Failed veya Cancelled run için Backtest Result, Results History satırı veya Mainboard result summary oluşturma. Failure/cancellation diagnostics/audit ayrı tutulur.

12. Backtest workerın current Mainboard DOMunu, local storageı veya latest Package/Data lookupını okumayı yasakla. Worker yalnız Run Manifestte pinlenen inputs/asset checksums/policies ile çalışsın.

13. Mutations ve RUN için idempotency key uygula. Aynı key aynı logical resultı döndürmeli; duplicate row veya duplicate worker job yaratmamalıdır.

14. Item PATCH/reorder/pin/enable commandlerinde `expected_row_version` kullan. Last-write-wins yapma; mismatchte `ROW_VERSION_CONFLICT` döndür.

15. × actionı “remove row” değil type-specific Delete Work Object intentidir. Confirmation + server preflight olmadan UI actionı kesin delete state göstermesin.

16. Soft delete rootu ACTIVE listelerden kaldırmalı; Trash Entry, audit event ve outbox event aynı transactionda oluşmalı. Bu parçalardan biri başarısızsa delete transactionını rollback et.

17. Running/Queued BacktestRun manifestinde input olan rootun delete veya purge işlemini block et. Active manifestin referansını UI tarafından koparma.

18. Restore yalnız Admin tarafından çalıştırılmalı; aynı root ID/current revision pointerı ACTIVEye döndürmeli; yeni revision üretmemeli; fresh Ready Check gerektirmelidir.

19. Allocation bağlarını display name veya `Strategy N` sayısı ile değil `mainboard_working_item_id` ile kur. Visual order engine priority veya allocation identity değildir.

20. Mainboard latest Result summaryni Result artifactinden read-only olarak render et. Metrikleri frontendde tekrar hesaplama veya V18 demo sayılarını default gerçek veri gibi gösterme.

21. Human UI actionları ile Agent Tool Gateway aynı command/service policy setini kullanmalı. Agent browser/tıklama/logout/chat stateine bağımlı çalıştırılmamalıdır.

22. Agentın insan default Mainboarduna otomatik item eklemesini yasakla. Human-facing attach/pin için açık policy, provenance ve action gerekir.

23. UI hidden/disabled stateini authorization doğrusu sayma. Direct API çağrısında server actor/role/owner/visibility/lifecycle validationını mutlaka yeniden yap.

24. Future Dev / Live Trade davranışını Mainboard RUNa bağlama. RUN yalnız backtest orchestrationdır; real broker/exchange side effect üretmez.

## 14.1 Forbidden Shortcuts

<table>
  <tr>
    <th>Yasak shortcut</th>
    <th>Neden yanlış</th>
    <th>Doğru yön</th>
  </tr>
  <tr>
    <td>`document.querySelectorAll()` ile Ready Check business state üretmek</td>
    <td>DOM eksik/stale olabilir; unsaved/persisted, visibility ve server dependency bilgisi taşımaz.</td>
    <td>Server snapshot + validator services + immutable report.</td>
  </tr>
  <tr>
    <td>Signal/Trade Logu Package listesine type olarak eklemek</td>
    <td>CR-01 domain ayrımını bozar.</td>
    <td>Add Outsource Signal -&gt; external work object flow.</td>
  </tr>
  <tr>
    <td>Row titleyı object identity kabul etmek</td>
    <td>Ad değişebilir/tekrarlanabilir; allocation/audit/result yanlış eşleşir.</td>
    <td>UUID root/item/revision identifiers.</td>
  </tr>
  <tr>
    <td>Result cardı Mainboard item saymak</td>
    <td>Result immutable output artifacttir, input composition itemi değildir.</td>
    <td>Result summary projection to `result_id`.</td>
  </tr>
  <tr>
    <td>Ready booleanı client requestinden kabul etmek</td>
    <td>Tamper/stale composition riskini taşır.</td>
    <td>Server verifies current report/hash/preflight.</td>
  </tr>
  <tr>
    <td>Save sonrası latest revisionı otomatik kullanmak</td>
    <td>Historical reproducibility ve user intent bozulur.</td>
    <td>Explicit pin revision mutation.</td>
  </tr>
  <tr>
    <td>Delete sırasında immediate hard delete</td>
    <td>Trash/restore/audit/historical integrity bozulur.</td>
    <td>Soft delete + Trash Entry + audit + retention-aware purge.</td>
  </tr>
  <tr>
    <td>Agentı UI botu yapmak</td>
    <td>Browser lifecycle bağlılığı ve separate behavior path üretir.</td>
    <td>Tool Gateway -&gt; same domain command -&gt; same backend state.</td>
  </tr>
</table>

# 15. Acceptance Tests

Aşağıdaki senaryolar Mainboard sayfasının “görünüyor” olmasından ziyade UI, authorization, persistence, snapshot, async execution, lifecycle, Agent parity ve historical integrity açısından tamam olduğunu doğrular.

<table>
  <tr>
    <th>#</th>
    <th>Scenario</th>
    <th>Expected result</th>
  </tr>
  <tr>
    <td>1</td>
    <td>Anonymous visitor opens Mainboard route.</td>
    <td>Private/default human items are not leaked. UI shows permitted restricted/intro state; create/Ready/RUN mutations are rejected server-side.</td>
  </tr>
  <tr>
    <td>2</td>
    <td>Authenticated User opens default Mainboard with zero items.</td>
    <td>Empty-state title/body/action text appears. RUN is disabled. Ready Check returns composition-empty blocker.</td>
  </tr>
  <tr>
    <td>3</td>
    <td>User clicks Add Strategy but does not save.</td>
    <td>Transient `Unsaved` row appears. It has no root/revision/item identity. Ready Check returns `UNSAVED_MAINBOARD_DRAFT`; manifest excludes it.</td>
  </tr>
  <tr>
    <td>4</td>
    <td>User saves valid Strategy Draft.</td>
    <td>Strategy root + immutable revision + Mainboard item with exact pinned revision are created. Audit includes creation/attach. Ready becomes stale/not-ready.</td>
  </tr>
  <tr>
    <td>5</td>
    <td>User creates Strategy revision 2 without pinning it.</td>
    <td>Mainboard item still points revision 1. New snapshot and old result use revision 1; no implicit latest behavior.</td>
  </tr>
  <tr>
    <td>6</td>
    <td>User explicitly pins revision 2.</td>
    <td>Item update requires current row_version, new composition hash is generated, prior Ready report becomes STALE.</td>
  </tr>
  <tr>
    <td>7</td>
    <td>User opens/closes row arrow only.</td>
    <td>Presentation changes; no revision, no changed composition hash, no stale report, no audit requirement.</td>
  </tr>
  <tr>
    <td>8</td>
    <td>User adds Trading Signal through Add Outsource Signal.</td>
    <td>External work object kind `trading_signal` is created after source/mapping validation. PackageKind enum and Package Library API remain unchanged.</td>
  </tr>
  <tr>
    <td>9</td>
    <td>User adds Trade Log with selected file but unfinished import.</td>
    <td>Ready Check fails; file input value alone is not accepted. Normalized validated import revision is required.</td>
  </tr>
  <tr>
    <td>10</td>
    <td>User opens Add Package.</td>
    <td>Production picker lists only usable Strategy Package revisions. Trading Signal and Trade Log are not package picker types.</td>
  </tr>
  <tr>
    <td>11</td>
    <td>User creates derived Strategy from Strategy Package.</td>
    <td>New Strategy Draft provenance carries source package root/revision and dependencies; original package remains unchanged.</td>
  </tr>
  <tr>
    <td>12</td>
    <td>User runs Ready Check with enabled persisted valid items.</td>
    <td>Server creates immutable snapshot/report. PASS/PASS_WITH_WARNINGS activates RUN only while fingerprint remains current.</td>
  </tr>
  <tr>
    <td>13</td>
    <td>User changes Strategy execution/data/entry rule after Ready Check.</td>
    <td>Report becomes STALE, RUN UI locks, and direct run request with old report/hash returns `READY_REPORT_STALE`/409.</td>
  </tr>
  <tr>
    <td>14</td>
    <td>Client posts RUN with `ready=true` but no valid report.</td>
    <td>Server rejects; no BacktestRun/job created.</td>
  </tr>
  <tr>
    <td>15</td>
    <td>Same RUN request is sent twice with same idempotency key.</td>
    <td>One BacktestRun exists or same run id is returned; no duplicate worker job.</td>
  </tr>
  <tr>
    <td>16</td>
    <td>User closes browser while BacktestRun is RUNNING.</td>
    <td>Worker continues from immutable manifest. UI later fetches current state/events successfully.</td>
  </tr>
  <tr>
    <td>17</td>
    <td>Run succeeds.</td>
    <td>Exactly one immutable Backtest Result is materialized; latest summary projection displays artifact-derived metrics; History indexes the result.</td>
  </tr>
  <tr>
    <td>18</td>
    <td>Run fails or is cancelled.</td>
    <td>No normal Backtest Result, no History row, no Mainboard result summary. Failure/cancel diagnostics/audit remain available.</td>
  </tr>
  <tr>
    <td>19</td>
    <td>User deletes own Strategy not used by active run.</td>
    <td>Confirmation -&gt; root soft_deleted -&gt; row removed -&gt; Trash Entry/audit/outbox created. Old completed result manifests remain readable.</td>
  </tr>
  <tr>
    <td>20</td>
    <td>User tries deleting Strategy used by RUNNING/QUEUED run.</td>
    <td>Delete is blocked with `OBJECT_IN_ACTIVE_RUN`/DELETE_BLOCKED_BY_RUNNING_JOB. Root remains ACTIVE.</td>
  </tr>
  <tr>
    <td>21</td>
    <td>Non-Admin opens Trash or restore route.</td>
    <td>UI does not offer access and direct endpoint returns forbidden. No restore action occurs.</td>
  </tr>
  <tr>
    <td>22</td>
    <td>Admin restores a deleted Strategy.</td>
    <td>Same root ID/current revision pointer returns ACTIVE, original location reattaches where valid, audit writes; Ready must be rerun.</td>
  </tr>
  <tr>
    <td>23</td>
    <td>Two actors pin different revisions concurrently.</td>
    <td>One succeeds; stale expected row version receives 409. No last-write-wins overwrite.</td>
  </tr>
  <tr>
    <td>24</td>
    <td>Agent creates/revises own Strategy and requests Ready/Run without browser.</td>
    <td>Same schema/policy/preflight applies; provenance is Agent/task/checkpoint aware; human UI closure has no effect.</td>
  </tr>
  <tr>
    <td>25</td>
    <td>Agent attempts to edit a human private root.</td>
    <td>Server returns `OBJECT_EDIT_FORBIDDEN`; Agent task records policy block and continues its broader loop.</td>
  </tr>
  <tr>
    <td>26</td>
    <td>User changes display label or row title.</td>
    <td>Allocation/result/audit identity remains based on item/root/revision IDs; no accidental reassignment occurs.</td>
  </tr>
  <tr>
    <td>27</td>
    <td>An enabled item is disabled using future control/API.</td>
    <td>Item remains visible but excluded from composition snapshot, Ready Check and allocation. Report becomes stale.</td>
  </tr>
  <tr>
    <td>28</td>
    <td>A result summary opens after Mainboard has since changed.</td>
    <td>Result details still read immutable `result_id` artifact; never recompute metrics from current board state.</td>
  </tr>
  <tr>
    <td>29</td>
    <td>Result row is soft-deleted.</td>
    <td>Latest result projection and History active list refresh; BacktestRun and source manifest remain intact.</td>
  </tr>
  <tr>
    <td>30</td>
    <td>Worker tries resolving “latest” Package/Data instead of manifest revision.</td>
    <td>Run fails with manifest resolution/asset unavailable failure; worker does not silently substitute current resource.</td>
  </tr>
</table>

# 16. Final Consistency Check — Master Technical Reference Alignment

<table>
  <tr>
    <th>Kontrol</th>
    <th>Durum / karar</th>
  </tr>
  <tr>
    <td>Mainboard item türleri</td>
    <td>Uyumlu. Yalnız Strategy, Trading Signal, Trade Log. Indicator/Condition/Embedded System Package top-level row değildir.</td>
  </tr>
  <tr>
    <td>Trading Signal / Trade Log terminology</td>
    <td>Uyumlu. V18 legacy “Package” labels yalnız prototype observation olarak ayrıldı; Production canonical terminology external work objecttir.</td>
  </tr>
  <tr>
    <td>Default Mainboard + multi-board scope</td>
    <td>Uyumlu. Her human için Default Mainboard; schema multi-workspace hazır; multi-board management UI V1 kapsamı dışında.</td>
  </tr>
  <tr>
    <td>Persisted vs transient state</td>
    <td>Uyumlu. Unsaved draft Ready/Run inputu değildir; discard Trash üretmez.</td>
  </tr>
  <tr>
    <td>Pinned revision / latest rule</td>
    <td>Uyumlu. Exact root + revision pin zorunlu; implicit latest yasak.</td>
  </tr>
  <tr>
    <td>Snapshot / Ready Check / RUN</td>
    <td>Uyumlu. Immutable composition snapshot, current fingerprint, server-side preflight, async Run manifest; client boolean authority değil.</td>
  </tr>
  <tr>
    <td>Run / Result separation</td>
    <td>Uyumlu. Sadece succeeded run Result yaratır. Failed/cancelled run normal Result/History summary üretmez.</td>
  </tr>
  <tr>
    <td>Agent architecture</td>
    <td>Uyumlu. Agent UI/browser/session/chat bağımsız backend actor; same Tool/API/domain capability parity uygulanır.</td>
  </tr>
  <tr>
    <td>Soft delete / Trash</td>
    <td>Uyumlu. Normal delete soft delete + Trash/audit; restore/permanent delete yalnız Admin; active run input delete blocker.</td>
  </tr>
  <tr>
    <td>Historical integrity</td>
    <td>Uyumlu. Old runs/results exact manifests/revisions ile okunur; later edit/delete onları yeniden yazmaz.</td>
  </tr>
  <tr>
    <td>Portfolio allocation binding</td>
    <td>Uyumlu. Item display name/sırası değil mainboard_working_item_id üzerinden bağlanır.</td>
  </tr>
  <tr>
    <td>Future Dev boundary</td>
    <td>Uyumlu. Mainboard RUN yalnız backtest orchestrationdır; Live Trade/Future Dev side effecti üretmez.</td>
  </tr>
  <tr>
    <td>V18 vs Production distinction</td>
    <td>Uyumlu. Browser counters, DOM Ready bool, local Trash, demo result and legacy picker labels canonical backend davranışa dönüştürülmedi; ayrı Alignment Notes ile düzeltildi.</td>
  </tr>
  <tr>
    <td>Scope boundary</td>
    <td>Uyumlu. Strategy Details, external source/import field schemas, Portfolio form ve Result detailinin tam alan sözleşmeleri sonraki sayfa dokümanlarına ayrıldı; Mainboard host and composition responsibility bu belgede tam tanımlandı.</td>
  </tr>
</table>

<table>
  <tr>
    <th>FINAL IMPLEMENTATION POSITION<br/>Mainboard doğru uygulandığında, insan ve Agent üretimini aynı immutable backtest giriş standardına bağlayan kalıcı kompozisyon katmanıdır. Güvenilirlik satırın DOMda görünmesinden değil; persisted Work Object revisionlarından, explicit pinlerden, server-side composition snapshotından, current Ready Check reportundan, async BacktestRun manifestinden ve append-only audit/provenance zincirinden doğar.</th>
  </tr>
</table>
