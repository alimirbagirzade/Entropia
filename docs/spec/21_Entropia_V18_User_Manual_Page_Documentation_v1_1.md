---
title: "Entropia V18 — User Manual Page Documentation v1.1"
page_number: 21
document_type: "Page implementation specification"
source_document: "Entropia_V18_User_Manual_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — User Manual Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18 | USER MANUAL | SAYFA DOKÜMANTASYONU 21/22
> **Original DOCX footer:** Entropia V18 | User Manual Page Documentation v1.0 | Production V1 implementation reference

ENTROPIA V18

USER MANUAL

Sayfa Dokümantasyonu 21/22 | Sürekli Manual Stream, Admin Append/Upload, Search, Revision, Agent Retrieval, Trash ve Audit Sözleşmesi

<table>
  <tr>
    <th>Belge kapsamı<br/>Bu belge yalnız Help &gt; User Manual sayfasını tanımlar. Reader, sidebar, arama, Admin compose/upload akışı, manual document lifecycle, internal Agent retrieval, soft delete/restore ve audit bu kapsamın içindedir. Mainboard, Package Library, Analysis Lab, Trash veya Panelin kendi ayrıntılı arayüz davranışları burada tekrar tasarlanmaz; yalnız bu sayfanın bağımlılığı olarak anılır.</th>
  </tr>
</table>

# 0. Document Control, Scope ve Source Traceability

Bu teslim, Entropia V18 User Manual sayfası için Production V1 implementation specificationdır. V18 HTML görünür arayüz ve interaction hedefini gösterir; persistence, authorization, lifecycle, API ve agent davranışında Master Technical Reference v1.0 üst otoritedir.

<table>
  <tr>
    <th>Kaynak / referans</th>
    <th>Bu sayfada kullanılan karar</th>
    <th>Öncelik ve uygulama notu</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 - Modül 17</td>
    <td>Continuous Manual Stream, all-role read/search, Admin-only write, root/revision/stream entry, block model, search, Agent retrieval, Trash/audit, API ve acceptance tests.</td>
    <td>Canonical technical authority.</td>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 - Modül 1, 2, 3, 14, 16, 19, 20</td>
    <td>Role/policy, immutable revision, soft delete/restore, Agent API parity, logs/audit, API layering, storage/outbox/cache sınırları.</td>
    <td>Çapraz canonical dependencies.</td>
  </tr>
  <tr>
    <td>V18 ana HTML - Help &gt; User Manual</td>
    <td>İki kolon layout, sidebar, Upload Text Document, + Add / Paste Text, arama, documents listesi, continuous reader, built-in guide, remove action, placeholder ve notice metinleri.</td>
    <td>V18 Interface Observation; backend doğrusu değildir.</td>
  </tr>
  <tr>
    <td>Sayfa Bazlı Dokümantasyon Handoff v1.1</td>
    <td>Field/state/content/command matrices, V18 vs Production ayrımı, implementation rules ve acceptance test standardı.</td>
    <td>Yazım ve teslim standardı.</td>
  </tr>
  <tr>
    <td>2.3 POSITION ENTRY LOGIC örneği</td>
    <td>Kavramları insan + engine/backend/Agent katmanlarında açıklama, dependency/validation/recovery ve test kesinliği.</td>
    <td>Anlatım derinliği referansı; domain otoritesi değildir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam dışı sınır<br/>Bu sayfa PDF/DOCX/OCR ingestion, community documentation, non-Admin collaborative editing, rich WYSIWYG editing, per-document custom visibility, kullanıcı yorumları veya executable manual content tasarlamaz. Bunlar Production V1 içinde aktif sayılmaz.</th>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kavramsal Sınır

User Manual, Entropia içindeki yayınlanmış ürün bilgisini tek bir reader deneyiminde sunan yardım katmanıdır. Kullanıcı, baseline guide ve Admin tarafından eklenmiş belgeleri tek bir continuous manual stream içinde okur. Bu sayfa işlem üreten bir workbench değildir; kullanıcının kavramları, sayfaları ve güvenli kullanım sınırlarını anlaması için sistem bilgisini yayınlar.

Production V1de tek bir büyük TEXT alanı veya tarayıcı localStorage listesi yoktur. Her eklenen içerik ayrı bir Manual Document root olarak yaşar; içerik değişiklikleri immutable Manual Document Revision üretir; reader ise yayınlanmış revisionları sabit stream order ile birleştirir.

<table>
  <tr>
    <th>Kavram</th>
    <th>Canonical kısa tanım</th>
    <th>Bu sayfadaki görünür karşılık</th>
  </tr>
  <tr>
    <td>Baseline Guide</td>
    <td>Ürünle birlikte gelen system-owned başlangıç rehberi; is_baseline=true.</td>
    <td>Readerın ilk bölümü; Remove Document yoktur.</td>
  </tr>
  <tr>
    <td>Manual Document</td>
    <td>Admin tarafından eklenen ya da text file üzerinden yüklenen bağımsız bilgi belgesi rootu.</td>
    <td>Sidebar document listesi ve reader bölümü.</td>
  </tr>
  <tr>
    <td>Manual Document Revision</td>
    <td>Bir belgenin değiştirilemez içerik/source/parse sürümü.</td>
    <td>Readerda görünen Published revision; source label ile izlenir.</td>
  </tr>
  <tr>
    <td>Continuous Manual Stream</td>
    <td>Baseline + aktif published manual entrylerinin sıralı read model birleştirmesi.</td>
    <td>Sağ readerda kesintisiz metin akışı.</td>
  </tr>
  <tr>
    <td>Canonical Content Block</td>
    <td>Heading, paragraph, list, code, callout vb. güvenli renderlanabilir içerik parçası.</td>
    <td>Production readerın biçimlendirilmiş içerik blokları.</td>
  </tr>
  <tr>
    <td>Manual Search Chunk</td>
    <td>Revision/block range üzerinden title/heading/content arama projeksiyonu.</td>
    <td>Arama sonucu, excerpt ve deep link.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Canonical Rule<br/>Manual content ürün bilgisidir; runtime policy kaynağı değildir. Manualdaki eski prototype ifadeleri, Package enumu, Trading Signal/Trade Log sınıflaması, role policy veya Backtest davranışını override edemez. Bu kararlar ilgili domain service ve Master modüllerinden gelir.</th>
  </tr>
</table>

# 2. Erişim, Görünürlük, Ownership ve Server-Side Yetki

User Manualın Published corpusunu Admin, Supervisor, User ve Agent okuyabilir ve arayabilir. Human UI menü görünürlüğü veya V18de bir actionın hidden/disabled olması authorization kanıtı değildir. Her reader, search ve mutation endpointi server-side policy ile karar verir.

<table>
  <tr>
    <th>İşlem</th>
    <th>Admin</th>
    <th>Supervisor</th>
    <th>User</th>
    <th>Agent</th>
    <th>Production policy</th>
  </tr>
  <tr>
    <td>Published stream okuma</td>
    <td>Evet</td>
    <td>Evet</td>
    <td>Evet</td>
    <td>Internal retrieval</td>
    <td>Published ve active stream içeriği.</td>
  </tr>
  <tr>
    <td>Search</td>
    <td>Evet</td>
    <td>Evet</td>
    <td>Evet</td>
    <td>Internal retrieval</td>
    <td>Yalnız Published search projection.</td>
  </tr>
  <tr>
    <td>Belge ekleme / upload</td>
    <td>Evet</td>
    <td>Hayır</td>
    <td>Hayır</td>
    <td>Hayır</td>
    <td>ADMIN_MANUAL_WRITE_REQUIRED.</td>
  </tr>
  <tr>
    <td>Revision replace / publish</td>
    <td>Evet</td>
    <td>Hayır</td>
    <td>Hayır</td>
    <td>Hayır</td>
    <td>Admin command + revision concurrency.</td>
  </tr>
  <tr>
    <td>Soft delete</td>
    <td>Evet</td>
    <td>Hayır</td>
    <td>Hayır</td>
    <td>Hayır</td>
    <td>Baseline hariç, Admin-only.</td>
  </tr>
  <tr>
    <td>Restore / permanent purge</td>
    <td>Evet</td>
    <td>Hayır</td>
    <td>Hayır</td>
    <td>Hayır</td>
    <td>Trash Admin-only policy.</td>
  </tr>
  <tr>
    <td>Reader UI kullanımı</td>
    <td>Evet</td>
    <td>Evet</td>
    <td>Evet</td>
    <td>Zorunlu değil</td>
    <td>Agent browser kullanıcı değildir.</td>
  </tr>
</table>

V18de upload yetkisi `canUploadUserManual()` ile `canManageRoles()` sonucuna bağlanmıştır. Productionda bu görünür helper değil, explicit manual mutation policy uygulanır: Admin principal dışında hiçbir human veya Agent append, upload, replace, delete ya da restore yapamaz.

<table>
  <tr>
    <th>V18 Interface Observation<br/>V18de appended documentin Remove Document düğmesi, generic owner/delete helper davranışına bağlı görünebilir. Productionda User Manual için daha dar ve canonical kural uygulanır: ekleme, düzenleme, kaldırma ve restore yalnız Admin tarafından başlatılır.</th>
  </tr>
</table>

# 3. V18 Interface Behavior: Gerçek Arayüz Yerleşimi ve Bileşen Envanteri

V18de Help menüsü altındaki User Manual actionı sayfayı açar. Sayfa 980px altındaki dar ekranlarda tek kolona düşen iki kolonlu bir shell kullanır: solda sticky sidebar, sağda minimum 620px yüksekliğinde reader. V18de görünür ayrı modal, tab, pagination toolbar, sort control veya ⓘ info icon yoktur.

# 3.1 Sidebar: MANUAL DOCUMENTS

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 görünür davranış ve default</th>
    <th>Görünme / erişim koşulu</th>
  </tr>
  <tr>
    <td>MANUAL DOCUMENTS başlığı</td>
    <td>Sidebar üstünde sabit label.</td>
    <td>Her User Manual sayfasında.</td>
  </tr>
  <tr>
    <td>Upload Text Document</td>
    <td>Dosya inputu olan label-button. Accept: .txt, .md, .html, text/plain, text/markdown, text/html.</td>
    <td>Yalnız V18de upload yetkisi olan kullanıcıda; Production Admin-only.</td>
  </tr>
  <tr>
    <td>+ Add / Paste Text / Close Text Editor</td>
    <td>Composerı açıp kapatan geniş button. Default: composer kapalı.</td>
    <td>Admin-only Production. Composer açıkken label Close Text Editor olur.</td>
  </tr>
  <tr>
    <td>Admin-only note</td>
    <td>“Only Admin can upload or add manual documents. All roles can search, open and read the complete manual text.”</td>
    <td>Admin olmayan human rolelarda görünür.</td>
  </tr>
  <tr>
    <td>Search all manual text</td>
    <td>Search label + input. Default: boş. Placeholder: “Search headings or text”.</td>
    <td>Tüm reader erişimi olan human kullanıcılarda.</td>
  </tr>
  <tr>
    <td>SEARCH RESULTS</td>
    <td>Query boşsa yardım empty-state; query varsa result buttons veya no-match state.</td>
    <td>Her zaman; içerik query durumuna göre.</td>
  </tr>
  <tr>
    <td>CONTINUOUS MANUAL SECTIONS</td>
    <td>Baseline dahil document listesi; item title + source meta.</td>
    <td>Streamde görünür active documents varsa.</td>
  </tr>
  <tr>
    <td>ADD TEXT DOCUMENT composer</td>
    <td>Document Title input, Full Text textarea ve Add Document button.</td>
    <td>Composer açık + Admin.</td>
  </tr>
</table>

# 3.2 Reader: ENTROPIA USER MANUAL

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 görünür davranış ve default</th>
    <th>Production eşlemesi</th>
  </tr>
  <tr>
    <td>Reader toolbar</td>
    <td>Title: ENTROPIA USER MANUAL. Meta: “Built-in guidance and added documents are displayed below as one continuous reading flow.”</td>
    <td>Continuous stream read modelinin headerı; ayrı document seçme viewı değildir.</td>
  </tr>
  <tr>
    <td>Notice banner</td>
    <td>`userManualNotice` boşsa görünmez; action sonrası açık mavi notice görünür.</td>
    <td>Command result / search indexing state için transient UI message.</td>
  </tr>
  <tr>
    <td>Built-in guide</td>
    <td>İlk section: Entropia Interface Guide; source “Built-in Manual”.</td>
    <td>System-owned baseline; reader UI ile silinemez.</td>
  </tr>
  <tr>
    <td>Appended document section</td>
    <td>Title, source meta, formatted content; section id `manual-section-{id}`.</td>
    <td>Active stream entry + visible Published revision + stable section anchor.</td>
  </tr>
  <tr>
    <td>Remove Document</td>
    <td>V18de removable appended section altında gösterilir; built-in guide için gösterilmez.</td>
    <td>Production Admin-only soft delete + confirmation; baseline için yok.</td>
  </tr>
  <tr>
    <td>Smooth-scroll target</td>
    <td>Search ve list item click ilgili sectiona `scrollIntoView` yapar.</td>
    <td>Deep link / anchor resolve; server search result anchorı doğrulanır.</td>
  </tr>
</table>

# 3.3 V18 prototype default manual metni için alignment notu

V18 built-in guide, güncel canonical kavramlardan eski veya sadeleştirilmiş prototip terimler taşıyabilir. Özellikle “Trading Signal ve Trade Log packages” ifadesi Production V1 için doğru değildir: Trading Signal ve Trade Log Package Library package typeı değil, external Mainboard Working Itemdır. Baseline guide sistem release/migration yoluyla canonical içerikle güncellenmelidir; client-side hardcoded text veya localStorage bu kaynak doğrusu olamaz.

<table>
  <tr>
    <th>Implementation Alignment Note<br/>V18 readerın tek akış deneyimi korunur; fakat localStorage persistence, FileReader ile doğrudan array mutation, basit substring search, raw-source formatting heuristic ve generic owner delete helper Productionda taşınmaz. Bunların yerine server-authoritative root/revision/stream/index modeli uygulanır.</th>
  </tr>
</table>

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen / state</th>
    <th>Varsayılan veya trigger</th>
    <th>UI davranışı</th>
    <th>Payload / engine / persistence etkisi</th>
  </tr>
  <tr>
    <td>Page load - loading</td>
    <td>Help &gt; User Manual açılır.</td>
    <td>Reader skeleton veya compact loading state; stale local content source of truth değildir.</td>
    <td>GET stream query; response tek stream_version snapshotı taşır.</td>
  </tr>
  <tr>
    <td>Reader ready</td>
    <td>Published baseline + active entries döner.</td>
    <td>Baseline ilk, appended docs position sırasıyla görünür.</td>
    <td>Canonical reader projection renderlanır.</td>
  </tr>
  <tr>
    <td>Reader empty (non-baseline)</td>
    <td>Appended manual yok.</td>
    <td>Baseline görünür; sidebar section listesinde yalnız baseline görünür.</td>
    <td>Hata değildir; stream normaldir.</td>
  </tr>
  <tr>
    <td>Search blank</td>
    <td>Input boş.</td>
    <td>“Enter a word or phrase to search every part of the continuous manual.”</td>
    <td>Search query çağrısı zorunlu değildir.</td>
  </tr>
  <tr>
    <td>Search results</td>
    <td>Debounced non-empty query.</td>
    <td>Title/heading/excerpt/source; click deep link.</td>
    <td>Server search Published chunks üzerinden çalışır.</td>
  </tr>
  <tr>
    <td>Search no match</td>
    <td>Query için sonuç yok.</td>
    <td>“No document text matches this search.”</td>
    <td>Stream değişmez.</td>
  </tr>
  <tr>
    <td>Search index updating</td>
    <td>Yeni publication sonrası index job tamamlanmamış.</td>
    <td>Reader belgenin görünür olduğunu korur; küçük note: “Search index updating. New content may appear in search shortly.”</td>
    <td>Eventual consistency; manual kaybı değildir.</td>
  </tr>
  <tr>
    <td>Composer closed</td>
    <td>Default.</td>
    <td>Title/content alanları görünmez.</td>
    <td>Draft form state yok veya UI transient.</td>
  </tr>
  <tr>
    <td>Composer open</td>
    <td>Admin + Add/Paste click.</td>
    <td>Title ve content alanları görünür.</td>
    <td>Henüz root/revision oluşmaz.</td>
  </tr>
  <tr>
    <td>Composer validation error</td>
    <td>Title/content eksik veya server validation fail.</td>
    <td>Composer açık kalır; field error/notice görünür; entered text korunur.</td>
    <td>No document/revision/stream event.</td>
  </tr>
  <tr>
    <td>Upload reading / parsing</td>
    <td>Admin valid source seçer.</td>
    <td>Button/input busy; duplicate submit engellenir.</td>
    <td>Raw source staging + parse/validation pipeline.</td>
  </tr>
  <tr>
    <td>Publish success</td>
    <td>Append transaction commit olur.</td>
    <td>Notice, reader refetch, yeni anchor scroll; index note olabilir.</td>
    <td>Root + revision + stream entry + audit atomik.</td>
  </tr>
  <tr>
    <td>Stale / conflict</td>
    <td>Stream/revision context değişmiş.</td>
    <td>“Manual changed while you were editing. Review the latest version and try again.”</td>
    <td>409/412; client canonical state ile rehydrate olur.</td>
  </tr>
  <tr>
    <td>Soft-deleted document</td>
    <td>Admin remove command success.</td>
    <td>Section/sidebar/searchten çıkar; toast görünür.</td>
    <td>root.lifecycle_state=soft_deleted; Trash snapshot.</td>
  </tr>
  <tr>
    <td>Restored document</td>
    <td>Trash restore success.</td>
    <td>Reader/list/search projection refetch; deterministic positionta döner.</td>
    <td>Same root/revision chain; audit/index event.</td>
  </tr>
</table>

# 5. Field Contract Matrix: Alanlar, Varsayılanlar, Zorunluluk ve Dependency

V18de yalnız Admin compose formunda görünür yıldız işareti yoktur. Productionda zorunlu alanlar label yanında `*` ile gösterilir. `*`, UI dekorasyonu değil; backend request validation, Admin command schema ve Agent tool policy ile eşleşen zorunluluktur.

<table>
  <tr>
    <th>Alan / UI tipi</th>
    <th>V18 default</th>
    <th>Zorunluluk ve koşul</th>
    <th>Production payload</th>
    <th>Validation / dependent-state davranışı</th>
  </tr>
  <tr>
    <td>Search all manual text<br/>text input</td>
    <td>Boş; placeholder “Search headings or text”.</td>
    <td>Zorunlu değil. Boş query search çağrısı üretmez.</td>
    <td>q, cursor, limit, stream_version optional.</td>
    <td>Trim; max query limit; published corpus only. Query değişince önceki results stale sayılır.</td>
  </tr>
  <tr>
    <td>Upload Text Document<br/>file input</td>
    <td>Seçim yok; accept .txt/.md/.html ve MIME eşdeğerleri.</td>
    <td>Admin actionı için dosya zorunlu. Title uploadda filename steminden türetilir; Admin değiştirebilir.</td>
    <td>source_type, source_filename, bytes, content_stream / object_ref, idempotency_key.</td>
    <td>TXT/MD/HTML only; UTF-8 normalize; byte-size, parse, duplicate checksum. PDF/DOCX/image reject.</td>
  </tr>
  <tr>
    <td>Document Title *<br/>text input</td>
    <td>Boş; placeholder “Manual document title”.</td>
    <td>Add/Paste composer açıkken always required. Uploadda initial suggestion filename olabilir, fakat final title required.</td>
    <td>title.</td>
    <td>Whitespace-only yok; normalized title limit; duplicate title tek başına blocker değildir ancak warning olabilir.</td>
  </tr>
  <tr>
    <td>Full Text *<br/>textarea</td>
    <td>Boş; placeholder V18 metni aşağıda catalogda.</td>
    <td>Add/Paste composer açıkken always required.</td>
    <td>content, source_type=AddedText.</td>
    <td>Canonical blocks içinde en az bir visible text block; empty/whitespace reject.</td>
  </tr>
  <tr>
    <td>Add Document<br/>button</td>
    <td>Composer closedken görünmez; openken enabled unless submission in progress.</td>
    <td>Title + Full Text valid olduğunda action enabled; server yine validate eder.</td>
    <td>POST manual document command.</td>
    <td>Disabled/loading; idempotency; 201 success anchor; 422 errors.</td>
  </tr>
  <tr>
    <td>Close Text Editor<br/>button</td>
    <td>Composer açıkken gösterilir.</td>
    <td>Required değil; unsaved content varsa Production confirmation.</td>
    <td>No server mutation.</td>
    <td>Client-only state; close does not delete existing document.</td>
  </tr>
  <tr>
    <td>Document list item<br/>button</td>
    <td>All docs visible; baseline first.</td>
    <td>Read access required.</td>
    <td>document_id/revision/anchor query preference.</td>
    <td>Click target missing/stale ise stream refetch then anchor retry.</td>
  </tr>
  <tr>
    <td>Remove Document<br/>button</td>
    <td>Appended docs only; V18 generic owner helper.</td>
    <td>Production: Admin + non-baseline + Active root.</td>
    <td>DELETE document id + expected_table_version + idempotency_key.</td>
    <td>Soft delete confirmation; BASELINE_MANUAL_IMMUTABLE; Admin policy.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Conditional requiredness<br/>Upload akışında file seçimi ve desteklenen format zorunludur; title V18de kullanıcıdan ayrı istenmez fakat Productionda filename-derived başlık editlenebilir ve final committe boş olamaz. Add/Paste akışında hem Document Title * hem Full Text * zorunludur.</th>
  </tr>
</table>

# 6. Information Content Catalog ve Nihai UI Metinleri

V18 User Manual ekranında görünür ⓘ information button bulunmaz. Bu nedenle aşağıdaki ilk satır, mevcut UI için “yok” kaydıdır. Devamındaki metinler Productionda bir ⓘ kontrolü gösterilirse doğrudan kullanılacak final panel içeriğidir; yeni zorunlu işlem akışı yaratmaz.

<table>
  <tr>
    <th>Info key / UI alanı</th>
    <th>Panel başlığı</th>
    <th>Nihai UI metni</th>
  </tr>
  <tr>
    <td>V18 visible ⓘ inventory</td>
    <td>Not applicable</td>
    <td>V18 User Manual ekranında görünür ⓘ bilgi düğmesi yoktur. Mevcut yardım, sidebar labels, placeholders, admin-only note ve reader meta metinleriyle verilir.</td>
  </tr>
  <tr>
    <td>manualContinuousStreamInfo</td>
    <td>Continuous Manual Stream</td>
    <td>The User Manual is shown as one reading flow. The built-in guide always appears first. Added published documents follow in a stable order. Updating a document does not move its position in the flow.</td>
  </tr>
  <tr>
    <td>manualUploadInfo</td>
    <td>Supported Text Documents</td>
    <td>You can upload UTF-8 TXT, Markdown or HTML text documents. The system converts supported content into safe manual blocks before publication. PDF, DOCX and image files are not accepted in Production V1.</td>
  </tr>
  <tr>
    <td>manualSearchInfo</td>
    <td>Search the Manual</td>
    <td>Search looks through published document titles, headings and content. Results open the most relevant section in the continuous manual. Newly published content can appear in the reader before its search index is ready.</td>
  </tr>
  <tr>
    <td>manualComposerInfo</td>
    <td>Add Text Document</td>
    <td>Enter a clear title and the complete text. The document will be normalized, validated and appended to the end of the published manual stream after the command succeeds.</td>
  </tr>
  <tr>
    <td>manualRemoveInfo</td>
    <td>Remove Document</td>
    <td>Removing a manual document moves it to Trash; it does not immediately destroy the historical revision. Only an Admin can remove or restore an added document. The built-in guide cannot be removed from this page.</td>
  </tr>
</table>

# 6.1 Placeholder, helper, warning, toast, confirmation ve error metinleri

<table>
  <tr>
    <th>UI bağlamı</th>
    <th>Nihai metin</th>
  </tr>
  <tr>
    <td>Search placeholder</td>
    <td>Search headings or text</td>
  </tr>
  <tr>
    <td>Composer title placeholder</td>
    <td>Manual document title</td>
  </tr>
  <tr>
    <td>Composer content placeholder</td>
    <td>Paste or write the complete text. It will be appended below the existing manual in the same continuous reading flow.</td>
  </tr>
  <tr>
    <td>Non-Admin helper</td>
    <td>Only Admin can upload or add manual documents. All roles can search, open and read the complete manual text.</td>
  </tr>
  <tr>
    <td>Blank search empty-state</td>
    <td>Enter a word or phrase to search every part of the continuous manual.</td>
  </tr>
  <tr>
    <td>No search result</td>
    <td>No document text matches this search.</td>
  </tr>
  <tr>
    <td>Text append success</td>
    <td>Text document added to the end of the continuous manual.</td>
  </tr>
  <tr>
    <td>Upload success</td>
    <td>Uploaded document added to the end of the continuous manual.</td>
  </tr>
  <tr>
    <td>Soft delete success</td>
    <td>Document moved to Trash.</td>
  </tr>
  <tr>
    <td>Upload read failure</td>
    <td>The selected document could not be read. Use a UTF-8 TXT, MD or HTML text file.</td>
  </tr>
  <tr>
    <td>Required fields error</td>
    <td>A document title and full text are required.</td>
  </tr>
  <tr>
    <td>Unsupported type error</td>
    <td>This file type is not supported. Upload a UTF-8 TXT, Markdown or HTML text document.</td>
  </tr>
  <tr>
    <td>Parse error</td>
    <td>The document could not be converted into a valid manual structure. No changes were published.</td>
  </tr>
  <tr>
    <td>Duplicate content warning</td>
    <td>An active manual section has the same normalized content. Review the existing section before adding a duplicate.</td>
  </tr>
  <tr>
    <td>Unauthorized error</td>
    <td>Only Admin can add, upload, revise, remove or restore manual documents.</td>
  </tr>
  <tr>
    <td>Stale conflict</td>
    <td>Manual content changed while you were editing. Review the latest version and try again.</td>
  </tr>
  <tr>
    <td>Remove confirmation title</td>
    <td>Remove manual document?</td>
  </tr>
  <tr>
    <td>Remove confirmation body</td>
    <td>“{title}” will be removed from the published manual and moved to Trash. Existing historical citations remain preserved according to retention policy.</td>
  </tr>
  <tr>
    <td>Remove confirmation actions</td>
    <td>Cancel | Move to Trash</td>
  </tr>
  <tr>
    <td>Search index note</td>
    <td>Search index updating. New content may appear in search shortly.</td>
  </tr>
</table>

# 7. Button, Command ve State Sözleşmesi

<table>
  <tr>
    <th>UI action</th>
    <th>Production command / query</th>
    <th>Precondition ve disabled/loading</th>
    <th>Success / error / audit</th>
  </tr>
  <tr>
    <td>Open User Manual</td>
    <td>GET /v1/manual/stream</td>
    <td>Published reader access. Page shows loading until consistent stream snapshot arrives.</td>
    <td>200 stream + stream_version/ETag. Read audit optional; no mutation audit required.</td>
  </tr>
  <tr>
    <td>Type search query</td>
    <td>GET /v1/manual/search?q=&amp;cursor=</td>
    <td>Trimmed non-empty q; debounce; prior response ignored when query token changes.</td>
    <td>Results carry document_id, revision_no, heading_path, excerpt, anchor, stream_version.</td>
  </tr>
  <tr>
    <td>Open result / section</td>
    <td>Anchor navigation + optional GET revision/section</td>
    <td>Anchor must exist in current stream version; if stale, refetch then resolve.</td>
    <td>Smooth scroll; no mutation. Missing anchor shows “The section is no longer available in the current manual.”</td>
  </tr>
  <tr>
    <td>+ Add / Paste Text</td>
    <td>Local compose state transition</td>
    <td>Admin capability; no server mutation. If close with dirty text, confirmation.</td>
    <td>Composer open/closed only.</td>
  </tr>
  <tr>
    <td>Add Document</td>
    <td>POST /v1/admin/manual/documents</td>
    <td>Admin; title/content valid; idempotency_key; optional expected_table_version. Busy state blocks duplicate click.</td>
    <td>201 document/revision/anchor; refetch stream; scroll anchor; manual_document_published event. 422/409/403 handled.</td>
  </tr>
  <tr>
    <td>Upload Text Document</td>
    <td>POST /v1/admin/manual/documents:upload</td>
    <td>Admin; supported file; pending upload/parse prevents duplicate submit.</td>
    <td>201 success same as pasted text; raw source object retained per policy; outbox index job.</td>
  </tr>
  <tr>
    <td>Remove Document</td>
    <td>DELETE /v1/admin/manual/documents/{id}</td>
    <td>Admin; active non-baseline document; explicit confirmation; expected_table_version and idempotency_key.</td>
    <td>202/200 soft delete; stream/search invalidated; Trash entry; manual_document_soft_deleted.</td>
  </tr>
  <tr>
    <td>Restore from Trash</td>
    <td>POST /v1/admin/manual/documents/{id}:restore</td>
    <td>Admin Trash action; recoverable entry; not permanently purged.</td>
    <td>Active stream entry returns at deterministic position; index job; manual_document_restored.</td>
  </tr>
  <tr>
    <td>Replace revision (backend capability; V18 UI not exposed)</td>
    <td>POST /v1/admin/manual/documents/{id}/revisions</td>
    <td>Admin; expected_head_revision_id; HTTP transport: If-Match/ETag; parsed valid content.</td>
    <td>New Published revision replaces visible revision at same stream position; old revision Superseded; manual_document_revised.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Implementation Decision - Concurrency and idempotency<br/>Stream mutations use an `expected_table_version` precondition when the caller acts on a known reader snapshot; revision replacement uses `expected_head_revision_id`; HTTP transport: If-Match/ETag. The HTTP ETag transports concurrency information; it is not the domain revision identity. Every create/upload/delete/restore command carries an idempotency_key.</th>
  </tr>
</table>

# 8. Kullanıcı, Admin, Agent ve Recovery Akışları

# 8.1 Flow A - All-role read ve search

- Human user Help > User Manual açar. Frontend published stream projectionını ister; localStorage veya cached DOM canonical kaynak kabul edilmez.

- Backend caller policy uygular ve baseline + active published entries için tek stream_version snapshot döndürür.

- Reader baselineı ilk, appended manual sectionsı stream_position sırasıyla render eder. Sidebar aynı snapshot üzerinden document listesi oluşturur.

- Kullanıcı arama metni girer. Server title, heading ve content chunk üzerinde search yapar; document-level substring filtre yeterli değildir.

- Kullanıcı sonuç seçer. Frontend, result anchorı mevcut streamde resolve eder ve ilgili block/sectiona smooth-scroll yapar. Stale anchor varsa readerı rehydrate eder.

# 8.2 Flow B - Admin pasted text append

- Admin + Add / Paste Text ile composerı açar. Document Title * ve Full Text * girilir.

- Frontend yalnız temel empty-state validation yapabilir; canonical validation server commandde yeniden çalışır.

- POST command raw texti alır; UTF-8 normalize eder, canonical blocks/heading tree üretir, checksum ve duplicate kontrollerini çalıştırır.

- Başarı transactionı document root, immutable Published revision, active stream entry, publication event ve outbox search-index eventini birlikte oluşturur.

- Response anchor döndürür. UI streami yeniden alır, success notice gösterir, yeni bölüme scroll eder. Search index gecikirse reader görünür kalır ve küçük status note gösterilir.

# 8.3 Flow C - Admin upload

- Admin Upload Text Document actionından TXT, MD veya HTML seçer. Uploadda title filename steminden önerilir; publish öncesi final title boş olamaz.

- Backend source metadata, allowed format, byte size, encoding ve parse outcome doğrular. Raw source object storageda retention/policy kapsamında tutulabilir.

- Markdown ve allowlisted HTML canonical block modeline dönüştürülür. Raw HTML, markdown veya filename readerda doğrudan inject edilmez.

- Parser/validation başarısızsa root/revision/stream entry yayınlanmaz; readerın önceki published snapshotı korunur ve error mesajı gösterilir.

# 8.4 Flow D - Admin soft delete, restore ve historical citation

- Admin appended documentte Remove Documentı seçer. Production confirmation modalı title ve Trash sonucunu açıklar.

- DELETE command, baseline olmadığını, callerın Admin olduğunu, documentin active olduğunu ve stream preconditionını doğrular.

- Soft delete root lifecycleını soft_deleted yapar; active stream entry reader/search projectionından çıkar; immutable snapshot Trash entry ile ilişkilendirilir.

- Daha önce Agent artifactinde kullanılabilen revision/block citationı retention boyunca resolve edilebilir kalır. Güncel readerdan kaybolması, tarihi kanıtı kırmaz.

- Admin Trash üzerinden restore isterse aynı root/revision chain yeniden etkinleşir. Original position boşsa deterministic yakın relative position kuralı uygulanır; V18deki “always end” prototype davranışı canonical değildir.

# 8.5 Flow E - Agent documentation retrieval

- Agent, browser UIya veya human sessiona bağlı olmadan Tool Gateway üzerinden `documentation.search` / `documentation.get_section` çağrısı yapar.

- Backend yalnız Published manual stream/canonical blocks döndürür; draft veya soft-deleted içerik normal retrievala dahil değildir.

- Agent bir artifactte manualdan yararlanırsa document_id, revision_no, anchor ve block_ids citation olarak eklenir.

- Agent manualı kavramsal açıklama için kullanabilir; role, data usage, backtest readiness veya domain policy kararı için ilgili authoritative servicein validation sonucunu kullanır.

- Agent append, upload, replace, publish, delete, restore veya UI-based workflow çağrısı yapamaz.

# 9. Production Backend / Domain Modeli

User Manual Production V1de root-revision-stream-entry ayrımını kullanır. UI reader bir denormalized projectiondır; kalıcı kaynak doğrusu değildir. Aşağıdaki nesneler yalnız bu sayfanın domain sınırı içindedir.

<table>
  <tr>
    <th>Nesne</th>
    <th>Kimlik / lifecycle</th>
    <th>Temel sorumluluk</th>
  </tr>
  <tr>
    <td>manual_document</td>
    <td>document_id UUID; lifecycle_state = active | soft_deleted; is_baseline boolean.</td>
    <td>Kalıcı kimlik, ownership/provenance, baseline ayrımı.</td>
  </tr>
  <tr>
    <td>manual_document_revision</td>
    <td>revision_id UUID; revision_no artar; publication_state = Draft | Published | Superseded | Removed.</td>
    <td>Title, source metadata, normalized blocks, heading tree, checksum. Immutable content version.</td>
  </tr>
  <tr>
    <td>manual_stream_entry</td>
    <td>stream_entry_id UUID; state Active | Removed; unique stream_position; visible_revision_id.</td>
    <td>Documentin continuous streamdeki sabit sırası ve görünür revisionı.</td>
  </tr>
  <tr>
    <td>manual_content_block</td>
    <td>block_id stable; revisiona bağlı.</td>
    <td>heading/paragraph/bullet_list/ordered_list/code/callout/divider safe renderer inputu.</td>
  </tr>
  <tr>
    <td>manual_search_chunk</td>
    <td>revision + block range + heading path + anchor.</td>
    <td>Server-side search, ranking, excerpt ve deep link.</td>
  </tr>
  <tr>
    <td>manual_publication_event</td>
    <td>immutable event/correlation id.</td>
    <td>append, publish, revise, remove, restore, purge audit izi.</td>
  </tr>
  <tr>
    <td>manual_stream_projection</td>
    <td>stream_version/ETag taşıyan read model.</td>
    <td>Reader/sidebar için cachelenebilir consistent snapshot.</td>
  </tr>
</table>

# 9.1 Minimum persisted fields

<table>
  <tr>
    <th>Alan</th>
    <th>Kural</th>
  </tr>
  <tr>
    <td>manual_document.document_id</td>
    <td>Kalıcı root UUID.</td>
  </tr>
  <tr>
    <td>manual_document.owner_actor_id</td>
    <td>Productionda descriptive provenance; manual write Admin actor ile sınırlıdır.</td>
  </tr>
  <tr>
    <td>manual_document.is_baseline</td>
    <td>Built-in guide için true; normal User Manual delete akışından hariç.</td>
  </tr>
  <tr>
    <td>manual_revision.title</td>
    <td>Zorunlu kullanıcı-facing section title.</td>
  </tr>
  <tr>
    <td>manual_revision.source_type</td>
    <td>BuiltIn | AddedText | UploadedTxt | UploadedMarkdown | UploadedHtml.</td>
  </tr>
  <tr>
    <td>manual_revision.source_filename</td>
    <td>Upload source ise orijinal filename; readerda raw source olarak çalıştırılmaz.</td>
  </tr>
  <tr>
    <td>manual_revision.normalized_content</td>
    <td>Canonical block collection.</td>
  </tr>
  <tr>
    <td>manual_revision.content_checksum</td>
    <td>Duplicate content detect için normalized checksum.</td>
  </tr>
  <tr>
    <td>manual_stream_entry.stream_position</td>
    <td>Active entries arasında unique, atomik ve sıralı numeric position.</td>
  </tr>
  <tr>
    <td>manual_stream_entry.visible_revision_id</td>
    <td>Readerın render ettiği current Published revision.</td>
  </tr>
  <tr>
    <td>manual_stream_projection.stream_version</td>
    <td>Publish/revise/remove/restore sonrası artan consistent reader snapshot sürümü.</td>
  </tr>
</table>

# 9.2 Canonical block renderer

<table>
  <tr>
    <th>Block type</th>
    <th>Zorunlu alanlar</th>
    <th>Reader kuralı</th>
  </tr>
  <tr>
    <td>heading</td>
    <td>block_id, level, text, anchor</td>
    <td>Semantic heading render; stable deep link.</td>
  </tr>
  <tr>
    <td>paragraph</td>
    <td>block_id, text</td>
    <td>Escaped text + safe typography.</td>
  </tr>
  <tr>
    <td>bullet_list / ordered_list</td>
    <td>block_id, items[]</td>
    <td>Safe list item render.</td>
  </tr>
  <tr>
    <td>code</td>
    <td>block_id, code_text, language nullable</td>
    <td>Text-only code block; no execution.</td>
  </tr>
  <tr>
    <td>callout</td>
    <td>block_id, tone, title nullable, text</td>
    <td>Note/warning/decision panel.</td>
  </tr>
  <tr>
    <td>divider</td>
    <td>block_id</td>
    <td>Section separator.</td>
  </tr>
</table>

# 10. Validation, Hata, Concurrency ve Recovery Contract

<table>
  <tr>
    <th>Kontrol / hata</th>
    <th>Kural</th>
    <th>UI recovery / API etkisi</th>
  </tr>
  <tr>
    <td>MANUAL_TITLE_REQUIRED</td>
    <td>Title boş veya only-whitespace olamaz.</td>
    <td>Composer açık kalır; title alanı hata statei; text korunur.</td>
  </tr>
  <tr>
    <td>MANUAL_CONTENT_REQUIRED</td>
    <td>Normalized contentte en az bir visible text block zorunlu.</td>
    <td>Textarea hata statei; stream değişmez.</td>
  </tr>
  <tr>
    <td>MANUAL_FILE_TYPE_UNSUPPORTED</td>
    <td>Yalnız TXT/MD/HTML.</td>
    <td>File reject; reader korunur.</td>
  </tr>
  <tr>
    <td>MANUAL_SOURCE_ENCODING_INVALID</td>
    <td>UTF-8 normalize edilemeyen source publish edilmez.</td>
    <td>Encoding guidance göster; raw source retention policyye göre quarantine/stagingde kalabilir.</td>
  </tr>
  <tr>
    <td>MANUAL_PARSE_FAILED</td>
    <td>Markdown/HTML canonical blocks üretmiyor veya allowlist ihlali var.</td>
    <td>No publication; error + retry with supported text.</td>
  </tr>
  <tr>
    <td>MANUAL_DUPLICATE_CONTENT</td>
    <td>Aynı normalized checksum active streamde mevcut.</td>
    <td>Warning; default append block. Explicit override varsa Admin audit ile ayrı decision.</td>
  </tr>
  <tr>
    <td>ADMIN_MANUAL_WRITE_REQUIRED</td>
    <td>Actor Admin değil.</td>
    <td>403; input state korunabilir fakat mutation oluşmaz.</td>
  </tr>
  <tr>
    <td>BASELINE_MANUAL_IMMUTABLE</td>
    <td>is_baseline=true document için delete/normal replace UI akışı yasak.</td>
    <td>403/409 semantics; baseline readerda kalır. Release/migration only.</td>
  </tr>
  <tr>
    <td>MANUAL_REVISION_CONFLICT</td>
    <td>expected_head_revision_id stale; HTTP transport If-Match/ETag mismatched.</td>
    <td>409/412; latest revision fetch, compare/retry veya new revision workflow.</td>
  </tr>
  <tr>
    <td>MANUAL_STREAM_CONFLICT</td>
    <td>Expected stream_version stale.</td>
    <td>409/412; reader refetch; append/delete intent user confirmation ile retry.</td>
  </tr>
  <tr>
    <td>UPLOAD_JOB_FAILED</td>
    <td>Source upload/parse/index pipeline teknik olarak başarısız.</td>
    <td>Persistent failure correlation id; retry action; no phantom manual section.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Recovery principle<br/>Başarısız command sonrası existing reader stream bozulmaz. Frontend başarısız upload veya append için local UIya geçici sahte document eklemez. Command response, correlation id, canonical error code ve retry-safe state döndürmelidir.</th>
  </tr>
</table>

# 11. Lifecycle, Audit, Trash ve Historical Integrity

<table>
  <tr>
    <th>İşlem</th>
    <th>Current reader/search etkisi</th>
    <th>Tarihsel / audit etkisi</th>
  </tr>
  <tr>
    <td>Append / publish</td>
    <td>Yeni document stream sonuna gelir; indexlenir.</td>
    <td>manual_document_published; revision Published olarak immutable korunur.</td>
  </tr>
  <tr>
    <td>Replace revision</td>
    <td>Aynı stream_positionda yeni visible revision görünür.</td>
    <td>Old revision Superseded; manual_document_revised.</td>
  </tr>
  <tr>
    <td>Soft delete</td>
    <td>Section/sidebar/searchten çıkar.</td>
    <td>Root soft_deleted; Trash snapshot; manual_document_soft_deleted.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>Deterministic original/near-original positionta yeniden görünür.</td>
    <td>Same root/revision chain; manual_document_restored + index job.</td>
  </tr>
  <tr>
    <td>Permanent purge</td>
    <td>Reader/searchte yok; retention sonrası source/content silinebilir.</td>
    <td>Admin-only Trash action; manual_document_purged; prior citation retention policy check.</td>
  </tr>
  <tr>
    <td>Baseline update</td>
    <td>Normal User Manual remove/replace UI dışındadır.</td>
    <td>System/release migration revision; audit/provenance belirtilir.</td>
  </tr>
</table>

Minimum audit payload: event_id, event_type, actor_principal_id/type, document_id, revision_id nullable, stream_entry_id nullable, prior_stream_version, resulting_stream_version, source_type, source_filename nullable, checksum, correlation_id, occurred_at. Mutation auditleri immutable olmalıdır.

<table>
  <tr>
    <th>Trash boundary<br/>Trash yalnız Admin tarafından görüntülenir, restore edilir veya permanently delete edilir. User Manual sayfasındaki Remove Document yalnız soft delete komutudur; Remove Document düğmesini görmek permanent delete hakkı vermez.</th>
  </tr>
</table>

# 12. Agent Tool/API Eşdeğeri

Agentın User Manual eşdeğeri UI click otomasyonu değildir. Agent internal Tool Gateway/API yoluyla Published manual corpusuna erişir. Aynı reader/search canonical block modelini kullanır; ancak Agentın mutasyon yetkisi yoktur.

<table>
  <tr>
    <th>Tool / API</th>
    <th>Input</th>
    <th>Output / sınır</th>
  </tr>
  <tr>
    <td>documentation.search</td>
    <td>query, scope=published_manual, cursor/limit</td>
    <td>document_id, revision_no, heading_path, excerpt, anchor, block_ids. Published-only.</td>
  </tr>
  <tr>
    <td>documentation.get_section</td>
    <td>document_id, revision_no, anchor</td>
    <td>Canonical blocks + source label + stream_version + citation metadata.</td>
  </tr>
  <tr>
    <td>artifact.attach_citation</td>
    <td>artifact_id, manual citation</td>
    <td>Provenance evidence ekler; manualı değiştirmez.</td>
  </tr>
  <tr>
    <td>Forbidden manual mutation tools</td>
    <td>append/upload/replace/delete/restore</td>
    <td>Agent için yoktur; Admin-only command endpoints exposed edilmez.</td>
  </tr>
</table>

UI capability parity ilkesi burada şu şekilde uygulanır: insanın gerçek read/search yeteneği ile Agent retrieval yeteneği aynı canonical Published content ve revision/anchor referansına bağlanır. Ancak write capability parity, Agent için policy tarafından bilinçli biçimde kapalıdır; Agent mutasyon amacıyla browser kullanamaz.

# 13. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Alan</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Persistence</td>
    <td>Document array localStorageda tutulur.</td>
    <td>PostgreSQL root/revision/stream metadata + object storage raw source + block/search projections.</td>
    <td>localStorage yalnız scroll/reader preference gibi transient UX için kullanılabilir.</td>
  </tr>
  <tr>
    <td>Append</td>
    <td>UI array push + rerender + scroll.</td>
    <td>Atomic root + Published revision + stream entry + publication/audit event + outbox index job.</td>
    <td>Yeni section committen önce readerda görünmez.</td>
  </tr>
  <tr>
    <td>Search</td>
    <td>Title/source/content substring, doc-level.</td>
    <td>Server-side full-text title/heading/chunk search; paged results/deep links.</td>
    <td>V18 interaction korunur, result semantics gelişir.</td>
  </tr>
  <tr>
    <td>Formatting</td>
    <td>Plaintext heuristic; source escaped.</td>
    <td>TXT/MD/HTML canonical blocks + safe renderer.</td>
    <td>Raw HTML/Markdown direct injection yasaktır.</td>
  </tr>
  <tr>
    <td>Delete</td>
    <td>Generic owner helper ile arrayden çıkarıp Trash callback.</td>
    <td>Admin-only soft delete; baseline immutable; snapshot + stream/index update.</td>
    <td>V18 generic owner rule override edilmez.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>Prototype callback documenti end/near original list positionına ekleyebilir.</td>
    <td>Deterministic original relative position algorithm + stream transaction.</td>
    <td>“Always append to end” canonical değildir.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>V18de visible Agent path tanımlı değil.</td>
    <td>Internal documentation retrieval API + citation provenance.</td>
    <td>Agent UI readera bağımlı değildir.</td>
  </tr>
</table>

# 14. Kodcu AI İçin Implementation Rules

- Manual contenti tek bir append-only TEXT blob olarak saklama. manual_document, manual_document_revision, manual_stream_entry, manual_content_block ve manual_search_chunk ayrımını uygula.

- Built-in baseline guide için is_baseline=true sakla; normal User Manual UI delete, move veya replace komutları baselineı mutate etmesin. Baseline update yalnız system release/migration workflowudur.

- Reader ve sidebarı tek stream_version snapshot üzerinden render et. Aynı request içinde baselinelı ve appended sections farklı snapshotlardan gelmesin.

- Append order için created_at sıralaması kullanma. Active stream entrylere transaction altında unique stream_position ata; revision değişiminde positionı koru.

- Add/Paste ve Upload akışlarını ayrı persistence modellerine bölme. Her ikisini normalized block, validation, publication event, audit ve index pipelineına sok.

- TXT, Markdown ve allowlisted HTML dışında upload kabul etme. PDF, DOCX, image veya OCR ingestion Production V1 User Manual pipelineına sokma.

- Raw HTML, raw Markdown veya user-supplied filenameı doğrudan innerHTML / executable content olarak render etme. Canonical block renderer kullan.

- Published Manual read/search endpointlerini tüm roller ve Agent internal principal için erişilebilir yap; write/upload/revise/delete/restore endpointlerini Admin server policy ile koru.

- Search resultında yalnız document id dönme. revision_no, heading_path, excerpt, anchor, block_ids ve stream_version dön; stale anchor recovery uygula.

- Every create/upload/delete/restore command idempotency_key kullanmalı; stream/revision mutasyonlarında explicit concurrency precondition uygulanmalıdır.

- Soft-deleted documents reader/search projectionından çıkarılmalı; prior Agent citationlar için revision/block snapshotları retention boyunca resolve edilebilir kalmalıdır.

- User Manual contenti runtime authorization veya package classification kaynağı sayma. Domain validation için ilgili authoritative servicei çağır.

- Frontend local state, FileReader sonucu, browser cache veya menu visibility authoritative persistence/authorization olarak kullanılmamalıdır.

- Search indexing eventual consistency gösterebilir; fakat stream publication transactionı başarısızsa readerda sahte bölüm görünmemelidir.

- Agenta manual mutasyon endpointi, human session impersonation veya UI automation yolu verme. Agent yalnız internal retrieval ve citation capabilitylerini kullanır.

# 15. Acceptance Tests

<table>
  <tr>
    <th>ID</th>
    <th>Senaryo</th>
    <th>Beklenen sonuç</th>
  </tr>
  <tr>
    <td>UM-01</td>
    <td>User User Manualı açar.</td>
    <td>Baseline guide ve tüm Published appended sections tek continuous streamde görünür.</td>
  </tr>
  <tr>
    <td>UM-02</td>
    <td>Supervisor “allocation” arar.</td>
    <td>Published manual chunk result, excerpt, heading path ve doğru section anchor döner.</td>
  </tr>
  <tr>
    <td>UM-03</td>
    <td>Agent internal retrieval ile “available time” sorgular.</td>
    <td>Published revision + canonical blocks + revision/anchor/block citation döner; UI gerekmez.</td>
  </tr>
  <tr>
    <td>UM-04</td>
    <td>Admin geçerli title/content ile pasted text ekler.</td>
    <td>Root, Published revision, stream entry, audit event atomik oluşur; UI yeni anchora scroll eder.</td>
  </tr>
  <tr>
    <td>UM-05</td>
    <td>Admin valid .md yükler.</td>
    <td>Markdown heading/list/code/callout canonical blocksına dönüşür; reader safe render eder.</td>
  </tr>
  <tr>
    <td>UM-06</td>
    <td>Admin PDF/DOCX/image upload eder.</td>
    <td>MANUAL_FILE_TYPE_UNSUPPORTED; stream değişmez.</td>
  </tr>
  <tr>
    <td>UM-07</td>
    <td>Supervisor add/upload endpointini çağırır.</td>
    <td>ADMIN_MANUAL_WRITE_REQUIRED; revision, stream entry ve audit mutation oluşmaz.</td>
  </tr>
  <tr>
    <td>UM-08</td>
    <td>Admin appended documenti soft delete eder.</td>
    <td>Reader/sidebar/searchten çıkar; Trash snapshot + manual_document_soft_deleted audit oluşur.</td>
  </tr>
  <tr>
    <td>UM-09</td>
    <td>Admin Trash üzerinden restore eder.</td>
    <td>Same root/revision chain deterministic stream positionta döner; index job/audit tetiklenir.</td>
  </tr>
  <tr>
    <td>UM-10</td>
    <td>Admin baselineı silmeye çalışır.</td>
    <td>BASELINE_MANUAL_IMMUTABLE; baseline görünmeye devam eder.</td>
  </tr>
  <tr>
    <td>UM-11</td>
    <td>Admin document revision v2 publish eder.</td>
    <td>stream_position değişmez; v1 Superseded olur; reader v2yi gösterir.</td>
  </tr>
  <tr>
    <td>UM-12</td>
    <td>Agent artifacti soft-deleted revisiona citation taşır.</td>
    <td>Artifact viewer retention süresince cited revision/block snapshotını resolve eder.</td>
  </tr>
  <tr>
    <td>UM-13</td>
    <td>İki Admin eşzamanlı append başlatır.</td>
    <td>Transaction/unique position sayesinde two deterministic positions; no duplicate side effect.</td>
  </tr>
  <tr>
    <td>UM-14</td>
    <td>Search index job gecikir.</td>
    <td>Reader published documenti gösterir; Search index updating note; data loss yok.</td>
  </tr>
  <tr>
    <td>UM-15</td>
    <td>Stale stream versionla delete istenir.</td>
    <td>MANUAL_STREAM_CONFLICT; UI latest stream ile rehydrate edilir; accidental delete olmaz.</td>
  </tr>
  <tr>
    <td>UM-16</td>
    <td>V18 client-side role flag manipulate edilir.</td>
    <td>Server Admin policy dışı mutationı reddeder.</td>
  </tr>
  <tr>
    <td>UM-17</td>
    <td>Upload parse fail olur.</td>
    <td>No phantom reader section; source/correlation error trace korunur; retry possible.</td>
  </tr>
  <tr>
    <td>UM-18</td>
    <td>Result list item stale anchora gider.</td>
    <td>Client refetch + anchor retry; bulunamazsa precise unavailable message.</td>
  </tr>
</table>

# 16. Final Consistency Check

<table>
  <tr>
    <th>Kontrol noktası</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Master authority</td>
    <td>Modül 17 read/search/write/root-revision-stream/Agent/Trash/audit kararları uygulanmıştır.</td>
  </tr>
  <tr>
    <td>V18 vs Production ayrımı</td>
    <td>localStorage, FileReader array mutation, generic owner delete, doc-level substring ve raw content heuristic canonical davranış olarak taşınmamıştır.</td>
  </tr>
  <tr>
    <td>Roles</td>
    <td>Published manual all-role read/search; Admin-only append/upload/revise/delete/restore; Agent internal API only.</td>
  </tr>
  <tr>
    <td>Baseline</td>
    <td>Baseline first; UI delete yok; release/migration lifecycle.</td>
  </tr>
  <tr>
    <td>Revision &amp; position</td>
    <td>Immutable revisions; stable stream position; deterministic restore.</td>
  </tr>
  <tr>
    <td>Search</td>
    <td>Server-side title/heading/content chunk search, excerpt, anchor, stream_version.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Citation-aware retrieval; no UI dependency; no mutation tool.</td>
  </tr>
  <tr>
    <td>Trash / audit</td>
    <td>Soft delete, restore, purge boundary; historical citations preserved under retention.</td>
  </tr>
  <tr>
    <td>Future Dev boundary</td>
    <td>PDF/DOCX/OCR, WYSIWYG, community editing, custom visibility ve interactive scripts active Production V1 değildir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Master Technical Reference tutarlılık sonucu<br/>User Manual Production V1 sözleşmesi: baseline first; Admin-only write; all-role Published read/search; Agent internal retrieval only; text formats only; canonical safe blocks; immutable revisions; stable stream positions; server-side search; soft delete + audit. Bu kurallar birlikte uygulanmadan User Manual production-ready kabul edilmez.</th>
  </tr>
</table>
