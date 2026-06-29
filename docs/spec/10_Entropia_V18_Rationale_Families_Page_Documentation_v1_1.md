---
title: "Entropia V18 — Rationale Families Page Documentation v1.1"
page_number: 10
document_type: "Page implementation specification"
source_document: "Entropia_V18_Rationale_Families_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Rationale Families Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | PAGE DOCUMENTATION 10/22 | RATIONALE FAMILIES
> **Original DOCX footer:** Canonical page documentation | Production V1 alignment |

ENTROPIA V18

RATIONALE FAMILIES

Sayfa Dokümantasyonu 10/22 | Paylaşımlı semantik sınıflandırma, immutable Family revision, package assignment ve Agent ontology sözleşmesi

<table>
  <tr>
    <th>Kapsam sınırı: Bu belge yalnız Edit &gt; Rationale Families çalışma yüzeyini, Family kartlarını ve Package Rationale Assignment tablosunu kapsar. Package Librarynin genel katalog sayfası, Strategy Details içindeki zorunlu Rationale Family pickerı, Create Package / Pre-Check önerileri, Agent Workspace, Trash ve Panel ayrı sayfalardır; burada yalnız bu sayfanın onlarla olan veri, policy, lifecycle ve API bağlantısı anlatılır.</th>
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
    <td>Entropia V18 | Page Documentation 10/22 | Rationale Families | v1.1</td>
  </tr>
  <tr>
    <td>Belge amacı</td>
    <td>V18 arayüzündeki shared Rationale Family kartları ve Package Rationale Assignment tablosunu; Production V1 root/revision modeli, global shared-editing policy, soft delete/Trash, optimistic concurrency, atomic package reclassification ve Agent Tool/API parity ile birlikte implementasyon sözleşmesine dönüştürmek.</td>
  </tr>
  <tr>
    <td>Kapsam</td>
    <td>Edit menüsünden açılan RATIONALE FAMILIES sayfası; Family listesi, New Rationale Family inputu, Family card view/edit state’i, pastel presentation, assignment table, Unassigned davranışı, Add/Edit/Remove/Save/Cancel/Save Assignment Changes komutları.</td>
  </tr>
  <tr>
    <td>Kapsam dışı</td>
    <td>Generic Package Library filtre/kart düzeni; Strategy Details tüm alanları; Trading Signal/Trade Log ekranları; Pre-Check; Results; Trash ekranı; Agent Workspace sohbeti. Bu alanlar yalnız dependency veya referans bağlamında anılır.</td>
  </tr>
  <tr>
    <td>Primary canonical source</td>
    <td>Master Technical Reference v1.0: Module 6 - Rationale Families: Ortak Strateji Mantığı Sınıflandırması; Canonical Integration: CR-01 semantic classification rule.</td>
  </tr>
  <tr>
    <td>Cross-cutting Master sources</td>
    <td>Module 0 (UI/backend/Agent sınırı), Module 1 (role/policy), Module 2 (root-revision lifecycle), Module 3 (soft delete/Trash), Module 7 (Package revisions), Module 10 (Strategy Context required family), Module 12 (Ready Check), Module 19-20 (API, event, durable state principles).</td>
  </tr>
  <tr>
    <td>V18 HTML source area</td>
    <td>Edit menu item `Rationale Families`; `rationaleFamilies` seed array; `renderRationaleFamiliesPage`; `renderRationaleFamilyCard`; `renderRationalePackageAssignmentRows`; add/edit/remove/save functions; `saveRationaleAssignments`; rationale card/grid CSS.</td>
  </tr>
  <tr>
    <td>Writing standard</td>
    <td>Handoff v1.1 Section 5 locked page template; 2.3 Position Entry Logic example for explanatory and implementation depth.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Canonical Rule: Rationale Family semantic bir sınıflandırmadır. Target nesnenin package typeını, entry/exit logicini, risk ayarını, order executionını veya backtest matematiğini değiştirmez. Trading Signal ve Trade Log Package Library package type değildir; bu sınıflandırma onları package türüne dönüştüremez.</th>
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
    <td>Family kartları</td>
    <td>M6 §3-6; root/revision, shared edit, lifecycle, color policy.</td>
    <td>`rationaleFamilies`, `renderRationaleFamilyCard`, Edit/Remove functions.</td>
    <td>M1 policy, M2 versioning, M3 Trash.</td>
    <td>Production string identity yerine `family_root_id + current_revision_id` kullanır.</td>
  </tr>
  <tr>
    <td>New Family</td>
    <td>M6 §4.2, §10.1, API create command.</td>
    <td>`newRationaleFamilyName`; `+ Add Family`.</td>
    <td>Agent Tool Gateway, audit stream.</td>
    <td>Family Name zorunludur; add command stable root + revision 1 üretir.</td>
  </tr>
  <tr>
    <td>Family edit/rename</td>
    <td>M6 §4.3, §6.2, §10.3.</td>
    <td>Inline edit card; `Save`, `Cancel`; alias map.</td>
    <td>Revision history, Strategy/Run manifest.</td>
    <td>Rename rootu değiştirmez; new immutable revision ve optimistic concurrency zorunludur.</td>
  </tr>
  <tr>
    <td>Package assignment</td>
    <td>M6 §7, §10.2, §11.2.</td>
    <td>Indicator/Condition rows, select, `Save Assignment Changes`.</td>
    <td>M7 Package revision, M10 Strategy use, M12 Ready Check.</td>
    <td>Batch atomiktir; her değişen package için new package revision üretir.</td>
  </tr>
  <tr>
    <td>Delete/restore</td>
    <td>M6 §4.4, M3.</td>
    <td>`Remove`; local Trash entry.</td>
    <td>Admin-only Trash route.</td>
    <td>Soft delete cascade delete yapmaz. Restore/purge yalnız Admin.</td>
  </tr>
  <tr>
    <td>Agent access</td>
    <td>M0 §5-6, M6 §9.4.</td>
    <td>V18 UI demo may simulate Agent role.</td>
    <td>Agent runtime, Tool Gateway, checkpoint/artifact.</td>
    <td>Agent UIye tıklamadan same command/service capability kullanır.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kesin Kavramsal Ayrımlar

Rationale Families; Strategy, Package ve araştırma artefactlarının hangi piyasa mantığına, davranış ailesine veya araştırma yaklaşımına hizmet ettiğini anlatan shared semantic registrydir. Bu sayfa bir etiket bulutu, kişisel klasör, role grubu veya trading engine ayar formu değildir. Aynı kavramı insan ve Agent tarafından tutarlı biçimde bulmayı, filtrelemeyi, karşılaştırmayı ve tarihsel olarak yeniden açıklamayı sağlar.

<table>
  <tr>
    <th>Research hypothesis / package idea<br/>  -&gt; Rationale Family (shared semantic catalog)<br/>  -&gt; Package revision classification / Strategy revision snapshot<br/>  -&gt; Ready Check / Backtest manifest preserves selected snapshot<br/>  -&gt; Result, portfolio diversity and Agent research can query the same stable family root</th>
  </tr>
</table>

## 1.1 Kesin terimler

<table>
  <tr>
    <th>Terim</th>
    <th>Canonical anlam</th>
    <th>Ne değildir / uygulanacak sınır</th>
  </tr>
  <tr>
    <td>Rationale Family</td>
    <td>Ortak strateji mantığı ailesi; market davranışı, hipotez yönü veya işlevsel yaklaşımı tanımlar.</td>
    <td>Package type, market, timeframe, user group, permission level veya backtest inputu değildir.</td>
  </tr>
  <tr>
    <td>Subfamily</td>
    <td>Family altındaki daha dar anlatımsal ayrım. Örn. Reversal altında VWAP Reversion.</td>
    <td>Bağımsız permission scope, yeni root veya hard engine rule değildir.</td>
  </tr>
  <tr>
    <td>Compatible Output Type</td>
    <td>Family ile anlamlı ilişki kurabilen outputların advisory listesi.</td>
    <td>Katı runtime enumu veya Agentı yeni output keşfinden alıkoyan validation gate değildir.</td>
  </tr>
  <tr>
    <td>Family Root</td>
    <td>Aile adından bağımsız, kalıcı mantıksal kimlik.</td>
    <td>Kartta görünen display name stringi değildir.</td>
  </tr>
  <tr>
    <td>Family Revision</td>
    <td>Bir Family içeriğinin immutable sürümü.</td>
    <td>Geçmişi ezerek yapılan in-place update değildir.</td>
  </tr>
  <tr>
    <td>Family Snapshot</td>
    <td>Bir package/strategy/backtest manifestine pinlenen tarihsel Family root + revision bilgisi.</td>
    <td>Her zaman current karta bakarak yeniden türetilen geçici display stringi değildir.</td>
  </tr>
  <tr>
    <td>Package Rationale Assignment</td>
    <td>Bir package revisionının Family root/revision ile semantik bağlantısı.</td>
    <td>Package kodunu, parametrelerini, ownerını veya execution davranışını değiştiren işlem değildir.</td>
  </tr>
  <tr>
    <td>Shared Editing Exception</td>
    <td>Bu sayfada normal owner-based modify kuralının bilinçli istisnası.</td>
    <td>Sistemde her resourceun herkesçe düzenlenebileceği genel yetki kuralı değildir.</td>
  </tr>
</table>

## 1.2 Sistem ilişkisi ve sınırlar

<table>
  <tr>
    <th>Bağlı alan</th>
    <th>Rationale Families davranışı</th>
    <th>Bu sayfanın sınırı</th>
  </tr>
  <tr>
    <td>Strategy Details</td>
    <td>Strategy Context içindeki Rationale Family * yalnız ACTIVE roots gösterir; saved Strategy revision root + selected revision snapshotını taşır.</td>
    <td>Strategy formunun diğer fieldları veya entry logic graphı burada tanımlanmaz.</td>
  </tr>
  <tr>
    <td>Package Library</td>
    <td>Current package projection, Family root id üzerinden filter/join edilir. Unassigned packageler görünür kalır.</td>
    <td>Package catalogun own/shared/published policy detayları ayrı Package Library belgesindedir.</td>
  </tr>
  <tr>
    <td>Create Package / Pre-Check</td>
    <td>Candidate code veya natural-language prompt için suggested family listesi dönebilir.</td>
    <td>Öneri otomatik Family create ya da package assignment mutation yapmaz.</td>
  </tr>
  <tr>
    <td>Backtest / Results</td>
    <td>Run manifest historical Family snapshotsını taşıyabilir; rename eski resultı değiştirmez.</td>
    <td>Rationale seçimi performance calculationı veya run engine davranışını değiştirmez.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Ontology/catalog query, family create/revise/assign commands Tool Gateway üzerinden çağrılabilir.</td>
    <td>Lab Assistant chat veya browser Agentın zorunlu çalışma yolu değildir.</td>
  </tr>
  <tr>
    <td>Trash</td>
    <td>Family soft delete sonrası ACTIVE listeden çıkar; past package/strategy/history korunur.</td>
    <td>Trash list/restore/purge UI burada değil, Admin-only Trash sayfasındadır.</td>
  </tr>
</table>

# 2. Erişim, Görünürlük, Ownership ve Server-Side Policy

V18de `canManageRationaleFamilies()` ve `canEditRationaleAssignments()` fonksiyonları bütün demo roller için `true` döndürür. Productionda bu görünür davranış, global shared-editing exception olarak korunur; ancak Guest ile authenticated User birbirinden ayrılır ve server-side policy her commandde tekrar uygulanır. Created By sadece provenance bilgisidir; edit, remove veya assignment save yetkisini sınırlandırmaz.

<table>
  <tr>
    <th>Principal / role</th>
    <th>Page list/view/use</th>
    <th>Family create / edit / soft delete</th>
    <th>Assignment save</th>
    <th>Trash / restore / purge</th>
  </tr>
  <tr>
    <td>Guest / anonymous</td>
    <td>Page doğrudan erişimde authentication required; active registry veya assignment tablosu dönmez.</td>
    <td>No.</td>
    <td>No.</td>
    <td>No.</td>
  </tr>
  <tr>
    <td>Registered User</td>
    <td>ACTIVE Family kartlarını ve allowed package assignment projectionını görür/kullanır.</td>
    <td>Yes. Own/other Family fark etmez; shared exception.</td>
    <td>Yes. Own/other package root fark etmez, semantic assignment scope ile sınırlı.</td>
    <td>No.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Shared registryyi görür/kullanır.</td>
    <td>Yes. Normal owner kuralı burada uygulanmaz.</td>
    <td>Yes.</td>
    <td>No.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm visible state ve audit-authorized views.</td>
    <td>Yes.</td>
    <td>Yes.</td>
    <td>Only Admin: Admin Trash view, restore, permanent delete.</td>
  </tr>
  <tr>
    <td>Agent (system actor)</td>
    <td>Runtime service identity ile catalog query/use. UI login gerekmez.</td>
    <td>Yes, policy allowed; own/other Family fark etmez.</td>
    <td>Yes, but only semantic assignment mutation; package logic ownership remains separate.</td>
    <td>No.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Canonical Rule: Rationale Family endpointsinde generic `can_modify_object(owner)` veya `is_current_owner` policysi kullanılmayacaktır. `can_manage_rationale_families(actor)` ve `can_edit_rationale_assignments(actor)` aktif Admin, Supervisor, User ve Agent için true döner. Restore ve permanent delete bu exceptiona dahil değildir; yalnız Admin gerçekleştirebilir.</th>
  </tr>
</table>

Policy boundary: Package Rationale Assignment shared olsa bile package code, parameter, data binding, publication, approval, deprecate veya normal package owner değişikliği shared edit kapsamına girmez.

# 3. V18 Interface Behavior - Yerleşim, Navigasyon ve Görünür Bileşenler

V18de sayfa Edit menüsü altındaki Rationale Families itemı ile açılır. Generic page shell page title alanında `RATIONALE FAMILIES` gösterir. İçerik üstte shared-editing açıklaması, altında masaüstünde iki kolonlu management paneli, mobil/dar ekranda tek kolonlu düzen içerir. Sol taraf Family listesi; sağ taraf Package Rationale Assignment tablosudur.

<table>
  <tr>
    <th>Bölge / bileşen</th>
    <th>V18de görünür davranış ve metin</th>
    <th>Production V1 yorum / sayfa kapsamı</th>
  </tr>
  <tr>
    <td>Menu entry</td>
    <td>Edit &gt; Rationale Families.</td>
    <td>Dedicated Rationale Families route/page. Route visibility UXdir; backend policy source of truthdur.</td>
  </tr>
  <tr>
    <td>Page intro</td>
    <td>&quot;Rationale Families are a shared-editing workspace ... Every role can edit and save this shared assignment table.&quot;</td>
    <td>Shared exception açıklaması korunur. Guest için page render edilmez; server returns policy error.</td>
  </tr>
  <tr>
    <td>Left column title</td>
    <td>RATIONALE FAMILY LIST.</td>
    <td>Current ACTIVE Family roots projectionı.</td>
  </tr>
  <tr>
    <td>New Family row</td>
    <td>Label `New Rationale Family`; empty input; `+ Add Family` button. V18de yıldız/placeholder yok.</td>
    <td>Production label `New Rationale Family *`; server validation. Help text and disabled/loading states below.</td>
  </tr>
  <tr>
    <td>Family cards</td>
    <td>Pastel background; display fields Family Name, Subfamilies, Compatible Output Types, Created By; actions Edit and Remove.</td>
    <td>Current root + revision projection. Color root-level persistent display metadata; Created By provenance only.</td>
  </tr>
  <tr>
    <td>Inline editor</td>
    <td>Card is replaced by `EDIT RATIONALE FAMILY` editor with three inputs and Cancel/Save.</td>
    <td>Edit operates against current revision + ETag; Save creates immutable Family revision.</td>
  </tr>
  <tr>
    <td>Right column title</td>
    <td>PACKAGE RATIONALE ASSIGNMENT.</td>
    <td>Current rationale-assignable package projection; initial V18 scope Indicator + Condition packages.</td>
  </tr>
  <tr>
    <td>Assignment note</td>
    <td>&quot;Select the appropriate shared Rationale Family for each package, then save the assignment changes. Every role can edit and save this shared assignment table.&quot;</td>
    <td>Stage edits locally; submit only changed rows in atomic batch command.</td>
  </tr>
  <tr>
    <td>Assignment table</td>
    <td>Columns Package Type, Package Name, Current Rationale Family. Select options are Unassigned + current in-memory family names.</td>
    <td>Options use ACTIVE family root ids; label uses current revision display name. Deleted roots unavailable for new assignment.</td>
  </tr>
  <tr>
    <td>Save Assignment Changes</td>
    <td>Visible because V18 permission function returns true.</td>
    <td>Enabled only when staged diff exists and no save is in flight; writes a single atomic batch.</td>
  </tr>
  <tr>
    <td>Modal/popup</td>
    <td>No page-specific modal, ⓘ popover, search/filter bar, pagination, confirmation dialog or revision history visible in V18.</td>
    <td>Production adds destructive confirmation and stale-conflict recovery UI. Revision history is data-supported; inline history view is out of current V18 scope.</td>
  </tr>
</table>

## 3.1 V18 initial Family cards and production seed alignment

<table>
  <tr>
    <th>V18 seed Family</th>
    <th>Subfamilies shown</th>
    <th>Compatible Output Types shown</th>
    <th>Production alignment</th>
  </tr>
  <tr>
    <td>Reversal / Mean Reversion</td>
    <td>Range Reversion; Panic Reversion; VWAP Reversion; Statistical Reversion</td>
    <td>Directional Signal; Oversold / Overbought Zone; Distance from Mean</td>
    <td>Keep as ACTIVE seed; Family root identity is stable, display name can revise.</td>
  </tr>
  <tr>
    <td>Trend / Directional Regime</td>
    <td>Trend Continuation; Direction State; Pullback Continuation</td>
    <td>Color / Direction State; Trend State; Moving Average Slope</td>
    <td>Keep as ACTIVE seed.</td>
  </tr>
  <tr>
    <td>Breakout / Volatility Expansion</td>
    <td>Range Break; Volume Breakout; Momentum Expansion</td>
    <td>Breakout Signal; Volume Confirmation; Range Exit</td>
    <td>Keep as ACTIVE seed.</td>
  </tr>
  <tr>
    <td>Volatility / Regime</td>
    <td>Compression; Expansion; High Volatility; Low Volatility</td>
    <td>Regime Label; Volatility State; ATR Threshold</td>
    <td>Keep as ACTIVE seed.</td>
  </tr>
  <tr>
    <td>External Signal / Trade Log</td>
    <td>Copy Trading; Imported Record; Trade Log</td>
    <td>Trade Record; Signal Event; External Direction</td>
    <td>Keep semantic card only; does not make Trading Signal/Trade Log a Package Library package type.</td>
  </tr>
  <tr>
    <td>Embedded System / TA Resolver</td>
    <td>Not present as a V18 Family card.</td>
    <td>Referenced by V18 Embedded System Package metadata.</td>
    <td>Production seed correction: create as ACTIVE Family. It remains shared-editable; no hidden system lock.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Implementation Alignment Note: V18 Embedded System Package metadata refers to `Embedded System / TA Resolver`, but the visible V18 Family seed list does not contain this card. Production V1 must resolve the mismatch by seeding that ACTIVE Family. This document adopts the Master-selected direction: add the seed Family; do not silently remove the metadata or fake a string-only option.</th>
  </tr>
</table>

## 3.2 V18 assignment table rows and dropdown options

<table>
  <tr>
    <th>V18 row</th>
    <th>Package Type</th>
    <th>V18 default current assignment</th>
    <th>Dropdown contents</th>
  </tr>
  <tr>
    <td>SMOOTHED HEIKEN ASHI</td>
    <td>Indicator Package</td>
    <td>Trend / Directional Regime (generic indicator default metadata).</td>
    <td>Unassigned; Reversal / Mean Reversion; Trend / Directional Regime; Breakout / Volatility Expansion; Volatility / Regime; External Signal / Trade Log.</td>
  </tr>
  <tr>
    <td>Predictive Ranges</td>
    <td>Indicator Package</td>
    <td>Trend / Directional Regime (generic indicator default metadata).</td>
    <td>Same as above; V18 option list is generated from in-memory Family array.</td>
  </tr>
  <tr>
    <td>Resistance Proximity Trigger Condition</td>
    <td>Condition Package</td>
    <td>Reversal / Mean Reversion (generic condition default metadata).</td>
    <td>Same as above.</td>
  </tr>
  <tr>
    <td>Volatility Compression Condition</td>
    <td>Condition Package</td>
    <td>Reversal / Mean Reversion (generic condition default metadata).</td>
    <td>Same as above.</td>
  </tr>
</table>

V18 observation: Only Indicator and Condition rows render on this page. Strategy, Embedded System Package, Trading Signal and Trade Log rows are not rendered in this table. Production may support additional rationale-assignable package types at the model level, but the initial UI should not expand scope without an explicit design change.

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen</th>
    <th>Varsayılan / visible state</th>
    <th>Activation / transition</th>
    <th>Disabled, loading, stale, error and payload effect</th>
  </tr>
  <tr>
    <td>Page shell</td>
    <td>Authenticated User/Supervisor/Admin page; Agent runtime can use equivalent API without UI.</td>
    <td>Edit &gt; Rationale Families navigation or direct permitted route.</td>
    <td>Guest access returns AUTHENTICATION_REQUIRED. UI visibility cannot substitute server policy.</td>
  </tr>
  <tr>
    <td>New Family input</td>
    <td>Empty string. V18 has no placeholder.</td>
    <td>User types normalized candidate name.</td>
    <td>Production Add disabled for trimmed empty/invalid name; submit payload includes display_name and optional fields only if provided by API client.</td>
  </tr>
  <tr>
    <td>+ Add Family</td>
    <td>V18 visibly enabled even with empty field; handler no-ops on blank/duplicate.</td>
    <td>Production enabled only when client validation passes and no create request in flight.</td>
    <td>Loading prevents duplicate command; server duplicates/invalid text return structured validation. Success hydrates new root/current revision.</td>
  </tr>
  <tr>
    <td>Family card view</td>
    <td>Every ACTIVE Family shows a pastel card.</td>
    <td>Card becomes edit mode only after Edit.</td>
    <td>Deleted root removed from active list. Color remains presentation metadata; no engine payload effect.</td>
  </tr>
  <tr>
    <td>Family inline editor</td>
    <td>Hidden until Edit; replaces one card.</td>
    <td>Open edit with current revision id + row_version/ETag.</td>
    <td>Save disabled if required name invalid or request in flight. Stale response leaves local edits visible and offers reload/compare/reapply, not overwrite.</td>
  </tr>
  <tr>
    <td>Cancel</td>
    <td>Visible in edit mode.</td>
    <td>Discard unsaved local change and restore current server projection.</td>
    <td>No persistence, no audit, no revision, no engine payload effect.</td>
  </tr>
  <tr>
    <td>Remove</td>
    <td>V18 immediately soft-deletes from local UI.</td>
    <td>Production requires explicit destructive confirmation and current ETag.</td>
    <td>Loading pending delete; 409 requires reload. Success produces root.lifecycle_state=soft_deleted + Trash entry; no cascade deletion.</td>
  </tr>
  <tr>
    <td>Assignment selects</td>
    <td>Render current package assignment; V18 permits Unassigned.</td>
    <td>Each select change marks staged table dirty.</td>
    <td>No package mutation until Save Assignment Changes. Deleted Family cannot be selected for new assignment.</td>
  </tr>
  <tr>
    <td>Save Assignment Changes</td>
    <td>Visible to all production actor types covered by shared exception.</td>
    <td>Enabled only when staged change set nonempty and all rows valid/current.</td>
    <td>Single atomic request; any stale/deleted/missing row rejects full batch. Success returns new package revisions and warnings.</td>
  </tr>
  <tr>
    <td>Empty Family list</td>
    <td>No explicit V18 empty-state text.</td>
    <td>All active roots deleted or no seed data.</td>
    <td>Production shows prescribed empty state; Strategy creation cannot use a missing Family and Ready Check will block Strategy without required Family.</td>
  </tr>
  <tr>
    <td>Empty assignment table</td>
    <td>No explicit V18 empty-state text.</td>
    <td>No visible rationale-assignable package.</td>
    <td>Production shows prescribed empty state; Save button disabled, no empty batch sent.</td>
  </tr>
</table>

## 4.1 State layers and source of truth

<table>
  <tr>
    <th>Layer</th>
    <th>Example on this page</th>
    <th>Authority / persistence rule</th>
  </tr>
  <tr>
    <td>Frontend transient state</td>
    <td>New Family input text; currently edited card id; unsaved inline values; staged assignment changes.</td>
    <td>Browser-only working state. Refresh may discard it; never source of truth.</td>
  </tr>
  <tr>
    <td>Current projection</td>
    <td>Active Family cards, display color, current package assignment table.</td>
    <td>Read model derived from current roots/revisions; role-aware server query.</td>
  </tr>
  <tr>
    <td>Mutable command intent</td>
    <td>POST create payload, revision draft payload, batch assignment change list with expected_table_version.</td>
    <td>Short-lived command input. It becomes durable only after server validation + transaction.</td>
  </tr>
  <tr>
    <td>Immutable Family revision</td>
    <td>Family display name, normalized name, subfamily list, compatible output type list, change note, provenance/hash.</td>
    <td>Historical record; change creates new revision, not overwrite.</td>
  </tr>
  <tr>
    <td>Immutable Package revision</td>
    <td>Assigned family root/revision snapshot and rationale display snapshot.</td>
    <td>Every changed assignment produces new package revision; old Strategy/Run remains pinned.</td>
  </tr>
  <tr>
    <td>Historical manifest / audit</td>
    <td>Strategy revision, Backtest Run manifest, shared-edit audit event, Trash snapshot.</td>
    <td>Durable historical truth; later rename/delete does not mutate it.</td>
  </tr>
</table>

# 5. Field Contract Matrix

`*` işareti Production V1 zorunluluğunu ifade eder. V18de sadece Strategy Contextte Family picker `*` ile görünür; Rationale Families pageindeki New Family ve inline editor labels V18de yıldız taşımaz. Production formu bu sayfa üzerinde Family Namei açıkça `*` ile işaretlemelidir. Requiredness UI etiketiyle sınırlı değildir: API validation, Agent tool schema ve concurrency-aware save contract aynı kuralı uygular.

<table>
  <tr>
    <th>Alan / control</th>
    <th>UI type and V18 default</th>
    <th>Requiredness / options</th>
    <th>Production payload and validation</th>
    <th>Dependency / state preservation</th>
  </tr>
  <tr>
    <td>New Rationale Family *</td>
    <td>Single-line text input; V18 default empty; no placeholder.</td>
    <td>Always required for add. 2-120 visible chars after trim.</td>
    <td>`display_name`; trim, whitespace collapse, control-char reject, normalized case-insensitive uniqueness.</td>
    <td>Duplicate active/deleted reserved name blocks create. Draft text remains visible after error.</td>
  </tr>
  <tr>
    <td>Family Name * (edit)</td>
    <td>Single-line text; seeded current display name.</td>
    <td>Always required. Same 2-120 validation.</td>
    <td>New Family revision `display_name`, `normalized_name`, expected_head_revision_id/ETag.</td>
    <td>Rename preserves root id and display_color. Existing historical snapshots remain unchanged.</td>
  </tr>
  <tr>
    <td>Subfamilies</td>
    <td>Single-line V18 text; default current value or empty.</td>
    <td>Optional. V18 stores comma-text; Production accepts comma/newline list.</td>
    <td>`subfamilies[]`; max 100 items, each max 160 chars; normalize/trim/drop empty values.</td>
    <td>Blank is valid empty list. Changing creates Family revision.</td>
  </tr>
  <tr>
    <td>Compatible Output Types</td>
    <td>Single-line V18 text; default current value or empty.</td>
    <td>Optional advisory list.</td>
    <td>`compatible_output_types[]`; max 100 items, each max 160 chars.</td>
    <td>Mismatch to Package output contract produces warning, not hard reject. Changing creates Family revision.</td>
  </tr>
  <tr>
    <td>Created By</td>
    <td>Read-only card field; V18 fallback Admin.</td>
    <td>System populated; never required user input.</td>
    <td>`created_by_actor_id` on root/revision projection.</td>
    <td>Provenance only; does not control edit/remove/save rights.</td>
  </tr>
  <tr>
    <td>Pastel Color</td>
    <td>No user field; auto selected from V18 palette.</td>
    <td>System assigned; no user selection.</td>
    <td>`display_color` on Family root.</td>
    <td>Stable across edit/rename/reload; presentation only; no logic/engine impact.</td>
  </tr>
  <tr>
    <td>Edit</td>
    <td>Button per active card.</td>
    <td>Available to Admin/Supervisor/User/Agent under shared exception.</td>
    <td>GET detail/current revision then open local editor.</td>
    <td>No mutation. Current ETag/row_version is required for subsequent save.</td>
  </tr>
  <tr>
    <td>Cancel</td>
    <td>Button in inline edit card.</td>
    <td>Always available when editor open.</td>
    <td>No payload.</td>
    <td>Discard transient changes only; current server card rerenders.</td>
  </tr>
  <tr>
    <td>Save</td>
    <td>Button in inline edit card.</td>
    <td>Family Name required; optional metadata may be blank.</td>
    <td>`POST /v1/rationale-families/{id}/revisions` with expected_head_revision_id; HTTP transport: If-Match/ETag; content hash; optional change note.</td>
    <td>Creates immutable revision; no in-place mutation. 409 keeps edit context for recovery.</td>
  </tr>
  <tr>
    <td>Remove</td>
    <td>Button per active card.</td>
    <td>All four active actor types can soft delete shared Family.</td>
    <td>`DELETE /v1/rationale-families/{id}` with expected row version.</td>
    <td>active -&gt; soft_deleted, Trash entry + audit. Does not delete packages/strategies/runs.</td>
  </tr>
  <tr>
    <td>Package Type</td>
    <td>Read-only assignment table cell.</td>
    <td>V18 shows Indicator Package or Condition Package.</td>
    <td>Server projection field.</td>
    <td>No user payload; initial UI scope only rationale-assignable types.</td>
  </tr>
  <tr>
    <td>Package Name</td>
    <td>Read-only assignment table cell.</td>
    <td>Visible current package name.</td>
    <td>`package_root_id` / current revision returned separately; display string not identity.</td>
    <td>Rename/revision history must not break selected row identity.</td>
  </tr>
  <tr>
    <td>Current Rationale Family</td>
    <td>Select; V18 options: Unassigned plus in-memory Family names.</td>
    <td>Not required. Unassigned is valid. Active Family roots are valid targets.</td>
    <td>Change row: `package_root_id`, expected_head_revision_id, `rationale_family_id|null`, expected selected Family current revision where non-null.</td>
    <td>Staged only until batch save. Deleted Family cannot be newly selected. Unassigned sets family fields null in new package revision.</td>
  </tr>
  <tr>
    <td>Save Assignment Changes</td>
    <td>Action button below table.</td>
    <td>Required only when there are staged diffs; disabled otherwise.</td>
    <td>Atomic `POST /v1/package-rationale-assignments:batch` with table ETag/version and changed rows.</td>
    <td>All-or-nothing. Successful changed rows receive new Package revisions; original package owner remains unchanged.</td>
  </tr>
</table>

## 5.1 V18 dropdown catalogue and Production V1 options

<table>
  <tr>
    <th>Dropdown</th>
    <th>V18 options</th>
    <th>Production V1 contract</th>
  </tr>
  <tr>
    <td>Current Rationale Family</td>
    <td>`Unassigned` plus dynamically generated current `rationaleFamilies` display names: Reversal / Mean Reversion; Trend / Directional Regime; Breakout / Volatility Expansion; Volatility / Regime; External Signal / Trade Log.</td>
    <td>`Unassigned` + ACTIVE Family root current revision labels only. Values are `null` or stable `rationale_family_id`; display labels must never be persisted as relationship keys. Production seed additionally includes Embedded System / TA Resolver.</td>
  </tr>
  <tr>
    <td>Strategy Context Rationale Family (cross-page dependency)</td>
    <td>V18 uses `Choose Rationale Family` placeholder plus current family names. It is not rendered inside this page.</td>
    <td>Required `*` for Strategy revision. Only ACTIVE roots. Saved Strategy revision pins family root id + selected Family revision id. Deleted Family is not selectable for new Strategy, but historical snapshots remain.</td>
  </tr>
</table>

# 6. Information Content Catalog, Placeholder, Helper, Warning, Toast and Error Text

V18 Rationale Families pageinde doğrudan ⓘ info button veya page-specific popup bulunmaz. Aşağıdaki catalog iki parçadan oluşur: mevcut V18de olmayan bilgilerin açık kaydı ve Production V1de dokümantasyon standardını karşılamak üzere eklenecek contextual help metinleri. Bu ek help controls Implementation Decisiondır; Masterın canonical data/policy kararlarını değiştirmez.

## 6.1 V18 existing ⓘ control status

<table>
  <tr>
    <th>UI area</th>
    <th>V18 ⓘ status</th>
    <th>Documentation result</th>
  </tr>
  <tr>
    <td>New Rationale Family input</td>
    <td>No ⓘ control.</td>
    <td>No existing V18 popover text to preserve.</td>
  </tr>
  <tr>
    <td>Family card display fields</td>
    <td>No ⓘ control.</td>
    <td>No existing V18 popover text to preserve.</td>
  </tr>
  <tr>
    <td>Inline editor fields</td>
    <td>No ⓘ control.</td>
    <td>No existing V18 popover text to preserve.</td>
  </tr>
  <tr>
    <td>Package Rationale Assignment table</td>
    <td>No ⓘ control.</td>
    <td>No existing V18 popover text to preserve; its visible explanatory note is transcribed below.</td>
  </tr>
</table>

## 6.2 Production V1 contextual help panels - Implementation Decision

<table>
  <tr>
    <th>Info key / field</th>
    <th>Panel title</th>
    <th>Exact UI text</th>
  </tr>
  <tr>
    <td>rationaleFamilyInfo / New Rationale Family</td>
    <td>Rationale Family</td>
    <td>A Rationale Family is a shared semantic classification for a market behavior, research hypothesis or reusable trading logic. It helps people and Agents find related Strategies and Packages. It does not create entry, exit, stop, sizing, execution or market-data rules by itself. Use a clear family-level name such as “Liquidity Sweep Reversal”.</td>
  </tr>
  <tr>
    <td>familyNameInfo / Family Name *</td>
    <td>Family Name</td>
    <td>Enter the visible name of this shared Family. The name is normalized for duplicate checks, but the system stores a stable Family root ID behind it. Renaming creates a new Family revision; it does not rewrite historical Strategy, Package or Backtest snapshots. A name must be 2-120 visible characters and unique after case-insensitive normalization.</td>
  </tr>
  <tr>
    <td>subfamiliesInfo / Subfamilies</td>
    <td>Subfamilies</td>
    <td>List narrower variants that belong under this Family. Separate items with commas or new lines. Examples: “VWAP Reversion” and “Panic Reversion”. Subfamilies improve discovery and explanation; they are not permission scopes, executable rules or independent Family roots.</td>
  </tr>
  <tr>
    <td>compatibleOutputsInfo / Compatible Output Types</td>
    <td>Compatible Output Types</td>
    <td>List output types that are normally meaningful for this Family, such as “Directional Signal” or “Regime Label”. This list is advisory. A Package with a novel output type may still be assigned; the system shows a warning instead of blocking research or Agent discovery.</td>
  </tr>
  <tr>
    <td>createdByInfo / Created By</td>
    <td>Created By</td>
    <td>Created By identifies the actor that first created the Family root. It is provenance information only. Rationale Families are a shared-editing exception: Admin, Supervisor, User and Agent can edit or remove a Family regardless of Created By. Trash restore and permanent delete remain Admin-only.</td>
  </tr>
  <tr>
    <td>sharedEditingInfo / Intro note</td>
    <td>Shared Editing</td>
    <td>This page is a deliberate shared-editing workspace. The normal owner-only rule does not apply to Family cards or semantic Package Rationale Assignments. This exception does not grant permission to change package code, parameters, approval state, data bindings or execution rules.</td>
  </tr>
  <tr>
    <td>assignmentInfo / Current Rationale Family</td>
    <td>Package Rationale Assignment</td>
    <td>Choose the Family that best describes the Package’s semantic role. Saving an assignment does not mutate the package in place. The server creates a new immutable Package revision that references the selected Family root and current Family revision. Historical Strategy and Backtest manifests keep their previous snapshots.</td>
  </tr>
  <tr>
    <td>unassignedInfo / Unassigned</td>
    <td>Unassigned</td>
    <td>Unassigned is valid for generic helper packages, early research outputs and packages that do not yet have a clear semantic home. It does not hide the Package or stop Agent research. A Strategy Rationale Family is a separate required field when a Strategy must become Backtest Ready.</td>
  </tr>
  <tr>
    <td>pastelColorInfo / Family card color</td>
    <td>Family Card Color</td>
    <td>The pastel color is a persistent display aid. It is assigned by the system, remains stable across rename and refresh, and has no relationship to risk, performance, status, owner or Agent priority.</td>
  </tr>
</table>

## 6.3 Exact V18 text and prescribed Production text

<table>
  <tr>
    <th>Message type</th>
    <th>V18 text / behavior</th>
    <th>Production V1 final UI text</th>
  </tr>
  <tr>
    <td>Page intro</td>
    <td>Rationale Families are a shared-editing workspace used by Create Package, Package Library and strategy workflows. Admin, Supervisor, User and Agent can all add, edit, remove, save and use every Family card, including cards created by other actors. Package Rationale Assignment is also fully shared and editable by every role.</td>
    <td>Keep same meaning; render with contextual ⓘ Shared Editing panel link. Guest route: “Sign in to view the shared Rationale Family registry.”</td>
  </tr>
  <tr>
    <td>Assignment note</td>
    <td>Select the appropriate shared Rationale Family for each package, then save the assignment changes. Every role can edit and save this shared assignment table.</td>
    <td>“Choose an ACTIVE Rationale Family or Unassigned for each Package. Changes are staged locally until saved. Saving is atomic: if one changed row is stale or invalid, no Package assignment is changed.”</td>
  </tr>
  <tr>
    <td>New Family placeholder</td>
    <td>No V18 placeholder.</td>
    <td>“e.g., Liquidity Sweep Reversal”</td>
  </tr>
  <tr>
    <td>New Family helper</td>
    <td>No V18 helper.</td>
    <td>“Required. Use a clear shared semantic name. Duplicate names are checked case-insensitively.”</td>
  </tr>
  <tr>
    <td>Empty Family list</td>
    <td>No V18 empty state.</td>
    <td>“No active Rationale Families are available. Create a Family to establish a shared semantic classification. Strategies cannot become Backtest Ready until an active Rationale Family is selected.”</td>
  </tr>
  <tr>
    <td>Empty assignment table</td>
    <td>No V18 empty state.</td>
    <td>“No rationale-assignable Packages match the current scope. There are no assignment changes to save.”</td>
  </tr>
  <tr>
    <td>Create success</td>
    <td>V18 silently rerenders after push.</td>
    <td>“Rationale Family “{familyName}” was created.”</td>
  </tr>
  <tr>
    <td>Revision success</td>
    <td>V18 silently rerenders after replace.</td>
    <td>“Rationale Family revision {revisionNumber} was saved.”</td>
  </tr>
  <tr>
    <td>Assignment success</td>
    <td>V18 silently rerenders after local select writes.</td>
    <td>“Rationale assignments were saved. {count} Package revision(s) were created.”</td>
  </tr>
  <tr>
    <td>Compatibility warning</td>
    <td>No V18 warning.</td>
    <td>“Current output type is not listed as compatible; the assignment was saved.”</td>
  </tr>
  <tr>
    <td>Duplicate error</td>
    <td>V18 silently ignores duplicate add.</td>
    <td>“A Rationale Family named “{familyName}” already exists. Open the existing card or choose a more specific name.”</td>
  </tr>
  <tr>
    <td>Stale conflict</td>
    <td>No V18 conflict behavior.</td>
    <td>“This Family changed after you opened it. Reload the current revision, review the changes, then reapply your update.”</td>
  </tr>
  <tr>
    <td>Batch conflict</td>
    <td>No V18 conflict behavior.</td>
    <td>“Assignments were not saved because one or more Packages changed after this table was loaded. No Package revisions were created. Reload the table and try again.”</td>
  </tr>
  <tr>
    <td>Remove confirmation</td>
    <td>No V18 confirmation.</td>
    <td>“Remove shared Rationale Family “{familyName}”? This is a soft delete. Historical Packages, Strategies and Backtest Results remain intact. Only an Admin can restore or permanently delete the Trash record.”</td>
  </tr>
  <tr>
    <td>Delete success</td>
    <td>V18 silently removes card and creates local Trash item.</td>
    <td>“Rationale Family “{familyName}” was moved to Trash.”</td>
  </tr>
  <tr>
    <td>Deleted Family dependency warning</td>
    <td>V18 Trash dependency summary only.</td>
    <td>“This Family is assigned to {count} current Package projection(s). They will remain historically valid but show “Assigned to deleted Family” until the Family is restored or reassigned.”</td>
  </tr>
</table>

# 7. Buttons, Commands, Preconditions and UI State Contracts

<table>
  <tr>
    <th>Control</th>
    <th>Production command / query</th>
    <th>Preconditions and disabled state</th>
    <th>Success / error / retry / audit</th>
  </tr>
  <tr>
    <td>Open page</td>
    <td>GET /v1/rationale-families?state=active; GET /v1/package-rationale-assignments.</td>
    <td>Authenticated human or Agent service context; page route only visual entry.</td>
    <td>Returns role-aware current projections + ETags/table version. Query is audit-light; denied access returns AUTHENTICATION_REQUIRED/POLICY_DENIED.</td>
  </tr>
  <tr>
    <td>+ Add Family</td>
    <td>POST /v1/rationale-families.</td>
    <td>Family Name valid; no create in flight; optional client idempotency key.</td>
    <td>201 creates root + revision 1 + color; toast success. Validation error keeps input. Audit: RATIONALE_FAMILY_CREATED.</td>
  </tr>
  <tr>
    <td>Edit</td>
    <td>GET /v1/rationale-families/{id} or current projection already loaded.</td>
    <td>Family must be ACTIVE and visible. Shared exception does not bypass deleted lifecycle.</td>
    <td>Opens local edit state with current revision ID/ETag. No audit mutation.</td>
  </tr>
  <tr>
    <td>Cancel</td>
    <td>No backend command.</td>
    <td>Only when editor open.</td>
    <td>Discard local draft. No audit and no revision.</td>
  </tr>
  <tr>
    <td>Save</td>
    <td>POST /v1/rationale-families/{id}/revisions.</td>
    <td>ACTIVE Family, valid Family Name, expected_head_revision_id/ETag, no save in flight.</td>
    <td>200 returns new revision/current root. 409 RATIONALE_FAMILY_CONFLICT offers reload. Audit: RATIONALE_FAMILY_REVISION_CREATED.</td>
  </tr>
  <tr>
    <td>Remove</td>
    <td>DELETE /v1/rationale-families/{id}.</td>
    <td>ACTIVE Family, expected row version, explicit confirm. Shared policy permits soft delete for all active actor types.</td>
    <td>200 transitions active -&gt; soft_deleted and creates Trash entry. Audit: RATIONALE_FAMILY_SOFT_DELETED. 409 stale -&gt; refresh; dependency warning never means cascade delete.</td>
  </tr>
  <tr>
    <td>Assignment select change</td>
    <td>No immediate backend mutation.</td>
    <td>Table loaded; target Family must be ACTIVE or null for Unassigned.</td>
    <td>Mark row dirty and update local staged diff. No audit until batch save.</td>
  </tr>
  <tr>
    <td>Save Assignment Changes</td>
    <td>POST /v1/package-rationale-assignments:batch.</td>
    <td>At least one dirty row; expected table version + expected package revision(s); no batch in flight.</td>
    <td>200 returns changed Package revisions and warnings. 409 conflict rejects all rows. Audit per changed assignment: PACKAGE_RATIONALE_ASSIGNED / UNASSIGNED.</td>
  </tr>
  <tr>
    <td>Restore (cross-page)</td>
    <td>POST /v1/trash/{trash_id}/restore.</td>
    <td>Admin only; executed from Trash page, not normal Family page.</td>
    <td>Restores same root/current revision to ACTIVE; audits RATIONALE_FAMILY_RESTORED.</td>
  </tr>
  <tr>
    <td>Permanent Delete (cross-page)</td>
    <td>DELETE /v1/trash/{trash_id}/purge.</td>
    <td>Admin only; retention/dependency checks and final re-auth required by Trash policy.</td>
    <td>Reject if historical manifests would be broken. Audit permanent deletion.</td>
  </tr>
</table>

## 7.1 Command payload examples

<table>
  <tr>
    <th>POST /v1/rationale-families<br/>{<br/>  &quot;display_name&quot;: &quot;Liquidity Sweep Reversal&quot;,<br/>  &quot;subfamilies&quot;: [&quot;Stop Run Reversal&quot;, &quot;Liquidity Void Reversal&quot;],<br/>  &quot;compatible_output_types&quot;: [&quot;Directional Signal&quot;, &quot;Liquidity Zone&quot;],<br/>  &quot;change_note&quot;: &quot;Created from research hypothesis HYP-204&quot;,<br/>  &quot;idempotency_key&quot;: &quot;...&quot;<br/>}</th>
  </tr>
</table>

<table>
  <tr>
    <th>POST /v1/package-rationale-assignments:batch<br/>{<br/>  &quot;expected_table_version&quot;: &quot;etag:assignments:2026-06-24T16:40:00Z&quot;,<br/>  &quot;changes&quot;: [<br/>    {&quot;package_root_id&quot;: &quot;pkg-root-01&quot;, &quot;expected_head_revision_id&quot;: &quot;pkg-rev-07&quot;, &quot;rationale_family_id&quot;: &quot;family-root-reversal&quot;, &quot;expected_family_current_revision_id&quot;: &quot;family-rev-04&quot;},<br/>    {&quot;package_root_id&quot;: &quot;pkg-root-02&quot;, &quot;expected_head_revision_id&quot;: &quot;pkg-rev-11&quot;, &quot;rationale_family_id&quot;: null}<br/>  ],<br/>  &quot;idempotency_key&quot;: &quot;...&quot;<br/>}</th>
  </tr>
</table>

API naming note: Endpoint paths are concrete implementation guidance aligned with Master Module 6. The binding behavior is canonical: stable root IDs, expected_head_revision_id / expected_table_version, immutable revisions and atomic batch semantics.

# 8. User, Agent and Recovery Flows

## 8.1 Successful human flow - create, enrich and assign

1. Authenticated User opens Edit > Rationale Families and reads the shared-editing note.

2. User enters “Liquidity Sweep Reversal” in New Rationale Family * and selects + Add Family.

3. Backend normalizes and uniqueness-checks the name, then creates a Family root, revision 1, persistent pastel color and audit event in one transaction.

4. The new card appears. User opens Edit, enters Subfamilies and Compatible Output Types, then saves a new Family revision.

5. User chooses the new Family for one or more Package rows. The table becomes dirty; no Package has changed yet.

6. User selects Save Assignment Changes. Backend validates every changed row and atomically creates a new Package revision for each changed assignment.

7. Page rehydrates from canonical response. Old Package revisions, existing Strategy references and Backtest manifests remain unchanged.

## 8.2 Empty and validation flow

1. User presses + Add Family with a blank or whitespace-only Family Name.

2. Client blocks the command and shows “Enter a Rationale Family name.” If a request reaches the server, backend returns RATIONALE_FAMILY_NAME_REQUIRED.

3. User enters a duplicate active normalized name. Backend returns RATIONALE_FAMILY_NAME_CONFLICT; existing card remains unchanged and input remains for correction.

4. User enters a name reserved by a soft-deleted root. Backend returns RATIONALE_FAMILY_NAME_RESERVED and presents recovery direction: restore/rename existing Family or choose a different name.

5. No active Family exists. Page shows the prescribed empty state. Strategy creation can remain in research/draft context, but Strategy Ready Check will later block any Strategy missing required Rationale Family.

## 8.3 Stale/concurrency flow - Family card

1. User A and Agent B open the same Family card. Both receive current revision ID and ETag/row_version.

2. User A saves a rename. Backend creates revision n+1 and advances root.current_revision_id.

3. Agent B saves using revision n. Backend rejects with 409 RATIONALE_FAMILY_CONFLICT; it does not apply last-write-wins overwrite.

4. Agent B reloads current revision, compares fields, reapplies intended semantic change and submits a new revision command with current expected_head_revision_id.

5. The successful operation produces a new immutable revision and diff audit event.

## 8.4 Stale/concurrency flow - assignment batch

1. User stages two assignment changes with table ETag and package current revision IDs.

2. Another actor changes one referenced Package before the batch is saved.

3. Server rejects the full request with PACKAGE_RATIONALE_ASSIGNMENT_CONFLICT. It creates no partial Package revisions.

4. UI keeps local staged diff visible, marks affected rows stale, offers Reload current assignments and Compare/reapply actions.

5. After reload, user submits a new batch. On success all changed package assignments transition together.

## 8.5 Soft delete, restore and historical integrity flow

1. Any active role invokes Remove for a shared Family and confirms the destructive action.

2. Backend sets root.lifecycle_state=soft_deleted, records Trash snapshot/dependency summary and emits RATIONALE_FAMILY_SOFT_DELETED.

3. Family leaves the active list and is absent from new assignment/Strategy selection lists. Existing package current projections show ASSIGNED_TO_DELETED_FAMILY where relevant.

4. Package logic, Strategy revisions, historical Results, Backtest manifests, Agent artifacts and previous Family snapshots remain intact.

5. Admin later restores from Trash. The same root/current revision becomes ACTIVE, old assignment projections normalize, and an audit event records restoration.

## 8.6 Agent Tool/API parity flow

1. Alpha Agent queries the Rationale Catalog API while running a backend research task; no browser or Lab Assistant conversation is required.

2. Agent finds no sufficient active Family for a research discovery. It writes a checkpoint/artifact proposal and, if its task policy permits, invokes POST /rationale-families.

3. The server creates Family root/revision with Agent provenance and audit event. Agent may then semantically assign an eligible Package using the same atomic assignment command as humans.

4. If the Agent only proposes a Family but does not apply it, audit/event type is AGENT_RATIONALE_PROPOSAL rather than a mutation event.

5. Agent cannot use shared assignment as a bypass to edit another owner’s Package code, parameters, execution rules, publication or approval state.

# 9. Production Backend and Domain Model

## 9.1 Canonical entities, identifiers and revisions

<table>
  <tr>
    <th>Entity</th>
    <th>Minimum fields</th>
    <th>Canonical behavior</th>
  </tr>
  <tr>
    <td>RationaleFamilyRoot</td>
    <td>id UUID; current_revision_id; soft_deleted; display_color; created_by_actor_id; created_at; deleted_at/by; row_version.</td>
    <td>Stable identity. Display name is not identity. Root color persists across revisions and rename.</td>
  </tr>
  <tr>
    <td>RationaleFamilyRevision</td>
    <td>id; family_id; revision_number; display_name; normalized_name; subfamilies_json; compatible_output_types_json; change_note; created_by/at; content_hash.</td>
    <td>Immutable. Any Family Name/Subfamily/Compatible Output Type change produces new revision.</td>
  </tr>
  <tr>
    <td>PackageRevision rationale snapshot</td>
    <td>package_root_id; package revision id; rationale_family_id nullable; rationale_family_revision_id nullable; rationale_display_snapshot_json.</td>
    <td>Assignment is stored on Package revision, not mutable root string. Historical current state remains reproducible.</td>
  </tr>
  <tr>
    <td>StrategyRevision Family snapshot</td>
    <td>strategy revision id; rationale_family_id required; rationale_family_revision_id required.</td>
    <td>Strategy stores exact selected active Family snapshot. Missing required Family blocks Backtest Ready state.</td>
  </tr>
  <tr>
    <td>Current assignment projection</td>
    <td>package_root_id; current_package_revision_id; rationale_family_id; current_family_name; assignment_state; updated_at.</td>
    <td>Read optimization only. Source truth remains immutable Package revision data.</td>
  </tr>
  <tr>
    <td>Trash entry</td>
    <td>trash_id; object_type; original root/revision snapshot; original location; deleted by/at; dependency summary.</td>
    <td>Soft deletion enables Admin restore/purge workflow without historical cascade delete.</td>
  </tr>
  <tr>
    <td>Audit event</td>
    <td>event type; actor; root/revision IDs; diff/snapshot; correlation/batch/task/checkpoint context.</td>
    <td>Every shared mutation is observable. Agent proposal and Agent applied mutation are distinct events.</td>
  </tr>
</table>

## 9.2 Lifecycle and deletion rules

<table>
  <tr>
    <th>State</th>
    <th>Meaning</th>
    <th>New selection availability</th>
    <th>Historical behavior</th>
  </tr>
  <tr>
    <td>ACTIVE</td>
    <td>Visible current Family root; can be selected, revised, soft-deleted and assignment target.</td>
    <td>Yes.</td>
    <td>Existing snapshots remain valid.</td>
  </tr>
  <tr>
    <td>soft_deleted</td>
    <td>Soft-deleted; absent from active cards/dropdowns.</td>
    <td>No. New package assignment must use active Family or Unassigned.</td>
    <td>Existing Package/Strategy/Run snapshots remain intact. Current projections may show ASSIGNED_TO_DELETED_FAMILY.</td>
  </tr>
  <tr>
    <td>RESTORED</td>
    <td>Not a separate durable state; restore returns root to ACTIVE.</td>
    <td>Yes.</td>
    <td>Existing snapshots remain intact; previous assignments return to normal projection state.</td>
  </tr>
</table>

## 9.3 Dependency rules

- No cascade delete: Deleting a Family must not delete or rewrite Packages, Strategies, Backtest Runs, Results or Agent artifacts.

- Historical snapshot integrity: Family rename/delete must not alter a previously persisted Family snapshot in a Package revision, Strategy revision or Backtest Run manifest.

- Assignment is semantic only: Family assignment has no hidden impact on entry/exit logic, risk, execution, order behavior or engine performance math.

- Strategy requiredness: A Strategy may remain Draft/Research without selected Family only when its lifecycle permits; Backtest Ready requires an ACTIVE Family selection.

- Unassigned package policy: Unassigned is valid for generic helpers, early research outputs and not-yet-classified Agent artifacts; it does not hide the package or block the Agent.

- Deleted root selection: A deleted Family cannot be newly assigned or selected in Strategy Context, even though old references remain valid historical snapshots.

# 10. Validation, Error and Recovery Contract

## 10.1 Family field validation

<table>
  <tr>
    <th>Check</th>
    <th>Rule</th>
    <th>Error code</th>
    <th>User / Agent recovery</th>
  </tr>
  <tr>
    <td>Blank Family Name</td>
    <td>Trimmed name cannot be empty.</td>
    <td>RATIONALE_FAMILY_NAME_REQUIRED</td>
    <td>Enter a shared semantic Family name.</td>
  </tr>
  <tr>
    <td>Length</td>
    <td>2-120 visible characters.</td>
    <td>RATIONALE_FAMILY_NAME_TOO_LONG</td>
    <td>Shorten the name while retaining semantic meaning.</td>
  </tr>
  <tr>
    <td>Duplicate active name</td>
    <td>Normalized case-insensitive active name must be unique.</td>
    <td>RATIONALE_FAMILY_NAME_CONFLICT</td>
    <td>Open existing Family or use a more specific distinct name.</td>
  </tr>
  <tr>
    <td>Reserved deleted name</td>
    <td>Soft-deleted normalized name is reserved by default.</td>
    <td>RATIONALE_FAMILY_NAME_RESERVED</td>
    <td>Restore/rename old Family where appropriate, or choose a different name.</td>
  </tr>
  <tr>
    <td>Subfamily/output limits</td>
    <td>At most 100 list items; each max 160 chars.</td>
    <td>RATIONALE_FAMILY_METADATA_LIMIT</td>
    <td>Split/trim the list; retain meaningful distinct values.</td>
  </tr>
  <tr>
    <td>Invalid text</td>
    <td>Reject unsafe control characters / malformed text.</td>
    <td>RATIONALE_FAMILY_INVALID_TEXT</td>
    <td>Paste plain visible text and retry.</td>
  </tr>
  <tr>
    <td>Stale Family revision</td>
    <td>expected_head_revision_id is no longer current; HTTP transport If-Match/ETag is stale.</td>
    <td>RATIONALE_FAMILY_CONFLICT</td>
    <td>Reload current revision, compare, reapply and save.</td>
  </tr>
</table>

## 10.2 Assignment validation

<table>
  <tr>
    <th>Check</th>
    <th>Expected behavior</th>
    <th>Error / warning</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>Missing/deleted Package root</td>
    <td>Reject row; atomic batch remains entirely unchanged.</td>
    <td>PACKAGE_NOT_FOUND or LIFECYCLE_BLOCKED.</td>
    <td>Reload assignment projection; remove stale row.</td>
  </tr>
  <tr>
    <td>Stale Package revision</td>
    <td>Reject full batch; no partial save.</td>
    <td>PACKAGE_RATIONALE_ASSIGNMENT_CONFLICT.</td>
    <td>Reload table and reapply intended changes.</td>
  </tr>
  <tr>
    <td>Selected Family soft_deleted</td>
    <td>Block new assignment.</td>
    <td>RATIONALE_FAMILY_NOT_ACTIVE.</td>
    <td>Select active Family or Unassigned; restore is Admin-only from Trash.</td>
  </tr>
  <tr>
    <td>Family revision stale</td>
    <td>Reject or require current revision reload.</td>
    <td>RATIONALE_FAMILY_CONFLICT.</td>
    <td>Refresh target Family and resubmit consciously.</td>
  </tr>
  <tr>
    <td>Compatible output mismatch</td>
    <td>Do not hard block.</td>
    <td>Warning OUTPUT_TYPE_NOT_LISTED: “Current output type is not listed as compatible; the assignment was saved.”</td>
    <td>Review Family output list or package contract; retain novel output where appropriate.</td>
  </tr>
  <tr>
    <td>Unassigned</td>
    <td>Valid null assignment.</td>
    <td>No error.</td>
    <td>New Package revision stores null family fields.</td>
  </tr>
  <tr>
    <td>Same assignment repeated</td>
    <td>No unnecessary revision.</td>
    <td>Idempotent no-op.</td>
    <td>Return current revision mapping; UI clears dirty state.</td>
  </tr>
</table>

## 10.3 Authorization and generic error behavior

<table>
  <tr>
    <th>Situation</th>
    <th>Server behavior</th>
    <th>Prescribed UI text</th>
  </tr>
  <tr>
    <td>Anonymous route or command</td>
    <td>Reject before registry data is returned.</td>
    <td>“Sign in to view the shared Rationale Family registry.”</td>
  </tr>
  <tr>
    <td>Role/policy denial caused by malformed client context</td>
    <td>Reject. Client-supplied role/owner flags are not authority.</td>
    <td>“You do not have permission to perform this action.”</td>
  </tr>
  <tr>
    <td>Network interruption before command result</td>
    <td>Do not assume mutation failed or succeeded. Use idempotency key/correlation ID to resolve.</td>
    <td>“We could not confirm the outcome. Refresh the page to load the current shared state before trying again.”</td>
  </tr>
  <tr>
    <td>Server unexpected error</td>
    <td>Preserve trace/correlation ID; no partial batch.</td>
    <td>“The shared registry could not be updated. No unconfirmed changes were applied. Try again or contact an administrator with reference {correlationId}.”</td>
  </tr>
</table>

# 11. Audit, Provenance, Lifecycle and Trash Effects

<table>
  <tr>
    <th>Event type</th>
    <th>Minimum audit payload</th>
    <th>Why it matters</th>
  </tr>
  <tr>
    <td>RATIONALE_FAMILY_CREATED</td>
    <td>family_id, revision_id, actor, name snapshot, color, source context, idempotency/correlation ID.</td>
    <td>Explains origin of shared semantic vocabulary.</td>
  </tr>
  <tr>
    <td>RATIONALE_FAMILY_REVISION_CREATED</td>
    <td>family_id, previous/new revision ID, diff, actor, optional change note.</td>
    <td>Explains rename/subfamily/output evolution without losing history.</td>
  </tr>
  <tr>
    <td>RATIONALE_FAMILY_SOFT_DELETED</td>
    <td>family_id, current revision snapshot, actor, dependency summary, trash_id.</td>
    <td>Supports shared-delete accountability and safe Admin recovery.</td>
  </tr>
  <tr>
    <td>RATIONALE_FAMILY_RESTORED</td>
    <td>family_id, actor=Admin, trash_id, restored revision.</td>
    <td>Documents restoration of shared semantic option.</td>
  </tr>
  <tr>
    <td>PACKAGE_RATIONALE_ASSIGNED</td>
    <td>Package root old/new revision mapping, Family snapshot, actor, batch ID.</td>
    <td>Shows semantic reclassification separate from package logic edits.</td>
  </tr>
  <tr>
    <td>PACKAGE_RATIONALE_UNASSIGNED</td>
    <td>Package root old/new revision mapping, actor, reason if supplied, batch ID.</td>
    <td>Preserves explicit removal of classification.</td>
  </tr>
  <tr>
    <td>AGENT_RATIONALE_PROPOSAL</td>
    <td>Agent ID, hypothesis/task/checkpoint references, suggestion vs applied action.</td>
    <td>Separates Agent recommendation from an actual shared registry mutation.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Trash Rule: Any Admin, Supervisor, User or Agent may initiate normal soft delete of a Rationale Family because this page is a global shared-editing exception. Only Admin may view Trash, restore or permanently delete. Permanent purge must be rejected when it would violate retention/dependency rules or break historical manifest integrity.</th>
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
    <td>Identity</td>
    <td>Families and assignments are held in browser JavaScript arrays and string names.</td>
    <td>Stable Family root IDs, immutable Family revisions, Package revision snapshots and read projections are persistent server records.</td>
    <td>Never persist display name as the only relationship key.</td>
  </tr>
  <tr>
    <td>Add family</td>
    <td>Blank/duplicate add is local no-op; accepted add pushes to array.</td>
    <td>Validate normalized name; create root + revision 1 + persistent color + audit in a transaction.</td>
    <td>Add visible * and helper; server remains authoritative.</td>
  </tr>
  <tr>
    <td>Edit/rename</td>
    <td>Replaces array item; uses alias map from old name to new name.</td>
    <td>Creates new Family revision with ETag/row_version optimistic concurrency.</td>
    <td>Alias may be migration/search helper only; never runtime source of truth.</td>
  </tr>
  <tr>
    <td>Color</td>
    <td>Assigns pastel in local memory when rendered.</td>
    <td>Stores root display_color and preserves it through rename/reload.</td>
    <td>Color remains visual only and must not be name-hash derived.</td>
  </tr>
  <tr>
    <td>Assignments</td>
    <td>Reads select values and writes `pkg.rationaleFamily` local string one by one.</td>
    <td>Atomic batch writes immutable Package revisions, uses expected table/package/family versions, returns warnings/conflicts.</td>
    <td>No partial updates or silent string overwrite.</td>
  </tr>
  <tr>
    <td>Shared editing</td>
    <td>Permission helpers return true in prototype.</td>
    <td>Special policy functions authorize Admin/Supervisor/User/Agent; Guest is not a User.</td>
    <td>Do not use generic owner policy for this limited semantic scope.</td>
  </tr>
  <tr>
    <td>Delete</td>
    <td>Splices array, makes local Trash entry; no confirmation.</td>
    <td>Soft delete ACTIVE-&gt;soft_deleted, Trash entry/audit/dependency summary; no cascade.</td>
    <td>Add confirm and stale version guard as Implementation Decision.</td>
  </tr>
  <tr>
    <td>Restore/purge</td>
    <td>Prototype Trash logic exists elsewhere and uses demo Admin gate.</td>
    <td>Admin-only Trash endpoints with retention/dependency validation.</td>
    <td>Rationale page must not offer direct non-Admin restore/purge control.</td>
  </tr>
  <tr>
    <td>Seed consistency</td>
    <td>V18 seed card list lacks Embedded System / TA Resolver although ESP metadata references it.</td>
    <td>Seed Family is created ACTIVE.</td>
    <td>Canonical Master-selected production correction.</td>
  </tr>
  <tr>
    <td>ⓘ help</td>
    <td>No existing page-specific ⓘ buttons.</td>
    <td>Help content may be added without altering domain model.</td>
    <td>Production contextual help catalog in Section 6.2 is an explicit Implementation Decision.</td>
  </tr>
</table>

# 13. Kodcu AI için Implementation Rules

1. Rationale Family relationshiplarını Package veya Strategy tablolarında yalnız display-name stringi olarak persist etme. Family root ID ve selected Family revision ID kullan.

2. Family Name, Subfamilies veya Compatible Output Types değiştiğinde current revisionı in-place update etme; yeni immutable Family revision oluştur ve root.current_revision_idyi atomik güncelle.

3. Rationale Families ve Package Rationale Assignment endpointsinde generic owner-only edit/delete policy kullanma. Bu özel semantic scope için shared-edit policy fonksiyonlarını kullan.

4. Shared-edit exceptionı Trash list, restore, permanent delete, package code edit, parameter edit, data binding, approval, publish veya execution rule mutationına genişletme.

5. Family root display_colorını root seviyesinde sakla; Family rename sonrasında rengi değiştirme, name-hash ile yeniden üretme veya performans/risk/owner anlamı yükleme.

6. New Family inputunda trim, whitespace normalization, visible-character length, control-character rejection ve active/deleted normalized-name conflict validationı hem UI hem serverda uygula.

7. Deleted Familyyi yeni assignment veya Strategy Context seçeneği olarak döndürme. Eski Package/Strategy/Run snapshotsını ise olduğu gibi sakla.

8. Package Rationale Assignment değişikliğini mutable Package root metadata patchi olarak yazma. Her değişen Package root için yeni immutable Package revision üret.

9. Batch assignment save sırasında bir satır stale veya invalid ise tüm batchi reddet; kısmi başarı, sırayla yazma veya silent retry uygulama.

10. Assignment tablosu için table ETag/version ve her changed row için expected_head_revision_id kullan. Family edit için expected Family revision/ETag kullan.

11. Compatible Output Types uyumsuzluğunu default hard blocker yapma. Warning üret; Agentın novel output ve yeni Family keşfini gereksiz kısıtlama.

12. Unassigned Package kayıtlarını filtre dışında bırakma veya Agent araştırmasını durdurma. Unassigned, valid semantic state olarak modelle.

13. Family selectionının strategy logic graphını, stop/sizing/scaling ayarını, order behaviorını veya backtest outputunu gizli biçimde değiştirmesine izin verme.

14. Agentın Rationale Catalogu UI, browser, Login veya Lab Assistant conversation bağımlılığıyla kullanmasını isteme. Agent Tool Gateway/API üzerinden same domain commandlere erişsin.

15. Agent proposal eventini applied mutation eventinden ayır. Checkpoint/task/hypothesis provenance audit payloadında korunmalı.

16. Her successful shared mutation sonrası frontend statei canonical response ile rehydrate et; optimistic local string stateini source of truth kabul etme.

17. Trading Signal ve Trade Logu Rationale Family classification yüzünden PackageKind enumuna dahil etme. Semantic Family classification target typeı değiştirmez.

18. V18deki Embedded System / TA Resolver seed eksikliğini Productionda ACTIVE seed Family oluşturarak düzelt.

# 14. Acceptance Tests

<table>
  <tr>
    <th>ID</th>
    <th>Scenario</th>
    <th>Expected result</th>
  </tr>
  <tr>
    <td>RF-01</td>
    <td>Registered User, Adminin oluşturduğu Family kartını düzenler.</td>
    <td>Shared exception uygulanır; new immutable revision ve audit event oluşur.</td>
  </tr>
  <tr>
    <td>RF-02</td>
    <td>Agent, başka ownerın eligible Packagei için rationale assignment batchine değişiklik ekler.</td>
    <td>Semantic assignment başarıyla Package revision üretir; Package logic ownership policy değişmez.</td>
  </tr>
  <tr>
    <td>RF-03</td>
    <td>Supervisor aynı Family kartını eski ETag ile kaydeder.</td>
    <td>409 RATIONALE_FAMILY_CONFLICT döner; silent overwrite olmaz.</td>
  </tr>
  <tr>
    <td>RF-04</td>
    <td>Family rename edilir, eski Backtest Run açılır.</td>
    <td>Manifestteki previous Family snapshot görünür; historical run/result değişmez.</td>
  </tr>
  <tr>
    <td>RF-05</td>
    <td>Family soft delete edilir.</td>
    <td>Kart active list/dropdownlardan çıkar; Package/Strategy/Run/Artifactlar korunur; Trash entry/audit oluşur.</td>
  </tr>
  <tr>
    <td>RF-06</td>
    <td>Admin deleted Familyyi Trash üzerinden restore eder.</td>
    <td>Aynı root/current revision ACTIVE olur; assignment projectionları normal ASSIGNED durumuna döner.</td>
  </tr>
  <tr>
    <td>RF-07</td>
    <td>User active normalized isimle aynı Familyyi ekler.</td>
    <td>RATIONALE_FAMILY_NAME_CONFLICT döner; duplicate root/revision oluşmaz.</td>
  </tr>
  <tr>
    <td>RF-08</td>
    <td>Soft-deleted Family ismi ile yeni Family create denenir.</td>
    <td>RATIONALE_FAMILY_NAME_RESERVED döner; restore/rename/different name recovery gösterilir.</td>
  </tr>
  <tr>
    <td>RF-09</td>
    <td>Two-row assignment batchte tek Package stale olur.</td>
    <td>Full batch conflict ile reddedilir; hiçbir new Package revision oluşmaz.</td>
  </tr>
  <tr>
    <td>RF-10</td>
    <td>Package output type Family compatible listesinde yoktur.</td>
    <td>OUTPUT_TYPE_NOT_LISTED warning döner; assignment policy izinliyse save bloklanmaz.</td>
  </tr>
  <tr>
    <td>RF-11</td>
    <td>Unassigned seçilir ve batch save edilir.</td>
    <td>New Package revisionda family root/revision alanları null olur; package listeden kaybolmaz.</td>
  </tr>
  <tr>
    <td>RF-12</td>
    <td>Strategy Contextte Family seçmeden Ready Check çalıştırılır.</td>
    <td>Ready Check failure; Run locked/blocked kalır.</td>
  </tr>
  <tr>
    <td>RF-13</td>
    <td>Agent UI kapalıyken yeni Family create command çalıştırır.</td>
    <td>Backendde Family root/revision/audit oluşur; UI later query ile gösterir.</td>
  </tr>
  <tr>
    <td>RF-14</td>
    <td>Guest direct page/API erişimi dener.</td>
    <td>Registry data dönmez; authentication/policy error döner.</td>
  </tr>
  <tr>
    <td>RF-15</td>
    <td>V18 seed/ESP consistency test edilir.</td>
    <td>Embedded System / TA Resolver ACTIVE seed Family olarak bulunur; ESP meta/filter ilişkisi string mismatch olmadan çalışır.</td>
  </tr>
  <tr>
    <td>RF-16</td>
    <td>Delete button clientte manipüle edilerek çağrılır.</td>
    <td>Server shared exception applies only to active allowed actor; lifecycle/expected-version guard validationı yine zorunludur.</td>
  </tr>
  <tr>
    <td>RF-17</td>
    <td>Network timeout sonrası create command tekrar gönderilir.</td>
    <td>Same idempotency key previous resultı döndürür; duplicate Family root oluşmaz.</td>
  </tr>
  <tr>
    <td>RF-18</td>
    <td>Browser refresh assignment table dirty iken gerçekleşir.</td>
    <td>Unsaved staged changes kaybolabilir; persisted assignment yalnız canonical server state olarak geri gelir.</td>
  </tr>
</table>

# 15. Final Consistency Check - Master Technical Reference v1.0

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Master authority</td>
    <td>Evet. Module 6 root/revision, shared edit, assignment batch, lifecycle, audit ve CR-01 semantic classification rule tercih edildi.</td>
  </tr>
  <tr>
    <td>V18 vs Production ayrımı</td>
    <td>Evet. V18 string/array/local behavior ayrı; Production stable IDs, immutable revisions, API and concurrency ayrı açıklandı.</td>
  </tr>
  <tr>
    <td>Global shared-editing exception</td>
    <td>Evet. Family cards and Package Rationale Assignment for Admin/Supervisor/User/Agent; Trash restore/purge only Admin.</td>
  </tr>
  <tr>
    <td>Package / Working Item distinction</td>
    <td>Evet. Rationale classification target typeı değiştirmez; Trading Signal/Trade Log package type değildir.</td>
  </tr>
  <tr>
    <td>Agent continuous-runtime principle</td>
    <td>Evet. Agent Tool/API parity, UI/browser independence, proposal vs applied audit difference yazıldı.</td>
  </tr>
  <tr>
    <td>Revision / manifest integrity</td>
    <td>Evet. Family rename/delete historical Package/Strategy/Run snapshotsını değiştirmez; assignment new Package revision üretir.</td>
  </tr>
  <tr>
    <td>Validation / recovery / concurrency</td>
    <td>Evet. Field and batch validation, ETag/row version, 409 conflict, no partial batch, retry/reload behaviors yazıldı.</td>
  </tr>
  <tr>
    <td>Lifecycle / Trash</td>
    <td>Evet. Soft delete only normal removal; no cascade; Admin-only restore/purge; dependency/recovery effects açıklandı.</td>
  </tr>
  <tr>
    <td>Future Dev boundary</td>
    <td>Uygulanmaz. Rationale Families Production V1 active core alanıdır; Future Dev capability olarak anlatılmadı.</td>
  </tr>
  <tr>
    <td>Scope discipline</td>
    <td>Evet. İlgili sayfalar yalnız dependency/boundary bağlamında anıldı; ayrı sayfaların UI dokümantasyonu tekrar edilmedi.</td>
  </tr>
</table>

Bu sayfanın Production V1 uygulaması; shared edit policy, stable Family root kimliği, immutable Family revision, package revision üzerinden semantic assignment, atomic concurrency, soft delete/Trash, audit provenance ve Agent UI bağımsızlığı birlikte sağlandığında tamamlanmış kabul edilir. Bu unsurlardan herhangi biri eksikse V18deki basit kart ve tablo görünümü, çok aktörlü ve yeniden üretilebilir Entropia sistemine güvenli biçimde taşınmış sayılmaz.
