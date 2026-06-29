---
title: "Entropia V18 — Pre-Check Page Documentation v1.1"
page_number: 7
document_type: "Page implementation specification"
source_document: "Entropia_V18_Pre_Check_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Pre-Check Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | PAGE DOCUMENTATION 7/22 | PRE-CHECK
> **Original DOCX footer:** Canonical page documentation | Production V1 alignment |

ENTROPIA V18

PRE-CHECK

Sayfa Dokümantasyonu 7/22 | PineScript dependency gate, canonical Embedded System Package resolver eşleme ve statik ön inceleme sözleşmesi

<table>
  <tr>
    <th>Kapsam sınırı: Pre-Check V18de bağımsız route değildir; Create Package ekranındaki Pre-Check düğmesi, TA Pre-Check status satırı, Pine TA / Embedded System Package Resolver yardım alanı ve TA PRE-CHECK RESULT modalı ile görünen mantıksal iş akışıdır. Bu belge yalnız bu ön inceleme yüzeyini ve onun Production V1 dependency-gate davranışını kapsar. Create Packageın candidate üretimi, draft oluşturma, validation, baseline, approval, Package Library, Embedded System Packages yönetimi ve Trash ekranları ayrı sayfaların kapsamıdır; burada yalnız doğrudan bağımlılık olarak anılır.</th>
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
    <td>Entropia V18 | Page Documentation 7/22 | Pre-Check | v1.1</td>
  </tr>
  <tr>
    <td>Belge amacı</td>
    <td>V18de Create Package içinde açılan Pre-Check davranışını, Pine TA dependency çözümünü, status/popup sözleşmesini ve Production V1 immutable dependency-scan / resolver-registry modelini kodcu AI için uygulanabilir seviyeye indirmek.</td>
  </tr>
  <tr>
    <td>Kapsam</td>
    <td>Pre-Check triggerı; source/kontekst girdilerinin izlenmesi; TA dependency algılama; canonical Embedded System Package resolver eşlemesi; durum pillı; result modalı; Send gatei; stale, failure ve recovery; command/API, job, audit, ownership, Agent parity ve lifecycle etkileri.</td>
  </tr>
  <tr>
    <td>Kapsam dışı</td>
    <td>Create Packageın tüm form sözleşmesi; CP Agent candidate üretimi; Create Draft Package; baseline upload/karşılaştırma; validation testleri; Package Library katalog yönetimi; Embedded System Package edit/approval ekranı; Strategy Details; Backtest Run/Result; Trash ekranı.</td>
  </tr>
  <tr>
    <td>Kaynak önceliği</td>
    <td>1) Entropia V18 Master Technical Reference v1.0, 2) V18 ana HTML, 3) Sayfa Bazlı Dokümantasyon Handoff v1.1, 4) 2.3 POSITION ENTRY LOGIC anlatım derinliği örneği.</td>
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
    <td>Pre-Check amacı ve scope</td>
    <td>Modül 8 §5; kavram sözlüğü ve lifecycle matrisi</td>
    <td>Pre-Check düğmesi cpRunPreCheck(); TA PRE-CHECK RESULT modalı</td>
    <td>Pre-Check dependency + temel statik uygunluk kapısıdır; çeviri, semantic validation veya market backtest değildir.</td>
  </tr>
  <tr>
    <td>Source/runtime conflict</td>
    <td>Modül 8 §1.3; target_runtime canonical kararı</td>
    <td>Source prompt Python ister; Target Runtime dropdown PHP gösterir</td>
    <td>Production V1 target_runtime = python-3.12; PHP prototip seçimi taşınmaz. Uyuşmazlık REQUIRES_CLARIFICATION üretir.</td>
  </tr>
  <tr>
    <td>Pine TA resolver</td>
    <td>Modül 8 §5.2-5.4 ve §6; ESP resolver contractı</td>
    <td>Regex ile ta.* taranır; local embedded map üzerinden name lookup yapılır</td>
    <td>Production parser/lexer + signature doğrulaması kullanır. Aynı isimli package yeterli değildir; exact approved resolver revision gerekir.</td>
  </tr>
  <tr>
    <td>Lifecycle / gate</td>
    <td>Modül 8 state machine, request lifecycle ve Send gatei</td>
    <td>Not Checked / Passed / Blocked pill; Send yalnız precheckBlocked ile engellenir</td>
    <td>Production requested -&gt; precheck_pending/passed/blocked/not_applicable; source/runtime/contract değişiminde stale. Code request stale iken Send reddedilir.</td>
  </tr>
  <tr>
    <td>Role / approval</td>
    <td>Modül 1 role policy; Modül 7 CR-02; Modül 8 §5.4</td>
    <td>V18 Blocked mesajı Admin action required der</td>
    <td>Eksik resolver için herkes proposal/draft oluşturabilir; canonical ESP registry update ve approve_and_publish yalnız Admin.</td>
  </tr>
  <tr>
    <td>Audit / Agent / persistence</td>
    <td>Modül 0, 1-3, 8 §10-11, 19</td>
    <td>V18 local cpState ile status tutar</td>
    <td>Dependency scan immutable artifacttır. Browser/Agent UIdan bağımsız API kullanır; job, audit, source hash ve resolver pins saklanır.</td>
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
    <td>Masterda açıkça kilitlenmiş Production V1 davranışıdır. Örnek: Pre-Check, Pine TA çağrılarını canonical Embedded System Package resolverlarıyla eşler; eksik resolver bulunduğunda aynı source hash için candidate generation engellenir.</td>
  </tr>
  <tr>
    <td>Derived Rule</td>
    <td>Canonical kuralın zorunlu sonucudur. Örnek: Resolver registrydeki isim eşleşmesi tek başına yeterli olmadığından, scanner result signature ve pinned resolver revision ref taşımalıdır.</td>
  </tr>
  <tr>
    <td>V18 Interface Observation</td>
    <td>HTMLde görünen prototype davranışıdır. Örnek: code detection regex ile yapılır; target runtime PHPdir; modal dış tıklamayla kapanır; status local cpState içinde yaşar.</td>
  </tr>
  <tr>
    <td>Implementation Decision - Non-Canonical Gap Resolution</td>
    <td>Master exact UI progress veya request-save mekanizmasını kilitlemediğinde bu belgede seçilen teknik yöndür. Örnek: Pre-Check worker job olarak durable kaydedilir, UI SSE/polling ile durumu izler ve aynı context hash için idempotent çalışır.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Canonical Kavramlar

Pre-Check, Create Package üretim hattında bir kod kaynağının dönüştürülmeden önce dependency ve temel statik uygunluk bakımından incelendiği kapıdır. Özellikle PineScript içindeki teknik analiz primitive çağrılarını tespit eder, bu çağrıların Entropia runtimeındaki canonical Embedded System Package (ESP) karşılıklarını bulur ve yalnız doğru sürüm/signature ile çözümlenmiş isteklerin candidate generation aşamasına geçmesine izin verir.

Bu mekanizma bir kod dönüştürücü, onay mekanizması, real-market validation veya backtest değildir. CP Agentın belirsiz bir ta.* fonksiyonunu sessizce uydurmasını, her generated package içine farklı resolver kodu kopyalamasını ve historical sonuçların hangi platform semantiğiyle üretildiğinin kaybolmasını önlemek için vardır.

## 1.1 İlk geçen kavramlar

<table>
  <tr>
    <th>Kavram</th>
    <th>Canonical kısa tanım</th>
    <th>Bu sayfadaki uygulama sonucu</th>
  </tr>
  <tr>
    <td>Package Request</td>
    <td>Bir insan veya Agentın üretmek istediği package için kaynak, seçilmiş tür, creation mode, target runtime ve output contract içeren talep kaydı.</td>
    <td>Pre-Check kaynak/kontekst hashini bu requeste bağlar; Request approved package değildir.</td>
  </tr>
  <tr>
    <td>Pre-Check</td>
    <td>Kod dependency ve temel statik uygunluk ön incelemesi.</td>
    <td>Pine TA çağrılarını canonical resolverlarla eşler; semantic equivalence veya market validation sağlamaz.</td>
  </tr>
  <tr>
    <td>Dependency Scan</td>
    <td>Belirli source/context hash için immutable tespit ve eşleme artifactı.</td>
    <td>Detected calls, resolved revisions, missing/unsupported calls, scanner version ve decision içerir.</td>
  </tr>
  <tr>
    <td>Embedded System Package / ESP</td>
    <td>ta.sma, ta.rsi gibi platform primitiveinin trusted, versioned Entropia runtime çözümü.</td>
    <td>Generic Indicator Package değildir; canonical registryye yalnız Admin onayıyla girer.</td>
  </tr>
  <tr>
    <td>Resolver Registry</td>
    <td>Canonical key -&gt; active approved ESP revision mappingi.</td>
    <td>Pre-Check yalnız root.lifecycle_state=active, revision.validation_state=passed, revision.approval_state=approved, visibility_scope=system/published, registry_trust_state=trusted ve runtime-uyumlu resolver revisionını kabul eder.</td>
  </tr>
  <tr>
    <td>Resolver Signature</td>
    <td>Fonksiyonun adı, argüman cardinality/type/optional parametreleri, return shape ve warm-up semantiği.</td>
    <td>Aynı isimli ama imzası farklı resolver dependencyyi resolved yapamaz.</td>
  </tr>
  <tr>
    <td>Context Hash</td>
    <td>Source hash + normalized source language + target runtime + output contract + dependency ayarlarının hashidir.</td>
    <td>Bu değer değişirse önceki precheck stale olur; eski Passed/Blocked sonucu yeni istek için kullanılamaz.</td>
  </tr>
  <tr>
    <td>Precheck Gate</td>
    <td>Candidate generation öncesi server-side izin kontrolüdür.</td>
    <td>Code source için passed, description için not_applicable gerekir; blocked/stale/failed state Sendi durdurur.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Canonical Rule: CP Agent candidate üretir; Embedded System Package resolverini tahmin ederek canonical dependency yerine geçemez. Pre-Check yalnızca active canonical resolver revisionlarını kabul eder. Eksik primitive nedeniyle candidate generation engellenir; resolver proposal/draft üretilebilir fakat canonical registry değişikliği ve publish Admin onayı olmadan gerçekleşmez.</th>
  </tr>
</table>

## 1.2 Sistem döngüsündeki yer

<table>
  <tr>
    <th>Package Request<br/>  -&gt; Pre-Check (dependency scan + static gate)<br/>     -&gt; PRECHECK_PASSED | PRECHECK_NOT_APPLICABLE | PRECHECK_BLOCKED<br/>  -&gt; Candidate Generation job<br/>  -&gt; Candidate Ready<br/>  -&gt; Create Draft Package<br/>  -&gt; Validation / Baseline / Approval<br/><br/>Pre-Check burada yalnız ikinci adımdır. Candidate, Draft Package, Validation Evidence veya Approved Package üretmez.</th>
  </tr>
</table>

## 1.3 Bu sayfanın yapmadığı işler

- Çeviri yapmaz: PineScripti Python runtime koduna dönüştürmez; candidate generation ayrı CP Agent/worker işlemidir.

- Kodu onaylamaz: Syntax, runtime, output contract, real market data, repaint/future leak ve baseline validation testleri ayrı kanıt işleridir.

- ESP yaratmaz: Eksik dependencyyi raporlar ve proposal remediation verir; canonical ESP root/revision üretimi ile Admin approvalı ayrı alandır.

- Package Libraryye eklemez: Pre-Check statusu, packagein Draft/Experimental/Approved olarak Libraryde kullanılabilir hale geldiği anlamına gelmez.

- Agentı durdurmaz: Eksik resolver yalnız ilgili conversion branchini blocked yapar. Agentın başka research taskları ve queue işleri devam eder.

# 2. Erişim, Görünürlük, Ownership ve Server-Side Policy

<table>
  <tr>
    <th>Actor</th>
    <th>View / query</th>
    <th>Run Pre-Check</th>
    <th>Read source + scan artifact</th>
    <th>Resolver remediation</th>
    <th>Approve / registry change</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Protected Create Package/Pre-Check view yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
    <td>Yok.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Own + policy ile erişilebilir request statusunu görür.</td>
    <td>Own Package Request üzerinde.</td>
    <td>Own request ve erişimi olan system resolver projectionları.</td>
    <td>Eksik ESP için proposal/draft oluşturabilir; canonical registry değiştiremez.</td>
    <td>Yok.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Erişilebilir working request ve resolver statusunu görür.</td>
    <td>Own request üzerinde.</td>
    <td>Own request + accessible working artifacts.</td>
    <td>Proposal/draft oluşturabilir; canonical registry değiştiremez.</td>
    <td>Yok.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm uygun request, scan artifact ve registry projectionlarını görür.</td>
    <td>Her uygun request için.</td>
    <td>Tüm uygun source/scan evidence.</td>
    <td>ESP draft/proposal oluşturabilir ve yönetebilir.</td>
    <td>Approved ESPyi canonical registryye publish/activate edebilir.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Human UI login olmadan Tool Gateway üzerinden policy-allowed request/scan kullanır.</td>
    <td>Own Agent request/branch için.</td>
    <td>Own artifact + allowed shared/system resolver registry.</td>
    <td>Resolver proposal artifacti oluşturabilir ve queueya bırakabilir.</td>
    <td>Yok; Admin only.</td>
  </tr>
</table>

UIde Pre-Check düğmesinin görünmesi, Send düğmesinin enabled görünmesi veya modalın açılması yetki kanıtı değildir. Her `pre-check`, `get request`, `get scan artifact`, `create resolver proposal` ve `approve_and_publish resolver` commandi server-side principal, owner, resource lifecycle, visibility ve operation policy ile yeniden kontrol edilir.

<table>
  <tr>
    <th>Yetki sınırı: Rationale Families için global shared-editing exception, Pre-Check veya Embedded Resolver Registryye genişletilmez. Resolver registry platform semantiği taşıdığı için approval/publish yalnız Admin commandidir.</th>
  </tr>
</table>

# 3. Arayüz Yerleşimi, Navigasyon ve Görünür Bileşenler

V18de Pre-Check bağımsız bir menü routeu veya ayrı page container değildir. Create Package görünümünün sol sütunundaki PACKAGE REQUEST / AI WORKSPACE compose alanından tetiklenir; sonucu sağ sütundaki PACKAGE STATUS kartındaki `TA Pre-Check` pillında ve overlay modalında görünür. Bu nedenle Production V1de de aynı görsel konum korunabilir; fakat Pre-Checkin gerçek kaynağı backenddeki Package Request + Dependency Scan artifactleri olmalıdır.

## 3.1 V18 görünür bileşen envanteri

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 konumu / başlangıç state</th>
    <th>Görünür içerik</th>
    <th>Production V1 anlamı</th>
  </tr>
  <tr>
    <td>Shared source textarea</td>
    <td>Create Package sol compose; defaultta örnek PineScript-&gt;Python talebi</td>
    <td>Kullanıcı kaynak kodu veya açıklama girer.</td>
    <td>Pre-Checkin `source_text` girdisidir; source hash oluşturulur. Bu alanın tam Create Package UX contractı Sayfa 6dadır.</td>
  </tr>
  <tr>
    <td>Pre-Check button</td>
    <td>Compose action row; default enabled</td>
    <td>`Pre-Check`</td>
    <td>Empty requestte informative modal gösterir. Code source için dependency scan commandini başlatır; checkingte duplicate click engellenir.</td>
  </tr>
  <tr>
    <td>TA Pre-Check status pill</td>
    <td>PACKAGE STATUS card; default `Not Checked`</td>
    <td>`Not Checked`, `Passed` veya `Blocked`</td>
    <td>V18 local state yerine requeste bağlı server projection. Production backend canonical enumu lowercase snake_case taşır.</td>
  </tr>
  <tr>
    <td>Resolver help area</td>
    <td>Sağ sütun; PINE TA / EMBEDDED SYSTEM PACKAGE RESOLVER</td>
    <td>ta.sma, ta.ema, ta.rsi, ta.atr gibi çağrıların ESP ile eşleşmesi gerektiğini anlatır.</td>
    <td>Kullanıcıya açıklayıcı metindir; resolver sonucunun gerçek kaynağı registry + dependency scan olmalıdır.</td>
  </tr>
  <tr>
    <td>TA PRE-CHECK RESULT modal</td>
    <td>Pre-Check click sonrası overlay</td>
    <td>Başlık, result body, Close ve × buttonu.</td>
    <td>Scan result artifactinin rendered summarysi. Untrusted source text HTML olarak render edilmez.</td>
  </tr>
  <tr>
    <td>Send gate modal</td>
    <td>V18de yalnız blocked state ile Send click sonrası</td>
    <td>`TA PRE-CHECK REQUIRED` uyarısı.</td>
    <td>Productionda blocked, stale, failed veya required precheck missing durumunda server-side candidate-generation commandi reddedilir.</td>
  </tr>
</table>

## 3.2 V18 modal ve close behavior

<table>
  <tr>
    <th>Öğe</th>
    <th>V18 Interface Behavior</th>
    <th>Production V1 behavior</th>
  </tr>
  <tr>
    <td>Modal layer</td>
    <td>`cp-precheck-overlay` fixed overlay olarak bodye eklenir.</td>
    <td>Route değişimi, refresh veya event reconnect sırasında status serverdan yeniden yüklenir; open modal transient UI state olabilir.</td>
  </tr>
  <tr>
    <td>Close ×</td>
    <td>Başlık yanında × buttonu overlayi kaldırır.</td>
    <td>Modalı kapatır; scan sonucunu, requesti veya audit kaydını değiştirmez.</td>
  </tr>
  <tr>
    <td>Close button</td>
    <td>Modal altında `Close` buttonu bulunur.</td>
    <td>Aynı davranış; keyboard focus buttona gider, Esc ile kapama desteklenir.</td>
  </tr>
  <tr>
    <td>Outside click</td>
    <td>Overlay click handler modalı kapatır; modal içi click propagation durdurur.</td>
    <td>Outside click yalnız transient modalı kapatır. Aktif `checking` job iptal edilmez; explicit cancel command yoktur.</td>
  </tr>
  <tr>
    <td>Content safety</td>
    <td>V18 result rowları escape eder; HTML template içinde sonucu render eder.</td>
    <td>Source-derived değerler strict text node / safe renderer ile gösterilir. Raw source veya error payload UI HTMLi olarak inject edilmez.</td>
  </tr>
</table>

## 3.3 Responsive, loading ve accessibility kararları

- V18 observation: Modal, viewporta göre max-width/max-height kullanır ve modal content scroll edebilir. Arka plan açılır fakat semi-transparent overlay gösterir.

- Production rule: Modal `role="dialog"`, `aria-modal="true"`, programmatic title association ve focus trap ile açılır. Açılışta title/failure summary odaklanır; kapanışta focus Pre-Check düğmesine döner.

- Implementation Decision: `checking` süresince Pre-Check düğmesi disabled + `Checking dependencies…` labelı alır; previous completed status pillı yerine distinct Checking state gösterilir. Browser refresh aktif jobu durdurmaz.

- Implementation Decision: Modal body, resolved/missing calls listesini semantic list/table olarak render eder; only-color üzerinden Passed/Blocked iletişimi kurulmaz.

# 4. Interaction State Matrix

<table>
  <tr>
    <th>State</th>
    <th>Trigger / görünüm</th>
    <th>Controls</th>
    <th>Payload / engine etkisi</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>not_checked</td>
    <td>Yeni Package Request veya V18 page load. UI pill: `Not Checked`.</td>
    <td>Pre-Check enabled; Send empty requesti ayrıca reddeder.</td>
    <td>Code source için candidate generationa izin vermez; description henüz normalize edilmemişse Send öncesi server karar verir.</td>
    <td>Source gir veya mevcut inputla Pre-Check çalıştır.</td>
  </tr>
  <tr>
    <td>checking</td>
    <td>Production precheck job accepted; UI pill `Checking`. V18de yok.</td>
    <td>Pre-Check disabled; Send disabled veya loading gate.</td>
    <td>Job source/context hashine bağlıdır. Aynı context duplicate job yaratmaz.</td>
    <td>SSE/polling sonucu beklenir; network kesilirse status tekrar sorgulanır.</td>
  </tr>
  <tr>
    <td>passed</td>
    <td>Code source tarandı; tüm dependencyler uygun resolver revisionlarına bağlandı.</td>
    <td>Send enabled; modal list resolved callsı gösterir.</td>
    <td>Resolved dependency manifest candidate generation için pinlenmeye hazırdır.</td>
    <td>Source/context değişirse stale; registry mismatch varsa Sendde server recheck.</td>
  </tr>
  <tr>
    <td>blocked</td>
    <td>Bir veya daha fazla mandatory dependency eksik/uyumsuz. UI pill `Blocked`.</td>
    <td>Send block mesajı gösterir; Pre-Check retry enabled.</td>
    <td>Aynı context hash için candidate generation 409 PRECHECK_BLOCKED. Missing dependency manifestte saklanır.</td>
    <td>ESP proposal oluştur; Admin canonical resolveri approve/publish eder; sonra fresh Pre-Check.</td>
  </tr>
  <tr>
    <td>not_applicable</td>
    <td>Source natural-language description veya code dependency scan uygulanmayan valid modality. V18 natural textte `Not Checked` gösterir.</td>
    <td>Send enabled; Pre-Check rerun optional.</td>
    <td>Request `source_kind=DESCRIPTION`, `source_language=null`; code dependency gate uygulanmaz.</td>
    <td>Descriptionı codea çevirirsen source kind değişir ve precheck required olur.</td>
  </tr>
  <tr>
    <td>stale</td>
    <td>Source, source language, target runtime, output contract veya dependency ayarı changed. V18de yok.</td>
    <td>Send blocked for code; Pre-Check enabled.</td>
    <td>Eski scan/history korunur fakat current context için invaliddir.</td>
    <td>Yeni context hash ile fresh scan çalıştır.</td>
  </tr>
  <tr>
    <td>failed</td>
    <td>Parser/scanner/registry query teknik hatası veya unsupported grammar.</td>
    <td>Send blocked for code; retry enabled.</td>
    <td>No positive dependency decision exists; candidate job oluşmaz.</td>
    <td>Hata detayını görüntüle; source languageı düzelt veya manual review/parse support talep et.</td>
  </tr>
  <tr>
    <td>deleted / restored request</td>
    <td>Request veya bağlı draft normal soft-delete / restore akışına girer.</td>
    <td>Deleted requestte Pre-Check action yok.</td>
    <td>Historical scan artifactleri audit/provenance için saklı kalır; current workten çıkar.</td>
    <td>Restore yalnız Admin; restored request current dependencies için stale kabul edilir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kritik state kuralı: `Passed` sonucu yalnız aynı `context_hash` için geçerlidir. Source text, source language, target runtime, output contract veya dependency ayarı değiştiğinde UI pillı otomatik `Stale` olur. Eski Passed veya Blocked kararını yeni content üzerinde sessizce tekrar kullanmak yasaktır.</th>
  </tr>
</table>

# 5. Field Contract Matrix: Pre-Checkin İzlediği Girdiler ve Çıktılar

Aşağıdaki alanların tamamı Create Package ekranında görünür; ancak bu belge yalnız Pre-Check açısından hangi alanın scan contextine girdiğini açıklar. Package Type, Creation Mode, Rationale Family ve diğer Create Package fieldlarının tam form/approval contractı Sayfa 6dadır.

<table>
  <tr>
    <th>Alan / UI tipi</th>
    <th>V18 observed default</th>
    <th>Requiredness ve Pre-Check bağımlılığı</th>
    <th>Production payload / validation</th>
  </tr>
  <tr>
    <td>Source Text<br/>Textarea</td>
    <td>Türkçe örnek prompt: PineScript indikatörünü Python diline çevir; Indicator Package; OHLCV; indicator_value/long_signal/short_signal; closed-bar.</td>
    <td>Pre-Check run için boş olamaz. Send için de boş request yasaktır. Source code ise code gate zorunlu; description ise not_applicable olabilir.</td>
    <td>`source_text` veya immutable `source_asset_revision_ref`; normalized `source_hash`. Whitespace-only -&gt; EMPTY_SOURCE. Size/type policy uygulanır.</td>
  </tr>
  <tr>
    <td>Package Type<br/>Dropdown</td>
    <td>Indicator Package</td>
    <td>Pre-Check dependency parsingini doğrudan değiştirmez; ancak requested output/ESP remediation contextini belirler. Type değişimi request semantic contextini güncellediği için stale yapar.</td>
    <td>`package_type`: indicator | condition | embedded_system. Strategy/Trading Signal/Trade Log seçenek olamaz.</td>
  </tr>
  <tr>
    <td>Creation Mode<br/>Dropdown</td>
    <td>Translate Existing Code</td>
    <td>Mode source_kind ve equivalence expectationsini etkiler. Mode code&lt;-&gt;descriptiona geçerse stale.</td>
    <td>`creation_mode`: translate_existing_code | generate_from_description | repair_existing_code | review_existing_code.</td>
  </tr>
  <tr>
    <td>Source Language<br/>Dropdown</td>
    <td>PineScript</td>
    <td>Code precheck için her zaman required. Natural Language V18de optiondur ancak Productionda `source_kind=description`, `source_language=null` normalize edilir.</td>
    <td>`source_language`: pinescript | python | cpp | other | null. UI selection, content detector ve parser sonucu uyuşmalı; mismatch -&gt; SOURCE_LANGUAGE_MISMATCH/REQUIRES_CLARIFICATION.</td>
  </tr>
  <tr>
    <td>Target Runtime<br/>Dropdown</td>
    <td>PHP (prototype conflict)</td>
    <td>Always required for code/candidate request. Runtime değişimi stale.</td>
    <td>Production V1 fixed `target_runtime=python-3.12`. PHP/C++ current UI options değildir. Prompt + selected runtime uyuşmazsa REQUIRES_CLARIFICATION.</td>
  </tr>
  <tr>
    <td>Output Type<br/>Dropdown</td>
    <td>Directional Signal</td>
    <td>Always required request context. Output contract değişimi stale, çünkü availability/type expectation etkilenir.</td>
    <td>`output_contract_draft`; selected top kind: directional_signal | boolean_condition | numeric_series | color_direction_state | trade_record. Package type with compatibility validation.</td>
  </tr>
  <tr>
    <td>Pre-Check button<br/>Button</td>
    <td>Enabled</td>
    <td>No asterisk. Empty source click informative response üretir; `checking`te disabled.</td>
    <td>Creates/uses Package Request then starts idempotent precheck command. Receives request id, scan/job id, context hash.</td>
  </tr>
  <tr>
    <td>TA Pre-Check<br/>Status pill</td>
    <td>Not Checked</td>
    <td>Read-only. User cannot select Passed/Blocked.</td>
    <td>Server projection: not_checked | checking | passed | blocked | not_applicable | stale | failed. UI label is presentation-only.</td>
  </tr>
</table>

## 5.1 Zorunluluk, * işareti ve koşullu zorunluluk standardı

<table>
  <tr>
    <th>Field</th>
    <th>UI * davranışı</th>
    <th>Backend / Agent schema kuralı</th>
    <th>Not</th>
  </tr>
  <tr>
    <td>Source Text</td>
    <td>Pre-Check button yanında V18de * yoktur; Productionda empty click informative feedback verir.</td>
    <td>`RunPreCheck` command source hash üretemezse scan başlatmaz. `GenerateCandidate` command whitespace-only source için 422 EMPTY_SOURCE döndürür.</td>
    <td>UIde star konulmaması fieldin Send için opsiyonel olduğu anlamına gelmez.</td>
  </tr>
  <tr>
    <td>Source Language</td>
    <td>Create Package sayfa formunda * ile işaretlenmelidir; Natural Language seçildiğinde yıldız labeldan kalkmaz, semantik `source_language=null` olur.</td>
    <td>Code requestte required; description requestte null mandatory normalization.</td>
    <td>V18de Natural Language source language gibi görünür; Productionda modalitydir.</td>
  </tr>
  <tr>
    <td>Target Runtime</td>
    <td>* always active for code request.</td>
    <td>Production V1de value fixed `python-3.12`; UI read-only/select single value olabilir.</td>
    <td>Prompt/runtime contradiction not silently guessed.</td>
  </tr>
  <tr>
    <td>Output Contract</td>
    <td>* request level. Top-level output type V18de selected.</td>
    <td>Output contract incompatible/empty ise Pre-Check passed olsa bile candidate generation 422 OUTPUT_CONTRACT_INVALID döner.</td>
    <td>Pre-Check output contractı semantic olarak doğrulamaz; only context pinning / stale rule uygular.</td>
  </tr>
</table>

## 5.2 Dependent-field mutation contract

<table>
  <tr>
    <th>Değişiklik</th>
    <th>UI state değişimi</th>
    <th>Persisted / engine etkisi</th>
    <th>Kullanıcı metni</th>
  </tr>
  <tr>
    <td>Source Text değişir</td>
    <td>Previous status `Stale`; resolved list modal close olabilir; Pre-Check CTA visible.</td>
    <td>New source hash; prior scan artifact immutable remains but current request scan pointer invalidated. Send code request blocked.</td>
    <td>`Source changed. Run Pre-Check again before generating a candidate.`</td>
  </tr>
  <tr>
    <td>Source Language değişir</td>
    <td>`Stale`; if switched to Natural Language, optional rerun can yield Not Applicable.</td>
    <td>Normalized source_kind/source_language changes; parser route changes.</td>
    <td>`Source language changed. The previous dependency scan no longer applies.`</td>
  </tr>
  <tr>
    <td>Target Runtime değişir</td>
    <td>`Stale`.</td>
    <td>Resolver runtime adapter and generated target semantics may differ.</td>
    <td>`Target runtime changed. Run Pre-Check again.`</td>
  </tr>
  <tr>
    <td>Output Type / output contract changes</td>
    <td>`Stale`.</td>
    <td>Context hash changes; candidate output expectation must be re-pinned.</td>
    <td>`Output contract changed. Run Pre-Check again.`</td>
  </tr>
  <tr>
    <td>Resolver registry changes after Passed</td>
    <td>UI may keep last result until refresh/event; on refresh or Send a registry version mismatch becomes `Stale`.</td>
    <td>Current scan must not resolve deleted/deprecated/changed active revision automatically; fresh scan required.</td>
    <td>`Resolver registry changed. Re-run Pre-Check to confirm current dependencies.`</td>
  </tr>
  <tr>
    <td>Clear button clicked</td>
    <td>Transient form and open modal clear; V18 status resets to Not Checked with page reset.</td>
    <td>Does not delete a persisted package request, scan, candidate, draft or resolver. Existing request may remain as abandoned/audited state.</td>
    <td>`Form cleared. Existing saved artifacts were not deleted.`</td>
  </tr>
</table>

# 6. Pine TA Dependency Resolver: Karar Hiyerarşisi ve Algoritma

Pre-Checkin temel değerlendirme hiyerarşisi, “text has `ta.foo`” seviyesinde bitmez. Production V1de Parse/lexical extraction -> canonical key normalization -> resolver registry lookup -> signature compatibility -> runtime adapter compatibility -> lifecycle/approval status -> immutable dependency manifest sırasıyla değerlendirilir. Bu sıranın herhangi bir aşaması başarısızsa sonuç `passed` olamaz.

## 6.1 V18 supported primitive başlangıç scopeu

<table>
  <tr>
    <th>Canonical Pine key</th>
    <th>V18 Embedded System Package örneği</th>
    <th>Beklenen semantic not</th>
    <th>Production resolver gereği</th>
  </tr>
  <tr>
    <td>ta.sma</td>
    <td>ESP_TA_SMA</td>
    <td>Simple moving average.</td>
    <td>source,length signature; warm-up/null behavior; Python 3.12 adapter; approved revision.</td>
  </tr>
  <tr>
    <td>ta.ema</td>
    <td>ESP_TA_EMA</td>
    <td>Exponential moving average.</td>
    <td>source,length; initialization/warm-up behavior pinned.</td>
  </tr>
  <tr>
    <td>ta.rma</td>
    <td>ESP_TA_RMA</td>
    <td>Running moving average.</td>
    <td>source,length; seed semantics pinned.</td>
  </tr>
  <tr>
    <td>ta.atr</td>
    <td>ESP_TA_ATR</td>
    <td>Average true range.</td>
    <td>length; input dependencies and warm-up pinned.</td>
  </tr>
  <tr>
    <td>ta.rsi</td>
    <td>ESP_TA_RSI</td>
    <td>Relative strength index.</td>
    <td>source,length; zero denominator/null behavior pinned.</td>
  </tr>
  <tr>
    <td>ta.wma</td>
    <td>ESP_TA_WMA</td>
    <td>Weighted moving average.</td>
    <td>source,length; weighting semantics pinned.</td>
  </tr>
  <tr>
    <td>ta.vwap</td>
    <td>ESP_TA_VWAP</td>
    <td>VWAP resolver.</td>
    <td>source plus session semantics and output availability pinned.</td>
  </tr>
</table>

Bu liste Production V1in tamamlanmış PineScript standard-library desteği değildir; V18deki canonical başlangıç resolver scopeudur. Listede olmayan bir fonksiyon “support edildi” sayılmaz. Pre-Check `missing` veya `unsupported` sonucu üretir ve CP Agent bunu kendi başına alternate implementation ile değiştiremez.

## 6.2 Production resolver matching algorithm

<table>
  <tr>
    <th>1. Normalize PackageRequest context; compute source_hash + context_hash.<br/>2. Confirm source_kind/code and source_language parser route.<br/>3. Parse source with PineScript parser/lexer; collect semantic TA call nodes (not regex text hits).<br/>4. Normalize each call to canonical_key, e.g. ta.rsi.<br/>5. Read resolver registry at a consistent registry_version.<br/>6. For each call, require an active, approved ESP revision with:<br/>   - exact canonical_key<br/>   - target runtime adapter = python-3.12<br/>   - compatible function signature / arg count / arg types / optional args<br/>   - declared return shape, warm-up/null semantics, closed-bar and lookahead contract<br/>7. Build immutable DependencyScanResult with resolved refs, missing calls, unsupported calls and scanner version.<br/>8. If missing/unsupported/signature mismatch exists -&gt; PRECHECK_BLOCKED or FAILED/MANUAL_REVIEW_REQUIRED.<br/>9. Otherwise -&gt; PRECHECK_PASSED; persist resolver revision pins for candidate generation.</th>
  </tr>
</table>

## 6.3 V18 regex ile Production parser ayrımı

<table>
  <tr>
    <th>Davranış</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Code detection</td>
    <td>`//@version`, `indicator()`, `strategy()`, `library()`, `ta.*`, `plot()`, `:=`, `=&gt;` regexleriyle likely-code kararı.</td>
    <td>Language detector + parser/lexer, comments/string literals/context parsing.</td>
    <td>Regex sadece local fast hint olabilir; dependency gate decisioni olamaz.</td>
  </tr>
  <tr>
    <td>TA call extraction</td>
    <td>`/\bta\.([A-Za-z_]\w*)\b/g` ile token-like match.</td>
    <td>AST/lexical call node; function namespace/call structure and semantic context.</td>
    <td>Comment veya string içindeki `ta.rsi` false positive olmamalı.</td>
  </tr>
  <tr>
    <td>Resolver match</td>
    <td>Local packageGroups.embedded mapinde `taFunction` name match.</td>
    <td>Registry canonical key + exact approved ESP revision + signature/runtime/lifecycle validation.</td>
    <td>Package name match yeterli değildir.</td>
  </tr>
  <tr>
    <td>Missing dependency</td>
    <td>Local HTML listesinde missing function.</td>
    <td>Machine-readable missing, unsupported, signature_mismatch, resolver_not_active categories.</td>
    <td>User remediation and Admin policy categoryye göre değişir.</td>
  </tr>
</table>

# 7. Information Content Catalog: Popup, Inline Help, Warning, Toast ve Hata Metinleri

V18 Pre-Check yüzeyinde ayrı bir ⓘ bilgi düğmesi bulunmaz. Bu nedenle “ⓘ paneli” envanteri `Uygulanmaz`dır; V18deki inline helper metinleri ve result modalı kullanıcıya bilgi taşıyan yüzeylerdir. Production V1 bu metinleri aşağıdaki nihai içeriklerle sunmalıdır. Mevcut HTMLde yer alan İngilizce UI dili korunmuştur.

<table>
  <tr>
    <th>Info key / surface</th>
    <th>Panel başlığı</th>
    <th>Nihai UI metni</th>
    <th>Gösterim koşulu</th>
  </tr>
  <tr>
    <td>precheck.inline_note</td>
    <td>Inline helper</td>
    <td>Pre-Check analyses PineScript TA dependencies through Embedded System Packages. It does not translate, approve, or backtest your code.</td>
    <td>Compose action row altında; always visible.</td>
  </tr>
  <tr>
    <td>precheck.resolver_help</td>
    <td>PINE TA / EMBEDDED SYSTEM PACKAGE RESOLVER</td>
    <td>Pre-Check scans PineScript calls such as ta.sma, ta.ema, ta.rsi and ta.atr. Each detected call must resolve to an active, approved Embedded System Package revision with a compatible signature and Python 3.12 runtime adapter before code conversion can start.</td>
    <td>Resolver help section; always visible.</td>
  </tr>
  <tr>
    <td>precheck.empty_source</td>
    <td>TA PRE-CHECK RESULT</td>
    <td>No input was provided. Paste PineScript code or enter a request before running Pre-Check.</td>
    <td>Pre-Check clicked with whitespace/empty source. No job starts.</td>
  </tr>
  <tr>
    <td>precheck.description</td>
    <td>TA PRE-CHECK RESULT</td>
    <td>The entered text is not a code work. Pre-Check is not required for a natural-language request. Press Send to submit this request to CP Agent.</td>
    <td>Source normalized as description / code not detected. Production status = Not Applicable.</td>
  </tr>
  <tr>
    <td>precheck.no_dependencies</td>
    <td>TA PRE-CHECK RESULT</td>
    <td>Analysis completed. No PineScript TA function dependency was detected. READY FOR CONVERSION. You can now press Send.</td>
    <td>Pine code parsed, no supported TA call is detected.</td>
  </tr>
  <tr>
    <td>precheck.passed</td>
    <td>TA PRE-CHECK RESULT</td>
    <td>Analysis completed. All detected PineScript dependencies resolved to compatible Embedded System Package revisions. READY FOR CONVERSION. You can now press Send.</td>
    <td>All detected calls successfully resolve. The modal lists each canonical key and pinned resolver revision.</td>
  </tr>
  <tr>
    <td>precheck.blocked</td>
    <td>TA PRE-CHECK RESULT</td>
    <td>Analysis completed. One or more canonical Embedded System Package dependencies are missing or incompatible. BLOCKED. Create or update a resolver proposal, obtain Admin approval for the canonical registry entry, then run Pre-Check again.</td>
    <td>Missing, inactive, deprecated-for-new-use or signature-incompatible resolver.</td>
  </tr>
  <tr>
    <td>precheck.send_blocked</td>
    <td>TA PRE-CHECK REQUIRED</td>
    <td>Send is blocked because the current source has unresolved Embedded System Package dependencies. Resolve the missing dependencies and run a fresh Pre-Check for this exact source and runtime context.</td>
    <td>User presses Send while current code request is blocked.</td>
  </tr>
  <tr>
    <td>precheck.stale</td>
    <td>PRE-CHECK STALE</td>
    <td>Source, source language, target runtime, output contract, dependency settings, or resolver registry state changed. Run Pre-Check again before generating a candidate.</td>
    <td>Context hash or registry version mismatch.</td>
  </tr>
  <tr>
    <td>precheck.failed</td>
    <td>PRE-CHECK FAILED</td>
    <td>Pre-Check could not determine a safe dependency decision. No candidate generation was started. Review the source language and parser details, then retry or request manual review.</td>
    <td>Parser/scanner/registry technical failure.</td>
  </tr>
  <tr>
    <td>precheck.language_mismatch</td>
    <td>SOURCE LANGUAGE MISMATCH</td>
    <td>The selected source language does not match the detected source content. Choose the correct language or revise the source before Pre-Check can continue.</td>
    <td>UI selection, content detector and parser outcome disagree.</td>
  </tr>
</table>

## 7.1 Dependency result row format

<table>
  <tr>
    <th>Result kind</th>
    <th>UI row content</th>
    <th>Accessibility / safety requirement</th>
  </tr>
  <tr>
    <td>Resolved</td>
    <td>✓ `ta.rsi` -&gt; Embedded System Package found: `ESP_TA_RSI` (revision `pkgrev:...`).</td>
    <td>Do not rely on checkmark/color alone; row must include text `Resolved`. Package name and revision ID are text-escaped.</td>
  </tr>
  <tr>
    <td>Missing</td>
    <td>✕ `ta.supertrend` -&gt; Missing canonical Embedded System Package.</td>
    <td>Row includes `Missing` text and remediation action. Raw source cannot inject HTML.</td>
  </tr>
  <tr>
    <td>Signature mismatch</td>
    <td>! `ta.sma(source, length, extra)` -&gt; Resolver exists but its signature is incompatible.</td>
    <td>Show expected and detected shapes without exposing untrusted payload as markup.</td>
  </tr>
  <tr>
    <td>Unsupported / manual review</td>
    <td>? `ta.unknown` -&gt; No supported parser/resolver rule is available.</td>
    <td>Status must not be shown as Passed. Use `Manual review required` / failed state.</td>
  </tr>
</table>

## 7.2 Toast and status-line text

<table>
  <tr>
    <th>Event</th>
    <th>Success / information text</th>
    <th>Error / retry text</th>
  </tr>
  <tr>
    <td>Pre-Check accepted</td>
    <td>Pre-Check started. Checking dependencies for this exact source and runtime context.</td>
    <td>&nbsp;</td>
  </tr>
  <tr>
    <td>Scan completed / passed</td>
    <td>Pre-Check passed. Dependency manifest is ready for candidate generation.</td>
    <td>&nbsp;</td>
  </tr>
  <tr>
    <td>Scan completed / blocked</td>
    <td>&nbsp;</td>
    <td>Pre-Check blocked. Resolve the listed Embedded System Package dependencies and run it again.</td>
  </tr>
  <tr>
    <td>Source edited after passed</td>
    <td>&nbsp;</td>
    <td>Pre-Check is stale because the source changed. Run it again before sending.</td>
  </tr>
  <tr>
    <td>Network reconnect</td>
    <td>Reconnected. Latest Pre-Check status was restored from the server.</td>
    <td>Unable to retrieve current Pre-Check status. Retry status refresh; do not assume the prior UI state is valid.</td>
  </tr>
  <tr>
    <td>Retry</td>
    <td>Pre-Check retry started with a new scan attempt.</td>
    <td>Retry could not start. The request was changed by another actor; refresh the latest request first.</td>
  </tr>
</table>

# 8. Button, Command ve State Contract

<table>
  <tr>
    <th>UI action</th>
    <th>Production command / query</th>
    <th>Precondition</th>
    <th>Loading / success / error / audit</th>
  </tr>
  <tr>
    <td>Pre-Check</td>
    <td>`POST /v1/package-requests/{id}/pre-check`<br/>Conceptual: `RunPreCheck`</td>
    <td>Request exists or UI first creates a normalized Package Request; source not whitespace for real scan; caller can modify/run request.</td>
    <td>Accepted -&gt; job/scan id + context hash. UI `Checking`. Success -&gt; passed/blocked/not_applicable/failed projection. Audit: package_request_created if needed, precheck_started, precheck_completed, dependency_missing/resolved.</td>
  </tr>
  <tr>
    <td>Open result modal</td>
    <td>`GET /v1/package-requests/{id}` or scan artifact query</td>
    <td>Caller can view request + scan artifact.</td>
    <td>No mutation. Server returns current scan associated with current context, or stale/none. Audit optional read telemetry only.</td>
  </tr>
  <tr>
    <td>Close / outside click</td>
    <td>None</td>
    <td>Modal open.</td>
    <td>Transient UI-only action. Must not cancel scan, mutate status or delete evidence.</td>
  </tr>
  <tr>
    <td>Send while Passed / Not Applicable</td>
    <td>`POST /v1/package-requests/{id}/generate-candidate` (out-of-scope command; gate documented here)</td>
    <td>Nonempty request; code =&gt; current passed scan; description =&gt; not_applicable; no stale/blocked/failed status.</td>
    <td>202 accepted -&gt; candidate job. 409 PRECHECK_BLOCKED/STale required -&gt; modal/toast. Audit candidate generation start happens in Create Package flow.</td>
  </tr>
  <tr>
    <td>Retry Pre-Check</td>
    <td>Same RunPreCheck command with fresh idempotency key / attempt number</td>
    <td>Current source/context is stable and caller authorized.</td>
    <td>New attempt; old immutable scan remains. 409 conflict if request head changed; UI refresh/retry workflow.</td>
  </tr>
  <tr>
    <td>Create missing resolver proposal</td>
    <td>Conceptual `CreateEmbeddedResolverProposal`</td>
    <td>Blocked scan contains missing call; caller can create package draft/proposal.</td>
    <td>Creates proposal/draft in separate Embedded System Packages flow. Does not mark original scan passed. Audit: resolver proposal created.</td>
  </tr>
  <tr>
    <td>Admin activate resolver</td>
    <td>Separate approve_and_publish / registry update command</td>
    <td>Admin + validated ESP revision.</td>
    <td>Registry event emitted; original request becomes stale and requires fresh scan. Audit: resolver registry changed.</td>
  </tr>
</table>

## 8.1 Idempotency, stale write ve duplicate-submit behavior

- Pre-Check command: Her çağrı `Idempotency-Key` taşır. Aynı request id + context hash + key tekrarlandığında yeni scan/job veya duplicate audit kaydı üretilmez; önceki accepted/completed cevap döndürülür.

- Concurrent edits: UI command `expected_request_version` veya equivalent request head taşır. Source/context job çalışırken değişirse completed old scan artifacti saklanır; fakat response current UI stateini overwrite etmez ve status `stale` olarak görünür.

- Registry race: Passed scan ile Send arasındaki resolver registry değişiminde server candidate commandi resolver registry versionını tekrar kontrol eder. Mismatch varsa `PRECHECK_STALE` döner; browser cached Passed statei kabul edilmez.

- Loading: Bir actorun scan jobı çalışırken ikinci click serverda idempotent reuse veya `PRECHECK_ALREADY_RUNNING` projectionı ile sonuçlanır. UI birden fazla modal/job progressi yaratmaz.

# 9. Kullanıcı ve Sistem Akışları

## 9.1 Başarılı Pine code dependency akışı

1. Kullanıcı Source Text içine PineScript kodu yapıştırır; Source Language = PineScript, Target Runtime = Python 3.12 bağlamı seçilidir.

2. Kullanıcı Pre-Checke basar. UI source/context changesini normalize eder; request yoksa Package Request oluşturulur, ardından idempotent dependency scan başlatılır.

3. Parser `ta.rsi` ve `ta.ema` çağrılarını semantic call node olarak tespit eder.

4. Registry, her çağrı için active approved ESP revisionı, compatible signature ve Python 3.12 adapterını döndürür.

5. DependencyScanResult immutable artifact olarak yazılır; request state PRECHECK_PASSED olur; status pill `Passed` görünür.

6. TA PRE-CHECK RESULT modalı resolved rowsı ve exact resolver revision pinsini gösterir.

7. Kullanıcı Send ile candidate generation başlatabilir. Candidate job, dependency manifestteki resolver revisionlarını pinleyerek çalışır.

## 9.2 Missing dependency / blocked akışı

1. Parser `ta.supertrend` çağrısını tespit eder; active registryde compatible canonical resolver yoktur.

2. Pre-Check request stateini PRECHECK_BLOCKED yapar, missing_calls listesiyle immutable scan artifacti kaydeder ve dependency_missing audit eventini yazar.

3. UI modalı BLOCKED durumunu ve resolver proposal remediationını gösterir. Send clicki aynı current source hash için serverda 409 PRECHECK_BLOCKED döner.

4. User, Supervisor veya Agent bir Embedded System Package proposal/draft üretebilir. Bu çözüm canonical registryye henüz girmez.

5. Admin, gerekli signature, semantic spec, warm-up/null behavior, closed-bar/lookahead contract ve test vectors kanıtlarıyla ESPyi approve_and_publish eder.

6. Registry eventinden sonra original request stale olur. Kullanıcı/Agent fresh Pre-Check çalıştırır; yeni scan resolved revisionı pinler.

## 9.3 Natural-language description akışı

1. Kullanıcı source textarea içine doğal dil teknik tarif girer veya Creation Mode = Generate From Description seçer.

2. Backend requesti `source_kind=DESCRIPTION`, `source_language=null` olarak normalize eder; Natural Language parser language değildir.

3. Pre-Check çalıştırılırsa result `PRECHECK_NOT_APPLICABLE` olur ve final UI metni CP Agenta Send ile devam edilmesini söyler.

4. Send dependency gate olmadan candidate generationa geçebilir; ancak output contract/test specification/clarification kuralları ayrı şekilde uygulanır.

## 9.4 Stale / concurrency recovery akışı

1. Kullanıcı Passed sonucu aldıktan sonra source text, target runtime veya output typeı değiştirir.

2. Frontend local comparison veya server update response ile statusu `Stale` gösterir; old scan sonuç detayını historical evidence olarak korur ama Sendi code request için engeller.

3. Kullanıcı yeni Pre-Check başlatır. Yeni context hash, new scan attempt ve audit correlation oluşturulur.

4. Başka actor aynı Package Requesti değiştirdiyse server 409 REQUEST_VERSION_CONFLICT döner. UI latest canonical requesti yükler, kullanıcı farkları görür ve yeni intentionla retry yapar.

## 9.5 Technical failure / parser unsupported recovery akışı

1. Source Language PineScript seçilir fakat content detector/parser sourceun başka veya desteklenmeyen grammar olduğunu belirler.

2. Backend SOURCE_LANGUAGE_MISMATCH, PARSE_UNSUPPORTED veya MANUAL_REVIEW_REQUIRED ile Pre-Checki failed statee geçirir; positive `passed` sonucu üretmez.

3. UI kullanıcıya selected languagei düzeltme, sourceu sadeleştirme veya manual review/proposal yolunu gösterir.

4. Retry yeni idempotency key ve attempt ile başlar. Eski failure evidence audit/provenance için korunur.

# 10. Production Backend ve Domain Modeli

## 10.1 Minimum kalıcı kayıtlar

<table>
  <tr>
    <th>Kayıt</th>
    <th>Zorunlu alanlar</th>
    <th>Pre-Check ilişkisi</th>
  </tr>
  <tr>
    <td>package_request</td>
    <td>id, actor_ref, package_type, creation_mode, source_ref/hash, source_kind, source_language, target_runtime, output_contract_draft, state, context_hash, request_version, idempotency_key.</td>
    <td>Current work contextini taşır. Source/context değişimi state -&gt; requested/stale projection ve new context hash üretir.</td>
  </tr>
  <tr>
    <td>dependency_scan</td>
    <td>id, request_ref, attempt_no, source_hash, context_hash, language, scanner_version, registry_version, detected_calls, resolved_refs, missing_calls, unsupported_calls, status, result_artifact_ref, completed_at.</td>
    <td>Immutable Pre-Check evidence. A scan başka source/context için reused edilemez.</td>
  </tr>
  <tr>
    <td>embedded_resolver_registry</td>
    <td>canonical_key, active_revision_ref, signature, runtime, registry_status, registry_version.</td>
    <td>Pre-Checkin canonical lookup kaynağı. Sadece root.lifecycle_state=active, revision.validation_state=passed, revision.approval_state=approved, visibility_scope=system/published ve registry_trust_state=trusted olan eligible ESP revisionlarını işaret eder.</td>
  </tr>
  <tr>
    <td>package_root / package_revision</td>
    <td>id, package_type, owner_ref, payload/output_contract/dependency manifest refs, lifecycle/approval state.</td>
    <td>Pre-Check draft oluşturmaz; candidate/draft oluştuğunda resolved resolver revisions dependency manifestine taşınır.</td>
  </tr>
  <tr>
    <td>job / event stream</td>
    <td>job_id, command, state, progress, correlation_id, error ref, timestamps.</td>
    <td>Implementation Decision: scan job durable yürütülür, UI SSE veya polling ile status görüntüler.</td>
  </tr>
  <tr>
    <td>audit_event</td>
    <td>event_type, actor_ref/type, request/scan/resolver ref, prior/new state, source/context hash, correlation_id, timestamp.</td>
    <td>precheck_started/completed, dependency_missing/resolved, stale, retry, registry changes immutable audit streamde yer alır.</td>
  </tr>
</table>

## 10.2 Request, scan ve resolver relationları

<table>
  <tr>
    <th>PackageRequest (mutable current work context)<br/>  1 -&gt; N DependencyScan (immutable evidence; source_hash + context_hash pinned)<br/>  N -&gt; 0..N CandidateAttempt (only after gate permits)<br/><br/>DependencyScan.resolved_refs[]<br/>  -&gt; EmbeddedResolverRegistry (registry version observed)<br/>  -&gt; EmbeddedSystemPackageRevision (exact immutable approved resolver revision)<br/><br/>CandidateAttempt / DraftPackageRevision.dependency_manifest<br/>  -&gt; repeats exact resolver revision refs; never dynamic &quot;latest resolver&quot; lookup.</th>
  </tr>
</table>

## 10.3 API contract core

<table>
  <tr>
    <th>Endpoint / command</th>
    <th>Request invariant</th>
    <th>Response invariant</th>
  </tr>
  <tr>
    <td>POST /v1/package-requests</td>
    <td>Normalizes user/Agent input into Package Request. `target_runtime=python-3.12` in Production V1. Idempotency key mandatory.</td>
    <td>Returns request id, request version, normalized source kind/language, state=requested and context hash.</td>
  </tr>
  <tr>
    <td>POST /v1/package-requests/{id}/pre-check</td>
    <td>Expected request version + idempotency key mandatory; server recomputes source/context hash.</td>
    <td>202 accepted or idempotent completed response: job/scan id, state precheck_pending/checking, context hash. Later projection contains passed/blocked/not_applicable/failed.</td>
  </tr>
  <tr>
    <td>GET /v1/package-requests/{id}</td>
    <td>Read policy enforced.</td>
    <td>Returns current request context, current precheck summary, latest compatible scan detail and allowed actions; old scans may be queried as history when policy permits.</td>
  </tr>
  <tr>
    <td>GET /v1/embedded-system-resolvers?canonical_key=pine.ta.rsi</td>
    <td>Does not mutate. Registry query is policy-aware but canonical resolver metadata is system-owned.</td>
    <td>Returns active revision ref, signature, runtime, lifecycle/registry status; must not return deleted resolver as active.</td>
  </tr>
  <tr>
    <td>POST /v1/package-requests/{id}/generate-candidate</td>
    <td>Out-of-scope action but gate is essential. Current request must be nonempty, nonstale and precheck-permitted.</td>
    <td>202 candidate job, or 409 PRECHECK_BLOCKED/PRECHECK_STALE, 422 input contract error, 403 authorization denial.</td>
  </tr>
</table>

## 10.4 Example payloads

<table>
  <tr>
    <th>RunPreCheck request (conceptual)<br/>{<br/>  &quot;expected_request_version&quot;: 7,<br/>  &quot;idempotency_key&quot;: &quot;uuid&quot;,<br/>  &quot;source_hash&quot;: &quot;sha256:...&quot;,<br/>  &quot;context_hash&quot;: &quot;sha256:...&quot;<br/>}<br/><br/>DependencyScanResult (conceptual)<br/>{<br/>  &quot;request_id&quot;: &quot;prq_...&quot;,<br/>  &quot;source_hash&quot;: &quot;sha256:...&quot;,<br/>  &quot;context_hash&quot;: &quot;sha256:...&quot;,<br/>  &quot;language&quot;: &quot;pinescript&quot;,<br/>  &quot;scanner_version&quot;: &quot;pine-parser-1.0&quot;,<br/>  &quot;registry_version&quot;: &quot;esp-reg-42&quot;,<br/>  &quot;detected_calls&quot;: [&quot;ta.sma&quot;, &quot;ta.rsi&quot;],<br/>  &quot;resolved&quot;: [<br/>    {&quot;call&quot;:&quot;ta.sma&quot;,&quot;embedded_revision_ref&quot;:&quot;pkgrev:esp-ta-sma:v3&quot;},<br/>    {&quot;call&quot;:&quot;ta.rsi&quot;,&quot;embedded_revision_ref&quot;:&quot;pkgrev:esp-ta-rsi:v2&quot;}<br/>  ],<br/>  &quot;missing&quot;: [],<br/>  &quot;unsupported&quot;: [],<br/>  &quot;result&quot;: &quot;passed&quot;<br/>}</th>
  </tr>
</table>

# 11. Agent Tool/API Eşdeğeri ve Sürekli Çalışma Sınırı

Agent, V18 Create Package ekranını veya Pre-Check düğmesini tarayıcı otomasyonuyla kullanmak zorunda değildir. Human UI ve Agent Tool Gateway aynı normalized Package Request / RunPreCheck domain commandini çağırır. UI yalnız kontrol ve inceleme yüzeyidir; Agentın research veya conversion branchi browser açık kalmadığında, kullanıcı logout olduğunda veya Lab Assistantla normal sohbet edildiğinde durmaz.

<table>
  <tr>
    <th>Human UI behavior</th>
    <th>Agent tool equivalent</th>
    <th>Parity / policy consequence</th>
  </tr>
  <tr>
    <td>Source Text gir + Pre-Checke bas</td>
    <td>`create_package_request` + `run_precheck` tool calls</td>
    <td>Aynı source/context hash, resolver registry, validation ve audit uygulanır.</td>
  </tr>
  <tr>
    <td>Result modalını gör</td>
    <td>`get_dependency_scan` tool call</td>
    <td>Agent structured scan resulti okur; UI modalına ihtiyaç duymaz.</td>
  </tr>
  <tr>
    <td>Missing resolver mesajı</td>
    <td>`create_embedded_resolver_proposal` tool call</td>
    <td>Agent proposal artifact üretir; canonical resolver approval/publish yapamaz.</td>
  </tr>
  <tr>
    <td>Send blocked mesajı</td>
    <td>`generate_candidate` returns PRECHECK_BLOCKED</td>
    <td>Agent aynı request branchini blocked tutar, retry şartını queue/artifacte yazar.</td>
  </tr>
  <tr>
    <td>Admin resolver activation</td>
    <td>Admin-only approve_and_publish command</td>
    <td>Agent registryyi mutasyona uğratamaz; registry event sonrası fresh scan talep eder.</td>
  </tr>
</table>

## 11.1 Agent branch behavior

- Missing dependency: Agent ana research loopunu durdurmaz. Sadece ilgili package conversion branchini `precheck_blocked` olarak işaretler; resolver proposal veya follow-up task üretir.

- Checkpoint: Agent, blocked scanın source/context hashini, missing callsı, resolver registry versionını ve remediationı checkpoint/artifacte kaydeder. Daha sonra Admin action veya registry eventinden sonra fresh scan çalıştırır.

- No UI-only bypass: Agent için “allow unverified conversion” veya local client helper ile Send bypass yolu yasaktır. Tool Gateway aynı backend gatei kullanır.

- Provenance: Agentinitiated precheck artifacti actor=Agent, task/checkpoint refs, tool version, scanner version, data/request context ve correlation id taşır.

# 12. Validation, Hata ve Recovery Contract

<table>
  <tr>
    <th>Class / error code</th>
    <th>Ne zaman</th>
    <th>UI davranışı</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>EMPTY_SOURCE</td>
    <td>Source boş/whitespace.</td>
    <td>TA PRE-CHECK RESULT informative modal; no job.</td>
    <td>Source veya technical description gir; Send emptiness validationı ayrıca çalışır.</td>
  </tr>
  <tr>
    <td>SOURCE_LANGUAGE_MISMATCH</td>
    <td>Selected source language, detector ve parser uyuşmuyor.</td>
    <td>Failed modal; selected field highlighted.</td>
    <td>Language seçimini düzelt veya sourceu uyumlu hale getir; fresh scan.</td>
  </tr>
  <tr>
    <td>PARSE_UNSUPPORTED</td>
    <td>Production parser/lexer grammar için güvenli extraction yapamıyor.</td>
    <td>Failed/Manual review required; Passed gösterilmez.</td>
    <td>Parser support eklenmesi, source exportun sadeleştirilmesi veya explicit manual review.</td>
  </tr>
  <tr>
    <td>MISSING_EMBEDDED_DEPENDENCY</td>
    <td>Canonical resolver yok.</td>
    <td>Blocked result rows + remediation link/action.</td>
    <td>ESP proposal -&gt; validation -&gt; Admin canonical approval -&gt; fresh Pre-Check.</td>
  </tr>
  <tr>
    <td>RESOLVER_SIGNATURE_MISMATCH</td>
    <td>Key bulunuyor ama signature/return/warmup/runtime uyumsuz.</td>
    <td>Blocked; missingden farklı warning.</td>
    <td>Compatible resolver revision üret; registry activate; rerun.</td>
  </tr>
  <tr>
    <td>RESOLVER_NOT_ACTIVE</td>
    <td>Resolver soft-deleted, deprecated-for-new-use veya registryden çıkarılmış.</td>
    <td>Blocked/stale depending on time of change.</td>
    <td>Active approved resolver revision ile fresh scan.</td>
  </tr>
  <tr>
    <td>PRECHECK_STALE</td>
    <td>Source/context/registry version scan sonrası değişti.</td>
    <td>Warning/toast + Send blocked for code.</td>
    <td>Latest requesti yükle; fresh scan.</td>
  </tr>
  <tr>
    <td>REQUEST_VERSION_CONFLICT</td>
    <td>Another actor request headini değiştirdi.</td>
    <td>Conflict banner; no optimistic overwrite.</td>
    <td>Refresh canonical request; compare/reapply intended change; retry.</td>
  </tr>
  <tr>
    <td>PRECHECK_BLOCKED</td>
    <td>Send/candidate command blocked state içinde çağrıldı.</td>
    <td>TA PRE-CHECK REQUIRED modal.</td>
    <td>Resolve dependencies; rerun exact current context.</td>
  </tr>
  <tr>
    <td>PRECHECK_FAILED</td>
    <td>Scanner/job technical failure.</td>
    <td>Failure modal; retry CTA.</td>
    <td>Retry creates new attempt; inspect structured error artifact if repeated.</td>
  </tr>
  <tr>
    <td>AUTHORIZATION_DENIED</td>
    <td>Caller owner/policy erişimine sahip değil.</td>
    <td>Permission message; no raw policy internals.</td>
    <td>Ask owner/Admin for access; do not rely on hidden button workarounds.</td>
  </tr>
</table>

## 12.1 Closed-bar / repaint / future-leak boundary

V18 Pre-Check promptu “Sinyaller yalnızca kapanmış mumlarda geçerli olsun” der. Bu, Pre-Checkin kullanıcıya hatırlattığı önemli requirementtir; fakat Pre-Checkin tek başına bir repaint/future-leak approvalı olduğu anlamına gelmez. Pre-Check resolver matching sırasında resolver semantic specinde closed-bar, warm-up/null, lookahead ve availability davranışının tanımlı olup olmadığını doğrular. Candidate codeun future-data/repaint denetimi; static risk scan, dynamic prefix-invariance ve availability/multi-timeframe testleri ile Validation aşamasında kanıtlanır.

<table>
  <tr>
    <th>Yasak kısa yol: Pre-Check Passed sonucu, “bu code repaint yapmaz”, “market data üzerinde doğrulandı” veya “approve edilebilir” anlamında kullanılmayacaktır. Bu iddialar yalnız ayrı Validation Evidence ile yapılabilir.</th>
  </tr>
</table>

# 13. Lifecycle, Revision, Audit ve Trash Etkileri

## 13.1 Canonical lifecycle mapping

<table>
  <tr>
    <th>V18 görünümü</th>
    <th>Production request state</th>
    <th>Anlam</th>
  </tr>
  <tr>
    <td>Not Checked</td>
    <td>requested / precheck_pending yok</td>
    <td>UI başlangıç göstergesi; persisted package revision state değildir.</td>
  </tr>
  <tr>
    <td>Not Checked after natural text</td>
    <td>precheck_not_applicable</td>
    <td>Description mode dependency gate dışında; Send permitted.</td>
  </tr>
  <tr>
    <td>Passed</td>
    <td>precheck_passed</td>
    <td>Exact source/context/registry snapshot dependency manifest için hazır.</td>
  </tr>
  <tr>
    <td>Blocked</td>
    <td>precheck_blocked</td>
    <td>Missing/incompatible canonical resolver. Same source hash candidate generation blocked.</td>
  </tr>
  <tr>
    <td>No V18 state</td>
    <td>precheck_pending / checking</td>
    <td>Durable scan job devam ediyor.</td>
  </tr>
  <tr>
    <td>No V18 state</td>
    <td>precheck_stale</td>
    <td>Previous result historical evidence; current context invalid.</td>
  </tr>
  <tr>
    <td>No V18 state</td>
    <td>precheck_failed</td>
    <td>No safe dependency decision. Technical/manual review required.</td>
  </tr>
</table>

## 13.2 Audit events

<table>
  <tr>
    <th>Event</th>
    <th>Minimum audit fields</th>
    <th>Neden</th>
  </tr>
  <tr>
    <td>package_request_created / updated</td>
    <td>actor_ref/type, request_ref, prior/new context hash, correlation id, timestamp.</td>
    <td>İstek normalizasyonu ve source-context değişiminin izlenebilirliği.</td>
  </tr>
  <tr>
    <td>precheck_started</td>
    <td>actor, request_ref, scan attempt, source/context hash, scanner version, job ref.</td>
    <td>Duplicate/retry/jobs ayrımı ve operational trace.</td>
  </tr>
  <tr>
    <td>precheck_completed</td>
    <td>result, resolved/missing/unsupported counts, registry version, scan artifact ref.</td>
    <td>Neden passed/blocked kararının denetlenmesi.</td>
  </tr>
  <tr>
    <td>dependency_resolved / dependency_missing</td>
    <td>canonical key, resolver revision ref or missing signature, request/scan refs.</td>
    <td>Resolver remediation ve provenance.</td>
  </tr>
  <tr>
    <td>precheck_stale</td>
    <td>old scan ref, old/new context hash or registry version, trigger actor/system.</td>
    <td>Eski Passed sonucun yeni inputta yanlış kullanılması önlenir.</td>
  </tr>
  <tr>
    <td>resolver_registry_changed</td>
    <td>Admin actor, canonical key, old/new active revision, approval evidence ref.</td>
    <td>Historical pins korunurken yeni prechecklerin doğru resolverı kullanması.</td>
  </tr>
  <tr>
    <td>soft_deleted / restored / purged</td>
    <td>resource ref, actor, reason, prior/new lifecycle, Trash record ref.</td>
    <td>Recovery, authorization, legal/audit trace.</td>
  </tr>
</table>

## 13.3 Soft delete, restore ve historical integrity

- Clear != delete: V18 `Clear` yalnız form/local state temizler. Productionda Clear, visible input stateini temizler veya açık request draftını abandon eder; existing dependency scan, candidate, draft package veya approved package artifactini silmez.

- Soft delete: Package Request, scan-related work artifact veya ESP root silinmek istenirse normal delete command Modül 3 soft delete + Trash audit akışına gider. Delete button tarafından client array temizlemek yeterli değildir.

- Admin-only recovery: Trash listesi, restore ve permanent delete yalnız Admin tarafından yapılır. User, Supervisor ve Agent kendi outputunu soft delete edebilir ama Trashı göremez/restore edemez.

- Historical pins: An approved ESP revision sonradan superseded/deprecated/soft deleted olsa bile historical candidate/draft package revisionı ve Backtest manifesti pinned resolver revisionı üzerinden okunabilir kalır. Yeni Pre-Check ise deleted/inactive resolverı resolved saymaz.

- Restore effect: Restored Package Request veya resolver revision otomatik current/active hale gelmez. Restored request current context için stale sayılır; restored ESP ayrıca valid approval/registry policy ile active mappinge alınmalıdır.

# 14. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Konu</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Pre-Check location</td>
    <td>Create Package compose içindeki button + popup; independent page route yok.</td>
    <td>Same logical surface can remain embedded; real state Package Request + Dependency Scan backend projectionundan gelir.</td>
    <td>“Pre-Check page” bu 22li dokümantasyon sırasındaki mantıksal workflow sayfasıdır; V18deki physical UI location aynen ayrı route üretme zorunluluğu doğurmaz.</td>
  </tr>
  <tr>
    <td>Code detector</td>
    <td>Regex / heuristic.</td>
    <td>Parser/lexer + semantic dependency extraction.</td>
    <td>Regex only preview helper; server gate cannot rely on it.</td>
  </tr>
  <tr>
    <td>Resolver lookup</td>
    <td>packageGroups.embedded local object map, function name only.</td>
    <td>Active approved registry, exact resolver revision, signature/runtime/warm-up/availability compatibility.</td>
    <td>Name match -&gt; canonical key/signature/version pin mapping.</td>
  </tr>
  <tr>
    <td>Target runtime</td>
    <td>Dropdown PHP; default prompt Python conversion asks.</td>
    <td>Production V1 target runtime Python 3.12.</td>
    <td>Master canonical decision overrides prototype. PHP is not shown as active Production V1 runtime option.</td>
  </tr>
  <tr>
    <td>Natural language</td>
    <td>V18 says not code, keeps state `Not Checked`, asks user to press Send.</td>
    <td>State = precheck_not_applicable; request normalizes `source_kind=DESCRIPTION`, `source_language=null`.</td>
    <td>Same user journey, but correct server lifecycle is explicit.</td>
  </tr>
  <tr>
    <td>Send gate</td>
    <td>Only `precheckBlocked` boolean blocks Send.</td>
    <td>Server blocks code candidate generation for not_checked/pending/stale/blocked/failed; descriptions can proceed with not_applicable.</td>
    <td>Prevents bypass by stale client boolean or direct API calls.</td>
  </tr>
  <tr>
    <td>Status storage</td>
    <td>cpState local values: Not Checked/Passed/Blocked.</td>
    <td>Persisted request/scan state, job status and audit/event stream.</td>
    <td>Refresh/logout/browser close cannot erase or falsify domain state.</td>
  </tr>
  <tr>
    <td>Modal result</td>
    <td>Static HTML built client side; resolved/missing rows text escaped.</td>
    <td>Server returns structured scan result; frontend safe renders it; modal is transient.</td>
    <td>Do not render raw source/error strings with unsafe innerHTML.</td>
  </tr>
  <tr>
    <td>Blocked remediation</td>
    <td>Message says Admin action required.</td>
    <td>All can propose/draft ESP; only Admin can approve/publish canonical resolver registry change.</td>
    <td>Makes role rule precise without blocking research proposals.</td>
  </tr>
</table>

# 15. Kodcu AI için Implementation Rules

1. Pre-Checki standalone compiler, backtest veya approval servicei olarak implement etme; yalnız dependency/static gate olarak sınırla.

2. V18 regexini Production dependency kararının tek kaynağı yapma. PineScript source için parser/lexer tabanlı semantic call extraction zorunludur.

3. Resolver eşleşmesini package adı veya canonical key eşitliğiyle bitirme. Active approved ESP revision, target runtime adapter, signature, return shape, warm-up/null ve availability/closed-bar sözleşmesi birlikte doğrulanmalıdır.

4. Her DependencyScanResult source_hash, context_hash, scanner_version ve registry_version taşımalıdır. Bu alanlar olmadan Passed sonucu persist edilmez.

5. Source, source language, target runtime, output contract veya dependency ayarı değiştiğinde current scanı otomatik Stale yap. Eski Passed sonucuyle candidate generation başlatma.

6. Production V1 target_runtime değerini `python-3.12` olarak sabitle. V18de görünen PHP dropdownını veya prompt/runtime çelişkisini servera taşıma.

7. Natural Language seçeneğini parser language olarak persist etme. `source_kind=DESCRIPTION`, `source_language=null`, `precheck_not_applicable` kullan.

8. Pre-Check commandi ve Candidate Generation commandi server-side idempotency key + expected request version ile çalışmalıdır. Client status booleanına güvenme.

9. Pre-Check sonucu current request contextine ait değilse veya resolver registry versionı değişmişse Sendde tekrar validate et; `PRECHECK_STALE` dön.

10. No dependency detected durumunu otomatik validation/approval kanıtı sayma. Repaint/future-leak, syntax, runtime, output contract, market data ve baseline testleri ayrı validation işleridir.

11. Missing ESP tespit edildiğinde CP Agentın veya Agentın kendi generated code içine ad hoc resolver gömmesine izin verme. Dependency manifest canonical ESP revision ref taşımalıdır.

12. Admin dışındaki actorların resolver proposal/draft oluşturmasına izin ver; fakat canonical resolver registry update, approve_and_publish veya active mapping mutationını yalnız Admin commandiyle koru.

13. Agent için UI tıklama zorunluluğu, browser session bağımlılığı veya special bypass endpoint oluşturma. Tool Gateway aynı normalized request/precheck commandini çağırmalıdır.

14. Loading, completed, blocked, stale ve failed stateini durable job/event server stateinden render et. Browser refresh veya modal kapanışı scanı iptal etmez.

15. Clear düğmesini soft delete yerine kullanma. Kalıcı request/draft/package/ESP silmeleri Module 3 soft delete + Trash + audit üzerinden yürür.

16. Raw source, parser output veya error textini modal HTMLine doğrudan interpolate etme. Safe text rendering/sanitization zorunludur.

# 16. Acceptance Tests

<table>
  <tr>
    <th>ID</th>
    <th>Scenario</th>
    <th>Expected result</th>
  </tr>
  <tr>
    <td>PC-01</td>
    <td>V18-like initial state</td>
    <td>Pre-Check surface status pill `Not Checked` / Production request state `requested`; no persisted Package Revision is created solely by rendering UI.</td>
  </tr>
  <tr>
    <td>PC-02</td>
    <td>Empty source + Pre-Check click</td>
    <td>No scan job starts. UI shows TA PRE-CHECK RESULT with final empty-input text. Send separately rejects empty request.</td>
  </tr>
  <tr>
    <td>PC-03</td>
    <td>Natural language description + Pre-Check</td>
    <td>Backend normalizes source_kind=DESCRIPTION/source_language=null; result PRECHECK_NOT_APPLICABLE; Send is allowed without code dependency gate.</td>
  </tr>
  <tr>
    <td>PC-04</td>
    <td>PineScript with ta.rsi and ta.ema; compatible active ESPs</td>
    <td>Parser finds calls; DependencyScanResult includes exact resolver revision refs; state PRECHECK_PASSED; Send allowed.</td>
  </tr>
  <tr>
    <td>PC-05</td>
    <td>PineScript with ta.supertrend; no registry resolver</td>
    <td>PRECHECK_BLOCKED; missing_calls includes ta.supertrend; Send receives 409 MISSING_EMBEDDED_DEPENDENCY/PRECHECK_BLOCKED; no candidate job is queued.</td>
  </tr>
  <tr>
    <td>PC-06</td>
    <td>Comment/string contains `ta.rsi`, no function call</td>
    <td>Parser does not create a false dependency. Regex-only matching cannot make status Passed/Blocked.</td>
  </tr>
  <tr>
    <td>PC-07</td>
    <td>Resolver exists by name but wrong arity/runtime/signature</td>
    <td>Result is blocked with RESOLVER_SIGNATURE_MISMATCH, not passed.</td>
  </tr>
  <tr>
    <td>PC-08</td>
    <td>Passed result then Source Text changes</td>
    <td>Current UI state becomes Stale; server candidate command rejects current code context until fresh Pre-Check.</td>
  </tr>
  <tr>
    <td>PC-09</td>
    <td>Passed result then resolver registry active revision changes</td>
    <td>Candidate command registry recheck identifies mismatch; returns PRECHECK_STALE; old scan remains historical evidence.</td>
  </tr>
  <tr>
    <td>PC-10</td>
    <td>Source Language PineScript but content parser detects Python</td>
    <td>No candidate starts. SOURCE_LANGUAGE_MISMATCH/REQUIRES_CLARIFICATION displayed with recovery text.</td>
  </tr>
  <tr>
    <td>PC-11</td>
    <td>Duplicate Pre-Check click / same idempotency key</td>
    <td>Only one scan/job/audit operation is created; replay returns same accepted/completed result.</td>
  </tr>
  <tr>
    <td>PC-12</td>
    <td>Source edited while scan is running</td>
    <td>Completed old scan does not overwrite newer UI context; old artifact retained, current status is Stale.</td>
  </tr>
  <tr>
    <td>PC-13</td>
    <td>User attempts direct candidate API call while blocked</td>
    <td>Server policy returns 409; manipulating disabled/hidden frontend controls cannot bypass gate.</td>
  </tr>
  <tr>
    <td>PC-14</td>
    <td>User tries resolver approval</td>
    <td>403 package_publish_admin_only / embedded resolver approval Admin only. Proposal/draft remains intact.</td>
  </tr>
  <tr>
    <td>PC-15</td>
    <td>Agent runs precheck with browser closed</td>
    <td>Tool Gateway run works; scan/audit/checkpoint provenance is stored; no UI automation dependency.</td>
  </tr>
  <tr>
    <td>PC-16</td>
    <td>Agent branch hits missing dependency</td>
    <td>Only conversion branch precheck_blocked; unrelated Agent tasks continue. Resolver proposal/follow-up artifact may be queued.</td>
  </tr>
  <tr>
    <td>PC-17</td>
    <td>Modal close / browser refresh during checking</td>
    <td>Modal close does not cancel job; refresh rehydrates current job/status from server; duplicate scan not created.</td>
  </tr>
  <tr>
    <td>PC-18</td>
    <td>Clear clicked after an existing scan/candidate/draft</td>
    <td>Visible form clears; existing persistent artifacts remain. No Trash record is created by Clear.</td>
  </tr>
  <tr>
    <td>PC-19</td>
    <td>Soft delete an ESP that historical package revision referenced</td>
    <td>Historical dependency manifest remains readable/reproducible; new Pre-Check does not resolve soft-deleted/inactive ESP.</td>
  </tr>
  <tr>
    <td>PC-20</td>
    <td>Trash restore attempted by User/Supervisor/Agent</td>
    <td>Server denies; only Admin can restore/permanently delete. Restored request must be stale; restored ESP needs active registry policy before resolving new scan.</td>
  </tr>
  <tr>
    <td>PC-21</td>
    <td>No TA dependency found</td>
    <td>State PRECHECK_PASSED; UI says Ready for conversion. No claim about repaint, future leak, validation or approval is made.</td>
  </tr>
  <tr>
    <td>PC-22</td>
    <td>Result modal content contains untrusted package/source string</td>
    <td>UI safely renders text; no HTML/script injection or layout corruption occurs.</td>
  </tr>
</table>

# 17. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 uyumu</td>
    <td>Evet. Pre-Check dependency gate, ESP canonical resolver, source/context stale, Python 3.12 target runtime, role-based resolver approval, audit/Trash ve Agent parity Modül 8 / cross-cutting modules ile hizalıdır.</td>
  </tr>
  <tr>
    <td>V18 prototype ve Production V1 ayrımı</td>
    <td>Evet. Regex/local map/PHP dropdown/local cpState gibi prototype davranışlar açıkça ayrılmış; Production parser/registry/immutable scan/server gate olarak tanımlanmıştır.</td>
  </tr>
  <tr>
    <td>Scope sınırı</td>
    <td>Evet. Candidate, Draft Package, validation/baseline/approval ve ESP management yalnız doğrudan dependency olarak anılmış; kendi ayrı sayfa sözleşmeleri yeniden yazılmamıştır.</td>
  </tr>
  <tr>
    <td>Package terminology</td>
    <td>Evet. Embedded System Package canonical reusable package türüdür. Trading Signal ve Trade Log bu belgeye package type olarak sokulmamıştır.</td>
  </tr>
  <tr>
    <td>Agent sınırı</td>
    <td>Evet. Agent UI tıklamasına veya chat/browsere bağlanmamış; Tool Gateway üzerinden same command parity tanımlanmıştır.</td>
  </tr>
  <tr>
    <td>Trash / lifecycle</td>
    <td>Evet. Clear ile delete ayrılmış; soft delete, Admin-only restore/purge ve historical resolver pins korunmuştur.</td>
  </tr>
  <tr>
    <td>Future Dev sınırı</td>
    <td>Evet. PHP/C++ gibi future runtime adapterları active Production V1 optionu olarak anlatılmamış; current V1 Python 3.12de sabitlenmiştir.</td>
  </tr>
  <tr>
    <td>Requiredness / messages / states</td>
    <td>Evet. Source/context conditional requiredness, status lifecycle, popup/inline/toast/error final textleri ve recovery yolları yazılmıştır.</td>
  </tr>
</table>
