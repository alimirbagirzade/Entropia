---
title: "Entropia V18 — Panel / Management / Logs Page Documentation v1.1"
page_number: 19
document_type: "Page implementation specification"
source_document: "Entropia_V18_Panel_Management_Logs_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Panel / Management / Logs Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18
> **Original DOCX footer:** ENTROPIA V18 | Panel / Management / Logs | Sayfa Dokümantasyonu 19/22 | Production V1 uygulama sözleşmesi

ENTROPIA V18

PANEL / MANAGEMENT / LOGS

Sayfa Dokümantasyonu 19/22 | Admin-only role management, immutable event-log projection ve merkezi operasyonel gözlem sözleşmesi

# 0. Document Control, Scope ve Source Traceability

Bu belge yalnız Panel menüsü altındaki Management ve Logs yüzlerini tanımlar. Panel, günlük Strategy/Package/Data üretimi için çalışma alanı değildir; merkezi yönetimsel görünürlük, insan kullanıcı rol yönetimi ve immutable olay kayıtlarının okunabilir projeksiyonu için Admin-only yüzdür. Trash, ayrı Sayfa Dokümantasyonu 20/22 kapsamında ayrıntılı olarak açıklanır; burada yalnız Panel içindeki görünürlük ve navigation sınırı belirtilir.

<table>
  <tr>
    <th>Canonical Production V1 kararı. Panel, Management ve Logs endpointleri yalnız authenticated human Admin principal tarafından erişilebilir olmalıdır. Supervisor, User ve Agent için görünürlük, client-side menu state veya V18 demo role switch ile sağlanmış olsa bile Production V1 policy bunu değiştirmez. Agent insan kullanıcı değildir; Management rol tablosuna girmez, rol atanamaz ve Panel sayfalarına sahip değildir.</th>
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
    <td>Modül 16 §§1-14; Canonical Integration CR-02, CR-04, CR-08</td>
    <td>Panelin Admin-only Production policysi; Management role commandi; Logs append-only projectionı; event model; cursor pagination; errors; API; transaction akışı; acceptance testleri.</td>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0</td>
    <td>Modül 1 §§5-11; Modül 2 §§2-9; Modül 3 §§1-9; Modül 19-20</td>
    <td>Role semantics, Agent system actor ayrımı, owner/created_by/audit; soft delete/Trash; server-side route policy; outbox/SSE/worker çalışma sınırı.</td>
  </tr>
  <tr>
    <td>V18 ana HTML</td>
    <td>Panel dropdown; `showPanelLogs`; `showPanelManagement`; `renderPanelManagementPage`; `assignRegisteredUserRole`; `registeredUsers`; `canAccessSystemWorkspace`; `canManageRoles`</td>
    <td>Gerçek prototip panel menüsü, V18 Logs tablo içeriği, Management tablosu, dropdown seçenekleri, System Actor ve Trash Visibility kartları, V18 role demo davranışı.</td>
  </tr>
  <tr>
    <td>Sayfa Bazlı Dokümantasyon Handoff v1.1</td>
    <td>§§2-6; Field/Interaction/Content/Command matrisleri; final consistency standardı</td>
    <td>Kaynak üstünlüğü, V18-Production ayrımı, requiredness, content catalog, Agent parity, lifecycle, audit, implementation rules ve acceptance test yapısı.</td>
  </tr>
  <tr>
    <td>2.3. POSITION ENTRY LOGIC örnek dokümanı</td>
    <td>Anlatım derinliği referansı</td>
    <td>Kavramı tanımlama, field/dependency sonucu, backend decision trace ve test edilebilir implementation rule dili.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam içi</th>
    <th>Kapsam dışı / yalnız çapraz referans</th>
  </tr>
  <tr>
    <td>Panel menu visibility; Management role registry; System Actor read-only kartı; canonical role scope matrix; Logs list, filters, pagination, detail drawer, correlation/cause chain; role/audit/event projectionları; Admin-only error/recovery davranışı.</td>
    <td>Authentication yöntemi ve parola yönetimi; kullanıcı account creation flowu; Account deactivation/deletion; Trash list/restore/purge ayrıntısı; Strategy/Data/Package/Backtest domain ekranlarının commandleri; Agent lifecycle controls; dış observability vendoru ve log retention altyapısının fiziksel seçimi.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kavramsal Terimler

Panel; Mainboard ve Agent Workspace gibi yeni çalışma nesnesi üretmez. Management yalnız insan kullanıcıların current role stateini değiştiren yönetim yüzüdür. Logs ise Strategy, Package, Dataset, Backtest Run, Result, Agent Artifact veya Management stateinin asıl kaynağı değildir; immutable domain/audit eventlerinden üretilmiş, filtrelenebilir ve zaman sıralı bir read projectiondır.

<table>
  <tr>
    <th>Terim</th>
    <th>Canonical kısa tanım</th>
    <th>Bu sayfadaki uygulama sonucu</th>
  </tr>
  <tr>
    <td>Principal</td>
    <td>Backendin adına işlem yürüttüğü kimlik: authenticated human, Agent runtime veya system service.</td>
    <td>Panel commandleri yalnız Admin human principal ile çalışır; request body içindeki role değeri otorite değildir.</td>
  </tr>
  <tr>
    <td>Registered Human User</td>
    <td>Admin, Supervisor veya User rolünü taşıyabilen insan hesabı.</td>
    <td>Management tablosunun tek atanan hedef türüdür.</td>
  </tr>
  <tr>
    <td>Agent System Actor</td>
    <td>Human account olmayan, server-side runtime kimliğiyle çalışan sistem aktörü.</td>
    <td>Read-only System Actor kartında gösterilir; role dropdownuna ve user registryye girmez.</td>
  </tr>
  <tr>
    <td>Role Assignment</td>
    <td>Bir human userin current roleunu atomik biçimde güncelleyen command.</td>
    <td>Owner transferi, historical provenance değişikliği veya Agent lifecycle komutu değildir.</td>
  </tr>
  <tr>
    <td>Audit Event</td>
    <td>Actor, action, subject, before/after summary, time ve correlation taşıyan append-only kanıt kaydı.</td>
    <td>Role change sonrası zorunlu oluşur; Logs bunu indeksleyip görüntüler.</td>
  </tr>
  <tr>
    <td>Log Projection</td>
    <td>Domain/audit eventlerine dayalı okunabilir, filtrelenebilir event listesi.</td>
    <td>Asıl event veya kaynak nesne yerine geçmez; edit/delete edilemez.</td>
  </tr>
  <tr>
    <td>Correlation ID / Causation Event ID</td>
    <td>Bağlı pipeline eventlerini ve tetikleyen önceki olayı ilişkilendiren anahtarlar.</td>
    <td>Log Detail Drawer, role change ve worker pipeline bağlamını göstermek için kullanır.</td>
  </tr>
  <tr>
    <td>Soft Delete</td>
    <td>Kaynağı aktif listeden çıkarıp Trashte restore edilebilir tutma lifecycle işlemi.</td>
    <td>Log event silinmez; subject soft-deleted ise Logs detailde Deleted / see Trash olarak kalır.</td>
  </tr>
</table>

# 2. Erişim, Görünürlük ve Server-side Policy

V18 prototipinde `canAccessSystemWorkspace()` Admin, Supervisor ve Agent için true döndürür; böylece Panel menüsü bu üç demo role görünür. `canManageRoles()` ise yalnız Admin için true döndürür ve role dropdownunu açar. Bu davranış V18 Interface Observationdır; Production V1 canonical policy değildir.

<table>
  <tr>
    <th>Actor</th>
    <th>V18 Panel menu / page</th>
    <th>Production V1 Panel / Management / Logs</th>
    <th>Server-side sonuç</th>
  </tr>
  <tr>
    <td>Guest</td>
    <td>Panel menu hidden. Demo currentRole başlangıçta User görünse de guest gerçek authenticated User değildir.</td>
    <td>No access.</td>
    <td>401 / unauthenticated veya public-route dışında denial.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Panel menu hidden.</td>
    <td>No access.</td>
    <td>403 `ADMIN_PANEL_ACCESS_REQUIRED`.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>V18 menu ve read-only Management/Logs görülebilir.</td>
    <td>No access.</td>
    <td>403 `ADMIN_PANEL_ACCESS_REQUIRED`; UI hidden olsa da endpoint guard zorunludur.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>V18 menu visible; Management role mutation; Logs table; Trash menu visible.</td>
    <td>Full page access; human role assignment, canonical logs query/detail/correlation access; Trash link visible.</td>
    <td>Admin policy, target-type, version and lifecycle validation ile command yürür.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>V18 menu ve read-only Management/Logs görülebilir; Agent demo login ile simüle edilir.</td>
    <td>No Panel access. Agent runtime, Panel UI olmadan kendi queue/checkpoint/artifact loopunu sürdürür.</td>
    <td>403 `ADMIN_PANEL_ACCESS_REQUIRED`; Agent logs query domain toolu Panel commandi değildir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Derived Rule. Panel erişimi, role assignment hakkı ile aynı kavram değildir; ancak Production V1de Panelin kendisi yalnız Admin sınırına alınır. Buna rağmen her Management veya Logs endpointi ayrıca `require_admin` uygular. Bir menu itemin hidden veya visible olması authorization kararı değildir.</th>
  </tr>
</table>

# 3. V18 Interface Behavior: Gerçek Görünür Arayüz Envanteri

V18 tek HTML prototipinde Panel, üst navigation shell içinde `admin-only` CSS sınıfı taşıyan bir dropdown menüdür. `updateAdminOnlyMenus()` demo role değişimine göre Panel menüsünü Admin, Supervisor ve Agent için görünür yapar; `trashMenuItem` yalnız Admin için görünür kalır. Productionda bu client-side davranış yalnız visual reference sayılır.

## 3.1 Panel Dropdown ve navigasyon

<table>
  <tr>
    <th>Bileşen</th>
    <th>V18 görünümü / default</th>
    <th>Etkileşim ve görünme koşulu</th>
    <th>Production notu</th>
  </tr>
  <tr>
    <td>Panel menu</td>
    <td>Top menu içinde `Panel`; default guest/User demo stateinde hidden.</td>
    <td>V18de Admin, Supervisor veya Agent login/demosu sonrasında visible. Hover ile dropdown açılır.</td>
    <td>Productionda yalnız authenticated Admin için route/menu projection gösterilir.</td>
  </tr>
  <tr>
    <td>Logs item</td>
    <td>Dropdown item: `Logs`.</td>
    <td>Click -&gt; `showPanelLogs(event)`; normal workspace page contenti `PANEL / LOGS` olur.</td>
    <td>Admin-only logs route; query-backed projection.</td>
  </tr>
  <tr>
    <td>Management item</td>
    <td>Dropdown item: `Management`.</td>
    <td>Click -&gt; `showPanelManagement(event)`; `PANEL / MANAGEMENT` görünür.</td>
    <td>Admin-only management route; role registry projection.</td>
  </tr>
  <tr>
    <td>Trash item</td>
    <td>Dropdown item: `Trash`; V18 default hidden unless Admin demo state.</td>
    <td>Click -&gt; separate Trash view.</td>
    <td>Sayfa 20 kapsamındadır; burada yalnız Admin-only navigation linki olarak tanımlanır.</td>
  </tr>
  <tr>
    <td>No V18 modal/popup</td>
    <td>Panel, Management veya Logs için V18de ayrı modal/popover yoktur.</td>
    <td>Page content workspace içinde değişir; V18 role Apply local array mutation yapar.</td>
    <td>Production Logs detail, liste contextini koruyan sağ detail drawer olarak uygulanır (Implementation Decision). Role update için generic confirmation modal zorunlu değildir.</td>
  </tr>
</table>

## 3.2 V18 Logs yüzü

V18 Logs ekranı, `All User Backtest Logs` başlığı altında yalnız backtestHistory arrayinden üretilen tek bir tablo gösterir. Açıklama metni şudur: “Logs list backtest history across all users. Result History is current-user oriented; Logs is admin-level history.” V18de filtre, arama, cursor pagination, satır detaili, event kind, severity, audit correlation veya immutable event davranışı görünmez.

<table>
  <tr>
    <th>V18 görünür alan / tablo</th>
    <th>Default / veri kaynağı</th>
    <th>V18 davranışı</th>
    <th>V18de olmayan ama Productionda zorunlu</th>
  </tr>
  <tr>
    <td>Heading</td>
    <td>`PANEL / LOGS`.</td>
    <td>`showPage` content title olarak render edilir.</td>
    <td>Admin route state ve server projection.</td>
  </tr>
  <tr>
    <td>Intro text</td>
    <td>All User Backtest Logs + kısa açıklama.</td>
    <td>Read-only prose.</td>
    <td>Canonical logs tanımı, eventual consistency ve Admin-only policy helper metni.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>BacktestHistory indexine göre `User` veya `Agent-Research-01` demo değeri.</td>
    <td>Read-only table cell.</td>
    <td>Canonical actor type/id server eventten gelir; demo index parity kullanılmaz.</td>
  </tr>
  <tr>
    <td>Date</td>
    <td>backtestHistory row.date.</td>
    <td>Read-only.</td>
    <td>`occurred_at` UTC event time; time zone presentation user locale olabilir ama source UTC kalır.</td>
  </tr>
  <tr>
    <td>Backtest</td>
    <td>backtestHistory row.title.</td>
    <td>Read-only.</td>
    <td>Subject reference / run deep-link; Result summarynin kopyası değildir.</td>
  </tr>
  <tr>
    <td>Net Profit / ROMAD / Trades</td>
    <td>backtestHistory metric değerleri.</td>
    <td>Read-only.</td>
    <td>Logs listede yalnız short message ve subject olur; metric report Results domaininden okunur.</td>
  </tr>
  <tr>
    <td>Filters / pagination / detail</td>
    <td>V18de yok.</td>
    <td>N/A.</td>
    <td>Server filters, cursor pagination, row detail drawer, correlation/cause chain ve deleted-source handling zorunludur.</td>
  </tr>
</table>

## 3.3 V18 Management yüzü

V18 Management ekranı üç görünür bölge içerir: Registered User Role Assignment tablosu, sağ System Actor / Trash Visibility kartları ve alt Role Scope Matrix. V18 registeredUsers listesi `admin`, `supervisor` ve `user` kayıtlarını içerir. Agent bu arraye bilinçli olarak eklenmez.

<table>
  <tr>
    <th>V18 bileşeni</th>
    <th>Görünür alanlar / seçenekler</th>
    <th>Default ve yetki</th>
    <th>V18 davranışı</th>
  </tr>
  <tr>
    <td>Intro</td>
    <td>“Admin, Supervisor and Agent can open Panel ... Only Admin can assign or change user roles ... Agent remains a built-in system actor ...”</td>
    <td>Always visible once page opens.</td>
    <td>Productionda bu metin canonical Admin-only policy ile güncellenir; Supervisor/Agent Panel access ifadesi V18 observation olarak kalır.</td>
  </tr>
  <tr>
    <td>Registered User Role Assignment - Admin view</td>
    <td>Columns: Username; Current Role; Assignable Role; Action.</td>
    <td>`admin`, `supervisor`, `user` rows; selectable role defaults rowun current roleudur.</td>
    <td>Admin için select + `Apply Role` button render edilir.</td>
  </tr>
  <tr>
    <td>Assignable Role dropdown</td>
    <td>Options: Admin; Supervisor; User.</td>
    <td>V18 current selected option = user.role.</td>
    <td>Agent optionu yoktur. `assignRegisteredUserRole(index)` local array row.role değiştirir.</td>
  </tr>
  <tr>
    <td>Read-only registry</td>
    <td>Columns: Username; Current Role; Role Assignment.</td>
    <td>V18 Supervisor/Agent view.</td>
    <td>Role Assignment cell: `Admin only`; role select ve Apply button yoktur.</td>
  </tr>
  <tr>
    <td>System Actor card</td>
    <td>Agent açıklaması; system actor, shared use, own output mutation, no Trash/no roles.</td>
    <td>Always right card.</td>
    <td>Read-only card; V18 Agent login simulationi vardır fakat Productionda Agent human login değildir.</td>
  </tr>
  <tr>
    <td>Trash Visibility card</td>
    <td>Trash yalnız Admin için visible/accessibile.</td>
    <td>Always card content.</td>
    <td>Separate Trash screen scope dışında.</td>
  </tr>
  <tr>
    <td>Role Scope Matrix</td>
    <td>Rows: Admin, Supervisor, User, Agent; columns View/Use, Edit, Delete, Trash, Role Assignment.</td>
    <td>Read-only.</td>
    <td>V18 simplified text; Productionda policy service `GET /v1/admin/role-matrix` projectionı source olur.</td>
  </tr>
</table>

# 4. Production Backend Behavior: Yönetim ve Log Domain Sözleşmesi

## 4.1 Registered Human User ve System Actor ayrımı

<table>
  <tr>
    <th>Kayıt</th>
    <th>Minimum canonical alanlar</th>
    <th>Bu sayfa davranışı</th>
  </tr>
  <tr>
    <td>Human user projection</td>
    <td>user_id; username/display_name; current_role; version; role_changed_at; role_changed_by; session/active summary; created_at.</td>
    <td>Management list yalnız human actorları cursor ile döndürür. Role dropdown hedefi yalnız `Admin | Supervisor | User` enumudur.</td>
  </tr>
  <tr>
    <td>System actor projection</td>
    <td>actor_type=`system_agent`; actor_id; display_name; service status summary; provenance policy summary.</td>
    <td>Agent User registrysinden ayrıdır. Read-only System Actor kartı bu projectiondan gelir; role update veya revoke commandi yoktur.</td>
  </tr>
  <tr>
    <td>Role policy matrix</td>
    <td>Role definitions ve operation scope; policy revision/version.</td>
    <td>Hard-coded V18 metni yerine canonical policy projectionı olur. Matrixin displayi server truthun read modelidir; UI bunu edit edemez.</td>
  </tr>
  <tr>
    <td>Audit event</td>
    <td>event_id; occurred_at; event_kind; severity; actor; subject; correlation_id; causation_event_id; message; payload_ref; trace_id/job_id.</td>
    <td>Logs liste/drawer event kaydını gösterir. Event ve payload immutable kaynaklardır.</td>
  </tr>
  <tr>
    <td>Log projection</td>
    <td>event index fields + subject/deep-link availability + search tokens + cursor ordering key.</td>
    <td>Admin Logs ekranı raw audit tableı veya browser statei yerine projectionı sorgular.</td>
  </tr>
</table>

## 4.2 Role Assignment commandi

Managementdeki gerçek mutasyon `PATCH /v1/admin/users/{user_id}/role` commandidir. Request yalnız server-derived Admin actor context ile yürür. Hedef role seçimi clienttan gelir; caller role, target user type ve last-Admin koruması clienttan kabul edilmez.

<table>
  <tr>
    <th>PATCH /v1/admin/users/{user_id}/role<br/>If-Match: &quot;user-version-12&quot;<br/>Idempotency-Key: 9b6...<br/><br/>{<br/>  &quot;target_role&quot;: &quot;Supervisor&quot;,<br/>  &quot;expected_head_revision_id&quot;: 12,<br/>  &quot;reason&quot;: &quot;Assigned as workspace supervisor&quot;<br/>}<br/><br/>200 OK<br/>{<br/>  &quot;user_id&quot;: &quot;usr_...&quot;,<br/>  &quot;username&quot;: &quot;supervisor&quot;,<br/>  &quot;role&quot;: &quot;Supervisor&quot;,<br/>  &quot;version&quot;: 13,<br/>  &quot;role_changed_at&quot;: &quot;2026-06-25T00:00:00Z&quot;,<br/>  &quot;audit_event_id&quot;: &quot;evt_...&quot;,<br/>  &quot;correlation_id&quot;: &quot;cmd_...&quot;<br/>}</th>
  </tr>
</table>

<table>
  <tr>
    <th>Adım</th>
    <th>Zorunlu server davranışı</th>
    <th>UI sonucu</th>
  </tr>
  <tr>
    <td>1. Authenticate / authorize</td>
    <td>Authenticated principal çözülür; `require_admin` true değilse command başlamaz.</td>
    <td>403; local dropdown/value commit edilmez.</td>
  </tr>
  <tr>
    <td>2. Lock / load target</td>
    <td>Human user row `FOR UPDATE` veya eşdeğer transaction lock ile okunur.</td>
    <td>Loading state row-level olur; diğer satırlar read-only kalabilir.</td>
  </tr>
  <tr>
    <td>3. Validate</td>
    <td>Target human olmalı; role enum geçerli olmalı; expected_head_revision_id eşleşmeli; son active Admin korunmalı; caller/session policy güncel olmalı.</td>
    <td>422/409 inline error; canonical current row refresh edilir.</td>
  </tr>
  <tr>
    <td>4. Mutate atomically</td>
    <td>users.role, users.version, role_changed_at, role_changed_by güncellenir. Owner, created_by, historical manifests veya prior audits değişmez.</td>
    <td>Success response sonrası satır server response ile rehydrate edilir.</td>
  </tr>
  <tr>
    <td>5. Write event / outbox</td>
    <td>Aynı transactionda `role_assigned` audit/outbox event yazılır.</td>
    <td>“Role updated. Audit event will appear in Logs shortly.” toastı gösterilir.</td>
  </tr>
  <tr>
    <td>6. Project / notify</td>
    <td>Event dispatcher immutable audit store ve searchable Logs projectionı üretir; event fanout admin UIyi invalidate edebilir.</td>
    <td>Open Logs filter eşleşirse list refetch veya SSE-driven refresh yapılır.</td>
  </tr>
  <tr>
    <td>7. Re-evaluate sessions</td>
    <td>Target userin sonraki requestleri current role ile değerlendirilir. Current Admin kendini down-role ederse page access yeniden hesaplanır.</td>
    <td>User artık Admin değilse Management UI bırakılır, restricted statee yönlendirilir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Implementation Decision - no-op role save. Seçilen target role, mevcut role eşitse backend mutation, version increment ve `role_assigned` audit event üretmez. API current user projectionını `changed=false` ile döndürür; UI “No role change was needed.” bilgisini gösterir. Bu karar audit zincirini anlamsız tekrarlarla doldurmamak içindir.</th>
  </tr>
</table>

## 4.3 Logs source, event model ve projection zinciri

Logs, backtest metrics tablosu değildir. Bir log satırı role assignment, package pre-check, dataset approval, soft delete, backtest worker failure veya Agent checkpoint gibi bir eventin kısa görünümüdür. Result, Dataset Revision, Package Revision, Backtest Run veya Agent Artifactın tam payloadı Logs içinde kopyalanmaz; stable subject reference ve erişim olduğu yerde deep link kullanılır.

<table>
  <tr>
    <th>Event alanı</th>
    <th>Canonical açıklama</th>
    <th>Logs UI davranışı</th>
  </tr>
  <tr>
    <td>event_id</td>
    <td>Immutable UUID; log/audit satırının ana kimliği.</td>
    <td>Detail Drawer identity ve stable route anahtarı.</td>
  </tr>
  <tr>
    <td>occurred_at</td>
    <td>Kaynak sistemde oluşma anı; UTC.</td>
    <td>List varsayılan newest-first sıralama anahtarı; UI locale render edebilir.</td>
  </tr>
  <tr>
    <td>event_kind</td>
    <td>Örnek: role_assigned, backtest_queued, backtest_failed, dataset_approved, agent_checkpoint_completed.</td>
    <td>Filterable event family / detailde full kind.</td>
  </tr>
  <tr>
    <td>severity</td>
    <td>INFO, WARNING veya ERROR; domain status yerine geçmez.</td>
    <td>Severity pill; All/INFO/WARNING/ERROR dropdownu.</td>
  </tr>
  <tr>
    <td>actor_type / actor_id</td>
    <td>human, system_agent veya system başlatıcı.</td>
    <td>Actor filter ve row display.</td>
  </tr>
  <tr>
    <td>subject_type / subject_id</td>
    <td>User, package_revision, dataset_revision, backtest_run, artifact vb. asıl nesne referansı.</td>
    <td>Deep link policy-rechecked; soft-deletedse Deleted / see Trash label.</td>
  </tr>
  <tr>
    <td>correlation_id</td>
    <td>Tek command veya job pipelineındaki bağlı olayların ortak anahtarı.</td>
    <td>“View correlation chain” action ile ordered events gösterilir.</td>
  </tr>
  <tr>
    <td>causation_event_id</td>
    <td>Bu eventin doğrudan tetikleyici event referansı.</td>
    <td>Drawerdaki causation row; event route.</td>
  </tr>
  <tr>
    <td>message / payload_ref</td>
    <td>Admin için kısa insan-okur mesaj; büyük immutable detail referansı.</td>
    <td>Raw secrets, full strategy JSON, full dataset rowları varsayılan UIya taşınmaz.</td>
  </tr>
  <tr>
    <td>trace_id / job_id</td>
    <td>Worker/job troubleshooting referansı.</td>
    <td>Technical identifiers collapsed section; editable değildir.</td>
  </tr>
</table>

# 5. Production UI Sözleşmesi: Interaction State Matrix

V18de Logs için toolbar, filter, loading veya pagination controls yoktur. Aşağıdaki state sözleşmesi Production V1 için canonical Logs projection gereksiniminden türetilmiş UI kararlarını tanımlar. Bu görünür kontroller yalnız Admin routeunda render edilir; server policy onların güvenlik karşılığıdır.

<table>
  <tr>
    <th>Bileşen</th>
    <th>Varsayılan / aktifleşme</th>
    <th>Disabled / loading davranışı</th>
    <th>Payload / backend etkisi</th>
    <th>Recovery / kullanıcı metni</th>
  </tr>
  <tr>
    <td>Panel route</td>
    <td>Admin menu click veya direct route.</td>
    <td>Initial route auth resolving; page content render edilmezse stale V18 content kalmaz.</td>
    <td>GET current actor context + route policy.</td>
    <td>“Admin access is required to use Panel.”</td>
  </tr>
  <tr>
    <td>Management registry</td>
    <td>Default current cursor first page; newest role changes değil, stable user listing order.</td>
    <td>Skeleton rows; Apply buttons related row mutation sırasında disabled.</td>
    <td>GET `/v1/admin/users?limit=50&amp;cursor=...`.</td>
    <td>“Loading registered users...” / retry query.</td>
  </tr>
  <tr>
    <td>Role select</td>
    <td>Current server role selected.</td>
    <td>Mutation pending row select+Apply disabled; no optimistic permanent role change.</td>
    <td>Draft target_role only; save ile PATCH.</td>
    <td>409de row canonical response ile reload.</td>
  </tr>
  <tr>
    <td>Apply Role</td>
    <td>Enabled only target role differs ve Admin route policy confirmed.</td>
    <td>Disabled if target unchanged, request pending, role data stale, selected role missing.</td>
    <td>PATCH role command + idempotency / expected_head_revision_id.</td>
    <td>“Role update was not applied. Reload the latest registry state.”</td>
  </tr>
  <tr>
    <td>System Actor card</td>
    <td>Read-only current projection.</td>
    <td>Loading placeholder; no mutation buttons.</td>
    <td>GET system actors / embedded overview ref.</td>
    <td>“System actor information is temporarily unavailable.”</td>
  </tr>
  <tr>
    <td>Role Scope Matrix</td>
    <td>Read-only canonical role policy.</td>
    <td>Static read-only while policy query loads.</td>
    <td>GET role matrix projection.</td>
    <td>No role edit affordance.</td>
  </tr>
  <tr>
    <td>Logs toolbar</td>
    <td>Newest-first; limit=50; filters empty/All by default.</td>
    <td>Apply/Reset disabled only while same query request pending.</td>
    <td>GET logs with server query parameters.</td>
    <td>Filter result page refetches; no browser-side full-history filter.</td>
  </tr>
  <tr>
    <td>Logs list</td>
    <td>Most recent 50 matching events.</td>
    <td>List skeleton; Load More disabled while cursor request pending or no next_cursor.</td>
    <td>Cursor page query against projection.</td>
    <td>“No events matched current filters.” is empty, not error.</td>
  </tr>
  <tr>
    <td>Log row</td>
    <td>Read-only.</td>
    <td>Drawer action disabled while detail loads.</td>
    <td>GET log detail / correlation context.</td>
    <td>404/retention failure -&gt; generic unavailable; event list stays unchanged.</td>
  </tr>
  <tr>
    <td>Detail Drawer</td>
    <td>Closed by default; opens when row chosen.</td>
    <td>Read-only; no edit/delete/retry/rerun controls.</td>
    <td>GET event detail / correlation route.</td>
    <td>“This event is no longer available for detail view.”</td>
  </tr>
  <tr>
    <td>Deleted source reference</td>
    <td>Event visible even if subject soft-deleted.</td>
    <td>Deep link disabled if no access / record deleted.</td>
    <td>Subject lifecycle metadata in projection/detail.</td>
    <td>“Source is deleted. See Trash.” Admin-only Trash link shown.</td>
  </tr>
</table>

# 6. Field Contract Matrix: Alanlar, Varsayılanlar, Zorunluluk ve Bağımlılıklar

V18 Managementde `*` işareti görünmez. Productionda mutating form alanları için yıldız standardı uygulanır: `Assignable Role *` yalnız Admin role update satırında zorunludur. Username ve Current Role salt okunur alanlardır. Logs filtersi optionaldır; hiçbir filter alanı log querynin zorunlu inputu değildir. Zorunluluk hem UI, server validation hem de Agent/API schema için aynı kuralı taşır.

## 6.1 Management field contract

<table>
  <tr>
    <th>Alan</th>
    <th>V18 default / type</th>
    <th>Production payload / requiredness</th>
    <th>Tüm seçenekler / dependency</th>
    <th>Validation ve state etkisi</th>
  </tr>
  <tr>
    <td>Username</td>
    <td>Read-only table cell: admin, supervisor, user.</td>
    <td>No patch payload; `user_id` route path kullanılır.</td>
    <td>N/A. Agent asla row değildir.</td>
    <td>Server user_id existence / human target check.</td>
  </tr>
  <tr>
    <td>Current Role</td>
    <td>Read-only bold label.</td>
    <td>Response projection: `role`.</td>
    <td>Admin / Supervisor / User only.</td>
    <td>Client editable değildir; source server.</td>
  </tr>
  <tr>
    <td>Assignable Role *</td>
    <td>Select; selected = current row role.</td>
    <td>`target_role` required for changed save.</td>
    <td>Admin; Supervisor; User. Agent optionu yoktur.</td>
    <td>Allowed enum; target role current roleden farklı olmalı; last Admin protection; row version dependency.</td>
  </tr>
  <tr>
    <td>expected_head_revision_id</td>
    <td>V18de görünmez.</td>
    <td>`expected_head_revision_id` required for mutation; HTTP `If-Match` transport mirror.</td>
    <td>Server returned current user projection version.</td>
    <td>Mismatch -&gt; 409 `USER_ROLE_VERSION_CONFLICT`; selected draft reset/server state rehydrate.</td>
  </tr>
  <tr>
    <td>Reason</td>
    <td>V18de yok.</td>
    <td>Optional `reason`; audit context, max length policy.</td>
    <td>Free text; role policyyi bypass etmez.</td>
    <td>Blank accepted; sensitive data/log secret yazılmaz.</td>
  </tr>
  <tr>
    <td>Apply Role</td>
    <td>Button.</td>
    <td>No direct payload field; role patch command.</td>
    <td>Enabled only Admin, valid changed target role, fresh version.</td>
    <td>Loading, success, 409/422/403 handling; audit event created only on effective mutation.</td>
  </tr>
  <tr>
    <td>System Actor</td>
    <td>Static V18 card.</td>
    <td>Read-only system actor projection.</td>
    <td>No dropdown, no delete, no role assignment.</td>
    <td>Attempted Agent target -&gt; 422 `AGENT_ROLE_NOT_ASSIGNABLE`.</td>
  </tr>
  <tr>
    <td>Role Scope Matrix</td>
    <td>Static V18 table.</td>
    <td>Read-only canonical policy projection.</td>
    <td>Roles: Admin, Supervisor, User, Agent.</td>
    <td>No editable policy cells. Shared exceptions referenced but not mutated here.</td>
  </tr>
</table>

## 6.2 Logs toolbar and query field contract

<table>
  <tr>
    <th>Alan</th>
    <th>Default</th>
    <th>Requiredness / all options</th>
    <th>Production query payload</th>
    <th>Validation / dependency</th>
  </tr>
  <tr>
    <td>Time range</td>
    <td>No V18 control. Production: unset = newest events across retained scope.</td>
    <td>Optional. From and To may be independent; if both exist, From &lt;= To.</td>
    <td>`from`, `to` in UTC ISO-8601.</td>
    <td>Invalid range -&gt; inline error; no query dispatch.</td>
  </tr>
  <tr>
    <td>Event family</td>
    <td>No V18 control. Default `All events`.</td>
    <td>Options: All events; Role &amp; access; Backtest; Data; Package; Strategy; Agent; Trash &amp; lifecycle; System / other. Values are server taxonomy projection, not hard-coded client authority.</td>
    <td>`family` optional.</td>
    <td>Unknown/deprecated family rejected or normalized by server; filter options hydrate from schema.</td>
  </tr>
  <tr>
    <td>Severity</td>
    <td>No V18 control. Default `All severities`.</td>
    <td>Options: All severities; INFO; WARNING; ERROR.</td>
    <td>`severity` optional.</td>
    <td>Exact enum. Severity is not run/result state.</td>
  </tr>
  <tr>
    <td>Actor</td>
    <td>No V18 control. Default `All actors`.</td>
    <td>Options: All actors; Human; System; System Agent; plus server-returned actor identities via search picker.</td>
    <td>`actor_type`, `actor_id` optional.</td>
    <td>Actor filter does not grant access to excluded data.</td>
  </tr>
  <tr>
    <td>Resource type</td>
    <td>No V18 control. Default `All resources`.</td>
    <td>Options source: user, strategy, package_revision, dataset_revision, backtest_run, backtest_result, artifact, manual_document, allocation_plan, system.</td>
    <td>`resource_type` optional.</td>
    <td>Options dynamically derived from allowed canonical subject types.</td>
  </tr>
  <tr>
    <td>Correlation ID</td>
    <td>No V18 control. Empty.</td>
    <td>Optional exact or prefix input.</td>
    <td>`correlation_id` optional.</td>
    <td>Format/length validation; no wildcard raw SQL.</td>
  </tr>
  <tr>
    <td>Search</td>
    <td>No V18 control. Empty.</td>
    <td>Optional text search over safe indexed fields.</td>
    <td>`q` optional.</td>
    <td>Trimmed; bounded length; no raw payload search.</td>
  </tr>
  <tr>
    <td>Page size</td>
    <td>No V18 control. Default 50.</td>
    <td>Not user editable in V1 page; server max enforced.</td>
    <td>`limit=50`; `cursor` from server.</td>
    <td>Cursor opaque; client must not construct/sort it.</td>
  </tr>
  <tr>
    <td>Apply filters</td>
    <td>No V18 button.</td>
    <td>Enabled whenever a filter draft differs from active query.</td>
    <td>GET logs query.</td>
    <td>Aborts/replaces pending same-view query; previous data may stay marked stale until response.</td>
  </tr>
  <tr>
    <td>Clear filters</td>
    <td>No V18 button.</td>
    <td>Enabled only if non-default filters active.</td>
    <td>Query reset with no filter params, `limit=50`.</td>
    <td>Returns newest-first initial projection.</td>
  </tr>
  <tr>
    <td>Load more</td>
    <td>No V18 button.</td>
    <td>Visible only if `next_cursor` exists.</td>
    <td>GET logs with active filters + opaque cursor.</td>
    <td>Duplicate click disabled; cursor page append deduplicates by event_id.</td>
  </tr>
</table>

# 7. Information Content Catalog ve Nihai UI Metinleri

V18 Panel/Management/Logs yüzünde görünür ⓘ bilgi düğmesi yoktur. Bu nedenle V18de açılacak mevcut popover envanteri boştur. Aşağıdaki katalog; ekrana zaten konması gereken helper, read-only explanatory card, aria-describedby veya Productionda erişilebilir bir ⓘ kontrolü eklenirse doğrudan kullanılacak nihai metni tanımlar. Bu bir yeni domain behavior değildir; canonical kuralları kullanıcıya doğru anlatma içerik sözleşmesidir.

<table>
  <tr>
    <th>Info key / alan</th>
    <th>Panel başlığı</th>
    <th>Nihai UI metni</th>
  </tr>
  <tr>
    <td>panelAccessInfo</td>
    <td>Panel Access</td>
    <td>Panel is an administrative visibility and control surface. In Production V1, only authenticated human Admin accounts can open Management, Logs, or Trash. Menu visibility does not replace server-side authorization.</td>
  </tr>
  <tr>
    <td>roleAssignmentInfo</td>
    <td>Assignable Role</td>
    <td>Choose the role for this registered human user. Admin, Supervisor, and User are the only assignable roles. The system Agent is not a human user and cannot be assigned, removed, or converted from this screen.</td>
  </tr>
  <tr>
    <td>roleChangeEffectInfo</td>
    <td>Effect of Role Change</td>
    <td>A role change affects future authorization decisions. It does not transfer ownership, rewrite created-by information, change historical backtest manifests, or alter existing audit records.</td>
  </tr>
  <tr>
    <td>lastAdminInfo</td>
    <td>Last Active Admin Protection</td>
    <td>The final active Admin cannot be changed to Supervisor or User. Assign another active Admin before reducing the last Admin role.</td>
  </tr>
  <tr>
    <td>systemActorInfo</td>
    <td>System Actor</td>
    <td>Agent is a server-side system actor. It may create and manage its own outputs according to policy, but it is not a login account, not an assignable role, and not a Panel administrator.</td>
  </tr>
  <tr>
    <td>logsInfo</td>
    <td>Logs</td>
    <td>Logs are a read-only projection of immutable domain and audit events. A log row explains what happened and links to its source when access permits; it does not replace the source object or allow historical edits.</td>
  </tr>
  <tr>
    <td>correlationInfo</td>
    <td>Correlation Chain</td>
    <td>A correlation chain groups events created by one command or pipeline. Causation identifies the event that directly triggered the selected event. These links make complex work such as a role change or backtest run traceable.</td>
  </tr>
  <tr>
    <td>deletedSourceInfo</td>
    <td>Deleted Source</td>
    <td>The event is retained even though its source object is no longer active. Admins can use the Trash link to inspect restore eligibility. The log record itself cannot be deleted or edited.</td>
  </tr>
  <tr>
    <td>eventualConsistencyInfo</td>
    <td>Log Projection Timing</td>
    <td>Management changes are committed together with an audit/outbox event. The searchable Logs projection may appear after a short dispatcher delay. Refreshing the list never creates a second audit event.</td>
  </tr>
</table>

## 7.1 Placeholder, helper, warning, toast, confirmation ve hata metinleri

<table>
  <tr>
    <th>Durum</th>
    <th>Nihai UI metni</th>
    <th>Kullanım</th>
  </tr>
  <tr>
    <td>Management loading</td>
    <td>Loading registered users and current role state...</td>
    <td>Initial Management query.</td>
  </tr>
  <tr>
    <td>Logs loading</td>
    <td>Loading the latest administrative events...</td>
    <td>Initial / filter logs query.</td>
  </tr>
  <tr>
    <td>Reason placeholder</td>
    <td>Optional audit context for this role change.</td>
    <td>Reason text input, only if Production UI exposes it.</td>
  </tr>
  <tr>
    <td>Role helper</td>
    <td>Changing a role affects future permissions only. Ownership and historical records do not change.</td>
    <td>Under role table.</td>
  </tr>
  <tr>
    <td>No-change notice</td>
    <td>No role change was needed.</td>
    <td>Selected role equals current role; no mutation.</td>
  </tr>
  <tr>
    <td>Role success</td>
    <td>Role updated. {username} is now {role}. The audit event will appear in Logs shortly.</td>
    <td>200 changed response.</td>
  </tr>
  <tr>
    <td>Forbidden</td>
    <td>Admin access is required to use Panel.</td>
    <td>403 Panel route or command denial.</td>
  </tr>
  <tr>
    <td>Agent target error</td>
    <td>The system Agent cannot be assigned to a human account.</td>
    <td>422 AGENT_ROLE_NOT_ASSIGNABLE.</td>
  </tr>
  <tr>
    <td>Last Admin blocker</td>
    <td>This change would remove the last active Admin. Assign another Admin first.</td>
    <td>422 LAST_ADMIN_PROTECTION.</td>
  </tr>
  <tr>
    <td>Version conflict</td>
    <td>This user record was updated by another Admin. The latest values have been loaded.</td>
    <td>409 USER_ROLE_VERSION_CONFLICT.</td>
  </tr>
  <tr>
    <td>Role policy changed</td>
    <td>Your current permission changed. Reloaded access rules are now in effect.</td>
    <td>Current actor role/session evaluation changed.</td>
  </tr>
  <tr>
    <td>Logs empty</td>
    <td>No events matched current filters.</td>
    <td>200 empty events query.</td>
  </tr>
  <tr>
    <td>Logs query error</td>
    <td>Administrative events could not be loaded. Try again.</td>
    <td>Network / temporary service error.</td>
  </tr>
  <tr>
    <td>Detail unavailable</td>
    <td>This event is no longer available for detail view.</td>
    <td>Event detail unavailable / retention projection fault.</td>
  </tr>
  <tr>
    <td>Deleted source</td>
    <td>Source is deleted. See Trash.</td>
    <td>Event source soft-deleted; link only for Admin.</td>
  </tr>
  <tr>
    <td>Projection pending</td>
    <td>Role updated. The event is being indexed for Logs.</td>
    <td>Audit exists; searchable projection pending.</td>
  </tr>
  <tr>
    <td>No further events</td>
    <td>There are no more events in this result set.</td>
    <td>No next_cursor.</td>
  </tr>
</table>

# 8. Buttons, Commands ve State Davranışı

<table>
  <tr>
    <th>UI action</th>
    <th>Command / query</th>
    <th>Precondition + disabled state</th>
    <th>Success / error / audit</th>
  </tr>
  <tr>
    <td>Open Panel &gt; Management</td>
    <td>GET `/v1/admin/users`; GET role matrix; GET system actors.</td>
    <td>Authenticated human Admin. Route hidden/forbidden otherwise.</td>
    <td>Render server projections. Read query itself does not create role audit event.</td>
  </tr>
  <tr>
    <td>Change role select</td>
    <td>Local draft only.</td>
    <td>Admin; row loaded; no request in progress.</td>
    <td>Does not mutate server or write audit. Apply button becomes enabled only when draft differs.</td>
  </tr>
  <tr>
    <td>Apply Role</td>
    <td>PATCH `/v1/admin/users/{id}/role`.</td>
    <td>Admin; target human; valid changed role; expected_head_revision_id fresh; not last-Admin violation. Disabled while pending.</td>
    <td>200 -&gt; row rehydrate + `role_assigned` audit/outbox. 409 -&gt; reload row. 422 -&gt; keep canonical current role. 403 -&gt; deny.</td>
  </tr>
  <tr>
    <td>Open Panel &gt; Logs</td>
    <td>GET `/v1/admin/logs?limit=50`.</td>
    <td>Authenticated human Admin.</td>
    <td>Read-only list; no audit mutation.</td>
  </tr>
  <tr>
    <td>Apply filters</td>
    <td>GET logs with active filter params.</td>
    <td>Admin; valid time range; not duplicate pending request.</td>
    <td>Replaces list with current cursor page. Query does not mutate log history.</td>
  </tr>
  <tr>
    <td>Clear filters</td>
    <td>GET `/v1/admin/logs?limit=50`.</td>
    <td>At least one non-default filter.</td>
    <td>Returns newest events; no audit mutation.</td>
  </tr>
  <tr>
    <td>Load more</td>
    <td>GET logs with same filters + next_cursor.</td>
    <td>Admin; next_cursor exists; no cursor request pending.</td>
    <td>Appends de-duplicated events.</td>
  </tr>
  <tr>
    <td>Open log detail</td>
    <td>GET `/v1/admin/logs/{event_id}`; optionally correlation route.</td>
    <td>Admin; selected row exists.</td>
    <td>Read-only drawer. Detail never displays mutable edit/delete/retry controls.</td>
  </tr>
  <tr>
    <td>Open source deep link</td>
    <td>Resource-specific GET.</td>
    <td>Admin and resource policy allows source view; source must be available.</td>
    <td>Navigation only. Deleted subject shows Deleted / see Trash instead of resource detail.</td>
  </tr>
  <tr>
    <td>Open Trash link</td>
    <td>Separate Trash route.</td>
    <td>Admin only.</td>
    <td>Outside this page scope; no Trash restore/purge logic duplicated here.</td>
  </tr>
</table>

# 9. Kullanıcı Akışları

## 9.1 Başarılı role atama akışı

- Admin Panel > Management açar; Management queryi serverdan human user listesi, versionlar ve role policy matrixini alır.

- Admin hedef kullanıcı satırında Assignable Role dropdownundan Admin, Supervisor veya User seçer. Seçilen değer current role ile aynıysa Apply disabled kalır.

- Admin Apply Role seçer. UI yalnız ilgili satırı loadinge alır ve PATCH requestine `expected_head_revision_id`, transport `If-Match` ve idempotency key ekler.

- Server require_admin, target human, allowed enum, version ve last active Admin korumasını doğrular; atomik role update + audit/outbox event commit eder.

- UI commit edilmiş user projection ile satırı rehydrate eder. Success toast gösterilir. Logs projection outbox dispatcher sonrası `role_assigned` eventini görünür yapar.

## 9.2 Concurrency / stale role row recovery

- İki Admin aynı user satırını farklı expected_row_version ile açar.

- İlk Admin commit eder; version artar ve event oluşur.

- İkinci Admin patchi 409 `USER_ROLE_VERSION_CONFLICT` alır. UI stale local roleu kalıcı gibi göstermez.

- UI current recordu response veya refetch ile yükler, draft selecti canonical valueya resetler ve “This user record was updated by another Admin...” metnini gösterir.

## 9.3 Last active Admin blocker

- Tek active Admin, kendi veya son Admin olan başka kullanıcı satırında Supervisor/User seçer.

- Server 422 `LAST_ADMIN_PROTECTION` döndürür; users.role/version değişmez, role_assigned event oluşmaz.

- UI dropdownu canonical Admin değerine döndürür ve başka bir Admin atama yolunu açıklayan blocker metnini gösterir.

## 9.4 Logs query / detail akışı

- Admin Panel > Logs açar; server latest-first 50 eventlik cursor page döndürür.

- Admin optional filtersi girer; Apply filters server-side query çalıştırır. Browser tüm event tarihçesini yüklemez veya client filter uygulamaz.

- Admin satırı seçer; detail drawer event identity, actor, subject, correlation/cause chain ve safe technical identifiersi okur.

- Subject active değilse row kalır; drawer `Source is deleted. See Trash.` mesajını gösterir. Event edit/delete/retry yapılmaz.

## 9.5 Yetkisiz erişim akışı

- Supervisor, User veya Agent doğrudan Admin Panel route/API çağırır.

- Server `ADMIN_PANEL_ACCESS_REQUIRED` ile reddeder. V18de menu görünür olsa bile Productionda bu route render edilmez.

- Unauthorized actorun browser statei, Agent runtimeı, running backtesti veya historic resourceu bu denemeden etkilenmez.

# 10. Agent Tool/API Eşdeğeri ve Agent Sınırı

Agent, Panel UIya tıklayarak çalışmaz. Agentın autonomous research loopu role registry yönetimi veya Admin Logs UI querylerine bağımlı değildir. Agent kendi task/checkpoint/artifact/run bağlamında Tool Gateway/API ile domain komutlarını çağırır; bu sayfa Agentın işi için zorunlu çalışma ortamı değildir.

<table>
  <tr>
    <th>Konu</th>
    <th>Agentın yapabileceği</th>
    <th>Agentın yapamayacağı / sınır</th>
  </tr>
  <tr>
    <td>Role registry</td>
    <td>Kendi current policy contextini trusted service principal üzerinden okuyabilir; yetki denemeleri audit/event üretiminde actor olabilir.</td>
    <td>Panel Management routeunu açamaz; human user role atayamaz/değiştiremez; Agent role atanamaz/revoke edilemez.</td>
  </tr>
  <tr>
    <td>Logs</td>
    <td>Kendi run/task/artifact eventsini internal observability / event stream üzerinden kullanabilir; system design uygun olduğunda event refs ile provenance kurabilir.</td>
    <td>Admin Panel Logs projectionına UI/API consumer olarak erişmez; insan Admin için tasarlanmış global operational historynin sahibi değildir.</td>
  </tr>
  <tr>
    <td>System actor</td>
    <td>Kendi `actor_type=system_agent`, `actor_id`, task/checkpoint provenanceini taşır.</td>
    <td>Human login accountuna dönüşmez; `registeredUsers` veya assignable role dropdownuna eklenmez.</td>
  </tr>
  <tr>
    <td>Backtest / data / package</td>
    <td>Tool Gateway üzerinden same domain commandlerle Backtest Request, dataset use, package/strategy draft oluşturabilir.</td>
    <td>Paneldeki role edit veya audit log edit mekanizmasını kullanarak domain statei bypass edemez.</td>
  </tr>
  <tr>
    <td>Audit</td>
    <td>Kendi outputlarında actor/reference chain bırakır.</td>
    <td>Audit event silme veya değiştirme; Trash restore/purge; role policy mutasyonu yapamaz.</td>
  </tr>
</table>

# 11. Validation, Hata, Recovery, Lifecycle, Audit ve Trash Etkileri

<table>
  <tr>
    <th>Alan</th>
    <th>Validation / hata kuralı</th>
    <th>Recovery / lifecycle / audit etkisi</th>
  </tr>
  <tr>
    <td>Role target type</td>
    <td>Target yalnız registered human user olmalı. Agent/sistem actor targeti 422 `AGENT_ROLE_NOT_ASSIGNABLE`.</td>
    <td>No role state mutation; no audit role_assigned; Agent runtime state değişmez.</td>
  </tr>
  <tr>
    <td>Role enum</td>
    <td>target_role sadece Admin, Supervisor veya User.</td>
    <td>422 validation; current projection korunur.</td>
  </tr>
  <tr>
    <td>Last active Admin</td>
    <td>Son active Adminin down-role/pasifleme yoluyla admin sayısını sıfıra indiren command reject edilir.</td>
    <td>422 `LAST_ADMIN_PROTECTION`; no mutation / no audit event.</td>
  </tr>
  <tr>
    <td>Optimistic concurrency</td>
    <td>`expected_head_revision_id` / `If-Match` canonical user versionla eşleşmeli.</td>
    <td>409 conflict; UI refetches. Historical role changes ve audit chain yeniden yazılmaz.</td>
  </tr>
  <tr>
    <td>Policy re-evaluation</td>
    <td>Caller Admin roleu request sırasında server session contextinden alınır.</td>
    <td>403 sonrası local controls security proof değildir. Current actor self-demote ettiyse next request policy yeni role ile çözülür.</td>
  </tr>
  <tr>
    <td>Audit integrity</td>
    <td>Logs row/audit event mutable değildir. Correction gerekiyorsa causation_event_id ile yeni annotation/correction event üretilir.</td>
    <td>Old event korunur; Logs projection append-only.</td>
  </tr>
  <tr>
    <td>Log source lifecycle</td>
    <td>Subject soft-deleted olabilir; event historical kanıt olarak kalır.</td>
    <td>Detailde Deleted/Trash ref; source restore edilirse original subject route tekrar erişilebilir olabilir.</td>
  </tr>
  <tr>
    <td>Trash</td>
    <td>Panel içinde yalnız navigation / visibility summary.</td>
    <td>Role change, Logs query veya System Actor cardı Trash entry üretmez. Restore/purge davranışı Sayfa 20 ve Modül 3 source of truthudur.</td>
  </tr>
  <tr>
    <td>Outbox / projection fault</td>
    <td>Role command commit edildiği halde Logs projection gecikebilir.</td>
    <td>Outbox retry duplicate role event üretmeden projectionu tamamlar; UI projection pending note gösterir.</td>
  </tr>
  <tr>
    <td>No log history edit</td>
    <td>Admin geçmiş logu “düzeltmek” için patch/delete kullanamaz.</td>
    <td>Yeni correction/annotation event ile causation zinciri oluşur; original immutable record korunur.</td>
  </tr>
</table>

# 12. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>Konu</th>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>Panel visibility</td>
    <td>Admin, Supervisor ve Agent için demo menu visibility; trash only Admin.</td>
    <td>Panel, Management, Logs ve Trash yalnız Admin human principal.</td>
    <td>Master Modül 16 canonical rule uygulanır. V18 `canAccessSystemWorkspace()` Production policy olarak taşınmaz.</td>
  </tr>
  <tr>
    <td>Agent login</td>
    <td>`agent` / `agent-research-01` demo login ile UI role simülasyonu.</td>
    <td>Agent internal runtime/service principal; human session/login değil.</td>
    <td>V18 demo login kaldırılır; System Actor read-only projection korunur.</td>
  </tr>
  <tr>
    <td>Role update</td>
    <td>Local `registeredUsers[index].role` mutation; no persistence/version/audit.</td>
    <td>Atomic user update, version check, audit/outbox, canonical response.</td>
    <td>V18 Apply label preserved; command server authoritative olur.</td>
  </tr>
  <tr>
    <td>Management user table</td>
    <td>Static admin/supervisor/user list.</td>
    <td>Paged human user registry from `GET /v1/admin/users`.</td>
    <td>Agent list dışında kalır; user account deletion/creation scope dışı.</td>
  </tr>
  <tr>
    <td>Role Scope Matrix</td>
    <td>Hard-coded role scope prose.</td>
    <td>Canonical policy projection / role matrix endpoint.</td>
    <td>Client string source of truth olmaz; matrix versioned policyden gelir.</td>
  </tr>
  <tr>
    <td>Logs content</td>
    <td>Only backtestHistory metrics table; fake user alternation by index.</td>
    <td>Append-only domain/audit event projection; actor, subject, correlation, severity.</td>
    <td>Metrics Results domaininde kalır; Logs onlara stable reference verir.</td>
  </tr>
  <tr>
    <td>Filters/pagination/detail</td>
    <td>Yok.</td>
    <td>Server filters, `limit=50`, opaque cursor, drawer detail, correlation chain.</td>
    <td>Implementation Decision: right detail drawer, not modal, to preserve filtered list context.</td>
  </tr>
  <tr>
    <td>Logs mutation</td>
    <td>V18 no edit controls.</td>
    <td>No event patch/delete; correction new event.</td>
    <td>V18 read-only direction preserved and strengthened.</td>
  </tr>
  <tr>
    <td>Trash relationship</td>
    <td>Visibility card and menu item.</td>
    <td>Admin-only separate resource/lifecycle area.</td>
    <td>Trash contents, restore/purge commands this docun scopeu dışında kalır.</td>
  </tr>
</table>

# 13. Kodcu AI İçin Kesin Implementation Rules

- Paneli günlük çalışma alanı olarak değil, yalnız Admin-only yönetim ve operasyonel gözlem yüzü olarak uygula.

- Productionda Panel, Management ve Logs route/endpointlerini yalnız authenticated human Admin principal için server-side guard ile koru. UI hidden state authorization yerine geçmez.

- Managemente yalnız registered human userları koy; Agentı `system_agent` read-only projection olarak göster. Agent dropdownuna, user tableına veya revoke flowuna ekleme.

- Assignable Role alanını yalnız `Admin | Supervisor | User` enumuyla uygula. Agent bir human role değildir.

- Role save işleminde `expected_head_revision_id` + HTTP `If-Match` kullan; role rowunu client-side array değişimiyle kalıcı sayma.

- Role mutationını transaction lock, last active Admin protection, audit/outbox event ve committed response zinciri olmadan tamamlanmış sayma.

- Role changein owner transferi, historical manifest rewrite, created_by rewrite veya historic audit mutationı olmadığını hem backend hem UI davranışında koru.

- Logs kaynağını append-only domain/audit eventlerden oluştur. Logs projectionunu raw source object yerine geçecek mutable tablo olarak tasarlama.

- Canonical Log Eventte event_id, occurred_at, event_kind, severity, actor, subject, correlation_id, causation_event_id ve message alanlarını zorunlu tut.

- Logs listesinde browsera tüm geçmişi yükleme. Server-side filter + newest-first + limit=50 + opaque cursor pagination uygula.

- Log detailde raw secrets, full dataset, full strategy JSON veya mutable remediation controls gösterme. Stable ref/deep link ve safe technical identifiers kullan.

- Soft-deleted subjecte bağlı eventleri silme. Event detailde Deleted / see Trash stateini göster; Trash linkini yalnız Admin policy ile aç.

- Log/audit event edit/delete actionı ekleme. Düzeltme gerekiyorsa causation_event_id ile linked new correction/annotation event üret.

- Role update success sonrası UIyi canonical API response ile rehydrate et; log projection eventual consistency durumunu duplicate event üretecek client retry ile çözme.

- Agentı Panel erişimine veya human role registryye bağlama. Agent runtime, kendi Tool Gateway/queue/checkpoint/artifact çevrimini Panel UI kapalıyken de sürdürür.

- Trash, identity hardening, user account deletion veya role-independent security grant modelleri için bu sayfada yeni behavior icat etme; ilgili Master modüllerine bağlı kal.

# 14. Acceptance Tests

- Guest, User, Supervisor ve Agent Production `/v1/admin/users`, `/v1/admin/logs` veya Panel routeuna erişmeye çalıştığında server 403/401 döndürür; yalnız menu visibility ile korunmuş sayılmaz.

- Admin Paneli açtığında Management, Logs ve Trash navigation linkini görür; Trash logic ayrı sayfa scopeunda kalır.

- Management registry yalnız human userları döndürür; Agent System Actor kartında read-only görünür ve assignable role selectinde yer almaz.

- Role dropdown yalnız Admin, Supervisor ve User seçeneklerini içerir; Agent seçeneği yoktur.

- Admin human Userı Supervisor yaptığında user version artar, `role_changed_at/by` güncellenir, committed response döner ve `role_assigned` audit/outbox event oluşur.

- Role change sonucunda target userun owner, created_by, existing strategy/package/dataset ownershipi veya historic manifest initiated_by bilgisi değişmez.

- Agent target idsiyle yapılan role update `AGENT_ROLE_NOT_ASSIGNABLE` döndürür; Agent statei, taski ve checkpointi değişmez.

- Sistemde tek active Admin kaldığında onun roleunu Supervisor veya User yapma isteği `LAST_ADMIN_PROTECTION` ile reddedilir; mutation/audit oluşmaz.

- İki Admin aynı userı farklı expected_row_version ilerla güncellediğinde yalnız bir transaction commit olur; diğeri `USER_ROLE_VERSION_CONFLICT` alır ve UI current server rowu yükler.

- Current Admin kendi roleunu downgrade ederse success commitinden sonra sonraki requestte admin authorization yoktur ve UI Panelden restricted statee geçer.

- Logs first query newest-first en fazla 50 event ve opaque next_cursor döndürür; browser bütün audit geçmişini indirmez.

- Logs filter query severity=ERROR, family=backtest, time range, actor, resource_type, correlation_id ve q parametrelerini serverda uygular; client-side filterden authoritative sonuç üretilmez.

- Bir backtest worker failure eventinde Logs row event_kind=backtest_failed, subject=backtest_run, correlation/job/trace referanslarıyla görünür; failed run için Result artifacti uydurulmaz.

- Admin role değişikliği sonra Logs projectionda `role_assigned` eventini correlation id ile görür; projection gecikirse duplicate audit event oluşmaz.

- Log detail drawer actor, subject, UTC occurrence, severity, event kind, correlation/cause chain ve safe identifiersi gösterir; edit/delete/retry/rerun buttonu içermez.

- Soft-deleted Strategy veya Packagee bağlı historical log event görünmeye devam eder; detailde Deleted / see Trash statei çıkar.

- Log event ve audit event için PATCH/DELETE UI/API actionı yoktur; correction yeni linked eventle temsil edilir.

- V18 demo Supervisor/Agent Panel erişimi Productionda taşınmaz; Agent Analysis Lab veya Tool Gateway işini Panel access olmadan devam ettirir.

- Role matrix ekranı hard-coded client policyye dayanmaz; canonical policy projectionı serverdan gelir ve edit edilemez.

- Page rendered state loading, empty, forbidden, stale conflict, last-Admin blocker, deleted source ve outbox projection pending metinlerini tanımlandığı gibi gösterir.

# 15. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç / bu dokümandaki garanti</th>
  </tr>
  <tr>
    <td>Master üstünlüğü</td>
    <td>Modül 16 Admin-only Panel policysi, V18 demo Supervisor/Agent accessin üzerinde uygulanmıştır.</td>
  </tr>
  <tr>
    <td>Terminoloji</td>
    <td>Human user, Agent system actor, role assignment, audit event, log projection, correlation, causation ve soft delete canonical anlamda kullanılmıştır.</td>
  </tr>
  <tr>
    <td>V18 / Production ayrımı</td>
    <td>V18 local array role mutationı, fake backtest metrics logu ve demo role switch açıkça Prototype olarak ayrılmıştır.</td>
  </tr>
  <tr>
    <td>Run / Result</td>
    <td>Logs failed/cancelled runu event olarak gösterebilir; yalnız succeeded run immutable Result üretir.</td>
  </tr>
  <tr>
    <td>Agent sınırı</td>
    <td>Agent Panel/role registryye bağlı değildir; UIless Tool Gateway eşdeğeri korunmuştur.</td>
  </tr>
  <tr>
    <td>Trash sınırı</td>
    <td>Trash only Admin ve event retention bağlamında anılmış; restore/purge ayrı sayfanın scopeuna bırakılmıştır.</td>
  </tr>
  <tr>
    <td>State / concurrency</td>
    <td>Role mutation expected_head_revision_id + If-Match; logs cursor pagination; audit append-only; source of truth backend olarak tanımlanmıştır.</td>
  </tr>
  <tr>
    <td>Future Dev sınırı</td>
    <td>Live Trade, external security hardening veya yeni identity products için aktif behavior eklenmemiştir.</td>
  </tr>
</table>
