# Stage 7b — Future Dev (doc 22) — Kickoff / Resume

> **Amaç:** Temiz oturumda kaldığımız yerden devam. Yapıştırmaya hazır resume prompt en altta.
> Stage 7b = Future Dev (doc 22) — Stage 7'nin son dilimi; ardından Stage 8 (e2e integration & hardening).

## Nerede kaldık (2026-07-02)

- **Stage 0–7a TAMAMLANDI.** 7a (User Manual, doc 21) PR **#30** MERGED → `main` = **`be65d4e`**
  (**git log ile doğrula** — özet stale-by-default). Alembic head = **`0019_user_manual`**
  (6 tablo: `manual_documents`/`manual_document_revisions`/`manual_stream_entries`/
  `manual_content_blocks`/`manual_search_chunks`/`manual_publication_events` + GIN FTS +
  baseline seed). İlk yeni migration **`0020_*`** (→0019). Test tabanı: **758 yeşil**.
- **Sıradaki = Stage 7b — Future Dev (doc 22).** Branch `feat/stage-7b-future-dev`.

## 7a'nın bıraktıkları (reuse anchor'ları — tam sembol adları)

- **`domain/manual`** — sayfa-lokal root deseni (EntityRegistry DIŞI kök + `deletion_state`
  overlay + Trash tip dispatch'i): `MANUAL_ENTITY_TYPE` örneği; 7b'de capability registry'nin
  registry-dışı satır ihtiyacı olursa şablon budur.
- **`infrastructure/postgres/repositories/manual.py`** — **L1 DERSİ (kritik):** SQLAlchemy,
  `relationship()` YOKSA tablolar arası insert'leri FK topolojisine göre SIRALAMAZ —
  `create_document`/`create_revision`/`create_stream_entry` async ve parent-before-child
  **flush** yapar. 7b'nin her yeni `create_*`'ı aynı deseni izlemeli. Ayrıca
  `lock_stream` (`pg_advisory_xact_lock(210_721)`) global-serileştirme örneği ve
  `search_chunks` exact-precision `(Numeric rank, id)` keyset FTS deseni.
- **`application/commands/manual.py`** — one-tx no-commit + `run_idempotent` + OCC
  (`expected_stream_version` / `expected_head_revision_id`) + `_audit_and_outbox` düzeni;
  7b `capability_transition` bu yapıyı `expected_registry_version` ile aynalar.
- **`domain/identity/policy.require_manual_admin`** — dar Admin-write guard deseni
  (route VE service). 7b'de capability transition için aynı desen (mevcut `require_admin`
  yeterli olabilir; doc 22 ayrı kod isterse yeni guard).
- **6a-2 Tool Gateway** (`domain/agent_lab/tool_gateway.ToolName` + `TOOL_ALLOWED_SCOPES`,
  `application/jobs/agent_tools._HANDLERS`) — 7a'da 3 tool eklendi
  (`documentation.search/get_section`, `artifact.attach_citation`); 7b **CR-08**: Agent'a
  tool contract YALNIZ Active/Limited capability'ler için sunulur — gateway'e capability
  gate'i burada bağlanır (`agent_tool_call.tool_name` düz String(64), CHECK yok).
- **Genel:** `enum_column`, `new_id`, `TimestampMixin`, `domain/agent_lab/cursor`
  (opaque keyset + `clamp_limit`), `run_idempotent`, `audit_repo.add_audit_event/
  add_outbox_event`, `session.refresh(with_for_update=True)`, `enqueue_job`/`send_job`.
- **`shared/errors.CapabilityNotActiveError`** — `CAPABILITY_NOT_ACTIVE` (403) **ZATEN VAR**
  (Stage 0'dan beri); 7b yalnız kullanır, yeniden tanımlamaz.

## 7b tasarım pointer'ları (doc 22'yi TAM çıkar)

- **`domain/capability`**: capability registry + **7 activation gate** + state graph
  (doc 22 §'lerinden tam çıkar: her capability'nin lifecycle state'i, legal edge'ler,
  gate'lerin her birinin doğrulanması). Placeholder'larda SAHTE endpoint/job/progress/chart
  YOK (CR-09) — inactive her operasyon `CAPABILITY_NOT_ACTIVE` döner, job/output üretmez.
- **`application/commands/capability_transition`**: Admin + legal state edge + **non-empty
  reason** + `expected_registry_version` OCC + `idempotency_key`; audit + outbox tek tx.
- **Tablolar (plan):** `future_capability`, `capability_activation_event`,
  `analysis_artifact`, `view_dataset`, `experiment_proposal`, `execution_plan` →
  migration `0020_future_dev` (→0019; L1 FK proof + up/down/up + parity zorunlu;
  capability registry seed'i migration'da olabilir — 7a baseline seed deseni).
- **Endpoints:** `GET /api/v1/capabilities`, `GET /capabilities/{key}`,
  `POST /capabilities/{key}/lifecycle-transitions` (Admin),
  `GET /future-dev/graphic_view/overview`, `POST /view-datasets/query`
  (yalnız Limited/Active), `POST /analysis-artifacts`.
- **CR-08:** Agent'a tool contract yalnız Active/Limited capability'ler için;
  **Live Trade ayrı execution plane** — asla Backtest-RUN varyantı değil.

## Yöntem (5a→7a dersleri — birebir)

- **Workflow KULLANMA** — doğrudan yaz. YENİ dosya = Bash heredoc (gate-free); mevcut dosya
  Edit → 4-fact (importers Grep / etkilenen API / data schema / talimat verbatim). `cd backend`.
- Lokal doğrula: `uv run ruff check . && uv run ruff format --check . && uv run mypy src` +
  `DATABASE_URL=... uv run pytest --no-cov -q` (**758 mevcut test yeşil kalmalı**) + HER yeni
  `create_*` için **L1 FK proof + parent-before-child flush** + alembic `0020` **up/down/up**
  (`LC_ALL=en_US.UTF-8`, önce `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`) +
  migration↔model parity (`alembic check` çıktısında yeni tablo diff'i sıfır olmalı —
  eski tablolardaki indeks-adı gürültüsü bilinen durum).
- **code-reviewer subagent → CRITICAL/HIGH AMPİRİK DOĞRULA** (6b: 3/5 false-positive;
  6c: 2/2 gerçek; 7a: 0 bulgu — HER ZAMAN doğrula) → commit (conventional, **attribution
  YOK**) → PR → `gh pr checks <n> --watch` (Backend/Frontend/Docker) → **merge için
  kullanıcıya sor** (self-merge kapalı).
- Türkçe, autonomous, **MALİYET BİLİNÇLİ**. Kapanışta: Stage 8 kickoff + resume prompt +
  `STAGE2_HANDOFF.md` + `CLAUDE.md` + memory (ecc graph + claude-mem) güncelle.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 7b başlat: Future Dev (doc 22). Önce bağlamı oku, working loop'a göre
ilerle. Branch feat/stage-7b-future-dev AÇ. MALİYET BİLİNÇLİ ol.

Durum: Stage 0–7a TAMAMLANDI (7a User Manual PR #30 merged). main = be65d4e (git log ile
DOĞRULA — özet stale-by-default). Alembic head 0019_user_manual. Yeni migration 0020_* (→0019).
758 test yeşil.

ÖNCE OKU (otorite sırası): (1) docs/STAGE7B_KICKOFF.md — bu dilimin tam handoff'u.
(2) docs/STAGE2_HANDOFF.md → "Stage 7a landed (PR #30)" + "Next: Stage 7b". (3)
docs/STAGE_BUILD_PLAN.md "Stage 7" satırı. (4) docs/spec/22_..Future_Dev §'lerini TAM çıkar
(capability registry, 7 activation gate, state graph, transition sözleşmesi, graphic view,
view-dataset query, CR-08/CR-09 sınırları). (5) mevcut kod: shared/errors.py
(CapabilityNotActiveError ZATEN VAR), application/commands/manual.py (one-tx + run_idempotent
+ OCC + _audit_and_outbox deseni), infrastructure/postgres/repositories/manual.py (L1
parent-before-child flush DERSİ + advisory lock + keyset), domain/agent_lab/tool_gateway.py +
application/jobs/agent_tools.py (CR-08 capability-gated tool contract buraya bağlanır),
domain/identity/policy.py (require_admin), domain/agent_lab/cursor.

TASARIM: domain/capability (7 activation gate + state graph; placeholder'da SAHTE
endpoint/job/progress/chart YOK — CR-09), application/commands/capability_transition
(Admin + legal edge + non-empty reason + expected_registry_version OCC + idempotency_key),
inactive op → CAPABILITY_NOT_ACTIVE, migration 0020_future_dev (future_capability,
capability_activation_event, analysis_artifact, view_dataset, experiment_proposal,
execution_plan), GET /api/v1/capabilities + /capabilities/{key} + POST
/capabilities/{key}/lifecycle-transitions (Admin) + GET /future-dev/graphic_view/overview +
POST /view-datasets/query (Limited/Active only) + POST /analysis-artifacts. Agent tool
contract yalnız Active/Limited (CR-08); Live Trade ayrı execution plane.

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 7a pattern birebir. YENİ dosya Bash heredoc; mevcut
dosya Edit 4-fact. cd backend. ruff+format+mypy+pytest (758 test yeşil kalmalı) + HER yeni
create_* için L1 FK proof + parent-before-child flush + alembic 0020 up/down/up
(LC_ALL=en_US.UTF-8, DROP SCHEMA önce) + migration↔model parity. code-reviewer subagent →
CRITICAL/HIGH AMPİRİK DOĞRULA → düzelt → commit (conventional, attribution YOK) → PR →
gh pr checks --watch (Backend/Frontend/Docker) → YEŞİL olunca merge için bana sor. Türkçe,
autonomous, MALİYET BİLİNÇLİ. Kapanışta: Stage 8 kickoff + resume prompt + STAGE2_HANDOFF.md
+ CLAUDE.md + memory (ecc graph + claude-mem) güncelle.
```
