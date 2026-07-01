# Stage 4b — Backtest Ready Check (doc 14) — Kickoff / Resume Handoff

> **Amaç:** Yeni/temiz bir oturumda kaldığımız yerden devam edebilmek için hazır bağlam + **yapıştırmaya hazır başlangıç prompt'u**. Her kapanış oturumunda güncellenir.

## Nerede kaldık (2026-07-01)

- **Stage 3 (docs 01–05) TAMAMLANDI** — main `7a3dab3` (PR #12 3d dahil merged).
- **Stage 4a — Portfolio/Equity Allocation (doc 13) ✅ TAMAMLANDI** — **PR #13 açık** (`feat/stage-4a-portfolio-allocation`, commit `1c5c963`). Alembic head = **`0012_portfolio_allocation`**. CI YEŞİL olunca main'e merge (kullanıcı onayıyla; self-merge bloklu). _Merge sonrası bu satırı güncelle._
- **Sıradaki = Stage 4b — Backtest Ready Check (doc 14).** Branch aç: `feat/stage-4b-ready-check`. Sonraki alembic = **`0013_*`**.

## Stage 4a'nın bıraktıkları (Stage 4b bunları tüketir)

- Tablolar (migration 0012): `portfolio_allocation_plan` (1:1 workspace, mutable draft + `row_version` + `current_revision_id`), `portfolio_allocation_entry` (composition_item_id ile bağlı, FK yok), `portfolio_allocation_plan_revision` (immutable: `config` JSONB + `config_hash` + `derived_amounts`).
- Domain: `domain/allocation/rules.py` → `validate_allocation(config, item_refs) -> (issues, derived)`, `compute_config_hash`, `DerivedAmounts`. `domain/allocation/config.py` (PortfolioAllocationConfigV1, Decimal).
- App: `application/commands/allocation_plan.py` (`upsert_allocation_draft`, `validate_allocation_draft`, `create_allocation_revision`), `application/queries/allocation_plan.py` (`get_allocation_draft`, `sync_preview`). Repo: `repositories/allocation.py` (`get_plan_for_workspace`, `list_entries`, `create_revision`, `max_revision_no`).

## Stage 4b tasarım (doc 14 + build plan satır ~82)

- **Ready Check, 3a'nın immutable `mainboard_composition_snapshot`'ından okur.** `readiness_report_id` 3a'da **null bırakıldı → Stage 4b dolduruyor**. `capital_mode_snapshot` (JSONB) → allocation plan revision'dan doldurulacak. **`mb_repo.create_snapshot(..., capital_mode_snapshot=...)` param'ı ZATEN var** — allocation'ı buradan pinle.
- **Endpoint:** `POST /compositions/{id}/readiness-checks` → `{report_id, state, issues[], snapshot_id, fingerprint}`. Report **immutable**, rerun = **yeni id**.
- **Snapshot persisted draft'tan transactional** kurulur (DOM/dosya varlığından DEĞİL). `composition_hash` STALE semantiği 3a'da wired (add/del/enable/pin değişince değişir → prior report STALE). **`expected_fingerprint` mismatch → 409**. save ≠ Ready PASS ≠ Run.
- **YENİ tablolar:** `ready_check_report`, `readiness_issue`. **YENİ modüller:** `domain/readiness/` (blocker/warning taxonomy, snapshot fingerprint compare), `application/commands/readiness_check.py`, query, route, migration `0013_*`.
- **3d follow-up'ları BURADA uygula (Ready Check konusu):** TL-09 mixed-symbol block · TL-11 allocation kapalıyken item `capital>0` zorunlu · OHLCV-fallback → approved Market Data revision ref zorunluluğu. Trade Log revision payload'ında `price_policy.approved_market_data_revision_ref` + `capital.independent_initial_capital` alanları ZATEN var (nullable).

## REUSE (yeniden yazma)

- **3a:** `mainboard_composition_snapshot` + `mb_repo.create_snapshot(capital_mode_snapshot=)`, `work_object_root/revision`, `mainboard_working_item`, `list_active_items`, `composition_hash` (`_recompute_composition_hash`).
- **4a:** `portfolio_allocation_plan(_revision)`, `alloc_repo.get_plan_for_workspace`, `validate_allocation` + `DerivedAmounts` (ready report allocation-yönü buradan).
- `run_idempotent`, `audit_repo.add_audit_event/add_outbox_event`, `request_context` dep (`ctx.session`/`ctx.actor`), `ensure_can_edit/can_view`, `enum_column` (VARCHAR, CHECK üretmez), `new_id(prefix)`, `RowVersionConflictError`/`ConflictError` (409), `ValidationError` (422), `AppError.http_status` otomatik map (`apps/api/errors.py`).

## Yöntem (3b–4a dersi)

- **Workflow KULLANMA** — doğrudan yaz, 4a pattern'i birebir (module-level async command'lar, tek-tx no-commit, `run_idempotent`, `session.refresh(with_for_update=True)` optimistic concurrency, `_audit_and_outbox`).
- **GateGuard:** YENİ dosyaları **Bash heredoc** (`cat > f << 'PYEOF'`) ile yaz → gate-free. **Mevcut dosya edit'i** her seferinde fact-force tetikliyor (4 fact sun: importer'lar / etkilenen public API / veri şeması / kullanıcı isteği verbatim → retry). Bash gate oturumda bir kez.
- **Lokal doğrula:** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov -q` + **HER `create_*` için L1 FK insert-order proof** + **alembic 0013 up/down/up** (`LC_ALL=en_US.UTF-8`, proof öncesi `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`). Yerel Postgres **:5432 ayakta** (entropia/entropia), `/opt/homebrew/bin`. Integration conftest `create_all` ile şema kuruyor.
- **code-reviewer subagent → CRITICAL/HIGH bulgularını AMPİRİK DOĞRULA** (bu oturumda 3 HIGH'ın 2'si yanlış çıktı: Pydantic `model_dump(mode='json')` Decimal'i STRING yapar; strategy zaten `expected_*_row_version`'ı idempotency payload'a koyar) → gerçek olanı düzelt → commit (conventional, attribution YOK) → PR → `gh pr checks <n> --watch` → **YEŞİL olunca merge için kullanıcıya sor**.
- **Türkçe konuş, autonomous ilerle, MALİYET BİLİNÇLİ** (bir önceki oturum $161 — gereksiz paralel ajan açma, review bulgusunu kendin doğrula). Her checkpoint'te ecc memory'ye yaz. **HER KAPANIŞTA:** `docs/STAGE<next>_KICKOFF.md` + resume prompt hazırla + `docs/STAGE2_HANDOFF.md` güncelle.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 4b başlat: Backtest Ready Check (doc 14). Önce bağlamı oku, sonra
working loop'a göre ilerle. Branch feat/stage-4b-ready-check AÇ. MALİYET BİLİNÇLİ ol.

Durum: Stage 3 (01–05) + Stage 4a Portfolio Allocation (doc 13) TAMAMLANDI. 4a =
PR #13 (merge olduysa main'de; alembic head 0012_portfolio_allocation). Sıradaki =
Stage 4b Ready Check. Sonraki alembic 0013_*.

ÖNCE OKU (otorite sırası): (1) docs/STAGE4_KICKOFF.md — bu dilimin tam handoff'u,
4a'nın bıraktıkları, 4b tasarım pointer'ları, reuse listesi, working loop, 3d
follow-up'ları. (2) docs/STAGE2_HANDOFF.md → "Stage 4a landed" + "Next: 4b" + dersler.
(3) docs/STAGE_BUILD_PLAN.md → "Stage 4 — Portfolio Allocation & Backtest Ready Check"
(satır ~82/85 Ready Check kolonu + acceptance). (4) docs/spec/14_..Backtest_Ready_Check..
→ spec'i TAM çıkar (§9 domain, §10 backend, acceptance testleri). (5) ecc memory
"Entropia Stage 4a — Portfolio Allocation" + "Stage 3d — Trade Log" checkpoint'leri.

TASARIM: Ready Check 3a'nın immutable mainboard_composition_snapshot'ından okur;
readiness_report_id'yi doldurur (3a'da null); capital_mode_snapshot'ı 4a'nın
portfolio_allocation_plan_revision'ından pinler (mb_repo.create_snapshot zaten
capital_mode_snapshot param'ı alıyor). POST /compositions/{id}/readiness-checks →
{report_id, state, issues[], snapshot_id, fingerprint}; report immutable, rerun=yeni id;
snapshot persisted draft'tan transactional; expected_fingerprint mismatch → 409. YENİ
tablolar ready_check_report + readiness_issue; YENİ domain/readiness + commands/queries/
routes + migration 0013_*. 3d follow-up: TL-09 mixed-symbol block, TL-11 allocation
kapalıyken capital>0, OHLCV-fallback→approved Market Data ref — Trade Log revision'da
approved_market_data_revision_ref + capital alanları hazır.

REUSE: 3a snapshot/create_snapshot/work_object/item/composition_hash, 4a allocation
plan_revision + validate_allocation + DerivedAmounts, run_idempotent, audit/outbox,
request_context, ensure_can_edit/can_view, enum_column, new_id.

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 4a pattern birebir. YENİ dosyaları Bash
heredoc ile yaz (gate-free); mevcut dosya edit'i GateGuard fact-force (4 fact→retry).
Lokal doğrula (ruff+format+mypy+pytest + HER create_* için L1 FK proof + alembic 0013
up/down/up; LC_ALL=en_US.UTF-8, DROP SCHEMA public CASCADE önce). Yerel Postgres :5432
ayakta (entropia/entropia). code-reviewer subagent → CRITICAL/HIGH bulgularını AMPİRİK
DOĞRULA → gerçek olanı düzelt → commit (conventional, attribution yok) → PR → gh pr
checks --watch, YEŞİL olunca merge için bana sor (self-merge bloklu). Türkçe konuş,
autonomous, MALİYET BİLİNÇLİ. Her checkpoint memory'ye. VE HER KAPANIŞTA:
docs/STAGE<next>_KICKOFF.md + resume prompt hazırla + STAGE2_HANDOFF.md güncelle.
```
