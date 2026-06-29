---
title: "Entropia V18 — Trade Log Page Documentation v1.1"
page_number: 5
document_type: "Page implementation specification"
source_document: "Entropia_V18_Trade_Log_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Trade Log Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | PAGE DOCUMENTATION 5/22 | TRADE LOG
> **Original DOCX footer:** Canonical page documentation | Production V1 alignment |

ENTROPIA V18

TRADE LOG

Sayfa Dokümantasyonu 5/22 | External Working Object, source-file import, canonical trade-record revision ve Mainboard binding sözleşmesi

<table>
  <tr>
    <th>Kapsam sınırı: Bu belge yalnız Trade Log çalışma nesnesinin Mainboard satırı ve ayrıntı panelini kapsar. Add Outsource Signal menü seçicisi, Trading Signal, Package Library, Backtest Ready Check, Portfolio / Equity Allocation, RUN / Results, Trash ve Panel ayrı sayfaların kapsamıdır; burada yalnız bu sayfanın doğrudan bağımlılığı olarak anılır.</th>
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
    <td>Entropia V18 | Page Documentation 5/22 | Trade Log | v1.1</td>
  </tr>
  <tr>
    <td>Belge amacı</td>
    <td>V18 prototipinde Mainboard altında açılan Trade Log ayrıntı panelinin görünür davranışını; Production V1 external working object, import, revision, Mainboard pin, validation, lifecycle ve Agent parity sözleşmesine indirmek.</td>
  </tr>
  <tr>
    <td>Kapsam</td>
    <td>Trade Log row, expand/collapse, identity/source fields, TXT/CSV source file, import format guidance, panel actions, save/revision/pin, export artifact, clear, delete, error/recovery, domain persistence ve audit bağlantısı.</td>
  </tr>
  <tr>
    <td>Kapsam dışı</td>
    <td>Add Outsource Signal chooser; Trading Signal event model; Strategy Details; Market Data yönetimi; Portfolio Allocation UI; Ready Check ekranı; Run/Result ekranı; Trash UI; Package Library ekranı.</td>
  </tr>
  <tr>
    <td>Öncelik sırası</td>
    <td>1) Master Technical Reference v1.0, 2) V18 ana HTML, 3) Handoff v1.1, 4) 2.3 Position Entry Logic anlatım derinliği örneği.</td>
  </tr>
</table>

## 0.1 Source Traceability Map

<table>
  <tr>
    <th>Konu</th>
    <th>Master Technical Reference</th>
    <th>V18 HTML gözlemi</th>
    <th>Çapraz bağımlılık / karar</th>
  </tr>
  <tr>
    <td>External object sınırı</td>
    <td>Modül 2 §4.3; Modül 7 §2.2; Modül 9 §4.3 ve CR-01</td>
    <td>Add Outsource Signal &gt; Trade Log; legacy &quot;TRADE LOG PACKAGE&quot; labelı</td>
    <td>Trade Log Package Library package kind değildir. Root object_kind = trade_log; Mainboard item_kind = trade_log. [V18 legacy prototype label; Production domain/API type değildir.]</td>
  </tr>
  <tr>
    <td>Mainboard / pin / snapshot</td>
    <td>Modül 9 §1.2, §5.1-5.4, §7, §10-11</td>
    <td>Satır DOMda eklenir; local counter/backtestReady state kullanılır</td>
    <td>Persisted root + immutable revision + explicit pinned_revision_id; DOM veya local boolean authoritative değildir.</td>
  </tr>
  <tr>
    <td>Import ve validation</td>
    <td>Modül 9 §4.3; Modül 2 §6; Modül 3 lifecycle</td>
    <td>TXT/CSV only; required columns and separators are shown; file input only marks local state</td>
    <td>Source asset, import/validation job, parse report, skipped row report and canonical trade-record revision server-side üretilir.</td>
  </tr>
  <tr>
    <td>Authorization / owner / Agent</td>
    <td>Modül 1 §§5-10; Modül 0 §§5-6</td>
    <td>Prototype role helpers ve client visibility</td>
    <td>Server policy: Admin override; User/Supervisor/Agent own-object mutation rule; Agent UI login bağımsız system actor.</td>
  </tr>
  <tr>
    <td>Trash / history</td>
    <td>Modül 3; Modül 9 §5.3</td>
    <td>× rowu client arrayden kaldırır, local Trash helper çağırır</td>
    <td>Soft delete + Trash entry + audit + outbox transaction; completed run provenance remains readable; restore/purge Admin only.</td>
  </tr>
  <tr>
    <td>API/concurrency</td>
    <td>Modül 2 §6.3; Modül 9 §10-11; Modül 19 API principles</td>
    <td>V18 form commands are mostly local/unbound</td>
    <td>Every mutation carries idempotency key and expected head/row version; stale writes return structured conflict.</td>
  </tr>
</table>

## 0.2 Rule Provenance Register

<table>
  <tr>
    <th>Etiket</th>
    <th>Bu belgede kullanım</th>
  </tr>
  <tr>
    <td>Canonical Rule</td>
    <td>Master içinde açıkça kilitli Production V1 davranışıdır. Örnek: Trade Log, historical entry/exit records taşıyan external working objecttir; package kind değildir.</td>
  </tr>
  <tr>
    <td>Derived Rule</td>
    <td>Canonical kararın zorunlu sonucu. Örnek: Backtest manifest yalnız pinned Trade Log revisionını taşır; &quot;latest&quot; revision sessizce kullanılamaz.</td>
  </tr>
  <tr>
    <td>V18 Interface Observation</td>
    <td>Prototipte görünen label/default/local interaction. Örnek: Initial Capital başlangıç değeri 10000 ve file input yalnız dataFileLoaded stateini işaretler.</td>
  </tr>
  <tr>
    <td>Implementation Decision - Non-Canonical Gap Resolution</td>
    <td>Master exact UI/API ayrıntısını kilitlemediğinde bu belgede seçilen yön. Her karar gerekçe ve etki ile ayrıca kayıtlıdır.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Canonical Kavramlar

Trade Log, geçmişte gerçekleşmiş veya dış sağlayıcıdan alınmış giriş/çıkış kayıtlarını temsil eden external working objecttir. Canlı sinyal üretmez; geçmiş işlem akışını değerlendirme, strateji evrenine veri olarak katma veya ayrıştırılmış geçmiş sonuçlara referans olma amacı taşır. Bu yüzden Trading Signal ile aynı dış kaynak ailesinde bulunsa da onun event/available-time modelinin yerine geçmez.

Trade Log satırı Mainboard içinde görünür; ancak Mainboard yalnızca bu nesnenin sırası, enabled durumu ve belirli bir revisiona olan pinini taşır. Trade Logun kaynak dosyası, normalize edilmiş trade kayıtları, kaynak/provenance bilgisi ve validation kanıtı Trade Log root/revision katmanında yaşar. Mainboard satırı bunları kopyalamaz.

## 1.1 İlk geçen kavramlar

<table>
  <tr>
    <th>Kavram</th>
    <th>Canonical kısa tanım</th>
    <th>Bu sayfadaki uygulama sonucu</th>
  </tr>
  <tr>
    <td>Trade Log</td>
    <td>Entry/exit kayıtlarından oluşan historical trade data external working objecti.</td>
    <td>object_kind = trade_log; PackageKind enumuna eklenmez.</td>
  </tr>
  <tr>
    <td>Trade Log Root</td>
    <td>Kullanıcı adı değişse de değişmeyen kalıcı iş nesnesi kimliği.</td>
    <td>UUIDv7 root id; ownership, lifecycle ve current revision pointerı taşır.</td>
  </tr>
  <tr>
    <td>Trade Log Revision</td>
    <td>Bir source asset, mapping, canonical records ve validation evidence içeren immutable sürüm.</td>
    <td>İçerik değişikliği yeni revision üretir; eski revision update edilmez.</td>
  </tr>
  <tr>
    <td>Source Asset</td>
    <td>Kullanıcının yüklediği orijinal TXT/CSV dosyasının immutable saklanan kanıt kopyası.</td>
    <td>raw asset hash saklanır; parse işlemi source dosyayı değiştirmez.</td>
  </tr>
  <tr>
    <td>Canonical Trade Record Batch</td>
    <td>Kaynak dosyadan normalize edilmiş, mapping ve timezone bilgisiyle ilişkili entry/exit kayıt seti.</td>
    <td>Ready Check ve historik analiz revision referansı üzerinden bu batchi bulur.</td>
  </tr>
  <tr>
    <td>Mainboard Item</td>
    <td>Trade Log rootuna ve exact revisiona bağlı satır kaydı.</td>
    <td>item_kind = trade_log; pinned_revision_id zorunludur.</td>
  </tr>
  <tr>
    <td>Pinned Revision</td>
    <td>Mainboard ve runın kullandığı kesin revision kimliği.</td>
    <td>Yeni revision oluştuğunda otomatik geçmez; açık pin gerekir.</td>
  </tr>
  <tr>
    <td>Import Job</td>
    <td>Dosya parse/normalize/validate eden durable worker işi.</td>
    <td>Refresh, logout veya tab close ile iptal olmaz.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Canonical Rule: Trading Signal ve Trade Log, Package Librarydeki reusable package türleri değildir. Trade Logun belirli bir kaynak dosyası ve historical record bağlamı vardır; yeniden kullanılabilir mantık packagei gibi package_type / package_kind değerine dönüştürülemez.</th>
  </tr>
</table>

## 1.2 Bu sayfanın görevi ve yapmadığı iş

- Yapar: Bir external trade-history kaynağını tanımlar; TXT/CSV assetini kabul eder; mapping/validation kanıtı üretir; immutable Trade Log revisionı kaydeder; gerektiğinde Mainboard itemine pinler.

- Yapar: Kayıtların zaman, fiyat, yön, market scope, capital ve price fallback bağlamını açıklaştırır; Ready Checke doğru input sağlar.

- Yapmaz: Yeni long/short sinyali üretmez, canlı emir göndermez, Strategy Details entry/exit logic oluşturmaz, Market Data registrysini yönetmez veya Backtest Result üretmez.

- Yapmaz: Bir Trade Logu "Trade Log Package" adıyla Package Library typeına dönüştürmez. V18 legacy labelı Productiona taşınmaz.

# 2. Erişim, Görünürlük, Ownership ve Server-Side Policy

<table>
  <tr>
    <th>Actor</th>
    <th>List / view / use</th>
    <th>Create / import</th>
    <th>Edit / save revision</th>
    <th>Delete</th>
    <th>Trash / restore / purge</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Protected Trade Log detail ve source asset erişimi yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Own + explicitly shared/published Trade Logları görür/kullanır.</td>
    <td>Kendi owner olduğu draft/root oluşturur.</td>
    <td>Yalnız own root üzerinde.</td>
    <td>Yalnız own root üzerinde soft delete.</td>
    <td>Yok; Admin only.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Erişilebilir working contenti görür/kullanır.</td>
    <td>Kendi owner olduğu root oluşturur.</td>
    <td>Yalnız own root üzerinde.</td>
    <td>Yalnız own root üzerinde.</td>
    <td>Yok; Admin only.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm uygun root/revision/source reportlarını görür/kullanır.</td>
    <td>Her bağlamda oluşturabilir.</td>
    <td>Tüm uygun rootları yönetebilir.</td>
    <td>Tüm normal rootları soft delete edebilir.</td>
    <td>View, restore ve purge yalnız Admin.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Policy ile erişilebilir system working contenti Tool Gateway üzerinden görür/kullanır. Human login değildir.</td>
    <td>Kendi agent-owned outputunu oluşturur.</td>
    <td>Yalnız own agent rootu üzerinde.</td>
    <td>Yalnız own outputunu soft delete eder.</td>
    <td>Yok; Trash/restore/purge yapamaz.</td>
  </tr>
</table>

Rationale Family kartı ve Package Rationale Assignment global shared-editing exceptiondır; ancak bu istisna Trade Log root, source asset, source mapping, file contents veya Trade Log revisionını değiştirme hakkı vermez. Trade Log normal owner policy ile korunur.

<table>
  <tr>
    <th>Canonical Rule: UIdeki hidden/disabled delete ya da save butonu authorization kanıtı değildir. Her list, detail, upload, import, save, pin, export ve delete commandi server-side principal, role, owner, lifecycle ve dependency policy ile tekrar doğrulanır.</th>
  </tr>
</table>

# 3. Arayüz Yerleşimi ve Navigasyon

V18de kullanıcı Mainboard > Add Outsource Signal > Trade Log seçimiyle yeni satır ekler. Satır "TRADE LOG n" veya legacy packageData geldiğinde "TRADE LOG PACKAGE n, [ad]" olarak görünür. Satırın sağında aç/kapat oku ve × silme kontrolü vardır. Ok, Trade Log details panelini açar; detay paneli üç kolonlu Strategy Details kabı içinde iki aktif kolonu kullanır: solda SOURCE/IDENTITY ve FILE UPLOAD/SOURCE DATA, ortada BULK TRADE LOG IMPORT / file-format guidance; alt sırada panel actions bulunur.

## 3.1 V18 görünür bileşen envanteri

<table>
  <tr>
    <th>Bölge / bileşen</th>
    <th>V18 Interface Behavior</th>
    <th>Görünme / varsayılan</th>
    <th>Production karşılığı</th>
  </tr>
  <tr>
    <td>Trade Log row</td>
    <td>Başlık metni, ▼/▲ arrow, × delete.</td>
    <td>Add Outsource Signal &gt; Trade Log seçilince satır oluşur; details kapalıdır.</td>
    <td>Persisted veya transient item projection. Legacy &quot;PACKAGE&quot; texti kaldırılır.</td>
  </tr>
  <tr>
    <td>Expanded detail panel</td>
    <td>trade-log-details / trading-data-details container; başta kapalı.</td>
    <td>Arrow ile open class eklenir.</td>
    <td>Presentation-only state; revision, readiness, audit veya engine etkisi yok.</td>
  </tr>
  <tr>
    <td>Column: TRADE LOG SOURCE</td>
    <td>1. TRADE LOG IDENTITY card; 7 field.</td>
    <td>Her yeni draftta görünür.</td>
    <td>Identity + scope draft formu.</td>
  </tr>
  <tr>
    <td>Column: BULK TRADE LOG IMPORT</td>
    <td>3. TRADE LOG TXT / CSV FILE card, native file input ve format guide.</td>
    <td>Her yeni draftta görünür.</td>
    <td>Source asset upload + durable ingestion job + report view.</td>
  </tr>
  <tr>
    <td>Bottom action bar</td>
    <td>Save As Trade Log Package, Clear, Export As Package. [V18 legacy prototype label; Production domain/API type değildir.]</td>
    <td>Her detay panelinde görünür.</td>
    <td>Labels/commands canonical terminologyye hizalanır; Save/Export actionları gerçek backend commands olur.</td>
  </tr>
  <tr>
    <td>Native file chooser</td>
    <td>input type=file accept=.txt,.csv.</td>
    <td>Dosya seçilene kadar boş.</td>
    <td>Accepted asset types same; actual upload/import server-side gerçekleşir.</td>
  </tr>
  <tr>
    <td>Modal/popover</td>
    <td>Bu panelde V18 custom modal veya ⓘ info popover yoktur.</td>
    <td>Uygulanmaz.</td>
    <td>Production: delete confirmation, durable import report drawer/paneli ve karar alanları için ⓘ controls eklenir.</td>
  </tr>
</table>

## 3.2 Responsive / scroll davranışı

- V18 CSS, trade-log-grid için dört kolonlu grid kullanır. Dar viewportlarda Strategy Details üst gridinin responsive kırılımı tek kolona düşer; detail container yatay taşmayı yönetir.

- TXT/CSV format guide monospaced, read-only bilgi alanıdır; uzun satırlar source file selector veya browser file UI tarafından gizlenmemelidir.

- Productionda import report tablo/drawerı büyük dosyalarda sanallaştırılmış veya sayfalı olmalıdır. Tüm satırları DOMa basmak, kaynak file boyutu büyüdüğünde UI bellek sorununa yol açmamalıdır.

- Expanded/collapsed state yalnız user presentation preference olarak tutulabilir. Shared Mainboard kompozisyonu, revision hash, Ready report veya Agent statei bu tercihten etkilenmez.

# 4. Interaction State Matrix

<table>
  <tr>
    <th>State</th>
    <th>Kullanıcının gördüğü durum</th>
    <th>Enabled actions</th>
    <th>Payload / engine etkisi</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>New transient draft</td>
    <td>Satır görünür; &quot;Unsaved&quot; badgei Productionda zorunlu. Defaults formda.</td>
    <td>Edit, choose file, Save Draft, Clear, discard.</td>
    <td>Root/revision/item yoksa Ready Check ve Run dahil etmez.</td>
    <td>Zorunlu alanları tamamla veya discard et; discard Trash oluşturmaz.</td>
  </tr>
  <tr>
    <td>Draft persisted</td>
    <td>Root + draft revision mevcut; import yok/eksik olabilir.</td>
    <td>Edit, upload, start import, Save Draft, delete.</td>
    <td>Ready olmayan revision pinlenebilir olsa dahi Ready Check blockers üretir.</td>
    <td>File/mapping/validation eksiklerini tamamla.</td>
  </tr>
  <tr>
    <td>File selected / upload pending</td>
    <td>Native inputta dosya adı / Production upload progress.</td>
    <td>Cancel before transfer complete, retry.</td>
    <td>Local selection engine inputu değildir; uploaded source asset oluşmadan revision ready olmaz.</td>
    <td>Tekrar seç veya network failure sonrası retry.</td>
  </tr>
  <tr>
    <td>Importing / parsing</td>
    <td>Durable job state + progress; UI refresh sonrası tekrar okunur.</td>
    <td>Read report; cancel only worker supports safe cancel.</td>
    <td>No Ready revision; active source asset immutable but parser output provisional.</td>
    <td>Job completion/failure stateini poll/SSE ile al; failed importi fix/reupload et.</td>
  </tr>
  <tr>
    <td>Parsed with warnings</td>
    <td>Row counts, skipped records, warnings gösterilir.</td>
    <td>Inspect report, revise mapping, save draft.</td>
    <td>Warning evidence revisionla ilişkilidir; severity policyye göre Ready Check warning/blocker olabilir.</td>
    <td>Mapping veya source data düzeltip new import revision üret.</td>
  </tr>
  <tr>
    <td>Validation failed / rejected</td>
    <td>Structured field/row errors and no Ready badge.</td>
    <td>Edit mapping, re-upload, Save Draft.</td>
    <td>Rejected revision backtest inputu olamaz.</td>
    <td>Source issueyi düzelt; prior valid revision historical olarak kalır.</td>
  </tr>
  <tr>
    <td>Ready revision, not pinned</td>
    <td>Validated immutable revision mevcut; board current pin eski olabilir.</td>
    <td>Use This Revision on Mainboard; export; create next revision.</td>
    <td>Current board / Run hâlâ old pinned revisionı kullanır.</td>
    <td>Açık pin commandi çalıştır.</td>
  </tr>
  <tr>
    <td>Pinned revision / ready report current</td>
    <td>Board item exact revisiona bağlıdır; Ready report hash ile ilişkilidir.</td>
    <td>Open, export, create new revision, delete subject to dependency preflight.</td>
    <td>Enabled ise snapshotta yer alır.</td>
    <td>Mutasyon/pin/enable değişirse Ready report stale olur; Ready Check tekrar gerekir.</td>
  </tr>
  <tr>
    <td>Stale / conflict</td>
    <td>Başka actor head veya row update yaptı; canonical server state gösterilir.</td>
    <td>Reload, compare, fork/merge, retry with new expected_head_revision_id.</td>
    <td>No silent overwrite, no hidden engine change.</td>
    <td>Server statei reload et; gerekirse forkla.</td>
  </tr>
  <tr>
    <td>Soft deleted</td>
    <td>Active list/selectorlardan kalkar; User/Supervisor/Agent Trash göremez.</td>
    <td>Normal edit/use/pin yok.</td>
    <td>Historical manifests/source summary remain readable through provenance policy.</td>
    <td>Only Admin restore; purge pending ise restore blocked.</td>
  </tr>
</table>

# 5. Alanlar, Varsayılanlar, Zorunluluk ve Dependency Contract

Yıldız (*) kuralı: Productionda zorunlu alanın etiketi * ile görünür. Yıldız yalnız görsel işaret değildir; frontend validation, server request validation, import validator, Ready Check ve Agent tool schema aynı requiredness kuralını uygular. V18de birden fazla required alan yıldızsız görünür; bu belge Production hizalamasını ayrıca belirtir.

## 5.1 Identity / source form field contract

<table>
  <tr>
    <th>Alan</th>
    <th>V18 UI / default</th>
    <th>Prod. requiredness</th>
    <th>Tüm seçenek / dependency</th>
    <th>Production payload</th>
    <th>Validation / reset behavior</th>
  </tr>
  <tr>
    <td>Trade Log Name</td>
    <td>Text input. Default: &quot;Trade Log n&quot;; legacy packageData name ile override olabilir.</td>
    <td>Always required *</td>
    <td>Free text display label; uniqueness root identity değildir.</td>
    <td>display_name</td>
    <td>Trimmed non-empty; max length policy. Clear new draftta factory defaulta döner; persisted draftta last-saved valueye döner.</td>
  </tr>
  <tr>
    <td>Source / Provider</td>
    <td>Text input. Default: &quot;External Quant&quot;; legacy packageData.owner gelebilir.</td>
    <td>Always required *</td>
    <td>Provider, broker export, internal research feed veya source description.</td>
    <td>source_provenance.provider_name</td>
    <td>Blank rejected. Name provider identity yerine geçmez; raw source asset hash ayrıca zorunludur.</td>
  </tr>
  <tr>
    <td>Market</td>
    <td>Text input. Default BTCUSDT.</td>
    <td>Always required *</td>
    <td>Production searchable canonical instrument scope selector. V1 single-instrument Trade Log.</td>
    <td>instrument_scope: [instrument_id]</td>
    <td>Free-text string persist edilmez. Unknown/unmapped symbol blocker. Source rows symbol sağlarsa selected scope ile match gerekir.</td>
  </tr>
  <tr>
    <td>Base TF</td>
    <td>Text input. Default 15m.</td>
    <td>Always required *</td>
    <td>Production enum: event_based | same_as_market_dataset | allowed bar interval. Trade Log non-bar events olabilir.</td>
    <td>time_model</td>
    <td>Unsupported TF or ambiguous event model rejected. Existing raw V18 text migrationda normalized value gerekir.</td>
  </tr>
  <tr>
    <td>Rationale Family</td>
    <td>Select. Default External Signal / Trade Log.</td>
    <td>Optional, recommended</td>
    <td>Options: Reversal / Mean Reversion; Trend / Directional Regime; Breakout / Volatility Expansion; Volatility / Regime; External Signal / Trade Log.</td>
    <td>rationale_family_ref {root_id, revision_id} | null</td>
    <td>Family seçimi trade mathiği değiştirmez. Selected family deleted/inaccessible ise save blocker or explicit unassign required per lifecycle.</td>
  </tr>
  <tr>
    <td>Data Quality</td>
    <td>Select. Default Entry / Exit Records Only.</td>
    <td>Always required *</td>
    <td>Entry / Exit Records Only; Trade Log + OHLCV; Trade Log + Signal Events.</td>
    <td>content_profile</td>
    <td>Seçim required column/mapping rulesini genişletir; Trade Log + Signal Events statusu Trading Signal rootuna dönüştürmez.</td>
  </tr>
  <tr>
    <td>Initial Capital</td>
    <td>Decimal text. Default 10000; V18de * visible.</td>
    <td>Conditional required *</td>
    <td>Equity Allocation disabled =&gt; required and &gt; 0. Enabled =&gt; preserved but run capital source değildir.</td>
    <td>independent_initial_capital.amount + currency</td>
    <td>Finite positive decimal. Allocation enabledken empty olabilir; old value silent delete edilmez.</td>
  </tr>
</table>

## 5.2 File / execution-context field contract

<table>
  <tr>
    <th>Alan</th>
    <th>V18 UI / default</th>
    <th>Prod. requiredness</th>
    <th>Tüm seçenek / dependency</th>
    <th>Production payload</th>
    <th>Validation / reset behavior</th>
  </tr>
  <tr>
    <td>Time Zone</td>
    <td>Text input. Default UTC.</td>
    <td>Always required *</td>
    <td>IANA timezone selector; timestamp with explicit offset overrides declared source zone only for that row.</td>
    <td>source_time_zone + normalization_policy</td>
    <td>Invalid/ambiguous timezone rejected. All canonical timestamps stored UTC plus original raw value/zone.</td>
  </tr>
  <tr>
    <td>Price Source</td>
    <td>Select. Default Trade Log Entry / Exit Price.</td>
    <td>Always required *</td>
    <td>Trade Log Entry / Exit Price; OHLCV Close If Needed; OHLCV Intrabar If Available.</td>
    <td>price_source_rule</td>
    <td>Fallback OHLCV seçilirse compatible Approved Market Dataset revision ref conditionally required. Ignore OHLCV context ile conflict oluşturamaz.</td>
  </tr>
  <tr>
    <td>OHLCV Use</td>
    <td>Select. Default Use only if supplied and needed.</td>
    <td>Always required *</td>
    <td>Use only if supplied and needed; Ignore OHLCV context; Use for price context and validation.</td>
    <td>ohlcv_context_policy</td>
    <td>Price Source fallbacki &quot;OHLCV Close/Intrabar&quot; ise Ignore invalid. Imported OHLCV columns, canonical Market Data replacement değildir.</td>
  </tr>
  <tr>
    <td>Trade Log TXT / CSV</td>
    <td>Native file input accept=.txt,.csv. Default no file.</td>
    <td>Required to create Validated / Ready revision *; Save Draft allows absent file.</td>
    <td>One source asset per import revision. TXT/CSV only; comma, semicolon, tab, pipe supported.</td>
    <td>source_asset_id + raw_asset_hash + import_mapping_ref</td>
    <td>Extension/parseability/type validated server-side. Changing file invalidates pending import and requires new source asset / revision.</td>
  </tr>
  <tr>
    <td>Column mapping</td>
    <td>V18 explicit mapping UI yok; format guide is read-only.</td>
    <td>Required for normalized import when exact canonical headers unavailable.</td>
    <td>Canonical required fields, optional fields and header alias resolver.</td>
    <td>import_mapping_json + mapping_hash</td>
    <td>Server cannot infer an ambiguous mapping. Mapping change produces new import evidence/revision; raw asset stays immutable.</td>
  </tr>
</table>

## 5.3 Data Quality option semantics

<table>
  <tr>
    <th>Option</th>
    <th>Anlam</th>
    <th>Import/engine consequence</th>
  </tr>
  <tr>
    <td>Entry / Exit Records Only</td>
    <td>Dosya yalnız geçmiş trade ledger alanlarını taşır.</td>
    <td>direction, entry_time, entry_price, exit_time, exit_price canonical minimumudur. Entry/exit fiyatları primary record evidence olur.</td>
  </tr>
  <tr>
    <td>Trade Log + OHLCV</td>
    <td>Trade records yanında open/high/low/close/volume gibi contextual columns bulunur.</td>
    <td>Source asset içindeki OHLCV yalnız context/validation evidence olarak tutulur. Backtest execution ground olması için ayrı Approved Market Dataset revision şarttır.</td>
  </tr>
  <tr>
    <td>Trade Log + Signal Events</td>
    <td>Trade records yanında source signal/event columns bulunur.</td>
    <td>Ek event metadata record provenanceına bağlı kalır. Kayıt Trade Log olarak kalır; Trading Signal Working Itemi otomatik yaratılmaz ve live signal semantics oluşmaz.</td>
  </tr>
</table>

## 5.4 Import file canonical column contract

<table>
  <tr>
    <th>Field</th>
    <th>Required</th>
    <th>Canonical semantic</th>
    <th>Server validation</th>
  </tr>
  <tr>
    <td>direction</td>
    <td>Yes</td>
    <td>Trade direction: long veya short.</td>
    <td>Case/alias normalization after mapping; enum dışı row skipped/error severity policy; Ready için unresolved invalid rows threshold aşamaz.</td>
  </tr>
  <tr>
    <td>entry_time</td>
    <td>Yes</td>
    <td>Açılış zamanı.</td>
    <td>Declared IANA timezone / explicit offset ile UTC normalize edilir. Invalid timestamp or unavailable zone rejects row.</td>
  </tr>
  <tr>
    <td>entry_price</td>
    <td>Yes</td>
    <td>Gerçekleşmiş veya source tarafından raporlanmış giriş fiyatı.</td>
    <td>Finite number and &gt; 0.</td>
  </tr>
  <tr>
    <td>exit_time</td>
    <td>Yes</td>
    <td>Kapanış zamanı.</td>
    <td>UTC normalize edilir; entry_time sonrasına veya eşitine izin verilir, öncesi reject.</td>
  </tr>
  <tr>
    <td>exit_price</td>
    <td>Yes</td>
    <td>Gerçekleşmiş veya source tarafından raporlanmış çıkış fiyatı.</td>
    <td>Finite number and &gt; 0.</td>
  </tr>
  <tr>
    <td>size</td>
    <td>No</td>
    <td>Raporlanmış quantity / size.</td>
    <td>Provided ise finite and &gt; 0. Unit metadata varsa preserve edilir; missing size recordı otomatik equity computationa dönüştürmez.</td>
  </tr>
  <tr>
    <td>fees</td>
    <td>No</td>
    <td>Raporlanmış fee.</td>
    <td>Provided ise finite and &gt;= 0. Fee currency mapping yoksa raw reported field olarak korunur; cross-currency reconciliation warning.</td>
  </tr>
  <tr>
    <td>pnl</td>
    <td>No</td>
    <td>Source-reported realised P&amp;L.</td>
    <td>Provided ise finite. Direction/price/size ile fark anlamlıysa warning; server silently overwrites reported P&amp;L yapmaz.</td>
  </tr>
  <tr>
    <td>symbol / instrument</td>
    <td>No but recommended</td>
    <td>Satır bazlı market identity.</td>
    <td>Provided ise selected Market / Instrument Scope ile normalize-match gerekir. V1 single-instrument scope ile mixed symbol blocker.</td>
  </tr>
  <tr>
    <td>open, high, low, close, volume</td>
    <td>No</td>
    <td>Trade record context OHLCV alanları.</td>
    <td>Only Data Quality allows contextual OHLCV. Not treated as Approved Market Dataset.</td>
  </tr>
</table>

## 5.5 V18 format guide - exact visible content

<table>
  <tr>
    <th>Required columns:<br/>direction, entry_time, entry_price, exit_time, exit_price<br/><br/>Optional columns:<br/>size, fees, pnl, symbol, open, high, low, close, volume<br/><br/>Accepted separators:<br/>comma, semicolon, tab or |<br/><br/>Example:<br/>Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850,1.0,2.1,750,BTCUSDT<br/>Short,2024-01-02 09:15,43000,2024-01-02 18:00,41950,1.0,2.4,1050,BTCUSDT</th>
  </tr>
</table>

V18 Interface Observation: Bu format kutusu read-only guidance olarak görünür; paste box yoktur. HTMLde parseTradeLogText, previewTradeLogBulk ve related preview functions bulunmasına rağmen rendered Trade Log panelinde textarea, preview table, Preview veya Clear Bulk buttonları yoktur. Bu nedenle dead/unused helper functions Production UI requirementi sayılmaz.

# 6. ⓘ Information Content Catalog

V18 rendered Trade Log panelinde alanlara bağlı ⓘ buttons bulunmaz. Handoff standardını karşılamak ve file/import semanticsini görünür kılmak için Production UI aşağıdaki karar-kritik alanlarda ⓘ ekler. Aşağıdaki metinler doğrudan UI popoverına yerleştirilecek nihai içeriktir.

<table>
  <tr>
    <th>Info key / UI field</th>
    <th>Panel title</th>
    <th>Nihai UI metni</th>
  </tr>
  <tr>
    <td>tradeLogNameInfo</td>
    <td>Trade Log Name</td>
    <td>Bu ad, Trade Log çalışma nesnesinin kullanıcıya görünen adıdır. Aynı adlı iki kaynak olabilir; sistemin gerçek kimliği ad değil Trade Log root ID ve revision IDdir.<br/><br/>Adı değiştirmek geçmiş Backtest Run veya Result kayıtlarını yeniden adlandırmaz. Kaydedilen değişiklik yeni bir Trade Log revisionı oluşturur.</td>
  </tr>
  <tr>
    <td>tradeLogProviderInfo</td>
    <td>Source / Provider</td>
    <td>Kaynağın nereden geldiğini açıklar: örneğin broker exportu, exchange CSVsi, copy-trading sağlayıcısı veya kurum içi araştırma feedi.<br/><br/>Bu alan tek başına kanıt değildir. Sistem ayrıca yüklenen source assetin hashini, import mappingini ve validation raporunu revisiona bağlar.</td>
  </tr>
  <tr>
    <td>tradeLogMarketInfo</td>
    <td>Market / Instrument Scope</td>
    <td>Trade Logun hangi enstrüman için geçerli olduğunu belirtir. Productionda serbest metin yerine canonical instrument seçimi kullanılır.<br/><br/>Dosyada symbol alanı varsa, bu seçilen enstrümanla eşleşmelidir. V1 Trade Log tek enstrüman scopeuyla çalışır; karışık sembollü dosya ayrı importlara bölünmelidir.</td>
  </tr>
  <tr>
    <td>tradeLogTimeModelInfo</td>
    <td>Base TF / Event Model</td>
    <td>Trade Log kayıtları event-based olabilir veya belirli bir bar çözünürlüğüne bağlı olabilir. Event-based kayıtlar yalnız zaman damgalarıyla değerlendirilir; bar tabanlı model ise seçilen timeframe ile hizalanır.<br/><br/>Bu seçim, source timestampinin ve gerekirse OHLCV fallbackin nasıl yorumlandığını belirler. Trade Log yeni live signal üretmez.</td>
  </tr>
  <tr>
    <td>tradeLogFamilyInfo</td>
    <td>Rationale Family</td>
    <td>Rationale Family, Trade Logu ortak araştırma sözlüğünde sınıflandırır; tek başına entry, exit, risk veya backtest matematiği üretmez.<br/><br/>Family kartları global shared-editing istisnasıdır; fakat bu seçimin yapılması başka kullanıcıya Trade Log source file veya revisionını düzenleme yetkisi vermez.</td>
  </tr>
  <tr>
    <td>tradeLogQualityInfo</td>
    <td>Data Quality</td>
    <td>Entry / Exit Records Only yalnız trade ledgerını ifade eder. Trade Log + OHLCV veya Trade Log + Signal Events seçeneği dosyada ek bağlam bulunduğunu belirtir.<br/><br/>Ek kolonlar source evidence olarak saklanır. Bunlar Market Data registrysini veya Trading Signal çalışma nesnesini otomatik oluşturmaz.</td>
  </tr>
  <tr>
    <td>tradeLogCapitalInfo</td>
    <td>Initial Capital</td>
    <td>Equity Allocation kapalıysa Trade Log bu bağımsız başlangıç sermayesiyle değerlendirilir ve değer sıfırdan büyük olmalıdır.<br/><br/>Equity Allocation açıksa shared pool ve allocation revisionı bu değer yerine kullanılır. Bu durumda bağımsız değer korunur fakat o backtestin aktif capital inputu değildir.</td>
  </tr>
  <tr>
    <td>tradeLogTimezoneInfo</td>
    <td>Time Zone</td>
    <td>Source timestamplerinin hangi zaman bölgesinde yazıldığını belirtir. Sistem kayıtları UTCye normalize eder; orijinal raw timestamp ve source timezone kanıt için korunur.<br/><br/>Saat dilimi belirsiz veya geçersizse import tamamlanmaz. Dosyada açık UTC offseti bulunan bir satır, o satır için genel timezone bilgisinden önceliklidir.</td>
  </tr>
  <tr>
    <td>tradeLogPriceSourceInfo</td>
    <td>Price Source</td>
    <td>Trade Log Entry / Exit Price, dosyada raporlanan giriş/çıkış fiyatlarını birincil kaynak kabul eder. OHLCV Close If Needed veya OHLCV Intrabar If Available yalnız açık fallback kuralıdır.<br/><br/>Fallback seçilirse compatible Approved Market Data revisionı zorunlu olur. Source dosyasındaki OHLCV kolonları tek başına production execution datası değildir.</td>
  </tr>
  <tr>
    <td>tradeLogOhlcvUseInfo</td>
    <td>OHLCV Use</td>
    <td>Use only if supplied and needed, source içindeki OHLCV bağlamını yalnız gerekli olduğunda kullanır. Ignore OHLCV context hiçbir OHLCV alanının işlenmemesini ister. Use for price context and validation, OHLCVyi açıklama/uyum kontrolü için kullanır.<br/><br/>Price Source OHLCV fallback seçiliyken Ignore OHLCV context seçilemez.</td>
  </tr>
  <tr>
    <td>tradeLogFileInfo</td>
    <td>Trade Log TXT / CSV File</td>
    <td>Bu alan bir source asset yükler. Dosya seçmek backtest için hazır olduğu anlamına gelmez; asset önce durable import job tarafından parse edilir, mapping uygulanır ve validation evidence üretilir.<br/><br/>Gerekli alanlar: direction, entry_time, entry_price, exit_time, exit_price. Kabul edilen ayraçlar: comma, semicolon, tab ve pipe.</td>
  </tr>
  <tr>
    <td>tradeLogImportReportInfo</td>
    <td>Import Report</td>
    <td>Import Report kaç satırın okunduğunu, kaç satırın atlandığını, hangi mappingin kullanıldığını ve hangi hata/warninglerin bulunduğunu gösterir.<br/><br/>Atlanan satırlar sessizce kaybolmaz; row number, raw reason ve severity revision evidenceinde saklanır. Ready statusu yalnız policyye uygun valid record seti oluştuğunda verilir.</td>
  </tr>
</table>

# 7. Placeholder, Helper, Warning, Toast ve Error Content Catalog

<table>
  <tr>
    <th>Tür / context</th>
    <th>Nihai UI metni</th>
  </tr>
  <tr>
    <td>Placeholder - Trade Log Name</td>
    <td>e.g., Binance BTCUSDT Perpetual trade history - Q1 2026</td>
  </tr>
  <tr>
    <td>Placeholder - Source / Provider</td>
    <td>e.g., Binance Futures export, broker statement, or internal research feed</td>
  </tr>
  <tr>
    <td>Placeholder - Market / Instrument Scope</td>
    <td>Select a market / instrument</td>
  </tr>
  <tr>
    <td>Helper - source file</td>
    <td>Upload one TXT or CSV source file for this import revision. The original file is preserved as immutable source evidence.</td>
  </tr>
  <tr>
    <td>Helper - import</td>
    <td>Required fields: direction, entry_time, entry_price, exit_time, exit_price. Optional fields are preserved when mapped.</td>
  </tr>
  <tr>
    <td>Warning - unpinned revision</td>
    <td>A newer validated Trade Log revision is available. The Mainboard still uses revision {pinned_revision_no}. Select &quot;Use This Revision on Mainboard&quot; to change the next snapshot.</td>
  </tr>
  <tr>
    <td>Warning - source OHLCV</td>
    <td>Source-file OHLCV is contextual evidence only. It does not replace an Approved Market Data revision for execution fallback.</td>
  </tr>
  <tr>
    <td>Warning - partial import</td>
    <td>{skipped_count} rows were skipped. Review the Import Report before using this revision in a backtest.</td>
  </tr>
  <tr>
    <td>Toast - draft saved</td>
    <td>Trade Log draft saved. It is not backtest-ready until source import and validation complete.</td>
  </tr>
  <tr>
    <td>Toast - revision ready</td>
    <td>Trade Log revision {revision_no} is validated and ready. The current Mainboard pin was not changed automatically.</td>
  </tr>
  <tr>
    <td>Toast - pinned</td>
    <td>Trade Log revision {revision_no} is now pinned to Mainboard. The previous Ready Check is stale; run Backtest Ready Check again.</td>
  </tr>
  <tr>
    <td>Toast - export ready</td>
    <td>Trade Log source-mapping export is ready. No Trade Log Package was created. [V18 legacy prototype label; Production domain/API type değildir.]</td>
  </tr>
  <tr>
    <td>Toast - deleted</td>
    <td>Trade Log was moved to Trash. Only an Admin can restore or permanently delete it.</td>
  </tr>
  <tr>
    <td>Error - required source</td>
    <td>Enter a source or provider name before saving this Trade Log.</td>
  </tr>
  <tr>
    <td>Error - required file</td>
    <td>Select a TXT or CSV source file before validating this Trade Log revision.</td>
  </tr>
  <tr>
    <td>Error - required column</td>
    <td>The file must provide direction, entry_time, entry_price, exit_time and exit_price.</td>
  </tr>
  <tr>
    <td>Error - time zone</td>
    <td>Select a valid IANA time zone before importing timestamps.</td>
  </tr>
  <tr>
    <td>Error - instrument mapping</td>
    <td>Map the selected market and every supplied symbol to the same canonical instrument before validation.</td>
  </tr>
  <tr>
    <td>Error - price context conflict</td>
    <td>OHLCV fallback cannot be used while OHLCV Use is set to Ignore OHLCV context.</td>
  </tr>
  <tr>
    <td>Error - capital</td>
    <td>Initial Capital must be greater than zero while Equity Allocation is not selected.</td>
  </tr>
  <tr>
    <td>Error - stale revision</td>
    <td>This Trade Log changed after you opened it. Reload the current revision, compare your changes and save a new revision.</td>
  </tr>
  <tr>
    <td>Error - active run dependency</td>
    <td>This Trade Log is part of a queued or running Backtest Run and cannot be deleted until that run is completed or cancelled.</td>
  </tr>
</table>

# 8. Buttons, Commands ve State Davranışları

<table>
  <tr>
    <th>V18 control</th>
    <th>V18 Interface Behavior</th>
    <th>Production command / precondition</th>
    <th>Loading / success / error / audit</th>
  </tr>
  <tr>
    <td>▼ / ▲ row arrow</td>
    <td>Toggles open classes; no server action.</td>
    <td>Presentation toggle only. Optional user_ui_preferences update; never revision/pin/readiness mutation.</td>
    <td>No loading. No audit required. Must not invalidate Ready report.</td>
  </tr>
  <tr>
    <td>× delete row</td>
    <td>Calls local moveMainboardItemToTrash, removes row and flips local backtestReady false.</td>
    <td>DeleteTradeLog(root_id, expected state, idempotency_key). Confirmation required. Block if queued/running run manifest references root/revision.</td>
    <td>Pending: disable confirm. Success: root soft_deleted + Trash entry + audit + outbox; row disappears only after server success. Error: show active run / permission / conflict recovery.</td>
  </tr>
  <tr>
    <td>Save As Trade Log Package [V18 legacy prototype label; Production domain/API type değildir.]</td>
    <td>Visible primary button; V18 has no bound command. Legacy wording is non-canonical.</td>
    <td>Production split: Save Draft, Validate &amp; Save Trade Log Revision. Initial valid save can attach revision 1 to originating default Mainboard; later saves create revision only.</td>
    <td>Saving state shows immutable revision creation. Success canonical response rehydrates editor. No &quot;Trade Log Package&quot; created. Audit TRADE_LOG_REVISION_CREATED. [V18 legacy prototype label; Production domain/API type değildir.]</td>
  </tr>
  <tr>
    <td>Use This Revision on Mainboard</td>
    <td>Not visible in V18.</td>
    <td>Implementation Decision: explicit PinTradeLogRevision(mainboard_working_item_id, revision_id, expected_row_version). Requires saved, use-authorized active revision.</td>
    <td>Success updates pin, composition hash and stales matching Ready reports; audit + event. Conflict returns current row/version.</td>
  </tr>
  <tr>
    <td>Clear</td>
    <td>V18 resets name to generic, clears source/file, keeps most other defaults/selects; flips local ready false.</td>
    <td>ClearUnsavedTradeLogDraft. For new transient draft restore factory defaults; for persisted draft restore last server-saved draft projection.</td>
    <td>No root/revision delete. No audit. Warn if local dirty edits: &quot;Discard unsaved changes?&quot;</td>
  </tr>
  <tr>
    <td>Export As Package</td>
    <td>Visible, no bound V18 command; label conflicts with canonical boundary.</td>
    <td>ExportTradeLogSourceMapping / RequestTradeLogExport. Generates mapping/provenance artifact, not PackageKind=trade_log.</td>
    <td>Small export can stream; large source-derived export is job. Audit export requested/completed; failure retry safe with idempotency.</td>
  </tr>
  <tr>
    <td>Choose TXT / CSV file</td>
    <td>Native browser file selection, then markTradingDataFileLoaded only.</td>
    <td>UploadSourceAsset + StartTradeLogIngestion. Draft/root permission and allowed file type required.</td>
    <td>Progress from durable upload/import state; source asset hash, report id and job id returned. Upload failure offers retry.</td>
  </tr>
</table>

## 8.1 Candidate API / Tool command contract

Exact URI names Masterda tam sabit değildir. Aşağıdaki semantic contract, Modül 19 OpenAPI çalışmasında korunacak Implementation Decision - Non-Canonical Gap Resolutiondır.

<table>
  <tr>
    <th>POST /v1/trade-logs/drafts<br/>{ workspace_id, display_name?, source_provenance?, instrument_scope?, time_model?, idempotency_key }<br/><br/>POST /v1/trade-logs/{root_id}/source-assets<br/>{ file, declared_time_zone, content_profile, idempotency_key } -&gt; { source_asset_id, raw_asset_hash, upload_id }<br/><br/>POST /v1/trade-logs/{root_id}/imports<br/>{ source_asset_id, import_mapping, expected_head_revision_id?, idempotency_key } -&gt; { import_job_id, state }<br/><br/>POST /v1/trade-logs/{root_id}/revisions<br/>{ expected_head_revision_id, identity, time_model, price_source_rule, ohlcv_context_policy, import_report_id, independent_initial_capital?, rationale_family_ref?, change_note?, idempotency_key } -&gt; { revision_id, revision_no, validation_summary, content_hash }<br/><br/>PATCH /v1/mainboard-items/{item_id}<br/>{ pinned_revision_id, expected_row_version, idempotency_key } -&gt; { item, composition_hash, ready_reports_marked_stale }<br/><br/>DELETE /v1/work-objects/{root_id}<br/>{ idempotency_key } -&gt; soft delete preflight / Trash entry / audit / outbox</th>
  </tr>
</table>

# 9. Kullanıcı Akışları

## 9.1 Yeni Trade Log oluşturma ve Ready revision üretme

- Kullanıcı Mainboard > Add Outsource Signal > Trade Log seçer. V18de geçici satır hemen görünür; Productionda bu satır açıkça Unsaved olarak işaretlenir.

- Kullanıcı Trade Log Name, Source / Provider, Market / Instrument Scope, Base TF / Event Model, Time Zone ve gerekli price/data policy alanlarını doldurur. Rationale Family isteğe bağlıdır; V18 defaultu External Signal / Trade Logtur.

- Kullanıcı TXT/CSV dosyasını seçer. Client yalnız upload isteğini başlatır; dosya satırlarını production authority olarak DOMda parse etmez.

- Backend source asseti immutable hash ile saklar ve Import Jobu queueya verir. UI durable job statusunu SSE/poll ile gösterir.

- Worker delimiter/mapping/timestamp normalization/record validation yapar; parse report, skipped-row report ve canonical trade-record batch üretir.

- Kullanıcı import reportu inceler. Blocker yoksa Validate & Save Trade Log Revision commandi immutable revision oluşturur. İlk save, originating default Mainboarda item attach edebilir; revision id explicit pinlenir.

- Ready Check daha sonra persisted, enabled ve pinned revisionı snapshotta kullanır. Bu sayfa Ready Check sonucunu üretmez; yalnız doğru revision dependencylerini sağlar.

## 9.2 Mapping veya source data hatası recovery

- Import Report required column missing, invalid timestamp veya unknown instrument bulursa revision Ready olmaz; UI row number + reason + severity gösterir.

- Kullanıcı mappingi, timezoneı veya source fileı düzeltir. Source file değişirse eski asset ve report immutable historical evidence olarak kalır; yeni asset/import evidence oluşur.

- Yeni valid payload yeni Trade Log revision üretir. Eski rejected/draft revisionlar üzerinde in-place update yapılmaz.

- Mevcut Mainboard item eski pinned revisionı kullanıyorsa kullanıcı açık "Use This Revision on Mainboard" actionını seçer. Pin sonrası prior Ready Check stale olur ve yeniden çalıştırılmalıdır.

## 9.3 Equity Allocation kapalı / açık initial capital akışı

- Allocation kapalı: Initial Capital * boş, sıfır veya negatifse Ready Check blocker üretir. Trade Log, own revisiondaki independent capital değerini kullanır.

- Allocation açık: Independent value editor stateinde korunabilir; ancak active run capital source shared Portfolio Allocation Plan / Revision olur. Bu sayfa allocation rowlarını yönetmez.

- Mutasyon etkisi: Initial Capital, enabled independent mode için revision contentinin parçasıdır. Değişiklik new revision üretir; eski run manifestleri değişmez.

## 9.4 Delete, historical integrity ve restore sınırı

- Kullanıcı × düğmesine basar. Production confirmation: "Delete Trade Log? This removes it from active Mainboard and new selections. Historical runs remain reproducible from their pinned revision."

- Backend owner/Admin policy ve active run/queue dependency preflighti yapar. Queued/running input varsa `OBJECT_IN_ACTIVE_RUN` ile delete reject edilir.

- Eligible delete rootu soft_deleted yapar, active Mainboard itemini kaldırır, Trash Entry snapshotı / audit event / outbox eventini aynı transactionda üretir.

- User, Supervisor ve Agent Trade Logu Trashda göremez. Admin restore ederse aynı root ID ve current revision pointer ACTIVE olur; yeni revision oluşmaz.

- Completed historical Backtest Result, silinen Trade Logun adı ve import provenanceını run manifest snapshotından okumaya devam eder. Purge yalnız Admin tarafından asenkron başlatılır; tombstone/audit chain korunur.

# 10. Production Backend ve Domain Davranışı

## 10.1 Root, revision, asset, job ve record ilişkisi

<table>
  <tr>
    <th>trade_log_root<br/>  id, object_kind=&quot;trade_log&quot;, owner_actor_id, current_revision_id, lifecycle_state, row_version<br/>      |<br/>      +-- trade_log_revision (immutable)<br/>      |     id, root_id, revision_no, payload_json, source_provenance_json, validation_summary_json, content_hash, supersedes_revision_id<br/>      |<br/>      +-- source_asset (immutable raw TXT/CSV)<br/>      |     id, root_id, raw_asset_hash, storage_ref, original_filename, declared_time_zone, uploaded_by, created_at<br/>      |<br/>      +-- import_job / import_report / canonical_trade_record_batch<br/>      |     source_asset_id, mapping_hash, parsed_count, skipped_count, error_summary, record_batch_revision_id<br/>      |<br/>      +-- mainboard_working_item<br/>            item_kind=&quot;trade_log&quot;, referenced_root_id, pinned_revision_id, is_enabled, position_index, row_version</th>
  </tr>
</table>

Masterdaki generic root/revision omurgası burada Trade Log domain tablolarıyla birleşir. Revision payload JSONB taşıyabilir; ancak root, revision, source asset, import report, record batch, ownership, lifecycle, dependency ve Mainboard relations sorgulanabilir tablolar/foreign keys olarak tutulmalıdır. Sadece tek büyük JSON kolonuna dayanmak yasaktır.

## 10.2 Canonical revision payload - conceptual schema

<table>
  <tr>
    <th>{<br/>  &quot;schema_version&quot;: &quot;trade_log_revision_v1&quot;,<br/>  &quot;display_name&quot;: &quot;Binance BTCUSDT Perpetual trade history - Q1 2026&quot;,<br/>  &quot;source_provenance&quot;: {&quot;provider_name&quot;: &quot;Binance Futures export&quot;, &quot;source_asset_id&quot;: &quot;asset_...&quot;, &quot;raw_asset_hash&quot;: &quot;sha256:...&quot;},<br/>  &quot;instrument_scope&quot;: [{&quot;instrument_id&quot;: &quot;inst_btcusdt_perp&quot;, &quot;display&quot;: &quot;BTCUSDT Perpetual&quot;}],<br/>  &quot;time_model&quot;: {&quot;kind&quot;: &quot;event_based&quot;, &quot;source_time_zone&quot;: &quot;UTC&quot;, &quot;normalization&quot;: &quot;utc&quot;},<br/>  &quot;rationale_family_ref&quot;: {&quot;root_id&quot;: &quot;family_external&quot;, &quot;revision_id&quot;: &quot;family_rev_...&quot;},<br/>  &quot;content_profile&quot;: &quot;entry_exit_records&quot;,<br/>  &quot;price_source_rule&quot;: &quot;trade_log_entry_exit_price&quot;,<br/>  &quot;ohlcv_context_policy&quot;: &quot;use_only_if_supplied_and_needed&quot;,<br/>  &quot;approved_market_data_revision_ref&quot;: null,<br/>  &quot;independent_initial_capital&quot;: {&quot;amount&quot;: &quot;10000&quot;, &quot;currency&quot;: &quot;USDT&quot;},<br/>  &quot;import&quot;: {&quot;report_id&quot;: &quot;import_report_...&quot;, &quot;mapping_hash&quot;: &quot;sha256:...&quot;, &quot;record_batch_revision_id&quot;: &quot;tlbatch_...&quot;},<br/>  &quot;validation_summary&quot;: {&quot;status&quot;: &quot;passed&quot;, &quot;warnings&quot;: []}<br/>}</th>
  </tr>
</table>

## 10.3 Import/validation worker pipeline

<table>
  <tr>
    <th>Aşama</th>
    <th>Command / worker</th>
    <th>Durable output</th>
    <th>Failure / recovery</th>
  </tr>
  <tr>
    <td>1. Upload acceptance</td>
    <td>UploadSourceAsset</td>
    <td>Immutable raw source asset, raw_asset_hash, upload audit.</td>
    <td>Invalid extension/content or duplicate handling returns structured error; caller can choose a corrected file.</td>
  </tr>
  <tr>
    <td>2. Ingestion queue</td>
    <td>StartTradeLogIngestion</td>
    <td>Import job id, queued state, correlation id.</td>
    <td>HTTP response returns immediately; refresh/logout does not stop job.</td>
  </tr>
  <tr>
    <td>3. Parse / delimiter</td>
    <td>Worker parses comma, semicolon, tab or pipe with quoting-aware parser.</td>
    <td>Detected delimiter, source row count, parse diagnostics.</td>
    <td>Unparseable file =&gt; IMPORT_PARSE_FAILED; raw asset remains evidence.</td>
  </tr>
  <tr>
    <td>4. Header/mapping</td>
    <td>Mapping resolver maps aliases to canonical trade fields.</td>
    <td>Mapping JSON, mapping hash, unresolved columns report.</td>
    <td>Ambiguous/missing required fields =&gt; MAPPING_REQUIRED / REQUIRED_COLUMN_MISSING.</td>
  </tr>
  <tr>
    <td>5. Normalize</td>
    <td>Timezone and instrument normalizer.</td>
    <td>UTC fields, source raw values, instrument mapping report.</td>
    <td>Invalid zone/time/symbol results row error/blocker according to policy.</td>
  </tr>
  <tr>
    <td>6. Record validation</td>
    <td>Trade-record validator.</td>
    <td>Canonical record batch + skipped row report + quality summary.</td>
    <td>Price/time/direction violations never silently corrected. User fixes source/mapping and creates new import evidence.</td>
  </tr>
  <tr>
    <td>7. Save revision</td>
    <td>CreateTradeLogRevision</td>
    <td>Immutable revision with validation summary and content hash.</td>
    <td>Expected head mismatch -&gt; 409; no lost update. Not Ready if evidence invalid.</td>
  </tr>
</table>

## 10.4 Decision order when a Trade Log participates in a backtest

Trade Logun internal validation pipelinei ile global Backtest Engine event order aynı şey değildir. Bu sayfa yalnız Trade Logun backtest girdisi olarak doğrulanmış historical records sağlayacağını tanımlar. Global run orchestration Ready Check / RUN sayfalarının kapsamındadır.

- Server reads a persisted, enabled Mainboard item and its exact pinned Trade Log revision from an immutable Mainboard Composition Snapshot.

- Engine resolves Trade Log revision, source asset provenance, import report, canonical record batch, time model, price source rule, independent capital or Allocation snapshot, and any approved Market Data fallback reference.

- Historical record timestamps and prices are interpreted only through normalized revision data. Browser form values, current display labels, latest source files, or current package catalogs are not read as runtime inputs.

- Trade Log behaviour is evaluated as historical reference/analysis input according to Run semantics. It does not create a live signal or mutate a Strategy rule graph.

- Run manifest stores root id, exact revision id, content hash, record batch revision id, source asset hash, mapping hash, price policy and capital mode snapshot. Only a succeeded Backtest Run can later create immutable Result artifacts.

## 10.5 Server-side command validation order

<table>
  <tr>
    <th>authorize(actor, command, trade_log_root?)<br/>assert_idempotency(actor, command_type, idempotency_key)<br/>load root/item/revision state FOR UPDATE when mutating<br/>validate role + owner + lifecycle + deletion state<br/>validate expected_head_revision_id / expected_row_version<br/>validate identity, scope, timezone, file/import/report, price-policy and capital dependencies<br/>canonicalize payload -&gt; calculate content_hash<br/>create immutable revision or update pin transactionally<br/>recompute composition_hash if Mainboard binding changes<br/>mark matching Ready reports stale when fingerprint changes<br/>append audit event + transactional outbox event<br/>return canonical server state, warnings and machine-readable issues</th>
  </tr>
</table>

# 11. Agent Tool / API Eşdeğeri ve Sürekli Çalışma Sınırı

Agent, Trade Log işlemlerini tarayıcıda dosya seçerek veya Mainboard butonlarına tıklayarak yürütmez. Agent runtime, Tool Gateway/API/domain service üzerinden aynı validation, ownership, revision, source-provenance, import-job, pinning ve audit yolunu kullanır. İnsan UIının açık kalması, normal chat mesajı veya Lab Assistant yanıtı Agentın bu işlemleri yapmasının ön koşulu değildir.

<table>
  <tr>
    <th>Agent capability</th>
    <th>UI equivalent</th>
    <th>Tool/API semantic action</th>
    <th>Policy / provenance</th>
  </tr>
  <tr>
    <td>Create draft</td>
    <td>Add Outsource Signal &gt; Trade Log</td>
    <td>create_trade_log_draft</td>
    <td>Agent-owned root/draft or research composition; human default board automatic mutation değildir.</td>
  </tr>
  <tr>
    <td>Attach source asset</td>
    <td>Choose TXT / CSV file</td>
    <td>upload_trade_log_source_asset</td>
    <td>Asset provider/source provenance, raw hash, task_id/checkpoint_id recorded.</td>
  </tr>
  <tr>
    <td>Import / validate</td>
    <td>No complete V18 server action</td>
    <td>start_trade_log_ingestion; get_import_report</td>
    <td>Durable job; Agent receives structured errors and may create remediation task.</td>
  </tr>
  <tr>
    <td>Save revision</td>
    <td>Save Draft / Validate &amp; Save</td>
    <td>create_trade_log_revision</td>
    <td>Expected head revision required; Agent cannot overwrite parallel work.</td>
  </tr>
  <tr>
    <td>Use revision</td>
    <td>Use This Revision on Mainboard</td>
    <td>pin_trade_log_revision</td>
    <td>Agent may pin in agent_research workspace; human board only explicit shared/attach policy.</td>
  </tr>
  <tr>
    <td>Export mapping</td>
    <td>Export Source Mapping</td>
    <td>request_trade_log_export</td>
    <td>Produces artifact; no Trade Log Package kind. [V18 legacy prototype label; Production domain/API type değildir.]</td>
  </tr>
  <tr>
    <td>Delete own output</td>
    <td>× delete</td>
    <td>soft_delete_trade_log</td>
    <td>Agent only own output; no Trash access/restore/purge; active task not silently stopped.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Canonical Rule: Normal discussion with Lab Assistant does not change Alpha Agent active task. A human directive is queued and taken only at a safe checkpoint. Therefore a Trade Log import/revision task created by Agent is durable coordinator work, not an in-browser chat side effect.</th>
  </tr>
</table>

# 12. Validation, Error, Recovery ve Concurrency Contract

<table>
  <tr>
    <th>Katman</th>
    <th>Blocker / warning örnekleri</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>Field validation</td>
    <td>Blank name/provider; invalid IANA timezone; capital &lt;= 0 in independent mode; unknown market.</td>
    <td>Correct field; save/retry. No revision created on blocker.</td>
  </tr>
  <tr>
    <td>File / parse</td>
    <td>Unsupported type, unreadable encoding, impossible delimiter, malformed quoted CSV.</td>
    <td>Upload corrected TXT/CSV. Raw failed asset/report remains evidence where accepted.</td>
  </tr>
  <tr>
    <td>Mapping / schema</td>
    <td>Missing required columns, ambiguous headers, no instrument mapping, mixed symbols under V1 single scope.</td>
    <td>Select/repair mapping, split file, or set canonical instrument scope; start new import revision.</td>
  </tr>
  <tr>
    <td>Trade-record integrity</td>
    <td>Direction outside long/short; invalid price; exit before entry; invalid timestamp.</td>
    <td>Fix source rows. Severity policy can surface row-level warnings; Ready requires valid canonical batch threshold.</td>
  </tr>
  <tr>
    <td>Cross-field dependency</td>
    <td>OHLCV fallback + Ignore context; fallback without Approved Market Data reference; profile mismatch.</td>
    <td>Align Price Source, OHLCV Use and approved market data dependency.</td>
  </tr>
  <tr>
    <td>Lifecycle / readiness</td>
    <td>Draft/rejected/deleted revision, stale Ready report, disabled item.</td>
    <td>Validate/save a Ready revision, restore via Admin, re-enable/pin if policy allows, rerun Ready Check.</td>
  </tr>
  <tr>
    <td>Authorization</td>
    <td>Caller not owner/Admin, root inaccessible, Agent attempts other owner mutation.</td>
    <td>Use/view may remain possible per policy; mutation rejected. Request owner/Admin action or create derived own output.</td>
  </tr>
  <tr>
    <td>Concurrency</td>
    <td>expected_head_revision_id or expected_row_version mismatch.</td>
    <td>Reload canonical state, compare/fork/merge as appropriate, retry with fresh expected_head_revision_id. Never last-write-wins.</td>
  </tr>
  <tr>
    <td>Async job failure</td>
    <td>Worker outage, parsing failure, object storage issue.</td>
    <td>Persistent failed job + error code/correlation id; safe retry with idempotency and no duplicate revision.</td>
  </tr>
  <tr>
    <td>Delete conflict</td>
    <td>Queued/running Backtest Run references root/revision.</td>
    <td>Wait for terminal run state or use run lifecycle control; then reattempt delete. Historical completed runs do not block eligible soft delete.</td>
  </tr>
</table>

## 12.1 Recommended machine-readable errors

<table>
  <tr>
    <th>Code</th>
    <th>HTTP family</th>
    <th>User-facing meaning</th>
    <th>Recovery action</th>
  </tr>
  <tr>
    <td>TRADE_LOG_NAME_REQUIRED</td>
    <td>422</td>
    <td>Trade Log Name is required.</td>
    <td>Enter a non-empty name.</td>
  </tr>
  <tr>
    <td>SOURCE_PROVIDER_REQUIRED</td>
    <td>422</td>
    <td>Source / Provider is required.</td>
    <td>Provide a source/provider description.</td>
  </tr>
  <tr>
    <td>SOURCE_FILE_REQUIRED</td>
    <td>422</td>
    <td>A TXT or CSV source file is required before validation.</td>
    <td>Choose/upload a supported file.</td>
  </tr>
  <tr>
    <td>UNSUPPORTED_SOURCE_FILE_TYPE</td>
    <td>422</td>
    <td>Only TXT and CSV source files are supported.</td>
    <td>Export or convert the source into TXT/CSV.</td>
  </tr>
  <tr>
    <td>REQUIRED_COLUMN_MISSING</td>
    <td>422</td>
    <td>Required trade-record columns are missing.</td>
    <td>Map or supply direction, entry_time, entry_price, exit_time and exit_price.</td>
  </tr>
  <tr>
    <td>TIME_ZONE_INVALID</td>
    <td>422</td>
    <td>The declared source time zone is invalid or ambiguous.</td>
    <td>Select a valid IANA zone or provide offset-aware timestamps.</td>
  </tr>
  <tr>
    <td>INSTRUMENT_MAPPING_REQUIRED</td>
    <td>422</td>
    <td>The file symbols cannot be mapped to the selected canonical instrument.</td>
    <td>Correct market scope/mapping or split mixed-symbol data.</td>
  </tr>
  <tr>
    <td>PRICE_CONTEXT_CONFLICT</td>
    <td>422</td>
    <td>The OHLCV fallback rule conflicts with OHLCV Use.</td>
    <td>Align Price Source and OHLCV Use, and select approved market data when required.</td>
  </tr>
  <tr>
    <td>TRADE_LOG_REVISION_CONFLICT</td>
    <td>409</td>
    <td>The Trade Log changed after this editor state was loaded.</td>
    <td>Reload/compare/fork and save from current head.</td>
  </tr>
  <tr>
    <td>ROW_VERSION_CONFLICT</td>
    <td>409</td>
    <td>The Mainboard item changed after you opened it.</td>
    <td>Reload item and explicitly repin/retry.</td>
  </tr>
  <tr>
    <td>OBJECT_NOT_ACTIVE</td>
    <td>409</td>
    <td>The selected Trade Log root or revision is deleted or inactive.</td>
    <td>Use active revision or ask Admin to restore.</td>
  </tr>
  <tr>
    <td>OBJECT_IN_ACTIVE_RUN</td>
    <td>409</td>
    <td>This Trade Log is used by a queued or running Backtest Run.</td>
    <td>Wait/cancel through run lifecycle, then retry deletion.</td>
  </tr>
  <tr>
    <td>ACCESS_DENIED</td>
    <td>403</td>
    <td>You do not have permission to modify this Trade Log.</td>
    <td>Use an allowed root or ask owner/Admin.</td>
  </tr>
</table>

# 13. Lifecycle, Versioning, Audit ve Trash Etkileri

## 13.1 Domain lifecycle ve deletion lifecycle ayrı tutulur

<table>
  <tr>
    <th>Aspect</th>
    <th>States / behavior</th>
    <th>Trade Log effect</th>
  </tr>
  <tr>
    <td>Domain lifecycle</td>
    <td>Draft -&gt; Imported -&gt; Parsed -&gt; Validated -&gt; Ready / Rejected -&gt; Soft Deleted</td>
    <td>Import/validation niteliğini ifade eder. Rejected revision Ready inputu olamaz; prior Ready revision historical olarak korunur.</td>
  </tr>
  <tr>
    <td>Deletion lifecycle</td>
    <td>active -&gt; soft_deleted -&gt; PURGE_PENDING -&gt; PURGED</td>
    <td>Teknik görünürlük ve restore/purge durumudur. Soft delete domain revision contentini yeniden yazmaz.</td>
  </tr>
  <tr>
    <td>Revision</td>
    <td>Revision 1, 2, 3... immutable</td>
    <td>Name, provider, mapping, source asset, records, price policy, capital, family or validation evidence change =&gt; new revision.</td>
  </tr>
  <tr>
    <td>Pin</td>
    <td>Mainboard item pinned_revision_id</td>
    <td>New head revision automatically selected değildir. Explicit pin changes composition hash.</td>
  </tr>
  <tr>
    <td>Historical run/result</td>
    <td>Immutable manifest references</td>
    <td>Completed run/result displays original Trade Log revision/source summary even after later revisions or soft delete.</td>
  </tr>
</table>

## 13.2 Required audit / event trail

<table>
  <tr>
    <th>Event</th>
    <th>Minimum payload / purpose</th>
  </tr>
  <tr>
    <td>TRADE_LOG_DRAFT_CREATED</td>
    <td>actor, root/draft ref, workspace context, correlation_id, provenance origin.</td>
  </tr>
  <tr>
    <td>TRADE_LOG_SOURCE_ASSET_UPLOADED</td>
    <td>actor, root ref, source asset id, raw_asset_hash, filename safe summary, correlation_id.</td>
  </tr>
  <tr>
    <td>TRADE_LOG_IMPORT_STARTED / COMPLETED / FAILED</td>
    <td>job id, source asset ref, mapping hash, parsed/skipped counts, error summary, correlation_id.</td>
  </tr>
  <tr>
    <td>TRADE_LOG_REVISION_CREATED</td>
    <td>root, prior head, new revision, content_hash, validation summary, actor, change note.</td>
  </tr>
  <tr>
    <td>MAINBOARD_ITEM_ATTACHED / REVISION_PINNED</td>
    <td>item id, root, old/new pinned revision, old/new composition hash, actor.</td>
  </tr>
  <tr>
    <td>READY_REPORT_STALE</td>
    <td>composition hash before/after and causation event when pin/enabled content changes.</td>
  </tr>
  <tr>
    <td>TRADE_LOG_EXPORT_REQUESTED / COMPLETED</td>
    <td>export artifact ref, requester, source revision, status; does not signal package creation.</td>
  </tr>
  <tr>
    <td>RESOURCE_SOFT_DELETED / RESTORED / PERMANENTLY_DELETED</td>
    <td>root id/type, owner, deleted_by/restored_by, Trash entry id, dependency snapshot, outcome.</td>
  </tr>
</table>

Audit payloadı full source-file content, credentials, tokens veya huge binary içermez. Audit event source asset / revision / report referanslarını taşır; detail gerektiğinde immutable evidence kayıtlarından okunur. Audit append-onlydir ve normal edit endpointleri ile mutate edilemez.

## 13.3 Delete / restore / purge rules

- Normal delete physical database delete değildir. Root lifecycle_state=soft_deleted, Trash Entry, audit event ve transactional outbox event aynı transactionda oluşur; dördünden biri başarısızsa delete success sayılmaz.

- Soft-deleted Trade Log active lists, selectors, newly created snapshots and Agent input catalogsından çıkar. Completed historical result/run manifest ilişkileri korunur.

- Restore yalnız Admindir. Restore same root id and current_revision_id ile ACTIVE stateine döner; yeni immutable revision üretmez.

- Purge otomatik çalışmaz. Adminin açık talebiyle asenkron retention/dependency workerı başlar; PURGE_PENDING sırasında restore/edit bloklanır. PURGED root restore edilemez, tombstone/audit identity korunur.

# 14. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Konu</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Terminology</td>
    <td>Row can display &quot;TRADE LOG PACKAGE&quot;; primary action says Save As Trade Log Package; export says Export As Package. [V18 legacy prototype label; Production domain/API type değildir.]</td>
    <td>Trade Log is external working object; no PackageKind=trade_log.</td>
    <td>All Production UI/API/DB labels use Trade Log. Export becomes Source Mapping / Provenance export artifact, not a Trade Log package.</td>
  </tr>
  <tr>
    <td>Creation</td>
    <td>Click creates DOM row and increments tradeLogCount.</td>
    <td>Transient draft may exist client-side; persisted root/revision only after server command.</td>
    <td>Add visible Unsaved badge; UUID root/item/revision generated server-side, never browser count.</td>
  </tr>
  <tr>
    <td>File import</td>
    <td>File chooser calls markTradingDataFileLoaded only.</td>
    <td>Upload asset and import/validation run as durable job; reports persisted.</td>
    <td>Do not promote client parser or file input value to canonical import evidence.</td>
  </tr>
  <tr>
    <td>Requiredness</td>
    <td>Only Initial Capital has visible *; Ready Check only checks source, file, capital.</td>
    <td>Name, provider, instrument, time model, timezone, price rule, OHLCV policy and file/import evidence required according to save/ready lifecycle.</td>
    <td>Production adds * and field errors; Save Draft remains permissive for incomplete state.</td>
  </tr>
  <tr>
    <td>Data model</td>
    <td>Market/Base TF/Timezone are free-text and Data Quality has simple select.</td>
    <td>Canonical instrument, typed time model, IANA zone, content profile and mapping hash persisted in immutable revision.</td>
    <td>Replace raw values with normalized selectors while preserving labels/intent.</td>
  </tr>
  <tr>
    <td>Clear</td>
    <td>Partially resets inputs and file; form may retain other values.</td>
    <td>Clears only unsaved local/draft edits, never deletes persisted revision or source asset.</td>
    <td>New draft: factory defaults. Persisted draft: last server draft. Prompt before discarding dirty input.</td>
  </tr>
  <tr>
    <td>Save and pin</td>
    <td>No bound save command or revision/pin separation.</td>
    <td>Save creates immutable revision; later pin is explicit and stales ready report.</td>
    <td>Initial valid save may attach revision 1 to originating board; later revision requires explicit Use This Revision on Mainboard.</td>
  </tr>
  <tr>
    <td>Delete</td>
    <td>Local row removal / prototype Trash helper.</td>
    <td>Delete preflight + soft delete + Trash/audit/outbox; active run dependency blocks.</td>
    <td>Confirm with canonical message; remove row only after backend success. Trash actions stay Admin-only.</td>
  </tr>
  <tr>
    <td>Info/help</td>
    <td>No Trade Log ⓘ controls.</td>
    <td>Decision-critical fields expose full help content.</td>
    <td>Add the cataloged ⓘ controls; V18 absence does not waive Handoff content standard.</td>
  </tr>
  <tr>
    <td>Dead bulk helper code</td>
    <td>HTML contains parsing/preview helper functions without visible rendered controls.</td>
    <td>Import job owns parse/report behavior.</td>
    <td>Do not reintroduce hidden paste/preview UI merely because unused prototype functions exist.</td>
  </tr>
</table>

# 15. Implementation Rules

1. Trade Logu Package Library package type, package_kind enum değeri veya "Trade Log Package" UI/endpoint labelı olarak modelleme. object_kind ve Mainboard item_kind yalnız trade_log olmalıdır. [V18 legacy prototype label; Production domain/API type değildir.]

2. Trade Log rootu, revisionu, source asseti, import reportu ve canonical record batchi ayrı kalıcı kayıtlarda tut; client form stateini veya DOMu source of truth kabul etme.

3. Her configuration/data meaning changeinde immutable Trade Log revision oluştur. Mevcut revision payloadını in-place UPDATE etme.

4. Every persisted Mainboard Trade Log item must carry referenced_root_id and exact pinned_revision_id. Latest/current revisiona implicit switch yapma.

5. TXT/CSV parsingi client-side preview helpera bağlama. Durable ingestion/validation worker, raw source asset hash, mapping hash, report ve retryable job state kullan.

6. Entry/exit record canonical minimum fieldleri direction, entry_time, entry_price, exit_time, exit_price olmadan Ready revision oluşturma. Invalid source rowsu sessizce normalleştirme veya kaybetme.

7. Timezone normalizationı explicit source zone/offset kuralıyla yap; source raw time ve canonical UTC timeı evidence için sakla.

8. Price Source OHLCV fallback seçildiğinde compatible Approved Market Data revision dependencysi zorunlu olsun. Source-file OHLCVyi primary Market Data yerine kabul etme.

9. Initial Capitalı yalnız shared Equity Allocation disabled iken required/active capital input olarak kullan. Allocation enabled olduğunda değeri koru fakat active run calculationına dahil etme.

10. Save/revision ve Mainboard pin commandlerini ayır. New revision, explicit pin olmadan existing board itemi değiştirmemeli; pin composition hash değiştirip readiness reportlarını stale yapmalıdır.

11. All mutating commands must use actor context, idempotency key and expected_head_revision_id or expected_row_version. Conflictte 409 ve canonical current state dön; last-write-wins yasaktır.

12. Expanded/collapsed detail stateini presentation preference olarak ele al. Bu action revision, audit, snapshot, engine evaluation veya Ready stateini değiştiremez.

13. Delete actionı soft delete + Trash entry + audit + outbox transactionı olmadan başarıyla dönme. Active queued/running run dependency varsa delete block et.

14. Agent için create/import/validate/save/pin/export/delete yeteneklerini Tool Gateway/API üzerinden sun. Browser automation, human login veya open UI Agentın ön koşulu olamaz.

15. Trade Log save/import/export actions never create a Backtest Result. Only a succeeded asynchronous Backtest Run creates immutable Backtest Result artifact.

16. Rationale Family shared-editing exceptionını Trade Log source file, revision veya ownership mutationına genişletme.

# 16. Acceptance Tests

<table>
  <tr>
    <th>ID</th>
    <th>Scenario</th>
    <th>Expected verifiable result</th>
  </tr>
  <tr>
    <td>TL-01</td>
    <td>Canonical type boundary</td>
    <td>Request attempts PackageKind=trade_log or GET /packages returns Trade Log as package. Server rejects/omits it; object_kind/item_kind=trade_log remains valid only as external work object/Mainboard item.</td>
  </tr>
  <tr>
    <td>TL-02</td>
    <td>Transient draft non-runnable</td>
    <td>New visible Trade Log row with no server root/revision is marked Unsaved and excluded from Ready Check/Run snapshot.</td>
  </tr>
  <tr>
    <td>TL-03</td>
    <td>Identity requiredness</td>
    <td>Validate/Save Ready with blank name or provider returns structured 422 field issue; no Ready revision or item pin is created.</td>
  </tr>
  <tr>
    <td>TL-04</td>
    <td>File requiredness</td>
    <td>Save Draft without file succeeds as Draft; Validate &amp; Save Ready without file returns SOURCE_FILE_REQUIRED.</td>
  </tr>
  <tr>
    <td>TL-05</td>
    <td>Canonical record schema</td>
    <td>Import missing direction/entry_time/entry_price/exit_time/exit_price returns REQUIRED_COLUMN_MISSING and yields no Ready revision.</td>
  </tr>
  <tr>
    <td>TL-06</td>
    <td>Delimiter support</td>
    <td>Comma, semicolon, tab and pipe source files parse through worker with equivalent canonical records; quoting-aware parser handles embedded delimiter per file rules.</td>
  </tr>
  <tr>
    <td>TL-07</td>
    <td>Timezone / time integrity</td>
    <td>Invalid timezone blocks import. A record exit_time before entry_time is reported with row number/reason and cannot silently become valid.</td>
  </tr>
  <tr>
    <td>TL-08</td>
    <td>Price integrity</td>
    <td>Zero/negative/non-finite entry or exit price is rejected. Reported P&amp;L mismatch produces non-destructive warning and preserves source-reported value.</td>
  </tr>
  <tr>
    <td>TL-09</td>
    <td>Instrument mapping</td>
    <td>Mixed BTCUSDT/ETHUSDT rows under one V1 single-instrument Trade Log block Ready status until split or mapping repair.</td>
  </tr>
  <tr>
    <td>TL-10</td>
    <td>OHLCV conflict</td>
    <td>Price Source=OHLCV Intrabar If Available + OHLCV Use=Ignore produces PRICE_CONTEXT_CONFLICT. Fallback without approved market-data ref blocks Ready.</td>
  </tr>
  <tr>
    <td>TL-11</td>
    <td>Capital conditionality</td>
    <td>Allocation disabled + blank/zero capital blocks Ready; Allocation enabled preserves independent capital but active run uses allocation snapshot.</td>
  </tr>
  <tr>
    <td>TL-12</td>
    <td>Revision immutability</td>
    <td>Changing provider/mapping/file/policy creates revision N+1; N content hash, source asset ref, completed run manifest remain unchanged.</td>
  </tr>
  <tr>
    <td>TL-13</td>
    <td>Explicit pin</td>
    <td>Saving new ready revision does not change existing board item pin. Explicit pin changes composition hash and stales prior readiness report.</td>
  </tr>
  <tr>
    <td>TL-14</td>
    <td>Import durability</td>
    <td>Upload/import returns durable job id. Browser refresh/logout/tab close does not cancel worker. UI can recover progress/result from job state.</td>
  </tr>
  <tr>
    <td>TL-15</td>
    <td>Idempotency</td>
    <td>Duplicate Upload/Import/Save/Pin call with same actor+key returns original canonical outcome and never creates duplicate source asset/revision/item/job.</td>
  </tr>
  <tr>
    <td>TL-16</td>
    <td>Concurrency</td>
    <td>Two editors use same expected head/row version. Exactly one write succeeds; other gets 409 conflict with server canonical state. No lost update.</td>
  </tr>
  <tr>
    <td>TL-17</td>
    <td>Authorization</td>
    <td>User/Supervisor/Agent cannot mutate other owner normal Trade Log. Admin can. Direct API call is blocked even if UI action was manipulated visible.</td>
  </tr>
  <tr>
    <td>TL-18</td>
    <td>Presentation state</td>
    <td>Expand/collapse changes no revision, no audit, no composition hash and no Ready report state.</td>
  </tr>
  <tr>
    <td>TL-19</td>
    <td>Delete preflight</td>
    <td>Attempt delete while queued/running backtest uses root/revision fails OBJECT_IN_ACTIVE_RUN and creates no Trash entry.</td>
  </tr>
  <tr>
    <td>TL-20</td>
    <td>Soft delete historical integrity</td>
    <td>Eligible delete removes active row/selectors, creates Trash/audit/outbox; completed historical Result still resolves original Trade Log revision/provenance from manifest.</td>
  </tr>
  <tr>
    <td>TL-21</td>
    <td>Trash restriction</td>
    <td>User, Supervisor and Agent direct Trash list/restore/purge calls denied; Admin restore returns same root/current revision without new revision.</td>
  </tr>
  <tr>
    <td>TL-22</td>
    <td>Agent parity</td>
    <td>Agent creates/imports/validates/saves/pins its Trade Log through Tool Gateway without browser; provenance task/checkpoint owner recorded, human Mainboard not auto-mutated.</td>
  </tr>
  <tr>
    <td>TL-23</td>
    <td>Run/result boundary</td>
    <td>Saving/importing/exporting a Trade Log creates no Backtest Result. Only succeeded async Backtest Run creates normal immutable Result; failed/cancelled Run does not.</td>
  </tr>
</table>

# 17. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Durum</th>
    <th>Sonuç / not</th>
  </tr>
  <tr>
    <td>Master authority</td>
    <td>Evet</td>
    <td>Modül 2 root/revision, Modül 3 Trash, Modül 7 package boundary, Modül 9 external work object/snapshot/pinning ve Modül 0/1 Agent-policy kuralları source of truth olarak uygulandı.</td>
  </tr>
  <tr>
    <td>Scope discipline</td>
    <td>Evet</td>
    <td>Bu belge Trade Log detail/import/revision lifecycleına odaklanır. Trading Signal, Add Outsource selector, Ready Check, Run/Result, Portfolio, Trash ve Package Library yalnız dependency sınırı kadar anıldı.</td>
  </tr>
  <tr>
    <td>Package boundary</td>
    <td>Evet</td>
    <td>Trade Log Package canonical type olarak anlatılmadı. V18 legacy labels visible behavior olarak kaydedildi ve Production alignment notu ile kaldırıldı.</td>
  </tr>
  <tr>
    <td>V18 vs Production</td>
    <td>Evet</td>
    <td>DOM counters, local file state, local readiness boolean, partial clear and unbound legacy buttons backend authorityden ayrıldı.</td>
  </tr>
  <tr>
    <td>Requiredness / content catalog</td>
    <td>Evet</td>
    <td>V18 defaults, Production * rules, conditional capital, import mapping and full ⓘ/helper/warning/toast/error textleri tanımlandı.</td>
  </tr>
  <tr>
    <td>Agent parity</td>
    <td>Evet</td>
    <td>Tool Gateway/API capability parity açıklandı; UI/browser/session dependency yasaklandı.</td>
  </tr>
  <tr>
    <td>Lifecycle / Trash</td>
    <td>Evet</td>
    <td>Soft delete, active-run blocker, Admin-only restore/purge, historical manifest and audit/outbox integrity tanımlandı.</td>
  </tr>
  <tr>
    <td>Run / Result boundary</td>
    <td>Evet</td>
    <td>Trade Log actionlarının Result üretmediği; yalnız succeeded Runın immutable Result ürettiği korundu.</td>
  </tr>
  <tr>
    <td>Non-canonical gap decisions identified</td>
    <td>Evet</td>
    <td>Production selectors, mapping UX, save/pin affordance, export form, info controls, source asset parsing/API semantic shapes Implementation Decision olarak ayrıldı.</td>
  </tr>
</table>

## 17.1 Implementation Decision Register

<table>
  <tr>
    <th>ID</th>
    <th>Karar</th>
    <th>Gerekçe / etki alanı</th>
  </tr>
  <tr>
    <td>ID-05-01</td>
    <td>Production Trade Log formu V18 raw Market/Base TF/Timezone inputlarını canonical instrument selector, typed event/bar model ve IANA timezone selector ile değiştirir.</td>
    <td>Master exact typed controlsü kilitlemez; reproducible source mapping ve timestamp normalization için serbest metin yetersizdir.</td>
  </tr>
  <tr>
    <td>ID-05-02</td>
    <td>V1 Trade Log single-instrument scope kullanır; mixed-symbol source files separate imports gerektirir.</td>
    <td>V18 panel tek Market alanı taşır; Multi-instrument portfolio ledger behavior ayrı kapsam/ileri sürüm olmalıdır.</td>
  </tr>
  <tr>
    <td>ID-05-03</td>
    <td>Production Save UI &quot;Save Draft&quot; + &quot;Validate &amp; Save Trade Log Revision&quot; + explicit &quot;Use This Revision on Mainboard&quot; olarak ayrılır.</td>
    <td>Master immutable revision ve explicit pin kuralını görünür UXe dönüştürür; legacy package labelı kaldırır.</td>
  </tr>
  <tr>
    <td>ID-05-04</td>
    <td>&quot;Export As Package&quot; yerine &quot;Export Source Mapping&quot; / provenance artifact üretilir; PackageKind=trade_log yaratılmaz.</td>
    <td>Master external root identity ile package boundaryyi korur; V18 legacy labelı canonical olmadığı için migration gerekir.</td>
  </tr>
  <tr>
    <td>ID-05-05</td>
    <td>Import mapping/delimiter parser quoting-aware server worker tarafından çalışır; row report/history immutable evidence olur. Source-file OHLCV contextual evidence olarak kalır; fallback only Approved Market Data revisiona bağlanır.</td>
    <td>V18 only guidance + dead client parser helper production ingestion authority olamaz; Market Data / execution ground semantic sınırı korunur.</td>
  </tr>
  <tr>
    <td>ID-05-06</td>
    <td>Production Trade Log paneline 12 ⓘ controls, import report paneli ve delete confirmation eklenir.</td>
    <td>Handoff information-content/recovery standardını karşılar; Master lifecycle/dependency davranışını kullanıcıya açık hale getirir.</td>
  </tr>
</table>
