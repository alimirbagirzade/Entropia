---
title: "Entropia V18 — Trading Signal Page Documentation v1.1"
page_number: 4
document_type: "Page implementation specification"
source_document: "Entropia_V18_Trading_Signal_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Trading Signal Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | PAGE DOCUMENTATION 4/22 | TRADING SIGNAL
> **Original DOCX footer:** Canonical page documentation | Production V1 alignment |

ENTROPIA V18

TRADING SIGNAL

Sayfa Dokümantasyonu 4/22 | External Working Object source, import, revision ve Mainboard binding sözleşmesi

<table>
  <tr>
    <th>Scope Boundary Bu belge yalnız Trading Signal çalışma nesnesinin ayrıntı ekranını kapsar. Add Outsource Signal üst menü seçicisi, Trade Log, Mainboard kompozisyonu, Ready Check, Allocation, Run ve Results kendi sayfa dokümanlarında ayrıntılanır; burada yalnız bu sayfanın doğrudan etkileşim noktaları kadar referans verilir.</th>
  </tr>
</table>

# 0. Document Control, Scope ve Source Traceability

<table>
  <tr>
    <th>Kayıt</th>
    <th>Değer</th>
  </tr>
  <tr>
    <td>Belge adı</td>
    <td>Entropia V18 - Trading Signal Page Documentation v1.1</td>
  </tr>
  <tr>
    <td>Sıra / kapsam</td>
    <td>[4]/22 - Trading Signal. V18de bağımsız route değil; Mainboard satırının expanded details paneli olarak görünür.</td>
  </tr>
  <tr>
    <td>Canonical teknik kaynak</td>
    <td>Master Technical Reference v1.0: Modül 0, 1, 2, 3, 9, 11, 12, 19, 20 ve CR-01 / CR-03 / CR-04 / CR-09.</td>
  </tr>
  <tr>
    <td>Prototip kaynak</td>
    <td>index_guncellenmis_duzeltilmis_v18.html: Add Outsource Signal &gt; Trading Signal, addSignalPackageBox(), createTradingDataDetailsContent(&quot;signal&quot;), Ready Check helpers ve legacy package library labels.</td>
  </tr>
  <tr>
    <td>Anlatım standardı</td>
    <td>Sayfa Bazlı Dokümantasyon Handoff ve Çalışma Standardı v1.1; ayrıntı/karar anlatımı için 2.3. POSITION ENTRY LOGIC örneği.</td>
  </tr>
  <tr>
    <td>Temel canonical ayrım</td>
    <td>Trading Signal bir Package değildir. `WorkingItemKind = trading_signal`; PackageKind enumuna eklenmez; `GET /packages` ile dönmez.</td>
  </tr>
  <tr>
    <td>Kapsam dışı</td>
    <td>Trade Log schema ve import semantiği; Add Outsource Signal type chooser; package creation; Market Data ingestion; Ready Check ekranının genel raporu; Backtest Run / Result ayrıntıları.</td>
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
    <td>Trading Signal external work object</td>
    <td>M9 §4.2, §4.4, §5.2, §7; M2 root/revision; CR-01</td>
    <td>`addSignalPackageBox`, `createTradingDataDetailsContent(&quot;signal&quot;)`</td>
    <td>Mainboard, Market Data, Ready Check, Allocation, Trash</td>
    <td>Signal root/revision ve board item ayrıdır. Legacy &quot;Package&quot; metni canonical değildir.</td>
  </tr>
  <tr>
    <td>Source event / import model</td>
    <td>M9 §4.2; M12 external working object checks; M20 data worker</td>
    <td>TXT/CSV file input, data-quality and price/OHLCV controls</td>
    <td>Data worker, object store, Market Data mapping</td>
    <td>`available_time` zorunlu lookahead korumasıdır. Browser parser otorite değildir.</td>
  </tr>
  <tr>
    <td>Identity / roles / lifecycle</td>
    <td>M1 §§5-8; M2; M3; M9 §5.3</td>
    <td>Row arrow, × delete, local backtestReady boolean</td>
    <td>Trash, audit, Mainboard projection</td>
    <td>UI hidden/disabled policy değildir. Soft delete ve Trash yalnız server command ile yürür.</td>
  </tr>
  <tr>
    <td>Run readiness</td>
    <td>M12 readiness schema / external binding checks</td>
    <td>`runBacktestReadyCheck` local source/file/capital checks</td>
    <td>Ready Check, Allocation, Run</td>
    <td>Ready status composition fingerprintine bağlıdır; V18 boolean authority değildir.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kavramsal Sınır

Trading Signal, dış sağlayıcıdan, entegrasyondan veya dosya tabanlı bir upstream kaynaktan alınan yönlü sinyal olaylarını temsil eden External Work Objecttir. Bu sayfa; sinyal kaynağının kimliği, event zamanlarının anlamı, instrument eşlemesi, price/OHLCV politikası, source asset importu, doğrulama bulguları ve immutable revision oluşturma kurallarını yönetir.

Trading Signal, bir Indicator Package değildir ve Strategy Details içindeki entry-indicator bloğunun yerine geçmez. Bir Strategy, ayrı bir karar modeli olarak Trading Signal revisionını referans alabilir; ancak Trading Signal kendisi top-level Mainboard working item olarak `trading_signal` türünde yaşar. Bu yüzden dış sinyalin gerçek event verisi, source provenance ve time-availability kuralı revision içinde açık biçimde sabitlenir.

<table>
  <tr>
    <th>Terim</th>
    <th>Canonical anlam</th>
    <th>Bu sayfadaki uygulama etkisi</th>
  </tr>
  <tr>
    <td>Trading Signal</td>
    <td>Dış sağlayıcıdan gelen yönlü signal eventleri taşıyan external work object. Package değildir.</td>
    <td>Kaynak, import ve mapping bir `trading_signal` root/revisionına yazılır; Mainboard satırı yalnız revisiona referans verir.</td>
  </tr>
  <tr>
    <td>Signal Event</td>
    <td>Belirli instrument için yön, event zamanı ve kullanılabilirlik zamanı taşıyan event kaydı.</td>
    <td>Backtest eventin yalnız `available_time` sonrasında bilinebildiğini varsayar.</td>
  </tr>
  <tr>
    <td>Available Time</td>
    <td>Sinyalin producer/provider tarafından sistemin kullanabileceği hale geldiği an.</td>
    <td>Lookahead biası engeller. `event_time` ile aynı olmak zorunda değildir ve boş bırakılamaz.</td>
  </tr>
  <tr>
    <td>Source Asset</td>
    <td>Yüklenmiş ham TXT/CSV veya başka approved integration çıktısı.</td>
    <td>Immutable object-store kanıtıdır; browser file inputu veya DOM statei değildir.</td>
  </tr>
  <tr>
    <td>Normalized Import Revision</td>
    <td>Parser/mapping/validation sonucunda oluşmuş, enginein tüketebileceği doğrulanmış event seti.</td>
    <td>Ready Check ve Run yalnız exact normalized revisiona referans verir.</td>
  </tr>
  <tr>
    <td>Pinned Revision</td>
    <td>Mainboard itemin kullanacağı exact Trading Signal revisionı.</td>
    <td>&quot;Latest&quot; otomatik çözümü yasaktır; yeni revision mevcut iteme otomatik geçmez.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Lifecycle Boundary Backtest Run ve Backtest Result bu sayfanın ürettiği nesneler değildir. Bu sayfa yalnız valid bir external-object revision ve gerekirse Mainboard item bindingi üretir. Sadece succeeded asynchronous Backtest Run immutable Backtest Result oluşturabilir.</th>
  </tr>
</table>

# 2. Erişim, Görünürlük, Ownership ve Server-Side Policy

<table>
  <tr>
    <th>Actor / rol</th>
    <th>Sayfayı görme</th>
    <th>Create / import</th>
    <th>Edit / save revision</th>
    <th>Use / attach</th>
    <th>Delete / Trash</th>
  </tr>
  <tr>
    <td>Guest / anonymous</td>
    <td>Hayır. Yalnız authentication entry yüzeyi.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Own / explicitly shared / published veya system-allowed Signal detayını görebilir.</td>
    <td>Kendi Trading Signal draftını oluşturur.</td>
    <td>Yalnız own root üzerinde; yeni revision own olur.</td>
    <td>Kullanımı policyye açık revisionı own Mainboarduna attach edebilir.</td>
    <td>Kendi rootunu soft delete edebilir. Trash göremez/restore edemez.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Shared working scope ve erişilebilir kaynakları görür/kullanır.</td>
    <td>Kendi outputunu oluşturur.</td>
    <td>Yalnız own Signal rootunu değiştirir; başkasını mutate edemez.</td>
    <td>Erişilebilir revisionı policyye göre attach/use edebilir.</td>
    <td>Yalnız own root soft delete; Trash yok.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Tüm uygun Signal root/revisionlarını görür/yönetir.</td>
    <td>Oluşturabilir.</td>
    <td>Ownerdan bağımsız revision/provenance kurallarıyla yönetebilir.</td>
    <td>Tüm uygun revisionları attach/use edebilir.</td>
    <td>Soft delete; Trash list/restore/permanent delete yetkisi yalnız Admindedir.</td>
  </tr>
  <tr>
    <td>Agent (system actor)</td>
    <td>Human UI login ile değil, Tool Gateway/API ile erişir. Uygun system working contenti görür/kullanır.</td>
    <td>Kendi output rootunu üretir; source provenance zorunludur.</td>
    <td>Yalnız own outputunu günceller/siler; normal owner policy uygulanır.</td>
    <td>Kendi agent research compositionına explicit attach edebilir.</td>
    <td>Trash yok; restore/purge yok.</td>
  </tr>
</table>

UIde bir satırın görünmesi, Save veya × butonunun enabled olması, callerın yetkili olduğu anlamına gelmez. Her query ve command server tarafında principal, operation, owner, visibility, lifecycle, dependency ve workspace row version bağlamıyla tekrar authorize edilir.

# 3. V18 Arayüz Yerleşimi ve Görünür Bileşen Envanteri

V18de Trading Signal bağımsız bir page route değildir. Mainboard menüsündeki Add Outsource Signal altından Trading Signal seçildiğinde bir Mainboard satırı eklenir. Satırdaki ▼ düğmesi expanded detail panelini açar. Detail paneli iki kolonlu bir düzenle, altta sticky action toolbarıyla görünür.

<table>
  <tr>
    <th>Bölge / bileşen</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Parent navigation</td>
    <td>Mainboard &gt; Add Outsource Signal hover submenu &gt; Trading Signal.</td>
    <td>Bu navigation yalnız UI discoverydir; persisted object commandi değildir.</td>
    <td>V18 menu yapısı korunabilir; selection sonrası oluşan satır Unsaved draft olarak açık etiketlenmelidir.</td>
  </tr>
  <tr>
    <td>Mainboard row</td>
    <td>Varsayılan `TRADING SIGNAL n`; legacy package data varsa `TRADING SIGNAL PACKAGE n, ...`.</td>
    <td>Persisted satır `MainboardWorkingItem(kind=trading_signal, root_id, pinned_revision_id)` projectionıdır.</td>
    <td>&quot;PACKAGE&quot; metni kaldırılır. Row label revision payloadından türetilir; satır metni kimlik değildir.</td>
  </tr>
  <tr>
    <td>Expand / collapse arrow</td>
    <td>▼ / ▲ ile detail panel local DOMda açılıp kapanır.</td>
    <td>Presentation stateidir; revision, composition hash, Ready status veya audit üretmez.</td>
    <td>İstenirse user_ui_preference olarak ayrı saklanır; domain mutation olarak saklanmaz.</td>
  </tr>
  <tr>
    <td>1. TRADING SIGNAL IDENTITY</td>
    <td>Name, Source/Provider, Market, Base TF, Rationale Family, Data Quality, Initial Capital alanları.</td>
    <td>Kimlik/source payloadı ve revision metadata olarak doğrulanır.</td>
    <td>V18 free-text/legacy defaults Productionda canonical selector/schema ile güçlendirilir.</td>
  </tr>
  <tr>
    <td>2. FILE UPLOAD / SOURCE DATA</td>
    <td>Time Zone, Price Source, OHLCV Use ve açıklama.</td>
    <td>Source timestamps, execution price policy ve market-context usage rule revisiona yazılır.</td>
    <td>V18 descriptionu entry/exit record odağındadır; Trading Signal event contractına hizalanır.</td>
  </tr>
  <tr>
    <td>3. BULK TRADING SIGNAL IMPORT</td>
    <td>Tek TXT/CSV file inputu; V18de Trade Log ile aynı entry/exit format boxı.</td>
    <td>Raw asset immutable storagea alınır; data worker parse/map/validate eder; client parser authority değildir.</td>
    <td>Signal event import şeması Trade Log entry/exit şemasından ayrılır.</td>
  </tr>
  <tr>
    <td>Bottom action toolbar</td>
    <td>`Save As Trading Signal Package`, `Clear`, `Export As Package`. [V18 legacy prototype label; Production domain/API type değildir.]</td>
    <td>Create/save revision, discard/reset draft, export source bundle veya approved interchange artifact commands.</td>
    <td>Save/Export etiketleri package dili kullanmayacak şekilde yenilenir.</td>
  </tr>
  <tr>
    <td>ⓘ controls / modal</td>
    <td>Bu detail panelde V18de visible ⓘ button, import progress paneli veya confirmation modal yoktur.</td>
    <td>Validation/report/job/provenance bilgisi serverdan gelir; destructive action için confirmation gerekir.</td>
    <td>Bu belge production usability için minimal ⓘ catalog ve explicit delete confirmation tanımlar.</td>
  </tr>
</table>

## 3.1 V18 Gerçek Varsayılanlar ve Görünen Seçenekler

<table>
  <tr>
    <th>Alan</th>
    <th>V18 default / seçenekler</th>
    <th>Production note</th>
  </tr>
  <tr>
    <td>Trading Signal Name</td>
    <td>`Trading Signal n` veya legacy package name.</td>
    <td>Görünen ad. Save için zorunlu; canonical id değildir.</td>
  </tr>
  <tr>
    <td>Source / Provider</td>
    <td>`External signal provider` veya legacy object owner değeri.</td>
    <td>Boş provider/source olmadan save/ready olmaz.</td>
  </tr>
  <tr>
    <td>Market</td>
    <td>`BTCUSDT` text input.</td>
    <td>Canonical instrument mapping ile doğrulanır; exact string equality yeterli değildir.</td>
  </tr>
  <tr>
    <td>Base TF</td>
    <td>`15m` text input.</td>
    <td>Event-based source için explicit `Event-based` modeli desteklenir; bar-aligned source için supported TF seçilir.</td>
  </tr>
  <tr>
    <td>Rationale Family</td>
    <td>V18de dynamic family listesi; selected `External Signal / Trade Log`. Örnek seçenekler: Reversal / Mean Reversion; Trend / Directional Regime; Breakout / Volatility Expansion; Volatility / Regime; External Signal / Trade Log.</td>
    <td>Global shared-editing exception olan family catalogundan live projection. Root ownership ile karıştırılmaz.</td>
  </tr>
  <tr>
    <td>Data Quality</td>
    <td>Selected `Entry / Exit Records Only`; `Trading Signal + OHLCV`; `Trading Signal + Signal Events`.</td>
    <td>Trading Signal için canonical terminology `Signal Events Only`, `Signal Events + Source OHLCV`, `Signal Events + Approved Market Data Context` olarak hizalanır.</td>
  </tr>
  <tr>
    <td>Initial Capital *</td>
    <td>`10000`; V18de her zaman yıldızlı.</td>
    <td>Allocation disabled ise conditionally required; enabled ise preserved independent fallback value olup run readiness için required değildir.</td>
  </tr>
  <tr>
    <td>Time Zone</td>
    <td>`UTC` free text.</td>
    <td>IANA timezone selector / canonical `UTC` default; event timestamps normalize edilir.</td>
  </tr>
  <tr>
    <td>Price Source</td>
    <td>Selected `Signal Entry / Exit Price`; `OHLCV Close If Needed`; `OHLCV Intrabar If Available`.</td>
    <td>Signal price policy; selected fallback için appropriate approved market data granularity zorunlu olabilir.</td>
  </tr>
  <tr>
    <td>OHLCV Use</td>
    <td>Selected `Use only if supplied and needed`; `Ignore OHLCV context`; `Use for price context and validation`.</td>
    <td>Source-file OHLCV, approved Market Data yerine geçmez. Engine market execution zemini için approved dataset gereksinimini ayrı kontrol eder.</td>
  </tr>
  <tr>
    <td>TXT / CSV</td>
    <td>Tek file, accept `.txt,.csv`; V18 separators comma/semicolon/tab/pipe guidance.</td>
    <td>Tek active source asset revision; upload job/validation report persistence. Same asset repeat upload idempotency / content checksum ile ele alınır.</td>
  </tr>
</table>

# 4. Interaction State Matrix ve State-Layering Contract

<table>
  <tr>
    <th>Bileşen</th>
    <th>Varsayılan / görünür state</th>
    <th>Aktifleşme / geçiş</th>
    <th>Disabled / stale iken payload ve engine etkisi</th>
  </tr>
  <tr>
    <td>Transient Signal Draft</td>
    <td>Type selection sonrası client viewda görünür; başlık `TRADING SIGNAL n`; root/revision/item id yok.</td>
    <td>User/Agent source identity ve event mapping hazırladıkça local draft değişir.</td>
    <td>Ready Check ve Run manifestine girmez. Clear/discard Trash/audit üretmez.</td>
  </tr>
  <tr>
    <td>Persisted Signal Revision</td>
    <td>Save sonrası root + immutable revision oluşur.</td>
    <td>New revision save edilir; current revision pointer güncellenebilir.</td>
    <td>Mainboard eski pinned revisionda kalabilir. Yeni revision pinlenmedikçe composition hash / Ready report değişmez.</td>
  </tr>
  <tr>
    <td>Import status</td>
    <td>V18de yalnız file-selected görünümü vardır.</td>
    <td>Production: `not_started | uploading | queued | claimed | running | succeeded | failed_retryable | failed_final`.</td>
    <td>`succeeded` normalized import revision olmadan save-ready değildir. Browser refresh/job statei etkilemez.</td>
  </tr>
  <tr>
    <td>Mapping validity</td>
    <td>V18de file selection sonrası mapping görünmez.</td>
    <td>Data worker schema/mapping report ve accepted/skipped count üretir.</td>
    <td>Invalid / unresolved fields revisiona/engine planına alınmaz; Ready Check blocker olur.</td>
  </tr>
  <tr>
    <td>Initial Capital</td>
    <td>V18 10000 ve * görünür.</td>
    <td>Allocation mode disabled ise required; enabled ise independent fallback olarak preserved.</td>
    <td>Allocation enabled iken field disabled/read-only gösterilebilir; stored value silinmez, active run capitaline dahil edilmez.</td>
  </tr>
  <tr>
    <td>Price/OHLCV controls</td>
    <td>Her zaman görünür/enabled.</td>
    <td>Data Quality veya price source selected policyyi belirler.</td>
    <td>OHLCV-related selections event payloadında geçersizse clear değil stale-invalid state. Save bloklanır; engine planına girmez.</td>
  </tr>
  <tr>
    <td>Save / Save &amp; Add</td>
    <td>V18de visible/always clickable prototype button.</td>
    <td>Unsaved draft + completed import + valid fields =&gt; Save &amp; Add. Existing object =&gt; Save New Revision, then explicit Use This Revision.</td>
    <td>Pending import, validation errors, access denial, stale workspace veya required field absence =&gt; disabled / server reject. No optimistic success.</td>
  </tr>
  <tr>
    <td>Clear</td>
    <td>V18 all input values resetler, file inputu temizler, `backtestReady=false`.</td>
    <td>Unsaved draftta discard/reset. Persisted objectta Clear unsaved edits only; never deletes saved revision/root.</td>
    <td>No engine impact until a persisted/pinned change occurs.</td>
  </tr>
  <tr>
    <td>Export</td>
    <td>V18 legacy `Export As Package`.</td>
    <td>Export canonical source bundle / normalized event export jobu başlatır; Package yaratmaz.</td>
    <td>No final export when normalized revision yoksa; queued async job or dependency error.</td>
  </tr>
  <tr>
    <td>Row expansion</td>
    <td>Collapsed by default.</td>
    <td>Arrow click / keyboard action.</td>
    <td>Presentation only; no audit/revision/hash/Ready state impact.</td>
  </tr>
  <tr>
    <td>Delete</td>
    <td>V18 × rowu instantly removes and writes demo Trash.</td>
    <td>Persisted root soft-delete preflight + confirmation + audit/outbox.</td>
    <td>Queued/running manifest dependency varsa blocked; historical manifests/results keep pinned provenance.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Implementation Rule State Layering Contract: (1) transient form state, (2) persisted Trading Signal root/current revision, (3) immutable source/import/mapping artifacts, (4) Mainboard item pinned revision ve (5) readiness/run snapshot birbirinin yerine geçmez. Client formu veya V18 `backtestReady` booleanı authoritative state değildir.</th>
  </tr>
</table>

# 5. Field Contract Matrix

Bu bölümde `*`, Productionda request validation, Ready Check ve Agent tool schema tarafından da zorunlu kabul edilen alanı ifade eder. Şartlı zorunlu alanlarda yıldız, sadece ilgili koşul aktifken görünür/etkin olur.

<table>
  <tr>
    <th>Alan / UI tipi</th>
    <th>V18 default / tüm seçenekler</th>
    <th>Zorunluluk ve dependency</th>
    <th>Production payload</th>
    <th>Validation / reset-preserve</th>
  </tr>
  <tr>
    <td>Trading Signal Name *<br/>text input</td>
    <td>`Trading Signal n` / legacy name.</td>
    <td>Always required for persisted revision.</td>
    <td>`identity.display_name`</td>
    <td>Trimmed 1..160 chars; UI label değil identity key. Duplicate allowed only with different root; same owner title conflict warning. Clear resets unsaved draft default, not saved revision.</td>
  </tr>
  <tr>
    <td>Source / Provider *<br/>text input</td>
    <td>`External signal provider` or legacy owner.</td>
    <td>Always required.</td>
    <td>`source.provider_name`, `source.kind`</td>
    <td>1..200 chars; provider identity/provenance. Must not contain secret/token. If changed after save, creates new revision.</td>
  </tr>
  <tr>
    <td>Market / Instrument Scope *<br/>V18 text; Prod selector</td>
    <td>`BTCUSDT`.</td>
    <td>Always required; mapped to canonical instrument.</td>
    <td>`instrument_scope.instrument_id`, `instrument_scope.display_symbol`</td>
    <td>Must resolve through Instrument Registry and be compatible with event rows. Changing market makes imported mapping stale; event rows must be remapped/revalidated.</td>
  </tr>
  <tr>
    <td>Base TF / Event Model *<br/>V18 text; Prod selector</td>
    <td>`15m`.</td>
    <td>Required: choose `event_based`, `same_as_market_dataset`, or supported bar TF. Bar TF required for bar-aligned policy / OHLCV use.</td>
    <td>`event_model.resolution_kind`, `event_model.base_timeframe` nullable only for event_based</td>
    <td>Unsupported TF reject. Changing model retains prior value as visibly stale local draft, excludes it from save until resolved.</td>
  </tr>
  <tr>
    <td>Rationale Family<br/>select</td>
    <td>Dynamic family options; selected `External Signal / Trade Log`.</td>
    <td>Optional classification in canonical Master; Production decision: one primary family required before publish/shared discovery, but private draft save allowed with `unclassified` state.</td>
    <td>`classification.rationale_family_id` nullable for draft</td>
    <td>Referenced family must exist and not be soft-deleted. Family edit may not silently rewrite historical revision snapshot.</td>
  </tr>
  <tr>
    <td>Data Quality *<br/>select</td>
    <td>Entry / Exit Records Only; Trading Signal + OHLCV; Trading Signal + Signal Events.</td>
    <td>Always required. Determines permissible source columns and policy validation.</td>
    <td>`data_quality.mode` enum: `signal_events_only | signal_events_with_source_ohlcv | signal_events_with_market_context`</td>
    <td>Legacy `Entry / Exit Records Only` is not accepted as a new canonical signal mode; migration maps only when event fields can be established.</td>
  </tr>
  <tr>
    <td>Initial Capital *<br/>decimal</td>
    <td>`10000`.</td>
    <td>Required only when run composition allocation mode is disabled.</td>
    <td>`capital.independent_initial_capital` decimal nullable</td>
    <td>Positive finite decimal; currency inherited from workspace/run policy. If allocation enabled, value preserved but excluded from active allocation calculation.</td>
  </tr>
  <tr>
    <td>Time Zone *<br/>V18 text; Prod IANA selector</td>
    <td>`UTC`.</td>
    <td>Always required unless every inbound timestamp includes offset; even then source timezone policy must be explicit.</td>
    <td>`time_policy.source_timezone`, `time_policy.normalization_timezone=&quot;UTC&quot;`</td>
    <td>IANA identifier. Changing timezone invalidates parsed temporal fields and requires reparse/remap.</td>
  </tr>
  <tr>
    <td>Price Source *<br/>select</td>
    <td>Signal Entry / Exit Price; OHLCV Close If Needed; OHLCV Intrabar If Available.</td>
    <td>Always required. Fallback options require compatible approved Market Data at Ready Check.</td>
    <td>`price_policy.source` enum / `fallback_policy`</td>
    <td>Suggested prices optional only when policy has a valid market fallback. Intrabar requires engine/data capability; otherwise blocker.</td>
  </tr>
  <tr>
    <td>OHLCV Use *<br/>select</td>
    <td>Use only if supplied and needed; Ignore OHLCV context; Use for price context and validation.</td>
    <td>Always required. Source OHLCV allowed only if Data Quality mode supports it.</td>
    <td>`ohlcv_policy.use_mode`</td>
    <td>Source OHLCV is contextual evidence; it cannot impersonate approved Market Data execution input. Invalid combination blocks save/ready.</td>
  </tr>
  <tr>
    <td>Trading Signal TXT / CSV *<br/>file input</td>
    <td>One file; `.txt,.csv`; accepted separators comma/semicolon/tab/pipe stated in V18.</td>
    <td>Required for file-source mode. Not required only for a separately approved integration connector that produces an equivalent immutable import revision.</td>
    <td>`source_asset_id`, `import_job_id`, `normalized_import_revision_id`</td>
    <td>Upload file extension/type/size screening; server parser and mapping required. New upload creates new source artifact/revision candidate, not overwrite.</td>
  </tr>
</table>

## 5.1 Trading Signal Event Import Contract

<table>
  <tr>
    <th>Canonical Rule Canonical Rule: Trading Signal revisionı için event seti en az `event_id`, `event_time`, `available_time`, `instrument_id`, `direction`, `signal_type` ve `source_record_id` taşımalıdır. Backtest eventin yalnız available_time sonrasında bilindiğini varsayar.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Incoming logical field</th>
    <th>Minimum requirement</th>
    <th>Canonical normalization / validation</th>
  </tr>
  <tr>
    <td>source_record_id *</td>
    <td>Source/provider içinde tekil event kaydı veya deterministic upstream reference.</td>
    <td>Required. Duplicate provider + source_record_id rows idempotently deduplicated or reported; silent duplicate execution yasaktır.</td>
  </tr>
  <tr>
    <td>event_time *</td>
    <td>Signalın üretildiği/oluştuğu timestamp.</td>
    <td>Timezone policy ile UTC normalize edilir. `event_time` future/unparseable olamaz.</td>
  </tr>
  <tr>
    <td>available_time *</td>
    <td>Entropianın evente erişebileceği ilk timestamp.</td>
    <td>UTC normalize edilir; event_time öncesi olamaz. Missing/ambiguous value `AVAILABLE_TIME_REQUIRED` blocker üretir.</td>
  </tr>
  <tr>
    <td>instrument / symbol *</td>
    <td>Upstream symbol veya canonical instrument key.</td>
    <td>Instrument Registry mappingi ile canonical `instrument_id` oluşturulur. Root market scope ile uyumsuz satırlar reject/skip raporuna girer.</td>
  </tr>
  <tr>
    <td>direction *</td>
    <td>Long veya Short.</td>
    <td>Case/alias mappingi sonrası canonical enum `long|short`. Other values rejected.</td>
  </tr>
  <tr>
    <td>signal_type *</td>
    <td>Örn. entry, exit_hint, scale_hint, close, provider_custom_type.</td>
    <td>Canonical signal type cataloguna map edilir. Unknown value explicit mapping required; `entry` semantics assumed by default değildir.</td>
  </tr>
  <tr>
    <td>suggested_entry_price / suggested_exit_price</td>
    <td>Optional.</td>
    <td>Positive finite number; chosen price policy source price kullanımını istiyorsa corresponding field veya valid fallback gerekli.</td>
  </tr>
  <tr>
    <td>confidence / size hint / metadata</td>
    <td>Optional.</td>
    <td>Typed schema/allowed metadata allowlist ile saklanır. Untrusted raw JSON engine inputuna doğrudan geçmez.</td>
  </tr>
</table>

V18 format boxında görünen `direction, entry_time, entry_price, exit_time, exit_price` şeması Trade Log semantiğidir. Bu schema Trading Signalin canonical inbound schemaası değildir. Production importer, legacy dosyayı ancak event_time/available_time, source_record_id ve signal_type için explicit mapping sağlanırsa Trading Signal olarak kabul edebilir; aksi halde kullanıcıyı Trade Log akışına yönlendirmelidir.

## 5.2 Conditional Requiredness, Dependency ve Reset/Preserve Kuralları

<table>
  <tr>
    <th>Koşul</th>
    <th>UI davranışı</th>
    <th>Backend / Ready Check davranışı</th>
  </tr>
  <tr>
    <td>Allocation disabled</td>
    <td>Initial Capital labelında `*` aktif; field editable.</td>
    <td>Positive independent capital missing ise `INITIAL_CAPITAL_REQUIRED` blocker.</td>
  </tr>
  <tr>
    <td>Allocation enabled</td>
    <td>Initial Capital field visible fakat helper &quot;Used only when Allocation is disabled&quot;; product kararına göre read-only gösterilebilir.</td>
    <td>Stored independent capital preserved; active run için allocation snapshot kullanılır. Missing capital blocker değildir.</td>
  </tr>
  <tr>
    <td>`event_based` selected</td>
    <td>Base TF field `Event-based` / no TF semantiğiyle disabled/read-only.</td>
    <td>`base_timeframe=null` allowed; event availability alignment policy is required.</td>
  </tr>
  <tr>
    <td>OHLCV Use = Ignore</td>
    <td>Price source OHLCV fallback seçenekleri selectionda görünür fakat incompatible ise warning + disabled / not selectable.</td>
    <td>No source OHLCV context consumed. Price fallback still needs explicit valid policy.</td>
  </tr>
  <tr>
    <td>OHLCV Use = Use for price context and validation</td>
    <td>Data Quality must support source OHLCV or approved market context.</td>
    <td>Missing/invalid required OHLCV source/context yields `OHLCV_CONTEXT_REQUIRED` or dataset dependency blocker.</td>
  </tr>
  <tr>
    <td>Price Source = OHLCV Intrabar If Available</td>
    <td>Helper shows data granularity dependency.</td>
    <td>Approved market dataset / engine must support intrabar/tick policy. Otherwise `INTRABAR_DATA_UNAVAILABLE` blocker.</td>
  </tr>
  <tr>
    <td>Market / timezone / event model changed after import</td>
    <td>Imported mapping state shows STALE; old summary retained for user inspection.</td>
    <td>Normalized import revision cannot be reused as valid; reparse/remap job required. Old revision remains historical evidence.</td>
  </tr>
  <tr>
    <td>Source file replaced</td>
    <td>Previous import report remains in prior revision provenance.</td>
    <td>New immutable source asset + new import candidate; no in-place file overwrite.</td>
  </tr>
  <tr>
    <td>Rationale Family edited/deleted elsewhere</td>
    <td>Current selection shows current catalog label; historical revision keeps family snapshot/ref.</td>
    <td>Missing/deleted current target blocks new save if selected; historical run manifest remains readable.</td>
  </tr>
</table>

# 6. Information Content Catalog - Final UI Text

V18 Trading Signal details panelinde visible ⓘ controls yoktur. Handoff standardı, kullanıcıya doğrudan yerleştirilebilir bilgi metni ister. Aşağıdaki help controls Production V1 için Implementation Decision olarak eklenir; input payloadına yazmaz, yetki vermez ve backend validationı bypass etmez.

<table>
  <tr>
    <th>Info key / alan</th>
    <th>Panel başlığı</th>
    <th>UIya yerleştirilecek tam metin</th>
  </tr>
  <tr>
    <td>tradingSignalNameInfo<br/>Trading Signal Name</td>
    <td>Trading Signal Name</td>
    <td>Bu ad, Mainboard ve sonuç görünümlerinde sinyal kaynağını tanımlamak için kullanılır. Teknik kimlik değildir; sistem root_id ve revision_id ile çalışır. Aynı görünen ada sahip iki farklı sinyal kaynağı oluşturulabilir, ancak kaynak/provider bilgisi ve revision geçmişi ayrı kalır.</td>
  </tr>
  <tr>
    <td>tradingSignalProviderInfo<br/>Source / Provider</td>
    <td>Source / Provider</td>
    <td>Sinyalin nereden geldiğini yazın: bir provider adı, entegrasyon adı veya doğrulanabilir dosya kaynağı. API anahtarı, şifre, token veya gizli bağlantı bilgisi yazmayın. Bu alan source provenance içinde saklanır ve geçmiş bir runın hangi upstream kaynağa dayandığını açıklar.</td>
  </tr>
  <tr>
    <td>tradingSignalTimingInfo<br/>Event Time and Available Time</td>
    <td>Signal timing and availability</td>
    <td>Event Time, sinyalin üretildiği andır. Available Time, sistemin bu sinyali gerçekte kullanabildiği ilk andır. Backtest, sinyali yalnız Available Time sonrasında işleyebilir. Available Time bilinmiyorsa sonuç lookahead bias taşıyabilir; bu nedenle import doğrulaması sinyali Ready duruma getirmez.</td>
  </tr>
  <tr>
    <td>tradingSignalInstrumentInfo<br/>Market / Instrument Scope</td>
    <td>Market / Instrument Scope</td>
    <td>Market alanı yalnız bir metin etiketi değildir. Kaynak satırlarındaki symbol/instrument değerleri Entropianın canonical instrument kaydıyla eşleştirilir. Eşleşmeyen satırlar kabul edilmez veya açık skip nedeni ile raporlanır.</td>
  </tr>
  <tr>
    <td>tradingSignalEventModelInfo<br/>Base TF / Event Model</td>
    <td>Base timeframe or event model</td>
    <td>Bar-temelli bir sağlayıcı için sinyalin hangi bar çözünürlüğünde üretildiğini seçin. Olay-temelli kaynaklarda Event-based seçeneğini kullanın. Event-based sinyallerde zaman hizalaması event ve available time üzerinden yapılır; sistem bunları otomatik olarak 15m bara indirgemez.</td>
  </tr>
  <tr>
    <td>tradingSignalQualityInfo<br/>Data Quality</td>
    <td>Data Quality</td>
    <td>Signal Events Only yalnız yönlü eventleri içerir. Signal Events + Source OHLCV, sağlayıcının gönderdiği bağlamsal OHLCV sütunlarını da taşır. Signal Events + Approved Market Data Context, fiyat doğrulaması ve execution için Entropianın onaylı Market Data revisionını kullanır. Source-file OHLCV, onaylı Market Data yerine geçmez.</td>
  </tr>
  <tr>
    <td>tradingSignalCapitalInfo<br/>Initial Capital</td>
    <td>Initial Capital</td>
    <td>Equity Allocation kapalıysa Trading Signal bağımsız sermaye ile değerlendirilir ve bu alan zorunludur. Equity Allocation açıksa shared pool ve allocation planı kullanılır; bu değer saklanır ancak o runın aktif sermaye hesabına girmez.</td>
  </tr>
  <tr>
    <td>tradingSignalPriceInfo<br/>Price Source</td>
    <td>Price Source</td>
    <td>Suggested signal price, providerın event içinde verdiği fiyatı kullanır. OHLCV Close If Needed yalnız uygun onaylı market verisi varsa fallback kullanır. OHLCV Intrabar If Available daha ayrıntılı fiyat verisi ve engine capability gerektirir. Seçim, signal eventin yönünü değil, testte fiyatın hangi politikayla yorumlanacağını belirler.</td>
  </tr>
  <tr>
    <td>tradingSignalOhlcvInfo<br/>OHLCV Use</td>
    <td>OHLCV Use</td>
    <td>Use only if supplied and needed, source OHLCVyi yalnız seçilen policy gerektirirse kullanır. Ignore OHLCV context, kaynak OHLCV sütunlarını engine bağlamından çıkarır. Use for price context and validation, OHLCVyi fiyat/mantık doğrulaması için kullanır; uygun veri yoksa save veya Ready Check bloklanır.</td>
  </tr>
  <tr>
    <td>tradingSignalImportInfo<br/>TXT / CSV File</td>
    <td>Trading Signal import file</td>
    <td>Dosya yalnız source eventleri içerir. Sistem ham dosyayı tarayıcıda authoritative olarak değerlendirmez; immutable source asset oluşturur ve arka plan import işi ile parse/map/validate eder. Sinyal eventleri için source record id, event time, available time, instrument, direction ve signal type bilgisi çözümlenmelidir.</td>
  </tr>
</table>

## 6.1 Placeholder, Helper, Warning, Toast, Empty-State ve Error Text Catalog

<table>
  <tr>
    <th>Tür</th>
    <th>Koşul / konum</th>
    <th>Nihai UI metni</th>
  </tr>
  <tr>
    <td>Placeholder</td>
    <td>Trading Signal Name</td>
    <td>Example: Copy Trading Signal Source A</td>
  </tr>
  <tr>
    <td>Placeholder</td>
    <td>Source / Provider</td>
    <td>Example: Provider name, integration, or verified file source</td>
  </tr>
  <tr>
    <td>Helper</td>
    <td>Initial Capital, Allocation enabled</td>
    <td>This value is preserved for independent mode. The active run uses the Portfolio Allocation Plan instead.</td>
  </tr>
  <tr>
    <td>Helper</td>
    <td>File input before selection</td>
    <td>Upload one TXT or CSV file containing Trading Signal events. A server-side import report will be created after upload.</td>
  </tr>
  <tr>
    <td>Helper</td>
    <td>Event-based model</td>
    <td>Event-based signals are evaluated from event_time and available_time; no base bar timeframe is applied.</td>
  </tr>
  <tr>
    <td>Warning</td>
    <td>Legacy entry/exit schema detected</td>
    <td>This file looks like a Trade Log because it contains entry and exit records but does not provide a valid signal-event mapping. Add event_time, available_time, source_record_id and signal_type, or import it as a Trade Log.</td>
  </tr>
  <tr>
    <td>Warning</td>
    <td>Source file OHLCV used</td>
    <td>Source-file OHLCV is contextual evidence only. It does not replace an Approved Market Data revision for execution or fill simulation.</td>
  </tr>
  <tr>
    <td>Toast success</td>
    <td>Save &amp; Add succeeds</td>
    <td>Trading Signal saved as revision {revision_no} and added to Mainboard.</td>
  </tr>
  <tr>
    <td>Toast success</td>
    <td>Save New Revision succeeds but not pinned</td>
    <td>Trading Signal revision {revision_no} was saved. Mainboard is still using revision {pinned_revision_no}. Select &quot;Use This Revision on Mainboard&quot; to update the active composition.</td>
  </tr>
  <tr>
    <td>Toast success</td>
    <td>Import job accepted</td>
    <td>Trading Signal file received. Import job {job_id} is running in the background.</td>
  </tr>
  <tr>
    <td>Toast error</td>
    <td>Required file missing</td>
    <td>Upload a TXT or CSV signal-event file before saving this file-based Trading Signal.</td>
  </tr>
  <tr>
    <td>Toast error</td>
    <td>Ready dependency</td>
    <td>Trading Signal cannot be used for a backtest until source identity, normalized import revision, event mapping, instrument, timezone, availability rule and capital/allocation binding are valid.</td>
  </tr>
  <tr>
    <td>Empty state</td>
    <td>No parsed events</td>
    <td>No accepted signal events are available yet. Upload a source file or fix the failed import mapping.</td>
  </tr>
  <tr>
    <td>Delete confirmation</td>
    <td>Persisted root</td>
    <td>Delete Trading Signal &quot;{display_name}&quot;? It will be removed from the active Mainboard and moved to Trash. Historical completed runs keep their pinned snapshot. This cannot delete a signal used by a queued or running run.</td>
  </tr>
  <tr>
    <td>Conflict</td>
    <td>Stale revision/workspace</td>
    <td>This Trading Signal or Mainboard changed elsewhere. Refresh the latest server state, review the differences, then save or pin again.</td>
  </tr>
</table>

# 7. Button, Command ve State Contract

<table>
  <tr>
    <th>Visible action</th>
    <th>V18 behavior</th>
    <th>Production command / precondition</th>
    <th>Loading, success, error, audit</th>
  </tr>
  <tr>
    <td>Add Outsource Signal &gt; Trading Signal</td>
    <td>Immediately appends a client DOM row and marks local backtestReady false.</td>
    <td>`POST /external-work-object-drafts` with `kind=trading_signal` may create only a transient client draft or server draft session; no persisted root required until Save.</td>
    <td>No audit for pure local discard. If server draft session exists, it is non-runnable and expires per draft policy.</td>
  </tr>
  <tr>
    <td>▼ / ▲</td>
    <td>Toggles detail panel.</td>
    <td>No domain command. Optional `PATCH /user-ui-preferences` only.</td>
    <td>Instant local UI; no hash/revision/Ready/audit side effect.</td>
  </tr>
  <tr>
    <td>Upload TXT / CSV</td>
    <td>V18 file selection marks `dataFileLoaded=true`.</td>
    <td>`POST /trading-signals/imports` or source-upload init command; upload immutable asset; enqueue data-worker import.</td>
    <td>Button/input shows Uploading then Import queued. Response returns stable job_id. Failure retains selected metadata and actionable report; retry creates/reuses controlled job.</td>
  </tr>
  <tr>
    <td>Save As Trading Signal Package<br/>(legacy)</td>
    <td>Prototype button has no production persistence.</td>
    <td>Unsaved: `CreateTradingSignalAndAttach`; persisted: `CreateTradingSignalRevision`. Neither creates Package.</td>
    <td>Validates fields/import; creates immutable revision with content hash. Save success rehydrates canonical state. Error returns structured issues; audit `work_object_revision_created`.</td>
  </tr>
  <tr>
    <td>Use This Revision on Mainboard<br/>(Production control)</td>
    <td>Not visible in V18.</td>
    <td>`PATCH /mainboard-items/{id}/pinned-revision` with `expected_row_version` and workspace expected fingerprint.</td>
    <td>Updates pin atomically; recomputes composition hash; marks affected readiness reports stale; audit `mainboard_item_revision_changed`.</td>
  </tr>
  <tr>
    <td>Clear</td>
    <td>Resets all inputs; name becomes Trading Signal; file clears; local ready false.</td>
    <td>Unsaved: `DiscardTransientTradingSignalDraft`; persisted: `ResetUnsavedEditorChanges`.</td>
    <td>No root delete. Confirm only if local unsaved changes exist. No audit for local reset; UI returns to canonical persisted revision or blank transient default.</td>
  </tr>
  <tr>
    <td>Export As Package<br/>(legacy)</td>
    <td>Visible without implementation.</td>
    <td>`RequestTradingSignalExport` / source bundle export; output is artifact, not Package.</td>
    <td>Async export job. Requires accessible normalized revision. Success provides artifact reference; failure reports job diagnostic. Audit/export event recorded.</td>
  </tr>
  <tr>
    <td>× Delete Trading Signal</td>
    <td>V18 instantly removes DOM row and demo Trash entry.</td>
    <td>`SoftDeleteTradingSignalRoot` with root_id, expected lifecycle/version and idempotency key.</td>
    <td>Confirmation first. Server preflight checks active Run/Queue dependency. Success removes projection and creates Trash/audit/outbox. Blocked state leaves row visible.</td>
  </tr>
</table>

## 7.1 Conceptual Command Payloads

<table>
  <tr>
    <th>CreateTradingSignalRevision<br/>{ root_id?, expected_head_revision_id?, identity, source, instrument_scope, event_model,<br/>  classification, data_quality, time_policy, price_policy, ohlcv_policy, capital,<br/>  source_asset_id, normalized_import_revision_id, idempotency_key }</th>
  </tr>
</table>

<table>
  <tr>
    <th>PinTradingSignalRevisionToMainboard<br/>{ workspace_id, item_id, new_pinned_revision_id, expected_item_row_version,<br/>  expected_workspace_fingerprint, idempotency_key }</th>
  </tr>
</table>

<table>
  <tr>
    <th>RequestTradingSignalImport<br/>{ draft_or_root_id, source_asset_id, mapping_profile_id?, expected_schema_version,<br/>  source_timezone, instrument_mapping_policy, idempotency_key }</th>
  </tr>
</table>

Endpoint shape is an Implementation Decision aligned to Master Modül 19; the invariant is not the URL string but typed request validation, actor context, idempotency, optimistic concurrency, immutable revision creation, durable job state and canonical response rehydration.

# 8. Kullanıcı Akışları

## 8.1 Başarılı yeni Trading Signal oluşturma ve Mainboarda ekleme

- Authenticated User Mainboard menüsünden Add Outsource Signal > Trading Signal seçer. UI transient `Unsaved` detail panelini açar; root/revision/item henüz yoktur.

- User Signal Name, Source / Provider, canonical Market/Instrument Scope, Event Model, Data Quality, Time Zone, Price Source ve OHLCV Use alanlarını tamamlar. Allocation kapalıysa Initial Capital da girilir.

- User TXT/CSV file seçer. Upload command immutable source asset ve job id döndürür; data worker parse/map/validate eder. UI job progress/report projectionını gösterir.

- Import succeeded olduğunda accepted/skipped rows, mapping summary, instrument/timezone/event availability validationı görünür. Required event mapping eksikse Save disabled veya server validation error olur.

- User `Save & Add to Mainboard` seçer. Server policy, source root/revision, import revision ve workspace concurrency bilgisini doğrular; atomic olarak Trading Signal root/revision ve `MainboardWorkingItem(kind=trading_signal)` oluşturur/pinler.

- Response canonical root, revision, item, composition hash ve Ready status `STALE/NOT_READY` bilgisini döndürür. UI local draftı bu server projectionıyla replace eder; success toast gösterir.

## 8.2 Mevcut Signal üzerinde yeni revision oluşturma ve explicit pin

- User persisted Trading Signal detailini açar. Mainboard iteminin currently pinned revisionı ve newer revision availability bilgisi gösterilir.

- User provider/timezone/price policy veya source file değiştirir. Bu mevcut immutable revisionı değiştirmez; new revision candidate olur.

- Save New Revision, exact source/mapping artifacts ile immutable revision oluşturur. Mainboard item otomatik olarak lateste ilerlemez.

- UI `Revision {new} saved; Mainboard uses revision {old}` mesajını gösterir. User yetkiliyse `Use This Revision on Mainboard` komutu ile explicit pin yapar.

- Pin başarıyla değişirse workspace fingerprint değişir ve ilgili Ready Report stale olur. User yeni Ready Check çalıştırmadan Run yapamaz.

## 8.3 Validation/dependency recovery

- Missing provider: UI Source / Provider alanını vurgular; server `SOURCE_PROVIDER_REQUIRED` döndürür. User source identity girip aynı draft/revision candidate üzerinden tekrar save eder.

- Missing available time: Import report `AVAILABLE_TIME_REQUIRED` hatası üretir. User CSV mappinge availability field ekler veya provider policy üzerinden deterministic availability rule tanımlar; new import revision oluşur.

- Instrument mismatch: Row-level report unmatched symbolsü gösterir. User mapping seçer veya source fileı düzeltir. Accepted/skipped oranı policy eşiğinin altındaysa Ready Check blocker devam eder.

- Intrabar source without data: Price Source seçimini close/suggested price policyye değiştirir ya da compatible approved market data/revision seçer. Existing signal revision silently altered edilmez.

- Allocation toggle changed: Initial Capital field value preserved edilir; Allocation kapatılırsa kullanıcıya it must be filled/positive warning gösterilir. Ready report new composition hash için tekrar çalışır.

## 8.4 Permission, stale concurrency ve delete recovery

- Access denied: UI action disabled olabilir fakat server `ACCESS_DENIED` / `OWNER_REQUIRED` döndürür. User owner/admindan edit izni veya own derived object oluşturma yolunu izler.

- Stale revision/workspace: `CONCURRENCY_CONFLICT` / `STALE_WORKSPACE` responseu UIı canonical latest state ile refresh/compare ekranına yönlendirir. User explicit merge/new revision/pin işlemini tekrarlar; silent overwrite yoktur.

- Delete blocked: Queued/running run manifest dependency varsa `ACTIVE_RUN_DEPENDENCY` döner. User active run lifecycleını uygun sayfadan cancel/complete eder veya delete denemesinden vazgeçer.

- Soft deleted: Root active list/pickersdan kalkar ve Admin Trash projectionına gider. Restore yalnız Admin komutudur; restore historical completed resultı değiştirmez.

# 9. Production Backend ve Domain Davranışı

## 9.1 Root, Revision, Mainboard Item ve Artifact modeli

<table>
  <tr>
    <th>Entity</th>
    <th>Sorumluluk</th>
    <th>Önemli alanlar / invariants</th>
  </tr>
  <tr>
    <td>TradingSignalRoot</td>
    <td>Trading Signalin kalıcı kök kimliği ve ownership/lifecycle bilgisi.</td>
    <td>`object_kind=trading_signal`; `owner_actor_id`; `current_revision_id`; `lifecycle_state`; deleted metadata. PackageRoot değildir.</td>
  </tr>
  <tr>
    <td>WorkObjectRevision</td>
    <td>Immutable source/mapping/policy/event-set tanımı.</td>
    <td>`revision_no`, `payload_json`, `source_provenance_json`, `validation_summary_json`, `content_hash`, `supersedes_revision_id`. Update mutasyon değil yeni revisiondır.</td>
  </tr>
  <tr>
    <td>Source Asset</td>
    <td>Uploaded raw file kanıtı.</td>
    <td>Object storage URI/checksum/content type/upload actor. Raw file overwrite edilmez; purge/retention policy dışında silinmez.</td>
  </tr>
  <tr>
    <td>Import Job</td>
    <td>Durable server-side parse/map/validate işi.</td>
    <td>`job_id`, generic job state, input asset refs, worker attempt, report artifact refs, correlation_id. Browser lifetime bağımsız.</td>
  </tr>
  <tr>
    <td>Normalized Signal Event Revision</td>
    <td>Engine-consumable normalized event set.</td>
    <td>Schema/mapping revision, accepted/skipped rows, event availability/timezone/instrument mapping evidence. Exact ID pinned to Signal revision.</td>
  </tr>
  <tr>
    <td>MainboardWorkingItem</td>
    <td>Trading Signal revisionını active compositiona bağlayan satır.</td>
    <td>`item_kind=trading_signal`, `work_object_root_id`, `pinned_revision_id`, `position_index`, `is_enabled`, `row_version`. Payload duplicate etmez.</td>
  </tr>
  <tr>
    <td>Composition Snapshot</td>
    <td>Ready Check/Run için immutable board manifest.</td>
    <td>Ordered enabled items, pinned revision IDs, capital mode/allocation snapshot, fingerprint/hash. Live DOMdan türetilmez.</td>
  </tr>
</table>

## 9.2 Revision Payload - Implementation Decision

Master root/revision ve minimum event contractını kilitler; exact payload field namingini sayfa seviyesinde kesinleştirmek gerekir. Aşağıdaki JSON biçimi Production V1 için Implementation Decisiondır. Field names typed API/OpenAPI schema ile aynı tutulmalıdır.

<table>
  <tr>
    <th>{<br/>  &quot;kind&quot;: &quot;trading_signal&quot;,<br/>  &quot;identity&quot;: {&quot;display_name&quot;: &quot;Copy Trading Signal Source A&quot;},<br/>  &quot;source&quot;: {&quot;provider_name&quot;: &quot;Provider X&quot;, &quot;source_kind&quot;: &quot;file&quot;},<br/>  &quot;instrument_scope&quot;: {&quot;instrument_id&quot;: &quot;inst_btcusdt_perp&quot;, &quot;display_symbol&quot;: &quot;BTCUSDT&quot;},<br/>  &quot;event_model&quot;: {&quot;resolution_kind&quot;: &quot;event_based&quot;, &quot;base_timeframe&quot;: null},<br/>  &quot;classification&quot;: {&quot;rationale_family_id&quot;: &quot;rf_external_signal_trade_log&quot;},<br/>  &quot;data_quality&quot;: {&quot;mode&quot;: &quot;signal_events_only&quot;},<br/>  &quot;time_policy&quot;: {&quot;source_timezone&quot;: &quot;UTC&quot;, &quot;normalization_timezone&quot;: &quot;UTC&quot;, &quot;availability_rule&quot;: &quot;row_available_time&quot;},<br/>  &quot;price_policy&quot;: {&quot;source&quot;: &quot;suggested_signal_price&quot;, &quot;fallback&quot;: &quot;approved_market_close_if_needed&quot;},<br/>  &quot;ohlcv_policy&quot;: {&quot;use_mode&quot;: &quot;use_if_supplied_and_needed&quot;},<br/>  &quot;capital&quot;: {&quot;independent_initial_capital&quot;: &quot;10000&quot;},<br/>  &quot;import_binding&quot;: {&quot;source_asset_id&quot;: &quot;asset_...&quot;, &quot;normalized_event_revision_id&quot;: &quot;sigrm_...&quot;, &quot;mapping_revision_id&quot;: &quot;map_...&quot;}<br/>}</th>
  </tr>
</table>

## 9.3 Command/query/job/event chain

<table>
  <tr>
    <th>Operation</th>
    <th>Application / domain behavior</th>
    <th>Worker / projection / audit behavior</th>
  </tr>
  <tr>
    <td>Create transient draft</td>
    <td>Client-only draft or short-lived server draft session. No runnable root/revision.</td>
    <td>No mandatory audit. Any server draft expiry is not a root delete.</td>
  </tr>
  <tr>
    <td>Upload source</td>
    <td>Authorize create/import; reserve source asset; issue upload reference; checksum metadata.</td>
    <td>Data worker validates file safety/type, parses/mapping/schema, emits normalized events and reports.</td>
  </tr>
  <tr>
    <td>Import validation</td>
    <td>Resolve provider, instrument, timezone, availability/time policy, price/OHLCV policy and event schema.</td>
    <td>Persist immutable validation evidence, accepted/skipped row report and structured issues.</td>
  </tr>
  <tr>
    <td>Save revision</td>
    <td>Authorize owner policy; resolve exact immutable import artifact; validate payload; write new revision transactionally.</td>
    <td>Append `work_object_revision_created` audit/event with safe summary and correlation_id.</td>
  </tr>
  <tr>
    <td>Attach/pin</td>
    <td>Authorize workspace use; verify root/revision type; optimistic concurrency; change pinned revision.</td>
    <td>Recompute composition hash; stale matching readiness reports; outbox `mainboard_item_revision_changed`.</td>
  </tr>
  <tr>
    <td>Delete</td>
    <td>Authorize delete; preflight run/queue dependencies; soft delete root and board item projection atomically.</td>
    <td>Trash entry + audit + outbox. Search/tool cache projections update asynchronously; root delete remains committed even if consumer retries.</td>
  </tr>
  <tr>
    <td>Export</td>
    <td>Authorize access; resolve normalized revision.</td>
    <td>Async export worker creates artifact. Does not create Package or mutate Signal revision.</td>
  </tr>
</table>

## 9.4 Ready Check / Run boundary specific to Trading Signal

Trading Signal sayfası Ready Check ekranını tanımlamaz; fakat Trading Signalin runa taşınabilmesi için Ready Checkin aşağıdaki external-object bağlamını doğrulaması zorunludur: source/provider identity, normalized import revision, schema/mapping revision, event mapping, instrument mapping, timezone, event availability rule, price policy ve independent capital veya allocation binding.

Ready Check reportu boolean değildir; exact composition fingerprinti için üretilen immutable/traceable reporttur. Signal revision kaydedilmesi ancak existing Mainboard item explicit olarak new revisiona pinlenirse fingerprinti değiştirir. Sadece editorün açık olması, rowun expand edilmesi veya transient form value değiştirilmesi readiness authority değildir.

# 10. Agent Tool/API Eşdeğeri ve Sürekli Çalışma Sınırı

Agent için Mainboard menusunu açmak veya HTMLdeki file inputa basmak gerçek yetenek değildir. Agent; Tool Gateway/API/domain services üzerinden aynı source discovery, source asset ingest, event mapping validation, Trading Signal revision creation, explicit composition attach/pin ve export commandlerini kullanır. Agentin sürekli araştırma döngüsü browser, user session veya Lab Assistant mesajına bağlı değildir.

<table>
  <tr>
    <th>Agent intent</th>
    <th>UI eşdeğeri</th>
    <th>Tool / domain capability</th>
    <th>Provenance / ownership</th>
  </tr>
  <tr>
    <td>trading_signal.create</td>
    <td>Add Outsource Signal &gt; Trading Signal</td>
    <td>CreateTransientExternalObjectDraft(kind=trading_signal) veya direct structured draft command</td>
    <td>New persisted root owner=Agent; parent task/checkpoint/source refs recorded.</td>
  </tr>
  <tr>
    <td>trading_signal.import_events</td>
    <td>File upload</td>
    <td>UploadSourceAsset + RequestTradingSignalImport</td>
    <td>Raw asset/import job/normalized revision correlation_id and agent task id carry.</td>
  </tr>
  <tr>
    <td>trading_signal.validate</td>
    <td>Wait/import report + Save</td>
    <td>ValidateTradingSignalDraft / GetImportReport</td>
    <td>Agent receives structured blockers/warnings; does not bypass availability/data policy.</td>
  </tr>
  <tr>
    <td>trading_signal.save_revision</td>
    <td>Save button</td>
    <td>CreateTradingSignalRevision</td>
    <td>Immutable revision; agent may update only own output except explicit policy exception.</td>
  </tr>
  <tr>
    <td>trading_signal.attach</td>
    <td>Use This Revision on Mainboard</td>
    <td>AttachOrPinTradingSignalRevision(workspace_id, revision_id)</td>
    <td>Agent attaches to its own agent research workspace, not automatically to a human Default Mainboard.</td>
  </tr>
  <tr>
    <td>trading_signal.delete</td>
    <td>×</td>
    <td>SoftDeleteTradingSignalRoot</td>
    <td>Agent can delete own output only; no Trash list/restore/purge capability.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Agent Boundary Agent capability parity does not mean Agent can bypass external source trust, approved data policies, lifecycle checks or server-side authorization. It means the same actual domain command exists without browser emulation.</th>
  </tr>
</table>

# 11. Validation, Error ve Recovery Contract

<table>
  <tr>
    <th>Kategori</th>
    <th>Blocker / warning örneği</th>
    <th>Server error code / UI recovery</th>
  </tr>
  <tr>
    <td>Field validation</td>
    <td>Name/provider empty; invalid decimal; malformed timezone; unsupported file extension.</td>
    <td>`VALIDATION_FAILED`, `SOURCE_PROVIDER_REQUIRED`, `TIMEZONE_INVALID`, `FILE_TYPE_NOT_ALLOWED`. Highlight exact field; preserve valid user input; retry after correction.</td>
  </tr>
  <tr>
    <td>Event schema</td>
    <td>Missing source_record_id/event_time/available_time/direction/signal_type; invalid direction; no accepted rows.</td>
    <td>`SIGNAL_EVENT_MAPPING_REQUIRED`, `AVAILABLE_TIME_REQUIRED`, `INVALID_SIGNAL_DIRECTION`, `NO_ACCEPTED_SIGNAL_EVENTS`. Show mapping/report and require new import revision.</td>
  </tr>
  <tr>
    <td>Cross-field</td>
    <td>Event-based + fixed TF contradiction; OHLCV ignore + intrabar policy; allocation disabled + no capital.</td>
    <td>`EVENT_MODEL_POLICY_CONFLICT`, `OHLCV_POLICY_CONFLICT`, `INITIAL_CAPITAL_REQUIRED`. Do not silently coerce choices.</td>
  </tr>
  <tr>
    <td>Dependency</td>
    <td>Instrument cannot map; price fallback lacks compatible approved Market Data; import revision not succeeded.</td>
    <td>`INSTRUMENT_MAPPING_UNRESOLVED`, `MARKET_DATA_DEPENDENCY_BLOCKED`, `IMPORT_NOT_READY`. Provide exact missing dependency/remediation.</td>
  </tr>
  <tr>
    <td>Authorization</td>
    <td>Caller edits/deletes other owner object or private source.</td>
    <td>`ACCESS_DENIED`, `OWNER_REQUIRED`. Do not reveal inaccessible source details; allow own copy only if policy permits.</td>
  </tr>
  <tr>
    <td>Lifecycle</td>
    <td>Root soft-deleted, import asset purged, revision incompatible/deprecated, active run dependency on delete.</td>
    <td>`LIFECYCLE_BLOCKED`, `DEPENDENCY_BLOCKED`, `ACTIVE_RUN_DEPENDENCY`. Explain restore/admin or run lifecycle route.</td>
  </tr>
  <tr>
    <td>Concurrency</td>
    <td>expected_head_revision_id / Mainboard row version mismatch.</td>
    <td>`CONCURRENCY_CONFLICT`, `STALE_WORKSPACE`. Refresh canonical state, compare, create new revision or repin; no lost update.</td>
  </tr>
  <tr>
    <td>Async job failure</td>
    <td>Worker parse/validation failure, storage unavailable, retry exhausted.</td>
    <td>`JOB_FAILED` plus job diagnostics. Retry uses job/config/source asset reference; no fake parsed result or backtest readiness.</td>
  </tr>
</table>

## 11.1 Error response minimum shape - Implementation Decision

<table>
  <tr>
    <th>{ &quot;code&quot;: &quot;SIGNAL_EVENT_MAPPING_REQUIRED&quot;, &quot;category&quot;: &quot;dependency_validation&quot;,<br/>  &quot;retryable&quot;: false, &quot;scope_type&quot;: &quot;TradingSignal&quot;, &quot;scope_id&quot;: &quot;draft_or_root_id&quot;,<br/>  &quot;field_path&quot;: &quot;import_binding.mapping.available_time&quot;,<br/>  &quot;message&quot;: &quot;Map an available time for every accepted signal event.&quot;,<br/>  &quot;remediation&quot;: &quot;Add the source column or choose an explicit provider availability rule, then rerun import validation.&quot;,<br/>  &quot;correlation_id&quot;: &quot;corr_...&quot; }</th>
  </tr>
</table>

# 12. Lifecycle, Versioning, Audit ve Trash

<table>
  <tr>
    <th>Olay</th>
    <th>Lifecycle / data behavior</th>
    <th>Audit / historical integrity</th>
  </tr>
  <tr>
    <td>Unsaved draft discarded</td>
    <td>No root/revision/item exists; local state removed.</td>
    <td>No Trash entry or domain audit required.</td>
  </tr>
  <tr>
    <td>Source file upload</td>
    <td>Raw source asset immutable; upload is evidence, not current revision overwrite.</td>
    <td>Upload/import job records carry actor/correlation/source metadata; raw content not copied into audit payload.</td>
  </tr>
  <tr>
    <td>New revision saved</td>
    <td>Existing revision immutable; `revision_no+1`, content hash, supersedes ref.</td>
    <td>`work_object_revision_created`; safe summary + root/revision identifiers. Previous completed run unchanged.</td>
  </tr>
  <tr>
    <td>New revision pinned</td>
    <td>Mainboard item pointer changes with expected row version.</td>
    <td>`mainboard_item_revision_changed`; composition hash changes; Ready report stale. Old manifests retain prior revision.</td>
  </tr>
  <tr>
    <td>Root soft delete</td>
    <td>Root lifecycle=soft_deleted; active Mainboard projection removed; new selectors exclude it.</td>
    <td>Trash entry and `work_object_soft_deleted`; historical run/result keeps pinned display/provenance snapshot.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>Admin-only; lifecycle restored atomically if preflight passes.</td>
    <td>`trash.restore.completed`. Restore does not rerun historical run, mutate result or change prior manifest.</td>
  </tr>
  <tr>
    <td>Permanent delete / purge</td>
    <td>Admin-only second confirmation; asynchronous retention/dependency preflight. May remove eligible payload/assets but leaves tombstone/minimum audit.</td>
    <td>`trash.purge.completed` or `trash.purge.failed`. Failure leaves root soft-deleted; restore only while not purged.</td>
  </tr>
</table>

# 13. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Notes

<table>
  <tr>
    <th>ID</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>IA-04-01</td>
    <td>Trading Signal row and details are created client-side immediately; `backtestReady` boolean becomes false.</td>
    <td>Only persisted root/revision/item is eligible for composition snapshot, Ready Check and Run.</td>
    <td>Render a transient `Unsaved` state after selection. Never treat DOM row/file selection as runnable object.</td>
  </tr>
  <tr>
    <td>IA-04-02</td>
    <td>Labels say `TRADING SIGNAL PACKAGE` and `Save As Trading Signal Package`; Package Library also has legacy Trading Signal Packages.</td>
    <td>CR-01 limits PackageKind to strategy, indicator, condition, embedded_system. Trading Signal is external working object.</td>
    <td>Replace all production labels/routes/enum/db fields with Trading Signal / `trading_signal`; do not migrate legacy data into PackageKind.</td>
  </tr>
  <tr>
    <td>IA-04-03</td>
    <td>Trading Signal shares a Trade Log-style required columns box: direction, entry_time, entry_price, exit_time, exit_price.</td>
    <td>Trading Signal needs event_id, event_time, available_time, instrument, direction, signal_type, source_record_id at minimum.</td>
    <td>Create a dedicated event-import mapping UX. Legacy entry/exit file is accepted only through explicit conversion mapping or Trade Log flow.</td>
  </tr>
  <tr>
    <td>IA-04-04</td>
    <td>Market/Base TF/Time Zone are free-text inputs and `UTC`/`15m` are defaults.</td>
    <td>Instrument registry mapping, IANA timezone validation and explicit event model are required.</td>
    <td>Use selectors with controlled custom mapping where needed; preserve V18 defaults only as initial convenience, not authority.</td>
  </tr>
  <tr>
    <td>IA-04-05</td>
    <td>Data Quality default is `Entry / Exit Records Only`.</td>
    <td>Trading Signal is event data, not completed trade ledger.</td>
    <td>Rename production modes to signal-event terminology and map legacy selection only when semantically valid.</td>
  </tr>
  <tr>
    <td>IA-04-06</td>
    <td>Clear removes file and resets fields, while × immediately moves row in demo Trash.</td>
    <td>Clear affects transient/unsaved editor state. Delete persisted root requires confirmation, preflight, soft delete, Trash/audit/outbox.</td>
    <td>Keep actions distinct. Clear must never delete a persisted revision/root.</td>
  </tr>
  <tr>
    <td>IA-04-07</td>
    <td>No progress, mapping report or error UI is visible.</td>
    <td>Import is durable async job with report/evidence; browser refresh does not cancel it.</td>
    <td>Add job status/report panel. Do not fabricate client-side parse success.</td>
  </tr>
  <tr>
    <td>IA-04-08</td>
    <td>Export As Package is visible.</td>
    <td>Export is an artifact job; it does not produce Package or alter Package Library.</td>
    <td>Rename to Export Signal Events / Export Source Bundle; output remains external-object artifact.</td>
  </tr>
  <tr>
    <td>IA-04-09</td>
    <td>No ⓘ controls are visible.</td>
    <td>Handoff requires UI-ready information content where explanatory controls exist.</td>
    <td>Add the documented minimal info controls as usability enhancement; this changes neither domain state nor policy.</td>
  </tr>
</table>

# 14. Implementation Rules

1. Use `trading_signal` only as an External Work Object / Mainboard Working Item kind. Never add `trading_signal`, `signal_package`, or `trade_log` to PackageKind or GET /packages output.

2. Treat the V18 labels "Trading Signal Package", "Save As Trading Signal Package" and "Export As Package" as legacy prototype text. Production labels and API contracts must not retain this terminology.

3. Do not run Ready Check, backtest or engine evaluation against client DOM, file input state, localStorage or a visible row. Require persisted root, immutable revision and exact normalized import revision.

4. Store external signal event time and available time separately. Backtest must not consume an event before available_time; no UI default may erase this requirement.

5. Use canonical instrument mapping, IANA timezone normalization and typed direction/signal-type enum validation. Do not compare unvalidated text strings as an execution contract.

6. Use an immutable raw source asset plus durable data-worker import/validation job. Browser parsing/previews may assist UX but cannot create authoritative normalized event state.

7. Do not reuse the Trade Log entry/exit schema as Trading Signal canonical input. Any legacy conversion needs explicit mapping and must produce event timing/availability provenance.

8. Every Save creates an immutable Trading Signal revision. Do not mutate the prior revision, raw source asset, normalized event revision or historical run manifest in place.

9. Do not auto-pin a newly saved revision over the Mainboard item's prior pinned revision except during the first atomic Save & Add flow. Existing board revision changes require explicit, policy-checked pin action.

10. Recompute the Mainboard composition hash transactionally when an item is added, deleted, enabled/disabled or repinned. Mark matching readiness reports stale; do not use a local boolean as authority.

11. Use optimistic concurrency for revision/current-head and Mainboard item mutations. Return conflict/precondition errors with canonical resource state; never silently overwrite another actor's change.

12. Keep expanded/collapsed panel state in presentation preferences only. It creates no revision, audit event, composition snapshot, Ready status change or engine effect.

13. Initial Capital is conditionally required only when shared Allocation is disabled. Preserve the independent value when Allocation is enabled, but exclude it from that run's active capital calculation.

14. Source-file OHLCV is not an Approved Market Data substitute. Any price/execution fallback using market data must resolve to a compatible approved revision at Ready Check/Run time.

15. Require server-side authorization for list/detail/use/edit/delete operations. UI visibility, disabled state or actor fields from request payload are not trusted authority.

16. Delete means soft delete for persisted Trading Signal roots. Require confirmation, active-run dependency preflight, Trash Entry, audit event and outbox; Trash/restore/purge stays Admin-only.

17. Expose the same real source-import, validate, save-revision, attach/pin, export and delete capabilities to Agent through Tool Gateway/API/domain services. Do not make browser automation or human login a prerequisite.

18. Never create a Backtest Result from Trading Signal save/import/export. Only a succeeded asynchronous Backtest Run produces immutable Result artifacts.

# 15. Acceptance Tests

<table>
  <tr>
    <th>ID</th>
    <th>Senaryo</th>
    <th>Beklenen doğrulanabilir sonuç</th>
  </tr>
  <tr>
    <td>TS-01</td>
    <td>Canonical type boundary</td>
    <td>Client sends `package_kind=trading_signal` or calls GET /packages expecting Signal. Server rejects/omits it; `WorkingItemKind=trading_signal` remains valid only for external work object/Mainboard item.</td>
  </tr>
  <tr>
    <td>TS-02</td>
    <td>Transient draft non-runnable</td>
    <td>Selecting Trading Signal creates visible Unsaved UI draft. No root/revision/item id exists; Ready Check snapshot and Run exclude it.</td>
  </tr>
  <tr>
    <td>TS-03</td>
    <td>Required identity</td>
    <td>Save with blank Signal Name or Provider returns structured field error and creates no root/revision/import binding.</td>
  </tr>
  <tr>
    <td>TS-04</td>
    <td>Source import durability</td>
    <td>TXT/CSV upload returns stable job_id. Refresh/logout/closed tab does not cancel import. Worker produces immutable source asset and report/evidence.</td>
  </tr>
  <tr>
    <td>TS-05</td>
    <td>Signal schema</td>
    <td>Import missing available_time produces `AVAILABLE_TIME_REQUIRED` blocker. No Ready valid Signal revision is created by inferring availability from UI render time.</td>
  </tr>
  <tr>
    <td>TS-06</td>
    <td>Signal vs Trade Log schema</td>
    <td>A file containing only entry/exit ledger fields is not silently accepted as a canonical Trading Signal. UI requires explicit event mapping or directs user to Trade Log.</td>
  </tr>
  <tr>
    <td>TS-07</td>
    <td>Timing / lookahead</td>
    <td>An event with event_time 10:00 and available_time 10:03 cannot influence engine decisions before 10:03 even if bar/model starts at 10:00.</td>
  </tr>
  <tr>
    <td>TS-08</td>
    <td>Instrument/timezone mapping</td>
    <td>Unmapped symbol or invalid timezone blocks save/Ready; correction creates new normalized import revision while old report remains historical.</td>
  </tr>
  <tr>
    <td>TS-09</td>
    <td>Data policy</td>
    <td>OHLCV Use=Ignore combined with Intrabar price policy returns cross-field conflict. Source-file OHLCV cannot satisfy an Approved Market Data requirement.</td>
  </tr>
  <tr>
    <td>TS-10</td>
    <td>Capital requiredness</td>
    <td>Allocation disabled + blank/zero capital blocks Ready. Allocation enabled preserves old independent capital but treats allocation binding as active capital source.</td>
  </tr>
  <tr>
    <td>TS-11</td>
    <td>Revision immutability</td>
    <td>Saving provider/mapping change creates revision N+1; revision N content hash and completed run manifest are unchanged.</td>
  </tr>
  <tr>
    <td>TS-12</td>
    <td>Explicit pin</td>
    <td>Saving a new revision does not update existing Mainboard item pin. Explicit pin changes workspace hash and makes prior readiness report stale.</td>
  </tr>
  <tr>
    <td>TS-13</td>
    <td>Concurrency</td>
    <td>Two sessions pin a signal revision using same old Mainboard row version. Exactly one succeeds; other receives stale/conflict response and no lost update.</td>
  </tr>
  <tr>
    <td>TS-14</td>
    <td>Idempotency</td>
    <td>Duplicate save/import/attach request with same idempotency key returns original outcome and creates no duplicate root/revision/job/item.</td>
  </tr>
  <tr>
    <td>TS-15</td>
    <td>Authorization</td>
    <td>User/Supervisor cannot mutate other owner private Signal; Admin may. Direct endpoint call enforces same policy regardless of UI button visibility.</td>
  </tr>
  <tr>
    <td>TS-16</td>
    <td>Presentation state</td>
    <td>Expanding/collapsing row creates no revision/audit/composition change and leaves Ready report valid for the same fingerprint.</td>
  </tr>
  <tr>
    <td>TS-17</td>
    <td>Delete preflight</td>
    <td>Delete a Signal referenced by queued/running Backtest Run returns `ACTIVE_RUN_DEPENDENCY`; no soft delete/Trash Entry is created.</td>
  </tr>
  <tr>
    <td>TS-18</td>
    <td>Soft delete historical integrity</td>
    <td>Eligible delete removes active row/projections and creates Trash/audit/outbox. Completed historical result still resolves signal name/revision provenance from run manifest snapshot.</td>
  </tr>
  <tr>
    <td>TS-19</td>
    <td>Trash restriction</td>
    <td>User/Supervisor/Agent direct Trash list/restore/purge calls are denied. Admin can restore/purge after lifecycle/retention preflight.</td>
  </tr>
  <tr>
    <td>TS-20</td>
    <td>Agent parity</td>
    <td>Agent creates/imports/validates/saves/attaches a Signal via Tool Gateway without opening browser. Agent output ownership and task/checkpoint provenance are recorded; human board is not auto-mutated.</td>
  </tr>
  <tr>
    <td>TS-21</td>
    <td>Run/result boundary</td>
    <td>Save/import/export does not create Backtest Result. Only a succeeded async Backtest Run produces immutable result artifact; failed/cancelled run does not produce normal Result.</td>
  </tr>
</table>

# 16. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Durum</th>
    <th>Sonuç / not</th>
  </tr>
  <tr>
    <td>Master authority</td>
    <td>Evet</td>
    <td>Modül 9 External Work Object, root/revision/pin, event availability ve CR-01 package boundary kaynak doğrusu olarak uygulandı.</td>
  </tr>
  <tr>
    <td>Scope discipline</td>
    <td>Evet</td>
    <td>Bu belge Trading Signal detail/edit/import lifecycleını açıklar. Trade Log, Add Outsource selector, Ready Check/Run, Allocation ve Trash sayfaları yalnız sınır/bağımlılık kadar anıldı.</td>
  </tr>
  <tr>
    <td>Package boundary</td>
    <td>Evet</td>
    <td>Trading Signal Package Library package type olarak anlatılmadı; legacy labels ayrı alignment notunda düzeltildi.</td>
  </tr>
  <tr>
    <td>Source timing</td>
    <td>Evet</td>
    <td>event_time ve available_time ayrımı; lookahead koruması ve required mapping açık yazıldı.</td>
  </tr>
  <tr>
    <td>UI vs backend</td>
    <td>Evet</td>
    <td>V18 DOM/file/local `backtestReady` behaviorı Production authorityden ayrıldı.</td>
  </tr>
  <tr>
    <td>Root/revision/snapshot</td>
    <td>Evet</td>
    <td>Transient draft, immutable revision, explicit pin, composition hash, Ready stale ve historical manifest bütünlüğü ayrıldı.</td>
  </tr>
  <tr>
    <td>Agent parity</td>
    <td>Evet</td>
    <td>Tool/API domain command pathı tanımlandı; UI/browser/human-session bağımlılığı yasaklandı.</td>
  </tr>
  <tr>
    <td>Trash / lifecycle</td>
    <td>Evet</td>
    <td>Soft delete, Admin-only restore/purge, active run blocker, audit/outbox ve historical provenance koruması tanımlandı.</td>
  </tr>
  <tr>
    <td>Run/result boundary</td>
    <td>Evet</td>
    <td>Trading Signal actionları Result üretmez; only succeeded Run immutable Result üretir.</td>
  </tr>
  <tr>
    <td>Implementation decisions identified</td>
    <td>Evet</td>
    <td>Event input schema, data quality terminology, IANA selector/event-model UX, info controls, concrete command/payload/error shapes ve primary save/pin affordance non-canonical gap resolution olarak etiketlendi.</td>
  </tr>
</table>

## 16.1 Implementation Decision Register

<table>
  <tr>
    <th>ID</th>
    <th>Karar</th>
    <th>Gerekçe / etki alanı</th>
  </tr>
  <tr>
    <td>ID-04-01</td>
    <td>Trading Signal inbound source schema uses source_record_id, event_time, available_time, instrument, direction, signal_type; server creates/holds canonical event_id.</td>
    <td>Master minimum revision event contractını uygulanabilir input/mapping sözleşmesine indirger; Trade Log ledger schema ile karışmayı engeller.</td>
  </tr>
  <tr>
    <td>ID-04-02</td>
    <td>Production UI offers `event_based`, `same_as_market_dataset`, or supported bar TF rather than raw Base TF text only.</td>
    <td>External signal sources bar-temelli olmak zorunda değildir. Explicit event model time alignment ve Ready Checki kesinleştirir.</td>
  </tr>
  <tr>
    <td>ID-04-03</td>
    <td>Data Quality options are renamed to signal-event semantics; legacy Entry/Exit wording migrated only if valid event mapping exists.</td>
    <td>V18 shared Trade Log formundaki terminoloji canonical object ayrımını ihlal eder.</td>
  </tr>
  <tr>
    <td>ID-04-04</td>
    <td>Initial save uses `Save &amp; Add to Mainboard`; subsequent saves create revision and require explicit `Use This Revision on Mainboard` pin action.</td>
    <td>Master first item creation ve explicit revision pin kuralını UXte açıklaştırır; silent latest davranışını engeller.</td>
  </tr>
  <tr>
    <td>ID-04-05</td>
    <td>Production adds minimal ⓘ controls, durable import progress/report paneli and explicit delete confirmation.</td>
    <td>Handoff full information-content ve state/recovery standardını karşılar; Master policy/lifecycleyi görünür kılar.</td>
  </tr>
  <tr>
    <td>ID-04-06</td>
    <td>Concrete route/payload/error field names are adopted as typed API contract candidates.</td>
    <td>Master endpoint behaviori kilitler ancak exact URI/field namesini sayfa seviyesinde tam sabitlemez. Modül 19 OpenAPI çalışmasında aynı semantic contract korunur.</td>
  </tr>
</table>
