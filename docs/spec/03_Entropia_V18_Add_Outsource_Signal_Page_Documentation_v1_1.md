---
title: "Entropia V18 — Add Outsource Signal Page Documentation v1.1"
page_number: 3
document_type: "Page implementation specification"
source_document: "Entropia_V18_Add_Outsource_Signal_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Add Outsource Signal Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18  |  SAYFA DOKÜMANTASYONU 3/22
> **Original DOCX footer:** Entropia V18 | Add Outsource Signal | Production V1 implementation specification | Page

ENTROPIA V18

Sayfa Dokümantasyonu [3]/22

ADD OUTSOURCE SIGNAL

Trading Signal ve Trade Log external Mainboard Working Item oluşturma giriş yüzeyi

<table>
  <tr>
    <th>Belge niteliği: V18 prototype davranışını ve Production V1 canonical domain sözleşmesini ayıran ayrıntılı frontend, backend, validation, lifecycle, audit ve Agent parity spesifikasyonu.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam kilidi<br/>Bu belge Add Outsource Signal seçici/giriş yüzeyini, iki canonical object type arasındaki ayrımı, transient draft yaratımını, Mainboarda attach/pin başlangıcını ve bu noktadaki authorization/lifecycle sözleşmesini kapsar. Trading Signal event/mapping formunun ayrıntılı alanları Sayfa [4]/22; Trade Log import/mapping formunun ayrıntılı alanları Sayfa [5]/22 içinde tanımlanacaktır. Aynı alanlar burada tekrar edilmez.</th>
  </tr>
</table>

# 0. Document Control, Scope ve Source Traceability

<table>
  <tr>
    <th>Kontrol alanı</th>
    <th>Kayıt</th>
  </tr>
  <tr>
    <td>Belge adı</td>
    <td>Entropia V18 - Add Outsource Signal Page Documentation v1.1</td>
  </tr>
  <tr>
    <td>Sayfa sırası</td>
    <td>3 / 22</td>
  </tr>
  <tr>
    <td>Canonical teknik otorite</td>
    <td>Entropia V18 - Master Technical Reference v1.0. V18 HTML yalnız görünür prototype behavior kaynağıdır; Handoff v1.1 üretim standardıdır; 2.3 POSITION ENTRY LOGIC anlatım derinliği referansıdır.</td>
  </tr>
  <tr>
    <td>Belge kapsamı</td>
    <td>Mainboard &gt; Add Outsource Signal hover submenu, Trading Signal ve Trade Log type choice, transient external-work draft başlangıcı, persisted work object oluşturma/attach sınırı, route/role/Agent parity, lifecycle/audit/Trash etkileri.</td>
  </tr>
  <tr>
    <td>Kapsam dışı</td>
    <td>Trading Signal detail schema ve mapping editor; Trade Log file format/mapping editor; Package Library katalog yönetimi; Ready Check ekranı; Portfolio Allocation formu; Trash ekranı; Run/Result detayları. Bu alanlar yalnız bu giriş yüzeyiyle ilişkileri kadar anılır.</td>
  </tr>
  <tr>
    <td>Temel canonical referanslar</td>
    <td>Master Modül 0: UI/Agent sınırı, durable iş ilkesi. Modül 1: role/policy, UI visibility ≠ authorization. Modül 2: UUID root, immutable revision, external work object ayrımı. Modül 3: soft delete/Trash/audit. Modül 7: Package type sınırı. Modül 9: §1.2, §2, §4.2-4.4, §5, §6.1, §7, §8, §9.3, §10-12 ve CR-01 Canonical Integration.</td>
  </tr>
  <tr>
    <td>V18 HTML izlenebilirliği</td>
    <td>Top menu: Mainboard &gt; Add Outsource Signal submenu. Functions: addSignalPackageBox(event, packageData), addTradeLogBox(event, packageData), createTradingDataDetailsContent(...), markTradingDataFileLoaded(...), clearTradingDataPanel(...). V18 local state: signalCount, tradeLogCount, backtestReady.</td>
  </tr>
  <tr>
    <td>Sayfa içi karar kayıtları</td>
    <td>ID-03-01: V18 hover submenu korunur; child selection first opens a transient unsaved draft instead of immediately persisting an empty root. ID-03-02: Production helper/info content adds a compact help affordance because V18 submenu has no ⓘ icon; the addition does not alter object type semantics.</td>
  </tr>
</table>

## 0.1 Source Traceability Map

<table>
  <tr>
    <th>Sayfa konusu</th>
    <th>Master referansı</th>
    <th>V18 HTML referansı</th>
    <th>Çapraz bağımlılık</th>
    <th>Karar / not</th>
  </tr>
  <tr>
    <td>External work type selection</td>
    <td>M2 §4.3; M9 §4.2-4.4; M9 Canonical Integration CR-01</td>
    <td>Mainboard &gt; Add Outsource Signal &gt; Trading Signal / Trade Log submenu</td>
    <td>Pages 1, 4, 5, 8</td>
    <td>Trading Signal ve Trade Log PackageKind değildir; item_kind yalnız trading_signal veya trade_log olabilir. [V18 legacy prototype label; Production domain/API type değildir.]</td>
  </tr>
  <tr>
    <td>Transient row/draft</td>
    <td>M9 §1.2(3), §4.1 analogy, §5.2</td>
    <td>Child click immediately appends a local row and opens details</td>
    <td>Pages 1, 4, 5, 14</td>
    <td>V18 local row unsaved olabilir; Production Ready Check/RUN sadece persisted ve enabled itemleri dikkate alır.</td>
  </tr>
  <tr>
    <td>Revision pin/attachment</td>
    <td>M2 §1.3; M9 §5.2, §7.1-7.3</td>
    <td>No stable root/revision identity in V18 DOM</td>
    <td>Pages 1, 4, 5, 14, 15</td>
    <td>Attach edilmiş Mainboard item specific root + revision taşır; implicit latest yasaktır.</td>
  </tr>
  <tr>
    <td>Import/integration path</td>
    <td>M9 §4.2-4.3; M0 §9.1</td>
    <td>TXT/CSV acceptance, local loaded flag</td>
    <td>Pages 4, 5, 11, 14</td>
    <td>Signal ingestion ve Trade Log importer HTTP request içinde tamamlanmaz; worker/job, source asset, reports, validation evidence üretir.</td>
  </tr>
  <tr>
    <td>Access/delete</td>
    <td>M1 §§5-8; M3 §§5-11; M9 §5.3, §9</td>
    <td>Menu visible in prototype; row × locally moves to Trash helper</td>
    <td>Pages 1, 20</td>
    <td>UI availability policy değildir. Delete root soft delete üretir; Trash/restore/purge sadece Admin.</td>
  </tr>
  <tr>
    <td>Agent parity</td>
    <td>M0 §§5-6; M1 §10; M9 §9.3</td>
    <td>No agent UI path</td>
    <td>Page 18</td>
    <td>Agent same domain command/tool capability ile external work create/import/attach isteği verir; browser emülasyonu kullanmaz.</td>
  </tr>
</table>

## 0.2 Kural Türleri

<table>
  <tr>
    <th>Etiket</th>
    <th>Bu belgede kullanımı</th>
  </tr>
  <tr>
    <td>Canonical Rule</td>
    <td>Master Technical Reference v1.0 içinde açıkça sabitlenmiş Production V1 davranışıdır. Bu belge bunu açıklığa kavuşturur; değiştirmez.</td>
  </tr>
  <tr>
    <td>Derived Rule</td>
    <td>Canonical kuralın zorunlu uygulama sonucudur. Örneğin PackageKind iki yeni değerle genişletilemediği için type pickerın yalnız external work object factoryye gitmesi gerekir.</td>
  </tr>
  <tr>
    <td>V18 Interface Observation</td>
    <td>HTMLde görünen hover, submenu, client counter, local row, legacy label veya client-side backtestReady davranışıdır. Server authority değildir.</td>
  </tr>
  <tr>
    <td>Implementation Decision - Non-Canonical Gap Resolution</td>
    <td>Masterın teknik hedefi açık olup birebir UX mekanizması belirtilmediğinde seçilen somut uygulama yönüdür. Bu belgede gerekçesi, etki alanı ve sınırı yazılır.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kapsam Sınırı

Add Outsource Signal, Mainboard üzerinde bir dış kaynağı iki farklı canonical çalışma nesnesinden biri olarak başlatan seçim yüzeyidir. Bu yüzey bir Package Library filtrelemesi, generic upload ekranı veya live-trading emri değildir. Kullanıcı ya da uygun policyye sahip Agent burada dış dünyadan gelen yönlü sinyal olaylarını temsil edecek bir Trading Signal oluşturma yolunu ya da zaten gerçekleşmiş işlem kayıtlarını temsil edecek bir Trade Log oluşturma yolunu başlatır.

Trading Signal, dış sağlayıcıdan veya entegrasyondan gelen yön/olay/sinyal akışını ifade eden external working objecttir. Trade Log ise zaten gerçekleşmiş veya dış kaynaktan sağlanmış entry/exit kayıtlarını ifade eden historical trade data objecttir; canlı sinyal üretmez. İki nesne ileride reusable mapping veya export ile ilişkilendirilebilir, ancak root domain kimlikleri external input olarak korunur.

<table>
  <tr>
    <th>Canonical Rule - Object boundary<br/>Package Librarydeki PackageKind enumu yalnız strategy_package, indicator_package, condition_package ve embedded_system_package değerlerinden oluşur. Trading Signal ve Trade Log bu enumun veya Package Library type pickerın içine eklenmez. Add Outsource Signal, bu iki external Mainboard Working Item için tek canonical başlangıç yüzeyidir.</th>
  </tr>
</table>

## 1.1 Araştırma ve Backtest Zincirindeki Konumu

- Kullanıcı veya Agent, bir dış kaynağın türünü seçer: Trading Signal ya da Trade Log.

- İlgili child detail surface üzerinde transient draft yapılandırılır; kaynak, mapping, zaman semantiği ve gerekli data/import bağımlılıkları belirlenir.

- Save Draft veya Save and Attach işlemi, root + immutable revision üretir veya yeni revision yaratır; attach edilirse MainboardWorkingItem bu revisiona pinlenir.

- Persisted, enabled item Mainboard Composition Snapshot içine aday olabilir; Ready Check yalnız snapshotın o anki composition hashine göre çalışır.

- RUN, immutable snapshot üzerinden async Backtest Run yaratır. Sadece succeeded run immutable Backtest Result üretir; Add Outsource Signal bir run veya result yaratmaz.

## 1.2 Bu Sayfanın Tanımlamadığı Alanlar

- Trading Signal detail schema: Event mapping, source connector, event-level requiredness, available-time policy ve signal validation Page [4]/22 sahibidir.

- Trade Log detail schema: File columns, mapping, parse preview, row-level validation, import job lifecycle ve historical trade evidence Page [5]/22 sahibidir.

- Package management: Exported reusable mapping veya future package relationshipi, Package Librarynin type modelini değiştirmez; katalog/Package lifecycle Page [8]/22 kapsamındadır.

- Run/Ready Check: Bu yüzey yalnız compositionı değiştirir. Readiness, snapshot, queue, execution ve Result davranışı Pages [14]-[16]/22 tarafından ayrıntılandırılır.

## 1.3 Kavramsal Terimler

<table>
  <tr>
    <th>Terim</th>
    <th>Canonical anlam</th>
    <th>Bu sayfadaki uygulama sonucu</th>
  </tr>
  <tr>
    <td>External Working Object</td>
    <td>Mainboardda çalışabilen fakat Package Library package type olmayan dış kaynaklı domain nesnesi.</td>
    <td>Trading Signal ve Trade Log type seçiminin ürettiği root family budur.</td>
  </tr>
  <tr>
    <td>Trading Signal</td>
    <td>Dış sağlayıcı/entegrasyondan gelen yönlü signal event akışı.</td>
    <td>Backtest, eventin event_timeı değil available_timeı sonrasında sinyali kullanabilir.</td>
  </tr>
  <tr>
    <td>Trade Log</td>
    <td>Entry/exit kayıtlarından oluşan geçmiş veya dış kaynaklı trade data nesnesi.</td>
    <td>Canlı entry signal üretmez; history/benchmark/reference inputu olarak değerlendirilir.</td>
  </tr>
  <tr>
    <td>Root</td>
    <td>İnsan okunabilir ad değişse dahi değişmeyen UUIDv7 iş nesnesi kimliği.</td>
    <td>Ana object type seçimi root familyyi belirler; root bir Package değildir.</td>
  </tr>
  <tr>
    <td>Revision</td>
    <td>Konfigürasyon veya veri anlamı değiştiğinde yaratılan immutable sürüm.</td>
    <td>Source mapping/import sonucu değişirse mevcut revision update edilmez; yeni revision üretilir.</td>
  </tr>
  <tr>
    <td>Pinned Revision</td>
    <td>Mainboard itemin explicit olarak bağlandığı revision.</td>
    <td>Board veya run implicit latest revision çözmez.</td>
  </tr>
  <tr>
    <td>Available Time</td>
    <td>Bir dış signal bilgisinin strateji/Agent için gerçek hayatta kullanılabilir hale geldiği an.</td>
    <td>Trading Signal eventleri yalnız bu zaman sonrası backtestte etkili olabilir.</td>
  </tr>
  <tr>
    <td>Source Asset</td>
    <td>Import veya connectorun getirdiği değişmez ham dosya/kayıt kanıtı.</td>
    <td>Trade Log importu source asset + parse/validation evidence üretmeden canonical revisiona dönüşmez.</td>
  </tr>
</table>

# 2. Erişim, Görünürlük, Sahiplik ve Server-Side Policy

Menüdeki bir seçeneğin görünmesi, submenunun hover ile açılması veya child rowun UI içinde eklenmesi herhangi bir callerın kalıcı Trading Signal/Trade Log oluşturma, başkasının objectini değiştirme ya da silme yetkisini kanıtlamaz. Her production command principal, operation, root owner, visibility, lifecycle, active-job dependency ve hedef revision contexti ile server-side doğrulanır.

<table>
  <tr>
    <th>Principal / rol</th>
    <th>Add Outsource Signal yüzeyi</th>
    <th>Create / attach</th>
    <th>Edit / delete</th>
    <th>Trash / restore</th>
  </tr>
  <tr>
    <td>Guest / anonymous</td>
    <td>V18de menu kabuğunu görebilir; Productionda protected selection actiona erişemez.</td>
    <td>Hayır. AUTHENTICATION_REQUIRED.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Kendi çalışma alanında type chooserı açar.</td>
    <td>Kendi Trading Signal/Trade Log rootunu oluşturur; erişilebilir kaynağı use ederek own output üretir; own Default Mainboarda attach eder.</td>
    <td>Normalde yalnız own object/revision. Başkasının shared objectini use etmek edit/delete vermez.</td>
    <td>Kendi delete commandini verebilir; Trashı göremez, restore/purge yapamaz.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Shared working contextte chooserı açar.</td>
    <td>Kendi outputunu oluşturur ve izinli workspacee attach eder.</td>
    <td>Yalnız own output mutate/delete. Başka ownerın objectini use edebilir fakat doğrudan edit/delete edemez.</td>
    <td>Trash yok; restore/purge yok.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm uygun workspace/action yüzeylerini açar.</td>
    <td>Tüm uygun objectleri oluşturur, attach eder veya yönetir.</td>
    <td>Ownerdan bağımsız edit/delete overrideı vardır; owner transfer yalnız ayrı auditli command ile olur.</td>
    <td>View/restore/permanent delete yalnız Admin.</td>
  </tr>
  <tr>
    <td>Agent principal</td>
    <td>Human menu kullanmaz; UI zorunlu değildir.</td>
    <td>Tool Gateway/API üzerinden own external work outputu veya snapshot/attach isteği üretir.</td>
    <td>Yalnız own outputları edit/delete eder; Admin override mümkündür.</td>
    <td>Trashı göremez; restore/purge yapamaz.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Derived Rule - Use ≠ edit<br/>Bir Actorün published/shared bir source, mapping ya da Mainboard workspacei görmesi; onu yeni output üretiminde referanslayabileceği anlamına gelebilir. Bu, source rootun ownerlığını devraldığı veya source revisionı düzenleyebileceği anlamına gelmez. Create edilen yeni Trading Signal/Trade Log rootunun ownerı create commandini başlatan principal olur; Agent outputunda owner Agent principal olarak kalır.</th>
  </tr>
</table>

## 2.1 Authorization Decision Flow

- Caller türünü çöz: anonymous, authenticated human veya trusted Agent runtime.

- Operationı sınıflandır: open_type_chooser, start_transient_draft, create_root_revision, attach, pin_revision, import_source, list/view, edit, soft_delete, restore veya permanent_delete.

- Hedef workspace/object/revision contextini yükle: owner, visibility, lifecycle, soft-delete state, current/pinned revision, active run dependency ve share/use policy.

- Global role rules ve resource-specific policy uygula. Client body içindeki role, owner, isAdmin, itemKind veya ready=true authority değildir.

- İzin yoksa mutation başlamadan structured error döndür. İzin varsa command transactionı, immutable revision/audit/outbox davranışını domain türüne göre uygula.

# 3. V18 Interface Behavior — Yerleşim, Navigasyon ve Görünür Bileşenler

V18de Add Outsource Signal ayrı bir route, page canvas, modal veya popup değildir. Mainboard menu dropdownı içinde bulunan parent submenu itemıdır. Kullanıcı Mainboard menu alanı üzerinde hover yaptığında Add Outsource Signal satırı görünür; bu satır hover olduğunda sağda iki seçenekli nested submenu açılır: Trading Signal ve Trade Log.

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 görünür davranış</th>
    <th>V18 local state / DOM etkisi</th>
    <th>Production anlamı</th>
  </tr>
  <tr>
    <td>Mainboard menu</td>
    <td>Mainboard label ve dropdown kabuğu hover ile açılır.</td>
    <td>CSS hover; click showMainboard() çağırabilir.</td>
    <td>Human navigation/presentation. Authorization endpoint/command seviyesinde ayrıca doğrulanır.</td>
  </tr>
  <tr>
    <td>Add Outsource Signal parent item</td>
    <td>Nested submenu taşıyan item; kendi başına form veya modal açmaz.</td>
    <td>Hoverda .submenu display:block olur.</td>
    <td>Type chooser giriş noktası. Parent item root/revision veya audit üretmez.</td>
  </tr>
  <tr>
    <td>Trading Signal child item</td>
    <td>Click addSignalPackageBox(event) çağırır.</td>
    <td>signalCount artırır, backtestReady false olur, DOMa local row/panel eklenir.</td>
    <td>Transient Trading Signal draft başlatır; persistent object ancak explicit save ile yaratılır.</td>
  </tr>
  <tr>
    <td>Trade Log child item</td>
    <td>Click addTradeLogBox(event) çağırır.</td>
    <td>tradeLogCount artırır, backtestReady false olur, DOMa local row/panel eklenir.</td>
    <td>Transient Trade Log draft başlatır; persisted import/revision ayrı save/import akışında oluşur.</td>
  </tr>
  <tr>
    <td>Generated Mainboard row</td>
    <td>Strategy-row style ile eklenir; arrow ve × action içerir.</td>
    <td>Arrow local details open/close; × local Trash helper çağrısı.</td>
    <td>Sadece persisted/attached itemler canonical Mainboard projectionında görünür. Transient row &quot;Unsaved&quot; olarak ayırt edilir.</td>
  </tr>
  <tr>
    <td>Legacy labels</td>
    <td>Row ve action metinlerinde &quot;TRADING SIGNAL PACKAGE&quot;, &quot;TRADE LOG PACKAGE&quot;, &quot;Save As ... Package&quot; örnekleri bulunur.</td>
    <td>Text content only; canonical type enforcement yoktur.</td>
    <td>CR-01 nedeniyle Production metin/API/enumlarından kaldırılır. Canonical isimler Trading Signal ve Trade Logdur.</td>
  </tr>
  <tr>
    <td>ⓘ info control</td>
    <td>Add Outsource Signal submenu veya type choice üzerinde ⓘ button yoktur.</td>
    <td>No popover state.</td>
    <td>V18 gözlemidir. Production usability alignment için aşağıdaki minimal help affordance önerilir; bu yeni UI yardım katmanıdır, domain type değildir.</td>
  </tr>
</table>

## 3.1 V18 Arayüz Anatomisi ve Görünme Koşulları

<table>
  <tr>
    <th>Görünür state</th>
    <th>Koşul</th>
    <th>Kullanıcıya görünen sonuç</th>
    <th>Backend / domain etkisi</th>
  </tr>
  <tr>
    <td>Closed</td>
    <td>Pointer Mainboard menu üzerinde değil.</td>
    <td>Add Outsource Signal görünmez.</td>
    <td>Yok.</td>
  </tr>
  <tr>
    <td>Mainboard dropdown open</td>
    <td>Pointer Mainboard menu üzerinde.</td>
    <td>Add Strategy, Add Outsource Signal, Add Package ve Portfolio/Eq. Allocation items görünür.</td>
    <td>Yok; hover stateidir.</td>
  </tr>
  <tr>
    <td>Outsource submenu open</td>
    <td>Pointer Add Outsource Signal parent item üzerinde.</td>
    <td>Sağ tarafta Trading Signal ve Trade Log child choices görünür.</td>
    <td>Yok; type henüz seçilmemiştir.</td>
  </tr>
  <tr>
    <td>Type chosen / transient detail</td>
    <td>Child option click.</td>
    <td>V18de Mainboarda yeni row + expanded details eklenir.</td>
    <td>Productionda type selection transient draft yaratır; ready/run inputu değildir.</td>
  </tr>
  <tr>
    <td>Persisted / attached</td>
    <td>Child detail Save başarılı.</td>
    <td>Canonical Mainboard row appears / rehydrates.</td>
    <td>Root + immutable revision + MainboardWorkingItem pin oluşur; composition hash değişir, prior readiness stale olur.</td>
  </tr>
  <tr>
    <td>Error / denied</td>
    <td>Policy, validation veya import dependency fail.</td>
    <td>V18de çoğu durumda no structured UI behavior.</td>
    <td>Production actionable error/toast gösterir; partial persistent object yaratılmaz.</td>
  </tr>
</table>

## 3.2 V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Trading Signal/Trade Log clicki DOMa hemen satır ekler ve client counters kullanır.</td>
    <td>Click tek başına root/revision yaratmaz. Transient draft UI stateidir; persisted work object only Save Draft / Save and Attach ile oluşur.</td>
    <td>ID-03-01. Bu ayrım boş/invalid external objectlerin kalıcı domain nesnesi olmasını engeller ve M9un persisted-item ruleunu korur.</td>
  </tr>
  <tr>
    <td>Rows &quot;... PACKAGE&quot; labelı taşıyabilir; Add Package içinde signal/trade-log package pathi de bulunabilir.</td>
    <td>PackageKind genişletilmez. Item kind yalnız trading_signal veya trade_logdur; API route/object names canonical external object language kullanır.</td>
    <td>CR-01 terminology migration. Legacy labels yalnız V18 observation olarak kaydedilir; Production UI değiştirilir.</td>
  </tr>
  <tr>
    <td>backtestReady booleanı type seçimi veya file input değişiminde false yapılır.</td>
    <td>Server current composition hash üzerinden immutable Ready Report üretir. Transient draft compositiona dahil olmadığından persisted set değişene kadar existing server report otomatik stale olmaz.</td>
    <td>Client boolean gerçek readiness authority değildir. Save/attach/pin/enable/delete sonrası server stale event üretir.</td>
  </tr>
  <tr>
    <td>Trade Log file state browser input/DOMdan okunur; sample parser browserda bulunur.</td>
    <td>Trade Log raw file object storagea immutable source asset olarak kabul edilir; parser/validator worker jobu parse report, skipped row report ve validation evidence üretir.</td>
    <td>Client-side parsing preview yalnız UX yardımı olabilir; canonical import sonucu değildir.</td>
  </tr>
  <tr>
    <td>Arrow open/close visually toggles details.</td>
    <td>Expanded/collapsed only presentation preference. Revision, composition hash veya audit event üretmez.</td>
    <td>M9 §5.1. Device sync istenirse separate user_ui_preference store kullanılabilir.</td>
  </tr>
</table>

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen / state</th>
    <th>Varsayılan / görünme koşulu</th>
    <th>Enabled / disabled / loading davranışı</th>
    <th>Payload / engine etkisi</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>Add Outsource Signal parent menu</td>
    <td>Closed. Mainboard dropdown hover olduğunda görünür.</td>
    <td>Enabled UI does not grant create policy. No loading state for hover.</td>
    <td>Payload yok; engine etkisi yok.</td>
    <td>Pointer away ile kapanır; policy denial only child commandde ortaya çıkar.</td>
  </tr>
  <tr>
    <td>Object type chooser</td>
    <td>No type preselected. User selects exactly one: Trading Signal veya Trade Log.</td>
    <td>Authenticated/authorized human için enabled. Guest selection clicki login gate veya AUTHENTICATION_REQUIRED result üretir.</td>
    <td>Draft.kind = trading_signal | trade_log. Engine effect yok.</td>
    <td>Cancel/escape or pointer-away does not create root/revision.</td>
  </tr>
  <tr>
    <td>Transient Trading Signal draft</td>
    <td>Type selected after child click. Unsaved badge required.</td>
    <td>Child form may be edited; Save disabled until child-required fields valide olur.</td>
    <td>No persisted Mainboard item; Ready Check/Run input excluded.</td>
    <td>Discard removes transient state; choose a type again to restart.</td>
  </tr>
  <tr>
    <td>Transient Trade Log draft</td>
    <td>Type selected after child click. Unsaved badge required.</td>
    <td>Upload/import actions may enter loading. Save/attach disabled while ingestion is pending/failed.</td>
    <td>No canonical trade-record revision until worker result passes validation.</td>
    <td>Retry upload/import, repair mapping, or discard. Do not preserve invalid partial records as usable input.</td>
  </tr>
  <tr>
    <td>Persisted attached item</td>
    <td>Save and Attach succeeds.</td>
    <td>Enabled by default unless user/server explicitly sets is_enabled=false. Loading only during attach/pin command.</td>
    <td>Specific pinned revision enters composition; changes composition hash and stales prior Ready Report.</td>
    <td>Canonical UI rehydrate; if stale report, run Ready Check again.</td>
  </tr>
  <tr>
    <td>Newer revision available</td>
    <td>Object gets a new saved revision but Mainboard remains pinned to older one.</td>
    <td>Row remains usable with old revision; show non-blocking badge/action.</td>
    <td>No implicit engine change.</td>
    <td>User/Agent explicitly pin new revision; action stales readiness.</td>
  </tr>
  <tr>
    <td>Policy denied</td>
    <td>Caller lacks create/attach/edit/delete right.</td>
    <td>Control may be hidden/disabled as UX, but server denial remains authoritative.</td>
    <td>No mutation; no revision; no draft attach.</td>
    <td>Explain required role/ownership/share path; reload context if role changed.</td>
  </tr>
  <tr>
    <td>Stale concurrency</td>
    <td>Expected workspace/item/revision version mismatches current server state.</td>
    <td>Save/attach/pin button completes with 409/412 semantics; local optimistic state must not overwrite remote state.</td>
    <td>No partial mutation; no unintended revision.</td>
    <td>Reload canonical state; compare/fork/reapply intended changes; retry with fresh version.</td>
  </tr>
</table>

## 4.1 State-Layering Contract

<table>
  <tr>
    <th>State katmanı</th>
    <th>Bu sayfadaki örnek</th>
    <th>Kaynak doğrusu ve sınır</th>
  </tr>
  <tr>
    <td>UI presentation state</td>
    <td>Mainboard dropdown open, nested submenu visible, row expanded/collapsed.</td>
    <td>Frontend stateidir. No audit/revision/composition mutation.</td>
  </tr>
  <tr>
    <td>Transient editor draft</td>
    <td>Type selected but child detail henüz Save edilmedi.</td>
    <td>Human form stateidir. May be held in local memory; it is not a root/revision and cannot enter Ready Check/RUN.</td>
  </tr>
  <tr>
    <td>Persisted root + immutable revision</td>
    <td>Saved Trading Signal source mapping or saved Trade Log canonical import revision.</td>
    <td>Backend source of truth. Meaningful change creates a new revision; existing revision is not mutated.</td>
  </tr>
  <tr>
    <td>Mainboard composition state</td>
    <td>MainboardWorkingItem with kind, work_object_root_id, pinned_revision_id, position_index, is_enabled.</td>
    <td>Backend authoritative. Attach/pin/enable/delete changes composition hash and readiness validity.</td>
  </tr>
  <tr>
    <td>Async job/projection state</td>
    <td>Trade Log import job, connector ingestion, validation report, UI projection refresh.</td>
    <td>Durable job/event state. Browser refresh/close does not cancel worker.</td>
  </tr>
</table>

# 5. Alanlar, Varsayılanlar, Zorunluluk ve Dependency Contract

<table>
  <tr>
    <th>Scope note<br/>Add Outsource Signalin V18de bağımsız bir formu yoktur. Bu nedenle bu sayfadaki gerçek visible field contract yalnız nested type choice ile sınırlıdır. Trading Signal ve Trade Log detay formlarında bulunan Name, Source/Provider, Market, Base TF, Rationale Family, Data Quality, Time Zone, Price Source, OHLCV Use, File upload ve Initial Capital alanlarının tam Field Contract Matrixleri kendi sayfalarında [4]/[5] yazılacaktır; burada tekrar edilmeleri kapsam ihlalidir.</th>
  </tr>
</table>

## 5.1 Type Choice Field Contract Matrix

<table>
  <tr>
    <th>Alan</th>
    <th>UI tipi / V18 default</th>
    <th>Zorunluluk</th>
    <th>Tüm seçenekler ve koşullar</th>
    <th>Production payload</th>
    <th>Validation / dependency</th>
  </tr>
  <tr>
    <td>External Object Type *</td>
    <td>Nested menu child choice. V18de default/preselection yoktur.</td>
    <td>Always required to start a draft. Type selection without a choice cannot create a draft.</td>
    <td>Trading Signal; Trade Log. Exactly one choice.</td>
    <td>item_kind: &quot;trading_signal&quot; | &quot;trade_log&quot; in transient draft metadata; persisted root family is derived from this enum.</td>
    <td>Reject null, empty, package, signal_package, trade_log_package or unknown enum. Selection determines the child schema; fields must not be mixed across kinds.</td>
  </tr>
  <tr>
    <td>Destination Mainboard</td>
    <td>V18 always operates on visible Mainboard; no picker.</td>
    <td>Conditionally required only on Save and Attach. Not required to merely open/discard a transient draft.</td>
    <td>Current authenticated human Default Mainboard in V1. Future multi-board management is out of scope.</td>
    <td>mainboard_id plus attach intent; created MainboardWorkingItem stores work_object_root_id + pinned_revision_id.</td>
    <td>Server resolves default board from principal/session or explicit authorized board_id. Client display name is not identity. If no accessible board exists, deny attach and retain valid saved object un-attached.</td>
  </tr>
  <tr>
    <td>Initial enabled state</td>
    <td>No V18 toggle; row visually behaves active.</td>
    <td>Not user-required in V18.</td>
    <td>Production default true for a successfully attached item unless server policy/incomplete lifecycle forces false.</td>
    <td>is_enabled: true by default at attach.</td>
    <td>Disabled item remains visible but excluded from snapshot/Ready Check/allocation. Child validation failure must not be modeled as enabled=false workaround.</td>
  </tr>
  <tr>
    <td>Human-readable label</td>
    <td>V18 local labels increment signalCount/tradeLogCount; not an input on chooser.</td>
    <td>Not required at type choice. Object naming belongs to child details.</td>
    <td>No production default identifier is derived from DOM count.</td>
    <td>No chooser payload; child save carries display_name.</td>
    <td>Server root UUIDv7 is identity; generated reference may be shown, but names cannot be used to resolve/pin object.</td>
  </tr>
</table>

## 5.2 Conditional Requiredness and Dependency Rules

<table>
  <tr>
    <th>Kural</th>
    <th>Ne zaman aktif olur</th>
    <th>UI zorunluluğu</th>
    <th>Server/engine etkisi</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>Type must be selected</td>
    <td>Every initial action.</td>
    <td>No selected type means no draft and no Next/Continue action.</td>
    <td>No root/revision/request built.</td>
    <td>Choose Trading Signal or Trade Log.</td>
  </tr>
  <tr>
    <td>Trading Signal child contract</td>
    <td>item_kind = trading_signal.</td>
    <td>Child page [4] required fields and signal event source/mapping must validate before save/attach.</td>
    <td>Revision must contain event contract including event_id, event_time, available_time, instrument_id, direction, signal_type, source_record_id; optional suggested entry/exit/confidence as applicable.</td>
    <td>Repair source/mapping/time policy; save new revision. Do not substitute current time for unknown available_time.</td>
  </tr>
  <tr>
    <td>Trade Log child contract</td>
    <td>item_kind = trade_log.</td>
    <td>Child page [5] import/source/mapping requirements must validate; save/attach stays blocked while job pending/failing.</td>
    <td>Raw source asset, parse report, skipped-row report, canonical trade-record revision and validation evidence are required before usable import revision.</td>
    <td>Upload supported source, repair mapping, inspect row report, retry job; invalid rows remain visible as evidence, not silent deletion.</td>
  </tr>
  <tr>
    <td>Attach requirement</td>
    <td>User chooses Save and Attach / Attach Existing Revision.</td>
    <td>Authorized workspace and specific revision required.</td>
    <td>MainboardWorkingItem created/pinned; composition hash changes and Ready Report becomes stale.</td>
    <td>Select an accessible board/revision or save object without attach.</td>
  </tr>
  <tr>
    <td>Delete restriction</td>
    <td>Object currently referenced by queued/running Run manifest.</td>
    <td>Delete button disabled with reason or action preflight blocks.</td>
    <td>No soft delete until active run is stopped/finished according to Run lifecycle.</td>
    <td>Wait for completion or controlled cancel/pause path; then retry delete.</td>
  </tr>
</table>

## 5.3 Disabled/Hidden State and State Preservation

- No hidden type coercion: A choice that begins as Trading Signal cannot be silently converted to Trade Log by changing a later field. User must discard or explicitly start a new draft of the other kind, because the two root schemas and lifecycle paths differ.

- Child dependency preservation: When a child-level selection becomes incompatible, the UI may retain the prior typed value for user inspection only if it is visibly invalid/stale. It must be excluded from save payload and engine resolution until repaired. The detailed reset/preserve rules are owned by Pages [4]/[5].

- Unsaved draft discard: Discarding a transient unpersisted draft clears its type-specific form state. It creates neither Trash entry nor audit event because no root/revision exists.

- Persisted object delete: Deleting a saved/attached object is never equivalent to clearing a draft. It follows soft delete, Trash and audit rules; historical manifests retain pinned provenance.

# 6. Information Content Catalog and Final UI Text

V18 Add Outsource Signal submenu üzerinde ⓘ button bulunmaz. Bu nedenle V18e ait mevcut info popover metni yoktur. Aşağıdaki iki production help controlü, seçim semantiğini gizlemeden netleştirmek için Implementation Decision ID-03-02 olarak önerilir. Bunlar form alanı değildir; payload yazmaz, permission vermez ve validation bypass etmez.

## 6.1 Production ⓘ Paneli - Add Outsource Signal

<table>
  <tr>
    <th>Info key / UI alanı</th>
    <th>Panel başlığı</th>
    <th>UIya doğrudan yerleştirilecek nihai metin</th>
  </tr>
  <tr>
    <td>outsourceSignalInfo / Add Outsource Signal</td>
    <td>Add Outsource Signal</td>
    <td>Buradan Package Libraryye yeni bir package eklemezsiniz. Dış kaynaklı bir çalışma nesnesi başlatırsınız.<br/><br/>Trading Signal: Dış sağlayıcıdan gelen yönlü veya olay tabanlı sinyal akışıdır. Backtest yalnız her eventin gerçekten kullanılabilir hale geldiği available time sonrasında bu sinyali değerlendirebilir.<br/><br/>Trade Log: Daha önce gerçekleşmiş işlem kayıtlarının dış kaynaktan içeri alınmış halidir. Canlı sinyal üretmez; geçmiş trade akışını analiz, kıyaslama veya araştırma bağlamında kullanır.<br/><br/>Seçimi yaptıktan sonra açılan taslak, kaydedilene kadar Ready Check veya RUNa dahil edilmez.</td>
  </tr>
  <tr>
    <td>outsourceTypeInfo / Object Type</td>
    <td>Trading Signal mi, Trade Log mu?</td>
    <td>Trading Signal seçin: Kaynağınız zaman içinde gelen long/short veya olay bazlı signal eventleri sağlıyorsa. Her event için event time ile available time ayrımı korunmalıdır.<br/><br/>Trade Log seçin: Kaynağınız gerçekleşmiş entry/exit kayıtlarını sağlıyorsa. Trade Log bir geçmiş kayıt nesnesidir; sistem bunu otomatik olarak yeni işlem açan canlı signal gibi yorumlamaz.<br/><br/>Bir taslağın türünü sonradan değiştirmek yerine diğer türde yeni bir taslak başlatın. İki türün root, revision ve validation sözleşmeleri farklıdır.</td>
  </tr>
  <tr>
    <td>unsavedExternalDraftInfo / Unsaved badge</td>
    <td>Unsaved External Draft</td>
    <td>Bu satır yalnız geçici düzenleme stateidir. Henüz canonical Trading Signal veya Trade Log rootu, immutable revisionı ya da Mainboarda pinlenmiş itemi yoktur.<br/><br/>Kaydetmeden bu taslak Ready Checke, Portfolio Allocationa veya RUN manifestine dahil edilmez. Taslağı kapatmak veya silmek Trash kaydı üretmez.<br/><br/>Kalıcı hale getirmek için ilgili detay ekranındaki Save Draft veya Save and Attach işlemini tamamlayın.</td>
  </tr>
</table>

## 6.2 Menu, Helper, Warning, Toast, Empty-State and Error Text Catalog

<table>
  <tr>
    <th>Bağlam</th>
    <th>Nihai UI metni</th>
    <th>Tetik / kullanım</th>
  </tr>
  <tr>
    <td>Menu parent label</td>
    <td>Add Outsource Signal</td>
    <td>V18deki parent label korunur.</td>
  </tr>
  <tr>
    <td>Type chooser helper</td>
    <td>Choose what the external source represents. Trading Signal is an actionable external event stream; Trade Log is completed historical trade data.</td>
    <td>Production compact helper / accessibility description.</td>
  </tr>
  <tr>
    <td>Trading Signal choice helper</td>
    <td>Create a Trading Signal draft from an external signal source. The draft must define time-safe event availability before it can be used in a backtest.</td>
    <td>Type hover/help description.</td>
  </tr>
  <tr>
    <td>Trade Log choice helper</td>
    <td>Create a Trade Log draft from imported historical trades. Import and validation must complete before the log can be attached as a usable Mainboard item.</td>
    <td>Type hover/help description.</td>
  </tr>
  <tr>
    <td>Unsaved draft badge</td>
    <td>Unsaved draft - not included in Ready Check or RUN.</td>
    <td>Transient detail row after type selection.</td>
  </tr>
  <tr>
    <td>Save/attach success toast</td>
    <td>Trading Signal saved and attached to this Mainboard. / Trade Log saved and attached to this Mainboard.</td>
    <td>Only after server returns canonical root, revision and item binding.</td>
  </tr>
  <tr>
    <td>Saved, not attached toast</td>
    <td>Saved as revision {revision_ref}. It is not yet attached to this Mainboard.</td>
    <td>Explicit save without attach.</td>
  </tr>
  <tr>
    <td>No accessible board error</td>
    <td>This external object was saved, but it could not be attached because no accessible Mainboard is available.</td>
    <td>Attach policy/context fails after valid object save; no silent rollback of successful object save.</td>
  </tr>
  <tr>
    <td>Unauthenticated error</td>
    <td>Sign in to create an external Trading Signal or Trade Log.</td>
    <td>Anonymous selection/save attempt.</td>
  </tr>
  <tr>
    <td>Type validation error</td>
    <td>Choose Trading Signal or Trade Log before continuing.</td>
    <td>No type selected / invalid client payload.</td>
  </tr>
  <tr>
    <td>Import pending warning</td>
    <td>Import is still running. Wait for the validation report before attaching this Trade Log.</td>
    <td>Trade Log job PENDING/RUNNING.</td>
  </tr>
  <tr>
    <td>Legacy label migration warning</td>
    <td>This source is an external working object, not a Package Library package.</td>
    <td>Where migration from V18 legacy labels needs user-facing clarification.</td>
  </tr>
  <tr>
    <td>Stale conflict error</td>
    <td>This Mainboard changed while you were working. Reload the latest composition, review the change, then try again.</td>
    <td>expected_head_revision_id/fingerprint conflict.</td>
  </tr>
  <tr>
    <td>Delete blocked warning</td>
    <td>This item is used by a queued or running backtest. Finish or stop that run before deleting the object.</td>
    <td>Delete preflight blocked.</td>
  </tr>
</table>

# 7. Buttonlar, Commandler ve State Davranışı

<table>
  <tr>
    <th>UI action</th>
    <th>V18 davranışı</th>
    <th>Production command / precondition</th>
    <th>Loading / success / error / audit</th>
  </tr>
  <tr>
    <td>Hover Mainboard / Add Outsource Signal</td>
    <td>CSS hover opens dropdown/submenu.</td>
    <td>No backend command. Presentation only.</td>
    <td>No loading/audit/revision. Keyboard focus should offer equivalent open/close behavior.</td>
  </tr>
  <tr>
    <td>Choose Trading Signal</td>
    <td>addSignalPackageBox adds client DOM row and resets backtestReady.</td>
    <td>start_transient_outsource_draft(kind=trading_signal). No root/revision creation. Requires an authenticated and policy-eligible human UI session.</td>
    <td>Immediate Unsaved draft UI. No audit. If session/role invalid, show AUTHENTICATION_REQUIRED/ACCESS_DENIED and do not create draft.</td>
  </tr>
  <tr>
    <td>Choose Trade Log</td>
    <td>addTradeLogBox adds client DOM row and resets backtestReady.</td>
    <td>start_transient_outsource_draft(kind=trade_log). No root/revision creation.</td>
    <td>Immediate Unsaved draft UI. No audit. Source import is not started until child upload/import action.</td>
  </tr>
  <tr>
    <td>Save Draft - child owned</td>
    <td>V18 buttons are labels without canonical API behavior.</td>
    <td>create_trading_signal_revision or create_trade_log_revision. Child required data must validate; mutation carries idempotency_key and expected draft/context version.</td>
    <td>Disable duplicate submit. Success returns canonical root + immutable revision; audit event. 422 returns structured field/dependency issues; 409/412 returns stale conflict.</td>
  </tr>
  <tr>
    <td>Save and Attach - child owned</td>
    <td>No canonical V18 attachment transaction.</td>
    <td>Atomic create/update revision + attach_mainboard_item or pin_mainboard_item_revision. Requires authorized board and explicit revision.</td>
    <td>Success rehydrates board, recomputes composition hash, stales prior Ready Reports, emits domain/outbox events. Partial success must be explicit: object may save but attach may fail only if transaction design intentionally separates operations.</td>
  </tr>
  <tr>
    <td>Discard unsaved draft</td>
    <td>V18 has no explicit chooser-level discard; local row can be removed by × helper.</td>
    <td>discard_transient_outsource_draft. No root/revision command.</td>
    <td>No Trash/audit. Confirm only if unsaved changes exist. UI returns to type chooser/closed state.</td>
  </tr>
  <tr>
    <td>Expand/collapse row</td>
    <td>Arrow swaps ▼/▲ and toggles details.</td>
    <td>toggle_presentation_state only; optional user_ui_preference persistence.</td>
    <td>No Ready stale, no audit, no revision.</td>
  </tr>
  <tr>
    <td>Delete persisted object</td>
    <td>× sends local helper to move to Trash.</td>
    <td>soft_delete_entity(entity_id, expected_head_revision_id, idempotency_key, reason). Requires owner/Admin and no active queued/running run dependency.</td>
    <td>Confirmation required. Success creates Trash Entry/audit/outbox; row removed. Blocked or denied response leaves canonical row intact.</td>
  </tr>
</table>

## 7.1 Command Contracts (Conceptual)

<table>
  <tr>
    <th>Command</th>
    <th>Request minimum</th>
    <th>Success response minimum</th>
    <th>Failure codes / recovery</th>
  </tr>
  <tr>
    <td>start_transient_outsource_draft</td>
    <td>kind; client_draft_id optional; no root id.</td>
    <td>Transient UI acknowledgement only or local state creation.</td>
    <td>INVALID_ITEM_KIND -&gt; present only two choices. AUTHENTICATION_REQUIRED/ACCESS_DENIED -&gt; do not create draft.</td>
  </tr>
  <tr>
    <td>create_trading_signal_revision</td>
    <td>draft payload; source/mapping contract; idempotency_key; expected context version.</td>
    <td>trading_signal_root_id; trading_signal_revision_id; lifecycle/state; validation summary.</td>
    <td>422 validation/dependency errors -&gt; repair child fields. 409/412 -&gt; reload/fork/reapply. 403 -&gt; ownership/policy explanation.</td>
  </tr>
  <tr>
    <td>create_trade_log_revision / request_import</td>
    <td>source asset reference or upload session; mapping config; idempotency_key.</td>
    <td>root/revision identity or import_job_id; source asset reference; job state.</td>
    <td>IMPORT_PENDING/IMPORT_FAILED/UNSUPPORTED_FORMAT -&gt; inspect report, repair, retry. Do not create usable revision from client parser output alone.</td>
  </tr>
  <tr>
    <td>attach_mainboard_item</td>
    <td>mainboard_id; work_object_root_id; pinned_revision_id; item_kind; expected board version; idempotency_key.</td>
    <td>mainboard_working_item_id; pinned revision; composition_hash; ready_report_status=STALE.</td>
    <td>BOARD_ACCESS_DENIED, REVISION_NOT_USABLE, OBJECT_SOFT_DELETED, CONCURRENCY_CONFLICT -&gt; retain object; fix explicit cause then retry.</td>
  </tr>
  <tr>
    <td>soft_delete_entity</td>
    <td>entity_id; expected_head_revision_id; idempotency_key; optional reason/context.</td>
    <td>trash_entry_id; deletion state; changed composition info.</td>
    <td>ACTIVE_RUN_DEPENDENCY -&gt; finish/cancel through run lifecycle. DELETE_FORBIDDEN -&gt; owner/Admin required. ALREADY_SOFT_DELETED -&gt; idempotent current state.</td>
  </tr>
</table>

# 8. Kullanıcı Akışları

## 8.1 Başarılı Trading Signal Oluşturma ve Attach Akışı

- Authenticated User Mainboard dropdownını açar, Add Outsource Signal üzerine gelir ve Trading Signal seçer.

- UI, "Unsaved draft - not included in Ready Check or RUN" badgei taşıyan transient Trading Signal detail panelini açar. Bu adım root/revision veya MainboardWorkingItem yaratmaz.

- User, Page [4] kontratındaki source/event/mapping bilgilerini tamamlar. Signal eventleri için available_time yoksa save validation bloklanır.

- User Save and Attach seçer. Backend policy, typed contract, idempotency ve expected board/draft version kontrolünü yapar.

- Backend immutable TradingSignalRevisionı ve authorized MainboardItemı transaction içinde oluşturur; item pinned_revision_id ile bağlanır.

- Backend composition hashini günceller, mevcut Ready Reportu STALE yapar, audit/outbox eventleri üretir ve UI canonical state ile yeniden hydrate edilir.

- Kullanıcı Ready Checki yeniden çalıştırmadan RUN yapamaz. Başarılı RUN ayrı Backtest Run/worker flowudur.

## 8.2 Başarılı Trade Log Import ve Attach Akışı

- Authenticated User Add Outsource Signal > Trade Log seçer; unsaved Trade Log draft açılır.

- User Page [5] üzerindeki source file ve mapping/configuration alanlarını tamamlar. File upload yalnız seçimdir; canonical import sonucu değildir.

- Upload/import commandi immutable source asset kaydını ve durable ingestion/validation jobunu başlatır. UI job id üzerinden progress/status izler.

- Worker parse report, skipped-row report, canonical trade-record revision ve validation evidence üretir. Failed/import pending durumunda attach disabled kalır.

- Validation başarılıysa User Save and Attach ile specific TradeLogRevisionı Mainboarda pinler.

- Attach composition hashini değiştirir ve Ready Reportu STALE yapar. Trade Logun historical olması, onu canlı entry signal gibi yorumlatmaz.

## 8.3 Empty, Validation, Dependency, Permission ve Recovery Akışları

<table>
  <tr>
    <th>Durum</th>
    <th>Kullanıcıya görünen sonuç</th>
    <th>Backend sonucu</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>No type selected</td>
    <td>Chooser açık kalır; helper visible.</td>
    <td>No command/no root/no revision.</td>
    <td>Trading Signal veya Trade Log seç.</td>
  </tr>
  <tr>
    <td>Anonymous selection</td>
    <td>Sign in to create an external Trading Signal or Trade Log.</td>
    <td>401/unauthenticated; no draft persisted.</td>
    <td>Login; menu state may be reopened after session refresh.</td>
  </tr>
  <tr>
    <td>Invalid legacy kind injected</td>
    <td>Unsupported external object type.</td>
    <td>400 INVALID_ITEM_KIND; package enum mutation rejected.</td>
    <td>Use canonical Trading Signal or Trade Log choice.</td>
  </tr>
  <tr>
    <td>Signal missing available time</td>
    <td>This signal source cannot be used until each event has a valid available time.</td>
    <td>422 time-safety validation; no usable revision/attach.</td>
    <td>Supply reliable availability policy/source field; save new revision.</td>
  </tr>
  <tr>
    <td>Trade Log import failed</td>
    <td>Import failed. Review the parse and validation report, then repair the file or mapping.</td>
    <td>Job terminal FAILED with retained source asset/report/evidence.</td>
    <td>Fix file/mapping; request retry/new import revision. Do not rely on browser preview.</td>
  </tr>
  <tr>
    <td>Object saved, attach denied</td>
    <td>Object saved, but not attached to this Mainboard.</td>
    <td>Revision remains persisted; attach transaction either separately fails or atomic combined flow rejects whole action per chosen command semantics.</td>
    <td>Select accessible board, request share, or leave object saved for later attach.</td>
  </tr>
  <tr>
    <td>Stale Mainboard</td>
    <td>This Mainboard changed while you were working.</td>
    <td>409/412; no overwriting pin/order/enabled state.</td>
    <td>Reload composition, compare intended item/revision, retry with updated expected_head_revision_id.</td>
  </tr>
  <tr>
    <td>Active run blocks delete</td>
    <td>This item is used by a queued or running backtest.</td>
    <td>Delete preflight BLOCKED; no Trash entry.</td>
    <td>Complete/cancel run through its lifecycle then retry delete.</td>
  </tr>
</table>

# 9. Production Backend and Domain Behavior

## 9.1 Domain Objects and Relations

<table>
  <tr>
    <th>Nesne</th>
    <th>Sorumluluk</th>
    <th>Kimlik / immutability</th>
    <th>Add Outsource Signal ilişkisi</th>
  </tr>
  <tr>
    <td>TradingSignalRoot</td>
    <td>External signal source object identity, owner, lifecycle, visibility.</td>
    <td>UUIDv7 root. Soft delete separate from revision history.</td>
    <td>Trading Signal choice ultimately creates this root only on explicit save.</td>
  </tr>
  <tr>
    <td>TradingSignalRevision</td>
    <td>Source/mapping/event contract and time-safe signal semantics.</td>
    <td>Immutable. Meaningful change creates next revision.</td>
    <td>Contains event-level required contract; attach pins a specific revision.</td>
  </tr>
  <tr>
    <td>TradeLogRoot</td>
    <td>Historical external trade data identity, owner, lifecycle, visibility.</td>
    <td>UUIDv7 root.</td>
    <td>Trade Log choice ultimately creates this root only on explicit save/import flow.</td>
  </tr>
  <tr>
    <td>TradeLogRevision</td>
    <td>Canonicalized trade records or import configuration + evidence references.</td>
    <td>Immutable. Import/mapping change creates next revision.</td>
    <td>Cannot be declared usable merely because a browser file input has value.</td>
  </tr>
  <tr>
    <td>SourceAsset</td>
    <td>Raw uploaded/ingested evidence, checksum, source metadata.</td>
    <td>Immutable asset reference.</td>
    <td>Produced/linked by external import/integration path; important for Trade Log and may support Signal source ingestion.</td>
  </tr>
  <tr>
    <td>Import / Ingestion Job</td>
    <td>Asynchronous parser, mapping validator, evidence/report producer.</td>
    <td>Durable job id/status; browser independent.</td>
    <td>Required for raw import path; no synchronous long parse in UI request.</td>
  </tr>
  <tr>
    <td>MainboardWorkingItem</td>
    <td>Composition row: item kind, root ref, pinned revision, position, enabled.</td>
    <td>Stable item id; points to revision, not name/latest lookup.</td>
    <td>Created on attach; type selected here must match the root family.</td>
  </tr>
  <tr>
    <td>Composition Snapshot / Ready Report</td>
    <td>Immutable view of enabled persisted composition and validation result.</td>
    <td>Hash-bound, staleable artifact.</td>
    <td>Type selection itself has no effect; attach/pin/enable/delete has effect.</td>
  </tr>
  <tr>
    <td>AuditEvent / TrashEntry</td>
    <td>Who did what and recoverable deletion record.</td>
    <td>Append-only audit; Trash only for persisted soft-deleted roots.</td>
    <td>Transient draft discard creates neither. Persisted delete creates both as appropriate.</td>
  </tr>
</table>

## 9.2 Required Trading Signal and Trade Log Boundary

<table>
  <tr>
    <th>Canonical Rule - Time-safe signal evaluation<br/>Trading Signal event revisionı en az event_id, event_time, available_time, instrument_id, direction, signal_type ve source_record_id taşır; relevant ise suggested_entry_price, suggested_exit_price ve confidence eklenebilir. Backtest signalı event_time anında değil available_time sonrasında değerlendirebilir. Aynı eventin sonradan değiştirilmiş daha erken availabilitysi geçmiş runın anlamını değiştiremez; yeni revision gerekir.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Canonical Rule - Trade Log import evidence<br/>Trade Log, canlı signal generator değildir. TXT/CSV accepted separator guidance V18de comma, semicolon, tab ve pipe olarak görülür; Production importer bunları destekleyebilir fakat client-side DOM parser canonical importer değildir. Import sonucunda immutable source asset, parse report, skipped-row report, canonical trade-record revision ve validation evidence üretilir.</th>
  </tr>
</table>

## 9.3 Persistence, Revision, Snapshot and Stale Behavior

- A transient type choice creates no root and no MainboardWorkingItem. It has no effect on server composition hash or current Ready Report.

- A successful Save creates a root if absent and an immutable first revision. Meaning-changing edits create a later revision; current historical revision rows are not patched.

- A successful attach creates or updates a MainboardWorkingItem with explicit work_object_root_id + pinned_revision_id. String names and "latest" resolution are forbidden.

- A newer revision does not automatically replace a currently pinned Mainboard revision. UI must show newer revision availability and require explicit pin/attach action.

- Any attach, pin, detach, enable/disable or delete action changes Mainboard composition hash; matching prior Ready Report is marked STALE. RUN rejects stale/mismatched readiness server-side.

- A Backtest Run receives a Composition Snapshot and Run Manifest. Worker reads only pinned ids/asset checksums/policies; it never reads current DOM, browser file state or latest revision.

## 9.4 Async / Worker and Event Behavior

<table>
  <tr>
    <th>Operation</th>
    <th>Synchronous transaction responsibility</th>
    <th>Async worker responsibility</th>
    <th>Event / projection</th>
  </tr>
  <tr>
    <td>Trading Signal connector/import request</td>
    <td>Accept typed request, authorize, create request/job record, persist source reference.</td>
    <td>Fetch/normalize/validate signal data; preserve event/available time evidence.</td>
    <td>external_signal_ingestion_requested / completed / failed; UI projection updates durable status.</td>
  </tr>
  <tr>
    <td>Trade Log file import</td>
    <td>Store/refer immutable source asset; create ingestion job; return stable job id.</td>
    <td>Parse supported delimiters, map rows, validate schema, record skipped rows, create canonical revision/evidence.</td>
    <td>trade_log_import_requested / completed / failed; retry uses job/config rather than hidden DOM state.</td>
  </tr>
  <tr>
    <td>Save and attach</td>
    <td>Atomic revision + item attachment, policy and concurrency validation, hash recompute, Ready stale update.</td>
    <td>No heavy engine work in request.</td>
    <td>mainboard_item_attached; mainboard_composition_changed; ready_report_staled; audit/outbox.</td>
  </tr>
  <tr>
    <td>Delete persisted object</td>
    <td>Policy/preflight, soft delete, Trash entry, audit/outbox.</td>
    <td>Downstream search/cache/tool registry projection refresh; event retry if consumer fails.</td>
    <td>work_object_soft_deleted; mainboard_projection_changed. Root delete remains successful even if projection consumer retries.</td>
  </tr>
</table>

# 10. Agent Tool/API Eşdeğeri ve Sürekli Çalışma Sınırı

Add Outsource Signal menüsünü açmak, Agent için bir iş yeteneği değildir; bu yalnız insan UI navigasyonudur. Agentın eşdeğer gerçek yeteneği, aynı domain command/service katmanı üzerinden Trading Signal veya Trade Log root/revision üretmek, import/validation jobu istemek ve uygun compositiona explicit revision attach etmektir. Agentın ana araştırma döngüsü browserın açık kalmasına, Mainboard menüsüne hover yapılmasına, normal Lab Assistant chatine veya insan oturumuna bağlı değildir.

<table>
  <tr>
    <th>Human UI intent</th>
    <th>Agent Tool / API capability</th>
    <th>Policy / provenance</th>
    <th>UI bağımlılığı</th>
  </tr>
  <tr>
    <td>Choose Trading Signal</td>
    <td>agent.create_trading_signal_draft or create_trading_signal_revision</td>
    <td>Owner = Agent principal for Agent-created output; agent_run_id/task_id/provenance recorded.</td>
    <td>No browser/menu click.</td>
  </tr>
  <tr>
    <td>Choose Trade Log</td>
    <td>agent.request_trade_log_import / create_trade_log_revision</td>
    <td>Source asset/import job/reports attach to Agent-owned or authorized workspace context.</td>
    <td>No browser file selector; Tool Gateway receives source reference/artifact handle.</td>
  </tr>
  <tr>
    <td>Save and attach</td>
    <td>agent.attach_mainboard_item or agent.create_composition_snapshot</td>
    <td>Agent may use accessible/published working content; cannot mutate others objects without policy. Human Mainboard auto-attach is forbidden unless explicit workflow/policy authorizes it.</td>
    <td>No UI-only action path.</td>
  </tr>
  <tr>
    <td>Repair validation issue</td>
    <td>agent.inspect_import_report / agent.revise_external_work_object</td>
    <td>A new revision or follow-up task; original evidence preserved.</td>
    <td>No screen scraping.</td>
  </tr>
  <tr>
    <td>Delete own output</td>
    <td>agent.soft_delete_entity</td>
    <td>Agent may delete own output only; Trash restore/purge forbidden.</td>
    <td>No Trash UI dependence.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Agent boundary<br/>Normal discussion with Lab Assistant does not automatically create, attach, delete or reprioritize an external work object. A human directive that asks for an import or new source evaluation becomes a durable queued request and is consumed at a safe Agent checkpoint according to policy. Agent output is not silently attached to a human Default Mainboard.</th>
  </tr>
</table>

# 11. Validation, Hata, Concurrency ve Recovery Contract

<table>
  <tr>
    <th>Validation class</th>
    <th>Canonical check</th>
    <th>Example structured code</th>
    <th>UI / Agent recovery</th>
  </tr>
  <tr>
    <td>Type / schema</td>
    <td>item_kind must be exactly trading_signal or trade_log; child payload must match selected root family.</td>
    <td>INVALID_ITEM_KIND; PAYLOAD_KIND_MISMATCH</td>
    <td>Restart with correct type. Do not coerce package or mixed payload into another family.</td>
  </tr>
  <tr>
    <td>Time integrity</td>
    <td>Trading Signal events require available_time; no lookahead via event_time assumption.</td>
    <td>AVAILABLE_TIME_REQUIRED; AVAILABLE_TIME_INVALID</td>
    <td>Repair source mapping/policy. Create a new revision after correction.</td>
  </tr>
  <tr>
    <td>Source/import</td>
    <td>Trade Log asset must be present/valid; importer must produce reports/evidence before revision is usable.</td>
    <td>SOURCE_ASSET_REQUIRED; IMPORT_PENDING; IMPORT_FAILED; ROW_MAPPING_INVALID</td>
    <td>Inspect retained reports, correct file/mapping, retry import. Browser preview cannot override server result.</td>
  </tr>
  <tr>
    <td>Revision/attachment</td>
    <td>Specific root and revision must exist, be active/usable and match item kind.</td>
    <td>REVISION_NOT_USABLE; OBJECT_SOFT_DELETED; KIND_REVISION_MISMATCH</td>
    <td>Select valid revision or restore through Admin when eligible.</td>
  </tr>
  <tr>
    <td>Authorization</td>
    <td>Caller must have create/attach/edit/delete authority based on role, owner, visibility and workspace.</td>
    <td>AUTHENTICATION_REQUIRED; ACCESS_DENIED; OWNER_REQUIRED</td>
    <td>Sign in, obtain share/use access, ask owner/Admin, or create own derived object.</td>
  </tr>
  <tr>
    <td>Concurrency</td>
    <td>Expected board/item/draft version must match latest canonical state.</td>
    <td>CONCURRENCY_CONFLICT; STALE_WORKSPACE</td>
    <td>Reload state, compare, reapply or fork. Never auto-overwrite other revision/pin.</td>
  </tr>
  <tr>
    <td>Lifecycle/dependency</td>
    <td>Cannot delete item/root used by queued/running run; soft-deleted object cannot be newly attached.</td>
    <td>ACTIVE_RUN_DEPENDENCY; DELETE_FORBIDDEN; SOFT_DELETED_NOT_USABLE</td>
    <td>Finish/cancel run via correct lifecycle; restore only Admin; retry explicit action.</td>
  </tr>
  <tr>
    <td>Idempotency</td>
    <td>Repeated logical Save/Attach/Delete request with same idempotency key must not create duplicate roots/items/jobs.</td>
    <td>IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD</td>
    <td>Reuse the original response for same payload or generate a new key for a new logical request.</td>
  </tr>
</table>

# 12. Lifecycle, Audit ve Trash Etkileri

## 12.1 Lifecycle Transitions

<table>
  <tr>
    <th>Başlangıç</th>
    <th>Action</th>
    <th>Sonuç</th>
    <th>Audit / Trash / historical impact</th>
  </tr>
  <tr>
    <td>No draft</td>
    <td>Choose type</td>
    <td>Transient draft only.</td>
    <td>No audit, no revision, no Trash, no composition impact.</td>
  </tr>
  <tr>
    <td>Transient draft</td>
    <td>Discard</td>
    <td>Transient state removed.</td>
    <td>No Trash/audit. Child upload session may be abandoned/cleaned by TTL policy but does not become work object evidence unless server accepted asset.</td>
  </tr>
  <tr>
    <td>Transient valid child config</td>
    <td>Save Draft</td>
    <td>Root + immutable revision persists; may remain unattached.</td>
    <td>Create/revision audit; no Mainboard composition change unless explicit attach occurs.</td>
  </tr>
  <tr>
    <td>Saved revision</td>
    <td>Attach/pin to Mainboard</td>
    <td>MainboardWorkingItem points to exact revision; enabled default true.</td>
    <td>Attach audit/outbox; composition hash changes; Ready Report stale.</td>
  </tr>
  <tr>
    <td>Attached revision</td>
    <td>Create new revision</td>
    <td>Object gets newer immutable revision; existing item remains on old pinned revision until explicit pin.</td>
    <td>Revision audit; no automatic run/input change.</td>
  </tr>
  <tr>
    <td>Persisted active object</td>
    <td>Delete</td>
    <td>Root soft_deleted; active Mainboard row removed if allowed.</td>
    <td>Trash Entry + audit + outbox. Block if used by queued/running run. Historical completed manifests remain interpretable.</td>
  </tr>
  <tr>
    <td>Soft deleted</td>
    <td>Restore</td>
    <td>Same root and pre-delete current revision pointer reactivate.</td>
    <td>Admin only. Restore does not create a new revision; emits audit/outbox. Reattach only by explicit action if required.</td>
  </tr>
  <tr>
    <td>Soft deleted</td>
    <td>Permanent delete</td>
    <td>Purge job performs retention/dependency checks.</td>
    <td>Admin only. Not a normal UI delete. Tombstone/minimum audit provenance remains.</td>
  </tr>
</table>

## 12.2 Audit Event Minimums

<table>
  <tr>
    <th>Event family</th>
    <th>Minimum safe payload</th>
    <th>Do not put in audit payload</th>
  </tr>
  <tr>
    <td>external_work.created / revision.created</td>
    <td>actor/principal, root id/ref, revision id/ref, kind, owner, source summary, correlation_id, causation_id where applicable.</td>
    <td>Raw full CSV/TXT, credentials, tokens, secrets, unbounded binary/source content.</td>
  </tr>
  <tr>
    <td>trade_log.import.requested/completed/failed</td>
    <td>job id, source asset reference/checksum, parser/mapping version, count summary, skipped/invalid count, status, error code.</td>
    <td>Full raw trade ledger or sensitive source content in audit row.</td>
  </tr>
  <tr>
    <td>mainboard_item.attached / revision.pinned</td>
    <td>mainboard id, item id, kind, root/revision ids, prior/new composition hash, actor, reason.</td>
    <td>Hidden DOM labels as source of truth; latest revision inferred names.</td>
  </tr>
  <tr>
    <td>ready_report.staled</td>
    <td>old report id/hash, new composition hash, causative change event.</td>
    <td>Full unrelated form payload.</td>
  </tr>
  <tr>
    <td>soft_delete / restore / purge</td>
    <td>subject root/type/name snapshot, actor, preflight result, trash id, dependency summary, correlation_id.</td>
    <td>Raw source asset contents or personal credentials.</td>
  </tr>
</table>

# 13. Implementation Rules

1. Model Add Outsource Signal as an external-work type chooser, not as a Package Library type picker. PackageKind must not gain trading_signal or trade_log values.

2. Accept exactly two canonical item kinds at this entry surface: trading_signal and trade_log. Reject legacy package labels/enums in API payloads and persistence.

3. Do not persist an empty root/revision merely because the user clicked a submenu item. Initial selection creates only a transient unsaved draft; persistence begins at explicit Save Draft / Save and Attach.

4. Mark every transient external draft visibly as Unsaved and exclude it from Mainboard Composition Snapshot, Ready Check, Portfolio Allocation and RUN.

5. Persist every meaningful source/mapping/import change as a new immutable TradingSignalRevision or TradeLogRevision. Never patch a historical revision in place.

6. Attach a Mainboard item only with work_object_root_id plus pinned_revision_id. Display names, browser counters and latest-revision lookup must never determine the attached input.

7. Require Trading Signal events to carry a valid available_time and evaluate them only after that time. event_time is not permission to use future information.

8. Treat Trade Log as historical trade data, not as a live signal generator. Do not synthesize actionable entry events from a Trade Log without a separately defined canonical transformation.

9. Run Trade Log parsing/import/validation through durable ingestion workers. Client-side TXT/CSV parsing may provide preview UX only; it is not canonical evidence or a usable revision.

10. For raw import, retain immutable source asset reference, parse report, skipped-row report and validation evidence. Do not silently discard invalid rows without a report.

11. Use server-side authorization for every create, save, attach, pin, import, edit and delete command. UI hidden/disabled state and client-provided role/owner fields are not authority.

12. Include idempotency_key and expected workspace/item/draft version in every mutating persistence command. Same logical request must not create duplicate object roots, items or import jobs.

13. On attach, pin, enable/disable, delete or detach, recompute composition hash transactionally and mark matching Ready Reports stale. Do not use V18 backtestReady boolean as authority.

14. Do not automatically replace an existing Mainboard pinned revision when a newer external-object revision is saved. Show newer-revision availability and require explicit pin action.

15. Keep expanded/collapsed menu/row state outside domain mutation. It must not create a revision, stale a Ready Report or become an audit event.

16. Implement root delete as soft delete with preflight, Trash Entry, audit event and outbox event. Block delete for queued/running run manifest dependency; historical completed manifests remain readable.

17. Allow only Admin to list Trash, restore or permanently delete. User/Supervisor/Agent may have delete rights under normal policy but cannot restore or purge.

18. Expose the same real create/import/attach/revise/delete capabilities to Agent through Tool Gateway/API/domain service. Do not require browser automation, menu hover or human session state.

19. Do not auto-attach Agent output to a human Default Mainboard. Any human-visible attach/pin is an explicit, policy-checked composition action.

20. Return canonical server state after mutation and rehydrate the UI from it. Never show a success toast or remove a persisted row before backend success response.

# 14. Acceptance Tests

<table>
  <tr>
    <th>ID</th>
    <th>Senaryo</th>
    <th>Beklenen doğrulanabilir sonuç</th>
  </tr>
  <tr>
    <td>AOS-01</td>
    <td>Hover/focus type chooser</td>
    <td>Mainboard dropdown içindeki Add Outsource Signal parent item only exposes Trading Signal and Trade Log. Keyboard navigation matches pointer behavior; no backend mutation occurs.</td>
  </tr>
  <tr>
    <td>AOS-02</td>
    <td>No default type</td>
    <td>Opening chooser preselects neither type. Continuing without a choice yields the final UI message: &quot;Choose Trading Signal or Trade Log before continuing.&quot;</td>
  </tr>
  <tr>
    <td>AOS-03</td>
    <td>Legacy payload rejected</td>
    <td>Client sends item_kind=signal_package or trade_log_package. Server returns INVALID_ITEM_KIND; no PackageKind expansion, root, revision or item is created.</td>
  </tr>
  <tr>
    <td>AOS-04</td>
    <td>Trading Signal draft</td>
    <td>Choosing Trading Signal creates an Unsaved transient draft view. It has no root/revision/item id and is absent from server Ready Check composition.</td>
  </tr>
  <tr>
    <td>AOS-05</td>
    <td>Trade Log draft</td>
    <td>Choosing Trade Log creates an Unsaved transient draft view. No import job starts until an explicit child upload/import action occurs.</td>
  </tr>
  <tr>
    <td>AOS-06</td>
    <td>Transient discard</td>
    <td>Discarding either unsaved draft removes it without Trash Entry, audit event, composition hash change or Ready Report stale event.</td>
  </tr>
  <tr>
    <td>AOS-07</td>
    <td>Signal available time</td>
    <td>Attempting to save a Trading Signal revision whose event source cannot supply valid available_time returns AVAILABLE_TIME_REQUIRED/INVALID; attach cannot proceed.</td>
  </tr>
  <tr>
    <td>AOS-08</td>
    <td>Trade Log background import</td>
    <td>TXT/CSV upload results in immutable source asset reference and durable job id. Browser refresh does not cancel parsing/validation. Job produces parse/skipped-row report and validation evidence.</td>
  </tr>
  <tr>
    <td>AOS-09</td>
    <td>Client parser is non-authoritative</td>
    <td>A local preview that appears valid cannot create an attached usable Trade Log without a successful server import/validation revision.</td>
  </tr>
  <tr>
    <td>AOS-10</td>
    <td>Save and attach atomicity</td>
    <td>Successful Save and Attach returns root, immutable revision, MainboardWorkingItem, explicit pin and new composition hash. UI rehydrates from response; older Ready Report becomes STALE.</td>
  </tr>
  <tr>
    <td>AOS-11</td>
    <td>Specific revision pin</td>
    <td>Save a newer Trading Signal/Trade Log revision. Existing Mainboard item continues to reference prior pinned revision until explicit pin action; no implicit latest resolution occurs.</td>
  </tr>
  <tr>
    <td>AOS-12</td>
    <td>Type/payload mismatch</td>
    <td>A Trading Signal attach request carrying a Trade Log revision id returns KIND_REVISION_MISMATCH with no partial item creation.</td>
  </tr>
  <tr>
    <td>AOS-13</td>
    <td>Authorization</td>
    <td>User can create own object; Supervisor cannot edit/delete other owner external object; Admin can; Agent cannot use human login UI as authority. Direct API request is policy-checked.</td>
  </tr>
  <tr>
    <td>AOS-14</td>
    <td>Concurrency</td>
    <td>Two sessions attach/pin against same stale Mainboard version. Exactly one succeeds; other receives CONCURRENCY_CONFLICT/STALE_WORKSPACE; no lost pin/order update occurs.</td>
  </tr>
  <tr>
    <td>AOS-15</td>
    <td>Idempotency</td>
    <td>Duplicate Save/Attach POST with same idempotency key and payload returns same root/revision/item outcome and does not create duplicates.</td>
  </tr>
  <tr>
    <td>AOS-16</td>
    <td>Expanded/collapsed presentation</td>
    <td>Opening/closing row changes only UI preference. It generates no revision, audit event, composition hash change or Ready Report stale state.</td>
  </tr>
  <tr>
    <td>AOS-17</td>
    <td>Delete dependency block</td>
    <td>Deleting a Trading Signal/Trade Log referenced by QUEUED or RUNNING Backtest Run is blocked with ACTIVE_RUN_DEPENDENCY and no Trash Entry.</td>
  </tr>
  <tr>
    <td>AOS-18</td>
    <td>Soft delete historical integrity</td>
    <td>Deleting an unblocked persisted Trade Log creates Trash Entry/audit/outbox and removes it from active selectors. Completed historical Result still resolves name/provenance from pinned manifest snapshot.</td>
  </tr>
  <tr>
    <td>AOS-19</td>
    <td>Trash restriction</td>
    <td>User/Supervisor/Agent cannot list or restore Trash item via direct API. Admin can restore and purge subject to lifecycle/retention policy.</td>
  </tr>
  <tr>
    <td>AOS-20</td>
    <td>Agent parity</td>
    <td>Agent creates/imports/attaches an external work object using Tool Gateway/domain commands without opening UI. Agent-created output owner/provenance is recorded; it is not auto-attached to a human board.</td>
  </tr>
  <tr>
    <td>AOS-21</td>
    <td>Run/result boundary</td>
    <td>Add Outsource Signal selection or save never creates Backtest Result. Only a succeeded asynchronous Run after valid Ready Check may create immutable Result.</td>
  </tr>
</table>

# 15. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Durum</th>
    <th>Sonuç / not</th>
  </tr>
  <tr>
    <td>Master authority</td>
    <td>Evet</td>
    <td>Modül 9 ve CR-01 ayrımı üst kaynak kabul edildi; V18 labels server rule olarak kullanılmadı.</td>
  </tr>
  <tr>
    <td>Scope discipline</td>
    <td>Evet</td>
    <td>Bu belge type chooser/factory boundarysini tanımlar. Trading Signal/Trade Log detay alanları yalnız referans olarak anıldı; child sayfalarla duplicate edilmedi.</td>
  </tr>
  <tr>
    <td>Package boundary</td>
    <td>Evet</td>
    <td>Trading Signal/Trade Log Package Library package type olarak anlatılmadı; legacy labels alignment note altında düzeltildi.</td>
  </tr>
  <tr>
    <td>Root/revision/snapshot</td>
    <td>Evet</td>
    <td>Transient draft, persisted root/revision, explicit pin, composition hash ve stale Ready Report ayrımı açık yazıldı.</td>
  </tr>
  <tr>
    <td>UI vs backend separation</td>
    <td>Evet</td>
    <td>Hover/menu/client counter/backtestReady observationları Production authorityden ayrıldı.</td>
  </tr>
  <tr>
    <td>Agent parity</td>
    <td>Evet</td>
    <td>Agent Tool Gateway/API/domain service pathı tanımlandı; browser/session/chat bağımlılığı yasaklandı.</td>
  </tr>
  <tr>
    <td>Async work</td>
    <td>Evet</td>
    <td>Trade Log import ve signal ingestion job/worker, source asset/report/evidence davranışı tanımlandı.</td>
  </tr>
  <tr>
    <td>Trash/audit</td>
    <td>Evet</td>
    <td>Transient discard ile persisted soft delete ayrıldı; Trash/restore/purge Admin only olarak korundu.</td>
  </tr>
  <tr>
    <td>Run/result distinction</td>
    <td>Evet</td>
    <td>Selection/save Result üretmez; only succeeded Run Result üretebilir.</td>
  </tr>
  <tr>
    <td>Implementation Decisions identified</td>
    <td>Evet</td>
    <td>ID-03-01 transient draft UX ve ID-03-02 helper affordance açıkça non-canonical gap resolution olarak etiketlendi.</td>
  </tr>
</table>

## 15.1 Implementation Alignment Notes

<table>
  <tr>
    <th>ID</th>
    <th>Ayrım</th>
    <th>Üretim hizalama kararı</th>
  </tr>
  <tr>
    <td>IA-03-01</td>
    <td>V18 seçime basınca client DOMa hemen row ekler; Master yalnız persisted itemlerin backtest inputu olduğunu söyler.</td>
    <td>Production row must be explicitly marked Unsaved until root/revision save succeeds. Unsaved row is not item projection and has no snapshot/Ready/Run effect.</td>
  </tr>
  <tr>
    <td>IA-03-02</td>
    <td>V18de Trading Signal Package / Trade Log Package legacy wordingi ve Add Package signal/tradeLog paths bulunur; Master CR-01 bunu yasaklar.</td>
    <td>All production navigation, route, enum, database and UI labels use Trading Signal / Trade Log external working object. Legacy prototype paths are removed/migrated.</td>
  </tr>
  <tr>
    <td>IA-03-03</td>
    <td>V18 submenu üzerinde info control yoktur; Handoff information catalogu UI-ready explanation ister.</td>
    <td>Add minimal ⓘ help for Add Outsource Signal/object type/unsaved draft as usability layer. It does not change backend, permission, or object schema.</td>
  </tr>
  <tr>
    <td>IA-03-04</td>
    <td>Master §4.4 only names Add Outsource Signal flow without prescribing exact click-to-draft UX.</td>
    <td>Keep nested type chooser but use transient draft before save. This preserves prototype discoverability and avoids empty persisted roots. Decision can be revisited only if a future multi-step wizard is explicitly approved.</td>
  </tr>
</table>
