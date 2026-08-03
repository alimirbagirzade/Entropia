# Agent Strategy Tool Gateway parity (AT-21) — sözleşme, scope tablosu, ToolCall örnekleri

> **Slice:** post-V1 S5 · `feat/agent-strategy-tool-gateway` · base `origin/main` @ `9944bfb`
> **Kapattığı boşluk:** `docs/audit/current_main_ground_truth_2026-08-03.md` §G-03'ün
> **strategy yarısı**. `trading_signal.*` yarısı **AÇIK KALIYOR** (aşağıda §6).
> **Migration:** YOK · **`ENGINE_VERSION`:** DEĞİŞMEDİ · **OpenAPI:** değişmedi (yeni route yok).

---

## 1. Neyi kanıtlıyor

Doc 02 §12 **AT-21**'in literal cümlesi: *"Agent Tool Gateway creates/validates/saves
Strategy revision using same schema, policy, idempotency and audit as UI; no browser
needed."* Bu cümle 2026-08-03 öncesinde **çağrılabilir değildi** — `ToolName`'de tek bir
`strategy.*` üye yoktu (G-03'te 5/5 literal ABSENT olarak ölçülmüştü). Bu slice o beş
aracı ekliyor; araçlar **yeni iş mantığı yazmıyor**, insanın kullandığı aynı
`application/commands/strategy_draft.py` + `application/queries/strategy.py` hattına
delege ediyor. Ownership, OCC, `Idempotency-Key`, compiler verdict, audit + outbox ve
Mainboard re-pin **o komutların içinde** kalıyor.

Kanıt: `backend/tests/integration/test_gateway_parity_strategy.py` (**23 test**).

---

## 2. Scope tablosu (`TOOL_ALLOWED_SCOPES`)

| Tool (literal) | İzinli policy scope | Delege ettiği hat | OCC token | `Idempotency-Key` | Kuyruk | Yetki kapısı |
|---|---|---|---|---|---|---|
| `strategy.get_draft` | `observation`, `research` | `queries/strategy.py::get_strategy_draft` | — (token'ı **döndürür**: `row_version`) | — (salt-okuma) | `agent` | `ensure_can_view` (private) |
| `strategy.create_draft` | `research`, `proposal` | `commands/strategy_draft.py::create_strategy_draft` | — (yeni kök) | ✔ `request.idempotency_key` | `agent` | `require_authenticated` → kök **Agent'a ait** doğar |
| `strategy.patch_draft` | `research`, `proposal` | `…::patch_strategy_draft` | ✔ **zorunlu** `expected_draft_row_version` | ✔ | `agent` | `ensure_can_edit` |
| `strategy.validate_draft` | `research`, `proposal` | `…::validate_strategy_draft` | — (mutasyon yok) | — | `agent` | `ensure_can_view` (private) |
| `strategy.save_revision` | `proposal` | `…::save_strategy_revision` | ✔ **zorunlu** `expected_draft_row_version` | ✔ | `agent` | `ensure_can_edit` + `LOCKED_FOR_TEST` kapısı |

**Neden bu scope'lar.** Taslak okumak gözlemdir; taslak şekillendirmek (create/patch/validate)
hipotez işidir; Save, Agent'ın **önerdiği** değişmez revision'ı üretir → `proposal`. Beşi de
**asla `execution` değildir** — koşu ayrı bir araçtır (`backtest.request`) ve Save bir Ready
PASS değildir (doc 02 §7.1). Bu yüzden hiçbiri `agent-high` düzlemini gerçek koşulardan
çalmaz: `queue_for_tool` beşi için de `agent` döner.

`execution` scope'uyla çağrı → **kaydedilmiş REJECTED** (`AGENT_TOOL_SCOPE_FORBIDDEN`).

### Adjudication — isimlendirme

Doc 18 §10'un parity tablosu düz metinde `strategy.draft.create` yazar. **Aynı hücre**
`artifact.query`, `context_manifest.read`, `market_data.query` ve `research_data.query`
adlarını da anar; bunların **hiçbiri** `ToolName` üyesi değildir. Yani o tablo niyeti
gösterir, registry değildir. Sevk edilmiş registry konvansiyonu `<family>.<verb_object>`
(`trade_log.create_revision`, `portfolio_allocation.upsert_draft`) — strategy ailesi onu
izler. Seçilen beş literal ayrıca G-03'ün ABSENT diye pinlediği literallerdir.
`parse_tool_name("strategy.draft.create")` bilerek **reddedilir** (test ile kilitli).

---

## 3. ToolCall envelope örnekleri (üretilmiş, elle yazılmamış)

Aşağıdaki gövdeler gerçek bir koşudan alındı (id'ler kısaltıldı, `config_hash` `<sha256>`
ile maskelendi). Zarf kuralı değişmedi: **satırın terminal `status`'ü ve `tool_call_id`'si
handler payload'ını EZER** (doc 18 §9.2).

```jsonc
// strategy.create_draft — scope: proposal
{ "draft_id": "stratdraft_…", "strategy_root_id": "strat_…",
  "display_name": "Doc strategy", "row_version": 0,
  "tool_call_id": "agttool_…", "status": "succeeded" }

// strategy.get_draft — scope: observation  (row_version = canlı OCC token'ı)
{ "draft_id": "stratdraft_…", "strategy_root_id": "strat_…",
  "payload": { /* tam StrategyConfig */ }, "is_dirty": true, "row_version": 0,
  "last_saved_revision_id": null, "source_provenance": null,
  "updated_at": "2026-08-03T16:26:10.531285+00:00",
  "tool_call_id": "agttool_…", "status": "succeeded" }

// strategy.patch_draft — scope: research
{ "draft_id": "stratdraft_…", "strategy_root_id": "strat_…",
  "row_version": 1, "is_dirty": true,
  "tool_call_id": "agttool_…", "status": "succeeded" }

// strategy.validate_draft — scope: research  (compiler'ın verdict'i, revision YOK)
{ "draft_id": "stratdraft_…", "valid": true, "issues": [], "warnings": [],
  "tool_call_id": "agttool_…", "status": "succeeded" }

// strategy.save_revision — scope: proposal  (Save != Ready PASS != Run)
{ "strategy_root_id": "strat_…", "strategy_revision_id": "stratrev_…",
  "revision_number": 1, "config_hash": "<sha256>", "mirror_revision_id": "worev_…",
  "pinned_items": [], "ready_state": "STALE", "warnings": [],
  "correlation_id": "corr_doc",
  "tool_call_id": "agttool_…", "status": "succeeded" }
```

Terminal **başarısızlık** biçimleri — üçü de **durable satır**, hiçbiri worker crash'i değil:

```jsonc
// bayat OCC token'ı → insan hattının KENDİ kodu
{ "tool_call_id": "agttool_…", "status": "failed",
  "failure_code": "STRATEGY_DRAFT_CONFLICT",
  "failure_reason": "This draft changed in another session. Reload the latest version before saving.",
  "details": [] }

// bozuk istek (draft_id yok) → komut HİÇ çalışmadı
{ "tool_call_id": "agttool_…", "status": "failed",
  "failure_code": "AGENT_TOOL_REQUEST_INVALID",
  "failure_reason": "'draft_id' must be a non-empty string.",
  "details": [ { "field": "draft_id", "actual": "NoneType" } ] }

// yasak scope → governance reddi (REJECTED, FAILED değil)
{ "tool_call_id": "agttool_…", "status": "rejected",
  "reason_code": "AGENT_TOOL_SCOPE_FORBIDDEN",
  "reason": "Tool 'strategy.save_revision' cannot run under policy scope 'execution'." }
```

---

## 4. Adjudication — `REJECTED` vs durable `FAILED`

Sevk edilmiş gateway yalnız `ForbiddenError`'ı yakalıyor ve **REJECTED** yazıyordu (AL-11:
*kaydedilmiş governance reddi*). Tipli ama governance-dışı her hata (bayat OCC, compiler
blocker, idempotency çakışması, bozuk istek) `dispatch_tool_call`'dan **kaçıyordu** →
worker `rollback` → dramatiq 3 kez retry → **hiç tool-call satırı kalmıyordu**. Deterministik
bir reddin üç kez denenip kanıtsız kaybolması durable bir gateway için kabul edilemez.

Bu slice **yalnız strategy ailesi** için (`_DURABLE_FAILURE_TOOLS`) ikinci bir dal ekliyor:
tipli `AppError` → **terminal `FAILED`**, `failure_code` = insan hattının kodunun **aynısı**,
`details` (compiler issue listesi) plan yapabilmek için taşınıyor.

**Bilerek dar tutuldu.** S4 aileleri (allocation / trade_log) mevcut *çağırana-propagate*
sözleşmesini koruyor; onu `test_gateway_parity_s4.py:356` (`AllocationHasBlockersError`) ve
`test_shared_allocation_containment.py:219` (`ReadinessBlockedError`) **kilitliyor** ve bu
slice'ın kapsamı değil. Sonuç: gateway'de iki aile iki farklı hata sözleşmesi taşıyor —
**bilinen, tescilli asimetri**; birleştirme ayrı bir slice'ın işi.

`FAILED` terminaldir → AL-14 gereği aynı gateway `idempotency_key` ile redelivery **yeniden
çalıştırmaz**, kaydedilmiş sonucu aynen döndürür.

### 4.1 SAVEPOINT — kaydedilmiş başarısızlık yarım iş taşımaz

Durable `FAILED` yazmanın kendi tuzağı var ve **kod incelemesinde yakalandı, negatif kontrolle
ölçüldü**: bir komut satır **flush edip** ardından tipli bir hataya çarpabilir (örn.
`save_strategy_revision` immutable revision'ı + mirror'ı flush ettikten sonra
`_repin_attached_items` içinde Mainboard OCC çakışması). İnsan hattını istek kapsamının
`rollback`'i kurtarır; **durable worker hattında öyle bir kapsam yoktur** — `run_tool_job`
dönerse worker `commit` eder. Yani savepoint olmadan gateway "FAILED" raporlarken yarım
yazılmış bir revision'ı commit edebilirdi.

Bu yüzden strategy handler'ı `session.begin_nested()` (SAVEPOINT) içinde koşuyor: hata
halinde handler'ın yazdığı **her şey** geri alınır, `agent_tool_call` satırı ise
savepoint'ten **önce** yaratıldığı için kanıt olarak ayakta kalır.

**Negatif kontrol (ölçüldü, 2026-08-03):** savepoint devre dışı bırakıldığında
`test_a_recorded_failure_rolls_back_everything_the_command_wrote` **kırmızı** oluyor —
`run_idempotent`'ın operasyondan ÖNCE yazdığı `idempotency_keys` satırı commit ediliyordu
(`assert 1 == 0`). Savepoint ile 0. Test bu yüzden vakum değil, gerçek bir regresyon kapısı.

---

## 5. Korunan sınırlar (test ile ölçüldü)

| Kural | Nasıl korunuyor |
|---|---|
| Agent yalnız **kendi** taslağını/kökünü mutate eder | `ensure_can_edit`/`ensure_can_view` komutun içinde; insan private draft'ı → **REJECTED `ACCESS_DENIED`**, insan hattının kodunun aynısı, sıfır yan etki |
| Runtime id ≠ principal id | Kök `owner/created_by = agent_alpha` (principal); `agent_tool_call.agent_id = alpha-agent` (runtime). İkisi **karışmıyor** |
| Human Mainboard auto-attach YOK | Araçların **workspace/attach parametresi yok**; insanın panosu 0 item + `composition_hash` değişmiyor, Agent'ın kendi panosu da 0 item |
| Save ≠ Ready PASS ≠ Run | Gövde `ready_state: "STALE"` döndürür; koşu ayrı araç |
| Human ile parity | Aynı payload → **aynı `config_hash`**, aynı `revision_number` |
| Idempotency duplicate revision üretmez | Gateway anahtarı → `replayed: true`, aynı `tool_call_id`; domain anahtarı → iki farklı tool call, **tek revision**; aynı anahtar + farklı payload → `IDEMPOTENCY_KEY_CONFLICT` |
| Durable kanıt | `enqueue_tool_call` → `run_tool_job`: audit (`strategy.revision_created`) + outbox + `tool_call_started/succeeded` + `strategy_revision_created` agent event'leri; redelivery replay eder |
| Analysis Lab görünürlüğü | `list_task_tool_calls` / `get_tool_call` yeni aileyi literal adı ve `failure_code`'uyla gösterir |

---

## 6. Dürüst sınırlar — bu slice'ın KAPATMADIĞI

1. **`trading_signal.*` araçları hâlâ YOK.** G-03'ün ikinci yarısı ve doc 04 **TS-20** /
   doc 03 **AOS-20**'nin literal "via Tool Gateway" cümlesi **açık kalıyor**. Bu slice
   onlara dokunmadı; `test_acceptance_agent_parity_gaps.py` docstring'i bu sınırı yeniden
   doğrulanmış olarak taşıyor.
2. **Approve / publish / Admin / Trash aracı eklenmedi** (durma koşulu). Agent bu
   yetkileri kazanmaz — doc 18 §14, AL-12/AL-16 aynen geçerli.
3. **Strategy ailesinin diğer komutları bilerek dışarıda:**
   `derive_strategy_draft_from_package`, `clear_strategy_draft`,
   `set_strategy_rationale_family`. Prompt'un minimum seti beş araçtır; bunları eklemek
   Agent'a yeni ürün davranışı icat etmek olurdu.
4. **Agent executor'ın aşama makinesine strategy adımı eklenmedi.**
   `jobs/agent_executor.py` doc 18'in ready_check → request → result.query → artifact.create
   döngüsünü uygular; Agent'ın *ne zaman* strateji yazacağı canonical bir ürün kararıdır ve
   corpus'ta yoktur → uydurulmadı. Araçlar **plan zamanında sunuluyor**
   (`exposed_tool_names` → Coordinator `exposed_tools` menüsü, test ile kilitli), executor
   çağrı yapmıyor.
5. **Capability gating yok** — strategy araçları V1 aktif yüzeydir, `CAPABILITY_GATED_TOOLS`
   dokunulmadı.
6. **Frontend değişmedi.** Bu tamamen sunucu tarafı bir parity yüzeyidir.
