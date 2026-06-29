---
title: "Entropia V18 — Add Package / Create Package Page Documentation v1.1"
page_number: 6
document_type: "Page implementation specification"
source_document: "Entropia_V18_Add_Package_Create_Package_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Add Package / Create Package Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | PAGE DOCUMENTATION 6/22 | ADD PACKAGE / CREATE PACKAGE
> **Original DOCX footer:** Canonical page documentation | Production V1 alignment |

ENTROPIA V18

ADD PACKAGE / CREATE PACKAGE

Sayfa Dokümantasyonu 6/22 | Strategy Package tabanlı Mainboard başlangıcı ve sürümlü Package üretim hattı sözleşmesi

<table>
  <tr>
    <th>Kapsam sınırı: Bu belge iki V18 yüzeyini kapsar: Mainboard &gt; Add Package popoverı ve Edit &gt; Create Package çalışma alanı. Pre-Check ayrıntı ekranı, Package Library, Embedded System Packages, Rationale Families, Mainboard, Strategy Details, Market Data, Ready Check, Results, Trash ve Analysis Lab ayrı sayfa dokümanlarının kapsamıdır. Bu belgede bu alanlar yalnız doğrudan bağımlılık, navigation handoff veya canonical sınır olarak anılır.</th>
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
    <td>Entropia V18 | Page Documentation 6/22 | Add Package / Create Package | v1.1</td>
  </tr>
  <tr>
    <td>Belge amacı</td>
    <td>V18deki Add Package popoverının legacy seçim modelini ve Create Package üretim yüzeyini; Production V1de canonical package type, request, candidate, draft revision, validation, approval/publish, Agent parity, audit ve lifecycle sözleşmesine indirmek.</td>
  </tr>
  <tr>
    <td>Kapsam</td>
    <td>Add Package type/package selector ve Mainboarda dönüşü; Create Package top controls, identity/compatibility, request workspace, Pre-Check entry action, candidate/draft controls, status projection, baseline upload, validation actions, approval/revision ve target-library projection.</td>
  </tr>
  <tr>
    <td>Kapsam dışı</td>
    <td>Pre-Check dependency-report ekranının ayrıntılı UI ve resolver yönetimi; Package Library list/detail ekranı; ESP yönetim ekranı; Rationale Families yönetimi; Strategy Details formu; Mainboard readiness/run/results; Trash UI.</td>
  </tr>
  <tr>
    <td>Kaynak önceliği</td>
    <td>1) Master Technical Reference v1.0, 2) V18 ana HTML, 3) Sayfa Bazlı Dokümantasyon Handoff ve Çalışma Standardı v1.1, 4) 2.3 POSITION ENTRY LOGIC örnek dokümanı.</td>
  </tr>
</table>

## 0.1 Source Traceability Map

<table>
  <tr>
    <th>Konu</th>
    <th>Master ref</th>
    <th>V18 HTML ref</th>
    <th>Çapraz bağımlılık / karar</th>
  </tr>
  <tr>
    <td>Create Package lifecycle</td>
    <td>Modül 8 §§1-4, §7-11, Canonical Integration CR-02</td>
    <td>renderCreatePackagePage(), cpState, cpSendRequest(), cpCreateDraft()</td>
    <td>Candidate, draft, validation ve publish aynı revision zincirinde yaşar; chat/local DOM canonical değildir.</td>
  </tr>
  <tr>
    <td>Package type sınırı</td>
    <td>Modül 7 §2, §9, Canonical Integration CR-01; Modül 8 §12</td>
    <td>cpPackageType: Indicator, Condition, Embedded System; Add Package: Strategy, Trading Signal, Trade Log</td>
    <td>PackageKind yalnız strategy, indicator, condition, embedded_system. Trading Signal / Trade Log package değildir.</td>
  </tr>
  <tr>
    <td>Add Package alignment</td>
    <td>Modül 9 §6.1-6.2, §12</td>
    <td>showAddPackagePanel(), populateAddPackageSelect(), addSelectedPackageToMainboard()</td>
    <td>Productionda yalnız Strategy Package seçimi Strategy Draft üretir. Indicator/Condition top-level Mainboard item değildir.</td>
  </tr>
  <tr>
    <td>Pre-Check / ESP gate</td>
    <td>Modül 8 §5-6</td>
    <td>cpRunPreCheck(), cpBuildPrecheckReport(), cpShowPrecheckPopup()</td>
    <td>UI action burada açıklanır; resolver report/detail sayfası 7/22 Pre-Checkte ayrıntılanır.</td>
  </tr>
  <tr>
    <td>Package revision / publish</td>
    <td>Modül 2 root/revision; Modül 7 §9; Modül 8 §7-11</td>
    <td>C.D.P, Run Validation Tests, Approve Package, Request Revision</td>
    <td>Current revision mutation yasak; immutable revision, dependency snapshot ve audit zorunlu.</td>
  </tr>
  <tr>
    <td>Roles / Agent / Trash</td>
    <td>Modül 0 §5-6; Modül 1 §§5-10; Modül 3; Modül 8 §11</td>
    <td>Prototype local functions / disabled buttons</td>
    <td>Frontend görünürlüğü policy değildir. Agent aynı commandsı Tool Gatewayden kullanır; Trash Admin only.</td>
  </tr>
  <tr>
    <td>Async API / durable jobs</td>
    <td>Modül 0 §9; Modül 8 §4, §10; Modül 19</td>
    <td>V18 synchronous local state and CP Agent chat messages</td>
    <td>Send, pre-check, validation, baseline parsing worker/job üzerinden yürür; UI durable state subscribes.</td>
  </tr>
</table>

## 0.2 Rule Provenance Register

<table>
  <tr>
    <th>Etiket</th>
    <th>Bu sayfadaki anlamı</th>
  </tr>
  <tr>
    <td>Canonical Rule</td>
    <td>Master tarafından açıkça kilitli Production davranışı. Örnek: Create Package UI yalnız Indicator, Condition ve Embedded System Package üretim tiplerini açar; Trading Signal / Trade Log bu type enumuna girmez.</td>
  </tr>
  <tr>
    <td>Derived Rule</td>
    <td>Canonical kuralın zorunlu sonucu. Örnek: Add Package popoverının Trading Signal / Trade Log satırları Productionda kaldırılır; bu iki obje Add Outsource Signal factorysinden gelir.</td>
  </tr>
  <tr>
    <td>V18 Interface Observation</td>
    <td>HTMLde görünen demo davranışı. Örnek: Target Runtime tek seçenek PHP, prompt metni ise Python dönüşümü talep eder; V18 local cpState ile button enable eder.</td>
  </tr>
  <tr>
    <td>Implementation Decision - Non-Canonical Gap Resolution</td>
    <td>Masterın exact frontend form ayrıntısını kilitlemediği yerde bu belgede seçilen teknik yön. Örnek: Production V1 initial target runtime Python worker runtimeıdır; PHP demo seçeneği registryde aktif adapter olmadan gösterilmez.</td>
  </tr>
  <tr>
    <td>Future Dev Boundary</td>
    <td>Bu sayfada gerçek broker/exchange işlem gönderimi, browserda model anahtarı kullanımı veya agentı UI chatine bağlayan sürekli araştırma döngüsü tanımlanmaz.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Canonical Kavramlar

Add Package / Create Package iki farklı işi aynı isim yakınlığı içinde gösterir; Production V1de bunlar ayrık domain akışlarıdır. Add Package, mevcut bir Strategy Package revisionından yeni ve bağımsız bir Strategy Draft başlatma girişidir. Create Package ise kaynak kod veya teknik açıklamadan Indicator Package, Condition Package ya da Embedded System Package adayı üretmek için request, dependency, candidate, draft, validation ve publish kanıtlarını bağlayan sürümlü üretim hattıdır.

Create Package, Package Libraryye anında satır ekleyen serbest bir form ve CP Agent da browser içindeki chat bot değildir. CP Agent backend capabilitydir; kullanıcı ya da Agent request gönderir, backend candidate-generation jobı üretir, immutable artifacts yazılır ve ayrı Create Draft Package commandı ile Package Root + Draft Revision oluşur. Approval, yetkili server-side state transitiondır.

## 1.1 İlk geçen kavramlar

<table>
  <tr>
    <th>Kavram</th>
    <th>Canonical kısa tanım</th>
    <th>Bu sayfadaki sonuç</th>
  </tr>
  <tr>
    <td>Package</td>
    <td>Tekrar kullanılabilir, sürümlü tanım/revision. Canonical türleri strategy_package, indicator_package, condition_package ve embedded_system_packagetir.</td>
    <td>Trading Signal veya Trade Logu package selector veya Create Package type seçeneği olarak gösterme.</td>
  </tr>
  <tr>
    <td>Strategy Package</td>
    <td>Bir strateji şablonu/blueprinti taşıyan reusable package.</td>
    <td>Add Package yalnız bunu seçerek yeni Strategy Draft üretir; original package mutate edilmez.</td>
  </tr>
  <tr>
    <td>Package Root</td>
    <td>Package kimliğini, owner/visibility/lifecycleı ve current revision pointerını taşıyan kalıcı üst nesne.</td>
    <td>Ad, tip veya code değişince root kimliği korunabilir; revision değişir.</td>
  </tr>
  <tr>
    <td>Package Revision</td>
    <td>Payload, output contract, dependency snapshot, implementation ref ve validation kanıtı taşıyan immutable sürüm.</td>
    <td>Current revision SQL UPDATE ile değiştirilmez; yeni revision oluşur.</td>
  </tr>
  <tr>
    <td>CreatePackageRequest</td>
    <td>UI/Agent tarafından normalized edilen, hashlenmiş ve idempotent request kaydı.</td>
    <td>Prompt, source kind, language, runtime, identity/compatibility seçimleri request artifactinde saklanır.</td>
  </tr>
  <tr>
    <td>CP Candidate</td>
    <td>CP Agent jobının ürettiği generated code, output contract, dependency listesi, risk/uncertainty ve test planı.</td>
    <td>Candidate tek başına Package Libraryye publish edilmez.</td>
  </tr>
  <tr>
    <td>Embedded System Package (ESP)</td>
    <td>Dış code içindeki canonical TA primitivein trusted resolver/adaptor tanımı.</td>
    <td>CP Agent resolver kodunu kopyalamaz; exact approved ESP revisionını dependency manifestte referanslar.</td>
  </tr>
  <tr>
    <td>Baseline Comparison</td>
    <td>Dış/orijinal implementationa eşdeğerlik iddiasını test eden kanıt süreci.</td>
    <td>Eşdeğerlik claimi varsa baseline metadata + matching evidence gereklidir; Generate From Descriptionda mode-aware değerlendirilir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Canonical Rule: Create Package ekranı için açık type seti Indicator Package, Condition Package ve Embedded System Packagedir. Strategy Package bu sayfada üretilmez; Strategy Details / Strategy Package akışı ayrı domain yoludur. Trading Signal ve Trade Log hiçbir durumda Package Type değildir.</th>
  </tr>
</table>

## 1.2 Sistem döngüsündeki yer

<table>
  <tr>
    <th>Source code or technical description<br/>  -&gt; normalized CreatePackageRequest + source hash<br/>  -&gt; dependency gate / Pre-Check (when applicable)<br/>  -&gt; async CP Candidate Generation Job<br/>  -&gt; candidate manifest + artifacts + uncertainty / test specification<br/>  -&gt; Create Draft Package (PackageRoot + immutable Draft Revision)<br/>  -&gt; validation / baseline evidence / revision request loop<br/>  -&gt; authorized approval + publish projection<br/>  -&gt; Package Library use by Strategy Details, Agent or later workflows</th>
  </tr>
</table>

Bu sayfa Backtest Run, Result veya Strategy Execution üretmez. Create Package tarafından oluşturulan bir revisionın sonraki kullanım alanları başka sayfalarda yönetilir. Bu sayfanın görevi yalnız reusable package tanımının güvenilir şekilde oluşmasını sağlamaktır.

# 2. Erişim, Görünürlük, Ownership ve Server-Side Policy

<table>
  <tr>
    <th>Actor</th>
    <th>View / discover</th>
    <th>Create request / draft</th>
    <th>Edit / revise / validate</th>
    <th>Approve / publish</th>
    <th>Delete / Trash</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Create Package workspace ve package artifactleri yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Own + explicitly shared/published package/candidate bağlamını görür.</td>
    <td>Kendi ownerlığında request ve draft oluşturur.</td>
    <td>Yalnız own draft/revision; başkasında normal edit yerine derive.</td>
    <td>Approval policyye göre yetkisiz; server guard.</td>
    <td>Yalnız own normal resource soft delete; Trash yok.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Erişilebilir working package/candidate içeriğini görür/kullanır.</td>
    <td>Kendi ownerlığında oluşturur.</td>
    <td>Yalnız own draft/revision.</td>
    <td>Admin yetkisi olmayan publish reddedilir.</td>
    <td>Yalnız own soft delete; Trash yok.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm uygun request/candidate/root/revisionı görür/yönetir.</td>
    <td>Her bağlamda oluşturabilir.</td>
    <td>Tüm uygun resource üzerinde override.</td>
    <td>Approval/publish ve ESP trusted resolver registry değişimi Admin only.</td>
    <td>Soft delete; view/restore/permanent delete Admin only.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Tool Gateway policy kapsamındaki package ve data contextini kullanır; human login değildir.</td>
    <td>Kendi agent-owned request/candidate/draft outputunu oluşturur.</td>
    <td>Yalnız own outputunu revize eder; başkasından derive yapar.</td>
    <td>Kendi kendine Admin approval bypassı yapamaz; proposal / approval_request oluşturur.</td>
    <td>Kendi outputu için soft delete başlatabilir; Trash yok.</td>
  </tr>
</table>

Rationale Family ve Package Rationale Assignment global shared-editing exceptiondır; bu exception yalnız semantic family card ve assignment mapping içindir. CP request source’u, generated code, output contract, dependency manifest, owner veya Package Revision payloadı üzerinde normal owner policyyi ortadan kaldırmaz.

<table>
  <tr>
    <th>Canonical Rule: UIde disabled veya hidden görünen Approve, Upload, Send ya da Delete düğmesi server-side policy yerine geçmez. Her mutation principal, role, ownership, lifecycle, dependency status, expected_head_revision_id ve idempotency_key ile yeniden doğrulanır.</th>
  </tr>
</table>

# 3. Arayüz Yerleşimi, Navigasyon ve Görünür Bileşenler

V18de Add Package, Mainboard menüsünden açılan küçük bir popoverdır. Create Package ise Edit menüsünden açılan iki kolonlu çalışma sayfasıdır: üstte dört kontrol, altında Package Identity / Compatibility grid, solda request/chat board ve draft-file listesi, sağda Package Status, Baseline, Resolver açıklaması, Validation Tests, actions ve Package Library Target projectionı bulunur.

## 3.1 V18 Add Package popover envanteri

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 Interface Behavior</th>
    <th>Varsayılan / görünme</th>
    <th>Production V1 karşılığı</th>
  </tr>
  <tr>
    <td>Mainboard &gt; Add Package</td>
    <td>Menü itemi showAddPackagePanel(event) çağırır.</td>
    <td>Mainboard dropdown içindedir.</td>
    <td>Navigation surface korunabilir; semantic action Strategy Package kaynaklı Strategy Drafttır.</td>
  </tr>
  <tr>
    <td>Popover title</td>
    <td>&quot;Add Package&quot; başlığı.</td>
    <td>Her açılışta.</td>
    <td>Implementation Decision: header &quot;Add Strategy From Package&quot;; menu label geçiş sürecinde Add Package kalabilir.</td>
  </tr>
  <tr>
    <td>Choose Package Type</td>
    <td>Placeholder + Strategy, Trading Signal, Trade Log seçenekleri.</td>
    <td>Placeholder selected; package select disabled.</td>
    <td>V18 legacy type picker. Productionda type fixed = Strategy Package; Trading Signal/Trade Log seçenekleri kaldırılır.</td>
  </tr>
  <tr>
    <td>Choose Package</td>
    <td>Seçilen typea göre packageGroups içinden local isim listesi.</td>
    <td>Type seçilince enable; placeholder selected.</td>
    <td>Role-aware Package Catalog queryden accessible strategy package revision seçenekleri gelir.</td>
  </tr>
  <tr>
    <td>Close</td>
    <td>Popoverı DOMdan kaldırır.</td>
    <td>Always enabled.</td>
    <td>Presentation-only close; server mutation yok.</td>
  </tr>
  <tr>
    <td>Add Selected Package</td>
    <td>V18de Strategy -&gt; addStrategyBox; legacy signal/log -&gt; dış item satırı ekler.</td>
    <td>Type and package selection yapılmadan local function return eder.</td>
    <td>Yalnız CreateDerivedStrategyDraftFromPackage commandını çalıştırır; source Package kopyalanmaz/mutate edilmez.</td>
  </tr>
</table>

## 3.2 V18 Create Package ekranı envanteri

<table>
  <tr>
    <th>Bölge</th>
    <th>V18 Interface Behavior</th>
    <th>Varsayılan / state</th>
    <th>Production karşılığı</th>
  </tr>
  <tr>
    <td>Top controls row</td>
    <td>Package Type, Creation Mode, Source Language, Target Runtime: dört select.</td>
    <td>Indicator / Translate Existing Code / PineScript / PHP.</td>
    <td>Normalized request builder; requiredness source mode ve typea göre server-side.</td>
  </tr>
  <tr>
    <td>Identity / Compatibility</td>
    <td>Rationale Family, Output Type, Compatible Family, Explicit Indicator Link.</td>
    <td>Reversal / Mean Reversion, Directional Signal, Same Rationale Family, Optional / Not Required.</td>
    <td>Typed identity + output + compatibility contract. V18 string names değil IDs/revision refs persist edilir.</td>
  </tr>
  <tr>
    <td>Package Request / AI Workspace</td>
    <td>CP Agent message board, default technical prompt textarea, Pre-Check, Send, C.D.P, Clear.</td>
    <td>Chat board empty; C.D.P disabled; prompt prefilled.</td>
    <td>Request + candidate progress view; CP Agent backend capability; Send async job submit.</td>
  </tr>
  <tr>
    <td>Draft Package Files</td>
    <td>No draft package created placeholder; C.D.P sonrası seven local list rows.</td>
    <td>Inactive until draft.</td>
    <td>Immutable artifacts and artifact metadata projection; not browser-rendered fake files.</td>
  </tr>
  <tr>
    <td>Package Status</td>
    <td>Name, Type, Version, Status, Target Library, TA Pre-Check.</td>
    <td>Not Created / Not Checked, values reflect select defaults.</td>
    <td>Read-only projection from request/candidate/revision/job state.</td>
  </tr>
  <tr>
    <td>TradingView Baseline</td>
    <td>No baseline CSV uploaded; Upload CSV disabled until draft.</td>
    <td>No file initially.</td>
    <td>Source asset upload and baseline parser/metadata validator; type/mode-aware eligibility.</td>
  </tr>
  <tr>
    <td>Pine TA / ESP Resolver</td>
    <td>Explanatory tiny note only.</td>
    <td>Always visible.</td>
    <td>Resolver/pre-check detail is delegated to page 7; this screen shows summary and action link.</td>
  </tr>
  <tr>
    <td>Validation Tests</td>
    <td>Syntax, Runtime, Output Structure, Real Market Data, Repaint/Future Leak, Baseline Comparison.</td>
    <td>All NOT STARTED.</td>
    <td>Independent validation evidence/job projections; states include queued/running/passed/failed/stale/not applicable.</td>
  </tr>
  <tr>
    <td>Bottom actions and target</td>
    <td>Run Validation Tests, Approve Package, Request Revision; target library row.</td>
    <td>Disabled until prior local state.</td>
    <td>Domain commands with role/dependency guards. Target is read-only type projection, not a writable destination picker.</td>
  </tr>
  <tr>
    <td>Pre-Check modal</td>
    <td>Overlay: title, ×, report HTML, Close.</td>
    <td>Only appears after Pre-Check or blocked Send.</td>
    <td>Production report component uses durable PreCheckReport artifact; detailed behavior page 7.</td>
  </tr>
</table>

## 3.3 Responsive, focus ve close behavior

- V18 observation: Create Package uses a two-column grid. Narrow layouts stack content vertically; the message area and side-panel components remain inside the page box. The Pre-Check overlay blocks background interaction and closes by ×, Close, or overlay click.

- Production rule: Keyboard focus enters the newly opened popover/page at the first required field. Native selectors and file input must retain usable labels. Modal focus is trapped while the Pre-Check report is open; Escape closes only the report and never cancels an in-flight job.

- Production rule: Closing Add Package or Create Package does not cancel a submitted candidate-generation, Pre-Check, baseline parsing or validation job. The UI may unmount; job state remains durable and is rehydrated when the page returns.

# 4. Field Contract Matrix

V18 labelsinde yıldız işareti yoktur. Production V1de aşağıdaki zorunlu alanlar görsel olarak * ile işaretlenir. Yıldız yalnız UX işareti değildir: aynı requiredness normal UI submit, Agent Tool schema, server validation ve approval/publish gate içinde uygulanır.

## 4.1 Add Package popover fields

<table>
  <tr>
    <th>Alan</th>
    <th>UI / V18 default</th>
    <th>Production requiredness ve options</th>
    <th>Normalized payload / validation</th>
  </tr>
  <tr>
    <td>Choose Package Type</td>
    <td>Select. Placeholder &quot;Choose Package Type&quot;; Strategy, Trading Signal, Trade Log.</td>
    <td>V18 yalnız observationdır. Productionda UI field kaldırılır veya read-only &quot;Strategy Package&quot; olarak görünür; type fixed.</td>
    <td>source_package_type = strategy_package. signal/trade_log seçimi CLIENT_LEGACY_TYPE_REJECTED; user Add Outsource Signal akışına yönlendirilir.</td>
  </tr>
  <tr>
    <td>Choose Strategy Package *</td>
    <td>Select initially disabled. V18 options browser packageGroups arrayinden gelir.</td>
    <td>Required. Accessible root.lifecycle_state=active, revision.approval_state=approved, visibility_scope=published Strategy Package revisions listelenir; optionally root + revision label. Empty result shows no eligible package state.</td>
    <td>source_strategy_package_root_id + source_strategy_package_revision_id required; can_use(policy), lifecycle ACTIVE, output/schema compatibility and exact revision availability checked.</td>
  </tr>
  <tr>
    <td>Revision selector (Production addition)</td>
    <td>V18de yok.</td>
    <td>Conditionally visible when root has multiple eligible revisions; default current approved revision but explicit selection required before confirm if caller changed default.</td>
    <td>source_strategy_package_revision_id always explicit; no implicit latest lookup at draft creation.</td>
  </tr>
</table>

## 4.2 Create Package request controls

<table>
  <tr>
    <th>Alan</th>
    <th>V18 default ve tüm seçenekler</th>
    <th>Production * / conditional requiredness</th>
    <th>Production payload / dependency</th>
  </tr>
  <tr>
    <td>Package Type *</td>
    <td>Indicator Package (selected); Condition Package; Embedded System Package.</td>
    <td>Always required. Strategy Package, Trading Signal ve Trade Log seçenekleri görünmez.</td>
    <td>package_type = indicator | condition | embedded_system. Type changes invalidate candidate, pre-check, validation and approval evidence.</td>
  </tr>
  <tr>
    <td>Creation Mode *</td>
    <td>Translate Existing Code (first); Generate From Description; Repair Existing Code; Review Existing Code.</td>
    <td>Always required. Translate/Repair/Review require source_kind=CODE. Generate requires source_kind=DESCRIPTION. Review does not enable publish until an explicit candidate output contract exists.</td>
    <td>creation_mode enum. Changing mode recalculates required fields and sets stale=true for all downstream artifacts.</td>
  </tr>
  <tr>
    <td>Source Language *</td>
    <td>PineScript; Python; C++; Natural Language; Other. PineScript is first.</td>
    <td>Required only when source_kind=CODE. Natural Language is removed from Production language enum; it maps to Generate From Description with source_language=null. Other requires Other Language Name * (production addition).</td>
    <td>source_language enum + optional other_language_label. Parser/detector mismatch returns SOURCE_LANGUAGE_MISMATCH or REQUIRES_CLARIFICATION.</td>
  </tr>
  <tr>
    <td>Target Runtime *</td>
    <td>PHP only, selected.</td>
    <td>Always required for a candidate intended to generate runnable code. Implementation Decision: Production V1 exposes registered Python Runtime v1 as initial active adapter; PHP is not selectable until an approved runtime adapter exists.</td>
    <td>target_runtime_id must be active, type-compatible and known to the artifact executor. Changing it stales pre-check/candidate/validation.</td>
  </tr>
  <tr>
    <td>Other Language Name *</td>
    <td>Not in V18.</td>
    <td>Visible and required only when Source Language = Other.</td>
    <td>other_language_label normalized; must match supported parser route or explicitly return REQUIRES_CLARIFICATION.</td>
  </tr>
</table>

## 4.3 Package identity, output and compatibility fields

<table>
  <tr>
    <th>Alan</th>
    <th>V18 default / options</th>
    <th>Production requiredness</th>
    <th>Typed payload / validation</th>
  </tr>
  <tr>
    <td>Rationale Family *</td>
    <td>Dynamic family options; V18 selected Reversal / Mean Reversion.</td>
    <td>Indicator/Condition: always required. Embedded System: system semantics classification is assigned by trusted registry workflow; personal family choice hidden/read-only.</td>
    <td>rationale_family_id. Must resolve to existing shared Family. Assignment mutation follows special shared-editing policy; package payload remains normal owner-controlled.</td>
  </tr>
  <tr>
    <td>Output Type *</td>
    <td>Directional Signal (selected); Boolean Condition; Numeric Series; Color / Direction State; Trade Record.</td>
    <td>Always required, but options filtered by Package Type. Indicator: directional_signal, numeric_series, state_series, boolean_event. Condition: boolean_condition only. ESP: output shape derives from canonical function signature. Trade Record is removed: Trade Log is external object, not package output.</td>
    <td>output_contract typed schema. Must be compatible with selected type, input contract, target runtime and declared validation suite.</td>
  </tr>
  <tr>
    <td>Compatible Family</td>
    <td>Same Rationale Family (selected) plus family options.</td>
    <td>Optional. Default resolves to selected rationale family; user can add allowed family compatibility references.</td>
    <td>compatible_rationale_family_ids[]. Must not auto-create any Family. Changing it does not rewrite current Rationale assignment silently.</td>
  </tr>
  <tr>
    <td>Explicit Indicator Link</td>
    <td>Optional / Not Required (selected); Reversal Sensor; Smoothed Heiken Ashi; Predictive Ranges; RSI; Volume Breakout.</td>
    <td>Only visible for a Condition Package whose input contract needs specific indicator output. Then * becomes active. Hidden for Indicator/ESP.</td>
    <td>linked_indicator_package_root_id + linked_indicator_package_revision_id. Name-only selection prohibited; output/input contract must match.</td>
  </tr>
  <tr>
    <td>Package Name / identity</td>
    <td>V18 has no editable field; name is generated after C.D.P as &quot;New [Type] Package&quot;.</td>
    <td>Production candidate generates suggested display name; editable via Draft metadata form after candidate. A non-empty normalized name is required before publish.</td>
    <td>package_name/display_name; unique-per-owner namespace policy; semantic rename is revision/audit relevant.</td>
  </tr>
</table>

## 4.4 Request composition, baseline and read-only projections

<table>
  <tr>
    <th>Alan / projection</th>
    <th>V18 default</th>
    <th>Production requiredness / state effect</th>
    <th>Canonical persistence</th>
  </tr>
  <tr>
    <td>Request textarea *</td>
    <td>Prefilled PineScript-to-Python request with OHLCV and closed-bar statement.</td>
    <td>Always required. Content must satisfy creation-mode source requirement: code, description, repair instruction or review objective. Empty Send is blocked with field error.</td>
    <td>request_body + source_content_hash. Original text stored immutable in request artifact; source is never overwritten by generated code.</td>
  </tr>
  <tr>
    <td>Baseline CSV asset</td>
    <td>&quot;No baseline CSV uploaded&quot;; Upload CSV disabled before draft.</td>
    <td>Required before approval only where candidate claims translation/repair/equivalence. Not automatically required for Generate From Description when equivalence_claim=false. Optional at draft stage.</td>
    <td>baseline_asset_id + BaselineMetadata + parse/validation report. File metadata must include provider, symbol, timeframe, range, timezone, settings and source revision context.</td>
  </tr>
  <tr>
    <td>Package Name</td>
    <td>— initially; V18 set to generated name after C.D.P.</td>
    <td>Read-only projection.</td>
    <td>Package root/revision metadata returned by backend.</td>
  </tr>
  <tr>
    <td>Type</td>
    <td>Indicator Package initially.</td>
    <td>Read-only projection derived from package_type.</td>
    <td>package_type enum.</td>
  </tr>
  <tr>
    <td>Version</td>
    <td>— then local v1/v2 counter.</td>
    <td>Read-only immutable revision identity projection. Human semantic version may be displayed, but canonical key is package_revision_id + parent chain.</td>
    <td>package_revision_id, parent_revision_id, revision_sequence / semantic tag.</td>
  </tr>
  <tr>
    <td>Status</td>
    <td>Not Created; Draft; Testing; Eligible for Approval; Experimental; Approved; Revision Required.</td>
    <td>Read-only workflow projection. V18 labels map to request/candidate/revision/evidence states; never inferred from a button click alone.</td>
    <td>CreatePackageRequest state, candidate job state, PackageRoot lifecycle, revision validation/approval facets, visibility scope and validation evidence.</td>
  </tr>
  <tr>
    <td>Target Library</td>
    <td>Indicator/Condition/Embedded System Packages.</td>
    <td>Read-only destination projection derived from package_type.</td>
    <td>Not user writable. Before publish: Awaiting approval. After success: Published/Approved package available in correct catalog projection.</td>
  </tr>
  <tr>
    <td>TA Pre-Check</td>
    <td>Not Checked; CP helper may set Passed/Blocked.</td>
    <td>Read-only report summary. Applicable to code/source route that requires resolver resolution; stale on source/dependency/runtime/output change.</td>
    <td>precheck_report_id + status NOT_APPLICABLE|PENDING|PASSED|BLOCKED|STALE.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Implementation Decision: V18de Target Runtime PHP iken textarea Python dönüşümü ister. Production V1de code-generation runtime gerçek backtest/validation workerıyla aynı registered Python Runtime v1 adapterına bağlanır. PHP demo seçeneği runtime registryde approved adapter ve test evidence bulunmadıkça görünmez. Bu karar, UI metni ile engine çalışabilirliği arasındaki çelişkiyi kapatır.</th>
  </tr>
</table>

# 5. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen</th>
    <th>Default</th>
    <th>Aktifleşme / disabled koşulu</th>
    <th>Payload / engine etkisi</th>
  </tr>
  <tr>
    <td>Add Package popover</td>
    <td>Closed; no selection.</td>
    <td>Menu click opens. Strategy package list loading until query returns.</td>
    <td>Opening/closing creates no domain mutation.</td>
  </tr>
  <tr>
    <td>Add Strategy From Package confirm</td>
    <td>Disabled until eligible exact revision selected.</td>
    <td>Enabled after selection and can_use succeeds. Loading while derived draft command persists.</td>
    <td>Creates new Strategy Draft provenance; does not attach/clone Trading Signal/Trade Log or mutate source package.</td>
  </tr>
  <tr>
    <td>Create Package form</td>
    <td>Fresh request editor with V18 defaults; no request persisted until Send.</td>
    <td>Downstream fields change visibility by type/mode.</td>
    <td>Editor-only transient state; before Send no canonical package root/revision exists.</td>
  </tr>
  <tr>
    <td>Pre-Check</td>
    <td>Not Checked.</td>
    <td>Code route: enabled when source body has content. Description route: report Not Applicable. Send blocked only if current report BLOCKED.</td>
    <td>No code conversion; creates report artifact. Source hash/runtime/output/dependency change makes report STALE.</td>
  </tr>
  <tr>
    <td>Send</td>
    <td>Enabled when request fields valid and no blocking current pre-check.</td>
    <td>On click, disabled per idempotency; job queued/running indicator.</td>
    <td>Creates immutable CreatePackageRequest + async CP candidate job. Browser close does not cancel.</td>
  </tr>
  <tr>
    <td>C.D.P</td>
    <td>Disabled until candidate success and required candidate outputs present.</td>
    <td>Enabled only for non-stale successful candidate.</td>
    <td>Creates PackageRoot if needed + immutable Draft Revision. Repeat same candidate returns existing draft (idempotent).</td>
  </tr>
  <tr>
    <td>Baseline Upload</td>
    <td>Disabled until a draft/candidate baseline target exists.</td>
    <td>Enabled for eligible candidate revision; parser running after upload.</td>
    <td>Uploads immutable asset; failed validation does not erase source asset, but evidence remains invalid.</td>
  </tr>
  <tr>
    <td>Validation tests</td>
    <td>All NOT STARTED initially.</td>
    <td>Run disabled until draft and non-stale dependency snapshot exists.</td>
    <td>Validation jobs write immutable evidence. Output changes thereafter make evidence stale.</td>
  </tr>
  <tr>
    <td>Approve Package</td>
    <td>Disabled initially; V18 requires baseline.</td>
    <td>Production enabled only after evidence/role/dependency/mode gate succeeds. ESP trusted resolver publish is Admin only.</td>
    <td>Publishes/repoints current revision atomically; UI receives canonical revision/target projection.</td>
  </tr>
  <tr>
    <td>Request Revision</td>
    <td>Disabled until draft exists.</td>
    <td>Enabled after draft/candidate review, including failed validation.</td>
    <td>Creates new candidate attempt with parent revision ref; never edits existing revision.</td>
  </tr>
  <tr>
    <td>Clear</td>
    <td>Always enabled V18.</td>
    <td>Always closes/reset editor; confirmation only if unsent local input exists.</td>
    <td>Clears only transient editor. Does not delete request, candidate, draft, artifact, baseline or published package.</td>
  </tr>
  <tr>
    <td>Pre-Check report modal</td>
    <td>Hidden until report/blocked send.</td>
    <td>Modal open while report displayed; Close/×/overlay dismiss.</td>
    <td>Presentation state only. Does not cancel or alter report/job.</td>
  </tr>
</table>

# 6. Information Content Catalog, Placeholder ve Final UI Metinleri

V18 Create Package yüzeyinde ⓘ icon button yoktur; alan açıklamaları cp-tiny-note metinleriyle sınırlıdır. Production V1, karmasık semantic alanlarda standardize edilmiş ⓘ buttons ekler. Bu ekleme bir Implementation Decisiondır. Aşağıdaki metinler doğrudan UIa yerleştirilecek nihai içeriktir.

<table>
  <tr>
    <th>Info key / field</th>
    <th>Panel title</th>
    <th>Final UI text</th>
  </tr>
  <tr>
    <td>addPackageStrategyInfo</td>
    <td>Add Strategy From Package</td>
    <td>Select a reusable Strategy Package revision as the starting blueprint for a new Strategy Draft. This action creates a new strategy owned by the caller and records the selected package revision as provenance. It never edits the source package and it never creates a Trading Signal or Trade Log item.</td>
  </tr>
  <tr>
    <td>cpPackageTypeInfo</td>
    <td>Package Type</td>
    <td>Choose the kind of reusable package to create. Indicator Packages calculate or emit indicator outputs. Condition Packages evaluate reusable boolean conditions. Embedded System Packages define trusted runtime resolvers for canonical functions. Trading Signal and Trade Log are external Mainboard working objects and are not package types.</td>
  </tr>
  <tr>
    <td>cpCreationModeInfo</td>
    <td>Creation Mode</td>
    <td>Translate Existing Code converts a known implementation. Generate From Description designs a new candidate from a technical specification. Repair Existing Code creates a new candidate intended to correct an identified defect. Review Existing Code analyses code and may propose a candidate, but review alone does not publish a package.</td>
  </tr>
  <tr>
    <td>cpSourceLanguageInfo</td>
    <td>Source Language</td>
    <td>Choose the language of supplied code. This field is required only for code-based modes. Natural language is a creation mode, not a source language: a descriptive request is stored as source_kind = DESCRIPTION with no code-language parser selected.</td>
  </tr>
  <tr>
    <td>cpTargetRuntimeInfo</td>
    <td>Target Runtime</td>
    <td>Target Runtime is the approved runtime adapter that will execute and validate generated code. The displayed runtime must be registered, active and compatible with the selected package type and output contract. Changing it invalidates previous Pre-Check, candidate and validation evidence.</td>
  </tr>
  <tr>
    <td>cpRationaleFamilyInfo</td>
    <td>Rationale Family</td>
    <td>Rationale Family places a reusable Indicator or Condition Package in the shared research taxonomy. It helps discovery and compatibility analysis but does not override code, output-contract or dependency validation. Embedded System Packages use a system resolver classification instead of a personal research family.</td>
  </tr>
  <tr>
    <td>cpOutputTypeInfo</td>
    <td>Output Type</td>
    <td>Output Type is the machine-readable contract produced by this package. It controls which downstream workflows may use the package and which validation tests are required. A Trade Record is not a package output in Production V1; historical trades are represented by the Trade Log external working object.</td>
  </tr>
  <tr>
    <td>cpCompatibleFamilyInfo</td>
    <td>Compatible Family</td>
    <td>Compatible Family lists other research families for which the package may be considered as a candidate. It is a discovery hint and compatibility declaration, not a permission bypass. It never creates a new family or silently changes a package rationale assignment.</td>
  </tr>
  <tr>
    <td>cpIndicatorLinkInfo</td>
    <td>Explicit Indicator Link</td>
    <td>Use this field only when a Condition Package requires the output of a specific Indicator Package. Select an exact compatible indicator revision. Choosing an indicator by display name alone is not sufficient; the saved dependency is the root and revision identifier.</td>
  </tr>
  <tr>
    <td>cpRequestInfo</td>
    <td>Package Request</td>
    <td>Describe the source code, the intended behavior, input data, output contract, timing/closed-bar rule, and known constraints. Do not place API keys, credentials or live trading instructions here. Sending a request creates an immutable request artifact and a background candidate-generation job.</td>
  </tr>
  <tr>
    <td>cpPrecheckInfo</td>
    <td>Pre-Check</td>
    <td>Pre-Check is a dependency gate and static inspection. For PineScript it looks for technical-analysis primitive calls and verifies that each has a compatible trusted Embedded System Package resolver. Passing Pre-Check does not translate code, approve a package or replace validation.</td>
  </tr>
  <tr>
    <td>cpBaselineInfo</td>
    <td>Baseline Comparison</td>
    <td>Use a baseline when the package claims to reproduce, repair or be equivalent to an external implementation. The baseline file must include enough metadata to reproduce the comparison: provider, symbol, timeframe, range, timezone, settings and source context. A file upload alone is not proof of equivalence.</td>
  </tr>
  <tr>
    <td>cpValidationInfo</td>
    <td>Validation Tests</td>
    <td>Validation produces evidence, not a cosmetic pass label. Tests cover syntax, runtime behavior, output structure, approved market-data execution, repaint or future-leak risk and, when applicable, baseline equivalence. A later source, dependency, runtime or output-contract change makes prior evidence stale.</td>
  </tr>
  <tr>
    <td>cpApprovalInfo</td>
    <td>Approve Package</td>
    <td>Approve publishes the immutable revision only after the server confirms current validation evidence, dependency health, required baseline policy and actor authorization. A disabled or hidden button is not the authority check. Embedded System resolver publication is Admin-only.</td>
  </tr>
</table>

## 6.1 Placeholder, helper text, warning, toast, empty-state, confirmation ve error copy

<table>
  <tr>
    <th>Context</th>
    <th>Final UI text</th>
  </tr>
  <tr>
    <td>Add Package empty selector</td>
    <td>No eligible Strategy Packages are available. Create or publish a Strategy Package first, or request access to an existing package.</td>
  </tr>
  <tr>
    <td>Add Package permission denial</td>
    <td>You can view this package but cannot use it to create a Strategy Draft. Ask the owner or an Admin to grant use access.</td>
  </tr>
  <tr>
    <td>Create Package request placeholder</td>
    <td>Paste code or describe the package to create. State the inputs, outputs, intended timing, closed-bar behavior, dependencies and known limits.</td>
  </tr>
  <tr>
    <td>Other language helper</td>
    <td>Enter the exact language and version, for example: &quot;EasyLanguage 10&quot;. Conversion will not start until a supported parser route is confirmed.</td>
  </tr>
  <tr>
    <td>Pre-Check not applicable</td>
    <td>Pre-Check is not required for this description-only request. Candidate generation can continue after the request is validated.</td>
  </tr>
  <tr>
    <td>Pre-Check stale warning</td>
    <td>Pre-Check is stale because the source, runtime, output contract or dependency context changed. Run Pre-Check again before sending this code request.</td>
  </tr>
  <tr>
    <td>Missing ESP blocker</td>
    <td>Conversion is blocked because one or more technical-analysis dependencies have no compatible trusted Embedded System Package resolver. Create a resolver proposal or ask an Admin to publish the required resolver, then run Pre-Check again.</td>
  </tr>
  <tr>
    <td>Send queued toast</td>
    <td>Package candidate request queued. You may leave this page; progress and artifacts will remain available.</td>
  </tr>
  <tr>
    <td>Candidate failure error</td>
    <td>Candidate generation failed before a usable candidate was produced. The request and failure evidence were saved. Review the error details and create a new revision attempt; retry does not overwrite the previous attempt.</td>
  </tr>
  <tr>
    <td>C.D.P success toast</td>
    <td>Draft Package created from candidate {candidate_id}. The draft is not approved or published.</td>
  </tr>
  <tr>
    <td>Baseline rejected error</td>
    <td>Baseline file was stored but cannot be used for equivalence validation. Correct the missing or inconsistent metadata and upload a new baseline asset.</td>
  </tr>
  <tr>
    <td>Validation stale warning</td>
    <td>Validation evidence is stale because the package candidate or dependency snapshot changed. Run validation again before approval.</td>
  </tr>
  <tr>
    <td>Approval success toast</td>
    <td>Package revision {revision_label} was approved and published to {target_library}.</td>
  </tr>
  <tr>
    <td>Approval denied error</td>
    <td>Package approval was not completed. Review validation evidence, dependency status, baseline policy and your authorization, then retry with the current revision.</td>
  </tr>
  <tr>
    <td>Request revision confirmation</td>
    <td>Create a new candidate attempt from this draft? The current draft and its validation evidence will be preserved and will not be edited.</td>
  </tr>
  <tr>
    <td>Clear confirmation</td>
    <td>Clear unsent editor changes? This does not delete any submitted request, draft package, artifact or published revision.</td>
  </tr>
  <tr>
    <td>Delete confirmation</td>
    <td>Move this Package to Trash? New use and new revisions will be blocked. Historical Strategy and Backtest manifests will keep their pinned revision references.</td>
  </tr>
</table>

# 7. Buttons, Commands ve State Contracts

<table>
  <tr>
    <th>UI action</th>
    <th>Production command / query</th>
    <th>Precondition and disabled</th>
    <th>Loading / success / error / audit</th>
  </tr>
  <tr>
    <td>Open Add Package</td>
    <td>GET /package-catalog?type=strategy&amp;use_allowed=true</td>
    <td>Caller may open only if Mainboard route policy permits.</td>
    <td>Loads role-aware list; no audit mutation. Query failure: retry list.</td>
  </tr>
  <tr>
    <td>Add Selected Package</td>
    <td>CreateDerivedStrategyDraftFromPackage</td>
    <td>Exact accessible Strategy Package revision selected; idempotency key.</td>
    <td>Loading locks duplicate click. Success returns StrategyDraft + provenance and navigates/opens strategy draft. Errors: PACKAGE_NOT_USABLE, REVISION_DEPRECATED, ACCESS_DENIED, STALE_SELECTION. Audit: strategy_draft_derived_from_package.</td>
  </tr>
  <tr>
    <td>Pre-Check</td>
    <td>StartPackagePreCheck</td>
    <td>Valid code request; current source hash and runtime context. For description: returns NOT_APPLICABLE, no parser job.</td>
    <td>Returns job/report id. UI listens to durable report. Errors: SOURCE_LANGUAGE_MISMATCH, PARSE_FAILED, MISSING_RESOLVER, PRECHECK_STALE. Audit: package_precheck_completed.</td>
  </tr>
  <tr>
    <td>Send</td>
    <td>SubmitCreatePackageRequest</td>
    <td>All mode/type dependent fields valid; current Pre-Check not BLOCKED for code route.</td>
    <td>Immediately returns request_id/job_id. Candidate job async. Success state QUEUED/RUNNING/SUCCEEDED. Failure artifacts saved. Audit: package_request_created, candidate_generation_started/failed/completed.</td>
  </tr>
  <tr>
    <td>C.D.P</td>
    <td>CreateDraftPackageFromCandidate</td>
    <td>Candidate succeeded, is current/not stale, output contract valid; idempotency key.</td>
    <td>Success returns package_root_id + draft_revision_id. Repeat returns same draft. Errors: CANDIDATE_STALE, CANDIDATE_INCOMPLETE, DEPENDENCY_UNRESOLVED. Audit: package_draft_created.</td>
  </tr>
  <tr>
    <td>Upload CSV</td>
    <td>UploadBaselineAsset + StartBaselineParse</td>
    <td>Draft/candidate context exists; accepted file type and size; caller may attach.</td>
    <td>Asset upload and parse are async. Success returns baseline_asset/report ids. Errors: FILE_TYPE_NOT_ALLOWED, BASELINE_METADATA_INVALID, PARSE_FAILED. Audit: baseline_uploaded/validated.</td>
  </tr>
  <tr>
    <td>Run Validation Tests</td>
    <td>StartPackageValidationRun</td>
    <td>Draft revision current; dependency snapshot resolved; evidence not running.</td>
    <td>Returns validation_run_id; rows show queued/running/passed/failed/stale. Errors save test artifacts. Audit: validation_run_started/completed.</td>
  </tr>
  <tr>
    <td>Approve Package</td>
    <td>ApproveAndPublishPackageRevision</td>
    <td>Current validation eligible; mode-aware baseline gate satisfied; dependencies active; Admin policy for publish / ESP registry.</td>
    <td>Atomic server transition. Success returns published revision and target projection. Errors: VALIDATION_REQUIRED, BASELINE_REQUIRED, DEPENDENCY_UNRESOLVED, APPROVAL_FORBIDDEN, STALE_REVISION. Audit: approval_granted/rejected, revision_published.</td>
  </tr>
  <tr>
    <td>Request Revision</td>
    <td>CreatePackageRevisionAttempt</td>
    <td>Draft/candidate exists; caller can revise own resource or derive.</td>
    <td>Creates immutable next attempt linked to parent revision and prior validation summary. Errors: ACCESS_DENIED / STALE_REVISION. Audit: revision_requested.</td>
  </tr>
  <tr>
    <td>Clear</td>
    <td>ClearCreatePackageEditor</td>
    <td>None; confirms only unsent local changes.</td>
    <td>No server delete, no audit mutation. Does not cancel job or remove stored objects.</td>
  </tr>
  <tr>
    <td>Close Pre-Check modal</td>
    <td>DismissPreCheckReportView</td>
    <td>Modal visible.</td>
    <td>No domain mutation; no job cancellation.</td>
  </tr>
</table>

## 7.1 Example normalized request and command shape

<table>
  <tr>
    <th>CreatePackageRequest<br/>{<br/>  request_id: &quot;cpr_...&quot;,<br/>  package_type: &quot;indicator&quot;,<br/>  creation_mode: &quot;translate_existing_code&quot;,<br/>  source_kind: &quot;code&quot;,<br/>  source_language: &quot;pinescript&quot;,<br/>  target_runtime_id: &quot;python-runtime-v1&quot;,<br/>  rationale_family_id: &quot;rf_...&quot;,<br/>  output_contract: { kind: &quot;directional_signal&quot;, fields: [&quot;indicator_value&quot;, &quot;long_signal&quot;, &quot;short_signal&quot;] },<br/>  compatible_rationale_family_ids: [&quot;rf_...&quot;],<br/>  linked_indicator_dependency: null,<br/>  source_content_hash: &quot;sha256:...&quot;,<br/>  body_artifact_id: &quot;asset_...&quot;,<br/>  precheck_report_id: &quot;pcr_...&quot;,<br/>  idempotency_key: &quot;...&quot;<br/>}<br/><br/>CreateDraftPackageFromCandidate<br/>{ candidate_id, expected_candidate_hash, idempotency_key }<br/><br/>ApproveAndPublishPackageRevision<br/>{ package_root_id, draft_revision_id, expected_head_revision_id, validation_run_id, idempotency_key }</th>
  </tr>
</table>

# 8. Kullanıcı Akışları

## 8.1 Mevcut Strategy Package ile Mainboard başlangıcı

1. Kullanıcı Mainboard > Add Package menüsünü açar. Production UI Strategy Package kaynak akışını gösterir; Trading Signal ve Trade Log type seçenekleri gösterilmez.

2. Backend role-aware catalog query ile kullanıcının use izni olan eligible Strategy Package revisionlarını döndürür.

3. Kullanıcı bir Package Root ve exact revision seçer. UI, package name, revision label ve basic compatibility özetini gösterir.

4. Kullanıcı Add Strategy From Package eylemini onaylar. Backend yeni Strategy Draft oluşturur; source package revision ve transitive dependency snapshotı provenancea yazar.

5. Source package değişmez. Yeni Strategy Draft ownerı caller olur. Kullanıcı daha sonra Strategy Details sayfasında bu draftı değiştirirse yalnız yeni Strategy Revisionlar oluşur.

## 8.2 PineScriptten Indicator Package adayı üretme

1. Kullanıcı Package Type = Indicator Package, Creation Mode = Translate Existing Code, Source Language = PineScript, Target Runtime = Python Runtime v1 seçer.

2. Kullanıcı Rationale Family ve Directional Signal output contractını doğrular; prompt alanına source code ve closed-bar gereksinimini girer.

3. Pre-Check canonical TA resolver dependencylerini kontrol eder. Missing resolver varsa report BLOCKED olur ve Send aynı source hash için reddedilir.

4. Pre-Check passed ise Send immutable request artifacti oluşturur ve CP Candidate Generation jobı queueya yazılır.

5. UI candidate job progressini durable event streamden izler. Başarılı candidate artifacts, uncertainty/risk listesi ve test specification ile döner.

6. C.D.P, candidate üzerinden Package Root + immutable Draft Revision oluşturur. Package henüz published değildir.

7. Kullanıcı baselineı ekler; validation jobs syntax/runtime/output/market/repaint/baseline kanıtlarını üretir. Approval koşulları sağlandığında Admin Approve Package ile publish eder.

## 8.3 Generate From Description ile baseline olmayan yeni Condition Package

1. Kullanıcı Package Type = Condition Package ve Creation Mode = Generate From Description seçer. Source Language alanı disabled/hidden olur; normalized source_kind=DESCRIPTION, source_language=null yazılır.

2. Kullanıcı boolean conditionın inputlarını, output true/false anlamını, availability/closed-bar kuralını ve gerekiyorsa Explicit Indicator Linkini tanımlar.

3. Pre-Check UI statei NOT_APPLICABLE gösterilir; Send candidate jobını başlatır.

4. Candidate ve Draft oluşturulduktan sonra validation evidence üretilir. Eşdeğerlik claimi yoksa baseline zorunlu değildir; package experimental/research workflowu ile değerlendirilir.

5. Publish yalnız mode-aware validation policy ve yetkili approval ile mümkündür. UI "no baseline" mesajını "failed" veya "approved equivalent" gibi yanlış yorumlamaz.

## 8.4 Missing ESP dependency recovery

1. Pre-Check, code içinde `ta.some_new_function` dependencysi algılar; Trusted ESP registryde signature-compatible resolver revision bulunmaz.

2. Report BLOCKED durumunu, eksik canonical keyleri ve source hashini saklar. Candidate conversion bu branch için başlamaz.

3. User, Supervisor veya Agent resolver proposal/draft hazırlayabilir; ancak trusted ESP registry publish ve production approval yalnız Admin tarafından yapılabilir.

4. Yeni compatible ESP revision yayımlandıktan sonra eski report otomatik Passed sayılmaz. Kullanıcı/Agent aynı veya güncel source hash ile Pre-Checki tekrar çalıştırır.

5. Yeni report exact ESP revisionını dependency snapshotına pinler; sadece bundan sonra Send/Candidate path devam eder.

## 8.5 Stale / concurrency / retry recovery

- Stale source: Source body, language, runtime, output contract veya dependency context değişirse previous pre-check, candidate, validation ve approve eligibility stale olur. UI hangi değişikliğin stale yarattığını gösterir; user ilgili stagei tekrar çalıştırır.

- Revision conflict: Başka actor current head revisionı publish ettiyse Approve veya Request Revision `STALE_REVISION`/409 döner. UI server canonical stateini rehydrate eder; Compare, Reload, Derive veya new revision attempt seçenekleri sunar. Client old data ile overwrite yapmaz.

- Job failure: Candidate/validation failure immutable request/draftı silmez. Error artifact, attempt id, tool provenance ve safe retry statement görünür. Retry yeni attempt numarası üretir; aynı attemptin gizli outputunu değiştirmez.

- Network interruption: Submit response kaybolsa bile idempotency key aynı command için aynı request/job identityyi döndürür. UI "Unknown result" yerine GetRequestByIdempotencyKey ile durumu yeniden sorgular.

# 9. Backend, Domain, Revision ve Artifact Davranışı

## 9.1 Persistent domain model

<table>
  <tr>
    <th>Entity</th>
    <th>Zorunlu alanlar</th>
    <th>Bu sayfayla ilişkisi</th>
  </tr>
  <tr>
    <td>PackageRequest</td>
    <td>request_id, actor/principal, package_type, mode, source_kind/language, runtime, source_content_hash, selected identity/output/compatibility, precheck ref, idempotency key, state.</td>
    <td>Send sonrası immutable request source-of-truth. Browser prompt statei değildir.</td>
  </tr>
  <tr>
    <td>PackageCandidate</td>
    <td>candidate_id, request_id, attempt_no, input hash, generated implementation ref, output contract, dependencies, uncertainty/risk, test spec, tool provenance, state.</td>
    <td>CP Agent outputu. Candidate package değildir; draft creationa kaynak olur.</td>
  </tr>
  <tr>
    <td>PackageRoot</td>
    <td>package_root_id, package_type, owner, visibility, lifecycle, current_revision_id.</td>
    <td>C.D.P ile yeni root gerekirse oluşur. Type immutable olur.</td>
  </tr>
  <tr>
    <td>PackageRevision</td>
    <td>package_revision_id, root ref, parent ref, content/dependency hash, payload, implementation artifact ref, output contract, validation summary, workflow state.</td>
    <td>Immutable revision. Draft/approved is revision.approval_state; published is visibility_scope. The current pointer/projection changes atomically after authorization.</td>
  </tr>
  <tr>
    <td>PackageDependency</td>
    <td>owner revision ref, dependency root/revision ref, kind, contract compatibility, resolution state.</td>
    <td>ESP, Indicator/Condition links and other dependencies exact revision IDs ile pinlenir.</td>
  </tr>
  <tr>
    <td>Artifact</td>
    <td>source body, code, request transcript, generated code, analyses, baseline, reports, logs, test specification.</td>
    <td>Object storage immutable asset/references. UI file list projectionu buradan gelir.</td>
  </tr>
  <tr>
    <td>AsyncJob / ValidationRun</td>
    <td>job id, kind, status, correlation id, retry/attempt, event stream cursor, evidence refs.</td>
    <td>Pre-check, candidate generation, baseline parse and validation HTTP lifecycle outside durable jobs.</td>
  </tr>
  <tr>
    <td>AuditEvent / OutboxEvent</td>
    <td>actor, action, entity refs, prior/next state, correlation, evidence refs.</td>
    <td>Append-only audit and downstream UI/event delivery consistency.</td>
  </tr>
</table>

## 9.2 State model and no-silent-mutation rules

<table>
  <tr>
    <th>CreatePackageRequest: draft_editor (transient only) -&gt; submitted -&gt; precheck_pending | precheck_passed | precheck_blocked | precheck_not_applicable<br/>CandidateJob: queued -&gt; running -&gt; succeeded | failed | cancelled<br/>Candidate: current | stale | superseded<br/>PackageRoot.root.lifecycle_state: active | deprecated | soft_deleted<br/>PackageRevision.revision.validation_state: pending | passed | warning | failed | stale<br/>PackageRevision.revision.approval_state: draft | approval_requested | approved | rejected<br/>PackageRevision.visibility_scope: private | explicitly_shared | published | system<br/><br/>Invariant: root lifecycle, revision validation, revision approval and visibility are independent facets. Source/dependency/runtime/output change makes related evidence stale. Immutable historical/published revision payload is never updated in place.</th>
  </tr>
</table>

Production UI can show V18-friendly labels such as Not Created, Draft, Testing, Eligible for Approval, Experimental and Approved, but the UI must render them from the explicit backend state/evidence summary. A local button click, `cpState.validated = true`, or a file-input selection cannot itself certify validation or approval.

## 9.3 Package source files and artifact projection

<table>
  <tr>
    <th>V18 file row</th>
    <th>Production artifact requirement</th>
  </tr>
  <tr>
    <td>manifest.json</td>
    <td>Candidate or Package Revision manifest: identity, output contract, dependency snapshot, state, provenance and content hashes.</td>
  </tr>
  <tr>
    <td>original_request.txt</td>
    <td>Immutable normalized request body; original client text and source hash.</td>
  </tr>
  <tr>
    <td>original_source.pine</td>
    <td>Source code asset. Actual extension derived from source language; never force `.pine` for Python/C++/description.</td>
  </tr>
  <tr>
    <td>generated_indicator.py / embedded_resolver.php</td>
    <td>Generated implementation artifact. Filename is presentation-only; runtime adapter and artifact hash are authoritative. Production V1 initial adapter is Python Runtime v1.</td>
  </tr>
  <tr>
    <td>ai_analysis_report.json</td>
    <td>Candidate analysis, uncertainty, semantic interpretation and risk report with tool/model provenance.</td>
  </tr>
  <tr>
    <td>test_specification.json</td>
    <td>Type/mode specific validation plan, expected outputs, timing contract and baseline tolerance policy.</td>
  </tr>
  <tr>
    <td>execution_log.txt</td>
    <td>Job/validation log artifact. Must not expose credentials or provider keys.</td>
  </tr>
</table>

## 9.4 Example API capability parity

<table>
  <tr>
    <th>Human UI -&gt; POST /create-package/requests -&gt; CreatePackageRequestService -&gt; PackageCandidateGenerationJob<br/>Agent Tool -&gt; tool.create_package_request(...) -&gt; same CreatePackageRequestService -&gt; same job<br/><br/>Human UI -&gt; POST /package-candidates/{id}/draft -&gt; PackageDraftService<br/>Agent Tool -&gt; tool.create_draft_package(candidate_id, ...) -&gt; same PackageDraftService<br/><br/>Human UI -&gt; POST /package-revisions/{id}/approve -&gt; ApprovalService<br/>Agent Tool -&gt; tool.request_package_approval(...) -&gt; same ApprovalService (no policy bypass)</th>
  </tr>
</table>

# 10. Agent İlişkisi ve UI-Siz Eşdeğer Tool/API Kullanımı

Agent, CP AGENT CHAT BOARD içindeki metinle çalışan bir frontend persona değildir. CP Agent yalnız Create Package pipelineındaki candidate generation capabilitysidir; Alpha Agent ise sürekli araştırma loopunu backendde ayrı runtime olarak yürütür. Bu iki kavram aynı şey değildir.

- Agent tool parity: Agent `create_package_request`, `start_precheck`, `create_draft_from_candidate`, `upload_baseline_reference`, `start_validation`, `request_revision` ve `request_approval` capabilitylerini aynı server-side command contracts üzerinden kullanır.

- Ownership: Agentın oluşturduğu request/candidate/draft owner = Agent principal olur. Agent başkasının package revisionını normal edit etmez; derive/reuse eder. Admin Agent outputunu yönetebilir.

- Continuous work: Agent candidate job veya missing ESP branchi nedeniyle UI chat response beklemez. Blocked branch için artifact/follow-up task üretir; diğer research tasklarına safe checkpoint yapısıyla devam eder.

- Approval boundary: Agent publish şartlarını değerlendirebilir, evidence hazırlayabilir ve approval request oluşturabilir; Admin-only ESP registry update ya da Admin-only approvalu kendisi bypass edemez.

- Provenance: Agent generated package artifacts agent_run_id, task_id, checkpoint_id, tool/model provider, source context, request/candidate IDs ve dependency revisions taşır.

<table>
  <tr>
    <th>Canonical Rule: Frontendde görünen Send, C.D.P veya Validation buttonlarının içinde Agentın kullanamadığı gizli iş mantığı yazılamaz. İnsan UI ve Agent Tool iki giriş yüzeyidir; gerçek iş aynı Domain Service ve durable worker zincirinden geçer.</th>
  </tr>
</table>

# 11. Validation, Error ve Recovery Contract

<table>
  <tr>
    <th>Sınıf</th>
    <th>Server-side rule</th>
    <th>UI / Agent recovery</th>
  </tr>
  <tr>
    <td>Field validation</td>
    <td>Required fields, enums, typed output contract, mode-specific source and language constraints request submitte doğrulanır.</td>
    <td>Inline field error + error summary. Agent structured ValidationIssue list alır; request yeniden düzenlenir.</td>
  </tr>
  <tr>
    <td>Source mismatch</td>
    <td>Selected language, content detector and parser conflicting source belirlerse conversion başlamaz.</td>
    <td>Show SOURCE_LANGUAGE_MISMATCH with detected syntax; choose correct language or clarify source. No silent auto-rewrite.</td>
  </tr>
  <tr>
    <td>Dependency validation</td>
    <td>Pine TA function name + signature + return shape + runtime adapter with exact ESP revision resolve edilir.</td>
    <td>MISSING_RESOLVER report; proposal/Admin publish then rerun Pre-Check.</td>
  </tr>
  <tr>
    <td>Output contract validation</td>
    <td>Package type, declared output type, implementation signature and downstream use compatibility match etmeli.</td>
    <td>OUTPUT_CONTRACT_INVALID; revise candidate or type/contract, re-run impacted checks.</td>
  </tr>
  <tr>
    <td>Runtime validation</td>
    <td>Target runtime adapter active and worker-executable olmalı.</td>
    <td>RUNTIME_UNAVAILABLE or RUNTIME_CONTRACT_MISMATCH; choose registered runtime, re-submit.</td>
  </tr>
  <tr>
    <td>Timing / future leak</td>
    <td>Closed-bar, event/available time, future index and MTF forwarding static + dynamic checksle doğrulanır.</td>
    <td>FUTURE_LEAK_RISK / REPAINT_RISK evidence. Request revision; cannot approve while blocker severity unresolved.</td>
  </tr>
  <tr>
    <td>Baseline validation</td>
    <td>Equivalence claims require metadata and contract-tolerance compatible comparison.</td>
    <td>BASELINE_METADATA_INVALID / BASELINE_MISMATCH. Keep evidence; upload corrected baseline or withdraw equivalence claim through new revision.</td>
  </tr>
  <tr>
    <td>Authorization</td>
    <td>View/use/create/edit/approve/delete policies actor and resource contextle doğrulanır.</td>
    <td>ACCESS_DENIED / OWNER_REQUIRED / APPROVAL_FORBIDDEN. UI does not retry blindly; present access/derive path.</td>
  </tr>
  <tr>
    <td>Concurrency</td>
    <td>expected_head_revision_id/head version differs.</td>
    <td>STALE_REVISION/409. Rehydrate canonical state; compare/revise/derive. Never force old payload over server head.</td>
  </tr>
  <tr>
    <td>Job failure</td>
    <td>Worker failure keeps request/candidate artifact and failure evidence.</td>
    <td>Show attempt ID, safe retry action and next step. Same idempotency key returns original command result; retry creates next attempt.</td>
  </tr>
</table>

# 12. Lifecycle, Audit, Trash ve Historical Integrity

Clear yalnız editor davranışıdır. Clear, CreatePackageRequest, Candidate, Draft Package, baseline asset, validation evidence veya published Package Revisionı silmez. Bu tür kalıcı nesneler için ayrı soft-delete commandı gerekir.

<table>
  <tr>
    <th>Olay</th>
    <th>Canonical behavior</th>
    <th>Historical / Trash effect</th>
  </tr>
  <tr>
    <td>Create Draft Package</td>
    <td>Candidate artifacts ile Package Root + immutable Draft Revision oluşturur.</td>
    <td>Audit: package_draft_created. No Trash record.</td>
  </tr>
  <tr>
    <td>Request Revision</td>
    <td>New candidate attempt + new revision chain; prior draft/evidence immutable kalır.</td>
    <td>Audit: revision_requested. Old revision historical graphte kalır.</td>
  </tr>
  <tr>
    <td>Approve / publish</td>
    <td>Server evidence/policy checks sonrası atomic current revision projection.</td>
    <td>Audit: approval_granted/rejected, revision_published. Backtest/Strategy later exact revision pinler.</td>
  </tr>
  <tr>
    <td>Deprecate</td>
    <td>New use için yönlendirme/engelleme; historical refs preserved.</td>
    <td>Historic strategy/run manifests continue exact pinned revision reference.</td>
  </tr>
  <tr>
    <td>Soft delete Package Root</td>
    <td>New library discovery/use/revision is blocked; root active catalogdan çıkar.</td>
    <td>Trash entry + audit + outbox. Historical package refs and run manifests readable. Restore/permanent delete Admin only.</td>
  </tr>
  <tr>
    <td>Soft delete ESP</td>
    <td>Active resolver registry projectiondan kaldırılır.</td>
    <td>New Pre-Check deleted resolverı resolved kabul etmez. Historical candidate/package/run records pinned ESP revisionı açıklamak için saklar.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>Only Admin restores eligible object; current policy/dependency checks repeat.</td>
    <td>Audit: restored. Restore does not rewrite old manifests or auto-republish stale candidate.</td>
  </tr>
  <tr>
    <td>Permanent delete</td>
    <td>Only Admin after retention/policy checks.</td>
    <td>Purged binary artifacts may be removed per policy, but audit/legal provenance handling must remain explicit; never silently erase historical manifest references.</td>
  </tr>
</table>

# 13. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Konu</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Add Package types</td>
    <td>Strategy, Trading Signal, Trade Log show in popover.</td>
    <td>Only Strategy Package can seed a Strategy Draft. Signal/Log are external Mainboard working items.</td>
    <td>Remove legacy Signal/Log options. The menu may retain &quot;Add Package&quot; temporarily, but content/action must be strategy-only.</td>
  </tr>
  <tr>
    <td>Target Runtime</td>
    <td>PHP is sole option; prompt asks Python output.</td>
    <td>Runtime selected from active registered adapters; must be executable and validated.</td>
    <td>Python Runtime v1 is initial active target. PHP only after registry activation/evidence.</td>
  </tr>
  <tr>
    <td>Send / CP Agent</td>
    <td>Adds local chat messages, clears textarea and enables C.D.P.</td>
    <td>Creates immutable request and queues async candidate-generation job.</td>
    <td>UI message board becomes job/artifact projection; no browser-side generation decision.</td>
  </tr>
  <tr>
    <td>Pre-Check</td>
    <td>Regex-like text scan and local modal; blocked flag stored in cpState.</td>
    <td>Parser/lexer + signature-aware resolver registry report, durable artifact.</td>
    <td>UI retains modal/summary, but resolver correctness is server-side and detailed Pre-Check page owns full report UI.</td>
  </tr>
  <tr>
    <td>C.D.P</td>
    <td>Sets local Draft, v1 and fake files.</td>
    <td>Idempotently creates Package Root + immutable Draft Revision from current candidate.</td>
    <td>Do not create duplicate drafts when same candidate command is retried.</td>
  </tr>
  <tr>
    <td>Baseline / validation</td>
    <td>Local boolean flags mark all rows passed; baseline absent means Experimental.</td>
    <td>Async evidence jobs validate metadata, contracts, timing and equivalence; exact policies mode-aware.</td>
    <td>Keep V18 categories as friendly labels only; authoritative state/evidence backend-derived.</td>
  </tr>
  <tr>
    <td>Approve</td>
    <td>Local enabled button inserts visual package in target.</td>
    <td>Authorized server-side approval/publish transition with concurrency and dependency checks.</td>
    <td>Button does not write catalog directly; publish transaction creates canonical projection.</td>
  </tr>
  <tr>
    <td>Clear</td>
    <td>Resets cpState and DOM.</td>
    <td>Clears transient editor only.</td>
    <td>No destructive persistence behavior is attached to Clear.</td>
  </tr>
</table>

# 14. Kodcu AI için Implementation Rules

1. PackageKind enumunu yalnız strategy_package, indicator_package, condition_package ve embedded_system_package değerleriyle sınırla. Trading Signal ve Trade Logu Add Package veya Create Package type listesinden kaldır.

2. Add Package actionını existing Strategy Package revisionından yeni Strategy Draft oluşturan derive/use commandı olarak uygula. Source package root/revisionı mutate etme, clone ID verme veya callerın source package ownerlığını devretme.

3. Create Package ekranındaki transient form stateini durable request/revision statei olarak kullanma. Send sonrası canonical request/job responseuyla UIyi rehydrate et.

4. Her CreatePackageRequest için normalized source_kind/source_language ayrımını uygula. Natural Languageı source language enumunda persist etme; Generate From Description modeunda source_language=null kullan.

5. PineScript code detection veya TA dependency resolution için V18 regexini production authority yapma. Parser/lexer ve signature-aware resolver registry kullan.

6. Source body, source language, target runtime, output contract veya dependency context değiştiğinde önceki Pre-Check, candidate, validation ve approval eligibilityyi server-side STALE yap.

7. CP Agent candidate generationını HTTP request veya browser session içinde çalıştırma. Command job_id döndürmeli; worker artifacts/provenance üretmeli; UI SSE/polling ile durable status göstermelidir.

8. C.D.P aynı candidate için idempotent olmalıdır. Aynı idempotency key ikinci Package Root veya ikinci Draft Revision yaratamaz.

9. Package Revision payloadını, dependency snapshotını, implementation refini veya validation evidenceini current row üzerinde update etme. Her işsel değişiklik yeni immutable revision/attempt üretmelidir.

10. Package dependencylerini display name ile değil exact root_id + revision_id ile sakla. ESP dependencyleri resolved canonical revisiona pinle; implicit latest resolver lookup yapma.

11. Target Library satırını writable selector olarak implement etme. Hedef package_type enumundan türeyen read-only catalog projectionudur.

12. Baseline policyyi mode-aware uygula. Translation/repair equivalence claiminde required evidence olmadan publish etme; description-origin packagei baseline olmadığı için otomatik invalid sayma.

13. Closed-bar, future-leak, repaint, available-time and multi-timeframe behaviorini only text warning olarak bırakma. Validation evidence ve output contractın enforce edilen parçası yap.

14. Approve/Publish commandini server-side current validation, dependency, baseline, role, ownership ve expected_head_revision_id checks olmadan çalıştırma. ESP trusted registry publishini Admin-only yap.

15. Clearın yalnız transient editor reset olduğunu koru. Delete için onaylı soft-delete commandı, Trash record, audit event ve historical manifest integrity gereklidir.

16. Agent için UI bypass veya ayrı daha zayıf schema yazma. Human UI ve Agent Tool aynı CreatePackageRequest, Draft, Validation ve Approval domain servicesini kullanmalıdır.

17. CP Agent chat messagesini Alpha Agentın sürekli araştırma loopu olarak modelleme. CP Agent candidate capabilitydir; Alpha Agent backend runtime ayrı bir sistem aktörüdür.

# 15. Acceptance Tests

<table>
  <tr>
    <th>Kategori</th>
    <th>Doğrulanabilir senaryo / beklenen sonuç</th>
  </tr>
  <tr>
    <td>Canonical types</td>
    <td>Add Package popoverında Productionda Trading Signal/Trade Log seçeneği yoktur; Create Package type enumu yalnız indicator/condition/embedded_system kabul eder; manipüle edilmiş request signal/trade_log gönderirse reddedilir.</td>
  </tr>
  <tr>
    <td>Add package derivation</td>
    <td>User seçtiği accessible Strategy Package revisionından Strategy Draft üretir. Draft provenance source root/revision ve dependency snapshot taşır; source package payload/owner değişmez.</td>
  </tr>
  <tr>
    <td>Use authorization</td>
    <td>User bir packagei görebilir ancak use izni yoksa Add Strategy From Package `ACCESS_DENIED`/use-denied döner; UI selection stale statei temizler.</td>
  </tr>
  <tr>
    <td>Request requiredness</td>
    <td>Translate Existing Code seçiliyken code body ve source language zorunludur. Generate From Description seçiliyken source_language=null normalize edilir. Other language seçiliyken Other Language Name olmadan Send bloklanır.</td>
  </tr>
  <tr>
    <td>Runtime alignment</td>
    <td>V18 PHP/Python çelişkisi Productionda görünmez: target runtime registered Python Runtime v1dir. Inactive runtime ID ile Send `RUNTIME_UNAVAILABLE` döner.</td>
  </tr>
  <tr>
    <td>Pre-Check stale</td>
    <td>Pine source için Passed Pre-Checkten sonra target runtime değiştirildiğinde report STALE olur, Send yeniden pre-check olmadan candidate generation başlatmaz.</td>
  </tr>
  <tr>
    <td>Missing ESP</td>
    <td>Pre-Check ta.unknown_fn için signature-compatible trusted ESP bulunamadığında BLOCKED report üretir; candidate job queueya yazılmaz; Admin publish sonrası fresh Pre-Check exact ESP revisionı pinler.</td>
  </tr>
  <tr>
    <td>Async resilience</td>
    <td>Send response sonrası browser refresh/logout gerçekleşse candidate job devam eder. UI geri açıldığında same request/job state ve artifacts backendden rehydrate edilir.</td>
  </tr>
  <tr>
    <td>Idempotency</td>
    <td>Aynı Send idempotency keyi aynı request/job identitysini döndürür. Aynı C.D.P keyi ikinci draft oluşturmaz.</td>
  </tr>
  <tr>
    <td>Revision immutability</td>
    <td>Validation failed draft için Request Revision yeni candidate attempt ve parent_revision_ref üretir; old draft/code/reportleri değişmeden kalır.</td>
  </tr>
  <tr>
    <td>Baseline policy</td>
    <td>Translation equivalence claimi baseline metadata eksikken Approve disabled ve server `BASELINE_REQUIRED` verir. Generate From Description + no equivalence claim mode-aware policy ile baseline olmadan validation pathine devam edebilir.</td>
  </tr>
  <tr>
    <td>Future-leak validation</td>
    <td>Candidate static review ve prefix-invariance testi future data/repaint bulursa critical evidence yazılır; Approve server-side reddedilir.</td>
  </tr>
  <tr>
    <td>Approval policy</td>
    <td>Supervisor veya Agent valid candidate için approval request oluşturabilir fakat Admin-only publish/ESP registry transitionı execute edemez. UI button visible/disabled olsa da backend guard uygulanır.</td>
  </tr>
  <tr>
    <td>Clear boundary</td>
    <td>Clear unsent editorı temizler; submitted request, candidate, draft, baseline asset, validation artifact veya published Packageyi silmez.</td>
  </tr>
  <tr>
    <td>Trash/history</td>
    <td>Soft-deleted package new catalog/use pathinden çıkar; only Admin restore/purge yapar; historical Strategy/Backtest manifests pinned revisionı açıklamaya devam eder.</td>
  </tr>
  <tr>
    <td>Agent parity</td>
    <td>Agent Tool aynı request schema ile candidate generation başlatır; UI açık değilken job/test/draft artifacts oluşur; Agent source UI DOMuna veya chat responseuna bağlı değildir.</td>
  </tr>
</table>

# 16. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Master priority</td>
    <td>Evet. Modül 8 Create Package canonical lifecycle, Modül 7 package root/revision, Modül 9 Add Package alignment ve Modül 0-3/19 cross-cutting kuralları üst otorite olarak uygulanmıştır.</td>
  </tr>
  <tr>
    <td>Package vs external working object</td>
    <td>Evet. Trading Signal / Trade Log hiçbir yerde Package Type ya da canonical PackageKind olarak tanımlanmamıştır.</td>
  </tr>
  <tr>
    <td>V18 / Production ayrımı</td>
    <td>Evet. Add Package legacy options, PHP/Python contradiction, cpState/local chat/validation behaviorları Production V1den açıkça ayrılmıştır.</td>
  </tr>
  <tr>
    <td>Pre-Check page scope</td>
    <td>Evet. Bu sayfa Pre-Check button/report handoffunu kapsar; parser/resolver report UI ayrıntısı ayrı 7/22 Pre-Check dokümanına bırakılmıştır.</td>
  </tr>
  <tr>
    <td>Agent boundary</td>
    <td>Evet. CP Agent candidate capability olarak, Alpha Agent ise UIden bağımsız continuous backend actor olarak ayrılmıştır.</td>
  </tr>
  <tr>
    <td>Async and source-of-truth</td>
    <td>Evet. Candidate generation, pre-check, baseline parsing ve validation durable job/worker + artifact stateine bağlıdır; UI local state authoritative değildir.</td>
  </tr>
  <tr>
    <td>Lifecycle / Trash</td>
    <td>Evet. Clear non-destructive; delete soft delete; Trash/restore/permanent delete Admin-only; historical revision/manifest integrity korunur.</td>
  </tr>
  <tr>
    <td>Implementation decisions labeled</td>
    <td>Evet. Target runtime registry/Python Runtime v1, Production info panels ve Add Package header alignment açık Implementation Decision olarak ayrılmıştır.</td>
  </tr>
</table>
