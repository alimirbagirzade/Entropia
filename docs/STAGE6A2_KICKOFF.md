# Stage 6a-2 — Analysis Lab Coordinator runtime loop + Tool Gateway (doc 18 §9.2/§10) — Kickoff / Resume

> **Amaç:** Temiz oturumda kaldığımız yerden devam. Yapıştırmaya hazır resume prompt en altta.

## Nerede kaldık (2026-07-01)

- **Stage 0–5c + 6a (Analysis Lab **surface+persistence**, doc 18-A) TAMAMLANDI.** 6a PR **#22** MERGED → `main` = **`c908cbc`** (**git log ile doğrula** — özet stale-by-default). Alembic head = **`0016_analysis_lab`**. İlk yeni migration (gerekirse) **`0017_*`** (→0016).
- **Sıradaki = Stage 6a-2 — Coordinator runtime loop + Tool Gateway (doc 18-B).** Branch `feat/stage-6a2-coordinator`.

## 6a'nın bıraktıkları (REUSE anchors — tam sembol adlarıyla)

- **domain/agent_lab/{enums,state_machine,cursor}**: `RuntimeStatus`/`RuntimeControl`/`AgentTaskStatus`/`AgentTaskPriority`(autonomous dahil)/`DirectiveStatus`/`HypothesisStatus`/`LabMessageType`; `TASK_ACTIVE/TERMINAL/STOPPABLE_STATES`, `ALPHA_AGENT_ID`; `runtime_can_pause/resume/request_stop`, `task_transition_allowed`, `directive_transition_allowed`, `parse_human_directive_priority`; opaque keyset cursor.
- **infrastructure/postgres/{models,repositories}/agent_lab**: 8 model + `al_repo.{get_runtime,create_task,get_task,page_tasks,recent_tasks,queue_counts,create_directive,next_queued_directive,create_checkpoint,max_checkpoint_no,get_latest_checkpoint,create_message,create_hypothesis,page_hypotheses,create_artifact_link,append_event,events_after,latest_event_seq}`.
- **application/commands/agent_coordinator** (SCAFFOLD → gerçek loop'a terfi et): `advance_to_safe_checkpoint`, `apply_pending_control`, `consume_next_directive`.
- **application/commands/agent_control**: `create_directive`, `pause_runtime`, `resume_runtime`, `stop_run` (row_version OCC). **application/commands/lab_message**: `record_discussion_message`.
- **application/queries/agent_workspace**: `get_overview`/`list_tasks`/`get_task`/`list_hypotheses`. **apps/api/routes/agent_lab**: 10 endpoint + SSE `/agent-events/stream`.
- **agent_event.seq** (BigInteger Identity) → SSE Last-Event-ID / gerçek event fan-out için hazır.

## 6a-2 tasarım pointer'ları (doc 18 §8/§9.2/§10/§11/§15 TAM çıkar)

- **Continuous Coordinator loop** (`apps/agent_coordinator`): UI'dan bağımsız çalışır (AL-01); pending control'ü safe checkpoint'te uygular; directive'i safe checkpoint'te tüketip **follow-up autonomous task** üretir; worker crash → last valid checkpoint'ten controlled retry/continuation (AL-14), **duplicate yok** (idempotency + at-least-once redelivery guard — `backtest_engine` pattern).
- **Tool Gateway** (`application/jobs/agent_tools`, `agent`/`agent-high` queue): her tool call `actor_context + task_id + checkpoint_id + input_manifest_id + idempotency_key + policy_scope + artifact_output_ref` ile kaydedilir. Human↔agent **parity**: `agent.task.query`, `data_bundle.resolve`, `package.proposal.create` (candidate/draft only — approve/publish YOK, AL-12), `backtest.ready_check`+`backtest.request` (Ready Check bypass YOK, manifest pinned), `result.query`+`artifact.create`+`followup_task.enqueue`.
- **Governance sınırları:** `agent_research_only` data execution/backtest input'a giremez (AL-11); cancelled/failed run normal Backtest Result üretmez; agent kendi artifact'ini soft-delete edebilir, restore/purge Admin-only (AL-16); agent dataset approval/Trash/role/publish yetkisi kazanmaz.
- **6a'dan taşınan düzeltme:** `stop_run`'a **tam task-row lock** ekle (loop artık concurrent — 6a'da runtime-lock + task re-read ile daraltıldı).

## REUSE

`run_idempotent`, `audit_repo.add_audit_event/add_outbox_event`, `request_context`/`RequestContext`, `require_authenticated/require_role/require_admin`, `enum_column`, `new_id`, `TimestampMixin`, generic `jobs`+`enqueue_job`+queue, `application/jobs/backtest_engine` (actor + at-least-once guard), 6a `agent_lab` domain/models/repo/commands (özellikle `agent_coordinator` scaffold).

## Yöntem (5a/6a dersi — birebir)

- **Workflow KULLANMA** — doğrudan yaz. YENİ dosyaları **Bash heredoc** (gate-free); mevcut dosya Edit → 4-fact (importers Grep / etkilenen API / data schema / user request verbatim). `cd backend` teyit et.
- ruff/mypy tüm proje. Lokal doğrula: `ruff check . && ruff format --check . && mypy src && pytest --no-cov -q` (DATABASE_URL ile) + **HER yeni `create_*` için L1 FK proof** + **alembic 0017 up/down/up** (`LC_ALL=en_US.UTF-8`, `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` önce) + migration↔model parity. Integration conftest `create_all` — seed'li tabloları (agent_runtime singleton) testte manuel seed et.
- **code-reviewer subagent → CRITICAL/HIGH AMPİRİK DOĞRULA** → gerçek olanı düzelt → commit (conventional, **attribution YOK**) → PR → `gh pr checks <n> --watch` → **YEŞİL olunca merge için kullanıcıya sor**.
- Türkçe, autonomous, **MALİYET BİLİNÇLİ**. Her KAPANIŞTA: sıradaki kickoff + resume prompt + `STAGE2_HANDOFF.md` + `CLAUDE.md` + memory (ecc + claude-mem) güncelle.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 6a-2 başlat: Analysis Lab Coordinator runtime loop + Tool Gateway
(doc 18 §9.2/§10). Önce bağlamı oku, working loop'a göre ilerle. Branch
feat/stage-6a2-coordinator AÇ. MALİYET BİLİNÇLİ ol.

Durum: Stage 0–5c + 6a (Analysis Lab surface+persistence, doc 18-A, PR #22) TAMAMLANDI.
main = c908cbc (git log ile DOĞRULA — özet stale-by-default). Alembic head
0016_analysis_lab. İlk yeni migration (gerekirse) 0017_*.

ÖNCE OKU (otorite sırası): (1) docs/STAGE6A2_KICKOFF.md — bu dilimin tam handoff'u.
(2) docs/STAGE2_HANDOFF.md → "Stage 6a landed" + "Next: Stage 6a-2" + deferred liste.
(3) docs/STAGE_BUILD_PLAN.md "Stage 6". (4) docs/spec/18_..Analysis_Lab §8 (flows),
§9.2 (Tool Gateway/API/event contract), §10 (UI-siz agent tool parity), §11, §15
(AL-01, AL-11..AL-16) TAM çıkar. (5) 6a kodu: domain/agent_lab/*, application/commands/
{agent_control,lab_message,agent_coordinator}, application/queries/agent_workspace,
infrastructure/postgres/{models,repositories}/agent_lab, apps/api/routes/agent_lab +
generic jobs/queue + application/jobs/backtest_engine (actor pattern) + enqueue_job.

TASARIM: 6a'daki agent_coordinator scaffold'ını (advance_to_safe_checkpoint /
apply_pending_control / consume_next_directive) GERÇEK continuous loop'a terfi ettir
(apps/agent_coordinator) — UI'dan bağımsız (AL-01), pending control'ü safe checkpoint'te
uygular, directive'i safe checkpoint'te tüketip follow-up autonomous task üretir, worker
crash → last checkpoint'ten controlled retry/continuation, duplicate yok. Tool Gateway =
application/jobs/agent_tools (agent/agent-high queue): her tool call actor_context +
task_id + checkpoint_id + input_manifest_id + idempotency_key + policy_scope +
artifact_output_ref ile kaydedilir. Parity: agent.task.query, data_bundle.resolve,
package.proposal.create (candidate/draft only, approve/publish YOK), backtest.ready_check
+ backtest.request (Ready Check bypass YOK, manifest pinned), result.query + artifact.
create + followup_task.enqueue. agent_research_only data execution/backtest input'a
giremez (AL-11). Cancelled/failed run normal Result üretmez. stop_run'a tam task-row lock
ekle (loop concurrent). YENİ tablo gerekiyorsa 0017_*.

REUSE: run_idempotent, audit/outbox, request_context, require_admin/require_role,
enum_column, new_id, TimestampMixin, generic jobs+enqueue_job+queue, backtest_engine
actor (at-least-once redelivery guard), 6a agent_lab domain/models/repo/commands.

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 5a/6a pattern birebir. YENİ dosyaları Bash
heredoc (gate-free); mevcut dosya Edit 4-fact. cd backend teyit. ruff/mypy tüm proje.
Lokal doğrula (ruff+format+mypy+pytest DATABASE_URL ile + HER yeni create_* için L1 FK
proof + alembic 0017 up/down/up LC_ALL=en_US.UTF-8 DROP SCHEMA önce + migration↔model
parity). Integration conftest create_all (agent_runtime singleton'ı testte manuel seed
et). code-reviewer subagent → CRITICAL/HIGH AMPİRİK DOĞRULA → gerçek olanı düzelt →
commit (conventional, attribution YOK) → PR → gh pr checks --watch, YEŞİL olunca merge
için bana sor. Türkçe, autonomous, MALİYET BİLİNÇLİ. Her KAPANIŞTA: sıradaki kickoff +
resume prompt + STAGE2_HANDOFF.md + CLAUDE.md + memory güncelle.
```
