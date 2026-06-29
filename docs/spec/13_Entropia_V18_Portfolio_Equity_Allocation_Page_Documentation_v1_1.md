---
title: "Entropia V18 — Portfolio / Equity Allocation Page Documentation v1.1"
page_number: 13
document_type: "Page implementation specification"
source_document: "Entropia_V18_Portfolio_Equity_Allocation_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Portfolio / Equity Allocation Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | SAYFA DOKÜMANTASYONU 13/22 | PORTFOLIO / EQUITY ALLOCATION
> **Original DOCX footer:** Canonical page documentation | Production V1 alignment |

ENTROPIA V18

PORTFOLIO / EQUITY ALLOCATION

Sayfa Dokümantasyonu 13/22 | Mainboard Composition içindeki opsiyonel shared capital pool, allocation sleeve, compounding ve immutable run snapshot sözleşmesi

<table>
  <tr>
    <th>Kilit canonical karar. Bu alanın tek canonical domain adı Portfolio Allocation Plan / Portfolio Allocation Plan Revisiondır. Plan bir Package, Rationale Family, global reusable allocation profile veya live portfolio hesabı değildir. V1de Mainboard Composition Draftının run-scoped parçasıdır; Backtest Run başladığında immutable manifest içinde pinlenir.</th>
  </tr>
</table>

# 0. Document Control, Scope ve Source Traceability

Bu belge yalnız Portfolio / Equity Allocation sayfasını açıklar. Mainboarddaki Strategy, Trading Signal ve Trade Log itemlerinin bağımsız initial capital ile mi, yoksa aynı backtest için ortak sermaye havuzundan mı çalışacağını tanımlar. Ready Check, RUN, Results veya Strategy Details ekranları burada yeniden dokümante edilmez; yalnız bu sayfanın onlarla olan açık domain bağlantısı belirtilir.

## 0.1 Source Traceability Map

<table>
  <tr>
    <th>Kaynak / referans</th>
    <th>Bu sayfadaki bağlayıcı kullanım</th>
    <th>Not</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 - Modül 11, §1-12; Canonical Integration CR-06 / CR-07</td>
    <td>Planın run-scoped niteliği, shared/independent mode, validation, engine flow, ownership, audit, API, immutable manifest ve canonical isimlendirme.</td>
    <td>Birincil canonical kaynak.</td>
  </tr>
  <tr>
    <td>Master - Modül 9 §8.2</td>
    <td>Allocation satırının display name değil stable Mainboard composition item kimliğiyle eşleşmesi.</td>
    <td>Strategy / Trading Signal / Trade Log item ayrımı korunur.</td>
  </tr>
  <tr>
    <td>Master - Modül 1-3, 12-13, 19-20</td>
    <td>Role policy, soft delete/Trash, Ready Check fingerprint, Backtest Run manifest, API/worker temel ilkeleri.</td>
    <td>Çapraz bağımlılık; bu sayfanın kapsamı değildir.</td>
  </tr>
  <tr>
    <td>V18 ana HTML - Mainboard menu &gt; Portfolio / Equity Allocation; renderPortfolioEquityAllocationPage</td>
    <td>Görünen panel, defaultlar, kartlar, alan adları, V18 preview/validation, + Add Item ve Sync davranışı.</td>
    <td>Production persistence/authorization doğrusu değildir.</td>
  </tr>
  <tr>
    <td>Handoff v1.1 §5-13 ve §11.1</td>
    <td>Sayfa şablonu, V18-Production ayrımı, Agent parity, test/lifecycle ve yalnız Portfolio Allocation Plan / Revision terimi.</td>
    <td>Belge üretim standardı.</td>
  </tr>
  <tr>
    <td>2.3 Position Entry Logic örneği</td>
    <td>Kavramı UI + backend + engine + Agent + acceptance test seviyesinde açıklama modeli.</td>
    <td>Teknik karar kaynağı değildir.</td>
  </tr>
</table>

## 0.2 Rule Provenance Register

<table>
  <tr>
    <th>Kural</th>
    <th>Provenance</th>
    <th>Uygulama sonucu</th>
  </tr>
  <tr>
    <td>Portfolio Allocation Plan / Revision terminolojisi</td>
    <td>Canonical Rule - CR-06</td>
    <td>allocation-profile, profile veya metric profile adı persisted entity olarak kullanılmaz.</td>
  </tr>
  <tr>
    <td>Equity Allocation default olarak kapalıdır ve valid independent moddur</td>
    <td>Canonical Rule + V18 Observation</td>
    <td>Toggle kapalıyken shared pool engine inputu değildir; itemlerin kendi Initial Capitalı doğrulanır.</td>
  </tr>
  <tr>
    <td>Allocation row = composition_item_id</td>
    <td>Canonical Rule</td>
    <td>Free-text item adı veya Type seçimi server payload kabulü değildir.</td>
  </tr>
  <tr>
    <td>Reserve Cash sabit nominal rezervdir</td>
    <td>Canonical Rule</td>
    <td>Compound modda yüzde her bar yeniden hesaplanmaz; R0 run başında sabitlenir.</td>
  </tr>
  <tr>
    <td>Visible Save düğmesi yoktur</td>
    <td>V18 Observation</td>
    <td>Production auto-save draft davranışı Implementation Decision olarak bu belgede açıkça tanımlanır.</td>
  </tr>
  <tr>
    <td>Production ⓘ alanları</td>
    <td>Implementation Decision</td>
    <td>V18de inline ⓘ yoktur; Initial Capital, Currency, Compounding, Reserve ve Allocation semantic alanları için erişilebilir yardım panelleri eklenir.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kapsam Sınırı

Portfolio / Equity Allocation, tekil itemlerin işlem mantığını değiştiren bir Strategy Details formu değildir. Aynı Mainboard Composition içindeki birden çok çalışma nesnesinin sermaye muhasebesini bir backtest bağlamında koordine eder. Toggle kapalıysa her enabled item kendi revisionında saklı Initial Capital ile bağımsız çalışır. Toggle açıksa shared capital pool, reserve, compounding mode ve item shareları yalnız o run için kullanılabilir sleeve capacity üretir.

## 1.1 Canonical kavramlar

<table>
  <tr>
    <th>Kavram</th>
    <th>Canonical anlam</th>
    <th>Yanlış yorum</th>
  </tr>
  <tr>
    <td>Portfolio Allocation Plan</td>
    <td>Bir Mainboard Compositiona bağlı shared pool/entry konfigürasyon rootu.</td>
    <td>Global yatırım hesabı, reusable template veya Package değildir.</td>
  </tr>
  <tr>
    <td>Portfolio Allocation Plan Revision</td>
    <td>Validated plan configinin immutable sürümü.</td>
    <td>Draftın son UI form değerleri değildir.</td>
  </tr>
  <tr>
    <td>Independent mode</td>
    <td>Allocation disabled; her active item kendi Initial Capitalıyla yürür.</td>
    <td>Not Ready veya eksik mod değildir.</td>
  </tr>
  <tr>
    <td>Shared equity pool</td>
    <td>Enabled planın Initial Capital - fixed Reserve Cash sonrasında dağıtılabilir sermayesi.</td>
    <td>Her itemin her zaman shareı kadar notional açacağı garanti değildir.</td>
  </tr>
  <tr>
    <td>Allocation sleeve</td>
    <td>Bir itemin shared pool içinde yeni entry/scale için erişebileceği üst capacity.</td>
    <td>Position Sizing, stop, leverage veya conflict rule yerine geçmez.</td>
  </tr>
  <tr>
    <td>Unallocated cash</td>
    <td>Active share toplamı 100den düşük olduğunda poolda boşta kalan sermaye.</td>
    <td>Reserve değildir; itemlere otomatik borrow/rebalance edilmez.</td>
  </tr>
  <tr>
    <td>Composition item</td>
    <td>Mainboard Working Itemın composition içindeki stable kaydı: strategy, trading_signal veya trade_log.</td>
    <td>Package kind değildir; Trading Signal/Trade Log Packagea dönüşmez. [V18 legacy prototype label; Production domain/API type değildir.]</td>
  </tr>
</table>

## 1.2 Sistem zincirindeki yeri

<table>
  <tr>
    <th>Mainboard Composition Draft<br/>  -&gt; Portfolio Allocation Draft (optional)<br/>  -&gt; Portfolio Allocation Plan Revision (only validated shared mode)<br/>  -&gt; Composition Snapshot + Readiness Report<br/>  -&gt; Backtest Run Manifest (allocation snapshot pinned)<br/>  -&gt; Backtest Run -&gt; succeeded only: immutable Backtest Result</th>
  </tr>
</table>

Bu zincirde planın değiştirilmesi, aktif veya tamamlanmış runın manifestini değiştiremez. Yeni allocation hipotezi yeni draft/revision ve yeni run gerektirir. Failed veya cancelled run normal Backtest Result üretmez; allocation snapshot sadece run manifesti ve diagnostic/artifact bağlamında kalabilir.

## 1.3 Kapsam dışı

<table>
  <tr>
    <th>Bu belgenin anlattığı</th>
    <th>Bu belgenin anlatmadığı</th>
  </tr>
  <tr>
    <td>Shared poolun kurulması, allocation rows, preview, validity, draft/revision, engine sleeve cap ve audit.</td>
    <td>Strategy giriş/çıkış/stop/sizing formunun tüm alanları; Strategy Details sayfası.</td>
  </tr>
  <tr>
    <td>Readinessin allocation yönünden başarısız/stale olma etkisi.</td>
    <td>Backtest Ready Check ekranının tam rapor/filter UIı.</td>
  </tr>
  <tr>
    <td>Run manifestte allocation snapshotının zorunlu metadata oluşu.</td>
    <td>RUN worker lifecyclei ve Result ekranının tam result/metric görünümü.</td>
  </tr>
  <tr>
    <td>Mainboard item seçicisiyle satır ilişkisinin domain sınırı.</td>
    <td>Add Outsource Signal, Trading Signal veya Trade Log detail schema/mapping UIı.</td>
  </tr>
</table>

# 2. Erişim, Görünürlük, Ownership ve Server-Side Policy

Frontendde menünün görünmesi veya inputun enabled olması yetki kanıtı değildir. Her query ve command, authenticated human session ya da trusted Agent runtime principalı; composition ownerı, visibility, lifecycle, expected_head_revision_id ve erişim izni üzerinden server-side değerlendirir.

## 2.1 Rol matrisi

<table>
  <tr>
    <th>Principal</th>
    <th>Sayfayı görme / planı okuma</th>
    <th>Draft oluşturma / değiştirme</th>
    <th>Validate / run request</th>
    <th>Trash / restore / purge</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Hayır; yalnız public/auth entry yüzeyleri.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Own / explicitly shared / published-use izinli composition bağlamında.</td>
    <td>Kendi compositionında; shared composition için explicit modify policy varsa.</td>
    <td>Kendi yetkili compositionında.</td>
    <td>Hayır.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Tüm erişilebilir shared working compositionlar.</td>
    <td>Yalnız kendi compositionı; başka ownerın planını mutate edemez.</td>
    <td>Kendi yetkili compositionında.</td>
    <td>Hayır.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm compositionlar ve planlar.</td>
    <td>Tüm planları yönetebilir; server lifecycle kurallarını atlayamaz.</td>
    <td>Yetkili tüm compositionlarda.</td>
    <td>Yalnız Admin.</td>
  </tr>
  <tr>
    <td>Agent runtime</td>
    <td>Policy ile erişebildiği composition/read model; human login değildir.</td>
    <td>Yalnız kendi ürettiği composition/planı günceller; shared/published kaynakları kendi compositionında kullanabilir.</td>
    <td>Kendi policy kapsamındaki configi validate/snapshot/run request edebilir.</td>
    <td>Hayır; Agent Trashı görmez/restore/purge edemez.</td>
  </tr>
</table>

## 2.2 Server-side authorization değerlendirme sırası

1. Principalı çöz: human için canonical session context; Agent için trusted service/runtime identity. Client bodydeki role, owner veya isAdmin alanını otorite kabul etme.

2. Operationı sınıflandır: view, edit_draft, sync, validate, create_revision, soft_delete, restore, permanently_delete veya start_run.

3. Target Mainboard Composition, Portfolio Allocation Plan, draft/revision ve item referanslarını yükle; owner, visibility, lifecycle, deletion state, row_version ve manifest pins kontrol et.

4. Normal role/ownership policyyi uygula. Rationale Families global shared-editing exceptionı bu plana uygulanmaz.

5. İzin yoksa mutasyon başlatmadan ACCESS_DENIED, OWNER_REQUIRED veya uygun lifecycle/dependency errorunu dön; client optimistic stateini kalıcı sayma.

6. İzin varsa transaction içinde mutation + audit/outbox event yaz; asynchronous work varsa stable job/run kimliği döndür.

# 3. V18 Interface Behavior: Görünür Yerleşim ve Bileşen Envanteri

V18de sayfa Mainboard menüsü altındaki `Portfolio / Equity Allocation` iteminden açılır. Page title `PORTFOLIO / EQUITY ALLOCATION`dır. Panel maksimum yaklaşık 1180px genişlikte, beyaz kartlardan oluşan tek akışlı bir çalışma alanıdır. V18de bu sayfada inline ⓘ butonu, arama toolbarı, pagination veya gerçek backend modalı yoktur.

## 3.1 Üst toggle ve durum notu

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 davranışı</th>
    <th>Görünme / enabled koşulu</th>
  </tr>
  <tr>
    <td>USE EQUITY ALLOCATION FOR THIS BACKTEST</td>
    <td>Checkbox. Başlangıç değeri false. Açıkken shared pool/rows/preview/check kullanılır; kapalıyken independent mode geçerlidir.</td>
    <td>Her zaman görünür ve tıklanabilir.</td>
  </tr>
  <tr>
    <td>Mode note</td>
    <td>Kapalı: “Equity Allocation is not selected...” Açık: “Equity Allocation is active...” metni.</td>
    <td>Her zaman görünür; toggle stateine göre metin değişir.</td>
  </tr>
  <tr>
    <td>Equity allocation workspace</td>
    <td>4 kart: Shared Capital Pool, Equity Allocation, Calculation Preview, Allocation Check.</td>
    <td>Toggle false iken opacity .42, grayscale ve pointer-events none ile soluk/disabled; toggle haricindeki kontroller input kabul etmez.</td>
  </tr>
  <tr>
    <td>Page actions</td>
    <td>+ Add Item ve Sync From Mainboard.</td>
    <td>Yalnız enabled shared mode içinde çalışır.</td>
  </tr>
  <tr>
    <td>Modal/popup</td>
    <td>V18de yok.</td>
    <td>Productionda Add Item picker ve destructive sync confirmation gerekir; aşağıda ayrı tanımlanmıştır.</td>
  </tr>
</table>

## 3.2 Kartlar ve row layout

<table>
  <tr>
    <th>Kart / alan</th>
    <th>V18 görünür içerik</th>
    <th>Production yorum</th>
  </tr>
  <tr>
    <td>1. SHARED CAPITAL POOL</td>
    <td>Initial Capital*, Base Currency, Compounding Mode*, Reserve Cash.</td>
    <td>Shared mode configinin editable draft alanları.</td>
  </tr>
  <tr>
    <td>2. EQUITY ALLOCATION</td>
    <td>Header: Active, Item, Type, Equity Share, Capital, Sizing Base, remove. Altında allocation rows.</td>
    <td>Item/Type free-text/select demo görünümüdür; productionda composition item picker + immutable derived type.</td>
  </tr>
  <tr>
    <td>3. CALCULATION PREVIEW</td>
    <td>Portfolio Initial Capital, Reserved Cash, Capital Available, Total Allocated, Unallocated; example note.</td>
    <td>Derived/read-only preview; server validate response ile eşleşmelidir.</td>
  </tr>
  <tr>
    <td>4. ALLOCATION CHECK</td>
    <td>READY FOR BACKTEST / NOT READY / NOT SELECTED ve issue listesi.</td>
    <td>Client statüsü bilgilendiricidir; server Ready Check/run preflight doğrusu değildir.</td>
  </tr>
</table>

## 3.3 V18 default state ve fallback rows

<table>
  <tr>
    <th>State</th>
    <th>V18 default / davranış</th>
    <th>Production Alignment</th>
  </tr>
  <tr>
    <td>equityAllocationEnabled</td>
    <td>false.</td>
    <td>Canonical independent mode; valid configuration.</td>
  </tr>
  <tr>
    <td>Initial Capital</td>
    <td>10000.</td>
    <td>Enabled shared mode için decimal &gt; 0 zorunlu.</td>
  </tr>
  <tr>
    <td>Base Currency</td>
    <td>USDT. Dropdown: USD, USDT, EUR, TRY.</td>
    <td>Enabled shared mode için canonical currency code zorunlu; V1 fixed enum set bu dört seçenek olabilir.</td>
  </tr>
  <tr>
    <td>Compounding Mode</td>
    <td>Compound Portfolio Equity.</td>
    <td>Dropdown yalnız Compound Portfolio Equity ve Fixed Initial Portfolio Capital.</td>
  </tr>
  <tr>
    <td>Reserve Cash</td>
    <td>0; V18 input labelında % görünmez, fakat percent olarak parse edilir.</td>
    <td>Production labelı `Reserve Cash (%)` veya görünür % suffixi taşımalıdır.</td>
  </tr>
  <tr>
    <td>Rows: Mainboard varsa</td>
    <td>Mainboard DOMundan name/type/initial capital okunur.</td>
    <td>Backend Composition Draft querysinden stable composition_item_id ile gelir.</td>
  </tr>
  <tr>
    <td>Rows: Mainboard boşsa fallback</td>
    <td>Strategy 1 %40, Strategy 2 %30, Copy Signal A %20, Imported Trade Log Example %10.</td>
    <td>Demo fallback persisted plan veya run inputu değildir; production empty state gösterir.</td>
  </tr>
</table>

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen</th>
    <th>Default</th>
    <th>Aktifleşme koşulu</th>
    <th>Disabled / payload / engine etkisi</th>
  </tr>
  <tr>
    <td>Allocation mode toggle</td>
    <td>false / independent.</td>
    <td>User veya Agent draftta enabled=true seçer.</td>
    <td>false iken shared fields/entries stored draftta kalabilir, fakat engine ve enabled validation bunları okumaz; manifest `enabled=false` taşır.</td>
  </tr>
  <tr>
    <td>Shared Capital Pool fields</td>
    <td>Görünür, fakat false modda disabled/faded.</td>
    <td>enabled=true.</td>
    <td>No input; payloadta preserve edilebilir ama allocation execution inputu değildir.</td>
  </tr>
  <tr>
    <td>Allocation rows</td>
    <td>V18de görünür, false modda disabled.</td>
    <td>enabled=true.</td>
    <td>No input; active/share values engine dışıdır. Independent resolver item Initial Capital kullanır.</td>
  </tr>
  <tr>
    <td>Calculation Preview</td>
    <td>False modda “Not in use”.</td>
    <td>enabled=true ve UI config renderı.</td>
    <td>Derived values allocation physicsi değil previewdir; authoritative hesap server validate/run snapshotından gelir.</td>
  </tr>
  <tr>
    <td>Allocation Check</td>
    <td>False modda NOT SELECTED.</td>
    <td>enabled=true ise local preflight hesaplar.</td>
    <td>Green READY yalnız client hint; server aynı kontrolü run öncesi yeniden yapar.</td>
  </tr>
  <tr>
    <td>+ Add Item</td>
    <td>Disabled.</td>
    <td>enabled=true ve compatible unrepresented item vardır.</td>
    <td>Productionda picker açar; free-text row eklemez.</td>
  </tr>
  <tr>
    <td>Sync From Mainboard</td>
    <td>Disabled.</td>
    <td>enabled=true.</td>
    <td>Production merge preview üretir; destructive overwrite confirmation token olmadan uygulanmaz.</td>
  </tr>
  <tr>
    <td>Draft save indicator</td>
    <td>V18de yok.</td>
    <td>Production auto-save draft aktifse.</td>
    <td>Saving / Saved / Save failed; unsaved client state source-of-truth değildir.</td>
  </tr>
  <tr>
    <td>Stale readiness indicator</td>
    <td>V18de bu sayfada yok.</td>
    <td>Allocation-affecting change sonrası.</td>
    <td>Current readiness fingerprint invalid; Run tekrar preflight yapmadan başlamaz.</td>
  </tr>
</table>

## 4.1 Dependent field preservation ve reset kuralları

<table>
  <tr>
    <th>Değişiklik</th>
    <th>Draft state davranışı</th>
    <th>Ready / engine sonucu</th>
  </tr>
  <tr>
    <td>enabled true -&gt; false</td>
    <td>Initial Capital, currency, mode, reserve, entries draftta korunabilir; workspace disabled olur.</td>
    <td>Allocation validation issueları kalkar; independent Initial Capital validationı devreye girer.</td>
  </tr>
  <tr>
    <td>enabled false -&gt; true</td>
    <td>Korunmuş değerler yeniden görünür; boş/invalid state otomatik valid kabul edilmez.</td>
    <td>Shared-mode validation tekrar çalışır; invalid fields blocker olur.</td>
  </tr>
  <tr>
    <td>Base Currency değişir</td>
    <td>Mevcut derived preview stale; currency conversion dependency yeniden çözülür.</td>
    <td>Pinned FX conversion yoksa blocker; old readiness stale.</td>
  </tr>
  <tr>
    <td>Compounding Mode değişir</td>
    <td>Rows/share korunur; preview semanticsi ve next-run manifest değişir.</td>
    <td>Current readiness stale; historical run değişmez.</td>
  </tr>
  <tr>
    <td>Reserve / Initial Capital değişir</td>
    <td>Entries korunur; all derived amountlar yeniden hesaplanır.</td>
    <td>Current readiness stale; enabled plan yeni validation ister.</td>
  </tr>
  <tr>
    <td>Composition item remove/soft delete</td>
    <td>Entry stale/orphaned olarak işaretlenir; UI rowu sessizce başka iteme bağlanmaz.</td>
    <td>Validation blocker: item reference unavailable. User picker/sync ile açık çözüm yapar.</td>
  </tr>
  <tr>
    <td>Sync From Mainboard</td>
    <td>V18 rowsu eşit share ile replace eder.</td>
    <td>Production preview; retained/missing/new entries gösterilir. Confirm edilmeden draft mutate edilmez.</td>
  </tr>
  <tr>
    <td>Remove allocation row</td>
    <td>Sadece plan entrysi silinir; source Mainboard Working Item silinmez.</td>
    <td>Enabled modda active entry sayısı / share toplamı yeniden doğrulanır.</td>
  </tr>
</table>

# 5. Field Contract Matrix

Yıldız `*`, yalnız görsel ipucu değildir: frontend, API schema, allocation validation, Ready Check ve Agent tool inputu aynı zorunluluğu uygular. V18de yıldız sadece Initial Capital ve Compounding Mode yanında görünür. Production V1de shared mode bağlamında Base Currency de zorunlu semantic input olduğundan `*` ile işaretlenir.

## 5.1 Shared Capital Pool

<table>
  <tr>
    <th>Alan / V18 UI</th>
    <th>V18 default ve seçenekler</th>
    <th>Zorunluluk</th>
    <th>Production payload</th>
    <th>Validation / dependency</th>
  </tr>
  <tr>
    <td>Use Equity Allocation for This Backtest | checkbox</td>
    <td>false; true/false.</td>
    <td>Always required boolean; default false.</td>
    <td>enabled: boolean</td>
    <td>false: independent resolver. true: shared mode validation gerekir.</td>
  </tr>
  <tr>
    <td>Initial Capital * | text/number input</td>
    <td>10000.</td>
    <td>enabled=true iken required; disabled modda allocation için required değildir.</td>
    <td>initial_capital.amount: decimal string; initial_capital.currency ile Money.</td>
    <td>&gt; 0; parseable decimal; binary float persist edilmez.</td>
  </tr>
  <tr>
    <td>Base Currency | select</td>
    <td>USDT. USD / USDT / EUR / TRY.</td>
    <td>enabled=true iken conditionally required; Production UIda *.</td>
    <td>initial_capital.currency: enum/string</td>
    <td>Item settlement currency aynı olmalı veya approved/pinned FX conversion dataset bulunmalı.</td>
  </tr>
  <tr>
    <td>Compounding Mode * | select</td>
    <td>Compound Portfolio Equity; Fixed Initial Portfolio Capital.</td>
    <td>enabled=true iken required.</td>
    <td>compounding_mode: COMPOUND_PORTFOLIO_EQUITY | FIXED_INITIAL_PORTFOLIO_CAPITAL</td>
    <td>Unknown/empty enum blocker. `Fixed Item Notional` V1 option değildir.</td>
  </tr>
  <tr>
    <td>Reserve Cash | text/number input</td>
    <td>0; percent olarak parse edilir.</td>
    <td>Optional; enabled=true ise default 0.</td>
    <td>reserve_cash_percent: decimal string</td>
    <td>0 &lt;= reserve &lt; 100. Reserve = P0*r; fixed nominal R0; every bar percentage reapply edilmez.</td>
  </tr>
</table>

## 5.2 Equity Allocation row

<table>
  <tr>
    <th>Alan / V18 UI</th>
    <th>V18 davranışı</th>
    <th>Production payload / source</th>
    <th>Requiredness / validation</th>
  </tr>
  <tr>
    <td>Active | checkbox</td>
    <td>New/fallback rows true.</td>
    <td>entries[].active: boolean.</td>
    <td>Shared mode içinde active entry yoksa blocker.</td>
  </tr>
  <tr>
    <td>Item | free-text input</td>
    <td>V18de name yazılabilir.</td>
    <td>entries[].composition_item_id; production pickerdan gelir. display name yalnız read model/snapshot.</td>
    <td>active=true iken required; selected item current compositionda, erişilebilir, non-deleted ve compatible olmalı.</td>
  </tr>
  <tr>
    <td>Type | select</td>
    <td>Strategy / Trading Signal / Trade Log.</td>
    <td>Derived item_type veya picker presentation; client source-of-truth değildir.</td>
    <td>User edit yapamaz. Server composition item type ile eşleşmeyen payloadu reddeder.</td>
  </tr>
  <tr>
    <td>Equity Share % | input</td>
    <td>Blank olabilir; active row inputu.</td>
    <td>entries[].equity_share_percent: decimal string.</td>
    <td>active=true iken &gt;0; active total &lt;=100. &lt;100 warning; inactive row share engine dışı.</td>
  </tr>
  <tr>
    <td>Capital | readonly input</td>
    <td>Available capital * row share / 100.</td>
    <td>Derived validate/run output: initial_sleeve_capital.</td>
    <td>User-editable değildir. Preview string engine inputu değildir.</td>
  </tr>
  <tr>
    <td>Sizing Base | readonly</td>
    <td>V18: `Allocation`.</td>
    <td>Derived semantic: allocation sleeve cap.</td>
    <td>Position sizing method değildir; Strategy Details desired size üretir, allocation outer cap uygular.</td>
  </tr>
  <tr>
    <td>× remove | button</td>
    <td>Rowu DOMdan kaldırır.</td>
    <td>remove_plan_entry command / draft patch.</td>
    <td>Source Working Itemi silmez. At least one active entry rule subsequent validationda uygulanır.</td>
  </tr>
</table>

## 5.3 Calculation Preview ve Allocation Check

<table>
  <tr>
    <th>Alan</th>
    <th>V18 state</th>
    <th>Canonical derived value / UI kuralı</th>
  </tr>
  <tr>
    <td>Portfolio Initial Capital</td>
    <td>enabled=false: Not in use; enabled=true: formatted amount + currency.</td>
    <td>P0 = canonical initial capital. Read-only; source field değildir.</td>
  </tr>
  <tr>
    <td>Reserved Cash</td>
    <td>enabled=false: Not in use.</td>
    <td>R0 = P0 * reserve_cash_percent / 100. Fixed nominal reserve; run manifestte decimal olarak pinlenir.</td>
  </tr>
  <tr>
    <td>Capital Available</td>
    <td>enabled=false: Not in use.</td>
    <td>A0 = max(0, P0 - R0). Shared planın başlangıç allocatable poolu.</td>
  </tr>
  <tr>
    <td>Total Allocated</td>
    <td>enabled=true: sum sleeve capitals.</td>
    <td>sum(Ci0) only active entries; total share &lt;=100.</td>
  </tr>
  <tr>
    <td>Unallocated</td>
    <td>enabled=true: A0 - Total Allocated.</td>
    <td>U0; warning olabilir, automatic borrowing/reallocation yoktur.</td>
  </tr>
  <tr>
    <td>Example note</td>
    <td>First active rowun allocation örneği.</td>
    <td>Production note selected/first active item için server derived preview ile tam eşleşmeli.</td>
  </tr>
  <tr>
    <td>Allocation Check</td>
    <td>V18 local READY/NOT READY/NOT SELECTED.</td>
    <td>Production server validation report issue list, warnings, derived preview and report id ile render edilir.</td>
  </tr>
</table>

# 6. Information Content Catalog: ⓘ, Helper, Warning, Toast ve Error Metinleri

V18 Allocation panelinde alan yanına yerleştirilmiş inline ⓘ butonu render edilmemektedir. Buna rağmen semantik finans alanlarında hata riskini azaltmak için aşağıdaki beş Production UI info paneli Implementation Decision olarak eklenir. Global info-text registrydeki eski `Fixed Item Notional` açıklaması bu sayfada kullanılmaz; V1 dropdownunda bu seçenek yoktur.

## 6.1 Production ⓘ panel metinleri

<table>
  <tr>
    <th>Info key / alan</th>
    <th>Panel başlığı</th>
    <th>UIya doğrudan yerleştirilecek nihai metin</th>
  </tr>
  <tr>
    <td>allocationModeInfo / Use Equity Allocation</td>
    <td>Use Equity Allocation for This Backtest</td>
    <td>Bu seçenek kapalıyken her aktif Strategy, Trading Signal ve Trade Log kendi details alanındaki Initial Capital ile bağımsız yürür.<br/><br/>Açıkken tüm aktif allocation satırları tek bir shared capital pooldan kendi Equity Share oranlarıyla sleeve alır. Bu seçim yalnız mevcut ve sonraki Backtest Run snapshotları için geçerlidir; geçmiş runları değiştirmez.<br/><br/>Not: Allocation, Trading Signal veya Trade Logu Packagea dönüştürmez. Bunlar Mainboard Working Item olarak kalır.</td>
  </tr>
  <tr>
    <td>portfolioInitialCapitalInfo / Initial Capital</td>
    <td>Shared Portfolio Initial Capital</td>
    <td>Shared mode açıkken bu değer portföyün başlangıç sermayesidir. Reserve Cash ayrıldıktan sonra kalan tutar, aktif allocation satırlarının Equity Share oranlarıyla sleeve cap olarak bölünür.<br/><br/>Bu değer itemlerin kendi Initial Capital alanlarını silmez. Sadece allocation açık olan Backtest Run için engine sizing baseini değiştirir.<br/><br/>Örnek: 10,000 USDT ve %10 reserve ile dağıtılabilir tutar 9,000 USDTdir. %40 share alan itemin başlangıç sleeve capi 3,600 USDT olur.</td>
  </tr>
  <tr>
    <td>portfolioCurrencyInfo / Base Currency</td>
    <td>Base Currency and Conversion</td>
    <td>Base Currency, shared poolun ve portfolio ledgerın hesap para birimidir. Her itemin settlement currencysi aynı olmalı veya run manifestine pinlenmiş onaylı FX conversion dataset bulunmalıdır.<br/><br/>Sistem sessiz kur çevirimi yapmaz. Uyumlu conversion kaynağı yoksa Ready Check ve run preflight blocker üretir.</td>
  </tr>
  <tr>
    <td>portfolioCompoundingInfo / Compounding Mode</td>
    <td>Compounding Mode</td>
    <td>Compound Portfolio Equity: Her deterministik valuation pointte, fixed nominal reserve düşüldükten sonraki current portfolio equity üzerinden yeni entry ve scale-in için sleeve capler yeniden hesaplanır. Aynı timestampte tüm itemler aynı valuation snapshotını görür.<br/><br/>Fixed Initial Portfolio Capital: Run başlangıcındaki sleeve capler sizing base olarak sabit kalır. PnL, fee ve funding ledgera yazılır fakat kazançlar yeni trade boyutunu otomatik büyütmez.<br/><br/>Bu alan yalnız yeni entry/scale kararlarını etkiler; açık pozisyonlar equity değişti diye zorla rebalance edilmez.</td>
  </tr>
  <tr>
    <td>portfolioReserveInfo / Reserve Cash</td>
    <td>Reserve Cash</td>
    <td>Reserve Cash, Initial Capitalın yüzdesinden run başlangıcında bir kez hesaplanan ve sabit nominal tutar olarak tutulan sermayedir. Aktif itemler bu tutarı kullanamaz.<br/><br/>Reserve oranı her barda current equitye yeniden uygulanmaz. %10 reserve ve 10,000 USDT başlangıç sermayesinde reserve 1,000 USDT olarak kalır.</td>
  </tr>
  <tr>
    <td>allocationShareInfo / Equity Share</td>
    <td>Equity Share</td>
    <td>Equity Share, toplam dağıtılabilir shared capitalın bir itema ayrılan oranıdır. Bu alan tek bir tradein pozisyon büyüklüğü değildir. Strategy Details önce kendi desired sizeini üretir; Allocation engine bu talebi itemin kalan sleeve capacitysiyle sınırlar.<br/><br/>Active share toplamı %100ü geçemez. %100den düşük toplam kabul edilir; fark unallocated cash olarak boşta kalır ve başka itemler tarafından otomatik kullanılmaz.</td>
  </tr>
</table>

## 6.2 Helper, warning, toast, empty-state ve error metinleri

<table>
  <tr>
    <th>Tür / tetikleyici</th>
    <th>Nihai metin</th>
  </tr>
  <tr>
    <td>Helper - Item picker</td>
    <td>Bu compositionda allocation satırı olmayan bir Mainboard item seçin. Strategy, Trading Signal ve Trade Log ayrı Package türleri değildir; yalnız bu run için sermaye sleevei alabilir.</td>
  </tr>
  <tr>
    <td>Empty state - composition boş</td>
    <td>Allocation için Mainboardda compatible item bulunmuyor. Önce Strategy, Trading Signal veya Trade Log working item ekleyin.</td>
  </tr>
  <tr>
    <td>Empty state - no unrepresented items</td>
    <td>Bu compositiondaki tüm compatible itemler zaten allocation planında. Yeni satır eklemek için mevcut satırı kaldırın veya Mainboard compositionı değiştirin.</td>
  </tr>
  <tr>
    <td>Warning - share &lt; 100</td>
    <td>%{share_total} aktif share tanımlandı. Kalan %{unallocated_percent} dağıtılmadan kalacak ve hiçbir item tarafından otomatik kullanılmayacak.</td>
  </tr>
  <tr>
    <td>Warning - one active sleeve</td>
    <td>Shared allocation yalnız bir aktif sleeve içeriyor. Bu geçerlidir; ancak portfolio-level dağıtım etkisi sınırlı olacaktır.</td>
  </tr>
  <tr>
    <td>Warning - own Initial Capital differs</td>
    <td>Shared allocation açık. Itemin own Initial Capital değeri bu run için kullanılmayacak; independent runlarda korunacaktır.</td>
  </tr>
  <tr>
    <td>Toast - draft saved</td>
    <td>Portfolio allocation draft saved.</td>
  </tr>
  <tr>
    <td>Toast - sync preview ready</td>
    <td>Mainboard changes were compared. Review the allocation merge before applying it.</td>
  </tr>
  <tr>
    <td>Toast - plan revision created</td>
    <td>Portfolio Allocation Plan Revision {revision_id} was created and is ready for snapshotting.</td>
  </tr>
  <tr>
    <td>Error - active item has zero share</td>
    <td>{item_name} is active but Equity Share must be greater than 0.</td>
  </tr>
  <tr>
    <td>Error - duplicate entry</td>
    <td>{item_name} already has an active allocation row. An item can have only one active sleeve in V1.</td>
  </tr>
  <tr>
    <td>Error - total share</td>
    <td>Total allocation is {share_total}%; it cannot exceed 100%.</td>
  </tr>
  <tr>
    <td>Error - item unavailable</td>
    <td>The selected Mainboard item is unavailable, deleted, or no longer belongs to this composition. Select a current compatible item.</td>
  </tr>
  <tr>
    <td>Error - FX dependency</td>
    <td>Base Currency differs from an item settlement currency and no approved pinned FX conversion dataset is available.</td>
  </tr>
  <tr>
    <td>Error - stale conflict</td>
    <td>This allocation draft changed elsewhere. Refresh the current draft, compare changes, then reapply your update.</td>
  </tr>
</table>

# 7. Buttons, Commands ve State Davranışı

<table>
  <tr>
    <th>UI action</th>
    <th>Production command / precondition</th>
    <th>Loading / success / error / audit</th>
  </tr>
  <tr>
    <td>Toggle mode</td>
    <td>PUT portfolio-allocation-draft patch `{enabled}` with expected_row_version.</td>
    <td>Local state may update optimistically but rehydrates from response. Saving state shown. Audit: allocation_enabled_changed; Ready fingerprint stale.</td>
  </tr>
  <tr>
    <td>Edit pool field / row</td>
    <td>Debounced PUT draft patch; expected_row_version + idempotency_key.</td>
    <td>Saving -&gt; Saved. 409 CONFLICT stops local overwrite and shows compare/reapply. Audit field diff or entry change.</td>
  </tr>
  <tr>
    <td>+ Add Item</td>
    <td>Open `Add Allocation Item` picker. Precondition: enabled=true; candidate is compatible, accessible, current composition member, no active entry.</td>
    <td>No candidate -&gt; empty state. Selection adds draft entry, server validates, writes audit.</td>
  </tr>
  <tr>
    <td>Remove row ×</td>
    <td>PATCH/remove entry. Precondition: user may edit plan.</td>
    <td>Removes allocation entry only; source item remains. Validation may later report no active row.</td>
  </tr>
  <tr>
    <td>Sync From Mainboard</td>
    <td>POST portfolio-allocation/sync. Precondition: enabled=true.</td>
    <td>Returns merge preview. If replacement/removal occurs, require confirmation token. Apply success invalidates readiness and audits sync source.</td>
  </tr>
  <tr>
    <td>Validate Allocation</td>
    <td>POST portfolio-allocation/validate. Precondition: current draft saved or server merges submitted validated payload.</td>
    <td>Loading spinner; returns immutable validation_report_id, errors/warnings and derived amounts. No Backtest Run created.</td>
  </tr>
  <tr>
    <td>Create Plan Revision</td>
    <td>POST portfolio-allocation/revisions. Precondition: validated draft; no blockers; expected_row_version.</td>
    <td>Returns immutable plan revision + config hash. 422 if invalid; 409 if stale; audit plan_revision_created.</td>
  </tr>
  <tr>
    <td>Run / Ready controls outside this page</td>
    <td>Other page commands consume this page state.</td>
    <td>They must server-revalidate the allocation snapshot. A green local check cannot bypass validation or create a job.</td>
  </tr>
</table>

## 7.1 Implementation Decision: draft persistence without a visible V18 Save button

<table>
  <tr>
    <th>Implementation Decision - Non-Canonical Gap Resolution. V18de Save button olmadığı için Production V1, edit field blurundan veya 750ms debounce sonrasında `PUT /mainboard-compositions/{id}/portfolio-allocation-draft` çağıran visible autosave state kullanır: `Saving`, `Saved`, `Save failed`, `Conflict`. Bu yalnız mutable draftı kaydeder. Immutable Portfolio Allocation Plan Revision yalnız validationdan geçen drafttan açık command ile veya canonical run-snapshot flowunda üretilir. Browser memory veya localStorage canonical draft değildir.</th>
  </tr>
</table>

## 7.2 Command idempotency ve concurrency contract

Mutating commandlar `expected_row_version` taşır; HTTP transportta ETag/If-Match kullanılabilir fakat domain concurrency değeriyle aynı isimde saklanmaz. Long-running veya retryable commands `idempotency_key` taşır. Aynı semantic request duplicate draft mutation, plan revision veya run yaratmamalıdır.

<table>
  <tr>
    <th>PUT /mainboard-compositions/{composition_id}/portfolio-allocation-draft<br/>Headers: If-Match: &quot;etag...&quot;<br/>Body: { expected_row_version, idempotency_key, enabled, initial_capital, compounding_mode, reserve_cash_percent, entries[] }<br/>Success: { draft, row_version, inline_issues[], readiness_invalidated: true }<br/>Conflict: 409 { code: &quot;CONFLICT&quot;, current_draft, changed_paths[] }</th>
  </tr>
</table>

# 8. Production Backend ve Domain Behavior

## 8.1 Persistent domain model

<table>
  <tr>
    <th>Katman</th>
    <th>Mutable?</th>
    <th>Sorumluluk</th>
    <th>Backtestte kullanımı</th>
  </tr>
  <tr>
    <td>Mainboard Composition Draft</td>
    <td>Evet</td>
    <td>Working item listesi, order, config ve mutable allocation draft bağlamı.</td>
    <td>Doğrudan kullanılmaz.</td>
  </tr>
  <tr>
    <td>PortfolioAllocationPlan root</td>
    <td>Controlled lifecycle</td>
    <td>Compositiona bağlı plan identity, owner/composition ref, deletion metadata.</td>
    <td>Revisioni referanslayacak root; UI display name gibi alanlara güvenilmez.</td>
  </tr>
  <tr>
    <td>PortfolioAllocationPlanDraft</td>
    <td>Evet</td>
    <td>enabled, initial capital, currency, compounding, reserve, entry listesi, row_version.</td>
    <td>Doğrudan kullanılmaz.</td>
  </tr>
  <tr>
    <td>PortfolioAllocationPlanRevision</td>
    <td>Hayır</td>
    <td>Validated canonical config + config hash.</td>
    <td>Shared mode run requestte pinlenir.</td>
  </tr>
  <tr>
    <td>Composition Snapshot</td>
    <td>Hayır</td>
    <td>Item revisionları + plan revision + resolved references.</td>
    <td>Ready Check ve manifest inputu.</td>
  </tr>
  <tr>
    <td>Backtest Run Manifest</td>
    <td>Hayır</td>
    <td>Exact plan snapshot, calculated sleeve amounts, currency/FX refs, engine allocation policy version.</td>
    <td>Enginein tek source-of-truthu.</td>
  </tr>
  <tr>
    <td>Backtest Result</td>
    <td>Hayır</td>
    <td>Succeeded runın outputu; allocation metadata run context olarak görünür.</td>
    <td>Planı veya manifesti mutate etmez.</td>
  </tr>
</table>

## 8.2 Canonical payload

<table>
  <tr>
    <th>PortfolioAllocationConfigV1 {<br/>  enabled: true,<br/>  initial_capital: { amount: &quot;10000.00&quot;, currency: &quot;USDT&quot; },<br/>  compounding_mode: &quot;COMPOUND_PORTFOLIO_EQUITY&quot;,<br/>  reserve_cash_percent: &quot;10.00&quot;,<br/>  entries: [<br/>    { composition_item_id: &quot;cmbi_...&quot;, item_type: &quot;STRATEGY&quot;, active: true, equity_share_percent: &quot;40.00&quot; },<br/>    { composition_item_id: &quot;cmbi_...&quot;, item_type: &quot;TRADING_SIGNAL&quot;, active: true, equity_share_percent: &quot;20.00&quot; }<br/>  ]<br/>}</th>
  </tr>
</table>

Para ve yüzde alanları binary float olarak persist edilmez. Server locale virgülü gibi kullanıcı girdisini parse edebilir; canonical persistence ve manifestte decimal string / NUMERIC kullanılır. `item_type` requestten güvenilir kabul edilmez; server current composition itemın canonical kindından türetir.

## 8.3 Sermaye formülleri ve compounding semantiği

<table>
  <tr>
    <th>P0 = initial_capital<br/>r  = reserve_cash_percent / 100<br/>R0 = P0 * r                         # fixed nominal reserve<br/>A0 = max(0, P0 - R0)                # allocatable initial pool<br/>Ci0 = A0 * wi / 100                 # item i initial sleeve capital<br/>U0 = A0 - sum(Ci0)                  # unallocated cash<br/><br/>Compound: E(t) = P0 + realized_pnl(t) - fees(t) - funding(t) - realized_costs(t)<br/>          A(t) = max(0, E(t) - R0)<br/>          Ci(t) = A(t) * wi / 100<br/>Fixed:    Ci_fixed = A0 * wi / 100<br/><br/>allowed_size = min(desired_size_from_strategy_details, remaining_sleeve_capacity, item_risk_limits, ledger_solvency_limit)</th>
  </tr>
</table>

Aynı timestampte engine, mandatory stop/exit/funding/fee olaylarını önce resolver; ardından tek bir portfolio valuation snapshotı üretir. Tüm aktif itemler aynı snapshotla entry/scale intent üretir. UI row sırası, DOM orderı veya API arrival orderı allocation sonucu değiştiremez. Allocation yalnız yeni entry/scale için outer cap uygular; mevcut açık pozisyonlar equity değişti diye zorla rebalance edilmez.

## 8.4 Deterministik pipeline ve Conflict Rules ilişkisi

1. Market/Research inputları event time / available time kurallarına göre hazırlanır.

2. Zorunlu stop, exit, funding ve fee olayları versioned Engine Contract prioritysiyle resolve edilir; ledger güncellenir.

3. Compound mode için A(t) ve sleeve capacityler aynı portfolio valuation snapshotından türetilir; fixed mod için Ci_fixed kullanılır.

4. Tüm active Mainboard itemleri aynı data + valuation snapshotıyla intent üretir.

5. Strategy Details sizing/risk constraints uygulanır; ardından allocation remaining sleeve capacity ve ledger solvency kontrol edilir.

6. Conflict Rules item intentini engellerse o itemin shareı diğer itemlere run içinde otomatik devredilmez.

7. Fill/partial fill/reject ledgera işlenir. Bir sonraki allocation target ancak sonraki valuation pointte hesaplanır.

## 8.5 Allocation plan, Ready Check, Run manifest ve Result ilişkisi

<table>
  <tr>
    <th>Aşama</th>
    <th>Allocation etkisi</th>
  </tr>
  <tr>
    <td>Draft edit</td>
    <td>Mainboard composition fingerprint değişir; varsa mevcut readiness report STALE olur.</td>
  </tr>
  <tr>
    <td>Allocation validate</td>
    <td>Server errors/warnings/derived amounts üretir. Bu report Run değildir ve Result oluşturmaz.</td>
  </tr>
  <tr>
    <td>Plan revision</td>
    <td>No blockers varsa immutable `portfolio_allocation_plan_revision_id` + config hash üretilir.</td>
  </tr>
  <tr>
    <td>Composition snapshot</td>
    <td>Exact working item revisions + allocation plan revision + dependency refs sabitlenir.</td>
  </tr>
  <tr>
    <td>Backtest Run manifest</td>
    <td>enabled=true ise exact plan revision + snapshot; enabled=false ise plan revision null olabilir ama independent mode explicit yazılır.</td>
  </tr>
  <tr>
    <td>Backtest Result</td>
    <td>Succeeded run sonucu allocation enabled/mode/currency/reserve/share/unallocated metadata gösterir. Bu değerler metric profile değildir.</td>
  </tr>
</table>

# 9. Agent Tool/API Eşdeğeri ve Sürekli Çalışma Modeli

Agent, Portfolio / Equity Allocation ekranını tıklamak zorunda değildir. UI Button -> API Command -> Domain Service zincirinin aynı commandları Tool Gateway üzerinden Agent runtimea sunulur. Agentın Mainboard sayfası, Lab chat veya insan sessionı kapansa bile araştırma loopu devam eder.

<table>
  <tr>
    <th>Agent tool</th>
    <th>Amaç</th>
    <th>Policy / provenance</th>
  </tr>
  <tr>
    <td>portfolio_allocation.get_draft</td>
    <td>Compositiona bağlı allocation draftını, row_versionı ve candidate itemleri okur.</td>
    <td>Agent yalnız policy kapsamındaki compositionı okuyabilir; private başka owner planı erişim dışıdır.</td>
  </tr>
  <tr>
    <td>portfolio_allocation.upsert_draft</td>
    <td>Enabled/pool/entries configini typed schema ile günceller.</td>
    <td>Yalnız Agent-owned planlarda mutate; expected_row_version, idempotency key, audit ve task/checkpoint context zorunlu.</td>
  </tr>
  <tr>
    <td>portfolio_allocation.sync_preview</td>
    <td>Mainboard item değişimlerini merge preview olarak alır.</td>
    <td>Agent free-text item uyduramaz; confirmed merge kararı artifact/audit izine bağlanır.</td>
  </tr>
  <tr>
    <td>portfolio_allocation.validate</td>
    <td>Portfolio hypothesis için blocker/warning/derived capleri çözer.</td>
    <td>Validation report id, composition fingerprint, data/FX dependencies ve agent task context kaydedilir.</td>
  </tr>
  <tr>
    <td>portfolio_allocation.create_revision</td>
    <td>Validated draftı immutable plan revisiona dönüştürür.</td>
    <td>Aktif/completed run manifestini değiştiremez; yeni revision yalnız future snapshotta kullanılır.</td>
  </tr>
  <tr>
    <td>backtest.run with allocation ref</td>
    <td>Composition snapshot + plan revision ile run request yaratır.</td>
    <td>Queue/worker arkada çalışır; Agent browser UI veya human approval beklemez; policy/validation aynı server guardsdan geçer.</td>
  </tr>
</table>

Agent, currency mismatch, duplicate allocation entry veya missing item dependency bulursa bunları override etmez; validation artifacti ve follow-up task üretir. Planı yalnız kendi produced compositionı üzerinde update eder; shared/published source itemleri kendi compositionında referanslamak ownership transferi değildir.

# 10. Validation, Error, Recovery ve Kullanıcı Akışları

## 10.1 Validation matrix

<table>
  <tr>
    <th>Kategori</th>
    <th>Blocker / warning</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>Field</td>
    <td>Initial Capital &lt;= 0 veya parse edilemez; reserve &lt;0 veya &gt;=100; compounding empty/unknown.</td>
    <td>Inline erroru düzelt; normalized decimal draftı kaydet; validate tekrar çalıştır.</td>
  </tr>
  <tr>
    <td>Cross-field</td>
    <td>enabled=true + no active entry; active entry share&lt;=0; total active share&gt;100; duplicate active item.</td>
    <td>Rowu activate/deactivate et, shareı düzelt veya duplicate entryyi kaldır.</td>
  </tr>
  <tr>
    <td>Dependency</td>
    <td>Item current compositionda değil, soft-deleted, access dışı, invalid revision; FX dependency yok.</td>
    <td>Pickerdan valid item seç, Mainboard dependencyyi düzelt/restore et veya approved pinned FX dataset bağla.</td>
  </tr>
  <tr>
    <td>Independent mode</td>
    <td>enabled=false iken allocation fields invalid olabilir ama engine okumaz; item own Initial Capital eksikse blocker.</td>
    <td>Item details alanındaki own Initial Capitalı tamamla; allocationı zorla açma.</td>
  </tr>
  <tr>
    <td>Authorization</td>
    <td>Caller planı view/edit/use hakkına sahip değil.</td>
    <td>ACCESS_DENIED / OWNER_REQUIRED göster; own composition aç veya Admin/owner actionı iste.</td>
  </tr>
  <tr>
    <td>Lifecycle</td>
    <td>Composition veya referenced item soft-deleted/purge pending; immutable plan revision patch edilmeye çalışılıyor.</td>
    <td>Restore preflight / clone-to-draft / current active composition seç.</td>
  </tr>
  <tr>
    <td>Concurrency</td>
    <td>expected_row_version outdated.</td>
    <td>409 CONFLICT; current draftı çek, changed pathleri karşılaştır, merge/reapply yap.</td>
  </tr>
  <tr>
    <td>Async / run</td>
    <td>Validation stale, job failure, run preflight mismatch.</td>
    <td>Latest server validationı al; blockersı çöz; retry yeni run / new manifest üretir.</td>
  </tr>
</table>

## 10.2 User and system flows

Flow A - Flow A - Independent mode başarıyla çalışır

1. Kullanıcı sayfayı açar; toggle kapalıdır. Shared workspace soluk görünür ve status `NOT SELECTED` yazar.

2. Kullanıcı allocation alanlarını düzenlemez; her active Strategy, Trading Signal ve Trade Log kendi details içindeki Initial Capitalla kalır.

3. Ready Check allocation validatorını shared mode için çalıştırmaz; item-level Initial Capital ve execution/risk bağımlılıklarını kontrol eder.

4. Manifestte `portfolio_allocation.enabled=false` açıkça saklanır. Shared pool, reserve ve share değerleri engine inputu değildir.

Flow B - Flow B - Shared pool, compound mode

1. Kullanıcı toggleı açar; Production draft autosave `Saving` sonra `Saved` durumuna geçer.

2. 10,000 USDT, %10 Reserve, Compound Portfolio Equity seçer; Strategy A %40, Strategy B %35, Trading Signal %15 aktif bırakır.

3. Server validation R0=1,000, A0=9,000, sleeve capleri 3,600 / 3,150 / 1,350 ve %10 unallocated cash uyarısını üretir.

4. User valid drafttan immutable plan revision üretir; composition snapshot/run manifest exact revision, FX dependencies ve engine policy versionu pinler.

5. Yeni valuation pointlerde resolved equity değişirse yalnız yeni entry/scale capacityleri hesaplanır; mevcut positions zorla rebalance edilmez.

Flow C - Flow C - Invalid plan

1. Kullanıcı shared modeu açar, Initial Capitalı 0 bırakır ve iki active rowa %70 + %45 yazar.

2. UI local preview issue gösterebilir; server validate `INITIAL_CAPITAL_INVALID` ve `TOTAL_ALLOCATION_EXCEEDS_100` blockerlarını döndürür.

3. Allocation Check NOT READY olur; Plan Revision ve Backtest Run commandları disabled görünür. Direct API request de 422 döner; manifest/job oluşturulmaz.

4. User capitalı pozitif değere, active share toplamını 100 veya altına düzeltir; validation yeniden çalışır.

Flow D - Flow D - Safe Mainboard sync

1. Compositiona yeni Trading Signal eklenir veya bir item silinir. Allocation draft/readiness fingerprinti STALE olur.

2. Kullanıcı Sync From Mainboarda basar. Production server new, missing, unchanged ve ambiguous entryleri içeren merge preview döndürür.

3. Destructive removals veya share redistribution otomatik uygulanmaz; user confirmation token ile değişikliği açıkça onaylar.

4. Apply sonrası new draft row_version döner, audit `allocation_sync_applied` yazılır ve validation tekrar gerekir.

Flow E - Flow E - Stale conflict

1. Supervisorın kendi compositionında açık draftı v12 iken başka sekmede v13e güncellenir.

2. Eski `expected_row_version=v12` ile save denemesi 409 CONFLICT döndürür; server current draft + changed paths verir.

3. UI local unsaved fields ile server stateini compare görünümünde sunar. User reapply veya discard seçer; last-write-wins yapılmaz.

Flow F - Flow F - Soft delete / restore

1. Composition veya plan rootu soft-delete edilirse aktif listelerden ve future run seçiminden kalkar; historical manifests aynı immutable allocation snapshotını korur.

2. Trash yalnız Admin tarafından listelenir. Restore aynı root ID ve current revision pointer ile ACTIVE hale döner; yeni plan revision oluşmaz.

3. Referenced immutable artifact tarafından korunan plan için purge isteği `PURGE_REFERENCED_BY_IMMUTABLE_ARTIFACT` ile engellenir. Root soft-deleted kalır ve restore adayıdır.

# 11. Lifecycle, Audit, Trash ve Historical Integrity

## 11.1 Lifecycle sözleşmesi

<table>
  <tr>
    <th>Nesne</th>
    <th>Normal mutasyon</th>
    <th>Silme / restore</th>
    <th>Historical etkisi</th>
  </tr>
  <tr>
    <td>Portfolio Allocation Plan Draft</td>
    <td>PUT/PATCH; row_version ile concurrent save.</td>
    <td>Draft/plan root soft-delete composition aggregate kuralına bağlıdır.</td>
    <td>Direct engine input değildir.</td>
  </tr>
  <tr>
    <td>Portfolio Allocation Plan Revision</td>
    <td>Immutable; edit yok, clone/new draft gerekir.</td>
    <td>Referenced revision soft-delete olsa bile manifest snapshot korunur.</td>
    <td>Run/Result manifestini değiştirilemez.</td>
  </tr>
  <tr>
    <td>Allocation entry</td>
    <td>Draft relation add/remove/update; no independent external item mutation.</td>
    <td>Row removal source itemi silmez; independent Trash kaydı oluşmaz.</td>
    <td>Historical plan revision entry snapshotı korunur.</td>
  </tr>
  <tr>
    <td>Mainboard composition delete</td>
    <td>Linked plan root/deletion projectiona etki eder.</td>
    <td>Normal delete soft delete; restore same root/current pointer; Admin-only Trash.</td>
    <td>Historical run/result allocation snapshots intact.</td>
  </tr>
  <tr>
    <td>Purge</td>
    <td>Admin-only async purge job; dependency/retention preflight.</td>
    <td>PURGE_PENDINGde restore kapalı.</td>
    <td>Immutable artifact reference varsa purge blocked; audit/tombstone retained.</td>
  </tr>
</table>

## 11.2 Mandatory audit events

<table>
  <tr>
    <th>Event</th>
    <th>Minimum audit fields</th>
  </tr>
  <tr>
    <td>portfolio_allocation_enabled_changed</td>
    <td>actor, composition_root_id, previous_enabled, new_enabled, request_id, timestamp, correlation_id.</td>
  </tr>
  <tr>
    <td>portfolio_allocation_draft_changed</td>
    <td>actor, plan/draft id, expected/current row_version, field diff, old/new normalized values, outcome.</td>
  </tr>
  <tr>
    <td>portfolio_allocation_entry_changed</td>
    <td>actor, composition_item_id, old/new share, old/new active, sync_source, outcome.</td>
  </tr>
  <tr>
    <td>portfolio_allocation_validated</td>
    <td>actor or Agent, validation_report_id, composition fingerprint, issues summary, config hash.</td>
  </tr>
  <tr>
    <td>portfolio_allocation_revision_created</td>
    <td>actor, plan_root_id, plan_revision_id, config hash, source draft version.</td>
  </tr>
  <tr>
    <td>portfolio_allocation_snapshot_pinned</td>
    <td>actor/system, plan_revision_id nullable, composition_snapshot_id, run_manifest_id, engine policy version.</td>
  </tr>
  <tr>
    <td>portfolio_allocation_soft_deleted/restored/purge_*</td>
    <td>actor, target root/revision refs, trash entry id, preflight outcome, restore/purge result, correlation id.</td>
  </tr>
</table>

Audit event, revision tablosunun yerine geçmez. Hangi actorün hangi commandi hangi contextte çalıştırdığını append-only olarak kanıtlar. Soft delete, restore ve purge; client DOMundan veya generic repository updateinden değil explicit backend command service üzerinden yürütülür.

# 12. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Konu</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Allocation row identity</td>
    <td>Item name inputu ve Type dropdown serbestçe düzenlenebilir.</td>
    <td>Each entry `composition_item_id` ile bağlanır; type server-derived.</td>
    <td>Free-text/name/type alanı picker + readonly detail ile değiştirilir.</td>
  </tr>
  <tr>
    <td>+ Add Item</td>
    <td>Boş `Strategy N` row ekler.</td>
    <td>Sadece unrepresented compatible composition itemleri gösteren picker.</td>
    <td>No free-text creation; item membership/type tam server doğrulaması.</td>
  </tr>
  <tr>
    <td>Sync From Mainboard</td>
    <td>Rowsu eşit share ile doğrudan replace eder; floor(100/n) ile remainder unallocated kalabilir.</td>
    <td>POST sync merge preview; destructive apply confirmation token ister.</td>
    <td>Preserve/replace choice görünür olur; silent data loss yok.</td>
  </tr>
  <tr>
    <td>Reserve Cash</td>
    <td>Label yüzde belirtmez; text parser %.</td>
    <td>`Reserve Cash (%)` numeric decimal.</td>
    <td>Visible unit/suffix, [0,100) validation ve fixed nominal semantics.</td>
  </tr>
  <tr>
    <td>Calculation preview</td>
    <td>Browserda JavaScript ile hesaplanır.</td>
    <td>Server validate responseun derived valuesi canonicaldır.</td>
    <td>Client preview same formula ile hint olabilir; run uses server snapshot.</td>
  </tr>
  <tr>
    <td>Allocation Check</td>
    <td>Local READY FOR BACKTEST metni.</td>
    <td>Server validation/Ready Check/run preflight repeats checks.</td>
    <td>Green UI is not authorization or run permission.</td>
  </tr>
  <tr>
    <td>Save behavior</td>
    <td>Explicit Save yok; local JS state.</td>
    <td>Draft persisted by versioned server command; revision immutable.</td>
    <td>Autosave status added without pretending client state is canonical.</td>
  </tr>
  <tr>
    <td>Info text</td>
    <td>Inline ⓘ yok; global registryde compounding texti `Fixed Item Notional` içerir.</td>
    <td>V1 only two compounding enums.</td>
    <td>Production info catalog above replaces outdated option; no hidden third mode.</td>
  </tr>
  <tr>
    <td>Fallback sample rows</td>
    <td>Mainboard boşken demo sample rows.</td>
    <td>No persisted synthetic item; empty state.</td>
    <td>Run cannot use demo fallback or fake composition reference.</td>
  </tr>
</table>

# 13. Implementation Rules for Kodcu AI

- Portfolio Allocation için yalnız `PortfolioAllocationPlan` rootu ve immutable `PortfolioAllocationPlanRevision` terimlerini kullan. `allocation_profile`, `portfolio profile` veya metric/output profileı ayrı persisted entity olarak üretme.

- Planı Mainboard Composition Draftına bağla; global reusable template, live brokerage account veya Package olarak modelleme.

- Allocation entryyi display name, DOM index veya Type dropdown metniyle persist etme. `composition_item_id` zorunludur; item type server tarafından canonical composition itemdan türetilir.

- Trading Signal ve Trade Logu allocationa dahil edebilirsin; onları Package Library package kindı yapma.

- enabled=false iken shared pool, reserve, share, preview veya stale local values engine evaluation planına dahil edilmez. Independent capital resolver kullan.

- enabled=true iken Initial Capital >0, valid Base Currency, valid Compounding Mode, 0<=Reserve<100, minimum bir active entry, active share>0, total active share<=100 ve non-duplicate accessible item kontrollerini server-side zorunlu uygula.

- Reserve Cashi sabit nominal R0 olarak hesapla. Compound modda reserve yüzdesini current equityye yeniden uygulama.

- Allocationı Strategy Details sizingin yerine geçirme. Desired size strategy rulelarından gelir; allocation yalnız outer sleeve capacity cap uygular.

- Aynı timestampte bütün active itemler aynı portfolio valuation snapshotını görmelidir. DOM row orderı, browser timing veya request arrival orderı sonucu değiştirmemelidir.

- Conflict nedeniyle engellenen itemin shareını başka iteme run içinde otomatik devretme. Share planı immutable run snapshot boyunca sabittir.

- Money ve percent değerlerini NUMERIC/fixed-point veya decimal string olarak sakla; float rounding ile manifest/preview mismatch üretme.

- Initial Capital, currency, compounding, reserve veya active/share/item değiştiğinde composition fingerprinti invalid yap ve prior Readiness Reportu STALE olarak işaretle.

- Draft write commandlarında `expected_row_version` ve idempotency key kullan. 409 CONFLICTte last-write-wins yapma; current state + changed paths döndür.

- Validated allocation configi immutable revisiona dönüştür; mevcut revisionı generic PATCH ile mutate etme. Historical run/result manifestini asla güncelleme.

- Shared mode run manifesti exact `portfolio_allocation_plan_revision_id`, resolved sleeve amounts, currency/FX refs, compounding mode ve allocation engine policy versionunu taşımalıdır. Independent modda revision id null olabilir fakat enabled=false açık olmalıdır.

- Client preview/green statusu run yetkisi sayma. `POST /backtest-runs`, request anında allocation validation ve snapshot integrity kontrolünü tekrar yürütmelidir.

- Agent aynı command/service capabilityleri Tool Gateway üzerinden kullanmalıdır. Agentın UI tıklaması, chat mesajı veya human sessionı allocation edit/validate/run için gerekli değildir.

- Allocation Plan normal ownership kuralına tabidir; Rationale Families shared-editing exceptionını bu sayfaya genişletme.

- Plan/Composition soft delete olduğunda yeni selection/run kullanımını kes; historical manifests/artifactler korunur. Trash, restore ve purge yalnız Admindir. Referenced immutable artifact varsa purgeyi retention erroruyla engelle.

- Every mutation, validation, revision creation, snapshot pin ve delete/restore/purge action correlation idli audit/outbox event üretmelidir.

# 14. Acceptance Tests

1. Sayfa ilk açıldığında toggle false, Initial Capital 10000, Base Currency USDT, Compounding Mode Compound Portfolio Equity ve Reserve Cash 0 render edilir; workspace soluk/disabled ve independent mode valid görünür.

2. Toggle false iken allocation fieldleri herhangi eski draft değeri taşısa bile engine shared pool/reserve/share okumaz; each active item own Initial Capital resolver ile değerlendirilir.

3. Toggle true iken Initial Capital <=0, Reserve<0, Reserve>=100, empty/unknown compounding mode veya missing Base Currency server tarafında 422/blocker üretir.

4. Active entry yoksa, active entry share<=0 ise veya total active share>100 ise validation blocker üretir; Plan Revision ve Run manifest oluşturulmaz.

5. Total share <100 olduğunda validation READY_WITH_WARNINGS veya equivalent warning üretir; unallocated capital amount exact decimal hesaplanır ve auto-borrow olmaz.

6. Aynı composition_item_id iki active allocation rowunda gönderilirse server duplicate-entry validation hata verir.

7. V18 free-text Item/Type manipülasyonu Production APIde canonical composition itema karşı doğrulanır; unknown, foreign, soft-deleted veya inaccessible item 422/DEPENDENCY_BLOCKED döner.

8. + Add Item picker yalnız active compositionda rowu olmayan compatible Strategy, Trading Signal veya Trade Log itemlerini listeler; no candidate empty state doğru görünür.

9. Sync From Mainboard server merge preview döndürür; destructive row removal/share overwrite confirmation token olmadan persisted drafta uygulanmaz.

10. 10,000 USDT, reserve %10 ve shares %40/%35/%15 için server derived values R0=1,000, A0=9,000, sleeves 3,600/3,150/1,350, unallocated=900 üretir.

11. Compound mode valuation pointinde fee/funding/mandatory exitler işlendiğinde tüm itemler aynı E(t) snapshotını görür; row order sonucu değiştirmez.

12. Fixed mode new entry/scale sizing baseini Ci_fixedte tutar; PnL recorded olsa dahi auto compounding yapmaz; insolvency/required margin durumunda silent borrow yoktur.

13. Strategy Details desired size sleeve capacityyi aştığında engine deterministik cap/reject davranışını manifest policyye göre uygular; allocation position sizing methodunu değiştirmez.

14. Allocation config değiştiğinde current Readiness Report STALE olur. Green client check, stale report veya direct API çağrısı run job oluşturamaz; server preflight yeniden validasyon ister.

15. Same idempotency key ile double-click save/revision commandi duplicate plan revision veya audit side effect üretmez; same response/reference döner.

16. Stale expected_row_version ile draft save 409 CONFLICT döndürür; server current draft/changing paths sağlar; last-write-wins gerçekleşmez.

17. Agent Tool Gateway aynı draft/validate/revision/run commandlarını UI olmadan çağırabilir; Agent başka ownerın private planını mutate edemez.

18. Normal delete soft delete + Trash audit kaydı üretir. User/Supervisor/Agent Trash list/restore/purge endpointine 403 alır; Admin restore same root/current revision ile ACTIVE yapar.

19. Historical immutable run manifestteki allocation snapshot, plan/edit/delete/restore sonrasında değişmez. Purge referenced immutable artifact için `PURGE_REFERENCED_BY_IMMUTABLE_ARTIFACT` döner.

20. Result metadata allocation enabled/mode/currency/initial capital/reserve/active share total/unallocated cashı run context olarak gösterir; Result View Metric Profileın yerine geçmez.

# 15. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Portfolio Allocation Plan / Revision canonical terimi kullanıldı mı?</td>
    <td>Evet. allocation-profile yalnız V18/legacy compatibility notu olarak anıldı; persisted canonical entity değildir.</td>
  </tr>
  <tr>
    <td>Trading Signal / Trade Log Package olarak anlatıldı mı? [V18 legacy prototype label; Production domain/API type değildir.]</td>
    <td>Hayır. Bunlar external Mainboard Working Itemdır; allocationda sleeve alabilirler.</td>
  </tr>
  <tr>
    <td>Independent mode valid ve engine-clear olarak anlatıldı mı?</td>
    <td>Evet. Toggle kapalıyken shared config engine dışıdır; own Initial Capital kontrol edilir.</td>
  </tr>
  <tr>
    <td>Run / Result ayrımı korundu mu?</td>
    <td>Evet. Plan snapshot Run Manifestte pinlenir; yalnız succeeded run immutable Result üretir.</td>
  </tr>
  <tr>
    <td>Agent UI bağımsız capability parity açık mı?</td>
    <td>Evet. Tool Gateway commandları ve owner/policy sınırı yazıldı.</td>
  </tr>
  <tr>
    <td>Trash Admin-only, historical integrity ve purge retention doğru mu?</td>
    <td>Evet. Restore/purge yalnız Admin; immutable artifact reference purgeyi bloklar.</td>
  </tr>
  <tr>
    <td>V18 free-text/JS behavior ile Production canonical behavior ayrıldı mı?</td>
    <td>Evet. Item picker, server validation, autosave draft, revision/snapshot ve sync confirmation ayrı yazıldı.</td>
  </tr>
  <tr>
    <td>Implementation decisions canonical kural gibi etiketlenmeden ayrıldı mı?</td>
    <td>Evet. Autosave, production ⓘ panels, percent label ve sync UI davranışı açık Implementation Decision olarak işaretlendi.</td>
  </tr>
  <tr>
    <td>Bu belge dış sayfaların tam kapsamını yeniden dokümante ediyor mu?</td>
    <td>Hayır. Ready Check, Run, Results, Mainboard ve Strategy Details yalnız sınır/bağımlılık düzeyinde anıldı.</td>
  </tr>
</table>
