---
title: "Entropia V18 — Embedded System Packages Page Documentation v1.1"
page_number: 9
document_type: "Page implementation specification"
source_document: "Entropia_V18_Embedded_System_Packages_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Embedded System Packages Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | PAGE DOCUMENTATION 9/22 | EMBEDDED SYSTEM PACKAGES
> **Original DOCX footer:** Canonical page documentation | Production V1 alignment |

ENTROPIA V18

EMBEDDED SYSTEM PACKAGES

Sayfa Dokümantasyonu 9/22 | Trusted technical-analysis resolver registry, immutable semantics, validation evidence ve dependency pinning sözleşmesi

<table>
  <tr>
    <th>Kapsam sınırı: Bu belge yalnız Embedded System Packages (ESP) scoped catalog görünümünü ve ESPlerin Production V1 resolver-registry davranışını kapsar. Add Package / Create Package ve Pre-Check, ESP adayının nasıl üretildiğini veya eksik dependency gateini ayrı sayfalarda ayrıntılandırır. Package Librarynin genel katalog davranışı, Rationale Families editörü, Strategy Details package pickerı, Ready Check, Trash ekranı ve Backtest Results bu belgenin ayrı UI kapsamı değildir; yalnız ESPnin bu alanlardaki dependency, policy veya lifecycle etkisi kadar anılır.</th>
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
    <td>Entropia V18 | Page Documentation 9/22 | Embedded System Packages | v1.1</td>
  </tr>
  <tr>
    <td>Belge amacı</td>
    <td>V18deki Embedded System Packages hedefini; trusted TA resolver/adaptor catalog, resolver detail, filters, export/delete görünümü, Production V1 registry contractı, immutable revisionlar, dependency resolve, validation evidence, access policy ve Agent parity açısından kodcu AI için uygulanabilir sözleşmeye dönüştürmek.</td>
  </tr>
  <tr>
    <td>Ana Master dayanağı</td>
    <td>Modül 7: 3.4 ESP, 5.3 timing/repaint, 6 dependency/version pinning, 8 catalog projection, 9 lifecycle; Modül 8: 5.3 Pine resolver, 5.4 blocked, 6 ESP canonical TA layer, 9 approval/publish, 10 API/job, 11 audit/Trash/Agent. Canonical Integration: CR-01/CR-02.</td>
  </tr>
  <tr>
    <td>Çapraz Master dayanakları</td>
    <td>Modül 1 role/policy ve System-owned resources; Modül 2 root/revision/ownership; Modül 3 soft delete/Trash; Modül 6 Rationale Family shared-editing exception ve seed Family; Modül 12 Ready Check/Run manifest; Modül 19 frontend-backend contract.</td>
  </tr>
  <tr>
    <td>V18 HTML referansı</td>
    <td>Edit &gt; Package Library &gt; Embedded System Packages menüsü; `showPackagePool(event, &quot;embedded&quot;)`; `packageGroups.embedded`; generic filter bar; expandable package row; Export Package; delete ×; Create Package Pre-Check resolver messaging.</td>
  </tr>
  <tr>
    <td>Kaynak önceliği</td>
    <td>1) Master Technical Reference v1.0, 2) V18 ana HTML, 3) Handoff v1.1, 4) Position Entry Logic örneği. Alt kaynak üst kaynağın Production V1 kararını değiştiremez.</td>
  </tr>
  <tr>
    <td>Açık Implementation Decisionlar</td>
    <td>ESP scoped viewin Production V1de `package_type=embedded_system` ile pinlenmiş Package Library projectionı olarak sunulması; trusted published ESPlerin System-owned registry kaydı olması; V18de eksik System facets ve Rationale seedin düzeltilmesi; performans metriklerinin ESP için N/A olması.</td>
  </tr>
</table>

## 0.1 Source Traceability Map

<table>
  <tr>
    <th>Sayfa konusu</th>
    <th>Master ref</th>
    <th>V18 HTML ref</th>
    <th>Çapraz bağımlılık</th>
    <th>Karar / not</th>
  </tr>
  <tr>
    <td>ESP menu entry ve scoped catalog</td>
    <td>M7 §8, M8 §6</td>
    <td>Edit submenu &gt; Embedded System Packages; `showPackagePool(..., &quot;embedded&quot;)`</td>
    <td>Package Library, Rationale Families</td>
    <td>V18de ayrı sayfa yerine generic catalog içinde target sectiona scroll vardır. Productionda same catalog querynin ESP-scoped projectionı uygulanır.</td>
  </tr>
  <tr>
    <td>Canonical resolver semantics</td>
    <td>M7 §3.4, M8 §5.3 ve §6.2</td>
    <td>ESP_TA_SMA/EMA/RMA/ATR/RSI/WMA/VWAP sample rows</td>
    <td>Pre-Check, Create Package</td>
    <td>Name match yeterli değildir; resolver key + exact signature + adapter + trusted revision gerekir.</td>
  </tr>
  <tr>
    <td>Revision and use pinning</td>
    <td>M7 §4, §6, §9; M2 root/revision model</td>
    <td>Local array row and browser export</td>
    <td>Strategy Details, Run manifest, Agent experiment</td>
    <td>Current revision client memoryden çözülmez; exact `package_revision_id` or transitive resolver revision pinlenir.</td>
  </tr>
  <tr>
    <td>Approval / registry activation</td>
    <td>M8 §5.4, §6.2, §9</td>
    <td>V18 meta Status=Approved</td>
    <td>Create Package / Pre-Check</td>
    <td>Trusted canonical resolver activationı Admin-only server transactiondır; Status texti tek persistence enum değildir.</td>
  </tr>
  <tr>
    <td>Deprecate, delete and Trash</td>
    <td>M7 §9.2, M8 §11.2, M3 ESP policy</td>
    <td>× Move to Trash behavior</td>
    <td>Trash, existing manifests</td>
    <td>Active resolverde default action delete değil Deprecate olmalıdır. Soft delete/purge yalnız Admin/system policy under guard.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kapsam Sınırı

Embedded System Package (ESP), dış kaynak kodlarında geçen temel teknik analiz fonksiyonlarının Entropia runtimeındaki trusted resolver/adaptor tanımıdır. ESP, Strategyde doğrudan entry/exit sinyali üreten generic Indicator Package değildir. Örneğin Pre-Check bir PineScript metninde `ta.rsi(source, length)` çağrısını algıladığında, ESP catalogdan aynı canonical resolver keye, uyumlu function signaturea, onaylı runtime adaptera ve trusted immutable revisiona sahip bir karşılık arar.

ESP sayfasının amacı, insanın ve Agentın hangi teknik primitivein sistem tarafından güvenilir biçimde desteklendiğini görmesini, semantic contractını denetlemesini, dependency/evidence durumunu okumasını, yeni code-conversion veya package üretiminde exact revisiona referans vermesini ve yetkiliyse lifecycle aksiyonu başlatmasını sağlamaktır. Sayfa bir code editor veya generic strategy builder değildir.

<table>
  <tr>
    <th>Canonical Rule: ESP, generic indicator package değildir. CP Agent generated code içine resolver implementasyonunu kopyalamaz; dependency manifestte canonical ESP revisionına referans verir. Bu nedenle aynı `ta.rsi` semantiğinin farklı generated package içinde sessizce farklılaşması yasaktır.</th>
  </tr>
</table>

## 1.1 Araştırma ve üretim zincirindeki konumu

<table>
  <tr>
    <th>PineScript / source code<br/>  -&gt; parser + dependency scan<br/>  -&gt; Embedded Resolver Registry lookup (key + signature + adapter + trust)<br/>  -&gt; Pre-Check pass / dependency blocked<br/>  -&gt; candidate/draft package uses exact ESP revision dependency<br/>  -&gt; validation evidence + approval<br/>  -&gt; Strategy / Backtest Run / Agent experiment manifest pinning</th>
  </tr>
</table>

Bu zincirde ESP yalnız dependency çözüm katmanıdır. Backtest Result performans ölçümü, Trade Log, Trading Signal, Rationale Family kart düzenleme formu veya human-facing Create Package chat inputu bu sayfanın kendi domain nesnesi değildir.

# 2. Erişim, Görünürlük, Ownership ve Server-Side Policy

UIde satırın görünmesi, × düğmesinin aktif olması veya Export düğmesinin render edilmesi authorization kanıtı değildir. Her query ve command server tarafında principal, role, visibility, system-owned state, lifecycle, registry trust, dependency state ve action type ile tekrar doğrulanır.

<table>
  <tr>
    <th>Principal / role</th>
    <th>ESP scoped page</th>
    <th>View / use</th>
    <th>Mutation</th>
    <th>Registry / Trash</th>
  </tr>
  <tr>
    <td>Guest / anonymous</td>
    <td>Görmez; direct route yalnız login/public policyye göre restricted response verir.</td>
    <td>No view, no resolver use, no export.</td>
    <td>No action.</td>
    <td>No registry operation, no Trash.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Own/shared/published/system policy kapsamındaki ESP projectionını görür. Canonical System ESPleri view/use edebilir.</td>
    <td>Trusted active resolveri dependency olarak referanslayabilir; ownership devralmaz.</td>
    <td>System-owned trusted ESPyi edit/delete/deprecate edemez. Kendi proposal draftı için Create Package akışında mutation yapabilir.</td>
    <td>No approval/activation. No Trash.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Shared working scope ve system ESPleri görür/kullanır.</td>
    <td>Exact trusted revisionı new outputa pinleyebilir.</td>
    <td>Başkasının veya System rootunun normal revisionını mutate etmez; resolver proposal/derive oluşturabilir.</td>
    <td>No activation; no Trash.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm ESP root/revision/evidence kayıtlarını görür.</td>
    <td>Use, review, approve/publish, deprecate, emergency policy action.</td>
    <td>System ESP registry activation/deprecation ve allowed soft delete kararlarını yönetir.</td>
    <td>Only Admin: Trash view, restore, permanent delete subject to policy.</td>
  </tr>
  <tr>
    <td>Agent (system actor)</td>
    <td>UIye bağımlı olmadan registry query/resolve çağırır; ilgili visible system working contenti kullanır.</td>
    <td>Exact resolver revisionını candidate/package/experiment manifestine pinler.</td>
    <td>Kendi proposal/draft outputlarını revisionlayabilir; System trusted rootu mutate/activate edemez.</td>
    <td>No Trash. Cannot self-approve / activate canonical resolver.</td>
  </tr>
</table>

Implementation Decision: Trusted, published canonical ESP roots `owner_principal=System` olarak modellenir; `created_by`, proposal origin, reviewer ve Admin approval auditte korunur. İnsan veya Agent tarafından açılan ESP proposal draftsı approvala kadar kendi ownerında kalabilir. Bu karar, Masterdaki System-owned resource örneğini resolver registry için netleştirir.

# 3. V18 Interface Behavior - Yerleşim, Navigasyon ve Görünür Bileşenler

V18de Embedded System Packages için ayrı bir standalone page title veya dedicated editor yoktur. Kullanıcı Edit menüsünde Package Library hover submenu içindeki Embedded System Packages öğesine tıklar. Handler önce in-memory `packagePoolFilterState.type = "embedded"` yapar, ardından generic PACKAGE LIBRARY pageini render eder ve yaklaşık 50 ms sonra `#package-section-embedded` bölümüne scroll eder.

## 3.1 V18 görünür bileşen envanteri

<table>
  <tr>
    <th>Bölge / bileşen</th>
    <th>V18deki davranış ve görünür metin</th>
    <th>Production yorum / kapsam</th>
  </tr>
  <tr>
    <td>Menü yolu</td>
    <td>Edit &gt; Package Library &gt; Embedded System Packages.</td>
    <td>ESP page entrypoint. Productionda route, `package_type=embedded_system` query/path scopeu açar.</td>
  </tr>
  <tr>
    <td>Page title / intro</td>
    <td>Generic title: PACKAGE LIBRARY; intro text package objects için Admin/Supervisor/Agent view/use açıklaması yapar.</td>
    <td>ESP scope generic catalogun alt görünümüdür. Dedicated title: EMBEDDED SYSTEM PACKAGES kullanılmalıdır.</td>
  </tr>
  <tr>
    <td>Filter bar</td>
    <td>Type, Market, Timeframe, Rationale Family, Status, Sort By dropdownları.</td>
    <td>Shared filter UX korunur; ESPde System-specific facets uygulanır.</td>
  </tr>
  <tr>
    <td>Section headings</td>
    <td>Generic page tüm sectionları render eder. Type=embedded stateinde Strategy/Indicator/Condition/Signal/Trade Log bölümleri `No package matched current filters.` gösterebilir; Embedded section hedef olarak scroll edilir.</td>
    <td>Production ESP route yalnız ESP scoped result setini gösterir; canonical olmayan Trading Signal / Trade Log sectionı hiç render edilmez.</td>
  </tr>
  <tr>
    <td>ESP rows</td>
    <td>Her satır: `ESP_TA_* | Embedded TA resolver | ta.* | ...` summary; caret; kullanıcı yetkisine bağlı ×.</td>
    <td>Row root/current revision projectionını taşır; name/array index identity değildir.</td>
  </tr>
  <tr>
    <td>Expanded detail</td>
    <td>Name, details text, Rationale, Market, Timeframe, Status, Backtest Ready, OOS, generic Permissions cardları ve Export Package butonu.</td>
    <td>Production detail gerçek resolver signature, adapter, semantics, test evidence, trust, dependency usage ve history içerir.</td>
  </tr>
  <tr>
    <td>No data state</td>
    <td>`No package matched current filters.`</td>
    <td>Production metni ESP terminology ve clear action ile zenginleştirilir.</td>
  </tr>
  <tr>
    <td>ⓘ buttons</td>
    <td>V18 ESP sectionında ⓘ info button yoktur.</td>
    <td>Production recommended info triggers bu belgede ayrı catalogda verilir; V18 existing control olarak iddia edilmez.</td>
  </tr>
  <tr>
    <td>Delete / Trash</td>
    <td>V18 × local arrayden satırı çıkarır, confirmation olmadan Trash entry ekler.</td>
    <td>Production trusted active resolverde deprecate-first policy uygular; soft delete only Admin/system policy.</td>
  </tr>
  <tr>
    <td>Export</td>
    <td>V18 browserda local JSON Blob indirir.</td>
    <td>Production immutable revision + dependency/evidence manifest export üretir.</td>
  </tr>
</table>

## 3.2 V18 sample Embedded System Package rows

<table>
  <tr>
    <th>V18 name</th>
    <th>Resolver key / function signature displayed or inferable</th>
    <th>V18 summary / details</th>
    <th>Production canonical implication</th>
  </tr>
  <tr>
    <td>ESP_TA_SMA</td>
    <td>`ta.sma(source, length)`</td>
    <td>Simple moving average; trusted dependency note.</td>
    <td>Key `ta.sma`; signature must define ordered source series + integer length, return numeric series, warm-up behavior and adapter.</td>
  </tr>
  <tr>
    <td>ESP_TA_EMA</td>
    <td>`ta.ema(source, length)`</td>
    <td>Exponential moving average.</td>
    <td>Key `ta.ema`; complete alpha/initialization semantics must be immutable in revision.</td>
  </tr>
  <tr>
    <td>ESP_TA_RMA</td>
    <td>`ta.rma(source, length)`</td>
    <td>Running moving average.</td>
    <td>Key `ta.rma`; seed behavior and NA propagation must be test-vector covered.</td>
  </tr>
  <tr>
    <td>ESP_TA_ATR</td>
    <td>`ta.atr(length)`</td>
    <td>Average true range.</td>
    <td>Key `ta.atr`; implicit OHLC dependency, range calculation and warm-up contract required.</td>
  </tr>
  <tr>
    <td>ESP_TA_RSI</td>
    <td>`ta.rsi(source, length)`</td>
    <td>Relative strength index.</td>
    <td>Key `ta.rsi`; zero-loss/zero-gain behavior, output bounds and NA/warm-up semantics must be explicit.</td>
  </tr>
  <tr>
    <td>ESP_TA_WMA</td>
    <td>`ta.wma(source, length)`</td>
    <td>Weighted moving average.</td>
    <td>Key `ta.wma`; weight formula and window boundaries are semantic contract, not user-editable guesswork.</td>
  </tr>
  <tr>
    <td>ESP_TA_VWAP</td>
    <td>`ta.vwap(source)`</td>
    <td>VWAP resolver.</td>
    <td>Key `ta.vwap`; session/anchoring and volume source semantics must be explicit before trusted activation.</td>
  </tr>
</table>

V18 Interface Observation: ESP rows V18de `market=System`, `timeframe=System`, `status=Approved`, `backtestReady=N/A`, `oosPassed=N/A`, `owner=Admin` default metadata ile oluşur. Rationale Family ise `Embedded System / TA Resolver` olarak atanır; fakat V18 seed Family listesinde bu card bulunmaz. Masterın production düzeltmesi bu Familynin seed olarak eklenmesidir.

## 3.3 Shared filter controls - exact V18 options and ESP alignment

<table>
  <tr>
    <th>Field</th>
    <th>V18 exact options / default</th>
    <th>V18 ESP result behavior</th>
    <th>Production V1 contract</th>
  </tr>
  <tr>
    <td>Type</td>
    <td>All; Strategy; Indicator; Condition; Trading Signal; Trade Log; Embedded System. Initial UI select HTMLde All; menu handler in-memory type=embedded yapar.</td>
    <td>Only embedded rows filterden geçer; select visual stateinin rerenderda All göstermesi prototype inconsistencydir.</td>
    <td>ESP route type facetini `embedded_system`e lock eder. Navigate to full Package Library explicit actiondır. Trading Signal/Trade Log package enumunda yoktur.</td>
  </tr>
  <tr>
    <td>Market</td>
    <td>All; BTCUSDT; ETHUSDT; Multi. Default All.</td>
    <td>ESP metadata Market=System olduğu için listedeki non-All market options ile match olmaz.</td>
    <td>Facet values: All / System. Market instrument filter ESP semantic filteri değildir; scope System olarak read-only gösterilir.</td>
  </tr>
  <tr>
    <td>Timeframe</td>
    <td>All; 15m; 1h; 4h; Weekly; Multi. Default All.</td>
    <td>ESP metadata Timeframe=System; non-All optionlar match etmez.</td>
    <td>Facet values: All / System (or Not applicable). Runtime algorithm timeframe semantics detailde okunur; market strategy timeframei değildir.</td>
  </tr>
  <tr>
    <td>Rationale Family</td>
    <td>All + current rationale cards. V18 seed listede Embedded System / TA Resolver eksik.</td>
    <td>Embedded row metadata family ile filter dropdown seçenekleri uyumsuz kalabilir.</td>
    <td>Seed `Embedded System / TA Resolver` family productionda vardır. Assignment editing exception yalnız semantic mappinge uygulanır.</td>
  </tr>
  <tr>
    <td>Status</td>
    <td>All; Backtest Ready; Approved; Imported; Mapped. Default All.</td>
    <td>Embedded rows Approved metadata taşır.</td>
    <td>Single Status field forbidden. Filter facets: lifecycle, validation, approval/publication, registry trust, deprecation state. Imported/Mapped generic ESP trust statusu değildir.</td>
  </tr>
  <tr>
    <td>Sort By</td>
    <td>Created Date; Net Profit; Max Drawdown; ROMAD; Win Rate; Trade Count; Out-of-Sample Result. Default Created Date.</td>
    <td>ESP metric values V18de 0/N/A ile gelir; performance sort anlamsızdır.</td>
    <td>Allowed: Resolver Key, Display Name, Current Revision Date, Validation Result, Trust State, Deprecation State, Last Reviewed. Performance metric sort ESP scopeunda hidden/N/A.</td>
  </tr>
</table>

# 4. Production Backend Behavior - Canonical Embedded Resolver Registry

Production V1de ESP page, frontende önceden yüklenmiş `packageGroups.embedded` dizisini filtrelemez. Backend, callerın görebileceği `package_type=embedded_system` roots için role-aware, lifecycle-aware ve registry-aware scoped projection döndürür. List query yalnız active/current/detail-safe projectionları verir; detail query ise root, current immutable revision, provenance, dependency evidence ve allowed action projectionını birleştirir.

## 4.1 Logical domain records

<table>
  <tr>
    <th>Record</th>
    <th>Core fields</th>
    <th>Purpose / invariants</th>
  </tr>
  <tr>
    <td>PackageRoot</td>
    <td>`package_root_id`, `package_type=embedded_system`, `owner_principal`, `created_by`, `visibility_scope=system|published|explicitly_shared|private`, `root.lifecycle_state=active|deprecated|soft_deleted`, `current_revision_id`.</td>
    <td>Stable resolver identity and access context. `package_type` root creationda set edilir; later mutate edilmez.</td>
  </tr>
  <tr>
    <td>PackageRevision</td>
    <td>`package_revision_id`, parent revision, immutable payload hash, resolver contract, adapter ref, semantics spec, validation config, dependency refs, created_at/by.</td>
    <td>Technical truth. Any semantic, signature, code, adapter, contract or test specification change creates a new revision.</td>
  </tr>
  <tr>
    <td>EmbeddedResolverContract</td>
    <td>`resolver_key`, canonical signature, parameter contract, return shape, warm-up, NA behavior, time/availability semantics, repaint/lookahead policy, error behavior.</td>
    <td>Pre-Check exact matching and conversion correctness. Same function name alone is not a resolver match.</td>
  </tr>
  <tr>
    <td>RuntimeAdapterRef</td>
    <td>target runtime, adapter artifact/version, supported runtime ABI/capabilities, deterministic execution policy.</td>
    <td>Separates public semantic contract from implementation adapter. UI may show target runtime; it cannot silently substitute an incompatible adapter.</td>
  </tr>
  <tr>
    <td>ValidationEvidence</td>
    <td>test vector set, static review, runtime verification, differential/baseline result where applicable, prefix-invariance, signature verification, review status.</td>
    <td>Trust evidence; passed tests are required before canonical registry activation.</td>
  </tr>
  <tr>
    <td>ResolverRegistryEntry</td>
    <td>resolver key -&gt; trusted active revision pointer, supported signatures/adapters, effective state, deprecated/replacement pointer.</td>
    <td>Makes a revision discoverable to Pre-Check. It is not a mutable alias that retroactively changes old manifests.</td>
  </tr>
  <tr>
    <td>PackageDependency</td>
    <td>consumer revision -&gt; exact ESP revision, dependency purpose, optionality, compatibility proof.</td>
    <td>Generated package and strategy manifests pin exact revision. No implicit latest lookup.</td>
  </tr>
  <tr>
    <td>Audit / Artifact records</td>
    <td>event id, actor, command/correlation id, before/after state, evidence refs, agent task id if applicable.</td>
    <td>Append-only trace for proposal, validation, activation, deprecation, soft delete, restore and purge.</td>
  </tr>
</table>

## 4.2 Resolver contract - minimum immutable payload

<table>
  <tr>
    <th>Canonical Rule: A resolver is resolved only when function key, selected exact signature, argument compatibility, return shape, warm-up behavior, designated runtime adapter and trust/lifecycle state are all compatible. `ta.rsi` text match without these checks is insufficient.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Payload group</th>
    <th>Required production fields</th>
    <th>Validation / engine effect</th>
  </tr>
  <tr>
    <td>Identity</td>
    <td>`resolver_key*`; `display_name*`; `package_type=embedded_system`; `contract_version*`; immutable content hash.</td>
    <td>Key unique within active registry scope; normalized canonical key comparison; display name is not identity.</td>
  </tr>
  <tr>
    <td>Function signature</td>
    <td>`function_name*`; ordered arguments*; min/max arity*; argument types*; optional defaults; return type/shape*; unit/series semantics.</td>
    <td>Pre-Check compares parsed call with signature. Wrong parameter order, arity or return shape = `RESOLVER_SIGNATURE_MISMATCH`.</td>
  </tr>
  <tr>
    <td>Semantic behavior</td>
    <td>warm-up rule*; seed/initialization behavior*; NA/null propagation*; boundary behavior*; numerical precision/tolerance policy; error behavior*.</td>
    <td>Test vectors must cover edge cases. Different behavior requires new revision, not a comment update.</td>
  </tr>
  <tr>
    <td>Timing / integrity</td>
    <td>`closed_bar_only` or intrabar capability; `available_at`; repaint policy*; future/lookahead prohibited rule*; timeframe/session semantics*.</td>
    <td>Candidate package cannot claim a value earlier than resolver availability. Critical future leak/repaint blocks trusted activation.</td>
  </tr>
  <tr>
    <td>Runtime adapter</td>
    <td>target runtime*; `adapter_artifact_ref*`; adapter version*; ABI/capability compatibility; deterministic execution flags*.</td>
    <td>Pre-Check refuses a key whose trusted revision lacks a compatible designated adapter for requested target runtime.</td>
  </tr>
  <tr>
    <td>Evidence</td>
    <td>test vector set*; expected outputs*; static review result*; runtime test result*; validation report refs*; reviewer/approval record when trusted.</td>
    <td>Passing evidence is a precondition for registry activation. LLM output or package name is not evidence.</td>
  </tr>
  <tr>
    <td>Lifecycle linkage</td>
    <td>validation state, publication/approval state, registry trust state, deprecation/replacement reference, current revision pointer.</td>
    <td>Facets are separate. No single V18-style Status enum may collapse them.</td>
  </tr>
</table>

## 4.3 Resolver query and Pre-Check resolution algorithm

<table>
  <tr>
    <th>resolve_embedded_dependency(parsed_call, target_runtime):<br/>  1. normalize canonical resolver_key and parsed argument list<br/>  2. query registry for active trusted candidates by key<br/>  3. require exact compatible signature: arity, order, types, optional args, return shape<br/>  4. require designated adapter compatible with target_runtime and runtime ABI<br/>  5. require lifecycle ACTIVE, validation PASSED, trust=TRUSTED, not deleted<br/>  6. return exact package_revision_id + contract/evidence snapshot<br/>  7. otherwise return structured missing / signature mismatch / adapter mismatch diagnostic</th>
  </tr>
</table>

Resolution output is appended to the Pre-Check report and later copied into the Candidate/Draft dependency manifest. A subsequent resolver update does not rewrite the prior report, candidate, package revision, Strategy Revision, Backtest Run or Agent experiment. New work may choose the current approved revision only through a new explicit resolution run.

# 5. Interaction State Matrix

<table>
  <tr>
    <th>State</th>
    <th>List / row behavior</th>
    <th>Detail / action behavior</th>
    <th>Payload / engine effect</th>
  </tr>
  <tr>
    <td>Default scoped load</td>
    <td>Server query with type=`embedded_system`, default sort Resolver Key or most recently reviewed.</td>
    <td>Summary rows show loading skeleton then current projections.</td>
    <td>No client-local resolver catalog is authoritative.</td>
  </tr>
  <tr>
    <td>Empty permitted set</td>
    <td>ESP-specific empty state; Clear / refresh action available.</td>
    <td>No stale prior detail remains selected.</td>
    <td>No resolver assumed available; Pre-Check remains unable to resolve missing call.</td>
  </tr>
  <tr>
    <td>Active + trusted</td>
    <td>Visible and selectable as dependency subject to adapter/signature match.</td>
    <td>Detail shows trust evidence, exact current revision, exports, usage count, history.</td>
    <td>Eligible for new Pre-Check resolution; exact revision pin required.</td>
  </tr>
  <tr>
    <td>Draft / candidate</td>
    <td>Visible only to eligible owner/Admin and appropriate working scope.</td>
    <td>Read evidence/proposal; activation hidden/disabled unless Admin after validation.</td>
    <td>Not resolvable by Pre-Check as canonical dependency.</td>
  </tr>
  <tr>
    <td>Validation running</td>
    <td>Status facet shows Validation running; detail evidence list refreshes through job event.</td>
    <td>Approve/activate disabled; retry only if job policy permits.</td>
    <td>No trusted resolution; existing old revision remains unaffected.</td>
  </tr>
  <tr>
    <td>Validation failed / blocked</td>
    <td>Visible to eligible actor with diagnostic.</td>
    <td>Activate disabled; Request Revision / open evidence enabled according to policy.</td>
    <td>Pre-Check reports missing or non-resolvable; candidate conversion branch blocked.</td>
  </tr>
  <tr>
    <td>Deprecated / superseded</td>
    <td>Visible in history and optionally catalog with Deprecated facet; excluded from default new-work selector.</td>
    <td>Replacement resolver reference and impact summary shown.</td>
    <td>Historical manifests continue reading pinned revision. New resolution targets latest trusted active policy-compatible revision.</td>
  </tr>
  <tr>
    <td>Soft deleted</td>
    <td>Excluded from active scoped list, pickers and resolution registry.</td>
    <td>Normal detail route responds not found; Admin reaches safe snapshot in Trash only.</td>
    <td>New dependency resolution fails. Historical pinned manifest reads remain possible under historical provenance policy.</td>
  </tr>
  <tr>
    <td>Stale / concurrent</td>
    <td>List/detail response includes current revision token.</td>
    <td>Mutating action returns conflict banner; Reload, Compare, or Create Revision route shown.</td>
    <td>No last-write-wins activation/deprecation. Old request cannot overwrite new registry state.</td>
  </tr>
  <tr>
    <td>Permission denied</td>
    <td>Row omitted from normal list or action disabled as UX only.</td>
    <td>Direct detail/action returns structured access denied.</td>
    <td>No data mutation; optional denial audit may be recorded.</td>
  </tr>
</table>

# 6. Field Contract Matrix - Filters, Detail Projection and Action Dialogs

V18 embedded section has no create/edit input form and no `*` marker. Therefore its existing visible filters are optional query inputs, not required persistence fields. Production action dialogs have their own conditional requiredness. A star (`*`) below means required in the Production request schema, server-side validation, Agent tool schema and Ready/Pre-Check policy - not only in the UI.

<table>
  <tr>
    <th>Field / control</th>
    <th>UI type / V18 default</th>
    <th>Requiredness / options</th>
    <th>Production payload and validation</th>
  </tr>
  <tr>
    <td>Resolver scope type</td>
    <td>V18 generic Type select; UI HTML default All, menu handler sets hidden filter state to embedded.</td>
    <td>Query optional in full Library; fixed/locked to Embedded System Package in ESP scoped route.</td>
    <td>`package_type=embedded_system`. Reject `trading_signal` and `trade_log` values. Navigation to full Library is separate route.</td>
  </tr>
  <tr>
    <td>Market facet</td>
    <td>Dropdown. All / BTCUSDT / ETHUSDT / Multi. Default All.</td>
    <td>Optional query; V18 has no System option.</td>
    <td>Production ESP options All / System. `market_scope=system`; user cannot claim trading symbol scope for a resolver root.</td>
  </tr>
  <tr>
    <td>Timeframe facet</td>
    <td>Dropdown. All / 15m / 1h / 4h / Weekly / Multi. Default All.</td>
    <td>Optional query; V18 has no System option.</td>
    <td>Production ESP options All / System / Not applicable. Runtime contract may state timeframe/session semantics separately.</td>
  </tr>
  <tr>
    <td>Rationale Family facet</td>
    <td>Dropdown. All + active Family cards.</td>
    <td>Optional. Production seeded `Embedded System / TA Resolver` is selectable.</td>
    <td>`rationale_family_id` query. Assignment mapping may be shared-edited, but cannot override resolver contract or trust.</td>
  </tr>
  <tr>
    <td>Lifecycle / trust facet</td>
    <td>V18 single Status select: All, Backtest Ready, Approved, Imported, Mapped.</td>
    <td>Optional filters.</td>
    <td>Separate `root.lifecycle_state`, `revision.validation_state`, `revision.approval_state`, `visibility_scope`, and `registry_trust_state`. Do not model publication, trust or deprecation as one pseudo `status=Approved` enum.</td>
  </tr>
  <tr>
    <td>Sort</td>
    <td>V18 Created Date / performance metrics / OOS.</td>
    <td>Optional.</td>
    <td>`sort=resolver_key|display_name|current_revision_created_at|validation_state|trust_state|last_reviewed_at`. Performance sorts invalid for ESP.</td>
  </tr>
  <tr>
    <td>Expand detail</td>
    <td>V18 caret ▼/▲.</td>
    <td>No required fields.</td>
    <td>Query by `package_root_id` and `current_revision_id`; server returns action projection and ETag/revision token.</td>
  </tr>
  <tr>
    <td>Resolver Key *</td>
    <td>Production detail / proposal/revision identity panel.</td>
    <td>Always required for proposal/activation. Example `ta.rsi`. Immutable after root creation; rename requires new root/migration policy.</td>
    <td>`resolver_key`; canonical normalization; unique active registry key+signature scope; must match parsed language namespace policy.</td>
  </tr>
  <tr>
    <td>Canonical Signature *</td>
    <td>Production read-only trusted detail; proposal/revision form appears only in Create Package linked flow.</td>
    <td>Always required for candidate/trusted revision.</td>
    <td>`signature`: ordered params, types, min/max arity, defaults, return shape. Must pass parser/contract validation.</td>
  </tr>
  <tr>
    <td>Target Runtime Adapter *</td>
    <td>Production detail; selected in linked proposal/revision flow.</td>
    <td>Required for trusted active ESP.</td>
    <td>`runtime_adapter_ref`; adapter artifact must exist, match ABI/capability and be approved for registry.</td>
  </tr>
  <tr>
    <td>Test Vector Set *</td>
    <td>Production evidence section; attach/select action in Create Package linked flow.</td>
    <td>Required before trusted activation; conditional for a non-executable documentation-only proposal.</td>
    <td>`test_vector_set_id` / immutable evidence artifact refs. Must cover normal, warm-up, boundary and NA/error conditions.</td>
  </tr>
  <tr>
    <td>Deprecation Reason *</td>
    <td>Deprecate confirmation modal.</td>
    <td>Required when Admin deprecates an active ESP.</td>
    <td>`reason`; non-empty safe text; audit captured. Does not mutate historical revision.</td>
  </tr>
  <tr>
    <td>Replacement Resolver Revision *</td>
    <td>Deprecate confirmation modal.</td>
    <td>Conditionally required when policy requires a safe successor for active/new conversion paths.</td>
    <td>`replacement_package_revision_id`; must be trusted active, compatible signature/adapter or an approved explicit migration plan.</td>
  </tr>
  <tr>
    <td>Expected head revision *</td>
    <td>Hidden concurrency control for all mutation actions.</td>
    <td>Always required for activate, deprecate, soft delete, restoration-related requests.</td>
    <td>`expected_head_revision_id`; HTTP transport: If-Match/ETag. Mismatch -&gt; 409 `PACKAGE_REVISION_CONFLICT` / `RESOLVER_REGISTRY_CONFLICT`.</td>
  </tr>
</table>

## 6.1 Dependent-field mutation and state preservation rules

- Changing a proposal/revision signature, adapter, semantics spec, code artifact, test vectors or timing policy invalidates prior Pre-Check, validation and trust evidence for that candidate revision. The old immutable evidence remains historical; the new candidate is not silently trusted.

- Changing resolver key changes canonical registry identity. It must create a new Package Root or a controlled migration record; it cannot overwrite a live resolver key in place.

- When an ESP becomes Deprecated, its immutable payload and prior evidence are preserved. The `registry_trust_state` for new resolution becomes non-selectable; historical manifests continue to show their pinned resolver revision.

- When soft delete is permitted, the active registry pointer is removed in the same server transaction. A deleted resolver is not treated as resolved by Pre-Check even if old artifacts still reference it.

- Changing Rationale Family assignment does not change signature, adapter, validation, current revision or registry trust. The global shared-editing exception is limited to this semantic mapping.

# 7. Information Content Catalog - ⓘ Panels and Final UI Text

V18de ESP sectionında existing ⓘ control yoktur. Aşağıdaki set, Production V1 scoped detail viewde eklenmesi önerilen bilgi tetikleyicilerinin doğrudan UIya yerleştirilebilir nihai metnidir. Bunlar V18de mevcutmuş gibi değil, Implementation Alignment olarak uygulanır.

<table>
  <tr>
    <th>Info key / field</th>
    <th>Panel title</th>
    <th>Final UI text</th>
  </tr>
  <tr>
    <td>espResolverKeyInfo / Resolver Key</td>
    <td>Resolver Key</td>
    <td>A resolver key is the canonical technical name used when source code dependencies are matched. Example: `ta.rsi`. A matching display name is not enough. Entropia resolves a dependency only when the key, function signature, runtime adapter and trusted revision are compatible.</td>
  </tr>
  <tr>
    <td>espSignatureInfo / Canonical Signature</td>
    <td>Canonical Function Signature</td>
    <td>This contract defines parameter order, parameter types, optional arguments, minimum and maximum argument counts, return shape and unit semantics. `ta.sma(source, length)` and a function with the same name but a different argument order are not interchangeable.</td>
  </tr>
  <tr>
    <td>espTrustInfo / Trust State</td>
    <td>Trusted Resolver State</td>
    <td>Trusted means this exact revision has passed required validation evidence and has been approved for registry resolution. It does not mean that every package using it is profitable or backtest-ready. A trusted resolver provides technical semantic consistency.</td>
  </tr>
  <tr>
    <td>espAdapterInfo / Runtime Adapter</td>
    <td>Runtime Adapter</td>
    <td>The runtime adapter is the tested implementation that executes this resolver in the selected Entropia runtime. A resolver key can be recognized but still blocked when no compatible approved adapter exists for the target runtime.</td>
  </tr>
  <tr>
    <td>espEvidenceInfo / Validation Evidence</td>
    <td>Validation Evidence</td>
    <td>Validation evidence includes signature checks, runtime checks, test vectors, timing and availability checks, and repaint or future-data review. A package name, an AI explanation or a successful one-off sample is not sufficient evidence for activation.</td>
  </tr>
  <tr>
    <td>espTimingInfo / Timing Semantics</td>
    <td>Timing and Availability</td>
    <td>This resolver declares when its output becomes known. Closed-bar resolvers can be consumed only after the relevant bar has closed. Intrabar behavior requires compatible market-data capability. A resolver must never make future values appear available earlier than they were.</td>
  </tr>
  <tr>
    <td>espDeprecationInfo / Deprecate</td>
    <td>Deprecating a Resolver</td>
    <td>Deprecation stops this resolver from being selected for new conversions by default. It does not rewrite historical package revisions, validation evidence or backtest manifests that already pin an older revision. A replacement resolver may be required before deprecation is accepted.</td>
  </tr>
  <tr>
    <td>espHistoryPinningInfo / Used By</td>
    <td>Historical Pinning</td>
    <td>Packages, strategies, backtest runs and Agent experiments use exact resolver revisions. Updating the current catalog revision does not change historical behavior. Open a manifest or revision history to see the exact resolver revision used.</td>
  </tr>
</table>

## 7.1 Placeholder, helper, warning, toast, modal and error texts

<table>
  <tr>
    <th>UI context</th>
    <th>Final text</th>
  </tr>
  <tr>
    <td>Scoped search placeholder</td>
    <td>Search resolver key, package name, function signature or runtime adapter</td>
  </tr>
  <tr>
    <td>Empty state</td>
    <td>No Embedded System Packages matched the current filters.</td>
  </tr>
  <tr>
    <td>Empty-state helper</td>
    <td>Clear one or more filters, refresh the registry, or open Create Package to propose a missing resolver.</td>
  </tr>
  <tr>
    <td>Missing resolver warning</td>
    <td>No trusted Embedded System Package matched this dependency. Conversion cannot continue until a compatible resolver revision is approved for the requested runtime.</td>
  </tr>
  <tr>
    <td>Signature mismatch warning</td>
    <td>A resolver with the same key exists, but its canonical signature is not compatible with this call. Review the argument contract or create a compatible resolver proposal.</td>
  </tr>
  <tr>
    <td>Adapter mismatch warning</td>
    <td>The resolver is trusted, but no approved runtime adapter is compatible with the selected target runtime.</td>
  </tr>
  <tr>
    <td>Validation running status</td>
    <td>Validation evidence is being collected. This resolver cannot be activated until all required checks have completed successfully.</td>
  </tr>
  <tr>
    <td>Deprecation confirmation title</td>
    <td>Deprecate Embedded System Package?</td>
  </tr>
  <tr>
    <td>Deprecation confirmation body</td>
    <td>This action removes the resolver from default new conversions. Historical packages, runs and manifests keep their pinned revision. Enter a reason and select a replacement when required.</td>
  </tr>
  <tr>
    <td>Soft-delete confirmation title</td>
    <td>Move Embedded System Package to Trash?</td>
  </tr>
  <tr>
    <td>Soft-delete confirmation body</td>
    <td>This action is restricted to Admin and system policy. The resolver will no longer resolve new dependencies. Historical manifests remain readable. Prefer Deprecate for an active trusted resolver.</td>
  </tr>
  <tr>
    <td>Success toast - activation</td>
    <td>Resolver revision activated in the trusted registry.</td>
  </tr>
  <tr>
    <td>Success toast - deprecation</td>
    <td>Resolver deprecated. New conversion requests will use the approved replacement policy.</td>
  </tr>
  <tr>
    <td>Success toast - export</td>
    <td>Resolver revision export is ready. The export contains the immutable revision and evidence manifest.</td>
  </tr>
  <tr>
    <td>Error - permission</td>
    <td>You do not have permission to change this Embedded System Package.</td>
  </tr>
  <tr>
    <td>Error - stale</td>
    <td>This resolver changed while you were reviewing it. Reload the current revision before trying again.</td>
  </tr>
  <tr>
    <td>Error - blocked delete</td>
    <td>This resolver is active in the canonical registry. Deprecate it or complete the required Admin/system policy steps before deletion.</td>
  </tr>
</table>

# 8. Button / Command / State Contract

<table>
  <tr>
    <th>UI action</th>
    <th>V18 behavior</th>
    <th>Production command / preconditions</th>
    <th>Loading, success, error, audit</th>
  </tr>
  <tr>
    <td>Open ESP menu</td>
    <td>Sets local filter `type=embedded`, opens Package Library and scrolls.</td>
    <td>`GET /v1/packages?type=embedded_system&amp;scope=resolver_registry`. Caller may view only permitted projections.</td>
    <td>Loading skeleton; success renders scoped list. Unauthorized records are omitted. `resolver.catalog.viewed` analytics/audit optional.</td>
  </tr>
  <tr>
    <td>Filter / sort</td>
    <td>Local rerender + client array filter.</td>
    <td>`GET /v1/embedded-system-packages` with typed query facets. Query only; no mutation.</td>
    <td>Debounced loading; empty state as catalog response. Invalid facet -&gt; 400 `INVALID_FILTER_VALUE`.</td>
  </tr>
  <tr>
    <td>Expand detail</td>
    <td>Toggles local sibling `.package-details`.</td>
    <td>`GET /v1/packages/{package_root_id}/revisions/{current_revision_id}` or scoped resolver detail.</td>
    <td>Disable duplicate click while loading. Success includes actions/ETag. Not found/deleted -&gt; 404 active resource; Admin uses Trash route.</td>
  </tr>
  <tr>
    <td>Export Package</td>
    <td>Builds browser JSON Blob from local object.</td>
    <td>`POST /v1/packages/{root}/revisions/{revision}/exports` or signed immutable manifest query.</td>
    <td>Async export job for large evidence bundle; returns `job_id`/artifact. Success toast. Audit `package.export.requested/completed`.</td>
  </tr>
  <tr>
    <td>Request Revision</td>
    <td>No V18 row action.</td>
    <td>Routes to linked Create Package revision request with `base_package_revision_id`; actor must be owner of proposal or derive/approval policy.</td>
    <td>Creates new candidate attempt; does not mutate selected revision. Audit `package.revision.requested`.</td>
  </tr>
  <tr>
    <td>Propose missing resolver</td>
    <td>V18 Pre-Check message directs user to Create Package; not a direct ESP action.</td>
    <td>Create Package command with type `embedded_system`, resolver key/signature request context.</td>
    <td>Creates candidate/proposal job. Agent/human can propose; no automatic registry activation. Audit `resolver.proposal.created`.</td>
  </tr>
  <tr>
    <td>Approve and activate</td>
    <td>V18 generic status exists; no real registry activation control.</td>
    <td>Admin-only `approve_and_activate_embedded_resolver` with expected_head_revision_id, passed validation, compatible adapter and policy checks.</td>
    <td>Button disabled while request in flight. Atomic success updates publication + registry pointer; audit `resolver.registry.activated`. 422/403/409 displays structured reason.</td>
  </tr>
  <tr>
    <td>Deprecate</td>
    <td>No V18 dedicated action.</td>
    <td>Admin-only `deprecate_embedded_resolver` with reason*, replacement if required*, expected token*.</td>
    <td>Confirmation modal; action locks repeated submit. Success updates registry selection policy; audit `resolver.deprecated`.</td>
  </tr>
  <tr>
    <td>Move to Trash / ×</td>
    <td>V18 directly removes local array item and adds Trash record; no confirm.</td>
    <td>Admin/system policy `soft_delete_package_root`; active trusted ESP normally blocked or redirected to Deprecate-first path.</td>
    <td>Success hides from active query; creates Trash entry/audit. Error `DELETE_POLICY_BLOCKED` preserves view.</td>
  </tr>
  <tr>
    <td>Restore / permanently delete</td>
    <td>Not on this page; V18 Trash handles it separately.</td>
    <td>Admin-only Trash commands.</td>
    <td>Out of scope UI; this page may show historical lifecycle badge only. Audit exists for restore/purge.</td>
  </tr>
</table>

# 9. User, Agent and Error-Recovery Flows

## 9.1 Successful Pre-Check resolution

1. A User, Supervisor, Admin or Agent submits a source code request through the separate Create Package / Pre-Check flow.

2. Parser identifies `ta.rsi(source, length)`. The resolver service queries the ESP registry by key and target runtime.

3. The service finds a trusted active ESP revision whose canonical signature, adapter, lifecycle and evidence state are compatible.

4. Pre-Check records the exact `package_revision_id`, signature compatibility proof and resolver evidence reference in its report.

5. Candidate/draft package dependency manifest pins this exact ESP revision. A later ESP update does not alter the candidate or any later Strategy/Run manifest.

## 9.2 Missing resolver / proposal recovery

1. Pre-Check finds `ta.custom_function(...)` or a known key without a compatible trusted revision.

2. The conversion branch becomes PRECHECK_BLOCKED and shows the missing key, parsed signature and target runtime diagnostic. No runtime implementation is invented by the CP Agent.

3. User, Supervisor or Agent can create an ESP proposal through the linked Create Package workflow. The new proposal is an owned draft/candidate, not an active resolver.

4. Validation collects test vectors, adapter compatibility and integrity evidence. Admin reviews and, only after requirements pass, activates a trusted registry revision.

5. The blocked branch is re-run from the source hash. It creates a new Pre-Check result; it does not turn the old blocked report into a hidden pass.

## 9.3 Signature mismatch recovery

1. Pre-Check finds `ta.sma(length, source)` but the active resolver supports only `ta.sma(source, length)`.

2. Resolver lookup returns `RESOLVER_SIGNATURE_MISMATCH` with expected and received contract summaries. Same-name matching is not accepted.

3. User corrects the source call, selects a correct source language/runtime, or opens a revision/proposal request for an explicitly supported signature.

4. The system re-runs dependency resolution. Existing trusted `ta.sma(source, length)` revision stays unchanged.

## 9.4 Stale concurrency and deprecation recovery

1. Admin A opens trusted ESP revision 12. Admin B activates revision 13 or deprecates revision 12 first.

2. Admin A submits an action with `expected_head_revision_id=12`.

3. Backend returns 409 `RESOLVER_REGISTRY_CONFLICT` and does not override current pointer or registry policy.

4. UI shows: `This resolver changed while you were reviewing it. Reload the current revision before trying again.` The actor can Reload, Compare revision 12/13, or start a new revision request.

## 9.5 Soft delete / restore lifecycle flow

1. An Admin attempts to remove an ESP root. Backend runs dependency and registry policy preflight.

2. If the ESP is trusted active or used as an active resolver, server returns `DELETE_POLICY_BLOCKED` and directs to Deprecate / replacement policy. The root is not deleted.

3. If policy allows soft delete, backend creates a Trash Entry snapshot, marks root `soft_deleted`, removes it from active registry resolution and writes append-only audit events in one transaction.

4. Only Admin may later restore from Trash. Restore returns the same root/current immutable revision pointer; it does not create a new revision or automatically reinstate a resolver trust pointer without policy re-evaluation.

# 10. Backend / Domain Model, Commands, API Parity and Agent Tools

## 10.1 Example query and command surface

<table>
  <tr>
    <th>GET  /v1/embedded-system-packages?trust=trusted&amp;lifecycle=active&amp;sort=resolver_key<br/>GET  /v1/embedded-system-packages/{package_root_id}<br/>GET  /v1/embedded-system-packages/{package_root_id}/revisions/{revision_id}/evidence<br/>POST /v1/embedded-system-packages/{package_root_id}/revisions/{revision_id}/exports<br/>POST /v1/embedded-system-packages/proposals              # redirects to Create Package pipeline<br/>POST /v1/embedded-system-packages/{package_root_id}/activate<br/>POST /v1/embedded-system-packages/{package_root_id}/deprecate<br/>POST /v1/packages/{package_root_id}/soft-delete          # policy guarded<br/>POST /v1/trash/{trash_entry_id}/restore                  # Admin only</th>
  </tr>
</table>

Endpoint names are examples; the behavior is binding. Every mutable request carries a correlation/idempotency key and expected head revision token. Server responses return the canonical root/revision/job/action state or a structured error. A browser-specific path must not contain behavior unavailable to the Agent Tool Gateway.

## 10.2 Command payload example - activation

<table>
  <tr>
    <th>{<br/>  &quot;package_root_id&quot;: &quot;pkg_...&quot;,<br/>  &quot;package_revision_id&quot;: &quot;pkgrev_...&quot;,<br/>  &quot;expected_head_revision_id&quot;: &quot;pkgrev_...&quot;,<br/>  &quot;expected_registry_version&quot;: &quot;reg_...&quot;,<br/>  &quot;activation_scope&quot;: &quot;canonical_ta_resolver&quot;,<br/>  &quot;idempotency_key&quot;: &quot;...&quot;,<br/>  &quot;correlation_id&quot;: &quot;...&quot;<br/>}</th>
  </tr>
</table>

Server preconditions: caller is Admin; revision belongs to `embedded_system` root; validation evidence is passed/current; resolver key/signature/adapter and trust policy are complete; no conflicting active registry entry exists; target root.lifecycle_state is not soft_deleted; expected_head_revision_id and expected_registry_version match. The transaction writes publication/registry pointer state, audit and outbox event atomically.

## 10.3 Agent Tool Gateway parity

<table>
  <tr>
    <th>Agent capability</th>
    <th>Equivalent UI meaning</th>
    <th>Policy and provenance</th>
  </tr>
  <tr>
    <td>`resolver.search`</td>
    <td>Filter/sort ESP catalog.</td>
    <td>Returns only policy-allowed scoped projections and typed facets. UI does not need to be open.</td>
  </tr>
  <tr>
    <td>`resolver.get_contract`</td>
    <td>Open row detail and ⓘ fields.</td>
    <td>Returns exact revision contract/evidence and action projection; Agent cannot infer active trust from display name.</td>
  </tr>
  <tr>
    <td>`resolver.resolve_dependency`</td>
    <td>Pre-Check resolver lookup.</td>
    <td>Takes parsed call + target runtime; returns exact revision or structured diagnostic. Output is stored in candidate/checkpoint artifact.</td>
  </tr>
  <tr>
    <td>`resolver.propose`</td>
    <td>Open linked Create Package request.</td>
    <td>Creates owned proposal/candidate via same normalized Create Package request. Does not publish or activate.</td>
  </tr>
  <tr>
    <td>`resolver.request_revision`</td>
    <td>Request Revision action.</td>
    <td>New candidate/revision chain with parent revision ref. Only own proposal normal mutation; foreign source requires derive/proposal policy.</td>
  </tr>
  <tr>
    <td>`resolver.read_evidence`</td>
    <td>View test vectors / validation evidence.</td>
    <td>Read access follows policy; evidence ref is included in Agent provenance.</td>
  </tr>
  <tr>
    <td>`resolver.activate`</td>
    <td>Admin activation control.</td>
    <td>Unavailable to Agent. Server rejects even if a client sends fabricated role/approval payload.</td>
  </tr>
  <tr>
    <td>`resolver.deprecate`</td>
    <td>Admin deprecate control.</td>
    <td>Unavailable to Agent. Agent may create an impact artifact or replacement proposal.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Agentic boundary: Missing or incompatible resolver yalnız o conversion branchini PRECHECK_BLOCKED yapar. Alpha Agentın ana araştırma döngüsü browser, Lab Assistant mesajı veya Admin ekranı beklemez; Agent resolver proposal/revision-required artifacti ve follow-up task üretip başka research worke devam eder.</th>
  </tr>
</table>

# 11. Validation, Error, Recovery, Lifecycle, Audit ve Trash

## 11.1 Validation contract

<table>
  <tr>
    <th>Validation layer</th>
    <th>Required behavior</th>
    <th>Failure / recovery</th>
  </tr>
  <tr>
    <td>Schema and contract validation</td>
    <td>Package type is embedded_system; resolver key, signature, adapter, semantic/timing contract and required evidence refs validate against typed schema.</td>
    <td>422 `RESOLVER_CONTRACT_INVALID`; preserve draft, identify field paths, no registry mutation.</td>
  </tr>
  <tr>
    <td>Parser/signature compatibility</td>
    <td>Parsed source call must match key, ordered argument types, arity and return shape.</td>
    <td>`RESOLVER_SIGNATURE_MISMATCH`; source/contract repair or proposal revision required.</td>
  </tr>
  <tr>
    <td>Runtime adapter validation</td>
    <td>Designated adapter exists, is compatible with requested runtime and produces deterministic contract output.</td>
    <td>`RESOLVER_ADAPTER_INCOMPATIBLE`; choose compatible adapter/revision or build one through controlled pipeline.</td>
  </tr>
  <tr>
    <td>Test vectors</td>
    <td>Normal, warm-up, NA/null, boundary, invalid input and numerical tolerance cases pass.</td>
    <td>`RESOLVER_TEST_VECTOR_FAILED`; new candidate/revision; old trusted revision remains active.</td>
  </tr>
  <tr>
    <td>Timing and integrity</td>
    <td>Closed-bar/intrabar availability, lookahead/repaint review, prefix-invariance and multi-timeframe/session semantics verified.</td>
    <td>`RESOLVER_TIMING_RISK_BLOCKED`; cannot activate; evidence artifact explains risk.</td>
  </tr>
  <tr>
    <td>Dependency graph</td>
    <td>ESP dependencies and consumer references resolve exact active revisions without cycles.</td>
    <td>`PACKAGE_DEPENDENCY_CYCLE` / `DEPENDENCY_UNRESOLVED`; repair graph and revalidate.</td>
  </tr>
  <tr>
    <td>Authorization / lifecycle</td>
    <td>Caller, root/revision state, system ownership, trust and expected token evaluated on server.</td>
    <td>403/409/423 structured error; UI/Agent refreshes authoritative state.</td>
  </tr>
</table>

## 11.2 Lifecycle and registry state

<table>
  <tr>
    <th>Layer</th>
    <th>State / transition</th>
    <th>Meaning</th>
  </tr>
  <tr>
    <td>Package revision workflow</td>
    <td>revision.validation_state: pending | passed | warning | failed | stale; revision.approval_state: draft | approval_requested | approved | rejected; visibility_scope: private | explicitly_shared | published | system. Root lifecycle and ESP registry_trust_state remain separate.</td>
    <td>Immutable revision chain. Candidate can be valid enough for review but is not automatically active resolver.</td>
  </tr>
  <tr>
    <td>Root lifecycle</td>
    <td>root.lifecycle_state: active | deprecated | soft_deleted; Trash purge state is separate: pending | running | failed | completed.</td>
    <td>Root visibility and new-use behavior. Deprecation normally precedes deletion for trusted registry ESP.</td>
  </tr>
  <tr>
    <td>Registry trust projection</td>
    <td>Candidate / Trusted Active / Deprecated / Unavailable.</td>
    <td>Separate resolver registry selection state; Pre-Check uses only Trusted Active candidates with compatible signature/adapter.</td>
  </tr>
  <tr>
    <td>Historical provenance</td>
    <td>Pinned old revision remains resolvable for historical artifact/manifest reading.</td>
    <td>Never substitute current/latest resolver into old package/Strategy/Run/Result manifest.</td>
  </tr>
</table>

## 11.3 Audit event contract

<table>
  <tr>
    <th>Event type</th>
    <th>Must record</th>
  </tr>
  <tr>
    <td>`resolver.proposal.created`</td>
    <td>actor principal/type; source request hash; resolver key/signature; candidate/job refs; correlation id; originating Agent task where applicable.</td>
  </tr>
  <tr>
    <td>`resolver.validation.completed`</td>
    <td>revision ref; evidence refs; pass/fail; timing/repaint findings; adapter/version; reviewer and server timestamp.</td>
  </tr>
  <tr>
    <td>`resolver.registry.activated`</td>
    <td>Admin actor; old/new registry pointer; expected/current revision token; evidence summary; approval rationale.</td>
  </tr>
  <tr>
    <td>`resolver.deprecated`</td>
    <td>Admin actor; reason; replacement revision if any; impact summary; prior/new registry state.</td>
  </tr>
  <tr>
    <td>`package.soft_deleted` / `trash.restore.completed` / `trash.purge.*`</td>
    <td>root/revision/trash refs; actor; policy outcome; before/after safe summary; command/correlation id; server time.</td>
  </tr>
  <tr>
    <td>`resolver.resolve_dependency` (artifact/event)</td>
    <td>$parsed call, runtime, selected exact revision or reason code, package/candidate/run/Agent context. Retention may be sampled by policy but candidate manifest evidence is durable.</td>
  </tr>
</table>

# 12. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Topic</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Entry point</td>
    <td>Generic Package Library page opens and scrolls to Embedded section.</td>
    <td>Scoped resolver registry query, dedicated ESP title/route.</td>
    <td>Keep menu path; route may be `/embedded-system-packages` or Package Library type scope. Do not duplicate domain model.</td>
  </tr>
  <tr>
    <td>Canonical types</td>
    <td>V18 filters include Trading Signal and Trade Log packages.</td>
    <td>Package types only strategy, indicator, condition, embedded_system.</td>
    <td>Remove signal/log package types from Production Library/ESP route; they remain Mainboard external working objects.</td>
  </tr>
  <tr>
    <td>ESP owner</td>
    <td>V18 defaults `owner=Admin`.</td>
    <td>Trusted published ESP is System-owned; Admin approves/operates registry.</td>
    <td>Preserve proposal creator in provenance; System ownership prevents accidental personal edit/delete semantics.</td>
  </tr>
  <tr>
    <td>System facets</td>
    <td>V18 Market/Timeframe dropdowns omit System though ESP metadata uses it.</td>
    <td>System/Not applicable facet is explicit; performance fields N/A.</td>
    <td>Add System values or lock those facets in ESP scoped route.</td>
  </tr>
  <tr>
    <td>Rationale seed</td>
    <td>V18 ESP metadata references a Family absent from seed cards.</td>
    <td>`Embedded System / TA Resolver` is seeded and globally editable only as assignment metadata.</td>
    <td>Seed Family at migration/bootstrap. Do not grant shared edit rights to resolver payload.</td>
  </tr>
  <tr>
    <td>Status</td>
    <td>V18 `Approved` card plus generic Backtest Ready/OOS.</td>
    <td>Lifecycle, validation, publication and registry trust are separate facts.</td>
    <td>Replace one Status chip with typed facet badges; hide/mark N/A performance fields.</td>
  </tr>
  <tr>
    <td>Resolver matching</td>
    <td>V18 precheck uses local map by function name.</td>
    <td>Exact resolver key + signature + adapter + trusted revision lookup.</td>
    <td>Name-only map is prototype behavior; parser/service must be canonical source.</td>
  </tr>
  <tr>
    <td>Delete</td>
    <td>V18 × immediately splices local array and creates a client Trash entry.</td>
    <td>Deprecate-first; Admin/system policy guards soft delete; Trash Admin-only.</td>
    <td>Add confirmation/preflight/structured policy errors; never delete an active trusted resolver by local UI state.</td>
  </tr>
  <tr>
    <td>Export</td>
    <td>V18 browser Blob with current local record.</td>
    <td>Immutable revision + dependency/evidence manifest export, possibly async job.</td>
    <td>No local array source of truth; export exact revision id and content hash.</td>
  </tr>
</table>

# 13. Kavramsal Terimler

<table>
  <tr>
    <th>Term</th>
    <th>Canonical meaning</th>
  </tr>
  <tr>
    <td>Embedded System Package (ESP)</td>
    <td>Technical-analysis/code-conversion layerındaki trusted resolver/adaptor package. Generic Indicator Package veya live signal source değildir.</td>
  </tr>
  <tr>
    <td>Resolver Key</td>
    <td>Source language dependency lookupta kullanılan canonical technical key, örn. `ta.rsi`.</td>
  </tr>
  <tr>
    <td>Canonical Signature</td>
    <td>Resolver functionunun arity, argument order/types, optional defaults, return shape ve semanticsini tanımlayan immutable contract.</td>
  </tr>
  <tr>
    <td>Runtime Adapter</td>
    <td>Canonical semantic contractı hedef Entropia runtimeında çalıştıran test edilmiş implementation/reference.</td>
  </tr>
  <tr>
    <td>Trusted Active</td>
    <td>Registryde yeni Pre-Check ve conversion work için seçilebilir; required validation evidence ve Admin activationdan geçmiş exact revision projectionı.</td>
  </tr>
  <tr>
    <td>Deprecate</td>
    <td>New work için default selectionı kapatmak; historical pinned artifactsi değiştirmemek. Soft delete ile aynı değildir.</td>
  </tr>
  <tr>
    <td>Exact Revision Pinning</td>
    <td>Consumer package, Strategy, Backtest Run veya Agent experimentin current/latest yerine belirli immutable resolver revisionına bağlanması.</td>
  </tr>
  <tr>
    <td>Test Vector</td>
    <td>Belirli inputlar için expected output/behavior içeren repeatable technical evidence seti.</td>
  </tr>
</table>

# 14. Implementation Rules for Coding AI

- Package type enumunu yalnız `strategy`, `indicator`, `condition`, `embedded_system` olarak uygula. Trading Signal ve Trade Logu ESP veya Package Library type olarak modelleme.

- ESP resolveri generic Indicator Package gibi semantikleme. ESPnin primary purposeı source-code TA dependency resolution ve trusted runtime adapter reuseudur.

- Resolver identityyi display name, `ESP_TA_*` labelı veya array indexiyle belirleme. Stable root id + resolver key + exact immutable revision kullanılmalıdır.

- A resolver matchi yalnız function name ile kabul etme. Key, full canonical signature, arity, ordered argument types, return shape, timing semantics, adapter compatibility ve trust state birlikte doğrulanmalıdır.

- Trusted active ESP revisionına SQL UPDATE ile in-place code/contract değişikliği yapma. Code, adapter, signature, semantics, test vector veya timing policy değişikliği yeni immutable revision üretir.

- Pre-Check/CP Agent generated outputuna resolver implementation kopyalama. Candidate/package dependency manifestinde exact ESP revision refi sakla.

- New conversiona deprecated, soft-deleted, untrusted, failed-validation veya adapter-incompatible resolver seçtirme. Historical manifest reading exceptionını new resolutiona genişletme.

- ESPde Backtest Ready, OOS, Net Profit, ROMAD, Win Rate veya Trade Count uydurma. Teknik resolver contextinde bu fields `Not applicable` olmalıdır.

- V18 Status labelını persistence enumuna dönüştürme. Lifecycle, validation, publication/approval, registry trust, deprecation ve deletion states ayrı modelle.

- V18de missing olan `Embedded System / TA Resolver` Rationale Familyyi production seed data olarak oluştur. Shared-editing exception yalnız assignment mappingde uygulanır.

- Trusted system resolver publish/activationını Admin-only server-side transaction yap. Client role payloadı, button disabled veya menu hidden authorization yerine geçemez.

- Normal trusted ESP removal actionını Deprecate olarak tasarla. Soft delete/purge attemptinde active registry/dependency policy preflight uygula; active resolverde `DELETE_POLICY_BLOCKED` döndür.

- Soft delete, Trash Entry ve audit eventini aynı transactionda oluştur. Restore/purge yalnız Admin; restore new revision yaratmaz ve registry trusti otomatik bypass etmez.

- Every mutable registry actionda idempotency key, correlation id, `expected_head_revision_id` ve registry version token kullan. Mismatchte 409 conflict; silent last-write-wins yok.

- Catalog, filter, sort, detail, export and action projection queriesini role-aware backendde yap. Unauthorized ESP records clienta gönderilip CSS/JS ile gizlenmez.

- Agent Tool Gatewaye UI actionlarla parity sağlayan typed resolver search/get/resolve/propose/evidence tools ver. Agent UI browserına, Lab Assistant messageine veya human sessiona bağımlı olamaz.

- Exportu immutable revision, contract hash, adapter ref, test evidence manifest ve dependencies üzerinden üret. Local browser object exportu canonical artifact değildir.

- All resolver validation jobs queue/worker modelinde çalışmalıdır. Browser refresh/tab closure jobu veya Agent branchi durdurmaz.

# 15. Acceptance Tests

<table>
  <tr>
    <th>Category</th>
    <th>Acceptance scenario</th>
    <th>Expected result</th>
  </tr>
  <tr>
    <td>Menu scope</td>
    <td>User chooses Edit &gt; Package Library &gt; Embedded System Packages.</td>
    <td>Production opens ESP scoped registry list/type=embedded_system and not a generic mixed catalog scroll workaround. Menu remains familiar.</td>
  </tr>
  <tr>
    <td>Canonical type enforcement</td>
    <td>Client calls package endpoint with `type=trading_signal` or `trade_log`.</td>
    <td>Server rejects invalid package type; no ESP/PackageRoot created. External working-object flow remains separate.</td>
  </tr>
  <tr>
    <td>V18 sample catalog</td>
    <td>Scoped list includes approved/test fixtures for ESP_TA_SMA, EMA, RMA, ATR, RSI, WMA and VWAP.</td>
    <td>Rows show resolver key + technical status; performance metrics are N/A, not fabricated zeroes.</td>
  </tr>
  <tr>
    <td>System facets</td>
    <td>User filters Market=System and Timeframe=System.</td>
    <td>Trusted ESP rows are returned. V18 missing facet inconsistency is absent.</td>
  </tr>
  <tr>
    <td>Rationale seed</td>
    <td>User opens ESP Rationale filter after bootstrap.</td>
    <td>Embedded System / TA Resolver appears. Editing assignment follows shared exception, while resolver payload remains protected.</td>
  </tr>
  <tr>
    <td>Resolver exact match</td>
    <td>Pre-Check parses `ta.sma(source, length)` and trusted compatible revision exists.</td>
    <td>Returns exact revision id + signature/adapter evidence ref; candidate manifest pins exact revision.</td>
  </tr>
  <tr>
    <td>Name-only rejection</td>
    <td>A package displays `ta.sma` but its signature arguments are reversed.</td>
    <td>Pre-Check returns `RESOLVER_SIGNATURE_MISMATCH`; it does not accept same-name resolver.</td>
  </tr>
  <tr>
    <td>Adapter rejection</td>
    <td>Trusted resolver lacks compatible PHP/runtime adapter.</td>
    <td>Pre-Check returns `RESOLVER_ADAPTER_INCOMPATIBLE`; no conversion result is treated ready.</td>
  </tr>
  <tr>
    <td>Evidence gate</td>
    <td>Candidate ESP has generated code but missing test vectors/passed timing review.</td>
    <td>Admin activate command is rejected; registry pointer unchanged.</td>
  </tr>
  <tr>
    <td>Timing integrity</td>
    <td>Candidate outputs a high-timeframe value before its source bar closes.</td>
    <td>Validation marks timing/future-leak risk BLOCKED and prevents trusted activation.</td>
  </tr>
  <tr>
    <td>Immutable revision</td>
    <td>Admin corrects RSI seed behavior.</td>
    <td>New revision is created and activated; old package/Backtest manifests remain pinned to old revision.</td>
  </tr>
  <tr>
    <td>Stale activation</td>
    <td>Admin A and Admin B activate based on same expected_head_revision_id; B completes first.</td>
    <td>A receives 409 conflict; no silent overwrite or duplicate registry pointer occurs.</td>
  </tr>
  <tr>
    <td>Permission</td>
    <td>Supervisor/Agent attempts `activate_embedded_resolver`.</td>
    <td>Server denies. They may submit a proposal/revision request within ownership policy; active registry unchanged.</td>
  </tr>
  <tr>
    <td>Agent parity</td>
    <td>Browser closed; Agent resolves `ta.atr(length)` through Tool Gateway.</td>
    <td>Agent obtains exact trusted revision or structured diagnostic; provenance is written; no browser/UI automation used.</td>
  </tr>
  <tr>
    <td>Missing resolver recovery</td>
    <td>Pre-Check finds an unsupported Pine TA call.</td>
    <td>Branch becomes PRECHECK_BLOCKED; UI/Agent sees precise missing dependency; proposal can be created; no inferred implementation is silently used.</td>
  </tr>
  <tr>
    <td>Deprecation</td>
    <td>Admin deprecates trusted ESP with required reason/replacement.</td>
    <td>New conversion resolves replacement policy; historical manifest still resolves original pinned revision.</td>
  </tr>
  <tr>
    <td>Delete policy</td>
    <td>Admin tries to soft-delete active trusted resolver.</td>
    <td>Server blocks/redirects to deprecation unless explicit policy preflight permits delete; no local immediate removal.</td>
  </tr>
  <tr>
    <td>Trash policy</td>
    <td>User/Agent tries restore/purge ESP Trash record.</td>
    <td>Server returns Admin-only access denial. Admin restore preserves root/current revision but rechecks active registry policy.</td>
  </tr>
  <tr>
    <td>Export integrity</td>
    <td>User exports exact ESP revision.</td>
    <td>Artifact contains root/revision identity, content hash, signature, adapter ref, evidence and dependency manifest.</td>
  </tr>
  <tr>
    <td>Role-aware list</td>
    <td>User owns no ESP proposal and may view System trusted ESP only.</td>
    <td>List omits other private proposal drafts; direct ID query also enforces can_view.</td>
  </tr>
</table>

# 16. Final Consistency Check

<table>
  <tr>
    <th>Check</th>
    <th>Result</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 precedence and canonical type boundary</td>
    <td>Yes. Module 7/8 resolver, immutable revision, lifecycle and CR-01 boundaries override V18 local prototype behavior. Only strategy, indicator, condition and embedded_system are Package types; Trading Signal / Trade Log are excluded from ESP scope.</td>
  </tr>
  <tr>
    <td>ESP semantic boundary and V18/Production separation</td>
    <td>Preserved. ESP is a trusted resolver/adaptor layer, not an entry/exit Indicator Package, external signal or performance-bearing strategy component. Menu/filter/local array/status/delete/export artifacts are explicitly separated from role-aware registry query, typed contract, exact signature matching, evidence, lifecycle and policy behavior.</td>
  </tr>
  <tr>
    <td>Agent, revision, Rationale, Trash and scope integrity</td>
    <td>Yes. Tool Gateway search/resolve/propose/evidence APIs avoid browser dependency; all consumers pin immutable exact resolver revisions; trusted published ESP is System-owned with provenance preserved. Shared edit exception is limited to assignment mapping. Active resolver uses deprecate-first, Trash actions are Admin-only, and separate page UIs are not duplicated here.</td>
  </tr>
</table>
