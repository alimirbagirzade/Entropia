# Stage 7 — User Manual (doc 21) & Future Dev (doc 22) — Kickoff / Resume

> **Amaç:** Temiz oturumda kaldığımız yerden devam. Yapıştırmaya hazır resume prompt en altta.
> Stage 7a = User Manual (doc 21) ÖNCE; Stage 7b = Future Dev (doc 22) SONRA. Alt-dilim atlanmaz.

## Nerede kaldık (2026-07-02)

- **Stage 0–6 TAMAMLANDI.** 6c (Trash, doc 20) PR **#28** MERGED → `main` = **`b437254`**
  (**git log ile doğrula** — özet stale-by-default). Alembic head = **`0018_trash_page`**
  (yeni tablo yok — `trash_entries` sayfa sözleşmesi kolonları + `(deleted_at DESC, id DESC)`
  keyset indeksi). İlk yeni migration **`0019_*`** (→0018).
- **Sıradaki = Stage 7a — User Manual (doc 21).** Branch `feat/stage-7a-user-manual`.

## 6c'nin bıraktıkları (reuse anchor'ları — tam sembol adları)

- **`application/commands/deletion.py`**: `soft_delete_entity(session, actor, *, entity_id,
  reason=None, display_name=None, original_location=None, deletion_snapshot=None)` (row-lock +
  idempotent tekrar + `_soft_delete_preflight` tip dispatcher'ı — 7a manual dokümanı silme buna
  entity_type dalı ekleyebilir), `restore_trash_entry`, `request_purge`, `RESULT_ENTITY_TYPE`
  tipi dispatch örneği (registry-dışı satırlar için şablon).
- **`application/jobs/purge.py`**: `run_purge` worker + `_purge_preflight`/`_finalize_purge`
  tip dalları (manual doc purge kuralı: "Built-in/system content purge policy may block" —
  doc 20 §10 satırı 7a'da buraya bağlanır).
- **`domain/trash/page.py`**: `TRASH_OBJECT_LOCATIONS` kataloğu — 7a'da `manual_document`
  tipi + "Help / User Manual" lokasyonu EKLENMELI (doc 20 §3.3 zaten listeliyor).
- **`domain/identity/policy.require_trash_admin`** (403 `TRASH_ACCESS_FORBIDDEN`),
  `require_admin_panel`, `require_admin`.
- **6a-2 Tool Gateway** (`application/jobs/agent_tools.py`): `ToolName` registry + handler
  map — 7a Agent tool'ları (`documentation.search`, `documentation.get_section`,
  `artifact.attach_citation`) buraya eklenir (AL-01/AL-11..16 parity düzeni).
- **Genel:** `domain/agent_lab/cursor` (opaque keyset + `clamp_limit`), `run_idempotent`,
  `audit_repo.add_audit_event/add_outbox_event`, `enum_column`, `new_id`, `TimestampMixin`,
  `session.refresh(with_for_update=True)` OCC deseni, `enqueue_job`/`send_job` worker deseni,
  `EntityRegistry`/`create_root_with_revision`/`append_revision` (revizyonlu kökler).

## 7a tasarım pointer'ları (doc 21'i TAM çıkar)

- **`domain/manual`**: atomic unique `stream_position` (created_at DEĞİL — plan acceptance),
  canonical content block modeli (raw HTML/MD innerHTML YASAK), stable sequence key ile
  restore (doc 20 §10 User Manual satırı: "restore original stable sequence keyyle returns
  without deleting later segments").
- **Tablolar (plan):** `manual_document`, `manual_document_revision`, `manual_stream_entry`,
  `manual_content_block`, `manual_search_chunk`, `manual_publication_event` → migration
  `0019_user_manual` (L1 FK insert-order proof + up/down/up + parity zorunlu).
- **Endpoints:** `GET /v1/manual/stream` (all-role, cursor), `GET /v1/manual/search?q=&cursor=`
  (Postgres FTS; eventually consistent ama publication atomik), Admin-only write:
  `POST /v1/admin/manual/documents`, `:upload`, `POST .../{id}/revisions`,
  `DELETE .../{id}` + `:restore` (LANDED Trash çekirdeği üzerinden — soft delete entry yazar,
  restore Admin Trash'ten). `BASELINE_MANUAL_IMMUTABLE` (baseline UI'dan silinemez/değişemez).
- **Agent parity:** Tool Gateway'e `documentation.search`/`documentation.get_section` (read)
  + `artifact.attach_citation`; Agent manual WRITE yeteneği YOK.

## 7b tasarım pointer'ları (doc 22 — 7a bittikten sonra)

- `domain/capability`: 7 activation gate + state graph; `application/commands/
  capability_transition` (Admin + legal edge + non-empty reason + `expected_registry_version`
  OCC + idempotency_key); inactive op → `CAPABILITY_NOT_ACTIVE` (`shared/errors`'ta ZATEN var).
- Agent'a tool contract yalnız Active/Limited capability'ler için (CR-08); placeholder'larda
  SAHTE endpoint/job/progress/chart YOK (CR-09); Live Trade ayrı execution plane.

## Yöntem (5a→6c dersleri — birebir)

- **Workflow KULLANMA** — doğrudan yaz. YENİ dosya = Bash heredoc (gate-free); mevcut dosya
  Edit → 4-fact (importers Grep / etkilenen API / data schema / talimat verbatim). `cd backend`.
- Lokal doğrula: `uv run ruff check . && uv run ruff format --check . && uv run mypy src` +
  `DATABASE_URL=... uv run pytest --no-cov -q` (719 mevcut test yeşil kalmalı) + HER yeni
  `create_*` için **L1 FK proof** + alembic `0019` **up/down/up** (`LC_ALL=en_US.UTF-8`,
  önce `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`) + migration↔model parity.
- **code-reviewer subagent → CRITICAL/HIGH AMPİRİK DOĞRULA** (6b: 5 bulgudan 3 false-positive;
  6c: 2/2 gerçekti — HER ZAMAN doğrula) → commit (conventional, **attribution YOK**) → PR →
  `gh pr checks <n> --watch` (repo'da 3 CI check VAR: Backend/Frontend/Docker) → **merge için
  kullanıcıya sor** (self-merge kapalı).
- Türkçe, autonomous, **MALİYET BİLİNÇLİ**. Kapanışta: 7b kickoff + resume prompt +
  `STAGE2_HANDOFF.md` + `CLAUDE.md` + memory (ecc graph + claude-mem) güncelle.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 7a başlat: User Manual (doc 21). Önce bağlamı oku, working loop'a göre
ilerle. Branch feat/stage-7a-user-manual AÇ. MALİYET BİLİNÇLİ ol.

Durum: Stage 0–6 TAMAMLANDI (6c Trash PR #28 merged). main = b437254 (git log ile DOĞRULA —
özet stale-by-default). Alembic head 0018_trash_page. Yeni migration 0019_* (→0018).

ÖNCE OKU (otorite sırası): (1) docs/STAGE7_KICKOFF.md — bu dilimin tam handoff'u.
(2) docs/STAGE2_HANDOFF.md → "Stage 6c landed (PR #28)" + "Next: Stage 7". (3)
docs/STAGE_BUILD_PLAN.md "Stage 7" satırı. (4) docs/spec/21_..User_Manual §'lerini TAM çıkar
(stream position, canonical block, baseline immutability, search, Admin write, restore).
(5) mevcut kod: application/commands/deletion.py (soft_delete_entity tip preflight +
restore_trash_entry — manual_document tipi entegre olacak), domain/trash/page.py
(TRASH_OBJECT_LOCATIONS'a manual_document ekle), application/jobs/agent_tools.py (Tool
Gateway — documentation.search/get_section + artifact.attach_citation eklenecek),
domain/agent_lab/cursor, run_idempotent, audit/outbox, EntityRegistry revision zinciri.

TASARIM: domain/manual (atomic unique stream_position — created_at DEĞİL; canonical content
blocks — raw HTML/MD YASAK; stable sequence key ile Trash restore), migration 0019_user_manual
(manual_document, manual_document_revision, manual_stream_entry, manual_content_block,
manual_search_chunk, manual_publication_event), GET /v1/manual/stream + /search (all-role,
Postgres FTS, opaque cursor; search eventually consistent, publication atomik), Admin-only
write (POST /v1/admin/manual/documents, :upload, revisions, DELETE + :restore Trash çekirdeği
üzerinden), BASELINE_MANUAL_IMMUTABLE, Agent read-only tool parity (Tool Gateway).

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 6c pattern birebir. YENİ dosya Bash heredoc; mevcut
dosya Edit 4-fact. cd backend. ruff+format+mypy+pytest (719 test yeşil kalmalı) + HER yeni
create_* için L1 FK proof + alembic 0019 up/down/up (LC_ALL=en_US.UTF-8, DROP SCHEMA önce) +
migration↔model parity. code-reviewer subagent → CRITICAL/HIGH AMPİRİK DOĞRULA (6c'de 2/2
gerçekti) → düzelt → commit (conventional, attribution YOK) → PR → gh pr checks --watch
(Backend/Frontend/Docker check'leri var) → YEŞİL olunca merge için bana sor. Türkçe,
autonomous, MALİYET BİLİNÇLİ. Kapanışta: 7b (Future Dev, doc 22) kickoff + resume prompt +
STAGE2_HANDOFF.md + CLAUDE.md + memory (ecc graph + claude-mem) güncelle.
```
