---
title: "Entropia V18 — Backtest Ready Check Page Documentation v1.1"
page_number: 14
document_type: "Page implementation specification"
source_document: "Entropia_V18_Backtest_Ready_Check_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Backtest Ready Check Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | SAYFA DOKÜMANTASYONU 14/22 | BACKTEST READY CHECK
> **Original DOCX footer:** Canonical page documentation | Production V1 alignment |

ENTROPIA V18

BACKTEST READY CHECK

Sayfa Dokümantasyonu 14/22 | Mainboard Composition için immutable snapshot tabanlı preflight, readiness report, stale kontrolü ve RUN izni sözleşmesi

<table>
  <tr>
    <th>Kilit canonical karar. Backtest Ready Check bir browser form doğrulaması değildir. Server, current Mainboard Composition Drafttan transactionally immutable Composition Snapshot üretir; exact dependency revisions, policy ve engine uyumluluğunu doğrular; immutable Readiness Report saklar. RUN komutu bu raporu yalnız yardımcı bilgi olarak kullanır ve server-side preflightı tekrarlar.</th>
  </tr>
</table>

# 0. Document Control, Scope ve Source Traceability

Bu belge yalnız Backtest Ready Check yüzeyini açıklar: Mainboarddaki sabit konumlu Ready Check düğmesi, readiness durum şeridi, Passed / Failed / Warnings modalı ve bu görünümün Production V1 server-side preflight karşılığı. RUN execution lifecyclei, Result ekranı, Strategy Details formu, external import ekranları veya Portfolio / Equity Allocation ekranının kendi alanları burada yeniden dokümante edilmez; yalnız Ready Checkin bağımlılıkları olarak tanımlanır.

<table>
  <tr>
    <th>Kaynak / tür</th>
    <th>Bu sayfada kullanılan bölüm</th>
    <th>Kullanım amacı</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 - primary canonical source</td>
    <td>Module 12: Backtest Ready Check and Backtest Run Orchestration; Canonical Integration CR-03, CR-04, CR-05, CR-06, CR-07. Cross-cutting: Modules 0-5, 7-11, 13, 19-20.</td>
    <td>Readiness state, immutable snapshot/report, validator boundaries, manifest, role/policy, Agent parity, async and audit decisions.</td>
  </tr>
  <tr>
    <td>V18 main HTML - prototype evidence</td>
    <td>Fixed `.run-controls`; `runBacktestReadyCheck()`; `buildBacktestReadyReport()`; `backtestReadyStatus`; `readyCheckModal`; local `addBacktestResult()` behavior.</td>
    <td>Visible layout, labels, default client behavior, demo checks and modal text.</td>
  </tr>
  <tr>
    <td>Page Documentation Handoff v1.1</td>
    <td>Mandatory source traceability, interaction and field matrices, content catalog, validation/recovery, V18/Production separation, rules and tests.</td>
    <td>Document structure and delivery standard.</td>
  </tr>
  <tr>
    <td>2.3 Position Entry Logic example</td>
    <td>Decision hierarchy, dependency explanation, deterministic evaluation and Agent parity writing depth.</td>
    <td>Narrative and implementation precision standard only; not technical authority.</td>
  </tr>
</table>

Cross-page dependency boundary: Strategy, Trading Signal and Trade Log remain Mainboard Working Items; they are not Package Library package kinds. A ready report may validate their dependencies but does not change their ownership, revision or import lifecycle.

# 1. Amaç, Sistem İçindeki Yer ve Kapsam Sınırı

Backtest Ready Check, Active Mainboard Compositionın kendisiyle birlikte çalıştırılabilir olup olmadığını ölçen preflight katmanıdır. Kontrol; kompozisyon varlığını, selected strategy/external-object revisions, package dependencyleri, Market Data ve Research Data uygunluğunu, time/available-time kurallarını, Equity Allocationı, execution modelini ve server policyyi tek raporda birleştirir. Bir backtest sonucunun tekrarlanabilir olması için RUNdan önce bu bağlamın dondurulması gerekir.

Kanonik akış: Sistem akışı

<table>
  <tr>
    <th>Mainboard Composition Draft (mutable)<br/>  -&gt; change =&gt; readiness becomes STALE<br/>Composition Snapshot + Readiness Report (immutable)<br/>  -&gt; no blockers + same fingerprint<br/>Backtest Run Manifest (immutable, hash-pinned)<br/>  -&gt; queue -&gt; worker -&gt; event stream -&gt; Result Artifacts / Failure Record</th>
  </tr>
</table>

<table>
  <tr>
    <th>Bu sayfanın kapsamadığı alanlar. Ready Check, entry/exit/stop/sizing motor semantiğini yeniden tanımlamaz; yalnız ilgili Strategy Revisionın gerekli ve engine-compatible olduğunu denetler. RUN ve Backtest Results sayfası run lifecyclei, progress ve immutable result presentationını ayrıntılandırır. Future Dev live trading bu akışın uzantısı değildir.</th>
  </tr>
</table>

# 2. Erişim, Görünürlük, Kullanım ve Yetki

<table>
  <tr>
    <th>Actor</th>
    <th>Ready Check görünürlüğü / report view</th>
    <th>Check request ve RUN intent</th>
    <th>Server-side sınır</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Görmez; yalnız public/auth entry alanlarını kullanabilir.</td>
    <td>Yok.</td>
    <td>Authenticated human veya internal Agent principal olmadan report/snapshot üretilmez.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Kendi, explicit shared veya published kaynaklarla kurulmuş erişilebilir composition için görünür.</td>
    <td>Kendi/izinli composition için check ve run intent gönderebilir.</td>
    <td>Private revision/data/package use hakkı ayrıca doğrulanır; UI görünmesi yetki kanıtı değildir.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Shared working pagesde erişilebilir compositionları görür.</td>
    <td>Kendi veya policy ile use edebildiği composition için.</td>
    <td>Başka ownerın private draftını check/run ederek görünür kılamaz veya mutate edemez.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm erişilebilir composition/report ve audit detaylarını görür.</td>
    <td>Policyye göre tüm uygun compositionlarda request edebilir.</td>
    <td>Admin override auditlenir; report immutable kalır.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Human login kullanmaz; runtime context ile ilgili artifact/reportu okuyabilir.</td>
    <td>Tool Gateway/internal command ile check/run request verir.</td>
    <td>Human UI endpointinden gevşek veya bypass edilen ayrı validator yolu yoktur; owner/provenance kuralları korunur.</td>
  </tr>
</table>

Görünürlük veya disabled UI yalnız kullanıcı deneyimidir. `POST /compositions/{id}/readiness-checks` ve `POST /backtest-runs` endpointleri caller principal, resource view/use policy, lifecycle state ve dependency erişimini server-side yeniden doğrular.

# 3. V18 Arayüz Yerleşimi ve Gerçek Görünür Bileşenler

## 3.1 Sabit Mainboard çalışma kontrolü

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 görünümü / konumu</th>
    <th>Varsayılan durum</th>
    <th>Interaction</th>
  </tr>
  <tr>
    <td>Backtest Ready Check button</td>
    <td>Mainboardun sağ-altında, fixed `.run-controls` grubu içinde; beyaz, 124 x 66 px, üç satırlı “Backtest / Ready / Check” labelı.</td>
    <td>Enabled görünür.</td>
    <td>Click `runBacktestReadyCheck()` çağırır; local DOM taraması ile report oluşturur ve modal açar.</td>
  </tr>
  <tr>
    <td>Ready status strip</td>
    <td>Ready Check ile RUN arasında 14 x 66 px dikey şerit.</td>
    <td>Kırmızı; title: “Backtest Ready: Not Ready”.</td>
    <td>V18 `ready` CSS class ile yeşile döner ve title “Backtest Ready: Ready” olur.</td>
  </tr>
  <tr>
    <td>RUN button - adjacent control</td>
    <td>Sağda 120 x 66 px büyük “RUN” button.</td>
    <td>`locked` class ile gri, düşük opacity, cursor not-allowed.</td>
    <td>Bu belge RUNın execution akışını tanımlamaz; sadece readiness statein bu controlun UX lockunu etkilediğini açıklar.</td>
  </tr>
  <tr>
    <td>Ready Check modal overlay</td>
    <td>Click sonrası sayfa üzerinde şeffaf koyulaştırma; `ready-check-overlay`.</td>
    <td>Gizli.</td>
    <td>Overlayin dışına click modalı kapatır; iç kutuda propagation durdurulur.</td>
  </tr>
  <tr>
    <td>Ready Check modal box</td>
    <td>Max 760 px genişlik; height auto; max-height 82vh; scroll. Title: “Backtest Ready Check”.</td>
    <td>Gizli.</td>
    <td>Passed, Failed, Warnings kolonlarını ve Close buttonu gösterir.</td>
  </tr>
  <tr>
    <td>Passed card</td>
    <td>`ready-report-card` içinde yeşil tick satırları.</td>
    <td>No passed item yet. fallback metni.</td>
    <td>V18 sadece text listesi; navigable remediation veya scope linki yoktur.</td>
  </tr>
  <tr>
    <td>Failed card</td>
    <td>`ready-report-card` içinde kırmızı cross satırları.</td>
    <td>Blocker yoksa “No blocking issue detected.” yeşil metni.</td>
    <td>V18 sadece text listesi; field path, severity code veya fix action yoktur.</td>
  </tr>
  <tr>
    <td>Warnings card</td>
    <td>`ready-report-card` içinde `!` prefiksi.</td>
    <td>V18de iki statik warning eklenir.</td>
    <td>Warningler RUNı engellemez; V18de report içinde görünür.</td>
  </tr>
  <tr>
    <td>Close button</td>
    <td>Modal footer/right aligned page action.</td>
    <td>Enabled.</td>
    <td>`closeReadyCheckModal()` ile overlay `display:none`; report storage veya readiness statei değiştirmez.</td>
  </tr>
</table>

## 3.2 V18de görünmeyen fakat Production için zorunlu olan presentation alanları

Production V1 modal veya dedicated report paneli, V18deki üç kolonlu görseli koruyabilir; ancak her issue satırı severity, stable code, scope, field path, remediation action ve report fingerprint bilgisini taşımalıdır. Bu alanlar yalnız backend detail endpointinden gelir. DOMdan yeniden hesaplanmış veya UI stringlerinden türetilmiş alanlar canonical değildir.

# 4. Interaction State Matrix

<table>
  <tr>
    <th>State</th>
    <th>Aktifleşme / giriş koşulu</th>
    <th>UI davranışı</th>
    <th>Payload / backend etkisi</th>
  </tr>
  <tr>
    <td>NOT_CHECKED</td>
    <td>No current immutable report; page first load; valid report never created.</td>
    <td>Status red; RUN visually locked.</td>
    <td>No report_id is authoritative; RUN endpoint still preflight runs but UI should guide user to check.</td>
  </tr>
  <tr>
    <td>CHECKING</td>
    <td>Ready Check command accepted and snapshot/report calculation in progress.</td>
    <td>Status neutral loading treatment; Ready Check button loading/disabled; RUN locked. V18 has no real loading state.</td>
    <td>Server transactionally reads current draft; creates snapshot and aggregates deterministic validators.</td>
  </tr>
  <tr>
    <td>NOT_READY</td>
    <td>At least one BLOCKER issue.</td>
    <td>Red status; Failed card populated; RUN locked.</td>
    <td>Immutable report persisted with state NOT_READY; no run manifest or queue job is created.</td>
  </tr>
  <tr>
    <td>READY_WITH_WARNINGS</td>
    <td>No blocker; one or more WARNING issues.</td>
    <td>Green-ready treatment plus warning count/summary; RUN may be enabled.</td>
    <td>Report immutable; warnings must be copied into any later manifest after fresh preflight.</td>
  </tr>
  <tr>
    <td>READY</td>
    <td>No blocker and no warning; report fingerprint equals current composition fingerprint.</td>
    <td>Green status; RUN may be visually unlocked.</td>
    <td>Report can be supplied as optimization hint; RUN endpoint never trusts only client readiness.</td>
  </tr>
  <tr>
    <td>STALE</td>
    <td>Previously current report no longer matches composition/dependency fingerprint.</td>
    <td>Status visually distinct from READY; message: “Ready check must be run again.”; RUN locked.</td>
    <td>Old report remains historical; server rejects mismatched RUN with 409 COMPOSITION_STALE or READY_REPORT_STALE.</td>
  </tr>
  <tr>
    <td>SUPERSEDED</td>
    <td>A newer/more complete report exists for same snapshot or current context.</td>
    <td>Old report remains viewable historical record; not current.</td>
    <td>No direct mutation; new report has separate id and policy/validator version.</td>
  </tr>
  <tr>
    <td>ACCESS_DENIED / dependency inaccessible</td>
    <td>Caller cannot view/use current resource or dependency.</td>
    <td>Show permission error; no sensitive private resource details leaked.</td>
    <td>Request rejected before report issue data leaks; audit-relevant denial may be emitted.</td>
  </tr>
  <tr>
    <td>Composition soft-deleted / invalid lifecycle</td>
    <td>Composition or selected revision no longer usable.</td>
    <td>Report may remain historical; new check/run disabled.</td>
    <td>Soft-deleted/inaccessible revision cannot enter new snapshot; historical manifests retain their reference.</td>
  </tr>
</table>

<table>
  <tr>
    <th>State separation rule. Readiness state and BacktestRun lifecycle state are separate. A composition can be READY while a previous run is queued, running, failed or cancelled. Conversely, a run terminal failure does not change an immutable past report into NOT_READY.</th>
  </tr>
</table>

# 5. Field Contract Matrix: Görünür Kontroller ve Implicit Preflight Girdileri

Bu sayfada klasik input alanı yoktur. Ready Checkin gerçek girdisi, browserdaki form statei değil, serverdaki current Mainboard Composition Draft ve onun pinned dependencyleridir. Yıldız (*) yalnız bağlı sayfalardaki form requirednessini gösterir; check raporu bu zorunlulukları server-side tekrar değerlendirir.

<table>
  <tr>
    <th>Alan / UI kontrol</th>
    <th>V18 default / seçenek</th>
    <th>Requiredness / dependency</th>
    <th>Production payload ve validation</th>
  </tr>
  <tr>
    <td>`Backtest Ready Check` command button</td>
    <td>Always visible; no dropdown.</td>
    <td>Authenticated actor + usable composition gerekir.</td>
    <td>POST `/compositions/{composition_id}/readiness-checks`; current server draft snapshot alınır. Client item listesi authoritative değildir.</td>
  </tr>
  <tr>
    <td>Composition identity</td>
    <td>V18 local DOM strategy/signal/log lists.</td>
    <td>At least one enabled persisted MainboardWorkingItem required. Item kind only strategy, trading_signal, trade_log.</td>
    <td>`composition_id`; server resolves current row/version and emits `composition_snapshot_id`, `composition_fingerprint`.</td>
  </tr>
  <tr>
    <td>Expected fingerprint</td>
    <td>V18de yok.</td>
    <td>RUN intent için current composition fingerprint ile eşleşmesi koşullu zorunlu.</td>
    <td>`expected_fingerprint` on POST `/backtest-runs`; mismatch =&gt; 409 COMPOSITION_STALE.</td>
  </tr>
  <tr>
    <td>Selected report id</td>
    <td>V18de yok.</td>
    <td>Optional optimization hint; report may be omitted.</td>
    <td>`readiness_report_id` optional; server checks it belongs to composition and is current, then repeats/equivalently reuses preflight.</td>
  </tr>
  <tr>
    <td>Report state / status strip</td>
    <td>V18 red by default; green only failed list empty.</td>
    <td>No user-editable value.</td>
    <td>Derived from server state NOT_CHECKED, CHECKING, NOT_READY, READY_WITH_WARNINGS, READY, STALE, SUPERSEDED.</td>
  </tr>
  <tr>
    <td>Passed / Failed / Warnings cards</td>
    <td>Three text lists, no filtering or navigation.</td>
    <td>Report output; not input.</td>
    <td>Report summary and `issues[]`. PASS may be summary-only; BLOCKER/WARNING carry code, scope, path, message, remediation.</td>
  </tr>
  <tr>
    <td>Close modal</td>
    <td>Visible modal footer control.</td>
    <td>Always available when modal open.</td>
    <td>UI-only; never discards report or changes readiness state.</td>
  </tr>
  <tr>
    <td>Adjacent RUN UX lock</td>
    <td>`locked` when local `backtestReady=false`.</td>
    <td>Not an authorization or lifecycle decision.</td>
    <td>Actual run command requires server preflight, expected fingerprint, idempotency key and immutable manifest build.</td>
  </tr>
</table>

## 5.1 Underlying requiredness that the V18 report actually checks

<table>
  <tr>
    <th>Scope</th>
    <th>V18 DOM check</th>
    <th>Production V1 canonical condition</th>
  </tr>
  <tr>
    <td>Composition</td>
    <td>At least one Strategy, Trading Signal or Trade Log row exists.</td>
    <td>At least one enabled persisted MainboardWorkingItem exists; duplicate enabled same working object is blocked in V1 unless explicitly supported.</td>
  </tr>
  <tr>
    <td>Independent capital mode</td>
    <td>When allocation disabled, each Strategy/Trading Signal/Trade Log needs Initial Capital &gt; 0.</td>
    <td>Same principle; item-level own capital is validated only when allocation is disabled.</td>
  </tr>
  <tr>
    <td>Equity Allocation enabled</td>
    <td>Shared Initial Capital &gt; 0; Base Currency selected; Compounding Mode selected; active allocation share &gt;0; total &lt;=100.</td>
    <td>Exact PortfolioAllocationPlanRevision/snapshot must resolve. Missing currency conversion policy, invalid mapping or total &gt;100 are blockers; total &lt;100 is warning for unallocated cash.</td>
  </tr>
  <tr>
    <td>Strategy context</td>
    <td>Name, Rationale Family, Market, Data Source, Entry Execution, Exit Execution, Backtest Range start/end.</td>
    <td>All relevant star-required values must resolve to current/pinned revisions; start &lt; end, approved coverage and warm-up rules are checked.</td>
  </tr>
  <tr>
    <td>Strategy entry</td>
    <td>V18 requires trigger source, and at least one Indicator + Condition.</td>
    <td>At least one required Indicator Block with valid package revision/trigger source. Condition is required only when Trigger Source requires a Condition Package; Native Trigger alone does not require it.</td>
  </tr>
  <tr>
    <td>Strategy exit/protection</td>
    <td>V18 requires Exit Indicator + Condition OR any checked Stop Logic toggle.</td>
    <td>Valid Exit Logic or at least one active Stop Logic. Disabled/soluk structures are not active engine rules and are not validated as required.</td>
  </tr>
  <tr>
    <td>Strategy sizing</td>
    <td>V18 requires a checked sizing method.</td>
    <td>Exactly one active sizing method with valid parameters and internally consistent exposure/position limits.</td>
  </tr>
  <tr>
    <td>Trading Signal</td>
    <td>Source name and selected TXT/CSV file; independent Initial Capital when needed.</td>
    <td>Provider/source, normalized parsed import revision, event mapping, instrument/timezone/availability rule and policy must resolve. File-input presence alone is never sufficient.</td>
  </tr>
  <tr>
    <td>Trade Log</td>
    <td>Source name and selected TXT/CSV file; independent Initial Capital when needed.</td>
    <td>Normalized trade ledger revision, valid direction/time/price fields, chronology, market/timezone mapping and validation report must resolve. File-input presence alone is never sufficient.</td>
  </tr>
</table>

# 6. Information Content Catalog ve Nihai UI Metinleri

V18 Ready Check buttonu veya modalında ayrı ⓘ info button bulunmaz. Bu nedenle V18de “info panel” envanteri yoktur. Aşağıdaki metinler Production V1de readiness status yanında veya modal başlığında yer alacak read-only bilgi yüzeyi için Implementation Decision olarak tanımlanır; mevcut V18deki görünür label veya titleı değiştirmez.

<table>
  <tr>
    <th>Info key / placement</th>
    <th>Panel title</th>
    <th>Nihai UI metni</th>
  </tr>
  <tr>
    <td>`readyCheckStatusInfo` - status strip yanında recommended ⓘ</td>
    <td>Backtest Ready Check</td>
    <td>Backtest Ready Check, mevcut Mainboard Compositionın çalıştırılabilirliğini server tarafında değerlendirir. Kontrol; item revisions, Package dependencies, Market Data ve Research Data uygunluğu, execution capability, external importlar ve varsa Portfolio Allocation bağlamını kapsar. Yeşil durum yalnız mevcut composition fingerprinti için geçerlidir. Bir ayar veya dependency değişirse rapor STALE olur ve yeniden kontrol gerekir.</td>
  </tr>
  <tr>
    <td>`readyCheckWarningsInfo` - Warnings card heading yanında recommended ⓘ</td>
    <td>Warnings do not block the run</td>
    <td>Warning, RUN oluşturulmasını engellemez; ancak sonuç yorumunu etkileyebilecek bir varsayımı veya kalite riskini bildirir. RUN başladığında ilgili warningler immutable Run Manifest içine yazılır. Warningi görmezden gelmek validationın kaldırıldığı anlamına gelmez.</td>
  </tr>
  <tr>
    <td>`readyCheckStaleInfo` - stale message yanında recommended ⓘ</td>
    <td>Why this report is stale</td>
    <td>Bu rapor, önceki Mainboard Composition fingerprinti için üretildi. Item, strategy revision, package/data reference, external import, allocation, engine profile veya execution varsayımı değiştiği için mevcut yapı farklıdır. Eski rapor tarihsel kayıt olarak korunur; RUN için yeni Ready Check gerekir.</td>
  </tr>
  <tr>
    <td>V18 status title - actual HTML</td>
    <td>Ready status tooltip</td>
    <td>Not Ready: “Backtest Ready: Not Ready”. Ready: “Backtest Ready: Ready”.</td>
  </tr>
</table>

## 6.1 V18de görünen nihai durum, warning, empty-state ve error metinleri

<table>
  <tr>
    <th>Context</th>
    <th>V18 actual text</th>
    <th>Production behavior</th>
  </tr>
  <tr>
    <td>No passed card content</td>
    <td>“No passed item yet.”</td>
    <td>Use only when report has no pass summary. Production may show a count and report provenance.</td>
  </tr>
  <tr>
    <td>No failed issues</td>
    <td>“No blocking issue detected.”</td>
    <td>Show only when blocker_count=0. In READY_WITH_WARNINGS state, include warning count and warning semantics.</td>
  </tr>
  <tr>
    <td>No Mainboard item</td>
    <td>“No Strategy, Trading Signal or Trade Log exists on Mainboard.”</td>
    <td>BLOCKER with stable code such as `COMPOSITION_EMPTY`; do not leak hidden resources.</td>
  </tr>
  <tr>
    <td>Allocation disabled</td>
    <td>“Equity Allocation is not selected; independent Initial Capital mode is active.”</td>
    <td>Derived informational pass; each enabled item own capital is then validated.</td>
  </tr>
  <tr>
    <td>Optional fields warning</td>
    <td>“Optional fields default to None and are not blocking unless the selected strategy setup needs them.”</td>
    <td>Keep as warning or field-level rule; production checks selected dependencies, not generic text only.</td>
  </tr>
  <tr>
    <td>Execution realism warning</td>
    <td>“Commission, spread and slippage assumptions should be reviewed before real engine execution.”</td>
    <td>Persist as warning when assumptions are default/empty or execution profile requires review; include scope/path/remediation.</td>
  </tr>
  <tr>
    <td>Stale report recommended message</td>
    <td>Not present in V18.</td>
    <td>“Ready check must be run again.” Include last checked time, report id and changed fingerprint context.</td>
  </tr>
  <tr>
    <td>Permission error recommended message</td>
    <td>Not present in V18.</td>
    <td>“You do not have permission to use one or more selected resources in this composition.” Do not name private resources outside caller access.</td>
  </tr>
</table>

# 7. Buton, Command ve State Sözleşmesi

<table>
  <tr>
    <th>UI action</th>
    <th>V18 behavior</th>
    <th>Production command / precondition</th>
    <th>Loading, success, error, audit</th>
  </tr>
  <tr>
    <td>Run Backtest Ready Check</td>
    <td>Builds report from current DOM; sets local `backtestReady` based only on `failed.length===0`; opens modal.</td>
    <td>POST `/compositions/{id}/readiness-checks`; actor can view/use composition; server gets transactionally consistent current draft.</td>
    <td>Loading: CHECKING and RUN locked. Success: immutable report id/fingerprint/state/summary/issues. Error: 403/404/409/422/5xx structured response. Audit `readiness_check_requested` and `readiness_report_created`.</td>
  </tr>
  <tr>
    <td>Close modal</td>
    <td>Hides overlay; no state mutation.</td>
    <td>No domain command.</td>
    <td>Modal closes immediately; report remains retrievable by id. No audit required for a local dismiss action.</td>
  </tr>
  <tr>
    <td>Adjacent RUN click when not ready</td>
    <td>V18 `addBacktestResult()` invokes Ready Check if `backtestReady=false`.</td>
    <td>POST `/backtest-runs` cannot rely on a UI boolean. Requires composition id, expected fingerprint, idempotency key; report id optional.</td>
    <td>409 stale =&gt; re-check; 422 blockers =&gt; no run; success creates `queued` run only. Execution and Result are outside this page scope.</td>
  </tr>
  <tr>
    <td>Run while ready</td>
    <td>V18 creates one local demo result row if `backtestResultCreated` false.</td>
    <td>Server repeats mandatory preflight or deterministic cache; freezes snapshot + immutable manifest + run record transactionally.</td>
    <td>202/queued response plus event-stream URL. Queue failure becomes terminal run failure or safe outbox retry; no synthetic result.</td>
  </tr>
  <tr>
    <td>Retry Ready Check</td>
    <td>V18 can click again; overwrites visual local state.</td>
    <td>New POST always produces a new immutable report; no report patch.</td>
    <td>New report is current when matching current fingerprint; prior report remains historical; audit carries report ids/policy versions.</td>
  </tr>
  <tr>
    <td>Cancel/modal escape</td>
    <td>V18 overlay click closes modal.</td>
    <td>Does not cancel check/run unless explicit cancel command exists.</td>
    <td>No implicit cancellation of server work by UI dismissal, refresh, logout or event-stream disconnect.</td>
  </tr>
</table>

<table>
  <tr>
    <th>POST /compositions/{composition_id}/readiness-checks<br/>  -&gt; { report_id, state, summary, issues[], composition_snapshot_id, composition_fingerprint }<br/><br/>POST /backtest-runs<br/>  body: { composition_id, expected_fingerprint, readiness_report_id?, run_profile_id, output_profile, idempotency_key }<br/>  -&gt; { run_id, state: &quot;queued&quot;, manifest_hash, event_stream_url }</th>
  </tr>
</table>

# 8. Kullanıcı ve Sistem Akışları

## 8.1 Flow A - Başarılı READY

1. Kullanıcı en az bir persisted, enabled MainboardWorkingItem içeren compositionı açar ve ilgili Strategy/External Object revisionsını kaydeder.

2. Backtest Ready Check buttonuna basar. UI CHECKING gösterebilir; RUN locked kalır.

3. Server current composition draftından immutable snapshot üretir, deterministic validatorları çalıştırır ve blocker/warning içermeyen immutable report kaydeder.

4. Modal Passed kolonunda özetleri gösterir; status READY olur; composition fingerprint hâlâ current ise RUN UXi açılabilir.

5. Kullanıcı daha sonra RUN intent gönderirse server fingerprinti kontrol eder ve preflightı tekrarlar. Bu belge burada biter; queue/run lifecycle RUN ve Results dokümanında devam eder.

## 8.2 Flow B - READY_WITH_WARNINGS

1. Server blocker bulmaz, ancak örneğin unallocated cash veya commission/spread/slippage assumption warningi üretir.

2. Modal Warnings kolonunda warningleri gösterir; status RUNı açabilir fakat warning count görünür kalır.

3. RUN kabul edilirse server warnings listesini immutable Run Manifest içine yazmak zorundadır. Warningler UI kapandığında kaybolmaz.

4. Sonuç ekranı warningleri manifest/diagnostic bağlamından okuyabilir; warning, “sonucun yanlış” olduğunu değil, yorum riskini bildirir.

## 8.3 Flow C - BLOCKER ve recovery

1. Kullanıcı Ready Checki çalıştırır; server veya V18 demo kontrolü eksik item/field/dependency bulur.

2. Production report issue satırı code, severity=BLOCKER, scope, field_path, message ve remediation taşır. RUN locked kalır.

3. UI kullanıcıyı ilgili sayfaya veya alan pathine yönlendirebilir; başka ownerın private kaynağı ise yalnız permission-safe mesaj gösterir.

4. Kullanıcı veya yetkili actor kaynağı/alanı düzeltir, update current composition fingerprintini değiştirir ve eski report STALE olur.

5. Yeni Ready Check immutable yeni report üretir. Eski report düzenlenmez veya deleted olarak saklanmaz.

## 8.4 Flow D - STALE report

1. Bir composition READY iken Strategy Trigger Sourceu, Market Data revisionı, external import mappingi veya Portfolio Allocation değişir.

2. Backend composition/dependency fingerprintini değiştirir. Ready status STALEdir; RUN visually locked olur.

3. Client eski `expected_fingerprint` ile RUN çağırırsa server 409 COMPOSITION_STALE veya READY_REPORT_STALE döndürür.

4. UI “Ready check must be run again.” mesajını gösterir, current server statei yeniden hydrate eder ve user yeni check başlatır.

## 8.5 Flow E - Agent tool parity

1. Agent, Task/Checkpoint bağlamından composition id ve intended run profilei belirler.

2. Tool Gateway aynı Readiness Servicei çağırır; UIyi açmaz veya buton clicki taklit etmez.

3. Blocker varsa Agent `readiness_blocked` artifacti oluşturur; remediation/task önerisi üretir ve ana taskı safe checkpointte günceller.

4. Ready ise Agent internal run request gönderir; parent task, returned run_idyi dependency olarak checkpointine yazar ve UI açık olmadan event/artefact üzerinden sonucu izler.

# 9. Production Backend ve Domain Davranışı

## 9.1 Core object model

<table>
  <tr>
    <th>Nesne</th>
    <th>Temel alanlar</th>
    <th>Immutability / ilişki</th>
  </tr>
  <tr>
    <td>Mainboard Composition Draft</td>
    <td>id, owner/principal context, row_version, current composition items, dependency references, current fingerprint.</td>
    <td>Mutable aggregate. Any engine-relevant change yields new fingerprint and stales prior current report.</td>
  </tr>
  <tr>
    <td>Composition Snapshot</td>
    <td>id, composition_id, composition_fingerprint, item manifest, capital mode snapshot, created_by, created_at.</td>
    <td>Immutable point-in-time copy. Ready Check and manifest build read this snapshot; browser DOM is not source of truth.</td>
  </tr>
  <tr>
    <td>Readiness Report</td>
    <td>id, composition_snapshot_id, composition_fingerprint, dependency_fingerprint, policy_version, engine_compatibility_profile_id, state, checked_at/by, summary.</td>
    <td>Immutable. New check creates new report; report text and issues are not patched.</td>
  </tr>
  <tr>
    <td>Readiness Issue</td>
    <td>id, report_id, code, severity, scope_type/scope_id, field_path, message, remediation.</td>
    <td>Immutable child. Severity only BLOCKER or WARNING; PASS may remain in summary rather than an issue row.</td>
  </tr>
  <tr>
    <td>Backtest Run Manifest</td>
    <td>id, run_id, canonical JSON, manifest_hash, engine contract version, readiness_report_id.</td>
    <td>Created by RUN path, not by a browser. Exact strategy/package/data/research/allocation/engine identities are pinned.</td>
  </tr>
  <tr>
    <td>Backtest Run</td>
    <td>id, state, manifest_id, requested_by, parent_agent_task_id, idempotency_key, retry_of_run_id, timestamps, failure_code.</td>
    <td>Lifecycle is separate from readiness. Failed/cancelled run never becomes Backtest Result.</td>
  </tr>
  <tr>
    <td>Run event / artifact</td>
    <td>run_id, sequence_no, occurred_at, type, payload, correlation id; artifact URI/checksum/schema.</td>
    <td>Append-only observability. UI disconnect does not stop worker.</td>
  </tr>
</table>

## 9.2 Validator architecture and fixed check order

Ready Check validators must be separate pure deterministic domain services, not one large frontend handler or controller. The orchestrator owns aggregation, report persistence, audit correlation and current-fingerprint decision.

<table>
  <tr>
    <th>Validator layer</th>
    <th>Blocker examples</th>
    <th>Warning examples</th>
  </tr>
  <tr>
    <td>Composition / items</td>
    <td>No enabled item; non-canonical item kind; duplicate enabled same working object; snapshot cannot resolve.</td>
    <td>Similar strategies on same market/timeframe; correlation review recommended.</td>
  </tr>
  <tr>
    <td>Authorization / lifecycle</td>
    <td>Caller cannot use selected private dependency; selected revision soft-deleted/inaccessible.</td>
    <td>Agent parent task provenance missing where policy permits report creation.</td>
  </tr>
  <tr>
    <td>Strategy configuration</td>
    <td>Required market/data/range/execution/trigger missing; no entry logic; no exit nor active stop; sizing invalid.</td>
    <td>Commission/spread/slippage assumptions default or incomplete.</td>
  </tr>
  <tr>
    <td>Package / resolver</td>
    <td>Revision not usable; dependency resolution fails; unsupported resolver.</td>
    <td>Package validation created under an older policy version.</td>
  </tr>
  <tr>
    <td>Market Data</td>
    <td>Dataset not Approved; coverage gap; instrument/timeframe mismatch; processed asset absent.</td>
    <td>Gap ratio under warning threshold but above quality-review threshold.</td>
  </tr>
  <tr>
    <td>Research Data</td>
    <td>usage_scope excludes backtest; exact Market Data compatibility missing; available_time undefined.</td>
    <td>Limited coverage or low fill rate in part of requested interval.</td>
  </tr>
  <tr>
    <td>External working objects</td>
    <td>No normalized import revision/mapping/timezone/instrument/availability; invalid Trade Log chronology.</td>
    <td>Skipped-row ratio within policy warning band.</td>
  </tr>
  <tr>
    <td>Portfolio allocation</td>
    <td>Enabled but capital/currency/mode missing; share &lt;=0; total &gt;100; invalid item mapping.</td>
    <td>Total active share &lt;100; unallocated cash remains.</td>
  </tr>
  <tr>
    <td>Engine compatibility</td>
    <td>Intrabar execution requires unavailable tick/intrabar data; unsupported fill/conflict contract.</td>
    <td>Execution assumptions materially increase sensitivity.</td>
  </tr>
</table>

## 9.3 Server-side RUN preflight boundary

Ready Check and RUN are coupled but not interchangeable. The report determines UI readiness; the RUN endpoint determines whether a run can actually be admitted. It must not trust client `ready=true`, client item arrays, current rendered modal content or a stale report id.

1. Authenticate human session or trusted Agent runtime identity and authorize composition use.

2. Compare `expected_fingerprint` with current composition fingerprint; mismatch returns 409 COMPOSITION_STALE.

3. If a report id is supplied, verify report composition and current fingerprint; otherwise do not assume it is current.

4. Run mandatory server-side preflight or deterministic equivalent. Any blocker returns 422 READINESS_BLOCKED; do not create manifest, run or job.

5. In one transaction create immutable Composition Snapshot, Backtest Run Manifest and BacktestRun. Compute manifest hash.

6. Use idempotency_key to return the existing run for duplicate same-actor/same-route submission. Commit then publish run id through safe outbox/queue mechanism.

7. Return queued metadata/event-stream reference only. Engine result is never calculated synchronously in this page handler.

# 10. Agent Tool/API Eşdeğeri

Agent Ready Check operasyonu insan UIından ayrı transport kullanabilir, ancak domain behavior aynıdır. Agent için “fast/loose readiness” veya browser state bypassı yasaktır.

<table>
  <tr>
    <th>Tool / internal command</th>
    <th>Input</th>
    <th>Output</th>
    <th>Guardrails</th>
  </tr>
  <tr>
    <td>`backtest_readiness_check`</td>
    <td>composition_id, parent_task_id?, correlation_id.</td>
    <td>report_id, state, summary, issues, fingerprint, snapshot id.</td>
    <td>Same Readiness Service, authorization/use policy, immutable report and validator set.</td>
  </tr>
  <tr>
    <td>`backtest_run_request`</td>
    <td>composition_id, expected_fingerprint, readiness_report_id?, run_profile_id, output profile, idempotency_key, parent_task_id.</td>
    <td>run_id, `queued`, manifest_hash, event stream reference.</td>
    <td>Same manifest builder/preflight/orchestrator; no direct worker call from Agent.</td>
  </tr>
  <tr>
    <td>`read_readiness_report`</td>
    <td>report_id, authorized scope.</td>
    <td>Immutable report/detail/issue list.</td>
    <td>No mutation or reclassification of report issues.</td>
  </tr>
  <tr>
    <td>`backtest_run_events`</td>
    <td>run_id, last_sequence?</td>
    <td>Ordered event stream or current run state.</td>
    <td>Agent may checkpoint wait dependency; event ordering must be monotonic.</td>
  </tr>
</table>

Agent failure recovery: `BLOCKER` produces a structured artifact with issue codes and proposed remediation; it does not silently edit another owner’s private Strategy, retry an unchanged run indefinitely or wait for a browser modal. A normal Lab Assistant discussion does not alter Agent check/run work. A directive is handled only at safe checkpoint according to Agent policy.

# 11. Validation, Error ve Recovery Contract

<table>
  <tr>
    <th>Error / state</th>
    <th>When</th>
    <th>UI / API behavior</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>422 `UNSAVED_MAINBOARD_DRAFT`</td>
    <td>Only transient UI draft exists or unsaved item must participate.</td>
    <td>Highlight draft row; do not include it in snapshot/manifest.</td>
    <td>Save persisted revision or discard draft, then run Ready Check again.</td>
  </tr>
  <tr>
    <td>422 `READINESS_BLOCKED`</td>
    <td>One or more blocker issues during RUN preflight.</td>
    <td>RUN remains locked; response contains safe issue list.</td>
    <td>Resolve canonical field/dependency; generate new report.</td>
  </tr>
  <tr>
    <td>409 `COMPOSITION_STALE`</td>
    <td>expected_fingerprint does not equal current draft fingerprint.</td>
    <td>Show current report stale; do not start job.</td>
    <td>Refresh server state; rerun Ready Check.</td>
  </tr>
  <tr>
    <td>409 `READY_REPORT_STALE`</td>
    <td>Report no longer current or dependency fingerprint changed.</td>
    <td>Show stale message; old report remains viewable.</td>
    <td>Create new report; do not patch old report.</td>
  </tr>
  <tr>
    <td>403 `ACCESS_DENIED` / use denied</td>
    <td>Caller cannot check/run selected composition or dependency.</td>
    <td>No private resource details exposed.</td>
    <td>Use own/shared/published valid resources or request authorized action.</td>
  </tr>
  <tr>
    <td>422 `MARKET_DATASET_NOT_APPROVED`</td>
    <td>Selected Market Data revision not Approved or not usable.</td>
    <td>Issue points to dataset field/path.</td>
    <td>Select an Approved revision matching canonical instrument/timeframe/coverage.</td>
  </tr>
  <tr>
    <td>422 `RESEARCH_DATASET_NOT_APPROVED` / timing incompatible</td>
    <td>Research usage scope, available_time, linked Market Data or feature definition invalid.</td>
    <td>Issue includes remediation.</td>
    <td>Choose eligible revision; repair mapping/availability; regenerate check.</td>
  </tr>
  <tr>
    <td>422 external import invalid</td>
    <td>File selected in UI but no normalized import revision/mapping, or Trade Log chronology invalid.</td>
    <td>Report does not accept browser file presence as proof.</td>
    <td>Complete ingestion/parse/mapping validation; bind accepted import revision.</td>
  </tr>
  <tr>
    <td>409/422 allocation issue</td>
    <td>Allocation total/currency/mapping/capital invalid.</td>
    <td>Show scoped allocation issue without changing plan.</td>
    <td>Repair plan draft, save new revision as required, rerun check.</td>
  </tr>
  <tr>
    <td>500 / queue publish failure</td>
    <td>Manifest/run transaction cannot safely publish work after accepted request.</td>
    <td>Do not fabricate success. Run is FAILED/QUEUE_PUBLISH_FAILED or safely republished by outbox.</td>
    <td>Show retry guidance; retry creates a new run only if original terminal failure policy requires it.</td>
  </tr>
  <tr>
    <td>Network / SSE disconnect</td>
    <td>UI cannot observe progress after future RUN request.</td>
    <td>Ready report remains persisted; run not cancelled.</td>
    <td>Reconnect by event sequence or query current state endpoint.</td>
  </tr>
</table>

# 12. Lifecycle, Audit, Trash ve Historical Integrity

## 12.1 Lifecycle and retention

<table>
  <tr>
    <th>Nesne</th>
    <th>Mutation policy</th>
    <th>Soft delete / restore</th>
    <th>Historical integrity</th>
  </tr>
  <tr>
    <td>Readiness Report</td>
    <td>Immutable; rerun creates new report, never update in place.</td>
    <td>Reports normally retained with snapshot/run provenance; deletion policy must not erase evidence of admitted run.</td>
    <td>Existing manifest/result references retain report identity, policy and issues.</td>
  </tr>
  <tr>
    <td>Readiness Issue</td>
    <td>Immutable child of report.</td>
    <td>No independent user delete.</td>
    <td>Issue text/code remains evidence of decision at check time.</td>
  </tr>
  <tr>
    <td>Composition Draft</td>
    <td>Mutable while active; changes stale report.</td>
    <td>Normal delete is soft delete. Trash view/restore/permanent delete Admin-only.</td>
    <td>Historical snapshot/manifest remains unchanged even if root later soft-deleted.</td>
  </tr>
  <tr>
    <td>Strategy/External/Data/Package revision</td>
    <td>No historical mutation through Ready Check.</td>
    <td>Current use may be blocked if soft-deleted/inaccessible; historical reference remains.</td>
    <td>Manifest pin continues to identify exact past revision and checksum.</td>
  </tr>
  <tr>
    <td>BacktestRun</td>
    <td>Created only by RUN path; lifecycle separate.</td>
    <td>Run input roots cannot be destructively purged while referenced/active by retention policy.</td>
    <td>Failed/cancelled run retains diagnostics but no successful Backtest Result.</td>
  </tr>
</table>

## 12.2 Mandatory audit events

<table>
  <tr>
    <th>Event</th>
    <th>Minimum audit fields</th>
  </tr>
  <tr>
    <td>`readiness_check_requested`</td>
    <td>actor principal/type, composition_id, request_id, correlation_id, current fingerprint, parent_agent_task_id nullable.</td>
  </tr>
  <tr>
    <td>`composition_snapshot_created`</td>
    <td>snapshot_id, composition_id, fingerprint, item count, included revision ids, actor/system, timestamp.</td>
  </tr>
  <tr>
    <td>`readiness_report_created`</td>
    <td>report_id, state, policy_version, engine compatibility profile, blocker/warning/pass counts, dependency fingerprint, checked_by.</td>
  </tr>
  <tr>
    <td>`readiness_issue_detected`</td>
    <td>report_id, issue code, severity, scope type/id, field path, remediation id/text; avoid logging secret data.</td>
  </tr>
  <tr>
    <td>`readiness_became_stale`</td>
    <td>previous report id, old/new fingerprint or changed dependency category, source mutation/event id.</td>
  </tr>
  <tr>
    <td>`run_admission_rejected`</td>
    <td>actor, composition id, expected/current fingerprint, report id nullable, response code, issue summary, correlation id.</td>
  </tr>
  <tr>
    <td>`run_admission_accepted`</td>
    <td>run id, manifest hash, report id, idempotency key hash, actor, parent Agent task id nullable, queue/outbox outcome.</td>
  </tr>
  <tr>
    <td>`readiness_access_denied`</td>
    <td>actor context, target type/id redacted as policy requires, operation, denial code, request/correlation id.</td>
  </tr>
</table>

Trash rule: only Admin can view Trash, restore or permanently delete normal soft-deleted objects. Ready Check has no client-side “delete report” control. Admin restoration must not retroactively make an old report current; currentness is always recomputed from the current composition/dependency fingerprint.

# 13. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Topic</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Data source for check</td>
    <td>`buildBacktestReadyReport()` reads current DOM and file input values.</td>
    <td>Server reads persisted current composition draft and resolves exact revisions/imports under transaction.</td>
    <td>Do not use DOM/file chooser presence as the source of readiness.</td>
  </tr>
  <tr>
    <td>Ready boolean</td>
    <td>`backtestReady = report.failed.length === 0`.</td>
    <td>Readiness is derived from immutable report state + current fingerprint; states include CHECKING, READY_WITH_WARNINGS, STALE, SUPERSEDED.</td>
    <td>Replace boolean with server status model; preserve red/green UX as a presentation projection.</td>
  </tr>
  <tr>
    <td>Modal content</td>
    <td>Passed / Failed / Warnings plain strings.</td>
    <td>Issue list has code, severity, scope, path, message, remediation and report provenance.</td>
    <td>Keep three-card reading model but add accessible detail and remediation links.</td>
  </tr>
  <tr>
    <td>Entry condition check</td>
    <td>V18 requires Indicator + Condition for any entry setup.</td>
    <td>Condition is conditionally required: Native Trigger alone does not require Condition Package; other trigger sources do.</td>
    <td>Production validator follows Trigger Source contract, not static DOM selector rule.</td>
  </tr>
  <tr>
    <td>External source check</td>
    <td>V18 accepts source text + selected TXT/CSV file.</td>
    <td>Normalized immutable import revision, mapping/validation/availability required.</td>
    <td>File selector is only upload intent, never Ready Check proof.</td>
  </tr>
  <tr>
    <td>Status strip</td>
    <td>Only red/green title values.</td>
    <td>NOT_CHECKED/CHECKING/NOT_READY/READY_WITH_WARNINGS/READY/STALE/SUPERSEDED projected from server report.</td>
    <td>Add neutral/loading/stale affordance; color is supplemental, not sole communication.</td>
  </tr>
  <tr>
    <td>RUN behavior</td>
    <td>When not ready, V18 RUN calls Ready Check; when ready it creates one local demo result.</td>
    <td>RUN creates `queued` BacktestRun only after mandatory server preflight and manifest freeze; Result only after succeeded worker run.</td>
    <td>Do not preserve local result creation or `backtestResultCreated` as production logic.</td>
  </tr>
  <tr>
    <td>Report persistence</td>
    <td>V18 report lives only in browser.</td>
    <td>Immutable report + issues + snapshot are persisted/auditable.</td>
    <td>Modal close, refresh, logout and browser exit do not erase current/historical report.</td>
  </tr>
  <tr>
    <td>Latest revisions</td>
    <td>V18 reads current rendered selections.</td>
    <td>Exact revisions are pinned; catalog updates do not auto-upgrade an existing draft.</td>
    <td>Report stales only when composition reference actually changes, not merely when a newer catalog revision exists.</td>
  </tr>
</table>

# 14. Kodcu AI için Implementation Rules

- Ready Checki frontend form validationı veya local boolean olarak implement etme; server-side immutable snapshot validator olarak implement et.

- Her Ready Check isteğinde current Mainboard Composition Drafttan transactionally consistent snapshot üret; browserın gönderdiği item listesini canonical kabul etme.

- Readiness Report ve Readiness Issue kayıtlarını immutable yap. Yeni check yeni report üretir; issue metni veya severitysi yerinde güncellenmez.

- Currentnessi report fingerprinti ile current composition/dependency fingerprintini karşılaştırarak hesapla. Her engine-relevant change old reportu STALE yapmalıdır.

- RUN endpointinde client `ready` flagini, modal içeriğini veya old reportun varlığını yeterli kabul etme; expected_fingerprint kontrolü ve server preflight zorunludur.

- UI RUN lockunu authorization olarak kullanma. 403/409/422 kararları server-side policy, lifecycle ve validation katmanlarında tekrar uygulanmalıdır.

- Trading Signal ve Trade Logu Package kind gibi doğrulama; external Mainboard Working Item olarak kendi import/mapping/availability validatorlarıyla kontrol et.

- TXT/CSV input doluluğunu import readiness kanıtı sayma. Normalized immutable import revision, mapping sonucu ve validation summary olmadan PASS üretme.

- Strategy Entry Conditionı yalnız Trigger Source gerektirdiğinde şartlı zorunlu yap. Native Trigger için statik Condition Package zorunluluğu koyma.

- Disabled Strategy structuresı engine evaluation planına ve required validationa dahil etme; opacity/pointer-events tek başına state değildir.

- Readiness state ile BacktestRun lifecycleini ayrı registry/model olarak tut. READY bir compositionın running/failed run stateini değiştirme; failed/cancelled run Backtest Result üretmez.

- Manifestte exact Strategy, Package, Market Data, Research Data, external import, allocation plan revision, engine contract ve profile kimliklerini pinle; worker “latest”e fallback yapamaz.

- Duplicate runı aynı idempotency key ile yaratma. Same actor/route context için mevcut run referansını döndür; retry ise yeni run id ve yeni manifest hash üretir.

- Agent için ayrı, daha gevşek validator veya direct worker yolu oluşturma. Agent internal transportu aynı Readiness Service, Manifest Builder ve Orchestratorı kullanmalıdır.

- UI event connectionı, modal dismiss, refresh veya logout nedeniyle check/run workerını iptal etme. Durable state ve ordered event stream kullan.

- Soft delete/restore işlemlerinin historical report/snapshot/manifest kanıtını bozmasına izin verme; Trash access, restore and permanent delete Admin-only kalmalıdır.

# 15. Acceptance Tests

<table>
  <tr>
    <th>ID</th>
    <th>Scenario</th>
    <th>Expected verifiable result</th>
  </tr>
  <tr>
    <td>RC-01</td>
    <td>Mainboard has no enabled persisted item; Ready Check requested.</td>
    <td>Immutable report state NOT_READY; issue `COMPOSITION_EMPTY`/equivalent blocker; red status; RUN locked; no manifest/job.</td>
  </tr>
  <tr>
    <td>RC-02</td>
    <td>One valid Strategy; no blockers/warnings; report fingerprint equals current fingerprint.</td>
    <td>Report READY; green status; RUN UX may unlock; report/snapshot ids stored.</td>
  </tr>
  <tr>
    <td>RC-03</td>
    <td>Valid composition with unallocated cash below 100% allocation.</td>
    <td>READY_WITH_WARNINGS; warning retained in report and later manifest; RUN allowed after fresh preflight.</td>
  </tr>
  <tr>
    <td>RC-04</td>
    <td>Allocation enabled with share total 102%.</td>
    <td>NOT_READY; allocation scope blocker; RUN endpoint returns 422 READINESS_BLOCKED and creates no run.</td>
  </tr>
  <tr>
    <td>RC-05</td>
    <td>Strategy Native Trigger selected without Condition Package.</td>
    <td>Ready Check does not block solely because no Condition Package exists; only trigger sources requiring Condition Package enforce it.</td>
  </tr>
  <tr>
    <td>RC-06</td>
    <td>Strategy uses Output + Condition and Condition Package missing.</td>
    <td>NOT_READY with condition dependency blocker and path to affected indicator block.</td>
  </tr>
  <tr>
    <td>RC-07</td>
    <td>Trading Signal UI has file input value but no normalized import revision.</td>
    <td>NOT_READY; file presence is not treated as valid source evidence.</td>
  </tr>
  <tr>
    <td>RC-08</td>
    <td>Trade Log accepted row contains exit_time &lt; entry_time.</td>
    <td>Import/chronology validation blocks Ready Check or rejects row under explicit policy; no silent pass.</td>
  </tr>
  <tr>
    <td>RC-09</td>
    <td>Ready report exists; user changes Market Data revision or Strategy Trigger Source.</td>
    <td>Current report becomes STALE; RUN locks; old expected fingerprint returns 409 COMPOSITION_STALE.</td>
  </tr>
  <tr>
    <td>RC-10</td>
    <td>Another catalog revision appears, but current draft still pins old exact revision.</td>
    <td>Existing report does not stale solely because a newer catalog revision exists.</td>
  </tr>
  <tr>
    <td>RC-11</td>
    <td>User manually changes client DOM status to green and calls RUN.</td>
    <td>Server ignores client readiness; repeats preflight; blocks if current state invalid.</td>
  </tr>
  <tr>
    <td>RC-12</td>
    <td>Same actor submits identical RUN request twice with same idempotency key.</td>
    <td>One BacktestRun/job only; second response references original run.</td>
  </tr>
  <tr>
    <td>RC-13</td>
    <td>Agent requests Ready Check via internal tool while browser is closed.</td>
    <td>Same report/validator results as human path; no UI dependency; parent task/correlation provenance stored.</td>
  </tr>
  <tr>
    <td>RC-14</td>
    <td>UI closes modal or loses SSE connection after RUN has been queued.</td>
    <td>Run continues independently; later query/event resume reflects durable state.</td>
  </tr>
  <tr>
    <td>RC-15</td>
    <td>RUN fails or is cancelled after a previously READY check.</td>
    <td>Failure/cancellation trace/artifact stored; no immutable Backtest Result or Results History performance entry is created.</td>
  </tr>
  <tr>
    <td>RC-16</td>
    <td>Soft-deleted dependency is selected for new check.</td>
    <td>NOT_READY / lifecycle blocker; historical manifest still retains old reference and is not rewritten.</td>
  </tr>
  <tr>
    <td>RC-17</td>
    <td>Unauthorized User attempts check on a private composition/resource.</td>
    <td>403/permission-safe rejection; no confidential dependency details in response.</td>
  </tr>
  <tr>
    <td>RC-18</td>
    <td>Ready report rerun on unchanged snapshot.</td>
    <td>A new immutable report id is created; older report is historical/superseded; no in-place mutation.</td>
  </tr>
</table>

# 16. Final Master Consistency Check

<table>
  <tr>
    <th>Control</th>
    <th>Status</th>
    <th>Page-level confirmation</th>
  </tr>
  <tr>
    <td>Master authority</td>
    <td>PASS</td>
    <td>Module 12 and CR-03 to CR-07 govern all Production decisions; V18 is treated as prototype evidence.</td>
  </tr>
  <tr>
    <td>Run vs Result</td>
    <td>PASS</td>
    <td>Ready Check creates report/snapshot only; RUN admission creates queued run; only succeeded run may yield immutable Result.</td>
  </tr>
  <tr>
    <td>Working Item taxonomy</td>
    <td>PASS</td>
    <td>Trading Signal and Trade Log are external Mainboard Working Items, not Package Library kinds.</td>
  </tr>
  <tr>
    <td>Snapshot / manifest integrity</td>
    <td>PASS</td>
    <td>Ready report is fingerprint-bound; RUN freezes exact immutable manifest; worker uses no latest fallback.</td>
  </tr>
  <tr>
    <td>Agent continuity</td>
    <td>PASS</td>
    <td>Agent uses Tool Gateway/internal API; no browser, modal or chat dependency.</td>
  </tr>
  <tr>
    <td>Role and Trash boundary</td>
    <td>PASS</td>
    <td>Server policy governs access; normal delete is soft delete; Trash/restore/permanent delete are Admin-only.</td>
  </tr>
  <tr>
    <td>V18 alignment</td>
    <td>PASS WITH EXPLICIT ALIGNMENT NOTES</td>
    <td>Local DOM boolean/report/file checks, red/green only status and demo result creation are not Production truth.</td>
  </tr>
  <tr>
    <td>Future Dev boundary</td>
    <td>PASS</td>
    <td>No live order, broker action or Future Dev job is introduced by this Ready Check specification.</td>
  </tr>
</table>

Canonical summary: Son karar

Entropiada “Ready” yalnız bir yeşil şerit veya browserda açılan modal değildir. Ready; belirli bir immutable Composition Snapshot ve fingerprint için, exact revisions ve time-aware dependencies doğrulanarak üretilmiş server-side Readiness Report durumudur. RUN isteği bu sonucu yeniden doğrular, manifesti dondurur ve işi UIdan bağımsız queue/worker hattına verir.
