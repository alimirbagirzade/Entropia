---
title: "Entropia V18 — Analysis Lab Page Documentation v1.1"
page_number: 18
document_type: "Page implementation specification"
source_document: "Entropia_V18_Analysis_Lab_Page_Documentation_v1_1.docx"
format: "Lossless Markdown/HTML-table conversion"
---

# Entropia V18 — Analysis Lab Page Documentation v1.1

## Source Layout Metadata

> **Original DOCX header:** ENTROPIA V18
> **Original DOCX footer:** ENTROPIA V18 | Analysis Lab | Sayfa Dokümantasyonu 18/22 | Production V1 uygulama sözleşmesi

ENTROPIA V18

ANALYSIS LAB

Sayfa Dokümantasyonu 18/22 | Alpha Agent gözlem yüzeyi, Lab Assistant, directive kuyruğu, checkpoint ve kalıcı research output sözleşmesi

# 0. Document Control, Scope ve Source Traceability

Bu belge yalnız Agent Workspace içindeki Analysis Lab sayfasını tanımlar. Analysis Lab; Alpha Agentın durumunu, veri bağlamını, work queueyu, Lab Assistant konuşmasını ve kalıcı hypothesis/outputlarını görünür yapan operasyon yüzeyidir. Sayfa; Research Data registry yönetimini, Create Package üretim hattını, Backtest Ready Check detaylarını, sonuç ekranını veya Panel/Logs yönetim ekranını yeniden tasarlamaz. Bu alanlar yalnız Analysis Labin referans aldığı context, task, artifact veya command bağımlılığı olarak anılır.

<table>
  <tr>
    <th>Kilit mimari kararı. Alpha Agent server-side çalışan sürekli bir sistem aktörüdür. Analysis Lab, Agentın runtimeı veya zorunlu çalışma ortamı değildir; UI yalnız gözlem, konuşma, güvenli directive ve istisnai Admin lifecycle kontrol yüzeyidir. Browser kapansa, kullanıcı logout olsa veya Lab hiç açılmasa bile Coordinator, Queue, Checkpoint Store ve Artifact Store üzerindeki Agent döngüsü sürer.</th>
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
    <td>Modül 14 §§1-18; Canonical Integration CR-02 ve CR-04</td>
    <td>Alpha Agent/Lab Assistant ayrımı, Agent Workspace UI sözleşmesi, roller, queue, checkpoint, task/artifact modeli, tool gateway, API, event, hata, acceptance test ve Agent governance sınırları.</td>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0</td>
    <td>Modül 0 §§5-9; Modül 1 §§5-10; Modül 2-3; Modül 5/15; Modül 12-13; Modül 19-20</td>
    <td>Sürekli Agent ilkesi, server-side policy, root/revision/snapshot, soft delete/Trash, data bundle timing, Ready Check/Run/Result ayrımı, API/SSE ve worker altyapısı.</td>
  </tr>
  <tr>
    <td>V18 ana HTML</td>
    <td>Agent Workspace &gt; Analysis Lab; `analysisLabState`; `renderAnalysisLabPage`; `sendAnalysisLabMessage`; `sendAnalysisLabDirective`; `toggleAnalysisLabPause`; `stopAnalysisLabRun`</td>
    <td>Gerçek görünen paneller, etiketler, V18 default/demo state, textarea placeholderı, Directive Priority seçenekleri, button visibility ve prototype local davranışı.</td>
  </tr>
  <tr>
    <td>Sayfa Bazlı Dokümantasyon Handoff v1.1</td>
    <td>§§4-13; Analysis Lab özel dikkat notu</td>
    <td>Source traceability, interaction/field/content matrisleri, V18-Production ayrımı, Agent parity, lifecycle, audit ve acceptance test standardı.</td>
  </tr>
  <tr>
    <td>2.3. POSITION ENTRY LOGIC örnek dokümanı</td>
    <td>Anlatım derinliği referansı</td>
    <td>Kavramların canonical kısa tanımı, dependency/validation ayrımı, backend-karar izi ve kodcu AI için test edilebilir implementation rule dili.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam içi</th>
    <th>Kapsam dışı / yalnız çapraz referans</th>
  </tr>
  <tr>
    <td>Agent runtime overview, Lab Context, conversation, message/directive ayrımı, Work Queue, Hypothesis &amp; Output Board, Admin Pause/Resume ve Stop Current Run kontrolü; task/checkpoint/artifact read model ve event projectionları.</td>
    <td>Research Dataset yaratma/approval; Market Data ingestion; Package approval/publish; Strategy Details formu; Backtest Ready Check kural listesinin ayrıntıları; Backtest Result metrik ekranı; Panel role yönetimi; Trash ekranı.</td>
  </tr>
  <tr>
    <td>Labın ilgili data/package/result referanslarını manifest/provenance üzerinden gösterme; Agent Tool Gateway eşdeğeri; directive, checkpoint, queue ve lifecycle command sözleşmesi.</td>
    <td>Live trade, broker/exchange emir gönderimi, permission-free automation, Agentın Admin yetkilerini devralması, kullanıcı role/Trash yönetimi veya Future Dev capability activation.</td>
  </tr>
</table>

# 1. Amaç, Sistem İçindeki Yer ve Kavramsal Sınır

Analysis Lab, Entropia araştırma döngüsünün görünür koordinasyon ve inceleme yüzeyidir. Kullanıcı burada Alpha Agentın hangi araştırma görevi üzerinde bulunduğunu, hangi pinlenmiş data bundleını kullandığını, hangi follow-up işleri beklettiğini, son checkpointini, kalıcı hypothesis/artifactlerini ve Lab Assistantın kaydedilmiş bağlama dayalı açıklamalarını görür. Bu nedenle Lab bir chat arayüzünden daha fazlasıdır; fakat Agentın asıl akıl yürütme/runtime katmanı değildir.

<table>
  <tr>
    <th>Kavram</th>
    <th>Canonical tanım</th>
    <th>Analysis Lab etkisi</th>
  </tr>
  <tr>
    <td>Alpha Agent</td>
    <td>Hipotez, data, strategy/package taslağı, ready check, backtest ve sonuç yorumu döngüsünü backend üzerinde sürekli sürdüren non-login sistem aktörü.</td>
    <td>Üst şeritte status/current task olarak görünür; UI açık kalmadan çalışır.</td>
  </tr>
  <tr>
    <td>Lab Assistant</td>
    <td>Alpha Agentın son checkpointi, active taskı, context manifesti, queue ve artifactleri üzerinden insanla konuşan görünür yardımcı katman.</td>
    <td>Conversation panelindeki assistant response üreticisidir; Alpha Agentın yerine job kontrolü veya gizli reasoning trace gösterimi yapmaz.</td>
  </tr>
  <tr>
    <td>Normal discussion</td>
    <td>Kullanıcının soru/yorum/inceleme mesajı.</td>
    <td>Lab Assistant hemen yanıtlar; active task, stage, progress ve queue sırası değişmez.</td>
  </tr>
  <tr>
    <td>Queued directive</td>
    <td>Admin veya Supervisor tarafından gönderilen Normal/High öncelikli, durable research direction kaydı.</td>
    <td>Task Directive olarak persistencea yazılır; yalnız sonraki safe checkpointte Agent Coordinator tarafından tüketilebilir.</td>
  </tr>
  <tr>
    <td>Safe checkpoint</td>
    <td>Plan, context, yapılan adımlar, artifact referansları ve resume bilgisinin tutarlı biçimde kaydedildiği müdahale güvenli noktadır.</td>
    <td>Directive consume, controlled pause, stop veya restart güvenli sınırda yürür; aktif worker içine çıplak prompt enjekte edilmez.</td>
  </tr>
  <tr>
    <td>Context manifest</td>
    <td>Taskin Market/Research Data revisionlarını, available-time/usage scope sonuçlarını, package/strategy referanslarını ve policy snapshotını sabitleyen immutable bağlam kaydı.</td>
    <td>Active Data Bundle serbest metin değildir; manifestten türetilen read-only kısa görünümüdür.</td>
  </tr>
  <tr>
    <td>Hypothesis artifact</td>
    <td>Mechanism, evidence, data context, status, next action ve source task/checkpoint bağlarını taşıyan kalıcı araştırma çıktısı.</td>
    <td>Output Board chat kartı değildir; ayrı artifact query ile listelenir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Kapsam sınırı. Analysis Lab gerçek zamanlı trade execution ekranı değildir. Agent bu sayfadan doğrudan broker hesabına emir göndermez; dataset approval, Trash, role management, canonical package publish/approval veya live trade başlatma yetkisi kazanmaz. Agent özerkliği ile governance ayrı policy katmanlarıdır.</th>
  </tr>
</table>

# 2. Erişim, Görünürlük, Ownership ve Server-Side Yetki

V18de Agent Workspace menüsünün görünmesi veya bir kontrolün disabled olması yetki kanıtı değildir. Her overview, message, directive, pause, stop, task detail ve artifact querysi server-side principal, operation, lifecycle, resource visibility ve Agent policy üzerinden yeniden doğrulanır. Client request body içindeki `role`, `isAdmin`, `status`, `task_id` veya `target_agent_id` alanları kendi başına otorite kabul edilmez.

<table>
  <tr>
    <th>Principal / rol</th>
    <th>Sayfayı görme</th>
    <th>Normal message</th>
    <th>Queued directive</th>
    <th>Pause / Resume / Stop</th>
    <th>Output ve Agent sınırı</th>
  </tr>
  <tr>
    <td>Guest / anonymous</td>
    <td>Hayır. Protected route açılırsa authentication/access denial.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Agent state, task veya artifact sızdırılmaz.</td>
  </tr>
  <tr>
    <td>User</td>
    <td>Hayır. V18de “Admin, Supervisor or Agent access required.” görünür.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Hayır.</td>
    <td>Kendi erişimi olan başka domain objelerini kullanabilir; Analysis Lab APIsine erişemez.</td>
  </tr>
  <tr>
    <td>Supervisor</td>
    <td>Evet; shared operations read scope.</td>
    <td>Evet. Discussion kaydı oluşturur.</td>
    <td>Evet. Normal veya High directive gönderebilir.</td>
    <td>Hayır.</td>
    <td>Lab overview/task/artifactleri policy filtrasyonuyla görür; başka ownerın normal resourceunu mutate etmez.</td>
  </tr>
  <tr>
    <td>Admin</td>
    <td>Evet.</td>
    <td>Evet.</td>
    <td>Evet.</td>
    <td>Evet; controlled lifecycle command yalnız safe checkpoint/cancel-safe boundaryde uygulanır.</td>
    <td>Full operational oversight; Agent outputlarını normal Admin policy ile yönetebilir.</td>
  </tr>
  <tr>
    <td>Agent</td>
    <td>Human login/UI şartı yok. Internal runtime/service identity ile kaynaklara erişir.</td>
    <td>N/A; Lab Assistant farklı bileşendir.</td>
    <td>N/A; insan directive tüketicisidir.</td>
    <td>N/A; kendi lifecycleını human UI üzerinden yönetmez.</td>
    <td>Kendi outputunu üretir/mutate eder; dataset approval, Trash, role management ve canonical publish/approval yapamaz.</td>
  </tr>
</table>

Authorization sonucu UI düzeninden bağımsızdır. Örneğin Supervisorın `Send as Directive` düğmesini görmesi, Stop endpointine erişebileceği anlamına gelmez. Aynı şekilde Userın doğrudan `/agent-workspace/overview` çağrısı 403/uygun policy denial almalı; response hiçbir queue, checkpoint, artifact veya data bundle detayı döndürmemelidir.

# 3. V18 Interface Behavior: Gerçek Arayüz Yerleşimi ve Görünür Bileşenler

V18de Analysis Lab, üst menüde Agent Workspace altından açılır. Uygun erişime sahip kullanıcıda page title `AGENT WORKSPACE / ANALYSIS LAB` olur. Ekran; giriş açıklama kutusu, üst durum şeridi, üç kolonlu panel düzeni ve altında Hypothesis & Output Boarddan oluşur. Genişlik 1120px altına düştüğünde grid tek kolona iner; mesaj alanının üst sınırı kaldırılır ve output kartları tek kolonda gösterilir.

<table>
  <tr>
    <th>Bölge</th>
    <th>V18 görünür içeriği</th>
    <th>V18 default / görünme koşulu</th>
    <th>Production karşılığı</th>
  </tr>
  <tr>
    <td>Analysis Lab intro</td>
    <td>“Analysis Lab is the operational research environment...” açıklaması; Lab Assistant ile Alpha Agent ayrımı.</td>
    <td>Sayfa erişilebiliyorsa her zaman görünür.</td>
    <td>Read-only architecture helper; server responsea değil static product copyye dayanır.</td>
  </tr>
  <tr>
    <td>Top status bar</td>
    <td>ALPHA AGENT; ACTIVE/PAUSED pill; CONTINUOUS MODE tag; `Current work: ...`; Admin için Pause/Resume ve Stop Current Run.</td>
    <td>Demo default: ACTIVE, Continuous, high-funding BTCUSDT reversal araştırması. Admin dışı kullanıcıda “Run controls: Admin only”.</td>
    <td>`agent_runtime` + `active_task` projection; lifecycle command policy.</td>
  </tr>
  <tr>
    <td>LAB CONTEXT</td>
    <td>PRIMARY MISSION; ACTIVE DATA BUNDLE; Instrument mapping/Available-time/Dataset versions checks; SAFE CHECKPOINT RULE; AGENT BOUNDARIES.</td>
    <td>READ ONLY tag ile her erişilebilir sayfada görünür.</td>
    <td>`context_manifest` + policy snapshot + validation projection.</td>
  </tr>
  <tr>
    <td>LAB CONVERSATION</td>
    <td>LAB ASSISTANT tag; assistant/system/directive/message bubbles; timestamp; textarea; Send Message; Directive Priority select; Send as Directive; helper note.</td>
    <td>Textarea boş. Priority default Normal. Directive controls yalnız Admin/Supervisor için enabled.</td>
    <td>`lab_message`, `task_directive`, `agent_event`, Lab Assistant response query/commandleri.</td>
  </tr>
  <tr>
    <td>WORK QUEUE</td>
    <td>Current Task title, stage/progress; task cards title/source/priority/status; count tag.</td>
    <td>Demo: 3 items; one Running, two Queued.</td>
    <td>`agent_task` ve coordinator queue projectionı.</td>
  </tr>
  <tr>
    <td>HYPOTHESIS &amp; OUTPUT BOARD</td>
    <td>Exploring/Testing/Candidate status; Title, Mechanism, Data, Next action.</td>
    <td>Demo: üç hypothesis artifact cardı.</td>
    <td>`hypothesis_artifact` + evidence/artifact links querysi.</td>
  </tr>
</table>

## 3.1 V18 top bar ve run control görünürlüğü

<table>
  <tr>
    <th>Kontrol / label</th>
    <th>V18 davranışı</th>
    <th>Görünme koşulu</th>
    <th>Not</th>
  </tr>
  <tr>
    <td>ALPHA AGENT</td>
    <td>Sabit başlık.</td>
    <td>Sayfa erişilebiliyorsa görünür.</td>
    <td>Productionda registrydeki Agent display name olabilir; runtime identity ile karıştırılmaz.</td>
  </tr>
  <tr>
    <td>ACTIVE / PAUSED</td>
    <td>Status pill.</td>
    <td>Runtime statusa göre active veya paused CSS class.</td>
    <td>Production API lowercase snake_case döndürür; UI `ACTIVE`/`PAUSED` label mapini registryden üretir.</td>
  </tr>
  <tr>
    <td>CONTINUOUS MODE</td>
    <td>Mode tag.</td>
    <td>Demo default Continuous.</td>
    <td>Mode read-only runtime/policy stateidir; kullanıcı dropdownı değildir.</td>
  </tr>
  <tr>
    <td>Pause / Resume</td>
    <td>Button label statusa göre değişir.</td>
    <td>Yalnız Admin.</td>
    <td>Pause request safety checkpointte tamamlanır; tek click anlık durma değildir.</td>
  </tr>
  <tr>
    <td>Stop Current Run</td>
    <td>Button.</td>
    <td>Yalnız Admin.</td>
    <td>Controlled cancellationdır; completed Backtest Result oluşturmaz.</td>
  </tr>
  <tr>
    <td>Run controls: Admin only</td>
    <td>Read-only status metni.</td>
    <td>Admin olmayan erişebilir kullanıcılar.</td>
    <td>Supervisor directive gönderebilir, lifecycle command gönderemez.</td>
  </tr>
</table>

## 3.2 Lab Conversation gerçek alanları

<table>
  <tr>
    <th>Alan / kontrol</th>
    <th>UI tipi / V18 default</th>
    <th>Zorunluluk ve bağımlılık</th>
    <th>V18 seçenekleri / Production payload</th>
  </tr>
  <tr>
    <td>Conversation message input</td>
    <td>Textarea; başlangıçta boş; min-height 88px; resize vertical.</td>
    <td>Send Message veya Send as Directive tetiklenirse boş/whitespace olamaz. Aynı text iki farklı semantic commandde kullanılabilir.</td>
    <td>Placeholder: “Ask Lab Assistant about current work, data, findings or outputs. Use Send as Directive only for a queued research task.” Payload: `text`.</td>
  </tr>
  <tr>
    <td>Directive Priority</td>
    <td>Select; default `Normal`.</td>
    <td>Yalnız Send as Directive için zorunlu. User/Agent/UI-disallowed principal için disabled.</td>
    <td>V18: Normal, High. Production enum: `normal | high`; `autonomous` insan tarafından seçilemez.</td>
  </tr>
  <tr>
    <td>Send Message</td>
    <td>Button.</td>
    <td>Textarea non-empty; caller Admin veya Supervisor olmalıdır.</td>
    <td>`POST /lab/messages` =&gt; discussion_message; active task değişmez.</td>
  </tr>
  <tr>
    <td>Send as Directive</td>
    <td>Button.</td>
    <td>Textarea non-empty + priority + Admin/Supervisor policy.</td>
    <td>`POST /agent-directives` =&gt; task_directive, queue ref, 202 Accepted.</td>
  </tr>
  <tr>
    <td>Conversation cards</td>
    <td>Read-only cards with type/tag/time/text.</td>
    <td>N/A.</td>
    <td>Types: assistant, message, directive, system; canonical persisted types §9.</td>
  </tr>
</table>

V18 ekranında görünür ⓘ ikonları, modal dialog veya ayrı filter/sort toolbarı yoktur. Bu nedenle bilgiyi açıklayan gerçek içerik intro, Lab Context ve compose helper note içinde yer alır. Productionda erişilebilirlik için bu bilgi metinleri kısaltılmamalı; control açıklamaları `aria-describedby` ile bağlanmalı ve command sonuçları `aria-live` bölgesinde duyurulmalıdır.

# 4. Interaction State Matrix

<table>
  <tr>
    <th>Bileşen</th>
    <th>Varsayılan / aktifleşme</th>
    <th>Disabled / loading davranışı</th>
    <th>Payload / runtime etkisi</th>
    <th>Recovery / kullanıcı metni</th>
  </tr>
  <tr>
    <td>Page overview</td>
    <td>Authorized Admin/Supervisor için initial loading; Agent internal UI-less.</td>
    <td>Skeleton/loading; stale cached task status source of truth değildir.</td>
    <td>GET overview + task/artifact queries; SSE yalnız refresh sinyalidir.</td>
    <td>“Loading Analysis Lab state...” sonra canonical projection render edilir.</td>
  </tr>
  <tr>
    <td>Top status bar</td>
    <td>Demo ACTIVE/Continuous; production runtime status.</td>
    <td>Pause/Stop command pending iken related controls disabled; status optimistic final sayılmaz.</td>
    <td>Lifecycle command accepted; runtime state worker/coordinator eventinden değişir.</td>
    <td>“Pause requested. Alpha Agent will pause after the next safe checkpoint.”</td>
  </tr>
  <tr>
    <td>Lab Context</td>
    <td>Read only.</td>
    <td>Her zaman non-editable; missing manifestte warning.</td>
    <td>Serbest input payloadı üretmez; context manifestten derive edilir.</td>
    <td>“Current context is unavailable. Reload the latest Agent state.”</td>
  </tr>
  <tr>
    <td>Textarea</td>
    <td>Empty, editable.</td>
    <td>Message/directive submit pendingde duplicate submit disabled; textarea value korunur.</td>
    <td>Text only successful command sonrası persisted message/directive olur.</td>
    <td>422de text korunur; inline validation gösterilir.</td>
  </tr>
  <tr>
    <td>Directive Priority</td>
    <td>Normal, enabled only Admin/Supervisor.</td>
    <td>User/Agent visible UI stateinde disabled; message button değil directive button disabled.</td>
    <td>Sadece directive payloadına `priority` girer.</td>
    <td>403de server denial; UI local disable security yerine geçmez.</td>
  </tr>
  <tr>
    <td>Work Queue</td>
    <td>Current task + queue cards.</td>
    <td>Queue refresh pendingde cards read-only; task currently checkpointing/paused can show transient state.</td>
    <td>Task state coordinator gerçeğidir; browser arrayi değil.</td>
    <td>Waiting/Fault reason göster; SSE reconnect sonrası query refetch.</td>
  </tr>
  <tr>
    <td>Hypothesis Board</td>
    <td>Accessible artifact cards.</td>
    <td>Artifact detail loading or stale state; no fake card.</td>
    <td>Artifact output chatten ayrı persists.</td>
    <td>“No persistent hypotheses or outputs match this context yet.”</td>
  </tr>
  <tr>
    <td>Pause/Resume</td>
    <td>Admin only; active command.</td>
    <td>Disabled if lifecycle command already pending or runtime not eligible.</td>
    <td>`lifecycle_command` -&gt; coordinator checkpoint request.</td>
    <td>409 state conflict: “Runtime state changed. Reload before sending another control command.”</td>
  </tr>
  <tr>
    <td>Stop Current Run</td>
    <td>Admin only; available when stoppable current agent sub-run exists.</td>
    <td>Disabled when no active stoppable run, already cancelling, or paused without sub-run.</td>
    <td>Controlled cancellation; last checkpoint/partial diagnostics survive; no cancelled Result.</td>
    <td>“Stop requested. The current run will end at a cancellation-safe boundary.”</td>
  </tr>
</table>

# 5. Field Contract Matrix: Alanlar, Varsayılanlar, Zorunluluk ve Dependency

Analysis Lab klasik bir entity edit formu değildir. V18de `*` işaretli görünür alan yoktur. Buna rağmen submit yapılınca text ve directive priority contractı server-side zorunludur. Yıldız standardı Productionda aşağıdaki şekilde uygulanır: Textarea etiketi “Message *” olur; user `Send as Directive` moduna geçerse “Directive Priority *” etiketi görünür. V18de label görünmüyorsa da validation aynı şekilde çalışır.

<table>
  <tr>
    <th>Alan</th>
    <th>V18 observed default</th>
    <th>Production effective default</th>
    <th>Requiredness / dependency</th>
    <th>Validation</th>
  </tr>
  <tr>
    <td>Runtime status</td>
    <td>ACTIVE demo.</td>
    <td>Server projectiondan gelen `active | paused | stopping | recovering` UI aliası.</td>
    <td>Read-only; submit alanı değildir.</td>
    <td>Unknown status fail-open olmaz; `Unavailable` + event/retry gösterilir.</td>
  </tr>
  <tr>
    <td>Mode</td>
    <td>Continuous demo.</td>
    <td>Runtime registry/policyden derive.</td>
    <td>Read-only.</td>
    <td>Kullanıcıdan mode override alınmaz.</td>
  </tr>
  <tr>
    <td>Current task</td>
    <td>High-funding BTCUSDT task demo.</td>
    <td>`active_task_id` üzerinden task read model.</td>
    <td>Read-only; no task direct mutation.</td>
    <td>Task visibility/policy rechecked on detail query.</td>
  </tr>
  <tr>
    <td>Active Data Bundle</td>
    <td>Market v1.0 + Funding v1.0 + OI v1.0 demo.</td>
    <td>Immutable `context_manifest_id` özeti.</td>
    <td>Read-only; dataset selection alanı değildir.</td>
    <td>Approved status, usage scope, mapping, available-time, exact revision kontrolü context compiler/Tool Gatewaydedir.</td>
  </tr>
  <tr>
    <td>Message Text *</td>
    <td>Empty textarea.</td>
    <td>Empty until caller enters non-whitespace text.</td>
    <td>Send Message veya Send as Directive ile koşullu zorunlu.</td>
    <td>Trimmed text non-empty; max length and content policy schema; duplicate idempotency/retry safe.</td>
  </tr>
  <tr>
    <td>Directive Priority *</td>
    <td>Normal.</td>
    <td>`normal`.</td>
    <td>Sadece Send as Directivede koşullu zorunlu.</td>
    <td>`normal | high`; caller must Admin/Supervisor; autonomous rejected for human call.</td>
  </tr>
  <tr>
    <td>Directive target context</td>
    <td>V18de implicit active Alpha Agent; related task UIda ayrı alan değil.</td>
    <td>`target_agent_id`, optional `related_task_id` and `context` object.</td>
    <td>Directive creationda target agent zorunlu; related task optional.</td>
    <td>Target active/eligible; directive no direct worker injection; expected runtime context checked.</td>
  </tr>
  <tr>
    <td>Queue status</td>
    <td>Running / Queued demo.</td>
    <td>`queued | running | waiting | checkpointing | paused | succeeded | failed | cancelled`.</td>
    <td>Read-only.</td>
    <td>UI unknown statusu arbitrary success pill yapmaz; server enum contract.</td>
  </tr>
  <tr>
    <td>Hypothesis status</td>
    <td>Testing / Exploring / Candidate demo.</td>
    <td>`exploring | testing | candidate | rejected | archived` registry status.</td>
    <td>Read-only UI in V18; structured mutation separate artifact command.</td>
    <td>Status transition evidence/task/checkpoint policy ile doğrulanır.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Send discussion message<br/>POST /lab/messages<br/>{<br/>  &quot;text&quot;: &quot;Which dataset revisions are pinned for the current robustness check?&quot;,<br/>  &quot;related_task_id&quot;: &quot;agt_task_...&quot;,<br/>  &quot;idempotency_key&quot;: &quot;...&quot;<br/>}<br/><br/>Queue directive<br/>POST /agent-directives<br/>{<br/>  &quot;text&quot;: &quot;After the current robustness run completes, add a low-volatility regime split.&quot;,<br/>  &quot;priority&quot;: &quot;high&quot;,<br/>  &quot;target_agent_id&quot;: &quot;alpha-agent&quot;,<br/>  &quot;context&quot;: {&quot;related_task_id&quot;: &quot;agt_task_...&quot;},<br/>  &quot;idempotency_key&quot;: &quot;...&quot;<br/>}<br/><br/>HTTP transport: If-Match / ETag only for mutable runtime control or correction resources; directive create uses idempotency_key and canonical actor context.</th>
  </tr>
</table>

# 6. Information Content Catalog ve Nihai UI Metinleri

V18de görünür ⓘ bilgi düğmesi yoktur; bu nedenle mevcut UIda açılacak info popover envanteri boştur. Aşağıdaki content catalog, V18 ekranında zaten yardımcı metin olarak görünmesi gereken nihai copyyi ve Productionda ayrı ⓘ/tooltip eklenirse doğrudan kullanılacak metni içerir. Bilgi içeriği, Agentın gizli chain-of-thoughtunu veya ham reasoning traceini göstermez.

<table>
  <tr>
    <th>Info key / alan</th>
    <th>Panel başlığı</th>
    <th>Nihai UI metni</th>
  </tr>
  <tr>
    <td>analysisLabIntro</td>
    <td>Analysis Lab</td>
    <td>Analysis Lab is the operational research environment. The visible conversation layer is Lab Assistant. Alpha Agent continues autonomous research from saved checkpoints and is not interrupted by normal messages or queued directives.</td>
  </tr>
  <tr>
    <td>runtimeStatusInfo</td>
    <td>Alpha Agent status</td>
    <td>Status reflects the latest server-confirmed Agent runtime state. ACTIVE means continuous research is enabled. PAUSED means the Agent has reached a safe checkpoint and is waiting. A status label does not replace the task, checkpoint, or event record.</td>
  </tr>
  <tr>
    <td>dataBundleInfo</td>
    <td>Active Data Bundle</td>
    <td>This summary is generated from the current context manifest. It lists the exact approved dataset revisions and policies used by the active task. Dataset revisions do not switch to “latest” while a task is running.</td>
  </tr>
  <tr>
    <td>safeCheckpointInfo</td>
    <td>Safe Checkpoint Rule</td>
    <td>A safe checkpoint is a saved, consistent point in the research workflow. Directives, pause, resume, and controlled stop actions are applied only at a safe checkpoint or another cancellation-safe boundary.</td>
  </tr>
  <tr>
    <td>labAssistantInfo</td>
    <td>Lab Assistant</td>
    <td>Lab Assistant answers from saved task, checkpoint, artifact, and manifest context. It is not Alpha Agent’s hidden reasoning trace and does not directly change the active research task when you send a normal message.</td>
  </tr>
  <tr>
    <td>directiveInfo</td>
    <td>Send as Directive</td>
    <td>A directive creates a durable queued research instruction. Choose Normal or High priority. High priority affects queue ordering after a safe checkpoint; it never interrupts the current task immediately.</td>
  </tr>
  <tr>
    <td>pauseInfo</td>
    <td>Pause / Resume</td>
    <td>Pause asks the Coordinator to stop Alpha Agent at the next safe checkpoint. Queue entries, directives, checkpoints, and artifacts remain available. Resume continues from saved state.</td>
  </tr>
  <tr>
    <td>stopInfo</td>
    <td>Stop Current Run</td>
    <td>Stop requests a controlled cancellation of the current Agent sub-run. The last completed checkpoint and partial diagnostics are retained. A cancelled run does not publish a normal immutable Backtest Result.</td>
  </tr>
  <tr>
    <td>outputBoardInfo</td>
    <td>Hypothesis &amp; Output Board</td>
    <td>This board shows persistent research artifacts, evidence, and next actions. It is not generated from chat history. A visible artifact is not automatically approved, published, or ready for live use.</td>
  </tr>
</table>

## 6.1 Placeholder, helper, warning, toast, confirmation ve error metinleri

<table>
  <tr>
    <th>Durum</th>
    <th>Nihai UI metni</th>
    <th>Kullanım</th>
  </tr>
  <tr>
    <td>Textarea placeholder</td>
    <td>Ask Lab Assistant about current work, data, findings or outputs. Use Send as Directive only for a queued research task.</td>
    <td>V18 textarea placeholder.</td>
  </tr>
  <tr>
    <td>Compose helper</td>
    <td>Messages do not affect the active job. Directives enter the queue and run only after a safe checkpoint.</td>
    <td>V18 compose action row.</td>
  </tr>
  <tr>
    <td>Loading</td>
    <td>Loading the latest Analysis Lab state...</td>
    <td>Overview/task/artifact initial query.</td>
  </tr>
  <tr>
    <td>Empty queue</td>
    <td>No queued or running Agent tasks are available. Alpha Agent will continue when the Coordinator schedules an eligible task.</td>
    <td>Task list empty.</td>
  </tr>
  <tr>
    <td>Empty output board</td>
    <td>No persistent hypotheses or outputs match the current context yet.</td>
    <td>Artifact query empty.</td>
  </tr>
  <tr>
    <td>Empty message error</td>
    <td>Enter a message before sending.</td>
    <td>Trimmed textarea empty.</td>
  </tr>
  <tr>
    <td>Directive access error</td>
    <td>You do not have permission to queue an Agent directive.</td>
    <td>403/role policy.</td>
  </tr>
  <tr>
    <td>Pause confirmation</td>
    <td>Pause Alpha Agent after the next safe checkpoint? The active step will finish to a durable checkpoint. Queue entries, directives, and artifacts will remain available.</td>
    <td>Production confirmation modal before POST pause.</td>
  </tr>
  <tr>
    <td>Stop confirmation</td>
    <td>Stop the current Agent run? The run will be cancelled at the next cancellation-safe boundary. The last completed checkpoint and partial diagnostics will remain available. No Backtest Result will be published for a cancelled run.</td>
    <td>Production destructive confirmation modal before POST stop.</td>
  </tr>
  <tr>
    <td>Directive success</td>
    <td>Directive queued. Alpha Agent will consider it at the next safe checkpoint. The active task was not interrupted.</td>
    <td>202 directive response.</td>
  </tr>
  <tr>
    <td>Discussion success</td>
    <td>Message recorded. Lab Assistant will answer from the latest saved Agent state.</td>
    <td>Discussion persistence response.</td>
  </tr>
  <tr>
    <td>Pause requested</td>
    <td>Pause requested. Alpha Agent will pause after the next safe checkpoint.</td>
    <td>202 pause response.</td>
  </tr>
  <tr>
    <td>Stop requested</td>
    <td>Stop requested. The current run will end at a cancellation-safe boundary.</td>
    <td>202 stop response.</td>
  </tr>
  <tr>
    <td>Stale state warning</td>
    <td>Analysis Lab state changed elsewhere. Reload the latest runtime state before sending another control command.</td>
    <td>409/412 control conflict.</td>
  </tr>
  <tr>
    <td>Dependency waiting</td>
    <td>The task is waiting for {dependency_name}. The queue will continue when the dependency becomes available.</td>
    <td>Task Waiting state.</td>
  </tr>
  <tr>
    <td>Recovery notice</td>
    <td>Recovered from checkpoint {checkpoint_id}. The current task resumed without duplicating completed work.</td>
    <td>Worker/coordinator recovery event.</td>
  </tr>
</table>

# 7. Button, Command ve State Sözleşmesi

<table>
  <tr>
    <th>UI action</th>
    <th>Production query / command</th>
    <th>Precondition</th>
    <th>Disabled / loading / retry</th>
    <th>Success, error, audit</th>
  </tr>
  <tr>
    <td>Open Analysis Lab</td>
    <td>GET `/agent-workspace/overview`; GET task and artifact projections; subscribe GET `/agent-events/stream`.</td>
    <td>Admin/Supervisor server policy; Agent internal service context.</td>
    <td>Initial skeleton; stale cached cards do not override query response. SSE reconnect triggers refetch.</td>
    <td>Overview DTO contains runtime, context, queue, output summary. Access denial returns no sensitive state.</td>
  </tr>
  <tr>
    <td>Send Message</td>
    <td>POST `/lab/messages`.</td>
    <td>Authorized Admin/Supervisor; trimmed text non-empty; optional related task visible.</td>
    <td>Disable Send Message during idempotent request; preserve text on validation/network failure.</td>
    <td>Creates `discussion_message`; queues Lab Assistant response generation/read. Audit/event: `discussion_recorded`, `lab_assistant_response_created`.</td>
  </tr>
  <tr>
    <td>Send as Directive</td>
    <td>POST `/agent-directives`.</td>
    <td>Admin/Supervisor; text non-empty; priority normal/high; target Agent valid.</td>
    <td>Disable directive controls while pending; same idempotency key returns same directive DTO.</td>
    <td>202: directive `queued`, delivery_policy `next_safe_checkpoint`, `active_task_interrupted=false`. Creates directive + queue ref + audit atomically.</td>
  </tr>
  <tr>
    <td>Pause</td>
    <td>POST `/agent-runtime/pause`.</td>
    <td>Admin; runtime active/eligible; no lifecycle command pending.</td>
    <td>Button disabled while accepted/pending checkpoint.</td>
    <td>202 command accepted; `agent_run_control_requested`; runtime emits checkpoint and paused events.</td>
  </tr>
  <tr>
    <td>Resume</td>
    <td>POST `/agent-runtime/resume`.</td>
    <td>Admin; runtime paused with resumable checkpoint.</td>
    <td>Disabled unless paused.</td>
    <td>202 accepted; Coordinator schedules continuation from saved checkpoint; `task_resumed` event.</td>
  </tr>
  <tr>
    <td>Stop Current Run</td>
    <td>POST `/agent-runs/{id}/stop`.</td>
    <td>Admin; active stoppable Agent sub-run exists.</td>
    <td>Disabled if no active run or cancellation already requested.</td>
    <td>202 accepted; controlled cancellation; `task_cancelled`/run event; partial diagnostics retained; no normal Result if run cancelled.</td>
  </tr>
  <tr>
    <td>Open task/artifact detail</td>
    <td>GET `/agent-tasks/{id}` / GET `/hypotheses/{id}`.</td>
    <td>Caller can view target.</td>
    <td>Detail drawer/modal loading; no local hidden data fallback.</td>
    <td>Returns manifest/checkpoint/artifact references; view event optional.</td>
  </tr>
  <tr>
    <td>Agent internal tool parity</td>
    <td>Tool Gateway: `agent.task.query`, `data_bundle.resolve`, `package.proposal.create`, `backtest.request`, `artifact.create`.</td>
    <td>Agent runtime policy, task/checkpoint, manifest, idempotency.</td>
    <td>No UI dependency; worker retry uses idempotency key.</td>
    <td>Every tool call records task, checkpoint, actor, manifest and output artifact reference.</td>
  </tr>
</table>

# 8. Kullanıcı ve Sistem Akışları

## 8.1 Flow A - Labı açma ve read-only runtime görünümü

- Admin veya Supervisor, Agent Workspace > Analysis Lab seçer. Frontend access hintine güvenmeden overview endpointini çağırır.

- Server principal/role policy uygular. User veya anonymous caller 403/uygun denial alır; UI “Admin, Supervisor or Agent access required.” metnini gösterir.

- Başarılı overview response, runtime statusu, active task, context manifest summary, queue cardları ve hypothesis artifact özetlerini döndürür.

- Frontend `ACTIVE` veya `PAUSED` labelını server enum registryden render eder; task progressi JavaScript timer ile uydurmaz.

- SSE event geldiğinde frontend event payloadını source of truth kabul etmez; gerektiğinde query refetch ile projectionı yeniden hydrate eder.

## 8.2 Flow B - Normal discussion ve Lab Assistant yanıtı

- Admin veya Supervisor textarea içine mevcut task, data bundle, bulgu veya output hakkında bir soru yazar.

- Send Message, trimmed text boş değilse `POST /lab/messages` çağrısını idempotency key ile gönderir.

- Server `discussion_message` kaydını, actor, related task context ve correlation id ile persist eder; active taskın stage/progressi değişmez.

- Lab Assistant, son checkpoint, context manifest, queue ve artifact projectionından yanıt üretir. Yanıt gerekçe özeti verir; gizli chain-of-thought veya ham internal reasoning trace döndürmez.

- Conversation paneli message ve assistant response kartını gösterir. Alpha Agentın ana döngüsü bu konuşma yüzünden durmaz, yeniden önceliklenmez veya yeni taska dönüşmez.

## 8.3 Flow C - Queued directive ve safe checkpoint tüketimi

- Admin veya Supervisor araştırma talebini yazar; Directive Priorityden Normal veya High seçer. V18 defaultu Normaldir.

- Send as Directive commandi task_directive, audit event ve queue entryyi tek transactionda oluşturur; 202 response active taskın kesilmediğini bildirir.

- Coordinator current taskı tamamlanabilir bir safe checkpointa getirir; plan/context/artifact pointerları kaydedilir.

- Coordinator directive cursor üzerinden eligible directivei tüketir. High priority queue orderingi etkiler ancak aktif workerı yarıda kesmez.

- Directive accepted/deferred/consumed statei event stream ve Work Queue projectionında görünür. Dependency/policy/budget engeli varsa directive deferred veya requires-review benzeri metadata ile saklanır; sessizce kaybolmaz.

## 8.4 Flow D - Admin controlled Pause, Resume ve Stop

- Admin Pausea basar ve production confirmation modalını onaylar. API, runtimea doğrudan process kill sinyali değil controlled checkpoint request iletir.

- Agent/worker uygun safe boundaryde checkpoint yazar; runtime `paused` olur. Queue, directives ve artifacts korunur.

- Admin Resumea basarsa Coordinator last checkpointten continuation taskı başlatır. Eski task geçmişi mutate edilmez; resume event/audit oluşur.

- Admin Stop Current Runa basar ve stop confirmation modalını onaylar. Stop yalnız aktif Agent sub-run/backtest run için controlled cancellation ister.

- Son checkpoint, partial diagnostic ve oluşmuş artifacts korunur. Cancelled Backtest Run normal immutable Backtest Result publish etmez; devam için yeni restart/continuation taskı yaratılır.

## 8.5 Flow E - Worker crash, stale UI ve recovery

- Worker crashi veya geçici tool failure olursa Coordinator last valid checkpointi ve job/task stateini okur.

- Retry policy eligible ise same idempotency key/context manifest ile controlled retry veya continuation task oluşturur; duplicate package proposal/backtest request oluşmaz.

- UI eventte failure/recovery görse bile canonical statusu query ile doğrular. Browser kapanması, logout veya SSE kopması taskı iptal etmez.

- Non-recoverable failurede task `failed` olur; failure reason, last checkpoint, input manifest ve next recovery action görünür olur. Partial output artifact varsa status/diagnostic sınırı açıkça gösterilir.

# 9. Production Backend ve Domain Davranışı

Productionda V18deki tek `analysisLabState` nesnesi ayrı domain kayıtları ve projectionlardan oluşur. Frontend yalnız overview/read modelini render eder; agent runtime, task queue, checkpoint, data access, tool execution ve artifact persistence backendde ayrı bileşenlerdir.

<table>
  <tr>
    <th>Kalıcı nesne</th>
    <th>Amaç</th>
    <th>Ana alanlar</th>
    <th>İlişkiler / immutability</th>
  </tr>
  <tr>
    <td>agent_runtime</td>
    <td>Alpha Agent instance ve lifecycle.</td>
    <td>agent_id, mode, status, active_task_id, last_checkpoint_id, policy_revision.</td>
    <td>Status/current pointer mutable operational state; Agent human account değildir.</td>
  </tr>
  <tr>
    <td>agent_task</td>
    <td>Kalıcı araştırma/iş nesnesi.</td>
    <td>task_id, task_type, title, source, priority, status, stage, progress, context_manifest_id, parent_task_id.</td>
    <td>Queue, checkpoint, artifact, tool execution. Task status generic job/run enumlarıyla karıştırılmaz.</td>
  </tr>
  <tr>
    <td>task_directive</td>
    <td>Kuyrukta işlenecek insan yönlendirmesi.</td>
    <td>directive_id, author_actor_id, text, priority, status, target_agent_id, related_task_id, consumed_checkpoint_id.</td>
    <td>Created immutable; status transition/audit append-only.</td>
  </tr>
  <tr>
    <td>agent_checkpoint</td>
    <td>Devam edilebilir çalışma kaydı.</td>
    <td>checkpoint_id, task_id, stage, state_ref, context_manifest_id, plan_revision, directive_cursor, artifact_ids.</td>
    <td>Payload/manifest/evidence oluşturulduktan sonra immutable.</td>
  </tr>
  <tr>
    <td>lab_message</td>
    <td>Conversation/event kaydı.</td>
    <td>message_id, type, author, text, task_id, created_at, correlation_id.</td>
    <td>Correction gerekiyorsa original silinmez; clarification/correction event eklenir.</td>
  </tr>
  <tr>
    <td>hypothesis_artifact</td>
    <td>Kalıcı hypothesis/output.</td>
    <td>artifact_id, status, mechanism, evidence_refs, next_action, source_task_id, checkpoint_id.</td>
    <td>Revision/status update auditli; chatten türetilmez.</td>
  </tr>
  <tr>
    <td>artifact_link</td>
    <td>Provenance ilişkisi.</td>
    <td>source_artifact_id, target_type, target_id, relation_type.</td>
    <td>Package/run/result/data referans bağını taşır.</td>
  </tr>
  <tr>
    <td>agent_event</td>
    <td>Durable observability ve projection trigger.</td>
    <td>event_id, type, actor, task_id, payload_ref, occurred_at, correlation_id.</td>
    <td>Append-only audit/event stream; UI state source of truth değil refresh sinyalidir.</td>
  </tr>
</table>

## 9.1 Task, checkpoint, data bundle ve artifact state model

<table>
  <tr>
    <th>Model</th>
    <th>Canonical kural</th>
  </tr>
  <tr>
    <td>Task states</td>
    <td>API canonical enumları `queued`, `running`, `waiting`, `checkpointing`, `paused`, `succeeded`, `failed`, `cancelled` olmalıdır. V18deki Running/Queued/Waiting pillleri presentation mapidir.</td>
  </tr>
  <tr>
    <td>Task priority</td>
    <td>Human directive yalnız `normal` veya `high` seçer. `autonomous` Coordinator tarafından yaratılan follow-up/scheduled task kaynağını temsil eder; user-selectable değildir.</td>
  </tr>
  <tr>
    <td>Checkpoint</td>
    <td>Checkpoint payloadı UI textarea/DOM taşımaz; only real state, completed/pending steps, manifest refs, artifact refs, directive cursor ve resume metadata saklar.</td>
  </tr>
  <tr>
    <td>Data bundle</td>
    <td>Agent normal araştırma/backtest bağlamına yalnız approved Market Data ve usage scope izinli Research Data revisions ekler. `agent_research_only` data research context sağlayabilir fakat otomatik execution feature/trade trigger olmaz.</td>
  </tr>
  <tr>
    <td>Artifact</td>
    <td>Artifact görünmesi approval/publish değildir. Package proposal Create Package pipelineına; backtest request Ready Check/Run Orchestrationa; research feature önerisi Research Data governanceına gider.</td>
  </tr>
  <tr>
    <td>Run/Result</td>
    <td>Agentin başlattığı Backtest Run async worker işidir. Sadece succeeded run immutable Backtest Result üretir; failed/cancelled/stopped run normal Result üretmez.</td>
  </tr>
</table>

## 9.2 Tool Gateway, API ve event contract

<table>
  <tr>
    <th>Agent Runtime -&gt; Coordinator / Task Queue -&gt; Tool Gateway<br/>  -&gt; Data Query / Context Bundle Tool<br/>  -&gt; Package / Create Package Proposal Tool<br/>  -&gt; Backtest Ready Check Tool<br/>  -&gt; Backtest Run Request Tool<br/>  -&gt; Result / Artifact Query Tool<br/>  -&gt; Directive / Checkpoint Tool<br/>  -&gt; Isolated Workers: analysis, package validation, backtest, export<br/><br/>Her tool call zorunlu olarak actor_context, task_id, checkpoint_id, input_manifest_id, idempotency_key, policy_scope ve artifact_output_ref ile kaydedilir.</th>
  </tr>
</table>

<table>
  <tr>
    <th>Endpoint / command</th>
    <th>Amaç</th>
    <th>Başarı çıktısı / policy</th>
  </tr>
  <tr>
    <td>GET `/agent-workspace/overview`</td>
    <td>Runtime, active task, data bundle, queue ve output summary querysi.</td>
    <td>Overview DTO. Admin/Supervisor UI; Agent internal service policy.</td>
  </tr>
  <tr>
    <td>GET `/agent-tasks?status=`</td>
    <td>Task queue/history sorgusu.</td>
    <td>Paginated task projection; filters server-side.</td>
  </tr>
  <tr>
    <td>GET `/agent-tasks/{id}`</td>
    <td>Task, checkpoints, manifest/artifact bağlantıları.</td>
    <td>Task DTO; `can_view` tekrar doğrulanır.</td>
  </tr>
  <tr>
    <td>POST `/lab/messages`</td>
    <td>Normal discussion persistence ve Lab Assistant response workflowu.</td>
    <td>Message DTO + response job/ref; active task unchanged.</td>
  </tr>
  <tr>
    <td>POST `/agent-directives`</td>
    <td>Queued directive oluşturma.</td>
    <td>202 directive DTO + queue task ref; Admin/Supervisor; priority normal/high.</td>
  </tr>
  <tr>
    <td>POST `/agent-runtime/pause` / `/resume`</td>
    <td>Controlled lifecycle command.</td>
    <td>202 accepted; Admin only; checkpoint after effect.</td>
  </tr>
  <tr>
    <td>POST `/agent-runs/{id}/stop`</td>
    <td>Controlled cancellation.</td>
    <td>202 accepted; Admin only; partial state retained.</td>
  </tr>
  <tr>
    <td>GET `/hypotheses`</td>
    <td>Output Board artifact querysi.</td>
    <td>Artifact DTO list; status/context filters.</td>
  </tr>
  <tr>
    <td>GET `/agent-events/stream`</td>
    <td>SSE event feed.</td>
    <td>Event subscription; reconnect sonrası query refetch zorunlu.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Zorunlu eventler</th>
    <th>UI / audit etkisi</th>
  </tr>
  <tr>
    <td>agent_task_created, task_started, task_waiting, checkpoint_saved, task_resumed, task_succeeded, task_failed, task_cancelled</td>
    <td>Work Queue ve top status projectionı; restart/recovery ve audit izi.</td>
  </tr>
  <tr>
    <td>directive_queued, directive_consumed, directive_deferred, discussion_recorded, lab_assistant_response_created</td>
    <td>Conversation cardları ve directive lifecycle görünümü.</td>
  </tr>
  <tr>
    <td>data_bundle_pinned, tool_call_started, tool_call_succeeded, tool_call_failed, backtest_requested, result_linked</td>
    <td>Lab Context integrity, artifact provenance ve task diagnostics.</td>
  </tr>
  <tr>
    <td>hypothesis_created, hypothesis_status_changed, artifact_created, package_proposal_created</td>
    <td>Hypothesis &amp; Output Board projectionı; chat listesi yerine artifact query refresh.</td>
  </tr>
</table>

# 10. Agent İlişkisi ve UI-siz Eşdeğer Tool/API Kullanımı

Analysis Lab, Agentın kendisi için zorunlu bir ekran değildir. Alpha Agent; UI butonlarını tıklamadan Tool Gateway veya aynı Application Service commandleriyle context bundle çözer, package/strategy taslağı oluşturur, Ready Check ve Backtest Run request üretir, sonuç/artifact sorgular, yeni hypothesis/next task yazar ve safe checkpoint kaydeder. UI ve Agent farklı giriş kanallarıdır; gerçek domain işi aynı policyli command/service hattında yürümelidir.

<table>
  <tr>
    <th>İnsan UI niyeti</th>
    <th>UI command</th>
    <th>Agent UI-siz eşdeğeri</th>
    <th>Ownership / policy sınırı</th>
  </tr>
  <tr>
    <td>Mevcut çalışmayı öğrenmek</td>
    <td>GET overview / task detail.</td>
    <td>`agent.task.query`, `artifact.query`, `context_manifest.read`.</td>
    <td>Agent kendi tasklarına erişir; başka principalın private normal objectine policy dışı erişmez.</td>
  </tr>
  <tr>
    <td>Araştırma yönlendirmek</td>
    <td>POST directive.</td>
    <td>Coordinator autonomous follow-up veya internal task planlama.</td>
    <td>Human directive Admin/Supervisor; Agent kendi policy/budgeti içinde task yaratır.</td>
  </tr>
  <tr>
    <td>Veri bağlamını kullanmak</td>
    <td>Read-only Lab Context.</td>
    <td>`data_bundle.resolve`, `market_data.query`, `research_data.query`.</td>
    <td>Approved/usable revision, available-time, mapping and scope validation zorunlu.</td>
  </tr>
  <tr>
    <td>Package/Strategy önerisi oluşturmak</td>
    <td>Output Boardda artifact görünür.</td>
    <td>`package.proposal.create`, `strategy.draft.create`.</td>
    <td>Agent candidate/draft yaratır; approve/publish edemez.</td>
  </tr>
  <tr>
    <td>Backtest istemek</td>
    <td>Queue / system event görünür.</td>
    <td>`backtest.ready_check`, `backtest.request`.</td>
    <td>Ready Check bypass edilmez; run async, manifest pinned.</td>
  </tr>
  <tr>
    <td>Sonucu yorumlamak</td>
    <td>Lab Assistant/artifact kartı.</td>
    <td>`result.query`, `artifact.create`, `followup_task.enqueue`.</td>
    <td>Result immutable kalır; Agent yorum artifacti oluşturur.</td>
  </tr>
  <tr>
    <td>Pause/Stop</td>
    <td>Admin lifecycle command.</td>
    <td>N/A - Agent kendi human lifecycle controlünü UI endpointiyle yönetmez.</td>
    <td>Agent Admin role/Trash/role management yetkisi kazanmaz.</td>
  </tr>
</table>

# 11. Validation, Hata ve Recovery Sözleşmesi

<table>
  <tr>
    <th>Kategori</th>
    <th>Örnek</th>
    <th>Server davranışı</th>
    <th>UI / Agent recovery</th>
  </tr>
  <tr>
    <td>Field validation</td>
    <td>Blank veya whitespace message.</td>
    <td>422 `MESSAGE_TEXT_REQUIRED`; message/directive persistence yapılmaz.</td>
    <td>Textarea text korunur; “Enter a message before sending.” inline gösterilir.</td>
  </tr>
  <tr>
    <td>Priority validation</td>
    <td>`autonomous` veya bilinmeyen priority.</td>
    <td>422 `INVALID_DIRECTIVE_PRIORITY`.</td>
    <td>Select Normal/Higha döner; Agent Coordinator autonomous priorityyi yalnız internal üretir.</td>
  </tr>
  <tr>
    <td>Authorization</td>
    <td>Userın directive/pause/overview çağrısı.</td>
    <td>403/appropriate `ACCESS_DENIED`; state sızmaz.</td>
    <td>“Admin, Supervisor or Agent access required.”; client local statei bypass edemez.</td>
  </tr>
  <tr>
    <td>Context dependency</td>
    <td>Unapproved data, invalid mapping veya usage scope mismatch.</td>
    <td>Tool/context resolve reddedilir; `research_input_blocked` event/artifact reason oluşur.</td>
    <td>Lab Context warning; Agent corrected task/follow-up üretir.</td>
  </tr>
  <tr>
    <td>Task dependency</td>
    <td>Backtest worker capacity veya data job bekliyor.</td>
    <td>Task `waiting`; dependency ref/next event kaydedilir.</td>
    <td>Queue card Waiting reason gösterir; manual refreshle job yaratılmaz.</td>
  </tr>
  <tr>
    <td>Recoverable tool failure</td>
    <td>Temporary data timeout.</td>
    <td>Retry policy veya waiting/failed with checkpoint.</td>
    <td>System event; retry same idempotency/context ile no duplicate output.</td>
  </tr>
  <tr>
    <td>Worker crash</td>
    <td>Runtime/tool worker process kesildi.</td>
    <td>Stale recovery last valid checkpointten controlled retry veya failed.</td>
    <td>“Recovered from checkpoint...” veya failure reason; browser state kaybı taskı etkilemez.</td>
  </tr>
  <tr>
    <td>Directive conflict</td>
    <td>Directive aktif planla uyumsuz.</td>
    <td>Directive queued/deferred/requires review; current job unchanged.</td>
    <td>Conversation system event açıklaması; silent drop yok.</td>
  </tr>
  <tr>
    <td>Concurrency</td>
    <td>Birden çok Admin lifecycle commandi veya stale overview.</td>
    <td>409/412; current status/ETag dönülür.</td>
    <td>Reload latest runtime; previous confirmation tekrar istenir.</td>
  </tr>
  <tr>
    <td>Cancelled run</td>
    <td>Stop sonrası backtest cancellation.</td>
    <td>Run cancelled/stopped; partial diagnostic/artifact retained; no Backtest Result.</td>
    <td>Output boardda diagnostic/ref görünür olabilir; Results screen normal result kartı oluşturmaz.</td>
  </tr>
</table>

# 12. Lifecycle, Audit, Soft Delete ve Trash Etkileri

Analysis Labde görünür state tek bir “Save” actionıyla ilerlemez. Conversation, directive, task, checkpoint, artifact ve lifecycle commandleri ayrı domain kaydı ve audit/event üretir. Root/revision/snapshot ayrımı kalıcı outputlarda korunur; runtimeın mutable operational pointerları (status, stage, progress, lease/worker, current checkpoint pointer) yalnız ilgili service tarafından güncellenir.

<table>
  <tr>
    <th>Nesne / eylem</th>
    <th>Lifecycle / versioning</th>
    <th>Audit / event</th>
    <th>Trash etkisi</th>
  </tr>
  <tr>
    <td>Discussion message</td>
    <td>Kalıcı `lab_message`; correction gerekiyorsa original retained + clarification event.</td>
    <td>`discussion_recorded`, actor, related task, correlation id.</td>
    <td>Normal conversation deletion policy özel retention gerektirir; user UI delete V18de yoktur. Soft delete uygulanırsa audit/context link korunur.</td>
  </tr>
  <tr>
    <td>Directive</td>
    <td>Created -&gt; queued -&gt; consumed/deferred/completed/cancelled projection. Original text immutable; status transitions eventlidir.</td>
    <td>`directive_queued`, `directive_consumed`, `directive_deferred`; author/priority/checkpoint ref.</td>
    <td>Directive normal delete ile contextten koparılmaz. Authorized removal soft delete olsa bile task/audit history referansı korunur.</td>
  </tr>
  <tr>
    <td>Checkpoint</td>
    <td>Immutable payload + manifest/evidence refs. New information creates a new checkpoint.</td>
    <td>`checkpoint_saved`; task/stage/manifest/artifact refs.</td>
    <td>Checkpoint active boarddan kalksa bile restart/audit için retention policy korunur; Trash restore normal çalışma yolu değildir.</td>
  </tr>
  <tr>
    <td>Hypothesis / artifact</td>
    <td>Status update veya mechanism/next-action change new revision or structured audit update.</td>
    <td>`hypothesis_created`, `hypothesis_status_changed`, `artifact_created`.</td>
    <td>Agent kendi artifactini soft delete edebilir; active boarddan kalkar fakat source task/checkpoint/audit korunur. Restore yalnız Admin.</td>
  </tr>
  <tr>
    <td>Pause / Resume / Stop</td>
    <td>Lifecycle commands durable request; pause/resume checkpointten; stop controlled cancellation.</td>
    <td>`AGENT_RUN_CONTROL_REQUESTED`, task/runtime events.</td>
    <td>Lifecycle command Trasha gitmez; artifact/diagnostic retention ayrı çalışır.</td>
  </tr>
  <tr>
    <td>Data/package/result references</td>
    <td>Manifest/provenance references immutable; later resource revision/deletion historical task evidenceyi rewrite etmez.</td>
    <td>`data_bundle_pinned`, tool call/result link events.</td>
    <td>Soft-deleted source historical manifestte referans olarak kalır; new use policy lifecycleye göre engellenir.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Trash sınırı. Trash, restore ve permanent delete yalnız Admin yetkisindedir. Alpha Agent Trashı göremez veya restore kararı veremez. Agentın kendi outputunu soft delete etmesi bir Trash/audit kaydı üretir; Agentın ana scheduled research görevi bu işlem yüzünden durmaz.</th>
  </tr>
</table>

# 13. V18 Interface Behavior / Production Backend Behavior / Implementation Alignment Note

<table>
  <tr>
    <th>V18 Interface Behavior</th>
    <th>Production Backend Behavior</th>
    <th>Implementation Alignment Note</th>
  </tr>
  <tr>
    <td>`analysisLabState` tek local JavaScript nesnesiyle status, messages, queue ve hypotheses tutar.</td>
    <td>Runtime/task/checkpoint/message/directive/artifactler ayrı durable persistence ve queriesden gelir.</td>
    <td>V18 local state sadece interaction hedefidir. UI ilk açılışta overview query ile hydrate edilir; local state source of truth değildir.</td>
  </tr>
  <tr>
    <td>Send Message, user mesajını ve canned Lab Assistant cevabını aynı browser arrayine ekler.</td>
    <td>Discussion message persistence, Lab Assistant response creation ve event projectionları ayrı kayıtlardır.</td>
    <td>Normal discussion active taskı değiştirmez; response saved contextten türetilir.</td>
  </tr>
  <tr>
    <td>Send as Directive sadece queue arrayinin başına item ekler.</td>
    <td>Directive, audit event ve task queue ref tek transactionda oluşturulur; coordinator safe checkpointte consume eder.</td>
    <td>High priority preemption değildir. HTTP 202 + `next_safe_checkpoint` delivery policy açık gösterilir.</td>
  </tr>
  <tr>
    <td>Pause/Stop buttonları local status/stage değiştirir.</td>
    <td>Pause/Resume controlled lifecycle command; Stop controlled cancellation requesttir.</td>
    <td>V18 fast visual toggle Productionda optimistic terminal state değildir; state yalnız checkpoint/cancel-safe event sonrası değişir.</td>
  </tr>
  <tr>
    <td>Active Data Bundle metin stringidir.</td>
    <td>Context manifest exact dataset revisions, usage scope, mapping/time policy taşır.</td>
    <td>Bundle read-only manifest summaryden derive edilir; task ortasında latest revisiona geçmez.</td>
  </tr>
  <tr>
    <td>Output cards local `hypotheses` arrayindendir.</td>
    <td>Hypothesis/artifact querysi kalıcı, provenance-linked outputları döndürür.</td>
    <td>Board chatten türetilmez; artifact görünmesi publish/approval değildir.</td>
  </tr>
  <tr>
    <td>User role için generic page copy gösterilir.</td>
    <td>Route/query/command seviyesinde server policy uygulanır.</td>
    <td>UI hidden/disabled state authorization değildir.</td>
  </tr>
  <tr>
    <td>V18de confirm modalı yoktur.</td>
    <td>Pause/Stop destructive/exceptional lifecycle commandleridir.</td>
    <td>Implementation Decision: Productionda explicit confirmation modalı, command idempotency ve current ETag/expected runtime state zorunludur.</td>
  </tr>
</table>

# 14. Kodcu AI için Implementation Rules

- Frontend, localStorage veya V18deki `analysisLabState` benzeri client arraylerini Agent runtime, task, directive, checkpoint veya artifact için source of truth olarak kullanmayacaktır.

- Alpha Agent ayrı continuous Coordinator/runtime processi olarak çalışacaktır; browser, session, Lab Assistant chat veya UI visibility Agentın ana döngüsünü başlatma/durdurma koşulu olmayacaktır.

- Lab Assistant, Alpha Agentın hidden reasoning traceini göstermeyecek; yalnız saved checkpoint, manifest, queue, artifact ve izinli output contextinden insan-okur özet döndürecektir.

- Normal discussion ve queued directive ayrı endpoint, ayrı persistence type, ayrı audit/event ve ayrı lifecycle ile uygulanacaktır. Discussion active taskı mutasyona uğratmayacaktır.

- Directive create commandi `text`, `priority`, `target_agent_id`, actor context ve idempotency key ile validate edilecek; directive, queue ref ve audit kayıtları atomik oluşturulacaktır.

- High directive priority, aktif taskı veya backtest workerını preempt etmeyecek; Coordinator directivei yalnız safe checkpointte, quota/dependency/capacity/policy kontrolünden sonra consume edecektir.

- Pause ve Stop, worker process kill veya anlık memory mutation olarak uygulanmayacaktır. Pause checkpoint request, Stop controlled cancellation requesttir; last checkpoint ve artifactler korunacaktır.

- Cancelled veya failed Backtest Run için normal immutable Backtest Result üretilmeyecek; diagnostic/partial artifact sonucu normal Results History itemı gibi yayınlanmayacaktır.

- Lab Contextte görünen Active Data Bundle, context manifestten türetilecek; exact revision, usage scope, instrument mapping, event-time/available-time validation ve policy statusu task boyunca pinlenecektir.

- Research Data `agent_research_only` scopeundaysa Agentın araştırma bağlamına girebilir; otomatik execution feature, trade trigger veya backtest inputu olarak kullanılamayacaktır.

- Hypothesis & Output Board, chat messagesden türetilmeyecek; `hypothesis_artifact` ve artifact provenance queryleriyle doldurulacaktır.

- Her Agent tool call, task_id, checkpoint_id, input_manifest_id, actor context, idempotency_key, policy scope, correlation id ve artifact output referansı taşıyacaktır.

- SSE eventleri UI projection refresh sinyalidir; reconnect, event kaybı veya refresh sonrası UI canonical GET query ile actual runtime/task stateini yeniden yükleyecektir.

- User role, Agent Workspace query/commandlerine erişemeyecek; Supervisor directive gönderebilecek ama pause/resume/stop lifecycle command gönderemeyecektir.

- Agent, dataset approval, Trash, human role management, canonical package publish/approval ve live trade başlatma yetkisi elde etmeyecektir.

- Agentın kendi ürettiği artifact soft delete edildiğinde task/checkpoint provenance ve audit event silinmeyecek; restore/permanent delete sadece Admin tarafından uygulanacaktır.

- Unknown status enum, missing manifest veya policy-denied artifact UIde sahte success/card olarak render edilmeyecek; structured error/empty/stale state gösterilecektir.

- API uzun Agent/backtest işini HTTP response içinde çalıştırmayacak; command accepted dönecek, Coordinator/worker durable state ve event yayını üretecektir.

# 15. Acceptance Tests

<table>
  <tr>
    <th>ID</th>
    <th>Senaryo</th>
    <th>Beklenen sonuç</th>
  </tr>
  <tr>
    <td>AL-01</td>
    <td>Analysis Lab UI hiç açılmadan Alpha Agent Coordinator çalışır.</td>
    <td>Agent task queue, checkpoint ve artifact akışı devam eder; browser stateine bağımlılık oluşmaz.</td>
  </tr>
  <tr>
    <td>AL-02</td>
    <td>Admin veya Supervisor Labı açar.</td>
    <td>Overview server queryden runtime/context/queue/output projectionıyla gelir; V18 demo arrayi canonical state yerine geçmez.</td>
  </tr>
  <tr>
    <td>AL-03</td>
    <td>User Agent Workspace URL/API çağırır.</td>
    <td>403/uygun access denial; queue, data bundle, checkpoint veya artifact bilgisi sızmaz.</td>
  </tr>
  <tr>
    <td>AL-04</td>
    <td>Admin normal discussion mesajı gönderir.</td>
    <td>Discussion kaydolur ve Lab Assistant response oluşur; active task stage/progress/queue ordering değişmez.</td>
  </tr>
  <tr>
    <td>AL-05</td>
    <td>Supervisor High directive gönderir.</td>
    <td>Directive `queued` olur, audit ve queue ref oluşur; active task kesilmez; safe checkpoint sonrası tüketilebilir.</td>
  </tr>
  <tr>
    <td>AL-06</td>
    <td>Boş/whitespace directive gönderilir.</td>
    <td>422 validation; directive/queue/audit mutation oluşmaz; textarea texti kullanıcıda korunur.</td>
  </tr>
  <tr>
    <td>AL-07</td>
    <td>User `autonomous` priority gönderir veya UI payloadı manipüle eder.</td>
    <td>422 invalid priority; human callable values yalnız normal/highdır.</td>
  </tr>
  <tr>
    <td>AL-08</td>
    <td>Admin Pause gönderir.</td>
    <td>Coordinator checkpoint request iletir; Agent safe checkpointte paused olur; queue/directive/artifact korunur.</td>
  </tr>
  <tr>
    <td>AL-09</td>
    <td>Supervisor Pause veya Stop endpointine çağrı yapar.</td>
    <td>403 policy denial; runtime state değişmez; audit-relevant denial kaydı policyye göre oluşabilir.</td>
  </tr>
  <tr>
    <td>AL-10</td>
    <td>Admin Stop Current Run gönderir.</td>
    <td>Controlled cancellation; last checkpoint/partial diagnostics korunur; cancelled run normal Backtest Result publish etmez.</td>
  </tr>
  <tr>
    <td>AL-11</td>
    <td>Agent Research Only data ile execution/backtest feature çağırır.</td>
    <td>Tool Gateway policy validation reddeder; rejection event/artifact oluşur; invalid data bundle run manifestine girmez.</td>
  </tr>
  <tr>
    <td>AL-12</td>
    <td>Agent new package proposal üretir.</td>
    <td>Candidate/draft pipeline ve provenance oluşturulur; Agent approval/publish yapamaz.</td>
  </tr>
  <tr>
    <td>AL-13</td>
    <td>Backtest sonucu succeeds.</td>
    <td>Immutable Result ve run manifest hypothesis/artifacte bağlanır; Results alanı event/query ile projection yeniler.</td>
  </tr>
  <tr>
    <td>AL-14</td>
    <td>Worker crashi checkpointten sonra oluşur.</td>
    <td>Coordinator controlled retry/continuation yürütür; duplicate tool call/backtest/package proposal oluşmaz.</td>
  </tr>
  <tr>
    <td>AL-15</td>
    <td>SSE bağlantısı kesilir veya browser refresh olur.</td>
    <td>Agent işi devam eder; frontend reconnect sonrası GET query ile canonical runtime/task stateine döner.</td>
  </tr>
  <tr>
    <td>AL-16</td>
    <td>Agent kendi hypothesis artifactini soft delete eder.</td>
    <td>Artifact active boarddan kalkar; task/checkpoint/audit provenance korunur; Agent Trashı göremez; Admin restore edebilir.</td>
  </tr>
  <tr>
    <td>AL-17</td>
    <td>İki Admin eşzamanlı runtime control gönderir.</td>
    <td>Expected runtime version/ETag veya lifecycle lock ikinci stale commandi 409/412 ile reddeder; silent overwrite olmaz.</td>
  </tr>
  <tr>
    <td>AL-18</td>
    <td>Context manifestten sonra dataset yeni revision alır.</td>
    <td>Current task “latest”e geçmez; yeni revision için yeni task/context manifest gerekir.</td>
  </tr>
</table>

# 16. Final Consistency Check

<table>
  <tr>
    <th>Kontrol</th>
    <th>Sonuç</th>
  </tr>
  <tr>
    <td>Master Technical Reference v1.0 Module 14 ve CR-02/CR-04 ile çelişki</td>
    <td>Hayır. Alpha Agent continuous runtime, Lab Assistant ayrımı, directive safe checkpoint, Agent governance sınırı, task/run enums ve Production server-side authority korunmuştur.</td>
  </tr>
  <tr>
    <td>V18 prototype ile Production V1 ayrımı</td>
    <td>Evet. Local `analysisLabState`, instant buttons ve demo cards canonical persistence/lifecycle olarak yazılmamıştır.</td>
  </tr>
  <tr>
    <td>Agent sürekli çalışma ilkesi</td>
    <td>Evet. Normal chat, directive, UI visibility, browser refresh veya human session ana loopu durdurmaz.</td>
  </tr>
  <tr>
    <td>Directive ve run control ayrımı</td>
    <td>Evet. Directive Admin/Supervisor tarafından queueya gider; pause/stop yalnız Admin lifecycle commanddir.</td>
  </tr>
  <tr>
    <td>Data/time/policy sınırı</td>
    <td>Evet. Context manifest revision pinning, available-time, usage scope ve Research Only sınırı yazılmıştır.</td>
  </tr>
  <tr>
    <td>Run/Result ayrımı</td>
    <td>Evet. Stop/cancelled run normal Backtest Result üretmez.</td>
  </tr>
  <tr>
    <td>Trash/ownership</td>
    <td>Evet. Agent own artifact soft delete edebilir; Trash view/restore/permanent delete Admin-onlydir.</td>
  </tr>
  <tr>
    <td>Future Dev / live trade sınırı</td>
    <td>Evet. Analysis Lab live execution, fake service veya permission-free automation olarak anlatılmamıştır.</td>
  </tr>
  <tr>
    <td>Implementation Decision kayıtları</td>
    <td>Evet. Production confirmation modalı/ETag gibi Masterın açık UI detaylandırmadığı kararlar Implementation Alignment Note kapsamında ayrıştırılmıştır.</td>
  </tr>
</table>

<table>
  <tr>
    <th>Teslim hükmü. Bu belge yalnız Analysis Lab sayfasının görünür arayüzü ile Production V1 Agent Workspace sözleşmesini kapsar. Kodcu AI; Agentın gerçek işi UIde değil, Agent Runtime + Coordinator + Queue + Checkpoint Store + Artifact Store + Tool Gateway üzerinden sürdürecek; UIyı ise güvenli gözlem ve insan kontrol yüzeyi olarak uygulayacaktır.</th>
  </tr>
</table>
