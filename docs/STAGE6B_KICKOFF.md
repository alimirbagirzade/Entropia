# Stage 6b — Panel / Management / Logs (doc 19) — Kickoff / Resume

> **Amaç:** Temiz oturumda kaldığımız yerden devam. Yapıştırmaya hazır resume prompt en altta.

## Nerede kaldık (2026-07-01)

- **Stage 0–5c + 6a (surface+persistence) + 6a-2 (Coordinator loop + Tool Gateway) TAMAMLANDI.**
  6a-2 PR **#24** MERGED → `main` = **`23e13a5`** (**git log ile doğrula** — özet stale-by-default).
  Alembic head = **`0017_agent_tool_gateway`**. İlk yeni migration (gerekirse) **`0018_*`** (→0017).
- **Sıradaki = Stage 6b — Panel / Management / Logs (doc 19).** Branch `feat/stage-6b-panel-logs`.

## 6a-2'nin bıraktıkları (REUSE anchors — tam sembol adlarıyla)

- **domain/agent_lab/tool_gateway**: `ToolName`/`ToolCallStatus`/`PolicyScope`; `TOOL_ALLOWED_SCOPES`,
  `ensure_scope_allowed`, `queue_for_tool(tool, scope)`, `parse_tool_name`/`parse_policy_scope`.
- **application/jobs/agent_tools**: `dispatch_tool_call`, `run_tool_job`, `enqueue_tool_call` (agent/agent-high).
- **application/commands/agent_loop.run_coordinator_cycle** + `apps/agent_coordinator/__main__` (continuous loop).
- **infrastructure/postgres/{models,repositories}/agent_tool_gateway**: `AgentToolCall` + `create_tool_call`/
  `get_by_idempotency_key`/`get_tool_call`/`list_tool_calls`.
- **Governance error'ları (shared/errors)**: `ToolPolicyScopeError`, `ResearchInputBlockedError`,
  `AgentToolCallForbiddenError`, `ArtifactOwnershipError` (hepsi `ForbiddenError`/403).
- **Zaten var (Stage 1 identity)**: `application/commands/roles.py::change_user_role` — 6b role atama bunun
  ÜZERİNE kurulacak (ne yaptığını ÖNCE oku; Panel endpoint'leri + log_projection read model YENİ iş olabilir).

## 6b tasarım pointer'ları (doc 19 §2/§4.1/§4.2/§4.3/§9/§10/§11/§13 TAM çıkar)

- **Role Assignment** (`application/commands/role_assignment` veya mevcut `roles.change_user_role` genişlet):
  `PATCH /v1/admin/users/{id}/role` — atomik, `expected_head_revision_id`+If-Match OCC, **last active Admin
  koruması** (son admini düşürme → blok, doc 19 §9.3), audit+outbox. Registered Human User ↔ System Actor
  ayrımı (§4.1): system actor'lara human role atanamaz.
- **Logs read model** (`application/queries/log_projection`, Admin-only): `GET /v1/admin/logs` (filters +
  opaque keyset cursor — `domain/agent_lab/cursor` reuse), `GET /v1/admin/logs/{event_id}` (detail),
  `audit_events` üzerinden projection; **append-only** (PATCH/DELETE yok, düzeltme `causation_event_id` ile).
- **Management/Users**: `GET /v1/admin/users`, role-matrix, system-actors read.
- **Server-side policy (§2, §13)**: HER endpoint + service `require_admin` (menü gizleme YETMEZ); User/Supervisor
  Panel'e erişemez; UI hidden/disabled ≠ authorization.
- **Agent sınırı (§10)**: Agent role management/Trash yetkisi KAZANMAZ (6a-2'de zaten enforce; burada da doğrula).
- **YENİ tablo gerekiyorsa `0018_*`** (`log_projection` read model + gerekirse `role_policy_matrix`).

## REUSE

`change_user_role` (mevcut), `require_admin`/`require_role`, `Actor`/`request_context`/`RequestContext`,
`run_idempotent`, `audit_repo.add_audit_event/add_outbox_event`, `domain/agent_lab/cursor` (opaque keyset),
`enum_column`, `new_id`, `TimestampMixin`, `Role` enum, `AuditEvent`/`OutboxEvent` modelleri.

## Yöntem (5a/6a/6a-2 dersi — birebir)

- **Workflow KULLANMA** — doğrudan yaz. YENİ dosyaları **Bash heredoc** (gate-free); mevcut dosya Edit → 4-fact
  (importers Grep / etkilenen API / data schema / user request verbatim). `cd backend` teyit et.
- ruff/mypy tüm proje. Lokal doğrula: `ruff check . && ruff format --check . && mypy src && pytest --no-cov -q`
  (DATABASE_URL ile) + **HER yeni `create_*` için L1 FK proof** + **alembic `0018` up/down/up**
  (`LC_ALL=en_US.UTF-8`, `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` önce, iki ayrı statement) +
  migration↔model parity. Integration conftest `create_all`.
- **code-reviewer subagent → CRITICAL/HIGH AMPİRİK DOĞRULA** (6a-2'de review'in 3 CRITICAL/HIGH bulgusu da
  FALSE POSITIVE çıktı — her zaman doğrula) → gerçek olanı düzelt → commit (conventional, **attribution YOK**) →
  PR → `gh pr checks <n> --watch` → **YEŞİL olunca merge için kullanıcıya sor**.
- Türkçe, autonomous, **MALİYET BİLİNÇLİ**. Her KAPANIŞTA: sıradaki kickoff + resume prompt +
  `STAGE2_HANDOFF.md` + `CLAUDE.md` + memory (ecc graph + claude-mem) güncelle.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 6b başlat: Panel / Management / Logs (doc 19). Önce bağlamı oku,
working loop'a göre ilerle. Branch feat/stage-6b-panel-logs AÇ. MALİYET BİLİNÇLİ ol.

Durum: Stage 0–5c + 6a + 6a-2 (Analysis Lab Coordinator loop + Tool Gateway, PR #24)
TAMAMLANDI. main = 23e13a5 (git log ile DOĞRULA — özet stale-by-default). Alembic head
0017_agent_tool_gateway. İlk yeni migration (gerekirse) 0018_*.

ÖNCE OKU (otorite sırası): (1) docs/STAGE6B_KICKOFF.md — bu dilimin tam handoff'u.
(2) docs/STAGE2_HANDOFF.md → "Stage 6a-2 landed" + "Next: Stage 6b". (3)
docs/STAGE_BUILD_PLAN.md "Stage 6" satırı (Panel/Logs). (4) docs/spec/19_..Panel_
Management_Logs §2 (policy), §4.1 (human user↔system actor), §4.2 (role assignment),
§4.3 (logs projection), §9 (flows, özellikle §9.3 last-admin), §10 (agent sınırı), §11,
§13 (implementation rules) TAM çıkar. (5) mevcut kod: application/commands/roles.py
(change_user_role — ÜZERİNE kur), domain/identity/policy (require_admin/require_role),
infrastructure/postgres/models/audit (AuditEvent/OutboxEvent), domain/agent_lab/cursor
(opaque keyset), request_context/RequestContext, run_idempotent, audit/outbox.

TASARIM: Role Assignment PATCH /v1/admin/users/{id}/role — atomik, expected_head_
revision_id+If-Match OCC, LAST ACTIVE ADMIN koruması (son admini düşürme blok),
audit+outbox, system-actor'a human role atanamaz. Logs read model application/queries/
log_projection (Admin-only): GET /v1/admin/logs (filters + opaque keyset cursor), GET
/v1/admin/logs/{event_id}, audit_events üzerinden projection, APPEND-ONLY (düzeltme
causation_event_id). GET /v1/admin/users + role-matrix + system-actors. HER endpoint +
service require_admin (menü gizleme YETMEZ). Agent role management/Trash yetkisi
KAZANMAZ. YENİ tablo gerekiyorsa 0018_*.

REUSE: change_user_role (mevcut), require_admin/require_role, Actor/request_context,
run_idempotent, audit/outbox, domain/agent_lab/cursor (keyset), enum_column, new_id,
TimestampMixin, Role enum, AuditEvent/OutboxEvent.

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 5a/6a/6a-2 pattern birebir. YENİ dosyaları
Bash heredoc (gate-free); mevcut dosya Edit 4-fact. cd backend teyit. ruff/mypy tüm
proje. Lokal doğrula (ruff+format+mypy+pytest DATABASE_URL ile + HER yeni create_* için
L1 FK proof + alembic 0018 up/down/up LC_ALL=en_US.UTF-8 DROP SCHEMA önce + migration↔
model parity). code-reviewer subagent → CRITICAL/HIGH AMPİRİK DOĞRULA (6a-2'de hepsi
false positive çıktı) → gerçek olanı düzelt → commit (conventional, attribution YOK) →
PR → gh pr checks --watch, YEŞİL olunca merge için bana sor. Türkçe, autonomous,
MALİYET BİLİNÇLİ. Her KAPANIŞTA: sıradaki kickoff + resume prompt + STAGE2_HANDOFF.md +
CLAUDE.md + memory güncelle.
```
