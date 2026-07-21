# Entropia — Claude Operating Guide

Backend-first, **spec-driven, staged** build (FastAPI + Postgres + Alembic + dramatiq).
Specs live in `docs/spec/NN_*`; the stage roadmap is `docs/STAGE_BUILD_PLAN.md`; the
running handoff is `docs/STAGE2_HANDOFF.md`; each slice has a `docs/STAGE<x>_KICKOFF.md`
with a **paste-ready resume prompt** at the bottom.

> Conversation language: **Turkish**. Technical identifiers stay in English.

---

## Session START protocol (do this FIRST, every session)

1. **Verify — the handoff/summary is STALE-BY-DEFAULT.** Never trust a prior-session
   summary or local branch. Run `git fetch`, `git log --oneline origin/main -6`,
   `gh pr list --state all`. Confirm what actually **landed/merged** before acting.
2. **Read in authority order:** (1) latest `docs/STAGE<next>_KICKOFF.md` (this slice's
   full handoff), (2) `docs/STAGE2_HANDOFF.md` ("... landed" + "Next"), (3)
   `docs/STAGE_BUILD_PLAN.md` (stage table + acceptance), (4) `docs/spec/NN_*` (extract
   the spec FULLY), (5) memory checkpoints for the prior stage (ecc graph + claude-mem).
3. The **paste-ready resume prompt** at the bottom of the kickoff doc is your
   continuation seed — that is what gets pasted into a fresh session.
4. **Kod tarafına geçmeden:** dokunacağın alanın `docs/CODEMAPS/` haritasını oku, sonra
   `codebase-memory-mcp` ile sembolleri bul (§"Kod arama"). Geçmiş bir slice'ın ayrıntısı
   gerekiyorsa `docs/PROJECT_HISTORY.md`'den **hedefli** oku — baştan sona okuma.

---

## Session CLOSING ritual (do this at EVERY close — MANDATORY)

Before stopping a working session, produce **ALL** of the following:

1. **Handoff** — update `docs/STAGE2_HANDOFF.md`: add a `## Stage <x> — <title> landed (PR #n)`
   entry (migration, new tables, test counts, review outcome, deferred items) and set
   `## Next: Stage <y> — <title>`.
2. **Kickoff + resume prompt** — create/refresh `docs/STAGE<next>_KICKOFF.md`: where we
   are, what the last slice **left behind (reuse anchors with exact symbol names)**, next
   design pointers, REUSE list, working-loop method, and a **paste-ready resume prompt
   block** (the exact text to paste into a clean session to continue).
3. **Tarihçe + özet — İKİSİ AYRI (context disiplini):**
   - **`docs/PROJECT_HISTORY.md`** → slice'ın **tam** kaydı buraya eklenir (ne landed,
     migration, OCC biçimi, test sayıları, honest boundary'ler).
   - **`CLAUDE.md` §Current position** → SADECE 5–6 satırlık özet güncellenir (HEAD sha,
     alembic head, test sayıları, son dalga, Next). **Buraya slice anlatısı YAZMA** —
     CLAUDE.md her oturumda tamamı context'e yüklenir, ince kalmak zorunda.
4. **Memory checkpoint — write BOTH systems:**
   - **ecc knowledge graph** — an entity `Entropia Stage <x> — <title>` with rich factual
     observations + a relation to the next stage (`unblocks`).
   - **claude-mem** — a checkpoint observation for the slice (searchable via `mem-search`).
5. **Codemap tazeleme** — slice yeni endpoint / tablo / sayfa / job eklediyse
   `docs/CODEMAPS/` içindeki ilgili haritayı güncelle (veya `ecc:update-codemaps`).
6. **Commit -> PR -> await merge** — commit on branch `docs/stage-<x>-landed` (conventional
   message, **NO AI attribution**), push, open a PR to `main`, `gh pr checks <n> --watch`;
   **self-merge is blocked -> ask the user to merge** once green.

---

## Conventions

- **Cost-conscious.** No unnecessary parallel agents or full-file reads. **Empirically
  verify** every code-review CRITICAL/HIGH finding before fixing (they are often wrong).
- **Direct-author (no Workflow)** for backend slices; mirror the previous slice's pattern
  (module-level async commands, one-tx no-commit, `run_idempotent`,
  `session.refresh(with_for_update=True)`, `_audit_and_outbox`).
- **GateGuard:** write NEW files via Bash heredoc (`cat > f << 'PYEOF'`) -> gate-free; an
  EDIT/WRITE to an existing file triggers fact-force (present 4 facts: importers / affected
  public API / data schema / user request verbatim -> retry). First Bash of a session
  triggers a one-time fact gate.
- **Local verify (backend):** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov -q`
  + an **L1 FK insert-order proof for every new `create_*`** + **alembic `<n>` up/down/up**
  (`LC_ALL=en_US.UTF-8`, `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` before the proof)
  + migration<->model column parity. Local Postgres on **:5432** (`entropia`/`entropia`).
- **Git:** `feat/stage-<x>-<slug>` for features, `docs/stage-<x>-landed` for closing docs.
  Commit `<type>(stage-<x>): <subject>`. **No AI attribution** (disabled globally).
- **Stage order is authoritative** (`STAGE_BUILD_PLAN.md`) — never skip sub-stages.
  Stage 5 = docs 15/16/17; Stage 6 = docs 18/19/20; Stage 7 = docs 21/22.
- **UI / frontend = v18 mockup is the visual reference (mandatory).** Every frontend/UI
  change takes `docs/spec/index_guncellenmis_duzeltilmis_v18.html` (the canonical v18 mockup)
  as its layout/style source of truth; the theme lives in `frontend/src/styles/global.css`
  variables (`--accent:#00a9e8 --border:#cfcfcf --radius:4px --text:#222`, Arial). Work is
  **presentation-only** — never touch route paths, react-query keys, OCC tokens
  (If-Match / `expected_*_version` / `X-*-Version`), Idempotency-Key, hooks, SSE taxonomy,
  API calls, or `lib/*.ts` data logic; `app/nav.ts` NAV/ALL_NAV_ITEMS stay verbatim. A broken
  test is re-aligned to the NEW markup (option values + OCC/Idempotency assertions unchanged;
  only visible labels / container scope via `aria-label` + `role`). To preview locally,
  `cp docs/spec/index_guncellenmis_duzeltilmis_v18.html frontend/public/mockup_v18.html` (a
  gitignored dev-only copy — canonical stays in `docs/spec/`).

---

## Current position (keep in sync at each closing)

> Aşağıdaki değerler **2026-07-20** tarihinde repodan empirik doğrulandı. Yine de
> **STALE-BY-DEFAULT** kabul et: §Session START adım 1'i çalıştırmadan bunlara güvenme.

- **Durum:** V1 ROADMAP COMPLETE (Stages 0–8, docs 01–22) + post-V1 + **video-alignment
  dalgası**. Tüm route yüzeyleri frontend'e bağlı; TIER 2 sayfa haritası 24/24.
- **`main` HEAD:** `8e9a1f4` (PR **#323** merge). Açık PR **yok**.
- **alembic head:** **`0035_portfolio_rules`** (35 migration, tek head — `0023` DEĞİL)
- **Testler:** ⚠️ **doğrulanmadı** — sayı yazmıyorum çünkü elimdeki rakamlar bayattı.
  CI server-truth için: `gh run list --branch main --limit 1` → job log'undan oku.
- **Son dalga (#313–#323):** #313 request-tx commit sırası · #314/#318 Mainboard Add
  Strategy + legacy item hijyeni · #315 Docker'sız local stack docs · #316 approved
  indicator uçtan uca kullanılabilir · #317 Result headline render crash · **#319
  per-item contribution breakdown** (correlation / diversification / marginal deltas) ·
  **#320 portfolio-level rules** (Max Total Exposure + cross-item conflict policy) ·
  #321 openapi snapshot · #322 README · #323 handoff docs

- **Next — video-alignment kalan iş** (kaynak: `docs/spec/Video Anlatımı /entropia_transkript.md`;
  ayrıntı `docs/STAGE2_HANDOFF.md:2262` + `docs/POST_V1_KICKOFF.md:42`):
  - **KALAN-A ✅ TAMAM** — Market Data Browse File upload UI (video 9:24–12:37): tek submit
    create→upload→finalize→analysis zinciri + detail poll → verified → Admin approve →
    bundle; e2e 02 tam yolculuk canlı stack'te yeşil. Kayıt: `docs/PROJECT_HISTORY.md`
    "KALAN-A" + `docs/STAGE2_HANDOFF.md` landed girdisi. vitest 511/511.
  - **KALAN-B ✅ TAMAM** — Portfolio "Use Allocation Backtest" + Mainboard per-item pay
    görünürlüğü (video 7:16–9:24): toggle backend'de `draft.enabled` olarak zaten vardı
    (Portfolio checkbox'ı, PR #113); Mainboard'a server-truth mode şeridi + per-satır
    `Share %` rozetleri + Portfolio deep-link eklendi. Kayıt: `docs/STAGE2_HANDOFF.md`
    "KALAN-B" landed girdisi. vitest 514/514.
  - **KALAN-C ✅ TAMAM** — öğenin evrene katkısı (video 3:35) → PR #319 + #320.
  - **R2-13 ✅ TAMAM** — 22 sayfa screenshot matrisi (122 PNG baseline + 20 prototip referansı)
    + sapma listesi `docs/implementation/v18_visual_deviations.md` (6 FIX adayı) + 8 kritik
    sayfa `toHaveScreenshot` regression (`frontend/e2e` `npm run screenshots|visual`).
    Sıradaki: **R2-14** (responsive+a11y son geçiş + PO onayı).
- **KAPSAM DIŞI (bilerek):** retention auto-purge (doc 20 §16 — "Production V1'de kapalı"),
  LLM generation (Future-Dev), Graphic View renderer (doc 22 — V18 statik placeholder kalır).

> **Tam tarihsel kayıt** — her PR'ın ne getirdiği, ENGINE_VERSION geçmişi, her sayfanın OCC
> token biçimi, honest boundary'ler: **`docs/PROJECT_HISTORY.md`**. Bir slice'ın ayrıntısı
> gerektiğinde oradan **OKU**; buraya geri taşıma. Kapanışta yeni slice kaydı **oraya** yazılır,
> buradaki özet 5–6 satır güncellenir.

---

## Kod arama — dosya okumadan ÖNCE (ZORUNLU)

Bu repo **488 dosya / ~114k satır**. Kör grep + tam dosya okuma hem pahalı hem yavaş.
**Önce graph'a sor, sonra dosya oku.**

`codebase-memory-mcp` bu repoyu **indekslemiş durumda** (~13k node / ~59k edge).
ToolSearch ile yükle ve ilk başvuru noktası yap:

| Araç | Ne için |
|---|---|
| `search_graph` | fonksiyon / class / route bul (isim veya qualified-name deseni) |
| `trace_path` | çağrı zinciri, veri akışı, servisler arası iz |
| `get_code_snippet` | sembolün tam kaynağı (kesin satır aralığı) |
| `get_architecture` | katman / modül yapısı |
| `search_code` | graph-destekli metin araması |

Grep/Glob'u **config, doc ve kod-dışı** dosyalar için serbestçe kullan.
Düzenlemeden önce **her zaman** Read (Edit bunu zaten zorunlu kılar).

**Sıkıştırılmış mimari haritalar → `docs/CODEMAPS/`**

| Harita | İçerik |
|---|---|
| `BACKEND_ROUTES.md` | her endpoint: path → command/query → OCC biçimi → Idempotency → rol kapısı |
| `BACKEND_LAYERS.md` | commands / queries / domain modül haritası + dokunulan tablolar |
| `DATA_MODEL.md` | tablolar, FK'ler, soft-delete + row_version kolonları, alembic head |
| `FRONTEND_MAP.md` | sayfa → `lib/*.ts` → react-query key → endpoint grubu; SSE `EVENT_QUERY_KEYS` |
| `JOBS_AND_EVENTS.md` | dramatiq actor'ları, kuyruklar, outbox→SSE akışı, event taksonomisi |

Bir alana **ilk kez** dokunuyorsan ilgili codemap'i oku — kod taramaya oradan başla.
Codemap'ler türetilmiş dosyadır: mimari değişince `ecc:update-codemaps` ile tazele.
