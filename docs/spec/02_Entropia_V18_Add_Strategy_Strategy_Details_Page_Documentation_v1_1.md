---
title: "Entropia V18 — Add Strategy / Strategy Details Page Documentation v1.1"
page_number: 2
document_type: "Page implementation specification"
source_document: "Entropia_V18_Add_Strategy_Strategy_Details_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Add Strategy / Strategy Details Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18  |  PAGE DOCUMENTATION  |  ADD STRATEGY / STRATEGY DETAILS
> **Original DOCX footer:** Entropia V18 | Add Strategy / Strategy Details | Page  of

# ADD STRATEGY / STRATEGY DETAILS

*Sayfa Dokümantasyonu [2/22] | Entropia V18 | Production V1 implementation specification*

<table>
  <tr>
    <th>BELGE AMACI<br/>Bu doküman Add Strategy ile başlayan Strategy draft oluşturma akışını ve açılan Strategy Details editörünü uçtan uca tanımlar. Strategy Details; bir stratejinin veri bağlamını, giriş-çıkış karar grafiğini, risk ve sizing kurallarını, scaling/filtre/conflict davranışını tek sürümlü davranış sözleşmesine çevirir. V18 görünür formu ile Production V1 draft, immutable revision, dependency pinning ve engine değerlendirme doğrusu açık biçimde ayrılmıştır.</th>
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
    <td>Entropia V18 — Add Strategy / Strategy Details Page Documentation</td>
  </tr>
  <tr>
    <td>Belge kodu</td>
    <td>ENT-V18-PG-02-ADD-STRATEGY-DETAILS</td>
  </tr>
  <tr>
    <td>Sürüm</td>
    <td>v1.1</td>
  </tr>
  <tr>
    <td>Kapsam</td>
    <td>Mainboard içindeki Add Strategy entry action; yeni Strategy draftı; Strategy Details üç kolonlu editör; sections 1–10; generic settings/info popover; Save Strategy Revision ve Clear davranışı.</td>
  </tr>
  <tr>
    <td>Kapsam dışı</td>
    <td>Mainboard composition listesi/Ready Check/RUN hostu; Add Outsource Signal; Trading Signal/Trade Log detayları; Package Library/Create Package/Pre-Check; Portfolio Allocation formu; Results/History; Panel/Trash UI. Bu alanlar yalnız dependency veya lifecycle sınırı olarak anılır.</td>
  </tr>
  <tr>
    <td>Kaynak otoritesi</td>
    <td>1) Master Technical Reference v1.0, 2) V18 ana HTML, 3) Handoff v1.1, 4) 2.3 POSITION ENTRY LOGIC örnek dokümanı.</td>
  </tr>
  <tr>
    <td>Canonical rule</td>
    <td>Master açık karar veriyorsa HTML demo davranışı veya örnek metin override edemez. Master boşluğu açık “Implementation Decision — Non-Canonical Gap Resolution” etiketiyle kapanır.</td>
  </tr>
  <tr>
    <td>Teslim sınırı</td>
    <td>Bu dosya yalnız bu sayfanın DOCX dokümanıdır; HTML preview, ara HTML veya başka sayfa dokümanı içermez.</td>
  </tr>
</table>

# Kaynak İzlenebilirliği ve Sayfa Sınırı

<table>
  <tr>
    <th>Kaynak</th>
    <th>İlgili bölüm / UI referansı</th>
    <th>Bu belgede kullanımı</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0</td>
    <td>Modül 0 §§5–9; Modül 1 §§5–8; Modül 2 root/revision/lifecycle; Modül 3 soft delete/Trash; Modül 4–5 data timing; Modül 7–8 Package/Pre-Check; Modül 9 §4.1 Strategy item; Modül 10 Strategy Details §§1–20; Modül 12 Ready/Run; Modül 19 API contract; CR-01/CR-09.</td>
    <td>Production V1 domain, revision, policy, engine, Agent parity, async/recovery ve audit doğrusu.</td>
  </tr>
  <tr>
    <td>V18 ana HTML</td>
    <td>`addStrategyBox`; `createDetailsContent`; entry/exit/stop/scaling builder functions; `initializeStrategyDetails`; `clearStrategyDetails`; `saveStrategyVersion`; `infoTexts`; `.strategy-details` three-column grid; all select/input default values.</td>
    <td>Kullanıcının gördüğü gerçek label, default, visible card, dropdown, popover, disabled/soluk state ve prototype interaction hedefi.</td>
  </tr>
  <tr>
    <td>Handoff v1.1</td>
    <td>Sections 2–10; Source Traceability Map; Interaction State Matrix; Field Contract Matrix; Information Content Catalog; command/recovery; lifecycle/audit; implementation rules; acceptance tests.</td>
    <td>Bu belgenin zorunlu üretim ve kalite standardı.</td>
  </tr>
  <tr>
    <td>2.3 POSITION ENTRY LOGIC örneği</td>
    <td>Signal/Indicator/Condition hierarchy; typed configuration; dependency validation; deterministic engine; decision trace; Agent parity.</td>
    <td>Position Entry bölümünün teknik derinlik, kavram açıklama ve acceptance yaklaşımı için referans; canonical domain kaynağı değil.</td>
  </tr>
</table>

<table>
  <tr>
    <th>SCOPE BOUNDARY<br/>Strategy Details, Mainboard satırında host edilir; fakat Mainboard yalnızca Strategy itemin pinned revisionına işaret eder. Strategy form alanları bu dokümanda tanımlanır; Ready Check/RUNın kompozisyon, allocation ve Result davranışı yalnız gerekli integration sınırı kadar anılır.</th>
  </tr>
</table>

# 1. Amaç ve Sistem İçindeki Yer

Strategy, market/veri bağlamını, karar mantığını, execution varsayımlarını, risk/sizing davranışını ve conflict çözümünü bir araya getiren test edilebilir çalışma nesnesidir. Strategy Details, bu nesnenin editable draftını düzenleyen insan kontrol yüzeyidir. Save sonrasında form verisi serbest UI metni olarak kalmaz; typed canonical Strategy Config payloadına dönüşür ve immutable Strategy Revision olarak kaydedilir.

Bu sayfa, “bir strateji ne zaman pozisyon açar; nasıl yürütür; ne zaman çıkar; hangi risk ve exposure sınırlarına uyar; eşzamanlı olayları nasıl çözer?” sorusuna deterministik cevap üretir. Backtest Engine canlı DOM veya kullanıcının açık formu üzerinden değil, yalnız pinlenmiş revision/snapshot/manifest üzerinden çalışır.

## 1.1 Araştırma ve Backtest Zincirindeki Konumu

<table>
  <tr>
    <th>Hypothesis / research task<br/>  -&gt; Add Strategy creates editor draft<br/>  -&gt; Strategy Details config graph<br/>  -&gt; Save Strategy Revision (immutable) + dependency refs<br/>  -&gt; Mainboard item pins revision<br/>  -&gt; Ready Check / Composition Snapshot<br/>  -&gt; Backtest Run (async worker)<br/>  -&gt; Succeeded Run -&gt; immutable Backtest Result + diagnostics<br/>  -&gt; Human / Agent interpretation -&gt; next revision or new hypothesis</th>
  </tr>
</table>

## 1.2 Bu Sayfanın Tanımlamadığı Davranışlar

• Package creation/publish: Indicator/Condition/Embedded System Package yaratma veya Pre-Check bu sayfanın görevi değildir. Strategy Details yalnız erişilebilir, uygun revisionları referans alır.

• Trading Signal ve Trade Log: Bunlar Package Library package type değildir; Add Outsource Signal altında oluşan external Mainboard Working Itemlardır. Strategy Details içindeki Condition Package seçimi Trading Signal veya Trade Log paketi seçimi olamaz.

• Ready Check/RUN worker orchestration: Strategy Save başarılı olmakla Backtest Ready aynı şey değildir. Ready Check, Mainboard kompozisyonu için ayrı immutable rapor üretir; RUN ayrı async job yaratır.

• Portfolio Allocation: Strategy Initial Capital ve risk/sizing alanları burada tanımlanır. Shared Equity Allocation aktifse run-level allocation cap dış sınır olarak uygulanır; bu sayfa Allocation Plan formunu yönetmez.

• Trash UI: Strategy soft delete/restore/purge kuralları bu sayfanın lifecycle bağıdır; Trash ekranı yalnız Adminin ayrı sayfasıdır.

## 1.3 Kavramsal Terimler

<table>
  <tr>
    <th>Terim</th>
    <th>Canonical kısa tanım</th>
    <th>Bu sayfadaki kullanım</th>
  </tr>
  <tr>
    <td>Strategy Root</td>
    <td>Strategy nesnesinin kalıcı kimliği; revisionlardan ayrı yaşar.</td>
    <td>Mainboard itemi Strategy Roota ve seçilmiş Strategy Revisiona bağlanır.</td>
  </tr>
  <tr>
    <td>Editor Draft</td>
    <td>Eksik/yarım blok içerebilen mutable çalışma statei.</td>
    <td>Kullanıcı formu dener; Draft engine inputu değildir.</td>
  </tr>
  <tr>
    <td>Strategy Revision</td>
    <td>Save ile üretilen immutable davranış sözleşmesi.</td>
    <td>Backtest/Ready Checkin referans alabileceği tek Strategy config sürümüdür.</td>
  </tr>
  <tr>
    <td>Package Revision</td>
    <td>Indicator/Condition/ESP gibi reusable logic nesnesinin immutable sürümü.</td>
    <td>Her dependency `root_id + revision_id` ile pinlenir; UI adı tek başına yeterli değildir.</td>
  </tr>
  <tr>
    <td>Signal Block</td>
    <td>Birden fazla Indicator Block sonucunu entry/exit düzeyinde birleştiren üst karar grafiği.</td>
    <td>Entry ve Exit Logic içinde ayrı ayrı bulunur.</td>
  </tr>
  <tr>
    <td>Condition Block</td>
    <td>Bağlı Indicator Blockun native trigger/output sonucunu doğrulayan, daraltan veya tetik oluşturan alt koşul.</td>
    <td>Tek başına tüm Strategy için entry/exit üretemez.</td>
  </tr>
  <tr>
    <td>Canonical payload</td>
    <td>Formdan normalize edilmiş typed enum/number/reference yapısı.</td>
    <td>Engine serbest UI labelı değil bu payloadı yorumlar.</td>
  </tr>
  <tr>
    <td>Pinned reference</td>
    <td>Root kimliğiyle birlikte kesin revision kimliği taşıyan dependency bağlamı.</td>
    <td>Latest/current otomatik takip edilmez.</td>
  </tr>
  <tr>
    <td>Decision trace</td>
    <td>Bir actionın üretildiği veya engellendiği nedenleri taşıyan makine-okunur iz.</td>
    <td>Backtest diagnostics ve Agent reasoning artifacti için gerekir.</td>
  </tr>
  <tr>
    <td>Disabled semantic boundary</td>
    <td>Soluk/disabled yapı yalnız estetik değil; `enabled=false` ve engine dışı olma anlamı taşır.</td>
    <td>Sections 5–8 için zorunlu state kuralıdır.</td>
  </tr>
</table>

# 2. Erişim, Görünürlük, Sahiplik ve Yetki

UI bir paneli gösterse veya bir butonu enabled yapsa bile authorization doğrusu değildir. Server her query ve mutationda caller principal, role, ownership, visibility, lifecycle state, dependency state ve operation türünü yeniden doğrular. Client body içindeki role/owner alanı otorite değildir.

<table>
  <tr>
    <th>Principal</th>
    <th>Sayfayı görme</th>
    <th>Draft create/edit/save</th>
    <th>Read/use dependency</th>
    <th>Soft delete</th>
    <th>Restore/purge</th>
    <th>Agent / özel not</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Strategy Details formu kalıcı iş için açılmaz; yalnız public/demo route varsa kısıtlı tanıtım görünür.</td>
    <td>Yok.</td>
    <td>Yok veya public read policy.</td>
    <td>Yok.</td>
    <td>Yok.</td>
    <td>Productionda V18 guest/user demo statei gerçek User değildir.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Kendi, explicitly shared veya published/system kaynak bağlı Strategyleri görür.</td>
    <td>Kendi Strategy Draft/Rootu üzerinde; shared kaynakları use edebilir ancak mutate edemez.</td>
    <td>Own/shared/published scope.</td>
    <td>Kendi rootu için soft delete.</td>
    <td>Yok.</td>
    <td>Rationale Family editing exception dışında normal owner policy geçerlidir.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Erişilebilir shared working contenti görür.</td>
    <td>Yalnız own Strategy Draft/Root üzerinde edit/save; başkasının strategy’sini clone/use edebilir.</td>
    <td>Geniş erişilebilir working scope.</td>
    <td>Yalnız own root.</td>
    <td>Yok.</td>
    <td>Queued directive gönderebilir; Agent işi UIya bağlı değildir.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm erişilebilir Strategyler ve dependencies.</td>
    <td>Tüm root/draft/revisionlarda policy override ile yönetebilir.</td>
    <td>Tümü.</td>
    <td>Tüm normal resource rootları soft delete edebilir.</td>
    <td>Yalnız Admin restore/permanent delete.</td>
    <td>Role/Trash authority Admin sınırındadır.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>UI görünürlüğü zorunlu değildir; Agent Tool Gateway ile read/use yapar.</td>
    <td>Yalnız Agent-owned output draft/root/revisionlarını create/edit/save/delete eder.</td>
    <td>Policy izinli system working content + published/shared.</td>
    <td>Yalnız kendi outputu.</td>
    <td>Yok.</td>
    <td>Agent human login değildir; runtime service principal ile çalışır.</td>
  </tr>
</table>

<table>
  <tr>
    <th>CANONICAL RULE — RATIONALE FAMILY EXCEPTION<br/>Rationale Family ve Package Rationale Assignment global shared-editing exceptiondır. Bu Strategy formu içindeki Rationale Family seçimi yalnız own-resource policy ile filtrelenmez; bütün yetkili aktörler shared family kartlarını kullanabilir/düzenleyebilir. Bu istisna Strategy Root edit hakkını genişletmez.</th>
  </tr>
</table>

## 2.1 V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Katman</th>
    <th>Davranış</th>
  </tr>
  <tr>
    <td>V18 Interface Behavior</td>
    <td>`Add Strategy` menü actionı JavaScriptte yeni `.strategy-package` row ve kapalı `.strategy-details` paneli oluşturur. `Created By` alanına `currentUser || guest` yazılır. Save button yalnız row title ve `versionSaved=true` local stateini günceller; UI herhangi bir gerçek revision/authorization/dependency call yapmaz.</td>
  </tr>
  <tr>
    <td>Production Backend Behavior</td>
    <td>Add Strategy authenticated actor için mutable Strategy Draft bootstrap eder veya client transient draft başlatır; kalıcı Strategy Root/Revision yalnız Save Strategy Revision commandi başarılı olunca oluşur. Created By, server principal contextinden gelir. Save atomik validation, dependency resolution, immutable revision, audit ve gerekli Mainboard item pinning işlemidir.</td>
  </tr>
  <tr>
    <td>Implementation Alignment Note</td>
    <td>V18deki “Save as Strategy Package” etiketi canonical ayrımla çelişmeye açıktır. Production V1 button labelı Save Strategy Revision olmalıdır. Strategy Package üretmek ayrı Package/Create Package akışıyla yapılır; Strategy Details Save normalde Mainboard Strategy working itemın revisionını üretir/pinler.</td>
  </tr>
</table>

# 3. Arayüz Yerleşimi, Navigasyon ve Görünme Koşulları

V18de Strategy Details, Mainboarddaki Strategy rowunun arrow düğmesi ile expandable panel olarak açılır. Panel açıkken row open state/visual blue vurgusu alır; arrow `▼` yerine `▲` olur. Productionda bu expanded/collapsed state yalnız presentation preferenceidir; Strategy Revision üretmez, Ready Check fingerprintini değiştirmez ve audit event oluşturması gerekmez.

<table>
  <tr>
    <th>Bölge</th>
    <th>V18 görünür bileşenleri</th>
    <th>Production sorumluluğu / görünme koşulu</th>
  </tr>
  <tr>
    <td>Entry action</td>
    <td>Mainboard menu &gt; `Add Strategy`.</td>
    <td>Authenticated create policy. Aksiyon yeni Strategy Draft başlatır; Mainboard sayfa dokümanındaki row host davranışı dışında Strategy config bu sayfada tanımlanır.</td>
  </tr>
  <tr>
    <td>Strategy row host</td>
    <td>Başlık/metin, expand arrow, × delete.</td>
    <td>Bu belgenin scopeunda yalnız Strategy Detailsin host/entry bağı vardır. Delete ayrı Mainboard/Trash lifecycle sınırıdır; referans inputu olarak edited draftın konumu gösterilir.</td>
  </tr>
  <tr>
    <td>Details grid</td>
    <td>3 kol: SETUP &amp; DATA, DECISION LOGIC, RISK MANAGEMENT. Dar viewportta kol stacked akışa döner; panel yatay overflowa izin verir.</td>
    <td>Form sectionleri read model/draft state ile hydrate edilir; responsive layout domain semanticsini değiştirmez.</td>
  </tr>
  <tr>
    <td>Setup &amp; Data</td>
    <td>1. Strategy Context; 2. Data &amp; Execution; conditional Limit Order Details; Intrabar/Funding.</td>
    <td>Identity, data reference, execution assumptions ve capital base payloadı.</td>
  </tr>
  <tr>
    <td>Decision Logic</td>
    <td>3. Position Entry Logic; 4. Position Exit Logic; dynamic Indicator/Condition blocks.</td>
    <td>Typed entry/exit decision graphı. Her block UUID + display order taşır.</td>
  </tr>
  <tr>
    <td>Risk Management</td>
    <td>5. Protection/Stop; 6. Position Sizing; 7. Scaling; 8. Restrictions; 9. Conflict/Position Handling.</td>
    <td>Risk/position state machine, feature toggles ve deterministic conflict policy.</td>
  </tr>
  <tr>
    <td>Sticky action bar</td>
    <td>10. Save as Strategy Package; Clear.</td>
    <td>Production: Save Strategy Revision; Clear Draft. Save pendingde bar actionları duplicate submit engeller; sticky UI yalnız usabilitydir.</td>
  </tr>
  <tr>
    <td>Info popovers</td>
    <td>ⓘ buttons fixed, draggable V18 popover olarak görünür.</td>
    <td>Aç/kapat/drag UI stateidir. Content catalogta tanımlı yardım metni render edilir; popover form statei veya validationı değiştirmez.</td>
  </tr>
  <tr>
    <td>Indicator Settings button</td>
    <td>V18 görünür buton; generic settings modalının gerçek persistencei yok.</td>
    <td>Package revision `parameter_schema`dan üretilen modal/drawer. Cancel draftı değiştirmez; Apply typed strategy-local override patch üretir.</td>
  </tr>
  <tr>
    <td>Limit Order Details</td>
    <td>Order Type Limit Order veya Stop-Limit Order seçilince açılır; V18de varsayılan Market Order iken gizli.</td>
    <td>Hidden panelin valuesi engineye girmez. Limit/stop-limit seçimi conditional requirednessi aktive eder.</td>
  </tr>
</table>

## 3.1 Strategy Details Bölüm Envanteri

<table>
  <tr>
    <th>No</th>
    <th>Başlık</th>
    <th>V18 default / başlangıç görünümü</th>
    <th>Production semantic boundary</th>
  </tr>
  <tr>
    <td>1</td>
    <td>Strategy Context</td>
    <td>Name: STRATEGY N; Rationale/Market boş; Direction Long &amp; Short; Status Research Only; Created By readonly.</td>
    <td>Kimlik ve discovery layer; Strategy Root/Revision identity değil editor metadata/configdir.</td>
  </tr>
  <tr>
    <td>2</td>
    <td>Data &amp; Execution</td>
    <td>Data source boş; range 2020-01-01…2025-12-31; capital 10000; execution boş; Market Order; cost fields boş.</td>
    <td>Data revision + execution model deterministic fill assumptionsına dönüşür.</td>
  </tr>
  <tr>
    <td>3</td>
    <td>Position Entry Logic</td>
    <td>Rule: Required + Minimum Supporting; count 1; first Indicator/Condition placeholders boş; trigger boş; block requirement Required.</td>
    <td>Entry graph zorunlu ve engine active. Trigger Source condition conditional requirementini belirler.</td>
  </tr>
  <tr>
    <td>4</td>
    <td>Position Exit Logic</td>
    <td>Applies Long; Close 100%; partial aftermath Move Stop to Entry; rule minimum supporting 1; first exit indicator boş.</td>
    <td>Exit graph açık/valid blok varsa active; boş placeholder draft engine rule değildir.</td>
  </tr>
  <tr>
    <td>5</td>
    <td>Protection / Stop Logic</td>
    <td>Logic stop, Percentage Stop 1.00%, Trailing 2.00%/0.80% enabled; Absolute stop disabled.</td>
    <td>Her rule feature toggle ile semantic active/inactive. Stop engine reason/trigger/fill data yazmalıdır.</td>
  </tr>
  <tr>
    <td>6</td>
    <td>Position Sizing</td>
    <td>Base Position Size selected; input blank; Risk/Formula disabled; leverage mode Isolated; limits blank; signal strength no adjustment.</td>
    <td>Tam olarak bir sizing method active. Disabled methods payload/engine dışındadır.</td>
  </tr>
  <tr>
    <td>7</td>
    <td>Scaling Logic</td>
    <td>Timeframe same; custom sequence disabled; Price/Logic scaling method ikisi de unselected/disabled; add size = % of initial / 50; limits blank.</td>
    <td>Method seçilmedikçe `scaling.enabled=false`; visible values only inactive draft state.</td>
  </tr>
  <tr>
    <td>8</td>
    <td>Restrictions / Filters</td>
    <td>ANY rule; Volatility/Spread/Volume/Date Blackout/Max Daily Loss/Consecutive Loss checked; diğerleri unchecked.</td>
    <td>Her enabled filter engine eligibility/action graphına girer; disabled filter payloadta inactive kalır.</td>
  </tr>
  <tr>
    <td>9</td>
    <td>Conflict / Position Handling</td>
    <td>Her dropdown first option ile defaultlanır.</td>
    <td>Every option engine event priority/resolution policy enumuna dönüşür; UI label tek başına karar değildir.</td>
  </tr>
  <tr>
    <td>10</td>
    <td>Save / Package Actions</td>
    <td>Save as Strategy Package + Clear.</td>
    <td>Save Strategy Revision + Clear Draft; atomik validation/revision/audit; Clear saved revisionı silmez.</td>
  </tr>
</table>

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen</th>
    <th>Varsayılan</th>
    <th>Active / visible koşulu</th>
    <th>Disabled/hidden iken payload / engine etkisi</th>
    <th>State preserve / reset / recovery</th>
  </tr>
  <tr>
    <td>New Add Strategy row</td>
    <td>V18de `STRATEGY N`, panel closed, unsaved local DOM.</td>
    <td>Authenticated create action.</td>
    <td>Productionda unsaved transient draft Mainboard snapshot/Ready Check/RUN inputu değildir.</td>
    <td>Save ilk revisionı üretir ve itemi pinler. Close/open sadece UI. User leaves: local draft için explicit discard warning veya server draft autosave policy gerekir.</td>
  </tr>
  <tr>
    <td>Limit Order Details</td>
    <td>Hidden because Market Order selected.</td>
    <td>Order Type = Limit Order veya Stop-Limit Order.</td>
    <td>`limit_order` subtree omitted/`enabled=false`; stale hidden values engineye sızmaz. Stop Orderda limit fields kullanılmaz.</td>
    <td>Order type Market/Stopa dönünce values draftta korunabilir ama inactive. Limit/Stop-Limit tekrar seçilince prior values restore edilir; incompatible fill policy reset with warning.</td>
  </tr>
  <tr>
    <td>Entry Indicator/Condition blocks</td>
    <td>First placeholder visible.</td>
    <td>At least one active Indicator Block required for saved config. Trigger controls condition dependency.</td>
    <td>Blank/invalid Dynamic Block draftta olabilir; revision payloadta active graph node olamaz.</td>
    <td>Package change compatibilityyi tekrar çözer; incompatible condition references clear edilir and warning shown. Remove deletes node UUID from draft graph.</td>
  </tr>
  <tr>
    <td>Exit Logic placeholder</td>
    <td>Section visible; first indicator blank.</td>
    <td>At least one valid exit block selected/filled.</td>
    <td>Blank placeholder no exit graph node; engine ignores it.</td>
    <td>Indicator selected after default condition: V18 demo condition is reset/re-filtered; never preserve incompatible condition silently.</td>
  </tr>
  <tr>
    <td>Logic-Based Stop Block</td>
    <td>Block 1 enabled V18; dynamic additional blocks can be added.</td>
    <td>Checkbox enabled and complete indicator/condition contract.</td>
    <td>`enabled=false`; child references not in active evaluator/manifest dependency set.</td>
    <td>Disable preserves local values. Removing block detaches children/refs from draft. Re-enable validates current package revision again.</td>
  </tr>
  <tr>
    <td>Percentage/Trailing/Absolute Stop</td>
    <td>Percentage + trailing enabled; absolute disabled.</td>
    <td>Checkbox each rule.</td>
    <td>Inactive rule not evaluated, not reported as active risk protection.</td>
    <td>Disable preserves values. Re-enable uses stored values but validates range/data capability; empty required child blocks error only when enabled.</td>
  </tr>
  <tr>
    <td>Sizing method group</td>
    <td>Base Position Size selected; Risk/Formula panels soluk.</td>
    <td>Exactly one selector active.</td>
    <td>Nonselected method values may stay in draft but canonical payload carries only selected `method`; engine sees no alternative.</td>
    <td>Switching method preserves prior drafts per method; selecting back restores last valid values. Save validates selected method only plus global caps.</td>
  </tr>
  <tr>
    <td>Signal Strength Adjustment</td>
    <td>No Signal Strength Adjustment selected.</td>
    <td>Adjustment enum non-none AND needed Condition Package rules valid.</td>
    <td>No adjustment: condition rows are not evaluated; no multiplier/band in engine payload.</td>
    <td>Changing to No retains draft config inactive. Re-enable revalidates packages and caps.</td>
  </tr>
  <tr>
    <td>Scaling Logic</td>
    <td>No additional-layer method selected; method panels disabled.</td>
    <td>Exactly one: Price-Distance OR Logic-Based.</td>
    <td>`scaling.enabled=false`; all child values and references are ignored by engine and excluded from manifest active dependencies.</td>
    <td>Method switch preserves separated inactive draft branch. Re-enable restores if compatible; selected method change resets method-specific required fields only.</td>
  </tr>
  <tr>
    <td>Restriction/filter panel</td>
    <td>Per-filter checkboxes; mixed V18 defaults.</td>
    <td>Filter checkbox enabled.</td>
    <td>Disabled filter does not create entry block, resize, exit-only, warning or scaling effect.</td>
    <td>Toggle back restores stored settings after validation. Remove dynamic filter deletes only its UUID node.</td>
  </tr>
  <tr>
    <td>Date Blackout rows</td>
    <td>Panel enabled, one row; V18 row has blank dates.</td>
    <td>Date Blackout checkbox enabled and range complete.</td>
    <td>Incomplete row cannot be active; save blocker only if checkbox enabled.</td>
    <td>Date ordering/overlap normalization shown before save; removing row detaches it. Empty enabled panel warns/blockers depending rule count.</td>
  </tr>
  <tr>
    <td>Save action bar</td>
    <td>Visible/sticky when details open.</td>
    <td>Draft dirty and caller editable.</td>
    <td>Disabled during command pending/permission denial/locked revision until clone draft created.</td>
    <td>409 stale opens compare/reload/merge flow. 422 preserves draft and field errors. Success rehydrates canonical revision.</td>
  </tr>
  <tr>
    <td>Clear</td>
    <td>Visible.</td>
    <td>Draft exists; if dirty confirmation needed.</td>
    <td>No engine effect; cannot clear immutable saved revision.</td>
    <td>Confirmed clear resets editor default/blank draft; `DRAFT_CLEARED` audit possible; no Trash record.</td>
  </tr>
</table>

<table>
  <tr>
    <th>CANONICAL RULE — DISABLED IS NOT MERELY VISUAL<br/>V18in soluk structureları, özellikle Protection/Stop Logic, Position Sizing, Scaling Logic ve Restrictions/Filters içinde gerçek semantic boundarydir. Toggle/method checkbox kapalıysa alt değerler engine evaluation planına, active dependency manifestine veya valid action graphına giremez. Draftta geçmiş değerler korunabilir; ancak `enabled=false` veya semantik eşdeğer active-state açıkça serialized edilir.</th>
  </tr>
</table>

# 5. Alanlar, Varsayılanlar, Zorunluluk ve Dependency Contract

## 5.1 Add Strategy Entry Action ve Strategy Context

<table>
  <tr>
    <th>Alan / UI</th>
    <th>V18 observed default</th>
    <th>Zorunluluk</th>
    <th>Seçenekler / davranış</th>
    <th>Production payload ve validation</th>
  </tr>
  <tr>
    <td>Add Strategy</td>
    <td>Mainboard menu action; new `STRATEGY N` row; panel closed.</td>
    <td>Authenticated create policy.</td>
    <td>No modal in V18; creates client DOM.</td>
    <td>`strategy_draft.create`. Draft may be transient or server-backed. No Root/Revision/Backtest input before Save. Duplicate actions must use idempotency key.</td>
  </tr>
  <tr>
    <td>Strategy Name *</td>
    <td>`STRATEGY N`.</td>
    <td>Always required for revision save.</td>
    <td>Free text.</td>
    <td>`identity.display_name`: trimmed, 1–160 Unicode chars; forbidden blank/control-only; uniqueness is not global required but duplicate display name shows non-blocking warning. Server owns canonical normalization.</td>
  </tr>
  <tr>
    <td>Rationale Family *</td>
    <td>`Choose Rationale Family`.</td>
    <td>Always required.</td>
    <td>Global Rationale Family options. V18 prototype tanımı: Choice is loaded from global Rationale Family list; boş başlangıç “Choose Rationale Family”. Production: yalnız erişilebilir global shared Rationale Family IDs; list isim üzerinden değil `family_id` ile değer taşır.</td>
    <td>`rationale_family_id`; must exist, active/usable and accessible by special shared policy. Label-only input rejected.</td>
  </tr>
  <tr>
    <td>Market *</td>
    <td>`Choose Market`.</td>
    <td>Always required.</td>
    <td>BTCUSDT, ETHUSDT, EURUSD, XAUUSD, NASDAQ, SP500 in V18 demo.</td>
    <td>`instrument_id` / market identity. Must be compatible with selected Market Data revision and execution/funding policy; V18 free label is not canonical.</td>
  </tr>
  <tr>
    <td>Direction Mode</td>
    <td>Long &amp; Short.</td>
    <td>Required with production default `long_and_short`.</td>
    <td>Long &amp; Short; Long Only; Short Only.</td>
    <td>`direction_mode` enum. Entry Indicator direction/Exit applies-to-position/conflict hedge settings cannot request prohibited direction.</td>
  </tr>
  <tr>
    <td>Status</td>
    <td>Research Only.</td>
    <td>Required with default. Not readiness proof.</td>
    <td>Research Only; Backtest Ready; Locked for Test; Deprecated; Active Candidate.</td>
    <td>`lifecycle_intent/status` typed enum. `Backtest Ready` UI intent cannot bypass Ready Check. `Locked for Test` requires clone-to-draft before edit. `Deprecated` cannot be newly pinned/used without override policy. `Active Candidate` does not enable live trade.</td>
  </tr>
  <tr>
    <td>Created By</td>
    <td>readonly `currentUser || guest`.</td>
    <td>System-generated; not user-editable.</td>
    <td>Readonly.</td>
    <td>`created_by_principal`, `owner_principal` and `updated_by_principal` server-owned. Client value ignored. Guest is never persisted as authenticated User.</td>
  </tr>
</table>

## 5.2 Data & Execution

<table>
  <tr>
    <th>Alan / UI</th>
    <th>V18 observed default</th>
    <th>Zorunluluk</th>
    <th>Tüm seçenekler / koşul</th>
    <th>Production payload ve validation</th>
  </tr>
  <tr>
    <td>Data Source *</td>
    <td>Choose Data Source.</td>
    <td>Always required.</td>
    <td>BTCUSDT 15m/1m/1h/4h OHLCV 2020–2025; BTCUSDT Tick Data 2020–2025.</td>
    <td>`market_dataset_root_id + market_dataset_revision_id`. Must be approved/use-permitted, instrument-compatible, coverage-valid and resolution-capable. V18 strings are labels only.</td>
  </tr>
  <tr>
    <td>Backtest Range *</td>
    <td>2020-01-01 to 2025-12-31.</td>
    <td>Always required.</td>
    <td>Start date + End date.</td>
    <td>`backtest_range.start/end` ISO timestamps in dataset time basis. Start &lt;= end; range must be inside coverage; timezone/alignment explicit; missing coverage is blocker, limited coverage warning only if declared gap policy exists.</td>
  </tr>
  <tr>
    <td>Initial Capital *</td>
    <td>10000.</td>
    <td>Always required unless run-level Allocation enabled, yet field persists.</td>
    <td>Numeric decimal.</td>
    <td>`initial_capital.amount` and resolved currency. Must be &gt; 0, finite, compatible with settlement/base currency or pinned FX conversion. Allocation enabled uses allocation sleeve as run sizing base; disabled uses this amount.</td>
  </tr>
  <tr>
    <td>Capital Rule</td>
    <td>Readonly explanatory text.</td>
    <td>Not input.</td>
    <td>“Uses Equity Allocation only when enabled…”</td>
    <td>Derived UI projection. Never client authority. Engine run manifest resolves whether independent or shared allocation applies.</td>
  </tr>
  <tr>
    <td>Entry Execution *</td>
    <td>Choose Entry Execution.</td>
    <td>Always required.</td>
    <td>Next Candle Open; Current Candle Close; Next Candle Close; Intrabar Touch; Limit Fill Simulation; Market Fill Simulation.</td>
    <td>`execution.entry_timing` enum. Data resolution must support precision. Intrabar/limit policies validate against tick/OHLCV capability; cannot silently imitate unavailable detail.</td>
  </tr>
  <tr>
    <td>Exit Execution *</td>
    <td>Choose Exit Execution.</td>
    <td>Always required.</td>
    <td>Next Candle Open; Current Candle Close; Next Candle Close; Intrabar Touch; Stop / Limit Priority Simulation; Market Fill Simulation.</td>
    <td>`execution.exit_timing` enum. Combined with stop/conflict policy and data capabilities.</td>
  </tr>
  <tr>
    <td>Order Type ⓘ</td>
    <td>Market Order.</td>
    <td>Required with default.</td>
    <td>Market Order; Limit Order; Stop Order; Stop-Limit Order; Simulation Only.</td>
    <td>`order.type` enum. Limit and stop-limit activate conditional subtree. Simulation Only must be stored as explicit simulation behavior, not live-trading order.</td>
  </tr>
  <tr>
    <td>Commission</td>
    <td>Blank.</td>
    <td>Optional; required if selected execution/cost policy does not derive a dataset cost.</td>
    <td>Numeric amount or percentage according to configured unit.</td>
    <td>`costs.commission`; non-negative finite. Unit/currency explicit; absent means dataset/default policy, never magical zero if not declared.</td>
  </tr>
  <tr>
    <td>Spread</td>
    <td>Blank.</td>
    <td>Optional; becomes required if chosen fill model needs manual spread and no dataset spread exists.</td>
    <td>Numeric amount/percentage.</td>
    <td>`costs.spread`; non-negative; historical bid/ask source wins if selected. Consistency with data resolution is validated.</td>
  </tr>
  <tr>
    <td>Slippage Model</td>
    <td>Percentage Slippage.</td>
    <td>Required with default.</td>
    <td>Percentage Slippage; Historical Slippage If Available.</td>
    <td>`slippage.mode`. Historical requires approved compatible execution data or explicit percentage fallback warning/blocker by policy.</td>
  </tr>
  <tr>
    <td>Slippage Value</td>
    <td>Blank.</td>
    <td>Conditionally required for Percentage Slippage and fallback.</td>
    <td>Numeric percentage/amount per canonical unit.</td>
    <td>`slippage.value`; &gt;= 0 and realistic configured max. Ignored when historical selected with resolved history and no fallback.</td>
  </tr>
  <tr>
    <td>Use Tick Data ⓘ</td>
    <td>None.</td>
    <td>Optional tri-state default.</td>
    <td>None; Yes; No.</td>
    <td>`intrabar.tick_policy = inherit | require | disable`. Require is blocker if tick data unavailable; disable forces OHLCV conservative resolution even when tick exists.</td>
  </tr>
  <tr>
    <td>Funding Fee ⓘ</td>
    <td>Use Historical Funding Data.</td>
    <td>Conditionally required for perpetual/funding-capable market.</td>
    <td>Use Historical Funding Data; Disabled.</td>
    <td>`funding.enabled`. Historical mode needs compatible Research/Funding dataset revision; disabled excludes funding evaluator.</td>
  </tr>
  <tr>
    <td>Funding Source ⓘ</td>
    <td>Binance Historical Funding.</td>
    <td>Required only when historical funding enabled.</td>
    <td>Binance Historical Funding; Bybit Historical Funding; Manual Funding Source.</td>
    <td>`funding.source_root_id + revision_id`. Must match instrument/exchange/cadence/time availability. Disabled fee omits source from active payload.</td>
  </tr>
</table>

### 5.2.1 Limit Order Details — Conditional Fields

<table>
  <tr>
    <th>Alan / UI</th>
    <th>Visible / required condition</th>
    <th>V18 default/options</th>
    <th>Production behavior / validation</th>
  </tr>
  <tr>
    <td>Limit Order Details ⓘ</td>
    <td>Visible if Order Type = Limit Order or Stop-Limit Order.</td>
    <td>Initially hidden because Market Order.</td>
    <td>`order.limit.enabled=true`. Hidden fields excluded from active engine plan when not applicable.</td>
  </tr>
  <tr>
    <td>Limit Price Rule ⓘ</td>
    <td>Required when Limit/Stop-Limit.</td>
    <td>Entry signal price; Best bid / ask; Signal price minus offset; Signal price plus offset.</td>
    <td>`limit.price_rule` enum; offset variants require typed offset parameter supplied by schema/strategy-local config. Best bid/ask requires data capability or warning/blocker.</td>
  </tr>
  <tr>
    <td>Order Validity ⓘ</td>
    <td>Required when Limit/Stop-Limit.</td>
    <td>3 candles; Current candle only; 1 candle; 5 candles; Until cancelled.</td>
    <td>`limit.validity` typed duration enum; candlestick count resolved against source timeframe. Until cancelled needs explicit cancellation/invalidating event behavior.</td>
  </tr>
  <tr>
    <td>If Not Filled ⓘ</td>
    <td>Required when Limit/Stop-Limit.</td>
    <td>Cancel Order; Keep Until Validity Ends; Re-price Next Candle; Convert to Market Order.</td>
    <td>`limit.unfilled_policy`. Conversion/reprice must define timing/cost calculation and cannot create fill outside data capability.</td>
  </tr>
  <tr>
    <td>Partial Fill ⓘ</td>
    <td>Required when Limit/Stop-Limit when partial fill model supported.</td>
    <td>Not Allowed; Allowed; Minimum 50% Fill; Fill Remaining as Market; Cancel Remaining.</td>
    <td>`limit.partial_fill_policy`; requires liquidity/order-book proxy capability or conservative simulation declaration. Unsupported partial-fill realism is blocker or explicit fallback warning.</td>
  </tr>
</table>

## 5.3 Position Entry Logic — Signal / Indicator / Condition Graph

<table>
  <tr>
    <th>CANONICAL RULE — TRIGGER SOURCE DEPENDENCY<br/>`Indicator Native Trigger` seçildiğinde Condition Package zorunlu değildir. `Indicator Native Trigger + Condition Package` ile `Indicator Output + Condition Package` seçildiğinde en az bir active, valid ve compatible Condition Package zorunludur. V18in ilk Condition Blocku her koşulda required görünse de Production server validation bu conditional ruleu uygular.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Alan / UI</th>
    <th>V18 default</th>
    <th>Zorunluluk / dependency</th>
    <th>Options / production typed contract</th>
  </tr>
  <tr>
    <td>Entry Signal Block / Indicator Block Rule ⓘ</td>
    <td>Required + Minimum Supporting Indicator Blocks.</td>
    <td>Entry graph için required. Minimum count yalnız ilgili rule seçildiğinde required.</td>
    <td>Required Indicator Blocks Only; Required + Any Supporting Indicator Block; Required + Minimum Supporting Indicator Blocks; Required + All Confirmations -&gt; `entry.signal_block.rule` enum.</td>
  </tr>
  <tr>
    <td>Min Supporting Indicator Blocks Count ⓘ</td>
    <td>1.</td>
    <td>Required only `required_plus_min_supporting`; &gt;=1 and &lt;= count of active Supporting Indicator Blocks.</td>
    <td>Integer `entry.signal_block.min_supporting_count`. No supporting blocks =&gt; rule invalid; single active Indicator Block must be Required.</td>
  </tr>
  <tr>
    <td>Indicator Block</td>
    <td>Block 1 visible, non-removable initial placeholder; later blocks removable.</td>
    <td>At least one complete active Entry Indicator Block required to save/revise.</td>
    <td>Stable `block_id`, `display_order`, `enabled`, `package_ref`, `trigger_source`, `direction`, `timeframe`, `validity`, `requirement`, condition graph.</td>
  </tr>
  <tr>
    <td>Indicator *</td>
    <td>Choose Indicator.</td>
    <td>Always required for active block.</td>
    <td>Reversal Sensor; Smoothed Heiken Ashi; Predictive Ranges; RSI; TD Sequential; Volume Breakout; Top and Bottom Hunter. Production list = accessible compatible Indicator Package revisions only.</td>
  </tr>
  <tr>
    <td>Indicator Settings</td>
    <td>Adjust Indicator Settings button.</td>
    <td>Optional only if package exposes parameter schema; Apply values must validate.</td>
    <td>Generic `parameter_overrides` from package `parameter_schema`; button cannot mutate shared Package Revision.</td>
  </tr>
  <tr>
    <td>Trigger Source *</td>
    <td>Choose Trigger Source.</td>
    <td>Always required for active Entry Indicator Block.</td>
    <td>Indicator Native Trigger; Indicator Native Trigger + Condition Package; Indicator Output + Condition Package -&gt; exact enum.</td>
  </tr>
  <tr>
    <td>Direction</td>
    <td>Long &amp; Short.</td>
    <td>Required with default; must fit Strategy Direction Mode.</td>
    <td>Long; Short; Long &amp; Short -&gt; `direction_filter`. Long Only Strategy rejects/normalizes incompatible short; server validates.</td>
  </tr>
  <tr>
    <td>Timeframe</td>
    <td>Same as Base TF.</td>
    <td>Required with default.</td>
    <td>Same as Base TF; Use Package Default TF; 1m;3m;5m;15m;30m;1h;2h;4h;1D. Production resolves `timeframe_policy` + explicit timeframe; close alignment/lookahead rule mandatory.</td>
  </tr>
  <tr>
    <td>Validity ⓘ</td>
    <td>3 Candles.</td>
    <td>Required.</td>
    <td>Current Candle Only;1;2;3;4 Candles; Until Opposite Signal -&gt; event timestamps `valid_from`, `valid_until`, invalidation reason.</td>
  </tr>
  <tr>
    <td>Requirement ⓘ</td>
    <td>Required.</td>
    <td>Required for each active block.</td>
    <td>Required; Supporting. Supporting semantics determined by outer rule; at least one Required required.</td>
  </tr>
  <tr>
    <td>Condition Block Rule ⓘ</td>
    <td>Required Condition Blocks Only.</td>
    <td>Required when active conditions exist.</td>
    <td>Required Condition Blocks Only; Required + Any Supporting; Required + Minimum Supporting; Required + All Supporting -&gt; typed enum.</td>
  </tr>
  <tr>
    <td>Min Supporting Condition Blocks Count ⓘ</td>
    <td>1.</td>
    <td>Required only min-supporting condition rule.</td>
    <td>Integer &gt;=1 &lt;= active Supporting Condition Blocks. Not a count of conditions across different Indicator Blocks.</td>
  </tr>
  <tr>
    <td>Condition Block</td>
    <td>Condition Block 1 visible under first entry block.</td>
    <td>Required only by Trigger Source/condition graph semantics.</td>
    <td>Stable `condition_block_id`, `package_ref`, requirement, validity. V18 görünür örnekleri: Reversal Sensor (Long/Short/Strength), Smoothed Heiken Ashi (green/red/continuation), Predictive Ranges (support/resistance/ break), RSI (cross/divergence), TD Sequential (long/short count), Volume Breakout (volume / breakout confirmation). Production: liste selected Indicator Package revision input/output contractı ile uyumlu aktif Condition Package revisions üzerinden dinamik filtrelenir; statik string listesi veya Trading Signal package seçeneği yoktur.</td>
  </tr>
  <tr>
    <td>+ ADD CONDITION BLOCK</td>
    <td>Visible within Indicator Block.</td>
    <td>May add a blank inactive draft block.</td>
    <td>`strategy_draft.condition_block.add`; new UUID; no engine effect until complete/active. Renumber visual display only.</td>
  </tr>
  <tr>
    <td>+ ADD INDICATOR BLOCK</td>
    <td>Visible within Indicator Block.</td>
    <td>May add blank inactive draft block.</td>
    <td>`strategy_draft.indicator_block.add`; new UUID. A block’s condition rows belong only to that block.</td>
  </tr>
  <tr>
    <td>Remove dynamic block</td>
    <td>× only on noninitial dynamic blocks.</td>
    <td>Allowed only draft editor/policy.</td>
    <td>Remove from draft graph; detach dependency refs; display renumber; audit patch draft optionally. Cannot silently reuse removed UUID.</td>
  </tr>
</table>

## 5.4 Position Exit Logic

<table>
  <tr>
    <th>Alan / UI</th>
    <th>V18 default</th>
    <th>Zorunluluk / dependency</th>
    <th>Options / production typed contract</th>
  </tr>
  <tr>
    <td>Applies To Position ⓘ</td>
    <td>Long Positions.</td>
    <td>Required if Exit Logic active.</td>
    <td>Long Positions; Short Positions; Long &amp; Short Positions -&gt; must not contradict Strategy Direction Mode.</td>
  </tr>
  <tr>
    <td>Exit Action ⓘ</td>
    <td>Close 100%.</td>
    <td>Required if Exit Logic active.</td>
    <td>Close 100%; Close 75%; Close 50%; Close 25%; Move Stop to Entry; Activate Trailing Stop; Exit Warning Only. Partial close creates explicit action payload and ledger event.</td>
  </tr>
  <tr>
    <td>After Partial Close ⓘ</td>
    <td>Move Stop to Entry.</td>
    <td>Required only for partial close actions.</td>
    <td>Move Stop to Entry; Activate Trailing Stop; Close Remaining Position at Next Exit Signal. Hidden/inactive for Close 100 / non-close actions.</td>
  </tr>
  <tr>
    <td>Exit Signal Block Rule ⓘ</td>
    <td>Required + Minimum Supporting Indicator Blocks.</td>
    <td>Required if active Exit graph.</td>
    <td>Same four outer combination enums as Entry. Count rule validation same.</td>
  </tr>
  <tr>
    <td>Min Supporting Indicator Blocks Count</td>
    <td>1.</td>
    <td>Conditionally required by exit rule.</td>
    <td>Integer &gt;=1 &lt;= supporting exit blocks.</td>
  </tr>
  <tr>
    <td>Exit Indicator Block</td>
    <td>Block 1 visible; Indicator Package blank; V18 default Condition says Reversal Sensor / Opposite Signal.</td>
    <td>Blank initial placeholder does not make Exit Logic active. Once active, Indicator, package settings, timeframe, validity, requirement and valid condition graph required.</td>
    <td>Package source list: same Indicator Package model. V18 default condition must be re-filtered/reset after indicator selection; server never accepts incompatible cached condition.</td>
  </tr>
  <tr>
    <td>Exit Indicator Settings</td>
    <td>Adjust Indicator Settings.</td>
    <td>If package schema exposes editable parameter.</td>
    <td>Strategy-local parameter override, not package mutation.</td>
  </tr>
  <tr>
    <td>Exit Timeframe / Validity / Requirement</td>
    <td>Same as Base TF / 3 Candles / Required.</td>
    <td>Required for active exit block.</td>
    <td>Same typed policy family as Entry. Validity applies to exit candidate not entire position lifespan.</td>
  </tr>
  <tr>
    <td>Exit Condition Block Rule / Min Count</td>
    <td>Required Condition Blocks Only / 1.</td>
    <td>Required only when active conditions exist; min count conditional.</td>
    <td>Same typed condition aggregation semantics.</td>
  </tr>
  <tr>
    <td>Exit Condition Block</td>
    <td>First condition default shows Opposite Signal in V18.</td>
    <td>Active condition package must be compatible with selected exit indicator/revision.</td>
    <td>Required/Supporting; Current Candle Only; 1–4 Candles; Until Opposite Condition. `Condition Block` does not independently close a position; it contributes to Exit Indicator Block.</td>
  </tr>
  <tr>
    <td>+ Add / remove blocks</td>
    <td>Same patterns as Entry.</td>
    <td>Policy + draft concurrency applies.</td>
    <td>Stable UUIDs; display sequence only. Remove clears active refs/any now-invalid min count.</td>
  </tr>
</table>

<table>
  <tr>
    <th>IMPLEMENTATION DECISION — EXIT PLACEHOLDER<br/>V18 first Exit Indicator Blockunu görünür fakat eksik bırakır. Productionda boş initial Exit block **inactive draft placeholder** olarak ele alınır: Save active exit node üretmez ve Stop Logic tek başına strategy exit protection sağlayabilir. Kullanıcı bir exit Indicator Package seçtiği anda block active adayına dönüşür; ilgili required fields/compatibility ve Direction rules tamamlanmadan Save Strategy Revision blocker verir.</th>
  </tr>
</table>

## 5.5 Protection / Stop Logic

Protection / Stop Logic, normal Position Exit Logicten ayrı bir risk koruma katmanıdır. Stop rule tetiklendiğinde motor yalnız “sinyal vardı” bilgisi tutmaz; evaluation timestamp, source condition, trigger price, resolved priority, selected fill model, fee/spread/slippage ve position state etkisini decision trace/ledger artifacte yazar.

<table>
  <tr>
    <th>Alan / UI</th>
    <th>V18 default</th>
    <th>Activation / requiredness</th>
    <th>Production behavior</th>
  </tr>
  <tr>
    <td>Stop Trigger Requirement / Stop Mode ⓘ</td>
    <td>Any Active Stop Rule Triggers Stop.</td>
    <td>Required with default.</td>
    <td>Any Active Stop Rule Triggers Stop; All Active Stop Rules Must Trigger Stop -&gt; `stop.mode`. “All” requires every active stop rule to be evaluable over defined time window; otherwise ambiguous config blocker.</td>
  </tr>
  <tr>
    <td>Logic-Based Stop Block 1 ⓘ</td>
    <td>Enabled; Indicator blank; Condition 01 Choose Condition Package.</td>
    <td>Enabled checkbox + a compatible Indicator + at least one valid Condition required before engine active.</td>
    <td>`stop.logic_blocks[]`; each has UUID, indicator ref, parameter overrides, condition list, combination rule. `+ Add Condition` adds dynamic row; `+ Add Logic-Based Stop Block` adds separate rule. Disabled/removed handling follows Interaction Matrix.</td>
  </tr>
  <tr>
    <td>Logic stop Indicator</td>
    <td>Choose Indicator.</td>
    <td>Required if block enabled.</td>
    <td>Reversal Sensor; Predictive Ranges; Top and Bottom Hunter; Volume Breakout; Smoothed Heiken Ashi; TD Sequential; RSI; Moving Average in V18. Production uses compatible Indicator Package revisions.</td>
  </tr>
  <tr>
    <td>Logic stop Conditions</td>
    <td>Condition 01 starts placeholder.</td>
    <td>At least one active compatible condition when block enabled.</td>
    <td>Dynamically filtered Package revisions. `Any Added Condition Can Produce Stop Signal` vs `All Added Conditions Must Be Valid` -&gt; enum; never “first matching UI string”.</td>
  </tr>
  <tr>
    <td>Percentage Stop ⓘ</td>
    <td>Enabled; Stop Distance 1.00%.</td>
    <td>If checked, Stop Distance required &gt;0.</td>
    <td>`stop.percentage.enabled`, distance percentage. Trigger semantics must state reference (fill/average entry) and use selected execution/market data resolution.</td>
  </tr>
  <tr>
    <td>Trailing Stop ⓘ</td>
    <td>Enabled; Activate After Profit 2.00%; Trailing Distance 0.80%.</td>
    <td>If checked, both values required; distance &gt;0; activation threshold defined.</td>
    <td>`stop.trailing.enabled`, profit_activation, trailing_distance, high/low extreme tracking. Engine updates trailing state deterministic per interval.</td>
  </tr>
  <tr>
    <td>Absolute Price Stop</td>
    <td>Disabled; price blank.</td>
    <td>If checked, Stop Price required &gt;0 / valid price scale.</td>
    <td>`stop.absolute.enabled`, price. May be absolute market price only if instrument tick/precision supports it.</td>
  </tr>
  <tr>
    <td>+ Add Logic-Based Stop Block</td>
    <td>Visible.</td>
    <td>May create blank draft block.</td>
    <td>Creates UUID. New block does not affect engine until enabled+valid. Removing a dynamic block detaches child refs/invalidates min conditions as relevant.</td>
  </tr>
</table>

<table>
  <tr>
    <th>IMPLEMENTATION DECISION — NO ACTIVE STOP RULE<br/>Production V1 allows a Strategy Revision with no active stop rule only in Research Only state; Save emits a high-severity warning that risk protection is absent. For any status intended for backtest candidate use, Ready Check surfaces the warning and may be configured by portfolio policy to block the run; the Strategy form itself never fabricates an invisible stop. This is a documented risk governance choice, not a UI default bypass.</th>
  </tr>
</table>

## 5.6 Position Sizing

<table>
  <tr>
    <th>Alan / UI</th>
    <th>V18 default</th>
    <th>Requiredness / disabled behavior</th>
    <th>Production typed contract / validation</th>
  </tr>
  <tr>
    <td>Sizing method group</td>
    <td>Base Position Size checked; Risk Per Trade and Custom Formula checkbox-looking controls unselected/disabled.</td>
    <td>Exactly one active method required for a saved Strategy Revision. Checked visual controls are mutually exclusive radio semantics.</td>
    <td>`sizing.method = base_position_size | risk_per_trade | custom_formula`; only selected branch serialized as active. Nonselected branch stored optional draft-only but engine omitted.</td>
  </tr>
  <tr>
    <td>Base Position Size ⓘ</td>
    <td>Selected; Position Size blank.</td>
    <td>When selected, Position Size required &gt;0.</td>
    <td>`sizing.base_position_size.percent` or typed unit; &lt;= Max Single Position and subject to allocation/exposure cap.</td>
  </tr>
  <tr>
    <td>Risk Per Trade ⓘ</td>
    <td>Disabled; Risk Amount blank.</td>
    <td>When selected, Risk Amount required &gt;0 and valid protective stop/risk price model required.</td>
    <td>`sizing.risk_per_trade.percent`; engine calculates quantity from risk amount, stop distance and execution assumptions; cannot use undefined stop distance.</td>
  </tr>
  <tr>
    <td>Custom Formula ⓘ</td>
    <td>Disabled; Formula blank.</td>
    <td>When selected, formula required and must parse/type-check.</td>
    <td>`sizing.custom_formula.ast` from restricted, versioned DSL. Never evaluates Python/JavaScript/PineScript. Ref dependencies must resolve and output non-negative finite size.</td>
  </tr>
  <tr>
    <td>Max Single Position ⓘ</td>
    <td>Blank.</td>
    <td>Required for production candidate config; may be blank draft.</td>
    <td>`limits.max_single_position_percent`; &gt;0; &gt;= base/add layer intended size only if cap policy adjusts/rejects explicitly.</td>
  </tr>
  <tr>
    <td>Max Total Exposure ⓘ</td>
    <td>Blank.</td>
    <td>Required for production candidate config; may be blank draft.</td>
    <td>`limits.max_total_exposure_percent`; &gt;0; &gt;= max single; total main + layers cannot exceed. Allocation is external cap, not bypass.</td>
  </tr>
  <tr>
    <td>Leverage Mode ⓘ</td>
    <td>Isolated.</td>
    <td>Required default.</td>
    <td>No Leverage; Isolated; Cross -&gt; typed enum; available options depend on market/exchange/execution scope.</td>
  </tr>
  <tr>
    <td>Leverage</td>
    <td>Blank.</td>
    <td>Required if leverage mode Isolated/Cross; must be 1 when No Leverage if shown.</td>
    <td>`leverage.multiplier`; finite &gt;0 and max allowed by market policy. No UI/client trust for leverage limit.</td>
  </tr>
  <tr>
    <td>Signal Strength Adjustment</td>
    <td>No Signal Strength Adjustment.</td>
    <td>Condition rules/rows required only non-none adjustment.</td>
    <td>No; Increase Size When Condition Package Is Met; Decrease Size When Condition Package Is Met; Use Size Bands… -&gt; `signal_strength_adjustment`. Non-none requires compatible condition refs, multiplier/band config and final caps.</td>
  </tr>
  <tr>
    <td>Condition Package Rule</td>
    <td>Any Added Condition Package Can Enable Adjustment.</td>
    <td>Active only non-none adjustment.</td>
    <td>Any Added…; All Added… -&gt; typed aggregation enum. `+ ADD CONDITION PACKAGE` adds stable UUID row. Values ignored when no adjustment.</td>
  </tr>
</table>

<table>
  <tr>
    <th>CANONICAL RULE — SIZING METHOD EXCLUSIVITY<br/>V18 checkbox görünümüne rağmen Base Position Size, Risk Per Trade ve Custom Formula aynı anda aktif olamaz. Production payload tek `sizing.method` enumu taşır. UI birden fazla seçili görünse bile server 422 `SIZING_METHOD_NOT_EXCLUSIVE` ile reddeder.</th>
  </tr>
</table>

## 5.7 Scaling Logic

<table>
  <tr>
    <th>Alan / UI</th>
    <th>V18 default</th>
    <th>Activation / dependency</th>
    <th>Production behavior</th>
  </tr>
  <tr>
    <td>Scaling Timeframe Structure ⓘ</td>
    <td>Same as Strategy Timeframe.</td>
    <td>Always visible; active scaling method yoksa engine inactive.</td>
    <td>`scaling.timeframe_mode`: same_strategy | increasing_by_layer | custom_sequence.</td>
  </tr>
  <tr>
    <td>Timeframe Mode ⓘ</td>
    <td>Same as Strategy Timeframe.</td>
    <td>Custom sequence required only Custom Timeframe Sequence.</td>
    <td>Same; Increasing Timeframe by Layer; Custom Timeframe Sequence. Alignment/lookahead check per layer; all package outputs use closed-bar rule.</td>
  </tr>
  <tr>
    <td>Custom Timeframe Sequence ⓘ</td>
    <td>Disabled; `15m &gt; 30m &gt; 1h &gt; 4h`.</td>
    <td>Enabled + required only custom sequence.</td>
    <td>Typed array of canonical timeframe enums, not free string. Strictly valid sequence; default text is V18 visual seed only.</td>
  </tr>
  <tr>
    <td>Additional Layer Method ⓘ</td>
    <td>No method checked; Price/Logic panels disabled.</td>
    <td>Exactly zero or one. Selection makes Scaling active.</td>
    <td>Price-Distance Based Scaling OR Logic-Based Scaling. Scaling only adds same-direction layers; opposite direction signal never counts as scaling.</td>
  </tr>
  <tr>
    <td>Price-Distance Based Scaling ⓘ</td>
    <td>Disabled.</td>
    <td>When selected: direction, reference price and distance required.</td>
    <td>Price movement: Against Open Position / In Favor. Reference: Initial Entry Price / Previous Filled Layer. `distance_percent` &gt;0; layer may be rejected by exposure/cooldown/loss caps.</td>
  </tr>
  <tr>
    <td>Logic-Based Scaling ⓘ</td>
    <td>Disabled.</td>
    <td>When selected: one+ valid rule, compatible packages and aggregation contract.</td>
    <td>Logic Combination: All / Any / Minimum N of M. Minimum N conditional. Dynamic Logic-Based Rule &gt; Signal Block &gt; Indicator/Condition Blocks; stable UUIDs.</td>
  </tr>
  <tr>
    <td>Logic-Based Rules Required to Scale ⓘ</td>
    <td>Blank/disabled.</td>
    <td>Required only minimum N of M.</td>
    <td>Integer 1…active rule count. Server rejects no rules or count above active rules.</td>
  </tr>
  <tr>
    <td>Add Size Per Scale ⓘ</td>
    <td>Percentage of Initial Entry Size; value 50.</td>
    <td>Required only when scaling enabled.</td>
    <td>Same as Initial Entry Size; Percentage of Initial Entry Size; Percentage of Current Position; Fixed Amount; Risk-Based; Custom Formula. `add_size_value` unit/type follows method; formula DSL rules apply.</td>
  </tr>
  <tr>
    <td>Scaling Limits ⓘ</td>
    <td>All blank.</td>
    <td>Required only enabled scaling except optional soft caps by policy.</td>
    <td>Max Additional Layer Count; Minimum Bars Between Layers; Stop Adding Layers At Position Loss. Positive integer/decimal rules. Cooling/loss state updated engine-side.</td>
  </tr>
</table>

<table>
  <tr>
    <th>CANONICAL RULE — SAME-DIRECTION ONLY<br/>Scaling Logic mevcut pozisyona yalnız aynı yönde ilave layer ekler. Karşıt yönlü sinyal scaling değildir; Conflict / Position Handling Rules üzerinden resolve edilir. UI bir “reverse scaling” seçeneği üretmemeli, Agent tool da bu bypassı kabul etmemelidir.</th>
  </tr>
</table>

## 5.8 Restrictions / Filters

<table>
  <tr>
    <th>Filter / field</th>
    <th>V18 default</th>
    <th>Required when enabled</th>
    <th>Options / canonical action semantics</th>
  </tr>
  <tr>
    <td>Restriction Rule ⓘ</td>
    <td>If ANY restriction is active, block entry.</td>
    <td>Required if any restriction enabled.</td>
    <td>ANY blocks entry; ALL blocks entry; Minimum N of M -&gt; typed `restriction.combination` and count. A filter action can be block, resize, exit-only, warning; not all filters necessarily same effect.</td>
  </tr>
  <tr>
    <td>Volatility Filter ⓘ</td>
    <td>Enabled; Volatility too high.</td>
    <td>Condition required if enabled.</td>
    <td>Too high; too low; spike; compression; ATR above/below threshold. Production payload adds typed threshold/indicator ref if condition needs it.</td>
  </tr>
  <tr>
    <td>Spread Filter</td>
    <td>Enabled; Max Spread 0.05%.</td>
    <td>Max spread &gt;0 required if enabled.</td>
    <td>Data must expose spread or declared proxy. If unavailable, cannot silently use zero spread.</td>
  </tr>
  <tr>
    <td>Volume Filter</td>
    <td>Enabled; Volume too low.</td>
    <td>Condition required if enabled.</td>
    <td>Too low/high; spike; below/above MA; abnormal. If MA condition, package/parameter/version defined.</td>
  </tr>
  <tr>
    <td>Regime Filter</td>
    <td>Disabled; Range Market Only.</td>
    <td>Allowed Regime required if enabled.</td>
    <td>Trend; Range; High/Low vol; Bullish/Bearish/Neutral. Regime classifier reference must be resolved/versioned.</td>
  </tr>
  <tr>
    <td>Session Filter</td>
    <td>Disabled; London + New York.</td>
    <td>Allowed Session required if enabled.</td>
    <td>All; Asia; London; New York; London+New York; Asia+London. Session timezone/calendar policy must be explicit.</td>
  </tr>
  <tr>
    <td>Weekend Filter</td>
    <td>Disabled; Block Weekend Trades.</td>
    <td>Action required if enabled.</td>
    <td>Allow; Block; Close before weekend; Reduce size; Warning Only. Calendar derives from instrument venue/timezone.</td>
  </tr>
  <tr>
    <td>Specific Time Filter</td>
    <td>Disabled; 09:00–18:00.</td>
    <td>From/To required if enabled.</td>
    <td>Overnight crossing must be normalized explicitly. Time basis derived from Market Data/exchange timezone.</td>
  </tr>
  <tr>
    <td>Date Blackout Windows ⓘ</td>
    <td>Enabled; 1 blank date range.</td>
    <td>At least one valid non-overlapping start/end required if enabled.</td>
    <td>Action: Block New Entries + Block New Scaling; Block New Entries Only; Close at Start; Allow Exit Only; Warning Only. Dynamic ranges UUID + timezone.</td>
  </tr>
  <tr>
    <td>Max Daily Loss</td>
    <td>Enabled; 3.0%; Block New Entries.</td>
    <td>Limit &gt;0 and action required if enabled.</td>
    <td>Block; Reduce New Position Size; Close All; Disable Strategy for Day; Warning Only. State reset boundary uses strategy/instrument calendar policy.</td>
  </tr>
  <tr>
    <td>Consecutive Loss Filter ⓘ</td>
    <td>Enabled; 5; Block New Entries.</td>
    <td>Max losses integer &gt;=1 and action required if enabled.</td>
    <td>Block; reduce size; pause N candles; disable day; warning. Counter is engine ledger state, not UI counter.</td>
  </tr>
  <tr>
    <td>Equity Curve Filter ⓘ</td>
    <td>Disabled; Equity below MA; Block New Entries.</td>
    <td>Condition/action required if enabled.</td>
    <td>Below MA; drawdown threshold; below peak X%; fails recovery. Needs defined equity sampling/indicator values; cannot use future equity.</td>
  </tr>
  <tr>
    <td>Condition-Based Restriction ⓘ</td>
    <td>Disabled; Condition package blank; Block New Entries.</td>
    <td>Condition Package + action required if enabled.</td>
    <td>Condition Package must be compatible, accessible revision. V18 “Available saved Trading Signal Packages” option is removed: Trading Signal is not a Condition Package.</td>
  </tr>
  <tr>
    <td>+ Add Restriction / Filter</td>
    <td>Visible; no dynamic filters initially.</td>
    <td>Blank dynamic item ignored until enabled/complete.</td>
    <td>Creates stable UUID restriction node. Removal cleans refs and recomputes combination min N; duplicate logical filters warn.</td>
  </tr>
</table>

## 5.9 Conflict / Position Handling Rules

<table>
  <tr>
    <th>Field</th>
    <th>V18 default (first option)</th>
    <th>All V18 options</th>
    <th>Production resolution</th>
  </tr>
  <tr>
    <td>Long + Short</td>
    <td>Ignore Both</td>
    <td>Ignore Both; Stronger Signal Wins; Long Priority; Short Priority; Use Higher Timeframe Direction.</td>
    <td>`conflict.long_short` enum; strength method / HTF source must be explicitly resolved, otherwise option invalid.</td>
  </tr>
  <tr>
    <td>Entry + Exit</td>
    <td>Exit Has Priority</td>
    <td>Exit Has Priority; Ignore Entry; Allow Entry After Exit; Stronger Signal Wins.</td>
    <td>Deterministic same interval sequence; “Allow Entry After Exit” requires selected execution timing and position state update convention.</td>
  </tr>
  <tr>
    <td>Entry + Restriction</td>
    <td>Restriction Blocks Entry</td>
    <td>Restriction Blocks Entry; Warning Only; Reduce Position Size; Ignore Restriction.</td>
    <td>Restriction rule action generally wins; Ignore restriction must be policy constrained and auditable.</td>
  </tr>
  <tr>
    <td>Stop + Exit ⓘ</td>
    <td>Stop Has Priority</td>
    <td>Stop Has Priority; Exit Has Priority; Record Both Reasons; First Trigger Wins.</td>
    <td>Engine writes resolved priority + all simultaneous reason codes even when one action executes.</td>
  </tr>
  <tr>
    <td>Multiple Stops ⓘ</td>
    <td>First Trigger Wins</td>
    <td>First Trigger Wins; Most Conservative Stop Wins; Priority Order; Record All / Execute Highest Priority.</td>
    <td>Priority order requires ordered stop rule IDs. “Most conservative” definition is direction-aware and data-resolution-safe.</td>
  </tr>
  <tr>
    <td>Scaling + Stop</td>
    <td>Stop Blocks Scaling</td>
    <td>Stop Blocks Scaling; Allow Scaling; Reduce Scaling Size.</td>
    <td>Same interval stop eligibility must be resolved before scales in global engine pipeline unless explicitly policy allows alternative.</td>
  </tr>
  <tr>
    <td>Open Pos. + Opposite</td>
    <td>Close Current, Then Wait</td>
    <td>Close Current, Then Wait; Ignore Opposite; Close Current; Close Current, Then Open Opposite; Hedge If Allowed.</td>
    <td>Hedge only if market/execution permissions and Direction Mode allow. Not a default V1 live-trading capability.</td>
  </tr>
  <tr>
    <td>Same Candle Entry / Exit</td>
    <td>Use Intrabar Data If Available</td>
    <td>Use Intrabar Data If Available; Exit First; Stop First; Ignore Trade; Conservative Rule.</td>
    <td>If tick unavailable, engine follows declared conservative/priority policy; never assumes unknown intrabar sequence.</td>
  </tr>
  <tr>
    <td>Same-Direction Signal</td>
    <td>Add Layer If Scaling Allows</td>
    <td>Add Layer If Scaling Allows; Ignore New Signal; Open Separate Position; Reset Entry Price.</td>
    <td>Separate position only if position model supports it; otherwise validation blocks. Scaling constraints still apply.</td>
  </tr>
  <tr>
    <td>Opposite-Direction Signal</td>
    <td>Close Current, Then Wait</td>
    <td>Close Current, Then Wait; Ignore; Close Current; Close Current, Then Reverse; Hedge If Allowed.</td>
    <td>Must cohere with Open Pos. + Opposite and Direction Mode; incompatible combinations blocker.</td>
  </tr>
  <tr>
    <td>Allow Multiple Same Direction</td>
    <td>No</td>
    <td>No; Yes; Only If Scaling Allows.</td>
    <td>Enum; engine count/caps/sizing rules authoritative.</td>
  </tr>
  <tr>
    <td>Allow Opposite While Open</td>
    <td>No</td>
    <td>No; Yes; Only Hedge Mode.</td>
    <td>Enum; requires market policy support. UI availability is not server entitlement.</td>
  </tr>
</table>

# 6. Information Content Catalog — ⓘ Panelleri

Bu bölümdeki metinler, ilgili ⓘ button tıklandığında açılan bilgi paneline doğrudan yerleştirilebilecek nihai UI içeriğidir. V18 HTMLdeki mevcut popover metni temel alınmış; UI seçenekleri ile çelişen satırlar ve canonical ayrımlar Production V1e göre hizalanmıştır. Popover, yardım içerir; form değeri yazmaz, validation bypass etmez, package/data erişim hakkı vermez.

<table>
  <tr>
    <th>CONTENT RULE<br/>V18 info panelindeki “4 Candles” veya “Skip Trade” gibi formda görünmeyen seçenekler Productionda kullanılmayacaktır. Panel metni, o anki UI / typed enum seti ile aynı sözleşmeyi anlatmak zorundadır.</th>
  </tr>
</table>

## 6.1 Individual Information Panels

### ⓘ Condition Block

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`entryConditionBlock`<br/>Entry Condition Block</td>
    <td>Condition Block<br/><br/>Condition Block, üstündeki Indicator Package&#x27;ın hangi somut davranışının “true” kabul edileceğini seçtiğin yerdir. Bir Indicator Block&#x27;a birden fazla condition ekleyerek daha dar veya daha onaylı bir sinyal tarif edebilirsin.<br/><br/>Örnek: RSI indicator için “Crosses Above 30” koşulu, RSI&#x27;ın yalnızca düşük olduğunu değil, düşük bölgeden yukarı doğru çıktığını ifade eder; bu daha somut bir giriş davranışıdır.</td>
  </tr>
</table>

### ⓘ Condition Block — Requirement

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`conditionRequirement`<br/>Entry Condition Requirement</td>
    <td>Condition Block — Requirement<br/><br/>Bu koşulun bağlı bulunduğu Indicator Block içinde zorunlu mu yoksa yardımcı mı olacağını belirler.<br/><br/>• Required: Condition true olmadan Indicator Block geçerli sinyal üretemez.<br/><br/>• Supporting: Condition bir onay olarak değerlendirilir; gerekli sayıya ulaşılıp ulaşılmadığı Condition Rule tarafından belirlenir.<br/><br/>Örnek: “Fiyat desteğe yakın” Required, “hacim ortalamanın üzerinde” Supporting olabilir.</td>
  </tr>
</table>

### ⓘ Condition Block — Validity

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`conditionValidity`<br/>Entry Condition Validity</td>
    <td>Condition Block — Validity<br/><br/>Koşul true olduktan sonra kaç mum boyunca hâlâ geçerli sayılacağını belirler.<br/><br/>• Current Candle Only: Koşul sadece oluştuğu mumda kullanılabilir.<br/><br/>• 1 / 2 / 3 / 4 Candles: Koşul belirlenen mum sayısı süresince true olarak taşınır.<br/><br/>• Until Opposite Condition: Karşıt bir condition oluşana kadar geçerli kalır.<br/><br/>Örnek: Fiyat desteğe dokunduğu mumdan sonra dönüş göstergesi iki mum sonra oluşabiliyorsa, destek koşuluna 2 Candles validity verilebilir.</td>
  </tr>
</table>

### ⓘ Indicator Block

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`entryIndicatorBlock`<br/>Entry Indicator Block</td>
    <td>Indicator Block<br/><br/>Indicator Block, tek bir Indicator Package&#x27;ın bu stratejide nasıl kullanılacağını tanımlar. İçindeki Condition Block&#x27;lar, indikatörün hangi davranışının geçerli giriş sinyali sayılacağını belirler.<br/><br/>Yeni bir indikatör eklemek, stratejiye yeni bir onay veya zorunlu şart eklemek demektir; aynı indikatörü farklı timeframe veya farklı koşulla ayrı bir block olarak da ekleyebilirsin.<br/><br/>Örnek: Smoothed Heiken Ashi seçilir; koşul olarak “Color Turns Green” atanır; Requirement “Supporting” yapılır. Bu block, ana giriş sinyalini tek başına başlatmaz fakat onaylayabilir.</td>
  </tr>
</table>

### ⓘ Indicator Block — Validity

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`indicatorValidity`<br/>Entry Indicator Block Validity</td>
    <td>Indicator Block — Validity<br/><br/>İndikatörün ürettiği geçerli sinyalin kaç mum boyunca kullanılabilir sayılacağını belirler. Bu, farklı indikatörlerin tam aynı mumda sinyal vermek zorunda kalmasını engelleyebilir; fakat süre uzadıkça eski sinyalle işlem açma riski artar.<br/><br/>• Current Candle Only: Sinyal yalnızca oluştuğu mumda kullanılabilir.<br/><br/>• 1 / 2 / 3 / 4 Candles: Sinyal belirtilen mum süresince aktif kabul edilir.<br/><br/>• Until Opposite Signal: Ters bir sinyal oluşana kadar aktif kalır.<br/><br/>Örnek: 15 dakikalık timeframe&#x27;de 3 Candles, sinyalin oluşmasından sonra en fazla 45 dakika giriş kararına katkı verebilmesi anlamına gelir.</td>
  </tr>
</table>

### ⓘ Indicator Block — Requirement

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`indicatorRequirement`<br/>Entry Indicator Block Requirement</td>
    <td>Indicator Block — Requirement<br/><br/>Bu block&#x27;un nihai giriş kararındaki statüsünü belirler.<br/><br/>• Required: Bu block geçerli sinyal üretmeden Signal Block giriş sinyali üretemez. Ana koşullar için kullanılır.<br/><br/>• Supporting: Bu block yardımcı onaydır. Gerekip gerekmediğini Signal Block içindeki Indicator Rule ve minimum supporting sayısı belirler.<br/><br/>Örnek: Reversal Sensor giriş fikrinin kaynağıysa Required; hacim yeterliliği yalnızca onaysa Volume Breakout Supporting seçilebilir.</td>
  </tr>
</table>

### ⓘ Indicator Block — Condition Block Rule

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`conditionRule`<br/>Entry Indicator Condition Block Rule</td>
    <td>Indicator Block — Condition Block Rule<br/><br/>Bir Indicator Block içine birden fazla Condition Block eklenebilir. Bu menü, o koşulların indikatör sinyalini üretmek için nasıl birleşeceğini belirler.<br/><br/>• Required Condition Blocks Only: Required olarak işaretlenen tüm koşullar doğru olmalıdır; Supporting koşullar sonuca katılmaz.<br/><br/>• Required + Any Supporting Condition Block: Required koşulların tamamına ek olarak en az bir Supporting koşul doğru olmalıdır.<br/><br/>• Required + Minimum Supporting Condition Blocks: Required koşulların tamamına ek olarak belirlenen sayıda Supporting koşul doğru olmalıdır.<br/><br/>• Required + All Supporting Conditions: Eklenen tüm Required ve Supporting koşullar doğru olmalıdır.<br/><br/>Örnek: Heiken Ashi “yeşile döndü” Required, “iki mum yeşil devam etti” Supporting ise, ikinci şartı onay olarak kullanıp kullanmayacağını bu menü belirler.</td>
  </tr>
</table>

### ⓘ Indicator Block — Min. Supporting Condition Blocks Count

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`entryMinimumSupportingConditionCount`<br/>Entry Min. Supporting Condition Blocks Count</td>
    <td>Indicator Block — Min. Supporting Condition Blocks Count<br/><br/>Bu sayı, yalnızca içinde bulunduğu Indicator Block &#x27;a eklenmiş Supporting Condition Block&#x27;lardan kaçının aynı indikatörün sinyalini onaylaması gerektiğini belirler. Signal Block seviyesindeki indicator sayımıyla karıştırılmamalıdır.<br/><br/>Örnek: RSI Indicator Block içinde “Crosses Above 30” Required; “Bullish Divergence” ve “Slope Turns Up” Supporting olsun. Count = 1 seçilirse Required koşula ek olarak bu iki supporting koşuldan biri geçerli olduğunda RSI block sinyal üretir.</td>
  </tr>
</table>

### ⓘ Exit — Condition Block

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`exitConditionBlock`<br/>Exit Condition Block</td>
    <td>Exit — Condition Block<br/><br/>Bağlı olduğu indicator&#x27;ın hangi somut davranışının çıkış açısından true sayılacağını belirler. Bu bloklar yeni eklenebildiği için, bir indikatör için birden fazla çıkış şartı kurabilirsin.<br/><br/>Örnek: Smoothed Heiken Ashi için “Color Turns Red”, açık long pozisyonun zayıfladığını gösteren çıkış koşulu olabilir.</td>
  </tr>
</table>

### ⓘ Exit Condition — Requirement

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`exitConditionRequirement`<br/>Exit Condition Requirement</td>
    <td>Exit Condition — Requirement<br/><br/>• Required: Bu condition doğru olmadan üst Indicator Block çıkış sinyali üretemez.<br/><br/>• Supporting: Bu condition yardımcıdır; Condition Rule&#x27;un istediği sayıda yardımcı koşuldan biri olabilir.<br/><br/>Örnek: “Resistance Reached” Required, “RSI Bearish Divergence” Supporting olarak kurulabilir.</td>
  </tr>
</table>

### ⓘ Exit Condition — Validity

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`exitConditionValidity`<br/>Exit Condition Validity</td>
    <td>Exit Condition — Validity<br/><br/>Exit koşulu oluştuktan sonra kaç mum boyunca kullanılabilir sayılacağını belirler.<br/><br/>• Current Candle Only: Çıkış koşulu yalnızca görüldüğü mumda geçerlidir.<br/><br/>• 1 / 2 / 3 / 4 Candles: Koşul belirtilen süre boyunca aktif kalır.<br/><br/>• Until Opposite Condition: Karşıt koşul gelene kadar geçerli sayılır.<br/><br/>Örnek: Fiyat hedefe ulaştı fakat ikinci onay bir mum sonra geliyorsa validity 1 Candle seçimi bu iki koşulun birlikte exit üretmesine izin verebilir.</td>
  </tr>
</table>

### ⓘ Exit — Indicator Block

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`exitIndicatorBlock`<br/>Exit Indicator Block</td>
    <td>Exit — Indicator Block<br/><br/>Tek bir indikatörün açık pozisyondan çıkış kararına nasıl katkı vereceğini tanımlar. Seçtiğin Condition Block&#x27;lar bu indikatörün hangi davranışının exit sinyali olduğunu belirler.<br/><br/>Örnek: Predictive Ranges indicator&#x27;ı içinde “Price Near Resistance” condition&#x27;ı, long pozisyonda bir exit onayı olarak kullanılabilir.</td>
  </tr>
</table>

### ⓘ Exit Indicator Block — Requirement

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`exitRequirement`<br/>Exit Indicator Block Requirement</td>
    <td>Exit Indicator Block — Requirement<br/><br/>• Required: Bu Indicator Block geçerli çıkış sinyali üretmeden Signal Block&#x27;un exit eylemi çalışmaz.<br/><br/>• Supporting: Bu blok yardımcı çıkış onayıdır; gerekli olup olmadığını Indicator Rule belirler.<br/><br/>Örnek: Hedef bölgeye erişim Required; momentum zayıflaması Supporting olarak seçilebilir.</td>
  </tr>
</table>

### ⓘ Logic-Based Stop Block

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`logicBasedStopBlock`<br/>Logic-Based Stop Block</td>
    <td>Logic-Based Stop Block<br/><br/>Bir indikatör ve ona bağlı condition&#x27;lar üzerinden stop sinyali üretir. Fiyat önceden belirlenmiş yüzde stop seviyesine gelmeden önce, stratejinin temel mantığı bozulduysa pozisyonu kapatmak için kullanılır.<br/><br/>+ Add Condition , aynı indikatör için yeni bir koşul ekler. + Add Logic-Based Stop Block , farklı bir indikatörle ayrı bir stop kuralı kurar.<br/><br/>Örnek: Long pozisyon için Smoothed Heiken Ashi seçip “Color Turns Red” condition&#x27;ı eklenirse, gösterge kırmızıya döndüğünde stop sinyali üretilebilir.</td>
  </tr>
</table>

### ⓘ Scaling Condition — Requirement

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`scalingRequirement`<br/>Scaling Condition Requirement</td>
    <td>Scaling Condition — Requirement<br/><br/>• Required: Bu condition true olmadan ilgili Indicator Block layer ekleme sinyali üretemez.<br/><br/>• Supporting: Yardımcı onay olarak değerlendirilir; üstte kurulan rule mantığına göre karara katkı verir.<br/><br/>Örnek: Ana sinyalin yönü Required, hacim desteği Supporting olarak kurulabilir.</td>
  </tr>
</table>

### ⓘ Order Type

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`orderType`<br/>Order Type</td>
    <td>Order Type<br/><br/>Bu seçim, sinyal oluştuğunda backtest motorunun pozisyona nasıl girmiş sayacağını belirler. Emir türü, giriş fiyatını, işlem sayısını ve slippage etkisini doğrudan değiştirebilir.<br/><br/>• Market Order: Sinyal geldiğinde pozisyon piyasa fiyatından hemen açılmış kabul edilir. En basit ve en hızlı dolum varsayımıdır; spread ve slippage etkisi ayrıca uygulanabilir.<br/><br/>• Limit Order: Emir sadece belirlenen limit fiyatına gelinirse dolmuş sayılır. Daha iyi fiyat hedeflenir ama fiyat oraya gelmezse işlem kaçabilir.<br/><br/>• Stop Order: Fiyat belirlenen tetik seviyesine ulaşınca emir aktive olur ve genellikle market davranışına yakın şekilde işleme girer. Breakout veya momentum girişlerinde kullanılabilir.<br/><br/>• Stop-Limit Order: Önce stop seviyesi tetiklenir, sonra limit fiyat koşulu aranır. Tetik oluşsa bile limit fiyat dolmazsa pozisyon açılmayabilir.<br/><br/>• Simulation Only: Gerçek emir tipi gibi davranmaz; sinyalin pozisyon açma mantığını basitleştirilmiş sanal dolumla test etmek için kullanılır.<br/><br/>Örnek: Long sinyali 100 seviyesinde geldi. Market Order seçilirse işlem 100 civarında hemen açılır. Limit Order seçilirse sistem örneğin 99.50 seviyesine geri çekilme bekleyebilir. Fiyat 99.50’ye inmezse işlem gerçekleşmez.</td>
  </tr>
</table>

### ⓘ Limit Order Details

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`limitOrderDetails`<br/>Limit Order Details</td>
    <td>Limit Order Details<br/><br/>Limit emir, “şu fiyattan veya daha iyi fiyattan işlem aç” talimatıdır. Backtest, limit emri gerçekten kullanılabilir biçimde simüle edecekse sadece sinyalin oluştuğunu bilmek yetmez; fiyatın nasıl yerleştirileceğini, ne kadar süre bekleneceğini, dolmazsa ne yapılacağını ve kısmi dolumun kabul edilip edilmeyeceğini de bilmelidir.<br/><br/>Örnek: Long sinyali 100 fiyatta oluştu. Limit fiyat 99.50 seçilmişse, fiyat bu seviyeye geri gelmeden pozisyon açılmış kabul edilmemelidir.</td>
  </tr>
</table>

### ⓘ Limit Price Rule

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`limitPriceRule`<br/>Limit Price Rule</td>
    <td>Limit Price Rule<br/><br/>Bu seçim, sinyal oluştuktan sonra limit emrin hangi fiyata yazılacağını belirler. Fiyat seçimi, işlem sayısını ve görünen performansı doğrudan değiştirebilir.<br/><br/>• Entry signal price: Emir, sinyalin hesaplandığı fiyat seviyesine konur. Örneğin sinyal 100&#x27;de oluştuysa limit 100 olur.<br/><br/>• Best bid / ask: O anda piyasada görülen en yakın alınabilir/satılabilir fiyat kullanılır. İşlem gerçekleşme ihtimali daha yüksektir; ancak spread etkisini taşır.<br/><br/>• Signal price minus offset: Limit fiyat sinyal fiyatından daha aşağıya konur. Long işlemde daha ucuz giriş beklenir; fiyat geri gelmezse işlem kaçabilir.<br/><br/>• Signal price plus offset: Emir daha kolay dolabilecek tarafa yaklaştırılır. Dolum ihtimali artar fakat daha kötü fiyattan işlem açılabilir.<br/><br/>Örnek: Long sinyali 100, offset %0.5 ise Signal price minus offset seçimi 99.50&#x27;de alış bekler.</td>
  </tr>
</table>

### ⓘ Order Validity

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`orderValidity`<br/>Order Validity</td>
    <td>Order Validity<br/><br/>Limit emir hemen dolmak zorunda değildir. Bu alan, emir dolmadan bekleyebileceği süreyi belirler. Süre dolunca emir artık o sinyale ait geçerli bir giriş sayılmaz.<br/><br/>• Current candle only: Fiyat aynı mum içinde limite dokunmazsa işlem iptal edilir.<br/><br/>• 1 candle: Emir bir sonraki mum boyunca da dolabilir; sonrasında iptal edilir.<br/><br/>• 3 candles: Emir üç mum boyunca bekler. Daha fazla dolum olabilir ancak eski bir sinyalle geç giriş riski artar.<br/><br/>• 4 candles: Daha uzun bekleme süresidir; özellikle yavaş stratejiler için kullanılabilir.<br/><br/>• Until cancelled: Başka bir iptal kuralı çalışana kadar emir açık kabul edilir.<br/><br/>Örnek: 15 dakikalık veride “3 candles”, limit emrin en fazla 45 dakika bekleyebilmesi anlamına gelir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>IMPLEMENTATION ALIGNMENT NOTE<br/>Final text alignment: V18 form uses `3 candles`, `Current candle only`, `1 candle`, `5 candles`, `Until cancelled`; the older popover phrase “4 candles” is not retained.</th>
  </tr>
</table>

### ⓘ If Not Filled

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`ifNotFilled`<br/>If Not Filled</td>
    <td>If Not Filled<br/><br/>Limit emir seçilmiş fiyata hiç ulaşmazsa sistemin ne yapacağını belirler. Bu karar verilmezse backtest dolmayan işlemleri yanlışlıkla gerçekleşmiş sayabilir.<br/><br/>• Cancel Order: Süre bittiğinde emir iptal edilir; pozisyon açılmaz.<br/><br/>• Convert to Market Order: Limit dolmazsa emir o andaki piyasa fiyatından açılır. İşlem kaçmaz, fakat giriş fiyatı kötüleşebilir.<br/><br/>• Wait Until Validity Ends: Belirlenen süre bitene kadar beklenir; süreç içinde fiyat limite dokunursa işlem açılır.<br/><br/>• Re-price Next Candle: Sonraki mumda yeni piyasa bilgisine göre limit fiyatı yeniden hesaplanır.<br/><br/>• Skip Trade: Bu sinyal fırsatı tamamen geçilir; yeni sinyal beklenir.<br/><br/>Örnek: Limit alış 99.50, fiyat 100&#x27;den 103&#x27;e gitti ve limite dönmedi. Skip Trade işlem açmaz; Convert to Market Order ise daha yüksek fiyattan pozisyona sokar.</td>
  </tr>
</table>

<table>
  <tr>
    <th>IMPLEMENTATION ALIGNMENT NOTE<br/>Final text alignment: V18 form exposes `Cancel Order`, `Keep Until Validity Ends`, `Re-price Next Candle`, `Convert to Market Order`. “Skip Trade” is not a separate Production option unless later added as a new enum/versioned schema.</th>
  </tr>
</table>

### ⓘ Partial Fill

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`partialFill`<br/>Partial Fill</td>
    <td>Partial Fill<br/><br/>Gerçek piyasada verilen emrin tamamı aynı anda karşılanmayabilir. Bu alan, emrin yalnızca bir kısmı dolduğunda backtestin ne kabul edeceğini söyler.<br/><br/>• Not Allowed: Emir tam miktarda dolmadıkça pozisyon açılmış sayılmaz.<br/><br/>• Allowed: Dolan miktar kadar pozisyon açılır; sonuçlar daha küçük açık pozisyon üzerinden hesaplanır.<br/><br/>• Minimum 50% Fill: Emrin en az yarısı dolmuşsa işlem geçerli kabul edilir.<br/><br/>• Fill Remaining as Market: Dolmayan bölüm, piyasa fiyatından tamamlanır; slippage doğabilir.<br/><br/>• Cancel Remaining: Dolan bölüm korunur; geri kalan emir iptal edilir.<br/><br/>Örnek: 10 birimlik emirden yalnızca 6 birim dolduysa, Minimum 50% Fill işlemi kabul eder; Not Allowed kabul etmez.</td>
  </tr>
</table>

### ⓘ Intrabar / Funding

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`intrabarFunding`<br/>Intrabar / Funding</td>
    <td>Intrabar / Funding<br/><br/>Bu alan iki ayrı gerçekçilik katmanını yönetir: mumun içindeki fiyat sırasını görmek için daha detaylı veri kullanımı ve kaldıraçlı perpetual işlemlerde periyodik fonlama maliyetinin sonuca eklenmesi.<br/><br/>Örnek: Aynı 15 dakikalık mum içinde hem stop hem kâr hedefi görünüyorsa, tick verisi hangi seviyenin önce çalıştığını gösterebilir.</td>
  </tr>
</table>

### ⓘ Use Tick Data

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`useTickDataFor`<br/>Use Tick Data</td>
    <td>Use Tick Data<br/><br/>Tick data, mumun içindeki fiyat hareketini daha ayrıntılı görmek için kullanılır. Bu alan artık sade bir aç/kapat tercihi olarak düşünülmeli.<br/><br/>• None: Bu strateji için tick data tercihi belirtilmez; sistem genel varsayıma dönebilir.<br/><br/>• Yes: Tick data mevcutsa giriş, çıkış, stop ve intrabar kontrolünde daha ayrıntılı fiyat akışı kullanılabilir.<br/><br/>• No: Tick data kullanılmaz; hesaplama OHLCV mum verisi üzerinden yapılır.<br/><br/>Örnek: Aynı mum içinde hem stop hem take profit görünüyorsa tick data varsa önce hangisinin çalıştığı daha doğru anlaşılır. Tick data yoksa motor seçilen muhafazakâr varsayıma göre karar verir.</td>
  </tr>
</table>

### ⓘ Funding Fee

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`fundingFee`<br/>Funding Fee</td>
    <td>Funding Fee<br/><br/>Perpetual vadeli işlemlerde açık pozisyon belirli saatlerde fonlama ödemesi yapabilir veya alabilir. Bu seçenek, funding etkisinin tarihsel veriyle uygulanıp uygulanmayacağını belirler.<br/><br/>• Use Historical Funding Data: Test tarihindeki gerçek funding oranları uygulanır. Veri mevcutsa en gerçekçi seçenektir.<br/><br/>• Disabled: Funding etkisi sonuçlara eklenmez.<br/><br/>Örnek: Long pozisyon üç funding döneminden geçtiyse, her dönemdeki maliyet işlem kârından düşülür veya pozisyona göre eklenir.</td>
  </tr>
</table>

### ⓘ Funding Source

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`fundingSource`<br/>Funding Source</td>
    <td>Funding Source<br/><br/>Funding Fee aktif olduğunda hesaplamada kullanılacak oranların hangi veri kaynağından geleceğini belirler. Test edilen piyasa ile veri kaynağının eşleşmesi önemlidir.<br/><br/>• Binance Historical Funding: Binance perpetual sözleşmesine ait geçmiş funding oranları kullanılır.<br/><br/>• Bybit Historical Funding: Bybit perpetual piyasasının geçmiş oranları kullanılır.<br/><br/>• Manual Funding Source: Kullanıcı kendi girdiği oran veya tabloyu kullanır.<br/><br/>Örnek: Binance BTCUSDT perpetual üzerinde test yapıyorsan, Binance tarihsel funding verisini kullanmak sonuçla işlem ortamını uyumlu tutar.</td>
  </tr>
</table>

### ⓘ 3. Position Entry Logic

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`positionEntryLogic`<br/>Position Entry Logic</td>
    <td>3. Position Entry Logic<br/><br/>Bu bölüm, henüz pozisyon yokken hangi koşulların yeni bir işlem açacağını tanımlar. Yapı iki katmandan oluşur: Indicator Block bir indikatörün sinyal üretip üretmediğini değerlendirir; Signal Block birden fazla indikatörün birlikte giriş kararı üretip üretmeyeceğini değerlendirir.<br/><br/>Örnek: Reversal Sensor zorunlu olsun; Smoothed Heiken Ashi ve Volume Breakout supporting olsun. “Required + Minimum Supporting Indicator Blocks = 1” seçilirse Reversal Sensor doğru olmadan giriş olmaz; ayrıca supporting bloklardan en az biri de doğrulamalıdır.</td>
  </tr>
</table>

### ⓘ Entry Signal Block

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`entrySignalBlock`<br/>Entry Signal Block</td>
    <td>Entry Signal Block<br/><br/>Signal Block, giriş kararının en üst karar kutusudur. İçindeki Indicator Block&#x27;ları tek tek değerlendirir ve seçilen Indicator Rule&#x27;a göre nihai “pozisyon aç” sinyali üretir.<br/><br/>Bir indikatörün tek başına yeterli olmadığı stratejilerde, ana sinyali zorunlu tutup yardımcı sinyallerden belirli sayıda onay istemek için kullanılır.<br/><br/>Örnek: Ana dönüş göstergesi Required , hacim ve trend göstergeleri Supporting seçilebilir. Böylece sinyal sadece dönüş görüldüğü ve piyasa koşulu en az bir yardımcı göstergeden onay aldığı zaman üretilir.</td>
  </tr>
</table>

### ⓘ Entry Signal Block — Indicator Block Rule

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`entryIndicatorRule`<br/>Entry Signal Block — Indicator Block Rule</td>
    <td>Entry Signal Block — Indicator Block Rule<br/><br/>Bu açılır menü, Signal Block içindeki Required ve Supporting Indicator Block&#x27;ların nasıl birlikte karar vereceğini belirler.<br/><br/>• Required Indicator Blocks Only: Yalnızca Required bloklar değerlendirilir; hepsi geçerliyse giriş sinyali oluşur. Supporting bloklar göz ardı edilir.<br/><br/>• Required + Any Supporting Indicator Block: Tüm Required bloklar geçerli olmalı; buna ek olarak Supporting bloklardan birinin geçerli olması yeterlidir.<br/><br/>• Required + Minimum Supporting Indicator Blocks: Tüm Required bloklar geçerli olmalı; ayrıca “Min. Supporting Indicator Blocks Count” alanında yazan sayı kadar Supporting blok geçerli olmalıdır.<br/><br/>• Required + All Confirmations: Required ve Supporting olarak eklenen tüm blokların geçerli olması gerekir; en katı seçimdir.<br/><br/>Örnek: Bir Required ve üç Supporting blok var. Minimum sayı 2 seçilirse ana blok + yardımcı bloklardan ikisi doğru olduğunda giriş sinyali oluşur.</td>
  </tr>
</table>

### ⓘ Signal Block — Min. Supporting Indicator Blocks Count

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`entryMinimumSupportingIndicatorCount`<br/>Min. Supporting Indicator Blocks Count</td>
    <td>Signal Block — Min. Supporting Indicator Blocks Count<br/><br/>Bu sayı, Signal Block içindeki Supporting Indicator Block &#x27;lardan kaç tanesinin giriş kararını onaylaması gerektiğini belirler. Yalnızca Indicator Rule içinde Required + Minimum Supporting Indicator Blocks seçildiğinde anlamlıdır.<br/><br/>Bu alan, bir Indicator Block&#x27;un içindeki condition sayısını değil, birbirinden ayrı indikatör bloklarının onay sayısını kontrol eder.<br/><br/>Örnek: Reversal Sensor Required ; RSI, Volume Breakout ve Smoothed Heiken Ashi Supporting olsun. Count = 2 seçilirse, Reversal Sensor doğru olduktan sonra üç yardımcı indikatörden en az ikisinin de doğru olması gerekir.</td>
  </tr>
</table>

### ⓘ 4. Position Exit Logic

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`positionExitLogic`<br/>Position Exit Logic</td>
    <td>4. Position Exit Logic<br/><br/>Bu bölüm, açık bir pozisyonun normal strateji kararıyla nasıl yönetileceğini belirler. Stop bölümünden farkı şudur: exit, kâr alma veya strateji sinyalinin bittiğini görme gibi planlı çıkış davranışlarını tanımlar; stop ise risk korumasıdır.<br/><br/>Örnek: Long pozisyonda fiyat direnç bölgesine ulaştığında %50 kapatıp kalan pozisyonu trailing stop ile yönetmek, Position Exit Logic içinde tarif edilir.</td>
  </tr>
</table>

### ⓘ Exit Signal Block

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`exitSignalBlock`<br/>Exit Signal Block</td>
    <td>Exit Signal Block<br/><br/>Açık pozisyonda hangi indicator onaylarının bir exit eylemi oluşturacağını belirleyen üst bloktur. Önce hangi pozisyona uygulanacağını ve oluştuğunda ne yapılacağını seçersin; ardından Indicator Block&#x27;larla çıkış koşulunu kurarsın.<br/><br/>Örnek: Bu blok yalnızca long pozisyonlara uygulanabilir ve “Close 50%” eylemiyle, long trend zayıflayınca pozisyonun yarısını kapatabilir.</td>
  </tr>
</table>

### ⓘ Applies To Position

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`appliesToPosition`<br/>Applies To Position</td>
    <td>Applies To Position<br/><br/>Exit Signal Block&#x27;un hangi açık pozisyon türünde değerlendirileceğini belirler.<br/><br/>• Long Positions: Yalnızca alış yönünde açık pozisyon varsa bu exit kuralı çalışır.<br/><br/>• Short Positions: Yalnızca satış yönünde açık pozisyon varsa çalışır.<br/><br/>• Long &amp; Short Positions: Aynı çıkış yapısı her iki yön için de değerlendirilebilir; seçilen condition&#x27;ın yönle uyumlu kurulması gerekir.<br/><br/>Örnek: “Price Near Resistance” long pozisyon için kâr alma nedeni olabilir; short pozisyon için aynı koşul genellikle çıkış nedeni olmaz.</td>
  </tr>
</table>

### ⓘ Exit Action

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`exitAction`<br/>Exit Action</td>
    <td>Exit Action<br/><br/>Geçerli exit sinyali oluştuğu anda açık pozisyona uygulanacak işlemdir.<br/><br/>• Close 100%: İlgili pozisyon tamamen kapatılır.<br/><br/>• Close 75% / 50% / 25%: Pozisyonun yalnızca belirtilen bölümü kapanır; kalan kısmın yönetimi After Partial Close ile belirlenir.<br/><br/>• Move Stop to Entry: Pozisyon kapanmaz; stop giriş fiyatına taşınarak artık başlangıç sermayesi korunmaya çalışılır.<br/><br/>• Activate Trailing Stop: Pozisyon kapanmaz; fiyat kâra devam ederse takip edilir, geri dönerse kapanır.<br/><br/>• Block New Scaling: Pozisyon açık kalır fakat yeni layer eklenemez.<br/><br/>• Exit Warning Only: Eylem uygulanmaz; sinyal yalnızca kaydedilir.<br/><br/>Örnek: İlk hedefe ulaşıldığında Close 50% seçip kalan yarıyı trailing ile taşımak mümkündür.</td>
  </tr>
</table>

### ⓘ After Partial Close

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`afterPartialClose`<br/>After Partial Close</td>
    <td>After Partial Close<br/><br/>Exit Action pozisyonun tamamını değil bir kısmını kapatıyorsa, açık kalan miktarın bundan sonra nasıl yönetileceğini belirler.<br/><br/>• Continue With Existing Exit / Stop Rules: Kalan pozisyon aynı kurallarla izlenmeye devam eder.<br/><br/>• Move Stop to Entry: Kalan miktarın stop seviyesi ilk giriş fiyatına taşınır.<br/><br/>• Activate Trailing Stop: Kalan miktar fiyatı takip eden stop ile yönetilir.<br/><br/>• Close Remaining Position at Next Exit Signal: Sonraki geçerli exit sinyalinde geri kalan bölüm tamamen kapatılır.<br/><br/>• Block New Scaling: Kalan pozisyon açık kalır fakat ek kademe açılmaz.<br/><br/>Örnek: Pozisyonun %50&#x27;si hedefte kapandıktan sonra Move Stop to Entry seçilirse kalan %50&#x27;nin zarara dönüşmesi engellenmeye çalışılır.</td>
  </tr>
</table>

### ⓘ Exit Signal Block — Indicator Block Rule

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`exitIndicatorRule`<br/>Exit Signal Block — Indicator Block Rule</td>
    <td>Exit Signal Block — Indicator Block Rule<br/><br/>Exit kararında Required ve Supporting Indicator Block&#x27;ların nasıl birleşeceğini belirler.<br/><br/>• Required Indicator Blocks Only: Yalnızca Required blokların tamamı exit sinyali üretirse eylem uygulanır.<br/><br/>• Required + Any Supporting Indicator Block: Required bloklara ek olarak herhangi bir supporting çıkış onayı yeterlidir.<br/><br/>• Required + Minimum Supporting Indicator Blocks: Required bloklara ek olarak belirtilen sayıda supporting onay gereklidir.<br/><br/>• Required + All Confirmations: Eklenen bütün bloklar çıkışı onaylamalıdır.<br/><br/>Örnek: Dirence ulaşma Required, Heiken Ashi&#x27;nin kırmızıya dönmesi Supporting ise, minimum sayı 1 seçildiğinde ancak ikisi birlikte görülürse kısmi çıkış yapılır.</td>
  </tr>
</table>

### ⓘ 5. Protection / Stop Logic

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`protectionStopLogic`<br/>Protection / Stop Logic</td>
    <td>5. Protection / Stop Logic<br/><br/>Bu bölüm, açık pozisyonun risk nedeniyle hangi koşullarda kapatılacağını belirler. Entry veya normal Exit mantığından bağımsız koruma katmanıdır. Birden fazla stop kuralı aynı anda aktif olabilir.<br/><br/>Örnek: Pozisyon %1 zarar görürse Percentage Stop kapanış üretir. Ancak fiyat zarara ulaşmadan indikatör ters sinyal verirse Logic-Based Stop Block daha önce çalışabilir.</td>
  </tr>
</table>

### ⓘ Stop Mode — Stop Trigger Requirement

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`stopMode`<br/>Stop Mode</td>
    <td>Stop Mode — Stop Trigger Requirement<br/><br/>Aktif stop bloklarından kaçının stop kararı vermesi gerektiğini belirler.<br/><br/>• Any Active Stop Rule Triggers Stop: Aktif kurallardan biri bile tetiklenirse pozisyon kapatılır. Risk koruması açısından doğrudan davranıştır.<br/><br/>• All Active Stop Rules Must Trigger Stop: Pozisyonun kapanması için aktif stop kurallarının tamamı aynı kararı vermelidir. Daha geç çıkışa ve daha yüksek riske yol açabilir.<br/><br/>Örnek: Percentage Stop %1&#x27;de çalıştı ama trailing tetiklenmedi. “Any” seçiliyse pozisyon hemen kapanır; “All” seçiliyse kapanmaz.</td>
  </tr>
</table>

### ⓘ Stop Rules

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`stopRules`<br/>Stop Rules</td>
    <td>Stop Rules<br/><br/>Bu alandaki her stop türü eşit seviyede bir koruma kuralıdır ve solundaki checkbox ile aktif edilir. Logic-Based Stop Block indikatör/condition ile; Percentage Stop sabit zarar mesafesiyle; Trailing Stop kârı takip ederek; Absolute Price Stop belirli fiyat seviyesinde çalışır.<br/><br/>Aktif kuralların birbirleriyle nasıl karar vereceğini Stop Mode belirler.</td>
  </tr>
</table>

### ⓘ Percentage Stop

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`percentageStop`<br/>Percentage Stop</td>
    <td>Percentage Stop<br/><br/>Giriş fiyatından itibaren pozisyonun aleyhine belirlenen yüzde kadar hareket olduğunda stop üretir. İndikatör beklemez; fiyat mesafesine dayanır.<br/><br/>Örnek: Long işlem 100 fiyattan açıldı ve Stop Distance %1.00 seçildi. Fiyat 99&#x27;a düşerse Percentage Stop tetiklenir.</td>
  </tr>
</table>

### ⓘ Trailing Stop

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`trailingStop`<br/>Trailing Stop</td>
    <td>Trailing Stop<br/><br/>Fiyat belirli miktarda kâra ulaştıktan sonra aktifleşen ve fiyat lehine ilerledikçe stop seviyesini taşıyan korumadır. Amaç, kazanan pozisyonun bir kısmını geri vermeden trendin devamına alan bırakmaktır.<br/><br/>Örnek: Long işlem 100&#x27;den açıldı. Activate After Profit %2 ise trailing 102&#x27;de devreye girer. Trailing Distance %0.8 ise fiyat 105&#x27;e ulaştığında stop yaklaşık 104.16 seviyesine kadar yükselmiş olur.</td>
  </tr>
</table>

### ⓘ Base Position Size

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`basePositionSize`<br/>Base Position Size</td>
    <td>Base Position Size<br/><br/>İşleme doğrudan sermayenin belirli bir yüzdesiyle girmek için kullanılan pozisyon boyutu yöntemidir. Seçildiğinde Risk Per Trade ve Custom Formula pasif hale gelir; çünkü tek işlem için iki farklı boyutlandırma yöntemi aynı anda kullanılamaz.<br/><br/>Örnek: Equity 10.000 USD ve Position Size %10 ise ilk pozisyon nominal olarak 1.000 USD üzerinden oluşturulur; kaldıraç etkisi ayrıca uygulanır.</td>
  </tr>
</table>

### ⓘ Risk Per Trade

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`riskPerTrade`<br/>Risk Per Trade</td>
    <td>Risk Per Trade<br/><br/>Pozisyon büyüklüğünü, stop gerçekleşirse kaybedilecek toplam sermaye oranına göre hesaplatır. Bu yöntemin çalışabilmesi için kullanılacak stop mesafesi motor tarafından bilinmelidir.<br/><br/>Örnek: Equity 10.000 USD, risk %1 ise maksimum zarar 100 USD&#x27;dir. Stop mesafesi %2 ise sistem, stopta yaklaşık 100 USD kaybettirecek pozisyon miktarını hesaplar.</td>
  </tr>
</table>

### ⓘ Custom Formula

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`customFormula`<br/>Custom Formula</td>
    <td>Custom Formula<br/><br/>Pozisyon büyüklüğünün kullanıcının tanımladığı formülle hesaplanmasını sağlar. Formül; equity, volatilite, sinyal gücü veya başka değişkenleri kullanabilir. Seçildiğinde diğer iki boyutlandırma yöntemi pasif kalır.<br/><br/>Örnek: positionSize = equity * 0.05 * volatilityAdjustment düşük volatilitede daha büyük, yüksek volatilitede daha küçük pozisyon üretebilir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>IMPLEMENTATION ALIGNMENT NOTE<br/>Canonical alignment: Custom Formula is a versioned restricted DSL/AST. It does not evaluate free Python, JavaScript or PineScript.</th>
  </tr>
</table>

### ⓘ Max Single Position

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`maxSinglePosition`<br/>Max Single Position</td>
    <td>Max Single Position<br/><br/>Tek bir pozisyonun ulaşabileceği maksimum büyüklüğü sınırlar. Base Position Size, Risk Per Trade veya Custom Formula daha büyük bir miktar hesaplamış olsa bile bu sınır aşılmaz.<br/><br/>Örnek: Max Single Position %25 ise bir sinyal çok güçlü görünse bile tek pozisyon equity&#x27;nin %25&#x27;inden büyük açılamaz.</td>
  </tr>
</table>

### ⓘ Max Total Exposure

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`maxTotalExposure`<br/>Max Total Exposure</td>
    <td>Max Total Exposure<br/><br/>Aynı stratejiye ait açık pozisyonların ve scaling ile eklenen layer&#x27;ların toplam büyüklük sınırıdır. Scaling Logic bu değeri aşacak yeni kademe oluşturamaz.<br/><br/>Örnek: Açık ana pozisyon %10 ve ek layer&#x27;lar toplam %35&#x27;e ulaştıysa, Max Total Exposure %40 iken yeni %10 layer açılamaz.</td>
  </tr>
</table>

### ⓘ Leverage Mode

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`leverageMode`<br/>Leverage Mode</td>
    <td>Leverage Mode<br/><br/>Kaldıraçlı pozisyonun teminat yapısını belirler.<br/><br/>• No Leverage: Pozisyon kaldıraç kullanılmadan hesaplanır.<br/><br/>• Isolated: Pozisyona ayrılan teminat o pozisyonla sınırlıdır; zarar doğrudan tüm hesabın marjinini kullanmaz.<br/><br/>• Cross: Uygun hesap bakiyesi açık pozisyonun marjinini destekleyebilir; risk hesabı tüm açık marjin ilişkisini dikkate almalıdır.<br/><br/>Örnek: Isolated 5x seçilmiş pozisyonda, o işlem için ayrılan teminat ve likidasyon davranışı ayrı hesaplanır.</td>
  </tr>
</table>

### ⓘ Signal Strength Sizing

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`signalStrengthConditionPackage`<br/>Signal Strength Sizing</td>
    <td>Signal Strength Sizing<br/><br/>Bu bölüm, sinyal gücünün pozisyon büyüklüğünü ancak seçilen Condition Package sağlandığında etkilemesini sağlar.</td>
  </tr>
</table>

### ⓘ 7. Scaling Logic

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`scalingLogic`<br/>Scaling Logic</td>
    <td>7. Scaling Logic<br/><br/>Scaling Logic, zaten açık olan bir pozisyona aynı yönde yeni layer eklemeyi tanımlar. Bu bölüm pozisyon azaltma veya partial close için kullanılmaz; çıkış işlemleri Position Exit Logic içinde kalır.<br/><br/>Örnek: Long pozisyon açıkken fiyat %1 aleyhe hareket ettiğinde yeni long layer eklemek Price-Distance Based Scaling; yeni bir indicator onayı gelince layer eklemek Logic-Based Scaling&#x27;dir.</td>
  </tr>
</table>

### ⓘ 1. Scaling Timeframe Structure

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`scalingTimeframeStructure`<br/>Scaling Timeframe Structure</td>
    <td>1. Scaling Timeframe Structure<br/><br/>Yalnızca Logic-Based Scaling kurallarının hangi timeframe&#x27;de değerlendirileceğini belirler. Price-Distance Based Scaling doğrudan fiyat mesafesiyle tetiklendiğinden bu timeframe dizisini kullanmaz.<br/><br/>Örnek: Ana strateji 15m iken layer 1 için 15m, layer 2 için 30m, layer 3 için 1h sinyali aramak, yeni kademe açıldıkça daha güçlü onay istemek anlamına gelir.</td>
  </tr>
</table>

### ⓘ Timeframe Mode

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`timeframeMode`<br/>Timeframe Mode</td>
    <td>Timeframe Mode<br/><br/>• Same as Strategy Timeframe: Tüm Logic-Based layer sinyalleri Strategy Context içindeki ana timeframe ile kontrol edilir.<br/><br/>• Increasing Timeframe by Layer: Her yeni layer&#x27;da sistem ana timeframe&#x27;den başlayarak bir üst timeframe&#x27;e geçer.<br/><br/>• Custom Timeframe Sequence: Layer sırasına uygulanacak timeframe dizisini kullanıcı yazar.<br/><br/>Örnek: Ana timeframe 15m ve Increasing seçiliyse, sistem sırasıyla 15m → 30m → 1h gibi daha yüksek zaman dilimi onayları kullanabilir.</td>
  </tr>
</table>

### ⓘ Custom Timeframe Sequence

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`customTimeframeSequence`<br/>Custom Timeframe Sequence</td>
    <td>Custom Timeframe Sequence<br/><br/>Her yeni logic-based layer&#x27;ın hangi timeframe üzerinden sinyal arayacağını elle tanımlarsın. Bu input yalnızca Timeframe Mode içinde Custom Timeframe Sequence seçildiğinde aktif olur.<br/><br/>Kullanılabilir timeframe seçimleri: 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1D, Custom .<br/><br/>Örnek: 15m &gt; 30m &gt; 1h &gt; 4h yazılmışsa birinci layer 15m, ikinci layer 30m, üçüncü layer 1h onayı ile eklenir.</td>
  </tr>
</table>

### ⓘ 2. Additional Layer Method

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`additionalLayerMethod`<br/>Additional Layer Method</td>
    <td>2. Additional Layer Method<br/><br/>Açık pozisyona yeni layer&#x27;ın hangi yöntemle ekleneceğini belirler. Price-Distance Based Scaling ve Logic-Based Scaling eşit seviyede iki alternatif yöntemdir; aynı anda yalnızca biri aktif olabilir.<br/><br/>Örnek: Fiyat her %1 düştüğünde long layer eklemek mesafe tabanlıdır. Reversal Sensor tekrar long sinyal verdiğinde layer eklemek logic tabanlıdır.</td>
  </tr>
</table>

### ⓘ Price-Distance Based Scaling

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`priceDistanceScaling`<br/>Price-Distance Based Scaling</td>
    <td>Price-Distance Based Scaling<br/><br/>Yeni layer&#x27;ı indikatör beklemeden, fiyatın seçilen referans noktadan belirli yüzde kadar hareket etmesiyle ekler. Fiyatın pozisyona karşı mı yoksa pozisyon lehine mi hareketinde ekleneceği ayrıca seçilir.<br/><br/>Örnek: Long pozisyon açık, Direction “Against Open Position”, mesafe %1 ve Reference “Previous Filled Layer” ise; her önceki dolan layer&#x27;dan %1 aşağıda yeni long layer tetiklenir.</td>
  </tr>
</table>

### ⓘ Price Movement Direction

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`priceMovementDirection`<br/>Price Movement Direction</td>
    <td>Price Movement Direction<br/><br/>• Against Open Position: Fiyat mevcut pozisyonun zarar yönüne giderken layer eklenir. Long için düşüş, short için yükseliştir.<br/><br/>• In Favor of Open Position: Fiyat pozisyonun kâr yönüne giderken layer eklenir. Bu, kazanan pozisyona ekleme davranışıdır.<br/><br/>Örnek: Long pozisyonda fiyat yükselirken layer eklemek “In Favor”; fiyat düşerken maliyet ortalaması için eklemek “Against” seçeneğidir.</td>
  </tr>
</table>

### ⓘ Reference Price

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`referencePrice`<br/>Reference Price</td>
    <td>Reference Price<br/><br/>• Initial Entry Price: Her layer mesafesi ilk açılan pozisyon fiyatına göre ölçülür.<br/><br/>• Previous Filled Layer: Yeni layer mesafesi son dolmuş layer fiyatından itibaren ölçülür; kademeler birbirine eşit aralıkla ilerleyebilir.<br/><br/>Örnek: İlk giriş 100, layer aralığı %1. Initial Entry seçiliyse bir sonraki ölçüm yine 100&#x27;e dayanır; Previous Filled Layer seçiliyse 99&#x27;da dolan layer&#x27;dan sonra sonraki tetik yaklaşık 98.01 üzerinden ölçülür.</td>
  </tr>
</table>

### ⓘ Logic-Based Scaling

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`logicBasedScaling`<br/>Logic-Based Scaling</td>
    <td>Logic-Based Scaling<br/><br/>Yeni layer yalnızca tanımlı Signal Block içindeki indicator/condition kuralları geçerli olduğunda eklenir. Fiyatın belirli mesafeye gelmesi tek başına yeterli değildir.<br/><br/>Örnek: Zarar yönünde hareket eden long pozisyona, ancak Predictive Ranges desteği korunuyor ve Reversal Sensor yeniden long sinyal üretiyorsa layer eklenebilir.</td>
  </tr>
</table>

### ⓘ Logic Combination

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`logicCombination`<br/>Logic Combination</td>
    <td>Logic Combination<br/><br/>Birden fazla Logic-Based Rule eklenmişse bunların yeni layer kararı için nasıl birleşeceğini belirler.<br/><br/>• All Logic-Based Rules Must Be Met: Eklenen her kural doğru olmalıdır.<br/><br/>• Any Logic-Based Rule Can Be Met: Kurallardan birinin doğru olması layer eklemek için yeterlidir.<br/><br/>• Minimum N of M Logic-Based Rules Must Be Met: Toplam kural sayısından belirlenen adet doğru olmalıdır; Required True Rule Count bu seçimde aktif olur.<br/><br/>Örnek: Üç farklı logic rule var ve minimum sayı 2 ise, üç kuraldan ikisi geçerli olduğunda layer eklenir.</td>
  </tr>
</table>

### ⓘ Required True Rule Count

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`logicBasedRulesRequiredToScale`<br/>Logic-Based Rules Required to Scale</td>
    <td>Required True Rule Count<br/><br/>Logic Combination içinde yalnızca Minimum N of M Logic-Based Rules Must Be Met seçildiğinde kullanılır. Yeni layer açılabilmesi için kaç ayrı logic-based rule&#x27;un geçerli olması gerektiğini sayısal olarak belirtir.<br/><br/>Örnek: Toplam dört rule eklenmiş ve değer 3 yazılmışsa, en az üç rule true olmadan yeni layer açılmaz.</td>
  </tr>
</table>

### ⓘ Add Size Per Scale

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`addSizePerScale`<br/>Add Size Per Scale</td>
    <td>Add Size Per Scale<br/><br/>Scale koşulu gerçekleştiğinde açık pozisyona aynı yönde ne kadar ekleme yapılacağını belirler.</td>
  </tr>
</table>

### ⓘ 3. Layer Size & Scaling Limits

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`scalingLimits`<br/>Scaling Limits</td>
    <td>3. Layer Size &amp; Scaling Limits<br/><br/>Yeni layer&#x27;ların büyüklüğünü ve scaling davranışının kontrol sınırlarını belirler. Scaling yöntemi sinyal üretiyor olsa bile bu sınırlar aşılırsa yeni layer eklenmez.<br/><br/>Örnek: Maksimum ek layer sayısı 3 ise dördüncü ekleme sinyali görülse bile yeni layer açılmaz.</td>
  </tr>
</table>

### ⓘ Restriction Rule

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`restrictionRule`<br/>Restriction Rule</td>
    <td>Restriction Rule<br/><br/>Restriction, entry sinyali doğru olsa bile yeni pozisyon açılmasını sınırlayan güvenlik veya piyasa uygunluğu kontrolüdür. Bu açılır menü aktif filtrelerin nasıl birleşeceğini belirler.<br/><br/>• If ANY restriction is active, block entry: Aktif filtrelerden biri risk gördüğünde yeni giriş engellenir. En korumacı seçimdir.<br/><br/>• If ALL restrictions are active, block entry: Tüm aktif filtreler aynı anda risk göstermeden giriş engellenmez.<br/><br/>• Minimum N of M restrictions must be active: Belirli sayıda filtrenin birlikte tetiklenmesi gerekir.<br/><br/>• Restriction Score Threshold: Filtrelerin puanları toplamı eşik üzerinde olursa giriş engellenir.<br/><br/>• Warning Only: İşlem engellenmez; yalnızca uyarı kaydı oluşur.<br/><br/>Örnek: Spread çok yüksekse, sinyal ne kadar iyi görünürse görünsün “ANY” seçimi yeni pozisyonu engeller; açık pozisyonu kapatmaz.</td>
  </tr>
</table>

### ⓘ Volatility Filter

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`volatilityFilter`<br/>Volatility Filter</td>
    <td>Volatility Filter<br/><br/>Volatility (oynaklık) , fiyatın belirli sürede ne kadar geniş ve hızlı dalgalandığını ifade eder. Yüksek volatilite büyük fiyat hareketleri; düşük volatilite dar ve sakin hareketler anlamına gelir. Bu filtre, stratejinin uygun olmadığı oynaklık ortamlarında yeni pozisyon açmasını engellemek için kullanılır.<br/><br/>• Volatility too high: Piyasa normalden fazla dalgalanıyorsa filtre çalışır; stopların ani fiyat sıçramalarıyla bozulmasını önlemeye yardım eder.<br/><br/>• Volatility too low: Hareket yetersizse filtre çalışır; özellikle breakout stratejisinde işlem fırsatı zayıf olabilir.<br/><br/>• Volatility spike detected: Çok kısa sürede ani oynaklık artışı tespit edildiğinde tetiklenir.<br/><br/>• Volatility compression detected: Oynaklık sıkışması tespit edildiğinde tetiklenir; strateji türüne göre giriş engelleme amacı taşıyabilir.<br/><br/>• ATR above threshold: Average True Range (Ortalama Gerçek Aralık) belirlenen değerin üstüne çıktığında aktif olur.<br/><br/>• ATR below threshold: Average True Range (Ortalama Gerçek Aralık) belirlenen değerin altına indiğinde aktif olur.<br/><br/>Örnek: Ortalama 15 dakikalık fiyat aralığı %0.4 iken aniden %2.5 aralıklı mumlar oluşuyorsa “Volatility spike detected” yeni girişleri geçici olarak engelleyebilir.</td>
  </tr>
</table>

### ⓘ Date Blackout Windows

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`dateBlackoutWindows`<br/>Date Blackout Windows</td>
    <td>Date Blackout Windows<br/><br/>Bu panel, belirli takvim aralıklarında Strategynin yeni entry veya scaling davranışını sınırlamak için kullanılır. Her aralık başlangıç ve bitiş zamanı, Strategy/Data timezoneı ve seçilmiş aksiyonla birlikte değerlendirilir.<br/><br/>• Block New Entries + Block New Scaling: Açık pozisyonlar korunur; yeni giriş ve yeni layer engellenir.<br/><br/>• Block New Entries Only: Yeni ana giriş engellenir; Scaling/exit ayrı kuralına göre devam edebilir.<br/><br/>• Close Open Positions at Start Date: Aralık başladığında açık pozisyon için deterministic close intent üretilir.<br/><br/>• Allow Exit Only: Yalnız risk/exit işlemlerine izin verilir.<br/><br/>• Warning Only: Engine kararını engellemez; trace ve warning üretir.<br/><br/>Örnek: Önemli bir veri açıklaması veya bakım dönemi için 12:00–14:00 aralığı tanımlanır. “Block New Entries + Block New Scaling” seçilirse sistem bu aralıkta açık pozisyonu büyütmez ve yeni trade açmaz.</td>
  </tr>
</table>

<table>
  <tr>
    <th>IMPLEMENTATION ALIGNMENT NOTE<br/>The V18 UI contains this ⓘ action but the provided `infoTexts` map has no matching entry. This document supplies the finalized Production V1 panel text.</th>
  </tr>
</table>

### ⓘ Consecutive Loss Filter

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`consecutiveLossFilter`<br/>Consecutive Loss Filter</td>
    <td>Consecutive Loss Filter<br/><br/>Arka arkaya gelen zarar sayısı belirli bir sınıra ulaştığında yeni işlem açılmasını engellemek veya stratejiyi geçici olarak yavaşlatmak için kullanılır. Amaç, piyasanın o anda strateji için uygun olmayabileceğini kabul ederek aynı hatayı art arda büyütmemektir.<br/><br/>• Block New Entries: Açık pozisyonlara dokunmaz, yalnızca yeni girişleri engeller.<br/><br/>• Reduce New Position Size: Yeni sinyaller alınabilir fakat daha küçük pozisyonla denenir.<br/><br/>• Pause Strategy for N Candles: Belirlenen mum sayısı boyunca yeni giriş aranmaz.<br/><br/>• Disable Strategy for the Day: Günün kalanında yeni pozisyon açılmaz.<br/><br/>• Warning Only: İşlem davranışı değişmez; yalnızca kayıt/uyarı üretir.<br/><br/>Örnek: Max Consecutive Losses = 5 ve Action = Block New Entries ise, beşinci ardışık zarardan sonra yeni giriş sinyalleri uygulanmaz.</td>
  </tr>
</table>

### ⓘ Equity Curve Filter

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`equityCurveFilter`<br/>Equity Curve Filter</td>
    <td>Equity Curve Filter<br/><br/>Stratejinin kendi birikimli performans eğrisine bakarak yeni işlem açma davranışını sınırlar. Fiyat grafiğinin değil, stratejinin son dönemde iyi veya kötü çalışıp çalışmadığının filtresidir.<br/><br/>• Equity below moving average: Performans eğrisi kendi ortalamasının altındaysa strateji zayıf kabul edilir.<br/><br/>• Equity drawdown above threshold: Son zirveden düşüş belirlenen sınırı aşarsa filtre çalışır.<br/><br/>• Equity below previous peak by X%: Bir önceki tepeye göre kayıp ölçülür.<br/><br/>• Equity fails recovery condition: Strateji belirlenen iyileşme şartını sağlayana kadar filtre aktif kalır.<br/><br/>• Custom Equity Condition: Özel performans kuralı tanımlanır.<br/><br/>Örnek: Strateji equity curve&#x27;ü 50 işlem ortalamasının altına düştüğünde yeni girişler durdurulur; mevcut açık pozisyon ancak Exit veya Stop kuralı çalışırsa kapanır.</td>
  </tr>
</table>

### ⓘ Condition-Based Restriction

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`conditionBasedRestriction`<br/>Condition-Based Restriction</td>
    <td>Condition-Based Restriction<br/><br/>Önceden hazırlanmış bir Condition Package veya Trading Signal Package kullanarak yeni pozisyon girişini engeller ya da sınırlı hale getirir. Bu alan, sabit spread veya günlük zarar gibi hazır filtrelerin dışında özel bir yasaklayıcı durum tanımlamak içindir.<br/><br/>• Block New Entries: Koşul true olduğunda yeni pozisyon açılamaz.<br/><br/>• Reduce Position Size: İşlem tamamen yasaklanmaz, daha küçük büyüklükle açılır.<br/><br/>• Block Scaling Only: Ana pozisyon açık kalabilir fakat yeni layer eklenmez.<br/><br/>• Allow Exit Only: Yeni giriş ve kademe engellenir; yalnızca pozisyon azaltıcı kararlar uygulanır.<br/><br/>• Warning Only: Kural kaydedilir ancak emri engellemez.<br/><br/>Örnek: “Major News Window Active” isimli condition true olduğunda Action = Block New Entries seçilirse, entry sinyali gelse bile yeni pozisyon açılmaz. [V18 legacy prototype label; Production domain/API type değildir.]</td>
  </tr>
</table>

<table>
  <tr>
    <th>IMPLEMENTATION ALIGNMENT NOTE<br/>Canonical alignment: Condition Package list does not contain Trading Signal Package. Trading Signal is an external Mainboard Working Item, not a Package Library condition type.</th>
  </tr>
</table>

### ⓘ Stop + Exit

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`stopExitConflict`<br/>Stop + Exit Conflict</td>
    <td>Stop + Exit<br/><br/>Aynı mumda hem risk kaynaklı Stop sinyali hem de normal Exit sinyali oluşursa pozisyon kapatılır; ancak kapanışın hangi nedenle kaydedileceği ve yürütme önceliği bu menüyle belirlenir.<br/><br/>• Stop Has Priority: Kapanış risk koruması olarak kaydedilir; özellikle stop performans analizinde tutarlılık sağlar.<br/><br/>• Exit Has Priority: Normal çıkış sinyali esas alınır.<br/><br/>• Record Both Reasons: Tek kapanış uygulanır fakat raporda iki neden de saklanır.<br/><br/>• First Trigger Wins: İntrabar veri mevcutsa önce gerçekleşen tetikleyici kapanış nedeni olur.<br/><br/>Örnek: Long pozisyonda fiyat hem yüzde stop seviyesine dokunuyor hem de exit indikatörü ters sinyal üretiyorsa, Stop Has Priority seçimi kapanışı stop olarak raporlar.</td>
  </tr>
</table>

### ⓘ Multiple Stops

<table>
  <tr>
    <th>UI alanı / key</th>
    <th>Nihai panel metni</th>
  </tr>
  <tr>
    <td>`multipleStopsConflict`<br/>Multiple Stops Conflict</td>
    <td>Multiple Stops<br/><br/>Aynı pozisyon için birden fazla aktif stop kuralı aynı anda veya aynı mum içinde tetiklenebilir. Bu menü hangi stop seviyesinin uygulanacağını ve sonuçlarda hangi nedenin raporlanacağını belirler.<br/><br/>• First Trigger Wins: Fiyat akışında ilk tetiklenen stop uygulanır; ayrıntılı veri mevcutsa doğrudan okunabilir.<br/><br/>• Most Conservative Stop Wins: Pozisyonu daha erken kapatan ve daha az risk bırakan stop seçilir.<br/><br/>• Priority Order: Önceden tanımlanan stop sıralaması esas alınır.<br/><br/>• Record All / Execute Highest Priority: Bir stop uygulanır, fakat aynı anda çalışan diğer stoplar rapora eklenir.<br/><br/>Örnek: Aynı mumda Percentage Stop ve Logic-Based Stop Block tetiklenirse, Record All seçimi kapanışı tek kez uygular fakat analizde iki tetikleyiciyi de gösterir.</td>
  </tr>
</table>

# 7. Butonlar, Commandler ve State Davranışı

<table>
  <tr>
    <th>UI action</th>
    <th>Logical command / API</th>
    <th>Precondition</th>
    <th>Loading / success</th>
    <th>Error / retry / audit</th>
  </tr>
  <tr>
    <td>Add Strategy</td>
    <td>`POST /strategy-drafts` or local transient bootstrap with idempotency.</td>
    <td>Authenticated actor may create Strategy output.</td>
    <td>Creates draft identity or ephemeral draft. UI row/title only after canonical response if server-backed.</td>
    <td>403 create denied; duplicate retry returns same draft by idempotency. Audit only persistent creation policy event.</td>
  </tr>
  <tr>
    <td>Expand / collapse details</td>
    <td>No domain command. Optional user preference state.</td>
    <td>Row visible.</td>
    <td>Immediate UI; no revision/fingerprint state changes.</td>
    <td>No audit mandatory; no Ready Check invalidation.</td>
  </tr>
  <tr>
    <td>Edit field / draft patch</td>
    <td>`PATCH /strategy-drafts/{draft_id}` with `expected_row_version`, debounced/explicit commit.</td>
    <td>Edit policy; draft not locked/abandoned.</td>
    <td>UI shows local dirty state and patch pending; canonical draft returned.</td>
    <td>409 ROW_VERSION_CONFLICT returns latest + changed paths; user chooses reload, merge, fork or discard. Never last-write-wins.</td>
  </tr>
  <tr>
    <td>Adjust Indicator Settings</td>
    <td>`PATCH /strategy-drafts/{id}` parameter override branch, or staged local update.</td>
    <td>Package ref selected; `parameter_schema` resolved; caller can use package.</td>
    <td>Modal Apply validates typed values; Cancel no mutation; Reset uses selected package revision defaults.</td>
    <td>422 parameter path errors; package deleted/deprecated/changed -&gt; reference stale error and reselect/fork route.</td>
  </tr>
  <tr>
    <td>Add / remove dynamic block</td>
    <td>`PATCH` graph node add/remove.</td>
    <td>Draft editable.</td>
    <td>Add creates UUID and display order. Remove applies draft patch and recomputes counts.</td>
    <td>409 stale; 422 if remove would violate an already-active min count until rule reconfigured. Audit draft edit optional, revision audit on save mandatory.</td>
  </tr>
  <tr>
    <td>Save Strategy Revision</td>
    <td>`POST /strategies/{root_id}/revisions` or `POST /strategy-drafts/{id}/save` with idempotency + expected_head_revision_id.</td>
    <td>Edit policy; typed schema/refs valid; required fields/config active nodes valid.</td>
    <td>Action disabled on pending. Success creates immutable revision, dependency rows, config hash and response with new revision ID; Mainboard binding updated/pinned per canonical flow.</td>
    <td>422 validation blockers preserve draft; 409 conflict; 403; dependency lifecycle error. Audit `STRATEGY_REVISION_CREATED`, `STRATEGY_MAINBOARD_PIN_UPDATED`; Ready status becomes stale.</td>
  </tr>
  <tr>
    <td>Clear</td>
    <td>`POST /strategy-drafts/{id}/clear` or local clear before persistent draft.</td>
    <td>Draft exists; confirmation if dirty.</td>
    <td>Clears to default/blank state; no Root/Revision deletion.</td>
    <td>Cancel leaves draft untouched. Audit `DRAFT_CLEARED`/`DRAFT_DISCARDED` allowed. No Trash entry.</td>
  </tr>
  <tr>
    <td>Delete Strategy row (host action)</td>
    <td>Mainboard scope command `DELETE /work-objects/{root_id}`.</td>
    <td>Owner/Admin; root not committed input to queued/running manifest.</td>
    <td>Confirmation and pending. Success soft deletes Root + removes active board row.</td>
    <td>403/409 Active Run/Already Deleted. Trash/audit behavior described in §10; Restore Admin only.</td>
  </tr>
</table>

## 7.1 Save Strategy Revision — Atomik Backend Akışı

1. Server actor identity, Strategy Root ownership/access ve expected draft row_version doğrulanır.

2. Draft schema versionına göre parse edilir; unknown enum, malformed numeric, ignored disabled child veya illegal free-text rule reddedilir.

3. Market Data, Research/Funding, Indicator/Condition Package ve varsa external reference root + exact revision ile çözülür.

4. Instrument/timeframe/coverage/available-time, package contracts, condition compatibility, Direction Mode, sizing, formula AST, stop/scaling/restriction/conflict coherence ve execution data capabilities semantic olarak validate edilir.

5. Blocker varsa immutable revision üretilmez. Server machine code, title, path, retryability ve correlation ID içeren issue envelope döner. Warningler explicit revision metadata olarak saklanabilir.

6. Başarılı durumda canonical config serializasyonu ve config hash üretilir; immutable revision number artırılır; normalized reference rows, dependency graph ve audit transaction içinde yazılır.

7. Açık Mainboard Strategy item yeni revisiona pinlenir; composition hash değişir; önceki Ready Check report STALE olur. Client canonical revision, pinned item, dependency change summary ve readystate projectionunu hydrate eder.

<table>
  <tr>
    <th>POST /strategy-drafts/{draft_id}/save<br/>Idempotency-Key: 6b7e...<br/>If-Match: draft-row-version-17<br/><br/>response 201<br/>{<br/>  &quot;strategy_root_id&quot;: &quot;str_...&quot;,<br/>  &quot;strategy_revision_id&quot;: &quot;strrev_...&quot;,<br/>  &quot;revision_number&quot;: 4,<br/>  &quot;config_hash&quot;: &quot;sha256:...&quot;,<br/>  &quot;mainboard_working_item_id&quot;: &quot;mbi_...&quot;,<br/>  &quot;pinned_revision_id&quot;: &quot;strrev_...&quot;,<br/>  &quot;ready_state&quot;: &quot;STALE&quot;,<br/>  &quot;warnings&quot;: [],<br/>  &quot;correlation_id&quot;: &quot;corr_...&quot;<br/>}</th>
  </tr>
</table>

# 8. Kullanıcı Akışları, Validation, Hata ve Recovery

## 8.1 Başarılı Akış — Yeni Strategy Revision

1. Kullanıcı Mainboarddan Add Strategy seçer. V18de `STRATEGY N` paneli kapalı gelir; Productionda editable Strategy Draft başlar.

2. Kullanıcı Strategy Contexti doldurur: Name, Rationale Family, Market, Direction/Status. Data & Executionda approved Data Source, range, Initial Capital ve execution assumptions seçilir.

3. Entry Signal Graphi tamamlanır. Trigger Source seçimine bağlı Condition dependency çözülür; package settings yalnız strategy-local override olarak uygulanır.

4. Exit/Stop/Sizing/Scaling/Restrictions/Conflict kuralları aktif/inactive semantic boundarylere göre yapılandırılır. Disabled branchler engine inputu değildir.

5. Save Strategy Revision tıklanır. Server typed payloadı validate eder, refs pinler, immutable revision oluşturur ve active Mainboard itemini exact revisiona bağlar.

6. UI success toast: `Strategy revision saved and pinned to Mainboard. Backtest Ready Check is now stale.` gösterir. Kullanıcı Ready Check/RUN için Mainboard akışına döner.

## 8.2 Validation ve Dependency Akışları

<table>
  <tr>
    <th>Senaryo</th>
    <th>UI metni</th>
    <th>Server rule / recovery</th>
  </tr>
  <tr>
    <td>Missing required field</td>
    <td>`Complete all required fields marked with * before saving.`</td>
    <td>422 `REQUIRED_FIELD_MISSING` with JSON path. Scroll/focus first error; draft state preserved.</td>
  </tr>
  <tr>
    <td>Entry Trigger Source needs condition</td>
    <td>`Add at least one compatible Condition Package for the selected Trigger Source.`</td>
    <td>422 `TRIGGER_SOURCE_CONDITION_REQUIRED`; compatible package picker opens/filter refreshes.</td>
  </tr>
  <tr>
    <td>Selected condition incompatible</td>
    <td>`This Condition Package is not compatible with the selected Indicator Package revision.`</td>
    <td>422 `PACKAGE_CONTRACT_INCOMPATIBLE`; clear stale condition and choose a compatible revision. Server revalidates even if UI cached option.</td>
  </tr>
  <tr>
    <td>Data/market mismatch</td>
    <td>`Selected Data Source does not match the Strategy Market.`</td>
    <td>422 `MARKET_DATA_INSTRUMENT_MISMATCH`; select matching market/dataset. No implicit symbol mapping.</td>
  </tr>
  <tr>
    <td>Date range outside coverage</td>
    <td>`Backtest Range exceeds the selected dataset coverage.`</td>
    <td>422 `DATA_COVERAGE_MISSING`; adjust range or select another approved revision.</td>
  </tr>
  <tr>
    <td>Intrabar without capability</td>
    <td>`Intrabar execution requires compatible tick or declared intrabar data capability.`</td>
    <td>422/Warning depending conservative fallback policy. User selects data/timing or accepts declared conservative policy.</td>
  </tr>
  <tr>
    <td>Sizing formula invalid</td>
    <td>`Custom Formula could not be parsed as a permitted sizing expression.`</td>
    <td>422 `FORMULA_AST_INVALID`; highlight parser span; no code execution/retry until expression repaired.</td>
  </tr>
  <tr>
    <td>Mutually exclusive sizing</td>
    <td>`Select exactly one Position Sizing method.`</td>
    <td>422 `SIZING_METHOD_NOT_EXCLUSIVE`; UI normalizes radio state after canonical response.</td>
  </tr>
  <tr>
    <td>Scaling min count invalid</td>
    <td>`Logic-Based Rules Required to Scale cannot exceed the number of active rules.`</td>
    <td>422 `SCALING_RULE_COUNT_INVALID`; adjust count or add/remove complete rules.</td>
  </tr>
  <tr>
    <td>Conflict configuration incompatible</td>
    <td>`Hedge behavior is not available for the current Direction Mode and execution policy.`</td>
    <td>422 `CONFLICT_POLICY_INCOMPATIBLE`; select a supported resolution.</td>
  </tr>
  <tr>
    <td>Dependency soft-deleted</td>
    <td>`A referenced dependency is no longer active. Select another revision or ask an Admin to restore it.`</td>
    <td>409 `REFERENCE_NOT_ACTIVE`; historical revisions/runs unchanged. User reselects or Admin restore exists only Trash flow.</td>
  </tr>
  <tr>
    <td>Draft stale / concurrent edit</td>
    <td>`This draft changed in another session. Reload the latest version before saving.`</td>
    <td>409 `ROW_VERSION_CONFLICT`; show changed paths and offer Reload, Merge, Fork Draft, or Discard Local Changes.</td>
  </tr>
  <tr>
    <td>Permission denied</td>
    <td>`You do not have permission to save changes to this Strategy.`</td>
    <td>403 `EDIT_FORBIDDEN`; no mutation. User can clone an accessible source if use allowed.</td>
  </tr>
  <tr>
    <td>Save success but Ready stale</td>
    <td>`Strategy revision saved. Run Backtest Ready Check again before RUN.`</td>
    <td>Not error. Composition hash changed; old report only historical, cannot authorize new Run.</td>
  </tr>
</table>

## 8.3 Empty / Loading / Confirmation / Toast Content

<table>
  <tr>
    <th>State</th>
    <th>Final UI text</th>
    <th>Behavior</th>
  </tr>
  <tr>
    <td>New entry graph empty</td>
    <td>`Choose an Indicator Package and Trigger Source to define the first entry rule.`</td>
    <td>Shown in draft placeholder; Save blocked until a valid active entry graph exists.</td>
  </tr>
  <tr>
    <td>No compatible condition package</td>
    <td>`No compatible Condition Package is available for this Indicator revision. Create or publish a compatible Condition Package, or choose a different Trigger Source.`</td>
    <td>No unsafe global fallback; package creation is separate page/workflow.</td>
  </tr>
  <tr>
    <td>Settings loading</td>
    <td>`Loading parameter schema for the selected package revision…`</td>
    <td>Modal controls disabled until schema fetch resolves; close/cancel allowed.</td>
  </tr>
  <tr>
    <td>Settings no configurable fields</td>
    <td>`This package revision has no strategy-local parameters to adjust.`</td>
    <td>Read-only info state; no empty fake form.</td>
  </tr>
  <tr>
    <td>Save loading</td>
    <td>`Validating strategy configuration and creating immutable revision…`</td>
    <td>Disable Save/duplicate mutations; preserve Clear as disabled or confirm exit depending dirty/pending policy.</td>
  </tr>
  <tr>
    <td>Save success</td>
    <td>`Strategy revision saved and pinned to Mainboard.`</td>
    <td>Rehydrate canonical revision; Ready Check stale banner.</td>
  </tr>
  <tr>
    <td>Clear confirmation</td>
    <td>`Discard all unsaved changes in this Strategy draft? Saved revisions will not be deleted.`</td>
    <td>Primary: Discard changes. Secondary: Keep editing. Confirm creates clean draft/default state.</td>
  </tr>
  <tr>
    <td>Clear success</td>
    <td>`Unsaved draft changes were cleared.`</td>
    <td>No Trash/audit root deletion.</td>
  </tr>
  <tr>
    <td>Remove dynamic block confirmation</td>
    <td>`Remove this block and its unsaved configuration?`</td>
    <td>Required only when block contains non-default data; child refs removed from draft on confirm.</td>
  </tr>
  <tr>
    <td>Deprecated reference warning</td>
    <td>`This dependency is deprecated. The current revision can be inspected, but select an active replacement before creating a new backtest-ready revision.`</td>
    <td>Production policy does not silently repin to latest.</td>
  </tr>
  <tr>
    <td>Permission read-only</td>
    <td>`You can view this Strategy but cannot modify it. Create a new draft from this revision to continue.`</td>
    <td>Edit controls disabled for UX; server remains authoritative.</td>
  </tr>
</table>

## 8.4 Agent Tool / API Eşdeğeri

Agent, Strategy Details UI butonlarını browser automation ile tıklamak zorunda değildir. Agent Runtime aynı domain command/schema sözleşmesini Tool Gateway üzerinden çağırır; output owner = Agent olur; human session, Mainboard panelinin açık olması veya Lab Assistant sohbeti Agentın ana döngüsünün önkoşulu değildir.

<table>
  <tr>
    <th>Human UI capability</th>
    <th>Agent tool / domain command</th>
    <th>Policy / artifact expectation</th>
  </tr>
  <tr>
    <td>Add Strategy</td>
    <td>`strategy_draft.create`</td>
    <td>Agent may create Agent-owned draft; input includes objective/provenance/task ID.</td>
  </tr>
  <tr>
    <td>Select Package/Data ref</td>
    <td>`strategy_draft.set_reference` / `strategy_draft.patch`</td>
    <td>Tool accepts root+revision IDs; server checks use policy and lifecycle; selection rationale saved to task artifact when policy requires.</td>
  </tr>
  <tr>
    <td>Adjust settings</td>
    <td>`strategy_draft.patch_parameter_overrides`</td>
    <td>Schema-driven, typed, no free code execution.</td>
  </tr>
  <tr>
    <td>Add/remove blocks</td>
    <td>`strategy_draft.add_node`, `strategy_draft.remove_node`, `strategy_draft.reorder_node`</td>
    <td>Stable UUID; agent cannot invent unsupported node type; constraints/limits apply.</td>
  </tr>
  <tr>
    <td>Validate draft</td>
    <td>`strategy_draft.validate`</td>
    <td>Returns structured issues/warnings/compatible options; no immutable revision created.</td>
  </tr>
  <tr>
    <td>Save revision</td>
    <td>`strategy_draft.save` / `strategy_revision.create`</td>
    <td>Same semantic validation/idempotency/concurrency. Agent output is provenance-linked to agent_run_id/task_id/checkpoint.</td>
  </tr>
  <tr>
    <td>Pin revision to board</td>
    <td>`mainboard_item.pin_revision`</td>
    <td>Agent can pin only owned output or policy-allowed composition; composition ready becomes stale.</td>
  </tr>
  <tr>
    <td>Run follow-up</td>
    <td>`ready_check.request`, `backtest_run.request`</td>
    <td>Async job; Agent does not wait in UI; consumes result artifact and writes checkpoint/follow-up task.</td>
  </tr>
  <tr>
    <td>Explain decisions</td>
    <td>`strategy_decision_trace.query`</td>
    <td>Returns artifact/projection, not hidden chain-of-thought. Human UI can show sufficient diagnosis.</td>
  </tr>
</table>

# 9. Backend / Domain Model, Lifecycle, Audit ve Trash

## 9.1 Canonical Entity Relationship

<table>
  <tr>
    <th>StrategyRoot<br/>  ├─ StrategyDraft (mutable, row_version, may be incomplete)<br/>  ├─ StrategyRevision (immutable, revision_number, config_hash)<br/>  │    ├─ StrategyConfig JSON payload (typed)<br/>  │    ├─ StrategyReference rows (package/data/funding/external root+revision)<br/>  │    └─ ValidationSummary / warnings<br/>  └─ lifecycle + ownership + visibility metadata<br/><br/>MainboardWorkingItem(kind=strategy) -&gt; StrategyRoot + pinned StrategyRevision<br/>BacktestCompositionSnapshot -&gt; pinned Mainboard items + allocation ref<br/>BacktestRun Manifest -&gt; explicit StrategyRevision + exact dependencies<br/>BacktestResult -&gt; only succeeded BacktestRun output; immutable</th>
  </tr>
</table>

<table>
  <tr>
    <th>Entity</th>
    <th>Mutable?</th>
    <th>Key fields / behavior</th>
    <th>Lifecycle / audit</th>
  </tr>
  <tr>
    <td>StrategyDraft</td>
    <td>Yes.</td>
    <td>`draft_id`, root optional before first save, `row_version`, config editor tree, dirty state, validation projection.</td>
    <td>Draft may be incomplete. Concurrent patches use expected_head_revision_id. Clear/discard does not create Trash entry.</td>
  </tr>
  <tr>
    <td>StrategyRoot</td>
    <td>Limited lifecycle mutations.</td>
    <td>`strategy_root_id`, owner, visibility, created_by, current revision projection/status.</td>
    <td>Soft delete moves root from active lists and creates Trash record; root not permanently deleted except Admin Trash purge policy.</td>
  </tr>
  <tr>
    <td>StrategyRevision</td>
    <td>No.</td>
    <td>`strategy_revision_id`, revision_number, schema_version, config_hash, canonical config, dependency refs.</td>
    <td>Created by Save transaction. No update endpoint; clone-to-draft creates new mutable work path.</td>
  </tr>
  <tr>
    <td>StrategyReference</td>
    <td>No for revision.</td>
    <td>`ref_type`, root_id, revision_id, purpose/path, active flag resolved at save.</td>
    <td>Supports dependency graph, package usage, delete/restore checks and reproducible manifest.</td>
  </tr>
  <tr>
    <td>MainboardWorkingItem</td>
    <td>Yes with concurrency.</td>
    <td>`composition_item_id`, root_id, pinned_revision_id, position_index, is_enabled.</td>
    <td>Revision change/pin creates composition change audit and Ready Check stale status.</td>
  </tr>
  <tr>
    <td>Decision/validation artifact</td>
    <td>Append-only.</td>
    <td>Issue code/path, decision trace, source refs, timestamp, correlation/job/run IDs.</td>
    <td>Supports troubleshooting/Agent/provenance; does not mutate historical revision.</td>
  </tr>
  <tr>
    <td>BacktestRun / Result</td>
    <td>Run mutable through lifecycle; Result immutable.</td>
    <td>Manifest pins revisions.</td>
    <td>Only succeeded Run produces Result. Failed/cancelled normal Result does not exist.</td>
  </tr>
</table>

## 9.2 Canonical StrategyConfig Shape

<table>
  <tr>
    <th>StrategyConfig v1<br/>{<br/>  identity: { display_name, rationale_family_id, instrument_id, direction_mode, status },<br/>  data_execution: { market_dataset_ref, backtest_range, initial_capital, entry_execution, exit_execution, order, costs, intrabar, funding },<br/>  entry_logic: { signal_block: { rule, min_supporting_count, indicator_blocks[] } },<br/>  exit_logic: { enabled, applies_to_position, action, partial_close_policy, signal_block },<br/>  protection_stop: { mode, logic_blocks[], percentage, trailing, absolute },<br/>  sizing: { method, selected_branch, max_single_position, max_total_exposure, leverage, signal_strength_adjustment },<br/>  scaling: { enabled, timeframe_mode, custom_sequence?, method?, limits? },<br/>  restrictions: { combination, filters[] },<br/>  conflicts: { long_short, entry_exit, entry_restriction, stop_exit, multiple_stops, ... },<br/>  provenance: { source_package_ref?, created_from_draft_id, schema_version }<br/>}</th>
  </tr>
</table>

<table>
  <tr>
    <th>CANONICAL RULE — REFERENCES AND IMMUTABILITY<br/>Her Package/Dataset/Research/Funding/External reference root identity ve exact revision identity taşır. “Latest/current”, dropdown labelı veya browser cachei engine inputu değildir. Yeni package/dataset sürümü çıktığında mevcut Strategy Revision otomatik değişmez; user/Agent yeni ref seçer ve yeni Strategy Revision kaydeder.</th>
  </tr>
</table>

## 9.3 Deterministic Engine Evaluation Order

1. Run manifestinden Strategy Revision, Market Data revision, Research/Funding revisions, Package revisions, execution policy ve resolved capital alınır.

2. Her decision intervalde yalnız `available_time`ı geçmiş Market/Research support verisi hazırlanır.

3. Restrictions/filters evaluatorları çalışır; entry/scaling eligibility, exit-only ve close-position flags üretilir.

4. Açık positions için active Stop Rules, trailing state, Exit Logic ve scaling cooldown/limits değerlendirilir; action candidate listesi kurulur.

5. Entry/Exit Signal Block graphs package output contractsıyla değerlendirilir; closed-bar alignment, validity windows ve required/supporting kombinasyonları çözülür.

6. Candidates Direction Mode, position state, exposure, sizing, allocation cap, execution constraints ve Conflict Rules ile resolve edilir.

7. Legal actions selected fill modeline göre order/simulated fill eventine dönüşür; commission/spread/slippage/funding uygulanır.

8. Ledger, position/equity/risk/trailing/scaling counters ve diagnostics güncellenir; meaningful decision için reason code, source revision, trigger timestamp, resolved priority ve calculated size artifacte yazılır.

## 9.4 Audit Events

<table>
  <tr>
    <th>Event</th>
    <th>When</th>
    <th>Minimum audit metadata</th>
  </tr>
  <tr>
    <td>STRATEGY_DRAFT_CREATED</td>
    <td>Persisted draft bootstrap.</td>
    <td>actor principal, draft/root IDs, origin Mainboard/action, correlation ID.</td>
  </tr>
  <tr>
    <td>STRATEGY_DRAFT_PATCHED</td>
    <td>Canonical draft patch accepted.</td>
    <td>changed paths summary, previous/new row_version, actor, correlation.</td>
  </tr>
  <tr>
    <td>STRATEGY_DRAFT_CLEARED / DISCARDED</td>
    <td>Clear confirmed.</td>
    <td>draft ID, actor, reason/confirmation, no Trash entry.</td>
  </tr>
  <tr>
    <td>STRATEGY_REVISION_CREATED</td>
    <td>Save transaction succeeds.</td>
    <td>root/revision IDs, revision number, config hash, dependency refs, warnings, actor, correlation.</td>
  </tr>
  <tr>
    <td>MAINBOARD_ITEM_REVISION_PINNED</td>
    <td>Saved revision becomes active board pin.</td>
    <td>item ID, old/new revision, composition hash before/after, actor.</td>
  </tr>
  <tr>
    <td>STRATEGY_VALIDATION_FAILED</td>
    <td>Save/validate blocked; policy can record.</td>
    <td>machine issue codes/paths, actor, correlation; never store secrets/raw code improperly.</td>
  </tr>
  <tr>
    <td>STRATEGY_SOFT_DELETED</td>
    <td>Root delete succeeds.</td>
    <td>root ID, deleted by, deletion reason, source location, Trash record ID.</td>
  </tr>
  <tr>
    <td>STRATEGY_RESTORED / PERMANENTLY_DELETED</td>
    <td>Admin Trash workflow.</td>
    <td>Admin actor, root/trash IDs, restore conflict or purge outcome.</td>
  </tr>
</table>

## 9.5 Soft Delete / Trash / Restore Effects

• Soft delete normal Strategy root delete actionıdır. Aktif listelerden çıkar; Mainboard row projection kaldırılır; Trash entry/audit/outbox event oluşur. Historical immutable Strategy Revision, prior Composition Snapshot, Backtest Run Manifest ve Result provenance üzerindeki kimlik bağlantısı silinmez.

• Delete block: Strategy root active queued/running Backtest Run manifesti tarafından input olarak kullanılıyorsa delete command 409 `OBJECT_IN_ACTIVE_RUN` ile reddedilir. Çalışan runın input manifesti sonradan değiştirilemez.

• Restore yalnız Admin tarafından Trash üzerinden yapılabilir. Restore rootu active listelere otomatik “latest” pin olarak sokmaz; restore sonrası kullanmak için explicit new pin/revision selection gerekir. Historical runs değişmez.

• Permanent delete yalnız Admin Trash actionıdır. Audit/provenance retention policy doğrudan physical delete davranışını belirler; active/historical references varsa purge policy blocker/retention rule uygular.

• Clear Strategy soft delete değildir. Yalnız unsaved editor draftını temizler; Trash record oluşturmaz; saved revisionları ve historical resultsı etkilemez.

# 10. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Notes

<table>
  <tr>
    <th>Tema</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>New Strategy</td>
    <td>DOM row created and local counter increments; no persisted identity.</td>
    <td>Draft/Root/Revision lifecycle as described; initial DOM not authority.</td>
    <td>Transient UI draft allowed but cannot enter Ready Check/RUN until persisted revision exists.</td>
  </tr>
  <tr>
    <td>Save button</td>
    <td>`Save as Strategy Package` changes local title/state.</td>
    <td>Atomic Save Strategy Revision creates immutable revision/config hash/reference rows/audit and pins item per policy.</td>
    <td>Rename button to Save Strategy Revision. Do not turn Strategy working item into Package Library item by label.</td>
  </tr>
  <tr>
    <td>Package selection</td>
    <td>Static demo names in selects; V18 condition/restriction text includes Trading Signal package wording.</td>
    <td>Server resolves root+revision/access/lifecycle/schema compatibility.</td>
    <td>Remove Trading Signal Package option: Trading Signal is external working item, not Condition Package. [V18 legacy prototype label; Production domain/API type değildir.]</td>
  </tr>
  <tr>
    <td>Created By</td>
    <td>Reads demo currentUser/guest.</td>
    <td>Server principal context, immutable created_by + owner, auditable updated_by.</td>
    <td>Guest is UI demo only, never persisted as authenticated user owner.</td>
  </tr>
  <tr>
    <td>Required star</td>
    <td>HTML `data-required`/red star on selected fields.</td>
    <td>Server validates presence/type/availability/cross-field constraints.</td>
    <td>Trigger source conditional condition requirement supersedes simplistic V18 first-condition required flag.</td>
  </tr>
  <tr>
    <td>Disabled cards</td>
    <td>CSS opacity/pointer-events; some prior values can remain in DOM.</td>
    <td>`enabled=false` excludes child from active config/evaluator/manifest.</td>
    <td>Preserve inactive draft values optionally; never silently execute them.</td>
  </tr>
  <tr>
    <td>Custom Formula</td>
    <td>Free input visible.</td>
    <td>Restricted versioned DSL/AST with parsing/type/dependency validation.</td>
    <td>No arbitrary code/runtime evaluation.</td>
  </tr>
  <tr>
    <td>Dynamic blocks</td>
    <td>DOM add/remove + displayed renumber.</td>
    <td>Stable UUID and display order separate; server graph validation.</td>
    <td>Remove cleans refs; no index-based identity.</td>
  </tr>
  <tr>
    <td>Intrabar/tick</td>
    <td>V18 dropdown.</td>
    <td>Data capability + declared conservative fallback evaluation.</td>
    <td>No false intrabar knowledge from OHLCV.</td>
  </tr>
  <tr>
    <td>Backtest readiness</td>
    <td>Prototype status dropdown and save do not create real report.</td>
    <td>Ready Check separate immutable report tied to current Mainboard composition hash.</td>
    <td>Status “Backtest Ready” does not authorize RUN.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>V18 UI supports generic interface interaction.</td>
    <td>Agent Tool Gateway invokes same domain services asynchronously.</td>
    <td>No browser/session/chat dependency for continuous Agent research.</td>
  </tr>
  <tr>
    <td>Delete/Clear</td>
    <td>V18 row × sends demo Trash; Clear resets DOM.</td>
    <td>Soft delete root has Trash/audit; Clear only draft.</td>
    <td>Never conflate Clear with deletion or restore/purge.</td>
  </tr>
</table>

# 11. Kodcu AI için Implementation Rules

1. Strategy Detailsi salt HTML form olarak değil, typed canonical StrategyConfig üreten **versioned behavior compiler** olarak uygula.

2. Draft mutable; Strategy Revision immutabledır. Immutable revision için PATCH/UPDATE endpointi yazma; clone-to-draft kullan.

3. Her dependencyyi display name yerine `root_id + revision_id` ile taşı. “Latest” indirgeme yapma.

4. Required star, client-side disable veya dropdown filter server-side validationın yerine geçmez.

5. Selection labelını engine business logic olarak yorumlama; fixed enum/typed payloada dönüştür.

6. Package parameter settings shared Package Revisionı mutate etmez; Strategy-local override/snapshot olarak kaydedilir.

7. Trigger Source = Native Trigger iken condition zorunlu yapma; diğer iki condition-bearing source için en az bir compatible active condition iste.

8. Condition package listesi UI kolaylığı için filtrelenebilir; Save sırasında server tüm input/output compatibilityyi yeniden doğrular.

9. Entry block, exit block, stop block, scaling rule, dynamic restriction ve blackout range için immutable UUID + mutable display order kullan.

10. Remove action alt node/dependency reflerini draft graphından temizler; numbered UI positionunu persistent ID sanma.

11. Disabled veya hidden feature altındaki değerleri engine evaluatoruna, active dependency manifestine veya run outputuna sızdırma.

12. Position Sizing methodini semantik radio group yap: exactly one active method. Risk Per Trade stop/risk model olmadan size hesaplamaz.

13. Custom Formula serbest code çalıştırmaz; AST/DSL parse, type check, allowlist function ve dependency resolver zorunludur.

14. Scaling yalnız same-direction layer ekler. Opposite signal transitionını Conflict Rulesa yönlendir.

15. Conflict dropdownlarını executable event-resolution policy enumları olarak persist et; same-candle ambiguityyi UI orderına bırakma.

16. OHLCV verisi tick path bilgisi değildir. Intrabar, stop/limit fill ve same-candle actions için explicit data capability/conservative policy zorunludur.

17. Save commandinde idempotency key, expected draft row_version, correlation ID, atomic transaction ve canonical rehydrate uygula.

18. 409 stale conflictte last-write-wins yapma. Changed paths + latest draft ile Reload/Merge/Fork kararını kullanıcıya/Agent toola ver.

19. Strategy Save successini Ready Check PASS sayma. Mainboard composition hash değişince prior Ready Check reportu STALE olur.

20. Agent, UI button tıklamak yerine same command/domain service contractını Tool Gateway üzerinden çağırır; Agent outputu provenance metadata taşır.

21. Soft delete historical manifest/result provenanceyi bozmaz. Restore/purge yalnız Admin Trash policy üzerinden çalışır.

22. Future Dev/Live Trade davranışını Strategy Detailsin active Production V1 inputu gibi ekleme; explicit capability activation olmadan gerçek broker order üretme.

# 12. Acceptance Tests

<table>
  <tr>
    <th>ID</th>
    <th>Doğrulanabilir senaryo</th>
  </tr>
  <tr>
    <td>AT-01 Add Strategy draft</td>
    <td>Authenticated User Add Strategy seçtiğinde editable draft açılır; unsaved draft Ready Check/RUN inputuna giremez.</td>
  </tr>
  <tr>
    <td>AT-02 First save creates immutable revision</td>
    <td>Valid draft Save edildiğinde server new revision_number/config_hash/ref rows üretir; original revision değişmez.</td>
  </tr>
  <tr>
    <td>AT-03 Required fields</td>
    <td>Name, Rationale Family, Market, Data Source, range, Initial Capital, Entry/Exit Execution boşken save 422 blocker döner; UI star alone is insufficient.</td>
  </tr>
  <tr>
    <td>AT-04 Market/data binding</td>
    <td>EURUSD Market + BTCUSDT dataset payloadı server tarafından `MARKET_DATA_INSTRUMENT_MISMATCH` ile reddedilir.</td>
  </tr>
  <tr>
    <td>AT-05 Trigger source conditional requirement</td>
    <td>Native Trigger + zero condition valid olabilir; Native+Condition/Output+Condition + zero active compatible condition 422 üretir.</td>
  </tr>
  <tr>
    <td>AT-06 Condition compatibility</td>
    <td>UI cache manipulated to send incompatible condition revision; Save server-side compatibility blocker üretir.</td>
  </tr>
  <tr>
    <td>AT-07 Dynamic identity</td>
    <td>Two entry blocks created, first removed. Remaining block display number 1 olur ancak original UUIDsi korunur.</td>
  </tr>
  <tr>
    <td>AT-08 Direction coherence</td>
    <td>Long Only Strategy içinde short-only indicator/hedge config Save blocker üretir veya canonical normalized policy requires explicit user correction.</td>
  </tr>
  <tr>
    <td>AT-09 Limit branch</td>
    <td>Market Order seçiliyken limit subtree engine payloadında yoktur. Limit Order seçilince mandatory limit policy fields validate edilir.</td>
  </tr>
  <tr>
    <td>AT-10 Intrabar capability</td>
    <td>Intrabar Touch/Tick Require tick-compatible approved data olmadan blocker veya declared conservative warning policy verir; silent synthetic tick yoktur.</td>
  </tr>
  <tr>
    <td>AT-11 Stop disabled state</td>
    <td>Disabled Percentage/Trailing/Absolute/Logic rule active evaluator/manifest dependenciese dahil edilmez. Re-enable old valueyi revalidates.</td>
  </tr>
  <tr>
    <td>AT-12 Sizing exclusivity</td>
    <td>Client iki sizing checkboxı active gönderirse 422 `SIZING_METHOD_NOT_EXCLUSIVE` döner.</td>
  </tr>
  <tr>
    <td>AT-13 Custom formula safe</td>
    <td>Free Python/JS/Pine expression rejected; valid DSL AST stores schema/version/dependency trace.</td>
  </tr>
  <tr>
    <td>AT-14 Scaling state</td>
    <td>No scaling method selected -&gt; `scaling.enabled=false`, add-size/limit drafts have zero engine effect. Exactly one method activates relevant fields.</td>
  </tr>
  <tr>
    <td>AT-15 Same direction scaling</td>
    <td>Opposite signal Scaling Logic üzerinden layer üretmez; Conflict Rules resolution patha gider.</td>
  </tr>
  <tr>
    <td>AT-16 Restriction disabled state</td>
    <td>Unchecked Volatility/Spread/etc. filter rule does not block, resize or warn during engine evaluation.</td>
  </tr>
  <tr>
    <td>AT-17 Date blackout validation</td>
    <td>Enabled blackout with missing/end-before-start/overlap invalid range returns issues at exact row path; disabled blank rows do not block save.</td>
  </tr>
  <tr>
    <td>AT-18 Conflict determinism</td>
    <td>Same candle Stop + Exit / Multiple Stop configuration results are stable across reruns with same data and engine policy version.</td>
  </tr>
  <tr>
    <td>AT-19 Optimistic concurrency</td>
    <td>Two editors patch same draft. Second stale patch gets 409 + current version/changed paths; no last-write-wins overwrite.</td>
  </tr>
  <tr>
    <td>AT-20 Save -&gt; Ready stale</td>
    <td>Successful revision pin changes Mainboard composition hash; prior Ready report cannot authorize RUN.</td>
  </tr>
  <tr>
    <td>AT-21 Agent parity</td>
    <td>Agent Tool Gateway creates/validates/saves Strategy revision using same schema, policy, idempotency and audit as UI; no browser needed.</td>
  </tr>
  <tr>
    <td>AT-22 Authorization</td>
    <td>Supervisor/User cannot mutate another owner’s normal Strategy Root; Admin can; Rationale Family exception does not grant Strategy edit.</td>
  </tr>
  <tr>
    <td>AT-23 Clear behavior</td>
    <td>Clear confirms dirty draft, removes unsaved config, creates no Trash record, and does not delete a prior immutable revision.</td>
  </tr>
  <tr>
    <td>AT-24 Soft delete integrity</td>
    <td>Delete Strategy soft deletes Root/row after active-run guard; historical Run Manifest/Result continues to resolve immutable provenance; Trash restore Admin-only.</td>
  </tr>
  <tr>
    <td>AT-25 Info content</td>
    <td>Every rendered ⓘ key has a title/body matching this catalog; no popover adds hidden config or silently changes a field.</td>
  </tr>
</table>

# 13. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç / zorunlu doğrulama</th>
  </tr>
  <tr>
    <td>Master authority</td>
    <td>Modül 10 root/draft/revision, typed payload, disabled semantic boundary, sizing exclusivity, formula DSL, execution-data capability, engine order, Agent UI independence, concurrency ve save atomicity uygulanmıştır.</td>
  </tr>
  <tr>
    <td>V18/Production separation</td>
    <td>V18 local DOM/guest/package wording/demo row state Production persistence/authorization/lifecycle doğrusu olarak taşınmamıştır.</td>
  </tr>
  <tr>
    <td>Terminology</td>
    <td>Strategy = Mainboard Working Item; Trading Signal/Trade Log = external Working Item; Indicator/Condition/Embedded System = Package types. Trading Signal/Trade Log Condition Package gibi listelenmez.</td>
  </tr>
  <tr>
    <td>Requiredness</td>
    <td>Her required/conditional required field UI star, server validation, Ready Check and Agent schema semanticsinde açık tanımlanmıştır.</td>
  </tr>
  <tr>
    <td>Special disabled state</td>
    <td>Sections 5–8 içindeki stop/sizing/scaling/restriction disabled state payload/engine/preserve-reset/re-enable etkileri açıkça belirtilmiştir.</td>
  </tr>
  <tr>
    <td>Run / Result</td>
    <td>Save != Ready. Ready Check != Run. Only succeeded Backtest Run immutable Result üretir; failed/cancelled normal Result oluşturmaz.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Agent continuous backend system actor; UI actionların command/tool paritysi sağlanır; Lab Assistant/normal chat Agent taskına zorunlu bağımlılık getirmez.</td>
  </tr>
  <tr>
    <td>Trash</td>
    <td>Normal delete soft delete/audit/Trash record; restore/permanent delete Admin-only. Clear Draft deletion değildir.</td>
  </tr>
  <tr>
    <td>Future Dev boundary</td>
    <td>Live Trade/future capability active Production V1 Strategy Details behaviorı gibi eklenmemiştir.</td>
  </tr>
  <tr>
    <td>Delivery boundary</td>
    <td>Bu doküman yalnız Add Strategy / Strategy Details sayfasını kapsamaktadır; bağımsız sayfa dokümanlarını içeri almamıştır.</td>
  </tr>
</table>
