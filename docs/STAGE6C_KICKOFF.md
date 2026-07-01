# Stage 6c — Trash (doc 20) — Kickoff / Resume

> **Amaç:** Temiz oturumda kaldığımız yerden devam. Yapıştırmaya hazır resume prompt en altta.

## Nerede kaldık (2026-07-02)

- **Stage 0–5c + 6a + 6a-2 + 6b TAMAMLANDI.** 6b (Panel/Management/Logs, doc 19) PR **#26**
  MERGED → `main` = **`77ea5b4`** (**git log ile doğrula** — özet stale-by-default).
  Alembic head = **`0017_agent_tool_gateway`** (6b yeni tablo/migration EKLEMEDİ — Logs =
  `audit_events` üzerinde read model). İlk yeni migration (gerekirse) **`0018_*`** (→0017).
- **Sıradaki = Stage 6c — Trash (doc 20).** Branch `feat/stage-6c-trash`. Stage 6 son alt-dilimi.

## ÖNEMLİ: Trash çekirdeği ZATEN Stage 1'de indi — 6c bunun ÜZERİNE sayfa sözleşmesi kurar

Reuse anchor'ları (tam sembol adlarıyla — ÖNCE ne yaptıklarını oku):
- **application/commands/deletion.py**: `soft_delete_entity(session, actor, *, entity_id, reason)`,
  `restore_entity(session, actor, *, entity_id)`, `purge_entity(session, actor, *, entity_id)`,
  `_require_root` (EntityRegistry resolve).
- **infrastructure/postgres/models**: `TrashEntry` (Stage 1), `EntityRegistry`
  (`deletion_state`/`deleted_at`/`deleted_by`/`delete_reason`/`row_version`/`current_revision_id`).
- **domain/lifecycle/enums.DeletionState**: `ACTIVE`/`SOFT_DELETED`/`PURGE_PENDING`/`PURGED`.
- **application/queries/trash.py** + **apps/api/routes/trash.py**: `DELETE /entities/{id}` (soft),
  `GET /trash`, `POST /trash/{id}/restore`, `DELETE /trash/{id}/purge` (BASİT mevcut sürüm —
  6c bunu cursor'lu list projection + filtreler + restore-eligibility ile GENİŞLETİR).
- **6b'den yeni**: `require_admin_panel` (Admin-only guard), `domain/agent_lab/cursor` (opaque keyset),
  `run_idempotent`, `audit_repo.add_audit_event/add_outbox_event`.

## 6c tasarım pointer'ları (doc 20 §2/§4/§5/§9.1-9.3/§10/§11/§12/§14 TAM çıkar)

- **§9.1 state layers / §9.2 deletion state machine** (active→soft_deleted→purge_pending→purged):
  mevcut `DeletionState` + `soft_delete/restore/purge` ile hizala; eksik geçiş varsa ekle.
- **§9.3 delete/restore/purge command flow**: OCC (`expected_row_version`/If-Match), idempotency,
  audit+outbox; **purge = Admin-only** (`require_admin`/`require_admin_panel`), soft-delete = owner|Admin.
- **§10 type-specific dependency + restore + historical-integrity rules** (EN KRİTİK): purged/renamed
  parent'a restore engeli; dependency (ör. bir Strategy'e bağlı Package) restore/purge sırası;
  historical manifest/audit IMMUTABLE — restore geçmişi yeniden yazmaz.
- **§4/§5 Trash list projection**: Admin/owner görünürlüğü SQL'e it (visibility push-down);
  cursor pagination (keyset, `domain/agent_lab/cursor`), filtreler (type, deleted_by, time),
  restore-eligibility flag'i; V18 array değil server read model.
- **§11 Agent sınırı**: Agent kendi artifact'ını soft-delete edebilir (6a-2 `artifact.soft_delete`,
  AL-16), ama Trash restore/purge veya başka owner'ın kaydına ERİŞEMEZ.
- **YENİ tablo pek olası DEĞİL** — büyük olasılıkla `EntityRegistry`+`TrashEntry` yeter. Gerekirse `0018_*`.

## REUSE

`soft_delete_entity`/`restore_entity`/`purge_entity` (mevcut), `TrashEntry`/`EntityRegistry`,
`DeletionState`, `require_admin`/`require_admin_panel`, `domain/agent_lab/cursor` (keyset),
`run_idempotent`, `audit_repo.add_audit_event/add_outbox_event`, `enum_column`, `new_id`,
`TimestampMixin`, `session.refresh(with_for_update=True)` OCC pattern.

## Yöntem (5a/6a/6a-2/6b dersi — birebir)

- **Workflow KULLANMA** — doğrudan yaz. YENİ dosyaları **Bash heredoc** (gate-free); mevcut dosya
  Edit → 4-fact (importers Grep / etkilenen API / data schema / user request verbatim). `cd backend` teyit.
- ruff/mypy tüm proje. Lokal doğrula: `ruff check . && ruff format --check . && mypy src && pytest --no-cov -q`
  (DATABASE_URL ile) + **HER yeni `create_*` için L1 FK proof** + (yeni migration varsa) **alembic `0018`
  up/down/up** (`LC_ALL=en_US.UTF-8`, `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` önce) +
  migration↔model parity. Integration conftest `create_all`.
- **code-reviewer subagent → CRITICAL/HIGH AMPİRİK DOĞRULA** (6b'de 5 bulgunun 3'ü false-positive,
  2'si gerçekti — HER ZAMAN doğrula) → gerçek olanı düzelt → commit (conventional, **attribution YOK**) →
  PR → `gh pr checks <n> --watch` (bu repoda CI check yok → lokal yeşil = gate) → **merge için kullanıcıya sor**.
- Türkçe, autonomous, **MALİYET BİLİNÇLİ**. Her KAPANIŞTA: sıradaki kickoff + resume prompt +
  `STAGE2_HANDOFF.md` + `CLAUDE.md` + memory (ecc graph + claude-mem) güncelle. **6c = Stage 6 sonu.**

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 6c başlat: Trash (doc 20). Önce bağlamı oku, working loop'a göre ilerle.
Branch feat/stage-6c-trash AÇ. MALİYET BİLİNÇLİ ol.

Durum: Stage 0–5c + 6a + 6a-2 + 6b (Panel/Management/Logs, PR #26) TAMAMLANDI.
main = 77ea5b4 (git log ile DOĞRULA — özet stale-by-default). Alembic head
0017_agent_tool_gateway (6b migration EKLEMEDİ). İlk yeni migration (gerekirse) 0018_*.

ÖNCE OKU (otorite sırası): (1) docs/STAGE6C_KICKOFF.md — bu dilimin tam handoff'u.
(2) docs/STAGE2_HANDOFF.md → "Stage 6b landed (PR #26)" + "Next: Stage 6c". (3)
docs/STAGE_BUILD_PLAN.md "Stage 6" satırı. (4) docs/spec/20_..Trash §2 (policy),
§4/§5 (list/field contract), §9.1-9.3 (state layers + state machine + delete/restore/
purge flow), §10 (type-specific dependency/restore/historical-integrity — EN KRİTİK),
§11 (agent sınırı), §12 (validation/audit), §14 (acceptance) TAM çıkar. (5) mevcut kod:
application/commands/deletion.py (soft_delete_entity/restore_entity/purge_entity — ÜZERİNE
kur), application/queries/trash.py + apps/api/routes/trash.py (mevcut basit sürüm — cursor'lu
list projection + filtreler + restore-eligibility ile genişlet), TrashEntry/EntityRegistry
modelleri, DeletionState enum, require_admin/require_admin_panel, domain/agent_lab/cursor
(keyset), run_idempotent, audit/outbox.

TASARIM: Trash sayfası çekirdeği ZATEN Stage 1'de indi; 6c doc 20 sayfa sözleşmesini kurar:
§9.2 deletion state machine hizası (active→soft_deleted→purge_pending→purged), §9.3 delete/
restore/purge flow (OCC If-Match + idempotency + audit/outbox; PURGE Admin-only), §10 type-
specific dependency + restore + historical-integrity kuralları (purged/renamed parent'a restore
engeli, historical manifest/audit immutable), §4/§5 cursor-paginated Trash list projection
(visibility push-down, filtreler, restore-eligibility). Agent restore/purge YAPAMAZ (kendi
artifact soft-delete hariç, AL-16). YENİ tablo pek olası değil — EntityRegistry+TrashEntry yeter;
gerekirse 0018_*.

REUSE: soft_delete_entity/restore_entity/purge_entity (mevcut), TrashEntry/EntityRegistry,
DeletionState, require_admin/require_admin_panel, domain/agent_lab/cursor (keyset), run_idempotent,
audit/outbox, enum_column, new_id, TimestampMixin, session.refresh(with_for_update=True).

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 5a/6a/6a-2/6b pattern birebir. YENİ dosyaları Bash
heredoc (gate-free); mevcut dosya Edit 4-fact. cd backend teyit. ruff/mypy tüm proje. Lokal
doğrula (ruff+format+mypy+pytest DATABASE_URL ile + HER yeni create_* için L1 FK proof + yeni
migration varsa alembic 0018 up/down/up LC_ALL=en_US.UTF-8 DROP SCHEMA önce + migration↔model
parity). code-reviewer subagent → CRITICAL/HIGH AMPİRİK DOĞRULA (6b'de 3 false-positive/2 gerçek)
→ gerçek olanı düzelt → commit (conventional, attribution YOK) → PR → gh pr checks --watch (CI
check yoksa lokal yeşil = gate), YEŞİL olunca merge için bana sor. Türkçe, autonomous, MALİYET
BİLİNÇLİ. 6c = Stage 6 sonu — kapanışta Stage 7 kickoff'a geç. Her KAPANIŞTA: sıradaki kickoff +
resume prompt + STAGE2_HANDOFF.md + CLAUDE.md + memory güncelle.
```
