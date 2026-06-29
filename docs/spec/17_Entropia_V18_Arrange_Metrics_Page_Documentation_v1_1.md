---
title: "Entropia V18 — Arrange Metrics Page Documentation v1.1"
page_number: 17
document_type: "Page implementation specification"
source_document: "Entropia_V18_Arrange_Metrics_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Arrange Metrics Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18
> **Original DOCX footer:** ENTROPIA V18 | Arrange Metrics | Sayfa Dokümantasyonu 17/22 | Production V1 uygulama sözleşmesi

ENTROPIA V18

ARRANGE METRICS

Sayfa Dokümantasyonu 17/22 | Result View Metric Profile, metric registry seçimi, görünüm sırası ve lock davranışı

# 0. Document Control, Scope ve Source Traceability

Bu belge yalnız Arrange Metrics sayfasını tanımlar. Sayfanın görevi, Backtest Results içinde gösterilecek mevcut metric subsetini ve sabit presentation sırasını Result View Metric Profile üzerinden yönetmektir. Sayfa Backtest engine formüllerini, workerın hesapladığı canonical metric kapsamını, Backtest Run manifestini, Result Summaryyi veya immutable Backtest Result değerlerini değiştirmez.

<table>
  <tr>
    <th>Kilit canonical karar. Arrange Metrics yalnız presentation katmanıdır. Bir metric profiledan çıkarıldığında enginein hesapladığı MetricValue kaydı silinmez; profile eklendiğinde de geçmişte hesaplanmamış bir result için değer uydurulmaz. Bu ayrım Modül 13 ve CR-07 ile bağlayıcıdır.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Kaynak / tür</th>
    <th>Bu sayfada kullanılan bölüm</th>
    <th>Kullanım amacı</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0</td>
    <td>Modül 13 §1-5.4; §9-10; §12; Canonical Integration CR-03, CR-04, CR-06, CR-07</td>
    <td>Immutable Result, MetricDefinition registry, selectable/future metric ayrımı, Result View Metric Profile, lock, audit, API ve run/result ayrımı.</td>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0</td>
    <td>Modül 1-3; Modül 19-20</td>
    <td>Rol/policy, ownership, soft delete/Trash, client-server sınırı, concurrency ve durable persistence.</td>
  </tr>
  <tr>
    <td>V18 ana HTML</td>
    <td>Performance Metrics &gt; Arrange Metrics; availableMetrics; selectedMetrics; futureMetrics; metricsLocked; showArrangeMetrics(); applyMetricSelection(); lockMetrics(); unlockMetrics(); createMetricGridHTML()</td>
    <td>Mevcut UI etiketleri, dokuz checkboxın varsayılan seçimi, future metric listesi, action düğmeleri ve prototype state akışı.</td>
  </tr>
  <tr>
    <td>Sayfa Bazlı Dokümantasyon Handoff v1.1</td>
    <td>§5-13; özel Arrange Metrics notu</td>
    <td>Zorunlu doküman matrisi, V18/Production ayrımı ve “metric profile yalnız görünüm tercihidir” kalite kapısı.</td>
  </tr>
  <tr>
    <td>2.3 Position Entry Logic örneği</td>
    <td>Anlatım derinliği ve implementation rule biçimi</td>
    <td>Kavramların ilk kullanımda açıklanması, backend/Agent parity, validation, recovery ve test derinliği için referans.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam içi</th>
    <th>Kapsam dışı / yalnız çapraz referans</th>
  </tr>
  <tr>
    <td>Result View Metric Profileın seçili metric kodları, registry tabanlı kullanılabilirlik, lock state, default fallback, statü metni ve Result Viewe etkisi.</td>
    <td>Metric formüllerinin engine içinde hesaplanması, Result History sorgu/sort ekranı, Run orkestrasyonu, export üretimi, diagnostics, Trading Signal/Trade Log veya Future Dev capability aktivasyonu.</td>
  </tr>
  <tr>
    <td>V18 checkbox grid, Future Version Metrics listesi, Apply/Lock/Unlock actions, status line, error/empty/loading/recovery states.</td>
    <td>Yeni Backtest Result üretme; result root, trade ledger veya summary değerlerini değiştirme; mevcut Resultları yeniden materialize etme.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kavramsal Sınır

Arrange Metrics, kullanıcı veya yetkili workspace contexti için Backtest Result görünümünde hangi mevcut metriclerin hangi sabit sırada gösterileceğini belirleyen presentation yüzeyidir. Bir Backtest Result immutable kanıt paketidir; Metric Profile ise o kanıt paketinden hangi mevcut değerlerin UI kartı olarak okunacağını belirleyen mutable preference/revision zinciridir.

<table>
  <tr>
    <th>Kavram</th>
    <th>Canonical tanım</th>
    <th>Bu sayfadaki uygulama etkisi</th>
  </tr>
  <tr>
    <td>MetricDefinition</td>
    <td>Kod, formula_version, value type, unit, aggregation scope, availability status, açıklama, null davranışı ve registry display order taşıyan canonical registry kaydı.</td>
    <td>UI serbest metin metric adıyla çalışmaz. Checkbox değerinde metric_code, ekranda display_name kullanılır.</td>
  </tr>
  <tr>
    <td>MetricValue</td>
    <td>Belirli bir Result için engine/materialization tarafından hesaplanmış immutable metric değeri ve durumu.</td>
    <td>Profile değiştirildiğinde silinmez, yeniden hesaplanmaz ve değer değişmez.</td>
  </tr>
  <tr>
    <td>Result View Metric Profile</td>
    <td>Kullanıcı veya workspace seviyesinde, Result ekranında görünmesi istenen metriclerin subset/sıra tercihi.</td>
    <td>Bu sayfanın ana domain nesnesidir; engine metric kapsamından ayrıdır.</td>
  </tr>
  <tr>
    <td>Profile Revision</td>
    <td>Seçili metric_code dizisi, display order, lock state ve registry versionın append-only kaydı.</td>
    <td>Apply, Lock ve Unlock yeni revision üretir; UI canonical response ile rehydrate edilir.</td>
  </tr>
  <tr>
    <td>System Default Profile</td>
    <td>Kişisel profil bulunmadığında kullanılan, silinemeyen ve yeni revision ile güncellenen system/workspace fallback profile.</td>
    <td>V18deki dokuz mevcut metricin registry sırası default başlangıç seçimidir.</td>
  </tr>
  <tr>
    <td>Metric availability</td>
    <td>Registry içindeki kullanılabilirlik durumu. V1 için selectable, future veya experimental statüsünü taşır.</td>
    <td>Future/experimental metric ekran listesinde görünebilir; SELECTABLE değilse checkbox olarak seçilemez veya Apply payloadına giremez.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam sınırı. Arrange Metrics, Run Profile veya Output Artifact Profile değildir. Backtest Engine hangi canonical metricleri hesaplayacağını profile göre daraltmaz; export ve Agent result bundleı da insan UI seçiminden eksik veri üretmez.</th>
  </tr>
</table>

# 2. Erişim, Görünürlük, Ownership ve Server-Side Yetki

Performance Metrics menüsünün görünmesi veya checkboxların browserda enabled olması authorization kanıtı değildir. Profile list, read, create, revise ve workspace-default mutationları server-side principal, scope, ownership ve operation policy ile doğrulanır. Clientın gönderdiği role, profile scope, locked flag veya owner alanı otorite kabul edilmez.

<table>
  <tr>
    <th>Principal / rol</th>
    <th>Sayfayı görme</th>
    <th>Profile okuma ve kullanma</th>
    <th>Profile revise / lock</th>
    <th>Workspace/system default</th>
    <th>Agent davranışı</th>
  </tr>
  <tr>
    <td>Guest / anonymous</td>
    <td>Hayır. Authentication veya public shell dışında result preference verilmez.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Agent değildir.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Evet; erişebildiği Resultlar bağlamında.</td>
    <td>Kendi profileını okuyabilir; profil yoksa system default fallback görür.</td>
    <td>Yalnız kendi Result View Metric Profileını revise, lock veya unlock edebilir.</td>
    <td>Hayır.</td>
    <td>Uygulanmaz.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Evet; shared working scope içinde.</td>
    <td>Kendi profileını okuyabilir; erişebildiği Resultlarda kullanabilir.</td>
    <td>Yalnız kendi profileını revise, lock veya unlock edebilir.</td>
    <td>Hayır; ayrı Admin workspace policy gerekir.</td>
    <td>Uygulanmaz.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Evet.</td>
    <td>Kendi ve yetkili workspace default profileını okuyabilir.</td>
    <td>Kendi profileını ve policy izin veriyorsa workspace default profileını revise edebilir.</td>
    <td>Evet; default silinmez, yalnız yeni revisionla güncellenir.</td>
    <td>Uygulanmaz.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>İnsan UI oturumuna bağlı değildir.</td>
    <td>Human UI profileına bağlı değildir; registryden uygun metric schema ve Result MetricValue bundleını Tool/API ile ister.</td>
    <td>Human profileı mutate etmez.</td>
    <td>Hayır.</td>
    <td>Agent, yeni yorum/hypothesis artifacti üretir; immutable Result ve kullanıcı profilini değiştirmez.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Policy kuralı. Lock Metrics bir security veya role-escalation mekanizması değildir; accidental-edit korumasıdır. Locked profile için dahi edit policy server-side yeniden doğrulanır. Locku değiştirme hakkı olmayan caller doğrudan API çağrısıyla başarı elde edemez.</th>
  </tr>
</table>

# 3. V18 Interface Behavior: Gerçek Arayüz Yerleşimi ve Görünür Bileşenler

V18de Arrange Metrics, üst navigation shelldeki Performance Metrics açılır menüsünden açılır. Bu menüde Results History ve Arrange Metrics seçenekleri bulunur. Arrange Metrics seçildiğinde generic page view kullanılır; ayrı route, modal, drawer veya tab yoktur. Sayfa başında kalın “Arrange Metrics” metni ve seçilebilir mevcut metriclerin yalnız Result ekranında görüneceğini açıklayan yardım cümlesi vardır.

<table>
  <tr>
    <th>Görünür bölge / bileşen</th>
    <th>V18 davranışı</th>
    <th>Görünme koşulu / state</th>
    <th>Production hizalaması</th>
  </tr>
  <tr>
    <td>Navigation entry</td>
    <td>Performance Metrics &gt; Arrange Metrics clickable menu item.</td>
    <td>Performance Metrics açılır menüsü hover/click durumunda görünür. V18de role guard yoktur.</td>
    <td>Authenticated caller için route/page guard uygulanır; browserda görünmesi yetki kanıtı değildir.</td>
  </tr>
  <tr>
    <td>Page heading ve intro</td>
    <td>“Arrange Metrics” ve “Select which currently available performance metrics should appear inside Backtest Results...” metni.</td>
    <td>Sayfa açıldığında görünür.</td>
    <td>Aynı amaç korunur; intro selected metriclerin yalnız presentation etkisi yaptığını açıkça belirtir.</td>
  </tr>
  <tr>
    <td>Current metrics panel</td>
    <td>`metrics-panel` içinde dokuz checkbox labelı. Her checkbox V18 `availableMetrics` dizisinden üretilir.</td>
    <td>Locked=false iken selectable; locked=true iken input disabled.</td>
    <td>Registryde SELECTABLE olan metricDefinition kayıtlarından üretilir. String liste hard-code edilmez.</td>
  </tr>
  <tr>
    <td>Max Stop Streak helper</td>
    <td>Bu label altında küçük metin: “Maximum consecutive stop-loss exits.”</td>
    <td>Sadece Max Stop Streak satırında görünür.</td>
    <td>Canonical tanım terminal STOP_LOSS exit reason kategorisine göre hesaplanır; “consecutive losses” değildir.</td>
  </tr>
  <tr>
    <td>Future Version Metrics panel</td>
    <td>Başlık, reference-only açıklaması ve 18 metriclik non-interactive liste.</td>
    <td>Her zaman görünür; checkbox veya action taşımaz.</td>
    <td>Registryden FUTURE/EXPERIMENTAL availability statusü ile gelir; UI gri kutu/serbest metinle hard-code edilmez.</td>
  </tr>
  <tr>
    <td>Action row</td>
    <td>Apply Selection, Lock Metrics, Unlock Metrics düğmeleri.</td>
    <td>V18de üç düğme her state görünürdür.</td>
    <td>Statee göre doğru enable/disabled davranışı uygulanır; her command revision üretir.</td>
  </tr>
  <tr>
    <td>Status line</td>
    <td>“Metrics are editable. Selected metric count: N” veya “Metrics are locked. Selected metric count: N”.</td>
    <td>Sayfa açılışında ve action sonrası güncellenir.</td>
    <td>Serverdan dönen canonical profile revision, lock ve selected count ile render edilir.</td>
  </tr>
  <tr>
    <td>Modal / popup / table / toolbar</td>
    <td>V18de Arrange Metrics özel modal, popover, table veya search/filter toolbarı yoktur.</td>
    <td>Uygulanmaz.</td>
    <td>Yeni modal veya metric execution formu eklenmez. Gerekirse erişilebilir inline description/tooltip kullanılır.</td>
  </tr>
</table>

<table>
  <tr>
    <th>V18 gözlemi. V18, Apply Selection ile checkboxların DOM sırasını browser memorysine aktarır; result grid de aynı in-memory `selectedMetrics` listesine göre şekillenir. Bu local prototype davranışı Production persistence, authorization veya revision doğrusu değildir.</th>
  </tr>
</table>

## 3.1 V18 current selectable metric listesi ve varsayılanlar

<table>
  <tr>
    <th>metric_code</th>
    <th>V18 label</th>
    <th>V18 default</th>
    <th>Önemli canonical not</th>
  </tr>
  <tr>
    <td>net_profit</td>
    <td>Net Profit</td>
    <td>Checked</td>
    <td>V18de seçili; Result Summary kartı olarak gösterilir.</td>
  </tr>
  <tr>
    <td>max_drawdown</td>
    <td>Max Drawdown</td>
    <td>Checked</td>
    <td>V18de seçili; UI negatif gösterse de canonical value absolute decimaldir.</td>
  </tr>
  <tr>
    <td>romad</td>
    <td>ROMAD</td>
    <td>Checked</td>
    <td>V18de seçili; drawdown sıfırsa null/no_drawdown davranışı gerekir.</td>
  </tr>
  <tr>
    <td>win_rate</td>
    <td>Win Rate</td>
    <td>Checked</td>
    <td>V18de seçili; breakeven trade default denominator dışında kalır.</td>
  </tr>
  <tr>
    <td>profit_factor</td>
    <td>Profit Factor</td>
    <td>Checked</td>
    <td>V18de seçili; gross loss sıfırsa infinity değil null/no_losing_trade.</td>
  </tr>
  <tr>
    <td>total_trades</td>
    <td>Total Trades</td>
    <td>Checked</td>
    <td>V18de seçili; trade root sayısıdır, fill/leg sayısı değildir.</td>
  </tr>
  <tr>
    <td>total_stops</td>
    <td>Total Stops</td>
    <td>Checked</td>
    <td>V18de seçili; terminal STOP_LOSS root count.</td>
  </tr>
  <tr>
    <td>max_stop_streak</td>
    <td>Max Stop Streak</td>
    <td>Checked</td>
    <td>V18de seçili; helper text görünür.</td>
  </tr>
  <tr>
    <td>total_winning_trades</td>
    <td>Total Winning Trades</td>
    <td>Checked</td>
    <td>V18de seçili; fee/funding sonrası net PnL &gt; 0 trade root count.</td>
  </tr>
</table>

## 3.2 Future Version Metrics listesi

<table>
  <tr>
    <th>Future reference 1</th>
    <th>Future reference 2</th>
    <th>Future reference 3</th>
  </tr>
  <tr>
    <td>Sharpe Ratio</td>
    <td>Sortino Ratio</td>
    <td>Recovery Factor</td>
  </tr>
  <tr>
    <td>Robustness Test</td>
    <td>Monte Carlo Result</td>
    <td>Walk-Forward Result</td>
  </tr>
  <tr>
    <td>Out of Sample Result</td>
    <td>Average Trade</td>
    <td>Average Holding Time</td>
  </tr>
  <tr>
    <td>Consecutive Losses</td>
    <td>Exposure</td>
    <td>Long / Short Distribution</td>
  </tr>
  <tr>
    <td>Monthly Return</td>
    <td>Timeframe Sensitivity</td>
    <td>Regime Sensitivity</td>
  </tr>
  <tr>
    <td>Parameter Stability</td>
    <td>Slippage Sensitivity</td>
    <td>Commission Sensitivity</td>
  </tr>
</table>

Bu liste V18de referans amaçlı görünür. Bir future metric hiçbir koşulda checkbox, Apply Selection payloadı, sahte numeric card veya backfilled immutable MetricValue olarak davranmaz. Productionda registryde `availability_status = future` veya `experimental` değerleri ile yönetilir.

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen / durum</th>
    <th>Varsayılan veya tetik</th>
    <th>UI davranışı</th>
    <th>Payload / engine etkisi</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>First open / profile absent</td>
    <td>Authenticated kullanıcıda personal profile root yok.</td>
    <td>System Default Profileın dokuz metrici registry sırasıyla checked görünür; “Using default profile” helper gösterilir.</td>
    <td>Engine ve Result değişmez. Apply ilk kez çağrılırsa personal profile root + first revision yaratılır.</td>
    <td>User seçim yapmadan defaultu kullanır veya Apply ile personal profile oluşturur.</td>
  </tr>
  <tr>
    <td>Loading</td>
    <td>Profile ve MetricDefinition registry sorgusu sürüyor.</td>
    <td>Skeleton/grid loading, actions disabled, previous stale checkbox state kullanılmaz.</td>
    <td>Hiçbir mutation payloadı gönderilmez.</td>
    <td>GET başarısızsa retry.</td>
  </tr>
  <tr>
    <td>Editable</td>
    <td>Profile exists ve `is_locked=false`.</td>
    <td>Selectable checkboxlar aktif; Apply ve Lock aktif, Unlock disabled.</td>
    <td>Henüz engine/Result etkisi yok.</td>
    <td>Seçimleri değiştir, Apply yap.</td>
  </tr>
  <tr>
    <td>Locked</td>
    <td>Current revision `is_locked=true`.</td>
    <td>Checkboxlar disabled; Apply ve Lock disabled; Unlock yalnız editor için aktif.</td>
    <td>Profile revision immutable kalır; Result değişmez.</td>
    <td>Editor Unlock ile yeni unlocked revision yaratır.</td>
  </tr>
  <tr>
    <td>Applying selection</td>
    <td>Apply command kabul edildi.</td>
    <td>Controls pending state; duplicate click engellenir; status “Saving metric profile...” gösterir.</td>
    <td>POST profile revision; idempotency key zorunlu. Engine/Run tetiklenmez.</td>
    <td>Success canonical revision ile rehydrate; failure old revision stateine dön.</td>
  </tr>
  <tr>
    <td>Validation blocked</td>
    <td>0 selected metric, duplicate/unknown code veya non-selectable metric.</td>
    <td>Alan odaklı hata ve status line gösterilir; save yapılmaz.</td>
    <td>Revision oluşmaz.</td>
    <td>En az bir SELECTABLE metric bırak; registryye uygun kod seç.</td>
  </tr>
  <tr>
    <td>Stale conflict</td>
    <td>Başka tab/user aynı profile headini değiştirdi.</td>
    <td>“Metric profile changed elsewhere” warning; current vs pending summary gösterilir.</td>
    <td>409/412; mutation/overwrite yok.</td>
    <td>Reload current revision; kişisel profile yeniden uygula veya yetkiliyse explicit overwrite revision oluştur.</td>
  </tr>
  <tr>
    <td>Registry availability change</td>
    <td>Seçili code artık SELECTABLE değil.</td>
    <td>Metric “Unavailable in current registry” olarak disabled/unchecked işaretlenir; Apply blocked.</td>
    <td>Result MetricValue silinmez; active profile invalid code ile render edilmez.</td>
    <td>Geçerli metric seçerek repair revision oluştur.</td>
  </tr>
  <tr>
    <td>No data for selected metric</td>
    <td>Resultta selected metric için value yok veya null behavior üretmiş.</td>
    <td>Card “Not available”, “No qualifying trades” veya “Not computed” gösterir; 0 yazılmaz.</td>
    <td>Profile aynı kalır; engine geriye dönük hesaplama yapmaz.</td>
    <td>Metric detaili/manifesti incele veya başka görünür metric seç.</td>
  </tr>
  <tr>
    <td>Unauthorized</td>
    <td>Caller profileı veya workspace defaultu revise etmeye yetkili değil.</td>
    <td>Controls hidden/disabled UX olabilir; server error authoritative.</td>
    <td>403/404; audit-relevant denial kaydı policyye göre tutulabilir.</td>
    <td>Own profile kullan veya Admin workspace policy ile işlem yap.</td>
  </tr>
  <tr>
    <td>Agent schema request</td>
    <td>Agent Resulta API/tool üzerinden erişir.</td>
    <td>Human UI profile statei değiştirilmez.</td>
    <td>Agent metric_codes / metric registry version ister; run ve engine değişmez.</td>
    <td>Agent result yorumunu ayrı artifact olarak kaydeder.</td>
  </tr>
</table>

# 5. Field Contract Matrix: Alanlar, Varsayılanlar, Zorunluluk ve Dependency

Bu sayfa klasik isim/parametre formu değildir. V18de yıldız (*) taşıyan alan yoktur. Productionda Apply Selection commandi için `selected_metric_codes` alanı zorunludur; bu alan UIda checkbox grubu olarak temsil edilir. Master açık minimum sayı vermediği için aşağıdaki en az bir metric kuralı Implementation Decisiondır.

<table>
  <tr>
    <th>Implementation Decision - Non-Canonical Gap Resolution. Result Summarynin boş bir container haline gelmesini engellemek için profile revision kaydedilirken en az bir `SELECTABLE` metric seçilmelidir. Kullanıcı tüm checkboxları kaldırdığında Apply Selection bloklanır; mevcut canonical profile korunur. Gerekçe: Bu sayfanın amacı Result görünümünü düzenlemektir, Result Summaryyi anlamsızlaştırmak değildir.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Alan / kontrol</th>
    <th>UI tipi ve V18 default</th>
    <th>Zorunluluk / koşul</th>
    <th>Production payload</th>
    <th>Validation / dependency</th>
  </tr>
  <tr>
    <td>Metric checkboxları</td>
    <td>Checkbox; dokuz mevcut metricin tümü başlangıçta checked. Locked durumda disabled.</td>
    <td>UIda * yok. Apply için `selected_metric_codes` her zaman zorunlu; en az 1 seçim gerekir.</td>
    <td>`selected_metric_codes: metric_code[]`; sıra registry `display_order` ile normalize edilir.</td>
    <td>Her code MetricDefinitionda var ve `availability_status=selectable` olmalı; duplicate kabul edilmez.</td>
  </tr>
  <tr>
    <td>Current metric label</td>
    <td>Read-only label; V18 English display name.</td>
    <td>Zorunlu değil.</td>
    <td>Payloada display string girmez; code backend truth sourcedur.</td>
    <td>UI text registry `display_name`den gelir.</td>
  </tr>
  <tr>
    <td>Max Stop Streak helper</td>
    <td>Visible small helper only for this row.</td>
    <td>Zorunlu değil.</td>
    <td>Yok.</td>
    <td>Helper, canonical stop streak tanımıyla çelişemez.</td>
  </tr>
  <tr>
    <td>Future Version Metrics listesi</td>
    <td>Non-interactive reference list; V18de checkbox yok.</td>
    <td>Seçilemez; Apply payloadına giremez.</td>
    <td>Yok; registry queryden `future/experimental` entries.</td>
    <td>SELECTABLE değilse code profile revisiona dahil edilemez.</td>
  </tr>
  <tr>
    <td>Apply Selection</td>
    <td>Button. V18 unlocked/locked farkını handler içinde kontrol eder.</td>
    <td>Unlocked + edit yetkisi + valid selection koşulunda kullanılabilir.</td>
    <td>`profile_id`, `expected_profile_revision_id`, `selected_metric_codes`, `is_locked` korunur, `idempotency_key`.</td>
    <td>0 selection, stale revision, locked, policy denied, invalid registry code bloklar.</td>
  </tr>
  <tr>
    <td>Lock Metrics</td>
    <td>Button. V18de global `metricsLocked=true`.</td>
    <td>Unlocked + edit yetkisi.</td>
    <td>Yeni revision: selected code dizisi aynı, `is_locked=true`.</td>
    <td>Lock security değildir; stale/policy check yine zorunlu.</td>
  </tr>
  <tr>
    <td>Unlock Metrics</td>
    <td>Button. V18de global `metricsLocked=false`.</td>
    <td>Locked + edit yetkisi.</td>
    <td>Yeni revision: selected code dizisi aynı, `is_locked=false`.</td>
    <td>Sadece profileı revise etmeye yetkili caller.</td>
  </tr>
  <tr>
    <td>Status line</td>
    <td>Read-only metin. V18de editable/locked ve selected count.</td>
    <td>Her zaman görünür.</td>
    <td>Yok; canonical profile response projeksiyonu.</td>
    <td>Count client seçiminden değil server response selected codesdan render edilir.</td>
  </tr>
</table>

## 5.1 Production profile payload ve state layering

<table>
  <tr>
    <th>ResultViewMetricProfileRoot {<br/>  profile_id, scope: user | workspace_default | system_default, owner_principal_id | null,<br/>  lifecycle_state, current_revision_id, created_at, updated_at<br/>}<br/><br/>ResultViewMetricProfileRevision {<br/>  profile_revision_id, profile_id, selected_metric_codes[], display_order[],<br/>  is_locked, metric_definition_registry_version, created_by_principal_id, created_at,<br/>  previous_revision_id, audit_correlation_id<br/>}</th>
  </tr>
</table>

State katmanları: (1) checkboxların local UI draftı, (2) serverdan yüklenen canonical current profile revision, (3) append-only historical profile revisions, (4) immutable Result MetricValue kayıtlarıdır. Local checkbox değişikliği yalnız Apply başarılı olunca persistencea geçer. Backtest Resultdaki metric value, profile revisiondan bağımsız immutable source of truth olarak kalır.

# 6. Information Content Catalog ve Nihai UI Metinleri

V18 Arrange Metrics ekranında görünür bir ⓘ bilgi butonu yoktur. Bu nedenle V18 info-button envanteri boştur. Production V1, icon eklemek zorunda değildir; fakat metric meaning, availability ve lock davranışı klavye ile erişilebilir helper/tooltip veya `aria-describedby` içeriğiyle açıklanmalıdır. Aşağıdaki metinler yeni ⓘ/tooltip eklenirse doğrudan UIya yerleştirilecek nihai içeriktir.

<table>
  <tr>
    <th>Info key / UI alanı</th>
    <th>Panel başlığı</th>
    <th>Nihai UI metni</th>
  </tr>
  <tr>
    <td>arrangeMetricsInfo</td>
    <td>Arrange Metrics</td>
    <td>Choose which currently available performance metrics appear in Backtest Results. This setting changes only the result view. It does not change the backtest engine, the metrics calculated for a run, or any saved Backtest Result.</td>
  </tr>
  <tr>
    <td>metricAvailabilityInfo</td>
    <td>Metric availability</td>
    <td>Only metrics marked Selectable in the metric registry can be added to this profile. Future and Experimental metrics may be listed for reference, but they cannot be selected until their capability and calculation contract are activated.</td>
  </tr>
  <tr>
    <td>metricLockInfo</td>
    <td>Lock Metrics</td>
    <td>Locking prevents accidental changes to this metric profile. It is a preference, not a permission grant. You can unlock the profile only when you are allowed to edit it.</td>
  </tr>
  <tr>
    <td>netProfitInfo</td>
    <td>Net Profit</td>
    <td>Net Profit is final equity minus initial equity after realized PnL, fees, commissions, funding, spread, slippage, and every cost included by the run manifest.</td>
  </tr>
  <tr>
    <td>maxDrawdownInfo</td>
    <td>Max Drawdown</td>
    <td>Max Drawdown is the largest peak-to-trough decline on the equity curve. The canonical value is stored as an absolute decimal; the UI may display it with a minus sign.</td>
  </tr>
  <tr>
    <td>romadInfo</td>
    <td>ROMAD</td>
    <td>ROMAD is return over maximum drawdown. When maximum drawdown is zero, ROMAD is not shown as infinity; it is reported as Not available with a no_drawdown status.</td>
  </tr>
  <tr>
    <td>winRateInfo</td>
    <td>Win Rate</td>
    <td>Win Rate is winning closed trade roots divided by winning plus losing closed trade roots. Breakeven trades are stored separately and are excluded from the default denominator.</td>
  </tr>
  <tr>
    <td>profitFactorInfo</td>
    <td>Profit Factor</td>
    <td>Profit Factor is gross profit divided by absolute gross loss. When there are no losing trades, it is reported as Not available with a no_losing_trade status rather than as infinity.</td>
  </tr>
  <tr>
    <td>totalTradesInfo</td>
    <td>Total Trades</td>
    <td>Total Trades counts fully closed trade roots. Scaling legs, partial exits, and multiple fills do not create extra trade roots.</td>
  </tr>
  <tr>
    <td>totalStopsInfo</td>
    <td>Total Stops</td>
    <td>Total Stops counts completed trade roots whose terminal close reason category is STOP_LOSS. A partial stop leg is retained in diagnostics but does not increase this root-level metric by itself.</td>
  </tr>
  <tr>
    <td>maxStopStreakInfo</td>
    <td>Max Stop Streak</td>
    <td>Max Stop Streak is the longest consecutive sequence of fully closed trade roots whose terminal close reason category is STOP_LOSS. A losing trade closed by normal exit logic does not increase this streak and ends it.</td>
  </tr>
  <tr>
    <td>totalWinningTradesInfo</td>
    <td>Total Winning Trades</td>
    <td>Total Winning Trades counts fully closed trade roots with net PnL greater than zero after fees, funding, and all run-manifest costs.</td>
  </tr>
</table>

## 6.1 Placeholder, helper, warning, toast ve error metinleri

<table>
  <tr>
    <th>Durum</th>
    <th>Nihai UI metni</th>
    <th>Kullanım</th>
  </tr>
  <tr>
    <td>Page helper</td>
    <td>Choose which currently available performance metrics appear in Backtest Results. This setting changes the view only; it does not recalculate any result.</td>
    <td>Başlık altında.</td>
  </tr>
  <tr>
    <td>Default fallback helper</td>
    <td>Using the system default metric profile. Save a selection to create your personal profile.</td>
    <td>Personal profile root yoksa.</td>
  </tr>
  <tr>
    <td>Editable status</td>
    <td>Metrics are editable. Selected metric count: {count}.</td>
    <td>Unlocked canonical revision.</td>
  </tr>
  <tr>
    <td>Locked status</td>
    <td>Metrics are locked. Selected metric count: {count}.</td>
    <td>Locked canonical revision.</td>
  </tr>
  <tr>
    <td>Saving</td>
    <td>Saving metric profile...</td>
    <td>Apply/lock/unlock pending.</td>
  </tr>
  <tr>
    <td>Apply success</td>
    <td>Metric profile updated. {count} metrics will appear in Result views where values are available.</td>
    <td>Revision success.</td>
  </tr>
  <tr>
    <td>Lock success</td>
    <td>Metric profile locked. Selections are protected from accidental edits.</td>
    <td>Lock revision success.</td>
  </tr>
  <tr>
    <td>Unlock success</td>
    <td>Metric profile unlocked. You can edit the selected metrics.</td>
    <td>Unlock revision success.</td>
  </tr>
  <tr>
    <td>Minimum selection error</td>
    <td>Select at least one available metric before applying this profile.</td>
    <td>0 selectable metric selected.</td>
  </tr>
  <tr>
    <td>Metric availability error</td>
    <td>{metric_name} is not selectable in the current metric registry and cannot be applied.</td>
    <td>future/experimental/unknown code.</td>
  </tr>
  <tr>
    <td>Stale warning</td>
    <td>Metric profile changed elsewhere. Reload the latest profile before saving your changes.</td>
    <td>409/412 concurrency response.</td>
  </tr>
  <tr>
    <td>Permission error</td>
    <td>You do not have permission to change this metric profile.</td>
    <td>403/404 policy result.</td>
  </tr>
  <tr>
    <td>Metric value null</td>
    <td>Not available</td>
    <td>Generic null metric value; use more specific status below when supplied.</td>
  </tr>
  <tr>
    <td>No qualifying trades</td>
    <td>No qualifying trades</td>
    <td>Metric denominator requires trade roots but none qualify.</td>
  </tr>
  <tr>
    <td>Not computed</td>
    <td>Not computed for this result</td>
    <td>Metric definition existed but this immutable result was not calculated with it.</td>
  </tr>
  <tr>
    <td>Registry repair warning</td>
    <td>One or more selected metrics are unavailable in the current registry. Choose replacement metrics and apply a new profile revision.</td>
    <td>Registry status drift.</td>
  </tr>
</table>

# 7. Button, Command ve State Sözleşmesi

<table>
  <tr>
    <th>UI action</th>
    <th>Production command / query</th>
    <th>Precondition</th>
    <th>Disabled / loading</th>
    <th>Success, error, audit</th>
  </tr>
  <tr>
    <td>Open Arrange Metrics</td>
    <td>GET `/metric-definitions?availability=selectable,future,experimental`; GET resolved profile for caller scope.</td>
    <td>Authenticated caller with Result view context.</td>
    <td>Page loading state; no stale local selection reused.</td>
    <td>Returns registry + resolved profile + permissions. `METRIC_PROFILE_VIEWED` audit optional by policy.</td>
  </tr>
  <tr>
    <td>Apply Selection</td>
    <td>POST `/metric-profiles/{profile_id}/revisions`</td>
    <td>Can edit target scope; profile unlocked; min 1 valid SELECTABLE code; `expected_profile_revision_id`.</td>
    <td>Pending disables checkbox/actions and duplicate submit; uses idempotency key.</td>
    <td>New profile revision returned. Audit `METRIC_PROFILE_UPDATED`. 422 validation, 409/412 stale, 403 policy errors structured.</td>
  </tr>
  <tr>
    <td>Lock Metrics</td>
    <td>POST `/metric-profiles/{profile_id}/revisions` with same selection and `is_locked=true`.</td>
    <td>Can edit target; current profile unlocked; expected_profile_revision_id matches.</td>
    <td>Lock disabled while pending or already locked.</td>
    <td>New locked revision; audit `METRIC_PROFILE_UPDATED` with reason `lock`.</td>
  </tr>
  <tr>
    <td>Unlock Metrics</td>
    <td>POST `/metric-profiles/{profile_id}/revisions` with same selection and `is_locked=false`.</td>
    <td>Can edit target; profile locked; expected_profile_revision_id matches.</td>
    <td>Unlock disabled while pending or already unlocked.</td>
    <td>New unlocked revision; audit `METRIC_PROFILE_UPDATED` with reason `unlock`.</td>
  </tr>
  <tr>
    <td>Read result metrics</td>
    <td>GET `/backtest-results/{result_id}/metrics`</td>
    <td>Can view Result.</td>
    <td>No client fallback calculation.</td>
    <td>Returns MetricDefinition metadata + immutable canonical values + display/null hints.</td>
  </tr>
  <tr>
    <td>Agent metric schema request</td>
    <td>Tool/API: `result_metrics.get` with `result_id`, requested metric codes and schema version.</td>
    <td>Agent can view Result; code allowed by registry/query policy.</td>
    <td>No UI dependency.</td>
    <td>Returns canonical data bundle; Agent creates separate Artifact for interpretation.</td>
  </tr>
</table>

<table>
  <tr>
    <th>ApplyMetricProfileSelection command<br/>{<br/>  profile_id,<br/>  expected_profile_revision_id,<br/>  selected_metric_codes: [&quot;net_profit&quot;, &quot;max_drawdown&quot;, &quot;romad&quot;],<br/>  display_order: [&quot;net_profit&quot;, &quot;max_drawdown&quot;, &quot;romad&quot;],<br/>  is_locked: false,<br/>  idempotency_key<br/>}<br/><br/>HTTP transport: If-Match: &lt;profile-revision-etag&gt;<br/>Conflict response: 409 METRIC_PROFILE_STALE or 412 PRECONDITION_FAILED</th>
  </tr>
</table>

# 8. Kullanıcı Akışları

## 8.1 İlk açılış ve personal profile fallback

- Kullanıcı Performance Metrics > Arrange Metrics seçer.

- Frontend yalnız local V18 arrayine güvenmeden serverdan MetricDefinition registry ve resolved Result View Metric Profileı ister.

- Personal profile yoksa system default profile uygulanır; dokuz selectable metric registry sırası ile checked render edilir.

- Kullanıcı hiçbir seçim yapmadan Result ekranına dönerse default profile ile görünüm devam eder; Result ve engine değişmez.

- Kullanıcı seçimi değiştirip Apply Selectiona basarsa server personal profile rootu ve ilk immutable revisionı transaction içinde oluşturur; canonical response UIyı yeniden hydrate eder.

## 8.2 Seçim değişikliği, Apply ve Result görünümü

- Kullanıcı örneğin Profit Factor ve Total Stops checkboxlarını kaldırır; bu değişim yalnız local UI draftıdır.

- Apply Selection preflightı en az bir selected metric, registry availability, profile lock, scope policy ve concurrencyyi kontrol eder.

- Başarılı save yeni profile revisionı üretir ve “Metric profile updated...” toastı gösterilir.

- Açılan Result detaili, yalnız yeni profileda seçili ve Resultta mevcut value taşıyan metric kartlarını registry order ile gösterir.

- MetricValue kayıtları, Result Summary, Result manifest, Trade Ledger, diagnostics veya export değişmez; yeni Backtest Run başlamaz.

## 8.3 Lock / unlock

- Editable profileda kullanıcı Lock Metrics seçer.

- Server current selected code dizisini koruyarak `is_locked=true` ile yeni revision yazar ve audit event üretir.

- UI checkboxları ve Apply düğmesini disabled gösterir; Unlock enabled kalır.

- Yetkili editor Unlock Metrics seçerse yeni unlocked revision oluşur. Locku açmak/kapamak Resultun veya enginein security boundarysi değildir.

## 8.4 Future metric ve registry repair

- Kullanıcı Future Version Metrics listesindeki bir metricin görünür olduğunu görür; satır selectable değildir.

- Frontend bu codeu Apply payloadına koymaz; server da SELECTABLE olmayan codeu 422 ile reddeder.

- Bir registry değişikliği önceki personal profiledaki codeu unavailable yaparsa historical revision korunur; aktif profil warning stateine geçer.

- Kullanıcı geçerli replacement metric seçip Apply ile repair revision oluşturur. Resultta geçmiş metric value geriye dönük oluşturulmaz.

## 8.5 Stale/concurrency ve permission recovery

- Kullanıcı iki farklı tarayıcı sekmesinde aynı profileı açar.

- İlk sekme yeni revision kaydeder; ikinci sekme eski `expected_profile_revision_id` ile Apply yapar.

- Backend mutation yapmadan 409/412 stale response ve latest revision summary döner.

- İkinci sekme current profileı reload eder, seçim farkını kullanıcıya gösterir ve userın tekrar Apply yapmasını ister. Silent overwrite yasaktır.

- Workspace default için User/Supervisor mutation denemesi server policy ile reddedilir; user kendi profileına dönebilir.

# 9. Production Backend ve Domain Davranışı

Metric calculation engine/result materialization katmanında gerçekleşir. Arrange Metrics yalnız bu immutable `MetricValue[]` setinin UI projectionını seçer. `MetricDefinition` registry, formula versiyonu ve null behavior ile calculation/display arasında açık sözleşme kurar; frontendte `if (metricName === ...)` zincirleri veya browserda formula hesaplama yasaktır.

## 9.1 Domain ilişkisi ve data flow

<table>
  <tr>
    <th>BacktestRun (succeeded)<br/>  -&gt; BacktestResult (immutable)<br/>     -&gt; ResultSummary + MetricValue[] (immutable, registry-linked)<br/>     -&gt; ResultManifestSnapshot (metric_definition_set_version + profile provenance)<br/><br/>ResultViewMetricProfileRoot (user/workspace/default)<br/>  -&gt; ResultViewMetricProfileRevision[] (mutable preference history)<br/>  -&gt; Result detail projection = MetricValue[] filtered/ordered by active profile</th>
  </tr>
</table>

Result manifestteki `result_view_metric_profile_id`, run/result üretim anındaki profile provenance bilgisidir; active UI, aynı Result için kullanıcının güncel yetkili profile revisionını kullanarak presentation yapabilir. Bu durum metric values veya manifest hashini değiştirmez. Profile, resultun semantic doğruluğu veya run reproducibility için input gate değildir.

## 9.2 MetricDefinition registry ve canonical metric sözleşmesi

<table>
  <tr>
    <th>Metric code</th>
    <th>Formula / aggregation özeti</th>
    <th>Null / özel davranış</th>
    <th>Display notu</th>
  </tr>
  <tr>
    <td>net_profit</td>
    <td>final_equity - initial_equity; realized PnL, fee, commission, funding, spread/slippage ve manifest maliyetleri dahildir.</td>
    <td>Resultta yoksa Not available; browserda yeniden hesaplanmaz.</td>
    <td>Yüzde formatı initial_equity denominatorına bağlıdır.</td>
  </tr>
  <tr>
    <td>max_drawdown</td>
    <td>Equity curvedeki en büyük peak-to-trough düşüş.</td>
    <td>Value absolute decimaldir.</td>
    <td>UI -18.1% gibi negatif gösterir; stored value negatif değildir.</td>
  </tr>
  <tr>
    <td>romad</td>
    <td>net_profit_percent / abs(max_drawdown_percent).</td>
    <td>Max drawdown=0 ise null + `no_drawdown`; infinity yasak.</td>
    <td>Registry unit/formatı uygulanır.</td>
  </tr>
  <tr>
    <td>win_rate</td>
    <td>Winning closed trade roots / (winning + losing closed trade roots).</td>
    <td>Denominator=0 ise null.</td>
    <td>Breakeven ayrı sayılır; default denominatora girmez.</td>
  </tr>
  <tr>
    <td>profit_factor</td>
    <td>gross_profit / abs(gross_loss).</td>
    <td>Gross loss=0 ise null + `no_losing_trade`; infinity yasak.</td>
    <td>Gross/net kavramı backend formula contractına bağlıdır.</td>
  </tr>
  <tr>
    <td>total_trades</td>
    <td>Fully closed trade root count.</td>
    <td>No qualifying trades olursa relevant null/zero semantics registryde tanımlı olur.</td>
    <td>Fills, legs, partial exits ayrı trade sayılmaz.</td>
  </tr>
  <tr>
    <td>total_stops</td>
    <td>Terminal exit reason category STOP_LOSS olan completed trade roots.</td>
    <td>Partial stop leg metrici tek başına artırmaz.</td>
    <td>Stop reason mapping canonicaldır.</td>
  </tr>
  <tr>
    <td>max_stop_streak</td>
    <td>Closure time sırasındaki en uzun ardışık terminal STOP_LOSS trade root dizisi.</td>
    <td>Stop olmayan terminal close streaki sıfırlar.</td>
    <td>Consecutive losses ile aynı metric değildir.</td>
  </tr>
  <tr>
    <td>total_winning_trades</td>
    <td>Net PnL &gt; 0 completed trade root count.</td>
    <td>No qualifying tradesde appropriate null/zero behavior registryde.</td>
    <td>Fee/funding sonrası net sonuç kullanılır.</td>
  </tr>
</table>

## 9.3 Profile root/revision lifecycle

<table>
  <tr>
    <th>Olay</th>
    <th>Root / revision davranışı</th>
    <th>Result / engine etkisi</th>
    <th>Audit</th>
  </tr>
  <tr>
    <td>Profile resolve</td>
    <td>Personal root varsa current revision; yoksa system default resolve edilir.</td>
    <td>Yalnız UI projection.</td>
    <td>Read audit optional.</td>
  </tr>
  <tr>
    <td>Apply selection</td>
    <td>Current head korunur; yeni append-only profile revision yazılır.</td>
    <td>Result MetricValue değişmez; run başlatılmaz.</td>
    <td>`METRIC_PROFILE_UPDATED`.</td>
  </tr>
  <tr>
    <td>Lock / unlock</td>
    <td>Selection aynı kalabilir; yalnız `is_locked` değişikliği yeni revisiondır.</td>
    <td>Result/engine etkisi yok.</td>
    <td>`METRIC_PROFILE_UPDATED` + reason.</td>
  </tr>
  <tr>
    <td>Registry status drift</td>
    <td>Historical profile revision korunur; active resolver unavailable codeu UIda repair warninge düşürür.</td>
    <td>Engine geçmiş Resultu değiştirmez.</td>
    <td>Registry/profile compatibility event.</td>
  </tr>
  <tr>
    <td>Default profile update</td>
    <td>Default root silinmez; Admin yeni revision yazar.</td>
    <td>Users personal profile yoksa yeni defaultu görür; historical Result values değişmez.</td>
    <td>`METRIC_PROFILE_UPDATED` actor=Admin.</td>
  </tr>
  <tr>
    <td>Soft delete effect</td>
    <td>Bu sayfa delete action sunmaz. Generic admin maintenance ile profile root soft delete edilirse resolver fallbacka döner; default root silinemez.</td>
    <td>Result root, metric values, history, manifest ve exports korunur.</td>
    <td>Soft delete/restore only admin Trash policy.</td>
  </tr>
</table>

# 10. Agent Tool/API Eşdeğeri ve Boundary

Agent, Arrange Metrics sayfasındaki checkboxlara tıklayan bir browser automasyonu değildir. Agent sonuç araştırması için aynı canonical MetricDefinition registry ve Result metrics endpointlerini Tool Gateway/API üzerinden kullanır. İnsan Result View Metric Profileı, Agentın sürekli araştırma loopunun dependencysi değildir.

<table>
  <tr>
    <th>Agent amacı</th>
    <th>UI eşdeğeri</th>
    <th>Tool/API davranışı</th>
    <th>Sınır</th>
  </tr>
  <tr>
    <td>Metric schema keşfi</td>
    <td>Arrange Metrics sayfasındaki selectable/future listesi.</td>
    <td>`metric_definitions.list(availability, registry_version)`</td>
    <td>Agent registry bilgisini okur; UI stringini scrape etmez.</td>
  </tr>
  <tr>
    <td>Result metric okuma</td>
    <td>Result Summary metric cards.</td>
    <td>`result_metrics.get(result_id, metric_codes, include_metadata=true)`</td>
    <td>Immutable MetricValue döner; Agent formula uydurmaz veya browserda hesaplamaz.</td>
  </tr>
  <tr>
    <td>Eksik/null metric analizi</td>
    <td>Not available / Not computed UI state.</td>
    <td>`result_metrics.explain_availability(result_id, metric_code)`</td>
    <td>Agent missing value için yeni Result değeri yazmaz; diagnostic/hypothesis artifact üretir.</td>
  </tr>
  <tr>
    <td>Yeni araştırma talebi</td>
    <td>İnsan RUN/analysis akışı.</td>
    <td>`backtest_runs.request(...)` veya follow-up task queue.</td>
    <td>Metric profile değişikliği Run inputu değildir.</td>
  </tr>
  <tr>
    <td>Human-visible profile önerisi</td>
    <td>Kullanıcıya öneri vermek.</td>
    <td>AgentArtifact: `metric_profile_recommendation` + source_result_ids.</td>
    <td>Agent user/workspace metric profileını doğrudan mutate etmez; yetkili insan Apply ile karar verir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Agent parity kuralı. UI Button -&gt; API Command -&gt; Domain Service -&gt; Profile Revision zinciri insan için geçerlidir. Agent aynı sistemde Result metric data okumak için doğrudan Tool/API kullanır; ancak human presentation preferenceını UI bypass ederek değiştirmek için ayrı gizli yol kullanamaz.</th>
  </tr>
</table>

# 11. Validation, Hata ve Recovery Sözleşmesi

<table>
  <tr>
    <th>Kontrol / hata code</th>
    <th>Ne zaman oluşur</th>
    <th>Nihai kullanıcı mesajı</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>METRIC_SELECTION_EMPTY</td>
    <td>Apply payloadında seçili SELECTABLE metric yok.</td>
    <td>Select at least one available metric before applying this profile.</td>
    <td>En az bir current selectable metric seç.</td>
  </tr>
  <tr>
    <td>METRIC_CODE_UNKNOWN</td>
    <td>metric_code registryde yok.</td>
    <td>One or more selected metrics are no longer recognized by the metric registry. Reload the page and choose available metrics.</td>
    <td>Registryyi ve profileı reload et.</td>
  </tr>
  <tr>
    <td>METRIC_NOT_SELECTABLE</td>
    <td>Code future/experimental veya UIa kapalı.</td>
    <td>{metric_name} is not selectable in the current metric registry and cannot be applied.</td>
    <td>Güncel selectable code seç.</td>
  </tr>
  <tr>
    <td>METRIC_PROFILE_LOCKED</td>
    <td>Locked revisiona Apply selection gönderildi.</td>
    <td>Metrics are locked. Unlock this profile before changing the selection.</td>
    <td>Yetkili editor Unlock yapar.</td>
  </tr>
  <tr>
    <td>METRIC_PROFILE_STALE</td>
    <td>Expected profile revision current head ile eşleşmez.</td>
    <td>Metric profile changed elsewhere. Reload the latest profile before saving your changes.</td>
    <td>Reload, compare, then explicit new revision.</td>
  </tr>
  <tr>
    <td>PROFILE_EDIT_DENIED</td>
    <td>Caller own profile/workspace default için mutate policyi geçemedi.</td>
    <td>You do not have permission to change this metric profile.</td>
    <td>Own profile kullan veya Admin policyi.</td>
  </tr>
  <tr>
    <td>METRIC_REGISTRY_UNAVAILABLE</td>
    <td>Registry query/dependency geçici başarısız.</td>
    <td>Metric definitions are temporarily unavailable. Try again.</td>
    <td>Retry; cached stale listten mutation yapma.</td>
  </tr>
  <tr>
    <td>RESULT_METRIC_UNAVAILABLE</td>
    <td>Resultta metric value yok/null.</td>
    <td>Not computed for this result.</td>
    <td>Manifest/definition availabilityyi incele; placeholder value oluşturma.</td>
  </tr>
  <tr>
    <td>IDEMPOTENCY_REPLAY</td>
    <td>Aynı Apply request retry edildi.</td>
    <td>Metric profile update already completed. Latest profile has been loaded.</td>
    <td>Canonical responseu kullan; ikinci revision üretme.</td>
  </tr>
</table>

# 12. Lifecycle, Audit ve Trash Etkileri

Arrange Metrics tarafından oluşturulan şey Backtest Result değil, Result View Metric Profile revisionıdır. Bu nedenle bir profile updatein soft delete, restore veya audit etkisi Result rootun immutable kanıt zincirinden ayrı tutulur.

<table>
  <tr>
    <th>Nesne</th>
    <th>Bu sayfada mutasyon</th>
    <th>Soft delete / Trash</th>
    <th>Historical integrity</th>
  </tr>
  <tr>
    <td>BacktestResult</td>
    <td>Yok. Read-only metric values only.</td>
    <td>Result silme bu sayfanın actionı değildir. Result soft delete ayrı policy ile Admin Trash alanından yönetilir.</td>
    <td>Result manifest, MetricValue, trade ledger ve artifact hashleri profile değişiminden etkilenmez.</td>
  </tr>
  <tr>
    <td>ResultViewMetricProfileRoot</td>
    <td>İlk Applyde create; sonraki actions revision append.</td>
    <td>V18de delete UI yok. Default profile silinemez. Generic profile maintenance soft delete yaparsa Trash Admin-onlydir.</td>
    <td>Geçmiş profile revisions audit/provenance için korunur.</td>
  </tr>
  <tr>
    <td>ResultViewMetricProfileRevision</td>
    <td>Apply/Lock/Unlock ile append-only create.</td>
    <td>Revision doğrudan silinmez; active head controlled update ile ilerler.</td>
    <td>Önceki revisionlar Result valueyi değiştirmez.</td>
  </tr>
  <tr>
    <td>MetricDefinition</td>
    <td>Bu sayfada mutate edilmez.</td>
    <td>Registry lifecycle başka yönetim alanındadır.</td>
    <td>Formula/version availability değişimleri result manifest/registry version ile izlenir.</td>
  </tr>
</table>

Zorunlu audit alanları: actor principal, profile_id, old_revision_id, new_revision_id, old/new selected metric codes, old/new `is_locked`, scope, registry version, request correlation/idempotency key, timestamp ve policy sonucu. `METRIC_PROFILE_UPDATED` eventi Result metric değerlerini taşımaz; yalnız preference mutationını kaydeder.

# 13. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Konu</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Metric list source</td>
    <td>`availableMetrics` ve `futureMetrics` JavaScript dizileri.</td>
    <td>MetricDefinition registry; code, unit, formula_version, availability, null behavior ve display order server source of truth.</td>
    <td>HTML label/prototype listesi korunur; persistence ve availability registryye taşınır.</td>
  </tr>
  <tr>
    <td>Default selection</td>
    <td>Dokuz current metric checkboxı checked.</td>
    <td>Personal profile yoksa system default profile fallback; default silinmez, revisionlanır.</td>
    <td>V18 varsayılanı Production system default initial revisionına maplenir.</td>
  </tr>
  <tr>
    <td>Apply</td>
    <td>DOM checkboxları `selectedMetrics` browser arrayine yazılır; persistence yok.</td>
    <td>Append-only Result View Metric Profile revision commandi; authorization, validation, optimistic concurrency, audit.</td>
    <td>Prototype immediate UI effecti korunur, ancak canonical server response sonrası yapılır.</td>
  </tr>
  <tr>
    <td>Display order</td>
    <td>Checkbox DOM sırası output sırası olur; reorder control yok.</td>
    <td>Profile revision `display_order` taşır; current V1 UI selectionı registry display order ile normalize eder.</td>
    <td>Implementation Decision: V1de drag-reorder eklenmez; explicit reorder capability ayrı UI tasarımı olmadan açılmaz.</td>
  </tr>
  <tr>
    <td>Lock</td>
    <td>Tek global `metricsLocked` boolean; tüm düğmeler görünür.</td>
    <td>Per-profile revision `is_locked`; security değildir; policy her commandde serverda değerlendirilir.</td>
    <td>Locked statein UX amacı korunur; global browser boolean persistence/doğruluk kaynağı değildir.</td>
  </tr>
  <tr>
    <td>Future metrics</td>
    <td>“Future version only” listesi V10 ifadesiyle hard-coded.</td>
    <td>Registry availability `future` / `experimental`; not selectable, no fake value.</td>
    <td>V10 metni Productionda “This release” veya “Production V1” olarak düzeltilir.</td>
  </tr>
  <tr>
    <td>Result impact</td>
    <td>Current in-memory Backtest Details gridi değişir.</td>
    <td>Active Result viewer only filters/orders immutable MetricValue[]. Engine/run/result materialization değişmez.</td>
    <td>CR-07 gereği profile, canonical metric seti eksiltmez veya formula değiştirmez.</td>
  </tr>
</table>

# 14. Kodcu AI için Implementation Rules

- Metric isimlerini UI componentlerinde serbest string veya if/else zinciri olarak saklama. Tüm metric seçimleri `MetricDefinition.metric_code` üzerinden yapılmalıdır.

- Arrange Metrics, Backtest enginein hesaplayacağı canonical metric kapsamını değiştirmemelidir. Profile değişimi RUN, Ready Check, worker veya materialization job tetiklemez.

- Bir Backtest Result tamamlandıktan sonra MetricValue, ResultSummary, manifest hash veya formula outputu profile değişimiyle mutate edilmemelidir.

- Current metric checkboxları sadece registryde `availability_status=selectable` olan kayıtlar için render edilmelidir. Future/experimental kayıtlar Apply payloadına eklenemez.

- V18deki future metric listesi sahte numeric result, placeholder formula veya browser fallback hesaplama üretemez.

- Apply Selection, Lock Metrics ve Unlock Metrics yalnız serverda başarılı append-only profile revision sonrasında success statee geçmelidir. UI, canonical response ile yeniden hydrate edilmelidir.

- Profile revisiona en az bir SELECTABLE metric code yazılmalıdır. Boş seçimi kabul etmek yerine mevcut canonical profile korunmalı ve validation mesajı gösterilmelidir.

- Selected codes duplicate kabul etmemeli; server registry display order ile deterministic `display_order` üretmelidir. Mevcut V1 ekranında tanımsız drag-and-drop order semantiği eklenmemelidir.

- Locked state, authorization değildir. Server profile edit policy, scope, owner ve expected_profile_revision_id kontrolünü Lock/Unlock dahil her mutationda tekrar uygulamalıdır.

- Concurrency için domain payload `expected_profile_revision_id`, HTTP transportta `If-Match`/ETag ve retryde `idempotency_key` birlikte kullanılmalıdır. Stale update silent overwrite yapmamalıdır.

- Metric null değerleri 0, infinity veya uydurulmuş default olarak render edilmemelidir. Registry null behaviorına göre Not available, No qualifying trades veya Not computed gösterilmelidir.

- Agent, insan Result View Metric Profileını UI bypass ederek mutate etmemelidir. Agent metric schema/value okumayı Tool/API ile yapmalı; önerisini ayrı provenance taşıyan AgentArtifact olarak kaydetmelidir.

- Default profile silinmemelidir. Bu sayfa delete action sunmaz; generic soft delete varsa Resultlara değil yalnız profile rootuna uygulanır ve Trash Admin-only policyde kalır.

- Result detail, aktif Mainboard veya browser `selectedMetrics` memorysinden değil; immutable Result MetricValue seti ile resolved profile revisionın server projectionından render edilmelidir.

- Metric registry availability veya formula version değişimi historical Resultların anlamını sessizce değiştirmemelidir. Result manifestteki metric_definition_set_version korunmalıdır.

# 15. Acceptance Tests

<table>
  <tr>
    <th>No</th>
    <th>Test senaryosu</th>
    <th>Beklenen sonuç</th>
  </tr>
  <tr>
    <td>1</td>
    <td>Default profile resolution: User personal profile olmadan Arrange Metrics açar.</td>
    <td>Dokuz selectable V18 metric registry order ile checked görünür; Apply edilene kadar personal root oluşturulmaz.</td>
  </tr>
  <tr>
    <td>2</td>
    <td>Presentation separation: User Max Stop Streaki profiledan kaldırır.</td>
    <td>MetricValue kaydı silinmez; Result detailde sadece ilgili card gizlenir.</td>
  </tr>
  <tr>
    <td>3</td>
    <td>No engine impact: Profile change sonrası READY/RUN state incelenir.</td>
    <td>Backtest Run oluşmaz; Result manifest ve engine outputs değişmez.</td>
  </tr>
  <tr>
    <td>4</td>
    <td>Future metric block: User Sharpe Ratioyu seçmeye/submit etmeye çalışır.</td>
    <td>UI checkbox sunmaz; crafted API payload 422 `METRIC_NOT_SELECTABLE` döner.</td>
  </tr>
  <tr>
    <td>5</td>
    <td>Minimum selection: User dokuz checkboxın tümünü kaldırıp Apply yapar.</td>
    <td>UI/Server Applyi bloklar; `METRIC_SELECTION_EMPTY`; previous canonical revision korunur.</td>
  </tr>
  <tr>
    <td>6</td>
    <td>Lock behavior: Editable profile Lock Metrics ile kilitlenir.</td>
    <td>Yeni locked revision oluşur; checkbox/Apply disabled, Unlock enabled olur; result values değişmez.</td>
  </tr>
  <tr>
    <td>7</td>
    <td>Lock is not authorization: Yetkisiz User locked workspace default profileı unlock etmeye çağırır.</td>
    <td>Server policy deny döner; lock preference role grant sağlamaz.</td>
  </tr>
  <tr>
    <td>8</td>
    <td>Stale update: İki sekme aynı profileı açar; biri Apply yapar, diğeri eski revisionla Apply yapar.</td>
    <td>İkinci çağrı 409/412 döner; silent overwrite ve ikinci revision oluşmaz.</td>
  </tr>
  <tr>
    <td>9</td>
    <td>Idempotent retry: Network timeout sonrası aynı idempotency key ile Apply tekrar gönderilir.</td>
    <td>Tek profile revision oluşur; canonical latest response döner.</td>
  </tr>
  <tr>
    <td>10</td>
    <td>Metric null: ROMAD için max drawdown=0 olan Result açılır.</td>
    <td>Card infinity/0 göstermez; Not available + no_drawdown semanticsi gösterir.</td>
  </tr>
  <tr>
    <td>11</td>
    <td>Trade semantics: Partial stop leg + normal exitli trade içeren Result okunur.</td>
    <td>Total Stops ve Max Stop Streak trade root terminal reason üzerinden doğru kalır; partial leg yalnız diagnosticsde görünür.</td>
  </tr>
  <tr>
    <td>12</td>
    <td>Registry drift: Seçili code registryde future durumuna alınır.</td>
    <td>Historical revision korunur; active profile repair warning gösterir; Apply invalid code ile başarı vermez.</td>
  </tr>
  <tr>
    <td>13</td>
    <td>Agent parity: Agent bir Result için net_profit, max_drawdown, romad ister.</td>
    <td>Tool/API registry metadata + immutable values döner; human profile değişmez ve Agent artifacti provenance taşır.</td>
  </tr>
  <tr>
    <td>14</td>
    <td>Role guard: User başka kullanıcının private workspace profileını revise etmeye çalışır.</td>
    <td>Server 403/404 policy response verir; UI hidden/disabled state tek başına koruma değildir.</td>
  </tr>
  <tr>
    <td>15</td>
    <td>Trash boundary: Admin generic maintenance ile non-default profile rootu soft delete eder.</td>
    <td>Resultlar ve metric values korunur; resolver fallbacka döner; Trash restore/purge yalnız Admindir.</td>
  </tr>
  <tr>
    <td>16</td>
    <td>V18 alignment: V18 screen açılır.</td>
    <td>Dokuz default selected metric, future reference listesi, action labels ve status wording korunur; Production V1de V10 typo düzeltilir.</td>
  </tr>
</table>

# 16. Final Consistency Check

- Master Technical Reference v1.0 ile çelişen bir davranış tanımlanmadı: Arrange Metrics yalnız Result View Metric Profile/presentation tercihidir.

- Backtest Run ile Backtest Result ayrımı korundu; profile mutationı run/result lifecycleı üretmez veya değiştirmez.

- MetricDefinition registry, immutable MetricValue ve Result View Metric Profile ayrımı açıklandı; client-side formula hesaplama yasaklandı.

- Future metrics active Production V1 capability gibi anlatılmadı; yalnız registry controlled, non-selectable reference olarak sınırlandı.

- Lock state security/yetki mekanizması gibi anlatılmadı; server-side policy ayrı korundu.

- Agentın sürekli backend aktörü olması ve Tool/API parity korundu; Agent human UI profileını mutate etmez.

- Trash etkisi yalnız profile root maintenance ile sınırlı açıklandı; Result, manifest ve historical metric values korunur; Trash Admin-onlydir.

- V18 prototype browser arraysi ile Production revision/persistence/authorization davranışı ayrı başlıkta görünür biçimde hizalandı.

- Implementation Decisionlar açık etiketlendi: minimum bir metric seçimi ve V1de registry-order display order yaklaşımı.

- Bu sayfa Results History, RUN/Backtest Results veya Future Dev sayfalarının bağımsız UIlarını yeniden tanımlamadı; yalnız çapraz dependencyleri belirtti.

<table>
  <tr>
    <th>Sonuç. Arrange Metrics, ölçüm motorunun kapsamını yöneten bir ekran değil; immutable Backtest Result verisini kullanıcı/workspace için okunabilir hale getiren revisionlı Result View Metric Profile yüzeyidir. Bu sınır korunduğunda görünüm tercihi, deneyin kanıt zincirini veya Agent araştırma doğruluğunu bozamaz.</th>
  </tr>
</table>
