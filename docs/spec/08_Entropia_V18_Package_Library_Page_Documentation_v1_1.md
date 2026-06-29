---
title: "Entropia V18 — Package Library Page Documentation v1.1"
page_number: 8
document_type: "Page implementation specification"
source_document: "Entropia_V18_Package_Library_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Package Library Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | PAGE DOCUMENTATION 8/22 | PACKAGE LIBRARY
> **Original DOCX footer:** Canonical page documentation | Production V1 alignment |

ENTROPIA V18

PACKAGE LIBRARY

Sayfa Dokümantasyonu 8/22 | Sürümlü reusable logic catalog, compatibility, use/derive, export ve lifecycle sözleşmesi

<table>
  <tr>
    <th>Kapsam sınırı: Bu belge yalnız Package Library katalog yüzeyini ve onun Production V1 catalog/query/action davranışını kapsar. Create Package ve Pre-Check üretim hattı, Embedded System Packages içeriğinin resolver yönetimi, Rationale Family kartlarının düzenleme ekranı, Strategy Details içindeki package seçim alanları, Mainboard çalışma nesneleri, Ready Check ve Trash ekranları ayrı sayfalardır. Bu alanlar yalnız bu sayfadaki dependency, link-out, permission veya lifecycle etkisi kadar anılır.</th>
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
    <td>Entropia V18 | Page Documentation 8/22 | Package Library | v1.1</td>
  </tr>
  <tr>
    <td>Belge amacı</td>
    <td>Package Librarynin visible catalog, filters, rows, expandable detail, export/delete actions ve Production V1de root/revision/contract/dependency/lifecycle/authorization katmanını kodcu AI için uygulanabilir sözleşmeye dönüştürmek.</td>
  </tr>
  <tr>
    <td>Ana Master dayanağı</td>
    <td>Modül 7: Package Sistemi ve Package Library; Canonical Integration CR-01 / CR-02. Çapraz: Modül 0 (UI/Agent sınırı), Modül 1-3 (roles, ownership, Trash), Modül 6 (Rationale assignment), Modül 8 (creation/approval), Modül 10/12/13 (use/run/result pinning), Modül 19 (API).</td>
  </tr>
  <tr>
    <td>V18 HTML referansı</td>
    <td>Edit &gt; Package Library menüsü; `packageGroups`; `packagePoolFilterState`; `renderPackagePoolPage`; `renderPackageSection`; `getPackageMeta`; `togglePackageDetails`; `exportPackage`; `deletePackage`; V18 page components and labels.</td>
  </tr>
  <tr>
    <td>Kritik canonical sınır</td>
    <td>Package types yalnız Strategy, Indicator, Condition ve Embedded System Package. Trading Signal ve Trade Log Package Library type değildir; Add Outsource Signal altında oluşturulan external Mainboard Working Itemlardır. [V18 legacy prototype label; Production domain/API type değildir.]</td>
  </tr>
  <tr>
    <td>Açık Implementation Decisions</td>
    <td>Server-side search, independent status facets, detail tabs/sections, action-specific button set, pagination/cursor, stale detail recovery ve filter persistence bu belgede Masterın genel ilkelerine dayanarak netleştirilmiştir.</td>
  </tr>
</table>

## 0.1 Source Traceability Map

<table>
  <tr>
    <th>Sayfa alanı</th>
    <th>Master ref</th>
    <th>V18 HTML gözlemi</th>
    <th>Çapraz bağımlılık</th>
    <th>Karar / not</th>
  </tr>
  <tr>
    <td>Catalog types &amp; projection</td>
    <td>M7 §1-4, §8; CR-01</td>
    <td>6 category sections including Trading Signal / Trade Log</td>
    <td>M9 Add Outsource Signal</td>
    <td>Production canonical catalog 4 package type ile sınırlıdır; external items Package Libraryde listelenmez.</td>
  </tr>
  <tr>
    <td>Filters / sorting</td>
    <td>M7 §8.3</td>
    <td>Type, Market, Timeframe, Rationale Family, Status, Sort By</td>
    <td>M6 Rationale; M13 metrics</td>
    <td>Backend query/filter; composite V18 Status split into independent facets. Performance sort only Strategy Package projection when applicable.</td>
  </tr>
  <tr>
    <td>Detail / actions</td>
    <td>M7 §8.1, §8.4-8.5, §10, §12</td>
    <td>Expandable row, summary, metadata cells, Export Package, × delete</td>
    <td>M1-3, M8, M10</td>
    <td>Detail is root + current revision projection; production actions are policy/lifecycle-aware commands, not client array mutations.</td>
  </tr>
  <tr>
    <td>Use / derive / pinning</td>
    <td>M7 §6-7, §13; M10/M12</td>
    <td>Not directly visible as a standalone V18 button</td>
    <td>M10 Strategy Details, M12 Ready Check</td>
    <td>Use pins exact revision; foreign owner payload changes require Derive, not edit. No implicit latest lookup.</td>
  </tr>
  <tr>
    <td>Lifecycle / Trash</td>
    <td>M7 §9; M3; M1</td>
    <td>× removes local entry and adds demo Trash record</td>
    <td>M3 Trash, M12 historic runs</td>
    <td>Soft delete removes root from active catalog/new use; history and manifests retain exact revisions; restore/permanent delete Admin only.</td>
  </tr>
</table>

## 0.2 Rule Provenance Register

<table>
  <tr>
    <th>Etiket</th>
    <th>Bu belgedeki kullanım</th>
  </tr>
  <tr>
    <td>Canonical Rule</td>
    <td>Masterda açıkça kilitli Production V1 davranışıdır. Örnek: Package type enumu yalnız strategy, indicator, condition, embedded_system değerlerinden oluşur; published/shared geçişi yalnız Admin `approve_and_publish` transactionı ile olur.</td>
  </tr>
  <tr>
    <td>Derived Rule</td>
    <td>Canonical kuralın zorunlu sonucudur. Örnek: Katalog satırı `package_root_id + current_revision_id` taşımalıdır; yalnız görünen ada dayalı Use, Export veya Delete yapılamaz.</td>
  </tr>
  <tr>
    <td>V18 Interface Observation</td>
    <td>HTMLde görünen prototype davranışıdır. Örnek: Status tek dropdown içinde `Backtest Ready`, `Approved`, `Imported`, `Mapped` değerlerini karıştırır; filtreleme local array üzerinde yapılır; Export browser Blob indirir.</td>
  </tr>
  <tr>
    <td>Implementation Decision - Non-Canonical Gap Resolution</td>
    <td>Master detay UI yerleşimini sabitlemediğinde seçilmiş teknik yön. Örnek: production listede server-side search + cursor pagination, independent lifecycle/approval/validation facets ve current revision changed banner kullanılır.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Canonical Kavramlar

Package Library, Entropia içindeki tekrar kullanılabilir mantık bileşenlerinin katalog yüzüdür. İnsan veya Agent burada mevcut packageleri bulur, türünü ve teknik sözleşmesini görür, uyumluluğunu değerlendirir, belirli bir revisionı kullanmak için seçer, kendi varyasyonunu türetir, immutable manifest export eder veya yetkisi varsa lifecycle işlemi başlatır. Sayfanın görevi code editor olmak, açık pozisyon yönetmek veya Backtest sonucu üretmek değildir.

Katalog yalnız ekranda görünen kartlardan oluşmaz. Production V1de her satır, Package Rootun erişim/lifecycle bağlamı ile onun current immutable Package Revisionının metadata, dependency, validation ve output-contract projectionını temsil eder. Tarihsel Strategy, Backtest Run veya Agent experiment, catalogdaki en yeni görünümü değil kendi manifestinde pinlenmiş exact revisionı kullanır.

## 1.1 İlk geçen canonical kavramlar

<table>
  <tr>
    <th>Kavram</th>
    <th>Canonical kısa tanım</th>
    <th>Bu sayfadaki uygulama sonucu</th>
  </tr>
  <tr>
    <td>Package Root</td>
    <td>Bir reusable logic bileşeninin kalıcı kimliği ve soy ağacı.</td>
    <td>Katalog satırının stable identitysidir; name veya revision değişse de root id korunur.</td>
  </tr>
  <tr>
    <td>Package Revision</td>
    <td>Bir rootun belirli andaki immutable içerik sürümü.</td>
    <td>Detail açıldığında current revision özeti görünür; history ayrı erişimle tüm allowed revisions gösterir.</td>
  </tr>
  <tr>
    <td>Catalog Projection</td>
    <td>Root + current revisionın hızlı okunabilir list/detail özeti.</td>
    <td>Katalog asıl tarihsel veri kaynağı değildir; listede lazy/current projection gösterilir.</td>
  </tr>
  <tr>
    <td>Package Type</td>
    <td>Strategy, Indicator, Condition veya Embedded System teknik rolü.</td>
    <td>Root oluşurken belirlenir; sonradan type conversion yapılmaz.</td>
  </tr>
  <tr>
    <td>Output Contract</td>
    <td>Packagein hangi inputtan ne tür output ürettiği ve outputun ne zaman kullanılabilir olduğu sözleşme.</td>
    <td>Use actiondan önce compatibility kontrolünün temelidir; text summary yeterli değildir.</td>
  </tr>
  <tr>
    <td>Dependency Snapshot</td>
    <td>Bir revisionın çalışmak için gerekli exact Package/ESP/implementation/data capability referansları.</td>
    <td>`latest` referansı yasaktır; use/run/agent manifestlerine exact revisionlar pinlenir.</td>
  </tr>
  <tr>
    <td>Use</td>
    <td>Başka ownerın packageini değiştirmeden exact revisionını referans alma.</td>
    <td>Source ownership taşınmaz; callerın yeni outputu kendi ownerlığında oluşur.</td>
  </tr>
  <tr>
    <td>Derive</td>
    <td>Mevcut revisiondan yeni owner altında yeni package root üretme.</td>
    <td>Foreign package değişikliği için canonical yoldur; doğrudan edit yerine görünür.</td>
  </tr>
  <tr>
    <td>Deprecated</td>
    <td>Yeni kullanım için varsayılan olmayan fakat controlled historical reproductionda korunmuş root lifecycle statei.</td>
    <td>Yeni strategy draft dropdownlarında default seçenek değildir; eski manifestleri bozmaz.</td>
  </tr>
  <tr>
    <td>Soft Delete</td>
    <td>Rootu aktif katalogdan kaldıran, historyyi ve audit bilgisini koruyan silme.</td>
    <td>Normal delete geri alınabilir; Trash, restore ve permanent delete yalnız Admin yetkisindedir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Canonical type boundary: Trading Signal ve Trade Log reusable Package type değildir. Bunlar Add Outsource Signal altında root/revision taşıyan external working objectlerdir; Package Librarynin `package_type` enumuna eklenmez, `GET /v1/packages` sonucuna konmaz ve burada Strategy/Indicator/Condition/ESP ile aynı catalog bölümü altında gösterilmez.</th>
  </tr>
</table>

## 1.2 Araştırma döngüsündeki yeri

<table>
  <tr>
    <th>Research / hypothesis<br/>  -&gt; Create Package / Draft / Validation / Approval<br/>  -&gt; Package Library (discover, inspect, use, derive, export, lifecycle)<br/>  -&gt; Strategy Definition / Package Revision references exact dependencies<br/>  -&gt; Ready Check resolves compatibility<br/>  -&gt; Backtest Run manifest pins all transitive revisions<br/>  -&gt; Result / Agent artifact preserves provenance<br/><br/>Package Library = catalog and governed reuse layer; it is not the Backtest Engine, Mainboard composition or Agent runtime.</th>
  </tr>
</table>

## 1.3 Sayfa dışı sınırlar

- Create / validation pipeline: Package Request, Pre-Check, candidate, Draft Package, baseline and approval evidence are produced in the Create Package / Pre-Check flows. Package Library only projects relevant lifecycle and evidence state.

- Embedded System Package deep management: ESP rows can be discovered and inspected here, but canonical resolver registry, test vectors and activation details belong to the Embedded System Packages page.

- Strategy construction: Package Library identifies and pins a reusable dependency; Strategy Details defines how Indicator/Condition/Strategy Package content is used in a concrete Strategy Definition.

- Mainboard external objects: Trading Signal and Trade Log are discovered and edited through their external working-object pages, not converted into package rows.

- Rationale editing: The catalog may filter or display a Family assignment. Family card and batch assignment editing mechanics are documented in Rationale Families.

# 2. Erişim, Görünürlük, Ownership ve Server-Side Policy

<table>
  <tr>
    <th>Actor</th>
    <th>List / view</th>
    <th>Use / reference</th>
    <th>Create revision / edit</th>
    <th>Derive</th>
    <th>Delete / deprecate</th>
    <th>Publish / restore</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Protected library and detail access yok; public-read policy ayrıca açılmadıkça katalog döndürülmez.</td>
    <td>Yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Own + explicitly shared + published/system packages.</td>
    <td>Policy-allowed exact revisionı kendi Strategy/Package outputunda kullanır.</td>
    <td>Yalnız own package draft/revision.</td>
    <td>Erişebildiği foreign revisiondan own root türetebilir.</td>
    <td>Yalnız own root için soft delete; lifecycle gate server-side.</td>
    <td>Publish yok. Restore/permanent delete yok.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Shared working catalog + own resources; private personal draftlar otomatik görünmez.</td>
    <td>Erişebildiği exact revisionı kullanır.</td>
    <td>Yalnız own package.</td>
    <td>Erişebildiği foreign revisiondan derive.</td>
    <td>Yalnız own root için soft delete/deprecate.</td>
    <td>Publish yok. Restore/permanent delete yok.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm policy-allowed roots/revisions; system packages dahil.</td>
    <td>Tüm suitable revisions.</td>
    <td>Tüm normal package roots/revisions.</td>
    <td>Gerekirse derive veya override edit.</td>
    <td>Tüm normal roots için soft delete/deprecate.</td>
    <td>`approve_and_publish`; Trash view/restore/permanent delete.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>UI login olmadan Tool Gateway ile allowed shared/system working catalog. Private personal draftlar policy dışında kalır.</td>
    <td>Exact revisionı Agent output/experimentte pinler.</td>
    <td>Yalnız own Agent package root/revision.</td>
    <td>Foreign revisiondan own root derive eder.</td>
    <td>Yalnız own output root için soft delete/deprecate.</td>
    <td>Publish yok. Trash yok.</td>
  </tr>
</table>

Frontendde delete × ikonunun disabled veya hidden olması yalnız kullanıcı deneyimidir. Server, her list/detail/use/derive/revision/delete/deprecate/export/import requestinde principal türünü, role, ownership, visibility, lifecycle, approval/validation state ve target revisionı yeniden doğrular. Clientten gelen owner veya role alanı otorite değildir.

<table>
  <tr>
    <th>Rationale exception sınırı: Rationale Family ve Package Rationale Assignment global shared-editing exceptiondır. Bu exception yalnız semantic assignment scopeundadır; package payloadını, codeunu, parameter şemasını, dependency manifestini, ownerını veya lifecycle stateini herkesin düzenleyebileceği anlamına gelmez.</th>
  </tr>
</table>

# 3. V18 Interface Behavior - Yerleşim, Navigasyon ve Görünür Bileşenler

V18 Package Library, Edit menüsü altından açılan bir page viewdır. Ana görünüm önce kısa bir erişim açıklaması, ardından altı alanlı bir filter bar ve type bazlı section listeleri sunar. Her package satırı tek satırda isim + summary gösterir; açılır ok satırı genişletir, × silme kontrolü varsa packagei local demo dizisinden kaldırır. Açılan detail alanı açıklama metni, küçük metadata cell grid ve `Export Package` butonu içerir.

## 3.1 V18 bileşen envanteri

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 görünümü / default</th>
    <th>Kullanıcı etkileşimi</th>
    <th>Production V1 karşılığı</th>
  </tr>
  <tr>
    <td>Navigation</td>
    <td>Edit &gt; Package Library; alt menüde Strategy, Indicator, Condition, Trading Signal, Trade Log, Embedded System</td>
    <td>Submenu target type filterı set eder ve ilgili sectiona scroll eder.</td>
    <td>Canonical four-type catalog. Trading Signal/Trade Log submenu items External Objects routesine yönlendirilir.</td>
  </tr>
  <tr>
    <td>Intro paragraph</td>
    <td>Packages reusable building blocks; role açıklaması.</td>
    <td>Salt read-only bilgi.</td>
    <td>Policy summaryden türetilmiş helper; gerçek authorization backendde.</td>
  </tr>
  <tr>
    <td>Filter bar</td>
    <td>Type, Market, Timeframe, Rationale Family, Status, Sort By. Default: all/all/all/all/all/Created Date.</td>
    <td>Her select local filter statei değiştirir ve page contenti yeniden render edilir.</td>
    <td>Server-side query facets + optional persisted view preference. V18 status/sort conflationı ayrıştırılır.</td>
  </tr>
  <tr>
    <td>Package sections</td>
    <td>Strategy Packages; Indicator Packages; Condition Packages; Trading Signal Packages; Trade Log Packages; Embedded System Packages. [V18 legacy prototype label; Production domain/API type değildir.]</td>
    <td>Active filters sonrası her category ayrı görünür.</td>
    <td>Strategy / Indicator / Condition / Embedded System only. Empty sections server result/UX policyye göre hidden veya labeled empty.</td>
  </tr>
  <tr>
    <td>Package row</td>
    <td>`name | summary`; ▼ button; conditional ×.</td>
    <td>▼ detaili expand/collapse eder; × removes local item.</td>
    <td>Row current root + revision projection; actions permission/state-aware commands.</td>
  </tr>
  <tr>
    <td>Detail panel</td>
    <td>Name, free-text details, metadata grid: Rationale, Market, Timeframe, Status, Backtest Ready, OOS, Permissions; Export Package.</td>
    <td>User detaili okur ve export başlatır.</td>
    <td>Root metadata, revision metadata, contracts, dependencies, validation, usage/provenance, permission and action sections.</td>
  </tr>
  <tr>
    <td>Empty state</td>
    <td>`No package matched current filters.`</td>
    <td>Filters daraltılınca appears.</td>
    <td>Same clear message + Clear Filters action + server query diagnostic.</td>
  </tr>
</table>

## 3.2 V18 filter controls - exact visible options

<table>
  <tr>
    <th>Filter</th>
    <th>V18 options</th>
    <th>V18 default</th>
    <th>V18 interaction</th>
    <th>Canonical alignment</th>
  </tr>
  <tr>
    <td>Type</td>
    <td>All; Strategy; Indicator; Condition; Trading Signal; Trade Log; Embedded System</td>
    <td>All</td>
    <td>Section filters local `packageGroups`.</td>
    <td>Production: All; Strategy Package; Indicator Package; Condition Package; Embedded System Package. Signal/Trade Log values removed; route to external objects.</td>
  </tr>
  <tr>
    <td>Market</td>
    <td>All; BTCUSDT; ETHUSDT; Multi</td>
    <td>All</td>
    <td>Exact visible meta equality.</td>
    <td>Production supports market/instrument scopes from catalog projection; System scope is valid for ESP; unsupported values not silently hidden.</td>
  </tr>
  <tr>
    <td>Timeframe</td>
    <td>All; 15m; 1h; 4h; Weekly; Multi</td>
    <td>All</td>
    <td>Exact visible meta equality.</td>
    <td>Production supports explicit, multi, same-as-base capability and System for ESP; only values supplied by current query facets are shown.</td>
  </tr>
  <tr>
    <td>Rationale Family</td>
    <td>All + current dynamic Family names</td>
    <td>All</td>
    <td>Matches local display name.</td>
    <td>Production filter uses stable family_root_id; label displays current Family revision name. Supports All, active Families, Unassigned and optional Deleted Family Assignments.</td>
  </tr>
  <tr>
    <td>Status</td>
    <td>All; Backtest Ready; Approved; Imported; Mapped</td>
    <td>All</td>
    <td>Matches one demo string.</td>
    <td>Not one enum. Split lifecycle, validation, readiness, approval/publication and ESP trust facets.</td>
  </tr>
  <tr>
    <td>Sort By</td>
    <td>Created Date; Net Profit; Max Drawdown; ROMAD; Win Rate; Trade Count; Out-of-Sample Result</td>
    <td>Created Date</td>
    <td>Local numeric/string sort.</td>
    <td>Generic sorts always allowed: updated/created/name/type/usage. Performance sorts only Strategy Package projections with linked runs; N/A for other types.</td>
  </tr>
</table>

<table>
  <tr>
    <th>V18 Interface Observation: V18 Indicator, Condition and Embedded rows use Net Profit, Drawdown, ROMAD, Win Rate and Trade Count values of zero in local metadata. Production V1 bunu gerçek performans verisi gibi saklamaz veya sıralamaz. Bu alanlar bu types için `null / Not applicable` olur; yalnız Strategy Package performance projectionı linked run evidence üzerinden görünür.</th>
  </tr>
</table>

## 3.3 Package rows, sections and V18 sample content

<table>
  <tr>
    <th>V18 section</th>
    <th>Examples visible in HTML</th>
    <th>V18 metadata convention</th>
    <th>Production correction</th>
  </tr>
  <tr>
    <td>Strategy Packages</td>
    <td>Reversal Sensor 15-30-1-1.5 Strategy; Volume Breakout Strategy</td>
    <td>BTCUSDT / 15m / Reversal / Mean Reversion / Backtest Ready; metrics populated.</td>
    <td>Current revision projection with optional linked-run performance summary, never intrinsic package payload performance.</td>
  </tr>
  <tr>
    <td>Indicator Packages</td>
    <td>SMOOTHED HEIKEN ASHI; Predictive Ranges</td>
    <td>Multi / Multi / Approved; metrics zero.</td>
    <td>Input/output/parameter/timing contract and validation state shown; no fabricated result metrics.</td>
  </tr>
  <tr>
    <td>Condition Packages</td>
    <td>Resistance Proximity Trigger Condition; Volatility Compression Condition</td>
    <td>Multi / Multi / Approved; metrics zero.</td>
    <td>Input graph, output kind, availability and compatibility shown; no fabricated result metrics.</td>
  </tr>
  <tr>
    <td>Trading Signal Packages [V18 legacy prototype label; Production domain/API type değildir.]</td>
    <td>Copy Trading Signal Source A; Trade Log Mapping / Imported External Record</td>
    <td>Mapped / weekly / external rationale.</td>
    <td>Removed from Package Library. V18 records must be migrated/routed to Trading Signal or Trade Log working-object catalog.</td>
  </tr>
  <tr>
    <td>Trade Log Packages [V18 legacy prototype label; Production domain/API type değildir.]</td>
    <td>Imported Trade Log Example</td>
    <td>Imported / BTCUSDT / 15m.</td>
    <td>Removed from Package Library. Existing external history remains a Trade Log root/revision, not PackageRoot.</td>
  </tr>
  <tr>
    <td>Embedded System Packages</td>
    <td>ESP_TA_SMA; ESP_TA_EMA; ESP_TA_RSI; ESP_TA_ATR; etc.</td>
    <td>System / System / Approved.</td>
    <td>Catalog row includes canonical signature, adapter, exact test vector evidence and trust level; details continue on Page 9.</td>
  </tr>
</table>

# 4. Production Backend Behavior - Canonical Catalog Projection

Production Package Library, client memorydeki küçük bir `packageGroups` dizisini filtrelemez. Role-aware backend query, callerın erişemeyeceği root/revisionları liste sonucuna koymadan pagination/cursor ile current catalog projection döndürür. UI cache yalnız gösterim optimizasyonudur; root/revision, policy, lifecycle ve validation doğrusu backenddir.

## 4.1 Canonical package section model

<table>
  <tr>
    <th>Canonical section</th>
    <th>Purpose</th>
    <th>Minimum projected detail</th>
    <th>Explicitly excluded</th>
  </tr>
  <tr>
    <td>Strategy Packages</td>
    <td>Reusable strategy blueprintleri keşfetme ve Strategy Draft yaratma/derive.</td>
    <td>Blueprint scope; default config surfaces; pinned Indicator/Condition/ESP dependencies; readiness; linked run performance projection where evidence exists.</td>
    <td>Concrete Market Dataset revision, Backtest Range, run-specific commission and Equity Allocation plan are not intrinsic package payload.</td>
  </tr>
  <tr>
    <td>Indicator Packages</td>
    <td>Calculation contracts discovery.</td>
    <td>Input series; parameter schema; output names/kinds; timeframe capabilities; availability; repaint policy; validation state.</td>
    <td>Standalone PnL/ROMAD/Win Rate.</td>
  </tr>
  <tr>
    <td>Condition Packages</td>
    <td>Boolean/score/permission logic discovery.</td>
    <td>Declared inputs; referenced output contract; expression/logic graph summary; output kind/direction; availability; compatibility.</td>
    <td>Required/Supporting role; that belongs to Strategy Details use context.</td>
  </tr>
  <tr>
    <td>Embedded System Packages</td>
    <td>Trusted platform resolver/adaptor discovery.</td>
    <td>Canonical function signature; runtime adapter; deterministic test vectors; trust level; registry status.</td>
    <td>Open-ended general-user code editor or automatic resolver activation; detailed management is Page 9.</td>
  </tr>
</table>

## 4.2 Root and revision projection contract

<table>
  <tr>
    <th>Layer</th>
    <th>Required fields</th>
    <th>Library behavior</th>
  </tr>
  <tr>
    <td>Package Root</td>
    <td>package_id; package_type; owner_actor_id; created_by_actor_id; root.lifecycle_state. current_revision_id; derived_from_revision_id; visibility_scope.</td>
    <td>Row identity and policy/lifecycle context. Current revision can change, root ID stays stable. Root type never changes.</td>
  </tr>
  <tr>
    <td>Current Package Revision</td>
    <td>package_revision_id; revision_number; payload summary; input_contract; output_contract; dependency_snapshot; rationale_family_snapshot; validation_summary; content_hash; created_at/by; change_note; status_projection.</td>
    <td>Expand/detail shows immutable current technical truth. Read-only until authorized revision draft action; no in-place SQL mutation.</td>
  </tr>
  <tr>
    <td>Usage / provenance projection</td>
    <td>reference_count; active_strategy_reference_count; historical_run_reference_count; derived_from / derived_children; Agent task/checkpoint provenance where allowed.</td>
    <td>Human sees reuse and impact; delete/deprecate warning includes historical and active-use implications without exposing unauthorized details.</td>
  </tr>
  <tr>
    <td>Permission projection</td>
    <td>can_view; can_use; can_derive; can_create_revision; can_request_validation; can_request_approval; can_approve_publish; can_deprecate; can_soft_delete; can_export.</td>
    <td>Frontend renders action availability from backend response but backend repeats all guards.</td>
  </tr>
</table>

## 4.3 Detail panel contract - Production V1

<table>
  <tr>
    <th>Detail section</th>
    <th>Must show</th>
    <th>Why it is required</th>
  </tr>
  <tr>
    <td>Identity &amp; lifecycle</td>
    <td>Canonical name, root ID (copyable technical reference), type, owner/created by, visibility, lifecycle, current revision number/id, derived source if any.</td>
    <td>Prevents name-as-identity shortcuts and explains whether a root is usable, deprecated or deleted.</td>
  </tr>
  <tr>
    <td>Revision &amp; content summary</td>
    <td>Change note, content hash, created time/actor, type-specific payload summary, schema version.</td>
    <td>Makes immutable history and change intent inspectable without editing payload inline.</td>
  </tr>
  <tr>
    <td>Input/output contract</td>
    <td>Inputs, required data capability, output kinds/names/units/direction, timeframe and availability semantics, closed-bar/intrabar and lookahead/repaint policy.</td>
    <td>Enables safe human/Agent compatibility judgement before selection.</td>
  </tr>
  <tr>
    <td>Dependencies</td>
    <td>Exact package_revision_ids, ESP revisions, implementation version, data capability and documentation refs; transitive resolution status.</td>
    <td>No `latest` ambiguity; unresolved/cycle/deleted dependency is visible.</td>
  </tr>
  <tr>
    <td>Validation &amp; readiness</td>
    <td>Validation state, warnings/errors, test evidence summary, readiness state, trust level when ESP, approval/publication state.</td>
    <td>Separates technical validity from approval, discoverability and usable context.</td>
  </tr>
  <tr>
    <td>Rationale &amp; provenance</td>
    <td>Family root/revision snapshot, display label, derivation, origin/import source, Agent task/checkpoint provenance where policy allows.</td>
    <td>Supports semantic discovery while preserving historical truth.</td>
  </tr>
  <tr>
    <td>Usage impact</td>
    <td>Current active references, historical run manifests, whether new use is allowed, potential blockers.</td>
    <td>User understands deprecate/delete consequences without modifying history.</td>
  </tr>
  <tr>
    <td>Actions</td>
    <td>Use in…, Create Strategy Draft from Package (Strategy only), Derive, Create Revision, Request Validation, Request Approval, Admin Approve &amp; Publish, Export, Deprecate, Move to Trash.</td>
    <td>Action set is type/role/state dependent. Absent actions are explained by permission/lifecycle; not merely hidden.</td>
  </tr>
</table>

# 4.4 Interaction State Matrix

<table>
  <tr>
    <th>Component/state</th>
    <th>Default / trigger</th>
    <th>UI behavior</th>
    <th>Payload / engine effect</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>Catalog initial load</td>
    <td>Route open; default view all types / current permitted scope / newest updated.</td>
    <td>Skeleton rows, filter controls disabled until facets arrive.</td>
    <td>No engine effect; catalog query only.</td>
    <td>Retry query; preserve last successful filters if server error.</td>
  </tr>
  <tr>
    <td>Filtered list</td>
    <td>User changes a filter or search.</td>
    <td>Debounced query; cursor resets; URL/view state updates.</td>
    <td>No package mutation.</td>
    <td>Clear one filter or Clear All; request facets refresh.</td>
  </tr>
  <tr>
    <td>No matching packages</td>
    <td>Successful query returns empty.</td>
    <td>`No packages matched current filters.` + `Clear filters` action.</td>
    <td>No engine effect.</td>
    <td>Clear/relax filters; create/derive only from allowed source flows.</td>
  </tr>
  <tr>
    <td>Detail collapsed</td>
    <td>Default for all rows.</td>
    <td>Name/summary/status chips; no dependency payload loaded until detail open if lazy.</td>
    <td>No engine effect.</td>
    <td>Open row or dedicated detail route.</td>
  </tr>
  <tr>
    <td>Detail loading</td>
    <td>Expand/detail query in progress.</td>
    <td>Skeleton sections; action buttons disabled.</td>
    <td>No mutation.</td>
    <td>Retry detail query; list remains usable.</td>
  </tr>
  <tr>
    <td>Detail stale</td>
    <td>Current revision changed, lifecycle changed or permission projection changed after list loaded.</td>
    <td>Banner: `This package changed after this view was loaded.` Mutating actions disabled.</td>
    <td>No stale expected_head_revision_id may be submitted.</td>
    <td>Reload package; compare previous/current; derive or retry with fresh head.</td>
  </tr>
  <tr>
    <td>Deprecated root</td>
    <td>root.lifecycle_state.DEPRECATED.</td>
    <td>Amber badge; Use not default; export/history remain available subject to policy.</td>
    <td>New default strategy selection blocked; historical reproduction permitted by policy.</td>
    <td>Choose active replacement, derive/upgrade, or explicitly use only where historical policy permits.</td>
  </tr>
  <tr>
    <td>Validation blocked</td>
    <td>Validation failed/unresolved dependency/timing incompatibility.</td>
    <td>Red/amber summary; Use action disabled or context-specific blocked.</td>
    <td>Cannot be pinned into new executable strategy/run.</td>
    <td>Open validation report; repair in own revision or derive; revalidate.</td>
  </tr>
  <tr>
    <td>Delete pending</td>
    <td>Authorized user selects Move to Trash.</td>
    <td>Confirmation modal; button loading; row remains until server success.</td>
    <td>Soft delete root; blocks new use/revisions; no historic manifest mutation.</td>
    <td>Cancel; on success show toast. Restore only Admin via Trash.</td>
  </tr>
  <tr>
    <td>Export generating</td>
    <td>Export command accepted.</td>
    <td>Progress/status; repeated clicks disabled by idempotency key.</td>
    <td>Immutable export artifact generated; no package mutation.</td>
    <td>Download when ready; retry job if failure with same revision selection.</td>
  </tr>
</table>

# 5. Field Contract Matrix - Filters, Search and Detail Controls

V18 Package Libraryde * ile işaretlenmiş zorunlu input yoktur. Bu sayfada filters ve search query optionaldır. Ancak action dialogs içinde target selection, change note, approval reason veya confirm text koşullu zorunlu olabilir. Zorunluluk, UI labelden bağımsız olarak server validation ve Agent tool schema tarafından da uygulanır.

<table>
  <tr>
    <th>Field / control</th>
    <th>UI type &amp; production default</th>
    <th>Requiredness / options</th>
    <th>Request payload</th>
    <th>Validation / dependent behavior</th>
  </tr>
  <tr>
    <td>Search</td>
    <td>Text input. Default empty. Placeholder: `Search package name, output, dependency or rationale family`.</td>
    <td>Optional. Case-insensitive server search across permitted projection fields.</td>
    <td>q string, max 200 chars.</td>
    <td>Trim/normalize; no regex execution; query is permission-scoped. Empty query returns default listing.</td>
  </tr>
  <tr>
    <td>Type</td>
    <td>Multi-select or single select. Default All.</td>
    <td>All; Strategy Package; Indicator Package; Condition Package; Embedded System Package.</td>
    <td>type[] or type.</td>
    <td>External types rejected with `PACKAGE_TYPE_INVALID`; Type changes valid sort/facet options.</td>
  </tr>
  <tr>
    <td>Market / Instrument scope</td>
    <td>Facet select. Default All.</td>
    <td>Values supplied by backend facets: instrument(s), Multi, System.</td>
    <td>market_scope[] / instrument_id.</td>
    <td>System exists only for ESP. Any requested value must be caller-visible and facet-valid.</td>
  </tr>
  <tr>
    <td>Timeframe scope</td>
    <td>Facet select. Default All.</td>
    <td>Exact TFs; Multi; Same-as-base capability; System.</td>
    <td>timeframe_scope[].</td>
    <td>System only ESP; source facets derive from permitted result set.</td>
  </tr>
  <tr>
    <td>Rationale Family</td>
    <td>Facet select. Default All.</td>
    <td>All; active family root IDs; Unassigned; optional Deleted Family Assignments.</td>
    <td>rationale_family_id or assignment_state.</td>
    <td>Stable ID, not display-name string. Assignment changes are shown from current root/revision projection.</td>
  </tr>
  <tr>
    <td>Lifecycle</td>
    <td>Facet select. Default Active + allowed published scope.</td>
    <td>UI filter labels: Active; Deprecated; Deleted only for Admin/Trash route. Technical root.root.lifecycle_state.values: active | deprecated | soft_deleted.</td>
    <td>root.lifecycle_state.</td>
    <td>User-facing Deleted is not exposed in normal catalog route; technical state soft_deleted must not be used for new work.</td>
  </tr>
  <tr>
    <td>Validation / readiness</td>
    <td>Facet select. Default usable only.</td>
    <td>Validation: Pending/Passed/Failed; readiness: Ready/Blocked/N/A.</td>
    <td>validation_state, readiness_state.</td>
    <td>Filter values distinct; invalid combinations return 422 filter validation or zero result, never coerced silently.</td>
  </tr>
  <tr>
    <td>Approval / visibility</td>
    <td>Facet select. Default policy-usable catalog visibility.</td>
    <td>visibility_scope: private | explicitly_shared | published | system; revision.approval_state: draft | approval_requested | approved | rejected; root.root.lifecycle_state.is shown separately.</td>
    <td>approval_state, visibility_scope.</td>
    <td>Non-owner draft visibility filtered server-side. Published/shared stays Admin-controlled.</td>
  </tr>
  <tr>
    <td>Sort By</td>
    <td>Select. Default Last Updated descending; V18 Created Date becomes allowed option.</td>
    <td>Updated; Created; Name; Type; Usage; Strategy performance sorts where applicable.</td>
    <td>sort, direction.</td>
    <td>Net Profit/ROMAD/Drawdown/Win Rate/Trade Count only valid for Strategy Package performance projection; API returns `NOT_APPLICABLE` facet for other types.</td>
  </tr>
  <tr>
    <td>Use in…</td>
    <td>Action dialog. Default no target.</td>
    <td>Conditionally required target draft/workspace; only compatible targets shown.</td>
    <td>target_kind, target_id, package_revision_id.</td>
    <td>Target and revision must be visible/use-authorized, active/compatible, and no cycle. Exact revision pinned.</td>
  </tr>
  <tr>
    <td>Derive Package</td>
    <td>Action dialog. Default source current revision.</td>
    <td>Derived name and optional change note required; optional target visibility.</td>
    <td>source_package_revision_id, canonical_name, change_note, visibility.</td>
    <td>Caller must view source; creates new root owned by caller; source remains unchanged.</td>
  </tr>
  <tr>
    <td>Create Revision</td>
    <td>Action. Default current head.</td>
    <td>expected_head_revision_id ID required (hidden concurrency field); change note required.</td>
    <td>base_revision_id, expected_head_revision_id, draft_payload/change_note.</td>
    <td>Owner/Admin only; 409 if head changed; current revision payload never patched in place.</td>
  </tr>
  <tr>
    <td>Approve &amp; Publish</td>
    <td>Admin-only action modal.</td>
    <td>Approval reason required; validation Passed and policy evidence required.</td>
    <td>package_revision_id, evidence_snapshot_id, approval_reason.</td>
    <td>Atomic approval + publication; reject if non-Admin or evidence stale/failed.</td>
  </tr>
  <tr>
    <td>Move to Trash</td>
    <td>Confirmation action.</td>
    <td>Confirmation required; expected root/current revision guard required.</td>
    <td>package_id, expected_head_revision_id, idempotency_key.</td>
    <td>Owner/Admin normal policy; dependent history survives; soft-deleted root cannot new-use.</td>
  </tr>
</table>

## 5.1 Conditional requiredness and dependent-field mutation rules

<table>
  <tr>
    <th>Trigger</th>
    <th>What becomes required / changes</th>
    <th>Preserve or clear state</th>
    <th>Engine / lifecycle impact</th>
  </tr>
  <tr>
    <td>Type changes in filter</td>
    <td>Sort and facet values recalculated.</td>
    <td>Keep valid common filters; clear facets invalid for new type with visible `Filter adjusted for selected type.` notice.</td>
    <td>Query only; no package mutation.</td>
  </tr>
  <tr>
    <td>Select Indicator/Condition in Use in…</td>
    <td>Compatible target Strategy/Package Draft selection becomes required.</td>
    <td>Do not preselect a hidden/unauthorized target; retain user selection only if still compatible.</td>
    <td>Exact package revision reference will be pinned into target draft after command success.</td>
  </tr>
  <tr>
    <td>Select Strategy Package in Use in…</td>
    <td>Create Strategy Draft target/workspace becomes required unless one default workspace is eligible.</td>
    <td>No direct Mainboard item attach. Existing target selections that are not compatible clear with warning.</td>
    <td>Backend creates/updates Strategy Definition draft derived from Strategy Package; source package remains immutable.</td>
  </tr>
  <tr>
    <td>Derive foreign package</td>
    <td>New canonical name and change note become required.</td>
    <td>Source revision ID immutable/readonly; no source payload write.</td>
    <td>Creates a new Package Root owned by caller with `derived_from_revision_id` provenance.</td>
  </tr>
  <tr>
    <td>Create Revision</td>
    <td>expected_head_revision_id and change note required.</td>
    <td>Base revision is readonly; editing occurs in draft payload state.</td>
    <td>Concurrent change returns conflict; server must not overwrite current revision.</td>
  </tr>
  <tr>
    <td>Approve &amp; Publish</td>
    <td>Approval reason and validation/evidence snapshot required.</td>
    <td>If validation state becomes stale/failed, clear approval confirmation and force refresh.</td>
    <td>Admin atomically writes approval_state=approved and shared_published visibility where policy applies.</td>
  </tr>
  <tr>
    <td>Deprecate / delete</td>
    <td>Confirmation becomes required; replacement package recommendation optional.</td>
    <td>No historical revision or usage reference is cleared.</td>
    <td>Deprecated blocks default new use; deleted blocks all new use/revision and adds Trash record.</td>
  </tr>
</table>

# 6. Information Content Catalog and Final UI Text

V18 Package Library HTMLinde ⓘ button bulunmaz. Bu nedenle “V18 existing info button” sayısı sıfırdır. Aşağıdaki catalog, Production V1de filter labels ve detail status badges yanında gösterilmesi önerilen contextual information panels için Implementation Decisiondır; burada verilen metin UIya doğrudan yerleştirilebilir. Mevcut V18de yeni ⓘ eklemek zorunlu değildir; eklendiğinde bu content kullanılmalıdır.

<table>
  <tr>
    <th>Info key / location</th>
    <th>Panel title</th>
    <th>Final UI text</th>
  </tr>
  <tr>
    <td>pkgTypeInfo / Type filter</td>
    <td>Package Type</td>
    <td>A package type defines the technical role and allowed contract of a reusable component. Strategy Packages are reusable blueprints. Indicator Packages calculate series, states or triggers. Condition Packages turn declared inputs into boolean, score or permission outputs. Embedded System Packages are trusted platform resolvers. Trading Signal and Trade Log are not package types; they are external working objects managed through Add Outsource Signal.</td>
  </tr>
  <tr>
    <td>pkgRationaleInfo / Rationale Family</td>
    <td>Rationale Family</td>
    <td>Rationale Family is a shared semantic classification used to discover related research logic. The filter uses the stable Family identity, while the current display name is shown in the UI. A Family assignment does not grant permission to edit a package payload, dependencies or owner. Unassigned packages remain valid unless another rule blocks their use.</td>
  </tr>
  <tr>
    <td>pkgStatusInfo / Status facets</td>
    <td>Lifecycle, Validation and Approval</td>
    <td>These states answer different questions. Lifecycle says whether the package root is Active, Deprecated or Deleted. Validation says whether the selected revision passed its technical checks. Readiness says whether it can be used in a specific context. Approval and publication say whether the revision is private, requested for approval or shared/published. Do not interpret one badge as all of these states.</td>
  </tr>
  <tr>
    <td>pkgTimingInfo / detail contract</td>
    <td>Timing and Lookahead Safety</td>
    <td>A package must state when its output becomes available. Closed-bar-only outputs can be consumed only after the source bar closes. Intrabar outputs require compatible tick or intrabar path capability. Research-data inputs use available time, not only event time. A critical repaint or future-data risk blocks active use until resolved.</td>
  </tr>
  <tr>
    <td>pkgDependencyInfo / detail dependencies</td>
    <td>Pinned Dependencies</td>
    <td>Dependencies are exact revision references, not links to the latest package. Updating a dependency later does not silently change this package, an existing strategy or a historical backtest. A missing, deleted, untrusted or cyclic dependency can block new use and must be repaired in a new revision or derived package.</td>
  </tr>
  <tr>
    <td>pkgUseInfo / Use in…</td>
    <td>Use a Package</td>
    <td>Using a package creates an exact revision reference in the selected compatible target. It does not transfer ownership and does not modify the source package. Strategy Packages create or seed a Strategy Draft; Indicator and Condition Packages are attached as dependencies inside a compatible logic context.</td>
  </tr>
  <tr>
    <td>pkgDeriveInfo / Derive</td>
    <td>Derive a Package</td>
    <td>Derive creates a new package root owned by you, starting from the selected source revision. The source package is not edited. The new root records its source revision for provenance and must complete its own validation and approval lifecycle before shared publication.</td>
  </tr>
  <tr>
    <td>pkgExportInfo / Export</td>
    <td>Export Package Revision</td>
    <td>Export produces a portable immutable manifest for the selected package revision and its dependency information. It does not create a live connection to another system and does not guarantee that the receiving environment can execute the package. Imported dependencies must be resolved and validated again.</td>
  </tr>
  <tr>
    <td>pkgDeprecateInfo / Deprecate</td>
    <td>Deprecate a Package</td>
    <td>Deprecation keeps the package and its historical revisions available for audit and approved historical reproduction, but removes it from default new-use choices. Use deprecation when a replacement exists or a package should no longer be selected for new work. It is different from moving the root to Trash.</td>
  </tr>
  <tr>
    <td>pkgTrashInfo / Move to Trash</td>
    <td>Move Package to Trash</td>
    <td>Moving a package to Trash is a soft delete. It removes the root from normal catalog discovery and blocks new use or revisions, but it does not rewrite historical strategy references, backtest manifests or results. Only an Admin can view Trash, restore the root or permanently delete the recoverable record.</td>
  </tr>
</table>

## 6.1 Placeholder, helper, warning, toast, modal and error texts

<table>
  <tr>
    <th>UI situation</th>
    <th>Final user-visible text</th>
    <th>State / implementation note</th>
  </tr>
  <tr>
    <td>Search placeholder</td>
    <td>Search package name, output, dependency or rationale family</td>
    <td>Search is server-side and permission-scoped.</td>
  </tr>
  <tr>
    <td>Filter empty state</td>
    <td>No packages matched current filters.</td>
    <td>Shown only after successful zero-result response.</td>
  </tr>
  <tr>
    <td>Empty-state secondary action</td>
    <td>Clear filters</td>
    <td>Resets all optional filters and returns the default permitted catalog view.</td>
  </tr>
  <tr>
    <td>Loading</td>
    <td>Loading packages…</td>
    <td>Use skeleton layout; no fake static result data.</td>
  </tr>
  <tr>
    <td>Detail loading</td>
    <td>Loading package details…</td>
    <td>Actions remain disabled until permission/lifecycle projection arrives.</td>
  </tr>
  <tr>
    <td>Stale detail banner</td>
    <td>This package changed after this view was loaded. Reload it before continuing.</td>
    <td>Shown on current revision, permission or lifecycle mismatch.</td>
  </tr>
  <tr>
    <td>Deprecated warning</td>
    <td>This package is deprecated and is not offered for new work by default. Historical references remain unchanged.</td>
    <td>Read-only/history/export actions may remain available by policy.</td>
  </tr>
  <tr>
    <td>Dependency warning</td>
    <td>This package has unresolved or incompatible dependencies and cannot be used in a new executable configuration.</td>
    <td>Open dependency/validation panel; Use disabled.</td>
  </tr>
  <tr>
    <td>Delete confirm title</td>
    <td>Move package to Trash?</td>
    <td>Do not say “permanently delete.”</td>
  </tr>
  <tr>
    <td>Delete confirm body</td>
    <td>This removes the package from the active catalog and blocks new use. Historical strategies, run manifests and results keep their pinned revision references. Only an Admin can restore or permanently delete the Trash record.</td>
    <td>Confirmation must name package and current revision.</td>
  </tr>
  <tr>
    <td>Delete success</td>
    <td>Package moved to Trash.</td>
    <td>Toast after canonical server success; remove row from active list.</td>
  </tr>
  <tr>
    <td>Delete denied</td>
    <td>You do not have permission to move this package to Trash.</td>
    <td>Server error; do not rely on disabled icon.</td>
  </tr>
  <tr>
    <td>Use success</td>
    <td>Package revision attached to the selected draft.</td>
    <td>Include display name and revision number; target draft reloads canonical state.</td>
  </tr>
  <tr>
    <td>Derive success</td>
    <td>A new draft package was created from this revision.</td>
    <td>Open newly owned draft or show direct link/action.</td>
  </tr>
  <tr>
    <td>Export success</td>
    <td>Package export is ready.</td>
    <td>Download signed/authorized artifact; event/audit includes revision id.</td>
  </tr>
  <tr>
    <td>Publish denied</td>
    <td>Only an Admin can approve and publish a package.</td>
    <td>Keep draft/approval request intact.</td>
  </tr>
  <tr>
    <td>Conflict error</td>
    <td>This package changed before your action could be saved. Reload the package, compare the new revision, then retry or derive a new package.</td>
    <td>Mapped from PACKAGE_REVISION_CONFLICT / 409.</td>
  </tr>
</table>

# 7. Button / Command / State Contract

<table>
  <tr>
    <th>UI action</th>
    <th>Backend command / query</th>
    <th>Precondition</th>
    <th>Loading / success / error / retry</th>
    <th>Audit / immutable effect</th>
  </tr>
  <tr>
    <td>Open catalog</td>
    <td>GET /v1/packages?...</td>
    <td>Authenticated / policy-visible route.</td>
    <td>Skeleton -&gt; list; query error -&gt; Retry.</td>
    <td>Read event optional; no mutation.</td>
  </tr>
  <tr>
    <td>Open detail / history</td>
    <td>GET /v1/packages/{package_id}</td>
    <td>can_view current root/revision.</td>
    <td>Detail skeleton -&gt; projection; 404/403 result does not leak hidden metadata.</td>
    <td>Read event optional; no mutation.</td>
  </tr>
  <tr>
    <td>Use in…</td>
    <td>POST /v1/strategy-drafts/{id}/package-references or type-specific target command</td>
    <td>can_use; active/useable revision; compatible target; no cycle.</td>
    <td>Disable submit -&gt; canonical target draft state; 422/409 -&gt; inline issue + Reload/Retry.</td>
    <td>Target draft gets exact revision reference; source unchanged; audit `PACKAGE_USED`.</td>
  </tr>
  <tr>
    <td>Create Strategy Draft from Strategy Package</td>
    <td>POST /v1/strategy-drafts:from-package</td>
    <td>Strategy Package revision useable; permitted workspace.</td>
    <td>Loading -&gt; new Strategy Draft id; failure leaves package unchanged.</td>
    <td>New Strategy root/draft provenance records source root/revision.</td>
  </tr>
  <tr>
    <td>Derive</td>
    <td>POST /v1/packages/{id}/revisions/{rev}:derive</td>
    <td>can_view/use source; name/change note valid.</td>
    <td>Loading -&gt; new root/draft; 409/422 -&gt; preserve input.</td>
    <td>New root owner=caller; `derived_from_revision_id`; audit `PACKAGE_DERIVED`.</td>
  </tr>
  <tr>
    <td>Create Revision</td>
    <td>POST /v1/packages/{id}/revisions:draft</td>
    <td>Owner/Admin; root active; expected_head_revision_id matches.</td>
    <td>Draft editor opens; 409 conflict -&gt; reload/compare/derive.</td>
    <td>No old revision mutation; draft is based on exact base revision.</td>
  </tr>
  <tr>
    <td>Request validation</td>
    <td>POST /v1/package-revisions/{id}/validation-runs</td>
    <td>Owner/Admin; revision draft exists; test prerequisites available.</td>
    <td>Job status via durable event/poll; refresh does not stop it.</td>
    <td>Validation artifacts/evidence persisted; audit `PACKAGE_VALIDATION_REQUESTED`.</td>
  </tr>
  <tr>
    <td>Request approval</td>
    <td>POST /v1/package-revisions/{id}/request-approval</td>
    <td>Validation evidence meets policy; caller authorized to request.</td>
    <td>Status -&gt; approval_requested; errors explain missing evidence.</td>
    <td>Approval request audit; no shared visibility yet.</td>
  </tr>
  <tr>
    <td>Approve &amp; Publish</td>
    <td>POST /v1/package-revisions/{id}/approve or `approve_and_publish` transaction</td>
    <td>Admin; validation passed; evidence snapshot current.</td>
    <td>Confirm -&gt; atomic success; 403/422/409 shows error; Retry after resolution.</td>
    <td>Writes approval decision and shared_published state atomically; audit `PACKAGE_APPROVED_PUBLISHED`.</td>
  </tr>
  <tr>
    <td>Export</td>
    <td>GET /v1/packages/{id}/revisions/{rev}:export</td>
    <td>can_view/export; revision selected.</td>
    <td>Button locked by idempotency job token -&gt; ready download; job failure -&gt; Retry.</td>
    <td>Immutable export artifact + audit `PACKAGE_EXPORTED`; no source mutation.</td>
  </tr>
  <tr>
    <td>Deprecate</td>
    <td>POST /v1/packages/{id}:deprecate</td>
    <td>Owner/Admin; active root; confirmation.</td>
    <td>Success updates lifecycle projection; new-use action disabled.</td>
    <td>root.lifecycle_state=active -&gt; deprecated; audit `PACKAGE_DEPRECATED`; history kept.</td>
  </tr>
  <tr>
    <td>Move to Trash</td>
    <td>DELETE /v1/packages/{id}</td>
    <td>Owner/Admin normal policy; root.lifecycle_state is not soft_deleted; expected_head_revision_id matches.</td>
    <td>Confirm/loading -&gt; row removed; 403/409 -&gt; toast + refresh.</td>
    <td>Soft delete root + Trash entry + audit `PACKAGE_SOFT_DELETED`; historic pinning preserved.</td>
  </tr>
</table>

# 8. User Flows

## 8.1 Find and use a compatible Indicator Package

1. User opens Package Library. Backend returns only packages visible to that User plus permitted current facets.

2. User selects Type = Indicator Package, Market = Multi and Rationale Family = Reversal / Mean Reversion. The UI sends a server query; it does not filter a preloaded global catalog.

3. User opens a row and reviews output contract, availability, dependencies and validation. The row shows `can_use=true` only if backend policy and lifecycle allow use.

4. User selects Use in… and chooses a compatible Strategy Draft. The dialog sends the selected exact `package_revision_id`, not only the package name.

5. Backend verifies use permission, active lifecycle, validation state, input/output contract, timing/data capability and dependency cycle. It writes the reference into the Strategy Draft and returns canonical draft state.

6. UI shows `Package revision attached to the selected draft.` The target Strategy Draft uses the pinned revision; future Package Library updates do not silently alter it.

## 8.2 Derive another owner’s Condition Package

1. Supervisor opens a shared Condition Package owned by a User. Detail action projection has `can_create_revision=false` and `can_derive=true`.

2. Supervisor selects Derive, supplies required new name and change note, then submits.

3. Backend copies the selected immutable source revision into a new Package Root owned by Supervisor and records `derived_from_revision_id`.

4. Supervisor modifies the new draft and starts validation. Original owner, source revision and strategies that already use it remain unchanged.

5. After requirements are met, Supervisor can request approval. Only Admin can atomically approve and publish the revision into shared/published scope.

## 8.3 Filtered empty catalog

1. User chooses a narrow combination such as Market = ETHUSDT, Type = Embedded System Package and Timeframe = 15m.

2. Server returns zero permitted matches with facet metadata. UI shows `No packages matched current filters.`

3. User selects Clear filters. UI restores the default query; no package object, ownership or lifecycle value changes.

## 8.4 Delete and Admin restore

1. Owner opens an active package row and selects Move to Trash. Confirmation explains that historical manifests remain intact.

2. Backend checks owner/Admin policy and expected_head_revision_id, marks root soft_deleted, creates a Trash record and writes audit event.

3. Normal Package Library queries stop returning the soft-deleted root. New use, new revision and approval actions are blocked; historical Strategy/Run/Result references remain resolvable by their pinned revision IDs.

4. Only Admin opens Trash and restores the root. Restore returns the same root and current revision pointer to active context; it does not create a new package revision. Restore and permanent delete are documented in the Trash page.

## 8.5 Stale concurrent revision attempt

1. Owner A and Agent both load Package X revision 7. Owner A publishes revision 8 first.

2. Agent submits a revision action with `expected_head_revision_id=revision_7`.

3. Backend returns 409 `PACKAGE_REVISION_CONFLICT`; it does not overwrite revision 8 or create a silent merge.

4. UI shows the stale banner and offers Reload, Compare, or Derive. Agent refreshes catalog state, reevaluates its intended change and either creates a revision based on revision 8 or creates a separate derived root.

# 9. Backend / Domain Model, Commands and API Parity

## 9.1 Logical domain records

<table>
  <tr>
    <th>Record</th>
    <th>Core fields</th>
    <th>Purpose</th>
  </tr>
  <tr>
    <td>package_root</td>
    <td>id, package_type, owner_ref, created_by_ref, root.lifecycle_state. current_revision_id, visibility_scope, derived_from_revision_id, timestamps.</td>
    <td>Stable identity, ownership, lifecycle and root-level policy.</td>
  </tr>
  <tr>
    <td>package_revision</td>
    <td>id, package_root_id, revision_number, payload_json, input_contract, output_contract, dependency_snapshot, rationale_family_snapshot, validation_summary, content_hash, change_note, created_by, created_at, supersedes_revision_id.</td>
    <td>Immutable technical truth used by Strategy/Backtest/Agent manifests.</td>
  </tr>
  <tr>
    <td>package_dependency</td>
    <td>source_revision_id, dependency_kind, target_revision_id or capability/schema requirement, resolution status.</td>
    <td>Exact dependency graph and cycle detection input.</td>
  </tr>
  <tr>
    <td>package_usage_reference</td>
    <td>source revision/root, consumer root/revision/run/agent artifact, reference role, created_at.</td>
    <td>Usage impact and audit/provenance projection.</td>
  </tr>
  <tr>
    <td>package_export</td>
    <td>id, source_revision_id, manifest hash, artifact URI, created_by, created_at, state.</td>
    <td>Portable immutable export artifact and retrieval control.</td>
  </tr>
  <tr>
    <td>package_import_job</td>
    <td>id, input asset/hash, parsed origin, target root, status, unresolved dependencies, diagnostics.</td>
    <td>Async import; unresolved imports become DRAFT/BLOCKED, never silently executable.</td>
  </tr>
  <tr>
    <td>approval_decision</td>
    <td>package_revision_id, actor, evidence snapshot, decision, reason, timestamp.</td>
    <td>Admin approval/publish proof; audit-correlated.</td>
  </tr>
</table>

## 9.2 Canonical query/API examples

<table>
  <tr>
    <th>GET /v1/packages?type=indicator&amp;market=BTCUSDT&amp;rationale_family_id=rf_reversal&amp;root.lifecycle_state.active&amp;sort=updated_desc&amp;cursor=...<br/><br/>200 OK<br/>{<br/>  &quot;items&quot;: [{<br/>    &quot;package_id&quot;: &quot;pkg_ind_01&quot;,<br/>    &quot;package_type&quot;: &quot;indicator&quot;,<br/>    &quot;name&quot;: &quot;RSI Core&quot;,<br/>    &quot;current_revision_id&quot;: &quot;pkgrev_ind_014&quot;,<br/>    &quot;root.lifecycle_state.: &quot;ACTIVE&quot;,<br/>    &quot;validation_state&quot;: &quot;PASSED&quot;,<br/>    &quot;market_scope&quot;: [&quot;Multi&quot;],<br/>    &quot;timeframe_scope&quot;: [&quot;same_as_base&quot;, &quot;15m&quot;, &quot;1h&quot;],<br/>    &quot;rationale_family&quot;: {&quot;id&quot;:&quot;rf_reversal&quot;,&quot;name&quot;:&quot;Reversal / Mean Reversion&quot;},<br/>    &quot;output_kinds&quot;: [&quot;numeric_series&quot;,&quot;boolean_event&quot;],<br/>    &quot;actions&quot;: {&quot;can_use&quot;:true,&quot;can_derive&quot;:true,&quot;can_create_revision&quot;:false,&quot;can_delete&quot;:false}<br/>  }],<br/>  &quot;next_cursor&quot;: null<br/>}</th>
  </tr>
</table>

Endpoint adları örnektir; davranış bağlayıcıdır. List endpoint unauthorized roots/revisionsı döndürmez. Detail endpoint listeden gelmiş görünen resource için de tekrar `can_view` uygular. UI route parametresi veya client-sent action flag authorization yerine geçmez.

## 9.3 Use, derive, revision and export parity

<table>
  <tr>
    <th>Operation</th>
    <th>Human UI path</th>
    <th>Agent Tool Gateway equivalent</th>
    <th>Shared canonical domain service</th>
  </tr>
  <tr>
    <td>Discover</td>
    <td>Filter/search/list/detail in Package Library.</td>
    <td>`catalog.search(filters)` / `catalog.get_detail(root, revision)`.</td>
    <td>Role-aware Catalog Query Service.</td>
  </tr>
  <tr>
    <td>Use</td>
    <td>Use in… target picker and attach confirmation.</td>
    <td>`package.use_in_target(package_revision_id, target_ref)`.</td>
    <td>Dependency Resolution + Target Draft Reference Service.</td>
  </tr>
  <tr>
    <td>Derive</td>
    <td>Derive modal with new name/change note.</td>
    <td>`package.derive(source_revision_id, name, note)`.</td>
    <td>Derive Package Command.</td>
  </tr>
  <tr>
    <td>Create own revision</td>
    <td>Create Revision from owned root.</td>
    <td>`package.create_revision_draft(root_id, base_revision_id, changes)`.</td>
    <td>Revision Draft Service with optimistic concurrency.</td>
  </tr>
  <tr>
    <td>Validate / request approval</td>
    <td>Action buttons and durable progress.</td>
    <td>`package.request_validation(revision_id)` / `package.request_approval(revision_id)`.</td>
    <td>Validation Orchestrator / Approval Request Service.</td>
  </tr>
  <tr>
    <td>Export</td>
    <td>Export Package action.</td>
    <td>`package.export_revision(revision_id)`.</td>
    <td>Export Job Service.</td>
  </tr>
  <tr>
    <td>Lifecycle</td>
    <td>Deprecate / Move to Trash confirmation.</td>
    <td>`package.deprecate(root_id)` / `package.soft_delete(root_id)`.</td>
    <td>Lifecycle + Trash Domain Service.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Agent parity: Agent Package Library sayfasını veya browser downloadını beklemez. Catalog Query Service üzerinden type, output contract, rationale, data capability, timing policy, lifecycle ve visibility filtreleriyle paket arar; seçtiği exact revisionları kendi experiment checkpoint ve artifact provenanceına yazar. Agent yalnız kendi roots/revisionsını mutate eder; foreign source için Derive kullanır; publish/Trash restore yetkisi yoktur.</th>
  </tr>
</table>

# 10. Validation, Errors and Recovery Contract

<table>
  <tr>
    <th>Validation / error class</th>
    <th>Canonical / page error</th>
    <th>UI behavior</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>Filter/query validation</td>
    <td>PACKAGE_TYPE_INVALID; invalid facet value; malformed cursor.</td>
    <td>Do not silently substitute another type; show inline filter error and keep last valid result.</td>
    <td>Clear invalid selection or refresh permitted facets.</td>
  </tr>
  <tr>
    <td>Lifecycle</td>
    <td>PACKAGE_DELETED; lifecycle blocked; deprecated default-use blocked.</td>
    <td>Use/Create Revision/Delete action state updates from server projection.</td>
    <td>Restore via Admin Trash for soft-deleted root; select active replacement or derive/revise for deprecated root.</td>
  </tr>
  <tr>
    <td>Dependency</td>
    <td>PACKAGE_DEPENDENCY_UNRESOLVED; dependency cycle; `PACKAGE_TIMING_INCOMPATIBLE`.</td>
    <td>Detail shows dependency path and validation summary; Use disabled.</td>
    <td>Repair exact dependency in new revision/derived root; satisfy required data capability; rerun validation.</td>
  </tr>
  <tr>
    <td>Contract / schema</td>
    <td>OUTPUT_CONTRACT_INVALID; payload schema invalid; output names duplicate.</td>
    <td>Validation report links fields/paths; no publish.</td>
    <td>Fix revision draft; keep previous immutable revision unchanged.</td>
  </tr>
  <tr>
    <td>Authorization</td>
    <td>ACCESS_DENIED; OWNER_REQUIRED; PACKAGE_EDIT_FORBIDDEN; package_publish_admin_only; TRASH_ADMIN_ONLY.</td>
    <td>Action disabled when known, but server error always handled.</td>
    <td>Use allowed source, Derive, request owner/Admin support, or use Admin-only flow.</td>
  </tr>
  <tr>
    <td>Concurrency</td>
    <td>PACKAGE_REVISION_CONFLICT / 409.</td>
    <td>Stale banner; action submission is stopped; no optimistic overwrite.</td>
    <td>Reload; compare current revision; merge intentionally into new revision or derive.</td>
  </tr>
  <tr>
    <td>Export/import job</td>
    <td>JOB_FAILED; import dependency unresolved.</td>
    <td>Durable job status, diagnostic and retry button.</td>
    <td>Retry export; for import resolve dependencies then revalidate. Import stays DRAFT/BLOCKED.</td>
  </tr>
  <tr>
    <td>Not applicable metrics</td>
    <td>NOT_APPLICABLE performance projection.</td>
    <td>Show `Not applicable`, do not display 0 as performance.</td>
    <td>Choose Strategy Package filter/sort when performance comparison is intended.</td>
  </tr>
</table>

# 11. Lifecycle, Revisioning, Audit and Trash

## 11.1 Canonical lifecycle states

<table>
  <tr>
    <th>PackageRoot.root.lifecycle_state: active | deprecated | soft_deleted<br/>PackageRevision.revision.validation_state: pending | passed | warning | failed | stale<br/>PackageRevision.revision.approval_state: draft | approval_requested | approved | rejected<br/>PackageRevision.visibility_scope: private | explicitly_shared | published | system<br/><br/>These are independent facets. A display badge may summarize them but must not collapse them into one database enum.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Event</th>
    <th>Required behavior</th>
    <th>Historical / audit effect</th>
  </tr>
  <tr>
    <td>New revision publish</td>
    <td>Insert immutable revision N+1; atomically update root.current_revision_id after validation/concurrency pass.</td>
    <td>Old revision becomes superseded/current-history; any existing Strategy/Run/Agent manifest stays pinned to old exact revision.</td>
  </tr>
  <tr>
    <td>Derive</td>
    <td>Create a new root, owned by caller, from source revision snapshot.</td>
    <td>Source provenance retained; original root never mutated.</td>
  </tr>
  <tr>
    <td>Deprecate</td>
    <td>Keep root visible in controlled/history scope; remove from default new-use candidates.</td>
    <td>Audit records actor/reason/replacement reference if supplied; historical reproduction permitted by policy.</td>
  </tr>
  <tr>
    <td>Soft delete</td>
    <td>Set root lifecycle soft_deleted; remove active catalog/new-use/update availability; create Trash entry.</td>
    <td>Current and historical revisions, references and manifests retained for audit/reproducibility.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>Admin restores same root/current revision pointer to active context after policy checks.</td>
    <td>No new revision created by restore; audit `RESTORED` event.</td>
  </tr>
  <tr>
    <td>Permanent delete</td>
    <td>Admin-only Trash action; retention/policy gates enforced.</td>
    <td>Historical run/result manifest integrity must not be broken; if purge policy cannot preserve required evidence, refuse permanent delete.</td>
  </tr>
</table>

## 11.2 Audit event contract

<table>
  <tr>
    <th>Event</th>
    <th>Minimum audit fields</th>
  </tr>
  <tr>
    <td>PACKAGE_USED</td>
    <td>actor/principal, source package_root_id/revision_id, target type/id/revision/draft, compatibility decision, timestamp, correlation id.</td>
  </tr>
  <tr>
    <td>PACKAGE_DERIVED</td>
    <td>actor, source revision, new root/revision, requested name, change note, timestamp, provenance link.</td>
  </tr>
  <tr>
    <td>PACKAGE_REVISION_DRAFTED / PUBLISHED</td>
    <td>actor, root, base revision, expected head, new revision, content hash, validation summary ref, change note, correlation id.</td>
  </tr>
  <tr>
    <td>PACKAGE_VALIDATION_REQUESTED / COMPLETED</td>
    <td>actor/job, revision, test manifest, status, evidence artifact refs, error/warning summary.</td>
  </tr>
  <tr>
    <td>PACKAGE_APPROVAL_REQUESTED / APPROVED_PUBLISHED / REJECTED</td>
    <td>actor/approver, revision, evidence snapshot, reason, old/new approval/visibility state.</td>
  </tr>
  <tr>
    <td>PACKAGE_EXPORTED / IMPORTED</td>
    <td>actor, exact revision or input asset hash, artifact/job id, manifest hash, dependency resolution result.</td>
  </tr>
  <tr>
    <td>PACKAGE_DEPRECATED / soft_deleted / RESTORED / PERMANENTLY_DELETED</td>
    <td>actor, root, current revision, original location, lifecycle transition, Trash record id where relevant, timestamp.</td>
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
    <td>Canonical types</td>
    <td>Shows six sections and Type options including Trading Signal and Trade Log.</td>
    <td>Only Strategy, Indicator, Condition, Embedded System packages exist in Package Library. Trading Signal/Trade Log are external Mainboard Working Items.</td>
    <td>Remove two external rows/options from Package Library. Existing prototype entries are migrated/routed to external object views; do not add package enums.</td>
  </tr>
  <tr>
    <td>Status</td>
    <td>One filter combines Backtest Ready, Approved, Imported, Mapped.</td>
    <td>Lifecycle, validation, readiness, trust, approval and visibility are independent dimensions.</td>
    <td>Replace one generic Status filter with facets or a labeled status summary; retain simple UI presentation without collapsing persistence model.</td>
  </tr>
  <tr>
    <td>Filtering</td>
    <td>Local `packageGroups` array is filtered and sorted client-side.</td>
    <td>Role-aware server query/filter/search, cursor pagination, current facets and policy guards.</td>
    <td>Filter controls drive query parameters; browser cache is non-authoritative.</td>
  </tr>
  <tr>
    <td>Detail</td>
    <td>Free-text summary and small metadata grid.</td>
    <td>Root/revision identity, contracts, dependencies, validation, usage/provenance, permission and action projection.</td>
    <td>Expand detail into structured sections/tabs while preserving compact row + expand interaction.</td>
  </tr>
  <tr>
    <td>Metrics</td>
    <td>Indicator/Condition/ESP default metrics are zeros.</td>
    <td>Only Strategy Packages may expose linked-run performance projection; other types return null/not applicable.</td>
    <td>Do not produce fake performance values or allow misleading generic metric sort.</td>
  </tr>
  <tr>
    <td>Export</td>
    <td>Browser creates JSON Blob directly from demo object.</td>
    <td>Server creates authorized immutable revision manifest/export artifact; dependencies revalidated on import.</td>
    <td>Use async/durable export if artifact generation is non-trivial; export selected revision, not name-only row.</td>
  </tr>
  <tr>
    <td>Delete</td>
    <td>Removes local array item and adds demo Trash entry.</td>
    <td>Server policy -&gt; soft delete root -&gt; Trash/audit; history preserved; Admin-only restore/permanent delete.</td>
    <td>× becomes Move to Trash with confirmation and canonical response rehydrate.</td>
  </tr>
  <tr>
    <td>Use / derive</td>
    <td>Not shown as action.</td>
    <td>Use pins exact revision into target; foreign changes use Derive; owner/Admin creates revisions.</td>
    <td>Add typed action projection based on package type/target compatibility and policy.</td>
  </tr>
  <tr>
    <td>Embedded System</td>
    <td>Appears as generic package rows.</td>
    <td>ESP requires trusted resolver signature, adapter, test vectors and trust/registry state.</td>
    <td>Keep overview in generic catalog; route deep resolver management to page 9.</td>
  </tr>
</table>

# 13. Implementation Rules for Coding AI

- Package Library type enumunu yalnız `strategy`, `indicator`, `condition`, `embedded_system` olarak uygula. Trading Signal veya Trade Log için package type, section, API enum veya database column value ekleme.

- Katalog satırında stable `package_id` ve `current_revision_id` taşı. Name, section order veya displayed summary hiçbir commandin identitysi olamaz.

- Current Package Revision payloadını SQL UPDATE ile yerinde değiştirme. Her content, contract, dependency, semantic assignment veya validation configuration değişikliği immutable yeni revision üretir.

- Catalog list, search, sort, facet ve detail querylerini backendde role-aware uygula. Unauthorized resources istemciye gönderilip sonra CSS/JS ile gizlenmez.

- Package statusunu tek enumda birleştirme. lifecycle, validation, readiness, approval/publication, trust ve performance projectionı bağımsız modelle.

- Indicator, Condition veya ESP için Net Profit, ROMAD, Drawdown, Win Rate veya Trade Count sıfır uydurma. Uygulanmayan alan `null / Not applicable` olmalıdır.

- Use commandi exact `package_revision_id` pinlemelidir. Current/latest catalog lookupı Strategy, Backtest Run veya Agent experiment çalışırken implicit olarak yapılmaz.

- Foreign owner package için normal edit/revision commandi çalıştırma. Caller use edebilir veya source revisiondan new owned root Derive edebilir; Admin override ayrı policy ile uygulanır.

- Dependency graphı publish/use öncesi exact revision referanslarıyla çöz ve cycle detection yap. Cycle, deleted/untrusted/unresolved dependency veya timing incompatibilityyi UIya bırakma.

- Output contractta input types, output kinds, timeframe semantics, availability, closed-bar/intrabar requirement ve repaint/lookahead policy olmadan executable/usable state verme.

- Shared/published Packagee geçişi yalnız Admin `approve_and_publish` transactionı ile yap. Non-Admin draft/candidate/validation/approval request üretebilir fakat publish yapamaz.

- V18 Status dropdownundaki Backtest Ready, Approved, Imported ve Mapped label’larını persistence enumu olarak saklama; bunları doğru state facets/provenance projectionına eşle.

- Delete actionı normalde root-level soft delete olmalıdır. Deleted root yeni use veya revision kabul etmez; historical manifest ve results references değiştirilmez.

- Trash list/view/restore/permanent delete endpointleri yalnız Admin için server-side guarded olmalıdır. Ownerın delete hakkı restore veya permanent delete hakkı vermez.

- Detail UI Action projectionını backendden al ve client tarafında yalnız display amacıyla kullan. Server her actionda policy/lifecycle/current-head validationını tekrar uygular.

- Revision publish ve mutating lifecycle commandlerinde `expected_head_revision_id` / equivalent concurrency token kullan. Mismatchte 409 `PACKAGE_REVISION_CONFLICT` dön; silent last-write-wins uygulama.

- Export selected immutable revision + dependency manifest üzerinden üretilmelidir. Importta dependency unresolved ise target packagei DRAFT/BLOCKED bırak; hidden external live link kurma.

- Package Library browser açık değilken Agentın package discovery/use/derive/revision workflowu Tool Gateway/API üzerinden devam edebilmelidir. UI özel bypass veya automation zorunluluğu koyma.

- Rationale Family global shared-editing exceptionını yalnız Package Rationale Assignment scopeunda uygula; package payload, code, owner, dependency veya lifecyclee genişletme.

- V18deki signals/trade logs prototype satırlarını production migrationda External Signal / Trade Log working object cataloguna yönlendir; PackageRoota dönüştürme.

# 14. Acceptance Tests

<table>
  <tr>
    <th>Category</th>
    <th>Acceptance scenario</th>
    <th>Expected result</th>
  </tr>
  <tr>
    <td>Canonical types</td>
    <td>User opens Package Library after migration.</td>
    <td>Only Strategy, Indicator, Condition and Embedded System package sections/types are returned. Trading Signal/Trade Log are not returned by `GET /v1/packages`.</td>
  </tr>
  <tr>
    <td>Default list / policy</td>
    <td>User requests the initial catalog.</td>
    <td>API returns only own/shared/published/system policy-allowed current projections; private other-user drafts are absent.</td>
  </tr>
  <tr>
    <td>Filter query</td>
    <td>User selects Type=Indicator, Rationale=Reversal, Market=Multi.</td>
    <td>Server query uses stable filter values and returns matching permitted rows; no client-only global array is source of truth.</td>
  </tr>
  <tr>
    <td>External type rejection</td>
    <td>Client posts `type=trading_signal` to package list/create route.</td>
    <td>Server rejects with `PACKAGE_TYPE_INVALID` or canonical validation error; no PackageRoot created.</td>
  </tr>
  <tr>
    <td>Status separation</td>
    <td>A revision is validation PASSED but approval REQUESTED/private.</td>
    <td>Detail shows independent validation and approval/visibility facts; it is not incorrectly shown as shared published.</td>
  </tr>
  <tr>
    <td>Metric applicability</td>
    <td>User sorts Condition Packages by ROMAD.</td>
    <td>API/UI returns Not applicable / blocks sort for type scope; it does not rank fabricated zero values.</td>
  </tr>
  <tr>
    <td>Use exact pinning</td>
    <td>User attaches Indicator revision 14 to Strategy Draft. Later revision 15 becomes current.</td>
    <td>Strategy Draft keeps revision 14 reference until an explicit new draft/revision action changes it.</td>
  </tr>
  <tr>
    <td>Compatibility</td>
    <td>Condition requires intrabar tick capability; selected target data only offers 15m OHLCV.</td>
    <td>Use/Ready path is blocked with `PACKAGE_TIMING_INCOMPATIBLE`; detail explains required capability.</td>
  </tr>
  <tr>
    <td>Dependency cycle</td>
    <td>Publish attempt creates A -&gt; B -&gt; A dependency path.</td>
    <td>Server rejects publish; diagnostic identifies cycle path; UI preserves draft for repair.</td>
  </tr>
  <tr>
    <td>Foreign edit</td>
    <td>Supervisor opens another owner Condition Package.</td>
    <td>Create Revision/edit action is denied; Derive is available when view/use allowed; source is unchanged.</td>
  </tr>
  <tr>
    <td>Derive provenance</td>
    <td>User derives shared revision.</td>
    <td>New root owner=User and `derived_from_revision_id` points to exact source revision; source owner unchanged.</td>
  </tr>
  <tr>
    <td>Admin publish</td>
    <td>Supervisor requests approval for validated revision; Admin approves/publishes.</td>
    <td>Only Admin command atomically updates approval and shared publication state; audit has evidence snapshot/reason.</td>
  </tr>
  <tr>
    <td>Non-admin publish</td>
    <td>Agent calls approve/publish endpoint.</td>
    <td>Server returns authorization error; candidate/draft remains intact and Agent can continue other work.</td>
  </tr>
  <tr>
    <td>Concurrency</td>
    <td>Two actors publish from same base. First succeeds.</td>
    <td>Second receives 409 `PACKAGE_REVISION_CONFLICT`; no overwrite or silent merge occurs.</td>
  </tr>
  <tr>
    <td>Delete</td>
    <td>Owner soft deletes an active root.</td>
    <td>Root disappears from active catalog/new-use; Trash entry/audit record exists; historical manifests still resolve pinned revision.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>Admin restores soft-deleted root.</td>
    <td>Same root/current revision returns to active context; no new revision created; audit event exists.</td>
  </tr>
  <tr>
    <td>Trash policy</td>
    <td>User/Agent attempts restore or permanent delete.</td>
    <td>Server denies; only Admin can manage Trash.</td>
  </tr>
  <tr>
    <td>Export</td>
    <td>User exports exact revision.</td>
    <td>Export artifact includes immutable revision/dependency manifest; source package unchanged.</td>
  </tr>
  <tr>
    <td>Import unresolved</td>
    <td>Imported manifest references unavailable dependency.</td>
    <td>New local root/revision stays DRAFT/BLOCKED with diagnostic; system creates no hidden live link.</td>
  </tr>
  <tr>
    <td>Agent parity</td>
    <td>Browser is closed; Agent queries catalog and attaches exact revision to Agent Strategy Draft.</td>
    <td>Operation succeeds via Tool Gateway with policy and provenance; no UI/browser dependency exists.</td>
  </tr>
  <tr>
    <td>V18 alignment</td>
    <td>V18 local expanded row behavior is reimplemented.</td>
    <td>Production compact expand/collapse remains usable while detail is backed by root/revision projection and async state.</td>
  </tr>
</table>

# 15. Final Consistency Check

<table>
  <tr>
    <th>Check</th>
    <th>Result</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 precedence applied</td>
    <td>Yes. Module 7 and CR-01/CR-02 override prototype labels and old package categories.</td>
  </tr>
  <tr>
    <td>Trading Signal / Trade Log treated as Package types?</td>
    <td>No. They are explicitly excluded from canonical Package Library and routed to Add Outsource Signal / Mainboard working-object context.</td>
  </tr>
  <tr>
    <td>V18 vs Production distinction visible</td>
    <td>Yes. Prototype filters/status/local state and canonical server projection/lifecycle are separated under explicit headings and alignment table.</td>
  </tr>
  <tr>
    <td>Agent browser/session dependency avoided</td>
    <td>Yes. Catalog/use/derive/revision APIs are Tool Gateway accessible and continue without Package Library UI.</td>
  </tr>
  <tr>
    <td>Root/revision/snapshot integrity preserved</td>
    <td>Yes. Exact revision pinning, immutable revisions, dependency snapshots, content hashes and history are required.</td>
  </tr>
  <tr>
    <td>Role and Trash policy correct</td>
    <td>Yes. UI state is non-authoritative; Admin-only approve/publish and Trash restore/permanent delete remain server guarded.</td>
  </tr>
  <tr>
    <td>Rationale shared exception constrained</td>
    <td>Yes. It applies only to semantic assignment, not package payload/lifecycle/ownership.</td>
  </tr>
  <tr>
    <td>Future Dev leakage</td>
    <td>No. This page defines active Package Library behavior only; no Future Dev capability is presented as production active.</td>
  </tr>
  <tr>
    <td>Scope discipline</td>
    <td>Yes. Embedded resolver deep management, Create Package, Rationale editor, Strategy Details, Mainboard, Ready Check and Trash UI are not documented as separate page behavior.</td>
  </tr>
</table>
