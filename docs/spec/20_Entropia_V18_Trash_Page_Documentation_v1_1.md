---
title: "Entropia V18 — Trash Page Documentation v1.1"
page_number: 20
document_type: "Page implementation specification"
source_document: "Entropia_V18_Trash_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Trash Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18
> **Original DOCX footer:** ENTROPIA V18 | Trash | Sayfa Dokümantasyonu 20/22 | Production V1 uygulama sözleşmesi

ENTROPIA V18

TRASH

Sayfa Dokümantasyonu 20/22 | Admin-only soft delete, restore, purge ve kanıt koruma sözleşmesi

# 0. Document Control, Scope ve Source Traceability

Bu belge yalnız Panel > Trash yüzünü ve bu yüzün Production V1 soft delete, restore, purge, audit ve dependency davranışını tanımlar. Trash; günlük çalışma nesnesi üretme, Strategy düzenleme veya Data yönetme ekranı değildir. Aktif alanlardan kaldırılmış business root nesneleri için Admin kontrollü geri alma ve kalıcı arındırma yüzüdür. Strategy, Package, Dataset, Backtest Result, Rationale Family, Analysis Lab output ve User Manual segmentlerinin kendi alanlarına ait ayrıntılı düzenleme davranışları bu belge kapsamına girmez; burada yalnız Trash lifecycle etkileri tanımlanır.

<table>
  <tr>
    <th>Canonical Production V1 kararı. Normal silme fiziksel silme değildir. Başarılı delete transactionı aynı anda root lifecycle_state = soft_deleted, Trash Entry, append-only audit event ve outbox event üretmelidir. Trash listesi, restore ve purge yalnız authenticated human Admin tarafından kullanılabilir. UI menüsünün gizli olması veya V18 client-side role statei server-side authorization yerine geçmez.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Kaynak / tür</th>
    <th>İlgili bölüm</th>
    <th>Bu sayfada kullanım amacı</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0</td>
    <td>Modül 3 §§1-14; Canonical Integration</td>
    <td>Soft delete, Trash Entry, restore, purge, root/revision korunumu, dependency preflight, audit/outbox, hata kodları ve acceptance kuralları.</td>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0</td>
    <td>Modül 1 §§5-11; Modül 2 §§2-11; Modül 16; Modül 17; Modül 19-20</td>
    <td>Admin-only role policy; Agent principal ayrımı; root/revision/provenance; Panel navigation; User Manual segment restore; API, job/worker, outbox ve transaction ilkeleri.</td>
  </tr>
  <tr>
    <td>V18 ana HTML</td>
    <td>`trashMenuItem`; `showTrash`; `renderTrashPage`; `addTrashEntry`; `restoreTrashItem`; `permanentlyDeleteTrashItem`; `deletedItems`; `trashAuditLog`</td>
    <td>Gerçek prototype menu visibility, toolbar, table, snapshot, action labels, empty-state metni, confirmation ve local-array demo davranışı.</td>
  </tr>
  <tr>
    <td>Sayfa Bazlı Dokümantasyon Handoff v1.1</td>
    <td>§§2-6; Field/Interaction/Content/Command matrisleri</td>
    <td>Kaynak üstünlüğü; V18/Production ayrımı; field requiredness; content catalog; lifecycle; Agent parity; implementation rules; acceptance tests.</td>
  </tr>
  <tr>
    <td>2.3. POSITION ENTRY LOGIC örnek dokümanı</td>
    <td>Anlatım derinliği referansı</td>
    <td>Kavramları ilk kullanımda canonical açıklama, dependency sonucu, backend trace ve test edilebilir kesin uygulama dili.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam içi</th>
    <th>Kapsam dışı / yalnız çapraz referans</th>
  </tr>
  <tr>
    <td>Trash navigation; Admin gate; search/type filter; snapshot reader; deleted-object table; restore action; permanent delete/purge action; purge job states; audit/outbox; error/recovery; historical manifest bütünlüğü; type-specific deletion/restore consequences.</td>
    <td>Object-specific editor alanları; normal delete buttons of Mainboard/Package/Data pages; Rationale Family repair formu; Backtest Run cancellation; Agent task pause/stop; physical storage vendor seçimi; login/MFA implementation; generic Logs page ayrıntısı.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kavramsal Terimler

Trash, bir nesnenin ekrandan kaldırılması ile tarihsel anlamının yok edilmesini birbirinden ayırır. Bir Strategy, Package veya Dataset aktif seçicilerden çıkabilir; ancak önceki Backtest Run manifestleri, Result artifactleri, Agent checkpoint bağlantıları ve audit zinciri korunur. Bu nedenle Trash sayfası yalnız bir geri dönüşüm alanı değil, Entropia tekrar üretilebilirlik modelinin yönetimsel yüzüdür.

<table>
  <tr>
    <th>Terim</th>
    <th>Canonical kısa tanım</th>
    <th>Trash sayfasındaki uygulama sonucu</th>
  </tr>
  <tr>
    <td>Business root / root identity</td>
    <td>Bir çalışma nesnesinin kalıcı ana kimliği; immutable revisionlardan ayrıdır.</td>
    <td>Restore aynı entity_idyi yeniden active yapar; yeni root oluşturmaz.</td>
  </tr>
  <tr>
    <td>Deletion lifecycle</td>
    <td>Domain lifecycledan ayrı, silme durumunu taşıyan state makinesi.</td>
    <td>Draft/Approved/Deprecated gibi domain state restore sonrasında korunur; deletion state ayrı değişir.</td>
  </tr>
  <tr>
    <td>Soft Delete</td>
    <td>Business rootu fiziksel olarak yok etmeden aktif kullanım ve yeni seçimlerden çekme işlemi.</td>
    <td>Root soft_deleted olur; Trash Entry, audit ve outbox yaratılır.</td>
  </tr>
  <tr>
    <td>Trash Entry</td>
    <td>Admin Trash görünümü için silinmiş rootu tanımlayan kayıt.</td>
    <td>Original location, owner, deleted by/time, snapshot, dependency summary, restore data ve purge status taşır.</td>
  </tr>
  <tr>
    <td>Deletion Snapshot</td>
    <td>Silme anındaki metadata, revision pointer, görünür ad, location ve dependency bilgisinin immutable kopyası.</td>
    <td>Canlı nesne/metadata sonradan değişse bile Admin silme bağlamını okuyabilir.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>Soft-deleted rootu önceki active bağlamına geri alma transactionı.</td>
    <td>Same root identity + same current_revision_id; yeni revision yok; historical run/result değişmez.</td>
  </tr>
  <tr>
    <td>Purge</td>
    <td>Soft-deleted payload, object artifactleri ve türev projectionları retention politikasına göre kontrollü arındırma işi.</td>
    <td>Admin başlatır; worker asenkron yürütür; purge pending iken restore kapalıdır.</td>
  </tr>
  <tr>
    <td>Tombstone</td>
    <td>Purge sonrasında minimum identity ve audit bağlantısı için korunmuş kayıt.</td>
    <td>Purged nesne ACTIVEye dönemez; gerekirse yeni root oluşturulur.</td>
  </tr>
  <tr>
    <td>Audit Event</td>
    <td>Actor, action, target, before/after summary, time ve correlation taşıyan append-only kanıt olayı.</td>
    <td>Delete, restore, purge-request, purge-complete ve purge-failed olayları silinmez.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Domain sınırı. Trash bir revision editoru değildir. Restore, silinmeden önceki revision pointerı döndürür; draft/approval/validation stateini yeniden yazmaz. Purge de geçmiş Result veya Runı yeni inputlarla tekrar üretmez. Tüm tarihsel yorum pinned manifest ve immutable artifactler üzerinden okunur.</th>
  </tr>
</table>

# 2. Erişim, Görünürlük ve Server-side Policy

V18 HTMLde `trashMenuItem`, `canManageRoles()` true olduğunda görünür; bu demo kuralı fiilen Admin roleuna bağlıdır. Production V1de Trash erişimi tek bir Admin-only policy ile uygulanır. Admin olup olmadığı request bodydeki role stringinden değil authenticated human session/principal contextinden çözülür.

<table>
  <tr>
    <th>Actor</th>
    <th>V18 Trash davranışı</th>
    <th>Production V1 policy</th>
    <th>Server-side sonuç</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Panel/Trash menu hidden; doğrudan showTrash çağrısı “Admin access required.” metni döndürebilir.</td>
    <td>No access.</td>
    <td>401 unauthenticated veya public route dışında denial.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Trash menu hidden; normal own-object delete sonucu kendi aktif listesinden kaybolur.</td>
    <td>Trash list/view/restore/purge yok.</td>
    <td>403 `TRASH_ACCESS_FORBIDDEN`.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Panel demo görünürlüğü olsa bile Trash item hidden.</td>
    <td>Trash list/view/restore/purge yok.</td>
    <td>403 `TRASH_ACCESS_FORBIDDEN`.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Trash menu visible; V18 table, snapshot, Restore ve Permanent Delete actionları kullanılabilir.</td>
    <td>Full Trash access; list/detail/restore/purge request; all resource types üzerinde policy preflight.</td>
    <td>Admin guard + target lifecycle + expected_head_revision_id + retention/dependency validation.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Trash menu hidden; Agent kendi outputunu soft delete edebilir ama Trash kullanamaz.</td>
    <td>No Trash UI/tool access. Agent normal entity.soft_delete commandini yalnız own outputlar için kullanabilir.</td>
    <td>403 `TRASH_ACCESS_FORBIDDEN`; Agent runtime loopu silme eylemi nedeniyle durmaz.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Derived Rule. Rationale Families global shared-editing exceptiondır; bu istisna yalnız aktif Family/Assignment create-edit-remove kapsamındadır. Trash restore ve purge yetkisini genişletmez. Bir User veya Agent ortak Familyyi soft delete edebilse bile Trashta restore/purge yalnız Admin tarafından yapılır.</th>
  </tr>
</table>

# 3. V18 Interface Behavior: Gerçek Görünür Arayüz Envanteri

V18de Trash, Panel dropdown altındaki `Trash` itemiyle workspace içinde `PANEL / TRASH` başlığı altında render edilir. Ayrı bir route, modal veya popup yoktur. `deletedItems` ve `trashAuditLog` browser memory arrayleridir; `renderTrashPage()` tabloyu bu local state üzerinden yeniden üretir. Bu davranış yalnız prototype interaction referansıdır.

## 3.1 Navigation, bilgi bandı ve toolbar

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 görünümü / default</th>
    <th>Etkileşim</th>
    <th>Production V1 anlamı</th>
  </tr>
  <tr>
    <td>Panel &gt; Trash menu item</td>
    <td>`trashMenuItem`; default hidden unless V18 current role Admin.</td>
    <td>Click -&gt; `showTrash(event)`.</td>
    <td>Admin-only route/menu projection; direct URL/API guard ayrıca zorunlu.</td>
  </tr>
  <tr>
    <td>Page title</td>
    <td>`PANEL / TRASH`.</td>
    <td>Trash page açıldığında workspace title olarak görünür.</td>
    <td>Read-only page heading; no mutation.</td>
  </tr>
  <tr>
    <td>Intro band</td>
    <td>“Trash is Admin-only. Every normal deletion is a soft delete...” metni görünür.</td>
    <td>Read-only explanatory block.</td>
    <td>Canonical lifecycle/help copy; Productionda exact text aşağıdaki Content Catalogdan gelir.</td>
  </tr>
  <tr>
    <td>Search input</td>
    <td>Placeholder: `Search deleted objects, locations or actors`; default empty.</td>
    <td>`oninput` search statei günceller, visible rows anında rerender edilir.</td>
    <td>Debounced query parameter; server-side filtered cursor list. Search optional, never a destructive filter.</td>
  </tr>
  <tr>
    <td>Type filter</td>
    <td>Select; default `All types`; diğer seçenekler deletedItems içindeki object type valuesinden dinamik gelir.</td>
    <td>Change -&gt; visible rows type equality ile filtrelenir.</td>
    <td>Canonical object_type enum/projection valuesi; untrusted free-text type kabul edilmez.</td>
  </tr>
  <tr>
    <td>Status detail</td>
    <td>`N recoverable object(s) · M audit event(s)` metni.</td>
    <td>Current local array counts.</td>
    <td>Server summary: recoverable count + matching/total count + latest projection timestamp; audit total ayrı endpoint/summary olabilir.</td>
  </tr>
</table>

## 3.2 Snapshot panel, table ve empty state

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 görünümü</th>
    <th>V18 davranışı</th>
    <th>Production V1 karşılığı</th>
  </tr>
  <tr>
    <td>Snapshot panel</td>
    <td>Varsayılan hidden; `Open Snapshot` sonrası üstte `Snapshot: {name}` ve JSON `&lt;pre&gt;` görünür.</td>
    <td>Selected snapshotIndex browser stateinde tutulur.</td>
    <td>Server detail query ile redacted structured deletion snapshot + dependency snapshot. Seçim URL query veya drawer stateinde tutulabilir; no secret/raw credential render.</td>
  </tr>
  <tr>
    <td>Trash table</td>
    <td>Visible entries varsa database-table görünür.</td>
    <td>Headers: Object, Type, Original Location, Original Owner, Deleted By, Deleted At, Dependencies, Status, Actions.</td>
    <td>Cursor-paginated read projection. Tabloda immutable snapshot fields ve current purge status açıkça ayrılır.</td>
  </tr>
  <tr>
    <td>Status pill</td>
    <td>V18 kayıt default `Soft Deleted`; CSS class `deleted`.</td>
    <td>Read-only label.</td>
    <td>UI label: Soft Deleted / Purge Pending / Purge Failed / Purged. API canonical enum lowercase snake_case olur.</td>
  </tr>
  <tr>
    <td>Action row</td>
    <td>Open Snapshot, Restore, Permanent Delete.</td>
    <td>Restore local callback çağırır; Permanent Delete browser confirm sonrası arrayden çıkarır.</td>
    <td>Her action server commanddir; disabled/loading/success/error/retry state zorunludur.</td>
  </tr>
  <tr>
    <td>Empty state</td>
    <td>“No deleted object matches the current filter...” metni.</td>
    <td>Filter sonucu boşsa görünür.</td>
    <td>Empty state ile access error, loading error ve no-more-pages durumu birbirinden ayrılır.</td>
  </tr>
</table>

## 3.3 V18de oluşan Trash Entry kaynakları

<table>
  <tr>
    <th>V18 kaynak yüz</th>
    <th>V18 object type</th>
    <th>V18 original location / snapshot davranışı</th>
    <th>Production note</th>
  </tr>
  <tr>
    <td>Mainboard Strategy row</td>
    <td>Strategy</td>
    <td>`Mainboard / Strategies`; item display name; dependency summary result snapshots intact.</td>
    <td>Canonical `MainboardWorkingItem.item_kind = strategy`; active Runs/jobs delete preflightte ayrıca kontrol edilir.</td>
  </tr>
  <tr>
    <td>Mainboard Trading Signal row</td>
    <td>Trading Signal</td>
    <td>`Mainboard / Trading Signals`; Mainboard geri dönüş callbacki.</td>
    <td>Package değildir; external Mainboard Working Item root olarak restore edilir.</td>
  </tr>
  <tr>
    <td>Mainboard Trade Log row</td>
    <td>Trade Log</td>
    <td>`Mainboard / Trade Logs`; historical result summary korunur.</td>
    <td>Package değildir; imported file summary/provenance retained policy uygulanır.</td>
  </tr>
  <tr>
    <td>Results card</td>
    <td>Backtest Result</td>
    <td>`Mainboard / Backtest Results`; V18 UI card callbacki.</td>
    <td>Result soft delete historical Run manifestini değiştirmez; Result root/data retention policy ayrı uygulanır.</td>
  </tr>
  <tr>
    <td>Package Library</td>
    <td>Package</td>
    <td>`Package Library / {type}`; package + metadata snapshot.</td>
    <td>Package root new selectorsdan çıkar; prior Strategy Revision/Run pinli revisionla okunur.</td>
  </tr>
  <tr>
    <td>Rationale Families</td>
    <td>Rationale Family</td>
    <td>`Edit / Rationale Families`; family object snapshot.</td>
    <td>Active assignment varsa delete preflight block/repair plan ister; dangling assignment kabul edilmez.</td>
  </tr>
  <tr>
    <td>User Manual</td>
    <td>User Manual Document</td>
    <td>`Help / User Manual`; document snapshot.</td>
    <td>Restore stable sequence key ile continuous manual akışına geri döner.</td>
  </tr>
</table>

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen / state</th>
    <th>Visible / enable koşulu</th>
    <th>UI davranışı</th>
    <th>Payload / engine / lifecycle etkisi</th>
  </tr>
  <tr>
    <td>Page loading</td>
    <td>Admin route açılırken.</td>
    <td>Skeleton/table loading state; stale previous data destructive action için kullanılmaz.</td>
    <td>GET trash entries query; state source backend projection.</td>
  </tr>
  <tr>
    <td>Access denied</td>
    <td>Admin olmayan caller.</td>
    <td>Generic page error; Trash kayıt adı/sayısı sızdırılmaz.</td>
    <td>No list/detail/restore/purge command; 401/403.</td>
  </tr>
  <tr>
    <td>Normal list</td>
    <td>Admin + page has query result.</td>
    <td>Table, toolbar ve action rows visible.</td>
    <td>All roots remain soft_deleted unless current status purge_pending/purged.</td>
  </tr>
  <tr>
    <td>Filtered empty</td>
    <td>Admin; query returned zero rows.</td>
    <td>Exact empty-state message; filter controls remain enabled.</td>
    <td>No mutation; does not prove Trash globally empty.</td>
  </tr>
  <tr>
    <td>Snapshot closed</td>
    <td>Default.</td>
    <td>No snapshot panel.</td>
    <td>No extra detail fetch until Open Snapshot command/query.</td>
  </tr>
  <tr>
    <td>Snapshot loading / open</td>
    <td>Admin selects row.</td>
    <td>Inline panel or right drawer loading then redacted snapshot.</td>
    <td>GET trash-entry detail; no root reactivation.</td>
  </tr>
  <tr>
    <td>Restore ready</td>
    <td>Entry records object_lifecycle_snapshot=soft_deleted; restore preflight has no blocker.</td>
    <td>Restore enabled.</td>
    <td>Target root can return to active with same revision pointer.</td>
  </tr>
  <tr>
    <td>Restore blocked</td>
    <td>Dependency/location/name/policy conflict.</td>
    <td>Restore disabled or command returns actionable conflict card.</td>
    <td>Root remains soft_deleted; no partial restore.</td>
  </tr>
  <tr>
    <td>Restore loading</td>
    <td>Admin sends restore command.</td>
    <td>Selected row actions disabled; spinner; duplicate click prevented.</td>
    <td>Expected deletion version + idempotency; atomic transaction.</td>
  </tr>
  <tr>
    <td>Purge confirmation</td>
    <td>Admin chooses Permanent Delete.</td>
    <td>Second explicit confirmation; target name/type shown; re-auth step invoked.</td>
    <td>No purge until confirmation/re-auth token accepted.</td>
  </tr>
  <tr>
    <td>Purge pending</td>
    <td>Command accepted; worker has not completed.</td>
    <td>Status pill `Purge Pending`; Restore disabled; action shows View job / Refresh.</td>
    <td>Root lifecycle_state remains soft_deleted; trash_entry.purge_status=pending.</td>
  </tr>
  <tr>
    <td>Purge failed</td>
    <td>Worker/retention recheck fails.</td>
    <td>Status `Purge Failed`; detail error and Retry eligibility.</td>
    <td>Root returns/remains soft_deleted; audit error + job trace retained.</td>
  </tr>
  <tr>
    <td>Purged / tombstone</td>
    <td>Worker completes.</td>
    <td>Default list may hide completed purged records; historical audit link can remain.</td>
    <td>Root purged/tombstoned; restore data removed; cannot return active.</td>
  </tr>
</table>

# 5. Field Contract Matrix: Alanlar, Varsayılanlar, Zorunluluk ve Dependency

Trash sayfasında kullanıcı tarafından doldurulan yalnız iki filter alanı vardır. Restore ve purge actionları field formu değil command başlatıcılarıdır. Bu nedenle yıldız (*) ile zorunlu işaretlenecek bir normal input yoktur. Permanent Delete için ikinci explicit confirmation ve Admin re-authentication koşullu zorunluluktur; bunlar action-level requiredness olarak gösterilir.

<table>
  <tr>
    <th>Alan</th>
    <th>UI tipi / V18 default</th>
    <th>Zorunluluk</th>
    <th>Seçenek / bağımlılık</th>
    <th>Production payload ve validation</th>
  </tr>
  <tr>
    <td>Search deleted objects, locations or actors</td>
    <td>Text input; default empty; placeholder exact V18 text.</td>
    <td>Optional.</td>
    <td>Search haystack: display name, type, original location, owner, deleted by, dependency summary.</td>
    <td>`q?: string`; trimmed, max-length/rate safe, server-side full-text/index query. Client filtering as authoritative source yasak.</td>
  </tr>
  <tr>
    <td>Object Type</td>
    <td>Dropdown; default `All types`.</td>
    <td>Optional.</td>
    <td>`All types` + server-returned supported trash object_type values. V18 dynamic array values.</td>
    <td>`object_type?: enum`; unknown value -&gt; 422 `INVALID_TRASH_OBJECT_TYPE`. No free-text object type injection.</td>
  </tr>
  <tr>
    <td>Snapshot selection</td>
    <td>Action-driven; default none.</td>
    <td>Optional.</td>
    <td>Only currently authorized Admin-selected entry.</td>
    <td>`GET /trash-entries/{id}`; id must be list/detail policy authorized. Snapshot redaction/size policy applies.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>Button; enabled only when entry restore-eligible.</td>
    <td>Action requiredness: Admin + `soft_deleted` + preflight allow.</td>
    <td>Expected deletion version; dependency/location conflict may block.</td>
    <td>`POST /trash-entries/{id}/restore`; `expected_head_revision_id`, `idempotency_key`; 409/422 outcomes explicit.</td>
  </tr>
  <tr>
    <td>Permanent Delete</td>
    <td>Button; V18 direct confirm.</td>
    <td>Conditional requiredness: Admin + entry soft_deleted + second confirmation + re-auth token + purge eligibility.</td>
    <td>Restore must not be in progress; retention and dependency recheck required.</td>
    <td>`POST /trash-entries/{id}/purge`; `confirmation_phrase`, `reauth_proof`, `idempotency_key`; returns 202 job reference.</td>
  </tr>
  <tr>
    <td>Restore conflict choice</td>
    <td>Production conflict dialog only if domain adapter returns supported alternatives.</td>
    <td>Conditional requiredness only for a returned conflict resolution option.</td>
    <td>Examples: manual sequence insertion policy, domain-specific name/location conflict. Generic handler must not invent a fix.</td>
    <td>Typed `resolution` enum from preflight; unsupported/unknown -&gt; 422.</td>
  </tr>
  <tr>
    <td>Delete reason</td>
    <td>Not rendered on V18 Trash page; originates from delete command if source page supports it.</td>
    <td>Optional unless source domain policy makes it required.</td>
    <td>Captured at delete time, read-only in snapshot.</td>
    <td>`delete_reason?: string`; immutable audit/snapshot evidence; Trash Restore does not alter it.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Requiredness rule. A `*` marker is not used for Search or Object Type because neither is required to list Trash. The Production Permanent Delete confirmation modal must mark the confirmation phrase and re-authentication completion as required only after the Admin has selected Permanent Delete. The purge command must not be sent until both are valid.</th>
  </tr>
</table>

# 6. Information Content Catalog ve Nihai UI Metinleri

V18 Trash yüzünde bağımsız bir ⓘ düğmesi bulunmaz. Bu nedenle V18de field-level info popover yoktur. Production V1, V18 görünümünü koruyarak intro bandını ve confirmation içeriklerini canonical yardım metni olarak kullanır. Uygulamanın ortak page-help ⓘ componenti bu sayfada etkinleştirilirse aşağıdaki `trashPageInfo` içeriğini aynen göstermelidir; yeni bir domain kuralı üretmez.

<table>
  <tr>
    <th>UI key / alan</th>
    <th>Panel başlığı</th>
    <th>Nihai UI metni</th>
  </tr>
  <tr>
    <td>trashPageInfo (optional generic page ⓘ)</td>
    <td>About Trash</td>
    <td>Trash stores recoverable records created by normal soft delete actions. A deleted object is removed from active lists and new selectors, but its root identity, historical revisions, completed run references and audit evidence are retained. Only Admin can view Trash, restore an eligible object or request permanent deletion. Permanent deletion starts a controlled purge job; it is not an immediate local removal and cannot be undone.</td>
  </tr>
  <tr>
    <td>Trash intro band</td>
    <td>Trash is Admin-only</td>
    <td>Trash is Admin-only. Every normal deletion is a soft delete. Restoring preserves the object identity and original location whenever possible. Permanent Delete starts an irreversible, retention-checked purge. Historical runs, results and audit evidence are not rewritten.</td>
  </tr>
  <tr>
    <td>Snapshot help</td>
    <td>Deletion Snapshot</td>
    <td>This snapshot describes the object at the time it was deleted. It is evidence for review and restore preflight. It may contain redacted values and is not an editable copy of the object.</td>
  </tr>
  <tr>
    <td>Restore confirmation</td>
    <td>Restore deleted object</td>
    <td>Restore “{object_name}” to its prior active context? Restore keeps the same object identity and current revision pointer. It does not recreate historical runs or replace changes made to other objects after deletion.</td>
  </tr>
  <tr>
    <td>Restore conflict</td>
    <td>Restore needs attention</td>
    <td>This object cannot be restored automatically because: {conflict_summary}. Review the available domain-specific resolution options. No change has been applied; the object remains in Trash.</td>
  </tr>
  <tr>
    <td>Permanent delete confirmation</td>
    <td>Permanently delete recoverable object</td>
    <td>Permanently delete “{object_name}” ({object_type})? This starts an irreversible purge of eligible recoverable payloads. The object cannot be restored after purge. Audit evidence and a minimal tombstone remain. Enter the object name and complete Admin re-authentication to continue.</td>
  </tr>
  <tr>
    <td>Purge pending</td>
    <td>Purge requested</td>
    <td>Permanent deletion was requested. The object remains unavailable while retention and dependency checks run in the background. Restore is unavailable until this purge job finishes or fails.</td>
  </tr>
  <tr>
    <td>Purge failure</td>
    <td>Purge could not complete</td>
    <td>Permanent deletion did not complete. The object remains safely soft-deleted and recoverable. Review the retention or dependency reason, then retry only after the issue is resolved.</td>
  </tr>
  <tr>
    <td>Search placeholder</td>
    <td>Search deleted objects, locations or actors</td>
    <td>Search deleted objects, locations or actors</td>
  </tr>
  <tr>
    <td>Empty state</td>
    <td>No matching deleted objects</td>
    <td>No deleted object matches the current filter. Deleted Strategies, Trading Signals, Trade Logs, Packages, Rationale Families and manual documents appear here until an Admin restores or permanently deletes them.</td>
  </tr>
  <tr>
    <td>Access denied</td>
    <td>Admin access required</td>
    <td>Trash is available only to an authenticated Admin. No deleted-object details were loaded.</td>
  </tr>
  <tr>
    <td>List loading</td>
    <td>Loading deleted objects</td>
    <td>Loading deleted objects and recovery status...</td>
  </tr>
  <tr>
    <td>Restore success toast</td>
    <td>Object restored</td>
    <td>“{object_name}” was restored to its active context. Historical runs and audit evidence were not changed.</td>
  </tr>
  <tr>
    <td>Purge accepted toast</td>
    <td>Purge started</td>
    <td>Permanent deletion was requested for “{object_name}”. Track the purge status before leaving this page.</td>
  </tr>
  <tr>
    <td>Stale conflict toast</td>
    <td>Trash record changed</td>
    <td>This Trash record changed while you were reviewing it. Refresh the record and review the latest status before trying again.</td>
  </tr>
</table>

# 7. Button / Command / State Contract

<table>
  <tr>
    <th>Action</th>
    <th>Command / query</th>
    <th>Precondition and disabled state</th>
    <th>Success / error / retry / audit</th>
  </tr>
  <tr>
    <td>Open Snapshot</td>
    <td>GET trash-entry detail.</td>
    <td>Admin; entry remains visible in list; disabled while detail load active.</td>
    <td>Renders redacted immutable snapshot. 404/403 does not leak data. Query event may be logged as access audit according to observability policy, but does not mutate domain state.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>`trash.restore` command.</td>
    <td>Admin; root soft_deleted; expected deletion version matches; restore preflight ALLOW or supported resolution submitted. Disabled for purge_pending, purged, loading or conflicts without resolution.</td>
    <td>Atomic root ACTIVE + Trash Entry restored status + audit `trash.restored` + outbox `entity.restored`. UI receives canonical projection. Conflict/retry remains soft_deleted.</td>
  </tr>
  <tr>
    <td>Permanent Delete</td>
    <td>`trash.purge.request` command.</td>
    <td>Admin; root soft_deleted; explicit confirmation phrase + reauth proof; purge preflight eligible; no active duplicate job. Disabled for restore/loading/purge_pending/purged.</td>
    <td>Returns 202 with purge_job_id; root purge_pending, Trash Entry pending, audit `trash.purge_requested`, outbox event. Duplicate submit same idempotency key returns same job.</td>
  </tr>
  <tr>
    <td>Refresh status</td>
    <td>GET trash list/detail and GET purge job status.</td>
    <td>Admin; page or detail open.</td>
    <td>Rehydrates canonical server state. No optimistic terminal status inferred from client timer.</td>
  </tr>
  <tr>
    <td>Retry purge</td>
    <td>New `trash.purge.request` after prior failure, only if preflight now eligible.</td>
    <td>Admin; purge_status failed; root remains soft_deleted; new reauth/confirmation required.</td>
    <td>New job/correlation id; prior failed audit is retained, never overwritten.</td>
  </tr>
  <tr>
    <td>Close Snapshot</td>
    <td>Client state action only.</td>
    <td>Snapshot panel open.</td>
    <td>Removes selected detail from view; no backend mutation or audit.</td>
  </tr>
  <tr>
    <td>Filter Search / Type</td>
    <td>GET trash list with cursor/filter query.</td>
    <td>Admin; controls enabled after page load.</td>
    <td>UI preserves filter state across pagination/refresh. No audit mutation; list uses server policy.</td>
  </tr>
</table>

<table>
  <tr>
    <th>POST /v1/trash-entries/{trash_entry_id}/restore<br/>{ expected_head_revision_id, resolution?: { kind, value }, idempotency_key }<br/><br/>POST /v1/trash-entries/{trash_entry_id}/purge<br/>{ expected_head_revision_id, confirmation_phrase, reauth_proof, idempotency_key }<br/>-&gt; 202 { purge_job_id, trash_entry_id, root_lifecycle_state: &#x27;soft_deleted&#x27;, purge_status: &#x27;pending&#x27; }</th>
  </tr>
</table>

# 8. Kullanıcı Akışları

## 8.1 Başarılı normal delete -> Admin restore akışı

- Owner veya Admin kaynak sayfasında Delete/Remove niyetini başlatır. UI yalnız niyeti toplar; rootu local arrayden kalıcı olarak silmez.

- Backend actor policy, root active state, expected row/version, domain preflight, active job/assignment ve idempotency kontrolünü yürütür.

- Transaction içinde root soft_deleted olur; deletion snapshot + dependency snapshot, Trash Entry, audit event ve outbox event oluşur.

- Active list/selector/search projectionları outbox consumer ile güncellenir. Owner Trash görmez; Admin Trashta original owner, deleted by ve dependency summary ile kaydı görür.

- Admin Trashta filtreler, snapshotı inceler ve Restore seçer. Restore preflight geçerse aynı entity_id/current_revision_id ile root active olur; `trash.restored` audit ve `entity.restored` outbox event yazılır.

## 8.2 Restore conflict akışı

- Admin Restore seçer; backend root lifecycle_state, purge status, retained payload, location/name/sequence ve type-specific dependencyleri yeniden doğrular.

- Preflight conflict dönerse UI “Restore needs attention” panelini gösterir. Generic Trash handler silent repair yapmaz.

- Admin yalnız domain adapterın sunduğu typed resolutionı seçebilir. Resolution yoksa command başlatılamaz; root soft_deleted kalır.

- Yeni resolution ile retry aynı expected deletion version üzerinden yapılır. Record değişmişse stale conflict döner ve Admin canonical detaili yeniler.

## 8.3 Permanent Delete / Purge akışı

- Admin entrynin snapshotını ve dependency summarysini inceler, Permanent Delete seçer.

- UI target name/type içeren second confirmation modal açar. Admin object name confirmationını girer ve re-authentication tamamlar.

- Backend token, Admin policy, idempotency, expected deletion version ve initial retention eligibility kontrolünü yapar; successde root purge_pending, Trash Entry pending olur; 202 job reference döner.

- Purge worker dependency/retention kontrolünü job startında yeniden yapar. Uygunsa domain payload, object storage artifacts, search/cache/projection kayıtları policy sırasıyla arındırılır.

- Successde root purged/tombstone olur, Trash Entry completed, audit `trash.purge_completed`; failureda root soft_deleted kalır, Trash Entry failed, audit `trash.purge_failed` oluşur.

## 8.4 Permission, empty, network and stale recovery

<table>
  <tr>
    <th>Durum</th>
    <th>UI sonucu</th>
    <th>Recovery</th>
  </tr>
  <tr>
    <td>Non-Admin page/direct API attempt</td>
    <td>Admin access required; no row metadata or counts.</td>
    <td>Authenticate as Admin; no client role spoof recovery.</td>
  </tr>
  <tr>
    <td>No matching filter result</td>
    <td>Empty-state copy; toolbar remains active.</td>
    <td>Clear/change filter; this is not a global-empty assertion.</td>
  </tr>
  <tr>
    <td>Network lost during Restore/Purge request</td>
    <td>Unknown-result banner; action stays locked until idempotency lookup/refresh.</td>
    <td>Retry with same idempotency key or fetch command status; never submit a new blind duplicate.</td>
  </tr>
  <tr>
    <td>Expected deletion version stale</td>
    <td>“Trash record changed” toast; no mutation.</td>
    <td>Refresh detail/list and re-evaluate current lifecycle/purge status.</td>
  </tr>
  <tr>
    <td>Running job blocks original delete</td>
    <td>Source page delete preflight gives blocker; no Trash Entry exists.</td>
    <td>Wait/cancel through job-specific lifecycle flow; do not use Trash to bypass.</td>
  </tr>
  <tr>
    <td>Purge worker failure</td>
    <td>Soft-deleted entry remains visible with failure reason and retry eligibility.</td>
    <td>Resolve retention/dependency reason; start a new confirmed/reauthed purge request.</td>
  </tr>
</table>

# 9. Production Backend / Domain Model

# 9.1 State layers and lifecycle

Deletion lifecycle domain lifecycledan ayrı tutulur. Örnek: bir Market Dataset domain olarak `approved` olabilir, fakat deletion statei `soft_deleted` olduğunda yeni seçim listelerinden çıkar. Restore datasetin approvalını veya revisionını değiştirmez; yalnız deletion stateini activeye döndürür.

<table>
  <tr>
    <th>Katman</th>
    <th>Canonical fields / records</th>
    <th>Trash etkisi</th>
  </tr>
  <tr>
    <td>Root identity registry</td>
    <td>entity_id, entity_type, owner_principal_id, current_revision_id, root_lifecycle_state, deleted_at, deleted_by_principal_id, delete_reason, trash_entry_id.</td>
    <td>Active listten çekme/deletion state kontrolünün canonical kaynağıdır.</td>
  </tr>
  <tr>
    <td>Immutable revisions / manifests</td>
    <td>revision_id, version/content hash, pinned run manifest references.</td>
    <td>Soft delete ve restore revisionları mutate etmez; completed Runs/Results same pinned inputla okunur.</td>
  </tr>
  <tr>
    <td>Trash Entry</td>
    <td>trash_entry_id, entity_id/type, display name, original location, owner, deleted by/at/reason, deletion/dependency snapshots, restore context, purge_status, purge_job_id, correlation_id.</td>
    <td>Admin read projection ve recovery/purge denetimi için ayrı kalıcı kayıt.</td>
  </tr>
  <tr>
    <td>Audit Event</td>
    <td>event_id, kind, actor, target, before/after summary, timestamp, correlation_id, causation_event_id.</td>
    <td>Delete/restore/purge trace append-onlydir; purge sonrasında minimum evidence korunur.</td>
  </tr>
  <tr>
    <td>Outbox Event</td>
    <td>event type, entity/trash IDs, occurred_at, correlation, payload pointer.</td>
    <td>Search/cache/selector/Agent tool registry/Trash projection consumersına reliable downstream update taşır.</td>
  </tr>
  <tr>
    <td>Purge Job</td>
    <td>job_id, state, attempts, error, started/completed times, retention result.</td>
    <td>Asenkron irreversible cleanup; browser/session lifetimeına bağlı değildir.</td>
  </tr>
  <tr>
    <td>Tombstone</td>
    <td>minimum entity identity, purged_at/by, audit linkage, superseded_by optional.</td>
    <td>Purged record restore edilemez; old identity historical audit için kanıt olarak kalır.</td>
  </tr>
</table>

# 9.2 Deletion state machine

<table>
  <tr>
    <th>ACTIVE --soft_delete--&gt; soft_deleted --restore--&gt; ACTIVE<br/>soft_deleted --purge request--&gt; PURGE_PENDING --worker success--&gt; PURGED / TOMBSTONE<br/>PURGE_PENDING --worker failure--&gt; soft_deleted (purge_status = failed)<br/><br/>Forbidden: ACTIVE -&gt; PURGED direct; PURGE_PENDING -&gt; restore; PURGED -&gt; ACTIVE</th>
  </tr>
</table>

A soft-deleted root yeni revision oluşturamaz, yeni Backtestte seçilemez veya Agentın yeni input contextine bağlanamaz. Purged tombstone aynı root olarak restore edilemez. Aynı business content tekrar gerekirse yeni root oluşturulur; domain izin verirse eski tombstonea `superseded_by` bağı kaydedilir.

# 9.3 Delete, restore and purge command flow

<table>
  <tr>
    <th>Command</th>
    <th>Mandatory transaction / job behavior</th>
    <th>Audit/outbox</th>
  </tr>
  <tr>
    <td>entity.soft_delete</td>
    <td>Row lock; policy + lifecycle + domain preflight; if already soft deleted return same entry/idempotent response; snapshot creation; root state write; Trash Entry write.</td>
    <td>`entity.soft_deleted` audit and outbox in same transaction.</td>
  </tr>
  <tr>
    <td>trash.restore</td>
    <td>Admin guard; row lock; restore preflight; root active + original context projection; entry restored state. No new revision.</td>
    <td>`trash.restored` audit + `entity.restored` outbox in same transaction.</td>
  </tr>
  <tr>
    <td>trash.purge.request</td>
    <td>Admin guard; explicit confirmation/re-auth; root purge_pending + entry pending + job enqueue through outbox/queue.</td>
    <td>`trash.purge_requested` audit and outbox.</td>
  </tr>
  <tr>
    <td>purge worker</td>
    <td>Re-check retention/dependency; delete eligible payloads/artifacts/projections; tombstone root/entry final status.</td>
    <td>`trash.purge_completed` or `trash.purge_failed`; trace/correlation retained.</td>
  </tr>
</table>

# 10. Type-Specific Dependency, Restore ve Historical Integrity Rules

<table>
  <tr>
    <th>Object family</th>
    <th>Soft delete / restore rule</th>
    <th>Purge rule / historical integrity</th>
  </tr>
  <tr>
    <td>Strategy / MainboardWorkingItem strategy</td>
    <td>Active Mainboard and selector projectionlardan çıkar; restore same root/revision pointer ile geri gelir. Active queued/running Run inputu varsa delete block edilir.</td>
    <td>Completed Run/Result manifests remain readable. Referenced immutable revision physical cleanup retention policyye tabidir.</td>
  </tr>
  <tr>
    <td>Trading Signal / Trade Log</td>
    <td>External Mainboard Working Itemdır; Package type değildir. Restore original Mainboard location/contextine döner.</td>
    <td>Imported source summary/provenance and prior run links retention policyyle korunur.</td>
  </tr>
  <tr>
    <td>Package / Embedded System Package</td>
    <td>New package selectionlerden çekilir; prior strategy/run revisions pinli kalır. System package için delete yerine deprecate/policy may apply.</td>
    <td>Purge policy system-owned canonical package için restrictive; no accidental removal of active system dependency.</td>
  </tr>
  <tr>
    <td>Market Data / Research Data</td>
    <td>New run/feature selectionlerinden çıkar; approved/referenced dataset revisions old manifestler için readable kalır.</td>
    <td>Immutable revision/artifact retention before cleanup is mandatory.</td>
  </tr>
  <tr>
    <td>Backtest Result</td>
    <td>Main Results/History list projectionundan çıkar; parent Run manifest stays immutable.</td>
    <td>Minimum result metadata/audit linkage must remain; result payload purge policy retains reproducibility evidence as required.</td>
  </tr>
  <tr>
    <td>Rationale Family</td>
    <td>Delete before active assignments repair/unassign plan is mandatory. Restore reintroduces active shared card; old family snapshots remain historical.</td>
    <td>No dangling assignment. Shared-edit exception does not grant Trash rights.</td>
  </tr>
  <tr>
    <td>Analysis Lab output / Agent artifact</td>
    <td>Owner Agent or permitted human may soft delete; source task/checkpoint/provenance retained. Agent main loop is not stopped.</td>
    <td>Running task/checkpoint is not deleted via generic Trash route. Coordinator lifecycle rules apply.</td>
  </tr>
  <tr>
    <td>User Manual document segment</td>
    <td>Reader projectiondan çıkar; restore original stable sequence keyyle returns without deleting later segments.</td>
    <td>Built-in/system content purge policy may block or require system-specific approval.</td>
  </tr>
</table>

# 11. Agent Tool / API Eşdeğeri ve Sınırlar

Agent, trash UIyı veya browser clicki kullanmaz. Agentın kendi ürettiği outputları kaldırması gerekiyorsa aynı canonical `entity.soft_delete` domain commandini trusted Agent principal ile çağırır. Agentın Trash list, snapshot detail, restore veya purge için tool/API yeteneği yoktur. Bu sınır Agentın sürekli araştırma loopunu UI oturumundan bağımsız tutar ve Admin geri alma yetkisini Agenta devretmez.

<table>
  <tr>
    <th>Agent capability</th>
    <th>Allowed?</th>
    <th>Canonical behavior</th>
  </tr>
  <tr>
    <td>Own Strategy draft / hypothesis / artifact soft delete</td>
    <td>Yes, policy and ownership permitse.</td>
    <td>Agent tool -&gt; `entity.soft_delete`; same snapshot/audit/outbox pipeline; no browser automation.</td>
  </tr>
  <tr>
    <td>Other owner normal object soft delete</td>
    <td>No, except Rationale shared-edit exception if the active-resource policy applies.</td>
    <td>Server rejects `DELETE_FORBIDDEN`; visibility/use right edit/delete right değildir.</td>
  </tr>
  <tr>
    <td>Trash list / snapshot query</td>
    <td>No.</td>
    <td>No `trash.list` or `trash.get` Agent tool exposed; 403 if direct attempt.</td>
  </tr>
  <tr>
    <td>Restore own output</td>
    <td>No.</td>
    <td>Only human Admin through Trash restore command.</td>
  </tr>
  <tr>
    <td>Purge own output</td>
    <td>No.</td>
    <td>Only human Admin + reauth + purge job.</td>
  </tr>
  <tr>
    <td>Delete running Agent task/checkpoint</td>
    <td>No, not generic delete.</td>
    <td>Agent Coordinator lifecycle / pause/cancel/complete commands govern task state; active loop remains consistent.</td>
  </tr>
  <tr>
    <td>React to removed input</td>
    <td>Yes, controlled.</td>
    <td>Coordinator records dependency failure/follow-up; it must not silently substitute data and change historical meaning.</td>
  </tr>
</table>

# 12. Validation, Hata, Recovery, Lifecycle ve Audit Contract

<table>
  <tr>
    <th>Class</th>
    <th>Canonical validation / error</th>
    <th>UI and recovery behavior</th>
  </tr>
  <tr>
    <td>Authorization</td>
    <td>`TRASH_ACCESS_FORBIDDEN`, `ADMIN_PANEL_ACCESS_REQUIRED`.</td>
    <td>No row data leak. Hide menu for UX, but guard every list/detail/restore/purge endpoint server-side.</td>
  </tr>
  <tr>
    <td>Lifecycle</td>
    <td>`ENTITY_ALREADY_SOFT_DELETED`, `ENTITY_NOT_SOFT_DELETED`, `PURGE_IN_PROGRESS`, `OBJECT_ALREADY_PURGED`.</td>
    <td>Refresh canonical record; show exact current state. Do not offer local restore/purge guesses.</td>
  </tr>
  <tr>
    <td>Dependency / domain preflight</td>
    <td>`DELETE_BLOCKED_BY_RUNNING_JOB`, `RATIONALE_FAMILY_IN_USE`, `RESTORE_CONFLICT`, `PURGE_NOT_ELIGIBLE`.</td>
    <td>Show blocker/warning and repair target. No Trash Entry for a blocked initial delete. Restore remains soft_deleted; purge remains non-terminal.</td>
  </tr>
  <tr>
    <td>Concurrency</td>
    <td>Expected deletion version mismatch / 409 conflict.</td>
    <td>Show stale toast; re-fetch detail; do not overwrite newer restore/purge result.</td>
  </tr>
  <tr>
    <td>Idempotency</td>
    <td>Same `idempotency_key` repeats delete/restore/purge request.</td>
    <td>Return original outcome/job reference; never create duplicate Trash Entry or parallel purge jobs.</td>
  </tr>
  <tr>
    <td>Purge worker</td>
    <td>Retention failure, object storage failure, index cleanup failure.</td>
    <td>Root stays soft_deleted; entry purge_status=failed; audit/log includes safe diagnostic code; retry only through new confirmed request.</td>
  </tr>
  <tr>
    <td>Snapshot protection</td>
    <td>Snapshot contains redacted/size-bounded data only.</td>
    <td>Never render credentials, secrets, tokens or unnecessary raw artifacts in Trash detail.</td>
  </tr>
  <tr>
    <td>Audit integrity</td>
    <td>Delete/restore/purge event chain persists.</td>
    <td>UI cannot edit/delete audit event. Purge may remove payload but not minimal audit/tombstone evidence.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Trash and audit rule. A deletion is not complete merely because the row disappears from a visible list. Delete success requires root state, Trash Entry, audit event and outbox event to commit atomically. Conversely, an outbox consumer failure must not roll the root back to active; it is retried and observed separately.</th>
  </tr>
</table>

# 13. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Konuyu</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Trash storage</td>
    <td>`deletedItems` and `trashAuditLog` JavaScript arrays; reload persistence absent.</td>
    <td>PostgreSQL root/trash/audit/outbox records plus object storage/artifact references; source of truth server-side.</td>
    <td>Do not promote client array to persistence. UI rehydrates backend cursor projection.</td>
  </tr>
  <tr>
    <td>Delete record</td>
    <td>V18 `addTrashEntry()` pushes local record and `status: Soft Deleted`.</td>
    <td>Delete command is transactional root lifecycle mutation with snapshots, audit and outbox.</td>
    <td>V18 labels retained; actual API enum uses `soft_deleted`.</td>
  </tr>
  <tr>
    <td>Search/filter</td>
    <td>V18 browser substring search and dynamic types from memory.</td>
    <td>Server-side policy-filtered cursor query, indexed q/type filters.</td>
    <td>Keep same visible UX; query results must be authoritative and page-safe.</td>
  </tr>
  <tr>
    <td>Snapshot</td>
    <td>V18 displays JSON in same page after Open Snapshot.</td>
    <td>Detail query returns redacted bounded snapshot/dependency summary.</td>
    <td>Inline panel may remain; implementation may use drawer only if same accessibility/selection behavior.</td>
  </tr>
  <tr>
    <td>Restore</td>
    <td>V18 invokes callback, removes entry from array, appends local audit log.</td>
    <td>Atomic admin restore, same root/revision pointer, audit/outbox, type-specific preflight.</td>
    <td>No new revision, no owner transfer, no historical result mutation.</td>
  </tr>
  <tr>
    <td>Permanent Delete</td>
    <td>V18 browser confirm then removes local entry immediately.</td>
    <td>Admin re-auth + explicit confirmation -&gt; async purge job; retention recheck; terminal/tombstone state.</td>
    <td>V18 immediate removal is not Production truth. Keep pending/failed state visible until worker outcome.</td>
  </tr>
  <tr>
    <td>Access gate</td>
    <td>V18 `canManageRoles()` controls menu/page behavior.</td>
    <td>Authenticated human Admin policy on every endpoint.</td>
    <td>Client role visibility is UX only; Agent/other human roles cannot bypass direct request.</td>
  </tr>
  <tr>
    <td>Audit</td>
    <td>V18 local `trashAuditLog` counter.</td>
    <td>Append-only audit events correlated to domain events/jobs.</td>
    <td>Display may show summary count; detailed Logs projection remains a separate page.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Implementation Decision - Non-Canonical Gap Resolution. Production Trash list uses cursor pagination with a default stable sort of `deleted_at DESC, trash_entry_id DESC`, while V18 renders all local rows. This is selected because Trash can grow over time and stable ordering prevents duplicate/missing entries across refreshes. Cursor values are opaque; `All types` and free-text filter parameters apply to the same server query.</th>
  </tr>
</table>

# 14. Kodcu AI için Implementation Rules

- Persisted domain entity names must remain canonical. Use root identity + domain tables and a separate Trash Entry; do not introduce a second generic business object model for Trash.

- Normal delete must use the explicit `entity.soft_delete` command handler. Do not physically delete a root/revision or mutate `root.lifecycle_state` through a generic repository/SQL admin update.

- Delete success is valid only when root soft_deleted state, deletion/dependency snapshots, Trash Entry, audit event and outbox event commit in the same database transaction.

- A soft-deleted root must be excluded from active lists, normal search, new selectors and new Agent input catalogs, but historical pinned revisions/manifests remain readable.

- Deletion lifecycle must stay separate from domain lifecycle. Restore does not turn an approved dataset into draft, does not change package approval and does not create a revision.

- Trash list, snapshot detail, restore and purge endpoints must require an authenticated human Admin. UI visibility or client-supplied role is never authority.

- Rationale Family shared-editing exception does not extend to Trash. Delete preflight must require assignment repair before soft delete; restore/purge remain Admin-only.

- Use `expected_head_revision_id` for Trash lifecycle concurrency, `If-Match`/ETag only as transport support, and an idempotency key for mutating commands. Do not treat them as interchangeable fields.

- Never create a duplicate Trash Entry for the same root deletion. A repeated delete request returns the existing entry/idempotent outcome or explicit already-deleted response.

- Restore must be atomic. If preflight fails, root remains soft_deleted and the UI receives no partial active projection.

- Permanent Delete means purge. It must require second confirmation and re-authentication, run asynchronously, re-check dependencies/retention in the worker and keep audit/tombstone evidence.

- Purge pending disables Restore. Purged roots are never reactivated; re-creation uses a new root identity with optional supersession linkage.

- Snapshot rendering must be redacted and bounded. Do not expose secrets, raw credentials, internal tokens or arbitrary object storage payloads through Trash.

- Agent uses the same soft-delete domain capability only for its own permitted outputs. Do not add Agent Trash browse/restore/purge tools and do not make the Agent click UI controls.

- Source-page delete controls must only remove the item from local view after the backend command succeeds. A failed request leaves the canonical active projection intact.

- Do not conflate Backtest Run and Backtest Result. Soft deleting a Result does not delete the Run manifest; failed/cancelled Runs do not become Result Trash rows unless a real persisted Result root exists.

# 15. Acceptance Tests

<table>
  <tr>
    <th>Test scenario</th>
    <th>Expected result</th>
  </tr>
  <tr>
    <td>Admin opens Trash</td>
    <td>Authenticated Admin receives cursor list, toolbar, counts and only records allowed by policy.</td>
  </tr>
  <tr>
    <td>User/Supervisor/Agent direct Trash list call</td>
    <td>403 `TRASH_ACCESS_FORBIDDEN`; response contains no object names, counts or snapshots.</td>
  </tr>
  <tr>
    <td>User deletes own Trade Log</td>
    <td>Soft delete succeeds; exactly one Trash Entry/audit/outbox event exists; Trade Log leaves active Mainboard; User cannot open Trash.</td>
  </tr>
  <tr>
    <td>Duplicate delete retry</td>
    <td>Same idempotency key returns same Trash Entry; no duplicate entry or duplicate audit completion event.</td>
  </tr>
  <tr>
    <td>Admin soft deletes Dataset referenced by completed Run</td>
    <td>New selectors exclude root; old Run/Result manifest and pinned dataset revision remain readable.</td>
  </tr>
  <tr>
    <td>Delete Strategy used by running Backtest</td>
    <td>409 `DELETE_BLOCKED_BY_RUNNING_JOB`; root remains active; no Trash Entry/audit completed delete event.</td>
  </tr>
  <tr>
    <td>Delete Rationale Family with active assignment</td>
    <td>409 `RATIONALE_FAMILY_IN_USE`; repair plan required; no dangling assignment and no Trash Entry until repair completed.</td>
  </tr>
  <tr>
    <td>Admin restores eligible object</td>
    <td>Same entity_id/current_revision_id becomes active; owner unchanged; no new revision; Trash audit/outbox emitted.</td>
  </tr>
  <tr>
    <td>Non-Admin restore attempt</td>
    <td>403; soft_deleted root and Trash Entry remain unchanged.</td>
  </tr>
  <tr>
    <td>Restore stale version</td>
    <td>409 stale conflict; no partial projection; admin refreshes record.</td>
  </tr>
  <tr>
    <td>Admin starts permanent delete</td>
    <td>Confirmation phrase/re-auth validated; 202 job id; root/entry become purge_pending; Restore disabled.</td>
  </tr>
  <tr>
    <td>Purge retention block</td>
    <td>Worker rejects cleanup; root remains soft_deleted; entry shows purge_failed; audit reason preserved; retry needs fresh confirmation/re-auth.</td>
  </tr>
  <tr>
    <td>Successful purge</td>
    <td>Eligible payloads/projections cleaned; root tombstoned/purged; restore unavailable; audit/tombstone retained.</td>
  </tr>
  <tr>
    <td>Agent deletes own hypothesis output</td>
    <td>Soft delete succeeds; Agent main task/checkpoint loop continues; Agent Trash list/restore/purge calls are denied.</td>
  </tr>
  <tr>
    <td>Snapshot privacy</td>
    <td>Trash snapshot response excludes credentials, tokens and unbounded raw artifact payload; only policy-approved redacted fields render.</td>
  </tr>
  <tr>
    <td>Pagination stability</td>
    <td>With deleted_at ties, cursor sort `deleted_at DESC, trash_entry_id DESC` returns no duplicate or missing entries after refresh.</td>
  </tr>
</table>

# 16. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Canonical terminology</td>
    <td>Trash Entry, soft delete, restore and purge are distinct; `hard delete` is not used as a Production command.</td>
  </tr>
  <tr>
    <td>Role policy</td>
    <td>Trash list/restore/purge is Admin-only; Rationale shared editing does not change this; Agent is non-login and no Trash actor.</td>
  </tr>
  <tr>
    <td>Lifecycle</td>
    <td>Deletion lifecycle is separate from domain lifecycle; restore same root/revision; purge pending/purged transitions are explicit.</td>
  </tr>
  <tr>
    <td>History and reproducibility</td>
    <td>Soft delete does not alter immutable revision chain, completed Run manifest, Result interpretation, Agent provenance or audit evidence.</td>
  </tr>
  <tr>
    <td>V18 alignment</td>
    <td>Actual V18 toolbar/table/snapshot/actions/confirmation/empty state are documented; local-array behavior is not used as Production persistence.</td>
  </tr>
  <tr>
    <td>Async behavior</td>
    <td>Only purge is a durable worker job; delete/restore are transactional commands with outbox downstream propagation.</td>
  </tr>
  <tr>
    <td>UI vs backend</td>
    <td>No UI hidden/disabled state is treated as authorization or lifecycle truth; canonical state rehydrates from server.</td>
  </tr>
  <tr>
    <td>Future Dev boundary</td>
    <td>No fake retention automation or live-trading behavior added. Automatic purge remains disabled in Production V1.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Master Technical Reference consistency result. This page preserves the Master decisions that normal deletion is soft delete; Trash is Admin-only; restore keeps the same root identity and revision pointer; historical runs/results remain meaningful; purge is explicit, asynchronous, retention-controlled and audit-preserving; and Agent continuous work does not depend on Trash UI.</th>
  </tr>
</table>
